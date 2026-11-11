"""
Tests for P32 Retrosheet Game Log Parser.

Coverage:
- parser maps Retrosheet positional fields correctly
- parser derives y_true_home_win correctly
- parser blocks invalid schema
- build_game_id is deterministic
- normalize_game_date handles valid and invalid dates
- derive_home_away_scores handles missing scores
- filter_to_season returns only 2024 rows
- compute_outcome_coverage is accurate
"""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p32_retrosheet_game_log_parser import (
    build_game_id,
    compute_outcome_coverage,
    derive_home_away_scores,
    derive_y_true_home_win,
    filter_to_season,
    load_retrosheet_game_log,
    normalize_game_date,
    normalize_team_fields,
    parse_retrosheet_game_log_rows,
    validate_retrosheet_schema,
    REQUIRED_OUTPUT_COLUMNS,
    RETROSHEET_MIN_FIELD_COUNT,
    SOURCE_NAME,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_retrosheet_row(
    date: str = "20240401",
    game_num: str = "0",
    day: str = "Mon",
    away: str = "BOS",
    away_league: str = "AL",
    away_gn: str = "1",
    home: str = "NYY",
    home_league: str = "AL",
    home_gn: str = "1",
    away_score: str = "3",
    home_score: str = "5",
    pad_to: int = 11,
) -> pd.Series:
    """Build a minimal valid Retrosheet row as a pandas Series."""
    base = [date, game_num, day, away, away_league, away_gn,
            home, home_league, home_gn, away_score, home_score]
    # Pad to at least pad_to columns
    while len(base) < pad_to:
        base.append("")
    return pd.Series(base)


def _make_retrosheet_df(rows: list[list[str]]) -> pd.DataFrame:
    """Build a raw Retrosheet DataFrame from a list of string lists."""
    return pd.DataFrame(rows, dtype=str)


def _make_minimal_raw_df(n_rows: int = 3) -> pd.DataFrame:
    """Build a minimal valid raw Retrosheet DataFrame."""
    rows = []
    for i in range(n_rows):
        day = 1 + i
        rows.append(
            ["202404{:02d}".format(day), "0", "Mon", "BOS", "AL", "1",
             "NYY", "AL", "1", str(3 + i), str(5 + i)]
        )
    return _make_retrosheet_df(rows)


# ---------------------------------------------------------------------------
# validate_retrosheet_schema
# ---------------------------------------------------------------------------


class TestValidateRetroSheetSchema:
    def test_valid_schema_passes(self) -> None:
        df = _make_minimal_raw_df(3)
        ok, reason = validate_retrosheet_schema(df)
        assert ok, reason

    def test_empty_df_fails(self) -> None:
        df = pd.DataFrame()
        ok, _ = validate_retrosheet_schema(df)
        assert not ok

    def test_too_few_columns_fails(self) -> None:
        df = pd.DataFrame([["20240401", "0", "Mon"]])
        ok, reason = validate_retrosheet_schema(df)
        assert not ok
        assert "columns" in reason.lower()

    def test_bad_date_column_fails(self) -> None:
        rows = [["BADDATE", "0", "Mon", "BOS", "AL", "1",
                 "NYY", "AL", "1", "3", "5"]]
        df = _make_retrosheet_df(rows)
        ok, reason = validate_retrosheet_schema(df)
        assert not ok
        assert "date" in reason.lower()


# ---------------------------------------------------------------------------
# normalize_game_date
# ---------------------------------------------------------------------------


class TestNormalizeGameDate:
    def test_valid_date(self) -> None:
        row = _make_retrosheet_row(date="20240401")
        assert normalize_game_date(row) == "2024-04-01"

    def test_invalid_date_returns_empty(self) -> None:
        row = _make_retrosheet_row(date="BADDATE")
        assert normalize_game_date(row) == ""

    def test_seven_digit_date_invalid(self) -> None:
        row = _make_retrosheet_row(date="2024041")
        assert normalize_game_date(row) == ""

    def test_nine_digit_date_invalid(self) -> None:
        row = _make_retrosheet_row(date="202404011")
        assert normalize_game_date(row) == ""

    def test_opening_day_2024(self) -> None:
        row = _make_retrosheet_row(date="20240320")
        assert normalize_game_date(row) == "2024-03-20"


# ---------------------------------------------------------------------------
# normalize_team_fields
# ---------------------------------------------------------------------------


class TestNormalizeTeamFields:
    def test_valid_team_uppercase(self) -> None:
        row = _make_retrosheet_row(away="bos")
        result = normalize_team_fields(row, team_col=3)
        assert result == "BOS"

    def test_truncates_to_three_chars(self) -> None:
        row = _make_retrosheet_row(away="BOSTON")
        result = normalize_team_fields(row, team_col=3)
        assert result == "BOS"

    def test_missing_team_returns_unk(self) -> None:
        row = _make_retrosheet_row(away="")
        result = normalize_team_fields(row, team_col=3)
        assert result == "UNK"


# ---------------------------------------------------------------------------
# build_game_id
# ---------------------------------------------------------------------------


class TestBuildGameId:
    def test_deterministic_single_game(self) -> None:
        gid1 = build_game_id("2024-04-01", "NYY", "0")
        gid2 = build_game_id("2024-04-01", "NYY", "0")
        assert gid1 == gid2

    def test_format_correct(self) -> None:
        gid = build_game_id("2024-04-01", "NYY", "0")
        assert gid == "NYY-20240401-0"

    def test_doubleheader_game1(self) -> None:
        gid = build_game_id("2024-06-15", "BOS", "1")
        assert gid == "BOS-20240615-1"

    def test_different_teams_different_ids(self) -> None:
        gid1 = build_game_id("2024-04-01", "NYY", "0")
        gid2 = build_game_id("2024-04-01", "BOS", "0")
        assert gid1 != gid2

    def test_different_dates_different_ids(self) -> None:
        gid1 = build_game_id("2024-04-01", "NYY", "0")
        gid2 = build_game_id("2024-04-02", "NYY", "0")
        assert gid1 != gid2


# ---------------------------------------------------------------------------
# derive_home_away_scores
# ---------------------------------------------------------------------------


class TestDeriveHomeAwayScores:
    def test_valid_scores(self) -> None:
        row = _make_retrosheet_row(away_score="3", home_score="5")
        away, home = derive_home_away_scores(row)
        assert away == 3
        assert home == 5

    def test_missing_score_returns_none(self) -> None:
        row = _make_retrosheet_row(away_score="", home_score="")
        away, home = derive_home_away_scores(row)
        assert away is None
        assert home is None

    def test_non_numeric_score_returns_none(self) -> None:
        row = _make_retrosheet_row(away_score="X", home_score="Y")
        away, home = derive_home_away_scores(row)
        assert away is None
        assert home is None

    def test_zero_score(self) -> None:
        row = _make_retrosheet_row(away_score="0", home_score="1")
        away, home = derive_home_away_scores(row)
        assert away == 0
        assert home == 1


# ---------------------------------------------------------------------------
# derive_y_true_home_win
# ---------------------------------------------------------------------------


class TestDeriveYTrueHomeWin:
    def test_home_win(self) -> None:
        assert derive_y_true_home_win(3, 5) == 1

    def test_away_win(self) -> None:
        assert derive_y_true_home_win(5, 3) == 0

    def test_tied_returns_none(self) -> None:
        assert derive_y_true_home_win(3, 3) is None

    def test_none_scores_returns_none(self) -> None:
        assert derive_y_true_home_win(None, None) is None

    def test_one_none_score_returns_none(self) -> None:
        assert derive_y_true_home_win(3, None) is None


# ---------------------------------------------------------------------------
# parse_retrosheet_game_log_rows
# ---------------------------------------------------------------------------


class TestParseRetroSheetGameLogRows:
    def test_valid_rows_parsed_correctly(self) -> None:
        """Parser maps Retrosheet positional fields correctly."""
        df = _make_minimal_raw_df(3)
        result = parse_retrosheet_game_log_rows(df)
        assert len(result) == 3
        assert list(result.columns) == REQUIRED_OUTPUT_COLUMNS

    def test_game_date_iso_format(self) -> None:
        df = _make_minimal_raw_df(1)
        result = parse_retrosheet_game_log_rows(df)
        assert result.iloc[0]["game_date"] == "2024-04-01"

    def test_teams_mapped_correctly(self) -> None:
        df = _make_minimal_raw_df(1)
        result = parse_retrosheet_game_log_rows(df)
        assert result.iloc[0]["away_team"] == "BOS"
        assert result.iloc[0]["home_team"] == "NYY"

    def test_y_true_home_win_correct(self) -> None:
        """Parser derives y_true_home_win correctly — home_score > away_score."""
        # home=5, away=3 → y_true=1
        df = _make_retrosheet_df([[
            "20240401", "0", "Mon", "BOS", "AL", "1",
            "NYY", "AL", "1", "3", "5"
        ]])
        result = parse_retrosheet_game_log_rows(df)
        assert result.iloc[0]["y_true_home_win"] == 1

    def test_y_true_away_win(self) -> None:
        """home_score < away_score → y_true=0."""
        df = _make_retrosheet_df([[
            "20240401", "0", "Mon", "BOS", "AL", "1",
            "NYY", "AL", "1", "7", "2"
        ]])
        result = parse_retrosheet_game_log_rows(df)
        assert result.iloc[0]["y_true_home_win"] == 0

    def test_source_name_is_retrosheet(self) -> None:
        df = _make_minimal_raw_df(2)
        result = parse_retrosheet_game_log_rows(df)
        assert (result["source_name"] == SOURCE_NAME).all()

    def test_season_inferred_from_date(self) -> None:
        df = _make_minimal_raw_df(1)
        result = parse_retrosheet_game_log_rows(df)
        assert result.iloc[0]["season"] == 2024

    def test_blocks_invalid_schema(self) -> None:
        """Parser blocks invalid schema."""
        bad_df = pd.DataFrame([["not", "a", "date"]])
        with pytest.raises(ValueError, match="SCHEMA"):
            parse_retrosheet_game_log_rows(bad_df)

    def test_skips_rows_with_bad_dates(self) -> None:
        # First row must be valid so schema check passes;
        # the bad-date row (row 2) is skipped at row-level parsing.
        rows = [
            ["20240401", "0", "Mon", "BOS", "AL", "1", "NYY", "AL", "1", "3", "5"],
            ["BADDATE", "0", "Mon", "BOS", "AL", "1", "NYY", "AL", "1", "4", "6"],
        ]
        df = _make_retrosheet_df(rows)
        result = parse_retrosheet_game_log_rows(df)
        assert len(result) == 1

    def test_no_odds_in_output(self) -> None:
        df = _make_minimal_raw_df(3)
        result = parse_retrosheet_game_log_rows(df)
        odds_cols = {"odds", "moneyline", "closing_odds", "spread", "over_under"}
        assert not (odds_cols & set(result.columns))

    def test_no_predictions_in_output(self) -> None:
        df = _make_minimal_raw_df(3)
        result = parse_retrosheet_game_log_rows(df)
        pred_cols = {"predicted_probability", "edge", "kelly_fraction", "recommendation"}
        assert not (pred_cols & set(result.columns))


# ---------------------------------------------------------------------------
# filter_to_season
# ---------------------------------------------------------------------------


class TestFilterToSeason:
    def test_filters_to_2024(self) -> None:
        rows = [
            ["20240401", "0", "Mon", "BOS", "AL", "1", "NYY", "AL", "1", "3", "5"],
            ["20250401", "0", "Mon", "LAD", "NL", "1", "SF", "NL", "1", "2", "4"],
        ]
        df = _make_retrosheet_df(rows)
        parsed = parse_retrosheet_game_log_rows(df)
        filtered = filter_to_season(parsed, 2024)
        assert len(filtered) == 1
        assert filtered.iloc[0]["season"] == 2024

    def test_empty_result_when_no_matching_season(self) -> None:
        df = _make_minimal_raw_df(2)  # 2024 rows
        parsed = parse_retrosheet_game_log_rows(df)
        filtered = filter_to_season(parsed, 2023)
        assert len(filtered) == 0


# ---------------------------------------------------------------------------
# compute_outcome_coverage
# ---------------------------------------------------------------------------


class TestComputeOutcomeCoverage:
    def test_full_coverage(self) -> None:
        df = _make_minimal_raw_df(3)
        parsed = parse_retrosheet_game_log_rows(df)
        cov = compute_outcome_coverage(parsed)
        assert cov == pytest.approx(1.0)

    def test_empty_df_returns_zero(self) -> None:
        empty = pd.DataFrame(columns=REQUIRED_OUTPUT_COLUMNS)
        assert compute_outcome_coverage(empty) == 0.0

    def test_partial_coverage(self) -> None:
        rows = [
            ["20240401", "0", "Mon", "BOS", "AL", "1", "NYY", "AL", "1", "3", "5"],
            ["20240402", "0", "Mon", "BOS", "AL", "1", "NYY", "AL", "1", "", ""],
        ]
        df = _make_retrosheet_df(rows)
        parsed = parse_retrosheet_game_log_rows(df)
        cov = compute_outcome_coverage(parsed)
        assert 0.0 < cov < 1.0


# ---------------------------------------------------------------------------
# load_retrosheet_game_log
# ---------------------------------------------------------------------------


class TestLoadRetroSheetGameLog:
    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_retrosheet_game_log(tmp_path / "nonexistent.txt")

    def test_loads_csv_no_header(self, tmp_path: Path) -> None:
        content = "20240401,0,Mon,BOS,AL,1,NYY,AL,1,3,5\n"
        f = tmp_path / "gl2024.txt"
        f.write_text(content, encoding="latin-1")
        df = load_retrosheet_game_log(f)
        assert len(df) == 1
        assert df.shape[1] >= 11
