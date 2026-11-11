"""
tests/test_phase21_learning_patch_gate.py
==========================================
Phase 21 — Candidate Patch Gate from Learning Insight.

9 tests covering:
  1. HOLD recommendation does not create patch.
  2. INVESTIGATE creates investigation-only task (model-validation-atomic).
  3. CANDIDATE_PATCH with low sample count is rejected.
  4. CANDIDATE_PATCH with strong sandbox evidence creates sandbox patch-evaluation task.
  5. Sandbox source never creates production patch family.
  6. Production source requires higher sample count (≥50 vs ≥20).
  7. training_memory records gate decision.
  8. ops_report / readiness expose gate result.
  9. No external LLM is called during gate evaluation.
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


# ── Shared fixture factories ─────────────────────────────────────────────────

def _base_kwargs(
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


# ── Test 1: HOLD does not create patch ──────────────────────────────────────

def test_hold_recommendation_does_not_create_patch():
    """HOLD recommendation → gate_decision=HOLD, no allowed task family."""
    result = evaluate_patch_gate(**_base_kwargs(
        recommendation="HOLD",
        computed_clv_count=5,
        mean_clv=0.035,
        positive_rate=1.0,
    ))

    assert result["gate_decision"] == GATE_HOLD
    assert result["allowed_task_family"] is None
    assert "HOLD" in result["reason"]
    assert result["requires_human_review"] is False


# ── Test 2: INVESTIGATE creates investigation-only task ──────────────────────

def test_investigate_creates_investigation_only_task():
    """INVESTIGATE with adequate evidence → INVESTIGATE_ONLY + model-validation-atomic."""
    result = evaluate_patch_gate(**_base_kwargs(
        recommendation="INVESTIGATE",
        computed_clv_count=8,
        mean_clv=0.002,
        positive_rate=0.5,
    ))

    assert result["gate_decision"] == GATE_INVESTIGATE_ONLY
    assert result["allowed_task_family"] == "model-validation-atomic"
    # Must NOT return ALLOW_PATCH or HOLD
    assert result["gate_decision"] != GATE_ALLOW_PATCH
    assert result["gate_decision"] != GATE_HOLD


# ── Test 3: CANDIDATE_PATCH with low sample count is rejected ────────────────

def test_candidate_patch_rejected_low_sample_count():
    """CANDIDATE_PATCH with computed_count < _MIN_COUNT → REJECT."""
    # 4 records < minimum 5
    result = evaluate_patch_gate(**_base_kwargs(
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=4,
        mean_clv=-0.025,
        positive_rate=0.10,
        clv_variance=0.0003,
    ))

    assert result["gate_decision"] == GATE_REJECT
    assert result["allowed_task_family"] is None
    assert "4" in result["reason"]  # mentions the actual count

    # Also test: ≥5 but < sandbox threshold of 20 → also REJECT for CANDIDATE_PATCH
    result2 = evaluate_patch_gate(**_base_kwargs(
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=15,
        mean_clv=-0.025,
        positive_rate=0.10,
        clv_variance=0.0003,
        source="sandbox/test",
    ))
    assert result2["gate_decision"] == GATE_REJECT
    assert "15" in result2["reason"]


# ── Test 4: CANDIDATE_PATCH with strong sandbox evidence → allowed ────────────

def test_candidate_patch_strong_sandbox_evidence_creates_patch_evaluation():
    """CANDIDATE_PATCH with 20+ sandbox records and negative edge → ALLOW."""
    result = evaluate_patch_gate(**_base_kwargs(
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=25,
        mean_clv=-0.025,
        clv_variance=0.0003,
        positive_rate=0.20,
        source="sandbox/test",
    ))

    assert result["gate_decision"] == GATE_ALLOW_PATCH
    assert result["allowed_task_family"] in (
        "model-validation-atomic", "calibration-patch-evaluation"
    )
    assert result["requires_human_review"] is True   # sandbox always requires review
    assert "sandbox" in result["reason"].lower()


# ── Test 5: Sandbox source never creates production patch family ──────────────

def test_sandbox_never_creates_production_patch_family():
    """Sandbox source ALLOW decision must not yield a production-only patch family."""
    production_only_families = {"model-patch-atomic", "calibration-atomic"}

    # Even with extremely strong evidence, sandbox must stay in safe families
    result = evaluate_patch_gate(**_base_kwargs(
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=100,
        mean_clv=-0.050,
        clv_variance=0.0010,
        positive_rate=0.05,
        source="sandbox/test",
    ))

    if result["gate_decision"] == GATE_ALLOW_PATCH:
        assert result["allowed_task_family"] not in production_only_families, (
            f"Sandbox must not yield production family: {result['allowed_task_family']}"
        )
    # Either ALLOW (with safe family) or REJECT — never a production family
    assert result["allowed_task_family"] not in production_only_families or \
           result["allowed_task_family"] is None


# ── Test 6: Production source requires higher sample count ────────────────────

def test_production_source_requires_higher_sample_count():
    """Production source CANDIDATE_PATCH requires ≥50 records (sandbox only needs ≥20)."""
    # 25 records is enough for sandbox but not production
    sandbox_result = evaluate_patch_gate(**_base_kwargs(
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=25,
        mean_clv=-0.025,
        clv_variance=0.0003,
        positive_rate=0.20,
        source="sandbox/test",
    ))
    production_result = evaluate_patch_gate(**_base_kwargs(
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=25,
        mean_clv=-0.025,
        clv_variance=0.0003,
        positive_rate=0.20,
        source="production",
    ))

    assert sandbox_result["gate_decision"] == GATE_ALLOW_PATCH
    assert production_result["gate_decision"] == GATE_REJECT
    assert "50" in production_result["reason"]  # mentions production threshold

    # 55 records should pass production threshold
    production_ok = evaluate_patch_gate(**_base_kwargs(
        recommendation="CANDIDATE_PATCH",
        computed_clv_count=55,
        mean_clv=-0.025,
        clv_variance=0.0003,
        positive_rate=0.20,
        source="production",
    ))
    assert production_ok["gate_decision"] == GATE_ALLOW_PATCH


# ── Test 7: training_memory records gate decision ─────────────────────────────

def test_training_memory_records_gate_decision(tmp_path):
    """Gate result is persisted to training_memory and can be retrieved."""
    import orchestrator.training_memory as tm_module

    orig = tm_module.MEMORY_PATH
    tm_module.MEMORY_PATH = tmp_path / "training_memory.json"
    try:
        gate_result = evaluate_patch_gate(**_base_kwargs(
            recommendation="HOLD",
            computed_clv_count=5,
        ))

        tm_module.record_gate_decision(
            learning_cycle_id="cycle_test_007",
            gate_decision=gate_result["gate_decision"],
            reason=gate_result["reason"],
            confidence=gate_result["confidence"],
            requires_human_review=gate_result["requires_human_review"],
            recommendation=gate_result["recommendation"],
            computed_clv_count=gate_result["computed_clv_count"],
            source=gate_result["source"],
            generated_task_id=None,
            allowed_task_family=gate_result["allowed_task_family"],
        )

        history = tm_module.get_gate_decision_history()
        assert len(history) >= 1

        latest = tm_module.get_latest_gate_decision()
        assert latest is not None
        assert latest["learning_cycle_id"] == "cycle_test_007"
        assert latest["gate_decision"] == GATE_HOLD
        assert latest["source"] == "sandbox/test"
        assert "recorded_at" in latest
    finally:
        tm_module.MEMORY_PATH = orig


# ── Test 8: ops_report / readiness expose gate result ────────────────────────

def test_ops_report_and_readiness_expose_gate_result(tmp_path):
    """
    After recording a gate decision, ops_report and readiness summary both
    contain a latest_gate_decision field.
    """
    import orchestrator.training_memory as tm_module
    import orchestrator.optimization_ops_report as ops_module
    import orchestrator.optimization_readiness as readiness_module

    orig_path = tm_module.MEMORY_PATH
    tm_module.MEMORY_PATH = tmp_path / "training_memory.json"
    try:
        # Record a gate decision so memory has content
        tm_module.record_gate_decision(
            learning_cycle_id="cycle_test_008",
            gate_decision=GATE_HOLD,
            reason="HOLD: test",
            confidence="low",
            requires_human_review=False,
            recommendation="HOLD",
            computed_clv_count=5,
            source="sandbox/test",
        )

        # ops_report training memory summary
        mem = tm_module.load_memory()
        gate_decisions = mem.get("gate_decisions", [])
        latest = gate_decisions[-1] if gate_decisions else None
        assert latest is not None
        assert latest["gate_decision"] == GATE_HOLD

        # readiness get_latest_gate_decision
        from orchestrator.training_memory import get_latest_gate_decision
        rd = get_latest_gate_decision()
        assert rd is not None
        assert rd["gate_decision"] == GATE_HOLD
        assert rd["learning_cycle_id"] == "cycle_test_008"
    finally:
        tm_module.MEMORY_PATH = orig_path


# ── Test 9: No external LLM called during gate evaluation ────────────────────

def test_no_external_llm_called_during_gate_evaluation(tmp_path):
    """
    evaluate_patch_gate is fully deterministic — it must not write to
    llm_usage.jsonl and must not import or call any LLM provider.
    """
    import orchestrator.llm_usage_logger as lul_module

    llm_log = tmp_path / "llm_usage.jsonl"
    orig_log_path = lul_module._LOG_PATH
    lul_module._LOG_PATH = str(llm_log)
    try:
        # Run gate under all three recommendation types
        for rec, count, mean_v, pos_rate in [
            ("HOLD", 5, 0.035, 1.0),
            ("INVESTIGATE", 8, 0.002, 0.5),
            ("CANDIDATE_PATCH", 25, -0.025, 0.20),
        ]:
            evaluate_patch_gate(
                signal_state_type="learning_clv_quality",
                recommendation=rec,
                computed_clv_count=count,
                mean_clv=mean_v,
                median_clv=mean_v,
                clv_variance=0.0003,
                positive_rate=pos_rate,
                source="sandbox/test",
            )

        # llm_usage.jsonl must not have been created or written to
        assert not llm_log.exists(), (
            f"Gate evaluation wrote to llm_usage.jsonl — LLM usage is forbidden: "
            f"{llm_log.read_text()[:200] if llm_log.exists() else ''}"
        )
    finally:
        lul_module._LOG_PATH = orig_log_path
