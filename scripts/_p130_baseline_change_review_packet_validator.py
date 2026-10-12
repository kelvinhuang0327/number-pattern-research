# P130 Baseline Change Review Packet Validator
# Paper-only validator for baseline change review packets defined by P129 contract.

import copy
import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P129_PATH = "data/mlb_2026/derived/p129_replay_drift_alert_contract_summary.json"
OUT_PATH = "data/mlb_2026/derived/p130_baseline_change_review_packet_validator_summary.json"
REPORT_PATH = "report/p130_baseline_change_review_packet_validator_20260601.md"

REQUIRED_PACKET_FIELDS = [
    "baseline_change_request_id",
    "baseline_change_owner",
    "baseline_change_reason",
    "source_fixture_version_before",
    "source_fixture_version_after",
    "old_fingerprint",
    "new_fingerprint",
    "rule_change_summary",
    "expected_verdict_delta",
    "reviewer_approval_status",
    "reviewer_identity",
    "approval_timestamp",
    "rollback_plan",
    "non_unlock_attestation",
    "production_unlock_requested",
    "recommendation_unlock_requested",
    "provider_unlock_requested",
    "real_odds_ingestion_requested",
    "live_or_paid_api_requested",
]

INVALID_CASES = [
    "MISSING_BASELINE_CHANGE_REQUEST_ID_BLOCKED",
    "MISSING_BASELINE_CHANGE_OWNER_BLOCKED",
    "MISSING_BASELINE_CHANGE_REASON_BLOCKED",
    "MISSING_SOURCE_FIXTURE_VERSION_BEFORE_BLOCKED",
    "MISSING_SOURCE_FIXTURE_VERSION_AFTER_BLOCKED",
    "MISSING_OLD_FINGERPRINT_BLOCKED",
    "MISSING_NEW_FINGERPRINT_BLOCKED",
    "MISSING_RULE_CHANGE_SUMMARY_BLOCKED",
    "MISSING_EXPECTED_VERDICT_DELTA_BLOCKED",
    "REVIEWER_APPROVAL_NOT_APPROVED_BLOCKED",
    "MISSING_REVIEWER_IDENTITY_BLOCKED",
    "MISSING_APPROVAL_TIMESTAMP_BLOCKED",
    "MISSING_ROLLBACK_PLAN_BLOCKED",
    "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED",
    "PRODUCTION_UNLOCK_REQUESTED_BLOCKED",
    "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED",
    "PROVIDER_UNLOCK_REQUESTED_BLOCKED",
    "REAL_ODDS_INGESTION_REQUESTED_BLOCKED",
    "LIVE_OR_PAID_API_REQUESTED_BLOCKED",
    "SAME_OLD_AND_NEW_FINGERPRINT_BLOCKED",
    "EMPTY_RULE_CHANGE_WITH_FINGERPRINT_CHANGE_BLOCKED",
]

MISSING_FIELD_BLOCKERS = {
    "baseline_change_request_id": "BASELINE_CHANGE_REQUEST_ID_MISSING_BLOCKER",
    "baseline_change_owner": "BASELINE_CHANGE_OWNER_MISSING_BLOCKER",
    "baseline_change_reason": "BASELINE_CHANGE_REASON_MISSING_BLOCKER",
    "source_fixture_version_before": "SOURCE_FIXTURE_VERSION_BEFORE_MISSING_BLOCKER",
    "source_fixture_version_after": "SOURCE_FIXTURE_VERSION_AFTER_MISSING_BLOCKER",
    "old_fingerprint": "OLD_FINGERPRINT_MISSING_BLOCKER",
    "new_fingerprint": "NEW_FINGERPRINT_MISSING_BLOCKER",
    "rule_change_summary": "RULE_CHANGE_SUMMARY_MISSING_BLOCKER",
    "expected_verdict_delta": "EXPECTED_VERDICT_DELTA_MISSING_BLOCKER",
    "reviewer_identity": "REVIEWER_IDENTITY_MISSING_BLOCKER",
    "approval_timestamp": "APPROVAL_TIMESTAMP_MISSING_BLOCKER",
    "rollback_plan": "ROLLBACK_PLAN_MISSING_BLOCKER",
    "non_unlock_attestation": "NON_UNLOCK_ATTESTATION_MISSING_BLOCKER",
}

