#!/usr/bin/env python3
"""
apply_p0_schema_migration.py
============================
Idempotent apply script for migration 0001_p0_schema_stabilization.sql.

Safety guarantees:
  - Dry-run by default; pass --apply to write to DB
  - Auto-backup DB before any write (backup path printed)
  - Idempotent: re-running with --apply on an already-migrated DB is safe
  - Never deletes existing rows
  - Never modifies existing column values

Usage:
  python3 scripts/apply_p0_schema_migration.py            # dry-run
  python3 scripts/apply_p0_schema_migration.py --apply    # write to DB
  python3 scripts/apply_p0_schema_migration.py --apply --backup-dir /path/to/backups
"""

import argparse
import datetime
import pathlib
import shutil
import sqlite3
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
MIGRATION = REPO_ROOT / "lottery_api" / "migrations" / "0001_p0_schema_stabilization.sql"
DEFAULT_BACKUP_DIR = REPO_ROOT / "backups"

# Columns to add: (name, type, default_expr)
NEW_COLUMNS = [
    ("truth_level",       "TEXT",    "NULL"),
    ("controlled_apply_id", "TEXT",  "NULL"),
    ("source",            "TEXT",    "NULL"),
    ("provenance_hash",   "TEXT",    "NULL"),
    ("provenance_source", "TEXT",    "NULL"),
    ("dry_run",           "INTEGER", "0"),
]

# Indexes to create: (index_name, table, columns)
NEW_INDEXES = [
    ("idx_spr_controlled_apply_id", "strategy_prediction_replays", "controlled_apply_id"),
    ("idx_spr_truth_level",         "strategy_prediction_replays", "truth_level"),
]


def get_existing_columns(conn: sqlite3.Connection, table: str) -> set:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def get_existing_indexes(conn: sqlite3.Connection) -> set:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    return {r[0] for r in rows}


def compute_diff(conn: sqlite3.Connection) -> dict:
    """Compute what changes need to be applied (read-only)."""
    existing_cols  = get_existing_columns(conn, "strategy_prediction_replays")
    existing_idxs  = get_existing_indexes(conn)

    cols_to_add  = [(n, t, d) for n, t, d in NEW_COLUMNS   if n not in existing_cols]
    idxs_to_add  = [(n, tbl, c) for n, tbl, c in NEW_INDEXES if n not in existing_idxs]

    row_count = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    return {
        "existing_columns":  sorted(existing_cols),
        "columns_to_add":    cols_to_add,
        "indexes_to_add":    idxs_to_add,
        "existing_row_count": row_count,
        "already_migrated":  len(cols_to_add) == 0 and len(idxs_to_add) == 0,
    }


def apply_migration(conn: sqlite3.Connection, diff: dict, dry_run: bool) -> list:
    """Apply migration steps. Returns list of SQL statements executed."""
    executed = []

    for col_name, col_type, col_default in diff["columns_to_add"]:
        stmt = (
            f"ALTER TABLE strategy_prediction_replays "
            f"ADD COLUMN {col_name} {col_type} DEFAULT {col_default}"
        )
        if not dry_run:
            conn.execute(stmt)
        executed.append(stmt)

    for idx_name, tbl, col in diff["indexes_to_add"]:
        stmt = f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl}({col})"
        if not dry_run:
            conn.execute(stmt)
        executed.append(stmt)

    if not dry_run and executed:
        conn.commit()

    return executed


def backup_db(db_path: pathlib.Path, backup_dir: pathlib.Path) -> pathlib.Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"lottery_v2_pre_p0_{ts}.db"
    shutil.copy2(str(db_path), str(dest))
    return dest


def main():
    parser = argparse.ArgumentParser(description="Apply P0 schema migration")
    parser.add_argument("--apply",      action="store_true", help="Write to DB (default: dry-run)")
    parser.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR), help="Backup directory")
    args = parser.parse_args()

    dry_run = not args.apply
    backup_dir = pathlib.Path(args.backup_dir)

    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))

    try:
        diff = compute_diff(conn)

        print("=" * 60)
        print(f"Migration: 0001_p0_schema_stabilization")
        print(f"Mode:      {'DRY-RUN (pass --apply to write)' if dry_run else 'APPLY'}")
        print(f"DB:        {DB_PATH}")
        print(f"Rows:      {diff['existing_row_count']}")
        print("=" * 60)

        if diff["already_migrated"]:
            print("ALREADY MIGRATED — no changes needed.")
            conn.close()
            return

        print(f"\nColumns to add ({len(diff['columns_to_add'])}):")
        for n, t, d in diff["columns_to_add"]:
            print(f"  + {n}  {t}  DEFAULT {d}")

        print(f"\nIndexes to add ({len(diff['indexes_to_add'])}):")
        for n, tbl, c in diff["indexes_to_add"]:
            print(f"  + {n} ON {tbl}({c})")

        if not dry_run:
            print(f"\nBacking up DB ...")
            backup_path = backup_db(DB_PATH, backup_dir)
            print(f"  Backup: {backup_path}")

        executed = apply_migration(conn, diff, dry_run)

        print(f"\nStatements {'(dry-run, not executed)' if dry_run else 'executed'}:")
        for s in executed:
            print(f"  {s}")

        if not dry_run:
            # Verify
            diff_after = compute_diff(conn)
            remaining = len(diff_after["columns_to_add"]) + len(diff_after["indexes_to_add"])
            if remaining == 0:
                print(f"\nMIGRATION APPLIED SUCCESSFULLY")
                print(f"  Rows unchanged: {diff_after['existing_row_count']}")
            else:
                print(f"\nERROR: {remaining} items still pending after apply", file=sys.stderr)
                sys.exit(1)
        else:
            print(f"\nDRY-RUN COMPLETE — run with --apply to write changes")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
