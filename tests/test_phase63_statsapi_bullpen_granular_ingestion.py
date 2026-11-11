"""
tests/test_phase63_statsapi_bullpen_granular_ingestion.py
=========================================================
Phase 63 — StatsAPI-based Bullpen Granular Ingestion Implementation

Gate: GRANULAR_INGESTION_READY | DIAGNOSTIC_ARTIFACT_ONLY | DATA_QUALITY_BLOCKED | SOURCE_INTEGRATION_BLOCKED

Verifies:
  1. Safety constants (Phase 63 additions)
  2. NormalizedReliefAppearance schema & fields
  3. SSOTFeatureArtifact schema & DATA_LIMITED guards
  4. outs_recorded computation (float drift safety)
  5. parse_boxscore_to_normalized_appearances (Phase 63 parser)
  6. Edge case policies: doubleheader / postponed / suspended / opener / bulk pitcher
  7. compute_ssot_feature_artifact (1d/3d/5d/b2b/3-in-4/closer)
  8. PIT safety across all window functions
  9. Phase 63 diagnostic report structure & gate decision
 10. Backward compatibility with Phase 62 Module & gate
 11. Phase 62 regression smoke test (does not re-test full Phase 62 suite)

FIXTURE: tests/fixtures/phase62_boxscore_fixtures.json (4 games + 1 null)
  - NORMAL_GAME_1: 2025-05-01 NYY(home) vs BOS(away)
  - NORMAL_GAME_2: 2025-05-02 NYY vs BOS (Holmes/Weaver B2B)
  - NORMAL_GAME_3: 2025-05-03 NYY vs BOS (Weaver 3rd consecutive day)
  - OPENER_GAME:   2025-05-04 HOU(home) vs TB(away) (Pressly opener 1.1 IP)
  - MISSING_BOXSCORE: null → postponed

All tests are fixture-only; no live external API calls permitted.
"""

from __future__ import annotations

import dataclasses
import hashlib
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from wbc_backend.features.mlb_bullpen_granular_ingestion import (
    # Phase 62 constants (backward compat)
    MODULE_VERSION,
    GATE_RESULT,
    SELECTED_SOURCE,
    SOURCE_LABEL,
    OPENER_IP_THRESHOLD,
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    ALPHA_MODIFIED,
    DIAGNOSTIC_ONLY,
    # Phase 63 constants
    PHASE63_MODULE_VERSION,
    _DATA_LIMITED_SENTINEL,
    EDGE_CASE_POLICIES,
    # Phase 63 dataclasses
    NormalizedReliefAppearance,
    SSOTFeatureArtifact,
    # Phase 63 functions
    _compute_outs_recorded,
    _appearance_audit_hash,
    _build_opponent_map_from_appearances,
    parse_boxscore_to_normalized_appearances,
    parse_fixture_to_phase63_ingestion,
    build_availability_map,
    build_pit_window_map,
    compute_ssot_feature_artifact,
    build_phase63_diagnostic_report,
    # Phase 62 functions (backward compat)
    parse_fixture_to_ingestion_result,
    build_phase62_diagnostic_report,
    parse_boxscore_to_appearances,
    compute_bullpen_ip_window,
    compute_back_to_back_count,
    compute_three_in_four_days_count,
    compute_closer_used_within_days,
    ssot_available_features_from_boxscore,
    ssot_still_data_limited_features,
    # Phase 62 dataclasses (for helper functions)
    ReliefAppearanceRecord,
    IngestionResult,
)

# ---------------------------------------------------------------------------
# Fixture path
# ---------------------------------------------------------------------------
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "phase62_boxscore_fixtures.json"

# ---------------------------------------------------------------------------
# Minimal mock boxscore factory
# ---------------------------------------------------------------------------

