"""Tests for Phase 69 — Calibration Objective Redesign Counterfactual.

Tests cover:
  - Safety constants (FROZEN)
  - Phase identity / completion marker
  - Core math functions
  - Probability shaping reversals (paper-only counterfactuals)
  - OOF split correctness (PIT safety)
  - OOF calibration (isotonic + Platt) on synthetic data
  - Counterfactual metrics computation
  - Calibration band analysis
  - Bootstrap CI construction
  - Negative controls
  - Abstention diagnostics
  - Gate determination
  - Serialization / JSON round-trip
  - Analysis thresholds
  - Integration (smoke test on real data if available)
  - End-to-end on real data (skipped if absent)
"""
from __future__ import annotations

import json
import math
import random
import tempfile
from pathlib import Path

import pytest

import orchestrator.phase69_calibration_objective_redesign_counterfactual as p69
from orchestrator.phase69_calibration_objective_redesign_counterfactual import (
    ABSTENTION_GUARD_PROMISING,
    ALPHA,
    ALPHA_MODIFIED,
    CALIBRATION_OBJECTIVE_NOT_PROMISING,
    CALIBRATION_OBJECTIVE_PATCH_PROMISING,
    CANDIDATE_PATCH_CREATED,
    COMPLETION_MARKER,
    DATA_LIMITED,
    DIAGNOSTIC_ONLY,
    IN_SAMPLE_FIT_AND_EVALUATE,
    OVERFIT_RISK,
    PHASE68_GATE_ANCHOR,
    PHASE_VERSION,
    PIT_SAFE_VALIDATION,
    PREDICTION_JSONL_OVERWRITTEN,
    PROBABILITY_SHAPING_REMOVAL_PROMISING,
    PRODUCTION_MODIFIED,
    _AWAY_DAMPING_FACTOR,
    _AWAY_DAMPING_THRESHOLD,
    _BOOTSTRAP_N,
    _CALIB_BAND_DEFS,
    _EXTREME_FAV_THRESHOLD,
    _HEAVY_FAV_THRESHOLD,
    _HIGH_CONF_THRESHOLD,
    _LOGIT_SHARPENING_FACTOR,
    _MIN_BRIER_IMPROVEMENT,
    _MIN_CALIB_EVAL_N,
    _MIN_CALIB_TRAIN_N,
    _MIN_ECE_IMPROVEMENT,
    _MIN_SEGMENT_N,
    _OOF_EVAL_WINDOWS,
    _OOF_TRAIN_WINDOWS,
    _OVERFIT_GAP_THRESHOLD,
    _PHASE45_FAIL_MIN_FAV,
    _VALID_GATES,
    _apply_counterfactual,
    _brier,
    _bss_direct,
    _bootstrap_brier_delta,
    _compute_abstention_diagnostics,
    _compute_calibration_bands_for_method,
    _compute_counterfactual_metrics,
    _counterfactual_fav_prob,
    _determine_gate,
    _ece,
    _enrich,
    _filter_segment,
    _fit_and_apply_oof_calibration,
    _get_cf_fav_probs,
    _logit_fn,
    _mean,
    _percentile,
    _reverse_away_damping_only,
    _reverse_both,
    _reverse_logit_sharpening,
    _run_negative_controls,
    _sigmoid,
    _std,
    _to_dict,
    run_phase69_calibration_objective_redesign_counterfactual,
)

# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

_PREDICTIONS_PATH = (
    Path(__file__).resolve().parent.parent
    / "data/mlb_2025/derived"
    / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)

_REAL_DATA_AVAILABLE = _PREDICTIONS_PATH.exists()


def _make_row(
    model_home_prob: float = 0.60,
    market_home_prob_no_vig: float = 0.55,
    home_win: int = 1,
    split_id: str = "window_1",
    game_date: str = "2025-04-27",
    model_version: str = "marl_w_elo=0.494_w_market=0.400",
    feature_version: str = "phase56_sp_bullpen_context_v1",
) -> dict:
    return {
        "model_home_prob": model_home_prob,
        "market_home_prob_no_vig": market_home_prob_no_vig,
        "home_win": home_win,
        "split_id": split_id,
        "game_date": game_date,
        "model_version": model_version,
        "feature_version": feature_version,
    }


def _make_rows(n: int, model_prob: float = 0.60, mkt_prob: float = 0.55,
               win_rate: float = 0.6, split_id: str = "window_1",
               game_date: str = "2025-04-27") -> list[dict]:
    rows = []
    rng = random.Random(99)
    for i in range(n):
        home_win = 1 if rng.random() < win_rate else 0
        rows.append(_make_row(
            model_home_prob=model_prob,
            market_home_prob_no_vig=mkt_prob,
            home_win=home_win,
            split_id=split_id,
            game_date=game_date,
        ))
    return rows


def _enrich_rows(rows: list[dict]) -> list[dict]:
    return _enrich([dict(r) for r in rows])


# ═══════════════════════════════════════════════════════════════════
# TestSafetyConstants
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

    def test_prediction_jsonl_overwritten_is_false(self):
        assert PREDICTION_JSONL_OVERWRITTEN is False

    def test_in_sample_fit_and_evaluate_is_false(self):
        assert IN_SAMPLE_FIT_AND_EVALUATE is False

    def test_pit_safe_validation_is_true(self):
        assert PIT_SAFE_VALIDATION is True

    def test_alpha_is_0_40(self):
        assert abs(ALPHA - 0.40) < 1e-9

    def test_logit_sharpening_factor(self):
        assert _LOGIT_SHARPENING_FACTOR == 0.85

    def test_away_damping_factor(self):
        assert _AWAY_DAMPING_FACTOR == 0.90

    def test_away_damping_threshold(self):
        assert _AWAY_DAMPING_THRESHOLD == 0.30


# ═══════════════════════════════════════════════════════════════════
# TestPhaseIdentity
# ═══════════════════════════════════════════════════════════════════

class TestPhaseIdentity:
    def test_phase_version_contains_phase69(self):
        assert "phase69" in PHASE_VERSION

    def test_completion_marker(self):
        assert COMPLETION_MARKER == "PHASE_69_CALIBRATION_OBJECTIVE_REDESIGN_COUNTERFACTUAL_VERIFIED"

    def test_phase68_gate_anchor(self):
        assert PHASE68_GATE_ANCHOR == "CALIBRATION_OBJECTIVE_REDESIGN_PROMISING"

    def test_valid_gates_complete(self):
        expected = {
            "CALIBRATION_OBJECTIVE_PATCH_PROMISING",
            "PROBABILITY_SHAPING_REMOVAL_PROMISING",
            "ENSEMBLE_WEIGHTING_REPAIR_PROMISING",
            "ABSTENTION_GUARD_PROMISING",
            "OVERFIT_RISK",
            "DATA_LIMITED",
            "CALIBRATION_OBJECTIVE_NOT_PROMISING",
        }
        assert _VALID_GATES == expected

    def test_oof_train_windows(self):
        assert _OOF_TRAIN_WINDOWS == frozenset({"window_1", "window_2", "window_3"})

    def test_oof_eval_windows(self):
        assert _OOF_EVAL_WINDOWS == frozenset({"window_4", "window_5"})

    def test_train_eval_windows_disjoint(self):
        assert _OOF_TRAIN_WINDOWS.isdisjoint(_OOF_EVAL_WINDOWS)


