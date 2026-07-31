"""Strategy historical replay row normalization helpers.

Pure functions only. No file I/O, no DB access, no side effects.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

_KNOWN_LIFECYCLE_STATES = {"online", "offline", "rejected", "observation"}
_PENDING_OUTCOME_VALUES = {"", "pending", "unknown", "n/a", "na", "none"}


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_lower(value: object) -> str:
    return _as_text(value).lower()


def normalize_lifecycle_state(state: object) -> str:
    raw_state = _normalize_lower(state)
    if not raw_state:
        return "unknown"
    if raw_state in _KNOWN_LIFECYCLE_STATES:
        return raw_state
    if raw_state in {"obs", "observed"}:
        return "observation"
    return "unknown"


def _normalize_outcome_value(value: object) -> str:
    raw_value = _normalize_lower(value)
    if not raw_value or raw_value in _PENDING_OUTCOME_VALUES:
        return ""
    return raw_value


def _canonicalize_outcome_key(record: Mapping[str, Any]) -> tuple[str, bool]:
    explicit_key = _as_text(record.get("canonical_outcome_key"))
    if explicit_key:
        return explicit_key, False

    fallback_key = _as_text(record.get("game_id"))
    if fallback_key:
        return fallback_key, True

    return "", False


def derive_settlement_status(actual_result: object) -> str:
    normalized_result = _normalize_outcome_value(actual_result)
    if not normalized_result:
        return "PENDING"

    mapping = {
        "win": "WON",
        "won": "WON",
        "loss": "LOST",
        "lost": "LOST",
        "lose": "LOST",
        "push": "PUSH",
        "void": "VOID",
        "voided": "VOID",
        "pending": "PENDING",
    }
    return mapping.get(normalized_result, "UNKNOWN")


def derive_hit_miss_push(settlement_status: object) -> str:
    normalized_status = _normalize_lower(settlement_status)
    mapping = {
        "won": "HIT",
        "lost": "MISS",
        "push": "PUSH",
        "void": "VOID",
        "pending": "PENDING",
        "unknown": "UNKNOWN",
    }
    return mapping.get(normalized_status, "UNKNOWN")


def build_data_quality_flags(row: Mapping[str, Any]) -> list[str]:
    flags: list[str] = []

    if not _as_text(row.get("strategy_id")):
        flags.append("MISSING_STRATEGY_ID")

    raw_lifecycle_state = _as_text(
        row.get("lifecycle_state_at_prediction_time_raw", row.get("lifecycle_state_at_prediction_time"))
    )
    lifecycle_state = _as_text(row.get("lifecycle_state_at_prediction_time"))
    if not raw_lifecycle_state:
        flags.append("MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME")
    elif normalize_lifecycle_state(raw_lifecycle_state) == "unknown":
        flags.append("UNKNOWN_LIFECYCLE_STATE_AT_PREDICTION_TIME")

    canonical_outcome_key = _as_text(row.get("canonical_outcome_key"))
    game_id = _as_text(row.get("game_id"))
    if not canonical_outcome_key:
        flags.append("MISSING_CANONICAL_OUTCOME_KEY")
    elif canonical_outcome_key.lower() in {"tmp", "temp", "unknown", "pending", "n/a", "na", "none"}:
        flags.append("UNSTABLE_CANONICAL_OUTCOME_KEY")

    actual_result = _as_text(row.get("actual_result"))
    if not actual_result or actual_result.lower() in _PENDING_OUTCOME_VALUES:
        flags.append("MISSING_ACTUAL_RESULT")

    if not game_id:
        flags.append("MISSING_GAME_ID")

    source_refs = row.get("source_refs")
    if not isinstance(source_refs, Mapping) or not source_refs:
        flags.append("MISSING_SOURCE_REFS")

    if row.get("canonical_outcome_key_was_fallback") is True:
        flags.append("CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID")

    return flags


def validate_strategy_replay_row(row: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []

    required_text_fields = [
        "strategy_id",
        "strategy_name",
        "lifecycle_state_at_prediction_time",
        "current_lifecycle_state",
        "prediction_timestamp",
        "game_id",
        "canonical_outcome_key",
        "market_type",
        "recommendation",
        "actual_result",
        "hit_miss_push",
        "settlement_status",
    ]
    for field_name in required_text_fields:
        if not _as_text(row.get(field_name)):
            errors.append(f"missing required field: {field_name}")

    if not isinstance(row.get("data_quality_flags"), list):
        errors.append("data_quality_flags must be a list")

    if not isinstance(row.get("source_refs"), Mapping) or not row.get("source_refs"):
        errors.append("source_refs must be a non-empty mapping")

    if _as_text(row.get("lifecycle_state_at_prediction_time")):
        normalized_state = normalize_lifecycle_state(row.get("lifecycle_state_at_prediction_time"))
        if normalized_state == "unknown":
            errors.append("lifecycle_state_at_prediction_time must normalize to a known state")

    return errors


def build_strategy_replay_row(record: Mapping[str, Any]) -> dict[str, Any]:
    canonical_outcome_key, used_fallback = _canonicalize_outcome_key(record)
    actual_result = record.get("actual_result")
    settlement_status = derive_settlement_status(actual_result)

    row: dict[str, Any] = {
        "strategy_id": _as_text(record.get("strategy_id")),
        "strategy_name": _as_text(record.get("strategy_name")),
        "lifecycle_state_at_prediction_time_raw": _as_text(
            record.get("lifecycle_state_at_prediction_time")
        ),
        "lifecycle_state_at_prediction_time": normalize_lifecycle_state(
            record.get("lifecycle_state_at_prediction_time")
        ),
        "current_lifecycle_state": normalize_lifecycle_state(
            record.get("current_lifecycle_state")
        ),
        "prediction_timestamp": _as_text(
            record.get("prediction_timestamp") or record.get("recorded_at_utc")
        ),
        "game_id": _as_text(record.get("game_id")),
        "canonical_outcome_key": canonical_outcome_key,
        "canonical_outcome_key_was_fallback": used_fallback,
        "market_type": _as_text(record.get("market_type")),
        "recommendation": _as_text(record.get("recommendation")),
        "confidence": record.get("confidence", record.get("model_prob")),
        "edge": record.get("edge", record.get("market_edge")),
        "actual_result": _normalize_outcome_value(actual_result),
        "hit_miss_push": derive_hit_miss_push(settlement_status),
        "settlement_status": settlement_status,
        "source_refs": dict(record.get("source_refs") or {}),
    }

    row["data_quality_flags"] = build_data_quality_flags(row)
    return row
