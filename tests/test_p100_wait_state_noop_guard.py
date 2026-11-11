"""
tests/test_p100_wait_state_noop_guard.py
=========================================
20 tests for P100 Wait-State No-Op Guard.

Run:
    pytest tests/test_p100_wait_state_noop_guard.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Artifact paths
P94_PATH = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
P95_PATH = REPO_ROOT / "data/mlb_2026/derived/p95_fip_stratified_shadow_tracker_summary.json"
P96_PATH = REPO_ROOT / "data/mlb_2026/derived/p96_high_fip_segment_drift_monitor_summary.json"
P97_PATH = REPO_ROOT / "data/mlb_2026/derived/p97_high_fip_production_gate_preflight_summary.json"
P98_PATH = REPO_ROOT / "data/mlb_2026/derived/p98_data_coverage_accumulation_gate_summary.json"
P99_PATH = REPO_ROOT / "data/mlb_2026/derived/p99_wait_state_coverage_snapshot_summary.json"
P100_PATH = REPO_ROOT / "data/mlb_2026/derived/p100_wait_state_noop_guard_summary.json"

ALLOWED_CLASSIFICATIONS = [
    "P100_WAIT_STATE_NOOP_CONFIRMED",
    "P100_WAIT_STATE_UPDATED_SNAPSHOT_REQUIRED",
    "P100_READY_FOR_CEO_RERUN_AUTHORIZATION",
    "P100_WAIT_STATE_NOOP_FAILED_VALIDATION",
]

FORBIDDEN_ACTION_SUBSTRINGS = [
    "production_promot",
    "recommendation_surface",
    "odds_integrat",
    "ev_clv_kelly",
    "calibration_refit",
    "champion_replacement",
    "taiwan_lottery_paper_recommend",
    "stake_sizing",
]

SAFE_ALLOWED_ACTIONS_SUBSTRINGS = [
    "wait",
    "monitor",
    "rerun_p99",
    "rerun_p100",
    "request_ceo",
]


@pytest.fixture(scope="module")
def p100() -> dict:
    assert P100_PATH.exists(), f"P100 summary JSON missing: {P100_PATH}"
    return json.loads(P100_PATH.read_text())


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
# Test 1: P99 summary exists + correct classification
# ---------------------------------------------------------------------------
def test_t01_p99_exists_and_classification(p99):
    assert P99_PATH.exists()
    assert p99.get("final_classification") == "P99_WAIT_STATE_CONFIRMED_NO_RERUN"


# ---------------------------------------------------------------------------
# Test 2: P98 summary exists + correct classification
# ---------------------------------------------------------------------------
def test_t02_p98_exists_and_classification(p98):
    assert P98_PATH.exists()
    assert p98.get("final_classification") == "P98_WAIT_ACCUMULATE_COVERAGE_UNCHANGED"


# ---------------------------------------------------------------------------
# Test 3: P97 summary exists + correct classification
# ---------------------------------------------------------------------------
def test_t03_p97_exists_and_classification(p97):
    assert P97_PATH.exists()
    assert p97.get("final_classification") == "P97_HIGH_FIP_PREFLIGHT_SIGNAL_PASS_PRODUCTION_BLOCKED"


# ---------------------------------------------------------------------------
# Test 4: P96 summary exists + correct classification
# ---------------------------------------------------------------------------
def test_t04_p96_exists_and_classification(p96):
    assert P96_PATH.exists()
    assert p96.get("final_classification") == "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED"


# ---------------------------------------------------------------------------
# Test 5: P95 summary exists + correct classification
# ---------------------------------------------------------------------------
def test_t05_p95_exists_and_classification(p95):
    assert P95_PATH.exists()
    assert p95.get("final_classification") == "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE"


# ---------------------------------------------------------------------------
# Test 6: P94 summary exists + correct classification
# ---------------------------------------------------------------------------
def test_t06_p94_exists_and_classification(p94):
    assert P94_PATH.exists()
    assert p94.get("final_classification") == "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"


# ---------------------------------------------------------------------------
# Test 7: P100 summary JSON exists after script run
# ---------------------------------------------------------------------------
def test_t07_p100_summary_json_exists(p100):
    assert P100_PATH.exists()
    assert isinstance(p100, dict)
    assert p100.get("phase") == "P100"


# ---------------------------------------------------------------------------
# Test 8: step2_data_recount exists with required sub-keys
# ---------------------------------------------------------------------------
def test_t08_step2_data_recount_structure(p100):
    s2 = p100.get("step2_data_recount", {})
    required_keys = [
        "total_canonical_rows", "outcome_available_rows", "high_fip_rows",
        "mid_fip_rows", "low_fip_rows", "n_observed_months",
        "schedule_coverage_pct", "outcome_coverage_pct", "date_range",
        "p99_baseline_comparison", "status",
    ]
    for k in required_keys:
        assert k in s2, f"step2 missing key: {k}"
    assert s2["status"] == "PASSED"


# ---------------------------------------------------------------------------
# Test 9: step2 baseline comparison sub-keys exist (delta fields)
# ---------------------------------------------------------------------------
def test_t09_step2_baseline_comparison_fields(p100):
    comp = p100["step2_data_recount"]["p99_baseline_comparison"]
    required = [
        "p99_baseline_canonical_rows", "p99_baseline_outcome_rows",
        "p99_baseline_high_fip_n", "p99_baseline_coverage_pct",
        "p99_baseline_observed_months", "delta_canonical_rows",
        "delta_outcome_rows", "delta_high_fip_rows",
        "delta_observed_months", "delta_schedule_coverage_pct",
    ]
    for k in required:
        assert k in comp, f"p99_baseline_comparison missing key: {k}"


# ---------------------------------------------------------------------------
# Test 10: delta rows are all 0 (no new data since P99)
# ---------------------------------------------------------------------------
def test_t10_delta_rows_all_zero(p100):
    comp = p100["step2_data_recount"]["p99_baseline_comparison"]
    assert comp["delta_canonical_rows"] == 0, "Expected delta_canonical_rows=0 (no new data)"
    assert comp["delta_outcome_rows"] == 0, "Expected delta_outcome_rows=0 (no new data)"
    assert comp["delta_high_fip_rows"] == 0, "Expected delta_high_fip_rows=0 (no new data)"


# ---------------------------------------------------------------------------
# Test 11: step3_noop_decision exists with noop_state field
# ---------------------------------------------------------------------------
def test_t11_step3_noop_decision_structure(p100):
    s3 = p100.get("step3_noop_decision", {})
    required = [
        "noop_state", "delta_outcome_rows", "delta_high_fip_rows",
        "schedule_coverage_pct", "observed_months",
        "above_coverage_threshold", "above_months_threshold",
        "no_new_data", "new_data_exists", "ceo_gate_triggered",
        "thresholds", "status",
    ]
    for k in required:
        assert k in s3, f"step3 missing key: {k}"
    assert s3["status"] == "PASSED"


# ---------------------------------------------------------------------------
# Test 12: NOOP_CONFIRMED path works when delta=0 and thresholds not met
# ---------------------------------------------------------------------------
def test_t12_noop_confirmed_path(p100):
    s3 = p100["step3_noop_decision"]
    assert s3["noop_state"] == "NOOP_CONFIRMED", (
        f"Expected NOOP_CONFIRMED, got {s3['noop_state']!r} "
        f"(delta_outcome={s3['delta_outcome_rows']}, delta_high_fip={s3['delta_high_fip_rows']}, "
        f"cov={s3['schedule_coverage_pct']}, months={s3['observed_months']})"
    )
    assert s3["no_new_data"] is True
    assert s3["new_data_exists"] is False
    assert s3["ceo_gate_triggered"] is False


# ---------------------------------------------------------------------------
# Test 13: UPDATED_SNAPSHOT_REQUIRED decision logic
# ---------------------------------------------------------------------------
def test_t13_updated_snapshot_required_decision_logic():
    """Unit test: simulate new rows but thresholds not met → UPDATED_SNAPSHOT_REQUIRED."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from _p100_wait_state_noop_guard import step3_noop_decision

    s2_mock: dict = {
        "schedule_coverage_pct": 45.0,
        "n_observed_months": 3,
        "p99_baseline_comparison": {
            "delta_outcome_rows": 50,
            "delta_high_fip_rows": 10,
        },
    }
    result = step3_noop_decision(s2_mock)
    assert result["noop_state"] == "UPDATED_SNAPSHOT_REQUIRED", (
        f"Expected UPDATED_SNAPSHOT_REQUIRED, got {result['noop_state']!r}"
    )


