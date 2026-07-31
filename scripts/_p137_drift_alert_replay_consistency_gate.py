# P137 Drift Alert Replay Consistency Gate
# Deterministic paper-only replay consistency gate for P136 drift alert runner outputs.

import hashlib
import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P136_PATH = "data/mlb_2026/derived/p136_signoff_drift_alert_runner_escalation_decision_packet_summary.json"
OUT_PATH = "data/mlb_2026/derived/p137_drift_alert_replay_consistency_gate_summary.json"
REPORT_PATH = "report/p137_drift_alert_replay_consistency_gate_20260601.md"

REPLAY_RUN_COUNT = 3

FINAL_CLASSIFICATION_OPTIONS = [
    "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS",
    "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION",
]

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use replay consistency output for governance diagnostics only",
    "Require baseline review before accepting drift contract or runner changes",
    "Keep full regression state explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat replay consistency as legal provider approval or production readiness",
    "Do not bypass blocker resolution and required owner routing",
]

DANGEROUS_CASE_IDS = {
    "FINGERPRINT_DRIFT_BLOCKED",
    "SIGNOFF_VERDICT_MATRIX_DRIFT_BLOCKED",
    "BLOCKER_CLASSIFICATION_DRIFT_BLOCKED",
    "REQUIRED_EVIDENCE_MATRIX_DRIFT_BLOCKED",
    "ESCALATION_LEVEL_COVERAGE_DRIFT_BLOCKED",
    "GOVERNANCE_INVARIANT_DRIFT_BLOCKED",
    "UNLOCK_PREVENTION_DRIFT_BLOCKED",
    "SIGNOFF_PACKET_COUNT_DRIFT_BLOCKED",
    "INVALID_PACKET_COUNT_DRIFT_BLOCKED",
    "REPLAY_METADATA_DRIFT_REVIEW_REQUIRED",
    "DRIFT_DETAILS_MISSING_BLOCKED",
    "PROVIDER_APPROVAL_UNLOCK_DRIFT_CRITICAL_STOP",
    "AUTHORIZATION_EVIDENCE_UNLOCK_DRIFT_CRITICAL_STOP",
    "RECOMMENDATION_UNLOCK_DRIFT_CRITICAL_STOP",
    "PRODUCTION_UNLOCK_DRIFT_CRITICAL_STOP",
    "REAL_ODDS_INGESTION_DRIFT_CRITICAL_STOP",
    "LIVE_OR_PAID_API_DRIFT_CRITICAL_STOP",
}


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def canonical_hash(payload: dict) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def replay_payload(source: dict) -> dict:
    return {
        "evaluated_drift_event_count": source.get("evaluated_drift_event_count", 0),
        "alert_verdicts": source.get("alert_verdicts", []),
        "escalation_decision_packets": source.get("escalation_decision_packets", []),
        "alert_level_execution_matrix": source.get("alert_level_execution_matrix", {}),
        "drift_type_execution_matrix": source.get("drift_type_execution_matrix", {}),
        "escalation_path_execution_matrix": source.get("escalation_path_execution_matrix", {}),
        "sla_execution_matrix": source.get("sla_execution_matrix", {}),
        "required_owner_execution_matrix": source.get("required_owner_execution_matrix", {}),
        "blocked_action_matrix": source.get("blocked_action_matrix", {}),
        "unlock_prevention_matrix": source.get("unlock_prevention_matrix", {}),
        "no_drift_record_packet": source.get("no_drift_record_packet", {}),
        "simulated_blocking_drift_cases": source.get("simulated_blocking_drift_cases", []),
        "final_classification": source.get("final_classification", ""),
    }


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


