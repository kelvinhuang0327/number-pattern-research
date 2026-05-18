"""
test_p0_schema_migration_idempotent.py
=======================================
P0 Schema Stabilization — Idempotency Tests

Verifies:
1. Running migration twice does not raise errors.
2. After migration, all P0 governance columns are present.
3. Migration log status is correct.

Safety: Uses the live DB in dry-run mode; tests that would write use a temp copy.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# P0 governance columns that MUST exist post-migration
P0_GOVERNANCE_COLUMNS = {
    "truth_level",
    "source",
    "provenance_hash",
    "provenance_source",
    "controlled_apply_id",
    "dry_run_only",
}

# P0 governance indexes that MUST exist post-migration
P0_GOVERNANCE_INDEXES = {
    "idx_spr_truth_level",
    "idx_spr_controlled_apply",
    "idx_spr_dry_run",
}


def _get_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def _get_indexes(conn: sqlite3.Connection) -> set[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    return {row[0] for row in cur.fetchall()}


class TestMigrationIdempotent:
    """Migration can be run multiple times without error or data loss."""

    def test_live_db_has_governance_columns(self):
        """Live DB must already have all P0 governance columns."""
        assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
        conn = sqlite3.connect(str(DB_PATH))
        try:
            actual = _get_columns(conn, "strategy_prediction_replays")
            missing = P0_GOVERNANCE_COLUMNS - actual
            assert not missing, f"Missing governance columns: {missing}"
        finally:
            conn.close()

    def test_live_db_has_governance_indexes(self):
        """Live DB must have P0 governance indexes after migration --apply."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            actual = _get_indexes(conn)
            missing = P0_GOVERNANCE_INDEXES - actual
            assert not missing, f"Missing governance indexes: {missing}"
        finally:
            conn.close()

    def test_migration_dry_run_is_idempotent(self):
        """Dry-run migration twice does not error."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.apply_p0_schema_migration import run_migration

        log1 = run_migration(dry_run=True)
        log2 = run_migration(dry_run=True)

        assert log1["status"] == "DRY_RUN_COMPLETE", f"First dry-run failed: {log1}"
        assert log2["status"] == "DRY_RUN_COMPLETE", f"Second dry-run failed: {log2}"

    def test_migration_apply_on_temp_db_is_idempotent(self):
        """Apply migration twice on a temp DB copy — no errors, no duplicate columns."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.apply_p0_schema_migration import run_migration, DB_PATH as ORIG_DB

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = Path(tmpdir) / "lottery_v2_test.db"
            shutil.copy2(str(DB_PATH), str(tmp_db))

            # Monkey-patch DB_PATH in the module
            import scripts.apply_p0_schema_migration as mod
            original_db = mod.DB_PATH
            try:
                mod.DB_PATH = tmp_db

                log1 = run_migration(dry_run=False)
                assert log1["status"] == "MIGRATION_APPLIED_OK", f"First apply failed: {log1}"

                log2 = run_migration(dry_run=False)
                assert log2["status"] == "MIGRATION_APPLIED_OK", f"Second apply failed: {log2}"

                # Verify columns after two runs
                conn = sqlite3.connect(str(tmp_db))
                try:
                    cols = _get_columns(conn, "strategy_prediction_replays")
                    missing = P0_GOVERNANCE_COLUMNS - cols
                    assert not missing, f"Still missing after double-apply: {missing}"

                    # Verify no duplicate columns (SQLite PRAGMA doesn't produce duplicates
                    # but sanity check via count)
                    cur = conn.execute("PRAGMA table_info(strategy_prediction_replays)")
                    all_cols = [row[1] for row in cur.fetchall()]
                    assert len(all_cols) == len(set(all_cols)), "Duplicate columns detected!"
                finally:
                    conn.close()

            finally:
                mod.DB_PATH = original_db

    def test_migration_log_structure(self):
        """Migration log has expected fields."""
        import sys
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.apply_p0_schema_migration import run_migration

        log = run_migration(dry_run=True)

        required_fields = {
            "migration_id",
            "executed_at",
            "dry_run",
            "db_path",
            "columns_checked",
            "columns_added",
            "columns_skipped",
            "indexes_added",
            "indexes_skipped",
            "errors",
            "status",
        }
        missing = required_fields - set(log.keys())
        assert not missing, f"Log missing fields: {missing}"
        assert log["migration_id"] == "0001_p0_schema_stabilization"
        assert log["dry_run"] is True
        assert isinstance(log["errors"], list)

    def test_all_governance_columns_present_after_migration(self):
        """Every P0 governance column is present post-migration in live DB."""
        conn = sqlite3.connect(str(DB_PATH))
        try:
            actual = _get_columns(conn, "strategy_prediction_replays")
            for col in P0_GOVERNANCE_COLUMNS:
                assert col in actual, f"Governance column missing: {col}"
        finally:
            conn.close()
