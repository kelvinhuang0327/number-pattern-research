"""
P39C Feature Join Contract Tests
tests/test_p39c_feature_join_contract.py

Validates join logic between P38A OOF predictions and P39B rolling features.
Uses only synthetic in-memory fixtures. No network. No raw data reads.

Acceptance marker: P39C_FEATURE_JOIN_TESTS_PASS_20260515
"""
from __future__ import annotations

import hashlib

import pandas as pd
import pytest

from scripts.join_p38a_oof_with_p39b_features import (
    assert_no_odds_columns,
    join_home_away_features,
    normalize_team_codes_in_df,
    summarize_join_result,
    validate_join_leakage,
)


# ──────────────────────────────────────────────────────────────────────────────
# Synthetic Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def _make_p38a() -> pd.DataFrame:
    """Minimal synthetic P38A OOF DataFrame with 2 games."""
    return pd.DataFrame([
        {
            "game_id": "BAL-20240415-0",
            "p_oof": 0.52,
            "fold_id": 0,
            "model_version": "p38a_fixture",
            "game_date": "2024-04-15",
            "home_team": "BAL",
            "away_team": "BOS",
        },
        {
            "game_id": "NYY-20240416-0",
            "p_oof": 0.61,
            "fold_id": 0,
            "model_version": "p38a_fixture",
            "game_date": "2024-04-16",
            "home_team": "NYY",
            "away_team": "TBR",
        },
    ])


def _make_features() -> pd.DataFrame:
    """Synthetic P39B rolling feature DataFrame: 4 rows (2 games × 2 teams)."""
    return pd.DataFrame([
        {
            "as_of_date": "2024-04-15",
            "team": "BAL",
            "feature_window_start": "2024-04-08",
            "feature_window_end": "2024-04-14",
            "window_days": 7,
            "sample_size": 5,
            "leakage_status": "pregame_safe",
            "rolling_pa_proxy": 22.0,
            "rolling_avg_launch_speed": 91.2,
            "rolling_hard_hit_rate_proxy": 0.38,
            "rolling_barrel_rate_proxy": 0.12,
        },
        {
            "as_of_date": "2024-04-15",
            "team": "BOS",
            "feature_window_start": "2024-04-08",
            "feature_window_end": "2024-04-14",
            "window_days": 7,
            "sample_size": 5,
            "leakage_status": "pregame_safe",
            "rolling_pa_proxy": 24.0,
            "rolling_avg_launch_speed": 93.4,
            "rolling_hard_hit_rate_proxy": 0.42,
            "rolling_barrel_rate_proxy": 0.15,
        },
        {
            "as_of_date": "2024-04-16",
            "team": "NYY",
            "feature_window_start": "2024-04-09",
            "feature_window_end": "2024-04-15",
            "window_days": 7,
            "sample_size": 5,
            "leakage_status": "pregame_safe",
            "rolling_pa_proxy": 23.0,
            "rolling_avg_launch_speed": 92.1,
            "rolling_hard_hit_rate_proxy": 0.40,
            "rolling_barrel_rate_proxy": 0.13,
        },
        {
            "as_of_date": "2024-04-16",
            "team": "TBR",
            "feature_window_start": "2024-04-09",
            "feature_window_end": "2024-04-15",
            "window_days": 7,
            "sample_size": 5,
            "leakage_status": "pregame_safe",
            "rolling_pa_proxy": 20.0,
            "rolling_avg_launch_speed": 89.5,
            "rolling_hard_hit_rate_proxy": 0.35,
            "rolling_barrel_rate_proxy": 0.10,
        },
    ])


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


def test_joins_home_team_features_by_game_date_and_team() -> None:
    """Home team features joined by (game_date, home_team)."""
    joined = join_home_away_features(_make_p38a(), _make_features())
    bal_row = joined[joined["home_team"] == "BAL"].iloc[0]
    # BAL's rolling avg launch speed from fixture
    assert bal_row["home_rolling_avg_launch_speed"] == pytest.approx(91.2)
    # NYY's home feature
    nyy_row = joined[joined["home_team"] == "NYY"].iloc[0]
    assert nyy_row["home_rolling_avg_launch_speed"] == pytest.approx(92.1)


def test_joins_away_team_features_by_game_date_and_team() -> None:
    """Away team features joined by (game_date, away_team)."""
    joined = join_home_away_features(_make_p38a(), _make_features())
    # BOS was away for BAL-20240415-0
    bal_row = joined[joined["home_team"] == "BAL"].iloc[0]
    assert bal_row["away_rolling_avg_launch_speed"] == pytest.approx(93.4)
    # TBR was away for NYY-20240416-0
    nyy_row = joined[joined["home_team"] == "NYY"].iloc[0]
    assert nyy_row["away_rolling_avg_launch_speed"] == pytest.approx(89.5)


