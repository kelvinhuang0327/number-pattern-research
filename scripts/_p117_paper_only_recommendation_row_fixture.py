# P117 Paper-Only Recommendation Row Fixture
# 產生靜態 paper-only recommendation row fixture，僅供 schema/contract 驗證，不產生任何推薦、賠率、或 production output。
import json
from pathlib import Path

# 來源 artifact 路徑
P116_PATH = "data/mlb_2026/derived/p116_paper_only_recommendation_row_dry_run_contract_summary.json"
P115_PATH = "data/mlb_2026/derived/p115_paper_only_odds_ingestion_contract_fixture_summary.json"
P114_PATH = "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json"
P113_PATH = "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json"
P112_PATH = "data/mlb_2026/derived/p112_lane_a_market_contract_gap_review_summary.json"
P101_PATH = "data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json"
P84E_PATH = "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"

OUT_PATH = "data/mlb_2026/derived/p117_paper_only_recommendation_row_fixture_summary.json"

# 必要欄位與 fixture 結構
fixture = {
    "fixture_metadata": {
        "fixture_version": "P117.20260531",
        "generated_at": "2026-05-31",
        "source_p116_contract_reference": P116_PATH,
        "final_classification": "P117_RECOMMENDATION_ROW_FIXTURE_READY_WITH_BLOCKERS"
    },
    "source_p116_contract_reference": P116_PATH,
    "paper_only_recommendation_rows": [],
    "market_row_fixtures": [],
    "prediction_field_fixtures": [
        "game_id", "market_id", "predicted_side", "odds", "source_trace", "dry_run_status", "blocker_type"
    ],
    "market_field_fixtures": [
        "market_id", "market_name", "supported_status", "side_fields", "line_fields"
    ],
    "odds_reference_fixtures": [
        "odds", "publish_time", "fetch_time"
    ],
    "source_trace_fixtures": [
        "provider_id", "provider_name", "source_trace_id", "audit_log_id"
    ],
    "blocked_decision_fields": [
        "dry_run_status", "blocker_type", "allowed_future_action", "prohibited_action"
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
        "recommendation_generated": False,
        "taiwan_lottery_recommendation": False,
        "champion_replacement": False,
        "production_mutation": False,
        "calibration_refit": False,
        "canonical_rows_modified": False,
        "outcome_rows_modified": False,
        "p83e_mapping_modified": False,
        "ui_modified": False
    },
    "validation_rules": [
        "No real odds, EV, CLV, Kelly, stake, profit, or recommendation present.",
        "All rows must be dry_run_status=blocked.",
        "All governance_locks must be strictly enforced."
    ],
    "future_integration_gates": [
        "Integration with future legal odds ingestion and market mapping modules only after blockers resolved."
    ],
    "prohibited_actions": [
        "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
    ]
}

