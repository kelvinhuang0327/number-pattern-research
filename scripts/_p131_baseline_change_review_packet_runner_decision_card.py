# P131 Baseline Change Review Packet Runner + Decision Card
# Paper-only runner that executes P130 packet cases and emits standardized decision cards.

import json
from collections import Counter
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P130_PATH = "data/mlb_2026/derived/p130_baseline_change_review_packet_validator_summary.json"
OUT_PATH = "data/mlb_2026/derived/p131_baseline_change_review_packet_runner_decision_card_summary.json"
REPORT_PATH = "report/p131_baseline_change_review_packet_runner_decision_card_20260601.md"

DECISION_CARD_SCHEMA = {
    "packet_id": "string",
    "packet_name": "string",
    "packet_type": "VALID_TEMPLATE | INVALID_CASE",
    "verdict": "GOVERNANCE_ONLY_PENDING | BLOCKED",
    "decision_level": "YELLOW_GOVERNANCE_ONLY | RED_BLOCKED",
    "blocker_count": "integer",
    "blocker_codes": "string[]",
    "missing_required_fields": "string[]",
    "unauthorized_change_flags": "string[]",
    "reviewer_approval_status": "APPROVED | NOT_APPROVED | MISSING",
    "reviewer_identity_status": "PRESENT | MISSING",
    "approval_timestamp_status": "PRESENT | MISSING",
    "rollback_plan_status": "PRESENT | MISSING",
    "non_unlock_attestation_status": "VALID | MISSING | INVALID",
    "baseline_fingerprint_change_status": "CHANGED | UNCHANGED | MISSING",
    "expected_verdict_delta_status": "PRESENT | MISSING",
    "provider_unlock_allowed": "boolean",
    "odds_unlock_allowed": "boolean",
    "recommendation_unlock_allowed": "boolean",
    "production_unlock_allowed": "boolean",
    "ev_clv_kelly_unlock_allowed": "boolean",
    "decision_reason": "string",
    "next_required_action": "string",
}

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use decision cards for governance review workflow only",
    "Require reviewer approval, rollback plan, and valid non-unlock attestation before baseline change",
    "Keep full regression status explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat packet review as legal provider approval or production readiness",
    "Do not bypass blocker resolution before any baseline change",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_READY_WITH_BLOCKERS",
    "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_BLOCKED_BY_MISSING_ARTIFACTS",
    "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_missing_required_fields(packet: dict, required_fields: list):
    missing = []
    for field in required_fields:
        if field not in packet or packet[field] in (None, ""):
            missing.append(field)
    return sorted(missing)


def extract_unauthorized_flags(packet: dict):
    flags = []
    if bool(packet.get("production_unlock_requested", False)):
        flags.append("production_unlock_requested")
    if bool(packet.get("recommendation_unlock_requested", False)):
        flags.append("recommendation_unlock_requested")
    if bool(packet.get("provider_unlock_requested", False)):
        flags.append("provider_unlock_requested")
    if bool(packet.get("real_odds_ingestion_requested", False)):
        flags.append("real_odds_ingestion_requested")
    if bool(packet.get("live_or_paid_api_requested", False)):
        flags.append("live_or_paid_api_requested")
    return sorted(flags)


