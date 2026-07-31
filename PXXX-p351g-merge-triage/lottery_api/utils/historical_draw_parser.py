"""P253E — Historical Draw Parser SSOT.

Pure-Python module for historical draw parsing vocabulary, positional-field
validation, sorted-vs-positional semantics, and read-only validation helpers.
Consolidates M1 gap from P252B. Standardises parser source types, positional
coverage status, and sorted/positional semantics previously scattered across
upload scripts and P213x controlled-apply scripts.

Design constraints:
- No DB connection
- No strategy registry dependency
- No production recommendation dependency
- No numpy / scipy — pure stdlib only (json, math, statistics, typing)
- Deterministic output for identical inputs
- No claim of predictive edge
- No betting advice

Vocabulary alignment (P252B M1 gap):
    sorted_numbers      — numbers stored in ascending order (all lottery types)
    positional_numbers  — numbers in original draw order (3_STAR / 4_STAR only)
    pool_draw           — unordered pool draw (BIG_LOTTO, POWER_LOTTO, DAILY_539)
    straight_play       — digit-order matters (3_STAR, 4_STAR)

Positional coverage notes (P253D):
    3_STAR: 5,850 rows, 100% numbers_positional coverage, draw order confirmed
    4_STAR: 5,850 rows, 100% numbers_positional coverage, draw order confirmed
    BIG_LOTTO / POWER_LOTTO / DAILY_539: 0% positional — not needed for pool draw

Usage::

    from lottery_api.utils.historical_draw_parser import (
        PARSER_SOURCE_TYPES,
        POSITIONAL_STATUS,
        SORTING_SEMANTICS,
        normalize_lottery_type,
        validate_numbers_payload,
        validate_positional_payload,
        compare_sorted_vs_positional,
        classify_positional_coverage,
        parser_inventory_entry,
        parser_summary,
    )

    # Check coverage for 3_STAR
    status = classify_positional_coverage(5850, 5850, lottery_type="3_STAR")
    assert status == "complete"

    # Compare sorted vs positional
    result = compare_sorted_vs_positional([1, 2, 3], [3, 1, 2])
    assert result["differs"] is True
"""
from __future__ import annotations

import json
import math
from typing import Any, List, Optional, Sequence, Union

# ---------------------------------------------------------------------------
# Module metadata
# ---------------------------------------------------------------------------

MODULE_VERSION = "1.0"
SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# Vocabulary constants
# ---------------------------------------------------------------------------

# Canonical parser source-type labels (P252B M1 gap)
PARSER_SOURCE_TYPES = {
    "active_parser": (
        "Currently active production parser / ingest route "
        "(e.g. lottery_api/routes/ingest.py)"
    ),
    "official_dry_run_parser": (
        "Official source format validated via dry-run; "
        "no production DB write performed (e.g. P213G, P213I)"
    ),
    "controlled_apply_complete": (
        "Controlled apply script executed and completed; "
        "production DB write authorised and applied (e.g. P213H, P213L)"
    ),
    "historical_import_script": (
        "One-off or historical CSV/TXT import tool; "
        "ad-hoc schema, typically uses legacy DB path (e.g. upload_big_lotto_csv.py)"
    ),
    "archived_or_exploratory_defer": (
        "Archived, exploratory, or diagnostic script; "
        "no active production dependency (e.g. P214B, P214C)"
    ),
    "unknown_needs_scope": "Classification unclear — requires further scoping",
}

# Canonical positional status labels
POSITIONAL_STATUS = {
    "complete":          "100% of rows have numbers_positional populated",
    "partial":           "Some rows have numbers_positional; some are NULL",
    "missing":           "No rows have numbers_positional populated",
    "not_applicable":    (
        "Positional draw order is not meaningful for this lottery type "
        "(pool draw — BIG_LOTTO, POWER_LOTTO, DAILY_539)"
    ),
    "blocked_by_schema": "Schema does not support numbers_positional column",
    "unknown":           "Cannot determine positional status",
}

