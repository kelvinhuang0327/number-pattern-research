"""
tests/test_p27_p26_segmented_replay_runner.py

Unit tests for p27_p26_segmented_replay_runner.py.
"""
import json
from pathlib import Path

import pytest

from wbc_backend.recommendation.p27_full_true_date_backfill_contract import P27ExpansionSegment
from wbc_backend.recommendation.p27_p26_segmented_replay_runner import (
    run_p26_replay_for_all_segments,
    summarize_segment_replay_results,
    validate_segment_replay_outputs,
)


def _make_segment(index=0, start="2025-05-08", end="2025-05-21", count=14):
    return P27ExpansionSegment(
        segment_index=index,
        date_start=start,
        date_end=end,
        date_count=count,
        p25_output_dir="/tmp/p25",
        p26_output_dir="/tmp/p26",
    )


def _blocked_result(index=0, start="2025-05-08", end="2025-05-21"):
    return {
        "segment_index": index,
        "date_start": start,
        "date_end": end,
        "p26_gate": "P26_BLOCKED_SCRIPT_NOT_FOUND",
        "blocked": True,
        "returncode": -1,
        "stdout": "",
        "stderr": "script not found",
        "output_dir": "",
        "gate_data": {},
    }


def _ready_result(index=0, start="2025-05-08", end="2025-05-21"):
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
            "n_dates_ready": 12,
            "n_dates_blocked": 2,
            "total_active_entries": 25,
            "total_settled_win": 11,
            "total_settled_loss": 14,
            "total_unsettled": 0,
            "total_stake_units": 6.25,
            "total_pnl_units": -0.55,
        },
    }


class TestSummarizeSegmentReplayResults:
    def test_all_blocked(self):
        results = [_blocked_result(0), _blocked_result(1, "2025-05-22", "2025-06-04")]
        s = summarize_segment_replay_results(results)
        assert s["n_segments_blocked"] == 2
        assert s["n_segments_ready"] == 0

    def test_all_ready(self):
        results = [_ready_result(0), _ready_result(1, "2025-05-22", "2025-06-04")]
        s = summarize_segment_replay_results(results)
        assert s["n_segments_ready"] == 2
        assert s["n_segments_blocked"] == 0

    def test_mixed_segments_blocked_not_hidden(self):
        """Blocked segments must appear in output, not hidden."""
        results = [_ready_result(0), _blocked_result(1, "2025-05-22", "2025-06-04")]
        s = summarize_segment_replay_results(results)
        assert s["n_segments"] == 2
        assert s["n_segments_ready"] == 1
        assert s["n_segments_blocked"] == 1
        assert len(s["blocked_segment_labels"]) == 1

    def test_weighted_roi_not_averaged(self):
        """ROI = total_pnl / total_stake, not average of per-segment ROIs."""
        r1 = _ready_result(0)
        r1["gate_data"]["total_stake_units"] = 4.0
        r1["gate_data"]["total_pnl_units"] = 1.0
        r2 = _ready_result(1, "2025-05-22", "2025-06-04")
        r2["gate_data"]["total_stake_units"] = 6.0
        r2["gate_data"]["total_pnl_units"] = -0.6
        results = [r1, r2]
        s = summarize_segment_replay_results(results)
        # Weighted: (1.0 + -0.6) / (4.0 + 6.0) = 0.4 / 10.0 = 0.04
        assert abs(s["aggregate_roi_units"] - 0.04) < 1e-6

    def test_weighted_hit_rate_not_averaged(self):
        """Hit rate = total_wins / (total_wins + total_losses)."""
        r1 = _ready_result(0)
        r1["gate_data"]["total_settled_win"] = 10
        r1["gate_data"]["total_settled_loss"] = 10
        r2 = _ready_result(1, "2025-05-22", "2025-06-04")
        r2["gate_data"]["total_settled_win"] = 5
        r2["gate_data"]["total_settled_loss"] = 5
        results = [r1, r2]
        s = summarize_segment_replay_results(results)
        # 15 wins / (15 + 15) = 0.5
        assert abs(s["aggregate_hit_rate"] - 0.5) < 1e-6

    def test_empty_results(self):
        s = summarize_segment_replay_results([])
        assert s["n_segments"] == 0


class TestValidateSegmentReplayOutputs:
    def test_valid_ready_result(self):
        results = [_ready_result(0)]
        ok, reason = validate_segment_replay_outputs(results)
        assert ok is True, reason

    def test_valid_blocked_result(self):
        results = [_blocked_result(0)]
        ok, reason = validate_segment_replay_outputs(results)
        assert ok is True, reason  # blocked is valid state

    def test_missing_required_key_returns_false(self):
        bad = {
            "segment_index": 0,
            "date_start": "2025-05-08",
            # missing date_end, p26_gate, blocked, gate_data
        }
        ok, reason = validate_segment_replay_outputs([bad])
        assert ok is False

    def test_empty_results_is_valid(self):
        ok, reason = validate_segment_replay_outputs([])
        assert ok is True


class TestRunP26ReplayForAllSegments:
    def test_all_blocked_when_script_missing(self, tmp_path):
        """If P26 script is missing, all segments return blocked."""
        segments = [_make_segment(0), _make_segment(1, "2025-05-22", "2025-06-04", 14)]
        results = run_p26_replay_for_all_segments(
            segments=segments,
            p25_base_dir=tmp_path,
            output_base_dir=tmp_path / "out",
            cwd=str(tmp_path),  # empty dir — no script present
        )
        assert len(results) == 2
        # Blocked but still returned
        for r in results:
            assert r["blocked"] is True
            assert "segment_index" in r

    def test_blocked_segments_not_hidden(self, tmp_path):
        """Even if all blocked, segment count must match input."""
        segments = [_make_segment(i, f"2025-05-{8+i*14:02d}", f"2025-05-{21+i*14:02d}", 14)
                    for i in range(3)]
        results = run_p26_replay_for_all_segments(
            segments=segments,
            p25_base_dir=tmp_path,
            output_base_dir=tmp_path / "out",
            cwd=str(tmp_path),
        )
        assert len(results) == 3
