"""
tests/test_p30_dry_run_artifact_builder_skeleton.py

Unit tests for P30 dry-run artifact builder skeleton.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict, Any

import pandas as pd
import pytest

from wbc_backend.recommendation.p30_dry_run_artifact_builder_skeleton import (
    DRY_RUN_STATUS_BLOCKED_MISSING,
    DRY_RUN_STATUS_EMPTY,
    DRY_RUN_STATUS_PREVIEW_READY,
    PREVIEW_SCHEMA_COLUMNS,
    build_dry_run_joined_input_preview,
    summarize_preview,
    validate_joined_input_preview,
    write_preview_artifacts,
)
from wbc_backend.recommendation.p30_source_acquisition_contract import (
    ARTIFACT_GAME_IDENTITY,
    ARTIFACT_GAME_OUTCOMES,
    ARTIFACT_MARKET_ODDS,
    ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
    ARTIFACT_TRUE_DATE_JOINED_INPUT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def identity_csv(tmp_path):
    """Write a minimal identity CSV (no fabricated predictions/outcomes)."""
    path = tmp_path / "identity.csv"
    df = pd.DataFrame(
        {
            "game_date": ["2024-04-01", "2024-04-02"],
            "home_team": ["Team A", "Team B"],
            "away_team": ["Team C", "Team D"],
        }
    )
    df.to_csv(path, index=False)
    return path


@pytest.fixture
def complete_csv(tmp_path):
    """Write a CSV with all preview schema columns."""
    path = tmp_path / "complete.csv"
    df = pd.DataFrame(
        {
            "game_id": ["G001", "G002"],
            "game_date": ["2024-04-01", "2024-04-02"],
            "home_team": ["Team A", "Team B"],
            "away_team": ["Team C", "Team D"],
            "y_true": [1, 0],
            "p_model": [0.6, 0.4],
            "p_market": [0.55, 0.45],
            "odds_decimal": [1.81, 2.22],
        }
    )
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# build_dry_run_joined_input_preview
# ---------------------------------------------------------------------------


def test_preview_returns_dataframe_from_identity_source(identity_csv):
    mapping = {ARTIFACT_GAME_IDENTITY: str(identity_csv)}
    df = build_dry_run_joined_input_preview(mapping, Path("/tmp"))
    assert isinstance(df, pd.DataFrame)


def test_preview_returns_dataframe_from_complete_source(complete_csv):
    mapping = {ARTIFACT_GAME_IDENTITY: str(complete_csv)}
    df = build_dry_run_joined_input_preview(mapping, Path("/tmp"))
    assert isinstance(df, pd.DataFrame)
    assert len(df) > 0


def test_preview_returns_empty_for_empty_mapping(tmp_path):
    df = build_dry_run_joined_input_preview({}, tmp_path)
    assert isinstance(df, pd.DataFrame)
    assert df.empty


def test_preview_does_not_fabricate_missing_odds(identity_csv):
    """Preview should not add p_model or odds columns if they are not in the source."""
    mapping = {ARTIFACT_GAME_IDENTITY: str(identity_csv)}
    df = build_dry_run_joined_input_preview(mapping, Path("/tmp"))
    # identity_csv has no p_model or odds_decimal
    assert "p_model" not in df.columns
    assert "odds_decimal" not in df.columns


def test_preview_does_not_fabricate_y_true(identity_csv):
    """Preview should not add y_true column if not in source."""
    mapping = {ARTIFACT_GAME_IDENTITY: str(identity_csv)}
    df = build_dry_run_joined_input_preview(mapping, Path("/tmp"))
    assert "y_true" not in df.columns


def test_preview_uses_complete_source_columns(complete_csv):
    mapping = {ARTIFACT_GAME_IDENTITY: str(complete_csv)}
    df = build_dry_run_joined_input_preview(mapping, Path("/tmp"))
    expected_cols = set(PREVIEW_SCHEMA_COLUMNS)
    present_cols = set(df.columns)
    # All present cols should be a subset of preview schema
    assert present_cols.issubset(expected_cols)


def test_preview_empty_for_bad_path(tmp_path):
    mapping = {ARTIFACT_GAME_IDENTITY: str(tmp_path / "nonexistent.csv")}
    df = build_dry_run_joined_input_preview(mapping, tmp_path)
    assert isinstance(df, pd.DataFrame)
    assert df.empty


# ---------------------------------------------------------------------------
# validate_joined_input_preview
# ---------------------------------------------------------------------------


def test_validate_empty_df_is_invalid():
    df = pd.DataFrame(columns=PREVIEW_SCHEMA_COLUMNS)
    result = validate_joined_input_preview(df)
    assert result["is_valid"] is False
    assert result["n_rows"] == 0
    assert len(result["blocker_reasons"]) > 0


def test_validate_complete_df_is_valid():
    df = pd.DataFrame(
        {
            "game_id": ["G001"],
            "game_date": ["2024-04-01"],
            "home_team": ["A"],
            "away_team": ["B"],
            "y_true": [1],
            "p_model": [0.6],
            "p_market": [0.55],
            "odds_decimal": [1.81],
        }
    )
    result = validate_joined_input_preview(df)
    assert result["is_valid"] is True
    assert result["n_rows"] == 1
    assert result["columns_missing"] == []


def test_validate_partial_df_reports_missing_cols():
    df = pd.DataFrame({"game_date": ["2024-04-01"], "home_team": ["A"], "away_team": ["B"]})
    result = validate_joined_input_preview(df)
    assert result["is_valid"] is False
    assert "p_model" in result["columns_missing"]
    assert "y_true" in result["columns_missing"]
    assert len(result["blocker_reasons"]) > 0


def test_validate_reports_missing_model():
    df = pd.DataFrame(
        {
            "game_id": ["G001"],
            "game_date": ["2024-04-01"],
            "home_team": ["A"],
            "away_team": ["B"],
            "y_true": [1],
            "p_market": [0.55],
            "odds_decimal": [1.81],
        }
    )
    result = validate_joined_input_preview(df)
    assert "p_model" in result["columns_missing"]
    assert any("p_model" in b or "model" in b.lower() for b in result["blocker_reasons"])


# ---------------------------------------------------------------------------
# summarize_preview
# ---------------------------------------------------------------------------


def test_summarize_empty_df():
    df = pd.DataFrame(columns=PREVIEW_SCHEMA_COLUMNS)
    summary = summarize_preview(df)
    assert summary["n_rows"] == 0
    assert summary["dry_run_status"] == DRY_RUN_STATUS_BLOCKED_MISSING
    assert len(summary["blocker_reasons"]) > 0
    assert summary["paper_only"] is True
    assert summary["production_ready"] is False
    assert summary["is_fabricated"] is False


def test_summarize_partial_df():
    df = pd.DataFrame({"game_date": ["2024-04-01"], "home_team": ["A"]})
    summary = summarize_preview(df)
    assert summary["n_rows"] == 1
    assert summary["dry_run_status"] == DRY_RUN_STATUS_PREVIEW_READY
    assert summary["schema_coverage"] == "PARTIAL"
    assert summary["is_fabricated"] is False


def test_summarize_complete_df():
    df = pd.DataFrame(
        {
            "game_id": ["G001"],
            "game_date": ["2024-04-01"],
            "home_team": ["A"],
            "away_team": ["B"],
            "y_true": [1],
            "p_model": [0.6],
            "p_market": [0.55],
            "odds_decimal": [1.81],
        }
    )
    summary = summarize_preview(df)
    assert summary["dry_run_status"] == DRY_RUN_STATUS_PREVIEW_READY
    assert summary["schema_coverage"] == "FULL"


def test_summarize_returns_dict_with_note():
    df = pd.DataFrame(columns=PREVIEW_SCHEMA_COLUMNS)
    summary = summarize_preview(df)
    assert "note" in summary
    assert "fabricated" in summary["note"].lower() or "no data" in summary["note"].lower() or "dry-run" in summary["note"].lower()


# ---------------------------------------------------------------------------
# write_preview_artifacts
# ---------------------------------------------------------------------------


def test_write_preview_creates_files(tmp_path):
    df = pd.DataFrame({"game_date": ["2024-04-01"], "home_team": ["A"]})
    summary = summarize_preview(df)
    validation = validate_joined_input_preview(df)
    write_preview_artifacts(tmp_path, df, summary, validation)
    preview_dir = tmp_path / "preview"
    assert (preview_dir / "joined_input_preview.csv").exists()
    assert (preview_dir / "dry_run_preview_summary.json").exists()
    assert (preview_dir / "dry_run_preview_validation.json").exists()


def test_write_preview_empty_df_still_creates_files(tmp_path):
    df = pd.DataFrame(columns=PREVIEW_SCHEMA_COLUMNS)
    summary = summarize_preview(df)
    validation = validate_joined_input_preview(df)
    write_preview_artifacts(tmp_path, df, summary, validation)
    preview_dir = tmp_path / "preview"
    assert (preview_dir / "joined_input_preview.csv").exists()


def test_write_preview_summary_valid_json(tmp_path):
    df = pd.DataFrame({"game_date": ["2024-04-01"]})
    summary = summarize_preview(df)
    validation = validate_joined_input_preview(df)
    write_preview_artifacts(tmp_path, df, summary, validation)
    data = json.loads((tmp_path / "preview" / "dry_run_preview_summary.json").read_text())
    assert "n_rows" in data
    assert "is_fabricated" in data
    assert data["is_fabricated"] is False
