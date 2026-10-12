"""Pure UI stop-gate helpers for Strategy Replay."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return _as_text(value).lower() in {"1", "true", "yes", "y", "on"}


def identify_strategy_replay_ui_blockers(
    metadata_source_summary: Mapping[str, Any] | None,
    readiness_summary: Mapping[str, Any] | None,
) -> list[str]:
    source = dict(metadata_source_summary or {})
    readiness = dict(readiness_summary or {})
    blockers: list[str] = []

    if not _as_bool(source.get("has_strategy_id_source")):
        blockers.append("MISSING_STRATEGY_ID_SOURCE")
    if not _as_bool(source.get("has_strategy_name_source")):
        blockers.append("MISSING_STRATEGY_NAME_SOURCE")
    if not _as_bool(source.get("has_lifecycle_state_at_prediction_time_source")):
        blockers.append("MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME_SOURCE")
    if not _as_bool(source.get("future_rows_write_explicit_metadata")):
        blockers.append("MISSING_FUTURE_ROWS_EXPLICIT_METADATA")
    if _as_bool(source.get("historical_identity_repair_stopped", True)):
        blockers.append("HISTORICAL_IDENTITY_REPAIR_STOPPED")

    readiness_level = _as_text(readiness.get("readiness_level"))
    if readiness_level == "BACKFILL_REQUIRED":
        blockers.append("READINESS_BACKFILL_REQUIRED")
    if readiness_level != "UI_MVP_READY":
        blockers.append("PRODUCTION_MIGRATION_BLOCKED")

    return blockers


def evaluate_strategy_replay_ui_gate(
    metadata_source_summary: Mapping[str, Any] | None,
    readiness_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    source = dict(metadata_source_summary or {})
    readiness = dict(readiness_summary or {})
    blockers = identify_strategy_replay_ui_blockers(source, readiness)
    readiness_level = _as_text(readiness.get("readiness_level"))
    explicitly_non_production = _as_bool(source.get("explicitly_non_production_mode"))
    approved_mock_data_mode = _as_bool(source.get("approved_mock_data_mode"))

    has_all_metadata_sources = all(
        [
            _as_bool(source.get("has_strategy_id_source")),
            _as_bool(source.get("has_strategy_name_source")),
            _as_bool(source.get("has_lifecycle_state_at_prediction_time_source")),
            _as_bool(source.get("future_rows_write_explicit_metadata")),
        ]
    )

    ui_can_start = False
    ui_mode = "blocked"
    if has_all_metadata_sources and readiness_level == "UI_MVP_READY":
        ui_can_start = True
        ui_mode = "production"
    elif has_all_metadata_sources and approved_mock_data_mode and explicitly_non_production:
        ui_can_start = True
        ui_mode = "mock-data"

    production_can_start = bool(
        ui_can_start and readiness_level == "UI_MVP_READY" and ui_mode == "production"
    )

    return {
        "ui_can_start": ui_can_start,
        "production_can_start": production_can_start,
        "ui_mode": ui_mode,
        "readiness_level": readiness_level,
        "blockers": blockers,
        "has_all_metadata_sources": has_all_metadata_sources,
    }


def build_strategy_replay_ui_stop_notice(
    metadata_source_summary: Mapping[str, Any] | None,
    readiness_summary: Mapping[str, Any] | None,
) -> dict[str, Any]:
    gate = evaluate_strategy_replay_ui_gate(metadata_source_summary, readiness_summary)
    return {
        "title": "Strategy Replay UI stopped",
        "ui_can_start": gate["ui_can_start"],
        "production_can_start": gate["production_can_start"],
        "ui_mode": gate["ui_mode"],
        "blockers": gate["blockers"],
        "notice": "UI remains blocked until explicit metadata sources exist and readiness reaches UI_MVP_READY or an approved non-production mock-data mode.",
    }


def summarize_strategy_replay_ui_gate(gate_result: Mapping[str, Any] | None) -> dict[str, Any]:
    gate = dict(gate_result or {})
    blockers = list(gate.get("blockers") or [])
    return {
        "ui_can_start": bool(gate.get("ui_can_start", False)),
        "production_can_start": bool(gate.get("production_can_start", False)),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "readiness_level": _as_text(gate.get("readiness_level")),
        "ui_mode": _as_text(gate.get("ui_mode")) or "blocked",
    }
