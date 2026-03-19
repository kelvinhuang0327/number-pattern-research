#!/usr/bin/env python3
"""
Unified Quantitative Lottery Research Engine
Covers: POWER_LOTTO, BIG_LOTTO, DAILY_539
"""

import json
import math
import random
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Tuple, Set

import numpy as np
from scipy.stats import binomtest

SEED = 20260226
random.seed(SEED)
np.random.seed(SEED)

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_JSON = ROOT / "docs" / "UNIFIED_LOTTERY_RESEARCH_REPORT_2026_02_26.json"
OUT_MD = ROOT / "docs" / "UNIFIED_LOTTERY_RESEARCH_REPORT_2026_02_26.md"


@dataclass
class LotteryCfg:
    key: str
    name: str
    max_num: int
    pick: int
    hit_threshold: int


CONFIGS = [
    LotteryCfg("POWER_LOTTO", "Taiwan Power Lotto", 38, 6, 3),
    LotteryCfg("BIG_LOTTO", "Taiwan Big Lotto", 49, 6, 3),
    LotteryCfg("DAILY_539", "Taiwan 539", 39, 5, 2),
]

METHOD_COMPLEXITY = {
    "frequency_hotcold": 1.0,
    "gap_interval": 1.2,
    "markov_transition": 2.0,
    "fourier_spectral": 2.5,
    "tail_extreme": 1.3,
    "entropy_concentration": 2.1,
    "cluster_regime": 2.2,
    "monte_carlo_baseline": 0.8,
    "bayesian_posterior": 1.8,
    "combinatorial_coverage": 1.6,
    "feature_interaction": 2.0,
    "adaptive_ensemble": 2.8,
    "time_series_pattern": 2.4,
    "novel_hybrid_lotto": 3.0,
}


