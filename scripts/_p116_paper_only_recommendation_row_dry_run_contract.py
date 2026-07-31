"""
P116 Paper-Only Recommendation Row Dry-Run Contract

本檔案僅定義 dry-run recommendation row contract/schema，嚴格禁止任何 odds/EV/CLV/Kelly/production/recommendation 行為。
不產生實際推薦，不抓取/儲存/計算任何 odds、EV、CLV、Kelly、stake、profit、recommendation。
"""
import json
from pathlib import Path

# 上游 artifact 路徑
P115_PATH = "data/mlb_2026/derived/p115_paper_only_odds_ingestion_contract_fixture_summary.json"
P114_PATH = "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json"
P113_PATH = "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json"
P84E_PATH = "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"

# 合約 metadata
CONTRACT_METADATA = {
    "contract_version": "P116.20260531",
    "generated_at": "2026-05-31",
    "source_p115_ingestion_fixture_reference": P115_PATH,
    "source_p114_requirements_reference": P114_PATH,
    "source_p113_schema_fixture_reference": P113_PATH,
    "final_classification": "P116_RECOMMENDATION_ROW_DRY_RUN_CONTRACT_READY_WITH_BLOCKERS"
}

# 禁止行為與治理鎖
GOVERNANCE_LOCKS = {
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

PROHIBITED_ACTIONS = [
    "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation",
    "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
]

BLOCKER_CATEGORIES = [
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
]

# 讀取 P84e prediction row 欄位
with open(P84E_PATH, "r", encoding="utf-8") as f:
    first_row = json.loads(f.readline())
PREDICTION_FIELDS = list(first_row.keys())

# 定義 dry-run recommendation row schema
PAPER_ONLY_RECOMMENDATION_ROW_SCHEMA = {
    "required_fields": [
        "game_id", "game_date", "predicted_side", "model_probability", "source_prediction_version",
        "paper_only", "diagnostic_only", "odds_used", "production_ready", "result_home_score", "result_away_score",
        "actual_winner", "is_correct", "outcome_available", "outcome_source", "outcome_finalized_at"
    ],
    "optional_fields": [k for k in PREDICTION_FIELDS if k not in [
        "game_id", "game_date", "predicted_side", "model_probability", "source_prediction_version",
        "paper_only", "diagnostic_only", "odds_used", "production_ready", "result_home_score", "result_away_score",
        "actual_winner", "is_correct", "outcome_available", "outcome_source", "outcome_finalized_at"
    ]],
    "prohibited_fields": [
        "odds", "ev", "clv", "kelly", "stake", "profit", "recommendation", "production_ready"
    ]
}

# 各市場合約
MARKET_ROW_CONTRACTS = []
for market_id in [
    "moneyline_winner", "run_line_handicap", "total_runs_over_under", "first_five_innings_if_supported_later", "unsupported_market_placeholder"
]:
    MARKET_ROW_CONTRACTS.append({
        "market_id": market_id,
        "row_version": "P116.20260531",
        "required_game_identity_fields": ["game_id", "game_date"],
        "required_prediction_fields": ["predicted_side", "model_probability", "source_prediction_version"],
        "required_market_identity_fields": ["market_id"],
        "required_side_fields": ["home", "away"],
        "required_line_fields": ["line" if market_id != "moneyline_winner" else None],
        "required_odds_reference_fields": [],
        "required_source_trace_fields": ["source_prediction_version"],
        "required_timestamp_fields": ["game_date", "outcome_finalized_at"],
        "required_governance_fields": list(GOVERNANCE_LOCKS.keys()),
        "dry_run_status": "blocked",
        "blocker_type": BLOCKER_CATEGORIES,
        "allowed_future_action": "integration_after_contract",
        "prohibited_action": PROHIBITED_ACTIONS
    })

# prediction/market/odds/source trace contract
PREDICTION_FIELD_CONTRACT = {
    "fields": PREDICTION_FIELDS,
    "prohibited_fields": ["odds", "ev", "clv", "kelly", "stake", "profit", "recommendation"]
}
MARKET_FIELD_CONTRACT = {
    "fields": ["market_id", "side", "line"],
    "prohibited_fields": ["odds", "ev", "clv", "kelly", "stake", "profit", "recommendation", "production_ready"]
}
ODDS_REFERENCE_CONTRACT = {
    "fields": [],
    "note": "odds 欄位禁止出現，僅允許未來 integration 時納入，現階段必須為空"
}
SOURCE_TRACE_CONTRACT = {
    "fields": ["source_prediction_version"],
    "policy": "所有 recommendation row 必須可追溯至 prediction pipeline 版本"
}

BLOCKED_DECISION_FIELDS = ["ev", "clv", "kelly", "stake", "profit", "recommendation"]

VALIDATION_RULES = [
    "不得產生任何 odds、EV、CLV、Kelly、stake、profit、recommendation 欄位",
    "不得產生 production_ready=true 的 row",
    "所有治理鎖必須為 true 或 false（如規範）",
    "不得有任何 odds 欄位出現於 row 內"
]

FUTURE_INTEGRATION_GATES = [
    "待合法 odds provider API 合約簽署",
    "待 schema mapping 驗證通過",
    "待 source trace/audit pipeline 完成",
    "待 ingestion 實作完成"
]

# 合約總結
SUMMARY = {
    "contract_metadata": CONTRACT_METADATA,
    "governance_locks": GOVERNANCE_LOCKS,
    "prohibited_actions": PROHIBITED_ACTIONS,
    "blocker_categories": BLOCKER_CATEGORIES,
    "paper_only_recommendation_row_schema": PAPER_ONLY_RECOMMENDATION_ROW_SCHEMA,
    "market_row_contracts": MARKET_ROW_CONTRACTS,
    "prediction_field_contract": PREDICTION_FIELD_CONTRACT,
    "market_field_contract": MARKET_FIELD_CONTRACT,
    "odds_reference_contract": ODDS_REFERENCE_CONTRACT,
    "source_trace_contract": SOURCE_TRACE_CONTRACT,
    "blocked_decision_fields": BLOCKED_DECISION_FIELDS,
    "validation_rules": VALIDATION_RULES,
    "future_integration_gates": FUTURE_INTEGRATION_GATES,
    "final_classification": CONTRACT_METADATA["final_classification"]
}

# 輸出 summary json
OUT_PATH = "data/mlb_2026/derived/p116_paper_only_recommendation_row_dry_run_contract_summary.json"
Path(OUT_PATH).parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(SUMMARY, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    print(f"P116 dry-run contract summary written to {OUT_PATH}")
