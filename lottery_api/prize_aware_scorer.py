"""
P271C — Standalone Prize-Aware Scorer (Pure Function Module)

Parallel evaluation track alongside existing M3+/replay scoring.
Does NOT replace, override, migrate, deprecate, or change existing
M3+/replay scoring semantics (P265A SSOT: hit_count >= 3,
special_hit excluded). Existing M3+/replay scoring remains UNCHANGED.

Source contract: outputs/research/p271b_official_prize_rule_scoring_engine_design_20260611.json
(tier_mapping_by_lottery, endpoint_mapping_by_lottery, unit_test_fixture_matrix)

This module:
  - is deterministic and side-effect free
  - performs no file I/O, DB access, network access, or env access
  - performs no logging writes
  - does not mutate caller inputs
  - does not import replay.py, DB/repository, or strategy-selection modules
  - is not registered in any production registry, API, or replay pipeline

scoring_version = "prize_aware_v1"
source_verification_status = "MANUAL_VERIFICATION_REQUIRED"
  (Official Taiwan Lottery prize-table pages are JavaScript SPAs and could not
  be machine-verified in P271B/P271C. Tier mappings are sourced from internal
  repo documentation — lottery_api/CLAUDE.md calc_prize docstrings and
  calculate_win_probability.py — per the P271B design artifact.)

No prize-money amounts, EV, ROI, or betting-advice logic is implemented here.
"""

from __future__ import annotations

SCORING_VERSION = "prize_aware_v1"
SOURCE_VERIFICATION_STATUS = "MANUAL_VERIFICATION_REQUIRED"

SUPPORTED_LOTTERY_TYPES = ("POWER_LOTTO", "BIG_LOTTO", "DAILY_539")

_MAIN_PICK_COUNT = {
    "POWER_LOTTO": 6,
    "BIG_LOTTO": 6,
    "DAILY_539": 5,
}

_MAIN_NUMBER_RANGE = {
    "POWER_LOTTO": (1, 38),
    "BIG_LOTTO": (1, 49),
    "DAILY_539": (1, 39),
}

_SECOND_ZONE_RANGE = (1, 8)  # POWER_LOTTO 特別號 (second area)


# ---------------------------------------------------------------------------
# Tier classification (per P271B tier_mapping_by_lottery)
# ---------------------------------------------------------------------------

def classify_power_lotto_tier(hit_count: int, special_hit: int) -> str:
    """Classify a POWER_LOTTO (威力彩) row into its prize tier.

    hit_count: number of first-zone (1-38, pick 6) main-number hits, 0-6.
    special_hit: 1 if predicted second-zone number == actual second-zone
        number, else 0.
    """
    _validate_hit_count("POWER_LOTTO", hit_count)
    _validate_special_hit(special_hit)

    if hit_count == 6 and special_hit == 1:
        return "POWER_FIRST_PRIZE"
    if hit_count == 6 and special_hit == 0:
        return "POWER_SECOND_PRIZE"
    if hit_count == 5 and special_hit == 1:
        return "POWER_THIRD_PRIZE"
    if hit_count == 5 and special_hit == 0:
        return "POWER_FOURTH_PRIZE"
    if hit_count == 4 and special_hit == 1:
        return "POWER_FIFTH_PRIZE"
    if hit_count == 4 and special_hit == 0:
        return "POWER_SIXTH_PRIZE"
    if hit_count == 3 and special_hit == 1:
        return "POWER_SEVENTH_PRIZE"
    if hit_count == 2 and special_hit == 1:
        return "POWER_EIGHTH_PRIZE"
    if hit_count == 3 and special_hit == 0:
        return "POWER_NINTH_PRIZE"
    if hit_count == 1 and special_hit == 1:
        return "POWER_CONSOLATION_PRIZE"
    return "POWER_NO_PRIZE"


def classify_big_lotto_tier(hit_count: int, special_hit: int) -> str:
    """Classify a BIG_LOTTO (大樂透) row into its prize tier.

    hit_count: number of main-number (1-49, pick 6) hits, 0-6.
    special_hit: 1 if the actual special number is contained in the
        predicted main numbers, else 0.
    """
    _validate_hit_count("BIG_LOTTO", hit_count)
    _validate_special_hit(special_hit)

    if hit_count == 6:
        # 頭獎: special is irrelevant when hit_count == 6
        return "BIG_FIRST_PRIZE"
    if hit_count == 5 and special_hit == 1:
        return "BIG_SECOND_PRIZE"
    if hit_count == 5 and special_hit == 0:
        return "BIG_THIRD_PRIZE"
    if hit_count == 4 and special_hit == 1:
        return "BIG_FOURTH_PRIZE"
    if hit_count == 4 and special_hit == 0:
        return "BIG_FIFTH_PRIZE"
    if hit_count == 3 and special_hit == 1:
        return "BIG_SIXTH_PRIZE"
    if hit_count == 3 and special_hit == 0:
        return "BIG_SEVENTH_PRIZE"
    if hit_count == 2 and special_hit == 1:
        return "BIG_CONSOLATION_PRIZE"
    return "BIG_NO_PRIZE"