# Canonical sorting / positional semantics labels
SORTING_SEMANTICS = {
    "sorted_numbers": (
        "`numbers` column — digits stored in ascending sorted order. "
        "Always populated. Correct for pool-draw games."
    ),
    "positional_numbers": (
        "`numbers_positional` column — digits in original draw order. "
        "Required for straight-play analysis of 3_STAR / 4_STAR. "
        "Must NOT be used for pool-draw games."
    ),
    "pool_draw": (
        "Lottery where draw order is irrelevant — "
        "numbers are drawn from a pool independently. "
        "Examples: BIG_LOTTO (1-49 choose 6), POWER_LOTTO (1-38 choose 6), "
        "DAILY_539 (1-39 choose 5)."
    ),
    "straight_play": (
        "Lottery where digit position matters. "
        "A straight-play bet wins only when drawn digits match in exact order. "
        "Examples: 3_STAR (3-digit), 4_STAR (4-digit). "
        "Requires numbers_positional for position-frequency analysis."
    ),
}

# Known pool-draw lottery types (positional data is NOT applicable)
POOL_DRAW_LOTTERY_TYPES = frozenset({
    "BIG_LOTTO", "POWER_LOTTO", "DAILY_539",
    "38_LOTTO", "39_LOTTO", "49_LOTTO",
    "DOUBLE_WIN", "BIG_LOTTO_BONUS", "LOTTO_6_38",
})

# Known straight-play / positional lottery types
POSITIONAL_LOTTERY_TYPES = frozenset({
    "3_STAR", "4_STAR",
})

# Normalisation aliases (lower-case variants → canonical)
_LOTTERY_TYPE_ALIASES: dict[str, str] = {
    "3_star":       "3_STAR",
    "3star":        "3_STAR",
    "three_star":   "3_STAR",
    "daily_star3":  "3_STAR",
    "4_star":       "4_STAR",
    "4star":        "4_STAR",
    "four_star":    "4_STAR",
    "daily_star4":  "4_STAR",
    "big_lotto":    "BIG_LOTTO",
    "biglotto":     "BIG_LOTTO",
    "power_lotto":  "POWER_LOTTO",
    "powerlotto":   "POWER_LOTTO",
    "daily_539":    "DAILY_539",
    "daily539":     "DAILY_539",
    "539":          "DAILY_539",
    "38_lotto":     "38_LOTTO",
    "39_lotto":     "39_LOTTO",
    "49_lotto":     "49_LOTTO",
    "double_win":   "DOUBLE_WIN",
    "big_lotto_bonus": "BIG_LOTTO_BONUS",
    "lotto_6_38":   "LOTTO_6_38",
}

EPSILON = 1e-9


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def normalize_lottery_type(lottery_type: str) -> str:
    """Return canonical lottery-type string.

    Accepts case-insensitive variants and common aliases.

    Args:
        lottery_type: Raw lottery type string (e.g. '3_star', '3_STAR', 'three_star').

    Returns:
        Canonical upper-case lottery type string (e.g. '3_STAR').

    Raises:
        ValueError: If lottery_type is empty or not a string.
    """
    if not isinstance(lottery_type, str):
        raise ValueError(f"lottery_type must be a string, got {type(lottery_type).__name__!r}")
    stripped = lottery_type.strip()
    if not stripped:
        raise ValueError("lottery_type must not be empty")
    # Try direct upper-case match first
    upper = stripped.upper()
    # Map underscore variants
    lower = stripped.lower()
    if lower in _LOTTERY_TYPE_ALIASES:
        return _LOTTERY_TYPE_ALIASES[lower]
    # Return upper-cased if no alias found (pass-through for unknown types)
    return upper


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _parse_numbers(numbers: Any) -> list[int]:
    """Coerce numbers to list[int]. Accepts list, tuple, or JSON string."""
    if isinstance(numbers, str):
        try:
            numbers = json.loads(numbers)
        except json.JSONDecodeError as exc:
            raise ValueError(f"numbers JSON parse failed: {exc}") from exc
    if not hasattr(numbers, "__iter__") or isinstance(numbers, (str, bytes)):
        raise TypeError(f"numbers must be a sequence, got {type(numbers).__name__!r}")
    result = []
    for i, v in enumerate(numbers):
        try:
            result.append(int(v))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"numbers[{i}]={v!r} is not convertible to int") from exc
    return result


