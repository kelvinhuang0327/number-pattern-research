# P125 Legal Evidence Intake Schema + Review Owner Gate - Dedicated Test
import json
from pathlib import Path

P125_PATH = "data/mlb_2026/derived/p125_legal_evidence_intake_schema_review_owner_gate_summary.json"

FINAL_CLASSIFICATIONS = {
    "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_READY_WITH_BLOCKERS",
    "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_BLOCKED_BY_MISSING_P121_OR_P124",
    "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_FAILED_VALIDATION",
}

REQUIRED_TOP_LEVEL = [
    "intake_schema_status",
    "review_owner_gate_status",
    "required_intake_fields",
    "required_review_owner_fields",
    "required_approval_workflow_fields",
    "required_legal_document_reference_fields",
    "required_scope_fields",
    "required_date_fields",
    "required_provider_identity_fields",
    "required_data_rights_fields",
    "required_repository_safety_fields",
    "required_secret_exclusion_fields",
    "required_reviewer_attestation_fields",
    "intake_validation_rules",
    "review_owner_validation_rules",
    "blocked_state_rules",
    "placeholder_rejection_rules",
    "allowed_next_actions",
    "prohibited_actions",
    "blockers",
    "regression_status",
    "governance_invariants",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p125_summary_exists():
    assert Path(P125_PATH).exists(), "P125 summary JSON missing"


def test_required_sections_exist():
    d = load_json(P125_PATH)
    for k in REQUIRED_TOP_LEVEL:
        assert k in d, f"Missing section: {k}"


def test_required_intake_fields_cover_prompt_requirements():
    d = load_json(P125_PATH)
    fields = set(d["required_intake_fields"])
    required = {
        "intake_id",
        "evidence_type",
        "legal_document_reference_id",
        "provider_legal_name",
        "provider_identifier",
        "submitted_by",
        "submitted_at",
        "review_owner",
        "review_status",
        "approval_owner",
        "authorized_sports",
        "authorized_leagues",
        "authorized_markets",
        "authorized_data_types",
        "authorized_usage_scope",
        "authorized_environment",
        "effective_date",
        "source_trace_reference",
        "audit_trail_reference",
        "restriction_notes",
        "repository_storage_policy",
        "secret_exclusion_attestation",
        "private_contract_body_excluded",
        "row_level_proprietary_odds_excluded",
    }
    for k in required:
        assert k in fields, f"Missing intake field: {k}"


def test_review_owner_gate_blocking_rules_present():
    d = load_json(P125_PATH)
    rules = d["review_owner_validation_rules"]
    assert rules["review_owner_required"] is True
    assert rules["approval_owner_required"] is True
    assert rules["review_status_must_be_explicit"] is True
    blocked = d["blocked_state_rules"]
    assert blocked["missing_review_owner_blocked"] is True
    assert blocked["missing_approval_owner_blocked"] is True
    assert blocked["review_not_explicitly_approved_blocked"] is True


def test_placeholder_and_unlock_safety():
    d = load_json(P125_PATH)
    assert d["placeholder_detected"] is True
    assert d["placeholder_allowed_as_authorization"] is False
    assert d["provider_approved"] is False
    assert d["authorization_evidence_present"] is False


def test_governance_invariants_are_safe():
    d = load_json(P125_PATH)
    g = d["governance_invariants"]
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


def test_blockers_cover_required_cases():
    d = load_json(P125_PATH)
    blockers = set(d["blockers"])
    required = {
        "REVIEW_OWNER_MISSING_BLOCKER",
        "APPROVAL_OWNER_MISSING_BLOCKER",
        "REVIEW_STATUS_NOT_EXPLICITLY_APPROVED_BLOCKER",
        "LEGAL_DOCUMENT_REFERENCE_MISSING_BLOCKER",
        "PROVIDER_IDENTITY_MISSING_BLOCKER",
        "SCOPE_FIELDS_MISSING_BLOCKER",
        "EFFECTIVE_DATE_MISSING_BLOCKER",
        "EXPIRATION_OR_RENEWAL_MISSING_BLOCKER",
        "SOURCE_TRACE_OR_AUDIT_MISSING_BLOCKER",
        "SECRET_EXCLUSION_ATTESTATION_MISSING_BLOCKER",
        "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKER",
        "SECRET_OR_AUTH_URL_DETECTED_BLOCKER",
        "PLACEHOLDER_DETECTED_BLOCKER",
        "UNLOCK_REQUEST_WITHOUT_APPROVAL_BLOCKER",
    }
    for b in required:
        assert b in blockers, f"Missing blocker: {b}"


def test_regression_status_policy():
    d = load_json(P125_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"


def test_final_classification_allowed_and_expected():
    d = load_json(P125_PATH)
    fc = d["gate_metadata"]["final_classification"]
    assert fc in FINAL_CLASSIFICATIONS
    assert fc == "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_READY_WITH_BLOCKERS"
