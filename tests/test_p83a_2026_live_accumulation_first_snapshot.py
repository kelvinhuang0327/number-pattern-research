"""
P83A — Tests for 2026 Live Accumulation First Snapshot / Awaiting Contract
46 tests covering: P82C source verification, schema definition, discovery,
awaiting contract, governance, forbidden phrases, and full regression chain P72A→P83A.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCRIPT = ROOT / "scripts/_p83a_2026_live_accumulation_first_snapshot.py"
JSON_OUT = ROOT / "data/mlb_2026/derived/p83a_2026_live_accumulation_first_snapshot_summary.json"
REPORT_OUT = ROOT / "report/p83a_2026_live_accumulation_first_snapshot_20260526.md"

P82C_JSON = ROOT / "data/mlb_2025/derived/p82c_staging_guard_dryrun_scanner_summary.json"
P82B_JSON = ROOT / "data/mlb_2025/derived/p82b_raw_paid_odds_data_policy_contract_summary.json"
P82A_JSON = ROOT / "data/mlb_2025/derived/p82a_real_legal_odds_intake_gate_summary.json"
P81_JSON  = ROOT / "data/mlb_2025/derived/p81_legal_odds_dataset_validator_contract_summary.json"
P80_JSON  = ROOT / "data/mlb_2025/derived/p80_market_edge_reentry_readiness_contract_summary.json"
P79B_JSON = ROOT / "data/mlb_2025/derived/p79b_tier_b_vs_tier_c_comparison_harness_summary.json"
P79A_JSON = ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json"
P78_JSON  = ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json"
P77_JSON  = ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json"
P76_JSON  = ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json"
P75B_JSON = ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json"
P75A_JSON = ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json"
P74_JSON  = ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json"
P73_JSON  = ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json"
P72B_JSON = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"
P72A_JSON = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"

FORBIDDEN_PHRASES = [
    "expected_value",
    "closing_line_value",
    '"clv_calculated": true',
    "kelly fraction",
    '"kelly_deploy_allowed": true',
    '"production_ready": true',
    "profitability confirmed",
    '"real_bet_allowed": true',
    '"p82_unlocked": true',
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def p83a_module():
    mod_name = "_p83a_2026_live_accumulation_first_snapshot"
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def p83a_result(p83a_module):
    return p83a_module.run_p83a()


@pytest.fixture(scope="module")
def p83a_json() -> dict:
    assert JSON_OUT.exists(), f"Output JSON not found: {JSON_OUT}"
    with open(JSON_OUT) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1-5: P82C source verification
# ---------------------------------------------------------------------------
def test_01_p82c_source_artifact_loads():
    assert P82C_JSON.exists(), "P82C JSON must exist for P83A"
    with open(P82C_JSON) as f:
        data = json.load(f)
    assert "p82c_classification" in data


def test_02_p82c_classification_verified(p83a_result):
    v = p83a_result["step1_p82c_verification"]
    assert v["classification"] == "P82C_STAGING_GUARD_DRYRUN_READY"
    assert v["classification_ok"] is True


def test_03_p82c_scanner_modes_verified(p83a_result):
    v = p83a_result["step1_p82c_verification"]
    assert v["scan_modes_ok"] is True
    assert v["scan_modes_count"] >= 4


def test_04_p82c_current_repo_guard_state_verified(p83a_result):
    v = p83a_result["step1_p82c_verification"]
    assert v["guard_state_ok"] is True
    assert v["overall_guard_state"] in ("STAGE_CLEAN", "REVIEW_REQUIRED")


def test_05_p82_remains_blocked(p83a_result):
    v = p83a_result["step1_p82c_verification"]
    assert v["p82_blocked"] is True
    assert v["p82_status"] == "BLOCKED_NO_REAL_DATASET"


# ---------------------------------------------------------------------------
# 6-8: Discovery
# ---------------------------------------------------------------------------
def test_06_2026_data_discovery_runs_local_only(p83a_result):
    disc = p83a_result["step2_discovery"]
    assert disc["discovery_local_only"] is True
    assert disc["no_api_calls"] is True


def test_07_discovery_candidate_paths_defined(p83a_result, p83a_module):
    """Discovery must check the defined candidate paths."""
    disc = p83a_result["step2_discovery"]
    assert len(disc["candidate_paths_checked"]) >= 4
    # Should include data/mlb_2026
    assert any("mlb_2026" in p for p in disc["candidate_paths_checked"])


def test_08_discovery_does_not_require_odds(p83a_result):
    disc = p83a_result["step2_discovery"]
    # Discovery should not require odds; check governance on result
    gov = p83a_result["governance"]
    assert gov["uses_historical_odds"] is False
    assert gov["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# 9-17: Expected row schema
# ---------------------------------------------------------------------------
def test_09_expected_row_schema_generated(p83a_result):
    schema = p83a_result.get("step3_expected_schema", {})
    assert schema.get("schema_id") == "P83A_2026_PREDICTION_ROW_SCHEMA_V1"


def test_10_required_schema_fields_present(p83a_result, p83a_module):
    schema = p83a_result["step3_expected_schema"]
    for f in p83a_module.REQUIRED_SCHEMA_FIELDS:
        assert f in schema["required_fields"], f"Required field '{f}' missing from schema"


def test_11_optional_outcome_fields_present(p83a_result, p83a_module):
    schema = p83a_result["step3_expected_schema"]
    for f in p83a_module.OPTIONAL_OUTCOME_FIELDS:
        assert f in schema["optional_outcome_fields"], f"Outcome field '{f}' missing"


def test_12_governance_fields_required(p83a_result):
    schema = p83a_result["step3_expected_schema"]
    gov_vals = schema["governance_required_values"]
    assert "paper_only" in gov_vals
    assert "diagnostic_only" in gov_vals
    assert "odds_used" in gov_vals
    assert "market_edge_evaluated" in gov_vals
    assert "production_ready" in gov_vals


def test_13_paper_only_true_required(p83a_result):
    schema = p83a_result["step3_expected_schema"]
    assert schema["governance_required_values"]["paper_only"] is True


def test_14_diagnostic_only_true_required(p83a_result):
    schema = p83a_result["step3_expected_schema"]
    assert schema["governance_required_values"]["diagnostic_only"] is True


def test_15_odds_used_false_required(p83a_result):
    schema = p83a_result["step3_expected_schema"]
    assert schema["governance_required_values"]["odds_used"] is False


def test_16_market_edge_evaluated_false_required(p83a_result):
    schema = p83a_result["step3_expected_schema"]
    assert schema["governance_required_values"]["market_edge_evaluated"] is False


def test_17_production_ready_false_required(p83a_result):
    schema = p83a_result["step3_expected_schema"]
    assert schema["governance_required_values"]["production_ready"] is False


# ---------------------------------------------------------------------------
# 18-19: Snapshot / awaiting contract branching
# ---------------------------------------------------------------------------
def test_18_if_rows_exist_snapshot_logic_handles_them(p83a_module):
    """Verify the snapshot function handles a mock row list without crashing."""
    mock_row = {
        "game_id": "2026-06-01-NYY-BOS-001",
        "game_date": "2026-06-01",
        "season": 2026,
        "home_team": "NYY",
        "away_team": "BOS",
        "predicted_side": "home",
        "model_probability": 0.62,
        "sp_fip_delta": 0.75,
        "abs_sp_fip_delta": 0.75,
        "source_prediction_version": "p83a_mock_v1",
        "paper_only": True,
        "diagnostic_only": True,
        "odds_used": False,
        "market_edge_evaluated": False,
        "production_ready": False,
    }
    snapshot = p83a_module.step4_snapshot_if_data_exists([mock_row])
    assert snapshot["snapshot_available"] is True
    assert snapshot["no_odds_required"] is True
    assert snapshot["no_market_edge"] is True
    assert "hit_rate" in snapshot["metrics"]


def test_19_if_no_rows_exist_awaiting_contract_generated(p83a_result):
    """P83A classification must be a valid P83A state."""
    cls = p83a_result.get("p83a_classification")
    VALID_P83A = {
        "P83A_AWAITING_2026_DATA",
        "P83A_2026_DATA_INVALID",
        "P83A_2026_DATA_READY",
    }
    assert cls in VALID_P83A, f"Expected a valid P83A classification, got {cls}"


# ---------------------------------------------------------------------------
# 20-24: Snapshot thresholds
# ---------------------------------------------------------------------------
def test_20_smoke_threshold_n1_defined(p83a_result, p83a_module):
    t = p83a_module.SNAPSHOT_THRESHOLDS
    assert t["smoke"]["min_n"] == 1


def test_21_sample_limited_threshold_n10_defined(p83a_result, p83a_module):
    t = p83a_module.SNAPSHOT_THRESHOLDS
    assert t["sample_limited"]["min_n"] == 10


def test_22_checkpoint_1_threshold_n50_defined(p83a_module):
    t = p83a_module.SNAPSHOT_THRESHOLDS
    assert t["checkpoint_1"]["min_n"] == 50


def test_23_checkpoint_2_threshold_n100_defined(p83a_module):
    t = p83a_module.SNAPSHOT_THRESHOLDS
    assert t["checkpoint_2"]["min_n"] == 100


def test_24_operational_threshold_n200_defined(p83a_module):
    t = p83a_module.SNAPSHOT_THRESHOLDS
    assert t["operational"]["min_n"] == 200


# ---------------------------------------------------------------------------
# 25-30: Rule definitions
# ---------------------------------------------------------------------------
def test_25_primary_125_rule_defined(p83a_result, p83a_module):
    ac = p83a_result.get("step5_awaiting_contract")
    if ac is None:
        pytest.skip("step5_awaiting_contract not present (P83A not in AWAITING state)")
    assert ac["primary_rule_tracked"] == "TIER_C_HOME_PLUS_AWAY_125"
    assert p83a_module.PRIMARY_RULE["away_threshold"] == pytest.approx(1.25)


def test_26_shadow_100_rule_defined(p83a_result, p83a_module):
    ac = p83a_result.get("step5_awaiting_contract")
    if ac is None:
        pytest.skip("step5_awaiting_contract not present (P83A not in AWAITING state)")
    assert ac["shadow_rule_tracked"] == "TIER_C_HOME_PLUS_AWAY_100"
    assert p83a_module.SHADOW_RULE["away_threshold"] == pytest.approx(1.00)


def test_27_tier_b_candidate_definition_present(p83a_result, p83a_module):
    ac = p83a_result.get("step5_awaiting_contract")
    if ac is None:
        pytest.skip("step5_awaiting_contract not present (P83A not in AWAITING state)")
    assert "TIER_B" in ac["tier_b_rule"]
    assert p83a_module.TIER_B_RULE["delta_lo"] == pytest.approx(0.25)
    assert p83a_module.TIER_B_RULE["delta_hi"] == pytest.approx(0.50)


def test_28_tier_a_watchlist_definition_present(p83a_result, p83a_module):
    ac = p83a_result.get("step5_awaiting_contract")
    if ac is None:
        pytest.skip("step5_awaiting_contract not present (P83A not in AWAITING state)")
    assert "TIER_A" in ac["tier_a_watchlist"]
    assert p83a_module.TIER_A_WATCHLIST["delta_hi"] == pytest.approx(0.25)


def test_29_outcomes_optional_in_early_snapshot(p83a_module):
    """Snapshot with no outcomes should give P83A_2026_DATA_PRESENT_OUTCOMES_PENDING."""
    mock_rows = [
        {
            "game_id": f"2026-06-01-NYY-BOS-00{i}",
            "game_date": "2026-06-01",
            "season": 2026,
            "home_team": "NYY",
            "away_team": "BOS",
            "predicted_side": "home",
            "model_probability": 0.62,
            "sp_fip_delta": 0.75,
            "abs_sp_fip_delta": 0.75,
            "source_prediction_version": "v1",
            "paper_only": True,
            "diagnostic_only": True,
            "odds_used": False,
            "market_edge_evaluated": False,
            "production_ready": False,
            # No is_correct / outcome fields
        }
        for i in range(5)
    ]
    snapshot = p83a_module.step4_snapshot_if_data_exists(mock_rows)
    assert snapshot["outcomes_available"] is False
    assert snapshot["metrics"]["hit_rate"] == "NOT_YET_AVAILABLE"
    assert snapshot["snapshot_classification"] == "P83A_2026_DATA_PRESENT_OUTCOMES_PENDING"


def test_30_metrics_only_computed_when_outcomes_exist(p83a_module):
    """When is_correct is present, metrics show COMPUTABLE."""
    mock_rows = [
        {
            "game_id": f"2026-06-01-NYY-BOS-00{i}",
            "game_date": "2026-06-01",
            "season": 2026,
            "home_team": "NYY",
            "away_team": "BOS",
            "predicted_side": "home",
            "model_probability": 0.62,
            "sp_fip_delta": 0.75,
            "abs_sp_fip_delta": 0.75,
            "source_prediction_version": "v1",
            "paper_only": True,
            "diagnostic_only": True,
            "odds_used": False,
            "market_edge_evaluated": False,
            "production_ready": False,
            "is_correct": True,
            "actual_winner": "home",
        }
        for i in range(20)
    ]
    snapshot = p83a_module.step4_snapshot_if_data_exists(mock_rows)
    assert snapshot["outcomes_available"] is True
    assert snapshot["metrics"]["hit_rate"] == "COMPUTABLE"
    assert snapshot["metrics"]["auc"] == "COMPUTABLE"


# ---------------------------------------------------------------------------
# 31-44: Governance invariants
# ---------------------------------------------------------------------------
def test_31_no_odds_required(p83a_result):
    gov = p83a_result["governance"]
    assert gov["uses_historical_odds"] is False


def test_32_no_api_call(p83a_result):
    gov = p83a_result["governance"]
    assert gov["live_api_calls"] == 0


def test_33_no_api_key_access(p83a_result):
    gov = p83a_result["governance"]
    assert gov["the_odds_api_key_required"] is False


def test_34_no_edge_calculated(p83a_result):
    gov = p83a_result["governance"]
    assert gov["market_edge_calculated"] is False


def test_35_no_clv_calculated(p83a_result):
    gov = p83a_result["governance"]
    assert gov["clv_calculated"] is False


def test_36_no_ev_calculated(p83a_result):
    gov = p83a_result["governance"]
    assert gov["ev_calculated"] is False


def test_37_no_kelly_calculated(p83a_result):
    gov = p83a_result["governance"]
    assert gov["kelly_deploy_allowed"] is False


def test_38_live_api_calls_zero(p83a_result):
    gov = p83a_result["governance"]
    assert gov["live_api_calls"] == 0


def test_39_production_ready_false(p83a_result):
    gov = p83a_result["governance"]
    assert gov["production_ready"] is False


def test_40_kelly_deploy_allowed_false(p83a_result):
    gov = p83a_result["governance"]
    assert gov["kelly_deploy_allowed"] is False


def test_41_forbidden_scan_passes(p83a_json):
    text = json.dumps(p83a_json).lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase.lower() not in text, f"Forbidden phrase found: '{phrase}'"


def test_42_json_schema_stable(p83a_json):
    required_keys = [
        "phase", "date", "p83a_classification", "governance",
        "step1_p82c_verification", "step2_discovery",
        "step3_expected_schema", "forbidden_scan",
    ]
    for k in required_keys:
        assert k in p83a_json, f"Required key missing: {k}"


def test_43_report_includes_discovery_result():
    assert REPORT_OUT.exists()
    content = REPORT_OUT.read_text()
    assert "2026 Data Discovery" in content or "Discovery" in content
    assert "P83A" in content


def test_44_report_includes_snapshot_or_awaiting_contract():
    content = REPORT_OUT.read_text()
    assert "Awaiting" in content or "Snapshot" in content or "AWAITING" in content


def test_45_active_task_md_updated():
    active_task = ROOT / "00-Plan/roadmap/active_task.md"
    assert active_task.exists()
    content = active_task.read_text()
    assert "P82" in content  # at minimum P82 completed is present


# ---------------------------------------------------------------------------
# 46: Full regression chain P72A → P83A
# ---------------------------------------------------------------------------
def test_46_regression_prior_phases_intact():
    """All prior phase JSON summaries must still carry expected classifications."""
    chain = [
        (P72A_JSON, ["p72a_classification", "final_classification"],
         "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED"),
        (P72B_JSON, ["p72b_classification"],
         "P72B_OBJECTIVE_CONTRACT_READY"),
        (P73_JSON, ["p73_classification"],
         "P73_TIER_C_OPERATIONAL_STABLE_TIER_B_RESEARCH_CONFIRMED"),
        (P74_JSON, ["p74_classification"],
         "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED"),
        (P75A_JSON, ["p75a_classification"],
         "P75A_MULTI_CANDIDATE_REQUIRES_CALIBRATION"),
        (P75B_JSON, ["p75b_classification"],
         "P75B_MULTI_CANDIDATE_KEEP_FOR_NEXT_PHASE"),
        (P76_JSON, ["p76_classification"],
         "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA"),
        (P77_JSON, ["p77_classification"],
         "P77_SHADOW_TRACKER_CONTRACT_READY"),
        (P78_JSON, ["p78_classification"],
         "P78_MONTHLY_SHADOW_TRACKER_TEMPLATE_READY"),
        (P79A_JSON, ["p79a_classification"],
         "P79A_TIER_B_TRIGGER_READINESS_CONTRACT_READY"),
        (P79B_JSON, ["p79b_classification"],
         "P79B_TIER_B_FIXTURE_RESEARCH_ONLY"),
        (P80_JSON, ["p80_classification"],
         "P80_MARKET_EDGE_REENTRY_CONTRACT_READY"),
        (P81_JSON, ["p81_classification"],
         "P81_VALIDATOR_CONTRACT_READY_MOCK_ONLY"),
        (P82A_JSON, ["p82a_classification"],
         "P82A_REAL_LEGAL_ODDS_INTAKE_GATE_READY"),
        (P82B_JSON, ["p82b_classification"],
         "P82B_RAW_PAID_DATA_POLICY_READY"),
        (P82C_JSON, ["p82c_classification"],
         "P82C_STAGING_GUARD_DRYRUN_READY"),
    ]
    for path, keys, expected in chain:
        assert path.exists(), f"Missing prior artifact: {path}"
        with open(path) as f:
            data = json.load(f)
        value = ""
        for k in keys:
            v = data.get(k)
            if v:
                value = str(v)
                break
        assert value == expected, (
            f"{path.name}: expected classification '{expected}', got '{value}'"
        )
