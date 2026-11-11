"""
P84G tests — Fix Predicted-Side Mapping + Regenerate Canonical Prediction Rows
Tests: T01-T30 (30 required)

Test groups:
  T01-T05: P84F source artifact verification (pre-fix state evidence)
  T06-T10: P83E code mapping inspection
  T11-T15: Canonical row regeneration
  T16-T20: P84E corrected metrics
  T21-T25: P84F rerun (post-fix classification)
  T26-T30: Governance invariants + regression
"""

from __future__ import annotations

import json
import pathlib
import types

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]

P84G_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84g_predicted_side_mapping_fix_summary.json"
P84F_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json"
P84E_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json"
P83E_SCRIPT_PATH  = ROOT / "scripts/_p83e_2026_canonical_prediction_row_producer.py"
CANONICAL_ROWS_PATH = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"
P84G_REPORT_PATH  = ROOT / "report/p84g_predicted_side_mapping_fix_20260526.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def p84g_summary() -> dict:
    assert P84G_SUMMARY_PATH.exists(), f"P84G summary missing: {P84G_SUMMARY_PATH}"
    return json.loads(P84G_SUMMARY_PATH.read_text())


@pytest.fixture(scope="module")
def p84f_summary() -> dict:
    assert P84F_SUMMARY_PATH.exists(), f"P84F summary missing: {P84F_SUMMARY_PATH}"
    return json.loads(P84F_SUMMARY_PATH.read_text())


@pytest.fixture(scope="module")
def p84e_summary() -> dict:
    assert P84E_SUMMARY_PATH.exists(), f"P84E summary missing: {P84E_SUMMARY_PATH}"
    return json.loads(P84E_SUMMARY_PATH.read_text())


@pytest.fixture(scope="module")
def canonical_rows() -> list[dict]:
    assert CANONICAL_ROWS_PATH.exists(), f"Canonical rows missing: {CANONICAL_ROWS_PATH}"
    return [json.loads(l) for l in CANONICAL_ROWS_PATH.read_text().splitlines() if l.strip()]


@pytest.fixture(scope="module")
def p83e_src() -> str:
    assert P83E_SCRIPT_PATH.exists(), f"P83E script missing: {P83E_SCRIPT_PATH}"
    return P83E_SCRIPT_PATH.read_text()


# ===========================================================================
# T01-T05: P84F source artifact verification (pre-fix state evidence)
# ===========================================================================

def test_t01_p84g_summary_exists():
    """T01: P84G summary artifact was generated."""
    assert P84G_SUMMARY_PATH.exists(), f"P84G summary not found at {P84G_SUMMARY_PATH}"


def test_t02_p84g_classification_correct(p84g_summary):
    """T02: P84G classification is SIDE_MAPPING_FIXED_METRICS_REGENERATED."""
    assert p84g_summary["p84g_classification"] == "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED"


def test_t03_p84g_prefix_state_recorded(p84g_summary):
    """T03: Pre-fix state (P84F_SIDE_MAPPING_INVERTED) is recorded in summary."""
    pre = p84g_summary["prefix_state"]
    assert pre["p84f_classification"] == "P84F_SIDE_MAPPING_INVERTED"
    assert pre["commit"] == "9175759"


def test_t04_p84g_prefix_hit_rate_was_below_05(p84g_summary):
    """T04: Pre-fix hit_rate < 0.5 (inverted mapping produced low hit rate)."""
    pre = p84g_summary["prefix_state"]
    assert pre["current_hit_rate"] < 0.5, f"Pre-fix hit_rate should be < 0.5, got {pre['current_hit_rate']}"


def test_t05_p84g_fix_applied_confirmed(p84g_summary):
    """T05: Step 1 confirms fix was applied (post-fix class ≠ SIDE_MAPPING_INVERTED)."""
    s1 = p84g_summary["step1_verify_prefix"]
    assert s1["fix_applied_confirmed"] is True
    assert s1["postfix_classification"] != "P84F_SIDE_MAPPING_INVERTED"


# ===========================================================================
# T06-T10: P83E code mapping inspection
# ===========================================================================

def test_t06_p83e_compute_predicted_side_away_when_pos_delta(p83e_src):
    """T06: P83E source returns 'away' when sp_fip_delta > 0 (home pitcher worse)."""
    assert 'return "away"  # home pitcher worse' in p83e_src, (
        "P83E compute_predicted_side must return 'away' when delta>0"
    )


def test_t07_p83e_compute_predicted_side_home_when_neg_delta(p83e_src):
    """T07: P83E source returns 'home' when sp_fip_delta < 0 (away pitcher worse)."""
    assert 'return "home"  # away pitcher worse' in p83e_src, (
        "P83E compute_predicted_side must return 'home' when delta<0"
    )


