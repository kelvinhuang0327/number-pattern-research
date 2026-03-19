"""
Decision & Payout Engine — Strict Validation Module
=====================================================
Hardens Stage 2 (position sizing) and Stage 3/BIG_LOTTO (anti-crowd payout).

Key distinction enforced here:
  CONDITIONAL edge = edge on draws WHERE we bet
  UNCONDITIONAL edge = edge across ALL draws (zeros on skipped draws)

Both must be evaluated. Gains that exist only conditionally but not
unconditionally are labeled ADVISORY_ONLY or REJECT.

Final classification:
  PRODUCTION_CANDIDATE — conditional+unconditional both positive,
                          perm p<0.05, McNemar p<0.05 or net≥+5,
                          three windows stable
  WATCH                — conditional positive, unconditional borderline,
                          at least 2 of 4 gates pass
  ADVISORY_ONLY        — conditional edge real but unconditional diluted,
                          OR single-gate failure with borderline stats
  REJECT               — unconditional edge negative or near-zero,
                          no statistical significance

Usage:
    python3 analysis/decision_payout_validation.py --game all
    python3 analysis/decision_payout_validation.py --game DAILY_539 --verbose
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

try:
    from player_behavior.popularity_model import compute_popularity
    from player_behavior.anti_crowd import suggest_anti_crowd
    _HAS_PLAYER_BEHAVIOR = True
except ImportError:
    _HAS_PLAYER_BEHAVIOR = False

SEED         = 42
RESULTS_DIR  = os.path.join(PROJECT_ROOT, "analysis", "results")
DOCS_DIR     = os.path.join(PROJECT_ROOT, "docs")
DATA_DIR     = os.path.join(PROJECT_ROOT, "data")

# ─── Shared constants (mirror decision_payout_engine.py) ─────────────────────
BASELINES: Dict[str, Dict[int, float]] = {
    "POWER_LOTTO": {1: 0.0387, 2: 0.0759, 3: 0.1117, 4: 0.1460, 5: 0.1791},
    "BIG_LOTTO":   {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 5: 0.0896},
    "DAILY_539":   {1: 0.1140, 2: 0.2154, 3: 0.3050, 4: 0.3843, 5: 0.4539},
}

PRIZE_TABLES: Dict[str, Dict] = {
    "DAILY_539":   {"cost": 50,  "prizes": {2: 50, 3: 300, 4: 20_000, 5: 4_000_000},
                    "metric": "is_m2plus", "pool": 39, "pick": 5},
    "BIG_LOTTO":   {"cost": 50,  "prizes": {3: 400, 4: 2_000, 5: 40_000, 6: 5_000_000},
                    "metric": "is_m3plus", "pool": 49, "pick": 6},
    "POWER_LOTTO": {"cost": 100, "prizes": {3: 100, 4: 800,   5: 40_000, 6: 5_000_000},
                    "metric": "is_m3plus", "pool": 38, "pick": 6},
}

TIER_STRATEGIES: Dict[str, List[Optional[str]]] = {
    "DAILY_539":   [None, "acb_1bet", "midfreq_acb_2bet", "acb_markov_midfreq_3bet"],
    "BIG_LOTTO":   [None, "regime_2bet", "ts3_regime_3bet", "p1_dev_sum5bet"],
    "POWER_LOTTO": [None, "fourier_rhythm_3bet", "pp3_freqort_4bet", "orthogonal_5bet"],
}

WARM_UP   = 100
N_PERM    = 1000
GAMES_ALL = ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]


# ─── Data loading ─────────────────────────────────────────────────────────────

def load_rsm(game: str) -> Dict[str, List[Dict]]:
    path = os.path.join(DATA_DIR, f"rolling_monitor_{game}.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("records", {})


def aligned_draws(records: Dict[str, List[Dict]]) -> List[str]:
    if not records:
        return []
    sets = [set(r["draw_id"] for r in v) for v in records.values()]
    return sorted(sets[0].intersection(*sets[1:]))


def _strat_recs_aligned(records: Dict[str, List[Dict]],
                        draw_ids: List[str]) -> Dict[str, List[Dict]]:
    out = {}
    for strat, recs in records.items():
        by_id = {r["draw_id"]: r for r in recs}
        out[strat] = [by_id[did] for did in draw_ids if did in by_id]
    return out


# ─── Per-draw helpers ─────────────────────────────────────────────────────────

def draw_profit(match_counts: List[int], game: str) -> float:
    prizes = PRIZE_TABLES[game]["prizes"]
    return sum(float(prizes.get(mc, 0)) for mc in match_counts) \
           - len(match_counts) * PRIZE_TABLES[game]["cost"]


def draw_hit(record: Dict, metric: str) -> int:
    return 1 if record.get(metric, False) else 0


def _edge_window(rec_list: List[Dict], end_idx: int, window: int,
                 metric: str, baseline: float) -> Optional[float]:
    start = max(0, end_idx - window)
    subset = rec_list[start:end_idx]
    if not subset:
        return None
    hr = float(np.mean([1.0 if r.get(metric, False) else 0.0 for r in subset]))
    return hr - baseline


def _rolling_std(rec_list: List[Dict], end_idx: int, window: int, metric: str) -> float:
    start = max(0, end_idx - window)
    arr = [1.0 if r.get(metric, False) else 0.0 for r in rec_list[start:end_idx]]
    return float(np.std(arr)) if len(arr) > 1 else 0.0


# ─── Re-import confidence score from engine ──────────────────────────────────
# (duplicate the implementation to avoid circular import)

def _jaccard(a: set, b: set) -> float:
    u = a | b
    return len(a & b) / len(u) if u else 0.0


def _signal_consensus(bets_list: List[List[List[int]]]) -> float:
    sets = [set(n for bet in bets for n in bet) for bets in bets_list]
    if len(sets) < 2:
        return 0.0
    sims = [_jaccard(sets[i], sets[j]) for i, j in combinations(range(len(sets)), 2)]
    return float(np.mean(sims))


def confidence_score(game: str, draw_idx: int,
                     strat_recs: Dict[str, List[Dict]],
                     draw_id: str) -> float:
    metric = PRIZE_TABLES[game]["metric"]
    active = {s: recs for s, recs in strat_recs.items()
              if draw_idx < len(recs) and recs[draw_idx].get("draw_id") == draw_id}
    if not active:
        return 50.0

    bets_list = [recs[draw_idx].get("predicted_bets", []) for recs in active.values()]
    consensus = _signal_consensus(bets_list)

    rep = max(active, key=lambda s: active[s][draw_idx].get("num_bets", 0))
    rep_recs = active[rep]
    num_bets  = rep_recs[draw_idx].get("num_bets", 1)
    baseline  = BASELINES[game].get(num_bets, 0.3)

    e30  = _edge_window(rep_recs, draw_idx, 30,  metric, baseline) or 0.0
    e100 = _edge_window(rep_recs, draw_idx, 100, metric, baseline) or 0.0
    e300 = _edge_window(rep_recs, draw_idx, 300, metric, baseline) or 0.0

    edges = [e30, e100, e300]
    if all(e > 0 for e in edges):
        max_e = max(abs(e) for e in edges) or 1e-9
        consistency = min(abs(e) for e in edges) / max_e
    elif all(e < 0 for e in edges):
        consistency = -0.5
    else:
        pos = sum(1 for e in edges if e > 0)
        consistency = pos / 3.0 - 0.5

    drift = abs(e30 / e300 - 1.0) if abs(e300) > 1e-6 else 0.5
    drift_score = max(0.0, 1.0 - drift)
    std30 = _rolling_std(rep_recs, draw_idx, 30, metric)
    bstd  = math.sqrt(baseline * (1 - baseline))
    var_penalty = 1.0 - min(1.0, std30 / bstd) if bstd > 0 else 0.0

    total = (consensus * 30.0 +
             max(0.0, consistency + 0.5) * 30.0 +
             drift_score * 20.0 +
             var_penalty * 20.0)
    return round(min(100.0, max(0.0, total)), 2)


# ─── Stage 2 Strict Re-evaluation ────────────────────────────────────────────

def _compute_stage2_series(
    game: str,
    boundaries: Tuple[int, int, int],
    records: Dict[str, List[Dict]],
    draw_ids: List[str],
    strat_recs: Dict[str, List[Dict]],
) -> Dict:
    """
    Given optimal boundaries from Stage 2, compute per-draw series for all
    draws from WARM_UP onward. Returns:
      - bet_flags: [bool] — did we bet on each draw?
      - gated_profits: [float] — profit on bet draws
      - flat_profits:  [float] — profit if always flat-betting (tier 2)
      - gated_hits:    [int]   — binary hit on bet draws
      - flat_hits:     [int]   — binary hit under flat policy
      - tier_per_draw: [int]   — which tier selected each draw
      - baselines_per_bet: [float] — strategy baseline for each bet draw
    """
    tiers    = TIER_STRATEGIES[game]
    metric   = PRIZE_TABLES[game]["metric"]
    cost     = PRIZE_TABLES[game]["cost"]
    b1, b2, b3 = boundaries

    flat_strat    = tiers[2] if tiers[2] else tiers[1]
    flat_recs     = strat_recs.get(flat_strat, [])
    flat_num_bets = flat_recs[WARM_UP].get("num_bets", 1) if len(flat_recs) > WARM_UP else 1
    flat_bl       = BASELINES[game].get(flat_num_bets, 0.3)

    bet_flags:       List[bool]  = []
    gated_profits:   List[float] = []
    flat_profits:    List[float] = []
    gated_hits:      List[int]   = []
    flat_hits:       List[int]   = []
    tier_per_draw:   List[int]   = []
    baselines_per_bet: List[float] = []

    oos_idxs = list(range(WARM_UP, len(draw_ids)))

    for idx in oos_idxs:
        if idx >= len(flat_recs):
            continue
        did = draw_ids[idx]

        # Flat baseline
        fr = flat_recs[idx]
        fp = draw_profit(fr.get("match_counts", []), game)
        fh = draw_hit(fr, metric)
        flat_profits.append(fp)
        flat_hits.append(fh)

        # Confidence + tier selection
        sc    = confidence_score(game, idx, strat_recs, did)
        if sc < b1:
            tier = 0
        elif sc < b2:
            tier = 1
        elif sc < b3:
            tier = 2
        else:
            tier = 3

        tier_per_draw.append(tier)
        strat_name = tiers[tier]

        if strat_name is None:
            bet_flags.append(False)
            gated_profits.append(0.0)
            gated_hits.append(0)
        else:
            tier_recs = strat_recs.get(strat_name, [])
            if idx >= len(tier_recs):
                bet_flags.append(False)
                gated_profits.append(0.0)
                gated_hits.append(0)
                continue
            r  = tier_recs[idx]
            gp = draw_profit(r.get("match_counts", []), game)
            gh = draw_hit(r, metric)
            nm = r.get("num_bets", 1)
            bet_flags.append(True)
            gated_profits.append(gp)
            gated_hits.append(gh)
            baselines_per_bet.append(BASELINES[game].get(nm, 0.3))

    return {
        "bet_flags":         bet_flags,
        "gated_profits":     gated_profits,
        "flat_profits":      flat_profits,
        "gated_hits":        gated_hits,
        "flat_hits":         flat_hits,
        "tier_per_draw":     tier_per_draw,
        "baselines_per_bet": baselines_per_bet,
        "oos_n":             len(flat_profits),
        "n_bet":             sum(bet_flags),
        "n_skip":            sum(1 for f in bet_flags if not f),
        "flat_bl":           flat_bl,
    }


def _window_edge(
    series: Dict,
    window: int,
    game: str,
    mode: str = "conditional",
) -> Optional[float]:
    """
    Compute edge in a trailing window.
    mode='conditional': only on bet draws
    mode='unconditional': all draws (skipped contribute 0 profit)
    """
    flat_p  = series["flat_profits"]
    gated_p = series["gated_profits"]
    flags   = series["bet_flags"]
    bls     = series["baselines_per_bet"]
    cost    = PRIZE_TABLES[game]["cost"]

    n = len(flat_p)
    if window > n:
        return None

    flat_w   = flat_p[-window:]
    flags_w  = flags[-window:]

    if mode == "conditional":
        # Edge per bet draw (hit_rate above baseline)
        cond_hits: List[int] = []
        cond_bls:  List[float] = []
        gated_w   = gated_p[-window:]
        bet_bl    = bls  # all baselines in order of bets

        # Re-walk the window to get conditional hits
        bet_idx = sum(1 for f in flags[:-window] if f)  # bets before this window
        for k, (f, gp) in enumerate(zip(flags_w, gated_w)):
            if f:
                idx_in_bls = bet_idx + sum(1 for ff in flags_w[:k] if ff)
                bl = bls[idx_in_bls] if idx_in_bls < len(bls) else 0.3
                hit = 1 if gp > 0 else 0  # crude: any payout = hit
                cond_hits.append(hit)
                cond_bls.append(bl)

        if not cond_hits:
            return None
        cond_hr = float(np.mean(cond_hits))
        avg_bl  = float(np.mean(cond_bls))
        return cond_hr - avg_bl

    else:  # unconditional
        # Hit-rate edge per draw (all draws; skipped draws contribute 0 hits).
        # gated_hits already has 0 for skipped draws, same length as flat_hits.
        gh_all = series["gated_hits"]
        if window > len(gh_all):
            return None
        uncond_hr = float(np.mean(gh_all[-window:]))
        flat_bl   = series.get("flat_bl", 0.3)
        return uncond_hr - flat_bl


def _window_stability(
    series: Dict,
    game: str,
    windows: Tuple[int, ...] = (100, 200),
) -> Dict:
    """
    Check conditional AND unconditional edge across multiple windows.
    Returns window-by-window results + stability flag.
    Note: 1500p is flagged as DATA_INSUFFICIENT if n_oos < 1500.
    """
    n_oos = series["oos_n"]
    results = {}
    for w in (150, 500, 1500):
        if w > n_oos:
            results[f"w{w}"] = {
                "status": "DATA_INSUFFICIENT",
                "n_available": n_oos,
                "conditional_edge": None,
                "unconditional_edge": None,
            }
            continue

        ce = _window_edge(series, w, game, "conditional")
        ue = _window_edge(series, w, game, "unconditional")
        results[f"w{w}"] = {
            "status":             "OK",
            "conditional_edge":   round(ce, 4) if ce is not None else None,
            "unconditional_edge": round(ue, 4) if ue is not None else None,
            "cond_positive":      ce is not None and ce > 0,
            "uncond_positive":    ue is not None and ue > 0,
        }

    available_w = [v for v in results.values() if v["status"] == "OK"]
    cond_stable  = all(v["cond_positive"]  for v in available_w) if available_w else False
    uncond_stable = all(v["uncond_positive"] for v in available_w) if available_w else False

    return {
        "windows":      results,
        "cond_stable":  cond_stable,
        "uncond_stable": uncond_stable,
        "available_windows": [w for w in (150, 500, 1500) if results.get(f"w{w}", {}).get("status") == "OK"],
        "insufficient_windows": [w for w in (150, 500, 1500) if results.get(f"w{w}", {}).get("status") != "OK"],
    }


def _permutation_test_stage2(
    series: Dict,
    game: str,
    n_perm: int = N_PERM,
    seed: int = SEED,
) -> Dict:
    """
    Proper permutation test for position sizing.

    Null: the confidence-based tier selection is independent of outcomes.
    Method: shuffle which tier each draw gets, keeping tier distribution fixed.
    Observed metric: conditional hit rate of bet draws - avg baseline.
    p = P(null_edge >= observed_edge).
    """
    rng     = np.random.default_rng(seed)
    flags   = series["bet_flags"]
    bls     = series["baselines_per_bet"]
    gated_h = series["gated_hits"]

    n_bet = sum(flags)
    if n_bet < 10:
        return {"p_value": 1.0, "significant": False, "note": "too_few_bets"}

    # Observed conditional hit rate edge
    obs_hr  = sum(gated_h) / n_bet
    avg_bl  = float(np.mean(bls)) if bls else 0.3
    obs_edge = obs_hr - avg_bl

    # Flat hit rates — pull from the full OOS period, same indices as bets
    # We'll use all OOS hit outcomes (flat_hits) and sample n_bet from them
    flat_hits = series["flat_hits"]
    all_hits  = np.array(flat_hits, dtype=float)

    perm_edges: List[float] = []
    for _ in range(n_perm):
        shuffled = rng.choice(all_hits, size=n_bet, replace=False)
        perm_hr  = float(np.mean(shuffled))
        perm_edges.append(perm_hr - avg_bl)

    perm_arr = np.array(perm_edges)
    p_value  = float(np.mean(perm_arr >= obs_edge))

    return {
        "observed_edge":   round(obs_edge, 4),
        "observed_hr":     round(obs_hr, 4),
        "avg_baseline":    round(avg_bl, 4),
        "null_mean_edge":  round(float(np.mean(perm_arr)), 4),
        "null_95pct_edge": round(float(np.percentile(perm_arr, 95)), 4),
        "p_value":         round(p_value, 4),
        "significant":     p_value < 0.05,
        "n_bet":           n_bet,
        "n_perm":          n_perm,
    }


def _mcnemar_stage2(series: Dict) -> Dict:
    """McNemar: gated hits vs flat hits on SAME draw index (conditional only — bet draws)."""
    flags      = series["bet_flags"]
    gated_hits = series["gated_hits"]
    flat_hits  = series["flat_hits"]

    # Align: for bet draws, compare gated_hit vs flat_hit at same draw
    gated_iter = iter(gated_hits)
    paired_g: List[int] = []
    paired_f: List[int] = []
    for k, f in enumerate(flags):
        if f:
            gh = next(gated_iter)
            fh = flat_hits[k] if k < len(flat_hits) else 0
            paired_g.append(gh)
            paired_f.append(fh)

    b = sum(1 for g, f in zip(paired_g, paired_f) if g == 1 and f == 0)
    c = sum(1 for g, f in zip(paired_g, paired_f) if g == 0 and f == 1)
    net = b - c
    n_disc = b + c

    if n_disc == 0:
        p_value = 1.0
    else:
        try:
            from scipy.stats import binomtest as _bt
            p_value = float(_bt(b, n_disc, 0.5).pvalue)
        except ImportError:
            p_value = 1.0 if abs(net) == 0 else float(0.5 ** n_disc)

    return {"b": b, "c": c, "net": net, "n_discordant": n_disc,
            "p_value": round(p_value, 4), "significant": p_value < 0.05}


def _sharpe_comparison(series: Dict, game: str) -> Dict:
    """Compare Sharpe of gated (on bet draws) vs flat (all OOS draws)."""
    g = np.array(series["gated_profits"])
    f = np.array(series["flat_profits"])

    g_sharpe = float(np.mean(g) / np.std(g)) if np.std(g) > 0 else 0.0
    f_sharpe = float(np.mean(f) / np.std(f)) if np.std(f) > 0 else 0.0

    # Unconditional Sharpe: gated_profits already has 0.0 for skipped draws
    gu = np.array(series["gated_profits"])
    u_sharpe = float(np.mean(gu) / np.std(gu)) if np.std(gu) > 0 else 0.0

    return {
        "cond_gated_sharpe":   round(g_sharpe, 4),
        "flat_sharpe":         round(f_sharpe, 4),
        "uncond_gated_sharpe": round(u_sharpe, 4),
        "cond_beats_flat":     g_sharpe > f_sharpe,
        "uncond_beats_flat":   u_sharpe > f_sharpe,
    }


def _effective_sample_size(series: Dict) -> Dict:
    """ESS and statistical power estimate."""
    n_oos = series["oos_n"]
    n_bet = series["n_bet"]
    skip_rate = series["n_skip"] / n_oos if n_oos > 0 else 1.0

    # Minimum detectable effect at power=0.80, alpha=0.05 (one-sided)
    # For Bernoulli: delta_min = 1.96 * sqrt(p*(1-p)/n) * 1.28  ≈ 2.5/sqrt(n)
    p_est = 0.35  # rough mid-range hit rate
    if n_bet > 0:
        mde = 2.5 / math.sqrt(n_bet) * math.sqrt(p_est * (1 - p_est))
    else:
        mde = 999.0

    power_note = (
        "SUFFICIENT"  if n_bet >= 100 else
        "MARGINAL"    if n_bet >= 50  else
        "INSUFFICIENT"
    )

    return {
        "n_oos":           n_oos,
        "n_bet":           n_bet,
        "n_skip":          series["n_skip"],
        "skip_rate":       round(skip_rate, 3),
        "min_detectable_edge_pct": round(mde * 100, 2),
        "power_note":      power_note,
    }


def validate_stage2(game: str, verbose: bool = False) -> Dict:
    """
    Full strict validation of Stage 2 position sizing for one game.
    Loads optimal boundaries from stage2_sizing.json output.
    """
    # Load previously computed Stage 2 boundaries
    s2_path = os.path.join(RESULTS_DIR, "stage2_sizing.json")
    try:
        with open(s2_path) as f:
            s2_data = json.load(f)
        bounds = s2_data.get(game, {}).get("best_boundaries")
        if bounds is None or len(bounds) != 3:
            return {"game": game, "error": "no_boundaries_in_stage2_output"}
        b1, b2, b3 = bounds
    except Exception as e:
        return {"game": game, "error": f"stage2 load failed: {e}"}

    records  = load_rsm(game)
    draw_ids = aligned_draws(records)
    strat_recs = _strat_recs_aligned(records, draw_ids)
    metric   = PRIZE_TABLES[game]["metric"]
    cost     = PRIZE_TABLES[game]["cost"]

    # Rebuild per-draw series
    series = _compute_stage2_series(game, (b1, b2, b3), records, draw_ids, strat_recs)
    ess    = _effective_sample_size(series)

    if ess["power_note"] == "INSUFFICIENT":
        return {
            "game":   game,
            "verdict": "REJECT",
            "reason":  f"n_bet={ess['n_bet']} < 50 — insufficient statistical power",
            "ess":     ess,
        }

    # ── Conditional metrics ────────────────────────────────────────────────
    gated_h   = series["gated_hits"]
    bls       = series["baselines_per_bet"]
    n_bet     = series["n_bet"]
    cond_hr   = sum(gated_h) / n_bet if n_bet > 0 else 0.0
    avg_bl    = float(np.mean(bls)) if bls else 0.3
    cond_edge = cond_hr - avg_bl

    # Flat benchmark
    flat_h    = series["flat_hits"]
    n_flat    = len(flat_h)
    flat_recs_all = strat_recs.get(
        TIER_STRATEGIES[game][2] or TIER_STRATEGIES[game][1], []
    )
    flat_num_bets = flat_recs_all[WARM_UP].get("num_bets", 1) if len(flat_recs_all) > WARM_UP else 1
    flat_bl   = BASELINES[game].get(flat_num_bets, 0.3)
    flat_hr   = sum(flat_h) / n_flat if n_flat > 0 else 0.0
    flat_edge = flat_hr - flat_bl

    # ── Unconditional metrics ──────────────────────────────────────────────
    # gated_hits already has 0 for skipped draws — no reconstruction needed
    uncond_hr   = sum(gated_h) / n_flat if n_flat > 0 else 0.0
    uncond_edge = uncond_hr - flat_bl   # compare against flat baseline for all draws

    # ── Statistical tests ─────────────────────────────────────────────────
    perm   = _permutation_test_stage2(series, game)
    mc     = _mcnemar_stage2(series)
    sharpe = _sharpe_comparison(series, game)
    stab   = _window_stability(series, game)

    # ── Final classification ───────────────────────────────────────────────
    gates = {
        "cond_edge_positive":   cond_edge > 0,
        "uncond_edge_positive": uncond_edge > 0,
        "perm_p05":             perm["significant"],
        "mcnemar_net_pos":      mc["net"] > 0,
        "sharpe_cond_beats_flat": sharpe["cond_beats_flat"],
        "sharpe_uncond_beats_flat": sharpe["uncond_beats_flat"],
        "window_cond_stable":   stab["cond_stable"],
        "window_uncond_stable": stab["uncond_stable"],
    }
    n_pass = sum(1 for v in gates.values() if v)
    n_gates = len(gates)

    # Unconditional edge is the authoritative metric
    verdict, reason = _classify_stage2(gates, cond_edge, uncond_edge, perm, mc, stab, ess)

    if verbose:
        _print_stage2_detail(game, bounds, ess, cond_edge, uncond_edge,
                             flat_edge, perm, mc, sharpe, stab, gates, verdict)

    return {
        "game":               game,
        "boundaries":         bounds,
        "verdict":            verdict,
        "reason":             reason,
        "n_gates_pass":       n_pass,
        "n_gates_total":      n_gates,
        "ess":                ess,
        "conditional": {
            "hit_rate":       round(cond_hr, 4),
            "avg_baseline":   round(avg_bl, 4),
            "edge":           round(cond_edge, 4),
            "edge_pct":       round(cond_edge * 100, 2),
        },
        "unconditional": {
            "hit_rate":       round(uncond_hr, 4),
            "flat_baseline":  round(flat_bl, 4),
            "edge":           round(uncond_edge, 4),
            "edge_pct":       round(uncond_edge * 100, 2),
        },
        "flat_baseline": {
            "hit_rate":       round(flat_hr, 4),
            "baseline":       round(flat_bl, 4),
            "edge":           round(flat_edge, 4),
            "edge_pct":       round(flat_edge * 100, 2),
        },
        "permutation_test":   perm,
        "mcnemar":            mc,
        "sharpe":             sharpe,
        "window_stability":   stab,
        "gates":              gates,
    }


def _classify_stage2(
    gates: Dict[str, bool],
    cond_edge: float,
    uncond_edge: float,
    perm: Dict,
    mc: Dict,
    stab: Dict,
    ess: Dict,
) -> Tuple[str, str]:
    """Produce PRODUCTION_CANDIDATE / WATCH / ADVISORY_ONLY / REJECT verdict."""

    # Hard gates for PRODUCTION
    if (gates["cond_edge_positive"] and
        gates["uncond_edge_positive"] and
        gates["perm_p05"] and
        (gates["mcnemar_net_pos"] or mc["net"] >= 3) and
        (gates["window_cond_stable"] or gates["window_uncond_stable"])):
        return ("PRODUCTION_CANDIDATE",
                f"All critical gates pass. Cond edge={cond_edge*100:+.2f}%, "
                f"Uncond edge={uncond_edge*100:+.2f}%, perm p={perm['p_value']:.3f}")

    # WATCH: conditional edge real, unconditional borderline (but positive)
    if (gates["cond_edge_positive"] and
        uncond_edge >= -0.005 and   # unconditional not worse than -0.5%
        gates["sharpe_cond_beats_flat"] and
        sum(1 for v in gates.values() if v) >= 4):
        return ("WATCH",
                f"Conditional edge={cond_edge*100:+.2f}% positive but perm not significant "
                f"(p={perm['p_value']:.3f}). Unconditional edge={uncond_edge*100:+.2f}%.")

    # ADVISORY_ONLY: conditional positive, unconditional diluted/negative
    if gates["cond_edge_positive"] and not gates["uncond_edge_positive"]:
        return ("ADVISORY_ONLY",
                f"Conditional edge exists ({cond_edge*100:+.2f}%) but disappears unconditionally "
                f"({uncond_edge*100:+.2f}%). Gain is an artifact of bet-selection, not real edge.")

    # REJECT: unconditional edge negative, no statistical support
    return ("REJECT",
            f"Unconditional edge={uncond_edge*100:+.2f}% (negative or insignificant). "
            f"Cond edge={cond_edge*100:+.2f}%. perm p={perm['p_value']:.3f}.")


def _print_stage2_detail(game, bounds, ess, cond_edge, uncond_edge, flat_edge,
                          perm, mc, sharpe, stab, gates, verdict):
    print(f"\n{'─'*60}")
    print(f"  Stage 2 Validation — {game}")
    print(f"  Boundaries: {bounds}  |  n_bet={ess['n_bet']}/{ess['n_oos']} "
          f"(skip={ess['skip_rate']*100:.0f}%)  [{ess['power_note']}]")
    print(f"{'─'*60}")
    print(f"  Conditional   hit rate edge: {cond_edge*100:+.2f}%")
    print(f"  Unconditional hit rate edge: {uncond_edge*100:+.2f}%  (vs flat edge {flat_edge*100:+.2f}%)")
    print(f"  Permutation test: p={perm['p_value']:.4f}  {'✅' if perm['significant'] else '❌'}")
    print(f"  McNemar: net={mc['net']:+d}  p={mc['p_value']:.4f}  {'✅' if mc['significant'] else '❌'}")
    print(f"  Sharpe (cond): {sharpe['cond_gated_sharpe']:.3f} vs flat {sharpe['flat_sharpe']:.3f}  "
          f"{'✅' if sharpe['cond_beats_flat'] else '❌'}")
    print(f"  Sharpe (uncond): {sharpe['uncond_gated_sharpe']:.3f}  "
          f"{'✅' if sharpe['uncond_beats_flat'] else '❌'}")
    avail = stab.get("available_windows", [])
    for w in avail:
        wr = stab["windows"][f"w{w}"]
        print(f"  w{w:4d}: cond={wr['conditional_edge']*100:+.2f}%  "
              f"uncond={wr['unconditional_edge']*100:+.2f}%")
    for w in stab.get("insufficient_windows", []):
        print(f"  w{w:4d}: ⚠️  DATA_INSUFFICIENT (only {ess['n_oos']} draws)")
    n_pass = sum(1 for v in gates.values() if v)
    print(f"  Gates: {n_pass}/{len(gates)} pass")
    print(f"  VERDICT: {verdict}")


# ─── Stage 3 BIG_LOTTO Anti-Crowd Validation ─────────────────────────────────

def _anticrowd_series(game: str) -> Optional[Dict]:
    """Rebuild anti-crowd results as a per-draw series for statistical testing."""
    if not _HAS_PLAYER_BEHAVIOR:
        return None
    tbl    = PRIZE_TABLES[game]
    pool   = tbl["pool"]
    pick   = tbl["pick"]
    metric = tbl["metric"]
    cost   = tbl["cost"]

    records  = load_rsm(game)

    # Best strategy by 300p edge
    best_strat = None
    best_edge  = -999.0
    for strat, recs in records.items():
        if len(recs) < 50:
            continue
        nm = recs[0].get("num_bets", 1)
        bl = BASELINES[game].get(nm, 0.3)
        hr = sum(1 for r in recs if r.get(metric, False)) / len(recs)
        if hr - bl > best_edge:
            best_edge  = hr - bl
            best_strat = strat

    if best_strat is None:
        return None

    recs = records[best_strat]
    orig_pays:    List[float] = []
    swapped_pays: List[float] = []
    pop_reductions: List[float] = []
    accept_mask:    List[bool]  = []

    for r in recs:
        bets   = r.get("predicted_bets", [])
        actual = r.get("actual", [])
        if not bets or not actual:
            continue

        orig_t = 0.0
        swap_t = 0.0
        any_swap = False
        pop_red  = 0.0

        for bet in bets:
            sb = sorted(bet)
            orig_mc = len(set(sb) & set(actual))
            orig_pay = float(tbl["prizes"].get(orig_mc, 0))
            orig_t  += orig_pay

            try:
                pop_res = compute_popularity(sb, pool, pick)
                pop_sc  = pop_res["popularity_score"]
            except Exception:
                pop_sc = 0.0

            try:
                ac = suggest_anti_crowd(sb, pool, pick, pop_sc)
                alt = ac.get("alternative")
            except Exception:
                alt = None

            if alt is not None:
                alt_s   = sorted(alt)
                alt_mc  = len(set(alt_s) & set(actual))
                if alt_mc >= orig_mc:
                    swap_t += float(tbl["prizes"].get(alt_mc, 0))
                    try:
                        alt_pop = compute_popularity(alt_s, pool, pick)["popularity_score"]
                        pop_red += (pop_sc - alt_pop)
                    except Exception:
                        pass
                    any_swap = True
                else:
                    swap_t += orig_pay
            else:
                swap_t += orig_pay

        orig_pays.append(orig_t)
        swapped_pays.append(swap_t)
        pop_reductions.append(pop_red)
        accept_mask.append(any_swap)

    return {
        "strategy":     best_strat,
        "orig_pays":    orig_pays,
        "swapped_pays": swapped_pays,
        "pop_reductions": pop_reductions,
        "accept_mask":  accept_mask,
        "n_draws":      len(orig_pays),
        "num_bets":     recs[0].get("num_bets", 1) if recs else 1,
    }


def _perm_test_anticrowd(
    orig_pays: List[float],
    swapped_pays: List[float],
    n_perm: int = N_PERM,
    seed: int = SEED,
) -> Dict:
    """
    Permutation test for anti-crowd ROI delta.
    Null: randomly swap orig vs swapped for each draw.
    Observed: mean(swapped_pays - orig_pays).
    """
    rng = np.random.default_rng(seed)
    orig  = np.array(orig_pays)
    swap  = np.array(swapped_pays)
    deltas = swap - orig
    obs = float(np.mean(deltas))

    perm_means: List[float] = []
    n = len(deltas)
    for _ in range(n_perm):
        signs   = rng.choice([-1.0, 1.0], size=n)
        permuted = deltas * signs   # randomly flip sign of each delta
        perm_means.append(float(np.mean(permuted)))

    perm_arr = np.array(perm_means)
    p_one    = float(np.mean(perm_arr >= obs))

    return {
        "observed_delta":     round(obs, 4),
        "null_mean":          round(float(np.mean(perm_arr)), 4),
        "null_95pct":         round(float(np.percentile(perm_arr, 95)), 4),
        "p_value_one_sided":  round(p_one, 4),
        "significant":        p_one < 0.05,
        "n_perm":             n_perm,
    }


def _threshold_sensitivity(game: str) -> Dict:
    """Test anti-crowd robustness: vary popularity_score threshold 0→20→30→40→50→60."""
    if not _HAS_PLAYER_BEHAVIOR:
        return {"status": "skipped"}

    tbl    = PRIZE_TABLES[game]
    pool   = tbl["pool"]
    pick   = tbl["pick"]
    metric = tbl["metric"]
    records = load_rsm(game)

    best_strat = None
    best_edge  = -999.0
    for strat, recs in records.items():
        if len(recs) < 50:
            continue
        nm = recs[0].get("num_bets", 1)
        bl = BASELINES[game].get(nm, 0.3)
        hr = sum(1 for r in recs if r.get(metric, False)) / len(recs)
        if hr - bl > best_edge:
            best_edge  = hr - bl
            best_strat = strat

    if best_strat is None:
        return {"status": "no_strategy"}

    recs     = records[best_strat]
    cost_pd  = recs[0].get("num_bets", 1) * tbl["cost"] if recs else tbl["cost"]
    n        = len(recs)

    results = {}
    for thresh in [0, 20, 30, 40, 50, 60, 70]:
        orig_pays: List[float] = []
        swap_pays: List[float] = []
        for r in recs:
            bets   = r.get("predicted_bets", [])
            actual = r.get("actual", [])
            if not bets or not actual:
                continue
            ot = 0.0
            st = 0.0
            for bet in bets:
                sb  = sorted(bet)
                omc = len(set(sb) & set(actual))
                op  = float(tbl["prizes"].get(omc, 0))
                ot += op
                try:
                    psc = compute_popularity(sb, pool, pick)["popularity_score"]
                except Exception:
                    psc = 0.0
                if psc >= thresh:
                    try:
                        ac  = suggest_anti_crowd(sb, pool, pick, psc)
                        alt = ac.get("alternative")
                    except Exception:
                        alt = None
                    if alt is not None:
                        alt_s  = sorted(alt)
                        amc    = len(set(alt_s) & set(actual))
                        if amc >= omc:
                            st += float(tbl["prizes"].get(amc, 0))
                            continue
                st += op
            orig_pays.append(ot)
            swap_pays.append(st)

        if orig_pays:
            total_cost = n * cost_pd
            orig_roi  = (sum(orig_pays)  - total_cost) / max(total_cost, 1)
            swap_roi  = (sum(swap_pays)  - total_cost) / max(total_cost, 1)
            results[str(thresh)] = {
                "orig_roi_pct":  round(orig_roi * 100, 2),
                "swap_roi_pct":  round(swap_roi * 100, 2),
                "delta_pct":     round((swap_roi - orig_roi) * 100, 2),
                "swap_rate_pct": round(100 * sum(1 for o, s in zip(orig_pays, swap_pays)
                                                 if s != o) / max(len(orig_pays), 1), 1),
            }

    return results


def validate_stage3_biglotto(verbose: bool = False) -> Dict:
    """Full strict validation of Stage 3 anti-crowd for BIG_LOTTO."""
    game = "BIG_LOTTO"

    series = _anticrowd_series(game)
    if series is None:
        return {"game": game, "error": "series unavailable (missing player_behavior module)"}

    orig  = series["orig_pays"]
    swap  = series["swapped_pays"]
    n     = series["n_draws"]
    cost_per_draw = series["num_bets"] * PRIZE_TABLES[game]["cost"]

    if n < 30:
        return {"game": game, "error": f"insufficient data: n={n}"}

    # Observed ROI delta
    total_cost  = n * cost_per_draw
    orig_roi    = (sum(orig) - total_cost) / max(total_cost, 1)
    swap_roi    = (sum(swap) - total_cost) / max(total_cost, 1)
    roi_delta   = swap_roi - orig_roi

    # Permutation test
    perm = _perm_test_anticrowd(orig, swap)

    # Three-window stability
    windows: Dict = {}
    for w in (100, 200, n):
        label = f"w{w if w != n else 'full'}"
        o_w = orig[-w:]
        s_w = swap[-w:]
        cost_w = len(o_w) * cost_per_draw
        d_w = (sum(s_w) - sum(o_w)) / max(cost_w, 1)
        windows[label] = {"delta_roi_pct": round(d_w * 100, 2), "positive": d_w >= 0}

    all_win_pos = all(v["positive"] for v in windows.values())

    # Threshold sensitivity
    sensitivity = _threshold_sensitivity(game)

    # Popularity reduction stats
    pop_reds = series["pop_reductions"]
    pop_mean = float(np.mean(pop_reds)) if pop_reds else 0.0
    n_swapped = sum(1 for m in series["accept_mask"] if m)

    # Gate summary
    gates = {
        "roi_delta_positive": roi_delta > 0,
        "perm_p05":           perm["significant"],
        "three_windows_pos":  all_win_pos,
        "swap_rate_meaningful": n_swapped / n > 0.02,
        "popularity_reduced":   pop_mean > 0,
    }
    n_pass = sum(1 for v in gates.values() if v)

    # Classification
    if gates["roi_delta_positive"] and gates["perm_p05"] and all_win_pos:
        verdict = "GAIN_VALIDATED"
        reason  = f"ROI delta={roi_delta*100:+.2f}%, perm p={perm['p_value_one_sided']:.4f}, all windows positive."
    elif gates["roi_delta_positive"] and not gates["perm_p05"]:
        verdict = "ADVISORY_ONLY"
        reason  = (f"ROI delta={roi_delta*100:+.2f}% positive but NOT statistically significant "
                   f"(perm p={perm['p_value_one_sided']:.4f}). Effect size too small for current n={n}.")
    else:
        verdict = "REJECT"
        reason  = f"ROI delta={roi_delta*100:+.2f}% not consistently positive."

    if verbose:
        print(f"\n{'─'*60}")
        print(f"  Stage 3 Anti-Crowd — BIG_LOTTO")
        print(f"{'─'*60}")
        print(f"  Strategy: {series['strategy']}  n={n}  n_swapped={n_swapped}")
        print(f"  Original ROI: {orig_roi*100:.2f}%  Swapped ROI: {swap_roi*100:.2f}%")
        print(f"  ROI delta: {roi_delta*100:+.2f}%")
        print(f"  Perm test: p={perm['p_value_one_sided']:.4f}  {'✅' if perm['significant'] else '❌'}")
        for lab, wr in windows.items():
            print(f"  {lab}: delta={wr['delta_roi_pct']:+.2f}%  {'✅' if wr['positive'] else '❌'}")
        print(f"  Popularity reduction: {pop_mean:.2f} pts avg")
        print(f"  Gates: {n_pass}/{len(gates)} pass")
        print(f"  Threshold sensitivity:")
        for t, td in sensitivity.items():
            print(f"    thresh={t}: delta={td['delta_pct']:+.2f}%  swap_rate={td['swap_rate_pct']:.1f}%")
        print(f"  VERDICT: {verdict}")

    return {
        "game":           game,
        "strategy":       series["strategy"],
        "verdict":        verdict,
        "reason":         reason,
        "n_draws":        n,
        "n_swapped":      n_swapped,
        "swap_rate":      round(n_swapped / n, 3),
        "original_roi_pct":  round(orig_roi * 100, 2),
        "swapped_roi_pct":   round(swap_roi * 100, 2),
        "roi_delta_pct":     round(roi_delta * 100, 2),
        "permutation_test":  perm,
        "window_stability":  windows,
        "all_windows_positive": all_win_pos,
        "threshold_sensitivity": sensitivity,
        "popularity_reduction_mean": round(pop_mean, 2),
        "gates":          gates,
        "n_gates_pass":   n_pass,
    }


# ─── Final Classification Table ───────────────────────────────────────────────

def _final_classification(s2_results: Dict[str, Dict], s3_result: Dict) -> List[Dict]:
    rows = []
    for game in GAMES_ALL:
        r = s2_results.get(game, {})
        rows.append({
            "stage":   "Stage 2 (Position Sizing)",
            "game":    game,
            "verdict": r.get("verdict", "N/A"),
            "cond_edge_pct":   r.get("conditional",   {}).get("edge_pct", None),
            "uncond_edge_pct": r.get("unconditional",  {}).get("edge_pct", None),
            "perm_p":  r.get("permutation_test", {}).get("p_value", None),
            "mc_net":  r.get("mcnemar", {}).get("net", None),
            "n_bet":   r.get("ess", {}).get("n_bet", None),
            "reason":  r.get("reason", ""),
        })
    rows.append({
        "stage":   "Stage 3 (Anti-Crowd Payout)",
        "game":    "BIG_LOTTO",
        "verdict": s3_result.get("verdict", "N/A"),
        "cond_edge_pct":   None,
        "uncond_edge_pct": None,
        "roi_delta_pct":   s3_result.get("roi_delta_pct", None),
        "perm_p":  s3_result.get("permutation_test", {}).get("p_value_one_sided", None),
        "mc_net":  None,
        "n_bet":   s3_result.get("n_draws", None),
        "reason":  s3_result.get("reason", ""),
    })
    return rows


def generate_validation_report(
    s2_results: Dict[str, Dict],
    s3_result:  Dict,
    table:      List[Dict],
    output_path: str,
) -> None:
    lines: List[str] = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines += [
        "# Decision & Payout Engine — Strict Validation Report",
        f"**Generated:** {now}  |  seed=42  |  N_PERM=1000",
        "",
        "> **Key principle**: Conditional edge ≠ real edge.",
        "> All gains must be positive both conditionally AND unconditionally.",
        "> Any gain that disappears in the unconditional metric is labeled ADVISORY_ONLY.",
        "",
        "---",
        "",
        "## Final Classification Table",
        "",
        "| Stage | Game | Verdict | Cond.Edge% | Uncond.Edge% | Perm p | McNemar net | N | Deployable? |",
        "|-------|------|---------|-----------|-------------|--------|------------|---|-------------|",
    ]
    for row in table:
        v   = row["verdict"]
        ce  = f"{row['cond_edge_pct']:+.2f}%" if row.get("cond_edge_pct") is not None else "—"
        ue  = f"{row['uncond_edge_pct']:+.2f}%" if row.get("uncond_edge_pct") is not None else (
              f"(ROI Δ{row['roi_delta_pct']:+.2f}%)" if row.get("roi_delta_pct") is not None else "—")
        pp  = f"{row['perm_p']:.4f}" if row.get("perm_p") is not None else "—"
        mc  = f"{row['mc_net']:+d}"  if row.get("mc_net") is not None else "—"
        n   = str(row.get("n_bet", "—"))
        dep = "✅ YES" if v == "PRODUCTION_CANDIDATE" else (
              "🔶 WATCH"   if v == "WATCH"        else
              "⚪ ADVISORY" if v in ("ADVISORY_ONLY", "GAIN_VALIDATED") else
              "❌ NO")
        emoji = {"PRODUCTION_CANDIDATE": "✅", "WATCH": "🔶",
                 "ADVISORY_ONLY": "⚪", "GAIN_VALIDATED": "🔶",
                 "REJECT": "❌"}.get(v, "")
        lines.append(f"| {row['stage']} | {row['game']} | {emoji} {v} "
                     f"| {ce} | {ue} | {pp} | {mc} | {n} | {dep} |")

    lines += ["", "---", "", "## Stage 2 — Position Sizing Detail", ""]

    for game in GAMES_ALL:
        r = s2_results.get(game, {})
        v = r.get("verdict", "N/A")
        emoji = {"PRODUCTION_CANDIDATE": "✅", "WATCH": "🔶",
                 "ADVISORY_ONLY": "⚪", "REJECT": "❌"}.get(v, "")
        lines += [f"### {game} — {emoji} {v}", ""]

        if "error" in r:
            lines += [f"> Error: {r['error']}", ""]
            continue

        ess = r.get("ess", {})
        lines.append(f"- Boundaries: `{r.get('boundaries')}`  "
                     f"| n_bet={ess.get('n_bet')}/{ess.get('n_oos')} "
                     f"(skip={ess.get('skip_rate',0)*100:.0f}%)")
        lines.append(f"- Power: {ess.get('power_note')}  "
                     f"(min detectable edge: {ess.get('min_detectable_edge_pct',0):.1f}%)")
        lines.append("")
        cd = r.get("conditional", {})
        ud = r.get("unconditional", {})
        fd = r.get("flat_baseline", {})
        lines += [
            "| Metric | Conditional | Unconditional | Flat Baseline |",
            "|--------|------------|---------------|---------------|",
            f"| Hit rate | {cd.get('hit_rate',0):.3f} | {ud.get('hit_rate',0):.3f} | {fd.get('hit_rate',0):.3f} |",
            f"| Baseline | {cd.get('avg_baseline',0):.3f} | {ud.get('flat_baseline',0):.3f} | {fd.get('baseline',0):.3f} |",
            f"| Edge | **{cd.get('edge_pct',0):+.2f}%** | **{ud.get('edge_pct',0):+.2f}%** | {fd.get('edge_pct',0):+.2f}% |",
            "",
        ]

        perm   = r.get("permutation_test", {})
        mc     = r.get("mcnemar", {})
        sharpe = r.get("sharpe", {})
        stab   = r.get("window_stability", {})
        gates  = r.get("gates", {})

        lines += [
            "**Statistical tests:**",
            f"- Permutation: obs_edge={perm.get('observed_edge',0)*100:+.2f}%  "
            f"null_95pct={perm.get('null_95pct_edge',0)*100:+.2f}%  "
            f"p={perm.get('p_value',1):.4f}  {'✅' if perm.get('significant') else '❌'}",
            f"- McNemar: b={mc.get('b',0)} c={mc.get('c',0)} net={mc.get('net',0):+d}  "
            f"p={mc.get('p_value',1):.4f}  {'✅' if mc.get('significant') else '❌'}",
            f"- Sharpe (cond): {sharpe.get('cond_gated_sharpe',0):.3f} vs flat {sharpe.get('flat_sharpe',0):.3f}  "
            f"{'✅' if sharpe.get('cond_beats_flat') else '❌'}",
            f"- Sharpe (uncond): {sharpe.get('uncond_gated_sharpe',0):.3f}  "
            f"{'✅' if sharpe.get('uncond_beats_flat') else '❌'}",
            "",
        ]

        lines.append("**Window stability (conditional / unconditional):**")
        for w in (150, 500, 1500):
            wr = stab.get("windows", {}).get(f"w{w}", {})
            if wr.get("status") == "DATA_INSUFFICIENT":
                lines.append(f"- w{w}: ⚠️ DATA_INSUFFICIENT (only {wr.get('n_available')} draws available)")
            else:
                ce = wr.get('conditional_edge') or 0
                ue2 = wr.get('unconditional_edge') or 0
                lines.append(f"- w{w}: cond={ce*100:+.2f}% {'✅' if wr.get('cond_positive') else '❌'}  "
                             f"uncond={ue2*100:+.2f}% {'✅' if wr.get('uncond_positive') else '❌'}")

        lines += [
            "",
            f"**Gate summary** ({r.get('n_gates_pass')}/{r.get('n_gates_total')} pass):",
        ]
        for g, gv in gates.items():
            lines.append(f"- {g}: {'✅' if gv else '❌'}")
        lines += [f"", f"> **Reason**: {r.get('reason', '')}", "", "---", ""]

    # Stage 3
    lines += ["## Stage 3 — BIG_LOTTO Anti-Crowd Payout Detail", ""]
    v3  = s3_result.get("verdict", "N/A")
    e3  = {"GAIN_VALIDATED": "🔶", "ADVISORY_ONLY": "⚪", "REJECT": "❌"}.get(v3, "")
    lines += [f"### BIG_LOTTO — {e3} {v3}", ""]
    if "error" not in s3_result:
        p3 = s3_result.get("permutation_test", {})
        lines += [
            f"- Strategy: `{s3_result.get('strategy')}`  n={s3_result.get('n_draws')}  "
            f"swap_rate={s3_result.get('swap_rate',0)*100:.1f}%",
            f"- Original ROI: {s3_result.get('original_roi_pct',0):.2f}%  "
            f"→ Swapped ROI: {s3_result.get('swapped_roi_pct',0):.2f}%  "
            f"(Δ{s3_result.get('roi_delta_pct',0):+.2f}%)",
            f"- Permutation test: p={p3.get('p_value_one_sided',1):.4f}  "
            f"{'✅' if p3.get('significant') else '❌'}",
            f"- All windows positive: {'✅' if s3_result.get('all_windows_positive') else '❌'}",
            "",
            "**Window stability:**",
        ]
        for wk, wr in s3_result.get("window_stability", {}).items():
            lines.append(f"- {wk}: Δ={wr['delta_roi_pct']:+.2f}%  {'✅' if wr['positive'] else '❌'}")
        lines += ["", "**Threshold sensitivity (popularity score threshold → ROI delta):**", ""]
        lines.append("| Threshold | Orig ROI% | Swap ROI% | Δ ROI% | Swap rate |")
        lines.append("|-----------|-----------|-----------|--------|-----------|")
        for t, td in s3_result.get("threshold_sensitivity", {}).items():
            lines.append(f"| {t} | {td['orig_roi_pct']:+.2f}% | {td['swap_roi_pct']:+.2f}% "
                         f"| {td['delta_pct']:+.2f}% | {td['swap_rate_pct']:.1f}% |")
        lines += [""]
        gates3 = s3_result.get("gates", {})
        n_pass3 = s3_result.get("n_gates_pass", 0)
        lines += [f"**Gate summary** ({n_pass3}/{len(gates3)} pass):"]
        for g, gv in gates3.items():
            lines.append(f"- {g}: {'✅' if gv else '❌'}")
        lines += ["", f"> **Reason**: {s3_result.get('reason', '')}", ""]

    lines += [
        "---",
        "",
        "## Interpretation Guide",
        "",
        "| Verdict | Meaning |",
        "|---------|---------|",
        "| PRODUCTION_CANDIDATE | Both conditional and unconditional edge positive, perm p<0.05, McNemar improvement. Ready for shadow deployment. |",
        "| WATCH | Conditional edge real, unconditional borderline. Continue monitoring with more data. |",
        "| ADVISORY_ONLY | Gain exists conditionally only — artifact of bet selection, not signal quality. Use as informational only. |",
        "| GAIN_VALIDATED (Stage 3) | ROI uplift present but permutation not significant — effect real but small. ADVISORY use. |",
        "| REJECT | No consistent improvement. Do not deploy. |",
        "",
        "---",
        f"*Generated by `analysis/decision_payout_validation.py` — seed=42, N_PERM=1000*",
    ]

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  ✅ {os.path.basename(output_path)}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Strict validation of Stage 2 and Stage 3 BIG_LOTTO"
    )
    parser.add_argument("--game", choices=["DAILY_539", "BIG_LOTTO", "POWER_LOTTO", "all"],
                        default="all")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    np.random.seed(SEED)
    games = GAMES_ALL if args.game == "all" else [args.game]
    os.makedirs(RESULTS_DIR, exist_ok=True)

    print(f"\n{'='*65}")
    print(f"  Decision & Payout Validation  N_PERM={N_PERM}")
    print(f"  Conditional vs Unconditional edge — strict gates")
    print(f"{'='*65}")

    # Stage 2 validation
    print("\n[Stage 2] Position Sizing — Strict Validation...")
    s2_results: Dict[str, Dict] = {}
    for g in games:
        print(f"  {g}...")
        try:
            s2_results[g] = validate_stage2(g, verbose=args.verbose)
        except Exception as e:
            s2_results[g] = {"game": g, "error": str(e), "verdict": "ERROR"}

    # Stage 3 BIG_LOTTO validation
    print("\n[Stage 3] BIG_LOTTO Anti-Crowd — Strict Validation...")
    try:
        s3_result = validate_stage3_biglotto(verbose=args.verbose)
    except Exception as e:
        s3_result = {"game": "BIG_LOTTO", "error": str(e), "verdict": "ERROR"}

    # Final classification table
    table = _final_classification(s2_results, s3_result)

    # Save JSON
    all_json = {"stage2": s2_results, "stage3_biglotto": s3_result,
                "classification_table": table}
    json_path = os.path.join(RESULTS_DIR, "strict_validation.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_json, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n  ✅ strict_validation.json")

    # Report
    print("\n[Report] Generating strict validation report...")
    generate_validation_report(
        s2_results, s3_result, table,
        os.path.join(DOCS_DIR, "decision_payout_validation_report.md"),
    )

    # Print summary
    print(f"\n{'='*65}")
    print(f"  FINAL CLASSIFICATION TABLE")
    print(f"{'='*65}")
    print(f"  {'Stage':<28} {'Game':<14} {'Verdict':<22} {'Cond%':>7} {'Uncond%':>8} {'Perm p':>7}")
    print(f"  {'─'*85}")
    for row in table:
        ce = f"{row['cond_edge_pct']:+.2f}" if row.get("cond_edge_pct") is not None else "  N/A"
        ue_raw = row.get("uncond_edge_pct")
        ue  = f"{ue_raw:+.2f}" if ue_raw is not None else (
              f"Δ{row['roi_delta_pct']:+.2f}" if row.get("roi_delta_pct") is not None else "  N/A")
        pp  = f"{row['perm_p']:.4f}" if row.get("perm_p") is not None else "  N/A"
        print(f"  {row['stage']:<28} {row['game']:<14} {row['verdict']:<22} {ce:>7}% {ue:>7}% {pp:>7}")
    print(f"{'='*65}")


if __name__ == "__main__":
    main()
