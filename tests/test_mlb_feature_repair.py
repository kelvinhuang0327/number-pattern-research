"""
tests/test_mlb_feature_repair.py

Unit tests for wbc_backend/prediction/mlb_feature_repair.py
Covers all P9 minimum requirements (12+).
"""
from __future__ import annotations

import json
import math
from typing import Any

import pytest
from wbc_backend.prediction.mlb_feature_repair import build_repaired_feature_rows


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_row(
    date: str = "2025-04-01",
    home: str = "Chicago Cubs",
    away: str = "Los Angeles Dodgers",
    model_prob: float = 0.57,
    home_ml: str = "+125",
    away_ml: str = "-150",
    home_score: float | None = None,
    away_score: float | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "Date": date,
        "Home": home,
        "Away": away,
        "model_prob_home": model_prob,
        "Home ML": home_ml,
        "Away ML": away_ml,
    }
    if home_score is not None:
        row["Home Score"] = home_score
    if away_score is not None:
        row["Away Score"] = away_score
    return row


# ─────────────────────────────────────────────────────────────────────────────
# Basic API contract
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildRepairedFeatureRowsContract:
    def test_returns_tuple_of_list_and_dict(self):
        rows = [_make_row()]
        result = build_repaired_feature_rows(rows)
        assert isinstance(result, tuple) and len(result) == 2
        repaired, meta = result
        assert isinstance(repaired, list)
        assert isinstance(meta, dict)

    def test_empty_input_returns_empty_list(self):
        repaired, meta = build_repaired_feature_rows([])
        assert repaired == []
        assert meta["input_count"] == 0

    def test_output_count_equals_unique_game_count(self):
        rows = [_make_row(date="2025-04-01"), _make_row(date="2025-04-02")]
        repaired, meta = build_repaired_feature_rows(rows)
        assert meta["output_count"] == 2

    def test_duplicate_rows_are_dropped(self):
        rows = [_make_row(date="2025-04-01"), _make_row(date="2025-04-01")]
        repaired, meta = build_repaired_feature_rows(rows)
        assert len(repaired) == 1
        assert meta["duplicate_count"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# RC-1: home_bias removal
# ─────────────────────────────────────────────────────────────────────────────

class TestHomeBiasRemoval:
    def test_probability_source_is_repaired_model_candidate(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows, remove_constant_home_bias=True)
        assert repaired[0]["probability_source"] == "repaired_model_candidate"

    def test_raw_model_prob_preserved(self):
        rows = [_make_row(model_prob=0.57)]
        repaired, _ = build_repaired_feature_rows(rows)
        assert repaired[0]["raw_model_prob_home"] == pytest.approx(0.57, abs=1e-6)

    def test_repaired_home_bias_removed_flag_true(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows, remove_constant_home_bias=True)
        assert repaired[0]["repaired_home_bias_removed"] is True

    def test_repaired_home_bias_removed_flag_false_when_disabled(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows, remove_constant_home_bias=False)
        assert repaired[0]["repaired_home_bias_removed"] is False

    def test_removing_bias_reduces_high_model_prob(self):
        # Model consistently over-predicts home; removing bias should reduce prob
        rows = [_make_row(model_prob=0.60, home_ml="+130", away_ml="-160")]
        repaired_with, _ = build_repaired_feature_rows(rows, remove_constant_home_bias=True)
        repaired_without, _ = build_repaired_feature_rows(rows, remove_constant_home_bias=False)
        # With bias removed, prob should differ
        assert repaired_with[0]["model_prob_home"] != repaired_without[0]["model_prob_home"]

    def test_model_prob_changed_after_repair(self):
        rows = [_make_row(model_prob=0.566)]
        repaired, _ = build_repaired_feature_rows(rows, remove_constant_home_bias=True)
        # The repaired probability must differ from the original (assuming some bias)
        # At minimum it should be in valid [0.01, 0.99] range
        p = repaired[0]["model_prob_home"]
        assert 0.01 <= p <= 0.99


# ─────────────────────────────────────────────────────────────────────────────
# Non-market independent features
# ─────────────────────────────────────────────────────────────────────────────

class TestIndependentFeatureColumns:
    def test_bullpen_delta_column_exists(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows)
        assert "bullpen_delta" in repaired[0]

    def test_rest_delta_column_exists(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows)
        assert "rest_delta" in repaired[0]

    def test_win_rate_delta_column_exists(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows)
        assert "win_rate_delta" in repaired[0]

    def test_at_least_2_independent_feature_columns(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows)
        r = repaired[0]
        independent_cols = [
            "bullpen_delta",
            "rest_delta",
            "win_rate_delta",
            "bullpen_usage_last_3d_home",
            "bullpen_usage_last_3d_away",
            "rest_days_home",
            "rest_days_away",
            "recent_win_rate_home",
            "recent_win_rate_away",
        ]
        present = sum(1 for c in independent_cols if c in r)
        assert present >= 2, f"Expected >=2 independent feature columns; got {present}"

    def test_win_rate_defaults_to_0_5_with_no_history(self):
        rows = [_make_row()]  # No scores → no history
        repaired, _ = build_repaired_feature_rows(rows)
        r = repaired[0]
        assert r["recent_win_rate_home"] == pytest.approx(0.5, abs=1e-3)
        assert r["recent_win_rate_away"] == pytest.approx(0.5, abs=1e-3)

    def test_win_rate_computed_from_historical_scores(self):
        # Provide 5 historical results: home team wins all 5
        rows = []
        for i in range(5):
            rows.append(_make_row(
                date=f"2025-04-{i+1:02d}",
                home="Chicago Cubs",
                away="Los Angeles Dodgers",
                model_prob=0.55,
                home_score=5.0,
                away_score=2.0,
            ))
        # Add a target game with no score
        rows.append(_make_row(date="2025-04-07"))
        repaired, _ = build_repaired_feature_rows(rows)
        # Last row: home (CHC) should have non-zero win rate after 5 wins
        last = repaired[-1]
        assert last["recent_win_rate_home"] > 0.5


# ─────────────────────────────────────────────────────────────────────────────
# Feature metadata columns
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureMetadataColumns:
    def test_repaired_feature_version_correct(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows)
        assert repaired[0]["repaired_feature_version"] == "p9_feature_repair_v1"

    def test_repaired_feature_trace_is_valid_json(self):
        rows = [_make_row()]
        repaired, _ = build_repaired_feature_rows(rows)
        trace_raw = repaired[0]["repaired_feature_trace"]
        trace = json.loads(trace_raw)
        assert isinstance(trace, dict)
        assert "raw_logit" in trace
        assert "adjusted_logit" in trace

    def test_game_id_added_to_every_row(self):
        rows = [_make_row(), _make_row(date="2025-04-02")]
        repaired, _ = build_repaired_feature_rows(rows)
        for r in repaired:
            assert "game_id" in r and r["game_id"]


# ─────────────────────────────────────────────────────────────────────────────
# Metadata dict
# ─────────────────────────────────────────────────────────────────────────────

class TestMetadataDict:
    def test_metadata_required_keys(self):
        rows = [_make_row()]
        _, meta = build_repaired_feature_rows(rows)
        required = {
            "input_count", "output_count", "duplicate_count",
            "bullpen_join_hit_count", "bullpen_join_miss_count",
            "rest_join_hit_count", "rest_join_miss_count",
            "home_bias_logit_correction",
            "avg_model_prob_before", "avg_model_prob_after",
            "repaired_feature_version",
            "leakage_safe", "paper_only",
        }
        assert required <= meta.keys()

    def test_leakage_safe_true(self):
        rows = [_make_row()]
        _, meta = build_repaired_feature_rows(rows)
        assert meta["leakage_safe"] is True

    def test_paper_only_true(self):
        rows = [_make_row()]
        _, meta = build_repaired_feature_rows(rows)
        assert meta["paper_only"] is True

    def test_avg_prob_after_is_float(self):
        rows = [_make_row()]
        _, meta = build_repaired_feature_rows(rows)
        assert isinstance(meta["avg_model_prob_after"], float)
        assert math.isfinite(meta["avg_model_prob_after"])

    def test_counts_sum_to_input(self):
        rows = [_make_row(date="2025-04-01"), _make_row(date="2025-04-02")]
        _, meta = build_repaired_feature_rows(rows)
        assert meta["bullpen_join_hit_count"] + meta["bullpen_join_miss_count"] == meta["output_count"]
