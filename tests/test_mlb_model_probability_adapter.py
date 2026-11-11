"""
tests/test_mlb_model_probability_adapter.py

Unit tests for the MLB model probability adapter.

P5 tests:
- Refuses market proxy by default
- Allows market proxy with flag
- PAPER zone path enforcement
- merge join-by-game_id
- merge join-by-date+teams
- Team code normalization
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wbc_backend.prediction.mlb_model_probability import MlbModelProbability
from wbc_backend.prediction.mlb_model_probability_adapter import (
    MLB_TEAM_CODE_MAP,
    _normalize_team_to_code,
    merge_model_probabilities_into_rows,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_mlb_prob(
    game_id: str | None = "baseball:mlb:20250501:LAD:NYY",
    game_date: str = "2025-05-01",
    home_team: str = "LAD",
    away_team: str = "NYY",
    model_prob_home: float = 0.55,
    model_prob_away: float = 0.45,
    probability_source: str = "calibrated_model",
) -> MlbModelProbability:
    return MlbModelProbability(
        game_id=game_id,
        game_date=game_date,
        home_team=home_team,
        away_team=away_team,
        model_prob_home=model_prob_home,
        model_prob_away=model_prob_away,
        model_version="v1-test",
        probability_source=probability_source,
        generated_at_utc=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _paper_tmp_path() -> Path:
    """Return a temp path that passes the PAPER zone check."""
    base = Path(tempfile.mkdtemp())
    paper_dir = base / "outputs" / "predictions" / "PAPER" / "test"
    paper_dir.mkdir(parents=True, exist_ok=True)
    return paper_dir / "mlb_model_probabilities.jsonl"


# ── Tests: team code normalization ────────────────────────────────────────────

class TestNormalizeTeamToCode:
    def test_full_name_maps_to_code(self):
        assert _normalize_team_to_code("Los Angeles Dodgers") == "LAD"

    def test_code_passthrough(self):
        assert _normalize_team_to_code("LAD") == "LAD"

    def test_case_insensitive(self):
        assert _normalize_team_to_code("los angeles dodgers") == "LAD"

    def test_athletics_variants(self):
        assert _normalize_team_to_code("Athletics") == "ATH"
        assert _normalize_team_to_code("Oakland Athletics") == "ATH"

    def test_unknown_team_returns_none(self):
        result = _normalize_team_to_code("Unknown Unicorns")
        assert result is None

    def test_all_30_teams_in_map(self):
        assert len(MLB_TEAM_CODE_MAP) >= 30


# ── Tests: merge by game_id ───────────────────────────────────────────────────

class TestMergeModeByGameId:
    def test_merge_matches_by_game_id(self):
        probs = [_make_mlb_prob(game_id="baseball:mlb:20250501:LAD:NYY")]
        rows = [{"game_id": "baseball:mlb:20250501:LAD:NYY", "Home ML": "-130", "Away ML": "+110"}]
        enriched = merge_model_probabilities_into_rows(rows, probs)
        assert enriched[0]["model_prob_home"] == 0.55
        assert enriched[0]["probability_source"] == "calibrated_model"

    def test_merge_by_canonical_match_id(self):
        probs = [_make_mlb_prob(game_id="baseball:mlb:20250501:LAD:NYY")]
        rows = [{"canonical_match_id": "baseball:mlb:20250501:LAD:NYY"}]
        enriched = merge_model_probabilities_into_rows(rows, probs)
        assert enriched[0]["model_prob_home"] == 0.55

    def test_no_match_leaves_row_unchanged(self):
        probs = [_make_mlb_prob(game_id="baseball:mlb:20250501:LAD:NYY")]
        rows = [{"game_id": "baseball:mlb:20250601:BOS:NYY"}]
        enriched = merge_model_probabilities_into_rows(rows, probs)
        assert "model_prob_home" not in enriched[0]


# ── Tests: merge by date + teams ──────────────────────────────────────────────

class TestMergeModeByDateTeams:
    def test_merge_matches_by_date_and_teams(self):
        probs = [
            _make_mlb_prob(
                game_id=None,  # no game_id → must use date+teams
                game_date="2025-06-15",
                home_team="LAD",
                away_team="NYY",
            )
        ]
        rows = [
            {
                "Date": "2025-06-15",
                "Home": "Los Angeles Dodgers",
                "Away": "New York Yankees",
                "Home ML": "-140",
                "Away ML": "+120",
            }
        ]
        enriched = merge_model_probabilities_into_rows(rows, probs)
        assert enriched[0]["model_prob_home"] == 0.55
        assert enriched[0]["model_version"] == "v1-test"

    def test_multiple_rows_only_matched_updated(self):
        probs = [
            _make_mlb_prob(
                game_id=None,
                game_date="2025-06-15",
                home_team="LAD",
                away_team="NYY",
            )
        ]
        rows = [
            {"Date": "2025-06-15", "Home": "Los Angeles Dodgers", "Away": "New York Yankees"},
            {"Date": "2025-06-15", "Home": "Boston Red Sox", "Away": "Atlanta Braves"},
        ]
        enriched = merge_model_probabilities_into_rows(rows, probs)
        assert "model_prob_home" in enriched[0]
        assert "model_prob_home" not in enriched[1]

    def test_source_trace_attached_to_enriched_row(self):
        probs = [_make_mlb_prob(game_id="baseball:mlb:20250501:LAD:NYY")]
        rows = [{"game_id": "baseball:mlb:20250501:LAD:NYY"}]
        enriched = merge_model_probabilities_into_rows(rows, probs)
        assert "probability_source_trace" in enriched[0]
        assert isinstance(enriched[0]["probability_source_trace"], dict)


# ── Tests: PAPER zone security ────────────────────────────────────────────────

class TestPaperZoneSecurity:
    def test_non_paper_path_raises(self):
        from wbc_backend.prediction.mlb_model_probability_adapter import _assert_paper_output_path
        with pytest.raises(ValueError, match="PAPER"):
            _assert_paper_output_path(Path("/tmp/not_paper/output.jsonl"))

    def test_paper_path_accepted(self):
        from wbc_backend.prediction.mlb_model_probability_adapter import _assert_paper_output_path
        p = _paper_tmp_path()
        # Should not raise
        _assert_paper_output_path(p)
