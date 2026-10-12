#!/usr/bin/env python3
"""P219 — Ten-method external diagnostic sweep (READ-ONLY).

Pre-registration: outputs/research/p219_external_method_diagnostic_sweep_plan_20260605.md
Runs 10 external-method families as read-only diagnostics over distinct REAL draws,
every p-value a Monte-Carlo / permutation empirical p-value (pure stdlib; no numpy/scipy).
Applies Bonferroni + BH-FDR across the whole pre-registered family.

NO DB/registry/production write. NO strategy promotion. NO betting advice.
Statistical unit = distinct real draws (BIG_LOTTO excludes simulation artifacts
with composite hyphenated IDs). Honest expected outcome: NULL.

Usage:
    python3 analysis/p219_external_method_diagnostic_sweep.py [--b-scale F] [--out PREFIX]
"""
from __future__ import annotations

# ── P252H SSOT Governance Annotation (2026-06-07) ───────────────────────────
# This script (P219) is a COMPLETED HISTORICAL ARTIFACT. Its statistical logic
# is retained as-is. New research tasks should import from the SSOT modules:
#   baseline     : from lottery_api.utils.baseline_calculator import (
#                      single_ticket_probability, n_ticket_probability,
#                      random_baseline_summary)
#   correction   : from lottery_api.utils.correction_gate import (
#                      bonferroni_correction, benjamini_hochberg_fdr,
#                      correction_gate_summary)
#   permutation  : from lottery_api.utils.permutation_test import (
#                      empirical_p_value, permutation_summary)
#   rolling_window: from lottery_api.utils.rolling_window import (
#                      P221F_WINDOWS, rolling_summary, tail_window)
# See P252C / P252D / P252E / P252F for SSOT implementations.
# ────────────────────────────────────────────────────────────────────────────

import argparse
import json
import math
import os
import random
import sqlite3
import sys
import zlib
from collections import Counter, defaultdict

SEED = 20260605

# --- DB resolution (read-only) ---------------------------------------------
_CANDIDATE_DBS = [
    os.path.join(os.path.dirname(__file__), "..", "lottery_api", "data", "lottery_v2.db"),
    "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db",
]


def resolve_db(explicit: str | None = None) -> str:
    for cand in ([explicit] if explicit else []) + _CANDIDATE_DBS:
        if cand and os.path.exists(cand):
            return os.path.abspath(cand)
    raise FileNotFoundError("lottery_v2.db not found in candidate paths")


# game -> (sql filter, pool size, draw size, kind)
GAMES = {
    "DAILY_539":  {"filter": "lottery_type='DAILY_539'",                      "pool": 39, "k": 5, "kind": "number"},
    "BIG_LOTTO":  {"filter": "lottery_type='BIG_LOTTO' AND draw NOT LIKE '%-%'", "pool": 49, "k": 6, "kind": "number"},
    "POWER_LOTTO":{"filter": "lottery_type='POWER_LOTTO'",                     "pool": 38, "k": 6, "kind": "number"},
    "3_STAR":     {"filter": "lottery_type='3_STAR'",                          "pool": 10, "k": 3, "kind": "digit"},
    "4_STAR":     {"filter": "lottery_type='4_STAR'",                          "pool": 10, "k": 4, "kind": "digit"},
}


