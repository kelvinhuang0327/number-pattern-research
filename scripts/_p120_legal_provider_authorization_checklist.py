# P120 Legal Provider Authorization Checklist
# Diagnostic-only, no odds, no live API, no scraping, no production logic
# Outputs checklist summary JSON for legal provider integration requirements

import json
from pathlib import Path

P119_PATH = "data/mlb_2026/derived/p119_recommendation_row_gate_violation_fixture_summary.json"
P118_PATH = "data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json"
OUT_PATH = "data/mlb_2026/derived/p120_legal_provider_authorization_checklist_summary.json"

MARKETS = [
    "moneyline_winner",
    "run_line_handicap",
    "total_runs_over_under",
    "first_five_innings_if_supported_later",
    "unsupported_market_placeholder"
]

BLOCKER_CATEGORIES = [
    "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
    "DATA_LICENSE_BLOCKER",
    "FORBIDDEN_SCRAPING_BLOCKER",
    "SOURCE_TRACE_BLOCKER",
    "AUDIT_LOG_BLOCKER",
    "SECRET_HANDLING_BLOCKER",
    "MARKET_COVERAGE_BLOCKER",
    "TIMESTAMP_FRESHNESS_BLOCKER",
    "DATA_RETENTION_POLICY_BLOCKER",
    "COMPLIANCE_REVIEW_BLOCKER",
    "EV_CLV_NOT_ALLOWED_BLOCKER",
    "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
    "GOVERNANCE_PRODUCTION_BLOCKER",
    "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
]

def build_market_checklist():
    checklist = []
    for market_id in MARKETS:
        checklist.append({
            "market_id": market_id,
            "provider_authorization_required": True,
            "license_required": True,
            "legal_usage_scope_required": True,
            "allowed_access_method": "Official API or legally authorized data feed only",
            "forbidden_access_methods": ["Scraping", "Unofficial API", "Grey/illegal source"],
            "required_source_trace_fields": ["provider_id", "fetch_time", "market_id"],
            "required_audit_fields": ["audit_log_id"],
            "required_timestamp_fields": ["publish_time", "fetch_time"],
            "required_data_quality_fields": ["no_missing_odds", "no_negative_odds", "deduplication"],
            "authorization_status": "BLOCKED",
            "blocker_type": BLOCKER_CATEGORIES,
            "allowed_future_action": "Authorize with signed contract and compliance review",
            "prohibited_action": "Any odds ingestion, storage, computation, or recommendation until authorized"
        })
    return checklist

def main():
    summary = {
        "checklist_metadata": {
            "checklist_version": "P120.20260531",
            "generated_at": "2026-05-31",
            "final_classification": "P120_LEGAL_PROVIDER_AUTHORIZATION_CHECKLIST_READY_WITH_BLOCKERS"
        },
        "source_p119_gate_violation_reference": P119_PATH,
        "source_p118_gate_reference": P118_PATH,
        "authorization_scope": "Defines all requirements for legal provider, odds source, or market data integration. No provider is authorized until all checklist items are satisfied and signed artifact is present.",
        "legal_provider_authorization_requirements": [
            "Provider must be legally authorized (e.g. Taiwan Sports Lottery, MLB official)",
            "No scraping, no unofficial/grey/illegal sources",
            "Authorization artifact (contract, license) must be present in repo before any integration"
        ],
        "provider_contract_requirements": [
            "Signed provider contract required",
            "Scope of data usage and allowed markets must be explicit"
        ],
        "data_license_requirements": [
            "Explicit data license required for all odds/market data",
            "License must cover all intended use cases"
        ],
        "market_coverage_requirements": [
            f"Must cover: {', '.join(MARKETS)}",
            "All markets must be individually authorized"
        ],
        "odds_access_method_requirements": [
            "Only official API or authorized data feed allowed",
            "Scraping forbidden unless explicitly authorized in writing"
        ],
        "source_trace_requirements": [
            "All records must include provider_id, fetch_time, market_id",
            "Traceability and auditability required"
        ],
        "audit_log_requirements": [
            "All data access and ingestion must be logged",
            "Audit logs must be retained for compliance review"
        ],
        "data_retention_requirements": [
            "Retention policy must be defined in contract",
            "No indefinite storage without legal basis"
        ],
        "security_and_secret_handling_requirements": [
            "No credentials, secrets, or auth URLs in repo",
            "All secrets must be managed via secure vault, never hardcoded"
        ],
        "compliance_review_requirements": [
            "All provider integrations must pass legal and compliance review before activation"
        ],
        "blocked_until_authorized_items": [
            "All odds ingestion, storage, computation, recommendation, and production use are BLOCKED until all checklist items are satisfied and signed artifact is present"
        ],
        "future_integration_gates": [
            "Legal provider contract upload",
            "Compliance review pass",
            "Technical integration review"
        ],
        "allowed_future_actions": ["Begin integration only after all legal, license, and compliance gates are satisfied"],
        "prohibited_actions": [
            "No odds fetching, storage, ingestion, computation, or recommendation until authorized",
            "No scraping unless explicitly authorized",
            "No credentials, secrets, or auth URLs in repo"
        ],
        "market_authorization_matrix": build_market_checklist(),
        "blocker_category_coverage": BLOCKER_CATEGORIES
    }
    Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"P120 legal provider authorization checklist written to {OUT_PATH}")

if __name__ == "__main__":
    main()
