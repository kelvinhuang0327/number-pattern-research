# P127 Intake Payload Evaluation Runner + Deterministic Gate Verdict Report - Dedicated Test
import json
from pathlib import Path

P127_PATH = "data/mlb_2026/derived/p127_intake_payload_evaluation_runner_verdict_report_summary.json"

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
    "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_READY_WITH_BLOCKERS",
    "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_BLOCKED_BY_MISSING_ARTIFACTS",
    "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p127_summary_exists():
    assert Path(P127_PATH).exists(), "P127 summary JSON missing"


def test_required_top_level_sections():
    d = load_json(P127_PATH)
    for key in (
        "evaluation_runner_status",
        "deterministic_verdict_status",
        "evaluated_fixture_count",
        "expected_blocked_count",
        "actual_blocked_count",
        "unexpected_allowed_count",
        "verdicts",
        "rule_evaluation_matrix",
        "blocked_reason_matrix",
        "unlock_prevention_matrix",
        "reproducibility_metadata",
        "allowed_next_actions",
        "prohibited_actions",
        "blockers",
        "final_classification",
    ):
        assert key in d, f"Missing section: {key}"


def test_required_verdict_cases_present_and_blocked():
    d = load_json(P127_PATH)
    case_ids = {v["case_id"] for v in d["verdicts"]}
    for c in REQUIRED_CASES:
        assert c in case_ids, f"Missing required case: {c}"

    for v in d["verdicts"]:
        assert v["status"] == "BLOCKED"
        assert v["provider_approved"] is False
        assert v["authorization_evidence_present"] is False
        assert v["recommendation_unlock_allowed"] is False
        assert v["production_unlock_allowed"] is False
        assert v["ev_unlock_allowed"] is False
        assert v["clv_unlock_allowed"] is False
        assert v["kelly_unlock_allowed"] is False
        assert v["stake_unlock_allowed"] is False
        assert v["profit_unlock_allowed"] is False
        assert v["real_legal_odds_ingested"] is False
        assert v["live_api_calls"] == 0
        assert v["paid_api_called"] is False
        assert len(v["rule_ids"]) >= 1
        assert len(v["blocked_reasons"]) >= 1


def test_count_consistency_and_unexpected_allowed_zero():
    d = load_json(P127_PATH)
    assert d["evaluated_fixture_count"] == len(d["verdicts"])
    assert d["expected_blocked_count"] == d["evaluated_fixture_count"]
    assert d["actual_blocked_count"] == d["evaluated_fixture_count"]
    assert d["unexpected_allowed_count"] == 0


def test_rule_matrix_and_unlock_matrix_cover_all_cases():
    d = load_json(P127_PATH)
    verdict_cases = {v["case_id"] for v in d["verdicts"]}
    assert set(d["rule_evaluation_matrix"].keys()) == verdict_cases
    assert set(d["blocked_reason_matrix"].keys()) == verdict_cases
    assert set(d["unlock_prevention_matrix"].keys()) == verdict_cases

    for case_id, rows in d["rule_evaluation_matrix"].items():
        assert len(rows) >= 1, f"No rules evaluated for {case_id}"
        for row in rows:
            assert row["triggered"] is True
            assert row["result"] == "BLOCKED"
            assert row["rule_id"].startswith("R")


def test_governance_invariants_are_safe():
    d = load_json(P127_PATH)
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


def test_reproducibility_metadata_present():
    d = load_json(P127_PATH)
    r = d["reproducibility_metadata"]
    assert r["runner_version"] == "P127.20260601"
    assert len(r["deterministic_hash_sha256"]) == 64
    assert r["source_p121_reference"].endswith("p121_provider_authorization_evidence_placeholder_summary.json")
    assert r["source_p126_reference"].endswith("p126_legal_evidence_intake_payload_fixture_negative_cases_summary.json")


def test_regression_status_policy_and_classification():
    d = load_json(P127_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_READY_WITH_BLOCKERS"
