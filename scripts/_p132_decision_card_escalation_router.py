# P132 Decision Card Escalation Router
# Paper-only governance router that maps P131 decision cards to deterministic escalation cards.

import json
from collections import Counter
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P131_PATH = "data/mlb_2026/derived/p131_baseline_change_review_packet_runner_decision_card_summary.json"
OUT_PATH = "data/mlb_2026/derived/p132_decision_card_escalation_router_summary.json"
REPORT_PATH = "report/p132_decision_card_escalation_router_20260601.md"

REQUIRED_ESCALATION_LEVELS = [
    "INFO_GOVERNANCE_RECORD_ONLY",
    "REVIEW_REQUIRED",
    "LEGAL_REVIEW_REQUIRED",
    "CTO_REVIEW_REQUIRED",
    "CEO_REVIEW_REQUIRED",
    "BLOCKED_NO_UNLOCK_ALLOWED",
    "CRITICAL_STOP",
]

REQUIRED_SLA_CLASSES = [
    "SLA_NONE_RECORD_ONLY",
    "SLA_STANDARD_REVIEW",
    "SLA_EXPEDITED_REVIEW",
    "SLA_LEGAL_REQUIRED",
    "SLA_EXECUTIVE_REQUIRED",
    "SLA_IMMEDIATE_STOP",
]

REQUIRED_SIGNOFF_ROLES = [
    "engineering_owner",
    "cto_owner",
    "legal_owner",
    "compliance_owner",
    "ceo_owner",
    "data_rights_owner",
    "security_owner",
]

ESCALATION_POLICY_DEFINITIONS = {
    "paper_only": True,
    "diagnostic_only": True,
    "routing_mode": "DETERMINISTIC",
    "unlock_policy": "ALL_UNLOCK_FLAGS_FALSE",
    "no_live_or_paid_api_calls": True,
    "no_real_odds_ingestion": True,
    "no_provider_activation": True,
    "no_recommendation_activation": True,
    "no_production_activation": True,
}

DECISION_LEVEL_ROUTE_MAP = {
    "YELLOW_GOVERNANCE_ONLY": "REVIEW_REQUIRED",
    "RED_BLOCKED": "BLOCKED_NO_UNLOCK_ALLOWED",
}

BLOCKER_CODE_ROUTE_MAP = {
    "LEGAL_DOCUMENT_REFERENCE_MISSING_BLOCKER": "LEGAL_REVIEW_REQUIRED",
    "REVIEW_OWNER_MISSING_BLOCKER": "REVIEW_REQUIRED",
    "REVIEWER_IDENTITY_MISSING_BLOCKER": "REVIEW_REQUIRED",
    "APPROVAL_OWNER_MISSING_BLOCKER": "REVIEW_REQUIRED",
    "REVIEWER_APPROVAL_NOT_APPROVED_BLOCKER": "REVIEW_REQUIRED",
    "BASELINE_CHANGE_APPROVAL_REQUIRED_BLOCKER": "BLOCKED_NO_UNLOCK_ALLOWED",
    "ROLLBACK_PLAN_MISSING_BLOCKER": "CTO_REVIEW_REQUIRED",
    "NON_UNLOCK_ATTESTATION_MISSING_BLOCKER": "CTO_REVIEW_REQUIRED",
    "FULL_REGRESSION_NOT_RUN_BLOCKER": "REVIEW_REQUIRED",
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "PRODUCTION_UNLOCK_REQUEST_BLOCKER": "CRITICAL_STOP",
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "RECOMMENDATION_UNLOCK_REQUEST_BLOCKER": "CRITICAL_STOP",
    "PROVIDER_UNLOCK_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "PROVIDER_UNLOCK_REQUEST_BLOCKER": "CRITICAL_STOP",
    "REAL_ODDS_INGESTION_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "LIVE_OR_PAID_API_REQUESTED_BLOCKER": "CRITICAL_STOP",
    "SECRET_OR_AUTH_URL_DETECTED_BLOCKER": "CRITICAL_STOP",
    "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKER": "CRITICAL_STOP",
}

