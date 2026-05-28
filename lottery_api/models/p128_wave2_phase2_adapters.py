"""
p128_wave2_phase2_adapters.py
==============================
P128 Wave 2 Phase 2 — Multi-Bet get_all_bets() Adapters

Implements get_all_bets() for priority 7-12 strategies from P127 spec.

SCOPE BOUNDARIES (P128 Phase 2):
  - ADAPTER-ONLY: No DB writes, no controlled_apply, no replay row insertion.
  - These functions produce list[list[int]] — all N bets for a strategy.
  - No lifecycle mutation, no registry change.
  - production_db_rows_after = 72462 (unchanged from P128 Phase 1 baseline).

Strategies implemented (priority 7-12):
  P7:  acb_markov_midfreq_3bet  (DAILY_539)    bet-1=ACB,            bet-2=Markov, bet-3=MidFreq
  P8:  midfreq_fourier_mk_3bet  (POWER_LOTTO)  bet-1=MidFreq,        bet-2=Fourier, bet-3=Markov30
  P9:  fourier_rhythm_3bet      (POWER_LOTTO)  bet-1=Fourier500,     bet-2=Fourier100, bet-3=ACB
  P10: power_precision_3bet     (POWER_LOTTO)  bet-1=MidFreq+Fourier, bet-2=Cold, bet-3=Markov30
       *** RSR-6 FLAGGED: 20 orphan bet_index=2 rows — adapter defined, apply BLOCKED ***
  P11: pp3_freqort_4bet          (POWER_LOTTO)  bet-1=MidFreq, bet-2=Fourier, bet-3=Cold, bet-4=Markov30
  P12: power_orthogonal_5bet    (POWER_LOTTO)  bet-1=MidFreq, bet-2=Fourier, bet-3=Cold, bet-4=Markov30, bet-5=ACB
       *** RSR-6 FLAGGED: 20 orphan bet_index=2 rows — adapter defined, apply BLOCKED ***

RSR-6 status:
  - power_precision_3bet (P10): 20 orphan bet_index=2 rows. Apply BLOCKED until reconciled.
  - power_orthogonal_5bet (P12): 20 orphan bet_index=2 rows. Apply BLOCKED until reconciled.
RSR-7 note: fourier_rhythm_3bet (P9) has 1501 DB rows (expected 1500). Does NOT block adapter.

Governance:
  - No lifecycle/champion/registry mutation.
  - No writes to lottery_api/data/lottery_v2.db.
  - Deterministic: same draw_context -> same output.
  - No future data permitted beyond draw_context['history'].
  - SHA256 provenance fingerprint included in module.

P127 source: outputs/replay/p127_adapter_build_specs_remaining_multi_bet_20260528.json
P128 Phase 1: outputs/replay/p128_wave2_adapter_phase1_20260528.json
P128 task_id: P128_PHASE2
"""
from __future__ import annotations

import hashlib
import math
import sys
import logging
import numpy as np
from collections import Counter
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ─── SHA256 provenance fingerprint ────────────────────────────────────────────
# Computed from: P128_PHASE2 task_id + P127 classification + strategy_ids (priority 7-12)
_PROVENANCE_INPUT = (
    "P128_PHASE2|P127_ADAPTER_BUILD_SPECS_READY|"
    "acb_markov_midfreq_3bet|midfreq_fourier_mk_3bet|fourier_rhythm_3bet|"
    "power_precision_3bet|pp3_freqort_4bet|power_orthogonal_5bet"
)
PROVENANCE_SHA256: str = hashlib.sha256(_PROVENANCE_INPUT.encode()).hexdigest()

# ─── RSR-6 blocked strategy registry ──────────────────────────────────────────
# Strategies that have orphan bet_index=2 rows — must NOT proceed to apply until resolved.
RSR6_BLOCKED_STRATEGIES = frozenset({
    "power_precision_3bet",
    "power_orthogonal_5bet",
})

