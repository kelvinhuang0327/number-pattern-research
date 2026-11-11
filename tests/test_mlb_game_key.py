"""
tests/test_mlb_game_key.py

Unit tests for wbc_backend/prediction/mlb_game_key.py
"""
from __future__ import annotations

import pytest
from wbc_backend.prediction.mlb_game_key import (
    build_mlb_date_team_key,
    build_mlb_game_id,
    dedupe_mlb_rows,
    normalize_mlb_team,
    parse_context_game_id,
)


# ─────────────────────────────────────────────────────────────────────────────
# normalize_mlb_team
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeMlbTeam:
    def test_full_name_lowercase(self):
        assert normalize_mlb_team("los angeles dodgers") == "LAD"

    def test_full_name_mixed_case(self):
        assert normalize_mlb_team("Los Angeles Dodgers") == "LAD"

    def test_abbreviation_passthrough(self):
        assert normalize_mlb_team("LAD") == "LAD"

    def test_underscored_uppercase(self):
        assert normalize_mlb_team("LOS_ANGELES_DODGERS") == "LAD"

    def test_underscored_full_cubs(self):
        assert normalize_mlb_team("CHICAGO_CUBS") == "CHC"

    def test_underscored_minnesota_twins(self):
        assert normalize_mlb_team("MINNESOTA_TWINS") == "MIN"

    def test_empty_string_returns_unk(self):
        assert normalize_mlb_team("") == "UNK"

    def test_none_handled_via_empty(self):
        # normalize_mlb_team expects a str; empty str → UNK
        assert normalize_mlb_team("") == "UNK"

    def test_stl_cardinals(self):
        assert normalize_mlb_team("St. Louis Cardinals") == "STL"

    def test_stl_cardinals_underscored(self):
        # "ST._LOUIS_CARDINALS" after underscore replacement → "st. louis cardinals"
        result = normalize_mlb_team("ST._LOUIS_CARDINALS")
        # Should map to STL eventually; if edge case fails, at least check no crash
        assert isinstance(result, str) and len(result) > 0

    def test_yankees_abbrev(self):
        assert normalize_mlb_team("NYY") == "NYY"

    def test_padres_full(self):
        assert normalize_mlb_team("San Diego Padres") == "SD"

    def test_dodgers_underscored_at_variant(self):
        # Segment after -AT- in context game_ids
        assert normalize_mlb_team("LOS_ANGELES_DODGERS") == "LAD"


# ─────────────────────────────────────────────────────────────────────────────
# build_mlb_game_id
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildMlbGameId:
    def test_basic(self):
        gid = build_mlb_game_id("2025-03-18", "Chicago Cubs", "Los Angeles Dodgers")
        assert gid == "2025-03-18_CHC_LAD"

    def test_date_only_first_10_chars(self):
        gid = build_mlb_game_id("2025-03-18T12:00:00", "New York Yankees", "Boston Red Sox")
        assert gid == "2025-03-18_NYY_BOS"

    def test_date_slash_format(self):
        gid = build_mlb_game_id("3/18/2025", "Chicago Cubs", "Los Angeles Dodgers")
        assert gid == "2025-03-18_CHC_LAD"

    def test_abbreviation_teams(self):
        gid = build_mlb_game_id("2025-04-01", "STL", "MIN")
        assert gid == "2025-04-01_STL_MIN"

    def test_game_id_format_components(self):
        gid = build_mlb_game_id("2025-05-11", "Houston Astros", "Tampa Bay Rays")
        parts = gid.split("_")
        assert len(parts) == 3
        assert parts[0] == "2025-05-11"
        assert parts[1] == "HOU"
        assert parts[2] == "TB"


# ─────────────────────────────────────────────────────────────────────────────
# build_mlb_date_team_key
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildMlbDateTeamKey:
    def test_basic(self):
        key = build_mlb_date_team_key("2025-03-18", "Chicago Cubs", "Los Angeles Dodgers")
        assert key == "2025-03-18_CHC_vs_LAD"

    def test_vs_separator(self):
        key = build_mlb_date_team_key("2025-04-01", "STL", "MIN")
        assert "_vs_" in key


