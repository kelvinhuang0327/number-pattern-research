"""
tests/test_p18_strategy_policy_grid.py

Unit tests for wbc_backend/simulation/p18_strategy_policy_grid.py
"""
from __future__ import annotations

import pandas as pd
import pytest

from wbc_backend.simulation.p18_strategy_policy_grid import (
    GridSearchReport,
    PolicyCandidate,
    run_policy_grid_search,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_ledger(rows: list[dict]) -> pd.DataFrame:
    base = {
        "row_idx": 0,
        "fold_id": 1,
        "y_true": 1,
        "p_model": 0.65,
        "p_market": 0.50,
        "decimal_odds": 2.0,
        "policy": "capped_kelly",
        "should_bet": True,
        "stake_fraction": 0.02,
        "reason": "POLICY_SELECTED",
        "paper_only": True,
    }
    records = []
    for i, r in enumerate(rows):
        rec = {**base, "row_idx": i}
        rec.update(r)
        records.append(rec)
    return pd.DataFrame(records)


def _high_win_ledger(n: int = 200) -> pd.DataFrame:
    """Ledger with 60% win rate, moderate odds, small edge → policy should pass."""
    rows = []
    for i in range(n):
        rows.append({
            "y_true": 1 if i % 5 != 0 else 0,   # 80% win rate
            "p_model": 0.70,
            "p_market": 0.55,
            "decimal_odds": 1.80,
            "stake_fraction": 0.02,
        })
    return _make_ledger(rows)


def _low_win_ledger(n: int = 200) -> pd.DataFrame:
    """Ledger with 30% win rate → policy likely to have high drawdown."""
    rows = []
    for i in range(n):
        rows.append({
            "y_true": 1 if i % 3 == 0 else 0,  # 33% win rate
            "p_model": 0.65,
            "p_market": 0.50,
            "decimal_odds": 2.0,
            "stake_fraction": 0.02,
        })
    return _make_ledger(rows)


def _tiny_ledger() -> pd.DataFrame:
    """Ledger with only 10 bets → all policies should fail n_bets >= 50."""
    rows = [
        {"y_true": 1, "p_model": 0.70, "p_market": 0.50,
         "decimal_odds": 2.0, "stake_fraction": 0.02}
    ] * 10
    return _make_ledger(rows)


# ── Structure tests ────────────────────────────────────────────────────────────

def test_grid_search_returns_report():
    ledger = _high_win_ledger(200)
    report = run_policy_grid_search(ledger, min_bets_floor=10, bootstrap_n_iter=50)
    assert isinstance(report, GridSearchReport)
    assert report.n_candidates_evaluated > 0
    assert isinstance(report.candidates, list)
    assert all(isinstance(c, PolicyCandidate) for c in report.candidates)


def test_candidate_has_all_required_fields():
    ledger = _high_win_ledger(200)
    report = run_policy_grid_search(ledger, min_bets_floor=10, bootstrap_n_iter=50)
    for c in report.candidates[:5]:
        assert hasattr(c, "policy_id")
        assert hasattr(c, "edge_threshold")
        assert hasattr(c, "max_stake_cap")
        assert hasattr(c, "kelly_fraction")
        assert hasattr(c, "odds_decimal_max")
        assert hasattr(c, "n_bets")
        assert hasattr(c, "roi_mean")
        assert hasattr(c, "roi_ci_low_95")
        assert hasattr(c, "roi_ci_high_95")
        assert hasattr(c, "max_drawdown_pct")
        assert hasattr(c, "sharpe_ratio")
        assert hasattr(c, "hit_rate")
        assert hasattr(c, "max_consecutive_loss")
        assert hasattr(c, "avg_edge")
        assert hasattr(c, "avg_stake_fraction")
        assert hasattr(c, "total_turnover")
        assert hasattr(c, "policy_pass")
        assert hasattr(c, "fail_reasons")


# ── Pass criteria ──────────────────────────────────────────────────────────────

def test_policy_pass_requires_n_bets_floor():
    """A policy with n_bets < floor must not pass."""
    ledger = _tiny_ledger()
    report = run_policy_grid_search(
        ledger,
        min_bets_floor=50,  # 10 bets < 50
        max_drawdown_limit=0.25,
        sharpe_floor=0.0,
        bootstrap_n_iter=50,
    )
    for c in report.candidates:
        if c.n_bets < 50:
            assert c.policy_pass is False


def test_policy_pass_requires_drawdown_limit():
    """Candidates exceeding drawdown limit must not pass."""
    ledger = _low_win_ledger(200)
    report = run_policy_grid_search(
        ledger,
        min_bets_floor=10,
        max_drawdown_limit=0.25,
        sharpe_floor=-999.0,  # disable sharpe check
        bootstrap_n_iter=50,
    )
    for c in report.candidates:
        if c.max_drawdown_pct > 25.0:
            assert c.policy_pass is False


def test_policy_pass_requires_positive_sharpe():
    """Candidates with sharpe < floor must not pass."""
    ledger = _low_win_ledger(200)
    report = run_policy_grid_search(
        ledger,
        min_bets_floor=10,
        max_drawdown_limit=99.0,  # disable drawdown check
        sharpe_floor=0.0,
        bootstrap_n_iter=50,
    )
    for c in report.candidates:
        if c.sharpe_ratio < 0.0:
            assert c.policy_pass is False


# ── Selection rule ─────────────────────────────────────────────────────────────

def test_selection_prefers_lower_drawdown():
    """Among passing candidates, the one with lowest drawdown is selected."""
    ledger = _high_win_ledger(400)
    report = run_policy_grid_search(ledger, min_bets_floor=10, bootstrap_n_iter=50)
    if report.best_candidate is not None:
        passing = [c for c in report.candidates if c.policy_pass]
        min_dd = min(c.max_drawdown_pct for c in passing)
        # Best candidate should have the minimum drawdown
        assert report.best_candidate.max_drawdown_pct <= min_dd + 1e-9


def test_no_pass_candidate_emits_blocked():
    """When no candidate passes, gate must be P18_BLOCKED_NO_RISK_ACCEPTABLE_POLICY."""
    ledger = _tiny_ledger()
    report = run_policy_grid_search(
        ledger,
        min_bets_floor=50,  # impossible with 10 bets
        bootstrap_n_iter=50,
    )
    assert report.gate_decision == "P18_BLOCKED_NO_RISK_ACCEPTABLE_POLICY"
    assert report.best_candidate is None


def test_passing_candidate_emits_repaired():
    """When a candidate passes, gate must be P18_STRATEGY_POLICY_RISK_REPAIRED."""
    ledger = _high_win_ledger(400)
    report = run_policy_grid_search(ledger, min_bets_floor=10, bootstrap_n_iter=50)
    # With 400 bets at 80% win rate, at least one policy should pass
    if report.n_candidates_passing > 0:
        assert report.gate_decision == "P18_STRATEGY_POLICY_RISK_REPAIRED"
        assert report.best_candidate is not None


# ── Determinism ────────────────────────────────────────────────────────────────

def test_grid_search_deterministic():
    ledger = _high_win_ledger(300)
    r1 = run_policy_grid_search(ledger, min_bets_floor=10, bootstrap_n_iter=50)
    r2 = run_policy_grid_search(ledger, min_bets_floor=10, bootstrap_n_iter=50)
    assert r1.n_candidates_evaluated == r2.n_candidates_evaluated
    assert r1.gate_decision == r2.gate_decision
    if r1.best_candidate and r2.best_candidate:
        assert r1.best_candidate.policy_id == r2.best_candidate.policy_id
        assert abs(r1.best_candidate.max_drawdown_pct - r2.best_candidate.max_drawdown_pct) < 1e-9


# ── Total candidates ──────────────────────────────────────────────────────────

def test_grid_evaluates_all_combinations():
    """5 edge × 5 stake × 4 kelly × 4 odds = 400 candidates."""
    ledger = _high_win_ledger(400)
    report = run_policy_grid_search(ledger, min_bets_floor=10, bootstrap_n_iter=50)
    assert report.n_candidates_evaluated == 5 * 5 * 4 * 4