UNAUTHORIZED_CHANGE_BLOCKERS = {
    "production_unlock_requested": "PRODUCTION_UNLOCK_REQUESTED_BLOCKER",
    "recommendation_unlock_requested": "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKER",
    "provider_unlock_requested": "PROVIDER_UNLOCK_REQUESTED_BLOCKER",
    "real_odds_ingestion_requested": "REAL_ODDS_INGESTION_REQUESTED_BLOCKER",
    "live_or_paid_api_requested": "LIVE_OR_PAID_API_REQUESTED_BLOCKER",
}

PACKET_VALIDATION_RULES = {
    "R001_REQUIRED_FIELDS": "All required packet fields must be present and non-empty",
    "R002_REVIEWER_APPROVAL": "reviewer_approval_status must equal APPROVED",
    "R003_UNLOCK_FLAGS_FORBIDDEN": "All unlock request flags must be false",
    "R004_FINGERPRINT_CHANGE_VALIDITY": "old_fingerprint and new_fingerprint cannot be identical",
    "R005_RULE_CHANGE_SUMMARY_REQUIRED": "Fingerprint change must include non-empty rule_change_summary",
    "R006_ROLLBACK_PLAN_REQUIRED": "rollback_plan must be present",
    "R007_NON_UNLOCK_ATTESTATION_REQUIRED": "non_unlock_attestation must explicitly deny provider/odds/recommendation/production unlock",
    "R008_GOVERNANCE_ONLY": "Baseline change approval does not imply legal provider approval or production readiness",
}

BASELINE_FINGERPRINT_CHANGE_RULES = {
    "rule": "Fingerprint changes are governance-only and require approved review packet",
    "required_fields": ["old_fingerprint", "new_fingerprint", "rule_change_summary", "expected_verdict_delta"],
    "blocked_if": [
        "old_fingerprint == new_fingerprint",
        "rule_change_summary is empty",
        "reviewer_approval_status != APPROVED",
    ],
}

FIXTURE_VERSION_CHANGE_RULES = {
    "rule": "Fixture version transitions must be explicitly declared before and after",
    "required_fields": ["source_fixture_version_before", "source_fixture_version_after"],
    "blocked_if": ["source_fixture_version_before missing", "source_fixture_version_after missing"],
}

RULE_CHANGE_SUMMARY_RULES = {
    "rule": "Rule change summary must explain baseline delta scope",
    "required_fields": ["rule_change_summary"],
    "blocked_if": ["rule_change_summary empty while fingerprint changed"],
}

EXPECTED_VERDICT_DELTA_RULES = {
    "rule": "Expected verdict delta must be declared and remain governance-only",
    "required_fields": ["expected_verdict_delta"],
    "blocked_if": ["expected_verdict_delta missing"],
}

REVIEWER_APPROVAL_RULES = {
    "rule": "Reviewer approval identity and timestamp are mandatory",
    "required_fields": ["reviewer_approval_status", "reviewer_identity", "approval_timestamp"],
    "blocked_if": ["reviewer_approval_status != APPROVED", "reviewer_identity missing", "approval_timestamp missing"],
}

ROLLBACK_PLAN_RULES = {
    "rule": "Rollback plan is required before accepting any baseline change",
    "required_fields": ["rollback_plan"],
    "blocked_if": ["rollback_plan missing"],
}