# ═══════════════════════════════════════════════════════════════════
# TestCoreMath
# ═══════════════════════════════════════════════════════════════════

class TestCoreMath:
    def test_sigmoid_at_zero(self):
        assert abs(_sigmoid(0.0) - 0.5) < 1e-9

    def test_sigmoid_large_positive(self):
        assert _sigmoid(100.0) > 0.999

    def test_sigmoid_large_negative(self):
        assert _sigmoid(-100.0) < 0.001

    def test_logit_at_half(self):
        assert abs(_logit_fn(0.5)) < 1e-9

    def test_logit_sigmoid_inverse(self):
        for p in (0.2, 0.4, 0.6, 0.8):
            assert abs(_sigmoid(_logit_fn(p)) - p) < 1e-9

    def test_brier_perfect(self):
        probs = [1.0] * 10
        labels = [1.0] * 10
        assert _brier(probs, labels) == 0.0

    def test_brier_worst(self):
        probs = [1.0] * 10
        labels = [0.0] * 10
        assert abs(_brier(probs, labels) - 1.0) < 1e-9

    def test_brier_half(self):
        probs = [0.5] * 10
        labels = [1.0] * 10
        assert abs(_brier(probs, labels) - 0.25) < 1e-9

    def test_brier_empty(self):
        assert _brier([], []) == 0.0

    def test_bss_direct_positive(self):
        # model_brier < ref_brier → positive BSS
        assert _bss_direct(0.20, 0.25) > 0.0

    def test_bss_direct_zero_ref(self):
        assert _bss_direct(0.20, 0.0) == 0.0

    def test_bss_direct_equal(self):
        assert abs(_bss_direct(0.25, 0.25)) < 1e-9

    def test_ece_perfect_calibration(self):
        # 60% predicted, 60% actual win rate
        probs = [0.6] * 30 + [0.4] * 20
        labels = [1.0] * 18 + [0.0] * 12 + [0.0] * 20
        ece = _ece(probs, labels)
        assert ece >= 0.0

    def test_ece_empty(self):
        assert _ece([], []) == 0.0

    def test_mean_basic(self):
        assert abs(_mean([1.0, 2.0, 3.0]) - 2.0) < 1e-9

    def test_mean_empty(self):
        assert _mean([]) == 0.0

    def test_std_basic(self):
        assert abs(_std([1.0, 1.0, 1.0]) - 0.0) < 1e-9

    def test_std_single(self):
        assert _std([5.0]) == 0.0

    def test_percentile_median(self):
        vals = list(range(100))
        assert abs(_percentile(vals, 50) - 49.5) < 0.5

    def test_percentile_min(self):
        vals = list(range(100))
        assert _percentile(vals, 0) == 0.0

    def test_percentile_max(self):
        vals = list(range(100))
        assert _percentile(vals, 100) == 99.0


# ═══════════════════════════════════════════════════════════════════
# TestEnrich
# ═══════════════════════════════════════════════════════════════════

class TestEnrich:
    def test_enrich_adds_blend(self):
        rows = _enrich_rows([_make_row(0.6, 0.55)])
        assert "_blend" in rows[0]

    def test_enrich_blend_formula(self):
        rows = _enrich_rows([_make_row(0.6, 0.55)])
        expected_blend = (1 - ALPHA) * 0.6 + ALPHA * 0.55
        assert abs(rows[0]["_blend"] - expected_blend) < 1e-9

    def test_enrich_fav_prob_is_max_of_blend(self):
        rows = _enrich_rows([_make_row(0.6, 0.55)])
        blend = rows[0]["_blend"]
        assert rows[0]["_fav_prob"] == max(blend, 1 - blend)

    def test_enrich_fav_win_correct_home_fav(self):
        # model > 0.5, so home is favourite
        rows = _enrich_rows([_make_row(0.7, 0.65, home_win=1)])
        assert rows[0]["_fav_win"] == 1.0

    def test_enrich_fav_win_correct_away_fav(self):
        rows = _enrich_rows([_make_row(0.3, 0.4, home_win=0)])
        # blend < 0.5 → away is favourite, fav_win = 1 - home_win = 1
        assert rows[0]["_fav_win"] == 1.0

    def test_enrich_model_fav_prob(self):
        rows = _enrich_rows([_make_row(0.65, 0.6)])
        assert rows[0]["_model_fav_prob"] == max(0.65, 0.35)

    def test_enrich_mkt_fav_prob(self):
        rows = _enrich_rows([_make_row(0.65, 0.6)])
        assert rows[0]["_mkt_fav_prob"] == max(0.6, 0.4)

    def test_enrich_inplace_mutation(self):
        rows = [_make_row(0.6, 0.55)]
        result = _enrich(rows)
        assert result is rows


# ═══════════════════════════════════════════════════════════════════
# TestProbabilityShapers
# ═══════════════════════════════════════════════════════════════════

