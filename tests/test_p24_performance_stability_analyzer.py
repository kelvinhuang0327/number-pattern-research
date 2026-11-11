"""
tests/test_p24_performance_stability_analyzer.py

Unit tests for p24_performance_stability_analyzer.py.
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wbc_backend.recommendation.p24_backfill_stability_contract import (
    STABILITY_ACCEPTABLE,
    STABILITY_INSUFFICIENT_VARIANCE,
    P24DatePerformanceProfile,
)
from wbc_backend.recommendation.p24_performance_stability_analyzer import (
    _std,
    compute_per_date_performance_profiles,
    compute_variance_metrics,
    compute_weighted_aggregate_metrics,
    detect_too_uniform_performance,
    load_p23_date_results,
    summarize_performance_stability,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df_row(
    run_date: str = "2026-05-01",
    n_active: int = 100,
    n_win: int = 55,
    n_loss: int = 45,
    n_unsettled: int = 0,
    stake: float = 25.0,
    pnl: float = 2.5,
    roi: float = 0.10,
    hit_rate: float = 0.55,
    coverage: float = 1.0,
) -> dict:
    return {
        "run_date": run_date,
        "n_active_paper_entries": n_active,
        "n_settled_win": n_win,
        "n_settled_loss": n_loss,
        "n_unsettled": n_unsettled,
        "total_stake_units": stake,
        "total_pnl_units": pnl,
        "roi_units": roi,
        "hit_rate": hit_rate,
        "game_id_coverage": coverage,
    }


def _make_p23_csv(tmp_path: Path, rows: list) -> str:
    df = pd.DataFrame(rows)
    path = tmp_path / "date_replay_results.csv"
    df.to_csv(path, index=False)
    return str(path)


def _make_profile(
    run_date: str = "2026-05-01",
    roi: float = 0.10,
    hit_rate: float = 0.55,
    n_active: int = 100,
    stake: float = 25.0,
    pnl: float = 2.5,
    source_hash: str = "aabbcc",
    match_date: bool = True,
) -> P24DatePerformanceProfile:
    return P24DatePerformanceProfile(
        run_date=run_date,
        n_active_entries=n_active,
        n_settled_win=55,
        n_settled_loss=45,
        n_unsettled=0,
        total_stake_units=stake,
        total_pnl_units=pnl,
        roi_units=roi,
        hit_rate=hit_rate,
        game_id_coverage=1.0,
        source_hash_content=source_hash,
        game_id_set_hash="ggg",
        game_date_range_str="2026-05-01:2026-05-01",
        run_date_matches_game_date=match_date,
    )


# ---------------------------------------------------------------------------
# _std
# ---------------------------------------------------------------------------


def test_std_of_identical_values():
    assert _std([5.0, 5.0, 5.0]) == pytest.approx(0.0)


def test_std_of_varied_values():
    # Population std of [2, 4, 4, 4, 5, 5, 7, 9] = 2.0
    assert _std([2, 4, 4, 4, 5, 5, 7, 9]) == pytest.approx(2.0)


def test_std_single_value():
    assert _std([10.0]) == 0.0


# ---------------------------------------------------------------------------
# load_p23_date_results
# ---------------------------------------------------------------------------


def test_load_p23_date_results_ok(tmp_path):
    rows = [_make_df_row()]
    path = _make_p23_csv(tmp_path, rows)
    df = load_p23_date_results(path)
    assert len(df) == 1
    assert "run_date" in df.columns


def test_load_p23_date_results_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_p23_date_results(str(tmp_path / "nonexistent.csv"))


# ---------------------------------------------------------------------------
# compute_per_date_performance_profiles
# ---------------------------------------------------------------------------


def test_profiles_built_from_df(tmp_path):
    rows = [
        _make_df_row("2026-05-01", n_active=100, stake=25.0, pnl=2.5, roi=0.10),
        _make_df_row("2026-05-02", n_active=200, stake=50.0, pnl=5.0, roi=0.10),
    ]
    df = pd.DataFrame(rows)
    profiles = compute_per_date_performance_profiles(df)
    assert len(profiles) == 2
    assert profiles[0].run_date == "2026-05-01"
    assert profiles[1].run_date == "2026-05-02"
    assert profiles[0].n_active_entries == 100


def test_profiles_source_hash_map_applied(tmp_path):
    rows = [_make_df_row("2026-05-01")]
    df = pd.DataFrame(rows)
    profiles = compute_per_date_performance_profiles(
        df, source_hash_map={"2026-05-01": "myhash"}
    )
    assert profiles[0].source_hash_content == "myhash"


# ---------------------------------------------------------------------------
# compute_weighted_aggregate_metrics
# ---------------------------------------------------------------------------


def test_weighted_roi_is_total_pnl_over_total_stake():
    """ROI = total_pnl / total_stake (not average of per-date ROIs)."""
    p1 = _make_profile(stake=100.0, pnl=10.0, roi=0.10)
    p2 = _make_profile(stake=50.0, pnl=5.0, roi=0.10)
    agg = compute_weighted_aggregate_metrics([p1, p2])
    # total_pnl = 15, total_stake = 150 → roi = 0.10
    assert agg["aggregate_roi_units"] == pytest.approx(15.0 / 150.0)
    assert agg["total_stake_units"] == pytest.approx(150.0)
    assert agg["total_pnl_units"] == pytest.approx(15.0)


def test_weighted_roi_asymmetric():
    """Different stake sizes: roi ≠ simple average."""
    p1 = _make_profile(stake=100.0, pnl=10.0)
    p2 = _make_profile(stake=50.0, pnl=2.5)
    agg = compute_weighted_aggregate_metrics([p1, p2])
    expected_roi = 12.5 / 150.0
    assert agg["aggregate_roi_units"] == pytest.approx(expected_roi)


def test_aggregate_zero_stake():
    p = _make_profile(stake=0.0, pnl=0.0)
    agg = compute_weighted_aggregate_metrics([p])
    assert agg["aggregate_roi_units"] == 0.0


# ---------------------------------------------------------------------------
# compute_variance_metrics
# ---------------------------------------------------------------------------


def test_variance_zero_for_identical_profiles():
    profiles = [_make_profile(roi=0.10, hit_rate=0.55, n_active=100) for _ in range(5)]
    v = compute_variance_metrics(profiles)
    assert v["roi_std_by_date"] == pytest.approx(0.0)
    assert v["hit_rate_std_by_date"] == pytest.approx(0.0)
    assert v["active_entry_std_by_date"] == pytest.approx(0.0)
    assert v["roi_min_by_date"] == pytest.approx(0.10)
    assert v["roi_max_by_date"] == pytest.approx(0.10)


def test_variance_positive_for_varied_profiles():
    p1 = _make_profile(roi=0.05, hit_rate=0.50, n_active=100)
    p2 = _make_profile(roi=0.15, hit_rate=0.60, n_active=200)
    v = compute_variance_metrics([p1, p2])
    assert v["roi_std_by_date"] > 0
    assert v["hit_rate_std_by_date"] > 0
    assert v["roi_min_by_date"] == pytest.approx(0.05)
    assert v["roi_max_by_date"] == pytest.approx(0.15)
    assert v["active_entry_min_by_date"] == 100
    assert v["active_entry_max_by_date"] == 200


def test_variance_empty_profiles():
    v = compute_variance_metrics([])
    assert v["roi_std_by_date"] == 0.0
    assert v["active_entry_min_by_date"] == 0


# ---------------------------------------------------------------------------
# detect_too_uniform_performance
# ---------------------------------------------------------------------------


def test_detects_identical_roi():
    profiles = [_make_profile(roi=0.10, source_hash="h1") for _ in range(5)]
    is_suspicious, reason = detect_too_uniform_performance(profiles)
    assert is_suspicious is True
    assert "identical ROI" in reason


def test_detects_identical_hash():
    profiles = [_make_profile(source_hash="samehash") for _ in range(3)]
    is_suspicious, reason = detect_too_uniform_performance(profiles)
    assert is_suspicious is True
    assert "source content hash" in reason


def test_detects_date_mismatch():
    profiles = [_make_profile(match_date=False) for _ in range(3)]
    is_suspicious, reason = detect_too_uniform_performance(profiles)
    assert is_suspicious is True
    assert "game_date" in reason


def test_not_suspicious_for_varied_performance():
    p1 = _make_profile(roi=0.05, hit_rate=0.50, n_active=80, source_hash="h1", match_date=True)
    p2 = _make_profile(roi=0.15, hit_rate=0.60, n_active=120, source_hash="h2", match_date=True)
    is_suspicious, reason = detect_too_uniform_performance([p1, p2])
    # ROI differs, hit_rate differs, source_hash differs, active differs → not suspicious
    assert is_suspicious is False


def test_single_profile_not_suspicious():
    profiles = [_make_profile()]
    is_suspicious, reason = detect_too_uniform_performance(profiles)
    assert is_suspicious is False


# ---------------------------------------------------------------------------
# summarize_performance_stability
# ---------------------------------------------------------------------------


def test_summarize_flags_uniform():
    profiles = [_make_profile(roi=0.10, hit_rate=0.55, n_active=100) for _ in range(12)]
    summary = summarize_performance_stability(profiles)
    assert summary["is_performance_suspicious"] is True
    assert summary["performance_stability_flag"] == STABILITY_INSUFFICIENT_VARIANCE


def test_summarize_acceptable_for_varied():
    profiles = [
        _make_profile(
            roi=0.05 + i * 0.01,
            hit_rate=0.50 + i * 0.01,
            n_active=80 + i * 10,  # vary active count too
            source_hash=f"h{i}",
            match_date=True,
        )
        for i in range(5)
    ]
    summary = summarize_performance_stability(profiles)
    # ROI varies, hit_rate varies, active count varies, source hashes differ → acceptable
    assert summary["is_performance_suspicious"] is False
