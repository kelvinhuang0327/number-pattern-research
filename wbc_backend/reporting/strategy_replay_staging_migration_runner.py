"""Staging-only / fixture-only migration runner skeleton for Strategy Replay."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from wbc_backend.reporting.strategy_replay_backfill_apply import apply_write_plan_to_rows
from wbc_backend.reporting.strategy_replay_backfill_write_plan import validate_write_plan


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


def _rows_copy(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [copy.deepcopy(row) for row in rows]


def _load_gate_fields(migration_gate_summary: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(migration_gate_summary, dict):
        return {}
    return migration_gate_summary


def _rollback_plan_ref(migration_gate_summary: dict[str, Any] | None) -> str:
    gate = _load_gate_fields(migration_gate_summary)
    rollback_plan = gate.get("rollback_plan")
    if isinstance(rollback_plan, list) and rollback_plan:
        first_item = _as_text(rollback_plan[0])
        if first_item:
            return first_item
    return _as_text(gate.get("rollback_plan_ref") or gate.get("rollback_plan_id") or "migration_gate_summary.rollback_plan")


def _validate_target_mode(target_mode: str) -> list[str]:
    mode = _as_text(target_mode).upper()
    errors: list[str] = []
    if mode == "PRODUCTION":
        errors.append("production target_mode is refused")
    if mode not in {"STAGING", "FIXTURE"}:
        errors.append("target_mode must be STAGING or FIXTURE")
    return errors


def _validate_input_rows(input_rows: list[dict[str, Any]] | None) -> list[str]:
    if not isinstance(input_rows, list) or not all(isinstance(row, dict) for row in input_rows):
        return ["input_rows must be a list of mapping rows"]
    return []


def _validate_write_plan(write_plan: dict[str, Any] | None) -> list[str]:
    errors: list[str] = []
    if not isinstance(write_plan, dict):
        return ["write_plan must be a mapping"]

    validation = validate_write_plan(write_plan)
    if not validation["valid"]:
        errors.extend(validation["errors"])
    if _as_bool((write_plan.get("summary") or {}).get("dry_run_only")) is not True:
        errors.append("write plan must be dry_run_only")
    return errors


def _validate_gate_summary(migration_gate_summary: dict[str, Any] | None) -> list[str]:
    gate = _load_gate_fields(migration_gate_summary)
    errors: list[str] = []
    if not isinstance(gate, dict):
        return ["migration_gate_summary must be a mapping"]
    if _as_bool(gate.get("migration_allowed")) is not True:
        errors.append("migration gate must allow migration")
    if _as_bool(gate.get("human_approved")) is not True:
        errors.append("human approval is required")
    if _as_bool(gate.get("rollback_plan_exists")) is not True and not _rollback_plan_ref(gate):
        errors.append("rollback plan must exist")
    if _as_bool(gate.get("rollback_plan_exists")) is not True:
        errors.append("rollback plan must exist")
    return errors


def validate_staging_migration_inputs(
    input_rows: list[dict[str, Any]] | None,
    write_plan: dict[str, Any] | None,
    migration_gate_summary: dict[str, Any] | None,
    *,
    target_mode: str = "STAGING",
) -> dict[str, Any]:
    errors: list[str] = []
    gate = _load_gate_fields(migration_gate_summary)
    mode = _as_text(target_mode).upper()

    errors.extend(_validate_target_mode(mode))
    errors.extend(_validate_input_rows(input_rows))
    errors.extend(_validate_write_plan(write_plan))
    errors.extend(_validate_gate_summary(gate))

    return {
        "valid": not errors,
        "errors": errors,
        "target_mode": mode,
        "rollback_plan_ref": _rollback_plan_ref(gate),
    }


def build_staging_migration_result(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    migration_gate_summary: dict[str, Any] | None,
    *,
    target_mode: str,
    blocked_reasons: list[str] | None = None,
    applied_count: int | None = None,
    skipped_count: int | None = None,
    unchanged_count: int | None = None,
) -> dict[str, Any]:
    summary = summarize_staging_migration_result(
        before_rows,
        after_rows,
        migration_gate_summary,
        target_mode=target_mode,
        blocked_reasons=blocked_reasons,
    )
    if applied_count is not None:
        summary["applied_count"] = applied_count
    if skipped_count is not None:
        summary["skipped_count"] = skipped_count
    if unchanged_count is not None:
        summary["unchanged_count"] = unchanged_count
    return {
        "staging_only": True,
        "production_write_allowed": False,
        "target_mode": _as_text(target_mode).upper(),
        "rollback_plan_ref": _rollback_plan_ref(migration_gate_summary),
        "blocked_reasons": list(blocked_reasons or []),
        "applied_count": summary["applied_count"],
        "skipped_count": summary["skipped_count"],
        "unchanged_count": summary["unchanged_count"],
        "rows": after_rows,
        "summary": summary,
    }


def run_staging_migration_simulation(
    input_rows: list[dict[str, Any]],
    write_plan: dict[str, Any],
    migration_gate_summary: dict[str, Any],
    *,
    target_mode: str = "STAGING",
) -> dict[str, Any]:
    validation = validate_staging_migration_inputs(
        input_rows,
        write_plan,
        migration_gate_summary,
        target_mode=target_mode,
    )
    if not validation["valid"]:
        raise ValueError("staging migration runner refused: " + "; ".join(validation["errors"]))

    before_rows = _rows_copy(input_rows)
    apply_result = apply_write_plan_to_rows(before_rows, write_plan)
    after_rows = list(apply_result.get("rows") or [])
    return build_staging_migration_result(
        before_rows,
        after_rows,
        migration_gate_summary,
        target_mode=target_mode,
        blocked_reasons=[],
        applied_count=_as_int(apply_result.get("applied_count"), 0),
        skipped_count=_as_int(apply_result.get("skipped_count"), 0),
        unchanged_count=_as_int(apply_result.get("unchanged_count"), 0),
    )


def summarize_staging_migration_result(
    before_rows: list[dict[str, Any]],
    after_rows: list[dict[str, Any]],
    migration_gate_summary: dict[str, Any] | None,
    *,
    target_mode: str,
    blocked_reasons: list[str] | None = None,
) -> dict[str, Any]:
    applied_count = sum(1 for before, after in zip(before_rows, after_rows) if before != after)
    unchanged_count = sum(1 for before, after in zip(before_rows, after_rows) if before == after)
    return {
        "staging_only": True,
        "production_write_allowed": False,
        "target_mode": _as_text(target_mode).upper(),
        "applied_count": applied_count,
        "skipped_count": max(_as_int((migration_gate_summary or {}).get("write_plan_summary", {}).get("summary", {}).get("write_ready_count")) - applied_count, 0),
        "unchanged_count": unchanged_count,
        "blocked_reasons": list(blocked_reasons or []),
        "rollback_plan_ref": _rollback_plan_ref(migration_gate_summary),
    }
