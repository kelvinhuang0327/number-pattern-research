import json
from datetime import datetime

# 輸入路徑
P112_PATH = "data/mlb_2026/derived/p112_lane_a_market_contract_gap_review_summary.json"
P101_PATH = "data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json"

# 輸出路徑
OUT_PATH = "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json"


def main():
    with open(P112_PATH, "r", encoding="utf-8") as f:
        p112 = json.load(f)
    with open(P101_PATH, "r", encoding="utf-8") as f:
        p101 = json.load(f)

    fixture = {
        "fixture_metadata": {
            "fixture_version": "P113.20260531",
            "generated_at": datetime.now().strftime("%Y-%m-%d"),
            "source_gap_review_version": "P112.20260531",
            "final_classification": "P113_MARKET_CONTRACT_SCHEMA_FIXTURE_READY_WITH_BLOCKERS"
        },
        "source_gap_review_reference": {
            "gap_review_path": P112_PATH,
            "gap_review_version": "P112.20260531",
            "final_classification": p112.get("final_classification")
        },
        "market_contracts": [],
        "required_prediction_fields": ["game_id", "predicted_side"],
        "required_odds_fields": ["odds"],
        "required_source_trace_fields": ["source_trace", "source_prediction_version"],
        "required_timestamp_fields": ["game_date", "outcome_finalized_at"],
        "required_outcome_fields": ["actual_winner", "is_correct", "result_home_score", "result_away_score"],
        "blocked_fields": ["ev", "clv", "kelly", "stake", "recommendation"],
        "governance_locks": p112["governance"],
        "allowed_future_actions": ["diagnostic_tracking_only"],
        "prohibited_actions": ["production", "recommendation", "betting", "odds", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"],
        "validation_rules": [
            "No market may output a recommendation.",
            "No market may compute EV, CLV, Kelly, stake size, or production readiness.",
            "Moneyline may be schema-ready but still blocked by missing legal odds.",
            "Run line, total runs, and first five innings must remain blocked or partial unless source data clearly supports them.",
            "Taiwan Sports Lottery recommendation must remain false.",
            "Production readiness must remain false."
        ]
    }

    # 依據 P101 與 P112 gap，產生 market_contracts
    market_types = [
        ("moneyline_winner", "Moneyline Winner", "moneyline"),
        ("run_line_handicap", "Run Line Handicap", "run_line"),
        ("total_runs_over_under", "Total Runs Over/Under", "total_runs"),
        ("first_five_innings_if_supported_later", "First Five Innings (if supported later)", "first_five_innings"),
        ("unsupported_market_placeholder", "Unsupported Market Placeholder", "unsupported")
    ]
    gap_map = {g["market_type"]: g for g in p112["market_gaps"]}
    for market_id, market_name, market_type in market_types:
        gap = gap_map.get(market_type)
        contract = {
            "market_id": market_id,
            "market_name": market_name,
            "market_type": market_type,
            "supported_status": gap is not None and gap["gap_type"] != "market_not_supported",
            "prediction_side_options": ["home", "away"],
            "required_prediction_fields": gap["required_fields"] if gap else [],
            "required_legal_odds_fields": ["odds"],
            "required_source_trace": True,
            "required_timestamp_fields": ["game_date", "outcome_finalized_at"],
            "required_outcome_fields": ["actual_winner", "is_correct", "result_home_score", "result_away_score"],
            "current_blockers": [],
            "readiness_status": "blocked" if gap and gap["gap_type"] != "" else "partial",
            "allowed_next_action": "diagnostic_tracking_only",
            "prohibited_action": ["production", "recommendation", "betting", "odds", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"]
        }
        # Blocker categories
        blockers = []
        if gap:
            if gap["gap_type"] == "missing_odds":
                blockers.append("LEGAL_ODDS_SOURCE_BLOCKER")
            if gap["gap_type"] == "market_not_supported":
                blockers.append("MARKET_SCHEMA_BLOCKER")
        if market_type == "moneyline":
            blockers.append("GOVERNANCE_PRODUCTION_BLOCKER")
            blockers.append("EV_CLV_NOT_ALLOWED_BLOCKER")
        contract["current_blockers"] = blockers
        fixture["market_contracts"].append(contract)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(fixture, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
