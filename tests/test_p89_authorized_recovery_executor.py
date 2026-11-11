"""
Tests for P89 — Authorized Recovery Executor

P89 executes the authorized recovery sequence (P84E→P84F→P84G→P84H→P85→P86)
following P88 authorization gate passage.

Expected classification: P89_RECOVERY_COMPLETE_CONTRACT_RESTORED
"""

from __future__ import annotations

import json
import math
import pathlib

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p89_authorized_recovery_executor_summary.json"
REPORT_PATH  = ROOT / "report/p89_authorized_recovery_executor_20260527.md"
SCRIPT_PATH  = ROOT / "scripts/_p89_authorized_recovery_executor.py"
ACTIVE_TASK  = ROOT / "00-Plan/roadmap/active_task.md"

ALLOWED_CLASSIFICATIONS = [
    "P89_RECOVERY_COMPLETE_CONTRACT_RESTORED",
    "P89_RECOVERY_PARTIAL_UPSTREAM_FAILED",
    "P89_RECOVERY_COMPLETE_METRICS_DRIFT_DETECTED",
    "P89_AUTHORIZATION_MISMATCH",
]

EXPECTED_CLASSIFICATION = "P89_RECOVERY_COMPLETE_CONTRACT_RESTORED"
EXPECTED_P86_POST = "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"
REQUIRED_PHRASE = "YES regenerate stale downstream artifacts for P87 recovery"

BASELINE_METRICS = {
    "hit_rate": 0.569307,
    "auc":      0.594315,
    "brier":    0.249408,
    "ece":      0.069682,
}
TOLERANCE = 1e-4

RECOVERY_SEQUENCE = ["P84E", "P84F", "P84G", "P84H", "P85", "P86"]

EXPECTED_PHASE_CLASSIFICATIONS = {
    "P84E": "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS",
    "P84F": "P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK",
    "P84G": "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED",
    "P84H": "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED",
    "P85":  "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY",
    "P86":  "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY",
}

FORBIDDEN_TERMS = [
    "EV", "CLV", "Kelly", "stake", "real bet",
    "運彩", "投注建議", "下注", "賠率計算",
]


@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"P89 summary missing: {SUMMARY_PATH}"
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.exists(), f"P89 report missing: {REPORT_PATH}"
    return REPORT_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def s1(summary) -> dict:
    return summary["step1_verify_authorization"]


@pytest.fixture(scope="module")
def s2(summary) -> dict:
    return summary["step2_pre_recovery_state"]


@pytest.fixture(scope="module")
def s3(summary) -> dict:
    return summary["step3_execute_recovery"]


@pytest.fixture(scope="module")
def s4(summary) -> dict:
    return summary["step4_verify_p84e_freshness"]


@pytest.fixture(scope="module")
def s5(summary) -> dict:
    return summary["step5_validate_metrics"]


@pytest.fixture(scope="module")
def s6(summary) -> dict:
    return summary["step6_confirm_p86_restored"]


@pytest.fixture(scope="module")
def s7(summary) -> dict:
    return summary["step7_governance_scan"]


@pytest.fixture(scope="module")
def recovery_results(s3) -> dict[str, dict]:
    """Index results by phase."""
    return {r["phase"]: r for r in s3["results"]}


# ---------------------------------------------------------------------------
# 1. Infrastructure
# ---------------------------------------------------------------------------

