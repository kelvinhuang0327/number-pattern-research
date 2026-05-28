"""
p128_wave2_phase1_adapters.py
==============================
P128 Wave 2 Phase 1 — Multi-Bet get_all_bets() Adapters

Implements get_all_bets() for priority 1-6 strategies from P127 spec.

SCOPE BOUNDARIES (P128):
  - ADAPTER-ONLY: No DB writes, no controlled_apply, no replay row insertion.
  - These functions produce list[list[int]] — all N bets for a strategy.
  - No lifecycle mutation, no registry change.
  - production_db_rows_after = 72462 (unchanged from P127 baseline).

Strategies implemented (priority 1-6, all 2-bet):
  P1: midfreq_acb_2bet        (DAILY_539)    bet-1=MidFreq,       bet-2=ACB
  P2: midfreq_fourier_2bet    (DAILY_539)    bet-1=MidFreq,       bet-2=Fourier
  P3: zonal_entropy_2bet      (POWER_LOTTO)  bet-1=EntropyAdapt,  bet-2=OppRegime
  P4: cold_complement_2bet    (POWER_LOTTO)  bet-1=Cold,          bet-2=Hot
  P5: midfreq_fourier_2bet    (POWER_LOTTO)  bet-1=MidFreq+Fourier, bet-2=PureFourier
  P6: fourier30_markov30_2bet (POWER_LOTTO)  bet-1=Fourier30,     bet-2=Markov30

RSR-6 status: NOT applicable to Phase 1 (affects priority 10/12 only — Phase 2).
RSR-7 note:   fourier30_markov30_2bet (P6) has 1501 DB rows (expected 1500).
              Low priority, does NOT block adapter implementation.

Governance:
  - No lifecycle/champion/registry mutation.
  - No writes to lottery_api/data/lottery_v2.db.
  - Deterministic: same draw_context -> same output.
  - No future data permitted beyond draw_context['history'].
  - SHA256 provenance fingerprint included in module.

P127 source: outputs/replay/p127_adapter_build_specs_remaining_multi_bet_20260528.json
P128 task_id: P128
"""
from __future__ import annotations

import hashlib
import math
import sys
import logging
import numpy as np
from collections import Counter
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ─── SHA256 provenance fingerprint ────────────────────────────────────────────
# Computed from: P128 task_id + P127 classification + strategy_ids (priority 1-6)
_PROVENANCE_INPUT = (
    "P128|P127_ADAPTER_BUILD_SPECS_READY|"
    "midfreq_acb_2bet|midfreq_fourier_2bet|zonal_entropy_2bet|"
    "cold_complement_2bet|midfreq_fourier_2bet|fourier30_markov30_2bet"
)
PROVENANCE_SHA256: str = hashlib.sha256(_PROVENANCE_INPUT.encode()).hexdigest()

# ─── Phase 1 strategy manifest ────────────────────────────────────────────────

PHASE1_STRATEGIES: list[dict] = [
    {"priority": 1, "strategy_id": "midfreq_acb_2bet",        "lottery_type": "DAILY_539",    "bet_count": 2, "function": "get_all_bets_midfreq_acb"},
    {"priority": 2, "strategy_id": "midfreq_fourier_2bet",    "lottery_type": "DAILY_539",    "bet_count": 2, "function": "get_all_bets_fourier_d539"},
    {"priority": 3, "strategy_id": "zonal_entropy_2bet",      "lottery_type": "POWER_LOTTO",  "bet_count": 2, "function": "get_all_bets_zonal_entropy"},
    {"priority": 4, "strategy_id": "cold_complement_2bet",    "lottery_type": "POWER_LOTTO",  "bet_count": 2, "function": "get_all_bets_cold_complement"},
    {"priority": 5, "strategy_id": "midfreq_fourier_2bet",    "lottery_type": "POWER_LOTTO",  "bet_count": 2, "function": "get_all_bets_fourier_power"},
    {"priority": 6, "strategy_id": "fourier30_markov30_2bet", "lottery_type": "POWER_LOTTO",  "bet_count": 2, "function": "get_all_bets_fourier30_markov30"},
]

