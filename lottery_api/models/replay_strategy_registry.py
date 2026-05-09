"""
replay_strategy_registry.py
============================
Strategy adapter registry for the Historical Replay Store.

IMPORTANT SCOPE:
  - This is EXCLUSIVELY for the historical replay audit system.
  - DO NOT use these adapters for live prediction or strategy promotion.
  - Each adapter wraps an existing tools/predict_*.py function with a
    one-bet causal interface: get_one_bet(history, lottery_type) -> (numbers, special)

HARD RULES:
  - history MUST be all draws STRICTLY BEFORE the target draw (causal slice).
  - Adapters MUST NOT read any external state (DB, files, env) during prediction.
  - Only one bet is recorded per (strategy, draw) pair.
  - DAILY_539 has no special number — always return None for special.
  - POWER_LOTTO bets must have exactly 6 main numbers.
  - BIG_LOTTO bets must have exactly 6 main numbers.
  - DAILY_539 bets must have exactly 5 main numbers.

LIFECYCLE_STATUS values (P0-A expanded enum):
  ONLINE      — deployed and active in replay generation (replaces ACTIVE)
  OFFLINE     — previously deployed, now suspended; old rows preserved in DB
  REJECTED    — evaluated and rejected during governance review
  OBSERVATION — under shadow evaluation / observation period
  RETIRED     — formally retired after lifecycle; old rows preserved in DB

Backward compatibility:
  ACTIVE is still accepted as an alias for ONLINE in code that uses the old enum.
  Canonical output always normalises ACTIVE → ONLINE.
"""
from __future__ import annotations

import sys
import json
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Callable

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ─── Lifecycle Status SSOT ────────────────────────────────────────────────────

# Canonical lifecycle status values (P0-A)
LIFECYCLE_STATUSES = ("ONLINE", "OFFLINE", "REJECTED", "OBSERVATION", "RETIRED")

# Legacy alias mapping — ACTIVE is normalised to ONLINE in all outputs
_LEGACY_STATUS_MAP: dict[str, str] = {
    "ACTIVE": "ONLINE",
}


def normalise_lifecycle_status(status: str) -> str:
    """Normalise legacy status aliases to canonical lifecycle values."""
    return _LEGACY_STATUS_MAP.get(status, status)


# Statuses that are included in replay generation (active-equivalent)
_GENERATION_STATUSES = frozenset({"ONLINE", "ACTIVE"})

# ─── Custom Exceptions ────────────────────────────────────────────────────────

class RejectPrediction(Exception):
    """
    Raise inside an adapter when the strategy deliberately passes on this draw.
    The caller will record replay_status=REJECTED with reject_reason=str(exc).
    """

class UnsupportedLotteryType(Exception):
    """
    Raised when an adapter is called with a lottery_type it does not support.
    """

class InvalidOutput(Exception):
    """
    Raised when an adapter returns structurally invalid numbers.
    """

class InsufficientHistory(Exception):
    """
    Raised when history is too short to run the strategy.
    """

# ─── Registry Entry ───────────────────────────────────────────────────────────

class _StrategyMeta:
    __slots__ = ("strategy_id", "strategy_name", "strategy_version",
                 "supported_lottery_types", "min_history", "status",
                 "lifecycle_status")

    def __init__(self, strategy_id: str, strategy_name: str,
                 strategy_version: str, supported_lottery_types: List[str],
                 min_history: int = 100, status: str = "ONLINE"):
        self.strategy_id            = strategy_id
        self.strategy_name          = strategy_name
        self.strategy_version       = strategy_version
        self.supported_lottery_types = supported_lottery_types
        self.min_history            = min_history
        # Normalise legacy ACTIVE → ONLINE
        self.status                 = normalise_lifecycle_status(status)
        self.lifecycle_status       = self.status  # canonical alias


# ─── Number validation helpers ────────────────────────────────────────────────

_LOTTERY_RULES = {
    "BIG_LOTTO":   {"k": 6, "pool": 49},
    "POWER_LOTTO": {"k": 6, "pool": 38},
    "DAILY_539":   {"k": 5, "pool": 39},
}

_NO_SPECIAL_TYPES = {"DAILY_539"}


def _validate_numbers(numbers: List[int], lottery_type: str, strategy_id: str) -> List[int]:
    """
    Validates that `numbers` are correct for the given lottery_type.
    Raises InvalidOutput if validation fails.
    Returns the sorted numbers list.
    """
    rules = _LOTTERY_RULES.get(lottery_type)
    if not rules:
        raise UnsupportedLotteryType(f"Unknown lottery_type: {lottery_type}")
    k, pool = rules["k"], rules["pool"]
    nums = sorted(int(n) for n in numbers)
    if len(nums) != k:
        raise InvalidOutput(
            f"{strategy_id}: expected {k} numbers, got {len(nums)}: {nums}"
        )
    if not all(1 <= n <= pool for n in nums):
        raise InvalidOutput(
            f"{strategy_id}: numbers {nums} out of range [1..{pool}]"
        )
    if len(set(nums)) != k:
        raise InvalidOutput(
            f"{strategy_id}: duplicate numbers in {nums}"
        )
    return nums


