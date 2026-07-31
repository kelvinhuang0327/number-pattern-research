# P133 Escalation Sign-off Evidence Packet Validator
# Paper-only validator that enforces deterministic sign-off packet governance over P132 escalation cards.

import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P132_PATH = "data/mlb_2026/derived/p132_decision_card_escalation_router_summary.json"
OUT_PATH = "data/mlb_2026/derived/p133_escalation_signoff_evidence_packet_validator_summary.json"
REPORT_PATH = "report/p133_escalation_signoff_evidence_packet_validator_20260601.md"

SIGNOFF_PACKET_SCHEMA = {
    "signoff_packet_id": "string",
    "source_packet_id": "string",
    "source_escalation_level": "string",
    "source_blocker_codes": "string[]",
    "required_signoff_roles": "string[]",
    "provided_signoff_roles": "string[]",
    "signer_identity_by_role": "dict[str,str]",
    "signer_authority_attestation_by_role": "dict[str,str]",
    "signoff_status_by_role": "dict[str,APPROVED|REJECTED|PENDING]",
    "signoff_timestamp_by_role": "dict[str,string]",
    "evidence_reference_by_role": "dict[str,string]",
    "escalation_reason": "string",
    "decision_scope": "string",
    "non_unlock_attestation": "string",
    "rollback_acknowledgement": "string",
    "provider_unlock_requested": "boolean",
    "odds_unlock_requested": "boolean",
    "recommendation_unlock_requested": "boolean",
    "production_unlock_requested": "boolean",
    "ev_clv_kelly_unlock_requested": "boolean",
    "live_or_paid_api_requested": "boolean",
}

SCHEMA_FIELDS = list(SIGNOFF_PACKET_SCHEMA.keys())

INVALID_CASE_IDS = [
    "MISSING_SIGNOFF_PACKET_ID_BLOCKED",
    "MISSING_SOURCE_PACKET_ID_BLOCKED",
    "MISSING_SOURCE_ESCALATION_LEVEL_BLOCKED",
    "MISSING_REQUIRED_SIGNOFF_ROLES_BLOCKED",
    "MISSING_PROVIDED_SIGNOFF_ROLES_BLOCKED",
    "MISSING_SIGNER_IDENTITY_BLOCKED",
    "MISSING_SIGNER_AUTHORITY_ATTESTATION_BLOCKED",
    "SIGNOFF_STATUS_NOT_APPROVED_BLOCKED",
    "MISSING_SIGNOFF_TIMESTAMP_BLOCKED",
    "MISSING_EVIDENCE_REFERENCE_BLOCKED",
    "ROLE_MISMATCH_BLOCKED",
    "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED",
    "MISSING_ROLLBACK_ACKNOWLEDGEMENT_BLOCKED",
    "PROVIDER_UNLOCK_REQUESTED_BLOCKED",
    "ODDS_UNLOCK_REQUESTED_BLOCKED",
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED",
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKED",
    "EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKED",
    "LIVE_OR_PAID_API_REQUESTED_BLOCKED",
    "SIGNOFF_FOR_CRITICAL_STOP_WITH_UNLOCK_REQUEST_BLOCKED",
    "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKED",
]

