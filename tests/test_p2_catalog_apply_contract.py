"""
tests/test_p2_catalog_apply_contract.py
=========================================
Contract-level tests for the P2 catalog apply design.
Verifies safety invariants, table schema, and entry constraints.
Does NOT apply to the live DB.
"""

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest
from lottery_api.models.replay_strategy_catalog_contract import CatalogVisibilityState

DRY_RUN_OUTPUT = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"


@pytest.fixture(scope="module")
def dry_run_plan():
    assert DRY_RUN_OUTPUT.exists(), f"Missing: {DRY_RUN_OUTPUT}"
    return json.loads(DRY_RUN_OUTPUT.read_text())


class TestP2EntryCount:
    def test_total_entries_59(self, dry_run_plan):
        """Expected: 18 registered + 41 artifact candidates = 59."""
        assert dry_run_plan["total"] == 59, (
            f"Expected 59 total, got {dry_run_plan['total']}"
        )

    def test_all_are_insert_in_fresh_dry_run(self, dry_run_plan):
        """First dry-run on empty table → all 59 are INSERT."""
        assert dry_run_plan["inserted"] == 59
        assert dry_run_plan["updated"]  == 0
        assert dry_run_plan["skipped"]  == 0


class TestP2SafetyInvariants:
    def test_all_dry_run_only(self, dry_run_plan):
        """Every action must have dry_run_only=1."""
        for a in dry_run_plan["actions"]:
            assert a["dry_run_only"] == 1, (
                f"Entry {a['strategy_id']!r} has dry_run_only != 1"
            )

    def test_no_artifact_candidate_online(self, dry_run_plan):
        """ARTIFACT_CANDIDATE entries must never have lifecycle_state=ONLINE."""
        for a in dry_run_plan["actions"]:
            if a["catalog_visibility_state"] == CatalogVisibilityState.ARTIFACT_CANDIDATE:
                assert a["lifecycle_state"] != "ONLINE", (
                    f"ARTIFACT_CANDIDATE {a['strategy_id']!r} has lifecycle_state=ONLINE"
                )

    def test_no_violations(self, dry_run_plan):
        assert dry_run_plan["violations"] == []

    def test_dry_run_flag_true(self, dry_run_plan):
        assert dry_run_plan["dry_run"] is True

    def test_no_backup_in_dry_run(self, dry_run_plan):
        """Dry-run must NOT create a backup (only --apply does)."""
        assert dry_run_plan["backup_path"] is None


class TestP2MigrationFile:
    def test_migration_file_exists(self):
        migration = REPO_ROOT / "lottery_api" / "migrations" / "0002_p2_catalog_table.sql"
        assert migration.exists(), f"Missing: {migration}"

    def test_migration_has_unique_constraint(self):
        migration = REPO_ROOT / "lottery_api" / "migrations" / "0002_p2_catalog_table.sql"
        sql = migration.read_text()
        assert "UNIQUE(strategy_id, lottery_type)" in sql

    def test_migration_has_required_indexes(self):
        migration = REPO_ROOT / "lottery_api" / "migrations" / "0002_p2_catalog_table.sql"
        sql = migration.read_text()
        for idx in ["idx_sc_visibility", "idx_sc_lifecycle",
                    "idx_sc_has_replay_rows", "idx_sc_has_historical"]:
            assert idx in sql, f"Missing index: {idx}"

    def test_migration_no_touch_replay_rows(self):
        """Migration must not ALTER, UPDATE, DROP, or INSERT into protected tables."""
        migration = REPO_ROOT / "lottery_api" / "migrations" / "0002_p2_catalog_table.sql"
        import re
        sql = migration.read_text()
        # Strip SQL comments (-- ... lines) before checking
        sql_no_comments = re.sub(r'--[^\n]*', '', sql)
        lower = sql_no_comments.lower()
        protected = ["strategy_prediction_replays", "prediction_items"]
        for tbl in protected:
            assert tbl not in lower, (
                f"Migration DDL references protected table: {tbl}"
            )

    def test_migration_idempotent_create_if_not_exists(self):
        migration = REPO_ROOT / "lottery_api" / "migrations" / "0002_p2_catalog_table.sql"
        sql = migration.read_text()
        assert "CREATE TABLE IF NOT EXISTS strategy_catalog" in sql


class TestP2ApplyScript:
    def test_apply_script_exists(self):
        script = REPO_ROOT / "scripts" / "p2_catalog_apply.py"
        assert script.exists()

    def test_apply_script_has_rollback(self):
        script = REPO_ROOT / "scripts" / "p2_catalog_apply.py"
        code = script.read_text()
        assert "rollback" in code.lower()
        assert "DROP TABLE IF EXISTS strategy_catalog" in code

    def test_apply_script_has_backup(self):
        script = REPO_ROOT / "scripts" / "p2_catalog_apply.py"
        code = script.read_text()
        assert "_backup_db" in code

    def test_apply_script_protects_replay_rows(self):
        script = REPO_ROOT / "scripts" / "p2_catalog_apply.py"
        code = script.read_text()
        assert "strategy_prediction_replays" in code
        assert "_PROTECTED_TABLES" in code