def validate_numbers_payload(
    numbers: Any,
    expected_len: Optional[int] = None,
    allow_empty: bool = False,
) -> dict:
    """Validate a numbers payload (sorted canonical numbers list).

    Args:
        numbers: List/tuple/JSON-string of draw numbers.
        expected_len: If set, check that len(numbers) == expected_len.
        allow_empty: If False (default), raises on empty list.

    Returns:
        dict with keys: valid (bool), errors (list), warnings (list),
        numbers (list[int] or None), length (int).

    Never raises for ordinary invalid input — always returns dict.
    """
    errors: list[str] = []
    warnings: list[str] = []
    parsed: Optional[list[int]] = None

    try:
        parsed = _parse_numbers(numbers)
    except (ValueError, TypeError) as exc:
        errors.append(str(exc))
        return {"valid": False, "errors": errors, "warnings": warnings,
                "numbers": None, "length": 0}

    if not allow_empty and len(parsed) == 0:
        errors.append("numbers must not be empty")
        return {"valid": False, "errors": errors, "warnings": warnings,
                "numbers": None, "length": 0}

    if expected_len is not None and len(parsed) != expected_len:
        errors.append(
            f"expected {expected_len} numbers, got {len(parsed)}"
        )

    # Check sorted order for sorted_numbers semantics
    if parsed and parsed != sorted(parsed):
        warnings.append(
            "numbers are not in sorted ascending order — "
            "sorted_numbers semantic expects ascending sort"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "numbers": parsed,
        "length": len(parsed),
    }


def validate_positional_payload(
    numbers_positional: Any,
    expected_len: Optional[int] = None,
    allow_none: bool = True,
) -> dict:
    """Validate a numbers_positional payload (draw-order numbers list).

    Args:
        numbers_positional: List/tuple/JSON-string, or None.
        expected_len: If set, check length.
        allow_none: If True (default), None is valid (pool-draw lottery types).

    Returns:
        dict with keys: valid (bool), errors (list), warnings (list),
        numbers_positional (list[int] or None), is_null (bool), length (int).
    """
    errors: list[str] = []
    warnings: list[str] = []

    if numbers_positional is None or numbers_positional == "":
        if allow_none:
            return {"valid": True, "errors": [], "warnings": [],
                    "numbers_positional": None, "is_null": True, "length": 0}
        errors.append("numbers_positional is NULL but allow_none=False")
        return {"valid": False, "errors": errors, "warnings": warnings,
                "numbers_positional": None, "is_null": True, "length": 0}

    try:
        parsed = _parse_numbers(numbers_positional)
    except (ValueError, TypeError) as exc:
        errors.append(str(exc))
        return {"valid": False, "errors": errors, "warnings": warnings,
                "numbers_positional": None, "is_null": False, "length": 0}

    if expected_len is not None and len(parsed) != expected_len:
        errors.append(
            f"expected {expected_len} positional numbers, got {len(parsed)}"
        )

    # positional_numbers should generally NOT be sorted
    if parsed and parsed == sorted(parsed):
        warnings.append(
            "numbers_positional equals sorted order — "
            "may be a coincidental match rather than confirmed draw order"
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "numbers_positional": parsed,
        "is_null": False,
        "length": len(parsed),
    }


# ---------------------------------------------------------------------------
# Sorted-vs-positional comparison
# ---------------------------------------------------------------------------


