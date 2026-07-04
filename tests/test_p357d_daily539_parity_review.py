from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any, Callable

import pytest

from recovered_strategies.daily539 import (
    generate_no_db_adapter_output,
    predict_3bet_f_cold_fmid,
    predict_3bet_f_cold_x2,
    predict_3bet_ortho,
)

MAX_NUM = 39
PICK = 5
TOTAL_NUMBERS = tuple(range(1, MAX_NUM + 1))


def _synthetic_daily539_history(draw_count: int = 520) -> list[dict[str, object]]:
    history: list[dict[str, object]] = []
    for draw_index in range(draw_count):
        numbers: list[int] = []
        counter = 0
        while len(numbers) < PICK:
            block = hashlib.sha256(
                f"P357D-DAILY539:{draw_index}:{counter}".encode("ascii")
            ).digest()
            for byte in block:
                number = byte % MAX_NUM + 1
                if number not in numbers:
                    numbers.append(number)
                if len(numbers) == PICK:
                    break
            counter += 1
        history.append(
            {
                "draw": f"SYN539-{draw_index:04d}",
                "date": f"SYNTHETIC-{draw_index:04d}",
                "numbers": sorted(numbers),
            }
        )
    return history


def _get_numbers(draw: dict[str, Any]) -> list[int]:
    nums = draw.get("numbers", [])
    if isinstance(nums, str):
        nums = json.loads(nums)
    return list(nums)


def _historical_fourier_scores(
    history: list[dict[str, Any]], window: int = 500
) -> dict[int, float]:
    draws = history[-window:] if len(history) >= window else history
    width = len(draws)
    scores: dict[int, float] = {}
    for number in TOTAL_NUMBERS:
        binary_history = [
            1.0 if number in _get_numbers(draw) else 0.0 for draw in draws
        ]
        if sum(binary_history) < 2.0:
            scores[number] = 0.0
            continue
        mean = sum(binary_history) / width
        centered = [value - mean for value in binary_history]
        peak_k = 0
        peak_power = 0.0
        # Historical scipy.fft.fftfreq(width, 1) > 0 excludes the even-window
        # Nyquist bin, so the positive k range ends at (width - 1) // 2.
        for k in range(1, (width - 1) // 2 + 1):
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


def _historical_cold_scores(
    history: list[dict[str, Any]], window: int = 100
) -> Counter[int]:
    freq: Counter[int] = Counter()
    for draw in history[-window:]:
        freq.update(_get_numbers(draw))
    return freq


def _historical_predict_3bet_f_cold_fmid(
    history: list[dict[str, Any]],
) -> list[list[int]]:
    scores = _historical_fourier_scores(history, 500)
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if scores[n] > 0]
    if len(ranked) < 25:
        ranked.extend([n for n in TOTAL_NUMBERS if n not in ranked])

    bet1 = sorted(ranked[:5])
    exclude = set(bet1)

    freq = _historical_cold_scores(history, 100)
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n: freq.get(n, 0))
    bet2 = sorted([n for n in cold_sorted if n not in exclude][:5])
    exclude.update(bet2)

    bet3_pool = [n for n in ranked[20:] if n not in exclude]
    bet3 = sorted(bet3_pool[:5])
    if len(bet3) < 5:
        remaining = [
            n for n in TOTAL_NUMBERS if n not in exclude and n not in bet3
        ]
        bet3 = sorted((bet3 + remaining)[:5])

    return [bet1, bet2, bet3]


def _historical_predict_3bet_f_cold_x2(
    history: list[dict[str, Any]],
) -> list[list[int]]:
    scores = _historical_fourier_scores(history, 500)
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if scores[n] > 0]
    if len(ranked) < 5:
        ranked.extend([n for n in TOTAL_NUMBERS if n not in ranked])

    bet1 = sorted(ranked[:5])
    exclude = set(bet1)

    freq = _historical_cold_scores(history, 100)
    cold_sorted = sorted(TOTAL_NUMBERS, key=lambda n: freq.get(n, 0))
    bet2 = sorted([n for n in cold_sorted if n not in exclude][:5])
    exclude.update(bet2)

    bet3 = sorted([n for n in cold_sorted if n not in exclude][:5])
    if len(bet3) < 5:
        remaining = [
            n for n in TOTAL_NUMBERS if n not in exclude and n not in bet3
        ]
        bet3 = sorted((bet3 + remaining)[:5])

    return [bet1, bet2, bet3]


@pytest.mark.parametrize(
    ("adapter", "historical"),
    [
        (predict_3bet_f_cold_fmid, _historical_predict_3bet_f_cold_fmid),
        (predict_3bet_f_cold_x2, _historical_predict_3bet_f_cold_x2),
    ],
)
def test_p357d_self_contained_fourier_cold_adapters_match_historical_logic(
    adapter: Callable[[list[dict[str, Any]]], list[list[int]]],
    historical: Callable[[list[dict[str, Any]]], list[list[int]]],
) -> None:
    history = _synthetic_daily539_history(520)

    assert adapter(history) == historical(history)


def test_p357d_orthogonal_adapter_preserves_no_db_contract() -> None:
    history = _synthetic_daily539_history(520)

    first = predict_3bet_ortho(history)
    second = predict_3bet_ortho(history)

    assert first == second
    assert len(first) == 3
    all_numbers: list[int] = []
    for bet in first:
        assert len(bet) == 5
        assert len(set(bet)) == 5
        assert all(1 <= number <= 39 for number in bet)
        all_numbers.extend(bet)
    assert len(set(all_numbers)) == 15


def test_p357d_adapter_output_shape_remains_replay_harness_ready() -> None:
    history = _synthetic_daily539_history(520)

    for strategy_id in (
        "539_3bet_orthogonal",
        "p0b_539_3bet_f_cold_fmid",
        "p0c_539_3bet_f_cold_x2",
    ):
        output = generate_no_db_adapter_output(strategy_id, history)

        assert output["strategy_id"] == strategy_id
        assert output["game"] == "DAILY_539"
        assert output["bet_count"] == 3
        assert output["warnings"] == []
        assert output["predictions"] == [
            candidate["numbers"] for candidate in output["candidate_sets"]
        ]
