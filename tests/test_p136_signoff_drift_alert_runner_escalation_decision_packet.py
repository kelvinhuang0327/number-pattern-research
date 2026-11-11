# P136 Sign-off Drift Alert Runner + Escalation Decision Packet - Dedicated Test
import json
from pathlib import Path

P135_PATH = "data/mlb_2026/derived/p135_signoff_evidence_drift_alert_contract_summary.json"
P136_PATH = "data/mlb_2026/derived/p136_signoff_drift_alert_runner_escalation_decision_packet_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "signoff_drift_alert_runner_status",
    "source_signoff_drift_alert_contract_status",
    "source_signoff_replay_gate_status",
    "source_replay_run_count",
    "source_signoff_packet_count",
    "source_invalid_packet_count",
    "source_drift_detected",
    "evaluated_drift_event_count",
    "alert_verdicts",
    "escalation_decision_packets",
    "alert_level_execution_matrix",
    "drift_type_execution_matrix",
    "escalation_path_execution_matrix",
    "sla_execution_matrix",
    "required_owner_execution_matrix",
    "blocked_action_matrix",
    "unlock_prevention_matrix",
    "no_drift_record_packet",
    "simulated_blocking_drift_cases",
    "allowed_next_actions",
    "prohibited_actions",
    "blockers",
    "final_classification",
    "governance_invariant_summary",
    "governance_statement",
    "regression_status",
    "required_packet_fields",
}

REQUIRED_CASE_IDS = {
    "NO_SIGNOFF_DRIFT_RECORD_ONLY",
    "FINGERPRINT_DRIFT_BLOCKED",
    "SIGNOFF_VERDICT_MATRIX_DRIFT_BLOCKED",
    "BLOCKER_CLASSIFICATION_DRIFT_BLOCKED",
    "REQUIRED_EVIDENCE_MATRIX_DRIFT_BLOCKED",
    "ESCALATION_LEVEL_COVERAGE_DRIFT_BLOCKED",
    "GOVERNANCE_INVARIANT_DRIFT_BLOCKED",
    "UNLOCK_PREVENTION_DRIFT_BLOCKED",
    "SIGNOFF_PACKET_COUNT_DRIFT_BLOCKED",
    "INVALID_PACKET_COUNT_DRIFT_BLOCKED",
    "REPLAY_METADATA_DRIFT_REVIEW_REQUIRED",
    "DRIFT_DETAILS_MISSING_BLOCKED",
    "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
    "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
    "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
    "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
    "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
    "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
}

REQUIRED_PACKET_FIELDS = {
    "drift_case_id",
    "drift_type",
    "alert_level",
    "source_packet_or_matrix",
    "verdict",
    "blocked",
    "critical_stop",
    "escalation_path",
    "sla_class",
    "required_signoff_owners",
    "affected_roles",
    "affected_blocker_codes",
    "affected_unlock_flags",
    "remediation_required",
    "rollback_required",
    "non_unlock_attestation_required",
    "next_required_action",
    "provider_unlock_allowed",
    "odds_unlock_allowed",
    "recommendation_unlock_allowed",
    "production_unlock_allowed",
    "ev_clv_kelly_unlock_allowed",
}

FINAL_CLASSIFICATIONS = {
    "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_READY_WITH_BLOCKERS",
    "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_BLOCKED_BY_MISSING_ARTIFACTS",
    "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p136_summary_exists():
    assert Path(P136_PATH).exists(), "P136 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P136_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_status_matches_p135_contract():
    p135 = load_json(P135_PATH)
    p136 = load_json(P136_PATH)

    assert p136["source_signoff_drift_alert_contract_status"] == p135["signoff_drift_alert_contract_status"]
    assert p136["source_replay_run_count"] == 3
    assert p136["source_signoff_packet_count"] == 22
    assert p136["source_invalid_packet_count"] == 21
    assert p136["source_drift_detected"] is False


def test_runner_cases_and_packets_complete():
    d = load_json(P136_PATH)
    packets = d["escalation_decision_packets"]

    case_ids = {p["drift_case_id"] for p in packets}
    assert REQUIRED_CASE_IDS == case_ids
    assert d["evaluated_drift_event_count"] == len(REQUIRED_CASE_IDS)

    for p in packets:
        assert REQUIRED_PACKET_FIELDS.issubset(set(p.keys()))
        assert p["provider_unlock_allowed"] is False
        assert p["odds_unlock_allowed"] is False
        assert p["recommendation_unlock_allowed"] is False
        assert p["production_unlock_allowed"] is False
        assert p["ev_clv_kelly_unlock_allowed"] is False


def test_no_drift_and_dangerous_case_classification():
    d = load_json(P136_PATH)
    packets = {p["drift_case_id"]: p for p in d["escalation_decision_packets"]}

    no_drift = packets["NO_SIGNOFF_DRIFT_RECORD_ONLY"]
    assert no_drift["alert_level"] == "GREEN_NO_SIGNOFF_DRIFT"
    assert no_drift["blocked"] is False
    assert no_drift["critical_stop"] is False
    assert no_drift["escalation_path"] == "record_only"

    dangerous_cases = REQUIRED_CASE_IDS - {"NO_SIGNOFF_DRIFT_RECORD_ONLY"}
    for cid in dangerous_cases:
        assert packets[cid]["blocked"] is True

    for cid in {
        "GOVERNANCE_INVARIANT_DRIFT_BLOCKED",
        "UNLOCK_PREVENTION_DRIFT_BLOCKED",
        "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
        "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
        "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
        "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
        "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
        "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
    }:
        assert packets[cid]["critical_stop"] is True


def test_execution_matrices_and_blocked_lists_exist():
    d = load_json(P136_PATH)

    assert "GREEN_NO_SIGNOFF_DRIFT" in d["alert_level_execution_matrix"]
    assert "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT" in d["alert_level_execution_matrix"]
    assert "record_only" in d["escalation_path_execution_matrix"]
    assert "immediate_stop" in d["escalation_path_execution_matrix"]
    assert "SLA_IMMEDIATE_STOP" in d["sla_execution_matrix"]
    assert "engineering_owner" in d["required_owner_execution_matrix"]

    assert set(d["simulated_blocking_drift_cases"]) == (REQUIRED_CASE_IDS - {"NO_SIGNOFF_DRIFT_RECORD_ONLY"})


def test_governance_invariants_and_statement():
    d = load_json(P136_PATH)
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

    assert "does not imply legal provider approval" in d["governance_statement"]


def test_regression_status_and_final_classification():
    d = load_json(P136_PATH)

    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_READY_WITH_BLOCKERS"
