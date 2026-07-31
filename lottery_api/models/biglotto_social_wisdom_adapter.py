"""Target-native BIG_LOTTO Social Wisdom replay adapter."""
from __future__ import annotations

from typing import Any, List, NoReturn, Type, cast


BIG_LOTTO = "BIG_LOTTO"
STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_PICK_COUNT = 6
_MIN_NUM = 1
_MAX_NUM = 49
_HISTORY_WINDOW = 50


def _raise(error_type: Type[Exception], message: str) -> NoReturn:
    raise error_type(message)


def _require_exact_history_list(
    history: object,
    error_type: Type[Exception],
) -> List[dict]:
    if type(history) is not list:
        _raise(error_type, f"{STRATEGY_ID}: expected a history list")
    return cast(List[dict], history)


def _validated_biglotto_numbers(
    numbers: object,
    error_type: Type[Exception],
) -> List[int]:
    if type(numbers) is not list:
        _raise(error_type, f"{STRATEGY_ID}: expected a number list")
    number_list = cast(List[object], numbers)
    if len(number_list) != _PICK_COUNT:
        _raise(
            error_type,
            f"{STRATEGY_ID}: expected {_PICK_COUNT} numbers, got {len(number_list)}",
        )
    if not all(type(number) is int for number in number_list):
        _raise(error_type, f"{STRATEGY_ID}: numbers must be exact built-in integers")

    validated = sorted(cast(List[int], number_list))
    if not all(_MIN_NUM <= number <= _MAX_NUM for number in validated):
        _raise(error_type, f"{STRATEGY_ID}: numbers out of range [1..49]")
    if len(set(validated)) != _PICK_COUNT:
        _raise(error_type, f"{STRATEGY_ID}: duplicate numbers")
    return validated


def _validated_history_row(
    row: object,
    index: int,
    error_type: Type[Exception],
) -> dict:
    if type(row) is not dict:
        _raise(error_type, f"{STRATEGY_ID}: history row {index} is not an object")
    row_dict = cast(dict, row)

    missing = [
        field for field in ("draw", "date", "numbers") if field not in row_dict
    ]
    if missing:
        _raise(
            error_type,
            f"{STRATEGY_ID}: history row {index} missing {','.join(missing)}",
        )

    draw = row_dict["draw"]
    date = row_dict["date"]
    if type(draw) is not str or not draw:
        _raise(
            error_type,
            f"{STRATEGY_ID}: history row {index} draw must be a non-empty string",
        )
    if type(date) is not str or not date:
        _raise(
            error_type,
            f"{STRATEGY_ID}: history row {index} date must be a non-empty string",
        )

    return {
        "draw": draw,
        "date": date,
        "numbers": _validated_biglotto_numbers(row_dict["numbers"], error_type),
    }


def build_social_wisdom_adapter(
    adapter_base: type,
    meta_type: type,
    invalid_output: Type[Exception],
    unsupported_lottery_type: Type[Exception],
) -> Any:
    """Build the executable adapter against the registry's native contracts."""

    class BigLottoSocialWisdomAntiPopularityAdapter(adapter_base):  # type: ignore[misc, valid-type]
        meta = meta_type(
            strategy_id=STRATEGY_ID,
            strategy_name="大樂透 Social Wisdom Anti-Popularity",
            strategy_version="v0.1",
            supported_lottery_types=[BIG_LOTTO],
            min_history=1,
            status="ONLINE",
        )

        def get_one_bet(self, history: object, lottery_type: str):
            if lottery_type not in self.meta.supported_lottery_types:
                raise unsupported_lottery_type(
                    f"{self.meta.strategy_id} does not support {lottery_type}"
                )
            _require_exact_history_list(history, invalid_output)
            return super().get_one_bet(history, lottery_type)

        def _call_strategy(
            self,
            history: List[dict],
            lottery_type: str,
        ) -> List[int]:
            from lottery_api.models.social_wisdom_predictor import (
                SocialWisdomPredictor,
            )

            selected_history = _require_exact_history_list(
                history,
                invalid_output,
            )[-_HISTORY_WINDOW:]
            newest_first_history = [
                _validated_history_row(row, index, invalid_output)
                for index, row in enumerate(selected_history)
            ]
            newest_first_history.reverse()
            predicted = SocialWisdomPredictor(max_num=_MAX_NUM).predict(
                newest_first_history,
                pick_count=_PICK_COUNT,
            )
            return _validated_biglotto_numbers(predicted, invalid_output)

    return BigLottoSocialWisdomAntiPopularityAdapter()
