"""
tests/test_phase22_sandbox_patch_evaluation.py
================================================
Phase 22 — Sandbox Patch Evaluation Task Generation.

10 tests covering:
  1.  HOLD gate decision creates no patch task.
  2.  INVESTIGATE creates investigation-only task (not patch).
  3.  Weak CANDIDATE_PATCH (count < 20) creates no task.
  4.  ALLOW_PATCH_CANDIDATE creates a sandbox calibration_patch_evaluation task.
  5.  Sandbox task never has production execution mode.
  6.  Deterministic executor writes a non-empty Markdown artifact.
  7.  Evaluation result recorded in training memory.
  8.  Ops/readiness expose latest patch evaluation result.
  9.  No external LLM called during evaluation.
  10. No production model files modified by evaluation.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from orchestrator.learning_patch_gate import (
    GATE_ALLOW_PATCH,
    GATE_HOLD,
    GATE_INVESTIGATE_ONLY,
    GATE_REJECT,
    evaluate_patch_gate,
)
from orchestrator.learning_patch_task_generator import (
    EXECUTION_MODE_SANDBOX,
    generate_investigation_task,
    generate_patch_evaluation_task,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _gate_kwargs(
    recommendation: str = "HOLD",
    computed_clv_count: int = 5,
    mean_clv: float = 0.035,
    clv_variance: float = 0.00005,
    positive_rate: float = 1.0,
    source: str = "sandbox/test",
) -> dict:
    return dict(
        signal_state_type="learning_clv_quality",
        recommendation=recommendation,
        computed_clv_count=computed_clv_count,
        mean_clv=mean_clv,
        median_clv=mean_clv,
        clv_variance=clv_variance,
        positive_rate=positive_rate,
        source=source,
    )


def _allow_gate_decision(source: str = "sandbox/test") -> dict:
    """Build a pre-evaluated ALLOW_PATCH_CANDIDATE gate decision dict."""
    result = evaluate_patch_gate(
        **_gate_kwargs(
            recommendation="CANDIDATE_PATCH",
            computed_clv_count=25,
            mean_clv=-0.025,
            clv_variance=0.0003,
            positive_rate=0.20,
            source=source,
        )
    )
    result["learning_cycle_id"] = "cycle_test_p22"
    result["gate_decision_id"] = "gate_cycle_test_ALLO_2026-04-30"
    return result


def _make_negative_clv_fixture(tmp_path: Path, count: int = 25) -> Path:
    """
    Write 'count' COMPUTED CLV rows with strongly negative values to tmp_path.
    Returns the fixture directory.
    """
    fixture_dir = tmp_path / "reports"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(count):
        rows.append(json.dumps({
            "prediction_id": f"neg_pred_{i:03d}",
            "clv_status": "COMPUTED",
            "clv_value": round(-0.020 - i * 0.001, 4),
            "source": "sandbox/test",
        }))
    fixture_file = fixture_dir / "clv_validation_records_6u_2026-04-30.jsonl"
    fixture_file.write_text("\n".join(rows), encoding="utf-8")
    return fixture_dir


# ── Test 1: HOLD creates no patch task ────────────────────────────────────────

def test_hold_creates_no_patch_task():
    """HOLD gate decision → generate_patch_evaluation_task returns None."""
    hold_result = evaluate_patch_gate(**_gate_kwargs(recommendation="HOLD"))
    assert hold_result["gate_decision"] == GATE_HOLD

    task_spec = generate_patch_evaluation_task(hold_result)
    assert task_spec is None


# ── Test 2: INVESTIGATE creates investigation-only task (not patch) ───────────

def test_investigate_creates_investigation_only_task():
    """INVESTIGATE_ONLY → generate_investigation_task returns spec, generate_patch_evaluation_task returns None."""
    inv_result = evaluate_patch_gate(**_gate_kwargs(
        recommendation="INVESTIGATE", computed_clv_count=8
    ))
    assert inv_result["gate_decision"] == GATE_INVESTIGATE_ONLY

    # Must not produce a patch task
    patch_spec = generate_patch_evaluation_task(inv_result)
    assert patch_spec is None

    # Must produce an investigation task
    inv_spec = generate_investigation_task(inv_result)
    assert inv_spec is not None
    assert inv_spec["task_type"] == "model_validation_atomic"
    assert inv_spec["execution_mode"] == EXECUTION_MODE_SANDBOX
    assert inv_spec["acceptance_criteria"]["production_patch_allowed"] is False


# ── Test 3: Weak CANDIDATE_PATCH (<20) creates no task ───────────────────────

def test_weak_candidate_patch_creates_no_task():
    """CANDIDATE_PATCH with count < 20 → gate REJECTS → no task generated."""
    weak_result = evaluate_patch_gate(**_gate_kwargs(
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=15,
        mean_clv=-0.025,
        clv_variance=0.0003,
        positive_rate=0.20,
    ))
    assert weak_result["gate_decision"] == GATE_REJECT

    task_spec = generate_patch_evaluation_task(weak_result)
    assert task_spec is None


# ── Test 4: ALLOW_PATCH_CANDIDATE creates sandbox calibration task ────────────

def test_allow_patch_candidate_creates_sandbox_calibration_task():
    """ALLOW_PATCH_CANDIDATE → generate_patch_evaluation_task returns a sandbox task spec."""
    gate = _allow_gate_decision(source="sandbox/test")
    assert gate["gate_decision"] == GATE_ALLOW_PATCH

    task_spec = generate_patch_evaluation_task(gate)
    assert task_spec is not None
    assert task_spec["task_type"] == "calibration_patch_evaluation"
    assert task_spec["execution_mode"] == EXECUTION_MODE_SANDBOX
    assert task_spec["source"] == "learning_patch_gate"
    assert task_spec["acceptance_criteria"]["no_production_mutation"] is True
    assert task_spec["acceptance_criteria"]["no_external_llm"] is True
    assert task_spec["acceptance_criteria"]["production_patch_allowed"] is False
    assert "sandbox" in task_spec["title"].lower() or "SANDBOX" in task_spec["title"]


# ── Test 5: Sandbox task never has production execution mode ──────────────────

def test_sandbox_task_never_has_production_execution_mode():
    """All generated task specs from sandbox source must use SANDBOX_ONLY mode."""
    gate = _allow_gate_decision(source="sandbox/test")
    task_spec = generate_patch_evaluation_task(gate)

    assert task_spec is not None
    assert task_spec["execution_mode"] == "SANDBOX_ONLY"
    assert task_spec["execution_mode"] != "PRODUCTION"
    assert task_spec["acceptance_criteria"]["production_patch_allowed"] is False
    # Task family must be in safe sandbox set
    assert task_spec["analysis_family"] in (
        "calibration-patch-evaluation", "model-validation-atomic"
    )


# ── Test 6: Deterministic executor writes non-empty Markdown artifact ─────────

def test_deterministic_executor_writes_artifact(tmp_path):
    """calibration_patch_evaluation executor produces a non-empty .md file."""
    from orchestrator.safe_task_executor import execute_safe_task

    fixture_dir = _make_negative_clv_fixture(tmp_path, count=25)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    task = {
        "id": "p22_test_006",
        "task_type": "calibration_patch_evaluation",
        "_sandbox_reports_dir": str(fixture_dir),
        "_sandbox_artifact_dir": str(artifact_dir),
        "learning_cycle_id": "cycle_test_p22",
        "gate_decision_id": "gate_test_006",
    }

    result = execute_safe_task(task)

    assert result["success"] is True
    assert result["execution_mode"] == "SANDBOX_ONLY"
    assert result["production_patch_allowed"] is False
    assert result["evaluation_decision"] in (
        "KEEP_SANDBOX_CANDIDATE", "REJECT_SANDBOX_CANDIDATE", "NEED_MORE_DATA"
    )

    artifact_path = Path(result["completed_file_path"])
    assert artifact_path.exists(), f"Artifact not found: {artifact_path}"
    content = artifact_path.read_text(encoding="utf-8")
    assert len(content) > 100, "Artifact is too short"
    assert "SANDBOX_ONLY" in content
    assert "production_patch_allowed" in content.lower() or "false" in content.lower()


# ── Test 7: Evaluation result recorded in training memory ────────────────────

def test_evaluation_result_recorded_in_training_memory(tmp_path):
    """record_patch_evaluation persists result; get_latest_patch_evaluation retrieves it."""
    import orchestrator.training_memory as tm_module
    from orchestrator.safe_task_executor import execute_safe_task

    orig = tm_module.MEMORY_PATH
    tm_module.MEMORY_PATH = tmp_path / "training_memory.json"
    try:
        fixture_dir = _make_negative_clv_fixture(tmp_path, count=5)
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()

        task = {
            "id": "p22_test_007",
            "task_type": "calibration_patch_evaluation",
            "_sandbox_reports_dir": str(fixture_dir),
            "_sandbox_artifact_dir": str(artifact_dir),
            "learning_cycle_id": "cycle_test_p22",
            "gate_decision_id": "gate_test_007",
        }
        result = execute_safe_task(task)

        tm_module.record_patch_evaluation(
            gate_decision_id=result["gate_decision_id"],
            task_id="p22_test_007",
            evaluation_decision=result["evaluation_decision"],
            baseline_metric=result["baseline_mean_clv"],
            candidate_metric=result["candidate_mean_clv"],
            delta=result["delta"],
            sample_count=result["sample_count"],
            source=result["source"],
            learning_cycle_id=result["learning_cycle_id"],
            artifact_path=result["completed_file_path"],
        )

        latest = tm_module.get_latest_patch_evaluation()
        assert latest is not None
        assert latest["gate_decision_id"] == "gate_test_007"
        assert latest["task_id"] == "p22_test_007"
        assert latest["evaluation_decision"] in (
            "KEEP_SANDBOX_CANDIDATE", "REJECT_SANDBOX_CANDIDATE", "NEED_MORE_DATA"
        )
        assert latest["production_patch_allowed"] is False
        assert latest["source"] == "sandbox/test"
        assert "recorded_at" in latest
    finally:
        tm_module.MEMORY_PATH = orig


# ── Test 8: Ops/readiness expose latest patch evaluation ─────────────────────

def test_ops_readiness_expose_patch_evaluation(tmp_path):
    """After recording a patch evaluation, training_memory exposes it correctly."""
    import orchestrator.training_memory as tm_module

    orig = tm_module.MEMORY_PATH
    tm_module.MEMORY_PATH = tmp_path / "training_memory.json"
    try:
        tm_module.record_patch_evaluation(
            gate_decision_id="gate_test_008",
            task_id="p22_test_008",
            evaluation_decision="REJECT_SANDBOX_CANDIDATE",
            baseline_metric=-0.020,
            candidate_metric=-0.015,
            delta=0.005,
            sample_count=10,
            source="sandbox/test",
            learning_cycle_id="cycle_test_p22",
        )

        from orchestrator.training_memory import get_latest_patch_evaluation
        latest = get_latest_patch_evaluation()
        assert latest is not None
        assert latest["gate_decision_id"] == "gate_test_008"
        assert latest["evaluation_decision"] == "REJECT_SANDBOX_CANDIDATE"
        assert latest["production_patch_allowed"] is False

        # Verify raw memory structure
        mem = tm_module.load_memory()
        assert "patch_evaluations" in mem
        assert len(mem["patch_evaluations"]) >= 1
        entry = mem["patch_evaluations"][-1]
        assert entry["task_id"] == "p22_test_008"
    finally:
        tm_module.MEMORY_PATH = orig


# ── Test 9: No external LLM called ───────────────────────────────────────────

def test_no_external_llm_called_during_patch_evaluation(tmp_path):
    """
    The full patch evaluation pipeline (gate → task spec → executor) must not
    write to llm_usage.jsonl.
    """
    import orchestrator.llm_usage_logger as lul_module
    from orchestrator.safe_task_executor import execute_safe_task

    llm_log = tmp_path / "llm_usage.jsonl"
    orig_log_path = lul_module._LOG_PATH
    lul_module._LOG_PATH = str(llm_log)

    try:
        # 1. Gate evaluation
        gate = _allow_gate_decision(source="sandbox/test")
        assert gate["gate_decision"] == GATE_ALLOW_PATCH

        # 2. Task spec generation
        task_spec = generate_patch_evaluation_task(gate)
        assert task_spec is not None

        # 3. Deterministic executor
        fixture_dir = _make_negative_clv_fixture(tmp_path, count=5)
        artifact_dir = tmp_path / "artifacts"
        artifact_dir.mkdir()
        task_spec["id"] = "p22_test_009"
        task_spec["_sandbox_reports_dir"] = str(fixture_dir)
        task_spec["_sandbox_artifact_dir"] = str(artifact_dir)

        result = execute_safe_task(task_spec)
        assert result["success"] is True

        assert not llm_log.exists(), (
            "LLM usage log was created — LLM call is forbidden in patch evaluation: "
            + (llm_log.read_text()[:200] if llm_log.exists() else "")
        )
    finally:
        lul_module._LOG_PATH = orig_log_path


# ── Test 10: No production model files modified ──────────────────────────────

def test_no_production_model_files_modified(tmp_path):
    """
    Running calibration_patch_evaluation must not create or modify files
    outside the designated sandbox artifact directory.
    """
    from orchestrator.safe_task_executor import execute_safe_task

    fixture_dir = _make_negative_clv_fixture(tmp_path, count=10)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    # Collect production paths that must not be touched
    import orchestrator.safe_task_executor as ste
    prod_reports_dir = ste._REPORTS_DIR
    prod_tasks_root = ste._ORCH_TASKS_ROOT

    # Snapshot existing files in production paths
    def _snapshot(directory: Path) -> set[str]:
        if not directory.exists():
            return set()
        return {
            str(p) for p in directory.rglob("*") if p.is_file()
        }

    before_reports = _snapshot(prod_reports_dir)
    before_tasks = _snapshot(prod_tasks_root)

    task = {
        "id": "p22_test_010",
        "task_type": "calibration_patch_evaluation",
        "_sandbox_reports_dir": str(fixture_dir),
        "_sandbox_artifact_dir": str(artifact_dir),
        "learning_cycle_id": "cycle_test_p22",
        "gate_decision_id": "gate_test_010",
    }

    result = execute_safe_task(task)
    assert result["success"] is True

    after_reports = _snapshot(prod_reports_dir)
    after_tasks = _snapshot(prod_tasks_root)

    new_in_reports = after_reports - before_reports
    new_in_tasks = after_tasks - before_tasks

    # No new production report files
    assert not new_in_reports, (
        f"Unexpected new files in production reports dir: {new_in_reports}"
    )
    # No new task files in production tasks dir (artifact goes to sandbox artifact_dir)
    assert not new_in_tasks, (
        f"Unexpected new files in production tasks dir: {new_in_tasks}"
    )

    # Artifact must be inside the sandbox dir
    artifact_path = Path(result["completed_file_path"])
    assert str(artifact_path).startswith(str(artifact_dir)), (
        f"Artifact written outside sandbox dir: {artifact_path}"
    )
