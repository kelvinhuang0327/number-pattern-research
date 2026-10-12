"""
Runtime validation script for DATA_WAITING safe workflow.
Run: python3 scripts/_validate_dw_runtime.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from orchestrator import db, planner_tick

print("=" * 60)
print("DATA_WAITING Safe Workflow — Runtime Validation")
print("=" * 60)
print()

# ── Show runtime mode ─────────────────────────────────────────
mode = db.get_llm_execution_mode()
print(f"llm_execution_mode : {mode}")
print(f"is_hard_off_mode   : {db.is_hard_off_mode()}")
print()

# ── Confirm optimization_state ────────────────────────────────
from orchestrator import optimization_state
state_result = optimization_state.classify()
print(f"optimization_state : {state_result.get('state')}")
print(f"allowed_families   : {state_result.get('allowed_task_families', [])}")
print(f"blocked_families   : {state_result.get('blocked_task_families', [])}")
print(f"reasons            : {state_result.get('reasons', [])}")
print()

# ── Invoke _attempt_data_waiting_safe_task directly ───────────
print("Invoking _attempt_data_waiting_safe_task() ...")
opt_state_result = {
    "state": state_result.get("state", "DATA_WAITING"),
    "reasons": state_result.get("reasons", []),
}
result = planner_tick._attempt_data_waiting_safe_task(
    request_id="manual-validation-001",
    start_time=datetime.now(timezone.utc),
    opt_state_result=opt_state_result,
)
print(f"Result status      : {result['status']}")
print(f"Result task_id     : {result.get('task_id')}")
print(f"Result dedupe_key  : {result.get('dedupe_key')}")
print()

# ── Show task details ─────────────────────────────────────────
task_id = result.get("task_id")
if task_id:
    task = db.get_task(task_id)
    if task:
        print("Generated task details:")
        print(f"  title          : {task.get('title')}")
        print(f"  analysis_family: {task.get('analysis_family')}")
        print(f"  worker_type    : {task.get('worker_type')}")
        print(f"  task_type      : {task.get('task_type')}")
        print(f"  status         : {task.get('status')}")
        print(f"  dedupe_key     : {task.get('dedupe_key')}")
        print()

        # DB has no analysis_family column — use task_type as the family indicator
        task_type = task.get("task_type", "")
        _safe_task_types = {
            "closing_monitor", "ops_report", "scheduler_health", "artifact_health",
            "wiki_maintenance", "architecture_cleanup", "maintenance", "data_monitor",
        }
        _learning_task_types = {
            "model_patch_atomic", "strategy_reinforcement", "clv_reinforcement",
            "calibration_atomic", "feedback_atomic",
        }
        is_safe = task_type in _safe_task_types
        is_learning = task_type in _learning_task_types
        print(f"  task_type      : {task_type}")
        print(f"  is_safe_family : {is_safe}")
        print(f"  is_learning    : {is_learning} (must be False)")
        print()

# ── Worker tick: not possible with HARD_OFF but verify task is QUEUED ──
print("Worker verification (HARD_OFF mode — skipping live LLM call):")
print("  Task is QUEUED and will be picked up when llm_execution_mode is restored.")
print("  Confirming task in DB is QUEUED (not COMPLETED/FAILED/RUNNING) ...")
if task_id:
    task = db.get_task(task_id)
    task_status = task.get("status") if task else "NOT_FOUND"
    print(f"  task status: {task_status}")
    worker_ok = task_status in ("QUEUED",)
else:
    worker_ok = False

# ── Final verdict ─────────────────────────────────────────────
print()
print("=" * 60)
print("VALIDATION SUMMARY")
print("=" * 60)

checks = {
    "opt_state=DATA_WAITING": state_result.get("state") == "DATA_WAITING",
    "learning families blocked": any(
        f in state_result.get("blocked_task_families", [])
        for f in ["model-patch-atomic", "strategy-reinforcement"]
    ),
    "safe families allowed": any(
        f in state_result.get("allowed_task_families", [])
        for f in ["closing-monitor", "ops-report"]
    ),
    "safe task created/exists": result["status"] in ("CREATED", "SKIP_DAILY_CAP"),
    "task family is safe": (
        task_id
        and db.get_task(task_id) is not None
        and db.get_task(task_id).get("task_type") in (
            "closing_monitor", "ops_report", "scheduler_health",
            "artifact_health", "wiki_maintenance", "maintenance",
        )
    ),
    "task family NOT learning": (
        task_id
        and db.get_task(task_id) is not None
        and db.get_task(task_id).get("task_type") not in (
            "model_patch_atomic", "strategy_reinforcement", "clv_reinforcement",
        )
    ),
    "task queued for worker": worker_ok,
}

all_pass = True
for check, passed in checks.items():
    mark = "✅" if passed else "❌"
    print(f"  {mark}  {check}")
    if not passed:
        all_pass = False

print()
if all_pass:
    print("VERDICT: DATA_WAITING_SAFE_WORKFLOW_RUNTIME_CONFIRMED")
else:
    failed = [k for k, v in checks.items() if not v]
    print(f"VERDICT: PARTIAL — failed checks: {failed}")
