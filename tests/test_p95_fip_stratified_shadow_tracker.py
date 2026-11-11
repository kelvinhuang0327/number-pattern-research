"""
P95 FIP-Stratified Shadow Tracker — Test Suite

測試項目：
1. Pre-flight source artifacts 存在
2. P94 final_classification 正確
3. P95 summary JSON 存在且合法
4. Segment n 與 P93/P94 基準一致（tolerance 1e-4）
5. HIGH_FIP hit_rate 與 P94 基準一致
6. MID/LOW FIP 未被標記為 strong signal
7. Policy block 禁止 recommendation/product/production
8. Governance flags 全部正確
9. Final classification 在允許列表內
10. 無 calibration/refit flag 啟用
11. 無 champion/recommendation mutation flag 啟用
"""

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
P95_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p95_fip_stratified_shadow_tracker_summary.json"
P94_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
P93_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p93_prediction_only_coverage_feature_bias_audit_summary.json"
P92_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p92_prediction_only_side_bias_baseline_gate_summary.json"
P91_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p91_prediction_only_tracking_gate_summary.json"
P84E_ROWS = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"

VALID_FINAL_CLASSIFICATIONS = {
    "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY",
    "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE",
    "P95_FIP_STRATIFIED_SHADOW_TRACKER_BLOCKED_BY_P94_MISMATCH",
    "P95_FIP_STRATIFIED_SHADOW_TRACKER_FAILED_VALIDATION",
}

P94_HIGH_FIP_N = 287
P94_HIGH_FIP_HIT_RATE = 0.641115
P93_MID_FIP_N = 343
P93_MID_FIP_HIT_RATE = 0.530612
P93_LOW_FIP_N = 178
P93_LOW_FIP_HIT_RATE = 0.528090
TOLERANCE = 1e-4


@pytest.fixture(scope="module")
def summary() -> dict:
    assert P95_SUMMARY.exists(), f"P95 summary not found: {P95_SUMMARY}"
    with open(P95_SUMMARY) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Pre-flight source artifacts 存在
# ---------------------------------------------------------------------------

class TestPreflightArtifacts:
    def test_p94_summary_exists(self):
        assert P94_SUMMARY.exists()

    def test_p93_summary_exists(self):
        assert P93_SUMMARY.exists()

    def test_p92_summary_exists(self):
        assert P92_SUMMARY.exists()

    def test_p91_summary_exists(self):
        assert P91_SUMMARY.exists()

    def test_p84e_rows_exist(self):
        assert P84E_ROWS.exists()

    def test_summary_gate_ok(self, summary):
        assert summary["step1_preflight"]["all_gates_ok"] is True


# ---------------------------------------------------------------------------
# 2. P94 final_classification 正確
# ---------------------------------------------------------------------------

class TestP94Classification:
    def test_p94_final_classification(self):
        with open(P94_SUMMARY) as f:
            d = json.load(f)
        assert d["final_classification"] == "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"

    def test_p94_upstream_check_in_p95(self, summary):
        checks = summary["step1_preflight"]["upstream_checks"]["details"]
        assert checks.get("p94_high_fip_subset_diagnostic_summary.json", {}).get("ok") is True

    def test_p93_upstream_check_in_p95(self, summary):
        checks = summary["step1_preflight"]["upstream_checks"]["details"]
        assert checks.get("p93_prediction_only_coverage_feature_bias_audit_summary.json", {}).get("ok") is True


# ---------------------------------------------------------------------------
# 3. P95 summary JSON 存在且合法
# ---------------------------------------------------------------------------

class TestP95SummaryStructure:
    def test_summary_exists(self):
        assert P95_SUMMARY.exists()

    def test_required_steps_present(self, summary):
        for key in ["step1_preflight", "step2_segment_metrics", "step3_shadow_tracker_policy",
                    "step4_drift_overclaim_guards", "step5_classification"]:
            assert key in summary, f"Missing key: {key}"

    def test_final_classification_present(self, summary):
        assert "final_classification" in summary

    def test_partial_coverage_present(self, summary):
        pc = summary.get("partial_coverage", {})
        assert pc.get("canonical_rows") == 828
        assert pc.get("schedule_rows") == 2430

    def test_governance_all_pass(self, summary):
        assert summary.get("governance_all_pass") is True


# ---------------------------------------------------------------------------
# 4. Segment n 與 P93/P94 基準一致
# ---------------------------------------------------------------------------

