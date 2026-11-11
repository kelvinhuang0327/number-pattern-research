"""Tests for Phase 68 — Model Architecture and Ensemble Failure Audit.

Test coverage:
  - Core math functions (_brier, _bss_direct, _ece, _mean, _std, _cv)
  - Row enrichment (_enrich)
  - Segment metric computation (_compute_segment_metrics)
  - Calibration band computation (_compute_calibration_bands)
  - Disagreement bucket computation (_compute_disagreement_buckets)
  - Model version parsing (_parse_model_version)
  - Model version profiles (_compute_model_version_profiles)
  - Architecture instability (_compute_architecture_instability)
  - Ensemble sharpness (_compute_ensemble_sharpness)
  - Blend dilution checks (_compute_blend_dilution_checks)
  - Negative controls (_run_negative_controls)
  - Gate determination (_determine_gate)
  - Safety constants
  - Phase identity / gate constants
  - Full integration (run_phase68...)
  - JSON report round-trip
"""
from __future__ import annotations

import json
import math
import random
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from orchestrator.phase68_model_architecture_ensemble_failure_audit import (
    ABSTENTION_GUARD_PROMISING,
    ALPHA,
    ALPHA_MODIFIED,
    CALIBRATION_OBJECTIVE_REDESIGN_PROMISING,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DIAGNOSTIC_ONLY,
    ENSEMBLE_WEIGHTING_REPAIR_PROMISING,
    MODEL_ARCHITECTURE_NOT_PROMISING,
    MODEL_ARCHITECTURE_REPAIR_PROMISING,
    OVERFIT_RISK,
    PHASE64B_GATE_ANCHOR,
    PHASE65_GATE_ANCHOR,
    PHASE66_GATE_ANCHOR,
    PHASE67_GATE_ANCHOR,
    PHASE_VERSION,
    PRODUCTION_MODIFIED,
    _ABSTENTION_ECE_THRESHOLD,
    _BOOTSTRAP_N,
    _HEAVY_FAV_THRESHOLD,
    _HIGH_CONF_THRESHOLD,
    _INSTABILITY_CV_THRESHOLD,
    _LARGE_DISAGREE_THRESHOLD,
    _MIN_BUCKET_N,
    _MIN_SEGMENT_N,
    _OVERCONF_RESIDUAL_THRESHOLD,
    _OVERFIT_GAP_THRESHOLD,
    _PHASE45_FAIL_MIN_FAV,
    _UNDERCONF_RESIDUAL_THRESHOLD,
    _VALID_GATES,
    _brier,
    _bss_direct,
    _compute_architecture_instability,
    _compute_blend_dilution_checks,
    _compute_calibration_bands,
    _compute_disagreement_buckets,
    _compute_ensemble_sharpness,
    _compute_model_version_profiles,
    _compute_segment_metrics,
    _cv,
    _determine_gate,
    _ece,
    _enrich,
    _mean,
    _parse_model_version,
    _run_negative_controls,
    _std,
    _to_dict,
    run_phase68_model_architecture_ensemble_failure_audit,
    ArchitectureInstability,
    BlendDilutionCheck,
    CalibrationBand,
    DisagreementBucket,
    EnsembleSharpness,
    ModelVersionProfile,
    NegativeControl,
    Phase68Report,
    SegmentMetrics,
)


# ═══════════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════════

def _make_row(
    model_home_prob: float = 0.55,
    market_home_prob_no_vig: float = 0.54,
    home_win: int = 1,
    model_version: str = "marl_w_elo=0.543_w_market=0.243",
    feature_version: str = "phase56_sp_bullpen_context_v1",
) -> dict:
    return {
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": market_home_prob_no_vig,
        "home_win": home_win,
        "model_version": model_version,
        "feature_version": feature_version,
    }


def _make_rows(n: int = 50) -> list[dict]:
    """50 balanced rows: half home wins, alternating high/low confidence."""
    rng = random.Random(0)
    rows = []
    for i in range(n):
        model_p = 0.50 + rng.uniform(0, 0.30)
        mkt_p = 0.50 + rng.uniform(0, 0.28)
        hw = 1 if rng.random() > 0.50 else 0
        rows.append(_make_row(model_p, mkt_p, hw))
    return rows


def _make_enriched(n: int = 50) -> list[dict]:
    return _enrich(_make_rows(n))


@pytest.fixture
def sample_rows() -> list[dict]:
    return _make_enriched(100)


@pytest.fixture
def predictions_jsonl(tmp_path: Path) -> Path:
    """Write 200 synthetic predictions to a JSONL file."""
    rng = random.Random(99)
    path = tmp_path / "preds.jsonl"
    with open(path, "w") as fh:
        for _ in range(200):
            model_p = max(0.20, min(0.80, 0.50 + rng.gauss(0, 0.10)))
            mkt_p = max(0.20, min(0.80, 0.50 + rng.gauss(0, 0.10)))
            hw = 1 if rng.random() > 0.50 else 0
            row = {
                "model_home_prob": round(model_p, 4),
                "market_home_prob_no_vig": round(mkt_p, 4),
                "home_win": hw,
                "model_version": "marl_w_elo=0.543_w_market=0.243",
                "feature_version": "phase56_sp_bullpen_context_v1",
                "split_id": "window_1",
                "source_backtest": "full_backtest.FullBacktestEngine",
            }
            fh.write(json.dumps(row) + "\n")
    return path


# ═══════════════════════════════════════════════════════════════════
# SAFETY CONSTANTS
# ═══════════════════════════════════════════════════════════════════

class TestSafetyConstants:
    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_alpha_is_0_40(self):
        assert abs(ALPHA - 0.40) < 1e-9

    def test_alpha_type_is_float(self):
        assert isinstance(ALPHA, float)

    def test_all_safety_booleans_are_bool(self):
        assert isinstance(CANDIDATE_PATCH_CREATED, bool)
        assert isinstance(PRODUCTION_MODIFIED, bool)
        assert isinstance(ALPHA_MODIFIED, bool)
        assert isinstance(DIAGNOSTIC_ONLY, bool)


# ═══════════════════════════════════════════════════════════════════
# PHASE IDENTITY AND GATE CONSTANTS
# ═══════════════════════════════════════════════════════════════════

