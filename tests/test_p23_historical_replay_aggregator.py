"""
tests/test_p23_historical_replay_aggregator.py

Unit tests for P23 historical replay aggregator.

Key coverage:
- weighted ROI = total_pnl / total_stake
- weighted hit_rate = total_win / (total_win + total_loss)
- blocked dates are counted and reported
- gate = READY if ≥1 date ready, BLOCKED if none
"""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from wbc_backend.recommendation.p23_historical_replay_contract import (
    P23_BLOCKED_ALL_DATES_FAILED,
    P23_BLOCKED_NO_READY_DATES,
    P23_DATE_ALREADY_READY,
    P23_DATE_BLOCKED_P16_6_FAILED,
    P23_DATE_BLOCKED_SOURCE_NOT_READY,
    P23_DATE_REPLAY_READY,
    P23_HISTORICAL_REPLAY_BACKFILL_READY,
    P23ReplayDateResult,
)
from wbc_backend.recommendation.p23_historical_replay_aggregator import (
    aggregate_replay_results,
    build_gate_result,
    validate_aggregate_summary,
    write_replay_outputs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ready_result(
    run_date: str,
    n_win: int = 171,
    n_loss: int = 153,
    n_active: int = 324,
    stake: float = 81.0,
    pnl: float = 8.73,
    game_id_coverage: float = 1.0,
    date_gate: str = P23_DATE_REPLAY_READY,
) -> P23ReplayDateResult:
    roi = pnl / stake if stake > 0 else 0.0
    settled = n_win + n_loss
    hit_rate = n_win / settled if settled > 0 else 0.0
    return P23ReplayDateResult(
        run_date=run_date,
        source_ready=True,
        p15_preview_ready=True,
        p16_6_gate="P16_6_PAPER_RECOMMENDATION_GATE_READY",
        p19_gate="P19_ODDS_IDENTITY_JOIN_REPAIRED",
        p17_replay_gate="P17_PAPER_LEDGER_READY",
        p20_gate="P20_DAILY_PAPER_ORCHESTRATOR_READY",
        date_gate=date_gate,
        n_recommended_rows=n_active,
        n_active_paper_entries=n_active,
        n_settled_win=n_win,
        n_settled_loss=n_loss,
        n_unsettled=0,
        total_stake_units=stake,
        total_pnl_units=pnl,
        roi_units=roi,
        hit_rate=hit_rate,
        game_id_coverage=game_id_coverage,
        settlement_join_method="JOIN_BY_GAME_ID",
        paper_only=True,
        production_ready=False,
    )


def _make_blocked_result(
    run_date: str,
    date_gate: str = P23_DATE_BLOCKED_SOURCE_NOT_READY,
) -> P23ReplayDateResult:
    return P23ReplayDateResult(
        run_date=run_date,
        source_ready=False,
        p15_preview_ready=False,
        p16_6_gate="",
        p19_gate="",
        p17_replay_gate="",
        p20_gate="",
        date_gate=date_gate,
        n_recommended_rows=0,
        n_active_paper_entries=0,
        n_settled_win=0,
        n_settled_loss=0,
        n_unsettled=0,
        total_stake_units=0.0,
        total_pnl_units=0.0,
        roi_units=0.0,
        hit_rate=0.0,
        game_id_coverage=0.0,
        settlement_join_method="",
        blocker_reason=f"Blocked at {date_gate}",
        paper_only=True,
        production_ready=False,
    )


# ---------------------------------------------------------------------------
# aggregate_replay_results — weighted ROI
# ---------------------------------------------------------------------------

class TestAggregateROI:
    def test_weighted_roi_is_total_pnl_over_total_stake(self):
        """ROI must be total_pnl / total_stake, not average of per-date ROIs."""
        r1 = _make_ready_result("2026-05-01", stake=100.0, pnl=10.0)   # ROI = 10%
        r2 = _make_ready_result("2026-05-02", stake=50.0, pnl=2.5)     # ROI = 5%
        # Weighted ROI = 12.5 / 150 = 8.333...%, not (10+5)/2 = 7.5%

        summary = aggregate_replay_results(
            date_results=[r1, r2],
            date_start="2026-05-01",
            date_end="2026-05-02",
            n_dates_requested=2,
        )

        expected_roi = 12.5 / 150.0
        assert abs(summary.aggregate_roi_units - expected_roi) < 1e-9
        assert abs(summary.total_stake_units - 150.0) < 1e-9
        assert abs(summary.total_pnl_units - 12.5) < 1e-9

    def test_roi_zero_when_no_stake(self):
        """aggregate_roi should be 0.0 when total_stake_units = 0."""
        r = _make_ready_result("2026-05-01", stake=0.0, pnl=0.0)
        summary = aggregate_replay_results(
            date_results=[r],
            date_start="2026-05-01",
            date_end="2026-05-01",
            n_dates_requested=1,
        )
        assert summary.aggregate_roi_units == 0.0


# ---------------------------------------------------------------------------
# aggregate_replay_results — weighted hit rate
# ---------------------------------------------------------------------------

class TestAggregateHitRate:
    def test_weighted_hit_rate_is_wins_over_settled(self):
        """hit_rate = total_win / (total_win + total_loss), not average."""
        r1 = _make_ready_result("2026-05-01", n_win=80, n_loss=20)   # 80%
        r2 = _make_ready_result("2026-05-02", n_win=10, n_loss=90)   # 10%
        # Weighted: 90/(80+20+10+90) = 90/200 = 45%  (not (80+10)/2 = 45% — coincidence)
        # Let's use r1: 100 win/20 loss = 80%; r2: 10 win/190 loss = 5%
        r2 = _make_ready_result("2026-05-02", n_win=10, n_loss=190)

        summary = aggregate_replay_results(
            date_results=[r1, r2],
            date_start="2026-05-01",
            date_end="2026-05-02",
            n_dates_requested=2,
        )

        expected_hit_rate = (80 + 10) / (80 + 20 + 10 + 190)
        assert abs(summary.aggregate_hit_rate - expected_hit_rate) < 1e-9

    def test_hit_rate_zero_when_no_settled_bets(self):
        r = P23ReplayDateResult(
            run_date="2026-05-01",
            source_ready=True,
            p15_preview_ready=True,
            p16_6_gate="X",
            p19_gate="X",
            p17_replay_gate="X",
            p20_gate="X",
            date_gate=P23_DATE_REPLAY_READY,
            n_recommended_rows=0,
            n_active_paper_entries=0,
            n_settled_win=0,
            n_settled_loss=0,
            n_unsettled=5,
            total_stake_units=10.0,
            total_pnl_units=0.0,
            roi_units=0.0,
            hit_rate=0.0,
            game_id_coverage=1.0,
            settlement_join_method="JOIN_BY_GAME_ID",
            paper_only=True,
            production_ready=False,
        )
        summary = aggregate_replay_results(
            date_results=[r],
            date_start="2026-05-01",
            date_end="2026-05-01",
            n_dates_requested=1,
        )
        assert summary.aggregate_hit_rate == 0.0


# ---------------------------------------------------------------------------
# aggregate_replay_results — blocked dates counted
# ---------------------------------------------------------------------------

class TestAggregateBlockedDates:
    def test_blocked_dates_counted_correctly(self):
        results = [
            _make_ready_result("2026-05-01"),
            _make_blocked_result("2026-05-02"),
            _make_blocked_result("2026-05-03", date_gate=P23_DATE_BLOCKED_P16_6_FAILED),
        ]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-01",
            date_end="2026-05-03",
            n_dates_requested=3,
        )
        assert summary.n_dates_ready == 1
        assert summary.n_dates_blocked == 2
        assert summary.n_dates_attempted == 3

    def test_blocked_dates_do_not_inflate_totals(self):
        """Blocked dates must contribute 0 to stake, pnl, win, loss counts."""
        results = [
            _make_ready_result("2026-05-01", stake=81.0, pnl=8.73, n_win=171, n_loss=153),
            _make_blocked_result("2026-05-02"),
        ]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-01",
            date_end="2026-05-02",
            n_dates_requested=2,
        )
        assert abs(summary.total_stake_units - 81.0) < 1e-9
        assert abs(summary.total_pnl_units - 8.73) < 1e-9
        assert summary.total_settled_win == 171
        assert summary.total_settled_loss == 153


