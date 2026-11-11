# P130 Baseline Change Review Packet Validator - Dedicated Test
import json
from pathlib import Path

P130_PATH = "data/mlb_2026/derived/p130_baseline_change_review_packet_validator_summary.json"

REQUIRED_PACKET_FIELDS = {
    "baseline_change_request_id",
    "baseline_change_owner",
    "baseline_change_reason",
    "source_fixture_version_before",
    "source_fixture_version_after",
    "old_fingerprint",
    "new_fingerprint",
    "rule_change_summary",
    "expected_verdict_delta",
    "reviewer_approval_status",
    "reviewer_identity",
    "approval_timestamp",
    "rollback_plan",
    "non_unlock_attestation",
    "production_unlock_requested",
    "recommendation_unlock_requested",
    "provider_unlock_requested",
    "real_odds_ingestion_requested",
    "live_or_paid_api_requested",
}

REQUIRED_INVALID_CASES = {
    "MISSING_BASELINE_CHANGE_REQUEST_ID_BLOCKED",
    "MISSING_BASELINE_CHANGE_OWNER_BLOCKED",
    "MISSING_BASELINE_CHANGE_REASON_BLOCKED",
    "MISSING_SOURCE_FIXTURE_VERSION_BEFORE_BLOCKED",
    "MISSING_SOURCE_FIXTURE_VERSION_AFTER_BLOCKED",
    "MISSING_OLD_FINGERPRINT_BLOCKED",
    "MISSING_NEW_FINGERPRINT_BLOCKED",
    "MISSING_RULE_CHANGE_SUMMARY_BLOCKED",
    "MISSING_EXPECTED_VERDICT_DELTA_BLOCKED",
    "REVIEWER_APPROVAL_NOT_APPROVED_BLOCKED",
    "MISSING_REVIEWER_IDENTITY_BLOCKED",
    "MISSING_APPROVAL_TIMESTAMP_BLOCKED",
    "MISSING_ROLLBACK_PLAN_BLOCKED",
    "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED",
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKED",
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED",
    "PROVIDER_UNLOCK_REQUESTED_BLOCKED",
    "REAL_ODDS_INGESTION_REQUESTED_BLOCKED",
    "LIVE_OR_PAID_API_REQUESTED_BLOCKED",
    "SAME_OLD_AND_NEW_FINGERPRINT_BLOCKED",
    "EMPTY_RULE_CHANGE_WITH_FINGERPRINT_CHANGE_BLOCKED",
}

FINAL_CLASSIFICATIONS = {
    "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_READY_WITH_BLOCKERS",
    "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_BLOCKED_BY_MISSING_ARTIFACTS",
    "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p130_summary_exists():
    assert Path(P130_PATH).exists(), "P130 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P130_PATH)
    for key in (
        "baseline_change_review_validator_status",
        "source_replay_drift_alert_contract_status",
        "required_packet_fields",
        "valid_packet_template",
        "invalid_packet_cases",
        "packet_validation_rules",
        "packet_verdict_matrix",
        "missing_field_blockers",
        "unauthorized_change_blockers",
        "baseline_fingerprint_change_rules",
        "fixture_version_change_rules",
        "rule_change_summary_rules",
        "expected_verdict_delta_rules",
        "reviewer_approval_rules",
        "rollback_plan_rules",
        "non_unlock_attestation_rules",
        "allowed_next_actions",
        "prohibited_actions",
        "blockers",
        "final_classification",
        "governance_invariants",
        "regression_status",
        "governance_statement",
    ):
        assert key in d, f"Missing section: {key}"


def test_source_contract_status_and_required_fields():
    d = load_json(P130_PATH)
    assert d["source_replay_drift_alert_contract_status"] == "READY_WITH_BLOCKERS"
    assert set(d["required_packet_fields"]) == REQUIRED_PACKET_FIELDS


def test_valid_packet_is_schema_valid_pending_review():
    d = load_json(P130_PATH)
    valid_verdict = d["packet_verdict_matrix"]["VALID_PACKET_TEMPLATE"]
    assert valid_verdict["status"] == "SCHEMA_VALID_PENDING_REVIEW"
    assert valid_verdict["blockers"] == []


def test_invalid_case_coverage_and_blocked_status():
    d = load_json(P130_PATH)
    case_ids = {row["case_id"] for row in d["invalid_packet_cases"]}
    assert case_ids == REQUIRED_INVALID_CASES

    for row in d["invalid_packet_cases"]:
        assert row["status"] == "BLOCKED"
        assert len(row["blockers"]) >= 1

    for case_id in REQUIRED_INVALID_CASES:
        assert d["packet_verdict_matrix"][case_id]["status"] == "BLOCKED"


def test_governance_statement_and_non_unlock_attestation_rule():
    d = load_json(P130_PATH)
    assert "does not imply legal provider approval or production readiness" in d["governance_statement"]
    assert "required_statement" in d["non_unlock_attestation_rules"]


def test_governance_invariants_are_safe():
    d = load_json(P130_PATH)
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


def test_regression_policy_and_final_classification():
    d = load_json(P130_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_READY_WITH_BLOCKERS"