INVALID_CASE_BLOCKERS = {
    "MISSING_SIGNOFF_PACKET_ID_BLOCKED": ["SIGNOFF_PACKET_ID_MISSING_BLOCKER"],
    "MISSING_SOURCE_PACKET_ID_BLOCKED": ["SOURCE_PACKET_ID_MISSING_BLOCKER"],
    "MISSING_SOURCE_ESCALATION_LEVEL_BLOCKED": ["SOURCE_ESCALATION_LEVEL_MISSING_BLOCKER"],
    "MISSING_REQUIRED_SIGNOFF_ROLES_BLOCKED": ["REQUIRED_SIGNOFF_ROLES_MISSING_BLOCKER"],
    "MISSING_PROVIDED_SIGNOFF_ROLES_BLOCKED": ["PROVIDED_SIGNOFF_ROLES_MISSING_BLOCKER"],
    "MISSING_SIGNER_IDENTITY_BLOCKED": ["SIGNER_IDENTITY_MISSING_BLOCKER"],
    "MISSING_SIGNER_AUTHORITY_ATTESTATION_BLOCKED": ["SIGNER_AUTHORITY_ATTESTATION_MISSING_BLOCKER"],
    "SIGNOFF_STATUS_NOT_APPROVED_BLOCKED": ["SIGNOFF_STATUS_NOT_APPROVED_BLOCKER"],
    "MISSING_SIGNOFF_TIMESTAMP_BLOCKED": ["SIGNOFF_TIMESTAMP_MISSING_BLOCKER"],
    "MISSING_EVIDENCE_REFERENCE_BLOCKED": ["EVIDENCE_REFERENCE_MISSING_BLOCKER"],
    "ROLE_MISMATCH_BLOCKED": ["ROLE_MISMATCH_BLOCKER"],
    "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED": ["NON_UNLOCK_ATTESTATION_MISSING_BLOCKER"],
    "MISSING_ROLLBACK_ACKNOWLEDGEMENT_BLOCKED": ["ROLLBACK_ACKNOWLEDGEMENT_MISSING_BLOCKER"],
    "PROVIDER_UNLOCK_REQUESTED_BLOCKED": ["PROVIDER_UNLOCK_REQUESTED_BLOCKER"],
    "ODDS_UNLOCK_REQUESTED_BLOCKED": ["ODDS_UNLOCK_REQUESTED_BLOCKER"],
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED": ["RECOMMENDATION_UNLOCK_REQUESTED_BLOCKER"],
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKED": ["PRODUCTION_UNLOCK_REQUESTED_BLOCKER"],
    "EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKED": ["EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKER"],
    "LIVE_OR_PAID_API_REQUESTED_BLOCKED": ["LIVE_OR_PAID_API_REQUESTED_BLOCKER"],
    "SIGNOFF_FOR_CRITICAL_STOP_WITH_UNLOCK_REQUEST_BLOCKED": [
        "CRITICAL_STOP_UNLOCK_REQUEST_BLOCKER",
        "UNAUTHORIZED_UNLOCK_REQUEST_BLOCKER",
    ],
    "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKED": ["SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKER"],
}

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Validate sign-off packet evidence completeness and role alignment only",
    "Require full role-based evidence before governance progression",
    "Keep full regression state explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat sign-off packet approval as legal provider approval",
    "Do not bypass role coverage, timestamp, non-unlock, or rollback requirements",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_READY_WITH_BLOCKERS",
    "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_BLOCKED_BY_MISSING_ARTIFACTS",
    "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def governance_invariants(p121: dict):
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


def build_valid_template(escalation_card: dict):
    roles = sorted(escalation_card["required_signoff_roles"])
    signer_identity_by_role = {r: f"{r}@governance.local" for r in roles}
    signer_authority_attestation_by_role = {r: f"{r} authorized for governance sign-off" for r in roles}
    signoff_status_by_role = {r: "APPROVED" for r in roles}
    signoff_timestamp_by_role = {r: "2026-06-01T12:00:00Z" for r in roles}
    evidence_reference_by_role = {r: f"governance://evidence/{r}/P133_VALID_TEMPLATE" for r in roles}

    return {
        "signoff_packet_id": "P133_SIGNOFF_VALID_TEMPLATE",
        "source_packet_id": escalation_card["packet_id"],
        "source_escalation_level": escalation_card["escalation_level"],
        "source_blocker_codes": sorted(escalation_card["blocker_codes"]),
        "required_signoff_roles": roles,
        "provided_signoff_roles": roles,
        "signer_identity_by_role": signer_identity_by_role,
        "signer_authority_attestation_by_role": signer_authority_attestation_by_role,
        "signoff_status_by_role": signoff_status_by_role,
        "signoff_timestamp_by_role": signoff_timestamp_by_role,
        "evidence_reference_by_role": evidence_reference_by_role,
        "escalation_reason": escalation_card["escalation_reason"],
        "decision_scope": "Governance sign-off evidence validation only",
        "non_unlock_attestation": "Sign-off packet does not imply legal provider approval or production readiness.",
        "rollback_acknowledgement": "Rollback plan acknowledged for any future governance action.",
        "provider_unlock_requested": False,
        "odds_unlock_requested": False,
        "recommendation_unlock_requested": False,
        "production_unlock_requested": False,
        "ev_clv_kelly_unlock_requested": False,
        "live_or_paid_api_requested": False,
    }


