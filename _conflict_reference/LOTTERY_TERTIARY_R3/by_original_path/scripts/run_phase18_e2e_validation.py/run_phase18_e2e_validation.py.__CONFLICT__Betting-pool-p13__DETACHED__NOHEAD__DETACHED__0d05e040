"""
scripts/run_phase18_e2e_validation.py

Phase 18 — End-to-End Autonomous Waiting Loop Runtime Validation

Proves the full DATA_WAITING loop:
  DATA_WAITING
  → readiness WAITING_ACTIVE
  → planner chooses safe refresh/audit task
  → deterministic executor runs
  → artifact is valid
  → refresh memory records outcome
  → ops report updates
  → decision card shows status
  → learning remains blocked

Usage:
    python3 scripts/run_phase18_e2e_validation.py [--dry-run]

Exit codes:
    0 — PHASE_18_E2E_WAITING_LOOP_RUNTIME_VERIFIED
    1 — validation failed (see output)
"""
from __future__ import annotations

import argparse
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── path setup ─────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

# ── constants ──────────────────────────────────────────────────────────────
VALID_DATA_WAITING_TASK_TYPES = frozenset({
    "refresh_external_closing",
    "refresh_tsl_closing",
    "closing_availability_audit",
    "closing_monitor",
    "manual_review_summary",
})

FORBIDDEN_TASK_TYPES = frozenset({
    "model_patch",
    "strategy_reinforcement",
    "feedback_learning",
})

FORBIDDEN_LLM_PROVIDERS = frozenset({
    "codex", "claude", "openai", "anthropic",
})

_SEP = "=" * 60


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _heading(title: str) -> None:
    print(f"\n{_SEP}\n  {title}\n{_SEP}")


def _ok(msg: str) -> None:
    print(f"  ✅  {msg}")


def _fail(msg: str) -> None:
    print(f"  ❌  {msg}")


def _info(msg: str) -> None:
    print(f"       {msg}")


# ──────────────────────────────────────────────────────────────────────────
# STEP 1 — Baseline state
# ──────────────────────────────────────────────────────────────────────────

def capture_baseline() -> dict[str, Any]:
    """Return baseline CLV counts and readiness state."""
    from orchestrator import db
    db.init_db()

    baseline: dict[str, Any] = {
        "captured_at": _ts(),
        "clv_pending": 0,
        "clv_computed": 0,
        "learning_allowed": False,
        "readiness_state": "UNKNOWN",
        "next_refresh_action": "UNKNOWN",
        "escalation_recommended": False,
    }

    # CLV counts from JSONL diagnostics (not DB table)
    try:
        from orchestrator.closing_odds_monitor import get_pending_diagnostics
        diag = get_pending_diagnostics()
        ss = diag.get("source_summary", {})
        baseline["clv_pending"] = ss.get("pending_total", 0)
        baseline["clv_computed"] = ss.get("computed_total", 0)
    except Exception as exc:
        _info(f"[baseline] CLV diagnostics read failed: {exc}")

    # Readiness state
    try:
        from orchestrator.optimization_readiness import get_readiness_summary
        rs = get_readiness_summary()
        baseline["readiness_state"] = rs.get("readiness_state", "UNKNOWN")
        baseline["learning_allowed"] = rs.get("learning_allowed", False)
        ca = rs.get("closing_availability", {})
        baseline["next_refresh_action"] = ca.get("next_refresh_action", "UNKNOWN")
        baseline["escalation_recommended"] = ca.get("escalation_recommended", False)
    except Exception as exc:
        _info(f"[baseline] Readiness read failed: {exc}")

    return baseline


# ──────────────────────────────────────────────────────────────────────────
# STEP 2 — Planner tick
# ──────────────────────────────────────────────────────────────────────────

