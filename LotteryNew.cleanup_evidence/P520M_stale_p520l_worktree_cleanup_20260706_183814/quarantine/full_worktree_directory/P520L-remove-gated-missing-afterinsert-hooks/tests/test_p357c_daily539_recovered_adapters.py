from __future__ import annotations

import hashlib
import sqlite3

import pytest

from recovered_strategies.daily539 import (
    DAILY539_RECOVERED_STRATEGY_IDS,
    generate_no_db_adapter_output,
)


def _synthetic_daily539_history(draw_count: int = 520) -> list[dict[str, object]]:
    history: list[dict[str, object]] = []
    for draw_index in range(draw_count):
        numbers: list[int] = []
        counter = 0
        while len(numbers) < 5:
            block = hashlib.sha256(
                f"P357C-DAILY539:{draw_index}:{counter}".encode("ascii")
            ).digest()
            for byte in block:
                number = byte % 39 + 1
                if number not in numbers:
                    numbers.append(number)
                if len(numbers) == 5:
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


def test_p357c_daily539_strategy_ids_are_exact_slice() -> None:
    assert DAILY539_RECOVERED_STRATEGY_IDS == (
        "539_3bet_orthogonal",
        "p0b_539_3bet_f_cold_fmid",
        "p0c_539_3bet_f_cold_x2",
    )


@pytest.mark.parametrize("strategy_id", DAILY539_RECOVERED_STRATEGY_IDS)
def test_p357c_daily539_recovered_adapter_output_shape(strategy_id: str) -> None:
    output = generate_no_db_adapter_output(
        strategy_id, _synthetic_daily539_history()
    )

    assert output["strategy_id"] == strategy_id
    assert output["game"] == "DAILY_539"
    assert output["bet_count"] == 3
    assert output["predictions"] == [
        item["numbers"] for item in output["candidate_sets"]
    ]
    assert [item["bet_index"] for item in output["candidate_sets"]] == [1, 2, 3]

    all_numbers: list[int] = []
    for bet in output["predictions"]:
        assert len(bet) == 5
        assert len(set(bet)) == 5
        assert all(1 <= number <= 39 for number in bet)
        all_numbers.extend(bet)
    assert len(set(all_numbers)) == 15


def test_p357c_daily539_adapters_do_not_open_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"sqlite3.connect must not be called: {args} {kwargs}")

    monkeypatch.setattr(sqlite3, "connect", fail_connect)
    history = _synthetic_daily539_history()

    for strategy_id in DAILY539_RECOVERED_STRATEGY_IDS:
        output = generate_no_db_adapter_output(strategy_id, history)
        assert output["bet_count"] == 3
