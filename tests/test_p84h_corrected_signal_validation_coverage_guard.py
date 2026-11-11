"""
tests/test_p84h_corrected_signal_validation_coverage_guard.py
=============================================================
Tests for P84H — Corrected 2026 Prediction-Only Signal Validation + Coverage Guard.

Validates:
  - Artifact consistency check (Step 1)
  - Recomputed metrics vs P84E tolerance check (Step 2)
  - Split metrics: monthly, chronological thirds, side, rule subset (Step 3)
  - Calibration analysis (Step 4)
  - Coverage classification (Step 5)
  - Subset binomial test (Step 6)
  - Final classification — one of five (Step 7)
  - Governance flags — all correct (Step G)
  - Report and summary file existence

Classification: P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED
Predecessor: P84G@021a8a8
"""
from __future__ import annotations

import json
import pathlib

import pytest

ROOT    = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
REPORT  = ROOT / "report"
SCRIPT  = ROOT / "scripts" / "_p84h_corrected_signal_validation_coverage_guard.py"
P84H_SUMMARY_PATH = DERIVED / "p84h_corrected_signal_validation_coverage_guard_summary.json"
P84H_REPORT_PATH  = REPORT  / "p84h_corrected_signal_validation_coverage_guard_20260527.md"

ALLOWED_CLASSIFICATIONS = [
    "P84H_CORRECTED_SIGNAL_VALIDATED_DIAGNOSTIC_ONLY",
    "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED",
    "P84H_CALIBRATION_WEAK_REQUIRES_REVIEW",
    "P84H_COVERAGE_TOO_LOW_FOR_SIGNAL_CLAIM",
    "P84H_FAILED_VALIDATION",
]


@pytest.fixture(scope="module")
def summary() -> dict:
    assert P84H_SUMMARY_PATH.exists(), f"P84H summary not found: {P84H_SUMMARY_PATH}"
    return json.loads(P84H_SUMMARY_PATH.read_text(encoding="utf-8"))


# ──────────────────────────────────────────────────────────────────────────────
# INFRASTRUCTURE CHECKS
# ──────────────────────────────────────────────────────────────────────────────

class TestInfrastructure:
    def test_script_exists(self):
        """P84H script file must exist."""
        assert SCRIPT.exists(), f"Script not found: {SCRIPT}"

    def test_summary_exists(self):
        """P84H summary JSON must exist."""
        assert P84H_SUMMARY_PATH.exists(), f"Summary not found: {P84H_SUMMARY_PATH}"

    def test_report_exists(self):
        """P84H markdown report must exist."""
        assert P84H_REPORT_PATH.exists(), f"Report not found: {P84H_REPORT_PATH}"

    def test_report_has_content(self):
        """Report must reference diagnostic_only and the classification."""
        text = P84H_REPORT_PATH.read_text(encoding="utf-8")
        assert "diagnostic_only=true" in text.lower() or "diagnostic_only" in text
        assert "production_ready=false" in text.lower() or "production_ready" in text
        assert "P84H" in text

    def test_summary_phase_correct(self, summary):
        """Summary must declare phase=P84H."""
        assert summary["phase"] == "P84H"

    def test_summary_date(self, summary):
        """Summary must have date field."""
        assert summary.get("date") == "2026-05-27"

    def test_allowed_classifications_present(self, summary):
        """Summary must list all five allowed classifications."""
        assert len(summary["allowed_classifications"]) == 5
        for clf in ALLOWED_CLASSIFICATIONS:
            assert clf in summary["allowed_classifications"]


# ──────────────────────────────────────────────────────────────────────────────
# STEP 1 — ARTIFACT CONSISTENCY
# ──────────────────────────────────────────────────────────────────────────────

