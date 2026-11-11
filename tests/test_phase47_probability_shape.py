"""
Tests for Phase 47: Probability Shape Repair (Pre-Feature Fix)
==============================================================
Covers:
  - Distribution stats computation
  - Reliability diagram bins and calibration verdict
  - Bucket-level overconfidence/underconfidence diagnosis
  - Temperature scaling (offline)
  - Isotonic regression calibration (offline)
  - Metrics comparison (raw vs calibrated)
  - Gate decision logic
  - Hard-rule invariants (no patch, no production modification)
  - Edge cases and audit trail
"""
from __future__ import annotations

import math
import uuid
from dataclasses import asdict

import pytest

from orchestrator.phase47_probability_shape import (
    ALPHA,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    _CALIBRATION_FIRST,
    _OVERCONFIDENT,
    _PROCEED_TO_FEATURE_PHASE,
    _UNDERCONFIDENT,
    _WELL_CALIBRATED,
    BucketDiagnosis,
    CalibrationMetrics,
    DistributionStats,
    ShapeRepairResult,
    _binary_entropy,
    _calibration_verdict,
    _compute_audit_hash,
    _gate_decision,
    build_reliability_bins,
    compute_distribution_stats,
    diagnose_all_buckets,
    diagnose_bucket,
    isotonic_calibrate,
    run_phase47_shape_repair,
    temperature_scale,
)
from wbc_backend.evaluation.prediction_persistence import PredictionRow


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_row(
    model_prob: float,
    market_prob: float,
    label: int,
    game_date: str = "2025-06-15",
    game_id: str = "",
) -> PredictionRow:
    """Create a minimal PredictionRow for testing."""
    return PredictionRow(
        model_home_prob=model_prob,
        market_home_prob_no_vig=market_prob,
        market_away_prob_no_vig=round(1.0 - market_prob, 8),
        home_win=label,
        game_date=game_date,
        game_id=game_id or f"TEST_{model_prob:.3f}_{market_prob:.3f}_{label}",
    )


def _make_rows(
    n: int,
    *,
    model_prob: float = 0.6,
    market_prob: float = 0.55,
    label: int = 1,
) -> list[PredictionRow]:
    """Create n identical PredictionRows."""
    return [
        _make_row(model_prob, market_prob, label, game_id=f"TEST_{i:04d}")
        for i in range(n)
    ]


def _mixed_rows(n_pos: int = 30, n_neg: int = 30) -> list[PredictionRow]:
    """Mix of label=1 (model overconfident) and label=0."""
    rows = []
    # label=1: model and market aligned, prediction OK
    rows += [_make_row(0.65, 0.60, 1, game_id=f"P_{i:04d}") for i in range(n_pos)]
    # label=0: model overconfident (predicts high, actual loss)
    rows += [_make_row(0.75, 0.65, 0, game_id=f"N_{i:04d}") for i in range(n_neg)]
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# § A  Binary Entropy
# ═══════════════════════════════════════════════════════════════════════════════

class TestBinaryEntropy:
    def test_max_entropy_at_half(self):
        h = _binary_entropy(0.5)
        assert abs(h - 1.0) < 1e-9

    def test_zero_entropy_at_zero(self):
        assert _binary_entropy(0.0) == 0.0

    def test_zero_entropy_at_one(self):
        assert _binary_entropy(1.0) == 0.0

    def test_intermediate_value(self):
        h = _binary_entropy(0.8)
        assert 0.0 < h < 1.0

    def test_symmetric(self):
        assert abs(_binary_entropy(0.3) - _binary_entropy(0.7)) < 1e-12


# ═══════════════════════════════════════════════════════════════════════════════
# § B  Distribution Stats
# ═══════════════════════════════════════════════════════════════════════════════