SLA_CLASS_DEFINITIONS = {
    "INFO_GOVERNANCE_RECORD_ONLY": "SLA_NONE_RECORD_ONLY",
    "REVIEW_REQUIRED": "SLA_STANDARD_REVIEW",
    "LEGAL_REVIEW_REQUIRED": "SLA_LEGAL_REQUIRED",
    "CTO_REVIEW_REQUIRED": "SLA_EXPEDITED_REVIEW",
    "CEO_REVIEW_REQUIRED": "SLA_EXECUTIVE_REQUIRED",
    "BLOCKED_NO_UNLOCK_ALLOWED": "SLA_EXPEDITED_REVIEW",
    "CRITICAL_STOP": "SLA_IMMEDIATE_STOP",
}

REQUIRED_SIGNOFF_MATRIX = {
    "INFO_GOVERNANCE_RECORD_ONLY": ["engineering_owner"],
    "REVIEW_REQUIRED": ["engineering_owner", "compliance_owner"],
    "LEGAL_REVIEW_REQUIRED": ["legal_owner", "compliance_owner", "data_rights_owner"],
    "CTO_REVIEW_REQUIRED": ["engineering_owner", "cto_owner", "security_owner"],
    "CEO_REVIEW_REQUIRED": ["ceo_owner", "cto_owner", "legal_owner", "compliance_owner"],
    "BLOCKED_NO_UNLOCK_ALLOWED": ["engineering_owner", "compliance_owner", "security_owner"],
    "CRITICAL_STOP": [
        "engineering_owner",
        "cto_owner",
        "legal_owner",
        "compliance_owner",
        "ceo_owner",
        "data_rights_owner",
        "security_owner",
    ],
}

ALLOWED_ACTIONS_BY_LEVEL = {
    "INFO_GOVERNANCE_RECORD_ONLY": [
        "Record decision card for governance evidence",
        "Keep paper_only=true and diagnostic_only=true",
    ],
    "REVIEW_REQUIRED": [
        "Collect missing review metadata",
        "Re-run governance checks without unlock",
    ],
    "LEGAL_REVIEW_REQUIRED": [
        "Attach legal evidence references",
        "Obtain legal and compliance sign-off",
    ],
    "CTO_REVIEW_REQUIRED": [
        "Provide rollback and non-unlock attestation evidence",
        "Obtain CTO/security sign-off",
    ],
    "CEO_REVIEW_REQUIRED": [
        "Escalate to executive governance committee",
        "Document final governance verdict",
    ],
    "BLOCKED_NO_UNLOCK_ALLOWED": [
        "Resolve blockers and resubmit baseline packet",
        "Keep all unlock flags false",
    ],
    "CRITICAL_STOP": [
        "Immediately stop unlock/escalation pipeline",
        "Open incident review and legal/compliance escalation",
    ],
}

BLOCKED_ACTIONS_BY_LEVEL = {
    "INFO_GOVERNANCE_RECORD_ONLY": [
        "provider_unlock",
        "odds_unlock",
        "recommendation_unlock",
        "production_unlock",
        "ev_clv_kelly_unlock",
    ],
    "REVIEW_REQUIRED": [
        "provider_unlock",
        "odds_unlock",
        "recommendation_unlock",
        "production_unlock",
        "ev_clv_kelly_unlock",
    ],
    "LEGAL_REVIEW_REQUIRED": [
        "provider_unlock",
        "odds_unlock",
        "recommendation_unlock",
        "production_unlock",
        "ev_clv_kelly_unlock",
        "legal_evidence_bypass",
    ],
    "CTO_REVIEW_REQUIRED": [
        "provider_unlock",
        "odds_unlock",
        "recommendation_unlock",
        "production_unlock",
        "ev_clv_kelly_unlock",
        "rollback_bypass",
    ],
    "CEO_REVIEW_REQUIRED": [
        "provider_unlock",
        "odds_unlock",
        "recommendation_unlock",
        "production_unlock",
        "ev_clv_kelly_unlock",
        "executive_bypass",
    ],
    "BLOCKED_NO_UNLOCK_ALLOWED": [
        "provider_unlock",
        "odds_unlock",
        "recommendation_unlock",
        "production_unlock",
        "ev_clv_kelly_unlock",
        "baseline_change_apply",
    ],
    "CRITICAL_STOP": [
        "provider_unlock",
        "odds_unlock",
        "recommendation_unlock",
        "production_unlock",
        "ev_clv_kelly_unlock",
        "live_api_call",
        "paid_api_call",
        "real_odds_ingestion",
        "baseline_change_apply",
    ],
}

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Route decision cards through governance-only escalation path",
    "Collect required sign-off evidence before any baseline change",
    "Keep full regression state explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat escalation routing as legal provider approval or production readiness",
    "Do not bypass blocker resolution and required sign-off",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P132_DECISION_CARD_ESCALATION_ROUTER_READY_WITH_BLOCKERS",
    "P132_DECISION_CARD_ESCALATION_ROUTER_BLOCKED_BY_MISSING_ARTIFACTS",
    "P132_DECISION_CARD_ESCALATION_ROUTER_FAILED_VALIDATION",
]

