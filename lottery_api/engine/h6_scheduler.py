"""
H6 Daily Report Scheduler
==========================
Wraps the report generator and alert engine into a single callable pipeline.
Designed to be triggered:
  - Manually via scripts/h6_schedule_run.py
  - After each DAILY_539 draw outcome is recorded
  - By a cron job or watchdog after draw time

Pipeline steps:
  1. generate_report(game_type, latest=True, output_dir=output_dir)
     — writes JSON + Markdown to runtime/h6_daily_reports/
  2. process_report_alerts(report, game_type)
     — logs tick, creates CTO backlog item, creates rollback task if needed
  3. Returns a merged summary dict

Does NOT raise on PENDING_OUTCOME — that's a valid non-error state.

2026-05  Created (H6 Daily Report Automation, Phase 2)
"""
from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

# ── sys.path ───────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_LOTTERY_API = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_LOTTERY_API)
for _p in (_LOTTERY_API, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from engine.h6_report_generator import generate_report       # noqa: E402
from engine.h6_alert_engine import process_report_alerts      # noqa: E402
from engine.draw_no_hygiene import is_test_draw_no            # noqa: E402


def run_scheduled_report(
    game_type: str = "DAILY_539",
    output_dir: str | None = None,
) -> dict:
    """
    Run the daily report + alert pipeline for *game_type*.

    Returns a summary dict:
        success            bool
        draw_no            str
        report_status      str   — COMPLETE | PENDING_OUTCOME
        risk_level         str   — LOW | MEDIUM | HIGH
        action             str
        json_path          str | None
        markdown_path      str | None
        alert              dict  — result from process_report_alerts()
        error              str | None
    """
    try:
        report = generate_report(
            game_type=game_type,
            latest=True,
            output_dir=output_dir,
        )
    except Exception as exc:
        logger.error("[h6_scheduler] generate_report failed: %s", exc)
        return {
            "success": False,
            "draw_no": None,
            "report_status": "ERROR",
            "risk_level": None,
            "action": None,
            "json_path": None,
            "markdown_path": None,
            "alert": {},
            "error": str(exc),
        }

    draw_no = report.get("report_meta", {}).get("draw_no")
    report_status = report.get("report_meta", {}).get("report_status")
    risk_level = report.get("risk_assessment", {}).get("risk_level")
    action = report.get("action_recommendation", {}).get("action")
    json_path = report.get("output", {}).get("json_path")
    markdown_path = report.get("output", {}).get("markdown_path")

    # ── hygiene guard: skip alerts for test/synthetic draw_nos ─────────────────
    if is_test_draw_no(draw_no or "", game_type):
        logger.info(
            "[h6_scheduler] skipping alert for test/synthetic draw_no=%s (environment=test)",
            draw_no,
        )
        alert_result = {
            "alerted": False,
            "draw_no": draw_no,
            "skipped_reason": "test_draw_no",
        }
    else:
        alert_result = process_report_alerts(report, game_type=game_type)

    return {
        "success": True,
        "draw_no": draw_no,
        "report_status": report_status,
        "risk_level": risk_level,
        "action": action,
        "json_path": json_path,
        "markdown_path": markdown_path,
        "alert": alert_result,
        "error": None,
    }
