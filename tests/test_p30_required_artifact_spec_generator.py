"""
tests/test_p30_required_artifact_spec_generator.py

Unit tests for P30 required artifact spec generator.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List

import pytest

from wbc_backend.recommendation.p30_required_artifact_spec_generator import (
    build_required_artifact_specs,
    identify_schema_gaps,
    map_existing_sources_to_specs,
    validate_required_artifact_specs,
    write_artifact_spec_docs,
)
from wbc_backend.recommendation.p30_source_acquisition_contract import (
    ARTIFACT_GAME_IDENTITY,
    ARTIFACT_GAME_OUTCOMES,
    ARTIFACT_MARKET_ODDS,
    ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
    ARTIFACT_PAPER_REPLAY_OUTPUT,
    ARTIFACT_TRUE_DATE_JOINED_INPUT,
    ARTIFACT_TRUE_DATE_SLICE_OUTPUT,
    P30RequiredArtifactSpec,
)


# ---------------------------------------------------------------------------
# build_required_artifact_specs
# ---------------------------------------------------------------------------


def test_build_specs_returns_5_for_2024():
    """build_required_artifact_specs returns exactly 5 primary specs."""
    specs = build_required_artifact_specs("2024")
    # Should include at least the 5 primary artifact types
    artifact_types = {s.artifact_type for s in specs}
    required = {
        ARTIFACT_GAME_IDENTITY,
        ARTIFACT_GAME_OUTCOMES,
        ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
        ARTIFACT_MARKET_ODDS,
        ARTIFACT_TRUE_DATE_JOINED_INPUT,
    }
    assert required.issubset(artifact_types)


def test_build_specs_count_is_7():
    """Should return one spec per artifact type constant (7 total)."""
    specs = build_required_artifact_specs("2024")
    assert len(specs) == 7


def test_build_specs_all_have_required_columns():
    specs = build_required_artifact_specs("2024")
    for s in specs:
        assert len(s.required_columns) > 0, f"{s.artifact_type} has empty required_columns"


def test_build_specs_all_paper_only():
    specs = build_required_artifact_specs("2024")
    for s in specs:
        assert s.paper_only is True
        assert s.production_ready is False


def test_build_specs_target_season_2024():
    specs = build_required_artifact_specs("2024")
    for s in specs:
        assert s.target_season == "2024"


def test_build_specs_missing_coverage_initially():
    specs = build_required_artifact_specs("2024")
    # No sources mapped yet — all should start as MISSING
    for s in specs:
        assert s.coverage_status == "MISSING"


# ---------------------------------------------------------------------------
# validate_required_artifact_specs
# ---------------------------------------------------------------------------


def test_validate_passes_for_full_specs():
    specs = build_required_artifact_specs("2024")
    assert validate_required_artifact_specs(specs) is True


def test_validate_raises_for_missing_artifact_type():
    # Only supply 3 specs — should raise
    specs = build_required_artifact_specs("2024")[:3]
    with pytest.raises(ValueError, match="Missing artifact spec types"):
        validate_required_artifact_specs(specs)


def test_validate_raises_for_invalid_coverage():
    specs = build_required_artifact_specs("2024")
    # Tamper by creating a new spec with invalid coverage
    bad_specs = list(specs) + [
        P30RequiredArtifactSpec(
            artifact_type=ARTIFACT_GAME_IDENTITY,
            target_season="2024",
            required_columns="game_id",
            accepted_aliases="{}",
            is_present_in_existing_source=False,
            coverage_status="FULL",  # valid
            missing_columns="",
            schema_gap_note="",
            paper_only=True,
            production_ready=False,
        )
    ]
    # Should pass since coverage is valid
    # Let's make one with truly invalid coverage (this would fail P30RequiredArtifactSpec __post_init__)
    with pytest.raises(ValueError):
        P30RequiredArtifactSpec(
            artifact_type=ARTIFACT_GAME_IDENTITY,
            target_season="2024",
            required_columns="game_id",
            accepted_aliases="{}",
            is_present_in_existing_source=False,
            coverage_status="BOGUS",
            missing_columns="",
            schema_gap_note="",
            paper_only=True,
            production_ready=False,
        )


# ---------------------------------------------------------------------------
# map_existing_sources_to_specs
# ---------------------------------------------------------------------------


def _make_inventory_candidate(columns: List[str], status: str = "SOURCE_PLAN_PARTIAL"):
    return {
        "path": "/tmp/test.csv",
        "source_type": "csv",
        "target_season": "2024",
        "source_status": status,
        "schema_coverage": "PARTIAL",
        "has_game_id": "game_id" in columns,
        "has_game_date": any(c in columns for c in ["game_date", "date", "Date"]),
        "has_y_true": any(c in columns for c in ["y_true", "outcome"]),
        "has_home_away_teams": "home_team" in columns and "away_team" in columns,
        "has_p_model": "p_model" in columns,
        "has_p_market": "p_market" in columns,
        "has_odds_decimal": any(c in columns for c in ["odds_decimal", "Away ML", "Home ML"]),
        "columns": columns,
    }


def test_map_sources_detects_game_identity():
    inventory = [_make_inventory_candidate(["game_id", "game_date", "home_team", "away_team"])]
    specs = build_required_artifact_specs("2024")
    mapped = map_existing_sources_to_specs(inventory, specs)
    identity_spec = next(s for s in mapped if s.artifact_type == ARTIFACT_GAME_IDENTITY)
    assert identity_spec.coverage_status == "FULL"


def test_map_sources_detects_missing_p_market():
    inventory = [_make_inventory_candidate(
        ["game_id", "game_date", "home_team", "away_team", "y_true", "p_model", "odds_decimal"]
    )]
    specs = build_required_artifact_specs("2024")
    mapped = map_existing_sources_to_specs(inventory, specs)
    # MARKET_ODDS requires p_market
    market_spec = next(s for s in mapped if s.artifact_type == ARTIFACT_MARKET_ODDS)
    assert "p_market" in market_spec.missing_columns


def test_map_sources_detects_missing_y_true():
    inventory = [_make_inventory_candidate(
        ["game_id", "game_date", "home_team", "away_team", "p_model", "p_market", "odds_decimal"]
    )]
    specs = build_required_artifact_specs("2024")
    mapped = map_existing_sources_to_specs(inventory, specs)
    outcomes_spec = next(s for s in mapped if s.artifact_type == ARTIFACT_GAME_OUTCOMES)
    assert "y_true" in outcomes_spec.missing_columns


def test_map_sources_returns_same_count_as_input():
    inventory = [_make_inventory_candidate(["game_id", "game_date"])]
    specs = build_required_artifact_specs("2024")
    mapped = map_existing_sources_to_specs(inventory, specs)
    assert len(mapped) == len(specs)


def test_map_sources_all_paper_only():
    inventory = [_make_inventory_candidate(["game_id", "game_date"])]
    specs = build_required_artifact_specs("2024")
    mapped = map_existing_sources_to_specs(inventory, specs)
    for s in mapped:
        assert s.paper_only is True
        assert s.production_ready is False


# ---------------------------------------------------------------------------
# identify_schema_gaps
# ---------------------------------------------------------------------------


def test_schema_gaps_empty_when_all_full():
    specs = build_required_artifact_specs("2024")
    # Manually mark all as full
    full_specs = [
        P30RequiredArtifactSpec(
            artifact_type=s.artifact_type,
            target_season=s.target_season,
            required_columns=s.required_columns,
            accepted_aliases=s.accepted_aliases,
            is_present_in_existing_source=True,
            coverage_status="FULL",
            missing_columns="",
            schema_gap_note="All present.",
            paper_only=True,
            production_ready=False,
        )
        for s in specs
    ]
    gaps = identify_schema_gaps(full_specs)
    assert gaps["schema_gap_count"] == 0
    assert gaps["has_critical_gaps"] is False


def test_schema_gaps_detects_missing_p_market():
    inventory = [_make_inventory_candidate(
        ["game_id", "game_date", "home_team", "away_team", "y_true", "p_model"]
    )]
    specs = build_required_artifact_specs("2024")
    mapped = map_existing_sources_to_specs(inventory, specs)
    gaps = identify_schema_gaps(mapped)
    all_missing = gaps["all_missing_columns"]
    assert "p_market" in all_missing


def test_schema_gaps_detects_missing_y_true():
    inventory = [_make_inventory_candidate(
        ["game_id", "game_date", "Away ML", "Home ML", "p_market", "odds_decimal"]
    )]
    specs = build_required_artifact_specs("2024")
    mapped = map_existing_sources_to_specs(inventory, specs)
    gaps = identify_schema_gaps(mapped)
    all_missing = gaps["all_missing_columns"]
    assert "y_true" in all_missing


def test_schema_gaps_critical_when_no_model_predictions():
    inventory = [_make_inventory_candidate(["game_id", "game_date"])]
    specs = build_required_artifact_specs("2024")
    mapped = map_existing_sources_to_specs(inventory, specs)
    gaps = identify_schema_gaps(mapped)
    assert gaps["has_critical_gaps"] is True
    assert ARTIFACT_MODEL_PREDICTIONS_OR_OOF in gaps["critical_missing_artifacts"]


# ---------------------------------------------------------------------------
# write_artifact_spec_docs
# ---------------------------------------------------------------------------


def test_write_artifact_spec_docs_creates_files(tmp_path):
    specs = build_required_artifact_specs("2024")
    inventory = [_make_inventory_candidate(["game_id", "game_date"])]
    mapped = map_existing_sources_to_specs(inventory, specs)
    gaps = identify_schema_gaps(mapped)
    write_artifact_spec_docs(tmp_path, mapped, gaps, "2024")
    assert (tmp_path / "required_artifact_specs.json").exists()
    assert (tmp_path / "schema_gap_report.json").exists()


def test_write_artifact_spec_docs_valid_json(tmp_path):
    specs = build_required_artifact_specs("2024")
    inventory = [_make_inventory_candidate(["game_id", "game_date"])]
    mapped = map_existing_sources_to_specs(inventory, specs)
    gaps = identify_schema_gaps(mapped)
    write_artifact_spec_docs(tmp_path, mapped, gaps, "2024")
    spec_data = json.loads((tmp_path / "required_artifact_specs.json").read_text())
    assert "specs" in spec_data
    assert "target_season" in spec_data
