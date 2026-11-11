"""
Test for P104 Outcome-Only Score Simulation Design
"""
import json
import os
import importlib.util
from pathlib import Path

def test_p104_summary_generated():
    # 執行主程式產生 summary
    script_path = Path("scripts/_p104_outcome_only_score_simulation_design.py")
    spec = importlib.util.spec_from_file_location("p104", script_path)
    p104 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p104)
    out_path = Path("data/mlb_2026/derived/p104_outcome_only_score_simulation_design_summary.json")
    assert out_path.exists(), "P104 summary JSON 未產生"
    with out_path.open(encoding="utf-8") as f:
        summary = json.load(f)
    # 基本欄位檢查
    assert summary["final_classification"].startswith("P104_SCORE_SIMULATION_DESIGN"), "final_classification 不正確"
    assert "win_loss_simulation_by_strategy" in summary["supported_simulations"], "缺少 win_loss_simulation_by_strategy"
    assert "profit_simulation_blocked" in summary["blocked_simulations"], "未明確阻擋 profit_simulation"
    assert summary["governance"]["paper_only"] is True, "governance paper_only 必須為 True"
    assert summary["governance"]["diagnostic_only"] is True, "governance diagnostic_only 必須為 True"
    assert summary["governance"]["production_ready"] is False, "governance production_ready 必須為 False"
    assert summary["next_implementation_target"].startswith("P105"), "next_implementation_target 必須指向 P105"
    # Schema 欄位檢查
    for field in [
        "strategy_id", "eligible_rows", "predicted_side", "actual_winner", "win_loss_result", "home_score", "away_score", "score_margin", "score_margin_bucket", "accuracy_metrics", "sample_limitations"
    ]:
        assert field in summary["schema"], f"schema 缺少欄位: {field}"

def test_p103_summary_exists():
    p103_path = Path("data/mlb_2026/derived/p103_outcome_only_strategy_learning_matrix_summary.json")
    assert p103_path.exists(), "P103 summary 不存在"
    with p103_path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("final_classification", "").startswith("P103_STRATEGY_LEARNING_MATRIX_READY"), "P103 final_classification 不正確"

def test_p102_scorecard_exists():
    p102_path = Path("data/mlb_2026/derived/p102_outcome_only_strategy_backtest_scorecard_summary.json")
    assert p102_path.exists(), "P102 scorecard 不存在"
    with p102_path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert "scorecard" in data, "P102 scorecard 欄位缺失"

def test_p84e_score_fields():
    p84e_path = Path("data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl")
    assert p84e_path.exists(), "P84E outcome rows 不存在"
    with p84e_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            row = json.loads(line)
            for field in ["result_home_score", "result_away_score", "actual_winner", "predicted_side", "is_correct"]:
                assert field in row, f"P84E row 缺少欄位: {field}"
            if i > 10:
                break