class TestStep1ArtifactConsistency:
    def test_step1_status_passed(self, summary):
        """Step 1 artifact consistency check must PASS."""
        s1 = summary["step1_artifact_consistency"]
        assert s1["status"] == "PASSED", f"Expected PASSED, got: {s1['status']}"

    def test_step1_p83e_classification(self, summary):
        """P83E classification must be P83E_CANONICAL_ROWS_READY."""
        clfs = summary["step1_artifact_consistency"]["artifact_classifications"]
        assert clfs["p83e_classification"] == "P83E_CANONICAL_ROWS_READY"

    def test_step1_p84e_classification(self, summary):
        """P84E classification must be P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS."""
        clfs = summary["step1_artifact_consistency"]["artifact_classifications"]
        assert clfs["p84e_classification"] == "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS"

    def test_step1_p84f_classification(self, summary):
        """P84F post-fix classification must be P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK."""
        clfs = summary["step1_artifact_consistency"]["artifact_classifications"]
        assert clfs["p84f_classification"] == "P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK"

    def test_step1_p84g_classification(self, summary):
        """P84G classification must be P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED."""
        clfs = summary["step1_artifact_consistency"]["artifact_classifications"]
        assert clfs["p84g_classification"] == "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED"

    def test_step1_no_mismatches(self, summary):
        """No classification mismatches — all predecessor artifacts are consistent."""
        mismatches = summary["step1_artifact_consistency"]["classification_mismatches"]
        assert mismatches == {}, f"Unexpected mismatches: {mismatches}"

    def test_step1_canonical_row_count(self, summary):
        """Canonical row count must be 828 (from P83E output)."""
        assert summary["step1_artifact_consistency"]["canonical_row_count"] == 828

    def test_step1_outcome_available_count(self, summary):
        """Outcome-available row count must be 808 (from P84E output)."""
        assert summary["step1_artifact_consistency"]["outcome_available_count"] == 808

    def test_step1_row_count_ok(self, summary):
        """Both row counts must pass validation."""
        assert summary["step1_artifact_consistency"]["row_count_ok"] is True


# ──────────────────────────────────────────────────────────────────────────────
# STEP 2 — RECOMPUTED METRICS TOLERANCE CHECK
# ──────────────────────────────────────────────────────────────────────────────

class TestStep2RecomputedMetrics:
    def test_step2_status_passed(self, summary):
        """Step 2 tolerance check must PASS."""
        assert summary["step2_recomputed_metrics"]["status"] == "PASSED"

    def test_step2_tolerance_ok(self, summary):
        """All deltas between recomputed and P84E reference must be within tolerance."""
        assert summary["step2_recomputed_metrics"]["tolerance_ok"] is True

    def test_step2_recomputed_n(self, summary):
        """Recomputed row count must be 808 outcome-available rows."""
        assert summary["step2_recomputed_metrics"]["recomputed"]["n"] == 808

    def test_step2_recomputed_n_correct(self, summary):
        """Recomputed n_correct must be 460."""
        assert summary["step2_recomputed_metrics"]["recomputed"]["n_correct"] == 460

    def test_step2_recomputed_hit_rate_above_baseline(self, summary):
        """Recomputed hit_rate must be > 0.55 (post-P84G-fix, clear positive signal)."""
        hr = summary["step2_recomputed_metrics"]["recomputed"]["hit_rate"]
        assert hr > 0.55, f"Expected hit_rate > 0.55, got {hr}"

    def test_step2_recomputed_hit_rate_exact(self, summary):
        """Recomputed hit_rate must match P84E reference within 1e-4."""
        rc  = summary["step2_recomputed_metrics"]["recomputed"]["hit_rate"]
        ref = summary["step2_recomputed_metrics"]["p84e_reference"]["hit_rate"]
        assert abs(rc - ref) < 1e-4, f"hit_rate delta {abs(rc - ref)} exceeds tolerance"

    def test_step2_recomputed_auc_above_random(self, summary):
        """Recomputed AUC must be > 0.56 (discriminative signal present)."""
        auc = summary["step2_recomputed_metrics"]["recomputed"]["auc"]
        assert auc > 0.56, f"Expected AUC > 0.56, got {auc}"

    def test_step2_recomputed_auc_exact(self, summary):
        """Recomputed AUC must match P84E reference within 1e-4."""
        rc  = summary["step2_recomputed_metrics"]["recomputed"]["auc"]
        ref = summary["step2_recomputed_metrics"]["p84e_reference"]["auc"]
        assert abs(rc - ref) < 1e-4

    def test_step2_recomputed_brier_exact(self, summary):
        """Recomputed Brier score must match P84E reference within 1e-4."""
        rc  = summary["step2_recomputed_metrics"]["recomputed"]["brier"]
        ref = summary["step2_recomputed_metrics"]["p84e_reference"]["brier"]
        assert abs(rc - ref) < 1e-4

    def test_step2_recomputed_ece_exact(self, summary):
        """Recomputed ECE must match P84E reference within 1e-4."""
        rc  = summary["step2_recomputed_metrics"]["recomputed"]["ece"]
        ref = summary["step2_recomputed_metrics"]["p84e_reference"]["ece"]
        assert abs(rc - ref) < 1e-4

    def test_step2_all_deltas_zero(self, summary):
        """All metric deltas must be exactly 0.0 (perfect artifact consistency)."""
        for k, v in summary["step2_recomputed_metrics"]["deltas"].items():
            assert v == 0.0, f"Delta for {k} is {v}, expected 0.0"


