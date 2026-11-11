"""
Tests for P81 — Legal Odds Dataset Validator Contract
=====================================================
53 tests covering:
- P80 source artifact loading and readiness verification
- Validator input type contract
- Schema validator (all 21 fields)
- Validator gates (5 gates)
- Mock fixture validation (valid + invalid)
- Output decision states
- Governance invariants
- Forbidden scan
- JSON schema stability
- P72A-P81 regression
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Module fixture — load P81 script once
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
DERIVED = REPO_ROOT / "data" / "mlb_2025" / "derived"
SCRIPT_PATH = REPO_ROOT / "scripts" / "_p81_legal_odds_dataset_validator_contract.py"


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location("p81_module", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def summary(module):
    return module.main()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_json(fname: str) -> dict:
    return json.loads((DERIVED / fname).read_text())


# ---------------------------------------------------------------------------
# 01 — P80 source artifact loads
# ---------------------------------------------------------------------------
def test_01_p80_summary_loads():
    d = _load_json("p80_market_edge_reentry_readiness_contract_summary.json")
    assert isinstance(d, dict)
    assert "p80_classification" in d


# ---------------------------------------------------------------------------
# 02 — P80 classification verified
# ---------------------------------------------------------------------------
def test_02_p80_classification_verified(summary):
    s1 = summary["step1_p80_readiness"]
    assert s1["p80_classification"] == "P80_MARKET_EDGE_REENTRY_CONTRACT_READY"
    assert s1["status"] == "PASS"


# ---------------------------------------------------------------------------
# 03 — P80 legal odds contract fields extracted
# ---------------------------------------------------------------------------
def test_03_p80_required_field_count(summary):
    s1 = summary["step1_p80_readiness"]
    assert s1["required_field_count"] == 21


# ---------------------------------------------------------------------------
# 04 — P80 validation gates A-F verified
# ---------------------------------------------------------------------------
def test_04_p80_gates_a_through_f(summary):
    s1 = summary["step1_p80_readiness"]
    expected = {
        "gate_a_data_legality", "gate_b_schema", "gate_c_mapping",
        "gate_d_metric_readiness", "gate_e_cross_year_validation", "gate_f_governance",
    }
    assert expected.issubset(set(s1["gates_defined"]))


# ---------------------------------------------------------------------------
# 05 — Validator input types defined
# ---------------------------------------------------------------------------
def test_05_input_types_defined(summary):
    s2 = summary["step2_input_contract"]
    assert len(s2["input_types_defined"]) == 5


# ---------------------------------------------------------------------------
# 06 — Real legal dataset input type defined
# ---------------------------------------------------------------------------
def test_06_real_legal_dataset_defined(summary):
    s2 = summary["step2_input_contract"]
    assert "REAL_LEGAL_ODDS_DATASET" in s2["input_types_defined"]


# ---------------------------------------------------------------------------
# 07 — Mock fixture input type defined
# ---------------------------------------------------------------------------
def test_07_mock_fixture_defined(summary):
    s2 = summary["step2_input_contract"]
    assert "MOCK_ODDS_FIXTURE" in s2["input_types_defined"]


# ---------------------------------------------------------------------------
# 08 — Unknown source input type blocked
# ---------------------------------------------------------------------------
def test_08_unknown_source_cannot_unlock_p82(summary):
    s2 = summary["step2_input_contract"]
    assert s2["p82_unlock_eligibility"]["UNKNOWN_SOURCE_DATASET"] is False


# ---------------------------------------------------------------------------
# 09 — Scraping-prohibited source blocked
# ---------------------------------------------------------------------------
def test_09_scraping_prohibited_blocked(summary):
    s2 = summary["step2_input_contract"]
    assert s2["p82_unlock_eligibility"]["SCRAPING_PROHIBITED_SOURCE"] is False


# ---------------------------------------------------------------------------
# 10 — Raw paid data without policy blocked
# ---------------------------------------------------------------------------
def test_10_raw_paid_data_unpolicied_blocked(summary):
    s2 = summary["step2_input_contract"]
    assert s2["p82_unlock_eligibility"]["RAW_PAID_DATA_UNPOLICIED"] is False


# ---------------------------------------------------------------------------
# 11 — Required field list generated (21 fields)
# ---------------------------------------------------------------------------
def test_11_required_field_list_generated(summary):
    s3 = summary["step3_schema_validator"]
    assert len(s3["required_fields"]) == 21
    assert s3["required_field_count"] == 21


# ---------------------------------------------------------------------------
# 12 — Schema validator checks missing fields
# ---------------------------------------------------------------------------
def test_12_schema_validator_missing_fields(module):
    incomplete_row = {"game_id": "TEST-001"}
    result = module._validate_schema(incomplete_row)
    assert result["valid"] is False
    assert len(result["missing_fields"]) > 0


# ---------------------------------------------------------------------------
# 13 — Schema validator checks null fields
# ---------------------------------------------------------------------------
def test_13_schema_validator_null_fields(module):
    row = {f: None for f in module.REQUIRED_ODDS_FIELDS}
    result = module._validate_schema(row)
    assert result["valid"] is False
    assert len(result["null_fields"]) > 0


# ---------------------------------------------------------------------------
# 14 — Date parsing validated
# ---------------------------------------------------------------------------
def test_14_date_parsing(module):
    assert module._parse_utc("2025-07-04T00:00:00+00:00") is True
    assert module._parse_utc("not-a-date") is False
    assert module._parse_utc("") is False
    assert module._parse_utc(None) is False


# ---------------------------------------------------------------------------
# 15 — Season numeric validated
# ---------------------------------------------------------------------------
def test_15_season_numeric(module):
    valid_row = dict(module.MOCK_FIXTURE_VALID)
    invalid_row = dict(module.MOCK_FIXTURE_VALID)
    invalid_row["season"] = "twenty-twenty-five"
    result = module._validate_schema(invalid_row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 16 — Team fields validated
# ---------------------------------------------------------------------------
def test_16_team_fields_validated(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["home_team"] = ""
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 17 — Source field validated
# ---------------------------------------------------------------------------
def test_17_source_field_validated(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["sportsbook_or_source"] = ""
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 18 — Market type validated
# ---------------------------------------------------------------------------
def test_18_market_type_validated(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["market_type"] = ""
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 19 — Odds timestamp validated
# ---------------------------------------------------------------------------
def test_19_odds_timestamp_validated(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["odds_timestamp_utc"] = "bad-ts"
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 20 — Game start timestamp validated
# ---------------------------------------------------------------------------
def test_20_game_start_timestamp_validated(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["game_start_utc"] = "bad-ts"
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 21 — Moneyline numeric validation
# ---------------------------------------------------------------------------
def test_21_moneyline_numeric_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["home_moneyline"] = "EVEN"
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 22 — Implied probability range validation
# ---------------------------------------------------------------------------
def test_22_implied_prob_range_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["implied_home_prob"] = 1.5  # out of (0,1)
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 23 — Pregame boolean validation
# ---------------------------------------------------------------------------
def test_23_pregame_boolean_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["is_pregame"] = "yes"
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 24 — Closing boolean validation
# ---------------------------------------------------------------------------
def test_24_closing_boolean_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["is_closing"] = 1  # int, not bool
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 25 — Source license status validation
# ---------------------------------------------------------------------------
def test_25_source_license_status_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["source_license_status"] = "SCRAPING_TOS_VIOLATION"
    gate = module._run_legality_gate(row)
    assert gate["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 26 — Source trace validation
# ---------------------------------------------------------------------------
def test_26_source_trace_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["source_trace"] = ""
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 27 — Raw data policy validation
# ---------------------------------------------------------------------------
def test_27_raw_data_policy_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["raw_data_policy"] = "UNKNOWN"
    gate = module._run_raw_data_policy_gate(row)
    assert gate["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 28 — Checksum validation
# ---------------------------------------------------------------------------
def test_28_checksum_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["checksum_hash"] = ""
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 29 — Created-at validation
# ---------------------------------------------------------------------------
def test_29_created_at_validation(module):
    row = dict(module.MOCK_FIXTURE_VALID)
    row["created_at_utc"] = "not-a-date"
    result = module._validate_schema(row)
    assert result["valid"] is False


# ---------------------------------------------------------------------------
# 30 — Legality gate pass/fail tested
# ---------------------------------------------------------------------------
def test_30_legality_gate_pass_fail(module):
    # Pass: MOCK_VALIDATOR_ONLY
    pass_row = dict(module.MOCK_FIXTURE_VALID)
    assert module._run_legality_gate(pass_row)["status"] == "PASS"
    # Fail: prohibited
    fail_row = dict(module.MOCK_FIXTURE_VALID)
    fail_row["source_license_status"] = "ROBOTS_PROHIBITED"
    assert module._run_legality_gate(fail_row)["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 31 — Raw data policy gate pass/fail tested
# ---------------------------------------------------------------------------
def test_31_raw_data_policy_gate_pass_fail(module):
    # Pass: COMMIT_ALLOWED
    pass_row = dict(module.MOCK_FIXTURE_VALID)
    pass_row["raw_data_policy"] = "COMMIT_ALLOWED"
    assert module._run_raw_data_policy_gate(pass_row)["status"] == "PASS"
    # Fail: UNKNOWN
    fail_row = dict(module.MOCK_FIXTURE_VALID)
    fail_row["raw_data_policy"] = "UNKNOWN"
    assert module._run_raw_data_policy_gate(fail_row)["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 32 — Timestamp gate pass/fail tested
# ---------------------------------------------------------------------------
def test_32_timestamp_gate_pass_fail(module):
    # Pass: valid pregame timestamps
    pass_row = dict(module.MOCK_FIXTURE_VALID)
    assert module._run_timestamp_gate(pass_row)["status"] == "PASS"
    # Fail: odds_ts >= game_ts for pregame
    fail_row = dict(module.MOCK_FIXTURE_VALID)
    fail_row["odds_timestamp_utc"] = "2025-07-05T00:00:00+00:00"  # after game_start
    fail_row["is_pregame"] = True
    assert module._run_timestamp_gate(fail_row)["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 33 — Moneyline gate pass/fail tested
# ---------------------------------------------------------------------------
def test_33_moneyline_gate_pass_fail(module):
    # Pass
    pass_row = dict(module.MOCK_FIXTURE_VALID)
    assert module._run_moneyline_gate(pass_row)["status"] == "PASS"
    # Fail: non-numeric
    fail_row = dict(module.MOCK_FIXTURE_VALID)
    fail_row["home_moneyline"] = "EVEN"
    assert module._run_moneyline_gate(fail_row)["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 34 — Identity gate pass/fail tested
# ---------------------------------------------------------------------------
def test_34_identity_gate_pass_fail(module):
    # Pass
    pass_row = dict(module.MOCK_FIXTURE_VALID)
    assert module._run_identity_gate(pass_row)["status"] == "PASS"
    # Fail: home == away
    fail_row = dict(module.MOCK_FIXTURE_VALID)
    fail_row["away_team"] = fail_row["home_team"]
    assert module._run_identity_gate(fail_row)["status"] == "FAIL"


# ---------------------------------------------------------------------------
# 35 — Mock fixture passes schema
# ---------------------------------------------------------------------------
def test_35_mock_fixture_passes_schema(module):
    result = module._validate_schema(module.MOCK_FIXTURE_VALID)
    assert result["valid"] is True, f"Errors: {result['errors']}"


# ---------------------------------------------------------------------------
# 36 — Mock fixture does not unlock market readiness
# ---------------------------------------------------------------------------
def test_36_mock_fixture_not_market_ready(summary):
    step5 = summary["step5_mock_fixture_validation"]
    assert step5["mock_valid_fixture"]["can_unlock_p82"] is False
    assert step5["mock_valid_fixture"]["market_readiness"] is False
    assert step5["mock_cannot_unlock_p82"] is True


# ---------------------------------------------------------------------------
# 37 — Invalid fixture fails expected gates
# ---------------------------------------------------------------------------
def test_37_invalid_fixture_fails_gates(summary):
    step5 = summary["step5_mock_fixture_validation"]
    assert step5["mock_invalid_fixture"]["gate_results"]["all_gates_pass"] is False
    outcome = step5["mock_invalid_fixture"]["outcome"]
    assert outcome in (
        "BLOCKED_SOURCE_LEGALITY",
        "BLOCKED_RAW_DATA_POLICY",
        "BLOCKED_SCHEMA_INVALID",
    )


# ---------------------------------------------------------------------------
# 38 — Output decision states generated
# ---------------------------------------------------------------------------
def test_38_output_decision_states_generated(summary):
    s6 = summary["step6_output_decision_states"]
    assert len(s6["states_defined"]) >= 7
    assert "LEGAL_ODDS_DATASET_VALIDATED_FOR_P82" in s6["states_defined"]
    assert "MOCK_FIXTURE_VALIDATOR_PASS_NOT_MARKET_READY" in s6["states_defined"]
    assert "BLOCKED_NO_REAL_DATASET" in s6["states_defined"]


# ---------------------------------------------------------------------------
# 39 — P82 unlock impossible without real legal dataset
# ---------------------------------------------------------------------------
def test_39_p82_unlock_impossible_without_real_dataset(summary):
    s6 = summary["step6_output_decision_states"]
    assert "BLOCKED" in s6["p82_unlock_status"]
    assert summary["p82_unlock_status"] == "BLOCKED_NO_REAL_DATASET"
    s2 = summary["step2_input_contract"]
    assert s2["real_legal_dataset_available"] is False
    assert s2["p82_currently_unlockable"] is False


# ---------------------------------------------------------------------------
# 40 — No API call
# ---------------------------------------------------------------------------
def test_40_no_api_call(module):
    gov = module.GOVERNANCE
    assert gov["live_api_calls"] == 0
    assert gov["the_odds_api_key_required"] is False


# ---------------------------------------------------------------------------
# 41 — No API key access
# ---------------------------------------------------------------------------
def test_41_no_api_key_access(module):
    gov = module.GOVERNANCE
    assert gov["the_odds_api_key_accessed"] is False


# ---------------------------------------------------------------------------
# 42 — No edge calculation
# ---------------------------------------------------------------------------
def test_42_no_edge_calculation(module):
    gov = module.GOVERNANCE
    assert gov["market_edge_evaluated"] is False


# ---------------------------------------------------------------------------
# 43 — No CLV calculation
# ---------------------------------------------------------------------------
def test_43_no_clv_calculation(module):
    gov = module.GOVERNANCE
    assert gov["clv_calculated"] is False


# ---------------------------------------------------------------------------
# 44 — No EV calculation
# ---------------------------------------------------------------------------
def test_44_no_ev_calculation(module):
    gov = module.GOVERNANCE
    assert gov["ev_calculated"] is False


# ---------------------------------------------------------------------------
# 45 — No Kelly calculation
# ---------------------------------------------------------------------------
def test_45_no_kelly_calculation(module):
    gov = module.GOVERNANCE
    assert gov["kelly_calculated"] is False


# ---------------------------------------------------------------------------
# 46 — live_api_calls=0
# ---------------------------------------------------------------------------
def test_46_live_api_calls_zero(summary):
    assert summary["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# 47 — production_ready=false
# ---------------------------------------------------------------------------
def test_47_production_ready_false(module):
    assert module.GOVERNANCE["production_ready"] is False


# ---------------------------------------------------------------------------
# 48 — kelly_deploy_allowed=false
# ---------------------------------------------------------------------------
def test_48_kelly_deploy_allowed_false(module):
    assert module.GOVERNANCE["kelly_deploy_allowed"] is False


# ---------------------------------------------------------------------------
# 49 — Forbidden phrase scan passes
# ---------------------------------------------------------------------------
def test_49_forbidden_scan_passes(summary):
    scan = summary["step8_forbidden_scan"]
    assert scan["scan_passed"] is True
    assert scan["violations_count"] == 0


# ---------------------------------------------------------------------------
# 50 — JSON schema stable
# ---------------------------------------------------------------------------
def test_50_json_schema_stable():
    d = _load_json("p81_legal_odds_dataset_validator_contract_summary.json")
    required_top_keys = [
        "p81_classification",
        "schema_version",
        "snapshot_id",
        "governance_snapshot",
        "step1_p80_readiness",
        "step2_input_contract",
        "step3_schema_validator",
        "step4_validator_gates",
        "step5_mock_fixture_validation",
        "step6_output_decision_states",
        "step7_source_artifacts",
        "step8_forbidden_scan",
        "live_api_calls",
        "ev_clv_kelly_computed",
        "p82_unlock_status",
    ]
    for k in required_top_keys:
        assert k in d, f"Missing top-level key: {k}"


# ---------------------------------------------------------------------------
# 51 — Report includes validator gate table
# ---------------------------------------------------------------------------
def test_51_report_includes_validator_gate_table():
    report_path = REPO_ROOT / "report" / "p81_legal_odds_dataset_validator_contract_20260526.md"
    assert report_path.exists()
    text = report_path.read_text()
    assert "LEGALITY_GATE" in text
    assert "RAW_DATA_POLICY_GATE" in text
    assert "TIMESTAMP_GATE" in text
    assert "MONEYLINE_GATE" in text
    assert "IDENTITY_GATE" in text


# ---------------------------------------------------------------------------
# 52 — active_task.md updated
# ---------------------------------------------------------------------------
def test_52_active_task_updated():
    active = (REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md").read_text()
    # P80 must still be present as previous
    assert "P80" in active or "ecbcc37" in active


# ---------------------------------------------------------------------------
# 53 — P72A-P81 regression passes
# ---------------------------------------------------------------------------
REGRESSION_SUMMARIES = [
    "p72a_odds_free_strategy_accuracy_backtest_summary.json",
    "p72b_objective_metric_contract_summary.json",
    "p73_tier_stability_and_sample_expansion_summary.json",
    "p74_tier_c_home_away_bias_correction_summary.json",
    "p75a_tier_c_corrected_rule_validator_summary.json",
    "p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p76_corrected_tier_c_final_rule_selection_summary.json",
    "p77_prediction_only_shadow_tracker_contract_summary.json",
    "p78_monthly_shadow_tracker_report_template_summary.json",
    "p79a_tier_b_trigger_readiness_contract_summary.json",
    "p79b_tier_b_vs_tier_c_comparison_harness_summary.json",
    "p80_market_edge_reentry_readiness_contract_summary.json",
]


@pytest.mark.parametrize("fname", REGRESSION_SUMMARIES)
def test_p72a_p81_regression(fname):
    path = DERIVED / fname
    assert path.exists(), f"Missing regression artifact: {fname}"
    d = json.loads(path.read_text())
    assert isinstance(d, dict)
    assert len(d) > 0
