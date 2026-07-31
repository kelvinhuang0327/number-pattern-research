# P136 Sign-off Drift Alert Runner + Escalation Decision Packet
# Deterministic paper-only drift alert runner built from P135 contract and P134 replay state.

import json
from collections import defaultdict
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P134_PATH = "data/mlb_2026/derived/p134_signoff_evidence_replay_consistency_gate_summary.json"
P135_PATH = "data/mlb_2026/derived/p135_signoff_evidence_drift_alert_contract_summary.json"
OUT_PATH = "data/mlb_2026/derived/p136_signoff_drift_alert_runner_escalation_decision_packet_summary.json"
REPORT_PATH = "report/p136_signoff_drift_alert_runner_escalation_decision_packet_20260601.md"

FINAL_CLASSIFICATION_OPTIONS = [
    "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_READY_WITH_BLOCKERS",
    "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_BLOCKED_BY_MISSING_ARTIFACTS",
    "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_FAILED_VALIDATION",
]

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use sign-off drift alert runner output for governance diagnostics only",
    "Require approved baseline review before accepting drift contract changes",
    "Keep full regression state explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat drift alert routing as legal provider approval or production readiness",
    "Do not bypass blocker resolution and required sign-off owner routing",
]

REQUIRED_PACKET_FIELDS = [
    "drift_case_id",
    "drift_type",
    "alert_level",
    "source_packet_or_matrix",
    "verdict",
    "blocked",
    "critical_stop",
    "escalation_path",
    "sla_class",
    "required_signoff_owners",
    "affected_roles",
    "affected_blocker_codes",
    "affected_unlock_flags",
    "remediation_required",
    "rollback_required",
    "non_unlock_attestation_required",
    "next_required_action",
    "provider_unlock_allowed",
    "odds_unlock_allowed",
    "recommendation_unlock_allowed",
    "production_unlock_allowed",
    "ev_clv_kelly_unlock_allowed",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def governance_invariants(p121: dict):
    g = p121.get("governance_flags", {})
    return {
        "paper_only": bool(g.get("paper_only", False)),
        "diagnostic_only": bool(g.get("diagnostic_only", False)),
        "production_ready": bool(g.get("production_ready", False)),
        "real_bet_allowed": bool(g.get("real_bet_allowed", False)),
        "recommendation_allowed": bool(g.get("recommendation_allowed", False)),
        "provider_approved": bool(g.get("provider_approved", False)),
        "authorization_evidence_present": bool(g.get("authorization_evidence_present", False)),
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


def packet(case: dict, required_owner_matrix: dict):
    owners = required_owner_matrix.get(case["alert_level"], ["engineering_owner"])
    return {
        "drift_case_id": case["drift_case_id"],
        "drift_type": case["drift_type"],
        "alert_level": case["alert_level"],
        "source_packet_or_matrix": case["source_packet_or_matrix"],
        "verdict": case["verdict"],
        "blocked": case["blocked"],
        "critical_stop": case["critical_stop"],
        "escalation_path": case["escalation_path"],
        "sla_class": case["sla_class"],
        "required_signoff_owners": owners,
        "affected_roles": case["affected_roles"],
        "affected_blocker_codes": case["affected_blocker_codes"],
        "affected_unlock_flags": case["affected_unlock_flags"],
        "remediation_required": case["blocked"],
        "rollback_required": case["blocked"],
        "non_unlock_attestation_required": True,
        "next_required_action": case["next_required_action"],
        "provider_unlock_allowed": False,
        "odds_unlock_allowed": False,
        "recommendation_unlock_allowed": False,
        "production_unlock_allowed": False,
        "ev_clv_kelly_unlock_allowed": False,
    }


def build_cases():
    return [
        {
            "drift_case_id": "NO_SIGNOFF_DRIFT_RECORD_ONLY",
            "drift_type": "NO_DRIFT",
            "alert_level": "GREEN_NO_SIGNOFF_DRIFT",
            "source_packet_or_matrix": "replay_consistency_overview",
            "verdict": "RECORD_ONLY_NO_DRIFT",
            "blocked": False,
            "critical_stop": False,
            "escalation_path": "record_only",
            "sla_class": "SLA_NONE_RECORD_ONLY",
            "affected_roles": ["engineering_owner"],
            "affected_blocker_codes": [],
            "affected_unlock_flags": [],
            "next_required_action": "Record no-drift run and continue governance monitoring.",
        },
        {
            "drift_case_id": "FINGERPRINT_DRIFT_BLOCKED",
            "drift_type": "FINGERPRINT_DRIFT",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "source_packet_or_matrix": "baseline_fingerprint",
            "verdict": "BLOCKED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "affected_roles": ["engineering_owner", "compliance_owner"],
            "affected_blocker_codes": ["BASELINE_FINGERPRINT_DRIFT_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Open engineering review and baseline change packet.",
        },
        {
            "drift_case_id": "SIGNOFF_VERDICT_MATRIX_DRIFT_BLOCKED",
            "drift_type": "SIGNOFF_VERDICT_MATRIX_DRIFT",
            "alert_level": "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
            "source_packet_or_matrix": "replay_signoff_verdict_matrix",
            "verdict": "BLOCKED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "cto_review",
            "sla_class": "SLA_CTO_REVIEW",
            "affected_roles": ["engineering_owner", "cto_owner"],
            "affected_blocker_codes": ["SIGNOFF_VERDICT_MATRIX_DRIFT_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Escalate verdict matrix drift to CTO review.",
        },
        {
            "drift_case_id": "BLOCKER_CLASSIFICATION_DRIFT_BLOCKED",
            "drift_type": "BLOCKER_CLASSIFICATION_DRIFT",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "source_packet_or_matrix": "replay_blocker_matrix",
            "verdict": "BLOCKED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "compliance_review",
            "sla_class": "SLA_LEGAL_COMPLIANCE_REVIEW",
            "affected_roles": ["compliance_owner", "legal_owner"],
            "affected_blocker_codes": ["BLOCKER_CLASSIFICATION_DRIFT_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Run compliance blocker reclassification review.",
        },
        {
            "drift_case_id": "REQUIRED_EVIDENCE_MATRIX_DRIFT_BLOCKED",
            "drift_type": "REQUIRED_EVIDENCE_MATRIX_DRIFT",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "source_packet_or_matrix": "replay_required_evidence_matrix",
            "verdict": "BLOCKED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "legal_review",
            "sla_class": "SLA_LEGAL_COMPLIANCE_REVIEW",
            "affected_roles": ["legal_owner", "compliance_owner"],
            "affected_blocker_codes": ["REQUIRED_EVIDENCE_MATRIX_DRIFT_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Request legal evidence matrix reconciliation.",
        },
        {
            "drift_case_id": "ESCALATION_LEVEL_COVERAGE_DRIFT_BLOCKED",
            "drift_type": "ESCALATION_LEVEL_COVERAGE_DRIFT",
            "alert_level": "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
            "source_packet_or_matrix": "escalation_level_coverage_matrix",
            "verdict": "BLOCKED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "cto_review",
            "sla_class": "SLA_CTO_REVIEW",
            "affected_roles": ["cto_owner", "engineering_owner"],
            "affected_blocker_codes": ["ESCALATION_LEVEL_COVERAGE_DRIFT_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Reconcile escalation coverage and approve delta.",
        },
        {
            "drift_case_id": "GOVERNANCE_INVARIANT_DRIFT_BLOCKED",
            "drift_type": "GOVERNANCE_INVARIANT_DRIFT",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "source_packet_or_matrix": "governance_invariant_summary",
            "verdict": "CRITICAL_STOP",
            "blocked": True,
            "critical_stop": True,
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "affected_roles": ["cto_owner", "compliance_owner", "ceo_owner"],
            "affected_blocker_codes": ["GOVERNANCE_INVARIANT_DRIFT_BLOCKER"],
            "affected_unlock_flags": ["governance_invariant_unlock_risk"],
            "next_required_action": "Immediate stop and governance incident review.",
        },
        {
            "drift_case_id": "UNLOCK_PREVENTION_DRIFT_BLOCKED",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "source_packet_or_matrix": "unlock_prevention_matrix",
            "verdict": "CRITICAL_STOP",
            "blocked": True,
            "critical_stop": True,
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "affected_roles": ["security_owner", "cto_owner"],
            "affected_blocker_codes": ["UNLOCK_PREVENTION_DRIFT_BLOCKER"],
            "affected_unlock_flags": ["unlock_prevention_violation"],
            "next_required_action": "Immediate stop and security-compliance review.",
        },
        {
            "drift_case_id": "SIGNOFF_PACKET_COUNT_DRIFT_BLOCKED",
            "drift_type": "SIGNOFF_PACKET_COUNT_DRIFT",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "source_packet_or_matrix": "source_signoff_packet_count",
            "verdict": "BLOCKED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "affected_roles": ["engineering_owner"],
            "affected_blocker_codes": ["SIGNOFF_PACKET_COUNT_DRIFT_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Validate packet count drift against approved baseline.",
        },
        {
            "drift_case_id": "INVALID_PACKET_COUNT_DRIFT_BLOCKED",
            "drift_type": "INVALID_PACKET_COUNT_DRIFT",
            "alert_level": "ORANGE_SIGNOFF_BLOCKER_OR_EVIDENCE_MATRIX_DRIFT",
            "source_packet_or_matrix": "source_invalid_packet_count",
            "verdict": "BLOCKED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "affected_roles": ["engineering_owner"],
            "affected_blocker_codes": ["INVALID_PACKET_COUNT_DRIFT_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Validate invalid count drift against approved baseline.",
        },
        {
            "drift_case_id": "REPLAY_METADATA_DRIFT_REVIEW_REQUIRED",
            "drift_type": "REPLAY_METADATA_DRIFT",
            "alert_level": "YELLOW_SIGNOFF_METADATA_ONLY_DRIFT",
            "source_packet_or_matrix": "reproducibility_metadata",
            "verdict": "BLOCKED_REVIEW_REQUIRED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "affected_roles": ["engineering_owner", "compliance_owner"],
            "affected_blocker_codes": ["REPLAY_METADATA_DRIFT_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Review metadata drift and attach remediation evidence.",
        },
        {
            "drift_case_id": "DRIFT_DETAILS_MISSING_BLOCKED",
            "drift_type": "REPLAY_METADATA_DRIFT",
            "alert_level": "RED_SIGNOFF_VERDICT_OR_ESCALATION_COVERAGE_DRIFT",
            "source_packet_or_matrix": "drift_details",
            "verdict": "BLOCKED",
            "blocked": True,
            "critical_stop": False,
            "escalation_path": "engineering_review",
            "sla_class": "SLA_STANDARD_ENGINEERING_REVIEW",
            "affected_roles": ["engineering_owner", "legal_owner"],
            "affected_blocker_codes": ["DRIFT_DETAILS_REQUIRED_FIELDS_MISSING_BLOCKER"],
            "affected_unlock_flags": [],
            "next_required_action": "Provide complete drift details before re-run.",
        },
        {
            "drift_case_id": "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
            "drift_type": "GOVERNANCE_INVARIANT_DRIFT",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "source_packet_or_matrix": "provider_approved",
            "verdict": "CRITICAL_STOP",
            "blocked": True,
            "critical_stop": True,
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "affected_roles": ["legal_owner", "cto_owner", "ceo_owner"],
            "affected_blocker_codes": ["PROVIDER_APPROVAL_UNLOCK_DRIFT_BLOCKER"],
            "affected_unlock_flags": ["provider_unlock"],
            "next_required_action": "Immediate stop until legal provider evidence is verified.",
        },
        {
            "drift_case_id": "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
            "drift_type": "GOVERNANCE_INVARIANT_DRIFT",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "source_packet_or_matrix": "authorization_evidence_present",
            "verdict": "CRITICAL_STOP",
            "blocked": True,
            "critical_stop": True,
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "affected_roles": ["legal_owner", "compliance_owner", "ceo_owner"],
            "affected_blocker_codes": ["AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_BLOCKER"],
            "affected_unlock_flags": ["authorization_evidence_unlock"],
            "next_required_action": "Immediate stop and legal evidence verification.",
        },
        {
            "drift_case_id": "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "source_packet_or_matrix": "recommendation_allowed",
            "verdict": "CRITICAL_STOP",
            "blocked": True,
            "critical_stop": True,
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "affected_roles": ["cto_owner", "compliance_owner", "security_owner"],
            "affected_blocker_codes": ["RECOMMENDATION_UNLOCK_DRIFT_BLOCKER"],
            "affected_unlock_flags": ["recommendation_unlock"],
            "next_required_action": "Immediate stop and unlock-prevention remediation.",
        },
        {
            "drift_case_id": "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "source_packet_or_matrix": "production_ready",
            "verdict": "CRITICAL_STOP",
            "blocked": True,
            "critical_stop": True,
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "affected_roles": ["cto_owner", "ceo_owner", "security_owner"],
            "affected_blocker_codes": ["PRODUCTION_UNLOCK_DRIFT_BLOCKER"],
            "affected_unlock_flags": ["production_unlock"],
            "next_required_action": "Immediate stop and executive governance review.",
        },
        {
            "drift_case_id": "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "source_packet_or_matrix": "real_legal_odds_ingested",
            "verdict": "CRITICAL_STOP",
            "blocked": True,
            "critical_stop": True,
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "affected_roles": ["legal_owner", "data_rights_owner", "security_owner"],
            "affected_blocker_codes": ["REAL_ODDS_INGESTION_DRIFT_BLOCKER"],
            "affected_unlock_flags": ["odds_unlock"],
            "next_required_action": "Immediate stop and legal/provider data-rights review.",
        },
        {
            "drift_case_id": "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
            "drift_type": "UNLOCK_PREVENTION_DRIFT",
            "alert_level": "CRITICAL_SIGNOFF_UNLOCK_OR_PROVIDER_DRIFT",
            "source_packet_or_matrix": "live_api_calls_paid_api_called",
            "verdict": "CRITICAL_STOP",
            "blocked": True,
            "critical_stop": True,
            "escalation_path": "immediate_stop",
            "sla_class": "SLA_IMMEDIATE_STOP",
            "affected_roles": ["security_owner", "cto_owner", "data_rights_owner"],
            "affected_blocker_codes": ["LIVE_OR_PAID_API_DRIFT_BLOCKER"],
            "affected_unlock_flags": ["live_api_unlock", "paid_api_unlock"],
            "next_required_action": "Immediate stop and security incident review.",
        },
    ]


def summarize_packets(packets: list):
    alert_level = defaultdict(lambda: {"case_count": 0, "blocked_count": 0, "critical_stop_count": 0, "case_ids": []})
    drift_type = defaultdict(lambda: {"case_count": 0, "blocked_count": 0, "critical_stop_count": 0, "case_ids": []})
    escalation_path = defaultdict(lambda: {"case_count": 0, "blocked_count": 0, "critical_stop_count": 0, "case_ids": []})
    sla_class = defaultdict(lambda: {"case_count": 0, "blocked_count": 0, "critical_stop_count": 0, "case_ids": []})
    owner_counts = defaultdict(lambda: {"case_count": 0, "blocked_count": 0, "critical_stop_count": 0, "case_ids": []})

    for p in packets:
        cid = p["drift_case_id"]
        for bucket, key in (
            (alert_level, p["alert_level"]),
            (drift_type, p["drift_type"]),
            (escalation_path, p["escalation_path"]),
            (sla_class, p["sla_class"]),
        ):
            bucket[key]["case_count"] += 1
            bucket[key]["blocked_count"] += int(p["blocked"])
            bucket[key]["critical_stop_count"] += int(p["critical_stop"])
            bucket[key]["case_ids"].append(cid)

        for owner in p["required_signoff_owners"]:
            owner_counts[owner]["case_count"] += 1
            owner_counts[owner]["blocked_count"] += int(p["blocked"])
            owner_counts[owner]["critical_stop_count"] += int(p["critical_stop"])
            owner_counts[owner]["case_ids"].append(cid)

    def normalize(d):
        out = {}
        for k in sorted(d.keys()):
            out[k] = {
                "case_count": d[k]["case_count"],
                "blocked_count": d[k]["blocked_count"],
                "critical_stop_count": d[k]["critical_stop_count"],
                "case_ids": sorted(set(d[k]["case_ids"])),
            }
        return out

    return (
        normalize(alert_level),
        normalize(drift_type),
        normalize(escalation_path),
        normalize(sla_class),
        normalize(owner_counts),
    )


def empty_summary():
    return {
        "signoff_drift_alert_runner_status": "BLOCKED",
        "source_signoff_drift_alert_contract_status": "UNKNOWN",
        "source_signoff_replay_gate_status": "UNKNOWN",
        "source_replay_run_count": 0,
        "source_signoff_packet_count": 0,
        "source_invalid_packet_count": 0,
        "source_drift_detected": True,
        "evaluated_drift_event_count": 0,
        "alert_verdicts": {},
        "escalation_decision_packets": [],
        "alert_level_execution_matrix": {},
        "drift_type_execution_matrix": {},
        "escalation_path_execution_matrix": {},
        "sla_execution_matrix": {},
        "required_owner_execution_matrix": {},
        "blocked_action_matrix": {},
        "unlock_prevention_matrix": {},
        "no_drift_record_packet": {},
        "simulated_blocking_drift_cases": [],
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def main():
    missing = [p for p in (P121_PATH, P134_PATH, P135_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P136 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p134 = load_json(P134_PATH)
    p135 = load_json(P135_PATH)

    invariants = governance_invariants(p121)
    required_owner_matrix = p135.get("required_signoff_owner_matrix", {})
    cases = build_cases()
    packets = [packet(c, required_owner_matrix) for c in cases]

    alert_level_matrix, drift_type_matrix, escalation_path_matrix, sla_matrix, owner_matrix = summarize_packets(packets)

    alert_verdicts = {
        p["drift_case_id"]: {
            "verdict": p["verdict"],
            "blocked": p["blocked"],
            "critical_stop": p["critical_stop"],
            "alert_level": p["alert_level"],
            "drift_type": p["drift_type"],
            "escalation_path": p["escalation_path"],
            "sla_class": p["sla_class"],
        }
        for p in packets
    }

    blocked_action_matrix = {
        p["drift_case_id"]: {
            "provider_unlock_blocked": True,
            "odds_unlock_blocked": True,
            "recommendation_unlock_blocked": True,
            "production_unlock_blocked": True,
            "ev_clv_kelly_unlock_blocked": True,
            "live_paid_api_blocked": True,
            "blocked": p["blocked"],
            "critical_stop": p["critical_stop"],
        }
        for p in packets
    }

    unlock_prevention_matrix = {
        p["drift_case_id"]: {
            "provider_unlock_allowed": p["provider_unlock_allowed"],
            "odds_unlock_allowed": p["odds_unlock_allowed"],
            "recommendation_unlock_allowed": p["recommendation_unlock_allowed"],
            "production_unlock_allowed": p["production_unlock_allowed"],
            "ev_clv_kelly_unlock_allowed": p["ev_clv_kelly_unlock_allowed"],
        }
        for p in packets
    }

    no_drift_record_packet = next(p for p in packets if p["drift_case_id"] == "NO_SIGNOFF_DRIFT_RECORD_ONLY")
    simulated_blocking = sorted([p["drift_case_id"] for p in packets if p["drift_case_id"] != "NO_SIGNOFF_DRIFT_RECORD_ONLY"])

    invariant_fail = (
        invariants["paper_only"] is False
        or invariants["diagnostic_only"] is False
        or invariants["production_ready"] is True
        or invariants["real_bet_allowed"] is True
        or invariants["recommendation_allowed"] is True
        or invariants["provider_approved"] is True
        or invariants["authorization_evidence_present"] is True
        or invariants["placeholder_allowed_as_authorization"] is True
        or invariants["real_legal_odds_ingested"] is True
        or invariants["live_api_calls"] != 0
        or invariants["paid_api_called"] is True
        or invariants["ev_computed"] is True
        or invariants["clv_computed"] is True
        or invariants["kelly_computed"] is True
        or invariants["stake_sizing"] is True
        or invariants["profit_computed"] is True
        or invariants["recommendation_generated"] is True
    )

    blockers = sorted(set(p135.get("blockers", []) + [
        "SIGNOFF_DRIFT_ALERT_RUNNER_GOVERNANCE_ONLY_BLOCKER",
        "FULL_REGRESSION_NOT_RUN_BLOCKER",
    ]))

    final_classification = "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_READY_WITH_BLOCKERS"
    if invariant_fail:
        final_classification = "P136_SIGNOFF_DRIFT_ALERT_RUNNER_ESCALATION_DECISION_PACKET_FAILED_VALIDATION"

    summary = {
        "signoff_drift_alert_runner_status": "READY_WITH_BLOCKERS",
        "source_signoff_drift_alert_contract_status": p135.get("signoff_drift_alert_contract_status", "UNKNOWN"),
        "source_signoff_replay_gate_status": p134.get("signoff_replay_consistency_gate_status", "UNKNOWN"),
        "source_replay_run_count": p134.get("replay_run_count", 0),
        "source_signoff_packet_count": p134.get("source_signoff_packet_count", 0),
        "source_invalid_packet_count": p134.get("source_invalid_packet_count", 0),
        "source_drift_detected": bool(p134.get("drift_detected", True)),
        "evaluated_drift_event_count": len(packets),
        "alert_verdicts": alert_verdicts,
        "escalation_decision_packets": packets,
        "alert_level_execution_matrix": alert_level_matrix,
        "drift_type_execution_matrix": drift_type_matrix,
        "escalation_path_execution_matrix": escalation_path_matrix,
        "sla_execution_matrix": sla_matrix,
        "required_owner_execution_matrix": owner_matrix,
        "blocked_action_matrix": blocked_action_matrix,
        "unlock_prevention_matrix": unlock_prevention_matrix,
        "no_drift_record_packet": no_drift_record_packet,
        "simulated_blocking_drift_cases": simulated_blocking,
        "governance_invariant_summary": invariants,
        "governance_statement": "Sign-off drift alert routing does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "required_packet_fields": REQUIRED_PACKET_FIELDS,
        "regression_status": {
            "targeted_p118_p136_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P136 task.",
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
        f.write("# P136 Sign-off Drift Alert Runner + Escalation Decision Packet (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- signoff_drift_alert_runner_status: {summary['signoff_drift_alert_runner_status']}\n")
        f.write(f"- source_signoff_drift_alert_contract_status: {summary['source_signoff_drift_alert_contract_status']}\n")
        f.write(f"- source_signoff_replay_gate_status: {summary['source_signoff_replay_gate_status']}\n")
        f.write(f"- source_replay_run_count: {summary['source_replay_run_count']}\n")
        f.write(f"- source_signoff_packet_count: {summary['source_signoff_packet_count']}\n")
        f.write(f"- source_invalid_packet_count: {summary['source_invalid_packet_count']}\n")
        f.write(f"- source_drift_detected: {summary['source_drift_detected']}\n")
        f.write(f"- evaluated_drift_event_count: {summary['evaluated_drift_event_count']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Runner Cases\n")
        for p in packets:
            f.write(
                f"- {p['drift_case_id']}: {p['verdict']} "
                f"(level={p['alert_level']}, type={p['drift_type']}, "
                f"path={p['escalation_path']}, sla={p['sla_class']})\n"
            )
        f.write("\n")

        f.write("## Execution Matrices\n")
        f.write(f"- alert_level_execution_matrix: {summary['alert_level_execution_matrix']}\n")
        f.write(f"- drift_type_execution_matrix: {summary['drift_type_execution_matrix']}\n")
        f.write(f"- escalation_path_execution_matrix: {summary['escalation_path_execution_matrix']}\n")
        f.write(f"- sla_execution_matrix: {summary['sla_execution_matrix']}\n")
        f.write(f"- required_owner_execution_matrix: {summary['required_owner_execution_matrix']}\n")
        f.write(f"- blocked_action_matrix: {summary['blocked_action_matrix']}\n")
        f.write(f"- unlock_prevention_matrix: {summary['unlock_prevention_matrix']}\n")
        f.write(f"- no_drift_record_packet: {summary['no_drift_record_packet']}\n")
        f.write(f"- simulated_blocking_drift_cases: {summary['simulated_blocking_drift_cases']}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p136_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")

    print(f"P136 summary written to {OUT_PATH}")
    print(f"P136 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
