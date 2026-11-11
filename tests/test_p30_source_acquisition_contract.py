"""
tests/test_p30_source_acquisition_contract.py

Unit tests for P30 source acquisition contract — gate constants,
source statuses, artifact types, and frozen dataclasses.
"""
from __future__ import annotations

import pytest
import dataclasses

from wbc_backend.recommendation.p30_source_acquisition_contract import (
    # Gate constants
    P30_SOURCE_ACQUISITION_PLAN_READY,
    P30_BLOCKED_NO_VERIFIABLE_SOURCE,
    P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE,
    P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC,
    P30_BLOCKED_CONTRACT_VIOLATION,
    P30_FAIL_INPUT_MISSING,
    P30_FAIL_NON_DETERMINISTIC,
    # Source statuses
    SOURCE_PLAN_READY,
    SOURCE_PLAN_PARTIAL,
    SOURCE_PLAN_BLOCKED_PROVENANCE,
    SOURCE_PLAN_BLOCKED_SCHEMA_GAP,
    SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
    # Artifact types
    ARTIFACT_GAME_IDENTITY,
    ARTIFACT_GAME_OUTCOMES,
    ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
    ARTIFACT_MARKET_ODDS,
    ARTIFACT_TRUE_DATE_JOINED_INPUT,
    ARTIFACT_TRUE_DATE_SLICE_OUTPUT,
    ARTIFACT_PAPER_REPLAY_OUTPUT,
    # Dataclasses
    P30HistoricalSeasonSourceCandidate,
    P30RequiredArtifactSpec,
    P30SourceAcquisitionPlan,
    P30ArtifactBuilderPlan,
    P30SourceAcquisitionGateResult,
    _VALID_P30_GATES,
    _VALID_SOURCE_STATUSES,
    _VALID_ARTIFACT_TYPES,
)


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------


def test_gate_constants_are_strings():
    gates = [
        P30_SOURCE_ACQUISITION_PLAN_READY,
        P30_BLOCKED_NO_VERIFIABLE_SOURCE,
        P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE,
        P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC,
        P30_BLOCKED_CONTRACT_VIOLATION,
        P30_FAIL_INPUT_MISSING,
        P30_FAIL_NON_DETERMINISTIC,
    ]
    for g in gates:
        assert isinstance(g, str), f"Gate {g} is not a string"


def test_gate_constants_are_unique():
    gates = [
        P30_SOURCE_ACQUISITION_PLAN_READY,
        P30_BLOCKED_NO_VERIFIABLE_SOURCE,
        P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE,
        P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC,
        P30_BLOCKED_CONTRACT_VIOLATION,
        P30_FAIL_INPUT_MISSING,
        P30_FAIL_NON_DETERMINISTIC,
    ]
    assert len(gates) == len(set(gates))


def test_all_7_gate_constants_defined():
    assert len(_VALID_P30_GATES) == 7


def test_gate_ready_prefix():
    assert P30_SOURCE_ACQUISITION_PLAN_READY.startswith("P30_")


def test_gate_blocked_prefix():
    assert P30_BLOCKED_NO_VERIFIABLE_SOURCE.startswith("P30_BLOCKED_")
    assert P30_BLOCKED_LICENSE_OR_PROVENANCE_UNSAFE.startswith("P30_BLOCKED_")
    assert P30_BLOCKED_MISSING_REQUIRED_ARTIFACT_SPEC.startswith("P30_BLOCKED_")


def test_gate_fail_prefix():
    assert P30_FAIL_INPUT_MISSING.startswith("P30_FAIL_")
    assert P30_FAIL_NON_DETERMINISTIC.startswith("P30_FAIL_")


# ---------------------------------------------------------------------------
# Source candidate status constants
# ---------------------------------------------------------------------------


def test_source_statuses_are_strings():
    statuses = [
        SOURCE_PLAN_READY,
        SOURCE_PLAN_PARTIAL,
        SOURCE_PLAN_BLOCKED_PROVENANCE,
        SOURCE_PLAN_BLOCKED_SCHEMA_GAP,
        SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
    ]
    for s in statuses:
        assert isinstance(s, str)


def test_exactly_5_source_statuses():
    assert len(_VALID_SOURCE_STATUSES) == 5


def test_source_statuses_are_distinct():
    statuses = list(_VALID_SOURCE_STATUSES)
    assert len(statuses) == len(set(statuses))