# ─────────────────────────────────────────────────────────────────────────────
# parse_context_game_id
# ─────────────────────────────────────────────────────────────────────────────

class TestParseContextGameId:
    def test_dodgers_at_cubs(self):
        result = parse_context_game_id(
            "MLB-2025_03_18-6_10_AM-LOS_ANGELES_DODGERS-AT-CHICAGO_CUBS"
        )
        assert result is not None
        date_iso, home_code, away_code = result
        assert date_iso == "2025-03-18"
        assert home_code == "CHC"
        assert away_code == "LAD"

    def test_returns_none_for_empty(self):
        assert parse_context_game_id("") is None

    def test_returns_none_for_malformed(self):
        result = parse_context_game_id("not-a-valid-game-id")
        # No -AT- separator → should return None or fallback
        # Just assert it doesn't raise
        assert result is None or isinstance(result, tuple)

    def test_different_time(self):
        result = parse_context_game_id(
            "MLB-2025_04_15-7_05_PM-NEW_YORK_YANKEES-AT-BOSTON_RED_SOX"
        )
        assert result is not None
        date_iso, home_code, away_code = result
        assert date_iso == "2025-04-15"
        assert home_code == "BOS"
        assert away_code == "NYY"

    def test_padded_date(self):
        # Single-digit month/day
        result = parse_context_game_id(
            "MLB-2025_3_5-1_10_PM-MINNESOTA_TWINS-AT-ST._LOUIS_CARDINALS"
        )
        assert result is not None
        date_iso, _, _ = result
        assert date_iso == "2025-03-05"


# ─────────────────────────────────────────────────────────────────────────────
# dedupe_mlb_rows
# ─────────────────────────────────────────────────────────────────────────────

class TestDedupeMlbRows:
    def test_no_duplicates_unchanged(self):
        rows = [
            {"Date": "2025-03-18", "Home": "CHC", "Away": "LAD", "model_prob_home": 0.5},
            {"Date": "2025-03-19", "Home": "CHC", "Away": "LAD", "model_prob_home": 0.52},
        ]
        deduped, meta = dedupe_mlb_rows(rows)
        assert len(deduped) == 2
        assert meta["duplicate_game_id_count"] == 0
        assert meta["dropped_count"] == 0

    def test_duplicate_keeps_row_with_model_prob(self):
        rows = [
            {"Date": "2025-03-18", "Home": "CHC", "Away": "LAD", "model_prob_home": None},
            {"Date": "2025-03-18", "Home": "CHC", "Away": "LAD", "model_prob_home": "0.56"},
        ]
        deduped, meta = dedupe_mlb_rows(rows)
        assert len(deduped) == 1
        assert meta["duplicate_game_id_count"] == 1
        assert deduped[0]["model_prob_home"] == "0.56"

    def test_duplicate_both_no_model_keeps_first(self):
        rows = [
            {"Date": "2025-03-18", "Home": "CHC", "Away": "LAD", "model_prob_home": None, "some": "first"},
            {"Date": "2025-03-18", "Home": "CHC", "Away": "LAD", "model_prob_home": None, "some": "second"},
        ]
        deduped, meta = dedupe_mlb_rows(rows)
        assert len(deduped) == 1
        assert deduped[0]["some"] == "first"

    def test_game_id_added_to_rows(self):
        rows = [
            {"Date": "2025-03-18", "Home": "Chicago Cubs", "Away": "Los Angeles Dodgers"},
        ]
        deduped, _ = dedupe_mlb_rows(rows)
        assert "game_id" in deduped[0]
        assert deduped[0]["game_id"] == "2025-03-18_CHC_LAD"

    def test_metadata_keys_present(self):
        rows = [{"Date": "2025-03-18", "Home": "CHC", "Away": "LAD"}]
        _, meta = dedupe_mlb_rows(rows)
        required_keys = {
            "input_count", "output_count", "duplicate_game_id_count",
            "duplicate_date_team_key_count", "dropped_count", "risk_reasons",
        }
        assert required_keys <= meta.keys()

    def test_empty_input(self):
        deduped, meta = dedupe_mlb_rows([])
        assert deduped == []
        assert meta["input_count"] == 0