def compare_sorted_vs_positional(
    numbers: Any,
    numbers_positional: Any,
) -> dict:
    """Compare sorted canonical numbers against positional draw-order numbers.

    Args:
        numbers: Sorted canonical numbers (list, tuple, or JSON string).
        numbers_positional: Positional draw-order numbers (list, tuple, JSON, or None).

    Returns:
        dict with keys:
            differs (bool) — True when draw order differs from sorted,
            sorted_numbers (list[int]),
            positional_numbers (list[int] or None),
            same_multiset (bool) — True when both contain identical digits,
            position_matches (list[bool]) — per-position match,
            n_matching_positions (int),
            draw_order_confirmed (bool) — True when differs=True and same_multiset=True.
    """
    v_sorted = validate_numbers_payload(numbers, allow_empty=True)
    v_pos = validate_positional_payload(numbers_positional, allow_none=True)

    sorted_nums = v_sorted.get("numbers") or []
    pos_nums = v_pos.get("numbers_positional")

    if pos_nums is None:
        return {
            "differs": False,
            "sorted_numbers": sorted_nums,
            "positional_numbers": None,
            "same_multiset": None,
            "position_matches": [],
            "n_matching_positions": 0,
            "draw_order_confirmed": False,
            "note": "numbers_positional is NULL — cannot compare",
        }

    differs = sorted_nums != pos_nums
    same_multiset = sorted(sorted_nums) == sorted(pos_nums)
    n = min(len(sorted_nums), len(pos_nums))
    pos_matches = [sorted_nums[i] == pos_nums[i] for i in range(n)]

    return {
        "differs": differs,
        "sorted_numbers": sorted_nums,
        "positional_numbers": pos_nums,
        "same_multiset": same_multiset,
        "position_matches": pos_matches,
        "n_matching_positions": sum(pos_matches),
        "draw_order_confirmed": differs and same_multiset,
    }


# ---------------------------------------------------------------------------
# Positional coverage classification
# ---------------------------------------------------------------------------


def classify_positional_coverage(
    row_count: int,
    positional_non_null: int,
    lottery_type: Optional[str] = None,
) -> str:
    """Return canonical POSITIONAL_STATUS key for a lottery type's coverage.

    Args:
        row_count: Total draw rows for this lottery type.
        positional_non_null: Rows with numbers_positional populated.
        lottery_type: Optional canonical lottery type string for semantic check.

    Returns:
        One of POSITIONAL_STATUS keys.
    """
    if row_count < 0 or positional_non_null < 0:
        return "unknown"
    if row_count == 0:
        return "unknown"

    # Pool-draw lottery types: positional is not applicable
    if lottery_type is not None:
        try:
            canonical = normalize_lottery_type(lottery_type)
        except ValueError:
            canonical = None
        if canonical in POOL_DRAW_LOTTERY_TYPES:
            if positional_non_null > 0:
                # Unexpected — flag as unknown
                return "unknown"
            return "not_applicable"

    coverage = positional_non_null / row_count
    if coverage >= 1.0 - EPSILON:
        return "complete"
    if coverage <= EPSILON:
        return "missing"
    return "partial"


# ---------------------------------------------------------------------------
# Parser inventory entry
# ---------------------------------------------------------------------------


def parser_inventory_entry(
    path: str,
    classification: str,
    lottery_types: Sequence[str],
    description: str,
    numbers_positional_support: bool = False,
    schema_contract: Optional[str] = None,
    notes: Optional[str] = None,
) -> dict:
    """Build a structured parser inventory entry.

    Args:
        path: File path relative to repo root.
        classification: One of PARSER_SOURCE_TYPES keys.
        lottery_types: Canonical lottery type strings this parser handles.
        description: Human-readable description.
        numbers_positional_support: Whether this parser populates numbers_positional.
        schema_contract: Description of the input schema contract.
        notes: Optional additional notes.

    Returns:
        Structured dict with no_edge_claim=True.

    Raises:
        ValueError: If classification is not a known PARSER_SOURCE_TYPES key.
    """
    if classification not in PARSER_SOURCE_TYPES:
        raise ValueError(
            f"classification {classification!r} not in PARSER_SOURCE_TYPES. "
            f"Valid: {list(PARSER_SOURCE_TYPES)}"
        )
    canonical_types = []
    for lt in lottery_types:
        try:
            canonical_types.append(normalize_lottery_type(lt))
        except ValueError:
            canonical_types.append(lt)

    return {
        "schema_version": SCHEMA_VERSION,
        "path": path,
        "classification": classification,
        "classification_description": PARSER_SOURCE_TYPES[classification],
        "lottery_types": canonical_types,
        "description": description,
        "numbers_positional_support": numbers_positional_support,
        "schema_contract": schema_contract or "not specified",
        "notes": notes or "",
        "no_edge_claim": True,
        "no_betting_advice": True,
    }


