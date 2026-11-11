import json
import pytest
from pathlib import Path

def test_p101_summary_exists():
    assert Path("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json").exists()
    with open("data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["classification"].startswith("P101_TWO_LANE_ROADMAP_READY")

def test_p84e_rows_exist():
    assert Path("data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl").exists()
    with open("data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl", encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]
    assert len(lines) > 0

def test_p102_summary_generated():
    assert Path("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json").exists()
    with open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    assert "scorecard" in summary
    assert "comparison_matrix" in summary
    assert "learning_recommendation" in summary

def test_scorecard_keys():
    with open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    sc = summary["scorecard"]
    assert "ALL_ROWS" in sc
    assert "HIGH_FIP" in sc
    assert "MID_FIP" in sc
    assert "LOW_FIP" in sc

def test_high_fip_diagnostic():
    with open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    sc = summary["scorecard"]
    assert sc["HIGH_FIP"]["diagnostic_status"] == "diagnostic_only"

def test_mid_low_watch_only():
    with open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    sc = summary["scorecard"]
    assert sc["MID_FIP"]["diagnostic_status"] == "watch_only"
    assert sc["LOW_FIP"]["diagnostic_status"] == "watch_only"

def test_primary_shadow_tier_flags():
    with open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    sc = summary["scorecard"]
    # Should not error if missing, but if present, must have n and hit_rate
    for k in ["PRIMARY_125", "SHADOW_100", "TIER_A", "TIER_B"]:
        if k in sc:
            assert "n" in sc[k]
            assert "hit_rate" in sc[k]

def test_comparison_matrix_and_learning():
    with open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    assert "comparison_matrix" in summary
    assert "learning_recommendation" in summary

def test_governance_flags():
    with open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json", encoding="utf-8") as f:
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
    with open("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["classification"] in [
        "P102_OUTCOME_ONLY_SCORECARD_READY_DIAGNOSTIC_ONLY",
        "P102_OUTCOME_ONLY_SCORECARD_READY_WITH_SAMPLE_LIMITS",
        "P102_OUTCOME_ONLY_SCORECARD_BLOCKED_BY_MISSING_ARTIFACTS",
        "P102_OUTCOME_ONLY_SCORECARD_FAILED_VALIDATION"
    ]
