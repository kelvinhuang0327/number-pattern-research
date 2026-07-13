"""P541D_R2-selected BIG_LOTTO replay adapters.

This module is intentionally standalone and unregistered.  Its metadata is
implementation-scoped ``OBSERVATION`` metadata only; lifecycle publication and
replay generation remain outside this module's scope.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
from typing import List

from lottery_api.models.replay_strategy_registry import (
    ReplayStrategyAdapter,
    _StrategyMeta,
    _validate_numbers,
    InsufficientHistory,
    InvalidOutput,
    RejectPrediction,
    UnsupportedLotteryType,
)


__all__ = [
    "BigLottoSocialWisdomAntiPopularityAdapter",
    "BigLottoZoneSplit3BetBet1Adapter",
]


_BIG_LOTTO = "BIG_LOTTO"
_SOCIAL_STRATEGY_ID = "biglotto_social_wisdom_anti_popularity"
_ZONE_STRATEGY_ID = "biglotto_zone_split_3bet_bet1"
_ZONE_MIN_NUM = 1
_ZONE_MAX_NUM = 49
_ZONE_PICK_COUNT = 6
_ZONE_NUM_BETS = 3
_ZONE_OVERLAP_SIZE = 2


def _validated_biglotto_numbers(numbers: object, strategy_id: str) -> List[int]:
    """Apply the canonical validator and map malformed containers to InvalidOutput."""
    if not isinstance(numbers, list):
        raise InvalidOutput(f"{strategy_id}: expected a number list")
    try:
        return _validate_numbers(numbers, _BIG_LOTTO, strategy_id)
    except InvalidOutput:
        raise
    except (TypeError, ValueError, OverflowError) as exc:
        raise InvalidOutput(f"{strategy_id}: malformed number list") from exc


def _zone_split_pools() -> List[List[int]]:
    """Return fresh copies of the three pinned legacy candidate pools."""
    full_range = _ZONE_MAX_NUM - _ZONE_MIN_NUM + 1
    zone_size = full_range // _ZONE_NUM_BETS
    pools: List[List[int]] = []

    for index in range(_ZONE_NUM_BETS):
        start = _ZONE_MIN_NUM + index * zone_size
        end = _ZONE_MIN_NUM + (index + 1) * zone_size - 1
        if index == _ZONE_NUM_BETS - 1:
            end = _ZONE_MAX_NUM
        pool = list(
            range(
                max(_ZONE_MIN_NUM, start - _ZONE_OVERLAP_SIZE),
                min(_ZONE_MAX_NUM, end + _ZONE_OVERLAP_SIZE) + 1,
            )
        )
        if len(pool) < _ZONE_PICK_COUNT:
            pool = list(range(_ZONE_MIN_NUM, _ZONE_MAX_NUM + 1))
        pools.append(pool)

    return pools


def _canonical_zone_history(history: List[dict]) -> List[dict]:
    """Copy and canonicalize causal rows without changing their order."""
    canonical_history: List[dict] = []
    for index, row in enumerate(history):
        if not isinstance(row, dict):
            raise InvalidOutput(f"{_ZONE_STRATEGY_ID}: history row {index} is not an object")
        missing = [field for field in ("draw", "date", "numbers") if field not in row]
        if missing:
            raise InvalidOutput(
                f"{_ZONE_STRATEGY_ID}: history row {index} missing {','.join(missing)}"
            )

        numbers = _validated_biglotto_numbers(row["numbers"], _ZONE_STRATEGY_ID)
        try:
            draw = str(row["draw"])
            date = str(row["date"])
        except (TypeError, ValueError) as exc:
            raise InvalidOutput(
                f"{_ZONE_STRATEGY_ID}: history row {index} has unstable draw/date"
            ) from exc
        canonical_history.append({"draw": draw, "date": date, "numbers": numbers})

    return canonical_history


def _zone_seed_preimage(history: List[dict]) -> bytes:
    """Build the exact UTF-8 canonical JSON seed preimage."""
    payload = {
        "strategy_id": _ZONE_STRATEGY_ID,
        "lottery_type": _BIG_LOTTO,
        "causal_history": _canonical_zone_history(history),
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
        raise InvalidOutput(f"{_ZONE_STRATEGY_ID}: history is not JSON-safe") from exc
    return canonical_json.encode("utf-8")


def _zone_seed_digest(history: List[dict]) -> str:
    """Return the hexadecimal SHA-256 digest of the canonical seed preimage."""
    return hashlib.sha256(_zone_seed_preimage(history)).hexdigest()


def _zone_split_bets(history: List[dict]) -> List[List[int]]:
    """Generate the three pinned zone bets with one history-derived local RNG."""
    digest = hashlib.sha256(_zone_seed_preimage(history)).digest()
    local_rng = random.Random(int.from_bytes(digest, byteorder="big", signed=False))
    return [
        sorted(local_rng.sample(pool, _ZONE_PICK_COUNT))
        for pool in _zone_split_pools()
    ]


class BigLottoSocialWisdomAntiPopularityAdapter(ReplayStrategyAdapter):
    """Direct replay wrapper for the deterministic Social Wisdom callable."""

    meta = _StrategyMeta(
        strategy_id=_SOCIAL_STRATEGY_ID,
        strategy_name="大樂透 Social Wisdom Anti-Popularity",
        strategy_version="v0.1",
        supported_lottery_types=[_BIG_LOTTO],
        min_history=1,
        status="OBSERVATION",
    )

    def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
        from lottery_api.models.social_wisdom_predictor import SocialWisdomPredictor

        newest_first_history = copy.deepcopy(list(history[-50:]))
        newest_first_history.reverse()
        predicted = SocialWisdomPredictor(max_num=49).predict(
            newest_first_history,
            pick_count=6,
        )
        return _validated_biglotto_numbers(predicted, self.meta.strategy_id)


class BigLottoZoneSplit3BetBet1Adapter(ReplayStrategyAdapter):
    """Deterministic replay implementation of Zone Split 3-bet bet 1."""

    meta = _StrategyMeta(
        strategy_id=_ZONE_STRATEGY_ID,
        strategy_name="大樂透 Zone Split 3注（Replay Bet 1）",
        strategy_version="v0.1",
        supported_lottery_types=[_BIG_LOTTO],
        min_history=1,
        status="OBSERVATION",
    )

    def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
        return _zone_split_bets(history)[0]
