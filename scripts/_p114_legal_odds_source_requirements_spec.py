import json
from datetime import datetime

# 輸入路徑
P113_PATH = "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json"
P101_PATH = "data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json"

# 輸出路徑
OUT_PATH = "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json"


def main():
    with open(P113_PATH, "r", encoding="utf-8") as f:
        p113 = json.load(f)
    with open(P101_PATH, "r", encoding="utf-8") as f:
        p101 = json.load(f)

    spec = {
        "spec_metadata": {
            "spec_version": "P114.20260531",
            "generated_at": datetime.now().strftime("%Y-%m-%d"),
            "source_fixture_version": "P113.20260531",
            "final_classification": "P114_LEGAL_ODDS_SOURCE_REQUIREMENTS_READY_WITH_BLOCKERS"
        },
        "source_p113_fixture_reference": {
            "fixture_path": P113_PATH,
            "fixture_version": "P113.20260531",
            "final_classification": p113["fixture_metadata"]["final_classification"]
        },
        "legal_odds_source_requirements": {
            "provider_authorization": [
                "Must be an authorized legal provider (e.g. Taiwan Sports Lottery)",
                "No scraping, no unofficial APIs, no grey/illegal sources"
            ],
            "odds_schema": [
                "Must provide odds for all supported MLB pregame markets: moneyline, run line, total runs, first five innings (if supported)",
                "Odds must be decimal, positive, and match official market definitions"
            ],
            "source_trace": [
                "Each odds record must include provider, fetch timestamp, and unique market id",
                "Must include source trace fields for auditability"
            ],
            "timestamp": [
                "Odds must include official publish time and fetch time",
                "Must support freshness validation (max 5 min lag for pregame)"
            ],
            "market_mapping": [
                "Market ids and side options must match contract schema fixture",
                "Must provide mapping for all supported and unsupported markets"
            ],
            "data_quality": [
                "No missing odds, no negative/zero odds, no duplicate records",
                "Must pass deduplication and audit checks"
            ],
            "deduplication": [
                "Odds must be deduped by (provider, game_id, market_id, side, fetch_time)"
            ],
            "auditability": [
                "All odds records must be auditable and traceable to source provider"
            ]
        },
        "market_odds_requirements": [],
        "source_trace_requirements": ["provider", "fetch_timestamp", "market_id", "source_trace_id"],
        "timestamp_requirements": ["publish_time", "fetch_time"],
        "market_mapping_requirements": ["market_id", "side", "contract_market_id", "contract_side"],
        "data_quality_requirements": ["no_missing_odds", "no_negative_odds", "no_duplicates", "deduplication_passed", "audit_passed"],
        "deduplication_requirements": ["provider", "game_id", "market_id", "side", "fetch_time"],
        "auditability_requirements": ["provider", "source_trace_id", "audit_log_id"],
        "blocked_actions": ["fetch_odds", "store_odds", "use_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"],
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
            "live_api_calls": 0,
            "paid_api_calls": 0,
            "ev_computed": False,
            "clv_computed": False,
            "kelly_computed": False,
            "stake_sizing": False,
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
            "Source trace and audit pipeline ready"
        ],
        "validation_rules": [
            "No odds may be fetched, stored, used, or computed in this phase.",
            "No market may output a recommendation, EV, CLV, Kelly, stake, or production readiness.",
            "All governance locks must remain true."
        ]
    }

    # 依據 P113 fixture 產生 market_odds_requirements
    for contract in p113["market_contracts"]:
        market_req = {
            "market_id": contract["market_id"],
            "required_odds_fields": contract.get("required_legal_odds_fields", []),
            "required_line_fields": ["line" if "run_line" in contract["market_id"] or "total_runs" in contract["market_id"] else ""],
            "required_side_fields": contract.get("prediction_side_options", []),
            "required_source_trace_fields": ["provider", "fetch_timestamp", "market_id", "source_trace_id"],
            "required_timestamp_fields": ["publish_time", "fetch_time"],
            "required_market_status_fields": ["market_status", "blocked_reason"],
            "required_provider_metadata": ["provider_id", "provider_name"],
            "dedupe_key": ["provider", "game_id", "market_id", "side", "fetch_time"],
            "freshness_requirement": "pregame odds must be <5min old",
            "audit_requirement": "must be auditable to legal provider",
            "current_status": "blocked",
            "blocker_type": contract["current_blockers"] if "current_blockers" in contract else [],
            "allowed_future_action": "integration_after_contract",
            "prohibited_action": ["fetch_odds", "store_odds", "use_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"]
        }
        spec["market_odds_requirements"].append(market_req)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
