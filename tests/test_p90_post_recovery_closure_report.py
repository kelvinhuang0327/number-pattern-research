"""
tests/test_p90_post_recovery_closure_report.py
================================================
Test suite for P90 — Post-Recovery Closure Report and Roadmap Decision Gate.

Governance: paper-only, diagnostic-only. No EV/CLV/Kelly/odds/production.
"""

from __future__ import annotations

import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
REPORT_DIR = ROOT / "report"

SUMMARY_PATH = DERIVED / "p90_post_recovery_closure_report_summary.json"
REPORT_PATH = REPORT_DIR / "p90_post_recovery_closure_report_20260527.md"
SCRIPT_PATH = ROOT / "scripts" / "_p90_post_recovery_closure_report.py"

EXPECTED_FINAL_CLASSIFICATION = "P90_POST_RECOVERY_CLOSURE_READY"

ALLOWED_FINAL_CLASSIFICATIONS = [
    "P90_POST_RECOVERY_CLOSURE_READY",
    "P90_POST_RECOVERY_CLOSURE_BLOCKED_BY_PREFLIGHT",
    "P90_POST_RECOVERY_CLOSURE_FAILED_CLASSIFICATION_MISMATCH",
    "P90_POST_RECOVERY_CLOSURE_FAILED_GOVERNANCE_MISMATCH",
    "P90_POST_RECOVERY_CLOSURE_BLOCKED_BY_SCOPE_DRIFT",
]

EXPECTED_PHASE_CLASSIFICATIONS = {
    "p84h": "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED",
    "p85":  "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY",
    "p86":  "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY",
    "p87":  "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES",
    "p88":  "P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION",
    "p89":  "P89_RECOVERY_COMPLETE_CONTRACT_RESTORED",
}

