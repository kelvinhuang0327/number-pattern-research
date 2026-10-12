#!/usr/bin/env python3
"""
P36 Wave 2 — DAILY_539 Dry-Run + Temp DB Rehearsal
====================================================
P36: Wires replay adapter wrappers for the 6 Wave 2 DAILY_539 strategies,
generates 1500-period dry-run rows per strategy into a temp SQLite DB, runs
R1/R2/R3 temp rehearsal, and produces readiness artifacts.

AUTHORISATION GATE: This script is read-only with respect to the production DB.
  - Reads:  lottery_api/data/lottery_v2.db (draws only — no writes)
  - Writes: /tmp/p36_temp.db (temp DB, created fresh each run)
  - Output: outputs/replay/p36_wave2_daily539_dryrun_rehearsal_20260523.json
            outputs/replay/p36_temp_rehearsal_20260523.json

HARD RULES:
  - Production DB MUST remain at exactly 19960 rows after this script.
  - Temp DB rows are NEVER copied to production DB in P36.
  - lifecycle for all dry-run rows MUST be "DRY_RUN" (NOT "ONLINE").
  - Adapter wrappers are NOT registered in replay_strategy_registry.

Wave 2 Strategies (6 total × 1500 draws = 9000 rows):
  markov_1bet_539, acb_single_539, zone_gap_3bet_539,
  539_3bet_orthogonal, p0b_539_3bet_f_cold_fmid, p0c_539_3bet_f_cold_x2

P37 production apply requires separate explicit authorization.

Usage:
  cd /path/to/LotteryNew
  .venv/bin/python scripts/p36_wave2_daily539_dryrun_rehearsal.py
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List

# ─── Path setup ──────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(REPO_ROOT))

PROD_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
TEMP_DB_PATH = Path("/tmp/p36_temp.db")
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay"
DRYRUN_OUTPUT = OUTPUT_DIR / "p36_wave2_daily539_dryrun_rehearsal_20260523.json"
REHEARSAL_OUTPUT = OUTPUT_DIR / "p36_temp_rehearsal_20260523.json"

EXPECTED_PROD_ROWS = 19960
WINDOW_PERIODS = 1500     # dry-run spans last 1500 DAILY_539 draws
MIN_HISTORY = 100         # minimum history draws required for adapter
STRATEGIES_COUNT = 6
EXPECTED_DRY_RUN_ROWS = WINDOW_PERIODS * STRATEGIES_COUNT  # 9000

TRUTH_LEVEL = "P36_WAVE2_DAILY539_DRY_RUN"
RUN_ID = "p36_wave2_dryrun_20260523"

WAVE2_STRATEGY_IDS = [
    "markov_1bet_539",
    "acb_single_539",
    "zone_gap_3bet_539",
    "539_3bet_orthogonal",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
]

# P31B Wave 1 strategy IDs (must NOT appear in Wave 2)
WAVE1_STRATEGY_IDS = {
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
}

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ─── Production DB guard ──────────────────────────────────────────────────────

def _assert_prod_rows_unchanged(expected: int = EXPECTED_PROD_ROWS) -> int:
    """Assert production replay row count is exactly `expected`. Returns count."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()
        count = row[0] if row else 0
    finally:
        conn.close()
    if count != expected:
        raise RuntimeError(
            f"PRODUCTION ROW INVARIANT VIOLATED: expected {expected}, got {count}. "
            "Aborting P36 — production DB must not be modified."
        )
    return count


# ─── Draw loader ─────────────────────────────────────────────────────────────