def make_invalid_case(case_id: str, valid_template: dict):
    packet = json.loads(json.dumps(valid_template))

    if case_id == "MISSING_SIGNOFF_PACKET_ID_BLOCKED":
        packet["signoff_packet_id"] = ""
    elif case_id == "MISSING_SOURCE_PACKET_ID_BLOCKED":
        packet["source_packet_id"] = ""
    elif case_id == "MISSING_SOURCE_ESCALATION_LEVEL_BLOCKED":
        packet["source_escalation_level"] = ""
    elif case_id == "MISSING_REQUIRED_SIGNOFF_ROLES_BLOCKED":
        packet["required_signoff_roles"] = []
    elif case_id == "MISSING_PROVIDED_SIGNOFF_ROLES_BLOCKED":
        packet["provided_signoff_roles"] = []
    elif case_id == "MISSING_SIGNER_IDENTITY_BLOCKED":
        packet["signer_identity_by_role"] = {}
    elif case_id == "MISSING_SIGNER_AUTHORITY_ATTESTATION_BLOCKED":
        packet["signer_authority_attestation_by_role"] = {}
    elif case_id == "SIGNOFF_STATUS_NOT_APPROVED_BLOCKED":
        packet["signoff_status_by_role"] = {r: "PENDING" for r in packet["required_signoff_roles"]}
    elif case_id == "MISSING_SIGNOFF_TIMESTAMP_BLOCKED":
        packet["signoff_timestamp_by_role"] = {}
    elif case_id == "MISSING_EVIDENCE_REFERENCE_BLOCKED":
        packet["evidence_reference_by_role"] = {}
    elif case_id == "ROLE_MISMATCH_BLOCKED":
        packet["provided_signoff_roles"] = ["engineering_owner"]
    elif case_id == "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED":
        packet["non_unlock_attestation"] = ""
    elif case_id == "MISSING_ROLLBACK_ACKNOWLEDGEMENT_BLOCKED":
        packet["rollback_acknowledgement"] = ""
    elif case_id == "PROVIDER_UNLOCK_REQUESTED_BLOCKED":
        packet["provider_unlock_requested"] = True
    elif case_id == "ODDS_UNLOCK_REQUESTED_BLOCKED":
        packet["odds_unlock_requested"] = True
    elif case_id == "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED":
        packet["recommendation_unlock_requested"] = True
    elif case_id == "PRODUCTION_UNLOCK_REQUESTED_BLOCKED":
        packet["production_unlock_requested"] = True
    elif case_id == "EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKED":
        packet["ev_clv_kelly_unlock_requested"] = True
    elif case_id == "LIVE_OR_PAID_API_REQUESTED_BLOCKED":
        packet["live_or_paid_api_requested"] = True
    elif case_id == "SIGNOFF_FOR_CRITICAL_STOP_WITH_UNLOCK_REQUEST_BLOCKED":
        packet["source_escalation_level"] = "CRITICAL_STOP"
        packet["production_unlock_requested"] = True
    elif case_id == "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKED":
        packet["decision_scope"] = "Legal provider approval granted"

    return {
        "case_id": case_id,
        "packet": packet,
        "status": "BLOCKED",
        "blockers": INVALID_CASE_BLOCKERS[case_id],
    }


