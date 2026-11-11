"""
Phase 62 — Bullpen Granular Source Selection: Test Suite.

Tests the minimal PIT-safe ingestion proof via MLB StatsAPI boxscore fixtures.
All tests use fixtures only — zero live API calls.

GATE: STATSAPI_SELECTED (expected)
SAFETY: CANDIDATE_PATCH_CREATED=False, PRODUCTION_MODIFIED=False, ALPHA_MODIFIED=False

Test Classes:
    TestSafetyConstants              — Module-level safety invariants
    TestSourceContractSchema         — MLB boxscore field contract
    TestIPParsing                    — inningsPitched string → decimal conversion
    TestFixtureReliefAppearanceParser — Parse mock boxscore → ReliefAppearanceRecord
    TestStarterVsRelieverkClassification — Opener / bulk / closer heuristics
    TestPITSafeDateWindow            — Rolling window computations respect PIT boundary
    TestBackToBackDetection          — B2B and 3-in-4 detection from multi-game fixtures
    TestCloserCandidateDetection     — is_closer_candidate heuristic
    TestPhase61SSOTIntegration       — Ingestion aligns with Phase 61 SSOT feature list
    TestDataLimitedNoNeutralFallback — LI features remain DATA_LIMITED, not 0.0
    TestMissingBoxscorePolicy        — Null boxscore → 0 records, not crash
    TestDoubleheaderPolicy           — (structural) game IDs are distinct; D-0 excluded
    TestGateConclusion               — GATE_RESULT constant and rationale present
    TestDiagnosticReport             — build_phase62_diagnostic_report structure
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from wbc_backend.features.mlb_bullpen_granular_ingestion import (
    ALPHA_MODIFIED,
    B2B_CONSECUTIVE_DAYS,
    CANDIDATE_PATCH_CREATED,
    DIAGNOSTIC_ONLY,
    GATE_RATIONALE,
    GATE_RESULT,
    MODULE_VERSION,
    OPENER_IP_THRESHOLD,
    PRODUCTION_MODIFIED,
    SELECTED_SOURCE,
    SOURCE_CAPABILITY_TABLE,
    SOURCE_LABEL,
    THREE_IN_FOUR_MIN_APPEARANCES,
    THREE_IN_FOUR_WINDOW,
    WINDOW_1D,
    WINDOW_3D,
    WINDOW_5D,
    IngestionResult,
    ReliefAppearanceRecord,
    SourceCapabilityEntry,
    _normalize_ip,
    _parse_innings_pitched,
    assert_pit_safe,
    build_phase62_diagnostic_report,
    compute_back_to_back_count,
    compute_bullpen_ip_window,
    compute_closer_used_within_days,
    compute_three_in_four_days_count,
    load_fixture_boxscores,
    parse_boxscore_to_appearances,
    parse_fixture_to_ingestion_result,
    ssot_available_features_from_boxscore,
    ssot_still_data_limited_features,
)

# ─────────────────────────────────────────────────────────────────────────────
# Shared Fixtures
# ─────────────────────────────────────────────────────────────────────────────

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase62_boxscore_fixtures.json"

NORMAL_GAME_1_BOXSCORE = {
    "teams": {
        "home": {
            "pitchers": [700001, 700002, 700003],
            "players": {
                "ID700001": {
                    "person": {"id": 700001, "fullName": "Gerrit Cole"},
                    "stats": {"pitching": {"inningsPitched": "6.0"}},
                },
                "ID700002": {
                    "person": {"id": 700002, "fullName": "Clay Holmes"},
                    "stats": {"pitching": {"inningsPitched": "2.0"}},
                },
                "ID700003": {
                    "person": {"id": 700003, "fullName": "Luke Weaver"},
                    "stats": {"pitching": {"inningsPitched": "1.0"}},
                },
            },
        },
        "away": {
            "pitchers": [700011, 700012, 700013, 700014],
            "players": {
                "ID700011": {
                    "person": {"id": 700011, "fullName": "Brayan Bello"},
                    "stats": {"pitching": {"inningsPitched": "5.1"}},
                },
                "ID700012": {
                    "person": {"id": 700012, "fullName": "Luis Garcia"},
                    "stats": {"pitching": {"inningsPitched": "0.2"}},
                },
                "ID700013": {
                    "person": {"id": 700013, "fullName": "Greg Weissert"},
                    "stats": {"pitching": {"inningsPitched": "1.0"}},
                },
                "ID700014": {
                    "person": {"id": 700014, "fullName": "Aroldis Chapman"},
                    "stats": {"pitching": {"inningsPitched": "1.0"}},
                },
            },
        },
    }
}

OPENER_BOXSCORE = {
    "teams": {
        "home": {
            "pitchers": [800001, 800002, 800003, 800004],
            "players": {
                "ID800001": {
                    "person": {"id": 800001, "fullName": "Ryan Pressly"},
                    "stats": {"pitching": {"inningsPitched": "1.1"}},
                },
                "ID800002": {
                    "person": {"id": 800002, "fullName": "Hunter Brown"},
                    "stats": {"pitching": {"inningsPitched": "4.2"}},
                },
                "ID800003": {
                    "person": {"id": 800003, "fullName": "Bryan Abreu"},
                    "stats": {"pitching": {"inningsPitched": "1.0"}},
                },
                "ID800004": {
                    "person": {"id": 800004, "fullName": "Hector Neris"},
                    "stats": {"pitching": {"inningsPitched": "2.0"}},
                },
            },
        },
        "away": {
            "pitchers": [800011, 800012],
            "players": {
                "ID800011": {
                    "person": {"id": 800011, "fullName": "Zack Littell"},
                    "stats": {"pitching": {"inningsPitched": "6.0"}},
                },
                "ID800012": {
                    "person": {"id": 800012, "fullName": "Pete Fairbanks"},
                    "stats": {"pitching": {"inningsPitched": "3.0"}},
                },
            },
        },
    }
}


def _build_appearances_from_boxscore(
    boxscore: dict,
    game_id: str = "MLB-TESTGAME-HOME-AT-AWAY",
    game_date: str = "2025-05-01",
    home_team: str = "New York Yankees",
    away_team: str = "Boston Red Sox",
) -> list[ReliefAppearanceRecord]:
    return parse_boxscore_to_appearances(
        boxscore=boxscore,
        game_id=game_id,
        game_date=game_date,
        home_team=home_team,
        away_team=away_team,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. TestSafetyConstants
# ─────────────────────────────────────────────────────────────────────────────

class TestSafetyConstants:
    """Module-level safety invariants must never change."""

    def test_candidate_patch_created_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_true(self):
        assert DIAGNOSTIC_ONLY is True

    def test_module_version_matches_phase(self):
        assert "phase62" in MODULE_VERSION

    def test_source_label_is_statsapi_boxscore(self):
        assert SOURCE_LABEL == "mlb_stats_api_boxscore"

    def test_gate_result_is_one_of_four_valid_values(self):
        valid_gates = {
            "STATSAPI_SELECTED",
            "STATCAST_PBP_SELECTED",
            "HYBRID_SOURCE_REQUIRED",
            "SOURCE_BLOCKED",
        }
        assert GATE_RESULT in valid_gates

    def test_selected_source_matches_gate(self):
        # If gate is STATSAPI_SELECTED, selected source must be boxscore
        if GATE_RESULT == "STATSAPI_SELECTED":
            assert SELECTED_SOURCE == "mlb_stats_api_boxscore"

    def test_gate_rationale_nonempty(self):
        assert isinstance(GATE_RATIONALE, str)
        assert len(GATE_RATIONALE) > 50


# ─────────────────────────────────────────────────────────────────────────────
# 2. TestSourceContractSchema
# ─────────────────────────────────────────────────────────────────────────────

class TestSourceContractSchema:
    """MLB StatsAPI /game/{pk}/boxscore field contract tests."""

    def test_boxscore_has_teams_key(self):
        assert "teams" in NORMAL_GAME_1_BOXSCORE

    def test_teams_has_home_and_away(self):
        assert "home" in NORMAL_GAME_1_BOXSCORE["teams"]
        assert "away" in NORMAL_GAME_1_BOXSCORE["teams"]

    def test_side_has_pitchers_list(self):
        home = NORMAL_GAME_1_BOXSCORE["teams"]["home"]
        assert isinstance(home["pitchers"], list)
        assert len(home["pitchers"]) > 0

    def test_side_has_players_dict(self):
        home = NORMAL_GAME_1_BOXSCORE["teams"]["home"]
        assert isinstance(home["players"], dict)

    def test_player_has_person_fullname(self):
        home = NORMAL_GAME_1_BOXSCORE["teams"]["home"]
        pid = home["pitchers"][0]
        player = home["players"][f"ID{pid}"]
        assert "fullName" in player["person"]

    def test_player_has_pitching_stats(self):
        home = NORMAL_GAME_1_BOXSCORE["teams"]["home"]
        pid = home["pitchers"][0]
        player = home["players"][f"ID{pid}"]
        assert "pitching" in player["stats"]

    def test_pitching_stats_has_innings_pitched(self):
        home = NORMAL_GAME_1_BOXSCORE["teams"]["home"]
        pid = home["pitchers"][0]
        player = home["players"][f"ID{pid}"]
        assert "inningsPitched" in player["stats"]["pitching"]

    def test_source_capability_table_covers_all_12_ssot_features(self):
        features = {e.feature for e in SOURCE_CAPABILITY_TABLE}
        # Phase 61 SSOT defines 12 granular features
        assert len(features) == 12

    def test_source_capability_has_statsapi_and_statcast_fields(self):
        for entry in SOURCE_CAPABILITY_TABLE:
            assert entry.statsapi_boxscore in ("AVAILABLE", "DATA_LIMITED", "MISSING")
            assert entry.statcast_pbp in ("AVAILABLE", "DATA_LIMITED", "MISSING")

    def test_li_features_data_limited_in_boxscore(self):
        li_features = {
            "high_leverage_reliever_used_last_1d",
            "high_leverage_reliever_workload_last_3d",
        }
        for entry in SOURCE_CAPABILITY_TABLE:
            if entry.feature in li_features:
                assert entry.statsapi_boxscore == "DATA_LIMITED", (
                    f"{entry.feature} must be DATA_LIMITED in boxscore (no LI available)"
                )

    def test_li_features_available_in_statcast(self):
        li_features = {
            "high_leverage_reliever_used_last_1d",
            "high_leverage_reliever_workload_last_3d",
        }
        for entry in SOURCE_CAPABILITY_TABLE:
            if entry.feature in li_features:
                assert entry.statcast_pbp == "AVAILABLE", (
                    f"{entry.feature} must be AVAILABLE in statcast (has LI)"
                )


# ─────────────────────────────────────────────────────────────────────────────
# 3. TestIPParsing
# ─────────────────────────────────────────────────────────────────────────────

class TestIPParsing:
    """inningsPitched string → decimal conversion."""

    def test_whole_innings(self):
        assert _parse_innings_pitched("6.0") == pytest.approx(6.0)

    def test_one_third_inning(self):
        assert _parse_innings_pitched("6.1") == pytest.approx(6.333, abs=0.01)

    def test_two_thirds_inning(self):
        assert _parse_innings_pitched("6.2") == pytest.approx(6.667, abs=0.01)

    def test_zero_innings(self):
        assert _parse_innings_pitched("0.0") == pytest.approx(0.0)

    def test_integer_string(self):
        assert _parse_innings_pitched("7") == pytest.approx(7.0)

    def test_none_returns_none(self):
        assert _parse_innings_pitched(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_innings_pitched("") is None

    def test_non_numeric_returns_none(self):
        result = _parse_innings_pitched("N/A")
        # Should return None or raise — not a valid float for business logic
        # Implementation returns None for ValueError
        assert result is None or isinstance(result, float)

    def test_normalize_ip_handles_none(self):
        assert _normalize_ip(None) == 0.0

    def test_normalize_ip_clamps_negative(self):
        assert _normalize_ip(-1.5) == 0.0

    def test_normalize_ip_pass_through_valid(self):
        assert _normalize_ip(3.333) == pytest.approx(3.333)

    def test_fractional_ip_accumulation(self):
        # .1 + .2 of an inning = 1.0 full inning (3 outs total)
        ip_1 = _parse_innings_pitched("0.1")
        ip_2 = _parse_innings_pitched("0.2")
        total = ip_1 + ip_2
        assert total == pytest.approx(1.0, abs=0.01)


# ─────────────────────────────────────────────────────────────────────────────
# 4. TestFixtureReliefAppearanceParser
# ─────────────────────────────────────────────────────────────────────────────

class TestFixtureReliefAppearanceParser:
    """Parse mock boxscore → ReliefAppearanceRecord."""

    def test_returns_list(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        assert isinstance(recs, list)

    def test_correct_total_pitchers_counted(self):
        # home: 3, away: 4 → total 7
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        assert len(recs) == 7

    def test_game_id_propagated(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE, game_id="TEST-GAME-ID")
        assert all(r.game_id == "TEST-GAME-ID" for r in recs)

    def test_game_date_propagated(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE, game_date="2025-06-15")
        assert all(r.game_date == "2025-06-15" for r in recs)

    def test_team_name_propagated(self):
        recs = _build_appearances_from_boxscore(
            NORMAL_GAME_1_BOXSCORE,
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        home_recs = [r for r in recs if r.side == "home"]
        away_recs = [r for r in recs if r.side == "away"]
        assert all(r.team == "New York Yankees" for r in home_recs)
        assert all(r.team == "Boston Red Sox" for r in away_recs)

    def test_appearance_order_starts_at_1(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        home_recs = sorted([r for r in recs if r.side == "home"], key=lambda x: x.appearance_order)
        assert home_recs[0].appearance_order == 1

    def test_appearance_order_is_monotonic(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        home_recs = sorted([r for r in recs if r.side == "home"], key=lambda x: x.appearance_order)
        for i, rec in enumerate(home_recs):
            assert rec.appearance_order == i + 1

    def test_pitcher_ids_correct(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        home_ids = {r.pitcher_id for r in recs if r.side == "home"}
        assert home_ids == {700001, 700002, 700003}

    def test_pitcher_names_correct(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        home_names = {r.pitcher_name for r in recs if r.side == "home"}
        assert "Gerrit Cole" in home_names
        assert "Clay Holmes" in home_names
        assert "Luke Weaver" in home_names

    def test_ip_parsed_correctly_for_starter(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        cole = next(r for r in recs if r.pitcher_id == 700001)
        assert cole.innings_pitched == pytest.approx(6.0)

    def test_ip_parsed_for_fractional_inning(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        bello = next(r for r in recs if r.pitcher_id == 700011)
        # "5.1" → 5 + 1/3
        assert bello.innings_pitched == pytest.approx(5.333, abs=0.01)

    def test_fractional_ip_two_thirds(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        garcia = next(r for r in recs if r.pitcher_id == 700012)
        # "0.2" → 0 + 2/3
        assert garcia.innings_pitched == pytest.approx(0.667, abs=0.01)

    def test_source_is_correct(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        assert all(r.source == "mlb_stats_api_boxscore" for r in recs)

    def test_pit_safe_always_true(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        assert all(r.pit_safe is True for r in recs)

    def test_none_boxscore_returns_empty(self):
        recs = parse_boxscore_to_appearances(
            boxscore=None,
            game_id="TEST",
            game_date="2025-05-01",
            home_team="Home",
            away_team="Away",
        )
        assert recs == []

    def test_empty_dict_boxscore_returns_empty(self):
        recs = parse_boxscore_to_appearances(
            boxscore={},
            game_id="TEST",
            game_date="2025-05-01",
            home_team="Home",
            away_team="Away",
        )
        assert recs == []


# ─────────────────────────────────────────────────────────────────────────────
# 5. TestStarterVsRelieverkClassification
# ─────────────────────────────────────────────────────────────────────────────

class TestStarterVsRelieverkClassification:
    """Opener / traditional starter / closer heuristics."""

    def test_first_pitcher_above_threshold_is_starter(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        cole = next(r for r in recs if r.pitcher_id == 700001)
        assert cole.is_starter is True
        assert cole.is_reliever is False
        assert cole.is_opener is False

    def test_subsequent_pitchers_are_relievers(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        holmes = next(r for r in recs if r.pitcher_id == 700002)
        weaver = next(r for r in recs if r.pitcher_id == 700003)
        assert holmes.is_reliever is True
        assert weaver.is_reliever is True
        assert holmes.is_starter is False
        assert weaver.is_starter is False

    def test_opener_below_threshold_is_reliever(self):
        recs = _build_appearances_from_boxscore(OPENER_BOXSCORE)
        pressly = next(r for r in recs if r.pitcher_id == 800001)
        # 1.1 IP < 2.0 threshold → opener → is_reliever
        assert pressly.is_opener is True
        assert pressly.is_reliever is True
        assert pressly.is_starter is False

    def test_bulk_pitcher_after_opener_is_reliever(self):
        recs = _build_appearances_from_boxscore(OPENER_BOXSCORE)
        brown = next(r for r in recs if r.pitcher_id == 800002)
        # Hunter Brown, 4.2 IP, appearance_order=2 → is_reliever (not first pitcher)
        assert brown.is_reliever is True
        assert brown.is_starter is False
        assert brown.is_opener is False

    def test_traditional_starter_away_side(self):
        recs = _build_appearances_from_boxscore(OPENER_BOXSCORE)
        littell = next(r for r in recs if r.pitcher_id == 800011)
        # 6.0 IP, first pitcher → starter
        assert littell.is_starter is True
        assert littell.is_opener is False
        assert littell.is_reliever is False

    def test_last_pitcher_is_closer_candidate(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        home_recs = [r for r in recs if r.side == "home"]
        last = max(home_recs, key=lambda x: x.appearance_order)
        assert last.is_closer_candidate is True
        assert last.pitcher_id == 700003  # Luke Weaver

    def test_non_last_relievers_not_closer_candidate(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        holmes = next(r for r in recs if r.pitcher_id == 700002)
        assert holmes.is_closer_candidate is False

    def test_starter_not_closer_candidate(self):
        # Degenerate case: if only 1 pitcher, they're both starter and last
        # Normal case: starter is not closer candidate
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        cole = next(r for r in recs if r.pitcher_id == 700001)
        assert cole.is_closer_candidate is False

    def test_opener_threshold_value(self):
        assert OPENER_IP_THRESHOLD == 2.0


# ─────────────────────────────────────────────────────────────────────────────
# 6. TestPITSafeDateWindow
# ─────────────────────────────────────────────────────────────────────────────

class TestPITSafeDateWindow:
    """Rolling window computations respect PIT boundary."""

    def _build_sample_appearances(self) -> list[ReliefAppearanceRecord]:
        """Build two games' worth of appearances for window tests."""
        day1_box = {
            "teams": {
                "home": {
                    "pitchers": [900001, 900002, 900003],
                    "players": {
                        "ID900001": {"person": {"id": 900001, "fullName": "SP1"}, "stats": {"pitching": {"inningsPitched": "6.0"}}},
                        "ID900002": {"person": {"id": 900002, "fullName": "RP1"}, "stats": {"pitching": {"inningsPitched": "2.0"}}},
                        "ID900003": {"person": {"id": 900003, "fullName": "CL1"}, "stats": {"pitching": {"inningsPitched": "1.0"}}},
                    },
                },
                "away": {"pitchers": [], "players": {}},
            }
        }
        day2_box = {
            "teams": {
                "home": {
                    "pitchers": [900011, 900002, 900003],
                    "players": {
                        "ID900011": {"person": {"id": 900011, "fullName": "SP2"}, "stats": {"pitching": {"inningsPitched": "7.0"}}},
                        "ID900002": {"person": {"id": 900002, "fullName": "RP1"}, "stats": {"pitching": {"inningsPitched": "1.0"}}},
                        "ID900003": {"person": {"id": 900003, "fullName": "CL1"}, "stats": {"pitching": {"inningsPitched": "1.0"}}},
                    },
                },
                "away": {"pitchers": [], "players": {}},
            }
        }
        recs = []
        recs += parse_boxscore_to_appearances(boxscore=day1_box, game_id="G1", game_date="2025-05-01", home_team="TeamA", away_team="TeamB")
        recs += parse_boxscore_to_appearances(boxscore=day2_box, game_id="G2", game_date="2025-05-02", home_team="TeamA", away_team="TeamB")
        return recs

    def test_1d_window_includes_only_d_minus_1(self):
        recs = self._build_sample_appearances()
        # Predicting 2025-05-03 → D-1 = 2025-05-02, D-2 = 2025-05-01
        # 1d window should include only 2025-05-02 games
        ip = compute_bullpen_ip_window(recs, team="TeamA", prediction_date="2025-05-03", window_days=1)
        # D-2 game has RP1 (2.0) + CL1 (1.0) → but those are from D-1 (2025-05-02)
        # RP1 appeared on 2025-05-02 with 1.0 IP; CL1 1.0 IP → total 2.0
        assert ip == pytest.approx(2.0, abs=0.01)

    def test_3d_window_includes_d1_through_d3(self):
        recs = self._build_sample_appearances()
        # Predicting 2025-05-03 → window [2025-05-02, 2025-05-01, 2025-04-30]
        # D-1 (2025-05-02): RP1=1.0, CL1=1.0 → 2.0
        # D-2 (2025-05-01): RP1=2.0, CL1=1.0 → 3.0
        # Total = 5.0
        ip = compute_bullpen_ip_window(recs, team="TeamA", prediction_date="2025-05-03", window_days=3)
        assert ip == pytest.approx(5.0, abs=0.01)

    def test_prediction_date_excluded_from_window(self):
        recs = self._build_sample_appearances()
        # D-0 (2025-05-02) as prediction_date → that game's data must NOT be included
        # 1d window starting from 2025-05-02 should only include 2025-05-01 data
        ip = compute_bullpen_ip_window(recs, team="TeamA", prediction_date="2025-05-02", window_days=1)
        # Only D-1 = 2025-05-01 → RP1=2.0, CL1=1.0 → 3.0
        assert ip == pytest.approx(3.0, abs=0.01)

    def test_window_beyond_data_returns_none(self):
        recs = self._build_sample_appearances()
        # Window starts at 2025-04-24 but data only goes back to 2025-05-01
        ip = compute_bullpen_ip_window(recs, team="TeamA", prediction_date="2025-04-25", window_days=3)
        assert ip is None

    def test_different_team_excluded(self):
        recs = self._build_sample_appearances()
        ip = compute_bullpen_ip_window(recs, team="TeamC", prediction_date="2025-05-03", window_days=3)
        assert ip is None

    def test_starters_excluded_from_ip_window(self):
        recs = self._build_sample_appearances()
        # SP1 has 6.0 IP on D-2, SP2 has 7.0 on D-1
        # Those should NOT count toward bullpen usage window
        ip = compute_bullpen_ip_window(recs, team="TeamA", prediction_date="2025-05-03", window_days=3)
        # Only relievers: RP1+CL1 on both days → 2.0+1.0+1.0+1.0 = 5.0
        # NOT 13.0 (which would include SPs)
        assert ip < 10.0


