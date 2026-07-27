"""Target-native BIG_LOTTO Zone Split replay adapters.

The public Bet1 identity is also the immutable seed identity.  Every adapter
replays the same three-ticket sequence with one history-derived local RNG and
then returns its assigned ticket.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any, List, NoReturn, Type, cast


BIG_LOTTO = "BIG_LOTTO"
BET1_STRATEGY_ID = "biglotto_zone_split_3bet_bet1"
BET2_STRATEGY_ID = "biglotto_zone_split_3bet_bet2"
BET3_STRATEGY_ID = "biglotto_zone_split_3bet_bet3"
STRATEGY_IDS = (BET1_STRATEGY_ID, BET2_STRATEGY_ID, BET3_STRATEGY_ID)

_MIN_NUM = 1
_MAX_NUM = 49
_PICK_COUNT = 6
_NUM_BETS = 3
_OVERLAP_SIZE = 2


def _raise(error_type: Type[Exception], message: str) -> NoReturn:
    raise error_type(message)


def _require_exact_history_list(
    history: object,
    strategy_id: str,
    error_type: Type[Exception] = ValueError,
) -> List[dict]:
    if type(history) is not list:
        _raise(error_type, f"{strategy_id}: expected a history list")
    return cast(List[dict], history)


def _validated_biglotto_numbers(
    numbers: object,
    strategy_id: str,
    error_type: Type[Exception] = ValueError,
) -> List[int]:
    if type(numbers) is not list:
        _raise(error_type, f"{strategy_id}: expected a number list")
    number_list = cast(List[object], numbers)
    if len(number_list) != _PICK_COUNT:
        _raise(
            error_type,
            f"{strategy_id}: expected {_PICK_COUNT} numbers, got {len(number_list)}",
        )
    if not all(type(number) is int for number in number_list):
        _raise(error_type, f"{strategy_id}: numbers must be exact built-in integers")

    validated = sorted(cast(List[int], number_list))
    if not all(_MIN_NUM <= number <= _MAX_NUM for number in validated):
        _raise(error_type, f"{strategy_id}: numbers out of range [1..49]")
    if len(set(validated)) != _PICK_COUNT:
        _raise(error_type, f"{strategy_id}: duplicate numbers")
    return validated


def _validated_history_row(
    row: object,
    index: int,
    error_type: Type[Exception] = ValueError,
) -> dict:
    if type(row) is not dict:
        _raise(error_type, f"{BET1_STRATEGY_ID}: history row {index} is not an object")
    row_dict = cast(dict, row)

    missing = [
        field for field in ("draw", "date", "numbers") if field not in row_dict
    ]
    if missing:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {index} missing {','.join(missing)}",
        )

    draw = row_dict["draw"]
    date = row_dict["date"]
    if type(draw) is not str or not draw:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {index} draw must be a non-empty string",
        )
    if type(date) is not str or not date:
        _raise(
            error_type,
            f"{BET1_STRATEGY_ID}: history row {index} date must be a non-empty string",
        )

    numbers = _validated_biglotto_numbers(
        row_dict["numbers"],
        BET1_STRATEGY_ID,
        error_type,
    )
    return {"draw": draw, "date": date, "numbers": numbers}


def _zone_split_pools() -> List[List[int]]:
    full_range = _MAX_NUM - _MIN_NUM + 1
    zone_size = full_range // _NUM_BETS
    pools: List[List[int]] = []

    for index in range(_NUM_BETS):
        start = _MIN_NUM + index * zone_size
        end = _MIN_NUM + (index + 1) * zone_size - 1
        if index == _NUM_BETS - 1:
            end = _MAX_NUM
        pool = list(
            range(
                max(_MIN_NUM, start - _OVERLAP_SIZE),
                min(_MAX_NUM, end + _OVERLAP_SIZE) + 1,
            )
        )
        if len(pool) < _PICK_COUNT:
            pool = list(range(_MIN_NUM, _MAX_NUM + 1))
        pools.append(pool)

    return pools


def _canonical_zone_history(
    history: object,
    error_type: Type[Exception] = ValueError,
) -> List[dict]:
    rows = _require_exact_history_list(history, BET1_STRATEGY_ID, error_type)
    return [
        _validated_history_row(row, index, error_type)
        for index, row in enumerate(rows)
    ]


def _zone_seed_preimage(
    history: List[dict],
    error_type: Type[Exception] = ValueError,
) -> bytes:
    payload = {
        "strategy_id": BET1_STRATEGY_ID,
        "lottery_type": BIG_LOTTO,
        "causal_history": _canonical_zone_history(history, error_type),
    }
    try:
        canonical_json = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise error_type(f"{BET1_STRATEGY_ID}: history is not JSON-safe") from exc
    return canonical_json.encode("utf-8")


def _zone_seed_digest(
    history: List[dict],
    error_type: Type[Exception] = ValueError,
) -> str:
    return hashlib.sha256(_zone_seed_preimage(history, error_type)).hexdigest()


def _zone_split_bets(
    history: List[dict],
    error_type: Type[Exception] = ValueError,
) -> List[List[int]]:
    """Generate Bet1, Bet2, and Bet3 sequentially with one local RNG."""
    digest = hashlib.sha256(_zone_seed_preimage(history, error_type)).digest()
    local_rng = random.Random(int.from_bytes(digest, byteorder="big", signed=False))
    return [
        sorted(local_rng.sample(pool, _PICK_COUNT))
        for pool in _zone_split_pools()
    ]


def build_zone_split_adapters(
    adapter_base: type,
    meta_type: type,
    invalid_output: Type[Exception],
    unsupported_lottery_type: Type[Exception],
) -> List[Any]:
    """Build the three executable adapters against the registry's base contract."""

    class _ZoneSplitAdapter(adapter_base):  # type: ignore[misc, valid-type]
        bet_index = 0

        def get_one_bet(self, history: object, lottery_type: str):
            if lottery_type not in self.meta.supported_lottery_types:
                raise unsupported_lottery_type(
                    f"{self.meta.strategy_id} does not support {lottery_type}"
                )
            _require_exact_history_list(history, self.meta.strategy_id, invalid_output)
            return super().get_one_bet(history, lottery_type)

        def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
            return _zone_split_bets(history, invalid_output)[self.bet_index]

    class BigLottoZoneSplit3BetBet1Adapter(_ZoneSplitAdapter):
        bet_index = 0
        meta = meta_type(
            strategy_id=BET1_STRATEGY_ID,
            strategy_name="大樂透 Zone Split 3注（Replay Bet 1）",
            strategy_version="v0.1",
            supported_lottery_types=[BIG_LOTTO],
            min_history=1,
            status="ONLINE",
        )

    class BigLottoZoneSplit3BetBet2Adapter(_ZoneSplitAdapter):
        bet_index = 1
        meta = meta_type(
            strategy_id=BET2_STRATEGY_ID,
            strategy_name="大樂透 Zone Split 3注（Replay Bet 2）",
            strategy_version="v0.1",
            supported_lottery_types=[BIG_LOTTO],
            min_history=1,
            status="ONLINE",
        )

    class BigLottoZoneSplit3BetBet3Adapter(_ZoneSplitAdapter):
        bet_index = 2
        meta = meta_type(
            strategy_id=BET3_STRATEGY_ID,
            strategy_name="大樂透 Zone Split 3注（Replay Bet 3）",
            strategy_version="v0.1",
            supported_lottery_types=[BIG_LOTTO],
            min_history=1,
            status="ONLINE",
        )

    return [
        BigLottoZoneSplit3BetBet1Adapter(),
        BigLottoZoneSplit3BetBet2Adapter(),
        BigLottoZoneSplit3BetBet3Adapter(),
    ]