# ─── Pool / pick constants ─────────────────────────────────────────────────────

# DAILY_539
_D539_POOL = 39
_D539_PICK = 5
_D539_MIDFREQ_WINDOW = 100
_D539_ACB_WINDOW = 100
_D539_FOURIER_WINDOW = 100

# POWER_LOTTO
_PL_POOL = 38
_PL_PICK = 6
_PL_SPECIAL_POOL = 8
_PL_MIDFREQ_WINDOW = 100
_PL_FOURIER_WINDOW = 500
_PL_COLD_WINDOW = 100
_PL_F30_WINDOW = 30
_PL_M30_WINDOW = 30
_PL_ZONE_WINDOW = 30
_PL_ZONE_COLD_WINDOW = 100
_PL_ENTROPY_CHAOS_THRESHOLD = 2.2  # bits; log2(8) ≈ 3.0


# ══════════════════════════════════════════════════════════════════════════════
# DAILY_539 helper functions
# ══════════════════════════════════════════════════════════════════════════════

def _d539_midfreq_scores(history: List[dict], window: int = _D539_MIDFREQ_WINDOW) -> dict:
    """
    MidFreq (mean-reversion) scores for DAILY_539 pool (1..39).

    score = -(|actual_count - expected_count|)
    Numbers closest to expected frequency score highest (closest to 0).
    Tie-break: lower number preferred when scores are equal.
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w == 0:
        return {n: 0.0 for n in range(1, _D539_POOL + 1)}
    expected = w * _D539_PICK / _D539_POOL
    freq: Counter = Counter()
    for d in recent:
        for num in d.get("numbers", []):
            if 1 <= num <= _D539_POOL:
                freq[num] += 1
    return {num: -abs(freq.get(num, 0) - expected) for num in range(1, _D539_POOL + 1)}


def _d539_acb_scores(history: List[dict], window: int = _D539_ACB_WINDOW) -> dict:
    """
    ACB (Anomaly Capture Bet) scores for DAILY_539 pool (1..39).

    score = (expected_count - actual_count) / sigma
    Positive score = underrepresented = ACB candidate (anomaly).
    Mirrors p31a_wave1_retired_adapters._acb_scores() semantics.
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w == 0:
        return {n: 0.0 for n in range(1, _D539_POOL + 1)}

    p = _D539_PICK / _D539_POOL
    expected = w * p
    var = w * p * (1.0 - p)
    sigma = var ** 0.5 if var > 0 else 1.0

    freq: Counter = Counter()
    for d in recent:
        for num in d.get("numbers", []):
            if 1 <= num <= _D539_POOL:
                freq[num] += 1

    return {num: (expected - freq.get(num, 0)) / sigma for num in range(1, _D539_POOL + 1)}