# ─── Phase 2 strategy manifest ────────────────────────────────────────────────
PHASE2_STRATEGIES: list[dict] = [
    {
        "priority": 7,
        "strategy_id": "acb_markov_midfreq_3bet",
        "lottery_type": "DAILY_539",
        "bet_count": 3,
        "function": "get_all_bets_acb_markov_midfreq",
        "rsr6_blocked": False,
        "rsr7_note": None,
    },
    {
        "priority": 8,
        "strategy_id": "midfreq_fourier_mk_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "function": "get_all_bets_midfreq_fourier_mk",
        "rsr6_blocked": False,
        "rsr7_note": None,
    },
    {
        "priority": 9,
        "strategy_id": "fourier_rhythm_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "function": "get_all_bets_fourier_rhythm",
        "rsr6_blocked": False,
        "rsr7_note": "RSR-7: 1501 rows in DB (+1 extra). Adapter defined. Low priority anomaly.",
    },
    {
        "priority": 10,
        "strategy_id": "power_precision_3bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 3,
        "function": "get_all_bets_power_precision",
        "rsr6_blocked": True,
        "rsr7_note": "RSR-6: 20 orphan bet_index=2 rows. Apply BLOCKED until reconciliation.",
    },
    {
        "priority": 11,
        "strategy_id": "pp3_freqort_4bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 4,
        "function": "get_all_bets_pp3_freqort",
        "rsr6_blocked": False,
        "rsr7_note": None,
    },
    {
        "priority": 12,
        "strategy_id": "power_orthogonal_5bet",
        "lottery_type": "POWER_LOTTO",
        "bet_count": 5,
        "function": "get_all_bets_power_orthogonal",
        "rsr6_blocked": True,
        "rsr7_note": "RSR-6: 20 orphan bet_index=2 rows. Apply BLOCKED until reconciliation.",
    },
]

# ─── Pool / pick constants ─────────────────────────────────────────────────────

# DAILY_539
_D539_POOL = 39
_D539_PICK = 5
_D539_MIDFREQ_WINDOW = 100
_D539_ACB_WINDOW = 100
_D539_MARKOV_WINDOW = 30

# POWER_LOTTO
_PL_POOL = 38
_PL_PICK = 6
_PL_MIDFREQ_WINDOW = 100
_PL_FOURIER_LONG_WINDOW = 500
_PL_FOURIER_SHORT_WINDOW = 100
_PL_COLD_WINDOW = 100
_PL_MARKOV30_WINDOW = 30
_PL_ACB_WINDOW = 100


# ══════════════════════════════════════════════════════════════════════════════
# DAILY_539 helper functions
# ══════════════════════════════════════════════════════════════════════════════

def _d539_acb_scores(history: List[dict], window: int = _D539_ACB_WINDOW) -> dict:
    """
    ACB (Anomaly Capture Bet) scores for DAILY_539 pool (1..39).
    score = (expected - actual) / sigma — positive = underrepresented (ACB candidate).
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


def _d539_midfreq_scores(history: List[dict], window: int = _D539_MIDFREQ_WINDOW) -> dict:
    """
    MidFreq (mean-reversion) scores for DAILY_539 pool (1..39).
    score = -(|actual - expected|): numbers closest to expected freq score highest.
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


