#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator import db
from orchestrator import execution_policy


def _print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _run_daemon(disable_provider: bool) -> None:
    from orchestrator.planner_tick import run_planner_tick
    from orchestrator.worker_tick import run_worker_tick

    db.init_db()
    if disable_provider:
        print("Agent orchestrator daemon started in no-provider compatibility mode.")
    else:
        print("Agent orchestrator daemon started. Press Ctrl+C to stop.")

    PLANNER_INTERVAL = 600  # run planner every 10 minutes
    last_planner_at = 0.0

    try:
        while True:
            decision = execution_policy.evaluate_execution(
                runner="agent_orchestrator_daemon",
                background=True,
            )
            if not decision["allowed"]:
                time.sleep(5)
                continue

            now = time.time()
            worker_result = run_worker_tick()
            worker_skipped = worker_result.get("status") == "SKIPPED"
            planner_due = (now - last_planner_at) >= PLANNER_INTERVAL
            mining_needed = worker_result.get("mining_needed", False)

            # Run planner when: (a) worker found no queued tasks, (b) 10-minute interval elapsed,
            # or (c) worker signals mining is needed (replan_required_count > 0).
            if worker_skipped or planner_due or mining_needed:
                planner_result = run_planner_tick()
                planner_status = planner_result.get("status", "")
                # Only reset timer on meaningful planner activity (not SKIPPED)
                if planner_status not in ("SKIPPED",):
                    last_planner_at = now
                    print(
                        f"[Daemon] planner_tick status={planner_status}"
                        + (f" task_id={planner_result['task_id']}" if "task_id" in planner_result else "")
                    )

            if worker_skipped:
                time.sleep(10)
            else:
                time.sleep(2)
    except KeyboardInterrupt:
        print("\nDaemon stopped.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dual-agent orchestrator controls")
    parser.add_argument(
        "--profile",
        default="",
        help="Legacy profile option kept for compatibility; ignored by this repo.",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="Initialize orchestrator database.")

    planner_cmd = sub.add_parser("planner-tick", help="Run planner tick once.")
    planner_cmd.add_argument("--force", action="store_true", help="Ignore skip guards.")

    worker_cmd = sub.add_parser("worker-tick", help="Run worker tick once.")
    worker_cmd.add_argument(
        "--no-provider",
        action="store_true",
        help="Do not execute provider command; finalize as runtime blocked.",
    )

    tick_all = sub.add_parser("tick-all", help="Run planner then worker once.")
    tick_all.add_argument("--force", action="store_true", help="Force planner tick.")
    tick_all.add_argument(
        "--no-provider",
        action="store_true",
        help="Do not execute worker provider command.",
    )

    daemon = sub.add_parser("daemon", help="Run scheduler daemon loop.")
    daemon.add_argument(
        "--no-provider",
        action="store_true",
        help="Legacy compatibility flag; provider execution control is not used in this repo.",
    )

    api = sub.add_parser("api", help="Run local orchestrator API/UI server.")
    api.add_argument("--host", default="127.0.0.1")
    api.add_argument("--port", type=int, default=8787)

    sub.add_parser("summary", help="Print scheduler/task summary.")

    args = parser.parse_args()
    db.init_db()

    if args.cmd == "init":
        _print({"status": "ok", "database_path": db.DB_PATH})
        return 0

    if args.cmd == "planner-tick":
        from orchestrator.planner_tick import run_planner_tick

        _print(run_planner_tick())
        return 0

    if args.cmd == "worker-tick":
        from orchestrator.worker_tick import run_worker_tick

        _print(run_worker_tick())
        return 0

    if args.cmd == "tick-all":
        from orchestrator.planner_tick import run_planner_tick
        from orchestrator.worker_tick import run_worker_tick

        planner_result = run_planner_tick()
        worker_result = run_worker_tick()
        _print({"planner": planner_result, "worker": worker_result})
        return 0

    if args.cmd == "daemon":
        _run_daemon(disable_provider=args.no_provider)
        return 0

    if args.cmd == "api":
        from orchestrator.api import run_api_server

        run_api_server(args.profile, host=args.host, port=args.port)
        return 0

    if args.cmd == "summary":
        from orchestrator.common import get_current_timestamp
        from orchestrator.scheduler import get_scheduler_status

        payload = {
            "scheduler": {
                "enabled": execution_policy.get_state()["scheduler_enabled"],
                "cto_enabled": execution_policy.get_state()["cto_scheduler_enabled"],
                "runtime": get_scheduler_status(),
                "updated_at": get_current_timestamp(),
            },
            "execution_policy": execution_policy.get_state(),
            "counts": db.count_tasks_by_status(),
            "latest_task": db.get_latest_task(),
            "recent_runs": db.list_runs(limit=10),
        }
        _print(payload)
        return 0

    raise RuntimeError(f"Unsupported command: {args.cmd}")


if __name__ == "__main__":
    raise SystemExit(main())
