"""
Tests for P66 — Odds Mapping Integrity Audit
============================================
Minimum 25 tests covering all P66 contract invariants.

Validates:
  - All artifacts load successfully
  - P64/P65 classifications are valid
  - Join audit metrics computed correctly
  - Side mapping is consistent (Home → Home ML, Away → Away ML)
  - American odds conversion formulas verified
  - Edge recalculation matches original within tolerance
  - Forbidden scan = 0 violations
  - All governance flags preserved
  - 2024 data gap remains unresolved
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

P66_SUMMARY_PATH = DERIVED / "p66_odds_mapping_integrity_audit_summary.json"
P64_ROWS_PATH = DERIVED / "p64_paper_simulation_rows.jsonl"
P64_SUMMARY_PATH = DERIVED / "p64_paper_simulation_first_run_summary.json"
P65_SUMMARY_PATH = DERIVED / "p65_paper_simulation_walk_forward_validation_summary.json"
ODDS_CSV_PATH = ROOT / "data" / "mlb_2025" / "mlb_odds_2025_real.csv"
PREDICTIONS_PATH = DERIVED / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"

ALLOWED_P66_CLASSIFICATIONS = {
    "P66_ODDS_MAPPING_INTEGRITY_CONFIRMED",
    "P66_ODDS_MAPPING_ERROR_FOUND",
    "P66_SIDE_INVERSION_FOUND",
    "P66_ODDS_CONVERSION_ERROR_FOUND",
    "P66_EDGE_CALCULATION_ERROR_FOUND",
    "P66_BLOCKED_BY_SCHEMA_GAP",
    "P66_BLOCKED_BY_TEST_FAILURE",
}

PLATT_A = 0.435432
PLATT_B = 0.245464
EDGE_TOLERANCE = 1e-4


def platt_calibrate(p: float, a: float, b: float) -> float:
    """Platt formula matching P64: 1 / (1 + exp(-A * logit(p) - B))."""
    p = max(1e-9, min(1.0 - 1e-9, p))
    logit_p = math.log(p / (1.0 - p))
    return 1.0 / (1.0 + math.exp(-a * logit_p - b))


def american_to_decimal(ml_str: str) -> float | None:
    if not ml_str or str(ml_str).strip() in ("", "nan", "NaN", "None"):
        return None
    try:
        val = float(str(ml_str).strip().replace(" ", ""))
    except (ValueError, TypeError):
        return None
    if val == 0:
        return None
    if val > 0:
        return 1.0 + val / 100.0
    else:
        return 1.0 + 100.0 / abs(val)


@pytest.fixture(scope="module")
def p66() -> dict:
    assert P66_SUMMARY_PATH.exists(), f"P66 summary not found: {P66_SUMMARY_PATH}"
    with open(P66_SUMMARY_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def p64_rows() -> list[dict]:
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
def p65_summary() -> dict:
    with open(P65_SUMMARY_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Test 1: P64 rows load
# ---------------------------------------------------------------------------
def test_01_p64_rows_load(p64_rows):
    """P64 rows must load with 535 entries."""
    assert len(p64_rows) == 535


# ---------------------------------------------------------------------------
# Test 2: P64 summary loads
# ---------------------------------------------------------------------------
def test_02_p64_summary_loads(p64_summary):
    """P64 summary must load and contain expected keys."""
    assert "p64_classification" in p64_summary
    assert "simulation_scope" in p64_summary


# ---------------------------------------------------------------------------
# Test 3: P65 summary loads
# ---------------------------------------------------------------------------
def test_03_p65_summary_loads(p65_summary):
    """P65 summary must load and contain p65_classification."""
    assert "p65_classification" in p65_summary


# ---------------------------------------------------------------------------
# Test 4: Odds CSV loads
# ---------------------------------------------------------------------------
def test_04_odds_csv_loads():
    """Odds CSV must exist and have ≥ 1 row."""
    assert ODDS_CSV_PATH.exists(), f"Odds CSV not found: {ODDS_CSV_PATH}"
    import csv
    with open(ODDS_CSV_PATH) as f:
        rows = list(csv.DictReader(f))
    assert len(rows) >= 1


# ---------------------------------------------------------------------------
# Test 5: Predictions JSONL loads
# ---------------------------------------------------------------------------
def test_05_predictions_jsonl_loads():
    """Predictions JSONL must exist and have ≥ 1 row."""
    assert PREDICTIONS_PATH.exists(), f"Predictions JSONL not found: {PREDICTIONS_PATH}"
    count = 0
    with open(PREDICTIONS_PATH) as f:
        for line in f:
            if line.strip():
                count += 1
    assert count >= 1


# ---------------------------------------------------------------------------
# Test 6: P64 classification valid
# ---------------------------------------------------------------------------
def test_06_p64_classification_valid(p66):
    """P66 summary must record P64 classification as P64_PAPER_SIMULATION_FIRST_RUN_READY."""
    cl = p66["artifacts_loaded"]["p64_classification"]
    assert cl == "P64_PAPER_SIMULATION_FIRST_RUN_READY", f"P64 classification: {cl}"


# ---------------------------------------------------------------------------
# Test 7: P65 classification valid
# ---------------------------------------------------------------------------
def test_07_p65_classification_valid(p66):
    """P66 summary must record P65 classification as P65_EDGE_STABLE_NEGATIVE."""
    cl = p66["artifacts_loaded"]["p65_classification"]
    assert cl == "P65_EDGE_STABLE_NEGATIVE", f"P65 classification: {cl}"


# ---------------------------------------------------------------------------
# Test 8: P64 row count = 535
# ---------------------------------------------------------------------------
def test_08_p64_row_count_535(p66):
    """P66 must confirm 535 P64 rows were loaded."""
    assert p66["artifacts_loaded"]["p64_rows"] == 535


# ---------------------------------------------------------------------------
# Test 9: Join hit rate computed
# ---------------------------------------------------------------------------
def test_09_join_hit_rate_computed(p66):
    """Join hit rate must be computed and in (0, 1]."""
    hit_rate = p66["join_audit"]["hit_rate"]
    assert hit_rate is not None
    assert 0.0 < hit_rate <= 1.0, f"hit_rate out of range: {hit_rate}"


# ---------------------------------------------------------------------------
# Test 10: Duplicate join keys detected or ruled out
# ---------------------------------------------------------------------------
def test_10_duplicate_join_keys_detected(p66):
    """Duplicate odds key count must be computed (integer ≥ 0)."""
    dup_count = p66["join_audit"]["duplicate_odds_key_count"]
    assert isinstance(dup_count, int)
    assert dup_count >= 0


# ---------------------------------------------------------------------------
# Test 11: Unmatched rows counted
# ---------------------------------------------------------------------------
def test_11_unmatched_rows_counted(p66):
    """Unmatched join count must be computed."""
    unmatched = p66["join_audit"]["unmatched"]
    assert isinstance(unmatched, int)
    assert unmatched >= 0
    # P64 emitted 535 rows → unmatched for Tier C should be 0
    assert unmatched == 0, (
        f"P64 join had {unmatched} unmatched predictions — no odds matched at all"
    )


# ---------------------------------------------------------------------------
# Test 12: Side mapping audit computed
# ---------------------------------------------------------------------------
def test_12_side_mapping_audit_computed(p66):
    """Side mapping audit must be computed with total_rows = 535."""
    sm = p66["side_mapping_audit"]
    assert sm["total_rows"] == 535
    assert "side_mapping_status" in sm


# ---------------------------------------------------------------------------
# Test 13: Home ML maps to Home side
# ---------------------------------------------------------------------------
def test_13_home_ml_maps_to_home_side(p64_rows):
    """When side='Home', decimal_odds must match Home ML conversion."""
    failures = []
    for row in p64_rows:
        if row.get("side") != "Home":
            continue
        home_ml = str(row.get("_home_ml_raw", "")).strip()
        stored_decimal = row.get("decimal_odds")
        expected = american_to_decimal(home_ml)
        if expected is not None and stored_decimal is not None:
            if abs(stored_decimal - expected) > 1e-4:
                failures.append({
                    "game_id": row.get("game_id"),
                    "home_ml": home_ml,
                    "stored": stored_decimal,
                    "expected": expected,
                })
    assert not failures, f"Home ML mismatch in {len(failures)} rows: {failures[:3]}"


# ---------------------------------------------------------------------------
# Test 14: Away ML maps to Away side
# ---------------------------------------------------------------------------
def test_14_away_ml_maps_to_away_side(p64_rows):
    """When side='Away', decimal_odds must match Away ML conversion."""
    failures = []
    for row in p64_rows:
        if row.get("side") != "Away":
            continue
        away_ml = str(row.get("_away_ml_raw", "")).strip()
        stored_decimal = row.get("decimal_odds")
        expected = american_to_decimal(away_ml)
        if expected is not None and stored_decimal is not None:
            if abs(stored_decimal - expected) > 1e-4:
                failures.append({
                    "game_id": row.get("game_id"),
                    "away_ml": away_ml,
                    "stored": stored_decimal,
                    "expected": expected,
                })
    assert not failures, f"Away ML mismatch in {len(failures)} rows: {failures[:3]}"


# ---------------------------------------------------------------------------
# Test 15: American odds conversion — positive odds
# ---------------------------------------------------------------------------
def test_15_american_odds_conversion_positive():
    """Positive American odds: decimal = 1 + ml/100."""
    cases = [(100, 2.0), (150, 2.5), (200, 3.0), (250, 3.5), (110, 2.1)]
    for ml, expected in cases:
        result = american_to_decimal(f"+{ml}")
        assert result is not None, f"+{ml} returned None"
        assert abs(result - expected) < 1e-6, f"+{ml}: got {result}, expected {expected}"


# ---------------------------------------------------------------------------
# Test 16: American odds conversion — negative odds
# ---------------------------------------------------------------------------
def test_16_american_odds_conversion_negative():
    """Negative American odds: decimal = 1 + 100/abs(ml)."""
    cases = [(-110, 1.909091), (-150, 1.666667), (-200, 1.5), (-260, 1.384615)]
    for ml, expected in cases:
        result = american_to_decimal(str(ml))
        assert result is not None, f"{ml} returned None"
        assert abs(result - expected) < 1e-4, f"{ml}: got {result}, expected {expected}"


# ---------------------------------------------------------------------------
# Test 17: Implied probability conversion
# ---------------------------------------------------------------------------
def test_17_implied_probability_conversion(p64_rows):
    """implied_probability must equal 1 / decimal_odds within tolerance."""
    failures = []
    for row in p64_rows:
        d = row.get("decimal_odds")
        ip = row.get("implied_probability")
        if d is None or ip is None:
            continue
        expected_ip = 1.0 / d
        if abs(ip - expected_ip) > 1e-4:
            failures.append({
                "game_id": row.get("game_id"),
                "decimal": d,
                "stored_implied": ip,
                "expected_implied": expected_ip,
            })
    assert not failures, f"Implied prob mismatch in {len(failures)} rows: {failures[:3]}"


# ---------------------------------------------------------------------------
# Test 18: Edge recalculation computed for all 535 rows
# ---------------------------------------------------------------------------
def test_18_edge_recalculation_computed(p66):
    """Edge recalculation must cover all 535 audited rows."""
    ea = p66["edge_recalculation_audit"]
    assert ea["audited_rows"] == 535
    assert "edge_recalculation_status" in ea


# ---------------------------------------------------------------------------
# Test 19: Sign mismatch count computed
# ---------------------------------------------------------------------------
def test_19_sign_mismatch_count_computed(p66):
    """Sign mismatch count must be ≥ 0."""
    sm = p66["edge_recalculation_audit"]["sign_mismatch_count"]
    assert isinstance(sm, int)
    assert sm >= 0


# ---------------------------------------------------------------------------
# Test 20: Edge delta tolerance — max abs delta < 0.001
# ---------------------------------------------------------------------------
def test_20_edge_delta_within_tolerance(p66):
    """Max absolute edge delta between original and recalculated must be < 0.001."""
    max_delta = p66["edge_recalculation_audit"]["max_absolute_delta"]
    assert max_delta < 0.001, (
        f"Edge recalculation max delta = {max_delta}, expected < 0.001"
    )


# ---------------------------------------------------------------------------
# Test 21: Final P66 classification is in allowed set
# ---------------------------------------------------------------------------
def test_21_final_classification_allowed(p66):
    """P66 classification must be one of the defined allowed values."""
    cl = p66["p66_classification"]
    assert cl in ALLOWED_P66_CLASSIFICATIONS, f"Invalid P66 classification: {cl}"


# ---------------------------------------------------------------------------
# Test 22: Governance flags preserved
# ---------------------------------------------------------------------------
def test_22_governance_flags_preserved(p66):
    """All P66 governance flags must be set correctly."""
    gov = p66["governance"]
    assert gov["paper_only"] is True
    assert gov["diagnostic_only"] is True
    assert gov["promotion_freeze"] is True
    assert gov["kelly_deploy_allowed"] is False
    assert gov["live_api_calls"] == 0
    assert gov["paid_api_called"] is False
    assert gov["runtime_recommendation_logic_changed"] is False
    assert gov["real_bet_allowed"] is False
    assert gov["production_ready"] is False


# ---------------------------------------------------------------------------
# Test 23: 2024 data gap remains unresolved
# ---------------------------------------------------------------------------
def test_23_2024_data_gap_unresolved(p66):
    """2024 data gap must remain documented as unresolved in P66."""
    gov = p66["governance"]
    assert gov.get("data_year_2024_gap_remains_unresolved") is True


# ---------------------------------------------------------------------------
# Test 24: Forbidden affirmative scan = 0 violations
# ---------------------------------------------------------------------------
def test_24_forbidden_scan_zero_violations(p66):
    """Forbidden affirmative scan must return 0 violations (CLEAN)."""
    scan = p66["forbidden_scan"]
    assert scan["violations"] == 0, (
        f"Forbidden scan violations: {scan['violations']}, details: {scan.get('details')}"
    )
    assert scan["result"] == "CLEAN", f"Forbidden scan result: {scan['result']}"


# ---------------------------------------------------------------------------
# Test 25: active_task.md contains P66 or P65 reference
# ---------------------------------------------------------------------------
def test_25_active_task_updated():
    """active_task.md must exist and contain P65 (prior phase)."""
    active_task_path = ROOT / "00-Plan" / "roadmap" / "active_task.md"
    assert active_task_path.exists(), "active_task.md not found"
    content = active_task_path.read_text()
    assert "P65" in content, "active_task.md does not mention P65"


# ---------------------------------------------------------------------------
# Test 26: Side mapping all pass (no inversions)
# ---------------------------------------------------------------------------
def test_26_no_side_inversions(p66):
    """Side mapping must show 0 inversions and all 535 rows passing."""
    sm = p66["side_mapping_audit"]
    assert sm["side_inversion_count"] == 0
    assert sm["pass_count"] == 535
    assert sm["fail_count"] == 0
    assert sm["side_mapping_status"] == "SIDE_MAPPING_PASS"


# ---------------------------------------------------------------------------
# Test 27: Odds conversion all pass (no mismatches)
# ---------------------------------------------------------------------------
def test_27_odds_conversion_all_pass(p66):
    """Odds conversion must show 0 mismatches and 0 invalid values."""
    oc = p66["odds_conversion_audit"]
    assert oc["mismatch_count"] == 0
    assert oc["invalid_count"] == 0
    assert oc["odds_conversion_status"] == "ODDS_CONVERSION_PASS"


# ---------------------------------------------------------------------------
# Test 28: Edge recalculation mean matches original mean
# ---------------------------------------------------------------------------
def test_28_edge_recalc_mean_matches_original(p66):
    """Recalculated mean edge must equal original within 1e-4."""
    ea = p66["edge_recalculation_audit"]
    orig = ea["mean_edge_original"]
    recalc = ea["mean_edge_recomputed"]
    assert orig is not None, "mean_edge_original is None"
    assert recalc is not None, "mean_edge_recomputed is None"
    assert abs(orig - recalc) < EDGE_TOLERANCE, (
        f"Mean edge: original={orig}, recalculated={recalc}, delta={abs(orig - recalc)}"
    )


# ---------------------------------------------------------------------------
# Test 29: Positive edge count matches between original and recalculated
# ---------------------------------------------------------------------------
def test_29_positive_edge_count_matches(p66):
    """Positive edge count must be identical between original and recalculated."""
    ea = p66["edge_recalculation_audit"]
    assert ea["original_positive_count"] == ea["recomputed_positive_count"], (
        f"Positive count mismatch: original={ea['original_positive_count']}, "
        f"recalculated={ea['recomputed_positive_count']}"
    )


# ---------------------------------------------------------------------------
# Test 30: P66 summary file exists on disk
# ---------------------------------------------------------------------------
def test_30_p66_summary_output_exists():
    """P66 summary JSON output file must exist on disk."""
    assert P66_SUMMARY_PATH.exists(), f"P66 summary not found at {P66_SUMMARY_PATH}"
    with open(P66_SUMMARY_PATH) as f:
        data = json.load(f)
    assert "p66_classification" in data


# ---------------------------------------------------------------------------
# Test 31: Platt calibration formula sign is correct (negative A*logit + B)
# ---------------------------------------------------------------------------
def test_31_platt_formula_correct():
    """
    Platt formula must use: 1 / (1 + exp(-A * logit(p) - B)).
    Verified from P64 source docstring: model_prob=0.640146 → calibrated≈0.6216.
    """
    result = platt_calibrate(0.640146, PLATT_A, PLATT_B)
    assert abs(result - 0.6216) < 0.0005, (
        f"Platt calibration mismatch: got {result:.6f}, expected ~0.6216. "
        "Check formula sign: must be 1/(1+exp(-A*logit-B))."
    )


# ---------------------------------------------------------------------------
# Test 32: model_prob_home + model_prob_away ≈ 1 for all rows
# ---------------------------------------------------------------------------
def test_32_model_prob_sum_approx_one(p64_rows):
    """model_prob_home + model_prob_away must sum to ≈ 1 for all rows."""
    failures = []
    for row in p64_rows:
        h = row.get("model_prob_home")
        a = row.get("model_prob_away")
        if h is None or a is None:
            continue
        if abs(h + a - 1.0) > 0.01:
            failures.append({
                "game_id": row.get("game_id"),
                "sum": h + a,
            })
    assert not failures, f"Prob sum != 1 in {len(failures)} rows"


# ---------------------------------------------------------------------------
# Test 33: Positive odds examples captured in audit
# ---------------------------------------------------------------------------
def test_33_positive_odds_examples_captured(p66):
    """P66 must have captured ≥ 1 positive American odds example for audit trail."""
    examples = p66["odds_conversion_audit"]["positive_odds_examples"]
    assert len(examples) >= 1, "No positive American odds examples captured"
    # Verify first example is internally consistent
    ex = examples[0]
    ml_val = ex["ml_val"]
    expected_decimal = 1.0 + ml_val / 100.0
    assert abs(ex["stored_decimal"] - expected_decimal) < 1e-4


# ---------------------------------------------------------------------------
# Test 34: Negative odds examples captured in audit
# ---------------------------------------------------------------------------
def test_34_negative_odds_examples_captured(p66):
    """P66 must have captured ≥ 1 negative American odds example for audit trail."""
    examples = p66["odds_conversion_audit"]["negative_odds_examples"]
    assert len(examples) >= 1, "No negative American odds examples captured"
    # Verify first example is internally consistent
    ex = examples[0]
    ml_val = ex["ml_val"]
    expected_decimal = 1.0 + 100.0 / abs(ml_val)
    assert abs(ex["stored_decimal"] - expected_decimal) < 1e-4


# ---------------------------------------------------------------------------
# Test 35: Diagnosis negative edge confirmed after mapping validation
# ---------------------------------------------------------------------------
def test_35_negative_edge_confirmed_after_mapping(p66):
    """When classification is INTEGRITY_CONFIRMED, negative edge flag must be True."""
    cl = p66["p66_classification"]
    diag = p66["diagnosis"]
    if cl == "P66_ODDS_MAPPING_INTEGRITY_CONFIRMED":
        assert diag["negative_edge_confirmed_after_mapping_validation"] is True


# ---------------------------------------------------------------------------
# Test 36: Odds CSV row count reasonable (≥ 500)
# ---------------------------------------------------------------------------
def test_36_odds_csv_row_count_reasonable(p66):
    """Odds CSV must have ≥ 500 rows to cover 2025 season."""
    assert p66["artifacts_loaded"]["odds_csv_rows"] >= 500, (
        f"Odds CSV has only {p66['artifacts_loaded']['odds_csv_rows']} rows"
    )
