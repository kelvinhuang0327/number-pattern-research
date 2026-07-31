"""
Phase 20 — Sandbox Learning Cycle Runner
=========================================
Orchestrates one complete sandbox learning cycle end-to-end:

  COMPUTED CLV fixture
    → task spec generation (deterministic, no LLM, no DB)
    → CLV quality analysis execution
    → structured insight extraction
    → training memory update
    → readiness signal verification

Hard rules:
  - Source marker is always "sandbox/test" — NEVER "production"
  - No external LLM called
  - No production CLV JSONL file modified
  - No live betting triggered
  - No production patch generated from sandbox signal
  - Results MUST NOT be treated as production performance

Typical usage (tests / validation script):
    from orchestrator.learning_cycle_runner import run_sandbox_learning_cycle

    result = run_sandbox_learning_cycle(
        reports_dir=Path("runtime/agent_orchestrator/test_fixtures"),
        task_id="phase20_drill_001",
    )
    assert result["learning_cycle_status"] == "COMPLETED"
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_FIXTURE_DIR = (
    _REPO_ROOT / "runtime" / "agent_orchestrator" / "test_fixtures"
)
_DEFAULT_ARTIFACT_ROOT = (
    _REPO_ROOT / "runtime" / "agent_orchestrator" / "tasks"
)


def run_sandbox_learning_cycle(
    reports_dir: Path | None = None,
    artifact_dir: Path | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    """
    Run one complete sandbox learning cycle.

    Steps:
      1. Build a sandbox clv_quality_analysis task spec.
      2. Execute via the deterministic safe executor (no LLM).
      3. Record the result to training memory.
      4. Return a structured cycle result dict.

    Args:
        reports_dir:  Directory containing fixture CLV JSONL files.
                      Defaults to ``runtime/agent_orchestrator/test_fixtures/``.
        artifact_dir: Override the artifact output directory.
                      Defaults to ``runtime/agent_orchestrator/tasks/YYYYMMDD/``.
        task_id:      Explicit task ID string; a UUID is generated if omitted.

    Returns:
        {
          "task_id": str,
          "learning_cycle_status": "COMPLETED" | "FAILED",
          "computed_count": int,
          "mean_clv": float | None,
          "recommendation": str,
          "artifact_path": str | None,
          "insight": dict,
          "source": "sandbox/test",
          "executed_at": str,           # ISO timestamp
          "no_llm_used": True,          # Always True for this executor
          "no_production_mutation": True,
        }

    Raises:
        RuntimeError: if the executor signals failure (``success=False``).
    """
    from orchestrator.safe_task_executor import execute_safe_task
    from orchestrator import training_memory as tm

    resolved_task_id = task_id or f"phase20_cycle_{uuid.uuid4().hex[:12]}"
    resolved_reports_dir = reports_dir or _DEFAULT_FIXTURE_DIR
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    resolved_artifact_dir = artifact_dir or (_DEFAULT_ARTIFACT_ROOT / date_str)

    logger.info(
        "[LearningCycleRunner] Starting sandbox learning cycle task_id=%s "
        "reports_dir=%s",
        resolved_task_id,
        resolved_reports_dir,
    )

    # ── Build sandbox task spec ───────────────────────────────────────────
    task: dict[str, Any] = {
        "id": resolved_task_id,
        "task_type": "clv_quality_analysis",
        "title": f"Sandbox CLV Quality Analysis — {resolved_task_id}",
        "source": "sandbox/test",
        # Sandbox injection fields (private, never set in production)
        "_sandbox_reports_dir": resolved_reports_dir,
        "_sandbox_artifact_dir": resolved_artifact_dir,
    }

    # ── Execute deterministically (zero LLM) ─────────────────────────────
    exec_result = execute_safe_task(task)

    if not exec_result.get("success"):
        logger.error(
            "[LearningCycleRunner] Executor reported failure for task_id=%s",
            resolved_task_id,
        )
        return {
            "task_id": resolved_task_id,
            "learning_cycle_status": "FAILED",
            "computed_count": 0,
            "mean_clv": None,
            "recommendation": "INVESTIGATE",
            "artifact_path": None,
            "insight": {},
            "source": "sandbox/test",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "no_llm_used": True,
            "no_production_mutation": True,
        }

    # ── Extract analysis results ──────────────────────────────────────────
    computed_count: int = exec_result.get("computed_count", 0)
    mean_clv: float | None = exec_result.get("mean_clv")
    recommendation: str = exec_result.get("recommendation", "INVESTIGATE")
    artifact_path: str | None = exec_result.get("completed_file_path")
    insight: dict = exec_result.get("insight", {})

    # ── Record to training memory ─────────────────────────────────────────
    tm.record_learning_cycle(
        task_id=resolved_task_id,
        computed_clv_count=computed_count,
        mean_clv=mean_clv,
        recommendation=recommendation,
        learning_cycle_status="COMPLETED",
        source="sandbox/test",
        artifact_path=artifact_path,
    )

    logger.info(
        "[LearningCycleRunner] Sandbox learning cycle COMPLETED: "
        "task_id=%s  computed=%d  mean_clv=%s  recommendation=%s",
        resolved_task_id,
        computed_count,
        f"{mean_clv:.4f}" if mean_clv is not None else "N/A",
        recommendation,
    )

    return {
        "task_id": resolved_task_id,
        "learning_cycle_status": "COMPLETED",
        "computed_count": computed_count,
        "mean_clv": mean_clv,
        "recommendation": recommendation,
        "artifact_path": artifact_path,
        "insight": insight,
        "source": "sandbox/test",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "no_llm_used": True,
        "no_production_mutation": True,
    }
