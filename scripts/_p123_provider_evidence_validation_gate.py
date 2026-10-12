# P123 Provider Evidence Validation Gate
# Blocks placeholder-only evidence from being treated as legal provider authorization.

import json
from pathlib import Path

P121_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P122_PATH = "data/mlb_2026/derived/p122_paper_only_recommendation_readiness_review_summary.json"
OUT_PATH = "data/mlb_2026/derived/p123_provider_evidence_validation_gate_summary.json"
REPORT_PATH = "report/p123_provider_evidence_validation_gate_20260601.md"

SENSITIVE_KEYS = {
    "real_api_key",
    "api_key",
    "token",
    "real_token",
    "secret",
    "real_secret",
    "password",
    "real_password",
    "private_auth_url",
    "auth_url",
    "credential",
    "credentials",
    "provider_credentials",
    "signed_contract_binary",
    "private_contract_content",
    "production_access_token",
}

BLOCKERS = [
    "PROVIDER_APPROVAL_FALSE_BLOCKER",
    "AUTHORIZATION_EVIDENCE_MISSING_BLOCKER",
    "PLACEHOLDER_DETECTED_BLOCKER",
    "LEGAL_DOCUMENT_MISSING_BLOCKER",
    "LICENSE_SCOPE_MISSING_BLOCKER",
    "MARKET_SCOPE_MISSING_BLOCKER",
    "SOURCE_TRACE_MISSING_BLOCKER",
    "AUDIT_REQUIREMENTS_MISSING_BLOCKER",
    "REAL_LEGAL_ODDS_NOT_APPROVED_BLOCKER",
    "RECOMMENDATION_UNLOCK_NOT_ALLOWED_BLOCKER",
    "PRODUCTION_UNLOCK_NOT_ALLOWED_BLOCKER",
    "FULL_REGRESSION_NOT_RUN_BLOCKER",
]

PROHIBITED_ACTIONS = [
    "Do not treat placeholder evidence as provider approval",
    "Do not unlock provider integration, recommendation, EV, CLV, Kelly, stake, profit, or production",
    "Do not ingest or use real legal odds without legal approval workflow",
    "Do not store secrets, tokens, credentials, auth URLs, or private contract content in repo artifacts",
]

ALLOWED_NEXT_ACTIONS = [
    "Maintain paper_only=true and diagnostic_only=true",
    "Keep production_ready=false and recommendation_allowed=false",
    "Collect legal evidence via compliance workflow (outside placeholder)",
    "Add legal document, license scope, market scope, source trace, and audit evidence through reviewed process",
    "Re-run targeted tests and keep full regression status explicit as PASS/FAIL/NOT_RUN",
]

FINAL_CLASSIFICATION_OPTIONS = [
    "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_READY_BLOCKS_PLACEHOLDER_AUTHORIZATION",
    "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_BLOCKED_BY_MISSING_P121_OR_P122",
    "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_FAILED_VALIDATION",
]


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def detect_sensitive_content(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k).lower()
            if key in SENSITIVE_KEYS:
                if isinstance(v, str):
                    val = v.strip().lower()
                    if val and "<required future field>" not in val and "<no provider approved>" not in val:
                        return True
                elif v not in (None, False, 0, ""):
                    return True
            if detect_sensitive_content(v):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if detect_sensitive_content(item):
                return True
    return False


