# P124 Legal Evidence Completeness Contract
# Defines paper-only legal evidence completeness requirements for future authorization validation.

import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P123_PATH = "data/mlb_2026/derived/p123_provider_evidence_validation_gate_summary.json"
OUT_PATH = "data/mlb_2026/derived/p124_legal_evidence_completeness_contract_summary.json"
REPORT_PATH = "report/p124_legal_evidence_completeness_contract_20260601.md"

REQUIRED_LEGAL_DOCUMENT_FIELDS = [
    "legal_document_reference_id",
    "legal_document_external_reference",
    "legal_document_type",
    "legal_document_review_status",
]

REQUIRED_LICENSE_SCOPE_FIELDS = [
    "license_scope_id",
    "license_status",
    "authorized_data_types",
    "authorized_usage_scope",
]

REQUIRED_MARKET_SCOPE_FIELDS = [
    "authorized_sports",
    "authorized_leagues_or_competitions",
    "authorized_markets",
    "market_scope_restrictions",
]

REQUIRED_SOURCE_TRACE_FIELDS = [
    "provider_id",
    "source_trace_id",
    "source_reference_system",
    "evidence_traceability_reference",
]

REQUIRED_AUDIT_FIELDS = [
    "audit_log_policy_reference",
    "audit_owner",
    "audit_review_frequency",
    "audit_evidence_reference",
]

REQUIRED_EFFECTIVE_DATE_FIELDS = [
    "effective_date",
]

REQUIRED_EXPIRATION_OR_RENEWAL_FIELDS = [
    "expiration_date",
    "renewal_review_required",
    "renewal_review_date",
]

REQUIRED_PROVIDER_IDENTITY_FIELDS = [
    "provider_legal_name",
    "provider_registration_reference",
    "provider_approval_status",
]

REQUIRED_DATA_USAGE_SCOPE_FIELDS = [
    "authorized_environment_scope",
    "authorized_workload_scope",
    "authorized_region_scope",
]

REQUIRED_RESTRICTION_FIELDS = [
    "restriction_notes",
    "prohibited_usage_notes",
    "row_level_proprietary_odds_policy",
]

REQUIRED_SECRET_EXCLUSION_RULES = [
    "no_secrets_in_repo",
    "no_api_keys_in_repo",
    "no_auth_urls_in_repo",
    "no_private_contract_body_in_repo",
    "no_credentials_or_tokens_in_repo",
]

REQUIRED_REPOSITORY_SAFETY_RULES = [
    "paper_only_mode_required",
    "diagnostic_only_mode_required",
    "production_unlock_forbidden_without_approval",
    "recommendation_unlock_forbidden_without_approval",
    "no_row_level_proprietary_odds_commit_without_separate_data_rights_decision",
]

BLOCKERS = [
    "LEGAL_DOCUMENT_REFERENCE_MISSING_BLOCKER",
    "PROVIDER_IDENTITY_MISSING_BLOCKER",
    "LICENSE_SCOPE_MISSING_BLOCKER",
    "MARKET_SCOPE_MISSING_BLOCKER",
    "DATA_USAGE_SCOPE_MISSING_BLOCKER",
    "EFFECTIVE_DATE_MISSING_BLOCKER",
    "EXPIRATION_OR_RENEWAL_FIELD_MISSING_BLOCKER",
    "APPROVAL_OWNER_MISSING_BLOCKER",
    "AUDIT_OR_SOURCE_TRACE_MISSING_BLOCKER",
    "PLACEHOLDER_DETECTED_BLOCKER",
    "SECRET_OR_AUTH_URL_DETECTED_BLOCKER",
    "PRODUCTION_OR_RECOMMENDATION_UNLOCK_WITHOUT_APPROVAL_BLOCKER",
    "FULL_REGRESSION_NOT_RUN_BLOCKER",
]

PROHIBITED_ACTIONS = [
    "Do not treat placeholder evidence as complete legal authorization evidence",
    "Do not store private contract body, API keys, tokens, credentials, or auth URLs in repo",
    "Do not commit row-level proprietary odds data without separate data-rights decision",
    "Do not unlock recommendation, EV, CLV, Kelly, stake, profit, or production without explicit legal/provider approval",
]

