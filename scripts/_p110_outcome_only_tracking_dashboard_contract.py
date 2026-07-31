# -*- coding: utf-8 -*-
"""
P110 Outcome-Only Tracking Dashboard Contract Generator

- 依據 P109 drift snapshot 與上游診斷產物，產生 dashboard-ready contract/schema
- 僅限 diagnostic/paper-only，無 production、無 betting、無 odds/EV/Kelly
- 僅產生 data contract，不含 UI、不含推薦、不含 production flag
- 僅允許寫入 P110 whitelist 檔案
"""
import json
import datetime

# 檔案路徑
P109_PATH = "data/mlb_2026/derived/p109_outcome_only_tracking_drift_snapshot_summary.json"
P110_PATH = "data/mlb_2026/derived/p110_outcome_only_tracking_dashboard_contract_summary.json"
REPORT_PATH = "report/p110_outcome_only_tracking_dashboard_contract_20260531.md"

with open(P109_PATH, "r", encoding="utf-8") as f:
    p109 = json.load(f)
drift = p109["drift_snapshot"]

# 合約產生日期
today = datetime.date.today().isoformat()

# 合約 metadata
dashboard_metadata = {
    "contract_version": "P110.20260531",
    "generated_at": today,
    "source_phase": "P109",
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
        "p83e_mapping_modified": False,
        "ui_modified": False
    },
    "final_classification": "P110_TRACKING_DASHBOARD_CONTRACT_READY_DIAGNOSTIC_ONLY"
}

data_sources = [
    P109_PATH,
    "data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json",
    "data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json",
    "data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json",
    "data/mlb_2026/derived/p105_outcome_only_score_simulation_runner_summary.json",
    "data/mlb_2026/derived/p104_outcome_only_score_simulation_design_summary.json",
    "data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json",
    "data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json",
    "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
]

# 策略卡片定義
strategy_cards = [
    {
        "strategy_id": "HIGH_FIP",
        "display_name": "高 FIP 策略",
        "tracking_status": "diagnostic_only",
        "latest_hit_rate": drift["HIGH_FIP"].get("latest_month_hit_rate"),
        "eligible_rows": drift["HIGH_FIP"].get("eligible_rows", 0),
        "monthly_hit_rates": drift["HIGH_FIP"].get("monthly_hit_rate", {}),
        "drift_status": drift["HIGH_FIP"].get("drift_status", "UNKNOWN"),
        "sample_status": "sample_limited",
        "next_check_trigger": drift["HIGH_FIP"].get("next_check_trigger", "需累積更多樣本數，僅允許診斷追蹤"),
        "allowed_next_action": "diagnostic_tracking_only",
        "prohibited_actions": ["recommendation", "production", "betting", "odds", "ev", "kelly"]
    },
    {
        "strategy_id": "MID_FIP",
        "display_name": "中 FIP 策略",
        "tracking_status": "watch_only",
        "latest_hit_rate": drift["MID_FIP"].get("latest_month_hit_rate"),
        "eligible_rows": drift["MID_FIP"].get("eligible_rows", 0),
        "monthly_hit_rates": drift["MID_FIP"].get("monthly_hit_rate", {}),
        "drift_status": drift["MID_FIP"].get("drift_status", "UNKNOWN"),
        "sample_status": "sample_limited",
        "next_check_trigger": drift["MID_FIP"].get("next_check_trigger", "需累積更多樣本數，僅允許觀察"),
        "allowed_next_action": "watch_only",
        "prohibited_actions": ["recommendation", "production", "betting", "odds", "ev", "kelly"]
    },
    {
        "strategy_id": "LOW_FIP",
        "display_name": "低 FIP 策略",
        "tracking_status": "watch_only",
        "latest_hit_rate": drift["LOW_FIP"].get("latest_month_hit_rate"),
        "eligible_rows": drift["LOW_FIP"].get("eligible_rows", 0),
        "monthly_hit_rates": drift["LOW_FIP"].get("monthly_hit_rate", {}),
        "drift_status": drift["LOW_FIP"].get("drift_status", "UNKNOWN"),
        "sample_status": "sample_limited",
        "next_check_trigger": drift["LOW_FIP"].get("next_check_trigger", "需累積更多樣本數，僅允許觀察"),
        "allowed_next_action": "watch_only",
        "prohibited_actions": ["recommendation", "production", "betting", "odds", "ev", "kelly"]
    },
    {
        "strategy_id": "ALL_ROWS",
        "display_name": "全樣本基線",
        "tracking_status": "baseline_diagnostic",
        "latest_hit_rate": drift["ALL_ROWS"].get("latest_month_hit_rate"),
        "eligible_rows": drift["ALL_ROWS"].get("eligible_rows", 0),
        "monthly_hit_rates": drift["ALL_ROWS"].get("monthly_hit_rate", {}),
        "drift_status": drift["ALL_ROWS"].get("drift_status", "UNKNOWN"),
        "sample_status": "stable_diagnostic",
        "next_check_trigger": drift["ALL_ROWS"].get("next_check_trigger", "僅供基線參考，不可推進推薦/production"),
        "allowed_next_action": "diagnostic_tracking_only",
        "prohibited_actions": ["recommendation", "production", "betting", "odds", "ev", "kelly"]
    }
]