SEVERITY_RANK = {
    "INFO_GOVERNANCE_RECORD_ONLY": 1,
    "REVIEW_REQUIRED": 2,
    "LEGAL_REVIEW_REQUIRED": 3,
    "CTO_REVIEW_REQUIRED": 4,
    "CEO_REVIEW_REQUIRED": 5,
    "BLOCKED_NO_UNLOCK_ALLOWED": 6,
    "CRITICAL_STOP": 7,
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _pick_higher_level(current_level: str, next_level: str) -> str:
    if SEVERITY_RANK[next_level] > SEVERITY_RANK[current_level]:
        return next_level
    return current_level


def _governance_invariants(p121: dict):
    g = p121.get("governance_flags", {})
    provider_approved = g.get("provider_approved", False)
    authorization_evidence_present = g.get("authorization_evidence_present", False)
    if provider_approved is None:
        provider_approved = False
    if authorization_evidence_present is None:
        authorization_evidence_present = False

    return {
        "paper_only": bool(g.get("paper_only", False)),
        "diagnostic_only": bool(g.get("diagnostic_only", False)),
        "production_ready": bool(g.get("production_ready", False)),
        "real_bet_allowed": bool(g.get("real_bet_allowed", False)),
        "recommendation_allowed": bool(g.get("recommendation_allowed", False)),
        "provider_approved": bool(provider_approved),
        "authorization_evidence_present": bool(authorization_evidence_present),
        "placeholder_allowed_as_authorization": False,
        "real_legal_odds_ingested": bool(g.get("odds_ingested", False)),
        "live_api_calls": int(g.get("live_api_calls", 0)),
        "paid_api_called": int(g.get("paid_api_calls", 0)) > 0,
        "ev_computed": bool(g.get("ev_computed", False)),
        "clv_computed": bool(g.get("clv_computed", False)),
        "kelly_computed": bool(g.get("kelly_computed", False)),
        "stake_sizing": bool(g.get("stake_sizing", False)),
        "profit_computed": bool(g.get("profit_computed", False)),
        "recommendation_generated": bool(g.get("recommendation_generated", False)),
    }


def _next_action_by_level(level: str) -> str:
    if level == "CRITICAL_STOP":
        return "Trigger incident-style governance stop; keep all unlocks false and resolve critical blockers."
    if level == "BLOCKED_NO_UNLOCK_ALLOWED":
        return "Resolve blockers, preserve governance-only mode, and resubmit packet for review."
    if level == "CTO_REVIEW_REQUIRED":
        return "Provide rollback/non-unlock controls and complete CTO/security review."
    if level == "LEGAL_REVIEW_REQUIRED":
        return "Attach legal evidence references and complete legal/compliance review."
    if level == "CEO_REVIEW_REQUIRED":
        return "Escalate to executive review board before any baseline change discussion."
    if level == "REVIEW_REQUIRED":
        return "Complete missing review approvals/metadata and rerun governance checks."
    return "Record governance trace; keep paper-only diagnostics mode."


def _reason(card: dict, matched_blockers: list, level: str) -> str:
    if matched_blockers:
        return (
            f"Escalated by blocker route rules ({','.join(matched_blockers)}) "
            f"from source decision level {card['decision_level']} to {level}."
        )
    return f"Escalated by source decision level mapping from {card['decision_level']} to {level}."


def _build_escalation_card(card: dict):
    base_level = DECISION_LEVEL_ROUTE_MAP.get(card.get("decision_level", ""), "REVIEW_REQUIRED")
    final_level = base_level

    matched_blockers = []
    blocker_codes = sorted(card.get("blocker_codes", []))
    for code in blocker_codes:
        route = BLOCKER_CODE_ROUTE_MAP.get(code)
        if route:
            matched_blockers.append(code)
            final_level = _pick_higher_level(final_level, route)

    if card.get("source_verdict") == "BLOCKED" or card.get("verdict") == "BLOCKED":
        final_level = _pick_higher_level(final_level, "BLOCKED_NO_UNLOCK_ALLOWED")

    sla_class = SLA_CLASS_DEFINITIONS[final_level]
    required_signoff_roles = REQUIRED_SIGNOFF_MATRIX[final_level]
    blocked_actions = BLOCKED_ACTIONS_BY_LEVEL[final_level]
    allowed_actions = ALLOWED_ACTIONS_BY_LEVEL[final_level]

    return {
        "packet_id": card["packet_id"],
        "source_decision_level": card["decision_level"],
        "source_verdict": card["verdict"],
        "blocker_codes": blocker_codes,
        "escalation_level": final_level,
        "sla_class": sla_class,
        "required_signoff_roles": required_signoff_roles,
        "blocked_actions": blocked_actions,
        "allowed_actions": allowed_actions,
        "escalation_reason": _reason(card, matched_blockers, final_level),
        "next_required_action": _next_action_by_level(final_level),
        "unlock_allowed": False,
        "provider_unlock_allowed": False,
        "odds_unlock_allowed": False,
        "recommendation_unlock_allowed": False,
        "production_unlock_allowed": False,
        "ev_clv_kelly_unlock_allowed": False,
    }


def _empty_blocked_summary():
    return {
        "escalation_router_status": "BLOCKED",
        "source_decision_card_runner_status": "UNKNOWN",
        "source_evaluated_packet_count": 0,
        "source_blocked_packet_count": 0,
        "source_unexpected_approved_count": 0,
        "escalation_policy_definitions": ESCALATION_POLICY_DEFINITIONS,
        "decision_level_route_map": DECISION_LEVEL_ROUTE_MAP,
        "blocker_code_route_map": BLOCKER_CODE_ROUTE_MAP,
        "sla_class_definitions": SLA_CLASS_DEFINITIONS,
        "required_signoff_matrix": REQUIRED_SIGNOFF_MATRIX,
        "escalation_cards": [],
        "escalation_execution_matrix": {},
        "blocker_escalation_summary": {},
        "sla_summary": {},
        "signoff_requirement_summary": {},
        "blocked_action_summary": {},
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P132_DECISION_CARD_ESCALATION_ROUTER_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def main():
    missing = [path for path in (P121_PATH, P131_PATH) if not Path(path).exists()]
    if missing:
        summary = _empty_blocked_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P132 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p131 = load_json(P131_PATH)

    source_cards = sorted(p131.get("decision_cards", []), key=lambda x: x.get("packet_id", ""))
    escalation_cards = [_build_escalation_card(card) for card in source_cards]

    escalation_execution_matrix = {}
    for card in escalation_cards:
        escalation_execution_matrix[card["packet_id"]] = {
            "source_verdict": card["source_verdict"],
            "escalation_level": card["escalation_level"],
            "sla_class": card["sla_class"],
            "unlock_allowed": card["unlock_allowed"],
        }

    blocker_counter = Counter()
    for card in escalation_cards:
        for code in card["blocker_codes"]:
            blocker_counter[code] += 1

    sla_counter = Counter([c["sla_class"] for c in escalation_cards])
    role_counter = Counter()
    blocked_action_counter = Counter()

    for card in escalation_cards:
        for role in card["required_signoff_roles"]:
            role_counter[role] += 1
        for action in card["blocked_actions"]:
            blocked_action_counter[action] += 1

    governance_summary = _governance_invariants(p121)
    governance_fail = (
        governance_summary["paper_only"] is False
        or governance_summary["diagnostic_only"] is False
        or governance_summary["production_ready"] is True
        or governance_summary["real_bet_allowed"] is True
        or governance_summary["recommendation_allowed"] is True
        or governance_summary["provider_approved"] is True
        or governance_summary["authorization_evidence_present"] is True
        or governance_summary["placeholder_allowed_as_authorization"] is True
        or governance_summary["real_legal_odds_ingested"] is True
        or governance_summary["live_api_calls"] != 0
        or governance_summary["paid_api_called"] is True
        or governance_summary["ev_computed"] is True
        or governance_summary["clv_computed"] is True
        or governance_summary["kelly_computed"] is True
        or governance_summary["stake_sizing"] is True
        or governance_summary["profit_computed"] is True
        or governance_summary["recommendation_generated"] is True
    )

    blockers = sorted(set(p131.get("blockers", [])))
    blockers.extend(
        [
            "DECISION_CARD_ESCALATION_ROUTER_GOVERNANCE_ONLY_BLOCKER",
            "FULL_REGRESSION_NOT_RUN_BLOCKER",
        ]
    )
    blockers = sorted(set(blockers))

    final_classification = "P132_DECISION_CARD_ESCALATION_ROUTER_READY_WITH_BLOCKERS"
    if governance_fail or p131.get("unexpected_approved_count", 0) > 0:
        final_classification = "P132_DECISION_CARD_ESCALATION_ROUTER_FAILED_VALIDATION"

    summary = {
        "escalation_router_status": "READY_WITH_BLOCKERS",
        "source_decision_card_runner_status": p131.get("packet_runner_status", "UNKNOWN"),
        "source_evaluated_packet_count": p131.get("evaluated_packet_count", 0),
        "source_blocked_packet_count": p131.get("blocked_packet_count", 0),
        "source_unexpected_approved_count": p131.get("unexpected_approved_count", 0),
        "escalation_policy_definitions": ESCALATION_POLICY_DEFINITIONS,
        "decision_level_route_map": DECISION_LEVEL_ROUTE_MAP,
        "blocker_code_route_map": BLOCKER_CODE_ROUTE_MAP,
        "sla_class_definitions": SLA_CLASS_DEFINITIONS,
        "required_signoff_matrix": REQUIRED_SIGNOFF_MATRIX,
        "required_escalation_levels": REQUIRED_ESCALATION_LEVELS,
        "required_sla_classes": REQUIRED_SLA_CLASSES,
        "required_signoff_roles": REQUIRED_SIGNOFF_ROLES,
        "escalation_cards": escalation_cards,
        "escalation_execution_matrix": escalation_execution_matrix,
        "blocker_escalation_summary": {k: blocker_counter[k] for k in sorted(blocker_counter.keys())},
        "sla_summary": {k: sla_counter[k] for k in sorted(sla_counter.keys())},
        "signoff_requirement_summary": {k: role_counter[k] for k in sorted(role_counter.keys())},
        "blocked_action_summary": {k: blocked_action_counter[k] for k in sorted(blocked_action_counter.keys())},
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Escalation routing does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "regression_status": {
            "targeted_p118_p132_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P132 task.",
        },
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": blockers,
        "final_classification": final_classification,
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P132 Decision Card Escalation Router (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- escalation_router_status: {summary['escalation_router_status']}\n")
        f.write(f"- source_decision_card_runner_status: {summary['source_decision_card_runner_status']}\n")
        f.write(f"- source_evaluated_packet_count: {summary['source_evaluated_packet_count']}\n")
        f.write(f"- source_blocked_packet_count: {summary['source_blocked_packet_count']}\n")
        f.write(f"- source_unexpected_approved_count: {summary['source_unexpected_approved_count']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Escalation Summary\n")
        f.write(f"- sla_summary: {summary['sla_summary']}\n")
        f.write(f"- blocker_escalation_summary: {summary['blocker_escalation_summary']}\n")
        f.write(f"- signoff_requirement_summary: {summary['signoff_requirement_summary']}\n")
        f.write(f"- blocked_action_summary: {summary['blocked_action_summary']}\n\n")

        f.write("## Escalation Cards\n")
        for card in summary["escalation_cards"]:
            f.write(
                f"- {card['packet_id']}: source_verdict={card['source_verdict']} escalation_level={card['escalation_level']} sla={card['sla_class']}\n"
            )
        f.write("\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p132_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")
        f.write("\n")

        f.write("## Allowed Next Actions\n")
        for item in summary["allowed_next_actions"]:
            f.write(f"- {item}\n")

    print(f"P132 summary written to {OUT_PATH}")
    print(f"P132 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
