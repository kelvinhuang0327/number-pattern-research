import json
import os
import pytest

P114_PATH = "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json"
P113_PATH = "data/mlb_2026/derived/p113_paper_only_market_contract_schema_fixture_summary.json"

@pytest.mark.parametrize("summary_path", [P114_PATH])
def test_p114_summary_exists(summary_path):
    assert os.path.exists(summary_path), f"P114 summary file not found: {summary_path}"
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "spec_metadata" in data
    assert "legal_odds_source_requirements" in data
    assert "market_odds_requirements" in data
    assert data["spec_metadata"]["final_classification"].startswith("P114_LEGAL_ODDS_SOURCE_REQUIREMENTS_"), "Final classification invalid"
    # Governance
    gov = data["governance_locks"]
    assert gov["paper_only"] and gov["diagnostic_only"]
    assert not gov["production_ready"]
    assert not gov["recommendation_allowed"]
    assert not gov["odds_used"]
    assert not gov["odds_fetched"]
    assert not gov["odds_stored"]
    # Market requirements
    ids = [c["market_id"] for c in data["market_odds_requirements"]]
    assert "moneyline_winner" in ids
    assert "run_line_handicap" in ids
    assert "total_runs_over_under" in ids
    assert "first_five_innings_if_supported_later" in ids
    assert "unsupported_market_placeholder" in ids
    # Blockers
    for c in data["market_odds_requirements"]:
        assert "blocker_type" in c
        assert isinstance(c["blocker_type"], list)
    # No odds fetched/stored/used
    for c in data["market_odds_requirements"]:
        for pa in c["prohibited_action"]:
            assert pa in ["fetch_odds", "store_odds", "use_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "taiwan_lottery_recommendation"]
    # Required fields
    for c in data["market_odds_requirements"]:
        assert "required_odds_fields" in c
        assert "required_source_trace_fields" in c
        assert "required_timestamp_fields" in c
        assert "required_market_status_fields" in c
        assert "required_provider_metadata" in c
        assert "dedupe_key" in c
        assert "freshness_requirement" in c
        assert "audit_requirement" in c

@pytest.mark.parametrize("p113_path", [P113_PATH])
def test_p113_summary_exists_and_valid(p113_path):
    assert os.path.exists(p113_path), f"P113 summary file not found: {p113_path}"
    with open(p113_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("fixture_metadata", {}).get("final_classification", "").startswith("P113_MARKET_CONTRACT_SCHEMA_FIXTURE_READY_"), "P113 classification invalid"
