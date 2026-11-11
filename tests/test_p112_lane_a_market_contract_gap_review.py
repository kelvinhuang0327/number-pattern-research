import json
import os
import pytest

SUMMARY_PATH = "data/mlb_2026/derived/p112_lane_a_market_contract_gap_review_summary.json"

@pytest.mark.parametrize("summary_path", [SUMMARY_PATH])
def test_gap_summary_exists(summary_path):
    assert os.path.exists(summary_path), f"Gap summary file not found: {summary_path}"
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "market_gaps" in data, "Missing 'market_gaps' key in summary"
    assert isinstance(data["market_gaps"], list), "market_gaps should be a list"
    # Governance flag check
    assert data.get("governance", {}).get("diagnostic_only", False), "diagnostic_only flag must be True"
    assert not data.get("governance", {}).get("production_ready", True), "production_ready flag must be False"
    assert not data.get("governance", {}).get("recommendation_allowed", True), "recommendation_allowed flag must be False"
    # Each gap must have required fields
    for gap in data["market_gaps"]:
        assert "market_type" in gap, "Each gap must specify market_type"
        assert "gap_type" in gap, "Each gap must specify gap_type"
        assert "required_fields" in gap, "Each gap must specify required_fields"
        assert "pipeline_fields" in gap, "Each gap must specify pipeline_fields"
        assert "strategy_coverage" in gap, "Each gap must specify strategy_coverage"
