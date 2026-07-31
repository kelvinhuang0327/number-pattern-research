#!/usr/bin/env python3
"""
Phase 11 × Phase 9 整合驗證腳本。

建立一個新的 closing_monitor 任務，透過 Phase 11 deterministic executor 執行，
更新 DB，然後重新產出 ops report，確認 effective_completed_tasks >= 1。

Run: python3 scripts/_validate_phase11_ops_integration.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import db
from orchestrator.safe_task_executor import execute_safe_task
from orchestrator.task_completion_validator import (
    QUALITY_EFFECTIVE_STATES,
    validate_completion,
)
from orchestrator.optimization_ops_report import generate_report

# ── 1. Build synthetic task row (not QUEUED — bypass worker race) ─────────────
NOW = datetime.now(timezone.utc)
DATE_FOLDER = NOW.strftime("%Y%m%d")
SLOT_KEY = f"phase11-verify-{NOW.strftime('%H%M%S')}"
DEDUPE_KEY = f"phase11_verify_closing_monitor:{DATE_FOLDER}"

print("=== PHASE_11 × OPS_REPORT INTEGRATION VERIFICATION ===\n")

# Check if this dedupe key already exists — prevent double-insert
all_tasks = db.list_tasks(limit=200)
existing = [t for t in all_tasks if t.get("dedupe_key") == DEDUPE_KEY]
if existing:
    task_row = existing[0]
    task_id = task_row["id"]
    print(f"[재사용] Re-using existing task #{task_id} (dedupe_key={DEDUPE_KEY})")
else:
    task_id = db.create_task(
        slot_key=SLOT_KEY,
        date_folder=DATE_FOLDER,
        title="[Phase11 Verify] Closing Monitor Deterministic",
        slug=SLOT_KEY,
        status="QUEUED",
        task_type="closing_monitor",
        worker_type="light",
        dedupe_key=DEDUPE_KEY,
        regime_state="data_waiting",
        epoch_id=0,
        prompt_text="Phase 11 integration verification: deterministic closing monitor.",
        focus_keys="closing_monitor,clv,phase11_verify",
    )
    print(f"[DB] Created task #{task_id} (slot_key={SLOT_KEY})")

task = db.get_task(task_id)

# ── 2. Execute through Phase 11 deterministic executor (real, no mock) ────────
print("\n[Phase11] Running execute_safe_task (real closing_odds_monitor)...")
db.update_task(task_id, status="RUNNING", started_at=NOW.isoformat())

import time
t0 = time.monotonic()
try:
    execution_result = execute_safe_task(task)
    duration = round(time.monotonic() - t0, 2)
    execution_result.setdefault("duration_seconds", duration)
except Exception as exc:
    db.update_task(task_id, status="FAILED", error_message=str(exc))
    print(f"[ERROR] execute_safe_task raised: {exc}")
    sys.exit(1)

# ── 3. Validate completion quality ────────────────────────────────────────────
quality_result = validate_completion(task, execution_result)
quality = quality_result["quality"]
completed_text = execution_result.get("completed_text", "")
completed_file_path = execution_result.get("completed_file_path")

print(f"  success          : {execution_result['success']}")
print(f"  completed_text   : {len(completed_text)} chars")
print(f"  quality          : {quality}")
print(f"  is effective     : {quality in QUALITY_EFFECTIVE_STATES}")

# ── 4. Persist result to DB ──────────────────────────────────────────────────
import json
changed_files = execution_result.get("changed_files") or []
if completed_file_path and completed_file_path not in changed_files:
    changed_files.append(completed_file_path)

completed_at = datetime.now(timezone.utc).isoformat()
db.update_task(
    task_id,
    status="COMPLETED",
    completed_text=completed_text,
    completed_file_path=completed_file_path,
    changed_files_json=json.dumps(changed_files),
    completion_quality=quality,
    completed_at=completed_at,
    duration_seconds=execution_result.get("duration_seconds"),
    error_message=execution_result.get("error_message") or None,
)
print(f"\n[DB] Task #{task_id} updated → COMPLETED / quality={quality}")

# ── 5. Re-run ops report (8h window) ─────────────────────────────────────────
print("\n[OpsReport] Re-generating report (8h window)...")
report = generate_report(window="8h")
print(f"  classification          : {report['classification']}")
print(f"  tasks_completed         : {report['tasks_completed']}")
print(f"  completed_valid_tasks   : {report['completed_valid_tasks']}")
print(f"  completed_diagnostic_only:{report['completed_diagnostic_only']}")
print(f"  completed_empty_artifact: {report['completed_empty_artifact']}")
print(f"  completed_noop          : {report['completed_noop']}")
print(f"  effective_completed     : {report['effective_completed_tasks']}")
print(f"  clv_pending             : {report['clv_pending']}")
print(f"  clv_computed            : {report['clv_computed']}")

# ── 6. Assertions ─────────────────────────────────────────────────────────────
print()
ok = True

if quality not in QUALITY_EFFECTIVE_STATES:
    print(f"[FAIL] quality={quality} not in QUALITY_EFFECTIVE_STATES")
    ok = False
else:
    print(f"[OK] quality {quality} is effective")

if report["effective_completed_tasks"] < 1:
    print(f"[FAIL] effective_completed_tasks={report['effective_completed_tasks']} — expected >= 1")
    ok = False
else:
    print(f"[OK] effective_completed_tasks={report['effective_completed_tasks']} >= 1")

# Empty artifact count must equal only the pre-Phase-11 task (6169)
if report["completed_empty_artifact"] > 1:
    print(f"[WARN] completed_empty_artifact={report['completed_empty_artifact']} > 1 (unexpected extra empties)")
else:
    print(f"[OK] completed_empty_artifact={report['completed_empty_artifact']} (pre-Phase11 legacy only)")

# CLV state: PENDING must not decrease unless real odds arrived
if report["clv_pending"] < 14:
    print(f"[WARN] clv_pending dropped below 14 ({report['clv_pending']}) — investigate!")
else:
    print(f"[OK] clv_pending={report['clv_pending']} — no fake upgrades")

# Deterministic task must not have marked any CLV as COMPUTED spuriously
if execution_result.get("upgraded_count", 0) > 0:
    print(f"[WARN] upgraded_count={execution_result['upgraded_count']} — verify valid closing odds")
else:
    print(f"[OK] upgraded_count=0 — no CLV state changes (correct: no valid closing odds)")

print()
if ok:
    print("=== VERDICT: PHASE_11_OPS_REPORT_EFFECTIVENESS_CONFIRMED ===")
else:
    print("=== VERDICT: PHASE_11_OPS_REPORT_EFFECTIVENESS_PARTIAL ===")
    sys.exit(1)
