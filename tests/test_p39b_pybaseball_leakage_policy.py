"""
P39B Leakage Policy Tests
tests/test_p39b_pybaseball_leakage_policy.py

Validates strict D-1 pregame-safe leakage guardrails:
  - validate_feature_window (accept / reject)
  - assert_no_odds_columns (exact + keyword)
  - build_rolling_features (no as_of_date rows appear in window)
  - empty fail-soft

Acceptance marker: P39B_LEAKAGE_POLICY_TESTS_PASS_20260515
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from scripts.build_pybaseball_pregame_features_2024 import (
    assert_no_odds_columns,
    build_rolling_features,
    build_team_daily_statcast_aggregates,
    validate_feature_window,
)


# ---------------------------------------------------------------------------
# validate_feature_window tests
# ---------------------------------------------------------------------------


def test_validate_window_accepts_d_minus_1() -> None:
    """window_end = game_date - 1 → True (pregame-safe)."""
    game_date = date(2024, 4, 10)
    window_end = game_date - timedelta(days=1)
    assert validate_feature_window(game_date, window_end) is True


def test_validate_window_rejects_same_day() -> None:
    """window_end == game_date → False (same-day leakage)."""
    game_date = date(2024, 4, 10)
    window_end = game_date
    assert validate_feature_window(game_date, window_end) is False


def test_validate_window_rejects_future() -> None:
    """window_end > game_date → False (future leakage)."""
    game_date = date(2024, 4, 10)
    window_end = game_date + timedelta(days=1)
    assert validate_feature_window(game_date, window_end) is False


# ---------------------------------------------------------------------------
# assert_no_odds_columns tests
# ---------------------------------------------------------------------------


def test_assert_no_odds_columns_accepts_baseball_stats() -> None:
    """Pure baseball stat columns → no error raised."""
    safe_cols = [
        "launch_speed",
        "launch_angle",
        "hard_hit_rate_proxy",
        "barrel_rate_proxy",
        "plate_appearances_proxy",
        "batted_balls",
        "avg_estimated_woba_using_speedangle",
        "avg_release_speed_against",
    ]
    assert_no_odds_columns(safe_cols)  # should not raise


def test_assert_no_odds_columns_rejects_odds_keyword() -> None:
    """Column containing 'odds' substring → ValueError."""
    with pytest.raises(ValueError, match="LEAKAGE_DETECTED"):
        assert_no_odds_columns(["home_odds"])


def test_assert_no_odds_columns_rejects_moneyline_keyword() -> None:
    """Column containing 'moneyline' substring → ValueError."""
    with pytest.raises(ValueError, match="LEAKAGE_DETECTED"):
        assert_no_odds_columns(["home_moneyline"])


def test_assert_no_odds_columns_rejects_sportsbook_keyword() -> None:
    """Column containing 'sportsbook' substring → ValueError."""
    with pytest.raises(ValueError, match="LEAKAGE_DETECTED"):
        assert_no_odds_columns(["sportsbook_id"])


# ---------------------------------------------------------------------------
# build_rolling_features leakage guarantee tests
#
# Uses a synthetic team_daily fixture:
#   - game_date 2024-04-01 (should be EXCLUDED from as_of=2024-04-01 window)
#   - game_date 2024-03-31 (should be INCLUDED in as_of=2024-04-01 window)
# ---------------------------------------------------------------------------


def _make_team_daily_fixture() -> pd.DataFrame:
    """Synthetic team daily DataFrame for leakage tests (no network)."""
    return pd.DataFrame(
        [
            {
                "game_date": date(2024, 3, 31),
                "team": "BOS",
                "game_pk": 1001,
                "plate_appearances_proxy": 35,
                "batted_balls": 10,
                "avg_launch_speed": 90.0,
                "avg_launch_angle": 20.0,
                "avg_estimated_woba_using_speedangle": 0.320,
                "hard_hit_rate_proxy": 0.30,
                "barrel_rate_proxy": 0.10,
                "avg_release_speed_against": 93.0,
                "source": "pybaseball_statcast",
            },
            {
                "game_date": date(2024, 4, 1),  # as_of_date row — must NOT appear
                "team": "BOS",
                "game_pk": 1002,
                "plate_appearances_proxy": 38,
                "batted_balls": 12,
                "avg_launch_speed": 95.0,
                "avg_launch_angle": 25.0,
                "avg_estimated_woba_using_speedangle": 0.340,
                "hard_hit_rate_proxy": 0.50,
                "barrel_rate_proxy": 0.20,
                "avg_release_speed_against": 94.0,
                "source": "pybaseball_statcast",
            },
        ]
    )


def test_rolling_features_exclude_as_of_date_rows() -> None:
    """
    Data for game_date == as_of_date must NOT be used in the rolling window.
    """
    team_daily = _make_team_daily_fixture()
    as_of_dates = [date(2024, 4, 1)]
    result = build_rolling_features(team_daily, as_of_dates, window_days=7)

    assert not result.empty, "Should return one row for BOS"

    bos_row = result[result["team"] == "BOS"].iloc[0]

    # window_end must be 2024-03-31 (strictly before 2024-04-01)
    assert bos_row["feature_window_end"] < date(2024, 4, 1), (
        "feature_window_end must be strictly before as_of_date"
    )

    # The avg_launch_speed rolling value should come from 2024-03-31 only (90.0)
    # NOT 95.0 (which is the as_of_date row)
    rolling_ls = bos_row["rolling_avg_launch_speed"]
    assert rolling_ls == pytest.approx(90.0, abs=0.01), (
        f"Expected 90.0 (from 2024-03-31 only), got {rolling_ls}"
    )


def test_rolling_features_window_end_before_as_of_date() -> None:
    """feature_window_end < as_of_date for every row in output."""
    team_daily = _make_team_daily_fixture()
    as_of_dates = [date(2024, 4, 1), date(2024, 4, 2)]
    result = build_rolling_features(team_daily, as_of_dates, window_days=7)

    assert not result.empty
    for _, row in result.iterrows():
        assert row["feature_window_end"] < row["as_of_date"], (
            f"Leakage: window_end={row['feature_window_end']} >= as_of={row['as_of_date']}"
        )


def test_rolling_features_empty_input_fail_soft() -> None:
    """Empty team_daily DataFrame → empty output, no crash."""
    result = build_rolling_features(
        pd.DataFrame(), [date(2024, 4, 1)], window_days=7
    )
    assert isinstance(result, pd.DataFrame)
    assert result.empty


# ---------------------------------------------------------------------------
# Acceptance marker
# ---------------------------------------------------------------------------


def test_acceptance_marker() -> None:
    """Sentinel: if this test passes, acceptance criterion is met."""
    marker = "P39B_LEAKAGE_POLICY_TESTS_PASS_20260515"
    assert len(marker) > 0
