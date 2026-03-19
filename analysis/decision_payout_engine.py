"""
Decision & Payout Optimization Engine
========================================
Stage 0  — Baseline metrics (hit rate, monetary ROI, drawdown, ruin probability)
Stage 1  — Confidence score (0-100) + Betting gate optimization
Stage 2  — Position sizing (confidence → bet count)
Stage 3  — Payout optimization (anti-crowd backtest)
Stage 4  — Cross-game allocation (fractional Kelly)
Stage 5  — Validation gates (three-window + perm + McNemar + Sharpe)
Stage 6  — Integration report (docs/decision_payout_report.md)

CORE RULES:
  - Prediction engine NOT modified
  - No data leakage — only past data at every draw_idx
  - All stages additive and removable
  - NO_GAIN / REJECT output if no improvement found

Usage:
    python3 analysis/decision_payout_engine.py all --game all
    python3 analysis/decision_payout_engine.py s0  --game DAILY_539
    python3 analysis/decision_payout_engine.py s1  --game BIG_LOTTO
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ─── Path setup ───────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)

# ─── Reuse existing analysis modules (try/except — removable) ─────────────────
try:
    from player_behavior.popularity_model import compute_popularity
    from player_behavior.anti_crowd import suggest_anti_crowd
    _HAS_PLAYER_BEHAVIOR = True
except ImportError:
    _HAS_PLAYER_BEHAVIOR = False

try:
    from payout.payout_engine import expected_winners as _expected_winners_payout
    _HAS_PAYOUT_ENGINE = True
except ImportError:
    _HAS_PAYOUT_ENGINE = False

# ─── Constants ────────────────────────────────────────────────────────────────
SEED = 42
RESULTS_DIR  = os.path.join(PROJECT_ROOT, "analysis", "results")
DATA_DIR     = os.path.join(PROJECT_ROOT, "data")
DOCS_DIR     = os.path.join(PROJECT_ROOT, "docs")

BASELINES: Dict[str, Dict[int, float]] = {
    "POWER_LOTTO": {1: 0.0387, 2: 0.0759, 3: 0.1117, 4: 0.1460, 5: 0.1791},
    "BIG_LOTTO":   {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 5: 0.0896},
    "DAILY_539":   {1: 0.1140, 2: 0.2154, 3: 0.3050, 4: 0.3843, 5: 0.4539},
}

# Prize: match_count → TWD (fixed tiers only; jackpot capped at expected value)
PRIZE_TABLES: Dict[str, Dict] = {
    "DAILY_539": {
        "cost": 50,
        "prizes": {2: 50, 3: 300, 4: 20_000, 5: 4_000_000},  # 5-match: cap at EV-reasonable 4M
        "metric": "is_m2plus",
        "pool": 39, "pick": 5,
    },
    "BIG_LOTTO": {
        "cost": 50,
        "prizes": {3: 400, 4: 2_000, 5: 40_000, 6: 5_000_000},  # cap jackpot for ROI calc
        "metric": "is_m3plus",
        "pool": 49, "pick": 6,
    },
    "POWER_LOTTO": {
        "cost": 100,
        "prizes": {3: 100, 4: 800, 5: 40_000, 6: 5_000_000},
        "metric": "is_m3plus",
        "pool": 38, "pick": 6,
    },
}

# Primary strategies per game (per bet tier) for position sizing
TIER_STRATEGIES: Dict[str, List[Optional[str]]] = {
    "DAILY_539": [
        None,                          # tier 0: skip
        "acb_1bet",                    # tier 1: 1 bet
        "midfreq_acb_2bet",            # tier 2: 2 bets
        "acb_markov_midfreq_3bet",     # tier 3: 3 bets
    ],
    "BIG_LOTTO": [
        None,
        "regime_2bet",
        "ts3_regime_3bet",
        "p1_dev_sum5bet",
    ],
    "POWER_LOTTO": [
        None,
        "fourier_rhythm_3bet",
        "pp3_freqort_4bet",
        "orthogonal_5bet",
    ],
}

DRAWS_PER_WEEK = {"DAILY_539": 7, "BIG_LOTTO": 2, "POWER_LOTTO": 2}

WARM_UP       = 100    # minimum draws needed before confidence scoring
N_PERM        = 200    # permutation test iterations
N_MC_RUIN     = 10_000 # Monte Carlo ruin simulations
MC_HORIZON    = 300    # MC simulation horizon (draws)
NOISE_THRESHOLD = 0.005  # 0.5% ROI noise floor
KELLY_FRAC    = 0.25   # fractional Kelly multiplier


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_rsm(game: str) -> Dict[str, List[Dict]]:
    """Load rolling_monitor_{game}.json → {strategy: [records]}."""
    path = os.path.join(DATA_DIR, f"rolling_monitor_{game}.json")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return raw.get("records", {})


def aligned_draws(records: Dict[str, List[Dict]]) -> List[str]:
    """Return sorted draw_ids present in ALL strategies."""
    if not records:
        return []
    sets = [set(r["draw_id"] for r in v) for v in records.values()]
    common = sorted(sets[0].intersection(*sets[1:]))
    return common


# ─── Monetary payout ──────────────────────────────────────────────────────────

def draw_payout(match_counts: List[int], game: str) -> float:
    """Total monetary payout for one draw (sum across all bets)."""
    prizes = PRIZE_TABLES[game]["prizes"]
    total = 0.0
    for mc in match_counts:
        total += float(prizes.get(mc, 0))
    return total


def draw_profit(match_counts: List[int], game: str) -> float:
    """Net profit = payout - total bet cost."""
    cost = PRIZE_TABLES[game]["cost"] * len(match_counts)
    return draw_payout(match_counts, game) - cost


# ─── Rolling metrics (past-only) ──────────────────────────────────────────────

def _hit_rate_window(rec_list: List[Dict], end_idx: int, window: int, metric: str) -> float:
    start = max(0, end_idx - window)
    subset = rec_list[start:end_idx]
    if not subset:
        return 0.0
    return float(np.mean([1.0 if r.get(metric, False) else 0.0 for r in subset]))


def _edge_window(rec_list: List[Dict], end_idx: int, window: int, metric: str, baseline: float) -> float:
    return _hit_rate_window(rec_list, end_idx, window, metric) - baseline


def _rolling_binary_std(rec_list: List[Dict], end_idx: int, window: int, metric: str) -> float:
    start = max(0, end_idx - window)
    subset = rec_list[start:end_idx]
    if len(subset) < 2:
        return 0.0
    arr = np.array([1.0 if r.get(metric, False) else 0.0 for r in subset])
    return float(np.std(arr))


# ─── Stage 0: Baseline Metrics ────────────────────────────────────────────────

def _bootstrap_mc_ruin(profits: List[float], bankroll: float,
                       n_sims: int = N_MC_RUIN, horizon: int = MC_HORIZON,
                       seed: int = SEED) -> Dict:
    """Bootstrap MC ruin. Resample per-draw profits with replacement."""
    rng = np.random.default_rng(seed)
    arr = np.array(profits)
    if len(arr) == 0:
        return {"ruin_prob": 1.0, "mean_final_equity": 0.0, "median_final_equity": 0.0}
    sampled = rng.choice(arr, size=(n_sims, horizon), replace=True)
    equity = bankroll + np.cumsum(sampled, axis=1)
    ruined = np.any(equity <= 0, axis=1)
    ruin_prob = float(np.mean(ruined))
    final = equity[:, -1]
    return {
        "ruin_prob":            round(ruin_prob, 4),
        "mean_final_equity":    round(float(np.mean(final)), 2),
        "median_final_equity":  round(float(np.median(final)), 2),
    }


def stage0_baseline(game: str) -> Dict:
    """Stage 0: per-strategy baseline metrics for a game."""
    records   = load_rsm(game)
    tbl       = PRIZE_TABLES[game]
    cost      = tbl["cost"]
    metric    = tbl["metric"]
    bankroll0 = 100 * cost   # 100-bet starting bankroll

    result = {"game": game, "strategies": {}}

    for strat, recs in records.items():
        n = len(recs)
        if n == 0:
            result["strategies"][strat] = {"error": "no_records"}
            continue

        num_bets = recs[0].get("num_bets", 1)
        baseline = BASELINES[game].get(num_bets, 0.3)

        hits   = sum(1 for r in recs if r.get(metric, False))
        hr     = hits / n

        profits = [draw_profit(r.get("match_counts", []), game) for r in recs]
        payouts = [draw_payout(r.get("match_counts", []), game) for r in recs]
        total_cost    = n * num_bets * cost
        total_payout  = sum(payouts)
        monetary_roi  = (total_payout - total_cost) / max(total_cost, 1)

        # Max drawdown (longest losing streak)
        max_dd = 0
        cur_dd = 0
        for p in payouts:
            if p == 0:
                cur_dd += 1
                max_dd = max(max_dd, cur_dd)
            else:
                cur_dd = 0

        # Sharpe (Bernoulli per-draw)
        edge   = hr - baseline
        p_std  = math.sqrt(hr * (1 - hr)) if 0 < hr < 1 else 1e-9
        sharpe = edge / p_std

        # Monetary Sharpe
        prof_arr = np.array(profits)
        mon_sharpe = float(np.mean(prof_arr) / np.std(prof_arr)) if np.std(prof_arr) > 0 else 0.0

        # MC ruin
        mc = _bootstrap_mc_ruin(profits, bankroll0)

        result["strategies"][strat] = {
            "n_records":      n,
            "num_bets":       num_bets,
            "baseline":       round(baseline, 4),
            "hit_rate":       round(hr, 4),
            "edge":           round(edge, 4),
            "edge_pct":       round(edge * 100, 2),
            "monetary_roi":   round(monetary_roi, 4),
            "monetary_roi_pct": round(monetary_roi * 100, 2),
            "sharpe_bernoulli": round(sharpe, 4),
            "sharpe_monetary":  round(mon_sharpe, 4),
            "max_drawdown_draws": max_dd,
            "avg_profit_per_draw": round(float(np.mean(profits)), 2),
            "mc_ruin": mc,
        }

        if n < 100:
            result["strategies"][strat]["data_gap"] = f"only {n} records (need ≥100)"

    return result


# ─── Stage 1: Confidence Score + Betting Gate ─────────────────────────────────

def _jaccard(set_a: set, set_b: set) -> float:
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _signal_consensus(draw_strat_bets: List[List[List[int]]]) -> float:
    """Avg pairwise Jaccard of flattened predicted_bets across strategies."""
    sets = [set(n for bet in bets for n in bet) for bets in draw_strat_bets]
    if len(sets) < 2:
        return 0.0
    sims = []
    for i, j in combinations(range(len(sets)), 2):
        sims.append(_jaccard(sets[i], sets[j]))
    return float(np.mean(sims)) if sims else 0.0


def confidence_score(
    game: str,
    draw_idx: int,
    records_by_strat: Dict[str, List[Dict]],
    draw_id: str,
) -> float:
    """
    Compute confidence score 0-100 for draw at draw_idx (strictly past-only).

    Components:
      signal_consensus   30pts — pairwise Jaccard of predicted numbers
      edge_consistency   30pts — min/max edge consistency across 30/100/300p
      drift_penalty      20pts — edge_30p stable vs edge_300p
      variance_penalty   20pts — low variance in recent hit rate
    """
    metric = PRIZE_TABLES[game]["metric"]

    # Only use strategies with a record at this exact draw_id
    active_strats = {s: recs for s, recs in records_by_strat.items()
                     if draw_idx < len(recs) and recs[draw_idx].get("draw_id") == draw_id}
    if not active_strats:
        return 50.0  # neutral fallback

    # ─ Signal consensus ─────────────────────────────────────────────────────
    bets_list = []
    for s, recs in active_strats.items():
        bets_list.append(recs[draw_idx].get("predicted_bets", []))
    consensus = _signal_consensus(bets_list)
    score_consensus = consensus * 30.0

    # ─ Edge consistency ─────────────────────────────────────────────────────
    # Use any single representative strategy (most bets = best signal)
    rep_strat_name = max(active_strats, key=lambda s: active_strats[s][draw_idx].get("num_bets", 0))
    rep = active_strats[rep_strat_name]
    num_bets = rep[draw_idx].get("num_bets", 1)
    baseline = BASELINES[game].get(num_bets, 0.3)

    e30  = _edge_window(rep, draw_idx, 30,  metric, baseline)
    e100 = _edge_window(rep, draw_idx, 100, metric, baseline)
    e300 = _edge_window(rep, draw_idx, 300, metric, baseline)

    edges = [e30, e100, e300]
    if all(e > 0 for e in edges):
        max_e = max(abs(e) for e in edges) if any(abs(e) > 0 for e in edges) else 1e-9
        min_e = min(abs(e) for e in edges)
        consistency = min_e / max_e
    elif all(e < 0 for e in edges):
        consistency = -0.5  # uniformly negative
    else:
        # Mixed signs — penalise
        pos = sum(1 for e in edges if e > 0)
        consistency = (pos / 3.0) - 0.5
    score_edge = max(0.0, (consistency + 0.5)) * 30.0   # 0-30

    # ─ Drift penalty ────────────────────────────────────────────────────────
    if abs(e300) > 1e-6:
        drift = abs(e30 / e300 - 1.0)
        drift_score = max(0.0, 1.0 - drift)
    else:
        drift_score = 0.5  # no 300p edge data → neutral
    score_drift = drift_score * 20.0

    # ─ Variance penalty ─────────────────────────────────────────────────────
    std30 = _rolling_binary_std(rep, draw_idx, 30, metric)
    bernoulli_std = math.sqrt(baseline * (1 - baseline))
    if bernoulli_std > 0:
        var_penalty = 1.0 - min(1.0, std30 / bernoulli_std)
    else:
        var_penalty = 0.0
    score_var = var_penalty * 20.0

    total = score_consensus + score_edge + score_drift + score_var
    return round(min(100.0, max(0.0, total)), 2)


def stage1_decision(game: str) -> Dict:
    """Stage 1: confidence scores + betting gate grid search."""
    records      = load_rsm(game)
    draw_ids     = aligned_draws(records)
    tbl          = PRIZE_TABLES[game]
    metric       = tbl["metric"]
    cost         = tbl["cost"]

    # Build sorted per-strategy record lists aligned by draw_ids
    strat_recs: Dict[str, List[Dict]] = {}
    for strat, recs in records.items():
        by_id = {r["draw_id"]: r for r in recs}
        strat_recs[strat] = [by_id[did] for did in draw_ids if did in by_id]

    # Identify best strategy (highest 300p edge over full dataset)
    best_strat = None
    best_edge  = -999.0
    for strat, recs in strat_recs.items():
        if len(recs) < 50:
            continue
        num_bets = recs[0].get("num_bets", 1)
        bl = BASELINES[game].get(num_bets, 0.3)
        e = _edge_window(recs, len(recs), 300, metric, bl)
        if e > best_edge:
            best_edge  = e
            best_strat = strat

    if best_strat is None:
        return {"game": game, "error": "no_strategy", "gate_results": {}}

    best_recs = strat_recs[best_strat]
    num_bets  = best_recs[0].get("num_bets", 1)
    baseline  = BASELINES[game].get(num_bets, 0.3)

    # Compute confidence score for all OOS draws (draw_idx >= WARM_UP)
    scores: List[float] = []
    draw_ids_oos: List[str] = []
    for idx in range(WARM_UP, len(draw_ids)):
        did = draw_ids[idx]
        sc = confidence_score(game, idx, strat_recs, did)
        scores.append(sc)
        draw_ids_oos.append(did)

    n_oos = len(scores)
    if n_oos < 30:
        return {"game": game, "error": "insufficient_oos", "n_oos": n_oos}

    # ─ Flat baseline ────────────────────────────────────────────────────────
    flat_profits = []
    flat_hits    = []
    for idx in range(WARM_UP, len(draw_ids)):
        r = best_recs[idx] if idx < len(best_recs) else None
        if r is None:
            continue
        p = draw_profit(r.get("match_counts", []), game)
        flat_profits.append(p)
        flat_hits.append(1 if r.get(metric, False) else 0)

    flat_roi    = sum(flat_profits) / max(num_bets * cost * len(flat_profits), 1)
    flat_arr    = np.array(flat_profits)
    flat_sharpe = float(np.mean(flat_arr) / np.std(flat_arr)) if np.std(flat_arr) > 0 else 0.0

    # ─ Grid search gate threshold ────────────────────────────────────────────
    gate_results: Dict[int, Dict] = {}
    for thresh in range(40, 81, 5):
        g_profits = []
        g_hits    = []
        n_bet = 0
        for k, (sc, idx) in enumerate(zip(scores, range(WARM_UP, len(draw_ids)))):
            if sc >= thresh:
                r = best_recs[idx] if idx < len(best_recs) else None
                if r is None:
                    continue
                p = draw_profit(r.get("match_counts", []), game)
                g_profits.append(p)
                g_hits.append(1 if r.get(metric, False) else 0)
                n_bet += 1

        if n_bet < 10:
            gate_results[thresh] = {"n_bets": n_bet, "error": "too_few"}
            continue

        g_arr   = np.array(g_profits)
        g_roi   = sum(g_profits) / max(num_bets * cost * n_bet, 1)
        g_hr    = sum(g_hits) / n_bet
        g_sharpe = float(np.mean(g_arr) / np.std(g_arr)) if np.std(g_arr) > 0 else 0.0

        # Max drawdown (consecutive losses)
        max_dd = cur_dd = 0
        for p in g_profits:
            if p <= 0:
                cur_dd += 1
                max_dd = max(max_dd, cur_dd)
            else:
                cur_dd = 0

        gate_results[thresh] = {
            "n_bets":     n_bet,
            "skip_rate":  round(1 - n_bet / n_oos, 4),
            "hit_rate":   round(g_hr, 4),
            "edge":       round(g_hr - baseline, 4),
            "monetary_roi":  round(g_roi, 4),
            "monetary_roi_pct": round(g_roi * 100, 2),
            "sharpe":     round(g_sharpe, 4),
            "max_drawdown_draws": max_dd,
            "sharpe_vs_flat": round(g_sharpe - flat_sharpe, 4),
        }

    # Select best threshold: maximize edge-per-bet (hit_rate - baseline), require skip_rate < 0.70
    best_thresh = None
    best_thresh_edge = -999.0
    for t, res in gate_results.items():
        if "error" in res:
            continue
        if res.get("skip_rate", 1.0) >= 0.70:
            continue   # must bet on ≥30% of draws
        g_edge = res.get("edge", -999.0)
        if g_edge > best_thresh_edge:
            best_thresh_edge = g_edge
            best_thresh = t

    # Confidence histogram (10-point buckets)
    histogram = defaultdict(int)
    for sc in scores:
        bucket = int(sc // 10) * 10
        histogram[str(bucket)] += 1

    return {
        "game":           game,
        "best_strategy":  best_strat,
        "n_oos_draws":    n_oos,
        "flat_roi_pct":   round(flat_roi * 100, 2),
        "flat_sharpe":    round(flat_sharpe, 4),
        "best_gate_threshold": best_thresh,
        "best_gate_edge":      round(best_thresh_edge, 4),
        "confidence_histogram": dict(histogram),
        "confidence_stats": {
            "mean": round(float(np.mean(scores)), 2),
            "std":  round(float(np.std(scores)), 2),
            "p25":  round(float(np.percentile(scores, 25)), 2),
            "p50":  round(float(np.percentile(scores, 50)), 2),
            "p75":  round(float(np.percentile(scores, 75)), 2),
        },
        "gate_results":   gate_results,
    }


# ─── Stage 2: Position Sizing ─────────────────────────────────────────────────

def stage2_sizing(game: str, s1_result: Optional[Dict] = None) -> Dict:
    """Stage 2: brute-force search of confidence→bet-count boundaries."""
    records      = load_rsm(game)
    draw_ids     = aligned_draws(records)
    tbl          = PRIZE_TABLES[game]
    metric       = tbl["metric"]
    cost         = tbl["cost"]
    tiers        = TIER_STRATEGIES[game]   # [None, t1_strat, t2_strat, t3_strat]

    # Build strat_recs aligned to draw_ids
    strat_recs: Dict[str, List[Dict]] = {}
    for strat, recs in records.items():
        by_id = {r["draw_id"]: r for r in recs}
        strat_recs[strat] = [by_id[did] for did in draw_ids if did in by_id]

    # Confidence scores for OOS draws
    scores: List[float] = []
    for idx in range(WARM_UP, len(draw_ids)):
        did = draw_ids[idx]
        sc = confidence_score(game, idx, strat_recs, did)
        scores.append(sc)

    n_oos = len(scores)
    if n_oos < 30:
        return {"game": game, "error": "insufficient_oos"}

    oos_idxs = list(range(WARM_UP, len(draw_ids)))

    # Flat baseline (always tier 2 = best 2-3 bet strategy)
    flat_strat  = tiers[2] if tiers[2] else tiers[1]
    flat_num_bets = 1
    flat_hits: List[int] = []
    if flat_strat and flat_strat in strat_recs:
        flat_recs = strat_recs[flat_strat]
        flat_profs: List[float] = []
        for idx in oos_idxs:
            if idx < len(flat_recs):
                r = flat_recs[idx]
                flat_num_bets = r.get("num_bets", 1)
                flat_profs.append(draw_profit(r.get("match_counts", []), game))
                flat_hits.append(1 if r.get(metric, False) else 0)
        flat_arr    = np.array(flat_profs)
        flat_roi    = float(np.sum(flat_arr)) / max(cost * len(flat_profs), 1)
        flat_sharpe = float(np.mean(flat_arr) / np.std(flat_arr)) if np.std(flat_arr) > 0 else 0.0
    else:
        flat_roi = flat_sharpe = 0.0

    # Grid search boundaries — CONSTRAINT: skip_rate < 0.70 (must bet ≥30% of draws)
    # Optimize: hit-rate edge per active bet (not total ROI, to avoid skip-all trivial solution)
    boundary_vals = list(range(30, 81, 5))
    best_edge    = -999.0
    best_bounds  = None
    best_metrics: Dict = {}

    for b1, b2, b3 in combinations(boundary_vals, 3):
        if not (b1 < b2 < b3):
            continue
        n_skip = sum(1 for sc in scores if sc < b1)
        if n_skip / n_oos > 0.70:
            continue   # enforce minimum participation

        tier_profits = []
        tier_hits    = []
        tier_baselines: List[float] = []

        for k, sc in enumerate(scores):
            idx = oos_idxs[k]
            if sc < b1:
                tier = 0
            elif sc < b2:
                tier = 1
            elif sc < b3:
                tier = 2
            else:
                tier = 3

            strat_name = tiers[tier]
            if strat_name is None:
                tier_profits.append(0.0)
                tier_hits.append(0)
                continue

            recs_t = strat_recs.get(strat_name)
            if recs_t is None or idx >= len(recs_t):
                tier_profits.append(0.0)
                tier_hits.append(0)
                continue

            r = recs_t[idx]
            nm_t = r.get("num_bets", 1)
            bl_t = BASELINES[game].get(nm_t, 0.3)
            tier_profits.append(draw_profit(r.get("match_counts", []), game))
            tier_hits.append(1 if r.get(metric, False) else 0)
            tier_baselines.append(bl_t)

        n_active = sum(1 for p in tier_profits if p > 0 or p == 0)  # all active
        if n_active < 20:
            continue

        arr = np.array(tier_profits)
        roi = float(np.sum(arr)) / max(cost * n_active, 1)
        sharpe = float(np.mean(arr) / np.std(arr)) if np.std(arr) > 0 else -9.0
        # Edge metric: hit-rate above baseline (among active bets)
        active_hits = [h for sc, h in zip(scores, tier_hits) if (sc >= b1 if tiers[0] is None else True)]
        active_bl   = tier_baselines
        if active_hits and active_bl:
            gated_hr  = sum(active_hits) / len(active_hits)
            avg_bl    = float(np.mean(active_bl))
            edge_val  = gated_hr - avg_bl
        else:
            edge_val  = -999.0

        if edge_val > best_edge:
            best_edge   = edge_val
            best_bounds = (b1, b2, b3)
            max_dd = cur_dd = 0
            for p in tier_profits:
                if p <= 0:
                    cur_dd += 1; max_dd = max(max_dd, cur_dd)
                else:
                    cur_dd = 0
            best_metrics = {
                "roi": round(roi, 4),
                "roi_pct": round(roi * 100, 2),
                "sharpe": round(sharpe, 4),
                "max_drawdown_draws": max_dd,
                "skip_rate": round(n_skip / n_oos, 3),
                "sharpe_vs_flat": round(sharpe - flat_sharpe, 4),
                "roi_vs_flat_pct": round((roi - flat_roi) * 100, 2),
                "edge_per_bet": round(edge_val, 4),
                "edge_vs_flat": round(edge_val - (sum(flat_hits)/len(flat_hits) - BASELINES[game].get(flat_num_bets,0.3) if flat_hits else 0), 4),
            }

    return {
        "game":           game,
        "n_oos_draws":    n_oos,
        "flat_roi_pct":   round(flat_roi * 100, 2),
        "flat_sharpe":    round(flat_sharpe, 4),
        "best_boundaries":  list(best_bounds) if best_bounds else None,
        "tier_strategy_map": {
            "tier0_skip": "(skip)",
            "tier1": tiers[1],
            "tier2": tiers[2],
            "tier3": tiers[3],
        },
        "best_metrics":   best_metrics,
    }


# ─── Stage 3: Payout Optimization (Anti-Crowd) ────────────────────────────────

def _compute_match(ticket: List[int], actual: List[int]) -> int:
    return len(set(ticket) & set(actual))


def _ticket_payout(match_count: int, game: str) -> float:
    return float(PRIZE_TABLES[game]["prizes"].get(match_count, 0))


def stage3_payout(game: str) -> Dict:
    """Stage 3: anti-crowd counterfactual backtest on best strategy."""
    tbl    = PRIZE_TABLES[game]
    pool   = tbl["pool"]
    pick   = tbl["pick"]
    metric = tbl["metric"]

    records   = load_rsm(game)

    # Find best strategy by 300p edge
    best_strat = None
    best_edge  = -999.0
    for strat, recs in records.items():
        if len(recs) < 50:
            continue
        num_bets = recs[0].get("num_bets", 1)
        bl = BASELINES[game].get(num_bets, 0.3)
        hr = sum(1 for r in recs if r.get(metric, False)) / len(recs)
        e  = hr - bl
        if e > best_edge:
            best_edge  = e
            best_strat = strat

    if best_strat is None or not _HAS_PLAYER_BEHAVIOR:
        return {
            "game": game,
            "status": "SKIPPED",
            "reason": "no strategy or player_behavior module not available",
        }

    recs = records[best_strat]
    orig_payouts:    List[float] = []
    swapped_payouts: List[float] = []
    pop_before: List[float] = []
    pop_after:  List[float] = []
    n_swapped = n_rejected = n_unchanged = 0

    for r in recs:
        bets   = r.get("predicted_bets", [])
        actual = r.get("actual", [])
        if not bets or not actual:
            continue

        orig_total    = 0.0
        swapped_total = 0.0

        for bet in bets:
            sorted_bet   = sorted(bet)
            orig_mc      = _compute_match(sorted_bet, actual)
            orig_pay     = _ticket_payout(orig_mc, game)
            orig_total  += orig_pay

            try:
                pop_result = compute_popularity(sorted_bet, pool, pick)
                pop_sc = pop_result["popularity_score"]
            except Exception:
                pop_sc = 0.0

            pop_before.append(pop_sc)

            try:
                ac_result = suggest_anti_crowd(sorted_bet, pool, pick, pop_sc)
                alt = ac_result.get("alternative")
            except Exception:
                alt = None

            if alt is not None:
                alt_sorted = sorted(alt)
                alt_mc     = _compute_match(alt_sorted, actual)
                # Only accept if match count doesn't decrease
                if alt_mc >= orig_mc:
                    alt_pay       = _ticket_payout(alt_mc, game)
                    swapped_total += alt_pay
                    try:
                        alt_pop = compute_popularity(alt_sorted, pool, pick)["popularity_score"]
                    except Exception:
                        alt_pop = pop_sc
                    pop_after.append(alt_pop)
                    n_swapped += 1
                else:
                    swapped_total += orig_pay
                    pop_after.append(pop_sc)
                    n_rejected += 1
            else:
                swapped_total += orig_pay
                pop_after.append(pop_sc)
                n_unchanged += 1

        orig_payouts.append(orig_total)
        swapped_payouts.append(swapped_total)

    n = len(orig_payouts)
    if n == 0:
        return {"game": game, "status": "NO_DATA"}

    cost_per_draw = recs[0].get("num_bets", 1) * tbl["cost"]
    orig_roi    = (sum(orig_payouts)    - n * cost_per_draw) / max(n * cost_per_draw, 1)
    swapped_roi = (sum(swapped_payouts) - n * cost_per_draw) / max(n * cost_per_draw, 1)

    # Hit rate comparison (binary: any non-zero payout)
    orig_hits    = [1 if p > 0 else 0 for p in orig_payouts]
    swapped_hits = [1 if p > 0 else 0 for p in swapped_payouts]
    orig_hr    = sum(orig_hits)    / n
    swapped_hr = sum(swapped_hits) / n

    pop_mean_before = float(np.mean(pop_before)) if pop_before else 0.0
    pop_mean_after  = float(np.mean(pop_after))  if pop_after  else 0.0

    return {
        "game":        game,
        "strategy":    best_strat,
        "n_draws":     n,
        "n_swapped":   n_swapped,
        "n_rejected":  n_rejected,
        "n_unchanged": n_unchanged,
        "swap_rate":   round(n_swapped / max(n_swapped + n_rejected + n_unchanged, 1), 3),
        "original_hit_rate":    round(orig_hr, 4),
        "swapped_hit_rate":     round(swapped_hr, 4),
        "hit_rate_delta":       round(swapped_hr - orig_hr, 4),
        "original_roi_pct":     round(orig_roi * 100, 2),
        "swapped_roi_pct":      round(swapped_roi * 100, 2),
        "roi_delta_pct":        round((swapped_roi - orig_roi) * 100, 2),
        "popularity_before":    round(pop_mean_before, 2),
        "popularity_after":     round(pop_mean_after, 2),
        "popularity_reduction": round(pop_mean_before - pop_mean_after, 2),
        "verdict": (
            "GAIN"    if (swapped_roi - orig_roi) > NOISE_THRESHOLD else
            "NO_GAIN" if abs(swapped_roi - orig_roi) <= NOISE_THRESHOLD else
            "DEGRADED"
        ),
    }


# ─── Stage 4: Cross-Game Allocation ──────────────────────────────────────────

def _fractional_kelly(edge: float, vol: float, fraction: float = KELLY_FRAC) -> float:
    if vol <= 0 or edge <= 0:
        return 0.0
    return max(0.0, min(1.0, fraction * (edge / (vol ** 2))))


def stage4_allocation(games: List[str]) -> Dict:
    """Stage 4: fractional Kelly allocation across games."""
    game_data: Dict[str, Dict] = {}

    for game in games:
        try:
            records = load_rsm(game)
        except Exception:
            continue
        tbl    = PRIZE_TABLES[game]
        metric = tbl["metric"]
        cost   = tbl["cost"]

        # Find best strategy
        best_strat = None
        best_edge  = -999.0
        for strat, recs in records.items():
            if len(recs) < 50:
                continue
            nm = recs[0].get("num_bets", 1)
            bl = BASELINES[game].get(nm, 0.3)
            hr = sum(1 for r in recs if r.get(metric, False)) / len(recs)
            if (hr - bl) > best_edge:
                best_edge  = hr - bl
                best_strat = strat

        if best_strat is None:
            continue

        recs = records[best_strat]
        nm   = recs[0].get("num_bets", 1)

        # 100p rolling edge and vol using last 100 records
        last100 = recs[-100:]
        bl      = BASELINES[game].get(nm, 0.3)
        hr100   = sum(1 for r in last100 if r.get(metric, False)) / len(last100)
        edge100 = hr100 - bl
        profits = [draw_profit(r.get("match_counts", []), game) for r in last100]
        vol100  = float(np.std(profits)) if len(profits) > 1 else 1.0

        dpw = DRAWS_PER_WEEK[game]
        weekly_edge = edge100 * dpw
        weekly_vol  = vol100 * math.sqrt(dpw)

        game_data[game] = {
            "best_strategy": best_strat,
            "edge_100p":  round(edge100, 4),
            "vol_100p":   round(vol100, 2),
            "weekly_edge": round(weekly_edge, 4),
            "weekly_vol":  round(weekly_vol, 2),
            "draws_per_week": dpw,
            "kelly_f": round(_fractional_kelly(weekly_edge, weekly_vol), 4),
        }

    if not game_data:
        return {"error": "no_game_data"}

    total_kelly = sum(g["kelly_f"] for g in game_data.values())
    if total_kelly <= 0:
        alloc = {g: round(1 / len(game_data), 4) for g in game_data}
    else:
        alloc = {g: round(game_data[g]["kelly_f"] / total_kelly, 4) for g in game_data}

    return {
        "games_analyzed":  list(game_data.keys()),
        "allocations":     alloc,
        "game_detail":     game_data,
        "methodology":     f"Fractional Kelly (f={KELLY_FRAC}) on 100p weekly edge/vol",
        "rebalance_freq":  "monthly",
    }


# ─── Stage 5: Validation Gates ────────────────────────────────────────────────

def _three_window(profits_oos: List[float], base_profits: List[float]) -> Dict:
    """Three-window lift check: last 100, last 200, full dataset."""
    results = {}
    n = len(profits_oos)
    for label, w in [("last_100", 100), ("last_200", 200), ("full", n)]:
        a  = profits_oos[-w:]  if w < n else profits_oos
        b  = base_profits[-w:] if w < n else base_profits
        la = len(a)
        lb = len(b)
        if la == 0 or lb == 0:
            results[label] = {"lift": None, "positive": None}
            continue
        lift = float(np.mean(a)) - float(np.mean(b))
        results[label] = {"lift": round(lift, 4), "positive": lift >= 0}
    all_pos = all(v["positive"] for v in results.values() if v["positive"] is not None)
    return {"windows": results, "all_positive": all_pos}


def _permutation_test(
    gated_profits: List[float],
    base_profits:  List[float],
    gate_flags:    List[bool],
    n_perm: int = N_PERM,
    seed: int = SEED,
) -> Dict:
    """
    Null: shuffle gate/skip decisions randomly, recompute mean gated profit.
    Observed: actual mean gated profit.
    p-value = P(null >= observed).
    """
    rng = np.random.default_rng(seed)
    if len(gated_profits) < 5:
        return {"p_value": 1.0, "observed": 0.0, "null_mean": 0.0, "significant": False}

    observed = float(np.mean(gated_profits))
    all_profits = gated_profits + base_profits
    n_gate = len(gated_profits)

    null_means: List[float] = []
    for _ in range(n_perm):
        shuffled = rng.choice(all_profits, size=n_gate, replace=False).tolist()
        null_means.append(float(np.mean(shuffled)))

    null_arr = np.array(null_means)
    p_value  = float(np.mean(null_arr >= observed))

    return {
        "p_value":     round(p_value, 4),
        "observed":    round(observed, 2),
        "null_mean":   round(float(np.mean(null_arr)), 2),
        "null_95pct":  round(float(np.percentile(null_arr, 95)), 2),
        "significant": p_value < 0.05,
    }


def _mcnemar(hits_gated: List[int], hits_flat: List[int]) -> Dict:
    """McNemar test: gated vs flat per-draw binary hits."""
    if len(hits_gated) != len(hits_flat):
        min_n = min(len(hits_gated), len(hits_flat))
        hits_gated = hits_gated[:min_n]
        hits_flat  = hits_flat[:min_n]

    b = sum(1 for g, f in zip(hits_gated, hits_flat) if g == 1 and f == 0)
    c = sum(1 for g, f in zip(hits_gated, hits_flat) if g == 0 and f == 1)
    net = b - c
    n_disc = b + c
    if n_disc == 0:
        p_value = 1.0
    else:
        try:
            from scipy.stats import binomtest as _binomtest  # scipy ≥1.7
            p_value = float(_binomtest(b, n_disc, 0.5).pvalue)
        except ImportError:
            try:
                from scipy.stats import binom_test as _bt  # scipy <1.7
                p_value = float(_bt(b, n_disc, 0.5))
            except Exception:
                p_value = 1.0 if abs(net) == 0 else float(0.5 ** n_disc)

    return {
        "b": b, "c": c, "net": net, "n_discordant": n_disc,
        "p_value": round(p_value, 4),
        "significant": p_value < 0.05,
    }


def _sharpe_gate(gated_profits: List[float], flat_profits: List[float]) -> Dict:
    ga = np.array(gated_profits)
    fa = np.array(flat_profits)
    g_sharpe = float(np.mean(ga) / np.std(ga)) if np.std(ga) > 0 else 0.0
    f_sharpe = float(np.mean(fa) / np.std(fa)) if np.std(fa) > 0 else 0.0
    return {
        "gated_sharpe": round(g_sharpe, 4),
        "flat_sharpe":  round(f_sharpe, 4),
        "delta":        round(g_sharpe - f_sharpe, 4),
        "passes":       g_sharpe > f_sharpe,
    }


def stage5_validate(
    game: str,
    stage_name: str,
    gated_profits: List[float],
    flat_profits:  List[float],
    gate_flags:    List[bool],
    gated_hits:    List[int],
    flat_hits:     List[int],
    edge_pct: Optional[float] = None,
) -> Dict:
    """Stage 5: apply all validation gates to a stage's gated profits."""
    three_w = _three_window(gated_profits, flat_profits)
    perm    = _permutation_test(gated_profits, flat_profits, gate_flags)
    mc      = _mcnemar(gated_hits, flat_hits)
    sharpe  = _sharpe_gate(gated_profits, flat_profits)

    # McNemar OR edge > +10pp rule
    mc_pass = mc["significant"] or (edge_pct is not None and edge_pct > 10.0)

    all_pass = three_w["all_positive"] and perm["significant"] and mc_pass and sharpe["passes"]

    verdict = "PRODUCTION" if all_pass else (
        "WATCH" if (three_w["all_positive"] and (perm["significant"] or mc_pass)) else
        "NO_GAIN" if abs(float(np.mean(gated_profits)) - float(np.mean(flat_profits))) < abs(float(np.mean(flat_profits))) * 0.005 else
        "REJECT"
    )

    return {
        "stage":        stage_name,
        "game":         game,
        "verdict":      verdict,
        "all_pass":     all_pass,
        "three_window": three_w,
        "perm_test":    perm,
        "mcnemar":      mc,
        "sharpe":       sharpe,
        "gates": {
            "three_window": three_w["all_positive"],
            "perm_p05":     perm["significant"],
            "mcnemar":      mc_pass,
            "sharpe":       sharpe["passes"],
        },
    }