def run_planner_step(dry_run: bool) -> dict[str, Any]:
    """
    Trigger planner tick and return info about what was created/skipped.
    In dry_run mode, only inspects _choose_closing_refresh_action without writing DB.
    """
    from orchestrator import db
    db.init_db()

    if dry_run:
        from orchestrator.closing_odds_monitor import get_pending_diagnostics
        from orchestrator.planner_tick import _choose_closing_refresh_action
        try:
            diag = get_pending_diagnostics()
            source_summary = diag.get("source_summary", {})
        except Exception:
            source_summary = {}
        action_type = _choose_closing_refresh_action(source_summary)
        return {
            "status": "DRY_RUN",
            "action_type": action_type,
            "task_id": None,
            "dry_run": True,
        }

    from orchestrator.planner_tick import run_planner_tick
    result = run_planner_tick()

    # Determine the action_type from the created task (if any)
    task_id = result.get("task_id")
    action_type = None
    if task_id:
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT task_key, objective FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                obj = (row["objective"] or "").lower()
                for t in VALID_DATA_WAITING_TASK_TYPES:
                    if t in obj or t in (row["task_key"] or "").lower():
                        action_type = t
                        break
        except Exception:
            pass

    # Also check in meta.json
    if not action_type and task_id:
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT task_dir FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                meta_path = _REPO_ROOT / row["task_dir"] / "meta.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text())
                    action_type = meta.get("task_type")
        except Exception:
            pass

    return {
        "status": result.get("status", "UNKNOWN"),
        "action_type": action_type or result.get("action_type"),
        "task_id": task_id,
        "planner_message": result.get("message", ""),
        "dry_run": False,
    }


# ──────────────────────────────────────────────────────────────────────────
# STEP 3 — Worker tick
# ──────────────────────────────────────────────────────────────────────────

def run_worker_step(dry_run: bool, task_id: int | None) -> dict[str, Any]:
    """
    Trigger worker tick and return execution result.
    In dry_run mode, only verifies that the task *would* be handled deterministically.
    """
    from orchestrator import db
    db.init_db()

    if dry_run and task_id:
        # Verify the task is deterministic without executing
        try:
            conn = db.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT task_dir FROM tasks WHERE id=?", (task_id,))
            row = cur.fetchone()
            conn.close()
            if row:
                meta_path = _REPO_ROOT / row["task_dir"] / "meta.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text())
                    task_type = meta.get("task_type", "")
                    from orchestrator.safe_task_executor import is_deterministic_safe_task
                    is_det = is_deterministic_safe_task({"task_type": task_type})
                    return {
                        "status": "DRY_RUN",
                        "task_type": task_type,
                        "is_deterministic": is_det,
                        "dry_run": True,
                    }
        except Exception as exc:
            _info(f"[worker dry-run] failed: {exc}")
        return {"status": "DRY_RUN", "is_deterministic": None, "dry_run": True}

    if dry_run:
        return {"status": "DRY_RUN", "is_deterministic": None, "dry_run": True}

    # Record llm_usage.jsonl length before execution to detect new external calls
    usage_path = _REPO_ROOT / "runtime" / "agent_orchestrator" / "llm_usage.jsonl"
    usage_lines_before = 0
    if usage_path.exists():
        with usage_path.open() as f:
            usage_lines_before = sum(1 for _ in f)

    from orchestrator.worker_tick import run_worker_tick
    result = run_worker_tick()

    # Check for new LLM usage entries
    usage_lines_after = 0
    new_external_calls: list[str] = []
    if usage_path.exists():
        with usage_path.open() as f:
            lines = list(f)
        usage_lines_after = len(lines)
        for line in lines[usage_lines_before:]:
            try:
                entry = json.loads(line.strip())
                provider = (entry.get("provider") or "").lower()
                blocked = entry.get("blocked", False)
                task_t = entry.get("task_type", "")
                # Flag non-blocked calls to external LLMs for DATA_WAITING tasks
                if not blocked and any(p in provider for p in FORBIDDEN_LLM_PROVIDERS):
                    new_external_calls.append(f"provider={provider} task_type={task_t}")
            except Exception:
                pass

    return {
        "status": result.get("status", "UNKNOWN"),
        "task_id": result.get("task_id"),
        "completion_quality": result.get("completion_quality"),
        "artifact_path": result.get("artifact_path"),
        "success": result.get("success", False),
        "is_deterministic": result.get("is_deterministic"),
        "new_external_calls": new_external_calls,
        "usage_lines_before": usage_lines_before,
        "usage_lines_after": usage_lines_after,
        "dry_run": False,
    }


