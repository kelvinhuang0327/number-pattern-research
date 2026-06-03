"""
star_box_play.py
================
P227B — 3_STAR / 4_STAR Box-Play Dry-Run Semantics

Pure metric functions for star-lottery box-play evaluation.
This module is CODE-ONLY DRY-RUN and must never:
  - write to strategy_prediction_replays
  - write to any DB table
  - call calculate_match_score from quick_strategy_evaluation.py
    or comprehensive_strategy_evaluation.py

Background
----------
3_STAR and 4_STAR are digit lotteries (digits 0-9).
Current DB stores draw numbers as sorted JSON arrays, so positional order is lost.
Straight-play (exact position match) is therefore BLOCKED until re-ingestion.
Box-play (any-order combination match) is fully supported on sorted stored data.

Metric semantics
----------------
star_box_exact_match:
    Returns True if multiset(predicted) == multiset(actual).
    "Box-play win" in standard digit-lottery rules.

star_digit_overlap_count:
    Returns number of shared digits with multiplicity (multiset intersection size).
    Secondary diagnostic metric; does NOT correspond to a prize tier.

star_calculate_box_score:
    Returns pick_count if exact box hit, else 0.
    Use this value for hit_count storage (encoded as 0 or pick_count).
    Never compare the result to M2+/M3+ thresholds designed for 6-digit lotteries.

Baseline definitions (current sorted DB, no-repeat assumption)
--------------------------------------------------------------
3_STAR: C(10,3) = 120  →  random box-exact baseline ≈ 0.00833
4_STAR: C(10,4) = 210  →  random box-exact baseline ≈ 0.00476

If repeated digits are later re-ingested, baselines change to:
3_STAR: C(12,3) = 220  →  ≈ 0.00455
4_STAR: C(13,4) = 715  →  ≈ 0.00140

Statistical power note
----------------------
3_STAR has ~4,179 historical draws; 4_STAR ~2,922.
Detecting a 20 % relative lift (edge ≈ +0.00167 above 0.00833) at 80 % power, α=0.05
requires approximately 10,000 draws for 3_STAR and 17,000 for 4_STAR.
Both lotteries are currently UNDERPOWERED for exact-combo signal detection.
Any P227B scan must classify results as INSUFFICIENT_STATISTICAL_POWER if below threshold.
"""
from __future__ import annotations

from collections import Counter
from math import comb
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Lottery configuration constants
# ---------------------------------------------------------------------------

STAR_LOTTERY_TYPES = ("3_STAR", "4_STAR")

STAR_CONFIG = {
    "3_STAR": {
        "pick_count": 3,
        "min_digit": 0,
        "max_digit": 9,
        "repeats_allowed": True,       # per lottery_types.json
        "is_permutation": True,        # per lottery_types.json
        # Current DB: 100 % sorted, 0 repeated-digit draws observed.
        # active_mode limited to "box_exact" until re-ingestion.
        "active_mode": "box_exact",
        "combination_space_no_repeat": comb(10, 3),   # 120
        "combination_space_with_repeat": comb(12, 3),  # 220
        "baseline_no_repeat": 1 / comb(10, 3),         # ≈ 0.00833
        "baseline_with_repeat": 1 / comb(12, 3),       # ≈ 0.00455
    },
    "4_STAR": {
        "pick_count": 4,
        "min_digit": 0,
        "max_digit": 9,
        "repeats_allowed": True,
        "is_permutation": True,
        "active_mode": "box_exact",
        "combination_space_no_repeat": comb(10, 4),   # 210
        "combination_space_with_repeat": comb(13, 4),  # 715
        "baseline_no_repeat": 1 / comb(10, 4),         # ≈ 0.00476
        "baseline_with_repeat": 1 / comb(13, 4),       # ≈ 0.00140
    },
}

STRAIGHT_PLAY_BLOCKED_REASON = (
    "Straight-play requires per-digit positional order. "
    "Current DB stores draws as sorted arrays; positional information is lost. "
    "Re-ingest from raw positional source and obtain separate authorization before "
    "implementing straight-play."
)


# ---------------------------------------------------------------------------
# Public metric functions
# ---------------------------------------------------------------------------


