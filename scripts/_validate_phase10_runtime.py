#!/usr/bin/env python3
"""Phase 10 Task 7 — Runtime validate task #6169."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orchestrator import db
from orchestrator.task_completion_validator import validate_completion, QUALITY_EMPTY_ARTIFACT

task = db.get_task(6169)
if task is None:
    print("Task #6169 not found in DB")
    sys.exit(1)

print(f"task_id               : {task.get('id')}")
print(f"task_type             : {task.get('task_type')}")
print(f"status                : {task.get('status')}")
print(f"completed_text length : {len(task.get('completed_text') or '')}")
print(f"completed_file_path   : {task.get('completed_file_path')}")
print(f"changed_files_json    : {task.get('changed_files_json')}")
print(f"duration_seconds      : {task.get('duration_seconds')}")
print(f"completion_quality    : {task.get('completion_quality')}")

result = {
    "success": True,
    "completed_text": task.get("completed_text") or "",
    "completed_file_path": task.get("completed_file_path"),
    "changed_files": [],
    "execution_log": "",
    "duration_seconds": task.get("duration_seconds") or 0,
}

quality = validate_completion(task, result)
print(f"\nvalidate_completion => quality={quality['quality']}, valid={quality['valid']}")
print(f"reason  : {quality['reason']}")
print(f"checks  : {quality['checks']}")

assert quality["quality"] == QUALITY_EMPTY_ARTIFACT, (
    f"Expected COMPLETED_EMPTY_ARTIFACT for task #6169, got {quality['quality']}"
)
print("\n✅ RUNTIME VALIDATION: task #6169 correctly classified as COMPLETED_EMPTY_ARTIFACT")
print("✅ PHASE_10_COMPLETION_QUALITY_GUARD_VERIFIED (runtime)")
