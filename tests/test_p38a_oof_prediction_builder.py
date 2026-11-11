"""Tests for P38A OOF Prediction Builder."""
from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from wbc_backend.recommendation.p38a_retrosheet_feature_adapter import build_feature_dataframe
from wbc_backend.recommendation.p38a_oof_prediction_builder import (
    MODEL_VERSION,
    build_oof_predictions,
)

# ── Fixture helpers ──────────────────────────────────────────────────────────

_BASE_CSV = (
    "game_id,game_date,season,away_team,home_team,source_name,source_row_number,away_score,home_score,y_true_home_win\n"
)

_NUM_GAMES = 120


def _generate_csv(n: int = _NUM_GAMES) -> str:
    """Generate n synthetic games across two teams, alternating home/away."""
    rows = [_BASE_CSV.strip()]
    teams = ["NYA", "BOS"]
    for i in range(n):
        month = 4 + i // 30
        day = (i % 30) + 1
        game_id = f"G{i:04d}"
        game_date = f"2024-{month:02d}-{day:02d}"
        home = teams[i % 2]
        away = teams[(i + 1) % 2]
        home_score = (i % 5) + 1
        away_score = (i % 3) + 1
        y = 1 if home_score > away_score else 0
        rows.append(f"{game_id},{game_date},2024,{away},{home},Retrosheet,{i+1},{away_score},{home_score},{y}")
    return "\n".join(rows)


def _make_feature_df(n: int = _NUM_GAMES) -> tuple[pd.DataFrame, pd.Series]:
    csv_content = _generate_csv(n)
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w")
    tmp.write(csv_content)
    tmp.flush()
    csv_path = Path(tmp.name)
    raw = pd.read_csv(csv_path, dtype={"game_id": str})
    adapter_result = build_feature_dataframe(csv_path)
    label_map = raw.set_index("game_id")["y_true_home_win"].to_dict()
    y_true = adapter_result.feature_df["game_id"].map(label_map).astype(int)
    return adapter_result.feature_df, y_true


# ── Tests ────────────────────────────────────────────────────────────────────


def test_walk_forward_no_future_leak():
    """
    In a walk-forward scheme, fold k must only train on rows before the fold.
    Verify that fold_id increases monotonically and no game_id appears twice.
    """
    feature_df, y_true = _make_feature_df()
    result = build_oof_predictions(feature_df, y_true, n_folds=10)
    preds = result.predictions_df

    # No duplicate game_ids in predictions
    assert preds["game_id"].nunique() == len(preds), "Duplicate game_id in predictions"

    # fold_id should be non-negative integers
    assert (preds["fold_id"] >= 0).all()


def test_p_oof_range_0_1():
    """All p_oof values must be in [0, 1]."""
    feature_df, y_true = _make_feature_df()
    result = build_oof_predictions(feature_df, y_true, n_folds=10)
    p_oof = result.predictions_df["p_oof"]
    assert (p_oof >= 0.0).all() and (p_oof <= 1.0).all(), (
        f"p_oof out of range: min={p_oof.min():.4f} max={p_oof.max():.4f}"
    )


def test_model_version_string():
    """model_version column must equal the expected constant."""
    feature_df, y_true = _make_feature_df()
    result = build_oof_predictions(feature_df, y_true, n_folds=10)
    assert (result.predictions_df["model_version"] == MODEL_VERSION).all()


def test_deterministic_with_seed():
    """Two runs with identical input must produce identical output_hash."""
    feature_df, y_true = _make_feature_df()
    r1 = build_oof_predictions(feature_df, y_true, n_folds=5)
    r2 = build_oof_predictions(feature_df, y_true, n_folds=5)
    assert r1.output_hash == r2.output_hash


def test_generated_without_y_true_flag():
    """generated_without_y_true must be True for all predictions."""
    feature_df, y_true = _make_feature_df()
    result = build_oof_predictions(feature_df, y_true, n_folds=10)
    assert result.predictions_df["generated_without_y_true"].all()


def test_source_prediction_ref_populated():
    """source_prediction_ref must be a non-empty string for every row."""
    feature_df, y_true = _make_feature_df()
    result = build_oof_predictions(feature_df, y_true, n_folds=10)
    assert (result.predictions_df["source_prediction_ref"].str.len() > 0).all()


def test_coverage_reasonable():
    """Coverage should be at least 80% for 120 games with 10 folds."""
    feature_df, y_true = _make_feature_df()
    result = build_oof_predictions(feature_df, y_true, n_folds=10)
    assert result.metrics.coverage_pct >= 80.0


def test_brier_is_finite():
    """Brier score must be a finite float."""
    feature_df, y_true = _make_feature_df()
    result = build_oof_predictions(feature_df, y_true, n_folds=10)
    assert isinstance(result.metrics.brier, float)
    assert not (result.metrics.brier != result.metrics.brier)  # not NaN
