import json
from datetime import datetime

# 輸入路徑
P114_PATH = "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json"

# 輸出路徑
OUT_PATH = "data/mlb_2026/derived/p115_paper_only_odds_ingestion_contract_fixture_summary.json"

BLOCKER_CATEGORIES = [
    "LEGAL_ODDS_SOURCE_BLOCKER",
    "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
    "ODDS_SCHEMA_BLOCKER",
    "INGESTION_NOT_IMPLEMENTED_BLOCKER",
    "MARKET_MAPPING_BLOCKER",
    "SOURCE_TRACE_BLOCKER",
    "TIMESTAMP_FRESHNESS_BLOCKER",
    "DATA_QUALITY_BLOCKER",
    "EV_CLV_NOT_ALLOWED_BLOCKER",
    "GOVERNANCE_PRODUCTION_BLOCKER"
]

MARKETS = [
    {
        "market_id": "moneyline_winner",
        "payload_version": "P115.20260531",
        "required_provider_fields": ["provider_id", "provider_name"],
        "required_game_identity_fields": ["game_id"],
        "required_market_identity_fields": ["market_id"],
        "required_side_fields": ["home", "away"],
        "required_line_fields": [],
        "required_decimal_odds_fields": ["odds"],
        "required_timestamp_fields": ["publish_time", "fetch_time"],
        "required_source_trace_fields": ["provider", "fetch_timestamp", "market_id", "source_trace_id"],
        "required_audit_fields": ["audit_log_id"],
        "dedupe_key_fields": ["provider", "game_id", "market_id", "side", "fetch_time"],
        "freshness_policy": "pregame odds must be <5min old",
        "quality_policy": "no missing/negative/duplicate odds, must pass dedup/audit",
        "current_fixture_status": "blocked",
        "blocker_type": BLOCKER_CATEGORIES,
        "allowed_future_action": "integration_after_contract",
        "prohibited_action": [
            "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
        ]
    },
    {
        "market_id": "run_line_handicap",
        "payload_version": "P115.20260531",
        "required_provider_fields": ["provider_id", "provider_name"],
        "required_game_identity_fields": ["game_id"],
        "required_market_identity_fields": ["market_id"],
        "required_side_fields": [],
        "required_line_fields": ["line"],
        "required_decimal_odds_fields": ["odds"],
        "required_timestamp_fields": ["publish_time", "fetch_time"],
        "required_source_trace_fields": ["provider", "fetch_timestamp", "market_id", "source_trace_id"],
        "required_audit_fields": ["audit_log_id"],
        "dedupe_key_fields": ["provider", "game_id", "market_id", "side", "fetch_time"],
        "freshness_policy": "pregame odds must be <5min old",
        "quality_policy": "no missing/negative/duplicate odds, must pass dedup/audit",
        "current_fixture_status": "blocked",
        "blocker_type": BLOCKER_CATEGORIES,
        "allowed_future_action": "integration_after_contract",
        "prohibited_action": [
            "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
        ]
    },
    {
        "market_id": "total_runs_over_under",
        "payload_version": "P115.20260531",
        "required_provider_fields": ["provider_id", "provider_name"],
        "required_game_identity_fields": ["game_id"],
        "required_market_identity_fields": ["market_id"],
        "required_side_fields": [],
        "required_line_fields": ["line"],
        "required_decimal_odds_fields": ["odds"],
        "required_timestamp_fields": ["publish_time", "fetch_time"],
        "required_source_trace_fields": ["provider", "fetch_timestamp", "market_id", "source_trace_id"],
        "required_audit_fields": ["audit_log_id"],
        "dedupe_key_fields": ["provider", "game_id", "market_id", "side", "fetch_time"],
        "freshness_policy": "pregame odds must be <5min old",
        "quality_policy": "no missing/negative/duplicate odds, must pass dedup/audit",
        "current_fixture_status": "blocked",
        "blocker_type": BLOCKER_CATEGORIES,
        "allowed_future_action": "integration_after_contract",
        "prohibited_action": [
            "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
        ]
    },
    {
        "market_id": "first_five_innings_if_supported_later",
        "payload_version": "P115.20260531",
        "required_provider_fields": ["provider_id", "provider_name"],
        "required_game_identity_fields": ["game_id"],
        "required_market_identity_fields": ["market_id"],
        "required_side_fields": [],
        "required_line_fields": ["line"],
        "required_decimal_odds_fields": ["odds"],
        "required_timestamp_fields": ["publish_time", "fetch_time"],
        "required_source_trace_fields": ["provider", "fetch_timestamp", "market_id", "source_trace_id"],
        "required_audit_fields": ["audit_log_id"],
        "dedupe_key_fields": ["provider", "game_id", "market_id", "side", "fetch_time"],
        "freshness_policy": "pregame odds must be <5min old",
        "quality_policy": "no missing/negative/duplicate odds, must pass dedup/audit",
        "current_fixture_status": "blocked",
        "blocker_type": BLOCKER_CATEGORIES,
        "allowed_future_action": "integration_after_contract",
        "prohibited_action": [
            "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
        ]
    },
    {
        "market_id": "unsupported_market_placeholder",
        "payload_version": "P115.20260531",
        "required_provider_fields": ["provider_id", "provider_name"],
        "required_game_identity_fields": ["game_id"],
        "required_market_identity_fields": ["market_id"],
        "required_side_fields": [],
        "required_line_fields": [],
        "required_decimal_odds_fields": ["odds"],
        "required_timestamp_fields": ["publish_time", "fetch_time"],
        "required_source_trace_fields": ["provider", "fetch_timestamp", "market_id", "source_trace_id"],
        "required_audit_fields": ["audit_log_id"],
        "dedupe_key_fields": ["provider", "game_id", "market_id", "side", "fetch_time"],
        "freshness_policy": "pregame odds must be <5min old",
        "quality_policy": "no missing/negative/duplicate odds, must pass dedup/audit",
        "current_fixture_status": "blocked",
        "blocker_type": BLOCKER_CATEGORIES,
        "allowed_future_action": "integration_after_contract",
        "prohibited_action": [
            "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
        ]
    }
]

