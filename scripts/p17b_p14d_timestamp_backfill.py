#!/usr/bin/env python3
"""
P17B — P14D Timestamp Metadata Backfill.

Backfills prediction_cutoff_date and prediction_generated_at for the 1500
P14D ts3_regime_3bet BIG_LOTTO rows that were applied before these columns
existed (P16A).

SEMANTICS:
  prediction_cutoff_date   = draws.date WHERE draw = history_cutoff_draw
                             → the date of the last historical draw used
                             → accurately reflects what data the prediction saw
  prediction_generated_at  = backfill execution timestamp (P17B run time)
                             → NOT the original prediction time
                             → documented as P17B_METADATA_BACKFILL_TIME

This script only performs UPDATE operations on existing rows.
It NEVER inserts, deletes, or modifies prediction/actual/hit columns.

Modes:
  --apply      UPDATE NULL timestamp rows → fills 1500 rows on first run, 0 on rerun
  --rollback   Reset timestamps back to NULL for target rows
  --dry-run    Compute what would be updated; no DB write
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT  = Path(__file__).resolve().parents[1]
_PROD_DB    = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
_OUT_DIR    = _REPO_ROOT / "outputs" / "replay"

PHASE                = "P17B_P14D_TIMESTAMP_BACKFILL"
TARGET_APPLY_ID      = "P14D_BIGLOTTO_TS3_1500_PROD_20260520"
BACKFILL_APPLY_ID    = "P17B_P14D_TIMESTAMP_BACKFILL_20260520"
GEN_AT_SEMANTICS     = "P17B_METADATA_BACKFILL_TIME_NOT_ORIGINAL_PREDICTION_TIME"
EXPECTED_TARGET_ROWS = 1500


def _row_count(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


def _target_null_count(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id = ?
                 AND (prediction_cutoff_date IS NULL OR prediction_generated_at IS NULL)""",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()