NON_UNLOCK_ATTESTATION_RULES = {
    "rule": "Packet must explicitly attest no provider/odds/recommendation/production unlock",
    "required_fields": ["non_unlock_attestation"],
    "required_statement": "Baseline change approval does not imply legal provider approval or production readiness.",
    "blocked_if": ["non_unlock_attestation missing or contradicts governance-only policy"],
}

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use packet validator outputs for governance review only",
    "Require approved review packet before baseline updates",
    "Keep full regression state explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat baseline packet approval as legal provider approval",
    "Do not bypass rollback plan and non-unlock attestation requirements",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_READY_WITH_BLOCKERS",
    "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_BLOCKED_BY_MISSING_ARTIFACTS",
    "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_valid_packet_template():
    return {
        "baseline_change_request_id": "BCR-20260601-001",
        "baseline_change_owner": "governance_owner_placeholder",
        "baseline_change_reason": "Replay baseline metadata alignment under paper-only governance.",
        "source_fixture_version_before": "P128.20260601",
        "source_fixture_version_after": "P128.20260601A",
        "old_fingerprint": "1111111111111111111111111111111111111111111111111111111111111111",
        "new_fingerprint": "2222222222222222222222222222222222222222222222222222222222222222",
        "rule_change_summary": "No unlock logic changes; governance metadata alignment only.",
        "expected_verdict_delta": "No verdict delta expected; all tracked cases remain BLOCKED.",
        "reviewer_approval_status": "APPROVED",
        "reviewer_identity": "reviewer_placeholder",
        "approval_timestamp": "2026-06-01T00:00:00Z",
        "rollback_plan": "Restore previous baseline fingerprint and revert governance packet if drift appears.",
        "non_unlock_attestation": "Baseline change approval does not imply legal provider approval or production readiness.",
        "production_unlock_requested": False,
        "recommendation_unlock_requested": False,
        "provider_unlock_requested": False,
        "real_odds_ingestion_requested": False,
        "live_or_paid_api_requested": False,
    }


def validate_packet(packet: dict):
    blockers = []

    for field in REQUIRED_PACKET_FIELDS:
        if field not in packet or packet[field] in (None, ""):
            if field in MISSING_FIELD_BLOCKERS:
                blockers.append(MISSING_FIELD_BLOCKERS[field])
            else:
                blockers.append(f"{field.upper()}_MISSING_BLOCKER")

    if packet.get("reviewer_approval_status") != "APPROVED":
        blockers.append("REVIEWER_APPROVAL_NOT_APPROVED_BLOCKER")

    for key, blocker in UNAUTHORIZED_CHANGE_BLOCKERS.items():
        if bool(packet.get(key, False)):
            blockers.append(blocker)

    if packet.get("old_fingerprint") and packet.get("new_fingerprint"):
        if packet.get("old_fingerprint") == packet.get("new_fingerprint"):
            blockers.append("OLD_AND_NEW_FINGERPRINT_IDENTICAL_BLOCKER")

    if packet.get("old_fingerprint") and packet.get("new_fingerprint"):
        if packet.get("old_fingerprint") != packet.get("new_fingerprint") and not packet.get("rule_change_summary"):
            blockers.append("RULE_CHANGE_SUMMARY_EMPTY_WITH_FINGERPRINT_CHANGE_BLOCKER")

    non_unlock_attestation = str(packet.get("non_unlock_attestation", ""))
    if non_unlock_attestation:
        if "does not imply legal provider approval or production readiness" not in non_unlock_attestation:
            blockers.append("NON_UNLOCK_ATTESTATION_INVALID_BLOCKER")

    status = "BLOCKED" if blockers else "SCHEMA_VALID_PENDING_REVIEW"
    return status, sorted(set(blockers))