# ──────────────────────────────────────────────────────────────────────────────
# STEP 3 — SPLIT METRICS
# ──────────────────────────────────────────────────────────────────────────────

class TestStep3MonthlySplt:
    def test_step3_monthly_keys_present(self, summary):
        """Monthly split must cover 2026-03, 2026-04, 2026-05."""
        monthly = summary["step3_split_metrics"]["monthly"]
        for month in ("2026-03", "2026-04", "2026-05"):
            assert month in monthly, f"Missing month {month}"

    def test_step3_monthly_march_n(self, summary):
        """March 2026: n=73 outcome rows."""
        assert summary["step3_split_metrics"]["monthly"]["2026-03"]["n"] == 73

    def test_step3_monthly_march_hit_rate_above_05(self, summary):
        """March hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["monthly"]["2026-03"]["hit_rate"]
        assert hr > 0.50, f"March hit_rate {hr} <= 0.50"

    def test_step3_monthly_march_auc_present(self, summary):
        """March AUC must be computed and > 0.5."""
        auc = summary["step3_split_metrics"]["monthly"]["2026-03"]["auc"]
        assert auc is not None and auc > 0.5

    def test_step3_monthly_april_n(self, summary):
        """April 2026: n=389 outcome rows."""
        assert summary["step3_split_metrics"]["monthly"]["2026-04"]["n"] == 389

    def test_step3_monthly_april_hit_rate_above_05(self, summary):
        """April hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["monthly"]["2026-04"]["hit_rate"]
        assert hr > 0.50, f"April hit_rate {hr} <= 0.50"

    def test_step3_monthly_may_n(self, summary):
        """May 2026: n=346 outcome rows."""
        assert summary["step3_split_metrics"]["monthly"]["2026-05"]["n"] == 346

    def test_step3_monthly_may_hit_rate_above_05(self, summary):
        """May hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["monthly"]["2026-05"]["hit_rate"]
        assert hr > 0.50, f"May hit_rate {hr} <= 0.50"

    def test_step3_monthly_total_n_sums_correctly(self, summary):
        """Sum of monthly n must equal total outcome rows (808)."""
        monthly = summary["step3_split_metrics"]["monthly"]
        total = sum(v["n"] for v in monthly.values())
        assert total == 808, f"Monthly sum {total} != 808"


class TestStep3ChronologicalThirds:
    def test_step3_thirds_keys_present(self, summary):
        """Chronological thirds must have first/second/third_third."""
        thirds = summary["step3_split_metrics"]["chronological_thirds"]
        for k in ("first_third", "second_third", "third_third"):
            assert k in thirds

    def test_step3_thirds_n_sizes_reasonable(self, summary):
        """Each third must have n > 250 (roughly 808/3 ≈ 269)."""
        thirds = summary["step3_split_metrics"]["chronological_thirds"]
        for name, v in thirds.items():
            assert v["n"] >= 250, f"{name} has n={v['n']} < 250"

    def test_step3_thirds_total_n(self, summary):
        """Sum of thirds n must equal total outcome rows (808)."""
        thirds = summary["step3_split_metrics"]["chronological_thirds"]
        total = sum(v["n"] for v in thirds.values())
        assert total == 808, f"Thirds sum {total} != 808"

    def test_step3_first_third_hit_rate_above_05(self, summary):
        """First third hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["chronological_thirds"]["first_third"]["hit_rate"]
        assert hr > 0.50, f"first_third hit_rate {hr} <= 0.50"

    def test_step3_second_third_hit_rate_above_05(self, summary):
        """Second third hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["chronological_thirds"]["second_third"]["hit_rate"]
        assert hr > 0.50, f"second_third hit_rate {hr} <= 0.50"

    def test_step3_third_third_hit_rate_above_05(self, summary):
        """Third third hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["chronological_thirds"]["third_third"]["hit_rate"]
        assert hr > 0.50, f"third_third hit_rate {hr} <= 0.50"

    def test_step3_thirds_date_fields_present(self, summary):
        """Thirds must have date_start and date_end."""
        thirds = summary["step3_split_metrics"]["chronological_thirds"]
        for name, v in thirds.items():
            assert "date_start" in v, f"{name} missing date_start"
            assert "date_end"   in v, f"{name} missing date_end"

    def test_step3_thirds_chronological_order(self, summary):
        """Thirds must be in chronological order (first end <= second start)."""
        thirds = summary["step3_split_metrics"]["chronological_thirds"]
        first_end  = thirds["first_third"]["date_end"]
        second_start = thirds["second_third"]["date_start"]
        third_start  = thirds["third_third"]["date_start"]
        assert first_end <= second_start
        assert second_start <= third_start


class TestStep3SideSplit:
    def test_step3_side_keys_present(self, summary):
        """Side split must contain 'home' and 'away'."""
        side = summary["step3_split_metrics"]["side"]
        assert "home" in side and "away" in side

    def test_step3_side_home_n(self, summary):
        """Predicted-home rows: n=412."""
        assert summary["step3_split_metrics"]["side"]["home"]["n"] == 412

    def test_step3_side_away_n(self, summary):
        """Predicted-away rows: n=396."""
        assert summary["step3_split_metrics"]["side"]["away"]["n"] == 396

    def test_step3_side_total_n(self, summary):
        """Sum of side n must equal 808."""
        side = summary["step3_split_metrics"]["side"]
        total = side["home"]["n"] + side["away"]["n"]
        assert total == 808

    def test_step3_side_home_hit_rate_above_05(self, summary):
        """Predicted-home hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["side"]["home"]["hit_rate"]
        assert hr > 0.50, f"home hit_rate {hr} <= 0.50"

    def test_step3_side_away_hit_rate_above_05(self, summary):
        """Predicted-away hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["side"]["away"]["hit_rate"]
        assert hr > 0.50, f"away hit_rate {hr} <= 0.50"

    def test_step3_side_auc_above_05(self, summary):
        """Both side AUCs must be > 0.50."""
        for s in ("home", "away"):
            auc = summary["step3_split_metrics"]["side"][s]["auc"]
            assert auc is not None and auc > 0.50, f"{s} AUC={auc} <= 0.50"


