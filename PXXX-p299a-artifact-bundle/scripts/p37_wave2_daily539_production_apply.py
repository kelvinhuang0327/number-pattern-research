"""
p37_wave2_daily539_production_apply.py
=======================================
P37 Wave 2 — DAILY_539 Production Apply

Applies 9000 replay rows for the 6 Wave 2 DAILY_539 strategies
to the production database (lottery_api/data/lottery_v2.db).

This script is the authorized production-apply companion to P36. It:
  1. Validates pre-flight: production rows == 19960 (P36 baseline)
  2. Regenerates the same 9000 rows as P36 (deterministic, same algorithm)
  3. Runs a duplicate check: expects 0 Wave 2 rows already in production
  4. Applies 9000 rows to production inside a single atomic transaction
  5. Verifies post-apply: production rows == 28960
  6. Saves apply manifest to outputs/replay/p37_wave2_daily539_production_apply_20260523.json

Row semantics:
  - dry_run = 0  (production rows, not a rehearsal)
  - lifecycle_status = DRY_RUN (NOT changed to ONLINE)
  - controlled_apply_id = "P37_DAILY539_WAVE2_9000_PROD_20260523"
  - truth_level = "DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED"
  - source = "P37_WAVE2_PRODUCTION_APPLY"
  - replay_run_id = "p37_wave2_prod_20260523"

LIFECYCLE: All 6 strategies remain DRY_RUN.
           No lifecycle_status change. No _REGISTRY/_ALL_ADAPTERS mutation.

GOVERNANCE:
  - Must be run on branch p37-wave2-daily539-production-apply
  - Production DB write is one-way; rollback requires explicit intervention
  - Authorized by user phrase: YES apply P37 production wave2 daily539

STRATEGIES (6):
  markov_1bet_539, acb_single_539, zone_gap_3bet_539,
  539_3bet_orthogonal, p0b_539_3bet_f_cold_fmid, p0c_539_3bet_f_cold_x2

Usage:
  python3 scripts/p37_wave2_daily539_production_apply.py
  python3 scripts/p37_wave2_daily539_production_apply.py --json-out outputs/replay/p37_wave2_daily539_production_apply_20260523.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ─── Path setup ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay"

# ─── Constants ────────────────────────────────────────────────────────────────

PRE_APPLY_PROD_ROWS   = 19960   # Expected row count BEFORE apply
POST_APPLY_PROD_ROWS  = 28960   # Expected row count AFTER apply  (19960 + 9000)
EXPECTED_APPLIED_ROWS = 9000    # 6 strategies × 1500 draws each

WINDOW_PERIODS = 1500           # replay spans last 1500 DAILY_539 draws
MIN_HISTORY    = 100            # minimum history draws required
STRATEGIES_PER_RUN = 6

CONTROLLED_APPLY_ID = "P37_DAILY539_WAVE2_9000_PROD_20260523"
TRUTH_LEVEL         = "DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED"
SOURCE              = "P37_WAVE2_PRODUCTION_APPLY"
RUN_ID              = "p37_wave2_prod_20260523"

WAVE2_STRATEGY_IDS = frozenset({
    "markov_1bet_539",
    "acb_single_539",
    "zone_gap_3bet_539",
    "539_3bet_orthogonal",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
})

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Pre-flight check ─────────────────────────────────────────────────────────

def _check_prod_rows(expected: int) -> int:
    """Assert production replay row count is exactly `expected`. Returns count."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == expected, (
        f"PRODUCTION ROW COUNT MISMATCH: expected {expected}, got {count}."
    )
    return count


# ─── Draw loader ──────────────────────────────────────────────────────────────

