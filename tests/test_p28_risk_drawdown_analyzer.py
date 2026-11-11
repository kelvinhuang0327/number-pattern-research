"""
tests/test_p28_risk_drawdown_analyzer.py

Unit tests for P28 risk and drawdown analyzer.
"""
import pandas as pd
import pytest

from wbc_backend.recommendation.p28_risk_drawdown_analyzer import (
    build_daily_equity_curve,
    compute_loss_cluster_summary,
    compute_max_consecutive_losing_days,
    compute_max_drawdown,
    summarize_risk_profile,
)
from wbc_backend.recommendation.p28_true_date_stability_contract import (
    HIGH_LOSING_STREAK_DAYS,
    MAX_DRAWDOWN_PCT_LIMIT,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_date_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    for col in ["total_pnl_units", "total_stake_units", "n_active_paper_entries"]:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    if "run_date" not in df.columns:
        df["run_date"] = "2025-05-08"
    return df


# ---------------------------------------------------------------------------
# build_daily_equity_curve
# ---------------------------------------------------------------------------


def test_equity_curve_ascending():
    df = _make_date_df([
        {"run_date": "2025-05-08", "total_pnl_units": 1.0},
        {"run_date": "2025-05-09", "total_pnl_units": 2.0},
        {"run_date": "2025-05-10", "total_pnl_units": 1.5},
    ])
    curve = build_daily_equity_curve(df)
    assert list(curve.values) == pytest.approx([1.0, 3.0, 4.5])


def test_equity_curve_sorted_by_date():
    df = _make_date_df([
        {"run_date": "2025-05-10", "total_pnl_units": 1.0},
        {"run_date": "2025-05-08", "total_pnl_units": 2.0},
        {"run_date": "2025-05-09", "total_pnl_units": -0.5},
    ])
    curve = build_daily_equity_curve(df)
    assert list(curve.index) == ["2025-05-08", "2025-05-09", "2025-05-10"]
    # cumsum: 2.0, 1.5, 2.5
    assert list(curve.values) == pytest.approx([2.0, 1.5, 2.5])


def test_equity_curve_empty():
    curve = build_daily_equity_curve(pd.DataFrame())
    assert curve.empty


# ---------------------------------------------------------------------------
# compute_max_drawdown
# ---------------------------------------------------------------------------


def test_max_drawdown_basic():
    # Equity: 1, 3, 2, 4, 1 → peak=4, trough=1 → dd=3 units
    curve = pd.Series([1.0, 3.0, 2.0, 4.0, 1.0])
    result = compute_max_drawdown(curve)
    assert result["max_drawdown_units"] == pytest.approx(3.0)
    # pct = 3/4 * 100 = 75%
    assert result["max_drawdown_pct"] == pytest.approx(75.0)
    assert result["drawdown_exceeds_limit"] is True


def test_max_drawdown_no_drawdown():
    # Strictly ascending → no drawdown
    curve = pd.Series([1.0, 2.0, 3.0, 4.0])
    result = compute_max_drawdown(curve)
    assert result["max_drawdown_units"] == pytest.approx(0.0)
    assert result["max_drawdown_pct"] == pytest.approx(0.0)
    assert result["drawdown_exceeds_limit"] is False


def test_max_drawdown_within_limit():
    # Small drawdown
    curve = pd.Series([10.0, 9.0, 11.0])
    result = compute_max_drawdown(curve)
    assert result["max_drawdown_pct"] < MAX_DRAWDOWN_PCT_LIMIT
    assert result["drawdown_exceeds_limit"] is False


def test_max_drawdown_empty():
    result = compute_max_drawdown(pd.Series(dtype=float))
    assert result["max_drawdown_units"] == 0.0
    assert result["drawdown_exceeds_limit"] is False


# ---------------------------------------------------------------------------
# compute_max_consecutive_losing_days
# ---------------------------------------------------------------------------


def test_max_consecutive_losing_days_basic():
    df = _make_date_df([
        {"run_date": "2025-05-08", "total_pnl_units": -1.0},
        {"run_date": "2025-05-09", "total_pnl_units": -0.5},
        {"run_date": "2025-05-10", "total_pnl_units": 1.0},
        {"run_date": "2025-05-11", "total_pnl_units": -2.0},
    ])
    assert compute_max_consecutive_losing_days(df) == 2


def test_max_consecutive_losing_days_zero():
    df = _make_date_df([
        {"run_date": "2025-05-08", "total_pnl_units": 1.0},
        {"run_date": "2025-05-09", "total_pnl_units": 0.5},
    ])
    assert compute_max_consecutive_losing_days(df) == 0


def test_max_consecutive_losing_days_neutral_breaks_streak():
    df = _make_date_df([
        {"run_date": "2025-05-08", "total_pnl_units": -1.0},
        {"run_date": "2025-05-09", "total_pnl_units": 0.0},  # neutral breaks streak
        {"run_date": "2025-05-10", "total_pnl_units": -1.0},
    ])
    assert compute_max_consecutive_losing_days(df) == 1


def test_max_consecutive_losing_days_all_losing():
    df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "total_pnl_units": -0.1}
        for i in range(8, 16)  # 8 consecutive losing days
    ])
    result = compute_max_consecutive_losing_days(df)
    assert result == 8
    assert result >= HIGH_LOSING_STREAK_DAYS


