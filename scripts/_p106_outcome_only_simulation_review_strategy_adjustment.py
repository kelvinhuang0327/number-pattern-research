import json
from pathlib import Path

# 載入 P105/P104/P103/P102 summary
p105 = json.load(open("data/mlb_2026/derived/p105_outcome_only_score_simulation_runner_summary.json"))
p104 = json.load(open("data/mlb_2026/derived/p104_outcome_only_score_simulation_design_summary.json"))
p103 = json.load(open("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json"))
p102 = json.load(open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json"))

# 策略列表
strategies = list(p105["strategies"].keys())
adjustment_plan = {}
strongest = None
strongest_hit = -1
weakest = None
weakest_hit = 2
sample_limited = []

for s in strategies:
    strat = p105["strategies"][s]
    hit = strat.get("hit_rate", 0)
    n = strat.get("eligible_rows", 0)
    # 決策邏輯
    if s == "HIGH_FIP":
        decision = "TRACK_DIAGNOSTIC"
        rationale = "高命中率且樣本數足夠，維持診斷追蹤。"
    elif s in ("MID_FIP", "LOW_FIP"):
        decision = "WATCH_ONLY"
        rationale = "樣本數或穩定性不足，僅觀察不升級。"
    elif n < 100:
        decision = "NEED_MORE_SAMPLE"
        rationale = "樣本數過少，需更多資料。"
        sample_limited.append(s)
    else:
        decision = "WATCH_ONLY"
        rationale = "維持觀察，暫不升級。"
    # 強弱策略判斷
    if hit > strongest_hit and n >= 100:
        strongest = s
        strongest_hit = hit
    if hit < weakest_hit and n >= 100:
        weakest = s
        weakest_hit = hit
    adjustment_plan[s] = {
        "decision": decision,
        "rationale": rationale,
        "hit_rate": hit,
        "eligible_rows": n,
        "monthly_accuracy": strat.get("monthly_accuracy", {}),
        "side_split_accuracy": strat.get("side_split_accuracy", {}),
        "average_score_margin": strat.get("average_score_margin"),
        "median_score_margin": strat.get("median_score_margin"),
        "score_margin_buckets": strat.get("score_margin_buckets", {}),
    }

# 學習調整規則
learning_rules = {
    "improvement_metric": "hit_rate >= 0.60 且樣本數 >= 150",
    "downgrade_metric": "hit_rate < 0.50 或月穩定性顯著下滑",
    "minimum_sample_threshold": 100,
    "next_data_checkpoint": "2026-06-15",
    "allowed_next_action": "維持診斷/觀察，嚴禁推薦/production/投注/EV/CLV/Kelly/台灣運彩/實盤/資料異動",
    "prohibited_action": "任何 production、推薦、投注、EV、CLV、Kelly、台灣運彩、資料異動、production_mutation"
}

# 輸出 summary
summary = {
    "date": "2026-05-31",
    "final_classification": "P106_SIMULATION_REVIEW_ADJUSTMENT_READY_DIAGNOSTIC_ONLY",
    "adjustment_plan": adjustment_plan,
    "strongest_strategy": strongest,
    "weakest_strategy": weakest,
    "sample_limited_strategies": sample_limited,
    "learning_rules": learning_rules,
    "governance": {
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
        "recommendation_allowed": False,
        "product_surface_allowed": False,
        "odds_used": False,
        "ev_computed": False,
        "clv_computed": False,
        "kelly_computed": False,
        "stake_sizing": False,
        "taiwan_lottery_recommendation": False,
        "champion_replacement": False,
        "production_mutation": False,
        "calibration_refit": False,
        "live_api_calls": 0,
        "paid_api_calls": 0,
        "canonical_rows_modified": False,
        "outcome_rows_modified": False,
        "p83e_mapping_modified": False
    },
    "next_implementation_target": "P107 Outcome-Only Strategy Adjustment Backlog"
}

Path("data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print("[P106] Outcome-Only Simulation Review & Strategy Adjustment summary written.")
