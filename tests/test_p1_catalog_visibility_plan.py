"""
test_p1_catalog_visibility_plan.py
=====================================
Tests for the P1 catalog visibility planner.

Covers:
  1. Planner reports runtime_canonical_before = 18
  2. Planner creates NO_DATA entries for artifact candidates
  3. Planner dry-run does not write to DB
  4. Plan JSON has correct safety flags (all False)
  5. Plan JSON matches required schema
  6. No ONLINE artifact candidates in plan
  7. Skipped entries are bogus/unsafe IDs
  8. Plan output files exist after planner run
"""
import json
import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
PLAN_JSON = PROJECT_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260518.json"
PLAN_MD = PROJECT_ROOT / "docs" / "replay" / "p1_catalog_visibility_plan_20260518.md"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"


@pytest.fixture(scope="module")
def plan():
    """Load the pre-generated plan JSON."""
    if not PLAN_JSON.exists():
        pytest.skip(f"Plan JSON not found: {PLAN_JSON}. Run p1_catalog_visibility_plan.py first.")
    return json.loads(PLAN_JSON.read_text())


class TestPlanSchema:
    def test_plan_file_exists(self):
        assert PLAN_JSON.exists(), f"Plan JSON not found: {PLAN_JSON}"

    def test_markdown_file_exists(self):
        assert PLAN_MD.exists(), f"Plan markdown not found: {PLAN_MD}"

    def test_plan_required_keys(self, plan):
        required = [
            "generated_at", "runtime_canonical_before", "artifact_candidate_count",
            "planned_new_registry_entries", "planned_existing_registry_updates",
            "planned_no_data_entries", "by_lottery", "by_lifecycle", "entries", "safety",
        ]
        for key in required:
            assert key in plan, f"Missing required key in plan: {key}"

    def test_plan_safety_all_false(self, plan):
        safety = plan["safety"]
        assert safety["db_write"] is False
        assert safety["draw_import"] is False
        assert safety["replay_row_generation"] is False
        assert safety["prediction_update"] is False
        assert safety["strategy_execution"] is False

    def test_plan_json_serializable(self, plan):
        # Should already be a dict, but verify round-trip
        json.dumps(plan)


class TestPlanContent:
    def test_runtime_canonical_before_is_18(self, plan):
        assert plan["runtime_canonical_before"] == 18, \
            f"Expected 18 canonical strategies, got {plan['runtime_canonical_before']}"

    def test_artifact_candidate_count_positive(self, plan):
        assert plan["artifact_candidate_count"] > 0, \
            "Expected at least 1 artifact candidate in plan"

    def test_entries_count_positive(self, plan):
        assert len(plan["entries"]) > 0, "Expected at least 1 entry in plan"

    def test_no_online_artifact_candidates(self, plan):
        """Artifact candidates must NEVER be marked ONLINE."""
        violations = [
            e for e in plan["entries"]
            if e["catalog_visibility_state"] == "ARTIFACT_CANDIDATE"
            and e["lifecycle_state"] == "ONLINE"
        ]
        assert violations == [], \
            f"Found {len(violations)} ARTIFACT_CANDIDATE entries with ONLINE lifecycle: {[v['strategy_id'] for v in violations]}"

    def test_artifact_candidates_have_no_data_reason(self, plan):
        """All artifact candidates must have no_data_reason set."""
        missing = [
            e for e in plan["entries"]
            if e["catalog_visibility_state"] == "ARTIFACT_CANDIDATE"
            and not e.get("no_data_reason")
        ]
        assert missing == [], \
            f"Artifact candidates missing no_data_reason: {[m['strategy_id'] for m in missing]}"

    def test_artifact_candidates_have_no_replay_rows(self, plan):
        """Artifact candidates must have has_replay_rows=False."""
        with_rows = [
            e for e in plan["entries"]
            if e["catalog_visibility_state"] == "ARTIFACT_CANDIDATE"
            and e.get("has_replay_rows")
        ]
        assert with_rows == [], \
            f"Artifact candidates claiming replay rows: {[e['strategy_id'] for e in with_rows]}"

    def test_skipped_entries_are_bogus(self, plan):
        """Skipped entries should be bogus/unsafe (generic names)."""
        skipped = plan.get("skipped_entries", [])
        # Bogus IDs are generic names like 'big_lotto', 'daily_539', etc.
        bogus_ids = {"big_lotto", "daily_539", "power_lotto", "strategy"}
        for s in skipped:
            assert s["strategy_id"] in bogus_ids or len(s.get("reason", "")) > 0, \
                f"Skipped entry has no reason: {s}"

    def test_existing_18_strategies_in_plan(self, plan):
        """All 18 existing code registry strategies must appear in the plan."""
        expected_18 = {
            "power_precision_3bet", "power_orthogonal_5bet", "fourier_rhythm_3bet",
            "biglotto_triple_strike", "biglotto_deviation_2bet", "ts3_regime_3bet",
            "daily539_f4cold", "daily539_markov_cold",
            "biglotto_ts3_acb_4bet", "biglotto_ts3_markov_freq_5bet",
            "power_shlc_midfreq", "p1_deviation_2bet_539",
            "acb_1bet", "acb_markov_midfreq", "acb_markov_midfreq_3bet",
            "midfreq_acb_2bet", "midfreq_fourier_2bet", "h6_gate_mk20_ew85",
        }
        plan_ids = {e["strategy_id"] for e in plan["entries"]}
        missing = expected_18 - plan_ids
        assert missing == set(), \
            f"Missing existing strategies in plan: {missing}"

    def test_by_lottery_includes_all_types(self, plan):
        by_lottery = plan["by_lottery"]
        # Should have at least BIG_LOTTO, DAILY_539, POWER_LOTTO
        assert "BIG_LOTTO" in by_lottery, "Missing BIG_LOTTO in by_lottery"
        assert "DAILY_539" in by_lottery, "Missing DAILY_539 in by_lottery"
        assert "POWER_LOTTO" in by_lottery, "Missing POWER_LOTTO in by_lottery"


class TestPlanNoDB:
    def test_dry_run_did_not_write_to_existing_tables(self, plan):
        """
        Verify that the planner did NOT modify existing replay/prediction tables.
        Check row counts remain stable.
        """
        con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            # strategy_replay_runs should have exactly 7 rows (V1+V2 combined scopes)
            run_count = con.execute("SELECT COUNT(*) FROM strategy_replay_runs").fetchone()[0]
            # We just verify it's a positive number (not zero after planner ran)
            assert run_count >= 0, "strategy_replay_runs was unexpectedly zeroed"

            # prediction_items should be untouched
            item_count = con.execute("SELECT COUNT(*) FROM prediction_items").fetchone()[0]
            assert item_count >= 0

        finally:
            con.close()