def test_max_consecutive_losing_days_empty():
    assert compute_max_consecutive_losing_days(pd.DataFrame()) == 0


# ---------------------------------------------------------------------------
# compute_loss_cluster_summary
# ---------------------------------------------------------------------------


def test_loss_cluster_summary_basic():
    df = _make_date_df([
        {"run_date": "2025-05-08", "total_pnl_units": -1.0},
        {"run_date": "2025-05-09", "total_pnl_units": -0.5},  # cluster 1
        {"run_date": "2025-05-10", "total_pnl_units": 1.0},
        {"run_date": "2025-05-11", "total_pnl_units": -0.5},
        {"run_date": "2025-05-12", "total_pnl_units": 0.3},
    ])
    result = compute_loss_cluster_summary(df)
    assert result["total_losing_days"] == 3
    assert result["total_winning_days"] == 2
    assert result["n_loss_clusters"] == 1
    assert result["max_consecutive_losing_days"] == 2


def test_loss_cluster_summary_empty():
    result = compute_loss_cluster_summary(pd.DataFrame())
    assert result["total_losing_days"] == 0
    assert result["high_losing_streak"] is False


def test_loss_cluster_high_streak_flag():
    df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "total_pnl_units": -0.1}
        for i in range(8, 16)  # 8 consecutive losing days
    ])
    result = compute_loss_cluster_summary(df)
    assert result["high_losing_streak"] is True


# ---------------------------------------------------------------------------
# summarize_risk_profile
# ---------------------------------------------------------------------------


def test_summarize_risk_profile_returns_profile():
    df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "total_pnl_units": 0.05 if i % 2 == 0 else -0.03}
        for i in range(8, 28)
    ])
    risk = summarize_risk_profile(df)
    assert risk.paper_only is True
    assert risk.production_ready is False
    assert risk.max_drawdown_units >= 0.0
    assert risk.max_drawdown_pct >= 0.0
    assert risk.max_consecutive_losing_days >= 0


def test_summarize_risk_profile_all_positive():
    df = _make_date_df([
        {"run_date": f"2025-05-{i:02d}", "total_pnl_units": 0.1}
        for i in range(8, 20)
    ])
    risk = summarize_risk_profile(df)
    assert risk.max_drawdown_pct == pytest.approx(0.0)
    assert risk.drawdown_exceeds_limit is False
    assert risk.max_consecutive_losing_days == 0


def test_summarize_risk_profile_frozen():
    df = _make_date_df([{"run_date": "2025-05-08", "total_pnl_units": 0.1}])
    risk = summarize_risk_profile(df)
    with pytest.raises((AttributeError, TypeError)):
        risk.max_drawdown_pct = 99.0  # type: ignore[misc]