def _load_daily539_draws() -> List[dict]:
    """
    Load all DAILY_539 draws from production DB, sorted chronologically (date ASC).
    Returns list of dicts: [{draw, date, numbers}, ...]
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


# ─── Temp DB setup ────────────────────────────────────────────────────────────

def _create_temp_db(path: Path) -> sqlite3.Connection:
    """Create (or recreate) temp SQLite DB with the strategy_prediction_replays schema."""
    if path.exists():
        path.unlink()

    conn = sqlite3.connect(str(path))
    conn.execute("""
        CREATE TABLE strategy_prediction_replays (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            lottery_type           TEXT    NOT NULL,
            target_draw            TEXT    NOT NULL,
            target_date            TEXT,
            strategy_id            TEXT    NOT NULL,
            strategy_name          TEXT,
            strategy_version       TEXT,
            history_cutoff_draw    TEXT,
            replay_status          TEXT    NOT NULL DEFAULT 'PREDICTED',
            reject_reason          TEXT,
            predicted_numbers      TEXT,
            predicted_special      TEXT,
            actual_numbers         TEXT,
            actual_special         TEXT,
            hit_numbers            TEXT,
            hit_count              INTEGER DEFAULT 0,
            special_hit            INTEGER DEFAULT 0,
            replay_run_id          TEXT,
            generated_at           TEXT,
            truth_level            TEXT,
            controlled_apply_id    TEXT,
            source                 TEXT,
            provenance_hash        TEXT,
            provenance_source      TEXT,
            dry_run                INTEGER DEFAULT 1,
            prediction_cutoff_date TEXT,
            prediction_generated_at TEXT,
            lifecycle              TEXT    DEFAULT 'DRY_RUN',
            is_retired             INTEGER DEFAULT 0,
            UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)
        )
    """)
    conn.commit()
    logger.info("Temp DB created: %s", path)
    return conn


# ─── Row insertion ────────────────────────────────────────────────────────────

def _to_db_row(row: dict, now_str: str) -> dict:
    """Convert a generate_dryrun_rows() row to DB insert dict."""
    import hashlib
    predicted = row.get("predicted_numbers")
    predicted_json = json.dumps(sorted(predicted)) if predicted else None

    prov_hash = None
    if predicted:
        payload = f"{row['strategy_id']}|{row['target_draw']}|{sorted(predicted)}"
        prov_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]

    return {
        "lottery_type": row["lottery_type"],
        "target_draw": row["target_draw"],
        "target_date": row.get("draw_date"),
        "strategy_id": row["strategy_id"],
        "strategy_name": row.get("strategy_name"),
        "strategy_version": row.get("strategy_version"),
        "history_cutoff_draw": row.get("history_cutoff_draw"),
        "replay_status": row.get("replay_status", "PREDICTED"),
        "reject_reason": row.get("reject_reason"),
        "predicted_numbers": predicted_json,
        "predicted_special": None,
        "actual_numbers": json.dumps(row.get("actual_numbers", [])),
        "actual_special": None,
        "hit_numbers": json.dumps(row.get("hit_numbers", [])),
        "hit_count": row.get("hit_count", 0),
        "special_hit": 0,
        "replay_run_id": RUN_ID,
        "generated_at": now_str,
        "truth_level": TRUTH_LEVEL,
        "controlled_apply_id": None,
        "source": "P36_WAVE2_DRYRUN",
        "provenance_hash": prov_hash,
        "provenance_source": "p36_wave2_daily539_adapters.py",
        "dry_run": 1,
        "prediction_cutoff_date": row.get("prediction_cutoff_date"),
        "prediction_generated_at": row.get("prediction_generated_at", now_str),
        "lifecycle": "DRY_RUN",
        "is_retired": 0,
    }


def _insert_rows(conn: sqlite3.Connection, db_rows: List[dict]) -> int:
    """Insert rows into temp DB. Returns number inserted. Skips duplicates."""
    inserted = 0
    for row in db_rows:
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
                    prediction_cutoff_date, prediction_generated_at,
                    lifecycle, is_retired
                ) VALUES (
                    :lottery_type, :target_draw, :target_date, :strategy_id,
                    :strategy_name, :strategy_version, :history_cutoff_draw,
                    :replay_status, :reject_reason, :predicted_numbers,
                    :predicted_special, :actual_numbers, :actual_special,
                    :hit_numbers, :hit_count, :special_hit, :replay_run_id,
                    :generated_at, :truth_level, :controlled_apply_id, :source,
                    :provenance_hash, :provenance_source, :dry_run,
                    :prediction_cutoff_date, :prediction_generated_at,
                    :lifecycle, :is_retired
                )
                """,
                row,
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # duplicate — expected in R2 idempotency check
    conn.commit()
    return inserted


# ─── R1 / R2 / R3 Rehearsal ──────────────────────────────────────────────────