# ---------------------------------------------------------------------------
# aggregate_replay_results — gate decision
# ---------------------------------------------------------------------------

class TestAggregateGateDecision:
    def test_gate_ready_when_at_least_one_date_ready(self):
        results = [
            _make_ready_result("2026-05-12"),
            _make_blocked_result("2026-05-01"),
        ]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-01",
            date_end="2026-05-12",
            n_dates_requested=12,
        )
        assert summary.p23_gate == P23_HISTORICAL_REPLAY_BACKFILL_READY

    def test_gate_blocked_when_no_date_ready(self):
        results = [
            _make_blocked_result("2026-05-01"),
            _make_blocked_result("2026-05-02"),
        ]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-01",
            date_end="2026-05-02",
            n_dates_requested=2,
        )
        assert summary.p23_gate == P23_BLOCKED_ALL_DATES_FAILED

    def test_gate_no_ready_when_empty_results(self):
        summary = aggregate_replay_results(
            date_results=[],
            date_start="2026-05-01",
            date_end="2026-05-01",
            n_dates_requested=1,
        )
        assert summary.p23_gate == P23_BLOCKED_NO_READY_DATES

    def test_already_ready_counts_as_ready(self):
        """ALREADY_READY dates count toward n_dates_ready."""
        results = [
            _make_ready_result("2026-05-12", date_gate=P23_DATE_ALREADY_READY),
        ]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-12",
            date_end="2026-05-12",
            n_dates_requested=1,
        )
        assert summary.n_dates_ready == 1
        assert summary.p23_gate == P23_HISTORICAL_REPLAY_BACKFILL_READY