def _d539_fourier_scores(history: List[dict], window: int = _D539_FOURIER_WINDOW) -> dict:
    """
    Fourier rhythm scores for DAILY_539 pool (1..39).

    FFT period detection: score = 1 / (|gap - period| + 1).
    Numbers whose dominant FFT period aligns with current gap score highest.
    Mirrors p36_wave2_daily539_adapters._fourier_scores().
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w < 10:
        return {n: 0.0 for n in range(1, _D539_POOL + 1)}

    scores: dict = {}
    for num in range(1, _D539_POOL + 1):
        series = np.array(
            [1 if num in d.get("numbers", []) else 0 for d in recent],
            dtype=float,
        )
        if series.sum() < 2:
            scores[num] = 0.0
            continue
        yf = np.fft.rfft(series - series.mean())
        power = np.abs(yf) ** 2
        if len(power) <= 1:
            scores[num] = 0.0
            continue
        dominant_idx = int(np.argmax(power[1:])) + 1
        freq_val = dominant_idx / w
        if freq_val == 0:
            scores[num] = 0.0
            continue
        period = 1.0 / freq_val
        last_hit_arr = np.where(series == 1)[0]
        last_hit = int(last_hit_arr[-1]) if len(last_hit_arr) > 0 else -1
        gap = (w - 1) - last_hit
        scores[num] = 1.0 / (abs(gap - period) + 1.0)

    return scores


def _d539_top_n(scores: dict, n: int) -> List[int]:
    """Return top-n DAILY_539 numbers by score, tie-break by number ASC."""
    ranked = sorted(range(1, _D539_POOL + 1), key=lambda num: (-scores.get(num, 0.0), num))
    return sorted(ranked[:n])


# ══════════════════════════════════════════════════════════════════════════════
# POWER_LOTTO helper functions
# ══════════════════════════════════════════════════════════════════════════════

def _pl_midfreq_scores(history: List[dict], window: int = _PL_MIDFREQ_WINDOW) -> dict:
    """
    MidFreq (mean-reversion) scores for POWER_LOTTO pool (1..38).

    score = -(|actual_count - expected_count|)
    Mirrors p47_wave4_powerlotto_adapters._midfreq_scores().
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w == 0:
        return {n: 0.0 for n in range(1, _PL_POOL + 1)}
    expected = w * _PL_PICK / _PL_POOL
    freq: Counter = Counter()
    for d in recent:
        for num in d.get("numbers", []):
            if 1 <= num <= _PL_POOL:
                freq[num] += 1
    return {num: -abs(freq.get(num, 0) - expected) for num in range(1, _PL_POOL + 1)}


def _pl_fourier_scores(history: List[dict], window: int = _PL_FOURIER_WINDOW) -> dict:
    """
    Fourier rhythm scores for POWER_LOTTO pool (1..38).

    FFT period detection: score = 1 / (|gap - period| + 1).
    Mirrors p47_wave4_powerlotto_adapters._fourier_scores().
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w < 10:
        return {n: 0.0 for n in range(1, _PL_POOL + 1)}

    scores: dict = {}
    for num in range(1, _PL_POOL + 1):
        series = np.array(
            [1 if num in d.get("numbers", []) else 0 for d in recent],
            dtype=float,
        )
        if series.sum() < 2:
            scores[num] = 0.0
            continue
        yf = np.fft.rfft(series - series.mean())
        power = np.abs(yf) ** 2
        if len(power) <= 1:
            scores[num] = 0.0
            continue
        dominant_idx = int(np.argmax(power[1:])) + 1
        freq_val = dominant_idx / w
        if freq_val == 0:
            scores[num] = 0.0
            continue
        period = 1.0 / freq_val
        last_hit_arr = np.where(series == 1)[0]
        last_hit = int(last_hit_arr[-1]) if len(last_hit_arr) > 0 else -1
        gap = (w - 1) - last_hit
        scores[num] = 1.0 / (abs(gap - period) + 1.0)

    return scores


def _pl_markov30_scores(history: List[dict], window: int = _PL_M30_WINDOW) -> np.ndarray:
    """
    Markov transition scores for POWER_LOTTO pool (1..38), window=30.

    Returns np.ndarray of shape (38,): transition probability sums from last draw.
    Mirrors p47_wave4_powerlotto_adapters._markov_scores() with window=30.
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 2:
        return np.ones(_PL_POOL)

    transition = np.zeros((_PL_POOL, _PL_POOL))
    for i in range(len(recent) - 1):
        for a in recent[i].get("numbers", []):
            if 1 <= a <= _PL_POOL:
                for b in recent[i + 1].get("numbers", []):
                    if 1 <= b <= _PL_POOL:
                        transition[a - 1][b - 1] += 1

    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    transition = transition / row_sums

    last_nums = recent[-1].get("numbers", [])
    scores = np.zeros(_PL_POOL)
    for num in last_nums:
        if 1 <= num <= _PL_POOL:
            scores += transition[num - 1]

    return scores


def _pl_top_n_dict(scores: dict, n: int) -> List[int]:
    """Return top-n POWER_LOTTO numbers from dict scores, tie-break by num ASC."""
    ranked = sorted(range(1, _PL_POOL + 1), key=lambda num: (-scores.get(num, 0.0), num))
    return sorted(ranked[:n])


