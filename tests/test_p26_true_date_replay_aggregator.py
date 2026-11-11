"""
tests/test_p26_true_date_replay_aggregator.py

Unit tests for p26_true_date_replay_aggregator.py.
Verifies:
  - aggregate_true_date_results computes weighted ROI correctly
  - aggregate_true_date_results computes weighted hit rate correctly
  - blocked dates counted and reported in summary
  - gate = P26_TRUE_DATE_HISTORICAL_BACKFILL_READY when >= 1 date ready
  - gate = P26_BLOCKED_NO_READY_DATES when all dates blocked
  - run_true_date_historical_backfill writes all 6 output files
  - validate_true_date_aggregate_summary passes for valid summary
  - _date_range produces correct date list
"""
import json
import tempfile
from pathlib import Path

import pytest

from wbc_backend.recommendation.p26_true_date_replay_contract import (
    P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
    P26_DATE_REPLAY_READY,
    P26_TRUE_DATE_HISTORICAL_BACKFILL_READY,
    P26_BLOCKED_NO_READY_DATES,
    P26TrueDateReplayResult,
)
from wbc_backend.recommendation.p26_true_date_replay_aggregator import (
    aggregate_true_date_results,
    build_gate_result,
    run_true_date_historical_backfill,
    validate_true_date_aggregate_summary,
    write_true_date_replay_outputs,
    _date_range,
)
import pandas as pd


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_ready_result(
    run_date: str,
    n_win: int = 2,
    n_loss: int = 1,
    stake: float = 0.75,
    pnl: float = 0.20,
) -> P26TrueDateReplayResult:
    total_settled = n_win + n_loss
    hit_rate = n_win / total_settled if total_settled > 0 else 0.0
    roi = pnl / stake if stake > 0 else 0.0
    return P26TrueDateReplayResult(
        run_date=run_date,
        true_game_date=run_date,
        true_date_slice_status=P26_DATE_REPLAY_READY,
        n_slice_rows=n_win + n_loss + 3,
        n_unique_game_ids=n_win + n_loss,
        date_matches_slice=True,
        replay_gate=P26_DATE_REPLAY_READY,
        n_active_paper_entries=n_win + n_loss,
        n_settled_win=n_win,
        n_settled_loss=n_loss,
        n_unsettled=0,
        total_stake_units=stake,
        total_pnl_units=pnl,
        roi_units=roi,
        hit_rate=hit_rate,
        game_id_coverage=1.0,
        paper_only=True,
        production_ready=False,
        blocker_reason="",
    )


def _make_blocked_result(run_date: str) -> P26TrueDateReplayResult:
    return P26TrueDateReplayResult(
        run_date=run_date,
        true_game_date=run_date,
        true_date_slice_status=P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
        n_slice_rows=0,
        n_unique_game_ids=0,
        date_matches_slice=False,
        replay_gate=P26_DATE_BLOCKED_NO_TRUE_DATE_SLICE,
        n_active_paper_entries=0,
        n_settled_win=0,
        n_settled_loss=0,
        n_unsettled=0,
        total_stake_units=0.0,
        total_pnl_units=0.0,
        roi_units=0.0,
        hit_rate=0.0,
        game_id_coverage=0.0,
        paper_only=True,
        production_ready=False,
        blocker_reason="No slice for date.",
    )


def _make_p17_slice_csv(date: str, n_eligible: int = 2, n_blocked: int = 1) -> pd.DataFrame:
    rows = []
    for i in range(n_eligible):
        rows.append({
            "ledger_id": f"L{i:03d}", "game_id": f"G{i:03d}", "date": date,
            "side": "HOME" if i % 2 == 0 else "AWAY", "p_model": 0.60,
            "p_market": 0.52, "edge": 0.08, "odds_decimal": 1.90,
            "paper_stake_units": 0.25, "paper_stake_fraction": 0.0025,
            "gate_decision": "P16_6_ELIGIBLE_PAPER_RECOMMENDATION",
            "gate_reason": "ELIGIBLE",
            "settlement_status": "SETTLED_WIN" if i % 2 == 0 else "SETTLED_LOSS",
            "pnl_units": 0.2375 if i % 2 == 0 else -0.25,
            "is_win": i % 2 == 0, "is_loss": i % 2 != 0, "is_push": False,
            "y_true": 1 if i % 2 == 0 else 0, "paper_only": True, "production_ready": False,
        })
    for j in range(n_blocked):
        rows.append({
            "ledger_id": f"B{j:03d}", "game_id": f"BG{j:03d}", "date": date,
            "side": "HOME", "p_model": 0.52, "p_market": 0.55, "edge": -0.03,
            "odds_decimal": 1.80, "paper_stake_units": 0.0, "paper_stake_fraction": 0.0,
            "gate_decision": "P16_6_BLOCKED_NEGATIVE_EDGE", "gate_reason": "NEGATIVE_EDGE",
            "settlement_status": "UNSETTLED_NOT_RECOMMENDED",
            "pnl_units": 0.0, "is_win": False, "is_loss": False, "is_push": False,
            "y_true": 1, "paper_only": True, "production_ready": False,
        })
    return pd.DataFrame(rows)


