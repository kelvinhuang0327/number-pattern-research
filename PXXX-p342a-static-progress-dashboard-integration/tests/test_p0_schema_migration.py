"""
tests/test_p0_schema_migration.py
===================================
Tests for the P0 schema migration idempotency, backup, and column presence.
"""

import pathlib
import shutil
import sqlite3
import tempfile

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

REQUIRED_COLUMNS = {
    "truth_level",
    "controlled_apply_id",
    "source",
    "provenance_hash",
    "provenance_source",
    "dry_run",
}

REQUIRED_INDEXES = {
    "idx_spr_controlled_apply_id",
    "idx_spr_truth_level",
}


def _get_columns(db_path: pathlib.Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    conn.close()
    return {r[1] for r in rows}


def _get_indexes(db_path: pathlib.Path) -> set[str]:
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    conn.close()
    return {r[0] for r in rows}


class TestP0SchemaMigration:
    """Validate that the P0 migration was applied correctly to the main repo DB."""

    def test_required_columns_present(self):
        """All P0 columns must exist in strategy_prediction_replays."""
        existing = _get_columns(DB_PATH)
        missing = REQUIRED_COLUMNS - existing
        assert not missing, f"Missing columns after P0 migration: {missing}"

    def test_required_indexes_present(self):
        """P0 indexes must exist."""
        existing = _get_indexes(DB_PATH)
        missing = REQUIRED_INDEXES - existing
        assert not missing, f"Missing indexes after P0 migration: {missing}"

    def test_row_count_unchanged(self):
        """460 legacy rows must still be present and unchanged."""
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        conn.close()
        assert count == 460, f"Expected 460 rows, got {count}"

    def test_all_new_columns_are_null_or_zero(self):
        """New columns should be NULL (or 0 for dry_run) for all legacy rows."""
        conn = sqlite3.connect(str(DB_PATH))
        non_null_tl = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE truth_level IS NOT NULL"
        ).fetchone()[0]
        non_null_cai = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id IS NOT NULL"
        ).fetchone()[0]
        non_zero_dr = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE dry_run != 0"
        ).fetchone()[0]
        conn.close()
        assert non_null_tl == 0, f"Expected all truth_level NULL, got {non_null_tl} non-NULL"
        assert non_null_cai == 0, f"Expected all controlled_apply_id NULL, got {non_null_cai} non-NULL"
        assert non_zero_dr == 0, f"Expected all dry_run=0, got {non_zero_dr} non-zero"

    def test_migration_idempotent_on_copy(self):
        """Applying migration twice to a fresh copy must not error or change row count."""
        import sys
        sys.path.insert(0, str(REPO_ROOT))
        from scripts.apply_p0_schema_migration import compute_diff, apply_migration

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = pathlib.Path(tmpdir) / "test.db"
            shutil.copy2(str(DB_PATH), str(tmp_db))

            conn = sqlite3.connect(str(tmp_db))
            diff1 = compute_diff(conn)
            # Already migrated — should report already_migrated=True
            assert diff1["already_migrated"], (
                f"Expected already_migrated=True, diff: {diff1}"
            )
            # Applying again should execute 0 statements
            stmts = apply_migration(conn, diff1, dry_run=False)
            assert stmts == [], f"Expected 0 statements on re-apply, got: {stmts}"
            conn.close()

    def test_backup_created(self):
        """Backup directory must exist and contain at least one backup file."""
        backup_dir = REPO_ROOT / "backups"
        assert backup_dir.exists(), "backups/ directory does not exist"
        backups = list(backup_dir.glob("lottery_v2_pre_p0_*.db"))
        assert backups, "No P0 backup file found in backups/"
