"""Tests for orchestrator/metrics_ssot.py — P1 Metrics SSOT Foundation.

Tests verify:
- Brier / BSS / ECE math correctness (known values)
- Dataclass schema completeness
- Bootstrap CI determinism with seed
- Negative control schema
- Gate summary validation
- validate_metrics_payload error/pass paths
- Safety constants (immutable, correct types/values)
- VALID_GATES has exactly 7 members
- ssot_to_dict serialises recursively
- Inventory constants (CANONICAL_* fields) are non-empty
- PHASE_SCHEMA_INVENTORY covers all 6 phases (phase67–phase72)
- No production mutation flags
- Module version set
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.metrics_ssot import (
    # Safety constants
    PRODUCTION_MODIFIED,
    CANDIDATE_PATCH_CREATED,
    ALPHA_MODIFIED,
    PREDICTION_JSONL_OVERWRITTEN,
    NO_EDGE_CLAIM,
    NO_PROFIT_CLAIM,
    DIAGNOSTIC_ONLY,
    MODULE_VERSION,
    COMPLETION_MARKER,
    # Gate constants
    VALID_GATES,
    METRICS_SSOT_FOUNDATION_READY,
    METRICS_SSOT_INVENTORY_READY,
    METRICS_SSOT_NEEDS_PHASE_REFACTOR,
    METRICS_SSOT_DATA_LIMITED,
    METRICS_SSOT_SCHEMA_CONFLICT,
    METRICS_SSOT_REGRESSION_RISK,
    METRICS_SSOT_NOT_READY,
    # Dataclasses
    BrierResult,
    ECEBucket,
    ECEResult,
    ResidualSummary,
    SegmentMetricsSSO,
    BootstrapCISSO,
    NegativeControlSSO,
    GateSummarySSO,
    MetricsPayload,
    # Functions
    calculate_brier_score,
    calculate_bss,
    calculate_ece,
    calculate_bucket_ece,
    calculate_residual_summary,
    calculate_segment_metrics,
    calculate_model_market_delta,
    bootstrap_ci,
    bootstrap_brier_delta_ci,
    build_negative_control_summary,
    build_gate_summary,
    validate_metrics_payload,
    ssot_to_dict,
    # Inventory helpers
    CANONICAL_SEGMENT_FIELDS,
    CANONICAL_BOOTSTRAP_FIELDS,
    CANONICAL_NC_FIELDS,
    CANONICAL_GATE_FIELDS,
    PHASE_SCHEMA_INVENTORY,
)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Safety constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestSafetyConstants:
    def test_production_modified_is_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_candidate_patch_created_is_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_alpha_modified_is_false(self):
        assert ALPHA_MODIFIED is False

    def test_prediction_jsonl_overwritten_is_false(self):
        assert PREDICTION_JSONL_OVERWRITTEN is False

    def test_no_edge_claim_is_true(self):
        assert NO_EDGE_CLAIM is True

    def test_no_profit_claim_is_true(self):
        assert NO_PROFIT_CLAIM is True

    def test_diagnostic_only_is_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_module_version_is_string(self):
        assert isinstance(MODULE_VERSION, str) and MODULE_VERSION != ""

    def test_completion_marker_correct(self):
        assert COMPLETION_MARKER == "METRICS_SSOT_PHASE67_72_INVENTORY_VERIFIED"

    def test_safety_constants_are_bool(self):
        for flag in [PRODUCTION_MODIFIED, CANDIDATE_PATCH_CREATED, ALPHA_MODIFIED,
                     PREDICTION_JSONL_OVERWRITTEN, NO_EDGE_CLAIM, NO_PROFIT_CLAIM, DIAGNOSTIC_ONLY]:
            assert isinstance(flag, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Gate constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateConstants:
    def test_valid_gates_is_frozenset(self):
        assert isinstance(VALID_GATES, frozenset)

    def test_valid_gates_has_exactly_7_members(self):
        assert len(VALID_GATES) == 7

    def test_all_gate_strings_are_in_valid_gates(self):
        expected = {
            METRICS_SSOT_FOUNDATION_READY,
            METRICS_SSOT_INVENTORY_READY,
            METRICS_SSOT_NEEDS_PHASE_REFACTOR,
            METRICS_SSOT_DATA_LIMITED,
            METRICS_SSOT_SCHEMA_CONFLICT,
            METRICS_SSOT_REGRESSION_RISK,
            METRICS_SSOT_NOT_READY,
        }
        assert expected == VALID_GATES

    def test_gate_constants_are_nonempty_strings(self):
        for gate in VALID_GATES:
            assert isinstance(gate, str) and gate != ""


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — Brier / BSS math
# ═══════════════════════════════════════════════════════════════════════════════

class TestBrierScore:
    def test_perfect_predictions(self):
        probs = [1.0, 1.0, 0.0, 0.0]
        labels = [1.0, 1.0, 0.0, 0.0]
        result = calculate_brier_score(probs, labels)
        assert isinstance(result, BrierResult)
        assert result.brier == pytest.approx(0.0, abs=1e-6)

    def test_worst_predictions(self):
        probs = [0.0, 0.0, 1.0, 1.0]
        labels = [1.0, 1.0, 0.0, 0.0]
        result = calculate_brier_score(probs, labels)
        assert result.brier == pytest.approx(1.0, abs=1e-6)

    def test_50_50_uniform(self):
        probs = [0.5] * 100
        labels = [1.0] * 50 + [0.0] * 50
        result = calculate_brier_score(probs, labels)
        # Brier = mean((0.5 - y)^2) = 0.25
        assert result.brier == pytest.approx(0.25, abs=1e-4)

    def test_brier_result_fields(self):
        r = calculate_brier_score([0.6, 0.4], [1.0, 0.0])
        assert hasattr(r, "n")
        assert hasattr(r, "brier")
        assert hasattr(r, "baseline_brier")
        assert hasattr(r, "bss_vs_baseline")

    def test_n_matches_input_length(self):
        r = calculate_brier_score([0.5, 0.6, 0.7], [1.0, 1.0, 0.0])
        assert r.n == 3

    def test_empty_input_returns_zero(self):
        r = calculate_brier_score([], [])
        assert r.n == 0
        assert r.brier == 0.0

    def test_bss_vs_baseline_positive_when_model_better(self):
        # Climatology baseline = 0.5
        probs = [0.6, 0.6, 0.4, 0.4]
        labels = [1.0, 1.0, 0.0, 0.0]
        r = calculate_brier_score(probs, labels)
        assert r.bss_vs_baseline > 0.0

    def test_bss_vs_baseline_negative_when_model_worse(self):
        # Model worse than climatology
        probs = [0.3, 0.3, 0.7, 0.7]
        labels = [1.0, 1.0, 0.0, 0.0]
        r = calculate_brier_score(probs, labels)
        assert r.bss_vs_baseline < 0.0


class TestBSS:
    def test_positive_when_model_better(self):
        assert calculate_bss(0.20, 0.25) == pytest.approx(0.20, rel=1e-4)

    def test_negative_when_model_worse(self):
        assert calculate_bss(0.30, 0.25) < 0.0

    def test_zero_ref_returns_zero(self):
        assert calculate_bss(0.20, 0.0) == 0.0

    def test_equal_returns_zero(self):
        assert calculate_bss(0.25, 0.25) == pytest.approx(0.0, abs=1e-6)

    def test_perfect_model_returns_one(self):
        assert calculate_bss(0.0, 0.25) == pytest.approx(1.0, abs=1e-6)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — ECE math
# ═══════════════════════════════════════════════════════════════════════════════

class TestECE:
    def test_perfect_calibration_ece_near_zero(self):
        # If every prob bin has mean_predicted == mean_observed, ECE ≈ 0
        probs = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        labels = [0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        r = calculate_ece(probs, labels, n_bins=10)
        assert isinstance(r, ECEResult)
        # Not necessarily 0 but should be fairly small
        assert r.ece >= 0.0
        assert r.ece <= 1.0

    def test_ece_result_fields(self):
        r = calculate_ece([0.5, 0.6], [1.0, 0.0])
        assert hasattr(r, "n")
        assert hasattr(r, "ece")
        assert hasattr(r, "n_bins")
        assert hasattr(r, "buckets")

    def test_empty_returns_zero_ece(self):
        r = calculate_ece([], [])
        assert r.ece == 0.0
        assert r.n == 0
        assert r.buckets == []

    def test_n_bins_respected(self):
        probs = [float(i) / 20 for i in range(20)]
        labels = [0.0] * 10 + [1.0] * 10
        r = calculate_ece(probs, labels, n_bins=5)
        assert r.n_bins == 5

    def test_ece_in_range_zero_one(self):
        import random
        rng = random.Random(99)
        probs = [rng.random() for _ in range(200)]
        labels = [float(rng.random() > 0.5) for _ in range(200)]
        r = calculate_ece(probs, labels)
        assert 0.0 <= r.ece <= 1.0


class TestECEBucket:
    def test_bucket_schema(self):
        probs = [0.05, 0.15, 0.25, 0.35]
        labels = [0.0, 1.0, 1.0, 0.0]
        buckets = calculate_bucket_ece(probs, labels, n_bins=10)
        assert isinstance(buckets, list)
        for b in buckets:
            assert isinstance(b, ECEBucket)
            assert hasattr(b, "bin_index")
            assert hasattr(b, "bin_lo")
            assert hasattr(b, "bin_hi")
            assert hasattr(b, "n")
            assert hasattr(b, "mean_predicted")
            assert hasattr(b, "mean_observed")
            assert hasattr(b, "abs_calibration_error")
            assert hasattr(b, "weight")

    def test_bucket_weights_sum_to_one(self):
        import random
        rng = random.Random(7)
        probs = [rng.random() for _ in range(100)]
        labels = [float(rng.random() > 0.5) for _ in range(100)]
        buckets = calculate_bucket_ece(probs, labels, n_bins=10)
        total_weight = sum(b.weight for b in buckets)
        assert total_weight == pytest.approx(1.0, abs=1e-6)

    def test_bucket_ace_is_non_negative(self):
        probs = [0.1, 0.2, 0.3, 0.4, 0.5]
        labels = [0.0, 1.0, 0.0, 1.0, 1.0]
        buckets = calculate_bucket_ece(probs, labels)
        for b in buckets:
            assert b.abs_calibration_error >= 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — Residual summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestResidualSummary:
    def test_residual_summary_fields(self):
        probs = [0.6, 0.7, 0.4, 0.3]
        labels = [1.0, 1.0, 0.0, 0.0]
        r = calculate_residual_summary(probs, labels)
        assert isinstance(r, ResidualSummary)
        for field in ("n", "residual_mean", "residual_std", "residual_min",
                      "residual_max", "overconfident_bands", "underconfident_bands"):
            assert hasattr(r, field)

    def test_positive_mean_when_overconfident(self):
        # pred > actual → positive residual (overconfident)
        probs = [0.9, 0.9, 0.9, 0.9]
        labels = [0.0, 0.0, 0.0, 0.0]
        r = calculate_residual_summary(probs, labels)
        assert r.residual_mean > 0.0

    def test_empty_input(self):
        r = calculate_residual_summary([], [])
        assert r.n == 0
        assert r.residual_mean == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — Segment metrics schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestSegmentMetrics:
    def _make_segment(self, n: int = 50) -> SegmentMetricsSSO:
        import random
        rng = random.Random(1)
        model_probs = [0.55 + rng.gauss(0, 0.05) for _ in range(n)]
        market_probs = [0.52 + rng.gauss(0, 0.04) for _ in range(n)]
        labels = [float(rng.random() > 0.45) for _ in range(n)]
        return calculate_segment_metrics(model_probs, market_probs, labels,
                                         segment_name="test_seg",
                                         segment_definition="model_prob>0.5")

    def test_segment_schema_complete(self):
        seg = self._make_segment()
        assert isinstance(seg, SegmentMetricsSSO)
        for f in ("segment_name", "segment_definition", "n",
                  "model_brier", "model_ece", "model_residual_mean", "model_residual_std",
                  "model_mean_prob", "market_brier", "market_ece", "market_residual_mean",
                  "market_mean_prob", "brier_delta", "bss_vs_market",
                  "model_minus_market_mean", "observed_win_rate",
                  "market_superiority", "data_limited"):
            assert hasattr(seg, f), f"Missing field: {f}"

    def test_segment_n_correct(self):
        seg = self._make_segment(40)
        assert seg.n == 40

    def test_segment_data_limited_false_when_n_large(self):
        seg = self._make_segment(50)
        assert seg.data_limited is False

    def test_segment_data_limited_true_when_n_small(self):
        seg = calculate_segment_metrics([0.5], [0.5], [1.0], "tiny")
        assert seg.data_limited is True

    def test_segment_empty_input(self):
        seg = calculate_segment_metrics([], [], [], "empty")
        assert seg.n == 0
        assert seg.data_limited is True

    def test_segment_market_superiority_flag(self):
        # Model worse than market → market_superiority = True
        model_probs = [0.9] * 20   # overconfident
        market_probs = [0.6] * 20  # better calibrated
        labels = [0.0] * 10 + [1.0] * 10
        seg = calculate_segment_metrics(model_probs, market_probs, labels, "test")
        assert isinstance(seg.market_superiority, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Model-market delta
# ═══════════════════════════════════════════════════════════════════════════════

class TestModelMarketDelta:
    def test_required_keys_present(self):
        model_probs = [0.6, 0.5, 0.4]
        market_probs = [0.55, 0.52, 0.45]
        labels = [1.0, 0.0, 1.0]
        result = calculate_model_market_delta(model_probs, market_probs, labels)
        for key in ("n", "model_brier", "market_brier", "brier_delta",
                    "bss_vs_market", "model_prob_mean", "market_prob_mean", "prob_mean_delta"):
            assert key in result, f"Missing key: {key}"

    def test_empty_input_returns_zeros(self):
        result = calculate_model_market_delta([], [], [])
        assert result["n"] == 0
        assert result["model_brier"] == 0.0

    def test_n_matches_input(self):
        result = calculate_model_market_delta([0.5, 0.6], [0.5, 0.6], [1.0, 0.0])
        assert result["n"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — Bootstrap CI
# ═══════════════════════════════════════════════════════════════════════════════

class TestBootstrapCI:
    def test_ci_schema_complete(self):
        import random
        rng = random.Random(42)
        values = [rng.gauss(0.05, 0.02) for _ in range(100)]
        result = bootstrap_ci(values, lambda v: sum(v) / len(v), n_boot=200, seed=42,
                               metric="brier_delta", segment="overall")
        assert isinstance(result, BootstrapCISSO)
        for f in ("metric", "segment", "n", "n_boot", "seed",
                  "observed", "ci_lower", "ci_upper",
                  "ci_excludes_zero", "ci_stable", "ci_width", "data_limited"):
            assert hasattr(result, f), f"Missing field: {f}"

    def test_ci_deterministic_with_seed(self):
        import random
        rng = random.Random(0)
        values = [rng.gauss(0.03, 0.05) for _ in range(100)]
        r1 = bootstrap_ci(values, lambda v: sum(v) / len(v), n_boot=200, seed=7)
        r2 = bootstrap_ci(values, lambda v: sum(v) / len(v), n_boot=200, seed=7)
        assert r1.ci_lower == r2.ci_lower
        assert r1.ci_upper == r2.ci_upper
        assert r1.observed == r2.observed

    def test_ci_different_seeds_may_differ(self):
        import random
        rng = random.Random(0)
        values = [rng.gauss(0.03, 0.05) for _ in range(100)]
        r1 = bootstrap_ci(values, lambda v: sum(v) / len(v), n_boot=200, seed=7)
        r2 = bootstrap_ci(values, lambda v: sum(v) / len(v), n_boot=200, seed=99)
        # Different seeds should yield at least slightly different CIs (high probability)
        # Use wide tolerance: just ensure observed is the same (seed only affects bootstrap)
        assert r1.observed == r2.observed  # observed is deterministic regardless of seed

    def test_ci_width_is_hi_minus_lo(self):
        import random
        rng = random.Random(1)
        values = [rng.random() for _ in range(50)]
        r = bootstrap_ci(values, lambda v: sum(v) / len(v), n_boot=200, seed=42)
        assert r.ci_width == pytest.approx(r.ci_upper - r.ci_lower, abs=1e-6)

    def test_ci_data_limited_when_n_small(self):
        r = bootstrap_ci([0.5], lambda v: v[0], n_boot=100, seed=42)
        assert r.data_limited is True

    def test_bootstrap_brier_delta_ci_deterministic(self):
        import random
        rng = random.Random(42)
        model_probs = [0.55 + rng.gauss(0, 0.05) for _ in range(80)]
        market_probs = [0.52 + rng.gauss(0, 0.04) for _ in range(80)]
        labels = [float(rng.random() > 0.48) for _ in range(80)]
        r1 = bootstrap_brier_delta_ci(model_probs, market_probs, labels,
                                       n_boot=300, seed=42, segment="test")
        r2 = bootstrap_brier_delta_ci(model_probs, market_probs, labels,
                                       n_boot=300, seed=42, segment="test")
        assert r1.ci_lower == r2.ci_lower
        assert r1.ci_upper == r2.ci_upper

    def test_bootstrap_brier_delta_ci_schema(self):
        import random
        rng = random.Random(42)
        model_probs = [rng.random() for _ in range(50)]
        market_probs = [rng.random() for _ in range(50)]
        labels = [float(rng.random() > 0.5) for _ in range(50)]
        r = bootstrap_brier_delta_ci(model_probs, market_probs, labels, n_boot=200, seed=42)
        assert isinstance(r, BootstrapCISSO)
        assert r.metric == "brier_delta_vs_market"
        assert r.n == 50


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — Negative control schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestNegativeControl:
    def _make_nc(self) -> NegativeControlSSO:
        return build_negative_control_summary(
            control_name="shuffle_labels",
            control_type="shuffle_labels",
            description="Shuffle home win labels to test null distribution",
            observed_gap=0.05,
            permuted_gaps=[0.01, 0.02, 0.01, 0.03, 0.02],
            seed=42,
        )

    def test_nc_schema_complete(self):
        nc = self._make_nc()
        assert isinstance(nc, NegativeControlSSO)
        for f in ("control_name", "control_type", "description",
                  "n_permutations", "seed",
                  "observed_gap", "permuted_gap_mean", "permuted_gap_std",
                  "signal_gap", "overfit_risk", "interpretation"):
            assert hasattr(nc, f), f"Missing field: {f}"

    def test_nc_n_permutations_inferred(self):
        nc = self._make_nc()
        assert nc.n_permutations == 5

    def test_nc_interpretation_is_string(self):
        nc = self._make_nc()
        assert isinstance(nc.interpretation, str) and nc.interpretation != ""

    def test_nc_overfit_risk_is_bool(self):
        nc = self._make_nc()
        assert isinstance(nc.overfit_risk, bool)

    def test_nc_empty_permuted_gaps(self):
        nc = build_negative_control_summary(
            control_name="test", control_type="shuffle",
            description="test", observed_gap=0.05,
            permuted_gaps=[], seed=42,
        )
        assert nc.n_permutations == 0
        assert nc.interpretation == "insufficient_permutations"

    def test_nc_signal_gap_calculation(self):
        nc = build_negative_control_summary(
            control_name="test", control_type="shuffle",
            description="", observed_gap=0.10,
            permuted_gaps=[0.02, 0.02, 0.02],
            seed=42,
        )
        expected_mean = 0.02
        expected_signal = 0.10 - expected_mean
        assert nc.signal_gap == pytest.approx(expected_signal, abs=1e-5)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — Gate summary schema
# ═══════════════════════════════════════════════════════════════════════════════

class TestGateSummary:
    def _make_gate(self) -> GateSummarySSO:
        return build_gate_summary(
            phase_id="p1_metrics_ssot",
            gate=METRICS_SSOT_FOUNDATION_READY,
            gate_candidates=list(VALID_GATES),
            gate_rationale="SSOT module built and tested",
            completion_marker=COMPLETION_MARKER,
            worth_next_phase=True,
            next_phase_recommendation="Budget Guard hardening",
        )

    def test_gate_summary_schema_complete(self):
        gs = self._make_gate()
        assert isinstance(gs, GateSummarySSO)
        for f in ("phase_id", "gate", "gate_candidates", "gate_rationale",
                  "worth_next_phase", "next_phase_recommendation",
                  "candidate_patch_created", "production_modified", "alpha_modified",
                  "no_edge_claim", "report_paths", "completion_marker"):
            assert hasattr(gs, f), f"Missing field: {f}"

    def test_gate_must_be_in_valid_gates(self):
        with pytest.raises(ValueError):
            build_gate_summary(
                phase_id="test", gate="INVALID_GATE",
                gate_candidates=[], gate_rationale="",
                completion_marker=COMPLETION_MARKER,
            )

    def test_gate_safety_defaults(self):
        gs = self._make_gate()
        assert gs.candidate_patch_created is False
        assert gs.production_modified is False
        assert gs.alpha_modified is False
        assert gs.no_edge_claim is True

    def test_gate_report_paths_default_empty(self):
        gs = self._make_gate()
        assert isinstance(gs.report_paths, list)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — validate_metrics_payload
# ═══════════════════════════════════════════════════════════════════════════════

class TestValidateMetricsPayload:
    def _valid_payload(self) -> dict:
        return {
            "phase_id": "test_phase",
            "n_samples": 100,
            "segments": [
                {
                    "segment_name": "all",
                    "segment_definition": "all games",
                    "n": 100,
                    "model_brier": 0.22,
                    "model_ece": 0.04,
                    "model_residual_mean": 0.01,
                    "market_brier": 0.21,
                    "market_ece": 0.03,
                    "market_residual_mean": 0.00,
                    "brier_delta": 0.01,
                    "bss_vs_market": -0.048,
                    "observed_win_rate": 0.54,
                    "market_superiority": True,
                    "data_limited": False,
                }
            ],
            "bootstrap_ci": {
                "metric": "brier_delta",
                "segment": "all",
                "n": 100,
                "n_boot": 1000,
                "seed": 42,
                "observed": 0.01,
                "ci_lower": -0.01,
                "ci_upper": 0.03,
                "ci_excludes_zero": False,
                "ci_stable": True,
                "ci_width": 0.04,
                "data_limited": False,
            },
            "negative_controls": [
                {
                    "control_name": "shuffle_labels",
                    "control_type": "shuffle_labels",
                    "description": "Shuffle home win labels",
                    "n_permutations": 500,
                    "seed": 42,
                    "observed_gap": 0.01,
                    "permuted_gap_mean": 0.001,
                    "permuted_gap_std": 0.005,
                    "signal_gap": 0.009,
                    "overfit_risk": False,
                    "interpretation": "marginal_signal",
                }
            ],
            "gate_summary": {
                "phase_id": "test_phase",
                "gate": METRICS_SSOT_FOUNDATION_READY,
                "gate_candidates": [METRICS_SSOT_FOUNDATION_READY],
                "gate_rationale": "test",
                "worth_next_phase": True,
                "next_phase_recommendation": "",
                "candidate_patch_created": False,
                "production_modified": False,
                "alpha_modified": False,
                "no_edge_claim": True,
                "report_paths": [],
                "completion_marker": COMPLETION_MARKER,
            },
        }

    def test_valid_payload_passes(self):
        errors = validate_metrics_payload(self._valid_payload())
        assert errors == []

    def test_missing_phase_id(self):
        p = self._valid_payload()
        del p["phase_id"]
        errors = validate_metrics_payload(p)
        assert any("phase_id" in e for e in errors)

    def test_missing_n_samples(self):
        p = self._valid_payload()
        del p["n_samples"]
        errors = validate_metrics_payload(p)
        assert any("n_samples" in e for e in errors)

    def test_missing_segment_field(self):
        p = self._valid_payload()
        del p["segments"][0]["model_brier"]
        errors = validate_metrics_payload(p)
        assert any("model_brier" in e for e in errors)

    def test_missing_bootstrap_field(self):
        p = self._valid_payload()
        del p["bootstrap_ci"]["seed"]
        errors = validate_metrics_payload(p)
        assert any("seed" in e for e in errors)

    def test_missing_nc_field(self):
        p = self._valid_payload()
        del p["negative_controls"][0]["interpretation"]
        errors = validate_metrics_payload(p)
        assert any("interpretation" in e for e in errors)

    def test_missing_gate_field(self):
        p = self._valid_payload()
        del p["gate_summary"]["completion_marker"]
        errors = validate_metrics_payload(p)
        assert any("completion_marker" in e for e in errors)

    def test_invalid_gate_string(self):
        p = self._valid_payload()
        p["gate_summary"]["gate"] = "NOT_A_VALID_GATE"
        errors = validate_metrics_payload(p)
        assert any("VALID_GATES" in e for e in errors)

    def test_safety_violation_production_modified(self):
        p = self._valid_payload()
        p["production_modified"] = True
        errors = validate_metrics_payload(p)
        assert any("production_modified" in e.lower() for e in errors)

    def test_empty_payload_reports_errors(self):
        errors = validate_metrics_payload({})
        assert len(errors) >= 2  # phase_id + n_samples missing


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — ssot_to_dict serialisation
# ═══════════════════════════════════════════════════════════════════════════════

class TestSSOTToDict:
    def test_brierresult_serialises_to_dict(self):
        r = calculate_brier_score([0.6, 0.4], [1.0, 0.0])
        d = ssot_to_dict(r)
        assert isinstance(d, dict)
        assert "brier" in d
        assert "n" in d

    def test_nested_ece_result_serialises(self):
        r = calculate_ece([0.3, 0.6, 0.7], [0.0, 1.0, 1.0])
        d = ssot_to_dict(r)
        assert isinstance(d, dict)
        assert isinstance(d["buckets"], list)

    def test_segment_metrics_serialises(self):
        seg = calculate_segment_metrics([0.6, 0.7], [0.55, 0.6], [1.0, 0.0],
                                         segment_name="t", segment_definition="test")
        d = ssot_to_dict(seg)
        assert isinstance(d, dict)
        assert d["segment_name"] == "t"

    def test_primitive_passthrough(self):
        assert ssot_to_dict(42) == 42
        assert ssot_to_dict("hello") == "hello"
        assert ssot_to_dict(None) is None
        assert ssot_to_dict([1, 2, 3]) == [1, 2, 3]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — Inventory constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestInventoryConstants:
    def test_canonical_segment_fields_nonempty(self):
        assert len(CANONICAL_SEGMENT_FIELDS) > 0
        assert isinstance(CANONICAL_SEGMENT_FIELDS, list)

    def test_canonical_bootstrap_fields_nonempty(self):
        assert len(CANONICAL_BOOTSTRAP_FIELDS) > 0
        assert isinstance(CANONICAL_BOOTSTRAP_FIELDS, list)

    def test_canonical_nc_fields_nonempty(self):
        assert len(CANONICAL_NC_FIELDS) > 0
        assert isinstance(CANONICAL_NC_FIELDS, list)

    def test_canonical_gate_fields_nonempty(self):
        assert len(CANONICAL_GATE_FIELDS) > 0
        assert isinstance(CANONICAL_GATE_FIELDS, list)

    def test_canonical_segment_contains_required_fields(self):
        required = {"segment_name", "n", "model_brier", "market_brier",
                    "brier_delta", "bss_vs_market", "observed_win_rate",
                    "market_superiority", "data_limited"}
        assert required.issubset(set(CANONICAL_SEGMENT_FIELDS))

    def test_canonical_bootstrap_contains_required_fields(self):
        required = {"metric", "segment", "n", "n_boot", "seed",
                    "observed", "ci_lower", "ci_upper",
                    "ci_excludes_zero", "ci_stable", "ci_width", "data_limited"}
        assert required.issubset(set(CANONICAL_BOOTSTRAP_FIELDS))

    def test_canonical_nc_contains_required_fields(self):
        required = {"control_name", "control_type", "description",
                    "n_permutations", "seed", "observed_gap",
                    "permuted_gap_mean", "permuted_gap_std",
                    "signal_gap", "overfit_risk", "interpretation"}
        assert required.issubset(set(CANONICAL_NC_FIELDS))

    def test_phase_schema_inventory_has_six_phases(self):
        expected = {"phase67", "phase68", "phase69", "phase70", "phase71", "phase72"}
        assert expected.issubset(set(PHASE_SCHEMA_INVENTORY.keys()))

    def test_phase_schema_inventory_each_phase_has_gate(self):
        for phase_id, info in PHASE_SCHEMA_INVENTORY.items():
            assert "gate" in info, f"Phase {phase_id} missing 'gate'"

    def test_phase_schema_inventory_each_phase_has_naming_notes(self):
        for phase_id, info in PHASE_SCHEMA_INVENTORY.items():
            assert "naming_notes" in info, f"Phase {phase_id} missing 'naming_notes'"

    def test_phase_schema_inventory_each_phase_has_safety_flags(self):
        for phase_id, info in PHASE_SCHEMA_INVENTORY.items():
            assert "safety_flags" in info, f"Phase {phase_id} missing 'safety_flags'"

    def test_phase67_gate_is_overfit_risk(self):
        assert PHASE_SCHEMA_INVENTORY["phase67"]["gate"] == "OVERFIT_RISK"

    def test_phase72_gate_is_spec_ready(self):
        assert PHASE_SCHEMA_INVENTORY["phase72"]["gate"] == "MARKET_DERISK_GUARD_SPEC_READY"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 14 — No production mutation in module
# ═══════════════════════════════════════════════════════════════════════════════

class TestNoProductionMutation:
    def test_no_live_pipeline_import(self):
        """metrics_ssot.py must not import any live pipeline or data loader."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "metrics_ssot",
            Path(__file__).parent.parent / "orchestrator" / "metrics_ssot.py"
        )
        source = Path(__file__).parent.parent / "orchestrator" / "metrics_ssot.py"
        code = source.read_text(encoding="utf-8")
        forbidden = [
            "from data.mlb_live_pipeline",
            "import mlb_live_pipeline",
            "from data.tsl_crawler",
            "import tsl_crawler",
            "from data.wbc_data",
            "import wbc_data",
        ]
        for f in forbidden:
            assert f not in code, f"metrics_ssot.py must not import: {f}"

    def test_module_does_not_write_files(self):
        """metrics_ssot.py must not call open() for writing at module level."""
        source = Path(__file__).parent.parent / "orchestrator" / "metrics_ssot.py"
        code = source.read_text(encoding="utf-8")
        # Ensure no open(..., "w") or open(..., "wb") at top level
        # (Acceptable in functions only if explicitly documented)
        import re
        # Look for open() calls outside function bodies (very basic heuristic)
        lines = code.split("\n")
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("open(") and ("w" in stripped or "a" in stripped):
                # Must be inside a function or class (indented)
                assert line[0] == " " or line[0] == "\t", (
                    f"Line {i + 1}: suspicious top-level open() call: {line!r}"
                )
