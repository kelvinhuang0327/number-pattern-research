"""
tests/test_p27_full_backfill_reconciler.py

Unit tests for p27_full_backfill_reconciler.py.
"""
import json
from pathlib import Path

import pytest

from wbc_backend.recommendation.p27_full_true_date_backfill_contract import (
    P27_BLOCKED_P26_REPLAY_FAILED,
    P27_BLOCKED_RUNTIME_GUARD,
    P27_FAIL_INPUT_MISSING,
    P27_FULL_TRUE_DATE_BACKFILL_READY,
)
from wbc_backend.recommendation.p27_full_backfill_reconciler import (
    build_p27_gate_result,
    compute_full_range_weighted_metrics,
    detect_duplicate_segment_outputs,
    reconcile_segment_outputs,
    validate_full_backfill_summary,
    write_p27_outputs,
)
from wbc_backend.recommendation.p27_full_true_date_backfill_contract import (
    P27FullBackfillSummary,
    P27RuntimeGuardResult,
)


def _ready_seg(index=0, start="2025-05-08", end="2025-05-21",
               wins=11, losses=14, stake=6.25, pnl=-0.55, unsettled=0, dates_ready=14):
    return {
        "segment_index": index,
        "date_start": start,
        "date_end": end,
        "p26_gate": "P26_TRUE_DATE_HISTORICAL_BACKFILL_READY",
        "blocked": False,
        "returncode": 0,
        "stdout": "",
        "stderr": "",
        "output_dir": f"/tmp/p26_seg_{index}",
        "gate_data": {
            "n_dates_requested": 14,
            "n_dates_ready": dates_ready,
            "n_dates_blocked": 14 - dates_ready,
            "total_active_entries": wins + losses,
            "total_settled_win": wins,
            "total_settled_loss": losses,
            "total_unsettled": unsettled,
            "total_stake_units": stake,
            "total_pnl_units": pnl,
        },
    }


def _blocked_seg(index=0, start="2025-05-22", end="2025-06-04"):
    return {
        "segment_index": index,
        "date_start": start,
        "date_end": end,
        "p26_gate": "P26_BLOCKED",
        "blocked": True,
        "returncode": -1,
        "stdout": "",
        "stderr": "",
        "output_dir": "",
        "gate_data": {},
    }


class TestReconcileSegmentOutputs:
    def test_empty_results(self):
        s = reconcile_segment_outputs([])
        assert s.n_segments == 0
        assert s.paper_only is True
        assert s.production_ready is False

    def test_single_ready_segment(self):
        s = reconcile_segment_outputs([_ready_seg()])
        assert s.total_settled_win == 11
        assert s.total_settled_loss == 14
        assert s.paper_only is True
        assert s.production_ready is False


class TestComputeFullRangeWeightedMetrics:
    def test_weighted_roi_not_averaged(self):
        """ROI = total_pnl / total_stake, not avg of segment ROIs."""
        r1 = _ready_seg(0, stake=4.0, pnl=1.0, wins=5, losses=5)
        r2 = _ready_seg(1, "2025-05-22", "2025-06-04", stake=6.0, pnl=-0.6, wins=5, losses=5)
        s = compute_full_range_weighted_metrics(
            "2025-05-08", "2025-06-04", 2, [r1, r2], [], ""
        )
        expected_roi = 0.4 / 10.0
        assert abs(s.aggregate_roi_units - expected_roi) < 1e-6

    def test_weighted_hit_rate_not_averaged(self):
        """Hit rate = total_wins / (total_wins + total_losses)."""
        r1 = _ready_seg(0, wins=10, losses=10)
        r2 = _ready_seg(1, "2025-05-22", "2025-06-04", wins=5, losses=5)
        s = compute_full_range_weighted_metrics(
            "2025-05-08", "2025-06-04", 2, [r1, r2], [], ""
        )
        assert abs(s.aggregate_hit_rate - 0.5) < 1e-6

    def test_zero_stake_gives_zero_roi(self):
        r1 = _ready_seg(0, stake=0.0, pnl=0.0)
        s = compute_full_range_weighted_metrics(
            "2025-05-08", "2025-05-21", 1, [r1], [], ""
        )
        assert s.aggregate_roi_units == 0.0

    def test_blocked_segment_not_included_in_totals(self):
        r1 = _ready_seg(0, wins=10, losses=5, stake=5.0, pnl=1.0)
        r2 = _blocked_seg(1)
        s = compute_full_range_weighted_metrics(
            "2025-05-08", "2025-06-04", 2, [r1, r2], [], ""
        )
        # Only r1 should contribute to totals
        assert s.total_settled_win == 10
        assert s.total_settled_loss == 5
        assert abs(s.total_stake_units - 5.0) < 1e-6

    def test_paper_only_hardcoded(self):
        s = compute_full_range_weighted_metrics(
            "2025-05-08", "2025-05-21", 1, [_ready_seg()], [], ""
        )
        assert s.paper_only is True
        assert s.production_ready is False


