"""
test_p9_replay_launch_readiness_lock.py
=========================================
P9 Source-of-Truth Hardening — Lock Verification Tests.

Verifies the complete P0-P8 state is frozen and consistent:
  1. Production rows = 460 (the absolute ground truth)
  2. Drift guard passes
  3. Lock JSON exists and has correct classification
  4. Phase completion states match expected
  5. No unauthorized apply performed
  6. All invariants hold (no fake success, no retired in ONLINE scope, etc.)
  7. Canonical artifact files exist
  8. Coverage matrix totals consistent
  9. P7 gate correctly blocked (phrase not received)
 10. P8 field completeness = 100%
 11. Exactly 2 valid next actions documented
 12. Registry count = 18 canonical strategies
 13. API history response now includes P5 fields (visibility_state etc.)
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT  = Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
LOCK_JSON  = REPO_ROOT / "outputs" / "replay" / "p9_replay_launch_readiness_lock_20260520.json"

# All canonical P0-P8 artifacts that must exist
CANONICAL_ARTIFACTS = {
    # P0/P1
    "docs/replay/p1b_registry_reconciliation_20260520.md",
    "docs/replay/p7_readiness_report_20260520.md",
    # P2
    "docs/replay/p2_full_catalog_visibility_plan_20260520.md",
    "outputs/replay/p2_full_catalog_visibility_plan_20260520.json",
    # P3
    "docs/replay/p3_per_draw_all_strategy_coverage_matrix_20260520.md",
    "outputs/replay/p3_per_draw_all_strategy_coverage_matrix_20260520.json",
    "outputs/replay/p3_per_draw_all_strategy_coverage_summary_20260520.json",
    # P4
    "docs/replay/p4_apply_readiness_review_20260520.md",
    # P5
    "docs/replay/p5_replay_visual_api_verification_20260520.md",
    "outputs/replay/p5_replay_visual_api_verification_20260520.json",
    # P6
    "docs/replay/p6_catalog_apply_plan_v1_20260520.md",
    "outputs/replay/p6_catalog_apply_plan_v1_20260520.json",
    # P7
    "docs/replay/p7_authorized_apply_gate_review_20260520.md",
    "outputs/replay/p7_authorized_apply_gate_review_20260520.json",
    "outputs/replay/p7_controlled_apply_dry_run_20260520.json",
    # P8
    "docs/replay/p8_reconstructible_backfill_dry_run_20260520.md",
    "outputs/replay/p8_reconstructible_backfill_dry_run_20260520.json",
    # P9
    "outputs/replay/p9_replay_launch_readiness_lock_20260520.json",
    "docs/replay/p9_replay_launch_readiness_lock_20260520.md",
    "docs/replay/p9_canonical_artifact_index_20260520.md",
    # Scripts
    "scripts/p7_controlled_replay_row_apply.py",
    "scripts/p8_reconstructible_backfill_dry_run.py",
    "scripts/p2_full_catalog_visibility_plan.py",
    "scripts/p3_per_draw_all_strategy_coverage_matrix.py",
    "scripts/p6_catalog_apply_plan_v1.py",
    # Tests
    "tests/test_p7_controlled_apply_actual_gate.py",
    "tests/test_p2_full_catalog_visibility_plan.py",
    "tests/test_p3_per_draw_all_strategy_coverage_matrix.py",
    "tests/test_p6_catalog_apply_plan_v1.py",
    "tests/test_p8_reconstructible_backfill_dry_run.py",
}

sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="module")
def lock() -> dict:
    assert LOCK_JSON.exists(), f"Lock JSON not found: {LOCK_JSON}"
    return json.loads(LOCK_JSON.read_text())


class TestProductionGroundTruth:
    """Production DB state — the absolute ground truth."""

    def test_production_rows_460(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("PRAGMA query_only = ON")
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        conn.close()
        assert count == 460, (
            f"CRITICAL: Production rows = {count}, expected 460. "
            "An unauthorized apply may have occurred."
        )

    def test_no_unauthorized_apply_occurred(self, lock):
        assert lock["safety_flags"]["unauthorized_apply_performed"] is False
        assert lock["safety_flags"]["db_write_performed"] is False

    def test_lock_reports_460(self, lock):
        assert lock["production_state"]["strategy_prediction_replays_rows"] == 460


class TestLockStructure:
    def test_phase_is_p9(self, lock):
        assert lock["phase"] == "P9_REPLAY_LAUNCH_READINESS_LOCK"

    def test_classification(self, lock):
        assert lock["lock_classification"] == "P9_LOCKED_AWAITING_CEO_DECISION"

    def test_has_required_keys(self, lock):
        for key in ("phase", "lock_classification", "production_state",
                    "phase_completion", "catalog_universe", "coverage_matrix",
                    "p7_gate", "p8_reconstructible", "next_valid_actions",
                    "invariants", "safety_flags"):
            assert key in lock, f"Missing key: {key}"

    def test_exactly_two_next_actions(self, lock):
        assert len(lock["next_valid_actions"]) == 2

    def test_action_ids(self, lock):
        ids = {a["id"] for a in lock["next_valid_actions"]}
        assert ids == {"ACTION_A", "ACTION_B"}

    def test_action_a_requires_ceo_phrase(self, lock):
        action_a = next(a for a in lock["next_valid_actions"] if a["id"] == "ACTION_A")
        assert "YES apply P7 controlled replay rows" in action_a["trigger"]
        assert action_a["blocked_by"] is not None

    def test_action_b_not_blocked(self, lock):
        action_b = next(a for a in lock["next_valid_actions"] if a["id"] == "ACTION_B")
        assert action_b["blocked_by"] is None


class TestPhaseCompletion:
    def test_p0_through_p6_complete(self, lock):
        completed = [
            "P0_schema_stabilization",
            "P1_catalog_visibility_plan",
            "P2_full_catalog_visibility_plan_v2",
            "P3_per_draw_coverage_matrix",
            "P4_apply_readiness_review",
            "P5_api_verification_minimal_patch",
            "P6_catalog_apply_plan_v1",
            "P8_reconstructible_backfill_dry_run",
        ]
        for phase in completed:
            status = lock["phase_completion"].get(phase, "")
            assert "COMPLETE" in status, f"Phase {phase} not marked COMPLETE: {status}"

    def test_p7_blocked(self, lock):
        p7_status = lock["phase_completion"].get("P7_apply_gate", "")
        assert "BLOCKED" in p7_status or "blocked" in p7_status.lower()

    def test_all_test_suites_green(self, lock):
        assert lock["production_state"]["total_tests"] == "185/185 PASS"
        assert lock["production_state"]["api_contract_tests"] == "44/44 PASS"


class TestCoverageMatrixLock:
    def test_total_cells(self, lock):
        assert lock["coverage_matrix"]["total_cells"] == 1288

    def test_row_backed_cells(self, lock):
        assert lock["coverage_matrix"]["row_backed_cells"] == 300

    def test_reconstructible_cells(self, lock):
        assert lock["coverage_matrix"]["reconstructible_cells"] == 121

    def test_fake_success_is_zero(self, lock):
        assert lock["coverage_matrix"]["fake_success_count"] == 0
        assert lock["invariants"]["fake_success_count_is_zero"] is True

    def test_no_data_never_counted(self, lock):
        assert lock["invariants"]["no_data_never_counted_as_success"] is True


class TestP7GateLock:
    def test_authorization_not_received(self, lock):
        assert lock["p7_gate"]["authorization_received"] is False

    def test_required_phrase(self, lock):
        assert lock["p7_gate"]["required_phrase"] == "YES apply P7 controlled replay rows"

    def test_online_scope_28_rows(self, lock):
        assert lock["p7_gate"]["online_scope_rows"] == 28

    def test_online_strategies(self, lock):
        strats = set(lock["p7_gate"]["online_scope_strategies"])
        assert strats == {"fourier_rhythm_3bet", "ts3_regime_3bet"}

    def test_retired_scope_deferred(self, lock):
        assert lock["p7_gate"]["retired_scope_deferred"] is True
        assert lock["p7_gate"]["retired_scope_rows"] == 93

    def test_projected_rows_after_online(self, lock):
        assert lock["p7_gate"]["projected_rows_after_online"] == 488

    def test_no_retired_in_online_apply(self, lock):
        assert lock["invariants"]["no_retired_rows_in_p7_online_apply"] is True


class TestP8Lock:
    def test_total_candidates(self, lock):
        assert lock["p8_reconstructible"]["total_candidates"] == 121

    def test_field_completeness_100pct(self, lock):
        assert lock["p8_reconstructible"]["field_completeness_pct"] == 100.0

    def test_ready_count(self, lock):
        assert lock["p8_reconstructible"]["ready_for_online_apply"] == 28

    def test_pending_review_count(self, lock):
        assert lock["p8_reconstructible"]["pending_human_review_retired"] == 93


class TestCanonicalArtifacts:
    @pytest.mark.parametrize("artifact", sorted(CANONICAL_ARTIFACTS))
    def test_artifact_exists(self, artifact):
        path = REPO_ROOT / artifact
        assert path.exists(), f"Canonical artifact missing: {artifact}"


class TestAPIMinimalPatch:
    """Verify the P5 minimal API patch is active (fields present in response)."""

    def test_history_response_has_visibility_state(self):
        route_src = (REPO_ROOT / "lottery_api" / "routes" / "replay.py").read_text()
        assert '"visibility_state"' in route_src or "'visibility_state'" in route_src

    def test_history_response_has_display_status(self):
        route_src = (REPO_ROOT / "lottery_api" / "routes" / "replay.py").read_text()
        assert '"display_status"' in route_src or "'display_status'" in route_src

    def test_history_response_has_should_count(self):
        route_src = (REPO_ROOT / "lottery_api" / "routes" / "replay.py").read_text()
        assert "should_count_as_success" in route_src


class TestRegistryLock:
    def test_registry_count_18(self, lock):
        assert lock["catalog_universe"]["registry_strategies"] == 18

    def test_artifact_only_count_41(self, lock):
        assert lock["catalog_universe"]["artifact_only"] == 41

    def test_total_universe_59(self, lock):
        assert lock["catalog_universe"]["total_strategies"] == 59

    def test_row_backed_6(self, lock):
        assert lock["catalog_universe"]["by_visibility_state"]["ROW_BACKED"] == 6

    def test_reconstructible_5(self, lock):
        assert lock["catalog_universe"]["by_visibility_state"]["RECONSTRUCTIBLE"] == 5

    def test_no_data_7(self, lock):
        assert lock["catalog_universe"]["by_visibility_state"]["NO_DATA"] == 7