ALLOWED_NEXT_ACTIONS = [
    "Maintain paper_only=true and diagnostic_only=true",
    "Collect legal evidence metadata references (not private content) through compliance workflow",
    "Validate completeness fields and reviewer ownership before any approval attempt",
    "Keep full regression status explicitly PASS/FAIL/NOT_RUN in artifacts",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_READY_WITH_BLOCKERS",
    "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_BLOCKED_BY_MISSING_P121_OR_P123",
    "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    missing = []
    if not Path(P121_PATH).exists():
        missing.append(P121_PATH)
    if not Path(P123_PATH).exists():
        missing.append(P123_PATH)

    if missing:
        out = {
            "contract_metadata": {
                "contract_version": "P124.20260601",
                "generated_at": "2026-06-01",
                "final_classification": "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_BLOCKED_BY_MISSING_P121_OR_P123",
            },
            "legal_evidence_contract_status": "BLOCKED",
            "missing_artifacts": missing,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "prohibited_actions": PROHIBITED_ACTIONS,
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"P124 contract summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p123 = load_json(P123_PATH)

    g121 = p121.get("governance_flags", {})

    provider_approved = bool(g121.get("provider_approved", False))
    authorization_evidence_present = bool(g121.get("authorization_evidence_present", False))
    placeholder_detected = bool(p123.get("placeholder_detected", True))
    placeholder_allowed_as_authorization = bool(p123.get("placeholder_allowed_as_authorization", False))
    real_legal_odds_ingested = bool(g121.get("odds_ingested", False))
    recommendation_allowed = bool(g121.get("recommendation_allowed", False))
    production_ready = bool(g121.get("production_ready", False))

    completeness_validation_rules = {
        "must_have_legal_document_reference": True,
        "must_have_provider_identity": True,
        "must_have_license_scope": True,
        "must_have_market_scope": True,
        "must_have_data_usage_scope": True,
        "must_have_effective_date": True,
        "must_have_expiration_or_renewal": True,
        "must_have_approval_owner": True,
        "must_have_audit_and_source_trace": True,
        "must_reject_placeholder_as_authorization": True,
        "must_reject_secret_or_auth_url_in_repo": True,
        "must_block_unlock_without_explicit_approval": True,
    }

    placeholder_rejection_rules = {
        "placeholder_detected_means_blocked": True,
        "placeholder_allowed_as_authorization_must_be_false": True,
        "placeholder_only_evidence_cannot_set_provider_approved": True,
        "placeholder_only_evidence_cannot_set_authorization_evidence_present": True,
    }

    governance_invariants = {
        "paper_only": bool(g121.get("paper_only", False)),
        "diagnostic_only": bool(g121.get("diagnostic_only", False)),
        "production_ready": production_ready,
        "real_bet_allowed": bool(g121.get("real_bet_allowed", False)),
        "recommendation_allowed": recommendation_allowed,
        "provider_approved": provider_approved,
        "authorization_evidence_present": authorization_evidence_present,
        "placeholder_allowed_as_authorization": placeholder_allowed_as_authorization,
        "real_legal_odds_ingested": real_legal_odds_ingested,
        "live_api_calls": int(g121.get("live_api_calls", 0)),
        "paid_api_called": int(g121.get("paid_api_calls", 0)) > 0,
        "ev_computed": bool(g121.get("ev_computed", False)),
        "clv_computed": bool(g121.get("clv_computed", False)),
        "kelly_computed": bool(g121.get("kelly_computed", False)),
        "stake_sizing": bool(g121.get("stake_sizing", False)),
        "profit_computed": bool(g121.get("profit_computed", False)),
        "recommendation_generated": bool(g121.get("recommendation_generated", False)),
    }

    blockers = list(BLOCKERS)

    final_classification = "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_READY_WITH_BLOCKERS"
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
        final_classification = "P124_LEGAL_EVIDENCE_COMPLETENESS_CONTRACT_FAILED_VALIDATION"

    summary = {
        "contract_metadata": {
            "contract_version": "P124.20260601",
            "generated_at": "2026-06-01",
            "source_p121_reference": P121_PATH,
            "source_p123_reference": P123_PATH,
            "final_classification": final_classification,
        },
        "legal_evidence_contract_status": "READY_WITH_BLOCKERS",
        "required_legal_document_fields": REQUIRED_LEGAL_DOCUMENT_FIELDS,
        "required_license_scope_fields": REQUIRED_LICENSE_SCOPE_FIELDS,
        "required_market_scope_fields": REQUIRED_MARKET_SCOPE_FIELDS,
        "required_source_trace_fields": REQUIRED_SOURCE_TRACE_FIELDS,
        "required_audit_fields": REQUIRED_AUDIT_FIELDS,
        "required_effective_date_fields": REQUIRED_EFFECTIVE_DATE_FIELDS,
        "required_expiration_or_renewal_fields": REQUIRED_EXPIRATION_OR_RENEWAL_FIELDS,
        "required_provider_identity_fields": REQUIRED_PROVIDER_IDENTITY_FIELDS,
        "required_data_usage_scope_fields": REQUIRED_DATA_USAGE_SCOPE_FIELDS,
        "required_restriction_fields": REQUIRED_RESTRICTION_FIELDS,
        "required_secret_exclusion_rules": REQUIRED_SECRET_EXCLUSION_RULES,
        "required_repository_safety_rules": REQUIRED_REPOSITORY_SAFETY_RULES,
        "completeness_validation_rules": completeness_validation_rules,
        "placeholder_rejection_rules": placeholder_rejection_rules,
        "provider_approved": provider_approved,
        "authorization_evidence_present": authorization_evidence_present,
        "placeholder_detected": placeholder_detected,
        "placeholder_allowed_as_authorization": placeholder_allowed_as_authorization,
        "real_legal_odds_ingested": real_legal_odds_ingested,
        "governance_invariants": governance_invariants,
        "regression_status": {
            "targeted_p118_p123_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": p123.get("regression_status", {}).get("full_regression_evidence", "No full regression evidence provided."),
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
        f.write("# P124 Legal Evidence Completeness Contract (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- legal_evidence_contract_status: {summary['legal_evidence_contract_status']}\n")
        f.write(f"- final_classification: {summary['contract_metadata']['final_classification']}\n\n")

        f.write("## Core Contract Outputs\n")
        f.write(f"- provider_approved: {summary['provider_approved']}\n")
        f.write(f"- authorization_evidence_present: {summary['authorization_evidence_present']}\n")
        f.write(f"- placeholder_detected: {summary['placeholder_detected']}\n")
        f.write(f"- placeholder_allowed_as_authorization: {summary['placeholder_allowed_as_authorization']}\n")
        f.write(f"- real_legal_odds_ingested: {summary['real_legal_odds_ingested']}\n\n")

        f.write("## Governance Invariants\n")
        for k, v in summary["governance_invariants"].items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## Required Contract Field Groups\n")
        for key in (
            "required_legal_document_fields",
            "required_license_scope_fields",
            "required_market_scope_fields",
            "required_source_trace_fields",
            "required_audit_fields",
            "required_effective_date_fields",
            "required_expiration_or_renewal_fields",
            "required_provider_identity_fields",
            "required_data_usage_scope_fields",
            "required_restriction_fields",
            "required_secret_exclusion_rules",
            "required_repository_safety_rules",
        ):
            f.write(f"- {key}:\n")
            for item in summary[key]:
                f.write(f"  - {item}\n")

        f.write("\n## Completeness Validation Rules\n")
        for k, v in summary["completeness_validation_rules"].items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## Placeholder Rejection Rules\n")
        for k, v in summary["placeholder_rejection_rules"].items():
            f.write(f"- {k}: {v}\n")

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

    print(f"P124 contract summary written to {OUT_PATH}")
    print(f"P124 contract report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