class TestSegmentNs:
    def test_high_fip_n(self, summary):
        n = summary["step2_segment_metrics"]["segments"]["HIGH_FIP"]["n"]
        assert abs(n - P94_HIGH_FIP_N) <= 1, f"HIGH_FIP n={n}, expected ~{P94_HIGH_FIP_N}"

    def test_mid_fip_n(self, summary):
        n = summary["step2_segment_metrics"]["segments"]["MID_FIP"]["n"]
        assert abs(n - P93_MID_FIP_N) <= 1, f"MID_FIP n={n}, expected ~{P93_MID_FIP_N}"

    def test_low_fip_n(self, summary):
        n = summary["step2_segment_metrics"]["segments"]["LOW_FIP"]["n"]
        assert abs(n - P93_LOW_FIP_N) <= 1, f"LOW_FIP n={n}, expected ~{P93_LOW_FIP_N}"

    def test_total_n_equals_outcome_rows(self, summary):
        seg = summary["step2_segment_metrics"]["segments"]
        total = seg["HIGH_FIP"]["n"] + seg["MID_FIP"]["n"] + seg["LOW_FIP"]["n"]
        n_outcome = summary["step2_segment_metrics"]["n_outcome_rows"]
        assert abs(total - n_outcome) <= 3, f"Segment total {total} != n_outcome {n_outcome}"

    def test_tolerance_all_ok(self, summary):
        assert summary["step2_segment_metrics"]["tolerance_checks"]["all_ok"] is True

    def test_status_passed(self, summary):
        assert summary["step2_segment_metrics"]["status"] == "PASSED"


# ---------------------------------------------------------------------------
# 5. HIGH_FIP hit_rate 與 P94 基準一致
# ---------------------------------------------------------------------------

class TestHighFIPHitRate:
    def test_high_fip_hit_rate(self, summary):
        hr = summary["step2_segment_metrics"]["segments"]["HIGH_FIP"]["hit_rate"]
        assert hr is not None
        assert abs(hr - P94_HIGH_FIP_HIT_RATE) <= TOLERANCE, (
            f"HIGH_FIP hit_rate {hr} outside tolerance of {P94_HIGH_FIP_HIT_RATE}"
        )

    def test_high_fip_tracking_status(self, summary):
        ts = summary["step2_segment_metrics"]["segments"]["HIGH_FIP"]["tracking_status"]
        assert ts == "HIGH_FIP_DIAGNOSTIC_TRACKING_ALLOWED"

    def test_high_fip_brier_range(self, summary):
        b = summary["step2_segment_metrics"]["segments"]["HIGH_FIP"]["brier"]
        assert 0.0 < b < 1.0

    def test_high_fip_tolerance_flag(self, summary):
        assert summary["step2_segment_metrics"]["tolerance_checks"]["high_fip_ok"] is True


# ---------------------------------------------------------------------------
# 6. MID/LOW FIP 未被標記為 strong signal
# ---------------------------------------------------------------------------

class TestMidLowNotStrong:
    def test_mid_fip_tracking_status(self, summary):
        ts = summary["step2_segment_metrics"]["segments"]["MID_FIP"]["tracking_status"]
        assert ts == "MID_FIP_WATCH_ONLY"

    def test_low_fip_tracking_status(self, summary):
        ts = summary["step2_segment_metrics"]["segments"]["LOW_FIP"]["tracking_status"]
        assert ts == "LOW_FIP_WATCH_ONLY"

    def test_mid_fip_hit_rate_matches_p93(self, summary):
        hr = summary["step2_segment_metrics"]["segments"]["MID_FIP"]["hit_rate"]
        assert abs(hr - P93_MID_FIP_HIT_RATE) <= TOLERANCE

    def test_low_fip_hit_rate_matches_p93(self, summary):
        hr = summary["step2_segment_metrics"]["segments"]["LOW_FIP"]["hit_rate"]
        assert abs(hr - P93_LOW_FIP_HIT_RATE) <= TOLERANCE

    def test_mid_tracking_status_not_allowed(self, summary):
        ts = summary["step2_segment_metrics"]["segments"]["MID_FIP"]["tracking_status"]
        assert "ALLOWED" not in ts

    def test_low_tracking_status_not_allowed(self, summary):
        ts = summary["step2_segment_metrics"]["segments"]["LOW_FIP"]["tracking_status"]
        assert "ALLOWED" not in ts


# ---------------------------------------------------------------------------
# 7. Policy block 禁止 recommendation/product/production
# ---------------------------------------------------------------------------

