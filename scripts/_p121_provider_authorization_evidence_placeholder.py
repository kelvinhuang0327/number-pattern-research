# P121 Provider Authorization Evidence Placeholder
# 僅供診斷與治理驗證用途，嚴禁任何實際授權、推薦、賠率、EV、CLV、Kelly、投注、API、憑證、密鑰、合約、真實資料。
import json
from pathlib import Path

OUT_PATH = "data/mlb_2026/derived/p121_provider_authorization_evidence_placeholder_summary.json"
P120_PATH = "data/mlb_2026/derived/p120_legal_provider_authorization_checklist_summary.json"

REQUIRED_MARKETS = [
    "moneyline_winner",
    "run_line_handicap",
    "total_runs_over_under",
    "first_five_innings_if_supported_later",
    "unsupported_market_placeholder"
]

REQUIRED_BLOCKERS = [
    "PROVIDER_AUTHORIZATION_EVIDENCE_MISSING",
    "SIGNED_CONTRACT_MISSING",
    "DATA_LICENSE_MISSING",
    "COMPLIANCE_REVIEW_MISSING",
    "SECURITY_REVIEW_MISSING",
    "SOURCE_TRACE_REQUIREMENT_MISSING",
    "AUDIT_REFERENCE_MISSING",
    "SECRET_HANDLING_BLOCKER",
    "FORBIDDEN_CREDENTIAL_STORAGE_BLOCKER",
    "FORBIDDEN_SCRAPING_BLOCKER",
    "EV_CLV_NOT_ALLOWED_BLOCKER",
    "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
    "GOVERNANCE_PRODUCTION_BLOCKER",
    "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
]

REQUIRED_EVIDENCE_FIELDS = [
    "provider_name_placeholder",
    "provider_contract_status",
    "legal_usage_scope",
    "license_status",
    "authorized_markets",
    "authorized_access_method",
    "authorized_regions",
    "effective_date_placeholder",
    "expiry_date_placeholder",
    "review_owner_placeholder",
    "audit_reference_placeholder",
    "source_trace_requirement",
    "data_retention_policy_status",
    "security_review_status",
    "compliance_review_status"
]

FORBIDDEN_EVIDENCE_FIELDS = [
    "real_api_key",
    "real_secret",
    "real_token",
    "real_password",
    "private_auth_url",
    "signed_contract_binary",
    "provider_credentials",
    "live_endpoint_credentials",
    "personal_data",
    "production_access_token"
]

