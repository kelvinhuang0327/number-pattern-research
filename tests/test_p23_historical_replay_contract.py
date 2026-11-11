"""
tests/test_p23_historical_replay_contract.py

Unit tests for P23 historical replay contract dataclasses.
All frozen dataclasses must enforce paper_only=True and production_ready=False.
"""
from __future__ import annotations

import pytest

from wbc_backend.recommendation.p23_historical_replay_contract import (
    P23_DATE_ALREADY_READY,
    P23_DATE_BLOCKED_P15_BUILD_FAILED,
    P23_DATE_BLOCKED_P16_6_FAILED,
    P23_DATE_BLOCKED_P17_REPLAY_FAILED,
    P23_DATE_BLOCKED_P19_FAILED,
    P23_DATE_BLOCKED_P20_FAILED,
    P23_DATE_BLOCKED_SOURCE_NOT_READY,
    P23_DATE_REPLAY_READY,
    P23_HISTORICAL_REPLAY_BACKFILL_READY,
    P23_BLOCKED_ALL_DATES_FAILED,
    P23_BLOCKED_NO_READY_DATES,
    P23_FAIL_INPUT_MISSING,
    P23ReplayAggregateSummary,
    P23ReplayArtifactManifest,
    P23ReplayDateResult,
    P23ReplayDateTask,
    P23ReplayGateResult,
)


# ---------------------------------------------------------------------------
# Gate constant existence
# ---------------------------------------------------------------------------

class TestGateConstants:
    def test_date_level_gates_exist(self):
        assert P23_DATE_REPLAY_READY == "P23_DATE_REPLAY_READY"
        assert P23_DATE_ALREADY_READY == "P23_DATE_ALREADY_READY"
        assert P23_DATE_BLOCKED_SOURCE_NOT_READY == "P23_DATE_BLOCKED_SOURCE_NOT_READY"
        assert P23_DATE_BLOCKED_P15_BUILD_FAILED == "P23_DATE_BLOCKED_P15_BUILD_FAILED"
        assert P23_DATE_BLOCKED_P16_6_FAILED == "P23_DATE_BLOCKED_P16_6_FAILED"
        assert P23_DATE_BLOCKED_P19_FAILED == "P23_DATE_BLOCKED_P19_FAILED"
        assert P23_DATE_BLOCKED_P17_REPLAY_FAILED == "P23_DATE_BLOCKED_P17_REPLAY_FAILED"
        assert P23_DATE_BLOCKED_P20_FAILED == "P23_DATE_BLOCKED_P20_FAILED"

    def test_aggregate_gates_exist(self):
        assert P23_HISTORICAL_REPLAY_BACKFILL_READY == "P23_HISTORICAL_REPLAY_BACKFILL_READY"
        assert P23_BLOCKED_ALL_DATES_FAILED == "P23_BLOCKED_ALL_DATES_FAILED"
        assert P23_BLOCKED_NO_READY_DATES == "P23_BLOCKED_NO_READY_DATES"
        assert P23_FAIL_INPUT_MISSING == "P23_FAIL_INPUT_MISSING"


# ---------------------------------------------------------------------------
# P23ReplayDateTask
# ---------------------------------------------------------------------------

class TestP23ReplayDateTask:
    def test_valid_task_created(self):
        task = P23ReplayDateTask(
            run_date="2026-05-01",
            p22_5_source_ready=True,
            paper_only=True,
            production_ready=False,
        )
        assert task.run_date == "2026-05-01"
        assert task.paper_only is True
        assert task.production_ready is False

    def test_rejects_paper_only_false(self):
        with pytest.raises(ValueError, match="paper_only"):
            P23ReplayDateTask(
                run_date="2026-05-01",
                p22_5_source_ready=True,
                paper_only=False,
                production_ready=False,
            )

    def test_rejects_production_ready_true(self):
        with pytest.raises(ValueError, match="production_ready"):
            P23ReplayDateTask(
                run_date="2026-05-01",
                p22_5_source_ready=True,
                paper_only=True,
                production_ready=True,
            )

    def test_is_frozen(self):
        task = P23ReplayDateTask(
            run_date="2026-05-01",
            p22_5_source_ready=True,
        )
        with pytest.raises(Exception):
            task.run_date = "2026-05-02"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P23ReplayDateResult
# ---------------------------------------------------------------------------

