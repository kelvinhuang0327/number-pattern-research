"""
Phase 33 Tests — CLV Batch Accumulation Scheduler
===================================================
12 tests covering:
  1.  discovers registry batch without CLV records (needs_clv_generation=True)
  2.  discovers CLV batch with pending records (needs_closing_monitor=True)
  3.  discovers CLV batch with computed records (needs_accumulation_update=True)
  4.  clv_batch_accumulation artifact is non-empty
  5.  scheduler creates candidate when evidence_state=INSUFFICIENT
  6.  scheduler does not produce patch task below threshold
  7.  crossing 30 changes evidence_state to APPROACHING
  8.  crossing 50 allows patch gate recheck
  9.  no external LLM usage (hard rule constants)
 10.  no live betting (hard rule constants)
 11.  duplicate cadence prevents spam (same slot = same focus_area)
 12.  readiness summary and ops report expose batch accumulation status
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone

import pytest

from orchestrator.clv_batch_scheduler import (
    CADENCE_FAST_MINUTES,
    CADENCE_NORMAL_MINUTES,
    compute_cadence_slot,
    discover_batches,
    get_batch_scheduler_summary,
    is_scheduler_due,
)
from orchestrator.safe_task_executor import (
    DETERMINISTIC_TASK_TYPES,
    execute_safe_task,
    is_deterministic_safe_task,
)
from orchestrator.clv_accumulation_policy import evaluate_clv_accumulation


# ── Fixture helpers ─────────────────────────────────────────────────────────

def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def _make_registry_file(reports: Path, date: str = "2026-04-30", n: int = 5) -> Path:
    p = reports / f"prediction_registry_6t_{date}.jsonl"
    _write_jsonl(p, [{"id": i, "game_date": date} for i in range(n)])
    return p


def _make_clv_file(
    reports: Path,
    date: str = "2026-04-30",
    computed: int = 0,
    pending: int = 0,
) -> Path:
    p = reports / f"clv_validation_records_6u_{date}.jsonl"
    rows: list[dict] = []
    for i in range(computed):
        rows.append({"prediction_id": f"c_{i}", "clv_status": "COMPUTED", "clv_value": 0.01})
    for i in range(pending):
        rows.append({"prediction_id": f"p_{i}", "clv_status": "PENDING_CLOSING"})
    _write_jsonl(p, rows)
    return p


def _make_memory(tmpdir: Path, runs: list[dict] | None = None) -> Path:
    mem_dir = tmpdir / "runtime" / "agent_orchestrator"
    mem_dir.mkdir(parents=True, exist_ok=True)
    mem_path = mem_dir / "training_memory.json"
    data = {"clv_accumulation_runs": runs or []}
    mem_path.write_text(json.dumps(data), encoding="utf-8")
    return mem_path


# ── Test 1: registry batch without CLV records → needs_clv_generation=True ──

def test_discovers_registry_without_clv():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        _make_registry_file(reports, "2026-05-01", n=3)

        batches = discover_batches(reports)
        assert len(batches) == 1
        b = batches[0]
        assert b["batch_date"] == "2026-05-01"
        assert b["has_registry"] is True
        assert b["has_clv_records"] is False
        assert b["needs_clv_generation"] is True
        assert b["needs_closing_monitor"] is False
        assert b["computed_count"] == 0
        assert b["pending_count"] == 0


# ── Test 2: CLV batch with pending records → needs_closing_monitor=True ────

def test_discovers_clv_with_pending_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=5, pending=3)

        batches = discover_batches(reports)
        assert len(batches) == 1
        b = batches[0]
        assert b["has_clv_records"] is True
        assert b["computed_count"] == 5
        assert b["pending_count"] == 3
        assert b["needs_closing_monitor"] is True


# ── Test 3: CLV batch with computed records → needs_accumulation_update=True ─

def test_discovers_clv_with_computed_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=14, pending=0)

        batches = discover_batches(reports)
        assert len(batches) == 1
        b = batches[0]
        assert b["computed_count"] == 14
        assert b["pending_count"] == 0
        assert b["needs_accumulation_update"] is True
        assert b["needs_clv_generation"] is False
        assert b["needs_closing_monitor"] is False


# ── Test 4: clv_batch_accumulation artifact is non-empty ───────────────────

def test_clv_batch_accumulation_artifact_non_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=14)
        mem_path = _make_memory(Path(tmpdir))

        task = {
            "id": "test_task_33",
            "task_type": "clv_batch_accumulation",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_memory_path": str(mem_path),
            "_sandbox_artifact_dir": str(artifact_dir),
        }

        result = execute_safe_task(task)

        assert result["success"] is True
        assert result["completed_text"], "completed_text must be non-empty"
        assert len(result["completed_text"]) > 100
        assert "CLV Batch Accumulation" in result["completed_text"]
        assert result["completed_file_path"] is not None
        assert Path(result["completed_file_path"]).exists()
        # Hard rule fields
        assert result["production_mutation"] is False
        assert result["live_bet_submitted"] is False
        assert result["patch_candidate_allowed"] is False


# ── Test 5: scheduler creates candidate when evidence_state=INSUFFICIENT ────

def test_clv_batch_is_registered_deterministic_task():
    """clv_batch_accumulation must be in DETERMINISTIC_TASK_TYPES."""
    assert "clv_batch_accumulation" in DETERMINISTIC_TASK_TYPES
    assert is_deterministic_safe_task({"task_type": "clv_batch_accumulation"})


def test_scheduler_candidate_when_insufficient():
    """get_batch_scheduler_summary returns scheduler_due=True when no previous run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=14)
        mem_path = _make_memory(Path(tmpdir))  # no previous runs

        summary = get_batch_scheduler_summary(reports_dir=reports, memory_path=mem_path)
        assert summary["available"] is True
        assert summary["scheduler_due"] is True, (
            "scheduler_due must be True when no previous accumulation run exists"
        )
        # Evidence state should be INSUFFICIENT for 14 records
        assert summary["evidence_state"] == "INSUFFICIENT"


