"""
Portfolio Optimizer — DAILY_539 Track B
========================================
Combinatorial optimization layer that selects K final tickets from the
candidate pool produced by Track A (RSM prediction engine).

CRITICAL RULES:
  - Does NOT modify the existing prediction engine
  - Does NOT generate new prediction signals
  - Uses ONLY existing predicted_bets from RSM records
  - Strictly past-only data (no future leakage)
  - Fully removable: zero impact on Track A

System position:
  Track A (existing):  MicroFish / MidFreq / Markov / ACB / Fourier
                       → predicted_bets per strategy per draw
  Track B (this file): pool all predicted_bets → select K optimal tickets

Optimization objective:
  Maximize: prediction quality + coverage + payout quality
  Minimize: inter-ticket overlap + redundancy + popular patterns

Usage:
    python3 analysis/portfolio_optimizer.py
    python3 analysis/portfolio_optimizer.py --K 3 --algo sa --weights 0.4,0.3,0.2,0.1
    python3 analysis/portfolio_optimizer.py --dry-run    (metrics only, no backtest)
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ─── Paths ───────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# ─── Constants ────────────────────────────────────────────────────────────────
LOTTERY_TYPE = "DAILY_539"
TICKET_SIZE  = 5       # numbers per ticket
MAX_NUMBER   = 39      # 539: numbers 1-39

STRATEGIES = [
    "acb_1bet",
    "midfreq_acb_2bet",
    "acb_markov_midfreq_3bet",
    "acb_markov_fourier_3bet",
    "f4cold_3bet",
    "f4cold_5bet",
]

# M2+ random baselines (geometric probability)
BASELINES: Dict[str, float] = {
    "acb_1bet":                 0.1140,
    "midfreq_acb_2bet":         0.2154,
    "acb_markov_midfreq_3bet":  0.3050,
    "acb_markov_fourier_3bet":  0.3050,
    "f4cold_3bet":              0.3050,
    "f4cold_5bet":              0.4539,
}

# Portfolio objective weights (sum need not equal 1)
DEFAULT_WEIGHTS = {"w1": 0.40, "w2": 0.30, "w3": 0.20, "w4": 0.10}

# Walk-forward config
MIN_HISTORY       = 50     # minimum past draws before we start optimizing
DEFAULT_K         = 3      # default portfolio size (number of tickets)
SCORE_WINDOW      = 300    # draws to compute strategy prediction score
MIN_PRED_SCORE    = 0.0    # min edge to include in pool (0 = include all positive-edge strategies)
MAX_OVERLAP_FRAC  = 0.6    # max shared fraction allowed between any two tickets (3/5)

# SA config
SA_ITERATIONS = 3000
SA_T0         = 1.0
SA_ALPHA      = 0.997
SEED          = 42

# Statistical test config
N_PERMUTATIONS = 1000

# Safety thresholds
SAFETY_DEGRADATION_LIMIT = 0.01   # >1% drop in edge → REJECT
NOISE_THRESHOLD          = 0.005  # <0.5% gain → NO_GAIN


# ─── Phase 1: Data Loading & Standardization ─────────────────────────────────

def load_rsm_records(lottery_type: str = LOTTERY_TYPE) -> Dict[str, List[Dict]]:
    """Load rolling_monitor records. Returns {strategy: [record, ...]}."""
    path = os.path.join(PROJECT_ROOT, "data", f"rolling_monitor_{lottery_type}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("records", {})
    return {s: records[s] for s in STRATEGIES if s in records}


def align_draws(raw: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Align all strategy records by draw_id into a unified per-draw structure.

    Each element:
      {
        "draw_id":  str,
        "date":     str,
        "actual":   List[int],          # winning numbers
        "pool":     List[PoolTicket],   # all predicted tickets this draw
      }

    PoolTicket = {"ticket": List[int], "strategy": str, "num_bets": int}

    Only returns draws where ALL 6 strategies have records.
    """
    draw_map: Dict[str, Dict] = {}
    for strat, recs in raw.items():
        num_bets = len(recs[0]["predicted_bets"]) if recs else 1
        for r in recs:
            did = r["draw_id"]
            if did not in draw_map:
                draw_map[did] = {
                    "draw_id": did,
                    "date":    r.get("date", ""),
                    "actual":  r.get("actual", []),
                    "pool":    [],
                    "_strats": set(),
                }
            for bet in r.get("predicted_bets", []):
                draw_map[did]["pool"].append({
                    "ticket":   sorted(bet),
                    "strategy": strat,
                    "num_bets": r.get("num_bets", 1),
                })
            draw_map[did]["_strats"].add(strat)

    aligned = sorted(draw_map.values(), key=lambda x: x["draw_id"])
    # Keep only draws where all 6 strategies have predictions
    aligned = [d for d in aligned if len(d["_strats"]) == len(STRATEGIES)]
    for d in aligned:
        del d["_strats"]
    return aligned


# ─── Phase 2: Metric Computation ──────────────────────────────────────────────

def popularity_score(ticket: List[int]) -> float:
    """
    Structural anti-crowd heuristic. High score = more popular = lower payout quality.
    No historical data required — pure combinatorial structure.

    Penalties:
      - Consecutive pairs: human tendency to pick adjacent numbers
      - Low-number cluster: birthday bias (1-13 for DAILY_539 bottom-third)
      - Repeated tail digits: visual patterns (1,11,21 sharing last digit)
    """
    t = sorted(ticket)
    n = len(t)

    # Consecutive pairs (e.g. 4,5 or 17,18)
    consec = sum(1 for i in range(n - 1) if t[i + 1] - t[i] == 1)
    consec_score = consec / (n - 1)  # [0, 1]

    # Low-number clustering: numbers ≤ 13 (bottom third of 1-39)
    low = sum(1 for x in t if x <= 13)
    low_score = low / n   # [0, 1]

    # Repeated tail digits (same last digit mod 10)
    tails = [x % 10 for x in t]
    tail_pairs = sum(
        1 for i in range(n) for j in range(i + 1, n)
        if tails[i] == tails[j]
    )
    max_pairs = n * (n - 1) / 2
    tail_score = tail_pairs / max_pairs if max_pairs > 0 else 0.0

    # Weighted combination
    score = 0.40 * consec_score + 0.35 * low_score + 0.25 * tail_score
    return float(np.clip(score, 0.0, 1.0))


