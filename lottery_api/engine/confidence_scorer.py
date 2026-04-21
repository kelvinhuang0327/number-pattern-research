"""
Confidence Scorer — Phase T (Statistical Confidence Upgrade Layer)

Adds a *graded* confidence layer on top of the existing binary validation
system. Does NOT replace validated_status. Does NOT recompute edge / perm /
mcnemar. Only interprets the existing fields more carefully.

PRINCIPLE
---------
We are not changing reality — we are improving how we interpret uncertainty.

WHAT THIS MODULE ADDS
---------------------
1. adjusted_mcnemar_p   — Holm-Bonferroni corrected p-value (per lottery)
2. confidence_score     — weighted composite in [0, 1]
3. confidence_tier      — HIGH / MEDIUM / LOW / UNRELIABLE
4. promotable           — True when a WATCH strategy is close to passing

SAFETY
------
- Read-only: does not mutate strategy_states_*.json
- Feature flag: env var PHASE_T_CONFIDENCE_ENABLED (default "true")
- When disabled, get_lottery_confidence() returns empty → callers fall back
  to plain validated_status (identical to pre-Phase-T behavior).
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths / flags ─────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
LOTTERY_TYPES = ['DAILY_539', 'BIG_LOTTO', 'POWER_LOTTO']


def _env_flag(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on', 'enabled')


ENABLED = _env_flag('PHASE_T_CONFIDENCE_ENABLED', True)

# ── Scoring weights (spec) ────────────────────────────────────────────────────

W_SIGNIFICANCE = 0.35   # f1 = 1 - adjusted_mcnemar_p
W_PERMUTATION  = 0.25   # f2 = 1 - perm_p
W_STABILITY    = 0.20   # f3 = min(edge_w)/max(edge_w)  [when all positive]
W_SAMPLE       = 0.20   # f4 = min(1, total_records/500)

# Tier cutoffs (spec)
TIER_HIGH   = 0.75
TIER_MED    = 0.55
TIER_LOW    = 0.35

# Promotable rule (spec)
PROMOTABLE_ADJ_MCNEMAR = 0.08
PROMOTABLE_MIN_TIER    = 'MEDIUM'


# ── Holm–Bonferroni correction ────────────────────────────────────────────────

def holm_adjust(p_values: list) -> list:
    """
    Holm-Bonferroni step-down. Input is a list of (key, p_raw) tuples.
    Returns list of (key, p_adjusted), with ordering preserved as in input.

    Less conservative than Bonferroni, controls FWER at the nominal level.
    """
    if not p_values:
        return []
    n = len(p_values)
    # Sort by p ascending; p=None → treat as 1.0 (no info)
    indexed = [(i, k, (v if v is not None else 1.0)) for i, (k, v) in enumerate(p_values)]
    indexed_sorted = sorted(indexed, key=lambda t: t[2])

    adjusted = [None] * n
    running_max = 0.0
    for rank, (orig_i, key, p) in enumerate(indexed_sorted):
        # Holm: p_adj = p * (n - rank), clamped to monotone non-decreasing, max 1
        p_adj = min(1.0, p * (n - rank))
        # Enforce monotonicity across the sorted sequence
        p_adj = max(running_max, p_adj)
        running_max = p_adj
        adjusted[orig_i] = (key, round(p_adj, 6))
    return adjusted


# ── Confidence score ──────────────────────────────────────────────────────────

def _clip01(x: float) -> float:
    if x is None:
        return 0.0
    if x < 0: return 0.0
    if x > 1: return 1.0
    return x


def _stability_factor(e150, e500, e1500) -> float:
    """
    f3 = min(edges) / max(edges) when all positive.
    If any edge <= 0, returns 0 (unstable across windows).
    """
    vals = [e150, e500, e1500]
    if any(v is None for v in vals):
        return 0.0
    if any(v <= 0 for v in vals):
        return 0.0
    mn, mx = min(vals), max(vals)
    if mx <= 0:
        return 0.0
    return round(mn / mx, 6)


def _sample_factor(total_records: Optional[int]) -> float:
    if not total_records or total_records <= 0:
        return 0.0
    return round(min(1.0, total_records / 500.0), 6)


def _tier_from_score(score: float) -> str:
    if score >= TIER_HIGH: return 'HIGH_CONFIDENCE'
    if score >= TIER_MED:  return 'MEDIUM_CONFIDENCE'
    if score >= TIER_LOW:  return 'LOW_CONFIDENCE'
    return 'UNRELIABLE'


def _tier_rank(tier: str) -> int:
    """Higher is better."""
    return {'HIGH_CONFIDENCE': 3,
            'MEDIUM_CONFIDENCE': 2,
            'LOW_CONFIDENCE': 1,
            'UNRELIABLE': 0}.get(tier, 0)


def score_strategy(state: dict, adjusted_mc: Optional[float]) -> dict:
    """
    Compute confidence fields for one strategy. Does NOT mutate input.
    """
    perm_p     = state.get('perm_p')
    e150       = state.get('edge_150p')
    e500       = state.get('edge_500p')
    e1500      = state.get('edge_1500p')
    total_rec  = state.get('total_records')

    # Fallback: if adjusted mcnemar not available, use raw (conservative)
    if adjusted_mc is None:
        adjusted_mc = state.get('mcnemar_p')

    f1 = _clip01(1.0 - (adjusted_mc if adjusted_mc is not None else 1.0))
    f2 = _clip01(1.0 - (perm_p      if perm_p      is not None else 1.0))
    f3 = _stability_factor(e150, e500, e1500)
    f4 = _sample_factor(total_rec)

    score = (W_SIGNIFICANCE * f1 +
             W_PERMUTATION  * f2 +
             W_STABILITY    * f3 +
             W_SAMPLE       * f4)
    score = round(_clip01(score), 6)
    tier  = _tier_from_score(score)

    validated_status = (state.get('validated_status') or 'WATCH').upper()
    promotable = (
        validated_status == 'WATCH' and
        _tier_rank(tier) >= _tier_rank('MEDIUM_CONFIDENCE') and
        adjusted_mc is not None and adjusted_mc < PROMOTABLE_ADJ_MCNEMAR
    )

    return {
        'adjusted_mcnemar_p': (round(adjusted_mc, 6) if adjusted_mc is not None else None),
        'confidence_score':   score,
        'confidence_tier':    tier,
        'factors': {
            'f1_significance': round(f1, 6),
            'f2_permutation':  round(f2, 6),
            'f3_stability':    round(f3, 6),
            'f4_sample':       round(f4, 6),
        },
        'promotable': bool(promotable),
    }


# ── Lottery-level confidence table ────────────────────────────────────────────

def _load_states(lottery_type: str) -> dict:
    path = os.path.join(DATA_DIR, f'strategy_states_{lottery_type}.json')
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f'[Confidence] Failed to load {lottery_type}: {e}')
        return {}


def get_lottery_confidence(lottery_type: str) -> dict:
    """
    Returns {strategy_name: confidence_fields}. Empty dict when disabled
    or no data.
    """
    if not ENABLED:
        return {}
    states = _load_states(lottery_type)
    if not states:
        return {}

    # Holm-Bonferroni on mcnemar_p (per lottery)
    raw_pairs = [(name, (s.get('mcnemar_p') if s.get('mcnemar_p') is not None else 1.0))
                 for name, s in states.items()]
    adjusted = dict(holm_adjust(raw_pairs))

    out = {}
    for name, s in states.items():
        adj = adjusted.get(name)
        scored = score_strategy(s, adj)
        scored['name'] = name
        scored['validated_status'] = s.get('validated_status') or 'WATCH'
        scored['mcnemar_p_raw']    = s.get('mcnemar_p')
        scored['num_bets']         = s.get('num_bets')
        out[name] = scored
    return out


def get_all_confidence() -> dict:
    """Returns {lottery_type: {strategy_name: fields}} across all lotteries."""
    return {lt: get_lottery_confidence(lt) for lt in LOTTERY_TYPES}


def get_promotable(lottery_type: str) -> list:
    """Shortcut: list of strategies currently flagged as promotable."""
    table = get_lottery_confidence(lottery_type)
    return [s for s in table.values() if s.get('promotable')]