def _d539_markov_scores(history: List[dict], window: int = _D539_MARKOV_WINDOW) -> np.ndarray:
    """
    Markov transition scores for DAILY_539 pool (1..39), window=30.
    Returns np.ndarray of shape (39,): transition probability sums from last draw.
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 2:
        return np.ones(_D539_POOL)

    transition = np.zeros((_D539_POOL, _D539_POOL))
    for i in range(len(recent) - 1):
        for a in recent[i].get("numbers", []):
            if 1 <= a <= _D539_POOL:
                for b in recent[i + 1].get("numbers", []):
                    if 1 <= b <= _D539_POOL:
                        transition[a - 1][b - 1] += 1

    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    transition = transition / row_sums

    last_nums = recent[-1].get("numbers", [])
    scores = np.zeros(_D539_POOL)
    for num in last_nums:
        if 1 <= num <= _D539_POOL:
            scores += transition[num - 1]
    return scores


def _d539_top_n(scores: dict, n: int) -> List[int]:
    """Return top-n DAILY_539 numbers by dict score, tie-break by number ASC."""
    ranked = sorted(range(1, _D539_POOL + 1), key=lambda num: (-scores.get(num, 0.0), num))
    return sorted(ranked[:n])


def _d539_top_n_arr(scores_arr: np.ndarray, n: int) -> List[int]:
    """Return top-n DAILY_539 numbers from numpy array (0-indexed internally), tie-break ASC."""
    indexed = sorted(range(1, _D539_POOL + 1), key=lambda num: (-float(scores_arr[num - 1]), num))
    return sorted(indexed[:n])


# ══════════════════════════════════════════════════════════════════════════════
# POWER_LOTTO helper functions
# ══════════════════════════════════════════════════════════════════════════════

def _pl_midfreq_scores(history: List[dict], window: int = _PL_MIDFREQ_WINDOW) -> dict:
    """MidFreq (mean-reversion) scores for POWER_LOTTO pool (1..38)."""
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


def _pl_fourier_scores(history: List[dict], window: int = _PL_FOURIER_LONG_WINDOW) -> dict:
    """
    Fourier rhythm scores for POWER_LOTTO pool (1..38).
    FFT period detection: score = 1 / (|gap - period| + 1).
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


def _pl_acb_scores(history: List[dict], window: int = _PL_ACB_WINDOW) -> dict:
    """
    ACB (Anomaly Capture Bet) scores for POWER_LOTTO pool (1..38).
    score = (expected - actual) / sigma — positive = underrepresented (ACB candidate).
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w == 0:
        return {n: 0.0 for n in range(1, _PL_POOL + 1)}
    p = _PL_PICK / _PL_POOL
    expected = w * p
    var = w * p * (1.0 - p)
    sigma = var ** 0.5 if var > 0 else 1.0
    freq: Counter = Counter()
    for d in recent:
        for num in d.get("numbers", []):
            if 1 <= num <= _PL_POOL:
                freq[num] += 1
    return {num: (expected - freq.get(num, 0)) / sigma for num in range(1, _PL_POOL + 1)}


def _pl_cold_top6(history: List[dict], window: int = _PL_COLD_WINDOW) -> List[int]:
    """POWER_LOTTO cold top-6: lowest frequency numbers over window draws."""
    recent = history[-window:] if len(history) >= window else history
    freq: Counter = Counter()
    for d in recent:
        for num in d.get("numbers", []):
            if 1 <= num <= _PL_POOL:
                freq[num] += 1
    ranked = sorted(range(1, _PL_POOL + 1), key=lambda n: (freq.get(n, 0), n))
    return sorted(ranked[:_PL_PICK])


def _pl_markov30_scores(history: List[dict], window: int = _PL_MARKOV30_WINDOW) -> np.ndarray:
    """
    Markov transition scores for POWER_LOTTO pool (1..38), window=30.
    Returns np.ndarray of shape (38,).
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
    """Return top-n POWER_LOTTO numbers from numpy array (1-indexed), tie-break ASC."""
    indexed = sorted(range(1, _PL_POOL + 1), key=lambda num: (-float(scores_arr[num - 1]), num))
    return sorted(indexed[:n])


