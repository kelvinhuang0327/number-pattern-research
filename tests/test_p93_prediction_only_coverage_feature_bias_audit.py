"""
Tests for P93 — Prediction-Only Coverage and Feature Bias Audit Gate.

Validates:
- Infrastructure: files exist, JSON is valid
- Classification locks: P92 / P91 / P90 / P86
- Row counts: total, outcome, coverage rates
- Feature distribution: quartile counts, hit rates in range
- Bucket analysis: low/mid/high buckets present and valid
- Monthly decomposition: months present, hit rates in range
- Concentration assessment: in allowed set
- Governance flags: all correct
- Report content: no betting / EV / CLV / Kelly / stake instructions
- Final classification: in allowed list
"""

from __future__ import annotations

import json
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
REPORT_DIR = ROOT / "report"

P93_SUMMARY_PATH = DERIVED / "p93_prediction_only_coverage_feature_bias_audit_summary.json"
P93_REPORT_PATH = REPORT_DIR / "p93_prediction_only_coverage_feature_bias_audit_20260527.md"
P92_SUMMARY_PATH = DERIVED / "p92_prediction_only_side_bias_baseline_gate_summary.json"
P91_SUMMARY_PATH = DERIVED / "p91_prediction_only_tracking_gate_summary.json"
P90_SUMMARY_PATH = DERIVED / "p90_post_recovery_closure_report_summary.json"
P86_SUMMARY_PATH = DERIVED / "p86_artifact_regeneration_dependency_contract_summary.json"

ALLOWED_FINAL_CLASSIFICATIONS = [
    "P93_SIGNAL_BROADLY_DISTRIBUTED",
    "P93_SIGNAL_CONCENTRATED_IN_HIGH_FIP",
    "P93_SIGNAL_CONCENTRATED_IN_LOW_FIP",
    "P93_COVERAGE_GAP_DISTORTION",
    "P93_INSUFFICIENT_QUARTILE_EVIDENCE",
    "P93_COVERAGE_AUDIT_BLOCKED_BY_PREFLIGHT",
    "P93_COVERAGE_AUDIT_BLOCKED_BY_SCOPE_DRIFT",
]

ALLOWED_CONCENTRATION_ASSESSMENTS = [
    "SIGNAL_BROADLY_DISTRIBUTED",
    "SIGNAL_CONCENTRATED_IN_HIGH_FIP",
    "SIGNAL_CONCENTRATED_IN_LOW_FIP",
    "COVERAGE_GAP_DISTORTION",
    "INSUFFICIENT_QUARTILE_EVIDENCE",
]

TOLERANCE = 1e-4

