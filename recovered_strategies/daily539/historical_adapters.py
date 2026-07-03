"""P357C quarantined Daily 539 historical adapters.

This module restores the callable prediction surface for three deleted Daily 539
historical candidates under a recovery-only namespace. It deliberately avoids
DatabaseManager, replay registries, strategy status files, services, and DB
paths. Callers must pass in-memory draw history.

Historical evidence:
- tools/backtest_539_3bet_orthogonal.py deleted at 73062646, restorable from 73062646^.
- tools/backtest_539_3bet_f_cold_fmid.py deleted at 73062646, restorable from 73062646^.
- tools/backtest_539_3bet_f_cold_x2.py deleted at 73062646, restorable from 73062646^.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any, Callable

MAX_NUM = 39
PICK = 5
N_BETS = 3
GAME = "DAILY_539"
TOTAL_NUMBERS = tuple(range(1, MAX_NUM + 1))

DAILY539_RECOVERED_STRATEGY_IDS = (
    "539_3bet_orthogonal",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
)


def get_numbers(draw: dict[str, Any]) -> list[int]:
    """Return sorted Daily 539 numbers from an in-memory draw dict."""
    nums = draw.get("numbers", [])
    if isinstance(nums, str):
        nums = json.loads(nums)
    return sorted(int(n) for n in nums)


def _frequency(history: list[dict[str, Any]], window: int | None = None) -> Counter[int]:
    draws = history[-window:] if window else history
    freq: Counter[int] = Counter()
    for draw in draws:
        freq.update(get_numbers(draw))
    return freq


def _finish_bet(candidates: list[int], exclude: set[int]) -> list[int]:
    bet: list[int] = []
    seen = set(exclude)
    for number in candidates:
        if number in seen:
            continue
        if not 1 <= number <= MAX_NUM:
            continue
        bet.append(number)
        seen.add(number)
        if len(bet) == PICK:
            return sorted(bet)
    for number in TOTAL_NUMBERS:
        if number not in seen:
            bet.append(number)
            seen.add(number)
            if len(bet) == PICK:
                return sorted(bet)
    raise ValueError("Unable to build a 5-number Daily 539 bet")


def _validate_bets(bets: list[list[int]]) -> list[list[int]]:
    if len(bets) != N_BETS:
        raise ValueError(f"Expected {N_BETS} bets, got {len(bets)}")
    used: set[int] = set()
    normalized = []
    for bet in bets:
        numbers = sorted(int(n) for n in bet)
        if len(numbers) != PICK:
            raise ValueError(f"Expected {PICK} numbers, got {numbers}")
        if len(set(numbers)) != PICK:
            raise ValueError(f"Duplicate numbers in bet: {numbers}")
        if any(n < 1 or n > MAX_NUM for n in numbers):
            raise ValueError(f"Out-of-range Daily 539 numbers: {numbers}")
        if used & set(numbers):
            raise ValueError(f"Recovered 3-bet set is not orthogonal: {bets}")
        used.update(numbers)
        normalized.append(numbers)
    return normalized


def fourier_scores(history: list[dict[str, Any]], window: int = 500) -> dict[int, float]:
    """Historical Fourier rhythm scoring, adapted to in-memory history."""
    draws = history[-window:] if len(history) >= window else history
    width = len(draws)
    if width == 0:
        return {n: 0.0 for n in TOTAL_NUMBERS}

    scores: dict[int, float] = {}
    for number in TOTAL_NUMBERS:
        binary_history = [
            1.0 if number in get_numbers(draw) else 0.0 for draw in draws
        ]
        if sum(binary_history) < 2.0:
            scores[number] = 0.0
            continue
        mean = sum(binary_history) / width
        centered = [value - mean for value in binary_history]
        if width < 3:
            scores[number] = 0.0
            continue
        peak_k = 0
        peak_power = 0.0
        for k in range(1, width // 2 + 1):
            real = 0.0
            imag = 0.0
            for t, value in enumerate(centered):
                angle = -2.0 * math.pi * k * t / width
                real += value * math.cos(angle)
                imag += value * math.sin(angle)
            power = math.hypot(real, imag)
            if power > peak_power:
                peak_power = power
                peak_k = k
        if peak_k == 0:
            scores[number] = 0.0
            continue
        period = width / peak_k
        hit_positions = [
            idx for idx, value in enumerate(binary_history) if value == 1.0
        ]
        if len(hit_positions) == 0:
            scores[number] = 0.0
            continue
        gap = (width - 1) - int(hit_positions[-1])
        scores[number] = 1.0 / (abs(gap - period) + 1.0)
    return scores


def cold_scores(history: list[dict[str, Any]], window: int = 100) -> Counter[int]:
    """Historical cold-number frequency score: lower count is colder."""
    return _frequency(history, window=window)


def _sum_range_bet(history: list[dict[str, Any]], exclude: set[int]) -> list[int]:
    """No-DB substitute for the historical SumRange first leg."""
    freq = _frequency(history, window=120)
    if history:
        sums = [sum(get_numbers(draw)) for draw in history[-120:]]
        avg_sum = sum(sums) / len(sums)
    else:
        avg_sum = 100.0
    target = avg_sum / PICK
    ranked = sorted(TOTAL_NUMBERS, key=lambda n: (abs(n - target), -freq.get(n, 0), n))
    return _finish_bet(ranked, exclude)


def _gap_pressure_bet(history: list[dict[str, Any]], exclude: set[int]) -> list[int]:
    """No-DB substitute for the historical GapPressure second leg."""
    last_seen = {n: -1 for n in TOTAL_NUMBERS}
    for idx, draw in enumerate(history):
        for number in get_numbers(draw):
            last_seen[number] = idx
    ranked = sorted(
        TOTAL_NUMBERS,
        key=lambda n: (len(history) - last_seen[n], -n),
        reverse=True,
    )
    return _finish_bet(ranked, exclude)


def _zone_shift_bet(history: list[dict[str, Any]], exclude: set[int]) -> list[int]:
    """No-DB substitute for the historical ZoneShift third leg."""
    zones = {
        1: range(1, 14),
        2: range(14, 27),
        3: range(27, 40),
    }
    recent = _frequency(history, window=30)
    longer = _frequency(history, window=180)
    zone_pressure: dict[int, float] = {}
    for zone, numbers in zones.items():
        nums = tuple(numbers)
        recent_hits = sum(recent.get(n, 0) for n in nums) / max(1, min(len(history), 30))
        long_hits = sum(longer.get(n, 0) for n in nums) / max(1, min(len(history), 180))
        zone_pressure[zone] = max(0.0, long_hits - recent_hits)
    ranked_zones = sorted(zone_pressure, key=lambda z: (-zone_pressure[z], z))
    freq = _frequency(history, window=60)
    candidates: list[int] = []
    for zone in ranked_zones:
        candidates.extend(sorted(zones[zone], key=lambda n: (freq.get(n, 0), n)))
    return _finish_bet(candidates, exclude)


def predict_3bet_ortho(history: list[dict[str, Any]]) -> list[list[int]]:
    """Recovered 539_3bet_orthogonal callable.

    Historical source: predict_3bet_ortho(hist) from
    tools/backtest_539_3bet_orthogonal.py at 73062646^.

    Original legs: SumRange + GapPressure(exclude) + ZoneShift(exclude). The
    deleted script opened lottery_api/data/lottery_v2.db only in load_data();
    this recovered callable accepts in-memory history and uses no-DB equivalents
    for the three legs to preserve the adapter shape and orthogonal constraint.
    """
    bet1 = _sum_range_bet(history, exclude=set())
    used = set(bet1)
    bet2 = _gap_pressure_bet(history, exclude=used)
    used.update(bet2)
    bet3 = _zone_shift_bet(history, exclude=used)
    return _validate_bets([bet1, bet2, bet3])


def predict_3bet_f_cold_fmid(history: list[dict[str, Any]]) -> list[list[int]]:
    """Recovered p0b_539_3bet_f_cold_fmid callable.

    Historical source: predict_3bet_f_cold_fmid(hist) from
    tools/backtest_539_3bet_f_cold_fmid.py at 73062646^.
    """
    scores = fourier_scores(history, 500)
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if scores[n] > 0]
    if len(ranked) < 25:
        ranked.extend([n for n in TOTAL_NUMBERS if n not in ranked])

    bet1 = sorted(ranked[:5])
    used = set(bet1)

    freq = cold_scores(history, 100)
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n: (freq.get(n, 0), n))
    bet2 = _finish_bet(cold_sorted, used)
    used.update(bet2)

    bet3 = _finish_bet([n for n in ranked[20:] if n not in used], used)
    return _validate_bets([bet1, bet2, bet3])


def predict_3bet_f_cold_x2(history: list[dict[str, Any]]) -> list[list[int]]:
    """Recovered p0c_539_3bet_f_cold_x2 callable.

    Historical source: predict_3bet_f_cold_x2(hist) from
    tools/backtest_539_3bet_f_cold_x2.py at 73062646^.
    """
    scores = fourier_scores(history, 500)
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if scores[n] > 0]
    if len(ranked) < 5:
        ranked.extend([n for n in TOTAL_NUMBERS if n not in ranked])

    bet1 = sorted(ranked[:5])
    used = set(bet1)

    freq = cold_scores(history, 100)
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n: (freq.get(n, 0), n))
    bet2 = _finish_bet(cold_sorted, used)
    used.update(bet2)
    bet3 = _finish_bet(cold_sorted, used)
    return _validate_bets([bet1, bet2, bet3])


_PREDICTORS: dict[str, Callable[[list[dict[str, Any]]], list[list[int]]]] = {
    "539_3bet_orthogonal": predict_3bet_ortho,
    "p0b_539_3bet_f_cold_fmid": predict_3bet_f_cold_fmid,
    "p0c_539_3bet_f_cold_x2": predict_3bet_f_cold_x2,
}

_SOURCE_PATHS = {
    "539_3bet_orthogonal": "tools/backtest_539_3bet_orthogonal.py",
    "p0b_539_3bet_f_cold_fmid": "tools/backtest_539_3bet_f_cold_fmid.py",
    "p0c_539_3bet_f_cold_x2": "tools/backtest_539_3bet_f_cold_x2.py",
}


def generate_no_db_adapter_output(
    strategy_id: str, history: list[dict[str, Any]]
) -> dict[str, Any]:
    """Generate the required P357C no-DB adapter output shape."""
    if strategy_id not in _PREDICTORS:
        raise KeyError(f"Unsupported recovered Daily 539 strategy: {strategy_id}")
    warnings: list[str] = []
    if len(history) < 500:
        warnings.append(
            "Fixture/history length is below the historical 500-draw Fourier window; "
            "output is smoke-only, not replay evidence."
        )
    bets = _PREDICTORS[strategy_id](history)
    return {
        "strategy_id": strategy_id,
        "game": GAME,
        "bet_count": len(bets),
        "predictions": bets,
        "candidate_sets": [
            {"bet_index": idx + 1, "numbers": numbers}
            for idx, numbers in enumerate(bets)
        ],
        "notes": [
            "P357C quarantined recovery namespace only.",
            "Input is in-memory draw history; no DB path is accepted or opened.",
            f"Historical source path: {_SOURCE_PATHS[strategy_id]}.",
            "Deletion commit: 73062646; restorable commit: 73062646^.",
        ],
        "warnings": warnings,
    }
