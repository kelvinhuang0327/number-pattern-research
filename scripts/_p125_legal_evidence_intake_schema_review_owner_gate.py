# P125 Legal Evidence Intake Schema + Review Owner Gate
# Paper-only schema and governance gate. No provider unlock, no odds ingestion, no production logic.

import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P124_PATH = "data/mlb_2026/derived/p124_legal_evidence_completeness_contract_summary.json"
OUT_PATH = "data/mlb_2026/derived/p125_legal_evidence_intake_schema_review_owner_gate_summary.json"
REPORT_PATH = "report/p125_legal_evidence_intake_schema_review_owner_gate_20260601.md"

REQUIRED_INTAKE_FIELDS = [
    "intake_id",
    "evidence_type",
    "legal_document_reference_id",
    "provider_legal_name",
    "provider_identifier",
    "submitted_by",
    "submitted_at",
    "review_owner",
    "review_status",
    "approval_owner",
    "authorized_sports",
    "authorized_leagues",
    "authorized_markets",
    "authorized_data_types",
    "authorized_usage_scope",
    "authorized_environment",
    "effective_date",
    "expiration_date",
    "renewal_review_date",
    "source_trace_reference",
    "audit_trail_reference",
    "restriction_notes",
    "repository_storage_policy",
    "secret_exclusion_attestation",
    "private_contract_body_excluded",
    "row_level_proprietary_odds_excluded",
]

REQUIRED_REVIEW_OWNER_FIELDS = [
    "review_owner",
    "review_owner_role",
    "review_owner_identity_reference",
    "review_owner_attested_at",
    "review_status",
]

REQUIRED_APPROVAL_WORKFLOW_FIELDS = [
    "approval_owner",
    "approval_status",
    "approval_decision_at",
    "approval_decision_reference",
    "approval_scope_attestation",
]

REQUIRED_LEGAL_DOCUMENT_REFERENCE_FIELDS = [
    "legal_document_reference_id",
    "legal_document_external_reference",
    "legal_document_type",
    "legal_document_review_status",
]

REQUIRED_SCOPE_FIELDS = [
    "authorized_sports",
    "authorized_leagues",
    "authorized_markets",
    "authorized_data_types",
    "authorized_usage_scope",
    "authorized_environment",
]

REQUIRED_DATE_FIELDS = [
    "effective_date",
    "expiration_date",
    "renewal_review_date",
]

REQUIRED_PROVIDER_IDENTITY_FIELDS = [
    "provider_legal_name",
    "provider_identifier",
    "provider_approval_status",
]

REQUIRED_DATA_RIGHTS_FIELDS = [
    "row_level_proprietary_odds_excluded",
    "separate_data_rights_decision_reference",
    "repository_storage_policy",
]

REQUIRED_REPOSITORY_SAFETY_FIELDS = [
    "paper_only_required",
    "diagnostic_only_required",
    "no_recommendation_unlock_without_approval",
    "no_production_unlock_without_approval",
]

REQUIRED_SECRET_EXCLUSION_FIELDS = [
    "secret_exclusion_attestation",
    "private_contract_body_excluded",
    "no_api_key_in_repo",
    "no_token_or_credentials_in_repo",
    "no_auth_url_in_repo",
]

REQUIRED_REVIEWER_ATTESTATION_FIELDS = [
    "review_owner_attestation",
    "approval_owner_attestation",
    "scope_completeness_attestation",
    "repository_safety_attestation",
]

INTAKE_VALIDATION_RULES = {
    "must_include_required_intake_fields": True,
    "must_include_legal_document_reference": True,
    "must_include_provider_identity": True,
    "must_include_scope_fields": True,
    "must_include_effective_and_expiration_or_renewal": True,
    "must_include_source_trace_and_audit_reference": True,
    "must_include_secret_exclusion_attestation": True,
    "must_exclude_private_contract_body": True,
    "must_exclude_row_level_proprietary_odds_without_data_rights_decision": True,
}

REVIEW_OWNER_VALIDATION_RULES = {
    "review_owner_required": True,
    "approval_owner_required": True,
    "review_status_must_be_explicit": True,
    "approved_status_requires_authorized_reviewer": True,
    "missing_owner_means_blocked": True,
}

