# P135 Sign-off Evidence Drift Alert Contract
# Paper-only drift alert contract for P134 replay consistency results.

import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P134_PATH = "data/mlb_2026/derived/p134_signoff_evidence_replay_consistency_gate_summary.json"
OUT_PATH = "data/mlb_2026/derived/p135_signoff_evidence_drift_alert_contract_summary.json"
REPORT_PATH = "report/p135_signoff_evidence_drift_alert_contract_20260601.md"

ALERT_LEVEL_DEFINITIONS = {
    "GREEN_NO_SIGNOFF_DRIFT": "No drift detected; consistency checks all pass.",
    "YELLOW_SIGNOFF_METADATA_ONLY_DRIFT": "Metadata-only replay deviations detected.",
    "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT": "Blocker/evidence matrix drift detected.",
    "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT": "Verdict matrix or escalation coverage drift detected.",
    "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT": "Unlock/provider/governance invariant drift detected.",
}

DRIFT_TYPE_DEFINITIONS = {
    "FINGERPRINT_DRIFT": "Deterministic replay fingerprint mismatch.",
    "SIGNOFF_VERDICT_MATRIX_DRIFT": "Sign-off verdict matrix differs across runs.",
    "BLOCKER_CLASSIFICATION_DRIFT": "Blocker classification set differs across runs.",
    "REQUIRED_EVIDENCE_MATRIX_DRIFT": "Required evidence matrix differs across runs.",
    "ESCALATION_LEVEL_COVERAGE_DRIFT": "Escalation coverage mapping differs across runs.",
    "GOVERNANCE_INVARIANT_DRIFT": "Governance invariant values changed.",
    "UNLOCK_PREVENTION_DRIFT": "Unlock prevention matrix changed.",
    "SIGNOFF_PACKET_COUNT_DRIFT": "Sign-off packet count changed unexpectedly.",
    "INVALID_PACKET_COUNT_DRIFT": "Invalid packet count changed unexpectedly.",
    "REPLAY_METADATA_DRIFT": "Replay metadata changed unexpectedly.",
}

ESCALATION_PATH_DEFINITIONS = {
    "record_only": "Record event in governance audit log only.",
    "engineering_review": "Route to engineering owner for review.",
    "cto_review": "Escalate to CTO governance owner.",
    "legal_review": "Escalate to legal owner.",
    "compliance_review": "Escalate to compliance owner.",
    "security_review": "Escalate to security owner.",
    "ceo_review": "Escalate to executive/CEO review.",
    "immediate_stop": "Immediate stop: no governance progression.",
}

SLA_CLASS_DEFINITIONS = {
    "SLA_NONE_RECORD_ONLY": "No response time requirement; archival record.",
    "SLA_STANDARD_ENGINEERING_REVIEW": "Standard engineering review window.",
    "SLA_CTO_REVIEW": "Expedited CTO review window.",
    "SLA_LEGAL_COMPLIANCE_REVIEW": "Legal/compliance review required.",
    "SLA_SECURITY_REVIEW": "Security review required.",
    "SLA_EXECUTIVE_REVIEW": "Executive review required.",
    "SLA_IMMEDIATE_STOP": "Immediate stop and incident-style escalation.",
}

REQUIRED_SIGNOFF_OWNER_MATRIX = {
    "GREEN_NO_SIGNOFF_DRIFT": ["engineering_owner"],
    "YELLOW_SIGNOFF_METADATA_ONLY_DRIFT": ["engineering_owner", "compliance_owner"],
    "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT": ["engineering_owner", "compliance_owner", "cto_owner"],
    "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT": [
        "engineering_owner",
        "cto_owner",
        "legal_owner",
        "compliance_owner",
    ],
    "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT": [
        "engineering_owner",
        "cto_owner",
        "legal_owner",
        "compliance_owner",
        "ceo_owner",
        "data_rights_owner",
        "security_owner",
    ],
}

