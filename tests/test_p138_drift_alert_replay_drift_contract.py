# P138 Drift Alert Replay Drift Contract - Dedicated Test
import json
from pathlib import Path

P138_PATH = "data/mlb_2026/derived/p138_drift_alert_replay_drift_contract_summary.json"
P137_PATH = "data/mlb_2026/derived/p137_drift_alert_replay_consistency_gate_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "drift_alert_replay_drift_contract_status",
    "source_drift_alert_replay_consistency_gate_status",
    "source_replay_run_count",
    "source_evaluated_drift_event_count",
    "source_baseline_fingerprint",
    "source_drift_detected",
    "alert_level_definitions",
    "drift_type_definitions",
    "escalation_path_definitions",
    "sla_class_definitions",
    "required_owner_matrix",
    "blocking_conditions",
    "baseline_change_review_rules",
    "alert_verdict_drift_rules",
    "escalation_decision_packet_drift_rules",
    "alert_level_matrix_drift_rules",
    "drift_type_matrix_drift_rules",
    "escalation_path_matrix_drift_rules",
    "sla_matrix_drift_rules",
    "required_owner_matrix_drift_rules",
    "blocked_action_matrix_drift_rules",
    "unlock_prevention_matrix_drift_rules",
    "no_drift_record_packet_drift_rules",
    "simulated_blocking_drift_case_drift_rules",
    "final_classification_drift_rules",
    "fingerprint_drift_rules",
    "drift_details_required_fields",
    "allowed_next_actions",
    "prohibited_actions",
    "blockers",
    "final_classification",
    "governance_invariant_summary",
    "governance_statement",
    "regression_status",
}

REQUIRED_ALERT_LEVELS = {
    "GREEN_NO_REPLAY_DRIFT",
    "YELLOW_REPLAY_METADATA_ONLY_DRIFT",
    "ORANGE_REPLAY_MATRIX_OR_PACKET_DRIFT",
    "RED_REPLAY_VERDICT_OR_BLOCKED_ACTION_DRIFT",
    "CRITICAL_REPLAY_UNLOCK_OR_PROVIDER_DRIFT",
}

REQUIRED_DRIFT_TYPES = {
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
}

REQUIRED_ESCALATION_PATHS = {
    "record_only",
    "engineering_review",
    "cto_review",
    "legal_review",
    "compliance_review",
    "security_review",
    "ceo_review",
    "immediate_stop",
}

REQUIRED_SLA_CLASSES = {
    "SLA_NONE_RECORD_ONLY",
    "SLA_STANDARD_ENGINEERING_REVIEW",
    "SLA_CTO_REVIEW",
    "SLA_LEGAL_COMPLIANCE_REVIEW",
    "SLA_SECURITY_REVIEW",
    "SLA_EXECUTIVE_REVIEW",
    "SLA_IMMEDIATE_STOP",
}

REQUIRED_OWNERS = {
    "engineering_owner",
    "cto_owner",
    "legal_owner",
    "compliance_owner",
    "ceo_owner",
    "data_rights_owner",
    "security_owner",
}

REQUIRED_BLOCKING_RULE_SNIPPETS = {
    "any previously BLOCKED drift case becomes ALLOWED",
    "any CRITICAL_STOP case downgrades without approved baseline change",
    "no-drift record-only case changes verdict without approved baseline change",
    "evaluated_drift_event_count changes without approved baseline update",
    "replay_run_count changes without approved baseline update",
    "alert verdict matrix changes without approved review",
    "escalation decision packets change without approved review",
    "blocked action matrix changes without approved review",
    "unlock prevention matrix changes without approved review",
    "final classification changes without approved review",
    "baseline fingerprint changes without approved baseline change request",
    "provider_approved becomes true without verified legal evidence",
    "authorization_evidence_present becomes true without verified legal evidence",
    "recommendation_allowed becomes true",
    "production_ready becomes true",
    "EV/CLV/Kelly/stake/profit unlock becomes true",
    "real_legal_odds_ingested becomes true without explicit legal/provider approval",
    "live_api_calls or paid_api_called becomes non-zero",
    "drift_detected=true but drift_details is missing or incomplete",
}

