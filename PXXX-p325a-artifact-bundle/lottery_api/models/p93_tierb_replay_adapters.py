"""
p93_tierb_replay_adapters.py
============================
P93 Tier B Replay Adapter Bootstrap — 5 adapter-ready strategies.

SCOPE: Dry-run / temp-DB rehearsal only.
       These adapters are NOT registered in replay_strategy_registry._REGISTRY.
       They must NOT be used for live prediction, strategy promotion, or
       production replay row insertion.

GOVERNANCE:
  - No lifecycle/champion/registry mutation.
  - No writes to lottery_api/data/lottery_v2.db.
  - All rows generated using these adapters are dry_run=1, temp-DB only.
  - No official API calls.
  - Causal isolation: history = draws strictly before target draw.

Target strategies (P93):
  1. daily539_f4cold_3bet    — DAILY_539, 3 bets from predict(hist)[:3]
  2. daily539_f4cold_5bet    — DAILY_539, 5 bets from predict(hist)
  3. biglotto_echo_aware_3bet — BIG_LOTTO, 3 bets from echo_aware_mixed_3bet()
  4. power_fourier_rhythm_2bet — POWER_LOTTO, 2 bets from fourier_rhythm_predict(n_bets=2)
  5. biglotto_ts3_markov_4bet_w30 — BIG_LOTTO, 4 bets from generate_ts3_markov_4bet(w=30)

Storage convention: one replay row per (strategy, draw), storing the FIRST bet only.
Multi-bet adapters use _extract_first_bet() to normalise output to one bet.
"""
from __future__ import annotations

import sys
import logging
from pathlib import Path
from typing import List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Re-use shared primitives from the canonical registry — read-only import.
from lottery_api.models.replay_strategy_registry import (
    ReplayStrategyAdapter,
    _StrategyMeta,
    _extract_first_bet,
    _validate_numbers,
    InsufficientHistory,
    InvalidOutput,
    RejectPrediction,
    UnsupportedLotteryType,
)

logger = logging.getLogger(__name__)

# ─── Number-range rules (copied from registry for self-containment) ──────────

_LOTTERY_RULES = {
    "BIG_LOTTO":   {"k": 6, "pool": 49},
    "POWER_LOTTO": {"k": 6, "pool": 38},
    "DAILY_539":   {"k": 5, "pool": 39},
}

_NO_SPECIAL_TYPES = {"DAILY_539"}

# Expected bet counts per strategy (for validation in dry-run)
EXPECTED_BET_COUNTS: dict[str, int] = {
    "daily539_f4cold_3bet":       3,
    "daily539_f4cold_5bet":       5,
    "biglotto_echo_aware_3bet":   3,
    "power_fourier_rhythm_2bet":  2,
    "biglotto_ts3_markov_4bet_w30": 4,
}

# All 5 P93 strategy IDs in canonical order
P93_STRATEGY_IDS: List[str] = list(EXPECTED_BET_COUNTS.keys())

# Lottery type mapping
P93_LOTTERY_TYPES: dict[str, str] = {
    "daily539_f4cold_3bet":          "DAILY_539",
    "daily539_f4cold_5bet":          "DAILY_539",
    "biglotto_echo_aware_3bet":      "BIG_LOTTO",
    "power_fourier_rhythm_2bet":     "POWER_LOTTO",
    "biglotto_ts3_markov_4bet_w30":  "BIG_LOTTO",
}


# ─── Adapter 1: daily539_f4cold_3bet ─────────────────────────────────────────
# RSM source: f4cold_3bet
# Function:   tools/predict_539_5bet_f4cold.py::predict(hist)[:3]
# Bets:       3 (first 3 of the 5-bet Fourier4+Cold function)
# Special:    None (DAILY_539 has no special ball)