def main():
    with open(P114_PATH, "r", encoding="utf-8") as f:
        p114 = json.load(f)

    fixture = {
        "fixture_metadata": {
            "fixture_version": "P115.20260531",
            "generated_at": datetime.now().strftime("%Y-%m-%d"),
            "source_requirements_version": "P114.20260531",
            "final_classification": "P115_PAPER_ONLY_ODDS_INGESTION_CONTRACT_READY_WITH_BLOCKERS"
        },
        "source_p114_requirements_reference": {
            "requirements_path": P114_PATH,
            "requirements_version": "P114.20260531",
            "final_classification": p114["spec_metadata"]["final_classification"]
        },
        "paper_only_ingestion_payload_contract": {
            "description": "Defines the required fields, validation, dedupe, and audit for paper-only odds ingestion. No real odds are fetched, stored, used, or computed.",
            "allowed_payload_fields": [
                "provider_id", "provider_name", "game_id", "market_id", "side", "line", "odds", "publish_time", "fetch_time", "source_trace_id", "audit_log_id"
            ],
            "prohibited_fields": [
                "real_odds", "ev", "clv", "kelly", "stake", "profit", "recommendation", "production_ready"
            ],
            "governance_flags": {
                "paper_only": True,
                "diagnostic_only": True,
                "production_ready": False,
                "real_bet_allowed": False,
                "recommendation_allowed": False,
                "product_surface_allowed": False,
                "odds_used": False,
                "odds_fetched": False,
                "odds_stored": False,
                "odds_ingested": False,
                "live_api_calls": 0,
                "paid_api_calls": 0,
                "ev_computed": False,
                "clv_computed": False,
                "kelly_computed": False,
                "stake_sizing": False,
                "profit_computed": False,
                "taiwan_lottery_recommendation": False,
                "champion_replacement": False,
                "production_mutation": False,
                "calibration_refit": False,
                "canonical_rows_modified": False,
                "outcome_rows_modified": False,
                "p83e_mapping_modified": False,
                "ui_modified": False
            }
        },
        "market_payload_contracts": MARKETS,
        "dedupe_contract": {
            "dedupe_key_fields": ["provider", "game_id", "market_id", "side", "fetch_time"],
            "policy": "No duplicate odds records allowed for the same dedupe key."
        },
        "source_trace_contract": {
            "required_fields": ["provider", "fetch_timestamp", "market_id", "source_trace_id"],
            "policy": "All odds records must be traceable to legal provider."
        },
        "timestamp_freshness_contract": {
            "required_fields": ["publish_time", "fetch_time"],
            "policy": "Pregame odds must be <5min old at ingestion."
        },
        "provider_metadata_contract": {
            "required_fields": ["provider_id", "provider_name"],
            "policy": "Provider must be authorized and metadata must be present."
        },
        "data_quality_validation_contract": {
            "required_fields": ["odds"],
            "policy": "No missing, negative, or duplicate odds. Must pass deduplication and audit."
        },
        "audit_log_contract": {
            "required_fields": ["audit_log_id"],
            "policy": "All ingestion must be auditable."
        },
        "blocked_actions": [
            "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
        ],
        "governance_locks": {
            "paper_only": True,
            "diagnostic_only": True,
            "production_ready": False,
            "real_bet_allowed": False,
            "recommendation_allowed": False,
            "product_surface_allowed": False,
            "odds_used": False,
            "odds_fetched": False,
            "odds_stored": False,
            "odds_ingested": False,
            "live_api_calls": 0,
            "paid_api_calls": 0,
            "ev_computed": False,
            "clv_computed": False,
            "kelly_computed": False,
            "stake_sizing": False,
            "profit_computed": False,
            "taiwan_lottery_recommendation": False,
            "champion_replacement": False,
            "production_mutation": False,
            "calibration_refit": False,
            "canonical_rows_modified": False,
            "outcome_rows_modified": False,
            "p83e_mapping_modified": False,
            "ui_modified": False
        },
        "future_integration_gates": [
            "Legal provider API contract signed",
            "Schema mapping validated",
            "Source trace and audit pipeline ready",
            "Ingestion implementation complete"
        ],
        "validation_rules": [
            "No odds may be fetched, stored, ingested, used, or computed in this phase.",
            "No market may output a recommendation, EV, CLV, Kelly, stake, profit, or production readiness.",
            "All governance locks must remain true."
        ]
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
