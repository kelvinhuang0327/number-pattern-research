"""
tests/test_p26_true_date_replay_contract.py

Unit tests for p26_true_date_replay_contract.py.
Verifies all gate constants, frozen dataclass invariants, and validation rules.
"""
import pytest

from wbc_backend.recommendation.p26_true_date_replay_contract import (
    P26_DATE_REPLAY_READY,
    P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
    P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
    P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED,
    P26_DATE_BLOCKED_REPLAY_FAILED,
    P26_DATE_FAIL_CONTRACT_VIOLATION,
    P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,
    P26_BLOCKED_NO_READY_DATES,
    P26_BLOCKED_ALL_DATES_FAILED,
    P26_BLOCKED_CONTRACT_VIOLATION,
    P26_FAIL_INPUT_MISSING,
    P26_FAIL_NON_DETERMINISTIC,
    P26TrueDateReplayTask,
    P26TrueDateReplayResult,
    P26TrueDateReplaySummary,
    P26TrueDateReplayGateResult,
    P26TrueDateReplayManifest,
)


# ---------------------------------------------------------------------------
# Constants smoke tests
# ---------------------------------------------------------------------------


class TestGateConstants:
    def test_per_date_constants_are_strings(self):
        for c in [
            P26_DATE_REPLAY_READY,
            P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
            P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
            P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED,
            P26_DATE_BLOCKED_REPLAY_FAILED,
            P26_DATE_FAIL_CONTRACT_VIOLATION,
        ]:
            assert isinstance(c, str)

    def test_aggregate_constants_are_strings(self):
        for c in [
            P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,
            P26_BLOCKED_NO_READY_DATES,
            P26_BLOCKED_ALL_DATES_FAILED,
            P26_BLOCKED_CONTRACT_VIOLATION,
            P26_FAIL_INPUT_MISSING,
            P26_FAIL_NON_DETERMINISTIC,
        ]:
            assert isinstance(c, str)

    def test_per_date_constants_unique(self):
        constants = [
            P26_DATE_REPLAY_READY,
            P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
            P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
            P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED,
            P26_DATE_BLOCKED_REPLAY_FAILED,
            P26_DATE_FAIL_CONTRACT_VIOLATION,
        ]
        assert len(set(constants)) == len(constants)

    def test_aggregate_constants_unique(self):
        constants = [
            P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,
            P26_BLOCKED_NO_READY_DATES,
            P26_BLOCKED_ALL_DATES_FAILED,
            P26_BLOCKED_CONTRACT_VIOLATION,
            P26_FAIL_INPUT_MISSING,
            P26_FAIL_NON_DETERMINISTIC,
        ]
        assert len(set(constants)) == len(constants)


# ---------------------------------------------------------------------------
# P26TrueDateReplayTask
# ---------------------------------------------------------------------------


class TestP26TrueDateReplayTask:
    def _valid_kwargs(self):
        return dict(
            run_date="2025-05-08",
            p25_slice_path="/tmp/p25/true_date_slices/2025-05-08/p15_true_date_input.csv",
            output_dir="/tmp/out",
            paper_only=True,
            production_ready=False,
        )

    def test_valid_construction(self):
        t = P26TrueDateReplayTask(**self._valid_kwargs())
        assert t.run_date == "2025-05-08"
        assert t.paper_only is True
        assert t.production_ready is False

    def test_paper_only_must_be_true(self):
        kwargs = self._valid_kwargs()
        kwargs["paper_only"] = False
        with pytest.raises(ValueError, match="paper_only must be True"):
            P26TrueDateReplayTask(**kwargs)

    def test_production_ready_must_be_false(self):
        kwargs = self._valid_kwargs()
        kwargs["production_ready"] = True
        with pytest.raises(ValueError, match="production_ready must be False"):
            P26TrueDateReplayTask(**kwargs)

    def test_frozen(self):
        t = P26TrueDateReplayTask(**self._valid_kwargs())
        with pytest.raises((AttributeError, TypeError)):
            t.run_date = "2025-05-09"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# P26TrueDateReplayResult
