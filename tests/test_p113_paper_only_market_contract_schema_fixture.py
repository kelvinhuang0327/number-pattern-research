import json
import os
import pytest

P113_PATH = "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json"
P112_PATH = "data/mlb_2026/derived/p112_lane_a_market_contract_gap_review_summary.json"

@pytest.mark.parametrize("summary_path", [P113_PATH])
def test_p113_summary_exists(summary_path):
    assert os.path.exists(summary_path), f"P113 summary file not found: {summary_path}"
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "fixture_metadata" in data
    assert "market_contracts" in data
    assert data["fixture_metadata"]["final_classification"].startswith("P113_MARKET_CONTRACT_SCHEMA_FIXTURE_"), "Final classification invalid"
    # Governance
    gov = data["governance_locks"]
    assert gov["paper_only"] and gov["diagnostic_only"]
    assert not gov["production_ready"]
    assert not gov["recommendation_allowed"]
    # Market contracts
    ids = [c["market_id"] for c in data["market_contracts"]]
    assert "moneyline_winner" in ids
    assert "run_line_handicap" in ids
    assert "total_runs_over_under" in ids
    assert "first_five_innings_if_supported_later" in ids
    assert "unsupported_market_placeholder" in ids
    # Blockers
    for c in data["market_contracts"]:
        assert "current_blockers" in c
        assert isinstance(c["current_blockers"], list)
    # No recommendation, EV, CLV, Kelly, stake
    for c in data["market_contracts"]:
        for pa in c["prohibited_action"]:
            assert pa in ["production", "recommendation", "betting", "odds", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"]
    # Required fields
    for c in data["market_contracts"]:
        assert "required_prediction_fields" in c
        assert "required_legal_odds_fields" in c
        assert "required_source_trace" in c
        assert "required_timestamp_fields" in c
        assert "required_outcome_fields" in c

@pytest.mark.parametrize("p112_path", [P112_PATH])
def test_p112_summary_exists_and_valid(p112_path):
    assert os.path.exists(p112_path), f"P112 summary file not found: {p112_path}"
    with open(p112_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("final_classification", "").startswith("P112_LANE_A_MARKET_CONTRACT_GAP_REVIEW_READY_"), "P112 classification invalid"
