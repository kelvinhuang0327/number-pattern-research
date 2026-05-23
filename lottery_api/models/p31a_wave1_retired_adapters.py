"""
p31a_wave1_retired_adapters.py
================================
P31A Wave 1 — DAILY_539 Retired Adapter Wrappers (Dry-Run Only)

Standalone replay adapter wrappers for the 5 RETIRED DAILY_539 strategies.
These adapters are NOT registered in replay_strategy_registry._ALL_ADAPTERS
or _REGISTRY. They exist exclusively for P31A temp-DB dry-run rehearsal.

HARD RULES (same as main registry):
  - history MUST be all draws STRICTLY BEFORE the target draw (causal slice).
  - Adapters MUST NOT read external state (DB, files, env) during prediction.
  - Only one bet is recorded per (strategy, draw) pair.
  - DAILY_539 has no special number — always returns None for special.
  - Each bet must have exactly 5 distinct integers in range [1..39].

LIFECYCLE NOTE:
  All 5 strategies have lifecycle_status=RETIRED.
  These wrappers do NOT promote them to ONLINE or ACTIVE.
  Dry-run rows go ONLY to /tmp/p31a_temp.db — never to lottery_v2.db.

Wave 1 Strategies:
  acb_1bet            — 今彩539 ACB 1注            (pure ACB signal)
  acb_markov_midfreq  — 今彩539 ACB+Markov 中頻     (ACB + Markov, midfreq-filtered)
  acb_markov_midfreq_3bet — 今彩539 ACB+Markov 中頻 3注  (bet-1 of 3-bet = ACB)
  midfreq_acb_2bet    — 今彩539 中頻 ACB 2注         (bet-1 of 2-bet = MidFreq)
  midfreq_fourier_2bet — 今彩539 中頻 Fourier 2注    (bet-1 of 2-bet = MidFreq)

Algorithm Reference: lottery_api/CLAUDE.md §ACB, §MidFreq, §Fourier
"""
from __future__ import annotations

import sys
import logging
import numpy as np
from collections import Counter
from pathlib import Path
from typing import List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

_POOL = 39      # DAILY_539 number pool 1..39
_PICK = 5       # numbers per bet
_ACB_WINDOW = 100
_MIDFREQ_WINDOW = 100
_MARKOV_WINDOW = 30

# Cross-zone sets for DAILY_539 (pool=39)
_Z1 = frozenset(range(1, 14))   # 1–13
_Z2 = frozenset(range(14, 27))  # 14–26
_Z3 = frozenset(range(27, 40))  # 27–39

WAVE1_STRATEGY_IDS = frozenset({
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
})


# ─── Core algorithm helpers ───────────────────────────────────────────────────

def _zone_of(n: int) -> int:
    if n in _Z1:
        return 1
    if n in _Z2:
        return 2
    return 3


def _apply_cross_zone(ranked: List[int], scores: dict, n: int = _PICK) -> List[int]:
    """
    Given a ranked list of numbers and their scores, pick top-n while
    enforcing ≥2 distinct zones.  If unconstrained top-n already satisfies
    the constraint, returns unchanged.  Otherwise swaps one number from the
    over-represented zone with the best candidate from a missing zone.
    """
    selected = list(ranked[:n])
    zones_present = {_zone_of(x) for x in selected}

    if len(zones_present) >= 2:
        return selected

    # Identify dominant zone and missing zones
    zone_count = Counter(_zone_of(x) for x in selected)
    dominant_zone = max(zone_count, key=zone_count.get)
    missing_zones = [z for z in (1, 2, 3) if z not in zones_present]

    for mz in missing_zones:
        candidates = [x for x in ranked if _zone_of(x) == mz and x not in selected]
        if not candidates:
            continue
        new_num = candidates[0]
        # Remove worst from dominant zone
        dom_nums = [x for x in selected if _zone_of(x) == dominant_zone]
        if dom_nums:
            remove_num = min(dom_nums, key=lambda x: scores[x])
            selected = [x for x in selected if x != remove_num]
            selected.append(new_num)
            break

    return selected[:n]


