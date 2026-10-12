#!/usr/bin/env python
"""
scripts/run_phase22_patch_evaluation_validation.py
==================================================
Phase 22 — Sandbox Patch Evaluation Task Generation: 7-step validation.

Exercises the full pipeline end-to-end:
  Gate decision → Task spec → Deterministic executor → Artifact → Memory → Readiness

Usage:
    python scripts/run_phase22_patch_evaluation_validation.py

Exit code: 0 on full pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
import tempfile
import textwrap
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

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

RESULTS: dict[int, bool] = {}


def _pass(step: int, label: str) -> None:
    RESULTS[step] = True
    print(f"  ✓  Step {step}: {label}")


def _fail(step: int, label: str, detail: str) -> None:
    RESULTS[step] = False
    print(f"  ✗  Step {step}: {label}")
    print(textwrap.indent(detail, "       "))


def _make_negative_clv_fixture(directory: Path, count: int = 25) -> Path:
    rows = [
        json.dumps({
            "clv_status": "COMPUTED",
            "clv_value": round(-0.020 - i * 0.001, 4),
            "source": "sandbox/test",
        })
        for i in range(count)
    ]
    fixture_dir = directory / "reports"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "clv_validation_records_6u_2026-04-30.jsonl").write_text(
        "\n".join(rows), encoding="utf-8"
    )
    return fixture_dir


# ── Step 1: HOLD / REJECT / INVESTIGATE never produce patch task ──────────────

def step1_non_allow_decisions_produce_no_patch_task() -> None:
    step = 1
    label = "HOLD / REJECT / INVESTIGATE never produce a patch task"
    try:
        for rec, count in [("HOLD", 5), ("INVESTIGATE", 8)]:
            gate = evaluate_patch_gate(
                signal_state_type="learning_clv_quality",
                recommendation=rec,
                computed_clv_count=count,
                mean_clv=0.035,
                median_clv=0.030,
                clv_variance=0.0001,
                positive_rate=0.8,
                source="sandbox/test",
            )
            spec = generate_patch_evaluation_task(gate)
            assert spec is None, f"{rec} should not produce patch spec, got {spec}"

        # REJECT (too few records)
        gate_rej = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="CANDIDATE_PATCH",
            computed_clv_count=4,
            mean_clv=-0.025,
            median_clv=-0.020,
            clv_variance=0.0003,
            positive_rate=0.10,
            source="sandbox/test",
        )
        assert gate_rej["gate_decision"] == GATE_REJECT
        assert generate_patch_evaluation_task(gate_rej) is None

        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 2: INVESTIGATE creates investigation task, not patch ─────────────────

def step2_investigate_creates_investigation_task() -> None:
    step = 2
    label = "INVESTIGATE_ONLY → investigation task spec (not patch)"
    try:
        gate = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="INVESTIGATE",
            computed_clv_count=8,
            mean_clv=0.002,
            median_clv=0.001,
            clv_variance=0.0001,
            positive_rate=0.50,
            source="sandbox/test",
        )
        assert gate["gate_decision"] == GATE_INVESTIGATE_ONLY
        patch_spec = generate_patch_evaluation_task(gate)
        assert patch_spec is None, "INVESTIGATE must not create patch spec"

        inv_spec = generate_investigation_task(gate)
        assert inv_spec is not None
        assert inv_spec["task_type"] == "model_validation_atomic"
        assert inv_spec["execution_mode"] == EXECUTION_MODE_SANDBOX
        assert inv_spec["acceptance_criteria"]["production_patch_allowed"] is False
        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 3: ALLOW_PATCH_CANDIDATE creates sandbox calibration task ────────────

def step3_allow_creates_sandbox_calibration_task() -> None:
    step = 3
    label = "ALLOW_PATCH_CANDIDATE → calibration_patch_evaluation task spec"
    try:
        gate = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="CANDIDATE_PATCH",
            computed_clv_count=25,
            mean_clv=-0.025,
            median_clv=-0.022,
            clv_variance=0.0003,
            positive_rate=0.20,
            source="sandbox/test",
        )
        assert gate["gate_decision"] == GATE_ALLOW_PATCH

        gate["learning_cycle_id"] = "val_step3_cycle"
        spec = generate_patch_evaluation_task(gate)
        assert spec is not None
        assert spec["task_type"] == "calibration_patch_evaluation"
        assert spec["execution_mode"] == EXECUTION_MODE_SANDBOX
        assert spec["acceptance_criteria"]["production_patch_allowed"] is False
        assert spec["acceptance_criteria"]["no_external_llm"] is True
        assert spec["acceptance_criteria"]["no_production_mutation"] is True
        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 4: Sandbox hard rule — execution_mode always SANDBOX_ONLY ────────────

def step4_sandbox_hard_rule() -> None:
    step = 4
    label = "Sandbox hard rule — execution_mode always SANDBOX_ONLY from sandbox source"
    try:
        gate = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="CANDIDATE_PATCH",
            computed_clv_count=50,
            mean_clv=-0.040,
            median_clv=-0.038,
            clv_variance=0.0010,
            positive_rate=0.10,
            source="sandbox/test",
        )
        if gate["gate_decision"] == GATE_ALLOW_PATCH:
            spec = generate_patch_evaluation_task(gate)
            assert spec is not None
            assert spec["execution_mode"] == "SANDBOX_ONLY"
            assert spec["execution_mode"] != "PRODUCTION"
            assert spec["analysis_family"] in (
                "calibration-patch-evaluation", "model-validation-atomic"
            )
        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 5: Deterministic executor writes artifact ────────────────────────────

def step5_executor_writes_artifact() -> None:
    step = 5
    label = "Deterministic executor writes non-empty sandbox artifact"
    try:
        from orchestrator.safe_task_executor import execute_safe_task

        with tempfile.TemporaryDirectory() as tmpdir:
            fixture_dir = _make_negative_clv_fixture(Path(tmpdir), count=25)
            artifact_dir = Path(tmpdir) / "artifacts"
            artifact_dir.mkdir()

            result = execute_safe_task({
                "id": "val_step5_task",
                "task_type": "calibration_patch_evaluation",
                "_sandbox_reports_dir": str(fixture_dir),
                "_sandbox_artifact_dir": str(artifact_dir),
                "learning_cycle_id": "val_step5_cycle",
                "gate_decision_id": "gate_val_step5",
            })

            assert result["success"] is True
            assert result["execution_mode"] == "SANDBOX_ONLY"
            assert result["production_patch_allowed"] is False
            assert result["evaluation_decision"] in (
                "KEEP_SANDBOX_CANDIDATE", "REJECT_SANDBOX_CANDIDATE", "NEED_MORE_DATA"
            )

            artifact = Path(result["completed_file_path"])
            assert artifact.exists()
            content = artifact.read_text(encoding="utf-8")
            assert len(content) > 100
            assert "SANDBOX_ONLY" in content

        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 6: Training memory records evaluation ────────────────────────────────

def step6_training_memory_records_evaluation() -> None:
    step = 6
    label = "Training memory persists patch evaluation and retrieves it"
    try:
        import orchestrator.training_memory as tm_module
        from orchestrator.safe_task_executor import execute_safe_task

        with tempfile.TemporaryDirectory() as tmpdir:
            orig = tm_module.MEMORY_PATH
            tm_module.MEMORY_PATH = Path(tmpdir) / "training_memory.json"
            try:
                fixture_dir = _make_negative_clv_fixture(Path(tmpdir), count=5)
                artifact_dir = Path(tmpdir) / "artifacts"
                artifact_dir.mkdir()

                result = execute_safe_task({
                    "id": "val_step6_task",
                    "task_type": "calibration_patch_evaluation",
                    "_sandbox_reports_dir": str(fixture_dir),
                    "_sandbox_artifact_dir": str(artifact_dir),
                    "learning_cycle_id": "val_step6_cycle",
                    "gate_decision_id": "gate_val_step6",
                })

                tm_module.record_patch_evaluation(
                    gate_decision_id=result["gate_decision_id"],
                    task_id="val_step6_task",
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
                assert latest["gate_decision_id"] == "gate_val_step6"
                assert latest["production_patch_allowed"] is False
            finally:
                tm_module.MEMORY_PATH = orig

        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 7: Ops/Readiness exposes patch evaluation ────────────────────────────

def step7_readiness_exposes_patch_evaluation() -> None:
    step = 7
    label = "Ops/Readiness: get_latest_patch_evaluation returns persisted result"
    try:
        import orchestrator.training_memory as tm_module

        with tempfile.TemporaryDirectory() as tmpdir:
            orig = tm_module.MEMORY_PATH
            tm_module.MEMORY_PATH = Path(tmpdir) / "training_memory.json"
            try:
                tm_module.record_patch_evaluation(
                    gate_decision_id="gate_val_step7",
                    task_id="val_step7_task",
                    evaluation_decision="KEEP_SANDBOX_CANDIDATE",
                    baseline_metric=-0.025,
                    candidate_metric=-0.015,
                    delta=0.010,
                    sample_count=25,
                    source="sandbox/test",
                    learning_cycle_id="val_step7_cycle",
                )

                from orchestrator.training_memory import get_latest_patch_evaluation
                latest = get_latest_patch_evaluation()
                assert latest is not None
                assert latest["evaluation_decision"] == "KEEP_SANDBOX_CANDIDATE"
                assert latest["production_patch_allowed"] is False
                assert latest["source"] == "sandbox/test"

                # Verify memory structure
                mem = tm_module.load_memory()
                assert "patch_evaluations" in mem
                assert len(mem["patch_evaluations"]) >= 1
            finally:
                tm_module.MEMORY_PATH = orig

        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 64)
    print("  Phase 22 — Sandbox Patch Evaluation: 7-Step Validation")
    print("=" * 64 + "\n")

    step1_non_allow_decisions_produce_no_patch_task()
    step2_investigate_creates_investigation_task()
    step3_allow_creates_sandbox_calibration_task()
    step4_sandbox_hard_rule()
    step5_executor_writes_artifact()
    step6_training_memory_records_evaluation()
    step7_readiness_exposes_patch_evaluation()

    total = len(RESULTS)
    passed = sum(RESULTS.values())
    failed = total - passed

    print()
    print("─" * 64)
    print(f"  Result: {passed}/{total} steps passed", end="")
    if failed:
        print(f"  ({failed} FAILED)")
    else:
        print()
    print("─" * 64)

    if failed == 0:
        print("\n  VERDICT: PHASE_22_SANDBOX_PATCH_EVALUATION_TASK_VERIFIED\n")
        sys.exit(0)
    else:
        failed_steps = [s for s, ok in RESULTS.items() if not ok]
        print(f"\n  VERDICT: FAILED — steps {failed_steps} require attention\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
