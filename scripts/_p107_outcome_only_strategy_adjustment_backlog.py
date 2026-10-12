import json
from pathlib import Path

# 載入 P106 summary
p106 = json.load(open("data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json"))
adjustment_plan = p106["adjustment_plan"]

backlog = {
    "IMMEDIATE_DIAGNOSTIC_TRACKING": [],
    "WATCH_ONLY_CONTINUE": [],
    "SAMPLE_LIMITED_WAIT_FOR_DATA": [],
    "PAUSE_OPTIMIZATION": [],
    "REJECT_FOR_NOW": [],
    "BLOCKED_PRODUCTION": []
}

for strat, info in adjustment_plan.items():
    n = info.get("eligible_rows", 0)
    hit = info.get("hit_rate", 0)
    dec = info["decision"]
    # backlog_id
    backlog_id = f"P107_{strat}"
    evidence = f"hit_rate={hit:.3f}, n={n}, monthly={info.get('monthly_accuracy',{})}"
    allowed_scope = "diagnostic_only"
    prohibited_scope = "production, betting, odds, EV, CLV, Kelly, stake sizing, 台灣運彩, mutation"
    data_threshold = 150 if dec == "TRACK_DIAGNOSTIC" else 100
    test_requirement = "diagnostic test coverage, no production"
    governance_requirement = "paper_only, diagnostic_only, production_ready=false"
    priority = 1 if strat == "HIGH_FIP" else (2 if dec == "WATCH_ONLY" else 3)
    item = {
        "backlog_id": backlog_id,
        "strategy_id": strat,
        "source_decision": dec,
        "evidence_summary": evidence,
        "required_next_action": "持續診斷追蹤" if dec=="TRACK_DIAGNOSTIC" else "維持觀察" if dec=="WATCH_ONLY" else "等待樣本/暫停/拒絕/阻擋",
        "allowed_scope": allowed_scope,
        "prohibited_scope": prohibited_scope,
        "data_threshold": data_threshold,
        "test_requirement": test_requirement,
        "governance_requirement": governance_requirement,
        "priority": priority
    }
    if strat == "HIGH_FIP" and dec == "TRACK_DIAGNOSTIC":
        backlog["IMMEDIATE_DIAGNOSTIC_TRACKING"].append(item)
    elif dec == "WATCH_ONLY":
        backlog["WATCH_ONLY_CONTINUE"].append(item)
    elif dec == "NEED_MORE_SAMPLE":
        backlog["SAMPLE_LIMITED_WAIT_FOR_DATA"].append(item)
    elif dec == "PAUSE_OPTIMIZATION":
        backlog["PAUSE_OPTIMIZATION"].append(item)
    elif dec == "REJECT_FOR_NOW":
        backlog["REJECT_FOR_NOW"].append(item)
    elif dec == "BLOCKED_PRODUCTION":
        backlog["BLOCKED_PRODUCTION"].append(item)

summary = {
    "date": "2026-05-31",
    "final_classification": "P107_STRATEGY_ADJUSTMENT_BACKLOG_READY_DIAGNOSTIC_ONLY",
    "backlog": backlog,
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
    "next_implementation_target": "P108 Outcome-Only Diagnostic Tracking Report"
}

Path("data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print("[P107] Outcome-Only Strategy Adjustment Backlog summary written.")
