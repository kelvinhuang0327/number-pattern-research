"""Read-only backfill plan builder for strategy replay readiness."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from wbc_backend.reporting.strategy_replay_instrumentation import validate_backfill_candidate


def _as_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def classify_backfill_priority(candidate: Mapping[str, Any]) -> str:
    flags = set(candidate.get("data_quality_flags") or [])
    if not _as_text(candidate.get("strategy_id")) or "MISSING_STRATEGY_ID" in flags:
        return "P0"
    if not _as_text(candidate.get("lifecycle_state_at_prediction_time")) or "MISSING_LIFECYCLE_STATE_AT_PREDICTION_TIME" in flags:
        return "P0"
    if not _as_text(candidate.get("canonical_outcome_key")) or "MISSING_CANONICAL_OUTCOME_KEY" in flags:
        return "P0"
    if not _as_text(candidate.get("actual_result")) or "MISSING_ACTUAL_RESULT" in flags:
        return "P0"
    if "CANONICAL_OUTCOME_KEY_FALLBACK_TO_GAME_ID" in flags:
        return "P1"
    if "UNKNOWN_LIFECYCLE_STATE_AT_PREDICTION_TIME" in flags:
        return "P1"
    if not _as_text(candidate.get("lifecycle_state_at_prediction_time")):
        return "P1"
    if not _as_text(candidate.get("confidence")) or not _as_text(candidate.get("edge")):
        return "P2"
    return "READY"


def build_strategy_replay_backfill_plan(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        candidate = dict(row or {})
        candidate_errors = validate_backfill_candidate(candidate)
        plan.append(
            {
                "row_index": index,
                "priority": classify_backfill_priority(candidate),
                "candidate": candidate,
                "errors": candidate_errors,
            }
        )
    return plan


def summarize_backfill_requirements(plan: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "total_candidates": len(plan),
        "p0_gap_count": 0,
        "p1_gap_count": 0,
        "p2_gap_count": 0,
        "backfill_required_count": 0,
        "next_actions": [],
    }

    for item in plan:
        priority = _as_text(item.get("priority"))
        if priority == "P0":
            summary["p0_gap_count"] += 1
        elif priority == "P1":
            summary["p1_gap_count"] += 1
        elif priority == "P2":
            summary["p2_gap_count"] += 1

        if priority in {"P0", "P1", "P2"}:
            summary["backfill_required_count"] += 1

    if summary["p0_gap_count"] > 0:
        summary["next_actions"].append("Fix P0 gaps before any UI work")
    if summary["p1_gap_count"] > 0:
        summary["next_actions"].append("Normalize fallback-only joins and unknown lifecycle states")
    if summary["p2_gap_count"] > 0:
        summary["next_actions"].append("Backfill optional confidence/edge metadata when available")
    if not summary["next_actions"]:
        summary["next_actions"].append("No backfill blockers detected; verify production samples")

    return summary
