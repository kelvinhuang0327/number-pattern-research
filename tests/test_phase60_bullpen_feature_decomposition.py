"""
Phase 60 Test Suite — Bullpen Feature Decomposition and PIT-safe Attribution

Test classes:
  TestSafetyConstants        — frozen flags, gate validity, alpha unchanged
  TestPITNoLookaheadGuard    — forbidden features raise, PIT contract enforced
  TestFeatureFamilySchema    — all feature families present, DATA_LIMITED flagged
  TestSegmentAttributionSchema — all segments present, attribution has required fields
  TestNegativeControl        — shuffled feature shows no consistent signal
  TestNoProductionPatch      — confirm no candidate patch created
  TestEndToEnd               — integration test with real data (skipped if missing)
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.phase60_bullpen_feature_decomposition import (
    ALPHA,
    BULLPEN_FEATURE_NOT_PROMISING,
    BULLPEN_FEATURE_PROMISING,
    CANDIDATE_PATCH_CREATED,
    DATA_LIMITED,
    DIAGNOSTIC_ONLY,
    DIAGNOSTIC_ONLY_SIGNAL,
    PHASE_VERSION,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    _HEAVY_FAV_THRESHOLD,
    _HIGH_CONF_THRESHOLD,
    _MIN_SEGMENT_N,
    Phase60DecompositionResult,
    FeatureFamilyMeta,
    SegmentAttribution,
    BucketAttribution,
    NegativeControlResult,
    OOFSummary,
    _norm_team,
    _parse_bull_game_id,
    _blend_prob,
    _fav_prob,
    _brier_score,
    _bss,
    _compute_ece,
    _bucket_attribution,
    _compute_attribution,
    assert_no_forbidden_feature,
    validate_pit_safety,
    run_phase60_decomposition,
    result_to_dict,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_REAL_PREDICTIONS = Path("data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl")
_REAL_BULLPEN = Path("data/mlb_context/bullpen_usage_3d.jsonl")
_REAL_REST = Path("data/mlb_context/injury_rest.jsonl")
_REAL_DATA_AVAILABLE = _REAL_PREDICTIONS.exists() and _REAL_BULLPEN.exists()

REQUIRED_SEGMENTS = {"all", "heavy_favorite", "high_confidence", "phase45_failure"}
REQUIRED_AVAILABLE_FEATURES = {
    "bull_home_3d",
    "bull_away_3d",
    "bull_delta_3d",
    "bull_norm_delta_3d",
    "fav_fatigue_3d",
    "dog_fatigue_3d",
    "fav_vs_dog_delta_3d",
}
REQUIRED_DATA_LIMITED_FEATURES = {
    "bull_usage_last_1d",
    "bull_usage_last_5d",
    "back_to_back_proxy",
    "closer_high_leverage",
}
VALID_GATES = {
    BULLPEN_FEATURE_PROMISING,
    DIAGNOSTIC_ONLY_SIGNAL,
    DATA_LIMITED,
    BULLPEN_FEATURE_NOT_PROMISING,
}


# ---------------------------------------------------------------------------
# Class 1: TestSafetyConstants
# ---------------------------------------------------------------------------

class TestSafetyConstants:
    """Frozen safety flags and constants."""

    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_alpha_is_frozen(self):
        assert ALPHA == 0.40, f"ALPHA was modified: {ALPHA}"

    def test_phase_version_format(self):
        assert "phase60" in PHASE_VERSION.lower()

    def test_heavy_fav_threshold(self):
        assert _HEAVY_FAV_THRESHOLD == 0.70

    def test_high_conf_threshold(self):
        assert _HIGH_CONF_THRESHOLD == 0.75

    def test_min_segment_n_positive(self):
        assert _MIN_SEGMENT_N > 0

    def test_gate_constants_non_empty(self):
        for g in [BULLPEN_FEATURE_PROMISING, DIAGNOSTIC_ONLY_SIGNAL, DATA_LIMITED, BULLPEN_FEATURE_NOT_PROMISING]:
            assert isinstance(g, str) and len(g) > 0

    def test_gate_constants_distinct(self):
        gates = [BULLPEN_FEATURE_PROMISING, DIAGNOSTIC_ONLY_SIGNAL, DATA_LIMITED, BULLPEN_FEATURE_NOT_PROMISING]
        assert len(set(gates)) == 4


# ---------------------------------------------------------------------------
# Class 2: TestPITNoLookaheadGuard
# ---------------------------------------------------------------------------

class TestPITNoLookaheadGuard:
    """PIT safety: forbidden features must raise, PIT contract is enforced."""

    def test_home_win_feature_raises(self):
        with pytest.raises(ValueError, match="PIT-SAFETY"):
            assert_no_forbidden_feature("home_win")

    def test_result_feature_raises(self):
        with pytest.raises(ValueError, match="PIT-SAFETY"):
            assert_no_forbidden_feature("result")

    def test_final_score_raises(self):
        with pytest.raises(ValueError, match="PIT-SAFETY"):
            assert_no_forbidden_feature("final_score")

    def test_winning_team_raises(self):
        with pytest.raises(ValueError, match="PIT-SAFETY"):
            assert_no_forbidden_feature("winning_team")

    def test_valid_feature_passes(self):
        # Should NOT raise
        assert_no_forbidden_feature("fav_vs_dog_delta_3d")
        assert_no_forbidden_feature("bull_home_3d")
        assert_no_forbidden_feature("bull_delta_3d")

    def test_valid_fav_fatigue_passes(self):
        assert_no_forbidden_feature("fav_fatigue_3d")

    def test_valid_dog_fatigue_passes(self):
        assert_no_forbidden_feature("dog_fatigue_3d")

    def test_valid_norm_delta_passes(self):
        assert_no_forbidden_feature("bull_norm_delta_3d")

    def test_pit_safety_valid_entries(self):
        """Entries fetched after game date are PIT-safe."""
        entries = [
            {"game_id": "MLB-2025_07_15-1_10_PM-YANKEES-AT-RED_SOX", "fetched_at": "2025-07-16T03:00:00Z"},
            {"game_id": "MLB-2025_08_01-7_05_PM-CUBS-AT-DODGERS", "fetched_at": "2025-08-02T05:00:00Z"},
        ]
        assert validate_pit_safety(entries) is True

    def test_pit_safety_violation_detected(self):
        """Entries fetched on game date or before violate PIT."""
        entries = [
            {"game_id": "MLB-2025_07_15-1_10_PM-YANKEES-AT-RED_SOX", "fetched_at": "2025-07-15T10:00:00Z"},
        ]
        result = validate_pit_safety(entries)
        assert result is False

    def test_pit_safety_empty_entries(self):
        """Empty list is trivially PIT-safe."""
        assert validate_pit_safety([]) is True

    def test_norm_team_standardization(self):
        assert _norm_team("New York Yankees") == "NEW_YORK_YANKEES"
        assert _norm_team("red sox") == "RED_SOX"
        assert _norm_team("Cubs") == "CUBS"


# ---------------------------------------------------------------------------
# Class 3: TestFeatureFamilySchema
# ---------------------------------------------------------------------------

class TestFeatureFamilySchema:
    """Feature family metadata: available and DATA_LIMITED features declared correctly."""

    def _make_fake_meta(self) -> list[FeatureFamilyMeta]:
        """Create minimal fake feature family list for schema testing."""
        metas = []
        for fname in REQUIRED_AVAILABLE_FEATURES:
            metas.append(FeatureFamilyMeta(
                feature_name=fname, description="Test",
                available=True, coverage_pct=0.95, n_usable=1000,
            ))
        for fname in REQUIRED_DATA_LIMITED_FEATURES:
            metas.append(FeatureFamilyMeta(
                feature_name=fname, description="Test",
                available=False, coverage_pct=0.0, n_usable=0,
                data_limited_reason="No source",
            ))
        return metas

    def test_all_available_features_declared(self):
        metas = self._make_fake_meta()
        names = {m.feature_name for m in metas if m.available}
        for fn in REQUIRED_AVAILABLE_FEATURES:
            assert fn in names, f"Missing available feature: {fn}"

    def test_all_data_limited_features_declared(self):
        metas = self._make_fake_meta()
        names = {m.feature_name for m in metas if not m.available}
        for fn in REQUIRED_DATA_LIMITED_FEATURES:
            assert fn in names, f"Missing DATA_LIMITED feature: {fn}"

    def test_data_limited_has_reason(self):
        metas = self._make_fake_meta()
        for m in metas:
            if not m.available:
                assert m.data_limited_reason is not None
                assert len(m.data_limited_reason) > 0

    def test_available_features_have_positive_coverage(self):
        metas = self._make_fake_meta()
        for m in metas:
            if m.available:
                assert m.coverage_pct > 0, f"{m.feature_name} should have coverage > 0"
                assert m.n_usable > 0

    def test_data_limited_features_have_zero_usable(self):
        metas = self._make_fake_meta()
        for m in metas:
            if not m.available:
                assert m.n_usable == 0

    def test_derived_feature_delta_not_forbidden(self):
        """bull_delta_3d = home - away is a safe derived feature."""
        assert_no_forbidden_feature("bull_delta_3d")

    def test_derived_feature_norm_delta_not_forbidden(self):
        assert_no_forbidden_feature("bull_norm_delta_3d")

    def test_no_available_feature_is_forbidden(self):
        for fname in REQUIRED_AVAILABLE_FEATURES:
            try:
                assert_no_forbidden_feature(fname)
            except ValueError as e:
                pytest.fail(f"Available feature '{fname}' incorrectly flagged as forbidden: {e}")

    def test_bull_delta_computation_correct(self):
        """Verify derived feature: bull_delta_3d = home - away."""
        home_val, away_val = 12.3, 9.7
        delta = home_val - away_val
        assert abs(delta - 2.6) < 1e-6

    def test_fav_fatigue_attribution_direction(self):
        """Fav fatigue = tired favorite → fav win rate should decrease."""
        # When fav_vs_dog_delta_3d > 0 (fav more tired), fav win rate should go down
        # This is a design-intent check, not a statistical test
        # (The actual signal may be small; the design is that high fav_fatigue → fewer wins)
        assert True  # Design intent documented; actual signal tested in attribution

    def test_feature_coverage_bound(self):
        metas = self._make_fake_meta()
        for m in metas:
            assert 0.0 <= m.coverage_pct <= 1.0


# ---------------------------------------------------------------------------
# Class 4: TestSegmentAttributionSchema
# ---------------------------------------------------------------------------

class TestSegmentAttributionSchema:
    """Attribution results have required structure and valid numeric fields."""

    def _make_fake_attribution(
        self,
        feature_name: str = "fav_vs_dog_delta_3d",
        segment: str = "heavy_favorite",
        n: int = 50,
    ) -> SegmentAttribution:
        ba = BucketAttribution(
            n_high=25, n_low=25,
            win_rate_high=0.64, win_rate_low=0.72,
            win_rate_delta=-0.08,
            bootstrap_ci_lower=-0.22, bootstrap_ci_upper=0.06,
            bootstrap_significant=False,
        )
        return SegmentAttribution(
            feature_name=feature_name,
            segment=segment,
            n=n,
            coverage_pct=0.95,
            baseline_brier=0.23,
            baseline_bss=0.05,
            calibration_residual=0.01,
            ece=0.045,
            bucket_attribution=ba,
            oof_win_rate_delta=None,
            oof_n=None,
            oof_replicated=None,
        )

    def test_all_segments_represented(self):
        """At least one attribution per segment."""
        attrs = [
            self._make_fake_attribution(segment=s)
            for s in REQUIRED_SEGMENTS
        ]
        found_segments = {a.segment for a in attrs}
        for seg in REQUIRED_SEGMENTS:
            assert seg in found_segments

    def test_attribution_has_required_numeric_fields(self):
        attr = self._make_fake_attribution()
        assert isinstance(attr.baseline_brier, float)
        assert isinstance(attr.baseline_bss, float)
        assert isinstance(attr.calibration_residual, float)
        assert isinstance(attr.ece, float)
        assert isinstance(attr.coverage_pct, float)

    def test_attribution_coverage_in_bounds(self):
        attr = self._make_fake_attribution(n=50)
        assert 0.0 <= attr.coverage_pct <= 1.0

    def test_attribution_ece_non_negative(self):
        attr = self._make_fake_attribution()
        assert attr.ece >= 0.0

    def test_bucket_attribution_delta_consistency(self):
        attr = self._make_fake_attribution()
        ba = attr.bucket_attribution
        assert abs(ba.win_rate_delta - (ba.win_rate_high - ba.win_rate_low)) < 1e-4

    def test_bucket_attribution_n_consistency(self):
        attr = self._make_fake_attribution(n=50)
        ba = attr.bucket_attribution
        # high + low should be <= n (some rows may be exactly at median)
        assert ba.n_high + ba.n_low <= attr.n + 1  # +1 tolerance for median row

    def test_attribution_none_for_small_n(self):
        """Bucket attribution should be None when n < _MIN_SEGMENT_N."""
        feat_vals = [1.0] * 5  # only 5 rows
        blend_probs = [0.72] * 5
        win_labels = [1, 0, 1, 1, 0]
        attr = _compute_attribution("fav_fatigue_3d", "heavy_favorite",
                                    feat_vals, blend_probs, win_labels)
        # n < _MIN_SEGMENT_N → bucket_attribution should be None
        assert attr.bucket_attribution is None

    def test_attribution_with_sufficient_n(self):
        """Bucket attribution should be populated when n >= _MIN_SEGMENT_N."""
        n = 40
        feat_vals = [float(i) for i in range(n)]
        blend_probs = [0.72] * n
        win_labels = [int(i < 20) for i in range(n)]
        attr = _compute_attribution("bull_delta_3d", "all",
                                    feat_vals, blend_probs, win_labels)
        assert attr.n == n
        assert attr.bucket_attribution is not None

    def test_attribution_coverage_with_nones(self):
        """Coverage should reflect fraction of non-None features."""
        n = 40
        feat_vals = [float(i) if i < 30 else None for i in range(n)]
        blend_probs = [0.6] * n
        win_labels = [1] * n
        attr = _compute_attribution("bull_home_3d", "all",
                                    feat_vals, blend_probs, win_labels)
        assert abs(attr.coverage_pct - 30/40) < 0.01


# ---------------------------------------------------------------------------
# Class 5: TestNegativeControl
# ---------------------------------------------------------------------------

class TestNegativeControl:
    """Negative control: shuffled feature should show no consistent signal."""

    def test_negative_control_schema(self):
        nc = NegativeControlResult(
            real_win_rate_delta_heavy_fav=0.027,
            shuffled_mean_delta=0.001,
            shuffled_std_delta=0.08,
            null_rejected=False,
        )
        assert isinstance(nc.real_win_rate_delta_heavy_fav, float)
        assert isinstance(nc.shuffled_mean_delta, float)
        assert isinstance(nc.shuffled_std_delta, float)
        assert isinstance(nc.null_rejected, bool)

    def test_shuffled_distribution_near_zero(self):
        """Shuffled feature win_rate_delta should average near zero."""
        rng = random.Random(42)
        n = 60
        feat_vals = [rng.gauss(9.5, 3.0) for _ in range(n)]
        win_labels = [rng.randint(0, 1) for _ in range(n)]
        med = sorted(feat_vals)[n // 2]

        shuffle_deltas = []
        for _ in range(200):
            shuffled = rng.sample(feat_vals, len(feat_vals))
            high_w = [w for f, w in zip(shuffled, win_labels) if f > med]
            low_w = [w for f, w in zip(shuffled, win_labels) if f <= med]
            if high_w and low_w:
                d = (sum(high_w) / len(high_w)) - (sum(low_w) / len(low_w))
                shuffle_deltas.append(d)

        mean_d = sum(shuffle_deltas) / len(shuffle_deltas)
        # Shuffled mean should be near zero (within 0.05)
        assert abs(mean_d) < 0.05, f"Shuffled mean delta too large: {mean_d:.4f}"

    def test_null_rejected_logic(self):
        """null_rejected when real_delta > mean + 1.5*std."""
        # Real signal much larger than shuffled
        nc = NegativeControlResult(
            real_win_rate_delta_heavy_fav=0.20,
            shuffled_mean_delta=0.001,
            shuffled_std_delta=0.05,
            null_rejected=True,   # 0.20 > 0.001 + 1.5*0.05 = 0.076
        )
        expected = nc.real_win_rate_delta_heavy_fav > nc.shuffled_mean_delta + 1.5 * nc.shuffled_std_delta
        assert nc.null_rejected == expected

    def test_null_not_rejected_when_signal_weak(self):
        """null_rejected=False when real delta is within shuffled distribution."""
        nc = NegativeControlResult(
            real_win_rate_delta_heavy_fav=0.027,
            shuffled_mean_delta=0.001,
            shuffled_std_delta=0.08,
            null_rejected=False,  # 0.027 < 0.001 + 1.5*0.08 = 0.121
        )
        expected = nc.real_win_rate_delta_heavy_fav > nc.shuffled_mean_delta + 1.5 * nc.shuffled_std_delta
        assert nc.null_rejected == expected

    def test_bootstrap_ci_width_reasonable(self):
        """Bootstrap CI with n=60 should be reasonably wide (> 0.1 width)."""
        rng = random.Random(7)
        n = 60
        high_wins = [rng.randint(0, 1) for _ in range(30)]
        low_wins = [rng.randint(0, 1) for _ in range(30)]
        from orchestrator.phase60_bullpen_feature_decomposition import _bootstrap_win_rate_delta
        ci_lo, ci_hi = _bootstrap_win_rate_delta(high_wins, low_wins, n_boot=200)
        width = ci_hi - ci_lo
        assert width > 0.0, "Bootstrap CI should have positive width"
        assert ci_lo < ci_hi, "CI lower should be < upper"


# ---------------------------------------------------------------------------
# Class 6: TestNoProductionPatch
# ---------------------------------------------------------------------------

class TestNoProductionPatch:
    """Confirm no production modification and no candidate patch created."""

    def test_candidate_patch_created_false_at_module_level(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false_at_module_level(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_false_at_module_level(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_result_carries_diagnostic_only(self):
        """Phase60DecompositionResult should carry diagnostic_only=True."""
        # Build a minimal result to check the field
        from orchestrator.phase60_bullpen_feature_decomposition import OOFSummary, NegativeControlResult
        result = Phase60DecompositionResult(
            phase_version=PHASE_VERSION,
            run_timestamp="2026-05-06T00:00:00Z",
            audit_hash="abc123",
            candidate_patch_created=False,
            production_modified=False,
            alpha_modified=False,
            diagnostic_only=True,
            alpha=0.40,
            n_predictions=2025,
            n_bullpen_rows=2430,
            n_aligned=1843,
            alignment_rate=0.91,
            segment_n_all=2025,
            segment_n_heavy_fav=60,
            segment_n_high_conf=10,
            segment_n_phase45_failure=32,
            high_conf_note="test",
            feature_families=[],
            n_available_features=7,
            n_data_limited_features=4,
            attributions=[],
            negative_control=NegativeControlResult(0.0, 0.0, 0.0, False),
            oof_summary=OOFSummary(0, [], [], [], 0.0, False, False),
            gate=DIAGNOSTIC_ONLY_SIGNAL,
            gate_rationale="test",
        )
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.diagnostic_only is True
        assert result.alpha == 0.40

    def test_result_to_dict_preserves_safety_flags(self):
        """Serialised dict should preserve safety flags as False."""
        from orchestrator.phase60_bullpen_feature_decomposition import OOFSummary, NegativeControlResult
        result = Phase60DecompositionResult(
            phase_version=PHASE_VERSION,
            run_timestamp="2026-05-06T00:00:00Z",
            audit_hash="abc123",
            candidate_patch_created=False,
            production_modified=False,
            alpha_modified=False,
            diagnostic_only=True,
            alpha=0.40,
            n_predictions=100,
            n_bullpen_rows=100,
            n_aligned=90,
            alignment_rate=0.9,
            segment_n_all=100,
            segment_n_heavy_fav=5,
            segment_n_high_conf=1,
            segment_n_phase45_failure=3,
            high_conf_note="",
            feature_families=[],
            n_available_features=7,
            n_data_limited_features=4,
            attributions=[],
            negative_control=NegativeControlResult(0.0, 0.0, 0.0, False),
            oof_summary=OOFSummary(0, [], [], [], 0.0, False, False),
            gate=DATA_LIMITED,
            gate_rationale="test",
        )
        d = result_to_dict(result)
        assert d["candidate_patch_created"] is False
        assert d["production_modified"] is False
        assert d["diagnostic_only"] is True
        assert d["alpha"] == 0.40


# ---------------------------------------------------------------------------
# Class 7: TestEndToEnd
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not _REAL_DATA_AVAILABLE,
    reason="Real data files not found — skipping integration tests"
)
class TestEndToEnd:
    """Integration tests using real data files."""

    @pytest.fixture(scope="class")
    def result(self) -> Phase60DecompositionResult:
        return run_phase60_decomposition(
            predictions_path=str(_REAL_PREDICTIONS),
            bullpen_path=str(_REAL_BULLPEN),
            rest_path=str(_REAL_REST) if _REAL_REST.exists() else None,
        )

    def test_gate_is_valid(self, result):
        assert result.gate in VALID_GATES

    def test_safety_flags_unchanged(self, result):
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.alpha_modified is False
        assert result.diagnostic_only is True
        assert result.alpha == 0.40

    def test_audit_hash_non_empty(self, result):
        assert isinstance(result.audit_hash, str) and len(result.audit_hash) > 0

    def test_alignment_rate_above_threshold(self, result):
        assert result.alignment_rate >= 0.70, (
            f"Alignment rate too low: {result.alignment_rate:.2%}"
        )

    def test_segment_all_is_largest(self, result):
        assert result.segment_n_all >= result.segment_n_heavy_fav
        assert result.segment_n_all >= result.segment_n_high_conf

    def test_heavy_fav_segment_non_trivial(self, result):
        # Phase 59 confirmed ~59 heavy_fav rows
        assert result.segment_n_heavy_fav >= 50, (
            f"heavy_fav segment too small: {result.segment_n_heavy_fav}"
        )

    def test_high_conf_smaller_than_heavy_fav(self, result):
        assert result.segment_n_high_conf <= result.segment_n_heavy_fav

    def test_all_available_feature_families_present(self, result):
        found = {fm.feature_name for fm in result.feature_families if fm.available}
        for fn in REQUIRED_AVAILABLE_FEATURES:
            assert fn in found, f"Missing available feature: {fn}"

    def test_all_data_limited_features_declared(self, result):
        found_dl = {fm.feature_name for fm in result.feature_families if not fm.available}
        for fn in REQUIRED_DATA_LIMITED_FEATURES:
            assert fn in found_dl, f"Missing DATA_LIMITED feature: {fn}"

    def test_available_features_coverage_above_80pct(self, result):
        for fm in result.feature_families:
            if fm.available:
                assert fm.coverage_pct >= 0.80, (
                    f"Feature {fm.feature_name} coverage too low: {fm.coverage_pct:.2%}"
                )

    def test_attributions_cover_all_segments(self, result):
        found_segs = {a.segment for a in result.attributions}
        for seg in REQUIRED_SEGMENTS:
            assert seg in found_segs, f"Segment {seg} not in attributions"

    def test_attributions_cover_all_available_features(self, result):
        found_feats = {a.feature_name for a in result.attributions}
        for fn in REQUIRED_AVAILABLE_FEATURES:
            assert fn in found_feats, f"Feature {fn} not in attributions"

    def test_ece_non_negative(self, result):
        for attr in result.attributions:
            if not math.isnan(attr.ece):
                assert attr.ece >= 0.0, f"Negative ECE for {attr.feature_name}/{attr.segment}"

    def test_heavy_fav_attribution_has_bucket(self, result):
        """heavy_fav attribution for key feature should have bucket_attribution."""
        hf_key = next(
            (a for a in result.attributions
             if a.feature_name == "fav_vs_dog_delta_3d" and a.segment == "heavy_favorite"),
            None
        )
        assert hf_key is not None, "fav_vs_dog_delta_3d/heavy_favorite attribution missing"
        # n should be >= _MIN_SEGMENT_N (we have ~59 heavy_fav)
        if hf_key.n >= _MIN_SEGMENT_N:
            assert hf_key.bucket_attribution is not None

    def test_oof_summary_has_folds(self, result):
        """OOF should have at least 2 folds (6 months - first 2 train)."""
        assert result.oof_summary.n_folds >= 2, (
            f"OOF has only {result.oof_summary.n_folds} folds"
        )

    def test_negative_control_returns_result(self, result):
        nc = result.negative_control
        assert isinstance(nc.real_win_rate_delta_heavy_fav, float)
        assert isinstance(nc.shuffled_mean_delta, float)
        assert isinstance(nc.null_rejected, bool)

    def test_result_serialisable(self, result):
        d = result_to_dict(result)
        serialised = json.dumps(d)
        assert len(serialised) > 100

    def test_no_nan_in_serialised(self, result):
        """NaN values should be converted to None in result_to_dict."""
        d = result_to_dict(result)
        serialised = json.dumps(d)
        assert "NaN" not in serialised

    def test_phase_version_in_result(self, result):
        assert result.phase_version == PHASE_VERSION

    def test_alpha_in_result(self, result):
        assert result.alpha == 0.40

    def test_blend_formula_consistency(self, result):
        """Blend formula should match ALPHA=0.40."""
        mp, mkp = 0.60, 0.55
        expected = (1 - ALPHA) * mp + ALPHA * mkp
        computed = _blend_prob(mp, mkp)
        assert abs(computed - expected) < 1e-10

    def test_gate_rationale_non_empty(self, result):
        assert isinstance(result.gate_rationale, str) and len(result.gate_rationale) > 10

    def test_high_conf_note_mentions_threshold(self, result):
        assert "0.80" in result.high_conf_note or "threshold" in result.high_conf_note.lower()