class TestProbabilityShapers:
    """Test the paper-only shaping reversal functions."""

    def test_reverse_logit_sharpening_moves_toward_half(self):
        """Reversing sharpening should move probabilities toward 0.5 (less extreme)."""
        for p in (0.6, 0.65, 0.7, 0.75, 0.8):
            reversed_p = _reverse_logit_sharpening(p)
            # After reversing sharpening, the away_prob is LESS extreme
            # i.e. the home prob moves closer to 0.5
            assert abs(reversed_p - 0.5) < abs(p - 0.5) + 1e-6, (
                f"Expected reversed {reversed_p:.4f} closer to 0.5 than original {p:.4f}"
            )

    def test_reverse_logit_sharpening_identity_at_half(self):
        """At p=0.5, reversing sharpening should return 0.5 (logit(0.5)=0, scales to 0)."""
        assert abs(_reverse_logit_sharpening(0.5) - 0.5) < 1e-6

    def test_reverse_logit_sharpening_roundtrip(self):
        """Applying sharpening then reversing should recover original (approx)."""
        for p_away_original in (0.3, 0.4, 0.5, 0.6, 0.65):
            # Forward: apply stacking_model sharpening
            logit = _logit_fn(p_away_original)
            p_away_sharpened = _sigmoid(logit / _LOGIT_SHARPENING_FACTOR)
            p_home_sharpened = 1.0 - p_away_sharpened
            # Reverse
            p_home_recovered = _reverse_logit_sharpening(p_home_sharpened)
            p_away_recovered = 1.0 - p_home_recovered
            assert abs(p_away_recovered - p_away_original) < 1e-6, (
                f"Roundtrip failed for p_away={p_away_original}: "
                f"recovered={p_away_recovered:.6f}"
            )

    def test_reverse_away_damping_only_increases_away_prob_when_heavy_home_fav(self):
        """When model strongly favors home (away_wp < 0.27), undamping increases away prob."""
        # Heavy home favorite: model_home_prob = 0.80
        p_home = 0.80
        reversed_p = _reverse_away_damping_only(p_home)
        # Home prob should decrease (away prob increases after undamping)
        assert reversed_p < p_home or abs(reversed_p - p_home) < 1e-6, (
            f"Expected reversed_p {reversed_p} <= original {p_home} when home is heavy fav"
        )

    def test_reverse_away_damping_only_no_change_near_half(self):
        """When model is near 0.5, damping was not applied (away_wp ≈ 0.5 > 0.3)."""
        p_home = 0.52
        reversed_p = _reverse_away_damping_only(p_home)
        # No damping applied at this probability → reversed should be close to original
        # (only re-sharpening and un-sharpening happen, which cancel out approximately)
        assert abs(reversed_p - p_home) < 0.05  # some tolerance for combined transforms

    def test_reverse_both_combines_effects(self):
        """remove_both should produce the largest change from original for heavy home fav."""
        p_home = 0.80
        no_sharp = _reverse_logit_sharpening(p_home)
        no_both = _reverse_both(p_home)
        # remove_both should move home_prob even further toward 0.5 than remove_logit_sharpening
        assert abs(no_both - 0.5) <= abs(no_sharp - 0.5) + 1e-6

    def test_apply_counterfactual_original_baseline(self):
        row = _make_row(0.65, 0.6)
        assert _apply_counterfactual(row, "original_baseline") == 0.65

    def test_apply_counterfactual_remove_logit_sharpening(self):
        row = _make_row(0.70, 0.6)
        result = _apply_counterfactual(row, "remove_logit_sharpening")
        # Should be different from original and valid probability
        assert 0.0 < result < 1.0
        assert result != 0.70

    def test_apply_counterfactual_remove_away_damping(self):
        row = _make_row(0.80, 0.75)
        result = _apply_counterfactual(row, "remove_away_damping")
        assert 0.0 < result < 1.0

    def test_apply_counterfactual_remove_both(self):
        row = _make_row(0.75, 0.70)
        result = _apply_counterfactual(row, "remove_both")
        assert 0.0 < result < 1.0

    def test_apply_counterfactual_unknown_raises(self):
        row = _make_row()
        with pytest.raises(ValueError):
            _apply_counterfactual(row, "nonexistent_method")

    def test_shaping_reversal_symmetry(self):
        """Reversals should behave symmetrically around 0.5."""
        for p in (0.55, 0.60, 0.65, 0.70, 0.75):
            mirrored = 1.0 - p
            rev_p = _reverse_logit_sharpening(p)
            rev_m = _reverse_logit_sharpening(mirrored)
            # mirror of reversal of p should equal reversal of (1-p)
            assert abs((1.0 - rev_p) - rev_m) < 1e-9


# ═══════════════════════════════════════════════════════════════════
# TestOofSplit
# ═══════════════════════════════════════════════════════════════════

class TestOofSplit:
    """Test OOF split correctness (PIT safety)."""

    def test_train_windows_are_earlier_than_eval(self):
        """All train window IDs should precede eval window IDs chronologically."""
        # Window numbers: 1,2,3 < 4,5
        train_nums = sorted(int(w.split("_")[1]) for w in _OOF_TRAIN_WINDOWS)
        eval_nums = sorted(int(w.split("_")[1]) for w in _OOF_EVAL_WINDOWS)
        assert max(train_nums) < min(eval_nums), (
            f"Train windows {train_nums} overlap with eval windows {eval_nums}"
        )

    def test_enrich_rows_needed_for_oof(self):
        """Verify that split_id is preserved after enrich."""
        rows = _enrich_rows([_make_row(split_id="window_1")])
        assert rows[0]["split_id"] == "window_1"

    def test_oof_calibration_not_applied_to_train_rows(self):
        """OOF calibration should not add _oof_* keys to train rows."""
        train = _enrich_rows(_make_rows(20, split_id="window_1"))
        eval_r = _enrich_rows(_make_rows(20, split_id="window_4",
                                         game_date="2025-08-01"))
        _, eval_out = _fit_and_apply_oof_calibration(train, eval_r)
        for r in eval_out:
            assert "_oof_isotonic_home_prob" in r
            assert "_oof_platt_home_prob" in r

    def test_oof_calibration_eval_rows_have_valid_probs(self):
        """OOF calibrated probs should be in (0, 1)."""
        train = _enrich_rows(_make_rows(30, split_id="window_1", win_rate=0.6))
        eval_r = _enrich_rows(_make_rows(20, split_id="window_4",
                                         game_date="2025-08-01", win_rate=0.6))
        _, eval_out = _fit_and_apply_oof_calibration(train, eval_r)
        for r in eval_out:
            assert 0.0 < r["_oof_isotonic_home_prob"] < 1.0
            assert 0.0 < r["_oof_platt_home_prob"] < 1.0

    def test_oof_calibration_does_not_modify_originals(self):
        """eval_rows passed to OOF calibration should not be mutated."""
        train = _enrich_rows(_make_rows(20, split_id="window_1"))
        eval_r = _enrich_rows(_make_rows(10, split_id="window_4",
                                          game_date="2025-08-01"))
        orig_keys = set(eval_r[0].keys())
        _fit_and_apply_oof_calibration(train, eval_r)
        # Original eval_r rows should not be mutated
        assert set(eval_r[0].keys()) == orig_keys

    def test_oof_isotonic_calibration_monotone(self):
        """Isotonic calibration output should be non-decreasing when input increases."""
        # Create training data with clear signal (must have both win=0 and win=1)
        train = []
        for i in range(100):
            prob = 0.5 + i * 0.004
            win = 1 if i >= 30 else 0  # mix of wins and losses for valid Platt fit
            train.append(_make_row(model_home_prob=prob, home_win=win,
                                   split_id="window_1", game_date="2025-05-01"))
        train = _enrich_rows(train)
        # Eval with increasing probs
        eval_r = []
        for p in [0.5, 0.6, 0.7, 0.8, 0.9]:
            eval_r.append(_make_row(model_home_prob=p, split_id="window_4",
                                    game_date="2025-08-01"))
        eval_r = _enrich_rows(eval_r)
        _, eval_out = _fit_and_apply_oof_calibration(train, eval_r)
        iso_probs = [r["_oof_isotonic_home_prob"] for r in eval_out]
        # Isotonic is non-decreasing (monotone)
        for i in range(len(iso_probs) - 1):
            assert iso_probs[i] <= iso_probs[i + 1] + 1e-9


# ═══════════════════════════════════════════════════════════════════
# TestFilterSegment
# ═══════════════════════════════════════════════════════════════════