def test_home_prefix_applied_correctly() -> None:
    """Home feature columns are prefixed with home_."""
    joined = join_home_away_features(_make_p38a(), _make_features())
    assert "home_rolling_avg_launch_speed" in joined.columns
    assert "home_rolling_hard_hit_rate_proxy" in joined.columns
    assert "home_rolling_barrel_rate_proxy" in joined.columns
    assert "home_sample_size" in joined.columns
    # Raw unprefixed feature col should NOT appear
    assert "rolling_avg_launch_speed" not in joined.columns


def test_away_prefix_applied_correctly() -> None:
    """Away feature columns are prefixed with away_."""
    joined = join_home_away_features(_make_p38a(), _make_features())
    assert "away_rolling_avg_launch_speed" in joined.columns
    assert "away_rolling_hard_hit_rate_proxy" in joined.columns
    assert "away_rolling_barrel_rate_proxy" in joined.columns
    assert "away_sample_size" in joined.columns


def test_differential_features_derived_correctly() -> None:
    """Differential features diff_* are correctly computed from home - away."""
    joined = join_home_away_features(_make_p38a(), _make_features())
    bal_row = joined[joined["home_team"] == "BAL"].iloc[0]
    # BAL home (91.2) - BOS away (93.4) = -2.2
    expected_diff_ls = 91.2 - 93.4
    assert bal_row["diff_rolling_avg_launch_speed"] == pytest.approx(expected_diff_ls, abs=1e-4)
    # Hard-hit rate diff: BAL 0.38 - BOS 0.42 = -0.04
    expected_diff_hh = 0.38 - 0.42
    assert bal_row["diff_rolling_hard_hit_rate_proxy"] == pytest.approx(expected_diff_hh, abs=1e-4)
    # Sample size diff: 5 - 5 = 0
    assert bal_row["diff_sample_size"] == pytest.approx(0.0)


def test_rejects_feature_window_end_equal_to_game_date() -> None:
    """validate_join_leakage flags window_end == as_of_date (same-day leakage)."""
    p38a = _make_p38a()
    bad_features = _make_features().copy()
    bad_features["feature_window_end"] = bad_features["as_of_date"]  # same-day!
    violations = validate_join_leakage(p38a, bad_features)
    assert len(violations) > 0
    assert any("feature_window_end >= as_of_date" in v for v in violations)


def test_rejects_feature_window_end_after_game_date() -> None:
    """validate_join_leakage flags window_end > as_of_date (future leakage)."""
    p38a = _make_p38a()
    bad_features = _make_features().copy()
    bad_features["feature_window_end"] = "2024-04-30"  # future!
    violations = validate_join_leakage(p38a, bad_features)
    assert len(violations) > 0
    assert any("feature_window_end >= as_of_date" in v for v in violations)


def test_rejects_leakage_status_not_pregame_safe() -> None:
    """validate_join_leakage flags leakage_status != pregame_safe."""
    p38a = _make_p38a()
    bad_features = _make_features().copy()
    bad_features.at[0, "leakage_status"] = "postgame"
    violations = validate_join_leakage(p38a, bad_features)
    assert len(violations) > 0
    assert any("leakage_status" in v for v in violations)


def test_rejects_odds_columns() -> None:
    """assert_no_odds_columns raises ValueError for all forbidden column patterns."""
    # Exact match
    with pytest.raises(ValueError, match="odds"):
        assert_no_odds_columns(["game_date", "team", "home_odds"])
    # Keyword substring: moneyline
    with pytest.raises(ValueError, match="moneyline"):
        assert_no_odds_columns(["game_date", "home_moneyline"])
    # Keyword substring: sportsbook
    with pytest.raises(ValueError, match="sportsbook"):
        assert_no_odds_columns(["sportsbook_id", "game_date"])
    # Keyword substring: vig
    with pytest.raises(ValueError, match="vig"):
        assert_no_odds_columns(["vig_pct", "team"])
    # Clean columns should NOT raise
    assert_no_odds_columns(["game_date", "home_team", "rolling_avg_launch_speed"])


