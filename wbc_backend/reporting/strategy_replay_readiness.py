"""Read-only readiness classifier for the strategy replay page."""
from __future__ import annotations

from typing import Any

READYNESS_LEVEL_NOT_READY = "NOT_READY"
READYNESS_LEVEL_DATA_CONTRACT_READY = "DATA_CONTRACT_READY"
READYNESS_LEVEL_BACKFILL_REQUIRED = "BACKFILL_REQUIRED"
READYNESS_LEVEL_API_SKELETON_READY = "API_SKELETON_READY"
READYNESS_LEVEL_UI_MVP_READY = "UI_MVP_READY"

_REQUIRED_FLAG_KEYS = (
    "MISSING_STRATEGY_ID",
    "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME",
    "MISSING_CANONICAL_OUTCOME_KEY",
    "MISSING_ACTUAL_RESULT",
)


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _count_flag(rows: list[dict[str, Any]], flag: str) -> int:
    return sum(1 for row in rows if flag in set(row.get("data_quality_flags") or []))


def build_strategy_replay_readiness_summary(
    rows: list[dict[str, Any]],
    *,
    endpoint_mounted: bool = False,
    endpoint_stable: bool = False,
    ui_ready: bool = False,
    source_mode: str = "READ_ONLY",
) -> dict[str, Any]:
    total_rows = len(rows)
    missing_strategy_id = _count_flag(rows, "MISSING_STRATEGY_ID")
    missing_lifecycle_state_at_prediction_time = _count_flag(rows, "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME")
    missing_canonical_outcome_key = _count_flag(rows, "MISSING_CANONICAL_OUTCOME_KEY") + _count_flag(
        rows,
        "CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID",
    )
    missing_actual_result = _count_flag(rows, "MISSING_ACTUAL_RESULT")
    complete_rows = max(
        total_rows - max(
            missing_strategy_id,
            missing_lifecycle_state_at_prediction_time,
            missing_canonical_outcome_key,
            missing_actual_result,
        ),
        0,
    )

    summary = {
        "total_rows": total_rows,
        "missing_strategy_id": missing_strategy_id,
        "missing_lifecycle_state_at_prediction_time": missing_lifecycle_state_at_prediction_time,
        "missing_canonical_outcome_key": missing_canonical_outcome_key,
        "missing_actual_result": missing_actual_result,
        "complete_rows": complete_rows,
        "endpoint_mounted": endpoint_mounted,
        "endpoint_stable": endpoint_stable,
        "ui_ready": ui_ready,
        "source_mode": _as_text(source_mode) or "READ_ONLY",
        "readiness_level": READYNESS_LEVEL_NOT_READY,
    }
    summary["readiness_level"] = classify_strategy_replay_readiness(summary)
    return summary


def classify_strategy_replay_readiness(summary: dict[str, Any]) -> str:
    total_rows = int(summary.get("total_rows", 0) or 0)
    if total_rows == 0:
        return READYNESS_LEVEL_NOT_READY

    if int(summary.get("missing_strategy_id", 0) or 0) > 0:
        return READYNESS_LEVEL_BACKFILL_REQUIRED
    if int(summary.get("missing_lifecycle_state_at_prediction_time", 0) or 0) > 0:
        return READYNESS_LEVEL_BACKFILL_REQUIRED
    if int(summary.get("missing_canonical_outcome_key", 0) or 0) > 0:
        return READYNESS_LEVEL_BACKFILL_REQUIRED
    if int(summary.get("missing_actual_result", 0) or 0) > 0:
        return READYNESS_LEVEL_BACKFILL_REQUIRED

    if not bool(summary.get("endpoint_mounted", False)):
        return READYNESS_LEVEL_DATA_CONTRACT_READY
    if not bool(summary.get("endpoint_stable", False)):
        return READYNESS_LEVEL_API_SKELETON_READY
    if bool(summary.get("ui_ready", False)):
        return READYNESS_LEVEL_UI_MVP_READY
    return READYNESS_LEVEL_API_SKELETON_READY


def identify_strategy_replay_blockers(summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    total_rows = int(summary.get("total_rows", 0) or 0)
    if total_rows == 0:
        blockers.append("No replay rows available")

    if int(summary.get("missing_strategy_id", 0) or 0) > 0:
        blockers.append("Backfill strategy_id into historical replay rows")
    if int(summary.get("missing_lifecycle_state_at_prediction_time", 0) or 0) > 0:
        blockers.append("Instrument lifecycle_state_at_prediction_time at prediction write time")
    if int(summary.get("missing_canonical_outcome_key", 0) or 0) > 0:
        blockers.append("Stabilize canonical_outcome_key for replay joins")
    if int(summary.get("missing_actual_result", 0) or 0) > 0:
        blockers.append("Backfill actual_result from postgame outcomes")

    if not bool(summary.get("endpoint_mounted", False)):
        blockers.append("Mount the read-only API contract")
    if not bool(summary.get("endpoint_stable", False)):
        blockers.append("Validate endpoint contract stability")
    if not bool(summary.get("ui_ready", False)):
        blockers.append("Keep UI blocked until replay readiness reaches MVP level")

    return blockers


def build_strategy_replay_gap_closure_plan(summary: dict[str, Any]) -> list[str]:
    plan: list[str] = []
    if int(summary.get("total_rows", 0) or 0) == 0:
        plan.append("Populate a minimal replay sample from existing registry/outcome files and rerun readiness checks")
    if int(summary.get("missing_strategy_id", 0) or 0) > 0:
        plan.append("Backfill or instrument strategy_id at prediction time")
    if int(summary.get("missing_lifecycle_state_at_prediction_time", 0) or 0) > 0:
        plan.append("Persist lifecycle_state_at_prediction_time with each prediction record")
    if int(summary.get("missing_canonical_outcome_key", 0) or 0) > 0:
        plan.append("Normalize a stable canonical_outcome_key for replay joins")
    if int(summary.get("missing_actual_result", 0) or 0) > 0:
        plan.append("Join predictions to postgame results using the stable outcome key and backfill actual_result")

    if not bool(summary.get("endpoint_mounted", False)):
        plan.append("Keep the service/query skeleton separate until the replay store is ready")
    elif not bool(summary.get("endpoint_stable", False)):
        plan.append("Add endpoint contract tests and production-sample validation before UI work")
    elif bool(summary.get("ui_ready", False)):
        plan.append("Proceed to UI work with the validated read-only contract")
    else:
        plan.append("Hold UI work until readiness reaches UI_MVP_READY")

    return plan