def _load_daily539_draws() -> list[dict]:
    """
    Load all DAILY_539 draws from production DB, sorted chronologically.
    Returns list of dicts: [{draw, date, numbers}, ...]
    READ-ONLY — no writes.
    """
    conn = sqlite3.connect(str(PROD_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers FROM draws "
            "WHERE lottery_type = 'DAILY_539' "
            "ORDER BY date ASC, CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()

    draws = []
    for row in rows:
        nums = json.loads(row["numbers"]) if isinstance(row["numbers"], str) else row["numbers"]
        draws.append({
            "draw": row["draw"],
            "date": row["date"],
            "numbers": [int(n) for n in nums],
        })
    return draws


# ─── Provenance hash ──────────────────────────────────────────────────────────

def _provenance_hash(strategy_id: str, target_draw: str, numbers: list[int]) -> str:
    payload = f"{strategy_id}|{target_draw}|{sorted(numbers)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ─── Single-draw prediction runner ───────────────────────────────────────────

def _run_one_prediction(adapter, history: list[dict], target: dict) -> dict:
    """Run one prediction for a single (adapter, target_draw) pair.
    Returns a row dict ready for production DB insertion (dry_run=0).
    """
    strategy_id = adapter.meta.strategy_id
    strategy_name = adapter.meta.strategy_name
    strategy_version = adapter.meta.strategy_version
    lottery_type = "DAILY_539"

    replay_status = "PREDICTED"
    reject_reason = None
    predicted_numbers = None
    predicted_special = None
    hit_numbers = None
    hit_count = 0

    now_str = datetime.now(timezone.utc).isoformat()

    try:
        numbers, special = adapter.get_one_bet(history, lottery_type)
        predicted_numbers = json.dumps(numbers)
        predicted_special = None

        actual_nums = target["numbers"]
        hits = sorted(set(numbers) & set(actual_nums))
        hit_numbers = json.dumps(hits)
        hit_count = len(hits)

    except ValueError as exc:
        replay_status = "INSUFFICIENT_HISTORY"
        reject_reason = str(exc)
    except AssertionError as exc:
        replay_status = "INVALID_OUTPUT"
        reject_reason = str(exc)
    except Exception as exc:
        replay_status = "REPLAY_ERROR"
        reject_reason = str(exc)
        logger.warning("Prediction error %s / %s: %s", strategy_id, target["draw"], exc)

    history_cutoff = history[-1]["draw"] if history else None

    prov_hash = (
        _provenance_hash(
            strategy_id,
            str(target["draw"]),
            json.loads(predicted_numbers) if predicted_numbers else [],
        )
        if predicted_numbers
        else None
    )

    return {
        "lottery_type": lottery_type,
        "target_draw": str(target["draw"]),
        "target_date": target.get("date"),
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
        "history_cutoff_draw": str(history_cutoff) if history_cutoff else None,
        "replay_status": replay_status,
        "reject_reason": reject_reason,
        "predicted_numbers": predicted_numbers,
        "predicted_special": predicted_special,
        "actual_numbers": json.dumps(target["numbers"]),
        "actual_special": None,
        "hit_numbers": hit_numbers,
        "hit_count": hit_count,
        "special_hit": 0,
        "replay_run_id": RUN_ID,
        "generated_at": now_str,
        "truth_level": TRUTH_LEVEL,
        "controlled_apply_id": CONTROLLED_APPLY_ID,
        "source": SOURCE,
        "provenance_hash": prov_hash,
        "provenance_source": "p36_wave2_daily539_adapters.py",
        "dry_run": 0,                                    # PRODUCTION ROW
        "prediction_cutoff_date": history[-1]["date"] if history else None,
        "prediction_generated_at": now_str,
    }


# ─── Production DB apply ──────────────────────────────────────────────────────

def _apply_to_production(rows: list[dict]) -> tuple[int, int]:
    """
    INSERT rows into production DB inside a single atomic transaction.
    Returns (inserted, duplicate_count).
    Rolls back automatically on any exception.
    """
    inserted = 0
    duplicates = 0

    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        conn.execute("BEGIN EXCLUSIVE")
        for row in rows:
            try:
                conn.execute(
                    """
                    INSERT INTO strategy_prediction_replays (
                        lottery_type, target_draw, target_date, strategy_id,
                        strategy_name, strategy_version, history_cutoff_draw,
                        replay_status, reject_reason, predicted_numbers,
                        predicted_special, actual_numbers, actual_special,
                        hit_numbers, hit_count, special_hit, replay_run_id,
                        generated_at, truth_level, controlled_apply_id, source,
                        provenance_hash, provenance_source, dry_run,
                        prediction_cutoff_date, prediction_generated_at
                    ) VALUES (
                        :lottery_type, :target_draw, :target_date, :strategy_id,
                        :strategy_name, :strategy_version, :history_cutoff_draw,
                        :replay_status, :reject_reason, :predicted_numbers,
                        :predicted_special, :actual_numbers, :actual_special,
                        :hit_numbers, :hit_count, :special_hit, :replay_run_id,
                        :generated_at, :truth_level, :controlled_apply_id, :source,
                        :provenance_hash, :provenance_source, :dry_run,
                        :prediction_cutoff_date, :prediction_generated_at
                    )
                    """,
                    row,
                )
                inserted += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        conn.commit()
        logger.info("Production apply committed: inserted=%d, duplicates=%d", inserted, duplicates)
    except Exception:
        conn.rollback()
        conn.close()
        raise
    conn.close()
    return inserted, duplicates


# ─── Hit rate stats ───────────────────────────────────────────────────────────

def _compute_hit_stats(rows: list[dict]) -> dict:
    """Compute per-strategy hit rate statistics."""
    by_strategy: dict = defaultdict(lambda: defaultdict(int))

    for row in rows:
        sid = row["strategy_id"]
        if row["replay_status"] == "PREDICTED":
            by_strategy[sid]["predicted"] += 1
            hc = row.get("hit_count", 0) or 0
            by_strategy[sid][f"hit_{hc}"] += 1
        else:
            by_strategy[sid]["error"] += 1

    stats = {}
    for sid, counts in by_strategy.items():
        predicted = counts.get("predicted", 0)
        errors = counts.get("error", 0)
        hit_3plus = sum(counts.get(f"hit_{h}", 0) for h in (3, 4, 5))
        stats[sid] = {
            "predicted": predicted,
            "errors": errors,
            "total": predicted + errors,
            "hit_3plus": hit_3plus,
            "hit_3plus_rate": round(hit_3plus / predicted, 4) if predicted > 0 else 0.0,
            "hit_breakdown": {str(h): counts.get(f"hit_{h}", 0) for h in range(6)},
        }
    return stats


# ─── Main orchestrator ────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(
        description="P37 Wave 2 DAILY_539 Production Apply"
    )
    parser.add_argument(
        "--json-out",
        default=str(OUTPUT_DIR / "p37_wave2_daily539_production_apply_20260523.json"),
        help="Output JSON path",
    )
    args = parser.parse_args(argv)

    started_at = datetime.now(timezone.utc).isoformat()
    logger.info("=== P37 Wave 2 DAILY_539 Production Apply ===")
    logger.info("Started: %s", started_at)
    logger.info("Controlled apply ID: %s", CONTROLLED_APPLY_ID)
    logger.info("Authorization: YES apply P37 production wave2 daily539")

    # ── Pre-flight: assert production rows = 19960 ────────────────────────────
    logger.info("Pre-flight: checking production DB row count...")
    prod_rows_before = _check_prod_rows(PRE_APPLY_PROD_ROWS)
    logger.info("Pre-flight PASS: production DB has %d rows", prod_rows_before)

    # ── Duplicate check: no Wave 2 rows in production yet ────────────────────
    logger.info("Duplicate check: querying production for existing Wave 2 rows...")
    conn_check = sqlite3.connect(str(PROD_DB_PATH))
    existing_by_controlled = conn_check.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    existing_wave2 = conn_check.execute(
        "SELECT strategy_id, COUNT(*) as cnt FROM strategy_prediction_replays "
        "WHERE strategy_id IN (?,?,?,?,?,?) GROUP BY strategy_id",
        tuple(sorted(WAVE2_STRATEGY_IDS)),
    ).fetchall()
    conn_check.close()

    existing_wave2_map = {row[0]: row[1] for row in existing_wave2}
    total_existing_wave2 = sum(existing_wave2_map.values())

    logger.info("Existing P37 rows (by controlled_apply_id): %d", existing_by_controlled)
    logger.info("Existing Wave 2 strategy rows in production: %d", total_existing_wave2)

    assert existing_by_controlled == 0, (
        f"DUPLICATE GUARD FAILED: {existing_by_controlled} rows with controlled_apply_id="
        f"'{CONTROLLED_APPLY_ID}' already in production. P37 may have already run."
    )
    assert total_existing_wave2 == 0, (
        f"DUPLICATE GUARD FAILED: Wave 2 strategies already have {total_existing_wave2} "
        f"rows in production: {existing_wave2_map}"
    )
    logger.info("Duplicate check PASS: 0 Wave 2 rows in production")

    # ── Load DAILY_539 draws (read-only) ──────────────────────────────────────
    logger.info("Loading DAILY_539 draws from production DB (read-only)...")
    all_draws = _load_daily539_draws()
    total_draws = len(all_draws)
    logger.info("Loaded %d DAILY_539 draws", total_draws)

    assert total_draws >= MIN_HISTORY + WINDOW_PERIODS, (
        f"Need at least {MIN_HISTORY + WINDOW_PERIODS} draws, got {total_draws}"
    )

    # ── Select target draws (last 1500 periods) ───────────────────────────────
    target_draws = all_draws[-WINDOW_PERIODS:]
    logger.info(
        "Target window: %d draws (%s → %s)",
        len(target_draws),
        target_draws[0]["date"],
        target_draws[-1]["date"],
    )

    # ── Import Wave 2 adapters ────────────────────────────────────────────────
    from lottery_api.models.p36_wave2_daily539_adapters import WAVE2_ADAPTERS
    logger.info("Wave 2 adapters: %d", len(WAVE2_ADAPTERS))
    for a in WAVE2_ADAPTERS:
        logger.info("  - %s (%s)", a.meta.strategy_id, a.meta.lifecycle_status)

    # ── Generate production rows ───────────────────────────────────────────────
    logger.info(
        "Generating %d production rows (%d strategies × %d draws)...",
        EXPECTED_APPLIED_ROWS, STRATEGIES_PER_RUN, WINDOW_PERIODS,
    )

    all_rows: list[dict] = []
    per_strategy_progress: dict = {}

    for adapter in WAVE2_ADAPTERS:
        sid = adapter.meta.strategy_id
        strategy_rows = []
        errors = 0

        for i, target in enumerate(target_draws):
            # Causal slice: all draws STRICTLY BEFORE this target draw — no data leakage
            target_idx = total_draws - WINDOW_PERIODS + i
            history = all_draws[:target_idx]  # strictly before

            row = _run_one_prediction(adapter, history, target)
            strategy_rows.append(row)
            if row["replay_status"] != "PREDICTED":
                errors += 1

        per_strategy_progress[sid] = {
            "total": len(strategy_rows),
            "predicted": len(strategy_rows) - errors,
            "errors": errors,
        }
        all_rows.extend(strategy_rows)
        logger.info(
            "  %s: %d predicted, %d errors",
            sid, len(strategy_rows) - errors, errors,
        )

    generated_total = len(all_rows)
    logger.info("Total production rows generated: %d", generated_total)
    assert generated_total == EXPECTED_APPLIED_ROWS, (
        f"Row generation mismatch: expected {EXPECTED_APPLIED_ROWS}, got {generated_total}"
    )

    # ── Apply to production DB ────────────────────────────────────────────────
    logger.info("Applying %d rows to production DB (atomic transaction)...", generated_total)
    inserted, duplicates = _apply_to_production(all_rows)

    logger.info(
        "Production apply complete: inserted=%d, duplicates=%d",
        inserted, duplicates,
    )
    assert inserted == EXPECTED_APPLIED_ROWS, (
        f"APPLY MISMATCH: expected {EXPECTED_APPLIED_ROWS} inserted, got {inserted}. "
        f"duplicates={duplicates}"
    )
    assert duplicates == 0, (
        f"UNEXPECTED DUPLICATES: {duplicates} rows were not inserted due to UNIQUE constraint. "
        "Duplicate guard should have caught this."
    )

    # ── Post-apply verification ───────────────────────────────────────────────
    logger.info("Post-apply verification: checking production DB row count...")
    prod_rows_after = _check_prod_rows(POST_APPLY_PROD_ROWS)
    logger.info(
        "Post-apply PASS: production DB has %d rows (before=%d, inserted=%d)",
        prod_rows_after, prod_rows_before, inserted,
    )

    # Per-strategy verification
    conn_verify = sqlite3.connect(str(PROD_DB_PATH))
    strategy_counts_after = {
        row[0]: row[1]
        for row in conn_verify.execute(
            "SELECT strategy_id, COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id = ? GROUP BY strategy_id",
            (CONTROLLED_APPLY_ID,),
        ).fetchall()
    }
    conn_verify.close()
    logger.info("Per-strategy row counts after apply: %s", strategy_counts_after)

    for sid in WAVE2_STRATEGY_IDS:
        count = strategy_counts_after.get(sid, 0)
        assert count == WINDOW_PERIODS, (
            f"Strategy {sid}: expected {WINDOW_PERIODS} rows, got {count}"
        )

    # ── Hit rate stats ────────────────────────────────────────────────────────
    hit_stats = _compute_hit_stats(all_rows)

    # ── Build output manifest ─────────────────────────────────────────────────
    finished_at = datetime.now(timezone.utc).isoformat()

    result = {
        "p37_version": "20260523",
        "wave": 2,
        "lottery_type": "DAILY_539",
        "authorization": "YES apply P37 production wave2 daily539",
        "phase": "P37_WAVE2_DAILY539_PRODUCTION_APPLY",
        "classification": "P37_WAVE2_DAILY539_PRODUCTION_APPLY_MERGED_TO_MAIN",
        "status": "PASS",
        "started_at": started_at,
        "finished_at": finished_at,
        "controlled_apply_id": CONTROLLED_APPLY_ID,
        "truth_level": TRUTH_LEVEL,
        "source": SOURCE,
        "run_id": RUN_ID,
        "lifecycle_semantics": {
            "all_rows_lifecycle": "DRY_RUN",
            "online_rows": 0,
            "retired_rows": 0,
            "note": "P37 keeps all Wave 2 strategies as DRY_RUN. No lifecycle change to ONLINE.",
        },
        "production_rows_before": prod_rows_before,
        "production_rows_inserted": inserted,
        "production_rows_after": prod_rows_after,
        "strategies": [
            {"strategy_id": sid, "inserted": strategy_counts_after.get(sid, 0), "lifecycle": "DRY_RUN"}
            for sid in sorted(WAVE2_STRATEGY_IDS)
        ],
        "duplicate_check": "PASS",
        "transaction": "ATOMIC_COMMIT",
        "row_counts": {
            "prod_rows_before": prod_rows_before,
            "rows_generated": generated_total,
            "rows_inserted": inserted,
            "rows_duplicated": duplicates,
            "prod_rows_after": prod_rows_after,
        },
        "expected_row_counts": {
            "pre_apply": PRE_APPLY_PROD_ROWS,
            "post_apply": POST_APPLY_PROD_ROWS,
            "inserted": EXPECTED_APPLIED_ROWS,
        },
        "per_strategy_row_counts": strategy_counts_after,
        "per_strategy_generation": per_strategy_progress,
        "hit_statistics": hit_stats,
        "target_window": {
            "periods": WINDOW_PERIODS,
            "first_draw": str(target_draws[0]["draw"]),
            "last_draw": str(target_draws[-1]["draw"]),
            "first_date": target_draws[0]["date"],
            "last_date": target_draws[-1]["date"],
        },
        "preflight_pass": True,
        "duplicate_check_pass": True,
        "postflight_pass": True,
        "all_pass": True,
    }

    # ── Write output JSON ─────────────────────────────────────────────────────
    out_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    logger.info("Output JSON written: %s", out_path)

    logger.info("=== P37 COMPLETE: %s rows applied to production (19960 → 28960) ===", inserted)
    return result


if __name__ == "__main__":
    result = main()
    if result["status"] != "PASS":
        sys.exit(1)