class TestPolicyBlock:
    def test_recommendation_not_allowed(self, summary):
        assert summary["step3_shadow_tracker_policy"]["recommendation_allowed"] is False

    def test_product_surface_not_allowed(self, summary):
        assert summary["step3_shadow_tracker_policy"]["product_surface_allowed"] is False

    def test_production_ready_false(self, summary):
        assert summary["step3_shadow_tracker_policy"]["production_ready"] is False

    def test_real_bet_not_allowed(self, summary):
        assert summary["step3_shadow_tracker_policy"]["real_bet_allowed"] is False

    def test_odds_required(self, summary):
        assert summary["step3_shadow_tracker_policy"]["odds_required_before_betting_claim"] is True

    def test_high_fip_is_diagnostic_only(self, summary):
        val = summary["step3_shadow_tracker_policy"]["high_fip_tracking"]
        assert "diagnostic_only" in val

    def test_mid_fip_watch_only(self, summary):
        val = summary["step3_shadow_tracker_policy"]["mid_fip_tracking"]
        assert "watch_only" in val

    def test_low_fip_watch_only(self, summary):
        val = summary["step3_shadow_tracker_policy"]["low_fip_tracking"]
        assert "watch_only" in val

    def test_policy_status_passed(self, summary):
        assert summary["step3_shadow_tracker_policy"]["status"] == "PASSED"


# ---------------------------------------------------------------------------
# 8. Governance flags 全部正確
# ---------------------------------------------------------------------------

class TestGovernanceFlags:
    def test_odds_used_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["odds_used"] is False

    def test_ev_computed_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["ev_computed"] is False

    def test_clv_computed_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["clv_computed"] is False

    def test_kelly_computed_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["kelly_computed"] is False

    def test_production_ready_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["production_ready"] is False

    def test_paper_only_true(self, summary):
        assert summary["step4_drift_overclaim_guards"]["paper_only"] is True

    def test_diagnostic_only_true(self, summary):
        assert summary["step4_drift_overclaim_guards"]["diagnostic_only"] is True

    def test_live_api_calls_zero(self, summary):
        assert summary["step4_drift_overclaim_guards"]["live_api_calls"] == 0

    def test_paid_api_calls_zero(self, summary):
        assert summary["step4_drift_overclaim_guards"]["paid_api_calls"] == 0

    def test_real_bet_not_allowed(self, summary):
        assert summary["step4_drift_overclaim_guards"]["real_bet_allowed"] is False

    def test_guards_status_passed(self, summary):
        assert summary["step4_drift_overclaim_guards"]["status"] == "PASSED"

    def test_top_level_paper_only(self, summary):
        assert summary.get("paper_only") is True

    def test_top_level_diagnostic_only(self, summary):
        assert summary.get("diagnostic_only") is True

    def test_top_level_production_ready_false(self, summary):
        assert summary.get("production_ready") is False


# ---------------------------------------------------------------------------
# 9. Final classification 在允許列表內
# ---------------------------------------------------------------------------

class TestFinalClassification:
    def test_final_classification_valid(self, summary):
        fc = summary["final_classification"]
        assert fc in VALID_FINAL_CLASSIFICATIONS, f"Invalid: {fc}"

    def test_allowed_classifications_complete(self, summary):
        allowed = set(summary.get("allowed_classifications", []))
        assert allowed == VALID_FINAL_CLASSIFICATIONS

    def test_rationale_present(self, summary):
        assert len(summary.get("classification_rationale", "")) > 0

    def test_not_failed_or_blocked(self, summary):
        fc = summary["final_classification"]
        assert "FAILED_VALIDATION" not in fc
        assert "BLOCKED" not in fc


# ---------------------------------------------------------------------------
# 10. 無 calibration/refit flag 啟用
# ---------------------------------------------------------------------------

class TestNoCalibrationRefit:
    def test_calibration_refit_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["calibration_refit"] is False

    def test_platt_scaling_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["platt_scaling"] is False

    def test_isotonic_scaling_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["isotonic_scaling"] is False

    def test_score_transform_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["score_transform_refit"] is False


# ---------------------------------------------------------------------------
# 11. 無 champion/recommendation mutation flag 啟用
# ---------------------------------------------------------------------------

class TestNoChampionOrRecommendation:
    def test_champion_replacement_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["champion_replacement"] is False

    def test_production_mutation_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["production_mutation"] is False

    def test_taiwan_lottery_recommendation_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["taiwan_lottery_recommendation"] is False

    def test_stake_sizing_false(self, summary):
        assert summary["step4_drift_overclaim_guards"]["stake_sizing"] is False

    def test_canonical_rows_not_modified(self, summary):
        assert summary["step4_drift_overclaim_guards"]["canonical_rows_modified"] is False

    def test_outcome_rows_not_modified(self, summary):
        assert summary["step4_drift_overclaim_guards"]["outcome_rows_modified"] is False

    def test_p84_to_p94_not_modified(self, summary):
        assert summary["step4_drift_overclaim_guards"]["p84_to_p94_artifacts_modified"] is False