# 必要 market row fixture
market_fixtures = [
    {
        "fixture_row_id": "moneyline_winner_row",
        "market_id": "moneyline_winner",
        "row_version": "P117.20260531",
        "game_identity_fields": ["game_id"],
        "prediction_fields": ["predicted_side"],
        "market_identity_fields": ["market_id", "market_name"],
        "side_fields": ["home", "away"],
        "line_fields": [],
        "odds_reference_fields": ["odds"],
        "source_trace_fields": ["provider_id", "fetch_time"],
        "timestamp_fields": ["publish_time", "fetch_time"],
        "governance_fields": ["paper_only", "diagnostic_only", "production_ready", "recommendation_allowed"],
        "dry_run_status": "blocked",
        "blocker_type": [
            "LEGAL_ODDS_SOURCE_BLOCKER",
            "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
            "ODDS_INGESTION_NOT_IMPLEMENTED_BLOCKER",
            "ODDS_SCHEMA_BLOCKER",
            "MARKET_MAPPING_BLOCKER",
            "SOURCE_TRACE_BLOCKER",
            "TIMESTAMP_FRESHNESS_BLOCKER",
            "DATA_QUALITY_BLOCKER",
            "EV_CLV_NOT_ALLOWED_BLOCKER",
            "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
            "GOVERNANCE_PRODUCTION_BLOCKER",
            "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
        ],
        "allowed_future_action": "diagnostic_tracking_only",
        "prohibited_action": [
            "production", "recommendation", "betting", "odds", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"
        ]
    },
    {
        "fixture_row_id": "run_line_handicap_row",
        "market_id": "run_line_handicap",
        "row_version": "P117.20260531",
        "game_identity_fields": ["game_id"],
        "prediction_fields": ["predicted_side"],
        "market_identity_fields": ["market_id", "market_name"],
        "side_fields": ["home", "away"],
        "line_fields": ["run_line"],
        "odds_reference_fields": ["odds"],
        "source_trace_fields": ["provider_id", "fetch_time"],
        "timestamp_fields": ["publish_time", "fetch_time"],
        "governance_fields": ["paper_only", "diagnostic_only", "production_ready", "recommendation_allowed"],
        "dry_run_status": "blocked",
        "blocker_type": [
            "LEGAL_ODDS_SOURCE_BLOCKER",
            "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
            "ODDS_INGESTION_NOT_IMPLEMENTED_BLOCKER",
            "ODDS_SCHEMA_BLOCKER",
            "MARKET_MAPPING_BLOCKER",
            "SOURCE_TRACE_BLOCKER",
            "TIMESTAMP_FRESHNESS_BLOCKER",
            "DATA_QUALITY_BLOCKER",
            "EV_CLV_NOT_ALLOWED_BLOCKER",
            "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
            "GOVERNANCE_PRODUCTION_BLOCKER",
            "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
        ],
        "allowed_future_action": "diagnostic_tracking_only",
        "prohibited_action": [
            "production", "recommendation", "betting", "odds", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"
        ]
    },
    {
        "fixture_row_id": "total_runs_over_under_row",
        "market_id": "total_runs_over_under",
        "row_version": "P117.20260531",
        "game_identity_fields": ["game_id"],
        "prediction_fields": ["predicted_side"],
        "market_identity_fields": ["market_id", "market_name"],
        "side_fields": ["over", "under"],
        "line_fields": ["total_runs"],
        "odds_reference_fields": ["odds"],
        "source_trace_fields": ["provider_id", "fetch_time"],
        "timestamp_fields": ["publish_time", "fetch_time"],
        "governance_fields": ["paper_only", "diagnostic_only", "production_ready", "recommendation_allowed"],
        "dry_run_status": "blocked",
        "blocker_type": [
            "LEGAL_ODDS_SOURCE_BLOCKER",
            "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
            "ODDS_INGESTION_NOT_IMPLEMENTED_BLOCKER",
            "ODDS_SCHEMA_BLOCKER",
            "MARKET_MAPPING_BLOCKER",
            "SOURCE_TRACE_BLOCKER",
            "TIMESTAMP_FRESHNESS_BLOCKER",
            "DATA_QUALITY_BLOCKER",
            "EV_CLV_NOT_ALLOWED_BLOCKER",
            "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
            "GOVERNANCE_PRODUCTION_BLOCKER",
            "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
        ],
        "allowed_future_action": "diagnostic_tracking_only",
        "prohibited_action": [
            "production", "recommendation", "betting", "odds", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"
        ]
    },
    {
        "fixture_row_id": "first_five_innings_if_supported_later_row",
        "market_id": "first_five_innings_if_supported_later",
        "row_version": "P117.20260531",
        "game_identity_fields": ["game_id"],
        "prediction_fields": ["predicted_side"],
        "market_identity_fields": ["market_id", "market_name"],
        "side_fields": ["home", "away"],
        "line_fields": [],
        "odds_reference_fields": ["odds"],
        "source_trace_fields": ["provider_id", "fetch_time"],
        "timestamp_fields": ["publish_time", "fetch_time"],
        "governance_fields": ["paper_only", "diagnostic_only", "production_ready", "recommendation_allowed"],
        "dry_run_status": "blocked",
        "blocker_type": [
            "LEGAL_ODDS_SOURCE_BLOCKER",
            "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
            "ODDS_INGESTION_NOT_IMPLEMENTED_BLOCKER",
            "ODDS_SCHEMA_BLOCKER",
            "MARKET_MAPPING_BLOCKER",
            "SOURCE_TRACE_BLOCKER",
            "TIMESTAMP_FRESHNESS_BLOCKER",
            "DATA_QUALITY_BLOCKER",
            "EV_CLV_NOT_ALLOWED_BLOCKER",
            "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
            "GOVERNANCE_PRODUCTION_BLOCKER",
            "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
        ],
        "allowed_future_action": "diagnostic_tracking_only",
        "prohibited_action": [
            "production", "recommendation", "betting", "odds", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"
        ]
    },
    {
        "fixture_row_id": "unsupported_market_placeholder_row",
        "market_id": "unsupported_market_placeholder",
        "row_version": "P117.20260531",
        "game_identity_fields": ["game_id"],
        "prediction_fields": ["predicted_side"],
        "market_identity_fields": ["market_id", "market_name"],
        "side_fields": [],
        "line_fields": [],
        "odds_reference_fields": [],
        "source_trace_fields": [],
        "timestamp_fields": [],
        "governance_fields": ["paper_only", "diagnostic_only", "production_ready", "recommendation_allowed"],
        "dry_run_status": "blocked",
        "blocker_type": [
            "LEGAL_ODDS_SOURCE_BLOCKER",
            "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
            "ODDS_INGESTION_NOT_IMPLEMENTED_BLOCKER",
            "ODDS_SCHEMA_BLOCKER",
            "MARKET_MAPPING_BLOCKER",
            "SOURCE_TRACE_BLOCKER",
            "TIMESTAMP_FRESHNESS_BLOCKER",
            "DATA_QUALITY_BLOCKER",
            "EV_CLV_NOT_ALLOWED_BLOCKER",
            "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
            "GOVERNANCE_PRODUCTION_BLOCKER",
            "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
        ],
        "allowed_future_action": "diagnostic_tracking_only",
        "prohibited_action": [
            "production", "recommendation", "betting", "odds", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"
        ]
    }
]

fixture["market_row_fixtures"] = market_fixtures

# 產生空的 paper_only_recommendation_rows (僅 fixture 結構)
fixture["paper_only_recommendation_rows"] = []

# 輸出 JSON
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(fixture, f, ensure_ascii=False, indent=2)

print(f"P117 fixture generated: {OUT_PATH}")