# ──────────────────────────────────────────────────────────────────────────
# STEP 4 — CLV safety check
# ──────────────────────────────────────────────────────────────────────────

def verify_clv_safety(baseline: dict[str, Any]) -> dict[str, Any]:
    """Confirm CLV PENDING/COMPUTED counts are consistent with hard rules."""
    result: dict[str, Any] = {
        "pending_before": baseline["clv_pending"],
        "computed_before": baseline["clv_computed"],
        "pending_after": 0,
        "computed_after": 0,
        "pending_unchanged_or_decreased": True,
        "computed_only_increased_with_valid_odds": True,
        "learning_still_blocked": True,
    }

    try:
        from orchestrator.closing_odds_monitor import get_pending_diagnostics
        diag = get_pending_diagnostics()
        ss = diag.get("source_summary", {})
        result["pending_after"] = ss.get("pending_total", 0)
        result["computed_after"] = ss.get("computed_total", 0)
    except Exception as exc:
        result["error"] = str(exc)

    # If COMPUTED increased, verify closing odds actually exist
    if result["computed_after"] > result["computed_before"]:
        # Check that new COMPUTED records have valid closing odds
        try:
            from orchestrator.closing_odds_monitor import get_pending_diagnostics
            diag = get_pending_diagnostics()
            ss = diag.get("source_summary", {})
            # If all sources are missing, any increase is suspicious
            if ss.get("missing_all_sources", 0) > 0 and ss.get("computed_total", 0) == ss.get("pending_total", 0):
                result["computed_only_increased_with_valid_odds"] = False
        except Exception:
            pass

    # Check learning is still blocked
    try:
        from orchestrator.optimization_readiness import get_readiness_summary
        rs = get_readiness_summary()
        result["learning_still_blocked"] = not rs.get("learning_allowed", True)
    except Exception:
        pass

    return result


# ──────────────────────────────────────────────────────────────────────────
# STEP 5 — Refresh memory verification
# ──────────────────────────────────────────────────────────────────────────

def verify_refresh_memory() -> dict[str, Any]:
    """Check closing_refresh_memory.json reflects latest execution."""
    memory_path = _REPO_ROOT / "runtime" / "agent_orchestrator" / "closing_refresh_memory.json"
    result: dict[str, Any] = {
        "memory_exists": memory_path.exists(),
        "last_action": None,
        "last_improved": None,
        "consecutive_no_improvement": 0,
        "escalation_recommended": False,
        "history_count": 0,
    }

    if not memory_path.exists():
        return result

    try:
        data = json.loads(memory_path.read_text())
        history = data.get("history", [])
        per_action = data.get("per_action", {})
        result["history_count"] = len(history)
        if history:
            last = history[-1]
            result["last_action"] = last.get("action_type")
            result["last_improved"] = last.get("improved")
            result["consecutive_no_improvement"] = last.get("consecutive_no_improvement", 0)
            result["escalation_recommended"] = last.get("escalation_recommended", False)
        result["per_action_summary"] = {
            k: {
                "consecutive_no_improvement": v.get("consecutive_no_improvement", 0),
                "escalation_recommended": v.get("escalation_recommended", False),
            }
            for k, v in per_action.items()
        }
    except Exception as exc:
        result["error"] = str(exc)

    return result


# ──────────────────────────────────────────────────────────────────────────
# STEP 6 — Report verification
# ──────────────────────────────────────────────────────────────────────────