def _pl_midfreq_fourier_fusion(
    history: List[dict], n: int = _PL_PICK
) -> Tuple[List[int], List[int]]:
    """
    Shared helper: MidFreq+Fourier intersection fusion + pure Fourier fallback.
    Returns (fusion_bet, fourier_bet).
    fusion_bet: top-20 MidFreq ∩ top-20 Fourier, pick n. Supplement from MidFreq if needed.
    fourier_bet: top-n pure Fourier.
    """
    mf = _pl_midfreq_scores(history)
    fo = _pl_fourier_scores(history)

    mf_top20 = set(
        sorted(range(1, _PL_POOL + 1), key=lambda x: (-mf.get(x, 0.0), x))[:20]
    )
    fo_top20 = set(
        sorted(range(1, _PL_POOL + 1), key=lambda x: (-fo.get(x, 0.0), x))[:20]
    )

    intersection = sorted(mf_top20 & fo_top20, key=lambda x: (-mf.get(x, 0.0), x))
    if len(intersection) >= n:
        fusion = sorted(intersection[:n])
    else:
        # supplement from MidFreq top-20 remainder
        remainder = [x for x in sorted(mf_top20, key=lambda x: (-mf.get(x, 0.0), x)) if x not in set(intersection)]
        fusion = sorted((intersection + remainder)[:n])

    fourier = _pl_top_n_dict(fo, n)
    return fusion, fourier


# ══════════════════════════════════════════════════════════════════════════════
# Dispatch / validation utilities
# ══════════════════════════════════════════════════════════════════════════════

_LOTTERY_CONFIG = {
    "DAILY_539":  {"pool": _D539_POOL, "pick": _D539_PICK},
    "POWER_LOTTO": {"pool": _PL_POOL,  "pick": _PL_PICK},
}

_DISPATCH: dict = {}  # populated after function definitions


def _validate_bets(bets: list, strategy_id: str, lottery_type: str, expected_count: int) -> None:
    """
    Validate bets list from get_all_bets() output.
    Raises ValueError with descriptive message on any violation.
    """
    cfg = _LOTTERY_CONFIG[lottery_type]
    pool = cfg["pool"]
    pick = cfg["pick"]

    if len(bets) != expected_count:
        raise ValueError(
            f"{strategy_id}: expected {expected_count} bets, got {len(bets)}"
        )

    seen_indices: set = set()
    for i, bet in enumerate(bets, start=1):
        if i in seen_indices:
            raise ValueError(f"{strategy_id}: duplicate bet_index {i}")
        seen_indices.add(i)

        if not isinstance(bet, list):
            raise ValueError(f"{strategy_id} bet_index={i}: must be list, got {type(bet)}")
        if len(bet) != pick:
            raise ValueError(
                f"{strategy_id} bet_index={i}: expected {pick} numbers, got {len(bet)}"
            )
        if len(set(bet)) != pick:
            raise ValueError(f"{strategy_id} bet_index={i}: duplicate numbers in bet")
        if sorted(bet) != bet:
            raise ValueError(f"{strategy_id} bet_index={i}: numbers must be sorted ASC")
        for num in bet:
            if not (1 <= num <= pool):
                raise ValueError(
                    f"{strategy_id} bet_index={i}: number {num} out of range [1..{pool}]"
                )


# ══════════════════════════════════════════════════════════════════════════════
# P7: acb_markov_midfreq_3bet  (DAILY_539)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_acb_markov_midfreq(draw_context: dict) -> list[list[int]]:
    """
    Returns 3 bet combinations for acb_markov_midfreq_3bet (DAILY_539).

    bet-1 (bet_index=1): ACB top-5 — most underrepresented numbers.
      (Expected - Actual) / σ over window=100. Anomaly capture strategy.

    bet-2 (bet_index=2): Markov chain top-5 — transition probability from last draw.
      window=30; transition matrix P[a→b], score = sum of outgoing probs from
      last draw's numbers. Numbers most likely to follow last draw score highest.

    bet-3 (bet_index=3): MidFreq top-5 — numbers closest to expected frequency.
      -(|actual - expected|) over window=100. Mean-reversion hedge.

    Three orthogonal signals for maximum coverage:
      ACB (anomaly) | Markov (sequential) | MidFreq (mean-reversion).

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'DAILY_539',
        }

    Returns:
        [[b1_1..b1_5], [b2_1..b2_5], [b3_1..b3_5]]
        Each inner list: 5 sorted unique ints in [1..39].
    """
    history = draw_context["history"]

    acb = _d539_acb_scores(history)
    mk = _d539_markov_scores(history)
    mf = _d539_midfreq_scores(history)

    bet1 = _d539_top_n(acb, _D539_PICK)
    bet2 = _d539_top_n_arr(mk, _D539_PICK)
    bet3 = _d539_top_n(mf, _D539_PICK)

    return [bet1, bet2, bet3]


