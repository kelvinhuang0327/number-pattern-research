"""
Tests for P39I Walk-Forward Feature Ablation.

All fixtures are synthetic — no dependency on local-only enriched CSV.

Acceptance marker: P39I_WALKFORWARD_ABLATION_TESTS_PASS_20260515
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.run_p39i_walkforward_feature_ablation import (
    _validate_columns,
    build_walk_forward_folds,
    evaluate_robust_improvement,
    get_feature_groups,
    run_ablation,
    _eval_baseline_fold,
    _train_and_eval_fold,
)


# ── Fixture helpers ────────────────────────────────────────────────────────────

_N_ROWS = 200
_RANDOM = np.random.RandomState(42)


def _make_enriched_df(n: int = _N_ROWS, seed: int = 42) -> pd.DataFrame:
    """
    Synthetic enriched DataFrame that mirrors the schema of the real enriched CSV.
    Includes p_oof, Statcast rolling features, and y_true_home_win.
    """
    rng = np.random.RandomState(seed)
    dates = pd.date_range("2024-04-15", periods=n, freq="D")
    home_teams = rng.choice(["NYA", "BOS", "BAL", "TBA"], size=n)
    away_teams = rng.choice(["NYA", "BOS", "BAL", "TBA"], size=n)

    return pd.DataFrame(
        {
            "game_id": [f"G{i:04d}" for i in range(n)],
            "game_date": dates,
            "home_team": home_teams,
            "away_team": away_teams,
            "fold_id": rng.randint(0, 4, n),
            "p_oof": rng.uniform(0.35, 0.65, n),
            "model_version": "p38a_walk_forward_logistic_v1",
            "source_prediction_ref": [f"ref_{i}" for i in range(n)],
            "generated_without_y_true": True,
            "bridge_match_status": "MATCHED",
            "home_rolling_avg_launch_speed": rng.uniform(85, 92, n),
            "home_rolling_hard_hit_rate_proxy": rng.uniform(0.2, 0.5, n),
            "home_rolling_barrel_rate_proxy": rng.uniform(0.0, 0.12, n),
            "home_rolling_pa_proxy": rng.uniform(40, 80, n),
            "home_sample_size": rng.randint(5, 15, n),
            "away_rolling_avg_launch_speed": rng.uniform(85, 92, n),
            "away_rolling_hard_hit_rate_proxy": rng.uniform(0.2, 0.5, n),
            "away_rolling_barrel_rate_proxy": rng.uniform(0.0, 0.12, n),
            "away_rolling_pa_proxy": rng.uniform(40, 80, n),
            "away_sample_size": rng.randint(5, 15, n),
            "diff_rolling_avg_launch_speed": rng.uniform(-3, 3, n),
            "diff_rolling_hard_hit_rate_proxy": rng.uniform(-0.1, 0.1, n),
            "diff_sample_size": rng.randint(-5, 5, n),
            "y_true_home_win": rng.randint(0, 2, n),
        }
    ).sort_values("game_date").reset_index(drop=True)


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_chronological_folds_never_train_on_future_dates():
    """Fold k's training data must only include dates strictly before fold k's test window."""
    df = _make_enriched_df()
    folds = build_walk_forward_folds(df, n_folds=5, min_train_rows=10)

    for fold in folds:
        if fold["skipped"]:
            continue
        train_dates = df.iloc[fold["train_idx"]]["game_date"]
        test_dates = df.iloc[fold["test_idx"]]["game_date"]
        max_train = train_dates.max()
        min_test = test_dates.min()
        assert max_train < min_test, (
            f"Fold {fold['fold_id']}: max train date {max_train} >= min test date {min_test}"
        )


def test_no_random_split():
    """Fold ordering must be deterministic and time-based, not random."""
    df = _make_enriched_df()
    folds1 = build_walk_forward_folds(df, n_folds=5, min_train_rows=10)
    folds2 = build_walk_forward_folds(df, n_folds=5, min_train_rows=10)

    for f1, f2 in zip(folds1, folds2):
        assert f1["train_idx"] == f2["train_idx"]
        assert f1["test_idx"] == f2["test_idx"]


def test_baseline_p_oof_uses_p_oof_directly():
    """baseline_p_oof group should use p_oof values from the DataFrame directly (no training)."""
    df = _make_enriched_df(n=100)
    y = df["y_true_home_win"].to_numpy(dtype=float)
    test_idx = list(range(50, 100))

    metrics = _eval_baseline_fold(df, y, test_idx)

    # Manually compute expected Brier
    from sklearn.metrics import brier_score_loss
    p_oof = df.iloc[test_idx]["p_oof"].to_numpy(dtype=float)
    y_test = y[test_idx]
    expected_brier = brier_score_loss(y_test, p_oof)

    assert abs(metrics["brier"] - expected_brier) < 1e-10, (
        f"baseline Brier mismatch: {metrics['brier']} vs {expected_brier}"
    )


def test_feature_groups_contain_expected_columns():
    """Each feature group must include (or exclude) the expected column types."""
    df = _make_enriched_df()
    groups = get_feature_groups(df)

    # baseline_p_oof has no feature cols (direct p_oof use)
    assert groups["baseline_p_oof"] == []

    # diff_features_only should contain diff_* cols
    diff_cols = groups["diff_features_only"]
    assert all(c.startswith("diff_") for c in diff_cols)
    assert len(diff_cols) > 0

    # home_away_rolling_only should contain home_rolling_* and away_rolling_*
    ha_cols = groups["home_away_rolling_only"]
    assert all(c.startswith("home_rolling_") or c.startswith("away_rolling_") for c in ha_cols)
    assert len(ha_cols) > 0

    # full_statcast_rolling should be union of diff + home_away
    full = set(groups["full_statcast_rolling"])
    assert full == set(diff_cols) | set(ha_cols)

    # p_oof_plus_full_statcast must include p_oof
    assert "p_oof" in groups["p_oof_plus_full_statcast"]


def test_rejects_odds_columns():
    """_validate_columns must raise on odds-pattern columns."""
    bad_df = pd.DataFrame({
        "odds_home_ml": [1.9, 2.0],
        "some_feature": [0.5, 0.6],
    })
    with pytest.raises(ValueError, match="Odds columns"):
        _validate_columns(bad_df)


def test_rejects_target_leakage_columns():
    """_validate_columns must raise on target/leakage columns like y_true_home_win."""
    bad_df = pd.DataFrame({
        "y_true_home_win": [1, 0],
        "some_feature": [0.5, 0.6],
    })
    with pytest.raises(ValueError, match="Forbidden target columns"):
        _validate_columns(bad_df)


def test_computes_fold_brier_correctly():
    """_train_and_eval_fold should produce a valid Brier score in [0, 1]."""
    df = _make_enriched_df(n=150)
    y = df["y_true_home_win"].to_numpy(dtype=float)
    train_idx = list(range(100))
    test_idx = list(range(100, 150))
    feature_cols = ["home_rolling_avg_launch_speed", "away_rolling_avg_launch_speed"]

    metrics = _train_and_eval_fold(df, y, train_idx, test_idx, feature_cols)

    assert 0.0 <= metrics["brier"] <= 1.0
    assert not np.isnan(metrics["brier"])


def test_skips_insufficient_train_folds():
    """Folds with fewer than min_train_rows must be marked skipped."""
    df = _make_enriched_df(n=100)
    # Request min_train_rows larger than any single fold
    folds = build_walk_forward_folds(df, n_folds=5, min_train_rows=99)
    # First fold trains on ~20 rows -> should be skipped
    first_fold = folds[0]
    assert first_fold["skipped"] is True
    assert "train rows" in first_fold["skip_reason"]


def test_robust_improvement_rule_pass_example():
    """Deltas that meet all three criteria → ROBUST_IMPROVEMENT."""
    fold_deltas = [-0.003, -0.004, -0.005, -0.002]  # all negative, mean = -0.0035, worst = -0.002
    result = evaluate_robust_improvement(fold_deltas)
    assert result["classification"] == "ROBUST_IMPROVEMENT"
    assert result["mean_delta_pass"] is True
    assert result["pct_improved_pass"] is True
    assert result["worst_degradation_pass"] is True


def test_robust_improvement_rule_fail_example():
    """Deltas that fail criteria → NO_ROBUST_IMPROVEMENT."""
    fold_deltas = [0.001, 0.002, -0.001, 0.003]  # mostly positive, mean > -0.002
    result = evaluate_robust_improvement(fold_deltas)
    assert result["classification"] == "NO_ROBUST_IMPROVEMENT"
    assert result["mean_delta_pass"] is False


def test_deterministic_summary_for_same_fixture():
    """Two calls with identical input must produce identical results."""
    df = _make_enriched_df(n=200, seed=7)
    r1 = run_ablation(df, n_folds=5, min_train_rows=30)
    r2 = run_ablation(df, n_folds=5, min_train_rows=30)

    for group_name in r1["feature_groups"]:
        agg1 = r1["feature_groups"][group_name]["aggregate"]
        agg2 = r2["feature_groups"][group_name]["aggregate"]
        if agg1["mean_delta_brier"] is not None and agg2["mean_delta_brier"] is not None:
            assert abs(agg1["mean_delta_brier"] - agg2["mean_delta_brier"]) < 1e-12, (
                f"Non-deterministic for group {group_name}"
            )


def test_p_oof_plus_full_statcast_includes_p_oof_but_excludes_target():
    """p_oof_plus_full_statcast must include p_oof and must exclude y_true_home_win / target."""
    df = _make_enriched_df()
    groups = get_feature_groups(df)
    cols = groups["p_oof_plus_full_statcast"]

    assert "p_oof" in cols
    assert "y_true_home_win" not in cols
    assert "game_date" not in cols
    assert "home_score" not in cols
    assert "away_score" not in cols


def test_run_ablation_produces_required_keys():
    """run_ablation output must contain all required top-level keys."""
    df = _make_enriched_df(n=200, seed=3)
    result = run_ablation(df, n_folds=5, min_train_rows=30)

    required = ["script_version", "paper_only", "production_ready", "classification",
                "feature_groups", "fold_definitions", "robust_improvement_summary"]
    for key in required:
        assert key in result, f"Missing key: {key}"


def test_run_ablation_paper_only_flags():
    """paper_only must be True and production_ready must be False."""
    df = _make_enriched_df(n=100, seed=5)
    result = run_ablation(df, n_folds=3, min_train_rows=10)
    assert result["paper_only"] is True
    assert result["production_ready"] is False


def test_train_sets_do_not_overlap_with_test_sets():
    """train_idx and test_idx for each fold must be disjoint."""
    df = _make_enriched_df(n=200)
    folds = build_walk_forward_folds(df, n_folds=5, min_train_rows=10)
    for fold in folds:
        if fold["skipped"]:
            continue
        train_set = set(fold["train_idx"])
        test_set = set(fold["test_idx"])
        overlap = train_set & test_set
        assert not overlap, f"Fold {fold['fold_id']}: overlap between train and test: {overlap}"