def classify_daily_539_tier(hit_count: int) -> str:
    """Classify a DAILY_539 (今彩539) row into its prize tier.

    hit_count: number of main-number (1-39, pick 5) hits, 0-5.
    DAILY_539 has no special number and no second zone.
    """
    _validate_hit_count("DAILY_539", hit_count)

    if hit_count == 5:
        return "D539_FIRST_PRIZE"
    if hit_count == 4:
        return "D539_SECOND_PRIZE"
    if hit_count == 3:
        return "D539_THIRD_PRIZE"
    if hit_count == 2:
        return "D539_FOURTH_PRIZE"
    return "D539_NO_PRIZE"


def classify_tier(lottery_type: str, hit_count: int, special_hit: int) -> str:
    """Dispatch to the game-specific tier classifier.

    Raises ValueError for unsupported lottery_type.
    """
    _validate_lottery_type(lottery_type)

    if lottery_type == "POWER_LOTTO":
        return classify_power_lotto_tier(hit_count, special_hit)
    if lottery_type == "BIG_LOTTO":
        return classify_big_lotto_tier(hit_count, special_hit)
    # DAILY_539
    if special_hit != 0:
        raise ValueError(
            "DAILY_539 has no special number; special_hit must be 0, "
            f"got {special_hit!r}"
        )
    return classify_daily_539_tier(hit_count)


def is_any_prize_aware_win(lottery_type: str, hit_count: int, special_hit: int) -> bool:
    """True if tier_class is not the NO_PRIZE tier for lottery_type, else False."""
    tier_class = classify_tier(lottery_type, hit_count, special_hit)
    return not tier_class.endswith("_NO_PRIZE")


# ---------------------------------------------------------------------------
# Per-row scoring (parallel diagnostic alongside M3+)
# ---------------------------------------------------------------------------

def score_replay_row(lottery_type: str, hit_count: int, special_hit: int) -> dict:
    """Score a single replay row under the prize-aware tier rules.

    Returns a plain dict containing the prize-aware classification AND the
    existing M3+ diagnostic (hit_count >= 3, special_hit excluded — P265A SSOT,
    unchanged) side by side. Neither metric replaces the other.

    Pure function: no DB, file, network, or environment access; does not
    mutate any input.
    """
    _validate_lottery_type(lottery_type)
    _validate_hit_count(lottery_type, hit_count)
    _validate_special_hit(special_hit)
    if lottery_type == "DAILY_539" and special_hit != 0:
        raise ValueError(
            "DAILY_539 has no special number; special_hit must be 0, "
            f"got {special_hit!r}"
        )

    tier_class = classify_tier(lottery_type, hit_count, special_hit)
    is_prize_aware_win = not tier_class.endswith("_NO_PRIZE")
    is_m3_plus = hit_count >= 3

    any_prize_aware_win = is_prize_aware_win
    m3_plus_diagnostic = is_m3_plus
    if lottery_type == "POWER_LOTTO":
        consolation_or_above = hit_count >= 1 and special_hit == 1
    elif lottery_type == "BIG_LOTTO":
        consolation_or_above = hit_count == 2 and special_hit == 1
    else:  # DAILY_539
        consolation_or_above = hit_count == 2

    endpoint_flags = {
        "any_prize_aware_win": any_prize_aware_win,
        "m3_plus_diagnostic": m3_plus_diagnostic,
        "consolation_or_above": consolation_or_above,
    }

    return {
        "scoring_version": SCORING_VERSION,
        "lottery_type": lottery_type,
        "main_hit_count": hit_count,
        "special_hit": special_hit,
        "second_zone_hit": special_hit if lottery_type == "POWER_LOTTO" else None,
        "any_prize_aware_win": any_prize_aware_win,
        "prize_tier": tier_class,
        "tier_class": tier_class,
        "is_prize_aware_win": is_prize_aware_win,
        "is_m3_plus": is_m3_plus,
        "endpoint_flags": endpoint_flags,
        "source_verification_status": SOURCE_VERIFICATION_STATUS,
        "parallel_feature": True,
        "existing_m3_replay_scoring_changed": False,
    }


# ---------------------------------------------------------------------------
# Public ticket-level entry point
# ---------------------------------------------------------------------------