def build_invalid_case_packet(case_id: str, valid_packet: dict):
    packet = copy.deepcopy(valid_packet)

    if case_id == "MISSING_BASELINE_CHANGE_REQUEST_ID_BLOCKED":
        packet.pop("baseline_change_request_id", None)
    elif case_id == "MISSING_BASELINE_CHANGE_OWNER_BLOCKED":
        packet.pop("baseline_change_owner", None)
    elif case_id == "MISSING_BASELINE_CHANGE_REASON_BLOCKED":
        packet.pop("baseline_change_reason", None)
    elif case_id == "MISSING_SOURCE_FIXTURE_VERSION_BEFORE_BLOCKED":
        packet.pop("source_fixture_version_before", None)
    elif case_id == "MISSING_SOURCE_FIXTURE_VERSION_AFTER_BLOCKED":
        packet.pop("source_fixture_version_after", None)
    elif case_id == "MISSING_OLD_FINGERPRINT_BLOCKED":
        packet.pop("old_fingerprint", None)
    elif case_id == "MISSING_NEW_FINGERPRINT_BLOCKED":
        packet.pop("new_fingerprint", None)
    elif case_id == "MISSING_RULE_CHANGE_SUMMARY_BLOCKED":
        packet.pop("rule_change_summary", None)
    elif case_id == "MISSING_EXPECTED_VERDICT_DELTA_BLOCKED":
        packet.pop("expected_verdict_delta", None)
    elif case_id == "REVIEWER_APPROVAL_NOT_APPROVED_BLOCKED":
        packet["reviewer_approval_status"] = "PENDING"
    elif case_id == "MISSING_REVIEWER_IDENTITY_BLOCKED":
        packet.pop("reviewer_identity", None)
    elif case_id == "MISSING_APPROVAL_TIMESTAMP_BLOCKED":
        packet.pop("approval_timestamp", None)
    elif case_id == "MISSING_ROLLBACK_PLAN_BLOCKED":
        packet.pop("rollback_plan", None)
    elif case_id == "MISSING_NON_UNLOCK_ATTESTATION_BLOCKED":
        packet.pop("non_unlock_attestation", None)
    elif case_id == "PRODUCTION_UNLOCK_REQUESTED_BLOCKED":
        packet["production_unlock_requested"] = True
    elif case_id == "RECOMMENDATION_UNLOCK_REQUESTED_BLOCKED":
        packet["recommendation_unlock_requested"] = True
    elif case_id == "PROVIDER_UNLOCK_REQUESTED_BLOCKED":
        packet["provider_unlock_requested"] = True
    elif case_id == "REAL_ODDS_INGESTION_REQUESTED_BLOCKED":
        packet["real_odds_ingestion_requested"] = True
    elif case_id == "LIVE_OR_PAID_API_REQUESTED_BLOCKED":
        packet["live_or_paid_api_requested"] = True
    elif case_id == "SAME_OLD_AND_NEW_FINGERPRINT_BLOCKED":
        packet["new_fingerprint"] = packet["old_fingerprint"]
    elif case_id == "EMPTY_RULE_CHANGE_WITH_FINGERPRINT_CHANGE_BLOCKED":
        packet["rule_change_summary"] = ""

    return packet


def get_governance_invariants(p121: dict):
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