def _pl_top_n_arr(scores_arr: np.ndarray, n: int) -> List[int]:
    """Return top-n POWER_LOTTO numbers from numpy array (1-indexed), tie-break by num ASC."""
    indexed = sorted(range(1, _PL_POOL + 1), key=lambda num: (-float(scores_arr[num - 1]), num))
    return sorted(indexed[:n])


def _pl_get_zone(num: int) -> int:
    """Map POWER_LOTTO number (1..38) to zone (0..7)."""
    if num > 35:
        return 7
    return (num - 1) // 5


def _pl_zone_entropy(history: List[dict], window: int = _PL_ZONE_WINDOW) -> float:
    """Shannon entropy of zone distribution over last `window` draws."""
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return 0.0

    zone_counts: Counter = Counter()
    for d in recent:
        for num in d.get("numbers", []):
            if 1 <= num <= _PL_POOL:
                zone_counts[_pl_get_zone(num)] += 1

    total = sum(zone_counts.values())
    if total == 0:
        return 0.0

    entropy = 0.0
    for count in zone_counts.values():
        p = count / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


# ══════════════════════════════════════════════════════════════════════════════
# P1: midfreq_acb_2bet  (DAILY_539)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_midfreq_acb(draw_context: dict) -> list[list[int]]:
    """
    Returns 2 bet combinations for midfreq_acb_2bet (DAILY_539).

    bet-1 (bet_index=1): MidFreq top-5 — numbers closest to expected frequency.
    bet-2 (bet_index=2): ACB top-5 — most underrepresented numbers (anomaly).

    Both bets are derived from separate, orthogonal signals.
    Tie-break: number ASC (lower number preferred at equal score).

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'DAILY_539',
        }

    Returns:
        [[bet1_num1, ..., bet1_num5], [bet2_num1, ..., bet2_num5]]
        Each inner list: 5 sorted unique ints in [1..39].
    """
    history = draw_context["history"]

    mf_scores = _d539_midfreq_scores(history)
    acb_scores = _d539_acb_scores(history)

    bet1 = _d539_top_n(mf_scores, _D539_PICK)
    bet2 = _d539_top_n(acb_scores, _D539_PICK)

    return [bet1, bet2]


# ══════════════════════════════════════════════════════════════════════════════
# P2: midfreq_fourier_2bet  (DAILY_539)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_fourier_d539(draw_context: dict) -> list[list[int]]:
    """
    Returns 2 bet combinations for midfreq_fourier_2bet (DAILY_539).

    bet-1 (bet_index=1): MidFreq top-5 — numbers closest to expected frequency.
    bet-2 (bet_index=2): Fourier top-5 — strongest FFT rhythm alignment.

    Both bets are derived from separate, orthogonal signals.
    Tie-break: number ASC.

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'DAILY_539',
        }

    Returns:
        [[bet1_num1, ..., bet1_num5], [bet2_num1, ..., bet2_num5]]
        Each inner list: 5 sorted unique ints in [1..39].
    """
    history = draw_context["history"]

    mf_scores = _d539_midfreq_scores(history)
    fo_scores = _d539_fourier_scores(history)

    bet1 = _d539_top_n(mf_scores, _D539_PICK)
    bet2 = _d539_top_n(fo_scores, _D539_PICK)

    return [bet1, bet2]


