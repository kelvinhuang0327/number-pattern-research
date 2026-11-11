"""
Tests for P91 — Prediction-Only Tracking Gate.

Validates:
- Infrastructure: files exist, JSON is valid
- Phase chain locks: P90 / P86 / P84H classifications
- Tracking metrics: n_rows_tracked, hit_rate, coverage_rate, production_ready
- Governance scan: all 20 flags correct, all checks True
- Final classification: in allowed list
- Report content: no betting / EV / CLV / Kelly / stake instructions
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

P91_SUMMARY_PATH = DERIVED / "p91_prediction_only_tracking_gate_summary.json"
P91_REPORT_PATH = REPORT_DIR / "p91_prediction_only_tracking_gate_20260527.md"
P90_SUMMARY_PATH = DERIVED / "p90_post_recovery_closure_report_summary.json"
P86_SUMMARY_PATH = DERIVED / "p86_artifact_regeneration_dependency_contract_summary.json"
P84H_SUMMARY_PATH = DERIVED / "p84h_corrected_signal_validation_coverage_guard_summary.json"
ACTIVE_TASK_PATH = ROOT / "00-Plan" / "roadmap" / "active_task.md"

ALLOWED_FINAL_CLASSIFICATIONS = [
    "P91_TRACKING_ACTIVE_SIGNAL_STABLE",
    "P91_TRACKING_ACTIVE_SIGNAL_TRENDING",
    "P91_TRACKING_ACTIVE_INSUFFICIENT_DATA",
    "P91_TRACKING_BLOCKED_BY_PREFLIGHT",
    "P91_TRACKING_BLOCKED_BY_SCOPE_DRIFT",
]

TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def summary() -> dict:
    assert P91_SUMMARY_PATH.exists(), f"P91 summary not found: {P91_SUMMARY_PATH}"
    return json.loads(P91_SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p90_summary() -> dict:
    assert P90_SUMMARY_PATH.exists(), f"P90 summary not found: {P90_SUMMARY_PATH}"
    return json.loads(P90_SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p86_summary() -> dict:
    assert P86_SUMMARY_PATH.exists(), f"P86 summary not found: {P86_SUMMARY_PATH}"
    return json.loads(P86_SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p84h_summary() -> dict:
    assert P84H_SUMMARY_PATH.exists(), f"P84H summary not found: {P84H_SUMMARY_PATH}"
    return json.loads(P84H_SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report_text() -> str:
    assert P91_REPORT_PATH.exists(), f"P91 report not found: {P91_REPORT_PATH}"
    return P91_REPORT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def metrics(summary) -> dict:
    return summary["tracking_metrics"]


@pytest.fixture(scope="module")
def governance(summary) -> dict:
    return summary["governance_status"]


# ---------------------------------------------------------------------------
# TestInfrastructure
# ---------------------------------------------------------------------------

class TestInfrastructure:
    """Files exist and JSON is parseable."""

    def test_p91_summary_exists(self):
        assert P91_SUMMARY_PATH.exists(), "P91 summary JSON missing"

    def test_p91_report_exists(self):
        assert P91_REPORT_PATH.exists(), "P91 report Markdown missing"

    def test_p91_summary_valid_json(self):
        raw = P91_SUMMARY_PATH.read_text(encoding="utf-8")
        obj = json.loads(raw)
        assert isinstance(obj, dict), "Summary is not a JSON object"

    def test_p91_report_not_empty(self):
        txt = P91_REPORT_PATH.read_text(encoding="utf-8")
        assert len(txt.strip()) > 100, "Report content too short"

    def test_p91_script_exists(self):
        script = ROOT / "scripts" / "_p91_prediction_only_tracking_gate.py"
        assert script.exists(), "P91 script missing"

    def test_p91_summary_has_p91_classification(self, summary):
        assert "p91_classification" in summary, "p91_classification key missing"

    def test_p91_summary_has_tracking_metrics(self, summary):
        assert "tracking_metrics" in summary, "tracking_metrics key missing"

    def test_p91_summary_has_governance_status(self, summary):
        assert "governance_status" in summary, "governance_status key missing"


# ---------------------------------------------------------------------------
# TestPhaseChainLocks
# ---------------------------------------------------------------------------

class TestPhaseChainLocks:
    """Upstream phase chain classifications are locked."""

    def test_p90_classification_lock(self, summary):
        cls = summary.get("upstream_state", {}).get("p90_classification")
        assert cls == "P90_POST_RECOVERY_CLOSURE_READY", (
            f"P90 classification mismatch: {cls!r}"
        )

    def test_p86_classification_lock(self, summary):
        cls = summary.get("upstream_state", {}).get("p86_classification")
        assert cls == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY", (
            f"P86 classification mismatch: {cls!r}"
        )

    def test_p84h_classification_lock(self, summary):
        cls = summary.get("upstream_state", {}).get("p84h_classification")
        assert cls == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED", (
            f"P84H classification mismatch: {cls!r}"
        )

    def test_p90_ok_is_true(self, summary):
        assert summary.get("upstream_state", {}).get("p90_ok") is True

    def test_p86_ok_is_true(self, summary):
        assert summary.get("upstream_state", {}).get("p86_ok") is True

    def test_p84h_ok_is_true(self, summary):
        assert summary.get("upstream_state", {}).get("p84h_ok") is True

    def test_p90_direct_summary_lock(self, p90_summary):
        cls = p90_summary.get("p90_classification") or p90_summary.get("final_classification")
        assert cls == "P90_POST_RECOVERY_CLOSURE_READY", f"Direct P90 summary mismatch: {cls!r}"

    def test_p86_direct_summary_lock(self, p86_summary):
        cls = p86_summary.get("p86_classification")
        assert cls == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY", (
            f"Direct P86 summary mismatch: {cls!r}"
        )

    def test_p84h_direct_summary_lock(self, p84h_summary):
        cls = p84h_summary.get("p84h_classification")
        assert cls == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED", (
            f"Direct P84H summary mismatch: {cls!r}"
        )


# ---------------------------------------------------------------------------
# TestTrackingMetrics
# ---------------------------------------------------------------------------

class TestTrackingMetrics:
    """Tracking metric types and constraints."""

    def test_n_rows_tracked_is_int(self, metrics):
        assert isinstance(metrics["n_rows_tracked"], int), "n_rows_tracked must be int"

    def test_n_rows_tracked_nonnegative(self, metrics):
        assert metrics["n_rows_tracked"] >= 0, "n_rows_tracked must be ≥ 0"

    def test_n_correct_is_int(self, metrics):
        assert isinstance(metrics["n_correct"], int), "n_correct must be int"

    def test_n_correct_lte_n_rows_tracked(self, metrics):
        assert metrics["n_correct"] <= metrics["n_rows_tracked"], (
            "n_correct must be ≤ n_rows_tracked"
        )

    def test_hit_rate_is_float(self, metrics):
        assert isinstance(metrics["hit_rate"], float), "hit_rate must be float"

    def test_hit_rate_between_0_and_1(self, metrics):
        hr = metrics["hit_rate"]
        assert 0.0 <= hr <= 1.0, f"hit_rate out of range: {hr}"

    def test_coverage_rate_is_float(self, metrics):
        assert isinstance(metrics["coverage_rate"], float), "coverage_rate must be float"

    def test_coverage_rate_between_0_and_1(self, metrics):
        cr = metrics["coverage_rate"]
        assert 0.0 <= cr <= 1.0, f"coverage_rate out of range: {cr}"

    def test_production_ready_is_false(self, metrics):
        assert metrics["production_ready"] is False, "production_ready must be False"

    def test_signal_stability_assessment_valid(self, metrics):
        valid = {"STABLE", "TRENDING", "INSUFFICIENT_DATA"}
        actual = metrics["signal_stability_assessment"]
        assert actual in valid, f"signal_stability_assessment invalid: {actual!r}"

    def test_n_total_rows_positive(self, metrics):
        assert metrics["n_total_rows"] > 0, "n_total_rows must be > 0"

    def test_n_auc_eligible_nonnegative(self, metrics):
        assert metrics["n_auc_eligible"] >= 0, "n_auc_eligible must be ≥ 0"

    def test_auc_none_or_float_in_range(self, metrics):
        auc = metrics.get("auc")
        if auc is not None:
            assert isinstance(auc, float), f"auc must be float or None, got {type(auc)}"
            assert 0.0 <= auc <= 1.0, f"auc out of [0,1]: {auc}"

    # --- actual numeric values (guarded by tolerance) ---

    def test_n_rows_tracked_value(self, metrics):
        assert metrics["n_rows_tracked"] == 808, (
            f"Expected 808, got {metrics['n_rows_tracked']}"
        )

    def test_hit_rate_value(self, metrics):
        assert abs(metrics["hit_rate"] - 0.569307) < TOLERANCE, (
            f"hit_rate out of tolerance: {metrics['hit_rate']}"
        )

    def test_coverage_rate_value(self, metrics):
        assert abs(metrics["coverage_rate"] - 0.975845) < TOLERANCE, (
            f"coverage_rate out of tolerance: {metrics['coverage_rate']}"
        )

    def test_auc_value_if_computable(self, metrics):
        if metrics["auc_computable"]:
            assert abs(metrics["auc"] - 0.594315) < TOLERANCE, (
                f"auc out of tolerance: {metrics['auc']}"
            )


# ---------------------------------------------------------------------------
# TestGovernanceScan
# ---------------------------------------------------------------------------

class TestGovernanceScan:
    """All 20 governance flags and their checks."""

    def test_governance_all_pass_is_true(self, summary):
        assert summary["governance_all_pass"] is True, "governance_all_pass must be True"

    def test_n_flags_equals_20(self, governance):
        assert governance["n_flags"] == 20, f"Expected 20 flags, got {governance['n_flags']}"

    def test_paper_only_true(self, governance):
        assert governance["p91_governance"]["paper_only"] is True

    def test_diagnostic_only_true(self, governance):
        assert governance["p91_governance"]["diagnostic_only"] is True

    def test_production_ready_false(self, governance):
        assert governance["p91_governance"]["production_ready"] is False

    def test_no_real_bet_true(self, governance):
        assert governance["p91_governance"]["no_real_bet"] is True

    def test_odds_used_false(self, governance):
        assert governance["p91_governance"]["odds_used"] is False

    def test_ev_computed_false(self, governance):
        assert governance["p91_governance"]["ev_computed"] is False

    def test_clv_computed_false(self, governance):
        assert governance["p91_governance"]["clv_computed"] is False

    def test_kelly_computed_false(self, governance):
        assert governance["p91_governance"]["kelly_computed"] is False

    def test_live_api_calls_zero(self, governance):
        assert governance["p91_governance"]["live_api_calls"] == 0

    def test_paid_api_called_false(self, governance):
        assert governance["p91_governance"]["paid_api_called"] is False

    def test_no_champion_replacement_true(self, governance):
        assert governance["p91_governance"]["no_champion_replacement"] is True

    def test_no_runtime_recommendation_mutation_true(self, governance):
        assert governance["p91_governance"]["no_runtime_recommendation_mutation"] is True

    def test_no_production_betting_recommendation_true(self, governance):
        assert governance["p91_governance"]["no_production_betting_recommendation"] is True

    def test_no_taiwan_lottery_betting_recommendation_true(self, governance):
        assert governance["p91_governance"]["no_taiwan_lottery_betting_recommendation"] is True

    def test_no_calibration_refit_true(self, governance):
        assert governance["p91_governance"]["no_calibration_refit"] is True

    def test_no_model_retraining_true(self, governance):
        assert governance["p91_governance"]["no_model_retraining"] is True

    def test_no_canonical_rows_modification_true(self, governance):
        assert governance["p91_governance"]["no_canonical_rows_modification"] is True

    def test_no_raw_data_modification_true(self, governance):
        assert governance["p91_governance"]["no_raw_data_modification"] is True

    def test_no_historical_artifact_overwrite_true(self, governance):
        assert governance["p91_governance"]["no_historical_artifact_overwrite"] is True

    def test_scope_within_whitelist_true(self, governance):
        assert governance["p91_governance"]["scope_within_whitelist"] is True

    def test_all_governance_checks_are_true(self, governance):
        checks = governance["governance_checks"]
        failed = [k for k, v in checks.items() if not v]
        assert not failed, f"Governance checks failed: {failed}"


# ---------------------------------------------------------------------------
# TestFinalClassification
# ---------------------------------------------------------------------------

class TestFinalClassification:
    """Final classification is valid and in allowed list."""

    def test_p91_classification_in_allowed_list(self, summary):
        cls = summary["p91_classification"]
        assert cls in ALLOWED_FINAL_CLASSIFICATIONS, (
            f"Classification {cls!r} not in allowed list"
        )

    def test_final_classification_matches_p91_classification(self, summary):
        assert summary["final_classification"] == summary["p91_classification"], (
            "final_classification and p91_classification must match"
        )

    def test_classification_is_string(self, summary):
        assert isinstance(summary["p91_classification"], str), (
            "p91_classification must be string"
        )

    def test_classification_starts_with_p91(self, summary):
        assert summary["p91_classification"].startswith("P91_"), (
            "classification must start with P91_"
        )


# ---------------------------------------------------------------------------
# TestReportNoBettingContent
# ---------------------------------------------------------------------------

class TestReportNoBettingContent:
    """Report must not contain betting instructions, EV/CLV/Kelly/stake guidance."""

    FORBIDDEN_PHRASES = [
        "下注建議",
        "投注建議",
        "賠率建議",
        "建議下注",
        "建議投注",
        "購買",
        "stake",
        "Expected Value",
        "Closing Line Value",
        "Kelly criterion",
        "kelly criterion",
        "Kelly Criterion",
        "bet on",
        "place a bet",
        "recommend betting",
        "Taiwan Lottery recommendation",
        "台灣運彩建議",
        "運彩建議",
    ]

    def test_report_no_betting_instruction(self, report_text):
        forbidden = ["下注建議", "投注建議", "賠率建議", "建議下注", "建議投注"]
        hits = [p for p in forbidden if p in report_text]
        assert not hits, f"Report contains forbidden betting phrases: {hits}"

    def test_report_no_ev_instruction(self, report_text):
        # "Expected Value" or "EV" as instruction is forbidden; however "EV computed: False" is fine
        assert "ev_computed" not in report_text or "ev_computed: `False`" in report_text
        # No positive EV recommendation
        assert "positive EV" not in report_text.lower()

    def test_report_no_clv_instruction(self, report_text):
        assert "Closing Line Value" not in report_text
        assert "CLV recommendation" not in report_text

    def test_report_no_kelly_instruction(self, report_text):
        assert "kelly criterion" not in report_text.lower() or "kelly_computed" in report_text

    def test_report_no_stake_sizing(self, report_text):
        # Only flag positive stake sizing instructions, not disclaimer context
        forbidden_stake = ["bet size", "unit size", "position size", "stake sizing recommendation"]
        hits = [p for p in forbidden_stake if p.lower() in report_text.lower()]
        assert not hits, f"Report contains stake sizing instruction: {hits}"

    def test_report_no_taiwan_lottery_recommendation(self, report_text):
        forbidden = ["台灣運彩建議", "運彩建議", "Taiwan Lottery recommendation"]
        hits = [p for p in forbidden if p in report_text]
        assert not hits, f"Report contains Taiwan lottery recommendation: {hits}"

    def test_report_no_bet_on_instruction(self, report_text):
        assert "bet on" not in report_text.lower()
        assert "place a bet" not in report_text.lower()

    def test_report_has_paper_only_disclaimer(self, report_text):
        assert "paper" in report_text.lower(), "Report must reference 'paper' (paper-only)"

    def test_report_has_diagnostic_only(self, report_text):
        assert "diagnostic" in report_text.lower(), (
            "Report must reference 'diagnostic' (diagnostic-only mode)"
        )

    def test_report_has_no_production_betting(self, report_text):
        assert "No production betting recommendation" in report_text or \
               "no production betting" in report_text.lower() or \
               "no_production_betting_recommendation" in report_text


# ---------------------------------------------------------------------------
# TestActiveTaskMarker
# ---------------------------------------------------------------------------

class TestActiveTaskMarker:
    """active_task.md has P91 marker."""

    def test_active_task_has_p91_marker(self):
        assert ACTIVE_TASK_PATH.exists(), "active_task.md missing"
        txt = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
        assert "P91" in txt, "P91 marker missing from active_task.md"

    def test_active_task_p90_marker_still_present(self):
        txt = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
        assert "P90" in txt, "P90 marker must still be present in active_task.md"


# ---------------------------------------------------------------------------
# TestTemporalTrend
# ---------------------------------------------------------------------------

class TestTemporalTrend:
    """Temporal trend data is structurally valid."""

    def test_temporal_trend_present(self, summary):
        assert "temporal_trend" in summary, "temporal_trend missing from summary"

    def test_n_months_tracked_is_int(self, summary):
        n = summary["temporal_trend"]["n_months_tracked"]
        assert isinstance(n, int) and n >= 0, f"n_months_tracked invalid: {n}"

    def test_monthly_hit_rates_is_list(self, summary):
        mhr = summary["temporal_trend"]["monthly_hit_rates"]
        assert isinstance(mhr, list), "monthly_hit_rates must be a list"

    def test_monthly_entries_have_required_keys(self, summary):
        for entry in summary["temporal_trend"]["monthly_hit_rates"]:
            assert "month" in entry, f"monthly entry missing 'month': {entry}"
            assert "n" in entry, f"monthly entry missing 'n': {entry}"
            assert "hit_rate" in entry, f"monthly entry missing 'hit_rate': {entry}"

    def test_monthly_hit_rates_in_range(self, summary):
        for entry in summary["temporal_trend"]["monthly_hit_rates"]:
            hr = entry["hit_rate"]
            assert 0.0 <= hr <= 1.0, f"monthly hit_rate out of range: {entry}"
