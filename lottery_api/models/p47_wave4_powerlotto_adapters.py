"""
p47_wave4_powerlotto_adapters.py
=================================
P47 Wave 4 — POWER_LOTTO Dry-Run Adapter Scaffold

Standalone replay adapter wrappers for the 3 Wave 4 POWER_LOTTO strategies.
These adapters are NOT registered in replay_strategy_registry._ALL_ADAPTERS
or _REGISTRY. They exist exclusively for P47 temp-DB dry-run rehearsal.

POWER_LOTTO specifics:
  - First zone pool: 1-38, pick 6 per bet
  - Second zone (special): 1-8, pick 1
  - predicted_numbers: 6 unique ints in [1, 38]
  - predicted_special: 1 int in [1, 8]
  - hit_count: FIRST-ZONE ONLY (do NOT count special)
  - special_hit: 1 if predicted_special == actual_special, else 0
  - Lifecycle: DRY_RUN

HARD RULES (same as p42 BIG_LOTTO pattern):
  - history MUST be all draws STRICTLY BEFORE the target draw (causal slice).
  - Adapters MUST NOT read external state (DB, files, env) during prediction.
  - Only one bet is recorded per (strategy, draw) pair.
  - Each bet must have exactly 6 distinct integers in range [1..38].
  - predicted_special must be in range [1..8].

LIFECYCLE NOTE:
  All 3 strategies have lifecycle_status=DRY_RUN (not ONLINE, not RETIRED).
  Dry-run rows go ONLY to /tmp/p47_temp_rehearsal.db — never to lottery_v2.db.

Wave 4 Strategies (from P46 expansion planning):
  pp3_freqort_4bet          — PP3+FreqOrt 4注 bet-1 (Fourier rhythm, window=500)
  midfreq_fourier_mk_3bet   — MidFreq+Fourier+Markov 3注 bet-1 (composite)
  midfreq_fourier_2bet      — MidFreq+Fourier 2注 bet-1 (orthogonal)

Reference: lottery_api/models/p42_wave3_biglotto_adapters.py (BIG_LOTTO pattern)
P46 planning: outputs/replay/p46_powerlotto_expansion_planning_20260524.json
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

_POOL = 38       # POWER_LOTTO first-zone pool 1..38
_PICK = 6        # numbers per bet (first zone)
_SPECIAL_POOL = 8  # POWER_LOTTO second-zone pool 1..8
_MIDFREQ_WINDOW = 100
_MARKOV_WINDOW = 30
_FOURIER_WINDOW = 500

WAVE4_STRATEGY_IDS = frozenset({
    "pp3_freqort_4bet",
    "midfreq_fourier_mk_3bet",
    "midfreq_fourier_2bet",
})

WAVE4_STRATEGY_ID_LIST = [
    "pp3_freqort_4bet",
    "midfreq_fourier_mk_3bet",
    "midfreq_fourier_2bet",
]


# ─── Core algorithm helpers ───────────────────────────────────────────────────

def _fourier_scores(history: List[dict], window: int = _FOURIER_WINDOW) -> dict:
    """
    Compute Fourier rhythm scores for POWER_LOTTO first-zone pool (1..38).

    FFT period detection: score = 1 / (|gap - period| + 1).
    Returns dict: {num: score} for num in 1.._POOL.
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w < 10:
        return {n: 0.0 for n in range(1, _POOL + 1)}

    scores: dict = {}
    for num in range(1, _POOL + 1):
        series = np.array(
            [1 if num in d["numbers"] else 0 for d in recent], dtype=float
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


def _midfreq_scores(history: List[dict], window: int = _MIDFREQ_WINDOW) -> dict:
    """
    Compute MidFreq (mean-reversion) scores for POWER_LOTTO first-zone pool.

    score = -|actual_count - expected_count|
    Numbers closest to expected frequency score highest.

    Returns dict: {num: score} for num in 1.._POOL.
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w == 0:
        return {n: 0.0 for n in range(1, _POOL + 1)}

    expected = w * _PICK / _POOL
    freq: Counter = Counter()
    for d in recent:
        for num in d["numbers"]:
            if 1 <= num <= _POOL:
                freq[num] += 1

    return {num: -abs(freq.get(num, 0) - expected) for num in range(1, _POOL + 1)}


def _markov_scores(history: List[dict], window: int = _MARKOV_WINDOW) -> np.ndarray:
    """
    Compute 1st-order Markov transition scores for POWER_LOTTO pool (indices 0..37).

    Returns np.ndarray of shape (38,) representing next-draw probability scores.
    """
    recent = history[-window:] if len(history) >= window else history
    if len(recent) < 2:
        return np.ones(_POOL)

    transition = np.zeros((_POOL, _POOL))
    for i in range(len(recent) - 1):
        for a in recent[i]["numbers"]:
            for b in recent[i + 1]["numbers"]:
                if 1 <= a <= _POOL and 1 <= b <= _POOL:
                    transition[a - 1][b - 1] += 1

    row_sums = transition.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1.0
    transition = transition / row_sums

    last_nums = [n for n in recent[-1]["numbers"] if 1 <= n <= _POOL]
    if not last_nums:
        return np.ones(_POOL)

    scores = np.zeros(_POOL)
    for num in last_nums:
        scores += transition[num - 1]

    return scores


def _special_predict(history: List[dict], window: int = 100) -> int:
    """
    Predict special number (1..8) using frequency-based mean-reversion.

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
    expected = w / _SPECIAL_POOL  # each special number expected w/8 times

    # Pick the number closest to expected (mean-reversion)
    best = min(range(1, _SPECIAL_POOL + 1), key=lambda n: abs(freq.get(n, 0) - expected))
    return best


# ─── Prediction functions ─────────────────────────────────────────────────────

def predict_pp3_freqort_4bet_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of PP3+FreqOrt 4注 — strategy_id: pp3_freqort_4bet

    Fourier Rhythm top-6 from first-zone pool (1-38), window=500.
    Bet-1 = top Fourier rhythm slice (same as fourier_rhythm_3bet bet-1).
    Replay records bet-1 only.
    """
    scores = _fourier_scores(history, window=_FOURIER_WINDOW)
    ranked = sorted(range(1, _POOL + 1), key=lambda n: -scores[n])
    return sorted(ranked[:_PICK])


def predict_midfreq_fourier_mk_3bet_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of MidFreq+Fourier+Markov 3注 — strategy_id: midfreq_fourier_mk_3bet

    Composite: blend MidFreq(w=100) + Fourier(w=500) + Markov(w=30).
    Weights: MidFreq×0.3 + Fourier×0.4 + Markov×0.3 (per MEMORY.md L83).
    Bet-1 = top-6 by blended score.
    Replay records bet-1 only.
    """
    mf = _midfreq_scores(history, window=_MIDFREQ_WINDOW)
    fo = _fourier_scores(history, window=_FOURIER_WINDOW)
    mk = _markov_scores(history, window=_MARKOV_WINDOW)

    # Normalize each signal to [0, 1] range
    mf_vals = np.array([mf[n] for n in range(1, _POOL + 1)])
    fo_vals = np.array([fo[n] for n in range(1, _POOL + 1)])
    mk_vals = mk  # already 0..1 (transition probs)

    def _normalize(arr: np.ndarray) -> np.ndarray:
        lo, hi = arr.min(), arr.max()
        if hi == lo:
            return np.zeros_like(arr)
        return (arr - lo) / (hi - lo)

    mf_n = _normalize(mf_vals)
    fo_n = _normalize(fo_vals)
    mk_n = _normalize(mk_vals)

    # Composite: MidFreq×0.3 + Fourier×0.4 + Markov×0.3
    blend = 0.3 * mf_n + 0.4 * fo_n + 0.3 * mk_n
    ranked = [int(idx + 1) for idx in np.argsort(-blend)]
    return sorted(ranked[:_PICK])


def predict_midfreq_fourier_2bet_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of MidFreq+Fourier 2注 — strategy_id: midfreq_fourier_2bet

    Orthogonal: MidFreq top-20 ∩ Fourier top-20, pick 6 from intersection.
    If intersection < 6, supplement from MidFreq remainder.
    Replay records bet-1 only.
    """
    mf = _midfreq_scores(history, window=_MIDFREQ_WINDOW)
    fo = _fourier_scores(history, window=_FOURIER_WINDOW)

    mf_ranked = sorted(range(1, _POOL + 1), key=lambda n: -mf[n])
    fo_ranked = sorted(range(1, _POOL + 1), key=lambda n: -fo[n])

    mf_top20 = set(mf_ranked[:20])
    fo_top20 = set(fo_ranked[:20])

    # Intersection: numbers high in both signals
    intersect = sorted(mf_top20 & fo_top20, key=lambda n: -(mf[n] + fo[n]))

    if len(intersect) >= _PICK:
        return sorted(intersect[:_PICK])

    # Supplement from MidFreq top-20 (ordered by combined score)
    supplement = [n for n in mf_ranked if n not in set(intersect)]
    combined = intersect + supplement
    return sorted(combined[:_PICK])


# ─── Adapter class wrappers ───────────────────────────────────────────────────

class _P47AdapterMeta:
    """Lightweight metadata holder for P47 Wave 4 POWER_LOTTO adapters."""
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


class _P47BaseAdapter:
    """
    Minimal replay adapter base for P47 Wave 4 POWER_LOTTO dry-run wrappers.
    NOT a subclass of ReplayStrategyAdapter to avoid any registry side-effects.
    lifecycle_status = DRY_RUN (NOT ONLINE, NOT RETIRED).

    Special number policy: PREDICTED_FROM_HISTORY
      - predicted_special in [1..8] via frequency mean-reversion
      - special_hit: 1 if predicted_special == actual_special, else 0
      - hit_count: FIRST-ZONE ONLY (never counts special)
    """
    meta: _P47AdapterMeta

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
        # Validate outputs
        assert len(numbers) == _PICK, f"Expected {_PICK} numbers, got {len(numbers)}"
        assert len(set(numbers)) == _PICK, f"Duplicate numbers: {numbers}"
        assert all(1 <= n <= _POOL for n in numbers), f"Out of range: {numbers}"
        assert 1 <= special <= _SPECIAL_POOL, f"Special out of range: {special}"
        return sorted(numbers), special

    def _predict(self, history: List[dict]) -> List[int]:
        raise NotImplementedError


class Pp3FreqOrt4BetAdapter(_P47BaseAdapter):
    """威力彩 PP3+FreqOrt 4注 bet-1 — strategy_id: pp3_freqort_4bet"""
    meta = _P47AdapterMeta(
        strategy_id="pp3_freqort_4bet",
        strategy_name="威力彩 PP3+FreqOrt 4注",
        strategy_version="v0.1-p47",
        min_history=50,  # fourier needs at least 10; 50 for meaningful FFT
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_pp3_freqort_4bet_bet1(history)


class MidFreqFourierMk3BetAdapter(_P47BaseAdapter):
    """威力彩 MidFreq+Fourier+Markov 3注 bet-1 — strategy_id: midfreq_fourier_mk_3bet"""
    meta = _P47AdapterMeta(
        strategy_id="midfreq_fourier_mk_3bet",
        strategy_name="威力彩 MidFreq+Fourier+Markov 3注",
        strategy_version="v0.1-p47",
        min_history=_MARKOV_WINDOW,  # 30 (Markov is the most demanding)
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_midfreq_fourier_mk_3bet_bet1(history)


class MidFreqFourier2BetAdapter(_P47BaseAdapter):
    """威力彩 MidFreq+Fourier 2注 bet-1 — strategy_id: midfreq_fourier_2bet"""
    meta = _P47AdapterMeta(
        strategy_id="midfreq_fourier_2bet",
        strategy_name="威力彩 MidFreq+Fourier 2注",
        strategy_version="v0.1-p47",
        min_history=10,  # fourier needs at least 10
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_midfreq_fourier_2bet_bet1(history)


# ─── Wave 4 adapter registry ──────────────────────────────────────────────────

WAVE4_ADAPTERS: List[_P47BaseAdapter] = [
    Pp3FreqOrt4BetAdapter(),       # rank 1 — highest RSM edge
    MidFreqFourierMk3BetAdapter(), # rank 2 — composite validated
    MidFreqFourier2BetAdapter(),   # rank 3 — orthogonal pair
]

WAVE4_ADAPTER_MAP: dict = {a.meta.strategy_id: a for a in WAVE4_ADAPTERS}


def generate_dryrun_rows(
    all_draws: List[dict],
    rows_per_strategy: int = 1500,
) -> List[dict]:
    """
    Generate dry-run rows for all 3 Wave 4 POWER_LOTTO strategies.

    Uses the last `rows_per_strategy` draws as targets, with strictly causal
    history slices (all draws before the target).

    Returns a flat list of row dicts ready for DB insertion.
    Each row has:
      - strategy_id, lottery_type="POWER_LOTTO"
      - draw_date, prediction_cutoff_date, prediction_generated_at
      - predicted_numbers (list[int], 6 unique ints 1-38)
      - predicted_special (int, 1-8)
      - actual_numbers (list[int])
      - actual_special (int or None)
      - hit_numbers (list[int])           — first-zone matches only
      - hit_count (int)                   — first-zone matches only (NOT special)
      - special_hit (int 0 or 1)          — predicted_special == actual_special
      - lifecycle = "DRY_RUN"
    """
    from datetime import datetime, timezone

    total_draws = len(all_draws)
    min_history_needed = max(a.meta.min_history for a in WAVE4_ADAPTERS)
    assert total_draws >= rows_per_strategy + min_history_needed, (
        f"Need at least {rows_per_strategy + min_history_needed} total draws, "
        f"got {total_draws}"
    )

    target_draws = all_draws[-rows_per_strategy:]
    now_str = datetime.now(timezone.utc).isoformat()
    all_rows: List[dict] = []

    for adapter in WAVE4_ADAPTERS:
        sid = adapter.meta.strategy_id
        for i, target in enumerate(target_draws):
            target_idx = total_draws - rows_per_strategy + i
            history = all_draws[:target_idx]  # strictly before target

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

                # First-zone hits ONLY
                hits = sorted(set(numbers) & set(actual_nums))
                hit_numbers_list = hits
                hit_count = len(hits)

                # Special hit (separate)
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

            row = {
                "strategy_id": sid,
                "lottery_type": "POWER_LOTTO",
                "target_draw": str(target["draw"]),
                "draw_date": target.get("date"),
                "prediction_cutoff_date": history[-1]["date"] if history else None,
                "prediction_generated_at": now_str,
                "predicted_numbers": predicted_numbers,        # 6 ints [1..38]
                "predicted_special": predicted_special_val,    # 1 int [1..8]
                "actual_numbers": target["numbers"],
                "actual_special": target.get("special"),
                "hit_numbers": hit_numbers_list,
                "hit_count": hit_count,                        # first-zone only
                "special_hit": special_hit,                    # 0 or 1
                "lifecycle": "DRY_RUN",
                "replay_status": replay_status,
                "reject_reason": reject_reason,
                "history_cutoff_draw": str(history[-1]["draw"]) if history else None,
                "strategy_name": adapter.meta.strategy_name,
                "strategy_version": adapter.meta.strategy_version,
            }
            all_rows.append(row)

    return all_rows