# drift snapshot table
drift_snapshot_table = drift

# panels
sample_limit_panel = {
    "strategies": [s["strategy_id"] for s in strategy_cards if s["sample_status"] == "sample_limited"]
}
watch_only_panel = {
    "strategies": [s["strategy_id"] for s in strategy_cards if s["tracking_status"] == "watch_only"]
}
blocked_production_panel = {
    "strategies": [s["strategy_id"] for s in strategy_cards if "production" in s["prohibited_actions"]]
}
next_data_thresholds = {
    "HIGH_FIP": 100,
    "MID_FIP": 100,
    "LOW_FIP": 100
}
governance_locks = dashboard_metadata["governance"]
allowed_filters = ["strategy_id", "drift_status", "sample_status"]
prohibited_actions = ["recommendation", "production", "betting", "odds", "ev", "kelly"]

# 合約主體
dashboard_contract = {
    "dashboard_metadata": dashboard_metadata,
    "data_sources": data_sources,
    "strategy_tracking_cards": strategy_cards,
    "drift_snapshot_table": drift_snapshot_table,
    "sample_limit_panel": sample_limit_panel,
    "watch_only_panel": watch_only_panel,
    "blocked_production_panel": blocked_production_panel,
    "next_data_thresholds": next_data_thresholds,
    "governance_locks": governance_locks,
    "allowed_filters": allowed_filters,
    "prohibited_actions": prohibited_actions
}

# 輸出 JSON 合約
with open(P110_PATH, "w", encoding="utf-8") as f:
    json.dump(dashboard_contract, f, ensure_ascii=False, indent=2)

# 產生簡要報告
with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write(f"""# P110 Outcome-Only Tracking Dashboard Contract (2026-05-31)

- 合約版本: P110.20260531
- 產生日期: {today}
- 上游來源: P109 drift snapshot
- 最終分類: {dashboard_metadata['final_classification']}
- 策略卡片: {[s['strategy_id'] for s in strategy_cards]}
- sample_limit_panel: {sample_limit_panel['strategies']}
- watch_only_panel: {watch_only_panel['strategies']}
- blocked_production_panel: {blocked_production_panel['strategies']}
- governance: {dashboard_metadata['governance']}

本合約僅供診斷追蹤與 paper-only 報告用途，嚴禁用於 production、推薦、賠率、EV、Kelly、真實下注。
""")

print(f"[P110] Dashboard contract generated: {P110_PATH}")
print(f"[P110] Report generated: {REPORT_PATH}")
