# P134 Sign-off Evidence Replay Consistency Gate
# Paper-only deterministic replay gate for P133 sign-off evidence validation artifacts.

import hashlib
import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P133_PATH = "data/mlb_2026/derived/p133_escalation_signoff_evidence_packet_validator_summary.json"
OUT_PATH = "data/mlb_2026/derived/p134_signoff_evidence_replay_consistency_gate_summary.json"
REPORT_PATH = "report/p134_signoff_evidence_replay_consistency_gate_20260601.md"

REPLAY_RUN_COUNT = 3

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use replay consistency output for governance diagnostics only",
    "Require blockers resolution before any legal/provider/production readiness claim",
    "Keep full regression state explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not unlock provider/recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not treat replay consistency as legal provider approval or production readiness",
    "Do not bypass blocker resolution and sign-off evidence requirements",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS",
    "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
    "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def build_unlock_prevention_snapshot(p133: dict):
    valid = p133.get("valid_signoff_packet_template", {})
    invalid_cases = p133.get("invalid_signoff_packet_cases", [])

    invalid_statuses = {row.get("case_id", "UNKNOWN"): row.get("status", "UNKNOWN") for row in invalid_cases}
    invalid_unlock_requests = {}
    for row in invalid_cases:
        packet = row.get("packet", {})
        invalid_unlock_requests[row.get("case_id", "UNKNOWN")] = {
            "provider_unlock_requested": bool(packet.get("provider_unlock_requested", False)),
            "odds_unlock_requested": bool(packet.get("odds_unlock_requested", False)),
            "recommendation_unlock_requested": bool(packet.get("recommendation_unlock_requested", False)),
            "production_unlock_requested": bool(packet.get("production_unlock_requested", False)),
            "ev_clv_kelly_unlock_requested": bool(packet.get("ev_clv_kelly_unlock_requested", False)),
            "live_or_paid_api_requested": bool(packet.get("live_or_paid_api_requested", False)),
        }

    return {
        "valid_template_unlock_requests": {
            "provider_unlock_requested": bool(valid.get("provider_unlock_requested", False)),
            "odds_unlock_requested": bool(valid.get("odds_unlock_requested", False)),
            "recommendation_unlock_requested": bool(valid.get("recommendation_unlock_requested", False)),
            "production_unlock_requested": bool(valid.get("production_unlock_requested", False)),
            "ev_clv_kelly_unlock_requested": bool(valid.get("ev_clv_kelly_unlock_requested", False)),
            "live_or_paid_api_requested": bool(valid.get("live_or_paid_api_requested", False)),
        },
        "invalid_case_statuses": invalid_statuses,
        "invalid_case_unlock_requests": invalid_unlock_requests,
        "unlock_policy": "NO_UNLOCK_ALLOWED",
    }


def build_replay_snapshot(p133: dict, governance_summary: dict):
    verdict_matrix = p133.get("signoff_verdict_matrix", {})
    blocker_matrix = {
        "missing_signoff_blockers": p133.get("missing_signoff_blockers", {}),
        "unauthorized_signoff_blockers": p133.get("unauthorized_signoff_blockers", {}),
        "role_mismatch_blockers": p133.get("role_mismatch_blockers", {}),
        "stale_or_missing_timestamp_blockers": p133.get("stale_or_missing_timestamp_blockers", {}),
        "non_unlock_attestation_blockers": p133.get("non_unlock_attestation_blockers", {}),
    }
    required_evidence_matrix = p133.get("required_evidence_matrix", {})
    escalation_coverage = p133.get("escalation_level_coverage_matrix", {})
    unlock_prevention_matrix = build_unlock_prevention_snapshot(p133)

    replay_unit = {
        "signoff_verdict_matrix": verdict_matrix,
        "blocker_matrix": blocker_matrix,
        "required_evidence_matrix": required_evidence_matrix,
        "escalation_level_coverage_matrix": escalation_coverage,
        "governance_invariant_summary": governance_summary,
        "unlock_prevention_matrix": unlock_prevention_matrix,
    }
    fingerprint = sha256_text(canonical_json(replay_unit))

    return replay_unit, fingerprint


def empty_summary():
    return {
        "signoff_replay_consistency_gate_status": "BLOCKED",
        "source_signoff_packet_validator_status": "UNKNOWN",
        "replay_run_count": 0,
        "source_signoff_packet_count": 0,
        "source_invalid_packet_count": 0,
        "baseline_fingerprint": "",
        "replay_fingerprints": {},
        "fingerprint_consistency_status": "NOT_EVALUATED",
        "verdict_matrix_consistency_status": "NOT_EVALUATED",
        "blocker_classification_consistency_status": "NOT_EVALUATED",
        "required_evidence_matrix_consistency_status": "NOT_EVALUATED",
        "escalation_level_coverage_consistency_status": "NOT_EVALUATED",
        "governance_invariant_consistency_status": "NOT_EVALUATED",
        "unlock_prevention_consistency_status": "NOT_EVALUATED",
        "drift_detected": True,
        "drift_details": ["MISSING_REQUIRED_ARTIFACTS"],
        "replay_signoff_verdict_matrix": {},
        "replay_blocker_matrix": {},
        "replay_required_evidence_matrix": {},
        "replay_unlock_prevention_matrix": {},
        "reproducibility_metadata": {},
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
        "final_classification": "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_BLOCKED_BY_MISSING_ARTIFACTS",
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }


def main():
    missing = [p for p in (P121_PATH, P133_PATH) if not Path(p).exists()]
    if missing:
        summary = empty_summary()
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P134 summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p133 = load_json(P133_PATH)

    governance_summary = governance_invariants(p121)

    replay_fingerprints = {}
    replay_signoff_verdict_matrix = {}
    replay_blocker_matrix = {}
    replay_required_evidence_matrix = {}
    replay_unlock_prevention_matrix = {}
    replay_escalation_coverage_matrix = {}
    replay_governance_summary = {}

    baseline_unit = None
    baseline_fingerprint = ""

    for run_idx in range(1, REPLAY_RUN_COUNT + 1):
        run_key = f"run_{run_idx}"
        replay_unit, fp = build_replay_snapshot(p133, governance_summary)
        replay_fingerprints[run_key] = fp
        replay_signoff_verdict_matrix[run_key] = replay_unit["signoff_verdict_matrix"]
        replay_blocker_matrix[run_key] = replay_unit["blocker_matrix"]
        replay_required_evidence_matrix[run_key] = replay_unit["required_evidence_matrix"]
        replay_unlock_prevention_matrix[run_key] = replay_unit["unlock_prevention_matrix"]
        replay_escalation_coverage_matrix[run_key] = replay_unit["escalation_level_coverage_matrix"]
        replay_governance_summary[run_key] = replay_unit["governance_invariant_summary"]

        if run_idx == 1:
            baseline_unit = replay_unit
            baseline_fingerprint = fp

    drift_details = []

    fingerprint_consistency = "CONSISTENT"
    for run_key, fp in replay_fingerprints.items():
        if fp != baseline_fingerprint:
            fingerprint_consistency = "DRIFT_DETECTED"
            drift_details.append(f"FINGERPRINT_MISMATCH:{run_key}")

    def consistency_status(extractor_name, replay_map):
        status = "CONSISTENT"
        for run_key, payload in replay_map.items():
            if payload != baseline_unit[extractor_name]:
                status = "DRIFT_DETECTED"
                drift_details.append(f"{extractor_name.upper()}_MISMATCH:{run_key}")
        return status

    verdict_matrix_consistency = consistency_status("signoff_verdict_matrix", replay_signoff_verdict_matrix)
    blocker_classification_consistency = consistency_status("blocker_matrix", replay_blocker_matrix)
    required_evidence_matrix_consistency = consistency_status("required_evidence_matrix", replay_required_evidence_matrix)
    escalation_coverage_consistency = consistency_status("escalation_level_coverage_matrix", replay_escalation_coverage_matrix)
    governance_consistency = consistency_status("governance_invariant_summary", replay_governance_summary)
    unlock_prevention_consistency = consistency_status("unlock_prevention_matrix", replay_unlock_prevention_matrix)

    source_signoff_packet_count = len(p133.get("signoff_verdict_matrix", {}))
    source_invalid_packet_count = len(p133.get("invalid_signoff_packet_cases", []))

    # Additional deterministic checks for required replay behavior.
    for run_key, verdicts in replay_signoff_verdict_matrix.items():
        valid_status = verdicts.get("VALID_SIGNOFF_PACKET_TEMPLATE", {}).get("status")
        if valid_status != "GOVERNANCE_ONLY_PENDING_REVIEW":
            drift_details.append(f"VALID_TEMPLATE_STATUS_MISMATCH:{run_key}:{valid_status}")

        for case_id, row in verdicts.items():
            if case_id == "VALID_SIGNOFF_PACKET_TEMPLATE":
                continue
            if row.get("status") != "BLOCKED":
                drift_details.append(f"INVALID_CASE_NOT_BLOCKED:{run_key}:{case_id}")

    for run_key, unlock_matrix in replay_unlock_prevention_matrix.items():
        valid_unlock = unlock_matrix.get("valid_template_unlock_requests", {})
        for k, v in valid_unlock.items():
            if v is True:
                drift_details.append(f"VALID_TEMPLATE_UNLOCK_TRUE:{run_key}:{k}")

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

    drift_detected = len(drift_details) > 0

    blockers = sorted(set(p133.get("blockers", [])))
    blockers.extend(
        [
            "SIGNOFF_REPLAY_CONSISTENCY_GOVERNANCE_ONLY_BLOCKER",
            "FULL_REGRESSION_NOT_RUN_BLOCKER",
        ]
    )
    blockers = sorted(set(blockers))

    final_classification = "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_READY_WITH_BLOCKERS"
    if governance_fail or drift_detected:
        final_classification = "P134_SIGNOFF_EVIDENCE_REPLAY_CONSISTENCY_GATE_FAILED_VALIDATION"

    summary = {
        "signoff_replay_consistency_gate_status": "READY_WITH_BLOCKERS" if not drift_detected else "FAILED_VALIDATION",
        "source_signoff_packet_validator_status": p133.get("signoff_packet_validator_status", "UNKNOWN"),
        "replay_run_count": REPLAY_RUN_COUNT,
        "source_signoff_packet_count": source_signoff_packet_count,
        "source_invalid_packet_count": source_invalid_packet_count,
        "baseline_fingerprint": baseline_fingerprint,
        "replay_fingerprints": replay_fingerprints,
        "fingerprint_consistency_status": fingerprint_consistency,
        "verdict_matrix_consistency_status": verdict_matrix_consistency,
        "blocker_classification_consistency_status": blocker_classification_consistency,
        "required_evidence_matrix_consistency_status": required_evidence_matrix_consistency,
        "escalation_level_coverage_consistency_status": escalation_coverage_consistency,
        "governance_invariant_consistency_status": governance_consistency,
        "unlock_prevention_consistency_status": unlock_prevention_consistency,
        "drift_detected": drift_detected,
        "drift_details": sorted(drift_details),
        "replay_signoff_verdict_matrix": replay_signoff_verdict_matrix,
        "replay_blocker_matrix": replay_blocker_matrix,
        "replay_required_evidence_matrix": replay_required_evidence_matrix,
        "replay_unlock_prevention_matrix": replay_unlock_prevention_matrix,
        "governance_invariant_summary": governance_summary,
        "governance_statement": "Sign-off replay approval does not imply legal provider approval, real odds approval, recommendation readiness, or production readiness.",
        "reproducibility_metadata": {
            "fingerprint_algorithm": "sha256",
            "canonicalization": "json_sort_keys_true_compact_separators",
            "replay_run_count": REPLAY_RUN_COUNT,
            "deterministic_ordering": "sorted_dict_keys_and_stable_source_artifacts",
            "baseline_source": "P133_SIGNOFF_VALIDATION_ARTIFACTS",
        },
        "regression_status": {
            "targeted_p118_p134_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P134 task.",
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
        f.write("# P134 Sign-off Evidence Replay Consistency Gate (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- signoff_replay_consistency_gate_status: {summary['signoff_replay_consistency_gate_status']}\n")
        f.write(f"- source_signoff_packet_validator_status: {summary['source_signoff_packet_validator_status']}\n")
        f.write(f"- replay_run_count: {summary['replay_run_count']}\n")
        f.write(f"- source_signoff_packet_count: {summary['source_signoff_packet_count']}\n")
        f.write(f"- source_invalid_packet_count: {summary['source_invalid_packet_count']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Replay Consistency\n")
        f.write(f"- baseline_fingerprint: {summary['baseline_fingerprint']}\n")
        f.write(f"- replay_fingerprints: {summary['replay_fingerprints']}\n")
        f.write(f"- fingerprint_consistency_status: {summary['fingerprint_consistency_status']}\n")
        f.write(f"- verdict_matrix_consistency_status: {summary['verdict_matrix_consistency_status']}\n")
        f.write(f"- blocker_classification_consistency_status: {summary['blocker_classification_consistency_status']}\n")
        f.write(f"- required_evidence_matrix_consistency_status: {summary['required_evidence_matrix_consistency_status']}\n")
        f.write(f"- escalation_level_coverage_consistency_status: {summary['escalation_level_coverage_consistency_status']}\n")
        f.write(f"- governance_invariant_consistency_status: {summary['governance_invariant_consistency_status']}\n")
        f.write(f"- unlock_prevention_consistency_status: {summary['unlock_prevention_consistency_status']}\n")
        f.write(f"- drift_detected: {summary['drift_detected']}\n")
        f.write(f"- drift_details: {summary['drift_details']}\n\n")

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariant_summary"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p134_tests_status: NOT_RUN\n")
        f.write("- full_regression_status: NOT_RUN\n\n")

        f.write("## Prohibited Actions\n")
        for item in summary["prohibited_actions"]:
            f.write(f"- {item}\n")
        f.write("\n")

        f.write("## Allowed Next Actions\n")
        for item in summary["allowed_next_actions"]:
            f.write(f"- {item}\n")

    print(f"P134 summary written to {OUT_PATH}")
    print(f"P134 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