def star_box_exact_match(predicted: List[int], actual: List[int]) -> bool:
    """
    Return True if the multiset of predicted digits equals the multiset of actual digits.

    This is the definition of a box-play win in standard digit-lottery rules.

    Both inputs are sorted before comparison so the function is order-independent,
    consistent with sorted DB storage.

    Parameters
    ----------
    predicted : list of ints, each in 0-9, length == pick_count
    actual    : list of ints, each in 0-9, length == pick_count (as stored in DB)

    Returns
    -------
    bool : True = exact box hit, False = miss

    Examples
    --------
    >>> star_box_exact_match([5, 6, 9], [5, 6, 9])
    True
    >>> star_box_exact_match([9, 6, 5], [5, 6, 9])   # order irrelevant
    True
    >>> star_box_exact_match([1, 2, 3], [5, 6, 9])
    False
    >>> star_box_exact_match([5, 5, 9], [5, 5, 9])   # repeated digits
    True
    >>> star_box_exact_match([5, 5, 9], [5, 6, 9])   # repeat mismatch
    False
    """
    return Counter(predicted) == Counter(actual)


def star_digit_overlap_count(predicted: List[int], actual: List[int]) -> int:
    """
    Return the number of shared digits with multiplicity (multiset intersection size).

    This is a secondary diagnostic metric.  It does NOT correspond to a prize tier
    in standard 3_STAR / 4_STAR box-play rules.

    IMPORTANT: This function uses multiset (Counter) intersection, NOT set intersection.
    set intersection would incorrectly collapse repeated digits, e.g.:
        set([5,5,9]) & set([5,6,9]) → {5,9} → len=2  (WRONG: double-5 is one 5)
    Counter intersection: min(Counter([5,5,9]), Counter([5,6,9])) → {5:1} → len=1 (correct)

    Examples
    --------
    >>> star_digit_overlap_count([5, 6, 9], [5, 6, 9])
    3
    >>> star_digit_overlap_count([5, 6, 1], [5, 6, 9])
    2
    >>> star_digit_overlap_count([5, 5, 9], [5, 6, 9])   # only 1 five shared
    2
    >>> star_digit_overlap_count([5, 5, 9], [5, 5, 9])   # two fives shared
    3
    """
    c_pred = Counter(predicted)
    c_act = Counter(actual)
    intersection = c_pred & c_act          # Counter min
    return sum(intersection.values())


def star_calculate_box_score(
    predicted: List[int],
    actual: List[int],
    pick_count: int,
) -> Tuple[int, bool, int]:
    """
    Compute box-play score for storage in strategy_prediction_replays.

    Returns
    -------
    (hit_count, exact_box_hit, digit_overlap)
        hit_count      : pick_count if exact box hit, else 0.
                         Use this value for the `hit_count` DB column.
                         Never compare to M2+ / M3+ thresholds for 6-digit lotteries.
        exact_box_hit  : True if multiset(predicted) == multiset(actual)
        digit_overlap  : multiset intersection size (secondary metric)

    Parameters
    ----------
    predicted  : list of int digits (0-9), any order
    actual     : list of int digits (0-9), as stored in DB (sorted)
    pick_count : 3 for 3_STAR, 4 for 4_STAR

    Raises
    ------
    ValueError if len(predicted) != pick_count or len(actual) != pick_count.

    Examples
    --------
    >>> star_calculate_box_score([9,5,6], [5,6,9], 3)
    (3, True, 3)
    >>> star_calculate_box_score([1,2,3], [5,6,9], 3)
    (0, False, 0)
    >>> star_calculate_box_score([5,5,9], [5,6,9], 3)
    (0, False, 2)
    """
    if len(predicted) != pick_count:
        raise ValueError(
            f"predicted length {len(predicted)} != pick_count {pick_count}"
        )
    if len(actual) != pick_count:
        raise ValueError(
            f"actual length {len(actual)} != pick_count {pick_count}"
        )
    exact = star_box_exact_match(predicted, actual)
    overlap = star_digit_overlap_count(predicted, actual)
    return (pick_count if exact else 0, exact, overlap)