def main():
    missing = []
    if not Path(P121_PATH).exists():
        missing.append(P121_PATH)
    if not Path(P122_PATH).exists():
        missing.append(P122_PATH)

    if missing:
        summary = {
            "validation_metadata": {
                "gate_version": "P123.20260601",
                "generated_at": "2026-06-01",
                "final_classification": "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_BLOCKED_BY_MISSING_P121_OR_P122",
            },
            "provider_evidence_validation_status": "BLOCKED",
            "missing_artifacts": missing,
            "blockers": ["MISSING_REQUIRED_ARTIFACTS_BLOCKER"],
            "prohibited_actions": PROHIBITED_ACTIONS,
            "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
            "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
        }
        Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"P123 validation summary written to {OUT_PATH}")
        return

    p121 = load_json(P121_PATH)
    p122 = load_json(P122_PATH)

    g121 = p121.get("governance_flags", {})
    p121_meta = p121.get("placeholder_metadata", {})

    placeholder_detected = True
    placeholder_allowed_as_authorization = False

    provider_approved = bool(g121.get("provider_approved", False))
    authorization_evidence_present = bool(g121.get("authorization_evidence_present", False))

    legal_document_present = False
    license_scope_present = False
    market_scope_present = False
    source_trace_present = False
    audit_requirements_present = False

    if p121.get("required_future_evidence_fields"):
        required_fields = set(p121.get("required_future_evidence_fields", []))
        license_scope_present = "license_status" in required_fields
        market_scope_present = "authorized_markets" in required_fields
        source_trace_present = "source_trace_requirement" in required_fields
        audit_requirements_present = "audit_reference_placeholder" in required_fields

    # Placeholder schema exists, but legal document is intentionally absent at P121 stage.
    legal_document_present = False

    secret_or_auth_url_detected = detect_sensitive_content(p121)

    real_legal_odds_ingested = bool(g121.get("odds_ingested", False))

    recommendation_unlock_allowed = False
    production_unlock_allowed = False

    readiness_status = p122.get("readiness_status", "UNKNOWN")
    p122_regression = p122.get("regression_status", {})
    full_regression_status = p122_regression.get("full_regression_status", "NOT_RUN")

    governance_invariants = {
        "paper_only": bool(g121.get("paper_only", False)),
        "diagnostic_only": bool(g121.get("diagnostic_only", False)),
        "production_ready": bool(g121.get("production_ready", True)),
        "real_bet_allowed": bool(g121.get("real_bet_allowed", True)),
        "recommendation_allowed": bool(g121.get("recommendation_allowed", True)),
        "placeholder_allowed_as_authorization": placeholder_allowed_as_authorization,
        "provider_approved": provider_approved,
        "authorization_evidence_present": authorization_evidence_present,
        "real_legal_odds_ingested": real_legal_odds_ingested,
        "live_api_calls": int(g121.get("live_api_calls", 1)),
        "paid_api_called": int(g121.get("paid_api_calls", 1)) > 0,
        "ev_computed": bool(g121.get("ev_computed", True)),
        "clv_computed": bool(g121.get("clv_computed", True)),
        "kelly_computed": bool(g121.get("kelly_computed", True)),
        "stake_sizing": bool(g121.get("stake_sizing", True)),
        "profit_computed": bool(g121.get("profit_computed", True)),
        "recommendation_generated": bool(g121.get("recommendation_generated", True)),
    }

    blockers = list(BLOCKERS)
    if secret_or_auth_url_detected:
        blockers.append("SECRET_OR_AUTH_URL_DETECTED_BLOCKER")

    final_classification = "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_READY_BLOCKS_PLACEHOLDER_AUTHORIZATION"

    hard_fail = (
        governance_invariants["paper_only"] is False
        or governance_invariants["diagnostic_only"] is False
        or governance_invariants["production_ready"] is True
        or governance_invariants["real_bet_allowed"] is True
        or governance_invariants["recommendation_allowed"] is True
        or governance_invariants["placeholder_allowed_as_authorization"] is True
        or governance_invariants["provider_approved"] is True
        or governance_invariants["authorization_evidence_present"] is True
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
        final_classification = "P123_PROVIDER_EVIDENCE_VALIDATION_GATE_FAILED_VALIDATION"

    summary = {
        "validation_metadata": {
            "gate_version": "P123.20260601",
            "generated_at": "2026-06-01",
            "source_p121_reference": P121_PATH,
            "source_p122_reference": P122_PATH,
            "p121_final_classification": p121_meta.get("final_classification", "UNKNOWN"),
            "p122_final_classification": p122.get("readiness_metadata", {}).get("final_classification", "UNKNOWN"),
            "final_classification": final_classification,
        },
        "provider_evidence_validation_status": "BLOCKED",
        "provider_approved": provider_approved,
        "authorization_evidence_present": authorization_evidence_present,
        "placeholder_detected": placeholder_detected,
        "placeholder_allowed_as_authorization": placeholder_allowed_as_authorization,
        "legal_document_present": legal_document_present,
        "license_scope_present": license_scope_present,
        "market_scope_present": market_scope_present,
        "source_trace_present": source_trace_present,
        "audit_requirements_present": audit_requirements_present,
        "secret_or_auth_url_detected": secret_or_auth_url_detected,
        "real_legal_odds_ingested": real_legal_odds_ingested,
        "recommendation_unlock_allowed": recommendation_unlock_allowed,
        "production_unlock_allowed": production_unlock_allowed,
        "readiness_status_from_p122": readiness_status,
        "regression_status": {
            "targeted_p118_p122_tests_status": "NOT_RUN",
            "full_regression_status": full_regression_status,
            "full_regression_evidence": p122_regression.get(
                "full_regression_evidence",
                "No full regression evidence provided."
            ),
        },
        "governance_invariants": governance_invariants,
        "blockers": blockers,
        "prohibited_actions": PROHIBITED_ACTIONS,
        "allowed_next_actions": ALLOWED_NEXT_ACTIONS,
        "final_classification_options": FINAL_CLASSIFICATION_OPTIONS,
    }

    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# P123 Provider Evidence Validation Gate (2026-06-01)\n\n")
        f.write("## Decision\n")
        f.write(f"- provider_evidence_validation_status: {summary['provider_evidence_validation_status']}\n")
        f.write(f"- final_classification: {summary['validation_metadata']['final_classification']}\n\n")

        f.write("## Core Validation Fields\n")
        keys = [
            "provider_approved",
            "authorization_evidence_present",
            "placeholder_detected",
            "placeholder_allowed_as_authorization",
            "legal_document_present",
            "license_scope_present",
            "market_scope_present",
            "source_trace_present",
            "audit_requirements_present",
            "secret_or_auth_url_detected",
            "real_legal_odds_ingested",
            "recommendation_unlock_allowed",
            "production_unlock_allowed",
        ]
        for k in keys:
            f.write(f"- {k}: {summary[k]}\n")

        f.write("\n## Governance Invariants\n")
        for k, v in summary["governance_invariants"].items():
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

    print(f"P123 validation summary written to {OUT_PATH}")
    print(f"P123 validation report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
