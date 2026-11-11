import json
from pathlib import Path

def test_p107_summary_exists_and_classification():
    path = Path("data/mlb_2026/derived/p107_outcome_only_strategy_adjustment_backlog_summary.json")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["final_classification"] == "P107_STRATEGY_ADJUSTMENT_BACKLOG_READY_DIAGNOSTIC_ONLY"

def test_p108_summary_generated():
    path = Path("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["final_classification"].startswith("P108_DIAGNOSTIC_TRACKING_REPORT_READY")

def test_active_diagnostic_tracking():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    assert "active_diagnostic_tracking" in data
    assert any(item["strategy_id"] == "HIGH_FIP" for item in data["active_diagnostic_tracking"])

def test_watch_only_tracking():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    assert "watch_only_tracking" in data
    found = [item["strategy_id"] for item in data["watch_only_tracking"]]
    assert "MID_FIP" in found and "LOW_FIP" in found and "ALL_ROWS" in found

def test_sample_limited_tracking_exists():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    assert "sample_limited_tracking" in data
    # May be empty, but must exist

def test_paused_or_rejected_tracking_exists():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    assert "paused_or_rejected_tracking" in data
    # May be empty, but must exist

def test_blocked_production_items_exists():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    assert "blocked_production_items" in data
    # May be empty, but must exist

def test_governance_flags():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
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

def test_high_fip_remains_diagnostic_only():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    found = False
    for item in data["active_diagnostic_tracking"]:
        if item["strategy_id"] == "HIGH_FIP":
            found = True
            assert item["allowed_scope"] == "diagnostic_only"
            assert "production" in item["prohibited_scope"]
    assert found

def test_mid_low_all_rows_watch_only():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    found_mid = found_low = found_all = False
    for item in data["watch_only_tracking"]:
        if item["strategy_id"] == "MID_FIP":
            found_mid = True
        if item["strategy_id"] == "LOW_FIP":
            found_low = True
        if item["strategy_id"] == "ALL_ROWS":
            found_all = True
    assert found_mid and found_low and found_all

def test_next_data_thresholds():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    thresholds = data["next_data_thresholds"]
    assert "HIGH_FIP" in thresholds
    assert "MID_FIP" in thresholds
    assert "LOW_FIP" in thresholds
    assert "ALL_ROWS" in thresholds

def test_final_classification_valid():
    data = json.load(open("data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json"))
    assert data["final_classification"].startswith("P108_DIAGNOSTIC_TRACKING_REPORT_READY")
