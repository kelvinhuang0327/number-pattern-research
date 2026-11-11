import json
from pathlib import Path

def test_p106_summary_exists_and_classification():
    p106 = json.load(open("data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json"))
    assert p106["final_classification"] == "P106_SIMULATION_REVIEW_ADJUSTMENT_READY_DIAGNOSTIC_ONLY"

def test_p107_summary_generated():
    path = Path("data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["final_classification"].startswith("P107_STRATEGY_ADJUSTMENT_BACKLOG_READY")

def test_backlog_categories():
    data = json.load(open("data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json"))
    backlog = data["backlog"]
    assert "IMMEDIATE_DIAGNOSTIC_TRACKING" in backlog
    assert "WATCH_ONLY_CONTINUE" in backlog
    assert "SAMPLE_LIMITED_WAIT_FOR_DATA" in backlog
    assert "PAUSE_OPTIMIZATION" in backlog
    assert "REJECT_FOR_NOW" in backlog
    assert "BLOCKED_PRODUCTION" in backlog

def test_high_fip_is_diagnostic_tracking():
    data = json.load(open("data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json"))
    found = False
    for item in data["backlog"]["IMMEDIATE_DIAGNOSTIC_TRACKING"]:
        if item["strategy_id"] == "HIGH_FIP":
            found = True
            assert item["source_decision"] == "TRACK_DIAGNOSTIC"
    assert found

def test_mid_low_all_rows_watch_only():
    data = json.load(open("data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json"))
    found_mid = found_low = found_all = False
    for item in data["backlog"]["WATCH_ONLY_CONTINUE"]:
        if item["strategy_id"] == "MID_FIP":
            found_mid = True
        if item["strategy_id"] == "LOW_FIP":
            found_low = True
        if item["strategy_id"] == "ALL_ROWS":
            found_all = True
    assert found_mid and found_low and found_all

def test_governance_flags():
    data = json.load(open("data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json"))
    gov = data["governance"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["production_ready"] is False
    assert gov["odds_used"] is False
    assert gov["ev_computed"] is False
    assert gov["kelly_computed"] is False
    assert gov["taiwan_lottery_recommendation"] is False
    assert gov["production_mutation"] is False
    assert gov["canonical_rows_modified"] is False
    assert gov["outcome_rows_modified"] is False
    assert gov["p83e_mapping_modified"] is False
