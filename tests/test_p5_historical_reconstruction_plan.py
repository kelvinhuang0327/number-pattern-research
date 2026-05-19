"""
tests/test_p5_historical_reconstruction_plan.py
=================================================
P5 Historical Reconstruction Plan tests.

Verifies:
  1. No --apply option (script is permanently dry-run)
  2. dry_run_only = True for all plan rows
  3. can_apply = False for all plan rows
  4. DB rows unchanged (460 before/after)
  5. No prediction rows inserted
  6. Only RECONSTRUCTIBLE strategies in plan
  7. ARTIFACT_CANDIDATE → not in plan rows
  8. NO_DATA → not in plan rows
  9. CODE_SCAN → NEEDS_P6_POLICY
 10. PREDICTION_LOG with payload → PLAN_INSERT_REPLAY_ROW
 11. Missing payload → SKIP_NO_HISTORICAL_PAYLOAD
 12. No invented prediction numbers
 13. PLAN_INSERT_REPLAY_ROW has provenance_hash
 14. All 300 P4 cells classified
 15. rows_to_insert_planned = 62, skipped = 238
"""

from __future__ import annotations

import inspect
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.p5_historical_reconstruction_plan import run_reconstruction_plan
from lottery_api.models.replay_reconstruction_plan_contract import PlannedAction

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
P1_JSON = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
P4_JSON = REPO_ROOT / "outputs" / "replay" / "p4_coverage_matrix_dry_run_20260520.json"


@pytest.fixture(scope="module")
def plan():
    return run_reconstruction_plan(
        limit=50, lottery_type_filter="DAILY_539",
        db_path=DB_PATH, p2_json=P2_JSON, p1_json=P1_JSON, p4_json=P4_JSON,
    )


# ---------------------------------------------------------------------------
# Section 1: No --apply, read-only safety
# ---------------------------------------------------------------------------

class TestNoApplyReadOnly:
    def test_script_has_no_apply_argument(self):
        """Script must not register --apply via add_argument."""
        from scripts import p5_historical_reconstruction_plan as mod
        src = inspect.getsource(mod.main)
        # Must not call add_argument with "--apply"
        assert 'add_argument("--apply"' not in src and "add_argument('--apply'" not in src, (
            "P5 script must not register --apply argument"
        )

    def test_plan_is_dry_run(self, plan):
        assert plan["dry_run"] is True

    def test_safety_flags_no_apply(self, plan):
        assert plan["safety_flags"]["no_apply_option"] is True

    def test_all_rows_dry_run_true(self, plan):
        assert plan["safety_flags"]["all_dry_run"] is True

    def test_all_rows_can_apply_false(self, plan):
        assert plan["safety_flags"]["all_can_apply_false"] is True

    def test_db_rows_unchanged(self, plan):
        assert plan["safety_flags"]["rows_unchanged"] is True
        assert plan["safety_flags"]["db_row_count_before"] == 460
        assert plan["safety_flags"]["db_row_count_after"] == 460

    def test_direct_db_count_still_460(self):
        conn = sqlite3.connect(str(DB_PATH))
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == 460


# ---------------------------------------------------------------------------
# Section 2: Denominator and scope
# ---------------------------------------------------------------------------

class TestDenominatorAndScope:
    def test_catalog_denominator_59(self, plan):
        assert plan["catalog_denominator"] == 59

    def test_reconstructible_strategy_count_6_for_daily539(self, plan):
        assert plan["reconstructible_strategy_count"] == 6

    def test_candidate_cells_300(self, plan):
        assert plan["candidate_cells"] == 300

    def test_draw_count_50(self, plan):
        assert plan["draw_count"] == 50

    def test_lottery_type_filter_daily539(self, plan):
        assert plan["lottery_type_filter"] == "DAILY_539"


# ---------------------------------------------------------------------------
# Section 3: Action counts
# ---------------------------------------------------------------------------

class TestActionCounts:
    def test_rows_to_insert_planned_is_62(self, plan):
        assert plan["rows_to_insert_planned"] == 62

    def test_total_cells_equals_planned_plus_skipped(self, plan):
        total_skipped = sum(plan["skipped_by_reason"].values())
        assert plan["rows_to_insert_planned"] + total_skipped == 300

    def test_needs_p6_policy_count_is_100(self, plan):
        count = plan["skipped_by_reason"].get(PlannedAction.NEEDS_P6_POLICY, 0)
        assert count == 100  # acb_markov_midfreq(50) + midfreq_fourier_2bet(50)

    def test_skip_source_missing_count_is_50(self, plan):
        count = plan["skipped_by_reason"].get(PlannedAction.SKIP_SOURCE_MISSING, 0)
        assert count == 50  # p1_deviation_2bet_539 × 50 draws

    def test_skip_no_payload_count_is_88(self, plan):
        count = plan["skipped_by_reason"].get(PlannedAction.SKIP_NO_HISTORICAL_PAYLOAD, 0)
        assert count == 88  # acb_markov_midfreq_3bet(6) + acb_1bet(41) + midfreq_acb_2bet(41)

    def test_all_300_p4_cells_classified(self, plan):
        planned  = plan["rows_to_insert_planned"]
        skipped  = sum(plan["skipped_by_reason"].values())
        assert planned + skipped == 300, (
            f"Not all 300 P4 cells classified: planned={planned}, skipped={skipped}"
        )


