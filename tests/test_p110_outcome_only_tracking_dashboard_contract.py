# -*- coding: utf-8 -*-
"""
P110 Outcome-Only Tracking Dashboard Contract 測試
- 僅驗證合約/schema，不測 production/betting/odds/EV/Kelly
- 僅允許讀寫 P110 whitelist 檔案
"""
import os
import json
import pytest

P109_PATH = "data/mlb_2026/derived/p109_outcome_only_tracking_drift_snapshot_summary.json"
P110_PATH = "data/mlb_2026/derived/p110_outcome_only_tracking_dashboard_contract_summary.json"

@pytest.mark.order(1)
def test_p109_summary_exists_and_classification():
    assert os.path.exists(P109_PATH), "P109 summary missing"
    with open(P109_PATH, "r", encoding="utf-8") as f:
        p109 = json.load(f)
    drift = p109["drift_snapshot"]
    # 檢查四個策略
    for k in ["HIGH_FIP", "MID_FIP", "LOW_FIP", "ALL_ROWS"]:
        assert k in drift, f"P109 drift snapshot missing {k}"
    # 檢查 drift_status
    assert drift["HIGH_FIP"].get("drift_status") == "DRIFT_BLOCKED_BY_SAMPLE"
    assert drift["MID_FIP"].get("drift_status") == "DRIFT_BLOCKED_BY_SAMPLE"
    assert drift["LOW_FIP"].get("drift_status") == "DRIFT_BLOCKED_BY_SAMPLE"
    assert drift["ALL_ROWS"].get("drift_status") == "STABLE_DIAGNOSTIC"

@pytest.mark.order(2)
def test_p110_summary_json_generated():
    assert os.path.exists(P110_PATH), "P110 summary JSON not generated"
    with open(P110_PATH, "r", encoding="utf-8") as f:
        p110 = json.load(f)
    assert "dashboard_metadata" in p110
    assert "strategy_tracking_cards" in p110
    assert "drift_snapshot_table" in p110
    assert "sample_limit_panel" in p110
    assert "watch_only_panel" in p110
    assert "blocked_production_panel" in p110
    assert "next_data_thresholds" in p110
    assert "governance_locks" in p110
    assert "allowed_filters" in p110
    assert "prohibited_actions" in p110

@pytest.mark.order(3)
def test_strategy_cards_and_panels():
    with open(P110_PATH, "r", encoding="utf-8") as f:
        p110 = json.load(f)
    cards = {c["strategy_id"]: c for c in p110["strategy_tracking_cards"]}
    # 四個策略卡
    for sid in ["HIGH_FIP", "MID_FIP", "LOW_FIP", "ALL_ROWS"]:
        assert sid in cards
    # HIGH_FIP 僅 diagnostic_only
    assert cards["HIGH_FIP"]["tracking_status"] == "diagnostic_only"
    assert "recommendation" in cards["HIGH_FIP"]["prohibited_actions"]
    # MID/LOW 僅 watch_only
    assert cards["MID_FIP"]["tracking_status"] == "watch_only"
    assert cards["LOW_FIP"]["tracking_status"] == "watch_only"
    # ALL_ROWS 為 baseline_diagnostic
    assert cards["ALL_ROWS"]["tracking_status"] == "baseline_diagnostic"
    # sample_limit_panel
    assert set(p110["sample_limit_panel"]["strategies"]) == {"HIGH_FIP", "MID_FIP", "LOW_FIP"}
    # watch_only_panel
    assert set(p110["watch_only_panel"]["strategies"]) == {"MID_FIP", "LOW_FIP"}
    # blocked_production_panel
    for sid in ["HIGH_FIP", "MID_FIP", "LOW_FIP", "ALL_ROWS"]:
        assert sid in p110["blocked_production_panel"]["strategies"]

@pytest.mark.order(4)
def test_governance_flags():
    with open(P110_PATH, "r", encoding="utf-8") as f:
        p110 = json.load(f)
    g = p110["governance_locks"]
    assert g["paper_only"] is True
    assert g["diagnostic_only"] is True
    assert g["production_ready"] is False
    assert g["real_bet_allowed"] is False
    assert g["recommendation_allowed"] is False
    assert g["odds_used"] is False
    assert g["ev_computed"] is False
    assert g["kelly_computed"] is False
    assert g["ui_modified"] is False

@pytest.mark.order(5)
def test_final_classification():
    with open(P110_PATH, "r", encoding="utf-8") as f:
        p110 = json.load(f)
    c = p110["dashboard_metadata"]["final_classification"]
    assert c in [
        "P110_TRACKING_DASHBOARD_CONTRACT_READY_DIAGNOSTIC_ONLY",
        "P110_TRACKING_DASHBOARD_CONTRACT_READY_WITH_SAMPLE_LIMITS",
        "P110_TRACKING_DASHBOARD_CONTRACT_BLOCKED_BY_MISSING_P109",
        "P110_TRACKING_DASHBOARD_CONTRACT_FAILED_VALIDATION"
    ]
    assert c == "P110_TRACKING_DASHBOARD_CONTRACT_READY_DIAGNOSTIC_ONLY"
