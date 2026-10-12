"""Post-staging readiness recheck for Strategy Replay UI unlock."""
from __future__ import annotations

from typing import Any

from wbc_backend.reporting.strategy_replay_adapter import summarize_strategy_replay_rows
from wbc_backend.reporting.strategy_replay_readiness import (
    READYNESS_LEVEL_BACKFILL_REQUIRED,
    READYNESS_LEVEL_UI_MVP_READY,
    build_strategy_replay_gap_closure_plan,
    build_strategy_replay_readiness_summary,
    identify_strategy_replay_blockers,
)

UI_MODE_BLOCKED = "BLOCKED"
UI_MODE_FRONTEND_SPEC_MOCK_DATA = "FRONTEND_SPEC_MOCK_DATA"


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


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _rows_only(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _staging_value(staging_migration_result: dict[str, Any] | None, key_name: str, default: object = None) -> object:
    if not isinstance(staging_migration_result, dict):
        return default
    if key_name in staging_migration_result:
        return staging_migration_result.get(key_name, default)
    summary = staging_migration_result.get("summary")
    if isinstance(summary, dict) and key_name in summary:
        return summary.get(key_name, default)
    return default


def _normalize_staging_result(staging_migration_result: dict[str, Any] | None) -> dict[str, Any]:
    blocked_reasons = _staging_value(staging_migration_result, "blocked_reasons", [])
    if not isinstance(blocked_reasons, list):
        blocked_reasons = []

    return {
        "staging_only": _as_bool(_staging_value(staging_migration_result, "staging_only", False)),
        "production_write_allowed": _as_bool(_staging_value(staging_migration_result, "production_write_allowed", False)),
        "applied_count": _as_int(_staging_value(staging_migration_result, "applied_count", 0), 0),
        "skipped_count": _as_int(_staging_value(staging_migration_result, "skipped_count", 0), 0),
        "unchanged_count": _as_int(_staging_value(staging_migration_result, "unchanged_count", 0), 0),
        "dry_run_only": _as_bool(_staging_value(staging_migration_result, "dry_run_only", True)),
        "blocked_reasons": [_as_text(reason) for reason in blocked_reasons if _as_text(reason)],
        "rollback_plan_ref": _as_text(_staging_value(staging_migration_result, "rollback_plan_ref", "")),
        "target_mode": _as_text(_staging_value(staging_migration_result, "target_mode", "STAGING")).upper(),
    }


def _count_has_no_p0_blockers(readiness_summary: dict[str, Any]) -> bool:
    for key_name in (
        "missing_strategy_id",
        "missing_lifecycle_state_at_prediction_time",
        "missing_canonical_outcome_key",
        "missing_actual_result",
    ):
        if _as_int(readiness_summary.get(key_name), 0) > 0:
            return False
    return True


def _staging_result_is_safely_fixture_only(staging_result: dict[str, Any]) -> bool:
    return bool(
        staging_result.get("staging_only")
        and not staging_result.get("production_write_allowed")
        and _as_int(staging_result.get("applied_count"), 0) > 0
        and not staging_result.get("blocked_reasons")
    )


def build_post_staging_readiness_summary(
    rows: list[dict[str, Any]],
    staging_migration_result: dict[str, Any] | None,
) -> dict[str, Any]:
    safe_rows = _rows_only(rows)
    staging_result = _normalize_staging_result(staging_migration_result)
    data_quality_summary = summarize_strategy_replay_rows(safe_rows)
    staging_ready = _staging_result_is_safely_fixture_only(staging_result)
    ready_for_ui = staging_ready and _count_has_no_p0_blockers(
        {
            "missing_strategy_id": data_quality_summary.get("rows_missing_strategy_id", 0),
            "missing_lifecycle_state_at_prediction_time": data_quality_summary.get("rows_missing_lifecycle_state_at_prediction_time", 0),
            "missing_canonical_outcome_key": data_quality_summary.get("rows_missing_canonical_outcome_key", 0),
            "missing_actual_result": data_quality_summary.get("rows_missing_actual_result", 0),
        }
    )

    readiness_summary = build_strategy_replay_readiness_summary(
        safe_rows,
        endpoint_mounted=True,
        endpoint_stable=True,
        ui_ready=ready_for_ui,
        source_mode="READ_ONLY",
    )

    ui_checklist = build_ui_unlock_checklist(readiness_summary, staging_result)
    return {
        "row_count": len(safe_rows),
        "source_mode": readiness_summary["source_mode"],
        "data_quality_summary": data_quality_summary,
        "readiness_summary": readiness_summary,
        "staging_migration_result": staging_result,
        "ui_can_start": ui_checklist["ui_can_start"],
        "ui_mode": ui_checklist["ui_mode"],
        "blockers": ui_checklist["blockers"],
        "required_next_actions": ui_checklist["required_next_actions"],
        "readiness_level": readiness_summary["readiness_level"],
        "post_staging_ready": ui_checklist["ui_can_start"],
    }


def evaluate_ui_unlock_gate(
    readiness_summary: dict[str, Any],
    staging_migration_result: dict[str, Any] | None,
) -> dict[str, Any]:
    staging_result = _normalize_staging_result(staging_migration_result)
    blockers = identify_ui_unlock_blockers(readiness_summary, staging_result)
    ui_can_start = not blockers
    ui_mode = UI_MODE_FRONTEND_SPEC_MOCK_DATA if ui_can_start else UI_MODE_BLOCKED
    return {
        "ui_can_start": ui_can_start,
        "ui_mode": ui_mode,
        "blockers": blockers,
        "required_next_actions": _required_next_actions(ui_can_start, blockers),
        "staging_only": staging_result["staging_only"],
        "production_write_allowed": staging_result["production_write_allowed"],
        "readiness_level": _as_text(readiness_summary.get("readiness_level")),
        "source_mode": _as_text(readiness_summary.get("source_mode")),
    }


def _missing_count_blockers(readiness_summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for key_name, label in (
        ("missing_strategy_id", "strategy_id"),
        ("missing_lifecycle_state_at_prediction_time", "lifecycle_state_at_prediction_time"),
        ("missing_canonical_outcome_key", "canonical_outcome_key"),
        ("missing_actual_result", "actual_result"),
    ):
        if _as_int(readiness_summary.get(key_name), 0) > 0:
            blockers.append(f"missing required field counts remain for {label}")
    return blockers


def identify_ui_unlock_blockers(
    readiness_summary: dict[str, Any],
    staging_migration_result: dict[str, Any] | None,
) -> list[str]:
    blockers = list(identify_strategy_replay_blockers(readiness_summary))
    staging_result = _normalize_staging_result(staging_migration_result)

    if not staging_result["staging_only"]:
        blockers.append("staging migration output must be staging_only")
    if staging_result["production_write_allowed"]:
        blockers.append("production_write_allowed must be false")
    if _as_int(staging_result["applied_count"], 0) <= 0:
        blockers.append("applied_count must be greater than zero")
    if _as_text(readiness_summary.get("source_mode")) != "READ_ONLY":
        blockers.append("source_mode must remain READ_ONLY")
    if _as_text(readiness_summary.get("readiness_level")) != READYNESS_LEVEL_UI_MVP_READY:
        blockers.append("readiness_level must be UI_MVP_READY")
    if not _count_has_no_p0_blockers(readiness_summary):
        blockers.extend(_missing_count_blockers(readiness_summary))
    if staging_result["blocked_reasons"]:
        blockers.extend(f"staging blocked: {reason}" for reason in staging_result["blocked_reasons"])

    deduped: list[str] = []
    for blocker in blockers:
        if blocker and blocker not in deduped:
            deduped.append(blocker)
    return deduped


def _required_next_actions(ui_can_start: bool, blockers: list[str]) -> list[str]:
    if ui_can_start:
        return [
            "Start frontend spec / mock-data mode using staging output only",
            "Keep production UI blocked until a later production-readiness gate is approved",
        ]
    return blockers or ["Keep UI blocked until post-staging readiness reaches UI_MVP_READY"]


def build_ui_unlock_checklist(
    readiness_summary: dict[str, Any],
    staging_migration_result: dict[str, Any] | None,
) -> dict[str, Any]:
    gate = evaluate_ui_unlock_gate(readiness_summary, staging_migration_result)
    return {
        "ui_can_start": gate["ui_can_start"],
        "ui_mode": gate["ui_mode"],
        "blockers": gate["blockers"],
        "required_next_actions": gate["required_next_actions"],
        "readiness_level": gate["readiness_level"],
        "source_mode": gate["source_mode"],
        "staging_only": gate["staging_only"],
        "production_write_allowed": gate["production_write_allowed"],
    }
