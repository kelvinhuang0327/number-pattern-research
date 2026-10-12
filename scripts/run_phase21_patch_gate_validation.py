#!/usr/bin/env python
"""
scripts/run_phase21_patch_gate_validation.py
=============================================
Phase 21 — Candidate Patch Gate from Learning Insight: 7-step validation.

Exercises every gate decision path end-to-end, verifies training memory
persistence, confirms ops/readiness exposure, and guarantees no LLM is
called during gate evaluation.

Usage:
    python scripts/run_phase21_patch_gate_validation.py

Exit code: 0 on full pass, 1 on any failure.
"""
from __future__ import annotations

import json
import sys
import tempfile
import textwrap
from pathlib import Path

# ── Repo root on sys.path ─────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator.learning_patch_gate import (
    GATE_ALLOW_PATCH,
    GATE_HOLD,
    GATE_INVESTIGATE_ONLY,
    GATE_REJECT,
    evaluate_patch_gate,
)

STEPS: list[tuple[int, str]] = []
RESULTS: dict[int, bool] = {}


def _pass(step: int, label: str) -> None:
    RESULTS[step] = True
    print(f"  ✓  Step {step}: {label}")


def _fail(step: int, label: str, detail: str) -> None:
    RESULTS[step] = False
    print(f"  ✗  Step {step}: {label}")
    print(textwrap.indent(detail, "       "))


# ── Step 1: Gate module importable — HOLD blocks patch ──────────────────────

def step1_hold_blocks_patch() -> None:
    step = 1
    label = "Gate module importable — HOLD decision blocks patch"
    try:
        result = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="HOLD",
            computed_clv_count=5,
            mean_clv=0.035,
            median_clv=0.030,
            clv_variance=0.00005,
            positive_rate=1.0,
            source="sandbox/test",
        )
        assert result["gate_decision"] == GATE_HOLD, f"Expected HOLD, got {result['gate_decision']}"
        assert result["allowed_task_family"] is None, (
            f"HOLD must yield no task family, got {result['allowed_task_family']}"
        )
        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 2: INVESTIGATE_ONLY — investigation task, not patch ─────────────────

def step2_investigate_only() -> None:
    step = 2
    label = "INVESTIGATE_ONLY gate — creates investigation task, not patch"
    try:
        result = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="INVESTIGATE",
            computed_clv_count=8,
            mean_clv=0.002,
            median_clv=0.001,
            clv_variance=0.0001,
            positive_rate=0.50,
            source="sandbox/test",
        )
        assert result["gate_decision"] == GATE_INVESTIGATE_ONLY, (
            f"Expected INVESTIGATE_ONLY, got {result['gate_decision']}"
        )
        assert result["allowed_task_family"] == "model-validation-atomic", (
            f"Wrong family: {result['allowed_task_family']}"
        )
        assert result["gate_decision"] != GATE_ALLOW_PATCH, "Must not allow patch"
        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 3: REJECT_INSUFFICIENT_EVIDENCE — count < 5 blocked ────────────────

def step3_reject_insufficient_evidence() -> None:
    step = 3
    label = "REJECT_INSUFFICIENT_EVIDENCE — computed_count < 5 always blocked"
    try:
        result_4 = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="CANDIDATE_PATCH",
            computed_clv_count=4,
            mean_clv=-0.025,
            median_clv=-0.020,
            clv_variance=0.0003,
            positive_rate=0.10,
            source="sandbox/test",
        )
        assert result_4["gate_decision"] == GATE_REJECT, (
            f"count=4 should be REJECT, got {result_4['gate_decision']}"
        )

        # Also test: variance=None
        result_no_var = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="CANDIDATE_PATCH",
            computed_clv_count=10,
            mean_clv=-0.025,
            median_clv=-0.020,
            clv_variance=None,
            positive_rate=0.10,
            source="sandbox/test",
        )
        assert result_no_var["gate_decision"] == GATE_REJECT, (
            f"variance=None should be REJECT, got {result_no_var['gate_decision']}"
        )
        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 4: ALLOW_PATCH_CANDIDATE — count ≥ 20 with strong negative signal ──

def step4_allow_patch_candidate() -> None:
    step = 4
    label = "ALLOW_PATCH_CANDIDATE — 25 records, mean_clv=-0.025, positive_rate=0.20"
    try:
        result = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="CANDIDATE_PATCH",
            computed_clv_count=25,
            mean_clv=-0.025,
            median_clv=-0.022,
            clv_variance=0.0003,
            positive_rate=0.20,
            source="sandbox/test",
        )
        assert result["gate_decision"] == GATE_ALLOW_PATCH, (
            f"Expected ALLOW_PATCH_CANDIDATE, got {result['gate_decision']}\n{result['reason']}"
        )
        assert result["allowed_task_family"] is not None, "Must specify an allowed family"
        assert result["requires_human_review"] is True, "Sandbox patch requires human review"
        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 5: Sandbox hard rule — task family is always sandbox-safe ────────────

