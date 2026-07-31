# P129 Replay Drift Alert Contract
# Paper-only contract for classifying and blocking replay drift from P128.

import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P128_PATH = "data/mlb_2026/derived/p128_deterministic_replay_consistency_gate_summary.json"
OUT_PATH = "data/mlb_2026/derived/p129_replay_drift_alert_contract_summary.json"
REPORT_PATH = "report/p129_replay_drift_alert_contract_20260601.md"

BASELINE_CHANGE_REQUIRED_FIELDS = [
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
]

DRIFT_DETAILS_REQUIRED_FIELDS = [
    "run_id",
    "drift_type",
    "observed_value",
    "expected_value",
    "impact_scope",
    "requires_block",
    "alert_level",
    "mitigation_action",
]

ALERT_LEVEL_DEFINITIONS = {
    "GREEN_NO_DRIFT": {
        "severity": 0,
        "condition": "No drift across fingerprint/verdict/blocked reasons/rule matrix/unlock prevention",
        "required_action": "Record pass and continue paper-only diagnostics",
    },
    "YELLOW_METADATA_ONLY_DRIFT": {
        "severity": 1,
        "condition": "Only reproducibility metadata changed; no verdict/rule/unlock impact",
        "required_action": "Open baseline change review request and await approval",
    },
    "ORANGE_BLOCKED_REASON_OR_RULE_DRIFT": {
        "severity": 2,
        "condition": "Blocked reason matrix or rule matrix changed while verdict remains BLOCKED",
        "required_action": "Block release path, require rule review and approval",
    },
    "RED_VERDICT_OR_UNLOCK_DRIFT": {
        "severity": 3,
        "condition": "Any verdict changes or any unlock prevention field becomes true",
        "required_action": "Immediate block and incident review",
    },
    "CRITICAL_PROVIDER_OR_PRODUCTION_UNLOCK_DRIFT": {
        "severity": 4,
        "condition": "Provider approval/authorization/production unlock indicators become true without legal evidence",
        "required_action": "Hard block, compliance escalation, and rollback execution",
    },
}

ALERT_ESCALATION_RULES = [
    {
        "from_level": "GREEN_NO_DRIFT",
        "to_level": "YELLOW_METADATA_ONLY_DRIFT",
        "trigger": "fingerprint changed with metadata-only deltas",
        "block_required": True,
    },
    {
        "from_level": "YELLOW_METADATA_ONLY_DRIFT",
        "to_level": "ORANGE_BLOCKED_REASON_OR_RULE_DRIFT",
        "trigger": "blocked reasons or rule matrix changed",
        "block_required": True,
    },
    {
        "from_level": "ORANGE_BLOCKED_REASON_OR_RULE_DRIFT",
        "to_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
        "trigger": "any verdict drift or unlock-prevention drift",
        "block_required": True,
    },
    {
        "from_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
        "to_level": "CRITICAL_PROVIDER_OR_PRODUCTION_UNLOCK_DRIFT",
        "trigger": "provider/authorization/production flags turn true without verified legal evidence",
        "block_required": True,
    },
]

BLOCKING_CONDITIONS = [
    {
        "condition_id": "C001_PREVIOUSLY_BLOCKED_BECOMES_ALLOWED",
        "condition": "Any previously BLOCKED verdict becomes ALLOWED",
        "alert_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C002_UNEXPECTED_ALLOWED_COUNT_GT_ZERO",
        "condition": "unexpected_allowed_count > 0",
        "alert_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C003_ACTUAL_BLOCKED_LT_EXPECTED_BLOCKED",
        "condition": "actual_blocked_count < expected_blocked_count",
        "alert_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C004_RECOMMENDATION_UNLOCK_TRUE",
        "condition": "recommendation_unlock_allowed becomes true",
        "alert_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C005_PRODUCTION_UNLOCK_TRUE",
        "condition": "production_unlock_allowed becomes true",
        "alert_level": "CRITICAL_PROVIDER_OR_PRODUCTION_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C006_EV_CLV_KELLY_STAKE_PROFIT_UNLOCK_TRUE",
        "condition": "any EV/CLV/Kelly/stake/profit unlock becomes true",
        "alert_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C007_PROVIDER_APPROVED_WITHOUT_VERIFIED_LEGAL_EVIDENCE",
        "condition": "provider_approved=true without verified legal evidence",
        "alert_level": "CRITICAL_PROVIDER_OR_PRODUCTION_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C008_AUTH_EVIDENCE_PRESENT_WITHOUT_VERIFIED_LEGAL_EVIDENCE",
        "condition": "authorization_evidence_present=true without verified legal evidence",
        "alert_level": "CRITICAL_PROVIDER_OR_PRODUCTION_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C009_REAL_ODDS_INGESTED_WITHOUT_APPROVAL",
        "condition": "real_legal_odds_ingested=true without explicit legal/provider approval",
        "alert_level": "CRITICAL_PROVIDER_OR_PRODUCTION_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C010_LIVE_OR_PAID_API_CALLS_NON_ZERO",
        "condition": "live_api_calls>0 or paid_api_called=true",
        "alert_level": "CRITICAL_PROVIDER_OR_PRODUCTION_UNLOCK_DRIFT",
    },
    {
        "condition_id": "C011_BASELINE_FINGERPRINT_CHANGED_WITHOUT_APPROVAL",
        "condition": "baseline fingerprint changed and baseline change approval missing",
        "alert_level": "ORANGE_BLOCKED_REASON_OR_RULE_DRIFT",
    },
    {
        "condition_id": "C012_DRIFT_DETAILS_MISSING_WHEN_DRIFT_DETECTED",
        "condition": "drift_detected=true but drift_details missing/empty",
        "alert_level": "ORANGE_BLOCKED_REASON_OR_RULE_DRIFT",
    },
]

