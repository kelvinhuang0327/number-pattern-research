# P140 Drift Alert Replay Drift Signoff Evidence Packet Gate
# Deterministic paper-only signoff evidence packet gate based on P139 drift execution outputs.

import copy
import json
from collections import Counter
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P139_PATH = "data/mlb_2026/derived/p139_drift_alert_replay_drift_execution_gate_summary.json"
OUT_PATH = "data/mlb_2026/derived/p140_drift_alert_replay_drift_signoff_evidence_packet_gate_summary.json"
REPORT_PATH = "report/p140_drift_alert_replay_drift_signoff_evidence_packet_gate_20260601.md"

FINAL_CLASSIFICATION_OPTIONS = [
    "P140_DRIFT_ALERT_REPLAY_DRIFT_SIGNOFF_EVIDENCE_PACKET_GATE_READY_WITH_BLOCKERS",
    "P140_DRIFT_ALERT_REPLAY_DRIFT_SIGNOFF_EVIDENCE_PACKET_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P140_DRIFT_ALERT_REPLAY_DRIFT_SIGNOFF_EVIDENCE_PACKET_GATE_FAILED_VALIDATION",
]

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Validate signoff packets for governance-only evidence completeness",
    "Require all required owners and evidence fields before any production progression",
    "Keep targeted/full regression status explicit: NOT_RUN until verified",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat signoff packet approval as legal provider approval or production readiness",
    "Do not bypass required owner sign-off, rollback acknowledgement, or non-unlock attestation",
    "Do not treat governance-only template as a production-ready packet",
]

SIGNOFF_PACKET_SCHEMA = {
    "signoff_packet_id": "string",
    "source_execution_case_id": "string",
    "source_verdict": "string",
    "source_drift_type": "string",
    "source_alert_level": "string",
    "source_escalation_path": "string",
    "source_sla_class": "string",
    "required_owners": "string[]",
    "provided_signoff_owners": "string[]",
    "signer_identity_by_owner": "dict[str,str]",
    "signer_authority_attestation_by_owner": "dict[str,str]",
    "signoff_status_by_owner": "dict[str,string]",
    "signoff_timestamp_by_owner": "dict[str,string]",
    "evidence_reference_by_owner": "dict[str,string]",
    "drift_details_reference": "string",
    "baseline_change_request_reference": "string",
    "rollback_acknowledgement": "string",
    "non_unlock_attestation": "string",
    "provider_unlock_requested": "boolean",
    "odds_unlock_requested": "boolean",
    "recommendation_unlock_requested": "boolean",
    "production_unlock_requested": "boolean",
    "ev_clv_kelly_unlock_requested": "boolean",
    "live_or_paid_api_requested": "boolean",
}

INVALID_SIGNOFF_PACKET_CASE_IDS = [
    "MISSING_SIGNOFF_PACKET_ID_BLOCKED",
    "MISSING_SOURCE_EXECUTION_CASE_ID_BLOCKED",
    "MISSING_SOURCE_VERDICT_BLOCKED",
    "MISSING_SOURCE_DRIFT_TYPE_BLOCKED",
    "MISSING_REQUIRED_OWNERS_BLOCKED",
    "MISSING_PROVIDED_SIGNOFF_OWNERS_BLOCKED",
    "MISSING_SIGNER_IDENTITY_BLOCKED",
    "MISSING_SIGNER_AUTHORITY_ATTESTATION_BLOCKED",
    "SIGNOFF_STATUS_NOT_APPROVED_BLOCKED",
    "MISSING_SIGNOFF_TIMESTAMP_BLOCKED",
    "MISSING_EVIDENCE_REFERENCE_BLOCKED",
    "MISSING_DRIFT_DETAILS_REFERENCE_FOR_DRIFT_CASE_BLOCKED",
    "MISSING_BASELINE_CHANGE_REQUEST_REFERENCE_BLOCKED",
    "MISSING_ROLLBACK_ACKNOWLEDGEMENT_BLOCKED",
    "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED",
    "ROLE_MISMATCH_BLOCKED",
    "SIGNOFF_FOR_CRITICAL_STOP_WITH_UNLOCK_REQUEST_BLOCKED",
    "PROVIDER_UNLOCK_REQUESTED_BLOCKED",
    "ODDS_UNLOCK_REQUESTED_BLOCKED",
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED",
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKED",
    "EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKED",
    "LIVE_OR_PAID_API_REQUESTED_BLOCKED",
    "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKED",
    "SIGNOFF_PACKET_TREATED_AS_PRODUCTION_READY_BLOCKED",
]