BLOCKED_STATE_RULES = {
    "missing_review_owner_blocked": True,
    "missing_approval_owner_blocked": True,
    "review_not_explicitly_approved_blocked": True,
    "missing_legal_document_reference_blocked": True,
    "missing_provider_identity_blocked": True,
    "missing_scope_fields_blocked": True,
    "missing_effective_date_blocked": True,
    "missing_expiration_or_renewal_blocked": True,
    "missing_source_trace_or_audit_blocked": True,
    "missing_secret_exclusion_attestation_blocked": True,
    "private_contract_body_present_blocked": True,
    "secret_like_field_detected_blocked": True,
    "placeholder_detected_blocked": True,
    "unlock_requested_without_approval_blocked": True,
}

PLACEHOLDER_REJECTION_RULES = {
    "placeholder_detected_means_blocked": True,
    "placeholder_allowed_as_authorization_must_be_false": True,
    "placeholder_cannot_set_provider_approved": True,
    "placeholder_cannot_set_authorization_evidence_present": True,
}

ALLOWED_NEXT_ACTIONS = [
    "Maintain paper_only=true and diagnostic_only=true",
    "Submit intake payload with complete legal reference metadata and review owner fields",
    "Keep review_status blocked until authorized reviewer and approval owner attestations are complete",
    "Keep full regression status explicit as PASS/FAIL/NOT_RUN",
]

PROHIBITED_ACTIONS = [
    "Do not treat placeholder evidence as approved legal authorization",
    "Do not unlock provider, recommendation, EV, CLV, Kelly, stake, profit, or production",
    "Do not store API keys, tokens, credentials, auth URLs, or private contract body in repo artifacts",
    "Do not ingest real legal odds or call live/paid APIs from this schema/gate task",
]

