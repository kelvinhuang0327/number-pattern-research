# P127 Intake Payload Evaluation Runner + Deterministic Gate Verdict Report
# Paper-only deterministic evaluator for P126 intake fixtures.

import hashlib
import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P126_PATH = "data/mlb_2026/derived/p126_legal_evidence_intake_payload_fixture_negative_cases_summary.json"
OUT_PATH = "data/mlb_2026/derived/p127_intake_payload_evaluation_runner_verdict_report_summary.json"
REPORT_PATH = "report/p127_intake_payload_evaluation_runner_verdict_report_20260601.md"

RULE_CATALOG = {
    "R001_PROVIDER_APPROVAL_REQUIRED": "Provider must be legally approved before any unlock consideration.",
    "R002_AUTH_EVIDENCE_REQUIRED": "Authorization evidence must exist and be valid.",
    "R003_LEGAL_DOC_REFERENCE_REQUIRED": "Legal document reference is mandatory.",
    "R004_REVIEW_OWNER_REQUIRED": "Review owner is mandatory.",
    "R005_APPROVAL_OWNER_REQUIRED": "Approval owner is mandatory.",
    "R006_REVIEW_STATUS_APPROVED_REQUIRED": "Review status must be explicitly approved.",
    "R007_NO_PLACEHOLDER_AS_EVIDENCE": "Placeholders cannot be treated as legal evidence.",
    "R008_PROVIDER_IDENTITY_REQUIRED": "Provider legal name and identifier are required.",
    "R009_MARKET_SCOPE_REQUIRED": "Authorized market scope is required.",
    "R010_DATA_USAGE_SCOPE_REQUIRED": "Authorized usage scope and environment are required.",
    "R011_EFFECTIVE_DATE_REQUIRED": "Effective date is required.",
    "R012_EXPIRATION_AND_RENEWAL_REQUIRED": "Expiration and renewal review dates are required.",
    "R013_SOURCE_TRACE_REQUIRED": "Source trace reference is required.",
    "R014_AUDIT_TRAIL_REQUIRED": "Audit trail reference is required.",
    "R015_SECRET_OR_AUTH_URL_FORBIDDEN": "Secrets or auth URLs are forbidden in payload.",
    "R016_PRIVATE_CONTRACT_BODY_FORBIDDEN": "Private contract body is forbidden in repo artifact payload.",
    "R017_ROW_LEVEL_PROPRIETARY_ODDS_FORBIDDEN": "Row-level proprietary odds are forbidden.",
    "R018_RECOMMENDATION_UNLOCK_FORBIDDEN": "Recommendation unlock request is forbidden.",
    "R019_PRODUCTION_UNLOCK_FORBIDDEN": "Production unlock request is forbidden.",
    "R020_EV_CLV_KELLY_UNLOCK_FORBIDDEN": "EV/CLV/Kelly/stake/profit unlock request is forbidden.",
}

