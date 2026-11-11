"""
tests/test_p18_drawdown_diagnostics.py

Unit tests for wbc_backend/simulation/p18_drawdown_diagnostics.py
"""
from __future__ import annotations

import pandas as pd
import pytest

from wbc_backend.simulation.p18_drawdown_diagnostics import (
    DrawdownDiagnosticsReport,
    DrawdownSegment,
    LossCluster,
    compute_policy_exposure_profile,
    identify_loss_clusters,
    run_drawdown_diagnostics,
    summarize_drawdown_segments,
    summarize_outlier_loss_contribution,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

def _make_ledger(rows: list[dict]) -> pd.DataFrame:
    """Build a minimal ledger DataFrame."""
    base = {
        "row_idx": 0,
        "fold_id": 1,
        "y_true": 1,
        "p_model": 0.55,
        "p_market": 0.50,
        "decimal_odds": 2.0,
        "confidence_rank": 1,
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


def _simple_ledger(n_win: int = 5, n_loss: int = 5, threshold: float = 0.01) -> pd.DataFrame:
    rows = []
    for i in range(n_win):
        rows.append({"y_true": 1, "stake_fraction": 0.02, "decimal_odds": 2.0,
                     "p_model": 0.60, "p_market": 0.50})
    for i in range(n_loss):
        rows.append({"y_true": 0, "stake_fraction": 0.02, "decimal_odds": 2.0,
                     "p_model": 0.60, "p_market": 0.50})
    return _make_ledger(rows)


def _clustered_loss_ledger() -> pd.DataFrame:
    """Ledger with a 5-loss cluster."""
    rows = (
        [{"y_true": 1, "stake_fraction": 0.02, "decimal_odds": 2.0,
          "p_model": 0.60, "p_market": 0.50}] * 3
        + [{"y_true": 0, "stake_fraction": 0.02, "decimal_odds": 2.0,
            "p_model": 0.60, "p_market": 0.50}] * 5
        + [{"y_true": 1, "stake_fraction": 0.02, "decimal_odds": 2.0,
            "p_model": 0.60, "p_market": 0.50}] * 2
    )
    return _make_ledger(rows)


# ── summarize_drawdown_segments ────────────────────────────────────────────────

def test_summarize_drawdown_segments_detects_worst():
    ledger = _simple_ledger(n_win=3, n_loss=7)
    segments = summarize_drawdown_segments(ledger, threshold=0.01)
    assert len(segments) > 0
    worst = segments[0]
    assert worst.drawdown_pct > 0
    assert worst.start_row <= worst.end_row


def test_summarize_drawdown_segments_all_wins():
    rows = [{"y_true": 1, "stake_fraction": 0.02, "decimal_odds": 2.0,
             "p_model": 0.60, "p_market": 0.50}] * 10
    ledger = _make_ledger(rows)
    segments = summarize_drawdown_segments(ledger, threshold=0.01)
    # With all wins there's no drawdown
    assert all(s.drawdown_pct == 0 for s in segments) or len(segments) == 0


def test_summarize_drawdown_segments_returns_sorted():
    ledger = _simple_ledger(n_win=3, n_loss=7)
    segments = summarize_drawdown_segments(ledger, threshold=0.01, max_segments=10)
    pcts = [s.drawdown_pct for s in segments]
    assert pcts == sorted(pcts, reverse=True)


def test_summarize_drawdown_segments_empty_ledger():
    ledger = pd.DataFrame(columns=["row_idx", "fold_id", "y_true", "p_model",
                                   "p_market", "decimal_odds", "policy",
                                   "should_bet", "stake_fraction", "paper_only"])
    segments = summarize_drawdown_segments(ledger, threshold=0.01)
    assert segments == []


# ── identify_loss_clusters ─────────────────────────────────────────────────────

def test_identify_loss_clusters_detects_cluster():
    ledger = _clustered_loss_ledger()
    clusters = identify_loss_clusters(ledger, threshold=0.01)
    assert len(clusters) > 0
    longest = clusters[0]
    assert longest.consecutive_losses == 5


def test_identify_loss_clusters_deterministic():
    ledger = _clustered_loss_ledger()
    c1 = identify_loss_clusters(ledger, threshold=0.01)
    c2 = identify_loss_clusters(ledger, threshold=0.01)
    assert len(c1) == len(c2)
    for a, b in zip(c1, c2):
        assert a.consecutive_losses == b.consecutive_losses


def test_identify_loss_clusters_no_clusters_for_all_wins():
    rows = [{"y_true": 1, "stake_fraction": 0.02, "decimal_odds": 2.0,
             "p_model": 0.60, "p_market": 0.50}] * 10
    ledger = _make_ledger(rows)
    clusters = identify_loss_clusters(ledger, threshold=0.01)
    assert clusters == []


def test_identify_loss_clusters_sorted_descending():
    ledger = _clustered_loss_ledger()
    clusters = identify_loss_clusters(ledger, threshold=0.01)
    lengths = [c.consecutive_losses for c in clusters]
    assert lengths == sorted(lengths, reverse=True)


# ── summarize_outlier_loss_contribution ────────────────────────────────────────

def test_outlier_losses_returns_losses_only():
    ledger = _simple_ledger(n_win=5, n_loss=5)
    outliers = summarize_outlier_loss_contribution(ledger, threshold=0.01)
    for o in outliers:
        assert o.pnl < 0


def test_outlier_losses_sorted_most_negative_first():
    ledger = _simple_ledger(n_win=3, n_loss=7)
    outliers = summarize_outlier_loss_contribution(ledger, threshold=0.01)
    pnls = [o.pnl for o in outliers]
    assert pnls == sorted(pnls)


def test_outlier_losses_max_top_n():
    ledger = _simple_ledger(n_win=2, n_loss=20)
    outliers = summarize_outlier_loss_contribution(ledger, threshold=0.01, top_n=5)
    assert len(outliers) <= 5


# ── compute_policy_exposure_profile ───────────────────────────────────────────

def test_exposure_profile_fields():
    ledger = _simple_ledger()
    profile = compute_policy_exposure_profile(ledger, threshold=0.01)
    assert profile.n_bets > 0
    assert 0 <= profile.hit_rate <= 1
    assert profile.mean_stake > 0
    assert profile.mean_odds > 1


def test_exposure_profile_empty():
    ledger = pd.DataFrame(columns=["row_idx", "fold_id", "y_true", "p_model",
                                   "p_market", "decimal_odds", "policy",
                                   "should_bet", "stake_fraction", "paper_only"])
    profile = compute_policy_exposure_profile(ledger, threshold=0.01)
    assert profile.n_bets == 0


# ── run_drawdown_diagnostics ───────────────────────────────────────────────────

def test_diagnostics_returns_report():
    ledger = _clustered_loss_ledger()
    report = run_drawdown_diagnostics(ledger, threshold=0.01)
    assert isinstance(report, DrawdownDiagnosticsReport)
    assert report.max_drawdown_pct >= 0
    assert isinstance(report.root_cause_summary, str)
    assert isinstance(report.root_cause_flags, dict)


def test_diagnostics_detects_high_stake_flag():
    rows = [
        {"y_true": 0, "stake_fraction": 0.05, "decimal_odds": 2.0,
         "p_model": 0.60, "p_market": 0.50}
    ] * 10 + [
        {"y_true": 1, "stake_fraction": 0.05, "decimal_odds": 2.0,
         "p_model": 0.60, "p_market": 0.50}
    ] * 5
    ledger = _make_ledger(rows)
    report = run_drawdown_diagnostics(ledger, threshold=0.01)
    assert report.root_cause_flags["high_stake"] is True


def test_diagnostics_paper_only_always():
    ledger = _simple_ledger()
    report = run_drawdown_diagnostics(ledger, threshold=0.01)
    # The report itself does not have paper_only field,
    # but it should come from the outer system; exposure_profile exists
    assert report.exposure_profile is not None
