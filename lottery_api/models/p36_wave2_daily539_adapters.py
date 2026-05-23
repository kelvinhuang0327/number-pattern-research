"""
p36_wave2_daily539_adapters.py
================================
P36 Wave 2 — DAILY_539 Dry-Run Adapter Wrappers

Standalone replay adapter wrappers for the 6 Wave 2 DAILY_539 strategies.
These adapters are NOT registered in replay_strategy_registry._ALL_ADAPTERS
or _REGISTRY. They exist exclusively for P36 temp-DB dry-run rehearsal.

HARD RULES (same as main registry):
  - history MUST be all draws STRICTLY BEFORE the target draw (causal slice).
  - Adapters MUST NOT read external state (DB, files, env) during prediction.
  - Only one bet is recorded per (strategy, draw) pair.
  - DAILY_539 has no special number — always returns None for special.
  - Each bet must have exactly 5 distinct integers in range [1..39].

LIFECYCLE NOTE:
  All 6 strategies have lifecycle_status=DRY_RUN (not ONLINE, not RETIRED).
  These wrappers do NOT promote them to ONLINE or ACTIVE.
  Dry-run rows go ONLY to /tmp/p36_temp.db — never to lottery_v2.db.

Wave 2 Strategies:
  markov_1bet_539         — Markov transition 1注 (window=30)
  acb_single_539          — ACB single 1注 (ACB anomaly capture)
  zone_gap_3bet_539       — Zone balance + gap composite 3注
  539_3bet_orthogonal     — ACB+Markov+Fourier orthogonal 3注 (bet-1 only)
  p0b_539_3bet_f_cold_fmid — Fourier4正交 3注 (cold+midfreq variant, bet-1)
  p0c_539_3bet_f_cold_x2  — Fourier4正交 3注 (x2 cold variant, bet-1)

Algorithm Reference: lottery_api/CLAUDE.md §ACB, §MidFreq, §Fourier, §Markov
P31A pattern reference: lottery_api/models/p31a_wave1_retired_adapters.py
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
_FOURIER_WINDOW = 500
_COLD_WINDOW = 100
_ZONE_WINDOW = 100

# Cross-zone sets for DAILY_539 (pool=39)
_Z1 = frozenset(range(1, 14))   # 1–13
_Z2 = frozenset(range(14, 27))  # 14–26
_Z3 = frozenset(range(27, 40))  # 27–39

WAVE2_STRATEGY_IDS = frozenset({
    "markov_1bet_539",
    "acb_single_539",
    "zone_gap_3bet_539",
    "539_3bet_orthogonal",
    "p0b_539_3bet_f_cold_fmid",
    "p0c_539_3bet_f_cold_x2",
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
    enforcing ≥2 distinct zones. If unconstrained top-n already satisfies
    the constraint, returns unchanged. Otherwise swaps one number from the
    over-represented zone with the best candidate from a missing zone.
    """
    selected = list(ranked[:n])
    zones_present = {_zone_of(x) for x in selected}

    if len(zones_present) >= 2:
        return selected

    zone_count = Counter(_zone_of(x) for x in selected)
    dominant_zone = max(zone_count, key=zone_count.get)
    missing_zones = [z for z in (1, 2, 3) if z not in zones_present]

    for mz in missing_zones:
        candidates = [x for x in ranked if _zone_of(x) == mz and x not in selected]
        if not candidates:
            continue
        new_num = candidates[0]
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

        gap_idx = last_seen.get(num, -1)
        gap_score = (w - 1 - gap_idx) / w

        boundary_bonus = 1.2 if (num <= 5 or num >= 35) else 1.0
        mod3_bonus = 1.1 if (num % 3 == 0) else 1.0

        scores[num] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus

    return scores


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