# ---------------------------------------------------------------------------


class TestP26TrueDateReplayResult:
    def _valid_kwargs(self):
        return dict(
            run_date="2025-05-08",
            true_game_date="2025-05-08",
            true_date_slice_status=P26_DATE_REPLAY_READY,
            n_slice_rows=4,
            n_unique_game_ids=2,
            date_matches_slice=True,
            replay_gate=P26_DATE_REPLAY_READY,
            n_active_paper_entries=1,
            n_settled_win=1,
            n_settled_loss=0,
            n_unsettled=0,
            total_stake_units=0.25,
            total_pnl_units=0.1471,
            roi_units=0.5884,
            hit_rate=1.0,
            game_id_coverage=0.5,
            paper_only=True,
            production_ready=False,
            blocker_reason="",
        )

    def test_valid_construction(self):
        r = P26TrueDateReplayResult(**self._valid_kwargs())
        assert r.replay_gate == P26_DATE_REPLAY_READY

    def test_paper_only_enforced(self):
        kwargs = self._valid_kwargs()
        kwargs["paper_only"] = False
        with pytest.raises(ValueError, match="paper_only must be True"):
            P26TrueDateReplayResult(**kwargs)

    def test_production_ready_enforced(self):
        kwargs = self._valid_kwargs()
        kwargs["production_ready"] = True
        with pytest.raises(ValueError, match="production_ready must be False"):
            P26TrueDateReplayResult(**kwargs)

    def test_invalid_replay_gate_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["replay_gate"] = "INVALID_GATE"
        with pytest.raises(ValueError, match="invalid replay_gate"):
            P26TrueDateReplayResult(**kwargs)

    def test_all_valid_date_gates_accepted(self):
        for gate in [
            P26_DATE_REPLAY_READY,
            P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
            P26_DATE_BLOCKED_INVALID_TRUE_DATE_SLICE,
            P26_DATE_BLOCKED_P15_INPUT_BUILD_FAILED,
            P26_DATE_BLOCKED_REPLAY_FAILED,
            P26_DATE_FAIL_CONTRACT_VIOLATION,
        ]:
            kwargs = self._valid_kwargs()
            kwargs["replay_gate"] = gate
            r = P26TrueDateReplayResult(**kwargs)
            assert r.replay_gate == gate


# ---------------------------------------------------------------------------
# P26TrueDateReplaySummary
# ---------------------------------------------------------------------------


class TestP26TrueDateReplaySummary:
    def _valid_kwargs(self):
        return dict(
            date_start="2025-05-08",
            date_end="2025-05-14",
            n_dates_requested=7,
            n_dates_ready=7,
            n_dates_blocked=0,
            n_dates_failed=0,
            total_active_entries=25,
            total_settled_win=11,
            total_settled_loss=14,
            total_unsettled=0,
            total_stake_units=6.25,
            total_pnl_units=-0.5506,
            aggregate_roi_units=-0.0881,
            aggregate_hit_rate=0.44,
            blocked_date_list=(),
            source_p25_dir="/tmp/p25",
            paper_only=True,
            production_ready=False,
        )

    def test_valid_construction(self):
        s = P26TrueDateReplaySummary(**self._valid_kwargs())
        assert s.n_dates_requested == 7
        assert s.aggregate_hit_rate == pytest.approx(0.44)

    def test_paper_only_enforced(self):
        kwargs = self._valid_kwargs()
        kwargs["paper_only"] = False
        with pytest.raises(ValueError, match="paper_only must be True"):
            P26TrueDateReplaySummary(**kwargs)

    def test_production_ready_enforced(self):
        kwargs = self._valid_kwargs()
        kwargs["production_ready"] = True
        with pytest.raises(ValueError, match="production_ready must be False"):
            P26TrueDateReplaySummary(**kwargs)

    def test_blocked_date_list_is_tuple(self):
        s = P26TrueDateReplaySummary(**self._valid_kwargs())
        assert isinstance(s.blocked_date_list, tuple)


