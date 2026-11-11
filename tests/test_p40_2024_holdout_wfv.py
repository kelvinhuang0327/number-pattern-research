"""
P40 Tests — 2024 Holdout WFV Validation
=========================================
Tests for:
  - p40_2024_holdout_wfv_summary.json existence and content
  - Classification correctness
  - Governance fields
  - Metric plausibility (AUC in [0,1], BrierSk is float, etc.)
  - Temporal stability completeness
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

_REPO        = Path(__file__).parent.parent
_SUMMARY     = _REPO / "data" / "mlb_2025" / "derived" / "p40_2024_holdout_wfv_summary.json"
_FEATURES    = _REPO / "data" / "mlb_2025" / "derived" / "mlb_2024_sp_fip_delta_features.jsonl"

# P37 locked baseline
P37_AUC         = 0.5665
P37_BRIER_SKILL = 0.0123
P37_FAVORED_WR  = 0.608
P37_SE_COUNT    = 531


@pytest.fixture(scope="module")
def summary() -> dict:
    if not _SUMMARY.exists():
        pytest.skip(f"{_SUMMARY} not found — run _p40_2024_holdout_wfv_validation.py first")
    return json.loads(_SUMMARY.read_text(encoding="utf-8"))


# ── Test 1: Summary JSON exists ────────────────────────────────────────────────
class TestSummaryExists:
    def test_file_exists(self) -> None:
        assert _SUMMARY.exists(), f"P40 summary JSON not found: {_SUMMARY}"

    def test_file_nonempty(self) -> None:
        assert _SUMMARY.stat().st_size > 500, "P40 summary JSON is suspiciously small"

    def test_json_parseable(self) -> None:
        data = json.loads(_SUMMARY.read_text(encoding="utf-8"))
        assert isinstance(data, dict)


# ── Test 2: Governance fields ─────────────────────────────────────────────────
class TestGovernance:
    def test_phase_is_p40(self, summary: dict) -> None:
        assert summary["governance"]["phase"] == "P40"

    def test_diagnostic_only_true(self, summary: dict) -> None:
        assert summary["governance"]["diagnostic_only"] is True

    def test_promotion_freeze_true(self, summary: dict) -> None:
        assert summary["governance"]["promotion_freeze"] is True

    def test_t_locked_is_050(self, summary: dict) -> None:
        assert summary["governance"]["t_locked"] == 0.50

    def test_live_api_calls_zero(self, summary: dict) -> None:
        assert summary["governance"]["live_api_calls"] == 0


# ── Test 3: Data inventory ─────────────────────────────────────────────────────
class TestDataInventory:
    def test_total_records_correct(self, summary: dict) -> None:
        inv = summary["data_inventory"]
        assert inv["total_records"] >= 2400, (
            f"Expected ≥2400 total records, got {inv['total_records']}"
        )

    def test_quality_records_present(self, summary: dict) -> None:
        inv = summary["data_inventory"]
        assert inv["quality_records"] >= 1500, (
            f"Expected ≥1500 quality records, got {inv['quality_records']}"
        )

    def test_strong_edge_above_wfv_threshold(self, summary: dict) -> None:
        """At least 150 strong-edge records required for WFV."""
        n = summary["data_inventory"]["strong_edge_count"]
        assert n >= 150, f"Strong-edge count {n} < 150 WFV minimum"

    def test_strong_edge_exceeds_p37(self, summary: dict) -> None:
        """2024 holdout should have more strong-edge records than P37's 531."""
        n = summary["data_inventory"]["strong_edge_count"]
        assert n >= P37_SE_COUNT, (
            f"Strong-edge {n} < P37 baseline {P37_SE_COUNT}"
        )


# ── Test 4: Overall metrics ────────────────────────────────────────────────────
class TestOverallMetrics:
    def test_auc_in_valid_range(self, summary: dict) -> None:
        auc = summary["overall_metrics"]["auc"]
        assert 0.0 <= auc <= 1.0, f"AUC out of [0,1]: {auc}"

    def test_auc_above_random(self, summary: dict) -> None:
        """AUC must be > 0.50 for the signal to be positive."""
        auc = summary["overall_metrics"]["auc"]
        assert auc > 0.50, f"AUC {auc} is below random (0.50)"

    def test_auc_meets_confirmed_threshold(self, summary: dict) -> None:
        """Classification HOLDOUT_CONFIRMED requires AUC >= 0.54."""
        cls = summary["classification"]["classification"]
        auc = summary["overall_metrics"]["auc"]
        if cls == "HOLDOUT_CONFIRMED":
            assert auc >= 0.54, (
                f"Classification is HOLDOUT_CONFIRMED but AUC={auc} < 0.54"
            )

    def test_favored_wr_above_random(self, summary: dict) -> None:
        wr = summary["overall_metrics"]["favored_win_rate"]
        assert wr > 0.50, f"Favored win rate {wr} is below 50%"

    def test_brier_score_plausible(self, summary: dict) -> None:
        bs = summary["overall_metrics"]["brier_score"]
        assert 0.0 <= bs <= 1.0, f"Brier score out of [0,1]: {bs}"

    def test_base_rate_plausible(self, summary: dict) -> None:
        br = summary["overall_metrics"]["base_rate"]
        assert 0.40 <= br <= 0.65, f"Base rate (home win rate) implausible: {br}"

    def test_n_matches_inventory(self, summary: dict) -> None:
        n_overall = summary["overall_metrics"]["n"]
        n_inv     = summary["data_inventory"]["strong_edge_count"]
        assert n_overall == n_inv, (
            f"overall_metrics.n={n_overall} != data_inventory.strong_edge_count={n_inv}"
        )