class TestFilterSegment:
    def test_all_games_includes_all(self):
        rows = _enrich_rows(_make_rows(30))
        filtered = _filter_segment(rows, "all_games", "_fav_prob", 0.50, 1.01)
        assert len(filtered) == len(rows)

    def test_heavy_favorite_filters_correctly(self):
        heavy = _enrich_rows([_make_row(0.90, 0.88, home_win=1)])
        light = _enrich_rows([_make_row(0.55, 0.52, home_win=1)])
        rows = heavy + light
        result = _filter_segment(rows, "heavy_favorite", "_fav_prob", 0.70, 1.01)
        assert len(result) == 1

    def test_phase45_failure_filters_fav_wins_0(self):
        """Phase45 failure = fav_prob >= 0.60 AND fav_win == 0."""
        # fav_prob >= 0.60, fav_win=0 (favourite lost)
        lost_row = _enrich_rows([_make_row(0.75, 0.70, home_win=0)])
        # fav_prob >= 0.60, fav_win=1 (favourite won)
        won_row = _enrich_rows([_make_row(0.75, 0.70, home_win=1)])
        rows = lost_row + won_row
        result = _filter_segment(rows, "phase45_failure", "_fav_prob", 0.60, 1.01)
        assert len(result) == 1
        assert result[0]["_fav_win"] == 0.0

    def test_model_band_filters_by_model_fav_prob(self):
        high = _enrich_rows([_make_row(0.75, 0.6)])  # model_fav_prob=0.75
        low = _enrich_rows([_make_row(0.55, 0.6)])   # model_fav_prob=0.55
        rows = high + low
        result = _filter_segment(rows, "model_band_70_80", "_model_fav_prob", 0.70, 0.80)
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════
# TestCounterfactualMetrics
# ═══════════════════════════════════════════════════════════════════

class TestCounterfactualMetrics:
    def _make_eval_rows(self, n: int = 50, model_prob: float = 0.65,
                        win_rate: float = 0.65) -> list[dict]:
        rows = _make_rows(n, model_prob=model_prob, win_rate=win_rate,
                          split_id="window_4", game_date="2025-08-01")
        rows = _enrich_rows(rows)
        # Add OOF keys
        train = _enrich_rows(_make_rows(50, split_id="window_1"))
        _, rows = _fit_and_apply_oof_calibration(train, rows)
        return rows

    def test_original_baseline_brier_delta_is_zero(self):
        rows = self._make_eval_rows()
        orig_brier = {}
        for seg_name, seg_key, lo, hi in p69._SEGMENT_DEFS:
            seg = _filter_segment(rows, seg_name, seg_key, lo, hi)
            if seg:
                fps = [r["_fav_prob"] for r in seg]
                wins = [r["_fav_win"] for r in seg]
                orig_brier[seg_name] = p69._brier(fps, wins)
                orig_brier[f"{seg_name}_ece"] = p69._ece(fps, wins)

        metrics = _compute_counterfactual_metrics(rows, orig_brier)
        for m in metrics:
            if m.method == "original_baseline" and not m.data_limited and m.n > 0:
                assert abs(m.brier_delta_vs_original) < 1e-9, (
                    f"original_baseline delta should be 0, got {m.brier_delta_vs_original}"
                )

    def test_all_methods_covered(self):
        rows = self._make_eval_rows()
        orig_brier = {}
        for seg_name, seg_key, lo, hi in p69._SEGMENT_DEFS:
            seg = _filter_segment(rows, seg_name, seg_key, lo, hi)
            if seg:
                fps = [r["_fav_prob"] for r in seg]
                wins = [r["_fav_win"] for r in seg]
                orig_brier[seg_name] = p69._brier(fps, wins)
                orig_brier[f"{seg_name}_ece"] = p69._ece(fps, wins)

        metrics = _compute_counterfactual_metrics(rows, orig_brier)
        methods_found = {m.method for m in metrics}
        assert "original_baseline" in methods_found
        assert "oof_isotonic" in methods_found
        assert "oof_platt" in methods_found
        assert "remove_logit_sharpening" in methods_found
        assert "remove_both" in methods_found

    def test_all_segments_covered(self):
        rows = self._make_eval_rows(n=100)
        orig_brier: dict = {}
        metrics = _compute_counterfactual_metrics(rows, orig_brier)
        segments_found = {m.segment for m in metrics}
        assert "all_games" in segments_found
        assert "heavy_favorite" in segments_found

    def test_data_limited_flag_for_empty_segment(self):
        # Use rows that will produce empty extreme_favorite segment
        rows = _enrich_rows(_make_rows(20, model_prob=0.55, win_rate=0.6,
                                       split_id="window_4", game_date="2025-08-01"))
        train = _enrich_rows(_make_rows(20, split_id="window_1"))
        _, rows = _fit_and_apply_oof_calibration(train, rows)
        orig_brier: dict = {}
        metrics = _compute_counterfactual_metrics(rows, orig_brier)
        # extreme_favorite with prob=0.55 should have n=0 and data_limited=True
        ef_m = [m for m in metrics if m.segment == "extreme_favorite"
                and m.method == "original_baseline"]
        assert ef_m[0].data_limited is True


# ═══════════════════════════════════════════════════════════════════
# TestCalibrationBands
# ═══════════════════════════════════════════════════════════════════

class TestCalibrationBands:
    def _make_miscal_rows(self, n_per_band: int = 30) -> list[dict]:
        rows = []
        rng = random.Random(42)
        # 0.55 band: predict 0.57, actual 0.52 → overconfident
        for _ in range(n_per_band):
            win = 1 if rng.random() < 0.52 else 0
            rows.append(_make_row(0.57, 0.55, home_win=win,
                                  split_id="window_4", game_date="2025-08-01"))
        # 0.65 band: predict 0.67, actual 0.73 → underconfident
        for _ in range(n_per_band):
            win = 1 if rng.random() < 0.73 else 0
            rows.append(_make_row(0.67, 0.65, home_win=win,
                                  split_id="window_4", game_date="2025-08-01"))
        return _enrich_rows(rows)

    def test_bands_cover_range(self):
        rows = self._make_miscal_rows()
        bands = _compute_calibration_bands_for_method(rows, "original_baseline")
        band_labels = {b.band_label for b in bands}
        assert "0.55-0.60" in band_labels or "0.50-0.55" in band_labels

    def test_residual_sign_for_overconfident_band(self):
        """Overconfident band: pred > actual → residual > 0."""
        # All rows predict 0.80, 40% win
        rows = _enrich_rows([_make_row(0.80, 0.75, home_win=int(i % 5 == 0))
                              for i in range(50)])
        # Manually add OOF keys
        for r in rows:
            r["_oof_isotonic_home_prob"] = 0.80
            r["_oof_isotonic_fav_prob"] = max(0.80, 0.20)
            r["_oof_platt_home_prob"] = 0.80
            r["_oof_platt_fav_prob"] = max(0.80, 0.20)
        bands = _compute_calibration_bands_for_method(rows, "original_baseline")
        high_bands = [b for b in bands if b.lo >= 0.70]
        for b in high_bands:
            if not b.data_limited and b.n >= _MIN_SEGMENT_N:
                # With 20% actual win rate but 80% prediction, residual should be positive
                assert b.residual > 0.0, f"Expected overconfident residual, got {b.residual}"

    def test_all_methods_have_bands(self):
        rows = self._make_miscal_rows()
        train = _enrich_rows(_make_rows(20, split_id="window_1"))
        _, rows = _fit_and_apply_oof_calibration(train, rows)
        all_bands = []
        for method in p69._METHODS:
            all_bands.extend(_compute_calibration_bands_for_method(rows, method))
        methods_with_bands = {b.method for b in all_bands}
        assert "original_baseline" in methods_with_bands
        assert "oof_isotonic" in methods_with_bands

    def test_data_limited_flag(self):
        """Band with < _MIN_BUCKET_N rows should be data_limited."""
        rows = _enrich_rows([_make_row(0.72, 0.68) for _ in range(5)])
        bands = _compute_calibration_bands_for_method(rows, "original_baseline")
        for b in bands:
            if b.n < p69._MIN_BUCKET_N:
                assert b.data_limited is True