class Daily539F4Cold3BetAdapter(ReplayStrategyAdapter):
    """
    Adapter for daily539_f4cold_3bet (P93 Tier B dry-run).
    Wraps predict_539_5bet_f4cold.predict(hist)[:3].
    Returns first bet for storage (one row per draw).
    """
    meta = _StrategyMeta(
        strategy_id="daily539_f4cold_3bet",
        strategy_name="今彩539 F4Cold 3注",
        strategy_version="v0.1",
        supported_lottery_types=["DAILY_539"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
        from tools.predict_539_5bet_f4cold import predict
        raw = predict(history)  # returns 5 bets
        if not raw or len(raw) < 3:
            raise RejectPrediction(
                f"daily539_f4cold_3bet: predict() returned <3 bets: {raw}"
            )
        raw_3 = raw[:3]  # Take first 3 bets
        first = _extract_first_bet(raw_3)
        if not first or len(first) != 5:
            raise InvalidOutput(
                f"daily539_f4cold_3bet: _extract_first_bet returned {first}"
            )
        return first

    def get_all_bets(self, history: List[dict]) -> List[List[int]]:
        """Return all 3 validated bets for dry-run row generation."""
        from tools.predict_539_5bet_f4cold import predict
        raw = predict(history)
        if not raw or len(raw) < 3:
            raise RejectPrediction(
                f"daily539_f4cold_3bet: predict() returned <3 bets"
            )
        bets = []
        for raw_bet in raw[:3]:
            bet = sorted([int(n) for n in raw_bet])
            _validate_numbers(bet, "DAILY_539", "daily539_f4cold_3bet")
            bets.append(bet)
        return bets


# ─── Adapter 2: daily539_f4cold_5bet ─────────────────────────────────────────
# RSM source: f4cold_5bet
# Function:   tools/predict_539_5bet_f4cold.py::predict(hist)
# Bets:       5 (all bets from the 5-bet Fourier4+Cold function)
# Special:    None (DAILY_539 has no special ball)

class Daily539F4Cold5BetAdapter(ReplayStrategyAdapter):
    """
    Adapter for daily539_f4cold_5bet (P93 Tier B dry-run).
    Wraps predict_539_5bet_f4cold.predict(hist) (all 5 bets).
    Returns first bet for storage (one row per draw).
    """
    meta = _StrategyMeta(
        strategy_id="daily539_f4cold_5bet",
        strategy_name="今彩539 F4Cold 5注",
        strategy_version="v0.1",
        supported_lottery_types=["DAILY_539"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
        from tools.predict_539_5bet_f4cold import predict
        raw = predict(history)  # returns 5 bets
        if not raw or len(raw) < 5:
            raise RejectPrediction(
                f"daily539_f4cold_5bet: predict() returned <5 bets: {raw}"
            )
        first = _extract_first_bet(raw)
        if not first or len(first) != 5:
            raise InvalidOutput(
                f"daily539_f4cold_5bet: _extract_first_bet returned {first}"
            )
        return first

    def get_all_bets(self, history: List[dict]) -> List[List[int]]:
        """Return all 5 validated bets for dry-run row generation."""
        from tools.predict_539_5bet_f4cold import predict
        raw = predict(history)
        if not raw or len(raw) < 5:
            raise RejectPrediction(
                f"daily539_f4cold_5bet: predict() returned <5 bets"
            )
        bets = []
        for raw_bet in raw[:5]:
            bet = sorted([int(n) for n in raw_bet])
            _validate_numbers(bet, "DAILY_539", "daily539_f4cold_5bet")
            bets.append(bet)
        return bets


# ─── Adapter 3: biglotto_echo_aware_3bet ─────────────────────────────────────
# RSM source: echo_aware_3bet
# Function:   tools/predict_biglotto_echo_3bet.py::echo_aware_mixed_3bet(history)
# Bets:       3 (Hot+Echo, Cold+Echo, Echo+Warm)
# Special:    None (predicted_special=NULL, BIG_LOTTO special not predicted)

class BigLottoEchoAware3BetAdapter(ReplayStrategyAdapter):
    """
    Adapter for biglotto_echo_aware_3bet (P93 Tier B dry-run).
    Wraps predict_biglotto_echo_3bet.echo_aware_mixed_3bet(history).
    Returns first bet for storage (one row per draw).
    """
    meta = _StrategyMeta(
        strategy_id="biglotto_echo_aware_3bet",
        strategy_name="大樂透 Echo-Aware 混合 3注",
        strategy_version="v0.1",
        supported_lottery_types=["BIG_LOTTO"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
        from tools.predict_biglotto_echo_3bet import echo_aware_mixed_3bet
        raw = echo_aware_mixed_3bet(history, window=50, echo_weight=0.25)
        if not raw or len(raw) < 3:
            raise RejectPrediction(
                f"biglotto_echo_aware_3bet: echo_aware_mixed_3bet returned <3 bets: {raw}"
            )
        first = _extract_first_bet(raw)
        if not first or len(first) != 6:
            raise InvalidOutput(
                f"biglotto_echo_aware_3bet: _extract_first_bet returned {first}"
            )
        return first

    def get_all_bets(self, history: List[dict]) -> List[List[int]]:
        """Return all 3 validated bets for dry-run row generation."""
        from tools.predict_biglotto_echo_3bet import echo_aware_mixed_3bet
        raw = echo_aware_mixed_3bet(history, window=50, echo_weight=0.25)
        if not raw or len(raw) < 3:
            raise RejectPrediction(
                f"biglotto_echo_aware_3bet: returned <3 bets"
            )
        bets = []
        for raw_bet in raw[:3]:
            bet = sorted([int(n) for n in raw_bet])
            _validate_numbers(bet, "BIG_LOTTO", "biglotto_echo_aware_3bet")
            bets.append(bet)
        return bets


# ─── Adapter 4: power_fourier_rhythm_2bet ────────────────────────────────────
# RSM source: fourier_rhythm_2bet (POWER_LOTTO)
# Function:   tools/power_fourier_rhythm.py::fourier_rhythm_predict(history, n_bets=2)
# Bets:       2 (Fourier rhythm orthogonal)
# Special:    None (predicted_special=NULL, POWER_LOTTO special not predicted in replay v0.1)

class PowerFourierRhythm2BetAdapter(ReplayStrategyAdapter):
    """
    Adapter for power_fourier_rhythm_2bet (P93 Tier B dry-run).
    Wraps power_fourier_rhythm.fourier_rhythm_predict(history, n_bets=2, window=500).
    Returns first bet for storage (one row per draw).

    Note: Distinct from fourier_rhythm_3bet (ONLINE in main registry, n_bets=3).
    This adapter covers the 2-bet variant for POWER_LOTTO.
    """
    meta = _StrategyMeta(
        strategy_id="power_fourier_rhythm_2bet",
        strategy_name="威力彩 Fourier Rhythm 2注",
        strategy_version="v0.1",
        supported_lottery_types=["POWER_LOTTO"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        raw = fourier_rhythm_predict(history, n_bets=2, window=500)
        if not raw or len(raw) < 2:
            raise RejectPrediction(
                f"power_fourier_rhythm_2bet: fourier_rhythm_predict returned <2 bets: {raw}"
            )
        first = _extract_first_bet(raw)
        if not first or len(first) != 6:
            raise InvalidOutput(
                f"power_fourier_rhythm_2bet: _extract_first_bet returned {first}"
            )
        return first

    def get_all_bets(self, history: List[dict]) -> List[List[int]]:
        """Return all 2 validated bets for dry-run row generation."""
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        raw = fourier_rhythm_predict(history, n_bets=2, window=500)
        if not raw or len(raw) < 2:
            raise RejectPrediction(
                f"power_fourier_rhythm_2bet: returned <2 bets"
            )
        bets = []
        for raw_bet in raw[:2]:
            bet = sorted([int(n) for n in raw_bet])
            _validate_numbers(bet, "POWER_LOTTO", "power_fourier_rhythm_2bet")
            bets.append(bet)
        return bets


# ─── Adapter 5: biglotto_ts3_markov_4bet_w30 ─────────────────────────────────
# RSM source: ts3_markov_4bet_w30
# Function:   tools/backtest_biglotto_5bet_ts3markov.py::generate_ts3_markov_4bet(history, markov_window=30)
# Bets:       4 (Fourier + Cold + TailBalance + Markov)
# Special:    None (predicted_special=NULL, BIG_LOTTO special not predicted in replay v0.1)
# Note:       Distinct from SUPERSEDED ts3_markov_freq_5bet_w30.

class BigLottoTs3Markov4BetW30Adapter(ReplayStrategyAdapter):
    """
    Adapter for biglotto_ts3_markov_4bet_w30 (P93 Tier B dry-run).
    Wraps backtest_biglotto_5bet_ts3markov.generate_ts3_markov_4bet(history, markov_window=30).
    Returns first bet for storage (one row per draw).

    Governance: ts3_markov_freq_5bet_w30 is SUPERSEDED (REJECTED). This adapter
    covers the distinct 4-bet variant (ts3_markov_4bet_w30) confirmed in rsm_bootstrap.py.
    """
    meta = _StrategyMeta(
        strategy_id="biglotto_ts3_markov_4bet_w30",
        strategy_name="大樂透 TS3+Markov(w30) 4注",
        strategy_version="v0.1",
        supported_lottery_types=["BIG_LOTTO"],
        min_history=100,
        status="ONLINE",
    )

    def _call_strategy(self, history: List[dict], lottery_type: str) -> List[int]:
        from tools.backtest_biglotto_5bet_ts3markov import generate_ts3_markov_4bet
        raw = generate_ts3_markov_4bet(history, markov_window=30)
        if not raw or len(raw) < 4:
            raise RejectPrediction(
                f"biglotto_ts3_markov_4bet_w30: generate_ts3_markov_4bet returned "
                f"<4 bets: {raw}"
            )
        first = _extract_first_bet(raw)
        if not first or len(first) != 6:
            raise InvalidOutput(
                f"biglotto_ts3_markov_4bet_w30: _extract_first_bet returned {first}"
            )
        return first

    def get_all_bets(self, history: List[dict]) -> List[List[int]]:
        """Return all 4 validated bets for dry-run row generation."""
        from tools.backtest_biglotto_5bet_ts3markov import generate_ts3_markov_4bet
        raw = generate_ts3_markov_4bet(history, markov_window=30)
        if not raw or len(raw) < 4:
            raise RejectPrediction(
                f"biglotto_ts3_markov_4bet_w30: returned <4 bets"
            )
        bets = []
        for raw_bet in raw[:4]:
            bet = sorted([int(n) for n in raw_bet])
            _validate_numbers(bet, "BIG_LOTTO", "biglotto_ts3_markov_4bet_w30")
            bets.append(bet)
        return bets


# ─── P93 Adapter Registry (dry-run only) ─────────────────────────────────────
# NOT wired into replay_strategy_registry._REGISTRY.
# Used exclusively by p93_tierb_dryrun_rehearsal.py.

_P93_ADAPTERS: List[ReplayStrategyAdapter] = [
    Daily539F4Cold3BetAdapter(),
    Daily539F4Cold5BetAdapter(),
    BigLottoEchoAware3BetAdapter(),
    PowerFourierRhythm2BetAdapter(),
    BigLottoTs3Markov4BetW30Adapter(),
]

_P93_REGISTRY: dict[str, ReplayStrategyAdapter] = {
    a.meta.strategy_id: a for a in _P93_ADAPTERS
}


def get_p93_adapter(strategy_id: str) -> ReplayStrategyAdapter:
    """Returns the P93 dry-run adapter for a given strategy_id."""
    if strategy_id not in _P93_REGISTRY:
        raise KeyError(
            f"P93 adapter not found: {strategy_id!r}. "
            f"Available: {list(_P93_REGISTRY.keys())}"
        )
    return _P93_REGISTRY[strategy_id]


def list_p93_adapters() -> List[dict]:
    """Returns metadata for all 5 P93 adapters."""
    return [
        {
            "strategy_id":           a.meta.strategy_id,
            "strategy_name":         a.meta.strategy_name,
            "strategy_version":      a.meta.strategy_version,
            "lottery_type":          P93_LOTTERY_TYPES[a.meta.strategy_id],
            "expected_bet_count":    EXPECTED_BET_COUNTS[a.meta.strategy_id],
            "supported_lottery_types": a.meta.supported_lottery_types,
            "min_history":           a.meta.min_history,
            "status":                a.meta.status,
            "scope":                 "P93_DRYRUN_ONLY",
            "production_eligible":   False,
        }
        for a in _P93_ADAPTERS
    ]