VERDICT_DRIFT_RULES = {
    "rule": "Any verdict transition BLOCKED->ALLOWED or BLOCKED->UNKNOWN is blocking drift",
    "required_alert_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
    "block_required": True,
}

BLOCKED_REASON_DRIFT_RULES = {
    "rule": "Blocked reason set changes require rule review even if verdict remains BLOCKED",
    "required_alert_level": "ORANGE_BLOCKED_REASON_OR_RULE_DRIFT",
    "block_required": True,
}

RULE_MATRIX_DRIFT_RULES = {
    "rule": "Rule ID/name mapping drift requires approval before baseline update",
    "required_alert_level": "ORANGE_BLOCKED_REASON_OR_RULE_DRIFT",
    "block_required": True,
}

UNLOCK_PREVENTION_DRIFT_RULES = {
    "rule": "Any unlock-prevention field drift to true is hard-blocking",
    "required_alert_level": "RED_VERDICT_OR_UNLOCK_DRIFT",
    "block_required": True,
}

FINGERPRINT_DRIFT_RULES = {
    "rule": "Fingerprint drift is blocking unless approved baseline-change request exists",
    "required_alert_level": "YELLOW_METADATA_ONLY_DRIFT",
    "block_required": True,
}

REPRODUCIBILITY_METADATA_DRIFT_RULES = {
    "rule": "Metadata-only drift can be reviewed under controlled baseline-change workflow",
    "required_alert_level": "YELLOW_METADATA_ONLY_DRIFT",
    "block_required": True,
}

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use replay drift alert contract for governance diagnostics only",
    "Open baseline change request when fingerprint changes",
    "Keep full regression state explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not ingest real odds or call live/paid APIs",
    "Do not activate providers or approve authorization from placeholders",
    "Do not unlock recommendation/production/EV/CLV/Kelly/stake/profit",
    "Do not bypass baseline hash change review workflow",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P129_REPLAY_DRIFT_ALERT_CONTRACT_READY_WITH_BLOCKERS",
    "P129_REPLAY_DRIFT_ALERT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
    "P129_REPLAY_DRIFT_ALERT_CONTRACT_FAILED_VALIDATION",
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