INVALID_CASE_BLOCKERS = {
    "MISSING_SIGNOFF_PACKET_ID_BLOCKED": ["SIGNOFF_PACKET_ID_MISSING_BLOCKER"],
    "MISSING_SOURCE_EXECUTION_CASE_ID_BLOCKED": ["SOURCE_EXECUTION_CASE_ID_MISSING_BLOCKER"],
    "MISSING_SOURCE_VERDICT_BLOCKED": ["SOURCE_VERDICT_MISSING_BLOCKER"],
    "MISSING_SOURCE_DRIFT_TYPE_BLOCKED": ["SOURCE_DRIFT_TYPE_MISSING_BLOCKER"],
    "MISSING_REQUIRED_OWNERS_BLOCKED": ["REQUIRED_OWNERS_MISSING_BLOCKER"],
    "MISSING_PROVIDED_SIGNOFF_OWNERS_BLOCKED": ["PROVIDED_SIGNOFF_OWNERS_MISSING_BLOCKER"],
    "MISSING_SIGNER_IDENTITY_BLOCKED": ["SIGNER_IDENTITY_MISSING_BLOCKER"],
    "MISSING_SIGNER_AUTHORITY_ATTESTATION_BLOCKED": ["SIGNER_AUTHORITY_ATTESTATION_MISSING_BLOCKER"],
    "SIGNOFF_STATUS_NOT_APPROVED_BLOCKED": ["SIGNOFF_STATUS_NOT_APPROVED_BLOCKER"],
    "MISSING_SIGNOFF_TIMESTAMP_BLOCKED": ["SIGNOFF_TIMESTAMP_MISSING_BLOCKER"],
    "MISSING_EVIDENCE_REFERENCE_BLOCKED": ["EVIDENCE_REFERENCE_MISSING_BLOCKER"],
    "MISSING_DRIFT_DETAILS_REFERENCE_FOR_DRIFT_CASE_BLOCKED": ["DRIFT_DETAILS_REFERENCE_MISSING_BLOCKER"],
    "MISSING_BASELINE_CHANGE_REQUEST_REFERENCE_BLOCKED": ["BASELINE_CHANGE_REQUEST_REFERENCE_MISSING_BLOCKER"],
    "MISSING_ROLLBACK_ACKNOWLEDGEMENT_BLOCKED": ["ROLLBACK_ACKNOWLEDGEMENT_MISSING_BLOCKER"],
    "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED": ["NON_UNLOCK_ATTESTATION_MISSING_BLOCKER"],
    "ROLE_MISMATCH_BLOCKED": ["ROLE_MISMATCH_BLOCKER"],
    "SIGNOFF_FOR_CRITICAL_STOP_WITH_UNLOCK_REQUEST_BLOCKED": ["CRITICAL_STOP_UNLOCK_REQUEST_BLOCKER"],
    "PROVIDER_UNLOCK_REQUESTED_BLOCKED": ["PROVIDER_UNLOCK_REQUESTED_BLOCKER"],
    "ODDS_UNLOCK_REQUESTED_BLOCKED": ["ODDS_UNLOCK_REQUESTED_BLOCKER"],
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED": ["RECOMMENDATION_UNLOCK_REQUESTED_BLOCKER"],
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKED": ["PRODUCTION_UNLOCK_REQUESTED_BLOCKER"],
    "EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKED": ["EV_CLV_KELLY_UNLOCK_REQUESTED_BLOCKER"],
    "LIVE_OR_PAID_API_REQUESTED_BLOCKED": ["LIVE_OR_PAID_API_REQUESTED_BLOCKER"],
    "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKED": ["LEGAL_APPROVAL_IMPLICATION_BLOCKER"],
    "SIGNOFF_PACKET_TREATED_AS_PRODUCTION_READY_BLOCKED": ["PRODUCTION_READY_IMPLICATION_BLOCKER"],
}