def main():
    # 讀取 P120 summary 以引用 checklist
    if not Path(P120_PATH).exists():
        raise FileNotFoundError(f"P120 checklist not found: {P120_PATH}")
    with open(P120_PATH, encoding="utf-8") as f:
        p120 = json.load(f)
    # Placeholder summary
    d = {
        "placeholder_metadata": {
            "placeholder_version": "P121.20260531",
            "generated_at": "2026-05-31",
            "final_classification": "P121_PROVIDER_AUTHORIZATION_EVIDENCE_PLACEHOLDER_READY_WITH_BLOCKERS"
        },
        "source_p120_checklist_reference": P120_PATH,
        "authorization_evidence_scope": "Defines where and how future legal provider authorization evidence must be represented, validated, and blocked until real signed/legal artifacts exist. No provider is approved. No evidence is present.",
        "evidence_schema": {
            "required_future_evidence_fields": REQUIRED_EVIDENCE_FIELDS,
            "forbidden_evidence_fields": FORBIDDEN_EVIDENCE_FIELDS
        },
        "provider_authorization_evidence_placeholder": {
            "evidence_schema": {
                "required_future_evidence_fields": REQUIRED_EVIDENCE_FIELDS,
                "forbidden_evidence_fields": FORBIDDEN_EVIDENCE_FIELDS
            },
            "example_placeholder": {
                k: "<REQUIRED FUTURE FIELD>" for k in REQUIRED_EVIDENCE_FIELDS
            }
        },
        "required_future_evidence_fields": REQUIRED_EVIDENCE_FIELDS,
        "forbidden_evidence_fields": FORBIDDEN_EVIDENCE_FIELDS,
        "provider_status_matrix": [
            {
                "provider_name_placeholder": "<NO PROVIDER APPROVED>",
                "provider_contract_status": "MISSING",
                "authorization_evidence_present": False,
                "provider_approved": False,
                "provider_authorized": False,
                "authorization_status": "BLOCKED",
                "blocker_type": [
                    "PROVIDER_AUTHORIZATION_EVIDENCE_MISSING",
                    "SIGNED_CONTRACT_MISSING",
                    "DATA_LICENSE_MISSING",
                    "COMPLIANCE_REVIEW_MISSING",
                    "SECURITY_REVIEW_MISSING"
                ],
                "allowed_future_action": "Upload signed contract, pass compliance review, provide legal evidence",
                "prohibited_action": "No provider may be approved or authorized until all evidence is present and validated"
            }
        ],
        "market_authorization_matrix": [
            {
                "market_id": m,
                "authorization_evidence_required": True,
                "current_evidence_status": "MISSING",
                "required_future_evidence_fields": REQUIRED_EVIDENCE_FIELDS,
                "forbidden_evidence_fields": FORBIDDEN_EVIDENCE_FIELDS,
                "authorization_status": "BLOCKED",
                "blocker_type": REQUIRED_BLOCKERS,
                "allowed_future_action": "Provide all required evidence, pass all reviews",
                "prohibited_action": "No odds, recommendation, or production logic until evidence is present and validated"
            } for m in REQUIRED_MARKETS
        ],
        "evidence_validation_rules": [
            "No provider may be approved until all required evidence fields are present and validated",
            "No forbidden evidence fields may be present"
        ],
        "audit_review_requirements": [
            "All evidence must be auditable and reviewed by governance/legal/compliance before any provider is approved"
        ],
        "secret_handling_rules": [
            "No credentials, secrets, tokens, or private auth URLs may be present in repo or evidence placeholder"
        ],
        "blocked_until_evidence_items": [
            "All provider approval, odds ingestion, storage, computation, recommendation, and production use are BLOCKED until all evidence is present and validated"
        ],
        "future_integration_gates": [
            "Signed contract upload",
            "Legal evidence review",
            "Compliance review pass",
            "Technical integration review"
        ],
        "allowed_future_actions": [
            "Begin integration only after all legal, license, and compliance gates are satisfied"
        ],
        "prohibited_actions": [
            "No provider approval, odds fetching, storage, ingestion, computation, or recommendation until evidence is present and validated",
            "No credentials, secrets, tokens, or private auth URLs in repo or evidence placeholder"
        ],
        "blocker_category_coverage": REQUIRED_BLOCKERS,
        "governance_flags": {
            "paper_only": True,
            "diagnostic_only": True,
            "production_ready": False,
            "real_bet_allowed": False,
            "recommendation_allowed": False,
            "product_surface_allowed": False,
            "provider_approved": False,
            "provider_authorized": False,
            "authorization_evidence_present": False,
            "odds_used": False,
            "odds_fetched": False,
            "odds_stored": False,
            "odds_ingested": False,
            "live_api_calls": 0,
            "paid_api_calls": 0,
            "credentials_used": False,
            "credentials_stored": False,
            "secrets_modified": False,
            "scraping_used": False,
            "ev_computed": False,
            "clv_computed": False,
            "kelly_computed": False,
            "stake_sizing": False,
            "profit_computed": False,
            "recommendation_generated": False,
            "taiwan_lottery_recommendation": False,
            "champion_replacement": False,
            "production_mutation": False,
            "calibration_refit": False,
            "canonical_rows_modified": False,
            "outcome_rows_modified": False,
            "p83e_mapping_modified": False,
            "ui_modified": False,
            "branch_protection_modified": False,
            "force_push_used": False
        }
    }
    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    print(f"P121 provider authorization evidence placeholder written to {OUT_PATH}")

if __name__ == "__main__":
    main()
