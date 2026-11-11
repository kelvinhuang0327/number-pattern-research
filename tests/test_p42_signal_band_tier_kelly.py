"""
P42 test suite: signal-band tier framework + Kelly-equivalent diagnostic
=========================================================================
Tests the p42_signal_band_tier_kelly_summary.json output produced by
scripts/_p42_signal_band_tier_kelly_diagnostic.py

All assertions use exact-match or bounded ranges on values computed by the
script; no re-computation is performed here.

Governance:
  diagnostic_only      = True
  promotion_freeze     = True
  kelly_deploy_allowed = False
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data/mlb_2025/derived/p42_signal_band_tier_kelly_summary.json"


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(JSON_PATH.read_text())


# ── 1. File existence ─────────────────────────────────────────────────────────
class TestFileExists:
    def test_json_exists(self):
        assert JSON_PATH.exists(), f"Missing: {JSON_PATH}"

    def test_json_parseable(self, data):
        assert isinstance(data, dict)

    def test_version_field(self, data):
        assert data["version"] == "p42_v1"


# ── 2. Governance ─────────────────────────────────────────────────────────────
class TestGovernance:
    def test_diagnostic_only(self, data):
        assert data["governance"]["diagnostic_only"] is True

    def test_promotion_freeze(self, data):
        assert data["governance"]["promotion_freeze"] is True

    def test_kelly_deploy_forbidden(self, data):
        assert data["governance"]["kelly_deploy_allowed"] is False

    def test_live_api_calls_zero(self, data):
        assert data["governance"]["live_api_calls"] == 0

    def test_t_locked(self, data):
        assert data["governance"]["T_LOCKED"] == 0.50

    def test_p41_commit_ref(self, data):
        assert data["governance"]["p41_commit"] == "6ee4e57"

    def test_p40_commit_ref(self, data):
        assert data["governance"]["p40_commit"] == "5870cef"


# ── 3. Data inventory ─────────────────────────────────────────────────────────
class TestDataInventory:
    def test_total_quality_records_positive(self, data):
        n = data["data_inventory"]["n_quality_total"]
        assert n > 0

    def test_total_quality_records_range(self, data):
        # Combined 2024+2025 quality pool (full, not strong-edge subset)
        n = data["data_inventory"]["n_quality_total"]
        assert 3000 <= n <= 5000

    def test_n_2024_present(self, data):
        n24 = data["data_inventory"]["n_quality_2024"]
        assert n24 > 0

    def test_n_2025_present(self, data):
        n25 = data["data_inventory"]["n_quality_2025"]
        assert n25 > 0

    def test_year_totals_sum_to_total(self, data):
        inv = data["data_inventory"]
        assert inv["n_quality_2024"] + inv["n_quality_2025"] == inv["n_quality_total"]

    def test_t_locked_in_data_inventory(self, data):
        assert data["data_inventory"]["T_LOCKED"] == 0.50


# ── 4. Tier definitions ───────────────────────────────────────────────────────
class TestTierDefinitions:
    def test_tier_a_threshold(self, data):
        assert data["tier_definitions"]["A"]["threshold_abs_delta"] == 1.50

    def test_tier_b_threshold(self, data):
        assert data["tier_definitions"]["B"]["threshold_abs_delta"] == 1.25

    def test_tier_c_threshold(self, data):
        assert data["tier_definitions"]["C"]["threshold_abs_delta"] == 0.50

    def test_tiers_keys_present(self, data):
        assert set(data["tiers"].keys()) == {"A", "B", "C"}


# ── 5. Tier A metrics ─────────────────────────────────────────────────────────
class TestTierAMetrics:
    def test_tier_a_n_range(self, data):
        n = data["tiers"]["A"]["n"]
        assert 20 <= n <= 200, f"Tier A n={n} out of expected range"

    def test_tier_a_auc_positive(self, data):
        assert data["tiers"]["A"]["auc"] > 0.50

    def test_tier_a_auc_value(self, data):
        auc = data["tiers"]["A"]["auc"]
        assert 0.60 <= auc <= 0.85, f"Tier A AUC={auc}"

    def test_tier_a_favored_wr_positive(self, data):
        assert data["tiers"]["A"]["favored_wr"] > 0.50

    def test_tier_a_coverage_lower_than_tier_c(self, data):
        cov_a = data["tiers"]["A"]["coverage_pct"]
        cov_c = data["tiers"]["C"]["coverage_pct"]
        assert cov_a < cov_c

    def test_tier_a_cross_year_stable(self, data):
        assert data["tiers"]["A"]["cross_year_stable"] is True

    def test_tier_a_has_per_year(self, data):
        per_year = data["tiers"]["A"]["per_year"]
        assert "2024" in per_year and "2025" in per_year

    def test_tier_a_classification_sample_limited(self, data):
        cls = data["tiers"]["A"]["classification"]
        assert "SAMPLE_LIMITED" in cls, f"Expected SAMPLE_LIMITED in Tier A classification, got {cls}"


# ── 6. Tier B metrics ─────────────────────────────────────────────────────────
class TestTierBMetrics:
    def test_tier_b_n_range(self, data):
        n = data["tiers"]["B"]["n"]
        assert 50 <= n <= 500, f"Tier B n={n}"

    def test_tier_b_n_gt_tier_a(self, data):
        assert data["tiers"]["B"]["n"] > data["tiers"]["A"]["n"]

    def test_tier_b_auc_positive(self, data):
        assert data["tiers"]["B"]["auc"] > 0.50

    def test_tier_b_auc_between_a_and_c(self, data):
        auc_a = data["tiers"]["A"]["auc"]
        auc_b = data["tiers"]["B"]["auc"]
        auc_c = data["tiers"]["C"]["auc"]
        assert auc_c < auc_b < auc_a, (
            f"Expected AUC_C < AUC_B < AUC_A: {auc_c:.4f} < {auc_b:.4f} < {auc_a:.4f}"
        )

    def test_tier_b_cross_year_stable(self, data):
        assert data["tiers"]["B"]["cross_year_stable"] is True

    def test_tier_b_classification(self, data):
        cls = data["tiers"]["B"]["classification"]
        assert cls in {"HIGH_CONFIDENCE_DIAGNOSTIC", "MEDIUM_CONFIDENCE_DIAGNOSTIC"}, (
            f"Unexpected Tier B classification: {cls}"
        )

    def test_tier_b_per_year_2024_auc_positive(self, data):
        yr = data["tiers"]["B"]["per_year"].get("2024", {})
        if "auc_positive" in yr:
            assert yr["auc_positive"] is True

    def test_tier_b_per_year_2025_auc_positive(self, data):
        yr = data["tiers"]["B"]["per_year"].get("2025", {})
        if "auc_positive" in yr:
            assert yr["auc_positive"] is True


# ── 7. Tier C metrics ─────────────────────────────────────────────────────────
class TestTierCMetrics:
    def test_tier_c_n_range(self, data):
        n = data["tiers"]["C"]["n"]
        assert 1000 <= n <= 2000, f"Tier C n={n}"

    def test_tier_c_n_matches_p41_reference(self, data):
        """P41 committed result: n=1490 combined."""
        n = data["tiers"]["C"]["n"]
        assert abs(n - 1490) <= 10, f"Tier C n={n}, expected ~1490"

    def test_tier_c_auc_matches_p41(self, data):
        """P41 committed AUC=0.5865 for Tier C (same threshold)."""
        auc = data["tiers"]["C"]["auc"]
        assert abs(auc - 0.5865) < 0.01, f"Tier C AUC={auc}, expected ~0.5865"

    def test_tier_c_auc_positive(self, data):
        assert data["tiers"]["C"]["auc"] > 0.50

    def test_tier_c_cross_year_stable(self, data):
        assert data["tiers"]["C"]["cross_year_stable"] is True

    def test_tier_c_per_year_both_positive(self, data):
        per_year = data["tiers"]["C"]["per_year"]
        for yr in ("2024", "2025"):
            assert per_year[yr].get("auc_positive") is True, f"Tier C {yr} AUC not positive"

    def test_tier_c_coverage_pct_highest(self, data):
        cov_c = data["tiers"]["C"]["coverage_pct"]
        cov_b = data["tiers"]["B"]["coverage_pct"]
        cov_a = data["tiers"]["A"]["coverage_pct"]
        assert cov_c > cov_b > cov_a


# ── 8. Bootstrap CI ───────────────────────────────────────────────────────────
class TestBootstrapCI:
    def test_tier_a_auc_ci_brackets_point_estimate(self, data):
        t = data["tiers"]["A"]["bootstrap_auc"]
        auc = data["tiers"]["A"]["auc"]
        assert t["ci_95_low"] <= auc <= t["ci_95_high"]

    def test_tier_b_auc_ci_excludes_050(self, data):
        assert data["tiers"]["B"]["bootstrap_auc"]["ci_excludes_050"] is True

    def test_tier_c_auc_ci_excludes_050(self, data):
        assert data["tiers"]["C"]["bootstrap_auc"]["ci_excludes_050"] is True

    def test_tier_c_auc_ci_matches_p41_reference(self, data):
        """P41 CI was [0.5557, 0.6170]."""
        t = data["tiers"]["C"]["bootstrap_auc"]
        assert abs(t["ci_95_low"] - 0.5557) < 0.01
        assert abs(t["ci_95_high"] - 0.617) < 0.01

    def test_all_tiers_have_wr_bootstrap(self, data):
        for tier in "ABC":
            assert "bootstrap_wr" in data["tiers"][tier]
            bwr = data["tiers"][tier]["bootstrap_wr"]
            assert "ci_95_low" in bwr and "ci_95_high" in bwr

    def test_tier_c_wr_ci_excludes_050(self, data):
        assert data["tiers"]["C"]["bootstrap_wr"]["ci_excludes_050"] is True

    def test_n_boot_1000(self, data):
        for tier in "ABC":
            assert data["tiers"][tier]["bootstrap_auc"]["n_boot"] == 1000


# ── 9. Tier A vs C comparison ─────────────────────────────────────────────────
class TestComparisonAC:
    def test_comparison_key_exists(self, data):
        assert "comparison_tier_a_vs_c" in data

    def test_observed_delta_positive(self, data):
        delta = data["comparison_tier_a_vs_c"]["observed_delta"]
        assert delta > 0, f"Expected positive AUC delta A-C, got {delta}"

    def test_observed_delta_substantial(self, data):
        delta = data["comparison_tier_a_vs_c"]["observed_delta"]
        assert delta >= 0.10, f"AUC delta={delta}, expected >= 0.10"

    def test_n_permutations(self, data):
        assert data["comparison_tier_a_vs_c"]["n_permutations"] == 2000

    def test_significance_field_valid(self, data):
        sig = data["comparison_tier_a_vs_c"]["significance_05"]
        assert sig in {"significant", "not_significant"}

    def test_caveat_mentions_sample_size(self, data):
        caveat = data["comparison_tier_a_vs_c"]["caveat"].lower()
        assert "n=47" in caveat or "insufficient" in caveat, (
            "Caveat should mention Tier A sample size limitation"
        )

    def test_auc_values_consistent_with_tiers(self, data):
        cmp = data["comparison_tier_a_vs_c"]
        assert cmp["tier_a_auc"] == data["tiers"]["A"]["auc"]
        assert cmp["tier_c_auc"] == data["tiers"]["C"]["auc"]


# ── 10. Kelly diagnostic ──────────────────────────────────────────────────────
class TestKellyDiagnostic:
    def test_all_tiers_have_kelly_diagnostic(self, data):
        for tier in "ABC":
            assert "kelly_diagnostic" in data["tiers"][tier]
            assert len(data["tiers"][tier]["kelly_diagnostic"]) == 3

    def test_kelly_diagnostic_only_note(self, data):
        for tier in "ABC":
            for s in data["tiers"][tier]["kelly_diagnostic"]:
                note = s.get("note", "").upper()
                assert "DIAGNOSTIC ONLY" in note, (
                    f"Tier {tier} Kelly scenario missing DIAGNOSTIC ONLY note"
                )

    def test_kelly_scenarios_present(self, data):
        labels = {s["scenario"] for s in data["tiers"]["C"]["kelly_diagnostic"]}
        assert "fair_no_vig" in labels
        assert "tight_book" in labels
        assert "standard_book" in labels

    def test_tier_c_kelly_positive_ev(self, data):
        for s in data["tiers"]["C"]["kelly_diagnostic"]:
            assert s["positive_ev"] is True, (
                f"Tier C Kelly scenario {s['scenario']} not positive_ev"
            )

    def test_tier_b_kelly_positive_ev(self, data):
        for s in data["tiers"]["B"]["kelly_diagnostic"]:
            assert s["positive_ev"] is True

    def test_kelly_fractions_in_range(self, data):
        """All positive kelly fractions must be between 0 and 1."""
        for tier in "ABC":
            for s in data["tiers"][tier]["kelly_diagnostic"]:
                f = s.get("full_kelly_fraction")
                if f is not None:
                    assert 0 < f < 1.0, f"Kelly fraction out of range: tier={tier}, f={f}"

    def test_quarter_kelly_fraction_is_quarter_of_full(self, data):
        for tier in "ABC":
            for s in data["tiers"][tier]["kelly_diagnostic"]:
                full = s.get("full_kelly_fraction")
                quarter = s.get("quarter_kelly_fraction")
                if full is not None and quarter is not None:
                    assert abs(quarter - full / 4.0) < 1e-3, (
                        f"Quarter Kelly mismatch: full={full}, quarter={quarter}"
                    )

    def test_p_win_assumed_matches_favored_wr(self, data):
        for tier in "ABC":
            wr = data["tiers"][tier]["favored_wr"]
            for s in data["tiers"][tier]["kelly_diagnostic"]:
                assert abs(s["p_win_assumed"] - wr) < 1e-3, (
                    f"Tier {tier} Kelly p_win_assumed mismatch"
                )


# ── 11. Tier classification ───────────────────────────────────────────────────
class TestTierClassification:
    def test_tier_a_sample_limited(self, data):
        cls = data["tiers"]["A"]["classification"]
        assert "SAMPLE_LIMITED" in cls

    def test_tier_b_medium_or_high_confidence(self, data):
        cls = data["tiers"]["B"]["classification"]
        assert "CONFIDENCE_DIAGNOSTIC" in cls

    def test_tier_c_high_or_broad_signal(self, data):
        cls = data["tiers"]["C"]["classification"]
        assert cls in {
            "HIGH_CONFIDENCE_DIAGNOSTIC",
            "BROAD_STABLE_SIGNAL",
            "MEDIUM_CONFIDENCE_DIAGNOSTIC",
        }

    def test_classifications_not_calibration_required(self, data):
        """No tier should degrade to CALIBRATION_REQUIRED given the strong AUC signal."""
        for tier in "BC":  # Tier A excluded (sample limited)
            cls = data["tiers"][tier]["classification"]
            assert cls != "CALIBRATION_REQUIRED", (
                f"Tier {tier} degraded to CALIBRATION_REQUIRED"
            )


# ── 12. P41 reference consistency ────────────────────────────────────────────
class TestP41Reference:
    def test_p41_reference_auc(self, data):
        assert data["p41_reference"]["combined_auc"] == 0.5865

    def test_p41_reference_n(self, data):
        assert data["p41_reference"]["combined_n"] == 1490

    def test_p41_reference_commit(self, data):
        assert data["p41_reference"]["commit"] == "6ee4e57"

    def test_tier_c_auc_consistent_with_p41(self, data):
        """Tier C (T>=0.50) must reproduce P41's combined AUC within tolerance."""
        p41_auc = data["p41_reference"]["combined_auc"]
        tier_c_auc = data["tiers"]["C"]["auc"]
        assert abs(tier_c_auc - p41_auc) < 0.01


