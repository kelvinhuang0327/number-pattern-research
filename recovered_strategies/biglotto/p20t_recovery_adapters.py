"""Exact, cutoff-safe adapters recovered for the P20T governed identities.

Only strategy functions that accept caller-supplied old-to-new history are
exposed here.  Database loading, CLI output, reporting, and parameter search
from the historical scripts are deliberately excluded.
"""

from __future__ import annotations

import math
from collections import Counter
from itertools import combinations
from typing import Iterable

import numpy as np
from scipy.fft import fft, fftfreq

from recovered_strategies.biglotto.historical_adapters import (
    adapt_biglotto_zonal_pruning,
    normalize_history,
)


MAX_NUM = 49
PICK = 6
HISTORICAL_SOURCE_COMMIT = "28940a2572c051c6ba8b2ab6a077f706e800477d"
COMBINED_10BET_SOURCE_COMMIT = "285e161e7798d961002bf17fa5dc61ee8cffecda"


def _acb_predict(history: list[dict], *, window: int) -> list[int]:
    """Historical ``AdaptiveACB('BIG_LOTTO', window=...)`` prediction."""

    recent = history[-window:] if len(history) >= window else history
    counter = Counter({number: 0 for number in range(1, MAX_NUM + 1)})
    last_seen: dict[int, int] = {}
    for index, draw in enumerate(recent):
        for number in draw["numbers"]:
            counter[number] += 1
            last_seen[number] = index

    expected_frequency = len(recent) * PICK / MAX_NUM
    boundary_low = math.ceil(MAX_NUM * 0.13)
    boundary_high = MAX_NUM - boundary_low + 1
    scores: dict[int, float] = {}
    for number in range(1, MAX_NUM + 1):
        gap = len(recent) - last_seen.get(number, -1)
        frequency_deficit = expected_frequency - counter[number]
        gap_score = gap / (len(recent) / 2) if recent else 0.0
        boundary_bonus = (
            1.2 if number <= boundary_low or number >= boundary_high else 1.0
        )
        modulo_bonus = 1.1 if number % 3 == 0 else 1.0
        scores[number] = (
            (frequency_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * modulo_bonus
        )

    ranked = sorted(scores, key=lambda number: -scores[number])
    selected = ranked[:PICK]
    zone_size = MAX_NUM / 3

    def zone(number: int) -> int:
        return min(int((number - 1) / zone_size), 2)

    represented = {zone(number) for number in selected}
    if len(represented) < 2:
        for missing_zone in set(range(3)) - represented:
            zone_numbers = [
                number
                for number in range(1, MAX_NUM + 1)
                if zone(number) == missing_zone
            ]
            selected[-1] = sorted(zone_numbers, key=lambda number: -scores[number])[0]
            break
    return sorted(selected)


def _hot_feature(history: list[dict], window: int = 50) -> list[int]:
    frequency = Counter(
        number for draw in history[-window:] for number in draw["numbers"]
    )
    ranked = sorted(range(1, MAX_NUM + 1), key=lambda number: -frequency.get(number, 0))
    return sorted(ranked[:PICK])


def _fourier_feature(history: list[dict], window: int = 500) -> list[int]:
    recent = history[-window:] if len(history) >= window else history
    width = len(recent)
    scores: dict[int, float] = {}
    for number in range(1, MAX_NUM + 1):
        bitstream = np.zeros(width)
        for index, draw in enumerate(recent):
            if number in draw["numbers"]:
                bitstream[index] = 1
        if sum(bitstream) < 2:
            scores[number] = 0.0
            continue
        transformed = np.fft.fft(bitstream - np.mean(bitstream))
        frequencies = np.fft.fftfreq(width, 1)
        positive = np.where(frequencies > 0)
        amplitudes = np.abs(transformed[positive])
        positive_frequencies = frequencies[positive]
        peak = np.argmax(amplitudes)
        frequency = positive_frequencies[peak]
        if frequency == 0:
            scores[number] = 0.0
            continue
        period = 1 / frequency
        last_hit = np.where(bitstream == 1)[0][-1]
        gap = (width - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    ranked = [
        number
        for number in sorted(scores, key=lambda value: -scores[value])
        if scores[number] > 0
    ]
    return sorted(ranked[:PICK])


def adapt_acb_hot_fourier_3bet(history: Iterable[dict]) -> list[list[int]]:
    """Recover the committed ACB + hot-50 + Fourier-500 three-bet."""

    draws = normalize_history(history)
    return [
        _acb_predict(draws, window=100),
        _hot_feature(draws),
        _fourier_feature(draws),
    ]


def adapt_apriori_3bet(history: Iterable[dict]) -> list[list[int]]:
    """Call the exact current historical-cutoff Apriori backtest entrypoint."""

    from tools.backtest_apriori import BacktestApriori

    draws = normalize_history(history)
    return BacktestApriori().predict_for_backtest(draws, num_bets=3, window=150)


def adapt_cluster_pivot_4bet(history: Iterable[dict]) -> list[list[int]]:
    from tools.backtest_cluster_pivot_biglotto import cluster_pivot_4bet

    return cluster_pivot_4bet(normalize_history(history))


def adapt_biglotto_5bet_orthogonal(history: Iterable[dict]) -> list[list[int]]:
    from tools.backtest_big_lotto_orthogonal_5bet import (
        generate_big_lotto_orthogonal_5bet,
    )

    return generate_big_lotto_orthogonal_5bet(normalize_history(history))


def _historical_frequency_orthogonal_5bet(history: list[dict]) -> list[list[int]]:
    """Exact first half of the deleted combined 10-bet strategy."""

    from tools.backtest_biglotto_markov_4bet import (
        cold_numbers_bet,
        fourier_rhythm_bet,
        markov_orthogonal_bet,
        tail_balance_bet,
    )

    bet1 = fourier_rhythm_bet(history, window=500)
    used = set(bet1)
    bet2 = cold_numbers_bet(history, window=100, exclude=used)
    used.update(bet2)
    bet3 = tail_balance_bet(history, window=100, exclude=used)
    used.update(bet3)
    bet4 = markov_orthogonal_bet(history, exclude=used, markov_window=30)
    used.update(bet4)
    recent = history[-100:] if len(history) >= 100 else history
    frequency = Counter(number for draw in recent for number in draw["numbers"])
    remaining = sorted(
        (number for number in range(1, MAX_NUM + 1) if number not in used),
        key=lambda number: -frequency.get(number, 0),
    )
    return [bet1, bet2, bet3, bet4, sorted(remaining[:PICK])]


def _p1_fourier_scores(history: list[dict], window: int = 500) -> dict[int, float]:
    """Historical ``quick_predict._bl_fourier_scores`` implementation."""

    recent = history[-window:] if len(history) >= window else history
    width = len(recent)
    scores: dict[int, float] = {}
    for number in range(1, MAX_NUM + 1):
        bitstream = np.zeros(width)
        for index, draw in enumerate(recent):
            if number in draw["numbers"]:
                bitstream[index] = 1
        if sum(bitstream) < 2:
            scores[number] = 0.0
            continue
        transformed = fft(bitstream - np.mean(bitstream))
        frequencies = fftfreq(width, 1)
        positive = np.where(frequencies > 0)
        amplitudes = np.abs(transformed[positive])
        positive_frequencies = frequencies[positive]
        peak = np.argmax(amplitudes)
        frequency = positive_frequencies[peak]
        if frequency == 0:
            scores[number] = 0.0
            continue
        period = 1 / frequency
        if 2 < period < width / 2:
            last_hit = np.where(bitstream == 1)[0][-1]
            gap = (width - 1) - last_hit
            scores[number] = 1.0 / (abs(gap - period) + 1.0)
        else:
            scores[number] = 0.0
    return scores


def _p1_markov_scores(history: list[dict], window: int = 30) -> Counter[int]:
    recent = history[-window:]
    transitions: dict[int, Counter[int]] = {}
    for index in range(len(recent) - 1):
        for current in recent[index]["numbers"]:
            transitions.setdefault(current, Counter())
            for following in recent[index + 1]["numbers"]:
                transitions[current][following] += 1
    scores: Counter[int] = Counter()
    for previous in history[-1]["numbers"]:
        counts = transitions.get(previous, Counter())
        total = sum(counts.values())
        if total > 0:
            for number, count in counts.items():
                scores[number] += count / total
    return scores


def _p1_cold_sum_fixed(
    history: list[dict], exclude: set[int] | None = None, pool_size: int = 12
) -> list[int]:
    exclude = exclude or set()
    frequency = Counter(number for draw in history[-100:] for number in draw["numbers"])
    candidates = sorted(
        (number for number in range(1, MAX_NUM + 1) if number not in exclude),
        key=lambda number: frequency.get(number, 0),
    )
    pool = candidates[:pool_size]
    draw_sums = [sum(draw["numbers"]) for draw in history[-300:]]
    mean, deviation = np.mean(draw_sums), np.std(draw_sums)
    target_low, target_high = mean - 0.5 * deviation, mean + 0.5 * deviation
    best: tuple[int, ...] | None = None
    best_distance = float("inf")
    best_in_range = False
    for combo in combinations(pool, PICK):
        total = sum(combo)
        in_range = target_low <= total <= target_high
        distance = abs(total - mean)
        if in_range and (not best_in_range or distance < best_distance):
            best, best_distance, best_in_range = combo, distance, True
        elif not in_range and not best_in_range and distance < best_distance:
            best, best_distance = combo, distance
    return sorted(best if best else pool[:PICK])


def _p1_deviation_complement(
    history: list[dict], exclude: set[int] | None = None, window: int = 50
) -> tuple[list[int], list[int]]:
    exclude = exclude or set()
    recent = history[-window:]
    expected = len(recent) * PICK / MAX_NUM
    frequency = Counter(number for draw in recent for number in draw["numbers"])
    hot: list[tuple[int, float]] = []
    cold: list[tuple[int, float]] = []
    for number in range(1, MAX_NUM + 1):
        if number in exclude:
            continue
        deviation = frequency.get(number, 0) - expected
        if deviation > 1:
            hot.append((number, deviation))
        elif deviation < -1:
            cold.append((number, abs(deviation)))
    hot.sort(key=lambda item: -item[1])
    cold.sort(key=lambda item: -item[1])
    bet1 = [number for number, _ in hot[:PICK]]
    used = set(bet1) | exclude
    if len(bet1) < PICK:
        middle = sorted(
            (number for number in range(1, MAX_NUM + 1) if number not in used),
            key=lambda number: abs(frequency.get(number, 0) - expected),
        )
        for number in middle:
            if len(bet1) < PICK:
                bet1.append(number)
                used.add(number)
    bet2: list[int] = []
    for number, _ in cold:
        if number not in used and len(bet2) < PICK:
            bet2.append(number)
            used.add(number)
    if len(bet2) < PICK:
        for number in range(1, MAX_NUM + 1):
            if number not in used and len(bet2) < PICK:
                bet2.append(number)
                used.add(number)
    return sorted(bet1[:PICK]), sorted(bet2[:PICK])


def _p1_sum_conditional(history: list[dict], pool: list[int]) -> list[int]:
    if len(pool) <= PICK:
        return sorted(pool[:PICK])
    draw_sums = [sum(draw["numbers"]) for draw in history[-300:]]
    mean, deviation = np.mean(draw_sums), np.std(draw_sums)
    last_sum = sum(history[-1]["numbers"])
    if last_sum < mean - 0.5 * deviation:
        target_low, target_high = mean, mean + deviation
    elif last_sum > mean + 0.5 * deviation:
        target_low, target_high = mean - deviation, mean
    else:
        target_low, target_high = mean - 0.5 * deviation, mean + 0.5 * deviation
    recent = history[-100:]
    frequency = Counter(number for draw in recent for number in draw["numbers"])
    expected = len(recent) * PICK / MAX_NUM
    candidates = sorted(
        pool, key=lambda number: abs(frequency.get(number, 0) - expected)
    )[:18]
    midpoint = (target_low + target_high) / 2
    best: tuple[int, ...] | None = None
    best_distance = float("inf")
    for combo in combinations(candidates, PICK):
        distance = abs(sum(combo) - midpoint)
        if distance < best_distance:
            best, best_distance = combo, distance
    return sorted(best if best else candidates[:PICK])


def _historical_p1_deviation_5bet(history: list[dict]) -> list[list[int]]:
    neighbor_pool = {
        number + delta
        for number in history[-1]["numbers"]
        for delta in (-1, 0, 1)
        if 1 <= number + delta <= MAX_NUM
    }
    fourier_scores = _p1_fourier_scores(history, window=500)
    markov_scores = _p1_markov_scores(history, window=30)
    fourier_max = max(fourier_scores.values()) or 1
    markov_max = max(markov_scores.values()) or 1
    scores = {
        number: fourier_scores.get(number, 0) / fourier_max
        + 0.5 * (markov_scores.get(number, 0) / markov_max)
        for number in neighbor_pool
    }
    bet1 = sorted(
        sorted(neighbor_pool, key=lambda number: scores[number], reverse=True)[:PICK]
    )
    used = set(bet1)
    bet2 = _p1_cold_sum_fixed(history, exclude=used)
    used.update(bet2)
    bet3, bet4 = _p1_deviation_complement(history, exclude=used)
    used.update(bet3)
    used.update(bet4)
    bet5 = _p1_sum_conditional(
        history, [number for number in range(1, MAX_NUM + 1) if number not in used]
    )
    return [bet1, bet2, bet3, bet4, bet5]


def adapt_biglotto_10bet_combined(history: Iterable[dict]) -> list[list[int]]:
    """Recover the deleted frequency-orthogonal + P1-deviation 10-bet."""

    draws = normalize_history(history)
    return _historical_frequency_orthogonal_5bet(
        draws
    ) + _historical_p1_deviation_5bet(draws)


def _detect_sum_regime(
    history: list[dict], lookback: int = 10, threshold: int = 5
) -> str:
    if len(history) < 50:
        return "NEUTRAL"
    sample = history[-300:] if len(history) >= 300 else history
    draw_sums = [sum(draw["numbers"]) for draw in sample]
    mean, deviation = np.mean(draw_sums), np.std(draw_sums)
    if deviation < 1e-6:
        return "NEUTRAL"
    recent_sums = [sum(draw["numbers"]) for draw in history[-lookback:]]
    consecutive_above = 0
    for total in reversed(recent_sums):
        if total <= mean:
            break
        consecutive_above += 1
    consecutive_below = 0
    for total in reversed(recent_sums):
        if total >= mean:
            break
        consecutive_below += 1
    if consecutive_above >= threshold:
        return "HIGH_REGIME"
    if consecutive_below >= threshold:
        return "LOW_REGIME"
    return "NEUTRAL"


def _regime_fourier_bet(history: list[dict], regime: str) -> list[int]:
    scores = _p1_fourier_scores(history, window=500)
    if regime != "NEUTRAL":
        adjusted: dict[int, float] = {}
        for number, score in scores.items():
            favored = (regime == "HIGH_REGIME" and number <= 25) or (
                regime == "LOW_REGIME" and number > 25
            )
            adjusted[number] = score * (1.3 if favored else 0.7)
        scores = adjusted
    ranked = sorted(scores, key=lambda number: scores[number], reverse=True)
    return sorted(ranked[:PICK])


def _regime_cold_bet(
    history: list[dict], exclude: set[int], regime: str
) -> list[int]:
    recent = history[-100:]
    frequency = Counter(number for draw in recent for number in draw["numbers"])
    cold = sorted(
        (number for number in range(1, MAX_NUM + 1) if number not in exclude),
        key=lambda number: frequency.get(number, 0),
    )
    if regime == "HIGH_REGIME":
        pool = ([number for number in cold if number <= 25][:12]
                + [number for number in cold if number > 25][:6])[:12]
    elif regime == "LOW_REGIME":
        pool = ([number for number in cold if number > 25][:12]
                + [number for number in cold if number <= 25][:6])[:12]
    else:
        pool = cold[:12]
    sample = history[-300:] if len(history) >= 300 else history
    draw_sums = [sum(draw["numbers"]) for draw in sample]
    mean, deviation = np.mean(draw_sums), np.std(draw_sums)
    if regime == "HIGH_REGIME":
        target_low, target_high = mean - 1.5 * deviation, mean - 0.3 * deviation
    elif regime == "LOW_REGIME":
        target_low, target_high = mean + 0.3 * deviation, mean + 1.5 * deviation
    else:
        target_low, target_high = mean - 0.5 * deviation, mean + 0.5 * deviation
    midpoint = (target_low + target_high) / 2
    best: tuple[int, ...] | None = None
    best_distance = float("inf")
    best_in_range = False
    for combo in combinations(pool, PICK):
        total = sum(combo)
        in_range = target_low <= total <= target_high
        distance = abs(total - midpoint)
        if in_range and (not best_in_range or distance < best_distance):
            best, best_distance, best_in_range = combo, distance, True
        elif not in_range and not best_in_range and distance < best_distance:
            best, best_distance = combo, distance
    return sorted(best if best else pool[:PICK])


def adapt_predict_biglotto_regime_3bet(history: Iterable[dict]) -> list[list[int]]:
    """Exact no-DB extraction of deleted ``generate_ts3_regime``."""

    from tools.predict_biglotto_triple_strike import (
        generate_triple_strike,
        tail_balance_bet,
    )

    draws = normalize_history(history)
    regime = _detect_sum_regime(draws)
    if regime == "NEUTRAL":
        return generate_triple_strike(draws)
    bet1 = _regime_fourier_bet(draws, regime)
    used = set(bet1)
    bet2 = _regime_cold_bet(draws, used, regime)
    used.update(bet2)
    bet3 = tail_balance_bet(draws, window=100, exclude=used)
    return [sorted(bet1), sorted(bet2), sorted(bet3)]


def adapt_gap_dynamic_threshold(history: Iterable[dict]) -> list[list[int]]:
    from tools.backtest_gap_dynamic_1500 import triple_strike_gap_dynamic

    return triple_strike_gap_dynamic(
        normalize_history(history), gap_threshold=12, gap_weight=1.0
    )


def adapt_hot_stop_rebound(history: Iterable[dict]) -> list[list[int]]:
    from tools.backtest_biglotto_hot_stop_rebound import generate_hot_stop_bet

    return [
        generate_hot_stop_bet(
            normalize_history(history), freq_threshold=15, gap_threshold=12
        )
    ]


def adapt_markov_repeat_exception(history: Iterable[dict]) -> list[list[int]]:
    from tools.backtest_markov_repeat_exception import generate_ts3_markov4

    return generate_ts3_markov4(
        normalize_history(history), markov_window=30, repeat_boost_factor=0.1
    )


def adapt_ts3_markov_freq_5bet(history: Iterable[dict]) -> list[list[int]]:
    from tools.backtest_biglotto_5bet_ts3markov import (
        generate_ts3_markov_freq_5bet,
    )

    return generate_ts3_markov_freq_5bet(normalize_history(history), markov_window=30)


def adapt_ts3_acb_4bet(history: Iterable[dict]) -> list[list[int]]:
    from tools.predict_biglotto_triple_strike import generate_triple_strike

    draws = normalize_history(history)
    return [*generate_triple_strike(draws), _acb_predict(draws, window=30)]


def _fourier_scores_full(history: list[dict], window: int = 500) -> dict[int, float]:
    recent = history[-window:] if len(history) >= window else history
    width = len(recent)
    scores: dict[int, float] = {}
    for number in range(1, MAX_NUM + 1):
        bitstream = np.zeros(width)
        for index, draw in enumerate(recent):
            if number in draw["numbers"]:
                bitstream[index] = 1
        if sum(bitstream) < 2:
            scores[number] = 0.0
            continue
        transformed = fft(bitstream - np.mean(bitstream))
        frequencies = fftfreq(width, 1)
        positive = np.where(frequencies > 0)
        amplitudes = np.abs(transformed[positive])
        positive_frequencies = frequencies[positive]
        peak = np.argmax(amplitudes)
        frequency = positive_frequencies[peak]
        if frequency == 0:
            scores[number] = 0.0
            continue
        period = 1 / frequency
        last_hit = np.where(bitstream == 1)[0][-1]
        gap = (width - 1) - last_hit
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def _neighbor_set(numbers: Iterable[int]) -> set[int]:
    return {
        number + delta
        for number in numbers
        for delta in (-1, 1)
        if 1 <= number + delta <= MAX_NUM
    }


def _inject_neighbors(
    base_bet: list[int],
    neighbor_ranked: list[int],
    n_inject: int,
    global_used: set[int],
) -> list[int]:
    existing = [number for number in base_bet if number in set(neighbor_ranked)]
    needed = max(0, n_inject - len(existing))
    if needed == 0:
        return sorted(base_bet)
    injected = [
        number
        for number in neighbor_ranked
        if number not in base_bet and number not in global_used
    ][:needed]
    if not injected:
        return sorted(base_bet)
    result = list(base_bet)
    for _ in injected:
        if result:
            result.pop()
    result.extend(injected)
    return sorted(result[:PICK])


def adapt_neighbor_injection(history: Iterable[dict]) -> list[list[int]]:
    """Recover historical P0 Triple Strike neighbor injection (n=1)."""

    from tools.backtest_biglotto_5bet_ts3markov import (
        cold_numbers_bet,
        fourier_rhythm_bet,
        tail_balance_bet,
    )

    draws = normalize_history(history)
    neighbor_pool = _neighbor_set(draws[-1]["numbers"])
    fourier_scores = _fourier_scores_full(draws)
    neighbor_ranked = sorted(
        neighbor_pool, key=lambda number: -fourier_scores.get(number, 0.0)
    )
    bet1 = _inject_neighbors(
        fourier_rhythm_bet(draws, window=500), neighbor_ranked, 1, set()
    )
    used = set(bet1)
    bet2 = _inject_neighbors(
        cold_numbers_bet(draws, window=100, exclude=used),
        [number for number in neighbor_ranked if number not in used],
        1,
        used,
    )
    used.update(bet2)
    bet3 = _inject_neighbors(
        tail_balance_bet(draws, window=100, exclude=used),
        [number for number in neighbor_ranked if number not in used],
        1,
        used,
    )
    return [bet1, bet2, bet3]


__all__ = [
    "adapt_acb_hot_fourier_3bet",
    "adapt_apriori_3bet",
    "adapt_biglotto_10bet_combined",
    "adapt_biglotto_5bet_orthogonal",
    "adapt_biglotto_zonal_pruning",
    "adapt_cluster_pivot_4bet",
    "adapt_gap_dynamic_threshold",
    "adapt_hot_stop_rebound",
    "adapt_markov_repeat_exception",
    "adapt_neighbor_injection",
    "adapt_predict_biglotto_regime_3bet",
    "adapt_ts3_acb_4bet",
    "adapt_ts3_markov_freq_5bet",
]