def _fourier_scores(history: List[dict], window: int = _FOURIER_WINDOW) -> dict:
    """
    Compute Fourier rhythm scores for DAILY_539 pool.

    Returns dict: {num: score} for num in 1..39.
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


# ─── Prediction functions ─────────────────────────────────────────────────────

def predict_markov_1bet(history: List[dict]) -> List[int]:
    """
    Markov transition 1注 — strategy_id: markov_1bet_539

    Uses MarkovStrategy(n=1) from backtest_39lotto_comprehensive.py.
    window=30, top-5 by transition score.
    """
    scores_arr = _markov_scores(history, window=_MARKOV_WINDOW)
    ranked = [int(idx + 1) for idx in np.argsort(-scores_arr)]
    return sorted(ranked[:_PICK])


def predict_acb_single(history: List[dict]) -> List[int]:
    """
    ACB single 1注 — strategy_id: acb_single_539

    Pure ACB score: freq_deficit×0.4 + gap_score×0.6 with zone constraint.
    Parallel to acb_1bet but named for production ACB single semantics.
    """
    scores = _acb_scores(history)
    ranked = sorted(range(1, _POOL + 1), key=lambda x: -scores[x])
    selected = _apply_cross_zone(ranked, scores, _PICK)
    return sorted(selected)


def predict_zone_gap_1bet(history: List[dict]) -> List[int]:
    """
    Zone-gap composite 1注 (bet-1 of zone_gap_3bet_539).

    Algorithm:
      - Zone balance: compute zone deficits (Z1=1-13, Z2=14-26, Z3=27-39)
      - Gap score: (current_idx - last_seen_idx) / window for each number
      - Combined score = zone_deficit_of_zone[num] × 0.5 + gap_score[num] × 0.5
      - Allocate top numbers from each zone proportional to deficit.
    """
    recent = history[-_ZONE_WINDOW:] if len(history) >= _ZONE_WINDOW else history
    w = len(recent)
    if w < 10:
        return list(range(1, _PICK + 1))

    # Zone deficit
    zone_counter: Counter = Counter()
    num_counter: Counter = Counter()
    for d in recent:
        for num in d["numbers"]:
            num_counter[num] += 1
            zone_counter[_zone_of(num)] += 1

    total = sum(zone_counter.values())
    expected_zone = total / 3.0

    zone_deficit = {z: max(0.0, expected_zone - zone_counter.get(z, 0)) for z in (1, 2, 3)}
    total_deficit = sum(zone_deficit.values())

    # Allocate slots per zone
    if total_deficit == 0:
        allocations = {1: 2, 2: 2, 3: 1}
    else:
        raw = {z: zone_deficit[z] / total_deficit * _PICK for z in (1, 2, 3)}
        allocations = {z: max(1, round(raw[z])) for z in (1, 2, 3)}
        while sum(allocations.values()) > _PICK:
            max_z = max(allocations, key=allocations.get)
            allocations[max_z] -= 1
        while sum(allocations.values()) < _PICK:
            min_z = min(allocations, key=allocations.get)
            allocations[min_z] += 1

    # Gap score per number
    last_seen: dict = {}
    for i, d in enumerate(recent):
        for num in d["numbers"]:
            last_seen[num] = i

    gap_scores: dict = {}
    for num in range(1, _POOL + 1):
        idx = last_seen.get(num, -1)
        gap_scores[num] = (w - 1 - idx) / w

    # Combined score
    expected_num = w * _PICK / _POOL
    combined: dict = {}
    for num in range(1, _POOL + 1):
        zone_num_deficit = max(0.0, expected_num - num_counter.get(num, 0)) / max(expected_num, 1.0)
        combined[num] = zone_deficit.get(_zone_of(num), 0) / max(total_deficit, 1.0) * 0.5 + gap_scores[num] * 0.5

    # Pick top nums from each zone by combined score
    result = []
    zone_nums: dict = {1: list(_Z1), 2: list(_Z2), 3: list(_Z3)}
    for z in (1, 2, 3):
        nums_in_zone = sorted(zone_nums[z], key=lambda n: -combined[n])
        result.extend(nums_in_zone[:allocations[z]])

    return sorted(result[:_PICK])


def predict_acb_markov_fourier_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of ACB+Markov+Fourier orthogonal 3注 — strategy_id: 539_3bet_orthogonal

    Replay records bet-1 only = pure ACB bet (same as acb_single_539).
    bet-2 = Markov, bet-3 = Fourier are not recorded in replay.
    """
    # Bet-1 of the 3-bet orthogonal = pure ACB (same as acb_single)
    return predict_acb_single(history)