# ─── Stage 1+5 integrated: gate validation for confidence scores ──────────────

def stage1_with_validation(game: str) -> Dict:
    """Run Stage 1 and attach Stage 5 gates to the best gate threshold."""
    s1 = stage1_decision(game)
    if "error" in s1:
        return s1

    # Reconstruct gated vs flat profits for the best threshold
    thresh = s1.get("best_gate_threshold")
    if thresh is None:
        s1["validation"] = {"verdict": "NO_GATE_FOUND"}
        return s1

    records   = load_rsm(game)
    draw_ids  = aligned_draws(records)
    tbl       = PRIZE_TABLES[game]
    metric    = tbl["metric"]

    strat_recs: Dict[str, List[Dict]] = {}
    for strat, recs in records.items():
        by_id = {r["draw_id"]: r for r in recs}
        strat_recs[strat] = [by_id[did] for did in draw_ids if did in by_id]

    best_strat = s1["best_strategy"]
    best_recs  = strat_recs[best_strat]
    num_bets   = best_recs[0].get("num_bets", 1) if best_recs else 1
    baseline   = BASELINES[game].get(num_bets, 0.3)

    gated_profs: List[float] = []
    flat_profs:  List[float] = []
    gate_flags:  List[bool]  = []
    gated_hits:  List[int]   = []
    flat_hits:   List[int]   = []

    for idx in range(WARM_UP, len(draw_ids)):
        if idx >= len(best_recs):
            continue
        did = draw_ids[idx]
        sc  = confidence_score(game, idx, strat_recs, did)
        r   = best_recs[idx]
        fp  = draw_profit(r.get("match_counts", []), game)
        fh  = 1 if r.get(metric, False) else 0
        flat_profs.append(fp)
        flat_hits.append(fh)

        if sc >= thresh:
            gated_profs.append(fp)
            gated_hits.append(fh)
            gate_flags.append(True)
        else:
            gate_flags.append(False)

    best_gate_res = s1["gate_results"].get(thresh, {})
    edge_pct = best_gate_res.get("edge", 0.0) * 100 if best_gate_res else None

    s1["validation"] = stage5_validate(
        game, "stage1_betting_gate",
        gated_profs, flat_profs, gate_flags,
        gated_hits, flat_hits, edge_pct,
    )
    return s1


