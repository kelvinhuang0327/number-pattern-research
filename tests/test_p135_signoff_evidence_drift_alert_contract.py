# P135 Sign-off Evidence Drift Alert Contract - Dedicated Test
import json
from pathlib import Path

P134_PATH = "data/mlb_2026/derived/p134_signoff_evidence_replay_consistency_gate_summary.json"
P135_PATH = "data/mlb_2026/derived/p135_signoff_evidence_drift_alert_contract_summary.json"

REQUIRED_TOP_LEVEL_KEYS = {
    "signoff_drift_alert_contract_status",
    "source_signoff_replay_gate_status",
    "source_replay_run_count",
    "source_signoff_packet_count",
    "source_invalid_packet_count",
    "source_baseline_fingerprint",
    "source_drift_detected",
    "alert_level_definitions",
    "drift_type_definitions",
    "escalation_path_definitions",
    "sla_class_definitions",
    "required_signoff_owner_matrix",
    "blocking_conditions",
    "verdict_matrix_drift_rules",
    "blocker_classification_drift_rules",
    "required_evidence_matrix_drift_rules",
    "escalation_level_coverage_drift_rules",
    "governance_invariant_drift_rules",
    "unlock_prevention_drift_rules",
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
    "GREEN_NO_SIGNOFF_DRIFT",
    "YELLOW_SIGNOFF_METADATA_ONLY_DRIFT",
    "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
    "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
    "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
}

REQUIRED_DRIFT_TYPES = {
    "FINGERPRINT_DRIFT",
    "SIGNOFF_VERDICT_MATRIX_DRIFT",
    "BLOCKER_CLASSIFICATION_DRIFT",
    "REQUIRED_EVIDENCE_MATRIX_DRIFT",
    "ESCALATION_LEVEL_COVERAGE_DRIFT",
    "GOVERNANCE_INVARIANT_DRIFT",
    "UNLOCK_PREVENTION_DRIFT",
    "SIGNOFF_PACKET_COUNT_DRIFT",
    "INVALID_PACKET_COUNT_DRIFT",
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

REQUIRED_DRIFT_DETAIL_FIELDS = {
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
}

FINAL_CLASSIFICATIONS = {
    "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_READY_WITH_BLOCKERS",
    "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
    "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_FAILED_VALIDATION",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_p135_summary_exists():
    assert Path(P135_PATH).exists(), "P135 summary JSON missing"


def test_required_top_level_sections_present():
    d = load_json(P135_PATH)
    assert REQUIRED_TOP_LEVEL_KEYS.issubset(set(d.keys()))


def test_source_values_match_p134():
    p134 = load_json(P134_PATH)
    p135 = load_json(P135_PATH)

    assert p135["source_signoff_replay_gate_status"] == p134["signoff_replay_consistency_gate_status"]
    assert p135["source_replay_run_count"] == p134["replay_run_count"]
    assert p135["source_signoff_packet_count"] == p134["source_signoff_packet_count"]
    assert p135["source_invalid_packet_count"] == p134["source_invalid_packet_count"]
    assert p135["source_baseline_fingerprint"] == p134["baseline_fingerprint"]
    assert p135["source_drift_detected"] == p134["drift_detected"]


def test_required_contract_definitions_present():
    d = load_json(P135_PATH)

    assert REQUIRED_ALERT_LEVELS.issubset(set(d["alert_level_definitions"].keys()))
    assert REQUIRED_DRIFT_TYPES.issubset(set(d["drift_type_definitions"].keys()))
    assert REQUIRED_ESCALATION_PATHS.issubset(set(d["escalation_path_definitions"].keys()))
    assert REQUIRED_SLA_CLASSES.issubset(set(d["sla_class_definitions"].keys()))

    matrix_roles = set()
    for _, roles in d["required_signoff_owner_matrix"].items():
        matrix_roles.update(roles)
    assert REQUIRED_OWNERS.issubset(matrix_roles)


def test_blocking_conditions_cover_required_cases():
    d = load_json(P135_PATH)
    conditions = [row["condition"] for row in d["blocking_conditions"]]

    required_condition_phrases = [
        "any previously BLOCKED sign-off verdict becomes ALLOWED",
        "valid_signoff_packet_template becomes production-ready",
        "source_signoff_packet_count changes without approved baseline update",
        "source_invalid_packet_count changes without approved baseline update",
        "blocker classifications change without approved review",
        "required evidence matrix changes without approved review",
        "escalation coverage changes without approved review",
        "governance invariants become false",
        "provider_approved becomes true without verified legal evidence",
        "authorization_evidence_present becomes true without verified legal evidence",
        "recommendation_allowed becomes true",
        "production_ready becomes true",
        "EV/CLV/Kelly/stake/profit unlock becomes true",
        "real_legal_odds_ingested becomes true without explicit legal/provider approval",
        "live_api_calls or paid_api_called becomes non-zero",
        "drift_detected=true but drift_details is missing or incomplete",
    ]

    for phrase in required_condition_phrases:
        assert phrase in conditions

    for row in d["blocking_conditions"]:
        assert row["classification"] == "BLOCKED"
        assert len(row["required_signoff_owners"]) >= 1


def test_drift_detail_fields_and_governance_statement():
    d = load_json(P135_PATH)
    assert REQUIRED_DRIFT_DETAIL_FIELDS.issubset(set(d["drift_details_required_fields"]))
    assert "does not imply legal provider approval" in d["governance_statement"]


def test_governance_invariants_remain_safe():
    d = load_json(P135_PATH)
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
    d = load_json(P135_PATH)
    assert d["regression_status"]["full_regression_status"] == "NOT_RUN"
    assert d["final_classification"] in FINAL_CLASSIFICATIONS
    assert d["final_classification"] == "P135_SIGNOFF_EVIDENCE_DRIFT_ALERT_CONTRACT_READY_WITH_BLOCKERS"