# ── Test 5: Classification ─────────────────────────────────────────────────────
class TestClassification:
    def test_classification_is_valid_value(self, summary: dict) -> None:
        valid = {
            "HOLDOUT_CONFIRMED",
            "HOLDOUT_WEAK_REPLICATION",
            "HOLDOUT_FAILED",
            "INCONCLUSIVE",
        }
        cls = summary["classification"]["classification"]
        assert cls in valid, f"Unknown classification: {cls!r}"

    def test_classification_not_failed(self, summary: dict) -> None:
        """Strong-edge AUC > 0.50 means the holdout should not be FAILED."""
        cls = summary["classification"]["classification"]
        auc = summary["overall_metrics"]["auc"]
        if auc > 0.50:
            assert cls != "HOLDOUT_FAILED", (
                f"AUC={auc} > 0.50 but classification={cls!r}"
            )

    def test_classification_consistent_with_auc(self, summary: dict) -> None:
        cls = summary["classification"]["classification"]
        auc = summary["overall_metrics"]["auc"]
        if cls == "HOLDOUT_CONFIRMED":
            assert auc >= 0.54
        elif cls == "HOLDOUT_WEAK_REPLICATION":
            assert 0.50 <= auc < 0.54
        elif cls == "HOLDOUT_FAILED":
            assert auc < 0.50


# ── Test 6: Temporal stability ─────────────────────────────────────────────────
class TestTemporalStability:
    def test_monthly_metrics_present(self, summary: dict) -> None:
        monthly = summary["temporal_stability"]["monthly"]
        assert len(monthly) >= 7, (
            f"Expected ≥7 months of data, got {len(monthly)}"
        )

    def test_all_months_are_2024(self, summary: dict) -> None:
        monthly = summary["temporal_stability"]["monthly"]
        for ym in monthly.keys():
            assert ym[:4] == "2024", f"Non-2024 month key: {ym}"

    def test_stability_rate_in_valid_range(self, summary: dict) -> None:
        rate = summary["temporal_stability"]["monthly_stability_rate"]
        assert 0.0 <= rate <= 1.0, f"Stability rate out of [0,1]: {rate}"

    def test_high_monthly_stability(self, summary: dict) -> None:
        """Expect most months (≥70%) to have AUC >= 0.50."""
        rate = summary["temporal_stability"]["monthly_stability_rate"]
        assert rate >= 0.70, f"Monthly stability rate too low: {rate:.1%}"

    def test_period_keys_present(self, summary: dict) -> None:
        period = summary["temporal_stability"]["period"]
        assert "early" in period
        assert "mid" in period
        assert "late" in period

    def test_early_mid_late_positive_counts(self, summary: dict) -> None:
        period = summary["temporal_stability"]["period"]
        for p in ("early", "mid", "late"):
            n = period[p]["n"]
            assert n > 0, f"{p} season has 0 records"


# ── Test 7: Comparison vs P37 ──────────────────────────────────────────────────
class TestComparisonVsP37:
    def test_comparison_fields_present(self, summary: dict) -> None:
        cmp = summary["comparison_vs_p37"]
        assert "auc_delta" in cmp
        assert "brier_skill_delta" in cmp
        assert "favored_wr_delta" in cmp
        assert "stability_delta" in cmp

    def test_p37_baseline_recorded(self, summary: dict) -> None:
        b = summary["p37_baseline"]
        assert b["auc"] == P37_AUC
        assert b["brier_skill"] == P37_BRIER_SKILL
        assert b["season"] == "2025"

    def test_auc_delta_plausible(self, summary: dict) -> None:
        delta = summary["comparison_vs_p37"]["auc_delta"]
        # Delta should be in a reasonable range (not off by >0.3)
        assert -0.30 <= delta <= 0.30, f"AUC delta implausible: {delta}"
