"""Pure metadata source contract helpers for Strategy Replay."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


SAFE_SOURCE = "SAFE_SOURCE"
NEEDS_NEW_SOURCE = "NEEDS_NEW_SOURCE"
UNSAFE_HINT = "UNSAFE_HINT"
NOT_AVAILABLE = "NOT_AVAILABLE"

_REQUIRED_FIELDS = (
    "source_id",
    "source_name",
    "provided_fields",
    "explicit_identity",
    "lifecycle_snapshot_time",
    "owner_module",
    "durability",
    "auditability",
    "allowed_for_future_writes",
    "allowed_for_historical_backfill",
    "failure_modes",
    "validation_rules",
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _as_text(value).lower() in {"1", "true", "yes", "y", "on"}


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [_as_text(item) for item in value if _as_text(item)]
    if isinstance(value, tuple):
        return [_as_text(item) for item in value if _as_text(item)]
    text = _as_text(value)
    return [text] if text else []


def build_required_metadata_source_contract() -> dict[str, Any]:
    return {
        "source_id": "",
        "source_name": "",
        "provided_fields": [
            "strategy_id",
            "strategy_name",
            "lifecycle_state_at_prediction_time",
            "current_lifecycle_state",
            "canonical_outcome_key",
        ],
        "explicit_identity": True,
        "lifecycle_snapshot_time": "prediction_write_time",
        "owner_module": "",
        "durability": "required",
        "auditability": "required",
        "allowed_for_future_writes": True,
        "allowed_for_historical_backfill": False,
        "failure_modes": [
            "missing strategy_id",
            "missing strategy_name",
            "missing lifecycle_state_at_prediction_time",
            "current_lifecycle_state used as a substitute for historical lifecycle snapshot",
        ],
        "validation_rules": [
            "strategy_id must be explicit",
            "strategy_name must be explicit",
            "lifecycle_state_at_prediction_time must be explicit",
            "current_lifecycle_state cannot replace lifecycle_state_at_prediction_time",
            "SINGLE_BOOK is not strategy identity",
            "best_bet_strategy is not strategy identity",
            "query filter strategy_id is not a write source",
        ],
    }


def classify_strategy_replay_metadata_source(source: Mapping[str, Any] | None) -> str:
    if not isinstance(source, Mapping) or not source:
        return NOT_AVAILABLE

    source_type = _as_text(source.get("source_type"))
    explicit_identity = _as_bool(source.get("explicit_identity"))
    provided_fields = set(_as_list(source.get("provided_fields")))
    has_required_fields = {
        "strategy_id",
        "strategy_name",
        "lifecycle_state_at_prediction_time",
    }.issubset(provided_fields)
    allowed_for_future_writes = _as_bool(source.get("allowed_for_future_writes"))
    allowed_for_historical_backfill = _as_bool(source.get("allowed_for_historical_backfill"))
    durability = _as_text(source.get("durability")).lower()
    validation_rules = set(_as_list(source.get("validation_rules")))

    if source_type in {"execution_strategy", "best_bet_strategy", "query_filter"}:
        return UNSAFE_HINT
    if not explicit_identity or not has_required_fields:
        return NEEDS_NEW_SOURCE
    if not allowed_for_future_writes or durability not in {"required", "durable", "auditable"}:
        return NEEDS_NEW_SOURCE
    if allowed_for_historical_backfill:
        return NEEDS_NEW_SOURCE
    if "current_lifecycle_state cannot replace lifecycle_state_at_prediction_time" not in validation_rules:
        return NEEDS_NEW_SOURCE
    return SAFE_SOURCE


def validate_strategy_replay_metadata_source(source: Mapping[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if not isinstance(source, Mapping) or not source:
        return ["missing source"]

    if classify_strategy_replay_metadata_source(source) == UNSAFE_HINT:
        errors.append("source is an unsafe hint")

    if not _as_bool(source.get("explicit_identity")):
        errors.append("explicit_identity must be true")

    provided_fields = set(_as_list(source.get("provided_fields")))
    for field_name in ("strategy_id", "strategy_name", "lifecycle_state_at_prediction_time"):
        if field_name not in provided_fields:
            errors.append(f"missing required field: {field_name}")

    if "current_lifecycle_state cannot replace lifecycle_state_at_prediction_time" not in set(
        _as_list(source.get("validation_rules"))
    ):
        errors.append("current_lifecycle_state cannot replace lifecycle_state_at_prediction_time")

    if not _as_bool(source.get("allowed_for_future_writes")):
        errors.append("allowed_for_future_writes must be true")

    if _as_bool(source.get("allowed_for_historical_backfill")):
        errors.append("allowed_for_historical_backfill must be false")

    return errors


def summarize_metadata_source_coverage(sources: list[Mapping[str, Any]] | None) -> dict[str, Any]:
    items = [dict(source) for source in (sources or []) if isinstance(source, Mapping)]
    counts = {SAFE_SOURCE: 0, NEEDS_NEW_SOURCE: 0, UNSAFE_HINT: 0, NOT_AVAILABLE: 0}
    validated: list[dict[str, Any]] = []

    for source in items:
        classification = classify_strategy_replay_metadata_source(source)
        counts[classification] = counts.get(classification, 0) + 1
        validated.append(
            {
                **source,
                "classification": classification,
                "validation_errors": validate_strategy_replay_metadata_source(source),
            }
        )

    return {
        "total_sources": len(items),
        "counts": counts,
        "sources": validated,
        "required_contract": build_required_metadata_source_contract(),
    }
