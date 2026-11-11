"""
Test for P105 Outcome-Only Score Simulation Runner
"""
import json
import importlib.util
from pathlib import Path

def test_p105_summary_generated():
    # 執行主程式產生 summary
    script_path = Path("scripts/_p105_outcome_only_score_simulation_runner.py")
    spec = importlib.util.spec_from_file_location("p105", script_path)
    p105 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p105)
    out_path = Path("data/mlb_2026/derived/p105_outcome_only_score_simulation_runner_summary.json")
    assert out_path.exists(), "P105 summary JSON 未產生"
    with out_path.open(encoding="utf-8") as f:
        summary = json.load(f)
    # 基本欄位檢查
    assert summary["final_classification"].startswith("P105_SCORE_SIMULATION_RUNNER"), "final_classification 不正確"
    for sim in [
        "win_loss_simulation_by_strategy",
        "side_accuracy_by_strategy",
        "monthly_win_loss_simulation",
        "score_margin_descriptive_analysis"
    ]:
        assert sim in summary["supported_simulations"], f"缺少 supported simulation: {sim}"
    for sim in [
        "profit_simulation_blocked",
        "ev_simulation_blocked",
        "clv_simulation_blocked",
        "kelly_or_stake_simulation_blocked",
        "taiwan_lottery_recommendation_blocked"
    ]:
        assert sim in summary["blocked_simulations"], f"未明確阻擋 {sim}"
    assert summary["governance"]["paper_only"] is True, "governance paper_only 必須為 True"
    assert summary["governance"]["diagnostic_only"] is True, "governance diagnostic_only 必須為 True"
    assert summary["governance"]["production_ready"] is False, "governance production_ready 必須為 False"
    assert summary["next_implementation_target"].startswith("P106"), "next_implementation_target 必須指向 P106"
    # 策略欄位檢查
    for sid in ["ALL_ROWS", "HIGH_FIP", "MID_FIP", "LOW_FIP"]:
        if sid in summary["strategies"]:
            s = summary["strategies"][sid]
            for field in [
                "strategy_id", "eligible_rows", "wins", "losses", "hit_rate", "home_predicted_count", "away_predicted_count", "side_split_accuracy", "monthly_accuracy", "average_score_margin", "median_score_margin", "score_margin_buckets", "sample_status", "diagnostic_status"
            ]:
                assert field in s, f"{sid} 缺少欄位: {field}"

def test_p104_summary_exists():
    p104_path = Path("data/mlb_2026/derived/p104_outcome_only_score_simulation_design_summary.json")
    assert p104_path.exists(), "P104 summary 不存在"
    with p104_path.open(encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("final_classification", "").startswith("P104_SCORE_SIMULATION_DESIGN_READY"), "P104 final_classification 不正確"

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
