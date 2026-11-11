# P131 Baseline Change Review Packet Runner + Decision Card - Dedicated Test
import json
from pathlib import Path

P131_PATH = "data/mlb_2026/derived/p131_baseline_change_review_packet_runner_decision_card_summary.json"

REQUIRED_DECISION_CARD_FIELDS = {
    "packet_id",
    "packet_name",
    "packet_type",
    "verdict",
    "decision_level",
    "blocker_count",
    "blocker_codes",
    "missing_required_fields",
    "unauthorized_change_flags",
    "reviewer_approval_status",
    "reviewer_identity_status",
    "approval_timestamp_status",
    "rollback_plan_status",
    "non_unlock_attestation_status",
    "baseline_fingerprint_change_status",
    "expected_verdict_delta_status",
    "provider_unlock_allowed",
    "odds_unlock_allowed",
    "recommendation_unlock_allowed",
    "production_unlock_allowed",
    "ev_clv_kelly_unlock_allowed",
    "decision_reason",
    "next_required_action",
}

FINAL_CLASSIFICATIONS = {
    "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_READY_WITH_BLOCKERS",
    "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_BLOCKED_BY_MISSING_ARTIFACTS",
    "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p131_summary_exists():
    assert Path(P131_PATH).exists(), "P131 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P131_PATH)
    for key in (
        "packet_runner_status",
        "source_baseline_change_validator_status",
        "evaluated_packet_count",
        "approved_packet_count",
        "blocked_packet_count",
        "unexpected_approved_count",
        "decision_cards",
        "decision_card_schema",
        "packet_execution_matrix",
        "packet_blocker_summary",
        "reviewer_status_summary",
        "rollback_readiness_summary",
        "non_unlock_attestation_summary",
        "governance_invariant_summary",
        "allowed_next_actions",
        "prohibited_actions",
        "blockers",
        "final_classification",
        "regression_status",
        "governance_statement",
    ):
        assert key in d, f"Missing section: {key}"


def test_counts_and_source_status():
    d = load_json(P131_PATH)
    assert d["source_baseline_change_validator_status"] == "READY_WITH_BLOCKERS"
    assert d["evaluated_packet_count"] == len(d["decision_cards"])
    assert d["evaluated_packet_count"] == 22
    assert d["approved_packet_count"] == 0
    assert d["unexpected_approved_count"] == 0
    assert d["blocked_packet_count"] == 21


def test_decision_card_schema_and_cards():
    d = load_json(P131_PATH)
    assert set(d["decision_card_schema"].keys()) == REQUIRED_DECISION_CARD_FIELDS

    for card in d["decision_cards"]:
        assert set(card.keys()) == REQUIRED_DECISION_CARD_FIELDS
        assert card["provider_unlock_allowed"] is False
        assert card["odds_unlock_allowed"] is False
        assert card["recommendation_unlock_allowed"] is False
        assert card["production_unlock_allowed"] is False
        assert card["ev_clv_kelly_unlock_allowed"] is False

    cards_by_name = {c["packet_name"]: c for c in d["decision_cards"]}
    assert cards_by_name["VALID_PACKET_TEMPLATE"]["verdict"] == "GOVERNANCE_ONLY_PENDING"


def test_invalid_cases_blocked_and_matrix_consistent():
    d = load_json(P131_PATH)
    for name, row in d["packet_execution_matrix"].items():
        if name == "VALID_PACKET_TEMPLATE":
            assert row["verdict"] == "GOVERNANCE_ONLY_PENDING"
        else:
            assert row["verdict"] == "BLOCKED"


def test_governance_statement_and_invariants():
    d = load_json(P131_PATH)
    assert "does not imply legal provider approval" in d["governance_statement"]
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


def test_regression_policy_and_final_classification():
    d = load_json(P131_PATH)
    rs = d["regression_status"]
    assert rs["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_READY_WITH_BLOCKERS"