# ---------------------------------------------------------------------------
# Test 14: CEO_RERUN_AUTH_REQUIRED path works
# ---------------------------------------------------------------------------
def test_t14_ceo_rerun_auth_required_path():
    """Unit test: coverage>=60 AND months>=4 → CEO_RERUN_AUTH_REQUIRED."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from _p100_wait_state_noop_guard import step3_noop_decision

    s2_mock: dict = {
        "schedule_coverage_pct": 65.0,
        "n_observed_months": 5,
        "p99_baseline_comparison": {
            "delta_outcome_rows": 300,
            "delta_high_fip_rows": 100,
        },
    }
    result = step3_noop_decision(s2_mock)
    assert result["noop_state"] == "CEO_RERUN_AUTH_REQUIRED", (
        f"Expected CEO_RERUN_AUTH_REQUIRED, got {result['noop_state']!r}"
    )
    assert result["ceo_gate_triggered"] is True


# ---------------------------------------------------------------------------
# Test 15: step4 wait_state_instruction has required fields
# ---------------------------------------------------------------------------
def test_t15_step4_instruction_structure(p100):
    s4 = p100.get("step4_wait_state_instruction", {})
    required = [
        "noop_state", "action", "reason",
        "recommended_next", "next_check_trigger",
        "allowed_next_actions", "prohibited_next_actions", "status",
    ]
    for k in required:
        assert k in s4, f"step4 missing key: {k}"
    assert s4["status"] == "PASSED"
    assert isinstance(s4["allowed_next_actions"], list)
    assert isinstance(s4["prohibited_next_actions"], list)


# ---------------------------------------------------------------------------
# Test 16: final_classification is in allowed P100 list
# ---------------------------------------------------------------------------
def test_t16_final_classification_in_allowed_list(p100):
    fc = p100.get("final_classification")
    assert fc in ALLOWED_CLASSIFICATIONS, (
        f"final_classification {fc!r} not in allowed list"
    )
    # For the expected current state:
    assert fc == "P100_WAIT_STATE_NOOP_CONFIRMED"


# ---------------------------------------------------------------------------
# Test 17: governance_guards all pass
# ---------------------------------------------------------------------------
def test_t17_governance_guards_all_pass(p100):
    gov = p100.get("governance_guards", {})
    assert gov.get("status") == "PASSED", "governance_guards.status must be PASSED"
    assert gov.get("paper_only") is True
    assert gov.get("diagnostic_only") is True
    assert gov.get("production_ready") is False
    assert gov.get("real_bet_allowed") is False
    assert gov.get("recommendation_allowed") is False
    assert gov.get("product_surface_allowed") is False


# ---------------------------------------------------------------------------
# Test 18: no production/recommendation/odds/EV/Kelly flags enabled
# ---------------------------------------------------------------------------
def test_t18_no_forbidden_flags_enabled(p100):
    gov = p100.get("governance_guards", {})
    top = p100
    forbidden_booleans = [
        "odds_used", "ev_computed", "clv_computed", "kelly_computed",
        "stake_sizing", "taiwan_lottery_recommendation", "champion_replacement",
        "production_mutation", "calibration_refit", "platt_scaling",
        "isotonic_scaling", "score_transform_refit",
        "canonical_rows_modified", "outcome_rows_modified",
        "p83e_mapping_modified", "source_artifacts_modified",
    ]
    # Check in governance_guards first
    for f in forbidden_booleans:
        val_gov = gov.get(f)
        val_top = top.get(f)
        assert val_gov is not True, f"governance_guards.{f} must not be True"
        assert val_top is not True, f"top-level {f} must not be True"

    assert gov.get("live_api_calls", 0) == 0
    assert gov.get("paid_api_calls", 0) == 0


# ---------------------------------------------------------------------------
# Test 19: allowed_next_actions contain only safe actions
# ---------------------------------------------------------------------------
def test_t19_allowed_actions_are_safe(p100):
    s4 = p100.get("step4_wait_state_instruction", {})
    allowed = s4.get("allowed_next_actions", [])
    assert len(allowed) > 0, "allowed_next_actions must not be empty"
    for entry in allowed:
        action_name = entry.get("action", "").lower()
        desc = entry.get("description", "").lower()
        assert entry.get("safe") is True, (
            f"allowed action {action_name!r} must have safe=True"
        )
        # None of the safe actions should contain forbidden keywords
        for forbidden in FORBIDDEN_ACTION_SUBSTRINGS:
            assert forbidden not in action_name, (
                f"allowed action {action_name!r} contains forbidden keyword {forbidden!r}"
            )
        # Verify it matches safe patterns
        is_safe_action = any(kw in action_name or kw in desc for kw in SAFE_ALLOWED_ACTIONS_SUBSTRINGS)
        assert is_safe_action, (
            f"Allowed action {action_name!r} does not match any safe pattern in {SAFE_ALLOWED_ACTIONS_SUBSTRINGS}"
        )


# ---------------------------------------------------------------------------
# Test 20: prohibited_next_actions cover all required forbidden categories
# ---------------------------------------------------------------------------
def test_t20_prohibited_actions_cover_all_categories(p100):
    s4 = p100.get("step4_wait_state_instruction", {})
    prohibited = s4.get("prohibited_next_actions", [])
    assert len(prohibited) > 0, "prohibited_next_actions must not be empty"

    prohibited_action_names = [p.get("action", "").lower() for p in prohibited]
    prohibited_reasons = [p.get("reason", "").lower() for p in prohibited]

    required_prohibited_categories = [
        ("production_promot", "production promotion must be prohibited"),
        ("recommendation_surface", "recommendation surface must be prohibited"),
        ("odds_integrat", "odds integration must be prohibited"),
        ("ev_clv_kelly", "EV/CLV/Kelly computation must be prohibited"),
        ("calibration_refit", "calibration refit must be prohibited"),
        ("champion_replacement", "champion replacement must be prohibited"),
    ]
    for keyword, msg in required_prohibited_categories:
        matched = any(
            keyword in name or keyword in reason
            for name, reason in zip(prohibited_action_names, prohibited_reasons)
        )
        assert matched, f"Missing prohibited category: {msg} (keyword={keyword!r})"
