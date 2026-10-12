"""No-DB Big Lotto adapters recovered from current and deleted strategy sources.

This module is quarantined from production registries and DB-backed loaders. All
entrypoints accept in-memory draw history ordered old-to-new and return
``list[list[int]]`` containing sorted 6-number Big Lotto main-number bets.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from itertools import combinations
from typing import Callable, Iterable

MAX_NUM = 49
PICK = 6


ADAPTER_METADATA = {
    "adapt_biglotto_p0_2bet": {
        "source_strategy_id": "biglotto_p0_2bet",
        "classification": "CURRENT_EXECUTABLE_NOT_REPLAYED",
        "parity_status": "PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS",
        "bet_count": 2,
        "source_path": "tools/quick_predict.py",
        "lineage_label": "quick_predict.biglotto_p0_2bet current source",
    },
    "adapt_predict_biglotto_echo_2bet": {
        "source_strategy_id": "predict_biglotto_echo_2bet",
        "classification": "CURRENT_EXECUTABLE_NOT_REPLAYED",
        "parity_status": "PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS",
        "bet_count": 2,
        "source_path": "tools/predict_biglotto_echo_2bet.py",
        "lineage_label": "echo-aware deviation 2bet current source",
    },
    "adapt_predict_biglotto_echo_phase2_2bet": {
        "source_strategy_id": "predict_biglotto_echo_phase2",
        "classification": "CURRENT_EXECUTABLE_NOT_REPLAYED",
        "parity_status": "PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS",
        "bet_count": 2,
        "source_path": "tools/predict_biglotto_echo_phase2.py",
        "lineage_label": "phase2 adaptive echo 2bet current source",
    },
    "adapt_predict_biglotto_echo_phase2_3bet": {
        "source_strategy_id": "predict_biglotto_echo_phase2",
        "classification": "CURRENT_EXECUTABLE_NOT_REPLAYED",
        "parity_status": "PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS",
        "bet_count": 3,
        "source_path": "tools/predict_biglotto_echo_phase2.py",
        "lineage_label": "phase2 adaptive echo 3bet current source",
    },
    "adapt_predict_biglotto_echo_mixed_3bet": {
        "source_strategy_id": "predict_biglotto_echo_mixed_3bet",
        "classification": "CURRENT_EXECUTABLE_NOT_REPLAYED",
        "parity_status": "PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS",
        "bet_count": 3,
        "source_path": "tools/predict_biglotto_echo_3bet.py",
        "lineage_label": "echo-aware mixed 3bet current source",
    },
    "adapt_biglotto_zonal_pruning": {
        "source_strategy_id": "biglotto_zonal_pruning",
        "classification": "HISTORICAL_RESTORABLE_NEEDS_ADAPTER",
        "parity_status": "PARITY_PARTIAL_SHAPE_ONLY",
        "bet_count": 4,
        "source_path": "tools/biglotto_zonal_pruning.py",
        "lineage_label": "zonal pruning with local cluster-pivot replica",
    },
    "adapt_biglotto_5bet_orthogonal": {
        "source_strategy_id": "biglotto_5bet_orthogonal",
        "classification": "HISTORICAL_RESTORABLE_NEEDS_ADAPTER",
        "parity_status": "PARITY_PARTIAL_SHAPE_ONLY",
        "bet_count": 5,
        "source_path": "tools/quick_predict.py; tools/backtest_biglotto_5bet_ts3markov.py",
        "lineage_label": "TS3/Markov/FreqOrt 5bet no-DB safety replica",
    },
    "adapt_biglotto_10bet_combined": {
        "source_strategy_id": "biglotto_10bet_combined",
        "classification": "HISTORICAL_RESTORABLE_NEEDS_ADAPTER",
        "parity_status": "PARITY_PARTIAL_SHAPE_ONLY",
        "bet_count": 10,
        "source_path": "tools/backtest_biglotto_10bet_combined.py; tools/quick_predict.py@73062646^",
        "historical_commit": "73062646^",
        "lineage_label": "deleted 10bet combined script plus historical p1 deviation helper",
    },
    "adapt_predict_biglotto_regime_3bet": {
        "source_strategy_id": "predict_biglotto_regime",
        "classification": "HISTORICAL_RESTORABLE_NEEDS_ADAPTER",
        "parity_status": "PARITY_PARTIAL_SHAPE_ONLY",
        "bet_count": 3,
        "source_path": "tools/predict_biglotto_regime.py",
        "historical_commit": "73062646^",
        "lineage_label": "deleted predict_biglotto_regime.generate_ts3_regime",
    },
}


def normalize_history(history: Iterable[dict]) -> list[dict]:
    draws: list[dict] = []
    for idx, draw in enumerate(history):
        numbers = sorted(int(n) for n in draw.get("numbers", []))
        if len(numbers) != PICK or len(set(numbers)) != PICK:
            raise ValueError(f"draw {idx} must contain 6 unique main numbers")
        if any(n < 1 or n > MAX_NUM for n in numbers):
            raise ValueError(f"draw {idx} has out-of-range Big Lotto number")
        draws.append({**draw, "numbers": numbers})
    if not draws:
        raise ValueError("history must contain at least one Big Lotto draw")
    return draws


def _clean_bets(bets: Iterable[Iterable[int]], expected_count: int | None = None) -> list[list[int]]:
    cleaned: list[list[int]] = []
    for bet in bets:
        numbers = sorted(int(n) for n in bet)
        if len(numbers) != PICK or len(set(numbers)) != PICK:
            raise ValueError(f"adapter produced invalid Big Lotto bet: {numbers}")
        if any(n < 1 or n > MAX_NUM for n in numbers):
            raise ValueError(f"adapter produced out-of-range Big Lotto bet: {numbers}")
        cleaned.append(numbers)
    if expected_count is not None and len(cleaned) != expected_count:
        raise ValueError(f"expected {expected_count} bets, got {len(cleaned)}")
    return cleaned


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pstdev(values: list[float]) -> float:
    if not values:
        return 0.0
    mu = _mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / len(values))


def adapt_biglotto_p0_2bet(history: Iterable[dict], window: int = 50, echo_boost: float = 1.5) -> list[list[int]]:
    draws = normalize_history(history)
    recent = draws[-window:] if len(draws) > window else draws
    expected = len(recent) * PICK / MAX_NUM
    freq = Counter(n for d in recent for n in d["numbers"])
    scores = {n: freq.get(n, 0) - expected for n in range(1, MAX_NUM + 1)}
    if len(draws) >= 3:
        for n in draws[-2]["numbers"]:
            scores[n] += echo_boost
    hot = sorted([(n, s) for n, s in scores.items() if s > 1], key=lambda item: item[1], reverse=True)
    cold = sorted([(n, abs(s)) for n, s in scores.items() if s < -1], key=lambda item: item[1], reverse=True)
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1)
    if len(bet1) < PICK:
        for n in sorted(range(1, MAX_NUM + 1), key=lambda num: abs(scores[num])):
            if n not in used and len(bet1) < PICK:
                bet1.append(n)
                used.add(n)
    bet2: list[int] = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
            used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n)
                used.add(n)
    return _clean_bets([bet1, bet2], 2)


def _echo_detector(history: list[dict], max_lag: int = 5) -> dict[int, float]:
    if len(history) < max_lag + 1:
        return {}
    latest = set(history[-1]["numbers"])
    echo_scores: Counter[int] = Counter()
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)]["numbers"])
        overlap = latest & past
        if len(overlap) >= 2:
            weight = len(overlap) / PICK * (1.0 / lag)
            for n in overlap:
                echo_scores[n] += weight * 0.5
            for n in past - latest:
                echo_scores[n] += weight
    if echo_scores:
        max_score = max(echo_scores.values())
        if max_score > 0:
            return {n: score / max_score for n, score in echo_scores.items()}
    return dict(echo_scores)


def _continuous_temperature(history: list[dict], window: int = 50) -> dict[int, float]:
    recent = history[-window:] if len(history) > window else history
    short_window = min(20, len(recent))
    short_recent = history[-short_window:] if len(history) > short_window else history
    freq_long = Counter(n for d in recent for n in d["numbers"])
    freq_short = Counter(n for d in short_recent for n in d["numbers"])
    gaps = {}
    for n in range(1, MAX_NUM + 1):
        gap = 0
        for d in reversed(history):
            if n in d["numbers"]:
                break
            gap += 1
        gaps[n] = gap
    freq_sorted = sorted(freq_long.get(n, 0) for n in range(1, MAX_NUM + 1))
    temperatures = {}
    for n in range(1, MAX_NUM + 1):
        f = freq_long.get(n, 0)
        freq_component = sum(1 for v in freq_sorted if v <= f) / MAX_NUM
        gap_component = math.exp(-gaps[n] / (MAX_NUM / PICK))
        expected_short = short_window * PICK / MAX_NUM
        expected_long = len(recent) * PICK / MAX_NUM
        short_ratio = freq_short.get(n, 0) / max(expected_short, 0.1)
        long_ratio = f / max(expected_long, 0.1)
        trend_component = min(1.0, max(0.0, 0.5 + (short_ratio - long_ratio) * 0.5))
        temperatures[n] = 0.40 * freq_component + 0.30 * gap_component + 0.30 * trend_component
    return temperatures


def adapt_predict_biglotto_echo_2bet(history: Iterable[dict], window: int = 50, echo_weight: float = 0.25) -> list[list[int]]:
    draws = normalize_history(history)
    temps = _continuous_temperature(draws, window)
    echoes = _echo_detector(draws)
    hot_scores = {}
    cold_scores = {}
    for n in range(1, MAX_NUM + 1):
        temp = temps.get(n, 0.5)
        echo = echoes.get(n, 0.0)
        hot_scores[n] = temp * (1 - echo_weight) + echo * echo_weight
        cold_scores[n] = (1 - temp) * (1 - echo_weight) + echo * echo_weight
    bet1 = sorted(sorted(range(1, MAX_NUM + 1), key=lambda n: hot_scores[n], reverse=True)[:PICK])
    used = set(bet1)
    bet2 = [n for n in sorted(range(1, MAX_NUM + 1), key=lambda n: cold_scores[n], reverse=True) if n not in used][:PICK]
    return _clean_bets([bet1, bet2], 2)


def _structural_score(bet: list[int]) -> int:
    total = sum(bet)
    odd = sum(1 for n in bet if n % 2 == 1)
    zones = [0, 0, 0]
    for n in bet:
        zones[0 if n <= 16 else 1 if n <= 33 else 2] += 1
    consec = sum(1 for idx in range(len(bet) - 1) if bet[idx + 1] - bet[idx] == 1)
    spread = bet[-1] - bet[0]
    score = 0
    if 100 <= total <= 200:
        score += 2
    if 120 <= total <= 180:
        score += 2
    if 2 <= odd <= 4:
        score += 2
    if all(z >= 1 for z in zones):
        score += 2
    if consec <= 1:
        score += 1
    if spread >= 25:
        score += 1
    return score


def _echo_signal_strength(history: list[dict], max_lag: int = 5) -> float:
    if len(history) < max_lag + 1:
        return 0.0
    latest = set(history[-1]["numbers"])
    total_score = 0.0
    max_possible = 0.0
    for lag in range(1, max_lag + 1):
        past = set(history[-(lag + 1)]["numbers"])
        weight = 1.0 / lag
        max_possible += PICK * weight
        total_score += len(latest & past) * weight
    return min(1.0, total_score / max_possible) if max_possible else 0.0


def _rolling_echo_accuracy(history: list[dict], lookback: int = 50, echo_threshold: float = 0.3) -> float:
    if len(history) < lookback + 10:
        return 0.5
    hits = 0
    events = 0
    for idx in range(max(10, len(history) - lookback), len(history)):
        echoes = _echo_detector(history[:idx])
        echo_nums = {n for n, score in echoes.items() if score > echo_threshold}
        if echo_nums:
            events += 1
            if echo_nums & set(history[idx]["numbers"]):
                hits += 1
    return hits / events if events else 0.5


def _adaptive_echo_weight(history: list[dict], base_weight: float = 0.25, lookback: int = 50) -> tuple[float, float, float]:
    strength = _echo_signal_strength(history)
    accuracy = _rolling_echo_accuracy(history, lookback)
    strength_factor = min(1.5, max(0.3, 0.3 + strength * 2.4))
    accuracy_factor = min(1.5, max(0.3, 0.3 + accuracy * 1.7))
    weight = min(0.50, max(0.05, base_weight * strength_factor * accuracy_factor))
    return weight, strength, accuracy


def adapt_predict_biglotto_echo_phase2_2bet(history: Iterable[dict], window: int = 50, lookback: int = 50) -> list[list[int]]:
    draws = normalize_history(history)
    weight, _, _ = _adaptive_echo_weight(draws, lookback=lookback)
    return adapt_predict_biglotto_echo_2bet(draws, window=window, echo_weight=weight)


def _best_structural_combo(candidates: list[int], tiebreaker: Callable[[list[int]], float]) -> list[int] | None:
    if len(candidates) < PICK:
        return None
    best_bet = None
    best_score = -1.0
    for combo in combinations(candidates, PICK):
        bet = sorted(combo)
        score = _structural_score(bet) + tiebreaker(bet) * 0.1
        if score > best_score:
            best_score = score
            best_bet = bet
    return best_bet


def adapt_predict_biglotto_echo_mixed_3bet(history: Iterable[dict], window: int = 50, echo_weight: float = 0.25) -> list[list[int]]:
    draws = normalize_history(history)
    first_two = adapt_predict_biglotto_echo_2bet(draws, window=window, echo_weight=echo_weight)
    used = set(first_two[0]) | set(first_two[1])
    temps = _continuous_temperature(draws, window)
    echoes = _echo_detector(draws)
    bet3_scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
        temp = temps.get(n, 0.5)
        warm_proximity = 1.0 - abs(temp - 0.5) * 2.0
        bet3_scores[n] = echoes.get(n, 0.0) * 0.5 + warm_proximity * 0.5
    candidates = sorted(bet3_scores.keys(), key=lambda n: bet3_scores[n], reverse=True)[:18]
    if len(candidates) < PICK:
        candidates = [n for n in range(1, MAX_NUM + 1) if n not in used]
    best_bet = _best_structural_combo(sorted(candidates[:12]), lambda bet: sum(bet3_scores.get(n, 0) for n in bet) / PICK)
    return _clean_bets(first_two + [best_bet or sorted(candidates[:PICK])], 3)


def adapt_predict_biglotto_echo_phase2_3bet(history: Iterable[dict], window: int = 50, lookback: int = 50) -> list[list[int]]:
    draws = normalize_history(history)
    weight, _, _ = _adaptive_echo_weight(draws, lookback=lookback)
    first_two = adapt_predict_biglotto_echo_2bet(draws, window=window, echo_weight=weight)
    used = set(first_two[0]) | set(first_two[1])
    temps = _continuous_temperature(draws, window)
    echoes = _echo_detector(draws)
    bet3_scores = {}
    for n in range(1, MAX_NUM + 1):
        if n in used:
            continue
        temp = temps.get(n, 0.5)
        warm_proximity = 1.0 - abs(temp - 0.5) * 2.0
        echo_share = min(0.7, weight * 2)
        bet3_scores[n] = echoes.get(n, 0.0) * echo_share + warm_proximity * (1 - echo_share)
    candidates = sorted(bet3_scores.keys(), key=lambda n: bet3_scores[n], reverse=True)[:12]
    if len(candidates) < PICK:
        candidates = [n for n in range(1, MAX_NUM + 1) if n not in used]
    best_bet = _best_structural_combo(sorted(candidates), lambda bet: sum(bet3_scores.get(n, 0) for n in bet) / PICK)
    return _clean_bets(first_two + [best_bet or sorted(candidates[:PICK])], 3)


def _dft_fourier_scores(history: list[dict], window: int = 500) -> dict[int, float]:
    sample = history[-window:] if len(history) >= window else history
    width = len(sample)
    if width < 3:
        return {n: 0.0 for n in range(1, MAX_NUM + 1)}
    scores = {}
    for n in range(1, MAX_NUM + 1):
        series = [1.0 if n in d["numbers"] else 0.0 for d in sample]
        if sum(series) < 2:
            scores[n] = 0.0
            continue
        mu = _mean(series)
        best_k = None
        best_amp = -1.0
        for k in range(1, (width // 2) + 1):
            real = 0.0
            imag = 0.0
            for idx, value in enumerate(series):
                angle = -2.0 * math.pi * k * idx / width
                centered = value - mu
                real += centered * math.cos(angle)
                imag += centered * math.sin(angle)
            amp = math.hypot(real, imag)
            if amp > best_amp:
                best_amp = amp
                best_k = k
        if not best_k:
            scores[n] = 0.0
            continue
        period = width / best_k
        if 2 < period < width / 2:
            last_hit = max(idx for idx, value in enumerate(series) if value == 1.0)
            gap = (width - 1) - last_hit
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[n] = 0.0
    return scores


def _sum_target(history: list[dict]) -> tuple[float, float]:
    sample = history[-300:] if len(history) >= 300 else history
    sums = [sum(d["numbers"]) for d in sample]
    mu = _mean(sums)
    sigma = _pstdev(sums)
    last_sum = sum(history[-1]["numbers"])
    if last_sum < mu - 0.5 * sigma:
        return mu, mu + sigma
    if last_sum > mu + 0.5 * sigma:
        return mu - sigma, mu
    return mu - 0.5 * sigma, mu + 0.5 * sigma


def _fourier_bet(history: list[dict], window: int = 500) -> list[int]:
    scores = _dft_fourier_scores(history, window=window)
    return sorted(sorted(scores, key=lambda n: scores[n], reverse=True)[:PICK])


def _cold_sum_bet(history: list[dict], exclude: set[int] | None = None, window: int = 100, pool_size: int = 12) -> list[int]:
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d["numbers"])
    candidates = sorted([n for n in range(1, MAX_NUM + 1) if n not in exclude], key=lambda n: freq.get(n, 0))
    if len(history) < 2 or pool_size <= PICK:
        return sorted(candidates[:PICK])
    pool = candidates[:pool_size]
    target_low, target_high = _sum_target(history)
    midpoint = (target_low + target_high) / 2.0
    best_combo = None
    best_dist = float("inf")
    best_in_range = False
    for combo in combinations(pool, PICK):
        total = sum(combo)
        in_range = target_low <= total <= target_high
        dist = abs(total - midpoint)
        if in_range and (not best_in_range or dist < best_dist):
            best_combo, best_dist, best_in_range = combo, dist, True
        elif not in_range and not best_in_range and dist < best_dist:
            best_combo, best_dist = combo, dist
    return sorted(best_combo or pool[:PICK])


def _tail_balance_bet(history: list[dict], exclude: set[int] | None = None, window: int = 100) -> list[int]:
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d["numbers"])
    tail_groups = {tail: [] for tail in range(10)}
    for n in range(1, MAX_NUM + 1):
        if n not in exclude:
            tail_groups[n % 10].append((n, freq.get(n, 0)))
    for tail in tail_groups:
        tail_groups[tail].sort(key=lambda item: item[1], reverse=True)
    available_tails = sorted([t for t in range(10) if tail_groups[t]], key=lambda t: tail_groups[t][0][1], reverse=True)
    idx_in_group = {t: 0 for t in range(10)}
    selected: list[int] = []
    while len(selected) < PICK:
        added = False
        for tail in available_tails:
            if len(selected) >= PICK:
                break
            if idx_in_group[tail] < len(tail_groups[tail]):
                num, _ = tail_groups[tail][idx_in_group[tail]]
                if num not in selected:
                    selected.append(num)
                    added = True
                idx_in_group[tail] += 1
        if not added:
            break
    if len(selected) < PICK:
        remaining = [n for n in range(1, MAX_NUM + 1) if n not in selected and n not in exclude]
        remaining.sort(key=lambda n: freq.get(n, 0), reverse=True)
        selected.extend(remaining[: PICK - len(selected)])
    return sorted(selected[:PICK])


def _markov_bet(history: list[dict], exclude: set[int] | None = None, markov_window: int = 30) -> list[int]:
    exclude = exclude or set()
    recent = history[-markov_window:] if len(history) >= markov_window else history
    transitions = Counter()
    for idx in range(len(recent) - 1):
        for prev in recent[idx]["numbers"]:
            for nxt in recent[idx + 1]["numbers"]:
                transitions[(prev, nxt)] += 1
    scores = Counter()
    for prev in history[-1]["numbers"]:
        for n in range(1, MAX_NUM + 1):
            scores[n] += transitions.get((prev, n), 0)
    candidates = sorted([n for n in range(1, MAX_NUM + 1) if n not in exclude], key=lambda n: scores[n], reverse=True)
    return sorted(candidates[:PICK])


def _frequency_bet(history: list[dict], exclude: set[int] | None = None, window: int = 100) -> list[int]:
    exclude = exclude or set()
    recent = history[-window:] if len(history) >= window else history
    freq = Counter(n for d in recent for n in d["numbers"])
    candidates = sorted([n for n in range(1, MAX_NUM + 1) if n not in exclude], key=lambda n: freq.get(n, 0), reverse=True)
    return sorted(candidates[:PICK])


def adapt_biglotto_5bet_orthogonal(history: Iterable[dict]) -> list[list[int]]:
    draws = normalize_history(history)
    bet1 = _fourier_bet(draws)
    bet2 = _cold_sum_bet(draws, exclude=set(bet1))
    bet3 = _tail_balance_bet(draws, exclude=set(bet1) | set(bet2))
    used = set(bet1) | set(bet2) | set(bet3)
    bet4 = _markov_bet(draws, exclude=used, markov_window=30)
    bet5 = _frequency_bet(draws, exclude=used | set(bet4))
    return _clean_bets([bet1, bet2, bet3, bet4, bet5], 5)


def _cluster_pivot(history: list[dict], n_bets: int = 4, window: int = 150) -> list[list[int]]:
    recent = history[-window:]
    cooccur = Counter()
    for d in recent:
        for pair in combinations(sorted(d["numbers"]), 2):
            cooccur[pair] += 1
    num_scores = Counter()
    for (a, b), count in cooccur.items():
        num_scores[a] += count
        num_scores[b] += count
    centers = [num for num, _ in num_scores.most_common(n_bets)]
    bets = []
    exclude: set[int] = set()
    for center in centers:
        candidates = Counter()
        for (a, b), count in cooccur.items():
            if a == center and b not in exclude:
                candidates[b] += count
            elif b == center and a not in exclude:
                candidates[a] += count
        bet = [center]
        for n, _ in candidates.most_common(5):
            if n not in bet:
                bet.append(n)
        if len(bet) < PICK:
            for n in range(1, MAX_NUM + 1):
                if n not in bet and n not in exclude:
                    bet.append(n)
                if len(bet) == PICK:
                    break
        bets.append(sorted(bet[:PICK]))
        exclude.update(bet[:2])
    return bets


def _zone(n: int) -> int:
    return (n - 1) // 7


def adapt_biglotto_zonal_pruning(history: Iterable[dict], n_bets: int = 4, window: int = 150) -> list[list[int]]:
    draws = normalize_history(history)
    base_bets = _cluster_pivot(draws, n_bets=n_bets * 3, window=window)
    zone_counts = Counter(len({_zone(n) for n in d["numbers"]}) for d in draws[-200:])
    typical_zones = {count for count, _ in zone_counts.most_common(2)}
    pruned = []
    for bet in base_bets:
        if len({_zone(n) for n in bet}) in typical_zones:
            pruned.append(bet)
            if len(pruned) >= n_bets:
                break
    return _clean_bets(pruned or base_bets[:n_bets], n_bets)


def _detect_sum_regime(history: list[dict], lookback: int = 10, threshold: int = 5) -> tuple[str, int, float]:
    if len(history) < 50:
        return "NEUTRAL", 0, 0.0
    sums = [sum(d["numbers"]) for d in (history[-300:] if len(history) >= 300 else history)]
    mu = _mean(sums)
    sigma = _pstdev(sums)
    if sigma < 1e-6:
        return "NEUTRAL", 0, 0.0
    recent_sums = [sum(d["numbers"]) for d in history[-lookback:]]
    consec_above = 0
    z_above = 0.0
    for total in reversed(recent_sums):
        if total > mu:
            consec_above += 1
            z_above += (total - mu) / sigma
        else:
            break
    consec_below = 0
    z_below = 0.0
    for total in reversed(recent_sums):
        if total < mu:
            consec_below += 1
            z_below += (mu - total) / sigma
        else:
            break
    if consec_above >= threshold:
        return "HIGH_REGIME", consec_above, z_above / consec_above
    if consec_below >= threshold:
        return "LOW_REGIME", consec_below, z_below / consec_below
    return "NEUTRAL", 0, 0.0


def _apply_regime_weight(scores: dict[int, float], regime: str, strength: float = 0.3) -> dict[int, float]:
    if regime == "NEUTRAL":
        return scores
    adjusted = {}
    for n, score in scores.items():
        if regime == "HIGH_REGIME":
            adjusted[n] = score * (1.0 + strength) if n <= 25 else score * (1.0 - strength)
        elif regime == "LOW_REGIME":
            adjusted[n] = score * (1.0 + strength) if n > 25 else score * (1.0 - strength)
    return adjusted


def _fourier_regime_bet(history: list[dict], regime: str = "NEUTRAL", regime_strength: float = 0.3) -> list[int]:
    scores = _apply_regime_weight(_dft_fourier_scores(history, window=500), regime, regime_strength)
    return sorted(sorted(scores, key=lambda n: scores[n], reverse=True)[:PICK])


def _cold_regime_bet(history: list[dict], exclude: set[int] | None = None, regime: str = "NEUTRAL") -> list[int]:
    exclude = exclude or set()
    recent = history[-100:]
    freq = Counter(n for d in recent for n in d["numbers"])
    sorted_cold = sorted([n for n in range(1, MAX_NUM + 1) if n not in exclude], key=lambda n: freq.get(n, 0))
    if regime == "HIGH_REGIME":
        pool = ([n for n in sorted_cold if n <= 25][:12] + [n for n in sorted_cold if n > 25][:6])[:12]
    elif regime == "LOW_REGIME":
        pool = ([n for n in sorted_cold if n > 25][:12] + [n for n in sorted_cold if n <= 25][:6])[:12]
    else:
        pool = sorted_cold[:12]
    if len(pool) < PICK:
        return sorted(pool + [n for n in range(1, MAX_NUM + 1) if n not in set(pool) | exclude][: PICK - len(pool)])
    target_low, target_high = _sum_target(history)
    midpoint = (target_low + target_high) / 2.0
    best_combo = None
    best_dist = float("inf")
    for combo in combinations(pool, PICK):
        dist = abs(sum(combo) - midpoint)
        if dist < best_dist:
            best_combo, best_dist = combo, dist
    return sorted(best_combo or pool[:PICK])


def adapt_predict_biglotto_regime_3bet(history: Iterable[dict]) -> list[list[int]]:
    draws = normalize_history(history)
    regime, _, _ = _detect_sum_regime(draws)
    if regime == "NEUTRAL":
        bet1 = _fourier_bet(draws)
        bet2 = _cold_sum_bet(draws, exclude=set(bet1))
        bet3 = _tail_balance_bet(draws, exclude=set(bet1) | set(bet2))
        return _clean_bets([bet1, bet2, bet3], 3)
    bet1 = _fourier_regime_bet(draws, regime=regime)
    bet2 = _cold_regime_bet(draws, exclude=set(bet1), regime=regime)
    bet3 = _tail_balance_bet(draws, exclude=set(bet1) | set(bet2))
    return _clean_bets([bet1, bet2, bet3], 3)


def _markov_ratio_scores(history: list[dict], window: int = 30) -> Counter[int]:
    recent = history[-window:]
    transitions: defaultdict[int, Counter[int]] = defaultdict(Counter)
    for idx in range(len(recent) - 1):
        for current in recent[idx]["numbers"]:
            for nxt in recent[idx + 1]["numbers"]:
                transitions[current][nxt] += 1
    scores: Counter[int] = Counter()
    for prev in history[-1]["numbers"]:
        trans = transitions.get(prev, Counter())
        total = sum(trans.values())
        if total > 0:
            for n, count in trans.items():
                scores[n] += count / total
    return scores


def _dev_complement_2bet(history: list[dict], exclude: set[int] | None = None, window: int = 50) -> list[list[int]]:
    exclude = exclude or set()
    recent = history[-window:]
    expected = len(recent) * PICK / MAX_NUM
    freq = Counter(n for d in recent for n in d["numbers"])
    hot = []
    cold = []
    for n in range(1, MAX_NUM + 1):
        if n in exclude:
            continue
        dev = freq.get(n, 0) - expected
        if dev > 1:
            hot.append((n, dev))
        elif dev < -1:
            cold.append((n, abs(dev)))
    hot.sort(key=lambda item: item[1], reverse=True)
    cold.sort(key=lambda item: item[1], reverse=True)
    bet1 = [n for n, _ in hot[:PICK]]
    used = set(bet1) | exclude
    if len(bet1) < PICK:
        candidates = [num for num in range(1, MAX_NUM + 1) if num not in used]
        for n in sorted(candidates, key=lambda num: abs(freq.get(num, 0) - expected)):
            if len(bet1) < PICK:
                bet1.append(n)
                used.add(n)
    bet2 = []
    for n, _ in cold:
        if n not in used and len(bet2) < PICK:
            bet2.append(n)
            used.add(n)
    if len(bet2) < PICK:
        for n in range(1, MAX_NUM + 1):
            if n not in used and len(bet2) < PICK:
                bet2.append(n)
                used.add(n)
    return [sorted(bet1[:PICK]), sorted(bet2[:PICK])]


def _bet5_sum_conditional(history: list[dict], pool: list[int]) -> list[int]:
    if len(pool) <= PICK:
        return sorted(pool[:PICK])
    sums = [sum(d["numbers"]) for d in history[-300:]]
    mu = _mean(sums)
    sigma = _pstdev(sums)
    last_sum = sum(history[-1]["numbers"])
    if last_sum < mu - 0.5 * sigma:
        target_low, target_high = mu, mu + sigma
    elif last_sum > mu + 0.5 * sigma:
        target_low, target_high = mu - sigma, mu
    else:
        target_low, target_high = mu - 0.5 * sigma, mu + 0.5 * sigma
    freq = Counter(n for d in history[-100:] for n in d["numbers"])
    expected = len(history[-100:]) * PICK / MAX_NUM
    pool_candidates = sorted(pool, key=lambda n: abs(freq.get(n, 0) - expected))[:18]
    midpoint = (target_low + target_high) / 2.0
    best = None
    best_dist = float("inf")
    for combo in combinations(pool_candidates, PICK):
        dist = abs(sum(combo) - midpoint)
        if dist < best_dist:
            best, best_dist = combo, dist
    return sorted(best or pool_candidates[:PICK])


def _p1_deviation_5bet(history: list[dict]) -> list[list[int]]:
    neighbor_pool = set()
    for n in history[-1]["numbers"]:
        for delta in (-1, 0, 1):
            candidate = n + delta
            if 1 <= candidate <= MAX_NUM:
                neighbor_pool.add(candidate)
    f_scores = _dft_fourier_scores(history, window=500)
    mk_scores = _markov_ratio_scores(history, window=30)
    f_max = max(f_scores.values()) or 1.0
    mk_max = max(mk_scores.values()) or 1.0
    scored = {n: f_scores.get(n, 0.0) / f_max + 0.5 * (mk_scores.get(n, 0.0) / mk_max) for n in neighbor_pool}
    bet1 = sorted(sorted(neighbor_pool, key=lambda n: scored[n], reverse=True)[:PICK])
    used = set(bet1)
    bet2 = _cold_sum_bet(history, exclude=used)
    used.update(bet2)
    bet3, bet4 = _dev_complement_2bet(history, exclude=used)
    used.update(bet3)
    used.update(bet4)
    bet5 = _bet5_sum_conditional(history, [n for n in range(1, MAX_NUM + 1) if n not in used])
    return [bet1, bet2, bet3, bet4, bet5]


def adapt_biglotto_10bet_combined(history: Iterable[dict]) -> list[list[int]]:
    draws = normalize_history(history)
    return _clean_bets(adapt_biglotto_5bet_orthogonal(draws) + _p1_deviation_5bet(draws), 10)
