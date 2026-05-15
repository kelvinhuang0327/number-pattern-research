#!/usr/bin/env python3
"""
Resident GitHub Copilot worker daemon.

Runs inside a user-session context and continuously polls the orchestrator queue
when worker_provider is set to `copilot-daemon`.
"""

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator import common, db, worker_tick, execution_policy, health, llm_audit

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [copilot-daemon] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

RUNNER = "copilot-daemon"
POLL_SECONDS = int(os.environ.get("COPILOT_DAEMON_POLL_SECONDS", "10"))
STALE_QUEUE_AGE_SECONDS = int(os.environ.get("COPILOT_DAEMON_STALE_QUEUE_AGE_SECONDS", "300"))
STALE_NO_QUEUE_STREAK = int(os.environ.get("COPILOT_DAEMON_STALE_NO_QUEUE_STREAK", "3"))
SHUTDOWN = False


def _set_state(status: str, **kwargs):
    current = common.read_copilot_daemon_state()
    common.write_copilot_daemon_state(
        pid=os.getpid(),
        status=status,
        started_at=current.get("started_at") or datetime.now(timezone.utc).isoformat(),
        heartbeat_at=datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )


def _install_signal_handlers():
    def _handle_signal(signum, _frame):
        global SHUTDOWN
        SHUTDOWN = True
        logger.info("Received signal %s, shutting down daemon", signum)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)


def _acquire_singleton() -> bool:
    state = common.copilot_daemon_status()
    existing_pid = state.get("pid")
    if existing_pid and existing_pid != os.getpid() and state.get("running"):
        logger.warning("Another copilot daemon is already running (PID=%s)", existing_pid)
        return False
    _set_state("starting", current_task_id=None, worker_pid=None)
    return True


def _should_force_no_queue_for_test() -> bool:
    return os.environ.get("COPILOT_DAEMON_TEST_FORCE_NO_QUEUE", "0").strip() == "1"


def _maybe_trigger_stale_claim_guard(outcome: str, consecutive_no_queue: int) -> bool:
    """Detect stale queued research task + ineffective claim loop and request restart."""
    if outcome != "no-queued-task":
        return False

    stale_task = db.get_oldest_stale_queued_research_task(min_age_seconds=STALE_QUEUE_AGE_SECONDS)
    if not stale_task:
        return False

    task_id = int(stale_task.get("id"))
    has_claim = db.has_claim_event_for_task(task_id)
    # Trigger when stale queue exists and daemon keeps saying no-queued-task.
    # - consecutive no-queue streak reached, OR
    # - still zero claim events for stale task.
    if consecutive_no_queue < max(1, STALE_NO_QUEUE_STREAK) and has_claim:
        return False

    msg = (
        f"stale claim detected: task_id={task_id} status={stale_task.get('status')} "
        f"created_at={stale_task.get('created_at')} no_queue_streak={consecutive_no_queue} "
        f"has_claim_event={int(has_claim)} age_s>={STALE_QUEUE_AGE_SECONDS}"
    )
    _set_state(
        "restarting",
        current_task_id=task_id,
        worker_pid=None,
        note=f"stale-claim-guard: {msg}",
    )
    db.log_tick(RUNNER, "COPILOT_DAEMON_STALE_CLAIM_DETECTED", task_id=task_id, message=msg)
    db.log_tick(
        RUNNER,
        "COPILOT_DAEMON_AUTO_RESTART_REQUESTED",
        task_id=task_id,
        message="stale-claim guard requested self-exit for launchd restart",
    )
    common.log_jsonl(
        RUNNER,
        "COPILOT_DAEMON_STALE_CLAIM_DETECTED",
        task_id=task_id,
        dedupe_key=stale_task.get("dedupe_key"),
        created_at=stale_task.get("created_at"),
        no_queue_streak=consecutive_no_queue,
        has_claim_event=has_claim,
        stale_queue_age_seconds=STALE_QUEUE_AGE_SECONDS,
        action="self-exit-for-launchd-restart",
    )
    return True


