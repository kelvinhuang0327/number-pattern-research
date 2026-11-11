"""
tests/test_mlb_prediction_join_audit.py

P8: Unit tests for wbc_backend/prediction/mlb_prediction_join_audit.py
"""
from __future__ import annotations

import pytest

from wbc_backend.prediction.mlb_prediction_join_audit import (
    audit_prediction_join_integrity,
    normalize_mlb_team_name,
)


# ─────────────────────────────────────────────────────────────────────────────
# § 1  normalize_mlb_team_name
# ─────────────────────────────────────────────────────────────────────────────

class TestNormalizeMlbTeamName:
    # ── Empty / whitespace ────────────────────────────────────────────────────
    def test_empty_string(self):
        assert normalize_mlb_team_name("") == ""

    def test_whitespace(self):
        assert normalize_mlb_team_name("   ") == ""

    # ── Exact abbreviations ───────────────────────────────────────────────────
    def test_abbreviation_lad(self):
        assert normalize_mlb_team_name("LAD") == "LAD"

    def test_abbreviation_nyy(self):
        assert normalize_mlb_team_name("NYY") == "NYY"

    def test_abbreviation_nym(self):
        assert normalize_mlb_team_name("NYM") == "NYM"

    def test_abbreviation_kc(self):
        assert normalize_mlb_team_name("KC") == "KC"

    def test_abbreviation_tb(self):
        assert normalize_mlb_team_name("TB") == "TB"

    def test_abbreviation_oak_maps_to_ath(self):
        assert normalize_mlb_team_name("OAK") == "ATH"

    # ── Full names (case-insensitive) ─────────────────────────────────────────
    def test_full_los_angeles_dodgers(self):
        assert normalize_mlb_team_name("Los Angeles Dodgers") == "LAD"

    def test_full_new_york_yankees(self):
        assert normalize_mlb_team_name("New York Yankees") == "NYY"

    def test_full_st_louis_cardinals(self):
        assert normalize_mlb_team_name("St. Louis Cardinals") == "STL"

    def test_full_toronto_blue_jays(self):
        assert normalize_mlb_team_name("Toronto Blue Jays") == "TOR"

    def test_full_seattle_mariners(self):
        assert normalize_mlb_team_name("Seattle Mariners") == "SEA"

    def test_full_san_francisco_giants(self):
        assert normalize_mlb_team_name("San Francisco Giants") == "SF"

    def test_full_san_diego_padres(self):
        assert normalize_mlb_team_name("San Diego Padres") == "SD"

    def test_full_washington_nationals(self):
        assert normalize_mlb_team_name("Washington Nationals") == "WSH"

    def test_full_arizona_diamondbacks(self):
        assert normalize_mlb_team_name("Arizona Diamondbacks") == "ARI"

    def test_full_oakland_athletics(self):
        assert normalize_mlb_team_name("Oakland Athletics") == "ATH"

    # ── Nicknames ─────────────────────────────────────────────────────────────
    def test_nickname_dodgers(self):
        assert normalize_mlb_team_name("Dodgers") == "LAD"

    def test_nickname_yankees(self):
        assert normalize_mlb_team_name("Yankees") == "NYY"

    def test_nickname_red_sox(self):
        assert normalize_mlb_team_name("Red Sox") == "BOS"

    def test_nickname_blue_jays(self):
        assert normalize_mlb_team_name("Blue Jays") == "TOR"

    def test_nickname_guardians(self):
        assert normalize_mlb_team_name("Guardians") == "CLE"

    def test_nickname_cubs(self):
        assert normalize_mlb_team_name("Cubs") == "CHC"

    # ── Case insensitivity ────────────────────────────────────────────────────
    def test_lowercase_abbreviation(self):
        assert normalize_mlb_team_name("lad") == "LAD"

    def test_mixed_case_full_name(self):
        assert normalize_mlb_team_name("los angeles dodgers") == "LAD"

    # ── Unknown fallback ──────────────────────────────────────────────────────
    def test_unknown_returns_uppercased(self):
        result = normalize_mlb_team_name("UnknownTeam")
        assert result == "UNKNOWNTEAM"

    def test_unknown_number_string(self):
        result = normalize_mlb_team_name("123XYZ")
        assert isinstance(result, str)
        assert len(result) > 0

    # ── All 30 teams coverage ─────────────────────────────────────────────────
    @pytest.mark.parametrize("full_name,expected_code", [
        ("Arizona Diamondbacks", "ARI"),
        ("Atlanta Braves", "ATL"),
        ("Baltimore Orioles", "BAL"),
        ("Boston Red Sox", "BOS"),
        ("Chicago Cubs", "CHC"),
        ("Chicago White Sox", "CWS"),
        ("Cincinnati Reds", "CIN"),
        ("Cleveland Guardians", "CLE"),
        ("Colorado Rockies", "COL"),
        ("Detroit Tigers", "DET"),
        ("Houston Astros", "HOU"),
        ("Kansas City Royals", "KC"),
        ("Los Angeles Angels", "LAA"),
        ("Los Angeles Dodgers", "LAD"),
        ("Miami Marlins", "MIA"),
        ("Milwaukee Brewers", "MIL"),
        ("Minnesota Twins", "MIN"),
        ("New York Mets", "NYM"),
        ("New York Yankees", "NYY"),
        ("Philadelphia Phillies", "PHI"),
        ("Pittsburgh Pirates", "PIT"),
        ("San Diego Padres", "SD"),
        ("San Francisco Giants", "SF"),
        ("Seattle Mariners", "SEA"),
        ("St. Louis Cardinals", "STL"),
        ("Tampa Bay Rays", "TB"),
        ("Texas Rangers", "TEX"),
        ("Toronto Blue Jays", "TOR"),
        ("Washington Nationals", "WSH"),
    ])
    def test_all_30_teams_by_full_name(self, full_name, expected_code):
        assert normalize_mlb_team_name(full_name) == expected_code