class TestDistributionStats:
    def test_single_prob(self):
        ds = compute_distribution_stats([0.5])
        assert ds.n == 1
        assert ds.mean == 0.5
        assert ds.variance == 0.0
        assert ds.std == 0.0

    def test_mean_correct(self):
        probs = [0.3, 0.5, 0.7]
        ds = compute_distribution_stats(probs)
        assert abs(ds.mean - 0.5) < 1e-9

    def test_variance_correct(self):
        probs = [0.0, 1.0]
        ds = compute_distribution_stats(probs)
        assert abs(ds.variance - 0.25) < 1e-9

    def test_sharpness_high_when_extreme(self):
        # Very extreme predictions → high variance
        probs = [0.05] * 10 + [0.95] * 10
        ds = compute_distribution_stats(probs)
        assert ds.variance > 0.10

    def test_fraction_near_half(self):
        # All at 0.5 → all near half
        probs = [0.5] * 20
        ds = compute_distribution_stats(probs)
        assert ds.fraction_near_half == 1.0

    def test_fraction_extreme(self):
        # 0.8 is |0.8-0.5|=0.30 >= 0.20
        probs = [0.8] * 10 + [0.5] * 10
        ds = compute_distribution_stats(probs)
        assert abs(ds.fraction_extreme - 0.5) < 1e-9

    def test_entropy_max_at_half(self):
        # p=0.5 gives entropy=1.0 (max)
        probs = [0.5] * 20
        ds = compute_distribution_stats(probs)
        assert abs(ds.entropy - 1.0) < 1e-9

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compute_distribution_stats([])

    def test_returns_distribution_stats(self):
        ds = compute_distribution_stats([0.4, 0.6])
        assert isinstance(ds, DistributionStats)


# ═══════════════════════════════════════════════════════════════════════════════
# § C  Calibration Verdict
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalibrationVerdict:
    def test_overconfident(self):
        assert _calibration_verdict(0.80, 0.60) == _OVERCONFIDENT

    def test_underconfident(self):
        assert _calibration_verdict(0.40, 0.60) == _UNDERCONFIDENT

    def test_well_calibrated_exact(self):
        assert _calibration_verdict(0.60, 0.60) == _WELL_CALIBRATED

    def test_well_calibrated_within_margin(self):
        # gap = 0.005 < 0.01 → WELL_CALIBRATED
        assert _calibration_verdict(0.605, 0.60) == _WELL_CALIBRATED

    def test_boundary_overconfident(self):
        # gap = 0.011 > 0.01 → OVERCONFIDENT
        assert _calibration_verdict(0.611, 0.60) == _OVERCONFIDENT

    def test_boundary_underconfident(self):
        # gap = -0.011 < -0.01 → UNDERCONFIDENT
        assert _calibration_verdict(0.589, 0.60) == _UNDERCONFIDENT


# ═══════════════════════════════════════════════════════════════════════════════
# § D  Reliability Bins
# ═══════════════════════════════════════════════════════════════════════════════

class TestReliabilityBins:
    def test_returns_10_bins(self):
        rows = _make_rows(50, model_prob=0.6, label=1)
        probs = [r.model_home_prob for r in rows]
        labels = [r.home_win for r in rows]
        bins = build_reliability_bins(probs, labels)
        assert len(bins) == 10

    def test_bin_has_verdict(self):
        rows = _make_rows(20, model_prob=0.65, label=1)
        probs = [r.model_home_prob for r in rows]
        labels = [r.home_win for r in rows]
        bins = build_reliability_bins(probs, labels)
        for b in bins:
            assert b.verdict in (_OVERCONFIDENT, _UNDERCONFIDENT, _WELL_CALIBRATED)

    def test_perfect_calibration_well_calibrated(self):
        # pred=0.65, actual=1 about 65% of the time
        probs = [0.65] * 13 + [0.65] * 7
        labels = [1] * 13 + [0] * 7
        bins = build_reliability_bins(probs, labels)
        populated = [b for b in bins if b.count > 0]
        assert len(populated) == 1
        assert populated[0].verdict == _WELL_CALIBRATED

    def test_overconfident_bin(self):
        # pred=0.85 but only 50% win rate → overconfident
        probs = [0.85] * 20
        labels = [1] * 10 + [0] * 10
        bins = build_reliability_bins(probs, labels)
        populated = [b for b in bins if b.count > 0]
        assert populated[0].verdict == _OVERCONFIDENT

    def test_count_sums_to_n(self):
        probs = [0.3, 0.5, 0.7, 0.9]
        labels = [0, 1, 1, 1]
        bins = build_reliability_bins(probs, labels)
        assert sum(b.count for b in bins) == 4


