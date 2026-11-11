"""
Tests for P98 Data Coverage Accumulation Gate
==============================================
20 test cases covering upstream verification, coverage recount,
threshold logic, wait-state contract, classification, and governance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

P94_PATH = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
P95_PATH = REPO_ROOT / "data/mlb_2026/derived/p95_fip_stratified_shadow_tracker_summary.json"
P96_PATH = REPO_ROOT / "data/mlb_2026/derived/p96_high_fip_segment_drift_monitor_summary.json"
P97_PATH = REPO_ROOT / "data/mlb_2026/derived/p97_high_fip_production_gate_preflight_summary.json"
P98_PATH = REPO_ROOT / "data/mlb_2026/derived/p98_data_coverage_accumulation_gate_summary.json"

ALLOWED_P98_CLASSIFICATIONS = {
    "P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED",
    "P98_WAIT_ACCUMULATE_COVERAGE_INSUFFICIENT",
    "P98_READY_TO_RERUN_P96_COVERAGE_THRESHOLD_MET",
    "P98_DATA_COVERAGE_GATE_FAILED_VALIDATION",
}

EXPECTED_GOVERNANCE_FALSE_FLAGS = [
    "odds_used",
    "ev_computed",
    "clv_computed",
    "kelly_computed",
    "stake_sizing",
    "taiwan_lottery_recommendation",
    "champion_replacement",
    "production_mutation",
    "calibration_refit",
    "platt_scaling",
    "isotonic_scaling",
    "score_transform_refit",
    "canonical_rows_modified",
    "outcome_rows_modified",
    "p83e_mapping_modified",
    "source_artifacts_modified",
]

EXPECTED_GOVERNANCE_TRUE_FLAGS = [
    "paper_only",
    "diagnostic_only",
]

EXPECTED_PROHIBITED_ACTIONS = {
    "production_promotion",
    "recommendation_surface",
    "odds_integration",
    "ev_clv_kelly_computation",
    "calibration_refit",
    "champion_replacement",
    "taiwan_lottery_paper_recommendation",
    "stake_sizing",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p98() -> dict:
    return json.loads(P98_PATH.read_text())


@pytest.fixture(scope="module")
def p97() -> dict:
    return json.loads(P97_PATH.read_text())


@pytest.fixture(scope="module")
def p96() -> dict:
    return json.loads(P96_PATH.read_text())


@pytest.fixture(scope="module")
def p95() -> dict:
    return json.loads(P95_PATH.read_text())


@pytest.fixture(scope="module")
def p94() -> dict:
    return json.loads(P94_PATH.read_text())


# ---------------------------------------------------------------------------
# Test 1: P97 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_01_p97_exists_and_classification_matches(p97):
    assert P97_PATH.exists(), "P97 summary file must exist"
    assert p97["final_classification"] == "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED"


# ---------------------------------------------------------------------------
# Test 2: P96 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_02_p96_exists_and_classification_matches(p96):
    assert P96_PATH.exists(), "P96 summary file must exist"
    assert p96["final_classification"] == "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED"


# ---------------------------------------------------------------------------
# Test 3: P95 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_03_p95_exists_and_classification_matches(p95):
    assert P95_PATH.exists(), "P95 summary file must exist"
    assert p95["final_classification"] == "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE"


# ---------------------------------------------------------------------------
# Test 4: P94 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_04_p94_exists_and_classification_matches(p94):
    assert P94_PATH.exists(), "P94 summary file must exist"
    assert p94["final_classification"] == "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"


# ---------------------------------------------------------------------------
# Test 5: P98 summary JSON exists after script run
# ---------------------------------------------------------------------------

def test_05_p98_summary_json_exists():
    assert P98_PATH.exists(), "P98 output JSON must exist after script execution"


# ---------------------------------------------------------------------------
# Test 6: Current coverage recount is present
# ---------------------------------------------------------------------------

def test_06_coverage_recount_present(p98):
    s2 = p98.get("step2_coverage_recount")
    assert s2 is not None, "step2_coverage_recount must be present in P98 summary"
    required_keys = [
        "total_canonical_rows", "outcome_available_rows", "rows_with_sp_fip_delta",
        "high_fip_rows", "mid_fip_rows", "low_fip_rows",
        "observed_months", "n_observed_months", "schedule_coverage_pct",
        "outcome_coverage_pct", "date_range",
    ]
    for key in required_keys:
        assert key in s2, f"step2_coverage_recount missing key: {key}"


# ---------------------------------------------------------------------------
# Test 7: schedule_rows = 2430
# ---------------------------------------------------------------------------

def test_07_schedule_rows_2430(p98):
    s2 = p98["step2_coverage_recount"]
    assert s2["schedule_rows"] == 2430, f"schedule_rows should be 2430, got {s2['schedule_rows']}"


# ---------------------------------------------------------------------------
# Test 8: schedule_coverage_pct is computed
# ---------------------------------------------------------------------------

def test_08_schedule_coverage_pct_computed(p98):
    s2 = p98["step2_coverage_recount"]
    cov = s2["schedule_coverage_pct"]
    assert isinstance(cov, float), "schedule_coverage_pct must be a float"
    assert 0.0 < cov < 100.0, f"schedule_coverage_pct={cov} should be between 0 and 100"
    # Should be ~34.07% based on known P84E state
    assert abs(cov - 34.07) < 0.1, f"schedule_coverage_pct={cov}% expected ~34.07%"


# ---------------------------------------------------------------------------
# Test 9: observed_months is computed
# ---------------------------------------------------------------------------

def test_09_observed_months_computed(p98):
    s2 = p98["step2_coverage_recount"]
    n = s2["n_observed_months"]
    months = s2["observed_months"]
    assert isinstance(n, int), "n_observed_months must be an int"
    assert n >= 1, "Must have at least 1 observed month"
    assert len(months) == n, f"len(observed_months)={len(months)} must match n_observed_months={n}"
    # Known: March–May 2026 = 3 months
    assert n == 3, f"Expected 3 observed months (Mar/Apr/May 2026), got {n}"


# ---------------------------------------------------------------------------
# Test 10: HIGH_FIP n is computed
# ---------------------------------------------------------------------------

def test_10_high_fip_n_computed(p98):
    s2 = p98["step2_coverage_recount"]
    n = s2["high_fip_rows"]
    assert isinstance(n, int), "high_fip_rows must be an int"
    assert n > 0, "high_fip_rows must be > 0"
    # Known: HIGH_FIP n=287 from P94/P95/P96
    assert n == 287, f"Expected HIGH_FIP n=287, got {n}"


# ---------------------------------------------------------------------------
# Test 11: Baseline comparison against P97 is present
# ---------------------------------------------------------------------------

def test_11_baseline_comparison_present(p98):
    s4 = p98.get("step4_baseline_comparison")
    assert s4 is not None, "step4_baseline_comparison must be present"
    assert "p97_baseline" in s4, "p97_baseline dict must be in step4"
    assert "current" in s4, "current dict must be in step4"
    assert "deltas" in s4, "deltas dict must be in step4"
    assert "coverage_unchanged" in s4, "coverage_unchanged must be in step4"


# ---------------------------------------------------------------------------
# Test 12: delta rows are computed
# ---------------------------------------------------------------------------

def test_12_delta_rows_computed(p98):
    s4 = p98["step4_baseline_comparison"]
    deltas = s4["deltas"]
    for key in ["delta_canonical_rows", "delta_outcome_rows", "delta_high_fip_rows",
                "delta_coverage_pct", "delta_observed_months"]:
        assert key in deltas, f"deltas missing key: {key}"
    # All deltas should be 0 since no new data since P97
    assert deltas["delta_canonical_rows"] == 0, "Expected delta_canonical_rows=0 (no new data)"
    assert deltas["delta_outcome_rows"] == 0, "Expected delta_outcome_rows=0 (no new data)"
    assert deltas["delta_high_fip_rows"] == 0, "Expected delta_high_fip_rows=0 (no new data)"


# ---------------------------------------------------------------------------
# Test 13: recheck thresholds are present
# ---------------------------------------------------------------------------

def test_13_recheck_thresholds_present(p98):
    s3 = p98.get("step3_recheck_thresholds")
    assert s3 is not None, "step3_recheck_thresholds must be present"
    assert "thresholds" in s3, "thresholds list must be present"
    threshold_names = {t["threshold"] for t in s3["thresholds"]}
    expected = {
        "coverage_threshold_for_p96_rerun",
        "season_span_threshold",
        "incremental_rows_threshold",
        "high_fip_incremental_threshold",
        "production_preflight_threshold",
    }
    assert expected == threshold_names, f"threshold names mismatch: {threshold_names}"


# ---------------------------------------------------------------------------
# Test 14: coverage threshold returns WAIT when coverage <60
# ---------------------------------------------------------------------------

def test_14_coverage_threshold_wait(p98):
    s3 = p98["step3_recheck_thresholds"]
    coverage_thresh = next(
        t for t in s3["thresholds"] if t["threshold"] == "coverage_threshold_for_p96_rerun"
    )
    assert coverage_thresh["status"] == "WAIT", (
        f"coverage_threshold_for_p96_rerun should be WAIT when coverage={coverage_thresh.get('current_value')}% < 60%"
    )
    assert coverage_thresh.get("current_value", 100) < 60.0


# ---------------------------------------------------------------------------
# Test 15: season span threshold returns WAIT when observed_months <4
# ---------------------------------------------------------------------------

def test_15_season_span_threshold_wait(p98):
    s3 = p98["step3_recheck_thresholds"]
    span_thresh = next(
        t for t in s3["thresholds"] if t["threshold"] == "season_span_threshold"
    )
    assert span_thresh["status"] == "WAIT", (
        f"season_span_threshold should be WAIT when observed_months={span_thresh.get('current_value')} < 4"
    )
    assert span_thresh.get("current_value", 10) < 4


# ---------------------------------------------------------------------------
# Test 16: wait-state contract exists
# ---------------------------------------------------------------------------

def test_16_wait_state_contract_exists(p98):
    s5 = p98.get("step5_wait_state_contract")
    assert s5 is not None, "step5_wait_state_contract must be present"
    assert "state" in s5, "state field must be in wait-state contract"
    assert "next_recheck_trigger" in s5, "next_recheck_trigger must be in wait-state contract"
    assert "allowed_next_actions" in s5, "allowed_next_actions must be present"
    assert "prohibited_next_actions" in s5, "prohibited_next_actions must be present"

    state = s5["state"]
    valid_states = {
        "WAIT_ACCUMULATE_COVERAGE_UNCHANGED",
        "WAIT_ACCUMULATE_COVERAGE_INSUFFICIENT",
        "READY_TO_RERUN_P96",
    }
    assert state in valid_states, f"state={state!r} not in valid states {valid_states}"


# ---------------------------------------------------------------------------
# Test 17: allowed actions contain only diagnostic-safe actions
# ---------------------------------------------------------------------------

def test_17_allowed_actions_diagnostic_safe(p98):
    s5 = p98["step5_wait_state_contract"]
    allowed = s5["allowed_next_actions"]
    assert len(allowed) >= 1, "Must have at least 1 allowed action"

    forbidden_keywords = [
        "production", "recommendation", "odds_integration",
        "ev_clv", "kelly", "refit", "champion", "taiwan_lottery",
    ]
    for action in allowed:
        assert action.get("safe", True) is True, (
            f"All allowed actions must be safe=True, got safe={action.get('safe')} for {action['action']}"
        )
        name = action["action"].lower()
        for kw in forbidden_keywords:
            assert kw not in name, (
                f"Allowed action '{name}' contains forbidden keyword '{kw}'"
            )


# ---------------------------------------------------------------------------
# Test 18: prohibited actions include production, recommendation, odds, EV/CLV/Kelly,
#          calibration refit, champion replacement
# ---------------------------------------------------------------------------

def test_18_prohibited_actions_comprehensive(p98):
    s5 = p98["step5_wait_state_contract"]
    prohibited_names = {p["action"] for p in s5["prohibited_next_actions"]}
    missing = EXPECTED_PROHIBITED_ACTIONS - prohibited_names
    assert not missing, f"Missing required prohibited actions: {missing}"


# ---------------------------------------------------------------------------
# Test 19: final_classification is in allowed P98 list
# ---------------------------------------------------------------------------

def test_19_final_classification_in_allowed_list(p98):
    fc = p98["final_classification"]
    assert fc in ALLOWED_P98_CLASSIFICATIONS, (
        f"final_classification={fc!r} not in allowed list {ALLOWED_P98_CLASSIFICATIONS}"
    )
    # Given no new data, expect WAIT_ACCUMULATE_COVERAGE_UNCHANGED
    assert fc == "P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED", (
        f"Expected P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED (no new data since P97), got {fc!r}"
    )


# ---------------------------------------------------------------------------
# Test 20: governance flags all pass
# ---------------------------------------------------------------------------

def test_20_governance_flags_all_pass(p98):
    guards = p98["governance_guards"]

    for flag in EXPECTED_GOVERNANCE_FALSE_FLAGS:
        val = guards.get(flag, "MISSING")
        assert val is False or val == 0, (
            f"governance_guards[{flag!r}] should be False/0, got {val!r}"
        )

    for flag in EXPECTED_GOVERNANCE_TRUE_FLAGS:
        val = guards.get(flag, "MISSING")
        assert val is True, (
            f"governance_guards[{flag!r}] should be True, got {val!r}"
        )

    assert guards.get("live_api_calls", -1) == 0
    assert guards.get("paid_api_calls", -1) == 0
    assert guards.get("production_ready", True) is False
    assert guards.get("real_bet_allowed", True) is False
    assert guards.get("recommendation_allowed", True) is False
    assert guards.get("product_surface_allowed", True) is False

    # Top-level flags
    assert p98.get("paper_only") is True
    assert p98.get("diagnostic_only") is True
    assert p98.get("production_ready") is False
    assert p98.get("real_bet_allowed") is False
    assert p98.get("recommendation_allowed") is False
    assert p98.get("product_surface_allowed") is False