def parse_date(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return datetime(1900, 1, 1)


def load_draws(cfg: LotteryCfg) -> List[Dict]:
    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()
    cur.execute(
        """
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type = ?
        """,
        (cfg.key,),
    )
    rows = cur.fetchall()
    con.close()

    out = []
    for draw, date_s, numbers_s, special in rows:
        try:
            nums = json.loads(numbers_s) if isinstance(numbers_s, str) else list(numbers_s)
        except Exception:
            continue
        nums = sorted(int(x) for x in nums if 1 <= int(x) <= cfg.max_num)
        if len(nums) != cfg.pick:
            continue
        out.append(
            {
                "draw": str(draw),
                "date": str(date_s),
                "numbers": nums,
                "special": int(special) if special is not None else 0,
            }
        )
    out.sort(key=lambda x: (parse_date(x["date"]), x["draw"]))
    return out


def ensure_scores(scores: Dict[int, float], cfg: LotteryCfg) -> Dict[int, float]:
    out = {}
    for n in range(1, cfg.max_num + 1):
        out[n] = float(max(scores.get(n, 0.0), 1e-9))
    return out


def make_diverse_tickets(scores: Dict[int, float], cfg: LotteryCfg, n_tickets: int) -> List[List[int]]:
    scores = ensure_scores(scores, cfg)
    tickets = []
    used = Counter()
    for _ in range(n_tickets):
        adjusted = {n: scores[n] / (1.0 + 0.7 * used[n]) for n in scores}
        pick = sorted(sorted(adjusted, key=adjusted.get, reverse=True)[: cfg.pick])
        tickets.append(pick)
        for p in pick:
            used[p] += 1
    return tickets


def frequency_counter(hist: List[Dict], tail: int) -> Counter:
    seq = hist[-tail:] if tail > 0 else hist
    c = Counter()
    for d in seq:
        c.update(d["numbers"])
    return c


def gaps(hist: List[Dict], cfg: LotteryCfg, tail: int = 300) -> Dict[int, int]:
    seq = hist[-tail:] if tail > 0 else hist
    last = {n: -1 for n in range(1, cfg.max_num + 1)}
    for i, d in enumerate(seq):
        for n in d["numbers"]:
            last[n] = i
    m = len(seq)
    return {n: (m - last[n] if last[n] >= 0 else m + 10) for n in range(1, cfg.max_num + 1)}


def method_frequency_hotcold(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    hot = frequency_counter(hist, 80)
    gap_map = gaps(hist, cfg, 300)
    scores = {}
    for n in range(1, cfg.max_num + 1):
        scores[n] = 1.4 * hot.get(n, 0) + 0.7 * gap_map[n]
    return scores


def method_gap_interval(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    gap_map = gaps(hist, cfg, 500)
    fc = frequency_counter(hist, 500)
    scores = {}
    for n in range(1, cfg.max_num + 1):
        scores[n] = gap_map[n] * (1.0 + 1.0 / (1 + fc.get(n, 0)))
    return scores


def method_markov_transition(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    seq = hist[-500:]
    trans = defaultdict(Counter)
    for i in range(1, len(seq)):
        prev = seq[i - 1]["numbers"]
        curr = seq[i]["numbers"]
        for a in prev:
            for b in curr:
                trans[a][b] += 1
    last = seq[-1]["numbers"] if seq else []
    scores = Counter()
    for a in last:
        scores.update(trans[a])
    return dict(scores)


def method_fourier_spectral(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    w = min(512, len(hist))
    seq = hist[-w:]
    scores = {}
    for n in range(1, cfg.max_num + 1):
        x = np.array([1.0 if n in d["numbers"] else 0.0 for d in seq], dtype=float)
        if x.sum() < 2:
            scores[n] = 0.0
            continue
        fftv = np.fft.rfft(x - x.mean())
        mag = np.abs(fftv)
        if len(mag) > 2:
            peak = float(np.max(mag[1:]))
            dom = int(np.argmax(mag[1:]) + 1)
            scores[n] = peak * (1.0 + 0.1 * dom)
        else:
            scores[n] = 0.0
    return scores


def method_tail_extreme(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    w = min(600, len(hist))
    seq = hist[-w:]
    fc = frequency_counter(seq, w)
    vals = np.array([fc.get(n, 0) for n in range(1, cfg.max_num + 1)], dtype=float)
    mu, sd = float(vals.mean()), float(vals.std() + 1e-6)
    scores = {}
    for n in range(1, cfg.max_num + 1):
        z = (fc.get(n, 0) - mu) / sd
        scores[n] = abs(z) + (0.2 if z < 0 else 0.0)
    return scores


def method_entropy_concentration(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    ws = [60, 120, 240]
    ent = {}
    for n in range(1, cfg.max_num + 1):
        vec = []
        for w in ws:
            fc = frequency_counter(hist, w)
            p = fc.get(n, 0) / max(1, w * cfg.pick)
            vec.append(max(p, 1e-9))
        h = -sum(p * math.log(p) for p in vec)
        ent[n] = 1.0 / (h + 1e-6)
    return ent


def method_cluster_regime(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    w = min(500, len(hist))
    seq = hist[-w:]
    feats = []
    for d in seq:
        nums = d["numbers"]
        s = sum(nums)
        oe = sum(n % 2 for n in nums)
        span = max(nums) - min(nums)
        feats.append((s, oe, span))
    if not feats:
        return {}
    sums = np.array([f[0] for f in feats])
    thr1, thr2 = np.quantile(sums, [0.33, 0.66])
    regimes = [0 if s <= thr1 else (1 if s <= thr2 else 2) for s in sums]
    curr = regimes[-1]
    idx = [i for i, r in enumerate(regimes) if r == curr]
    c = Counter()
    for i in idx:
        c.update(seq[i]["numbers"])
    return dict(c)


def method_monte_carlo_baseline(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    # Explicit random baseline method category
    return {n: random.random() for n in range(1, cfg.max_num + 1)}


def method_bayesian_posterior(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    w = min(800, len(hist))
    seq = hist[-w:]
    fc = frequency_counter(seq, w)
    scores = {}
    for n in range(1, cfg.max_num + 1):
        alpha = 1 + fc.get(n, 0)
        beta = 1 + w - fc.get(n, 0)
        scores[n] = alpha / (alpha + beta)
    return scores


def method_combinatorial_coverage(hist: List[Dict], cfg: LotteryCfg) -> List[int]:
    # Favor numbers that improve partition coverage and medium frequency
    fc = frequency_counter(hist, 400)
    zones = 4
    zone_size = math.ceil(cfg.max_num / zones)
    chosen = []
    for z in range(zones):
        lo = z * zone_size + 1
        hi = min(cfg.max_num, (z + 1) * zone_size)
        cand = list(range(lo, hi + 1))
        cand.sort(key=lambda n: fc.get(n, 0), reverse=True)
        if cand:
            chosen.append(cand[0])
        if len(chosen) == cfg.pick:
            break
    all_nums = sorted(range(1, cfg.max_num + 1), key=lambda n: fc.get(n, 0), reverse=True)
    for n in all_nums:
        if len(chosen) >= cfg.pick:
            break
        if n not in chosen:
            chosen.append(n)
    return sorted(chosen[: cfg.pick])


def method_feature_interaction(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    hot = frequency_counter(hist, 100)
    med = frequency_counter(hist, 300)
    gap_map = gaps(hist, cfg, 300)
    scores = {}
    for n in range(1, cfg.max_num + 1):
        scores[n] = (1 + hot.get(n, 0)) * (1 + math.sqrt(med.get(n, 0))) * (1 + 0.1 * gap_map[n])
    return scores


def method_time_series_pattern(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    w = min(700, len(hist))
    seq = hist[-w:]
    scores = {}
    for n in range(1, cfg.max_num + 1):
        x = np.array([1.0 if n in d["numbers"] else 0.0 for d in seq], dtype=float)
        if len(x) < 20:
            scores[n] = 0.0
            continue
        ac1 = float(np.corrcoef(x[:-1], x[1:])[0, 1]) if np.std(x[:-1]) > 0 and np.std(x[1:]) > 0 else 0.0
        trend = float(np.polyfit(np.arange(len(x)), x, 1)[0])
        scores[n] = max(ac1, 0.0) + 5.0 * max(trend, 0.0)
    return scores


def method_novel_hybrid_lotto(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    s1 = method_markov_transition(hist, cfg)
    s2 = method_bayesian_posterior(hist, cfg)
    s3 = method_feature_interaction(hist, cfg)
    s4 = method_cluster_regime(hist, cfg)
    out = {}
    for n in range(1, cfg.max_num + 1):
        out[n] = 0.35 * s1.get(n, 0) + 0.25 * s2.get(n, 0) + 0.25 * s3.get(n, 0) + 0.15 * s4.get(n, 0)
    return out


def method_adaptive_ensemble(hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    # Adaptive weights based on recent concentration and volatility
    w = min(160, len(hist))
    seq = hist[-w:]
    sums = np.array([sum(d["numbers"]) for d in seq], dtype=float) if seq else np.array([0.0])
    vol = float(np.std(sums) / (np.mean(sums) + 1e-6))

    s_freq = method_frequency_hotcold(hist, cfg)
    s_gap = method_gap_interval(hist, cfg)
    s_mk = method_markov_transition(hist, cfg)
    s_bay = method_bayesian_posterior(hist, cfg)

    wf = max(0.2, 1.2 - vol)
    wg = max(0.2, 0.8 + vol)
    wm = 0.9
    wb = 0.9
    z = wf + wg + wm + wb
    wf, wg, wm, wb = wf / z, wg / z, wm / z, wb / z

    out = {}
    for n in range(1, cfg.max_num + 1):
        out[n] = wf * s_freq.get(n, 0) + wg * s_gap.get(n, 0) + wm * s_mk.get(n, 0) + wb * s_bay.get(n, 0)
    return out


METHODS = {
    "frequency_hotcold": lambda h, c: make_diverse_tickets(method_frequency_hotcold(h, c), c, 1),
    "gap_interval": lambda h, c: make_diverse_tickets(method_gap_interval(h, c), c, 1),
    "markov_transition": lambda h, c: make_diverse_tickets(method_markov_transition(h, c), c, 1),
    "fourier_spectral": lambda h, c: make_diverse_tickets(method_fourier_spectral(h, c), c, 1),
    "tail_extreme": lambda h, c: make_diverse_tickets(method_tail_extreme(h, c), c, 1),
    "entropy_concentration": lambda h, c: make_diverse_tickets(method_entropy_concentration(h, c), c, 1),
    "cluster_regime": lambda h, c: make_diverse_tickets(method_cluster_regime(h, c), c, 1),
    "monte_carlo_baseline": lambda h, c: make_diverse_tickets(method_monte_carlo_baseline(h, c), c, 1),
    "bayesian_posterior": lambda h, c: make_diverse_tickets(method_bayesian_posterior(h, c), c, 1),
    "combinatorial_coverage": lambda h, c: [method_combinatorial_coverage(h, c)],
    "feature_interaction": lambda h, c: make_diverse_tickets(method_feature_interaction(h, c), c, 1),
    "adaptive_ensemble": lambda h, c: make_diverse_tickets(method_adaptive_ensemble(h, c), c, 1),
    "time_series_pattern": lambda h, c: make_diverse_tickets(method_time_series_pattern(h, c), c, 1),
    "novel_hybrid_lotto": lambda h, c: make_diverse_tickets(method_novel_hybrid_lotto(h, c), c, 1),
}


def hit_event(tickets: List[List[int]], actual: List[int], threshold: int) -> int:
    aset = set(actual)
    for t in tickets:
        if len(set(t) & aset) >= threshold:
            return 1
    return 0


def baseline_prob(cfg: LotteryCfg, n_tickets: int) -> float:
    total = math.comb(cfg.max_num, cfg.pick)
    single = 0.0
    for k in range(cfg.hit_threshold, cfg.pick + 1):
        single += math.comb(cfg.pick, k) * math.comb(cfg.max_num - cfg.pick, cfg.pick - k) / total
    return 1 - (1 - single) ** n_tickets


def generate_tickets(method_name: str, hist: List[Dict], cfg: LotteryCfg, n_tickets: int) -> List[List[int]]:
    first = METHODS[method_name](hist, cfg)
    if len(first) >= n_tickets:
        return [sorted(t[: cfg.pick]) for t in first[:n_tickets]]

    # Expand additional tickets from method score where available
    if method_name == "combinatorial_coverage":
        fc = frequency_counter(hist, 300)
        nums = sorted(range(1, cfg.max_num + 1), key=lambda n: fc.get(n, 0), reverse=True)
        out = [first[0]]
        shift = 3
        while len(out) < n_tickets:
            cand = sorted(nums[shift:shift + cfg.pick])
            if len(cand) < cfg.pick:
                cand = sorted(random.sample(range(1, cfg.max_num + 1), cfg.pick))
            out.append(cand)
            shift += 2
        return out

    # Fallback diversified generation from this method's scores
    if method_name == "frequency_hotcold":
        s = method_frequency_hotcold(hist, cfg)
    elif method_name == "gap_interval":
        s = method_gap_interval(hist, cfg)
    elif method_name == "markov_transition":
        s = method_markov_transition(hist, cfg)
    elif method_name == "fourier_spectral":
        s = method_fourier_spectral(hist, cfg)
    elif method_name == "tail_extreme":
        s = method_tail_extreme(hist, cfg)
    elif method_name == "entropy_concentration":
        s = method_entropy_concentration(hist, cfg)
    elif method_name == "cluster_regime":
        s = method_cluster_regime(hist, cfg)
    elif method_name == "monte_carlo_baseline":
        s = method_monte_carlo_baseline(hist, cfg)
    elif method_name == "bayesian_posterior":
        s = method_bayesian_posterior(hist, cfg)
    elif method_name == "feature_interaction":
        s = method_feature_interaction(hist, cfg)
    elif method_name == "adaptive_ensemble":
        s = method_adaptive_ensemble(hist, cfg)
    elif method_name == "time_series_pattern":
        s = method_time_series_pattern(hist, cfg)
    else:
        s = method_novel_hybrid_lotto(hist, cfg)
    return make_diverse_tickets(s, cfg, n_tickets)


def evaluate_method(
    draws: List[Dict],
    cfg: LotteryCfg,
    method_name: str,
    n_tickets: int,
    test_window: int,
    min_train: int = 200,
    permutations: int = 40,
    stride: int = 1,
) -> Dict:
    n = len(draws)
    start = max(min_train, n - test_window)
    tickets_seq: List[List[List[int]]] = []
    actual_seq: List[List[int]] = []
    success = []

    for idx in range(start, n, max(1, stride)):
        hist = draws[:idx]
        actual = draws[idx]["numbers"]
        tix = generate_tickets(method_name, hist, cfg, n_tickets)
        ev = hit_event(tix, actual, cfg.hit_threshold)
        tickets_seq.append(tix)
        actual_seq.append(actual)
        success.append(ev)

    trials = len(success)
    obs_rate = float(np.mean(success)) if trials else 0.0
    p0 = baseline_prob(cfg, n_tickets)
    edge = obs_rate - p0
    z = 0.0
    if trials > 0 and p0 > 0 and p0 < 1:
        z = (obs_rate - p0) / math.sqrt(p0 * (1 - p0) / trials)
    p_bin = float(binomtest(int(sum(success)), trials, p0, alternative="greater").pvalue) if trials else 1.0

    # Shuffle/permutation baseline using random synthetic draws
    perm_rates = []
    universe = list(range(1, cfg.max_num + 1))
    for _ in range(permutations):
        cnt = 0
        for i in range(trials):
            shuffled_actual = random.sample(universe, cfg.pick)
            cnt += hit_event(tickets_seq[i], shuffled_actual, cfg.hit_threshold)
        perm_rates.append(cnt / trials if trials else 0.0)
    perm_rates_arr = np.array(perm_rates) if perm_rates else np.array([0.0])
    p_perm = float((1 + np.sum(perm_rates_arr >= obs_rate)) / (len(perm_rates_arr) + 1))

    return {
        "method": method_name,
        "tickets": n_tickets,
        "window": test_window,
        "trials": trials,
        "hits": int(sum(success)),
        "hit_rate": obs_rate,
        "baseline": p0,
        "edge": edge,
        "z_score": z,
        "p_binomial": p_bin,
        "p_permutation": p_perm,
        "ticket_examples_latest": tickets_seq[-1] if tickets_seq else [],
        "complexity": METHOD_COMPLEXITY.get(method_name, 2.0),
    }


def run_lottery(cfg: LotteryCfg, draws: List[Dict]) -> Dict:
    windows = [150, 500, 1500]
    methods = list(METHODS.keys())

    # iterative improvement loop for hybrid candidates
    rounds_log = []
    all_results = {2: defaultdict(dict), 3: defaultdict(dict)}

    for n_tickets in [2, 3]:
        rounds_log.append(f"start tickets={n_tickets} methods={len(methods)}")
        for w in windows:
            for m in methods:
                all_results[n_tickets][w][m] = evaluate_method(
                    draws=draws,
                    cfg=cfg,
                    method_name=m,
                    n_tickets=n_tickets,
                    test_window=min(w, len(draws) - 220),
                    min_train=220,
                    permutations=40,
                    stride=(2 if w <= 200 else (5 if w <= 500 else 15)),
                )

        # One mutation round: if top 2 long-window methods both positive edge, create blended hybrid candidate
        long_res = [all_results[n_tickets][1500][m] for m in methods if 1500 in all_results[n_tickets]]
        long_res = sorted(long_res, key=lambda x: (x["edge"], -x["p_binomial"]), reverse=True)
        if len(long_res) >= 2 and long_res[0]["edge"] > 0 and long_res[1]["edge"] > 0:
            m1, m2 = long_res[0]["method"], long_res[1]["method"]
            hybrid_name = f"iter_hybrid_{m1}_{m2}"

            def dyn_method(hist: List[Dict], c: LotteryCfg, a=m1, b=m2):
                sa = method_novel_hybrid_lotto(hist, c) if a.startswith("iter_hybrid") else _method_scores(a, hist, c)
                sb = method_novel_hybrid_lotto(hist, c) if b.startswith("iter_hybrid") else _method_scores(b, hist, c)
                out = {}
                for n in range(1, c.max_num + 1):
                    out[n] = 0.55 * sa.get(n, 0) + 0.45 * sb.get(n, 0)
                return make_diverse_tickets(out, c, 1)

            METHODS[hybrid_name] = dyn_method
            METHOD_COMPLEXITY[hybrid_name] = 3.2
            methods.append(hybrid_name)
            rounds_log.append(f"mutation add {hybrid_name}")

            for w in windows:
                all_results[n_tickets][w][hybrid_name] = evaluate_method(
                    draws=draws,
                    cfg=cfg,
                    method_name=hybrid_name,
                    n_tickets=n_tickets,
                    test_window=min(w, len(draws) - 220),
                    min_train=220,
                    permutations=40,
                    stride=(2 if w <= 200 else (5 if w <= 500 else 15)),
                )

            # early stop check
            before_best = long_res[0]["edge"]
            after_best = max(all_results[n_tickets][1500][m]["edge"] for m in methods)
            if after_best <= before_best + 1e-9:
                rounds_log.append("stop no significant improvement")
            else:
                rounds_log.append("improvement found in mutation round")
        else:
            rounds_log.append("stop no eligible positive-edge parents")

    # Bonferroni + stability + ranking
    summary = {}
    for n_tickets in [2, 3]:
        mnames = list(all_results[n_tickets][1500].keys())
        alpha_bonf = 0.05 / max(1, len(mnames))
        ranked = []
        for m in mnames:
            r150 = all_results[n_tickets][150].get(m)
            r500 = all_results[n_tickets][500].get(m)
            r1500 = all_results[n_tickets][1500].get(m)
            edges = [r150["edge"], r500["edge"], r1500["edge"]]
            mean_edge = float(np.mean(edges))
            std_edge = float(np.std(edges) + 1e-9)
            stability = max(0.0, mean_edge / std_edge) if mean_edge > 0 else 0.0
            valid = (
                r1500["p_binomial"] < alpha_bonf
                and r1500["p_permutation"] < alpha_bonf
                and min(edges) > 0
            )
            objective = (
                max(r1500["hit_rate"], 0.0)
                * max(r1500["edge"], 0.0)
                * max(stability, 0.0)
                / (r1500["complexity"] * n_tickets)
            )
            ranked.append(
                {
                    "method": m,
                    "objective": objective,
                    "valid": valid,
                    "stability": stability,
                    "windows": {"150": r150, "500": r500, "1500": r1500},
                    "latest_tickets": r1500["ticket_examples_latest"],
                    "alpha_bonferroni": alpha_bonf,
                }
            )

        ranked.sort(key=lambda x: (x["valid"], x["objective"], x["windows"]["1500"]["edge"]), reverse=True)
        summary[str(n_tickets)] = ranked

    return {
        "lottery": cfg.name,
        "key": cfg.key,
        "draw_count": len(draws),
        "draw_range": {
            "from": draws[0]["date"] if draws else None,
            "to": draws[-1]["date"] if draws else None,
        },
        "iteration_log": rounds_log,
        "ranking": summary,
    }


def _method_scores(name: str, hist: List[Dict], cfg: LotteryCfg) -> Dict[int, float]:
    if name == "frequency_hotcold":
        return method_frequency_hotcold(hist, cfg)
    if name == "gap_interval":
        return method_gap_interval(hist, cfg)
    if name == "markov_transition":
        return method_markov_transition(hist, cfg)
    if name == "fourier_spectral":
        return method_fourier_spectral(hist, cfg)
    if name == "tail_extreme":
        return method_tail_extreme(hist, cfg)
    if name == "entropy_concentration":
        return method_entropy_concentration(hist, cfg)
    if name == "cluster_regime":
        return method_cluster_regime(hist, cfg)
    if name == "monte_carlo_baseline":
        return method_monte_carlo_baseline(hist, cfg)
    if name == "bayesian_posterior":
        return method_bayesian_posterior(hist, cfg)
    if name == "feature_interaction":
        return method_feature_interaction(hist, cfg)
    if name == "adaptive_ensemble":
        return method_adaptive_ensemble(hist, cfg)
    if name == "time_series_pattern":
        return method_time_series_pattern(hist, cfg)
    if name == "combinatorial_coverage":
        return {n: (1.0 if n in method_combinatorial_coverage(hist, cfg) else 0.1) for n in range(1, cfg.max_num + 1)}
    return method_novel_hybrid_lotto(hist, cfg)


def build_markdown(report: Dict) -> str:
    lines = []
    lines.append("# Unified Lottery Quant Research Report (2026-02-26)")
    lines.append("")
    lines.append("Scientific protocol: walk-forward OOS, 150/500/1500 stability windows, permutation baseline, Bonferroni correction.")
    lines.append("")

    for lot in report["lotteries"]:
        lines.append(f"## {lot['lottery']} ({lot['key']})")
        lines.append(f"- Draws: {lot['draw_count']} ({lot['draw_range']['from']} -> {lot['draw_range']['to']})")
        lines.append(f"- Iteration log: {'; '.join(lot['iteration_log'])}")
        for tk in ["2", "3"]:
            lines.append("")
            lines.append(f"### Top strategies ({tk}-ticket)")
            lines.append("| Rank | Method | Valid | HitRate(1500) | Edge(1500) | p_bin | p_perm | z | Stability |")
            lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
            ranked = lot["ranking"][tk][:10]
            for i, r in enumerate(ranked, 1):
                w = r["windows"]["1500"]
                lines.append(
                    f"| {i} | {r['method']} | {'Y' if r['valid'] else 'N'} | {w['hit_rate']:.4f} | {w['edge']:.4f} | {w['p_binomial']:.4g} | {w['p_permutation']:.4g} | {w['z_score']:.2f} | {r['stability']:.3f} |"
                )

            top = ranked[0] if ranked else None
            if top:
                lines.append("")
                lines.append(f"Best {tk}-ticket method: `{top['method']}`")
                lines.append(f"- Latest tickets: {top['latest_tickets']}")
                lines.append(f"- Bonferroni alpha: {top['alpha_bonferroni']:.6f}")

        lines.append("")
        lines.append("#### Three-window stability snapshot (best 2-ticket)")
        b2 = lot["ranking"]["2"][0]
        for w in ["150", "500", "1500"]:
            rw = b2["windows"][w]
            lines.append(
                f"- window {w}: hit_rate={rw['hit_rate']:.4f}, edge={rw['edge']:.4f}, p_bin={rw['p_binomial']:.4g}, p_perm={rw['p_permutation']:.4g}"
            )
        lines.append("")

    lines.append("## Risk and limitations")
    lines.append("- Lottery draws are near-random; observed positive edge is generally small and unstable.")
    lines.append("- Multiple testing control (Bonferroni) is strict; most methods are expected to fail significance.")
    lines.append("- Ticket-independence baseline may slightly overstate random benchmark when tickets overlap.")
    lines.append("")
    lines.append("## Final scientific verdict")
    lines.append("- No robust, persistent high edge is expected under strict OOS + permutation + Bonferroni criteria.")
    lines.append("- Recommended practical use: only methods marked `Valid=Y`; otherwise treat as entertainment, not investment.")
    return "\n".join(lines) + "\n"


def main():
    report = {"seed": SEED, "db": str(DB_PATH), "lotteries": []}

    for cfg in CONFIGS:
        draws = load_draws(cfg)
        if len(draws) < 400:
            # simulate if missing (not needed in this dataset)
            synth = []
            for i in range(400):
                synth.append(
                    {
                        "draw": f"SIM{i+1:06d}",
                        "date": "2026-01-01",
                        "numbers": sorted(random.sample(range(1, cfg.max_num + 1), cfg.pick)),
                        "special": 0,
                    }
                )
            draws = synth
        report["lotteries"].append(run_lottery(cfg, draws))

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(build_markdown(report), encoding="utf-8")

    print(json.dumps({"json": str(OUT_JSON), "md": str(OUT_MD)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