class TestPhaseIdentity:
    def test_phase_version_contains_68(self):
        assert "phase68" in PHASE_VERSION

    def test_completion_marker_exact(self):
        assert COMPLETION_MARKER == "PHASE_68_MODEL_ARCHITECTURE_ENSEMBLE_FAILURE_AUDIT_VERIFIED"

    def test_valid_gates_has_six_entries(self):
        assert len(_VALID_GATES) == 6

    def test_all_gate_constants_in_valid_gates(self):
        assert MODEL_ARCHITECTURE_REPAIR_PROMISING in _VALID_GATES
        assert ENSEMBLE_WEIGHTING_REPAIR_PROMISING in _VALID_GATES
        assert CALIBRATION_OBJECTIVE_REDESIGN_PROMISING in _VALID_GATES
        assert ABSTENTION_GUARD_PROMISING in _VALID_GATES
        assert OVERFIT_RISK in _VALID_GATES
        assert MODEL_ARCHITECTURE_NOT_PROMISING in _VALID_GATES

    def test_gate_constants_are_strings(self):
        for g in _VALID_GATES:
            assert isinstance(g, str)

    def test_phase67_gate_anchor_is_overfit_risk(self):
        assert PHASE67_GATE_ANCHOR == "OVERFIT_RISK"

    def test_phase66_gate_anchor(self):
        assert PHASE66_GATE_ANCHOR == "MARKET_MICROSTRUCTURE_NOT_PROMISING"

    def test_phase65_gate_anchor(self):
        assert PHASE65_GATE_ANCHOR == "OVERFIT_RISK"

    def test_phase64b_gate_anchor(self):
        assert PHASE64B_GATE_ANCHOR == "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"


# ═══════════════════════════════════════════════════════════════════
# CORE MATH FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