FORBIDDEN_STRINGS = [
    "betting recommendation",
    "stake sizing",
    "kelly",
    "ev_computed",
    "clv_computed",
    "production bet",
    "place a bet",
    "recommended to bet",
    "wager",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def summary() -> dict:
    assert SUMMARY_PATH.exists(), f"P90 summary missing: {SUMMARY_PATH}"
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report_text() -> str:
    assert REPORT_PATH.exists(), f"P90 report missing: {REPORT_PATH}"
    return REPORT_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Class 1: Infrastructure
# ---------------------------------------------------------------------------


class TestInfrastructure:
    def test_script_exists(self):
        assert SCRIPT_PATH.exists(), f"P90 script missing: {SCRIPT_PATH}"

    def test_summary_exists(self):
        assert SUMMARY_PATH.exists(), f"P90 summary missing: {SUMMARY_PATH}"

    def test_report_exists(self):
        assert REPORT_PATH.exists(), f"P90 report missing: {REPORT_PATH}"

    def test_summary_is_valid_json(self):
        data = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_summary_has_date(self, summary):
        assert summary.get("date") == "2026-05-27"

    def test_summary_has_generated_at(self, summary):
        assert "generated_at" in summary
        assert "2026" in summary["generated_at"]

    def test_summary_has_phase(self, summary):
        assert summary.get("phase") == "diagnostic-only"

    def test_summary_has_final_classification_key(self, summary):
        assert "final_classification" in summary or "p90_classification" in summary

    def test_final_classification_is_allowed(self, summary):
        cls = summary.get("p90_classification") or summary.get("final_classification")
        assert cls in ALLOWED_FINAL_CLASSIFICATIONS, f"Unknown: {cls}"

    def test_final_classification_is_expected(self, summary):
        cls = summary.get("p90_classification") or summary.get("final_classification")
        assert cls == EXPECTED_FINAL_CLASSIFICATION, f"Got {cls!r}"

    def test_report_not_empty(self, report_text):
        assert len(report_text) > 200

    def test_report_has_p90_header(self, report_text):
        assert "P90" in report_text


# ---------------------------------------------------------------------------
# Class 2: Phase Chain Classification Locks
# ---------------------------------------------------------------------------


class TestPhaseChainClassificationLocks:
    def test_phase_chain_summary_exists(self, summary):
        assert "phase_chain_summary" in summary

    def test_all_six_phases_present(self, summary):
        chain = summary["phase_chain_summary"]
        for ph in ["p84h", "p85", "p86", "p87", "p88", "p89"]:
            assert ph in chain, f"Phase {ph} missing from chain"

    @pytest.mark.parametrize("phase,expected_cls", list(EXPECTED_PHASE_CLASSIFICATIONS.items()))
    def test_phase_classification_match(self, summary, phase, expected_cls):
        chain = summary["phase_chain_summary"]
        row = chain.get(phase, {})
        actual = row.get("classification")
        assert actual == expected_cls, (
            f"{phase.upper()}: expected {expected_cls!r}, got {actual!r}"
        )

    @pytest.mark.parametrize("phase", list(EXPECTED_PHASE_CLASSIFICATIONS.keys()))
    def test_phase_match_flag_true(self, summary, phase):
        chain = summary["phase_chain_summary"]
        assert chain[phase].get("match") is True, f"{phase.upper()} match=False"

    def test_all_classifications_match(self, summary):
        assert summary.get("all_classifications_match") is True

    def test_p84h_classification_lock(self, summary):
        chain = summary["phase_chain_summary"]
        assert chain["p84h"]["classification"] == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"

    def test_p85_classification_lock(self, summary):
        chain = summary["phase_chain_summary"]
        assert chain["p85"]["classification"] == "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY"

    def test_p86_classification_is_ready(self, summary):
        chain = summary["phase_chain_summary"]
        assert chain["p86"]["classification"] == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"

    def test_p89_classification_lock(self, summary):
        chain = summary["phase_chain_summary"]
        assert chain["p89"]["classification"] == "P89_RECOVERY_COMPLETE_CONTRACT_RESTORED"


# ---------------------------------------------------------------------------
# Class 3: Recovery Status
# ---------------------------------------------------------------------------


class TestRecoveryStatus:
    def test_recovery_status_exists(self, summary):
        assert "recovery_status" in summary

    def test_contract_restored(self, summary):
        rs = summary["recovery_status"]
        assert rs.get("contract_restored") is True

    def test_stale_risk_resolved(self, summary):
        rs = summary["recovery_status"]
        assert rs.get("stale_risk_resolved") is True

    def test_metrics_within_tolerance(self, summary):
        rs = summary["recovery_status"]
        assert rs.get("metrics_all_within_tolerance") is True

    def test_p86_is_ready(self, summary):
        rs = summary["recovery_status"]
        assert rs.get("p86_is_ready") is True

    def test_recovery_complete(self, summary):
        rs = summary["recovery_status"]
        assert rs.get("recovery_complete") is True

    def test_p86_current_classification(self, summary):
        rs = summary["recovery_status"]
        assert rs.get("p86_current_classification") == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"

    def test_authorization_granted(self, summary):
        rs = summary["recovery_status"]
        assert rs.get("authorization_status") == "GRANTED"

    def test_regression_record_present(self, summary):
        rs = summary["recovery_status"]
        assert isinstance(rs.get("regression_record"), str)
        assert "passed" in rs["regression_record"].lower()


# ---------------------------------------------------------------------------
# Class 4: P86 Contract Status
# ---------------------------------------------------------------------------


class TestP86ContractStatus:
    def test_p86_contract_status_field(self, summary):
        assert "p86_contract_status" in summary

    def test_p86_contract_is_ready(self, summary):
        assert summary["p86_contract_status"] == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"

    def test_stale_downstream_risk_absent(self, summary):
        assert summary.get("stale_downstream_risk_present") is False


# ---------------------------------------------------------------------------
# Class 5: Governance Scan
# ---------------------------------------------------------------------------


class TestGovernanceScan:
    def test_governance_status_exists(self, summary):
        assert "governance_status" in summary

    def test_governance_all_pass(self, summary):
        assert summary.get("governance_all_pass") is True

    def test_governance_status_all_pass(self, summary):
        gs = summary["governance_status"]
        assert gs.get("governance_all_pass") is True

    def test_n_flags_is_20(self, summary):
        gs = summary["governance_status"]
        assert gs.get("n_flags") == 20

    def test_paper_only_flag(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("paper_only") is True

    def test_diagnostic_only_flag(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("diagnostic_only") is True

    def test_production_ready_false(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("production_ready") is False

    def test_no_real_bet(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("no_real_bet") is True

    def test_odds_not_used(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("odds_used") is False

    def test_ev_not_computed(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("ev_computed") is False

    def test_clv_not_computed(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("clv_computed") is False

    def test_kelly_not_computed(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("kelly_computed") is False

    def test_no_paid_api(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("paid_api_called") is False

    def test_no_live_api_calls(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("live_api_calls") == 0

    def test_no_champion_replacement(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("no_champion_replacement") is True

    def test_no_runtime_mutation(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("no_runtime_recommendation_mutation") is True

    def test_no_production_betting(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("no_production_betting_recommendation") is True

    def test_no_taiwan_lottery(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("no_taiwan_lottery_betting_recommendation") is True

    def test_no_calibration_refit(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("no_calibration_refit") is True

    def test_no_model_retraining(self, summary):
        gov = summary["governance_status"]["p90_governance"]
        assert gov.get("no_model_retraining") is True

    @pytest.mark.parametrize("check_name", [
        "paper_only", "diagnostic_only", "not_production_ready",
        "no_real_bet", "no_odds", "no_ev", "no_clv", "no_kelly",
        "no_live_api", "no_paid_api", "no_champion_replacement",
        "no_runtime_mutation", "no_production_betting", "no_taiwan_lottery",
        "no_calibration_refit", "no_model_retraining",
        "no_canonical_rows_mod", "no_raw_data_mod",
        "no_historical_overwrite", "scope_within_whitelist",
    ])
    def test_governance_check_passes(self, summary, check_name):
        checks = summary["governance_status"]["governance_checks"]
        assert check_name in checks, f"Missing check: {check_name}"
        assert checks[check_name] is True, f"Check {check_name} is not True"


# ---------------------------------------------------------------------------
# Class 6: Next Phase Recommendation
# ---------------------------------------------------------------------------


class TestNextPhaseRecommendation:
    def test_next_phase_recommendation_field(self, summary):
        assert "next_phase_recommendation" in summary

    def test_next_phase_recommendation_is_string(self, summary):
        assert isinstance(summary["next_phase_recommendation"], str)
        assert len(summary["next_phase_recommendation"]) > 5

    def test_next_phase_lanes_present(self, summary):
        lanes = summary.get("next_phase_lanes", [])
        assert len(lanes) >= 3

    def test_prediction_only_tracking_lane_open(self, summary):
        lanes = summary.get("next_phase_lanes", [])
        lane_names = [l["lane"] for l in lanes]
        assert any("tracking" in n.lower() or "prediction" in n.lower() for n in lane_names)

    def test_market_edge_lane_blocked(self, summary):
        lanes = summary.get("next_phase_lanes", [])
        market = next((l for l in lanes if "market" in l["lane"].lower()), None)
        assert market is not None
        assert market["status"] == "BLOCKED"

    def test_product_recommendation_blocked(self, summary):
        lanes = summary.get("next_phase_lanes", [])
        prod = next((l for l in lanes if "product" in l["lane"].lower() or "recommendation" in l["lane"].lower()), None)
        assert prod is not None
        assert prod["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Class 7: Final Classification
# ---------------------------------------------------------------------------


class TestFinalClassification:
    def test_final_cls_in_allowed(self, summary):
        cls = summary.get("p90_classification") or summary.get("final_classification")
        assert cls in ALLOWED_FINAL_CLASSIFICATIONS

    def test_final_cls_is_ready(self, summary):
        cls = summary.get("p90_classification") or summary.get("final_classification")
        assert cls == "P90_POST_RECOVERY_CLOSURE_READY"

    def test_step8_classification_consistent(self, summary):
        top = summary.get("p90_classification") or summary.get("final_classification")
        step8 = summary.get("step8_final_classification", {})
        assert step8.get("classification") == top

    def test_step8_all_checks_passed(self, summary):
        step8 = summary.get("step8_final_classification", {})
        assert step8.get("n_checks_passed") == step8.get("n_checks_total")

    def test_report_contains_ready_classification(self, report_text):
        assert "P90_POST_RECOVERY_CLOSURE_READY" in report_text


# ---------------------------------------------------------------------------
# Class 8: Report Content — No Betting / EV / CLV / Kelly
# ---------------------------------------------------------------------------


class TestReportNoBettingContent:
    def test_report_no_betting_recommendation_text(self, report_text):
        lower = report_text.lower()
        # These are forbidden INSTRUCTIONS not references
        assert "you should bet" not in lower
        assert "place a bet" not in lower
        assert "recommended to bet" not in lower

    def test_report_no_ev_instruction(self, report_text):
        lower = report_text.lower()
        # "ev_computed" flag in governance section is OK; explicit instruction is not
        assert "expected value:" not in lower
        assert "ev = " not in lower

    def test_report_no_stake_instruction(self, report_text):
        lower = report_text.lower()
        assert "stake:" not in lower
        assert "bet size:" not in lower

    def test_report_no_kelly_instruction(self, report_text):
        lower = report_text.lower()
        assert "kelly fraction:" not in lower
        assert "kelly stake:" not in lower

    def test_report_no_taiwan_lottery_instruction(self, report_text):
        lower = report_text.lower()
        assert "台灣運彩" not in report_text or "no taiwan" in lower
        # More specifically: should not say "建議下注"
        assert "建議下注" not in report_text

    def test_report_contains_paper_only(self, report_text):
        lower = report_text.lower()
        assert "paper" in lower or "diagnostic" in lower

    def test_report_has_cto_summary(self, report_text):
        assert "CTO" in report_text

    def test_report_has_ceo_summary(self, report_text):
        assert "CEO" in report_text

    def test_report_has_governance_section(self, report_text):
        assert "Governance" in report_text or "governance" in report_text

    def test_report_has_phase_chain_table(self, report_text):
        assert "P84H" in report_text and "P89" in report_text


# ---------------------------------------------------------------------------
# Class 9: Frozen Artifact Integrity
# ---------------------------------------------------------------------------


class TestFrozenArtifactIntegrity:
    """Verify that upstream frozen artifacts are unchanged."""

    def test_p84h_classification_unchanged(self):
        p = DERIVED / "p84h_corrected_signal_validation_coverage_guard_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p84h_classification"] == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"

    def test_p85_classification_unchanged(self):
        p = DERIVED / "p85_prediction_convention_invariant_gate_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p85_classification"] == "P85_PREDICTION_CONVENTION_INVARIANT_GATE_READY"

    def test_p86_classification_unchanged(self):
        p = DERIVED / "p86_artifact_regeneration_dependency_contract_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p86_classification"] == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"

    def test_p87_classification_unchanged(self):
        p = DERIVED / "p87_stale_downstream_recovery_dry_run_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p87_classification"] == "P87_REGENERATION_REQUIRED_AWAITING_EXPLICIT_YES"

    def test_p88_classification_unchanged(self):
        p = DERIVED / "p88_regeneration_authorization_gate_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p88_classification"] == "P88_AWAITING_EXPLICIT_REGENERATION_AUTHORIZATION"

    def test_p89_classification_unchanged(self):
        p = DERIVED / "p89_authorized_recovery_executor_summary.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["p89_classification"] == "P89_RECOVERY_COMPLETE_CONTRACT_RESTORED"
