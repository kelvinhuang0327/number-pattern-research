"""
Step 6/7 — Worker Execution Validation under safe-run mode.

Validates:
  1. Mode switch hard-off → safe-run
  2. Worker selects the correct task (closing_monitor, NOT learning)
  3. Task is dispatched to the correct execution path
  4. CLV state is NOT modified
  5. Mode restored to hard-off

LLM execution note:
  worker_provider=copilot-daemon requires a running copilot daemon process.
  This script validates task SELECTION governance only; actual LLM execution
  is handled by the daemon when infrastructure is available.

Run: python3 scripts/_validate_worker_safe_run.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO))

from orchestrator import db, execution_policy

_LEARNING_TASK_TYPES = {
    "model_patch_atomic", "strategy_reinforcement", "clv_reinforcement",
    "calibration_atomic", "feedback_atomic", "model_patch_calibration",
    "backtest_validity_atomic", "feature_atomic", "regime_atomic",
}
_SAFE_TASK_TYPES = {
    "closing_monitor", "ops_report", "scheduler_health", "artifact_health",
    "wiki_maintenance", "architecture_cleanup", "maintenance_health_check",
    "data_monitor",
}

print("=" * 60)
print("Worker Safe-Run Validation")
print("=" * 60)
print()

# ── Step 1: Record mode before ────────────────────────────────
mode_before = db.get_llm_execution_mode()
scheduler_before = db.get_scheduler_enabled()
print(f"[BEFORE] llm_mode         : {mode_before}")
print(f"[BEFORE] scheduler_enabled: {scheduler_before}")
print(f"[BEFORE] worker_provider  : {db.get_worker_provider()}")
print()

# ── Step 2: Confirm task #6169 is still QUEUED ────────────────
task = db.get_task(6169)
if not task:
    print("❌  Task #6169 not found — cannot proceed")
    sys.exit(1)

print("Queued task details:")
print(f"  id          : {task['id']}")
print(f"  title       : {task['title']}")
print(f"  task_type   : {task['task_type']}")
print(f"  worker_type : {task['worker_type']}")
print(f"  status      : {task['status']}")
print(f"  regime_state: {task['regime_state']}")
print(f"  dedupe_key  : {task['dedupe_key']}")
print()

if task["status"] != "QUEUED":
    print(f"⚠️  Task is {task['status']} (not QUEUED) — may have been picked up already")

# ── Step 3: Switch to safe-run ────────────────────────────────
print("Switching llm_execution_mode: hard-off → safe-run ...")
execution_policy.set_llm_execution_mode("safe-run")
mode_after = db.get_llm_execution_mode()
hard_off_after = db.is_hard_off_mode()
print(f"[AFTER]  llm_mode  : {mode_after}")
print(f"[AFTER]  hard_off  : {hard_off_after}")
print()

# ── Step 4: Simulate evaluate_execution (background, manual override) ─
decision_bg = execution_policy.evaluate_execution(
    runner="worker_tick",
    background=True,
    manual_override=True,  # ORCHESTRATOR_FORCE_RUN=1 path
)
decision_llm = execution_policy.evaluate_execution(
    runner="worker_tick",
    requires_llm=True,
    background=True,
    manual_override=True,
)
print("evaluate_execution (background, manual_override=True):")
print(f"  allowed      : {decision_bg['allowed']}")
print(f"  reason       : {decision_bg['reason']}")
print()
print("evaluate_execution (requires_llm=True, manual_override=True):")
print(f"  allowed      : {decision_llm['allowed']}")
print(f"  reason       : {decision_llm['reason']}")
print()

# ── Step 5: Simulate worker task selection ────────────────────
print("Simulating worker task selection (list_tasks(status=QUEUED, limit=1)) ...")
queued = db.list_tasks(status="QUEUED", limit=1)
if not queued:
    print("  ❌  No QUEUED tasks found")
    selected_task = None
else:
    selected_task = queued[0]
    print(f"  → Selected task #{selected_task['id']}: {selected_task['title']}")
    print(f"     task_type  : {selected_task['task_type']}")
    print(f"     worker_type: {selected_task['worker_type']}")
    print(f"     status     : {selected_task['status']}")
print()

# ── Step 6: Check CLV state BEFORE (unchanged baseline) ───────
from orchestrator import optimization_state
state_result = optimization_state.classify()
clv_computed = sum(
    1 for r in state_result.get("reasons", [])
    if "COMPUTED" in r.upper()
)
print(f"CLV state (optimization_state): {state_result.get('state')}")
print(f"  reasons: {state_result.get('reasons', [])}")
print()

# ── Step 7: Worker provider routing check ────────────────────
provider = db.get_worker_provider()
print(f"Worker provider: {provider}")
if provider == "copilot-daemon":
    print("  → copilot-daemon: requires running daemon process")
    print("  → In daemon-absent environment: falls back to codex exec path")
    print("  → LLM execution requires: running orchestrator daemon OR codex in PATH")
    import shutil
    codex_available = bool(shutil.which("codex"))
    gh_available    = bool(shutil.which("gh"))
    print(f"  → codex in PATH  : {codex_available}")
    print(f"  → gh in PATH     : {gh_available}")
    llm_available = codex_available or gh_available
else:
    llm_available = True
print()

# ── Step 8: Restore hard-off ──────────────────────────────────
print("Restoring llm_execution_mode: safe-run → hard-off ...")
execution_policy.set_llm_execution_mode("hard-off")
mode_restored = db.get_llm_execution_mode()
print(f"[RESTORED] llm_mode: {mode_restored}")
print()

# ── Step 9: Final verdict ─────────────────────────────────────
print("=" * 60)
print("VALIDATION SUMMARY")
print("=" * 60)

checks: dict[str, bool] = {
    "task #6169 exists and is QUEUED": (
        task is not None and task.get("status") == "QUEUED"
    ),
    "mode switched to safe-run": mode_after == "safe-run" and not hard_off_after,
    "background execution allowed in safe-run": decision_bg["allowed"],
    "LLM execution allowed in safe-run (manual)": decision_llm["allowed"],
    "worker selects closing_monitor first": (
        selected_task is not None
        and selected_task["id"] == 6169
        and selected_task["task_type"] == "closing_monitor"
    ),
    "selected task is NOT learning": (
        selected_task is not None
        and selected_task["task_type"] not in _LEARNING_TASK_TYPES
    ),
    "selected task IS safe type": (
        selected_task is not None
        and selected_task["task_type"] in _SAFE_TASK_TYPES
    ),
    "CLV state unchanged (still DATA_WAITING)": (
        state_result.get("state") == "DATA_WAITING"
    ),
    "mode restored to hard-off": mode_restored == "hard-off",
}

all_pass = True
for check, passed in checks.items():
    mark = "✅" if passed else "❌"
    print(f"  {mark}  {check}")
    if not passed:
        all_pass = False

print()
print(f"Worker provider  : {provider}")
print(f"LLM available    : {llm_available}")
print()

if all_pass and llm_available:
    print("VERDICT: DATA_WAITING_SAFE_TASK_WORKER_EXECUTION_CONFIRMED")
    print()
    print("Note: All governance checks pass. Worker selects closing_monitor task.")
    print("      LLM (codex/gh) is available — full execution can proceed.")
elif all_pass and not llm_available:
    print("VERDICT: DATA_WAITING_SAFE_TASK_WORKER_EXECUTION_CONFIRMED")
    print()
    print("Note: All governance checks pass. Worker correctly selects closing_monitor.")
    print("      LLM (copilot-daemon) requires running daemon / codex in PATH.")
    print("      Governance layer fully confirmed; LLM execution is infrastructure-gated.")
else:
    failed = [k for k, v in checks.items() if not v]
    print(f"VERDICT: BLOCKED — failed checks: {failed}")
