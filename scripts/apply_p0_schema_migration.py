#!/usr/bin/env python3
"""
apply_p0_schema_migration.py
============================
P0 Schema Stabilization — Idempotent Migration Wrapper

Applies (or dry-runs) the governance column additions defined in
lottery_api/migrations/0001_p0_schema_stabilization.sql.

Usage:
    # Dry-run (default) — shows what would change, does not write:
    python3 scripts/apply_p0_schema_migration.py --dry-run

    # Apply — backs up DB first, then applies missing columns:
    python3 scripts/apply_p0_schema_migration.py --apply

    # Output JSON log:
    python3 scripts/apply_p0_schema_migration.py --apply --json-out /tmp/log.json

Safety guarantees:
  - All ALTER TABLE operations are idempotent (skipped if column already exists).
  - --apply creates a timestamped backup before any write.
  - No replay rows are written; no strategy code is executed.
  - Rollback: restore backup from lottery_api/data/backups/lottery_v2_pre_p0_<ts>.db

Down-migration:
  SQLite does not support DROP COLUMN (before 3.35.0).
  To rollback: cp lottery_api/data/backups/lottery_v2_pre_p0_<ts>.db lottery_api/data/lottery_v2.db
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_DIR = PROJECT_ROOT / "lottery_api" / "data" / "backups"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "replay"

# ── Target schema for strategy_prediction_replays ────────────────────────────
# Each entry: (column_name, type, default)
SPR_GOVERNANCE_COLUMNS = [
    ("truth_level",        "TEXT",    None),
    ("source",             "TEXT",    None),
    ("provenance_hash",    "TEXT",    None),
    ("provenance_source",  "TEXT",    None),
    ("controlled_apply_id","TEXT",    None),
    ("dry_run_only",       "INTEGER", "0"),
]

# Governance indexes to ensure exist
GOVERNANCE_INDEXES = [
    ("idx_spr_truth_level",    "strategy_prediction_replays", "truth_level"),
    ("idx_spr_controlled_apply","strategy_prediction_replays","controlled_apply_id"),
    ("idx_spr_dry_run",        "strategy_prediction_replays", "dry_run_only"),
]


def _get_existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return the set of column names currently in the table."""
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def _get_existing_indexes(conn: sqlite3.Connection) -> set[str]:
    """Return the set of index names currently in the DB."""
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    return {row[0] for row in cur.fetchall()}


