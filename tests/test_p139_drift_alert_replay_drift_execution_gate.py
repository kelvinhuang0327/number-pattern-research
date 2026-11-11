# P139 Drift Alert Replay Drift Execution Gate - Dedicated Test
import json
from pathlib import Path

P138_PATH = "data/mlb_2026/derived/p138_drift_alert_replay_drift_contract_summary.json"
P139_PATH = "data/mlb_2026/derived/p139_drift_alert_replay_drift_execution_gate_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "drift_alert_replay_drift_execution_gate_status",
    "source_drift_alert_replay_drift_contract_status",
    "source_replay_run_count",
    "source_evaluated_drift_event_count",
    "source_baseline_fingerprint",
    "evaluated_execution_case_count",
    "execution_cases",
    "execution_verdict_matrix",
    "blocking_condition_enforcement_matrix",
    "baseline_change_review_enforcement_matrix",
    "drift_detail_validation_matrix",
    "escalation_path_execution_matrix",
    "sla_execution_matrix",
    "required_owner_execution_matrix",
    "unlock_prevention_matrix",
    "no_unlock_governance_matrix",
    "invalid_drift_detail_cases",
    "invalid_baseline_change_cases",
    "allowed_next_actions",
    "prohibited_actions",
    "blockers",
    "final_classification",
    "governance_invariant_summary",
    "governance_statement",
    "regression_status",
}

REQUIRED_CASES = {
    "NO_REPLAY_DRIFT_RECORD_ONLY",
    "FINGERPRINT_DRIFT_BASELINE_REVIEW_REQUIRED",
    "ALERT_VERDICT_DRIFT_BLOCKED",
    "ESCALATION_DECISION_PACKET_DRIFT_BLOCKED",
    "ALERT_LEVEL_MATRIX_DRIFT_BLOCKED",
    "DRIFT_TYPE_MATRIX_DRIFT_BLOCKED",
    "ESCALATION_PATH_MATRIX_DRIFT_BLOCKED",
    "SLA_MATRIX_DRIFT_BLOCKED",
    "REQUIRED_OWNER_MATRIX_DRIFT_BLOCKED",
    "BLOCKED_ACTION_MATRIX_DRIFT_BLOCKED",
    "UNLOCK_PREVENTION_MATRIX_DRIFT_CRITICAL_STOP",
    "FINAL_CLASSIFICATION_DRIFT_BLOCKED",
    "REPLAY_RUN_COUNT_DRIFT_BLOCKED",
    "SOURCE_EVENT_COUNT_DRIFT_BLOCKED",
    "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
    "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
    "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
    "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
    "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
    "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
    "DRIFT_DETAILS_MISSING_BLOCKED",
    "BASELINE_CHANGE_REQUEST_MISSING_BLOCKED",
    "BASELINE_CHANGE_REVIEWER_NOT_APPROVED_BLOCKED",
    "BASELINE_CHANGE_NON_UNLOCK_ATTESTATION_MISSING_BLOCKED",
    "BASELINE_CHANGE_ROLLBACK_PLAN_MISSING_BLOCKED",
}

REQUIRED_EXECUTION_FIELDS = {
    "execution_case_id",
    "drift_type",
    "alert_level",
    "source_matrix_or_packet",
    "verdict",
    "blocked",
    "critical_stop",
    "baseline_change_required",
    "drift_details_required",
    "drift_details_complete",
    "baseline_change_review_required",
    "baseline_change_review_complete",
    "escalation_path",
    "sla_class",
    "required_owners",
    "blocked_actions",
    "next_required_action",
    "provider_unlock_allowed",
    "odds_unlock_allowed",
    "recommendation_unlock_allowed",
    "production_unlock_allowed",
    "ev_clv_kelly_unlock_allowed",
}

