# P124 Legal Evidence Completeness Contract - Dedicated Test
import json
from pathlib import Path

P124_PATH = "data/mlb_2026/derived/p124_legal_evidence_completeness_contract_summary.json"

FINAL_CLASSIFICATIONS = {
    "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_READY_WITH_BLOCKERS",
    "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_BLOCKED_BY_MISSING_P121_OR_P123",
    "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_FAILED_VALIDATION",
}

REQUIRED_TOP_LEVEL = [
    "legal_evidence_contract_status",
    "required_legal_document_fields",
    "required_license_scope_fields",
    "required_market_scope_fields",
    "required_source_trace_fields",
    "required_audit_fields",
    "required_effective_date_fields",
    "required_expiration_or_renewal_fields",
    "required_provider_identity_fields",
    "required_data_usage_scope_fields",
    "required_restriction_fields",
    "required_secret_exclusion_rules",
    "required_repository_safety_rules",
    "completeness_validation_rules",
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


def test_p124_summary_exists():
    assert Path(P124_PATH).exists(), "P124 summary JSON missing"


def test_required_sections_exist():
    d = load_json(P124_PATH)
    for k in REQUIRED_TOP_LEVEL:
        assert k in d, f"Missing section: {k}"


def test_required_contract_fields_cover_prompt_requirements():
    d = load_json(P124_PATH)
    legal_fields = set(d["required_legal_document_fields"])
    provider_fields = set(d["required_provider_identity_fields"])
    market_fields = set(d["required_market_scope_fields"])
    usage_fields = set(d["required_data_usage_scope_fields"])
    date_fields = set(d["required_effective_date_fields"]) | set(d["required_expiration_or_renewal_fields"])
    secret_rules = set(d["required_secret_exclusion_rules"])

    assert "legal_document_reference_id" in legal_fields or "legal_document_external_reference" in legal_fields
    assert "provider_legal_name" in provider_fields
    assert "provider_approval_status" in provider_fields
    assert "authorized_sports" in market_fields
    assert "authorized_leagues_or_competitions" in market_fields
    assert "authorized_markets" in market_fields
    assert "authorized_data_types" in set(d["required_license_scope_fields"])
    assert "authorized_usage_scope" in set(d["required_license_scope_fields"])
    assert "authorized_environment_scope" in usage_fields
    assert "effective_date" in date_fields
    assert "expiration_date" in date_fields or "renewal_review_required" in date_fields
    assert "no_secrets_in_repo" in secret_rules
    assert "no_api_keys_in_repo" in secret_rules
    assert "no_auth_urls_in_repo" in secret_rules
    assert "no_private_contract_body_in_repo" in secret_rules


def test_placeholder_rejection_and_blocked_state():
    d = load_json(P124_PATH)
    assert d["placeholder_detected"] is True
    assert d["placeholder_allowed_as_authorization"] is False
    assert d["provider_approved"] is False
    assert d["authorization_evidence_present"] is False


def test_governance_invariants_are_safe():
    d = load_json(P124_PATH)
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


def test_blockers_cover_required_blocked_states():
    d = load_json(P124_PATH)
    blockers = set(d["blockers"])
    required = {
        "LEGAL_DOCUMENT_REFERENCE_MISSING_BLOCKER",
        "PROVIDER_IDENTITY_MISSING_BLOCKER",
        "LICENSE_SCOPE_MISSING_BLOCKER",
        "MARKET_SCOPE_MISSING_BLOCKER",
        "DATA_USAGE_SCOPE_MISSING_BLOCKER",
        "EFFECTIVE_DATE_MISSING_BLOCKER",
        "EXPIRATION_OR_RENEWAL_FIELD_MISSING_BLOCKER",
        "APPROVAL_OWNER_MISSING_BLOCKER",
        "AUDIT_OR_SOURCE_TRACE_MISSING_BLOCKER",
        "PLACEHOLDER_DETECTED_BLOCKER",
        "SECRET_OR_AUTH_URL_DETECTED_BLOCKER",
        "PRODUCTION_OR_RECOMMENDATION_UNLOCK_WITHOUT_APPROVAL_BLOCKER",
    }
    for b in required:
        assert b in blockers, f"Missing blocker: {b}"


def test_regression_status_policy():
    d = load_json(P124_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"


def test_final_classification_allowed_and_expected():
    d = load_json(P124_PATH)
    final_classification = d["contract_metadata"]["final_classification"]
    assert final_classification in FINAL_CLASSIFICATIONS
    assert final_classification == "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_READY_WITH_BLOCKERS"
