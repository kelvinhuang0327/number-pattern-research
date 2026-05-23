"""
p42_wave3_biglotto_adapters.py
================================
P42 Wave 3 — BIG_LOTTO Dry-Run Adapter Scaffold

Standalone replay adapter wrappers for the 6 Wave 3 BIG_LOTTO strategies.
These adapters are NOT registered in replay_strategy_registry._ALL_ADAPTERS
or _REGISTRY. They exist exclusively for P42 temp-DB dry-run rehearsal.

BIG_LOTTO specifics:
  - Pool: 1-49
  - Pick: 6 main numbers per prediction
  - Special number: NOT predicted in Wave 3 (predicted_special=None, special_hit=0)
  - Lifecycle: DRY_RUN
  - 1500 rows per strategy

HARD RULES (same as p36 DAILY_539 pattern):
  - history MUST be all draws STRICTLY BEFORE the target draw (causal slice).
  - Adapters MUST NOT read external state (DB, files, env) during prediction.
  - Only one bet is recorded per (strategy, draw) pair.
  - BIG_LOTTO Wave 3 does NOT predict the special number: always returns None.
  - Each bet must have exactly 6 distinct integers in range [1..49].

LIFECYCLE NOTE:
  All 6 strategies have lifecycle_status=DRY_RUN (not ONLINE, not RETIRED).
  These wrappers do NOT promote them to ONLINE or ACTIVE.
  Dry-run rows go ONLY to /tmp/p42_temp_rehearsal.db — never to lottery_v2.db.

Wave 3 Strategies (from P41 bootstrap planning):
  markov_single_biglotto        — Markov transition 1注 (window=100)
  markov_2bet_biglotto          — Markov 2注 bet-1 only (window=100)
  bet2_fourier_expansion_biglotto — Fourier FFT 2注 orthogonal bet-1 (window=500)
  fourier30_markov30_biglotto   — Fourier30+Markov30 diversified bet-1
  cold_complement_biglotto      — Coldest-12 split 2注 bet-1 (window=100)
  coldpool15_biglotto           — Cold pool-15 pick-6 (window=100)

Reference: lottery_api/models/p36_wave2_daily539_adapters.py (DAILY_539 pattern)
P41 planning: outputs/replay/p41_wave3_biglotto_adapter_bootstrap_planning_20260524.json
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

_POOL = 49      # BIG_LOTTO number pool 1..49
_PICK = 6       # numbers per bet
_MARKOV_WINDOW = 100
_FOURIER_WINDOW = 500
_FOURIER30_WINDOW = 30
_MARKOV30_WINDOW = 30
_COLD_WINDOW = 100

WAVE3_STRATEGY_IDS = frozenset({
    "markov_single_biglotto",
    "markov_2bet_biglotto",
    "bet2_fourier_expansion_biglotto",
    "fourier30_markov30_biglotto",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
})


# ─── Core algorithm helpers ───────────────────────────────────────────────────

def _markov_scores(history: List[dict], window: int = _MARKOV_WINDOW) -> np.ndarray:
    """
    Compute 1st-order Markov transition scores for BIG_LOTTO pool (indices 0..48).

    Builds transition matrix from last `window` draws.
    Returns np.ndarray of shape (49,) representing next-draw probability scores.
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


