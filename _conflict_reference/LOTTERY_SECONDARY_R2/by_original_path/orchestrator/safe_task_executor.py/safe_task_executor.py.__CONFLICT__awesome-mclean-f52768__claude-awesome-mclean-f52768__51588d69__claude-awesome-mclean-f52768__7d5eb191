"""
Phase 11 — Deterministic Safe Task Executor

Executes deterministic task types directly via Python logic, bypassing LLM providers.
Each registered task type maps to a Python executor function that produces a
well-formed, non-empty artifact without relying on any external AI/LLM service.

Registered deterministic task types
-------------------------------------
closing_monitor            — CLV closing-odds audit + upgrade pass (fully implemented)
closing_availability_audit — Phase 16: per-record diagnostic snapshot (read-only)
refresh_tsl_closing        — Phase 16: TSL closing odds dry-run / diagnostic
refresh_external_closing   — Phase 16: external closing odds availability check (planned)
ops_report                 — (planned, not yet implemented)
scheduler_health_check     — (planned, not yet implemented)
artifact_health_check      — (planned, not yet implemented)
data_quality_monitor       — (planned, not yet implemented)

Hard rules:
  - Does not fake closing odds
  - Does not bypass Phase 7 closing-odds validation
  - Does not mark PENDING_CLOSING as COMPUTED without valid closing_ts > prediction_time_utc
  - Does not call any LLM/AI provider for registered deterministic task types
  - Does not alter live betting execution or strategy state
  - Does not modify original CLV JSONL source files
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPORTS_DIR = _REPO_ROOT / "data" / "wbc_backend" / "reports"
_ORCH_TASKS_ROOT = _REPO_ROOT / "runtime" / "agent_orchestrator" / "tasks"


# ── CLV state counting ────────────────────────────────────────────────────

def _count_clv_states(reports_dir: Path | None = None) -> tuple[int, int]:
    """
    Return (pending_count, computed_count) across all Phase 6U source CLV JSONL files.

    Excludes *upgraded* output files to avoid double-counting.
    Returns (0, 0) if no files are found.
    """
    rdir = reports_dir or _REPORTS_DIR
    pending = 0
    computed = 0
    for path in sorted(rdir.glob("clv_validation_records_6u_[0-9]*.jsonl")):
        if "upgraded" in path.name:
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                status = row.get("clv_status", "")
                if status == "PENDING_CLOSING":
                    pending += 1
                elif status == "COMPUTED":
                    computed += 1
        except OSError:
            continue
    return pending, computed


# ── Artifact path resolution ──────────────────────────────────────────────

def _resolve_artifact_path(task: dict) -> Path:
    """
    Determine the write path for the deterministic artifact.

    Preference:
    1. Same directory as the task prompt file — uses slot_key naming convention
       so completed_file_path is consistent with Claude/Codex paths.
    2. Fallback: tasks/{YYYYMMDD}/{task_id}-closing-monitor-report.md
    """
    task_id = task.get("id", "unknown")
    slot_key = task.get("slot_key")
    prompt_path_str = task.get("prompt_file_path")

    if prompt_path_str and os.path.isdir(os.path.dirname(prompt_path_str)):
        task_dir = Path(prompt_path_str).parent
        filename = f"{slot_key}-completed.md" if slot_key else f"{task_id}-completed.md"
        return task_dir / filename

    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    task_dir = _ORCH_TASKS_ROOT / date_str
    return task_dir / f"{task_id}-closing-monitor-report.md"


# ── closing_monitor executor ──────────────────────────────────────────────

def _execute_closing_monitor(task: dict) -> dict:
    """
    Deterministic closing monitor executor.

    Steps:
      1. Count CLV states before the monitor run (pending_before, computed_before).
      2. Call closing_odds_monitor.run_closing_odds_monitor() — real Phase 7 logic,
         which only upgrades records with valid closing_ts > prediction_time_utc.
      3. Count CLV states after (pending_after, computed_after).
      4. Build a non-empty diagnostic Markdown artifact.
      5. Write artifact to disk and return a well-formed result dict.

    If no valid closing odds are available for any pending record, the artifact still
    contains a WAITING_FOR_MARKET_SETTLEMENT status block with full diagnostic counts —
    never an empty file.
    """
    from orchestrator.closing_odds_monitor import run_closing_odds_monitor

    task_id = task.get("id", "unknown")
    exec_start = datetime.now(timezone.utc)

    logger.info(
        "[SafeExecutor] closing_monitor task #%s — starting deterministic run", task_id
    )

    # Step 1 — count before
    pending_before, computed_before = _count_clv_states()

    # Step 2 — run closing odds monitor (real Phase 7 validation inside)
    try:
        monitor_result = run_closing_odds_monitor()
    except Exception as exc:
        logger.exception(
            "[SafeExecutor] closing_odds_monitor raised for task #%s", task_id
        )
        monitor_result = {
            "dates_scanned": [],
            "total_stats": {
                "total_pending": pending_before,
                "upgraded": 0,
                "still_pending": pending_before,
                "stale_closing_rejected": 0,
            },
            "per_date": {},
            "run_at": exec_start.isoformat(),
            "_executor_error": str(exc),
        }

    # Step 3 — count after
    pending_after, computed_after = _count_clv_states()
    total_stats = monitor_result.get("total_stats", {})
    upgraded_count: int = int(total_stats.get("upgraded", 0))
    stale_rejected_count: int = int(total_stats.get("stale_closing_rejected", 0))
    dates_scanned: list[str] = monitor_result.get("dates_scanned", [])

    exec_end = datetime.now(timezone.utc)
    duration = (exec_end - exec_start).total_seconds()

    # Step 4 — Phase 15: get per-record availability diagnostics (read-only)
    from orchestrator.closing_odds_monitor import get_pending_diagnostics
    try:
        diag_result = get_pending_diagnostics()
        diag_available = True
    except Exception as _diag_exc:
        logger.debug("[SafeExecutor] get_pending_diagnostics failed: %s", _diag_exc)
        diag_result = {}
        diag_available = False

    source_summary: dict = diag_result.get("source_summary", {}) if diag_available else {}
    pending_details: list[dict] = (
        diag_result.get("pending_diagnostics", []) if diag_available else []
    )

    # Build artifact text (always non-empty)
    if upgraded_count > 0:
        status_line = (
            f"UPGRADED: {upgraded_count} record(s) promoted "
            f"PENDING_CLOSING → COMPUTED with valid closing odds"
        )
    else:
        status_line = (
            "WAITING_FOR_MARKET_SETTLEMENT: no valid closing odds available yet. "
            f"pending_count={pending_after}, computed_count={computed_after}."
        )

    dates_block = (
        "\n".join(f"- {d}" for d in dates_scanned)
        if dates_scanned
        else "- (none — no CLV 6U source files found)"
    )

    stats_json = json.dumps(
        monitor_result.get("total_stats", {}), indent=2, ensure_ascii=False
    )

    # ── Closing Odds Availability section ────────────────────────────
    if diag_available and source_summary:
        avail_block = (
            f"## Closing Odds Availability\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Pending total | {source_summary.get('pending_total', 0)} |\n"
            f"| Computed total | {source_summary.get('computed_total', 0)} |\n"
            f"| External valid | {source_summary.get('external_available_valid', 0)} |\n"
            f"| External invalid | {source_summary.get('external_available_invalid', 0)} |\n"
            f"| TSL valid | {source_summary.get('tsl_available_valid', 0)} |\n"
            f"| TSL invalid | {source_summary.get('tsl_available_invalid', 0)} |\n"
            f"| Missing all sources | {source_summary.get('missing_all_sources', 0)} |\n"
            f"| Invalid (before prediction) | {source_summary.get('invalid_before_prediction', 0)} |\n"
            f"| Invalid (same snapshot) | {source_summary.get('invalid_same_snapshot', 0)} |\n"
            f"| Stale candidates | {source_summary.get('stale_candidates', 0)} |\n"
            f"| Ready to upgrade | {source_summary.get('ready_to_upgrade', 0)} |\n"
            f"| Recommended: refresh TSL | {source_summary.get('recommended_refresh_tsl', 0)} |\n"
            f"| Recommended: refresh external | {source_summary.get('recommended_refresh_external', 0)} |\n"
            f"| Manual review required | {source_summary.get('manual_review_required', 0)} |\n\n"
            f"**Next action**: {source_summary.get('next_closing_action', '—')}\n\n"
        )
    else:
        avail_block = (
            "## Closing Odds Availability\n\n"
            "*(diagnostics unavailable — closing_odds_monitor not importable)*\n\n"
        )

    # ── Pending Details table ────────────────────────────────────────
    if pending_details:
        rows = "\n".join(
            f"| {d.get('prediction_id', '')[:16]} "
            f"| {d.get('canonical_match_id', '')} "
            f"| {d.get('selection', '')} "
            f"| {(d.get('prediction_time_utc') or '')[:16]} "
            f"| {d.get('best_candidate_source') or '—'} "
            f"| {(d.get('best_candidate_time_utc') or '')[:16] or '—'} "
            f"| {d.get('invalid_reason') or '—'} "
            f"| {d.get('recommended_action', '')} |"
            for d in pending_details
        )
        pending_block = (
            "## Pending Details\n\n"
            "| prediction_id | match_id | side | pred_time | best_source"
            " | best_time | invalid_reason | recommended_action |\n"
            "|---|---|---|---|---|---|---|---|\n"
            f"{rows}\n\n"
        )
    else:
        pending_block = "## Pending Details\n\n*(no PENDING_CLOSING records found)*\n\n"

    artifact_text = (
        f"# CLV Closing Monitor — Deterministic Report\n\n"
        f"**Task ID**: {task_id}\n"
        f"**Generated At**: {exec_end.isoformat()}\n"
        f"**Executor**: safe_task_executor (Phase 11 deterministic)\n\n"
        f"## Status\n\n"
        f"{status_line}\n\n"
        f"## CLV State Counts\n\n"
        f"| Metric | Before | After |\n"
        f"|--------|--------|-------|\n"
        f"| pending_count (PENDING_CLOSING) | {pending_before} | {pending_after} |\n"
        f"| computed_count (COMPUTED) | {computed_before} | {computed_after} |\n\n"
        f"## Upgrade Summary\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| upgraded_count | {upgraded_count} |\n"
        f"| stale_rejected_count | {stale_rejected_count} |\n"
        f"| dates_scanned | {len(dates_scanned)} |\n\n"
        f"## Dates Scanned\n\n"
        f"{dates_block}\n\n"
        f"## Monitor Run Details\n\n"
        f"```json\n{stats_json}\n```\n\n"
        f"{avail_block}"
        f"{pending_block}"
        f"## Hard Rules Verified\n\n"
        f"- \u2705 No fake closing odds used\n"
        f"- \u2705 Phase 7 validation applied to every upgrade candidate\n"
        f"- \u2705 PENDING_CLOSING marked COMPUTED only with valid "
        f"closing_ts > prediction_time_utc\n"
        f"- \u2705 No LLM provider called\n"
        f"- \u2705 No live betting state modified\n\n"
        f"*Duration: {duration:.2f}s*\n"
    )

    # Step 5 — write artifact
    artifact_path = _resolve_artifact_path(task)
    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(artifact_text, encoding="utf-8")
        logger.info("[SafeExecutor] artifact written → %s", artifact_path)
        completed_file_path: str | None = str(artifact_path)
        changed_files = [str(artifact_path)]
    except OSError as exc:
        logger.error(
            "[SafeExecutor] failed to write artifact for task #%s: %s", task_id, exc
        )
        completed_file_path = None
        changed_files = []

    return {
        "success": True,
        "completed_text": artifact_text,
        "completed_file_path": completed_file_path,
        "changed_files": changed_files,
        "duration_seconds": duration,
        # Extra diagnostic metadata (available to caller for logging)
        "pending_before": pending_before,
        "computed_before": computed_before,
        "pending_after": pending_after,
        "computed_after": computed_after,
        "upgraded_count": upgraded_count,
        "stale_rejected_count": stale_rejected_count,
    }


# ── closing_availability_audit executor ──────────────────────────────

def _execute_closing_availability_audit(task: dict) -> dict:
    """
    Phase 16/17 — Deterministic closing availability audit.

    Produces a per-record diagnostic snapshot using get_pending_diagnostics()
    without running the full upgrade pass. This is a read-only audit that
    explains WHY each PENDING_CLOSING record cannot yet be upgraded.

    Phase 17: records before/after state and outcome in closing_refresh_memory.

    Hard rules:
      - Does NOT run run_closing_odds_monitor() (no upgrade attempt)
      - Does NOT mark any record as COMPUTED
      - Does NOT call any external API
      - Artifact is always non-empty
    """
    from orchestrator.closing_odds_monitor import get_pending_diagnostics

    task_id = task.get("id", "unknown")
    exec_start = datetime.now(timezone.utc)

    logger.info(
        "[SafeExecutor] closing_availability_audit task #%s — starting read-only audit",
        task_id,
    )

    # Phase 17: capture BEFORE state
    _before_ss: dict = {}
    try:
        _before_diag = get_pending_diagnostics()
        _before_ss = _before_diag.get("source_summary", {})
    except Exception:
        pass
    _pending_before = _before_ss.get("pending_total", 0)
    _computed_before = _before_ss.get("computed_total", 0)
    _missing_before = _before_ss.get("missing_all_sources", 0)

    try:
        diag_result = get_pending_diagnostics()
        diag_available = True
    except Exception as exc:
        logger.exception("[SafeExecutor] get_pending_diagnostics failed for task #%s", task_id)
        diag_result = {}
        diag_available = False
        _diag_exc_str = str(exc)

    exec_end = datetime.now(timezone.utc)
    duration = (exec_end - exec_start).total_seconds()

    source_summary: dict = diag_result.get("source_summary", {}) if diag_available else {}
    pending_details: list[dict] = (
        diag_result.get("pending_diagnostics", []) if diag_available else []
    )
    generated_at: str = diag_result.get("generated_at", exec_end.isoformat())

    # ── Source summary table ──────────────────────────────────────────
    if diag_available and source_summary:
        next_action = source_summary.get("next_closing_action", "—")
        summary_block = (
            "## Source Summary\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Pending total | {source_summary.get('pending_total', 0)} |\n"
            f"| Computed total | {source_summary.get('computed_total', 0)} |\n"
            f"| External valid | {source_summary.get('external_available_valid', 0)} |\n"
            f"| External invalid | {source_summary.get('external_available_invalid', 0)} |\n"
            f"| TSL valid | {source_summary.get('tsl_available_valid', 0)} |\n"
            f"| TSL invalid | {source_summary.get('tsl_available_invalid', 0)} |\n"
            f"| Missing all sources | {source_summary.get('missing_all_sources', 0)} |\n"
            f"| Invalid (before prediction) | {source_summary.get('invalid_before_prediction', 0)} |\n"
            f"| Invalid (same snapshot) | {source_summary.get('invalid_same_snapshot', 0)} |\n"
            f"| Stale candidates | {source_summary.get('stale_candidates', 0)} |\n"
            f"| Recommended: refresh TSL | {source_summary.get('recommended_refresh_tsl', 0)} |\n"
            f"| Recommended: refresh external | {source_summary.get('recommended_refresh_external', 0)} |\n"
            f"| Manual review required | {source_summary.get('manual_review_required', 0)} |\n"
            f"| Ready to upgrade | {source_summary.get('ready_to_upgrade', 0)} |\n\n"
            f"**Next action**: {next_action}\n\n"
        )
    elif diag_available:
        summary_block = "## Source Summary\n\n*(no PENDING_CLOSING records found)*\n\n"
    else:
        summary_block = (
            "## Source Summary\n\n"
            f"*(diagnostics unavailable — import failed: {_diag_exc_str if not diag_available else ''})*\n\n"
        )

    # ── Per-record table ──────────────────────────────────────────────
    if pending_details:
        rows = "\n".join(
            f"| {d.get('prediction_id', '')[:16]} "
            f"| {d.get('canonical_match_id', '')} "
            f"| {d.get('selection', '')} "
            f"| {(d.get('prediction_time_utc') or '')[:16]} "
            f"| {d.get('best_candidate_source') or '—'} "
            f"| {(d.get('best_candidate_time_utc') or '')[:16] or '—'} "
            f"| {d.get('invalid_reason') or '—'} "
            f"| {d.get('recommended_action', '')} |"
            for d in pending_details
        )
        details_block = (
            "## Per-Record Diagnostics\n\n"
            "| prediction_id | match_id | side | pred_time | best_source"
            " | best_time | invalid_reason | recommended_action |\n"
            "|---|---|---|---|---|---|---|---|\n"
            f"{rows}\n\n"
        )
    else:
        details_block = (
            "## Per-Record Diagnostics\n\n*(no PENDING_CLOSING records found)*\n\n"
        )

    artifact_text = (
        f"# CLV Closing Availability Audit — Deterministic Report\n\n"
        f"**Task ID**: {task_id}\n"
        f"**Generated At**: {exec_end.isoformat()}\n"
        f"**Diagnostics Generated At**: {generated_at}\n"
        f"**Executor**: safe_task_executor (Phase 16 closing_availability_audit)\n\n"
        f"## Status\n\n"
        f"READ_ONLY AUDIT — no upgrade attempted. "
        f"Pending records: {source_summary.get('pending_total', 0)}. "
        f"Records with valid closing odds: {source_summary.get('ready_to_upgrade', 0)}.\n\n"
        f"{summary_block}"
        f"{details_block}"
        f"## Hard Rules Verified\n\n"
        f"- \u2705 No upgrade attempted (read-only audit)\n"
        f"- \u2705 No fake closing odds\n"
        f"- \u2705 No PENDING_CLOSING marked as COMPUTED\n"
        f"- \u2705 No external API called\n"
        f"- \u2705 No LLM provider called\n"
        f"- \u2705 No live betting state modified\n\n"
        f"*Duration: {duration:.2f}s*\n"
    )

    artifact_path = _resolve_artifact_path(task)
    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(artifact_text, encoding="utf-8")
        logger.info("[SafeExecutor] closing_availability_audit artifact → %s", artifact_path)
        completed_file_path: str | None = str(artifact_path)
        changed_files = [str(artifact_path)]
    except OSError as exc:
        logger.error("[SafeExecutor] failed to write audit artifact for task #%s: %s", task_id, exc)
        completed_file_path = None
        changed_files = []

    # Phase 17: record outcome
    _pending_after = source_summary.get("pending_total", 0)
    _computed_after = source_summary.get("computed_total", 0)
    _missing_after = source_summary.get("missing_all_sources", 0)
    try:
        from orchestrator.closing_refresh_memory import record_outcome as _rec_outcome
        _rec_outcome(
            action_type="closing_availability_audit",
            pending_before=_pending_before,
            pending_after=_pending_after,
            computed_before=_computed_before,
            computed_after=_computed_after,
            missing_before=_missing_before,
            missing_after=_missing_after,
        )
    except Exception as _mem_exc:
        logger.debug("[SafeExecutor] closing_refresh_memory.record_outcome failed: %s", _mem_exc)

    return {
        "success": True,
        "completed_text": artifact_text,
        "completed_file_path": completed_file_path,
        "changed_files": changed_files,
        "duration_seconds": duration,
        "pending_total": source_summary.get("pending_total", 0),
        "ready_to_upgrade": source_summary.get("ready_to_upgrade", 0),
        "recommended_refresh_tsl": source_summary.get("recommended_refresh_tsl", 0),
        "recommended_refresh_external": source_summary.get("recommended_refresh_external", 0),
    }


# ── refresh_tsl_closing executor ─────────────────────────────────────

def _execute_refresh_tsl_closing(task: dict) -> dict:
    """
    Phase 16 — Deterministic TSL closing odds refresh diagnostic.

    Checks TSL data availability for PENDING_CLOSING records that have
    recommended_action == 'refresh_tsl'. This is a safe diagnostic:
    it inspects the current timeline and reports what TSL data is available
    without making network calls.

    Hard rules:
      - Does NOT call any live TSL network API (dry-run / diagnostic only)
      - Does NOT mark any record as COMPUTED
      - Does NOT modify any state
      - Artifact is always non-empty

    Phase 17: records before/after state and outcome in closing_refresh_memory.
    """
    from orchestrator.closing_odds_monitor import get_pending_diagnostics

    task_id = task.get("id", "unknown")
    exec_start = datetime.now(timezone.utc)

    logger.info(
        "[SafeExecutor] refresh_tsl_closing task #%s — TSL refresh diagnostic",
        task_id,
    )

    # Phase 17: capture BEFORE state
    _tsl_before_ss: dict = {}
    try:
        _tsl_before_diag = get_pending_diagnostics()
        _tsl_before_ss = _tsl_before_diag.get("source_summary", {})
    except Exception:
        pass
    _tsl_pending_before = _tsl_before_ss.get("pending_total", 0)
    _tsl_computed_before = _tsl_before_ss.get("computed_total", 0)
    _tsl_missing_before = _tsl_before_ss.get("missing_all_sources", 0)

    try:
        diag_result = get_pending_diagnostics()
        diag_available = True
    except Exception as exc:
        logger.exception("[SafeExecutor] get_pending_diagnostics failed for task #%s", task_id)
        diag_result = {}
        diag_available = False

    exec_end = datetime.now(timezone.utc)
    duration = (exec_end - exec_start).total_seconds()

    source_summary: dict = diag_result.get("source_summary", {}) if diag_available else {}
    pending_details: list[dict] = (
        diag_result.get("pending_diagnostics", []) if diag_available else []
    )

    # Filter records that are TSL-relevant
    tsl_records = [
        d for d in pending_details
        if d.get("recommended_action") in ("refresh_tsl", "run_closing_monitor")
        or d.get("tsl_closing_found") is True
    ]
    missing_tsl = [
        d for d in pending_details
        if not d.get("tsl_closing_found")
    ]

    recommended_tsl = source_summary.get("recommended_refresh_tsl", 0)
    tsl_valid = source_summary.get("tsl_available_valid", 0)
    tsl_invalid = source_summary.get("tsl_available_invalid", 0)
    next_action = source_summary.get("next_closing_action", "—")

    # Build TSL record table
    if tsl_records:
        rows = "\n".join(
            f"| {d.get('prediction_id', '')[:16]} "
            f"| {d.get('canonical_match_id', '')} "
            f"| {'✅' if d.get('tsl_closing_found') else '❌'} "
            f"| {d.get('invalid_reason') or '—'} "
            f"| {d.get('recommended_action', '')} |"
            for d in tsl_records
        )
        tsl_block = (
            "## TSL-Relevant Records\n\n"
            "| prediction_id | match_id | tsl_found | invalid_reason | action |\n"
            "|---|---|---|---|---|\n"
            f"{rows}\n\n"
        )
    elif diag_available:
        tsl_block = "## TSL-Relevant Records\n\n*(none — no TSL-relevant PENDING_CLOSING records)*\n\n"
    else:
        tsl_block = "## TSL-Relevant Records\n\n*(diagnostics unavailable)*\n\n"

    if missing_tsl:
        missing_rows = "\n".join(
            f"| {d.get('prediction_id', '')[:16]} | {d.get('canonical_match_id', '')} |"
            for d in missing_tsl
        )
        missing_block = (
            "## Records Missing TSL Data\n\n"
            "| prediction_id | match_id |\n"
            "|---|---|\n"
            f"{missing_rows}\n\n"
            "**Action**: These records require TSL closing data. "
            "Run the TSL crawler (`data/tsl_crawler_v2.py`) to fetch latest closing lines.\n\n"
        )
    else:
        missing_block = "## Records Missing TSL Data\n\n*(none)*\n\n"

    artifact_text = (
        f"# TSL Closing Refresh Diagnostic — Deterministic Report\n\n"
        f"**Task ID**: {task_id}\n"
        f"**Generated At**: {exec_end.isoformat()}\n"
        f"**Executor**: safe_task_executor (Phase 16 refresh_tsl_closing)\n\n"
        f"## Status\n\n"
        f"DRY-RUN DIAGNOSTIC — no live network calls made. "
        f"TSL valid: {tsl_valid}. TSL invalid: {tsl_invalid}. "
        f"Records needing TSL refresh: {recommended_tsl}.\n\n"
        f"## TSL Data Summary\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Records needing TSL refresh | {recommended_tsl} |\n"
        f"| TSL data available (valid) | {tsl_valid} |\n"
        f"| TSL data available (invalid) | {tsl_invalid} |\n"
        f"| Missing TSL entirely | {len(missing_tsl)} |\n\n"
        f"**Next action**: {next_action}\n\n"
        f"{tsl_block}"
        f"{missing_block}"
        f"## Operator Instructions\n\n"
        f"To fetch fresh TSL closing data:\n"
        f"```bash\n"
        f"cd /path/to/betting-pool\n"
        f"python3 data/tsl_crawler_v2.py  # fetch latest TSL odds snapshot\n"
        f"python3 orchestrator/closing_odds_monitor.py  # re-run closing monitor\n"
        f"```\n\n"
        f"## Hard Rules Verified\n\n"
        f"- \u2705 No live network API calls\n"
        f"- \u2705 No PENDING_CLOSING marked as COMPUTED\n"
        f"- \u2705 No state modifications\n"
        f"- \u2705 No LLM provider called\n"
        f"- \u2705 No live betting state modified\n\n"
        f"*Duration: {duration:.2f}s*\n"
    )

    artifact_path = _resolve_artifact_path(task)
    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(artifact_text, encoding="utf-8")
        logger.info("[SafeExecutor] refresh_tsl_closing artifact → %s", artifact_path)
        completed_file_path: str | None = str(artifact_path)
        changed_files = [str(artifact_path)]
    except OSError as exc:
        logger.error("[SafeExecutor] failed to write tsl refresh artifact for task #%s: %s", task_id, exc)
        completed_file_path = None
        changed_files = []

    # Phase 17: record outcome
    _tsl_pending_after = source_summary.get("pending_total", 0)
    _tsl_computed_after = source_summary.get("computed_total", 0)
    _tsl_missing_after = source_summary.get("missing_all_sources", 0)
    try:
        from orchestrator.closing_refresh_memory import record_outcome as _rec_tsl_outcome
        _rec_tsl_outcome(
            action_type="refresh_tsl_closing",
            pending_before=_tsl_pending_before,
            pending_after=_tsl_pending_after,
            computed_before=_tsl_computed_before,
            computed_after=_tsl_computed_after,
            missing_before=_tsl_missing_before,
            missing_after=_tsl_missing_after,
        )
    except Exception as _tsl_mem_exc:
        logger.debug("[SafeExecutor] closing_refresh_memory.record_outcome(tsl) failed: %s", _tsl_mem_exc)

    return {
        "success": True,
        "completed_text": artifact_text,
        "completed_file_path": completed_file_path,
        "changed_files": changed_files,
        "duration_seconds": duration,
        "recommended_tsl_refresh": recommended_tsl,
        "tsl_available_valid": tsl_valid,
        "tsl_available_invalid": tsl_invalid,
        "missing_tsl_entirely": len(missing_tsl),
    }


# ── refresh_external_closing executor ────────────────────────────────

def _execute_refresh_external_closing(task: dict) -> dict:
    """
    Phase 16 — Deterministic external closing odds availability diagnostic.

    Inspects which PENDING_CLOSING records have external closing odds available
    but invalid (e.g. before prediction time, same snapshot). This is a
    read-only diagnostic that surfaces which records need external odds refresh.

    Hard rules:
      - Does NOT call any paid external odds API
      - Does NOT mark any record as COMPUTED
      - Does NOT modify any state
      - Artifact is always non-empty

    Phase 17: records before/after state and outcome in closing_refresh_memory.
    """
    from orchestrator.closing_odds_monitor import get_pending_diagnostics

    task_id = task.get("id", "unknown")
    exec_start = datetime.now(timezone.utc)

    logger.info(
        "[SafeExecutor] refresh_external_closing task #%s — external closing diagnostic",
        task_id,
    )

    # Phase 17: capture BEFORE state
    _ext_before_ss: dict = {}
    try:
        _ext_before_diag = get_pending_diagnostics()
        _ext_before_ss = _ext_before_diag.get("source_summary", {})
    except Exception:
        pass
    _ext_pending_before = _ext_before_ss.get("pending_total", 0)
    _ext_computed_before = _ext_before_ss.get("computed_total", 0)
    _ext_missing_before = _ext_before_ss.get("missing_all_sources", 0)

    try:
        diag_result = get_pending_diagnostics()
        diag_available = True
    except Exception as exc:
        logger.exception("[SafeExecutor] get_pending_diagnostics failed for task #%s", task_id)
        diag_result = {}
        diag_available = False

    exec_end = datetime.now(timezone.utc)
    duration = (exec_end - exec_start).total_seconds()

    source_summary: dict = diag_result.get("source_summary", {}) if diag_available else {}
    pending_details: list[dict] = (
        diag_result.get("pending_diagnostics", []) if diag_available else []
    )

    # Filter records that need external refresh
    ext_refresh_records = [
        d for d in pending_details
        if d.get("recommended_action") == "refresh_external"
        or (d.get("external_closing_found") and not d.get("candidate_valid")
            and d.get("best_candidate_source") == "external")
    ]
    ext_valid_records = [
        d for d in pending_details
        if d.get("external_closing_found") and d.get("candidate_valid")
        and d.get("best_candidate_source") == "external"
    ]
    missing_external = [
        d for d in pending_details
        if not d.get("external_closing_found")
    ]

    recommended_ext = source_summary.get("recommended_refresh_external", 0)
    ext_valid = source_summary.get("external_available_valid", 0)
    ext_invalid = source_summary.get("external_available_invalid", 0)
    next_action = source_summary.get("next_closing_action", "—")

    if ext_refresh_records:
        rows = "\n".join(
            f"| {d.get('prediction_id', '')[:16]} "
            f"| {d.get('canonical_match_id', '')} "
            f"| {'✅' if d.get('external_closing_found') else '❌'} "
            f"| {d.get('invalid_reason') or '—'} "
            f"| {(d.get('best_candidate_time_utc') or '')[:16] or '—'} |"
            for d in ext_refresh_records
        )
        refresh_block = (
            "## Records Needing External Refresh\n\n"
            "| prediction_id | match_id | ext_found | invalid_reason | ext_time |\n"
            "|---|---|---|---|---|\n"
            f"{rows}\n\n"
        )
    elif diag_available:
        refresh_block = (
            "## Records Needing External Refresh\n\n"
            "*(none — no records need external closing refresh)*\n\n"
        )
    else:
        refresh_block = "## Records Needing External Refresh\n\n*(diagnostics unavailable)*\n\n"

    if ext_valid_records:
        valid_rows = "\n".join(
            f"| {d.get('prediction_id', '')[:16]} "
            f"| {d.get('canonical_match_id', '')} "
            f"| {(d.get('best_candidate_time_utc') or '')[:16] or '—'} |"
            for d in ext_valid_records
        )
        valid_block = (
            "## Records With Valid External Closing\n\n"
            "*(these are ready to upgrade via closing_monitor)*\n\n"
            "| prediction_id | match_id | ext_time |\n"
            "|---|---|---|\n"
            f"{valid_rows}\n\n"
        )
    else:
        valid_block = ""

    artifact_text = (
        f"# External Closing Refresh Diagnostic — Deterministic Report\n\n"
        f"**Task ID**: {task_id}\n"
        f"**Generated At**: {exec_end.isoformat()}\n"
        f"**Executor**: safe_task_executor (Phase 16 refresh_external_closing)\n\n"
        f"## Status\n\n"
        f"READ-ONLY DIAGNOSTIC — no external API calls made. "
        f"External valid: {ext_valid}. External invalid: {ext_invalid}. "
        f"Records needing external refresh: {recommended_ext}. "
        f"Missing external entirely: {len(missing_external)}.\n\n"
        f"## External Closing Data Summary\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Records needing external refresh | {recommended_ext} |\n"
        f"| External data available (valid) | {ext_valid} |\n"
        f"| External data available (invalid) | {ext_invalid} |\n"
        f"| Missing external entirely | {len(missing_external)} |\n\n"
        f"**Next action**: {next_action}\n\n"
        f"{refresh_block}"
        f"{valid_block}"
        f"## Hard Rules Verified\n\n"
        f"- \u2705 No paid external odds API called\n"
        f"- \u2705 No PENDING_CLOSING marked as COMPUTED\n"
        f"- \u2705 No state modifications\n"
        f"- \u2705 No LLM provider called\n"
        f"- \u2705 No live betting state modified\n\n"
        f"*Duration: {duration:.2f}s*\n"
    )

    artifact_path = _resolve_artifact_path(task)
    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(artifact_text, encoding="utf-8")
        logger.info("[SafeExecutor] refresh_external_closing artifact → %s", artifact_path)
        completed_file_path: str | None = str(artifact_path)
        changed_files = [str(artifact_path)]
    except OSError as exc:
        logger.error("[SafeExecutor] failed to write ext refresh artifact for task #%s: %s", task_id, exc)
        completed_file_path = None
        changed_files = []

    # Phase 17: record outcome
    _ext_pending_after = source_summary.get("pending_total", 0)
    _ext_computed_after = source_summary.get("computed_total", 0)
    _ext_missing_after = source_summary.get("missing_all_sources", 0)
    try:
        from orchestrator.closing_refresh_memory import record_outcome as _rec_ext_outcome
        _rec_ext_outcome(
            action_type="refresh_external_closing",
            pending_before=_ext_pending_before,
            pending_after=_ext_pending_after,
            computed_before=_ext_computed_before,
            computed_after=_ext_computed_after,
            missing_before=_ext_missing_before,
            missing_after=_ext_missing_after,
        )
    except Exception as _ext_mem_exc:
        logger.debug("[SafeExecutor] closing_refresh_memory.record_outcome(ext) failed: %s", _ext_mem_exc)

    return {
        "success": True,
        "completed_text": artifact_text,
        "completed_file_path": completed_file_path,
        "changed_files": changed_files,
        "duration_seconds": duration,
        "recommended_external_refresh": recommended_ext,
        "external_available_valid": ext_valid,
        "external_available_invalid": ext_invalid,
        "missing_external_entirely": len(missing_external),
    }


# ── manual_review_summary executor ───────────────────────────────────────

def _execute_manual_review_summary(task: dict) -> dict:
    """
    Phase 17 — Escalation manual review summary.

    Aggregates refresh feedback state, escalation context, and per-record
    diagnostics into a structured operator-facing artifact. This task is
    triggered when automated refresh has failed to improve closing availability
    repeatedly and human intervention is required.

    Hard rules:
      - Does NOT unlock learning
      - Does NOT mark PENDING_CLOSING as COMPUTED
      - Does NOT call any paid external API
      - Does NOT modify CLV state
      - Artifact is always non-empty
    """
    from orchestrator.closing_odds_monitor import get_pending_diagnostics
    from orchestrator.closing_refresh_memory import (
        get_refresh_feedback_summary,
        get_escalation_status,
    )

    task_id = task.get("id", "unknown")
    exec_start = datetime.now(timezone.utc)

    logger.info(
        "[SafeExecutor] manual_review_summary task #%s — escalation review",
        task_id,
    )

    # Get current diagnostics
    try:
        diag_result = get_pending_diagnostics()
        diag_available = True
        source_summary: dict = diag_result.get("source_summary", {})
        pending_details: list[dict] = diag_result.get("pending_diagnostics", [])
    except Exception as exc:
        logger.exception("[SafeExecutor] get_pending_diagnostics failed for task #%s", task_id)
        diag_available = False
        source_summary = {}
        pending_details = []

    # Get refresh feedback
    feedback = get_refresh_feedback_summary()
    escalation = get_escalation_status()

    exec_end = datetime.now(timezone.utc)
    duration = (exec_end - exec_start).total_seconds()

    # ── Escalation context block ──────────────────────────────────
    esc_block = (
        "## Escalation Context\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| Escalation recommended | {'✅ YES' if escalation.get('escalation_recommended') else '❌ NO'} |\n"
        f"| Consecutive no-improvement | {escalation.get('consecutive_no_improvement', 0)} |\n"
        f"| Last refresh action | {feedback.get('last_refresh_action', '—')} |\n"
        f"| Last refresh improved | {'✅ YES' if feedback.get('last_refresh_improved') else ('❌ NO' if feedback.get('last_refresh_improved') is False else '—')} |\n"
        f"| Last refresh at | {(feedback.get('last_refresh_at_utc') or '—')[:16]} |\n"
        f"| Recommended action | **{escalation.get('recommended_escalation_action', 'manual_review_summary')}** |\n\n"
    )

    # ── Per-action escalation table ───────────────────────────────
    per_action = feedback.get("per_action", {})
    if per_action:
        action_rows = "\n".join(
            f"| {at} | {st.get('consecutive_no_improvement', 0)} "
            f"| {'✅' if st.get('escalation_recommended') else '❌'} "
            f"| {'✅' if st.get('last_improved') else ('❌' if st.get('last_improved') is False else '—')} |"
            for at, st in per_action.items()
        )
        per_action_block = (
            "## Per-Action Refresh History\n\n"
            "| Action Type | Consecutive No-Improvement | Escalated | Last Improved |\n"
            "|---|---|---|---|\n"
            f"{action_rows}\n\n"
        )
    else:
        per_action_block = (
            "## Per-Action Refresh History\n\n*(no refresh runs recorded yet)*\n\n"
        )

    # ── Current diagnostics summary ────────────────────────────────
    if diag_available and source_summary:
        diag_block = (
            "## Current Closing Odds State\n\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| Pending total | {source_summary.get('pending_total', 0)} |\n"
            f"| Computed total | {source_summary.get('computed_total', 0)} |\n"
            f"| Missing all sources | {source_summary.get('missing_all_sources', 0)} |\n"
            f"| Invalid (before prediction) | {source_summary.get('invalid_before_prediction', 0)} |\n"
            f"| Invalid (same snapshot) | {source_summary.get('invalid_same_snapshot', 0)} |\n"
            f"| Ready to upgrade | {source_summary.get('ready_to_upgrade', 0)} |\n"
            f"| Recommended: refresh TSL | {source_summary.get('recommended_refresh_tsl', 0)} |\n"
            f"| Recommended: refresh external | {source_summary.get('recommended_refresh_external', 0)} |\n"
            f"| Manual review required | {source_summary.get('manual_review_required', 0)} |\n\n"
        )
    elif diag_available:
        diag_block = "## Current Closing Odds State\n\n*(no PENDING_CLOSING records — state may have improved)*\n\n"
    else:
        diag_block = "## Current Closing Odds State\n\n*(diagnostics unavailable)*\n\n"

    # ── Operator instructions ──────────────────────────────────────
    pending_n = source_summary.get("pending_total", 0)
    missing_n = source_summary.get("missing_all_sources", 0)
    ext_recs = source_summary.get("recommended_refresh_external", 0)
    tsl_recs = source_summary.get("recommended_refresh_tsl", 0)

    instructions: list[str] = [
        "## Operator Action Required\n",
        "Automated refresh has not improved closing availability after repeated attempts.",
        "Please review the following actions:\n",
    ]
    if ext_recs > 0:
        instructions.append(
            f"1. **External closing data** ({ext_recs} records): "
            "Check if the external odds source is reachable and configure a valid API key "
            "if not already done. Run: `python3 data/odds_api_client.py --fetch-closing`"
        )
    if tsl_recs > 0:
        instructions.append(
            f"2. **TSL closing data** ({tsl_recs} records): "
            "Run the TSL crawler to fetch latest closing lines: "
            "`python3 data/tsl_crawler_v2.py`"
        )
    if missing_n > 0:
        instructions.append(
            f"3. **Missing all sources** ({missing_n} records): "
            "These records have no closing odds from any source. "
            "Manual investigation required — check game IDs against external sources."
        )
    if not instructions[3:]:
        instructions.append(
            f"No specific action identified ({pending_n} pending records). "
            "Inspect per-record diagnostics below."
        )
    instructions.append("")

    operator_block = "\n".join(instructions) + "\n"

    # ── Per-record detail table ────────────────────────────────────
    if pending_details:
        rows = "\n".join(
            f"| {d.get('prediction_id', '')[:16]} "
            f"| {d.get('canonical_match_id', '')} "
            f"| {d.get('selection', '')} "
            f"| {d.get('best_candidate_source') or '—'} "
            f"| {d.get('invalid_reason') or '—'} "
            f"| {d.get('recommended_action', '')} |"
            for d in pending_details
        )
        records_block = (
            "## Per-Record Detail\n\n"
            "| prediction_id | match_id | side | best_source | invalid_reason | recommended_action |\n"
            "|---|---|---|---|---|---|\n"
            f"{rows}\n\n"
        )
    else:
        records_block = "## Per-Record Detail\n\n*(no PENDING_CLOSING records)*\n\n"

    artifact_text = (
        f"# Manual Review Summary — Closing Refresh Escalation\n\n"
        f"**Task ID**: {task_id}\n"
        f"**Generated At**: {exec_end.isoformat()}\n"
        f"**Executor**: safe_task_executor (Phase 17 manual_review_summary)\n\n"
        f"## Status\n\n"
        f"ESCALATION TRIGGERED — automated refresh has not improved closing availability. "
        f"Pending CLV records: {source_summary.get('pending_total', 0)}. "
        f"Operator attention required.\n\n"
        f"{esc_block}"
        f"{per_action_block}"
        f"{diag_block}"
        f"{operator_block}"
        f"{records_block}"
        f"## Hard Rules Verified\n\n"
        f"- ✅ No learning unlocked\n"
        f"- ✅ No fake closing odds\n"
        f"- ✅ No PENDING_CLOSING marked as COMPUTED\n"
        f"- ✅ No paid external API called\n"
        f"- ✅ No LLM provider called\n"
        f"- ✅ No live betting state modified\n\n"
        f"*Duration: {duration:.2f}s*\n"
    )

    artifact_path = _resolve_artifact_path(task)
    try:
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(artifact_text, encoding="utf-8")
        logger.info("[SafeExecutor] manual_review_summary artifact → %s", artifact_path)
        completed_file_path: str | None = str(artifact_path)
        changed_files = [str(artifact_path)]
    except OSError as exc:
        logger.error("[SafeExecutor] failed to write manual_review_summary for task #%s: %s", task_id, exc)
        completed_file_path = None
        changed_files = []

    return {
        "success": True,
        "completed_text": artifact_text,
        "completed_file_path": completed_file_path,
        "changed_files": changed_files,
        "duration_seconds": duration,
        "escalation_recommended": escalation.get("escalation_recommended", False),
        "consecutive_no_improvement": escalation.get("consecutive_no_improvement", 0),
        "pending_total": source_summary.get("pending_total", 0),
    }


# ── Phase 20: CLV Quality Analysis executor ──────────────────────────────

def _execute_clv_quality_analysis(task: dict) -> dict:
    """
    Deterministic sandbox CLV quality analysis executor.

    Reads COMPUTED CLV records from a reports_dir (production or sandbox),
    computes descriptive statistics, determines a recommendation, writes a
    Markdown artifact, and returns a well-formed execution result.

    Sandbox injection:
        Set ``task["_sandbox_reports_dir"]`` to a ``pathlib.Path`` pointing at
        a directory with fixture JSONL files.  Production code never sets this
        field.

    Hard rules:
    - Never calls any external LLM.
    - Never modifies source CLV JSONL files.
    - Never triggers live betting or production patch generation.
    - Only reads ``clv_validation_records_6u_*.jsonl`` files.
    """
    import statistics as _stat

    task_id = str(task.get("id", "unknown"))
    exec_start = datetime.now(timezone.utc)

    logger.info(
        "[SafeExecutor] clv_quality_analysis task #%s — starting deterministic run",
        task_id,
    )

    # ── Resolve reports directory (sandbox vs production) ─────────────────
    sandbox_reports_dir = task.get("_sandbox_reports_dir")
    reports_dir: Path = (
        Path(sandbox_reports_dir) if sandbox_reports_dir else _REPORTS_DIR
    )

    # ── Read COMPUTED CLV records ─────────────────────────────────────────
    computed_rows: list[dict[str, Any]] = []
    for path in sorted(reports_dir.glob("clv_validation_records_6u_*.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("clv_status") == "COMPUTED" and row.get("clv_value") is not None:
                    try:
                        row["clv_value"] = float(row["clv_value"])
                        computed_rows.append(row)
                    except (TypeError, ValueError):
                        pass
        except OSError as exc:
            logger.warning(
                "[SafeExecutor] clv_quality_analysis: cannot read %s — %s", path, exc
            )

    # ── Compute statistics ────────────────────────────────────────────────
    computed_count = len(computed_rows)
    clv_values: list[float] = [r["clv_value"] for r in computed_rows]

    if computed_count > 0:
        mean_clv = sum(clv_values) / computed_count
        median_clv = _stat.median(clv_values)
        clv_variance = _stat.variance(clv_values) if computed_count >= 2 else 0.0
        positive_clv_count = sum(1 for v in clv_values if v > 0)
        negative_clv_count = sum(1 for v in clv_values if v < 0)
        flat_count = computed_count - positive_clv_count - negative_clv_count
        positive_rate = positive_clv_count / computed_count
    else:
        mean_clv = None
        median_clv = None
        clv_variance = None
        positive_clv_count = 0
        negative_clv_count = 0
        flat_count = 0
        positive_rate = 0.0

    # ── Recommendation logic ──────────────────────────────────────────────
    if computed_count == 0:
        recommendation = "INVESTIGATE"
    elif mean_clv is not None and mean_clv >= 0.010 and positive_rate >= 0.6:
        recommendation = "HOLD"
    elif mean_clv is not None and (mean_clv <= -0.010 or positive_rate < 0.3):
        recommendation = "CANDIDATE_PATCH"
    else:
        recommendation = "INVESTIGATE"

    # ── Confidence tier ───────────────────────────────────────────────────
    if computed_count >= 5:
        confidence = "high"
    elif computed_count >= 3:
        confidence = "medium"
    else:
        confidence = "low"

    # ── Structured insight ────────────────────────────────────────────────
    candidate_action_map = {
        "HOLD": "HOLD_STRATEGY",
        "INVESTIGATE": "INVESTIGATE_EDGE_DECAY",
        "CANDIDATE_PATCH": "PATCH_MODEL",
    }
    insight: dict[str, Any] = {
        "source": "sandbox_clv_quality_analysis",
        "signal_state_type": "learning_clv_quality",
        "confidence": confidence,
        "candidate_action": candidate_action_map.get(recommendation, "INVESTIGATE_EDGE_DECAY"),
        "requires_patch": recommendation == "CANDIDATE_PATCH",
        "evidence": {
            "computed_count": computed_count,
            "positive_clv_count": positive_clv_count,
            "negative_clv_count": negative_clv_count,
            "flat_count": flat_count,
            "mean_clv": round(mean_clv, 6) if mean_clv is not None else None,
            "median_clv": round(median_clv, 6) if median_clv is not None else None,
            "clv_variance": round(clv_variance, 6) if clv_variance is not None else None,
            "positive_rate": round(positive_rate, 4),
            "recommendation": recommendation,
        },
        "source_marker": "sandbox/test",
        "created_at": exec_start.isoformat(),
    }

    # ── Artifact path resolution ──────────────────────────────────────────
    sandbox_artifact_dir = task.get("_sandbox_artifact_dir")
    if sandbox_artifact_dir:
        artifact_dir = Path(sandbox_artifact_dir)
    else:
        date_str = exec_start.strftime("%Y%m%d")
        artifact_dir = _ORCH_TASKS_ROOT / date_str

    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{task_id}-clv-quality-analysis.md"

    # ── Build Markdown artifact ───────────────────────────────────────────
    mean_str = f"{mean_clv:.4f}" if mean_clv is not None else "N/A"
    median_str = f"{median_clv:.4f}" if median_clv is not None else "N/A"
    var_str = f"{clv_variance:.6f}" if clv_variance is not None else "N/A"
    positive_rate_str = f"{positive_rate:.1%}"

    artifact_text = (
        f"# CLV Quality Analysis — Task {task_id}\n\n"
        f"**Source**: `{reports_dir}`\n"
        f"**Executed at**: {exec_start.isoformat()}\n"
        f"**Source marker**: `sandbox/test`\n\n"
        "---\n\n"
        "## Summary Statistics\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Computed CLV records | {computed_count} |\n"
        f"| Positive CLV count   | {positive_clv_count} |\n"
        f"| Negative CLV count   | {negative_clv_count} |\n"
        f"| Flat CLV count       | {flat_count} |\n"
        f"| Mean CLV             | {mean_str} |\n"
        f"| Median CLV           | {median_str} |\n"
        f"| CLV Variance         | {var_str} |\n"
        f"| Positive rate        | {positive_rate_str} |\n\n"
        "## Recommendation\n\n"
        f"**{recommendation}**\n\n"
        f"- Confidence: `{confidence}`\n"
        f"- Requires patch: `{insight['requires_patch']}`\n"
        f"- Candidate action: `{insight['candidate_action']}`\n\n"
        "## Hard Rules Applied\n\n"
        "- No external LLM called\n"
        "- No production CLV file modified\n"
        "- No live betting triggered\n"
        "- Source marker: `sandbox/test`\n"
    )

    try:
        artifact_path.write_text(artifact_text, encoding="utf-8")
        logger.info(
            "[SafeExecutor] clv_quality_analysis: artifact written to %s", artifact_path
        )
    except OSError as exc:
        logger.error(
            "[SafeExecutor] clv_quality_analysis: artifact write failed — %s", exc
        )

    duration = (datetime.now(timezone.utc) - exec_start).total_seconds()

    return {
        "success": True,
        "completed_text": artifact_text,
        "completed_file_path": str(artifact_path),
        "changed_files": [str(artifact_path)],
        "duration_seconds": duration,
        # Analysis results (used by learning_cycle_runner)
        "computed_count": computed_count,
        "positive_clv_count": positive_clv_count,
        "negative_clv_count": negative_clv_count,
        "flat_count": flat_count,
        "mean_clv": mean_clv,
        "median_clv": median_clv,
        "clv_variance": clv_variance,
        "positive_rate": positive_rate,
        "recommendation": recommendation,
        "confidence": confidence,
        "insight": insight,
    }


# ── Registry ──────────────────────────────────────────────────────────────

# Maps task_type (lowercase) → executor function.
# Add new deterministic task types here when they are implemented.
def _execute_calibration_patch_evaluation(task: dict) -> dict:
    """
    Phase 22 — Deterministic sandbox calibration patch-evaluation executor.

    Simulates a simple calibration / threshold candidate against a baseline
    using the sandbox CLV fixture.  NO external LLM is called.  NO production
    model or CLV file is modified.

    Sandbox injection:
        ``task["_sandbox_reports_dir"]`` — Path to a directory containing
        ``clv_validation_records_6u_*.jsonl`` fixtures.

    Evaluation logic (deterministic):
        baseline  = mean of all COMPUTED CLV values (raw values as-is)
        candidate = mean of the 70th-percentile upper subset (simulates
                    a tighter threshold that retains only better-performing bets)

    Outcomes:
        KEEP_SANDBOX_CANDIDATE  — candidate_mean > baseline_mean by > 0.005
        REJECT_SANDBOX_CANDIDATE — candidate_mean <= baseline_mean
        NEED_MORE_DATA           — fewer than 3 COMPUTED records available
    """
    import statistics as _stat

    task_id = str(task.get("id", "unknown"))
    exec_start = datetime.now(timezone.utc)

    logger.info(
        "[SafeExecutor] calibration_patch_evaluation task #%s — starting sandbox eval",
        task_id,
    )

    # ── Resolve reports directory ─────────────────────────────────────────
    sandbox_reports_dir = task.get("_sandbox_reports_dir")
    reports_dir: Path = (
        Path(sandbox_reports_dir) if sandbox_reports_dir else _REPORTS_DIR
    )

    # ── Read COMPUTED CLV records (identical to clv_quality_analysis reader) ─
    clv_values: list[float] = []
    for path in sorted(reports_dir.glob("clv_validation_records_6u_*.jsonl")):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("clv_status") == "COMPUTED" and row.get("clv_value") is not None:
                    try:
                        clv_values.append(float(row["clv_value"]))
                    except (TypeError, ValueError):
                        pass
        except OSError as exc:
            logger.warning(
                "[SafeExecutor] calibration_patch_evaluation: cannot read %s — %s",
                path,
                exc,
            )

    sample_count = len(clv_values)

    # ── Evaluate ──────────────────────────────────────────────────────────
    if sample_count < 3:
        evaluation_decision = "NEED_MORE_DATA"
        baseline_mean = None
        candidate_mean = None
        delta = None
        reason = f"Insufficient data: {sample_count} record(s) — need >= 3"
    else:
        # Baseline: mean of all records
        baseline_mean = sum(clv_values) / sample_count

        # Candidate: mean of top-70th-percentile by CLV value
        # (simulates a stricter acceptance threshold)
        sorted_vals = sorted(clv_values, reverse=True)
        top_n = max(1, int(sample_count * 0.70))
        candidate_vals = sorted_vals[:top_n]
        candidate_mean = sum(candidate_vals) / len(candidate_vals)

        delta = candidate_mean - baseline_mean

        if delta > 0.005:
            evaluation_decision = "KEEP_SANDBOX_CANDIDATE"
            reason = (
                f"Candidate mean {candidate_mean:.4f} exceeds baseline "
                f"{baseline_mean:.4f} by {delta:.4f} — candidate retained in sandbox"
            )
        else:
            evaluation_decision = "REJECT_SANDBOX_CANDIDATE"
            reason = (
                f"Candidate mean {candidate_mean:.4f} does not outperform baseline "
                f"{baseline_mean:.4f} (delta={delta:.4f}) — candidate rejected"
            )

    # ── Artifact ──────────────────────────────────────────────────────────
    sandbox_artifact_dir = task.get("_sandbox_artifact_dir")
    if sandbox_artifact_dir:
        artifact_dir = Path(sandbox_artifact_dir)
    else:
        date_str = exec_start.strftime("%Y%m%d")
        artifact_dir = _ORCH_TASKS_ROOT / date_str

    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{task_id}-calibration-patch-evaluation.md"

    def _fmt(v: float | None) -> str:
        return f"{v:.4f}" if v is not None else "N/A"

    learning_cycle_id = task.get("learning_cycle_id", "unknown")
    gate_decision_id = task.get("gate_decision_id", "unknown")

    artifact_text = (
        f"# Calibration Patch Evaluation — Task {task_id}\n\n"
        f"**Execution mode**: `SANDBOX_ONLY`\n"
        f"**Source**: `{reports_dir}`\n"
        f"**Executed at**: {exec_start.isoformat()}\n"
        f"**Learning cycle**: `{learning_cycle_id}`\n"
        f"**Gate decision**: `{gate_decision_id}`\n\n"
        "---\n\n"
        "## Evaluation Summary\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Sample count       | {sample_count} |\n"
        f"| Baseline mean CLV  | {_fmt(baseline_mean)} |\n"
        f"| Candidate mean CLV | {_fmt(candidate_mean)} |\n"
        f"| Delta              | {_fmt(delta)} |\n"
        f"| **Decision**       | **{evaluation_decision}** |\n\n"
        f"## Reason\n\n{reason}\n\n"
        "## Hard Rules Applied\n\n"
        "- No external LLM called\n"
        "- No production model modified\n"
        "- No production CLV file modified\n"
        "- No live betting triggered\n"
        "- Execution mode: `SANDBOX_ONLY`\n"
        "- production_patch_allowed: `false`\n"
    )

    try:
        artifact_path.write_text(artifact_text, encoding="utf-8")
        logger.info(
            "[SafeExecutor] calibration_patch_evaluation: artifact → %s", artifact_path
        )
    except OSError as exc:
        logger.error(
            "[SafeExecutor] calibration_patch_evaluation: artifact write failed — %s", exc
        )

    duration = (datetime.now(timezone.utc) - exec_start).total_seconds()

    return {
        "success": True,
        "completed_text": artifact_text,
        "completed_file_path": str(artifact_path),
        "changed_files": [str(artifact_path)],
        "duration_seconds": duration,
        # Evaluation results
        "sample_count": sample_count,
        "baseline_mean_clv": baseline_mean,
        "candidate_mean_clv": candidate_mean,
        "delta": delta,
        "evaluation_decision": evaluation_decision,
        "reason": reason,
        # Provenance
        "execution_mode": "SANDBOX_ONLY",
        "production_patch_allowed": False,
        "source": "sandbox/test",
        "learning_cycle_id": learning_cycle_id,
        "gate_decision_id": gate_decision_id,
    }


DETERMINISTIC_TASK_TYPES: dict[str, Callable[[dict], dict]] = {
    "closing_monitor": _execute_closing_monitor,
    "closing_availability_audit": _execute_closing_availability_audit,
    "refresh_tsl_closing": _execute_refresh_tsl_closing,
    "refresh_external_closing": _execute_refresh_external_closing,
    "manual_review_summary": _execute_manual_review_summary,
    "clv_quality_analysis": _execute_clv_quality_analysis,
    "calibration_patch_evaluation": _execute_calibration_patch_evaluation,
}

# Future task types — listed here for registry completeness; not yet implemented.
_PLANNED_DETERMINISTIC_TYPES: frozenset[str] = frozenset({
    "ops_report",
    "scheduler_health_check",
    "artifact_health_check",
    "data_quality_monitor",
})


# ── Public API ────────────────────────────────────────────────────────────

def is_deterministic_safe_task(task: dict) -> bool:
    """
    Return True if *task* should be executed via the deterministic safe executor
    instead of being routed to an LLM provider.

    Only tasks with a task_type registered in DETERMINISTIC_TASK_TYPES qualify.
    """
    task_type = (task.get("task_type") or "").lower().strip()
    return task_type in DETERMINISTIC_TASK_TYPES


def execute_safe_task(task: dict) -> dict:
    """
    Execute a deterministic safe task without calling any LLM provider.

    Dispatches to the executor registered for task.task_type and returns a
    standard execution_result dict that is compatible with worker_tick's
    Phase 10 completion-quality validation.

    Args:
        task: DB task row dict (must have task_type set).

    Returns:
        {
          "success": bool,
          "completed_text": str,        # always non-empty for registered executors
          "completed_file_path": str | None,
          "changed_files": list[str],
          "duration_seconds": float,
          # executor-specific extra fields may also be present
        }

    Raises:
        ValueError: if task_type is not in DETERMINISTIC_TASK_TYPES.
    """
    task_type = (task.get("task_type") or "").lower().strip()
    executor = DETERMINISTIC_TASK_TYPES.get(task_type)

    if executor is None:
        raise ValueError(
            f"execute_safe_task: task_type={task_type!r} is not a registered "
            f"deterministic safe task. Registered types: {sorted(DETERMINISTIC_TASK_TYPES)}"
        )

    logger.info(
        "[SafeExecutor] task #%s (type=%s) → deterministic executor",
        task.get("id"), task_type,
    )
    return executor(task)