FORBIDDEN_TERMS = [
    "bet now", "place a bet", "stake sizing recommendation", "kelly criterion",
    "expected value calculation", "closing line value", "you should bet",
    "recommended bet", "place your bet", "wager this",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def summary() -> dict:
    assert P93_SUMMARY_PATH.exists(), f"P93 summary missing: {P93_SUMMARY_PATH}"
    with open(P93_SUMMARY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def report_text() -> str:
    assert P93_REPORT_PATH.exists(), f"P93 report missing: {P93_REPORT_PATH}"
    return P93_REPORT_PATH.read_text()


@pytest.fixture(scope="module")
def p92_summary() -> dict:
    assert P92_SUMMARY_PATH.exists(), f"P92 summary missing: {P92_SUMMARY_PATH}"
    with open(P92_SUMMARY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p91_summary() -> dict:
    assert P91_SUMMARY_PATH.exists(), f"P91 summary missing: {P91_SUMMARY_PATH}"
    with open(P91_SUMMARY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p90_summary() -> dict:
    assert P90_SUMMARY_PATH.exists(), f"P90 summary missing: {P90_SUMMARY_PATH}"
    with open(P90_SUMMARY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p86_summary() -> dict:
    assert P86_SUMMARY_PATH.exists(), f"P86 summary missing: {P86_SUMMARY_PATH}"
    with open(P86_SUMMARY_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------

class TestInfrastructure:
    def test_p93_summary_exists(self):
        assert P93_SUMMARY_PATH.exists()

    def test_p93_report_exists(self):
        assert P93_REPORT_PATH.exists()

    def test_p93_summary_valid_json(self, summary):
        assert isinstance(summary, dict)

    def test_p92_summary_exists(self):
        assert P92_SUMMARY_PATH.exists()

    def test_p91_summary_exists(self):
        assert P91_SUMMARY_PATH.exists()

    def test_p90_summary_exists(self):
        assert P90_SUMMARY_PATH.exists()

    def test_p86_summary_exists(self):
        assert P86_SUMMARY_PATH.exists()


# ---------------------------------------------------------------------------
# Classification locks
# ---------------------------------------------------------------------------

class TestClassificationLocks:
    def test_p92_classification_lock(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("p92_classification") == "P92_SIGNAL_NOT_EXPLAINED_BY_SIMPLE_SIDE_BASELINE", (
            f"P92 lock failed: {lock.get('p92_classification')}"
        )

    def test_p91_classification_lock(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("p91_classification") == "P91_TRACKING_ACTIVE_SIGNAL_STABLE", (
            f"P91 lock failed: {lock.get('p91_classification')}"
        )

    def test_p90_classification_lock(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("p90_classification") == "P90_POST_RECOVERY_CLOSURE_READY", (
            f"P90 lock failed: {lock.get('p90_classification')}"
        )

    def test_p86_classification_lock(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("p86_classification") == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY", (
            f"P86 lock failed: {lock.get('p86_classification')}"
        )

    def test_all_locks_pass(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("all_ok") is True


# ---------------------------------------------------------------------------
# Row counts
# ---------------------------------------------------------------------------

class TestRowCounts:
    def test_total_rows_positive(self, summary):
        inv = summary.get("step3_row_inventory", {})
        assert inv.get("n_total_rows", 0) > 0

    def test_outcome_rows_positive(self, summary):
        inv = summary.get("step3_row_inventory", {})
        assert inv.get("n_outcome_rows", 0) > 0

    def test_outcome_rows_lte_total(self, summary):
        inv = summary.get("step3_row_inventory", {})
        assert inv.get("n_outcome_rows", 0) <= inv.get("n_total_rows", 0)

    def test_rows_with_fip_equals_outcome(self, summary):
        inv = summary.get("step3_row_inventory", {})
        assert inv.get("rows_with_sp_fip_delta", 0) == inv.get("n_outcome_rows", -1)

    def test_coverage_gap_ratio_in_range(self, summary):
        inv = summary.get("step3_row_inventory", {})
        gap = inv.get("coverage_gap_ratio", -1)
        assert 0.0 <= gap <= 1.0

    def test_rows_missing_fip_zero(self, summary):
        inv = summary.get("step3_row_inventory", {})
        assert inv.get("rows_missing_sp_fip_delta", -1) == 0


# ---------------------------------------------------------------------------
# Feature distribution
# ---------------------------------------------------------------------------

class TestFeatureDistribution:
    def test_feature_distribution_present(self, summary):
        dist = summary.get("step4_feature_distribution", {})
        assert dist.get("n_with_fip", 0) > 0

    def test_abs_fip_min_non_negative(self, summary):
        dist = summary.get("step4_feature_distribution", {})
        assert dist.get("abs_sp_fip_delta_min", -1) >= 0.0

    def test_abs_fip_max_positive(self, summary):
        dist = summary.get("step4_feature_distribution", {})
        assert dist.get("abs_sp_fip_delta_max", 0) > 0.0

    def test_abs_fip_mean_positive(self, summary):
        dist = summary.get("step4_feature_distribution", {})
        assert dist.get("abs_sp_fip_delta_mean", 0) > 0.0


# ---------------------------------------------------------------------------
# Quartile decomposition
# ---------------------------------------------------------------------------

class TestQuartileDecomposition:
    def test_four_quartiles_present(self, summary):
        qd = summary.get("step5_quartile_decomposition", {})
        assert len(qd.get("quartiles", [])) == 4

    def test_all_quartiles_sufficient(self, summary):
        qd = summary.get("step5_quartile_decomposition", {})
        assert qd.get("all_quartiles_sufficient") is True

    def test_quartile_hit_rates_in_range(self, summary):
        qd = summary.get("step5_quartile_decomposition", {})
        for q in qd.get("quartiles", []):
            assert 0.0 <= q["model_hit_rate"] <= 1.0
            assert 0.0 <= q["home_baseline_hit_rate"] <= 1.0
            assert 0.0 <= q["away_baseline_hit_rate"] <= 1.0

    def test_quartile_baseline_sum_approx_one(self, summary):
        qd = summary.get("step5_quartile_decomposition", {})
        for q in qd.get("quartiles", []):
            total = q["home_baseline_hit_rate"] + q["away_baseline_hit_rate"]
            assert abs(total - 1.0) < TOLERANCE

    def test_quartile_labels_are_q1_to_q4(self, summary):
        qd = summary.get("step5_quartile_decomposition", {})
        labels = [q["quartile"] for q in qd.get("quartiles", [])]
        assert labels == ["Q1", "Q2", "Q3", "Q4"]


# ---------------------------------------------------------------------------
# Bucket analysis
# ---------------------------------------------------------------------------

class TestBucketAnalysis:
    def test_low_bucket_present(self, summary):
        ba = summary.get("step6_bucket_analysis", {})
        assert ba.get("low_bucket", {}).get("n", 0) > 0

    def test_high_bucket_present(self, summary):
        ba = summary.get("step6_bucket_analysis", {})
        assert ba.get("high_bucket", {}).get("n", 0) > 0

    def test_low_hit_rate_in_range(self, summary):
        ba = summary.get("step6_bucket_analysis", {})
        r = ba.get("low_fip_delta_hit_rate")
        if r is not None:
            assert 0.0 <= r <= 1.0

    def test_high_hit_rate_in_range(self, summary):
        ba = summary.get("step6_bucket_analysis", {})
        r = ba.get("high_fip_delta_hit_rate")
        if r is not None:
            assert 0.0 <= r <= 1.0

    def test_mid_hit_rate_in_range(self, summary):
        ba = summary.get("step6_bucket_analysis", {})
        r = ba.get("mid_fip_delta_hit_rate")
        if r is not None:
            assert 0.0 <= r <= 1.0


# ---------------------------------------------------------------------------
# Monthly bucket decomposition
# ---------------------------------------------------------------------------

class TestMonthlyBucketDecomposition:
    def test_monthly_results_present(self, summary):
        mb = summary.get("step7_monthly_bucket", {})
        assert mb.get("n_months", 0) > 0
        assert len(mb.get("monthly_results", [])) > 0

    def test_monthly_model_hit_rates_in_range(self, summary):
        mb = summary.get("step7_monthly_bucket", {})
        for m in mb.get("monthly_results", []):
            assert 0.0 <= m["model_hit_rate"] <= 1.0

    def test_monthly_low_hit_rates_in_range(self, summary):
        mb = summary.get("step7_monthly_bucket", {})
        for m in mb.get("monthly_results", []):
            if m.get("low_hit_rate") is not None:
                assert 0.0 <= m["low_hit_rate"] <= 1.0

    def test_monthly_high_hit_rates_in_range(self, summary):
        mb = summary.get("step7_monthly_bucket", {})
        for m in mb.get("monthly_results", []):
            if m.get("high_hit_rate") is not None:
                assert 0.0 <= m["high_hit_rate"] <= 1.0


# ---------------------------------------------------------------------------
# Concentration assessment
# ---------------------------------------------------------------------------

class TestConcentrationAssessment:
    def test_concentration_assessment_allowed(self, summary):
        conc = summary.get("step8_concentration_assessment", {})
        assessment = conc.get("feature_concentration_assessment")
        assert assessment in ALLOWED_CONCENTRATION_ASSESSMENTS, (
            f"feature_concentration_assessment '{assessment}' not in allowed set"
        )

    def test_coverage_gap_ratio_in_range(self, summary):
        conc = summary.get("step8_concentration_assessment", {})
        gap = conc.get("coverage_gap_ratio", -1)
        assert 0.0 <= gap <= 1.0

    def test_quartile_hit_rates_in_range(self, summary):
        conc = summary.get("step8_concentration_assessment", {})
        for hr in conc.get("quartile_hit_rates", []):
            assert 0.0 <= hr <= 1.0

    def test_low_fip_hit_rate_in_range(self, summary):
        conc = summary.get("step8_concentration_assessment", {})
        r = conc.get("low_fip_hit_rate")
        if r is not None:
            assert 0.0 <= r <= 1.0

    def test_high_fip_hit_rate_in_range(self, summary):
        conc = summary.get("step8_concentration_assessment", {})
        r = conc.get("high_fip_hit_rate")
        if r is not None:
            assert 0.0 <= r <= 1.0


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

class TestGovernance:
    def test_paper_only_true(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("paper_only") is True

    def test_diagnostic_only_true(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("diagnostic_only") is True

    def test_production_ready_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("production_ready") is False

    def test_odds_used_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("odds_used") is False

    def test_ev_computed_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("ev_computed") is False

    def test_clv_computed_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("clv_computed") is False

    def test_kelly_computed_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("kelly_computed") is False

    def test_live_api_calls_zero(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("live_api_calls") == 0

    def test_paid_api_called_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("paid_api_called") is False

    def test_no_champion_replacement(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("no_champion_replacement") is True

    def test_no_runtime_recommendation_mutation(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("no_runtime_recommendation_mutation") is True

    def test_no_production_betting_recommendation(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("no_production_betting_recommendation") is True

    def test_no_taiwan_lottery_betting_recommendation(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("no_taiwan_lottery_betting_recommendation") is True

    def test_no_calibration_refit(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("no_calibration_refit") is True

    def test_no_model_retraining(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p93_governance", {})
        assert gov.get("no_model_retraining") is True

    def test_governance_all_pass(self, summary):
        assert summary.get("governance_all_pass") is True

    def test_top_level_production_ready_false(self, summary):
        assert summary.get("production_ready") is False


# ---------------------------------------------------------------------------
# Report content
# ---------------------------------------------------------------------------

class TestReportContent:
    def test_no_betting_instructions(self, report_text):
        lower = report_text.lower()
        for term in FORBIDDEN_TERMS:
            assert term not in lower, (
                f"Forbidden term '{term}' found in report"
            )

    def test_no_ev_clv_kelly(self, report_text):
        lower = report_text.lower()
        for term in ["expected value calculation", "kelly criterion", "closing line value"]:
            assert term not in lower

    def test_no_stake_recommendation(self, report_text):
        lower = report_text.lower()
        assert "stake sizing" not in lower or "no stake" in lower

    def test_report_contains_classification(self, report_text, summary):
        cls = summary.get("final_classification", "")
        assert cls in report_text

    def test_report_contains_disclaimer(self, report_text):
        lower = report_text.lower()
        assert "diagnostic" in lower or "paper" in lower or "not investment" in lower


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

class TestFinalClassification:
    def test_final_classification_allowed(self, summary):
        cls = summary.get("final_classification")
        assert cls in ALLOWED_FINAL_CLASSIFICATIONS, (
            f"final_classification '{cls}' not in allowed list"
        )

    def test_final_classification_consistent(self, summary):
        assert summary.get("final_classification") == summary.get("p93_classification")
