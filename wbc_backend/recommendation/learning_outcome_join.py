"""Fail-closed learning outcome join guard.

P205B keeps this logic local/replay-only.  It does not score, rank, publish,
write data, or optimize strategy behavior; it only decides whether a
recommendation row may be counted as learning evidence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from wbc_backend.recommendation.provenance_contract import (
    NON_REAL_EVIDENCE_ODDS_SOURCES,
    PROVENANCE_CONTRACT_VERSION,
    ProvenanceContractError,
    validate_provenance_contract,
)


MISSING_CONTRACT = "missing_contract"
LEGACY_CONTRACT = "legacy_contract"
MALFORMED_CONTRACT = "malformed_contract"
NOT_LEARNING_ELIGIBLE = "not_learning_eligible"
MISSING_GAME_ID = "missing_game_id"
OUTCOME_NOT_FOUND = "outcome_not_found"
AMBIGUOUS_OUTCOME_JOIN = "ambiguous_outcome_join"
MISSING_PREDICTION_AS_OF_UTC = "missing_prediction_as_of_utc"
STALE_OR_INVALID_AS_OF = "stale_or_invalid_as_of"
RESULT_TIMESTAMP_MISSING = "result_timestamp_missing"

RESULT_TIMESTAMP_FIELDS: tuple[str, ...] = (
    "result_timestamp_utc",
    "outcome_timestamp_utc",
    "result_final_at_utc",
    "game_final_at_utc",
    "game_end_utc",
    "game_end_time_utc",
)


@dataclass(frozen=True)
class LearningOutcomeJoinDecision:
    """Decision returned by the P205B guard."""

    learning_eligible: bool
    block_reason: str | None
    recommendation_game_identity: str = ""
    outcome_game_identity: str = ""


def stable_game_identity(row: Mapping[str, Any]) -> str:
    """Return a stable game identity without team/date fuzzy matching."""
    for key in ("game_pk", "gamePk", "mlb_game_pk"):
        value = row.get(key)
        if isinstance(value, bool) or value is None:
            continue
        text = str(value).strip()
        if text:
            return text

    game_id = row.get("game_id")
    if not isinstance(game_id, str) or not game_id.strip():
        return ""

    text = game_id.strip()
    for separator in ("_", "-"):
        if separator in text:
            suffix = text.rsplit(separator, 1)[-1].strip()
            if suffix.isdigit():
                return suffix
    if text.isdigit():
        return text
    return ""


def index_outcomes_by_stable_identity(
    outcomes: Iterable[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    """Index outcomes by stable identity, preserving duplicates as ambiguous."""
    index: dict[str, list[Mapping[str, Any]]] = {}
    for outcome in outcomes:
        identity = stable_game_identity(outcome)
        if identity:
            index.setdefault(identity, []).append(outcome)
    return index


def outcome_result_timestamp(outcome: Mapping[str, Any]) -> str:
    for field in RESULT_TIMESTAMP_FIELDS:
        value = outcome.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _parse_utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _provenance_block_reason(rec: Mapping[str, Any]) -> str | None:
    if "source_trace" not in rec or rec.get("source_trace") is None:
        return MISSING_CONTRACT

    source_trace = rec.get("source_trace")
    if not isinstance(source_trace, dict):
        return MALFORMED_CONTRACT

    version = source_trace.get("provenance_contract_version")
    if version != PROVENANCE_CONTRACT_VERSION:
        return LEGACY_CONTRACT

    if (
        source_trace.get("learning_eligible") is True
        and not source_trace.get("prediction_as_of_utc")
    ):
        return MISSING_PREDICTION_AS_OF_UTC

    try:
        validate_provenance_contract(source_trace)
    except ProvenanceContractError:
        return MALFORMED_CONTRACT

    if source_trace.get("learning_eligible") is not True:
        return NOT_LEARNING_ELIGIBLE
    if source_trace.get("odds_source") in NON_REAL_EVIDENCE_ODDS_SOURCES:
        return NOT_LEARNING_ELIGIBLE
    if source_trace.get("odds_is_market_observed") is not True:
        return NOT_LEARNING_ELIGIBLE
    if source_trace.get("edge_is_real_evidence") is not True:
        return NOT_LEARNING_ELIGIBLE
    if not source_trace.get("prediction_as_of_utc"):
        return MISSING_PREDICTION_AS_OF_UTC

    return None


def evaluate_learning_outcome_join(
    rec: Mapping[str, Any],
    outcomes: Iterable[Mapping[str, Any]],
) -> LearningOutcomeJoinDecision:
    """Return whether ``rec`` can be accepted as learning evidence."""
    provenance_reason = _provenance_block_reason(rec)
    rec_identity = stable_game_identity(rec)
    if provenance_reason:
        return LearningOutcomeJoinDecision(False, provenance_reason, rec_identity)

    if not rec_identity:
        return LearningOutcomeJoinDecision(False, MISSING_GAME_ID)

    outcome_index = index_outcomes_by_stable_identity(outcomes)
    candidates = outcome_index.get(rec_identity, [])
    if not candidates:
        return LearningOutcomeJoinDecision(False, OUTCOME_NOT_FOUND, rec_identity)
    if len(candidates) > 1:
        return LearningOutcomeJoinDecision(False, AMBIGUOUS_OUTCOME_JOIN, rec_identity)

    outcome = candidates[0]
    outcome_identity = stable_game_identity(outcome)
    result_timestamp = outcome_result_timestamp(outcome)
    if not result_timestamp:
        return LearningOutcomeJoinDecision(
            False,
            RESULT_TIMESTAMP_MISSING,
            rec_identity,
            outcome_identity,
        )

    source_trace = rec["source_trace"]
    prediction_as_of = _parse_utc_datetime(source_trace.get("prediction_as_of_utc"))
    result_as_of = _parse_utc_datetime(result_timestamp)
    if prediction_as_of is None:
        return LearningOutcomeJoinDecision(
            False,
            MISSING_PREDICTION_AS_OF_UTC,
            rec_identity,
            outcome_identity,
        )
    if result_as_of is None or prediction_as_of >= result_as_of:
        return LearningOutcomeJoinDecision(
            False,
            STALE_OR_INVALID_AS_OF,
            rec_identity,
            outcome_identity,
        )

    return LearningOutcomeJoinDecision(True, None, rec_identity, outcome_identity)