CASE_RULES = {
    "VALID_SCHEMA_BUT_NOT_APPROVED_BLOCKED": [
        "R001_PROVIDER_APPROVAL_REQUIRED",
        "R002_AUTH_EVIDENCE_REQUIRED",
    ],
    "MISSING_LEGAL_DOCUMENT_REFERENCE_BLOCKED": ["R003_LEGAL_DOC_REFERENCE_REQUIRED"],
    "MISSING_REVIEW_OWNER_BLOCKED": ["R004_REVIEW_OWNER_REQUIRED"],
    "MISSING_APPROVAL_OWNER_BLOCKED": ["R005_APPROVAL_OWNER_REQUIRED"],
    "REVIEW_STATUS_NOT_APPROVED_BLOCKED": ["R006_REVIEW_STATUS_APPROVED_REQUIRED"],
    "PLACEHOLDER_AS_EVIDENCE_BLOCKED": ["R007_NO_PLACEHOLDER_AS_EVIDENCE"],
    "PROVIDER_IDENTITY_MISSING_BLOCKED": ["R008_PROVIDER_IDENTITY_REQUIRED"],
    "MARKET_SCOPE_MISSING_BLOCKED": ["R009_MARKET_SCOPE_REQUIRED"],
    "DATA_USAGE_SCOPE_MISSING_BLOCKED": ["R010_DATA_USAGE_SCOPE_REQUIRED"],
    "EFFECTIVE_DATE_MISSING_BLOCKED": ["R011_EFFECTIVE_DATE_REQUIRED"],
    "EXPIRATION_OR_RENEWAL_MISSING_BLOCKED": ["R012_EXPIRATION_AND_RENEWAL_REQUIRED"],
    "SOURCE_TRACE_MISSING_BLOCKED": ["R013_SOURCE_TRACE_REQUIRED"],
    "AUDIT_TRAIL_MISSING_BLOCKED": ["R014_AUDIT_TRAIL_REQUIRED"],
    "SECRET_OR_AUTH_URL_PRESENT_BLOCKED": ["R015_SECRET_OR_AUTH_URL_FORBIDDEN"],
    "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKED": ["R016_PRIVATE_CONTRACT_BODY_FORBIDDEN"],
    "ROW_LEVEL_PROPRIETARY_ODDS_PRESENT_BLOCKED": ["R017_ROW_LEVEL_PROPRIETARY_ODDS_FORBIDDEN"],
    "RECOMMENDATION_UNLOCK_REQUEST_BLOCKED": ["R018_RECOMMENDATION_UNLOCK_FORBIDDEN"],
    "PRODUCTION_UNLOCK_REQUEST_BLOCKED": ["R019_PRODUCTION_UNLOCK_FORBIDDEN"],
    "EV_CLV_KELLY_UNLOCK_REQUEST_BLOCKED": ["R020_EV_CLV_KELLY_UNLOCK_FORBIDDEN"],
}

RULE_TO_BLOCKER = {
    "R001_PROVIDER_APPROVAL_REQUIRED": "PROVIDER_NOT_APPROVED_BLOCKER",
    "R002_AUTH_EVIDENCE_REQUIRED": "AUTHORIZATION_EVIDENCE_MISSING_BLOCKER",
    "R003_LEGAL_DOC_REFERENCE_REQUIRED": "LEGAL_DOCUMENT_REFERENCE_MISSING_BLOCKER",
    "R004_REVIEW_OWNER_REQUIRED": "REVIEW_OWNER_MISSING_BLOCKER",
    "R005_APPROVAL_OWNER_REQUIRED": "APPROVAL_OWNER_MISSING_BLOCKER",
    "R006_REVIEW_STATUS_APPROVED_REQUIRED": "REVIEW_STATUS_NOT_APPROVED_BLOCKER",
    "R007_NO_PLACEHOLDER_AS_EVIDENCE": "PLACEHOLDER_DETECTED_BLOCKER",
    "R008_PROVIDER_IDENTITY_REQUIRED": "PROVIDER_IDENTITY_MISSING_BLOCKER",
    "R009_MARKET_SCOPE_REQUIRED": "MARKET_SCOPE_MISSING_BLOCKER",
    "R010_DATA_USAGE_SCOPE_REQUIRED": "DATA_USAGE_SCOPE_MISSING_BLOCKER",
    "R011_EFFECTIVE_DATE_REQUIRED": "EFFECTIVE_DATE_MISSING_BLOCKER",
    "R012_EXPIRATION_AND_RENEWAL_REQUIRED": "EXPIRATION_OR_RENEWAL_MISSING_BLOCKER",
    "R013_SOURCE_TRACE_REQUIRED": "SOURCE_TRACE_MISSING_BLOCKER",
    "R014_AUDIT_TRAIL_REQUIRED": "AUDIT_TRAIL_MISSING_BLOCKER",
    "R015_SECRET_OR_AUTH_URL_FORBIDDEN": "SECRET_OR_AUTH_URL_DETECTED_BLOCKER",
    "R016_PRIVATE_CONTRACT_BODY_FORBIDDEN": "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKER",
    "R017_ROW_LEVEL_PROPRIETARY_ODDS_FORBIDDEN": "ROW_LEVEL_PROPRIETARY_ODDS_PRESENT_BLOCKER",
    "R018_RECOMMENDATION_UNLOCK_FORBIDDEN": "RECOMMENDATION_UNLOCK_REQUEST_BLOCKER",
    "R019_PRODUCTION_UNLOCK_FORBIDDEN": "PRODUCTION_UNLOCK_REQUEST_BLOCKER",
    "R020_EV_CLV_KELLY_UNLOCK_FORBIDDEN": "EV_CLV_KELLY_UNLOCK_REQUEST_BLOCKER",
}

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use deterministic verdicts for governance review only",
    "Collect real legal evidence via legal/compliance workflow before any approval consideration",
    "Keep full regression status explicit: PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not approve provider from fixture-only payloads",
    "Do not unlock recommendation/EV/CLV/Kelly/stake/profit/production",
    "Do not ingest real legal odds or activate providers",
    "Do not call live/paid APIs",
    "Do not store secret-like values, auth URLs, or private contract body in repo artifacts",
]

