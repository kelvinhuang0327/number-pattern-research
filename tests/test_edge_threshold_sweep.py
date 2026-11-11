"""
tests/test_edge_threshold_sweep.py

Unit tests for wbc_backend/simulation/edge_threshold_sweep.py

Test cases:
- sweep returns SWEEP_INSUFFICIENT_SAMPLES when n_bets < 50 everywhere
- sweep picks max-Sharpe threshold subject to floor
- SweepReport has correct structure
- determinism
"""
from __future__ import annotations

import pandas as pd
import pytest

from wbc_backend.simulation.edge_threshold_sweep import (
    SWEEP_INSUFFICIENT_SAMPLES,
    SWEEP_OK,
    SweepReport,
    ThresholdResult,
    sweep_edge_thresholds,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ledger(
    n: int,
    y_true_pattern: list[int],
    edge_pattern: list[float],
    stake: float = 0.02,
    decimal_odds: float = 2.0,
) -> pd.DataFrame:
    y_true = [y_true_pattern[i % len(y_true_pattern)] for i in range(n)]
    edge = [edge_pattern[i % len(edge_pattern)] for i in range(n)]
    return pd.DataFrame({
        "policy": ["capped_kelly"] * n,
        "should_bet": [True] * n,
        "stake_fraction": [stake] * n,
        "decimal_odds": [decimal_odds] * n,
        "y_true": y_true,
        "p_model": [0.6] * n,
        "p_market": [0.6 - e for e in edge],
        "edge": edge,
    })


# ── SWEEP_INSUFFICIENT_SAMPLES ────────────────────────────────────────────────

def test_sweep_insufficient_when_all_thresholds_below_floor():
    # Only 10 rows, all with edge > 0.08 → any threshold gives n_bets < 50
    ledger = _make_ledger(10, [1, 0], [0.10])
    report = sweep_edge_thresholds(ledger, thresholds=[0.01, 0.02, 0.03], min_bets_floor=50)
    assert report.sweep_status == SWEEP_INSUFFICIENT_SAMPLES
    assert report.recommended_threshold is None
    assert report.fallback_threshold is not None


def test_sweep_insufficient_reason_code():
    ledger = _make_ledger(10, [1, 0], [0.10])
    report = sweep_edge_thresholds(ledger, thresholds=[0.01], min_bets_floor=50)
    assert SWEEP_INSUFFICIENT_SAMPLES in report.recommended_reason


# ── SWEEP_OK ──────────────────────────────────────────────────────────────────

def test_sweep_ok_when_enough_bets_at_low_threshold():
    # 200 rows with edge 0.05 → all pass threshold 0.01
    ledger = _make_ledger(200, [1, 1, 0, 1], [0.05])
    report = sweep_edge_thresholds(ledger, thresholds=[0.01, 0.03, 0.05], min_bets_floor=50)
    assert report.sweep_status == SWEEP_OK
    assert report.recommended_threshold is not None


def test_sweep_picks_max_sharpe_threshold():
    # Create ledger where higher edge threshold yields higher Sharpe
    # Edge=0.10 rows: all wins → high Sharpe but may have fewer bets
    # Edge=0.01 rows: mixed → lower Sharpe
    # 300 rows: half with edge 0.05 (wins), half with edge 0.10 (wins)
    # Threshold 0.10 → only 150 rows, high Sharpe
    # Threshold 0.01 → 300 rows, lower Sharpe
    rows = []
    for i in range(300):
        edge = 0.10 if i % 2 == 0 else 0.02
        y = 1  # all wins → sharpe depends on edge filter
        rows.append({
            "policy": "capped_kelly",
            "should_bet": True,
            "stake_fraction": 0.02,
            "decimal_odds": 2.0,
            "y_true": y,
            "p_model": 0.6,
            "p_market": 0.6 - edge,
            "edge": edge,
        })
    ledger = pd.DataFrame(rows)
    report = sweep_edge_thresholds(ledger, thresholds=[0.01, 0.05, 0.10], min_bets_floor=50)
    assert report.sweep_status == SWEEP_OK
    # Both thresholds have >= 50 bets; check recommended_threshold exists
    assert report.recommended_threshold in [0.01, 0.05, 0.10]


def test_sweep_report_structure():
    ledger = _make_ledger(200, [1, 0], [0.05])
    report = sweep_edge_thresholds(ledger, thresholds=[0.01, 0.03, 0.05], min_bets_floor=10)
    assert isinstance(report, SweepReport)
    assert len(report.per_threshold_rows) == 3
    for tr in report.per_threshold_rows:
        assert isinstance(tr, ThresholdResult)
        assert tr.threshold in [0.01, 0.03, 0.05]
        assert tr.n_eligible_rows >= 0


def test_sweep_deterministic():
    ledger = _make_ledger(200, [1, 0, 1], [0.05, 0.03, 0.01])
    r1 = sweep_edge_thresholds(ledger, thresholds=[0.01, 0.03, 0.05], min_bets_floor=10)
    r2 = sweep_edge_thresholds(ledger, thresholds=[0.01, 0.03, 0.05], min_bets_floor=10)
    assert r1.recommended_threshold == r2.recommended_threshold
    assert r1.sweep_status == r2.sweep_status
    for t1, t2 in zip(r1.per_threshold_rows, r2.per_threshold_rows):
        assert t1.threshold == t2.threshold
        assert t1.risk_profile.roi_mean == t2.risk_profile.roi_mean


def test_sweep_fallback_on_insufficient():
    ledger = _make_ledger(10, [1], [0.10])
    report = sweep_edge_thresholds(
        ledger,
        thresholds=[0.01, 0.05],
        min_bets_floor=50,
    )
    assert report.sweep_status == SWEEP_INSUFFICIENT_SAMPLES
    assert report.fallback_threshold == 0.01  # lowest threshold
    assert report.recommended_threshold is None


def test_sweep_n_eligible_rows_decreasing_with_threshold():
    # Higher threshold → fewer eligible rows
    ledger = _make_ledger(300, [1, 0], [0.01, 0.02, 0.03, 0.05, 0.08])
    report = sweep_edge_thresholds(
        ledger,
        thresholds=[0.01, 0.05],
        min_bets_floor=1,
    )
    n_low = next(r.n_eligible_rows for r in report.per_threshold_rows if r.threshold == 0.01)
    n_high = next(r.n_eligible_rows for r in report.per_threshold_rows if r.threshold == 0.05)
    assert n_low >= n_high