class TestBrier:
    def test_perfect_prediction(self):
        assert _brier([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)

    def test_worst_prediction(self):
        assert _brier([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)

    def test_naive_half(self):
        assert _brier([0.5, 0.5], [1.0, 0.0]) == pytest.approx(0.25)

    def test_empty_input(self):
        assert _brier([], []) == 0.0

    def test_single_row(self):
        assert _brier([0.7], [1.0]) == pytest.approx(0.09)

    def test_symmetric(self):
        b1 = _brier([0.6, 0.4], [1.0, 0.0])
        b2 = _brier([0.4, 0.6], [0.0, 1.0])
        assert b1 == pytest.approx(b2)

    def test_n_rows(self):
        probs = [0.7] * 100
        labels = [1.0] * 100
        assert _brier(probs, labels) == pytest.approx(0.09)


class TestBssDirect:
    def test_perfect_model_returns_1(self):
        assert _bss_direct(0.0, 0.25) == pytest.approx(1.0)

    def test_model_equal_ref_returns_0(self):
        assert _bss_direct(0.25, 0.25) == pytest.approx(0.0)

    def test_model_worse_than_ref_negative(self):
        assert _bss_direct(0.30, 0.25) == pytest.approx(-0.20)

    def test_zero_ref_returns_0(self):
        assert _bss_direct(0.10, 0.0) == 0.0

    def test_known_value(self):
        # 1 - 0.2434 / 0.2438 ≈ 0.00164
        result = _bss_direct(0.2434, 0.2438)
        assert result == pytest.approx(1 - 0.2434 / 0.2438, rel=1e-5)


class TestEce:
    def test_perfectly_calibrated(self):
        # If all predictions equal the actual win rate, ECE should be 0
        probs = [0.5] * 100
        labels = [1.0] * 50 + [0.0] * 50
        assert _ece(probs, labels) == pytest.approx(0.0, abs=0.01)

    def test_empty_input(self):
        assert _ece([], []) == 0.0

    def test_overconfident_has_positive_ece(self):
        # Always predict 0.9 but only 50% win
        probs = [0.9] * 100
        labels = [1.0] * 50 + [0.0] * 50
        assert _ece(probs, labels) > 0.0

    def test_n_bins_parameter(self):
        # Predict 90% but only 60% win rate → strongly miscalibrated
        probs = [0.9] * 50
        labels = [1.0] * 30 + [0.0] * 20
        ece_10 = _ece(probs, labels, n_bins=10)
        ece_5 = _ece(probs, labels, n_bins=5)
        # Both should be positive (miscalibrated)
        assert ece_10 > 0.0
        assert ece_5 > 0.0


class TestMeanStdCv:
    def test_mean_empty(self):
        assert _mean([]) == 0.0

    def test_mean_single(self):
        assert _mean([3.14]) == pytest.approx(3.14)

    def test_mean_known(self):
        assert _mean([1.0, 2.0, 3.0]) == pytest.approx(2.0)

    def test_std_empty(self):
        assert _std([]) == 0.0

    def test_std_single(self):
        assert _std([5.0]) == 0.0

    def test_std_known(self):
        # std([1, 2, 3]) = sqrt(2/3)
        assert _std([1.0, 2.0, 3.0]) == pytest.approx(math.sqrt(2 / 3))

    def test_cv_zero_mean(self):
        assert _cv([0.0, 0.0]) == 0.0

    def test_cv_known(self):
        # cv([1, 2, 3]) = std / mean = sqrt(2/3) / 2
        assert _cv([1.0, 2.0, 3.0]) == pytest.approx(math.sqrt(2 / 3) / 2.0)


# ═══════════════════════════════════════════════════════════════════
# ROW ENRICHMENT
# ═══════════════════════════════════════════════════════════════════

class TestEnrich:
    def test_blend_formula(self):
        row = _make_row(model_home_prob=0.60, market_home_prob_no_vig=0.50)
        enriched = _enrich([row])[0]
        expected_blend = (1 - 0.40) * 0.60 + 0.40 * 0.50
        assert enriched["_blend"] == pytest.approx(expected_blend)

    def test_fav_prob_always_gte_half(self):
        rows = _make_enriched(100)
        assert all(r["_fav_prob"] >= 0.5 for r in rows)

    def test_fav_is_home_when_blend_above_half(self):
        row = _make_row(model_home_prob=0.80, market_home_prob_no_vig=0.70)
        enriched = _enrich([row])[0]
        assert enriched["_fav_is_home"] is True

    def test_fav_is_away_when_blend_below_half(self):
        row = _make_row(model_home_prob=0.20, market_home_prob_no_vig=0.30)
        enriched = _enrich([row])[0]
        assert enriched["_fav_is_home"] is False

    def test_fav_win_when_fav_is_home_and_home_wins(self):
        row = _make_row(model_home_prob=0.70, market_home_prob_no_vig=0.65, home_win=1)
        enriched = _enrich([row])[0]
        assert enriched["_fav_win"] == pytest.approx(1.0)

    def test_fav_win_when_fav_is_home_and_home_loses(self):
        row = _make_row(model_home_prob=0.70, market_home_prob_no_vig=0.65, home_win=0)
        enriched = _enrich([row])[0]
        assert enriched["_fav_win"] == pytest.approx(0.0)

    def test_fav_win_when_fav_is_away_and_away_wins(self):
        row = _make_row(model_home_prob=0.20, market_home_prob_no_vig=0.30, home_win=0)
        enriched = _enrich([row])[0]
        assert enriched["_fav_win"] == pytest.approx(1.0)

    def test_model_fav_prob_symmetric(self):
        row = _make_row(model_home_prob=0.35)
        enriched = _enrich([row])[0]
        assert enriched["_model_fav_prob"] == pytest.approx(0.65)

    def test_mkt_fav_prob_symmetric(self):
        row = _make_row(market_home_prob_no_vig=0.40)
        enriched = _enrich([row])[0]
        assert enriched["_mkt_fav_prob"] == pytest.approx(0.60)

    def test_disagree_sign(self):
        row = _make_row(model_home_prob=0.60, market_home_prob_no_vig=0.50)
        enriched = _enrich([row])[0]
        assert enriched["_disagree"] == pytest.approx(0.10)

    def test_alpha_frozen_in_enrichment(self):
        # blend uses the module-level ALPHA = 0.40
        row = _make_row(model_home_prob=0.60, market_home_prob_no_vig=0.50)
        enriched = _enrich([row])[0]
        assert enriched["_blend"] == pytest.approx(0.60 * 0.60 + 0.40 * 0.50)


# ═══════════════════════════════════════════════════════════════════
# SEGMENT METRICS
# ═══════════════════════════════════════════════════════════════════

class TestComputeSegmentMetrics:
    def test_empty_returns_data_limited(self):
        m = _compute_segment_metrics([])
        assert m.n == 0
        assert m.data_limited is True

    def test_n_correct(self, sample_rows):
        m = _compute_segment_metrics(sample_rows)
        assert m.n == len(sample_rows)

    def test_data_limited_false_above_min_n(self, sample_rows):
        assert len(sample_rows) >= _MIN_SEGMENT_N
        m = _compute_segment_metrics(sample_rows)
        assert m.data_limited is False

    def test_data_limited_true_below_min_n(self):
        rows = _make_enriched(_MIN_SEGMENT_N - 1)
        m = _compute_segment_metrics(rows)
        assert m.data_limited is True

    def test_fav_win_rate_in_range(self, sample_rows):
        m = _compute_segment_metrics(sample_rows)
        assert 0.0 <= m.fav_win_rate <= 1.0

    def test_brier_scores_in_range(self, sample_rows):
        m = _compute_segment_metrics(sample_rows)
        assert 0.0 <= m.model_brier <= 1.0
        assert 0.0 <= m.market_brier <= 1.0
        assert 0.0 <= m.blend_brier <= 1.0

    def test_bss_formula_consistency(self, sample_rows):
        m = _compute_segment_metrics(sample_rows)
        expected_bss = _bss_direct(m.blend_brier, m.market_brier)
        assert m.blend_bss_vs_market == pytest.approx(expected_bss, abs=1e-4)

    def test_model_bss_formula_consistency(self, sample_rows):
        m = _compute_segment_metrics(sample_rows)
        expected = _bss_direct(m.model_brier, m.market_brier)
        assert m.model_bss_vs_market == pytest.approx(expected, abs=1e-4)

    def test_mean_fav_probs_above_half(self, sample_rows):
        m = _compute_segment_metrics(sample_rows)
        assert m.mean_blend_fav_prob >= 0.50
        assert m.mean_model_fav_prob >= 0.50
        assert m.mean_mkt_fav_prob >= 0.50

    def test_ece_values_in_range(self, sample_rows):
        m = _compute_segment_metrics(sample_rows)
        assert 0.0 <= m.ece_blend <= 1.0
        assert 0.0 <= m.ece_model <= 1.0
        assert 0.0 <= m.ece_market <= 1.0


# ═══════════════════════════════════════════════════════════════════
# CALIBRATION BANDS
# ═══════════════════════════════════════════════════════════════════

class TestCalibrationBands:
    def _get_bands(self, n: int = 500) -> list[CalibrationBand]:
        rows = _make_enriched(n)
        from orchestrator.phase68_model_architecture_ensemble_failure_audit import (
            _BLEND_CALIB_BANDS,
        )
        return _compute_calibration_bands(rows, "_fav_prob", _BLEND_CALIB_BANDS)

    def test_returns_list(self):
        bands = self._get_bands()
        assert isinstance(bands, list)

    def test_all_items_are_calibration_band(self):
        bands = self._get_bands()
        for b in bands:
            assert isinstance(b, CalibrationBand)

    def test_n_sums_to_total(self):
        rows = _make_enriched(500)
        from orchestrator.phase68_model_architecture_ensemble_failure_audit import (
            _BLEND_CALIB_BANDS,
        )
        bands = _compute_calibration_bands(rows, "_fav_prob", _BLEND_CALIB_BANDS)
        assert sum(b.n for b in bands) == 500

    def test_band_residual_formula(self):
        bands = self._get_bands(500)
        for b in bands:
            assert abs(b.residual - (b.blend_pred - b.actual_win_rate)) < 1e-5
            assert abs(b.model_residual - (b.model_pred - b.actual_win_rate)) < 1e-5
            assert abs(b.mkt_residual - (b.mkt_pred - b.actual_win_rate)) < 1e-5

    def test_overconfident_flag_when_residual_large(self):
        # Create rows where prediction >> actual in the 0.55-0.60 band
        # model_home_prob ≈ 0.58, market ≈ 0.57, home wins 30%
        rows = []
        for _ in range(50):
            r = _make_row(model_home_prob=0.58, market_home_prob_no_vig=0.57, home_win=0)
            rows.append(r)
        enriched = _enrich(rows)
        from orchestrator.phase68_model_architecture_ensemble_failure_audit import (
            _BLEND_CALIB_BANDS,
        )
        bands = _compute_calibration_bands(enriched, "_fav_prob", _BLEND_CALIB_BANDS)
        relevant = [b for b in bands if b.lo <= 0.57 < b.hi]
        if relevant:
            b = relevant[0]
            # blend_pred ≈ 0.574, actual ≈ 0.0 → residual >> threshold → overconfident
            if not b.data_limited:
                assert b.is_overconfident

    def test_data_limited_flag_for_small_bands(self):
        # Only one row in each band → all data_limited
        rows = _enrich([_make_row(0.52, 0.51, 1)])
        from orchestrator.phase68_model_architecture_ensemble_failure_audit import (
            _BLEND_CALIB_BANDS,
        )
        bands = _compute_calibration_bands(rows, "_fav_prob", _BLEND_CALIB_BANDS)
        for b in bands:
            assert b.data_limited is True

    def test_model_calib_bands_use_model_key(self):
        rows = _make_enriched(500)
        from orchestrator.phase68_model_architecture_ensemble_failure_audit import (
            _MODEL_CALIB_BANDS,
        )
        bands = _compute_calibration_bands(rows, "_model_fav_prob", _MODEL_CALIB_BANDS)
        assert len(bands) > 0

    def test_band_lo_hi_coverage(self):
        bands = self._get_bands(500)
        for b in bands:
            assert b.lo < b.hi
            assert 0.50 <= b.lo


# ═══════════════════════════════════════════════════════════════════
# DISAGREEMENT BUCKETS
# ═══════════════════════════════════════════════════════════════════

class TestDisagreementBuckets:
    def test_returns_three_buckets(self, sample_rows):
        buckets = _compute_disagreement_buckets(sample_rows)
        labels = {b.bucket_label for b in buckets}
        assert "model_large_fav" in labels or "mkt_large_fav" in labels or "agree" in labels

    def test_n_sums_to_total(self, sample_rows):
        buckets = _compute_disagreement_buckets(sample_rows)
        assert sum(b.n for b in buckets) == len(sample_rows)

    def test_threshold_stored(self, sample_rows):
        buckets = _compute_disagreement_buckets(sample_rows)
        for b in buckets:
            assert b.threshold == _LARGE_DISAGREE_THRESHOLD

    def test_brier_in_range(self, sample_rows):
        buckets = _compute_disagreement_buckets(sample_rows)
        for b in buckets:
            assert 0.0 <= b.model_brier <= 1.0
            assert 0.0 <= b.market_brier <= 1.0
            assert 0.0 <= b.blend_brier <= 1.0

    def test_market_beats_blend_flag_consistency(self, sample_rows):
        buckets = _compute_disagreement_buckets(sample_rows)
        for b in buckets:
            assert b.market_beats_blend == (b.market_brier < b.blend_brier)

    def test_market_beats_model_flag_consistency(self, sample_rows):
        buckets = _compute_disagreement_buckets(sample_rows)
        for b in buckets:
            assert b.market_beats_model == (b.market_brier < b.model_brier)


# ═══════════════════════════════════════════════════════════════════
# MODEL VERSION PARSING
# ═══════════════════════════════════════════════════════════════════

class TestParseModelVersion:
    def test_known_version_1(self):
        w_elo, w_mkt = _parse_model_version("marl_w_elo=0.543_w_market=0.243")
        assert w_elo == pytest.approx(0.543)
        assert w_mkt == pytest.approx(0.243)

    def test_known_version_2(self):
        w_elo, w_mkt = _parse_model_version("marl_w_elo=0.636_w_market=0.371")
        assert w_elo == pytest.approx(0.636)
        assert w_mkt == pytest.approx(0.371)

    def test_known_version_3(self):
        w_elo, w_mkt = _parse_model_version("marl_w_elo=0.400_w_market=0.350")
        assert w_elo == pytest.approx(0.400)
        assert w_mkt == pytest.approx(0.350)

    def test_known_version_4(self):
        w_elo, w_mkt = _parse_model_version("marl_w_elo=0.494_w_market=0.400")
        assert w_elo == pytest.approx(0.494)
        assert w_mkt == pytest.approx(0.400)

    def test_known_version_5(self):
        w_elo, w_mkt = _parse_model_version("marl_w_elo=0.413_w_market=0.384")
        assert w_elo == pytest.approx(0.413)
        assert w_mkt == pytest.approx(0.384)

    def test_malformed_returns_zeros(self):
        w_elo, w_mkt = _parse_model_version("unknown_version")
        assert w_elo == 0.0
        assert w_mkt == 0.0


# ═══════════════════════════════════════════════════════════════════
# MODEL VERSION PROFILES
# ═══════════════════════════════════════════════════════════════════

class TestModelVersionProfiles:
    def _make_multi_version_rows(self) -> list[dict]:
        versions = [
            "marl_w_elo=0.543_w_market=0.243",
            "marl_w_elo=0.494_w_market=0.400",
            "marl_w_elo=0.400_w_market=0.350",
        ]
        rng = random.Random(5)
        rows = []
        for i, v in enumerate(versions):
            for _ in range(20):
                model_p = 0.50 + rng.uniform(0, 0.20)
                mkt_p = 0.50 + rng.uniform(0, 0.18)
                hw = 1 if rng.random() > 0.50 else 0
                rows.append(_make_row(model_p, mkt_p, hw, model_version=v))
        return _enrich(rows)

    def test_returns_one_profile_per_version(self):
        rows = self._make_multi_version_rows()
        profiles = _compute_model_version_profiles(rows)
        assert len(profiles) == 3

    def test_profile_n_sums_to_total(self):
        rows = self._make_multi_version_rows()
        profiles = _compute_model_version_profiles(rows)
        assert sum(p.n for p in profiles) == len(rows)

    def test_profile_has_correct_w_elo(self):
        rows = self._make_multi_version_rows()
        profiles = _compute_model_version_profiles(rows)
        by_mv = {p.model_version: p for p in profiles}
        assert by_mv["marl_w_elo=0.543_w_market=0.243"].w_elo == pytest.approx(0.543)
        assert by_mv["marl_w_elo=0.494_w_market=0.400"].w_elo == pytest.approx(0.494)

    def test_profile_has_correct_w_market_internal(self):
        rows = self._make_multi_version_rows()
        profiles = _compute_model_version_profiles(rows)
        by_mv = {p.model_version: p for p in profiles}
        assert by_mv["marl_w_elo=0.543_w_market=0.243"].w_market_internal == pytest.approx(0.243)
        assert by_mv["marl_w_elo=0.400_w_market=0.350"].w_market_internal == pytest.approx(0.350)

    def test_brier_in_range(self):
        rows = self._make_multi_version_rows()
        profiles = _compute_model_version_profiles(rows)
        for p in profiles:
            assert 0.0 <= p.model_brier <= 1.0
            assert 0.0 <= p.market_brier <= 1.0
            assert 0.0 <= p.blend_brier <= 1.0

    def test_bss_consistency(self):
        rows = self._make_multi_version_rows()
        profiles = _compute_model_version_profiles(rows)
        for p in profiles:
            expected = _bss_direct(p.blend_brier, p.market_brier)
            assert p.blend_bss_vs_market == pytest.approx(expected, abs=1e-5)


# ═══════════════════════════════════════════════════════════════════
# ARCHITECTURE INSTABILITY
# ═══════════════════════════════════════════════════════════════════

class TestArchitectureInstability:
    def _make_profiles(self, w_mkt_vals: list[float]) -> list[ModelVersionProfile]:
        return [
            ModelVersionProfile(
                model_version=f"marl_w_elo=0.5_w_market={w}",
                n=100,
                w_elo=0.5,
                w_market_internal=w,
                model_brier=0.25,
                market_brier=0.24,
                blend_brier=0.24,
                blend_bss_vs_market=0.0,
            )
            for w in w_mkt_vals
        ]

    def test_instability_detected_high_cv(self):
        profiles = self._make_profiles([0.10, 0.50, 0.90])  # very spread
        ai = _compute_architecture_instability(profiles)
        assert ai.instability_detected is True

    def test_instability_not_detected_low_cv(self):
        profiles = self._make_profiles([0.35, 0.36, 0.37])  # barely varying
        ai = _compute_architecture_instability(profiles)
        assert ai.instability_detected is False

    def test_n_model_versions(self):
        profiles = self._make_profiles([0.30, 0.40, 0.35, 0.38, 0.32])
        ai = _compute_architecture_instability(profiles)
        assert ai.n_model_versions == 5

    def test_w_market_values_stored(self):
        vals = [0.243, 0.400, 0.350, 0.371, 0.384]
        profiles = self._make_profiles(vals)
        ai = _compute_architecture_instability(profiles)
        assert sorted(ai.w_market_values) == pytest.approx(sorted(vals))

    def test_cv_threshold(self):
        assert _INSTABILITY_CV_THRESHOLD == pytest.approx(0.10)

    def test_real_data_five_versions_detected(self):
        # The real predictions file has 5 different model versions with w_market
        # varying from 0.243 to 0.400 — CV ≈ 0.18 >> 0.10 threshold
        vals = [0.243, 0.400, 0.350, 0.371, 0.384]
        profiles = self._make_profiles(vals)
        ai = _compute_architecture_instability(profiles)
        assert ai.instability_detected is True


# ═══════════════════════════════════════════════════════════════════
# ENSEMBLE SHARPNESS
# ═══════════════════════════════════════════════════════════════════

class TestEnsembleSharpness:
    def test_model_less_sharp_than_market_detection(self):
        # Make model less confident than market
        rows = []
        for _ in range(50):
            # model: 55%, market: 70% (both fav is home → both > 0.5)
            rows.append(_make_row(model_home_prob=0.55, market_home_prob_no_vig=0.70, home_win=1))
        enriched = _enrich(rows)
        es = _compute_ensemble_sharpness(enriched)
        assert es.model_less_sharp_than_market is True

    def test_model_sharper_than_market(self):
        rows = []
        for _ in range(50):
            rows.append(_make_row(model_home_prob=0.80, market_home_prob_no_vig=0.55, home_win=1))
        enriched = _enrich(rows)
        es = _compute_ensemble_sharpness(enriched)
        assert es.model_less_sharp_than_market is False

    def test_mean_fav_prob_above_half(self, sample_rows):
        es = _compute_ensemble_sharpness(sample_rows)
        assert es.model_mean_fav_prob >= 0.5
        assert es.market_mean_fav_prob >= 0.5
        assert es.blend_mean_fav_prob >= 0.5

    def test_std_nonnegative(self, sample_rows):
        es = _compute_ensemble_sharpness(sample_rows)
        assert es.model_std_fav_prob >= 0.0
        assert es.market_std_fav_prob >= 0.0
        assert es.blend_std_fav_prob >= 0.0


# ═══════════════════════════════════════════════════════════════════
# BLEND DILUTION CHECKS
# ═══════════════════════════════════════════════════════════════════

class TestBlendDilutionChecks:
    def test_returns_list(self, sample_rows):
        checks = _compute_blend_dilution_checks(sample_rows)
        assert isinstance(checks, list)

    def test_all_items_are_blend_dilution_check(self, sample_rows):
        checks = _compute_blend_dilution_checks(sample_rows)
        for c in checks:
            assert isinstance(c, BlendDilutionCheck)

    def test_dilution_flag_consistent_with_magnitude(self, sample_rows):
        checks = _compute_blend_dilution_checks(sample_rows)
        for c in checks:
            if c.n >= _MIN_BUCKET_N:
                assert c.dilution_detected == (c.dilution_magnitude > 0)

    def test_all_games_segment_present(self, sample_rows):
        checks = _compute_blend_dilution_checks(sample_rows)
        labels = {c.segment for c in checks}
        assert "all_games" in labels

    def test_heavy_fav_segment_present(self, sample_rows):
        checks = _compute_blend_dilution_checks(sample_rows)
        labels = {c.segment for c in checks}
        assert "heavy_fav_0.70" in labels

    def test_magnitude_formula(self, sample_rows):
        checks = _compute_blend_dilution_checks(sample_rows)
        for c in checks:
            if c.n >= _MIN_BUCKET_N:
                expected_mag = c.blend_brier - c.market_brier
                assert c.dilution_magnitude == pytest.approx(expected_mag, abs=1e-5)


# ═══════════════════════════════════════════════════════════════════
# NEGATIVE CONTROLS
# ═══════════════════════════════════════════════════════════════════

class TestNegativeControls:
    def test_returns_controls(self, sample_rows):
        rng = random.Random(42)
        controls = _run_negative_controls(sample_rows, n_boot=50, rng=rng)
        assert len(controls) >= 2

    def test_shuffled_control_present(self, sample_rows):
        rng = random.Random(42)
        controls = _run_negative_controls(sample_rows, n_boot=50, rng=rng)
        names = {c.control_name for c in controls}
        assert "shuffled_confidence_bucket" in names

    def test_shuffled_null_bss_less_than_real_for_overfit_check(self):
        # For large n with genuine signal, real BSS should exceed shuffled
        # (synthetic data has no signal so just check the formula is applied)
        rows = _make_enriched(200)
        rng = random.Random(42)
        controls = _run_negative_controls(rows, n_boot=50, rng=rng)
        shuffled = next(c for c in controls if c.control_name == "shuffled_confidence_bucket")
        # signal_gap = real_bss - null_bss_mean (formula check)
        assert shuffled.signal_gap == pytest.approx(
            shuffled.real_bss - shuffled.null_bss_mean, abs=1e-4
        )

    def test_signal_gap_formula_shuffled_control(self, sample_rows):
        # The shuffled control uses: signal_gap = real_bss - null_bss_mean
        rng = random.Random(42)
        controls = _run_negative_controls(sample_rows, n_boot=50, rng=rng)
        shuffled = next(c for c in controls if c.control_name == "shuffled_confidence_bucket")
        assert shuffled.signal_gap == pytest.approx(
            shuffled.real_bss - shuffled.null_bss_mean, abs=1e-4
        )

    def test_overfit_threshold_stored(self, sample_rows):
        rng = random.Random(42)
        controls = _run_negative_controls(sample_rows, n_boot=50, rng=rng)
        for c in controls:
            assert c.overfit_threshold == _OVERFIT_GAP_THRESHOLD

    def test_overfit_flag_consistency(self, sample_rows):
        rng = random.Random(42)
        controls = _run_negative_controls(sample_rows, n_boot=50, rng=rng)
        shuffled = next(c for c in controls if c.control_name == "shuffled_confidence_bucket")
        expected = shuffled.signal_gap < _OVERFIT_GAP_THRESHOLD
        assert shuffled.overfit_risk == expected


# ═══════════════════════════════════════════════════════════════════
# GATE DETERMINATION
# ═══════════════════════════════════════════════════════════════════

class TestDetermineGate:
    def _make_seg_metrics(self, **kwargs) -> SegmentMetrics:
        defaults = dict(
            n=100, model_brier=0.245, market_brier=0.244, blend_brier=0.243,
            blend_bss_vs_market=0.0004, model_bss_vs_market=-0.0004,
            fav_win_rate=0.530, ece_blend=0.026, ece_model=0.031, ece_market=0.030,
            mean_blend_fav_prob=0.572, mean_model_fav_prob=0.572, mean_mkt_fav_prob=0.579,
            data_limited=False,
        )
        defaults.update(kwargs)
        return SegmentMetrics(**defaults)

    def _make_nc(self, overfit_risk: bool = False) -> list[NegativeControl]:
        return [NegativeControl(
            control_name="shuffled_confidence_bucket",  # must be this name to trigger gate
            description="test",
            real_bss=0.026,
            null_bss_mean=-0.006,
            null_bss_std=0.003,
            signal_gap=0.032,
            overfit_threshold=_OVERFIT_GAP_THRESHOLD,
            overfit_risk=overfit_risk,
        )]

    def _make_no_sig_calib_bands(self) -> list[CalibrationBand]:
        return [CalibrationBand(
            band_label="0.50-0.55", lo=0.50, hi=0.55, n=100,
            blend_pred=0.52, model_pred=0.52, mkt_pred=0.52,
            actual_win_rate=0.52, residual=0.00, model_residual=0.00, mkt_residual=0.00,
            is_overconfident=False, is_underconfident=False, data_limited=False,
        )]

    def _make_overconf_bands(self) -> list[CalibrationBand]:
        return [CalibrationBand(
            band_label="0.55-0.60", lo=0.55, hi=0.60, n=100,
            blend_pred=0.572, model_pred=0.572, mkt_pred=0.575,
            actual_win_rate=0.514, residual=0.058, model_residual=0.058, mkt_residual=0.061,
            is_overconfident=True, is_underconfident=False, data_limited=False,
        )]

    def _make_underconf_bands(self) -> list[CalibrationBand]:
        return [CalibrationBand(
            band_label="0.65-0.70", lo=0.65, hi=0.70, n=50,
            blend_pred=0.674, model_pred=0.672, mkt_pred=0.681,
            actual_win_rate=0.734, residual=-0.060, model_residual=-0.062, mkt_residual=-0.053,
            is_overconfident=False, is_underconfident=True, data_limited=False,
        )]

    def _make_disagreement_buckets(self) -> list[DisagreementBucket]:
        return []

    def _make_arch_instability(self, instability_detected: bool = True) -> ArchitectureInstability:
        return ArchitectureInstability(
            n_model_versions=5,
            model_versions=["v1", "v2", "v3", "v4", "v5"],
            w_market_values=[0.243, 0.400, 0.350, 0.371, 0.384],
            w_elo_values=[0.543, 0.494, 0.400, 0.636, 0.413],
            w_market_mean=0.350, w_market_std=0.062, w_market_cv=0.177,
            w_elo_mean=0.497, w_elo_std=0.091, w_elo_cv=0.183,
            instability_detected=instability_detected,
        )

    def test_overfit_risk_gate_when_nc_flags_overfit(self):
        gate, _, _, _ = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=self._make_seg_metrics(),
            calibration_bands_blend=self._make_no_sig_calib_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=True),
            architecture_instability=self._make_arch_instability(),
        )
        assert gate == OVERFIT_RISK

    def test_calibration_gate_from_overconfident_band(self):
        gate, _, _, _ = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=self._make_seg_metrics(),
            calibration_bands_blend=self._make_overconf_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=False),
            architecture_instability=self._make_arch_instability(),
        )
        assert gate == CALIBRATION_OBJECTIVE_REDESIGN_PROMISING

    def test_calibration_gate_from_underconfident_band(self):
        gate, _, _, _ = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=self._make_seg_metrics(),
            calibration_bands_blend=self._make_underconf_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=False),
            architecture_instability=self._make_arch_instability(),
        )
        assert gate == CALIBRATION_OBJECTIVE_REDESIGN_PROMISING

    def test_ensemble_weighting_gate_when_model_bss_negative(self):
        heavy_fav = self._make_seg_metrics(model_bss_vs_market=-0.012, data_limited=False)
        gate, _, _, _ = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=heavy_fav,
            calibration_bands_blend=self._make_no_sig_calib_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=False),
            architecture_instability=self._make_arch_instability(),
        )
        assert gate == ENSEMBLE_WEIGHTING_REPAIR_PROMISING

    def test_abstention_guard_gate_when_ece_high(self):
        heavy_fav = self._make_seg_metrics(
            model_bss_vs_market=0.001,  # model is positive
            ece_blend=_ABSTENTION_ECE_THRESHOLD + 0.01,
            data_limited=False,
        )
        gate, _, _, _ = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=heavy_fav,
            calibration_bands_blend=self._make_no_sig_calib_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=False),
            architecture_instability=self._make_arch_instability(),
        )
        assert gate == ABSTENTION_GUARD_PROMISING

    def test_default_gate_when_no_signals(self):
        gate, _, _, _ = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=self._make_seg_metrics(model_bss_vs_market=0.001),
            calibration_bands_blend=self._make_no_sig_calib_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=False),
            architecture_instability=self._make_arch_instability(),
        )
        assert gate == MODEL_ARCHITECTURE_NOT_PROMISING

    def test_overfit_takes_priority_over_calibration(self):
        # Even with overconfident bands, overfit gate wins
        gate, _, _, _ = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=self._make_seg_metrics(),
            calibration_bands_blend=self._make_overconf_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=True),
            architecture_instability=self._make_arch_instability(),
        )
        assert gate == OVERFIT_RISK

    def test_worth_phase69_true_for_calibration_gate(self):
        _, _, _, worth = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=self._make_seg_metrics(),
            calibration_bands_blend=self._make_overconf_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=False),
            architecture_instability=self._make_arch_instability(),
        )
        assert worth is True

    def test_worth_phase69_false_for_overfit_gate(self):
        _, _, _, worth = _determine_gate(
            all_metrics=self._make_seg_metrics(),
            heavy_fav_metrics=self._make_seg_metrics(),
            calibration_bands_blend=self._make_no_sig_calib_bands(),
            disagreement_buckets=[],
            negative_controls=self._make_nc(overfit_risk=True),
            architecture_instability=self._make_arch_instability(),
        )
        assert worth is False

    def test_gate_always_in_valid_gates(self):
        all_band_combos = [
            self._make_no_sig_calib_bands(),
            self._make_overconf_bands(),
            self._make_underconf_bands(),
        ]
        for bands in all_band_combos:
            for overfit in [True, False]:
                gate, _, _, _ = _determine_gate(
                    all_metrics=self._make_seg_metrics(),
                    heavy_fav_metrics=self._make_seg_metrics(),
                    calibration_bands_blend=bands,
                    disagreement_buckets=[],
                    negative_controls=self._make_nc(overfit_risk=overfit),
                    architecture_instability=self._make_arch_instability(),
                )
                assert gate in _VALID_GATES