def run_migration(dry_run: bool = True) -> dict[str, Any]:
    """
    Execute the P0 schema migration.

    Returns a log dict with actions taken / would-take.
    """
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    log: dict[str, Any] = {
        "migration_id": "0001_p0_schema_stabilization",
        "executed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "dry_run": dry_run,
        "db_path": str(DB_PATH),
        "backup_path": None,
        "columns_checked": [],
        "columns_added": [],
        "columns_skipped": [],
        "indexes_added": [],
        "indexes_skipped": [],
        "errors": [],
        "status": "PENDING",
    }

    if not DB_PATH.exists():
        log["status"] = "ERROR_DB_NOT_FOUND"
        log["errors"].append(f"DB not found: {DB_PATH}")
        return log

    # ── Backup before write ───────────────────────────────────────────────────
    if not dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup_path = BACKUP_DIR / f"lottery_v2_pre_p0_{ts}.db"
        shutil.copy2(str(DB_PATH), str(backup_path))
        log["backup_path"] = str(backup_path)
        print(f"[backup] {backup_path}")

    conn = sqlite3.connect(str(DB_PATH))
    try:
        existing_cols = _get_existing_columns(conn, "strategy_prediction_replays")
        existing_idx  = _get_existing_indexes(conn)

        # ── Column additions ─────────────────────────────────────────────────
        for col_name, col_type, col_default in SPR_GOVERNANCE_COLUMNS:
            log["columns_checked"].append(col_name)
            if col_name in existing_cols:
                log["columns_skipped"].append(col_name)
                print(f"[skip]  column already exists: strategy_prediction_replays.{col_name}")
            else:
                default_clause = f" DEFAULT {col_default}" if col_default is not None else ""
                ddl = f"ALTER TABLE strategy_prediction_replays ADD COLUMN {col_name} {col_type}{default_clause}"
                if dry_run:
                    print(f"[dry]   would execute: {ddl}")
                    log["columns_added"].append({"column": col_name, "ddl": ddl, "dry_run": True})
                else:
                    conn.execute(ddl)
                    conn.commit()
                    print(f"[apply] added column: strategy_prediction_replays.{col_name}")
                    log["columns_added"].append({"column": col_name, "ddl": ddl, "dry_run": False})

        # ── Index additions ──────────────────────────────────────────────────
        for idx_name, tbl_name, col_name in GOVERNANCE_INDEXES:
            if idx_name in existing_idx:
                log["indexes_skipped"].append(idx_name)
                print(f"[skip]  index already exists: {idx_name}")
            else:
                ddl = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl_name}({col_name})"
                if dry_run:
                    print(f"[dry]   would execute: {ddl}")
                    log["indexes_added"].append({"index": idx_name, "dry_run": True})
                else:
                    conn.execute(ddl)
                    conn.commit()
                    print(f"[apply] created index: {idx_name}")
                    log["indexes_added"].append({"index": idx_name, "dry_run": False})

        # ── Post-apply verification ──────────────────────────────────────────
        final_cols = _get_existing_columns(conn, "strategy_prediction_replays")
        required = {c[0] for c in SPR_GOVERNANCE_COLUMNS}
        missing = required - final_cols if not dry_run else set()

        if missing:
            log["status"] = "ERROR_COLUMNS_STILL_MISSING"
            log["errors"].append(f"Still missing after apply: {missing}")
        elif dry_run:
            needs_add = required - existing_cols
            log["status"] = "DRY_RUN_COMPLETE"
            log["dry_run_summary"] = {
                "columns_to_add": sorted(needs_add),
                "columns_already_present": sorted(required - needs_add),
            }
        else:
            log["status"] = "MIGRATION_APPLIED_OK"

    except Exception as exc:
        log["status"] = "ERROR_EXCEPTION"
        log["errors"].append(str(exc))
        print(f"[error] {exc}", file=sys.stderr)
        conn.rollback()
    finally:
        conn.close()

    return log


def main():
    parser = argparse.ArgumentParser(
        description="P0 schema stabilization migration (idempotent)"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True,
                       help="Show what would change (default)")
    group.add_argument("--apply", action="store_true",
                       help="Apply migration (backs up DB first)")
    parser.add_argument("--json-out", help="Write JSON log to this path")
    args = parser.parse_args()

    dry_run = not args.apply

    print("=" * 60)
    print(f"P0 Schema Migration — {'DRY RUN' if dry_run else 'APPLY'}")
    print(f"DB: {DB_PATH}")
    print("=" * 60)

    log = run_migration(dry_run=dry_run)

    print("\n--- Summary ---")
    print(f"Status:           {log['status']}")
    print(f"Columns checked:  {len(log['columns_checked'])}")
    print(f"Columns added:    {len(log['columns_added'])}")
    print(f"Columns skipped:  {len(log['columns_skipped'])}")
    print(f"Indexes added:    {len(log['indexes_added'])}")
    print(f"Indexes skipped:  {len(log['indexes_skipped'])}")
    if log.get("backup_path"):
        print(f"Backup:           {log['backup_path']}")
    if log["errors"]:
        print(f"Errors:           {log['errors']}")

    # Write migration log to outputs/replay/
    log_date = datetime.datetime.utcnow().strftime("%Y%m%d")
    default_out = OUTPUT_DIR / f"p0_migration_log_{log_date}.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(default_out), "w") as f:
        json.dump(log, f, indent=2)
    print(f"\nLog written: {default_out}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(log, f, indent=2)
        print(f"Log also written: {args.json_out}")

    sys.exit(0 if log["status"] in ("MIGRATION_APPLIED_OK", "DRY_RUN_COMPLETE") else 1)


if __name__ == "__main__":
    main()
