# P140 Drift Alert Replay Drift Signoff Evidence Packet Gate - Dedicated Test
import json
from pathlib import Path

P139_PATH = "data/mlb_2026/derived/p139_drift_alert_replay_drift_execution_gate_summary.json"
P140_PATH = "data/mlb_2026/derived/p140_drift_alert_replay_drift_signoff_evidence_packet_gate_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "drift_alert_replay_drift_signoff_packet_gate_status",
    "source_drift_alert_replay_drift_execution_gate_status",
    "source_evaluated_execution_case_count",
    "source_invalid_drift_detail_case_count",
    "source_invalid_baseline_change_case_count",
    "source_baseline_fingerprint",
    "signoff_packet_schema",
    "required_signoff_roles",
    "required_signoff_evidence_fields",
    "valid_signoff_packet_template",
    "invalid_signoff_packet_cases",
    "signoff_packet_verdict_matrix",
    "execution_case_signoff_requirement_matrix",
    "drift_detail_signoff_requirement_matrix",
    "baseline_change_signoff_requirement_matrix",
    "escalation_path_signoff_matrix",
    "sla_signoff_matrix",
    "owner_signoff_matrix",
    "non_unlock_attestation_matrix",
    "rollback_acknowledgement_matrix",
    "unlock_prevention_matrix",
    "no_unlock_governance_matrix",
    "allowed_next_actions",
    "prohibited_actions",
    "blockers",
    "final_classification",
    "governance_invariant_summary",
    "governance_statement",
    "regression_status",
}

REQUIRED_PACKET_FIELDS = {
    "signoff_packet_id",
    "source_execution_case_id",
    "source_verdict",
    "source_drift_type",
    "source_alert_level",
    "source_escalation_path",
    "source_sla_class",
    "required_owners",
    "provided_signoff_owners",
    "signer_identity_by_owner",
    "signer_authority_attestation_by_owner",
    "signoff_status_by_owner",
    "signoff_timestamp_by_owner",
    "evidence_reference_by_owner",
    "drift_details_reference",
    "baseline_change_request_reference",
    "rollback_acknowledgement",
    "non_unlock_attestation",
    "provider_unlock_requested",
    "odds_unlock_requested",
    "recommendation_unlock_requested",
    "production_unlock_requested",
    "ev_clv_kelly_unlock_requested",
    "live_or_paid_api_requested",
}

REQUIRED_INVALID_CASE_IDS = {
    "MISSING_SIGNOFF_PACKET_ID_BLOCKED",
    "MISSING_SOURCE_EXECUTION_CASE_ID_BLOCKED",
    "MISSING_SOURCE_VERDICT_BLOCKED",
    "MISSING_SOURCE_DRIFT_TYPE_BLOCKED",
    "MISSING_REQUIRED_OWNERS_BLOCKED",
    "MISSING_PROVIDED_SIGNOFF_OWNERS_BLOCKED",
    "MISSING_SIGNER_IDENTITY_BLOCKED",
    "MISSING_SIGNER_AUTHORITY_ATTESTATION_BLOCKED",
    "SIGNOFF_STATUS_NOT_APPROVED_BLOCKED",
    "MISSING_SIGNOFF_TIMESTAMP_BLOCKED",
    "MISSING_EVIDENCE_REFERENCE_BLOCKED",
    "MISSING_DRIFT_DETAILS_REFERENCE_FOR_DRIFT_CASE_BLOCKED",
    "MISSING_BASELINE_CHANGE_REQUEST_REFERENCE_BLOCKED",
    "MISSING_ROLLBACK_ACKNOWLEDGEMENT_BLOCKED",
    "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED",
    "ROLE_MISMATCH_BLOCKED",
    "SIGNOFF_FOR_CRITICAL_STOP_WITH_UNLOCK_REQUEST_BLOCKED",
    "PROVIDER_UNLOCK_REQUESTED_BLOCKED",
    "ODDS_UNLOCK_REQUESTED_BLOCKED",
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED",
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKED",
    "EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKED",
    "LIVE_OR_PAID_API_REQUESTED_BLOCKED",
    "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKED",
    "SIGNOFF_PACKET_TREATED_AS_PRODUCTION_READY_BLOCKED",
}

FINAL_CLASSIFICATION = "P140_DRIFT_ALERT_REPLAY_DRIFT_SIGNOFF_EVIDENCE_PACKET_GATE_READY_WITH_BLOCKERS"


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p140_summary_exists():
    assert Path(P140_PATH).exists(), "P140 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P140_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_status_matches_p139_execution_gate():
    p139 = load_json(P139_PATH)
    p140 = load_json(P140_PATH)

    assert p140["source_drift_alert_replay_drift_execution_gate_status"] == p139["drift_alert_replay_drift_execution_gate_status"]
    assert p140["source_evaluated_execution_case_count"] == p139["evaluated_execution_case_count"]
    assert p140["source_invalid_drift_detail_case_count"] == len(p139.get("invalid_drift_detail_cases", []))
    assert p140["source_invalid_baseline_change_case_count"] == len(p139.get("invalid_baseline_change_cases", []))
    assert p140["source_baseline_fingerprint"] == p139.get("source_baseline_fingerprint", "")


def test_signoff_packet_schema_and_template():
    d = load_json(P140_PATH)
    schema_fields = set(d["signoff_packet_schema"].keys())
    assert schema_fields == REQUIRED_PACKET_FIELDS

    valid = d["valid_signoff_packet_template"]
    assert set(valid.keys()) == REQUIRED_PACKET_FIELDS
    assert valid["provider_unlock_requested"] is False
    assert valid["odds_unlock_requested"] is False
    assert valid["recommendation_unlock_requested"] is False
    assert valid["production_unlock_requested"] is False
    assert valid["ev_clv_kelly_unlock_requested"] is False
    assert valid["live_or_paid_api_requested"] is False


def test_invalid_signoff_packet_cases_covered_and_blocked():
    d = load_json(P140_PATH)
    cases = {row["case_id"] for row in d["invalid_signoff_packet_cases"]}
    assert cases == REQUIRED_INVALID_CASE_IDS

    for row in d["invalid_signoff_packet_cases"]:
        assert row["status"] == "BLOCKED"
        assert len(row["blockers"]) >= 1
        assert d["signoff_packet_verdict_matrix"][row["case_id"]]["status"] == "BLOCKED"


def test_signoff_requirement_matrices_present():
    d = load_json(P140_PATH)
    assert isinstance(d["execution_case_signoff_requirement_matrix"], dict)
    assert isinstance(d["drift_detail_signoff_requirement_matrix"], dict)
    assert isinstance(d["baseline_change_signoff_requirement_matrix"], dict)
    assert isinstance(d["escalation_path_signoff_matrix"], dict)
    assert isinstance(d["sla_signoff_matrix"], dict)
    assert isinstance(d["owner_signoff_matrix"], dict)
    assert isinstance(d["non_unlock_attestation_matrix"], dict)
    assert isinstance(d["rollback_acknowledgement_matrix"], dict)
    assert isinstance(d["unlock_prevention_matrix"], dict)


def test_governance_invariants_and_statement():
    d = load_json(P140_PATH)
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
    assert "production readiness" in d["governance_statement"]


def test_regression_status_and_final_classification():
    d = load_json(P140_PATH)
    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["regression_status"]["targeted_p118_p140_tests_status"] == "PASS"
    assert isinstance(d["regression_status"].get("targeted_p118_p140_tests_command"), str)
    assert d["regression_status"]["targeted_p118_p140_tests_command"]
    assert d["final_classification"] == FINAL_CLASSIFICATION

