# P126 Legal Evidence Intake Payload Fixture + Negative Gate Cases
# Paper-only fixture and negative-case gate verification. No provider/odds/production unlock.

import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P125_PATH = "data/mlb_2026/derived/p125_legal_evidence_intake_schema_review_owner_gate_summary.json"
OUT_PATH = "data/mlb_2026/derived/p126_legal_evidence_intake_payload_fixture_negative_cases_summary.json"
REPORT_PATH = "report/p126_legal_evidence_intake_payload_fixture_negative_cases_20260601.md"

NEGATIVE_CASES = [
    "VALID_SCHEMA_BUT_NOT_APPROVED_BLOCKED",
    "MISSING_LEGAL_DOCUMENT_REFERENCE_BLOCKED",
    "MISSING_REVIEW_OWNER_BLOCKED",
    "MISSING_APPROVAL_OWNER_BLOCKED",
    "REVIEW_STATUS_NOT_APPROVED_BLOCKED",
    "PLACEHOLDER_AS_EVIDENCE_BLOCKED",
    "PROVIDER_IDENTITY_MISSING_BLOCKED",
    "MARKET_SCOPE_MISSING_BLOCKED",
    "DATA_USAGE_SCOPE_MISSING_BLOCKED",
    "EFFECTIVE_DATE_MISSING_BLOCKED",
    "EXPIRATION_OR_RENEWAL_MISSING_BLOCKED",
    "SOURCE_TRACE_MISSING_BLOCKED",
    "AUDIT_TRAIL_MISSING_BLOCKED",
    "SECRET_OR_AUTH_URL_PRESENT_BLOCKED",
    "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKED",
    "ROW_LEVEL_PROPRIETARY_ODDS_PRESENT_BLOCKED",
    "RECOMMENDATION_UNLOCK_REQUEST_BLOCKED",
    "PRODUCTION_UNLOCK_REQUEST_BLOCKED",
    "EV_CLV_KELLY_UNLOCK_REQUEST_BLOCKED",
]

BLOCKED_REASON_MAP = {
    "VALID_SCHEMA_BUT_NOT_APPROVED_BLOCKED": [
        "PROVIDER_NOT_APPROVED_BLOCKER",
        "AUTHORIZATION_EVIDENCE_MISSING_BLOCKER",
    ],
    "MISSING_LEGAL_DOCUMENT_REFERENCE_BLOCKED": ["LEGAL_DOCUMENT_REFERENCE_MISSING_BLOCKER"],
    "MISSING_REVIEW_OWNER_BLOCKED": ["REVIEW_OWNER_MISSING_BLOCKER"],
    "MISSING_APPROVAL_OWNER_BLOCKED": ["APPROVAL_OWNER_MISSING_BLOCKER"],
    "REVIEW_STATUS_NOT_APPROVED_BLOCKED": ["REVIEW_STATUS_NOT_APPROVED_BLOCKER"],
    "PLACEHOLDER_AS_EVIDENCE_BLOCKED": ["PLACEHOLDER_DETECTED_BLOCKER"],
    "PROVIDER_IDENTITY_MISSING_BLOCKED": ["PROVIDER_IDENTITY_MISSING_BLOCKER"],
    "MARKET_SCOPE_MISSING_BLOCKED": ["MARKET_SCOPE_MISSING_BLOCKER"],
    "DATA_USAGE_SCOPE_MISSING_BLOCKED": ["DATA_USAGE_SCOPE_MISSING_BLOCKER"],
    "EFFECTIVE_DATE_MISSING_BLOCKED": ["EFFECTIVE_DATE_MISSING_BLOCKER"],
    "EXPIRATION_OR_RENEWAL_MISSING_BLOCKED": ["EXPIRATION_OR_RENEWAL_MISSING_BLOCKER"],
    "SOURCE_TRACE_MISSING_BLOCKED": ["SOURCE_TRACE_MISSING_BLOCKER"],
    "AUDIT_TRAIL_MISSING_BLOCKED": ["AUDIT_TRAIL_MISSING_BLOCKER"],
    "SECRET_OR_AUTH_URL_PRESENT_BLOCKED": ["SECRET_OR_AUTH_URL_DETECTED_BLOCKER"],
    "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKED": ["PRIVATE_CONTRACT_BODY_PRESENT_BLOCKER"],
    "ROW_LEVEL_PROPRIETARY_ODDS_PRESENT_BLOCKED": ["ROW_LEVEL_PROPRIETARY_ODDS_PRESENT_BLOCKER"],
    "RECOMMENDATION_UNLOCK_REQUEST_BLOCKED": ["RECOMMENDATION_UNLOCK_REQUEST_BLOCKER"],
    "PRODUCTION_UNLOCK_REQUEST_BLOCKED": ["PRODUCTION_UNLOCK_REQUEST_BLOCKER"],
    "EV_CLV_KELLY_UNLOCK_REQUEST_BLOCKED": ["EV_CLV_KELLY_UNLOCK_REQUEST_BLOCKER"],
}