# ══════════════════════════════════════════════════════════════════════════════
# P3: zonal_entropy_2bet  (POWER_LOTTO)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_zonal_entropy(draw_context: dict) -> list[list[int]]:
    """
    Returns 2 bet combinations for zonal_entropy_2bet (POWER_LOTTO).

    Regime detection: Shannon entropy of zone distribution (8 zones, window=30).
      entropy > 2.2 bits → chaotic regime
      entropy ≤ 2.2 bits → stable regime

    bet-1 (bet_index=1): Entropy-adaptive primary prediction.
      Chaotic: cold numbers (reversion, window=100).
      Stable:  hot numbers (momentum, window=30).

    bet-2 (bet_index=2): Opposite-regime diversification.
      Chaotic bet-1 → bet-2 uses hot (window=30).
      Stable  bet-1 → bet-2 uses cold (window=100).

    This maximizes coverage: bet-1 follows current regime, bet-2 hedges.
    Tie-break: number ASC.

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[bet1_num1, ..., bet1_num6], [bet2_num1, ..., bet2_num6]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]

    entropy = _pl_zone_entropy(history, window=_PL_ZONE_WINDOW)
    is_chaotic = entropy > _PL_ENTROPY_CHAOS_THRESHOLD

    def _cold_top6(hist: List[dict], window: int) -> List[int]:
        recent = hist[-window:] if len(hist) >= window else hist
        freq: Counter = Counter()
        for d in recent:
            for num in d.get("numbers", []):
                if 1 <= num <= _PL_POOL:
                    freq[num] += 1
        ranked = sorted(range(1, _PL_POOL + 1), key=lambda n: (freq.get(n, 0), n))
        return sorted(ranked[:_PL_PICK])

    def _hot_top6(hist: List[dict], window: int) -> List[int]:
        recent = hist[-window:] if len(hist) >= window else hist
        freq: Counter = Counter()
        for d in recent:
            for num in d.get("numbers", []):
                if 1 <= num <= _PL_POOL:
                    freq[num] += 1
        ranked = sorted(range(1, _PL_POOL + 1), key=lambda n: (-freq.get(n, 0), n))
        return sorted(ranked[:_PL_PICK])

    if is_chaotic:
        bet1 = _cold_top6(history, _PL_ZONE_COLD_WINDOW)
        bet2 = _hot_top6(history, _PL_ZONE_WINDOW)
    else:
        bet1 = _hot_top6(history, _PL_ZONE_WINDOW)
        bet2 = _cold_top6(history, _PL_ZONE_COLD_WINDOW)

    return [bet1, bet2]


# ══════════════════════════════════════════════════════════════════════════════
# P4: cold_complement_2bet  (POWER_LOTTO)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_cold_complement(draw_context: dict) -> list[list[int]]:
    """
    Returns 2 bet combinations for cold_complement_2bet (POWER_LOTTO).

    bet-1 (bet_index=1): Cold top-6 — 6 numbers with LOWEST frequency over 100 draws.
                         Reversion hypothesis: underrepresented numbers converge.
    bet-2 (bet_index=2): Hot complement — 6 numbers with HIGHEST frequency over 100 draws.
                         Momentum hypothesis: frequently drawn numbers continue.

    Cold and Hot are computed from the same window for direct comparison.
    Tie-break: number ASC at equal frequency.

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[bet1_num1, ..., bet1_num6], [bet2_num1, ..., bet2_num6]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]
    recent = history[-_PL_COLD_WINDOW:] if len(history) >= _PL_COLD_WINDOW else history

    freq: Counter = Counter()
    for d in recent:
        for num in d.get("numbers", []):
            if 1 <= num <= _PL_POOL:
                freq[num] += 1

    # bet-1: Cold — lowest frequency, tie-break num ASC
    cold_ranked = sorted(range(1, _PL_POOL + 1), key=lambda n: (freq.get(n, 0), n))
    bet1 = sorted(cold_ranked[:_PL_PICK])

    # bet-2: Hot — highest frequency, tie-break num ASC
    hot_ranked = sorted(range(1, _PL_POOL + 1), key=lambda n: (-freq.get(n, 0), n))
    bet2 = sorted(hot_ranked[:_PL_PICK])

    return [bet1, bet2]