def _make_date_result(**kwargs) -> P23ReplayDateResult:
    defaults = dict(
        run_date="2026-05-01",
        source_ready=True,
        p15_preview_ready=True,
        p16_6_gate="P16_6_PAPER_RECOMMENDATION_GATE_READY",
        p19_gate="P19_ODDS_IDENTITY_JOIN_REPAIRED",
        p17_replay_gate="P17_PAPER_LEDGER_READY",
        p20_gate="P20_DAILY_PAPER_ORCHESTRATOR_READY",
        date_gate=P23_DATE_REPLAY_READY,
        n_recommended_rows=324,
        n_active_paper_entries=324,
        n_settled_win=171,
        n_settled_loss=153,
        n_unsettled=0,
        total_stake_units=81.0,
        total_pnl_units=8.73,
        roi_units=0.1078,
        hit_rate=0.5278,
        game_id_coverage=1.0,
        settlement_join_method="JOIN_BY_GAME_ID",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(kwargs)
    return P23ReplayDateResult(**defaults)


class TestP23ReplayDateResult:
    def test_valid_result_created(self):
        r = _make_date_result()
        assert r.run_date == "2026-05-01"
        assert r.date_gate == P23_DATE_REPLAY_READY
        assert r.paper_only is True
        assert r.production_ready is False

    def test_rejects_paper_only_false(self):
        with pytest.raises(ValueError, match="paper_only"):
            _make_date_result(paper_only=False)

    def test_rejects_production_ready_true(self):
        with pytest.raises(ValueError, match="production_ready"):
            _make_date_result(production_ready=True)

    def test_is_frozen(self):
        r = _make_date_result()
        with pytest.raises(Exception):
            r.roi_units = 99.0  # type: ignore[misc]

    def test_blocked_result_with_reason(self):
        r = _make_date_result(
            date_gate=P23_DATE_BLOCKED_P16_6_FAILED,
            blocker_reason="P16.6 failed: missing gate",
        )
        assert r.date_gate == P23_DATE_BLOCKED_P16_6_FAILED
        assert "P16.6" in r.blocker_reason


# ---------------------------------------------------------------------------
# P23ReplayAggregateSummary
# ---------------------------------------------------------------------------

def _make_aggregate(**kwargs) -> P23ReplayAggregateSummary:
    defaults = dict(
        date_start="2026-05-01",
        date_end="2026-05-12",
        n_dates_requested=12,
        n_dates_attempted=12,
        n_dates_ready=12,
        n_dates_blocked=0,
        total_active_entries=3888,
        total_settled_win=2052,
        total_settled_loss=1836,
        total_unsettled=0,
        total_stake_units=972.0,
        total_pnl_units=104.76,
        aggregate_roi_units=0.1078,
        aggregate_hit_rate=0.5278,
        min_game_id_coverage=1.0,
        p23_gate=P23_HISTORICAL_REPLAY_BACKFILL_READY,
        paper_only=True,
        production_ready=False,
    )
    defaults.update(kwargs)
    return P23ReplayAggregateSummary(**defaults)


class TestP23ReplayAggregateSummary:
    def test_valid_summary_created(self):
        s = _make_aggregate()
        assert s.n_dates_ready == 12
        assert s.paper_only is True
        assert s.production_ready is False

    def test_rejects_paper_only_false(self):
        with pytest.raises(ValueError, match="paper_only"):
            _make_aggregate(paper_only=False)

    def test_rejects_production_ready_true(self):
        with pytest.raises(ValueError, match="production_ready"):
            _make_aggregate(production_ready=True)

    def test_is_frozen(self):
        s = _make_aggregate()
        with pytest.raises(Exception):
            s.n_dates_ready = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P23ReplayGateResult
# ---------------------------------------------------------------------------

class TestP23ReplayGateResult:
    def test_valid_gate_result_created(self):
        gr = P23ReplayGateResult(
            p23_gate=P23_HISTORICAL_REPLAY_BACKFILL_READY,
            date_start="2026-05-01",
            date_end="2026-05-12",
            n_dates_requested=12,
            n_dates_attempted=12,
            n_dates_ready=12,
            n_dates_blocked=0,
            total_active_entries=3888,
            total_settled_win=2052,
            total_settled_loss=1836,
            total_unsettled=0,
            total_stake_units=972.0,
            total_pnl_units=104.76,
            aggregate_roi_units=0.1078,
            aggregate_hit_rate=0.5278,
            min_game_id_coverage=1.0,
            recommended_next_action="Proceed to P24",
            paper_only=True,
            production_ready=False,
            generated_at="2026-05-12T00:00:00+00:00",
        )
        assert gr.p23_gate == P23_HISTORICAL_REPLAY_BACKFILL_READY
        assert gr.paper_only is True
        assert gr.production_ready is False

    def test_rejects_paper_only_false(self):
        with pytest.raises(ValueError):
            P23ReplayGateResult(
                p23_gate=P23_HISTORICAL_REPLAY_BACKFILL_READY,
                date_start="2026-05-01",
                date_end="2026-05-12",
                n_dates_requested=12,
                n_dates_attempted=12,
                n_dates_ready=12,
                n_dates_blocked=0,
                total_active_entries=0,
                total_settled_win=0,
                total_settled_loss=0,
                total_unsettled=0,
                total_stake_units=0.0,
                total_pnl_units=0.0,
                aggregate_roi_units=0.0,
                aggregate_hit_rate=0.0,
                min_game_id_coverage=0.0,
                recommended_next_action="",
                paper_only=False,
                production_ready=False,
            )


# ---------------------------------------------------------------------------
# P23ReplayArtifactManifest
# ---------------------------------------------------------------------------

class TestP23ReplayArtifactManifest:
    def test_valid_manifest_created(self):
        m = P23ReplayArtifactManifest(
            date_start="2026-05-01",
            date_end="2026-05-12",
            n_dates_in_manifest=12,
            paper_only=True,
            production_ready=False,
        )
        assert m.n_dates_in_manifest == 12
        assert m.paper_only is True

    def test_rejects_production_ready_true(self):
        with pytest.raises(ValueError):
            P23ReplayArtifactManifest(
                date_start="2026-05-01",
                date_end="2026-05-12",
                n_dates_in_manifest=12,
                paper_only=True,
                production_ready=True,
            )
