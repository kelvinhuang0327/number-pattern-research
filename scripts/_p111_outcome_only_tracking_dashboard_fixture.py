# -*- coding: utf-8 -*-
"""
P111 Outcome-Only Tracking Dashboard Fixture Generator
- 依據 P110 dashboard contract，產生靜態 dashboard-ready fixture
- 僅限 diagnostic/paper-only，無 production、無 betting、無 odds/EV/Kelly
- 僅產生 fixture，不含 UI、不含推薦、不含 production flag
- 僅允許寫入 P111 whitelist 檔案
"""
import json
import datetime

P110_PATH = "data/mlb_2026/derived/p110_outcome_only_tracking_dashboard_contract_summary.json"
P111_PATH = "data/mlb_2026/derived/p111_outcome_only_tracking_dashboard_fixture_summary.json"
REPORT_PATH = "report/p111_outcome_only_tracking_dashboard_fixture_20260531.md"

with open(P110_PATH, "r", encoding="utf-8") as f:
    p110 = json.load(f)

# Metadata
fixture_metadata = {
    "fixture_version": "P111.20260531",
    "generated_at": datetime.date.today().isoformat(),
    "source_contract_version": p110["dashboard_metadata"]["contract_version"],
    "final_classification": "P111_TRACKING_DASHBOARD_FIXTURE_READY_DIAGNOSTIC_ONLY"
}

source_contract_reference = {
    "contract_path": P110_PATH,
    "contract_version": p110["dashboard_metadata"]["contract_version"],
    "final_classification": p110["dashboard_metadata"]["final_classification"]
}

governance_banner = (
    "本 fixture 僅供診斷追蹤與 paper-only 報告用途，嚴禁用於 production、推薦、賠率、EV、CLV、Kelly、真實下注。"
)

# Strategy cards with display_badges
strategy_cards = []
for card in p110["strategy_tracking_cards"]:
    badges = []
    if card["tracking_status"] == "diagnostic_only":
        badges.append("診斷追蹤")
    if card["tracking_status"] == "watch_only":
        badges.append("觀察中")
    if card["sample_status"] == "sample_limited":
        badges.append("樣本數不足")
    if card["drift_status"] == "DRIFT_BLOCKED_BY_SAMPLE":
        badges.append("樣本受限")
    if card["tracking_status"] == "baseline_diagnostic":
        badges.append("基線")
    strategy_cards.append({
        **card,
        "display_badges": badges
    })

# Panels
summary_panels = {
    "sample_limit": [c["strategy_id"] for c in strategy_cards if "樣本數不足" in c["display_badges"]],
    "watch_only": [c["strategy_id"] for c in strategy_cards if c["tracking_status"] == "watch_only"],
    "blocked_production": [c["strategy_id"] for c in strategy_cards if "production" in c["prohibited_actions"]]
}

dashboard_payload = {
    "strategy_cards": strategy_cards,
    "summary_panels": summary_panels
}

drift_table_rows = [
    {
        "strategy_id": c["strategy_id"],
        "drift_status": c["drift_status"],
        "sample_status": c["sample_status"],
        "eligible_rows": c["eligible_rows"]
    }
    for c in strategy_cards
]

filter_options = ["strategy_id", "drift_status", "sample_status"]
blocked_actions = ["recommendation", "production", "betting", "odds", "ev", "clv", "kelly"]
empty_state_messages = {
    "no_data": "目前無可用資料，僅供診斷追蹤用途。",
    "sample_limited": "樣本數不足，請等待更多資料累積。"
}

validation_contract = {
    "governance": p110["dashboard_metadata"]["governance"],
    "final_classification": fixture_metadata["final_classification"]
}

fixture = {
    "fixture_metadata": fixture_metadata,
    "source_contract_reference": source_contract_reference,
    "dashboard_payload": dashboard_payload,
    "strategy_cards": strategy_cards,
    "summary_panels": summary_panels,
    "drift_table_rows": drift_table_rows,
    "filter_options": filter_options,
    "governance_banner": governance_banner,
    "blocked_actions": blocked_actions,
    "empty_state_messages": empty_state_messages,
    "validation_contract": validation_contract
}

with open(P111_PATH, "w", encoding="utf-8") as f:
    json.dump(fixture, f, ensure_ascii=False, indent=2)

with open(REPORT_PATH, "w", encoding="utf-8") as f:
    f.write(f"""# P111 Outcome-Only Tracking Dashboard Fixture (2026-05-31)

- fixture_version: {fixture_metadata['fixture_version']}
- 產生日期: {fixture_metadata['generated_at']}
- 來源合約: {source_contract_reference['contract_path']}
- 最終分類: {fixture_metadata['final_classification']}
- 策略卡片: {[c['strategy_id'] for c in strategy_cards]}
- summary_panels: {summary_panels}
- governance_banner: {governance_banner}
- blocked_actions: {blocked_actions}

本 fixture 僅供診斷追蹤與 paper-only 報告用途，嚴禁用於 production、推薦、賠率、EV、CLV、Kelly、真實下注。
""")

print(f"[P111] Dashboard fixture generated: {P111_PATH}")
print(f"[P111] Report generated: {REPORT_PATH}")