DRIFT_DETAILS_REQUIRED_FIELDS = [
    "drift_event_id",
    "drift_type",
    "alert_level",
    "source_packet_id_or_matrix",
    "baseline_value",
    "observed_value",
    "affected_roles",
    "affected_blocker_codes",
    "affected_unlock_flags",
    "escalation_path",
    "sla_class",
    "required_signoff_owners",
    "reviewer_owner",
    "remediation_required",
    "rollback_required",
    "non_unlock_attestation_required",
    "created_at",
    "final_blocked_status",
]

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use drift alert contract for governance diagnostics only",
    "Require approved baseline review before accepting structural drift",
    "Keep full regression state explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat drift alert review as legal provider approval or production readiness",
    "Do not bypass blocker resolution and sign-off owner requirements",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_READY_WITH_BLOCKERS",
    "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
    "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_FAILED_VALIDATION",
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


def build_blocking_conditions(source: dict):
    return [
        {
            "condition_id": "C001",
            "condition": "any previously BLOCKED sign-off verdict becomes ALLOWED",
            "classification": "BLOCKED",
            "alert_level": "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
            "drift_type": "SIGNOFF_VERDICT_MATRIX_DRIFT",
            "escalation_path": "cto_review",
            "sla_class": "SLA_CTO_REVIEW",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT"],
        },
        {
            "condition_id": "C002",
            "condition": "valid_signoff_packet_template becomes production-ready",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C003",
            "condition": "source_signoff_packet_count changes without approved baseline update",
            "classification": "BLOCKED",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "drift_type": "SIGNOFF_PACKET_COUNT_DRIFT",
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT"],
        },
        {
            "condition_id": "C004",
            "condition": "source_invalid_packet_count changes without approved baseline update",
            "classification": "BLOCKED",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "drift_type": "INVALID_PACKET_COUNT_DRIFT",
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT"],
        },
        {
            "condition_id": "C005",
            "condition": "blocker classifications change without approved review",
            "classification": "BLOCKED",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "drift_type": "BLOCKER_CLASSIFICATION_DRIFT",
            "escalation_path": "compliance_review",
            "sla_class": "SLA_LEGAL_COMPLIANCE_REVIEW",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT"],
        },
        {
            "condition_id": "C006",
            "condition": "required evidence matrix changes without approved review",
            "classification": "BLOCKED",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "drift_type": "REQUIRED_EVIDENCE_MATRIX_DRIFT",
            "escalation_path": "legal_review",
            "sla_class": "SLA_LEGAL_COMPLIANCE_REVIEW",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT"],
        },
        {
            "condition_id": "C007",
            "condition": "escalation coverage changes without approved review",
            "classification": "BLOCKED",
            "alert_level": "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
            "drift_type": "ESCALATION_LEVEL_COVERAGE_DRIFT",
            "escalation_path": "cto_review",
            "sla_class": "SLA_CTO_REVIEW",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT"],
        },
        {
            "condition_id": "C008",
            "condition": "governance invariants become false",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "GOVERNANCE_INVARIANT_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C009",
            "condition": "provider_approved becomes true without verified legal evidence",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "GOVERNANCE_INVARIANT_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C010",
            "condition": "authorization_evidence_present becomes true without verified legal evidence",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "GOVERNANCE_INVARIANT_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C011",
            "condition": "recommendation_allowed becomes true",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C012",
            "condition": "production_ready becomes true",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C013",
            "condition": "EV/CLV/Kelly/stake/profit unlock becomes true",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C014",
            "condition": "real_legal_odds_ingested becomes true without explicit legal/provider approval",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C015",
            "condition": "live_api_calls or paid_api_called becomes non-zero",
            "classification": "BLOCKED",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT"],
        },
        {
            "condition_id": "C016",
            "condition": "drift_detected=true but drift_details is missing or incomplete",
            "classification": "BLOCKED",
            "alert_level": "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
            "drift_type": "REPLAY_METADATA_DRIFT",
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT"],
        },
        {
            "condition_id": "C017",
            "condition": "fingerprint consistency status changes from CONSISTENT",
            "classification": "BLOCKED",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "drift_type": "FINGERPRINT_DRIFT",
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "required_signoff_owners": REQUIRED_SIGNOFF_OWNER_MATRIX["ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT"],
        },
    ]