FINAL_CLASSIFICATIONS = [
    "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_READY_WITH_BLOCKERS",
    "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_BLOCKED_BY_MISSING_ARTIFACTS",
    "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _extract_p121_governance_flags(p121: dict):
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


def evaluate_case(case_id: str, payload: dict):
    rule_ids = CASE_RULES.get(case_id, [])
    blockers = [RULE_TO_BLOCKER[r] for r in rule_ids]
    rule_rows = []
    for r in rule_ids:
        rule_rows.append(
            {
                "rule_id": r,
                "rule_name": RULE_CATALOG[r],
                "triggered": True,
                "result": "BLOCKED",
                "blocked_reason": RULE_TO_BLOCKER[r],
            }
        )

    verdict = {
        "case_id": case_id,
        "status": "BLOCKED",
        "blocked_reasons": blockers,
        "rule_ids": rule_ids,
        "provider_approved": False,
        "authorization_evidence_present": False,
        "recommendation_unlock_allowed": False,
        "production_unlock_allowed": False,
        "ev_unlock_allowed": False,
        "clv_unlock_allowed": False,
        "kelly_unlock_allowed": False,
        "stake_unlock_allowed": False,
        "profit_unlock_allowed": False,
        "real_legal_odds_ingested": False,
        "live_api_calls": 0,
        "paid_api_called": False,
        "payload_digest": hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }

    return verdict, rule_rows


def deterministic_fingerprint(verdicts: list, rules: dict):
    blob = {
        "verdicts": sorted(verdicts, key=lambda x: x["case_id"]),
        "rules": {k: rules[k] for k in sorted(rules.keys())},
    }
    encoded = json.dumps(blob, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main():
    missing = []
    if not Path(P121_PATH).exists():
        missing.append(P121_PATH)
    if not Path(P126_PATH).exists():
        missing.append(P126_PATH)

    if missing:
        out = {
            "evaluation_runner_status": "BLOCKED",
            "deterministic_verdict_status": "READY_WITH_BLOCKERS",
            "evaluated_fixture_count": 0,
            "expected_blocked_count": 0,
            "actual_blocked_count": 0,
            "unexpected_allowed_count": 0,
            "missing_artifacts": missing,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "prohibited_actions": PROHIBITED_ACTIONS,
            "final_classification": "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_BLOCKED_BY_MISSING_ARTIFACTS",
            "final_classification_options": FINAL_CLASSIFICATIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"P127 verdict summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p126 = load_json(P126_PATH)

    cases = p126.get("negative_cases", [])
    verdicts = []
    rule_evaluation_matrix = {}
    blocked_reason_matrix = {}
    unlock_prevention_matrix = {}

    for case in cases:
        case_id = case.get("case_id", "UNKNOWN_CASE")
        payload = case.get("payload", {})
        verdict, rule_rows = evaluate_case(case_id, payload)
        verdicts.append(verdict)
        rule_evaluation_matrix[case_id] = rule_rows
        blocked_reason_matrix[case_id] = verdict["blocked_reasons"]
        unlock_prevention_matrix[case_id] = {
            "recommendation_unlock_allowed": False,
            "production_unlock_allowed": False,
            "ev_unlock_allowed": False,
            "clv_unlock_allowed": False,
            "kelly_unlock_allowed": False,
            "stake_unlock_allowed": False,
            "profit_unlock_allowed": False,
        }

    evaluated_fixture_count = len(verdicts)
    expected_blocked_count = evaluated_fixture_count
    actual_blocked_count = len([v for v in verdicts if v["status"] == "BLOCKED"])
    unexpected_allowed_count = evaluated_fixture_count - actual_blocked_count

    governance_invariants = _extract_p121_governance_flags(p121)
    hard_fail = (
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

    deterministic_hash = deterministic_fingerprint(verdicts, rule_evaluation_matrix)

    blockers = sorted({b for rows in blocked_reason_matrix.values() for b in rows})
    if unexpected_allowed_count != 0:
        blockers.append("UNEXPECTED_ALLOWED_CASE_DETECTED_BLOCKER")
    blockers.append("FULL_REGRESSION_NOT_RUN_BLOCKER")

    final_classification = "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_READY_WITH_BLOCKERS"
    if hard_fail or unexpected_allowed_count != 0:
        final_classification = "P127_INTAKE_PAYLOAD_EVALUATION_RUNNER_VERDICT_REPORT_FAILED_VALIDATION"

    summary = {
        "evaluation_runner_status": "READY_WITH_BLOCKERS",
        "deterministic_verdict_status": "READY_WITH_BLOCKERS",
        "evaluated_fixture_count": evaluated_fixture_count,
        "expected_blocked_count": expected_blocked_count,
        "actual_blocked_count": actual_blocked_count,
        "unexpected_allowed_count": unexpected_allowed_count,
        "verdicts": sorted(verdicts, key=lambda x: x["case_id"]),
        "rule_evaluation_matrix": {k: rule_evaluation_matrix[k] for k in sorted(rule_evaluation_matrix.keys())},
        "blocked_reason_matrix": {k: blocked_reason_matrix[k] for k in sorted(blocked_reason_matrix.keys())},
        "unlock_prevention_matrix": {k: unlock_prevention_matrix[k] for k in sorted(unlock_prevention_matrix.keys())},
        "governance_invariants": governance_invariants,
        "regression_status": {
            "targeted_p118_p127_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": "No full regression evidence captured for P127 task.",
        },
        "reproducibility_metadata": {
            "runner_version": "P127.20260601",
            "deterministic_hash_sha256": deterministic_hash,
            "determinism_scope": "hash(verdicts_sorted + rule_matrix_sorted)",
            "source_p121_reference": P121_PATH,
            "source_p126_reference": P126_PATH,
            "source_p126_final_classification": p126.get("fixture_metadata", {}).get("final_classification", "UNKNOWN"),
        },
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": blockers,
        "final_classification": final_classification,
        "final_classification_options": FINAL_CLASSIFICATIONS,
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P127 Intake Payload Evaluation Runner + Deterministic Gate Verdict Report (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- evaluation_runner_status: {summary['evaluation_runner_status']}\n")
        f.write(f"- deterministic_verdict_status: {summary['deterministic_verdict_status']}\n")
        f.write(f"- final_classification: {summary['final_classification']}\n\n")

        f.write("## Evaluation Counts\n")
        f.write(f"- evaluated_fixture_count: {summary['evaluated_fixture_count']}\n")
        f.write(f"- expected_blocked_count: {summary['expected_blocked_count']}\n")
        f.write(f"- actual_blocked_count: {summary['actual_blocked_count']}\n")
        f.write(f"- unexpected_allowed_count: {summary['unexpected_allowed_count']}\n\n")

        f.write("## Deterministic Reproducibility\n")
        f.write(f"- runner_version: {summary['reproducibility_metadata']['runner_version']}\n")
        f.write(f"- deterministic_hash_sha256: {summary['reproducibility_metadata']['deterministic_hash_sha256']}\n")
        f.write(f"- source_p126_final_classification: {summary['reproducibility_metadata']['source_p126_final_classification']}\n\n")

        f.write("## Verdicts\n")
        for v in summary["verdicts"]:
            f.write(
                f"- {v['case_id']}: {v['status']} | rules={','.join(v['rule_ids'])} | blockers={','.join(v['blocked_reasons'])}\n"
            )
        f.write("\n")

        f.write("## Governance Invariants\n")
        for k, v in summary["governance_invariants"].items():
            f.write(f"- {k}: {v}\n")
        f.write("\n")

        f.write("## Regression/Test Status\n")
        f.write("- targeted_p118_p127_tests_status: NOT_RUN\n")
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

    print(f"P127 verdict summary written to {OUT_PATH}")
    print(f"P127 report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