# ---------------------------------------------------------------------------
# validate_aggregate_summary
# ---------------------------------------------------------------------------

class TestValidateAggregateSummary:
    def test_valid_summary_passes(self):
        results = [_make_ready_result("2026-05-01")]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-01",
            date_end="2026-05-01",
            n_dates_requested=1,
        )
        violations = validate_aggregate_summary(summary)
        assert violations == []


# ---------------------------------------------------------------------------
# write_replay_outputs
# ---------------------------------------------------------------------------

class TestWriteReplayOutputs:
    def test_writes_all_6_output_files(self, tmp_path):
        results = [
            _make_ready_result("2026-05-12"),
            _make_blocked_result("2026-05-01"),
        ]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-01",
            date_end="2026-05-12",
            n_dates_requested=2,
        )
        gate_result = build_gate_result(summary)
        written = write_replay_outputs(
            summary=summary,
            gate_result=gate_result,
            date_results=results,
            output_dir=tmp_path / "p23_out",
        )

        assert len(written) == 6

        required_files = [
            "historical_replay_summary.json",
            "historical_replay_summary.md",
            "date_replay_results.csv",
            "blocked_dates.json",
            "artifact_manifest.json",
            "p23_gate_result.json",
        ]
        out = tmp_path / "p23_out"
        for fname in required_files:
            assert (out / fname).exists(), f"Missing: {fname}"

    def test_gate_result_json_has_correct_gate(self, tmp_path):
        results = [_make_ready_result("2026-05-12")]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-12",
            date_end="2026-05-12",
            n_dates_requested=1,
        )
        gate_result = build_gate_result(summary)
        write_replay_outputs(
            summary=summary,
            gate_result=gate_result,
            date_results=results,
            output_dir=tmp_path / "p23_out",
        )

        gate_data = json.loads((tmp_path / "p23_out" / "p23_gate_result.json").read_text())
        assert gate_data["p23_gate"] == P23_HISTORICAL_REPLAY_BACKFILL_READY
        assert gate_data["paper_only"] is True
        assert gate_data["production_ready"] is False

    def test_blocked_dates_json_lists_blocked(self, tmp_path):
        results = [
            _make_ready_result("2026-05-12"),
            _make_blocked_result("2026-05-01"),
            _make_blocked_result("2026-05-02"),
        ]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-01",
            date_end="2026-05-12",
            n_dates_requested=12,
        )
        gate_result = build_gate_result(summary)
        write_replay_outputs(
            summary=summary,
            gate_result=gate_result,
            date_results=results,
            output_dir=tmp_path / "p23_out",
        )

        blocked_data = json.loads(
            (tmp_path / "p23_out" / "blocked_dates.json").read_text()
        )
        assert blocked_data["n_blocked"] == 2
        blocked_run_dates = [d["run_date"] for d in blocked_data["blocked_dates"]]
        assert "2026-05-01" in blocked_run_dates
        assert "2026-05-02" in blocked_run_dates
        assert "2026-05-12" not in blocked_run_dates

    def test_summary_json_paper_only_true(self, tmp_path):
        results = [_make_ready_result("2026-05-12")]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-12",
            date_end="2026-05-12",
            n_dates_requested=1,
        )
        gate_result = build_gate_result(summary)
        write_replay_outputs(
            summary=summary,
            gate_result=gate_result,
            date_results=results,
            output_dir=tmp_path / "p23_out",
        )
        data = json.loads((tmp_path / "p23_out" / "historical_replay_summary.json").read_text())
        assert data["paper_only"] is True
        assert data["production_ready"] is False


# ---------------------------------------------------------------------------
# build_gate_result
# ---------------------------------------------------------------------------

class TestBuildGateResult:
    def test_gate_result_paper_only_true(self):
        results = [_make_ready_result("2026-05-01")]
        summary = aggregate_replay_results(
            date_results=results,
            date_start="2026-05-01",
            date_end="2026-05-01",
            n_dates_requested=1,
        )
        gate_result = build_gate_result(summary)
        assert gate_result.paper_only is True
        assert gate_result.production_ready is False
        assert gate_result.recommended_next_action != ""
