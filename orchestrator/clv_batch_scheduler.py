"""
orchestrator/clv_batch_scheduler.py
Phase 33 — CLV Batch Accumulation Scheduler

Deterministic batch discovery and scheduling policy for CLV accumulation.
Scans the reports directory for prediction registry batches and CLV validation
records, determines what work remains per date, and exposes a scheduler summary
suitable for readiness / ops / decision card surfaces.

All logic is pure / read-only.  No mutations, no LLM calls, no live betting.

HARD RULES:
  - Do not create production patches
  - Do not bypass patch gate threshold
  - Do not call external LLM
  - Do not call paid external APIs
  - Do not trigger live betting
  - Do not fake CLV records
  - Do not mark PENDING as COMPUTED without valid closing odds
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Default paths ─────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_REPORTS_DIR  = _ROOT / "data" / "wbc_backend" / "reports"
_DEFAULT_MEMORY_PATH  = _ROOT / "runtime" / "agent_orchestrator" / "training_memory.json"

# ── Cadence constants (minutes) ───────────────────────────────────────────
CADENCE_NORMAL_MINUTES: int  = 1440   # 24 h
CADENCE_FAST_MINUTES:   int  = 240    # 4 h — when pending CLV records exist
CADENCE_IMMEDIATE_MINUTES: int = 5    # new registry batch detected


# ─────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────

def _parse_date_from_filename(name: str) -> str | None:
    """Extract YYYY-MM-DD from filenames like prefix_YYYY-MM-DD.jsonl."""
    import re
    m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
    return m.group(1) if m else None


def _count_clv_statuses(path: Path) -> dict[str, int]:
    """Return {COMPUTED: n, PENDING_CLOSING: m, ...} for a CLV JSONL file."""
    counts: dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            status = row.get("clv_status", "UNKNOWN")
            counts[status] = counts.get(status, 0) + 1
    except OSError as exc:
        logger.debug("[BatchScheduler] Cannot read %s: %s", path, exc)
    return counts


def _get_last_accumulation_run_at(memory_path: Path) -> str | None:
    """Return ISO timestamp of the latest clv_accumulation_runs entry, or None."""
    try:
        raw = memory_path.read_text(encoding="utf-8")
        mem: dict = json.loads(raw)
        runs: list[dict] = mem.get("clv_accumulation_runs", [])
        if runs:
            return runs[-1].get("generated_at")
    except Exception as exc:
        logger.debug("[BatchScheduler] Cannot read last accumulation run: %s", exc)
    return None


# ─────────────────────────────────────────────────────────────────────────
# Batch discovery
# ─────────────────────────────────────────────────────────────────────────

def discover_batches(reports_dir: Path | None = None) -> list[dict[str, Any]]:
    """
    Scan the reports directory and return one status dict per detected date batch.

    A "batch" is defined by a prediction_registry_6t_YYYY-MM-DD.jsonl file.
    CLV validation records (clv_validation_records_6u_YYYY-MM-DD.jsonl) are
    matched by date and their COMPUTED / PENDING_CLOSING counts are surfaced.

    Returns:
        List of batch dicts sorted by batch_date ascending.
    """
    rdir = reports_dir or _DEFAULT_REPORTS_DIR

    # Collect registry files keyed by date
    registry_by_date: dict[str, Path] = {}
    for p in rdir.glob("prediction_registry_6t_*.jsonl"):
        date = _parse_date_from_filename(p.name)
        if date:
            registry_by_date[date] = p

    # Collect CLV validation files keyed by date
    clv_by_date: dict[str, Path] = {}
    for p in rdir.glob("clv_validation_records_6u_*.jsonl"):
        if "upgraded" in p.name:
            continue
        date = _parse_date_from_filename(p.name)
        if date:
            clv_by_date[date] = p

    # Union of all known dates
    all_dates = sorted(set(registry_by_date) | set(clv_by_date))

    batches: list[dict[str, Any]] = []
    for date in all_dates:
        has_registry   = date in registry_by_date
        has_clv        = date in clv_by_date

        computed_count  = 0
        pending_count   = 0
        if has_clv:
            statuses = _count_clv_statuses(clv_by_date[date])
            computed_count = statuses.get("COMPUTED", 0)
            pending_count  = statuses.get("PENDING_CLOSING", 0)

        # Count registry rows
        registry_row_count = 0
        if has_registry:
            try:
                registry_row_count = sum(
                    1 for line in registry_by_date[date].read_text(encoding="utf-8").splitlines()
                    if line.strip() and not line.strip().startswith("{") is False
                )
            except OSError:
                pass

        needs_clv_generation     = has_registry and not has_clv
        needs_closing_monitor    = has_clv and pending_count > 0
        needs_accumulation_update = has_clv and computed_count > 0

        batches.append({
            "batch_date":               date,
            "registry_path":            str(registry_by_date[date]) if has_registry else None,
            "clv_path":                 str(clv_by_date[date]) if has_clv else None,
            "has_registry":             has_registry,
            "has_clv_records":          has_clv,
            "registry_row_count":       registry_row_count,
            "computed_count":           computed_count,
            "pending_count":            pending_count,
            "needs_clv_generation":     needs_clv_generation,
            "needs_closing_monitor":    needs_closing_monitor,
            "needs_accumulation_update": needs_accumulation_update,
        })

    return batches


# ─────────────────────────────────────────────────────────────────────────
# Scheduler state helpers
# ─────────────────────────────────────────────────────────────────────────

def compute_cadence_slot(pending_batches: int = 0, new_registry_detected: bool = False) -> tuple[int, int]:
    """
    Return (slot_index, slot_minutes) for the current cadence window.

    Priority:
      1. new_registry_detected → CADENCE_IMMEDIATE_MINUTES
      2. pending_batches > 0   → CADENCE_FAST_MINUTES
      3. otherwise             → CADENCE_NORMAL_MINUTES
    """
    if new_registry_detected:
        slot_minutes = CADENCE_IMMEDIATE_MINUTES
    elif pending_batches > 0:
        slot_minutes = CADENCE_FAST_MINUTES
    else:
        slot_minutes = CADENCE_NORMAL_MINUTES

    epoch_seconds = int(datetime.now(timezone.utc).timestamp())
    slot_index = (epoch_seconds // 60) // slot_minutes
    return slot_index, slot_minutes


def _compute_next_batch_action(batches: list[dict], accumulation: dict) -> str:
    """Return human-readable next recommended action for the batch scheduler."""
    ev_state = accumulation.get("evidence_state", "UNKNOWN")
    computed  = accumulation.get("computed_count", 0)
    threshold = accumulation.get("threshold", 50)

    pending_total = sum(b["pending_count"] for b in batches)
    needs_gen     = sum(1 for b in batches if b["needs_clv_generation"])

    if ev_state == "SUFFICIENT":
        return "RUN_PATCH_GATE_RECHECK"
    if needs_gen > 0:
        return f"GENERATE_CLV_RECORDS ({needs_gen} batch(es) missing)"
    if pending_total > 0:
        return f"RUN_CLOSING_MONITOR ({pending_total} records pending)"
    if ev_state in ("INSUFFICIENT", "APPROACHING"):
        remaining = threshold - computed
        return f"COLLECT_MORE_DATA (need {remaining} more COMPUTED records)"
    return "MONITOR"


def is_scheduler_due(
    batches: list[dict],
    memory_path: Path | None = None,
    _now: datetime | None = None,
) -> bool:
    """
    Return True if a clv_batch_accumulation task should be created now.

    Logic:
      - If any batch needs_clv_generation or needs_closing_monitor → always due
      - Otherwise, check time since last run vs. cadence
    """
    pending_total = sum(b["pending_count"] for b in batches)
    needs_gen     = any(b["needs_clv_generation"] for b in batches)

    if needs_gen or pending_total > 0:
        return True

    mpath = memory_path or _DEFAULT_MEMORY_PATH
    last_run_at = _get_last_accumulation_run_at(mpath)
    if last_run_at is None:
        return True

    now = _now or datetime.now(timezone.utc)
    try:
        from datetime import timedelta
        last_dt = datetime.fromisoformat(last_run_at.replace("Z", "+00:00"))
        elapsed_minutes = (now - last_dt).total_seconds() / 60
        return elapsed_minutes >= CADENCE_NORMAL_MINUTES
    except Exception as exc:
        logger.debug("[BatchScheduler] Cannot parse last run at: %s", exc)
        return True


# ─────────────────────────────────────────────────────────────────────────
# Public summary API
# ─────────────────────────────────────────────────────────────────────────

def get_batch_scheduler_summary(
    reports_dir: Path | None = None,
    memory_path: Path | None = None,
) -> dict[str, Any]:
    """
    High-level batch scheduler summary for readiness / ops / decision card surfaces.

    Returns:
        {
          "available": True,
          "batches_seen": int,
          "latest_batch_date": str | None,
          "pending_batches": int,        # batches with pending CLV records
          "computed_total": int,
          "pending_total": int,
          "needs_clv_generation": int,   # batches missing CLV records
          "remaining_needed": int,       # to reach threshold
          "threshold_crossed": bool,
          "scheduler_due": bool,
          "next_batch_action": str,
          "last_accumulation_run_at": str | None,
          "cadence_slot_minutes": int,
        }
    """
    rdir  = reports_dir or _DEFAULT_REPORTS_DIR
    mpath = memory_path or _DEFAULT_MEMORY_PATH

    try:
        batches = discover_batches(rdir)
    except Exception as exc:
        logger.debug("[BatchScheduler] discover_batches failed: %s", exc)
        return {"available": False, "error": str(exc)}

    # Accumulation state
    accumulation: dict = {}
    try:
        from orchestrator.clv_accumulation_policy import get_clv_accumulation_summary
        accumulation = get_clv_accumulation_summary(reports_dir=rdir, memory_path=mpath)
    except Exception as exc:
        logger.debug("[BatchScheduler] clv_accumulation_policy unavailable: %s", exc)

    computed_total  = sum(b["computed_count"] for b in batches)
    pending_total   = sum(b["pending_count"]  for b in batches)
    pending_batches = sum(1 for b in batches if b["pending_count"] > 0)
    needs_gen       = sum(1 for b in batches if b["needs_clv_generation"])
    latest_date     = batches[-1]["batch_date"] if batches else None

    threshold       = accumulation.get("threshold", 50)
    remaining       = max(0, threshold - computed_total)
    threshold_crossed = computed_total >= threshold

    new_registry_detected = any(b["needs_clv_generation"] for b in batches)
    slot_idx, slot_min = compute_cadence_slot(
        pending_batches=pending_total,
        new_registry_detected=new_registry_detected,
    )

    scheduler_due = is_scheduler_due(batches, mpath)
    next_action   = _compute_next_batch_action(batches, accumulation)
    last_run_at   = _get_last_accumulation_run_at(mpath)

    return {
        "available":             True,
        "batches_seen":          len(batches),
        "latest_batch_date":     latest_date,
        "pending_batches":       pending_batches,
        "computed_total":        computed_total,
        "pending_total":         pending_total,
        "needs_clv_generation":  needs_gen,
        "remaining_needed":      remaining,
        "threshold_crossed":     threshold_crossed,
        "scheduler_due":         scheduler_due,
        "next_batch_action":     next_action,
        "last_accumulation_run_at": last_run_at,
        "cadence_slot_minutes":  slot_min,
        "cadence_slot_index":    slot_idx,
        "batches":               batches,
        "evidence_state":        accumulation.get("evidence_state", "UNKNOWN"),
        "patch_gate_recheck_allowed": accumulation.get("patch_gate_recheck_allowed", False),
    }