class TestInfrastructure:
    def test_script_exists(self):
        assert SCRIPT_PATH.exists(), f"P89 script missing: {SCRIPT_PATH}"

    def test_summary_exists(self):
        assert SUMMARY_PATH.exists(), f"P89 summary missing: {SUMMARY_PATH}"

    def test_report_exists(self):
        assert REPORT_PATH.exists(), f"P89 report missing: {REPORT_PATH}"

    def test_active_task_exists(self):
        assert ACTIVE_TASK.exists(), f"active_task.md missing: {ACTIVE_TASK}"

    def test_summary_classification_present(self, summary):
        assert "p89_classification" in summary

    def test_summary_classification_in_allowed_list(self, summary):
        assert summary["p89_classification"] in ALLOWED_CLASSIFICATIONS

    def test_summary_date_present(self, summary):
        assert "date" in summary
        d = summary["date"]
        assert isinstance(d, str) and len(d) == 10

    def test_summary_phase_field(self, summary):
        assert summary.get("phase") == "authorized-recovery"

    def test_summary_generated_at_present(self, summary):
        assert "generated_at" in summary
        assert isinstance(summary["generated_at"], str)

    def test_summary_recovery_sequence_field(self, summary):
        assert summary.get("recovery_sequence") == RECOVERY_SEQUENCE

    def test_summary_n_scripts_executed(self, summary):
        assert summary.get("n_scripts_executed") == 6

    def test_summary_allowed_classifications_field(self, summary):
        assert "allowed_classifications" in summary
        for cls in ALLOWED_CLASSIFICATIONS:
            assert cls in summary["allowed_classifications"]


# ---------------------------------------------------------------------------
# 2. Authorization Verification
# ---------------------------------------------------------------------------

class TestAuthorizationVerification:
    def test_authorization_received_matches_required_phrase(self, s1):
        assert s1["authorization_received"] == REQUIRED_PHRASE

    def test_required_phrase_field(self, s1):
        assert s1["required_phrase"] == REQUIRED_PHRASE

    def test_phrase_ok_true(self, s1):
        assert s1["phrase_ok"] is True

    def test_step1_status_passed(self, s1):
        assert s1["status"] == "PASSED"

    def test_authorization_status_granted(self, summary):
        assert summary.get("authorization_status") == "GRANTED"

    def test_authorization_phrase_received_in_summary(self, summary):
        assert summary.get("authorization_phrase_received") == REQUIRED_PHRASE

    def test_phrase_is_immutable_string(self, s1):
        # Phrase must be the exact required string, not a variable result
        phrase = s1["authorization_received"]
        assert phrase == "YES regenerate stale downstream artifacts for P87 recovery"
        assert len(phrase) == 58


# ---------------------------------------------------------------------------
# 3. Pre-Recovery State
# ---------------------------------------------------------------------------

class TestPreRecoveryState:
    def test_step2_status_passed(self, s2):
        assert s2["status"] == "PASSED"

    def test_p86_pre_classification_is_string(self, s2):
        cls = s2.get("p86_pre_classification")
        assert isinstance(cls, str) and len(cls) > 0

    def test_p86_pre_is_stale_is_boolean(self, s2):
        assert isinstance(s2.get("p86_pre_is_stale"), bool)

    def test_canonical_rows_mtime_recorded(self, s2):
        assert s2.get("canonical_rows_mtime") is not None

    def test_p84e_rows_mtime_pre_recorded(self, s2):
        assert s2.get("p84e_rows_mtime_pre") is not None

    def test_delta_seconds_pre_is_numeric(self, s2):
        delta = s2.get("delta_seconds_pre")
        assert delta is not None and not math.isnan(delta)

    def test_canonical_newer_than_p84e_rows_is_boolean(self, s2):
        assert isinstance(s2.get("canonical_newer_than_p84e_rows"), bool)

    def test_step_label(self, s2):
        assert s2.get("step") == "step2_pre_recovery_state"


# ---------------------------------------------------------------------------
# 4. Recovery Sequence — P84E
# ---------------------------------------------------------------------------

class TestP84ERegeneration:
    def test_p84e_result_present(self, recovery_results):
        assert "P84E" in recovery_results

    def test_p84e_returncode_zero(self, recovery_results):
        assert recovery_results["P84E"]["returncode"] == 0

    def test_p84e_success_true(self, recovery_results):
        assert recovery_results["P84E"]["success"] is True

    def test_p84e_validation_ok(self, recovery_results):
        assert recovery_results["P84E"]["validation"]["ok"] is True

    def test_p84e_classification(self, recovery_results):
        cls = recovery_results["P84E"]["validation"]["classification"]
        assert cls in (
            "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS",
            "P84E_OUTCOME_ATTACHMENT_READY_SAMPLE_LIMITED",
        )

    def test_p84e_script_path_recorded(self, recovery_results):
        script = recovery_results["P84E"].get("script", "")
        assert "p84e" in script


