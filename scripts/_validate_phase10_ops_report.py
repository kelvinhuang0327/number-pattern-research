#!/usr/bin/env python3
"""Phase 10 ops report integration validation — Steps 3-6."""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from orchestrator import db
from orchestrator.task_completion_validator import validate_completion, QUALITY_EMPTY_ARTIFACT

# ── Step 4: task #6169 classification ────────────────────────────────────
task = db.get_task(6169)
result = {
    "success": True,
    "completed_text": task.get("completed_text") or "",
    "completed_file_path": task.get("completed_file_path"),
    "changed_files": [],
    "execution_log": "",
    "duration_seconds": task.get("duration_seconds") or 0,
}
q = validate_completion(task, result)
print(f"Task #6169  quality : {q['quality']}")
print(f"            reason  : {q['reason']}")
assert q["quality"] == QUALITY_EMPTY_ARTIFACT, (
    f"Expected COMPLETED_EMPTY_ARTIFACT, got {q['quality']}"
)
print("Task #6169 classified as COMPLETED_EMPTY_ARTIFACT ✅")

# ── Step 3 + 5: JSON fields ───────────────────────────────────────────────
json_files = sorted(pathlib.Path("data/wbc_backend/reports").glob("optimization_ops_report_*.json"))
assert json_files, "No JSON report found"
p = json_files[-1]
r = json.loads(p.read_text())

print(f"\nJSON: {p}")
required = [
    "completed_valid_tasks",
    "completed_empty_artifact",
    "completed_noop",
    "completed_diagnostic_only",
    "effective_completed_tasks",
]
missing = [f for f in required if f not in r]
if missing:
    print(f"MISSING fields: {missing}")
    sys.exit(1)
print("\nStep 3 — required fields:")
for f in required:
    print(f"  {f}: {r[f]}")

print("\nStep 5 — effective-exclusion checks:")
assert r["completed_empty_artifact"] >= 1, "completed_empty_artifact must be >= 1"
print(f"  completed_empty_artifact >= 1   : {r['completed_empty_artifact']} ✅")
assert r["effective_completed_tasks"] == 0, (
    f"effective must be 0, got {r['effective_completed_tasks']}"
)
print(f"  effective_completed_tasks == 0  : {r['effective_completed_tasks']} ✅")
assert r["classification"] != "EFFECTIVE", (
    f"classification must not be EFFECTIVE, got {r['classification']}"
)
print(f"  classification != EFFECTIVE     : {r['classification']} ✅")

# ── Step 6: Markdown quality section ─────────────────────────────────────
md_files = sorted(pathlib.Path("docs/orchestration").glob("optimization_ops_report_*.md"))
assert md_files, "No Markdown report found"
md_path = md_files[-1]
md = md_path.read_text()

print(f"\nMarkdown: {md_path}")
assert "## Completion Quality" in md, "Completion Quality section missing"
assert "Empty Artifact" in md, "Empty Artifact row missing"
assert "⚠️" in md, "Warning block missing"
print("  ## Completion Quality section  : ✅")
print("  Empty Artifact row             : ✅")
print("  Warning block (⚠️)             : ✅")

print()
print("=== VERDICT: PHASE_10_OPS_REPORT_INTEGRATION_CONFIRMED ===")