# ---------------------------------------------------------------------------
# P26TrueDateReplayGateResult
# ---------------------------------------------------------------------------


class TestP26TrueDateReplayGateResult:
    def _valid_kwargs(self):
        return dict(
            p26_gate=P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,
            date_start="2025-05-08",
            date_end="2025-05-14",
            n_dates_requested=7,
            n_dates_ready=7,
            n_dates_blocked=0,
            total_active_entries=25,
            total_settled_win=11,
            total_settled_loss=14,
            total_unsettled=0,
            total_stake_units=6.25,
            total_pnl_units=-0.5506,
            aggregate_roi_units=-0.0881,
            aggregate_hit_rate=0.44,
            blocker_reason="",
            paper_only=True,
            production_ready=False,
            generated_at="2025-05-15T00:00:00+00:00",
        )

    def test_valid_construction(self):
        g = P26TrueDateReplayGateResult(**self._valid_kwargs())
        assert g.p26_gate == P26_TRUE_DATE_HISTORICAL_BACKFILL_READY

    def test_invalid_gate_rejected(self):
        kwargs = self._valid_kwargs()
        kwargs["p26_gate"] = "GARBAGE"
        with pytest.raises(ValueError, match="invalid p26_gate"):
            P26TrueDateReplayGateResult(**kwargs)

    def test_all_valid_aggregate_gates_accepted(self):
        for gate in [
            P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,
            P26_BLOCKED_NO_READY_DATES,
            P26_BLOCKED_ALL_DATES_FAILED,
            P26_BLOCKED_CONTRACT_VIOLATION,
            P26_FAIL_INPUT_MISSING,
            P26_FAIL_NON_DETERMINISTIC,
        ]:
            kwargs = self._valid_kwargs()
            kwargs["p26_gate"] = gate
            g = P26TrueDateReplayGateResult(**kwargs)
            assert g.p26_gate == gate

    def test_paper_only_enforced(self):
        kwargs = self._valid_kwargs()
        kwargs["paper_only"] = False
        with pytest.raises(ValueError, match="paper_only must be True"):
            P26TrueDateReplayGateResult(**kwargs)

    def test_production_ready_enforced(self):
        kwargs = self._valid_kwargs()
        kwargs["production_ready"] = True
        with pytest.raises(ValueError, match="production_ready must be False"):
            P26TrueDateReplayGateResult(**kwargs)


# ---------------------------------------------------------------------------
# P26TrueDateReplayManifest
# ---------------------------------------------------------------------------


class TestP26TrueDateReplayManifest:
    def _valid_kwargs(self):
        return dict(
            output_dir="/tmp/out",
            date_start="2025-05-08",
            date_end="2025-05-14",
            written_dates=("2025-05-08", "2025-05-09"),
            skipped_dates=(),
            total_rows_written=19,
            total_active_entries_written=7,
            paper_only=True,
            production_ready=False,
            generated_at="2025-05-15T00:00:00+00:00",
        )

    def test_valid_construction(self):
        m = P26TrueDateReplayManifest(**self._valid_kwargs())
        assert m.written_dates == ("2025-05-08", "2025-05-09")

    def test_paper_only_enforced(self):
        kwargs = self._valid_kwargs()
        kwargs["paper_only"] = False
        with pytest.raises(ValueError, match="paper_only must be True"):
            P26TrueDateReplayManifest(**kwargs)

    def test_production_ready_enforced(self):
        kwargs = self._valid_kwargs()
        kwargs["production_ready"] = True
        with pytest.raises(ValueError, match="production_ready must be False"):
            P26TrueDateReplayManifest(**kwargs)

    def test_written_dates_is_tuple(self):
        m = P26TrueDateReplayManifest(**self._valid_kwargs())
        assert isinstance(m.written_dates, tuple)
        assert isinstance(m.skipped_dates, tuple)