def empty_summary():
    return {
        "signoff_drift_alert_contract_status": "BLOCKED",
        "source_signoff_replay_gate_status": "UNKNOWN",
        "source_replay_run_count": 0,
        "source_signoff_packet_count": 0,
        "source_invalid_packet_count": 0,
        "source_baseline_fingerprint": "",
        "source_drift_detected": True,
        "alert_level_definitions": ALERT_LEVEL_DEFINITIONS,
        "drift_type_definitions": DRIFT_TYPE_DEFINITIONS,
        "escalation_path_definitions": ESCALATION_PATH_DEFINITIONS,
        "sla_class_definitions": SLA_CLASS_DEFINITIONS,
        "required_signoff_owner_matrix": REQUIRED_SIGNOFF_OWNER_MATRIX,
        "blocking_conditions": [],
        "verdict_matrix_drift_rules": {},
        "blocker_classification_drift_rules": {},
        "required_evidence_matrix_drift_rules": {},
        "escalation_level_coverage_drift_rules": {},
        "governance_invariant_drift_rules": {},
        "unlock_prevention_drift_rules": {},
        "fingerprint_drift_rules": {},
        "drift_details_required_fields": DRIFT_DETAILS_REQUIRED_FIELDS,
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def main():
    missing = [p for p in (P121_PATH, P134_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P135 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p134 = load_json(P134_PATH)

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

    blocking_conditions = build_blocking_conditions(p134)

    verdict_matrix_drift_rules = {
        "blocked_to_allowed_is_blocking": True,
        "valid_template_status_must_remain_governance_only_pending_review": True,
        "required_alert_level_for_verdict_drift": "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
        "required_escalation_path": "cto_review",
    }

    blocker_classification_drift_rules = {
        "blocker_set_change_without_review_is_blocking": True,
        "required_alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
        "required_escalation_path": "compliance_review",
    }

    required_evidence_matrix_drift_rules = {
        "evidence_matrix_change_without_review_is_blocking": True,
        "required_alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
        "required_escalation_path": "legal_review",
    }

    escalation_level_coverage_drift_rules = {
        "coverage_change_without_review_is_blocking": True,
        "required_alert_level": "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
        "required_escalation_path": "cto_review",
    }

    governance_invariant_drift_rules = {
        "any_false_invariant_is_critical_blocking": True,
        "required_alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
        "required_escalation_path": "immediate_stop",
    }

    unlock_prevention_drift_rules = {
        "any_unlock_flag_true_is_critical_blocking": True,
        "provider_or_authorization_true_without_legal_evidence_is_critical": True,
        "live_or_paid_api_nonzero_is_critical": True,
        "required_alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
        "required_escalation_path": "immediate_stop",
    }

    fingerprint_drift_rules = {
        "fingerprint_mismatch_is_blocking": True,
        "required_alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
        "required_escalation_path": "engineering_review",
        "hash_algorithm": "sha256",
    }

    blockers = sorted(set(p134.get("blockers", [])))
    blockers.extend(
        [
            "SIGNOFF_DRIFT_ALERT_CONTRACT_GOVERNANCE_ONLY_BLOCKER",
            "FULL_REGRESSION_NOT_RUN_BLOCKER",
        ]
    )
    blockers = sorted(set(blockers))

    final_classification = "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_READY_WITH_BLOCKERS"
    if governance_fail:
        final_classification = "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_FAILED_VALIDATION"

    summary = {
        "signoff_drift_alert_contract_status": "READY_WITH_BLOCKERS",
        "source_signoff_replay_gate_status": p134.get("signoff_replay_consistency_gate_status", "UNKNOWN"),
        "source_replay_run_count": p134.get("replay_run_count", 0),
        "source_signoff_packet_count": p134.get("source_signoff_packet_count", 0),
        "source_invalid_packet_count": p134.get("source_invalid_packet_count", 0),
        "source_baseline_fingerprint": p134.get("baseline_fingerprint", ""),
        "source_drift_detected": bool(p134.get("drift_detected", True)),
        "alert_level_definitions": ALERT_LEVEL_DEFINITIONS,
        "drift_type_definitions": DRIFT_TYPE_DEFINITIONS,
        "escalation_path_definitions": ESCALATION_PATH_DEFINITIONS,
        "sla_class_definitions": SLA_CLASS_DEFINITIONS,
        "required_signoff_owner_matrix": REQUIRED_SIGNOFF_OWNER_MATRIX,
        "blocking_conditions": blocking_conditions,
        "verdict_matrix_drift_rules": verdict_matrix_drift_rules,
        "blocker_classification_drift_rules": blocker_classification_drift_rules,
        "required_evidence_matrix_drift_rules": required_evidence_matrix_drift_rules,
        "escalation_level_coverage_drift_rules": escalation_level_coverage_drift_rules,
        "governance_invariant_drift_rules": governance_invariant_drift_rules,
        "unlock_prevention_drift_rules": unlock_prevention_drift_rules,
        "fingerprint_drift_rules": fingerprint_drift_rules,
        "drift_details_required_fields": DRIFT_DETAILS_REQUIRED_FIELDS,
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Sign-off drift alert review does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "regression_status": {
            "targeted_p118_p135_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P135 task.",
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
        f.write("# P135 Sign-off Evidence Drift Alert Contract (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- signoff_drift_alert_contract_status: {summary['signoff_drift_alert_contract_status']}\n")
        f.write(f"- source_signoff_replay_gate_status: {summary['source_signoff_replay_gate_status']}\n")
        f.write(f"- source_replay_run_count: {summary['source_replay_run_count']}\n")
        f.write(f"- source_signoff_packet_count: {summary['source_signoff_packet_count']}\n")
        f.write(f"- source_invalid_packet_count: {summary['source_invalid_packet_count']}\n")
        f.write(f"- source_drift_detected: {summary['source_drift_detected']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Alert Contract\n")
        f.write(f"- alert_level_definitions: {summary['alert_level_definitions']}\n")
        f.write(f"- drift_type_definitions: {summary['drift_type_definitions']}\n")
        f.write(f"- escalation_path_definitions: {summary['escalation_path_definitions']}\n")
        f.write(f"- sla_class_definitions: {summary['sla_class_definitions']}\n")
        f.write(f"- required_signoff_owner_matrix: {summary['required_signoff_owner_matrix']}\n\n")

        f.write("## Blocking Conditions\n")
        for row in summary["blocking_conditions"]:
            f.write(f"- {row['condition_id']}: {row['condition']} ({row['alert_level']}/{row['drift_type']})\n")
        f.write("\n")

        f.write("## Drift Rule Sets\n")
        f.write(f"- verdict_matrix_drift_rules: {summary['verdict_matrix_drift_rules']}\n")
        f.write(f"- blocker_classification_drift_rules: {summary['blocker_classification_drift_rules']}\n")
        f.write(f"- required_evidence_matrix_drift_rules: {summary['required_evidence_matrix_drift_rules']}\n")
        f.write(f"- escalation_level_coverage_drift_rules: {summary['escalation_level_coverage_drift_rules']}\n")
        f.write(f"- governance_invariant_drift_rules: {summary['governance_invariant_drift_rules']}\n")
        f.write(f"- unlock_prevention_drift_rules: {summary['unlock_prevention_drift_rules']}\n")
        f.write(f"- fingerprint_drift_rules: {summary['fingerprint_drift_rules']}\n")
        f.write(f"- drift_details_required_fields: {summary['drift_details_required_fields']}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p135_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")
        f.write("\n")

        f.write("## Allowed Next Actions\n")
        for item in summary["allowed_next_actions"]:
            f.write(f"- {item}\n")

    print(f"P135 summary written to {OUT_PATH}")
    print(f"P135 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
