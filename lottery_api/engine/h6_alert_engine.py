"""
H6 Alert Engine
===============
Evaluates a generated H6 daily operations report and fires alerts when
risk_level == "HIGH" or action is in {PREPARE_ROLLBACK, ROLLBACK_ACTIVE,
MANUAL_REVIEW_REQUIRED}.

Alert actions (all idempotent / deduped by draw_no):
  1. log_tick("h6-alert", "H6_DAILY_REPORT_ALERT") in agent_task_runs
  2. INSERT OR IGNORE into cto_backlog_items (finding_id = h6_alert:{game_type}:{draw_no})
  3. If rollback_status != "ACTIVE": create_task for rollback follow-up (deduped)

2026-05  Created (H6 Daily Report Automation, Phase 2)
"""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── sys.path — make orchestrator importable ───────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_LOTTERY_API = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_LOTTERY_API)
_ORCH = os.path.join(_ROOT, "orchestrator")
for _p in (_ORCH, _ROOT, _LOTTERY_API):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from engine.draw_no_hygiene import is_test_draw_no  # noqa: E402

# ── constants ─────────────────────────────────────────────────────────────────
ALERT_TRIGGER_ACTIONS = frozenset(
    {"PREPARE_ROLLBACK", "ROLLBACK_ACTIVE", "MANUAL_REVIEW_REQUIRED"}
)
_CTO_RUN_ID = "H6_ALERT_ENGINE"


# ── lazy DB helpers ───────────────────────────────────────────────────────────

def _orch_db():
    """Return orchestrator.db module (lazy import so lottery_api tests still work)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "orchestrator_db", os.path.join(_ORCH, "db.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _get_raw_conn() -> sqlite3.Connection:
    """Open a raw SQLite connection to orchestrator.db."""
    db_path = os.path.join(_ROOT, "runtime", "agent_orchestrator", "orchestrator.db")
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


# ── public API ────────────────────────────────────────────────────────────────

def should_alert(report: dict) -> bool:
    """Return True if the report meets alert criteria."""
    risk_level = report.get("risk_assessment", {}).get("risk_level", "LOW")
    action = report.get("action_recommendation", {}).get("action", "")
    return risk_level == "HIGH" or action in ALERT_TRIGGER_ACTIONS


def has_alert_for_draw(draw_no: str, game_type: str = "DAILY_539") -> bool:
    """Return True if a cto_backlog_items alert row already exists for this draw_no."""
    finding_id = f"h6_alert:{game_type}:{draw_no}"
    try:
        conn = _get_raw_conn()
        try:
            row = conn.execute(
                "SELECT id FROM cto_backlog_items WHERE finding_id = ? LIMIT 1",
                (finding_id,),
            ).fetchone()
            return bool(row)
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("[h6_alert_engine] has_alert_for_draw error: %s", exc)
        return False


def process_report_alerts(
    report: dict, game_type: str = "DAILY_539"
) -> dict:
    """
    Evaluate a generated report and fire alerts when conditions are met.

    Returns a result dict with keys:
        alerted            bool — True if alert was actually fired this call
        draw_no            str
        risk_level         str
        action             str
        duplicate          bool — True if alert already existed (skipped)
        tick_logged        bool — True if agent_task_runs row was inserted
        cto_finding_id     str | None
        rollback_task_id   int | None — agent_tasks.id of follow-up task
        error              str | None — set on unexpected exception
    """
    draw_no = report.get("report_meta", {}).get("draw_no", "UNKNOWN")
    risk_level = report.get("risk_assessment", {}).get("risk_level", "LOW")
    action = report.get("action_recommendation", {}).get("action", "CONTINUE_H6")
    rollback_status = report.get("strategy", {}).get("rollback_status", "ACTIVE")

    _base = {
        "draw_no": draw_no,
        "risk_level": risk_level,
        "action": action,
        "duplicate": False,
        "tick_logged": False,
        "cto_finding_id": None,
        "rollback_task_id": None,
        "error": None,
    }

    # ── Guard: only alert on HIGH risk or dangerous actions ──────────────────
    if not should_alert(report):
        return {"alerted": False, **_base}

    # ── Hygiene guard: never alert or create tasks for test/synthetic draw_nos ─
    if is_test_draw_no(draw_no, game_type):
        logger.info(
            "[h6_alert_engine] suppressed alert for test/synthetic draw_no=%s (environment=test)",
            draw_no,
        )
        return {"alerted": False, **_base, "skipped_reason": "test_draw_no"}

    # ── Dedup guard ───────────────────────────────────────────────────────────
    if has_alert_for_draw(draw_no, game_type):
        return {"alerted": False, **_base, "duplicate": True}

    finding_id = f"h6_alert:{game_type}:{draw_no}"
    now = datetime.now(timezone.utc).isoformat()
    tick_logged = False
    rollback_task_id: Optional[int] = None

    try:
        odb = _orch_db()

        # ── Step 1: log tick ──────────────────────────────────────────────────
        odb.log_tick(
            runner="h6-alert",
            outcome="H6_DAILY_REPORT_ALERT",
            message=(
                f"draw_no={draw_no} game_type={game_type} "
                f"risk={risk_level} action={action} rollback_status={rollback_status}"
            ),
        )
        tick_logged = True

        # ── Step 2: CTO backlog visibility ────────────────────────────────────
        conn = _get_raw_conn()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO cto_backlog_items
                    (finding_id, cto_run_id, source, severity, urgency, category,
                     suggested_action, status, priority_score, priority_level,
                     created_at, updated_at)
                VALUES (?, ?, 'h6_daily_report', ?, 'HIGH', 'strategy_risk',
                        ?, 'pending', 80.0, 'P1', ?, ?)
                """,
                (finding_id, _CTO_RUN_ID, risk_level, action, now, now),
            )
            conn.commit()
        finally:
            conn.close()

        # ── Step 3: rollback follow-up task (if rollback_status != ACTIVE) ───
        if rollback_status != "ACTIVE":
            ts = int(datetime.now(timezone.utc).timestamp())
            slot_key = f"h6_rollback_followup_{game_type}_{draw_no}_{ts}"
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            dedupe_key = f"h6_rollback:{game_type}:{draw_no}"

            existing = odb.get_inflight_task_by_dedupe_key(dedupe_key)
            if not existing:
                rollback_task_id = odb.create_task(
                    slot_key=slot_key,
                    date_folder=today,
                    title=(
                        f"[H6-ALERT] Rollback Follow-up: {game_type} draw={draw_no}"
                    ),
                    slug=f"h6-rollback-followup-{draw_no}",
                    prompt_text=(
                        f"H6 daily report triggered an alert for {game_type} draw_no={draw_no}. "
                        f"risk_level={risk_level}, action={action}, rollback_status={rollback_status}. "
                        f"Review live_strategy_outcomes and active_strategy_state for this game_type. "
                        f"Confirm whether rollback is appropriate and execute if needed."
                    ),
                    prompt_file_path=None,
                    dedupe_key=dedupe_key,
                    worker_type="light",
                )

        return {
            "alerted": True,
            "draw_no": draw_no,
            "risk_level": risk_level,
            "action": action,
            "duplicate": False,
            "tick_logged": tick_logged,
            "cto_finding_id": finding_id,
            "rollback_task_id": rollback_task_id,
            "error": None,
        }

    except Exception as exc:
        logger.error("[h6_alert_engine] process_report_alerts error: %s", exc)
        return {"alerted": False, "error": str(exc), **_base}
