import os
import json
import subprocess
import pytest

def test_p117_summary_exists_and_classification():
    path = "data/mlb_2026/derived/p117_paper_only_recommendation_row_fixture_summary.json"
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["fixture_metadata"]["final_classification"] == "P117_RECOMMENDATION_ROW_FIXTURE_READY_WITH_BLOCKERS"

def test_p118_script_runs_and_outputs():
    # Remove old output if exists
    out_path = "data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json"
    if os.path.exists(out_path):
        os.remove(out_path)
    subprocess.run(["python3", "scripts/_p118_recommendation_row_validation_gate.py"], check=True)
    assert os.path.exists(out_path)
    with open(out_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "gate_metadata" in data
    assert data["gate_metadata"]["final_classification"].startswith("P118_RECOMMENDATION_ROW_VALIDATION_GATE_READY")
    assert "market_row_validation_rules" in data
    assert len(data["market_row_validation_rules"]) >= 5
    for rule in data["market_row_validation_rules"]:
        assert rule["validation_status"] == "blocked"
        assert rule["forbidden_real_odds_fields"]
        assert rule["forbidden_decision_fields"]
        assert rule["forbidden_production_fields"]

def test_p118_invariants_and_governance():
    with open("data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    invariants = data["required_row_invariants"]
    assert "ROW_IS_PAPER_ONLY" in invariants
    assert "ROW_IS_DIAGNOSTIC_ONLY" in invariants
    assert "NO_REAL_ODDS" in invariants
    gov = data["governance_validation_rules"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["production_ready"] is False
    assert gov["recommendation_allowed"] is False

def test_p118_blocks_recommendation_and_production():
    with open("data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    blocked = data["blocked_decision_validation_rules"]
    assert blocked["recommendation_allowed"] is False
    assert blocked["production_ready"] is False

def test_p118_source_trace_and_legal_provider():
    with open("data/mlb_2026/derived/p118_recommendation_row_validation_gate_summary.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    trace = data["source_trace_validation_rules"]
    assert trace["source_trace_required"] is True
    assert trace["legal_provider_required"] is True