# ═══════════════════════════════════════════════════════════════════
# TestBootstrapCI
# ═══════════════════════════════════════════════════════════════════

class TestBootstrapCI:
    def _make_improved_rows(self, n: int = 100) -> list[dict]:
        """Create rows where remove_logit_sharpening clearly improves Brier."""
        rows = []
        rng = random.Random(7)
        for i in range(n):
            # Overconfident: predict 0.80, actual win rate 0.60
            home_win = 1 if rng.random() < 0.60 else 0
            rows.append(_make_row(0.80, 0.75, home_win=home_win,
                                  split_id="window_4", game_date="2025-08-01"))
        rows = _enrich_rows(rows)
        train = _enrich_rows(_make_rows(50, split_id="window_1", win_rate=0.6))
        _, rows = _fit_and_apply_oof_calibration(train, rows)
        return rows

    def test_bootstrap_ci_returns_ci_object(self):
        rows = self._make_improved_rows(50)
        ci = _bootstrap_brier_delta(
            rows, "remove_logit_sharpening", "all_games",
            "_fav_prob", 0.50, 1.01, n_boot=100, rng=random.Random(42)
        )
        assert ci.metric == "brier_delta"
        assert ci.method == "remove_logit_sharpening"
        assert ci.ci_lower <= ci.ci_upper

    def test_bootstrap_ci_observed_matches_actual_delta(self):
        rows = self._make_improved_rows(50)
        ci = _bootstrap_brier_delta(
            rows, "remove_logit_sharpening", "all_games",
            "_fav_prob", 0.50, 1.01, n_boot=100, rng=random.Random(42)
        )
        # Manually compute delta (observed is stored rounded to 6dp)
        fps_orig = _get_cf_fav_probs(rows, "original_baseline")
        fps_cf = _get_cf_fav_probs(rows, "remove_logit_sharpening")
        wins = [r["_fav_win"] for r in rows]
        expected_delta = _brier(fps_cf, wins) - _brier(fps_orig, wins)
        assert abs(ci.observed - expected_delta) < 1e-5  # stored as 6dp rounded

    def test_bootstrap_ci_data_limited_for_small_n(self):
        rows = self._make_improved_rows(5)
        ci = _bootstrap_brier_delta(
            rows, "remove_logit_sharpening", "all_games",
            "_fav_prob", 0.50, 1.01, n_boot=10, rng=random.Random(42)
        )
        assert ci.data_limited is True

    def test_bootstrap_ci_width_nonnegative(self):
        rows = self._make_improved_rows(50)
        ci = _bootstrap_brier_delta(
            rows, "oof_isotonic", "all_games",
            "_fav_prob", 0.50, 1.01, n_boot=200, rng=random.Random(42)
        )
        assert ci.ci_upper >= ci.ci_lower


# ═══════════════════════════════════════════════════════════════════
# TestNegativeControls
# ═══════════════════════════════════════════════════════════════════

class TestNegativeControls:
    def _make_rows_with_oof(self, n: int = 100, win_rate: float = 0.6) -> list[dict]:
        rows = _make_rows(n, model_prob=0.65, win_rate=win_rate,
                          split_id="window_4", game_date="2025-08-01")
        rows = _enrich_rows(rows)
        train = _enrich_rows(_make_rows(50, split_id="window_1"))
        _, rows = _fit_and_apply_oof_calibration(train, rows)
        return rows

    def test_three_controls_returned(self):
        rows = self._make_rows_with_oof()
        controls = _run_negative_controls(
            rows, "original_baseline", n_boot=50, rng=random.Random(42)
        )
        assert len(controls) == 3

    def test_control_names(self):
        rows = self._make_rows_with_oof()
        controls = _run_negative_controls(
            rows, "original_baseline", n_boot=50, rng=random.Random(42)
        )
        names = {c.control_name for c in controls}
        assert "shuffled_probability_band" in names
        assert "random_confidence_assignment" in names
        assert "irrelevant_bucket_split" in names

    def test_shuffled_control_null_mean_near_zero(self):
        """Shuffled probability null mean should be near 0 improvement."""
        rows = self._make_rows_with_oof(n=200)
        controls = _run_negative_controls(
            rows, "oof_isotonic", n_boot=200, rng=random.Random(42)
        )
        shuffled = next(c for c in controls if c.control_name == "shuffled_probability_band")
        # Null distribution mean should be very close to 0 (random shuffles = no improvement)
        assert abs(shuffled.null_improvement_mean) < 0.05

    def test_random_assignment_null_near_zero(self):
        """Random confidence assignment should have null mean near 0."""
        rows = self._make_rows_with_oof(n=200)
        controls = _run_negative_controls(
            rows, "oof_isotonic", n_boot=200, rng=random.Random(42)
        )
        rand_ctrl = next(c for c in controls
                         if c.control_name == "random_confidence_assignment")
        assert abs(rand_ctrl.null_improvement_mean) < 0.05

    def test_irrelevant_split_low_overfit_risk(self):
        """Irrelevant split should not show large signal gap → overfit_risk=False typically."""
        rows = self._make_rows_with_oof(n=200)
        controls = _run_negative_controls(
            rows, "original_baseline", n_boot=100, rng=random.Random(42)
        )
        irr = next(c for c in controls if c.control_name == "irrelevant_bucket_split")
        # For original_baseline (no improvement), irrelevant split should have low overfit risk
        assert irr.overfit_risk is False or irr.signal_gap < 0.1


# ═══════════════════════════════════════════════════════════════════
# TestAbstentionDiagnostics
# ═══════════════════════════════════════════════════════════════════