def load_game(db: str, game: str):
    """Return list of draws in chronological order.

    number games -> list[frozenset[int]]; digit games -> list[tuple[int,...]] (positional).
    """
    cfg = GAMES[game]
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        col = "numbers_positional" if cfg["kind"] == "digit" else "numbers"
        rows = conn.execute(
            f"SELECT draw, {col} FROM draws WHERE {cfg['filter']} "
            f"AND {col} IS NOT NULL AND {col} != '' "
            f"ORDER BY CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()
    draws = []
    for _draw, payload in rows:
        try:
            vals = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            continue
        if cfg["kind"] == "digit":
            if len(vals) == cfg["k"]:
                draws.append(tuple(int(v) for v in vals))
        else:
            s = frozenset(int(v) for v in vals)
            if len(s) == cfg["k"]:
                draws.append(s)
    return draws


# --- stats helpers ----------------------------------------------------------
def empirical_p(obs: float, null_samples: list[float], tail: str = "greater") -> float:
    """Monte-Carlo empirical p = (1 + #{extreme}) / (B + 1)."""
    b = len(null_samples)
    if b == 0:
        return float("nan")
    if tail == "greater":
        c = sum(1 for s in null_samples if s >= obs - 1e-12)
    elif tail == "less":
        c = sum(1 for s in null_samples if s <= obs + 1e-12)
    else:  # two-sided: count as-or-more-extreme on the closer side, doubled
        c_g = sum(1 for s in null_samples if s >= obs - 1e-12)
        c_l = sum(1 for s in null_samples if s <= obs + 1e-12)
        return min(1.0, 2.0 * (1 + min(c_g, c_l)) / (b + 1))
    return (1 + c) / (b + 1)


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def var(xs):
    xs = list(xs)
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def sim_uniform_number_draws(rng, n, pool, k):
    population = list(range(1, pool + 1))
    return [frozenset(rng.sample(population, k)) for _ in range(n)]


def sim_uniform_digit_draws(rng, n, k):
    return [tuple(rng.randrange(10) for _ in range(k)) for _ in range(n)]


# --- M1: Markov / consecutive dependency -----------------------------------
def m1_markov(draws, cfg, rng, B):
    kind = cfg["kind"]
    if kind == "number":
        obs = mean(len(draws[t] & draws[t + 1]) for t in range(len(draws) - 1))
    else:
        K = cfg["k"]
        obs = mean(
            sum(1 for p in range(K) if draws[t][p] == draws[t + 1][p]) / K
            for t in range(len(draws) - 1)
        )
    null = []
    idx = list(range(len(draws)))
    for _ in range(B):
        rng.shuffle(idx)
        perm = [draws[i] for i in idx]
        if kind == "number":
            null.append(mean(len(perm[t] & perm[t + 1]) for t in range(len(perm) - 1)))
        else:
            K = cfg["k"]
            null.append(mean(
                sum(1 for p in range(K) if perm[t][p] == perm[t + 1][p]) / K
                for t in range(len(perm) - 1)))
    return {"stat": "mean_consecutive_overlap" if kind == "number" else "consecutive_digit_match_rate",
            "obs": obs, "p": empirical_p(obs, null, "two-sided"),
            "null_mean": mean(null), "B": B, "tail": "two-sided"}


# --- M2: Gap / waiting-time dispersion --------------------------------------
def _pooled_gap_dispersion_number(draws, pool):
    last = {}
    gaps = []
    for t, d in enumerate(draws):
        for n in d:
            if n in last:
                gaps.append(t - last[n])
            last[n] = t
    m = mean(gaps)
    return (var(gaps) / m) if m else 0.0


def m2_gap(draws, cfg, rng, B):
    pool, k = cfg["pool"], cfg["k"]
    obs = _pooled_gap_dispersion_number(draws, pool)
    null = []
    n = len(draws)
    for _ in range(B):
        sim = sim_uniform_number_draws(rng, n, pool, k)
        null.append(_pooled_gap_dispersion_number(sim, pool))
    return {"stat": "pooled_gap_var_over_mean", "obs": obs,
            "p": empirical_p(obs, null, "two-sided"), "null_mean": mean(null),
            "B": B, "tail": "two-sided"}


# --- M3: Rolling-window frequency drift -------------------------------------
def _max_window_drift(seq_counts_fn, n, W, step, global_freq, items):
    """seq_counts_fn(a,b) -> Counter of item over draws[a:b]."""
    best = 0.0
    a = 0
    while a + W <= n:
        c = seq_counts_fn(a, a + W)
        tot = sum(c.values()) or 1
        l1 = sum(abs(c.get(it, 0) / tot - global_freq[it]) for it in items)
        best = max(best, l1)
        a += step
    return best


def m3_drift(draws, cfg, rng, B):
    kind, pool, k = cfg["kind"], cfg["pool"], cfg["k"]
    n = len(draws)
    W = 200 if n >= 600 else max(50, n // 4)
    step = max(1, W // 2)
    if kind == "number":
        items = list(range(1, pool + 1))
        gc = Counter()
        for d in draws:
            gc.update(d)
        tot = sum(gc.values()) or 1
        gfreq = {it: gc.get(it, 0) / tot for it in items}

        def counts(a, b):
            c = Counter()
            for d in draws[a:b]:
                c.update(d)
            return c
    else:
        items = [(p, dig) for p in range(k) for dig in range(10)]
        gc = Counter()
        for d in draws:
            for p in range(k):
                gc[(p, d[p])] += 1
        tot = sum(gc.values()) or 1
        gfreq = {it: gc.get(it, 0) / tot for it in items}

        def counts(a, b):
            c = Counter()
            for d in draws[a:b]:
                for p in range(k):
                    c[(p, d[p])] += 1
            return c

    obs = _max_window_drift(counts, n, W, step, gfreq, items)
    idx = list(range(n))
    null = []
    for _ in range(B):
        rng.shuffle(idx)
        perm = [draws[i] for i in idx]
        if kind == "number":
            def pc(a, b, perm=perm):
                c = Counter()
                for d in perm[a:b]:
                    c.update(d)
                return c
        else:
            def pc(a, b, perm=perm):
                c = Counter()
                for d in perm[a:b]:
                    for p in range(k):
                        c[(p, d[p])] += 1
                return c
        null.append(_max_window_drift(pc, n, W, step, gfreq, items))
    return {"stat": f"max_window_L1_drift(W={W})", "obs": obs,
            "p": empirical_p(obs, null, "greater"), "null_mean": mean(null),
            "B": B, "tail": "greater"}


# --- M4: Change-point (CUSUM range) -----------------------------------------
def _draw_scalar(draws, kind):
    if kind == "number":
        return [sum(d) for d in draws]
    return [sum(d) for d in draws]  # digit sum


def _cusum_range(s):
    m = mean(s)
    sd = math.sqrt(var(s)) or 1.0
    c = 0.0
    lo = hi = 0.0
    for x in s:
        c += (x - m)
        lo = min(lo, c)
        hi = max(hi, c)
    return (hi - lo) / sd


def m4_changepoint(draws, cfg, rng, B):
    s = _draw_scalar(draws, cfg["kind"])
    obs = _cusum_range(s)
    null = []
    for _ in range(B):
        sh = s[:]
        rng.shuffle(sh)
        null.append(_cusum_range(sh))
    return {"stat": "cusum_range_normalized", "obs": obs,
            "p": empirical_p(obs, null, "greater"), "null_mean": mean(null),
            "B": B, "tail": "greater"}


# --- M5: Bayesian (Dirichlet) smoothing predictive --------------------------
def _walk_forward_topk_number(draws, pool, k, oos_len, score_fn):
    """score_fn(counts_dict, seen) -> dict number->score; bet top-k; return hits list."""
    n = len(draws)
    start = n - oos_len
    counts = Counter()
    for d in draws[:start]:
        counts.update(d)
    seen = start
    hits = []
    for t in range(start, n):
        scores = score_fn(counts, seen, pool)
        topk = sorted(range(1, pool + 1), key=lambda x: -scores[x])[:k]
        hits.append(len(set(topk) & draws[t]))
        counts.update(draws[t])
        seen += 1
    return hits


def m5_bayes(draws, cfg, rng, B):
    pool, k = cfg["pool"], cfg["k"]
    n = len(draws)
    oos_len = min(500, n // 3)
    alpha = 1.0

    def dirichlet_score(counts, seen, pool):
        denom = seen * k + alpha * pool
        return {x: (counts.get(x, 0) + alpha) / denom for x in range(1, pool + 1)}

    hits = _walk_forward_topk_number(draws, pool, k, oos_len, dirichlet_score)
    obs_rate = sum(hits) / (oos_len * k)
    baseline = k / pool  # per-number inclusion prob under uniform
    null = []
    for _ in range(B):
        tot = sum(1 for _ in range(oos_len * k) if rng.random() < baseline)
        null.append(tot / (oos_len * k))
    return {"stat": f"dirichlet_topk_oos_hitrate(oos={oos_len})", "obs": obs_rate,
            "baseline": baseline, "edge": obs_rate - baseline,
            "p": empirical_p(obs_rate, null, "greater"), "null_mean": mean(null),
            "B": B, "tail": "greater"}


# --- M6: Entropy + compression ----------------------------------------------
def _freq_entropy_number(draws, pool):
    c = Counter()
    for d in draws:
        c.update(d)
    tot = sum(c.values()) or 1
    h = 0.0
    for n in range(1, pool + 1):
        p = c.get(n, 0) / tot
        if p > 0:
            h -= p * math.log2(p)
    return h


def _freq_entropy_digit(draws, k):
    c = Counter()
    for d in draws:
        for p in range(k):
            c[(p, d[p])] += 1
    tot = sum(c.values()) or 1
    h = 0.0
    for key, v in c.items():
        p = v / tot
        if p > 0:
            h -= p * math.log2(p)
    return h


def _compression_ratio(draws, kind):
    if kind == "number":
        raw = ";".join(",".join(str(x) for x in sorted(d)) for d in draws).encode()
    else:
        raw = ";".join(",".join(str(x) for x in d) for d in draws).encode()
    comp = zlib.compress(raw, 9)
    return len(comp) / len(raw)


def m6_entropy(draws, cfg, rng, B):
    kind, pool, k = cfg["kind"], cfg["pool"], cfg["k"]
    n = len(draws)
    if kind == "number":
        obs_h = _freq_entropy_number(draws, pool)
    else:
        obs_h = _freq_entropy_digit(draws, k)
    obs_c = _compression_ratio(draws, kind)
    null_h, null_c = [], []
    for _ in range(B):
        sim = (sim_uniform_number_draws(rng, n, pool, k) if kind == "number"
               else sim_uniform_digit_draws(rng, n, k))
        null_h.append(_freq_entropy_number(sim, pool) if kind == "number"
                      else _freq_entropy_digit(sim, k))
        null_c.append(_compression_ratio(sim, kind))
    return {
        "entropy": {"stat": "freq_distribution_shannon_entropy_bits", "obs": obs_h,
                    "p": empirical_p(obs_h, null_h, "two-sided"), "null_mean": mean(null_h),
                    "B": B, "tail": "two-sided"},
        "compression": {"stat": "zlib_compression_ratio", "obs": obs_c,
                        "p": empirical_p(obs_c, null_c, "two-sided"), "null_mean": mean(null_c),
                        "B": B, "tail": "two-sided"},
    }


# --- M7: Spectral / periodogram ---------------------------------------------
def _max_periodogram(s, pmax):
    m = mean(s)
    x = [v - m for v in s]
    n = len(x)
    best = 0.0
    best_p = 0
    for period in range(2, pmax + 1):
        w = 2 * math.pi / period
        a = b = 0.0
        for t in range(n):
            ang = w * t
            a += x[t] * math.cos(ang)
            b += x[t] * math.sin(ang)
        power = (a * a + b * b) / n
        if power > best:
            best, best_p = power, period
    return best, best_p


def m7_spectral(draws, cfg, rng, B):
    s = _draw_scalar(draws, cfg["kind"])
    n = len(s)
    pmax = min(40, n // 4)  # bounded to keep pure-Python periodogram tractable
    obs, obs_period = _max_periodogram(s, pmax)
    null = []
    for _ in range(B):
        sh = s[:]
        rng.shuffle(sh)
        null.append(_max_periodogram(sh, pmax)[0])
    return {"stat": f"max_schuster_periodogram_power(pmax={pmax})", "obs": obs,
            "dominant_period": obs_period, "p": empirical_p(obs, null, "greater"),
            "null_mean": mean(null), "B": B, "tail": "greater"}


# --- M8: Permutation model score (frequency generator gate) -----------------
def m8_perm_model(draws, cfg, rng, B):
    kind, pool, k = cfg["kind"], cfg["pool"], cfg["k"]
    n = len(draws)
    oos_len = min(500, n // 3)
    if kind == "number":
        def freq_score(counts, seen, pool):
            return {x: counts.get(x, 0) for x in range(1, pool + 1)}
        hits = _walk_forward_topk_number(draws, pool, k, oos_len, freq_score)
        obs_rate = sum(hits) / (oos_len * k)
        baseline = k / pool
        null = [sum(1 for _ in range(oos_len * k) if rng.random() < baseline) / (oos_len * k)
                for _ in range(B)]
    else:
        # per-position most-frequent digit generator
        start = n - oos_len
        pos_counts = [Counter() for _ in range(k)]
        for d in draws[:start]:
            for p in range(k):
                pos_counts[p][d[p]] += 1
        correct = 0
        for t in range(start, n):
            for p in range(k):
                pred = max(range(10), key=lambda dd: pos_counts[p].get(dd, 0))
                if pred == draws[t][p]:
                    correct += 1
                pos_counts[p][draws[t][p]] += 1
        obs_rate = correct / (oos_len * k)
        baseline = 0.1
        null = [sum(1 for _ in range(oos_len * k) if rng.random() < baseline) / (oos_len * k)
                for _ in range(B)]
    return {"stat": f"freq_generator_oos_hitrate(oos={oos_len})", "obs": obs_rate,
            "baseline": baseline, "edge": obs_rate - baseline,
            "p": empirical_p(obs_rate, null, "greater"), "null_mean": mean(null),
            "B": B, "tail": "greater"}


# --- M9: Conformal calibration ----------------------------------------------
def m9_conformal(draws, cfg, rng, B):
    pool, k = cfg["pool"], cfg["k"]
    n = len(draws)
    target = 0.80  # nominal coverage
    trivial_size = target * pool

    def run(seq):
        split = int(0.7 * len(seq))
        counts = Counter()
        for d in seq[:split]:
            counts.update(d)
        scores = {x: counts.get(x, 0) for x in range(1, pool + 1)}
        order = sorted(range(1, pool + 1), key=lambda x: -scores[x])
        # smallest prefix set whose calibration coverage >= target
        cal = seq[split:int(0.85 * len(seq))]
        test = seq[int(0.85 * len(seq)):]
        if not cal or not test:
            return 0.0, pool, target
        chosen = pool
        for size in range(1, pool + 1):
            S = set(order[:size])
            cov = mean(len(S & d) / k for d in cal)
            if cov >= target:
                chosen = size
                break
        S = set(order[:chosen])
        test_cov = mean(len(S & d) / k for d in test)
        size_reduction = 1 - chosen / trivial_size
        return size_reduction, chosen, test_cov

    obs_red, obs_size, obs_cov = run(draws)
    null = []
    for _ in range(B):
        sim = sim_uniform_number_draws(rng, n, pool, k)
        null.append(run(sim)[0])
    return {"stat": "conformal_set_size_reduction_vs_trivial", "obs": obs_red,
            "chosen_set_size": obs_size, "test_coverage": obs_cov, "target": target,
            "p": empirical_p(obs_red, null, "greater"), "null_mean": mean(null),
            "B": B, "tail": "greater"}


# --- M10: Feature-bottleneck synthesis --------------------------------------
def _mutual_information_binary(feature_vals, hit_vals, n_bins=3):
    """MI (bits) between a binned feature and a binary hit outcome."""
    pairs = list(zip(feature_vals, hit_vals))
    if not pairs:
        return 0.0
    fv = sorted(set(feature_vals))
    if len(fv) > n_bins:
        qs = [fv[int(len(fv) * i / n_bins)] for i in range(1, n_bins)]

        def binf(v):
            return sum(1 for q in qs if v >= q)
    else:
        def binf(v):
            return v
    joint = Counter()
    fb = Counter()
    hb = Counter()
    for f, h in pairs:
        b = binf(f)
        joint[(b, h)] += 1
        fb[b] += 1
        hb[h] += 1
    tot = len(pairs)
    mi = 0.0
    for (b, h), c in joint.items():
        pxy = c / tot
        px = fb[b] / tot
        py = hb[h] / tot
        if pxy > 0:
            mi += pxy * math.log2(pxy / (px * py))
    return max(0.0, mi)


def m10_bottleneck(draws, cfg):
    pool, k, kind = cfg["pool"], cfg["k"], cfg["kind"]
    n = len(draws)
    baseline = k / pool if kind == "number" else 0.1
    # min detectable edge: power 0.8, alpha 0.05 (two-sided) ~ (1.96+0.84)*SE
    oos_len = min(500, n // 3)
    n_bets = oos_len * k
    se = math.sqrt(baseline * (1 - baseline) / n_bets) if n_bets else float("nan")
    min_detectable_edge = 2.80 * se
    mi_results = {}
    if kind == "number":
        # feature: number's count in trailing window of 50 -> hit next draw
        Wt = 50
        counts = Counter()
        window = []
        feat, hit = [], []
        for t, d in enumerate(draws):
            if t >= Wt:
                for x in range(1, pool + 1):
                    feat.append(counts.get(x, 0))
                    hit.append(1 if x in d else 0)
            window.append(d)
            counts.update(d)
            if len(window) > Wt:
                counts.subtract(window.pop(0))
        mi_results["trailing_freq_to_next_hit_bits"] = _mutual_information_binary(feat, hit)
        # baseline entropy of a per-number bernoulli
        h_base = -(baseline * math.log2(baseline) + (1 - baseline) * math.log2(1 - baseline))
        mi_results["pct_of_outcome_entropy"] = (mi_results["trailing_freq_to_next_hit_bits"] / h_base) if h_base else 0.0
    return {"baseline": baseline, "oos_len": oos_len, "n_bets": n_bets,
            "min_detectable_edge_pp": min_detectable_edge * 100, "mutual_information": mi_results}


# --- BH-FDR / Bonferroni ----------------------------------------------------
def correct(tests):
    """tests: list of dicts with 'p'. Adds bonferroni/BH fields. Returns (m, alpha_bonf)."""
    valid = [t for t in tests if t["p"] == t["p"]]  # drop nan
    m = len(valid)
    alpha = 0.05
    bonf = alpha / m if m else alpha
    for t in valid:
        t["bonferroni_sig"] = t["p"] < bonf
    # BH
    ordered = sorted(valid, key=lambda t: t["p"])
    bh_thresh = 0.0
    for i, t in enumerate(ordered, 1):
        if t["p"] <= (i / m) * alpha:
            bh_thresh = (i / m) * alpha
    for t in valid:
        t["bh_sig"] = t["p"] <= bh_thresh
    return m, bonf


def run_all(db, b_scale=1.0):
    master = random.Random(SEED)
    results = {"seed": SEED, "b_scale": b_scale, "games": {}}
    flat_tests = []

    def B(base):
        return max(50, int(base * b_scale))

    for game, cfg in GAMES.items():
        draws = load_game(db, game)
        n = len(draws)
        g = {"n_draws": n, "config": {kk: cfg[kk] for kk in ("pool", "k", "kind")}, "methods": {}}
        rng = random.Random(master.randrange(1 << 30))
        kind = cfg["kind"]

        def add(label, res, sub=None):
            r = dict(res)
            r["label"] = f"{game}:{label}" + (f":{sub}" if sub else "")
            flat_tests.append(r)
            return r

        # Cheap O(N)/iter methods -> high B (Bonferroni-capable: floor 1/2001 < 0.05/m).
        # Expensive methods -> moderate B (flagged B-capped; low-p ones escalated separately).
        g["methods"]["M1_markov"] = add("M1_markov", m1_markov(draws, cfg, rng, B(2000)))
        if kind == "number":
            g["methods"]["M2_gap"] = add("M2_gap", m2_gap(draws, cfg, rng, B(800)))
        g["methods"]["M3_drift"] = add("M3_drift", m3_drift(draws, cfg, rng, B(500)))
        g["methods"]["M4_changepoint"] = add("M4_changepoint", m4_changepoint(draws, cfg, rng, B(2000)))
        if kind == "number":
            g["methods"]["M5_bayes"] = add("M5_bayes", m5_bayes(draws, cfg, rng, B(2000)))
        m6 = m6_entropy(draws, cfg, rng, B(600))
        g["methods"]["M6_entropy"] = {"entropy": add("M6_entropy", m6["entropy"], "entropy"),
                                      "compression": add("M6_entropy", m6["compression"], "compression")}
        g["methods"]["M7_spectral"] = add("M7_spectral", m7_spectral(draws, cfg, rng, B(400)))
        g["methods"]["M8_perm_model"] = add("M8_perm_model", m8_perm_model(draws, cfg, rng, B(2000)))
        if kind == "number":
            g["methods"]["M9_conformal"] = add("M9_conformal", m9_conformal(draws, cfg, rng, B(600)))
        g["methods"]["M10_bottleneck"] = m10_bottleneck(draws, cfg)  # synthesis, not in p-family
        results["games"][game] = g
        print(f"  [{game}] n={n} done", file=sys.stderr)

    m, bonf = correct(flat_tests)
    results["multiplicity"] = {
        "family_size_m": m, "alpha": 0.05, "bonferroni_alpha": bonf,
        "bonferroni_significant": sorted([t["label"] for t in flat_tests if t.get("bonferroni_sig")]),
        "bh_significant": sorted([t["label"] for t in flat_tests if t.get("bh_sig")]),
        "uncorrected_p_lt_05": sorted([(t["label"], round(t["p"], 4)) for t in flat_tests if t["p"] < 0.05]),
    }
    n_bonf = len(results["multiplicity"]["bonferroni_significant"])
    n_bh = len(results["multiplicity"]["bh_significant"])
    if n_bonf == 0 and n_bh == 0:
        results["classification"] = (
            "P219_TEN_METHOD_DIAGNOSTIC_SWEEP_COMPLETE_NULL"
            if not results["multiplicity"]["uncorrected_p_lt_05"]
            else "P219_TEN_METHOD_DIAGNOSTIC_SWEEP_COMPLETE_WITH_EXPLORATORY_WEAK")
    else:
        results["classification"] = "P219_TEN_METHOD_DIAGNOSTIC_SWEEP_COMPLETE_WITH_CORRECTED_SIGNAL"
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--b-scale", type=float, default=1.0, help="scale all B (replicates)")
    ap.add_argument("--out", default="outputs/research/p219_external_method_diagnostic_sweep_20260605")
    args = ap.parse_args()
    db = resolve_db(args.db)
    print(f"DB(ro)={db}", file=sys.stderr)
    res = run_all(db, b_scale=args.b_scale)
    out_json = args.out + ".json"
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(res, f, indent=2)
    print(f"wrote {out_json}", file=sys.stderr)
    print(json.dumps({"classification": res["classification"],
                      "family_size": res["multiplicity"]["family_size_m"],
                      "bonferroni_sig": res["multiplicity"]["bonferroni_significant"],
                      "bh_sig": res["multiplicity"]["bh_significant"],
                      "uncorrected_p_lt_05": res["multiplicity"]["uncorrected_p_lt_05"]}, indent=2))
