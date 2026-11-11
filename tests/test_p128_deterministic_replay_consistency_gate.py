# P128 Deterministic Replay Consistency Gate - Dedicated Test
import json
from pathlib import Path

P128_PATH = "data/mlb_2026/derived/p128_deterministic_replay_consistency_gate_summary.json"

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
    "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS",
    "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p128_summary_exists():
    assert Path(P128_PATH).exists(), "P128 summary JSON missing"


def test_required_top_level_sections():
    d = load_json(P128_PATH)
    for key in (
        "replay_consistency_gate_status",
        "replay_run_count",
        "source_fixture_count",
        "baseline_fingerprint",
        "replay_fingerprints",
        "fingerprint_consistency_status",
        "verdict_consistency_status",
        "blocked_reason_consistency_status",
        "rule_matrix_consistency_status",
        "unlock_prevention_consistency_status",
        "drift_detected",
        "drift_details",
        "replay_verdict_matrix",
        "replay_blocked_reason_matrix",
        "replay_unlock_prevention_matrix",
        "reproducibility_metadata",
        "allowed_next_actions",
        "prohibited_actions",
        "blockers",
        "final_classification",
        "governance_invariants",
        "regression_status",
    ):
        assert key in d, f"Missing section: {key}"


def test_replay_counts_and_fingerprint_consistency():
    d = load_json(P128_PATH)
    assert d["replay_run_count"] >= 3
    assert d["source_fixture_count"] == 19
    assert len(d["replay_fingerprints"]) == d["replay_run_count"]
    assert len(d["baseline_fingerprint"]) == 64

    fps = [x["fingerprint"] for x in d["replay_fingerprints"]]
    assert all(len(x) == 64 for x in fps)
    assert len(set(fps)) == 1
    assert d["fingerprint_consistency_status"] == "CONSISTENT"


def test_consistency_statuses_and_no_drift():
    d = load_json(P128_PATH)
    assert d["verdict_consistency_status"] == "CONSISTENT"
    assert d["blocked_reason_consistency_status"] == "CONSISTENT"
    assert d["rule_matrix_consistency_status"] == "CONSISTENT"
    assert d["unlock_prevention_consistency_status"] == "CONSISTENT"
    assert d["drift_detected"] is False
    assert d["drift_details"] == []


def test_every_run_preserves_expected_counts():
    d = load_json(P128_PATH)
    for row in d["replay_fingerprints"]:
        assert row["evaluated_fixture_count"] == 19
        assert row["expected_blocked_count"] == 19
        assert row["actual_blocked_count"] == 19
        assert row["unexpected_allowed_count"] == 0


def test_replay_matrices_cover_required_cases():
    d = load_json(P128_PATH)
    for run_id, verdict_matrix in d["replay_verdict_matrix"].items():
        assert set(verdict_matrix.keys()) == REQUIRED_CASES
        assert all(status == "BLOCKED" for status in verdict_matrix.values())

    for run_id, blocked_matrix in d["replay_blocked_reason_matrix"].items():
        assert set(blocked_matrix.keys()) == REQUIRED_CASES
        for reasons in blocked_matrix.values():
            assert len(reasons) >= 1

    for run_id, unlock_matrix in d["replay_unlock_prevention_matrix"].items():
        assert set(unlock_matrix.keys()) == REQUIRED_CASES
        for row in unlock_matrix.values():
            assert row["recommendation_unlock_allowed"] is False
            assert row["production_unlock_allowed"] is False
            assert row["ev_unlock_allowed"] is False
            assert row["clv_unlock_allowed"] is False
            assert row["kelly_unlock_allowed"] is False
            assert row["stake_unlock_allowed"] is False
            assert row["profit_unlock_allowed"] is False


def test_governance_invariants_are_safe():
    d = load_json(P128_PATH)
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


def test_regression_policy_and_classification():
    d = load_json(P128_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS"