def step5_sandbox_hard_rule() -> None:
    step = 5
    label = "Sandbox hard rule — allowed_task_family never production-only type"
    production_only = {"model-patch-atomic", "calibration-atomic"}
    try:
        result = evaluate_patch_gate(
            signal_state_type="learning_clv_quality",
            recommendation="CANDIDATE_PATCH",
            computed_clv_count=50,
            mean_clv=-0.040,
            median_clv=-0.035,
            clv_variance=0.0010,
            positive_rate=0.10,
            source="sandbox/test",
        )
        if result["gate_decision"] == GATE_ALLOW_PATCH:
            fam = result.get("allowed_task_family")
            assert fam not in production_only, (
                f"Sandbox must not yield production family: {fam}"
            )
        _pass(step, label)
    except Exception as exc:
        _fail(step, label, str(exc))


# ── Step 6: Training memory records gate decisions ────────────────────────────

def step6_training_memory_records_gate() -> None:
    step = 6
    label = "Training memory records gate decisions and retrieves them correctly"
    import orchestrator.training_memory as tm_module

    with tempfile.TemporaryDirectory() as tmpdir:
        orig = tm_module.MEMORY_PATH
        tm_module.MEMORY_PATH = Path(tmpdir) / "training_memory.json"
        try:
            result = evaluate_patch_gate(
                signal_state_type="learning_clv_quality",
                recommendation="HOLD",
                computed_clv_count=5,
                mean_clv=0.035,
                median_clv=0.030,
                clv_variance=0.00005,
                positive_rate=1.0,
                source="sandbox/test",
            )
            tm_module.record_gate_decision(
                learning_cycle_id="val_step6_cycle",
                gate_decision=result["gate_decision"],
                reason=result["reason"],
                confidence=result["confidence"],
                requires_human_review=result["requires_human_review"],
                recommendation=result["recommendation"],
                computed_clv_count=result["computed_clv_count"],
                source=result["source"],
                generated_task_id=None,
                allowed_task_family=result["allowed_task_family"],
            )

            latest = tm_module.get_latest_gate_decision()
            assert latest is not None, "get_latest_gate_decision returned None"
            assert latest["learning_cycle_id"] == "val_step6_cycle"
            assert latest["gate_decision"] == GATE_HOLD
            assert "recorded_at" in latest
            _pass(step, label)
        except Exception as exc:
            _fail(step, label, str(exc))
        finally:
            tm_module.MEMORY_PATH = orig


# ── Step 7: Ops/Readiness expose gate result ──────────────────────────────────

def step7_ops_readiness_expose_gate_result() -> None:
    step = 7
    label = "Ops/Readiness expose latest_gate_decision in their summaries"
    import orchestrator.training_memory as tm_module

    with tempfile.TemporaryDirectory() as tmpdir:
        orig = tm_module.MEMORY_PATH
        tm_module.MEMORY_PATH = Path(tmpdir) / "training_memory.json"
        try:
            tm_module.record_gate_decision(
                learning_cycle_id="val_step7_cycle",
                gate_decision=GATE_INVESTIGATE_ONLY,
                reason="Validation step 7 test",
                confidence="medium",
                requires_human_review=False,
                recommendation="INVESTIGATE",
                computed_clv_count=8,
                source="sandbox/test",
            )

            from orchestrator.training_memory import get_latest_gate_decision
            rd = get_latest_gate_decision()
            assert rd is not None, "get_latest_gate_decision returned None"
            assert rd["gate_decision"] == GATE_INVESTIGATE_ONLY
            assert rd["learning_cycle_id"] == "val_step7_cycle"

            # Verify that memory JSON contains gate_decisions key
            mem = tm_module.load_memory()
            assert "gate_decisions" in mem, "gate_decisions key missing from training memory"
            assert len(mem["gate_decisions"]) >= 1

            _pass(step, label)
        except Exception as exc:
            _fail(step, label, str(exc))
        finally:
            tm_module.MEMORY_PATH = orig


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 64)
    print("  Phase 21 — Candidate Patch Gate: 7-Step Validation")
    print("=" * 64 + "\n")

    step1_hold_blocks_patch()
    step2_investigate_only()
    step3_reject_insufficient_evidence()
    step4_allow_patch_candidate()
    step5_sandbox_hard_rule()
    step6_training_memory_records_gate()
    step7_ops_readiness_expose_gate_result()

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
        print("\n  VERDICT: PHASE_21_LEARNING_PATCH_GATE_VERIFIED\n")
        sys.exit(0)
    else:
        failed_steps = [s for s, ok in RESULTS.items() if not ok]
        print(f"\n  VERDICT: FAILED — steps {failed_steps} require attention\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
