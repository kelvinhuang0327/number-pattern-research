"""
p56_wave5_powerlotto_adapters.py
=================================
P56 Wave 5 — POWER_LOTTO Dry-Run Adapter Scaffold

Standalone replay adapter wrappers for the 3 Wave 5 POWER_LOTTO strategies.
These adapters are NOT registered in replay_strategy_registry._ALL_ADAPTERS
or _REGISTRY. They exist exclusively for P56 temp-DB dry-run rehearsal.

POWER_LOTTO specifics (canonical, from P46/P47):
  - First zone pool: 1-38, pick 6 per bet
  - Second zone (special): 1-8, pick 1
  - predicted_numbers: 6 unique ints in [1, 38]
  - predicted_special: 1 int in [1, 8]
  - hit_count: FIRST-ZONE ONLY (do NOT count special)
  - special_hit: 1 if predicted_special == actual_special, else 0
  - Lifecycle: DRY_RUN

HARD RULES (mirrors p47_wave4_powerlotto_adapters.py):
  - history MUST be all draws STRICTLY BEFORE the target draw (causal slice).
  - Adapters MUST NOT read external state (DB, files, env) during prediction.
  - Only one bet-0 is recorded per (strategy, draw) pair.
  - Each bet must have exactly 6 distinct integers in range [1..38].
  - predicted_special must be in range [1..8].
  - No random.seed() usage — all algorithms are deterministic.

LIFECYCLE NOTE:
  All 3 strategies have lifecycle_status=DRY_RUN (not ONLINE, not RETIRED).
  Dry-run rows go ONLY to /tmp/p56_temp.db — never to lottery_v2.db.

Wave 5 Strategies (from P55 candidate planning):
  cold_complement_2bet      — Cold-reversion, 100% non-overlap, bet-0: cold top 1-6
  fourier30_markov30_2bet   — Short-window Fourier30+Markov30, bet-0: Fourier30 top-6
  zonal_entropy_2bet        — Entropy-adaptive zone selection, bet-0: entropy-gated

P55 planning: docs/replay/p55_powerlotto_wave5_candidate_planning_20260525.md
Reference: lottery_api/models/p47_wave4_powerlotto_adapters.py (Wave 4 pattern)
"""
from __future__ import annotations

import sys
import logging
import math
import numpy as np
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

_POOL = 38          # POWER_LOTTO first-zone pool 1..38
_PICK = 6           # numbers per bet (first zone)
_SPECIAL_POOL = 8   # POWER_LOTTO second-zone pool 1..8

_COLD_WINDOW = 100   # cold_complement_2bet: frequency window
_F30_WINDOW = 30     # fourier30_markov30_2bet: Fourier window
_M30_WINDOW = 30     # fourier30_markov30_2bet: Markov window
_ZONE_WINDOW = 30    # zonal_entropy_2bet: entropy computation window
_ZONE_COLD_WINDOW = 100  # zonal_entropy_2bet: cold fallback window
_ENTROPY_CHAOS_THRESHOLD = 2.2  # bits; log2(8) ≈ 3.0, chaos if > 2.2

WAVE5_STRATEGY_IDS = frozenset({
    "cold_complement_2bet",
    "fourier30_markov30_2bet",
    "zonal_entropy_2bet",
})

WAVE5_STRATEGY_ID_LIST = [
    "cold_complement_2bet",
    "fourier30_markov30_2bet",
    "zonal_entropy_2bet",
]


# ─── Zone mapping ─────────────────────────────────────────────────────────────

def _get_zone(num: int) -> int:
    """
    Map POWER_LOTTO number (1..38) to zone (0..7).
    Mirrors power_scientific_zonal.py: zone = (num-1)//5, with num>35 → zone 7.
    """
    if num > 35:
        return 7
    return (num - 1) // 5