# ---------------------------------------------------------------------------
# 5. Recovery Sequence — P84F
# ---------------------------------------------------------------------------

class TestP84FRegeneration:
    def test_p84f_result_present(self, recovery_results):
        assert "P84F" in recovery_results

    def test_p84f_returncode_zero(self, recovery_results):
        assert recovery_results["P84F"]["returncode"] == 0

    def test_p84f_success_true(self, recovery_results):
        assert recovery_results["P84F"]["success"] is True

    def test_p84f_validation_ok(self, recovery_results):
        assert recovery_results["P84F"]["validation"]["ok"] is True

    def test_p84f_not_inverted(self, recovery_results):
        cls = recovery_results["P84F"]["validation"]["classification"]
        assert cls != "P84F_SIDE_MAPPING_INVERTED"


# ---------------------------------------------------------------------------
# 6. Recovery Sequence — P84G
# ---------------------------------------------------------------------------

class TestP84GRegeneration:
    def test_p84g_result_present(self, recovery_results):
        assert "P84G" in recovery_results

    def test_p84g_returncode_zero(self, recovery_results):
        assert recovery_results["P84G"]["returncode"] == 0

    def test_p84g_success_true(self, recovery_results):
        assert recovery_results["P84G"]["success"] is True

    def test_p84g_validation_ok(self, recovery_results):
        assert recovery_results["P84G"]["validation"]["ok"] is True

    def test_p84g_classification(self, recovery_results):
        assert recovery_results["P84G"]["validation"]["classification"] == \
            "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED"


# ---------------------------------------------------------------------------
# 7. Recovery Sequence — P84H
# ---------------------------------------------------------------------------

class TestP84HRegeneration:
    def test_p84h_result_present(self, recovery_results):
        assert "P84H" in recovery_results

    def test_p84h_returncode_zero(self, recovery_results):
        assert recovery_results["P84H"]["returncode"] == 0

    def test_p84h_success_true(self, recovery_results):
        assert recovery_results["P84H"]["success"] is True

    def test_p84h_validation_ok(self, recovery_results):
        assert recovery_results["P84H"]["validation"]["ok"] is True

    def test_p84h_classification(self, recovery_results):
        cls = recovery_results["P84H"]["validation"]["classification"]
        assert cls in (
            "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED",
            "P84H_CORRECTED_SIGNAL_VALIDATED_DIAGNOSTIC_ONLY",
        )

    def test_p84h_started_at_recorded(self, recovery_results):
        assert recovery_results["P84H"].get("started_at") is not None

    def test_p84h_finished_at_recorded(self, recovery_results):
        assert recovery_results["P84H"].get("finished_at") is not None


# ---------------------------------------------------------------------------
# 8. Recovery Sequence — P85
# ---------------------------------------------------------------------------

class TestP85Regeneration:
    def test_p85_result_present(self, recovery_results):
        assert "P85" in recovery_results

    def test_p85_returncode_zero(self, recovery_results):
        assert recovery_results["P85"]["returncode"] == 0

    def test_p85_success_true(self, recovery_results):
        assert recovery_results["P85"]["success"] is True

    def test_p85_validation_ok(self, recovery_results):
        assert recovery_results["P85"]["validation"]["ok"] is True

    def test_p85_classification(self, recovery_results):
        assert recovery_results["P85"]["validation"]["classification"] == \
            "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY"


# ---------------------------------------------------------------------------
# 9. P86 Contract Restored
# ---------------------------------------------------------------------------

class TestP86ContractRestored:
    def test_p86_result_present(self, recovery_results):
        assert "P86" in recovery_results

    def test_p86_returncode_zero(self, recovery_results):
        assert recovery_results["P86"]["returncode"] == 0

    def test_p86_validation_ok(self, recovery_results):
        assert recovery_results["P86"]["validation"]["ok"] is True

    def test_p86_post_classification(self, s6):
        assert s6["p86_post_classification"] == EXPECTED_P86_POST

    def test_p86_expected_post_field(self, s6):
        assert s6["p86_expected_post"] == EXPECTED_P86_POST

    def test_contract_restored_true(self, s6):
        assert s6["contract_restored"] is True

    def test_step6_status_passed(self, s6):
        assert s6["status"] == "PASSED"

    def test_summary_contract_restored_true(self, summary):
        assert summary["contract_restored"] is True

    def test_summary_stale_risk_resolved_true(self, summary):
        assert summary["stale_risk_resolved"] is True

    def test_p84e_freshness_stale_resolved(self, s4):
        assert s4["stale_resolved"] is True

    def test_p84e_rows_newer_than_canonical_post(self, s4):
        assert s4["p84e_rows_newer_than_canonical"] is True

    def test_step4_status(self, s4):
        assert s4["status"] in ("PASSED", "WARNING")