# ═══════════════════════════════════════════════════════════════════════════════
# § E  Bucket Diagnosis
# ═══════════════════════════════════════════════════════════════════════════════

class TestBucketDiagnosis:
    def test_overconfident_bucket(self):
        # model predicts 0.8, but only 50% win → overconfident
        probs = [0.8] * 20
        labels = [1] * 10 + [0] * 10
        diag = diagnose_bucket("test_bucket", probs, labels)
        assert diag.verdict == _OVERCONFIDENT
        assert diag.calibration_gap > 0.01

    def test_underconfident_bucket(self):
        # model predicts 0.3, but 80% win → underconfident
        probs = [0.3] * 20
        labels = [1] * 16 + [0] * 4
        diag = diagnose_bucket("test_bucket", probs, labels)
        assert diag.verdict == _UNDERCONFIDENT
        assert diag.calibration_gap < -0.01

    def test_well_calibrated_bucket(self):
        # model predicts 0.6, 60% win → well calibrated
        probs = [0.6] * 10
        labels = [1] * 6 + [0] * 4
        diag = diagnose_bucket("test_bucket", probs, labels)
        assert diag.verdict == _WELL_CALIBRATED

    def test_empty_probs_raises(self):
        with pytest.raises(ValueError, match="empty"):
            diagnose_bucket("test", [], [])

    def test_n_correct(self):
        probs = [0.5] * 15
        labels = [1] * 7 + [0] * 8
        diag = diagnose_bucket("test", probs, labels)
        assert diag.n == 15

    def test_predicted_mean_correct(self):
        probs = [0.4, 0.6]
        diag = diagnose_bucket("test", probs, [0, 1])
        assert abs(diag.predicted_mean - 0.5) < 1e-6


class TestDiagnoseAllBuckets:
    def test_returns_list_of_bucket_diagnosis(self):
        rows = _make_rows(50)
        result = diagnose_all_buckets(rows)
        assert isinstance(result, list)
        assert all(isinstance(d, BucketDiagnosis) for d in result)

    def test_covers_all_three_dimensions(self):
        rows = _make_rows(50, model_prob=0.6, market_prob=0.5)
        result = diagnose_all_buckets(rows)
        names = {d.bucket_name for d in result}
        # Should include at least one from each dimension
        assert any("confidence:" in n for n in names)
        assert any("odds_bucket:" in n for n in names)
        assert any("disagreement:" in n for n in names)

    def test_no_bucket_exceeds_total_sample(self):
        rows = _make_rows(40)
        result = diagnose_all_buckets(rows)
        assert all(d.n <= 40 for d in result)


# ═══════════════════════════════════════════════════════════════════════════════
# § F  Temperature Scaling
# ═══════════════════════════════════════════════════════════════════════════════