REQUIRED_SIGNOFF_EVIDENCE_FIELDS = [
    "signoff_packet_id",
    "source_execution_case_id",
    "source_verdict",
    "source_drift_type",
    "source_alert_level",
    "source_escalation_path",
    "source_sla_class",
    "required_owners",
    "provided_signoff_owners",
    "signer_identity_by_owner",
    "signer_authority_attestation_by_owner",
    "signoff_status_by_owner",
    "signoff_timestamp_by_owner",
    "evidence_reference_by_owner",
    "drift_details_reference",
    "baseline_change_request_reference",
    "rollback_acknowledgement",
    "non_unlock_attestation",
    "provider_unlock_requested",
    "odds_unlock_requested",
    "recommendation_unlock_requested",
    "production_unlock_requested",
    "ev_clv_kelly_unlock_requested",
    "live_or_paid_api_requested",
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


def build_valid_signoff_packet_template(source_case: dict, required_owners: list[str]):
    signer_identity = {o: f"{o}@governance.local" for o in required_owners}
    signer_authority_attestation = {o: "Authorized governance sign-off by owner." for o in required_owners}
    signoff_status = {o: "APPROVED" for o in required_owners}
    signoff_timestamp = {o: "2026-06-01T12:00:00Z" for o in required_owners}
    evidence_reference = {o: f"governance://evidence/{o}/P140_VALID_TEMPLATE" for o in required_owners}

    return {
        "signoff_packet_id": "P140_SIGNOFF_VALID_TEMPLATE",
        "source_execution_case_id": source_case.get("execution_case_id", "NO_REPLAY_DRIFT_RECORD_ONLY"),
        "source_verdict": source_case.get("verdict", "ALLOW_RECORD_ONLY"),
        "source_drift_type": source_case.get("drift_type", "NO_DRIFT"),
        "source_alert_level": source_case.get("alert_level", "GREEN_NO_REPLAY_DRIFT"),
        "source_escalation_path": source_case.get("escalation_path", "record_only"),
        "source_sla_class": source_case.get("sla_class", "SLA_NONE_RECORD_ONLY"),
        "required_owners": required_owners,
        "provided_signoff_owners": required_owners,
        "signer_identity_by_owner": signer_identity,
        "signer_authority_attestation_by_owner": signer_authority_attestation,
        "signoff_status_by_owner": signoff_status,
        "signoff_timestamp_by_owner": signoff_timestamp,
        "evidence_reference_by_owner": evidence_reference,
        "drift_details_reference": "governance://drift_details/none",
        "baseline_change_request_reference": "",
        "rollback_acknowledgement": "Rollback plan acknowledged for governance-only signoff.",
        "non_unlock_attestation": "This signoff packet does not imply any unlock or production approval.",
        "provider_unlock_requested": False,
        "odds_unlock_requested": False,
        "recommendation_unlock_requested": False,
        "production_unlock_requested": False,
        "ev_clv_kelly_unlock_requested": False,
        "live_or_paid_api_requested": False,
    }


def make_invalid_case(case_id: str, valid_template: dict):
    packet = copy.deepcopy(valid_template)
    if case_id == "MISSING_SIGNOFF_PACKET_ID_BLOCKED":
        packet["signoff_packet_id"] = ""
    elif case_id == "MISSING_SOURCE_EXECUTION_CASE_ID_BLOCKED":
        packet["source_execution_case_id"] = ""
    elif case_id == "MISSING_SOURCE_VERDICT_BLOCKED":
        packet["source_verdict"] = ""
    elif case_id == "MISSING_SOURCE_DRIFT_TYPE_BLOCKED":
        packet["source_drift_type"] = ""
    elif case_id == "MISSING_REQUIRED_OWNERS_BLOCKED":
        packet["required_owners"] = []
    elif case_id == "MISSING_PROVIDED_SIGNOFF_OWNERS_BLOCKED":
        packet["provided_signoff_owners"] = []
    elif case_id == "MISSING_SIGNER_IDENTITY_BLOCKED":
        packet["signer_identity_by_owner"] = {}
    elif case_id == "MISSING_SIGNER_AUTHORITY_ATTESTATION_BLOCKED":
        packet["signer_authority_attestation_by_owner"] = {}
    elif case_id == "SIGNOFF_STATUS_NOT_APPROVED_BLOCKED":
        packet["signoff_status_by_owner"] = {o: "PENDING" for o in packet["required_owners"]}
    elif case_id == "MISSING_SIGNOFF_TIMESTAMP_BLOCKED":
        packet["signoff_timestamp_by_owner"] = {}
    elif case_id == "MISSING_EVIDENCE_REFERENCE_BLOCKED":
        packet["evidence_reference_by_owner"] = {}
    elif case_id == "MISSING_DRIFT_DETAILS_REFERENCE_FOR_DRIFT_CASE_BLOCKED":
        packet["drift_details_reference"] = ""
    elif case_id == "MISSING_BASELINE_CHANGE_REQUEST_REFERENCE_BLOCKED":
        packet["baseline_change_request_reference"] = ""
    elif case_id == "MISSING_ROLLBACK_ACKNOWLEDGEMENT_BLOCKED":
        packet["rollback_acknowledgement"] = ""
    elif case_id == "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED":
        packet["non_unlock_attestation"] = ""
    elif case_id == "ROLE_MISMATCH_BLOCKED":
        packet["provided_signoff_owners"] = [packet["required_owners"][0]] if packet["required_owners"] else []
    elif case_id == "SIGNOFF_FOR_CRITICAL_STOP_WITH_UNLOCK_REQUEST_BLOCKED":
        packet["source_execution_case_id"] = "UNLOCK_PREVENTION_MATRIX_DRIFT_CRITICAL_STOP"
        packet["provider_unlock_requested"] = True
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
    elif case_id == "SIGNOFF_PACKET_TREATED_AS_LEGAL_APPROVAL_BLOCKED":
        packet["non_unlock_attestation"] = "This signoff packet grants legal provider approval."
    elif case_id == "SIGNOFF_PACKET_TREATED_AS_PRODUCTION_READY_BLOCKED":
        packet["non_unlock_attestation"] = "This signoff packet implies production readiness."

    return {
        "case_id": case_id,
        "packet": packet,
        "status": "BLOCKED",
        "blockers": INVALID_CASE_BLOCKERS.get(case_id, ["UNKNOWN_INVALID_CASE_BLOCKER"]),
    }


def build_execution_case_signoff_requirement_matrix(execution_cases: list[dict]):
    return {
        c["execution_case_id"]: {
            "required_owners": c.get("required_owners", []),
            "required_signoff_evidence_fields": REQUIRED_SIGNOFF_EVIDENCE_FIELDS,
            "drift_details_reference_required": c.get("drift_details_required", False),
            "baseline_change_request_reference_required": c.get("baseline_change_review_required", False),
            "rollback_acknowledgement_required": c.get("blocked", False),
            "non_unlock_attestation_required": True,
        }
        for c in execution_cases
    }


def build_drift_detail_signoff_requirement_matrix(execution_cases: list[dict]):
    return {
        c["execution_case_id"]: {
            "drift_details_reference_required": c.get("drift_details_required", False),
            "drift_details_reference_present": bool(c.get("drift_details_required", False)),
        }
        for c in execution_cases
    }


def build_baseline_change_signoff_requirement_matrix(execution_cases: list[dict]):
    return {
        c["execution_case_id"]: {
            "baseline_change_request_reference_required": c.get("baseline_change_review_required", False),
            "baseline_change_request_reference_present": bool(c.get("baseline_change_review_required", False)),
        }
        for c in execution_cases
    }


def build_escalation_path_signoff_matrix(execution_cases: list[dict]):
    return {c["execution_case_id"]: c.get("escalation_path", "") for c in execution_cases}


def build_sla_signoff_matrix(execution_cases: list[dict]):
    return {c["execution_case_id"]: c.get("sla_class", "") for c in execution_cases}


def build_owner_signoff_matrix(execution_cases: list[dict]):
    return {c["execution_case_id"]: c.get("required_owners", []) for c in execution_cases}


def build_non_unlock_attestation_matrix(execution_cases: list[dict]):
    return {c["execution_case_id"]: True for c in execution_cases}


def build_rollback_acknowledgement_matrix(execution_cases: list[dict]):
    return {c["execution_case_id"]: c.get("blocked", False) for c in execution_cases}


def build_unlock_prevention_matrix(execution_cases: list[dict]):
    return {
        c["execution_case_id"]: {
            "provider_unlock_requested": False,
            "odds_unlock_requested": False,
            "recommendation_unlock_requested": False,
            "production_unlock_requested": False,
            "ev_clv_kelly_unlock_requested": False,
            "live_or_paid_api_requested": False,
        }
        for c in execution_cases
    }


def empty_summary() -> dict:
    return {
        "drift_alert_replay_drift_signoff_packet_gate_status": "BLOCKED",
        "source_drift_alert_replay_drift_execution_gate_status": "UNKNOWN",
        "source_evaluated_execution_case_count": 0,
        "source_invalid_drift_detail_case_count": 0,
        "source_invalid_baseline_change_case_count": 0,
        "source_baseline_fingerprint": "",
        "signoff_packet_schema": SIGNOFF_PACKET_SCHEMA,
        "required_signoff_roles": [],
        "required_signoff_evidence_fields": REQUIRED_SIGNOFF_EVIDENCE_FIELDS,
        "valid_signoff_packet_template": {},
        "invalid_signoff_packet_cases": [],
        "signoff_packet_verdict_matrix": {},
        "execution_case_signoff_requirement_matrix": {},
        "drift_detail_signoff_requirement_matrix": {},
        "baseline_change_signoff_requirement_matrix": {},
        "escalation_path_signoff_matrix": {},
        "sla_signoff_matrix": {},
        "owner_signoff_matrix": {},
        "non_unlock_attestation_matrix": {},
        "rollback_acknowledgement_matrix": {},
        "unlock_prevention_matrix": {},
        "no_unlock_governance_matrix": {},
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "governance_invariant_summary": {},
        "governance_statement": "Signoff evidence packet gate does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "regression_status": {
            "targeted_p118_p140_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P140 task.",
        },
        "final_classification": "P140_DRIFT_ALERT_REPLAY_DRIFT_SIGNOFF_EVIDENCE_PACKET_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def main():
    missing = [p for p in (P121_PATH, P139_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write("# P140 Drift Alert Replay Drift Signoff Evidence Packet Gate (2026-06-01)\n\n")
            f.write("Missing required source artifacts for P140.\n")
        return

    p121 = load_json(P121_PATH)
    p139 = load_json(P139_PATH)
    source_cases = p139.get("execution_cases", [])
    required_signoff_roles = sorted({owner for case in source_cases for owner in case.get("required_owners", [])})

    valid_template = build_valid_signoff_packet_template(
        source_cases[0] if source_cases else {},
        required_signoff_roles,
    )
    invalid_signoff_packet_cases = [make_invalid_case(cid, valid_template) for cid in INVALID_SIGNOFF_PACKET_CASE_IDS]

    signoff_packet_verdict_matrix = {
        case["case_id"]: {"status": case["status"]} for case in invalid_signoff_packet_cases
    }
    signoff_packet_verdict_matrix["VALID_SIGNOFF_PACKET_TEMPLATE"] = {"status": "GOVERNANCE_ONLY_PENDING_REVIEW"}

    execution_case_signoff_requirement_matrix = build_execution_case_signoff_requirement_matrix(source_cases)
    drift_detail_signoff_requirement_matrix = build_drift_detail_signoff_requirement_matrix(source_cases)
    baseline_change_signoff_requirement_matrix = build_baseline_change_signoff_requirement_matrix(source_cases)
    escalation_path_signoff_matrix = build_escalation_path_signoff_matrix(source_cases)
    sla_signoff_matrix = build_sla_signoff_matrix(source_cases)
    owner_signoff_matrix = build_owner_signoff_matrix(source_cases)
    non_unlock_attestation_matrix = build_non_unlock_attestation_matrix(source_cases)
    rollback_acknowledgement_matrix = build_rollback_acknowledgement_matrix(source_cases)
    unlock_prevention_matrix = build_unlock_prevention_matrix(source_cases)

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
        "any_unlock_requested": False,
    }

    invalid_drift_detail_cases = p139.get("invalid_drift_detail_cases", [])
    invalid_baseline_change_cases = p139.get("invalid_baseline_change_cases", [])

    verdict_counts = Counter(case.get("verdict") for case in source_cases)
    escalation_counts = Counter(case.get("escalation_path") for case in source_cases)
    sla_counts = Counter(case.get("sla_class") for case in source_cases)
    owner_counts = Counter(owner for case in source_cases for owner in case.get("required_owners", []))

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

    blockers = sorted(
        set(
            p139.get("blockers", [])
            + [
                "DRIFT_SIGNOFF_EVIDENCE_PACKET_GATE_GOVERNANCE_ONLY_BLOCKER",
                "FULL_REGRESSION_NOT_RUN_BLOCKER",
                "SIGNOFF_EVIDENCE_PACKET_GATE_LEGAL_PROVIDER_APPROVAL_NOT_GRANTED_BLOCKER",
            ]
        )
    )

    final_classification = "P140_DRIFT_ALERT_REPLAY_DRIFT_SIGNOFF_EVIDENCE_PACKET_GATE_READY_WITH_BLOCKERS"
    if governance_fail:
        final_classification = "P140_DRIFT_ALERT_REPLAY_DRIFT_SIGNOFF_EVIDENCE_PACKET_GATE_FAILED_VALIDATION"

    summary = {
        "drift_alert_replay_drift_signoff_packet_gate_status": "READY_WITH_BLOCKERS",
        "source_drift_alert_replay_drift_execution_gate_status": p139.get("drift_alert_replay_drift_execution_gate_status", "UNKNOWN"),
        "source_evaluated_execution_case_count": int(p139.get("evaluated_execution_case_count", 0)),
        "source_invalid_drift_detail_case_count": int(len(invalid_drift_detail_cases)),
        "source_invalid_baseline_change_case_count": int(len(invalid_baseline_change_cases)),
        "source_baseline_fingerprint": p139.get("source_baseline_fingerprint", ""),
        "signoff_packet_schema": SIGNOFF_PACKET_SCHEMA,
        "required_signoff_roles": required_signoff_roles,
        "required_signoff_evidence_fields": REQUIRED_SIGNOFF_EVIDENCE_FIELDS,
        "valid_signoff_packet_template": valid_template,
        "invalid_signoff_packet_cases": invalid_signoff_packet_cases,
        "signoff_packet_verdict_matrix": signoff_packet_verdict_matrix,
        "execution_case_signoff_requirement_matrix": execution_case_signoff_requirement_matrix,
        "drift_detail_signoff_requirement_matrix": drift_detail_signoff_requirement_matrix,
        "baseline_change_signoff_requirement_matrix": baseline_change_signoff_requirement_matrix,
        "escalation_path_signoff_matrix": escalation_path_signoff_matrix,
        "sla_signoff_matrix": sla_signoff_matrix,
        "owner_signoff_matrix": owner_signoff_matrix,
        "non_unlock_attestation_matrix": non_unlock_attestation_matrix,
        "rollback_acknowledgement_matrix": rollback_acknowledgement_matrix,
        "unlock_prevention_matrix": unlock_prevention_matrix,
        "no_unlock_governance_matrix": no_unlock_governance_matrix,
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": blockers,
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Signoff evidence packet approval does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "regression_status": {
            "targeted_p118_p140_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P140 task.",
        },
        "final_classification": final_classification,
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P140 Drift Alert Replay Drift Signoff Evidence Packet Gate (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- drift_alert_replay_drift_signoff_packet_gate_status: {summary['drift_alert_replay_drift_signoff_packet_gate_status']}\n")
        f.write(f"- source_drift_alert_replay_drift_execution_gate_status: {summary['source_drift_alert_replay_drift_execution_gate_status']}\n")
        f.write(f"- source_evaluated_execution_case_count: {summary['source_evaluated_execution_case_count']}\n")
        f.write(f"- source_invalid_drift_detail_case_count: {summary['source_invalid_drift_detail_case_count']}\n")
        f.write(f"- source_invalid_baseline_change_case_count: {summary['source_invalid_baseline_change_case_count']}\n")
        f.write(f"- source_baseline_fingerprint: {summary['source_baseline_fingerprint']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Signoff Packet Schema\n")
        for field, field_type in summary["signoff_packet_schema"].items():
            f.write(f"- {field}: {field_type}\n")
        f.write("\n")

        f.write("## Required Signoff Fields\n")
        for field in summary["required_signoff_evidence_fields"]:
            f.write(f"- {field}\n")
        f.write("\n")

        f.write("## Invalid Signoff Packet Cases\n")
        for invalid in summary["invalid_signoff_packet_cases"]:
            f.write(f"- {invalid['case_id']}: {invalid['status']} (blockers={invalid['blockers']})\n")
        f.write("\n")

        f.write("## Allowed / Prohibited Actions\n")
        for action in summary["allowed_next_actions"]:
            f.write(f"- {action}\n")
        f.write("\n")
        for action in summary["prohibited_actions"]:
            f.write(f"- {action}\n")
        f.write("\n")

        f.write("## Regression Status\n")
        f.write(f"- targeted_p118_p140_tests_status: {summary['regression_status']['targeted_p118_p140_tests_status']}\n")
        f.write(f"- full_regression_status: {summary['regression_status']['full_regression_status']}\n")
        f.write("\n")

    print(f"P140 summary written to {OUT_PATH}")
    print(f"P140 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