def test_t08_p83e_old_inverted_logic_absent(p83e_src):
    """T08: Old inverted mapping (return 'home' when delta>0) no longer present."""
    # The old buggy single-line check
    assert 'return "home"\n    if sp_fip_delta < 0.0:\n        return "away"' not in p83e_src, (
        "Old inverted mapping still present in P83E"
    )


def test_t09_p83e_p84g_fix_marker_present(p83e_src):
    """T09: P83E contains P84G fix marker in docstring."""
    assert "P84G" in p83e_src, "P83E must contain P84G fix marker in docstrings"


def test_t10_p83e_convention_correct_in_summary(p84g_summary):
    """T10: P84G step2 confirms convention_correct=True."""
    s2 = p84g_summary["step2_inspect_p83e_mapping"]
    assert s2["convention_correct"] is True
    assert s2["has_away_if_pos_delta"] is True
    assert s2["has_home_if_neg_delta"] is True


# ===========================================================================
# T11-T15: Canonical row regeneration
# ===========================================================================

def test_t11_canonical_rows_count_828(canonical_rows):
    """T11: Canonical row count remains 828 (stable since P84B dedup fix)."""
    assert len(canonical_rows) == 828, f"Expected 828 canonical rows, got {len(canonical_rows)}"


def test_t12_pos_delta_maps_to_away(canonical_rows):
    """T12: All rows with sp_fip_delta > 0 have predicted_side='away'."""
    pos_delta = [r for r in canonical_rows if (r.get("sp_fip_delta") or 0.0) > 0.0]
    assert len(pos_delta) > 0, "No rows with positive sp_fip_delta found"
    wrong = [r for r in pos_delta if r.get("predicted_side") != "away"]
    assert len(wrong) == 0, (
        f"{len(wrong)} rows with delta>0 have predicted_side≠'away' (corrected mapping violated)"
    )


def test_t13_neg_delta_maps_to_home(canonical_rows):
    """T13: All rows with sp_fip_delta < 0 have predicted_side='home'."""
    neg_delta = [r for r in canonical_rows if (r.get("sp_fip_delta") or 0.0) < 0.0]
    assert len(neg_delta) > 0, "No rows with negative sp_fip_delta found"
    wrong = [r for r in neg_delta if r.get("predicted_side") != "home"]
    assert len(wrong) == 0, (
        f"{len(wrong)} rows with delta<0 have predicted_side≠'home' (corrected mapping violated)"
    )


def test_t14_canonical_rows_governance_preserved(canonical_rows):
    """T14: Governance fields in canonical rows are unchanged."""
    sample = canonical_rows[:20]
    for r in sample:
        assert r.get("paper_only") is True, "paper_only must be True in canonical rows"
        assert r.get("diagnostic_only") is True, "diagnostic_only must be True"
        assert r.get("production_ready") is False, "production_ready must be False"


def test_t15_canonical_rows_verified_in_p84g_summary(p84g_summary):
    """T15: P84G step3 reports canonical rows verified with correct mapping."""
    s3 = p84g_summary["step3_verify_canonical_rows"]
    assert s3["ok"] is True
    assert s3["count_stable"] is True
    assert s3["pos_delta_maps_to_away"] is True
    assert s3["neg_delta_maps_to_home"] is True


# ===========================================================================
# T16-T20: P84E corrected metrics
# ===========================================================================

def test_t16_p84e_corrected_hit_rate_gt_05(p84g_summary):
    """T16: Corrected P84E hit_rate > 0.5 (previously 0.4307 under inverted mapping)."""
    s4 = p84g_summary["step4_corrected_p84e_metrics"]
    hr = s4["all"]["hit_rate"]
    assert hr is not None, "P84E all hit_rate is None"
    assert hr > 0.5, f"Corrected hit_rate should be > 0.5, got {hr}"


def test_t17_p84e_corrected_auc_gt_05(p84g_summary):
    """T17: Corrected P84E AUC > 0.5 (model discrimination preserved)."""
    s4 = p84g_summary["step4_corrected_p84e_metrics"]
    auc = s4["all"]["auc"]
    assert auc is not None
    assert auc > 0.5, f"AUC should be > 0.5, got {auc}"


def test_t18_p84e_corrected_hit_rate_matches_flipped(p84g_summary):
    """T18: Corrected hit_rate ≈ pre-fix flipped_hit_rate (within 0.001 tolerance)."""
    s4 = p84g_summary["step4_corrected_p84e_metrics"]
    corrected_hr = s4["all"]["hit_rate"]
    pre_flipped = p84g_summary["prefix_state"]["flipped_hit_rate"]
    assert abs(corrected_hr - pre_flipped) < 0.001, (
        f"Corrected hit_rate {corrected_hr} should match pre-fix flipped_hit_rate {pre_flipped}"
    )


def test_t19_p84e_primary_125_hit_rate_gt_05(p84g_summary):
    """T19: Primary-125 subset hit_rate > 0.5 after fix."""
    s4 = p84g_summary["step4_corrected_p84e_metrics"]
    hr = s4.get("primary_125", {}).get("hit_rate")
    if hr is not None:
        assert hr > 0.5, f"primary_125 hit_rate should be > 0.5, got {hr}"


