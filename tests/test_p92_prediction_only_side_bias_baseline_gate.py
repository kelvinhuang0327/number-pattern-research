"""
Tests for P92 — Prediction-Only Side Bias and Baseline Decomposition Gate.

Validates:
- Infrastructure: files exist, JSON is valid
- Classification locks: P91 / P90 / P86
- Row counts: total, outcome, side split integrity
- Ratios: predicted_home_ratio + predicted_away_ratio = 1.0
- Metrics: hit rates, AUC, deltas all in valid ranges
- Side bias assessment: in allowed set
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

P92_SUMMARY_PATH = DERIVED / "p92_prediction_only_side_bias_baseline_gate_summary.json"
P92_REPORT_PATH = REPORT_DIR / "p92_prediction_only_side_bias_baseline_gate_20260527.md"
P91_SUMMARY_PATH = DERIVED / "p91_prediction_only_tracking_gate_summary.json"
P90_SUMMARY_PATH = DERIVED / "p90_post_recovery_closure_report_summary.json"
P86_SUMMARY_PATH = DERIVED / "p86_artifact_regeneration_dependency_contract_summary.json"

ALLOWED_FINAL_CLASSIFICATIONS = [
    "P92_SIGNAL_NOT_EXPLAINED_BY_SIMPLE_SIDE_BASELINE",
    "P92_HOME_BASELINE_CONFOUNDED",
    "P92_AWAY_BASELINE_CONFOUNDED",
    "P92_INSUFFICIENT_SIDE_SPLIT_EVIDENCE",
    "P92_SIDE_BIAS_GATE_BLOCKED_BY_PREFLIGHT",
    "P92_SIDE_BIAS_GATE_BLOCKED_BY_SCOPE_DRIFT",
]

ALLOWED_SIDE_BIAS_ASSESSMENTS = [
    "SIGNAL_NOT_EXPLAINED_BY_SIMPLE_SIDE_BASELINE",
    "HOME_BASELINE_CONFOUNDED",
    "AWAY_BASELINE_CONFOUNDED",
    "INSUFFICIENT_SIDE_SPLIT_EVIDENCE",
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
    assert P92_SUMMARY_PATH.exists(), f"P92 summary missing: {P92_SUMMARY_PATH}"
    with open(P92_SUMMARY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def report_text() -> str:
    assert P92_REPORT_PATH.exists(), f"P92 report missing: {P92_REPORT_PATH}"
    return P92_REPORT_PATH.read_text()


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
    def test_p92_summary_exists(self):
        assert P92_SUMMARY_PATH.exists()

    def test_p92_report_exists(self):
        assert P92_REPORT_PATH.exists()

    def test_p92_summary_valid_json(self, summary):
        assert isinstance(summary, dict)

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
    def test_p91_classification_lock(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("p91_classification") == "P91_TRACKING_ACTIVE_SIGNAL_STABLE", (
            f"P91 classification lock failed: {lock.get('p91_classification')}"
        )

    def test_p90_classification_lock(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("p90_classification") == "P90_POST_RECOVERY_CLOSURE_READY", (
            f"P90 classification lock failed: {lock.get('p90_classification')}"
        )

    def test_p86_classification_lock(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("p86_classification") == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY", (
            f"P86 classification lock failed: {lock.get('p86_classification')}"
        )

    def test_all_locks_pass(self, summary):
        lock = summary.get("step2_classification_locks", {})
        assert lock.get("all_ok") is True


# ---------------------------------------------------------------------------
# Row counts
# ---------------------------------------------------------------------------

class TestRowCounts:
    def test_total_rows_positive(self, summary):
        inv = summary.get("step3_load_rows", {})
        assert inv.get("n_total_rows", 0) > 0

    def test_outcome_rows_positive(self, summary):
        inv = summary.get("step3_load_rows", {})
        assert inv.get("n_outcome_rows", 0) > 0

    def test_outcome_rows_lte_total(self, summary):
        inv = summary.get("step3_load_rows", {})
        assert inv.get("n_outcome_rows", 0) <= inv.get("n_total_rows", 0)

    def test_home_plus_away_equals_outcome(self, summary):
        dist = summary.get("step4_side_distribution", {})
        outcome_n = summary.get("step3_load_rows", {}).get("n_outcome_rows", -1)
        home_c = dist.get("predicted_home_count", 0)
        away_c = dist.get("predicted_away_count", 0)
        assert home_c + away_c == outcome_n, (
            f"home ({home_c}) + away ({away_c}) != outcome_rows ({outcome_n})"
        )

    def test_side_split_counts_consistent(self, summary):
        dist = summary.get("step4_side_distribution", {})
        split = summary.get("step6_side_split", {})
        assert dist.get("predicted_home_count") == split.get("home_predicted_count")
        assert dist.get("predicted_away_count") == split.get("away_predicted_count")


# ---------------------------------------------------------------------------
# Ratios
# ---------------------------------------------------------------------------

class TestRatios:
    def test_predicted_home_ratio_in_range(self, summary):
        r = summary.get("step4_side_distribution", {}).get("predicted_home_ratio", -1)
        assert 0.0 <= r <= 1.0

    def test_predicted_away_ratio_in_range(self, summary):
        r = summary.get("step4_side_distribution", {}).get("predicted_away_ratio", -1)
        assert 0.0 <= r <= 1.0

    def test_ratios_sum_to_one(self, summary):
        dist = summary.get("step4_side_distribution", {})
        total = dist.get("predicted_home_ratio", 0) + dist.get("predicted_away_ratio", 0)
        assert abs(total - 1.0) < TOLERANCE


# ---------------------------------------------------------------------------
# Hit rates and metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_home_baseline_hit_rate_in_range(self, summary):
        r = summary.get("step5_baseline_comparison", {}).get("home_baseline_hit_rate", -1)
        assert 0.0 <= r <= 1.0

    def test_away_baseline_hit_rate_in_range(self, summary):
        r = summary.get("step5_baseline_comparison", {}).get("away_baseline_hit_rate", -1)
        assert 0.0 <= r <= 1.0

    def test_model_hit_rate_in_range(self, summary):
        r = summary.get("step5_baseline_comparison", {}).get("model_hit_rate", -1)
        assert 0.0 <= r <= 1.0

    def test_model_auc_in_range(self, summary):
        auc = summary.get("p91_metrics", {}).get("auc")
        if auc is not None:
            assert 0.0 <= auc <= 1.0

    def test_model_vs_home_baseline_delta_is_numeric(self, summary):
        d = summary.get("step5_baseline_comparison", {}).get("model_vs_home_baseline_delta")
        assert isinstance(d, float)

    def test_model_vs_away_baseline_delta_is_numeric(self, summary):
        d = summary.get("step5_baseline_comparison", {}).get("model_vs_away_baseline_delta")
        assert isinstance(d, float)

    def test_home_predicted_hit_rate_in_range(self, summary):
        r = summary.get("step6_side_split", {}).get("home_predicted_hit_rate")
        if r is not None:
            assert 0.0 <= r <= 1.0

    def test_away_predicted_hit_rate_in_range(self, summary):
        r = summary.get("step6_side_split", {}).get("away_predicted_hit_rate")
        if r is not None:
            assert 0.0 <= r <= 1.0

    def test_home_away_baselines_sum_approx_one(self, summary):
        base = summary.get("step5_baseline_comparison", {})
        total = base.get("home_baseline_hit_rate", 0) + base.get("away_baseline_hit_rate", 0)
        assert abs(total - 1.0) < TOLERANCE


# ---------------------------------------------------------------------------
# Monthly decomposition
# ---------------------------------------------------------------------------

class TestMonthlyDecomposition:
    def test_monthly_results_present(self, summary):
        monthly = summary.get("step7_monthly_decomposition", {})
        assert monthly.get("n_months", 0) > 0
        assert len(monthly.get("monthly_results", [])) > 0

    def test_monthly_hit_rates_in_range(self, summary):
        monthly = summary.get("step7_monthly_decomposition", {})
        for m in monthly.get("monthly_results", []):
            assert 0.0 <= m["model_hit_rate"] <= 1.0
            assert 0.0 <= m["home_baseline_hit_rate"] <= 1.0
            assert 0.0 <= m["away_baseline_hit_rate"] <= 1.0


# ---------------------------------------------------------------------------
# Side bias assessment
# ---------------------------------------------------------------------------

class TestSideBiasAssessment:
    def test_side_bias_assessment_allowed(self, summary):
        bias = summary.get("step8_side_bias_assessment", {})
        assessment = bias.get("side_bias_assessment")
        assert assessment in ALLOWED_SIDE_BIAS_ASSESSMENTS, (
            f"side_bias_assessment '{assessment}' not in allowed set"
        )


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

class TestGovernance:
    def test_paper_only_true(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("paper_only") is True

    def test_diagnostic_only_true(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("diagnostic_only") is True

    def test_production_ready_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("production_ready") is False

    def test_odds_used_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("odds_used") is False

    def test_ev_computed_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("ev_computed") is False

    def test_clv_computed_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("clv_computed") is False

    def test_kelly_computed_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("kelly_computed") is False

    def test_live_api_calls_zero(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("live_api_calls") == 0

    def test_paid_api_called_false(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("paid_api_called") is False

    def test_no_champion_replacement(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("no_champion_replacement") is True

    def test_no_runtime_recommendation_mutation(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("no_runtime_recommendation_mutation") is True

    def test_no_production_betting_recommendation(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("no_production_betting_recommendation") is True

    def test_no_taiwan_lottery_betting_recommendation(self, summary):
        gov = summary.get("step9_governance_scan", {}).get("p92_governance", {})
        assert gov.get("no_taiwan_lottery_betting_recommendation") is True

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
        assert summary.get("final_classification") == summary.get("p92_classification")