def _target_total_count(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id = ?",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()


def _cutoff_join_count(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            """SELECT COUNT(*)
               FROM strategy_prediction_replays r
               JOIN draws d
                 ON d.lottery_type = r.lottery_type
                AND d.draw          = r.history_cutoff_draw
               WHERE r.controlled_apply_id = ?""",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()


def _assert_not_prod(db: Path, allow_production: bool) -> None:
    if db.resolve() == _PROD_DB.resolve() and not allow_production:
        raise RuntimeError(
            f"SAFETY STOP: refusing to write to production DB without --allow-production. "
            f"DB={db}"
        )


def _cutoff_violations_after_update(db: Path) -> int:
    """Count rows where prediction_cutoff_date > target_date (post-update check)."""
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE controlled_apply_id = ?
                 AND prediction_cutoff_date IS NOT NULL
                 AND prediction_cutoff_date > target_date""",
            (TARGET_APPLY_ID,),
        ).fetchone()[0]
    finally:
        conn.close()


# ── apply ─────────────────────────────────────────────────────────────────────

def apply_backfill(
    db: Path,
    expected_rows: int,
    allow_production: bool,
    *,
    json_out: Path | None = None,
) -> dict:
    _assert_not_prod(db, allow_production)

    rows_before = _row_count(db)
    if rows_before != expected_rows:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows} rows before update, got {rows_before}"
        )

    target_rows   = _target_total_count(db)
    eligible_rows = _target_null_count(db)
    cutoff_join   = _cutoff_join_count(db)

    if cutoff_join < target_rows:
        raise RuntimeError(
            f"SAFETY STOP: only {cutoff_join}/{target_rows} P14D rows "
            f"can be resolved via history_cutoff_draw JOIN draws"
        )

    backfill_ts = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(str(db))
    try:
        with conn:
            cur = conn.execute(
                """
                UPDATE strategy_prediction_replays
                SET prediction_cutoff_date  = (
                        SELECT d.date FROM draws d
                        WHERE d.lottery_type = strategy_prediction_replays.lottery_type
                          AND d.draw         = strategy_prediction_replays.history_cutoff_draw
                        LIMIT 1
                    ),
                    prediction_generated_at = ?
                WHERE controlled_apply_id = ?
                  AND (prediction_cutoff_date IS NULL OR prediction_generated_at IS NULL)
                """,
                (backfill_ts, TARGET_APPLY_ID),
            )
            updated = cur.rowcount
    finally:
        conn.close()

    rows_after     = _row_count(db)
    violations     = _cutoff_violations_after_update(db)

    result = {
        "phase":               PHASE,
        "mode":                "apply",
        "generated_at":        backfill_ts,
        "production_apply":    allow_production and (db.resolve() == _PROD_DB.resolve()),
        "target_apply_id":     TARGET_APPLY_ID,
        "controlled_apply_id": BACKFILL_APPLY_ID,
        "target_rows":         target_rows,
        "eligible_rows":       eligible_rows,
        "cutoff_join_count":   cutoff_join,
        "updated_count":       updated,
        "inserted_count":      0,
        "deleted_count":       0,
        "rows_before":         rows_before,
        "rows_after":          rows_after,
        "cutoff_violations":   violations,
        "prediction_generated_at_semantics": GEN_AT_SEMANTICS,
        "production_rows_after": rows_after,
    }
    if json_out:
        _write(result, json_out)
    return result


# ── rollback ──────────────────────────────────────────────────────────────────

def rollback_backfill(
    db: Path,
    expected_rows: int,
    allow_production: bool,
    *,
    json_out: Path | None = None,
) -> dict:
    _assert_not_prod(db, allow_production)

    rows_before = _row_count(db)
    if rows_before != expected_rows:
        raise RuntimeError(
            f"SAFETY STOP: expected {expected_rows} rows before rollback, got {rows_before}"
        )

    conn = sqlite3.connect(str(db))
    try:
        with conn:
            cur = conn.execute(
                """
                UPDATE strategy_prediction_replays
                SET prediction_cutoff_date  = NULL,
                    prediction_generated_at = NULL
                WHERE controlled_apply_id = ?
                  AND prediction_cutoff_date IS NOT NULL
                """,
                (TARGET_APPLY_ID,),
            )
            rolled_back = cur.rowcount
    finally:
        conn.close()

    rows_after = _row_count(db)
    result = {
        "phase":                    PHASE,
        "mode":                     "rollback",
        "target_apply_id":          TARGET_APPLY_ID,
        "controlled_apply_id":      BACKFILL_APPLY_ID,
        "rows_before":              rows_before,
        "rollback_updated_count":   rolled_back,
        "rows_after_rollback":      rows_after,
        "production_rows_after":    rows_after,
    }
    if json_out:
        _write(result, json_out)
    return result


# ── dry-run ───────────────────────────────────────────────────────────────────

def dry_run(db: Path) -> dict:
    target   = _target_total_count(db)
    eligible = _target_null_count(db)
    joins    = _cutoff_join_count(db)
    return {
        "phase":           PHASE,
        "mode":            "dry-run",
        "target_rows":     target,
        "eligible_rows":   eligible,
        "cutoff_join_count": joins,
        "would_update":    eligible,
        "would_insert":    0,
        "db_writes":       0,
    }


# ── utilities ─────────────────────────────────────────────────────────────────

def _write(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[P17B] written → {path}")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="P17B P14D timestamp metadata backfill")
    parser.add_argument("--db",                default=str(_PROD_DB))
    parser.add_argument("--backup",            default=None)
    parser.add_argument("--json-out",          default=None)
    parser.add_argument("--expected-rows",     type=int, default=4960)
    parser.add_argument("--controlled-apply-id", default=BACKFILL_APPLY_ID)
    parser.add_argument("--target-apply-id",   default=TARGET_APPLY_ID)
    parser.add_argument("--allow-production",  action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply",    action="store_true")
    mode.add_argument("--rollback", action="store_true")
    mode.add_argument("--dry-run",  action="store_true")
    args = parser.parse_args()

    db       = Path(args.db)
    json_out = Path(args.json_out) if args.json_out else None

    if args.dry_run:
        result = dry_run(db)
        print(f"[P17B] dry-run: target={result['target_rows']} eligible={result['eligible_rows']} joins={result['cutoff_join_count']}")
        if json_out:
            _write(result, json_out)
        return

    if args.apply:
        result = apply_backfill(db, args.expected_rows, args.allow_production, json_out=json_out)
        print(f"[P17B] apply: updated={result['updated_count']} violations={result['cutoff_violations']} rows={result['rows_after']}")

    elif args.rollback:
        result = rollback_backfill(db, args.expected_rows, args.allow_production, json_out=json_out)
        print(f"[P17B] rollback: restored_to_null={result['rollback_updated_count']} rows={result['rows_after_rollback']}")


if __name__ == "__main__":
    main()
