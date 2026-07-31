# P138 Drift Alert Replay Drift Contract
# Paper-only governance contract derived from P137 replay consistency gate output.

import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P137_PATH = "data/mlb_2026/derived/p137_drift_alert_replay_consistency_gate_summary.json"
OUT_PATH = "data/mlb_2026/derived/p138_drift_alert_replay_drift_contract_summary.json"
REPORT_PATH = "report/p138_drift_alert_replay_drift_contract_20260601.md"

FINAL_CLASSIFICATION_OPTIONS = [
    "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_READY_WITH_BLOCKERS",
    "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
    "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_FAILED_VALIDATION",
]

REQUIRED_ALERT_LEVELS = [
    "GREEN_NO_REPLAY_DRIFT",
    "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
    "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
    "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
    "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
]

REQUIRED_DRIFT_TYPES = [
    "FINGERPRINT_DRIFT",
    "ALERT_VERDICT_DRIFT",
    "ESCALATION_DECISION_PACKET_DRIFT",
    "ALERT_LEVEL_MATRIX_DRIFT",
    "DRIFT_TYPE_MATRIX_DRIFT",
    "ESCALATION_PATH_MATRIX_DRIFT",
    "SLA_MATRIX_DRIFT",
    "REQUIRED_OWNER_MATRIX_DRIFT",
    "BLOCKED_ACTION_MATRIX_DRIFT",
    "UNLOCK_PREVENTION_MATRIX_DRIFT",
    "NO_DRIFT_RECORD_PACKET_DRIFT",
    "SIMULATED_BLOCKING_DRIFT_CASE_DRIFT",
    "FINAL_CLASSIFICATION_DRIFT",
    "REPLAY_RUN_COUNT_DRIFT",
    "SOURCE_EVENT_COUNT_DRIFT",
    "REPLAY_METADATA_DRIFT",
]

REQUIRED_ESCALATION_PATHS = [
    "record_only",
    "engineering_review",
    "cto_review",
    "legal_review",
    "compliance_review",
    "security_review",
    "ceo_review",
    "immediate_stop",
]

REQUIRED_SLA_CLASSES = [
    "SLA_NONE_RECORD_ONLY",
    "SLA_STANDARD_ENGINEERING_REVIEW",
    "SLA_CTO_REVIEW",
    "SLA_LEGAL_COMPLIANCE_REVIEW",
    "SLA_SECURITY_REVIEW",
    "SLA_EXECUTIVE_REVIEW",
    "SLA_IMMEDIATE_STOP",
]

REQUIRED_OWNERS = [
    "engineering_owner",
    "cto_owner",
    "legal_owner",
    "compliance_owner",
    "ceo_owner",
    "data_rights_owner",
    "security_owner",
]