PROHIBITED_ACTIONS = [
    "Do not approve provider from fixture-only payloads",
    "Do not unlock recommendation/EV/CLV/Kelly/stake/profit/production",
    "Do not ingest real legal odds or activate providers",
    "Do not store secret-like values, auth URLs, or private contract body in repo artifacts",
]

ALLOWED_NEXT_ACTIONS = [
    "Keep paper_only=true and diagnostic_only=true",
    "Use fixture results only for governance gate validation",
    "Collect real legal evidence through compliance workflow before any approval consideration",
    "Keep full regression explicitly PASS/FAIL/NOT_RUN",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_READY_WITH_BLOCKERS",
    "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_BLOCKED_BY_MISSING_P121_OR_P125",
    "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_valid_minimal_payload_template():
    return {
        "intake_id": "INTAKE_PLACEHOLDER_001",
        "evidence_type": "LEGAL_PROVIDER_AUTHORIZATION",
        "legal_document_reference_id": "<LEGAL_DOC_REFERENCE_REQUIRED>",
        "provider_legal_name": "<PROVIDER_LEGAL_NAME_REQUIRED>",
        "provider_identifier": "<PROVIDER_IDENTIFIER_REQUIRED>",
        "submitted_by": "<SUBMITTER_REQUIRED>",
        "submitted_at": "<ISO8601_REQUIRED>",
        "review_owner": "<REVIEW_OWNER_REQUIRED>",
        "review_status": "pending",
        "approval_owner": "<APPROVAL_OWNER_REQUIRED>",
        "authorized_sports": ["baseball"],
        "authorized_leagues": ["WBC"],
        "authorized_markets": ["moneyline_winner"],
        "authorized_data_types": ["odds_reference_metadata_only"],
        "authorized_usage_scope": "paper_only_research",
        "authorized_environment": "paper_only",
        "effective_date": "<EFFECTIVE_DATE_REQUIRED>",
        "expiration_date": "<EXPIRATION_DATE_REQUIRED>",
        "renewal_review_date": "<RENEWAL_REVIEW_DATE_REQUIRED>",
        "source_trace_reference": "<SOURCE_TRACE_REFERENCE_REQUIRED>",
        "audit_trail_reference": "<AUDIT_TRAIL_REFERENCE_REQUIRED>",
        "restriction_notes": "No recommendation/production unlock.",
        "repository_storage_policy": "No private legal body and no secrets in repo.",
        "secret_exclusion_attestation": True,
        "private_contract_body_excluded": True,
        "row_level_proprietary_odds_excluded": True,
    }


def build_negative_case_payload(case_id: str, base_payload: dict):
    payload = dict(base_payload)

    if case_id == "MISSING_LEGAL_DOCUMENT_REFERENCE_BLOCKED":
        payload.pop("legal_document_reference_id", None)
    elif case_id == "MISSING_REVIEW_OWNER_BLOCKED":
        payload.pop("review_owner", None)
    elif case_id == "MISSING_APPROVAL_OWNER_BLOCKED":
        payload.pop("approval_owner", None)
    elif case_id == "REVIEW_STATUS_NOT_APPROVED_BLOCKED":
        payload["review_status"] = "pending"
    elif case_id == "PLACEHOLDER_AS_EVIDENCE_BLOCKED":
        payload["legal_document_reference_id"] = "<REQUIRED FUTURE FIELD>"
    elif case_id == "PROVIDER_IDENTITY_MISSING_BLOCKED":
        payload.pop("provider_legal_name", None)
        payload.pop("provider_identifier", None)
    elif case_id == "MARKET_SCOPE_MISSING_BLOCKED":
        payload.pop("authorized_markets", None)
    elif case_id == "DATA_USAGE_SCOPE_MISSING_BLOCKED":
        payload.pop("authorized_usage_scope", None)
        payload.pop("authorized_environment", None)
    elif case_id == "EFFECTIVE_DATE_MISSING_BLOCKED":
        payload.pop("effective_date", None)
    elif case_id == "EXPIRATION_OR_RENEWAL_MISSING_BLOCKED":
        payload.pop("expiration_date", None)
        payload.pop("renewal_review_date", None)
    elif case_id == "SOURCE_TRACE_MISSING_BLOCKED":
        payload.pop("source_trace_reference", None)
    elif case_id == "AUDIT_TRAIL_MISSING_BLOCKED":
        payload.pop("audit_trail_reference", None)
    elif case_id == "SECRET_OR_AUTH_URL_PRESENT_BLOCKED":
        payload["api_key"] = "REAL_API_KEY_SHOULD_NOT_EXIST"
        payload["private_auth_url"] = "https://private-auth.example.com"
    elif case_id == "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKED":
        payload["private_contract_body"] = "PRIVATE CONTRACT CONTENT"
    elif case_id == "ROW_LEVEL_PROPRIETARY_ODDS_PRESENT_BLOCKED":
        payload["row_level_proprietary_odds"] = [{"market": "moneyline_winner", "odds": 1.95}]
    elif case_id == "RECOMMENDATION_UNLOCK_REQUEST_BLOCKED":
        payload["request_recommendation_unlock"] = True
    elif case_id == "PRODUCTION_UNLOCK_REQUEST_BLOCKED":
        payload["request_production_unlock"] = True
    elif case_id == "EV_CLV_KELLY_UNLOCK_REQUEST_BLOCKED":
        payload["request_ev_unlock"] = True
        payload["request_clv_unlock"] = True
        payload["request_kelly_unlock"] = True

    return payload


def main():
    missing = []
    if not Path(P121_PATH).exists():
        missing.append(P121_PATH)
    if not Path(P125_PATH).exists():
        missing.append(P125_PATH)

    if missing:
        out = {
            "fixture_metadata": {
                "fixture_version": "P126.20260601",
                "generated_at": "2026-06-01",
                "final_classification": "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_BLOCKED_BY_MISSING_P121_OR_P125",
            },
            "fixture_status": "BLOCKED",
            "negative_gate_case_status": "BLOCKED",
            "missing_artifacts": missing,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "prohibited_actions": PROHIBITED_ACTIONS,
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"P126 fixture summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p125 = load_json(P125_PATH)
    g121 = p121.get("governance_flags", {})

    template = build_valid_minimal_payload_template()
    negative_payloads = []
    expected_gate_results = []

    for case_id in NEGATIVE_CASES:
        payload = build_negative_case_payload(case_id, template)
        negative_payloads.append(
            {
                "case_id": case_id,
                "payload": payload,
            }
        )
        expected_gate_results.append(
            {
                "case_id": case_id,
                "expected_status": "BLOCKED",
                "expected_provider_approved": False,
                "expected_authorization_evidence_present": False,
                "expected_recommendation_unlock_allowed": False,
                "expected_production_unlock_allowed": False,
                "expected_real_legal_odds_ingested": False,
            }
        )

    placeholder_rejection_cases = [
        "PLACEHOLDER_AS_EVIDENCE_BLOCKED",
        "VALID_SCHEMA_BUT_NOT_APPROVED_BLOCKED",
    ]
    review_owner_failure_cases = [
        "MISSING_REVIEW_OWNER_BLOCKED",
        "REVIEW_STATUS_NOT_APPROVED_BLOCKED",
    ]
    approval_workflow_failure_cases = [
        "MISSING_APPROVAL_OWNER_BLOCKED",
        "REVIEW_STATUS_NOT_APPROVED_BLOCKED",
    ]
    legal_document_reference_failure_cases = [
        "MISSING_LEGAL_DOCUMENT_REFERENCE_BLOCKED",
        "PLACEHOLDER_AS_EVIDENCE_BLOCKED",
    ]
    scope_failure_cases = [
        "MARKET_SCOPE_MISSING_BLOCKED",
        "DATA_USAGE_SCOPE_MISSING_BLOCKED",
    ]
    date_failure_cases = [
        "EFFECTIVE_DATE_MISSING_BLOCKED",
        "EXPIRATION_OR_RENEWAL_MISSING_BLOCKED",
    ]
    source_trace_failure_cases = [
        "SOURCE_TRACE_MISSING_BLOCKED",
        "AUDIT_TRAIL_MISSING_BLOCKED",
    ]
    repository_safety_failure_cases = [
        "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKED",
        "ROW_LEVEL_PROPRIETARY_ODDS_PRESENT_BLOCKED",
    ]
    secret_detection_failure_cases = [
        "SECRET_OR_AUTH_URL_PRESENT_BLOCKED",
    ]
    unlock_request_failure_cases = [
        "RECOMMENDATION_UNLOCK_REQUEST_BLOCKED",
        "PRODUCTION_UNLOCK_REQUEST_BLOCKED",
        "EV_CLV_KELLY_UNLOCK_REQUEST_BLOCKED",
    ]

    governance_invariants = {
        "paper_only": bool(g121.get("paper_only", False)),
        "diagnostic_only": bool(g121.get("diagnostic_only", False)),
        "production_ready": bool(g121.get("production_ready", False)),
        "real_bet_allowed": bool(g121.get("real_bet_allowed", False)),
        "recommendation_allowed": bool(g121.get("recommendation_allowed", False)),
        "provider_approved": bool(g121.get("provider_approved", False)),
        "authorization_evidence_present": bool(g121.get("authorization_evidence_present", False)),
        "placeholder_allowed_as_authorization": False,
        "real_legal_odds_ingested": bool(g121.get("odds_ingested", False)),
        "live_api_calls": int(g121.get("live_api_calls", 0)),
        "paid_api_called": int(g121.get("paid_api_calls", 0)) > 0,
        "ev_computed": bool(g121.get("ev_computed", False)),
        "clv_computed": bool(g121.get("clv_computed", False)),
        "kelly_computed": bool(g121.get("kelly_computed", False)),
        "stake_sizing": bool(g121.get("stake_sizing", False)),
        "profit_computed": bool(g121.get("profit_computed", False)),
        "recommendation_generated": bool(g121.get("recommendation_generated", False)),
    }

    blockers = sorted({b for arr in BLOCKED_REASON_MAP.values() for b in arr})
    blockers.append("FULL_REGRESSION_NOT_RUN_BLOCKER")

    final_classification = "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_READY_WITH_BLOCKERS"
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
    if hard_fail:
        final_classification = "P126_LEGAL_EVIDENCE_INTAKE_PAYLOAD_FIXTURE_NEGATIVE_CASES_FAILED_VALIDATION"

    summary = {
        "fixture_metadata": {
            "fixture_version": "P126.20260601",
            "generated_at": "2026-06-01",
            "source_p121_reference": P121_PATH,
            "source_p125_reference": P125_PATH,
            "source_p125_final_classification": p125.get("gate_metadata", {}).get("final_classification", "UNKNOWN"),
            "final_classification": final_classification,
        },
        "fixture_status": "READY_WITH_BLOCKERS",
        "negative_gate_case_status": "BLOCKED",
        "valid_minimal_payload_template": template,
        "negative_cases": negative_payloads,
        "expected_gate_results": expected_gate_results,
        "blocked_reason_matrix": BLOCKED_REASON_MAP,
        "placeholder_rejection_cases": placeholder_rejection_cases,
        "review_owner_failure_cases": review_owner_failure_cases,
        "approval_workflow_failure_cases": approval_workflow_failure_cases,
        "legal_document_reference_failure_cases": legal_document_reference_failure_cases,
        "scope_failure_cases": scope_failure_cases,
        "date_failure_cases": date_failure_cases,
        "source_trace_failure_cases": source_trace_failure_cases,
        "repository_safety_failure_cases": repository_safety_failure_cases,
        "secret_detection_failure_cases": secret_detection_failure_cases,
        "unlock_request_failure_cases": unlock_request_failure_cases,
        "governance_invariants": governance_invariants,
        "regression_status": {
            "targeted_p118_p125_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": p125.get("regression_status", {}).get("full_regression_evidence", "No full regression evidence provided."),
        },
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": blockers,
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P126 Legal Evidence Intake Payload Fixture + Negative Gate Cases (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- fixture_status: {summary['fixture_status']}\n")
        f.write(f"- negative_gate_case_status: {summary['negative_gate_case_status']}\n")
        f.write(f"- final_classification: {summary['fixture_metadata']['final_classification']}\n\n")

        f.write("## Case Counts\n")
        f.write(f"- total_negative_cases: {len(summary['negative_cases'])}\n")
        f.write(f"- expected_blocked_cases: {len(summary['expected_gate_results'])}\n\n")

        f.write("## Governance Invariants\n")
        for k, v in summary["governance_invariants"].items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## Required Negative Cases\n")
        for case in NEGATIVE_CASES:
            f.write(f"- {case}: BLOCKED\n")

        f.write("\n## Category Buckets\n")
        for key in (
            "placeholder_rejection_cases",
            "review_owner_failure_cases",
            "approval_workflow_failure_cases",
            "legal_document_reference_failure_cases",
            "scope_failure_cases",
            "date_failure_cases",
            "source_trace_failure_cases",
            "repository_safety_failure_cases",
            "secret_detection_failure_cases",
            "unlock_request_failure_cases",
        ):
            f.write(f"- {key}:\n")
            for item in summary[key]:
                f.write(f"  - {item}\n")

        f.write("\n## Regression/Test Status\n")
        for k, v in summary["regression_status"].items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## Blockers\n")
        for b in summary["blockers"]:
            f.write(f"- {b}\n")

        f.write("\n## Prohibited Actions\n")
        for a in summary["prohibited_actions"]:
            f.write(f"- {a}\n")

        f.write("\n## Allowed Next Actions\n")
        for a in summary["allowed_next_actions"]:
            f.write(f"- {a}\n")

    print(f"P126 fixture summary written to {OUT_PATH}")
    print(f"P126 fixture report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