# ── Test 6: scheduler does NOT produce patch task below threshold ───────────

def test_no_patch_task_below_threshold():
    """Accumulation below threshold: patch_gate_recheck_allowed=False, no patch candidate."""
    records = [{"clv_status": "COMPUTED"}] * 14
    result = evaluate_clv_accumulation(records=records)
    assert result["patch_gate_recheck_allowed"] is False
    assert result["patch_candidate_allowed"] is False
    # Scheduler recommendations must not include any patch action (only NO_PATCH_TASKS)
    sched_recs = result.get("scheduler_recommendations", [])
    forbidden = [r for r in sched_recs if "PATCH" in r.upper() and "NO_PATCH" not in r.upper()]
    assert len(forbidden) == 0, f"Unexpected patch recommendations: {forbidden}"


# ── Test 7: crossing 30 changes evidence_state to APPROACHING ───────────────

def test_crossing_30_changes_state_to_approaching():
    records = [{"clv_status": "COMPUTED"}] * 30
    result = evaluate_clv_accumulation(records=records)
    assert result["evidence_state"] == "APPROACHING"
    assert result["computed_count"] == 30
    assert result["remaining_needed"] == 20
    assert result["patch_gate_recheck_allowed"] is False  # still below 50


# ── Test 8: crossing 50 allows patch gate recheck ───────────────────────────

def test_crossing_50_allows_patch_gate_recheck():
    records = [{"clv_status": "COMPUTED"}] * 50
    result = evaluate_clv_accumulation(records=records)
    assert result["evidence_state"] == "SUFFICIENT"
    assert result["patch_gate_recheck_allowed"] is True
    assert result["remaining_needed"] == 0


# ── Test 9: no external LLM usage ────────────────────────────────────────────

def test_no_external_llm_usage():
    """Executor must not call external LLM — hard rule in result fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=5)
        mem_path = _make_memory(Path(tmpdir))
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()

        task = {
            "id": "test_no_llm",
            "task_type": "clv_batch_accumulation",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_memory_path": str(mem_path),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)

        # Artifact must state no LLM was called
        assert "No external LLM called" in result["completed_text"]
        assert result["production_mutation"] is False


# ── Test 10: no live betting ──────────────────────────────────────────────────

def test_no_live_betting():
    """Executor result must confirm live_bet_submitted=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=5)
        mem_path = _make_memory(Path(tmpdir))
        artifact_dir = Path(tmpdir) / "artifacts"
        artifact_dir.mkdir()

        task = {
            "id": "test_no_bet",
            "task_type": "clv_batch_accumulation",
            "_sandbox_reports_dir": str(reports),
            "_sandbox_memory_path": str(mem_path),
            "_sandbox_artifact_dir": str(artifact_dir),
        }
        result = execute_safe_task(task)

        assert result["live_bet_submitted"] is False
        assert result["execution_mode"] == "PAPER_ONLY"


# ── Test 11: duplicate cadence prevents spam (same slot = same focus_area) ──

def test_duplicate_cadence_prevents_spam():
    """
    Two calls to compute_cadence_slot within the same window produce the same slot_index,
    meaning the focus_area key would be identical and prevent duplicate task creation.
    """
    # Normal cadence: consecutive calls in the same 1440-min window
    idx1, mins1 = compute_cadence_slot(pending_batches=0, new_registry_detected=False)
    idx2, mins2 = compute_cadence_slot(pending_batches=0, new_registry_detected=False)
    assert idx1 == idx2, "Same normal cadence window must produce same slot index"
    assert mins1 == CADENCE_NORMAL_MINUTES
    assert mins2 == CADENCE_NORMAL_MINUTES

    # Fast cadence when pending records exist
    idx3, mins3 = compute_cadence_slot(pending_batches=5, new_registry_detected=False)
    idx4, mins4 = compute_cadence_slot(pending_batches=3, new_registry_detected=False)
    assert idx3 == idx4, "Same fast cadence window must produce same slot index"
    assert mins3 == CADENCE_FAST_MINUTES

    # is_scheduler_due returns False when a recent run was recorded within the normal cadence
    with tempfile.TemporaryDirectory() as tmpdir:
        now = datetime.now(timezone.utc)
        recent_run = {"generated_at": now.isoformat()}
        mem_path = _make_memory(Path(tmpdir), runs=[recent_run])
        reports = Path(tmpdir) / "reports"
        reports.mkdir()
        _make_clv_file(reports, "2026-04-30", computed=14)

        batches = discover_batches(reports)
        due = is_scheduler_due(batches, mem_path, _now=now)
        assert due is False, (
            "is_scheduler_due must return False when last run was just now (within cadence)"
        )


# ── Test 12: readiness and ops report expose batch accumulation status ────────

def test_readiness_and_ops_expose_batch_scheduler():
    """get_readiness_summary and generate_report must include clv_batch_scheduler."""
    from orchestrator.optimization_readiness import get_readiness_summary
    summary = get_readiness_summary()
    assert "clv_batch_scheduler" in summary, (
        "get_readiness_summary() must include 'clv_batch_scheduler'"
    )
    assert isinstance(summary["clv_batch_scheduler"], dict)

    from orchestrator.optimization_ops_report import generate_report
    report = generate_report(window="8h")
    assert "clv_batch_scheduler" in report, (
        "generate_report() must include 'clv_batch_scheduler'"
    )
    assert isinstance(report["clv_batch_scheduler"], dict)
