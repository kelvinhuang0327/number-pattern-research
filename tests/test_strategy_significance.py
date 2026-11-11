"""P2 — strategy_significance tests."""
from __future__ import annotations

import random

from wbc_backend.recommendation.strategy_significance import (
    bootstrap_roi_ci,
    paired_test_vs_zero,
    paired_test_strategies,
    fold_level_stability,
    filter_by_min_edge,
    run_significance_suite,
    INSUFFICIENT_SAMPLE,
    MIN_SAMPLE,
)


def _mk(side_win, odds=-110, edge=0.05, fold=1, stake=0.01, ambiguous=False, pnl_eligible=True):
    return {
        "selected_side_win": side_win,
        "side": "home",
        "bet_side": "HOME",
        "home_ml_odds": odds,
        "away_ml_odds": -110,
        "edge": edge,
        "walk_forward_fold": fold,
        "stake_unit": stake,
        "ambiguous_doubleheader": ambiguous,
        "pnl_eligible": pnl_eligible,
        "ev": 0.05,
        "game_id": f"g_{random.random()}",
        "game_date": "2025-04-01",
    }


# (a) 全勝 bootstrap CI 為正
def test_all_wins_ci_positive():
    recs = [_mk(1) for _ in range(60)]
    out = bootstrap_roi_ci(recs, n_boot=500)
    assert out["status"] == "ok"
    assert out["ci_low"] > 0
    assert out["roi"] > 0


# (b) 全敗 CI 為負
def test_all_losses_ci_negative():
    recs = [_mk(0) for _ in range(60)]
    out = bootstrap_roi_ci(recs, n_boot=500)
    assert out["status"] == "ok"
    assert out["ci_high"] < 0


# (c) 隨機 50/50 樣本 p > 0.05
def test_random_sample_pvalue_not_significant():
    rng = random.Random(123)
    recs = [_mk(rng.randint(0, 1)) for _ in range(200)]
    pv = paired_test_vs_zero(recs, n_boot=500)
    assert pv["status"] == "ok"
    assert pv["p_value"] > 0.05


# (d) 明顯 edge p < 0.05
def test_clear_edge_pvalue_significant():
    rng = random.Random(7)
    # 70% 勝率，-110 odds → 顯著為正
    recs = [_mk(1 if rng.random() < 0.7 else 0) for _ in range(200)]
    pv = paired_test_vs_zero(recs, n_boot=500)
    assert pv["status"] == "ok"
    assert pv["p_value"] < 0.05


# (e) fold 數正確
def test_fold_count_correct():
    recs = []
    for f in (1, 2, 3, 4, 5):
        for _ in range(20):
            recs.append(_mk(1 if f % 2 == 0 else 0, fold=f))
    stab = fold_level_stability(recs)
    assert stab["status"] == "ok"
    assert stab["n_folds"] == 5


# (f) ambiguous_doubleheader 被排除
def test_ambiguous_doubleheader_excluded():
    recs = [_mk(1) for _ in range(40)]
    for r in recs[:10]:
        r["ambiguous_doubleheader"] = True
        r["pnl_eligible"] = False
    out = bootstrap_roi_ci(recs, n_boot=300)
    assert out["status"] == "ok"
    assert out["n"] == 30  # 排除 10 個 ambiguous


# (g) n < 30 → insufficient_sample
def test_insufficient_sample():
    recs = [_mk(1) for _ in range(20)]
    out = bootstrap_roi_ci(recs, n_boot=200)
    assert out["status"] == INSUFFICIENT_SAMPLE
    assert out["n"] == 20
    assert out["min_required"] == MIN_SAMPLE
    pv = paired_test_vs_zero(recs, n_boot=200)
    assert pv["status"] == INSUFFICIENT_SAMPLE


# (h) paper_only 維持 true
def test_paper_only_preserved_in_output():
    recs = [_mk(1) for _ in range(40)]
    out = bootstrap_roi_ci(recs, n_boot=200)
    assert out["paper_only"] is True
    pv = paired_test_vs_zero(recs, n_boot=200)
    assert pv["paper_only"] is True
    stab = fold_level_stability(recs)
    assert stab["paper_only"] is True


# 額外：paired_test_strategies works
def test_paired_strategies_runs():
    rng = random.Random(1)
    a = [_mk(1 if rng.random() < 0.6 else 0) for _ in range(60)]
    b = [_mk(1 if rng.random() < 0.5 else 0) for _ in range(60)]
    out = paired_test_strategies(a, b, n_boot=200)
    assert out["status"] == "ok"
    assert 0.0 <= out["p_value"] <= 1.0


def test_filter_by_min_edge():
    recs = [_mk(1, edge=0.01), _mk(1, edge=0.05), _mk(1, edge=0.10)]
    assert len(filter_by_min_edge(recs, 0.05)) == 2


def test_run_significance_suite_smoke():
    recs = [_mk(1 if i % 3 != 0 else 0, edge=0.03 + (i % 5) * 0.01) for i in range(120)]
    out = run_significance_suite(recs, [0.01, 0.03, 0.05], n_boot=200)
    assert "fixed_edge_1pct" in out
    assert "fixed_edge_5pct" in out
    for entry in out.values():
        assert entry["paper_only"] is True