# ══════════════════════════════════════════════════════════════════════════════
# P5: midfreq_fourier_2bet  (POWER_LOTTO)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_fourier_power(draw_context: dict) -> list[list[int]]:
    """
    Returns 2 bet combinations for midfreq_fourier_2bet (POWER_LOTTO).

    bet-1 (bet_index=1): MidFreq+Fourier orthogonal intersection.
      Top-20 MidFreq ∩ Top-20 Fourier, pick 6 from intersection.
      Supplement from MidFreq top-20 remainder if intersection < 6.

    bet-2 (bet_index=2): Pure Fourier top-6.
      Top-6 by highest FFT rhythm score (window=500).
      Supplement from MidFreq remainder if Fourier pool insufficient.

    Tie-break: number ASC at equal score.

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[bet1_num1, ..., bet1_num6], [bet2_num1, ..., bet2_num6]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]

    mf = _pl_midfreq_scores(history, window=_PL_MIDFREQ_WINDOW)
    fo = _pl_fourier_scores(history, window=_PL_FOURIER_WINDOW)

    mf_ranked = sorted(range(1, _PL_POOL + 1), key=lambda n: (-mf[n], n))
    fo_ranked = sorted(range(1, _PL_POOL + 1), key=lambda n: (-fo[n], n))

    mf_top20 = set(mf_ranked[:20])
    fo_top20 = set(fo_ranked[:20])

    # bet-1: MidFreq+Fourier intersection (top-6 from agreement set)
    intersect = sorted(mf_top20 & fo_top20, key=lambda n: -(mf[n] + fo[n]))
    if len(intersect) >= _PL_PICK:
        bet1 = sorted(intersect[:_PL_PICK])
    else:
        supplement = [n for n in mf_ranked if n not in set(intersect)]
        bet1 = sorted((intersect + supplement)[:_PL_PICK])

    # bet-2: Pure Fourier top-6
    bet2 = sorted(fo_ranked[:_PL_PICK])

    return [bet1, bet2]


# ══════════════════════════════════════════════════════════════════════════════
# P6: fourier30_markov30_2bet  (POWER_LOTTO)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_fourier30_markov30(draw_context: dict) -> list[list[int]]:
    """
    Returns 2 bet combinations for fourier30_markov30_2bet (POWER_LOTTO).

    bet-1 (bet_index=1): Fourier30 top-6.
      Weighted recency frequency over 30 draws.
      Weight(i) = 1 + 2*(i/n), linearly from 1.0 (oldest) to 3.0 (newest).
      Top-6 by weighted frequency, tie-break num ASC.

    bet-2 (bet_index=2): Markov30 top-6.
      Markov transition matrix over 30 draws.
      Scores = sum of transition probabilities from last draw's numbers.
      Top-6 by Markov score, tie-break num ASC.

    RSR-7 note: This strategy has 1501 DB rows (expected 1500 for bet_index=1).
                The 1 extra row is low priority and does NOT block this adapter.

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[bet1_num1, ..., bet1_num6], [bet2_num1, ..., bet2_num6]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]

    # bet-1: Fourier30 (weighted recency frequency)
    recent_f30 = history[-_PL_F30_WINDOW:] if len(history) >= _PL_F30_WINDOW else history
    n_f30 = len(recent_f30)

    if n_f30 == 0:
        bet1 = list(range(1, _PL_PICK + 1))  # fallback: first 6
    else:
        weighted_freq: Counter = Counter()
        for i, draw in enumerate(recent_f30):
            # Linearly increasing weight: 1.0 (oldest) → 3.0 (newest)
            weight = 1.0 + 2.0 * (i / n_f30)
            for num in draw.get("numbers", []):
                if 1 <= num <= _PL_POOL:
                    weighted_freq[num] += weight

        wf_ranked = sorted(range(1, _PL_POOL + 1), key=lambda n: (-weighted_freq.get(n, 0.0), n))
        bet1 = sorted(wf_ranked[:_PL_PICK])

    # bet-2: Markov30 (transition probability sums from last draw)
    markov_arr = _pl_markov30_scores(history, window=_PL_M30_WINDOW)
    bet2 = _pl_top_n_arr(markov_arr, _PL_PICK)

    return [bet1, bet2]


# ══════════════════════════════════════════════════════════════════════════════
# Unified dispatch + validation
# ══════════════════════════════════════════════════════════════════════════════