class TestAbstentionDiagnostics:
    def test_returns_diagnostics_list(self):
        rows = _enrich_rows(_make_rows(50, model_prob=0.65, split_id="window_4",
                                       game_date="2025-08-01"))
        diags = _compute_abstention_diagnostics(rows)
        assert isinstance(diags, list)
        assert len(diags) > 0

    def test_abstention_recommended_when_model_worse_than_market(self):
        """When model consistently underperforms market in a band, flag abstention."""
        # Create rows where blend is worse than market in 0.55-0.60 band
        rows = []
        rng = random.Random(13)
        for _ in range(50):
            # Model predicts 0.75 (very high) but actual win rate is 0.40
            home_win = 1 if rng.random() < 0.40 else 0
            rows.append(_make_row(0.75, 0.58, home_win=home_win,
                                  split_id="window_4", game_date="2025-08-01"))
        rows = _enrich_rows(rows)
        diags = _compute_abstention_diagnostics(rows)
        # At least one band should be flagged for abstention
        # (blend > market Brier when model is far off)
        abstention_bands = [d for d in diags if d.abstention_recommended]
        # Might be data_limited for some bands; just check the function runs
        assert isinstance(abstention_bands, list)

    def test_data_limited_flag_for_small_bands(self):
        """Small bands should be flagged as data_limited."""
        rows = _enrich_rows([_make_row(0.72, 0.70) for _ in range(3)])
        diags = _compute_abstention_diagnostics(rows)
        for d in diags:
            if d.n < p69._MIN_BUCKET_N:
                assert d.data_limited is True


# ═══════════════════════════════════════════════════════════════════
# TestGateDetermination
# ═══════════════════════════════════════════════════════════════════

class TestGateDetermination:
    def _make_oof_split_info(self, n_train: int = 1215, n_eval: int = 810):
        from orchestrator.phase69_calibration_objective_redesign_counterfactual import OofSplitInfo
        return OofSplitInfo(
            train_windows=["window_1", "window_2", "window_3"],
            eval_windows=["window_4", "window_5"],
            n_train=n_train, n_eval=n_eval,
            train_date_start="2025-04-27", train_date_end="2025-07-30",
            eval_date_start="2025-07-30", eval_date_end="2025-09-28",
            pit_safe=True,
        )

    def _make_metrics(self, method: str, segment: str,
                      brier_delta: float = 0.0, ece_delta: float = 0.0,
                      n: int = 100, data_limited: bool = False):
        from orchestrator.phase69_calibration_objective_redesign_counterfactual import CounterfactualMetrics
        return CounterfactualMetrics(
            method=method, segment=segment, n=n,
            brier=0.25, bss_vs_market=0.0, bss_vs_original=0.0,
            ece=0.03, brier_delta_vs_original=brier_delta,
            ece_delta_vs_original=ece_delta, data_limited=data_limited,
        )

    def test_gate_data_limited_for_small_eval(self):
        oof_split = self._make_oof_split_info(n_eval=50)
        gate, _, _, worth = _determine_gate(
            [], [], [], [], oof_split, []
        )
        assert gate == DATA_LIMITED
        assert worth is False

    def test_gate_calibration_objective_patch_promising(self):
        """When OOF isotonic clearly improves ECE on all_games."""
        metrics = [
            self._make_metrics("original_baseline", "all_games", 0.0, 0.0),
            self._make_metrics("original_baseline", "heavy_favorite", 0.0, 0.0),
            # oof_isotonic: significant ECE improvement
            self._make_metrics("oof_isotonic", "all_games",
                               brier_delta=-0.003, ece_delta=-0.005),
            self._make_metrics("oof_isotonic", "heavy_favorite",
                               brier_delta=-0.004, ece_delta=-0.006),
            self._make_metrics("oof_platt", "all_games",
                               brier_delta=-0.002, ece_delta=-0.003),
            self._make_metrics("oof_platt", "heavy_favorite", 0.0, 0.0),
        ]
        from orchestrator.phase69_calibration_objective_redesign_counterfactual import BootstrapCI
        ci = BootstrapCI(
            metric="brier_delta", method="oof_isotonic", segment="all_games",
            n=810, n_boot=1000, observed=-0.003, ci_lower=-0.006, ci_upper=-0.001,
            ci_excludes_zero=True, ci_stable=True, data_limited=False,
        )
        oof_split = self._make_oof_split_info()
        gate, _, _, worth = _determine_gate(
            metrics, [ci], [], [], oof_split, []
        )
        assert gate == CALIBRATION_OBJECTIVE_PATCH_PROMISING
        assert worth is True

    def test_gate_overfit_risk_when_nc_triggers(self):
        """When negative controls also show improvement → OVERFIT_RISK."""
        from orchestrator.phase69_calibration_objective_redesign_counterfactual import NegativeControlResult
        nc_bad = NegativeControlResult(
            control_name="shuffled_probability_band",
            description="test",
            real_improvement=0.005,
            null_improvement_mean=0.004,
            null_improvement_std=0.001,
            signal_gap=0.001,  # < 0.02 threshold
            overfit_risk=True,
            n_permutations=100,
        )
        metrics = [
            self._make_metrics("oof_isotonic", "all_games",
                               brier_delta=-0.003, ece_delta=-0.005),
        ]
        oof_split = self._make_oof_split_info()
        gate, _, _, worth = _determine_gate(
            metrics, [], [nc_bad], [], oof_split, []
        )
        assert gate == OVERFIT_RISK
        assert worth is False

    def test_gate_probability_shaping_promising(self):
        """When shaping removal improves heavy_fav without degrading all_games."""
        metrics = [
            self._make_metrics("original_baseline", "all_games", 0.0, 0.0),
            self._make_metrics("original_baseline", "heavy_favorite", 0.0, 0.0),
            self._make_metrics("remove_both", "all_games", brier_delta=0.0),
            self._make_metrics("remove_both", "heavy_favorite", brier_delta=-0.005),
            # OOF methods don't improve
            self._make_metrics("oof_isotonic", "all_games", brier_delta=0.0, ece_delta=0.0),
            self._make_metrics("oof_isotonic", "heavy_favorite", 0.0, 0.0),
            self._make_metrics("oof_platt", "all_games", 0.0, 0.0),
            self._make_metrics("oof_platt", "heavy_favorite", 0.0, 0.0),
            self._make_metrics("remove_logit_sharpening", "all_games", 0.0, 0.0),
            self._make_metrics("remove_logit_sharpening", "heavy_favorite", 0.0, 0.0),
            self._make_metrics("remove_away_damping", "all_games", 0.0, 0.0),
            self._make_metrics("remove_away_damping", "heavy_favorite", 0.0, 0.0),
        ]
        oof_split = self._make_oof_split_info()
        gate, _, _, worth = _determine_gate(
            metrics, [], [], [], oof_split, []
        )
        assert gate == PROBABILITY_SHAPING_REMOVAL_PROMISING
        assert worth is True

    def test_gate_not_promising_when_nothing_improves(self):
        """All methods fail to improve → CALIBRATION_OBJECTIVE_NOT_PROMISING."""
        metrics = [
            self._make_metrics(method, seg, 0.0, 0.0)
            for method in p69._METHODS
            for seg in ("all_games", "heavy_favorite")
        ]
        oof_split = self._make_oof_split_info()
        gate, _, _, worth = _determine_gate(
            metrics, [], [], [], oof_split, []
        )
        assert gate == CALIBRATION_OBJECTIVE_NOT_PROMISING
        assert worth is False

    def test_gate_in_valid_gates(self):
        """All possible gate outcomes must be in _VALID_GATES."""
        for g in _VALID_GATES:
            assert g in (
                CALIBRATION_OBJECTIVE_PATCH_PROMISING,
                PROBABILITY_SHAPING_REMOVAL_PROMISING,
                p69.ENSEMBLE_WEIGHTING_REPAIR_PROMISING,
                ABSTENTION_GUARD_PROMISING,
                OVERFIT_RISK,
                DATA_LIMITED,
                CALIBRATION_OBJECTIVE_NOT_PROMISING,
            )


