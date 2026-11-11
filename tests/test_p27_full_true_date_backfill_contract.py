"""
tests/test_p27_full_true_date_backfill_contract.py

Unit tests for p27_full_true_date_backfill_contract.py.
"""
import pytest

from wbc_backend.recommendation.p27_full_true_date_backfill_contract import (
    MIN_SAMPLE_SIZE_ADVISORY,
    P27_BLOCKED_CONTRACT_VIOLATION,
    P27_BLOCKED_INSUFFICIENT_SAMPLE_SIZE,
    P27_BLOCKED_P25_FULL_RANGE_NOT_READY,
    P27_BLOCKED_P26_REPLAY_FAILED,
    P27_BLOCKED_RUNTIME_GUARD,
    P27_FAIL_INPUT_MISSING,
    P27_FAIL_NON_DETERMINISTIC,
    P27_FULL_TRUE_DATE_BACKFILL_READY,
    P27ExpansionSegment,
    P27ExpansionDateResult,
    P27FullBackfillSummary,
    P27FullBackfillGateResult,
    P27RuntimeGuardResult,
    _VALID_AGGREGATE_GATES,
)


class TestGateConstants:
    def test_all_gates_unique(self):
        gates = [
            P27_FULL_TRUE_DATE_BACKFILL_READY,
            P27_BLOCKED_P25_FULL_RANGE_NOT_READY,
            P27_BLOCKED_P26_REPLAY_FAILED,
            P27_BLOCKED_INSUFFICIENT_SAMPLE_SIZE,
            P27_BLOCKED_RUNTIME_GUARD,
            P27_BLOCKED_CONTRACT_VIOLATION,
            P27_FAIL_INPUT_MISSING,
            P27_FAIL_NON_DETERMINISTIC,
        ]
        assert len(gates) == len(set(gates)), "Duplicate gate constants detected"

    def test_valid_gates_frozenset_complete(self):
        assert P27_FULL_TRUE_DATE_BACKFILL_READY in _VALID_AGGREGATE_GATES
        assert P27_FAIL_INPUT_MISSING in _VALID_AGGREGATE_GATES
        assert P27_BLOCKED_RUNTIME_GUARD in _VALID_AGGREGATE_GATES

    def test_min_sample_size_advisory(self):
        assert MIN_SAMPLE_SIZE_ADVISORY == 1500


class TestP27ExpansionSegment:
    def test_valid_segment(self):
        seg = P27ExpansionSegment(
            segment_index=0,
            date_start="2025-05-08",
            date_end="2025-05-21",
            date_count=14,
            p25_output_dir="/tmp/p25",
            p26_output_dir="/tmp/p26",
        )
        assert seg.date_count == 14

    def test_date_count_less_than_one_raises(self):
        with pytest.raises(ValueError, match="date_count"):
            P27ExpansionSegment(
                segment_index=0,
                date_start="2025-05-08",
                date_end="2025-05-08",
                date_count=0,
                p25_output_dir="/tmp/p25",
                p26_output_dir="/tmp/p26",
            )

    def test_start_after_end_raises(self):
        with pytest.raises(ValueError, match="date_start"):
            P27ExpansionSegment(
                segment_index=0,
                date_start="2025-05-10",
                date_end="2025-05-08",
                date_count=1,
                p25_output_dir="/tmp/p25",
                p26_output_dir="/tmp/p26",
            )

    def test_frozen(self):
        seg = P27ExpansionSegment(
            segment_index=0,
            date_start="2025-05-08",
            date_end="2025-05-21",
            date_count=14,
            p25_output_dir="/tmp/p25",
            p26_output_dir="/tmp/p26",
        )
        with pytest.raises(Exception):
            seg.segment_index = 99  # type: ignore[misc]


class TestP27ExpansionDateResult:
    def _make(self, paper_only=True, production_ready=False):
        return P27ExpansionDateResult(
            run_date="2025-05-08",
            segment_index=0,
            replay_gate="P26_DATE_REPLAY_READY",
            n_active_paper_entries=3,
            n_settled_win=2,
            n_settled_loss=1,
            n_unsettled=0,
            total_stake_units=0.75,
            total_pnl_units=0.10,
            hit_rate=0.67,
            paper_only=paper_only,
            production_ready=production_ready,
            blocker_reason="",
        )

    def test_valid(self):
        r = self._make()
        assert r.paper_only is True

    def test_rejects_production_ready_true(self):
        with pytest.raises(ValueError, match="production_ready"):
            self._make(production_ready=True)

    def test_rejects_paper_only_false(self):
        with pytest.raises(ValueError, match="paper_only"):
            self._make(paper_only=False)