# Dispatch key: (strategy_id, lottery_type) -> function
# Note: 'midfreq_fourier_2bet' appears in both DAILY_539 and POWER_LOTTO.
# Disambiguation: use draw_context['lottery_type'].
_DISPATCH: dict = {
    ("midfreq_acb_2bet",        "DAILY_539"):    get_all_bets_midfreq_acb,
    ("midfreq_fourier_2bet",    "DAILY_539"):    get_all_bets_fourier_d539,
    ("zonal_entropy_2bet",      "POWER_LOTTO"):  get_all_bets_zonal_entropy,
    ("cold_complement_2bet",    "POWER_LOTTO"):  get_all_bets_cold_complement,
    ("midfreq_fourier_2bet",    "POWER_LOTTO"):  get_all_bets_fourier_power,
    ("fourier30_markov30_2bet", "POWER_LOTTO"):  get_all_bets_fourier30_markov30,
}

# All 6 dispatch keys in priority order (for validation loops)
DISPATCH_KEYS_ORDERED: list[tuple[str, str]] = [
    ("midfreq_acb_2bet",        "DAILY_539"),
    ("midfreq_fourier_2bet",    "DAILY_539"),
    ("zonal_entropy_2bet",      "POWER_LOTTO"),
    ("cold_complement_2bet",    "POWER_LOTTO"),
    ("midfreq_fourier_2bet",    "POWER_LOTTO"),
    ("fourier30_markov30_2bet", "POWER_LOTTO"),
]


def get_all_bets(strategy_id: str, draw_context: dict) -> list[list[int]]:
    """
    Unified dispatch for P128 Phase 1 get_all_bets().

    draw_context must contain:
      - 'history': list of past draw dicts (each with 'numbers', optionally 'special')
      - 'lottery_type': 'DAILY_539' or 'POWER_LOTTO'

    Returns list[list[int]] — 2 bet combinations, ordered by descending confidence:
      [0] = bet-1 (primary, bet_index=1)
      [1] = bet-2 (secondary, bet_index=2)

    Deterministic: same (strategy_id, draw_context) -> same output.
    No DB write. No future data.

    Raises:
        ValueError: if (strategy_id, lottery_type) key not found.
        AssertionError: if output fails contract validation.
    """
    lottery_type = draw_context.get("lottery_type", "")
    key = (strategy_id, lottery_type)

    if key not in _DISPATCH:
        raise ValueError(
            f"Strategy '{strategy_id}' with lottery_type '{lottery_type}' "
            f"not found in P128 Phase 1. "
            f"Valid keys: {list(_DISPATCH.keys())}"
        )

    fn = _DISPATCH[key]
    bets = fn(draw_context)
    _validate_bets(bets, lottery_type)
    return bets


def _validate_bets(bets: list, lottery_type: str) -> None:
    """
    Validate get_all_bets() output against adapter contract.

    Checks:
      - Returns exactly 2 bets
      - Each bet has correct number of picks
      - All numbers unique within each bet
      - All numbers within valid pool range
      - Numbers sorted ascending within each bet
    """
    assert len(bets) == 2, f"Expected 2 bets, got {len(bets)}"

    if lottery_type == "DAILY_539":
        pool, pick = _D539_POOL, _D539_PICK
    elif lottery_type == "POWER_LOTTO":
        pool, pick = _PL_POOL, _PL_PICK
    else:
        raise AssertionError(f"Unknown lottery_type: {lottery_type!r}")

    for i, bet in enumerate(bets):
        assert len(bet) == pick, (
            f"Bet {i + 1}: expected {pick} numbers, got {len(bet)}: {bet}"
        )
        assert len(set(bet)) == pick, (
            f"Bet {i + 1}: duplicate numbers detected: {bet}"
        )
        assert all(1 <= n <= pool for n in bet), (
            f"Bet {i + 1}: numbers out of range [1..{pool}]: {bet}"
        )
        assert bet == sorted(bet), (
            f"Bet {i + 1}: numbers not sorted ASC: {bet}"
        )
