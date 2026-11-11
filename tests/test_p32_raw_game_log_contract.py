"""
Tests for P32 Raw Game Log Contract.

Coverage:
- contract rejects production_ready=True
- contract rejects paper_only=False
- contract rejects season != 2024
- gate constants are valid
- build summary rejects odds/predictions
- gate result to_dict is serializable
"""
from __future__ import annotations

import json
import pytest

from wbc_backend.recommendation.p32_raw_game_log_contract import (
    PAPER_ONLY,
    PRODUCTION_READY,
    VALID_P32_GATES,
    P32RawGameLogSource,
    P32GameIdentityRecord,
    P32GameOutcomeRecord,
    P32RawGameLogBuildSummary,
    P32RawGameLogGateResult,
    P32_RAW_GAME_LOG_ARTIFACT_READY,
    P32_BLOCKED_SOURCE_FILE_MISSING,
    P32_BLOCKED_SCHEMA_INVALID,
    P32_BLOCKED_NO_2024_GAMES,
    P32_BLOCKED_PROVENANCE_UNSAFE,
    P32_FAIL_INPUT_MISSING,
    P32_FAIL_NON_DETERMINISTIC,
    P32_BLOCKED_CONTRACT_VIOLATION,
)


# ---------------------------------------------------------------------------
# Safety constants
# ---------------------------------------------------------------------------

class TestSafetyConstants:
    def test_paper_only_true(self) -> None:
        assert PAPER_ONLY is True

    def test_production_ready_false(self) -> None:
        assert PRODUCTION_READY is False

    def test_all_gates_in_valid_set(self) -> None:
        for gate in [
            P32_RAW_GAME_LOG_ARTIFACT_READY,
            P32_BLOCKED_SOURCE_FILE_MISSING,
            P32_BLOCKED_SCHEMA_INVALID,
            P32_BLOCKED_NO_2024_GAMES,
            P32_BLOCKED_PROVENANCE_UNSAFE,
            P32_FAIL_INPUT_MISSING,
            P32_FAIL_NON_DETERMINISTIC,
            P32_BLOCKED_CONTRACT_VIOLATION,
        ]:
            assert gate in VALID_P32_GATES


# ---------------------------------------------------------------------------
# P32RawGameLogSource
# ---------------------------------------------------------------------------

class TestP32RawGameLogSource:
    def _valid(self, **kwargs) -> P32RawGameLogSource:
        defaults = dict(
            season=2024,
            source_name="Retrosheet",
            source_path="/data/gl2024.txt",
            provenance_status="VERIFIED",
            license_status="ATTRIBUTION_REQUIRED",
            attribution_required=True,
            paper_only=True,
            production_ready=False,
        )
        defaults.update(kwargs)
        return P32RawGameLogSource(**defaults)

    def test_valid_source_builds(self) -> None:
        src = self._valid()
        assert src.season == 2024
        assert src.paper_only is True
        assert src.production_ready is False

    def test_rejects_production_ready_true(self) -> None:
        with pytest.raises(ValueError, match="production_ready"):
            self._valid(production_ready=True)

    def test_rejects_paper_only_false(self) -> None:
        with pytest.raises(ValueError, match="paper_only"):
            self._valid(paper_only=False)

    def test_rejects_season_not_2024(self) -> None:
        with pytest.raises(ValueError, match="2024"):
            self._valid(season=2025)


# ---------------------------------------------------------------------------
# P32GameIdentityRecord
# ---------------------------------------------------------------------------

class TestP32GameIdentityRecord:
    def _valid(self, **kwargs) -> P32GameIdentityRecord:
        defaults = dict(
            game_id="NYY-20240401-0",
            game_date="2024-04-01",
            season=2024,
            away_team="BOS",
            home_team="NYY",
            source_name="Retrosheet",
            source_row_number=1,
            paper_only=True,
            production_ready=False,
        )
        defaults.update(kwargs)
        return P32GameIdentityRecord(**defaults)

    def test_valid_record_builds(self) -> None:
        r = self._valid()
        assert r.game_id == "NYY-20240401-0"
        assert r.paper_only is True

    def test_rejects_production_ready_true(self) -> None:
        with pytest.raises(ValueError, match="production_ready"):
            self._valid(production_ready=True)

    def test_rejects_paper_only_false(self) -> None:
        with pytest.raises(ValueError, match="paper_only"):
            self._valid(paper_only=False)

    def test_empty_game_id_is_a_string(self) -> None:
        # P32GameIdentityRecord doesn't validate empty strings at contract level
        # The parser is responsible for not emitting empty game_ids
        r = self._valid(game_id="")
        assert r.game_id == ""

    def test_season_matches_source(self) -> None:
        r = self._valid(season=2024)
        assert r.season == 2024


# ---------------------------------------------------------------------------
# P32GameOutcomeRecord
# ---------------------------------------------------------------------------

