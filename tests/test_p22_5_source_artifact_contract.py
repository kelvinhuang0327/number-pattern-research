"""
Tests for P22.5 source artifact contract.
Validates frozen dataclass enforcement and gate constants.
"""
import pytest

from wbc_backend.recommendation.p22_5_source_artifact_contract import (
    HISTORICAL_GAME_IDENTITY,
    HISTORICAL_MARKET_ODDS,
    HISTORICAL_OOF_PREDICTIONS,
    HISTORICAL_P15_JOINED_INPUT,
    HISTORICAL_P15_SIMULATION_INPUT,
    MAPPING_RISK_HIGH,
    MAPPING_RISK_LOW,
    MAPPING_RISK_MEDIUM,
    P22_5_BLOCKED_CONTRACT_VIOLATION,
    P22_5_BLOCKED_NO_SOURCE_CANDIDATES,
    P22_5_BLOCKED_UNSAFE_SOURCE_MAPPING,
    P22_5_FAIL_INPUT_MISSING,
    P22_5_FAIL_NON_DETERMINISTIC,
    P22_5_SOURCE_ARTIFACT_BUILDER_READY,
    SOURCE_CANDIDATE_MISSING,
    SOURCE_CANDIDATE_PARTIAL,
    SOURCE_CANDIDATE_UNKNOWN,
    SOURCE_CANDIDATE_UNSAFE_MAPPING,
    SOURCE_CANDIDATE_USABLE,
    P225ArtifactBuildPlan,
    P225ArtifactBuilderGateResult,
    P225DateSourceAvailability,
    P225HistoricalSourceCandidate,
    P225SourceArtifactSpec,
)


# ---------------------------------------------------------------------------
# Gate constant tests
# ---------------------------------------------------------------------------


def test_gate_constants_are_strings():
    assert isinstance(P22_5_SOURCE_ARTIFACT_BUILDER_READY, str)
    assert isinstance(P22_5_BLOCKED_NO_SOURCE_CANDIDATES, str)
    assert isinstance(P22_5_BLOCKED_UNSAFE_SOURCE_MAPPING, str)
    assert isinstance(P22_5_BLOCKED_CONTRACT_VIOLATION, str)
    assert isinstance(P22_5_FAIL_INPUT_MISSING, str)
    assert isinstance(P22_5_FAIL_NON_DETERMINISTIC, str)


def test_gate_constants_are_unique():
    gates = [
        P22_5_SOURCE_ARTIFACT_BUILDER_READY,
        P22_5_BLOCKED_NO_SOURCE_CANDIDATES,
        P22_5_BLOCKED_UNSAFE_SOURCE_MAPPING,
        P22_5_BLOCKED_CONTRACT_VIOLATION,
        P22_5_FAIL_INPUT_MISSING,
        P22_5_FAIL_NON_DETERMINISTIC,
    ]
    assert len(set(gates)) == len(gates), "Gate constants must be unique"


def test_source_type_constants_unique():
    types = [
        HISTORICAL_OOF_PREDICTIONS,
        HISTORICAL_MARKET_ODDS,
        HISTORICAL_P15_JOINED_INPUT,
        HISTORICAL_P15_SIMULATION_INPUT,
        HISTORICAL_GAME_IDENTITY,
    ]
    assert len(set(types)) == len(types)


def test_candidate_status_constants_unique():
    statuses = [
        SOURCE_CANDIDATE_USABLE,
        SOURCE_CANDIDATE_PARTIAL,
        SOURCE_CANDIDATE_MISSING,
        SOURCE_CANDIDATE_UNSAFE_MAPPING,
        SOURCE_CANDIDATE_UNKNOWN,
    ]
    assert len(set(statuses)) == len(statuses)


# ---------------------------------------------------------------------------
# P225HistoricalSourceCandidate safety guards
# ---------------------------------------------------------------------------


def _make_candidate(**overrides):
    defaults = dict(
        source_path="/data/mlb_odds.csv",
        source_type=HISTORICAL_MARKET_ODDS,
        source_date="2025-04-15",
        coverage_pct=0.95,
        row_count=2430,
        has_game_id=False,
        has_y_true=True,
        has_odds=True,
        has_p_model_or_p_oof=False,
        mapping_risk=MAPPING_RISK_MEDIUM,
        candidate_status=SOURCE_CANDIDATE_USABLE,
        paper_only=True,
        production_ready=False,
        error_message="",
    )
    defaults.update(overrides)
    return P225HistoricalSourceCandidate(**defaults)


