# 測試 P117 Paper-Only Recommendation Row Fixture
import json
import os
import pytest

P117_PATH = "data/mlb_2026/derived/p117_paper_only_recommendation_row_fixture_summary.json"
P116_PATH = "data/mlb_2026/derived/p116_paper_only_recommendation_row_dry_run_contract_summary.json"

@pytest.mark.order(1)
def test_p116_summary_exists_and_classification():
    assert os.path.exists(P116_PATH), "P116 summary missing"
    with open(P116_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("contract_metadata", {}).get("final_classification") == "P116_RECOMMENDATION_ROW_DRY_RUN_CONTRACT_READY_WITH_BLOCKERS"

@pytest.mark.order(2)
def test_p117_summary_generated():
    assert os.path.exists(P117_PATH), "P117 summary not generated"
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert data.get("fixture_metadata", {}).get("fixture_version") == "P117.20260531"
    assert data.get("fixture_metadata", {}).get("final_classification") in [
        "P117_RECOMMENDATION_ROW_FIXTURE_READY_WITH_BLOCKERS",
        "P117_RECOMMENDATION_ROW_FIXTURE_READY_DIAGNOSTIC_ONLY"
    ]

@pytest.mark.order(3)
def test_paper_only_recommendation_rows_exists():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "paper_only_recommendation_rows" in data
    assert isinstance(data["paper_only_recommendation_rows"], list)

@pytest.mark.order(4)
def test_market_row_fixtures():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    markets = data.get("market_row_fixtures", [])
    ids = {m.get("market_id") for m in markets}
    required = {"moneyline_winner", "run_line_handicap", "total_runs_over_under", "first_five_innings_if_supported_later", "unsupported_market_placeholder"}
    assert required.issubset(ids)
    for m in markets:
        assert m.get("dry_run_status") == "blocked"
        assert m.get("blocker_type")
        assert m.get("allowed_future_action") == "diagnostic_tracking_only"
        assert "production" in m.get("prohibited_action", [])

@pytest.mark.order(5)
def test_prediction_field_fixtures():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "prediction_field_fixtures" in data
    assert "predicted_side" in data["prediction_field_fixtures"]

@pytest.mark.order(6)
def test_market_field_fixtures():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "market_field_fixtures" in data
    assert "market_id" in data["market_field_fixtures"]

@pytest.mark.order(7)
def test_odds_reference_fixtures():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "odds_reference_fixtures" in data
    assert "odds" in data["odds_reference_fixtures"]
    # 不允許有真實賠率值
    assert data["odds_reference_fixtures"] == ["odds", "publish_time", "fetch_time"]

@pytest.mark.order(8)
def test_source_trace_fixtures():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "source_trace_fixtures" in data
    assert "provider_id" in data["source_trace_fixtures"]

@pytest.mark.order(9)
def test_blocked_decision_fields():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert "blocked_decision_fields" in data
    assert "dry_run_status" in data["blocked_decision_fields"]

@pytest.mark.order(10)
def test_blocker_categories():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for m in data.get("market_row_fixtures", []):
        blockers = set(m.get("blocker_type", []))
        required = {
            "LEGAL_ODDS_SOURCE_BLOCKER",
            "LEGAL_PROVIDER_AUTHORIZATION_BLOCKER",
            "ODDS_INGESTION_NOT_IMPLEMENTED_BLOCKER",
            "ODDS_SCHEMA_BLOCKER",
            "MARKET_MAPPING_BLOCKER",
            "SOURCE_TRACE_BLOCKER",
            "TIMESTAMP_FRESHNESS_BLOCKER",
            "DATA_QUALITY_BLOCKER",
            "EV_CLV_NOT_ALLOWED_BLOCKER",
            "KELLY_STAKE_NOT_ALLOWED_BLOCKER",
            "GOVERNANCE_PRODUCTION_BLOCKER",
            "RECOMMENDATION_NOT_ALLOWED_BLOCKER"
        }
        assert required.issubset(blockers)

@pytest.mark.order(11)
def test_no_odds_ev_clv_kelly():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for m in data.get("market_row_fixtures", []):
        for field in ["ev", "clv", "kelly", "stake", "profit", "recommendation"]:
            assert field not in m

@pytest.mark.order(12)
def test_all_rows_blocked():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for m in data.get("market_row_fixtures", []):
        assert m.get("dry_run_status") == "blocked"

@pytest.mark.order(13)
def test_governance_flags():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    g = data.get("governance_locks", {})
    assert g.get("paper_only") is True
    assert g.get("diagnostic_only") is True
    assert g.get("production_ready") is False
    assert g.get("recommendation_allowed") is False
    assert g.get("odds_used") is False
    assert g.get("ev_computed") is False
    assert g.get("kelly_computed") is False
    assert g.get("taiwan_lottery_recommendation") is False

@pytest.mark.order(14)
def test_final_classification():
    with open(P117_PATH, encoding="utf-8") as f:
        data = json.load(f)
    c = data.get("fixture_metadata", {}).get("final_classification")
    assert c in [
        "P117_RECOMMENDATION_ROW_FIXTURE_READY_WITH_BLOCKERS",
        "P117_RECOMMENDATION_ROW_FIXTURE_READY_DIAGNOSTIC_ONLY"
    ]
