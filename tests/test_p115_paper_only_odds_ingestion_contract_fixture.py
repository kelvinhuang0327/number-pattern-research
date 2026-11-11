import json
import os
import pytest

P115_PATH = "data/mlb_2026/derived/p115_paper_only_odds_ingestion_contract_fixture_summary.json"
P114_PATH = "data/mlb_2026/derived/p114_legal_odds_source_requirements_spec_summary.json"

@pytest.mark.parametrize("summary_path", [P115_PATH])
def test_p115_summary_exists(summary_path):
    assert os.path.exists(summary_path), f"P115 summary file not found: {summary_path}"
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "fixture_metadata" in data
    assert data["fixture_metadata"]["final_classification"].startswith("P115_PAPER_ONLY_ODDS_INGESTION_CONTRACT_"), "Final classification invalid"
    assert "paper_only_ingestion_payload_contract" in data
    assert "market_payload_contracts" in data
    assert "dedupe_contract" in data
    assert "source_trace_contract" in data
    assert "timestamp_freshness_contract" in data
    assert "provider_metadata_contract" in data
    assert "data_quality_validation_contract" in data
    assert "audit_log_contract" in data
    # Market coverage
    ids = [c["market_id"] for c in data["market_payload_contracts"]]
    for m in [
        "moneyline_winner",
        "run_line_handicap",
        "total_runs_over_under",
        "first_five_innings_if_supported_later",
        "unsupported_market_placeholder"
    ]:
        assert m in ids
    # Blocker categories
    for c in data["market_payload_contracts"]:
        for blocker in [
            "LEGAL_ODDS_SOURCE_BLOCKER",
            "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
            "ODDS_SCHEMA_BLOCKER",
            "INGESTION_NOT_IMPLEMENTED_BLOCKER",
            "MARKET_MAPPING_BLOCKER",
            "SOURCE_TRACE_BLOCKER",
            "TIMESTAMP_FRESHNESS_BLOCKER",
            "DATA_QUALITY_BLOCKER",
            "EV_CLV_NOT_ALLOWED_BLOCKER",
            "GOVERNANCE_PRODUCTION_BLOCKER"
        ]:
            assert blocker in c["blocker_type"]
    # Governance
    gov = data["governance_locks"]
    assert gov["paper_only"] and gov["diagnostic_only"]
    assert not gov["production_ready"]
    assert not gov["recommendation_allowed"]
    assert not gov["odds_used"]
    assert not gov["odds_fetched"]
    assert not gov["odds_stored"]
    assert not gov["odds_ingested"]
    # Blocked actions
    for a in [
        "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation", "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
    ]:
        assert a in data["blocked_actions"]
    # No odds fetched/stored/used/ingested
    for c in data["market_payload_contracts"]:
        for pa in c["prohibited_action"]:
            assert pa in data["blocked_actions"]
    # Validation rules
    assert "No odds may be fetched, stored, ingested, used, or computed in this phase." in data["validation_rules"]
    assert "All governance locks must remain true." in data["validation_rules"]

@pytest.mark.parametrize("p114_path", [P114_PATH])
def test_p114_summary_exists_and_valid(p114_path):
    assert os.path.exists(p114_path), f"P114 summary file not found: {p114_path}"
    with open(p114_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("spec_metadata", {}).get("final_classification", "").startswith("P114_LEGAL_ODDS_SOURCE_REQUIREMENTS_"), "P114 classification invalid"