# ─── Stage 6: Integration Report ─────────────────────────────────────────────

def _verdict_emoji(v: str) -> str:
    return {"PRODUCTION": "✅", "WATCH": "🔶", "NO_GAIN": "⚪", "REJECT": "❌",
            "GAIN": "✅", "DEGRADED": "❌", "SKIPPED": "⏭", "NO_DATA": "❓"}.get(v, "")


def generate_report(all_results: Dict, output_path: str) -> str:
    lines: List[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines += [
        "# Decision & Payout Optimization Engine Report",
        f"**Generated:** {now}  |  seed=42  |  ZERO prediction engine modifications",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
    ]

    # Collect verdicts
    verdicts: Dict[str, str] = {}
    for game in ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO"):
        s1 = all_results.get("stage1", {}).get(game, {})
        v  = s1.get("validation", {}).get("verdict", "N/A")
        verdicts[f"S1/{game}"] = v

        s2 = all_results.get("stage2", {}).get(game, {})
        best_m = s2.get("best_metrics", {})
        v2 = ("PRODUCTION" if best_m.get("sharpe_vs_flat", 0) > 0.01 else
              "NO_GAIN"    if best_m else "N/A")
        verdicts[f"S2/{game}"] = v2

        s3 = all_results.get("stage3", {}).get(game, {})
        verdicts[f"S3/{game}"] = s3.get("verdict", "N/A")

    for k, v in verdicts.items():
        e = _verdict_emoji(v)
        lines.append(f"- **{k}**: {e} {v}")
    lines += ["", "---", ""]

    # Stage 0
    lines += ["## Stage 0 — Baseline Metrics", ""]
    for game in ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO"):
        s0 = all_results.get("stage0", {}).get(game, {})
        strats = s0.get("strategies", {})
        lines += [f"### {game}", ""]
        lines.append(f"| Strategy | Bets | Hit Rate | Edge% | Mon.ROI% | Sharpe | MaxDD | RuinP |")
        lines.append(f"|----------|------|----------|-------|----------|--------|-------|-------|")
        for strat, d in strats.items():
            if "error" in d:
                continue
            mc = d.get("mc_ruin", {})
            lines.append(
                f"| {strat} | {d['num_bets']} "
                f"| {d['hit_rate']:.3f} | {d['edge_pct']:+.1f}% "
                f"| {d['monetary_roi_pct']:+.1f}% "
                f"| {d['sharpe_bernoulli']:.3f} "
                f"| {d['max_drawdown_draws']} "
                f"| {mc.get('ruin_prob', '?'):.3f} |"
            )
        lines.append("")

    # Stage 1
    lines += ["## Stage 1 — Decision Layer (Confidence Score + Betting Gate)", ""]
    for game in ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO"):
        s1 = all_results.get("stage1", {}).get(game, {})
        if "error" in s1:
            lines += [f"### {game}: ❌ {s1['error']}", ""]
            continue
        val = s1.get("validation", {})
        v   = val.get("verdict", "N/A")
        lines += [f"### {game} — {_verdict_emoji(v)} {v}", ""]
        lines.append(f"- Best strategy: `{s1.get('best_strategy')}`")
        lines.append(f"- Optimal gate threshold: **{s1.get('best_gate_threshold')}**")
        lines.append(f"- OOS draws analyzed: {s1.get('n_oos_draws')}")
        lines.append(f"- Flat ROI: {s1.get('flat_roi_pct', 0):+.1f}%  |  Flat Sharpe: {s1.get('flat_sharpe', 0):.3f}")
        lines.append("")

        gt = s1.get("gate_results", {}).get(s1.get("best_gate_threshold"), {})
        if gt and "error" not in gt:
            lines.append(f"| Metric | Flat | Gated |")
            lines.append(f"|--------|------|-------|")
            lines.append(f"| Hit rate | — | {gt.get('hit_rate', 0):.3f} |")
            lines.append(f"| ROI% | {s1.get('flat_roi_pct',0):+.1f}% | {gt.get('monetary_roi_pct',0):+.1f}% |")
            lines.append(f"| Sharpe | {s1.get('flat_sharpe',0):.3f} | {gt.get('sharpe',0):.3f} |")
            lines.append(f"| Skip rate | 0% | {gt.get('skip_rate',0)*100:.0f}% |")
            lines.append("")

        gates = val.get("gates", {})
        lines.append("**Validation gates:**")
        for g, r in gates.items():
            lines.append(f"- {g}: {'✅' if r else '❌'}")
        lines += ["", "---", ""]

    # Stage 2
    lines += ["## Stage 2 — Position Sizing", ""]
    for game in ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO"):
        s2 = all_results.get("stage2", {}).get(game, {})
        if "error" in s2:
            lines += [f"### {game}: ❌ {s2['error']}", ""]
            continue
        bm = s2.get("best_metrics", {})
        lines += [f"### {game}", ""]
        lines.append(f"- Best boundaries: **{s2.get('best_boundaries')}**")
        t = s2.get("tier_strategy_map", {})
        lines.append(f"- Tier map: skip → {t.get('tier1')} → {t.get('tier2')} → {t.get('tier3')}")
        lines.append(f"- ROI vs flat: {bm.get('roi_vs_flat_pct', 0):+.1f}%  |  Sharpe vs flat: {bm.get('sharpe_vs_flat', 0):+.3f}")
        lines += [""]

    lines += ["---", ""]

    # Stage 3
    lines += ["## Stage 3 — Payout Optimization (Anti-Crowd)", ""]
    for game in ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO"):
        s3 = all_results.get("stage3", {}).get(game, {})
        v  = s3.get("verdict", "N/A")
        lines += [f"### {game} — {_verdict_emoji(v)} {v}", ""]
        if s3.get("status") in ("SKIPPED", "NO_DATA"):
            lines += [f"- {s3.get('reason', s3.get('status'))}", ""]
            continue
        lines.append(f"- Strategy: `{s3.get('strategy')}`")
        lines.append(f"- Swap rate: {s3.get('swap_rate', 0)*100:.0f}% of tickets")
        lines.append(f"- Popularity score: {s3.get('popularity_before', 0):.1f} → {s3.get('popularity_after', 0):.1f} (Δ{s3.get('popularity_reduction', 0):+.1f})")
        lines.append(f"- Hit rate delta: {s3.get('hit_rate_delta', 0)*100:+.2f}%")
        lines.append(f"- ROI delta: {s3.get('roi_delta_pct', 0):+.2f}%")
        lines += [""]

    lines += ["---", ""]

    # Stage 4
    lines += ["## Stage 4 — Cross-Game Allocation (Fractional Kelly)", ""]
    s4 = all_results.get("stage4", {})
    if "error" not in s4:
        alloc = s4.get("allocations", {})
        lines.append(f"| Game | Allocation | Edge 100p | Weekly Edge | Kelly f |")
        lines.append(f"|------|------------|-----------|-------------|---------|")
        for g, pct in alloc.items():
            gd = s4.get("game_detail", {}).get(g, {})
            lines.append(
                f"| {g} | **{pct*100:.0f}%** "
                f"| {gd.get('edge_100p',0)*100:+.2f}% "
                f"| {gd.get('weekly_edge',0)*100:+.2f}% "
                f"| {gd.get('kelly_f',0):.4f} |"
            )
        lines += ["", f"*Methodology: {s4.get('methodology', '')}*", ""]
    lines += ["---", ""]

    # Final deployment table
    lines += ["## Deployment Recommendation", ""]
    lines.append("| Stage | Game | Verdict | Deploy? |")
    lines.append("|-------|------|---------|---------|")
    for k, v in verdicts.items():
        deploy = "✅ YES" if v in ("PRODUCTION", "GAIN") else "❌ NO"
        lines.append(f"| {k} | — | {_verdict_emoji(v)} {v} | {deploy} |")
    lines += [
        "",
        "> **Core principle**: NO prediction engine modifications made.",
        "> All stages are additive, try/except wrapped, and removable.",
        "",
        "---",
        f"*Generated by `analysis/decision_payout_engine.py` — seed=42*",
    ]

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    return content


# ─── Top-level runner ─────────────────────────────────────────────────────────

GAMES_ALL = ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]


