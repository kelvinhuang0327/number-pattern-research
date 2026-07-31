from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class TaskFeedbackProjection:
    task_id: int | None
    review_status: str
    strategy_status: str
    task_summary_status: str
    negative_learning_required: bool
    planner_note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def project_cto_decision_to_task_feedback(
    task_id: int | None,
    cto_decision: str | None,
    strategy_decision: str | None,
    reason: str | None,
) -> TaskFeedbackProjection:
    review = str(cto_decision or "UNREVIEWED").strip().upper()
    strategy = str(strategy_decision or "UNASSESSED").strip().upper()
    detail = str(reason or "").strip()

    if review.startswith("REJECTED"):
        return TaskFeedbackProjection(
            task_id=task_id,
            review_status=review,
            strategy_status=strategy,
            task_summary_status="REJECTED",
            negative_learning_required=True,
            planner_note=detail or "CTO rejected this task output; avoid repeating the same delivery path without change.",
        )

    if strategy in {"REJECT_STRATEGY", "NEEDS_RESEARCH"}:
        return TaskFeedbackProjection(
            task_id=task_id,
            review_status=review,
            strategy_status=strategy,
            task_summary_status="REJECTED",
            negative_learning_required=True,
            planner_note=detail or "Research direction is not promotable; add to negative-space memory and redirect planner.",
        )

    if review in {"APPROVED_FOR_MERGE", "MERGED"} or strategy in {"APPROVE_STRATEGY", "SHADOW_STRATEGY"}:
        return TaskFeedbackProjection(
            task_id=task_id,
            review_status=review,
            strategy_status=strategy,
            task_summary_status="DONE",
            negative_learning_required=False,
            planner_note=detail or "Governance accepted this direction.",
        )

    return TaskFeedbackProjection(
        task_id=task_id,
        review_status=review,
        strategy_status=strategy,
        task_summary_status="IN_PROGRESS",
        negative_learning_required=False,
        planner_note=detail or "Awaiting clearer governance or strategy decision.",
    )


def build_negative_learning_record(
    game_type: str | None,
    family: str | None,
    source_task_id: int | None,
    review_status: str,
    planner_note: str,
) -> dict[str, Any]:
    return {
        "game_type": game_type or "UNKNOWN",
        "family": family or "UNKNOWN",
        "source_task_id": source_task_id,
        "status": "REJECT",
        "reason": planner_note,
        "source": f"task:{source_task_id}" if source_task_id is not None else "task:unknown",
        "retry_condition": "only retry after materially new evidence or validation design",
        "review_status": review_status,
    }