def _zone_entropy(history: List[dict], window: int = _ZONE_WINDOW) -> float:
    """
    Compute Shannon entropy (bits) of zone distribution over last `window` draws.

    Returns entropy in [0, log2(8)] ≈ [0, 3.0].
    High entropy → chaotic (numbers scattered across zones).
    Low entropy  → stable (numbers cluster in fewer zones).
    """
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return 0.0

    zone_counts: Counter = Counter()
    for d in recent:
        for num in d["numbers"]:
            if 1 <= num <= _POOL:
                zone_counts[_get_zone(num)] += 1

    total = sum(zone_counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in zone_counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


# ─── Special number predictor ────────────────────────────────────────────────

def _special_predict(history: List[dict], window: int = 100) -> int:
    """
    Predict special number (1..8) using frequency-based mean-reversion.

    Identical to p47_wave4_powerlotto_adapters._special_predict().
    Returns the number in [1..8] closest to expected frequency over `window` draws.
    Falls back to 1 if no history.
    """
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return 1

    freq: Counter = Counter()
    for d in recent:
        sp = d.get("special")
        if sp is not None and 1 <= sp <= _SPECIAL_POOL:
            freq[sp] += 1

    w = len(recent)
    expected = w / _SPECIAL_POOL  # each special expected w/8 times

    best = min(range(1, _SPECIAL_POOL + 1), key=lambda n: abs(freq.get(n, 0) - expected))
    return best


# ─── cold_complement_2bet — prediction ────────────────────────────────────────

def predict_cold_complement_2bet_bet0(history: List[dict]) -> List[int]:
    """
    Bet-0 of cold_complement_2bet.

    Cold-reversion: selects the 6 numbers with the LOWEST frequency over the
    last 100 draws (cold top 1-6). Tie-breaking: lower number preferred.

    Theory: cold-reversion assumes underrepresented numbers revert toward
    expected frequency. Validated at edge +0.45% (N=200).

    Fully deterministic: Counter → stable sort. No random.seed().
    """
    recent = history[-_COLD_WINDOW:] if len(history) >= _COLD_WINDOW else history
    freq: Counter = Counter()
    for d in recent:
        for num in d["numbers"]:
            if 1 <= num <= _POOL:
                freq[num] += 1

    # Sort by frequency ASC, then by number ASC as stable tie-breaker
    sorted_cold = sorted(range(1, _POOL + 1), key=lambda n: (freq.get(n, 0), n))
    return sorted(sorted_cold[:_PICK])


# ─── fourier30_markov30_2bet — prediction ─────────────────────────────────────

def predict_fourier30_markov30_2bet_bet0(history: List[dict]) -> List[int]:
    """
    Bet-0 of fourier30_markov30_2bet — Fourier30 top-6.

    Weighted frequency with linear recency weight over the last 30 draws.
    Weight(draw_i) = 1 + 2 * (i / n) — linearly increasing (1.0 to 3.0).
    This gives recent draws 3× more weight than the oldest in the window.

    Mirrors bet1_fourier30() in tools/power_2bet_hedging.py (same algorithm,
    adapted to use only first-zone numbers 1..38).

    Fully deterministic: Counter → stable sort. No random.seed().
    """
    recent = history[-_F30_WINDOW:] if len(history) >= _F30_WINDOW else history
    n = len(recent)
    if n == 0:
        return list(range(1, _PICK + 1))

    weighted_freq: Counter = Counter()
    for i, draw in enumerate(recent):
        # Linear recency weight: 1.0 (oldest) → 3.0 (most recent)
        weight = 1.0 + 2.0 * (i / n)
        for num in draw["numbers"]:
            if 1 <= num <= _POOL:
                weighted_freq[num] += weight

    # Top-6 by weighted frequency, tie-break by number ASC
    ranked = sorted(
        range(1, _POOL + 1),
        key=lambda num: (-weighted_freq.get(num, 0.0), num),
    )
    return sorted(ranked[:_PICK])


# ─── zonal_entropy_2bet — prediction ─────────────────────────────────────────

def predict_zonal_entropy_2bet_bet0(history: List[dict]) -> List[int]:
    """
    Bet-0 of zonal_entropy_2bet — entropy-adaptive zone selection.

    Regime detection:
      entropy = Shannon entropy of zone distribution over last 30 draws.
      If entropy > 2.2 bits (chaotic): cold mode (window=100)
      If entropy ≤ 2.2 bits (stable):  hot mode (window=30)

    Cold mode: top-6 by lowest frequency (cold numbers; reversion hypothesis).
    Hot mode:  top-6 by highest frequency (hot numbers; momentum hypothesis).

    Determinism guarantee:
      - No random.seed() (was flagged in power_scientific_zonal.py — removed).
      - Tie-breaking by number ASC ensures stable ranking.
      - No external state or file reads during prediction.
    """
    entropy = _zone_entropy(history, window=_ZONE_WINDOW)
    is_chaotic = entropy > _ENTROPY_CHAOS_THRESHOLD

    if is_chaotic:
        # Cold regime: cold numbers over window=100
        recent = history[-_ZONE_COLD_WINDOW:] if len(history) >= _ZONE_COLD_WINDOW else history
        freq: Counter = Counter()
        for d in recent:
            for num in d["numbers"]:
                if 1 <= num <= _POOL:
                    freq[num] += 1
        # Sort by frequency ASC (cold first), tie-break by number ASC
        ranked = sorted(range(1, _POOL + 1), key=lambda n: (freq.get(n, 0), n))
    else:
        # Stable regime: hot numbers over window=30 (momentum)
        recent = history[-_ZONE_WINDOW:] if len(history) >= _ZONE_WINDOW else history
        freq = Counter()
        for d in recent:
            for num in d["numbers"]:
                if 1 <= num <= _POOL:
                    freq[num] += 1
        # Sort by frequency DESC (hot first), tie-break by number ASC
        ranked = sorted(range(1, _POOL + 1), key=lambda n: (-freq.get(n, 0), n))

    return sorted(ranked[:_PICK])


# ─── Adapter metadata / base ──────────────────────────────────────────────────

class _P56AdapterMeta:
    """Lightweight metadata holder for P56 Wave 5 POWER_LOTTO adapters."""
    def __init__(
        self,
        strategy_id: str,
        strategy_name: str,
        strategy_version: str,
        min_history: int = 30,
    ):
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.strategy_version = strategy_version
        self.lifecycle_status = "DRY_RUN"
        self.supported_lottery_types = ["POWER_LOTTO"]
        self.min_history = min_history


class _P56BaseAdapter:
    """
    Minimal replay adapter base for P56 Wave 5 POWER_LOTTO dry-run wrappers.
    NOT a subclass of ReplayStrategyAdapter to avoid any registry side-effects.
    lifecycle_status = DRY_RUN (NOT ONLINE, NOT RETIRED).

    Special number policy: PREDICTED_FROM_HISTORY
      - predicted_special in [1..8] via frequency mean-reversion (same as P47)
      - special_hit: 1 if predicted_special == actual_special, else 0
      - hit_count: FIRST-ZONE ONLY (never counts special)
    """
    meta: _P56AdapterMeta

    def get_one_bet(
        self, history: List[dict], lottery_type: str
    ) -> Tuple[List[int], int]:
        if lottery_type not in self.meta.supported_lottery_types:
            raise ValueError(
                f"{self.meta.strategy_id} does not support {lottery_type}"
            )
        if len(history) < self.meta.min_history:
            raise ValueError(
                f"{self.meta.strategy_id}: needs {self.meta.min_history} draws, "
                f"got {len(history)}"
            )
        numbers = self._predict(history)
        special = _special_predict(history)

        # Strict POWER_LOTTO semantic validation
        assert len(numbers) == _PICK, (
            f"Expected {_PICK} numbers, got {len(numbers)}: {numbers}"
        )
        assert len(set(numbers)) == _PICK, (
            f"Duplicate numbers in prediction: {numbers}"
        )
        assert all(1 <= n <= _POOL for n in numbers), (
            f"Numbers out of range [1..{_POOL}]: {numbers}"
        )
        assert 1 <= special <= _SPECIAL_POOL, (
            f"Special number out of range [1..{_SPECIAL_POOL}]: {special}"
        )
        return sorted(numbers), special

    def _predict(self, history: List[dict]) -> List[int]:
        raise NotImplementedError


class ColdComplement2BetAdapter(_P56BaseAdapter):
    """威力彩 冷號互補 2注 bet-0 — strategy_id: cold_complement_2bet"""
    meta = _P56AdapterMeta(
        strategy_id="cold_complement_2bet",
        strategy_name="威力彩 冷號互補 2注",
        strategy_version="v0.1-p56",
        min_history=10,  # window=100 with fallback; 10 = absolute minimum
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_cold_complement_2bet_bet0(history)


class Fourier30Markov30_2BetAdapter(_P56BaseAdapter):
    """威力彩 Fourier30+Markov30 2注 bet-0 — strategy_id: fourier30_markov30_2bet"""
    meta = _P56AdapterMeta(
        strategy_id="fourier30_markov30_2bet",
        strategy_name="威力彩 Fourier30+Markov30 2注",
        strategy_version="v0.1-p56",
        min_history=_F30_WINDOW,  # 30 for meaningful Fourier30 window
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_fourier30_markov30_2bet_bet0(history)


class ZonalEntropy2BetAdapter(_P56BaseAdapter):
    """威力彩 Zonal Entropy 2注 bet-0 — strategy_id: zonal_entropy_2bet"""
    meta = _P56AdapterMeta(
        strategy_id="zonal_entropy_2bet",
        strategy_name="威力彩 Zonal Entropy 2注",
        strategy_version="v0.1-p56",
        min_history=_ZONE_WINDOW,  # 30 for entropy computation
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_zonal_entropy_2bet_bet0(history)


# ─── Wave 5 adapter registry ──────────────────────────────────────────────────

WAVE5_ADAPTERS: List[_P56BaseAdapter] = [
    ColdComplement2BetAdapter(),       # rank 1 — score 75 (cold-reversion)
    Fourier30Markov30_2BetAdapter(),   # rank 2 — score 72 (short-window Fourier)
    ZonalEntropy2BetAdapter(),         # rank 3 — score 64 (entropy-adaptive)
]

WAVE5_ADAPTER_MAP: dict = {a.meta.strategy_id: a for a in WAVE5_ADAPTERS}


# ─── Dry-run row generator ────────────────────────────────────────────────────

def generate_dryrun_rows(
    all_draws: List[dict],
    rows_per_strategy: int = 1500,
) -> List[dict]:
    """
    Generate dry-run rows for all 3 Wave 5 POWER_LOTTO strategies.

    Follows p47_wave4_powerlotto_adapters.generate_dryrun_rows() exactly:
      - Uses the last `rows_per_strategy` draws as targets.
      - Strictly causal history slices (all draws before the target).
      - Records bet-0 only per (strategy, draw) pair.
      - lifecycle = "DRY_RUN", dry_run = 1.

    Returns a flat list of row dicts ready for temp DB insertion.
    Each row has:
      - strategy_id, lottery_type="POWER_LOTTO"
      - draw_date, prediction_cutoff_date, prediction_generated_at
      - predicted_numbers (list[int], 6 unique ints 1-38)
      - predicted_special (int, 1-8)
      - actual_numbers (list[int])
      - actual_special (int or None)
      - hit_numbers (list[int])     — first-zone matches only
      - hit_count (int)             — first-zone matches only (NOT special)
      - special_hit (int 0 or 1)   — predicted_special == actual_special
      - lifecycle = "DRY_RUN"
    """
    from datetime import datetime, timezone

    total_draws = len(all_draws)
    min_history_needed = max(a.meta.min_history for a in WAVE5_ADAPTERS)
    if total_draws < rows_per_strategy + min_history_needed:
        raise ValueError(
            f"Need at least {rows_per_strategy + min_history_needed} total draws, "
            f"got {total_draws}"
        )

    target_draws = all_draws[-rows_per_strategy:]
    now_str = datetime.now(timezone.utc).isoformat()
    all_rows: List[dict] = []

    for adapter in WAVE5_ADAPTERS:
        sid = adapter.meta.strategy_id
        for i, target in enumerate(target_draws):
            target_idx = total_draws - rows_per_strategy + i
            history = all_draws[:target_idx]  # strictly before target (causal)

            replay_status = "PREDICTED"
            reject_reason = None
            predicted_numbers = None
            predicted_special_val = None
            hit_numbers_list: List[int] = []
            hit_count = 0
            special_hit = 0

            try:
                numbers, special = adapter.get_one_bet(history, "POWER_LOTTO")
                predicted_numbers = numbers
                predicted_special_val = special

                actual_nums = target["numbers"]
                actual_sp = target.get("special")

                # First-zone hits ONLY — special is not counted here
                hits = sorted(set(numbers) & set(actual_nums))
                hit_numbers_list = hits
                hit_count = len(hits)

                # Special hit — separate accounting
                if actual_sp is not None and special is not None:
                    special_hit = 1 if special == actual_sp else 0
                else:
                    special_hit = 0

            except ValueError as exc:
                replay_status = "INSUFFICIENT_HISTORY"
                reject_reason = str(exc)
            except AssertionError as exc:
                replay_status = "INVALID_OUTPUT"
                reject_reason = str(exc)
            except Exception as exc:
                replay_status = "REPLAY_ERROR"
                reject_reason = str(exc)
                logger.warning("Unexpected error for %s draw %s: %s", sid, target.get("draw"), exc)

            row = {
                "strategy_id": sid,
                "lottery_type": "POWER_LOTTO",
                "target_draw": str(target["draw"]),
                "draw_date": target.get("date"),
                "prediction_cutoff_date": history[-1]["date"] if history else None,
                "prediction_generated_at": now_str,
                "predicted_numbers": predicted_numbers,       # 6 ints [1..38]
                "predicted_special": predicted_special_val,   # 1 int [1..8]
                "actual_numbers": target["numbers"],
                "actual_special": target.get("special"),
                "hit_numbers": hit_numbers_list,
                "hit_count": hit_count,                       # first-zone only
                "special_hit": special_hit,                   # 0 or 1
                "lifecycle": "DRY_RUN",
                "replay_status": replay_status,
                "reject_reason": reject_reason,
                "history_cutoff_draw": str(history[-1]["draw"]) if history else None,
                "strategy_name": adapter.meta.strategy_name,
                "strategy_version": adapter.meta.strategy_version,
            }
            all_rows.append(row)

    return all_rows