def predict_fourier4_cold_fmid_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of p0b_539_3bet_f_cold_fmid — Fourier4正交 cold+midfreq variant.

    Source: predict_539_5bet_f4cold.py (F4Cold pattern)
    Bet-1 = top Fourier slice (numbers ranked by Fourier score, first 5).
    """
    scores = _fourier_scores(history, window=_FOURIER_WINDOW)
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if scores[n] > 0]
    if len(ranked) < _PICK:
        # Fallback: use midfreq for remaining
        mf = _midfreq_scores(history)
        remaining = [n for n in sorted(mf, key=lambda x: -mf[x]) if n not in ranked]
        ranked = ranked + remaining
    return sorted(ranked[:_PICK])


def predict_fourier4_cold_x2_bet1(history: List[dict]) -> List[int]:
    """
    Bet-1 of p0c_539_3bet_f_cold_x2 — Fourier4正交 x2 cold variant.

    Source: predict_539_5bet_f4cold.py (F4Cold x2 variant)
    Bet-1 = top Fourier slice. Same first-bet as p0b; x2 cold applies to later bets.
    """
    # x2 cold multiplier applies to bet-5 (cold × 2 weight), bet-1 is same Fourier slice
    scores = _fourier_scores(history, window=_FOURIER_WINDOW)
    ranked = [n for n in sorted(scores, key=lambda x: -scores[x]) if scores[n] > 0]
    if len(ranked) < _PICK:
        # Fallback
        acb = _acb_scores(history)
        remaining = [n for n in sorted(acb, key=lambda x: -acb[x]) if n not in ranked]
        ranked = ranked + remaining
    return sorted(ranked[:_PICK])


# ─── Adapter class wrappers ───────────────────────────────────────────────────

class _P36AdapterMeta:
    """Lightweight metadata holder (mirrors _P31AAdapterMeta without registry binding)."""
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
        self.supported_lottery_types = ["DAILY_539"]
        self.min_history = min_history


class _P36BaseAdapter:
    """
    Minimal replay adapter base for P36 dry-run wrappers.
    NOT a subclass of ReplayStrategyAdapter to avoid any registry side-effects.
    lifecycle_status = DRY_RUN (NOT ONLINE, NOT RETIRED).
    """
    meta: _P36AdapterMeta

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


class Markov1Bet539Adapter(_P36BaseAdapter):
    """今彩539 Markov 1注 — strategy_id: markov_1bet_539"""
    meta = _P36AdapterMeta(
        strategy_id="markov_1bet_539",
        strategy_name="今彩539 Markov 1注",
        strategy_version="v0.1-p36",
        min_history=_MARKOV_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_markov_1bet(history)


class AcbSingle539Adapter(_P36BaseAdapter):
    """今彩539 ACB Single 1注 — strategy_id: acb_single_539"""
    meta = _P36AdapterMeta(
        strategy_id="acb_single_539",
        strategy_name="今彩539 ACB Single 1注",
        strategy_version="v0.1-p36",
        min_history=_ACB_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_acb_single(history)


class ZoneGap3Bet539Adapter(_P36BaseAdapter):
    """
    今彩539 Zone+Gap 3注 — strategy_id: zone_gap_3bet_539

    Replay records bet-1 only = zone-gap composite bet.
    """
    meta = _P36AdapterMeta(
        strategy_id="zone_gap_3bet_539",
        strategy_name="今彩539 Zone+Gap 3注",
        strategy_version="v0.1-p36",
        min_history=_ZONE_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_zone_gap_1bet(history)


class Orthogonal3Bet539Adapter(_P36BaseAdapter):
    """
    今彩539 ACB+Markov+Fourier 正交 3注 — strategy_id: 539_3bet_orthogonal

    Replay records bet-1 only = pure ACB bet.
    (bet-2 = Markov, bet-3 = Fourier are not recorded in replay.)
    """
    meta = _P36AdapterMeta(
        strategy_id="539_3bet_orthogonal",
        strategy_name="今彩539 ACB+Markov+Fourier 正交 3注",
        strategy_version="v0.1-p36",
        min_history=_ACB_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_acb_markov_fourier_bet1(history)


class P0b539FColdFmidAdapter(_P36BaseAdapter):
    """
    今彩539 Fourier4正交 cold+midfreq 3注 — strategy_id: p0b_539_3bet_f_cold_fmid

    Replay records bet-1 only = top Fourier slice.
    (bet-2 = midfreq cold, bet-3 = cold+midfreq blend are not recorded.)
    """
    meta = _P36AdapterMeta(
        strategy_id="p0b_539_3bet_f_cold_fmid",
        strategy_name="今彩539 Fourier4正交 cold+midfreq 3注",
        strategy_version="v0.1-p36",
        min_history=_COLD_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_fourier4_cold_fmid_bet1(history)


class P0c539FColdX2Adapter(_P36BaseAdapter):
    """
    今彩539 Fourier4正交 x2 cold 3注 — strategy_id: p0c_539_3bet_f_cold_x2

    Replay records bet-1 only = top Fourier slice.
    (bet-2 = cold x2 weighted, bet-3 = cold x2 fallback are not recorded.)
    """
    meta = _P36AdapterMeta(
        strategy_id="p0c_539_3bet_f_cold_x2",
        strategy_name="今彩539 Fourier4正交 x2 cold 3注",
        strategy_version="v0.1-p36",
        min_history=_COLD_WINDOW,
    )

    def _predict(self, history: List[dict]) -> List[int]:
        return predict_fourier4_cold_x2_bet1(history)


# ─── Wave 2 adapter registry (ordered by wave2_rank from P35) ─────────────────

WAVE2_ADAPTERS: List[_P36BaseAdapter] = [
    Markov1Bet539Adapter(),       # rank 1
    AcbSingle539Adapter(),        # rank 2
    ZoneGap3Bet539Adapter(),      # rank 3
    Orthogonal3Bet539Adapter(),   # rank 4
    P0b539FColdFmidAdapter(),     # rank 5
    P0c539FColdX2Adapter(),       # rank 6
]

WAVE2_ADAPTER_MAP: dict = {a.meta.strategy_id: a for a in WAVE2_ADAPTERS}


def generate_dryrun_rows(
    all_draws: List[dict],
    rows_per_strategy: int = 1500,
) -> List[dict]:
    """
    Generate dry-run rows for all 6 Wave 2 DAILY_539 strategies.

    Uses the last `rows_per_strategy` draws as targets, with strictly causal
    history slices (all draws before the target).

    Returns a flat list of row dicts ready for DB insertion.
    Each row has:
      - strategy_id, lottery_type="DAILY_539"
      - draw_date, prediction_cutoff_date, prediction_generated_at
      - predicted_numbers (list[int], 5 unique ints 1-39)
      - actual_numbers (list[int])
      - hit_numbers (list[int])
      - hit_count (int)
      - is_retired = False
      - lifecycle = "DRY_RUN"
    """
    import hashlib
    import json
    from datetime import datetime, timezone

    total_draws = len(all_draws)
    assert total_draws >= rows_per_strategy + 100, (
        f"Need at least {rows_per_strategy + 100} total draws, got {total_draws}"
    )

    target_draws = all_draws[-rows_per_strategy:]
    now_str = datetime.now(timezone.utc).isoformat()
    all_rows: List[dict] = []

    for adapter in WAVE2_ADAPTERS:
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
                numbers, _ = adapter.get_one_bet(history, "DAILY_539")
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
                "lottery_type": "DAILY_539",
                "target_draw": str(target["draw"]),
                "draw_date": target.get("date"),
                "prediction_cutoff_date": history[-1]["date"] if history else None,
                "prediction_generated_at": now_str,
                "predicted_numbers": predicted_numbers,
                "actual_numbers": target["numbers"],
                "hit_numbers": hit_numbers_list,
                "hit_count": hit_count,
                "is_retired": False,
                "lifecycle": "DRY_RUN",
                "replay_status": replay_status,
                "reject_reason": reject_reason,
                "history_cutoff_draw": str(history_cutoff) if history_cutoff else None,
                "strategy_name": adapter.meta.strategy_name,
                "strategy_version": adapter.meta.strategy_version,
            }
            all_rows.append(row)

    return all_rows
