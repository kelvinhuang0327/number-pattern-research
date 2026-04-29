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

from orchestrator import common, db, worker_tick, execution_policy, health

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [copilot-daemon] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

RUNNER = "copilot-daemon"
POLL_SECONDS = int(os.environ.get("COPILOT_DAEMON_POLL_SECONDS", "10"))
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
        _set_state("idle", current_task_id=None, worker_pid=None, worker_provider=worker_provider, note=reason)
        return reason

    provider_block = common.get_provider_rate_limit_block(worker_provider)
    if provider_block:
        reset_hint = provider_block.get("reset_hint") or provider_block.get("blocked_until") or "unknown"
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

    queued = db.list_tasks(status="QUEUED", limit=1)
    if not queued:
        _set_state("idle", current_task_id=None, worker_pid=None, worker_provider=worker_provider, note="no-queued-task")
        return "no-queued-task"

    task = queued[0]
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
    try:
        while not SHUTDOWN:
            try:
                outcome = run_once()
                common.log_jsonl(RUNNER, "COPILOT_DAEMON_TICK", tick_outcome=outcome)
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
