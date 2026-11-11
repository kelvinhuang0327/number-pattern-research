# P126 Legal Evidence Intake Payload Fixture + Negative Gate Cases - Dedicated Test
import json
from pathlib import Path

P126_PATH = "data/mlb_2026/derived/p126_legal_evidence_intake_payload_fixture_negative_cases_summary.json"

REQUIRED_CASES = {
    "VALID_SCHEMA_BUT_NOT_APPROVED_BLOCKED",
    "MISSING_LEGAL_DOCUMENT_REFERENCE_BLOCKED",
    "MISSING_REVIEW_OWNER_BLOCKED",
    "MISSING_APPROVAL_OWNER_BLOCKED",
    "REVIEW_STATUS_NOT_APPROVED_BLOCKED",
    "PLACEHOLDER_AS_EVIDENCE_BLOCKED",
    "PROVIDER_IDENTITY_MISSING_BLOCKED",
    "MARKET_SCOPE_MISSING_BLOCKED",
    "DATA_USAGE_SCOPE_MISSING_BLOCKED",
    "EFFECTIVE_DATE_MISSING_BLOCKED",
    "EXPIRATION_OR_RENEWAL_MISSING_BLOCKED",
    "SOURCE_TRACE_MISSING_BLOCKED",
    "AUDIT_TRAIL_MISSING_BLOCKED",
    "SECRET_OR_AUTH_URL_PRESENT_BLOCKED",
    "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKED",
    "ROW_LEVEL_PROPRIETARY_ODDS_PRESENT_BLOCKED",
    "RECOMMENDATION_UNLOCK_REQUEST_BLOCKED",
    "PRODUCTION_UNLOCK_REQUEST_BLOCKED",
    "EV_CLV_KELLY_UNLOCK_REQUEST_BLOCKED",
}

FINAL_CLASSIFICATIONS = {
    "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_READY_WITH_BLOCKERS",
    "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_BLOCKED_BY_MISSING_P121_OR_P125",
    "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p126_summary_exists():
    assert Path(P126_PATH).exists(), "P126 summary JSON missing"


def test_required_top_level_sections():
    d = load_json(P126_PATH)
    for key in (
        "fixture_status",
        "negative_gate_case_status",
        "valid_minimal_payload_template",
        "negative_cases",
        "expected_gate_results",
        "blocked_reason_matrix",
        "placeholder_rejection_cases",
        "review_owner_failure_cases",
        "approval_workflow_failure_cases",
        "legal_document_reference_failure_cases",
        "scope_failure_cases",
        "date_failure_cases",
        "source_trace_failure_cases",
        "repository_safety_failure_cases",
        "secret_detection_failure_cases",
        "unlock_request_failure_cases",
        "allowed_next_actions",
        "prohibited_actions",
        "blockers",
        "governance_invariants",
        "regression_status",
    ):
        assert key in d, f"Missing section: {key}"


def test_all_required_negative_cases_present():
    d = load_json(P126_PATH)
    case_ids = {c["case_id"] for c in d["negative_cases"]}
    for c in REQUIRED_CASES:
        assert c in case_ids, f"Missing required case: {c}"


def test_every_case_expected_blocked():
    d = load_json(P126_PATH)
    for r in d["expected_gate_results"]:
        assert r["expected_status"] == "BLOCKED"
        assert r["expected_provider_approved"] is False
        assert r["expected_authorization_evidence_present"] is False
        assert r["expected_recommendation_unlock_allowed"] is False
        assert r["expected_production_unlock_allowed"] is False
        assert r["expected_real_legal_odds_ingested"] is False


def test_governance_invariants_are_safe():
    d = load_json(P126_PATH)
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


def test_required_case_buckets_non_empty():
    d = load_json(P126_PATH)
    for key in (
        "placeholder_rejection_cases",
        "review_owner_failure_cases",
        "approval_workflow_failure_cases",
        "legal_document_reference_failure_cases",
        "scope_failure_cases",
        "date_failure_cases",
        "source_trace_failure_cases",
        "repository_safety_failure_cases",
        "secret_detection_failure_cases",
        "unlock_request_failure_cases",
    ):
        assert len(d[key]) >= 1, f"Bucket should not be empty: {key}"


def test_regression_status_policy():
    d = load_json(P126_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"


def test_final_classification_allowed_and_expected():
    d = load_json(P126_PATH)
    fc = d["fixture_metadata"]["final_classification"]
    assert fc in FINAL_CLASSIFICATIONS
    assert fc == "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_READY_WITH_BLOCKERS"
