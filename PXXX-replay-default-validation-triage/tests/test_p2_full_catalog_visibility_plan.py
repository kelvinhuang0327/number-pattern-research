"""
test_p2_full_catalog_visibility_plan.py
=========================================
Tests for P2 Full-Catalog Visibility Plan.

Verifies:
  1. Plan contains exactly the four visibility states
  2. ROW_BACKED count matches actual strategy_prediction_replays grouping
  3. RECONSTRUCTIBLE entries have prediction_items_count > 0
  4. NO_DATA entries have both replay_row_count==0 and prediction_items_count==0
  5. ARTIFACT_ONLY entries are not in runtime registry
  6. All entries have dry_run_only=True
  7. Zero DB writes (production table unchanged)
  8. Script is read-only (no write SQL patterns)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT    = Path(__file__).resolve().parent.parent
DB_PATH      = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
PLAN_JSON    = REPO_ROOT / "outputs" / "replay" / "p2_full_catalog_visibility_plan_20260520.json"
PLAN_SCRIPT  = REPO_ROOT / "scripts" / "p2_full_catalog_visibility_plan.py"

sys.path.insert(0, str(REPO_ROOT))

VALID_STATES = {"ROW_BACKED", "RECONSTRUCTIBLE", "NO_DATA", "ARTIFACT_ONLY"}
EXPECTED_REGISTRY_COUNT = 18


@pytest.fixture(scope="module")
def plan() -> dict:
    """Load the P2 catalog visibility plan JSON."""
    assert PLAN_JSON.exists(), f"Plan JSON not found: {PLAN_JSON}. Run p2_full_catalog_visibility_plan.py first."
    return json.loads(PLAN_JSON.read_text())


@pytest.fixture(scope="module")
def registry_ids() -> set[str]:
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
    return {m["strategy_id"] for m in list_strategy_lifecycle_metadata()}


@pytest.fixture(scope="module")
def replay_counts() -> dict[str, int]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA query_only = ON")
    rows = conn.execute(
        "SELECT strategy_id, COUNT(*) as cnt FROM strategy_prediction_replays GROUP BY strategy_id"
    ).fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}


class TestPlanStructure:
    def test_plan_has_required_keys(self, plan):
        for key in ("phase", "generated_at", "dry_run_only", "by_visibility_state", "entries",
                    "total_entries", "registry_count", "artifact_only_count",
                    "production_replay_rows_unchanged", "safety_flags"):
            assert key in plan, f"Missing key: {key}"

    def test_phase_is_p2(self, plan):
        assert plan["phase"] == "P2_FULL_CATALOG_VISIBILITY_PLAN"

    def test_dry_run_only_true(self, plan):
        assert plan["dry_run_only"] is True

    def test_db_write_false(self, plan):
        assert plan["safety_flags"]["db_write_performed"] is False

    def test_replay_rows_not_generated(self, plan):
        assert plan["safety_flags"]["replay_rows_generated"] is False

    def test_strategy_execution_false(self, plan):
        assert plan["safety_flags"]["strategy_execution_performed"] is False

    def test_four_visibility_states_present(self, plan):
        states = set(plan["by_visibility_state"].keys())
        assert states == VALID_STATES, (
            f"Expected exactly {VALID_STATES}, got {states}"
        )

    def test_registry_count_is_18(self, plan):
        assert plan["registry_count"] == EXPECTED_REGISTRY_COUNT

    def test_total_entries_matches_sum(self, plan):
        total_from_counts = sum(plan["by_visibility_state"].values())
        assert plan["total_entries"] == total_from_counts


class TestVisibilityStates:
    def test_row_backed_count_matches_db(self, plan, replay_counts):
        expected_row_backed = len([sid for sid, cnt in replay_counts.items() if cnt > 0])
        actual_row_backed = plan["by_visibility_state"]["ROW_BACKED"]
        assert actual_row_backed == expected_row_backed, (
            f"ROW_BACKED count {actual_row_backed} != DB count {expected_row_backed}"
        )

    def test_row_backed_entries_have_replay_rows(self, plan, replay_counts):
        for e in plan["entries"]:
            if e["visibility_state"] == "ROW_BACKED":
                assert e["replay_row_count"] > 0, (
                    f"ROW_BACKED entry {e['strategy_id']} has replay_row_count=0"
                )

    def test_reconstructible_entries_have_prediction_items(self, plan):
        for e in plan["entries"]:
            if e["visibility_state"] == "RECONSTRUCTIBLE":
                assert e.get("prediction_items_count", 0) > 0, (
                    f"RECONSTRUCTIBLE entry {e['strategy_id']} has no prediction_items"
                )
                assert e.get("reconstructible_reason") is not None

    def test_no_data_entries_have_zero_source(self, plan):
        for e in plan["entries"]:
            if e["visibility_state"] == "NO_DATA":
                assert e.get("replay_row_count", 0) == 0
                assert e.get("prediction_items_count", 0) == 0
                assert e.get("no_data_reason") is not None

    def test_artifact_only_not_in_registry(self, plan, registry_ids):
        for e in plan["entries"]:
            if e["visibility_state"] == "ARTIFACT_ONLY":
                assert e["strategy_id"] not in registry_ids, (
                    f"ARTIFACT_ONLY entry {e['strategy_id']} is in runtime registry"
                )

    def test_all_entries_dry_run_only(self, plan):
        for e in plan["entries"]:
            assert e.get("dry_run_only") is True, (
                f"Entry {e.get('strategy_id', '?')} has dry_run_only != True"
            )

    def test_all_entries_cannot_generate_rows(self, plan):
        for e in plan["entries"]:
            assert e.get("can_generate_replay_rows") is False, (
                f"Entry {e.get('strategy_id', '?')} has can_generate_replay_rows=True"
            )

    def test_no_entry_is_both_row_backed_and_reconstructible(self, plan):
        row_backed_ids = {e["strategy_id"] for e in plan["entries"]
                          if e["visibility_state"] == "ROW_BACKED"}
        reconstructible_ids = {e["strategy_id"] for e in plan["entries"]
                                if e["visibility_state"] == "RECONSTRUCTIBLE"}
        overlap = row_backed_ids & reconstructible_ids
        assert not overlap, f"Strategy IDs in both ROW_BACKED and RECONSTRUCTIBLE: {overlap}"


class TestProductionDBIntegrity:
    def test_production_rows_unchanged(self, plan):
        """Production DB must remain at 460 rows."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        actual = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert actual == 460, f"Production rows changed: expected 460, got {actual}"

    def test_plan_reports_correct_production_rows(self, plan):
        assert plan["production_replay_rows_unchanged"] == 460


class TestScriptSafety:
    def test_script_has_no_insert_sql(self):
        src = PLAN_SCRIPT.read_text()
        assert "INSERT INTO" not in src.upper(), (
            "P2 plan script must not contain INSERT SQL"
        )

    def test_script_has_no_delete_sql(self):
        src = PLAN_SCRIPT.read_text()
        assert "DELETE FROM" not in src.upper()

    def test_script_has_no_update_sql(self):
        src = PLAN_SCRIPT.read_text()
        assert "UPDATE " not in src.upper()

    def test_script_opens_db_readonly(self):
        src = PLAN_SCRIPT.read_text()
        assert "query_only" in src or "mode=ro" in src, (
            "P2 script must open DB read-only"
        )

    def test_script_has_no_strategy_execution(self):
        src = PLAN_SCRIPT.read_text()
        assert "predict_func" not in src and "generate_numbers" not in src