def test_candidate_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_candidate(production_ready=True)


def test_candidate_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_candidate(paper_only=False)


def test_candidate_accepts_valid_defaults():
    c = _make_candidate()
    assert c.paper_only is True
    assert c.production_ready is False
    assert c.candidate_status == SOURCE_CANDIDATE_USABLE


def test_candidate_is_frozen():
    c = _make_candidate()
    with pytest.raises((AttributeError, TypeError)):
        c.has_game_id = True  # type: ignore


# ---------------------------------------------------------------------------
# P225DateSourceAvailability safety guards
# ---------------------------------------------------------------------------


def _make_availability(**overrides):
    defaults = dict(
        run_date="2026-05-05",
        candidate_status=SOURCE_CANDIDATE_USABLE,
        has_predictions=True,
        has_odds=True,
        has_outcomes=True,
        has_identity=True,
        is_p15_ready=True,
        blocked_reason="",
        candidates=(),
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P225DateSourceAvailability(**defaults)


def test_availability_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_availability(production_ready=True)


def test_availability_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_availability(paper_only=False)


def test_availability_is_frozen():
    a = _make_availability()
    with pytest.raises((AttributeError, TypeError)):
        a.is_p15_ready = False  # type: ignore


# ---------------------------------------------------------------------------
# P225ArtifactBuildPlan safety guards
# ---------------------------------------------------------------------------


def _make_plan(**overrides):
    defaults = dict(
        date_start="2026-05-01",
        date_end="2026-05-12",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(overrides)
    return P225ArtifactBuildPlan(**defaults)


def test_plan_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_plan(production_ready=True)


def test_plan_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_plan(paper_only=False)


def test_plan_is_frozen():
    plan = _make_plan()
    with pytest.raises((AttributeError, TypeError)):
        plan.date_start = "2026-01-01"  # type: ignore


def test_plan_accepts_ready_dates():
    plan = _make_plan(
        dates_ready_to_build_p15_inputs=("2026-05-01", "2026-05-02"),
    )
    assert len(plan.dates_ready_to_build_p15_inputs) == 2


# ---------------------------------------------------------------------------
# P225ArtifactBuilderGateResult safety guards
# ---------------------------------------------------------------------------


def _make_gate(**overrides):
    defaults = dict(
        p22_5_gate=P22_5_SOURCE_ARTIFACT_BUILDER_READY,
        date_start="2026-05-01",
        date_end="2026-05-12",
        n_source_candidates=5,
        n_usable_candidates=3,
        n_dates_ready_to_build=11,
        n_dates_partial=0,
        n_dates_unsafe=0,
        n_dates_missing=1,
        dry_run_preview_count=11,
        recommended_next_action="P23 Execute Replayable Historical Backfill.",
        paper_only=True,
        production_ready=False,
        generated_at="2026-05-12T00:00:00Z",
    )
    defaults.update(overrides)
    return P225ArtifactBuilderGateResult(**defaults)


def test_gate_result_rejects_production_ready_true():
    with pytest.raises(ValueError, match="production_ready must be False"):
        _make_gate(production_ready=True)


def test_gate_result_rejects_paper_only_false():
    with pytest.raises(ValueError, match="paper_only must be True"):
        _make_gate(paper_only=False)


def test_gate_result_accepts_ready():
    gr = _make_gate()
    assert gr.p22_5_gate == P22_5_SOURCE_ARTIFACT_BUILDER_READY
    assert gr.n_dates_ready_to_build == 11
    assert gr.paper_only is True
    assert gr.production_ready is False


def test_gate_result_is_frozen():
    gr = _make_gate()
    with pytest.raises((AttributeError, TypeError)):
        gr.n_dates_ready_to_build = 0  # type: ignore


# ---------------------------------------------------------------------------
# P225SourceArtifactSpec
# ---------------------------------------------------------------------------


def test_source_artifact_spec_defaults():
    spec = P225SourceArtifactSpec(source_type=HISTORICAL_OOF_PREDICTIONS)
    assert spec.required_columns == ()
    assert spec.optional_columns == ()
    assert spec.min_rows == 1