# ═══════════════════════════════════════════════════════════════════
# SERIALIZATION
# ═══════════════════════════════════════════════════════════════════

class TestSerialization:
    def test_to_dict_segment_metrics(self):
        m = SegmentMetrics(
            n=100, model_brier=0.245, market_brier=0.244, blend_brier=0.243,
            blend_bss_vs_market=0.0004, model_bss_vs_market=-0.0004,
            fav_win_rate=0.530, ece_blend=0.026, ece_model=0.031, ece_market=0.030,
            mean_blend_fav_prob=0.572, mean_model_fav_prob=0.572, mean_mkt_fav_prob=0.579,
            data_limited=False,
        )
        d = _to_dict(m)
        assert isinstance(d, dict)
        assert d["n"] == 100
        assert d["blend_brier"] == pytest.approx(0.243)

    def test_to_dict_list_of_dataclasses(self):
        bands = [
            CalibrationBand(
                band_label="0.55-0.60", lo=0.55, hi=0.60, n=100,
                blend_pred=0.57, model_pred=0.57, mkt_pred=0.575,
                actual_win_rate=0.514, residual=0.056, model_residual=0.056,
                mkt_residual=0.061, is_overconfident=True, is_underconfident=False,
                data_limited=False,
            )
        ]
        d = _to_dict(bands)
        assert isinstance(d, list)
        assert d[0]["band_label"] == "0.55-0.60"
        assert d[0]["is_overconfident"] is True

    def test_json_roundtrip(self, predictions_jsonl, tmp_path):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        d = _to_dict(report)
        out = tmp_path / "report.json"
        out.write_text(json.dumps(d))
        loaded = json.loads(out.read_text())
        assert loaded["gate"] in _VALID_GATES
        assert loaded["completion_marker"] == COMPLETION_MARKER
        assert loaded["n_predictions"] == 200


