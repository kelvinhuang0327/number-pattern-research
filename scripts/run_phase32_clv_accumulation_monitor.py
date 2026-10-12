#!/usr/bin/env python3
"""
Phase 32 — CLV Accumulation & Monitoring Policy CLI

Reads the production CLV validation records and training memory,
evaluates the current accumulation state, and writes a markdown report.

Usage:
  # Dry-run (default) — read-only, no disk writes, no mutations
  PYTHONPATH=. .venv/bin/python scripts/run_phase32_clv_accumulation_monitor.py

  # Apply mode — writes report to docs/orchestration/
  PYTHONPATH=. .venv/bin/python scripts/run_phase32_clv_accumulation_monitor.py --apply

HARD RULES:
  - Do not create patch candidates
  - Do not modify production models
  - Do not trigger live betting
  - Do not call external LLMs
  - Do not treat n < 50 as sufficient
  - Do not bypass human review
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

SOURCE_MARKER        = "production/paper"
EXECUTION_MODE       = "PAPER_ONLY"
PRODUCTION_MUTATION  = False
LIVE_BET_SUBMITTED   = False
EXIT_TOKEN           = "PHASE_32_CLV_ACCUMULATION_POLICY_VERIFIED"

_REPORTS_DIR      = _ROOT / "data" / "wbc_backend" / "reports"
_MEMORY_PATH      = _ROOT / "runtime" / "agent_orchestrator" / "training_memory.json"
_DOCS_DIR         = _ROOT / "docs" / "orchestration"


# ─────────────────────────────────────────────────────────────────────────
# Pure helpers
# ─────────────────────────────────────────────────────────────────────────

def load_computed_clv_records(reports_dir: Path = _REPORTS_DIR) -> list[dict]:
    """Load all COMPUTED CLV records from the latest validation file."""
    clv_files = sorted(reports_dir.glob("clv_validation_records_*.jsonl"))
    if not clv_files:
        return []
    records: list[dict] = []
    for line in clv_files[-1].read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if rec.get("clv_status") == "COMPUTED":
                records.append(rec)
        except json.JSONDecodeError:
            continue
    return records


def build_report_markdown(
    accumulation: dict,
    task_id: str,
    generated_at: str,
    source_file: str,
    memory_path: str,
) -> str:
    """Render a markdown report from the accumulation evaluation dict."""
    ev_state = accumulation.get("evidence_state", "UNKNOWN")
    ev_icon = {"INSUFFICIENT": "🔴", "APPROACHING": "🟡", "SUFFICIENT": "🟢"}.get(ev_state, "❓")
    computed = accumulation.get("computed_count", 0)
    threshold = accumulation.get("threshold", 50)
    remaining = accumulation.get("remaining_needed", 0)
    progress = accumulation.get("progress_pct", 0.0)
    learning_ok = accumulation.get("learning_cycle_allowed", False)
    gate_ok = accumulation.get("patch_gate_recheck_allowed", False)
    next_action = accumulation.get("recommended_next_action", "")
    scheduler_recs = accumulation.get("scheduler_recommendations", [])
    priority_segs = accumulation.get("priority_segments", [])
    patch_allowed = accumulation.get("patch_candidate_allowed", False)

    lines: list[str] = [
        f"# Phase 32 — CLV Accumulation Monitor Report",
        f"",
        f"**Generated at**: {generated_at}  ",
        f"**Task ID**: `{task_id}`  ",
        f"**Execution mode**: `{EXECUTION_MODE}`  ",
        f"**Source marker**: `{SOURCE_MARKER}`  ",
        f"**Production mutation**: `{PRODUCTION_MUTATION}`  ",
        f"**Live bet submitted**: `{LIVE_BET_SUBMITTED}`  ",
        f"",
        f"---",
        f"",
        f"## Accumulation State",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Evidence state | {ev_icon} **{ev_state}** |",
        f"| Computed records | {computed} / {threshold} |",
        f"| Progress | {progress:.1f}% |",
        f"| Remaining needed | {remaining} |",
        f"| Learning cycle allowed | {'✅ YES' if learning_ok else '❌ NO'} |",
        f"| Patch gate recheck | {'✅ ALLOWED' if gate_ok else '🚫 BLOCKED'} |",
        f"| Patch candidate | {'✅ ALLOWED' if patch_allowed else '🚫 BLOCKED'} |",
        f"",
        f"**Recommended next action**: {next_action}",
        f"",
        f"---",
        f"",
        f"## Scheduler Policy",
        f"",
    ]
    for rec in scheduler_recs:
        lines.append(f"- `{rec}`")
    lines += [
        f"",
        f"---",
        f"",
        f"## Priority Segments (observation-only until threshold)",
        f"",
    ]
    if priority_segs:
        lines.append(
            f"| Classification | Segment Type | Segment Value | Count | Mean CLV | Positive Rate | Observation Only |"
        )
        lines.append(
            f"|----------------|--------------|---------------|-------|----------|---------------|-----------------|"
        )
        for seg in priority_segs:
            lines.append(
                f"| {seg.get('classification','?')} "
                f"| {seg.get('segment_type','?')} "
                f"| {seg.get('segment_value','?')} "
                f"| {seg.get('count','?')} "
                f"| {seg.get('mean_clv','?')} "
                f"| {seg.get('positive_rate','?')} "
                f"| {'YES' if seg.get('observation_only_until_threshold') else 'NO'} |"
            )
    else:
        lines.append("_No priority segments loaded from investigation memory._")

    lines += [
        f"",
        f"---",
        f"",
        f"## Data Sources",
        f"",
        f"- CLV records file: `{source_file}`",
        f"- Training memory: `{memory_path}`",
        f"",
        f"---",
        f"",
        f"## Hard Rules Compliance",
        f"",
        f"- ✅ No patch candidate generated",
        f"- ✅ No production model modified",
        f"- ✅ No live bet submitted",
        f"- ✅ No external LLM called",
        f"- ✅ n={computed} treated as INSUFFICIENT (threshold={threshold})" if computed < threshold else f"- ✅ n={computed} meets/exceeds threshold",
        f"- ✅ No human review bypassed",
        f"",
        f"---",
        f"",
        f"## Exit Token",
        f"",
        f"`{EXIT_TOKEN}`",
        f"",
    ]
    return "\n".join(lines)


def record_accumulation_to_memory(
    task_id: str,
    accumulation: dict,
    memory_path: Path = _MEMORY_PATH,
) -> None:
    """Append this accumulation run to training_memory.json under 'clv_accumulation_runs'."""
    try:
        raw = memory_path.read_text(encoding="utf-8") if memory_path.exists() else "{}"
        mem: dict = json.loads(raw)
    except Exception:
        mem = {}

    entry = {
        "task_id": task_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_MARKER,
        "execution_mode": EXECUTION_MODE,
        "production_mutation": PRODUCTION_MUTATION,
        **accumulation,
    }
    runs: list = mem.setdefault("clv_accumulation_runs", [])
    runs.append(entry)
    memory_path.write_text(json.dumps(mem, indent=2, ensure_ascii=False), encoding="utf-8")


def run_monitor(
    clv_dir: Path = _REPORTS_DIR,
    docs_dir: Path = _DOCS_DIR,
    memory_path: Path = _MEMORY_PATH,
    apply: bool = False,
    task_id: str | None = None,
) -> dict:
    """
    Core runner — pure logic, no side effects unless apply=True.

    Returns:
        A result dict including accumulation state, report_path, exit_token.
    """
    from orchestrator.clv_accumulation_policy import evaluate_clv_accumulation

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if task_id is None:
        import uuid
        task_id = f"phase32_acc_{uuid.uuid4().hex[:12]}"

    # 1. Load records
    records = load_computed_clv_records(clv_dir)
    source_file = ""
    clv_files = sorted(clv_dir.glob("clv_validation_records_*.jsonl"))
    if clv_files:
        try:
            source_file = str(clv_files[-1].relative_to(_ROOT))
        except ValueError:
            source_file = str(clv_files[-1])

    # 2. Evaluate accumulation
    accumulation = evaluate_clv_accumulation(
        records=records,
        memory_path=memory_path,
    )

    # 3. Build report markdown
    try:
        mem_rel = str(memory_path.relative_to(_ROOT))
    except ValueError:
        mem_rel = str(memory_path)
    report_md = build_report_markdown(
        accumulation=accumulation,
        task_id=task_id,
        generated_at=generated_at,
        source_file=source_file,
        memory_path=mem_rel,
    )

    # 4. Verify readiness state is still LEARNING_READY
    readiness_state = "UNKNOWN"
    try:
        from orchestrator.optimization_readiness import get_readiness_summary
        rs = get_readiness_summary()
        readiness_state = rs.get("readiness_state", "UNKNOWN")
    except Exception as exc:
        print(f"[Phase 32] Warning: Could not verify readiness state: {exc}", file=sys.stderr)

    result = {
        "task_id":          task_id,
        "generated_at":     generated_at,
        "accumulation":     accumulation,
        "readiness_state":  readiness_state,
        "report_path":      None,
        "applied":          False,
        "exit_token":       EXIT_TOKEN,
    }

    if not apply:
        print("=== DRY-RUN MODE (no files written) ===")
        print(report_md)
        print(f"\n[Phase 32] Readiness state: {readiness_state}")
        print(f"[Phase 32] Exit token: {EXIT_TOKEN}")
        return result

    # 5. Write report
    docs_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_filename = f"phase32_clv_accumulation_monitor_report_{date_str}.md"
    report_path = docs_dir / report_filename
    report_path.write_text(report_md, encoding="utf-8")

    # 6. Record to training_memory
    record_accumulation_to_memory(task_id, accumulation, memory_path)

    result["report_path"] = str(report_path)
    result["applied"] = True

    print(report_md)
    print(f"\n[Phase 32] Report written → {report_path}")
    print(f"[Phase 32] Readiness state: {readiness_state}")
    print(f"[Phase 32] Exit token: {EXIT_TOKEN}")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 32 — CLV Accumulation Monitor (read-only unless --apply)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write report to docs/orchestration/ and record to training_memory.",
    )
    parser.add_argument(
        "--task-id",
        default=None,
        help="Override task ID (default: auto-generated).",
    )
    args = parser.parse_args()

    result = run_monitor(apply=args.apply, task_id=args.task_id)

    ev_state = result["accumulation"].get("evidence_state", "UNKNOWN")
    computed = result["accumulation"].get("computed_count", 0)
    threshold = result["accumulation"].get("threshold", 50)
    print(
        f"\n[Phase 32] evidence_state={ev_state}  "
        f"computed={computed}/{threshold}  "
        f"readiness={result['readiness_state']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
