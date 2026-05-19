"""
tests/test_p2_catalog_apply_dry_run.py
========================================
Verify that the P2 apply script in dry-run mode does NOT write to DB.
"""

import pathlib
import shutil
import sqlite3
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

PROTECTED_TABLES = [
    "strategy_prediction_replays",
    "prediction_items",
    "prediction_runs",
]


def _row_count(db_path: pathlib.Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return -1
    finally:
        conn.close()


def _catalog_exists(db_path: pathlib.Path) -> bool:
    conn = sqlite3.connect(str(db_path))
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='strategy_catalog'"
        ).fetchone()[0]
        return n > 0
    finally:
        conn.close()


class TestDryRunDoesNotWriteDB:
    def test_dry_run_does_not_create_catalog_table(self):
        """Dry-run must NOT create strategy_catalog table in the live DB."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply

        before = _catalog_exists(DB_PATH)
        entries = _build_catalog_entries()
        run_apply(dry_run=True, entries=entries)
        after = _catalog_exists(DB_PATH)

        # If table didn't exist before, it should still not exist after dry-run
        if not before:
            assert not after, "Dry-run created strategy_catalog table in live DB"

    def test_dry_run_does_not_change_replay_row_count(self):
        """strategy_prediction_replays count must be 460 before and after dry-run."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply

        before = _row_count(DB_PATH, "strategy_prediction_replays")
        entries = _build_catalog_entries()
        run_apply(dry_run=True, entries=entries)
        after = _row_count(DB_PATH, "strategy_prediction_replays")

        assert before == after == 460, (
            f"Replay row count changed: {before} → {after}"
        )

    def test_dry_run_result_has_dry_run_true(self):
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply

        entries = _build_catalog_entries()
        result = run_apply(dry_run=True, entries=entries)
        assert result["dry_run"] is True

    def test_dry_run_result_has_no_backup(self):
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply

        entries = _build_catalog_entries()
        result = run_apply(dry_run=True, entries=entries)
        assert result["backup_path"] is None

    def test_dry_run_on_copy_leaves_no_catalog_rows(self):
        """Apply dry-run to a temp DB copy — no catalog rows should appear."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = pathlib.Path(tmpdir) / "test.db"
            shutil.copy2(str(DB_PATH), str(tmp_db))

            # Monkey-patch DB_PATH for this test
            import scripts.p2_catalog_apply as p2mod
            original = p2mod.DB_PATH
            p2mod.DB_PATH = tmp_db
            try:
                entries = _build_catalog_entries()
                run_apply(dry_run=True, entries=entries)
                assert not _catalog_exists(tmp_db), (
                    "Dry-run created strategy_catalog in temp DB"
                )
            finally:
                p2mod.DB_PATH = original


class TestApplyOnCopy:
    def test_apply_on_copy_creates_catalog_table(self):
        """--apply on a temp copy DOES create the table."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = pathlib.Path(tmpdir) / "test.db"
            shutil.copy2(str(DB_PATH), str(tmp_db))

            import scripts.p2_catalog_apply as p2mod
            original_db     = p2mod.DB_PATH
            original_backup = p2mod.BACKUP_DIR
            p2mod.DB_PATH   = tmp_db
            p2mod.BACKUP_DIR = pathlib.Path(tmpdir) / "backups"
            try:
                entries = _build_catalog_entries()
                result = run_apply(dry_run=False, entries=entries)
                assert _catalog_exists(tmp_db), "Apply did not create strategy_catalog"
                assert result["final_catalog_row_count"] == 59, (
                    f"Expected 59 catalog rows, got {result['final_catalog_row_count']}"
                )
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup

    def test_apply_on_copy_does_not_touch_replay_rows(self):
        """After apply on temp copy, strategy_prediction_replays must still have 460 rows."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = pathlib.Path(tmpdir) / "test.db"
            shutil.copy2(str(DB_PATH), str(tmp_db))

            import scripts.p2_catalog_apply as p2mod
            original_db     = p2mod.DB_PATH
            original_backup = p2mod.BACKUP_DIR
            p2mod.DB_PATH   = tmp_db
            p2mod.BACKUP_DIR = pathlib.Path(tmpdir) / "backups"
            try:
                entries = _build_catalog_entries()
                result = run_apply(dry_run=False, entries=entries)
                assert result["violations"] == [], (
                    f"Protected table violations: {result['violations']}"
                )
                after_count = _row_count(tmp_db, "strategy_prediction_replays")
                assert after_count == 460
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup

    def test_apply_on_copy_creates_backup(self):
        """--apply must create a backup file before writing."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_db = pathlib.Path(tmpdir) / "test.db"
            shutil.copy2(str(DB_PATH), str(tmp_db))
            backup_dir = pathlib.Path(tmpdir) / "backups"

            import scripts.p2_catalog_apply as p2mod
            original_db     = p2mod.DB_PATH
            original_backup = p2mod.BACKUP_DIR
            p2mod.DB_PATH   = tmp_db
            p2mod.BACKUP_DIR = backup_dir
            try:
                entries = _build_catalog_entries()
                result = run_apply(dry_run=False, entries=entries)
                assert result["backup_path"] is not None
                assert pathlib.Path(result["backup_path"]).exists()
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup
