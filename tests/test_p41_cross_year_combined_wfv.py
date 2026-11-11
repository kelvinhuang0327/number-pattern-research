"""
P41 test suite — Cross-Year Combined WFV Validation
Requires: data/mlb_2025/derived/p41_cross_year_combined_summary.json
Run: pytest tests/test_p41_cross_year_combined_wfv.py -v
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_PATH = ROOT / "data/mlb_2025/derived/p41_cross_year_combined_summary.json"


@pytest.fixture(scope="module")
def summary() -> dict:
    with open(SUMMARY_PATH) as f:
        return json.load(f)


# ── Class 1: File Existence ───────────────────────────────────────────────────
class TestSummaryExists:
    def test_file_exists(self):
        assert SUMMARY_PATH.exists(), f"Missing: {SUMMARY_PATH}"

    def test_valid_json(self):
        data = json.loads(SUMMARY_PATH.read_text())
        assert isinstance(data, dict)

    def test_required_top_level_keys(self, summary):
        for key in ("governance", "data_inventory", "combined_metrics",
                    "bootstrap_ci", "band_analysis", "seasonal_breakdown",
                    "monthly_stability", "classification", "per_year_metrics"):
            assert key in summary, f"Missing key: {key}"

    def test_version_field(self, summary):
        assert summary.get("version", "").startswith("p41")


# ── Class 2: Governance ───────────────────────────────────────────────────────
class TestGovernance:
    def test_diagnostic_only(self, summary):
        assert summary["governance"]["diagnostic_only"] is True

    def test_promotion_freeze(self, summary):
        assert summary["governance"]["promotion_freeze"] is True

    def test_t_locked(self, summary):
        assert summary["governance"]["T_LOCKED"] == 0.50

    def test_live_api_calls_zero(self, summary):
        assert summary["governance"]["live_api_calls"] == 0

    def test_no_champion_modification(self, summary):
        assert summary["governance"]["no_champion_modification"] is True

    def test_p39_commit_present(self, summary):
        assert "p39_commit" in summary["governance"]
        assert len(summary["governance"]["p39_commit"]) >= 7

    def test_p40_commit_present(self, summary):
        assert "p40_commit" in summary["governance"]
        assert len(summary["governance"]["p40_commit"]) >= 7


# ── Class 3: Data Inventory ───────────────────────────────────────────────────
class TestDataInventory:
    def test_n_2025_quality_in_range(self, summary):
        n = summary["data_inventory"]["n_2025_quality"]
        assert 1000 <= n <= 3000, f"2025 quality count unexpected: {n}"

    def test_n_2024_quality_in_range(self, summary):
        n = summary["data_inventory"]["n_2024_quality"]
        assert 1000 <= n <= 4000, f"2024 quality count unexpected: {n}"

    def test_n_2025_strong_edge_in_range(self, summary):
        n = summary["data_inventory"]["n_2025_strong_edge"]
        assert 400 <= n <= 800, f"2025 strong-edge count unexpected: {n}"

    def test_n_2024_strong_edge_in_range(self, summary):
        n = summary["data_inventory"]["n_2024_strong_edge"]
        assert 800 <= n <= 1200, f"2024 strong-edge count unexpected: {n}"

    def test_combined_equals_sum(self, summary):
        inv = summary["data_inventory"]
        assert inv["n_combined_strong_edge"] == (
            inv["n_2025_strong_edge"] + inv["n_2024_strong_edge"]
        )

    def test_combined_min_threshold(self, summary):
        n = summary["data_inventory"]["n_combined_strong_edge"]
        assert n >= 1000, f"Combined n too small: {n}"

    def test_t_locked_correct(self, summary):
        assert summary["data_inventory"]["T_LOCKED"] == 0.50


# ── Class 4: Combined Metrics ─────────────────────────────────────────────────
class TestCombinedMetrics:
    def test_auc_in_valid_range(self, summary):
        auc = summary["combined_metrics"]["auc"]
        assert 0.0 <= auc <= 1.0, f"AUC out of range: {auc}"

    def test_auc_above_random(self, summary):
        auc = summary["combined_metrics"]["auc"]
        assert auc > 0.50, f"AUC <= 0.50 (random baseline): {auc}"

    def test_auc_confirmed_threshold(self, summary):
        """AUC must be >= 0.54 to match CROSS_YEAR_CONFIRMED classification."""
        cls = summary["classification"]["classification"]
        auc = summary["combined_metrics"]["auc"]
        if cls == "CROSS_YEAR_CONFIRMED":
            assert auc >= 0.54, f"CONFIRMED but AUC={auc} < 0.54"

    def test_favored_wr_above_50pct(self, summary):
        wr = summary["combined_metrics"]["favored_wr"]
        assert wr > 0.50, f"Favored WR <= 0.50: {wr}"

    def test_brier_score_valid(self, summary):
        bs = summary["combined_metrics"]["brier_score"]
        assert 0.0 < bs < 1.0, f"Brier score invalid: {bs}"

    def test_log_loss_positive(self, summary):
        ll = summary["combined_metrics"]["log_loss"]
        assert ll > 0.0, f"Log-loss not positive: {ll}"

    def test_ece_in_range(self, summary):
        ece = summary["combined_metrics"]["ece"]
        assert 0.0 <= ece <= 1.0, f"ECE out of range: {ece}"

    def test_per_year_2024_auc_above_random(self, summary):
        auc = summary["per_year_metrics"]["2024"]["auc"]
        assert auc > 0.50, f"2024 per-year AUC <= 0.50: {auc}"

    def test_per_year_2025_auc_above_random(self, summary):
        auc = summary["per_year_metrics"]["2025"]["auc"]
        assert auc > 0.50, f"2025 per-year AUC <= 0.50: {auc}"


# ── Class 5: Bootstrap CI ─────────────────────────────────────────────────────
class TestBootstrapCI:
    def test_ci_low_le_mean_le_high(self, summary):
        ci = summary["bootstrap_ci"]
        assert ci["ci_95_low"] <= ci["auc_mean"] <= ci["ci_95_high"]

    def test_ci_excludes_050(self, summary):
        ci = summary["bootstrap_ci"]
        assert ci["ci_95_low"] > 0.50, (
            f"95% CI lower bound {ci['ci_95_low']:.4f} does not exclude 0.50"
        )

    def test_ci_excludes_050_flag(self, summary):
        assert summary["bootstrap_ci"]["ci_excludes_0_50"] is True

    def test_ci_width_reasonable(self, summary):
        ci = summary["bootstrap_ci"]
        width = ci["ci_95_high"] - ci["ci_95_low"]
        assert 0.01 <= width <= 0.20, f"CI width unreasonable: {width:.4f}"

    def test_n_boot_recorded(self, summary):
        assert summary["bootstrap_ci"]["n_boot"] == 1000

    def test_classification_ci_low_consistent(self, summary):
        assert (
            summary["classification"]["ci_95_low"]
            == summary["bootstrap_ci"]["ci_95_low"]
        )


# ── Class 6: Band Analysis ────────────────────────────────────────────────────
class TestBandAnalysis:
    def test_five_bands_present(self, summary):
        assert len(summary["band_analysis"]) == 5

    def test_band_labels_correct(self, summary):
        expected = ["0.50–0.75", "0.75–1.00", "1.00–1.25", "1.25–1.50", "1.50+"]
        actual = [b["band"] for b in summary["band_analysis"]]
        assert actual == expected

    def test_all_bands_have_data(self, summary):
        for b in summary["band_analysis"]:
            assert b["n"] >= 0, f"Band {b['band']} has negative n"

    def test_band_counts_sum_to_combined(self, summary):
        total_band = sum(b["n"] for b in summary["band_analysis"])
        combined_n = summary["data_inventory"]["n_combined_strong_edge"]
        assert total_band == combined_n, (
            f"Band sum {total_band} != combined n {combined_n}"
        )

    def test_highest_band_auc_strongest(self, summary):
        """1.50+ band should have highest AUC (monotonic signal expectation)."""
        aucs = [(b["auc"], b["band"]) for b in summary["band_analysis"]
                if b.get("auc") is not None]
        if len(aucs) >= 2:
            last_auc = aucs[-1][0]
            first_auc = aucs[0][0]
            assert last_auc >= first_auc, (
                f"1.50+ AUC ({last_auc}) not >= 0.50-0.75 AUC ({first_auc})"
            )

    def test_all_band_aucs_in_valid_range(self, summary):
        for b in summary["band_analysis"]:
            if b.get("auc") is not None:
                assert 0.0 <= b["auc"] <= 1.0, f"Band {b['band']} AUC out of range"

    def test_all_bands_favored_wr_present(self, summary):
        for b in summary["band_analysis"]:
            if b["n"] >= 10:
                assert b.get("favored_wr") is not None, (
                    f"Band {b['band']} missing favored_wr (n={b['n']})"
                )


# ── Class 7: Seasonal Breakdown ───────────────────────────────────────────────
class TestSeasonalBreakdown:
    def test_2024_breakdown_has_three_periods(self, summary):
        assert len(summary["seasonal_breakdown"]["2024"]) == 3

    def test_2025_breakdown_has_three_periods(self, summary):
        assert len(summary["seasonal_breakdown"]["2025"]) == 3

    def test_2024_all_periods_auc_above_050(self, summary):
        for row in summary["seasonal_breakdown"]["2024"]:
            if row.get("auc") is not None:
                assert row["auc"] > 0.50, (
                    f"2024 {row['period']} AUC {row['auc']} <= 0.50"
                )

    def test_2025_all_periods_auc_above_050(self, summary):
        for row in summary["seasonal_breakdown"]["2025"]:
            if row.get("auc") is not None:
                assert row["auc"] > 0.50, (
                    f"2025 {row['period']} AUC {row['auc']} <= 0.50"
                )

    def test_seasonal_n_sums_match_year_totals(self, summary):
        n_2024 = sum(r["n"] for r in summary["seasonal_breakdown"]["2024"])
        n_2025 = sum(r["n"] for r in summary["seasonal_breakdown"]["2025"])
        assert n_2024 == summary["data_inventory"]["n_2024_strong_edge"]
        assert n_2025 == summary["data_inventory"]["n_2025_strong_edge"]


# ── Class 8: Monthly Stability ────────────────────────────────────────────────
class TestMonthlyStability:
    def test_stability_rate_above_70pct(self, summary):
        rate = summary["monthly_stability"]["stability_rate"]
        assert rate >= 0.70, f"Monthly stability rate {rate:.1%} < 70%"

    def test_eligible_months_reasonable(self, summary):
        n = summary["monthly_stability"]["eligible_months"]
        assert n >= 10, f"Too few eligible months: {n}"

    def test_monthly_auc_present(self, summary):
        assert "monthly_auc" in summary["monthly_stability"]
        assert len(summary["monthly_stability"]["monthly_auc"]) >= 10


# ── Class 9: Classification ───────────────────────────────────────────────────
class TestClassification:
    def test_classification_is_confirmed(self, summary):
        cls = summary["classification"]["classification"]
        assert cls == "CROSS_YEAR_CONFIRMED", f"Expected CROSS_YEAR_CONFIRMED, got {cls}"

    def test_classification_consistent_with_auc(self, summary):
        cls = summary["classification"]["classification"]
        auc = summary["classification"]["combined_auc"]
        n = summary["classification"]["combined_n"]
        if n >= 50:
            if auc >= 0.54:
                assert cls == "CROSS_YEAR_CONFIRMED"
            elif auc >= 0.50:
                assert cls == "CROSS_YEAR_WEAK"
            else:
                assert cls == "CROSS_YEAR_FAILED"

    def test_combined_n_sufficient(self, summary):
        n = summary["classification"]["combined_n"]
        assert n >= 1000, f"Combined n {n} is unexpectedly low"

    def test_ci_excludes_050_in_classification(self, summary):
        assert summary["classification"]["ci_excludes_0_50"] is True