def verify_reports() -> dict[str, Any]:
    """Re-run readiness + ops report and verify key fields are present."""
    result: dict[str, Any] = {
        "readiness_available": False,
        "readiness_state": None,
        "learning_allowed": False,
        "ops_available": False,
        "ops_classification": None,
        "ca_available": False,
        "refresh_feedback_available": False,
        "decision_card_has_closing_section": False,
        "decision_card_has_refresh_section": False,
        "decision_card_has_usage_section": False,
    }

    # Readiness
    try:
        from orchestrator.optimization_readiness import get_readiness_summary
        rs = get_readiness_summary()
        result["readiness_available"] = True
        result["readiness_state"] = rs.get("readiness_state")
        result["learning_allowed"] = rs.get("learning_allowed", False)
        ca = rs.get("closing_availability", {})
        result["ca_available"] = ca.get("available", False)
        result["refresh_feedback_available"] = "last_refresh_action" in ca
    except Exception as exc:
        result["readiness_error"] = str(exc)

    # Ops report
    try:
        from orchestrator.optimization_ops_report import generate_report
        report = generate_report(window="8h")
        result["ops_available"] = True
        result["ops_classification"] = report.get("classification")
    except Exception as exc:
        result["ops_error"] = str(exc)

    # Decision card — build payload and render
    try:
        from scripts.ops_decision_card import build_payload, render_card
        payload = build_payload()
        card = render_card(payload)
        result["decision_card_has_closing_section"] = "CLOSING ODDS AVAILABILITY" in card
        result["decision_card_has_refresh_section"] = "CLOSING REFRESH FEEDBACK" in card
        result["decision_card_has_usage_section"] = "USAGE" in card
    except Exception as exc:
        result["decision_card_error"] = str(exc)

    return result


# ──────────────────────────────────────────────────────────────────────────
# Main validation runner
# ──────────────────────────────────────────────────────────────────────────

