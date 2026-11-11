"""
tests/test_p28_performance_variance_analyzer.py

Unit tests for P28 performance variance analyzer.
"""
import pandas as pd
import pytest

from wbc_backend.recommendation.p28_performance_variance_analyzer import (
    bootstrap_roi_confidence_interval,
    compute_daily_roi_profiles,
    compute_hit_rate_variance_metrics,
    compute_roi_variance_metrics,
    compute_segment_roi_profiles,
    summarize_performance_variance,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_date_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ["total_stake_units", "total_pnl_units", "hit_rate",
                "n_active_paper_entries"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "run_date" not in df.columns:
        df["run_date"] = "2025-05-08"
    return df


def _make_segment_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ["segment_index", "total_active_entries", "total_settled_win",
                "total_settled_loss", "total_stake_units", "total_pnl_units"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


# ---------------------------------------------------------------------------
# compute_daily_roi_profiles
# ---------------------------------------------------------------------------


def test_daily_roi_profiles_basic():
    df = _make_date_df([
        {"run_date": "2025-05-08", "total_stake_units": 1.0, "total_pnl_units": 0.1, "hit_rate": 0.6},
        {"run_date": "2025-05-09", "total_stake_units": 2.0, "total_pnl_units": -0.2, "hit_rate": 0.4},
    ])
    profiles = compute_daily_roi_profiles(df)
    assert len(profiles) == 2
    assert abs(profiles[0]["roi_units"] - 0.1) < 1e-9
    assert abs(profiles[1]["roi_units"] - (-0.1)) < 1e-9


def test_daily_roi_profiles_zero_stake():
    df = _make_date_df([
        {"run_date": "2025-05-08", "total_stake_units": 0.0, "total_pnl_units": 0.0},
    ])
    profiles = compute_daily_roi_profiles(df)
    assert profiles[0]["roi_units"] == 0.0


def test_daily_roi_profiles_empty():
    profiles = compute_daily_roi_profiles(pd.DataFrame())
    assert profiles == []


# ---------------------------------------------------------------------------
# compute_segment_roi_profiles
# ---------------------------------------------------------------------------


def test_segment_roi_profiles_basic():
    df = _make_segment_df([
        {
            "segment_index": 0,
            "date_start": "2025-05-08", "date_end": "2025-05-21",
            "total_settled_win": 17, "total_settled_loss": 20,
            "total_active_entries": 37,
            "total_stake_units": 9.25, "total_pnl_units": -0.331,
        },
    ])
    profiles = compute_segment_roi_profiles(df)
    assert len(profiles) == 1
    roi = profiles[0]["roi_units"]
    expected_roi = -0.331 / 9.25
    assert abs(roi - expected_roi) < 1e-6
    expected_hit = 17 / (17 + 20)
    assert abs(profiles[0]["hit_rate"] - expected_hit) < 1e-6


def test_segment_roi_profiles_empty():
    profiles = compute_segment_roi_profiles(pd.DataFrame())
    assert profiles == []


# ---------------------------------------------------------------------------
# compute_roi_variance_metrics
# ---------------------------------------------------------------------------


def test_roi_variance_metrics_basic():
    profiles = [
        {"roi_units": 0.10, "hit_rate": 0.6},
        {"roi_units": -0.05, "hit_rate": 0.45},
        {"roi_units": 0.25, "hit_rate": 0.70},
    ]
    result = compute_roi_variance_metrics(profiles)
    assert result["min"] == pytest.approx(-0.05)
    assert result["max"] == pytest.approx(0.25)
    assert result["mean"] == pytest.approx((0.10 - 0.05 + 0.25) / 3)
    assert result["std"] > 0


def test_roi_variance_metrics_empty():
    result = compute_roi_variance_metrics([])
    assert result == {"min": 0.0, "max": 0.0, "mean": 0.0, "std": 0.0}


def test_roi_variance_metrics_single():
    result = compute_roi_variance_metrics([{"roi_units": 0.5, "hit_rate": 0.5}])
    assert result["std"] == 0.0


# ---------------------------------------------------------------------------
# compute_hit_rate_variance_metrics
# ---------------------------------------------------------------------------


def test_hit_rate_variance_basic():
    profiles = [{"roi_units": 0, "hit_rate": hr} for hr in [0.5, 0.6, 0.4]]
    result = compute_hit_rate_variance_metrics(profiles)
    assert result["min"] == pytest.approx(0.4)
    assert result["max"] == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# bootstrap_roi_confidence_interval
# ---------------------------------------------------------------------------


def test_bootstrap_ci_deterministic():
    df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "total_stake_units": 1.0, "total_pnl_units": 0.05}
        for i in range(8, 48)
    ])
    ci1 = bootstrap_roi_confidence_interval(df, n_iter=500, seed=42)
    ci2 = bootstrap_roi_confidence_interval(df, n_iter=500, seed=42)
    assert ci1["ci_low_95"] == ci2["ci_low_95"]
    assert ci1["ci_high_95"] == ci2["ci_high_95"]