class TestDetectDuplicateSegmentOutputs:
    def test_no_duplicates(self):
        results = [
            {"output_dir": "/tmp/a"},
            {"output_dir": "/tmp/b"},
        ]
        assert detect_duplicate_segment_outputs(results) == []

    def test_detects_duplicate(self):
        results = [
            {"output_dir": "/tmp/same"},
            {"output_dir": "/tmp/same"},
        ]
        dups = detect_duplicate_segment_outputs(results)
        assert "/tmp/same" in dups

    def test_empty_output_dir_ignored(self):
        results = [{"output_dir": ""}, {"output_dir": ""}]
        dups = detect_duplicate_segment_outputs(results)
        assert dups == []


class TestValidateFullBackfillSummary:
    def _make_summary(self, **kwargs):
        base = dict(
            date_start="2025-05-08", date_end="2025-05-21",
            n_segments=1, n_dates_requested=14, n_dates_ready=12,
            n_dates_empty=2, n_dates_blocked=0,
            total_active_entries=25, total_settled_win=11, total_settled_loss=14,
            total_unsettled=0, total_stake_units=6.25, total_pnl_units=-0.55,
            aggregate_roi_units=-0.088, aggregate_hit_rate=0.44,
            min_game_id_coverage=1.0, max_runtime_seconds=10.0,
            blocked_segment_list=(), blocked_date_list=(),
            source_p25_base_dir="/tmp/p25",
            paper_only=True, production_ready=False, blocker_reason="",
        )
        base.update(kwargs)
        return P27FullBackfillSummary(**base)

    def test_valid_passes(self):
        s = self._make_summary()
        assert validate_full_backfill_summary(s) is True

    def test_production_ready_true_raises(self):
        with pytest.raises(ValueError):
            s = self._make_summary(production_ready=True)

    def test_paper_only_false_raises(self):
        with pytest.raises(ValueError):
            s = self._make_summary(paper_only=False)