def build_decision_card(packet_id: str, packet_name: str, packet_type: str, packet: dict, verdict: str, blockers: list, required_fields: list):
    missing_required_fields = extract_missing_required_fields(packet, required_fields)
    unauthorized_change_flags = extract_unauthorized_flags(packet)

    reviewer_status_raw = packet.get("reviewer_approval_status")
    if reviewer_status_raw == "APPROVED":
        reviewer_approval_status = "APPROVED"
    elif reviewer_status_raw in (None, ""):
        reviewer_approval_status = "MISSING"
    else:
        reviewer_approval_status = "NOT_APPROVED"

    reviewer_identity_status = "PRESENT" if packet.get("reviewer_identity") else "MISSING"
    approval_timestamp_status = "PRESENT" if packet.get("approval_timestamp") else "MISSING"
    rollback_plan_status = "PRESENT" if packet.get("rollback_plan") else "MISSING"

    attestation = str(packet.get("non_unlock_attestation", ""))
    required_attestation = "does not imply legal provider approval or production readiness"
    if not attestation:
        non_unlock_attestation_status = "MISSING"
    elif required_attestation in attestation:
        non_unlock_attestation_status = "VALID"
    else:
        non_unlock_attestation_status = "INVALID"

    old_fp = packet.get("old_fingerprint")
    new_fp = packet.get("new_fingerprint")
    if not old_fp or not new_fp:
        baseline_fingerprint_change_status = "MISSING"
    elif old_fp == new_fp:
        baseline_fingerprint_change_status = "UNCHANGED"
    else:
        baseline_fingerprint_change_status = "CHANGED"

    expected_verdict_delta_status = "PRESENT" if packet.get("expected_verdict_delta") else "MISSING"

    decision_level = "RED_BLOCKED" if verdict == "BLOCKED" else "YELLOW_GOVERNANCE_ONLY"

    decision_reason = "Packet blocked due to missing/unauthorized/governance violations."
    next_required_action = "Resolve blockers and resubmit packet for governance review."
    if verdict != "BLOCKED":
        decision_reason = "Schema-valid governance packet, still not production-ready by policy."
        next_required_action = "Maintain governance-only flow; no unlock actions permitted."

    return {
        "packet_id": packet_id,
        "packet_name": packet_name,
        "packet_type": packet_type,
        "verdict": verdict,
        "decision_level": decision_level,
        "blocker_count": len(blockers),
        "blocker_codes": sorted(blockers),
        "missing_required_fields": missing_required_fields,
        "unauthorized_change_flags": unauthorized_change_flags,
        "reviewer_approval_status": reviewer_approval_status,
        "reviewer_identity_status": reviewer_identity_status,
        "approval_timestamp_status": approval_timestamp_status,
        "rollback_plan_status": rollback_plan_status,
        "non_unlock_attestation_status": non_unlock_attestation_status,
        "baseline_fingerprint_change_status": baseline_fingerprint_change_status,
        "expected_verdict_delta_status": expected_verdict_delta_status,
        "provider_unlock_allowed": False,
        "odds_unlock_allowed": False,
        "recommendation_unlock_allowed": False,
        "production_unlock_allowed": False,
        "ev_clv_kelly_unlock_allowed": False,
        "decision_reason": decision_reason,
        "next_required_action": next_required_action,
    }


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
    for path in (P121_PATH, P130_PATH):
        if not Path(path).exists():
            missing.append(path)

    if missing:
        out = {
            "packet_runner_status": "BLOCKED",
            "source_baseline_change_validator_status": "UNKNOWN",
            "evaluated_packet_count": 0,
            "approved_packet_count": 0,
            "blocked_packet_count": 0,
            "unexpected_approved_count": 0,
            "decision_cards": [],
            "decision_card_schema": DECISION_CARD_SCHEMA,
            "packet_execution_matrix": {},
            "packet_blocker_summary": {},
            "reviewer_status_summary": {},
            "rollback_readiness_summary": {},
            "non_unlock_attestation_summary": {},
            "governance_invariant_summary": {},
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "prohibited_actions": PROHIBITED_ACTIONS,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "final_classification": "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_BLOCKED_BY_MISSING_ARTIFACTS",
            "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"P131 runner summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p130 = load_json(P130_PATH)

    required_fields = p130.get("required_packet_fields", [])
    decision_cards = []
    packet_execution_matrix = {}

    valid_packet = p130.get("valid_packet_template", {})
    valid_verdict_meta = p130.get("packet_verdict_matrix", {}).get("VALID_PACKET_TEMPLATE", {})
    valid_verdict = valid_verdict_meta.get("status", "SCHEMA_VALID_PENDING_REVIEW")
    valid_blockers = valid_verdict_meta.get("blockers", [])

    valid_card = build_decision_card(
        packet_id="P130_VALID_TEMPLATE",
        packet_name="VALID_PACKET_TEMPLATE",
        packet_type="VALID_TEMPLATE",
        packet=valid_packet,
        verdict="GOVERNANCE_ONLY_PENDING" if valid_verdict != "BLOCKED" else "BLOCKED",
        blockers=valid_blockers,
        required_fields=required_fields,
    )
    decision_cards.append(valid_card)
    packet_execution_matrix[valid_card["packet_name"]] = {
        "verdict": valid_card["verdict"],
        "decision_level": valid_card["decision_level"],
        "blocker_codes": valid_card["blocker_codes"],
    }

    for row in p130.get("invalid_packet_cases", []):
        case_id = row.get("case_id", "UNKNOWN_CASE")
        packet = row.get("packet", {})
        blockers = row.get("blockers", [])
        card = build_decision_card(
            packet_id=f"P130_INVALID_{case_id}",
            packet_name=case_id,
            packet_type="INVALID_CASE",
            packet=packet,
            verdict="BLOCKED",
            blockers=blockers,
            required_fields=required_fields,
        )
        decision_cards.append(card)
        packet_execution_matrix[card["packet_name"]] = {
            "verdict": card["verdict"],
            "decision_level": card["decision_level"],
            "blocker_codes": card["blocker_codes"],
        }

    evaluated_packet_count = len(decision_cards)
    approved_packet_count = len([c for c in decision_cards if c["verdict"] == "APPROVED"])
    blocked_packet_count = len([c for c in decision_cards if c["verdict"] == "BLOCKED"])
    unexpected_approved_count = approved_packet_count

    blocker_counter = Counter()
    for c in decision_cards:
        for b in c["blocker_codes"]:
            blocker_counter[b] += 1

    reviewer_status_counter = Counter([c["reviewer_approval_status"] for c in decision_cards])
    rollback_status_counter = Counter([c["rollback_plan_status"] for c in decision_cards])
    attestation_status_counter = Counter([c["non_unlock_attestation_status"] for c in decision_cards])

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

    blockers = sorted(set(p130.get("blockers", [])))
    blockers.append("DECISION_CARD_GOVERNANCE_ONLY_BLOCKER")
    blockers.append("FULL_REGRESSION_NOT_RUN_BLOCKER")
    blockers = sorted(set(blockers))

    final_classification = "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_READY_WITH_BLOCKERS"
    if governance_fail:
        final_classification = "P131_BASELINE_CHANGE_REVIEW_PACKET_RUNNER_DECISION_CARD_FAILED_VALIDATION"

    summary = {
        "packet_runner_status": "READY_WITH_BLOCKERS",
        "source_baseline_change_validator_status": p130.get("baseline_change_review_validator_status", "UNKNOWN"),
        "evaluated_packet_count": evaluated_packet_count,
        "approved_packet_count": approved_packet_count,
        "blocked_packet_count": blocked_packet_count,
        "unexpected_approved_count": unexpected_approved_count,
        "decision_cards": decision_cards,
        "decision_card_schema": DECISION_CARD_SCHEMA,
        "packet_execution_matrix": packet_execution_matrix,
        "packet_blocker_summary": {k: blocker_counter[k] for k in sorted(blocker_counter.keys())},
        "reviewer_status_summary": {k: reviewer_status_counter[k] for k in sorted(reviewer_status_counter.keys())},
        "rollback_readiness_summary": {k: rollback_status_counter[k] for k in sorted(rollback_status_counter.keys())},
        "non_unlock_attestation_summary": {k: attestation_status_counter[k] for k in sorted(attestation_status_counter.keys())},
        "governance_invariant_summary": governance_invariants,
        "regression_status": {
            "targeted_p118_p131_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P131 task.",
        },
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": blockers,
        "final_classification": final_classification,
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        "governance_statement": "Baseline change approval does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P131 Baseline Change Review Packet Runner + Decision Card (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- packet_runner_status: {summary['packet_runner_status']}\n")
        f.write(f"- source_baseline_change_validator_status: {summary['source_baseline_change_validator_status']}\n")
        f.write(f"- evaluated_packet_count: {summary['evaluated_packet_count']}\n")
        f.write(f"- approved_packet_count: {summary['approved_packet_count']}\n")
        f.write(f"- blocked_packet_count: {summary['blocked_packet_count']}\n")
        f.write(f"- unexpected_approved_count: {summary['unexpected_approved_count']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Decision Cards\n")
        for c in summary["decision_cards"]:
            f.write(
                f"- {c['packet_name']}: verdict={c['verdict']} level={c['decision_level']} blockers={','.join(c['blocker_codes'])}\n"
            )
        f.write("\n")

        f.write("## Reviewer/Rollback/Attestation Summary\n")
        f.write(f"- reviewer_status_summary: {summary['reviewer_status_summary']}\n")
        f.write(f"- rollback_readiness_summary: {summary['rollback_readiness_summary']}\n")
        f.write(f"- non_unlock_attestation_summary: {summary['non_unlock_attestation_summary']}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p131_tests_status: NOT_RUN\n")
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

    print(f"P131 runner summary written to {OUT_PATH}")
    print(f"P131 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