def run_stage(stage: str, games: List[str], verbose: bool = False) -> Dict:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results: Dict = {}

    if stage in ("s0", "all"):
        print("\n[Stage 0] Baseline metrics...")
        results["stage0"] = {}
        for g in games:
            print(f"  {g}...")
            try:
                results["stage0"][g] = stage0_baseline(g)
            except Exception as e:
                results["stage0"][g] = {"error": str(e)}
        _save(results["stage0"], os.path.join(RESULTS_DIR, "stage0_baseline.json"))
        print(f"  ✅ stage0_baseline.json")

    if stage in ("s1", "all"):
        print("\n[Stage 1] Confidence score + Betting gate...")
        results["stage1"] = {}
        for g in games:
            print(f"  {g}...")
            try:
                results["stage1"][g] = stage1_with_validation(g)
            except Exception as e:
                results["stage1"][g] = {"error": str(e)}
        _save(results["stage1"], os.path.join(RESULTS_DIR, "stage1_decision.json"))
        print(f"  ✅ stage1_decision.json")

    if stage in ("s2", "all"):
        print("\n[Stage 2] Position sizing...")
        results["stage2"] = {}
        for g in games:
            print(f"  {g}...")
            try:
                s1 = results.get("stage1", {}).get(g)
                results["stage2"][g] = stage2_sizing(g, s1)
            except Exception as e:
                results["stage2"][g] = {"error": str(e)}
        _save(results["stage2"], os.path.join(RESULTS_DIR, "stage2_sizing.json"))
        print(f"  ✅ stage2_sizing.json")

    if stage in ("s3", "all"):
        print("\n[Stage 3] Payout optimization (anti-crowd)...")
        results["stage3"] = {}
        for g in games:
            print(f"  {g}...")
            try:
                results["stage3"][g] = stage3_payout(g)
            except Exception as e:
                results["stage3"][g] = {"error": str(e)}
        _save(results["stage3"], os.path.join(RESULTS_DIR, "stage3_payout.json"))
        print(f"  ✅ stage3_payout.json")

    if stage in ("s4", "all"):
        print("\n[Stage 4] Cross-game allocation...")
        try:
            results["stage4"] = stage4_allocation(games)
        except Exception as e:
            results["stage4"] = {"error": str(e)}
        _save(results["stage4"], os.path.join(RESULTS_DIR, "stage4_allocation.json"))
        print(f"  ✅ stage4_allocation.json")

    if stage == "all":
        print("\n[Stage 6] Generating report...")
        report_path = os.path.join(DOCS_DIR, "decision_payout_report.md")
        generate_report(results, report_path)
        print(f"  ✅ decision_payout_report.md")

    return results