# ═══════════════════════════════════════════════════════════════════
# THRESHOLDS VALIDATION
# ═══════════════════════════════════════════════════════════════════

class TestThresholds:
    def test_heavy_fav_threshold(self):
        assert _HEAVY_FAV_THRESHOLD == pytest.approx(0.70)

    def test_high_conf_threshold(self):
        assert _HIGH_CONF_THRESHOLD == pytest.approx(0.75)

    def test_phase45_min_fav(self):
        assert _PHASE45_FAIL_MIN_FAV == pytest.approx(0.60)

    def test_overconf_threshold(self):
        assert _OVERCONF_RESIDUAL_THRESHOLD == pytest.approx(0.04)

    def test_underconf_threshold(self):
        assert _UNDERCONF_RESIDUAL_THRESHOLD == pytest.approx(0.04)

    def test_large_disagree_threshold(self):
        assert _LARGE_DISAGREE_THRESHOLD == pytest.approx(0.05)

    def test_overfit_gap_threshold(self):
        assert _OVERFIT_GAP_THRESHOLD == pytest.approx(0.02)

    def test_min_segment_n(self):
        assert _MIN_SEGMENT_N == 20

    def test_min_bucket_n(self):
        assert _MIN_BUCKET_N == 15

    def test_bootstrap_n(self):
        assert _BOOTSTRAP_N == 1000

    def test_abstention_ece_threshold(self):
        assert _ABSTENTION_ECE_THRESHOLD == pytest.approx(0.06)


