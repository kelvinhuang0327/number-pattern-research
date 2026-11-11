"""
P39H — Unit Tests: Time-Aware Enriched Feature Model Comparison

Tests use synthetic fixture DataFrames only — no dependency on local-only CSVs.

Acceptance marker: P39H_MODEL_COMPARISON_TESTS_PASS_20260515
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts.run_p39h_enriched_feature_model_comparison import (
    ENRICHED_FEATURE_COLS,
    STATCAST_FEATURE_COLS,
    _bss,
    check_no_banned_features,
    check_no_target_in_features,
    compute_baseline_metrics,
    compute_enriched_metrics,
    interpret_comparison,
    time_aware_split,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_fixture_df(
    n: int = 200,
    seed: int = 42,
    date_start: str = "2024-04-15",
    date_end: str = "2024-09-30",
) -> pd.DataFrame:
    """
    Produce a synthetic DataFrame with the same schema as the enriched CSV
    plus y_true_home_win for testing.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range(date_start, date_end, periods=n)

    df = pd.DataFrame(
        {
            "game_id": [f"TST-{d.strftime('%Y%m%d')}-0" for d in dates],
            "game_date": dates,
            "fold_id": np.tile(np.arange(10), n // 10 + 1)[:n],
            "p_oof": rng.uniform(0.35, 0.65, n),
            "home_rolling_pa_proxy": rng.integers(20, 80, n).astype(float),
            "home_rolling_avg_launch_speed": rng.uniform(80, 94, n),
            "home_rolling_hard_hit_rate_proxy": rng.uniform(0.25, 0.50, n),
            "home_rolling_barrel_rate_proxy": rng.uniform(0.01, 0.10, n),
            "away_rolling_pa_proxy": rng.integers(20, 80, n).astype(float),
            "away_rolling_avg_launch_speed": rng.uniform(80, 94, n),
            "away_rolling_hard_hit_rate_proxy": rng.uniform(0.25, 0.50, n),
            "away_rolling_barrel_rate_proxy": rng.uniform(0.01, 0.10, n),
            "home_sample_size": rng.integers(3, 10, n).astype(float),
            "away_sample_size": rng.integers(3, 10, n).astype(float),
            "diff_rolling_avg_launch_speed": rng.uniform(-5, 5, n),
            "diff_rolling_hard_hit_rate_proxy": rng.uniform(-0.1, 0.1, n),
            "diff_sample_size": rng.integers(0, 7, n).astype(float),
            "y_true_home_win": rng.integers(0, 2, n).astype(float),
        }
    )
    return df


# ---------------------------------------------------------------------------
# 1. Rejects odds columns in feature list
# ---------------------------------------------------------------------------


def test_rejects_odds_column_in_features() -> None:
    """check_no_banned_features must raise ValueError for odds-related columns."""
    bad_cols = ["home_rolling_pa_proxy", "moneyline_home", "p_oof"]
    with pytest.raises(ValueError, match="Banned odds"):
        check_no_banned_features(bad_cols)


def test_rejects_spread_column_in_features() -> None:
    bad_cols = ["home_rolling_avg_launch_speed", "spread_home", "p_oof"]
    with pytest.raises(ValueError, match="Banned odds"):
        check_no_banned_features(bad_cols)


def test_rejects_vig_column_in_features() -> None:
    bad_cols = ["p_oof", "vig_pct"]
    with pytest.raises(ValueError, match="Banned odds"):
        check_no_banned_features(bad_cols)


def test_accepts_clean_feature_list() -> None:
    """The canonical ENRICHED_FEATURE_COLS must pass the leakage check."""
    check_no_banned_features(ENRICHED_FEATURE_COLS)  # should not raise


# ---------------------------------------------------------------------------
# 2. Rejects target leakage in features
# ---------------------------------------------------------------------------


def test_rejects_target_in_feature_list() -> None:
    cols_with_target = STATCAST_FEATURE_COLS + ["y_true_home_win"]
    with pytest.raises(ValueError, match="Target column"):
        check_no_target_in_features(cols_with_target)


def test_accepts_features_without_target() -> None:
    check_no_target_in_features(ENRICHED_FEATURE_COLS)  # should not raise


# ---------------------------------------------------------------------------
# 3. Time-aware split uses dates correctly
# ---------------------------------------------------------------------------


def test_time_aware_split_correct_sizes() -> None:
    df = _make_fixture_df(n=200)
    train, test = time_aware_split(df, "2024-08-01")
    assert len(train) > 0
    assert len(test) > 0
    assert len(train) + len(test) == len(df)


def test_time_aware_split_no_date_overlap() -> None:
    df = _make_fixture_df(n=200)
    cutoff = pd.Timestamp("2024-08-01")
    train, test = time_aware_split(df, "2024-08-01")
    assert train["game_date"].max() < cutoff
    assert test["game_date"].min() >= cutoff


def test_time_aware_split_train_before_test() -> None:
    df = _make_fixture_df(n=200)
    train, test = time_aware_split(df, "2024-07-01")
    assert train["game_date"].max() < test["game_date"].min()


# ---------------------------------------------------------------------------
# 4. No random split
# ---------------------------------------------------------------------------


def test_split_is_deterministic() -> None:
    """Same DataFrame → same train/test sizes every time (no randomness)."""
    df = _make_fixture_df(n=200, seed=0)
    train1, test1 = time_aware_split(df, "2024-08-01")
    train2, test2 = time_aware_split(df, "2024-08-01")
    assert len(train1) == len(train2)
    assert len(test1) == len(test2)
    assert list(train1["game_id"]) == list(train2["game_id"])


# ---------------------------------------------------------------------------
# 5. Computes Brier correctly
# ---------------------------------------------------------------------------


def test_baseline_brier_perfect_predictions() -> None:
    """With perfect predictions, Brier should be 0."""
    df = _make_fixture_df(n=100)
    df["p_oof"] = df["y_true_home_win"].astype(float)  # perfect
    metrics = compute_baseline_metrics(df)
    assert metrics["brier"] == pytest.approx(0.0, abs=1e-6)


def test_baseline_brier_worst_predictions() -> None:
    """With perfectly wrong predictions, Brier should be 1."""
    df = _make_fixture_df(n=100)
    df["p_oof"] = 1.0 - df["y_true_home_win"]  # always wrong
    metrics = compute_baseline_metrics(df)
    assert metrics["brier"] == pytest.approx(1.0, abs=1e-6)


def test_baseline_brier_range() -> None:
    df = _make_fixture_df(n=100)
    metrics = compute_baseline_metrics(df)
    assert 0.0 <= metrics["brier"] <= 1.0


def test_bss_computation() -> None:
    """BSS = 1 - brier / (base_rate * (1 - base_rate))."""
    base_rate = 0.5
    brier = 0.25
    expected_bss = 1.0 - 0.25 / (0.5 * 0.5)
    assert _bss(brier, base_rate) == pytest.approx(expected_bss, abs=1e-6)


# ---------------------------------------------------------------------------
# 6. Computes log-loss safely
# ---------------------------------------------------------------------------


def test_baseline_log_loss_finite() -> None:
    df = _make_fixture_df(n=100)
    metrics = compute_baseline_metrics(df)
    assert np.isfinite(metrics["log_loss"])
    assert metrics["log_loss"] > 0


def test_enriched_log_loss_finite() -> None:
    df = _make_fixture_df(n=200)
    train, test = time_aware_split(df, "2024-08-01")
    metrics = compute_enriched_metrics(train, test, ENRICHED_FEATURE_COLS, "logistic")
    if "error" not in metrics:
        assert np.isfinite(metrics["log_loss"])
        assert metrics["log_loss"] > 0


# ---------------------------------------------------------------------------
# 7. Handles missing feature columns fail-fast
# ---------------------------------------------------------------------------


def test_enriched_fails_on_missing_feature_col() -> None:
    df = _make_fixture_df(n=200)
    train, test = time_aware_split(df, "2024-08-01")
    bad_cols = ENRICHED_FEATURE_COLS + ["nonexistent_col"]
    with pytest.raises(ValueError, match="Required feature columns not found"):
        compute_enriched_metrics(train, test, bad_cols, "logistic")


# ---------------------------------------------------------------------------
# 8. Handles constant target fail-soft
# ---------------------------------------------------------------------------


def test_enriched_constant_target_returns_error_dict() -> None:
    df = _make_fixture_df(n=200)
    train, test = time_aware_split(df, "2024-08-01")
    # Force constant target
    train = train.copy()
    train["y_true_home_win"] = 1.0
    result = compute_enriched_metrics(train, test, ENRICHED_FEATURE_COLS, "logistic")
    assert result.get("error") == "CONSTANT_TARGET_TRAIN"
    assert result["brier"] is None


# ---------------------------------------------------------------------------
# 9. Summary output deterministic
# ---------------------------------------------------------------------------


def test_metrics_output_deterministic() -> None:
    df = _make_fixture_df(n=200, seed=7)
    train, test = time_aware_split(df, "2024-08-01")
    m1 = compute_enriched_metrics(train, test, ENRICHED_FEATURE_COLS, "logistic")
    m2 = compute_enriched_metrics(train, test, ENRICHED_FEATURE_COLS, "logistic")
    assert m1["brier"] == m2["brier"]
    assert m1["log_loss"] == m2["log_loss"]


# ---------------------------------------------------------------------------
# 10. Feature list contains only allowed columns
# ---------------------------------------------------------------------------


def test_enriched_feature_cols_are_allowed() -> None:
    """ENRICHED_FEATURE_COLS must not contain any banned pattern or target."""
    check_no_banned_features(ENRICHED_FEATURE_COLS)
    check_no_target_in_features(ENRICHED_FEATURE_COLS)
    # All Statcast features must be in the enriched list
    for col in STATCAST_FEATURE_COLS:
        assert col in ENRICHED_FEATURE_COLS, f"Missing Statcast feature: {col}"
    # p_oof must be included
    assert "p_oof" in ENRICHED_FEATURE_COLS


# ---------------------------------------------------------------------------
# interpret_comparison
# ---------------------------------------------------------------------------


def test_interpret_comparison_improved() -> None:
    bl = {"brier": 0.2500, "log_loss": 0.69}
    en = {"brier": 0.2480, "log_loss": 0.68}
    result = interpret_comparison(bl, en)
    assert result["interpretation"] == "IMPROVED"
    assert result["delta_brier"] == pytest.approx(-0.0020, abs=1e-6)


def test_interpret_comparison_degraded() -> None:
    bl = {"brier": 0.2480, "log_loss": 0.68}
    en = {"brier": 0.2510, "log_loss": 0.70}
    result = interpret_comparison(bl, en)
    assert result["interpretation"] == "DEGRADED"
    assert result["delta_brier"] > 0


def test_interpret_comparison_failed_on_constant_target() -> None:
    bl = {"brier": 0.25, "log_loss": 0.69}
    en = {"brier": None, "log_loss": None, "error": "CONSTANT_TARGET_TRAIN"}
    result = interpret_comparison(bl, en)
    assert result["interpretation"] == "FAILED"
    assert result["marker"] == "P39H_ENRICHED_MODEL_COMPARISON_FAILED_20260515"


# P39H_MODEL_COMPARISON_TESTS_PASS_20260515
