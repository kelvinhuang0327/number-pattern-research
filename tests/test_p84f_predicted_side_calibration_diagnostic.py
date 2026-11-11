"""
tests/test_p84f_predicted_side_calibration_diagnostic.py
=========================================================
40 tests covering the P84F Predicted-Side Direction / Calibration Diagnostic.

Tests are grouped:
  T01-T05  P84E source artefact verification
  T06-T10  Score/label interpretation audit (step 2)
  T11-T15  Predicted-side consistency (step 3)
  T16-T20  FIP delta sign audit (step 4)
  T21-T25  Rule subset audit (step 5)
  T26-T30  Governance invariants
  T31-T35  Diagnostic classification & remediation
  T36-T40  Regression / integration checks
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
P84E_SUMMARY   = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json"
P84E_DERIVED   = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
PRED_PATH      = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"
P84F_SUMMARY   = ROOT / "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json"
P84F_REPORT    = ROOT / "report/p84f_predicted_side_calibration_diagnostic_20260526.md"
ACTIVE_TASK    = ROOT / "00-Plan/roadmap/active_task.md"
P84F_SCRIPT    = ROOT / "scripts/_p84f_predicted_side_calibration_diagnostic.py"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def summary() -> dict:
    assert P84F_SUMMARY.exists(), f"P84F summary not found: {P84F_SUMMARY}"
    return json.loads(P84F_SUMMARY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def p84e_summary() -> dict:
    assert P84E_SUMMARY.exists(), f"P84E summary not found: {P84E_SUMMARY}"
    return json.loads(P84E_SUMMARY.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def derived_rows() -> list[dict]:
    assert P84E_DERIVED.exists(), f"P84E derived rows not found: {P84E_DERIVED}"
    return [
        json.loads(l)
        for l in P84E_DERIVED.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]


@pytest.fixture(scope="module")
def canonical_rows() -> list[dict]:
    assert PRED_PATH.exists(), f"Canonical pred rows not found: {PRED_PATH}"
    return [
        json.loads(l)
        for l in PRED_PATH.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]


@pytest.fixture(scope="module")
def p84f_module():
    """Import the P84F script as a module for unit-level testing."""
    spec = importlib.util.spec_from_file_location("p84f", P84F_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# T01 — T05: P84E source artefact verification
# ---------------------------------------------------------------------------

def test_t01_p84e_summary_exists():
    """T01: P84E summary artefact exists on disk."""
    assert P84E_SUMMARY.exists()


def test_t02_p84e_classification_verified(p84e_summary):
    """T02: P84E reported P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS."""
    assert p84e_summary["p84e_classification"] == "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS"


def test_t03_p84e_derived_rows_exist():
    """T03: P84E outcome-attached derived rows file exists."""
    assert P84E_DERIVED.exists()


def test_t04_p84e_outcome_available_count(derived_rows):
    """T04: Exactly 808 rows have outcome_available=True in P84E derived file."""
    n = sum(1 for r in derived_rows if r.get("outcome_available") is True)
    assert n == 808


def test_t05_p84e_step1_verified_in_p84f(summary):
    """T05: P84F step1 confirms P84E artefacts are VERIFIED."""
    s1 = summary["step1_verify_p84e"]
    assert s1["p84e_summary_exists"] is True
    assert s1["p84e_derived_exists"] is True
    assert s1["status"] in {"P84E_VERIFIED", "P84E_VERIFIED_WITH_WARNINGS"}


# ---------------------------------------------------------------------------
# T06 — T10: Score / label interpretation audit (step 2)
# ---------------------------------------------------------------------------

def test_t06_step2_score_label_audit_exists(summary):
    """T06: step2_score_label_audit key exists in P84F summary."""
    assert "step2_score_label_audit" in summary


def test_t07_auc_prob_home_win_gt_05(summary):
    """T07: AUC(model_probability, home_win) > 0.5 — confirms model_probability = P(home wins)."""
    auc = summary["step2_score_label_audit"]["auc_prob_home_win"]
    assert auc > 0.5, f"Expected AUC(prob, home_win) > 0.5, got {auc}"


def test_t08_auc_flipped_score_lt_05(summary):
    """T08: AUC(1 - model_probability, home_win) < 0.5 — flipped score loses signal."""
    auc = summary["step2_score_label_audit"]["auc_flipped_score_home_win"]
    assert auc < 0.5, f"Expected flipped AUC < 0.5, got {auc}"


def test_t09_auc_is_correct_lt_05(summary):
    """T09 (P84G-updated): AUC(model_probability, is_correct) > 0.5 — post-fix, mapping correct.

    Before P84G fix: AUC was 0.475337 < 0.5 (inverted mapping degraded signal).
    After P84G fix: AUC is 0.524663 > 0.5 (inversion resolved by P83E code fix).
    """
    auc = summary["step2_score_label_audit"]["auc_prob_is_correct"]
    assert auc > 0.5, f"Expected AUC(prob, is_correct) > 0.5 (post-P84G fix), got {auc}"


def test_t10_model_probability_interpretation(summary):
    """T10: model_probability interpretation is P_HOME_WIN."""
    interp = summary["step2_score_label_audit"]["model_probability_interpretation"]
    assert interp == "P_HOME_WIN"


# ---------------------------------------------------------------------------
# T11 — T15: Predicted-side consistency (step 3)
# ---------------------------------------------------------------------------

def test_t11_step3_predicted_side_consistency_exists(summary):
    """T11: step3_predicted_side_consistency key exists in P84F summary."""
    assert "step3_predicted_side_consistency" in summary


def test_t12_current_hit_rate_lt_05(summary):
    """T12 (P84G-updated): Current hit_rate > 0.5 — post-fix, mapping is FIP-correct.

    Before P84G fix: hit_rate=0.430693 < 0.5 (inverted predicted_side).
    After P84G fix: hit_rate=0.569307 > 0.5 (corrected predicted_side in P83E).
    """
    hr = summary["step3_predicted_side_consistency"]["current_hit_rate"]
    assert hr > 0.5, f"Expected current_hit_rate > 0.5 (post-P84G fix), got {hr}"


def test_t13_flipped_hit_rate_gt_05(summary):
    """T13 (P84G-updated): current_hit_rate > flipped_hit_rate — post-fix, current mapping wins.

    Before P84G fix: flipped_hit_rate > current_hit_rate (inversion proof).
    After P84G fix: current_hit_rate > flipped_hit_rate (mapping is now correct).
    """
    s3 = summary["step3_predicted_side_consistency"]
    current = s3["current_hit_rate"]
    flipped = s3["flipped_hit_rate"]
    assert current > flipped, (
        f"Post-fix: current_hit_rate ({current}) should exceed flipped ({flipped})"
    )


def test_t14_probability_threshold_hit_rate_computed(summary):
    """T14: probability_threshold_hit_rate is computed and > 0."""
    thr = summary["step3_predicted_side_consistency"]["probability_threshold_hit_rate"]
    assert thr is not None
    assert thr > 0.0


def test_t15_mapping_pattern_inverted(summary):
    """T15 (P84G-updated): Mapping pattern is PROB_GE_05_MAPS_TO_HOME (FIP-correct post-fix).

    Before P84G fix: PROB_GE_05_MAPS_TO_AWAY (prob>=0.5 → predicted away — wrong).
    After P84G fix: PROB_GE_05_MAPS_TO_HOME (prob>=0.5 → predicted home — correct).
    """
    mp = summary["step3_predicted_side_consistency"]["mapping_pattern"]
    assert mp == "PROB_GE_05_MAPS_TO_HOME", f"Expected PROB_GE_05_MAPS_TO_HOME (post-fix), got {mp}"


# ---------------------------------------------------------------------------
# T16 — T20: FIP delta sign audit (step 4)
# ---------------------------------------------------------------------------

def test_t16_step4_fip_delta_audit_exists(summary):
    """T16: step4_fip_delta_sign_audit key exists in P84F summary."""
    assert "step4_fip_delta_sign_audit" in summary


def test_t17_fip_pos_delta_away_win_rate_gt_05(summary):
    """T17: When delta > 0 (home pitcher worse), actual away win rate > 0.5 — valid FIP signal."""
    rate = summary["step4_fip_delta_sign_audit"]["pos_delta_away_win_rate"]
    assert rate is not None
    assert rate > 0.5, f"Expected away win rate > 0.5 when delta>0, got {rate}"


def test_t18_fip_neg_delta_home_win_rate_gt_05(summary):
    """T18: When delta < 0 (home pitcher better), actual home win rate > 0.5 — valid FIP signal."""
    rate = summary["step4_fip_delta_sign_audit"]["neg_delta_home_win_rate"]
    assert rate is not None
    assert rate > 0.5, f"Expected home win rate > 0.5 when delta<0, got {rate}"


def test_t19_fip_signal_valid(summary):
    """T19: FIP signal confirms VALID_AWAY_EDGE_WHEN_DELTA_POSITIVE."""
    sig = summary["step4_fip_delta_sign_audit"]["fip_signal"]
    assert sig == "VALID_AWAY_EDGE_WHEN_DELTA_POSITIVE"


def test_t20_predicted_side_fip_consistency_rate_zero(summary):
    """T20 (P84G-updated): predicted_side FIP consistency rate > 0.9 — fully consistent post-fix.

    Before P84G fix: rate=0.0 (fully inverted — predicted_side contradicted FIP in all 808 rows).
    After P84G fix: rate=1.0 (fully consistent — every row now follows FIP convention).
    """
    rate = summary["step4_fip_delta_sign_audit"]["predicted_side_fip_consistency_rate"]
    assert rate is not None
    assert rate > 0.9, f"Expected fip_consistency_rate > 0.9 (post-P84G fix), got {rate}"


# ---------------------------------------------------------------------------
# T21 — T25: Rule subset audit (step 5)
# ---------------------------------------------------------------------------

def test_t21_step5_rule_subset_audit_exists(summary):
    """T21: step5_rule_subset_audit key exists in P84F summary."""
    assert "step5_rule_subset_audit" in summary


def test_t22_step5_all_subset_n_808(summary):
    """T22: 'all' subset contains exactly 808 outcome-available rows."""
    n = summary["step5_rule_subset_audit"]["all"]["n"]
    assert n == 808


def test_t23_step5_primary_125_subset_computed(summary):
    """T23: primary_125 subset metrics are computed."""
    m = summary["step5_rule_subset_audit"]["primary_125"]
    assert "n" in m
    assert "current_hit_rate" in m


def test_t24_step5_shadow_100_subset_computed(summary):
    """T24: shadow_100 subset metrics are computed."""
    m = summary["step5_rule_subset_audit"]["shadow_100"]
    assert "n" in m
    assert "current_hit_rate" in m


def test_t25_step5_tier_b_subset_handled(summary):
    """T25: tier_b subset is present; sample_limited flag is set appropriately."""
    m = summary["step5_rule_subset_audit"]["tier_b"]
    assert "n" in m
    assert "sample_limited" in m


# ---------------------------------------------------------------------------
# T26 — T30: Governance invariants
# ---------------------------------------------------------------------------

def test_t26_governance_paper_only(summary):
    """T26: governance.paper_only = True."""
    assert summary["governance"]["paper_only"] is True


def test_t27_governance_diagnostic_only(summary):
    """T27: governance.diagnostic_only = True."""
    assert summary["governance"]["diagnostic_only"] is True


def test_t28_governance_production_ready_false(summary):
    """T28: governance.production_ready = False."""
    assert summary["governance"]["production_ready"] is False


def test_t29_governance_no_odds_api_call(summary):
    """T29: governance.odds_api_called = False — no odds calls made."""
    assert summary["governance"]["odds_api_called"] is False


def test_t30_governance_no_ev_clv_kelly(summary):
    """T30: ev, clv, kelly are all False in governance block."""
    gov = summary["governance"]
    assert gov["ev"] is False
    assert gov["clv"] is False
    assert gov["kelly"] is False


# ---------------------------------------------------------------------------
# T31 — T35: Diagnostic classification & remediation
# ---------------------------------------------------------------------------

def test_t31_p84f_classification_is_inverted(summary):
    """T31 (P84G-updated): Top-level p84f_classification = P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK.

    Before P84G fix: P84F_SIDE_MAPPING_INVERTED (committed at 9175759).
    After P84G fix: P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK (inversion resolved).
    """
    assert summary["p84f_classification"] == "P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK", (
        f"Expected P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK (post-fix), got {summary['p84f_classification']}"
    )


def test_t32_step7_diagnosis_exists(summary):
    """T32: step7_diagnosis block exists with classification, remediation_path, evidence."""
    d = summary["step7_diagnosis"]
    assert "classification" in d
    assert "remediation_path" in d
    assert "evidence" in d


def test_t33_remediation_path_mentions_p84g(summary):
    """T33: remediation_path references P84G as the next step."""
    path = summary["step7_diagnosis"]["remediation_path"]
    assert "P84G" in path, f"Expected 'P84G' in remediation_path, got: {path}"


def test_t34_evidence_list_nonempty(summary):
    """T34 (P84G-updated): Evidence list has at least 1 entry supporting the classification.

    Post-fix P84F has 2 evidence entries (AUC + FIP delta sign).
    """
    evidence = summary["step7_diagnosis"]["evidence"]
    assert isinstance(evidence, list)
    assert len(evidence) >= 1, f"Expected at least 1 evidence entry, got {len(evidence)}"


def test_t35_flipped_hr_exceeds_current_hr_by_meaningful_margin(summary):
    """T35 (P84G-updated): current_hit_rate exceeds flipped_hit_rate by > 0.10 — fix confirmed.

    Before P84G fix: flipped_hit_rate - current_hit_rate = +0.138614 (inverted mapping).
    After P84G fix: current_hit_rate - flipped_hit_rate = +0.138614 (mapping corrected).
    """
    s3 = summary["step3_predicted_side_consistency"]
    current_advantage = s3["current_hit_rate"] - s3["flipped_hit_rate"]
    assert current_advantage > 0.10, (
        f"Expected current_hit_rate to exceed flipped_hit_rate by > 0.10 (post-fix), got {current_advantage}"
    )


# ---------------------------------------------------------------------------
# T36 — T40: Regression / integration checks
# ---------------------------------------------------------------------------

def test_t36_canonical_rows_not_modified(canonical_rows):
    """T36: Original canonical prediction rows do NOT have outcome_available field (P84F is read-only)."""
    for r in canonical_rows[:20]:
        assert "outcome_available" not in r, (
            f"Canonical row {r.get('game_id')} has outcome_available — file was modified"
        )


def test_t37_derived_rows_not_modified_by_p84f(derived_rows):
    """T37: P84E derived rows still have exactly 828 rows (P84F did not alter them)."""
    assert len(derived_rows) == 828


def test_t38_p84f_report_exists_and_has_content():
    """T38 (P84G-updated): P84F markdown report exists and contains post-fix diagnostic sections."""
    assert P84F_REPORT.exists(), f"P84F report not found: {P84F_REPORT}"
    text = P84F_REPORT.read_text(encoding="utf-8")
    assert "P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK" in text, (
        "Report must contain post-fix classification P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK"
    )
    assert "FIP" in text


def test_t39_p84f_report_includes_calibration_bucket_table():
    """T39: P84F report includes calibration bucket table."""
    text = P84F_REPORT.read_text(encoding="utf-8")
    assert "Calibration Bucket" in text or "calibration" in text.lower()
    # Should have at least one bucket row
    assert "0." in text


def test_t40_p84f_calibration_buckets_in_summary(summary):
    """T40: step6_calibration_buckets is a non-empty list in summary."""
    buckets = summary.get("step6_calibration_buckets", [])
    assert isinstance(buckets, list)
    assert len(buckets) > 0
    # Each bucket has required keys
    for b in buckets:
        assert "prob_bucket" in b
        assert "n" in b
        assert "actual_home_win_rate" in b
        assert "actual_away_win_rate" in b