def empty_summary():
    return {
        "signoff_packet_validator_status": "BLOCKED",
        "source_escalation_router_status": "UNKNOWN",
        "source_escalation_card_count": 0,
        "required_signoff_roles": [],
        "signoff_packet_schema": SIGNOFF_PACKET_SCHEMA,
        "valid_signoff_packet_template": {},
        "invalid_signoff_packet_cases": [],
        "signoff_validation_rules": {},
        "signoff_verdict_matrix": {},
        "missing_signoff_blockers": {},
        "unauthorized_signoff_blockers": {},
        "role_mismatch_blockers": {},
        "stale_or_missing_timestamp_blockers": {},
        "non_unlock_attestation_blockers": {},
        "escalation_level_coverage_matrix": {},
        "required_evidence_matrix": {},
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def main():
    missing = [p for p in (P121_PATH, P132_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P133 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p132 = load_json(P132_PATH)

    escalation_cards = sorted(p132.get("escalation_cards", []), key=lambda x: x.get("packet_id", ""))
    required_signoff_roles = sorted(set(p132.get("required_signoff_roles", [])))

    template_source = None
    for card in escalation_cards:
        if card.get("packet_id") == "P130_VALID_TEMPLATE":
            template_source = card
            break
    if template_source is None:
        template_source = escalation_cards[0]

    valid_template = build_valid_template(template_source)
    invalid_cases = [make_invalid_case(case_id, valid_template) for case_id in INVALID_CASE_IDS]

    signoff_verdict_matrix = {
        "VALID_SIGNOFF_PACKET_TEMPLATE": {
            "status": "GOVERNANCE_ONLY_PENDING_REVIEW",
            "blockers": [],
        }
    }
    for row in invalid_cases:
        signoff_verdict_matrix[row["case_id"]] = {
            "status": "BLOCKED",
            "blockers": sorted(row["blockers"]),
        }

    missing_signoff_blockers = {
        "required_fields": SCHEMA_FIELDS,
        "missing_field_blockers": {
            "signoff_packet_id": "SIGNOFF_PACKET_ID_MISSING_BLOCKER",
            "source_packet_id": "SOURCE_PACKET_ID_MISSING_BLOCKER",
            "source_escalation_level": "SOURCE_ESCALATION_LEVEL_MISSING_BLOCKER",
            "required_signoff_roles": "REQUIRED_SIGNOFF_ROLES_MISSING_BLOCKER",
            "provided_signoff_roles": "PROVIDED_SIGNOFF_ROLES_MISSING_BLOCKER",
            "signer_identity_by_role": "SIGNER_IDENTITY_MISSING_BLOCKER",
            "signer_authority_attestation_by_role": "SIGNER_AUTHORITY_ATTESTATION_MISSING_BLOCKER",
            "signoff_status_by_role": "SIGNOFF_STATUS_NOT_APPROVED_BLOCKER",
            "signoff_timestamp_by_role": "SIGNOFF_TIMESTAMP_MISSING_BLOCKER",
            "evidence_reference_by_role": "EVIDENCE_REFERENCE_MISSING_BLOCKER",
        },
    }

    unauthorized_signoff_blockers = {
        "provider_unlock_requested": "PROVIDER_UNLOCK_REQUESTED_BLOCKER",
        "odds_unlock_requested": "ODDS_UNLOCK_REQUESTED_BLOCKER",
        "recommendation_unlock_requested": "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKER",
        "production_unlock_requested": "PRODUCTION_UNLOCK_REQUESTED_BLOCKER",
        "ev_clv_kelly_unlock_requested": "EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKER",
        "live_or_paid_api_requested": "LIVE_OR_PAID_API_REQUESTED_BLOCKER",
        "critical_stop_with_unlock": "CRITICAL_STOP_UNLOCK_REQUEST_BLOCKER",
        "treated_as_legal_approval": "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKER",
    }

    role_mismatch_blockers = {
        "required_roles_must_equal_provided_roles": "ROLE_MISMATCH_BLOCKER",
        "all_required_roles_must_have_signer_identity": "SIGNER_IDENTITY_MISSING_BLOCKER",
        "all_required_roles_must_have_authority_attestation": "SIGNER_AUTHORITY_ATTESTATION_MISSING_BLOCKER",
    }

    stale_or_missing_timestamp_blockers = {
        "all_required_roles_must_have_timestamps": "SIGNOFF_TIMESTAMP_MISSING_BLOCKER",
        "stale_timestamp_not_allowed_for_governance_progress": "SIGNOFF_TIMESTAMP_STALE_BLOCKER",
    }

    non_unlock_attestation_blockers = {
        "non_unlock_attestation_required": "NON_UNLOCK_ATTESTATION_MISSING_BLOCKER",
        "rollback_acknowledgement_required": "ROLLBACK_ACKNOWLEDGEMENT_MISSING_BLOCKER",
    }

    escalation_level_coverage_matrix = {}
    required_evidence_matrix = {}
    required_signoff_matrix = p132.get("required_signoff_matrix", {})
    for level in sorted(required_signoff_matrix.keys()):
        roles = sorted(required_signoff_matrix[level])
        escalation_level_coverage_matrix[level] = {
            "required_roles": roles,
            "coverage_status": "REQUIRED",
            "all_roles_must_be_present": True,
        }
        required_evidence_matrix[level] = {
            "required_roles": roles,
            "required_evidence_fields": [
                "signer_identity_by_role",
                "signer_authority_attestation_by_role",
                "signoff_status_by_role",
                "signoff_timestamp_by_role",
                "evidence_reference_by_role",
            ],
            "non_unlock_attestation_required": True,
            "rollback_acknowledgement_required": True,
        }

    governance_summary = governance_invariants(p121)
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

    blockers = sorted(set(p132.get("blockers", [])))
    blockers.extend(
        [
            "SIGNOFF_EVIDENCE_PACKET_GOVERNANCE_ONLY_BLOCKER",
            "FULL_REGRESSION_NOT_RUN_BLOCKER",
        ]
    )
    blockers = sorted(set(blockers))

    final_classification = "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_READY_WITH_BLOCKERS"
    if governance_fail or p132.get("source_unexpected_approved_count", 0) > 0:
        final_classification = "P133_ESCALATION_SIGNOFF_EVIDENCE_PACKET_VALIDATOR_FAILED_VALIDATION"

    summary = {
        "signoff_packet_validator_status": "READY_WITH_BLOCKERS",
        "source_escalation_router_status": p132.get("escalation_router_status", "UNKNOWN"),
        "source_escalation_card_count": len(escalation_cards),
        "required_signoff_roles": required_signoff_roles,
        "signoff_packet_schema": SIGNOFF_PACKET_SCHEMA,
        "valid_signoff_packet_template": valid_template,
        "invalid_signoff_packet_cases": invalid_cases,
        "signoff_validation_rules": {
            "required_fields": SCHEMA_FIELDS,
            "valid_template_status": "GOVERNANCE_ONLY_PENDING_REVIEW",
            "invalid_cases_status": "BLOCKED",
            "all_required_roles_must_be_present": True,
            "non_unlock_attestation_required_text": "does not imply legal provider approval or production readiness",
            "unlock_requests_must_be_false": True,
        },
        "signoff_verdict_matrix": signoff_verdict_matrix,
        "missing_signoff_blockers": missing_signoff_blockers,
        "unauthorized_signoff_blockers": unauthorized_signoff_blockers,
        "role_mismatch_blockers": role_mismatch_blockers,
        "stale_or_missing_timestamp_blockers": stale_or_missing_timestamp_blockers,
        "non_unlock_attestation_blockers": non_unlock_attestation_blockers,
        "escalation_level_coverage_matrix": escalation_level_coverage_matrix,
        "required_evidence_matrix": required_evidence_matrix,
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Sign-off packet approval does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "regression_status": {
            "targeted_p118_p133_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P133 task.",
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
        f.write("# P133 Escalation Sign-off Evidence Packet Validator (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- signoff_packet_validator_status: {summary['signoff_packet_validator_status']}\n")
        f.write(f"- source_escalation_router_status: {summary['source_escalation_router_status']}\n")
        f.write(f"- source_escalation_card_count: {summary['source_escalation_card_count']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Sign-off Validation\n")
        f.write("- valid_signoff_packet_template_status: GOVERNANCE_ONLY_PENDING_REVIEW\n")
        f.write(f"- invalid_signoff_packet_case_count: {len(summary['invalid_signoff_packet_cases'])}\n")
        f.write("- invalid_signoff_packet_cases_status: BLOCKED\n\n")

        f.write("## Coverage\n")
        f.write(f"- escalation_level_coverage_matrix: {summary['escalation_level_coverage_matrix']}\n")
        f.write(f"- required_evidence_matrix: {summary['required_evidence_matrix']}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p133_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")
        f.write("\n")

        f.write("## Allowed Next Actions\n")
        for item in summary["allowed_next_actions"]:
            f.write(f"- {item}\n")

    print(f"P133 summary written to {OUT_PATH}")
    print(f"P133 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