# ─────────────────────────────────────────────────────────────────────────────
# § 2  audit_prediction_join_integrity — contract
# ─────────────────────────────────────────────────────────────────────────────

def _make_audit_row(
    *,
    date: str = "2025-05-01",
    home: str = "Los Angeles Dodgers",
    away: str = "San Francisco Giants",
    game_id: str = "",
) -> dict:
    row: dict = {"Date": date, "Home": home, "Away": away}
    if game_id:
        row["game_id"] = game_id
    return row


class TestAuditPredictionJoinIntegrityContract:
    def test_returns_dict(self):
        result = audit_prediction_join_integrity([])
        assert isinstance(result, dict)

    def test_required_keys(self):
        result = audit_prediction_join_integrity([])
        required = {
            "row_count",
            "unique_game_id_count",
            "duplicate_game_id_count",
            "unique_date_team_key_count",
            "duplicate_date_team_key_count",
            "missing_game_id_count",
            "missing_date_count",
            "missing_home_team_count",
            "missing_away_team_count",
            "same_home_away_count",
            "normalization_examples",
            "risk_level",
            "risk_reasons",
        }
        assert required.issubset(result.keys()), f"Missing: {required - result.keys()}"

    def test_empty_rows(self):
        result = audit_prediction_join_integrity([])
        assert result["row_count"] == 0
        assert result["missing_game_id_count"] == 0
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_risk_level_valid(self):
        result = audit_prediction_join_integrity([_make_audit_row()])
        assert result["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_risk_reasons_is_list(self):
        result = audit_prediction_join_integrity([_make_audit_row()])
        assert isinstance(result["risk_reasons"], list)

    def test_normalization_examples_is_list(self):
        result = audit_prediction_join_integrity([_make_audit_row()])
        assert isinstance(result["normalization_examples"], list)


class TestAuditMissingGameId:
    def test_missing_game_id_all(self):
        rows = [_make_audit_row() for _ in range(5)]
        result = audit_prediction_join_integrity(rows)
        assert result["missing_game_id_count"] == 5

    def test_no_missing_game_id(self):
        rows = [_make_audit_row(game_id=f"g00{i}") for i in range(5)]
        result = audit_prediction_join_integrity(rows)
        assert result["missing_game_id_count"] == 0

    def test_partial_missing_game_id(self):
        rows = [_make_audit_row(game_id="g001"), _make_audit_row(), _make_audit_row(game_id="g002")]
        result = audit_prediction_join_integrity(rows)
        assert result["missing_game_id_count"] == 1


class TestAuditDuplicateGameId:
    def test_no_duplicates(self):
        rows = [_make_audit_row(game_id=f"g{i:03d}") for i in range(5)]
        result = audit_prediction_join_integrity(rows)
        assert result["duplicate_game_id_count"] == 0

    def test_one_duplicate_pair(self):
        rows = [
            _make_audit_row(game_id="g001", date="2025-05-01"),
            _make_audit_row(game_id="g001", date="2025-05-02"),
            _make_audit_row(game_id="g002"),
        ]
        result = audit_prediction_join_integrity(rows)
        assert result["duplicate_game_id_count"] == 1


class TestAuditDuplicateDateTeamKey:
    def test_no_duplicate_date_team(self):
        rows = [
            _make_audit_row(date="2025-05-01", home="Los Angeles Dodgers", away="San Francisco Giants"),
            _make_audit_row(date="2025-05-02", home="Los Angeles Dodgers", away="San Francisco Giants"),
        ]
        result = audit_prediction_join_integrity(rows)
        assert result["duplicate_date_team_key_count"] == 0

    def test_duplicate_date_team_detected(self):
        rows = [
            _make_audit_row(date="2025-05-01", home="Los Angeles Dodgers", away="San Francisco Giants"),
            _make_audit_row(date="2025-05-01", home="Los Angeles Dodgers", away="San Francisco Giants"),
        ]
        result = audit_prediction_join_integrity(rows)
        assert result["duplicate_date_team_key_count"] >= 1

    def test_duplicate_escalates_risk_level(self):
        rows = [
            _make_audit_row(date="2025-05-01", home="Los Angeles Dodgers", away="San Francisco Giants"),
            _make_audit_row(date="2025-05-01", home="Los Angeles Dodgers", away="San Francisco Giants"),
        ]
        result = audit_prediction_join_integrity(rows)
        assert result["risk_level"] == "HIGH"


class TestAuditSameTeam:
    def test_same_team_flagged(self):
        rows = [_make_audit_row(home="Los Angeles Dodgers", away="Los Angeles Dodgers")]
        result = audit_prediction_join_integrity(rows)
        assert result["same_home_away_count"] == 1

    def test_different_teams_no_flag(self):
        rows = [_make_audit_row(home="Los Angeles Dodgers", away="San Francisco Giants")]
        result = audit_prediction_join_integrity(rows)
        assert result["same_home_away_count"] == 0


class TestAuditLowRisk:
    def test_clean_rows_low_risk(self):
        rows = [
            _make_audit_row(game_id=f"g{i:03d}", date=f"2025-05-{i+1:02d}")
            for i in range(5)
        ]
        result = audit_prediction_join_integrity(rows)
        assert result["risk_level"] == "LOW"
        assert result["risk_reasons"] == []


class TestAuditNormalizationExamples:
    def test_examples_populated(self):
        rows = [
            _make_audit_row(home="Los Angeles Dodgers", away="San Francisco Giants")
            for _ in range(3)
        ]
        result = audit_prediction_join_integrity(rows)
        examples = result["normalization_examples"]
        assert len(examples) >= 1
        ex = examples[0]
        assert "home_raw" in ex
        assert "away_raw" in ex
        assert "home_norm" in ex
        assert "away_norm" in ex

    def test_examples_capped_at_5(self):
        rows = [
            _make_audit_row(
                game_id=f"g{i:03d}",
                home="Los Angeles Dodgers",
                away="San Francisco Giants"
            )
            for i in range(20)
        ]
        result = audit_prediction_join_integrity(rows)
        assert len(result["normalization_examples"]) <= 5


class TestAuditMissingTeams:
    def test_missing_home_counted(self):
        rows = [{"Date": "2025-05-01", "Away": "San Francisco Giants", "home_win": "1"}]
        result = audit_prediction_join_integrity(rows)
        assert result["missing_home_team_count"] == 1

    def test_missing_away_counted(self):
        rows = [{"Date": "2025-05-01", "Home": "Los Angeles Dodgers", "home_win": "1"}]
        result = audit_prediction_join_integrity(rows)
        assert result["missing_away_team_count"] == 1
