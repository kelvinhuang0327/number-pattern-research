"""
Tests for P97 HIGH_FIP Production-Gate Preflight
=================================================
20 test cases covering all gates, blockers, governance, and classification.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

P93_PATH = REPO_ROOT / "data/mlb_2026/derived/p93_prediction_only_coverage_feature_bias_audit_summary.json"
P94_PATH = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
P95_PATH = REPO_ROOT / "data/mlb_2026/derived/p95_fip_stratified_shadow_tracker_summary.json"
P96_PATH = REPO_ROOT / "data/mlb_2026/derived/p96_high_fip_segment_drift_monitor_summary.json"
P97_PATH = REPO_ROOT / "data/mlb_2026/derived/p97_high_fip_production_gate_preflight_summary.json"

ALLOWED_P97_CLASSIFICATIONS = {
    "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED",
    "P97_HIGH_FIP_PREFLIGHT_PARTIAL_PASS_REQUIRES_MORE_COVERAGE",
    "P97_HIGH_FIP_PREFLIGHT_FAILED_VALIDATION",
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

EXPECTED_BLOCKERS = {
    "DATA_COVERAGE_BLOCKER",
    "CALIBRATION_BLOCKER",
    "LEGAL_ODDS_BLOCKER",
    "MARKET_EDGE_BLOCKER",
    "RISK_CONTROL_BLOCKER",
    "PRODUCT_GOVERNANCE_BLOCKER",
}

SAFE_ALLOWED_KEYWORDS = {
    "continue_accumulating",
    "rerun_p96",
    "design_calibration_diagnostic",
    "keep_high_fip_shadow",
    "keep_mid_low_watch",
}

PROHIBITED_KEYWORDS = {
    "production_promotion",
    "recommendation",
    "odds",
    "ev_clv_kelly",
    "calibration_refit",
    "champion",
    "taiwan_lottery",
    "stake_sizing",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def p96_data() -> dict:
    return json.loads(P96_PATH.read_text())


@pytest.fixture(scope="module")
def p95_data() -> dict:
    return json.loads(P95_PATH.read_text())


@pytest.fixture(scope="module")
def p94_data() -> dict:
    return json.loads(P94_PATH.read_text())


@pytest.fixture(scope="module")
def p97_data() -> dict:
    return json.loads(P97_PATH.read_text())


def _get_gate(p97: dict, gate_name: str) -> dict:
    gates = p97["step2_readiness_checklist"]["gates"]
    for g in gates:
        if g["gate"] == gate_name:
            return g
    raise KeyError(f"Gate not found: {gate_name}")


# ---------------------------------------------------------------------------
# Test 1: P96 summary exists + classification matches
# ---------------------------------------------------------------------------

def test_01_p96_exists_and_classification_matches(p96_data):
    assert P96_PATH.exists(), "P96 summary file must exist"
    assert p96_data["final_classification"] == "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED"


# ---------------------------------------------------------------------------
# Test 2: P95 summary exists + classification matches
# ---------------------------------------------------------------------------

def test_02_p95_exists_and_classification_matches(p95_data):
    assert P95_PATH.exists(), "P95 summary file must exist"
    assert p95_data["final_classification"] == "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE"


# ---------------------------------------------------------------------------
# Test 3: P94 summary exists + classification matches
# ---------------------------------------------------------------------------

def test_03_p94_exists_and_classification_matches(p94_data):
    assert P94_PATH.exists(), "P94 summary file must exist"
    assert p94_data["final_classification"] == "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"


# ---------------------------------------------------------------------------
# Test 4: P97 summary JSON exists
# ---------------------------------------------------------------------------

def test_04_p97_summary_json_exists():
    assert P97_PATH.exists(), "P97 output JSON must exist after script execution"


# ---------------------------------------------------------------------------
# Test 5: prediction_signal_gate = PASS
# ---------------------------------------------------------------------------

def test_05_prediction_signal_gate_pass(p97_data):
    gate = _get_gate(p97_data, "prediction_signal_gate")
    assert gate["status"] == "PASS", f"prediction_signal_gate expected PASS, got {gate['status']}"
    assert gate["blocker_category"] is None


# ---------------------------------------------------------------------------
# Test 6: segment_scope_gate = PASS
# ---------------------------------------------------------------------------

def test_06_segment_scope_gate_pass(p97_data):
    gate = _get_gate(p97_data, "segment_scope_gate")
    assert gate["status"] == "PASS", f"segment_scope_gate expected PASS, got {gate['status']}"
    assert gate["blocker_category"] is None


# ---------------------------------------------------------------------------
# Test 7: coverage_gate = FAIL at 34.07%
# ---------------------------------------------------------------------------

def test_07_coverage_gate_fail(p97_data):
    gate = _get_gate(p97_data, "coverage_gate")
    assert gate["status"] == "FAIL", f"coverage_gate expected FAIL (34.07% < 60%), got {gate['status']}"
    assert gate["blocker_category"] == "DATA_COVERAGE_BLOCKER"
    s1 = p97_data["step1_upstream_verification"]
    cov_pct = s1["schedule_coverage_pct"]
    assert cov_pct < 60.0, f"Coverage {cov_pct}% should be below 60%"
    assert abs(cov_pct - 34.0741) < 0.01, f"Coverage should be ~34.07%, got {cov_pct}"


# ---------------------------------------------------------------------------
# Test 8: season_span_gate = FAIL for 3 months
# ---------------------------------------------------------------------------

def test_08_season_span_gate_fail(p97_data):
    gate = _get_gate(p97_data, "season_span_gate")
    assert gate["status"] == "FAIL", f"season_span_gate expected FAIL (3 months < 4), got {gate['status']}"
    assert gate["blocker_category"] == "DATA_COVERAGE_BLOCKER"
    observed_months = p97_data["step1_upstream_verification"]["observed_months"]
    assert len(observed_months) == 3, f"Expected 3 observed months, got {len(observed_months)}"


# ---------------------------------------------------------------------------
# Test 9: calibration_gate = FAIL
# ---------------------------------------------------------------------------

def test_09_calibration_gate_fail(p97_data):
    gate = _get_gate(p97_data, "calibration_gate")
    assert gate["status"] == "FAIL"
    assert gate["blocker_category"] == "CALIBRATION_BLOCKER"


# ---------------------------------------------------------------------------
# Test 10: odds_dataset_gate = FAIL
# ---------------------------------------------------------------------------

def test_10_odds_dataset_gate_fail(p97_data):
    gate = _get_gate(p97_data, "odds_dataset_gate")
    assert gate["status"] == "FAIL"
    assert gate["blocker_category"] == "LEGAL_ODDS_BLOCKER"


# ---------------------------------------------------------------------------
# Test 11: market_edge_gate = FAIL
# ---------------------------------------------------------------------------

def test_11_market_edge_gate_fail(p97_data):
    gate = _get_gate(p97_data, "market_edge_gate")
    assert gate["status"] == "FAIL"
    assert gate["blocker_category"] == "MARKET_EDGE_BLOCKER"


# ---------------------------------------------------------------------------
# Test 12: risk_control_gate = FAIL
# ---------------------------------------------------------------------------

def test_12_risk_control_gate_fail(p97_data):
    gate = _get_gate(p97_data, "risk_control_gate")
    assert gate["status"] == "FAIL"
    assert gate["blocker_category"] == "RISK_CONTROL_BLOCKER"


# ---------------------------------------------------------------------------
# Test 13: production_governance_gate = FAIL
# ---------------------------------------------------------------------------

def test_13_production_governance_gate_fail(p97_data):
    gate = _get_gate(p97_data, "production_governance_gate")
    assert gate["status"] == "FAIL"
    assert gate["blocker_category"] == "PRODUCT_GOVERNANCE_BLOCKER"


# ---------------------------------------------------------------------------
# Test 14: readiness_ratio computed and < 1.0
# ---------------------------------------------------------------------------

def test_14_readiness_ratio_lt_one(p97_data):
    s3 = p97_data["step3_readiness_scoring"]
    ratio = s3["readiness_ratio"]
    assert isinstance(ratio, float), "readiness_ratio must be a float"
    assert 0.0 <= ratio < 1.0, f"readiness_ratio={ratio} expected < 1.0"
    assert s3["pass_count"] == 2, f"Expected 2 gates to PASS, got {s3['pass_count']}"
    assert s3["fail_count"] == 8, f"Expected 8 gates to FAIL, got {s3['fail_count']}"
    assert s3["production_ready"] is False


# ---------------------------------------------------------------------------
# Test 15: blocker matrix has all 6 blockers
# ---------------------------------------------------------------------------

def test_15_blocker_matrix_complete(p97_data):
    s4 = p97_data["step4_blocker_matrix"]
    actual_blockers = set(s4["blocker_names"])
    assert EXPECTED_BLOCKERS == actual_blockers, (
        f"Blocker mismatch. Missing: {EXPECTED_BLOCKERS - actual_blockers}, "
        f"Extra: {actual_blockers - EXPECTED_BLOCKERS}"
    )
    assert s4["blocker_count"] == 6


# ---------------------------------------------------------------------------
# Test 16: allowed_next_actions are diagnostic-safe only
# ---------------------------------------------------------------------------

def test_16_allowed_actions_are_safe(p97_data):
    s5 = p97_data["step5_next_actions"]
    allowed = s5["allowed_next_actions"]
    assert len(allowed) >= 1, "Must have at least 1 allowed action"

    for action in allowed:
        assert action.get("safe", True) is True, (
            f"All allowed actions must be safe=True, got safe={action.get('safe')} for {action['action']}"
        )

    # None of the allowed actions should contain production/recommendation/odds/EV/Kelly keywords
    for action in allowed:
        name = action["action"].lower()
        description = action.get("description", "").lower()
        for forbidden_term in ["production", "recommendation", "odds", "ev_clv", "kelly", "refit", "champion", "taiwan_lottery"]:
            assert forbidden_term not in name, (
                f"Allowed action '{name}' contains forbidden term '{forbidden_term}'"
            )


# ---------------------------------------------------------------------------
# Test 17: prohibited_next_actions include production/recommendation/odds/EV/CLV/Kelly/refit/champion
# ---------------------------------------------------------------------------

def test_17_prohibited_actions_comprehensive(p97_data):
    s5 = p97_data["step5_next_actions"]
    prohibited = s5["prohibited_next_actions"]
    prohibited_names = {p["action"] for p in prohibited}

    required_prohibited = {
        "production_promotion",
        "recommendation_surface",
        "odds_integration",
        "ev_clv_kelly_computation",
        "calibration_refit",
        "champion_replacement",
        "taiwan_lottery_paper_recommendation",
        "stake_sizing",
    }
    missing = required_prohibited - prohibited_names
    assert not missing, f"Missing prohibited actions: {missing}"


# ---------------------------------------------------------------------------
# Test 18: final_classification in allowed P97 list
# ---------------------------------------------------------------------------

def test_18_final_classification_in_allowed_list(p97_data):
    fc = p97_data["final_classification"]
    assert fc in ALLOWED_P97_CLASSIFICATIONS, (
        f"final_classification={fc!r} not in allowed list {ALLOWED_P97_CLASSIFICATIONS}"
    )
    # Specifically expect the signal-pass-blocked classification given upstream state
    assert fc == "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED"


# ---------------------------------------------------------------------------
# Test 19: governance flags all pass
# ---------------------------------------------------------------------------

def test_19_governance_flags_all_pass(p97_data):
    guards = p97_data["governance_guards"]

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


# ---------------------------------------------------------------------------
# Test 20: no production/recommendation/calibration/odds/EV/CLV/Kelly flags enabled
# ---------------------------------------------------------------------------

def test_20_no_production_capability_flags_enabled(p97_data):
    # Top-level flags
    assert p97_data.get("paper_only") is True
    assert p97_data.get("diagnostic_only") is True
    assert p97_data.get("production_ready") is False
    assert p97_data.get("real_bet_allowed") is False
    assert p97_data.get("recommendation_allowed") is False
    assert p97_data.get("product_surface_allowed") is False

    # Guards embedded
    guards = p97_data["governance_guards"]
    production_flags = [
        "odds_used", "ev_computed", "clv_computed", "kelly_computed",
        "stake_sizing", "taiwan_lottery_recommendation", "champion_replacement",
        "production_mutation", "calibration_refit", "platt_scaling",
        "isotonic_scaling", "score_transform_refit",
    ]
    for flag in production_flags:
        val = guards.get(flag, "MISSING")
        assert val is False, (
            f"Expected guards[{flag!r}]=False (no production capability), got {val!r}"
        )

    # Confirm step3 agrees
    assert p97_data["step3_readiness_scoring"]["production_ready"] is False

    # Confirm no prohibited actions are allowed
    s5 = p97_data["step5_next_actions"]
    allowed_names = {a["action"] for a in s5["allowed_next_actions"]}
    assert "production_promotion" not in allowed_names
    assert "recommendation_surface" not in allowed_names
    assert "ev_clv_kelly_computation" not in allowed_names
