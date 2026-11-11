"""
P103 Outcome-Only Strategy Learning Matrix 測試
"""
import json
from pathlib import Path

def test_p103_summary_exists():
    path = Path("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
    assert path.exists(), "P103 summary JSON 檔案不存在"
    with path.open() as f:
        data = json.load(f)
    assert data["final_classification"].startswith("P103_STRATEGY_LEARNING_MATRIX"), "final_classification 不正確"
    assert data["governance"]["paper_only"] is True
    assert data["governance"]["diagnostic_only"] is True
    assert data["governance"]["production_ready"] is False
    assert data["governance"]["recommendation_allowed"] is False
    assert data["governance"]["odds_used"] is False
    assert data["governance"]["ev_computed"] is False
    assert data["governance"]["clv_computed"] is False
    assert data["governance"]["kelly_computed"] is False
    assert data["governance"]["stake_sizing"] is False

def test_p103_matrix_decisions():
    path = Path("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
    with path.open() as f:
        data = json.load(f)
    matrix = data["matrix"]
    for entry in matrix:
        if entry["strategy_id"] == "HIGH_FIP":
            assert entry["current_decision"] == "TRACK_DIAGNOSTIC"
        elif entry["strategy_id"] in ("MID_FIP", "LOW_FIP"):
            assert entry["current_decision"] == "WATCH_ONLY"
        else:
            assert entry["current_decision"] == "WATCH_ONLY"
        assert entry["current_decision"] != "PRODUCTION"
        assert entry["current_decision"] != "RECOMMENDATION"

def test_p103_learning_loop():
    path = Path("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
    with path.open() as f:
        data = json.load(f)
    loop = data["learning_loop"]
    assert "metric" in loop
    assert "re_evaluation_trigger" in loop
    assert "allowed_next_action" in loop
    assert "prohibited_action" in loop

def test_p103_strongest_signal():
    path = Path("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
    with path.open() as f:
        data = json.load(f)
    assert data["strongest_signal"] == "HIGH_FIP"

def test_p103_watch_only():
    path = Path("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
    with path.open() as f:
        data = json.load(f)
    assert "MID_FIP" in data["watch_only"]
    assert "LOW_FIP" in data["watch_only"]
