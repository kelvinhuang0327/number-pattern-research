"""Target-native BIG_LOTTO P0 2Bet replay adapters.

Both public adapters replay the same deterministic two-ticket sequence and
return only their assigned ticket.  The family identity remains lineage-only.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, List, NoReturn, Type, cast


BIG_LOTTO = "BIG_LOTTO"
BET1_STRATEGY_ID = "biglotto_p0_2bet_bet1"
BET2_STRATEGY_ID = "biglotto_p0_2bet_bet2"
STRATEGY_IDS = (BET1_STRATEGY_ID, BET2_STRATEGY_ID)

_MIN_NUM = 1
_MAX_NUM = 49
_PICK_COUNT = 6
_HISTORY_WINDOW = 50
_ECHO_BOOST = 1.5


def _raise(error_type: Type[Exception], message: str) -> NoReturn:
    raise error_type(message)


def _require_exact_history_list(
    history: object,
    error_type: Type[Exception],
) -> List[dict]:
    if type(history) is not list:
        _raise(error_type, f"{BET1_STRATEGY_ID}: expected a history list")
    return cast(List[dict], history)


def _validated_biglotto_numbers(
    numbers: object,
    row_index: int,
    error_type: Type[Exception],
) -> List[int]:
    if type(numbers) is not list:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {row_index} numbers must be a list",
        )
    number_list = cast(List[object], numbers)
    if len(number_list) != _PICK_COUNT:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {row_index} must have "
            f"{_PICK_COUNT} numbers",
        )
    if not all(type(number) is int for number in number_list):
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {row_index} numbers must be "
            "exact built-in integers",
        )

    validated = sorted(cast(List[int], number_list))
    if not all(_MIN_NUM <= number <= _MAX_NUM for number in validated):
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {row_index} numbers out of "
            "range [1..49]",
        )
    if len(set(validated)) != _PICK_COUNT:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {row_index} has duplicate numbers",
        )
    return validated


def _validated_history_row(
    row: object,
    index: int,
    error_type: Type[Exception],
) -> dict:
    if type(row) is not dict:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {index} is not an object",
        )
    row_dict = cast(dict, row)

    missing = [
        field for field in ("draw", "date", "numbers") if field not in row_dict
    ]
    if missing:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {index} missing "
            f"{','.join(missing)}",
        )

    draw = row_dict["draw"]
    date = row_dict["date"]
    if type(draw) is not str or not draw:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {index} draw must be a "
            "non-empty string",
        )
    if type(date) is not str or not date:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {index} date must be a "
            "non-empty string",
        )

    return {
        "draw": draw,
        "date": date,
        "numbers": _validated_biglotto_numbers(
            row_dict["numbers"],
            index,
            error_type,
        ),
    }


def _p0_2bet_bets(
    history: object,
    error_type: Type[Exception] = ValueError,
) -> List[List[int]]:
    """Return canonical Bet1 followed by Bet2 for valid old-to-new history."""
    history_rows = _require_exact_history_list(history, error_type)
    canonical_history = [
        _validated_history_row(row, index, error_type)
        for index, row in enumerate(history_rows)
    ]
    if not canonical_history:
        _raise(error_type, f"{BET1_STRATEGY_ID}: needs at least one draw")

    recent = canonical_history[-_HISTORY_WINDOW:]
    expected = len(recent) * _PICK_COUNT / _MAX_NUM
    frequency = Counter(
        number
        for row in recent
        for number in row["numbers"]
    )
    scores = {
        number: frequency.get(number, 0) - expected
        for number in range(_MIN_NUM, _MAX_NUM + 1)
    }

    if len(canonical_history) >= 3:
        for number in canonical_history[-2]["numbers"]:
            scores[number] += _ECHO_BOOST

    hot_numbers = sorted(
        (number for number, score in scores.items() if score > 1),
        key=lambda number: (-scores[number], number),
    )
    bet1 = hot_numbers[:_PICK_COUNT]
    bet1_used = set(bet1)
    if len(bet1) < _PICK_COUNT:
        fallback = sorted(
            range(_MIN_NUM, _MAX_NUM + 1),
            key=lambda number: (abs(scores[number]), number),
        )
        for number in fallback:
            if number not in bet1_used:
                bet1.append(number)
                bet1_used.add(number)
                if len(bet1) == _PICK_COUNT:
                    break

    cold_numbers = sorted(
        (number for number, score in scores.items() if score < -1),
        key=lambda number: (-abs(scores[number]), number),
    )
    bet2: List[int] = []
    for number in cold_numbers:
        if number not in bet1_used:
            bet2.append(number)
            if len(bet2) == _PICK_COUNT:
                break

    if len(bet2) < _PICK_COUNT:
        bet2_used = set(bet2)
        for number in range(_MIN_NUM, _MAX_NUM + 1):
            if number not in bet1_used and number not in bet2_used:
                bet2.append(number)
                bet2_used.add(number)
                if len(bet2) == _PICK_COUNT:
                    break

    return [sorted(bet1), sorted(bet2)]


def build_p0_2bet_adapters(
    adapter_base: type,
    meta_type: type,
    invalid_output: Type[Exception],
    unsupported_lottery_type: Type[Exception],
) -> List[Any]:
    """Build the two executable adapters against the registry's contracts."""

    class _P0TwoBetAdapter(adapter_base):  # type: ignore[misc, valid-type]
        bet_index = 0

        def get_one_bet(self, history: object, lottery_type: str):
            if lottery_type not in self.meta.supported_lottery_types:
                raise unsupported_lottery_type(
                    f"{self.meta.strategy_id} does not support {lottery_type}"
                )
            _require_exact_history_list(history, invalid_output)
            return super().get_one_bet(history, lottery_type)

        def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
            return _p0_2bet_bets(history, invalid_output)[self.bet_index]

    class BigLottoP0TwoBetBet1Adapter(_P0TwoBetAdapter):
        bet_index = 0
        meta = meta_type(
            strategy_id=BET1_STRATEGY_ID,
            strategy_name="大樂透 P0 偏差互補＋回聲 2注（Replay Bet 1）",
            strategy_version="v0.1",
            supported_lottery_types=[BIG_LOTTO],
            min_history=1,
            status="ONLINE",
        )

    class BigLottoP0TwoBetBet2Adapter(_P0TwoBetAdapter):
        bet_index = 1
        meta = meta_type(
            strategy_id=BET2_STRATEGY_ID,
            strategy_name="大樂透 P0 偏差互補＋回聲 2注（Replay Bet 2）",
            strategy_version="v0.1",
            supported_lottery_types=[BIG_LOTTO],
            min_history=1,
            status="ONLINE",
        )

    return [
        BigLottoP0TwoBetBet1Adapter(),
        BigLottoP0TwoBetBet2Adapter(),
    ]
