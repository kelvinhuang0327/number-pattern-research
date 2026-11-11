"""
Tests for P22 historical availability contract.

Covers:
- Gate and status constants are strings
- Frozen dataclass safety invariants (production_ready, paper_only)
- Phase artifact key constants present
- P22GateResult, P22HistoricalAvailabilitySummary, P22BackfillExecutionPlan
- P22DateAvailabilityResult
"""
from __future__ import annotations

import pytest

from wbc_backend.recommendation.p22_historical_availability_contract import (
    DATE_BLOCKED_INVALID_ARTIFACTS,
    DATE_BLOCKED_UNSAFE_IDENTITY,
    DATE_MISSING_REQUIRED_SOURCE,
    DATE_PARTIAL_SOURCE_AVAILABLE,
    DATE_READY_P20_EXISTS,
    DATE_READY_REPLAYABLE_FROM_P15_P16_P19,
    DATE_UNKNOWN,
    P15_JOINED_OOF_WITH_ODDS,
    P15_SIMULATION_LEDGER,
    P16_6_RECOMMENDATION_ROWS,
    P16_6_RECOMMENDATION_SUMMARY,
    P17_REPLAY_LEDGER,
    P17_REPLAY_SUMMARY,
    P19_ENRICHED_LEDGER,
    P19_GATE_RESULT,
    P20_DAILY_SUMMARY,
    P20_GATE_RESULT,
    P22_BLOCKED_NO_AVAILABLE_DATES,
    P22_BLOCKED_CONTRACT_VIOLATION,
    P22_FAIL_INPUT_MISSING,
    P22_FAIL_NON_DETERMINISTIC,
    P22_HISTORICAL_BACKFILL_AVAILABILITY_READY,
    P22BackfillExecutionPlan,
    P22DateAvailabilityResult,
    P22GateResult,
    P22HistoricalAvailabilitySummary,
    P22PhaseArtifactStatus,
)


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------


def test_gate_constants_are_strings() -> None:
    assert isinstance(P22_HISTORICAL_BACKFILL_AVAILABILITY_READY, str)
    assert isinstance(P22_BLOCKED_NO_AVAILABLE_DATES, str)
    assert isinstance(P22_BLOCKED_CONTRACT_VIOLATION, str)
    assert isinstance(P22_FAIL_INPUT_MISSING, str)
    assert isinstance(P22_FAIL_NON_DETERMINISTIC, str)


def test_gate_constant_values_unique() -> None:
    gates = [
        P22_HISTORICAL_BACKFILL_AVAILABILITY_READY,
        P22_BLOCKED_NO_AVAILABLE_DATES,
        P22_BLOCKED_CONTRACT_VIOLATION,
        P22_FAIL_INPUT_MISSING,
        P22_FAIL_NON_DETERMINISTIC,
    ]
    assert len(set(gates)) == len(gates)


def test_date_status_constants_are_strings() -> None:
    statuses = [
        DATE_READY_P20_EXISTS,
        DATE_READY_REPLAYABLE_FROM_P15_P16_P19,
        DATE_PARTIAL_SOURCE_AVAILABLE,
        DATE_MISSING_REQUIRED_SOURCE,
        DATE_BLOCKED_INVALID_ARTIFACTS,
        DATE_BLOCKED_UNSAFE_IDENTITY,
        DATE_UNKNOWN,
    ]
    for s in statuses:
        assert isinstance(s, str)


def test_date_status_constants_unique() -> None:
    statuses = [
        DATE_READY_P20_EXISTS,
        DATE_READY_REPLAYABLE_FROM_P15_P16_P19,
        DATE_PARTIAL_SOURCE_AVAILABLE,
        DATE_MISSING_REQUIRED_SOURCE,
        DATE_BLOCKED_INVALID_ARTIFACTS,
        DATE_BLOCKED_UNSAFE_IDENTITY,
        DATE_UNKNOWN,
    ]
    assert len(set(statuses)) == len(statuses)


def test_phase_artifact_key_constants_present() -> None:
    keys = [
        P15_JOINED_OOF_WITH_ODDS,
        P15_SIMULATION_LEDGER,
        P16_6_RECOMMENDATION_ROWS,
        P16_6_RECOMMENDATION_SUMMARY,
        P19_ENRICHED_LEDGER,
        P19_GATE_RESULT,
        P17_REPLAY_LEDGER,
        P17_REPLAY_SUMMARY,
        P20_DAILY_SUMMARY,
        P20_GATE_RESULT,
    ]
    assert len(keys) == 10
    assert all(isinstance(k, str) for k in keys)


# ---------------------------------------------------------------------------
# P22PhaseArtifactStatus
# ---------------------------------------------------------------------------