# ══════════════════════════════════════════════════════════════════════════════
# P8: midfreq_fourier_mk_3bet  (POWER_LOTTO)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_midfreq_fourier_mk(draw_context: dict) -> list[list[int]]:
    """
    Returns 3 bet combinations for midfreq_fourier_mk_3bet (POWER_LOTTO).

    bet-1 (bet_index=1): MidFreq top-6 — numbers closest to expected frequency.
      -(|actual - expected|) over window=100.

    bet-2 (bet_index=2): Fourier rhythm top-6 — dominant FFT period alignment.
      score = 1 / (|gap - period| + 1), window=500.

    bet-3 (bet_index=3): Markov30 top-6 — transition probability from last draw.
      window=30 transition matrix; numbers most likely to follow last draw.

    Three orthogonal signals: MidFreq (mean) | Fourier (rhythm) | Markov (sequence).

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[b1_1..b1_6], [b2_1..b2_6], [b3_1..b3_6]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]

    mf = _pl_midfreq_scores(history)
    fo = _pl_fourier_scores(history)
    mk = _pl_markov30_scores(history)

    bet1 = _pl_top_n_dict(mf, _PL_PICK)
    bet2 = _pl_top_n_dict(fo, _PL_PICK)
    bet3 = _pl_top_n_arr(mk, _PL_PICK)

    return [bet1, bet2, bet3]


# ══════════════════════════════════════════════════════════════════════════════
# P9: fourier_rhythm_3bet  (POWER_LOTTO) [RSR-7: 1501 rows]
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_fourier_rhythm(draw_context: dict) -> list[list[int]]:
    """
    Returns 3 bet combinations for fourier_rhythm_3bet (POWER_LOTTO).

    RSR-7 NOTE: This strategy has 1501 rows in the DB (expected 1500, +1 extra).
    Adapter implementation is NOT blocked by RSR-7. Low priority anomaly.

    bet-1 (bet_index=1): Fourier long-window top-6 — primary rhythm signal.
      FFT analysis over window=500 draws. Highest dominant-period alignment.

    bet-2 (bet_index=2): Fourier short-window top-6 — near-term rhythm variant.
      FFT analysis over window=100 draws. Captures recent phase shifts.

    bet-3 (bet_index=3): ACB top-6 — anomaly hedge.
      (Expected - Actual) / σ over window=100. Orthogonal reversion signal.

    Two Fourier windows + one ACB hedge for spectrum coverage.

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[b1_1..b1_6], [b2_1..b2_6], [b3_1..b3_6]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]

    fo_long  = _pl_fourier_scores(history, window=_PL_FOURIER_LONG_WINDOW)
    fo_short = _pl_fourier_scores(history, window=_PL_FOURIER_SHORT_WINDOW)
    acb      = _pl_acb_scores(history)

    bet1 = _pl_top_n_dict(fo_long,  _PL_PICK)
    bet2 = _pl_top_n_dict(fo_short, _PL_PICK)
    bet3 = _pl_top_n_dict(acb,      _PL_PICK)

    return [bet1, bet2, bet3]