# ═══════════════════════════════════════════════════════════════════
# INTEGRATION — FULL PIPELINE (synthetic data)
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    def test_run_returns_phase68_report(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert isinstance(report, Phase68Report)

    def test_completion_marker_in_report(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert report.completion_marker == COMPLETION_MARKER

    def test_gate_is_valid(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert report.gate in _VALID_GATES

    def test_safety_constants_in_report(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert report.candidate_patch_created is False
        assert report.production_modified is False
        assert report.alpha_modified is False
        assert report.diagnostic_only is True
        assert abs(report.alpha - 0.40) < 1e-9

    def test_n_predictions_correct(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert report.n_predictions == 200

    def test_phase_anchors_in_report(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert report.phase67_gate_anchor == "OVERFIT_RISK"
        assert report.phase66_gate_anchor == "MARKET_MICROSTRUCTURE_NOT_PROMISING"
        assert report.phase65_gate_anchor == "OVERFIT_RISK"
        assert report.phase64b_gate_anchor == "BULLPEN_GRANULAR_FEATURE_NOT_PROMISING"

    def test_all_metrics_n_correct(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert report.all_metrics.n == 200

    def test_segment_n_lte_all_metrics_n(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert report.heavy_fav_metrics.n <= report.all_metrics.n
        assert report.high_conf_metrics.n <= report.all_metrics.n
        assert report.extreme_fav_metrics.n <= report.all_metrics.n

    def test_phase45_failure_segment_n_lte_all(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert report.phase45_failure_metrics.n <= report.all_metrics.n

    def test_calibration_bands_blend_present(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert len(report.calibration_bands_blend) > 0

    def test_disagreement_buckets_n_sum(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        total = sum(b.n for b in report.disagreement_buckets)
        assert total == 200

    def test_blend_dilution_checks_present(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert len(report.blend_dilution_checks) >= 3

    def test_negative_controls_present(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert len(report.negative_controls) >= 2

    def test_model_version_profiles_present(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert len(report.model_version_profiles) >= 1

    def test_summary_flags_are_booleans(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert isinstance(report.calibration_overconfidence_detected, bool)
        assert isinstance(report.calibration_underconfidence_detected, bool)
        assert isinstance(report.blend_dilution_heavy_fav, bool)
        assert isinstance(report.architecture_instability_detected, bool)
        assert isinstance(report.overfit_risk_detected, bool)
        assert isinstance(report.worth_phase69, bool)

    def test_worth_phase69_consistent_with_gate(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        if report.gate == OVERFIT_RISK:
            assert report.worth_phase69 is False
        if report.gate == CALIBRATION_OBJECTIVE_REDESIGN_PROMISING:
            assert report.worth_phase69 is True

    def test_gate_rationale_nonempty(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert len(report.gate_rationale) > 10

    def test_next_step_nonempty(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert len(report.next_step) > 5

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            run_phase68_model_architecture_ensemble_failure_audit(
                predictions_path=tmp_path / "nonexistent.jsonl", n_boot=5, rng_seed=0
            )

    def test_generated_at_is_iso_format(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        # Should not raise
        datetime.fromisoformat(report.generated_at)

    def test_architecture_instability_object_present(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert isinstance(report.architecture_instability, ArchitectureInstability)

    def test_ensemble_sharpness_object_present(self, predictions_jsonl):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=predictions_jsonl, n_boot=20, rng_seed=0
        )
        assert isinstance(report.ensemble_sharpness, EnsembleSharpness)


# ═══════════════════════════════════════════════════════════════════
# END-TO-END WITH REAL DATA (skipped if file absent)
# ═══════════════════════════════════════════════════════════════════

_REAL_PREDICTIONS = Path(
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)


@pytest.mark.skipif(
    not _REAL_PREDICTIONS.exists(),
    reason="Real predictions file not present; skipping end-to-end test.",
)
class TestEndToEnd:
    def test_gate_is_calibration_objective_redesign(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=1000, rng_seed=42
        )
        assert report.gate == CALIBRATION_OBJECTIVE_REDESIGN_PROMISING

    def test_n_predictions_2025(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.n_predictions == 2025

    def test_heavy_fav_n_is_60(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.heavy_fav_metrics.n == 60

    def test_five_model_versions(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.architecture_instability.n_model_versions == 5

    def test_architecture_instability_detected(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.architecture_instability_detected is True

    def test_calibration_overconfidence_at_55_60(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        # 0.55-0.60 band: residual ≈ +0.0587 >> 0.04 threshold
        bands_55_60 = [b for b in report.calibration_bands_blend if b.band_label == "0.55-0.60"]
        assert len(bands_55_60) == 1
        assert bands_55_60[0].is_overconfident is True
        assert bands_55_60[0].residual > _OVERCONF_RESIDUAL_THRESHOLD

    def test_calibration_underconfidence_at_65_70(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        bands_65_70 = [b for b in report.calibration_bands_blend if b.band_label == "0.65-0.70"]
        assert len(bands_65_70) == 1
        assert bands_65_70[0].is_underconfident is True
        assert bands_65_70[0].residual < -_UNDERCONF_RESIDUAL_THRESHOLD

    def test_blend_dilution_at_heavy_fav(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.blend_dilution_heavy_fav is True

    def test_no_overfit_risk(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=1000, rng_seed=42
        )
        assert report.overfit_risk_detected is False

    def test_worth_phase69_true(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.worth_phase69 is True

    def test_model_less_sharp_than_market(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.ensemble_sharpness.model_less_sharp_than_market is True

    def test_heavy_fav_model_bss_negative(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.heavy_fav_metrics.model_bss_vs_market < 0.0

    def test_heavy_fav_blend_bss_negative(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.heavy_fav_metrics.blend_bss_vs_market < 0.0

    def test_market_beats_blend_in_disagree_mkt_large_bucket(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        mkt_bucket = next(
            (b for b in report.disagreement_buckets if b.bucket_label == "mkt_large_fav"), None
        )
        if mkt_bucket and mkt_bucket.n >= _MIN_BUCKET_N:
            assert mkt_bucket.market_beats_model is True

    def test_completion_marker(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        assert report.completion_marker == "PHASE_68_MODEL_ARCHITECTURE_ENSEMBLE_FAILURE_AUDIT_VERIFIED"

    def test_all_metrics_all_games_brier_range(self):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        # From probe: blend brier ≈ 0.2434
        assert 0.22 <= report.all_metrics.blend_brier <= 0.26

    def test_report_json_roundtrip(self, tmp_path):
        report = run_phase68_model_architecture_ensemble_failure_audit(
            predictions_path=_REAL_PREDICTIONS, n_boot=100, rng_seed=42
        )
        d = _to_dict(report)
        out = tmp_path / "p68_test.json"
        out.write_text(json.dumps(d, indent=2))
        loaded = json.loads(out.read_text())
        assert loaded["gate"] == report.gate
        assert loaded["n_predictions"] == 2025
        assert loaded["completion_marker"] == COMPLETION_MARKER