REQUIRED_BASELINE_CHANGE_FIELDS = {
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
}

REQUIRED_DRIFT_DETAIL_FIELDS = {
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
}

FINAL_CLASSIFICATIONS = {
    "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_READY_WITH_BLOCKERS",
    "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
    "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p138_summary_exists():
    assert Path(P138_PATH).exists(), "P138 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P138_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_values_align_with_p137():
    p137 = load_json(P137_PATH)
    p138 = load_json(P138_PATH)

    assert p138["source_drift_alert_replay_consistency_gate_status"] == p137["drift_alert_replay_consistency_gate_status"]
    assert p138["source_replay_run_count"] == p137["replay_run_count"]
    assert p138["source_evaluated_drift_event_count"] == p137["source_evaluated_drift_event_count"]
    assert p138["source_baseline_fingerprint"] == p137["baseline_fingerprint"]
    assert p138["source_drift_detected"] == p137["drift_detected"]


def test_required_contract_taxonomy_present():
    d = load_json(P138_PATH)

    assert REQUIRED_ALERT_LEVELS.issubset(set(d["alert_level_definitions"].keys()))
    assert REQUIRED_DRIFT_TYPES.issubset(set(d["drift_type_definitions"].keys()))
    assert REQUIRED_ESCALATION_PATHS.issubset(set(d["escalation_path_definitions"].keys()))
    assert REQUIRED_SLA_CLASSES.issubset(set(d["sla_class_definitions"].keys()))

    owners = set()
    for group in d["required_owner_matrix"].values():
        owners.update(group)
    assert REQUIRED_OWNERS.issubset(owners)


def test_required_blocking_conditions_and_baseline_review_rules_present():
    d = load_json(P138_PATH)

    all_rules = {item["rule"] for item in d["blocking_conditions"]}
    assert REQUIRED_BLOCKING_RULE_SNIPPETS.issubset(all_rules)

    baseline_fields = set(d["baseline_change_review_rules"]["required_fields"])
    assert REQUIRED_BASELINE_CHANGE_FIELDS.issubset(baseline_fields)
    assert "does not imply provider approval" in d["baseline_change_review_rules"]["non_unlock_governance_statement"]


def test_required_drift_rule_sections_and_drift_details_schema_present():
    d = load_json(P138_PATH)

    for section in [
        "alert_verdict_drift_rules",
        "escalation_decision_packet_drift_rules",
        "alert_level_matrix_drift_rules",
        "drift_type_matrix_drift_rules",
        "escalation_path_matrix_drift_rules",
        "sla_matrix_drift_rules",
        "required_owner_matrix_drift_rules",
        "blocked_action_matrix_drift_rules",
        "unlock_prevention_matrix_drift_rules",
        "no_drift_record_packet_drift_rules",
        "simulated_blocking_drift_case_drift_rules",
        "final_classification_drift_rules",
        "fingerprint_drift_rules",
    ]:
        assert section in d
        assert d[section]["blocked_if_unapproved"] is True

    assert REQUIRED_DRIFT_DETAIL_FIELDS.issubset(set(d["drift_details_required_fields"]))


def test_governance_invariants_remain_safe_and_no_unlock_language():
    d = load_json(P138_PATH)
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

    statement = d["governance_statement"].lower()
    assert "does not imply" in statement
    assert "provider approval" in statement
    assert "recommendation readiness" in statement
    assert "production readiness" in statement


def test_regression_status_and_final_classification():
    d = load_json(P138_PATH)

    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P138_DRIFT_ALERT_REPLAY_DRIFT_CONTRACT_READY_WITH_BLOCKERS"