def _extract_first_bet(raw) -> Optional[List[int]]:
    """
    Extract the first bet from various return formats:
      - list of list[int]
      - list of dict with 'numbers' key
      - list of int (single bet)
    Returns a list of ints or None.
    """
    if not raw:
        return None
    first = raw[0]
    if isinstance(first, (list, tuple)):
        return [int(n) for n in first]
    elif isinstance(first, dict):
        return [int(n) for n in first.get("numbers", [])]
    elif isinstance(first, int):
        return [int(n) for n in raw]
    return None


# ─── Base Adapter ─────────────────────────────────────────────────────────────

class ReplayStrategyAdapter:
    """
    Base class for all replay strategy adapters.

    Subclasses implement _call_strategy(history, lottery_type) and are
    responsible for raising one of:
      - RejectPrediction       → replay_status = REJECTED
      - InsufficientHistory    → replay_status = INSUFFICIENT_HISTORY
      - UnsupportedLotteryType → replay_status = STRATEGY_UNAVAILABLE
      - InvalidOutput          → replay_status = INVALID_OUTPUT
      - any other Exception    → replay_status = REPLAY_ERROR
    """
    meta: _StrategyMeta

    def get_one_bet(
        self,
        history: List[dict],
        lottery_type: str,
    ) -> Tuple[List[int], Optional[int]]:
        """
        Returns (sorted_numbers, special_or_None) for one bet.
        history MUST be all draws STRICTLY BEFORE the target draw.
        special is None for DAILY_539; an int for POWER_LOTTO / BIG_LOTTO.
        """
        if lottery_type not in self.meta.supported_lottery_types:
            raise UnsupportedLotteryType(
                f"{self.meta.strategy_id} does not support {lottery_type}"
            )
        if len(history) < self.meta.min_history:
            raise InsufficientHistory(
                f"{self.meta.strategy_id}: needs {self.meta.min_history} draws, "
                f"got {len(history)}"
            )
        numbers = self._call_strategy(history, lottery_type)
        validated = _validate_numbers(numbers, lottery_type, self.meta.strategy_id)
        special = None if lottery_type in _NO_SPECIAL_TYPES else None  # always None in replay v0.1
        return validated, special

    def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
        raise NotImplementedError


# ─── Power Lotto Adapters ─────────────────────────────────────────────────────

