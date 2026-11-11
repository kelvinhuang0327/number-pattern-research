"""
Tests for P32 Raw Game Artifact Writer.

Coverage:
- identity artifact is written with correct columns (no odds/scores)
- outcomes artifact includes scores and y_true_home_win
- joined artifact is written
- _assert_no_blocked_columns raises on forbidden columns
- manifest JSON lists correct files
- summary JSON is written
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p32_raw_game_artifact_writer import (
    BLOCKED_COLUMNS,
    IDENTITY_COLUMNS,
    IDENTITY_FILENAME,
    JOINED_FILENAME,
    MANIFEST_FILENAME,
    OUTCOME_COLUMNS,
    OUTCOMES_FILENAME,
    SUMMARY_FILENAME,
    _assert_no_blocked_columns,
    build_artifact_manifest,
    write_p32_summary,
    write_raw_game_identity_artifact,
    write_raw_game_joined_artifact,
    write_raw_game_outcome_artifact,
)
from wbc_backend.recommendation.p32_raw_game_log_contract import P32RawGameLogBuildSummary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_parsed_df(n: int = 5) -> pd.DataFrame:
    """Build a synthetic canonical DataFrame matching parser output schema."""
    rows = []
    for i in range(n):
        day = 1 + i
        date = f"2024-04-{day:02d}"
        game_id = f"NYY-202404{day:02d}-0"
        rows.append(
            {
                "game_id": game_id,
                "game_date": date,
                "away_team": "BOS",
                "home_team": "NYY",
                "away_score": 3 + i,
                "home_score": 5 + i,
                "y_true_home_win": 1,
                "season": 2024,
                "source_name": "Retrosheet",
                "source_row_number": i + 1,
            }
        )
    return pd.DataFrame(rows)


def _make_summary(output_dir: Path) -> P32RawGameLogBuildSummary:
    return P32RawGameLogBuildSummary(
        season=2024,
        source_name="Retrosheet",
        source_path=str(output_dir / "gl2024.txt"),
        row_count_raw=100,
        row_count_processed=95,
        unique_game_id_count=95,
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


# ---------------------------------------------------------------------------
# _assert_no_blocked_columns
# ---------------------------------------------------------------------------


class TestAssertNoBlockedColumns:
    def test_passes_clean_df(self) -> None:
        df = _make_parsed_df(3)
        # Should not raise
        _assert_no_blocked_columns(df, "test_artifact")

    def test_raises_on_odds_column(self) -> None:
        df = _make_parsed_df(3)
        df["odds"] = 1.5
        with pytest.raises(ValueError, match="odds"):
            _assert_no_blocked_columns(df, "identity")

    def test_raises_on_predicted_probability(self) -> None:
        df = _make_parsed_df(3)
        df["predicted_probability"] = 0.6
        with pytest.raises(ValueError, match="predicted_probability"):
            _assert_no_blocked_columns(df, "outcome")

    def test_raises_on_kelly_fraction(self) -> None:
        df = _make_parsed_df(3)
        df["kelly_fraction"] = 0.05
        with pytest.raises(ValueError, match="kelly_fraction"):
            _assert_no_blocked_columns(df, "joined")

    def test_blocked_columns_constant_not_empty(self) -> None:
        assert len(BLOCKED_COLUMNS) > 0
        assert "odds" in BLOCKED_COLUMNS
        assert "predicted_probability" in BLOCKED_COLUMNS


# ---------------------------------------------------------------------------
# write_raw_game_identity_artifact
# ---------------------------------------------------------------------------


class TestWriteRawGameIdentityArtifact:
    def test_file_is_written(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_identity_artifact(df, tmp_path)
        assert path.exists()
        assert path.name == IDENTITY_FILENAME

    def test_correct_columns_in_identity(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_identity_artifact(df, tmp_path)
        written = pd.read_csv(path)
        for col in IDENTITY_COLUMNS:
            assert col in written.columns

    def test_no_scores_in_identity(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_identity_artifact(df, tmp_path)
        written = pd.read_csv(path)
        assert "away_score" not in written.columns
        assert "home_score" not in written.columns
        assert "y_true_home_win" not in written.columns

    def test_no_odds_in_identity(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_identity_artifact(df, tmp_path)
        written = pd.read_csv(path)
        for blocked in BLOCKED_COLUMNS:
            assert blocked not in written.columns

    def test_row_count_preserved(self, tmp_path: Path) -> None:
        df = _make_parsed_df(7)
        path = write_raw_game_identity_artifact(df, tmp_path)
        written = pd.read_csv(path)
        assert len(written) == 7


# ---------------------------------------------------------------------------
# write_raw_game_outcome_artifact
# ---------------------------------------------------------------------------


class TestWriteRawGameOutcomeArtifact:
    def test_file_is_written(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_outcome_artifact(df, tmp_path)
        assert path.exists()
        assert path.name == OUTCOMES_FILENAME

    def test_outcome_includes_scores(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_outcome_artifact(df, tmp_path)
        written = pd.read_csv(path)
        assert "away_score" in written.columns
        assert "home_score" in written.columns
        assert "y_true_home_win" in written.columns

    def test_outcome_columns_match_spec(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_outcome_artifact(df, tmp_path)
        written = pd.read_csv(path)
        for col in OUTCOME_COLUMNS:
            assert col in written.columns

    def test_no_odds_in_outcome(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_outcome_artifact(df, tmp_path)
        written = pd.read_csv(path)
        for blocked in BLOCKED_COLUMNS:
            assert blocked not in written.columns


# ---------------------------------------------------------------------------
# write_raw_game_joined_artifact
# ---------------------------------------------------------------------------


class TestWriteRawGameJoinedArtifact:
    def test_file_is_written(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_joined_artifact(df, tmp_path)
        assert path.exists()
        assert path.name == JOINED_FILENAME

    def test_no_odds_in_joined(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_joined_artifact(df, tmp_path)
        written = pd.read_csv(path)
        for blocked in BLOCKED_COLUMNS:
            assert blocked not in written.columns

    def test_contains_both_identity_and_outcome_cols(self, tmp_path: Path) -> None:
        df = _make_parsed_df(5)
        path = write_raw_game_joined_artifact(df, tmp_path)
        written = pd.read_csv(path)
        for col in IDENTITY_COLUMNS:
            assert col in written.columns
        assert "away_score" in written.columns
        assert "home_score" in written.columns


# ---------------------------------------------------------------------------
# write_p32_summary
# ---------------------------------------------------------------------------


class TestWriteP32Summary:
    def test_summary_file_written(self, tmp_path: Path) -> None:
        summary = _make_summary(tmp_path)
        path = write_p32_summary(summary, tmp_path)
        assert path.exists()
        assert path.name == SUMMARY_FILENAME

    def test_summary_is_valid_json(self, tmp_path: Path) -> None:
        summary = _make_summary(tmp_path)
        path = write_p32_summary(summary, tmp_path)
        data = json.loads(path.read_text())
        assert data["season"] == 2024
        assert data["contains_odds"] is False
        assert data["contains_predictions"] is False
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_summary_row_counts(self, tmp_path: Path) -> None:
        summary = _make_summary(tmp_path)
        path = write_p32_summary(summary, tmp_path)
        data = json.loads(path.read_text())
        assert data["row_count_raw"] == 100
        assert data["row_count_processed"] == 95


# ---------------------------------------------------------------------------
# build_artifact_manifest
# ---------------------------------------------------------------------------


class TestBuildArtifactManifest:
    def test_manifest_written(self, tmp_path: Path) -> None:
        # Write some fake artifacts first
        (tmp_path / IDENTITY_FILENAME).write_text("game_id\n")
        (tmp_path / OUTCOMES_FILENAME).write_text("game_id\n")
        path = build_artifact_manifest(tmp_path)
        assert path.exists()
        assert path.name == MANIFEST_FILENAME

    def test_manifest_lists_files(self, tmp_path: Path) -> None:
        (tmp_path / IDENTITY_FILENAME).write_text("game_id\n")
        (tmp_path / OUTCOMES_FILENAME).write_text("game_id\n")
        build_artifact_manifest(tmp_path)
        data = json.loads((tmp_path / MANIFEST_FILENAME).read_text())
        assert "artifacts" in data
        filenames = [a["filename"] for a in data["artifacts"]]
        assert any(IDENTITY_FILENAME in f for f in filenames)
        assert any(OUTCOMES_FILENAME in f for f in filenames)

    def test_manifest_includes_paper_only_flag(self, tmp_path: Path) -> None:
        build_artifact_manifest(tmp_path)
        data = json.loads((tmp_path / MANIFEST_FILENAME).read_text())
        assert data.get("paper_only") is True
        assert data.get("production_ready") is False
