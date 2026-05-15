"""
S2 Predictor: 2nd-order Markov + Weibull Gap
===========================================
Reusable scoring/prediction utilities for low-risk temporal-signal research.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Dict, List, Tuple


NUM_POOL = {
    "BIG_LOTTO": 49,
    "POWER_LOTTO": 38,
    "DAILY_539": 39,
}

BET_SIZE = {
    "BIG_LOTTO": 6,
    "POWER_LOTTO": 6,
    "DAILY_539": 5,
}


def _normalize(scores: Dict[int, float]) -> Dict[int, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    mn, mx = min(vals), max(vals)
    if mx - mn <= 1e-12:
        return {k: 0.5 for k in scores}
    return {k: (v - mn) / (mx - mn) for k, v in scores.items()}


def markov2_score_all(
    history: List[dict],
    max_num: int,
    alpha: float = 0.5,
    min_state_count: int = 3,
) -> Dict[int, float]:
    """
    Per-number 2nd-order Markov probability:
    P(X_t=1 | X_{t-1}, X_{t-2}), where X_t is number-presence indicator.
    """
    n = len(history)
    if n < 3:
        return {i: 0.0 for i in range(1, max_num + 1)}

    last = set(int(x) for x in history[-1].get("numbers", []))
    prev = set(int(x) for x in history[-2].get("numbers", []))
    scores: Dict[int, float] = {}

    for num in range(1, max_num + 1):
        state_total = [0, 0, 0, 0]
        state_pos = [0, 0, 0, 0]
        one_total = [0, 0]
        one_pos = [0, 0]
        global_pos = 0
        global_total = 0

        for t in range(2, n):
            x2 = 1 if num in history[t - 2].get("numbers", []) else 0
            x1 = 1 if num in history[t - 1].get("numbers", []) else 0
            xt = 1 if num in history[t].get("numbers", []) else 0

            st = (x2 << 1) | x1
            state_total[st] += 1
            state_pos[st] += xt
            one_total[x1] += 1
            one_pos[x1] += xt
            global_total += 1
            global_pos += xt

        curr_state = ((1 if num in prev else 0) << 1) | (1 if num in last else 0)
        curr_x1 = 1 if num in last else 0
        p0 = (global_pos + alpha) / (global_total + 2 * alpha)

        if state_total[curr_state] >= min_state_count:
            p = (state_pos[curr_state] + alpha) / (state_total[curr_state] + 2 * alpha)
        elif one_total[curr_x1] >= min_state_count:
            p = (one_pos[curr_x1] + alpha) / (one_total[curr_x1] + 2 * alpha)
        else:
            p = p0
        scores[num] = float(p)

    return scores


def markov2_pair_sparse_score_all(
    history: List[dict],
    max_num: int,
    alpha: float = 0.5,
    pair_min_count: int = 3,
) -> Dict[int, float]:
    """
    Sparse pair-wise Markov2:
    P(next_number | a in draw[t-2], b in draw[t-1])
    Keep only pair states with count >= pair_min_count.
    """
    n = len(history)
    if n < 3:
        return {i: 0.0 for i in range(1, max_num + 1)}

    pair_total: Counter = Counter()
    pair_next: Dict[Tuple[int, int], Counter] = defaultdict(Counter)
    global_next: Counter = Counter()
    global_total = 0

    for t in range(2, n):
        d2 = [int(x) for x in history[t - 2].get("numbers", [])]
        d1 = [int(x) for x in history[t - 1].get("numbers", [])]
        dn = [int(x) for x in history[t].get("numbers", [])]
        for x in dn:
            if 1 <= x <= max_num:
                global_next[x] += 1
                global_total += 1
        for a in d2:
            if not (1 <= a <= max_num):
                continue
            for b in d1:
                if not (1 <= b <= max_num):
                    continue
                key = (a, b)
                pair_total[key] += 1
                for x in dn:
                    if 1 <= x <= max_num:
                        pair_next[key][x] += 1

    active_pairs = []
    last2 = [int(x) for x in history[-2].get("numbers", []) if 1 <= int(x) <= max_num]
    last1 = [int(x) for x in history[-1].get("numbers", []) if 1 <= int(x) <= max_num]
    for a in last2:
        for b in last1:
            key = (a, b)
            if pair_total.get(key, 0) >= pair_min_count:
                active_pairs.append(key)

    scores = {}
    p0_denom = global_total + alpha * max_num
    for x in range(1, max_num + 1):
        p0 = (global_next.get(x, 0) + alpha) / max(p0_denom, 1e-9)
        if not active_pairs:
            scores[x] = float(p0)
            continue
        vals = []
        for key in active_pairs:
            den = pair_total[key] + alpha * max_num
            vals.append((pair_next[key].get(x, 0) + alpha) / max(den, 1e-9))
        scores[x] = float(sum(vals) / len(vals))
    return scores


def weibull_gap_score_all(
    history: List[dict],
    max_num: int,
    min_occ: int = 6,
    pressure_boost: float = 0.25,
    regime_boost: Tuple[float, float, float] = (0.92, 1.00, 1.12),
) -> Dict[int, float]:
    """
    Weibull gap hazard score per number.
    Higher hazard => stronger "should reappear soon" signal.
    """
    n = len(history)
    if n < 20:
        return {i: 0.0 for i in range(1, max_num + 1)}

    positions: Dict[int, List[int]] = {i: [] for i in range(1, max_num + 1)}
    for i, d in enumerate(history):
        for x in d.get("numbers", []):
            num = int(x)
            if 1 <= num <= max_num:
                positions[num].append(i)

    out: Dict[int, float] = {}
    for num in range(1, max_num + 1):
        pos = positions[num]
        if not pos:
            out[num] = 0.0
            continue

        current_gap = n - 1 - pos[-1]
        if len(pos) < 2:
            out[num] = float(current_gap)
            continue

        gaps = [pos[i] - pos[i - 1] for i in range(1, len(pos))]
        mean_gap = sum(gaps) / len(gaps)
        if mean_gap <= 0:
            out[num] = 0.0
            continue

        if len(gaps) < min_occ:
            out[num] = current_gap / max(mean_gap, 1e-6)
            continue

        variance = sum((g - mean_gap) ** 2 for g in gaps) / max(len(gaps) - 1, 1)
        std_gap = math.sqrt(max(variance, 1e-9))
        cv = max(std_gap / mean_gap, 1e-6)

        # Empirical approximation between Weibull k and CV.
        k = max(0.5, min(10.0, cv ** -1.086))
        lam = mean_gap / max(math.gamma(1.0 + 1.0 / k), 1e-9)

        g = max(float(current_gap), 1e-6)
        ratio = max(g / max(lam, 1e-9), 1e-9)
        survival = math.exp(-(ratio ** k))
        pdf = (k / max(lam, 1e-9)) * (ratio ** (k - 1.0)) * survival
        hazard = pdf / max(survival, 1e-9)

        pressure = g / max(mean_gap, 1e-6)
        if pressure < 0.8:
            regime_mult = regime_boost[0]
        elif pressure > 1.2:
            regime_mult = regime_boost[2]
        else:
            regime_mult = regime_boost[1]
        out[num] = float(hazard * (1.0 + pressure_boost * pressure) * regime_mult)

    return out


def predict_markov2_weibull(
    history: List[dict],
    lottery_type: str,
    n_bets: int = 2,
    w_markov2: float = 0.62,
    w_weibull: float = 0.38,
    pair_min_count: int = 3,
    diversity_penalty: float = 0.17,
    pressure_boost: float = 0.25,
) -> List[List[int]]:
    max_num = NUM_POOL.get(lottery_type, 49)
    bet_size = BET_SIZE.get(lottery_type, 6)

    s_m2_base = _normalize(markov2_score_all(history, max_num=max_num))
    s_m2_pair = _normalize(
        markov2_pair_sparse_score_all(
            history, max_num=max_num, pair_min_count=pair_min_count
        )
    )
    # Blend simple + sparse pair Markov2 to avoid over-fragile sparse model.
    s_m2 = {n: 0.45 * s_m2_base.get(n, 0.0) + 0.55 * s_m2_pair.get(n, 0.0) for n in range(1, max_num + 1)}
    s_wb = _normalize(
        weibull_gap_score_all(
            history,
            max_num=max_num,
            pressure_boost=pressure_boost,
        )
    )

    fused = {
        n: w_markov2 * s_m2.get(n, 0.0) + w_weibull * s_wb.get(n, 0.0)
        for n in range(1, max_num + 1)
    }
    ranked = sorted(fused, key=lambda x: (-fused[x], x))

    # Greedy diversified multi-bet selection.
    bets: List[List[int]] = []
    used = {n: 0 for n in range(1, max_num + 1)}
    for _ in range(max(1, n_bets)):
        scored = []
        for n in ranked:
            penalty = diversity_penalty * used[n]
            scored.append((fused[n] - penalty, n))
        scored.sort(key=lambda x: (-x[0], x[1]))
        bet = sorted([n for _, n in scored[:bet_size]])
        bets.append(bet)
        for n in bet:
            used[n] += 1
    return bets