def score_prize_aware_ticket(
    lottery_type,
    predicted_main_numbers,
    actual_main_numbers,
    predicted_second_zone=None,
    actual_second_zone=None,
    actual_special_number=None,
):
    """Score one prize-aware ticket from raw predicted/actual numbers.

    Pure function: deterministic, side-effect free, performs no I/O.
    Does not mutate any caller-supplied list/sequence.

    lottery_type: one of "POWER_LOTTO", "BIG_LOTTO", "DAILY_539".

    predicted_main_numbers / actual_main_numbers: sequences of distinct
        integers within the valid range for lottery_type (length 6 for
        POWER_LOTTO/BIG_LOTTO, length 5 for DAILY_539).

    POWER_LOTTO only:
        predicted_second_zone / actual_second_zone: integers in 1-8
        (second-area / 特別號 prediction and result). Both are required.
        actual_special_number must be None (POWER_LOTTO has no
        first-zone "special number" concept distinct from second zone).

    BIG_LOTTO only:
        actual_special_number: the drawn special number (int, 1-49,
        not in actual_main_numbers). Required.
        special_hit = actual_special_number in predicted_main_numbers.
        predicted_second_zone / actual_second_zone must be None.

    DAILY_539 only:
        predicted_second_zone, actual_second_zone, and
        actual_special_number must all be None.

    Returns the same result contract as score_replay_row(), with
    main_hit_count and special_hit derived from the raw number lists.
    """
    _validate_lottery_type(lottery_type)

    predicted_main = _validate_number_list(
        lottery_type, "predicted_main_numbers", predicted_main_numbers
    )
    actual_main = _validate_number_list(
        lottery_type, "actual_main_numbers", actual_main_numbers
    )

    if lottery_type == "POWER_LOTTO":
        if predicted_second_zone is None or actual_second_zone is None:
            raise ValueError(
                "POWER_LOTTO requires predicted_second_zone and "
                "actual_second_zone"
            )
        if actual_special_number is not None:
            raise ValueError(
                "POWER_LOTTO does not use actual_special_number "
                "(use actual_second_zone instead)"
            )
        predicted_sz = _validate_second_zone_value(
            "predicted_second_zone", predicted_second_zone
        )
        actual_sz = _validate_second_zone_value(
            "actual_second_zone", actual_second_zone
        )
        special_hit = 1 if predicted_sz == actual_sz else 0

    elif lottery_type == "BIG_LOTTO":
        if predicted_second_zone is not None or actual_second_zone is not None:
            raise ValueError(
                "BIG_LOTTO does not use predicted_second_zone / "
                "actual_second_zone"
            )
        if actual_special_number is None:
            raise ValueError("BIG_LOTTO requires actual_special_number")
        actual_special = _validate_single_number(
            lottery_type, "actual_special_number", actual_special_number
        )
        if actual_special in actual_main:
            raise ValueError(
                "actual_special_number overlaps with actual_main_numbers "
                "(BIG_LOTTO special number must be distinct from the "
                "drawn main numbers)"
            )
        special_hit = 1 if actual_special in predicted_main else 0

    else:  # DAILY_539
        if (
            predicted_second_zone is not None
            or actual_second_zone is not None
            or actual_special_number is not None
        ):
            raise ValueError(
                "DAILY_539 does not use predicted_second_zone, "
                "actual_second_zone, or actual_special_number"
            )
        special_hit = 0

    main_hit_count = len(set(predicted_main) & set(actual_main))

    return score_replay_row(lottery_type, main_hit_count, special_hit)


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def _validate_lottery_type(lottery_type) -> None:
    if lottery_type not in SUPPORTED_LOTTERY_TYPES:
        raise ValueError(
            f"Unsupported lottery_type: {lottery_type!r}. "
            f"Must be one of {SUPPORTED_LOTTERY_TYPES}"
        )


def _validate_hit_count(lottery_type: str, hit_count) -> None:
    if isinstance(hit_count, bool) or not isinstance(hit_count, int):
        raise ValueError(f"hit_count must be an int, got {hit_count!r}")
    max_count = _MAIN_PICK_COUNT[lottery_type]
    if hit_count < 0 or hit_count > max_count:
        raise ValueError(
            f"hit_count for {lottery_type} must be 0-{max_count}, "
            f"got {hit_count!r}"
        )


def _validate_special_hit(special_hit) -> None:
    if isinstance(special_hit, bool) or not isinstance(special_hit, int):
        raise ValueError(f"special_hit must be an int, got {special_hit!r}")
    if special_hit not in (0, 1):
        raise ValueError(f"special_hit must be 0 or 1, got {special_hit!r}")


def _validate_second_zone_value(field_name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an int, got {value!r}")
    lo, hi = _SECOND_ZONE_RANGE
    if value < lo or value > hi:
        raise ValueError(
            f"{field_name} must be {lo}-{hi}, got {value!r}"
        )
    return value


def _validate_single_number(lottery_type: str, field_name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an int, got {value!r}")
    lo, hi = _MAIN_NUMBER_RANGE[lottery_type]
    if value < lo or value > hi:
        raise ValueError(
            f"{field_name} for {lottery_type} must be {lo}-{hi}, "
            f"got {value!r}"
        )
    return value


def _validate_number_list(lottery_type: str, field_name: str, numbers) -> list:
    expected_count = _MAIN_PICK_COUNT[lottery_type]
    lo, hi = _MAIN_NUMBER_RANGE[lottery_type]

    if numbers is None or isinstance(numbers, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of ints")

    try:
        values = list(numbers)
    except TypeError:
        raise ValueError(f"{field_name} must be a sequence of ints")

    if len(values) != expected_count:
        raise ValueError(
            f"{field_name} for {lottery_type} must contain exactly "
            f"{expected_count} numbers, got {len(values)}"
        )

    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"{field_name} entries must be ints, got {value!r}"
            )
        if value < lo or value > hi:
            raise ValueError(
                f"{field_name} entries for {lottery_type} must be "
                f"{lo}-{hi}, got {value!r}"
            )

    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must not contain duplicate numbers")

    return values