class TestP32GameOutcomeRecord:
    def _valid(self, **kwargs) -> P32GameOutcomeRecord:
        defaults = dict(
            game_id="NYY-20240401-0",
            game_date="2024-04-01",
            season=2024,
            away_team="BOS",
            home_team="NYY",
            away_score=3,
            home_score=5,
            y_true_home_win=1,
            source_name="Retrosheet",
            source_row_number=1,
            paper_only=True,
            production_ready=False,
        )
        defaults.update(kwargs)
        return P32GameOutcomeRecord(**defaults)

    def test_valid_record(self) -> None:
        r = self._valid()
        assert r.y_true_home_win == 1
        assert r.production_ready is False

    def test_rejects_production_ready_true(self) -> None:
        with pytest.raises(ValueError, match="production_ready"):
            self._valid(production_ready=True)

    def test_rejects_paper_only_false(self) -> None:
        with pytest.raises(ValueError, match="paper_only"):
            self._valid(paper_only=False)

    def test_rejects_inconsistent_y_true(self) -> None:
        """home_score=3 < away_score=5 but y_true_home_win=1 is wrong."""
        with pytest.raises(ValueError, match="inconsistent"):
            self._valid(away_score=5, home_score=3, y_true_home_win=1)

    def test_allows_none_scores(self) -> None:
        r = self._valid(away_score=None, home_score=None, y_true_home_win=None)
        assert r.y_true_home_win is None

    def test_away_win(self) -> None:
        r = self._valid(away_score=5, home_score=3, y_true_home_win=0)
        assert r.y_true_home_win == 0


# ---------------------------------------------------------------------------
# P32RawGameLogBuildSummary
# ---------------------------------------------------------------------------

class TestP32RawGameLogBuildSummary:
    def _valid(self, **kwargs) -> P32RawGameLogBuildSummary:
        defaults = dict(
            season=2024,
            source_name="Retrosheet",
            source_path="/data/gl2024.txt",
            row_count_raw=2430,
            row_count_processed=2415,
            unique_game_id_count=2415,
            date_start="2024-03-20",
            date_end="2024-10-01",
            teams_detected_count=30,
            outcome_coverage_pct=0.99,
            schema_valid=True,
            blocker="",
            paper_only=True,
            production_ready=False,
            contains_odds=False,
            contains_predictions=False,
        )
        defaults.update(kwargs)
        return P32RawGameLogBuildSummary(**defaults)

    def test_valid_summary(self) -> None:
        s = self._valid()
        assert s.contains_odds is False
        assert s.contains_predictions is False

    def test_rejects_production_ready_true(self) -> None:
        with pytest.raises(ValueError, match="production_ready"):
            self._valid(production_ready=True)

    def test_rejects_paper_only_false(self) -> None:
        with pytest.raises(ValueError, match="paper_only"):
            self._valid(paper_only=False)

    def test_rejects_contains_odds_true(self) -> None:
        with pytest.raises(ValueError, match="odds"):
            self._valid(contains_odds=True)

    def test_rejects_contains_predictions_true(self) -> None:
        with pytest.raises(ValueError, match="predictions"):
            self._valid(contains_predictions=True)


# ---------------------------------------------------------------------------
# P32RawGameLogGateResult
# ---------------------------------------------------------------------------

class TestP32RawGameLogGateResult:
    def _valid(self, **kwargs) -> P32RawGameLogGateResult:
        defaults = dict(
            gate=P32_RAW_GAME_LOG_ARTIFACT_READY,
            season=2024,
            source_path="/data/gl2024.txt",
            row_count_raw=2430,
            row_count_processed=2415,
            unique_game_id_count=2415,
            date_start="2024-03-20",
            date_end="2024-10-01",
            outcome_coverage_pct=0.99,
            provenance_status="VERIFIED",
            license_status="ATTRIBUTION_REQUIRED",
            paper_only=True,
            production_ready=False,
        )
        defaults.update(kwargs)
        return P32RawGameLogGateResult(**defaults)

    def test_valid_gate_result(self) -> None:
        gr = self._valid()
        assert gr.gate == P32_RAW_GAME_LOG_ARTIFACT_READY
        assert gr.production_ready is False

    def test_rejects_invalid_gate(self) -> None:
        with pytest.raises(ValueError, match="Invalid P32 gate"):
            self._valid(gate="SOME_MADE_UP_GATE")

    def test_rejects_production_ready_true(self) -> None:
        with pytest.raises(ValueError, match="production_ready"):
            self._valid(production_ready=True)

    def test_to_dict_is_json_serializable(self) -> None:
        gr = self._valid()
        d = gr.to_dict()
        # Should not raise
        serialized = json.dumps(d)
        loaded = json.loads(serialized)
        assert loaded["gate"] == P32_RAW_GAME_LOG_ARTIFACT_READY
        assert loaded["production_ready"] is False
        assert loaded["paper_only"] is True

    def test_blocked_gate_valid(self) -> None:
        gr = self._valid(
            gate=P32_BLOCKED_SOURCE_FILE_MISSING,
            blocker_reason="File not found",
        )
        assert gr.gate == P32_BLOCKED_SOURCE_FILE_MISSING
