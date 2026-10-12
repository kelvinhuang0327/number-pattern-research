# P139 Drift Alert Replay Drift Execution Gate
# Deterministic paper-only execution gate based on P138 drift contract.

import json
from collections import Counter
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P138_PATH = "data/mlb_2026/derived/p138_drift_alert_replay_drift_contract_summary.json"
OUT_PATH = "data/mlb_2026/derived/p139_drift_alert_replay_drift_execution_gate_summary.json"
REPORT_PATH = "report/p139_drift_alert_replay_drift_execution_gate_20260601.md"

FINAL_CLASSIFICATION_OPTIONS = [
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_READY_WITH_BLOCKERS",
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_FAILED_VALIDATION",
]

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Execute drift diagnostics and blocker enforcement only",
    "Require baseline change review packet before accepting any drift deltas",
    "Keep targeted/full regression status explicit and truthful",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat execution gate output as legal provider approval",
    "Do not treat execution gate output as real odds approval or recommendation readiness",
    "Do not treat execution gate output as production readiness",
]

REQUIRED_EXECUTION_CASES = [
    "NO_REPLAY_DRIFT_RECORD_ONLY",
    "FINGERPRINT_DRIFT_BASELINE_REVIEW_REQUIRED",
    "ALERT_VERDICT_DRIFT_BLOCKED",
    "ESCALATION_DECISION_PACKET_DRIFT_BLOCKED",
    "ALERT_LEVEL_MATRIX_DRIFT_BLOCKED",
    "DRIFT_TYPE_MATRIX_DRIFT_BLOCKED",
    "ESCALATION_PATH_MATRIX_DRIFT_BLOCKED",
    "SLA_MATRIX_DRIFT_BLOCKED",
    "REQUIRED_OWNER_MATRIX_DRIFT_BLOCKED",
    "BLOCKED_ACTION_MATRIX_DRIFT_BLOCKED",
    "UNLOCK_PREVENTION_MATRIX_DRIFT_CRITICAL_STOP",
    "FINAL_CLASSIFICATION_DRIFT_BLOCKED",
    "REPLAY_RUN_COUNT_DRIFT_BLOCKED",
    "SOURCE_EVENT_COUNT_DRIFT_BLOCKED",
    "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
    "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
    "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
    "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
    "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
    "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
    "DRIFT_DETAILS_MISSING_BLOCKED",
    "BASELINE_CHANGE_REQUEST_MISSING_BLOCKED",
    "BASELINE_CHANGE_REVIEWER_NOT_APPROVED_BLOCKED",
    "BASELINE_CHANGE_NON_UNLOCK_ATTESTATION_MISSING_BLOCKED",
    "BASELINE_CHANGE_ROLLBACK_PLAN_MISSING_BLOCKED",
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


def empty_summary() -> dict:
    return {
        "drift_alert_replay_drift_execution_gate_status": "BLOCKED",
        "source_drift_alert_replay_drift_contract_status": "UNKNOWN",
        "source_replay_run_count": 0,
        "source_evaluated_drift_event_count": 0,
        "source_baseline_fingerprint": "",
        "evaluated_execution_case_count": 0,
        "execution_cases": [],
        "execution_verdict_matrix": {},
        "blocking_condition_enforcement_matrix": {},
        "baseline_change_review_enforcement_matrix": {},
        "drift_detail_validation_matrix": {},
        "escalation_path_execution_matrix": {},
        "sla_execution_matrix": {},
        "required_owner_execution_matrix": {},
        "unlock_prevention_matrix": {},
        "no_unlock_governance_matrix": {},
        "invalid_drift_detail_cases": [],
        "invalid_baseline_change_cases": [],
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def make_case(
    case_id: str,
    drift_type: str,
    alert_level: str,
    source_matrix_or_packet: str,
    verdict: str,
    blocked: bool,
    critical_stop: bool,
    baseline_change_required: bool,
    drift_details_required: bool,
    drift_details_complete: bool,
    baseline_change_review_complete: bool,
    escalation_path: str,
    sla_class: str,
    required_owners: list[str],
    blocked_actions: list[str],
    next_required_action: str,
) -> dict:
    return {
        "execution_case_id": case_id,
        "drift_type": drift_type,
        "alert_level": alert_level,
        "source_matrix_or_packet": source_matrix_or_packet,
        "verdict": verdict,
        "blocked": blocked,
        "critical_stop": critical_stop,
        "baseline_change_required": baseline_change_required,
        "drift_details_required": drift_details_required,
        "drift_details_complete": drift_details_complete,
        "baseline_change_review_required": baseline_change_required,
        "baseline_change_review_complete": baseline_change_review_complete,
        "escalation_path": escalation_path,
        "sla_class": sla_class,
        "required_owners": required_owners,
        "blocked_actions": blocked_actions,
        "next_required_action": next_required_action,
        "provider_unlock_allowed": False,
        "odds_unlock_allowed": False,
        "recommendation_unlock_allowed": False,
        "production_unlock_allowed": False,
        "ev_clv_kelly_unlock_allowed": False,
    }


def main():
    missing = [p for p in (P121_PATH, P138_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P139 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p138 = load_json(P138_PATH)

    blocked_actions_default = [
        "provider_unlock",
        "odds_unlock",
        "recommendation_unlock",
        "production_unlock",
        "ev_clv_kelly_unlock",
    ]

    execution_cases = [
        make_case(
            "NO_REPLAY_DRIFT_RECORD_ONLY",
            "NO_DRIFT",
            "GREEN_NO_REPLAY_DRIFT",
            "no_drift_record_packet",
            "ALLOW_RECORD_ONLY",
            False,
            False,
            False,
            False,
            True,
            True,
            "record_only",
            "SLA_NONE_RECORD_ONLY",
            ["engineering_owner"],
            blocked_actions_default,
            "Record-only trace; keep governance locks.",
        ),
        make_case(
            "FINGERPRINT_DRIFT_BASELINE_REVIEW_REQUIRED",
            "FINGERPRINT_DRIFT",
            "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
            "source_baseline_fingerprint",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            True,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "data_rights_owner"],
            blocked_actions_default,
            "Submit approved baseline change request.",
        ),
        make_case(
            "ALERT_VERDICT_DRIFT_BLOCKED",
            "ALERT_VERDICT_DRIFT",
            "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
            "alert_verdict_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            True,
            "legal_review",
            "SLA_LEGAL_COMPLIANCE_REVIEW",
            ["engineering_owner", "cto_owner", "legal_owner", "compliance_owner"],
            blocked_actions_default,
            "Legal/compliance review and approved baseline change.",
        ),
        make_case(
            "ESCALATION_DECISION_PACKET_DRIFT_BLOCKED",
            "ESCALATION_DECISION_PACKET_DRIFT",
            "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
            "escalation_decision_packet_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            True,
            "cto_review",
            "SLA_CTO_REVIEW",
            ["engineering_owner", "cto_owner"],
            blocked_actions_default,
            "CTO review and approved baseline change.",
        ),
        make_case("ALERT_LEVEL_MATRIX_DRIFT_BLOCKED", "ALERT_LEVEL_MATRIX_DRIFT", "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT", "alert_level_matrix", "BLOCKED", True, False, True, True, True, True, "cto_review", "SLA_CTO_REVIEW", ["engineering_owner", "cto_owner"], blocked_actions_default, "CTO review and approved baseline change."),
        make_case("DRIFT_TYPE_MATRIX_DRIFT_BLOCKED", "DRIFT_TYPE_MATRIX_DRIFT", "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT", "drift_type_matrix", "BLOCKED", True, False, True, True, True, True, "cto_review", "SLA_CTO_REVIEW", ["engineering_owner", "cto_owner"], blocked_actions_default, "CTO review and approved baseline change."),
        make_case("ESCALATION_PATH_MATRIX_DRIFT_BLOCKED", "ESCALATION_PATH_MATRIX_DRIFT", "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT", "escalation_path_matrix", "BLOCKED", True, False, True, True, True, True, "cto_review", "SLA_CTO_REVIEW", ["engineering_owner", "cto_owner"], blocked_actions_default, "CTO review and approved baseline change."),
        make_case("SLA_MATRIX_DRIFT_BLOCKED", "SLA_MATRIX_DRIFT", "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT", "sla_matrix", "BLOCKED", True, False, True, True, True, True, "cto_review", "SLA_CTO_REVIEW", ["engineering_owner", "cto_owner"], blocked_actions_default, "CTO review and approved baseline change."),
        make_case("REQUIRED_OWNER_MATRIX_DRIFT_BLOCKED", "REQUIRED_OWNER_MATRIX_DRIFT", "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT", "required_owner_matrix", "BLOCKED", True, False, True, True, True, True, "compliance_review", "SLA_LEGAL_COMPLIANCE_REVIEW", ["engineering_owner", "cto_owner", "compliance_owner"], blocked_actions_default, "Compliance review and approved baseline change."),
        make_case("BLOCKED_ACTION_MATRIX_DRIFT_BLOCKED", "BLOCKED_ACTION_MATRIX_DRIFT", "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT", "blocked_action_matrix", "BLOCKED", True, False, True, True, True, True, "legal_review", "SLA_LEGAL_COMPLIANCE_REVIEW", ["engineering_owner", "legal_owner", "compliance_owner"], blocked_actions_default, "Legal/compliance review and approved baseline change."),
        make_case("UNLOCK_PREVENTION_MATRIX_DRIFT_CRITICAL_STOP", "UNLOCK_PREVENTION_MATRIX_DRIFT", "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT", "unlock_prevention_matrix", "CRITICAL_STOP", True, True, True, True, True, True, "immediate_stop", "SLA_IMMEDIATE_STOP", ["engineering_owner", "security_owner", "legal_owner", "compliance_owner", "ceo_owner"], blocked_actions_default, "Immediate stop, rollback, and executive approval required."),
        make_case("FINAL_CLASSIFICATION_DRIFT_BLOCKED", "FINAL_CLASSIFICATION_DRIFT", "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT", "final_classification", "BLOCKED", True, False, True, True, True, True, "cto_review", "SLA_EXECUTIVE_REVIEW", ["engineering_owner", "cto_owner", "ceo_owner"], blocked_actions_default, "Executive review and approved baseline change."),
        make_case("REPLAY_RUN_COUNT_DRIFT_BLOCKED", "REPLAY_RUN_COUNT_DRIFT", "YELLOW_REPLAY_METADATA_ONLY_DRIFT", "replay_run_count", "BLOCKED", True, False, True, True, True, True, "engineering_review", "SLA_STANDARD_ENGINEERING_REVIEW", ["engineering_owner", "data_rights_owner"], blocked_actions_default, "Baseline review for replay run count change."),
        make_case("SOURCE_EVENT_COUNT_DRIFT_BLOCKED", "SOURCE_EVENT_COUNT_DRIFT", "YELLOW_REPLAY_METADATA_ONLY_DRIFT", "source_evaluated_drift_event_count", "BLOCKED", True, False, True, True, True, True, "engineering_review", "SLA_STANDARD_ENGINEERING_REVIEW", ["engineering_owner", "data_rights_owner"], blocked_actions_default, "Baseline review for source event count change."),
        make_case("PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP", "PROVIDER_UNLOCK_DRIFT", "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT", "provider_approved", "CRITICAL_STOP", True, True, False, True, True, True, "immediate_stop", "SLA_IMMEDIATE_STOP", ["legal_owner", "compliance_owner", "ceo_owner", "security_owner"], blocked_actions_default, "Immediate stop: provider unlock drift forbidden."),
        make_case("AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP", "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT", "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT", "authorization_evidence_present", "CRITICAL_STOP", True, True, False, True, True, True, "immediate_stop", "SLA_IMMEDIATE_STOP", ["legal_owner", "compliance_owner", "ceo_owner", "security_owner"], blocked_actions_default, "Immediate stop: authorization evidence unlock drift forbidden."),
        make_case("RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP", "RECOMMENDATION_UNLOCK_DRIFT", "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT", "recommendation_allowed", "CRITICAL_STOP", True, True, False, True, True, True, "immediate_stop", "SLA_IMMEDIATE_STOP", ["cto_owner", "compliance_owner", "ceo_owner", "security_owner"], blocked_actions_default, "Immediate stop: recommendation unlock drift forbidden."),
        make_case("PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP", "PRODUCTION_UNLOCK_DRIFT", "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT", "production_ready", "CRITICAL_STOP", True, True, False, True, True, True, "immediate_stop", "SLA_IMMEDIATE_STOP", ["cto_owner", "compliance_owner", "ceo_owner", "security_owner"], blocked_actions_default, "Immediate stop: production unlock drift forbidden."),
        make_case("REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP", "REAL_ODDS_INGESTION_DRIFT", "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT", "real_legal_odds_ingested", "CRITICAL_STOP", True, True, False, True, True, True, "immediate_stop", "SLA_IMMEDIATE_STOP", ["legal_owner", "data_rights_owner", "compliance_owner", "security_owner", "ceo_owner"], blocked_actions_default, "Immediate stop: real odds ingestion forbidden."),
        make_case("LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP", "LIVE_OR_PAID_API_DRIFT", "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT", "live_api_calls_or_paid_api_called", "CRITICAL_STOP", True, True, False, True, True, True, "immediate_stop", "SLA_IMMEDIATE_STOP", ["security_owner", "compliance_owner", "ceo_owner"], blocked_actions_default, "Immediate stop: live/paid API drift forbidden."),
        make_case("DRIFT_DETAILS_MISSING_BLOCKED", "REPLAY_METADATA_DRIFT", "YELLOW_REPLAY_METADATA_ONLY_DRIFT", "drift_details", "BLOCKED", True, False, False, True, False, True, "engineering_review", "SLA_STANDARD_ENGINEERING_REVIEW", ["engineering_owner", "compliance_owner"], blocked_actions_default, "Provide complete drift details schema."),
        make_case("BASELINE_CHANGE_REQUEST_MISSING_BLOCKED", "BASELINE_CHANGE_PROCESS_DRIFT", "YELLOW_REPLAY_METADATA_ONLY_DRIFT", "baseline_change_request", "BLOCKED", True, False, True, True, True, False, "engineering_review", "SLA_STANDARD_ENGINEERING_REVIEW", ["engineering_owner", "compliance_owner"], blocked_actions_default, "Provide baseline_change_request_id and required fields."),
        make_case("BASELINE_CHANGE_REVIEWER_NOT_APPROVED_BLOCKED", "BASELINE_CHANGE_PROCESS_DRIFT", "YELLOW_REPLAY_METADATA_ONLY_DRIFT", "baseline_change_reviewer_approval", "BLOCKED", True, False, True, True, True, False, "compliance_review", "SLA_LEGAL_COMPLIANCE_REVIEW", ["engineering_owner", "compliance_owner", "legal_owner"], blocked_actions_default, "Reviewer approval must be APPROVED."),
        make_case("BASELINE_CHANGE_NON_UNLOCK_ATTESTATION_MISSING_BLOCKED", "BASELINE_CHANGE_PROCESS_DRIFT", "YELLOW_REPLAY_METADATA_ONLY_DRIFT", "baseline_change_non_unlock_attestation", "BLOCKED", True, False, True, True, True, False, "compliance_review", "SLA_LEGAL_COMPLIANCE_REVIEW", ["engineering_owner", "compliance_owner", "legal_owner"], blocked_actions_default, "Provide non-unlock attestation."),
        make_case("BASELINE_CHANGE_ROLLBACK_PLAN_MISSING_BLOCKED", "BASELINE_CHANGE_PROCESS_DRIFT", "YELLOW_REPLAY_METADATA_ONLY_DRIFT", "baseline_change_rollback_plan", "BLOCKED", True, False, True, True, True, False, "engineering_review", "SLA_STANDARD_ENGINEERING_REVIEW", ["engineering_owner", "cto_owner", "compliance_owner"], blocked_actions_default, "Provide rollback plan."),
    ]

    case_ids = {c["execution_case_id"] for c in execution_cases}
    missing_cases = [c for c in REQUIRED_EXECUTION_CASES if c not in case_ids]

    execution_verdict_matrix = {c["execution_case_id"]: c["verdict"] for c in execution_cases}

    blocking_condition_enforcement_matrix = {
        "BLOCKED_OR_CRITICAL_STOP_ENFORCED": [
            c["execution_case_id"] for c in execution_cases if c["execution_case_id"] != "NO_REPLAY_DRIFT_RECORD_ONLY" and c["blocked"]
        ],
        "NO_DRIFT_RECORD_ONLY_ENFORCED": [
            c["execution_case_id"] for c in execution_cases if c["execution_case_id"] == "NO_REPLAY_DRIFT_RECORD_ONLY" and c["blocked"] is False
        ],
        "CRITICAL_STOP_ENFORCED": [
            c["execution_case_id"] for c in execution_cases if c["critical_stop"]
        ],
    }

    baseline_change_review_enforcement_matrix = {
        c["execution_case_id"]: {
            "baseline_change_review_required": c["baseline_change_review_required"],
            "baseline_change_review_complete": c["baseline_change_review_complete"],
            "enforcement_status": "ENFORCED" if (not c["baseline_change_review_required"] or c["baseline_change_review_complete"]) else "BLOCKED",
        }
        for c in execution_cases
    }

    drift_detail_validation_matrix = {
        c["execution_case_id"]: {
            "drift_details_required": c["drift_details_required"],
            "drift_details_complete": c["drift_details_complete"],
            "validation_status": "VALID" if (not c["drift_details_required"] or c["drift_details_complete"]) else "INVALID",
        }
        for c in execution_cases
    }

    escalation_counts = Counter(c["escalation_path"] for c in execution_cases)
    sla_counts = Counter(c["sla_class"] for c in execution_cases)
    owner_counts = Counter(owner for c in execution_cases for owner in c["required_owners"])
    verdict_counts = Counter(c["verdict"] for c in execution_cases)

    escalation_path_execution_matrix = {
        "case_to_escalation_path": {c["execution_case_id"]: c["escalation_path"] for c in execution_cases},
        "escalation_path_counts": dict(escalation_counts),
    }
    sla_execution_matrix = {
        "case_to_sla_class": {c["execution_case_id"]: c["sla_class"] for c in execution_cases},
        "sla_class_counts": dict(sla_counts),
    }
    required_owner_execution_matrix = {
        "case_to_required_owners": {c["execution_case_id"]: c["required_owners"] for c in execution_cases},
        "required_owner_counts": dict(owner_counts),
    }

    unlock_prevention_matrix = {
        c["execution_case_id"]: {
            "provider_unlock_allowed": c["provider_unlock_allowed"],
            "odds_unlock_allowed": c["odds_unlock_allowed"],
            "recommendation_unlock_allowed": c["recommendation_unlock_allowed"],
            "production_unlock_allowed": c["production_unlock_allowed"],
            "ev_clv_kelly_unlock_allowed": c["ev_clv_kelly_unlock_allowed"],
        }
        for c in execution_cases
    }

    governance_summary = governance_invariants(p121)
    no_unlock_governance_matrix = {
        "paper_only": governance_summary["paper_only"],
        "diagnostic_only": governance_summary["diagnostic_only"],
        "provider_approved": governance_summary["provider_approved"],
        "authorization_evidence_present": governance_summary["authorization_evidence_present"],
        "recommendation_allowed": governance_summary["recommendation_allowed"],
        "production_ready": governance_summary["production_ready"],
        "real_legal_odds_ingested": governance_summary["real_legal_odds_ingested"],
        "live_api_calls": governance_summary["live_api_calls"],
        "paid_api_called": governance_summary["paid_api_called"],
        "any_unlock_allowed": any(
            c["provider_unlock_allowed"]
            or c["odds_unlock_allowed"]
            or c["recommendation_unlock_allowed"]
            or c["production_unlock_allowed"]
            or c["ev_clv_kelly_unlock_allowed"]
            for c in execution_cases
        ),
    }

    invalid_drift_detail_cases = [
        c["execution_case_id"]
        for c in execution_cases
        if c["drift_details_required"] and not c["drift_details_complete"]
    ]

    invalid_baseline_change_cases = [
        c["execution_case_id"]
        for c in execution_cases
        if c["baseline_change_review_required"] and not c["baseline_change_review_complete"]
    ]

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
        or no_unlock_governance_matrix["any_unlock_allowed"] is True
        or bool(missing_cases)
    )

    blockers = sorted(
        set(
            p138.get("blockers", [])
            + [
                "DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GOVERNANCE_ONLY_BLOCKER",
                "FULL_REGRESSION_NOT_RUN_BLOCKER",
                "LEGAL_PROVIDER_EVIDENCE_NOT_APPROVED_BLOCKER",
            ]
        )
    )

    final_classification = "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_READY_WITH_BLOCKERS"
    if governance_fail:
        final_classification = "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_FAILED_VALIDATION"

    summary = {
        "drift_alert_replay_drift_execution_gate_status": "READY_WITH_BLOCKERS",
        "source_drift_alert_replay_drift_contract_status": p138.get("drift_alert_replay_drift_contract_status", "UNKNOWN"),
        "source_replay_run_count": int(p138.get("source_replay_run_count", 0)),
        "source_evaluated_drift_event_count": int(p138.get("source_evaluated_drift_event_count", 0)),
        "source_baseline_fingerprint": p138.get("source_baseline_fingerprint", ""),
        "evaluated_execution_case_count": len(execution_cases),
        "execution_cases": execution_cases,
        "execution_verdict_matrix": execution_verdict_matrix,
        "blocking_condition_enforcement_matrix": blocking_condition_enforcement_matrix,
        "baseline_change_review_enforcement_matrix": baseline_change_review_enforcement_matrix,
        "drift_detail_validation_matrix": drift_detail_validation_matrix,
        "escalation_path_execution_matrix": escalation_path_execution_matrix,
        "sla_execution_matrix": sla_execution_matrix,
        "required_owner_execution_matrix": required_owner_execution_matrix,
        "unlock_prevention_matrix": unlock_prevention_matrix,
        "no_unlock_governance_matrix": no_unlock_governance_matrix,
        "invalid_drift_detail_cases": invalid_drift_detail_cases,
        "invalid_baseline_change_cases": invalid_baseline_change_cases,
        "enforcement_counts": {
            "verdict_counts": dict(verdict_counts),
            "blocked_case_count": sum(1 for c in execution_cases if c["blocked"]),
            "critical_stop_case_count": sum(1 for c in execution_cases if c["critical_stop"]),
            "baseline_change_required_case_count": sum(1 for c in execution_cases if c["baseline_change_required"]),
            "drift_details_required_case_count": sum(1 for c in execution_cases if c["drift_details_required"]),
            "blocking_condition_enforced_count": len(blocking_condition_enforcement_matrix["BLOCKED_OR_CRITICAL_STOP_ENFORCED"]),
            "escalation_path_counts": dict(escalation_counts),
            "sla_class_counts": dict(sla_counts),
            "required_owner_counts": dict(owner_counts),
        },
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Drift execution gate does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "regression_status": {
            "targeted_p118_p139_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P139 task.",
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
        f.write("# P139 Drift Alert Replay Drift Execution Gate (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- drift_alert_replay_drift_execution_gate_status: {summary['drift_alert_replay_drift_execution_gate_status']}\n")
        f.write(f"- source_drift_alert_replay_drift_contract_status: {summary['source_drift_alert_replay_drift_contract_status']}\n")
        f.write(f"- source_replay_run_count: {summary['source_replay_run_count']}\n")
        f.write(f"- source_evaluated_drift_event_count: {summary['source_evaluated_drift_event_count']}\n")
        f.write(f"- evaluated_execution_case_count: {summary['evaluated_execution_case_count']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Enforcement Counts\n")
        f.write(f"- verdict_counts: {summary['enforcement_counts']['verdict_counts']}\n")
        f.write(f"- blocked_case_count: {summary['enforcement_counts']['blocked_case_count']}\n")
        f.write(f"- critical_stop_case_count: {summary['enforcement_counts']['critical_stop_case_count']}\n")
        f.write(f"- baseline_change_required_case_count: {summary['enforcement_counts']['baseline_change_required_case_count']}\n")
        f.write(f"- drift_details_required_case_count: {summary['enforcement_counts']['drift_details_required_case_count']}\n")
        f.write(f"- escalation_path_counts: {summary['enforcement_counts']['escalation_path_counts']}\n")
        f.write(f"- sla_class_counts: {summary['enforcement_counts']['sla_class_counts']}\n")
        f.write(f"- required_owner_counts: {summary['enforcement_counts']['required_owner_counts']}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p139_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")

    print(f"P139 summary written to {OUT_PATH}")
    print(f"P139 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
# P139 Drift Alert Replay Drift Execution Gate
# Deterministic paper-only execution gate derived from P138 drift contract.

import json
from collections import Counter
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P138_PATH = "data/mlb_2026/derived/p138_drift_alert_replay_drift_contract_summary.json"
OUT_PATH = "data/mlb_2026/derived/p139_drift_alert_replay_drift_execution_gate_summary.json"
REPORT_PATH = "report/p139_drift_alert_replay_drift_execution_gate_20260601.md"

FINAL_CLASSIFICATION_OPTIONS = [
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_READY_WITH_BLOCKERS",
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_FAILED_VALIDATION",
]

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use execution verdicts for governance diagnostics and blocker enforcement only",
    "Require approved baseline change review for contract drift acceptance",
    "Keep full regression status explicit as PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat execution gate approval as legal provider approval",
    "Do not treat execution gate approval as real odds approval, recommendation readiness, or production readiness",
]

EXECUTION_CASE_IDS = [
    "NO_REPLAY_DRIFT_RECORD_ONLY",
    "FINGERPRINT_DRIFT_BASELINE_REVIEW_REQUIRED",
    "ALERT_VERDICT_DRIFT_BLOCKED",
    "ESCALATION_DECISION_PACKET_DRIFT_BLOCKED",
    "ALERT_LEVEL_MATRIX_DRIFT_BLOCKED",
    "DRIFT_TYPE_MATRIX_DRIFT_BLOCKED",
    "ESCALATION_PATH_MATRIX_DRIFT_BLOCKED",
    "SLA_MATRIX_DRIFT_BLOCKED",
    "REQUIRED_OWNER_MATRIX_DRIFT_BLOCKED",
    "BLOCKED_ACTION_MATRIX_DRIFT_BLOCKED",
    "UNLOCK_PREVENTION_MATRIX_DRIFT_CRITICAL_STOP",
    "FINAL_CLASSIFICATION_DRIFT_BLOCKED",
    "REPLAY_RUN_COUNT_DRIFT_BLOCKED",
    "SOURCE_EVENT_COUNT_DRIFT_BLOCKED",
    "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
    "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
    "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
    "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
    "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
    "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
    "DRIFT_DETAILS_MISSING_BLOCKED",
    "BASELINE_CHANGE_REQUEST_MISSING_BLOCKED",
    "BASELINE_CHANGE_REVIEWER_NOT_APPROVED_BLOCKED",
    "BASELINE_CHANGE_NON_UNLOCK_ATTESTATION_MISSING_BLOCKED",
    "BASELINE_CHANGE_ROLLBACK_PLAN_MISSING_BLOCKED",
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


def empty_summary() -> dict:
    return {
        "drift_alert_replay_drift_execution_gate_status": "BLOCKED",
        "source_drift_alert_replay_drift_contract_status": "UNKNOWN",
        "source_replay_run_count": 0,
        "source_evaluated_drift_event_count": 0,
        "source_baseline_fingerprint": "",
        "evaluated_execution_case_count": 0,
        "execution_cases": [],
        "execution_verdict_matrix": {},
        "blocking_condition_enforcement_matrix": {},
        "baseline_change_review_enforcement_matrix": {},
        "drift_detail_validation_matrix": {},
        "escalation_path_execution_matrix": {},
        "sla_execution_matrix": {},
        "required_owner_execution_matrix": {},
        "unlock_prevention_matrix": {},
        "no_unlock_governance_matrix": {},
        "invalid_drift_detail_cases": [],
        "invalid_baseline_change_cases": [],
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def case_template(
    execution_case_id: str,
    drift_type: str,
    alert_level: str,
    source_matrix_or_packet: str,
    verdict: str,
    blocked: bool,
    critical_stop: bool,
    baseline_change_required: bool,
    drift_details_required: bool,
    drift_details_complete: bool,
    baseline_change_review_complete: bool,
    escalation_path: str,
    sla_class: str,
    required_owners: list,
    blocked_actions: list,
    next_required_action: str,
):
    return {
        "execution_case_id": execution_case_id,
        "drift_type": drift_type,
        "alert_level": alert_level,
        "source_matrix_or_packet": source_matrix_or_packet,
        "verdict": verdict,
        "blocked": blocked,
        "critical_stop": critical_stop,
        "baseline_change_required": baseline_change_required,
        "drift_details_required": drift_details_required,
        "drift_details_complete": drift_details_complete,
        "baseline_change_review_required": baseline_change_required,
        "baseline_change_review_complete": baseline_change_review_complete,
        "escalation_path": escalation_path,
        "sla_class": sla_class,
        "required_owners": required_owners,
        "blocked_actions": blocked_actions,
        "next_required_action": next_required_action,
        "provider_unlock_allowed": False,
        "odds_unlock_allowed": False,
        "recommendation_unlock_allowed": False,
        "production_unlock_allowed": False,
        "ev_clv_kelly_unlock_allowed": False,
    }


def build_execution_cases() -> list:
    cases = [
        case_template(
            "NO_REPLAY_DRIFT_RECORD_ONLY",
            "REPLAY_METADATA_DRIFT",
            "GREEN_NO_REPLAY_DRIFT",
            "no_drift_record_packet",
            "RECORD_ONLY",
            False,
            False,
            False,
            False,
            True,
            True,
            "record_only",
            "SLA_NONE_RECORD_ONLY",
            ["engineering_owner"],
            [],
            "record_only_log_and_monitor",
        ),
        case_template(
            "FINGERPRINT_DRIFT_BASELINE_REVIEW_REQUIRED",
            "FINGERPRINT_DRIFT",
            "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
            "baseline_fingerprint",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "data_rights_owner"],
            ["baseline_fingerprint_override"],
            "submit_baseline_change_request",
        ),
        case_template(
            "ALERT_VERDICT_DRIFT_BLOCKED",
            "ALERT_VERDICT_DRIFT",
            "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
            "execution_verdict_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "legal_review",
            "SLA_LEGAL_COMPLIANCE_REVIEW",
            ["engineering_owner", "legal_owner", "compliance_owner"],
            ["verdict_matrix_change_apply"],
            "legal_compliance_review_required",
        ),
        case_template(
            "ESCALATION_DECISION_PACKET_DRIFT_BLOCKED",
            "ESCALATION_DECISION_PACKET_DRIFT",
            "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
            "execution_cases",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "cto_review",
            "SLA_CTO_REVIEW",
            ["engineering_owner", "cto_owner"],
            ["packet_change_apply"],
            "cto_baseline_review_required",
        ),
        case_template(
            "ALERT_LEVEL_MATRIX_DRIFT_BLOCKED",
            "ALERT_LEVEL_MATRIX_DRIFT",
            "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
            "escalation_path_execution_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "cto_review",
            "SLA_CTO_REVIEW",
            ["engineering_owner", "cto_owner"],
            ["alert_level_matrix_change_apply"],
            "cto_baseline_review_required",
        ),
        case_template(
            "DRIFT_TYPE_MATRIX_DRIFT_BLOCKED",
            "DRIFT_TYPE_MATRIX_DRIFT",
            "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
            "execution_verdict_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "cto_review",
            "SLA_CTO_REVIEW",
            ["engineering_owner", "cto_owner"],
            ["drift_type_matrix_change_apply"],
            "cto_baseline_review_required",
        ),
        case_template(
            "ESCALATION_PATH_MATRIX_DRIFT_BLOCKED",
            "ESCALATION_PATH_MATRIX_DRIFT",
            "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
            "escalation_path_execution_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "cto_review",
            "SLA_CTO_REVIEW",
            ["engineering_owner", "cto_owner"],
            ["escalation_path_matrix_change_apply"],
            "cto_baseline_review_required",
        ),
        case_template(
            "SLA_MATRIX_DRIFT_BLOCKED",
            "SLA_MATRIX_DRIFT",
            "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
            "sla_execution_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "cto_review",
            "SLA_CTO_REVIEW",
            ["engineering_owner", "cto_owner"],
            ["sla_matrix_change_apply"],
            "cto_baseline_review_required",
        ),
        case_template(
            "REQUIRED_OWNER_MATRIX_DRIFT_BLOCKED",
            "REQUIRED_OWNER_MATRIX_DRIFT",
            "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
            "required_owner_execution_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "compliance_review",
            "SLA_LEGAL_COMPLIANCE_REVIEW",
            ["engineering_owner", "compliance_owner", "legal_owner"],
            ["owner_matrix_change_apply"],
            "compliance_review_required",
        ),
        case_template(
            "BLOCKED_ACTION_MATRIX_DRIFT_BLOCKED",
            "BLOCKED_ACTION_MATRIX_DRIFT",
            "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
            "unlock_prevention_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "legal_review",
            "SLA_LEGAL_COMPLIANCE_REVIEW",
            ["engineering_owner", "legal_owner", "compliance_owner"],
            ["blocked_action_matrix_change_apply"],
            "legal_compliance_review_required",
        ),
        case_template(
            "UNLOCK_PREVENTION_MATRIX_DRIFT_CRITICAL_STOP",
            "UNLOCK_PREVENTION_MATRIX_DRIFT",
            "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
            "unlock_prevention_matrix",
            "CRITICAL_STOP",
            True,
            True,
            True,
            True,
            True,
            False,
            "immediate_stop",
            "SLA_IMMEDIATE_STOP",
            ["engineering_owner", "security_owner", "cto_owner", "ceo_owner"],
            ["unlock_prevention_matrix_change_apply", "recommendation_unlock"],
            "immediate_stop_and_rollback",
        ),
        case_template(
            "FINAL_CLASSIFICATION_DRIFT_BLOCKED",
            "FINAL_CLASSIFICATION_DRIFT",
            "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
            "execution_verdict_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "cto_review",
            "SLA_EXECUTIVE_REVIEW",
            ["engineering_owner", "cto_owner", "ceo_owner"],
            ["final_classification_change_apply"],
            "executive_review_required",
        ),
        case_template(
            "REPLAY_RUN_COUNT_DRIFT_BLOCKED",
            "REPLAY_RUN_COUNT_DRIFT",
            "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
            "source_replay_run_count",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "data_rights_owner"],
            ["replay_run_count_change_apply"],
            "baseline_change_request_required",
        ),
        case_template(
            "SOURCE_EVENT_COUNT_DRIFT_BLOCKED",
            "SOURCE_EVENT_COUNT_DRIFT",
            "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
            "source_evaluated_drift_event_count",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "data_rights_owner"],
            ["source_event_count_change_apply"],
            "baseline_change_request_required",
        ),
        case_template(
            "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
            "REPLAY_METADATA_DRIFT",
            "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
            "no_unlock_governance_matrix",
            "CRITICAL_STOP",
            True,
            True,
            False,
            True,
            True,
            True,
            "immediate_stop",
            "SLA_IMMEDIATE_STOP",
            ["legal_owner", "compliance_owner", "security_owner", "ceo_owner"],
            ["provider_unlock"],
            "immediate_stop_and_security_legal_review",
        ),
        case_template(
            "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
            "REPLAY_METADATA_DRIFT",
            "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
            "no_unlock_governance_matrix",
            "CRITICAL_STOP",
            True,
            True,
            False,
            True,
            True,
            True,
            "immediate_stop",
            "SLA_IMMEDIATE_STOP",
            ["legal_owner", "compliance_owner", "security_owner", "ceo_owner"],
            ["authorization_evidence_unlock"],
            "immediate_stop_and_security_legal_review",
        ),
        case_template(
            "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
            "REPLAY_METADATA_DRIFT",
            "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
            "no_unlock_governance_matrix",
            "CRITICAL_STOP",
            True,
            True,
            False,
            True,
            True,
            True,
            "immediate_stop",
            "SLA_IMMEDIATE_STOP",
            ["security_owner", "cto_owner", "ceo_owner"],
            ["recommendation_unlock"],
            "immediate_stop_and_security_review",
        ),
        case_template(
            "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
            "REPLAY_METADATA_DRIFT",
            "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
            "no_unlock_governance_matrix",
            "CRITICAL_STOP",
            True,
            True,
            False,
            True,
            True,
            True,
            "immediate_stop",
            "SLA_IMMEDIATE_STOP",
            ["security_owner", "cto_owner", "ceo_owner"],
            ["production_unlock"],
            "immediate_stop_and_security_review",
        ),
        case_template(
            "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
            "REPLAY_METADATA_DRIFT",
            "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
            "no_unlock_governance_matrix",
            "CRITICAL_STOP",
            True,
            True,
            False,
            True,
            True,
            True,
            "immediate_stop",
            "SLA_IMMEDIATE_STOP",
            ["legal_owner", "compliance_owner", "security_owner"],
            ["real_odds_ingestion"],
            "immediate_stop_and_legal_compliance_review",
        ),
        case_template(
            "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
            "REPLAY_METADATA_DRIFT",
            "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
            "no_unlock_governance_matrix",
            "CRITICAL_STOP",
            True,
            True,
            False,
            True,
            True,
            True,
            "immediate_stop",
            "SLA_IMMEDIATE_STOP",
            ["security_owner", "compliance_owner", "cto_owner"],
            ["live_or_paid_api_call"],
            "immediate_stop_and_security_review",
        ),
        case_template(
            "DRIFT_DETAILS_MISSING_BLOCKED",
            "REPLAY_METADATA_DRIFT",
            "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
            "drift_detail_validation_matrix",
            "BLOCKED",
            True,
            False,
            False,
            True,
            False,
            True,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "compliance_owner"],
            ["drift_without_detail_accept"],
            "complete_drift_details_first",
        ),
        case_template(
            "BASELINE_CHANGE_REQUEST_MISSING_BLOCKED",
            "FINGERPRINT_DRIFT",
            "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
            "baseline_change_review_enforcement_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "data_rights_owner"],
            ["baseline_change_without_request_id"],
            "provide_baseline_change_request",
        ),
        case_template(
            "BASELINE_CHANGE_REVIEWER_NOT_APPROVED_BLOCKED",
            "FINGERPRINT_DRIFT",
            "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
            "baseline_change_review_enforcement_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "reviewer_identity"],
            ["baseline_change_without_reviewer_approval"],
            "obtain_reviewer_approval",
        ),
        case_template(
            "BASELINE_CHANGE_NON_UNLOCK_ATTESTATION_MISSING_BLOCKED",
            "FINGERPRINT_DRIFT",
            "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
            "baseline_change_review_enforcement_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "compliance_owner"],
            ["baseline_change_without_non_unlock_attestation"],
            "attach_non_unlock_attestation",
        ),
        case_template(
            "BASELINE_CHANGE_ROLLBACK_PLAN_MISSING_BLOCKED",
            "FINGERPRINT_DRIFT",
            "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
            "baseline_change_review_enforcement_matrix",
            "BLOCKED",
            True,
            False,
            True,
            True,
            True,
            False,
            "engineering_review",
            "SLA_STANDARD_ENGINEERING_REVIEW",
            ["engineering_owner", "cto_owner"],
            ["baseline_change_without_rollback_plan"],
            "attach_rollback_plan",
        ),
    ]
    return cases


def main():
    missing = [p for p in (P121_PATH, P138_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P139 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p138 = load_json(P138_PATH)

    execution_cases = build_execution_cases()

    # Deterministic execution mapping for contract enforcement and reporting.
    execution_verdict_matrix = {c["execution_case_id"]: c["verdict"] for c in execution_cases}

    blocking_condition_enforcement_matrix = {}
    for item in p138.get("blocking_conditions", []):
        cid = item.get("condition_id", "UNKNOWN")
        rule = item.get("rule", "")
        related = [c["execution_case_id"] for c in execution_cases if "BLOCKED" in c["execution_case_id"] or "CRITICAL_STOP" in c["execution_case_id"]]
        blocking_condition_enforcement_matrix[cid] = {
            "rule": rule,
            "enforced": True,
            "covered_case_count": len(related),
            "covered_case_ids": related,
        }

    baseline_related = {
        c["execution_case_id"]: {
            "baseline_change_review_required": c["baseline_change_review_required"],
            "baseline_change_review_complete": c["baseline_change_review_complete"],
            "enforced": (not c["baseline_change_review_required"]) or c["baseline_change_review_complete"],
        }
        for c in execution_cases
    }

    drift_detail_validation_matrix = {
        c["execution_case_id"]: {
            "drift_details_required": c["drift_details_required"],
            "drift_details_complete": c["drift_details_complete"],
            "enforced": (not c["drift_details_required"]) or c["drift_details_complete"],
        }
        for c in execution_cases
    }

    escalation_path_execution_matrix = {c["execution_case_id"]: c["escalation_path"] for c in execution_cases}
    sla_execution_matrix = {c["execution_case_id"]: c["sla_class"] for c in execution_cases}
    required_owner_execution_matrix = {c["execution_case_id"]: c["required_owners"] for c in execution_cases}

    unlock_prevention_matrix = {
        c["execution_case_id"]: {
            "provider_unlock_allowed": c["provider_unlock_allowed"],
            "odds_unlock_allowed": c["odds_unlock_allowed"],
            "recommendation_unlock_allowed": c["recommendation_unlock_allowed"],
            "production_unlock_allowed": c["production_unlock_allowed"],
            "ev_clv_kelly_unlock_allowed": c["ev_clv_kelly_unlock_allowed"],
            "unlock_prevented": not any(
                [
                    c["provider_unlock_allowed"],
                    c["odds_unlock_allowed"],
                    c["recommendation_unlock_allowed"],
                    c["production_unlock_allowed"],
                    c["ev_clv_kelly_unlock_allowed"],
                ]
            ),
        }
        for c in execution_cases
    }

    governance_summary = governance_invariants(p121)
    no_unlock_governance_matrix = {
        "paper_only": governance_summary["paper_only"],
        "diagnostic_only": governance_summary["diagnostic_only"],
        "production_ready": governance_summary["production_ready"],
        "real_bet_allowed": governance_summary["real_bet_allowed"],
        "recommendation_allowed": governance_summary["recommendation_allowed"],
        "provider_approved": governance_summary["provider_approved"],
        "authorization_evidence_present": governance_summary["authorization_evidence_present"],
        "placeholder_allowed_as_authorization": governance_summary["placeholder_allowed_as_authorization"],
        "real_legal_odds_ingested": governance_summary["real_legal_odds_ingested"],
        "live_api_calls": governance_summary["live_api_calls"],
        "paid_api_called": governance_summary["paid_api_called"],
        "ev_computed": governance_summary["ev_computed"],
        "clv_computed": governance_summary["clv_computed"],
        "kelly_computed": governance_summary["kelly_computed"],
        "stake_sizing": governance_summary["stake_sizing"],
        "profit_computed": governance_summary["profit_computed"],
        "recommendation_generated": governance_summary["recommendation_generated"],
    }

    invalid_drift_detail_cases = [
        c["execution_case_id"] for c in execution_cases if c["drift_details_required"] and not c["drift_details_complete"]
    ]
    invalid_baseline_change_cases = [
        c["execution_case_id"]
        for c in execution_cases
        if c["baseline_change_review_required"] and not c["baseline_change_review_complete"]
    ]

    verdict_counts = Counter(c["verdict"] for c in execution_cases)
    blocked_counts = Counter("BLOCKED_OR_STOP" if c["blocked"] else "NOT_BLOCKED" for c in execution_cases)
    escalation_counts = Counter(c["escalation_path"] for c in execution_cases)
    sla_counts = Counter(c["sla_class"] for c in execution_cases)
    owner_counts = Counter(owner for c in execution_cases for owner in c["required_owners"])

    execution_enforcement_summary = {
        "verdict_counts": dict(verdict_counts),
        "blocking_counts": dict(blocked_counts),
        "escalation_path_counts": dict(escalation_counts),
        "sla_class_counts": dict(sla_counts),
        "required_owner_counts": dict(owner_counts),
    }

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

    dangerous_cases_valid = all(
        c["blocked"] is True
        for c in execution_cases
        if c["execution_case_id"] != "NO_REPLAY_DRIFT_RECORD_ONLY"
    )
    no_drift_record_only_valid = (
        execution_verdict_matrix.get("NO_REPLAY_DRIFT_RECORD_ONLY") == "RECORD_ONLY"
        and escalation_path_execution_matrix.get("NO_REPLAY_DRIFT_RECORD_ONLY") == "record_only"
        and unlock_prevention_matrix["NO_REPLAY_DRIFT_RECORD_ONLY"]["unlock_prevented"] is True
    )

    blockers = sorted(
        set(
            p138.get("blockers", [])
            + [
                "DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GOVERNANCE_ONLY_BLOCKER",
                "FULL_REGRESSION_NOT_RUN_BLOCKER",
                "LEGAL_PROVIDER_EVIDENCE_NOT_APPROVED_BLOCKER",
            ]
        )
    )

    final_classification = "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_READY_WITH_BLOCKERS"
    if governance_fail or not dangerous_cases_valid or not no_drift_record_only_valid:
        final_classification = "P139_DRIFT_ALERT_REPLAY_DRIFT_EXECUTION_GATE_FAILED_VALIDATION"

    summary = {
        "drift_alert_replay_drift_execution_gate_status": "READY_WITH_BLOCKERS",
        "source_drift_alert_replay_drift_contract_status": p138.get("drift_alert_replay_drift_contract_status", "UNKNOWN"),
        "source_replay_run_count": int(p138.get("source_replay_run_count", 0)),
        "source_evaluated_drift_event_count": int(p138.get("source_evaluated_drift_event_count", 0)),
        "source_baseline_fingerprint": p138.get("source_baseline_fingerprint", ""),
        "evaluated_execution_case_count": len(execution_cases),
        "execution_cases": execution_cases,
        "execution_verdict_matrix": execution_verdict_matrix,
        "blocking_condition_enforcement_matrix": blocking_condition_enforcement_matrix,
        "baseline_change_review_enforcement_matrix": baseline_related,
        "drift_detail_validation_matrix": drift_detail_validation_matrix,
        "escalation_path_execution_matrix": escalation_path_execution_matrix,
        "sla_execution_matrix": sla_execution_matrix,
        "required_owner_execution_matrix": required_owner_execution_matrix,
        "unlock_prevention_matrix": unlock_prevention_matrix,
        "no_unlock_governance_matrix": no_unlock_governance_matrix,
        "invalid_drift_detail_cases": invalid_drift_detail_cases,
        "invalid_baseline_change_cases": invalid_baseline_change_cases,
        "execution_enforcement_summary": execution_enforcement_summary,
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Drift execution gate does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "regression_status": {
            "targeted_p118_p139_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P139 task.",
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
        f.write("# P139 Drift Alert Replay Drift Execution Gate (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- drift_alert_replay_drift_execution_gate_status: {summary['drift_alert_replay_drift_execution_gate_status']}\n")
        f.write(f"- source_drift_alert_replay_drift_contract_status: {summary['source_drift_alert_replay_drift_contract_status']}\n")
        f.write(f"- source_replay_run_count: {summary['source_replay_run_count']}\n")
        f.write(f"- source_evaluated_drift_event_count: {summary['source_evaluated_drift_event_count']}\n")
        f.write(f"- evaluated_execution_case_count: {summary['evaluated_execution_case_count']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Enforcement Summary\n")
        for key, value in summary["execution_enforcement_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Invalid Case Buckets\n")
        f.write(f"- invalid_drift_detail_cases: {summary['invalid_drift_detail_cases']}\n")
        f.write(f"- invalid_baseline_change_cases: {summary['invalid_baseline_change_cases']}\n\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p139_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")

    print(f"P139 summary written to {OUT_PATH}")
    print(f"P139 report written to {REPORT_PATH}")


