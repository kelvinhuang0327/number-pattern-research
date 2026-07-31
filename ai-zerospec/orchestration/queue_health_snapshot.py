from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class QueueHealthSnapshot:
    task_id: int | None
    slot_key: str | None
    queue_age_seconds: int | None
    reason_code: str
    reason_detail: str
    confidence: str
    unverified_signals: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _queue_age_seconds(created_at: str | None, now: datetime | None = None) -> int | None:
    created = _parse_iso(created_at)
    if not created:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, int((current - created).total_seconds()))


def _scheduler_disabled(settings: dict[str, Any]) -> bool:
    return str(settings.get("scheduler_enabled", "1")).strip() in {"0", "false", "False"}


def _daemon_provider_snapshot(
    task_id: int | None,
    slot_key: str | None,
    queue_age: int | None,
    daemon_running: bool,
) -> QueueHealthSnapshot:
    if daemon_running:
        return QueueHealthSnapshot(
            task_id,
            slot_key,
            queue_age,
            "WAITING_FOR_DAEMON_CLAIM",
            "copilot-daemon provider selected and daemon appears running; queue should be polled shortly",
            "medium",
        )
    return QueueHealthSnapshot(
        task_id,
        slot_key,
        queue_age,
        "DAEMON_NOT_RUNNING",
        "worker provider requires resident daemon, but daemon state does not show a running process",
        "high",
    )


def _unverified_queue_snapshot(
    task_id: int | None,
    slot_key: str | None,
    queue_age: int | None,
) -> QueueHealthSnapshot:
    if queue_age is not None and queue_age > 900:
        return QueueHealthSnapshot(
            task_id,
            slot_key,
            queue_age,
            "QUEUE_STALL_UNVERIFIED",
            "task has remained queued longer than expected, but root cause requires live worker/daemon/log correlation",
            "low",
            ("no live claim trace correlated yet",),
        )

    return QueueHealthSnapshot(
        task_id,
        slot_key,
        queue_age,
        "QUEUE_WAITING_UNVERIFIED",
        "task is queued without a confirmed blocker",
        "low",
        ("insufficient runtime evidence for exact claim blocker",),
    )


def derive_queue_health(
    task: dict[str, Any] | None,
    worker_lock: dict[str, Any] | None,
    daemon_state: dict[str, Any] | None,
    settings: dict[str, Any] | None,
    provider_block: dict[str, Any] | None,
    now: datetime | None = None,
) -> QueueHealthSnapshot:
    task = task or {}
    worker_lock = worker_lock or {}
    daemon_state = daemon_state or {}
    settings = settings or {}
    provider_block = provider_block or {}
    queue_age = _queue_age_seconds(task.get("created_at"), now=now)
    task_id = task.get("id")
    slot_key = task.get("slot_key")
    if _scheduler_disabled(settings):
        return QueueHealthSnapshot(
            task_id,
            slot_key,
            queue_age,
            "SCHEDULER_DISABLED",
            "scheduler is disabled, queued task cannot be claimed",
            "high",
        )

    if worker_lock.get("pid"):
        return QueueHealthSnapshot(
            task_id,
            slot_key,
            queue_age,
            "WORKER_LOCK_HELD",
            f"worker lock is held by pid={worker_lock.get('pid')} task_id={worker_lock.get('task_id')}",
            "high",
        )

    if provider_block:
        return QueueHealthSnapshot(
            task_id,
            slot_key,
            queue_age,
            "PROVIDER_BLOCKED",
            f"provider blocked until {provider_block.get('blocked_until') or provider_block.get('reset_hint') or 'unknown'}",
            "high",
        )

    worker_provider = str(settings.get("worker_provider") or "").strip().lower()
    daemon_running = bool(daemon_state.get("running"))
    if worker_provider == "copilot-daemon":
        return _daemon_provider_snapshot(task_id, slot_key, queue_age, daemon_running)

    if not worker_provider:
        return QueueHealthSnapshot(
            task_id,
            slot_key,
            queue_age,
            "WORKER_PROVIDER_UNKNOWN",
            "worker provider is empty or unreadable",
            "medium",
            ("worker_provider missing",),
        )

    return _unverified_queue_snapshot(task_id, slot_key, queue_age)