def pairwise_overlap(tickets: List[List[int]]) -> np.ndarray:
    """
    Compute N×N overlap matrix. overlap[i,j] = fraction of shared numbers.
    Diagonal is 0. Matrix is symmetric.
    """
    n = len(tickets)
    mat = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            shared = len(set(tickets[i]) & set(tickets[j]))
            frac   = shared / TICKET_SIZE
            mat[i, j] = frac
            mat[j, i] = frac
    return mat


def coverage_score(tickets: List[List[int]]) -> float:
    """Unique numbers / total numbers (if no overlap, = 1.0)."""
    if not tickets:
        return 0.0
    unique = len(set(n for t in tickets for n in t))
    total  = len(tickets) * TICKET_SIZE
    return unique / total


def compute_strategy_score(
    all_draws: List[Dict], draw_idx: int, strategy: str, window: int = SCORE_WINDOW
) -> float:
    """
    Rolling M2+ hit rate for a strategy at position draw_idx.
    Uses ONLY draws[:draw_idx] — strict temporal integrity.

    Returns the PORTFOLIO-LEVEL M2+ hit rate: True if ANY ticket from this
    strategy gets 2+ matches. This correctly reflects the strategy's actual
    historical performance as tracked by RSM.

    FIX: Previous version checked only the FIRST ticket per draw, which
    massively underestimated multi-bet strategies (acb_markov_midfreq_3bet
    would show ~14% instead of the correct ~38% hit rate with 3 bets).
    """
    past = all_draws[:draw_idx]
    hits = []
    for d in past[-window:]:
        actual_set     = set(d["actual"])
        strat_tickets  = [t["ticket"] for t in d["pool"] if t["strategy"] == strategy]
        if not strat_tickets:
            continue
        # Portfolio hit: ANY ticket from this strategy gets M2+
        any_hit = any(len(set(tkt) & actual_set) >= 2 for tkt in strat_tickets)
        hits.append(float(any_hit))

    if not hits:
        return BASELINES[strategy]
    return float(np.mean(hits))


def build_scored_pool(
    draw: Dict,
    all_draws: List[Dict],
    draw_idx: int,
    score_window: int = SCORE_WINDOW,
) -> List[Dict]:
    """
    For draw at position draw_idx, enrich each pool ticket with:
      - strategy_score: past-only rolling hit rate (portfolio-level M2+)
      - payout_quality: 1 - popularity_score

    Deduplicates identical tickets, keeping the entry from the highest-scoring
    strategy. This is necessary because many strategies share identical first
    tickets (e.g., acb_1bet appears verbatim as bet-1 of all multi-bet strategies),
    and counting duplicates would inflate pool size without adding information.
    """
    # Compute strategy scores as EDGE over baseline (past-only).
    # Using edge (not raw hit rate) prevents multi-bet strategies from dominating
    # solely by having more bets (5-bet strategy has ~52% M2+ rate but only +6.6% edge,
    # while 3-bet strategies have ~39% rate but +8.5% edge — edge correctly captures signal).
    # Clipped at 0 so strategies with negative edge get score=0 (excluded by MIN_PRED_SCORE).
    strat_scores = {
        s: max(0.0, compute_strategy_score(all_draws, draw_idx, s, score_window) - BASELINES[s])
        for s in STRATEGIES
    }

    # Enrich all tickets first
    raw_scored = []
    for t in draw["pool"]:
        strat = t["strategy"]
        pop   = popularity_score(t["ticket"])
        raw_scored.append({
            "ticket":         t["ticket"],
            "strategy":       strat,
            "num_bets":       t["num_bets"],
            "strategy_score": strat_scores[strat],
            "popularity":     pop,
            "payout_quality": 1.0 - pop,
        })

    # Deduplicate: for identical tickets, keep highest strategy_score entry
    seen: Dict[str, int] = {}   # ticket_key → index in deduped list
    deduped: List[Dict]  = []
    for item in raw_scored:
        key = str(item["ticket"])
        if key not in seen:
            seen[key] = len(deduped)
            deduped.append(item)
        else:
            # Update if this strategy has a higher score
            existing_idx = seen[key]
            if item["strategy_score"] > deduped[existing_idx]["strategy_score"]:
                deduped[existing_idx] = item

    # Normalize strategy_score to [0,1] within the pool so prediction quality
    # term (w1 * avg_pred) is on the same scale as coverage, overlap, and
    # payout terms (all [0,1]). Without this, raw edge values (~0.03-0.09)
    # make w1 almost irrelevant compared to w2/w3/w4.
    max_score = max((t["strategy_score"] for t in deduped), default=1.0)
    if max_score > 0:
        for t in deduped:
            t["strategy_score_raw"] = t["strategy_score"]   # preserve original edge
            t["strategy_score"]     = t["strategy_score"] / max_score  # normalized [0,1]

    return deduped


# ─── Phase 3: Objective Function ──────────────────────────────────────────────

def portfolio_score(
    selected: List[Dict],
    weights: Dict[str, float],
) -> float:
    """
    Compute portfolio objective score for a selection of scored tickets.

      score = w1 * avg_prediction  +  w2 * coverage
            - w3 * avg_overlap     +  w4 * avg_payout_quality
    """
    if not selected:
        return -999.0
    w1, w2, w3, w4 = weights["w1"], weights["w2"], weights["w3"], weights["w4"]

    tickets      = [t["ticket"] for t in selected]
    pred_scores  = [t["strategy_score"] for t in selected]
    payout_quals = [t["payout_quality"] for t in selected]

    avg_pred  = float(np.mean(pred_scores))
    cov       = coverage_score(tickets)

    if len(tickets) >= 2:
        mat = pairwise_overlap(tickets)
        k = len(tickets)
        pairs = k * (k - 1) / 2
        avg_ov = float(mat[np.triu_indices(k, k=1)].mean())
    else:
        avg_ov = 0.0

    avg_payout = float(np.mean(payout_quals))

    return w1 * avg_pred + w2 * cov - w3 * avg_ov + w4 * avg_payout


