# P132 Decision Card Escalation Router - Dedicated Test
import json
from pathlib import Path

P131_PATH = "data/mlb_2026/derived/p131_baseline_change_review_packet_runner_decision_card_summary.json"
P132_PATH = "data/mlb_2026/derived/p132_decision_card_escalation_router_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "escalation_router_status",
    "source_decision_card_runner_status",
    "source_evaluated_packet_count",
    "source_blocked_packet_count",
    "source_unexpected_approved_count",
    "escalation_policy_definitions",
    "decision_level_route_map",
    "blocker_code_route_map",
    "sla_class_definitions",
    "required_signoff_matrix",
    "escalation_cards",
    "escalation_execution_matrix",
    "blocker_escalation_summary",
    "sla_summary",
    "signoff_requirement_summary",
    "blocked_action_summary",
    "allowed_next_actions",
    "prohibited_actions",
    "blockers",
    "final_classification",
    "governance_invariant_summary",
    "governance_statement",
    "regression_status",
}

REQUIRED_ESCALATION_CARD_FIELDS = {
    "packet_id",
    "source_decision_level",
    "source_verdict",
    "blocker_codes",
    "escalation_level",
    "sla_class",
    "required_signoff_roles",
    "blocked_actions",
    "allowed_actions",
    "escalation_reason",
    "next_required_action",
    "unlock_allowed",
    "provider_unlock_allowed",
    "odds_unlock_allowed",
    "recommendation_unlock_allowed",
    "production_unlock_allowed",
    "ev_clv_kelly_unlock_allowed",
}

REQUIRED_ESCALATION_LEVELS = {
    "INFO_GOVERNANCE_RECORD_ONLY",
    "REVIEW_REQUIRED",
    "LEGAL_REVIEW_REQUIRED",
    "CTO_REVIEW_REQUIRED",
    "CEO_REVIEW_REQUIRED",
    "BLOCKED_NO_UNLOCK_ALLOWED",
    "CRITICAL_STOP",
}

REQUIRED_SLA_CLASSES = {
    "SLA_NONE_RECORD_ONLY",
    "SLA_STANDARD_REVIEW",
    "SLA_EXPEDITED_REVIEW",
    "SLA_LEGAL_REQUIRED",
    "SLA_EXECUTIVE_REQUIRED",
    "SLA_IMMEDIATE_STOP",
}

REQUIRED_SIGNOFF_ROLES = {
    "engineering_owner",
    "cto_owner",
    "legal_owner",
    "compliance_owner",
    "ceo_owner",
    "data_rights_owner",
    "security_owner",
}

REQUIRED_BLOCKER_ROUTE_RULES = {
    "LEGAL_DOCUMENT_REFERENCE_MISSING_BLOCKER": "LEGAL_REVIEW_REQUIRED",
    "REVIEW_OWNER_MISSING_BLOCKER": "REVIEW_REQUIRED",
    "ROLLBACK_PLAN_MISSING_BLOCKER": "CTO_REVIEW_REQUIRED",
    "NON_UNLOCK_ATTESTATION_MISSING_BLOCKER": "CTO_REVIEW_REQUIRED",
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "PROVIDER_UNLOCK_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "REAL_ODDS_INGESTION_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "LIVE_OR_PAID_API_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "SECRET_OR_AUTH_URL_DETECTED_BLOCKER": "CRITICAL_STOP",
    "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKER": "CRITICAL_STOP",
    "BASELINE_CHANGE_APPROVAL_REQUIRED_BLOCKER": "BLOCKED_NO_UNLOCK_ALLOWED",
    "FULL_REGRESSION_NOT_RUN_BLOCKER": "REVIEW_REQUIRED",
}

FINAL_CLASSIFICATIONS = {
    "P132_DECISION_CARD_ESCALATION_ROUTER_READY_WITH_BLOCKERS",
    "P132_DECISION_CARD_ESCALATION_ROUTER_BLOCKED_BY_MISSING_ARTIFACTS",
    "P132_DECISION_CARD_ESCALATION_ROUTER_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p132_summary_exists():
    assert Path(P132_PATH).exists(), "P132 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P132_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_counts_match_p131():
    p131 = load_json(P131_PATH)
    p132 = load_json(P132_PATH)

    assert p132["source_decision_card_runner_status"] == p131["packet_runner_status"]
    assert p132["source_evaluated_packet_count"] == p131["evaluated_packet_count"]
    assert p132["source_blocked_packet_count"] == p131["blocked_packet_count"]
    assert p132["source_unexpected_approved_count"] == p131["unexpected_approved_count"]


def test_required_route_and_sla_definitions_present():
    d = load_json(P132_PATH)

    assert REQUIRED_ESCALATION_LEVELS.issubset(set(d["required_escalation_levels"]))
    assert REQUIRED_SLA_CLASSES.issubset(set(d["required_sla_classes"]))
    assert REQUIRED_SIGNOFF_ROLES.issubset(set(d["required_signoff_roles"]))

    for k, v in REQUIRED_BLOCKER_ROUTE_RULES.items():
        assert d["blocker_code_route_map"][k] == v


def test_one_escalation_card_per_source_card_and_unlocks_false():
    p131 = load_json(P131_PATH)
    p132 = load_json(P132_PATH)

    source_ids = sorted([c["packet_id"] for c in p131["decision_cards"]])
    routed_ids = sorted([c["packet_id"] for c in p132["escalation_cards"]])
    assert routed_ids == source_ids

    for card in p132["escalation_cards"]:
        assert set(card.keys()) == REQUIRED_ESCALATION_CARD_FIELDS
        assert card["unlock_allowed"] is False
        assert card["provider_unlock_allowed"] is False
        assert card["odds_unlock_allowed"] is False
        assert card["recommendation_unlock_allowed"] is False
        assert card["production_unlock_allowed"] is False
        assert card["ev_clv_kelly_unlock_allowed"] is False


def test_blocked_packets_remain_blocked_and_valid_template_non_production_ready():
    p132 = load_json(P132_PATH)

    for card in p132["escalation_cards"]:
        if card["source_verdict"] == "BLOCKED":
            assert card["escalation_level"] in {"BLOCKED_NO_UNLOCK_ALLOWED", "CRITICAL_STOP"}

    valid_template = [c for c in p132["escalation_cards"] if c["packet_id"] == "P130_VALID_TEMPLATE"][0]
    assert valid_template["source_verdict"] == "GOVERNANCE_ONLY_PENDING"
    assert valid_template["escalation_level"] in {"REVIEW_REQUIRED", "BLOCKED_NO_UNLOCK_ALLOWED"}
    assert valid_template["production_unlock_allowed"] is False


def test_governance_invariants_remain_safe():
    d = load_json(P132_PATH)
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
    d = load_json(P132_PATH)

    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P132_DECISION_CARD_ESCALATION_ROUTER_READY_WITH_BLOCKERS"
