import json
import pytest
from pathlib import Path

def test_artifacts_exist():
    assert Path("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json").exists(), "Summary JSON missing"
    assert Path("report/p101_two_lane_product_roadmap_realignment_20260531.md").exists(), "Report MD missing"
    assert Path("scripts/_p101_two_lane_product_roadmap_realignment.py").exists(), "Script missing"
    assert Path("00-Plan/roadmap/active_task.md").exists(), "Active task MD missing"

def test_two_lane_structure():
    with open("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    assert "lane_a" in summary and "lane_b" in summary
    assert summary["lane_a"]["title"].startswith("Taiwan Sports Lottery")
    assert summary["lane_b"]["title"].startswith("Outcome-Only")

def test_lane_a_contract():
    with open("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    lane_a = summary["lane_a"]
    assert any(m["type"] == "moneyline" and m["supported"] for m in lane_a["markets"])
    assert lane_a["recommendation_allowed"] is False
    assert lane_a["required_source_trace"]
    assert lane_a["required_odds_fields"]

def test_lane_a_blocks_without_odds():
    with open("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    lane_a = summary["lane_a"]
    for m in lane_a["markets"]:
        if not m["supported"]:
            assert "blocked_reason" in m

def test_lane_b_backtest_plan():
    with open("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    lane_b = summary["lane_b"]
    assert "HIGH_FIP_diagnostic_segment" in lane_b["strategies"]
    assert "MID_FIP_watch_only" in lane_b["strategies"]
    assert "LOW_FIP_watch_only" in lane_b["strategies"]
    assert "hit_rate" in lane_b["scorecard_fields"]
    assert lane_b["strategy_comparison_matrix"]
    assert lane_b["learning_loop_proposal"]
    assert not lane_b["calibration_refit"]
    assert not lane_b["production_mutation"]

def test_governance_flags():
    with open("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    g = summary["governance"]
    assert g["paper_only"]
    assert g["diagnostic_only"]
    assert not g["production_ready"]
    assert not g["recommendation_allowed"]
    assert not g["odds_used"]
    assert not g["ev_computed"]
    assert not g["clv_computed"]
    assert not g["kelly_computed"]
    assert not g["stake_sizing"]

def test_final_classification():
    with open("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["classification"] in [
        "P101_TWO_LANE_ROADMAP_READY_DIAGNOSTIC_ONLY",
        "P101_TWO_LANE_ROADMAP_BLOCKED_BY_MISSING_ARTIFACTS",
        "P101_TWO_LANE_ROADMAP_FAILED_VALIDATION"
    ]