# ---------------------------------------------------------------------------
# Parser summary (canonical SSOT output)
# ---------------------------------------------------------------------------


def parser_summary(
    lottery_type: str,
    parser_source_type: str,
    row_count: int,
    positional_non_null: int,
    sorted_vs_positional_diff_count: Optional[int] = None,
    family_label: Optional[str] = None,
) -> dict:
    """Canonical SSOT parser summary for one lottery type.

    Args:
        lottery_type: Canonical lottery type string.
        parser_source_type: One of PARSER_SOURCE_TYPES keys.
        row_count: Total draw rows.
        positional_non_null: Rows with numbers_positional populated.
        sorted_vs_positional_diff_count: Rows where positional ≠ sorted (optional).
        family_label: Optional audit label.

    Returns:
        dict: Canonical parser summary with schema_version, no_edge_claim=True.

    Raises:
        ValueError: If row_count/positional_non_null are negative, or parser_source_type unknown.
    """
    if row_count < 0:
        raise ValueError(f"row_count must be >= 0, got {row_count!r}")
    if positional_non_null < 0:
        raise ValueError(f"positional_non_null must be >= 0, got {positional_non_null!r}")
    if parser_source_type not in PARSER_SOURCE_TYPES:
        raise ValueError(
            f"parser_source_type {parser_source_type!r} not in PARSER_SOURCE_TYPES"
        )

    canonical = normalize_lottery_type(lottery_type)
    positional_null = row_count - positional_non_null
    coverage = round(positional_non_null / row_count * 100, 2) if row_count > 0 else 0.0
    pos_status = classify_positional_coverage(row_count, positional_non_null, canonical)

    is_pool_draw = canonical in POOL_DRAW_LOTTERY_TYPES
    is_straight_play = canonical in POSITIONAL_LOTTERY_TYPES

    caveat = (
        "numbers column stores sorted ascending digits — "
        "straight-play / positional-frequency analysis must use numbers_positional"
        if is_straight_play
        else "numbers column stores sorted ascending digits; "
             "positional column is not applicable for pool-draw games"
    )

    straight_play_supported = (
        is_straight_play and pos_status == "complete"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_type": "historical_draw_parser_ssot",
        "family_label": family_label or "UNLABELED",
        "lottery_type": canonical,
        "parser_source_type": parser_source_type,
        "parser_source_type_description": PARSER_SOURCE_TYPES[parser_source_type],
        "positional_status": pos_status,
        "positional_status_description": POSITIONAL_STATUS.get(pos_status, ""),
        "row_count": row_count,
        "positional_non_null": positional_non_null,
        "positional_null": positional_null,
        "positional_coverage_rate": coverage,
        "sorted_vs_positional_diff_count": sorted_vs_positional_diff_count,
        "draw_order_confirmed": (
            sorted_vs_positional_diff_count is not None
            and sorted_vs_positional_diff_count > 0
        ),
        "is_pool_draw": is_pool_draw,
        "is_straight_play": is_straight_play,
        "straight_play_position_frequency_supported": straight_play_supported,
        "sorted_storage_caveat": caveat,
        "no_edge_claim": True,
        "no_betting_advice": True,
        "assumptions": [
            "row_count and positional_non_null are from a read-only DB query",
            "numbers column always stores sorted canonical digits",
            "numbers_positional stores draw order only for 3_STAR / 4_STAR",
            "Pool-draw games (BIG_LOTTO / POWER_LOTTO / DAILY_539) do not need positional data",
        ],
        "limitations": [
            "A complete positional status does not imply a deployable prediction edge",
            "Straight-play analysis power may be insufficient (P214B: 3_STAR MARGINAL, 4_STAR INOPERABLE for exact-match)",
            "GREEN randomness does not imply any exploitable signal",
        ],
    }