def _setup_p25_dir(tmp_path: Path, dates: list) -> Path:
    """Create a fake P25 output dir with slices for each date."""
    p25_dir = tmp_path / "p25"
    for d in dates:
        slice_dir = p25_dir / "true_date_slices" / d
        slice_dir.mkdir(parents=True, exist_ok=True)
        _make_p17_slice_csv(d).to_csv(slice_dir / "p15_true_date_input.csv", index=False)
    return p25_dir


# ---------------------------------------------------------------------------
# _date_range
# ---------------------------------------------------------------------------


class TestDateRange:
    def test_single_date(self):
        dates = _date_range("2025-05-08", "2025-05-08")
        assert dates == ["2025-05-08"]

    def test_three_dates(self):
        dates = _date_range("2025-05-08", "2025-05-10")
        assert dates == ["2025-05-08", "2025-05-09", "2025-05-10"]

    def test_empty_when_start_after_end(self):
        dates = _date_range("2025-05-10", "2025-05-08")
        assert dates == []


# ---------------------------------------------------------------------------
# aggregate_true_date_results
# ---------------------------------------------------------------------------


class TestAggregateResults:
    def test_all_ready_summary(self):
        results = [
            _make_ready_result("2025-05-08", n_win=1, n_loss=0, stake=0.25, pnl=0.15),
            _make_ready_result("2025-05-09", n_win=2, n_loss=1, stake=0.75, pnl=0.10),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-09", "/tmp/p25", results)
        assert s.n_dates_requested == 2
        assert s.n_dates_ready == 2
        assert s.n_dates_blocked == 0
        assert s.total_settled_win == 3
        assert s.total_settled_loss == 1
        assert s.total_stake_units == pytest.approx(1.00, abs=0.001)
        assert s.total_pnl_units == pytest.approx(0.25, abs=0.001)

    def test_weighted_roi(self):
        results = [
            _make_ready_result("2025-05-08", stake=1.00, pnl=0.10),
            _make_ready_result("2025-05-09", stake=2.00, pnl=-0.40),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-09", "/tmp/p25", results)
        # ROI = (0.10 + -0.40) / (1.00 + 2.00) = -0.30 / 3.00 = -0.10
        assert s.aggregate_roi_units == pytest.approx(-0.10, abs=0.001)

    def test_weighted_hit_rate(self):
        results = [
            _make_ready_result("2025-05-08", n_win=3, n_loss=1),
            _make_ready_result("2025-05-09", n_win=1, n_loss=3),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-09", "/tmp/p25", results)
        # hit_rate = 4 wins / (4 wins + 4 losses) = 0.50
        assert s.aggregate_hit_rate == pytest.approx(0.50, abs=0.001)

    def test_blocked_dates_in_list(self):
        results = [
            _make_ready_result("2025-05-08"),
            _make_blocked_result("2025-05-09"),
            _make_blocked_result("2025-05-10"),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-10", "/tmp/p25", results)
        assert s.n_dates_blocked == 2
        assert "2025-05-09" in s.blocked_date_list
        assert "2025-05-10" in s.blocked_date_list

    def test_all_blocked_summary(self):
        results = [
            _make_blocked_result("2025-05-08"),
            _make_blocked_result("2025-05-09"),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-09", "/tmp/p25", results)
        assert s.n_dates_ready == 0
        assert s.total_active_entries == 0

    def test_paper_only_always_true(self):
        results = [_make_ready_result("2025-05-08")]
        s = aggregate_true_date_results("2025-05-08", "2025-05-08", "/tmp/p25", results)
        assert s.paper_only is True
        assert s.production_ready is False


# ---------------------------------------------------------------------------
# build_gate_result
# ---------------------------------------------------------------------------


class TestBuildGateResult:
    def test_ready_when_at_least_one_date_ready(self):
        results = [
            _make_ready_result("2025-05-08"),
            _make_blocked_result("2025-05-09"),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-09", "/tmp/p25", results)
        gate = build_gate_result(s)
        assert gate.p26_gate == P26_TRUE_DATE_HISTORICAL_BACKFILL_READY

    def test_blocked_when_no_dates_ready(self):
        results = [
            _make_blocked_result("2025-05-08"),
            _make_blocked_result("2025-05-09"),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-09", "/tmp/p25", results)
        gate = build_gate_result(s)
        assert gate.p26_gate == P26_BLOCKED_NO_READY_DATES

    def test_gate_carries_summary_stats(self):
        results = [_make_ready_result("2025-05-08", n_win=3, n_loss=2, stake=1.25, pnl=0.15)]
        s = aggregate_true_date_results("2025-05-08", "2025-05-08", "/tmp/p25", results)
        gate = build_gate_result(s)
        assert gate.total_settled_win == 3
        assert gate.total_settled_loss == 2
        assert gate.total_stake_units == pytest.approx(1.25, abs=0.001)


# ---------------------------------------------------------------------------
# validate_true_date_aggregate_summary
# ---------------------------------------------------------------------------


class TestValidateAggregateSummary:
    def test_valid_summary_passes(self):
        results = [_make_ready_result("2025-05-08")]
        s = aggregate_true_date_results("2025-05-08", "2025-05-08", "/tmp/p25", results)
        assert validate_true_date_aggregate_summary(s) is True


# ---------------------------------------------------------------------------
# write_true_date_replay_outputs (all 6 files)
# ---------------------------------------------------------------------------


class TestWriteTrueDateReplayOutputs:
    def test_all_six_files_written(self, tmp_path: Path):
        results = [_make_ready_result("2025-05-08")]
        s = aggregate_true_date_results("2025-05-08", "2025-05-08", "/tmp/p25", results)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        write_true_date_replay_outputs(s, results, out_dir, Path("/tmp/p25"))

        expected = [
            "p26_gate_result.json",
            "true_date_replay_summary.json",
            "true_date_replay_summary.md",
            "date_replay_results.csv",
            "blocked_dates.json",
            "artifact_manifest.json",
        ]
        for fname in expected:
            assert (out_dir / fname).exists(), f"Missing {fname}"

    def test_gate_result_json_valid(self, tmp_path: Path):
        results = [_make_ready_result("2025-05-08")]
        s = aggregate_true_date_results("2025-05-08", "2025-05-08", "/tmp/p25", results)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        write_true_date_replay_outputs(s, results, out_dir, Path("/tmp/p25"))
        data = json.loads((out_dir / "p26_gate_result.json").read_text())
        assert "p26_gate" in data
        assert data["paper_only"] is True
        assert data["production_ready"] is False

    def test_blocked_dates_json_valid(self, tmp_path: Path):
        results = [
            _make_ready_result("2025-05-08"),
            _make_blocked_result("2025-05-09"),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-09", "/tmp/p25", results)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        write_true_date_replay_outputs(s, results, out_dir, Path("/tmp/p25"))
        data = json.loads((out_dir / "blocked_dates.json").read_text())
        assert data["n_blocked"] == 1
        assert len(data["blocked_dates"]) == 1

    def test_artifact_manifest_has_correct_dates(self, tmp_path: Path):
        results = [
            _make_ready_result("2025-05-08"),
            _make_blocked_result("2025-05-09"),
        ]
        s = aggregate_true_date_results("2025-05-08", "2025-05-09", "/tmp/p25", results)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        write_true_date_replay_outputs(s, results, out_dir, Path("/tmp/p25"))
        data = json.loads((out_dir / "artifact_manifest.json").read_text())
        assert "2025-05-08" in data["written_dates"]
        assert "2025-05-09" in data["skipped_dates"]
        assert data["paper_only"] is True


# ---------------------------------------------------------------------------
# run_true_date_historical_backfill (integration, uses real files)
# ---------------------------------------------------------------------------


class TestRunTrueDateHistoricalBackfill:
    def test_raises_when_p25_dir_missing(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            run_true_date_historical_backfill(
                "2025-05-08", "2025-05-10",
                tmp_path / "nonexistent",
                tmp_path / "out",
            )

    def test_full_run_produces_all_outputs(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08", "2025-05-09"])
        out_dir = tmp_path / "out"
        summary = run_true_date_historical_backfill(
            "2025-05-08", "2025-05-09", p25_dir, out_dir
        )
        assert summary.n_dates_ready == 2
        assert summary.paper_only is True
        for fname in ["p26_gate_result.json", "date_replay_results.csv", "artifact_manifest.json"]:
            assert (out_dir / fname).exists()

    def test_blocked_date_reported_in_summary(self, tmp_path: Path):
        p25_dir = _setup_p25_dir(tmp_path, ["2025-05-08"])
        # 2025-05-09 has no slice — will be BLOCKED
        out_dir = tmp_path / "out"
        summary = run_true_date_historical_backfill(
            "2025-05-08", "2025-05-09", p25_dir, out_dir
        )
        assert summary.n_dates_ready == 1
        assert summary.n_dates_blocked == 1
        assert "2025-05-09" in summary.blocked_date_list
