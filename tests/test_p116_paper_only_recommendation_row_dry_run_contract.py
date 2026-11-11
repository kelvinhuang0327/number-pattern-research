"""
P116 Paper-Only Recommendation Row Dry-Run Contract 測試

覆蓋：
1. P115 summary 存在且分類正確
2. P116 summary JSON 產生
3. schema/contract 結構完整
4. 各市場合約存在
5. prediction/market/odds/source trace contract 規範
6. 禁止行為與治理鎖
7. blocker/validation/future gate
8. 不產生任何 odds/EV/CLV/Kelly/production/recommendation
"""
import json
import pytest
from pathlib import Path

P115_PATH = "data/mlb_2026/derived/p115_paper_only_odds_ingestion_contract_fixture_summary.json"
P116_PATH = "data/mlb_2026/derived/p116_paper_only_recommendation_row_dry_run_contract_summary.json"

@pytest.fixture(scope="module")
def p115_summary():
    with open(P115_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="module")
def p116_summary():
    with open(P116_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def test_p115_summary_exists_and_classification(p115_summary):
    assert p115_summary["fixture_metadata"]["final_classification"] == "P115_PAPER_ONLY_ODDS_INGESTION_CONTRACT_READY_WITH_BLOCKERS"

def test_p116_summary_exists_and_schema(p116_summary):
    assert "contract_metadata" in p116_summary
    assert "paper_only_recommendation_row_schema" in p116_summary
    assert "market_row_contracts" in p116_summary
    assert "prediction_field_contract" in p116_summary
    assert "market_field_contract" in p116_summary
    assert "odds_reference_contract" in p116_summary
    assert "source_trace_contract" in p116_summary
    assert "blocked_decision_fields" in p116_summary
    assert "blocker_categories" in p116_summary
    assert "validation_rules" in p116_summary
    assert "future_integration_gates" in p116_summary
    assert "governance_locks" in p116_summary
    assert "prohibited_actions" in p116_summary
    assert p116_summary["contract_metadata"]["final_classification"].startswith("P116_RECOMMENDATION_ROW_DRY_RUN_CONTRACT_")

def test_market_row_contracts_coverage(p116_summary):
    market_ids = [c["market_id"] for c in p116_summary["market_row_contracts"]]
    for m in [
        "moneyline_winner", "run_line_handicap", "total_runs_over_under", "first_five_innings_if_supported_later", "unsupported_market_placeholder"
    ]:
        assert m in market_ids

def test_prediction_field_contract(p116_summary):
    contract = p116_summary["prediction_field_contract"]
    assert "fields" in contract
    for f in ["game_id", "predicted_side", "model_probability", "source_prediction_version"]:
        assert f in contract["fields"]
    for pf in contract["prohibited_fields"]:
        assert pf not in contract["fields"]

def test_market_field_contract(p116_summary):
    contract = p116_summary["market_field_contract"]
    assert "fields" in contract
    for f in ["market_id", "side", "line"]:
        assert f in contract["fields"]
    for pf in contract["prohibited_fields"]:
        assert pf not in contract["fields"]

def test_odds_reference_contract(p116_summary):
    contract = p116_summary["odds_reference_contract"]
    assert contract["fields"] == []
    assert "odds" not in contract["fields"]

def test_source_trace_contract(p116_summary):
    contract = p116_summary["source_trace_contract"]
    assert "fields" in contract
    assert "source_prediction_version" in contract["fields"]

def test_blocked_decision_fields(p116_summary):
    blocked = p116_summary["blocked_decision_fields"]
    for f in ["ev", "clv", "kelly", "stake", "profit", "recommendation"]:
        assert f in blocked

def test_governance_locks(p116_summary):
    locks = p116_summary["governance_locks"]
    assert locks["paper_only"] is True
    assert locks["diagnostic_only"] is True
    assert locks["production_ready"] is False
    assert locks["recommendation_allowed"] is False
    assert locks["odds_used"] is False
    assert locks["ev_computed"] is False
    assert locks["kelly_computed"] is False
    assert locks["stake_sizing"] is False
    assert locks["taiwan_lottery_recommendation"] is False

def test_prohibited_actions(p116_summary):
    prohibited = p116_summary["prohibited_actions"]
    for act in [
        "fetch_odds", "store_odds", "use_odds", "ingest_odds", "production", "recommendation",
        "ev", "clv", "kelly", "stake_sizing", "profit", "taiwan_lottery_recommendation"
    ]:
        assert act in prohibited

def test_no_odds_ev_clv_kelly_in_schema(p116_summary):
    # 不得有 odds/ev/clv/kelly/stake/profit/recommendation 欄位
    for k in ["paper_only_recommendation_row_schema", "prediction_field_contract", "market_field_contract"]:
        for pf in ["odds", "ev", "clv", "kelly", "stake", "profit", "recommendation"]:
            if "fields" in p116_summary[k]:
                assert pf not in p116_summary[k]["fields"]
            if "prohibited_fields" in p116_summary[k]:
                assert pf in p116_summary[k]["prohibited_fields"]

def test_final_classification(p116_summary):
    assert p116_summary["final_classification"] in [
        "P116_RECOMMENDATION_ROW_DRY_RUN_CONTRACT_READY_DIAGNOSTIC_ONLY",
        "P116_RECOMMENDATION_ROW_DRY_RUN_CONTRACT_READY_WITH_BLOCKERS",
        "P116_RECOMMENDATION_ROW_DRY_RUN_CONTRACT_BLOCKED_BY_MISSING_P115",
        "P116_RECOMMENDATION_ROW_DRY_RUN_CONTRACT_FAILED_VALIDATION"
    ]