# ══════════════════════════════════════════════════════════════════════════════
# P10: power_precision_3bet  (POWER_LOTTO) [RSR-6 FLAGGED]
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_power_precision(draw_context: dict) -> list[list[int]]:
    """
    Returns 3 bet combinations for power_precision_3bet (POWER_LOTTO).

    *** RSR-6 WARNING ***
    DB has 20 orphan bet_index=2 rows for this strategy.
    This adapter is defined for FORWARD USE ONLY.
    controlled_apply of bet_index=2 rows is BLOCKED until RSR-6 reconciliation:
      - Audit the 20 orphan bet_index=2 rows (draws 99000085–99000094 range)
      - Determine provenance: are they legacy pre-schema test rows?
      - Quarantine or delete the 20 orphans before adding new bet_index≥2 rows.
    Apply gate status: BLOCKED for bet_index≥2.
    *** END RSR-6 WARNING ***

    bet-1 (bet_index=1): MidFreq+Fourier fusion top-6.
      Top-20 MidFreq ∩ Top-20 Fourier, pick 6 from intersection.
      Supplement from MidFreq top-20 if intersection < 6.

    bet-2 (bet_index=2): Cold reversion top-6.
      Lowest frequency numbers over window=100 draws.
      *** APPLY BLOCKED until RSR-6 resolved ***

    bet-3 (bet_index=3): Markov30 top-6.
      Transition probability from last draw, window=30.

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[b1_1..b1_6], [b2_1..b2_6], [b3_1..b3_6]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]

    fusion, _ = _pl_midfreq_fourier_fusion(history)
    cold = _pl_cold_top6(history)
    mk   = _pl_markov30_scores(history)

    bet1 = fusion
    bet2 = cold
    bet3 = _pl_top_n_arr(mk, _PL_PICK)

    return [bet1, bet2, bet3]


# ══════════════════════════════════════════════════════════════════════════════
# P11: pp3_freqort_4bet  (POWER_LOTTO)
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_pp3_freqort(draw_context: dict) -> list[list[int]]:
    """
    Returns 4 bet combinations for pp3_freqort_4bet (POWER_LOTTO).

    "pp3_freqort" = Power-Precision-3 + Frequency-Orthogonal approach.
    Four maximally orthogonal signals covering the signal space:

    bet-1 (bet_index=1): MidFreq top-6 — mean reversion (window=100).
    bet-2 (bet_index=2): Fourier rhythm top-6 — dominant FFT period (window=500).
    bet-3 (bet_index=3): Cold reversion top-6 — lowest frequency (window=100).
    bet-4 (bet_index=4): Markov30 top-6 — transition from last draw (window=30).

    Four orthogonal signals for 4-bet full coverage:
      MidFreq (mean) | Fourier (rhythm) | Cold (reversion) | Markov (sequence).

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[b1..], [b2..], [b3..], [b4..]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]

    mf   = _pl_midfreq_scores(history)
    fo   = _pl_fourier_scores(history)
    cold = _pl_cold_top6(history)
    mk   = _pl_markov30_scores(history)

    bet1 = _pl_top_n_dict(mf, _PL_PICK)
    bet2 = _pl_top_n_dict(fo, _PL_PICK)
    bet3 = cold
    bet4 = _pl_top_n_arr(mk, _PL_PICK)

    return [bet1, bet2, bet3, bet4]


# ══════════════════════════════════════════════════════════════════════════════
# P12: power_orthogonal_5bet  (POWER_LOTTO) [RSR-6 FLAGGED]
# ══════════════════════════════════════════════════════════════════════════════

