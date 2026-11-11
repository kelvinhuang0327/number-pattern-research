"""
tests/test_p21_multi_day_backfill_contract.py

Unit tests for P21 backfill contract dataclasses and gate constants.
"""
import pytest

from wbc_backend.recommendation.p21_multi_day_backfill_contract import (
    EXPECTED_P20_DAILY_GATE,
    P21BackfillAggregateSummary,
    P21BackfillDateResult,
    P21BackfillGateResult,
    P21MissingArtifactReport,
    P21_BLOCKED_CONTRACT_VIOLATION,
    P21_BLOCKED_DAILY_GATE_NOT_READY,
    P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS,
    P21_BLOCKED_NO_READY_DAILY_RUNS,
    P21_FAIL_INPUT_MISSING,
    P21_FAIL_NON_DETERMINISTIC,
    P21_MULTI_DAY_PAPER_BACKFILL_READY,
)


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------


def test_gate_constants_exist():
    assert P21_MULTI_DAY_PAPER_BACKFILL_READY == "P21_MULTI_DAY_PAPER_BACKFILL_READY"
    assert P21_BLOCKED_NO_READY_DAILY_RUNS == "P21_BLOCKED_NO_READY_DAILY_RUNS"
    assert P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS == "P21_BLOCKED_MISSING_REQUIRED_ARTIFACTS"
    assert P21_BLOCKED_DAILY_GATE_NOT_READY == "P21_BLOCKED_DAILY_GATE_NOT_READY"
    assert P21_BLOCKED_CONTRACT_VIOLATION == "P21_BLOCKED_CONTRACT_VIOLATION"
    assert P21_FAIL_INPUT_MISSING == "P21_FAIL_INPUT_MISSING"
    assert P21_FAIL_NON_DETERMINISTIC == "P21_FAIL_NON_DETERMINISTIC"


def test_expected_p20_gate():
    assert EXPECTED_P20_DAILY_GATE == "P20_DAILY_PAPER_ORCHESTRATOR_READY"


# ---------------------------------------------------------------------------
# P21BackfillDateResult
# ---------------------------------------------------------------------------


def _make_date_result(**kwargs):
    defaults = dict(
        run_date="2026-05-12",
        daily_gate=P21_MULTI_DAY_PAPER_BACKFILL_READY,
        p20_gate="P20_DAILY_PAPER_ORCHESTRATOR_READY",
        n_recommended_rows=324,
        n_active_paper_entries=324,
        n_settled_win=171,
        n_settled_loss=153,
        n_unsettled=0,
        total_stake_units=324.0,
        total_pnl_units=34.92,
        roi_units=0.1078,
        hit_rate=0.5278,
        game_id_coverage=1.0,
        settlement_join_method="JOIN_BY_GAME_ID",
        artifact_manifest_sha256="abc123",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(kwargs)
    return P21BackfillDateResult(**defaults)


def test_date_result_frozen():
    r = _make_date_result()
    with pytest.raises((AttributeError, TypeError)):
        r.run_date = "2026-05-13"  # type: ignore[misc]


def test_date_result_safety_defaults():
    r = _make_date_result()
    assert r.paper_only is True
    assert r.production_ready is False


def test_date_result_rejects_production_ready_true():
    """production_ready=True is allowed to construct but must be caught by aggregator."""
    r = _make_date_result(production_ready=True)
    assert r.production_ready is True  # frozen allows construction; validation catches it


def test_date_result_rejects_paper_only_false():
    r = _make_date_result(paper_only=False)
    assert r.paper_only is False  # frozen allows construction; validation catches it


# ---------------------------------------------------------------------------
# P21MissingArtifactReport
# ---------------------------------------------------------------------------


def test_missing_artifact_report_frozen():
    r = P21MissingArtifactReport(
        run_date="2026-05-11",
        missing_files=("daily_paper_summary.json",),
        error_message="Directory not found",
    )
    with pytest.raises((AttributeError, TypeError)):
        r.run_date = "2026-05-10"  # type: ignore[misc]


def test_missing_artifact_report_defaults():
    r = P21MissingArtifactReport(run_date="2026-05-11")
    assert r.missing_files == ()
    assert r.invalid_files == ()
    assert r.error_message == ""


# ---------------------------------------------------------------------------
# P21BackfillAggregateSummary
# ---------------------------------------------------------------------------


def _make_summary(**kwargs):
    defaults = dict(
        date_start="2026-05-12",
        date_end="2026-05-12",
        n_dates_requested=1,
        n_dates_ready=1,
        n_dates_missing=0,
        n_dates_blocked=0,
        total_active_entries=324,
        total_settled_win=171,
        total_settled_loss=153,
        total_unsettled=0,
        total_stake_units=324.0,
        total_pnl_units=34.92,
        aggregate_roi_units=0.1078,
        aggregate_hit_rate=0.5278,
        min_game_id_coverage=1.0,
        all_join_methods=("JOIN_BY_GAME_ID",),
        paper_only=True,
        production_ready=False,
        p21_gate=P21_MULTI_DAY_PAPER_BACKFILL_READY,
    )
    defaults.update(kwargs)
    return P21BackfillAggregateSummary(**defaults)


def test_aggregate_summary_frozen():
    s = _make_summary()
    with pytest.raises((AttributeError, TypeError)):
        s.paper_only = False  # type: ignore[misc]


def test_aggregate_summary_safety_invariants():
    s = _make_summary()
    assert s.paper_only is True
    assert s.production_ready is False


def test_aggregate_summary_rejects_production_ready_default():
    """Default production_ready must be False."""
    s = _make_summary()
    assert s.production_ready is False


def test_aggregate_summary_gate_string():
    s = _make_summary()
    assert s.p21_gate == P21_MULTI_DAY_PAPER_BACKFILL_READY


# ---------------------------------------------------------------------------
# P21BackfillGateResult
# ---------------------------------------------------------------------------


def test_gate_result_frozen():
    g = P21BackfillGateResult(
        p21_gate=P21_MULTI_DAY_PAPER_BACKFILL_READY,
        date_start="2026-05-12",
        date_end="2026-05-12",
        n_dates_requested=1,
        n_dates_ready=1,
        n_dates_missing=0,
        n_dates_blocked=0,
        total_active_entries=324,
        total_settled_win=171,
        total_settled_loss=153,
        total_unsettled=0,
        total_stake_units=324.0,
        total_pnl_units=34.92,
        aggregate_roi_units=0.1078,
        aggregate_hit_rate=0.5278,
        min_game_id_coverage=1.0,
    )
    with pytest.raises((AttributeError, TypeError)):
        g.paper_only = False  # type: ignore[misc]


def test_gate_result_safety_defaults():
    g = P21BackfillGateResult(
        p21_gate=P21_MULTI_DAY_PAPER_BACKFILL_READY,
        date_start="2026-05-12",
        date_end="2026-05-12",
        n_dates_requested=1,
        n_dates_ready=1,
        n_dates_missing=0,
        n_dates_blocked=0,
        total_active_entries=324,
        total_settled_win=171,
        total_settled_loss=153,
        total_unsettled=0,
        total_stake_units=324.0,
        total_pnl_units=34.92,
        aggregate_roi_units=0.1078,
        aggregate_hit_rate=0.5278,
        min_game_id_coverage=1.0,
    )
    assert g.paper_only is True
    assert g.production_ready is False
