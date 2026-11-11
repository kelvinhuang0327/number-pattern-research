"""
tests/test_p21_multi_day_backfill_aggregator.py

Unit tests for P21 multi-day backfill aggregation.
"""
import json
import tempfile
from pathlib import Path

import pytest

from wbc_backend.recommendation.p21_daily_artifact_discovery import (
    P21MissingArtifactReport,
)
from wbc_backend.recommendation.p21_multi_day_backfill_aggregator import (
    aggregate_backfill_results,
    compute_aggregate_hit_rate,
    compute_aggregate_roi,
    validate_backfill_summary,
    write_backfill_outputs,
)
from wbc_backend.recommendation.p21_multi_day_backfill_contract import (
    P21BackfillDateResult,
    P21_BLOCKED_CONTRACT_VIOLATION,
    P21_BLOCKED_NO_READY_DAILY_RUNS,
    P21_MULTI_DAY_PAPER_BACKFILL_READY,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_date_result(run_date="2026-05-12", **kwargs) -> P21BackfillDateResult:
    defaults = dict(
        run_date=run_date,
        daily_gate=P21_MULTI_DAY_PAPER_BACKFILL_READY,
        p20_gate="P20_DAILY_PAPER_ORCHESTRATOR_READY",
        n_recommended_rows=324,
        n_active_paper_entries=324,
        n_settled_win=171,
        n_settled_loss=153,
        n_unsettled=0,
        total_stake_units=324.0,
        total_pnl_units=34.921,
        roi_units=0.10778278086419754,
        hit_rate=0.5277777777777778,
        game_id_coverage=1.0,
        settlement_join_method="JOIN_BY_GAME_ID",
        artifact_manifest_sha256="abc123",
        paper_only=True,
        production_ready=False,
    )
    defaults.update(kwargs)
    return P21BackfillDateResult(**defaults)


# ---------------------------------------------------------------------------
# Tests: compute_aggregate_roi
# ---------------------------------------------------------------------------


def test_roi_stake_weighted_not_averaged():
    """ROI must be total_pnl / total_stake — NOT average of daily ROI values."""
    # Day 1: stake=100, pnl=50 → roi=0.50
    # Day 2: stake=200, pnl=10 → roi=0.05
    # Naive average: (0.50+0.05)/2 = 0.275
    # Correct stake-weighted: 60/300 = 0.20
    roi = compute_aggregate_roi(total_pnl_units=60.0, total_stake_units=300.0)
    assert abs(roi - 0.20) < 1e-9


def test_roi_zero_stake():
    assert compute_aggregate_roi(0.0, 0.0) == 0.0


def test_roi_negative():
    roi = compute_aggregate_roi(-10.0, 100.0)
    assert abs(roi - (-0.10)) < 1e-9


# ---------------------------------------------------------------------------
# Tests: compute_aggregate_hit_rate
# ---------------------------------------------------------------------------


def test_hit_rate_settled_bet_weighted():
    """Hit rate must be total_wins / (total_wins+total_losses)."""
    # Day 1: 10 wins, 10 losses → 50%
    # Day 2: 100 wins, 0 losses → 100%
    # Naive average: (0.5+1.0)/2 = 75%
    # Correct: 110/(110+10) = 91.67%
    hr = compute_aggregate_hit_rate(total_wins=110, total_losses=10)
    assert abs(hr - 110 / 120) < 1e-9


def test_hit_rate_zero_settled():
    assert compute_aggregate_hit_rate(0, 0) == 0.0


# ---------------------------------------------------------------------------
# Tests: aggregate_backfill_results
# ---------------------------------------------------------------------------


def test_aggregate_single_ready_date():
    items = [_make_date_result()]
    summary = aggregate_backfill_results(items)
    assert summary.p21_gate == P21_MULTI_DAY_PAPER_BACKFILL_READY
    assert summary.n_dates_requested == 1
    assert summary.n_dates_ready == 1
    assert summary.n_dates_missing == 0
    assert summary.n_dates_blocked == 0
    assert summary.total_active_entries == 324
    assert summary.total_settled_win == 171
    assert summary.total_settled_loss == 153
    assert summary.total_unsettled == 0


def test_aggregate_roi_stake_weighted_across_days():
    """Aggregate ROI must be stake-weighted, not day-averaged."""
    d1 = _make_date_result("2026-05-10", total_stake_units=100.0, total_pnl_units=50.0)
    d2 = _make_date_result("2026-05-11", total_stake_units=200.0, total_pnl_units=10.0)
    summary = aggregate_backfill_results([d1, d2])
    expected_roi = 60.0 / 300.0  # 0.20
    assert abs(summary.aggregate_roi_units - expected_roi) < 1e-9


def test_aggregate_hit_rate_bet_weighted_across_days():
    """Aggregate hit rate must be settled-bet-weighted, not day-averaged."""
    d1 = _make_date_result("2026-05-10", n_settled_win=10, n_settled_loss=10)
    d2 = _make_date_result("2026-05-11", n_settled_win=100, n_settled_loss=0)
    summary = aggregate_backfill_results([d1, d2])
    expected_hr = 110 / 120
    assert abs(summary.aggregate_hit_rate - expected_hr) < 1e-9


def test_aggregate_no_ready_dates_emits_blocked():
    """Zero ready dates must emit P21_BLOCKED_NO_READY_DAILY_RUNS."""
    missing = P21MissingArtifactReport(run_date="2026-05-11", error_message="missing")
    blocked = _make_date_result(daily_gate="P21_BLOCKED_DAILY_GATE_NOT_READY")
    summary = aggregate_backfill_results([missing, blocked])
    assert summary.p21_gate == P21_BLOCKED_NO_READY_DAILY_RUNS
    assert summary.n_dates_ready == 0


def test_aggregate_counts_missing_and_blocked_separately():
    missing = P21MissingArtifactReport(run_date="2026-05-11")
    blocked = _make_date_result("2026-05-10", daily_gate="P21_BLOCKED_DAILY_GATE_NOT_READY")
    ready = _make_date_result("2026-05-12")
    summary = aggregate_backfill_results([missing, blocked, ready])
    assert summary.n_dates_requested == 3
    assert summary.n_dates_missing == 1
    assert summary.n_dates_blocked == 1
    assert summary.n_dates_ready == 1


def test_aggregate_contract_violation_if_production_ready_true():
    """Ready run with production_ready=True must trigger contract violation."""
    r = _make_date_result(production_ready=True)
    summary = aggregate_backfill_results([r])
    assert summary.p21_gate == P21_BLOCKED_CONTRACT_VIOLATION


def test_aggregate_contract_violation_if_paper_only_false():
    r = _make_date_result(paper_only=False)
    summary = aggregate_backfill_results([r])
    assert summary.p21_gate == P21_BLOCKED_CONTRACT_VIOLATION


def test_aggregate_safety_invariants_always_set():
    summary = aggregate_backfill_results([_make_date_result()])
    assert summary.paper_only is True
    assert summary.production_ready is False


def test_aggregate_min_coverage_is_minimum():
    d1 = _make_date_result("2026-05-10", game_id_coverage=1.0)
    d2 = _make_date_result("2026-05-11", game_id_coverage=0.8)
    summary = aggregate_backfill_results([d1, d2])
    assert abs(summary.min_game_id_coverage - 0.8) < 1e-9


# ---------------------------------------------------------------------------
# Tests: validate_backfill_summary
# ---------------------------------------------------------------------------


def test_validate_ready_summary():
    summary = aggregate_backfill_results([_make_date_result()])
    result = validate_backfill_summary(summary)
    assert result.valid is True


def test_validate_rejects_no_ready_dates():
    missing = P21MissingArtifactReport(run_date="2026-05-11")
    summary = aggregate_backfill_results([missing])
    result = validate_backfill_summary(summary)
    assert result.valid is False
    assert result.error_code == P21_BLOCKED_NO_READY_DAILY_RUNS


# ---------------------------------------------------------------------------
# Tests: write_backfill_outputs
# ---------------------------------------------------------------------------


def test_write_backfill_outputs_creates_5_files():
    with tempfile.TemporaryDirectory() as tmp:
        items = [_make_date_result()]
        summary = aggregate_backfill_results(items)
        missing_reports: list = []
        written = write_backfill_outputs(summary, items, missing_reports, tmp)
        filenames = {Path(w).name for w in written}
        assert "backfill_summary.json" in filenames
        assert "backfill_summary.md" in filenames
        assert "date_results.csv" in filenames
        assert "missing_artifacts.json" in filenames
        assert "p21_gate_result.json" in filenames


def test_write_backfill_outputs_gate_result_has_required_fields():
    with tempfile.TemporaryDirectory() as tmp:
        items = [_make_date_result()]
        summary = aggregate_backfill_results(items)
        write_backfill_outputs(summary, items, [], tmp)
        gate = json.loads((Path(tmp) / "p21_gate_result.json").read_text())
        assert gate["p21_gate"] == P21_MULTI_DAY_PAPER_BACKFILL_READY
        assert gate["paper_only"] is True
        assert gate["production_ready"] is False
        assert gate["n_dates_requested"] == 1


def test_write_backfill_outputs_missing_artifacts_json_reflects_missing():
    with tempfile.TemporaryDirectory() as tmp:
        missing_reports = [
            {
                "run_date": "2026-05-11",
                "missing_files": ["daily_paper_summary.json"],
                "invalid_files": [],
                "error_message": "Directory not found",
            }
        ]
        items = [_make_date_result()]
        summary = aggregate_backfill_results(items)
        write_backfill_outputs(summary, items, missing_reports, tmp)
        loaded = json.loads((Path(tmp) / "missing_artifacts.json").read_text())
        assert len(loaded) == 1
        assert loaded[0]["run_date"] == "2026-05-11"