def _make_minimal_boxscore(
    home_pitchers: list[dict[str, Any]],
    away_pitchers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a minimal StatsAPI-shaped boxscore dict for unit tests."""
    def _side(pitchers: list[dict]) -> dict:
        pitcher_ids = [p["id"] for p in pitchers]
        players = {}
        for p in pitchers:
            players[f"ID{p['id']}"] = {
                "person": {"id": p["id"], "fullName": p["name"]},
                "stats": {
                    "pitching": {
                        "inningsPitched": p.get("ip", "0.0"),
                        "numberOfPitches": p.get("pitches"),
                    }
                },
            }
        return {"pitchers": pitcher_ids, "players": players}

    return {"teams": {"home": _side(home_pitchers), "away": _side(away_pitchers)}}


def _make_appearance(
    game_date: str,
    team: str,
    pitcher_id: int,
    ip: float,
    is_reliever: bool = True,
    is_closer_candidate: bool = False,
) -> ReliefAppearanceRecord:
    return ReliefAppearanceRecord(
        game_id=f"TEST-{game_date}",
        game_date=game_date,
        team=team,
        side="home",
        pitcher_id=pitcher_id,
        pitcher_name=f"Pitcher_{pitcher_id}",
        appearance_order=2 if is_reliever else 1,
        innings_pitched=ip,
        is_starter=not is_reliever,
        is_opener=False,
        is_reliever=is_reliever,
        is_closer_candidate=is_closer_candidate,
        source=SOURCE_LABEL,
        pit_safe=True,
    )


# ===========================================================================
# 1. TestPhase63SafetyConstants
# ===========================================================================

class TestPhase63SafetyConstants:
    """Phase 63 module-level safety and version constants."""

    def test_phase63_module_version_is_string(self):
        assert isinstance(PHASE63_MODULE_VERSION, str)

    def test_phase63_module_version_starts_with_phase63(self):
        assert PHASE63_MODULE_VERSION.startswith("phase63")

    def test_data_limited_sentinel_value(self):
        assert _DATA_LIMITED_SENTINEL == "DATA_LIMITED"

    def test_edge_case_policies_is_dict(self):
        assert isinstance(EDGE_CASE_POLICIES, dict)

    def test_edge_case_policy_doubleheader_exists(self):
        assert "doubleheader" in EDGE_CASE_POLICIES

    def test_edge_case_policy_postponed_exists(self):
        assert "postponed" in EDGE_CASE_POLICIES

    def test_edge_case_policy_suspended_exists(self):
        assert "suspended" in EDGE_CASE_POLICIES

    def test_edge_case_policy_opener_exists(self):
        assert "opener" in EDGE_CASE_POLICIES
        assert str(OPENER_IP_THRESHOLD) in EDGE_CASE_POLICIES["opener"]

    def test_edge_case_policy_bulk_pitcher_exists(self):
        assert "bulk_pitcher" in EDGE_CASE_POLICIES

    # Safety constants inherited from Phase 62 must not change
    def test_candidate_patch_created_still_false(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_modified_still_false(self):
        assert PRODUCTION_MODIFIED is False

    def test_alpha_modified_still_false(self):
        assert ALPHA_MODIFIED is False

    def test_diagnostic_only_still_true(self):
        assert DIAGNOSTIC_ONLY is True


# ===========================================================================
# 2. TestNormalizedReliefAppearanceSchema
# ===========================================================================

class TestNormalizedReliefAppearanceSchema:
    """NormalizedReliefAppearance dataclass structure and field semantics."""

    @pytest.fixture
    def sample_record(self):
        ip = 6.0 + 1 / 3  # 6.1 innings
        return NormalizedReliefAppearance(
            game_id="TEST-001",
            game_date="2025-05-01",
            team="New York Yankees",
            opponent="Boston Red Sox",
            pitcher_id=700003,
            pitcher_name="Luke Weaver",
            appeared_order=3,
            starter_flag=False,
            opener_flag=False,
            reliever_flag=True,
            innings_pitched=ip,
            outs_recorded=_compute_outs_recorded(ip),
            pitches_thrown=22,
            source=SOURCE_LABEL,
            source_game_id="100001",
            audit_hash=_appearance_audit_hash("TEST-001", 700003, ip),
        )

    def test_is_frozen_dataclass(self, sample_record):
        assert dataclasses.is_dataclass(sample_record)
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
            sample_record.team = "Other Team"  # type: ignore[misc]

    def test_required_fields_present(self, sample_record):
        required = [
            "game_id", "game_date", "team", "opponent", "pitcher_id",
            "pitcher_name", "appeared_order", "starter_flag", "opener_flag",
            "reliever_flag", "innings_pitched", "outs_recorded", "pitches_thrown",
            "source", "source_game_id", "audit_hash",
        ]
        for field in required:
            assert hasattr(sample_record, field), f"Missing field: {field}"

    def test_outs_recorded_is_int(self, sample_record):
        assert isinstance(sample_record.outs_recorded, int)

    def test_outs_recorded_value_for_6_1_ip(self, sample_record):
        # 6.1 = 6 + 1/3 → 19 outs
        assert sample_record.outs_recorded == 19

    def test_source_is_boxscore_label(self, sample_record):
        assert sample_record.source == SOURCE_LABEL

    def test_audit_hash_is_12_char_string(self, sample_record):
        assert isinstance(sample_record.audit_hash, str)
        assert len(sample_record.audit_hash) == 12

    def test_reliever_flag_true_for_reliever(self, sample_record):
        assert sample_record.reliever_flag is True

    def test_starter_flag_false_for_reliever(self, sample_record):
        assert sample_record.starter_flag is False

    def test_opener_flag_false_for_normal_reliever(self, sample_record):
        assert sample_record.opener_flag is False

    def test_opener_flag_true_for_opener(self):
        ip = 1.0 + 1 / 3  # 1.1 innings < OPENER_IP_THRESHOLD
        rec = NormalizedReliefAppearance(
            game_id="TEST-OPENER",
            game_date="2025-05-04",
            team="Houston Astros",
            opponent="Tampa Bay Rays",
            pitcher_id=800001,
            pitcher_name="Ryan Pressly",
            appeared_order=1,
            starter_flag=False,
            opener_flag=True,
            reliever_flag=True,
            innings_pitched=ip,
            outs_recorded=_compute_outs_recorded(ip),
            pitches_thrown=22,
            source=SOURCE_LABEL,
            source_game_id="100004",
            audit_hash=_appearance_audit_hash("TEST-OPENER", 800001, ip),
        )
        assert rec.opener_flag is True
        assert rec.reliever_flag is True
        assert rec.starter_flag is False

    def test_pitches_thrown_can_be_none(self):
        ip = 1.0
        rec = NormalizedReliefAppearance(
            game_id="TEST-NP",
            game_date="2025-05-01",
            team="New York Yankees",
            opponent="Boston Red Sox",
            pitcher_id=999,
            pitcher_name="Unknown",
            appeared_order=2,
            starter_flag=False,
            opener_flag=False,
            reliever_flag=True,
            innings_pitched=ip,
            outs_recorded=3,
            pitches_thrown=None,
            source=SOURCE_LABEL,
            source_game_id="",
            audit_hash=_appearance_audit_hash("TEST-NP", 999, ip),
        )
        assert rec.pitches_thrown is None


# ===========================================================================
# 3. TestSSOTFeatureArtifactSchema
# ===========================================================================

class TestSSOTFeatureArtifactSchema:
    """SSOTFeatureArtifact dataclass structure, DATA_LIMITED enforcement."""

    @pytest.fixture
    def minimal_artifact(self):
        return SSOTFeatureArtifact(
            prediction_game_id="TEST-PRED-001",
            game_date="2025-05-05",
            team="New York Yankees",
            bullpen_usage_last_1d=None,
            bullpen_usage_last_3d=5.333,
            bullpen_usage_last_5d=8.333,
            reliever_back_to_back_count=0,
            reliever_three_in_four_days_count=1,
            closer_used_last_1d=False,
            closer_used_last_2d=True,
            high_leverage_reliever_used_last_1d=None,
            high_leverage_reliever_workload_last_3d=None,
            availability_map=build_availability_map(),
            pit_window_map=build_pit_window_map(),
            audit_hash="aabbccdd1234",
        )

    def test_is_dataclass(self, minimal_artifact):
        assert dataclasses.is_dataclass(minimal_artifact)

    def test_high_leverage_used_last_1d_is_none(self, minimal_artifact):
        assert minimal_artifact.high_leverage_reliever_used_last_1d is None

    def test_high_leverage_workload_last_3d_is_none(self, minimal_artifact):
        assert minimal_artifact.high_leverage_reliever_workload_last_3d is None

    def test_availability_map_has_12_features(self, minimal_artifact):
        assert len(minimal_artifact.availability_map) == 12

    def test_availability_map_high_leverage_is_data_limited(self, minimal_artifact):
        assert minimal_artifact.availability_map["high_leverage_reliever_used_last_1d"] == "DATA_LIMITED"
        assert minimal_artifact.availability_map["high_leverage_reliever_workload_last_3d"] == "DATA_LIMITED"

    def test_availability_map_usage_1d_is_available(self, minimal_artifact):
        assert minimal_artifact.availability_map["bullpen_usage_last_1d"] == "AVAILABLE"

    def test_availability_map_b2b_is_available(self, minimal_artifact):
        assert minimal_artifact.availability_map["reliever_back_to_back_count"] == "AVAILABLE"

    def test_pit_window_map_has_12_features(self, minimal_artifact):
        assert len(minimal_artifact.pit_window_map) == 12

    def test_pit_window_map_values(self, minimal_artifact):
        wm = minimal_artifact.pit_window_map
        assert wm["bullpen_usage_last_1d"] == 1
        assert wm["bullpen_usage_last_3d"] == 3
        assert wm["bullpen_usage_last_5d"] == 5
        assert wm["reliever_back_to_back_count"] == 2
        assert wm["reliever_three_in_four_days_count"] == 4

    def test_diagnostic_only_is_true(self, minimal_artifact):
        assert minimal_artifact.diagnostic_only is True

    def test_module_version_matches_phase63(self, minimal_artifact):
        assert minimal_artifact.module_version == PHASE63_MODULE_VERSION

    def test_data_limited_sentinel_in_availability_map(self, minimal_artifact):
        limited = [
            k for k, v in minimal_artifact.availability_map.items()
            if v == "DATA_LIMITED"
        ]
        assert len(limited) == 2


# ===========================================================================
# 4. TestOutsRecordedComputation
# ===========================================================================

class TestOutsRecordedComputation:
    """_compute_outs_recorded — float drift safety and correctness."""

    def test_zero_ip(self):
        assert _compute_outs_recorded(0.0) == 0

    def test_one_full_inning(self):
        assert _compute_outs_recorded(1.0) == 3

    def test_1_1_ip(self):
        # 1.1 = 1 + 1/3 ≈ 1.333 → 4 outs
        assert _compute_outs_recorded(1 + 1 / 3) == 4

    def test_1_2_ip(self):
        # 1.2 = 1 + 2/3 ≈ 1.667 → 5 outs
        assert _compute_outs_recorded(1 + 2 / 3) == 5

    def test_6_1_ip(self):
        # 6.1 = 6 + 1/3 ≈ 6.333 → 19 outs (tests float drift: 6.333*3=18.999...)
        assert _compute_outs_recorded(6 + 1 / 3) == 19

    def test_6_2_ip(self):
        # 6.2 = 6 + 2/3 ≈ 6.667 → 20 outs
        assert _compute_outs_recorded(6 + 2 / 3) == 20

    def test_9_0_ip(self):
        assert _compute_outs_recorded(9.0) == 27

    def test_result_is_int(self):
        result = _compute_outs_recorded(5 + 1 / 3)
        assert isinstance(result, int)


# ===========================================================================
# 5. TestParseBoxscoreToNormalizedAppearances
# ===========================================================================

class TestParseBoxscoreToNormalizedAppearances:
    """parse_boxscore_to_normalized_appearances — Phase 63 parser correctness."""

    @pytest.fixture
    def normal_game1_boxscore(self):
        return _make_minimal_boxscore(
            home_pitchers=[
                {"id": 700001, "name": "Gerrit Cole", "ip": "6.0", "pitches": 95},
                {"id": 700002, "name": "Clay Holmes", "ip": "2.0", "pitches": 28},
                {"id": 700003, "name": "Luke Weaver", "ip": "1.0", "pitches": 15},
            ],
            away_pitchers=[
                {"id": 700011, "name": "Brayan Bello", "ip": "5.1", "pitches": 88},
                {"id": 700012, "name": "Luis Garcia", "ip": "0.2", "pitches": 12},
                {"id": 700013, "name": "Greg Weissert", "ip": "1.0", "pitches": 14},
                {"id": 700014, "name": "Aroldis Chapman", "ip": "1.0", "pitches": 18},
            ],
        )

    def test_returns_list_of_normalized(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        assert isinstance(recs, list)
        assert all(isinstance(r, NormalizedReliefAppearance) for r in recs)

    def test_correct_total_count(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        # 3 home + 4 away = 7
        assert len(recs) == 7

    def test_opponent_set_correctly_home(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        home_recs = [r for r in recs if r.team == "New York Yankees"]
        assert all(r.opponent == "Boston Red Sox" for r in home_recs)

    def test_opponent_set_correctly_away(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        away_recs = [r for r in recs if r.team == "Boston Red Sox"]
        assert all(r.opponent == "New York Yankees" for r in away_recs)

    def test_starter_flag_true_for_sp(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        cole = next(r for r in recs if r.pitcher_id == 700001)
        assert cole.starter_flag is True
        assert cole.reliever_flag is False
        assert cole.opener_flag is False

    def test_reliever_flag_true_for_second_pitcher(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        holmes = next(r for r in recs if r.pitcher_id == 700002)
        assert holmes.reliever_flag is True
        assert holmes.starter_flag is False

    def test_appeared_order_sequential(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        home_orders = [r.appeared_order for r in recs if r.team == "New York Yankees"]
        assert sorted(home_orders) == [1, 2, 3]

    def test_innings_pitched_parsed_correctly_5_1(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        bello = next(r for r in recs if r.pitcher_id == 700011)
        assert abs(bello.innings_pitched - (5 + 1 / 3)) < 1e-9

    def test_outs_recorded_5_1_ip(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        bello = next(r for r in recs if r.pitcher_id == 700011)
        assert bello.outs_recorded == 16

    def test_pitches_thrown_extracted(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        cole = next(r for r in recs if r.pitcher_id == 700001)
        assert cole.pitches_thrown == 95

    def test_pitches_thrown_none_when_missing(self):
        bx = _make_minimal_boxscore(
            home_pitchers=[{"id": 1, "name": "P1", "ip": "6.0"}],  # no pitches key
            away_pitchers=[{"id": 2, "name": "P2", "ip": "3.0"}],
        )
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=bx, game_id="T", game_date="2025-05-01",
            home_team="H", away_team="A",
        )
        assert all(r.pitches_thrown is None for r in recs)

    def test_source_game_id_propagated(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
            source_game_id="100001",
        )
        assert all(r.source_game_id == "100001" for r in recs)

    def test_source_is_boxscore_label(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        assert all(r.source == SOURCE_LABEL for r in recs)

    def test_audit_hash_length(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        for r in recs:
            assert isinstance(r.audit_hash, str)
            assert len(r.audit_hash) == 12

    def test_null_boxscore_returns_empty(self):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=None,  # type: ignore[arg-type]
            game_id="TEST", game_date="2025-05-01",
            home_team="H", away_team="A",
        )
        assert recs == []

    def test_empty_boxscore_returns_empty(self):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore={},
            game_id="TEST", game_date="2025-05-01",
            home_team="H", away_team="A",
        )
        assert recs == []

    def test_pitcher_name_extracted(self, normal_game1_boxscore):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=normal_game1_boxscore,
            game_id="TEST-G1",
            game_date="2025-05-01",
            home_team="New York Yankees",
            away_team="Boston Red Sox",
        )
        weaver = next(r for r in recs if r.pitcher_id == 700003)
        assert weaver.pitcher_name == "Luke Weaver"


# ===========================================================================
# 6. TestEdgeCasePolicies
# ===========================================================================

class TestEdgeCasePolicies:
    """Doubleheader / postponed / suspended / opener / bulk pitcher handling."""

    def test_doubleheader_d0_excluded_by_strict_lt(self):
        """
        Doubleheader: if Game 1 is on same prediction_date, it is excluded
        because game_date < prediction_date is STRICT (not <=).
        """
        appearances = [
            _make_appearance("2025-05-05", "Team A", 1, 2.0, is_reliever=True),
        ]
        # Prediction is also 2025-05-05 (same day = D-0); must be excluded
        result = compute_bullpen_ip_window(
            appearances, team="Team A", prediction_date="2025-05-05", window_days=1
        )
        assert result is None  # D-0 data excluded

    def test_doubleheader_only_prior_day_included(self):
        """D-1 data is included; same-day D-0 is not."""
        appearances = [
            _make_appearance("2025-05-04", "Team A", 1, 2.0, is_reliever=True),  # D-1
            _make_appearance("2025-05-05", "Team A", 2, 3.0, is_reliever=True),  # D-0 (same day)
        ]
        result = compute_bullpen_ip_window(
            appearances, team="Team A", prediction_date="2025-05-05", window_days=1
        )
        # Only D-1 (2.0 IP) should be included
        assert result == 2.0

    def test_postponed_null_boxscore_yields_zero_appearances(self):
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=None,  # type: ignore[arg-type]
            game_id="POSTPONED", game_date="2025-05-01",
            home_team="H", away_team="A",
        )
        assert len(recs) == 0

    def test_postponed_increments_games_missing(self):
        _, result = parse_fixture_to_phase63_ingestion(FIXTURE_PATH)
        assert result.games_missing >= 1

    def test_suspended_treated_as_null_boxscore(self):
        # Suspended game = null boxscore in our policy
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=None,  # type: ignore[arg-type]
            game_id="SUSPENDED", game_date="2025-05-01",
            home_team="H", away_team="A",
        )
        assert recs == []

    def test_opener_flag_true_when_ip_below_threshold(self):
        bx = _make_minimal_boxscore(
            home_pitchers=[
                {"id": 800001, "name": "Ryan Pressly", "ip": "1.1", "pitches": 22},
                {"id": 800002, "name": "Hunter Brown", "ip": "4.2", "pitches": 72},
            ],
            away_pitchers=[{"id": 900001, "name": "SP", "ip": "7.0"}],
        )
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=bx, game_id="OPG", game_date="2025-05-04",
            home_team="Houston Astros", away_team="Tampa Bay Rays",
        )
        pressly = next(r for r in recs if r.pitcher_id == 800001)
        assert pressly.opener_flag is True
        assert pressly.reliever_flag is True

    def test_opener_counted_in_bullpen_ip(self):
        """Opener is reliever_flag=True → contributes to bullpen IP window."""
        appearances = [
            _make_appearance("2025-05-04", "Houston Astros", 800001, 1 + 1 / 3, is_reliever=True),
        ]
        result = compute_bullpen_ip_window(
            appearances, team="Houston Astros", prediction_date="2025-05-05", window_days=1
        )
        assert result is not None
        assert abs(result - (1 + 1 / 3)) < 0.01

    def test_bulk_pitcher_reliever_flag_true(self):
        bx = _make_minimal_boxscore(
            home_pitchers=[
                {"id": 800001, "name": "Opener", "ip": "1.0"},
                {"id": 800002, "name": "Hunter Brown (Bulk)", "ip": "4.2"},
            ],
            away_pitchers=[{"id": 900001, "name": "SP", "ip": "7.0"}],
        )
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=bx, game_id="BULK", game_date="2025-05-04",
            home_team="H", away_team="A",
        )
        bulk = next(r for r in recs if r.pitcher_id == 800002)
        assert bulk.reliever_flag is True
        assert bulk.starter_flag is False
        assert bulk.opener_flag is False

    def test_bulk_pitcher_counted_in_bullpen_ip(self):
        appearances = [
            _make_appearance("2025-05-04", "H", 800002, 4 + 2 / 3, is_reliever=True),
        ]
        result = compute_bullpen_ip_window(
            appearances, team="H", prediction_date="2025-05-05", window_days=1
        )
        assert result is not None
        assert abs(result - (4 + 2 / 3)) < 0.01

    def test_opener_appears_at_order_1(self):
        bx = _make_minimal_boxscore(
            home_pitchers=[
                {"id": 800001, "name": "Opener", "ip": "1.1"},
                {"id": 800002, "name": "Bulk", "ip": "5.0"},
            ],
            away_pitchers=[{"id": 900001, "name": "SP", "ip": "7.0"}],
        )
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=bx, game_id="T", game_date="2025-05-01", home_team="H", away_team="A",
        )
        opener = next(r for r in recs if r.pitcher_id == 800001)
        assert opener.appeared_order == 1

    def test_bulk_pitcher_appears_at_order_2(self):
        bx = _make_minimal_boxscore(
            home_pitchers=[
                {"id": 800001, "name": "Opener", "ip": "1.1"},
                {"id": 800002, "name": "Bulk", "ip": "5.0"},
            ],
            away_pitchers=[{"id": 900001, "name": "SP", "ip": "7.0"}],
        )
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=bx, game_id="T", game_date="2025-05-01", home_team="H", away_team="A",
        )
        bulk = next(r for r in recs if r.pitcher_id == 800002)
        assert bulk.appeared_order == 2

    def test_starter_ip_above_threshold_has_starter_flag(self):
        bx = _make_minimal_boxscore(
            home_pitchers=[
                {"id": 1, "name": "SP", "ip": "6.0"},
                {"id": 2, "name": "RP", "ip": "1.0"},
            ],
            away_pitchers=[{"id": 3, "name": "SP2", "ip": "7.0"}],
        )
        recs = parse_boxscore_to_normalized_appearances(
            boxscore=bx, game_id="T", game_date="2025-05-01", home_team="H", away_team="A",
        )
        sp = next(r for r in recs if r.pitcher_id == 1)
        assert sp.starter_flag is True
        assert sp.opener_flag is False


# ===========================================================================
# 7. TestComputeSSOTFeatureArtifact
# ===========================================================================

class TestComputeSSOTFeatureArtifact:
    """compute_ssot_feature_artifact — all window computations via fixture."""

    @pytest.fixture(scope="class")
    def fixture_appearances(self):
        result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        return result.appearances

    @pytest.fixture(scope="class")
    def nyyartifact(self, fixture_appearances):
        return compute_ssot_feature_artifact(
            fixture_appearances,
            prediction_game_id="TEST-PRED-NYY-20250505",
            game_date="2025-05-05",
            team="New York Yankees",
        )

    @pytest.fixture(scope="class")
    def bosartifact(self, fixture_appearances):
        return compute_ssot_feature_artifact(
            fixture_appearances,
            prediction_game_id="TEST-PRED-BOS-20250505",
            game_date="2025-05-05",
            team="Boston Red Sox",
        )

    def test_returns_ssot_feature_artifact(self, nyyartifact):
        assert isinstance(nyyartifact, SSOTFeatureArtifact)

    def test_high_leverage_used_last_1d_is_none(self, nyyartifact):
        assert nyyartifact.high_leverage_reliever_used_last_1d is None

    def test_high_leverage_workload_last_3d_is_none(self, nyyartifact):
        assert nyyartifact.high_leverage_reliever_workload_last_3d is None

    def test_bullpen_usage_1d_none_when_no_d1_game(self, nyyartifact):
        # NYY last game was May 3; D-1 from May 5 = May 4 (no NYY game)
        assert nyyartifact.bullpen_usage_last_1d is None

    def test_bullpen_usage_3d_positive(self, nyyartifact):
        # May 2 (Holmes 1.0 + Weaver 1.0) + May 3 (Kahnle 1.333 + Weaver 2.0) = 5.333
        assert nyyartifact.bullpen_usage_last_3d is not None
        assert nyyartifact.bullpen_usage_last_3d > 0.0

    def test_bullpen_usage_5d_covers_may1_to_may4(self, nyyartifact):
        # 5d window from May 5: May 1-4 → includes all 3 NYY games
        assert nyyartifact.bullpen_usage_last_5d is not None
        assert nyyartifact.bullpen_usage_last_5d > nyyartifact.bullpen_usage_last_3d

    def test_b2b_count_zero_when_no_d1_game(self, nyyartifact):
        # No NYY game on May 4 → no D-1 appearances → B2B = 0
        assert nyyartifact.reliever_back_to_back_count == 0

    def test_three_in_four_detects_weaver(self, nyyartifact):
        # Weaver pitched May 1, 2, 3 (3 days in the D-1..D-4 = May 1-4 window)
        assert nyyartifact.reliever_three_in_four_days_count >= 1

    def test_closer_used_last_1d_false_no_d1_game(self, nyyartifact):
        # No NYY game May 4 → closer not used in D-1
        assert nyyartifact.closer_used_last_1d is False

    def test_closer_used_last_2d_true_may3_game(self, nyyartifact):
        # Weaver closed May 3 (is_closer_candidate) → within D-1 to D-2 of May 5
        assert nyyartifact.closer_used_last_2d is True

    def test_availability_map_populated(self, nyyartifact):
        assert isinstance(nyyartifact.availability_map, dict)
        assert len(nyyartifact.availability_map) == 12

    def test_pit_window_map_populated(self, nyyartifact):
        assert isinstance(nyyartifact.pit_window_map, dict)
        assert len(nyyartifact.pit_window_map) == 12

    def test_diagnostic_only_true(self, nyyartifact):
        assert nyyartifact.diagnostic_only is True

    def test_module_version_phase63(self, nyyartifact):
        assert nyyartifact.module_version == PHASE63_MODULE_VERSION

    def test_audit_hash_non_empty(self, nyyartifact):
        assert isinstance(nyyartifact.audit_hash, str)
        assert len(nyyartifact.audit_hash) == 12

    def test_pit_safety_excludes_same_day(self, fixture_appearances):
        # Compute features for May 1 (same as first game) → should exclude May 1 data
        # (strict <)
        artifact = compute_ssot_feature_artifact(
            fixture_appearances,
            prediction_game_id="TEST-PITCHECK",
            game_date="2025-05-01",
            team="New York Yankees",
        )
        # No prior data before May 1 for NYY → all None
        assert artifact.bullpen_usage_last_1d is None

    def test_bos_usage_3d_positive(self, bosartifact):
        assert bosartifact.bullpen_usage_last_3d is not None
        assert bosartifact.bullpen_usage_last_3d > 0.0

    def test_artifacts_differ_between_teams(self, nyyartifact, bosartifact):
        # Different teams → different audit hashes
        assert nyyartifact.audit_hash != bosartifact.audit_hash


# ===========================================================================
# 8. TestParseFixtureToPhase63Ingestion
# ===========================================================================

class TestParseFixtureToPhase63Ingestion:
    """parse_fixture_to_phase63_ingestion — combined normalized + IngestionResult."""

    @pytest.fixture(scope="class")
    def parsed(self):
        return parse_fixture_to_phase63_ingestion(FIXTURE_PATH)

    def test_returns_tuple(self, parsed):
        assert isinstance(parsed, tuple)
        assert len(parsed) == 2

    def test_first_element_is_list_of_normalized(self, parsed):
        normalized, _ = parsed
        assert isinstance(normalized, list)
        assert all(isinstance(r, NormalizedReliefAppearance) for r in normalized)

    def test_second_element_is_ingestion_result(self, parsed):
        _, result = parsed
        assert isinstance(result, IngestionResult)

    def test_normalized_count_matches_ingestion_result(self, parsed):
        normalized, result = parsed
        # Both should have same total pitcher appearances
        assert len(normalized) == len(result.appearances)

    def test_games_parsed_equals_4(self, parsed):
        _, result = parsed
        assert result.games_parsed == 4

    def test_games_missing_equals_1(self, parsed):
        _, result = parsed
        assert result.games_missing == 1

    def test_no_errors_in_parse(self, parsed):
        _, result = parsed
        assert result.errors == []

    def test_opponent_map_derivable(self, parsed):
        normalized, result = parsed
        opp_map = _build_opponent_map_from_appearances(result.appearances)
        # Every NYY appearance should have BOS as opponent
        nyyg1_id = "MLB-20250501-1_05_PM-BOSTON_RED_SOX-AT-NEW_YORK_YANKEES"
        if nyyg1_id in opp_map:
            assert opp_map[nyyg1_id].get("New York Yankees") == "Boston Red Sox"

    def test_all_normalized_have_audit_hash(self, parsed):
        normalized, _ = parsed
        assert all(len(r.audit_hash) == 12 for r in normalized)

    def test_pitches_thrown_extracted_from_fixture(self, parsed):
        normalized, _ = parsed
        # The fixture includes numberOfPitches for all pitchers → at least one non-None
        pitches = [r.pitches_thrown for r in normalized if r.pitches_thrown is not None]
        assert len(pitches) > 0

    def test_opener_detected_in_fixture(self, parsed):
        normalized, _ = parsed
        openers = [r for r in normalized if r.opener_flag]
        # OPENER_GAME has Pressly at 1.1 IP → opener
        assert len(openers) >= 1


# ===========================================================================
# 9. TestPhase63DiagnosticReport
# ===========================================================================

class TestPhase63DiagnosticReport:
    """build_phase63_diagnostic_report — structure, gate decision, artifact metadata."""

    @pytest.fixture(scope="class")
    def report_data(self):
        normalized, result = parse_fixture_to_phase63_ingestion(FIXTURE_PATH)
        artifacts = [
            compute_ssot_feature_artifact(
                result.appearances,
                prediction_game_id="TEST-PRED-NYY-20250505",
                game_date="2025-05-05",
                team="New York Yankees",
            ),
            compute_ssot_feature_artifact(
                result.appearances,
                prediction_game_id="TEST-PRED-BOS-20250505",
                game_date="2025-05-05",
                team="Boston Red Sox",
            ),
        ]
        return build_phase63_diagnostic_report(normalized, artifacts, result)

    def test_report_is_dict(self, report_data):
        assert isinstance(report_data, dict)

    def test_phase63_gate_present(self, report_data):
        assert "phase63_gate" in report_data

    def test_gate_is_granular_ingestion_ready(self, report_data):
        assert report_data["phase63_gate"] == "GRANULAR_INGESTION_READY"

    def test_phase62_gate_preserved(self, report_data):
        assert report_data["phase62_gate"] == GATE_RESULT  # "STATSAPI_SELECTED"

    def test_production_modified_false(self, report_data):
        assert report_data["production_modified"] is False

    def test_candidate_patch_created_false(self, report_data):
        assert report_data["candidate_patch_created"] is False

    def test_alpha_modified_false(self, report_data):
        assert report_data["alpha_modified"] is False

    def test_ingestion_summary_present(self, report_data):
        assert "ingestion_summary" in report_data
        summary = report_data["ingestion_summary"]
        assert summary["games_parsed"] == 4
        assert summary["games_missing"] == 1

    def test_ssot_artifact_summary_present(self, report_data):
        assert "ssot_artifact_summary" in report_data
        assert report_data["ssot_artifact_summary"]["total_artifacts"] == 2

    def test_data_limited_confirmed_in_report(self, report_data):
        assert report_data["ssot_artifact_summary"]["data_limited_confirmed"] is True

    def test_ssot_feature_status_10_available(self, report_data):
        status = report_data["ssot_feature_status"]
        assert status["available_count"] == 10

    def test_ssot_feature_status_2_data_limited(self, report_data):
        status = report_data["ssot_feature_status"]
        assert status["data_limited_count"] == 2

    def test_edge_case_policies_in_report(self, report_data):
        assert "edge_case_policies" in report_data
        policies = report_data["edge_case_policies"]
        assert "doubleheader" in policies
        assert "postponed" in policies

    def test_phase64_ready_true(self, report_data):
        assert report_data["phase64_ready"] is True

    def test_phase64_guidance_present(self, report_data):
        assert isinstance(report_data.get("phase64_guidance"), str)
        assert len(report_data["phase64_guidance"]) > 0

    def test_audit_hash_16_chars(self, report_data):
        assert isinstance(report_data["audit_hash"], str)
        assert len(report_data["audit_hash"]) == 16

    def test_module_version_phase63(self, report_data):
        assert report_data["module_version"] == PHASE63_MODULE_VERSION

    def test_data_quality_blocked_when_errors(self):
        normalized: list[NormalizedReliefAppearance] = []
        bad_result = IngestionResult(
            appearances=[],
            games_parsed=0,
            games_missing=0,
            errors=["game_X: connection refused"],
        )
        report = build_phase63_diagnostic_report(normalized, [], bad_result)
        assert report["phase63_gate"] == "DATA_QUALITY_BLOCKED"

    def test_source_integration_blocked_when_no_normalized(self):
        empty_result = IngestionResult(
            appearances=[], games_parsed=0, games_missing=0, errors=[]
        )
        report = build_phase63_diagnostic_report([], [], empty_result)
        assert report["phase63_gate"] == "SOURCE_INTEGRATION_BLOCKED"

    def test_diagnostic_artifact_only_when_no_ssot_artifacts(self):
        # Has appearances but no ssot_artifacts
        normalized = [
            NormalizedReliefAppearance(
                game_id="G1", game_date="2025-05-01", team="H", opponent="A",
                pitcher_id=1, pitcher_name="P", appeared_order=1,
                starter_flag=True, opener_flag=False, reliever_flag=False,
                innings_pitched=6.0, outs_recorded=18, pitches_thrown=None,
                source=SOURCE_LABEL, source_game_id="G1", audit_hash="aabbccdd1234",
            )
        ]
        ok_result = IngestionResult(appearances=[], games_parsed=1, games_missing=0, errors=[])
        report = build_phase63_diagnostic_report(normalized, [], ok_result)
        assert report["phase63_gate"] == "DIAGNOSTIC_ARTIFACT_ONLY"


# ===========================================================================
# 10. TestBuildAvailabilityAndPITWindowMaps
# ===========================================================================

class TestBuildAvailabilityAndPITWindowMaps:
    """build_availability_map and build_pit_window_map correctness."""

    def test_availability_map_has_exactly_12_keys(self):
        m = build_availability_map()
        assert len(m) == 12

    def test_availability_map_10_available(self):
        m = build_availability_map()
        available = [k for k, v in m.items() if v == "AVAILABLE"]
        assert len(available) == 10

    def test_availability_map_2_data_limited(self):
        m = build_availability_map()
        limited = [k for k, v in m.items() if v == "DATA_LIMITED"]
        assert len(limited) == 2

    def test_availability_map_data_limited_are_high_leverage(self):
        m = build_availability_map()
        limited = [k for k, v in m.items() if v == "DATA_LIMITED"]
        assert "high_leverage_reliever_used_last_1d" in limited
        assert "high_leverage_reliever_workload_last_3d" in limited

    def test_pit_window_map_has_exactly_12_keys(self):
        m = build_pit_window_map()
        assert len(m) == 12

    def test_pit_window_1d(self):
        m = build_pit_window_map()
        assert m["bullpen_usage_last_1d"] == 1

    def test_pit_window_3d(self):
        m = build_pit_window_map()
        assert m["bullpen_usage_last_3d"] == 3

    def test_pit_window_5d(self):
        m = build_pit_window_map()
        assert m["bullpen_usage_last_5d"] == 5

    def test_pit_window_b2b(self):
        m = build_pit_window_map()
        assert m["reliever_back_to_back_count"] == 2

    def test_pit_window_3_in_4(self):
        m = build_pit_window_map()
        assert m["reliever_three_in_four_days_count"] == 4


# ===========================================================================
# 11. TestPhase62BackwardCompatibility
# ===========================================================================

class TestPhase62BackwardCompatibility:
    """Ensure Phase 63 additions do not break Phase 62 contracts."""

    def test_module_version_unchanged(self):
        assert MODULE_VERSION == "phase62_bullpen_granular_ingestion_v1"

    def test_gate_result_unchanged(self):
        assert GATE_RESULT == "STATSAPI_SELECTED"

    def test_selected_source_unchanged(self):
        assert SELECTED_SOURCE == "mlb_stats_api_boxscore"

    def test_parse_fixture_to_ingestion_result_still_works(self):
        result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        assert result.games_parsed == 4
        assert result.games_missing == 1
        assert len(result.appearances) > 0

    def test_build_phase62_diagnostic_report_still_works(self):
        result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        report = build_phase62_diagnostic_report(result)
        assert report["gate"] == "STATSAPI_SELECTED"
        assert isinstance(report["audit_hash"], str)

    def test_phase62_appearances_are_relief_appearance_record(self):
        result = parse_fixture_to_ingestion_result(FIXTURE_PATH)
        assert all(isinstance(a, ReliefAppearanceRecord) for a in result.appearances)

    def test_ssot_available_features_count_unchanged(self):
        assert len(ssot_available_features_from_boxscore()) == 10

    def test_ssot_data_limited_features_count_unchanged(self):
        assert len(ssot_still_data_limited_features()) == 2
