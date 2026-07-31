#!/usr/bin/env python3
"""
P47 Wave 4 — POWER_LOTTO Dry-Run + Temp DB Rehearsal
=====================================================
P47: Wires replay adapter wrappers for the 3 Wave 4 POWER_LOTTO strategies,
generates 1500-period dry-run rows per strategy into a temp SQLite DB, runs
R1/R2/R3 temp rehearsal, and produces readiness artifacts.

AUTHORISATION GATE: This script is read-only with respect to the production DB.
  - Reads:  lottery_api/data/lottery_v2.db (draws only — no writes)
  - Writes: /tmp/p47_temp_rehearsal.db (temp DB, created fresh each run)
  - Output: outputs/replay/p47_powerlotto_wave4_dryrun_rehearsal_20260524.json
            outputs/replay/p47_temp_rehearsal_20260524.json

HARD RULES:
  - Production DB MUST remain at exactly 37960 rows after this script.
  - Temp DB rows are NEVER copied to production DB in P47.
  - lifecycle for all dry-run rows MUST be "DRY_RUN" (NOT "ONLINE").
  - Adapter wrappers are NOT registered in replay_strategy_registry.
  - POWER_LOTTO format: first zone 6 unique ints in [1,38], special 1 int in [1,8]
  - hit_count: FIRST-ZONE ONLY (do NOT count special)
  - special_hit: 1 if predicted_special == actual_special, else 0

Wave 4 Strategies (3 total × 1500 draws = 4500 rows):
  pp3_freqort_4bet, midfreq_fourier_mk_3bet, midfreq_fourier_2bet

P48 production apply requires separate explicit authorization.

Usage:
  cd /path/to/LotteryNew
  .venv/bin/python scripts/p47_powerlotto_wave4_dryrun_rehearsal.py
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
TEMP_DB_PATH = Path("/tmp/p47_temp_rehearsal.db")
OUTPUT_DIR = REPO_ROOT / "outputs" / "replay"
DRYRUN_OUTPUT = OUTPUT_DIR / "p47_powerlotto_wave4_dryrun_rehearsal_20260524.json"
REHEARSAL_OUTPUT = OUTPUT_DIR / "p47_temp_rehearsal_20260524.json"

EXPECTED_PROD_ROWS = 37960
WINDOW_PERIODS = 1500     # dry-run spans last 1500 POWER_LOTTO draws
STRATEGIES_COUNT = 3
EXPECTED_DRY_RUN_ROWS = WINDOW_PERIODS * STRATEGIES_COUNT  # 4500

TRUTH_LEVEL = "P47_WAVE4_POWERLOTTO_DRY_RUN"
RUN_ID = "p47_wave4_powerlotto_dryrun_20260524"

WAVE4_STRATEGY_IDS = [
    "pp3_freqort_4bet",
    "midfreq_fourier_mk_3bet",
    "midfreq_fourier_2bet",
]

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
            "Aborting P47 — production DB must not be modified."
        )
    return count


# ─── Draw loader ─────────────────────────────────────────────────────────────

def _load_powerlotto_draws() -> List[dict]:
    """
    Load all POWER_LOTTO draws from production DB, sorted chronologically (draw# ASC).
    Returns list of dicts: [{draw, date, numbers, special}, ...]
    """
    conn = sqlite3.connect(str(PROD_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type = 'POWER_LOTTO' "
            "ORDER BY CAST(draw AS INTEGER) ASC"
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
            "special": int(row["special"]) if row["special"] is not None else None,
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
    predicted_special = row.get("predicted_special")

    prov_hash = None
    if predicted:
        payload = f"{row['strategy_id']}|{row['target_draw']}|{sorted(predicted)}|{predicted_special}"
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
        "predicted_special": str(predicted_special) if predicted_special is not None else None,
        "actual_numbers": json.dumps(row.get("actual_numbers", [])),
        "actual_special": row.get("actual_special"),
        "hit_numbers": json.dumps(row.get("hit_numbers", [])),
        "hit_count": row.get("hit_count", 0),
        "special_hit": row.get("special_hit", 0),
        "replay_run_id": RUN_ID,
        "generated_at": now_str,
        "truth_level": TRUTH_LEVEL,
        "controlled_apply_id": None,
        "source": "P47_WAVE4_POWERLOTTO_DRYRUN",
        "provenance_hash": prov_hash,
        "provenance_source": "p47_wave4_powerlotto_adapters.py",
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


def _r3_rollback(conn: sqlite3.Connection) -> dict:
    """R3: Rollback — delete all rows from temp DB, verify 0 rows remain."""
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
    """Validate schema constraints for all dry-run POWER_LOTTO rows."""
    errors = []
    for i, row in enumerate(rows):
        sid = row.get("strategy_id", "?")
        lottery = row.get("lottery_type")
        lifecycle = row.get("lifecycle")
        pred = row.get("predicted_numbers")
        hit_nums = row.get("hit_numbers", [])
        hit_count = row.get("hit_count", 0)
        pred_special = row.get("predicted_special")
        special_hit = row.get("special_hit", 0)

        if lottery != "POWER_LOTTO":
            errors.append(f"Row {i} ({sid}): lottery_type={lottery} expected POWER_LOTTO")
        if lifecycle == "ONLINE":
            errors.append(f"Row {i} ({sid}): lifecycle=ONLINE is forbidden")
        if pred is not None:
            if len(pred) != 6:
                errors.append(f"Row {i} ({sid}): predicted_numbers len={len(pred)} expected 6")
            elif len(set(pred)) != 6:
                errors.append(f"Row {i} ({sid}): duplicate predicted_numbers {pred}")
            elif not all(1 <= n <= 38 for n in pred):
                errors.append(f"Row {i} ({sid}): out-of-range predicted_numbers (must be 1-38) {pred}")
        if hit_count != len(hit_nums):
            errors.append(f"Row {i} ({sid}): hit_count={hit_count} != len(hit_numbers)={len(hit_nums)}")
        if pred_special is not None and row.get("replay_status") == "PREDICTED":
            if not (1 <= pred_special <= 8):
                errors.append(f"Row {i} ({sid}): predicted_special={pred_special} not in [1..8]")
        if special_hit not in (0, 1):
            errors.append(f"Row {i} ({sid}): special_hit={special_hit} must be 0 or 1")

    return {
        "total_rows": len(rows),
        "errors": errors,
        "valid": len(errors) == 0,
    }


# ─── Data leakage check ───────────────────────────────────────────────────────

def _check_no_future_leakage(rows: List[dict]) -> dict:
    """
    Verify prediction_cutoff_date < draw_date for all PREDICTED rows.
    Returns count of violations (should be 0).
    """
    violations = []
    for row in rows:
        if row.get("replay_status") != "PREDICTED":
            continue
        cutoff = row.get("prediction_cutoff_date")
        draw = row.get("draw_date")
        if cutoff and draw and cutoff >= draw:
            violations.append({
                "strategy_id": row["strategy_id"],
                "draw_date": draw,
                "cutoff_date": cutoff,
            })
    return {
        "violation_count": len(violations),
        "violations": violations[:5],
        "pass": len(violations) == 0,
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
            by_strategy[sid]["special_hit"] += int(row.get("special_hit", 0) or 0)
        else:
            by_strategy[sid]["error"] += 1

    stats = {}
    for sid in WAVE4_STRATEGY_IDS:
        counts = by_strategy.get(sid, {})
        predicted = counts.get("predicted", 0)
        errors = counts.get("error", 0)
        hit_3plus = sum(counts.get(f"hit_{h}", 0) for h in (3, 4, 5, 6))
        special_hits = counts.get("special_hit", 0)
        stats[sid] = {
            "predicted": predicted,
            "errors": errors,
            "total": predicted + errors,
            "hit_3plus": hit_3plus,
            "hit_3plus_rate": round(hit_3plus / predicted, 4) if predicted > 0 else 0.0,
            "special_hits": special_hits,
            "special_hit_rate": round(special_hits / predicted, 4) if predicted > 0 else 0.0,
            "hit_breakdown": {str(h): counts.get(f"hit_{h}", 0) for h in range(7)},
        }
    return stats


# ─── Main orchestrator ────────────────────────────────────────────────────────

def main() -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    now_str = started_at
    logger.info("=== P47 Wave 4 POWER_LOTTO Dry-Run + Temp Rehearsal ===")
    logger.info("Started: %s", started_at)
    logger.info("Expected rows: %d strategies × %d draws = %d",
                STRATEGIES_COUNT, WINDOW_PERIODS, EXPECTED_DRY_RUN_ROWS)

    # ── Pre-flight: Production row invariant ──────────────────────────────────
    logger.info("Pre-flight: checking production DB row count...")
    prod_rows_before = _assert_prod_rows_unchanged()
    logger.info("Production DB: %d rows (PASS)", prod_rows_before)

    # ── Load POWER_LOTTO draws (read-only) ────────────────────────────────────
    logger.info("Loading POWER_LOTTO draws from production DB (read-only)...")
    all_draws = _load_powerlotto_draws()
    total_draws = len(all_draws)
    logger.info("Loaded %d POWER_LOTTO draws", total_draws)

    if total_draws < WINDOW_PERIODS + 50:
        raise RuntimeError(
            f"Need at least {WINDOW_PERIODS + 50} POWER_LOTTO draws, got {total_draws}"
        )

    # ── Import Wave 4 adapters ────────────────────────────────────────────────
    from lottery_api.models.p47_wave4_powerlotto_adapters import WAVE4_ADAPTERS, generate_dryrun_rows
    logger.info("Wave 4 adapters loaded: %d", len(WAVE4_ADAPTERS))
    for a in WAVE4_ADAPTERS:
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

    # ── Data leakage check ───────────────────────────────────────────────────
    leakage_check = _check_no_future_leakage(raw_rows)
    logger.info("Data leakage check: pass=%s, violations=%d",
                leakage_check["pass"], leakage_check["violation_count"])

    # ── Convert to DB rows ────────────────────────────────────────────────────
    db_rows = [_to_db_row(r, now_str) for r in raw_rows]

    # ── Per-strategy row counts ───────────────────────────────────────────────
    per_strategy_counts: dict = defaultdict(int)
    for r in raw_rows:
        per_strategy_counts[r["strategy_id"]] += 1

    for sid in WAVE4_STRATEGY_IDS:
        logger.info("  %s: %d rows", sid, per_strategy_counts.get(sid, 0))

    # ── POWER_LOTTO format validation ─────────────────────────────────────────
    predicted_rows = [r for r in raw_rows if r.get("predicted_numbers") is not None]
    format_ok = all(
        len(r["predicted_numbers"]) == 6
        and len(set(r["predicted_numbers"])) == 6
        and all(1 <= n <= 38 for n in r["predicted_numbers"])
        for r in predicted_rows
    )
    special_format_ok = all(
        1 <= r["predicted_special"] <= 8
        for r in predicted_rows
        if r.get("predicted_special") is not None
    )

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
        r3 = _r3_rollback(conn)

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
        and leakage_check["pass"]
        and format_ok
        and special_format_ok
        and prod_rows_before == prod_rows_after
        and len(raw_rows) == EXPECTED_DRY_RUN_ROWS
    )

    # ── Rehearsal JSON ────────────────────────────────────────────────────────
    rehearsal = {
        "phase": "P47_WAVE4_POWERLOTTO_DRY_RUN",
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
        "leakage_check": leakage_check,
        "powerlotto_format_ok": format_ok,
        "special_format_ok": special_format_ok,
        "r1": r1,
        "r2": r2,
        "r3": r3,
        "per_strategy_counts": dict(per_strategy_counts),
        "hit_stats": hit_stats,
        "all_rehearsals_pass": all_rehearsals_pass,
    }

    # ── Dryrun JSON (main output) ─────────────────────────────────────────────
    dryrun = {
        "p47_version": "20260524",
        "wave": 4,
        "lottery_type": "POWER_LOTTO",
        "total_dryrun_rows": len(raw_rows),
        "strategies": [
            {
                "strategy_id": sid,
                "row_count": per_strategy_counts.get(sid, 0),
                "lifecycle": "DRY_RUN",
            }
            for sid in WAVE4_STRATEGY_IDS
        ],
        "temp_rehearsal": {
            "R1_insert_count": r1.get("r1_inserted", 0),
            "R2_duplicate_count": r2.get("r2_duplicate_inserted", 0),
            "R3_rollback": "PASS" if r3.get("r3_rollback_ok") else "FAIL",
        },
        "production_rows_before": prod_rows_before,
        "production_rows_after": prod_rows_after,
        "first_zone_format": "6 unique ints in [1,38]",
        "special_zone_format": "1 int in [1,8]",
        "special_hit_semantics": "predicted_special == actual_special",
        "hit_count_semantics": "first_zone_only",
        "schema_validation": {
            "valid": validation["valid"],
            "error_count": len(validation["errors"]),
        },
        "powerlotto_format_validation": {
            "numbers_per_prediction": 6,
            "first_zone_range": "1-38",
            "special_zone_range": "1-8",
            "no_duplicates": True,
            "format_ok": format_ok,
            "special_format_ok": special_format_ok,
        },
        "leakage_check": leakage_check,
        "all_rehearsals_pass": all_rehearsals_pass,
        "classification": "P47_POWERLOTTO_WAVE4_DRYRUN_REHEARSAL_READY" if all_rehearsals_pass
                          else "P47_POWERLOTTO_WAVE4_DRYRUN_REHEARSAL_FAIL",
        "lifecycle_semantics": {
            "all_rows_lifecycle": "DRY_RUN",
            "online_rows": 0,
            "retired_rows": 0,
            "note": "P47 is dry-run only. Production apply requires P48 authorization.",
        },
        "production_apply_readiness": {
            "ready": all_rehearsals_pass,
            "requires_p48_authorization": True,
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
    logger.info("=== P47 SUMMARY ===")
    logger.info("Prod rows before:        %d", prod_rows_before)
    logger.info("Prod rows after:         %d", prod_rows_after)
    logger.info("Prod rows unchanged:     %s", prod_rows_before == prod_rows_after)
    logger.info("Total dryrun rows:       %d (expected %d)", len(raw_rows), EXPECTED_DRY_RUN_ROWS)
    logger.info("Schema valid:            %s", validation["valid"])
    logger.info("Leakage check:           %s", leakage_check["pass"])
    logger.info("POWER_LOTTO format ok:   %s", format_ok)
    logger.info("Special format ok:       %s", special_format_ok)
    logger.info("R1 (apply):              %s", r1["r1_ok"])
    logger.info("R2 (idempotent):         %s", r2["r2_idempotent"])
    logger.info("R3 (rollback ok):        %s", r3["r3_rollback_ok"])
    logger.info("All rehearsals pass:     %s", all_rehearsals_pass)
    logger.info("Classification:          %s", dryrun["classification"])
    logger.info("")
    logger.info("Outputs:")
    logger.info("  %s", DRYRUN_OUTPUT)
    logger.info("  %s", REHEARSAL_OUTPUT)

    return dryrun


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get("all_rehearsals_pass") else 1)