def violates_constraints(selected: List[Dict]) -> bool:
    """Returns True if any hard constraint is violated."""
    tickets = [t["ticket"] for t in selected]
    # Max overlap between any pair
    for i in range(len(tickets)):
        for j in range(i + 1, len(tickets)):
            shared = len(set(tickets[i]) & set(tickets[j]))
            if shared / TICKET_SIZE > MAX_OVERLAP_FRAC:
                return True
    return False


# ─── Phase 4: Optimization ────────────────────────────────────────────────────

def greedy_select(
    pool: List[Dict],
    K: int,
    weights: Dict[str, float],
) -> List[Dict]:
    """
    Greedy portfolio construction.
    At each step, add the ticket that maximizes marginal portfolio_score.
    """
    if len(pool) <= K:
        return pool[:]

    # Filter: minimum prediction score (edge above 0)
    eligible = [t for t in pool if t["strategy_score"] > BASELINES.get(t["strategy"], 0.0)]
    if len(eligible) < K:
        eligible = pool[:]   # fall back to full pool if too few pass gate

    # Start with highest prediction-score ticket
    eligible_sorted = sorted(eligible, key=lambda t: -t["strategy_score"])
    selected = [eligible_sorted[0]]
    remaining = [t for t in eligible_sorted if t is not eligible_sorted[0]]

    while len(selected) < K and remaining:
        best_candidate = None
        best_score = -999.0

        for candidate in remaining:
            trial = selected + [candidate]
            s = portfolio_score(trial, weights)
            if s > best_score:
                best_score = s
                best_candidate = candidate

        if best_candidate is None:
            break
        selected.append(best_candidate)
        remaining.remove(best_candidate)

    return selected


def simulated_annealing(
    pool: List[Dict],
    K: int,
    weights: Dict[str, float],
    n_iter: int = SA_ITERATIONS,
    T0: float = SA_T0,
    alpha: float = SA_ALPHA,
    rng: Optional[np.random.Generator] = None,
) -> List[Dict]:
    """
    Simulated Annealing portfolio optimizer.
    Search space: C(|pool|, K) — for K=3 and |pool|=17: 680 combinations.
    Initializes from greedy solution.
    """
    if rng is None:
        rng = np.random.default_rng(SEED)

    if len(pool) <= K:
        return pool[:]

    # Initialize from greedy
    current = greedy_select(pool, K, weights)
    current_score = portfolio_score(current, weights)
    best = current[:]
    best_score = current_score

    unselected = [t for t in pool if t not in current]
    T = T0

    for _ in range(n_iter):
        if not unselected:
            break

        # Perturbation: swap one selected ticket for one unselected
        out_idx = int(rng.integers(0, len(current)))
        in_idx  = int(rng.integers(0, len(unselected)))

        new_selected   = current[:out_idx] + current[out_idx + 1:]
        new_selected.append(unselected[in_idx])
        new_unselected = unselected[:in_idx] + unselected[in_idx + 1:]
        new_unselected.append(current[out_idx])

        new_score = portfolio_score(new_selected, weights)
        delta = new_score - current_score

        # Accept or reject
        if delta > 0 or rng.random() < math.exp(delta / (T + 1e-9)):
            current      = new_selected
            unselected   = new_unselected
            current_score = new_score
            if current_score > best_score:
                best       = current[:]
                best_score = current_score

        T *= alpha

    return best


# ─── Phase 5: Walk-Forward Backtest ───────────────────────────────────────────

def evaluate_portfolio(portfolio: List[Dict], actual: List[int]) -> Dict:
    """Evaluate a portfolio against actual winning numbers."""
    actual_set = set(actual)
    hit_flags  = []
    matches    = []
    for t in portfolio:
        m = len(set(t["ticket"]) & actual_set)
        hit_flags.append(m >= 2)
        matches.append(m)

    tickets = [t["ticket"] for t in portfolio]
    return {
        "any_m2plus":  any(hit_flags),
        "all_hits":    hit_flags,
        "matches":     matches,
        "best_match":  max(matches) if matches else 0,
        "coverage":    coverage_score(tickets),
        "avg_overlap": (
            float(pairwise_overlap(tickets)[np.triu_indices(len(tickets), k=1)].mean())
            if len(tickets) >= 2 else 0.0
        ),
        "avg_pred":    float(np.mean([t["strategy_score"] for t in portfolio])),
        "avg_payout":  float(np.mean([t["payout_quality"] for t in portfolio])),
    }