class TestStep3RuleSubset:
    def test_step3_rule_subset_keys_present(self, summary):
        """Rule subset split must contain primary_125, shadow_100, tier_b, tier_a."""
        rs = summary["step3_split_metrics"]["rule_subset"]
        for name in ("primary_125", "shadow_100", "tier_b", "tier_a"):
            assert name in rs, f"Missing subset {name}"

    def test_step3_primary_125_n(self, summary):
        """primary_125 subset: n=491 outcome rows."""
        assert summary["step3_split_metrics"]["rule_subset"]["primary_125"]["n"] == 491

    def test_step3_primary_125_hit_rate_above_055(self, summary):
        """primary_125 hit_rate must be > 0.55 (stronger subset)."""
        hr = summary["step3_split_metrics"]["rule_subset"]["primary_125"]["hit_rate"]
        assert hr > 0.55, f"primary_125 hit_rate {hr} <= 0.55"

    def test_step3_primary_125_hit_rate_exceeds_all(self, summary):
        """primary_125 hit_rate must exceed all-row hit_rate."""
        p125_hr = summary["step3_split_metrics"]["rule_subset"]["primary_125"]["hit_rate"]
        all_hr  = summary["step2_recomputed_metrics"]["recomputed"]["hit_rate"]
        assert p125_hr > all_hr, f"primary_125 {p125_hr} should exceed all {all_hr}"

    def test_step3_shadow_100_n(self, summary):
        """shadow_100 subset: n=536 outcome rows."""
        assert summary["step3_split_metrics"]["rule_subset"]["shadow_100"]["n"] == 536

    def test_step3_shadow_100_hit_rate_above_055(self, summary):
        """shadow_100 hit_rate must be > 0.55."""
        hr = summary["step3_split_metrics"]["rule_subset"]["shadow_100"]["hit_rate"]
        assert hr > 0.55, f"shadow_100 hit_rate {hr} <= 0.55"

    def test_step3_tier_b_n(self, summary):
        """tier_b subset: n=94 outcome rows."""
        assert summary["step3_split_metrics"]["rule_subset"]["tier_b"]["n"] == 94

    def test_step3_tier_b_hit_rate_above_05(self, summary):
        """tier_b hit_rate must be > 0.50."""
        hr = summary["step3_split_metrics"]["rule_subset"]["tier_b"]["hit_rate"]
        assert hr > 0.50, f"tier_b hit_rate {hr} <= 0.50"

    def test_step3_primary_125_auc_above_06(self, summary):
        """primary_125 AUC must be > 0.60 (meaningful discrimination)."""
        auc = summary["step3_split_metrics"]["rule_subset"]["primary_125"]["auc"]
        assert auc is not None and auc > 0.60, f"primary_125 AUC={auc} <= 0.60"


# ──────────────────────────────────────────────────────────────────────────────
# STEP 4 — CALIBRATION
# ──────────────────────────────────────────────────────────────────────────────

class TestStep4Calibration:
    def test_step4_ece_matches_recomputed(self, summary):
        """Step 4 ECE must match step 2 recomputed ECE within 1e-4."""
        s4_ece = summary["step4_calibration"]["ece"]
        s2_ece = summary["step2_recomputed_metrics"]["recomputed"]["ece"]
        assert abs(s4_ece - s2_ece) < 1e-4

    def test_step4_calibration_level_weak(self, summary):
        """Calibration level must be WEAK (ECE > 0.05)."""
        level = summary["step4_calibration"]["calibration_level"]
        assert level == "WEAK", f"Expected WEAK, got {level}"

    def test_step4_reliability_curve_has_populated_bins(self, summary):
        """Reliability curve must have at least 3 populated (non-zero-n) bins."""
        populated = [b for b in summary["step4_calibration"]["reliability_curve"] if b["n"] > 0]
        assert len(populated) >= 3, f"Only {len(populated)} populated bins"

    def test_step4_reliability_curve_n_bins(self, summary):
        """Reliability curve must use 10 bins."""
        assert summary["step4_calibration"]["n_bins"] == 10
        assert len(summary["step4_calibration"]["reliability_curve"]) == 10

    def test_step4_platt_refit_forbidden(self, summary):
        """Calibration notes must explicitly mark Platt/isotonic refit as FORBIDDEN."""
        note = summary["step4_calibration"]["calibration_notes"]["platt_isotonic_refit"]
        assert "FORBIDDEN" in note.upper()

    def test_step4_side_balance_low(self, summary):
        """Side imbalance ratio must be < 0.10 (roughly balanced predictions)."""
        ratio = summary["step4_calibration"]["side_balance"]["imbalance_ratio"]
        assert ratio < 0.10, f"Side imbalance {ratio} >= 0.10"


# ──────────────────────────────────────────────────────────────────────────────
# STEP 5 — COVERAGE CLASSIFICATION
# ──────────────────────────────────────────────────────────────────────────────

class TestStep5Coverage:
    def test_step5_schedule_rows(self, summary):
        """Schedule rows must be 2430 (full 2026 MLB season)."""
        assert summary["step5_coverage"]["schedule_rows"] == 2430

    def test_step5_canonical_rows(self, summary):
        """Canonical rows must be 828."""
        assert summary["step5_coverage"]["canonical_rows"] == 828

    def test_step5_outcome_available_rows(self, summary):
        """Outcome-available rows must be 808."""
        assert summary["step5_coverage"]["outcome_available_rows"] == 808

    def test_step5_canonical_coverage_ratio_in_range(self, summary):
        """Canonical coverage ratio must be in (0.20, 0.50) — COVERAGE_LIMITED."""
        ratio = summary["step5_coverage"]["canonical_coverage_ratio"]
        assert 0.20 <= ratio < 0.50, f"Coverage ratio {ratio} out of COVERAGE_LIMITED range"

    def test_step5_outcome_coverage_ratio_high(self, summary):
        """Outcome coverage ratio (outcome/canonical) must be > 0.95."""
        ratio = summary["step5_coverage"]["outcome_coverage_ratio"]
        assert ratio > 0.95, f"Outcome coverage ratio {ratio} < 0.95"

    def test_step5_coverage_classification_limited(self, summary):
        """Coverage classification must be COVERAGE_LIMITED."""
        clf = summary["step5_coverage"]["coverage_classification"]
        assert clf == "COVERAGE_LIMITED", f"Expected COVERAGE_LIMITED, got {clf}"

    def test_step5_full_season_claim_false(self, summary):
        """Full-season claim must be explicitly False."""
        assert summary["step5_coverage"]["full_season_claim_valid"] is False

    def test_step5_production_claim_false(self, summary):
        """Production claim must be explicitly False."""
        assert summary["step5_coverage"]["production_claim_valid"] is False

    def test_step5_date_range_partial(self, summary):
        """Date range covered must indicate March-May (partial coverage only)."""
        date_range = summary["step5_coverage"]["date_range_covered"]
        assert "2026-03" in date_range or "March" in date_range


# ──────────────────────────────────────────────────────────────────────────────
# STEP 6 — BINOMIAL TEST
# ──────────────────────────────────────────────────────────────────────────────

