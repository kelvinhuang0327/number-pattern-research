"""Pure helpers for explicit Strategy Replay runtime metadata injection."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from wbc_backend.reporting.strategy_replay_metadata_registry import (
    find_strategy_metadata_by_id,
    load_strategy_metadata_registry,
    validate_strategy_metadata_record,
    validate_strategy_metadata_registry,
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _as_text(value).lower() in {"1", "true", "yes", "y", "on"}


def load_runtime_strategy_metadata_registry(path: str | Path | None) -> list[dict[str, Any]]:
    """Load a runtime metadata registry from an explicit path only."""
    if path is None:
        return []

    registry_path = Path(path)
    if not registry_path.exists():
        return []
    return load_strategy_metadata_registry(registry_path)


def resolve_runtime_strategy_metadata(
    strategy_id: str | None,
    registry_records: Sequence[Mapping[str, Any]] | None = None,
    *,
    registry_path: str | Path | None = None,
) -> dict[str, Any]:
    """Resolve a single explicit strategy registry record without inventing values."""
    records = [dict(item) for item in (registry_records or []) if isinstance(item, Mapping)]
    if registry_path is not None:
        records = load_runtime_strategy_metadata_registry(registry_path)

    strategy_id_text = _as_text(strategy_id)
    matched_record = find_strategy_metadata_by_id(records, strategy_id_text) if strategy_id_text else None
    registry_validation = validate_strategy_metadata_registry(records) if records else {
        "total_records": 0,
        "valid_records": 0,
        "invalid_records": 0,
        "future_write_allowed_records": 0,
        "duplicate_strategy_ids": [],
        "records": [],
    }

    return {
        "strategy_id": strategy_id_text,
        "registry_records": records,
        "registry_validation": registry_validation,
        "matched_record": matched_record,
        "matched_record_errors": validate_strategy_metadata_record(matched_record) if matched_record else ["missing registry match"],
    }


def build_analyze_request_replay_metadata(
    strategy_metadata_record: Mapping[str, Any],
    *,
    current_lifecycle_state: str | None = None,
) -> dict[str, str]:
    """Build explicit AnalyzeRequest keyword arguments from a validated registry row."""
    current_state = _as_text(current_lifecycle_state) or _as_text(strategy_metadata_record.get("current_lifecycle_state"))
    return {
        "strategy_id": _as_text(strategy_metadata_record.get("strategy_id")),
        "strategy_name": _as_text(strategy_metadata_record.get("strategy_name")),
        "lifecycle_state_at_prediction_time": current_state,
        "current_lifecycle_state": current_state,
    }


def _validate_runtime_metadata_presence_errors(
    strategy_id_text: str,
    records: Sequence[Mapping[str, Any]],
    *,
    registry_path: str | Path | None = None,
) -> list[str]:
    errors: list[str] = []

    if not strategy_id_text:
        errors.append("missing strategy_id")

    if registry_path is not None and not Path(registry_path).exists():
        errors.append("missing runtime strategy metadata registry")

    if not records:
        errors.append("missing runtime strategy metadata registry")

    return errors


def _validate_runtime_metadata_registry_errors(
    strategy_id_text: str,
    registry_validation: Mapping[str, Any],
    matched_record: Mapping[str, Any] | None,
) -> list[str]:
    errors: list[str] = []

    duplicate_ids = set(registry_validation.get("duplicate_strategy_ids") or [])
    if strategy_id_text and strategy_id_text in duplicate_ids:
        errors.append(f"duplicate strategy_id in registry: {strategy_id_text}")

    if registry_validation.get("invalid_records", 0):
        for row in registry_validation.get("records", []):
            if row.get("errors"):
                errors.extend(row.get("errors") or [])

    if matched_record is None:
        errors.append(f"unknown strategy_id: {strategy_id_text or 'missing'}")
    return errors


def _validate_runtime_metadata_snapshot_errors(
    matched_record: Mapping[str, Any],
    *,
    current_lifecycle_state: str | None = None,
) -> list[str]:
    errors: list[str] = []

    errors.extend(validate_strategy_metadata_record(matched_record))

    if not _as_bool(matched_record.get("allowed_for_future_writes")):
        errors.append("allowed_for_future_writes must be true")
    if _as_bool(matched_record.get("allowed_for_historical_backfill")):
        errors.append("allowed_for_historical_backfill must be false")

    resolved_current_lifecycle_state = _as_text(current_lifecycle_state) or _as_text(
        matched_record.get("current_lifecycle_state")
    )
    if not resolved_current_lifecycle_state:
        errors.append("missing current_lifecycle_state")
    elif _as_text(current_lifecycle_state) and _as_text(current_lifecycle_state) != _as_text(
        matched_record.get("current_lifecycle_state")
    ):
        errors.append("current_lifecycle_state must match the validated registry snapshot")

    if not _as_text(matched_record.get("strategy_name")):
        errors.append("missing strategy_name")

    return errors


def validate_runtime_metadata_injection_inputs(
    strategy_id: str | None,
    registry_records: Sequence[Mapping[str, Any]] | None = None,
    *,
    registry_path: str | Path | None = None,
    current_lifecycle_state: str | None = None,
) -> list[str]:
    """Validate runtime metadata injection inputs without performing any writes."""
    resolution = resolve_runtime_strategy_metadata(
        strategy_id,
        registry_records,
        registry_path=registry_path,
    )

    strategy_id_text = resolution["strategy_id"]
    records = resolution["registry_records"]
    matched_record = resolution["matched_record"]
    registry_validation = resolution["registry_validation"]

    errors = _validate_runtime_metadata_presence_errors(
        strategy_id_text,
        records,
        registry_path=registry_path,
    )
    if not records:
        return errors

    errors.extend(
        _validate_runtime_metadata_registry_errors(
            strategy_id_text,
            registry_validation,
            matched_record,
        )
    )
    if matched_record is None:
        return errors

    errors.extend(
        _validate_runtime_metadata_snapshot_errors(
            matched_record,
            current_lifecycle_state=current_lifecycle_state,
        )
    )
    return errors


def prepare_runtime_strategy_metadata_request_kwargs(
    strategy_id: str | None,
    registry_records: Sequence[Mapping[str, Any]] | None = None,
    *,
    registry_path: str | Path | None = None,
    current_lifecycle_state: str | None = None,
    strict: bool = False,
) -> dict[str, str]:
    """Return explicit AnalyzeRequest kwargs when runtime metadata resolves safely."""
    errors = validate_runtime_metadata_injection_inputs(
        strategy_id,
        registry_records,
        registry_path=registry_path,
        current_lifecycle_state=current_lifecycle_state,
    )
    if errors:
        if strict:
            raise ValueError("; ".join(errors))
        return {}

    resolution = resolve_runtime_strategy_metadata(
        strategy_id,
        registry_records,
        registry_path=registry_path,
    )
    matched_record = resolution["matched_record"]
    if not isinstance(matched_record, Mapping):
        return {}

    return build_analyze_request_replay_metadata(
        matched_record,
        current_lifecycle_state=current_lifecycle_state,
    )
