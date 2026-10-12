from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


EXTERNAL_QUEUED = "QUEUED"
EXTERNAL_IN_PROGRESS = "IN_PROGRESS"
EXTERNAL_DONE = "DONE"
EXTERNAL_FAILED = "FAILED"
EXTERNAL_REJECTED = "REJECTED"


@dataclass(frozen=True)
class CanonicalState:
    execution_status: str
    review_status: str
    strategy_status: str
    knowledge_status: str
    external_status: str
    reasons: tuple[str, ...] = field(default_factory=tuple)


def _normalize(value: str | None, default: str) -> str:
    text = str(value or "").strip().upper()
    return text or default


def derive_external_status(
    execution_status: str | None,
    review_status: str | None = None,
    strategy_status: str | None = None,
    knowledge_status: str | None = None,
    queue_health_reason: str | None = None,
) -> CanonicalState:
    execution = _normalize(execution_status, "UNKNOWN")
    review = _normalize(review_status, "UNREVIEWED")
    strategy = _normalize(strategy_status, "UNASSESSED")
    knowledge = _normalize(knowledge_status, "UNKNOWN")
    reasons: list[str] = []

    if queue_health_reason:
        reasons.append(queue_health_reason)

    if execution == "QUEUED":
        return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_QUEUED, tuple(reasons))

    if execution in {"RUNNING", "BLOCKED_ENV"}:
        if execution == "BLOCKED_ENV":
            reasons.append("execution blocked by environment")
        return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_IN_PROGRESS, tuple(reasons))

    if execution in {"FAILED", "FAILED_RATE_LIMIT", "FAILED_NO_EDGE", "FAILED_WEAK_EDGE"}:
        reasons.append(f"execution terminal failure: {execution}")
        return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_FAILED, tuple(reasons))

    if execution in {"FAILED_ACCEPTANCE", "FAILED_FORMAT_CONTRACT", "FAILED_RESEARCH_CONTRACT", "REPLAN_REQUIRED", "CANCELLED"}:
        reasons.append(f"execution rejected before acceptance: {execution}")
        return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_REJECTED, tuple(reasons))

    if execution == "COMPLETED":
        if review.startswith("REJECTED") or strategy in {"REJECTED", "NEEDS_RESEARCH"}:
            reasons.append(f"review/strategy rejection: review={review}, strategy={strategy}")
            return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_REJECTED, tuple(reasons))
        if review in {"PENDING_REVIEW", "DEFERRED_CONFLICT", "UNREVIEWED"}:
            reasons.append(f"completion pending governance: {review}")
            return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_IN_PROGRESS, tuple(reasons))
        if knowledge in {"LEARNING_REVIEW_REQUIRED", "PENDING_WRITEBACK"}:
            reasons.append(f"knowledge loop incomplete: {knowledge}")
            return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_IN_PROGRESS, tuple(reasons))
        return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_DONE, tuple(reasons))

    reasons.append(f"unmapped execution status: {execution}")
    return CanonicalState(execution, review, strategy, knowledge, EXTERNAL_IN_PROGRESS, tuple(reasons))


def summarize_reason_chain(state: CanonicalState) -> str:
    if not state.reasons:
        return state.external_status
    return f"{state.external_status}: " + "; ".join(state.reasons)


def merge_reason_lists(*groups: Iterable[str]) -> tuple[str, ...]:
    merged: list[str] = []
    for group in groups:
        for item in group:
            if item and item not in merged:
                merged.append(item)
    return tuple(merged)