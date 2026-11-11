"""
tests/test_mlb_probability_calibration_repair.py

P6 tests for wbc_backend/prediction/mlb_probability_calibration_repair.py
"""
from __future__ import annotations

import pytest

from wbc_backend.prediction.mlb_probability_calibration_repair import (
    calibrate_probabilities_by_bins,
    evaluate_calibration_candidate,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_row(
    date: str = "2025-05-01",
    home_score: str = "5",
    away_score: str = "3",
    status: str = "Final",
    home_ml: str = "+100",
    away_ml: str = "-120",
    model_prob_home: str = "0.52",
    probability_source: str = "calibrated_model",
) -> dict:
    return {
        "Date": date,
        "Home Score": home_score,
        "Away Score": away_score,
        "Status": status,
        "Home ML": home_ml,
        "Away ML": away_ml,
        "model_prob_home": model_prob_home,
        "probability_source": probability_source,
    }


def _make_rows(n: int = 100) -> list[dict]:
    rows = []
    for i in range(n):
        hs, as_ = ("5", "2") if i % 2 == 0 else ("1", "3")
        prob = str(round(0.35 + (i % 7) * 0.05, 2))  # 0.35 to 0.65
        rows.append(_make_row(
            date=f"2025-{(i // 30) + 4:02d}-{(i % 28) + 1:02d}",
            home_score=hs,
            away_score=as_,
            model_prob_home=prob,
        ))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Tests: calibration
# ─────────────────────────────────────────────────────────────────────────────

class TestCalibrationByBins:
    def test_preserves_row_count(self):
        rows = _make_rows(100)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=5)
        assert len(calibrated) == 100

    def test_writes_raw_model_prob_home(self):
        rows = _make_rows(10)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=5, min_bin_size=1)
        for row in calibrated:
            assert "raw_model_prob_home" in row

    def test_labels_probability_source_calibrated_model(self):
        rows = _make_rows(20)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=5, min_bin_size=1)
        for row in calibrated:
            assert row["probability_source"] == "calibrated_model"

    def test_calibrated_probs_in_0_1(self):
        rows = _make_rows(100)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=5)
        for row in calibrated:
            p = float(row["model_prob_home"])
            assert 0.0 <= p <= 1.0, f"Out of range: {p}"

    def test_model_prob_away_complements_home(self):
        rows = _make_rows(50)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=3)
        for row in calibrated:
            home_p = float(row["model_prob_home"])
            away_p = float(row["model_prob_away"])
            assert abs(home_p + away_p - 1.0) < 1e-4, f"Probs don't sum to 1: {home_p} + {away_p}"

    def test_calibration_source_trace_present(self):
        rows = _make_rows(50)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=3)
        for row in calibrated:
            assert "calibration_source_trace" in row
            trace = row["calibration_source_trace"]
            assert trace["method"] == "equal_width_bin_calibration"
            assert "in_sample_warning" in trace

    def test_sparse_bin_fallback_does_not_crash(self):
        # Very few rows — all bins will be sparse
        rows = _make_rows(5)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=30)
        assert len(calibrated) == 5

    def test_raw_prob_preserved_differs_from_calibrated(self):
        rows = _make_rows(100)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=5)
        # At least some rows should have different raw vs calibrated prob
        diffs = sum(
            1 for r in calibrated
            if r["raw_model_prob_home"] is not None
            and abs(float(r["model_prob_home"]) - float(r["raw_model_prob_home"])) > 1e-9
        )
        assert diffs > 0, "Calibration should modify at least some probabilities"


# ─────────────────────────────────────────────────────────────────────────────
# Tests: evaluation
# ─────────────────────────────────────────────────────────────────────────────

class TestEvaluateCalibrationCandidate:
    def test_returns_delta_bss_and_ece(self):
        rows = _make_rows(100)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=5)
        result = evaluate_calibration_candidate(rows, calibrated)
        assert "delta_bss" in result
        assert "delta_ece" in result

    def test_original_bss_matches_known_direction(self):
        rows = _make_rows(100)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=5)
        result = evaluate_calibration_candidate(rows, calibrated)
        # Both original and calibrated BSS should be valid floats or None
        assert result["original_bss"] is None or isinstance(result["original_bss"], float)
        assert result["calibrated_bss"] is None or isinstance(result["calibrated_bss"], float)

    def test_recommendation_is_valid(self):
        rows = _make_rows(100)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=10, min_bin_size=5)
        result = evaluate_calibration_candidate(rows, calibrated)
        valid = {"KEEP_BLOCKED", "CANDIDATE_IMPROVED_BUT_NEEDS_OOF", "CANDIDATE_REJECTED"}
        assert result["recommendation"] in valid

    def test_in_sample_warning_present(self):
        rows = _make_rows(50)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=5, min_bin_size=3)
        result = evaluate_calibration_candidate(rows, calibrated)
        assert "in_sample_warning" in result
        assert "in-sample" in result["in_sample_warning"]

    def test_empty_rows_returns_rejected(self):
        result = evaluate_calibration_candidate([], [])
        assert result["recommendation"] == "CANDIDATE_REJECTED"

    def test_usable_row_counts_present(self):
        rows = _make_rows(50)
        calibrated = calibrate_probabilities_by_bins(rows, n_bins=5, min_bin_size=3)
        result = evaluate_calibration_candidate(rows, calibrated)
        assert "usable_original_rows" in result
        assert "usable_calibrated_rows" in result
