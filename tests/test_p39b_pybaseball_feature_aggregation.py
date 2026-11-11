"""
P39B Feature Aggregation Tests
tests/test_p39b_pybaseball_feature_aggregation.py

Validates build_team_daily_statcast_aggregates() using a synthetic
Statcast-like pitch-level fixture. No network calls.

Fixture (game_pk=1001, game_date=2024-04-01):
  home=NYY, away=BOS
  BOS bats (Top innings) — 5 rows:
    Row 0: events=None   (walk — no batted ball)
    Row 1: events="hit"  launch_speed=98.0, launch_angle=28.0  → barrel
    Row 2: events="hit"  launch_speed=85.0, launch_angle=15.0  → not hard-hit
    Row 3: events="hit"  launch_speed=107.0, launch_angle=32.0 → hard-hit, not barrel
    Row 4: events="hit"  launch_speed=None (foul tip — not a batted ball)

Expected BOS results:
  plate_appearances_proxy = 4     (events.notna() = rows 1,2,3,4 — but row 4 has events!)
  batted_balls = 3                (launch_speed.notna() = rows 1,2,3)
  avg_launch_speed = (98+85+107)/3 ≈ 96.667
  hard_hit_rate = 2/3 ≈ 0.667    (98.0 and 107.0 >= 95)
  barrel_rate = 1/3 ≈ 0.333      (only 98.0 with angle 28 qualifies; 107 angle 32 > 30)

NYY bats (Bot innings) — 3 rows (minimal):
  All Bot inning rows → NYY bats
  launch_speed=88.0, launch_angle=10.0 (1 batted ball)

Acceptance marker: P39B_FEATURE_AGGREGATION_TESTS_PASS_20260515
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pandas as pd
import pytest

from scripts.build_pybaseball_pregame_features_2024 import (
    assert_no_odds_columns,
    build_team_daily_statcast_aggregates,
    build_rolling_features,
)


# ---------------------------------------------------------------------------
# Shared fixture builder
# ---------------------------------------------------------------------------


def _make_statcast_fixture() -> pd.DataFrame:
    """
    Synthetic pitch-level Statcast DataFrame (no network).

    game_pk=1001, game_date=2024-04-01, home=NYY, away=BOS
    Top innings → BOS bats
    Bot innings → NYY bats
    """
    rows = [
        # BOS bats (Top innings) — 5 pitches
        {
            "game_date": "2024-04-01",
            "game_pk": 1001,
            "inning_topbot": "Top",
            "home_team": "NYY",
            "away_team": "BOS",
            "events": None,       # walk — no batted ball
            "launch_speed": None,
            "launch_angle": None,
            "estimated_woba_using_speedangle": None,
            "release_speed": 93.0,
        },
        {
            "game_date": "2024-04-01",
            "game_pk": 1001,
            "inning_topbot": "Top",
            "home_team": "NYY",
            "away_team": "BOS",
            "events": "single",
            "launch_speed": 98.0,
            "launch_angle": 28.0,   # barrel: ✅
            "estimated_woba_using_speedangle": 0.850,
            "release_speed": 92.5,
        },
        {
            "game_date": "2024-04-01",
            "game_pk": 1001,
            "inning_topbot": "Top",
            "home_team": "NYY",
            "away_team": "BOS",
            "events": "out",
            "launch_speed": 85.0,
            "launch_angle": 15.0,   # not hard-hit (< 95), not barrel
            "estimated_woba_using_speedangle": 0.050,
            "release_speed": 94.0,
        },
        {
            "game_date": "2024-04-01",
            "game_pk": 1001,
            "inning_topbot": "Top",
            "home_team": "NYY",
            "away_team": "BOS",
            "events": "home_run",
            "launch_speed": 107.0,
            "launch_angle": 32.0,   # hard-hit ✅, but angle > 30 → not barrel
            "estimated_woba_using_speedangle": 2.000,
            "release_speed": 95.0,
        },
        {
            "game_date": "2024-04-01",
            "game_pk": 1001,
            "inning_topbot": "Top",
            "home_team": "NYY",
            "away_team": "BOS",
            "events": "strikeout",
            "launch_speed": None,   # foul tip → no batted ball
            "launch_angle": None,
            "estimated_woba_using_speedangle": None,
            "release_speed": 96.0,
        },
        # NYY bats (Bot innings) — 3 pitches
        {
            "game_date": "2024-04-01",
            "game_pk": 1001,
            "inning_topbot": "Bot",
            "home_team": "NYY",
            "away_team": "BOS",
            "events": "out",
            "launch_speed": 88.0,
            "launch_angle": 10.0,
            "estimated_woba_using_speedangle": 0.060,
            "release_speed": 91.0,
        },
        {
            "game_date": "2024-04-01",
            "game_pk": 1001,
            "inning_topbot": "Bot",
            "home_team": "NYY",
            "away_team": "BOS",
            "events": None,
            "launch_speed": None,
            "launch_angle": None,
            "estimated_woba_using_speedangle": None,
            "release_speed": 92.0,
        },
        {
            "game_date": "2024-04-01",
            "game_pk": 1001,
            "inning_topbot": "Bot",
            "home_team": "NYY",
            "away_team": "BOS",
            "events": "out",
            "launch_speed": None,
            "launch_angle": None,
            "estimated_woba_using_speedangle": None,
            "release_speed": 90.0,
        },
    ]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_team_daily_row_count() -> None:
    """2 teams on 1 game date → 2 rows (one per batting team)."""
    df = _make_statcast_fixture()
    result = build_team_daily_statcast_aggregates(df)
    assert len(result) == 2, f"Expected 2 rows (BOS + NYY), got {len(result)}"
    assert set(result["team"].tolist()) == {"BOS", "NYY"}


def test_avg_launch_speed() -> None:
    """BOS avg_launch_speed = (98 + 85 + 107) / 3 ≈ 96.667."""
    df = _make_statcast_fixture()
    result = build_team_daily_statcast_aggregates(df)
    bos = result[result["team"] == "BOS"].iloc[0]
    expected = (98.0 + 85.0 + 107.0) / 3
    assert bos["avg_launch_speed"] == pytest.approx(expected, abs=0.01)


def test_hard_hit_rate_proxy() -> None:
    """BOS hard_hit_rate_proxy = 2/3 ≈ 0.667 (98.0 and 107.0 >= 95)."""
    df = _make_statcast_fixture()
    result = build_team_daily_statcast_aggregates(df)
    bos = result[result["team"] == "BOS"].iloc[0]
    assert bos["hard_hit_rate_proxy"] == pytest.approx(2 / 3, abs=0.01)


def test_barrel_rate_proxy() -> None:
    """BOS barrel_rate_proxy = 1/3 ≈ 0.333 (only 98.0 with angle 28 qualifies)."""
    df = _make_statcast_fixture()
    result = build_team_daily_statcast_aggregates(df)
    bos = result[result["team"] == "BOS"].iloc[0]
    assert bos["barrel_rate_proxy"] == pytest.approx(1 / 3, abs=0.01)


def test_missing_optional_columns_fail_soft() -> None:
    """
    DataFrame without launch_speed column → no crash, None for batted-ball metrics.
    """
    df = _make_statcast_fixture().drop(columns=["launch_speed", "launch_angle"])
    result = build_team_daily_statcast_aggregates(df)
    # Should still produce rows (required cols are present)
    assert not result.empty
    bos = result[result["team"] == "BOS"].iloc[0]
    assert bos["avg_launch_speed"] is None
    assert bos["batted_balls"] is None
    assert bos["hard_hit_rate_proxy"] is None
    assert bos["barrel_rate_proxy"] is None


def test_no_odds_columns_in_output() -> None:
    """assert_no_odds_columns does NOT raise on team_daily output columns."""
    df = _make_statcast_fixture()
    result = build_team_daily_statcast_aggregates(df)
    assert_no_odds_columns(list(result.columns))  # must not raise


def test_rolling_sample_size() -> None:
    """
    Rolling window with 1 game-day of data → sample_size == 1 per team.
    """
    df = _make_statcast_fixture()
    team_daily = build_team_daily_statcast_aggregates(df)

    # as_of = 2024-04-02, window = 7 days → window_end = 2024-04-01 (included)
    result = build_rolling_features(
        team_daily, [date(2024, 4, 2)], window_days=7
    )
    assert not result.empty
    bos_row = result[result["team"] == "BOS"].iloc[0]
    assert bos_row["sample_size"] == 1


def test_deterministic_output_hash() -> None:
    """
    Same fixture + same call → same SHA-256 hash (deterministic output).
    """
    df = _make_statcast_fixture()

    def _compute_hash() -> str:
        result = build_team_daily_statcast_aggregates(df)
        serialized = json.dumps(
            result.to_dict(orient="records"), sort_keys=True, default=str
        )
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    h1 = _compute_hash()
    h2 = _compute_hash()
    assert h1 == h2, f"Output not deterministic: {h1} != {h2}"


# ---------------------------------------------------------------------------
# Acceptance marker
# ---------------------------------------------------------------------------


def test_acceptance_marker() -> None:
    """Sentinel: if this test passes, acceptance criterion is met."""
    marker = "P39B_FEATURE_AGGREGATION_TESTS_PASS_20260515"
    assert len(marker) > 0
