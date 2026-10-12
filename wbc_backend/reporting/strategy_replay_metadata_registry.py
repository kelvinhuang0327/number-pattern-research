"""Pure Strategy Replay metadata registry skeleton helpers."""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


REGISTRY_METADATA_VERSION = "p28a-1.0"
NON_PRODUCTION_MARKERS = {"single_book", "best_bet_strategy", "query_filter", "current_lifecycle_state"}
PRODUCTION_READINESS_ERROR = "registry record may not claim production readiness"

REQUIRED_TEXT_FIELDS = [
    "strategy_id",
    "strategy_name",
    "current_lifecycle_state",
    "lifecycle_state_source",
    "lifecycle_state_updated_at",
    "owner_module",
    "audit_source",
]


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


def build_strategy_metadata_record(
    *,
    strategy_id: str,
    strategy_name: str,
    current_lifecycle_state: str,
    lifecycle_state_source: str,
    lifecycle_state_updated_at: str,
    owner_module: str,
    audit_source: str,
    allowed_for_future_writes: bool,
    metadata_version: str = REGISTRY_METADATA_VERSION,
    allowed_for_historical_backfill: bool = False,
    notes: str = "",
    source_kind: str = "registry",
) -> dict[str, Any]:
    return {
        "strategy_id": _as_text(strategy_id),
        "strategy_name": _as_text(strategy_name),
        "current_lifecycle_state": _as_text(current_lifecycle_state),
        "lifecycle_state_source": _as_text(lifecycle_state_source),
        "lifecycle_state_updated_at": _as_text(lifecycle_state_updated_at),
        "owner_module": _as_text(owner_module),
        "audit_source": _as_text(audit_source),
        "allowed_for_future_writes": bool(allowed_for_future_writes),
        "allowed_for_historical_backfill": bool(allowed_for_historical_backfill),
        "metadata_version": _as_text(metadata_version) or REGISTRY_METADATA_VERSION,
        "notes": _as_text(notes),
        "source_kind": _as_text(source_kind) or "registry",
    }


def _is_registry_payload(payload: object) -> bool:
    return isinstance(payload, Mapping) and ("records" in payload or "registry_kind" in payload)


def _validate_required_text_fields(record: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in REQUIRED_TEXT_FIELDS:
        if not _as_text(record.get(field_name)):
            errors.append(f"missing required field: {field_name}")


def _validate_boolean_flags(record: Mapping[str, Any], errors: list[str]) -> None:
    if "allowed_for_future_writes" not in record:
        errors.append("missing required field: allowed_for_future_writes")
    elif not isinstance(record.get("allowed_for_future_writes"), bool):
        errors.append("allowed_for_future_writes must be explicit bool")

    if "allowed_for_historical_backfill" not in record:
        errors.append("allowed_for_historical_backfill must default false")
    elif not isinstance(record.get("allowed_for_historical_backfill"), bool):
        errors.append("allowed_for_historical_backfill must be explicit bool")
    elif record.get("allowed_for_historical_backfill") is not False:
        errors.append("allowed_for_historical_backfill must be false")


def _validate_source_hints(record: Mapping[str, Any], errors: list[str]) -> None:
    lifecycle_state_source = _as_text(record.get("lifecycle_state_source")).lower()
    if lifecycle_state_source in {"current_lifecycle_state", "current_lifecycle_state_fallback"}:
        errors.append("lifecycle_state_source cannot be current_lifecycle_state fallback")

    source_kind = _as_text(record.get("source_kind")).lower()
    if source_kind in NON_PRODUCTION_MARKERS:
        errors.append(f"{_as_text(record.get('source_kind'))} is invalid as strategy identity source")

    if _as_text(record.get("strategy_name")).lower() == "single_book":
        errors.append("SINGLE_BOOK is invalid as strategy identity source")
    if _as_text(record.get("strategy_name")).lower() == "best_bet_strategy":
        errors.append("best_bet_strategy is invalid as strategy identity source")
    if _as_text(record.get("audit_source")).lower() == "strategy_id query filter":
        errors.append("strategy_id query filter is invalid as write source")


def _validate_readiness_flags(record: Mapping[str, Any], errors: list[str]) -> None:
    for field_name in ("production_ready", "ui_ready", "production_migration_ready"):
        if _as_bool(record.get(field_name)):
            errors.append(PRODUCTION_READINESS_ERROR)


def load_strategy_metadata_registry(path: str | Path) -> list[dict[str, Any]]:
    registry_path = Path(path)
    if not registry_path.exists():
        return []

    raw = json.loads(registry_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, Mapping)]
    if _is_registry_payload(raw):
        records = raw.get("records", [])
        return [dict(item) for item in records if isinstance(item, Mapping)]
    return []


def validate_strategy_metadata_record(record: Mapping[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, Mapping) or not record:
        return ["missing record"]

    _validate_required_text_fields(record, errors)
    _validate_boolean_flags(record, errors)
    _validate_source_hints(record, errors)
    _validate_readiness_flags(record, errors)

    return errors


def validate_strategy_metadata_registry(records: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    items = [dict(item) for item in (records or []) if isinstance(item, Mapping)]
    validation_rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    future_write_allowed = 0
    valid_rows = 0

    for index, record in enumerate(items, start=1):
        errors = validate_strategy_metadata_record(record)
        strategy_id = _as_text(record.get("strategy_id"))
        if strategy_id:
            if strategy_id in seen_ids:
                duplicate_ids.append(strategy_id)
                errors.append(f"duplicate strategy_id: {strategy_id}")
            else:
                seen_ids.add(strategy_id)
        if not errors:
            valid_rows += 1
        if _as_bool(record.get("allowed_for_future_writes")):
            future_write_allowed += 1

        validation_rows.append(
            {
                "row_index": index,
                "strategy_id": strategy_id,
                "errors": errors,
                "is_valid": not errors,
            }
        )

    return {
        "total_records": len(items),
        "valid_records": valid_rows,
        "invalid_records": len(items) - valid_rows,
        "future_write_allowed_records": future_write_allowed,
        "duplicate_strategy_ids": duplicate_ids,
        "records": validation_rows,
    }


def find_strategy_metadata_by_id(records: Iterable[Mapping[str, Any]] | None, strategy_id: str) -> dict[str, Any] | None:
    sought = _as_text(strategy_id)
    if not sought:
        return None
    for record in records or []:
        if not isinstance(record, Mapping):
            continue
        if _as_text(record.get("strategy_id")) == sought:
            return dict(record)
    return None


def summarize_strategy_metadata_registry(records: Iterable[Mapping[str, Any]] | None) -> dict[str, Any]:
    items = [dict(item) for item in (records or []) if isinstance(item, Mapping)]
    validation = validate_strategy_metadata_registry(items)
    backfill_defaults_false = sum(1 for record in items if record.get("allowed_for_historical_backfill") is False)
    non_production_records = sum(1 for record in items if not _as_bool(record.get("production_ready")))

    return {
        "total_records": validation["total_records"],
        "valid_records": validation["valid_records"],
        "invalid_records": validation["invalid_records"],
        "future_write_allowed_records": validation["future_write_allowed_records"],
        "backfill_defaults_false_records": backfill_defaults_false,
        "non_production_records": non_production_records,
        "duplicate_strategy_ids": validation["duplicate_strategy_ids"],
        "records": validation["records"],
    }