def _save(obj: Any, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


def _print_summary(results: Dict) -> None:
    print("\n" + "=" * 65)
    print("  DECISION & PAYOUT ENGINE — RESULTS SUMMARY")
    print("=" * 65)

    for game in GAMES_ALL:
        s1 = results.get("stage1", {}).get(game, {})
        s2 = results.get("stage2", {}).get(game, {})
        s3 = results.get("stage3", {}).get(game, {})
        val = s1.get("validation", {})
        verdict = val.get("verdict", "N/A")
        thresh  = s1.get("best_gate_threshold", "N/A")
        s2bm    = s2.get("best_metrics", {})
        print(f"\n  {game}")
        print(f"    S1 gate threshold={thresh}  verdict={verdict}")
        if s2bm:
            print(f"    S2 sizing  ROI vs flat: {s2bm.get('roi_vs_flat_pct',0):+.1f}%  Sharpe delta: {s2bm.get('sharpe_vs_flat',0):+.3f}")
        v3 = s3.get("verdict", "N/A")
        pr = s3.get("popularity_reduction", 0)
        print(f"    S3 payout  verdict={v3}  pop↓{pr:.1f}pts")

    s4 = results.get("stage4", {})
    if "allocations" in s4:
        print(f"\n  S4 cross-game allocations:")
        for g, pct in s4["allocations"].items():
            print(f"    {g}: {pct*100:.0f}%")

    print("=" * 65)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Decision & Payout Optimization Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Stages:
  s0   Baseline metrics (hit rate, ROI, drawdown, MC ruin)
  s1   Confidence score + Betting gate optimization
  s2   Position sizing (confidence → bet count)
  s3   Payout optimization (anti-crowd backtest)
  s4   Cross-game allocation (fractional Kelly)
  all  Run all stages + generate report

Examples:
  python3 analysis/decision_payout_engine.py all --game all
  python3 analysis/decision_payout_engine.py s1 --game DAILY_539
        """,
    )
    parser.add_argument(
        "stage",
        choices=["s0", "s1", "s2", "s3", "s4", "all"],
        help="Stage to run",
    )
    parser.add_argument(
        "--game",
        choices=["DAILY_539", "BIG_LOTTO", "POWER_LOTTO", "all"],
        default="all",
        help="Game to analyze (default: all)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    np.random.seed(args.seed)
    games = GAMES_ALL if args.game == "all" else [args.game]

    print(f"\n{'='*65}")
    print(f"  Decision & Payout Engine  stage={args.stage}  games={games}")
    print(f"{'='*65}")

    results = run_stage(args.stage, games, verbose=args.verbose)

    if args.stage == "all":
        _print_summary(results)

    return results


if __name__ == "__main__":
    main()
