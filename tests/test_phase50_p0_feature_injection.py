"""
tests/test_phase50_p0_feature_injection.py
==========================================
Phase 50 — P0 Feature Injection Test Suite (~60 tests, ≥10 classes)

覆蓋範圍：
  TestHardRuleInvariants         (6)  不變量
  TestAdjustmentCap              (6)  Total ≤ ±0.025 cap
  TestProbClamp                  (6)  adjusted ∈ [0.01, 0.99]
  TestSeasonGameIndex            (7)  F-004 early-season shrinkage
  TestParkRunFactor              (7)  F-002 park factor adjustment
  TestSpFipDelta                 (6)  F-001 sp_fip_delta (available/unavailable)
  TestLeakageGuard               (5)  forbidden field detection
  TestBuildPhase50Row            (6)  JSONL row structure
  TestBatchInjection             (7)  run_batch_injection stats
  TestPhase50Script              (6)  run() public API integration
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import pytest

# ── import adapter ────────────────────────────────────────────────────────────
from wbc_backend.features.mlb_p0_feature_injection import (
    CANDIDATE_PATCH_CREATED,
    FEATURE_VERSION,
    MAX_PER_FEATURE_ADJUSTMENT,     # noqa: F401  (may not exist, use module attribute)
    PRODUCTION_MODIFIED,
    AdjustmentResult,
    InjectionSummary,
    apply_p0_feature_adjustment,
    build_phase50_row,
    run_batch_injection,
)

# ── optional: import constants that might not be defined by name ──────────────
import wbc_backend.features.mlb_p0_feature_injection as _inj

MAX_TOTAL_ADJ = getattr(_inj, "_MAX_TOTAL_ADJUSTMENT", 0.025)
PROB_HI       = getattr(_inj, "_PROB_CLAMP_HI", 0.99)
PROB_LO       = getattr(_inj, "_PROB_CLAMP_LO", 0.01)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _p0(
    *,
    season_game_index: float = 0.5,
    season_game_index_available: bool = True,
    park_run_factor: float = 1.00,
    park_factor_available: bool = True,
    sp_fip_delta: float = 0.0,
    sp_fip_delta_available: bool = False,
) -> dict:
    """Build a minimal valid p0_features dict."""
    return {
        "feature_version": "phase48_p0_v1",
        "candidate_patch_created": False,
        "production_modified": False,
        "season_game_index": season_game_index,
        "season_game_index_available": season_game_index_available,
        "park_run_factor": park_run_factor,
        "park_factor_available": park_factor_available,
        "sp_fip_delta": sp_fip_delta,
        "sp_fip_delta_available": sp_fip_delta_available,
        "feature_audit_hash": "abc123" * 10,
        "audit_notes": {},
    }


def _adj(prob: float, **kw) -> AdjustmentResult:
    """Shorthand: apply adjustment with default neutral features + overrides."""
    return apply_p0_feature_adjustment(prob, _p0(**kw))


# ═══════════════════════════════════════════════════════════════════════════════
# § 1  TestHardRuleInvariants
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardRuleInvariants:
    """Hard rules that must NEVER change — see session memory for rationale."""

    def test_candidate_patch_created_module_constant_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_module_constant_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_feature_version_is_phase50(self):
        assert FEATURE_VERSION == "phase50_p0_injected_v1"

    def test_adjustment_result_candidate_patch_always_false(self):
        result = _adj(0.55)
        assert result.candidate_patch_created is False

    def test_adjustment_result_production_modified_always_false(self):
        result = _adj(0.55)
        assert result.production_modified is False

    def test_adjustment_result_preserves_original_prob(self):
        p = 0.6007
        result = apply_p0_feature_adjustment(p, _p0())
        assert result.original_model_home_prob == pytest.approx(p, abs=1e-6)


# ═══════════════════════════════════════════════════════════════════════════════
# § 2  TestAdjustmentCap
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdjustmentCap:
    """Total adjustment must never exceed ±0.025."""

    def test_normal_adjustment_within_cap(self):
        result = _adj(0.65, park_run_factor=1.12, park_factor_available=True,
                      season_game_index=0.10, season_game_index_available=True,
                      sp_fip_delta=0.0, sp_fip_delta_available=False)
        assert abs(result.capped_total_adjustment) <= MAX_TOTAL_ADJ + 1e-9

    def test_extreme_inputs_still_capped(self):
        """Even with extreme constructed values, total stays capped."""
        result = _adj(0.99, park_run_factor=1.50, park_factor_available=True,
                      season_game_index=0.01, season_game_index_available=True,
                      sp_fip_delta=5.0, sp_fip_delta_available=True)
        assert abs(result.capped_total_adjustment) <= MAX_TOTAL_ADJ + 1e-9

    def test_adjusted_prob_reflects_capped_not_raw_adjustment(self):
        """adjusted_prob must use capped_total_adjustment, not raw."""
        result = _adj(0.65, park_run_factor=1.12, park_factor_available=True,
                      season_game_index=0.05, season_game_index_available=True)
        expected = result.original_model_home_prob + result.capped_total_adjustment
        expected = max(PROB_LO, min(PROB_HI, expected))
        assert result.adjusted_model_home_prob == pytest.approx(expected, abs=1e-6)

    def test_cap_applied_flag_set_when_raw_exceeds_cap(self):
        """cap_applied should be True when raw exceeds limit."""
        # Force: early season shrink (pushes toward 0.5 from 0.99) → raw total large
        result = _adj(0.99, season_game_index=0.01, season_game_index_available=True,
                      park_run_factor=1.20, park_factor_available=True,
                      sp_fip_delta=3.0, sp_fip_delta_available=True)
        # raw_total should be large enough to hit cap
        if abs(result.raw_total_adjustment) > MAX_TOTAL_ADJ + 1e-9:
            assert result.cap_applied is True
        else:
            # If raw happens to be within cap for this case, check flag is False
            assert result.cap_applied is False

    def test_cap_applied_false_when_raw_within_limit(self):
        """With neutral inputs, cap_applied should be False."""
        result = _adj(0.50)  # neutral park, mid-season, no fip
        # Adjustment near zero — should not cap
        assert result.cap_applied is False

    def test_raw_vs_capped_relationship(self):
        """capped = clip(raw, -0.025, 0.025) always."""
        for p in [0.30, 0.50, 0.65, 0.80]:
            result = _adj(p, park_run_factor=1.15, park_factor_available=True,
                          season_game_index=0.05, season_game_index_available=True)
            expected_capped = max(-MAX_TOTAL_ADJ, min(MAX_TOTAL_ADJ, result.raw_total_adjustment))
            assert result.capped_total_adjustment == pytest.approx(expected_capped, abs=1e-9)


# ═══════════════════════════════════════════════════════════════════════════════
# § 3  TestProbClamp
# ═══════════════════════════════════════════════════════════════════════════════

class TestProbClamp:
    """adjusted_model_home_prob must always be in [0.01, 0.99]."""

    def test_normal_prob_not_clamped(self):
        result = _adj(0.55)
        assert PROB_LO <= result.adjusted_model_home_prob <= PROB_HI

    def test_very_low_base_prob_clamped_to_lo(self):
        """A very low base prob pushed negative should clamp to 0.01."""
        # Season shrink: (0.5 - 0.03) * 0.04 = positive → moves away from 0
        # Use sp_fip pushing away  (away SP much better → big negative)
        result = _adj(0.02, sp_fip_delta=-50.0, sp_fip_delta_available=True)
        assert result.adjusted_model_home_prob >= PROB_LO

    def test_very_high_base_prob_clamped_to_hi(self):
        result = _adj(0.98, sp_fip_delta=50.0, sp_fip_delta_available=True)
        assert result.adjusted_model_home_prob <= PROB_HI

    def test_prob_always_in_range_across_many_inputs(self):
        """Brute-force: 100 random-ish inputs must all stay in range."""
        import random
        rng = random.Random(42)
        for _ in range(100):
            p = rng.uniform(0.05, 0.95)
            prf = rng.uniform(0.85, 1.30)
            sgi = rng.uniform(0.0, 1.0)
            fip = rng.uniform(-5.0, 5.0)
            result = _adj(p, park_run_factor=prf, park_factor_available=True,
                          season_game_index=sgi, season_game_index_available=True,
                          sp_fip_delta=fip, sp_fip_delta_available=True)
            assert PROB_LO <= result.adjusted_model_home_prob <= PROB_HI

    def test_adjusted_prob_rounds_to_8_decimal_places(self):
        result = _adj(0.6007)
        # Should not be more precise than 8 dp (from round(..., 8))
        s = str(result.adjusted_model_home_prob)
        # Allow fewer than 8 dp due to trailing-zero removal
        if "." in s:
            decimals = len(s.split(".")[1])
            assert decimals <= 8

    def test_zero_base_prob_clamped(self):
        result = apply_p0_feature_adjustment(0.0, _p0())
        assert result.adjusted_model_home_prob >= PROB_LO

    def test_one_base_prob_clamped(self):
        result = apply_p0_feature_adjustment(1.0, _p0())
        assert result.adjusted_model_home_prob <= PROB_HI


# ═══════════════════════════════════════════════════════════════════════════════
# § 4  TestSeasonGameIndex
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeasonGameIndex:
    """F-004: early-season shrinks probability toward 0.5."""

    def test_early_season_shrinks_high_prob_toward_half(self):
        """High prob (0.80) in early season → adjusted < original."""
        result = _adj(0.80, season_game_index=0.05, season_game_index_available=True,
                      park_run_factor=1.00, park_factor_available=True)
        assert result.adjusted_model_home_prob < 0.80

    def test_early_season_shrinks_low_prob_toward_half(self):
        """Low prob (0.20) in early season → adjusted > original."""
        result = _adj(0.20, season_game_index=0.05, season_game_index_available=True,
                      park_run_factor=1.00, park_factor_available=True)
        assert result.adjusted_model_home_prob > 0.20

    def test_mid_season_no_season_adjustment(self):
        """season_game_index = 0.50 → season_index_adjustment = 0."""
        result = _adj(0.65, season_game_index=0.50, season_game_index_available=True,
                      park_factor_available=False)
        assert result.season_index_adjustment == pytest.approx(0.0, abs=1e-9)

    def test_late_season_no_season_adjustment(self):
        """season_game_index = 0.90 → season_index_adjustment = 0."""
        result = _adj(0.65, season_game_index=0.90, season_game_index_available=True,
                      park_factor_available=False)
        assert result.season_index_adjustment == pytest.approx(0.0, abs=1e-9)

    def test_unavailable_season_index_no_adjustment(self):
        """When season_game_index_available=False, no adjustment even if sgi=0.05."""
        result = _adj(0.80, season_game_index=0.05, season_game_index_available=False,
                      park_factor_available=False)
        assert result.season_index_adjustment == pytest.approx(0.0, abs=1e-9)

    def test_season_adj_proportional_to_distance_from_threshold(self):
        """Smaller sgi → larger shrink (more early-season uncertainty)."""
        result_a = _adj(0.70, season_game_index=0.05, season_game_index_available=True,
                        park_factor_available=False)
        result_b = _adj(0.70, season_game_index=0.15, season_game_index_available=True,
                        park_factor_available=False)
        # sgi=0.05 is farther below threshold → larger magnitude
        assert abs(result_a.season_index_adjustment) > abs(result_b.season_index_adjustment)

    def test_season_adj_listed_in_reasons_when_triggered(self):
        result = _adj(0.70, season_game_index=0.05, season_game_index_available=True,
                      park_factor_available=False)
        assert any("early_season" in r for r in result.adjustment_reason)


# ═══════════════════════════════════════════════════════════════════════════════
# § 5  TestParkRunFactor
# ═══════════════════════════════════════════════════════════════════════════════

class TestParkRunFactor:
    """F-002: hitter-friendly park discounts over-confident home prob."""

    def test_high_park_and_high_prob_gives_negative_adjustment(self):
        """park_run_factor=1.15, prob=0.75 → should produce negative park adjustment."""
        result = _adj(0.75, park_run_factor=1.15, park_factor_available=True,
                      season_game_index=0.50, season_game_index_available=True)
        assert result.park_run_adjustment < 0.0

    def test_medium_park_and_high_prob_gives_small_negative_adjustment(self):
        """park_run_factor=1.07, prob=0.70 → small negative park adjustment."""
        result = _adj(0.70, park_run_factor=1.07, park_factor_available=True,
                      season_game_index=0.50, season_game_index_available=True)
        assert result.park_run_adjustment < 0.0
        assert abs(result.park_run_adjustment) < 0.015  # within per-feature max

    def test_neutral_park_no_adjustment(self):
        """park_run_factor=1.00 → park_run_adjustment = 0."""
        result = _adj(0.70, park_run_factor=1.00, park_factor_available=True,
                      season_game_index=0.50, season_game_index_available=True)
        assert result.park_run_adjustment == pytest.approx(0.0, abs=1e-9)

    def test_high_park_low_prob_no_adjustment(self):
        """park_run_factor > threshold but prob <= 0.60 → no park adjustment."""
        result = _adj(0.50, park_run_factor=1.12, park_factor_available=True,
                      season_game_index=0.50, season_game_index_available=True)
        assert result.park_run_adjustment == pytest.approx(0.0, abs=1e-9)

    def test_park_unavailable_no_adjustment(self):
        """park_factor_available=False → park_run_adjustment = 0."""
        result = _adj(0.75, park_run_factor=1.20, park_factor_available=False,
                      season_game_index=0.50, season_game_index_available=True)
        assert result.park_run_adjustment == pytest.approx(0.0, abs=1e-9)

    def test_park_adjustment_in_reason_when_triggered(self):
        result = _adj(0.75, park_run_factor=1.15, park_factor_available=True,
                      season_game_index=0.50, season_game_index_available=True)
        assert any("park_factor" in r for r in result.adjustment_reason)

    def test_high_park_larger_than_medium_park_adjustment(self):
        """High park (>1.10) should produce larger abs adjustment than medium (1.05-1.10)."""
        p = 0.80
        result_high = _adj(p, park_run_factor=1.15, park_factor_available=True,
                           season_game_index=0.50, season_game_index_available=True)
        result_med  = _adj(p, park_run_factor=1.07, park_factor_available=True,
                           season_game_index=0.50, season_game_index_available=True)
        assert abs(result_high.park_run_adjustment) > abs(result_med.park_run_adjustment)


# ═══════════════════════════════════════════════════════════════════════════════
# § 6  TestSpFipDelta
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpFipDelta:
    """F-001: sp_fip_delta available/unavailable branch."""

    def test_unavailable_fip_gives_zero_adjustment(self):
        """sp_fip_delta_available=False → sp_fip_adjustment = 0."""
        result = _adj(0.55, sp_fip_delta=3.0, sp_fip_delta_available=False,
                      park_factor_available=False, season_game_index_available=False)
        assert result.sp_fip_adjustment == pytest.approx(0.0, abs=1e-9)

    def test_available_positive_fip_adjusts_upward(self):
        """Positive delta (home SP better) → positive sp_fip_adjustment."""
        result = _adj(0.55, sp_fip_delta=2.0, sp_fip_delta_available=True,
                      park_factor_available=False, season_game_index_available=False)
        assert result.sp_fip_adjustment > 0.0

    def test_available_negative_fip_adjusts_downward(self):
        """Negative delta (away SP better) → negative sp_fip_adjustment."""
        result = _adj(0.55, sp_fip_delta=-2.0, sp_fip_delta_available=True,
                      park_factor_available=False, season_game_index_available=False)
        assert result.sp_fip_adjustment < 0.0

    def test_zero_fip_delta_gives_zero_adjustment(self):
        """sp_fip_delta=0.0 → sp_fip_adjustment = 0."""
        result = _adj(0.55, sp_fip_delta=0.0, sp_fip_delta_available=True,
                      park_factor_available=False, season_game_index_available=False)
        assert result.sp_fip_adjustment == pytest.approx(0.0, abs=1e-9)

    def test_fip_adjustment_bounded_by_max_total_after_cap(self):
        """Large sp_fip_delta must not bypass total cap."""
        result = _adj(0.55, sp_fip_delta=100.0, sp_fip_delta_available=True,
                      park_factor_available=False, season_game_index_available=False)
        assert abs(result.capped_total_adjustment) <= MAX_TOTAL_ADJ + 1e-9

    def test_fip_available_reflected_in_components(self):
        """When available, sp_fip_delta should appear in adjustment_components."""
        result = _adj(0.55, sp_fip_delta=2.0, sp_fip_delta_available=True,
                      park_factor_available=False, season_game_index_available=False)
        assert result.adjustment_components.get("sp_fip_delta_available") is True


# ═══════════════════════════════════════════════════════════════════════════════
# § 7  TestLeakageGuard
# ═══════════════════════════════════════════════════════════════════════════════

class TestLeakageGuard:
    """Forbidden field detection — must raise ValueError if present."""

    def test_home_win_field_raises(self):
        p0 = _p0()
        p0["home_win"] = 1
        with pytest.raises(ValueError, match="home_win"):
            apply_p0_feature_adjustment(0.55, p0)

    def test_final_score_field_raises(self):
        p0 = _p0()
        p0["final_score"] = "5-3"
        with pytest.raises(ValueError, match="final_score"):
            apply_p0_feature_adjustment(0.55, p0)

    def test_result_field_raises(self):
        p0 = _p0()
        p0["result"] = "WIN"
        with pytest.raises(ValueError, match="result"):
            apply_p0_feature_adjustment(0.55, p0)

    def test_home_score_field_raises(self):
        p0 = _p0()
        p0["home_score"] = 5
        with pytest.raises(ValueError, match="home_score"):
            apply_p0_feature_adjustment(0.55, p0)

    def test_clean_features_no_raise(self):
        """Clean p0_features (no forbidden fields) should not raise."""
        result = apply_p0_feature_adjustment(0.55, _p0())
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# § 8  TestBuildPhase50Row
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildPhase50Row:
    """JSONL row structure produced by build_phase50_row()."""

    @pytest.fixture()
    def sample_row_and_adj(self):
        p48_row = {
            "schema_version": "phase39-v1",
            "game_id": "MLB2025_0001_FAKE",
            "game_date": "2025-04-01",
            "home_team": "NYY",
            "away_team": "BOS",
            "model_home_prob": 0.6007,
            "market_home_prob_no_vig": 0.55,
            "home_ml": "",
            "away_ml": "",
            "feature_version": "phase48_p0_v1",
            "p0_features": _p0(season_game_index=0.10, park_run_factor=1.06),
        }
        adj = apply_p0_feature_adjustment(0.6007, p48_row["p0_features"])
        row = build_phase50_row(p48_row, adj)
        return row, adj

    def test_feature_effect_mode_is_model_affecting(self, sample_row_and_adj):
        row, _ = sample_row_and_adj
        assert row["feature_effect_mode"] == "MODEL_AFFECTING"

    def test_feature_version_is_phase50(self, sample_row_and_adj):
        row, _ = sample_row_and_adj
        assert row["feature_version"] == FEATURE_VERSION

    def test_model_home_prob_is_adjusted(self, sample_row_and_adj):
        row, adj = sample_row_and_adj
        assert row["model_home_prob"] == pytest.approx(adj.adjusted_model_home_prob, abs=1e-8)

    def test_original_model_home_prob_preserved(self, sample_row_and_adj):
        row, adj = sample_row_and_adj
        assert row["original_model_home_prob"] == pytest.approx(adj.original_model_home_prob, abs=1e-8)

    def test_p0_feature_adjustment_block_present(self, sample_row_and_adj):
        row, _ = sample_row_and_adj
        assert "p0_feature_adjustment" in row
        block = row["p0_feature_adjustment"]
        assert block["candidate_patch_created"] is False
        assert block["production_modified"] is False

    def test_candidate_patch_and_production_flags(self, sample_row_and_adj):
        row, _ = sample_row_and_adj
        assert row["candidate_patch_created"] is False
        assert row["production_modified"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# § 9  TestBatchInjection
# ═══════════════════════════════════════════════════════════════════════════════

class TestBatchInjection:
    """run_batch_injection() summary statistics."""

    @pytest.fixture()
    def batch_rows(self):
        """10 rows: mix of early season, high park, neutral."""
        rows = []
        for i in range(10):
            prob = 0.50 + i * 0.03
            prf = 1.00 + i * 0.01
            sgi = 0.05 + i * 0.10
            rows.append({
                "game_id": f"FAKE_{i:04d}",
                "game_date": "2025-04-01",
                "model_home_prob": prob,
                "home_win": None,  # simulate missing label (allowed in row, not in p0)
                "p0_features": _p0(
                    season_game_index=sgi,
                    season_game_index_available=True,
                    park_run_factor=prf,
                    park_factor_available=True,
                    sp_fip_delta=0.0,
                    sp_fip_delta_available=False,
                ),
            })
        return rows

    def test_batch_returns_correct_row_count(self, batch_rows):
        phase50_rows, summary = run_batch_injection(batch_rows)
        assert len(phase50_rows) == 10

    def test_summary_rows_total(self, batch_rows):
        _, summary = run_batch_injection(batch_rows)
        assert summary.rows_total == 10

    def test_summary_rows_adjusted_plus_unchanged_equals_total(self, batch_rows):
        _, summary = run_batch_injection(batch_rows)
        assert summary.rows_adjusted + summary.rows_unchanged == summary.rows_total

    def test_summary_candidate_patch_false(self, batch_rows):
        _, summary = run_batch_injection(batch_rows)
        assert summary.candidate_patch_created is False

    def test_summary_production_modified_false(self, batch_rows):
        _, summary = run_batch_injection(batch_rows)
        assert summary.production_modified is False

    def test_summary_feature_version_is_phase50(self, batch_rows):
        _, summary = run_batch_injection(batch_rows)
        assert summary.feature_version == FEATURE_VERSION

    def test_summary_correlation_near_one(self, batch_rows):
        """Small adjustments → correlation with original should be very high."""
        _, summary = run_batch_injection(batch_rows)
        assert summary.original_adjusted_correlation > 0.95


# ═══════════════════════════════════════════════════════════════════════════════
# § 10  TestPhase50Script
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase50Script:
    """Integration test: run() public API from run_phase50_p0_feature_injection.py."""

    @pytest.fixture(scope="class")
    def phase50_result(self, tmp_path_factory):
        """Run the full pipeline with real Phase48 JSONL and temp output."""
        from scripts.run_phase50_p0_feature_injection import run

        _PHASE48 = (
            Path(__file__).resolve().parent.parent
            / "data" / "mlb_2025" / "derived"
            / "mlb_2025_per_game_predictions_phase48_p0_v1.jsonl"
        )
        _BASELINE = (
            Path(__file__).resolve().parent.parent
            / "data" / "mlb_2025" / "derived"
            / "mlb_2025_per_game_predictions.jsonl"
        )

        if not _PHASE48.exists():
            pytest.skip("Phase48 JSONL not available — skip integration test")
        if not _BASELINE.exists():
            pytest.skip("Baseline JSONL not available — skip integration test")

        tmp = tmp_path_factory.mktemp("phase50_out")
        out = tmp / "phase50_test_out.jsonl"
        return run(phase48_path=_PHASE48, output_path=out, baseline_path=_BASELINE)

    def test_rows_written_positive(self, phase50_result):
        assert phase50_result["rows_total"] > 0

    def test_feature_effect_mode_is_model_affecting(self, phase50_result):
        assert phase50_result["feature_effect_mode"] == "MODEL_AFFECTING"

    def test_candidate_patch_false(self, phase50_result):
        assert phase50_result["candidate_patch_created"] is False

    def test_production_modified_false(self, phase50_result):
        assert phase50_result["production_modified"] is False

    def test_model_home_prob_differs_from_baseline(self, phase50_result):
        """mean_abs_adjustment > 0 → model_home_prob truly differs."""
        assert phase50_result["mean_abs_adjustment"] > 0.0

    def test_gate_recommendation_is_valid(self, phase50_result):
        valid_gates = {
            "FEATURE_INJECTION_REQUIRED",
            "FEATURE_REPAIR_EFFECTIVE_PAPER_ONLY",
            "FEATURE_REPAIR_NOT_EFFECTIVE",
            "COLLECT_MORE_DATA",
        }
        assert phase50_result["gate_recommendation"] in valid_gates
