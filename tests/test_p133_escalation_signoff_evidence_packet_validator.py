# P133 Escalation Sign-off Evidence Packet Validator - Dedicated Test
import json
from pathlib import Path

P132_PATH = "data/mlb_2026/derived/p132_decision_card_escalation_router_summary.json"
P133_PATH = "data/mlb_2026/derived/p133_escalation_signoff_evidence_packet_validator_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "signoff_packet_validator_status",
    "source_escalation_router_status",
    "source_escalation_card_count",
    "required_signoff_roles",
    "signoff_packet_schema",
    "valid_signoff_packet_template",
    "invalid_signoff_packet_cases",
    "signoff_validation_rules",
    "signoff_verdict_matrix",
    "missing_signoff_blockers",
    "unauthorized_signoff_blockers",
    "role_mismatch_blockers",
    "stale_or_missing_timestamp_blockers",
    "non_unlock_attestation_blockers",
    "escalation_level_coverage_matrix",
    "required_evidence_matrix",
    "allowed_next_actions",
    "prohibited_actions",
    "blockers",
    "final_classification",
    "governance_invariant_summary",
    "governance_statement",
    "regression_status",
}

REQUIRED_SCHEMA_FIELDS = {
    "signoff_packet_id",
    "source_packet_id",
    "source_escalation_level",
    "source_blocker_codes",
    "required_signoff_roles",
    "provided_signoff_roles",
    "signer_identity_by_role",
    "signer_authority_attestation_by_role",
    "signoff_status_by_role",
    "signoff_timestamp_by_role",
    "evidence_reference_by_role",
    "escalation_reason",
    "decision_scope",
    "non_unlock_attestation",
    "rollback_acknowledgement",
    "provider_unlock_requested",
    "odds_unlock_requested",
    "recommendation_unlock_requested",
    "production_unlock_requested",
    "ev_clv_kelly_unlock_requested",
    "live_or_paid_api_requested",
}

REQUIRED_INVALID_CASES = {
    "MISSING_SIGNOFF_PACKET_ID_BLOCKED",
    "MISSING_SOURCE_PACKET_ID_BLOCKED",
    "MISSING_SOURCE_ESCALATION_LEVEL_BLOCKED",
    "MISSING_REQUIRED_SIGNOFF_ROLES_BLOCKED",
    "MISSING_PROVIDED_SIGNOFF_ROLES_BLOCKED",
    "MISSING_SIGNER_IDENTITY_BLOCKED",
    "MISSING_SIGNER_AUTHORITY_ATTESTATION_BLOCKED",
    "SIGNOFF_STATUS_NOT_APPROVED_BLOCKED",
    "MISSING_SIGNOFF_TIMESTAMP_BLOCKED",
    "MISSING_EVIDENCE_REFERENCE_BLOCKED",
    "ROLE_MISMATCH_BLOCKED",
    "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED",
    "MISSING_ROLLBACK_ACKNOWLEDGEMENT_BLOCKED",
    "PROVIDER_UNLOCK_REQUESTED_BLOCKED",
    "ODDS_UNLOCK_REQUESTED_BLOCKED",
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED",
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKED",
    "EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKED",
    "LIVE_OR_PAID_API_REQUESTED_BLOCKED",
    "SIGNOFF_FOR_CRITICAL_STOP_WITH_UNLOCK_REQUEST_BLOCKED",
    "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKED",
}

FINAL_CLASSIFICATIONS = {
    "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_READY_WITH_BLOCKERS",
    "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_BLOCKED_BY_MISSING_ARTIFACTS",
    "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p133_summary_exists():
    assert Path(P133_PATH).exists(), "P133 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P133_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_status_and_counts_match_p132():
    p132 = load_json(P132_PATH)
    p133 = load_json(P133_PATH)

    assert p133["source_escalation_router_status"] == p132["escalation_router_status"]
    assert p133["source_escalation_card_count"] == len(p132["escalation_cards"])


def test_schema_fields_and_valid_template():
    d = load_json(P133_PATH)

    assert set(d["signoff_packet_schema"].keys()) == REQUIRED_SCHEMA_FIELDS
    assert set(d["valid_signoff_packet_template"].keys()) == REQUIRED_SCHEMA_FIELDS
    assert d["signoff_verdict_matrix"]["VALID_SIGNOFF_PACKET_TEMPLATE"]["status"] == "GOVERNANCE_ONLY_PENDING_REVIEW"

    valid = d["valid_signoff_packet_template"]
    assert valid["provider_unlock_requested"] is False
    assert valid["odds_unlock_requested"] is False
    assert valid["recommendation_unlock_requested"] is False
    assert valid["production_unlock_requested"] is False
    assert valid["ev_clv_kelly_unlock_requested"] is False
    assert valid["live_or_paid_api_requested"] is False


def test_invalid_cases_covered_and_all_blocked():
    d = load_json(P133_PATH)

    cases = {row["case_id"] for row in d["invalid_signoff_packet_cases"]}
    assert cases == REQUIRED_INVALID_CASES

    for row in d["invalid_signoff_packet_cases"]:
        assert row["status"] == "BLOCKED"
        assert len(row["blockers"]) >= 1
        assert d["signoff_verdict_matrix"][row["case_id"]]["status"] == "BLOCKED"


def test_coverage_and_required_evidence_matrices():
    d = load_json(P133_PATH)

    for level, row in d["escalation_level_coverage_matrix"].items():
        assert row["coverage_status"] == "REQUIRED"
        assert row["all_roles_must_be_present"] is True
        assert len(row["required_roles"]) >= 1

    for level, row in d["required_evidence_matrix"].items():
        assert len(row["required_roles"]) >= 1
        assert "signer_identity_by_role" in row["required_evidence_fields"]
        assert "signer_authority_attestation_by_role" in row["required_evidence_fields"]
        assert "signoff_status_by_role" in row["required_evidence_fields"]
        assert "signoff_timestamp_by_role" in row["required_evidence_fields"]
        assert "evidence_reference_by_role" in row["required_evidence_fields"]
        assert row["non_unlock_attestation_required"] is True
        assert row["rollback_acknowledgement_required"] is True


def test_governance_invariants_remain_safe():
    d = load_json(P133_PATH)
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


def test_regression_status_and_final_classification():
    d = load_json(P133_PATH)

    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_READY_WITH_BLOCKERS"
