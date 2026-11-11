# -*- coding: utf-8 -*-
"""
P111 Outcome-Only Tracking Dashboard Fixture 測試
- 僅驗證 fixture/schema，不測 production/betting/odds/EV/Kelly
- 僅允許讀寫 P111 whitelist 檔案
"""
import os
import json
import pytest

P110_PATH = "data/mlb_2026/derived/p110_outcome_only_tracking_dashboard_contract_summary.json"
P111_PATH = "data/mlb_2026/derived/p111_outcome_only_tracking_dashboard_fixture_summary.json"

@pytest.mark.order(1)
def test_p110_summary_exists_and_classification():
    assert os.path.exists(P110_PATH), "P110 summary missing"
    with open(P110_PATH, "r", encoding="utf-8") as f:
        p110 = json.load(f)
    assert p110["dashboard_metadata"]["final_classification"] == "P110_TRACKING_DASHBOARD_CONTRACT_READY_DIAGNOSTIC_ONLY"

@pytest.mark.order(2)
def test_p111_summary_json_generated():
    assert os.path.exists(P111_PATH), "P111 fixture JSON not generated"
    with open(P111_PATH, "r", encoding="utf-8") as f:
        p111 = json.load(f)
    assert "fixture_metadata" in p111
    assert "dashboard_payload" in p111
    assert "strategy_cards" in p111
    assert "summary_panels" in p111
    assert "drift_table_rows" in p111
    assert "filter_options" in p111
    assert "governance_banner" in p111
    assert "blocked_actions" in p111
    assert "empty_state_messages" in p111
    assert "validation_contract" in p111

@pytest.mark.order(3)
def test_strategy_cards_and_panels():
    with open(P111_PATH, "r", encoding="utf-8") as f:
        p111 = json.load(f)
    cards = {c["strategy_id"]: c for c in p111["strategy_cards"]}
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
    # summary_panels
    assert set(p111["summary_panels"]["sample_limit"]) == {"HIGH_FIP", "MID_FIP", "LOW_FIP"}
    assert set(p111["summary_panels"]["watch_only"]) == {"MID_FIP", "LOW_FIP"}
    for sid in ["HIGH_FIP", "MID_FIP", "LOW_FIP", "ALL_ROWS"]:
        assert sid in p111["summary_panels"]["blocked_production"]

@pytest.mark.order(4)
def test_governance_banner_and_flags():
    with open(P111_PATH, "r", encoding="utf-8") as f:
        p111 = json.load(f)
    banner = p111["governance_banner"]
    assert "嚴禁用於 production" in banner
    g = p111["validation_contract"]["governance"]
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
    with open(P111_PATH, "r", encoding="utf-8") as f:
        p111 = json.load(f)
    c = p111["fixture_metadata"]["final_classification"]
    assert c in [
        "P111_TRACKING_DASHBOARD_FIXTURE_READY_DIAGNOSTIC_ONLY",
        "P111_TRACKING_DASHBOARD_FIXTURE_READY_WITH_SAMPLE_LIMITS",
        "P111_TRACKING_DASHBOARD_FIXTURE_BLOCKED_BY_MISSING_P110",
        "P111_TRACKING_DASHBOARD_FIXTURE_FAILED_VALIDATION"
    ]
    assert c == "P111_TRACKING_DASHBOARD_FIXTURE_READY_DIAGNOSTIC_ONLY"