# ── 13. Metric field completeness ────────────────────────────────────────────
class TestMetricCompleteness:
    EXPECTED_FIELDS = {
        "tier", "threshold", "n", "coverage_pct",
        "auc", "favored_wr", "brier_score", "brier_skill",
        "log_loss", "ece", "bootstrap_auc", "bootstrap_wr",
        "per_year", "cross_year_stable", "kelly_diagnostic", "classification",
    }

    def test_tier_a_has_all_fields(self, data):
        missing = self.EXPECTED_FIELDS - set(data["tiers"]["A"].keys())
        assert not missing, f"Tier A missing fields: {missing}"

    def test_tier_b_has_all_fields(self, data):
        missing = self.EXPECTED_FIELDS - set(data["tiers"]["B"].keys())
        assert not missing, f"Tier B missing fields: {missing}"

    def test_tier_c_has_all_fields(self, data):
        missing = self.EXPECTED_FIELDS - set(data["tiers"]["C"].keys())
        assert not missing, f"Tier C missing fields: {missing}"

    def test_all_auc_values_not_nan(self, data):
        for tier in "ABC":
            assert not math.isnan(data["tiers"][tier]["auc"]), f"Tier {tier} AUC is NaN"

    def test_tier_monotonicity(self, data):
        """Higher threshold → fewer records (strict monotone)."""
        n_a = data["tiers"]["A"]["n"]
        n_b = data["tiers"]["B"]["n"]
        n_c = data["tiers"]["C"]["n"]
        assert n_a < n_b < n_c, f"Monotonicity violated: n_A={n_a}, n_B={n_b}, n_C={n_c}"