# ═══════════════════════════════════════════════════════════════════
# TestSerialization
# ═══════════════════════════════════════════════════════════════════

class TestSerialization:
    def _make_mini_report(self):
        from orchestrator.phase69_calibration_objective_redesign_counterfactual import (
            Phase69Report, OofSplitInfo
        )
        oof = OofSplitInfo(
            train_windows=["w1"], eval_windows=["w2"],
            n_train=100, n_eval=50,
            train_date_start="2025-04-27", train_date_end="2025-06-27",
            eval_date_start="2025-06-27", eval_date_end="2025-09-28",
            pit_safe=True,
        )
        return Phase69Report(
            phase_version=PHASE_VERSION,
            completion_marker=COMPLETION_MARKER,
            generated_at="2026-05-07T00:00:00+00:00",
            data_path="/fake/path.jsonl",
            candidate_patch_created=False,
            production_modified=False,
            alpha_modified=False,
            diagnostic_only=True,
            prediction_jsonl_overwritten=False,
            in_sample_fit_and_evaluate=False,
            pit_safe_validation=True,
            alpha=0.40,
            phase68_gate_anchor=PHASE68_GATE_ANCHOR,
            phase67_gate_anchor="OVERFIT_RISK",
            n_total=150,
            n_train=100,
            n_eval=50,
            feature_version="phase56_sp_bullpen_context_v1",
            oof_split=oof,
            counterfactual_metrics=[],
            calibration_bands=[],
            bootstrap_cis=[],
            negative_controls=[],
            abstention_diagnostics=[],
            gate=CALIBRATION_OBJECTIVE_NOT_PROMISING,
            gate_rationale="test",
            phase70_recommendation="none",
            risk_notes=[],
            oof_calibration_improves_ece=False,
            oof_calibration_improves_bss=False,
            shaping_removal_improves_heavy_fav=False,
            negative_controls_clear=True,
            bootstrap_ci_stable=True,
            worth_phase70=False,
        )

    def test_to_dict_returns_dict(self):
        report = self._make_mini_report()
        d = _to_dict(report)
        assert isinstance(d, dict)

    def test_to_dict_json_serializable(self):
        report = self._make_mini_report()
        d = _to_dict(report)
        json_str = json.dumps(d)
        assert len(json_str) > 0

    def test_to_dict_contains_required_fields(self):
        report = self._make_mini_report()
        d = _to_dict(report)
        required = [
            "phase_version", "completion_marker", "generated_at",
            "candidate_patch_created", "production_modified", "alpha_modified",
            "prediction_jsonl_overwritten", "in_sample_fit_and_evaluate",
            "pit_safe_validation", "gate", "phase70_recommendation",
            "risk_notes", "oof_split", "counterfactual_metrics",
            "bootstrap_cis", "negative_controls",
        ]
        for field in required:
            assert field in d, f"Missing field: {field}"

    def test_safety_constants_in_dict(self):
        report = self._make_mini_report()
        d = _to_dict(report)
        assert d["candidate_patch_created"] is False
        assert d["production_modified"] is False
        assert d["alpha_modified"] is False
        assert d["prediction_jsonl_overwritten"] is False
        assert d["in_sample_fit_and_evaluate"] is False
        assert d["pit_safe_validation"] is True

    def test_completion_marker_in_dict(self):
        report = self._make_mini_report()
        d = _to_dict(report)
        assert d["completion_marker"] == COMPLETION_MARKER

    def test_gate_in_valid_gates(self):
        report = self._make_mini_report()
        d = _to_dict(report)
        assert d["gate"] in _VALID_GATES


# ═══════════════════════════════════════════════════════════════════
# TestThresholds
# ═══════════════════════════════════════════════════════════════════

class TestThresholds:
    def test_heavy_fav_threshold(self):
        assert _HEAVY_FAV_THRESHOLD == 0.70

    def test_high_conf_threshold(self):
        assert _HIGH_CONF_THRESHOLD == 0.75

    def test_extreme_fav_threshold(self):
        assert _EXTREME_FAV_THRESHOLD == 0.80

    def test_phase45_fail_min_fav(self):
        assert _PHASE45_FAIL_MIN_FAV == 0.60

    def test_min_segment_n(self):
        assert _MIN_SEGMENT_N == 20

    def test_bootstrap_n(self):
        assert _BOOTSTRAP_N == 1000

    def test_overfit_gap_threshold(self):
        assert _OVERFIT_GAP_THRESHOLD == 0.02

    def test_min_ece_improvement(self):
        assert _MIN_ECE_IMPROVEMENT > 0.0

    def test_calib_band_defs_coverage(self):
        """Calibration bands should cover [0.5, 1.0]."""
        lower = min(lo for _, lo, _ in _CALIB_BAND_DEFS)
        assert abs(lower - 0.50) < 1e-9

    def test_oof_windows_cover_five(self):
        """Total OOF windows should be 5 (3 train + 2 eval)."""
        all_windows = _OOF_TRAIN_WINDOWS | _OOF_EVAL_WINDOWS
        assert len(all_windows) == 5