def _acb_scores(history: List[dict], window: int = _ACB_WINDOW) -> dict:
    """
    Compute ACB (Anomaly Capture Bet) scores for DAILY_539 pool.

    score = (freq_deficit×0.4 + gap_score×0.6) × boundary_bonus × mod3_bonus

    freq_deficit = (expected_count - actual_count) / expected_count
    gap_score    = (w - 1 - last_seen_idx) / w   (0=just seen, 1=never seen)
    boundary_bonus = 1.2 if n≤5 or n≥35 else 1.0
    mod3_bonus     = 1.1 if n%3==0 else 1.0

    Returns dict: {num: score} for num in 1..39.
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w == 0:
        return {n: 0.0 for n in range(1, _POOL + 1)}

    expected = w * _PICK / _POOL

    freq: Counter = Counter()
    last_seen: dict = {}
    for i, d in enumerate(recent):
        for num in d["numbers"]:
            freq[num] += 1
            last_seen[num] = i

    scores: dict = {}
    for num in range(1, _POOL + 1):
        actual = freq.get(num, 0)
        freq_deficit = (expected - actual) / max(expected, 1.0)

        # gap_score: 0 = just appeared, 1 = never seen in window
        gap_idx = last_seen.get(num, -1)
        gap_score = (w - 1 - gap_idx) / w

        boundary_bonus = 1.2 if (num <= 5 or num >= 35) else 1.0
        mod3_bonus = 1.1 if (num % 3 == 0) else 1.0

        scores[num] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus

    return scores


def _midfreq_scores(history: List[dict], window: int = _MIDFREQ_WINDOW) -> dict:
    """
    Compute MidFreq (mean-reversion) scores for DAILY_539 pool.

    score = -|actual_count - expected_count|
    Numbers closest to expected frequency score highest.

    Returns dict: {num: score} for num in 1..39.
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w == 0:
        return {n: 0.0 for n in range(1, _POOL + 1)}

    expected = w * _PICK / _POOL
    freq: Counter = Counter()
    for d in recent:
        for num in d["numbers"]:
            freq[num] += 1

    return {num: -abs(freq.get(num, 0) - expected) for num in range(1, _POOL + 1)}