def _r1_apply(conn: sqlite3.Connection, db_rows: List[dict]) -> dict:
    """R1: Insert all dry-run rows into temp DB. Expect EXPECTED_DRY_RUN_ROWS inserted."""
    inserted = _insert_rows(conn, db_rows)
    after = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    r1_ok = inserted == EXPECTED_DRY_RUN_ROWS and after == EXPECTED_DRY_RUN_ROWS
    logger.info("R1: inserted=%d, total=%d, expected=%d, ok=%s",
                inserted, after, EXPECTED_DRY_RUN_ROWS, r1_ok)
    return {
        "r1_inserted": inserted,
        "r1_total_after": after,
        "r1_expected": EXPECTED_DRY_RUN_ROWS,
        "r1_ok": r1_ok,
    }


def _r2_rerun(conn: sqlite3.Connection, db_rows: List[dict]) -> dict:
    """R2: Re-insert same rows — expect 0 new rows (idempotency check)."""
    before = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    inserted = _insert_rows(conn, db_rows)
    after = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    r2_idempotent = inserted == 0 and after == before
    logger.info("R2: before=%d, duplicate_inserted=%d, after=%d, idempotent=%s",
                before, inserted, after, r2_idempotent)
    return {
        "r2_before": before,
        "r2_duplicate_inserted": inserted,
        "r2_after": after,
        "r2_idempotent": r2_idempotent,
    }


def _r3_rollback(conn: sqlite3.Connection, temp_path: Path) -> dict:
    """R3: Rollback/restore — delete all rows from temp DB, verify 0 rows remain."""
    before = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.execute("DELETE FROM strategy_prediction_replays")
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    rollback_ok = after == 0
    logger.info("R3 rollback: before=%d, after=%d, ok=%s", before, after, rollback_ok)
    return {
        "r3_before": before,
        "r3_after": after,
        "r3_rollback_ok": rollback_ok,
    }


# ─── Schema validation ────────────────────────────────────────────────────────

def _validate_rows(rows: List[dict]) -> dict:
    """Validate schema constraints for all dry-run rows."""
    errors = []
    for i, row in enumerate(rows):
        sid = row.get("strategy_id", "?")
        lottery = row.get("lottery_type")
        lifecycle = row.get("lifecycle")
        pred = row.get("predicted_numbers")
        actual = row.get("actual_numbers")
        hit_nums = row.get("hit_numbers", [])
        hit_count = row.get("hit_count", 0)
        is_retired = row.get("is_retired")

        if lottery != "DAILY_539":
            errors.append(f"Row {i} ({sid}): lottery_type={lottery} expected DAILY_539")
        if lifecycle == "ONLINE":
            errors.append(f"Row {i} ({sid}): lifecycle=ONLINE is forbidden")
        if pred is not None:
            if len(pred) != 5:
                errors.append(f"Row {i} ({sid}): predicted_numbers len={len(pred)} expected 5")
            elif len(set(pred)) != 5:
                errors.append(f"Row {i} ({sid}): duplicate predicted_numbers {pred}")
            elif not all(1 <= n <= 39 for n in pred):
                errors.append(f"Row {i} ({sid}): out-of-range predicted_numbers {pred}")
        if hit_count != len(hit_nums):
            errors.append(f"Row {i} ({sid}): hit_count={hit_count} != len(hit_numbers)={len(hit_nums)}")
        if is_retired is not False and is_retired != 0:
            errors.append(f"Row {i} ({sid}): is_retired should be False, got {is_retired}")

    return {
        "total_rows": len(rows),
        "errors": errors,
        "valid": len(errors) == 0,
    }


# ─── Hit stats ────────────────────────────────────────────────────────────────

def _compute_hit_stats(rows: List[dict]) -> dict:
    """Compute per-strategy hit rate statistics from dry-run rows."""
    by_strategy: dict = defaultdict(lambda: defaultdict(int))

    for row in rows:
        sid = row["strategy_id"]
        if row.get("replay_status") == "PREDICTED":
            by_strategy[sid]["predicted"] += 1
            hc = row.get("hit_count", 0) or 0
            by_strategy[sid][f"hit_{hc}"] += 1
        else:
            by_strategy[sid]["error"] += 1

    stats = {}
    for sid in WAVE2_STRATEGY_IDS:
        counts = by_strategy.get(sid, {})
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