BLOCKERS = [
    "REVIEW_OWNER_MISSING_BLOCKER",
    "APPROVAL_OWNER_MISSING_BLOCKER",
    "REVIEW_STATUS_NOT_EXPLICITLY_APPROVED_BLOCKER",
    "LEGAL_DOCUMENT_REFERENCE_MISSING_BLOCKER",
    "PROVIDER_IDENTITY_MISSING_BLOCKER",
    "SCOPE_FIELDS_MISSING_BLOCKER",
    "EFFECTIVE_DATE_MISSING_BLOCKER",
    "EXPIRATION_OR_RENEWAL_MISSING_BLOCKER",
    "SOURCE_TRACE_OR_AUDIT_MISSING_BLOCKER",
    "SECRET_EXCLUSION_ATTESTATION_MISSING_BLOCKER",
    "PRIVATE_CONTRACT_BODY_PRESENT_BLOCKER",
    "SECRET_OR_AUTH_URL_DETECTED_BLOCKER",
    "PLACEHOLDER_DETECTED_BLOCKER",
    "UNLOCK_REQUEST_WITHOUT_APPROVAL_BLOCKER",
    "FULL_REGRESSION_NOT_RUN_BLOCKER",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_READY_WITH_BLOCKERS",
    "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_BLOCKED_BY_MISSING_P121_OR_P124",
    "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main():
    missing = []
    if not Path(P121_PATH).exists():
        missing.append(P121_PATH)
    if not Path(P124_PATH).exists():
        missing.append(P124_PATH)

    if missing:
        out = {
            "gate_metadata": {
                "gate_version": "P125.20260601",
                "generated_at": "2026-06-01",
                "final_classification": "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_BLOCKED_BY_MISSING_P121_OR_P124",
            },
            "intake_schema_status": "BLOCKED",
            "review_owner_gate_status": "BLOCKED",
            "missing_artifacts": missing,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "prohibited_actions": PROHIBITED_ACTIONS,
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"P125 intake schema summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p124 = load_json(P124_PATH)

    g121 = p121.get("governance_flags", {})

    provider_approved = bool(g121.get("provider_approved", False))
    authorization_evidence_present = bool(g121.get("authorization_evidence_present", False))
    placeholder_detected = True
    placeholder_allowed_as_authorization = False
    real_legal_odds_ingested = bool(g121.get("odds_ingested", False))

    governance_invariants = {
        "paper_only": bool(g121.get("paper_only", False)),
        "diagnostic_only": bool(g121.get("diagnostic_only", False)),
        "production_ready": bool(g121.get("production_ready", False)),
        "real_bet_allowed": bool(g121.get("real_bet_allowed", False)),
        "recommendation_allowed": bool(g121.get("recommendation_allowed", False)),
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

    final_classification = "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_READY_WITH_BLOCKERS"
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
        final_classification = "P125_LEGAL_EVIDENCE_INTAKE_SCHEMA_REVIEW_OWNER_GATE_FAILED_VALIDATION"

    summary = {
        "gate_metadata": {
            "gate_version": "P125.20260601",
            "generated_at": "2026-06-01",
            "source_p121_reference": P121_PATH,
            "source_p124_reference": P124_PATH,
            "source_p124_final_classification": p124.get("contract_metadata", {}).get("final_classification", "UNKNOWN"),
            "final_classification": final_classification,
        },
        "intake_schema_status": "READY_WITH_BLOCKERS",
        "review_owner_gate_status": "BLOCKED",
        "required_intake_fields": REQUIRED_INTAKE_FIELDS,
        "required_review_owner_fields": REQUIRED_REVIEW_OWNER_FIELDS,
        "required_approval_workflow_fields": REQUIRED_APPROVAL_WORKFLOW_FIELDS,
        "required_legal_document_reference_fields": REQUIRED_LEGAL_DOCUMENT_REFERENCE_FIELDS,
        "required_scope_fields": REQUIRED_SCOPE_FIELDS,
        "required_date_fields": REQUIRED_DATE_FIELDS,
        "required_provider_identity_fields": REQUIRED_PROVIDER_IDENTITY_FIELDS,
        "required_data_rights_fields": REQUIRED_DATA_RIGHTS_FIELDS,
        "required_repository_safety_fields": REQUIRED_REPOSITORY_SAFETY_FIELDS,
        "required_secret_exclusion_fields": REQUIRED_SECRET_EXCLUSION_FIELDS,
        "required_reviewer_attestation_fields": REQUIRED_REVIEWER_ATTESTATION_FIELDS,
        "intake_validation_rules": INTAKE_VALIDATION_RULES,
        "review_owner_validation_rules": REVIEW_OWNER_VALIDATION_RULES,
        "blocked_state_rules": BLOCKED_STATE_RULES,
        "placeholder_rejection_rules": PLACEHOLDER_REJECTION_RULES,
        "provider_approved": provider_approved,
        "authorization_evidence_present": authorization_evidence_present,
        "placeholder_detected": placeholder_detected,
        "placeholder_allowed_as_authorization": placeholder_allowed_as_authorization,
        "real_legal_odds_ingested": real_legal_odds_ingested,
        "governance_invariants": governance_invariants,
        "regression_status": {
            "targeted_p118_p124_tests_status": "NOT_RUN",
            "full_regression_status": "NOT_RUN",
            "full_regression_evidence": p124.get("regression_status", {}).get("full_regression_evidence", "No full regression evidence provided."),
        },
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "blockers": BLOCKERS,
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P125 Legal Evidence Intake Schema + Review Owner Gate (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- intake_schema_status: {summary['intake_schema_status']}\n")
        f.write(f"- review_owner_gate_status: {summary['review_owner_gate_status']}\n")
        f.write(f"- final_classification: {summary['gate_metadata']['final_classification']}\n\n")

        f.write("## Core Validation Fields\n")
        for k in (
            "provider_approved",
            "authorization_evidence_present",
            "placeholder_detected",
            "placeholder_allowed_as_authorization",
            "real_legal_odds_ingested",
        ):
            f.write(f"- {k}: {summary[k]}\n")

        f.write("\n## Governance Invariants\n")
        for k, v in summary["governance_invariants"].items():
            f.write(f"- {k}: {v}\n")

        f.write("\n## Intake/Review Contract Groups\n")
        for key in (
            "required_intake_fields",
            "required_review_owner_fields",
            "required_approval_workflow_fields",
            "required_legal_document_reference_fields",
            "required_scope_fields",
            "required_date_fields",
            "required_provider_identity_fields",
            "required_data_rights_fields",
            "required_repository_safety_fields",
            "required_secret_exclusion_fields",
            "required_reviewer_attestation_fields",
        ):
            f.write(f"- {key}:\n")
            for item in summary[key]:
                f.write(f"  - {item}\n")

        f.write("\n## Rule Sets\n")
        for section in (
            "intake_validation_rules",
            "review_owner_validation_rules",
            "blocked_state_rules",
            "placeholder_rejection_rules",
        ):
            f.write(f"- {section}:\n")
            for k, v in summary[section].items():
                f.write(f"  - {k}: {v}\n")

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

    print(f"P125 intake schema summary written to {OUT_PATH}")
    print(f"P125 intake schema report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
