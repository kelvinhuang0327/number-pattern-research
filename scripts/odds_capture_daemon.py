#!/usr/bin/env python3
"""
MLB Odds Capture Daemon

Standalone long-running process that captures MLB odds at regular intervals.
Managed via launchd (macOS) for automatic startup and crash recovery.

Usage:
  python3 scripts/odds_capture_daemon.py                  # Default: 15-min interval
  python3 scripts/odds_capture_daemon.py --interval 10    # Custom interval (minutes)
  python3 scripts/odds_capture_daemon.py --once            # Single capture then exit

Management (prefer the control script):
  scripts/manage_daemon.sh start|stop|restart|status
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
PID_PATH = ROOT / "build" / "runtime_artifacts" / "odds_capture.pid"
HEARTBEAT_PATH = LOG_DIR / "daemon_heartbeat.jsonl"

# launchd captures stdout/stderr directly; we only add FileHandler for
# non-launchd (manual/nohup) runs detected by absence of LAUNCHED_BY_LAUNCHD.
_handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
if not os.environ.get("LAUNCHED_BY_LAUNCHD"):
    _handlers.append(logging.FileHandler(LOG_DIR / "odds_capture.log", mode="a"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=_handlers,
)
logger = logging.getLogger("odds_capture_daemon")

_running = True


def _handle_signal(signum: int, frame: object) -> None:
    global _running
    logger.info("Received signal %d, shutting down gracefully...", signum)
    _running = False


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# PID management — prevents duplicate daemons
# ---------------------------------------------------------------------------

def _is_process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _acquire_pid_lock() -> bool:
    """
    Write PID file. Returns False if another instance is already running.
    Removes stale PID files from dead processes automatically.
    """
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)

    if PID_PATH.exists():
        try:
            existing_pid = int(PID_PATH.read_text().strip())
        except (ValueError, OSError):
            existing_pid = None

        if existing_pid and _is_process_alive(existing_pid):
            logger.error(
                "Daemon already running (pid=%d). Exiting to prevent duplicate.",
                existing_pid,
            )
            return False

        # Stale PID — process is gone
        logger.warning("Removing stale PID file (pid=%s was dead)", existing_pid)
        PID_PATH.unlink(missing_ok=True)

    PID_PATH.write_text(str(os.getpid()))
    return True


def _release_pid_lock() -> None:
    if PID_PATH.exists():
        try:
            stored = int(PID_PATH.read_text().strip())
            if stored == os.getpid():
                PID_PATH.unlink(missing_ok=True)
        except (ValueError, OSError):
            pass


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def run_capture() -> dict:
    """Execute one capture cycle."""
    from wbc_backend.mlb_data.odds_capture_scheduler import run_scheduled_capture

    return run_scheduled_capture(
        odds_api_key=os.environ.get("ODDS_API_KEY"),
        force=True,
    )


def _write_heartbeat(result: dict) -> None:
    """Append one heartbeat row (schema v2). Never raise — observability must be safe."""
    try:
        import json as _json
        import re as _re
        from pathlib import Path as _Path

        from wbc_backend.mlb_data.heartbeat_schema import make_semantic_heartbeat_row

        state_path = ROOT / "data" / "mlb_context" / "external_closing_state.json"
        state: dict = {}
        if state_path.exists():
            try:
                state = _json.loads(state_path.read_text(encoding="utf-8"))
            except Exception:
                state = {}

        # Derive next_trigger_minutes from external_closing trigger_reason.
        # (The key lives at result["result"]["external_closing"]["trigger_reason"].)
        inner = ((result or {}).get("result") or {})
        ec = inner.get("external_closing") or {}
        next_trigger_min: float | None = None
        reason = str(ec.get("trigger_reason") or "")
        m = _re.search(r"(\d+(?:\.\d+)?)\s*min", reason)
        if m:
            try:
                next_trigger_min = float(m.group(1))
            except Exception:
                next_trigger_min = None

        row = make_semantic_heartbeat_row(
            result=result,
            existing_state=state,
            timestamp=_now_utc(),
            next_trigger_minutes=next_trigger_min,
        )
        _Path(HEARTBEAT_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(HEARTBEAT_PATH, "a", encoding="utf-8") as fh:
            fh.write(_json.dumps(row, ensure_ascii=False) + "\n")

        # P28D.2 — surface TSL monitor alerts to operator log path
        try:
            from wbc_backend.mlb_data.tsl_monitor_alert_formatter import (
                emit_alert_if_needed,
            )
            emit_alert_if_needed(row)
        except Exception as _alert_exc:
            logger.warning("TSL alert emission failed (non-fatal): %s", _alert_exc)
    except Exception as exc:
        logger.warning("heartbeat emission failed: %s", exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="MLB Odds Capture Daemon")
    parser.add_argument(
        "--interval",
        type=int,
        default=15,
        help="Capture interval in minutes (default: 15)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one capture and exit (skips PID lock)",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # In --once mode skip duplicate prevention (used for ad-hoc testing)
    if not args.once:
        if not _acquire_pid_lock():
            return 1

    interval_seconds = args.interval * 60

    logger.info(
        "Odds Capture Daemon started (interval=%dmin, pid=%d, launchd=%s)",
        args.interval,
        os.getpid(),
        bool(os.environ.get("LAUNCHED_BY_LAUNCHD")),
    )

    cycle = 0
    try:
        while _running:
            cycle += 1
            logger.info("=== Capture cycle #%d at %s ===", cycle, _now_utc())

            try:
                result = run_capture()
                status = result.get("status", "unknown")
                if status == "captured":
                    cap = result.get("result", {})
                    logger.info(
                        "Captured: games_updated=%d, snapshots_added=%d, duplicates=%d",
                        cap.get("games_updated", 0),
                        cap.get("snapshots_added", 0),
                        cap.get("duplicates_skipped", 0),
                    )
                else:
                    logger.info("Status: %s", status)
                _write_heartbeat(result)
            except Exception:
                logger.exception("Capture cycle failed — will retry next interval")
                _write_heartbeat({"status": "exception"})

            if args.once:
                logger.info("--once mode: exiting after first capture")
                break

            logger.info("Next capture in %d minutes", args.interval)
            deadline = time.monotonic() + interval_seconds
            while _running and time.monotonic() < deadline:
                time.sleep(min(10, deadline - time.monotonic()))

    finally:
        _release_pid_lock()
        logger.info("Daemon stopped (cycles=%d)", cycle)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