def get_box_baseline(lottery_type: str, repeats_detected: bool = False) -> float:
    """
    Return the random box-exact baseline for the given lottery_type.

    Parameters
    ----------
    lottery_type    : "3_STAR" or "4_STAR"
    repeats_detected: True if repeated-digit draws have been confirmed in the data.
                      Default False (current DB shows 0 repeated-digit draws).

    Returns
    -------
    float : probability of a random prediction exactly matching the draw in box mode.
    """
    if lottery_type not in STAR_CONFIG:
        raise ValueError(f"Unknown star lottery type: {lottery_type!r}")
    cfg = STAR_CONFIG[lottery_type]
    return cfg["baseline_with_repeat"] if repeats_detected else cfg["baseline_no_repeat"]


def validate_star_input(digits: List[int], lottery_type: str) -> None:
    """
    Raise ValueError if the digit list is invalid for the given star lottery type.

    Checks:
    - length equals pick_count
    - all digits in 0-9
    - if repeats_detected=False (current DB mode), no repeated digits

    This is a helper for adapter validation, not for scoring.
    """
    cfg = STAR_CONFIG[lottery_type]
    pick_count = cfg["pick_count"]
    if len(digits) != pick_count:
        raise ValueError(
            f"{lottery_type} expects {pick_count} digits, got {len(digits)}"
        )
    for d in digits:
        if not (0 <= d <= 9):
            raise ValueError(f"Digit {d} out of range 0-9 for {lottery_type}")


# ---------------------------------------------------------------------------
# Dry-run row dict builder (no DB write)
# ---------------------------------------------------------------------------


def build_dryrun_row(
    lottery_type: str,
    target_draw: str,
    target_date: str,
    strategy_id: str,
    strategy_name: str,
    history_cutoff_draw: str,
    predicted: List[int],
    actual: List[int],
    bet_index: int = 1,
) -> dict:
    """
    Build a dry-run result dict matching strategy_prediction_replays schema.

    This function NEVER writes to the database.  It returns a plain dict that
    can be serialised to JSON / CSV for off-DB dry-run analysis.

    dry_run is always set to 1.
    truth_level is set to 'BOX_PLAY_DRY_RUN_BOX_EXACT' to distinguish
    from any future live replay rows.

    Parameters
    ----------
    lottery_type        : "3_STAR" or "4_STAR"
    target_draw         : draw number string (e.g. "115000106")
    target_date         : ISO date string
    strategy_id         : e.g. "star3_digit_freq_box_1bet_dry_run"
    strategy_name       : human-readable name
    history_cutoff_draw : last draw used as history (draw before target)
    predicted           : list of predicted digits (any order)
    actual              : list of actual digits (as stored in DB, sorted)
    bet_index           : 1-based bet index (default 1)

    Returns
    -------
    dict with keys matching strategy_prediction_replays schema (dry_run=1).
    """
    if lottery_type not in STAR_CONFIG:
        raise ValueError(f"Unknown star lottery type: {lottery_type!r}")
    pick_count = STAR_CONFIG[lottery_type]["pick_count"]
    hit_count, exact_hit, overlap = star_calculate_box_score(
        predicted, actual, pick_count
    )
    return {
        "lottery_type": lottery_type,
        "target_draw": target_draw,
        "target_date": target_date,
        "strategy_id": strategy_id,
        "strategy_name": strategy_name,
        "strategy_version": "p227b_box_play_v0.1",
        "history_cutoff_draw": history_cutoff_draw,
        "replay_status": "PREDICTED",
        "predicted_numbers": sorted(predicted),   # store sorted for display
        "actual_numbers": actual,                  # as in DB (already sorted)
        "hit_numbers": sorted(set(predicted) & set(actual)),  # display overlap
        "hit_count": hit_count,                   # 0 or pick_count
        "special_hit": 0,                         # not used for star lotteries
        "dry_run": 1,                             # ALWAYS 1 — never write as 0
        "truth_level": "BOX_PLAY_DRY_RUN_BOX_EXACT",
        "source": "P227B_STAR_BOX_PLAY_DRY_RUN",
        "bet_index": bet_index,
        # Extra diagnostic fields (not in schema — omit before any DB insert)
        "_exact_box_hit": exact_hit,
        "_digit_overlap": overlap,
        "_baseline": get_box_baseline(lottery_type),
        "_play_mode": "box_exact",
        "_straight_play_blocked": STRAIGHT_PLAY_BLOCKED_REASON,
    }