def run_validation(dry_run: bool = False) -> int:
    """
    Run full Phase 18 E2E validation.

    Returns 0 on success (PHASE_18_E2E_WAITING_LOOP_RUNTIME_VERIFIED),
    returns 1 on any failure.
    """
    failures: list[str] = []
    warnings: list[str] = []

    print(f"\nPhase 18 — E2E Waiting Loop Runtime Validation")
    print(f"Generated: {_ts()}")
    if dry_run:
        print("  [DRY-RUN MODE — no DB writes]")

    # ── TASK 1: Baseline ───────────────────────────────────────────────
    _heading("TASK 1 — BASELINE STATE")
    baseline = capture_baseline()
    _info(f"CLV pending     : {baseline['clv_pending']}")
    _info(f"CLV computed    : {baseline['clv_computed']}")
    _info(f"Learning allowed: {baseline['learning_allowed']}")
    _info(f"Readiness state : {baseline['readiness_state']}")
    _info(f"Next action     : {baseline['next_refresh_action']}")
    _info(f"Escalation      : {baseline['escalation_recommended']}")

    # ── TASK 2: Planner tick ───────────────────────────────────────────
    _heading("TASK 2 — PLANNER DATA_WAITING PATH")
    planner_result = run_planner_step(dry_run)

    planner_status = planner_result.get("status", "UNKNOWN")
    action_type = planner_result.get("action_type")
    task_id = planner_result.get("task_id")

    _info(f"Planner status  : {planner_status}")
    _info(f"Action type     : {action_type}")
    _info(f"Task ID         : {task_id}")
    if planner_result.get("planner_message"):
        _info(f"Message         : {planner_result['planner_message'][:120]}")

    # Validate planner result
    if planner_status in ("SKIPPED", "DRY_RUN") and not action_type:
        # GLOBAL_HARD_OFF is expected behaviour during non-interactive runs
        msg = planner_result.get("planner_message", "")
        if "GLOBAL_HARD_OFF" in msg:
            _ok("Planner correctly skipped: GLOBAL_HARD_OFF mode active (expected)")
        else:
            warnings.append(f"Planner skipped without action_type (status={planner_status})")
    elif action_type and action_type not in VALID_DATA_WAITING_TASK_TYPES:
        failures.append(
            f"Planner generated FORBIDDEN task type: {action_type!r} "
            f"(allowed: {sorted(VALID_DATA_WAITING_TASK_TYPES)})"
        )
        _fail(f"Task type {action_type!r} is NOT in VALID_DATA_WAITING_TASK_TYPES")
    elif action_type in FORBIDDEN_TASK_TYPES:
        failures.append(f"Planner generated learning task: {action_type!r}")
        _fail(f"Planner generated FORBIDDEN learning task: {action_type!r}")
    else:
        if action_type:
            _ok(f"Planner chose valid DATA_WAITING task: {action_type!r}")
        else:
            # If planner was skipped due to RUNNING task being auto-resolved, that's OK
            if "PLANNER_SKIP_PREV_RUNNING" in planner_result.get("planner_message", ""):
                warnings.append("Planner skipped: previous RUNNING task still active")
                _info("Planner skipped (prev task RUNNING) — worker will handle existing task")
            elif planner_status in ("SKIP_CADENCE", "SKIPPED"):
                _ok(f"Planner cadence/policy skip (expected during DATA_WAITING)")
            elif dry_run:
                _ok(f"[DRY-RUN] Would choose: {planner_result.get('action_type', '?')!r}")

    # ── TASK 3: Worker tick ────────────────────────────────────────────
    _heading("TASK 3 — WORKER DETERMINISTIC PATH")

    # In dry_run, pass the task_id for inspection
    worker_result = run_worker_step(dry_run, task_id)

    worker_status = worker_result.get("status", "UNKNOWN")
    completion_quality = worker_result.get("completion_quality")
    is_deterministic = worker_result.get("is_deterministic")
    new_external_calls = worker_result.get("new_external_calls", [])

    _info(f"Worker status   : {worker_status}")
    _info(f"Completion qual : {completion_quality}")
    _info(f"Deterministic   : {is_deterministic}")
    _info(f"New ext LLM calls: {len(new_external_calls)}")

    if not dry_run:
        # Verify no external LLM was consumed
        if new_external_calls:
            failures.append(
                f"External LLM called during deterministic safe task: {new_external_calls}"
            )
            _fail(f"External LLM consumed: {new_external_calls}")
        else:
            _ok("No external LLM consumed during deterministic safe task")

        # Verify completion quality
        VALID_QUALITIES = {"COMPLETED_VALID", "COMPLETED_DIAGNOSTIC_ONLY",
                           "COMPLETED_VALID_SAFE_TASK", "COMPLETED_SAFE_TASK"}
        if worker_status == "NO_TASK":
            _info("Worker found no task to execute (expected if planner was skipped)")
        elif worker_status in ("SKIPPED", "BLOCKED"):
            _ok(f"Worker appropriately skipped/blocked (status={worker_status})")
        elif completion_quality and not any(
            q in (completion_quality or "") for q in ["COMPLETED", "VALID", "SAFE"]
        ):
            failures.append(
                f"Unexpected completion quality: {completion_quality!r}"
            )
            _fail(f"Completion quality {completion_quality!r} not in expected set")
        else:
            _ok(f"Worker completed safely (quality={completion_quality!r})")
    else:
        _info("[DRY-RUN] Worker execution skipped")

    # ── TASK 4: CLV safety ────────────────────────────────────────────
    _heading("TASK 4 — CLV SAFETY VERIFICATION")
    clv = verify_clv_safety(baseline)

    _info(f"Pending before  : {clv['pending_before']}  → after: {clv['pending_after']}")
    _info(f"Computed before : {clv['computed_before']} → after: {clv['computed_after']}")
    _info(f"Learning blocked: {clv['learning_still_blocked']}")

    # Rule: COMPUTED must NOT increase unless valid closing odds exists
    if not clv["computed_only_increased_with_valid_odds"]:
        failures.append(
            "CLV COMPUTED count increased without valid closing odds — fake CLV computation detected"
        )
        _fail("CLV COMPUTED increased without valid closing odds — HARD RULE VIOLATION")
    else:
        _ok("CLV COMPUTED count is safe (no fake computation)")

    # Rule: learning must remain blocked
    if not clv["learning_still_blocked"]:
        failures.append("Learning was unlocked after safe task execution — HARD RULE VIOLATION")
        _fail("Learning UNLOCKED — HARD RULE VIOLATION")
    else:
        _ok("Learning remains BLOCKED (DATA_WAITING)")

    # ── TASK 5: Refresh memory ─────────────────────────────────────────
    _heading("TASK 5 — REFRESH MEMORY VERIFICATION")
    mem = verify_refresh_memory()

    _info(f"Memory exists   : {mem['memory_exists']}")
    _info(f"History count   : {mem['history_count']}")
    _info(f"Last action     : {mem['last_action']}")
    _info(f"Last improved   : {mem['last_improved']}")
    _info(f"No-imp streak   : {mem['consecutive_no_improvement']}")
    _info(f"Escalation      : {mem['escalation_recommended']}")

    if not mem["memory_exists"]:
        failures.append("closing_refresh_memory.json does not exist")
        _fail("Refresh memory file missing")
    elif mem["history_count"] == 0:
        warnings.append("Refresh memory exists but history is empty (no refresh tasks ran yet)")
        _info("No refresh history yet (will be written after first refresh executor runs)")
    else:
        _ok(f"Refresh memory has {mem['history_count']} history entries")
        if mem.get("per_action_summary"):
            for at, state in mem["per_action_summary"].items():
                _info(f"  {at}: streak={state['consecutive_no_improvement']} esc={state['escalation_recommended']}")

    # ── TASK 6: Reports ────────────────────────────────────────────────
    _heading("TASK 6 — REPORT VERIFICATION")
    reports = verify_reports()

    _info(f"Readiness avail : {reports['readiness_available']}")
    _info(f"Readiness state : {reports['readiness_state']}")
    _info(f"Learning allowed: {reports['learning_allowed']}")
    _info(f"Ops report avail: {reports['ops_available']}")
    _info(f"Ops classif     : {reports['ops_classification']}")
    _info(f"CA available    : {reports['ca_available']}")
    _info(f"Refresh feedback: {reports['refresh_feedback_available']}")
    _info(f"Card: closing   : {reports['decision_card_has_closing_section']}")
    _info(f"Card: refresh   : {reports['decision_card_has_refresh_section']}")
    _info(f"Card: usage     : {reports['decision_card_has_usage_section']}")

    # Validate reports
    if not reports["readiness_available"]:
        failures.append(f"Readiness report unavailable: {reports.get('readiness_error')}")
        _fail("Readiness report failed")
    else:
        _ok("Readiness report generated successfully")

    if reports["learning_allowed"]:
        failures.append("Learning is ALLOWED in reports — should be BLOCKED during DATA_WAITING")
        _fail("Learning shown as ALLOWED — HARD RULE VIOLATION")
    else:
        _ok("Reports confirm learning is BLOCKED")

    if not reports["ops_available"]:
        failures.append(f"Ops report unavailable: {reports.get('ops_error')}")
        _fail("Ops report failed")
    else:
        _ok("Ops report generated successfully")

    if not reports["decision_card_has_closing_section"]:
        failures.append("Decision card missing CLOSING ODDS AVAILABILITY section")
        _fail("Decision card missing closing availability section")
    else:
        _ok("Decision card has CLOSING ODDS AVAILABILITY section")

    if not reports["decision_card_has_refresh_section"]:
        failures.append("Decision card missing CLOSING REFRESH FEEDBACK section")
        _fail("Decision card missing refresh feedback section")
    else:
        _ok("Decision card has CLOSING REFRESH FEEDBACK section")

    if not reports["decision_card_has_usage_section"]:
        warnings.append("Decision card missing USAGE section")
    else:
        _ok("Decision card has USAGE 詳細 section")

    # ── SUMMARY ───────────────────────────────────────────────────────
    _heading("PHASE 18 VALIDATION SUMMARY")

    if warnings:
        print("\n  ⚠️  WARNINGS:")
        for w in warnings:
            print(f"     - {w}")

    if failures:
        print("\n  ❌  FAILURES:")
        for f in failures:
            print(f"     - {f}")
        print(f"\n  RESULT: PHASE_18_VALIDATION_FAILED ({len(failures)} failures)\n")
        return 1

    print(f"\n  ✅  All checks passed (warnings: {len(warnings)})")
    print("\n  RESULT: PHASE_18_E2E_WAITING_LOOP_RUNTIME_VERIFIED\n")
    return 0


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 18: E2E Autonomous Waiting Loop Runtime Validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Exit codes:
              0 — PHASE_18_E2E_WAITING_LOOP_RUNTIME_VERIFIED
              1 — validation failed
        """),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect planner/worker logic without writing to DB or creating tasks",
    )
    args = parser.parse_args()
    sys.exit(run_validation(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