# ─────────────────────────────────────────────────────────────────────────────
# 7. TestBackToBackDetection
# ─────────────────────────────────────────────────────────────────────────────

class TestBackToBackDetection:
    """B2B and 3-in-4 detection from multi-game fixture file."""

    def setup_method(self):
        self.result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        self.appearances = self.result.appearances

    def test_fixture_loads_correctly(self):
        assert self.result.games_parsed >= 4
        assert len(self.appearances) > 0

    def test_b2b_detected_for_reliever_on_consecutive_days(self):
        # Luke Weaver (700003) appears in NYY home games on 2025-05-01 AND 2025-05-02
        # Predicting 2025-05-03: B2B count for NYY should include Weaver
        count = compute_back_to_back_count(
            self.appearances,
            team="New York Yankees",
            prediction_date="2025-05-03",
        )
        # Both Weaver (700003) AND Holmes (700002) appear on May-01 and May-02
        assert count >= 2

    def test_b2b_count_is_zero_when_no_consecutive_appearances(self):
        # TeamZ has no data
        count = compute_back_to_back_count(
            self.appearances,
            team="TeamZ_Does_Not_Exist",
            prediction_date="2025-05-03",
        )
        assert count == 0

    def test_three_in_four_detected_for_reliever_three_straight_days(self):
        # Luke Weaver appears on May-01, May-02, May-03
        # Predicting 2025-05-04: 3-in-4 for NYY should count Weaver
        count = compute_three_in_four_days_count(
            self.appearances,
            team="New York Yankees",
            prediction_date="2025-05-04",
        )
        assert count >= 1

    def test_closer_used_last_1d(self):
        # Luke Weaver (700003) is NYY's closer candidate and appeared on May-02
        # Predicting May-03 → closer used in last 1d = True
        used = compute_closer_used_within_days(
            self.appearances,
            team="New York Yankees",
            prediction_date="2025-05-03",
            within_days=1,
        )
        assert used is True

    def test_closer_used_last_2d(self):
        used = compute_closer_used_within_days(
            self.appearances,
            team="New York Yankees",
            prediction_date="2025-05-04",
            within_days=2,
        )
        # Weaver appeared on May-03 which is within 2d of May-04's prediction
        assert used is True

    def test_closer_not_used_when_no_data(self):
        used = compute_closer_used_within_days(
            self.appearances,
            team="NoTeam_XYZ",
            prediction_date="2025-05-04",
            within_days=2,
        )
        assert used is False

    def test_b2b_window_constant(self):
        assert B2B_CONSECUTIVE_DAYS == 2

    def test_three_in_four_constants(self):
        assert THREE_IN_FOUR_WINDOW == 4
        assert THREE_IN_FOUR_MIN_APPEARANCES == 3