# ---------------------------------------------------------------------------
# 10. Metrics Tolerance
# ---------------------------------------------------------------------------

class TestMetricsTolerance:
    def test_all_within_tolerance(self, s5):
        assert s5["all_within_tolerance"] is True

    def test_summary_metrics_within_tolerance(self, summary):
        assert summary["metrics_all_within_tolerance"] is True

    def test_tolerance_value(self, s5):
        assert s5["tolerance"] == TOLERANCE

    def test_baseline_metrics_recorded(self, s5):
        for metric in BASELINE_METRICS:
            assert metric in s5["baseline_metrics"]

    def test_post_recovery_metrics_recorded(self, s5):
        for metric in BASELINE_METRICS:
            assert metric in s5["post_recovery_metrics"]

    @pytest.mark.parametrize("metric,baseline", BASELINE_METRICS.items())
    def test_metric_within_tolerance(self, s5, metric, baseline):
        post = s5["post_recovery_metrics"][metric]
        delta = abs(post - baseline)
        assert delta <= TOLERANCE, (
            f"{metric}: baseline={baseline}, post={post}, delta={delta} > {TOLERANCE}"
        )

    @pytest.mark.parametrize("metric", BASELINE_METRICS.keys())
    def test_metric_within_tolerance_flag(self, s5, metric):
        assert s5["within_tolerance"][metric] is True, \
            f"within_tolerance[{metric}] is not True"

    @pytest.mark.parametrize("metric", BASELINE_METRICS.keys())
    def test_metric_delta_finite(self, s5, metric):
        delta = s5["deltas"].get(metric)
        assert delta is not None and not math.isnan(delta)

    def test_n_post_recorded(self, s5):
        n = s5.get("n_post")
        # n may be None if P84H summary lacks n, or be ~808
        assert n is None or isinstance(n, (int, float))

    def test_step5_status_passed(self, s5):
        assert s5["status"] == "PASSED"

    def test_summary_baseline_metrics(self, summary):
        for metric, baseline in BASELINE_METRICS.items():
            assert summary["baseline_metrics"][metric] == baseline


# ---------------------------------------------------------------------------
# 11. Governance Scan
# ---------------------------------------------------------------------------

GOVERNANCE_CHECKS = [
    "paper_only",
    "diagnostic_only",
    "not_production_ready",
    "no_real_bet",
    "no_odds",
    "no_ev",
    "no_clv",
    "no_kelly",
    "no_paid_api",
    "no_frozen_artifact_modification",
    "no_fabricated_outcomes",
    "no_model_refit",
    "explicit_yes_phrase_verified",
    "recovery_scope_minimal",
    "metrics_tolerance_checked",
    "no_taiwan_lottery_recommendation",
    "no_betting_advice",
    "no_stake_computation",
    "no_historical_artifact_overwrite",
    "authorization_phrase_immutable",
]


class TestGovernanceScan:
    def test_governance_all_pass(self, s7):
        assert s7["governance_all_pass"] is True

    def test_summary_governance_all_pass(self, summary):
        assert summary["governance_all_pass"] is True

    def test_n_flags_is_20(self, s7):
        assert s7["n_flags"] == 20

    def test_governance_checks_present(self, s7):
        assert "governance_checks" in s7

    def test_step7_status_passed(self, s7):
        assert s7["status"] == "PASSED"

    @pytest.mark.parametrize("check_name", GOVERNANCE_CHECKS)
    def test_governance_check_passes(self, s7, check_name):
        checks = s7["governance_checks"]
        assert check_name in checks, f"governance check '{check_name}' missing"
        assert checks[check_name] is True, f"governance check '{check_name}' failed"

    def test_production_ready_false_in_flags(self, s7):
        flags = s7["p89_governance"]
        assert flags.get("production_ready") is False

    def test_not_production_ready_check_true(self, s7):
        assert s7["governance_checks"]["not_production_ready"] is True

    def test_no_odds_check(self, s7):
        assert s7["governance_checks"]["no_odds"] is True

    def test_no_ev_check(self, s7):
        assert s7["governance_checks"]["no_ev"] is True

    def test_governance_n_flags_in_summary(self, summary):
        assert summary.get("governance_n_flags") == 20


