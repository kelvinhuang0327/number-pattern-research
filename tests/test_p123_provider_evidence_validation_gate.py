# P123 Provider Evidence Validation Gate - Dedicated Test
import json
from pathlib import Path

P123_PATH = "data/mlb_2026/derived/p123_provider_evidence_validation_gate_summary.json"

FINAL_CLASSIFICATIONS = {
    "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_READY_BLOCKS_PLACEHOLDER_AUTHORIZATION",
    "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_BLOCKED_BY_MISSING_P121_OR_P122",
    "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_FAILED_VALIDATION",
}

REQUIRED_FIELDS = [
    "provider_evidence_validation_status",
    "provider_approved",
    "authorization_evidence_present",
    "placeholder_detected",
    "placeholder_allowed_as_authorization",
    "legal_document_present",
    "license_scope_present",
    "market_scope_present",
    "source_trace_present",
    "audit_requirements_present",
    "secret_or_auth_url_detected",
    "real_legal_odds_ingested",
    "recommendation_unlock_allowed",
    "production_unlock_allowed",
    "blockers",
    "prohibited_actions",
    "allowed_next_actions",
    "regression_status",
    "governance_invariants",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p123_summary_exists():
    assert Path(P123_PATH).exists(), "P123 summary JSON missing"


def test_required_fields_exist():
    d = load_json(P123_PATH)
    for k in REQUIRED_FIELDS:
        assert k in d, f"Missing field: {k}"


def test_gate_blocks_placeholder_authorization():
    d = load_json(P123_PATH)
    assert d["provider_evidence_validation_status"] == "BLOCKED"
    assert d["placeholder_detected"] is True
    assert d["placeholder_allowed_as_authorization"] is False


def test_core_authorization_flags_blocked():
    d = load_json(P123_PATH)
    assert d["provider_approved"] is False
    assert d["authorization_evidence_present"] is False
    assert d["real_legal_odds_ingested"] is False
    assert d["recommendation_unlock_allowed"] is False
    assert d["production_unlock_allowed"] is False


def test_required_document_and_scope_fields_absent_for_now():
    d = load_json(P123_PATH)
    assert d["legal_document_present"] is False
    # Scope definitions may exist as required-field schema but are not valid legal approval evidence.
    assert d["license_scope_present"] is True
    assert d["market_scope_present"] is True
    assert d["source_trace_present"] is True
    assert d["audit_requirements_present"] is True


def test_sensitive_content_not_detected():
    d = load_json(P123_PATH)
    assert d["secret_or_auth_url_detected"] is False


def test_governance_invariants_are_safe():
    d = load_json(P123_PATH)
    g = d["governance_invariants"]
    assert g["paper_only"] is True
    assert g["diagnostic_only"] is True
    assert g["production_ready"] is False
    assert g["real_bet_allowed"] is False
    assert g["recommendation_allowed"] is False
    assert g["placeholder_allowed_as_authorization"] is False
    assert g["provider_approved"] is False
    assert g["authorization_evidence_present"] is False
    assert g["real_legal_odds_ingested"] is False
    assert g["live_api_calls"] == 0
    assert g["paid_api_called"] is False
    assert g["ev_computed"] is False
    assert g["clv_computed"] is False
    assert g["kelly_computed"] is False
    assert g["stake_sizing"] is False
    assert g["profit_computed"] is False
    assert g["recommendation_generated"] is False


def test_regression_status_policy():
    d = load_json(P123_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"


def test_blockers_cover_required_guardrails():
    d = load_json(P123_PATH)
    blockers = set(d["blockers"])
    required = {
        "PROVIDER_APPROVAL_FALSE_BLOCKER",
        "AUTHORIZATION_EVIDENCE_MISSING_BLOCKER",
        "PLACEHOLDER_DETECTED_BLOCKER",
        "LEGAL_DOCUMENT_MISSING_BLOCKER",
        "REAL_LEGAL_ODDS_NOT_APPROVED_BLOCKER",
        "RECOMMENDATION_UNLOCK_NOT_ALLOWED_BLOCKER",
        "PRODUCTION_UNLOCK_NOT_ALLOWED_BLOCKER",
    }
    for b in required:
        assert b in blockers, f"Missing blocker: {b}"


def test_final_classification_allowed_and_expected():
    d = load_json(P123_PATH)
    final_classification = d["validation_metadata"]["final_classification"]
    assert final_classification in FINAL_CLASSIFICATIONS
    assert final_classification == "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_READY_BLOCKS_PLACEHOLDER_AUTHORIZATION"