class TestStep6BinomialTest:
    def test_step6_method_documented(self, summary):
        """Binomial test method must be documented."""
        method = summary["step6_subset_comparison"]["method"]
        assert "binomial" in method.lower()

    def test_step6_all_subset_significant(self, summary):
        """All-row hit_rate must be significant at alpha=0.05 (H0: 0.50)."""
        sub = summary["step6_subset_comparison"]["subsets"]["all"]
        assert sub["significant_at_05"] is True
        assert sub["binomial_p_value"] < 0.05

    def test_step6_primary_125_significant(self, summary):
        """primary_125 hit_rate must be significant at alpha=0.05."""
        sub = summary["step6_subset_comparison"]["subsets"]["primary_125"]
        assert sub["significant_at_05"] is True
        assert sub["binomial_p_value"] < 0.05

    def test_step6_shadow_100_significant(self, summary):
        """shadow_100 hit_rate must be significant at alpha=0.05."""
        sub = summary["step6_subset_comparison"]["subsets"]["shadow_100"]
        assert sub["significant_at_05"] is True
        assert sub["binomial_p_value"] < 0.05

    def test_step6_tier_b_not_significant(self, summary):
        """tier_b hit_rate must NOT be significant at alpha=0.05 (n=94 too small)."""
        sub = summary["step6_subset_comparison"]["subsets"]["tier_b"]
        assert sub["significant_at_05"] is False
        assert sub["binomial_p_value"] >= 0.05

    def test_step6_primary_125_n_correct(self, summary):
        """primary_125 n_correct must be 296."""
        sub = summary["step6_subset_comparison"]["subsets"]["primary_125"]
        assert sub["n_correct"] == 296

    def test_step6_primary_125_exceeds_all(self, summary):
        """primary_125 hit_rate must exceed all-row hit_rate."""
        p125_hr = summary["step6_subset_comparison"]["subsets"]["primary_125"]["hit_rate"]
        all_hr  = summary["step6_subset_comparison"]["subsets"]["all"]["hit_rate"]
        assert p125_hr > all_hr, f"primary_125 {p125_hr} should exceed all {all_hr}"

    def test_step6_wilson_ci_above_05_for_primary(self, summary):
        """primary_125 Wilson CI lower bound must be > 0.50."""
        lo = summary["step6_subset_comparison"]["subsets"]["primary_125"]["wilson_ci_95_lo"]
        assert lo > 0.50, f"primary_125 Wilson CI lo={lo} <= 0.50"

    def test_step6_all_wilson_ci_above_05(self, summary):
        """All-row Wilson CI lower bound must be > 0.50."""
        lo = summary["step6_subset_comparison"]["subsets"]["all"]["wilson_ci_95_lo"]
        assert lo > 0.50, f"all Wilson CI lo={lo} <= 0.50"


# ──────────────────────────────────────────────────────────────────────────────
# STEP 7 — FINAL CLASSIFICATION
# ──────────────────────────────────────────────────────────────────────────────

class TestStep7FinalClassification:
    def test_step7_classification_is_one_of_five(self, summary):
        """Final classification must be one of the five allowed values."""
        clf = summary["p84h_classification"]
        assert clf in ALLOWED_CLASSIFICATIONS, f"Invalid classification: {clf}"

    def test_step7_classification_matches_step7(self, summary):
        """Top-level and step7 classification must match."""
        top   = summary["p84h_classification"]
        step7 = summary["step7_final_classification"]["classification"]
        assert top == step7, f"Mismatch: top={top}, step7={step7}"

    def test_step7_classification_value(self, summary):
        """Final classification must be P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED."""
        assert summary["p84h_classification"] == "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"

    def test_step7_key_metrics_hit_rate(self, summary):
        """Step 7 key_metrics hit_rate must be > 0.55."""
        hr = summary["step7_final_classification"]["key_metrics"]["hit_rate"]
        assert hr > 0.55, f"key_metrics hit_rate {hr} <= 0.55"

    def test_step7_key_metrics_auc(self, summary):
        """Step 7 key_metrics AUC must be > 0.56."""
        auc = summary["step7_final_classification"]["key_metrics"]["auc"]
        assert auc > 0.56, f"key_metrics AUC {auc} <= 0.56"

    def test_step7_key_metrics_coverage_class(self, summary):
        """Step 7 key_metrics coverage_classification must be COVERAGE_LIMITED."""
        cc = summary["step7_final_classification"]["key_metrics"]["coverage_classification"]
        assert cc == "COVERAGE_LIMITED"

    def test_step7_key_metrics_primary_125_significant(self, summary):
        """Step 7 key_metrics primary_125_significant must be True."""
        assert summary["step7_final_classification"]["key_metrics"]["primary_125_significant"] is True

    def test_step7_rationale_nonempty(self, summary):
        """Final classification must include at least 2 rationale entries."""
        rationale = summary["step7_final_classification"]["rationale"]
        assert isinstance(rationale, list) and len(rationale) >= 2


