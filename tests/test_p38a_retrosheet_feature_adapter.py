"""Tests for P38A Retrosheet Feature Adapter."""
from __future__ import annotations

import hashlib
import io
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p38a_retrosheet_feature_adapter import (
    REQUIRED_OUTPUT_FEATURE_KEYS,
    _LEAKAGE_COLUMNS,
    build_feature_dataframe,
)

# ── Fixture helpers ──────────────────────────────────────────────────────────

_MINIMAL_CSV = """game_id,game_date,season,away_team,home_team,source_name,source_row_number,away_score,home_score,y_true_home_win
G001,2024-04-01,2024,NYA,BOS,Retrosheet,1,3,5,1
G002,2024-04-02,2024,BOS,NYA,Retrosheet,2,4,2,0
G003,2024-04-03,2024,NYA,BOS,Retrosheet,3,1,6,1
G004,2024-04-05,2024,BOS,NYA,Retrosheet,4,3,3,0
G005,2024-04-06,2024,NYA,BOS,Retrosheet,5,2,4,1
"""


def _write_csv(content: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w")
    tmp.write(content)
    tmp.flush()
    return Path(tmp.name)


# ── Tests ────────────────────────────────────────────────────────────────────


def test_no_leakage_score_columns():
    """pregame_features must not contain any leakage columns."""
    path = _write_csv(_MINIMAL_CSV)
    result = build_feature_dataframe(path)
    for _, row in result.feature_df.iterrows():
        feature_keys = set(row["pregame_features"].keys())
        assert feature_keys.isdisjoint(_LEAKAGE_COLUMNS), (
            f"Leakage columns found in features: {feature_keys & _LEAKAGE_COLUMNS}"
        )


def test_pregame_only_window():
    """Rolling stats for game N must not include game N's own outcome."""
    # G001 is the very first game for BOS and NYA, so history must be empty before it
    path = _write_csv(_MINIMAL_CSV)
    result = build_feature_dataframe(path)
    df = result.feature_df

    # First game for BOS as home: G001 (2024-04-01)
    first_game = df[df["game_id"] == "G001"].iloc[0]
    features = first_game["pregame_features"]

    # No prior games => rolling stats should default to 0.5 winrate / 0.0 run_diff
    assert features["home_rolling_winrate_10g"] == pytest.approx(0.5)
    assert features["home_rolling_run_diff_10g"] == pytest.approx(0.0)
    # No prior game => rest_days defaults to 14.0
    assert features["home_rest_days"] == pytest.approx(14.0)


def test_deterministic_output():
    """Two identical runs must produce the same output_hash."""
    path = _write_csv(_MINIMAL_CSV)
    result1 = build_feature_dataframe(path)
    result2 = build_feature_dataframe(path)
    assert result1.output_hash == result2.output_hash


def test_required_columns_present():
    """Output DataFrame must have game_id, game_date, home_team, away_team, pregame_features."""
    path = _write_csv(_MINIMAL_CSV)
    result = build_feature_dataframe(path)
    for col in ["game_id", "game_date", "home_team", "away_team", "pregame_features"]:
        assert col in result.feature_df.columns, f"Missing column: {col}"


def test_required_feature_keys_in_pregame_features():
    """Every pregame_features dict must contain all REQUIRED_OUTPUT_FEATURE_KEYS."""
    path = _write_csv(_MINIMAL_CSV)
    result = build_feature_dataframe(path)
    for _, row in result.feature_df.iterrows():
        missing = REQUIRED_OUTPUT_FEATURE_KEYS - set(row["pregame_features"].keys())
        assert not missing, f"Missing feature keys for {row['game_id']}: {missing}"


def test_is_home_team_indicator_always_one():
    """is_home_team_indicator must be 1.0 for every row."""
    path = _write_csv(_MINIMAL_CSV)
    result = build_feature_dataframe(path)
    for _, row in result.feature_df.iterrows():
        assert row["pregame_features"]["is_home_team_indicator"] == pytest.approx(1.0)


def test_rolling_stats_use_prior_games():
    """By G003 BOS has 1 prior game as home (G001). Rolling winrate should reflect that."""
    path = _write_csv(_MINIMAL_CSV)
    result = build_feature_dataframe(path)
    df = result.feature_df

    # G003: BOS is home. Prior BOS home game = G001 (win). So home_rolling_winrate_10g = 1.0
    g003 = df[df["game_id"] == "G003"].iloc[0]
    # BOS was home in G001 (win=1) before G003 => rolling_winrate_10g for home = 1.0
    assert g003["pregame_features"]["home_rolling_winrate_10g"] == pytest.approx(1.0)
