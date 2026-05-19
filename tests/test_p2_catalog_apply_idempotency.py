"""
tests/test_p2_catalog_apply_idempotency.py
============================================
Verify idempotency: running apply twice produces the same catalog,
does not duplicate rows, and does not change protected tables.
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


def _get_catalog_rows(db_path: pathlib.Path) -> list[dict]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        exists = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='strategy_catalog'"
        ).fetchone()[0]
        if not exists:
            return []
        rows = conn.execute("SELECT * FROM strategy_catalog ORDER BY strategy_id, lottery_type").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


class TestIdempotency:
    def test_double_apply_same_row_count(self):
        """Running apply twice must yield the same number of catalog rows."""
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

                # First apply
                r1 = run_apply(dry_run=False, entries=entries)
                count1 = r1["final_catalog_row_count"]

                # Second apply
                r2 = run_apply(dry_run=False, entries=entries)
                count2 = r2["final_catalog_row_count"]

                assert count1 == count2 == 59, (
                    f"Row counts differ after double apply: {count1} vs {count2}"
                )
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup

    def test_double_apply_all_update_second_time(self):
        """On second apply all 59 entries should be UPDATE (not INSERT)."""
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
                run_apply(dry_run=False, entries=entries)  # first
                r2 = run_apply(dry_run=False, entries=entries)   # second

                assert r2["inserted"] == 0, f"Second apply should not INSERT; got {r2['inserted']}"
                assert r2["updated"] == 59, f"Second apply should UPDATE all 59; got {r2['updated']}"
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup

    def test_idempotency_no_replay_row_change(self):
        """strategy_prediction_replays must have 460 rows after two applies."""
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
                run_apply(dry_run=False, entries=entries)
                run_apply(dry_run=False, entries=entries)

                conn = sqlite3.connect(str(tmp_db))
                count = conn.execute(
                    "SELECT COUNT(*) FROM strategy_prediction_replays"
                ).fetchone()[0]
                conn.close()
                assert count == 460
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup


class TestRollback:
    def test_rollback_removes_catalog_table(self):
        """Rollback --apply should drop strategy_catalog."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply, run_rollback

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
                run_apply(dry_run=False, entries=entries)

                # Verify table exists
                conn = sqlite3.connect(str(tmp_db))
                exists_before = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='strategy_catalog'"
                ).fetchone()[0]
                conn.close()
                assert exists_before == 1

                # Rollback
                rb = run_rollback(dry_run=False)
                assert rb["action"] == "DROPPED"

                conn = sqlite3.connect(str(tmp_db))
                exists_after = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='strategy_catalog'"
                ).fetchone()[0]
                conn.close()
                assert exists_after == 0, "Rollback did not drop strategy_catalog"
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup

    def test_rollback_dry_run_does_not_drop(self):
        """Rollback in dry-run mode must NOT drop the table."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply, run_rollback

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
                run_apply(dry_run=False, entries=entries)
                run_rollback(dry_run=True)  # dry-run rollback

                conn = sqlite3.connect(str(tmp_db))
                still_exists = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='strategy_catalog'"
                ).fetchone()[0]
                conn.close()
                assert still_exists == 1, "Dry-run rollback dropped the table!"
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup


class TestLifecyclePreservation:
    def test_lifecycle_state_not_changed(self):
        """Apply must NOT change lifecycle_state of any strategy to ONLINE."""
        from scripts.p2_catalog_apply import _build_catalog_entries, run_apply
        from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata

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
                run_apply(dry_run=False, entries=entries)

                # Check that ARTIFACT_CANDIDATE entries are NOT lifecycle=ONLINE
                conn = sqlite3.connect(str(tmp_db))
                conn.row_factory = sqlite3.Row
                violations = conn.execute(
                    """
                    SELECT strategy_id, lifecycle_state, catalog_visibility_state
                    FROM strategy_catalog
                    WHERE catalog_visibility_state = 'ARTIFACT_CANDIDATE'
                      AND lifecycle_state = 'ONLINE'
                    """
                ).fetchall()
                conn.close()
                assert len(violations) == 0, (
                    f"ARTIFACT_CANDIDATE entries marked ONLINE: {[dict(v) for v in violations]}"
                )
            finally:
                p2mod.DB_PATH   = original_db
                p2mod.BACKUP_DIR = original_backup