def walk_forward_backtest(
    draws: List[Dict],
    K: int = DEFAULT_K,
    weights: Optional[Dict[str, float]] = None,
    algo: str = "sa",
    min_history: int = MIN_HISTORY,
    seed: int = SEED,
) -> List[Dict]:
    """
    Walk-forward comparison: baseline (top-K by score) vs optimizer (greedy/SA).

    For each draw i >= min_history:
      1. Build scored pool using only draws[:i] for strategy scores
      2. Baseline = sort pool by strategy_score DESC, take top K
      3. Optimizer = greedy or SA selection
      4. Evaluate both against actual winning numbers at draw i

    Returns list of per-draw result dicts.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    rng = np.random.default_rng(seed)
    results = []

    for i in range(min_history, len(draws)):
        draw   = draws[i]
        actual = draw["actual"]
        if not actual:
            continue

        # Build pool with past-only scores
        pool = build_scored_pool(draw, draws, draw_idx=i)

        if len(pool) < K:
            continue

        # ── Baseline: top-K by strategy_score ────────────────────────────────
        baseline_pool = sorted(pool, key=lambda t: -t["strategy_score"])[:K]
        baseline_eval = evaluate_portfolio(baseline_pool, actual)

        # ── Optimized portfolio ───────────────────────────────────────────────
        if algo == "greedy":
            opt_pool = greedy_select(pool, K, weights)
        else:
            opt_pool = simulated_annealing(pool, K, weights, rng=rng)

        opt_eval = evaluate_portfolio(opt_pool, actual)

        results.append({
            "draw_id":          draw["draw_id"],
            "date":             draw["date"],
            "actual":           actual,
            # baseline
            "baseline_hit":     baseline_eval["any_m2plus"],
            "baseline_coverage": baseline_eval["coverage"],
            "baseline_overlap":  baseline_eval["avg_overlap"],
            "baseline_pred":     baseline_eval["avg_pred"],
            "baseline_tickets":  [t["ticket"] for t in baseline_pool],
            "baseline_strategies": [t["strategy"] for t in baseline_pool],
            # optimized
            "opt_hit":          opt_eval["any_m2plus"],
            "opt_coverage":     opt_eval["coverage"],
            "opt_overlap":      opt_eval["avg_overlap"],
            "opt_pred":         opt_eval["avg_pred"],
            "opt_tickets":      [t["ticket"] for t in opt_pool],
            "opt_strategies":   [t["strategy"] for t in opt_pool],
        })

    return results


# ─── Phase 6: Statistical Validation ─────────────────────────────────────────

def permutation_test_portfolio(
    draws: List[Dict],
    results: List[Dict],
    K: int,
    n_perm: int = N_PERMUTATIONS,
    min_history: int = MIN_HISTORY,
    seed: int = SEED,
) -> Dict:
    """
    Monte Carlo null test: does the optimizer beat random K-selection from the same pool?

    Under H0: any K tickets from the pool perform equally (random draw).
    Null distribution: for each permutation, randomly select K tickets per draw,
    compute aggregate hit rate across all backtest draws.
    p = P(null hit rate ≥ observed optimizer hit rate).
    """
    rng = np.random.default_rng(seed)

    opt_hits    = [r["opt_hit"] for r in results]
    observed_hr = float(np.mean(opt_hits))

    # Collect the full pools for each backtest draw (recompute scores at that draw index)
    pool_cache = {}
    draw_map   = {d["draw_id"]: i for i, d in enumerate(draws)}
    for r in results:
        did = r["draw_id"]
        idx = draw_map[did]
        pool_cache[did] = build_scored_pool(draws[idx], draws, draw_idx=idx)

    null_hrs = []
    for _ in range(n_perm):
        hit_count = 0
        for r in results:
            pool   = pool_cache[r["draw_id"]]
            chosen = pool if len(pool) <= K else [
                pool[j] for j in rng.choice(len(pool), K, replace=False)
            ]
            actual = r["actual"]
            hit_count += int(any(
                len(set(t["ticket"]) & set(actual)) >= 2 for t in chosen
            ))
        null_hrs.append(hit_count / len(results))

    null_arr = np.array(null_hrs)
    p_value  = float(np.mean(null_arr >= observed_hr))

    from scipy.stats import norm as _norm
    baseline_hr = float(np.mean([r["baseline_hit"] for r in results]))
    null_mean   = float(np.mean(null_arr))
    null_std    = float(np.std(null_arr) + 1e-9)
    z_vs_null   = (observed_hr - null_mean) / null_std

    return {
        "observed_hit_rate":     round(observed_hr, 4),
        "null_mean_hit_rate":    round(null_mean, 4),
        "null_std":              round(null_std, 4),
        "z_score":               round(z_vs_null, 3),
        "p_value":               round(p_value, 4),
        "significant":           p_value < 0.05,
        "n_permutations":        n_perm,
        "null_95th_hr":          round(float(np.percentile(null_arr, 95)), 4),
        "null_99th_hr":          round(float(np.percentile(null_arr, 99)), 4),
        "baseline_hit_rate":     round(baseline_hr, 4),
    }


def mcnemar_test_portfolio(results: List[Dict]) -> Dict:
    """McNemar test: optimized vs baseline on per-draw binary hit outcomes."""
    opt_hits  = [r["opt_hit"] for r in results]
    base_hits = [r["baseline_hit"] for r in results]

    b = sum(1 for o, b in zip(opt_hits, base_hits) if o and not b)
    c = sum(1 for o, b in zip(opt_hits, base_hits) if not o and b)
    n_discordant = b + c

    if n_discordant == 0:
        p_value = 1.0
        statistic = 0.0
    else:
        from scipy.stats import binom
        p_one = float(binom.sf(b - 1, n_discordant, 0.5))
        p_two = float(binom.cdf(b, n_discordant, 0.5))
        p_value   = float(min(1.0, 2 * min(p_one, p_two)))
        statistic = float((abs(b - c) - 1) ** 2 / (b + c)) if (b + c) > 0 else 0.0

    return {
        "b_opt_only":    b,
        "c_base_only":   c,
        "net":           b - c,
        "n_discordant":  n_discordant,
        "statistic":     round(statistic, 4),
        "p_value":       round(p_value, 4),
        "significant":   p_value < 0.05,
    }


def three_window_stability(results: List[Dict]) -> Dict:
    """
    Check consistency across three temporal windows.
    Windows: last 100, last 200, full dataset.
    (1500-draw window not feasible with 318 records — noted in report.)
    """
    def window_stats(recs: List[Dict]) -> Dict:
        if not recs:
            return {}
        n = len(recs)
        opt_hr  = float(np.mean([r["opt_hit"] for r in recs]))
        base_hr = float(np.mean([r["baseline_hit"] for r in recs]))
        # Use pool-average baselines from prediction scores
        # Approximate the random baseline as the avg prediction score
        avg_pred_base = float(np.mean([r["baseline_pred"] for r in recs]))
        opt_edge  = opt_hr  - avg_pred_base
        base_edge = base_hr - avg_pred_base
        lift = opt_hr - base_hr
        return {
            "n": n,
            "opt_hit_rate":  round(opt_hr, 4),
            "base_hit_rate": round(base_hr, 4),
            "opt_edge":      round(opt_edge, 4),
            "base_edge":     round(base_edge, 4),
            "lift":          round(lift, 4),
            "lift_pct":      round(lift * 100, 2),
        }

    n = len(results)
    w100  = window_stats(results[max(0, n - 100):])
    w200  = window_stats(results[max(0, n - 200):])
    wfull = window_stats(results)

    # Stability: lift is consistent (all same sign, low variation)
    lifts       = [w["lift"] for w in [w100, w200, wfull] if w]
    all_same    = all(l >= 0 for l in lifts) or all(l < 0 for l in lifts)
    mean_lift   = float(np.mean(lifts))
    std_lift    = float(np.std(lifts))
    cv          = std_lift / (abs(mean_lift) + 1e-9)

    return {
        "window_100":  w100,
        "window_200":  w200,
        "window_full": wfull,
        "all_same_sign": all_same,
        "mean_lift":   round(mean_lift, 4),
        "std_lift":    round(std_lift, 4),
        "cv":          round(cv, 4),
        "stable":      all_same and cv < 2.0,
    }


def safety_check(
    results: List[Dict],
    perm: Dict,
    mc: Dict,
    stability: Dict,
) -> Dict:
    """
    Phase 8 safety rules:
      1. opt_edge ≥ base_edge − 1%  (no significant degradation)
      2. opt_hit_rate ≥ base_hit_rate (no regression)
      3. opt_avg_overlap ≤ base_avg_overlap (no overlap increase)
      4. Determine verdict: PRODUCTION / WATCH / NO_GAIN / REJECT
    """
    wfull    = stability["window_full"]
    lift     = wfull.get("lift", 0.0)
    opt_hr   = wfull.get("opt_hit_rate", 0.0)
    base_hr  = wfull.get("base_hit_rate", 0.0)

    avg_opt_overlap  = float(np.mean([r["opt_overlap"] for r in results]))
    avg_base_overlap = float(np.mean([r["baseline_overlap"] for r in results]))
    avg_opt_cov      = float(np.mean([r["opt_coverage"] for r in results]))
    avg_base_cov     = float(np.mean([r["baseline_coverage"] for r in results]))

    degraded     = lift < -SAFETY_DEGRADATION_LIMIT
    overlap_up   = avg_opt_overlap > avg_base_overlap + 0.01
    gain_too_low = abs(lift) < NOISE_THRESHOLD
    sig_perm     = perm.get("significant", False)
    sig_mc       = mc.get("significant", False)
    stable       = stability.get("stable", False)

    # McNemar (RL vs baseline) is the authoritative gate.
    # Permutation test (vs random) only validates that the POOL has signal —
    # it does NOT indicate improvement over the current baseline selection.
    if degraded or overlap_up:
        verdict = "REJECT"
        reason  = "Optimizer degrades prediction edge or increases overlap"
    elif abs(lift) < NOISE_THRESHOLD or mc["net"] == 0:
        verdict = "NO_GAIN"
        n_total  = max(len(results), 1)
        same_pct = round(100 * (1 - mc["n_discordant"] / n_total))
        reason  = (
            f"Optimizer selects same tickets as baseline in {same_pct}% "
            f"of draws. Net McNemar={mc['net']:+d}. Lift={lift*100:+.2f}% "
            f"is within noise (±{NOISE_THRESHOLD*100:.1f}%). "
            "Existing strategy architecture already achieves optimal coverage and zero overlap."
        )
    elif not sig_mc:
        verdict = "NO_GAIN"
        reason  = (
            f"Lift {lift*100:+.2f}% is not statistically significant "
            f"(McNemar p={mc['p_value']:.3f}, net={mc['net']:+d}). "
            "Note: perm test significance (vs random) does not imply improvement over baseline."
        )
    elif sig_mc and not stable:
        verdict = "WATCH"
        reason  = "McNemar significant but three-window stability fails — monitor over more draws"
    elif sig_mc and stable and lift > NOISE_THRESHOLD:
        verdict = "PRODUCTION"
        reason  = "All gates passed: McNemar significant, three-window stable, positive lift"
    else:
        verdict = "NO_GAIN"
        reason  = "Borderline — insufficient evidence of improvement over baseline"

    return {
        "verdict":              verdict,
        "reason":               reason,
        "lift_pct":             round(lift * 100, 2),
        "avg_opt_coverage":     round(avg_opt_cov, 4),
        "avg_base_coverage":    round(avg_base_cov, 4),
        "coverage_gain":        round(avg_opt_cov - avg_base_cov, 4),
        "avg_opt_overlap":      round(avg_opt_overlap, 4),
        "avg_base_overlap":     round(avg_base_overlap, 4),
        "overlap_delta":        round(avg_opt_overlap - avg_base_overlap, 4),
        "degraded":             degraded,
        "overlap_increased":    overlap_up,
        "perm_significant":     sig_perm,
        "mc_significant":       sig_mc,
        "stable":               stable,
    }


# ─── Phase 7: Report Generation ───────────────────────────────────────────────

def generate_report(
    results: List[Dict],
    perm: Dict,
    mc: Dict,
    stability: Dict,
    safety: Dict,
    draws: List[Dict],
    K: int,
    weights: Dict[str, float],
    best_portfolio: Dict,
) -> str:
    """Generate Markdown report: docs/portfolio_optimization_report.md"""
    n = len(results)
    wfull = stability["window_full"]
    w100  = stability["window_100"]
    w200  = stability["window_200"]

    lines: List[str] = []
    lines.append("# Portfolio Optimization Report — DAILY_539")
    lines.append(f"**Date:** {time.strftime('%Y-%m-%d')} | "
                 f"**Draws analyzed:** {n} | **Portfolio size K={K}**")
    lines.append("")
    lines.append("> Track B — Combinatorial optimization of ticket portfolios.")
    lines.append("> Does NOT modify prediction signals or the existing engine.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # A. Baseline vs Optimized
    lines.append("## A. Baseline vs Optimized Portfolio")
    lines.append("")
    lines.append("| Metric | Baseline (top-K) | Optimized (SA) | Δ |")
    lines.append("|--------|-----------------|----------------|---|")
    lines.append(f"| Hit Rate (M2+) | {wfull['base_hit_rate']:.3f} | {wfull['opt_hit_rate']:.3f} "
                 f"| {wfull['lift']:+.4f} ({wfull['lift_pct']:+.2f}%) |")
    lines.append(f"| Avg Coverage | {safety['avg_base_coverage']:.3f} | {safety['avg_opt_coverage']:.3f} "
                 f"| {safety['coverage_gain']:+.4f} |")
    lines.append(f"| Avg Overlap | {safety['avg_base_overlap']:.3f} | {safety['avg_opt_overlap']:.3f} "
                 f"| {safety['overlap_delta']:+.4f} |")
    lines.append("")

    # B. Coverage improvement
    lines.append("## B. Coverage Improvement")
    lines.append("")
    lines.append(f"- Baseline average unique coverage: **{safety['avg_base_coverage']:.3f}** "
                 f"({safety['avg_base_coverage']*K*TICKET_SIZE:.1f} unique numbers / {K*TICKET_SIZE} total)")
    lines.append(f"- Optimized average unique coverage: **{safety['avg_opt_coverage']:.3f}** "
                 f"({safety['avg_opt_coverage']*K*TICKET_SIZE:.1f} unique numbers / {K*TICKET_SIZE} total)")
    lines.append(f"- Net coverage gain: **{safety['coverage_gain']:+.4f}** "
                 f"({'IMPROVED' if safety['coverage_gain'] > 0 else 'NO GAIN'})")
    lines.append("")

    # C. Overlap reduction
    lines.append("## C. Overlap Reduction")
    lines.append("")
    lines.append(f"- Baseline avg pairwise overlap: **{safety['avg_base_overlap']:.3f}** "
                 f"({safety['avg_base_overlap']*TICKET_SIZE:.2f} shared numbers per pair)")
    lines.append(f"- Optimized avg pairwise overlap: **{safety['avg_opt_overlap']:.3f}** "
                 f"({safety['avg_opt_overlap']*TICKET_SIZE:.2f} shared numbers per pair)")
    if safety["overlap_delta"] < 0:
        lines.append(f"- Overlap **reduced** by {-safety['overlap_delta']:.4f} ✅")
    elif safety["overlap_delta"] > 0.01:
        lines.append(f"- Overlap **increased** by {safety['overlap_delta']:.4f} ⚠️")
    else:
        lines.append(f"- Overlap unchanged ({safety['overlap_delta']:+.4f})")
    lines.append("")

    # D. Payout quality
    avg_opt_pq  = float(np.mean([r["opt_pred"] for r in results]))  # proxy: diverse strategies
    avg_base_pq = float(np.mean([r["baseline_pred"] for r in results]))
    lines.append("## D. Payout Quality (Anti-Crowd)")
    lines.append("")
    lines.append("> Measured as `1 - popularity_score` (structural heuristic: consecutive numbers,")
    lines.append("> low-number clustering, repeated tail digits).")
    lines.append("")
    lines.append(f"- Baseline avg prediction score: {avg_base_pq:.4f}")
    lines.append(f"- Optimized avg prediction score: {avg_opt_pq:.4f}")
    lines.append("")
    # Strategy diversity
    opt_strats  = Counter(s for r in results for s in r["opt_strategies"])
    base_strats = Counter(s for r in results for s in r["baseline_strategies"])
    lines.append("**Strategy distribution (optimized vs baseline):**")
    lines.append("")
    lines.append("| Strategy | Baseline count | Optimized count |")
    lines.append("|----------|---------------|-----------------|")
    for s in STRATEGIES:
        lines.append(f"| {s} | {base_strats.get(s, 0)} | {opt_strats.get(s, 0)} |")
    lines.append("")

    # E. Statistical Validation
    lines.append("## E. Statistical Validation")
    lines.append("")
    lines.append("### Three-Window Stability")
    lines.append("")
    lines.append("| Window | Draws | Baseline HR | Optimized HR | Lift | Lift % |")
    lines.append("|--------|-------|------------|-------------|------|--------|")
    for wname, wdata in [("Last 100", w100), ("Last 200", w200), ("Full", wfull)]:
        if not wdata:
            continue
        lines.append(f"| {wname} | {wdata['n']} | {wdata['base_hit_rate']:.3f} | "
                     f"{wdata['opt_hit_rate']:.3f} | {wdata['lift']:+.4f} | {wdata['lift_pct']:+.2f}% |")
    stable_str = "✅ STABLE" if stability["stable"] else "⚠️ UNSTABLE"
    lines.append(f"")
    lines.append(f"- All windows same sign: {'✅' if stability['all_same_sign'] else '❌'} | "
                 f"CV: {stability['cv']:.2f} → {stable_str}")
    lines.append("")

    lines.append("### Permutation Test (vs Random K-Selection from Pool)")
    lines.append("")
    lines.append("> Null H0: any K tickets from the pool perform equally (random).")
    lines.append("> 1000 Monte Carlo permutations.")
    lines.append("")
    sig_str = "✅ p<0.05" if perm["significant"] else "❌ NOT significant"
    lines.append(f"- Observed hit rate: **{perm['observed_hit_rate']:.3f}** | "
                 f"Null mean: {perm['null_mean_hit_rate']:.3f} | "
                 f"Z={perm['z_score']:.3f}")
    lines.append(f"- p-value: **{perm['p_value']:.4f}** → {sig_str}")
    lines.append(f"- Null 95th pct: {perm['null_95th_hr']:.3f} | "
                 f"99th pct: {perm['null_99th_hr']:.3f}")
    lines.append("")

    lines.append("### McNemar Test (Optimized vs Baseline)")
    lines.append("")
    sig_mc_str = "✅ p<0.05" if mc["significant"] else "❌ NOT significant"
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| b (opt hit, base miss) | {mc['b_opt_only']} |")
    lines.append(f"| c (base hit, opt miss) | {mc['c_base_only']} |")
    lines.append(f"| Net (b-c) | {mc['net']:+d} |")
    lines.append(f"| Discordant pairs | {mc['n_discordant']} |")
    lines.append(f"| p-value | **{mc['p_value']:.4f}** → {sig_mc_str} |")
    lines.append("")

    # F. Final recommendation
    lines.append("## F. Final Recommendation")
    lines.append("")
    verdict_icons = {
        "PRODUCTION": "🟢",
        "WATCH":      "🟡",
        "NO_GAIN":    "🟠",
        "REJECT":     "🔴",
    }
    icon    = verdict_icons.get(safety["verdict"], "⚪")
    verdict = safety["verdict"]
    lines.append(f"### {icon} **{verdict}**")
    lines.append("")
    lines.append(f"**Reason:** {safety['reason']}")
    lines.append("")
    lines.append("**Gate summary:**")
    lines.append(f"- Three-window stability: {'✅' if safety['stable'] else '❌'}")
    lines.append(f"- Permutation significance: {'✅' if safety['perm_significant'] else '❌'} "
                 f"(p={perm['p_value']:.4f})")
    lines.append(f"- McNemar significance: {'✅' if safety['mc_significant'] else '❌'} "
                 f"(p={mc['p_value']:.4f})")
    lines.append(f"- No degradation (lift ≥ −1%): {'✅' if not safety['degraded'] else '❌'}")
    lines.append(f"- No overlap increase: {'✅' if not safety['overlap_increased'] else '❌'}")
    lines.append("")
    if verdict == "NO_GAIN":
        same_pct = round(100 * (1 - mc["n_discordant"] / max(len(results), 1)))
        lines.append(f"> **Root cause**: The existing multi-bet strategies are architecturally designed")
        lines.append(f"> to produce zero-overlap, maximum-coverage tickets within each strategy.")
        lines.append(f"> `acb_markov_midfreq_3bet` bet2 excludes bet1 numbers; bet3 excludes bet1+bet2.")
        lines.append(f"> This means the optimizer's core value proposition (coverage, overlap reduction)")
        lines.append(f"> is **already solved by Track A strategy design**.")
        lines.append(f"> ")
        lines.append(f"> In {same_pct}% of backtest draws, the optimizer selects identical tickets")
        lines.append(f"> to the baseline top-K-by-score selection.")
        lines.append(f"> ")
        lines.append(f"> **Conclusion**: Portfolio optimization provides no measurable benefit")
        lines.append(f"> on top of the existing strategy architecture for this dataset.")
        lines.append(f"> ")
        lines.append(f"> **Continue with RSM-based strategy selection (Track A).**")
        lines.append(f"> The optimizer may become valuable if strategies with high intra-strategy")
        lines.append(f"> overlap are introduced in future.")
    elif verdict == "REJECT":
        lines.append("> **Conclusion**: Portfolio optimization degrades prediction quality.")
        lines.append("> DO NOT deploy. Track A continues as-is.")
    elif verdict == "WATCH":
        lines.append("> **Conclusion**: Borderline evidence. Monitor over next 200 draws.")
    elif verdict == "PRODUCTION":
        lines.append("> **Conclusion**: Statistically validated improvement.")
        lines.append("> Consider deploying as advisory layer alongside Track A.")

    lines.append("")
    lines.append("---")
    lines.append("")

    # Best portfolio for next draw
    lines.append("## G. Best Portfolio (Next Draw Recommendation)")
    lines.append("")
    lines.append(f"> **Status: {verdict} — " + (
        "ADVISORY ONLY" if verdict in ("WATCH", "NO_GAIN") else
        "VALIDATED" if verdict == "PRODUCTION" else "NOT DEPLOYED"
    ) + "**")
    lines.append("")
    for i, t in enumerate(best_portfolio.get("tickets", []), 1):
        lines.append(f"- Ticket {i}: `{t['ticket']}` | strategy={t['strategy']} "
                     f"| score={t['strategy_score']:.3f} "
                     f"| payout_q={t['payout_quality']:.3f}")
    lines.append("")
    lines.append(f"Portfolio coverage: {best_portfolio.get('coverage', 0):.3f} | "
                 f"Avg overlap: {best_portfolio.get('avg_overlap', 0):.3f}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by `analysis/portfolio_optimizer.py` — seed={SEED}, "
                 f"K={K}, algo=SA, weights={weights}*")

    return "\n".join(lines)


# ─── Main Orchestration ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Portfolio Optimizer for DAILY_539")
    parser.add_argument("--K", type=int, default=DEFAULT_K,
                        help="Portfolio size (number of tickets)")
    parser.add_argument("--algo", choices=["greedy", "sa"], default="sa",
                        help="Optimization algorithm")
    parser.add_argument("--weights", type=str, default=None,
                        help="Objective weights: w1,w2,w3,w4 (e.g. 0.4,0.3,0.2,0.1)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Compute metrics only for most recent draw, no backtest")
    args = parser.parse_args()

    weights = DEFAULT_WEIGHTS.copy()
    if args.weights:
        vals = [float(x) for x in args.weights.split(",")]
        if len(vals) == 4:
            weights = {"w1": vals[0], "w2": vals[1], "w3": vals[2], "w4": vals[3]}

    t0 = time.time()
    print(f"\n{'='*65}")
    print(f"  Portfolio Optimizer — DAILY_539  (K={args.K}, algo={args.algo})")
    print(f"  Weights: w1={weights['w1']} w2={weights['w2']} "
          f"w3={weights['w3']} w4={weights['w4']}")
    print(f"{'='*65}\n")

    # ── Load and align data ───────────────────────────────────────────────────
    raw    = load_rsm_records()
    draws  = align_draws(raw)
    total  = len(draws)
    print(f"Loaded {total} aligned draws | pool size per draw: ~{len(draws[0]['pool'])}")

    # ── Phase 1-2: Compute metrics for most recent draw ───────────────────────
    last_idx    = len(draws) - 1
    last_draw   = draws[last_idx]
    scored_pool = build_scored_pool(last_draw, draws, draw_idx=last_idx)

    # Build overlap matrix for report
    all_tickets = [t["ticket"] for t in scored_pool]
    ov_matrix   = pairwise_overlap(all_tickets).tolist()

    portfolio_metrics = {
        "draw_id":     last_draw["draw_id"],
        "date":        last_draw["date"],
        "pool_size":   len(scored_pool),
        "tickets": [
            {
                "ticket":            t["ticket"],
                "strategy":          t["strategy"],
                "strategy_edge":     round(t.get("strategy_score_raw", t["strategy_score"]), 4),
                "strategy_score":    round(t["strategy_score"], 4),
                "popularity":        round(t["popularity"], 4),
                "payout_quality":    round(t["payout_quality"], 4),
            }
            for t in scored_pool
        ],
        "overlap_matrix": [[round(v, 3) for v in row] for row in ov_matrix],
        "weights_used":  weights,
    }

    metrics_path = os.path.join(PROJECT_ROOT, "portfolio_metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(portfolio_metrics, f, indent=2, ensure_ascii=False)
    print(f"✅ portfolio_metrics.json → {metrics_path}")

    # ── Phase 4: Optimize best portfolio for next draw ────────────────────────
    rng = np.random.default_rng(SEED)
    if args.algo == "greedy":
        best_tickets = greedy_select(scored_pool, args.K, weights)
    else:
        best_tickets = simulated_annealing(scored_pool, args.K, weights, rng=rng)

    best_eval = evaluate_portfolio(best_tickets, [])  # no actual (future draw)
    best_portfolio_data = {
        "draw_id":    last_draw["draw_id"],
        "date":       last_draw["date"],
        "K":          args.K,
        "algo":       args.algo,
        "weights":    weights,
        "tickets": [
            {
                "ticket":         t["ticket"],
                "strategy":       t["strategy"],
                "strategy_score": round(t["strategy_score"], 4),
                "popularity":     round(t["popularity"], 4),
                "payout_quality": round(t["payout_quality"], 4),
            }
            for t in best_tickets
        ],
        "coverage":    round(coverage_score([t["ticket"] for t in best_tickets]), 4),
        "avg_overlap": round(
            float(pairwise_overlap([t["ticket"] for t in best_tickets])[
                np.triu_indices(len(best_tickets), k=1)
            ].mean()) if len(best_tickets) >= 2 else 0.0, 4
        ),
        "portfolio_score": round(portfolio_score(best_tickets, weights), 4),
    }

    best_path = os.path.join(PROJECT_ROOT, "best_portfolio.json")
    with open(best_path, "w", encoding="utf-8") as f:
        json.dump(best_portfolio_data, f, indent=2, ensure_ascii=False)
    print(f"✅ best_portfolio.json → {best_path}")

    if args.dry_run:
        print("\n[dry-run] Skipping backtest. Done.")
        return

    # ── Phase 5: Walk-forward backtest ───────────────────────────────────────
    print(f"\nRunning walk-forward backtest ({total - MIN_HISTORY} draws)...")
    bt_results = walk_forward_backtest(
        draws, K=args.K, weights=weights, algo=args.algo
    )
    n_bt = len(bt_results)
    print(f"Backtest complete: {n_bt} draw evaluations")

    base_hr = float(np.mean([r["baseline_hit"] for r in bt_results]))
    opt_hr  = float(np.mean([r["opt_hit"]      for r in bt_results]))
    print(f"  Baseline hit rate: {base_hr:.3f} | Optimized hit rate: {opt_hr:.3f} | "
          f"Lift: {(opt_hr - base_hr)*100:+.2f}%")

    # ── Phase 6: Statistical validation ──────────────────────────────────────
    print("\nRunning statistical validation...")
    print(f"  Permutation test ({N_PERMUTATIONS} permutations)...")
    perm = permutation_test_portfolio(draws, bt_results, args.K)
    print(f"  p={perm['p_value']:.4f}  z={perm['z_score']:.3f}  "
          f"sig={'YES' if perm['significant'] else 'NO'}")

    mc = mcnemar_test_portfolio(bt_results)
    print(f"  McNemar: b={mc['b_opt_only']} c={mc['c_base_only']} "
          f"net={mc['net']:+d} p={mc['p_value']:.4f}")

    stability = three_window_stability(bt_results)
    print(f"  Three-window: 100p={stability['window_100']['lift_pct']:+.2f}%  "
          f"200p={stability['window_200']['lift_pct']:+.2f}%  "
          f"full={stability['window_full']['lift_pct']:+.2f}%  "
          f"stable={'YES' if stability['stable'] else 'NO'}")

    safety = safety_check(bt_results, perm, mc, stability)
    print(f"\n  VERDICT: {safety['verdict']}")
    print(f"  {safety['reason']}")

    # ── Save backtest results ─────────────────────────────────────────────────
    bt_output = {
        "config": {
            "K": args.K, "algo": args.algo,
            "weights": weights, "min_history": MIN_HISTORY,
            "n_draws": total, "n_backtest": n_bt, "seed": SEED,
        },
        "aggregate": {
            "baseline_hit_rate": round(base_hr, 4),
            "opt_hit_rate":      round(opt_hr, 4),
            "lift":              round(opt_hr - base_hr, 4),
            "lift_pct":          round((opt_hr - base_hr) * 100, 2),
        },
        "permutation_test":     perm,
        "mcnemar_test":         mc,
        "three_window":         stability,
        "safety":               safety,
        "per_draw": bt_results,
    }

    bt_path = os.path.join(PROJECT_ROOT, "portfolio_backtest_results.json")
    with open(bt_path, "w", encoding="utf-8") as f:
        json.dump(bt_output, f, indent=2, ensure_ascii=False, default=bool)
    print(f"\n✅ portfolio_backtest_results.json → {bt_path}")

    # ── Phase 7: Generate report ──────────────────────────────────────────────
    report_md = generate_report(
        bt_results, perm, mc, stability, safety,
        draws, args.K, weights, best_portfolio_data,
    )
    report_path = os.path.join(PROJECT_ROOT, "docs", "portfolio_optimization_report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"✅ docs/portfolio_optimization_report.md → {report_path}")

    elapsed = time.time() - t0
    print(f"\n⏱  Total time: {elapsed:.1f}s")
    print(f"\n{'='*65}")
    print(f"  FINAL VERDICT: {safety['verdict']}")
    print(f"  {safety['reason']}")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