# ---------------------------------------------------------------------------
# Section 4: Per-row semantic correctness
# ---------------------------------------------------------------------------

class TestPlanRowSemantics:
    def test_all_plan_rows_are_reconstructible(self, plan):
        for row in plan["plan_rows"]:
            assert row["catalog_visibility_state"] == "RECONSTRUCTIBLE", (
                f"Row for {row['strategy_id']!r}/{row['draw_id']!r} has wrong visibility"
            )

    def test_plan_insert_rows_have_provenance_hash(self, plan):
        for row in plan["plan_rows"]:
            if row["planned_action"] == PlannedAction.PLAN_INSERT_REPLAY_ROW:
                assert row["provenance_hash"], (
                    f"PLAN_INSERT row {row['plan_id']!r} missing provenance_hash"
                )

    def test_plan_insert_rows_have_predicted_numbers(self, plan):
        for row in plan["plan_rows"]:
            if row["planned_action"] == PlannedAction.PLAN_INSERT_REPLAY_ROW:
                assert row["predicted_numbers"] is not None, (
                    f"PLAN_INSERT row {row['plan_id']!r} missing predicted_numbers"
                )
                assert len(row["predicted_numbers"]) > 0

    def test_no_invented_numbers_for_skip_rows(self, plan):
        for row in plan["plan_rows"]:
            if row["planned_action"] != PlannedAction.PLAN_INSERT_REPLAY_ROW:
                assert row["predicted_numbers"] is None, (
                    f"Skip row {row['plan_id']!r} must not have predicted_numbers"
                )

    def test_code_scan_strategies_get_needs_p6(self, plan):
        code_scan = ["acb_markov_midfreq", "midfreq_fourier_2bet"]
        for row in plan["plan_rows"]:
            if row["strategy_id"] in code_scan:
                assert row["planned_action"] == PlannedAction.NEEDS_P6_POLICY, (
                    f"{row['strategy_id']!r} draw {row['draw_id']!r}: "
                    f"expected NEEDS_P6_POLICY, got {row['planned_action']!r}"
                )

    def test_all_rows_have_coverage_status_before_reconstructible_pending(self, plan):
        for row in plan["plan_rows"]:
            assert row["coverage_status_before"] == "RECONSTRUCTIBLE_PENDING"

    def test_all_rows_truth_level_plan_only(self, plan):
        for row in plan["plan_rows"]:
            from lottery_api.models.replay_reconstruction_plan_contract import TruthLevel
            assert row["truth_level"] == TruthLevel.RECONSTRUCTION_PLAN_ONLY

    def test_all_can_apply_serialized_false(self, plan):
        for row in plan["plan_rows"]:
            assert row["can_apply"] is False

    def test_all_dry_run_only_true(self, plan):
        for row in plan["plan_rows"]:
            assert row["dry_run_only"] is True


# ---------------------------------------------------------------------------
# Section 5: Per-strategy breakdown
# ---------------------------------------------------------------------------

class TestPerStrategyBreakdown:
    def test_acb_markov_midfreq_3bet_planned_44(self, plan):
        s = plan["by_strategy"]["acb_markov_midfreq_3bet"]
        assert s["planned"] == 44

    def test_acb_1bet_planned_9(self, plan):
        s = plan["by_strategy"]["acb_1bet"]
        assert s["planned"] == 9

    def test_midfreq_acb_2bet_planned_9(self, plan):
        s = plan["by_strategy"]["midfreq_acb_2bet"]
        assert s["planned"] == 9

    def test_acb_markov_midfreq_all_skipped(self, plan):
        s = plan["by_strategy"]["acb_markov_midfreq"]
        assert s["planned"] == 0
        assert s["skipped"] == 50

    def test_midfreq_fourier_2bet_all_skipped(self, plan):
        s = plan["by_strategy"]["midfreq_fourier_2bet"]
        assert s["planned"] == 0
        assert s["skipped"] == 50

    def test_p1_deviation_all_skipped(self, plan):
        s = plan["by_strategy"]["p1_deviation_2bet_539"]
        assert s["planned"] == 0
        assert s["skipped"] == 50


# ---------------------------------------------------------------------------
# Section 6: Output shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_required_top_level_fields(self, plan):
        required = [
            "generated_at", "phase", "dry_run", "catalog_denominator",
            "reconstructible_strategy_count", "candidate_cells",
            "rows_to_insert_planned", "skipped_by_reason",
            "by_strategy", "provenance_summary", "safety_flags", "plan_rows",
        ]
        for f in required:
            assert f in plan, f"Missing field: {f!r}"

    def test_plan_rows_have_required_fields(self, plan):
        required_row_fields = [
            "plan_id", "strategy_id", "lottery_type", "draw_id",
            "catalog_visibility_state", "coverage_status_before",
            "planned_action", "dry_run_only", "can_apply",
            "truth_level", "created_by_phase",
        ]
        for row in plan["plan_rows"][:5]:
            for f in required_row_fields:
                assert f in row, f"Plan row missing field: {f!r}"
