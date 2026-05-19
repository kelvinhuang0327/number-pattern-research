"""
tests/test_p1_catalog_visibility_plan.py
=========================================
Tests for the P1 catalog visibility planner (read-only validation).
"""

import json
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest
from scripts.p1_catalog_visibility_plan import build_plan
from lottery_api.models.replay_strategy_catalog_contract import CatalogVisibilityState

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"


@pytest.fixture(scope="module")
def plan():
    return build_plan(DB_PATH)


class TestPlannerDoesNotWriteDB:
    def test_planner_does_not_modify_db(self, plan):
        """Running the planner must not change row counts in the DB."""
        import sqlite3
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        conn.close()
        assert count == 460, f"DB was modified by planner! row count={count}"

    def test_all_entries_dry_run_only(self, plan):
        """Every entry in the plan must have dry_run_only=True."""
        for entry in plan["entries"]:
            assert entry["dry_run_only"] is True, (
                f"Entry {entry['strategy_id']!r} has dry_run_only=False"
            )

    def test_plan_dry_run_flag_true(self, plan):
        assert plan["dry_run_only"] is True


class TestExistingStrategiesVisible:
    def test_16_or_18_strategies_in_plan(self, plan):
        """Runtime canonical count must be >= 16 (main repo floor)."""
        count = plan["runtime_canonical_before"]["total"]
        assert count >= 16, f"Expected >=16 strategies, got {count}"

    def test_no_strategy_missing_from_plan(self, plan):
        """All strategies from the registry must appear in plan entries."""
        from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
        registry_ids = {e["strategy_id"] for e in list_strategy_lifecycle_metadata()}
        plan_ids = {e["strategy_id"] for e in plan["entries"]}
        missing = registry_ids - plan_ids
        assert not missing, f"Registry strategies missing from plan: {missing}"

    def test_strategies_with_replay_rows_classified_correctly(self, plan):
        """Strategies with replay rows must be REGISTERED_WITH_REPLAY_ROWS."""
        for entry in plan["entries"]:
            if entry["replay_row_count"] > 0:
                assert entry["catalog_visibility_state"] == CatalogVisibilityState.REGISTERED_WITH_REPLAY_ROWS, (
                    f"Strategy {entry['strategy_id']!r} has rows but state={entry['catalog_visibility_state']}"
                )


class TestArtifactCandidates:
    def test_artifact_candidates_not_online(self, plan):
        """ARTIFACT_CANDIDATE strategies must not have lifecycle_state=ONLINE."""
        all_entries = plan["entries"] + plan.get("artifact_candidates_extra", [])
        for entry in all_entries:
            if entry["catalog_visibility_state"] == CatalogVisibilityState.ARTIFACT_CANDIDATE:
                assert entry["lifecycle_state"] != "ONLINE", (
                    f"ARTIFACT_CANDIDATE {entry['strategy_id']!r} has lifecycle_state=ONLINE"
                )


class TestReconstructibleVsNoData:
    def test_reconstructible_has_reason(self, plan):
        """RECONSTRUCTIBLE entries must have reconstructible_reason set."""
        for entry in plan["entries"]:
            if entry["catalog_visibility_state"] == CatalogVisibilityState.RECONSTRUCTIBLE:
                assert entry["reconstructible_reason"], (
                    f"RECONSTRUCTIBLE {entry['strategy_id']!r} has no reconstructible_reason"
                )

    def test_no_data_not_reconstructible(self, plan):
        """An entry cannot be both RECONSTRUCTIBLE and have no_data_reason."""
        for entry in plan["entries"]:
            if entry["catalog_visibility_state"] == CatalogVisibilityState.RECONSTRUCTIBLE:
                # reconstructible_reason should be set, no_data_reason should be None
                assert entry.get("no_data_reason") is None, (
                    f"RECONSTRUCTIBLE {entry['strategy_id']!r} has no_data_reason set"
                )


class TestDriftGuardCompatibility:
    def test_drift_guard_still_passes_after_plan(self):
        """Running the planner must not break the drift guard."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/replay_lifecycle_drift_guard.py", "--strict"],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"Drift guard failed after planner run:\n{result.stdout}\n{result.stderr}"
        )

    def test_contract_tests_still_pass_after_plan(self):
        """API contract must still be 44/44 after planner run."""
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "tests/test_replay_api_contract.py"],
            capture_output=True, text=True,
            cwd=str(REPO_ROOT),
        )
        assert "44 passed" in result.stdout, (
            f"Contract tests degraded after planner:\n{result.stdout}\n{result.stderr}"
        )


class TestPlanOutputFiles:
    def test_json_output_exists(self):
        out = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
        assert out.exists(), f"JSON output missing: {out}"

    def test_json_output_valid(self):
        out = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
        data = json.loads(out.read_text())
        assert "entries" in data
        assert "by_visibility_state" in data
        assert "planned_actions" in data

    def test_md_output_exists(self):
        out = REPO_ROOT / "docs" / "replay" / "p1_catalog_visibility_plan_20260519.md"
        assert out.exists(), f"Markdown output missing: {out}"
