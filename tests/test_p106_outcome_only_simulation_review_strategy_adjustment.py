import json
from pathlib import Path

def test_p105_summary_exists_and_classification():
    p105 = json.load(open("data/mlb_2026/derived/p105_outcome_only_score_simulation_runner_summary.json"))
    assert p105["final_classification"] == "P105_SCORE_SIMULATION_RUNNER_READY_DIAGNOSTIC_ONLY"

def test_p106_summary_generated():
    path = Path("data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json")
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["final_classification"].startswith("P106_SIMULATION_REVIEW_ADJUSTMENT_READY")

def test_strategy_adjustment_plan():
    data = json.load(open("data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json"))
    plan = data["adjustment_plan"]
    assert "HIGH_FIP" in plan
    assert plan["HIGH_FIP"]["decision"] == "TRACK_DIAGNOSTIC"
    assert plan["HIGH_FIP"]["hit_rate"] >= 0.5
    assert plan["HIGH_FIP"]["eligible_rows"] >= 100
    assert plan["HIGH_FIP"]["rationale"]
    assert plan["MID_FIP"]["decision"] in ("WATCH_ONLY", "PAUSE_OPTIMIZATION", "REJECT_FOR_NOW", "NEED_MORE_SAMPLE")
    assert plan["LOW_FIP"]["decision"] in ("WATCH_ONLY", "PAUSE_OPTIMIZATION", "REJECT_FOR_NOW", "NEED_MORE_SAMPLE")
    assert plan["ALL_ROWS"]["decision"] == "WATCH_ONLY"

def test_strongest_and_sample_limited():
    data = json.load(open("data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json"))
    assert data["strongest_strategy"]
    assert isinstance(data["sample_limited_strategies"], list)

def test_learning_rules_and_governance():
    data = json.load(open("data/mlb_2026/derived/p106_outcome_only_simulation_review_strategy_adjustment_summary.json"))
    rules = data["learning_rules"]
    gov = data["governance"]
    assert "improvement_metric" in rules
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