def empty_summary():
    return {
        "drift_alert_replay_consistency_gate_status": "BLOCKED",
        "source_signoff_drift_alert_runner_status": "UNKNOWN",
        "source_evaluated_drift_event_count": 0,
        "source_replay_run_count": 0,
        "source_signoff_packet_count": 0,
        "source_invalid_packet_count": 0,
        "replay_run_count": 0,
        "baseline_fingerprint": "",
        "replay_fingerprints": {},
        "fingerprint_consistency_status": "INCONSISTENT",
        "alert_verdict_consistency_status": "INCONSISTENT",
        "escalation_decision_packet_consistency_status": "INCONSISTENT",
        "alert_level_matrix_consistency_status": "INCONSISTENT",
        "drift_type_matrix_consistency_status": "INCONSISTENT",
        "escalation_path_matrix_consistency_status": "INCONSISTENT",
        "sla_matrix_consistency_status": "INCONSISTENT",
        "required_owner_matrix_consistency_status": "INCONSISTENT",
        "blocked_action_matrix_consistency_status": "INCONSISTENT",
        "unlock_prevention_matrix_consistency_status": "INCONSISTENT",
        "no_drift_record_packet_consistency_status": "INCONSISTENT",
        "simulated_blocking_drift_case_consistency_status": "INCONSISTENT",
        "final_classification_consistency_status": "INCONSISTENT",
        "drift_detected": True,
        "drift_details": ["MISSING_REQUIRED_ARTIFACTS"],
        "replay_alert_verdict_matrix": {},
        "replay_escalation_decision_packet_matrix": {},
        "replay_blocked_action_matrix": {},
        "replay_unlock_prevention_matrix": {},
        "reproducibility_metadata": {},
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def main():
    missing = [p for p in (P121_PATH, P136_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P137 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p136 = load_json(P136_PATH)

    replay_payload_runs = {}
    replay_fingerprints = {}
    replay_alert_verdict_matrix = {}
    replay_escalation_decision_packet_matrix = {}
    replay_blocked_action_matrix = {}
    replay_unlock_prevention_matrix = {}

    baseline_payload = replay_payload(p136)
    baseline_fingerprint = canonical_hash(baseline_payload)

    for idx in range(1, REPLAY_RUN_COUNT + 1):
        key = f"run_{idx}"
        payload = replay_payload(p136)
        replay_payload_runs[key] = payload
        replay_fingerprints[key] = canonical_hash(payload)
        replay_alert_verdict_matrix[key] = payload["alert_verdicts"]
        replay_escalation_decision_packet_matrix[key] = payload["escalation_decision_packets"]
        replay_blocked_action_matrix[key] = payload["blocked_action_matrix"]
        replay_unlock_prevention_matrix[key] = payload["unlock_prevention_matrix"]

    drift_details = []

    def consistency_status(name: str, selector):
        first = selector(replay_payload_runs["run_1"])
        for idx in range(2, REPLAY_RUN_COUNT + 1):
            key = f"run_{idx}"
            if selector(replay_payload_runs[key]) != first:
                drift_details.append(f"{name}_MISMATCH_{key}")
                return "INCONSISTENT"
        return "CONSISTENT"

    fingerprint_consistency_status = "CONSISTENT"
    for _, fp in replay_fingerprints.items():
        if fp != baseline_fingerprint:
            fingerprint_consistency_status = "INCONSISTENT"
            drift_details.append("FINGERPRINT_MISMATCH")
            break

    alert_verdict_consistency_status = consistency_status("ALERT_VERDICT", lambda x: x["alert_verdicts"])
    escalation_decision_packet_consistency_status = consistency_status(
        "ESCALATION_DECISION_PACKET", lambda x: x["escalation_decision_packets"]
    )
    alert_level_matrix_consistency_status = consistency_status(
        "ALERT_LEVEL_MATRIX", lambda x: x["alert_level_execution_matrix"]
    )
    drift_type_matrix_consistency_status = consistency_status(
        "DRIFT_TYPE_MATRIX", lambda x: x["drift_type_execution_matrix"]
    )
    escalation_path_matrix_consistency_status = consistency_status(
        "ESCALATION_PATH_MATRIX", lambda x: x["escalation_path_execution_matrix"]
    )
    sla_matrix_consistency_status = consistency_status("SLA_MATRIX", lambda x: x["sla_execution_matrix"])
    required_owner_matrix_consistency_status = consistency_status(
        "REQUIRED_OWNER_MATRIX", lambda x: x["required_owner_execution_matrix"]
    )
    blocked_action_matrix_consistency_status = consistency_status(
        "BLOCKED_ACTION_MATRIX", lambda x: x["blocked_action_matrix"]
    )
    unlock_prevention_matrix_consistency_status = consistency_status(
        "UNLOCK_PREVENTION_MATRIX", lambda x: x["unlock_prevention_matrix"]
    )
    no_drift_record_packet_consistency_status = consistency_status(
        "NO_DRIFT_RECORD_PACKET", lambda x: x["no_drift_record_packet"]
    )
    simulated_blocking_drift_case_consistency_status = consistency_status(
        "SIMULATED_BLOCKING_DRIFT_CASE", lambda x: x["simulated_blocking_drift_cases"]
    )
    final_classification_consistency_status = consistency_status(
        "FINAL_CLASSIFICATION", lambda x: x["final_classification"]
    )

    evaluated_drift_event_count_stable = all(
        replay_payload_runs[f"run_{idx}"]["evaluated_drift_event_count"]
        == replay_payload_runs["run_1"]["evaluated_drift_event_count"]
        for idx in range(2, REPLAY_RUN_COUNT + 1)
    )
    if not evaluated_drift_event_count_stable:
        drift_details.append("EVALUATED_DRIFT_EVENT_COUNT_MISMATCH")

    packets = replay_payload_runs["run_1"]["escalation_decision_packets"]
    packet_by_id = {p.get("drift_case_id"): p for p in packets}

    no_drift_case_ok = (
        packet_by_id.get("NO_SIGNOFF_DRIFT_RECORD_ONLY", {}).get("blocked") is False
        and packet_by_id.get("NO_SIGNOFF_DRIFT_RECORD_ONLY", {}).get("critical_stop") is False
        and packet_by_id.get("NO_SIGNOFF_DRIFT_RECORD_ONLY", {}).get("escalation_path") == "record_only"
    )
    if not no_drift_case_ok:
        drift_details.append("NO_DRIFT_CASE_NOT_RECORD_ONLY")

    dangerous_cases_ok = True
    for case_id in DANGEROUS_CASE_IDS:
        packet = packet_by_id.get(case_id, {})
        if packet.get("blocked") is not True:
            dangerous_cases_ok = False
            drift_details.append(f"DANGEROUS_CASE_NOT_BLOCKED_{case_id}")

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
    if governance_fail:
        drift_details.append("GOVERNANCE_INVARIANT_FAILURE")

    drift_detected = bool(drift_details)

    blockers = sorted(set(p136.get("blockers", []) + [
        "DRIFT_ALERT_REPLAY_CONSISTENCY_GOVERNANCE_ONLY_BLOCKER",
        "FULL_REGRESSION_NOT_RUN_BLOCKER",
    ]))

    final_classification = "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS"
    if governance_fail:
        final_classification = "P137_DRIFT_ALERT_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION"

    summary = {
        "drift_alert_replay_consistency_gate_status": "READY_WITH_BLOCKERS",
        "source_signoff_drift_alert_runner_status": p136.get("signoff_drift_alert_runner_status", "UNKNOWN"),
        "source_evaluated_drift_event_count": p136.get("evaluated_drift_event_count", 0),
        "source_replay_run_count": p136.get("source_replay_run_count", 0),
        "source_signoff_packet_count": p136.get("source_signoff_packet_count", 0),
        "source_invalid_packet_count": p136.get("source_invalid_packet_count", 0),
        "replay_run_count": REPLAY_RUN_COUNT,
        "baseline_fingerprint": baseline_fingerprint,
        "replay_fingerprints": replay_fingerprints,
        "fingerprint_consistency_status": fingerprint_consistency_status,
        "alert_verdict_consistency_status": alert_verdict_consistency_status,
        "escalation_decision_packet_consistency_status": escalation_decision_packet_consistency_status,
        "alert_level_matrix_consistency_status": alert_level_matrix_consistency_status,
        "drift_type_matrix_consistency_status": drift_type_matrix_consistency_status,
        "escalation_path_matrix_consistency_status": escalation_path_matrix_consistency_status,
        "sla_matrix_consistency_status": sla_matrix_consistency_status,
        "required_owner_matrix_consistency_status": required_owner_matrix_consistency_status,
        "blocked_action_matrix_consistency_status": blocked_action_matrix_consistency_status,
        "unlock_prevention_matrix_consistency_status": unlock_prevention_matrix_consistency_status,
        "no_drift_record_packet_consistency_status": no_drift_record_packet_consistency_status,
        "simulated_blocking_drift_case_consistency_status": simulated_blocking_drift_case_consistency_status,
        "final_classification_consistency_status": final_classification_consistency_status,
        "evaluated_drift_event_count_stable": evaluated_drift_event_count_stable,
        "dangerous_case_block_status_consistent": dangerous_cases_ok,
        "no_drift_record_only_status_consistent": no_drift_case_ok,
        "drift_detected": drift_detected,
        "drift_details": sorted(set(drift_details)),
        "replay_alert_verdict_matrix": replay_alert_verdict_matrix,
        "replay_escalation_decision_packet_matrix": replay_escalation_decision_packet_matrix,
        "replay_blocked_action_matrix": replay_blocked_action_matrix,
        "replay_unlock_prevention_matrix": replay_unlock_prevention_matrix,
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Drift alert replay consistency does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "reproducibility_metadata": {
            "fingerprint_algorithm": "sha256",
            "canonicalization": "json_sort_keys_true_compact_separators",
            "replay_run_count": REPLAY_RUN_COUNT,
            "deterministic_ordering": "sorted_dict_keys_and_stable_source_artifacts",
            "baseline_source": "P136_DRIFT_ALERT_RUNNER_ARTIFACTS",
        },
        "regression_status": {
            "targeted_p118_p137_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P137 task.",
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
        f.write("# P137 Drift Alert Replay Consistency Gate (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- drift_alert_replay_consistency_gate_status: {summary['drift_alert_replay_consistency_gate_status']}\n")
        f.write(f"- source_signoff_drift_alert_runner_status: {summary['source_signoff_drift_alert_runner_status']}\n")
        f.write(f"- source_evaluated_drift_event_count: {summary['source_evaluated_drift_event_count']}\n")
        f.write(f"- replay_run_count: {summary['replay_run_count']}\n")
        f.write(f"- source_signoff_packet_count: {summary['source_signoff_packet_count']}\n")
        f.write(f"- source_invalid_packet_count: {summary['source_invalid_packet_count']}\n")
        f.write(f"- drift_detected: {summary['drift_detected']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Consistency Statuses\n")
        f.write(f"- fingerprint_consistency_status: {summary['fingerprint_consistency_status']}\n")
        f.write(f"- alert_verdict_consistency_status: {summary['alert_verdict_consistency_status']}\n")
        f.write(f"- escalation_decision_packet_consistency_status: {summary['escalation_decision_packet_consistency_status']}\n")
        f.write(f"- alert_level_matrix_consistency_status: {summary['alert_level_matrix_consistency_status']}\n")
        f.write(f"- drift_type_matrix_consistency_status: {summary['drift_type_matrix_consistency_status']}\n")
        f.write(f"- escalation_path_matrix_consistency_status: {summary['escalation_path_matrix_consistency_status']}\n")
        f.write(f"- sla_matrix_consistency_status: {summary['sla_matrix_consistency_status']}\n")
        f.write(f"- required_owner_matrix_consistency_status: {summary['required_owner_matrix_consistency_status']}\n")
        f.write(f"- blocked_action_matrix_consistency_status: {summary['blocked_action_matrix_consistency_status']}\n")
        f.write(f"- unlock_prevention_matrix_consistency_status: {summary['unlock_prevention_matrix_consistency_status']}\n")
        f.write(f"- no_drift_record_packet_consistency_status: {summary['no_drift_record_packet_consistency_status']}\n")
        f.write(f"- simulated_blocking_drift_case_consistency_status: {summary['simulated_blocking_drift_case_consistency_status']}\n")
        f.write(f"- final_classification_consistency_status: {summary['final_classification_consistency_status']}\n\n")

        f.write("## Replay Fingerprints\n")
        f.write(f"- baseline_fingerprint: {summary['baseline_fingerprint']}\n")
        f.write(f"- replay_fingerprints: {summary['replay_fingerprints']}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p137_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")

    print(f"P137 summary written to {OUT_PATH}")
    print(f"P137 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