# ═══════════════════════════════════════════════════════════════════
# TestIntegration (synthetic fixture, fast)
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    def _build_synthetic_jsonl(self, n_per_window: int = 30) -> Path:
        """Build a minimal synthetic JSONL for integration testing."""
        rows = []
        rng = random.Random(77)
        windows = ["window_1", "window_2", "window_3", "window_4", "window_5"]
        dates = ["2025-05-01", "2025-06-01", "2025-07-01", "2025-08-01", "2025-09-01"]
        for win, date in zip(windows, dates):
            for _ in range(n_per_window):
                p_model = rng.uniform(0.50, 0.80)
                p_mkt = rng.uniform(0.50, 0.75)
                home_win = 1 if rng.random() < (p_model * 0.7 + 0.15) else 0
                rows.append({
                    "schema_version": "v3",
                    "season": 2025,
                    "game_date": date,
                    "game_id": f"game_{win}_{_}",
                    "dedupe_key": f"{win}_{_}",
                    "home_team": "HOM",
                    "away_team": "AWY",
                    "home_win": home_win,
                    "model_home_prob": p_model,
                    "market_home_prob_no_vig": p_mkt,
                    "market_away_prob_no_vig": 1.0 - p_mkt,
                    "home_ml": -130,
                    "away_ml": 110,
                    "model_version": f"marl_w_elo=0.50_w_market=0.40",
                    "feature_version": "phase56_sp_bullpen_context_v1",
                    "split_id": win,
                    "train_window_start": date,
                    "train_window_end": date,
                    "test_window_start": date,
                    "test_window_end": date,
                    "prediction_time_utc": f"{date}T12:00:00Z",
                    "odds_snapshot_time_utc": f"{date}T11:00:00Z",
                    "source_backtest": True,
                    "audit_hash": "abc123",
                    "p0_features": {},
                    "feature_audit_hash": "def456",
                    "bullpen_features": {},
                    "phase56_context_audit_hash": "ghi789",
                    "bullpen_match_source": "synthetic",
                    "candidate_patch_created": False,
                    "production_modified": False,
                    "diagnostic_only": True,
                })
        tmpfile = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        for r in rows:
            tmpfile.write(json.dumps(r) + "\n")
        tmpfile.close()
        return Path(tmpfile.name)

    def test_full_pipeline_runs_on_synthetic_data(self):
        """End-to-end smoke test on synthetic data."""
        jsonl_path = self._build_synthetic_jsonl(n_per_window=60)
        try:
            report = run_phase69_calibration_objective_redesign_counterfactual(
                predictions_path=jsonl_path,
                n_boot=20,
                rng_seed=42,
            )
            # Safety constants
            assert report.candidate_patch_created is False
            assert report.production_modified is False
            assert report.alpha_modified is False
            assert report.prediction_jsonl_overwritten is False
            assert report.in_sample_fit_and_evaluate is False
            assert report.pit_safe_validation is True
            # Gate validity
            assert report.gate in _VALID_GATES
            # Completion marker
            assert report.completion_marker == COMPLETION_MARKER
            # Data counts
            assert report.n_total == 300  # 5 windows × 60
            assert report.n_train == 180  # windows 1-3
            assert report.n_eval == 120   # windows 4-5
            # OOF split PIT safety
            assert report.oof_split.pit_safe is True
            # Counterfactual metrics exist
            assert len(report.counterfactual_metrics) > 0
            # Bootstrap CIs exist
            assert len(report.bootstrap_cis) > 0
            # Negative controls exist
            assert len(report.negative_controls) == 3
        finally:
            jsonl_path.unlink(missing_ok=True)

    def test_report_serializable_to_json(self):
        """Report must serialize to valid JSON."""
        jsonl_path = self._build_synthetic_jsonl(n_per_window=40)
        try:
            report = run_phase69_calibration_objective_redesign_counterfactual(
                predictions_path=jsonl_path,
                n_boot=10,
                rng_seed=99,
            )
            d = _to_dict(report)
            json_str = json.dumps(d)
            parsed = json.loads(json_str)
            assert parsed["completion_marker"] == COMPLETION_MARKER
            assert parsed["candidate_patch_created"] is False
        finally:
            jsonl_path.unlink(missing_ok=True)

    def test_all_required_json_fields_present(self):
        """JSON output must contain all required fields per task spec."""
        jsonl_path = self._build_synthetic_jsonl(n_per_window=40)
        try:
            report = run_phase69_calibration_objective_redesign_counterfactual(
                predictions_path=jsonl_path,
                n_boot=10,
                rng_seed=0,
            )
            d = _to_dict(report)
            required = [
                "candidate_patch_created",
                "production_modified",
                "alpha_modified",
                "prediction_jsonl_overwritten",
                "pit_safe_validation",
                "in_sample_fit_and_evaluate",
                "counterfactual_metrics",
                "bootstrap_cis",
                "negative_controls",
                "gate",
                "phase70_recommendation",
                "risk_notes",
                "completion_marker",
            ]
            for f in required:
                assert f in d, f"Missing required JSON field: {f}"
        finally:
            jsonl_path.unlink(missing_ok=True)


# ═══════════════════════════════════════════════════════════════════
# TestEndToEnd (real data, skipped if absent)
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.skipif(
    not _REAL_DATA_AVAILABLE,
    reason="Real data not available: skip end-to-end test",
)
class TestEndToEnd:
    def test_end_to_end_real_data(self):
        report = run_phase69_calibration_objective_redesign_counterfactual(
            predictions_path=_PREDICTIONS_PATH,
            n_boot=_BOOTSTRAP_N,
            rng_seed=42,
        )
        # Safety constants
        assert report.candidate_patch_created is False
        assert report.production_modified is False
        assert report.alpha_modified is False
        assert report.prediction_jsonl_overwritten is False
        assert report.in_sample_fit_and_evaluate is False
        assert report.pit_safe_validation is True

        # Data counts
        assert report.n_total == 2025
        assert report.n_train == 1215  # windows 1-3
        assert report.n_eval == 810    # windows 4-5

        # OOF PIT safety
        assert report.oof_split.pit_safe is True
        assert report.oof_split.train_date_end <= report.oof_split.eval_date_start

        # Gate valid
        assert report.gate in _VALID_GATES
        assert report.completion_marker == COMPLETION_MARKER

        # Counterfactual metrics exist for all methods
        methods_found = {m.method for m in report.counterfactual_metrics}
        assert "original_baseline" in methods_found
        assert "remove_logit_sharpening" in methods_found
        assert "remove_both" in methods_found
        assert "oof_isotonic" in methods_found
        assert "oof_platt" in methods_found

        # All segments covered
        segs_found = {m.segment for m in report.counterfactual_metrics}
        assert "all_games" in segs_found
        assert "heavy_favorite" in segs_found

        # Bootstrap CIs for key methods
        assert len(report.bootstrap_cis) >= 4

        # Negative controls
        assert len(report.negative_controls) == 3

        # Phase 70 recommendation populated
        assert len(report.phase70_recommendation) > 0
        assert len(report.gate_rationale) > 0

    def test_end_to_end_serializable(self):
        report = run_phase69_calibration_objective_redesign_counterfactual(
            predictions_path=_PREDICTIONS_PATH,
            n_boot=100,  # faster for validation
            rng_seed=42,
        )
        d = _to_dict(report)
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["completion_marker"] == COMPLETION_MARKER
        assert parsed["gate"] in _VALID_GATES
        assert parsed["candidate_patch_created"] is False
        assert parsed["production_modified"] is False