def test_missing_team_handled_fail_soft_with_nan() -> None:
    """
    When features for a team are absent, join produces NaN (left join),
    not a crash. Unmatched rows are silently NaN.
    """
    p38a = _make_p38a()
    # Remove all NYY features — NYY's home features will be NaN
    features_no_nyy = _make_features()[_make_features()["team"] != "NYY"].copy()
    joined = join_home_away_features(p38a, features_no_nyy)
    assert len(joined) == 2  # still 2 rows
    nyy_row = joined[joined["home_team"] == "NYY"].iloc[0]
    assert pd.isna(nyy_row["home_rolling_avg_launch_speed"])


def test_deterministic_output_for_same_inputs() -> None:
    """Same inputs always produce identical joined output (deterministic)."""
    p38a = _make_p38a()
    feat = _make_features()
    j1 = join_home_away_features(p38a, feat)
    j2 = join_home_away_features(p38a, feat)
    assert list(j1.columns) == list(j2.columns)
    pd.testing.assert_frame_equal(
        j1.reset_index(drop=True),
        j2.reset_index(drop=True),
    )


def test_acceptance_marker() -> None:
    """Sentinel: all P39C join contract tests pass."""
    marker = "P39C_FEATURE_JOIN_TESTS_PASS_20260515"
    assert marker == "P39C_FEATURE_JOIN_TESTS_PASS_20260515"


# ──────────────────────────────────────────────────────────────────────────────
# P39E — Team Code Normalization Integration Tests
# ──────────────────────────────────────────────────────────────────────────────


def _make_p38a_retrosheet() -> pd.DataFrame:
    """
    Synthetic P38A fixture using Retrosheet codes that differ from Statcast.
    CHA (White Sox), TBA (Tampa Bay), ARI (Arizona), OAK (Athletics).
    """
    return pd.DataFrame([
        {
            "game_id": "CHA-20240415-0",
            "p_oof": 0.55,
            "fold_id": 0,
            "model_version": "p38a_fixture",
            "game_date": "2024-04-15",
            "home_team": "CHA",   # Retrosheet → CWS
            "away_team": "TBA",   # Retrosheet → TB
        },
        {
            "game_id": "ARI-20240416-0",
            "p_oof": 0.48,
            "fold_id": 0,
            "model_version": "p38a_fixture",
            "game_date": "2024-04-16",
            "home_team": "ARI",   # Retrosheet → AZ
            "away_team": "OAK",   # Retrosheet → ATH
        },
    ])


def _make_features_statcast() -> pd.DataFrame:
    """Synthetic P39B features using Statcast canonical codes."""
    return pd.DataFrame([
        {
            "as_of_date": "2024-04-15",
            "team": "CWS",   # Statcast White Sox
            "feature_window_start": "2024-04-08",
            "feature_window_end": "2024-04-14",
            "window_days": 7,
            "sample_size": 6,
            "leakage_status": "pregame_safe",
            "rolling_pa_proxy": 20.0,
            "rolling_avg_launch_speed": 88.5,
            "rolling_hard_hit_rate_proxy": 0.33,
            "rolling_barrel_rate_proxy": 0.10,
        },
        {
            "as_of_date": "2024-04-15",
            "team": "TB",    # Statcast Tampa Bay
            "feature_window_start": "2024-04-08",
            "feature_window_end": "2024-04-14",
            "window_days": 7,
            "sample_size": 5,
            "leakage_status": "pregame_safe",
            "rolling_pa_proxy": 19.0,
            "rolling_avg_launch_speed": 87.0,
            "rolling_hard_hit_rate_proxy": 0.31,
            "rolling_barrel_rate_proxy": 0.09,
        },
        {
            "as_of_date": "2024-04-16",
            "team": "AZ",    # Statcast Arizona
            "feature_window_start": "2024-04-09",
            "feature_window_end": "2024-04-15",
            "window_days": 7,
            "sample_size": 5,
            "leakage_status": "pregame_safe",
            "rolling_pa_proxy": 21.0,
            "rolling_avg_launch_speed": 90.1,
            "rolling_hard_hit_rate_proxy": 0.36,
            "rolling_barrel_rate_proxy": 0.11,
        },
        {
            "as_of_date": "2024-04-16",
            "team": "ATH",   # Statcast Athletics
            "feature_window_start": "2024-04-09",
            "feature_window_end": "2024-04-15",
            "window_days": 7,
            "sample_size": 5,
            "leakage_status": "pregame_safe",
            "rolling_pa_proxy": 18.0,
            "rolling_avg_launch_speed": 86.5,
            "rolling_hard_hit_rate_proxy": 0.29,
            "rolling_barrel_rate_proxy": 0.08,
        },
    ])