def main() -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    now_str = started_at
    logger.info("=== P36 Wave 2 DAILY_539 Dry-Run + Temp Rehearsal ===")
    logger.info("Started: %s", started_at)
    logger.info("Expected rows: %d strategies × %d draws = %d",
                STRATEGIES_COUNT, WINDOW_PERIODS, EXPECTED_DRY_RUN_ROWS)

    # ── Pre-flight: Production row invariant ──────────────────────────────────
    logger.info("Pre-flight: checking production DB row count...")
    prod_rows_before = _assert_prod_rows_unchanged()
    logger.info("Production DB: %d rows (PASS)", prod_rows_before)

    # ── Load DAILY_539 draws (read-only) ─────────────────────────────────────
    logger.info("Loading DAILY_539 draws from production DB (read-only)...")
    all_draws = _load_daily539_draws()
    total_draws = len(all_draws)
    logger.info("Loaded %d DAILY_539 draws", total_draws)

    assert total_draws >= MIN_HISTORY + WINDOW_PERIODS, (
        f"Need at least {MIN_HISTORY + WINDOW_PERIODS} draws, got {total_draws}"
    )

    # ── Import Wave 2 adapters ────────────────────────────────────────────────
    from lottery_api.models.p36_wave2_daily539_adapters import WAVE2_ADAPTERS, generate_dryrun_rows
    logger.info("Wave 2 adapters loaded: %d", len(WAVE2_ADAPTERS))
    for a in WAVE2_ADAPTERS:
        logger.info("  - %s (lifecycle=%s)", a.meta.strategy_id, a.meta.lifecycle_status)

    # ── Generate dry-run rows ─────────────────────────────────────────────────
    logger.info("Generating %d dry-run rows (%d strategies × %d draws)...",
                EXPECTED_DRY_RUN_ROWS, STRATEGIES_COUNT, WINDOW_PERIODS)

    raw_rows = generate_dryrun_rows(all_draws, rows_per_strategy=WINDOW_PERIODS)
    logger.info("Generated %d raw rows", len(raw_rows))

    # ── Schema validation ─────────────────────────────────────────────────────
    validation = _validate_rows(raw_rows)
    logger.info("Schema validation: valid=%s, errors=%d",
                validation["valid"], len(validation["errors"]))
    if not validation["valid"]:
        for err in validation["errors"][:10]:
            logger.error("  %s", err)

    # ── Convert to DB rows ────────────────────────────────────────────────────
    db_rows = [_to_db_row(r, now_str) for r in raw_rows]

    # ── Per-strategy row counts ───────────────────────────────────────────────
    per_strategy_counts: dict = defaultdict(int)
    for r in raw_rows:
        per_strategy_counts[r["strategy_id"]] += 1

    for sid in WAVE2_STRATEGY_IDS:
        logger.info("  %s: %d rows", sid, per_strategy_counts.get(sid, 0))

    # ── Create temp DB ────────────────────────────────────────────────────────
    conn = _create_temp_db(TEMP_DB_PATH)

    try:
        # R1: Apply
        logger.info("R1: Applying %d rows to temp DB...", len(db_rows))
        r1 = _r1_apply(conn, db_rows)

        # R2: Idempotency check
        logger.info("R2: Rerun idempotency check...")
        r2 = _r2_rerun(conn, db_rows)

        # R3: Rollback
        logger.info("R3: Rollback rehearsal...")
        r3 = _r3_rollback(conn, TEMP_DB_PATH)

        # Re-insert for artifact inspection
        _insert_rows(conn, db_rows)
        logger.info("Rows re-inserted for artifact inspection")

    finally:
        conn.close()

    # ── Post-flight: Production row invariant ─────────────────────────────────
    prod_rows_after = _assert_prod_rows_unchanged()
    logger.info("Post-flight production DB: %d rows (PASS)", prod_rows_after)

    # ── Hit stats ─────────────────────────────────────────────────────────────
    hit_stats = _compute_hit_stats(raw_rows)

    # ── All pass determination ────────────────────────────────────────────────
    all_rehearsals_pass = (
        r1["r1_ok"]
        and r2["r2_idempotent"]
        and r3["r3_rollback_ok"]
        and validation["valid"]
        and prod_rows_before == prod_rows_after
    )

    # ── Rehearsal JSON ────────────────────────────────────────────────────────
    rehearsal = {
        "phase": "P36_WAVE2_DAILY539_DRY_RUN",
        "run_id": RUN_ID,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "temp_db_path": str(TEMP_DB_PATH),
        "prod_rows_before": prod_rows_before,
        "prod_rows_after": prod_rows_after,
        "prod_rows_unchanged": prod_rows_before == prod_rows_after,
        "total_dry_run_rows": len(raw_rows),
        "expected_dry_run_rows": EXPECTED_DRY_RUN_ROWS,
        "row_count_ok": len(raw_rows) == EXPECTED_DRY_RUN_ROWS,
        "schema_validation": validation,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "per_strategy_counts": dict(per_strategy_counts),
        "hit_stats": hit_stats,
        "all_rehearsals_pass": all_rehearsals_pass,
    }

    # ── Dryrun JSON (main output) ─────────────────────────────────────────────
    dryrun = {
        "p36_version": "20260523",
        "wave": 2,
        "lottery_type": "DAILY_539",
        "total_dryrun_rows": len(raw_rows),
        "strategies": [
            {
                "strategy_id": sid,
                "row_count": per_strategy_counts.get(sid, 0),
                "lifecycle": "DRY_RUN",
            }
            for sid in WAVE2_STRATEGY_IDS
        ],
        "temp_rehearsal": {
            "R1_insert_count": r1.get("r1_inserted", 0),
            "R2_duplicate_count": r2.get("r2_duplicate_inserted", 0),
            "R3_rollback": "PASS" if r3.get("r3_rollback_ok") else "FAIL",
        },
        "production_rows_before": prod_rows_before,
        "production_rows_after": prod_rows_after,
        "schema_validation": {
            "valid": validation["valid"],
            "error_count": len(validation["errors"]),
        },
        "all_rehearsals_pass": all_rehearsals_pass,
        "classification": "P36_WAVE2_DAILY539_DRYRUN_REHEARSAL_READY" if all_rehearsals_pass
                          else "P36_WAVE2_DAILY539_DRYRUN_REHEARSAL_FAIL",
        "lifecycle_semantics": {
            "all_rows_lifecycle": "DRY_RUN",
            "online_rows": 0,
            "retired_rows": 0,
            "note": "P36 is dry-run only. Production apply requires P37 authorization.",
        },
        "production_apply_readiness": {
            "ready": all_rehearsals_pass,
            "requires_p37_authorization": True,
            "p37_authorization_phrase": "YES apply P37 production wave2 daily539",
            "blockers": [] if all_rehearsals_pass else ["rehearsal_failed"],
        },
        "run_id": RUN_ID,
        "started_at": started_at,
        "finished_at": rehearsal["finished_at"],
    }

    # ── Write outputs ─────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    DRYRUN_OUTPUT.write_text(json.dumps(dryrun, indent=2, ensure_ascii=False))
    logger.info("Dryrun output: %s", DRYRUN_OUTPUT)

    REHEARSAL_OUTPUT.write_text(json.dumps(rehearsal, indent=2, ensure_ascii=False))
    logger.info("Rehearsal output: %s", REHEARSAL_OUTPUT)

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info("")
    logger.info("=== P36 SUMMARY ===")
    logger.info("Prod rows before:     %d", prod_rows_before)
    logger.info("Prod rows after:      %d", prod_rows_after)
    logger.info("Prod rows unchanged:  %s", prod_rows_before == prod_rows_after)
    logger.info("Total dryrun rows:    %d (expected %d)", len(raw_rows), EXPECTED_DRY_RUN_ROWS)
    logger.info("Schema valid:         %s", validation["valid"])
    logger.info("R1 (apply):           %s", r1["r1_ok"])
    logger.info("R2 (idempotent):      %s", r2["r2_idempotent"])
    logger.info("R3 (rollback ok):     %s", r3["r3_rollback_ok"])
    logger.info("All rehearsals pass:  %s", all_rehearsals_pass)
    logger.info("Classification:       %s", dryrun["classification"])
    logger.info("")
    logger.info("Outputs:")
    logger.info("  %s", DRYRUN_OUTPUT)
    logger.info("  %s", REHEARSAL_OUTPUT)

    return dryrun


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get("all_rehearsals_pass") else 1)