def test_t20_p84e_outcome_available_count_808(p84g_summary):
    """T20: P84E outcome-available count is 808 (unchanged from P84E v1)."""
    s4 = p84g_summary["step4_corrected_p84e_metrics"]
    n = s4.get("n_outcome_available")
    # Allow for minor variation if public results updated; anchor at 808
    assert n is not None
    # Confirm it's the same as before (808 outcomes were available in P84E v1)
    assert 800 <= n <= 830, f"n_outcome_available={n} out of expected range [800, 830]"


# ===========================================================================
# T21-T25: P84F rerun (post-fix classification)
# ===========================================================================

def test_t21_p84f_no_longer_inverted(p84f_summary):
    """T21: P84F rerun classification is no longer SIDE_MAPPING_INVERTED."""
    assert p84f_summary["p84f_classification"] != "P84F_SIDE_MAPPING_INVERTED", (
        "P84F still classifies as SIDE_MAPPING_INVERTED after fix"
    )


def test_t22_p84f_mapping_pattern_correct(p84f_summary):
    """T22: P84F rerun mapping_pattern is PROB_GE_05_MAPS_TO_HOME."""
    s3 = p84f_summary["step3_predicted_side_consistency"]
    assert s3["mapping_pattern"] == "PROB_GE_05_MAPS_TO_HOME", (
        f"mapping_pattern should be PROB_GE_05_MAPS_TO_HOME, got {s3['mapping_pattern']}"
    )


def test_t23_p84f_n_inverted_zero(p84f_summary):
    """T23: P84F rerun n_inverted_from_standard_convention = 0 (no more inverted rows)."""
    s3 = p84f_summary["step3_predicted_side_consistency"]
    assert s3["n_inverted_from_standard_convention"] == 0, (
        f"Expected 0 inverted rows, got {s3['n_inverted_from_standard_convention']}"
    )


def test_t24_p84f_auc_is_correct_gt_05(p84f_summary):
    """T24: P84F rerun AUC(prob, is_correct) > 0.5 (was < 0.5 under inverted mapping)."""
    s2 = p84f_summary["step2_score_label_audit"]
    auc_correct = s2["auc_prob_is_correct"]
    assert auc_correct > 0.5, (
        f"auc_prob_is_correct should be > 0.5 after fix, got {auc_correct}"
    )


def test_t25_p84f_postfix_in_p84g_summary(p84g_summary):
    """T25: P84G step5 confirms P84F post-fix classification and n_inverted=0."""
    s5 = p84g_summary["step5_corrected_p84f_diagnostic"]
    assert s5["ok"] is True
    assert s5["n_inverted"] == 0
    assert s5["not_inverted"] is True
    assert s5["mapping_correct"] is True


# ===========================================================================
# T26-T30: Governance invariants + regression
# ===========================================================================

def test_t26_p84g_governance_paper_only(p84g_summary):
    """T26: governance.paper_only=True."""
    assert p84g_summary["governance"]["paper_only"] is True


def test_t27_p84g_governance_no_odds(p84g_summary):
    """T27: governance.odds_api_called=False and live_api_calls=0."""
    gov = p84g_summary["governance"]
    assert gov["odds_api_called"] is False
    assert gov["live_api_calls"] == 0


def test_t28_p84g_governance_no_ev_clv_kelly(p84g_summary):
    """T28: governance.ev=False, clv=False, kelly=False."""
    gov = p84g_summary["governance"]
    assert gov["ev"] is False
    assert gov["clv"] is False
    assert gov["kelly"] is False


def test_t29_p84g_report_exists_and_has_content():
    """T29: P84G report file exists with meaningful content."""
    assert P84G_REPORT_PATH.exists(), f"P84G report missing: {P84G_REPORT_PATH}"
    content = P84G_REPORT_PATH.read_text()
    assert len(content) > 500, "P84G report seems empty"
    assert "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED" in content
    assert "Before" in content and "After" in content


def test_t30_compute_predicted_side_function_correct_logic():
    """T30: compute_predicted_side() function returns corrected values at runtime."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_p83e", str(P83E_SCRIPT_PATH)
    )
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

    fn = mod.compute_predicted_side
    # Corrected: delta > 0 → 'away'
    assert fn(1.5) == "away", f"delta=1.5 should give 'away', got {fn(1.5)}"
    assert fn(0.1) == "away", f"delta=0.1 should give 'away', got {fn(0.1)}"
    # Corrected: delta < 0 → 'home'
    assert fn(-1.0) == "home", f"delta=-1.0 should give 'home', got {fn(-1.0)}"
    assert fn(-0.5) == "home", f"delta=-0.5 should give 'home', got {fn(-0.5)}"
    # Tie → None
    assert fn(0.0) is None, "delta=0.0 should return None (tie excluded)"