FINAL_CLASSIFICATIONS = {
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_READY_WITH_BLOCKERS",
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p139_summary_exists():
    assert Path(P139_PATH).exists(), "P139 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P139_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_values_align_with_p138():
    p138 = load_json(P138_PATH)
    p139 = load_json(P139_PATH)

    assert p139["source_drift_alert_replay_drift_contract_status"] == p138["drift_alert_replay_drift_contract_status"]
    assert p139["source_replay_run_count"] == p138["source_replay_run_count"]
    assert p139["source_evaluated_drift_event_count"] == p138["source_evaluated_drift_event_count"]
    assert p139["source_baseline_fingerprint"] == p138["source_baseline_fingerprint"]


def test_required_execution_case_coverage_and_case_count():
    d = load_json(P139_PATH)
    cases = d["execution_cases"]
    case_ids = {c["execution_case_id"] for c in cases}

    assert REQUIRED_CASES.issubset(case_ids)
    assert d["evaluated_execution_case_count"] == len(cases)


def test_each_execution_case_contains_required_verdict_fields():
    d = load_json(P139_PATH)
    for case in d["execution_cases"]:
        assert REQUIRED_EXECUTION_FIELDS.issubset(set(case.keys()))


def test_required_execution_behavior_blocking_and_record_only():
    d = load_json(P139_PATH)
    case_by_id = {c["execution_case_id"]: c for c in d["execution_cases"]}

    no_drift = case_by_id["NO_REPLAY_DRIFT_RECORD_ONLY"]
    assert no_drift["blocked"] is False
    assert no_drift["critical_stop"] is False
    assert no_drift["escalation_path"] == "record_only"
    assert no_drift["verdict"] == "ALLOW_RECORD_ONLY"

    for case_id, case in case_by_id.items():
        if case_id == "NO_REPLAY_DRIFT_RECORD_ONLY":
            continue
        assert case["blocked"] is True

    for critical_case in [
        "UNLOCK_PREVENTION_MATRIX_DRIFT_CRITICAL_STOP",
        "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
        "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
        "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
        "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
        "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
        "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
    ]:
        assert case_by_id[critical_case]["critical_stop"] is True


def test_baseline_review_and_drift_detail_enforcement():
    d = load_json(P139_PATH)
    case_by_id = {c["execution_case_id"]: c for c in d["execution_cases"]}

    for case_id in [
        "FINGERPRINT_DRIFT_BASELINE_REVIEW_REQUIRED",
        "REPLAY_RUN_COUNT_DRIFT_BLOCKED",
        "SOURCE_EVENT_COUNT_DRIFT_BLOCKED",
        "ALERT_VERDICT_DRIFT_BLOCKED",
        "ESCALATION_DECISION_PACKET_DRIFT_BLOCKED",
        "ALERT_LEVEL_MATRIX_DRIFT_BLOCKED",
        "DRIFT_TYPE_MATRIX_DRIFT_BLOCKED",
        "ESCALATION_PATH_MATRIX_DRIFT_BLOCKED",
        "SLA_MATRIX_DRIFT_BLOCKED",
        "REQUIRED_OWNER_MATRIX_DRIFT_BLOCKED",
        "BLOCKED_ACTION_MATRIX_DRIFT_BLOCKED",
        "FINAL_CLASSIFICATION_DRIFT_BLOCKED",
    ]:
        assert case_by_id[case_id]["baseline_change_required"] is True
        assert case_by_id[case_id]["baseline_change_review_required"] is True

    assert "DRIFT_DETAILS_MISSING_BLOCKED" in d["invalid_drift_detail_cases"]
    assert "BASELINE_CHANGE_REQUEST_MISSING_BLOCKED" in d["invalid_baseline_change_cases"]
    assert "BASELINE_CHANGE_REVIEWER_NOT_APPROVED_BLOCKED" in d["invalid_baseline_change_cases"]
    assert "BASELINE_CHANGE_NON_UNLOCK_ATTESTATION_MISSING_BLOCKED" in d["invalid_baseline_change_cases"]
    assert "BASELINE_CHANGE_ROLLBACK_PLAN_MISSING_BLOCKED" in d["invalid_baseline_change_cases"]


def test_unlock_and_governance_invariants_remain_safe():
    d = load_json(P139_PATH)
    g = d["governance_invariant_summary"]

    assert g["paper_only"] is True
    assert g["diagnostic_only"] is True
    assert g["production_ready"] is False
    assert g["real_bet_allowed"] is False
    assert g["recommendation_allowed"] is False
    assert g["provider_approved"] is False
    assert g["authorization_evidence_present"] is False
    assert g["placeholder_allowed_as_authorization"] is False
    assert g["real_legal_odds_ingested"] is False
    assert g["live_api_calls"] == 0
    assert g["paid_api_called"] is False
    assert g["ev_computed"] is False
    assert g["clv_computed"] is False
    assert g["kelly_computed"] is False
    assert g["stake_sizing"] is False
    assert g["profit_computed"] is False
    assert g["recommendation_generated"] is False

    for case in d["execution_cases"]:
        assert case["provider_unlock_allowed"] is False
        assert case["odds_unlock_allowed"] is False
        assert case["recommendation_unlock_allowed"] is False
        assert case["production_unlock_allowed"] is False
        assert case["ev_clv_kelly_unlock_allowed"] is False

    statement = d["governance_statement"].lower()
    assert "does not imply" in statement
    assert "provider approval" in statement
    assert "recommendation readiness" in statement
    assert "production readiness" in statement


def test_regression_status_and_final_classification():
    d = load_json(P139_PATH)

    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_READY_WITH_BLOCKERS"