def run_once() -> str:
    common.ensure_dirs()
    lock = db.get_worker_lock()
    worker_provider = db.get_worker_provider()

    if lock and lock.get("pid"):
        pid = lock["pid"]
        task_id = lock.get("task_id")
        if common.is_process_alive(pid):
            db.update_worker_heartbeat()
            _set_state("busy", current_task_id=task_id, worker_pid=pid, worker_provider=worker_provider)
            return "busy"

        logger.info("Detected dead worker PID=%s for task %s; finalizing", pid, task_id)
        _set_state("finalizing", current_task_id=task_id, worker_pid=pid, worker_provider=worker_provider)
        worker_tick._finalize(lock)
        return "finalized"

    if worker_provider != "copilot-daemon":
        _set_state("idle", current_task_id=None, worker_pid=None, worker_provider=worker_provider, note="provider-not-selected")
        return "provider-not-selected"

    decision = execution_policy.evaluate("copilot-daemon", scope="main", provider=worker_provider)
    if not decision.allowed:
        execution_policy.record_skip(decision)
        reason = (decision.skip_reason or "blocked").lower()
        llm_audit.write_blocked(
            runner_type=RUNNER,
            usage_role="worker",
            provider=worker_provider,
            block_reason=reason,
            trigger_source="worker_claim",
            extra_skip=1,
        )
        _set_state("idle", current_task_id=None, worker_pid=None, worker_provider=worker_provider, note=reason)
        return reason

    provider_block = common.get_provider_rate_limit_block(worker_provider)
    if provider_block:
        reset_hint = provider_block.get("reset_hint") or provider_block.get("blocked_until") or "unknown"
        llm_audit.write_blocked(
            runner_type=RUNNER,
            usage_role="worker",
            provider=worker_provider,
            block_reason=f"rate_limited_until_{reset_hint}",
            task_id=provider_block.get("task_id"),
            trigger_source="worker_claim",
            extra_skip=1,
        )
        _set_state(
            "rate_limited",
            current_task_id=provider_block.get("task_id"),
            worker_pid=None,
            worker_provider=worker_provider,
            note=f"rate-limited until {reset_hint}",
        )
        db.log_tick(RUNNER, "COPILOT_DAEMON_RATE_LIMIT_WAIT", task_id=provider_block.get("task_id"), message=f"Provider {worker_provider} waiting for reset: {reset_hint}")
        common.log_jsonl(RUNNER, "COPILOT_DAEMON_RATE_LIMIT_WAIT", provider=worker_provider, task_id=provider_block.get("task_id"), reset_hint=reset_hint)
        return "rate-limited"

    if _should_force_no_queue_for_test():
        _set_state("idle", current_task_id=None, worker_pid=None, worker_provider=worker_provider, note="forced-no-queue-test")
        return "no-queued-task"

    queued = db.get_next_research_task_by_priority()
    if not queued:
        _set_state("idle", current_task_id=None, worker_pid=None, worker_provider=worker_provider, note="no-queued-task")
        return "no-queued-task"

    task = queued
    _set_state("claiming", current_task_id=task["id"], worker_pid=None, worker_provider=worker_provider)
    claimed = worker_tick._claim(task)
    if not claimed:
        _set_state("idle", current_task_id=task["id"], worker_pid=None, worker_provider=worker_provider, note="claim-blocked")
        return "claim-blocked"
    lock = db.get_worker_lock()
    _set_state(
        "busy",
        current_task_id=task["id"],
        worker_pid=lock.get("pid") if lock else None,
        worker_provider=worker_provider,
    )
    db.log_tick(RUNNER, "COPILOT_DAEMON_CLAIMED", task_id=task["id"], message=f"Claimed task {task['id']}")
    common.log_jsonl(RUNNER, "COPILOT_DAEMON_CLAIMED", task_id=task["id"])
    return "claimed"


def serve_forever(poll_seconds: int = POLL_SECONDS):
    _install_signal_handlers()
    if not _acquire_singleton():
        return 1

    logger.info("Copilot daemon started with poll=%ss", poll_seconds)
    db.log_tick(RUNNER, "COPILOT_DAEMON_STARTED", message=f"PID={os.getpid()} poll={poll_seconds}s")
    common.log_jsonl(RUNNER, "COPILOT_DAEMON_STARTED", pid=os.getpid(), poll_seconds=poll_seconds)

    exit_code = 0
    consecutive_no_queue = 0
    try:
        while not SHUTDOWN:
            try:
                outcome = run_once()
                if outcome == "no-queued-task":
                    consecutive_no_queue += 1
                else:
                    consecutive_no_queue = 0
                common.log_jsonl(RUNNER, "COPILOT_DAEMON_TICK", tick_outcome=outcome)
                if _maybe_trigger_stale_claim_guard(outcome, consecutive_no_queue):
                    exit_code = 75
                    break
            except Exception as exc:
                exit_code = 1
                logger.exception("Daemon tick failed: %s", exc)
                _set_state("error", error_message=str(exc), current_task_id=None)
                db.log_tick(RUNNER, "COPILOT_DAEMON_ERROR", message=str(exc))
                common.log_jsonl(RUNNER, "COPILOT_DAEMON_ERROR", error=str(exc))
            time.sleep(max(1, poll_seconds))
    finally:
        common.clear_copilot_daemon_state(pid=os.getpid())
        db.log_tick(RUNNER, "COPILOT_DAEMON_STOPPED", message=f"PID={os.getpid()} exit={exit_code}")
        common.log_jsonl(RUNNER, "COPILOT_DAEMON_STOPPED", pid=os.getpid(), exit_code=exit_code)

    return exit_code


def main():
    parser = argparse.ArgumentParser(description="Resident Copilot worker daemon")
    parser.add_argument("--once", action="store_true", help="Run a single poll/claim cycle and exit")
    parser.add_argument("--poll-seconds", type=int, default=POLL_SECONDS, help="Polling interval for resident mode")
    args = parser.parse_args()

    # Import guard: validate critical modules before daemon starts
    if not health.run_startup_import_guard("copilot-daemon"):
        logger.error("[health] Import guard failed — copilot-daemon cannot start")
        return 1

    db.init_db()
    if args.once:
        _install_signal_handlers()
        if not _acquire_singleton():
            return 1
        try:
            run_once()
            return 0
        finally:
            common.clear_copilot_daemon_state(pid=os.getpid())

    return serve_forever(poll_seconds=args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
