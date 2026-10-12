# P128 Deterministic Replay Consistency Gate
# Paper-only deterministic replay verification over P127 evaluation outputs.

import hashlib
import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P126_PATH = "data/mlb_2026/derived/p126_legal_evidence_intake_payload_fixture_negative_cases_summary.json"
P127_PATH = "data/mlb_2026/derived/p127_intake_payload_evaluation_runner_verdict_report_summary.json"
OUT_PATH = "data/mlb_2026/derived/p128_deterministic_replay_consistency_gate_summary.json"
REPORT_PATH = "report/p128_deterministic_replay_consistency_gate_20260601.md"

REPLAY_RUN_COUNT = 3

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use replay consistency outputs for governance diagnostics only",
    "Collect real legal evidence via legal/compliance workflow before approval consideration",
    "Keep full regression status explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not activate providers or approve authorization from placeholder data",
    "Do not unlock recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not store secrets, auth URLs, private contract body, or row-level proprietary odds",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS",
    "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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


def normalize_unlock_prevention_matrix(unlock_matrix):
    if isinstance(unlock_matrix, dict):
        normalized = {}
        for case_id in sorted(unlock_matrix.keys()):
            row = unlock_matrix[case_id]
            normalized[case_id] = {
                "recommendation_unlock_allowed": bool(row.get("recommendation_unlock_allowed", False)),
                "production_unlock_allowed": bool(row.get("production_unlock_allowed", False)),
                "ev_unlock_allowed": bool(row.get("ev_unlock_allowed", False)),
                "clv_unlock_allowed": bool(row.get("clv_unlock_allowed", False)),
                "kelly_unlock_allowed": bool(row.get("kelly_unlock_allowed", False)),
                "stake_unlock_allowed": bool(row.get("stake_unlock_allowed", False)),
                "profit_unlock_allowed": bool(row.get("profit_unlock_allowed", False)),
            }
        return normalized

    if isinstance(unlock_matrix, list):
        normalized = {}
        for row in unlock_matrix:
            case_id = row.get("case_id", "UNKNOWN_CASE")
            normalized[case_id] = {
                "recommendation_unlock_allowed": bool(row.get("recommendation_unlock_allowed", False)),
                "production_unlock_allowed": bool(row.get("production_unlock_allowed", False)),
                "ev_unlock_allowed": bool(row.get("ev_unlock_allowed", False)),
                "clv_unlock_allowed": bool(row.get("clv_unlock_allowed", False)),
                "kelly_unlock_allowed": bool(row.get("kelly_unlock_allowed", False)),
                "stake_unlock_allowed": bool(row.get("stake_unlock_allowed", False)),
                "profit_unlock_allowed": bool(row.get("profit_unlock_allowed", False)),
            }
        return {k: normalized[k] for k in sorted(normalized.keys())}

    return {}


def normalize_rule_matrix(rule_matrix: dict):
    normalized = {}
    for case_id in sorted(rule_matrix.keys()):
        rows = rule_matrix.get(case_id, [])
        rule_ids = sorted([row.get("rule_id", "") for row in rows if row.get("rule_id")])
        normalized[case_id] = rule_ids
    return normalized


def normalize_verdicts(verdicts: list):
    verdict_matrix = {}
    blocked_reason_matrix = {}
    for row in sorted(verdicts, key=lambda x: x.get("case_id", "")):
        case_id = row.get("case_id", "UNKNOWN_CASE")
        verdict_matrix[case_id] = row.get("status", "UNKNOWN")
        blocked_reason_matrix[case_id] = sorted(row.get("blocked_reasons", []))
    return verdict_matrix, blocked_reason_matrix


def compute_fingerprint(snapshot: dict):
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_replay_snapshot(p127: dict):
    verdict_matrix, blocked_reason_matrix = normalize_verdicts(p127.get("verdicts", []))
    rule_matrix = normalize_rule_matrix(p127.get("rule_evaluation_matrix", {}))
    unlock_matrix = normalize_unlock_prevention_matrix(p127.get("unlock_prevention_matrix", {}))

    snapshot = {
        "evaluated_fixture_count": int(p127.get("evaluated_fixture_count", 0)),
        "expected_blocked_count": int(p127.get("expected_blocked_count", 0)),
        "actual_blocked_count": int(p127.get("actual_blocked_count", 0)),
        "unexpected_allowed_count": int(p127.get("unexpected_allowed_count", 0)),
        "verdict_matrix": verdict_matrix,
        "blocked_reason_matrix": blocked_reason_matrix,
        "rule_matrix": rule_matrix,
        "unlock_prevention_matrix": unlock_matrix,
    }

    return snapshot