# ---------------------------------------------------------------------------
# Artifact type constants
# ---------------------------------------------------------------------------


def test_artifact_types_are_strings():
    types = [
        ARTIFACT_GAME_IDENTITY,
        ARTIFACT_GAME_OUTCOMES,
        ARTIFACT_MODEL_PREDICTIONS_OR_OOF,
        ARTIFACT_MARKET_ODDS,
        ARTIFACT_TRUE_DATE_JOINED_INPUT,
        ARTIFACT_TRUE_DATE_SLICE_OUTPUT,
        ARTIFACT_PAPER_REPLAY_OUTPUT,
    ]
    for t in types:
        assert isinstance(t, str)


def test_exactly_7_artifact_types():
    assert len(_VALID_ARTIFACT_TYPES) == 7


# ---------------------------------------------------------------------------
# P30HistoricalSeasonSourceCandidate
# ---------------------------------------------------------------------------


def _make_source_candidate(**overrides) -> P30HistoricalSeasonSourceCandidate:
    defaults = dict(
        source_path="data/mlb_2024/test.csv",
        source_type="csv",
        target_season="2024",
        date_start="2024-03-20",
        date_end="2024-09-29",
        estimated_games=2430,
        estimated_rows=2430,
        has_game_id=False,
        has_game_date=True,
        has_y_true=False,
        has_home_away_teams=True,
        has_p_model=False,
        has_p_market=False,
        has_odds_decimal=True,
        provenance_status="KNOWN_HISTORICAL",
        license_risk="LOW",
        schema_coverage="PARTIAL",
        source_status=SOURCE_PLAN_PARTIAL,
        coverage_note="Missing model predictions.",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P30HistoricalSeasonSourceCandidate(**defaults)


def test_source_candidate_valid():
    obj = _make_source_candidate()
    assert obj.target_season == "2024"
    assert obj.paper_only is True
    assert obj.production_ready is False


def test_source_candidate_is_frozen():
    obj = _make_source_candidate()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        obj.target_season = "2025"  # type: ignore[misc]


def test_source_candidate_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_source_candidate(paper_only=False)


def test_source_candidate_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_source_candidate(production_ready=True)


def test_source_candidate_rejects_invalid_status():
    with pytest.raises(ValueError, match="source_status"):
        _make_source_candidate(source_status="INVALID_STATUS")


# ---------------------------------------------------------------------------
# P30RequiredArtifactSpec
# ---------------------------------------------------------------------------


def _make_artifact_spec(**overrides) -> P30RequiredArtifactSpec:
    defaults = dict(
        artifact_type=ARTIFACT_GAME_OUTCOMES,
        target_season="2024",
        required_columns="game_id, y_true",
        accepted_aliases='{"game_id": ["game_pk"]}',
        is_present_in_existing_source=False,
        coverage_status="MISSING",
        missing_columns="game_id, y_true",
        schema_gap_note="No source for game outcomes.",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P30RequiredArtifactSpec(**defaults)


def test_artifact_spec_valid():
    obj = _make_artifact_spec()
    assert obj.artifact_type == ARTIFACT_GAME_OUTCOMES
    assert obj.paper_only is True


def test_artifact_spec_is_frozen():
    obj = _make_artifact_spec()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        obj.artifact_type = ARTIFACT_MARKET_ODDS  # type: ignore[misc]


def test_artifact_spec_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_artifact_spec(paper_only=False)


def test_artifact_spec_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_artifact_spec(production_ready=True)


def test_artifact_spec_rejects_invalid_artifact_type():
    with pytest.raises(ValueError, match="artifact_type"):
        _make_artifact_spec(artifact_type="INVALID_ARTIFACT")


def test_artifact_spec_rejects_invalid_coverage_status():
    with pytest.raises(ValueError):
        _make_artifact_spec(coverage_status="UNKNOWN_STATUS")


# ---------------------------------------------------------------------------
# P30SourceAcquisitionPlan
# ---------------------------------------------------------------------------


def _make_acquisition_plan(**overrides) -> P30SourceAcquisitionPlan:
    defaults = dict(
        target_season="2024",
        date_start="2024-03-20",
        date_end="2024-09-29",
        expected_games=2430,
        expected_min_active_entries=498,
        source_path_or_url="data/mlb_2024/test.csv",
        provenance_status="KNOWN_HISTORICAL",
        license_risk="LOW",
        schema_coverage="PARTIAL",
        n_source_candidates=3,
        n_partial_sources=2,
        n_ready_sources=0,
        schema_gap_count=4,
        missing_artifact_types="MODEL_PREDICTIONS_OR_OOF, GAME_OUTCOMES",
        required_build_steps="Step 1: acquire game outcomes\nStep 2: acquire predictions",
        required_validation_steps="Validate 1: no leakage",
        estimated_sample_gain=498,
        recommended_next_action="Acquire model predictions for 2024.",
        acquisition_feasibility_note="2 partial sources found.",
        p30_gate=P30_BLOCKED_NO_VERIFIABLE_SOURCE,
        audit_status=SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P30SourceAcquisitionPlan(**defaults)


def test_acquisition_plan_valid():
    obj = _make_acquisition_plan()
    assert obj.target_season == "2024"
    assert obj.paper_only is True
    assert obj.production_ready is False


def test_acquisition_plan_is_frozen():
    obj = _make_acquisition_plan()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        obj.target_season = "2025"  # type: ignore[misc]


def test_acquisition_plan_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_acquisition_plan(paper_only=False)


def test_acquisition_plan_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_acquisition_plan(production_ready=True)


def test_acquisition_plan_rejects_invalid_gate():
    with pytest.raises(ValueError, match="p30_gate"):
        _make_acquisition_plan(p30_gate="INVALID_GATE")


# ---------------------------------------------------------------------------
# P30ArtifactBuilderPlan
# ---------------------------------------------------------------------------


def _make_builder_plan(**overrides) -> P30ArtifactBuilderPlan:
    defaults = dict(
        target_season="2024",
        build_phase="P31_BUILD_2024_JOINED_INPUT",
        requires_game_identity=True,
        requires_game_outcomes=True,
        requires_model_predictions=True,
        requires_market_odds=True,
        can_build_joined_input=False,
        can_build_true_date_slices=False,
        can_build_paper_replay=False,
        missing_artifacts="MODEL_PREDICTIONS_OR_OOF, GAME_OUTCOMES",
        dry_run_preview_path="outputs/.../preview/",
        dry_run_status="BLOCKED_MISSING_ARTIFACTS",
        blocker_reason="Missing model predictions.",
        build_command_plan="Step 1: acquire data\nStep 2: join",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P30ArtifactBuilderPlan(**defaults)


def test_builder_plan_valid():
    obj = _make_builder_plan()
    assert obj.target_season == "2024"
    assert obj.paper_only is True


def test_builder_plan_is_frozen():
    obj = _make_builder_plan()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        obj.target_season = "2025"  # type: ignore[misc]


def test_builder_plan_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_builder_plan(paper_only=False)


def test_builder_plan_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_builder_plan(production_ready=True)


# ---------------------------------------------------------------------------
# P30SourceAcquisitionGateResult
# ---------------------------------------------------------------------------


def _make_gate_result(**overrides) -> P30SourceAcquisitionGateResult:
    defaults = dict(
        p30_gate=P30_BLOCKED_NO_VERIFIABLE_SOURCE,
        target_season="2024",
        n_source_candidates=3,
        n_partial_sources=2,
        n_ready_sources=0,
        schema_gap_count=4,
        expected_sample_gain=498,
        recommended_next_action="Acquire 2024 season data.",
        audit_status=SOURCE_PLAN_BLOCKED_NOT_AVAILABLE,
        blocker_reason=P30_BLOCKED_NO_VERIFIABLE_SOURCE,
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P30SourceAcquisitionGateResult(**defaults)


def test_gate_result_valid():
    obj = _make_gate_result()
    assert obj.p30_gate == P30_BLOCKED_NO_VERIFIABLE_SOURCE
    assert obj.paper_only is True
    assert obj.production_ready is False


def test_gate_result_is_frozen():
    obj = _make_gate_result()
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        obj.p30_gate = P30_SOURCE_ACQUISITION_PLAN_READY  # type: ignore[misc]


def test_gate_result_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only"):
        _make_gate_result(paper_only=False)


def test_gate_result_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready"):
        _make_gate_result(production_ready=True)


def test_gate_result_rejects_invalid_gate():
    with pytest.raises(ValueError, match="p30_gate"):
        _make_gate_result(p30_gate="BAD_GATE")