class _PowerPrecision3BetAdapter(ReplayStrategyAdapter):
    meta = _StrategyMeta(
        strategy_id="power_precision_3bet",
        strategy_name="威力彩 Precision 3注",
        strategy_version="v0.1",
        supported_lottery_types=["POWER_LOTTO"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history, lottery_type):
        from tools.predict_power_precision_3bet import generate_power_precision_3bet
        raw = generate_power_precision_3bet(history)
        first = _extract_first_bet(raw)
        if not first:
            raise RejectPrediction("No bets returned by power_precision_3bet")
        return first


class _PowerOrthogonal5BetAdapter(ReplayStrategyAdapter):
    meta = _StrategyMeta(
        strategy_id="power_orthogonal_5bet",
        strategy_name="威力彩 Orthogonal 5注",
        strategy_version="v0.1",
        supported_lottery_types=["POWER_LOTTO"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history, lottery_type):
        from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
        raw = generate_orthogonal_5bet(history)
        first = _extract_first_bet(raw)
        if not first:
            raise RejectPrediction("No bets returned by power_orthogonal_5bet")
        return first


# ─── Big Lotto Adapters ───────────────────────────────────────────────────────

class _BigLottoTripleStrikeAdapter(ReplayStrategyAdapter):
    meta = _StrategyMeta(
        strategy_id="biglotto_triple_strike",
        strategy_name="大樂透 Triple Strike",
        strategy_version="v0.1",
        supported_lottery_types=["BIG_LOTTO"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history, lottery_type):
        from tools.predict_biglotto_triple_strike import generate_triple_strike
        raw = generate_triple_strike(history)
        first = _extract_first_bet(raw)
        if not first:
            raise RejectPrediction("No bets returned by biglotto_triple_strike")
        return first


class _BigLottoDeviation2BetAdapter(ReplayStrategyAdapter):
    meta = _StrategyMeta(
        strategy_id="biglotto_deviation_2bet",
        strategy_name="大樂透 Deviation 2注",
        strategy_version="v0.1",
        supported_lottery_types=["BIG_LOTTO"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history, lottery_type):
        from tools.predict_biglotto_deviation_2bet import deviation_complement_2bet
        raw = deviation_complement_2bet(history)
        first = _extract_first_bet(raw)
        if not first:
            raise RejectPrediction("No bets returned by biglotto_deviation_2bet")
        return first


# ─── DAILY_539 Adapters ───────────────────────────────────────────────────────

class _Daily539F4ColdAdapter(ReplayStrategyAdapter):
    meta = _StrategyMeta(
        strategy_id="daily539_f4cold",
        strategy_name="今彩539 F4 Cold",
        strategy_version="v0.1",
        supported_lottery_types=["DAILY_539"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history, lottery_type):
        from tools.predict_539_5bet_f4cold import predict as _f4cold_predict
        raw = _f4cold_predict(history)   # returns list of bets (each a list of 5 ints)
        first = _extract_first_bet(raw)
        if not first:
            raise RejectPrediction("No bets returned by daily539_f4cold")
        return first


class _Daily539MarkovColdAdapter(ReplayStrategyAdapter):
    meta = _StrategyMeta(
        strategy_id="daily539_markov_cold",
        strategy_name="今彩539 Markov Cold",
        strategy_version="v0.1",
        supported_lottery_types=["DAILY_539"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history, lottery_type):
        from tools.backtest_39lotto_comprehensive import MarkovStrategy
        strategy = MarkovStrategy(window=30)
        bet = strategy.predict(history)   # returns a single list of 5 ints
        if not bet:
            raise RejectPrediction("No bet returned by daily539_markov_cold")
        return bet   # already a flat list of ints


# ─── Registry ─────────────────────────────────────────────────────────────────

_ALL_ADAPTERS: List[ReplayStrategyAdapter] = [
    _PowerPrecision3BetAdapter(),
    _PowerOrthogonal5BetAdapter(),
    _BigLottoTripleStrikeAdapter(),
    _BigLottoDeviation2BetAdapter(),
    _Daily539F4ColdAdapter(),
    _Daily539MarkovColdAdapter(),
]

# strategy_id -> adapter (generation-eligible: ONLINE / ACTIVE)
_REGISTRY: dict[str, ReplayStrategyAdapter] = {
    a.meta.strategy_id: a
    for a in _ALL_ADAPTERS
    if a.meta.status in _GENERATION_STATUSES
}


def list_strategies(
    lottery_type: Optional[str] = None,
    lifecycle_status: Optional[str] = None,
) -> List[dict]:
    """
    Returns a list of ALL registered strategy metadata dicts (P0-A: all lifecycle states).

    Optional filters:
      lottery_type     — restrict to strategies that support this lottery type
      lifecycle_status — restrict to strategies with this lifecycle status
                         (ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED)
                         If None, ALL lifecycle states are returned.

    Each entry includes 'strategy_lifecycle_status' (canonical normalised value).
    """
    # Normalise requested filter value (accept legacy ACTIVE as ONLINE)
    canonical_filter: Optional[str] = None
    if lifecycle_status:
        canonical_filter = normalise_lifecycle_status(lifecycle_status.upper())

    out = []
    for a in _ALL_ADAPTERS:
        # Lifecycle filter (if specified)
        if canonical_filter and a.meta.lifecycle_status != canonical_filter:
            continue
        # Lottery type filter
        if lottery_type and lottery_type not in a.meta.supported_lottery_types:
            continue
        out.append({
            "strategy_id":              a.meta.strategy_id,
            "strategy_name":            a.meta.strategy_name,
            "strategy_version":         a.meta.strategy_version,
            "supported_lottery_types":  a.meta.supported_lottery_types,
            "min_history":              a.meta.min_history,
            "status":                   a.meta.status,           # canonical
            "strategy_lifecycle_status": a.meta.lifecycle_status, # explicit alias
        })
    return out


def get_strategy_lifecycle_status(strategy_id: str) -> Optional[str]:
    """
    Returns the canonical lifecycle_status for a strategy_id, or None if unknown.
    Searches ALL adapters (not just the generation-eligible registry).
    """
    for a in _ALL_ADAPTERS:
        if a.meta.strategy_id == strategy_id:
            return a.meta.lifecycle_status
    return None


def get_adapter(strategy_id: str) -> ReplayStrategyAdapter:
    """Returns the adapter for a given strategy_id, or raises KeyError."""
    if strategy_id not in _REGISTRY:
        raise KeyError(f"Unknown strategy_id: {strategy_id!r}. "
                       f"Available: {list(_REGISTRY.keys())}")
    return _REGISTRY[strategy_id]


def get_adapters_for_lottery(lottery_type: str) -> List[ReplayStrategyAdapter]:
    """Returns all generation-eligible (ONLINE) adapters that support `lottery_type`."""
    return [
        a for a in _ALL_ADAPTERS
        if a.meta.status in _GENERATION_STATUSES
        and lottery_type in a.meta.supported_lottery_types
    ]