DRIFT_DETAILS_REQUIRED_FIELDS = [
    "drift_event_id",
    "drift_type",
    "alert_level",
    "affected_matrix_or_packet",
    "baseline_value",
    "observed_value",
    "affected_drift_case_ids",
    "affected_alert_levels",
    "affected_escalation_paths",
    "affected_sla_classes",
    "affected_required_owners",
    "affected_blocked_actions",
    "affected_unlock_flags",
    "escalation_path",
    "sla_class",
    "required_owners",
    "remediation_required",
    "rollback_required",
    "non_unlock_attestation_required",
    "baseline_change_required",
    "final_blocked_status",
    "created_at",
]

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Run replay drift diagnostics and governance review only",
    "Submit baseline change request for any approved contract drift",
    "Keep targeted/full regression status explicit and truthful",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat replay drift contract as legal provider approval",
    "Do not treat replay drift contract as real odds approval or recommendation readiness",
    "Do not treat replay drift contract as production readiness",
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
        "drift_alert_replay_drift_contract_status": "BLOCKED",
        "source_drift_alert_replay_consistency_gate_status": "UNKNOWN",
        "source_replay_run_count": 0,
        "source_evaluated_drift_event_count": 0,
        "source_baseline_fingerprint": "",
        "source_drift_detected": True,
        "alert_level_definitions": {},
        "drift_type_definitions": {},
        "escalation_path_definitions": {},
        "sla_class_definitions": {},
        "required_owner_matrix": {},
        "blocking_conditions": [],
        "baseline_change_review_rules": {},
        "alert_verdict_drift_rules": {},
        "escalation_decision_packet_drift_rules": {},
        "alert_level_matrix_drift_rules": {},
        "drift_type_matrix_drift_rules": {},
        "escalation_path_matrix_drift_rules": {},
        "sla_matrix_drift_rules": {},
        "required_owner_matrix_drift_rules": {},
        "blocked_action_matrix_drift_rules": {},
        "unlock_prevention_matrix_drift_rules": {},
        "no_drift_record_packet_drift_rules": {},
        "simulated_blocking_drift_case_drift_rules": {},
        "final_classification_drift_rules": {},
        "fingerprint_drift_rules": {},
        "drift_details_required_fields": DRIFT_DETAILS_REQUIRED_FIELDS,
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def main():
    missing = [p for p in (P121_PATH, P137_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P138 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p137 = load_json(P137_PATH)

    alert_level_definitions = {
        "GREEN_NO_REPLAY_DRIFT": {
            "description": "No replay drift observed; keep record_only routing.",
            "default_escalation_path": "record_only",
            "default_sla_class": "SLA_NONE_RECORD_ONLY",
        },
        "YELLOW_REPLAY_METADATA_ONLY_DRIFT": {
            "description": "Replay metadata drift without matrix/verdict changes.",
            "default_escalation_path": "engineering_review",
            "default_sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
        },
        "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT": {
            "description": "Matrix or packet drift detected; requires owner review.",
            "default_escalation_path": "cto_review",
            "default_sla_class": "SLA_CTO_REVIEW",
        },
        "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT": {
            "description": "Verdict or blocked action drift detected; legal/compliance review required.",
            "default_escalation_path": "legal_review",
            "default_sla_class": "SLA_LEGAL_COMPLIANCE_REVIEW",
        },
        "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT": {
            "description": "Unlock/provider/governance drift detected; immediate stop.",
            "default_escalation_path": "immediate_stop",
            "default_sla_class": "SLA_IMMEDIATE_STOP",
        },
    }

    drift_type_definitions = {
        "FINGERPRINT_DRIFT": "Replay fingerprint differs from baseline fingerprint.",
        "ALERT_VERDICT_DRIFT": "Alert verdict matrix or verdict outcomes drifted.",
        "ESCALATION_DECISION_PACKET_DRIFT": "Escalation decision packets drifted.",
        "ALERT_LEVEL_MATRIX_DRIFT": "Alert level matrix drifted.",
        "DRIFT_TYPE_MATRIX_DRIFT": "Drift type matrix drifted.",
        "ESCALATION_PATH_MATRIX_DRIFT": "Escalation path matrix drifted.",
        "SLA_MATRIX_DRIFT": "SLA matrix drifted.",
        "REQUIRED_OWNER_MATRIX_DRIFT": "Required owner matrix drifted.",
        "BLOCKED_ACTION_MATRIX_DRIFT": "Blocked action matrix drifted.",
        "UNLOCK_PREVENTION_MATRIX_DRIFT": "Unlock prevention matrix drifted.",
        "NO_DRIFT_RECORD_PACKET_DRIFT": "No-drift record-only packet drifted.",
        "SIMULATED_BLOCKING_DRIFT_CASE_DRIFT": "Simulated blocking drift case behavior drifted.",
        "FINAL_CLASSIFICATION_DRIFT": "Final classification drifted.",
        "REPLAY_RUN_COUNT_DRIFT": "Replay run count drifted from approved baseline.",
        "SOURCE_EVENT_COUNT_DRIFT": "Evaluated drift event count drifted from approved baseline.",
        "REPLAY_METADATA_DRIFT": "Replay metadata changed and requires review.",
    }

    escalation_path_definitions = {
        "record_only": "Record-only path for no-drift stable outcomes.",
        "engineering_review": "Engineering triage and remediation path.",
        "cto_review": "CTO-level architecture and policy review path.",
        "legal_review": "Legal review path for compliance-impacting drift.",
        "compliance_review": "Compliance policy review path.",
        "security_review": "Security review path for governance/safety drift.",
        "ceo_review": "Executive escalation path.",
        "immediate_stop": "Immediate stop path for critical unlock/provider drift.",
    }

    sla_class_definitions = {
        "SLA_NONE_RECORD_ONLY": "No remediation SLA; record-only trace.",
        "SLA_STANDARD_ENGINEERING_REVIEW": "Standard engineering review SLA.",
        "SLA_CTO_REVIEW": "CTO review SLA.",
        "SLA_LEGAL_COMPLIANCE_REVIEW": "Joint legal and compliance SLA.",
        "SLA_SECURITY_REVIEW": "Security review SLA.",
        "SLA_EXECUTIVE_REVIEW": "Executive review SLA.",
        "SLA_IMMEDIATE_STOP": "Immediate stop and rollback SLA.",
    }

    required_owner_matrix = {
        "GREEN_NO_REPLAY_DRIFT": ["engineering_owner"],
        "YELLOW_REPLAY_METADATA_ONLY_DRIFT": ["engineering_owner", "data_rights_owner"],
        "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT": ["engineering_owner", "cto_owner"],
        "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT": [
            "engineering_owner",
            "cto_owner",
            "legal_owner",
            "compliance_owner",
        ],
        "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT": [
            "engineering_owner",
            "cto_owner",
            "legal_owner",
            "compliance_owner",
            "security_owner",
            "ceo_owner",
            "data_rights_owner",
        ],
    }

    blocking_conditions = [
        {
            "condition_id": "BC01_PREVIOUSLY_BLOCKED_CASE_BECOMES_ALLOWED",
            "rule": "any previously BLOCKED drift case becomes ALLOWED",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC02_CRITICAL_STOP_DOWNGRADE_WITHOUT_APPROVED_BASELINE_CHANGE",
            "rule": "any CRITICAL_STOP case downgrades without approved baseline change",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC03_NO_DRIFT_RECORD_ONLY_VERDICT_CHANGE",
            "rule": "no-drift record-only case changes verdict without approved baseline change",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC04_SOURCE_EVENT_COUNT_DRIFT",
            "rule": "evaluated_drift_event_count changes without approved baseline update",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC05_REPLAY_RUN_COUNT_DRIFT",
            "rule": "replay_run_count changes without approved baseline update",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC06_ALERT_VERDICT_MATRIX_CHANGE",
            "rule": "alert verdict matrix changes without approved review",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC07_ESCALATION_PACKET_CHANGE",
            "rule": "escalation decision packets change without approved review",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC08_BLOCKED_ACTION_MATRIX_CHANGE",
            "rule": "blocked action matrix changes without approved review",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC09_UNLOCK_PREVENTION_MATRIX_CHANGE",
            "rule": "unlock prevention matrix changes without approved review",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC10_FINAL_CLASSIFICATION_CHANGE",
            "rule": "final classification changes without approved review",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC11_BASELINE_FINGERPRINT_CHANGE",
            "rule": "baseline fingerprint changes without approved baseline change request",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC12_PROVIDER_APPROVED_UNLOCK",
            "rule": "provider_approved becomes true without verified legal evidence",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC13_AUTH_EVIDENCE_UNLOCK",
            "rule": "authorization_evidence_present becomes true without verified legal evidence",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC14_RECOMMENDATION_UNLOCK",
            "rule": "recommendation_allowed becomes true",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC15_PRODUCTION_UNLOCK",
            "rule": "production_ready becomes true",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC16_EV_CLV_KELLY_STAKE_PROFIT_UNLOCK",
            "rule": "EV/CLV/Kelly/stake/profit unlock becomes true",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC17_REAL_ODDS_INGESTION_UNLOCK",
            "rule": "real_legal_odds_ingested becomes true without explicit legal/provider approval",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC18_LIVE_OR_PAID_API_CALLS",
            "rule": "live_api_calls or paid_api_called becomes non-zero",
            "blocked_status": "BLOCKED",
        },
        {
            "condition_id": "BC19_DRIFT_DETAILS_INCOMPLETE",
            "rule": "drift_detected=true but drift_details is missing or incomplete",
            "blocked_status": "BLOCKED",
        },
    ]

    baseline_change_review_rules = {
        "required_fields": [
            "baseline_change_request_id",
            "baseline_change_owner",
            "baseline_change_reason",
            "source_baseline_fingerprint",
            "proposed_baseline_fingerprint",
            "old_replay_run_count",
            "new_replay_run_count",
            "old_evaluated_drift_event_count",
            "new_evaluated_drift_event_count",
            "changed_matrix_names",
            "changed_packet_names",
            "expected_verdict_delta",
            "expected_unlock_delta",
            "reviewer_approval_status",
            "reviewer_identity",
            "approval_timestamp",
            "rollback_plan",
            "non_unlock_attestation",
            "non_unlock_governance_statement",
        ],
        "non_unlock_governance_statement": "baseline change does not imply provider approval, odds approval, recommendation readiness, or production readiness",
    }

    def drift_rule(drift_type: str, alert_level: str, escalation_path: str, sla_class: str, requires_baseline_change: bool):
        return {
            "drift_type": drift_type,
            "alert_level": alert_level,
            "escalation_path": escalation_path,
            "sla_class": sla_class,
            "requires_baseline_change_review": requires_baseline_change,
            "non_unlock_attestation_required": True,
            "blocked_if_unapproved": True,
        }

    alert_verdict_drift_rules = drift_rule(
        "ALERT_VERDICT_DRIFT",
        "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
        "legal_review",
        "SLA_LEGAL_COMPLIANCE_REVIEW",
        True,
    )
    escalation_decision_packet_drift_rules = drift_rule(
        "ESCALATION_DECISION_PACKET_DRIFT",
        "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
        "cto_review",
        "SLA_CTO_REVIEW",
        True,
    )
    alert_level_matrix_drift_rules = drift_rule(
        "ALERT_LEVEL_MATRIX_DRIFT",
        "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
        "cto_review",
        "SLA_CTO_REVIEW",
        True,
    )
    drift_type_matrix_drift_rules = drift_rule(
        "DRIFT_TYPE_MATRIX_DRIFT",
        "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
        "cto_review",
        "SLA_CTO_REVIEW",
        True,
    )
    escalation_path_matrix_drift_rules = drift_rule(
        "ESCALATION_PATH_MATRIX_DRIFT",
        "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
        "cto_review",
        "SLA_CTO_REVIEW",
        True,
    )
    sla_matrix_drift_rules = drift_rule(
        "SLA_MATRIX_DRIFT",
        "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
        "cto_review",
        "SLA_CTO_REVIEW",
        True,
    )
    required_owner_matrix_drift_rules = drift_rule(
        "REQUIRED_OWNER_MATRIX_DRIFT",
        "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
        "compliance_review",
        "SLA_LEGAL_COMPLIANCE_REVIEW",
        True,
    )
    blocked_action_matrix_drift_rules = drift_rule(
        "BLOCKED_ACTION_MATRIX_DRIFT",
        "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
        "legal_review",
        "SLA_LEGAL_COMPLIANCE_REVIEW",
        True,
    )
    unlock_prevention_matrix_drift_rules = drift_rule(
        "UNLOCK_PREVENTION_MATRIX_DRIFT",
        "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
        "immediate_stop",
        "SLA_IMMEDIATE_STOP",
        True,
    )
    no_drift_record_packet_drift_rules = drift_rule(
        "NO_DRIFT_RECORD_PACKET_DRIFT",
        "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
        "engineering_review",
        "SLA_STANDARD_ENGINEERING_REVIEW",
        True,
    )
    simulated_blocking_drift_case_drift_rules = drift_rule(
        "SIMULATED_BLOCKING_DRIFT_CASE_DRIFT",
        "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
        "compliance_review",
        "SLA_LEGAL_COMPLIANCE_REVIEW",
        True,
    )
    final_classification_drift_rules = drift_rule(
        "FINAL_CLASSIFICATION_DRIFT",
        "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
        "cto_review",
        "SLA_EXECUTIVE_REVIEW",
        True,
    )
    fingerprint_drift_rules = drift_rule(
        "FINGERPRINT_DRIFT",
        "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
        "engineering_review",
        "SLA_STANDARD_ENGINEERING_REVIEW",
        True,
    )

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

    source_replay_run_count = int(p137.get("replay_run_count", 0))
    source_evaluated_drift_event_count = int(p137.get("source_evaluated_drift_event_count", 0))

    blockers = sorted(
        set(
            p137.get("blockers", [])
            + [
                "DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_GOVERNANCE_ONLY_BLOCKER",
                "FULL_REGRESSION_NOT_RUN_BLOCKER",
                "LEGAL_PROVIDER_EVIDENCE_NOT_APPROVED_BLOCKER",
            ]
        )
    )

    final_classification = "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_READY_WITH_BLOCKERS"
    if governance_fail:
        final_classification = "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_FAILED_VALIDATION"

    summary = {
        "drift_alert_replay_drift_contract_status": "READY_WITH_BLOCKERS",
        "source_drift_alert_replay_consistency_gate_status": p137.get(
            "drift_alert_replay_consistency_gate_status", "UNKNOWN"
        ),
        "source_replay_run_count": source_replay_run_count,
        "source_evaluated_drift_event_count": source_evaluated_drift_event_count,
        "source_baseline_fingerprint": p137.get("baseline_fingerprint", ""),
        "source_drift_detected": bool(p137.get("drift_detected", True)),
        "alert_level_definitions": alert_level_definitions,
        "drift_type_definitions": drift_type_definitions,
        "escalation_path_definitions": escalation_path_definitions,
        "sla_class_definitions": sla_class_definitions,
        "required_owner_matrix": required_owner_matrix,
        "blocking_conditions": blocking_conditions,
        "baseline_change_review_rules": baseline_change_review_rules,
        "alert_verdict_drift_rules": alert_verdict_drift_rules,
        "escalation_decision_packet_drift_rules": escalation_decision_packet_drift_rules,
        "alert_level_matrix_drift_rules": alert_level_matrix_drift_rules,
        "drift_type_matrix_drift_rules": drift_type_matrix_drift_rules,
        "escalation_path_matrix_drift_rules": escalation_path_matrix_drift_rules,
        "sla_matrix_drift_rules": sla_matrix_drift_rules,
        "required_owner_matrix_drift_rules": required_owner_matrix_drift_rules,
        "blocked_action_matrix_drift_rules": blocked_action_matrix_drift_rules,
        "unlock_prevention_matrix_drift_rules": unlock_prevention_matrix_drift_rules,
        "no_drift_record_packet_drift_rules": no_drift_record_packet_drift_rules,
        "simulated_blocking_drift_case_drift_rules": simulated_blocking_drift_case_drift_rules,
        "final_classification_drift_rules": final_classification_drift_rules,
        "fingerprint_drift_rules": fingerprint_drift_rules,
        "drift_details_required_fields": DRIFT_DETAILS_REQUIRED_FIELDS,
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Replay drift contract does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "regression_status": {
            "targeted_p118_p138_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P138 task.",
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
        f.write("# P138 Drift Alert Replay Drift Contract (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- drift_alert_replay_drift_contract_status: {summary['drift_alert_replay_drift_contract_status']}\n")
        f.write(
            f"- source_drift_alert_replay_consistency_gate_status: {summary['source_drift_alert_replay_consistency_gate_status']}\n"
        )
        f.write(f"- source_replay_run_count: {summary['source_replay_run_count']}\n")
        f.write(f"- source_evaluated_drift_event_count: {summary['source_evaluated_drift_event_count']}\n")
        f.write(f"- source_drift_detected: {summary['source_drift_detected']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Contract Scope\n")
        f.write(f"- alert_levels: {sorted(summary['alert_level_definitions'].keys())}\n")
        f.write(f"- drift_types: {sorted(summary['drift_type_definitions'].keys())}\n")
        f.write(f"- escalation_paths: {sorted(summary['escalation_path_definitions'].keys())}\n")
        f.write(f"- sla_classes: {sorted(summary['sla_class_definitions'].keys())}\n")
        f.write(f"- required_owners: {sorted(set(sum(summary['required_owner_matrix'].values(), [])))}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p138_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")

    print(f"P138 summary written to {OUT_PATH}")
    print(f"P138 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