class TestP27FullBackfillSummary:
    def _make(self, paper_only=True, production_ready=False):
        return P27FullBackfillSummary(
            date_start="2025-05-08",
            date_end="2025-05-21",
            n_segments=1,
            n_dates_requested=14,
            n_dates_ready=12,
            n_dates_empty=2,
            n_dates_blocked=0,
            total_active_entries=30,
            total_settled_win=15,
            total_settled_loss=10,
            total_unsettled=5,
            total_stake_units=7.5,
            total_pnl_units=0.5,
            aggregate_roi_units=0.0667,
            aggregate_hit_rate=0.6,
            min_game_id_coverage=0.9,
            max_runtime_seconds=10.0,
            blocked_segment_list=(),
            blocked_date_list=(),
            source_p25_base_dir="/tmp/p25",
            paper_only=paper_only,
            production_ready=production_ready,
            blocker_reason="",
        )

    def test_valid(self):
        s = self._make()
        assert s.n_segments == 1

    def test_rejects_production_ready_true(self):
        with pytest.raises(ValueError, match="production_ready"):
            self._make(production_ready=True)

    def test_rejects_paper_only_false(self):
        with pytest.raises(ValueError, match="paper_only"):
            self._make(paper_only=False)

    def test_frozen(self):
        s = self._make()
        with pytest.raises(Exception):
            s.n_segments = 99  # type: ignore[misc]


class TestP27FullBackfillGateResult:
    def _make(self, p27_gate=P27_FULL_TRUE_DATE_BACKFILL_READY,
              paper_only=True, production_ready=False):
        return P27FullBackfillGateResult(
            p27_gate=p27_gate,
            date_start="2025-05-08",
            date_end="2025-05-21",
            n_segments=1,
            n_dates_requested=14,
            n_dates_ready=12,
            n_dates_empty=2,
            n_dates_blocked=0,
            total_active_entries=30,
            total_settled_win=15,
            total_settled_loss=10,
            total_unsettled=5,
            total_stake_units=7.5,
            total_pnl_units=0.5,
            aggregate_roi_units=0.0667,
            aggregate_hit_rate=0.6,
            max_runtime_seconds=10.0,
            paper_only=paper_only,
            production_ready=production_ready,
            blocker_reason="",
            generated_at="2026-05-12T00:00:00+00:00",
        )

    def test_valid_gate(self):
        g = self._make()
        assert g.p27_gate == P27_FULL_TRUE_DATE_BACKFILL_READY

    def test_invalid_gate_raises(self):
        with pytest.raises(ValueError, match="invalid p27_gate"):
            self._make(p27_gate="TOTALLY_FAKE_GATE")

    def test_rejects_production_ready_true(self):
        with pytest.raises(ValueError, match="production_ready"):
            self._make(production_ready=True)

    def test_rejects_paper_only_false(self):
        with pytest.raises(ValueError, match="paper_only"):
            self._make(paper_only=False)


class TestP27RuntimeGuardResult:
    def test_valid(self):
        g = P27RuntimeGuardResult(
            max_runtime_seconds=180.0,
            actual_runtime_seconds=45.0,
            guard_triggered=False,
            guard_reason="",
            paper_only=True,
            production_ready=False,
        )
        assert g.guard_triggered is False

    def test_rejects_production_ready_true(self):
        with pytest.raises(ValueError, match="production_ready"):
            P27RuntimeGuardResult(
                max_runtime_seconds=180.0,
                actual_runtime_seconds=45.0,
                guard_triggered=False,
                guard_reason="",
                paper_only=True,
                production_ready=True,
            )

    def test_rejects_paper_only_false(self):
        with pytest.raises(ValueError, match="paper_only"):
            P27RuntimeGuardResult(
                max_runtime_seconds=180.0,
                actual_runtime_seconds=45.0,
                guard_triggered=False,
                guard_reason="",
                paper_only=False,
                production_ready=False,
            )