class TestTemperatureScaling:
    def test_returns_same_length(self):
        probs = [0.7] * 20 + [0.3] * 20
        labels = [1] * 20 + [0] * 20
        cal, T = temperature_scale(probs, labels)
        assert len(cal) == 40

    def test_temperature_positive(self):
        probs = [0.8] * 10 + [0.2] * 10
        labels = [1] * 8 + [0] * 2 + [0] * 8 + [1] * 2
        _, T = temperature_scale(probs, labels)
        assert T > 0

    def test_overconfident_increases_temperature(self):
        # Model predicts 0.9 but only 50% win → should get T > 1 (softer)
        probs = [0.9] * 30
        labels = [1] * 15 + [0] * 15
        cal, T = temperature_scale(probs, labels)
        assert T > 1.0

    def test_calibrated_probs_in_range(self):
        probs = [0.1, 0.3, 0.5, 0.7, 0.9]
        labels = [0, 0, 1, 1, 1]
        cal, _ = temperature_scale(probs, labels)
        assert all(0.0 <= p <= 1.0 for p in cal)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            temperature_scale([], [])

    def test_original_probs_unchanged(self):
        # Temperature scaling must NOT modify the original list
        probs = [0.8, 0.9, 0.7]
        labels = [0, 1, 1]
        original = list(probs)
        temperature_scale(probs, labels)
        assert probs == original


# ═══════════════════════════════════════════════════════════════════════════════
# § G  Isotonic Regression
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsotonicCalibration:
    def test_returns_same_length(self):
        probs = [0.3, 0.5, 0.7, 0.9]
        labels = [0, 0, 1, 1]
        cal = isotonic_calibrate(probs, labels)
        assert len(cal) == 4

    def test_output_in_range(self):
        probs = [0.1, 0.4, 0.6, 0.9]
        labels = [0, 0, 1, 1]
        cal = isotonic_calibrate(probs, labels)
        assert all(0.0 <= p <= 1.0 for p in cal)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            isotonic_calibrate([], [])

    def test_monotone_output(self):
        # Isotonic regression guarantees monotone output
        probs = [0.2, 0.4, 0.6, 0.8]
        labels = [0, 0, 1, 1]
        cal = isotonic_calibrate(probs, labels)
        for i in range(len(cal) - 1):
            assert cal[i] <= cal[i + 1] + 1e-9

    def test_original_unchanged(self):
        probs = [0.3, 0.6, 0.9]
        labels = [0, 1, 1]
        original = list(probs)
        isotonic_calibrate(probs, labels)
        assert probs == original


