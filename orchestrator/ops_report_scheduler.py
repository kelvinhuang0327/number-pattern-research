"""
Phase 9 — Autonomous Ops Report Scheduler Hook

Tracks when the last ops report was generated and triggers a new one
when the configured interval elapses.

Design:
  - State stored in runtime/agent_orchestrator/ops_report_state.json
  - No destructive actions
  - Does not affect planner or worker logic
  - Thread-safe: uses file-level state, not in-process shared memory

Usage (manual trigger):
  from orchestrator.ops_report_scheduler import trigger_ops_report_now
  trigger_ops_report_now()

Usage (called from planner_tick as a non-blocking side-effect):
  from orchestrator.ops_report_scheduler import maybe_trigger_ops_report
  maybe_trigger_ops_report()          # 8h default interval
  maybe_trigger_ops_report("24h")     # daily
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_STATE_PATH = (
    _REPO_ROOT / "runtime" / "agent_orchestrator" / "ops_report_state.json"
)
_REPORTS_JSON = _REPO_ROOT / "data" / "wbc_backend" / "reports"
_REPORTS_MD   = _REPO_ROOT / "docs" / "orchestration"

# ── Intervals ──────────────────────────────────────────────────────────────
_INTERVAL_8H  = timedelta(hours=8)
_INTERVAL_24H = timedelta(hours=24)


def _load_state() -> dict[str, Any]:
    if _STATE_PATH.exists():
        try:
            return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _run_report(window: str) -> dict[str, Any]:
    """Execute report generation. Returns the report dict."""
    import json as _json
    from datetime import datetime as _dt, timezone as _tz
    from orchestrator.optimization_ops_report import generate_report, render_markdown

    report = generate_report(window=window)
    ts = _dt.now(_tz.utc).strftime("%Y-%m-%d_%H%M")

    # Write JSON
    json_path = _REPORTS_JSON / f"optimization_ops_report_{ts}.json"
    _REPORTS_JSON.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        _json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Write Markdown
    md = render_markdown(report)
    md_path = _REPORTS_MD / f"optimization_ops_report_{ts}.md"
    _REPORTS_MD.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md, encoding="utf-8")

    logger.info(
        "[OpsScheduler] Report generated: window=%s  classification=%s  "
        "completed=%s  json=%s",
        window,
        report.get("classification"),
        report.get("tasks_completed", 0),
        json_path,
    )
    return report


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def trigger_ops_report_now(window: str = "8h") -> dict[str, Any]:
    """
    Manually trigger an ops report immediately, bypassing the interval check.

    SAFE: read-only report generation; does not affect planner or worker.
    Returns the generated report dict.
    """
    now = datetime.now(timezone.utc).isoformat()
    try:
        report = _run_report(window=window)
        state = _load_state()
        key = f"last_triggered_{window}"
        state[key] = now
        state["last_triggered_any"] = now
        _save_state(state)
        return report
    except Exception as exc:
        logger.warning("[OpsScheduler] trigger_ops_report_now failed: %s", exc)
        return {"error": str(exc), "triggered_at": now}


def maybe_trigger_ops_report(window: str = "8h") -> dict[str, Any] | None:
    """
    Trigger an ops report only if the configured interval has elapsed since the last run.
    Called as a non-blocking side-effect from the planner tick or cron daemon.

    SAFE: never modifies planner/worker logic; never deletes tasks or reports.

    Returns the report dict if triggered, None if interval has not elapsed.
    """
    interval = _INTERVAL_24H if "24" in window else _INTERVAL_8H
    state = _load_state()
    key = f"last_triggered_{window}"
    last_ts_str: str | None = state.get(key)

    if last_ts_str:
        try:
            last_ts = datetime.fromisoformat(last_ts_str)
            if last_ts.tzinfo is None:
                last_ts = last_ts.replace(tzinfo=timezone.utc)
            elapsed = datetime.now(timezone.utc) - last_ts
            if elapsed < interval:
                logger.debug(
                    "[OpsScheduler] Skipping %s report — %.0fm elapsed (interval=%.0fh)",
                    window,
                    elapsed.total_seconds() / 60,
                    interval.total_seconds() / 3600,
                )
                return None
        except Exception:
            pass  # malformed timestamp → proceed with generation

    logger.info("[OpsScheduler] Interval elapsed, generating %s ops report.", window)
    return trigger_ops_report_now(window=window)


def get_last_report_summary(window: str = "8h") -> dict[str, Any]:
    """
    Return metadata about the last generated ops report without generating a new one.
    """
    state = _load_state()
    key = f"last_triggered_{window}"
    return {
        "last_triggered": state.get(key),
        "last_triggered_any": state.get("last_triggered_any"),
        "state_path": str(_STATE_PATH),
    }