def test_phase_artifact_status_default_fields() -> None:
    s = P22PhaseArtifactStatus(
        artifact_key=P15_JOINED_OOF_WITH_ODDS,
        expected_path="p15/joined.csv",
        exists=True,
    )
    assert s.exists is True
    assert s.readable is False
    assert s.size_bytes == 0
    assert s.error_message == ""


def test_phase_artifact_status_frozen() -> None:
    s = P22PhaseArtifactStatus(
        artifact_key="KEY",
        expected_path="path",
        exists=False,
    )
    with pytest.raises((AttributeError, TypeError)):
        s.exists = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P22DateAvailabilityResult
# ---------------------------------------------------------------------------


def test_date_availability_result_defaults() -> None:
    r = P22DateAvailabilityResult(
        run_date="2026-05-12",
        availability_status=DATE_READY_P20_EXISTS,
    )
    assert r.paper_only is True
    assert r.production_ready is False
    assert r.phase_statuses == ()


def test_date_availability_result_rejects_production_ready() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        P22DateAvailabilityResult(
            run_date="2026-05-12",
            availability_status=DATE_READY_P20_EXISTS,
            production_ready=True,
        )


def test_date_availability_result_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        P22DateAvailabilityResult(
            run_date="2026-05-12",
            availability_status=DATE_READY_P20_EXISTS,
            paper_only=False,
        )


def test_date_availability_result_frozen() -> None:
    r = P22DateAvailabilityResult(
        run_date="2026-05-12",
        availability_status=DATE_MISSING_REQUIRED_SOURCE,
    )
    with pytest.raises((AttributeError, TypeError)):
        r.run_date = "2026-05-13"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P22HistoricalAvailabilitySummary
# ---------------------------------------------------------------------------


def _make_summary(**kwargs) -> P22HistoricalAvailabilitySummary:
    defaults = dict(
        date_start="2026-05-01",
        date_end="2026-05-12",
        n_dates_scanned=12,
        n_dates_p20_ready=1,
        n_dates_replayable=0,
        n_dates_partial=2,
        n_dates_missing=9,
        n_dates_blocked=0,
        n_backfill_candidate_dates=1,
        p22_gate=P22_HISTORICAL_BACKFILL_AVAILABILITY_READY,
    )
    defaults.update(kwargs)
    return P22HistoricalAvailabilitySummary(**defaults)


def test_summary_defaults() -> None:
    s = _make_summary()
    assert s.paper_only is True
    assert s.production_ready is False
    assert s.backfill_candidate_dates == ()
    assert s.missing_dates == ()


def test_summary_rejects_production_ready() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        _make_summary(production_ready=True)


def test_summary_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        _make_summary(paper_only=False)


def test_summary_frozen() -> None:
    s = _make_summary()
    with pytest.raises((AttributeError, TypeError)):
        s.n_dates_scanned = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P22BackfillExecutionPlan
# ---------------------------------------------------------------------------


def _make_plan(**kwargs) -> P22BackfillExecutionPlan:
    defaults = dict(date_start="2026-05-01", date_end="2026-05-12")
    defaults.update(kwargs)
    return P22BackfillExecutionPlan(**defaults)


def test_plan_defaults() -> None:
    p = _make_plan()
    assert p.paper_only is True
    assert p.production_ready is False
    assert p.dates_to_skip_already_ready == ()
    assert p.recommended_commands == ()


def test_plan_rejects_production_ready() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        _make_plan(production_ready=True)


def test_plan_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        _make_plan(paper_only=False)


def test_plan_frozen() -> None:
    p = _make_plan()
    with pytest.raises((AttributeError, TypeError)):
        p.date_start = "X"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P22GateResult
# ---------------------------------------------------------------------------


def _make_gate(**kwargs) -> P22GateResult:
    defaults = dict(
        p22_gate=P22_HISTORICAL_BACKFILL_AVAILABILITY_READY,
        date_start="2026-05-12",
        date_end="2026-05-12",
        n_dates_scanned=1,
        n_dates_p20_ready=1,
        n_dates_replayable=0,
        n_dates_partial=0,
        n_dates_missing=0,
        n_dates_blocked=0,
        n_backfill_candidate_dates=1,
        recommended_next_action="All 1 date(s) are P20-ready.",
    )
    defaults.update(kwargs)
    return P22GateResult(**defaults)


def test_gate_result_defaults() -> None:
    g = _make_gate()
    assert g.paper_only is True
    assert g.production_ready is False
    assert g.generated_at == ""


def test_gate_result_rejects_production_ready() -> None:
    with pytest.raises(ValueError, match="production_ready"):
        _make_gate(production_ready=True)


def test_gate_result_rejects_paper_only_false() -> None:
    with pytest.raises(ValueError, match="paper_only"):
        _make_gate(paper_only=False)


def test_gate_result_frozen() -> None:
    g = _make_gate()
    with pytest.raises((AttributeError, TypeError)):
        g.p22_gate = "X"  # type: ignore[misc]