# ──────────────────────────────────────────────────────────────────────────────
# GOVERNANCE SCAN
# ──────────────────────────────────────────────────────────────────────────────

class TestGovernanceScan:
    def test_gov_paper_only_true(self, summary):
        """paper_only must be True."""
        assert summary["governance"]["paper_only"] is True

    def test_gov_diagnostic_only_true(self, summary):
        """diagnostic_only must be True."""
        assert summary["governance"]["diagnostic_only"] is True

    def test_gov_production_ready_false(self, summary):
        """production_ready must be False."""
        assert summary["governance"]["production_ready"] is False

    def test_gov_odds_used_false(self, summary):
        """odds_used must be False — no odds data used."""
        assert summary["governance"]["odds_used"] is False

    def test_gov_ev_computed_false(self, summary):
        """ev_computed must be False — no EV calculation."""
        assert summary["governance"]["ev_computed"] is False

    def test_gov_clv_computed_false(self, summary):
        """clv_computed must be False — no CLV calculation."""
        assert summary["governance"]["clv_computed"] is False

    def test_gov_kelly_computed_false(self, summary):
        """kelly_computed must be False — no Kelly sizing."""
        assert summary["governance"]["kelly_computed"] is False

    def test_gov_live_api_calls_zero(self, summary):
        """live_api_calls must be 0 — no live or paid API calls."""
        assert summary["governance"]["live_api_calls"] == 0

    def test_gov_paid_api_called_false(self, summary):
        """paid_api_called must be False."""
        assert summary["governance"]["paid_api_called"] is False

    def test_gov_canonical_rows_not_modified(self, summary):
        """canonical_rows_modified must be False — frozen artifact."""
        assert summary["governance"]["canonical_rows_modified"] is False

    def test_gov_outcome_rows_not_modified(self, summary):
        """outcome_rows_modified must be False — frozen artifact."""
        assert summary["governance"]["outcome_rows_modified"] is False

    def test_gov_p83e_mapping_not_modified(self, summary):
        """p83e_mapping_modified must be False — P83E mapping frozen post-P84G."""
        assert summary["governance"]["p83e_mapping_modified"] is False

    def test_gov_champion_not_replaced(self, summary):
        """champion_replaced must be False — no strategy promotion."""
        assert summary["governance"]["champion_replaced"] is False


# ──────────────────────────────────────────────────────────────────────────────
# REPORT CONTENT CHECKS
# ──────────────────────────────────────────────────────────────────────────────

class TestReportContent:
    def test_report_contains_classification(self):
        """Report must contain the final classification string."""
        text = P84H_REPORT_PATH.read_text(encoding="utf-8")
        assert "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED" in text

    def test_report_contains_partial_coverage_note(self):
        """Report must note partial coverage (not full season)."""
        text = P84H_REPORT_PATH.read_text(encoding="utf-8")
        assert "828" in text and "2430" in text

    def test_report_contains_ece(self):
        """Report must contain ECE value."""
        text = P84H_REPORT_PATH.read_text(encoding="utf-8")
        assert "ECE" in text or "ece" in text.lower()

    def test_report_contains_fip_mention(self):
        """Report must mention FIP (the predictor basis)."""
        text = P84H_REPORT_PATH.read_text(encoding="utf-8")
        assert "FIP" in text or "fip" in text.lower()

    def test_report_no_odds_or_ev(self):
        """Report must NOT contain odds/EV/CLV/Kelly computation results."""
        text = P84H_REPORT_PATH.read_text(encoding="utf-8").lower()
        # It's OK to mention these as governance flags (odds_used=false), but
        # there should be no actual computed values presented
        assert "expected value" not in text or "ev_computed=false" in text.replace(" ", "").lower()

    def test_report_mentions_no_production_claim(self):
        """Report must explicitly state no production claim."""
        text = P84H_REPORT_PATH.read_text(encoding="utf-8")
        assert "production" in text.lower() and (
            "false" in text.lower() or "no production" in text.lower()
        )