def main():
    missing = []
    for path in (P121_PATH, P129_PATH):
        if not Path(path).exists():
            missing.append(path)

    if missing:
        out = {
            "baseline_change_review_validator_status": "BLOCKED",
            "source_replay_drift_alert_contract_status": "UNKNOWN",
            "required_packet_fields": REQUIRED_PACKET_FIELDS,
            "valid_packet_template": {},
            "invalid_packet_cases": [],
            "packet_validation_rules": PACKET_VALIDATION_RULES,
            "packet_verdict_matrix": {},
            "missing_field_blockers": MISSING_FIELD_BLOCKERS,
            "unauthorized_change_blockers": UNAUTHORIZED_CHANGE_BLOCKERS,
            "baseline_fingerprint_change_rules": BASELINE_FINGERPRINT_CHANGE_RULES,
            "fixture_version_change_rules": FIXTURE_VERSION_CHANGE_RULES,
            "rule_change_summary_rules": RULE_CHANGE_SUMMARY_RULES,
            "expected_verdict_delta_rules": EXPECTED_VERDICT_DELTA_RULES,
            "reviewer_approval_rules": REVIEWER_APPROVAL_RULES,
            "rollback_plan_rules": ROLLBACK_PLAN_RULES,
            "non_unlock_attestation_rules": NON_UNLOCK_ATTESTATION_RULES,
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "prohibited_actions": PROHIBITED_ACTIONS,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "final_classification": "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_BLOCKED_BY_MISSING_ARTIFACTS",
            "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"P130 validator summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p129 = load_json(P129_PATH)

    valid_packet_template = build_valid_packet_template()
    valid_status, valid_blockers = validate_packet(valid_packet_template)

    invalid_packet_cases = []
    packet_verdict_matrix = {
        "VALID_PACKET_TEMPLATE": {
            "status": valid_status,
            "blockers": valid_blockers,
            "notes": "Schema-valid governance packet. Baseline change remains governance-only pending process controls.",
        }
    }

    for case_id in INVALID_CASES:
        packet = build_invalid_case_packet(case_id, valid_packet_template)
        status, blockers = validate_packet(packet)
        if status != "BLOCKED":
            status = "BLOCKED"
            blockers = sorted(set(blockers + ["INVALID_CASE_NOT_BLOCKED_GUARDRAIL_BLOCKER"]))

        invalid_packet_cases.append({
            "case_id": case_id,
            "packet": packet,
            "status": status,
            "blockers": blockers,
        })
        packet_verdict_matrix[case_id] = {
            "status": status,
            "blockers": blockers,
        }

    governance_invariants = get_governance_invariants(p121)
    governance_fail = (
        governance_invariants["paper_only"] is False
        or governance_invariants["diagnostic_only"] is False
        or governance_invariants["production_ready"] is True
        or governance_invariants["real_bet_allowed"] is True
        or governance_invariants["recommendation_allowed"] is True
        or governance_invariants["provider_approved"] is True
        or governance_invariants["authorization_evidence_present"] is True
        or governance_invariants["placeholder_allowed_as_authorization"] is True
        or governance_invariants["real_legal_odds_ingested"] is True
        or governance_invariants["live_api_calls"] != 0
        or governance_invariants["paid_api_called"] is True
        or governance_invariants["ev_computed"] is True
        or governance_invariants["clv_computed"] is True
        or governance_invariants["kelly_computed"] is True
        or governance_invariants["stake_sizing"] is True
        or governance_invariants["profit_computed"] is True
        or governance_invariants["recommendation_generated"] is True
    )

    blockers = sorted(set(p129.get("blockers", [])))
    blockers.append("BASELINE_PACKET_REVIEW_REQUIRED_BLOCKER")
    blockers.append("FULL_REGRESSION_NOT_RUN_BLOCKER")
    blockers = sorted(set(blockers))

    final_classification = "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_READY_WITH_BLOCKERS"
    if governance_fail:
        final_classification = "P130_BASELINE_CHANGE_REVIEW_PACKET_VALIDATOR_FAILED_VALIDATION"

    summary = {
        "baseline_change_review_validator_status": "READY_WITH_BLOCKERS",
        "source_replay_drift_alert_contract_status": p129.get("replay_drift_alert_contract_status", "UNKNOWN"),
        "required_packet_fields": REQUIRED_PACKET_FIELDS,
        "valid_packet_template": valid_packet_template,
        "invalid_packet_cases": invalid_packet_cases,
        "packet_validation_rules": PACKET_VALIDATION_RULES,
        "packet_verdict_matrix": packet_verdict_matrix,
        "missing_field_blockers": MISSING_FIELD_BLOCKERS,
        "unauthorized_change_blockers": UNAUTHORIZED_CHANGE_BLOCKERS,
        "baseline_fingerprint_change_rules": BASELINE_FINGERPRINT_CHANGE_RULES,
        "fixture_version_change_rules": FIXTURE_VERSION_CHANGE_RULES,
        "rule_change_summary_rules": RULE_CHANGE_SUMMARY_RULES,
        "expected_verdict_delta_rules": EXPECTED_VERDICT_DELTA_RULES,
        "reviewer_approval_rules": REVIEWER_APPROVAL_RULES,
        "rollback_plan_rules": ROLLBACK_PLAN_RULES,
        "non_unlock_attestation_rules": NON_UNLOCK_ATTESTATION_RULES,
        "governance_invariants": governance_invariants,
        "regression_status": {
            "targeted_p118_p130_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P130 task.",
        },
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": blockers,
        "final_classification": final_classification,
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        "governance_statement": "Baseline change approval does not imply legal provider approval or production readiness.",
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P130 Baseline Change Review Packet Validator (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- baseline_change_review_validator_status: {summary['baseline_change_review_validator_status']}\n")
        f.write(f"- source_replay_drift_alert_contract_status: {summary['source_replay_drift_alert_contract_status']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Packet Field Requirements\n")
        for field in summary["required_packet_fields"]:
            f.write(f"- {field}\n")
        f.write("\n")

        f.write("## Validation Verdicts\n")
        for key, value in summary["packet_verdict_matrix"].items():
            blockers_text = ", ".join(value.get("blockers", []))
            f.write(f"- {key}: {value['status']} | blockers={blockers_text}\n")
        f.write("\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariants"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p130_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Blockers\n")
        for b in summary["blockers"]:
            f.write(f"- {b}\n")
        f.write("\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")
        f.write("\n")

        f.write("## Allowed Next Actions\n")
        for item in summary["allowed_next_actions"]:
            f.write(f"- {item}\n")

    print(f"P130 validator summary written to {OUT_PATH}")
    print(f"P130 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