def main():
    missing = []
    for p in (P121_PATH, P128_PATH):
        if not Path(p).exists():
            missing.append(p)

    if missing:
        summary = {
            "replay_drift_alert_contract_status": "BLOCKED",
            "source_replay_gate_status": "UNKNOWN",
            "source_replay_run_count": 0,
            "source_fixture_count": 0,
            "source_baseline_fingerprint": "",
            "source_drift_detected": None,
            "alert_level_definitions": ALERT_LEVEL_DEFINITIONS,
            "alert_escalation_rules": ALERT_ESCALATION_RULES,
            "blocking_conditions": BLOCKING_CONDITIONS,
            "baseline_hash_change_review_rules": {
                "required_fields": BASELINE_CHANGE_REQUIRED_FIELDS,
                "workflow_status": "MISSING_SOURCE_ARTIFACTS",
            },
            "verdict_drift_rules": VERDICT_DRIFT_RULES,
            "blocked_reason_drift_rules": BLOCKED_REASON_DRIFT_RULES,
            "rule_matrix_drift_rules": RULE_MATRIX_DRIFT_RULES,
            "unlock_prevention_drift_rules": UNLOCK_PREVENTION_DRIFT_RULES,
            "fingerprint_drift_rules": FINGERPRINT_DRIFT_RULES,
            "reproducibility_metadata_drift_rules": REPRODUCIBILITY_METADATA_DRIFT_RULES,
            "drift_details_required_fields": DRIFT_DETAILS_REQUIRED_FIELDS,
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "prohibited_actions": PROHIBITED_ACTIONS,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "final_classification": "P129_REPLAY_DRIFT_ALERT_CONTRACT_BLOCKED_BY_MISSING_ARTIFACTS",
            "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P129 contract summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p128 = load_json(P128_PATH)

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

    baseline_hash_change_review_rules = {
        "required_fields": BASELINE_CHANGE_REQUIRED_FIELDS,
        "approval_policy": "Any baseline fingerprint change requires completed request with reviewer approval before acceptance.",
        "non_unlock_attestation_required": "Baseline change does not unlock provider/odds/recommendation/production.",
        "template": {
            "baseline_change_request_id": "<REQUIRED>",
            "baseline_change_owner": "<REQUIRED>",
            "baseline_change_reason": "<REQUIRED>",
            "source_fixture_version_before": "<REQUIRED>",
            "source_fixture_version_after": "<REQUIRED>",
            "old_fingerprint": "<REQUIRED>",
            "new_fingerprint": "<REQUIRED>",
            "rule_change_summary": "<REQUIRED>",
            "expected_verdict_delta": "<REQUIRED>",
            "reviewer_approval_status": "<REQUIRED>",
            "reviewer_identity": "<REQUIRED>",
            "approval_timestamp": "<REQUIRED>",
            "rollback_plan": "<REQUIRED>",
            "non_unlock_attestation": "Baseline change does not unlock provider/odds/recommendation/production.",
        },
    }

    blockers = sorted(set(p128.get("blockers", [])))
    blockers.append("BASELINE_CHANGE_APPROVAL_REQUIRED_BLOCKER")
    blockers.append("FULL_REGRESSION_NOT_RUN_BLOCKER")
    blockers = sorted(set(blockers))

    final_classification = "P129_REPLAY_DRIFT_ALERT_CONTRACT_READY_WITH_BLOCKERS"
    if governance_fail:
        final_classification = "P129_REPLAY_DRIFT_ALERT_CONTRACT_FAILED_VALIDATION"

    summary = {
        "replay_drift_alert_contract_status": "READY_WITH_BLOCKERS",
        "source_replay_gate_status": p128.get("replay_consistency_gate_status", "UNKNOWN"),
        "source_replay_run_count": int(p128.get("replay_run_count", 0)),
        "source_fixture_count": int(p128.get("source_fixture_count", 0)),
        "source_baseline_fingerprint": p128.get("baseline_fingerprint", ""),
        "source_drift_detected": bool(p128.get("drift_detected", True)),
        "alert_level_definitions": ALERT_LEVEL_DEFINITIONS,
        "alert_escalation_rules": ALERT_ESCALATION_RULES,
        "blocking_conditions": BLOCKING_CONDITIONS,
        "baseline_hash_change_review_rules": baseline_hash_change_review_rules,
        "verdict_drift_rules": VERDICT_DRIFT_RULES,
        "blocked_reason_drift_rules": BLOCKED_REASON_DRIFT_RULES,
        "rule_matrix_drift_rules": RULE_MATRIX_DRIFT_RULES,
        "unlock_prevention_drift_rules": UNLOCK_PREVENTION_DRIFT_RULES,
        "fingerprint_drift_rules": FINGERPRINT_DRIFT_RULES,
        "reproducibility_metadata_drift_rules": REPRODUCIBILITY_METADATA_DRIFT_RULES,
        "drift_details_required_fields": DRIFT_DETAILS_REQUIRED_FIELDS,
        "governance_invariants": governance_invariants,
        "regression_status": {
            "targeted_p118_p129_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P129 task.",
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
        f.write("# P129 Replay Drift Alert Contract (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- replay_drift_alert_contract_status: {summary['replay_drift_alert_contract_status']}\n")
        f.write(f"- source_replay_gate_status: {summary['source_replay_gate_status']}\n")
        f.write(f"- source_replay_run_count: {summary['source_replay_run_count']}\n")
        f.write(f"- source_fixture_count: {summary['source_fixture_count']}\n")
        f.write(f"- source_drift_detected: {summary['source_drift_detected']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Alert Levels\n")
        for level, detail in summary["alert_level_definitions"].items():
            f.write(f"- {level}: {detail['condition']}\n")
        f.write("\n")

        f.write("## Blocking Conditions\n")
        for cond in summary["blocking_conditions"]:
            f.write(f"- {cond['condition_id']}: {cond['condition']} ({cond['alert_level']})\n")
        f.write("\n")

        f.write("## Baseline Hash Change Review Rules\n")
        f.write("- required_fields:\n")
        for field in summary["baseline_hash_change_review_rules"]["required_fields"]:
            f.write(f"  - {field}\n")
        f.write(f"- approval_policy: {summary['baseline_hash_change_review_rules']['approval_policy']}\n")
        f.write(
            f"- non_unlock_attestation_required: {summary['baseline_hash_change_review_rules']['non_unlock_attestation_required']}\n\n"
        )

        f.write("## Governance Invariants\n")
        for key, value in summary["governance_invariants"].items():
            f.write(f"- {key}: {value}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p129_tests_status: NOT_RUN\n")
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

    print(f"P129 contract summary written to {OUT_PATH}")
    print(f"P129 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
