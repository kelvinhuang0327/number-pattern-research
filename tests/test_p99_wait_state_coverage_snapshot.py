"""
Tests for P99 Wait-State Coverage Snapshot / Outcome-Ingestion Readiness Check
===============================================================================
20 test cases covering upstream verification, coverage snapshot, ingestion
readiness, recheck trigger, wait-state recommendation, classification,
and governance.
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
P99_PATH = REPO_ROOT / "data/mlb_2026/derived/p99_wait_state_coverage_snapshot_summary.json"

ALLOWED_P99_CLASSIFICATIONS = {
    "P99_WAIT_STATE_CONFIRMED_NO_RERUN",
    "P99_WAIT_STATE_UPDATED_BUT_NO_RERUN",
    "P99_READY_FOR_P96_RERUN_AUTHORIZATION",
    "P99_WAIT_STATE_SNAPSHOT_FAILED_VALIDATION",
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

FORBIDDEN_KEYWORDS_IN_ALLOWED = [
    "production_promotion",
    "recommendation_surface",
    "odds_integration",
    "ev_clv",
    "kelly_computation",
    "calibration_refit",
    "champion_replacement",
    "taiwan_lottery_paper",
    "stake_sizing",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p99() -> dict:
    return json.loads(P99_PATH.read_text())


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
# Test 1: P98 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_01_p98_exists_and_classification_matches(p98):
    assert P98_PATH.exists(), "P98 summary file must exist"
    assert p98["final_classification"] == "P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED"


# ---------------------------------------------------------------------------
# Test 2: P97 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_02_p97_exists_and_classification_matches(p97):
    assert P97_PATH.exists(), "P97 summary file must exist"
    assert p97["final_classification"] == "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED"


# ---------------------------------------------------------------------------
# Test 3: P96 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_03_p96_exists_and_classification_matches(p96):
    assert P96_PATH.exists(), "P96 summary file must exist"
    assert p96["final_classification"] == "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED"


# ---------------------------------------------------------------------------
# Test 4: P95 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_04_p95_exists_and_classification_matches(p95):
    assert P95_PATH.exists(), "P95 summary file must exist"
    assert p95["final_classification"] == "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE"


# ---------------------------------------------------------------------------
# Test 5: P94 summary exists and classification matches
# ---------------------------------------------------------------------------

def test_05_p94_exists_and_classification_matches(p94):
    assert P94_PATH.exists(), "P94 summary file must exist"
    assert p94["final_classification"] == "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"


# ---------------------------------------------------------------------------
# Test 6: P99 summary JSON exists after script run
# ---------------------------------------------------------------------------

def test_06_p99_summary_json_exists():
    assert P99_PATH.exists(), "P99 output JSON must exist after script execution"


# ---------------------------------------------------------------------------
# Test 7: Current coverage snapshot exists with required keys
# ---------------------------------------------------------------------------

def test_07_coverage_snapshot_exists(p99):
    s2 = p99.get("step2_coverage_snapshot")
    assert s2 is not None, "step2_coverage_snapshot must be present in P99 summary"
    required_keys = [
        "total_canonical_rows", "outcome_available_rows", "rows_with_sp_fip_delta",
        "high_fip_rows", "mid_fip_rows", "low_fip_rows",
        "observed_months", "n_observed_months", "schedule_coverage_pct",
        "outcome_coverage_pct", "date_range", "schedule_rows",
    ]
    for key in required_keys:
        assert key in s2, f"step2_coverage_snapshot missing key: {key}"


# ---------------------------------------------------------------------------
# Test 8: Baseline comparison vs P98 exists
# ---------------------------------------------------------------------------

def test_08_baseline_comparison_vs_p98_exists(p99):
    s2 = p99["step2_coverage_snapshot"]
    comp = s2.get("p98_baseline_comparison")
    assert comp is not None, "p98_baseline_comparison must be present in step2"
    required_keys = [
        "p98_baseline_canonical_rows", "p98_baseline_outcome_rows",
        "p98_baseline_high_fip_n", "p98_baseline_coverage_pct",
        "p98_baseline_observed_months",
        "delta_canonical_rows", "delta_outcome_rows", "delta_high_fip_rows",
        "delta_observed_months", "delta_schedule_coverage_pct",
        "coverage_unchanged", "material_change",
    ]
    for key in required_keys:
        assert key in comp, f"p98_baseline_comparison missing key: {key}"


# ---------------------------------------------------------------------------
# Test 9: Delta rows are computed
# ---------------------------------------------------------------------------

def test_09_delta_rows_computed(p99):
    s2 = p99["step2_coverage_snapshot"]
    comp = s2["p98_baseline_comparison"]

    # All deltas must be integers (or zero)
    for key in ["delta_canonical_rows", "delta_outcome_rows", "delta_high_fip_rows",
                "delta_mid_fip_rows", "delta_low_fip_rows", "delta_observed_months"]:
        assert key in comp, f"delta key missing: {key}"
        val = comp[key]
        assert isinstance(val, int), f"{key} should be int, got {type(val)}"

    # With no new data since P98: expect all zero
    assert comp["delta_canonical_rows"] == 0, "Expected delta_canonical_rows=0"
    assert comp["delta_outcome_rows"] == 0, "Expected delta_outcome_rows=0"
    assert comp["delta_high_fip_rows"] == 0, "Expected delta_high_fip_rows=0"


# ---------------------------------------------------------------------------
# Test 10: Outcome-ingestion readiness block exists
# ---------------------------------------------------------------------------

def test_10_ingestion_readiness_block_exists(p99):
    s3 = p99.get("step3_ingestion_readiness")
    assert s3 is not None, "step3_ingestion_readiness must be present"
    assert "ingestion_readiness" in s3, "ingestion_readiness field must exist"
    assert "checks" in s3, "checks dict must exist in step3"
    valid_readiness = {"READY_FOR_FUTURE_OUTCOME_APPEND", "BLOCKED_SCHEMA_OR_GOVERNANCE"}
    assert s3["ingestion_readiness"] in valid_readiness, (
        f"ingestion_readiness={s3['ingestion_readiness']!r} not in {valid_readiness}"
    )


# ---------------------------------------------------------------------------
# Test 11: Required fields are checked
# ---------------------------------------------------------------------------

def test_11_required_fields_checked(p99):
    s3 = p99["step3_ingestion_readiness"]
    assert "required_fields_checked" in s3, "required_fields_checked must be listed"
    required = s3["required_fields_checked"]
    essential = [
        "game_date", "game_id", "outcome_available", "sp_fip_delta",
        "predicted_side", "actual_winner", "is_correct", "model_probability",
        "paper_only", "diagnostic_only", "production_ready", "odds_used",
    ]
    for field in essential:
        assert field in required, f"Required field {field!r} not in required_fields_checked"

    checks = s3.get("checks", {})
    assert checks.get("required_fields_present", False) is True, (
        "required_fields_present must be True — all required fields should be present in P84E"
    )


# ---------------------------------------------------------------------------
# Test 12: Governance row checks are enforced
# ---------------------------------------------------------------------------

def test_12_governance_row_checks_enforced(p99):
    s3 = p99["step3_ingestion_readiness"]
    checks = s3.get("checks", {})

    # All governance row checks must pass
    assert checks.get("no_production_ready_rows") is True, (
        "no_production_ready_rows must be True — no P84E row should have production_ready=true"
    )
    assert checks.get("no_odds_used_rows") is True, (
        "no_odds_used_rows must be True — no P84E row should have odds_used=true"
    )
    assert checks.get("no_paper_only_false_rows") is True, (
        "no_paper_only_false_rows must be True — no P84E row should have paper_only=false"
    )
    assert checks.get("no_diagnostic_only_false_rows") is True, (
        "no_diagnostic_only_false_rows must be True — no P84E row should have diagnostic_only=false"
    )

    # Verify violation counts are all zero
    violations = checks.get("governance_row_violations", {})
    for key, count in violations.items():
        assert count == 0, f"governance_row_violations[{key!r}]={count}, expected 0"


# ---------------------------------------------------------------------------
# Test 13: Recheck trigger state exists
# ---------------------------------------------------------------------------

def test_13_recheck_trigger_state_exists(p99):
    s4 = p99.get("step4_recheck_trigger_state")
    assert s4 is not None, "step4_recheck_trigger_state must be present"
    assert "thresholds" in s4, "thresholds list must be present"
    assert "p96_rerun_ready" in s4, "p96_rerun_ready must be present"
    assert "ready_count" in s4, "ready_count must be present"
    assert "wait_count" in s4, "wait_count must be present"

    expected_threshold_names = {
        "coverage_threshold_for_p96_rerun",
        "season_span_threshold",
        "incremental_outcome_rows_since_p98",
        "incremental_high_fip_rows_since_p98",
        "combined_rerun_gate",
    }
    actual_names = {t["threshold"] for t in s4["thresholds"]}
    assert expected_threshold_names == actual_names, (
        f"threshold names mismatch: {actual_names}"
    )


# ---------------------------------------------------------------------------
# Test 14: p96_rerun_ready is false when thresholds are not met
# ---------------------------------------------------------------------------

def test_14_p96_rerun_ready_false(p99):
    s4 = p99["step4_recheck_trigger_state"]
    assert s4["p96_rerun_ready"] is False, (
        "p96_rerun_ready must be False — coverage=34.07% (threshold 60%), months=3 (threshold 4)"
    )
    # Verify the two primary thresholds are WAIT
    coverage_t = next(t for t in s4["thresholds"] if t["threshold"] == "coverage_threshold_for_p96_rerun")
    season_t = next(t for t in s4["thresholds"] if t["threshold"] == "season_span_threshold")
    assert coverage_t["status"] == "WAIT", f"coverage_threshold_for_p96_rerun should be WAIT, got {coverage_t['status']}"
    assert season_t["status"] == "WAIT", f"season_span_threshold should be WAIT, got {season_t['status']}"


# ---------------------------------------------------------------------------
# Test 15: Wait-state recommendation exists
# ---------------------------------------------------------------------------

def test_15_wait_state_recommendation_exists(p99):
    s5 = p99.get("step5_wait_state_recommendation")
    assert s5 is not None, "step5_wait_state_recommendation must be present"
    assert "state" in s5, "state field must be in wait-state recommendation"
    assert "recommendation" in s5, "recommendation field must be present"
    assert "reason" in s5, "reason field must be present"

    valid_states = {"WAIT_ACCUMULATE", "READY_FOR_P96_RERUN"}
    assert s5["state"] in valid_states, f"state={s5['state']!r} not in {valid_states}"

    valid_recommendations = {
        "NO_RERUN",
        "SNAPSHOT_ONLY_NO_P96_RERUN",
        "REQUEST_CEO_AUTHORIZATION_FOR_P96_RERUN",
    }
    assert s5["recommendation"] in valid_recommendations, (
        f"recommendation={s5['recommendation']!r} not in {valid_recommendations}"
    )

    # Expected: no rerun since no new data
    assert s5["state"] == "WAIT_ACCUMULATE", "Expected WAIT_ACCUMULATE (no new data since P98)"
    assert s5["recommendation"] == "NO_RERUN", "Expected NO_RERUN (coverage unchanged)"


# ---------------------------------------------------------------------------
# Test 16: Allowed actions contain only diagnostic-safe actions
# ---------------------------------------------------------------------------

def test_16_allowed_actions_diagnostic_safe(p99):
    s5 = p99["step5_wait_state_recommendation"]
    allowed = s5["allowed_next_actions"]
    assert len(allowed) >= 1, "Must have at least 1 allowed action"

    for action in allowed:
        assert action.get("safe", True) is True, (
            f"All allowed actions must be safe=True, got safe={action.get('safe')} for {action['action']}"
        )
        name = action["action"].lower()
        for kw in FORBIDDEN_KEYWORDS_IN_ALLOWED:
            assert kw not in name, (
                f"Allowed action '{name}' contains forbidden keyword '{kw}'"
            )


# ---------------------------------------------------------------------------
# Test 17: Prohibited actions include production, recommendation, odds, EV/CLV/Kelly,
#          calibration refit, champion replacement
# ---------------------------------------------------------------------------

def test_17_prohibited_actions_comprehensive(p99):
    s5 = p99["step5_wait_state_recommendation"]
    prohibited_names = {p["action"] for p in s5["prohibited_next_actions"]}
    missing = EXPECTED_PROHIBITED_ACTIONS - prohibited_names
    assert not missing, f"Missing required prohibited actions: {missing}"


# ---------------------------------------------------------------------------
# Test 18: final_classification is in allowed P99 list
# ---------------------------------------------------------------------------

def test_18_final_classification_in_allowed_list(p99):
    fc = p99["final_classification"]
    assert fc in ALLOWED_P99_CLASSIFICATIONS, (
        f"final_classification={fc!r} not in allowed list {ALLOWED_P99_CLASSIFICATIONS}"
    )
    # Expected given no new data since P98
    assert fc == "P99_WAIT_STATE_CONFIRMED_NO_RERUN", (
        f"Expected P99_WAIT_STATE_CONFIRMED_NO_RERUN (no material change since P98), got {fc!r}"
    )


# ---------------------------------------------------------------------------
# Test 19: Governance flags all pass
# ---------------------------------------------------------------------------

def test_19_governance_flags_all_pass(p99):
    guards = p99["governance_guards"]

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
    assert p99.get("paper_only") is True
    assert p99.get("diagnostic_only") is True
    assert p99.get("production_ready") is False
    assert p99.get("real_bet_allowed") is False
    assert p99.get("recommendation_allowed") is False
    assert p99.get("product_surface_allowed") is False


# ---------------------------------------------------------------------------
# Test 20: No production/recommendation/calibration/odds/EV/CLV/Kelly flags enabled
# ---------------------------------------------------------------------------

def test_20_no_forbidden_flags_enabled(p99):
    guards = p99["governance_guards"]

    forbidden_pairs = [
        ("odds_used", False),
        ("ev_computed", False),
        ("clv_computed", False),
        ("kelly_computed", False),
        ("stake_sizing", False),
        ("taiwan_lottery_recommendation", False),
        ("champion_replacement", False),
        ("production_mutation", False),
        ("calibration_refit", False),
        ("platt_scaling", False),
        ("isotonic_scaling", False),
        ("score_transform_refit", False),
        ("live_api_calls", 0),
        ("paid_api_calls", 0),
        ("canonical_rows_modified", False),
        ("outcome_rows_modified", False),
        ("p83e_mapping_modified", False),
        ("source_artifacts_modified", False),
    ]

    for flag, expected in forbidden_pairs:
        val = guards.get(flag, "MISSING")
        assert val == expected or val is expected, (
            f"governance_guards[{flag!r}] = {val!r}, expected {expected!r}. "
            "This flag must not be enabled in any diagnostic-only phase."
        )

    # Also confirm ingestion readiness — no governance violations in rows
    s3 = p99.get("step3_ingestion_readiness", {})
    assert s3.get("ingestion_readiness") == "READY_FOR_FUTURE_OUTCOME_APPEND", (
        "Ingestion readiness must be READY_FOR_FUTURE_OUTCOME_APPEND — no governance violations in P84E rows"
    )