def _fourier_scores(history: List[dict], window: int = _FOURIER_WINDOW) -> dict:
    """
    Compute Fourier rhythm scores for BIG_LOTTO pool.

    Uses FFT period detection: score = 1 / (|gap - period| + 1).
    Returns dict: {num: score} for num in 1..49.
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w < 10:
        return {n: 0.0 for n in range(1, _POOL + 1)}

    scores: dict = {}
    for num in range(1, _POOL + 1):
        series = np.array([1 if num in d["numbers"] else 0 for d in recent], dtype=float)
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


def _fourier30_weighted_scores(history: List[dict], window: int = _FOURIER30_WINDOW) -> dict:
    """
    Compute Fourier30 scores: linear-ramp weighted frequency over `window` draws.

    Numbers appearing in recent draws receive higher weight (ramp from 1 to window).
    Returns dict: {num: score} for num in 1..49.
    """
    recent = history[-window:] if len(history) >= window else history
    w = len(recent)
    if w == 0:
        return {n: 0.0 for n in range(1, _POOL + 1)}

    scores = {n: 0.0 for n in range(1, _POOL + 1)}
    for i, draw in enumerate(recent):
        weight = (i + 1)  # linear ramp: older=1, newer=window
        for num in draw["numbers"]:
            if 1 <= num <= _POOL:
                scores[num] += weight

    return scores


def _cold_freq_scores(history: List[dict], window: int = _COLD_WINDOW) -> dict:
    """
    Compute cold frequency scores for BIG_LOTTO pool.

    score = -count (ascending frequency; coldest numbers score highest).
    Returns dict: {num: score} for num in 1..49.
    """
    recent = history[-window:] if len(history) >= window else history
    freq: Counter = Counter()
    for d in recent:
        for num in d["numbers"]:
            if 1 <= num <= _POOL:
                freq[num] += 1

    # Cold: fewer appearances = higher score (negate the count)
    return {num: -freq.get(num, 0) for num in range(1, _POOL + 1)}


# ─── Prediction functions ─────────────────────────────────────────────────────

def predict_markov_single(history: List[dict]) -> List[int]:
    """
    Markov 1注 top-6 — strategy_id: markov_single_biglotto

    window=100. Top-6 by Markov next_scores. Deterministic.
    """
    scores = _markov_scores(history, window=_MARKOV_WINDOW)
    ranked = [int(idx + 1) for idx in np.argsort(-scores)]
    return sorted(ranked[:_PICK])


def predict_markov_2bet_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of Markov 2注 — strategy_id: markov_2bet_biglotto

    Same Markov transition as markov_single_biglotto.
    Replay records bet-1 only (bet-2 = next-6 by score is not recorded).
    window=100.
    """
    # Bet-1 is the same as markov_single: top-6 by score
    return predict_markov_single(history)


def predict_fourier_expansion_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of Fourier 2注 orthogonal — strategy_id: bet2_fourier_expansion_biglotto

    FFT period detection window=500. Top-6 by Fourier score = bet-1.
    Replay records bet-1 only (bet-2 = next-6 is not recorded).
    """
    scores = _fourier_scores(history, window=_FOURIER_WINDOW)
    ranked = sorted(range(1, _POOL + 1), key=lambda n: -scores[n])
    return sorted(ranked[:_PICK])


def predict_fourier30_markov30_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of Fourier30+Markov30 diversified — strategy_id: fourier30_markov30_biglotto

    Bet-1 = Fourier30 (linear-ramp weighted frequency, window=30), top-6.
    Bet-2 = Markov30, max_overlap=3 enforced (not recorded in replay).
    Replay records bet-1 only.
    """
    scores = _fourier30_weighted_scores(history, window=_FOURIER30_WINDOW)
    ranked = sorted(range(1, _POOL + 1), key=lambda n: -scores[n])
    return sorted(ranked[:_PICK])


