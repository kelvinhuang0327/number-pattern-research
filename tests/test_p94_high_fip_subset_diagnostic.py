"""
P94 High-FIP Subset Diagnostic — Test Suite

測試項目：
1. Pre-flight gates（Gate 1 / Gate 3）
2. Upstream artifact existence + final_classification 一致性
3. Row inventory recount vs P93 tolerance
4. High-FIP metrics recount vs P93 step6 tolerance
5. Bootstrap CI 結果落在合理範圍
6. Temporal split metrics 結構正確
7. Side split metrics 結構正確
8. Segment qualification 邏輯（兩條 path）
9. Final classification 在五分類列表內
10. Governance flags 全部正確
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
P94_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"

VALID_FINAL_CLASSIFICATIONS = {
    "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY",
    "P94_HIGH_FIP_PROMISING_BUT_SAMPLE_LIMITED",
    "P94_HIGH_FIP_UNSTABLE_REQUIRES_REVIEW",
    "P94_HIGH_FIP_NOT_SEPARABLE_FROM_NOISE",
    "P94_FAILED_VALIDATION",
}

HOME_BASELINE = 0.524752
P93_HIGH_FIP_HIT_RATE = 0.641115
P93_HIGH_FIP_N = 287
TOLERANCE = 1e-4


@pytest.fixture(scope="module")
def summary() -> dict:
    assert P94_SUMMARY.exists(), f"P94 summary not found: {P94_SUMMARY}"
    with open(P94_SUMMARY) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Pre-flight Gate 1 — canonical entry
# ---------------------------------------------------------------------------

class TestGate1CanonicalEntry:
    def test_git_toplevel_is_repo_root(self):
        toplevel = os.popen("git rev-parse --show-toplevel").read().strip()
        assert toplevel == "/Users/kelvin/Kelvin-WorkSpace/Betting-pool"

    def test_branch_is_main(self):
        branch = os.popen("git branch --show-current").read().strip()
        assert branch == "main"

    def test_git_dir_is_dot_git(self):
        git_dir = os.popen("git rev-parse --git-dir").read().strip()
        assert git_dir == ".git", f"Expected .git, got {git_dir}"

    def test_p94_summary_recorded_p93_head(self, summary):
        # Verify the summary was generated at P93 HEAD (2221f0f), not current HEAD
        recorded_head = summary.get("git_head", "")
        assert recorded_head == "2221f0f", f"P94 summary should record P93 head 2221f0f, got {recorded_head}"

    def test_summary_gate1_ok(self, summary):
        gate1 = summary["step1_preflight"]["gate1_canonical_entry"]
        assert gate1["ok"] is True, f"Gate 1 failed: {gate1}"


# ---------------------------------------------------------------------------
# 2. Upstream artifact existence + final_classification 一致性
# ---------------------------------------------------------------------------

class TestGate3UpstreamArtifacts:
    def test_p91_exists_and_classification(self):
        p = REPO_ROOT / "data/mlb_2026/derived/p91_prediction_only_tracking_gate_summary.json"
        assert p.exists()
        with open(p) as f:
            d = json.load(f)
        assert d.get("final_classification") == "P91_TRACKING_ACTIVE_SIGNAL_STABLE"

    def test_p92_exists_and_classification(self):
        p = REPO_ROOT / "data/mlb_2026/derived/p92_prediction_only_side_bias_baseline_gate_summary.json"
        assert p.exists()
        with open(p) as f:
            d = json.load(f)
        assert d.get("final_classification") == "P92_SIGNAL_NOT_EXPLAINED_BY_SIMPLE_SIDE_BASELINE"

    def test_p93_exists_and_classification(self):
        p = REPO_ROOT / "data/mlb_2026/derived/p93_prediction_only_coverage_feature_bias_audit_summary.json"
        assert p.exists()
        with open(p) as f:
            d = json.load(f)
        assert d.get("final_classification") == "P93_SIGNAL_CONCENTRATED_IN_HIGH_FIP"

    def test_p84e_rows_exist(self):
        p = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
        assert p.exists()

    def test_p84e_attachment_summary_exists(self):
        p = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json"
        assert p.exists()

    def test_summary_gate3_ok(self, summary):
        gate3 = summary["step1_preflight"]["gate3_upstream_consistency"]
        assert gate3["ok"] is True, f"Gate 3 failed: {gate3}"


# ---------------------------------------------------------------------------
# 3. Row inventory recount vs P93 tolerance
# ---------------------------------------------------------------------------

class TestRowInventory:
    def test_row_inventory_exists(self, summary):
        assert "step2_row_inventory" in summary

    def test_n_outcome_rows(self, summary):
        inv = summary["step2_row_inventory"]
        assert abs(inv["n_outcome_rows"] - 808) <= 1, f"Expected ~808 outcome rows, got {inv['n_outcome_rows']}"

    def test_n_with_fip_delta(self, summary):
        inv = summary["step2_row_inventory"]
        assert abs(inv["n_with_sp_fip_delta"] - 808) <= 1

    def test_tolerance_ok(self, summary):
        assert summary["step2_row_inventory"]["tolerance_ok"] is True

    def test_status_passed(self, summary):
        assert summary["step2_row_inventory"]["status"] == "PASSED"


# ---------------------------------------------------------------------------
# 4. High-FIP metrics recount vs P93 step6 tolerance
# ---------------------------------------------------------------------------

class TestHighFIPMetrics:
    def test_high_fip_n(self, summary):
        m = summary["step3_high_fip_metrics"]
        assert abs(m["n"] - P93_HIGH_FIP_N) <= 1

    def test_high_fip_hit_rate_tolerance(self, summary):
        m = summary["step3_high_fip_metrics"]
        assert abs(m["hit_rate"] - P93_HIGH_FIP_HIT_RATE) <= TOLERANCE, (
            f"hit_rate {m['hit_rate']} outside tolerance of P93 {P93_HIGH_FIP_HIT_RATE}"
        )

    def test_tolerance_ok_flag(self, summary):
        assert summary["step3_high_fip_metrics"]["tolerance_ok"] is True

    def test_status_passed(self, summary):
        assert summary["step3_high_fip_metrics"]["status"] == "PASSED"

    def test_brier_range(self, summary):
        brier = summary["step3_high_fip_metrics"]["brier"]
        assert 0.0 < brier < 1.0, f"Brier out of range: {brier}"

    def test_ece_range(self, summary):
        ece = summary["step3_high_fip_metrics"]["ece"]
        assert 0.0 <= ece < 0.5, f"ECE out of range: {ece}"

    def test_predicted_home_ratio_range(self, summary):
        r = summary["step3_high_fip_metrics"]["predicted_home_ratio"]
        assert 0.0 < r < 1.0


# ---------------------------------------------------------------------------
# 5. Bootstrap CI 結果落在合理範圍
# ---------------------------------------------------------------------------

class TestBootstrapCI:
    def test_bootstrap_exists(self, summary):
        assert "step4_bootstrap_ci" in summary

    def test_ci_low_less_than_ci_high(self, summary):
        b = summary["step4_bootstrap_ci"]
        assert b["ci_low"] < b["ci_high"]

    def test_ci_contains_observed(self, summary):
        b = summary["step4_bootstrap_ci"]
        assert b["ci_low"] <= b["observed_hit_rate"] <= b["ci_high"]

    def test_observed_above_home_baseline(self, summary):
        b = summary["step4_bootstrap_ci"]
        assert b["observed_hit_rate"] > HOME_BASELINE

    def test_stability_is_valid_category(self, summary):
        b = summary["step4_bootstrap_ci"]
        assert b["stability"] in {"STRONG", "MARGINAL", "UNSTABLE"}

    def test_ci_range_reasonable(self, summary):
        b = summary["step4_bootstrap_ci"]
        assert 0.4 <= b["ci_low"] <= b["ci_high"] <= 0.8

    def test_bootstrap_resamples(self, summary):
        b = summary["step4_bootstrap_ci"]
        assert b["bootstrap_resamples"] == 1000

    def test_status_passed(self, summary):
        assert summary["step4_bootstrap_ci"]["status"] == "PASSED"


# ---------------------------------------------------------------------------
# 6. Temporal split metrics 結構正確
# ---------------------------------------------------------------------------

class TestTemporalSplit:
    def test_temporal_exists(self, summary):
        assert "step5_temporal_split" in summary

    def test_three_thirds(self, summary):
        t = summary["step5_temporal_split"]
        assert len(t["thirds"]) == 3

    def test_each_third_has_n_and_hit_rate(self, summary):
        for third in summary["step5_temporal_split"]["thirds"]:
            assert "n" in third
            assert "hit_rate" in third
            assert third["n"] > 0
            assert 0.0 < third["hit_rate"] < 1.0

    def test_total_n_matches_high_fip_n(self, summary):
        t = summary["step5_temporal_split"]
        total_n = sum(t_["n"] for t_ in t["thirds"])
        high_fip_n = summary["step3_high_fip_metrics"]["n"]
        assert abs(total_n - high_fip_n) <= 2, f"Temporal split total {total_n} != high_fip_n {high_fip_n}"

    def test_temporal_stable_is_bool(self, summary):
        t = summary["step5_temporal_split"]
        assert isinstance(t["temporal_stable"], bool)

    def test_status_passed(self, summary):
        assert summary["step5_temporal_split"]["status"] == "PASSED"


# ---------------------------------------------------------------------------
# 7. Side split metrics 結構正確
# ---------------------------------------------------------------------------

class TestSideSplit:
    def test_side_split_exists(self, summary):
        assert "step6_side_split" in summary

    def test_home_and_away_keys(self, summary):
        s = summary["step6_side_split"]
        assert "home_predicted" in s
        assert "away_predicted" in s

    def test_hit_rates_in_range(self, summary):
        s = summary["step6_side_split"]
        assert 0.0 < s["home_predicted"]["hit_rate"] < 1.0
        assert 0.0 < s["away_predicted"]["hit_rate"] < 1.0

    def test_total_n_matches(self, summary):
        s = summary["step6_side_split"]
        total = s["home_predicted"]["n"] + s["away_predicted"]["n"]
        high_n = summary["step3_high_fip_metrics"]["n"]
        assert abs(total - high_n) <= 2

    def test_abs_side_delta_non_negative(self, summary):
        s = summary["step6_side_split"]
        assert s["abs_side_delta"] >= 0.0

    def test_side_balanced_is_bool(self, summary):
        s = summary["step6_side_split"]
        assert isinstance(s["side_balanced"], bool)

    def test_status_passed(self, summary):
        assert summary["step6_side_split"]["status"] == "PASSED"


# ---------------------------------------------------------------------------
# 8. Segment qualification 邏輯
# ---------------------------------------------------------------------------

class TestSegmentQualification:
    def test_segment_qual_exists(self, summary):
        assert "step7_segment_qualification" in summary

    def test_mid_and_low_buckets(self, summary):
        s = summary["step7_segment_qualification"]
        assert "mid_bucket" in s
        assert "low_bucket" in s

    def test_qualification_valid_value(self, summary):
        s = summary["step7_segment_qualification"]
        valid = {"LOW_MID_FIP_NOT_TRACKABLE", "LOW_MID_FIP_PARTIALLY_TRACKABLE"}
        assert s["segment_qualification"] in valid, (
            f"Unexpected segment_qualification: {s['segment_qualification']}"
        )

    def test_not_trackable_path(self, summary):
        s = summary["step7_segment_qualification"]
        mid_above = s["mid_bucket"].get("above_threshold", False)
        low_above = s["low_bucket"].get("above_threshold", False)
        qual = s["segment_qualification"]
        if not mid_above and not low_above:
            assert qual == "LOW_MID_FIP_NOT_TRACKABLE"

    def test_partially_trackable_path(self, summary):
        s = summary["step7_segment_qualification"]
        mid_above = s["mid_bucket"].get("above_threshold", False)
        low_above = s["low_bucket"].get("above_threshold", False)
        qual = s["segment_qualification"]
        if mid_above or low_above:
            assert qual == "LOW_MID_FIP_PARTIALLY_TRACKABLE"

    def test_bucket_ns_positive(self, summary):
        s = summary["step7_segment_qualification"]
        assert s["mid_bucket"]["n"] > 0
        assert s["low_bucket"]["n"] > 0

    def test_status_passed(self, summary):
        assert summary["step7_segment_qualification"]["status"] == "PASSED"


# ---------------------------------------------------------------------------
# 9. Final classification 在五分類列表內
# ---------------------------------------------------------------------------

class TestFinalClassification:
    def test_final_classification_exists(self, summary):
        assert "final_classification" in summary

    def test_final_classification_valid(self, summary):
        fc = summary["final_classification"]
        assert fc in VALID_FINAL_CLASSIFICATIONS, f"Invalid classification: {fc}"

    def test_classification_rationale_present(self, summary):
        assert len(summary.get("classification_rationale", "")) > 0

    def test_allowed_classifications_complete(self, summary):
        allowed = set(summary.get("allowed_classifications", []))
        assert allowed == VALID_FINAL_CLASSIFICATIONS


# ---------------------------------------------------------------------------
# 10. Governance flags 全部正確
# ---------------------------------------------------------------------------

class TestGovernanceFlags:
    def test_governance_exists(self, summary):
        assert "step10_governance" in summary

    def test_odds_used_false(self, summary):
        assert summary["step10_governance"]["odds_used"] is False

    def test_ev_computed_false(self, summary):
        assert summary["step10_governance"]["ev_computed"] is False

    def test_clv_computed_false(self, summary):
        assert summary["step10_governance"]["clv_computed"] is False

    def test_kelly_computed_false(self, summary):
        assert summary["step10_governance"]["kelly_computed"] is False

    def test_production_ready_false(self, summary):
        assert summary["step10_governance"]["production_ready"] is False

    def test_paper_only_true(self, summary):
        assert summary["step10_governance"]["paper_only"] is True

    def test_diagnostic_only_true(self, summary):
        assert summary["step10_governance"]["diagnostic_only"] is True

    def test_live_api_calls_zero(self, summary):
        assert summary["step10_governance"]["live_api_calls"] == 0

    def test_paid_api_called_false(self, summary):
        assert summary["step10_governance"]["paid_api_called"] is False

    def test_governance_all_pass(self, summary):
        assert summary.get("governance_all_pass") is True

    def test_top_level_paper_only(self, summary):
        assert summary.get("paper_only") is True

    def test_top_level_diagnostic_only(self, summary):
        assert summary.get("diagnostic_only") is True

    def test_top_level_production_ready_false(self, summary):
        assert summary.get("production_ready") is False

    def test_governance_status_passed(self, summary):
        assert summary["step10_governance"]["status"] == "PASSED"