def _markov_scores(history: List[dict], window: int = _MARKOV_WINDOW) -> np.ndarray:
    """
    Compute Markov transition scores for DAILY_539 pool (indices 0..38).

    Returns np.ndarray of shape (39,).
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 2:
        return np.ones(_POOL)

    transition = np.zeros((_POOL, _POOL))
    for i in range(len(recent) - 1):
        for a in recent[i]["numbers"]:
            for b in recent[i + 1]["numbers"]:
                transition[a - 1][b - 1] += 1

    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    transition = transition / row_sums

    last_nums = recent[-1]["numbers"]
    scores = np.zeros(_POOL)
    for num in last_nums:
        scores += transition[num - 1]

    return scores


# ─── Prediction functions ─────────────────────────────────────────────────────

def predict_acb(history: List[dict], n: int = _PICK) -> List[int]:
    """Pure ACB prediction — bet-1 of acb_1bet and acb_markov_midfreq_3bet."""
    scores = _acb_scores(history)
    ranked = sorted(range(1, _POOL + 1), key=lambda x: -scores[x])
    selected = _apply_cross_zone(ranked, scores, n)
    return sorted(selected)


def predict_midfreq(history: List[dict], n: int = _PICK) -> List[int]:
    """Pure MidFreq prediction — bet-1 of midfreq_acb_2bet and midfreq_fourier_2bet."""
    scores = _midfreq_scores(history)
    ranked = sorted(range(1, _POOL + 1), key=lambda x: -scores[x])
    # MidFreq does not require cross-zone constraint (mean-reversion signal)
    return sorted(ranked[:n])


def predict_acb_markov_midfreq(history: List[dict], n: int = _PICK) -> List[int]:
    """
    ACB+Markov midfreq-filtered fusion — acb_markov_midfreq single-bet.

    Algorithm:
      1. Compute ACB scores and Markov transition scores.
      2. Restrict candidate pool to midfreq numbers (within 1σ of expected freq).
      3. Combine: combined = 0.5 × norm(ACB) + 0.5 × norm(Markov).
      4. Apply cross-zone constraint (≥2 zones).
    """
    recent = history[-_ACB_WINDOW:] if len(history) >= _ACB_WINDOW else history
    w = len(recent)
    if w == 0:
        return list(range(1, n + 1))

    acb = _acb_scores(history)
    markov_raw = _markov_scores(history)

    # Normalize both signals to [0, 1]
    acb_vals = np.array([acb[num] for num in range(1, _POOL + 1)])
    a_min, a_max = acb_vals.min(), acb_vals.max()
    a_range = a_max - a_min if a_max > a_min else 1.0
    acb_norm = (acb_vals - a_min) / a_range

    m_min, m_max = markov_raw.min(), markov_raw.max()
    m_range = m_max - m_min if m_max > m_min else 1.0
    markov_norm = (markov_raw - m_min) / m_range

    # Midfreq filter: within 1 SD of expected frequency
    expected = w * _PICK / _POOL
    freq: Counter = Counter()
    for d in recent:
        for num in d["numbers"]:
            freq[num] += 1
    freq_arr = np.array([freq.get(n, 0) for n in range(1, _POOL + 1)], dtype=float)
    sigma = float(np.std(freq_arr))
    midfreq_mask = np.abs(freq_arr - expected) <= sigma  # True = midfreq candidate

    # Combine signals; boost midfreq candidates
    combined = {}
    for idx, num in enumerate(range(1, _POOL + 1)):
        boost = 1.1 if midfreq_mask[idx] else 0.8
        combined[num] = (acb_norm[idx] * 0.5 + markov_norm[idx] * 0.5) * boost

    ranked = sorted(range(1, _POOL + 1), key=lambda x: -combined[x])
    selected = _apply_cross_zone(ranked, combined, n)
    return sorted(selected)


def predict_fourier_midfreq(history: List[dict], n: int = _PICK) -> List[int]:
    """
    MidFreq bet (bet-1) for midfreq_fourier_2bet.
    Same as predict_midfreq — the Fourier component is bet-2 (not recorded in replay).
    """
    return predict_midfreq(history, n)


# ─── Adapter class wrappers ───────────────────────────────────────────────────

class _P31AAdapterMeta:
    """Lightweight metadata holder (mirrors _StrategyMeta without registry binding)."""
    def __init__(
        self,
        strategy_id: str,
        strategy_name: str,
        strategy_version: str,
        min_history: int = 100,
    ):
        self.strategy_id = strategy_id
        self.strategy_name = strategy_name
        self.strategy_version = strategy_version
        self.lifecycle_status = "RETIRED"
        self.supported_lottery_types = ["DAILY_539"]
        self.min_history = min_history


class _P31ABaseAdapter:
    """
    Minimal replay adapter base for P31A dry-run wrappers.
    NOT a subclass of ReplayStrategyAdapter to avoid any registry side-effects.
    """
    meta: _P31AAdapterMeta

    def get_one_bet(
        self, history: List[dict], lottery_type: str
    ) -> Tuple[List[int], Optional[int]]:
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
        # Validate output
        assert len(numbers) == _PICK, f"Expected {_PICK} numbers, got {len(numbers)}"
        assert len(set(numbers)) == _PICK, f"Duplicate numbers: {numbers}"
        assert all(1 <= n <= _POOL for n in numbers), f"Out of range: {numbers}"
        return sorted(numbers), None  # DAILY_539: no special

    def _predict(self, history: List[dict]) -> List[int]:
        raise NotImplementedError


class Acb1BetAdapter(_P31ABaseAdapter):
    """今彩539 ACB 1注 — strategy_id: acb_1bet"""
    meta = _P31AAdapterMeta(
        strategy_id="acb_1bet",
        strategy_name="今彩539 ACB 1注",
        strategy_version="v0.1-p31a",
        min_history=_ACB_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_acb(history)


class AcbMarkovMidfreqAdapter(_P31ABaseAdapter):
    """今彩539 ACB+Markov 中頻 — strategy_id: acb_markov_midfreq"""
    meta = _P31AAdapterMeta(
        strategy_id="acb_markov_midfreq",
        strategy_name="今彩539 ACB+Markov 中頻",
        strategy_version="v0.1-p31a",
        min_history=_ACB_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_acb_markov_midfreq(history)


class AcbMarkovMidfreq3BetAdapter(_P31ABaseAdapter):
    """
    今彩539 ACB+Markov 中頻 3注 — strategy_id: acb_markov_midfreq_3bet

    Replay records bet-1 only = pure ACB bet.
    (bet-2 = Markov, bet-3 = Fourier are not recorded in replay.)
    """
    meta = _P31AAdapterMeta(
        strategy_id="acb_markov_midfreq_3bet",
        strategy_name="今彩539 ACB+Markov 中頻 3注",
        strategy_version="v0.1-p31a",
        min_history=_ACB_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        # Bet-1 of the 3-bet orthogonal = pure ACB
        return predict_acb(history)


class MidfreqAcb2BetAdapter(_P31ABaseAdapter):
    """
    今彩539 中頻 ACB 2注 — strategy_id: midfreq_acb_2bet

    Replay records bet-1 only = MidFreq bet.
    (bet-2 = ACB is not recorded in replay.)
    """
    meta = _P31AAdapterMeta(
        strategy_id="midfreq_acb_2bet",
        strategy_name="今彩539 中頻 ACB 2注",
        strategy_version="v0.1-p31a",
        min_history=_MIDFREQ_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_midfreq(history)


class MidfreqFourier2BetAdapter(_P31ABaseAdapter):
    """
    今彩539 中頻 Fourier 2注 — strategy_id: midfreq_fourier_2bet

    Replay records bet-1 only = MidFreq bet.
    (bet-2 = Fourier is not recorded in replay.)
    """
    meta = _P31AAdapterMeta(
        strategy_id="midfreq_fourier_2bet",
        strategy_name="今彩539 中頻 Fourier 2注",
        strategy_version="v0.1-p31a",
        min_history=_MIDFREQ_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_midfreq(history)


# ─── Wave 1 adapter registry (ordered) ───────────────────────────────────────

WAVE1_ADAPTERS: List[_P31ABaseAdapter] = [
    Acb1BetAdapter(),
    AcbMarkovMidfreqAdapter(),
    AcbMarkovMidfreq3BetAdapter(),
    MidfreqAcb2BetAdapter(),
    MidfreqFourier2BetAdapter(),
]

WAVE1_ADAPTER_MAP: dict = {a.meta.strategy_id: a for a in WAVE1_ADAPTERS}