def predict_cold_complement_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of Cold complement 2注 — strategy_id: cold_complement_biglotto

    Top-12 coldest from last 100 draws.
    Bet-1 = coldest 6, bet-2 = next-coldest 6 (not recorded in replay).
    Replay records bet-1 only.
    """
    scores = _cold_freq_scores(history, window=_COLD_WINDOW)
    ranked = sorted(range(1, _POOL + 1), key=lambda n: scores[n])  # ascending freq = coldest first
    return sorted(ranked[:_PICK])


def predict_coldpool15(history: List[dict]) -> List[int]:
    """
    Cold pool-15 pick-6 — strategy_id: coldpool15_biglotto

    Top-15 coldest numbers from last 100 draws → pick 6 from that pool
    by further sorting within the 15 by ascending frequency.
    """
    scores = _cold_freq_scores(history, window=_COLD_WINDOW)
    # Get top-15 coldest
    ranked = sorted(range(1, _POOL + 1), key=lambda n: scores[n])[:15]  # ascending freq
    # From the 15, take the 6 coldest
    return sorted(ranked[:_PICK])


# ─── Adapter class wrappers ───────────────────────────────────────────────────

class _P42AdapterMeta:
    """Lightweight metadata holder for P42 Wave 3 BIG_LOTTO adapters."""
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
        self.lifecycle_status = "DRY_RUN"
        self.supported_lottery_types = ["BIG_LOTTO"]
        self.min_history = min_history


class _P42BaseAdapter:
    """
    Minimal replay adapter base for P42 Wave 3 BIG_LOTTO dry-run wrappers.
    NOT a subclass of ReplayStrategyAdapter to avoid any registry side-effects.
    lifecycle_status = DRY_RUN (NOT ONLINE, NOT RETIRED).

    Special number policy: NOT_PREDICTED_WAVE3
      - predicted_special is always None
      - special_hit is always 0
    """
    meta: _P42AdapterMeta

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
        return sorted(numbers), None  # BIG_LOTTO Wave 3: no special prediction

    def _predict(self, history: List[dict]) -> List[int]:
        raise NotImplementedError


class MarkovSingleBigLottoAdapter(_P42BaseAdapter):
    """大樂透 Markov 1注 — strategy_id: markov_single_biglotto"""
    meta = _P42AdapterMeta(
        strategy_id="markov_single_biglotto",
        strategy_name="大樂透 Markov Single 1注",
        strategy_version="v0.1-p42",
        min_history=_MARKOV_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_markov_single(history)


class Markov2BetBigLottoAdapter(_P42BaseAdapter):
    """大樂透 Markov 2注 bet-1 — strategy_id: markov_2bet_biglotto"""
    meta = _P42AdapterMeta(
        strategy_id="markov_2bet_biglotto",
        strategy_name="大樂透 Markov 2注",
        strategy_version="v0.1-p42",
        min_history=_MARKOV_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_markov_2bet_bet1(history)


class Bet2FourierExpansionBigLottoAdapter(_P42BaseAdapter):
    """
    大樂透 Fourier 2注 bet-1 — strategy_id: bet2_fourier_expansion_biglotto

    Replay records bet-1 only = top Fourier slice (window=500).
    """
    meta = _P42AdapterMeta(
        strategy_id="bet2_fourier_expansion_biglotto",
        strategy_name="大樂透 Fourier 2注 Expansion",
        strategy_version="v0.1-p42",
        min_history=50,  # fourier needs at least 10, but 50 for meaningful FFT
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_fourier_expansion_bet1(history)


class Fourier30Markov30BigLottoAdapter(_P42BaseAdapter):
    """
    大樂透 Fourier30+Markov30 bet-1 — strategy_id: fourier30_markov30_biglotto

    Replay records bet-1 only = Fourier30 weighted top-6.
    """
    meta = _P42AdapterMeta(
        strategy_id="fourier30_markov30_biglotto",
        strategy_name="大樂透 Fourier30+Markov30",
        strategy_version="v0.1-p42",
        min_history=_FOURIER30_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_fourier30_markov30_bet1(history)


class ColdComplementBigLottoAdapter(_P42BaseAdapter):
    """
    大樂透 Cold complement 2注 bet-1 — strategy_id: cold_complement_biglotto

    Replay records bet-1 only = coldest 6 from 100-draw window.
    """
    meta = _P42AdapterMeta(
        strategy_id="cold_complement_biglotto",
        strategy_name="大樂透 Cold Complement 2注",
        strategy_version="v0.1-p42",
        min_history=_COLD_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_cold_complement_bet1(history)


class Coldpool15BigLottoAdapter(_P42BaseAdapter):
    """大樂透 Cold pool-15 pick-6 — strategy_id: coldpool15_biglotto"""
    meta = _P42AdapterMeta(
        strategy_id="coldpool15_biglotto",
        strategy_name="大樂透 Cold Pool-15 Pick-6",
        strategy_version="v0.1-p42",
        min_history=_COLD_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_coldpool15(history)


# ─── Wave 3 adapter registry (ordered by wave3_rank from P41) ─────────────────

WAVE3_ADAPTERS: List[_P42BaseAdapter] = [
    MarkovSingleBigLottoAdapter(),         # rank 1
    Markov2BetBigLottoAdapter(),           # rank 2
    Bet2FourierExpansionBigLottoAdapter(), # rank 3
    Fourier30Markov30BigLottoAdapter(),    # rank 4
    ColdComplementBigLottoAdapter(),       # rank 5
    Coldpool15BigLottoAdapter(),           # rank 6
]

WAVE3_ADAPTER_MAP: dict = {a.meta.strategy_id: a for a in WAVE3_ADAPTERS}

WAVE3_STRATEGY_ID_LIST = [a.meta.strategy_id for a in WAVE3_ADAPTERS]


def generate_dryrun_rows(
    all_draws: List[dict],
    rows_per_strategy: int = 1500,
) -> List[dict]:
    """
    Generate dry-run rows for all 6 Wave 3 BIG_LOTTO strategies.

    Uses the last `rows_per_strategy` draws as targets, with strictly causal
    history slices (all draws before the target).

    Returns a flat list of row dicts ready for DB insertion.
    Each row has:
      - strategy_id, lottery_type="BIG_LOTTO"
      - draw_date, prediction_cutoff_date, prediction_generated_at
      - predicted_numbers (list[int], 6 unique ints 1-49)
      - actual_numbers (list[int])
      - actual_special (int or None)
      - hit_numbers (list[int])
      - hit_count (int)
      - predicted_special = None (Wave 3: NOT_PREDICTED)
      - special_hit = 0 (Wave 3: always 0)
      - lifecycle = "DRY_RUN"
    """
    import json
    from datetime import datetime, timezone

    total_draws = len(all_draws)
    assert total_draws >= rows_per_strategy + max(a.meta.min_history for a in WAVE3_ADAPTERS), (
        f"Need at least {rows_per_strategy + 100} total draws, got {total_draws}"
    )

    target_draws = all_draws[-rows_per_strategy:]
    now_str = datetime.now(timezone.utc).isoformat()
    all_rows: List[dict] = []

    for adapter in WAVE3_ADAPTERS:
        sid = adapter.meta.strategy_id
        for i, target in enumerate(target_draws):
            target_idx = total_draws - rows_per_strategy + i
            history = all_draws[:target_idx]  # strictly before target

            replay_status = "PREDICTED"
            reject_reason = None
            predicted_numbers = None
            hit_numbers_list: List[int] = []
            hit_count = 0

            try:
                numbers, _ = adapter.get_one_bet(history, "BIG_LOTTO")
                predicted_numbers = numbers

                actual_nums = target["numbers"]
                hits = sorted(set(numbers) & set(actual_nums))
                hit_numbers_list = hits
                hit_count = len(hits)

            except ValueError as exc:
                replay_status = "INSUFFICIENT_HISTORY"
                reject_reason = str(exc)
            except AssertionError as exc:
                replay_status = "INVALID_OUTPUT"
                reject_reason = str(exc)
            except Exception as exc:
                replay_status = "REPLAY_ERROR"
                reject_reason = str(exc)

            history_cutoff = history[-1]["draw"] if history else None

            row = {
                "strategy_id": sid,
                "lottery_type": "BIG_LOTTO",
                "target_draw": str(target["draw"]),
                "draw_date": target.get("date"),
                "prediction_cutoff_date": history[-1]["date"] if history else None,
                "prediction_generated_at": now_str,
                "predicted_numbers": predicted_numbers,
                "predicted_special": None,          # Wave 3: NOT_PREDICTED
                "actual_numbers": target["numbers"],
                "actual_special": target.get("special"),
                "hit_numbers": hit_numbers_list,
                "hit_count": hit_count,
                "special_hit": 0,                   # Wave 3: always 0
                "lifecycle": "DRY_RUN",
                "replay_status": replay_status,
                "reject_reason": reject_reason,
                "history_cutoff_draw": str(history_cutoff) if history_cutoff else None,
                "strategy_name": adapter.meta.strategy_name,
                "strategy_version": adapter.meta.strategy_version,
            }
            all_rows.append(row)

    return all_rows