def get_all_bets_power_orthogonal(draw_context: dict) -> list[list[int]]:
    """
    Returns 5 bet combinations for power_orthogonal_5bet (POWER_LOTTO).

    *** RSR-6 WARNING ***
    DB has 20 orphan bet_index=2 rows for this strategy.
    This adapter is defined for FORWARD USE ONLY.
    controlled_apply of bet_index=2 rows is BLOCKED until RSR-6 reconciliation:
      - Audit the 20 orphan bet_index=2 rows
      - Quarantine or delete the 20 orphans before adding new bet_index≥2 rows.
    Apply gate status: BLOCKED for bet_index≥2.
    *** END RSR-6 WARNING ***

    Five maximally orthogonal signals spanning the full prediction space:

    bet-1 (bet_index=1): MidFreq top-6 — mean reversion (window=100).
    bet-2 (bet_index=2): Fourier rhythm top-6 — FFT dominant period (window=500).
      *** APPLY BLOCKED for bet_index=2 until RSR-6 resolved ***
    bet-3 (bet_index=3): Cold reversion top-6 — lowest frequency (window=100).
    bet-4 (bet_index=4): Markov30 top-6 — transition from last draw (window=30).
    bet-5 (bet_index=5): ACB top-6 — anomaly capture (window=100).

    Five orthogonal signals: MidFreq | Fourier | Cold | Markov | ACB.

    Deterministic: same draw_context -> same output.
    No DB write. No future data.

    Args:
        draw_context: {
            'history': list[dict]  — draws before target, each with 'numbers',
            'lottery_type': 'POWER_LOTTO',
        }

    Returns:
        [[b1..], [b2..], [b3..], [b4..], [b5..]]
        Each inner list: 6 sorted unique ints in [1..38].
    """
    history = draw_context["history"]

    mf   = _pl_midfreq_scores(history)
    fo   = _pl_fourier_scores(history)
    cold = _pl_cold_top6(history)
    mk   = _pl_markov30_scores(history)
    acb  = _pl_acb_scores(history)

    bet1 = _pl_top_n_dict(mf,  _PL_PICK)
    bet2 = _pl_top_n_dict(fo,  _PL_PICK)
    bet3 = cold
    bet4 = _pl_top_n_arr(mk,   _PL_PICK)
    bet5 = _pl_top_n_dict(acb, _PL_PICK)

    return [bet1, bet2, bet3, bet4, bet5]


# ══════════════════════════════════════════════════════════════════════════════
# Unified dispatch
# ══════════════════════════════════════════════════════════════════════════════

_DISPATCH: dict = {
    ("acb_markov_midfreq_3bet",  "DAILY_539"):    (get_all_bets_acb_markov_midfreq, 3),
    ("midfreq_fourier_mk_3bet",  "POWER_LOTTO"):  (get_all_bets_midfreq_fourier_mk, 3),
    ("fourier_rhythm_3bet",      "POWER_LOTTO"):  (get_all_bets_fourier_rhythm,     3),
    ("power_precision_3bet",     "POWER_LOTTO"):  (get_all_bets_power_precision,    3),
    ("pp3_freqort_4bet",         "POWER_LOTTO"):  (get_all_bets_pp3_freqort,        4),
    ("power_orthogonal_5bet",    "POWER_LOTTO"):  (get_all_bets_power_orthogonal,   5),
}

DISPATCH_KEYS_ORDERED: list[tuple] = [
    ("acb_markov_midfreq_3bet",  "DAILY_539"),
    ("midfreq_fourier_mk_3bet",  "POWER_LOTTO"),
    ("fourier_rhythm_3bet",      "POWER_LOTTO"),
    ("power_precision_3bet",     "POWER_LOTTO"),
    ("pp3_freqort_4bet",         "POWER_LOTTO"),
    ("power_orthogonal_5bet",    "POWER_LOTTO"),
]


def get_all_bets(strategy_id: str, draw_context: dict) -> list[list[int]]:
    """
    Unified dispatch for all Phase 2 strategy get_all_bets() adapters.

    Args:
        strategy_id:   e.g. 'acb_markov_midfreq_3bet'
        draw_context:  {'history': list[dict], 'lottery_type': str}

    Returns:
        list[list[int]] — N bets (N = strategy target_bet_count)
        Each inner list: pick-count sorted unique ints in pool range.

    Raises:
        ValueError: unknown strategy_id/lottery_type combo, or bad output.

    NOTE: RSR-6 blocked strategies (power_precision_3bet, power_orthogonal_5bet)
    have adapters defined for FORWARD USE. Apply via controlled_apply is BLOCKED
    until orphan bet_index=2 rows are reconciled.
    """
    lottery_type = draw_context.get("lottery_type", "")
    key = (strategy_id, lottery_type)

    if key not in _DISPATCH:
        raise ValueError(
            f"Unknown Phase 2 strategy: strategy_id={strategy_id!r}, "
            f"lottery_type={lottery_type!r}. "
            f"Valid keys: {list(_DISPATCH.keys())}"
        )

    fn, expected_count = _DISPATCH[key]
    bets = fn(draw_context)
    _validate_bets(bets, strategy_id, lottery_type, expected_count)
    return bets
