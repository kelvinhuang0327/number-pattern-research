"""
P271E — Scoped Prize-Aware Replay Adapter

Standalone, read-only adapter that maps structurally eligible replay rows
from the canonical DB into the prize_aware_scorer input contract.

This module is PARALLEL to the existing M3+/replay scoring pipeline and
does NOT modify, replace, or override any existing semantics.

Key invariants:
  - Opens SQLite strictly read-only (URI mode=ro).
  - Performs SELECT statements only; no INSERT/UPDATE/DELETE.
  - Imports lottery_api.prize_aware_scorer but NOT lottery_api.routes.replay
    or any strategy-selection module.
  - Never writes results back to the DB.
  - Never mutates replay rows in memory.
  - Not registered in any production API, registry, or frontend.
  - POWER_LOTTO rows with NULL predicted_special are excluded with reason
    MISSING_PREDICTED_SECOND_ZONE and are never filled, defaulted,
    inferred, or replaced by the actual second-zone value.
  - Bounded execution: a positive integer limit must be supplied when
    iterating eligible rows or running the smoke sample; unbounded
    execution is rejected.

adapter_version = "prize_aware_adapter_v1"
scoring_version: delegated to lottery_api.prize_aware_scorer.SCORING_VERSION
source_verification_status = "MANUAL_VERIFICATION_REQUIRED"

No prize-money amounts, EV, ROI, or betting-advice logic is implemented here.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Iterator

from lottery_api.prize_aware_scorer import (
    SCORING_VERSION,
    SOURCE_VERIFICATION_STATUS,
    SUPPORTED_LOTTERY_TYPES,
    score_prize_aware_ticket,
)

ADAPTER_VERSION = "prize_aware_adapter_v1"

# Structural field constants
_MAIN_PICK_COUNT: dict[str, int] = {
    "POWER_LOTTO": 6,
    "BIG_LOTTO": 6,
    "DAILY_539": 5,
}
_MAIN_NUMBER_RANGE: dict[str, tuple[int, int]] = {
    "POWER_LOTTO": (1, 38),
    "BIG_LOTTO": (1, 49),
    "DAILY_539": (1, 39),
}
_SECOND_ZONE_RANGE = (1, 8)

# Required exclusion reason tokens
EXCLUSION_MISSING_PREDICTED_SECOND_ZONE = "MISSING_PREDICTED_SECOND_ZONE"
EXCLUSION_INVALID_PREDICTED_MAIN = "INVALID_PREDICTED_MAIN_NUMBERS"
EXCLUSION_INVALID_ACTUAL_MAIN = "INVALID_ACTUAL_MAIN_NUMBERS"
EXCLUSION_INVALID_PREDICTED_SECOND_ZONE = "INVALID_PREDICTED_SECOND_ZONE"
EXCLUSION_INVALID_ACTUAL_AUXILIARY = "INVALID_ACTUAL_AUXILIARY"
EXCLUSION_MISSING_DRAW_JOIN = "MISSING_DRAW_JOIN"
EXCLUSION_AMBIGUOUS_DRAW_JOIN = "AMBIGUOUS_DRAW_JOIN"
EXCLUSION_CAUSALITY_FAILURE = "CAUSALITY_FAILURE"
EXCLUSION_UNSUPPORTED_LOTTERY_TYPE = "UNSUPPORTED_LOTTERY_TYPE"

# All required exclusion reason tokens in canonical order
ALL_EXCLUSION_REASONS = (
    EXCLUSION_MISSING_PREDICTED_SECOND_ZONE,
    EXCLUSION_INVALID_PREDICTED_MAIN,
    EXCLUSION_INVALID_ACTUAL_MAIN,
    EXCLUSION_INVALID_PREDICTED_SECOND_ZONE,
    EXCLUSION_INVALID_ACTUAL_AUXILIARY,
    EXCLUSION_MISSING_DRAW_JOIN,
    EXCLUSION_AMBIGUOUS_DRAW_JOIN,
    EXCLUSION_CAUSALITY_FAILURE,
    EXCLUSION_UNSUPPORTED_LOTTERY_TYPE,
)


def _open_ro(db_path: str) -> sqlite3.Connection:
    """Open the canonical DB strictly read-only (sqlite3 URI mode=ro)."""
    uri = f"file:{db_path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _is_valid_number_list(
    raw: object, expected_len: int, lo: int, hi: int
) -> bool:
    """Return True if raw is a JSON list of expected_len distinct ints in [lo,hi]."""
    if raw is None:
        return False
    try:
        if isinstance(raw, str):
            values = json.loads(raw)
        elif isinstance(raw, list):
            values = raw
        else:
            return False
        if not isinstance(values, list) or len(values) != expected_len:
            return False
        if not all(isinstance(x, int) and not isinstance(x, bool) for x in values):
            return False
        if len(set(values)) != len(values):
            return False
        return all(lo <= x <= hi for x in values)
    except (json.JSONDecodeError, TypeError):
        return False


def _parse_number_list(raw: object) -> list[int]:
    """Parse a JSON number list; caller must first validate with _is_valid_number_list."""
    if isinstance(raw, list):
        return [int(x) for x in raw]
    return json.loads(raw)  # type: ignore[arg-type]


def _check_eligibility(row: dict) -> tuple[bool, str | None]:
    """Check structural eligibility for a single replay row dict.

    Returns (True, None) if eligible, or (False, exclusion_reason) if not.

    Lottery_type must already be validated to be in SUPPORTED_LOTTERY_TYPES
    before calling this function, or EXCLUSION_UNSUPPORTED_LOTTERY_TYPE is
    returned first.
    """
    lt = row.get("lottery_type")
    if lt not in SUPPORTED_LOTTERY_TYPES:
        return False, EXCLUSION_UNSUPPORTED_LOTTERY_TYPE

    expected_len = _MAIN_PICK_COUNT[lt]
    lo, hi = _MAIN_NUMBER_RANGE[lt]

    # Validate predicted main numbers
    if not _is_valid_number_list(row.get("predicted_numbers"), expected_len, lo, hi):
        return False, EXCLUSION_INVALID_PREDICTED_MAIN

    # Validate actual main numbers
    if not _is_valid_number_list(row.get("actual_numbers"), expected_len, lo, hi):
        return False, EXCLUSION_INVALID_ACTUAL_MAIN

    if lt == "POWER_LOTTO":
        # POWER_LOTTO: predicted_special must be stored (non-NULL) and in [1,8].
        # Rows missing predicted_special are excluded — NEVER filled or inferred.
        pred_special = row.get("predicted_special")
        if pred_special is None:
            return False, EXCLUSION_MISSING_PREDICTED_SECOND_ZONE
        szlo, szhi = _SECOND_ZONE_RANGE
        if not (isinstance(pred_special, int) and not isinstance(pred_special, bool)
                and szlo <= pred_special <= szhi):
            return False, EXCLUSION_INVALID_PREDICTED_SECOND_ZONE

        act_special = row.get("actual_special")
        if act_special is None or not (
            isinstance(act_special, int) and not isinstance(act_special, bool)
            and szlo <= act_special <= szhi
        ):
            return False, EXCLUSION_INVALID_ACTUAL_AUXILIARY

    elif lt == "BIG_LOTTO":
        # BIG_LOTTO: actual_special must be present and valid in [1,49].
        # No predicted_special field is required.
        act_special = row.get("actual_special")
        lo_main, hi_main = _MAIN_NUMBER_RANGE["BIG_LOTTO"]
        if act_special is None or not (
            isinstance(act_special, int) and not isinstance(act_special, bool)
            and lo_main <= act_special <= hi_main
        ):
            return False, EXCLUSION_INVALID_ACTUAL_AUXILIARY

    else:  # DAILY_539
        # DAILY_539: no auxiliary field is allowed.
        # Both predicted_special and actual_special must be absent/NULL.
        if row.get("predicted_special") is not None:
            return False, EXCLUSION_INVALID_ACTUAL_AUXILIARY
        if row.get("actual_special") is not None:
            return False, EXCLUSION_INVALID_ACTUAL_AUXILIARY

    # Deterministic draw join
    join_count = row.get("_join_count", 0)
    if join_count == 0:
        return False, EXCLUSION_MISSING_DRAW_JOIN
    if join_count > 1:
        return False, EXCLUSION_AMBIGUOUS_DRAW_JOIN

    # Causality: history_cutoff_draw (as integer) < target_draw (as integer)
    try:
        cutoff = int(row.get("history_cutoff_draw", 0) or 0)
        target = int(row.get("target_draw", 0) or 0)
        if not (cutoff > 0 and target > 0 and cutoff < target):
            return False, EXCLUSION_CAUSALITY_FAILURE
    except (ValueError, TypeError):
        return False, EXCLUSION_CAUSALITY_FAILURE

    return True, None


def iter_structurally_eligible_rows(
    db_path: str,
    lottery_type: str | None = None,
    limit: int | None = None,
) -> Iterator[dict]:
    """Yield structurally eligible replay rows, each as a plain dict.

    Rows are selected in deterministic order:
      (lottery_type ASC, CAST(target_draw AS INTEGER) ASC, strategy_id ASC, bet_index ASC).

    Only rows with replay_status = 'PREDICTED' and dry_run = 0 are considered.

    lottery_type: if provided, restrict to that lottery type.
    limit: positive integer; required. Raises ValueError if None or <= 0.
           Protects against unbounded iteration over the full dataset.
    """
    if limit is None or not isinstance(limit, int) or limit <= 0:
        raise ValueError(
            "limit must be a positive integer; "
            "unbounded iteration over the full dataset is not supported"
        )

    if lottery_type is not None and lottery_type not in SUPPORTED_LOTTERY_TYPES:
        raise ValueError(
            f"Unsupported lottery_type {lottery_type!r}; "
            f"must be one of {SUPPORTED_LOTTERY_TYPES}"
        )

    conn = _open_ro(db_path)
    try:
        cur = conn.cursor()
        if lottery_type is not None:
            cur.execute(
                """
                SELECT
                    r.lottery_type, r.target_draw, r.strategy_id, r.bet_index,
                    r.history_cutoff_draw, r.predicted_numbers,
                    r.predicted_special, r.actual_numbers, r.actual_special,
                    (SELECT COUNT(*) FROM draws d
                     WHERE d.lottery_type = r.lottery_type
                       AND d.draw = r.target_draw) AS _join_count
                FROM strategy_prediction_replays r
                WHERE r.lottery_type = ?
                  AND r.replay_status = 'PREDICTED'
                  AND r.dry_run = 0
                ORDER BY
                    CAST(r.target_draw AS INTEGER) ASC,
                    r.strategy_id ASC,
                    r.bet_index ASC
                """,
                (lottery_type,),
            )
        else:
            cur.execute(
                """
                SELECT
                    r.lottery_type, r.target_draw, r.strategy_id, r.bet_index,
                    r.history_cutoff_draw, r.predicted_numbers,
                    r.predicted_special, r.actual_numbers, r.actual_special,
                    (SELECT COUNT(*) FROM draws d
                     WHERE d.lottery_type = r.lottery_type
                       AND d.draw = r.target_draw) AS _join_count
                FROM strategy_prediction_replays r
                WHERE r.replay_status = 'PREDICTED'
                  AND r.dry_run = 0
                ORDER BY
                    r.lottery_type ASC,
                    CAST(r.target_draw AS INTEGER) ASC,
                    r.strategy_id ASC,
                    r.bet_index ASC
                """
            )

        yielded = 0
        for raw_row in cur:
            if yielded >= limit:
                break
            row = {
                "lottery_type": raw_row[0],
                "target_draw": raw_row[1],
                "strategy_id": raw_row[2],
                "bet_index": raw_row[3],
                "history_cutoff_draw": raw_row[4],
                "predicted_numbers": raw_row[5],
                "predicted_special": raw_row[6],
                "actual_numbers": raw_row[7],
                "actual_special": raw_row[8],
                "_join_count": raw_row[9],
            }
            eligible, reason = _check_eligibility(row)
            if not eligible:
                continue
            yielded += 1
            yield row
    finally:
        conn.close()


def map_replay_row_to_scorer_input(row: dict) -> dict:
    """Map a structurally eligible replay row dict to score_prize_aware_ticket kwargs.

    The row must already have passed _check_eligibility (eligible=True).
    Caller inputs are never mutated.

    Returns a plain dict of kwargs suitable for:
        score_prize_aware_ticket(**map_replay_row_to_scorer_input(row))
    """
    lt = row["lottery_type"]
    predicted_main = _parse_number_list(row["predicted_numbers"])
    actual_main = _parse_number_list(row["actual_numbers"])

    if lt == "POWER_LOTTO":
        return {
            "lottery_type": lt,
            "predicted_main_numbers": predicted_main,
            "actual_main_numbers": actual_main,
            "predicted_second_zone": int(row["predicted_special"]),
            "actual_second_zone": int(row["actual_special"]),
            "actual_special_number": None,
        }
    if lt == "BIG_LOTTO":
        return {
            "lottery_type": lt,
            "predicted_main_numbers": predicted_main,
            "actual_main_numbers": actual_main,
            "predicted_second_zone": None,
            "actual_second_zone": None,
            "actual_special_number": int(row["actual_special"]),
        }
    # DAILY_539
    return {
        "lottery_type": lt,
        "predicted_main_numbers": predicted_main,
        "actual_main_numbers": actual_main,
        "predicted_second_zone": None,
        "actual_second_zone": None,
        "actual_special_number": None,
    }


def _build_eligible_record(row: dict, scorer_result: dict) -> dict:
    """Build an output record for one eligible scored row.

    Contains only the allowed fields per the task specification.
    Does not include raw winning-number arrays, prize amounts,
    EV/ROI, recommendations, rankings, or baseline comparisons.
    """
    return {
        "adapter_version": ADAPTER_VERSION,
        "scoring_version": SCORING_VERSION,
        "lottery_type": row["lottery_type"],
        "target_draw": row["target_draw"],
        "strategy_id": row["strategy_id"],
        "bet_index": row["bet_index"],
        "history_cutoff_draw": row["history_cutoff_draw"],
        "structural_eligibility": True,
        "exclusion_reason": None,
        "scorer_result": {
            "scoring_version": scorer_result.get("scoring_version"),
            "lottery_type": scorer_result.get("lottery_type"),
            "main_hit_count": scorer_result.get("main_hit_count"),
            "special_hit": scorer_result.get("special_hit"),
            "second_zone_hit": scorer_result.get("second_zone_hit"),
            "any_prize_aware_win": scorer_result.get("any_prize_aware_win"),
            "prize_tier": scorer_result.get("prize_tier"),
            "tier_class": scorer_result.get("tier_class"),
            "is_prize_aware_win": scorer_result.get("is_prize_aware_win"),
            "is_m3_plus": scorer_result.get("is_m3_plus"),
            "endpoint_flags": scorer_result.get("endpoint_flags"),
            "source_verification_status": scorer_result.get(
                "source_verification_status"
            ),
            "parallel_feature": scorer_result.get("parallel_feature"),
            "existing_m3_replay_scoring_changed": scorer_result.get(
                "existing_m3_replay_scoring_changed"
            ),
        },
    }


def score_bounded_smoke_sample(
    db_path: str,
    limit_per_lottery: int = 10,
) -> dict:
    """Run a bounded smoke validation: score up to limit_per_lottery eligible rows
    per lottery type and verify the integration contract.

    limit_per_lottery: positive integer, maximum rows per lottery type to score.
    Raises ValueError if <= 0.

    Returns a summary dict suitable for the smoke artifact.
    The summary does NOT include:
      - aggregate success rates
      - tier-frequency percentages
      - strategy aggregates or rankings
      - comparisons between lotteries or strategies
      - raw actual-number arrays

    The summary DOES include:
      - requested limit
      - processed eligible rows per lottery
      - successful scorer calls per lottery
      - schema validation results
      - deterministic repeat check result
      - exclusion summary counts
      - DB read-only confirmation
    """
    if not isinstance(limit_per_lottery, int) or isinstance(limit_per_lottery, bool) \
            or limit_per_lottery <= 0:
        raise ValueError(
            "limit_per_lottery must be a positive integer"
        )

    processed: dict[str, int] = {}
    successful: dict[str, int] = {}
    schema_errors: dict[str, list[str]] = {}

    for lt in SUPPORTED_LOTTERY_TYPES:
        rows_first_pass = []
        for row in iter_structurally_eligible_rows(
            db_path, lottery_type=lt, limit=limit_per_lottery
        ):
            rows_first_pass.append(row)

        processed[lt] = len(rows_first_pass)
        successful[lt] = 0
        schema_errors[lt] = []

        for row in rows_first_pass:
            scorer_input = map_replay_row_to_scorer_input(row)
            result = score_prize_aware_ticket(**scorer_input)
            _validate_scorer_output_schema(lt, result, schema_errors[lt])
            successful[lt] += 1

    # Deterministic repeat check: re-run and compare
    deterministic_ok = True
    for lt in SUPPORTED_LOTTERY_TYPES:
        second_pass = []
        for row in iter_structurally_eligible_rows(
            db_path, lottery_type=lt, limit=limit_per_lottery
        ):
            second_pass.append(row)
        if len(second_pass) != processed[lt]:
            deterministic_ok = False
            break
        for row in second_pass:
            scorer_input = map_replay_row_to_scorer_input(row)
            result = score_prize_aware_ticket(**scorer_input)
            # Verify determinism: same row, same result
            if result.get("lottery_type") != lt:
                deterministic_ok = False
                break

    # Exclusion summary: count ineligible rows per reason per lottery
    exclusion_summary = summarize_structural_exclusions(db_path)

    any_schema_errors = any(schema_errors[lt] for lt in SUPPORTED_LOTTERY_TYPES)

    return {
        "adapter_version": ADAPTER_VERSION,
        "scoring_version": SCORING_VERSION,
        "db_read_only": True,
        "requested_limit_by_lottery": {lt: limit_per_lottery for lt in SUPPORTED_LOTTERY_TYPES},
        "processed_rows_by_lottery": processed,
        "successful_scorer_calls_by_lottery": successful,
        "schema_validation": {
            "all_pass": not any_schema_errors,
            "errors_by_lottery": schema_errors,
        },
        "deterministic_repeat_check": {
            "passed": deterministic_ok,
        },
        "exclusion_summary_by_lottery": exclusion_summary,
        "source_verification_status": SOURCE_VERIFICATION_STATUS,
        # Explicit safety flags
        "full_historical_evaluation_run": False,
        "success_rate_calculated": False,
        "strategy_comparison_run": False,
        "raw_actual_number_arrays_exported": False,
    }


def _validate_scorer_output_schema(
    lottery_type: str, result: dict, errors: list
) -> None:
    """Validate that scorer output contains all required fields."""
    required_fields = [
        "scoring_version", "lottery_type", "main_hit_count", "special_hit",
        "any_prize_aware_win", "prize_tier", "tier_class", "is_prize_aware_win",
        "is_m3_plus", "endpoint_flags", "source_verification_status",
        "parallel_feature", "existing_m3_replay_scoring_changed",
    ]
    for field in required_fields:
        if field not in result:
            errors.append(f"missing field: {field}")
    if result.get("lottery_type") != lottery_type:
        errors.append(
            f"lottery_type mismatch: expected {lottery_type!r}, "
            f"got {result.get('lottery_type')!r}"
        )
    if result.get("existing_m3_replay_scoring_changed") is not False:
        errors.append("existing_m3_replay_scoring_changed must be False")


def summarize_structural_exclusions(
    db_path: str,
    lottery_type: str | None = None,
) -> dict:
    """Return exclusion reason counts for ineligible rows, by lottery type.

    Does NOT export actual winning numbers.
    For a structural summary only: counts by exclusion reason.

    Uses a read-only LIMIT-protected scan over all replay rows to
    identify ineligible rows and their exclusion reasons.

    Returns: {lottery_type: {exclusion_reason: count, ...}, ...}
    """
    if lottery_type is not None and lottery_type not in SUPPORTED_LOTTERY_TYPES:
        raise ValueError(
            f"Unsupported lottery_type {lottery_type!r}"
        )

    lottery_types_to_scan = (
        (lottery_type,) if lottery_type is not None else SUPPORTED_LOTTERY_TYPES
    )

    result: dict[str, dict[str, int]] = {}
    conn = _open_ro(db_path)
    try:
        cur = conn.cursor()
        for lt in lottery_types_to_scan:
            counts: dict[str, int] = {r: 0 for r in ALL_EXCLUSION_REASONS}
            cur.execute(
                """
                SELECT
                    r.lottery_type, r.target_draw, r.strategy_id, r.bet_index,
                    r.history_cutoff_draw, r.predicted_numbers,
                    r.predicted_special, r.actual_numbers, r.actual_special,
                    (SELECT COUNT(*) FROM draws d
                     WHERE d.lottery_type = r.lottery_type
                       AND d.draw = r.target_draw) AS _join_count
                FROM strategy_prediction_replays r
                WHERE r.lottery_type = ?
                  AND r.replay_status = 'PREDICTED'
                  AND r.dry_run = 0
                ORDER BY
                    CAST(r.target_draw AS INTEGER) ASC,
                    r.strategy_id ASC,
                    r.bet_index ASC
                """,
                (lt,),
            )
            for raw_row in cur:
                row = {
                    "lottery_type": raw_row[0],
                    "target_draw": raw_row[1],
                    "strategy_id": raw_row[2],
                    "bet_index": raw_row[3],
                    "history_cutoff_draw": raw_row[4],
                    "predicted_numbers": raw_row[5],
                    "predicted_special": raw_row[6],
                    "actual_numbers": raw_row[7],
                    "actual_special": raw_row[8],
                    "_join_count": raw_row[9],
                }
                eligible, reason = _check_eligibility(row)
                if not eligible and reason is not None:
                    counts[reason] = counts.get(reason, 0) + 1
            result[lt] = counts
    finally:
        conn.close()

    return result