# ═══════════════════════════════════════════════════════════════════════════════
# § H  Hard-Rule Invariants (No Patch, No Production Modification)
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardRuleInvariants:
    def test_candidate_patch_created_false_constant(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false_constant(self):
        assert PRODUCTION_MODIFIED is False

    def test_result_candidate_patch_false(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert result.candidate_patch_created is False

    def test_result_production_modified_false(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert result.production_modified is False

    def test_to_dict_enforces_no_patch(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        d = result.to_dict()
        assert d["candidate_patch_created"] is False

    def test_to_dict_enforces_no_production_modified(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        d = result.to_dict()
        assert d["production_modified"] is False

    def test_gate_not_patch(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert result.gate != "PATCH"

    def test_gate_in_valid_set(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert result.gate in {_PROCEED_TO_FEATURE_PHASE, _CALIBRATION_FIRST}

    def test_alpha_enforced(self):
        rows = _make_rows(30)
        with pytest.raises(ValueError, match="alpha must be"):
            run_phase47_shape_repair(rows, alpha=0.3)

    def test_alpha_04_accepted(self):
        rows = _make_rows(30)
        result = run_phase47_shape_repair(rows, alpha=0.4)
        assert result.alpha == 0.4


# ═══════════════════════════════════════════════════════════════════════════════
# § I  Gate Decision Logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateDecision:
    def _make_metrics(self, method: str, brier: float, ece: float, bss: float) -> CalibrationMetrics:
        return CalibrationMetrics(
            method=method,
            brier=brier,
            ece=ece,
            bss_vs_market=bss,
            temperature=None,
            n=100,
        )

    def _make_diagnosis(self, bucket: str, verdict: str) -> BucketDiagnosis:
        return BucketDiagnosis(
            bucket_name=bucket,
            n=50,
            predicted_mean=0.7,
            actual_win_rate=0.5 if verdict == _OVERCONFIDENT else 0.7,
            calibration_gap=0.2 if verdict == _OVERCONFIDENT else 0.0,
            verdict=verdict,
        )

    def test_proceed_when_all_criteria_met(self):
        raw = self._make_metrics("raw", 0.25, 0.08, -0.01)
        # ECE reduction = (0.08 - 0.04) / 0.08 = 50% > 30%
        temp = self._make_metrics("temp", 0.24, 0.04, 0.01)
        iso = self._make_metrics("iso", 0.24, 0.05, 0.01)
        diagnoses = [
            self._make_diagnosis("confidence:high_confidence", _WELL_CALIBRATED),
            self._make_diagnosis("odds_bucket:heavy_favorite", _WELL_CALIBRATED),
        ]
        gate, rationale, *_ = _gate_decision(raw, temp, iso, diagnoses)
        assert gate == _PROCEED_TO_FEATURE_PHASE
        assert len(rationale) > 0

    def test_calibration_first_when_ece_insufficient(self):
        raw = self._make_metrics("raw", 0.25, 0.08, -0.01)
        # ECE reduction = (0.08 - 0.07) / 0.08 ≈ 12.5% < 30%
        temp = self._make_metrics("temp", 0.25, 0.07, -0.01)
        iso = self._make_metrics("iso", 0.25, 0.07, -0.01)
        diagnoses = [
            self._make_diagnosis("confidence:high_confidence", _WELL_CALIBRATED),
            self._make_diagnosis("odds_bucket:heavy_favorite", _WELL_CALIBRATED),
        ]
        gate, _, *_ = _gate_decision(raw, temp, iso, diagnoses)
        assert gate == _CALIBRATION_FIRST

    def test_calibration_first_when_high_conf_still_overconfident(self):
        raw = self._make_metrics("raw", 0.25, 0.10, -0.01)
        temp = self._make_metrics("temp", 0.24, 0.05, 0.01)  # 50% reduction
        iso = self._make_metrics("iso", 0.24, 0.05, 0.01)
        diagnoses = [
            self._make_diagnosis("confidence:high_confidence", _OVERCONFIDENT),  # still bad
            self._make_diagnosis("odds_bucket:heavy_favorite", _WELL_CALIBRATED),
        ]
        gate, _, *_ = _gate_decision(raw, temp, iso, diagnoses)
        assert gate == _CALIBRATION_FIRST

    def test_rationale_non_empty(self):
        raw = self._make_metrics("raw", 0.25, 0.08, -0.01)
        temp = self._make_metrics("temp", 0.24, 0.04, 0.01)
        iso = self._make_metrics("iso", 0.24, 0.05, 0.01)
        diagnoses = [
            self._make_diagnosis("confidence:high_confidence", _WELL_CALIBRATED),
            self._make_diagnosis("odds_bucket:heavy_favorite", _WELL_CALIBRATED),
        ]
        _, rationale, *_ = _gate_decision(raw, temp, iso, diagnoses)
        assert isinstance(rationale, str)
        assert len(rationale) > 20

    def test_ece_reduction_computed_correctly(self):
        raw = self._make_metrics("raw", 0.25, 0.10, -0.01)
        temp = self._make_metrics("temp", 0.24, 0.07, 0.01)   # 30% reduction
        iso = self._make_metrics("iso", 0.24, 0.06, 0.01)    # 40% reduction
        _, _, ece_red_temp, ece_red_iso, *_ = _gate_decision(raw, temp, iso, [])
        assert abs(ece_red_temp - 0.30) < 1e-6
        assert abs(ece_red_iso - 0.40) < 1e-6


# ═══════════════════════════════════════════════════════════════════════════════
# § J  Full Pipeline (run_phase47_shape_repair)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_returns_shape_repair_result(self):
        rows = _make_rows(60)
        result = run_phase47_shape_repair(rows)
        assert isinstance(result, ShapeRepairResult)

    def test_empty_rows_raises(self):
        with pytest.raises(ValueError, match="empty"):
            run_phase47_shape_repair([])

    def test_sample_size_correct(self):
        rows = _make_rows(80)
        result = run_phase47_shape_repair(rows)
        assert result.sample_size == 80

    def test_date_range_populated(self):
        rows = [
            _make_row(0.6, 0.55, 1, game_date="2025-04-01", game_id="A001"),
            _make_row(0.6, 0.55, 0, game_date="2025-09-28", game_id="A002"),
        ]
        result = run_phase47_shape_repair(rows)
        assert result.date_start == "2025-04-01"
        assert result.date_end == "2025-09-28"

    def test_run_id_is_uuid(self):
        rows = _make_rows(40)
        result = run_phase47_shape_repair(rows)
        # Should not raise
        uuid.UUID(result.run_id)

    def test_model_dist_populated(self):
        rows = _make_rows(40)
        result = run_phase47_shape_repair(rows)
        assert result.model_dist is not None
        assert result.model_dist.n == 40

    def test_market_dist_populated(self):
        rows = _make_rows(40)
        result = run_phase47_shape_repair(rows)
        assert result.market_dist is not None
        assert isinstance(result.market_dist, DistributionStats)

    def test_reliability_bins_populated(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert len(result.model_reliability_bins) == 10
        assert len(result.market_reliability_bins) == 10

    def test_raw_metrics_populated(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert result.raw_metrics is not None
        assert result.raw_metrics.method == "raw"
        assert 0.0 <= result.raw_metrics.ece <= 1.0

    def test_temp_metrics_populated(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert result.temp_scale_metrics is not None
        assert result.temp_scale_metrics.method == "temperature_scaling"
        assert result.temp_scale_metrics.temperature is not None

    def test_isotonic_metrics_populated(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert result.isotonic_metrics is not None
        assert result.isotonic_metrics.method == "isotonic_regression"

    def test_to_dict_serialisable(self):
        import json as _json
        rows = _make_rows(40)
        result = run_phase47_shape_repair(rows)
        d = result.to_dict()
        # Should serialise to JSON without error
        dumped = _json.dumps(d)
        assert len(dumped) > 100

    def test_alpha_stored_in_result(self):
        rows = _make_rows(40)
        result = run_phase47_shape_repair(rows)
        assert result.alpha == 0.4

    def test_ece_reduction_fields_are_floats(self):
        rows = _make_rows(50)
        result = run_phase47_shape_repair(rows)
        assert isinstance(result.ece_reduction_temp, float)
        assert isinstance(result.ece_reduction_isotonic, float)

    def test_ece_reduction_non_negative(self):
        # Calibration should not make things worse (isotonic always reduces ECE on train set)
        rows = _mixed_rows(30, 30)
        result = run_phase47_shape_repair(rows)
        # Isotonic on its own training data always achieves ECE >= 0 reduction
        assert result.ece_reduction_isotonic >= 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# § K  Audit Hash
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditHash:
    def test_audit_hash_non_empty(self):
        rows = _make_rows(30)
        h = _compute_audit_hash(rows)
        assert h and len(h) > 0

    def test_audit_hash_is_hex(self):
        rows = _make_rows(30)
        h = _compute_audit_hash(rows)
        int(h, 16)  # raises if not valid hex

    def test_audit_hash_length_64(self):
        rows = _make_rows(30)
        h = _compute_audit_hash(rows)
        assert len(h) == 64

    def test_audit_hash_stable_across_calls(self):
        rows = _make_rows(30)
        h1 = _compute_audit_hash(rows)
        h2 = _compute_audit_hash(rows)
        assert h1 == h2

    def test_audit_hash_differs_with_different_data(self):
        rows_a = _make_rows(30, model_prob=0.6)
        rows_b = _make_rows(30, model_prob=0.7)
        assert _compute_audit_hash(rows_a) != _compute_audit_hash(rows_b)

    def test_result_audit_hash_populated(self):
        rows = _make_rows(40)
        result = run_phase47_shape_repair(rows)
        assert len(result.audit_hash) == 64
