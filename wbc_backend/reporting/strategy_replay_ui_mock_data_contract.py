"""Pure validation helpers for the Strategy Replay UI mock-data/spec package."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

FINAL_MARKER = "P40_STRATEGY_REPLAY_UI_MOCK_DATA_SPEC_GATE_READY"
MOCK_DATA_SPEC_MODE = "UI_MOCK_DATA_SPEC_ONLY"
FIXTURE_ONLY_SOURCE_MODE = "FIXTURE_ONLY"
MOCK_ONLY_SOURCE_MODE = "MOCK_ONLY"
BACKFILL_REQUIRED_READINESS = "BACKFILL_REQUIRED"
MOCK_DATA_ONLY_READINESS = "MOCK_DATA_ONLY"
REQUIRED_WARNING_TEXTS = (
    "Mock-data/spec-only. Not production UI.",
    "No production migration has been executed.",
    "Historical strategy identity remains blocked unless explicit metadata source is accepted.",
)
REQUIRED_DISABLED_ACTIONS = ("PRODUCTION_LAUNCH",)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _normalize_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(payload or {})


def _rows(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        return []
    return [row for row in raw_rows if isinstance(row, dict)]


def _missing_required_row_fields(row: Mapping[str, Any]) -> list[str]:
    missing: list[str] = []
    for field_name in (
        "strategy_id",
        "strategy_name",
        "lifecycle_state_at_prediction_time",
        "current_lifecycle_state",
        "game_id",
        "prediction_timestamp",
        "prediction",
        "actual_result",
        "data_quality_flags",
        "replay_metadata_version",
    ):
        value = row.get(field_name)
        if field_name == "prediction":
            if not isinstance(value, dict):
                missing.append(field_name)
        elif field_name == "data_quality_flags":
            if not isinstance(value, list):
                missing.append(field_name)
        elif not _as_text(value):
            missing.append(field_name)
    return missing


def _top_level_blockers(payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []

    if _as_text(payload.get("mode")) != MOCK_DATA_SPEC_MODE:
        blockers.append("mode must be UI_MOCK_DATA_SPEC_ONLY")
    if _as_bool(payload.get("production_ui")):
        blockers.append("production_ui must be false")

    blockers.extend(_top_level_contract_blockers(payload))
    blockers.extend(_top_level_control_blockers(payload))

    return blockers


def _top_level_contract_blockers(payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []

    source_mode = _as_text(payload.get("source_mode"))
    if source_mode not in {FIXTURE_ONLY_SOURCE_MODE, MOCK_ONLY_SOURCE_MODE}:
        blockers.append("source_mode must be FIXTURE_ONLY or MOCK_ONLY")

    readiness_level = _as_text(payload.get("readiness_level"))
    if readiness_level not in {BACKFILL_REQUIRED_READINESS, MOCK_DATA_ONLY_READINESS}:
        blockers.append("readiness_level must be BACKFILL_REQUIRED or MOCK_DATA_ONLY")

    return blockers


def _top_level_control_blockers(payload: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []

    disabled_actions = {_as_text(action) for action in payload.get("disabled_actions") or [] if _as_text(action)}
    for required_action in REQUIRED_DISABLED_ACTIONS:
        if required_action not in disabled_actions:
            blockers.append(f"disabled_actions must include {required_action}")

    warnings = {_as_text(warning) for warning in payload.get("warnings") or [] if _as_text(warning)}
    for warning_text in REQUIRED_WARNING_TEXTS:
        if warning_text not in warnings:
            blockers.append(f"warnings must include: {warning_text}")

    if _as_bool(payload.get("runtime_production_enablement_allowed")):
        blockers.append("runtime_production_enablement_allowed must be false")
    if _as_bool(payload.get("production_migration_allowed")):
        blockers.append("production_migration_allowed must be false")
    if _as_bool(payload.get("production_launch_allowed")):
        blockers.append("production_launch_allowed must be false")
    if _as_bool(payload.get("production_ui_can_start")):
        blockers.append("production_ui_can_start must be false")

    return blockers


def _row_blockers(rows: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    if not rows:
        blockers.append("rows must contain mock samples")

    for index, row in enumerate(rows):
        missing_fields = _missing_required_row_fields(row)
        if missing_fields:
            blockers.append(f"row[{index}] missing required fields: {', '.join(missing_fields)}")
        if _as_bool(row.get("production_ready")):
            blockers.append(f"row[{index}] must not claim production readiness")
        if _as_text(row.get("ui_mode")) == "production":
            blockers.append(f"row[{index}] must not claim production ui mode")
        if _as_bool(row.get("runtime_production_enablement_allowed")):
            blockers.append(f"row[{index}] must not enable runtime production")
        if _as_bool(row.get("production_migration_allowed")):
            blockers.append(f"row[{index}] must not enable production migration")

    return blockers


def identify_strategy_replay_ui_mock_payload_blockers(payload: Mapping[str, Any] | None) -> list[str]:
    data = _normalize_payload(payload)
    blockers: list[str] = []
    blockers.extend(_top_level_blockers(data))
    blockers.extend(_row_blockers(_rows(data)))

    deduped: list[str] = []
    for blocker in blockers:
        if blocker and blocker not in deduped:
            deduped.append(blocker)
    return deduped


def validate_strategy_replay_ui_mock_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    blockers = identify_strategy_replay_ui_mock_payload_blockers(payload)
    return {
        "is_valid": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "summary": summarize_strategy_replay_ui_mock_payload(payload),
    }


def summarize_strategy_replay_ui_mock_payload(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    data = _normalize_payload(payload)
    rows = _rows(data)
    warnings = [warning for warning in data.get("warnings") or [] if _as_text(warning)]
    disabled_actions = [action for action in data.get("disabled_actions") or [] if _as_text(action)]
    blockers = identify_strategy_replay_ui_mock_payload_blockers(data)
    mode = _as_text(data.get("mode")) or MOCK_DATA_SPEC_MODE
    source_mode = _as_text(data.get("source_mode")) or FIXTURE_ONLY_SOURCE_MODE
    readiness_level = _as_text(data.get("readiness_level")) or BACKFILL_REQUIRED_READINESS
    return {
        "mode": mode,
        "source_mode": source_mode,
        "readiness_level": readiness_level,
        "row_count": len(rows),
        "warning_count": len(warnings),
        "disabled_action_count": len(disabled_actions),
        "production_ui_can_start": False,
        "runtime_production_enablement_can_start": False,
        "production_migration_can_start": False,
        "mock_data_spec_only": mode == MOCK_DATA_SPEC_MODE,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "final_marker": FINAL_MARKER,
    }