class TestBuildP27GateResult:
    def _make_summary(self, n_dates_requested=14, n_dates_ready=12):
        return P27FullBackfillSummary(
            date_start="2025-05-08", date_end="2025-05-21",
            n_segments=1, n_dates_requested=n_dates_requested, n_dates_ready=n_dates_ready,
            n_dates_empty=0, n_dates_blocked=0,
            total_active_entries=25, total_settled_win=11, total_settled_loss=14,
            total_unsettled=0, total_stake_units=6.25, total_pnl_units=-0.55,
            aggregate_roi_units=-0.088, aggregate_hit_rate=0.44,
            min_game_id_coverage=1.0, max_runtime_seconds=10.0,
            blocked_segment_list=(), blocked_date_list=(),
            source_p25_base_dir="/tmp/p25",
            paper_only=True, production_ready=False, blocker_reason="",
        )

    def test_ready_gate(self):
        s = self._make_summary()
        g = build_p27_gate_result(s)
        assert g.p27_gate == P27_FULL_TRUE_DATE_BACKFILL_READY

    def test_fail_input_missing_when_zero_dates(self):
        s = self._make_summary(n_dates_requested=0, n_dates_ready=0)
        g = build_p27_gate_result(s)
        assert g.p27_gate == P27_FAIL_INPUT_MISSING

    def test_blocked_p26_when_no_dates_ready(self):
        s = self._make_summary(n_dates_requested=14, n_dates_ready=0)
        g = build_p27_gate_result(s)
        assert g.p27_gate == P27_BLOCKED_P26_REPLAY_FAILED

    def test_blocked_runtime_guard(self):
        s = self._make_summary()
        g = build_p27_gate_result(s, runtime_seconds=200.0, max_runtime_seconds=180.0, guard_triggered=True)
        assert g.p27_gate == P27_BLOCKED_RUNTIME_GUARD

    def test_paper_only_hardcoded(self):
        s = self._make_summary()
        g = build_p27_gate_result(s)
        assert g.paper_only is True
        assert g.production_ready is False


class TestWriteP27Outputs:
    def _make_summary(self):
        return P27FullBackfillSummary(
            date_start="2025-05-08", date_end="2025-05-21",
            n_segments=1, n_dates_requested=14, n_dates_ready=12,
            n_dates_empty=2, n_dates_blocked=0,
            total_active_entries=25, total_settled_win=11, total_settled_loss=14,
            total_unsettled=0, total_stake_units=6.25, total_pnl_units=-0.55,
            aggregate_roi_units=-0.088, aggregate_hit_rate=0.44,
            min_game_id_coverage=1.0, max_runtime_seconds=10.0,
            blocked_segment_list=(), blocked_date_list=(),
            source_p25_base_dir="/tmp/p25",
            paper_only=True, production_ready=False, blocker_reason="",
        )

    def _make_gate(self, summary):
        return build_p27_gate_result(summary)

    def _make_runtime_guard(self):
        return P27RuntimeGuardResult(
            max_runtime_seconds=180.0,
            actual_runtime_seconds=45.0,
            guard_triggered=False,
            guard_reason="",
            paper_only=True,
            production_ready=False,
        )

    def test_writes_7_files(self, tmp_path):
        s = self._make_summary()
        g = self._make_gate(s)
        rg = self._make_runtime_guard()
        write_p27_outputs(s, g, [_ready_seg()], [], rg, tmp_path)
        expected = {
            "p27_gate_result.json",
            "p27_full_backfill_summary.json",
            "p27_full_backfill_summary.md",
            "segment_results.csv",
            "date_results.csv",
            "blocked_segments.json",
            "runtime_guard.json",
        }
        written = {f.name for f in tmp_path.iterdir()}
        assert expected == written

    def test_gate_result_json_correct(self, tmp_path):
        s = self._make_summary()
        g = self._make_gate(s)
        rg = self._make_runtime_guard()
        write_p27_outputs(s, g, [], [], rg, tmp_path)
        data = json.loads((tmp_path / "p27_gate_result.json").read_text())
        assert data["p27_gate"] == P27_FULL_TRUE_DATE_BACKFILL_READY
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_blocked_segments_json_paper_safe(self, tmp_path):
        s = self._make_summary()
        g = self._make_gate(s)
        rg = self._make_runtime_guard()
        write_p27_outputs(s, g, [], [], rg, tmp_path)
        data = json.loads((tmp_path / "blocked_segments.json").read_text())
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_segment_results_csv_has_header(self, tmp_path):
        s = self._make_summary()
        g = self._make_gate(s)
        rg = self._make_runtime_guard()
        write_p27_outputs(s, g, [_ready_seg()], [], rg, tmp_path)
        csv_text = (tmp_path / "segment_results.csv").read_text()
        assert "segment_index" in csv_text
        assert "p26_gate" in csv_text