# ---------------------------------------------------------------------------
# 12. Final Classification
# ---------------------------------------------------------------------------

class TestFinalClassification:
    def test_classification_is_contract_restored(self, summary):
        assert summary["p89_classification"] == EXPECTED_CLASSIFICATION

    def test_classification_not_mismatch(self, summary):
        assert summary["p89_classification"] != "P89_AUTHORIZATION_MISMATCH"

    def test_classification_not_partial_failure(self, summary):
        assert summary["p89_classification"] != "P89_RECOVERY_PARTIAL_UPSTREAM_FAILED"

    def test_classification_not_metrics_drift(self, summary):
        assert summary["p89_classification"] != "P89_RECOVERY_COMPLETE_METRICS_DRIFT_DETECTED"

    def test_classification_in_allowed_list(self, summary):
        assert summary["p89_classification"] in ALLOWED_CLASSIFICATIONS

    def test_all_recovery_scripts_ok(self, s3):
        assert s3["all_ok"] is True

    def test_failed_phase_none(self, s3):
        assert s3["failed_phase"] is None

    def test_step3_status_passed(self, s3):
        assert s3["status"] == "PASSED"


# ---------------------------------------------------------------------------
# 13. Frozen Artifact Integrity
# ---------------------------------------------------------------------------

class TestFrozenArtifactIntegrity:
    def test_no_frozen_artifact_modification_flag(self, s7):
        # Governance check confirms no frozen artifacts were touched
        assert s7["governance_checks"]["no_frozen_artifact_modification"] is True

    def test_no_historical_artifact_overwrite_flag(self, s7):
        assert s7["governance_checks"]["no_historical_artifact_overwrite"] is True

    def test_active_task_contains_p89_marker(self):
        text = ACTIVE_TASK.read_text(encoding="utf-8")
        assert "P89:" in text

    def test_active_task_contains_contract_restored_marker(self):
        text = ACTIVE_TASK.read_text(encoding="utf-8")
        assert "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY" in text

    def test_active_task_contains_all_historical_markers(self):
        text = ACTIVE_TASK.read_text(encoding="utf-8")
        for marker in ["P83A:", "P84E:", "P84F:", "P84G:", "P84H:", "P85:", "P86:", "P87:", "P88:"]:
            assert marker in text, f"Missing historical marker: {marker}"


# ---------------------------------------------------------------------------
# 14. Report Content
# ---------------------------------------------------------------------------

class TestReportContent:
    def test_report_contains_classification(self, report_text):
        assert EXPECTED_CLASSIFICATION in report_text

    def test_report_contains_recovery_complete(self, report_text):
        assert "RECOVERY COMPLETE" in report_text or "RECOVERY_COMPLETE" in report_text

    def test_report_contains_granted(self, report_text):
        assert "GRANTED" in report_text

    def test_report_contains_authorization_phrase(self, report_text):
        assert REQUIRED_PHRASE in report_text

    def test_report_contains_p86_ready(self, report_text):
        assert "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY" in report_text

    def test_report_no_ev_clv_kelly(self, report_text):
        # Report must not contain betting computation terms
        forbidden_in_report = ["EV =", "CLV =", "Kelly =", "stake ="]
        for term in forbidden_in_report:
            assert term not in report_text, f"Forbidden term in report: {term!r}"

    def test_report_contains_governance_table(self, report_text):
        assert "Governance" in report_text

    def test_report_no_betting_advice(self, report_text):
        assert "下注建議" not in report_text
        assert "投注建議" not in report_text