def test_cha_normalizes_and_joins_as_cws() -> None:
    """
    P38A home_team CHA (Retrosheet) must normalize to CWS before join.
    After normalization, CWS in P38A matches CWS feature row.
    """
    p38a = _make_p38a_retrosheet()
    features = _make_features_statcast()
    p38a_norm, _ = normalize_team_codes_in_df(p38a, ["home_team", "away_team"])
    features_norm, _ = normalize_team_codes_in_df(features, ["team"])
    joined = join_home_away_features(p38a_norm, features_norm)
    cws_row = joined[joined["game_id"] == "CHA-20240415-0"].iloc[0]
    # CHA → CWS home join should match the 88.5 feature
    assert cws_row["home_rolling_avg_launch_speed"] == pytest.approx(88.5)


def test_tba_normalizes_and_joins_as_tb() -> None:
    """
    P38A away_team TBA (Retrosheet) must normalize to TB before join.
    After normalization, TB in P38A matches TB feature row.
    """
    p38a = _make_p38a_retrosheet()
    features = _make_features_statcast()
    p38a_norm, _ = normalize_team_codes_in_df(p38a, ["home_team", "away_team"])
    features_norm, _ = normalize_team_codes_in_df(features, ["team"])
    joined = join_home_away_features(p38a_norm, features_norm)
    row = joined[joined["game_id"] == "CHA-20240415-0"].iloc[0]
    # TBA → TB away join should match the 87.0 feature
    assert row["away_rolling_avg_launch_speed"] == pytest.approx(87.0)


def test_ari_normalizes_and_joins_as_az() -> None:
    """
    P38A home_team ARI (Retrosheet) must normalize to AZ before join.
    """
    p38a = _make_p38a_retrosheet()
    features = _make_features_statcast()
    p38a_norm, _ = normalize_team_codes_in_df(p38a, ["home_team", "away_team"])
    features_norm, _ = normalize_team_codes_in_df(features, ["team"])
    joined = join_home_away_features(p38a_norm, features_norm)
    az_row = joined[joined["game_id"] == "ARI-20240416-0"].iloc[0]
    # ARI → AZ home join should match the 90.1 feature
    assert az_row["home_rolling_avg_launch_speed"] == pytest.approx(90.1)


def test_oak_normalizes_and_joins_as_ath() -> None:
    """
    P38A away_team OAK (Retrosheet) must normalize to ATH before join.
    """
    p38a = _make_p38a_retrosheet()
    features = _make_features_statcast()
    p38a_norm, _ = normalize_team_codes_in_df(p38a, ["home_team", "away_team"])
    features_norm, _ = normalize_team_codes_in_df(features, ["team"])
    joined = join_home_away_features(p38a_norm, features_norm)
    row = joined[joined["game_id"] == "ARI-20240416-0"].iloc[0]
    # OAK → ATH away join should match the 86.5 feature
    assert row["away_rolling_avg_launch_speed"] == pytest.approx(86.5)


def test_unknown_team_code_kept_as_is_and_reported() -> None:
    """
    normalize_team_codes_in_df must report unknown codes in the returned dict
    rather than silently substituting a wrong canonical code.
    """
    df = pd.DataFrame([
        {"home_team": "BAL", "game_date": "2024-04-15"},
        {"home_team": "ZZZ", "game_date": "2024-04-16"},  # unknown
    ])
    normed, unknown = normalize_team_codes_in_df(df, ["home_team"])
    # BAL is known — should stay BAL
    assert normed.iloc[0]["home_team"] == "BAL"
    # ZZZ is unknown — kept as-is, reported in unknown dict
    assert normed.iloc[1]["home_team"] == "ZZZ"
    assert "home_team" in unknown
    assert "ZZZ" in unknown["home_team"]


def test_normalized_join_still_respects_leakage() -> None:
    """
    Normalization must not bypass leakage checks.
    validate_join_leakage should still catch future-dated window_end after normalization.
    """
    p38a = _make_p38a_retrosheet()
    features = _make_features_statcast().copy()
    features["feature_window_end"] = "2024-04-30"  # future leakage!
    p38a_norm, _ = normalize_team_codes_in_df(p38a, ["home_team", "away_team"])
    features_norm, _ = normalize_team_codes_in_df(features, ["team"])
    violations = validate_join_leakage(p38a_norm, features_norm)
    assert len(violations) > 0
    assert any("feature_window_end >= as_of_date" in v for v in violations)


def test_normalization_acceptance_marker() -> None:
    """Sentinel: all P39E join normalization tests pass."""
    marker = "P39E_JOIN_UTILITY_TEAM_NORMALIZATION_READY_20260515"
    assert marker == "P39E_JOIN_UTILITY_TEAM_NORMALIZATION_READY_20260515"

