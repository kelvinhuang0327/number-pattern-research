"""
Tests for P65 — Paper Simulation Walk-Forward Validation
=========================================================
Minimum 24 tests covering all P65 contract invariants.

Validates:
  - P64 artifacts load correctly
  - P64 governance invariants preserved
  - All walk-forward window types generated
  - Per-window required metrics present
  - Stability classification is a valid allowed value
  - Diagnostic recommendations contain no production actions
  - 2024 data gap documented as unresolved
  - Forbidden affirmative scan = 0 violations
  - All P65 governance flags preserved
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2025" / "derived"

P65_SUMMARY_PATH = DERIVED / "p65_paper_simulation_walk_forward_validation_summary.json"
P64_ROWS_PATH = DERIVED / "p64_paper_simulation_rows.jsonl"
P64_SUMMARY_PATH = DERIVED / "p64_paper_simulation_first_run_summary.json"
P62_PATH = DERIVED / "p62_paper_recommendation_contract_draft_summary.json"
P63_PATH = DERIVED / "p63_paper_recommendation_contract_review_readiness_summary.json"

ALLOWED_STABILITY_CLASSIFICATIONS = {
    "P65_EDGE_STABLE_POSITIVE",
    "P65_EDGE_MIXED_TIME_DEPENDENT",
    "P65_EDGE_STABLE_NEGATIVE",
    "P65_EDGE_INSUFFICIENT_WINDOW_SAMPLE",
    "P65_BLOCKED_BY_P64_SCHEMA_GAP",
    "P65_BLOCKED_BY_TEST_FAILURE",
}

ALLOWED_RECOMMENDATIONS = {
    "REVIEW_ODDS_MAPPING",
    "REVIEW_MODEL_CALIBRATION",
    "REVIEW_TIER_THRESHOLD",
    "RESOLVE_2024_DATA_GAP",
    "DO_NOT_PROCEED_TO_PRODUCT",
    "ALLOW_CONTRACT_ITERATION_ONLY",
}

FORBIDDEN_PRODUCTION_ACTIONS = {
    "DEPLOY_TO_PRODUCTION",
    "AUTHORIZE_LIVE_BETTING",
    "ENABLE_KELLY_STAKING",
    "REPLACE_CHAMPION",
    "RELEASE_REAL_BET",
    "APPROVE_LIVE_DEPLOYMENT",
}

WINDOW_REQUIRED_METRICS = [
    "n",
    "mean_edge",
    "median_edge",
    "std_edge",
    "min_edge",
    "max_edge",
    "positive_edge_count",
    "negative_edge_count",
    "positive_edge_rate",
    "mean_calibrated_prob",
    "mean_implied_prob",
    "status_distribution",
    "gate_distribution",
]


@pytest.fixture(scope="module")
def p65() -> dict:
    assert P65_SUMMARY_PATH.exists(), f"P65 summary not found: {P65_SUMMARY_PATH}"
    with open(P65_SUMMARY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p64_rows() -> list[dict]:
    assert P64_ROWS_PATH.exists(), f"P64 rows JSONL not found: {P64_ROWS_PATH}"
    rows = []
    with open(P64_ROWS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


@pytest.fixture(scope="module")
def p64_summary() -> dict:
    with open(P64_SUMMARY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p62() -> dict:
    with open(P62_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p63() -> dict:
    with open(P63_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test 1: P64 rows load successfully
# ---------------------------------------------------------------------------
def test_01_p64_rows_load(p64_rows):
    """P64 rows JSONL must load successfully with non-zero count."""
    assert len(p64_rows) > 0, "P64 rows JSONL is empty"


# ---------------------------------------------------------------------------
# Test 2: P64 summary loads successfully
# ---------------------------------------------------------------------------
def test_02_p64_summary_loads(p64_summary):
    """P64 summary JSON must load successfully."""
    assert "p64_classification" in p64_summary
    assert "simulation_scope" in p64_summary


# ---------------------------------------------------------------------------
# Test 3: P64 classification is valid at time of P65 validation
# ---------------------------------------------------------------------------
def test_03_p64_classification_valid(p65):
    """P65 summary must record P64 classification as P64_PAPER_SIMULATION_FIRST_RUN_READY."""
    p64_cl = p65["p64_baseline"]["classification"]
    assert p64_cl == "P64_PAPER_SIMULATION_FIRST_RUN_READY", (
        f"P64 classification: {p64_cl}"
    )


# ---------------------------------------------------------------------------
# Test 4: P65 row count matches P64 summary
# ---------------------------------------------------------------------------
def test_04_row_count_matches_summary(p65, p64_rows):
    """P65 baseline row count must match actual P64 rows loaded."""
    assert p65["p64_baseline"]["total_rows"] == 535
    assert len(p64_rows) == 535


# ---------------------------------------------------------------------------
# Test 5: All P64 rows preserve paper_only=True
# ---------------------------------------------------------------------------
def test_05_paper_only_preserved(p64_rows):
    """paper_only must be True in every P64 row used by P65."""
    violations = [r["game_id"] for r in p64_rows if r.get("paper_only") is not True]
    assert not violations, f"paper_only!=True in {len(violations)} rows"


# ---------------------------------------------------------------------------
# Test 6: All P64 rows preserve diagnostic_only=True
# ---------------------------------------------------------------------------
def test_06_diagnostic_only_preserved(p64_rows):
    """diagnostic_only must be True in every P64 row used by P65."""
    violations = [r["game_id"] for r in p64_rows if r.get("diagnostic_only") is not True]
    assert not violations, f"diagnostic_only!=True in {len(violations)} rows"


# ---------------------------------------------------------------------------
# Test 7: All P64 rows preserve production_ready=False
# ---------------------------------------------------------------------------
def test_07_production_ready_false_preserved(p64_rows):
    """production_ready must be False in every P64 row used by P65."""
    violations = [r["game_id"] for r in p64_rows if r.get("production_ready") is not False]
    assert not violations, f"production_ready!=False in {len(violations)} rows"


# ---------------------------------------------------------------------------
# Test 8: All P64 rows preserve real_bet_allowed=False
# ---------------------------------------------------------------------------
def test_08_real_bet_allowed_false_preserved(p64_rows):
    """real_bet_allowed must be False in every P64 row."""
    violations = [r["game_id"] for r in p64_rows if r.get("real_bet_allowed") is not False]
    assert not violations, f"real_bet_allowed!=False in {len(violations)} rows"


# ---------------------------------------------------------------------------
# Test 9: All P64 rows preserve kelly_deploy_allowed=False
# ---------------------------------------------------------------------------
def test_09_kelly_deploy_allowed_false_preserved(p64_rows):
    """kelly_deploy_allowed must be False in every P64 row."""
    violations = [r["game_id"] for r in p64_rows if r.get("kelly_deploy_allowed") is not False]
    assert not violations, f"kelly_deploy_allowed!=False in {len(violations)} rows"


# ---------------------------------------------------------------------------
# Test 10: No live API calls in P65 governance
# ---------------------------------------------------------------------------
def test_10_no_live_api_calls(p65):
    """P65 governance must record live_api_calls = 0."""
    gov = p65["governance"]
    assert gov["live_api_calls"] == 0


# ---------------------------------------------------------------------------
# Test 11: No paid API calls in P65 governance
# ---------------------------------------------------------------------------
def test_11_no_paid_api_calls(p65):
    """P65 governance must record paid_api_called = False."""
    gov = p65["governance"]
    assert gov["paid_api_called"] is False


# ---------------------------------------------------------------------------
# Test 12: Monthly windows generated (all 6 months present)
# ---------------------------------------------------------------------------
def test_12_monthly_windows_generated(p65):
    """Monthly windows must be generated for all months present in P64 rows."""
    monthly = p65["walk_forward"]["monthly_windows"]
    assert len(monthly) >= 1, "No monthly windows generated"
    # All expected months
    expected_months = {"2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"}
    actual_months = set(monthly.keys())
    assert expected_months == actual_months, (
        f"Monthly window mismatch. Expected: {expected_months}, Got: {actual_months}"
    )


# ---------------------------------------------------------------------------
# Test 13: Chronological thirds generated with correct keys
# ---------------------------------------------------------------------------
def test_13_chronological_thirds_generated(p65):
    """Chronological thirds must be generated with third_1, third_2, third_3."""
    thirds = p65["walk_forward"]["chronological_thirds"]
    assert "third_1" in thirds
    assert "third_2" in thirds
    assert "third_3" in thirds
    # Each third must have rows
    for k in ("third_1", "third_2", "third_3"):
        assert thirds[k]["n"] > 0, f"{k} has 0 rows"


# ---------------------------------------------------------------------------
# Test 14: Rolling windows generated (100-row, step 50)
# ---------------------------------------------------------------------------
def test_14_rolling_windows_generated(p65):
    """Rolling windows must be generated with at least 1 window."""
    rolling = p65["walk_forward"]["rolling_windows"]
    assert isinstance(rolling, list), "rolling_windows must be a list"
    assert len(rolling) >= 1, "No rolling windows generated"
    # Each window has n <= 100
    for w in rolling:
        assert w["n"] <= 100, f"Rolling window has n={w['n']} > 100"


# ---------------------------------------------------------------------------
# Test 15: Each window (monthly) contains all required metrics
# ---------------------------------------------------------------------------
def test_15_monthly_windows_have_required_metrics(p65):
    """Every monthly window must contain all required metric keys."""
    monthly = p65["walk_forward"]["monthly_windows"]
    for month, stats in monthly.items():
        missing = [k for k in WINDOW_REQUIRED_METRICS if k not in stats]
        assert not missing, f"Month {month} missing metrics: {missing}"


# ---------------------------------------------------------------------------
# Test 16: Positive edge rate computed and in [0, 1] for all windows
# ---------------------------------------------------------------------------
def test_16_positive_edge_rate_computed(p65):
    """positive_edge_rate must be in [0, 1] for all monthly windows."""
    monthly = p65["walk_forward"]["monthly_windows"]
    for month, stats in monthly.items():
        per = stats["positive_edge_rate"]
        assert per is not None, f"Month {month}: positive_edge_rate is None"
        assert 0.0 <= per <= 1.0, f"Month {month}: positive_edge_rate={per} out of [0,1]"


# ---------------------------------------------------------------------------
# Test 17: Mean edge computed for each chronological third
# ---------------------------------------------------------------------------
def test_17_mean_edge_computed_in_thirds(p65):
    """mean_edge must be computed (non-None) for all chronological thirds."""
    thirds = p65["walk_forward"]["chronological_thirds"]
    for k in ("third_1", "third_2", "third_3"):
        me = thirds[k]["mean_edge"]
        assert me is not None, f"{k}: mean_edge is None"
        assert isinstance(me, float), f"{k}: mean_edge is not float: {type(me)}"


# ---------------------------------------------------------------------------
# Test 18: Status distribution computed in thirds
# ---------------------------------------------------------------------------
def test_18_status_distribution_in_thirds(p65):
    """status_distribution must be a non-empty dict in each third."""
    thirds = p65["walk_forward"]["chronological_thirds"]
    for k in ("third_1", "third_2", "third_3"):
        dist = thirds[k].get("status_distribution", {})
        assert isinstance(dist, dict), f"{k}: status_distribution not a dict"
        assert len(dist) > 0, f"{k}: status_distribution is empty"


# ---------------------------------------------------------------------------
# Test 19: Gate status distribution computed in thirds
# ---------------------------------------------------------------------------
def test_19_gate_distribution_in_thirds(p65):
    """gate_distribution must be present and contain GATE_PASS for all thirds."""
    thirds = p65["walk_forward"]["chronological_thirds"]
    for k in ("third_1", "third_2", "third_3"):
        gate_dist = thirds[k].get("gate_distribution", {})
        assert "GATE_PASS" in gate_dist, (
            f"{k}: GATE_PASS not in gate_distribution: {gate_dist}"
        )


# ---------------------------------------------------------------------------
# Test 20: Stability classification is one of the allowed values
# ---------------------------------------------------------------------------
def test_20_stability_classification_is_valid(p65):
    """P65 stability classification must be one of the defined allowed values."""
    cl = p65["p65_classification"]
    assert cl in ALLOWED_STABILITY_CLASSIFICATIONS, (
        f"Invalid P65 classification: {cl}"
    )


# ---------------------------------------------------------------------------
# Test 21: Diagnostic recommendations contain no forbidden production actions
# ---------------------------------------------------------------------------
def test_21_recommendations_contain_no_production_actions(p65):
    """No recommendation may authorize production, live betting, or Kelly deployment."""
    recs = p65["diagnostic_recommendations"]
    assert isinstance(recs, list), "diagnostic_recommendations must be a list"
    for rec in recs:
        assert rec not in FORBIDDEN_PRODUCTION_ACTIONS, (
            f"Forbidden production action found in recommendations: {rec}"
        )
        assert rec in ALLOWED_RECOMMENDATIONS, (
            f"Unknown recommendation: {rec}"
        )


# ---------------------------------------------------------------------------
# Test 22: 2024 data gap remains documented as unresolved
# ---------------------------------------------------------------------------
def test_22_2024_data_gap_unresolved(p65):
    """2024 data gap must remain documented as unresolved in P65."""
    gov = p65["governance"]
    assert gov.get("data_year_2024_gap_remains_unresolved") is True, (
        "2024 data gap must remain unresolved in P65"
    )
    # Resolve recommendation must be present
    recs = p65["diagnostic_recommendations"]
    assert "RESOLVE_2024_DATA_GAP" in recs, (
        "RESOLVE_2024_DATA_GAP not in recommendations despite unresolved gap"
    )


# ---------------------------------------------------------------------------
# Test 23: Forbidden affirmative scan = 0 violations
# ---------------------------------------------------------------------------
def test_23_forbidden_scan_zero_violations(p65):
    """Forbidden affirmative scan must return 0 violations (CLEAN)."""
    scan = p65["forbidden_scan"]
    assert scan["violations"] == 0, (
        f"Forbidden scan violations: {scan['violations']}, details: {scan.get('details')}"
    )
    assert scan["result"] == "CLEAN", f"Forbidden scan result: {scan['result']}"


# ---------------------------------------------------------------------------
# Test 24: active_task.md was updated for P65
# ---------------------------------------------------------------------------
def test_24_active_task_updated(p65):
    """active_task.md must exist and contain P65 references after completion."""
    active_task_path = ROOT / "00-Plan" / "roadmap" / "active_task.md"
    assert active_task_path.exists(), "active_task.md not found"
    content = active_task_path.read_text()
    assert "P65" in content, "active_task.md does not mention P65"
    assert "P64" in content, "active_task.md does not mention P64 (prior phase)"


# ---------------------------------------------------------------------------
# Test 25: Rolling windows have date_start and date_end fields
# ---------------------------------------------------------------------------
def test_25_rolling_windows_have_date_range(p65):
    """Each rolling window must have date_start and date_end."""
    rolling = p65["walk_forward"]["rolling_windows"]
    for i, w in enumerate(rolling):
        assert "date_start" in w, f"Rolling window {i}: missing date_start"
        assert "date_end" in w, f"Rolling window {i}: missing date_end"
        assert w["date_start"] is not None, f"Rolling window {i}: date_start is None"
        assert w["date_end"] is not None, f"Rolling window {i}: date_end is None"


# ---------------------------------------------------------------------------
# Test 26: Chronological thirds sum to total row count
# ---------------------------------------------------------------------------
def test_26_thirds_sum_to_total(p65):
    """Sum of rows across all three thirds must equal 535."""
    thirds = p65["walk_forward"]["chronological_thirds"]
    total = sum(thirds[k]["n"] for k in ("third_1", "third_2", "third_3"))
    assert total == 535, f"Thirds sum to {total}, expected 535"


# ---------------------------------------------------------------------------
# Test 27: Half split generated with first and second halves
# ---------------------------------------------------------------------------
def test_27_half_split_generated(p65):
    """Half split must have first_half and second_half with rows."""
    halves = p65["walk_forward"]["half_split"]
    assert "first_half" in halves
    assert "second_half" in halves
    assert halves["first_half"]["n"] > 0
    assert halves["second_half"]["n"] > 0
    total = halves["first_half"]["n"] + halves["second_half"]["n"]
    assert total == 535, f"Half split sums to {total}, expected 535"


# ---------------------------------------------------------------------------
# Test 28: P65 governance flags preserved
# ---------------------------------------------------------------------------
def test_28_p65_governance_flags_preserved(p65):
    """All P65 governance flags must be set correctly."""
    gov = p65["governance"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["promotion_freeze"] is True
    assert gov["kelly_deploy_allowed"] is False
    assert gov["real_bet_allowed"] is False
    assert gov["production_ready"] is False
    assert gov["runtime_recommendation_logic_changed"] is False


# ---------------------------------------------------------------------------
# Test 29: P64 negative edge mean documented in P65 baseline
# ---------------------------------------------------------------------------
def test_29_p64_negative_edge_documented(p65):
    """P65 baseline must document P64 edge mean = -0.032473."""
    edge_mean = p65["p64_baseline"]["edge_mean"]
    assert abs(edge_mean - (-0.032473)) < 1e-4, (
        f"P64 edge mean in P65 baseline: {edge_mean}, expected ~-0.032473"
    )


# ---------------------------------------------------------------------------
# Test 30: Monthly window rows sum to 535
# ---------------------------------------------------------------------------
def test_30_monthly_windows_sum_to_535(p65):
    """Sum of rows across all monthly windows must equal 535."""
    monthly = p65["walk_forward"]["monthly_windows"]
    total = sum(stats["n"] for stats in monthly.values())
    assert total == 535, f"Monthly window row sum = {total}, expected 535"


# ---------------------------------------------------------------------------
# Test 31: April window has n=16 (smallest month)
# ---------------------------------------------------------------------------
def test_31_april_window_correct_count(p65):
    """April 2025 must have exactly 16 Tier C rows."""
    april = p65["walk_forward"]["monthly_windows"].get("2025-04")
    assert april is not None, "2025-04 monthly window missing"
    assert april["n"] == 16, f"April row count: {april['n']}, expected 16"


# ---------------------------------------------------------------------------
# Test 32: All thirds have date range fields
# ---------------------------------------------------------------------------
def test_32_thirds_have_date_range(p65):
    """Each third must have start and end date fields."""
    thirds = p65["walk_forward"]["chronological_thirds"]
    for k in ("third_1", "third_2", "third_3"):
        assert "start" in thirds[k], f"{k}: missing start date"
        assert "end" in thirds[k], f"{k}: missing end date"
        assert thirds[k]["start"] is not None
        assert thirds[k]["end"] is not None


# ---------------------------------------------------------------------------
# Test 33: DO_NOT_PROCEED_TO_PRODUCT in recommendations for negative edge
# ---------------------------------------------------------------------------
def test_33_do_not_proceed_to_product_in_recs(p65):
    """
    When P65 classification is P65_EDGE_STABLE_NEGATIVE or P65_EDGE_MIXED_TIME_DEPENDENT,
    DO_NOT_PROCEED_TO_PRODUCT must be in recommendations.
    """
    cl = p65["p65_classification"]
    recs = p65["diagnostic_recommendations"]
    if cl in ("P65_EDGE_STABLE_NEGATIVE", "P65_EDGE_MIXED_TIME_DEPENDENT"):
        assert "DO_NOT_PROCEED_TO_PRODUCT" in recs, (
            f"Classification is {cl} but DO_NOT_PROCEED_TO_PRODUCT missing from recs"
        )


# ---------------------------------------------------------------------------
# Test 34: Rolling windows have chronological ordering
# ---------------------------------------------------------------------------
def test_34_rolling_windows_chronological(p65):
    """Rolling windows must be in chronological order (date_start non-decreasing)."""
    rolling = p65["walk_forward"]["rolling_windows"]
    for i in range(1, len(rolling)):
        prev = rolling[i - 1]["date_start"]
        curr = rolling[i]["date_start"]
        assert curr >= prev, (
            f"Rolling window {i}: date_start={curr} < prev={prev} (not chronological)"
        )


# ---------------------------------------------------------------------------
# Test 35: P65 summary output file exists on disk
# ---------------------------------------------------------------------------
def test_35_p65_summary_output_exists():
    """P65 summary JSON output file must exist on disk after pipeline run."""
    assert P65_SUMMARY_PATH.exists(), f"P65 summary not found at {P65_SUMMARY_PATH}"
    # Validate it's parseable JSON
    with open(P65_SUMMARY_PATH) as f:
        data = json.load(f)
    assert "p65_classification" in data


# ---------------------------------------------------------------------------
# Test 36: Monthly edge standard deviation computed for months with n > 1
# ---------------------------------------------------------------------------
def test_36_monthly_std_edge_computed(p65):
    """std_edge must be a non-negative float for monthly windows with n > 1."""
    monthly = p65["walk_forward"]["monthly_windows"]
    for month, stats in monthly.items():
        if stats["n"] > 1:
            std = stats["std_edge"]
            assert std is not None, f"Month {month}: std_edge is None"
            assert std >= 0.0, f"Month {month}: std_edge={std} is negative"