def main():
    missing = []
    for p in (P121_PATH, P126_PATH, P127_PATH):
        if not Path(p).exists():
            missing.append(p)

    if missing:
        summary = {
            "replay_consistency_gate_status": "BLOCKED",
            "replay_run_count": 0,
            "source_fixture_count": 0,
            "baseline_fingerprint": "",
            "replay_fingerprints": [],
            "fingerprint_consistency_status": "DRIFT_DETECTED",
            "verdict_consistency_status": "DRIFT_DETECTED",
            "blocked_reason_consistency_status": "DRIFT_DETECTED",
            "rule_matrix_consistency_status": "DRIFT_DETECTED",
            "unlock_prevention_consistency_status": "DRIFT_DETECTED",
            "drift_detected": True,
            "drift_details": [{"type": "MISSING_REQUIRED_ARTIFACTS", "missing": missing}],
            "replay_verdict_matrix": {},
            "replay_blocked_reason_matrix": {},
            "replay_unlock_prevention_matrix": {},
            "reproducibility_metadata": {
                "gate_version": "P128.20260601",
                "replay_mode": "deterministic_snapshot_replay",
                "missing_artifacts": missing,
            },
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "prohibited_actions": PROHIBITED_ACTIONS,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "final_classification": "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
            "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P128 replay summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p126 = load_json(P126_PATH)

    replay_fingerprints = []
    replay_snapshots = {}
    replay_verdict_matrix = {}
    replay_blocked_reason_matrix = {}
    replay_unlock_prevention_matrix = {}

    for i in range(1, REPLAY_RUN_COUNT + 1):
        p127 = load_json(P127_PATH)
        snapshot = build_replay_snapshot(p127)
        run_id = f"run_{i}"

        replay_snapshots[run_id] = snapshot
        replay_verdict_matrix[run_id] = snapshot["verdict_matrix"]
        replay_blocked_reason_matrix[run_id] = snapshot["blocked_reason_matrix"]
        replay_unlock_prevention_matrix[run_id] = snapshot["unlock_prevention_matrix"]

        replay_fingerprints.append(
            {
                "run_id": run_id,
                "fingerprint": compute_fingerprint(snapshot),
                "evaluated_fixture_count": snapshot["evaluated_fixture_count"],
                "expected_blocked_count": snapshot["expected_blocked_count"],
                "actual_blocked_count": snapshot["actual_blocked_count"],
                "unexpected_allowed_count": snapshot["unexpected_allowed_count"],
            }
        )

    baseline_snapshot = replay_snapshots["run_1"]
    baseline_fingerprint = replay_fingerprints[0]["fingerprint"]

    drift_details = []
    for i in range(2, REPLAY_RUN_COUNT + 1):
        run_id = f"run_{i}"
        current = replay_snapshots[run_id]
        if current["verdict_matrix"] != baseline_snapshot["verdict_matrix"]:
            drift_details.append({"run_id": run_id, "type": "VERDICT_MATRIX_DRIFT"})
        if current["blocked_reason_matrix"] != baseline_snapshot["blocked_reason_matrix"]:
            drift_details.append({"run_id": run_id, "type": "BLOCKED_REASON_MATRIX_DRIFT"})
        if current["rule_matrix"] != baseline_snapshot["rule_matrix"]:
            drift_details.append({"run_id": run_id, "type": "RULE_MATRIX_DRIFT"})
        if current["unlock_prevention_matrix"] != baseline_snapshot["unlock_prevention_matrix"]:
            drift_details.append({"run_id": run_id, "type": "UNLOCK_PREVENTION_MATRIX_DRIFT"})

    all_fingerprints = [x["fingerprint"] for x in replay_fingerprints]
    fingerprint_consistent = len(set(all_fingerprints)) == 1
    verdict_consistent = len({json.dumps(v, sort_keys=True) for v in replay_verdict_matrix.values()}) == 1
    blocked_reason_consistent = len({json.dumps(v, sort_keys=True) for v in replay_blocked_reason_matrix.values()}) == 1
    unlock_prevention_consistent = len({json.dumps(v, sort_keys=True) for v in replay_unlock_prevention_matrix.values()}) == 1
    rule_matrix_consistent = len({json.dumps(v["rule_matrix"], sort_keys=True) for v in replay_snapshots.values()}) == 1

    for run in replay_fingerprints:
        run_id = run["run_id"]
        snap = replay_snapshots[run_id]
        if run["evaluated_fixture_count"] != 19:
            drift_details.append({"run_id": run_id, "type": "EVALUATED_FIXTURE_COUNT_MISMATCH", "value": run["evaluated_fixture_count"]})
        if run["expected_blocked_count"] != 19:
            drift_details.append({"run_id": run_id, "type": "EXPECTED_BLOCKED_COUNT_MISMATCH", "value": run["expected_blocked_count"]})
        if run["actual_blocked_count"] != 19:
            drift_details.append({"run_id": run_id, "type": "ACTUAL_BLOCKED_COUNT_MISMATCH", "value": run["actual_blocked_count"]})
        if run["unexpected_allowed_count"] != 0:
            drift_details.append({"run_id": run_id, "type": "UNEXPECTED_ALLOWED_COUNT_MISMATCH", "value": run["unexpected_allowed_count"]})

        non_blocked = [case_id for case_id, status in snap["verdict_matrix"].items() if status != "BLOCKED"]
        if non_blocked:
            drift_details.append({"run_id": run_id, "type": "NON_BLOCKED_VERDICTS", "cases": non_blocked})

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

    drift_detected = len(drift_details) > 0 or not (
        fingerprint_consistent
        and verdict_consistent
        and blocked_reason_consistent
        and rule_matrix_consistent
        and unlock_prevention_consistent
    )

    blockers = sorted({b for b in p127.get("blockers", [])})
    if drift_detected:
        blockers.append("DETERMINISTIC_REPLAY_DRIFT_DETECTED_BLOCKER")
    blockers.append("FULL_REGRESSION_NOT_RUN_BLOCKER")
    blockers = sorted(set(blockers))

    final_classification = "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS"
    if governance_fail or drift_detected:
        final_classification = "P128_DETERMINISTIC_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION"

    summary = {
        "replay_consistency_gate_status": "READY_WITH_BLOCKERS",
        "replay_run_count": REPLAY_RUN_COUNT,
        "source_fixture_count": len(p126.get("negative_cases", [])),
        "baseline_fingerprint": baseline_fingerprint,
        "replay_fingerprints": replay_fingerprints,
        "fingerprint_consistency_status": "CONSISTENT" if fingerprint_consistent else "DRIFT_DETECTED",
        "verdict_consistency_status": "CONSISTENT" if verdict_consistent else "DRIFT_DETECTED",
        "blocked_reason_consistency_status": "CONSISTENT" if blocked_reason_consistent else "DRIFT_DETECTED",
        "rule_matrix_consistency_status": "CONSISTENT" if rule_matrix_consistent else "DRIFT_DETECTED",
        "unlock_prevention_consistency_status": "CONSISTENT" if unlock_prevention_consistent else "DRIFT_DETECTED",
        "drift_detected": drift_detected,
        "drift_details": drift_details,
        "replay_verdict_matrix": replay_verdict_matrix,
        "replay_blocked_reason_matrix": replay_blocked_reason_matrix,
        "replay_unlock_prevention_matrix": replay_unlock_prevention_matrix,
        "governance_invariants": governance_invariants,
        "regression_status": {
            "targeted_p118_p128_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P128 task.",
        },
        "reproducibility_metadata": {
            "gate_version": "P128.20260601",
            "replay_mode": "deterministic_snapshot_replay",
            "replay_input_source": P127_PATH,
            "source_p127_final_classification": p127.get("final_classification", "UNKNOWN"),
            "source_p126_final_classification": p126.get("fixture_metadata", {}).get("final_classification", "UNKNOWN"),
            "determinism_scope": "counts + verdict_matrix + blocked_reason_matrix + rule_matrix + unlock_prevention_matrix",
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
        f.write("# P128 Deterministic Replay Consistency Gate (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- replay_consistency_gate_status: {summary['replay_consistency_gate_status']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Replay Counts\n")
        f.write(f"- replay_run_count: {summary['replay_run_count']}\n")
        f.write(f"- source_fixture_count: {summary['source_fixture_count']}\n")
        f.write("\n")

        f.write("## Consistency Status\n")
        f.write(f"- fingerprint_consistency_status: {summary['fingerprint_consistency_status']}\n")
        f.write(f"- verdict_consistency_status: {summary['verdict_consistency_status']}\n")
        f.write(f"- blocked_reason_consistency_status: {summary['blocked_reason_consistency_status']}\n")
        f.write(f"- rule_matrix_consistency_status: {summary['rule_matrix_consistency_status']}\n")
        f.write(f"- unlock_prevention_consistency_status: {summary['unlock_prevention_consistency_status']}\n")
        f.write(f"- drift_detected: {summary['drift_detected']}\n\n")

        f.write("## Fingerprints\n")
        f.write(f"- baseline_fingerprint: {summary['baseline_fingerprint']}\n")
        for row in summary["replay_fingerprints"]:
            f.write(
                f"- {row['run_id']}: {row['fingerprint']} | evaluated={row['evaluated_fixture_count']} | expected_blocked={row['expected_blocked_count']} | actual_blocked={row['actual_blocked_count']} | unexpected_allowed={row['unexpected_allowed_count']}\n"
            )
        f.write("\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariants"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p128_tests_status: NOT_RUN\n")
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

    print(f"P128 replay summary written to {OUT_PATH}")
    print(f"P128 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