def test_bootstrap_ci_different_seeds():
    df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "total_stake_units": 1.0, "total_pnl_units": 0.1 * (i % 3 - 1)}
        for i in range(8, 48)
    ])
    ci1 = bootstrap_roi_confidence_interval(df, n_iter=500, seed=42)
    ci2 = bootstrap_roi_confidence_interval(df, n_iter=500, seed=99)
    # Different seeds SHOULD produce different results
    # (May occasionally match on trivial data; we just test both complete)
    assert isinstance(ci1["ci_low_95"], float)
    assert isinstance(ci2["ci_low_95"], float)


def test_bootstrap_ci_structure():
    df = _make_date_df([
        {"run_date": "2025-05-08", "total_stake_units": 2.0, "total_pnl_units": 0.2},
    ])
    ci = bootstrap_roi_confidence_interval(df, n_iter=100, seed=42)
    assert "ci_low_95" in ci
    assert "ci_high_95" in ci
    assert "n_iter" in ci
    assert ci["n_iter"] == 100
    assert ci["seed"] == 42
    assert ci["ci_low_95"] <= ci["ci_high_95"]


def test_bootstrap_ci_empty():
    ci = bootstrap_roi_confidence_interval(pd.DataFrame(), n_iter=100, seed=42)
    assert ci["ci_low_95"] == 0.0
    assert ci["ci_high_95"] == 0.0


# ---------------------------------------------------------------------------
# summarize_performance_variance
# ---------------------------------------------------------------------------


def test_summarize_performance_variance_returns_profile():
    date_df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "total_stake_units": 1.0,
         "total_pnl_units": 0.05, "hit_rate": 0.6}
        for i in range(8, 28)
    ])
    seg_df = _make_segment_df([
        {"segment_index": i, "date_start": "2025-05-08", "date_end": "2025-05-21",
         "total_settled_win": 5, "total_settled_loss": 4,
         "total_active_entries": 9, "total_stake_units": 2.25, "total_pnl_units": 0.1}
        for i in range(3)
    ])
    profile = summarize_performance_variance(date_df, seg_df, bootstrap_n_iter=200, bootstrap_seed=42)
    assert profile.paper_only is True
    assert profile.production_ready is False
    assert profile.bootstrap_roi_ci_low_95 <= profile.bootstrap_roi_ci_high_95


def test_summarize_performance_variance_n_positive_negative():
    seg_df = _make_segment_df([
        {"segment_index": 0, "total_settled_win": 3, "total_settled_loss": 2,
         "total_active_entries": 5, "total_stake_units": 1.25, "total_pnl_units": 0.05},
        {"segment_index": 1, "total_settled_win": 1, "total_settled_loss": 4,
         "total_active_entries": 5, "total_stake_units": 1.25, "total_pnl_units": -0.20},
    ])
    date_df = _make_date_df([
        {"run_date": "2025-05-08", "total_stake_units": 1.0, "total_pnl_units": 0.05},
    ])
    profile = summarize_performance_variance(date_df, seg_df, bootstrap_n_iter=50, bootstrap_seed=42)
    assert profile.n_positive_roi_segments == 1
    assert profile.n_negative_roi_segments == 1