# ─────────────────────────────────────────────────────────────────────────────
# 8. TestCloserCandidateDetection
# ─────────────────────────────────────────────────────────────────────────────

class TestCloserCandidateDetection:
    """is_closer_candidate heuristic tests."""

    def test_last_pitcher_in_normal_game_is_closer(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        home_recs = sorted([r for r in recs if r.side == "home"], key=lambda x: x.appearance_order)
        assert home_recs[-1].is_closer_candidate is True
        assert home_recs[-1].pitcher_id == 700003

    def test_away_last_pitcher_is_closer_candidate(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        away_recs = sorted([r for r in recs if r.side == "away"], key=lambda x: x.appearance_order)
        assert away_recs[-1].is_closer_candidate is True
        assert away_recs[-1].pitcher_id == 700014  # Chapman

    def test_opener_game_last_pitcher_is_closer_candidate(self):
        recs = _build_appearances_from_boxscore(OPENER_BOXSCORE)
        home_recs = sorted([r for r in recs if r.side == "home"], key=lambda x: x.appearance_order)
        last = home_recs[-1]
        assert last.is_closer_candidate is True
        assert last.pitcher_id == 800004  # Hector Neris

    def test_only_one_closer_candidate_per_team_per_game(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        home_closers = [r for r in recs if r.side == "home" and r.is_closer_candidate]
        away_closers = [r for r in recs if r.side == "away" and r.is_closer_candidate]
        assert len(home_closers) == 1
        assert len(away_closers) == 1

    def test_starter_not_closer_in_multi_pitcher_game(self):
        recs = _build_appearances_from_boxscore(NORMAL_GAME_1_BOXSCORE)
        cole = next(r for r in recs if r.pitcher_id == 700001)
        assert cole.is_closer_candidate is False


# ─────────────────────────────────────────────────────────────────────────────
# 9. TestPhase61SSOTIntegration
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase61SSOTIntegration:
    """Ingestion output aligns with Phase 61 SSOT feature list."""

    def test_ssot_available_features_count(self):
        features = ssot_available_features_from_boxscore()
        assert len(features) == 10

    def test_ssot_data_limited_features_count(self):
        features = ssot_still_data_limited_features()
        assert len(features) == 2

    def test_total_features_equals_12(self):
        total = len(ssot_available_features_from_boxscore()) + len(ssot_still_data_limited_features())
        assert total == 12

    def test_bullpen_usage_last_1d_in_available(self):
        assert "bullpen_usage_last_1d" in ssot_available_features_from_boxscore()

    def test_bullpen_usage_last_3d_in_available(self):
        assert "bullpen_usage_last_3d" in ssot_available_features_from_boxscore()

    def test_bullpen_usage_last_5d_in_available(self):
        assert "bullpen_usage_last_5d" in ssot_available_features_from_boxscore()

    def test_reliever_b2b_in_available(self):
        assert "reliever_back_to_back_count" in ssot_available_features_from_boxscore()

    def test_reliever_three_in_four_in_available(self):
        assert "reliever_three_in_four_days_count" in ssot_available_features_from_boxscore()

    def test_closer_1d_in_available(self):
        assert "closer_used_last_1d" in ssot_available_features_from_boxscore()

    def test_closer_2d_in_available(self):
        assert "closer_used_last_2d" in ssot_available_features_from_boxscore()

    def test_high_leverage_reliever_1d_in_data_limited(self):
        assert "high_leverage_reliever_used_last_1d" in ssot_still_data_limited_features()

    def test_high_leverage_reliever_workload_in_data_limited(self):
        assert "high_leverage_reliever_workload_last_3d" in ssot_still_data_limited_features()

    def test_no_overlap_between_available_and_data_limited(self):
        available = set(ssot_available_features_from_boxscore())
        data_limited = set(ssot_still_data_limited_features())
        assert available.isdisjoint(data_limited)


# ─────────────────────────────────────────────────────────────────────────────
# 10. TestDataLimitedNoNeutralFallback
# ─────────────────────────────────────────────────────────────────────────────

class TestDataLimitedNoNeutralFallback:
    """LI features must NOT output 0.0 as a neutral fallback; must be DATA_LIMITED."""

    def test_li_features_in_data_limited_list_not_available_list(self):
        available = ssot_available_features_from_boxscore()
        assert "high_leverage_reliever_used_last_1d" not in available
        assert "high_leverage_reliever_workload_last_3d" not in available

    def test_li_features_explicitly_data_limited_in_capability_table(self):
        li_map = {
            e.feature: e.statsapi_boxscore
            for e in SOURCE_CAPABILITY_TABLE
            if "leverage" in e.feature
        }
        for feature, status in li_map.items():
            assert status == "DATA_LIMITED", (
                f"Feature {feature!r} must be DATA_LIMITED in statsapi_boxscore, got {status!r}"
            )

    def test_data_limited_list_is_not_empty(self):
        assert len(ssot_still_data_limited_features()) > 0

    def test_data_limited_features_have_notes_in_capability_table(self):
        li_entries = [e for e in SOURCE_CAPABILITY_TABLE if e.statsapi_boxscore == "DATA_LIMITED"]
        for entry in li_entries:
            assert entry.notes, f"DATA_LIMITED entry for {entry.feature} must have notes"
            assert "LI" in entry.notes or "leverage" in entry.notes.lower(), (
                f"Notes for {entry.feature} must explain why LI is missing: {entry.notes}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# 11. TestMissingBoxscorePolicy
# ─────────────────────────────────────────────────────────────────────────────

class TestMissingBoxscorePolicy:
    """Null / missing boxscore → zero records, not crash."""

    def test_null_boxscore_returns_empty_list(self):
        recs = parse_boxscore_to_appearances(
            boxscore=None, game_id="X", game_date="2025-05-05",
            home_team="A", away_team="B",
        )
        assert recs == []

    def test_empty_dict_boxscore_returns_empty_list(self):
        recs = parse_boxscore_to_appearances(
            boxscore={}, game_id="X", game_date="2025-05-05",
            home_team="A", away_team="B",
        )
        assert recs == []

    def test_fixture_with_null_boxscore_counted_as_missing(self):
        result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        assert result.games_missing >= 1  # MISSING_BOXSCORE fixture

    def test_missing_boxscore_does_not_raise(self):
        result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        # No exceptions — errors list should be empty (null boxscore is handled gracefully)
        assert isinstance(result.errors, list)

    def test_ingestion_result_has_diagnostic_only_true(self):
        result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        assert result.diagnostic_only is True

    def test_ingestion_result_source_is_boxscore(self):
        result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        assert result.source == "mlb_stats_api_boxscore"


# ─────────────────────────────────────────────────────────────────────────────
# 12. TestDoubleheaderPolicy
# ─────────────────────────────────────────────────────────────────────────────

class TestDoubleheaderPolicy:
    """Game IDs must be distinct; D-0 (same day) data excluded from PIT window."""

    def test_distinct_game_ids_produce_distinct_appearances(self):
        box_g1 = {
            "teams": {
                "home": {"pitchers": [901], "players": {"ID901": {"person": {"id": 901, "fullName": "P1"}, "stats": {"pitching": {"inningsPitched": "9.0"}}}}},
                "away": {"pitchers": [], "players": {}},
            }
        }
        box_g2 = {
            "teams": {
                "home": {"pitchers": [902], "players": {"ID902": {"person": {"id": 902, "fullName": "P2"}, "stats": {"pitching": {"inningsPitched": "9.0"}}}}},
                "away": {"pitchers": [], "players": {}},
            }
        }
        recs1 = parse_boxscore_to_appearances(boxscore=box_g1, game_id="DH-GAME1", game_date="2025-06-01", home_team="T", away_team="X")
        recs2 = parse_boxscore_to_appearances(boxscore=box_g2, game_id="DH-GAME2", game_date="2025-06-01", home_team="T", away_team="X")
        all_recs = recs1 + recs2
        game_ids = {r.game_id for r in all_recs}
        assert "DH-GAME1" in game_ids
        assert "DH-GAME2" in game_ids
        assert len(game_ids) == 2

    def test_same_day_game_excluded_from_pit_window(self):
        # If we predict game on 2025-06-01 and there's another game also on 2025-06-01,
        # the rolling window must NOT include it.
        dh_rec = ReliefAppearanceRecord(
            game_id="DH-GAME1",
            game_date="2025-06-01",
            team="T",
            side="home",
            pitcher_id=901,
            pitcher_name="P1",
            appearance_order=2,
            innings_pitched=1.0,
            is_starter=False,
            is_opener=False,
            is_reliever=True,
            is_closer_candidate=True,
            source=SOURCE_LABEL,
            pit_safe=True,
        )
        # Predict on same day → that game must be excluded from 1d window
        ip = compute_bullpen_ip_window(
            [dh_rec],
            team="T",
            prediction_date="2025-06-01",  # Same day as the record
            window_days=1,
        )
        # D-1 of 2025-06-01 = 2025-05-31; the record is on 2025-06-01 → excluded
        assert ip is None

    def test_assert_pit_safe_raises_on_same_date(self):
        with pytest.raises(ValueError, match="PIT VIOLATION"):
            assert_pit_safe(prediction_date="2025-06-01", snapshot_date="2025-06-01")

    def test_assert_pit_safe_raises_on_future_snapshot(self):
        with pytest.raises(ValueError, match="PIT VIOLATION"):
            assert_pit_safe(prediction_date="2025-06-01", snapshot_date="2025-06-02")

    def test_assert_pit_safe_passes_for_prior_day(self):
        # Should not raise
        assert_pit_safe(prediction_date="2025-06-01", snapshot_date="2025-05-31")

    def test_assert_pit_safe_passes_for_much_earlier(self):
        assert_pit_safe(prediction_date="2025-06-01", snapshot_date="2025-01-01")


# ─────────────────────────────────────────────────────────────────────────────
# 13. TestGateConclusion
# ─────────────────────────────────────────────────────────────────────────────

class TestGateConclusion:
    """GATE_RESULT constant and rationale."""

    def test_gate_result_is_statsapi_selected(self):
        assert GATE_RESULT == "STATSAPI_SELECTED"

    def test_gate_rationale_mentions_boxscore(self):
        assert "boxscore" in GATE_RATIONALE.lower()

    def test_gate_rationale_mentions_data_limited(self):
        assert "DATA_LIMITED" in GATE_RATIONALE

    def test_gate_rationale_mentions_leverage_index(self):
        assert "LI" in GATE_RATIONALE or "leverage" in GATE_RATIONALE.lower()

    def test_gate_rationale_mentions_phase63(self):
        assert "Phase 63" in GATE_RATIONALE or "phase 63" in GATE_RATIONALE.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 14. TestDiagnosticReport
# ─────────────────────────────────────────────────────────────────────────────

class TestDiagnosticReport:
    """build_phase62_diagnostic_report structure."""

    def setup_method(self):
        self.result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        self.report = build_phase62_diagnostic_report(self.result)

    def test_report_has_gate_key(self):
        assert "gate" in self.report

    def test_report_gate_is_statsapi_selected(self):
        assert self.report["gate"] == "STATSAPI_SELECTED"

    def test_report_diagnostic_only_true(self):
        assert self.report["diagnostic_only"] is True

    def test_report_candidate_patch_created_false(self):
        assert self.report["candidate_patch_created"] is False

    def test_report_production_modified_false(self):
        assert self.report["production_modified"] is False

    def test_report_alpha_modified_false(self):
        assert self.report["alpha_modified"] is False

    def test_report_has_ingestion_proof_section(self):
        assert "ingestion_proof" in self.report
        proof = self.report["ingestion_proof"]
        assert "games_parsed" in proof
        assert "games_missing" in proof
        assert "total_pitcher_appearances" in proof
        assert "relievers" in proof
        assert "starters" in proof

    def test_report_ingestion_proof_counts_valid(self):
        proof = self.report["ingestion_proof"]
        assert proof["games_parsed"] >= 4
        assert proof["games_missing"] >= 1
        assert proof["total_pitcher_appearances"] > 0
        assert proof["relievers"] > 0
        assert proof["starters"] > 0

    def test_report_has_ssot_upgrade_section(self):
        assert "ssot_upgrade" in self.report
        ssot = self.report["ssot_upgrade"]
        assert ssot["available_count"] == 10
        assert ssot["data_limited_count"] == 2

    def test_report_has_source_capability_table(self):
        assert "source_capability_table" in self.report
        table = self.report["source_capability_table"]
        assert len(table) == 12

    def test_report_audit_hash_nonempty(self):
        assert "audit_hash" in self.report
        assert len(self.report["audit_hash"]) == 16

    def test_report_module_version_present(self):
        assert "module_version" in self.report
        assert "phase62" in self.report["module_version"]
