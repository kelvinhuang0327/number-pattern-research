"""
tests/test_phase23_patch_evaluation_gate.py
============================================
Phase 23 — Sandbox Patch Evaluation Decision Gate.

9 tests covering:
  1. REJECT_SANDBOX_CANDIDATE → REJECT, no task generated.
  2. NEED_MORE_DATA → REQUEST_MORE_DATA, allowed_next_task_family = clv-quality-analysis.
  3. KEEP_SANDBOX_CANDIDATE + sample_count < 50 → HUMAN_REVIEW_REQUIRED.
  4. KEEP_SANDBOX_CANDIDATE + sample_count >= 50 + material delta → PROMOTE, human review required.
  5. Sandbox result NEVER auto-applies production patch (production_patch_allowed always False).
  6. Training memory records gate decision correctly.
  7. Readiness exposes latest eval gate decision.
  8. No external LLM called throughout the full pipeline.
  9. PROMOTE_TO_PRODUCTION_PROPOSAL always requires human review.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from orchestrator.patch_evaluation_gate import (
    ED_KEEP,
    ED_MORE,
    ED_REJECT,
    ND_HOLD,
    ND_HUMAN_REVIEW,
    ND_PROMOTE,
    ND_REJECT,
    ND_REQUEST_MORE,
    TF_CLV_QUALITY,
    TF_MANUAL_REVIEW,
    TF_PRODUCTION_PROPOSAL,
    _PROMOTE_MIN_SANDBOX,
    _MATERIAL_DELTA_THRESHOLD,
    evaluate_patch_evaluation_gate,
)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _make_eval(
    evaluation_decision: str = ED_KEEP,
    sample_count: int = 60,
    delta: float = 0.010,
    source: str = "sandbox/test",
    task_id: str = "task_p23_test",
    gate_decision_id: str = "gate_p23_test",
    baseline_metric: float = -0.030,
    candidate_metric: float = -0.020,
) -> dict:
    return {
        "evaluation_decision": evaluation_decision,
        "sample_count": sample_count,
        "delta": delta,
        "source": source,
        "task_id": task_id,
        "gate_decision_id": gate_decision_id,
        "baseline_mean_clv": baseline_metric,
        "candidate_mean_clv": candidate_metric,
        "learning_cycle_id": "cycle_p23_test",
        "production_patch_allowed": False,
    }


# ── Test 1: REJECT_SANDBOX_CANDIDATE → REJECT, no task ────────────────────────

def test_reject_sandbox_candidate_returns_reject():
    """REJECT_SANDBOX_CANDIDATE evaluation → REJECT gate decision."""
    ev = _make_eval(evaluation_decision=ED_REJECT, delta=-0.003, sample_count=5)
    result = evaluate_patch_evaluation_gate(ev)

    assert result["next_decision"] == ND_REJECT
    assert result["allowed_next_task_family"] is None
    assert result["requires_human_review"] is False
    assert result["production_patch_allowed"] is False
    assert result["evaluation_decision"] == ED_REJECT


# ── Test 2: NEED_MORE_DATA → REQUEST_MORE_DATA + clv-quality-analysis ─────────

def test_need_more_data_returns_request_more_with_clv_family():
    """NEED_MORE_DATA evaluation → REQUEST_MORE_DATA with clv-quality-analysis family."""
    ev = _make_eval(evaluation_decision=ED_MORE, sample_count=2, delta=None)
    result = evaluate_patch_evaluation_gate(ev)

    assert result["next_decision"] == ND_REQUEST_MORE
    assert result["allowed_next_task_family"] == TF_CLV_QUALITY
    assert result["requires_human_review"] is False
    assert result["production_patch_allowed"] is False


# ── Test 3: KEEP + sample < 50 → HUMAN_REVIEW_REQUIRED ───────────────────────

def test_keep_sandbox_small_sample_requires_human_review():
    """KEEP with sample_count < _PROMOTE_MIN_SANDBOX → HUMAN_REVIEW or REQUEST_MORE_DATA."""
    assert _PROMOTE_MIN_SANDBOX == 50  # sanity-check constant

    # With promising delta but insufficient sample → HUMAN_REVIEW_REQUIRED
    ev = _make_eval(
        evaluation_decision=ED_KEEP,
        sample_count=30,
        delta=_MATERIAL_DELTA_THRESHOLD + 0.001,  # above threshold
        source="sandbox/test",
    )
    result = evaluate_patch_evaluation_gate(ev)

    assert result["next_decision"] == ND_HUMAN_REVIEW
    assert result["requires_human_review"] is True
    assert result["production_patch_allowed"] is False
    assert result["allowed_next_task_family"] in (TF_MANUAL_REVIEW, TF_CLV_QUALITY, None)


def test_keep_sandbox_small_sample_low_delta_requests_more_data():
    """KEEP with small sample AND delta below threshold → REQUEST_MORE_DATA."""
    ev = _make_eval(
        evaluation_decision=ED_KEEP,
        sample_count=20,
        delta=0.001,  # below _MATERIAL_DELTA_THRESHOLD
        source="sandbox/test",
    )
    result = evaluate_patch_evaluation_gate(ev)

    assert result["next_decision"] == ND_REQUEST_MORE
    assert result["production_patch_allowed"] is False
    assert result["allowed_next_task_family"] == TF_CLV_QUALITY


# ── Test 4: KEEP + sample >= 50 + material delta → PROMOTE + human review ─────

def test_keep_sandbox_sufficient_sample_and_delta_promotes():
    """KEEP with sample >= 50 and material delta → PROMOTE_TO_PRODUCTION_PROPOSAL."""
    ev = _make_eval(
        evaluation_decision=ED_KEEP,
        sample_count=_PROMOTE_MIN_SANDBOX,
        delta=_MATERIAL_DELTA_THRESHOLD + 0.001,
        source="sandbox/test",
    )
    result = evaluate_patch_evaluation_gate(ev)

    assert result["next_decision"] == ND_PROMOTE
    assert result["requires_human_review"] is True  # ALWAYS required for promote
    assert result["production_patch_allowed"] is False
    assert result["allowed_next_task_family"] == TF_PRODUCTION_PROPOSAL
    assert result["confidence"] == "high"


# ── Test 5: Sandbox result NEVER auto-applies production patch ─────────────────

def test_sandbox_result_never_auto_applies_production_patch():
    """
    All possible evaluation_decision values must return production_patch_allowed=False.
    """
    for ev_dec in (ED_KEEP, ED_REJECT, ED_MORE):
        for sample in (5, 50, 200):
            for source in ("sandbox/test", "sandbox"):
                ev = _make_eval(
                    evaluation_decision=ev_dec,
                    sample_count=sample,
                    delta=0.020 if ev_dec == ED_KEEP else -0.001,
                    source=source,
                )
                result = evaluate_patch_evaluation_gate(ev)
                assert result["production_patch_allowed"] is False, (
                    f"production_patch_allowed must be False for "
                    f"ev_dec={ev_dec!r} sample={sample} source={source!r}; "
                    f"got {result}"
                )
                assert result.get("production_model_modified") is False
                assert result.get("external_llm_called") is False


# ── Test 6: Training memory records gate decision ─────────────────────────────

def test_training_memory_records_eval_gate_decision(tmp_path):
    """record_patch_evaluation_gate_decision persists entry; getter retrieves it."""
    import orchestrator.training_memory as tm_module
    from orchestrator.training_memory import (
        record_patch_evaluation_gate_decision,
        get_latest_patch_evaluation_gate_decision,
    )

    orig = tm_module.MEMORY_PATH
    tm_module.MEMORY_PATH = tmp_path / "training_memory.json"
    try:
        ev = _make_eval(
            evaluation_decision=ED_KEEP,
            sample_count=60,
            delta=0.012,
            source="sandbox/test",
            task_id="task_p23_t6",
        )
        gate_result = evaluate_patch_evaluation_gate(ev)

        record_patch_evaluation_gate_decision(
            task_id="task_p23_t6",
            evaluation_decision=ev["evaluation_decision"],
            next_decision=gate_result["next_decision"],
            reason=gate_result["reason"],
            confidence=gate_result["confidence"],
            requires_human_review=gate_result["requires_human_review"],
            allowed_next_task_family=gate_result["allowed_next_task_family"],
            gate_decision_id=ev["gate_decision_id"],
            source=ev["source"],
            delta=ev["delta"],
            sample_count=ev["sample_count"],
        )

        latest = get_latest_patch_evaluation_gate_decision()
        assert latest is not None
        assert latest["task_id"] == "task_p23_t6"
        assert latest["evaluation_decision"] == ED_KEEP
        assert latest["next_decision"] == gate_result["next_decision"]
        assert latest["production_patch_allowed"] is False
        assert latest["production_model_modified"] is False
        assert latest["external_llm_called"] is False
        assert "recorded_at" in latest

        # Check raw memory structure
        mem = tm_module.load_memory()
        assert "patch_eval_gate_decisions" in mem
        assert len(mem["patch_eval_gate_decisions"]) >= 1
    finally:
        tm_module.MEMORY_PATH = orig


# ── Test 7: Readiness exposes latest eval gate decision ───────────────────────

def test_readiness_exposes_latest_eval_gate_decision(tmp_path):
    """After recording a gate decision, get_latest_patch_evaluation_gate_decision returns it."""
    import orchestrator.training_memory as tm_module
    from orchestrator.training_memory import (
        record_patch_evaluation_gate_decision,
        get_latest_patch_evaluation_gate_decision,
    )

    orig = tm_module.MEMORY_PATH
    tm_module.MEMORY_PATH = tmp_path / "training_memory.json"
    try:
        record_patch_evaluation_gate_decision(
            task_id="task_p23_t7",
            evaluation_decision=ED_REJECT,
            next_decision=ND_REJECT,
            reason="Candidate delta negative — rejected.",
            confidence="high",
            requires_human_review=False,
            allowed_next_task_family=None,
            gate_decision_id="gate_p23_t7",
            source="sandbox/test",
            delta=-0.003,
            sample_count=5,
        )

        latest = get_latest_patch_evaluation_gate_decision()
        assert latest is not None
        assert latest["next_decision"] == ND_REJECT
        assert latest["production_patch_allowed"] is False

        # Verify multiple records are kept in order
        record_patch_evaluation_gate_decision(
            task_id="task_p23_t7b",
            evaluation_decision=ED_MORE,
            next_decision=ND_REQUEST_MORE,
            reason="More data needed.",
            confidence="medium",
            requires_human_review=False,
            allowed_next_task_family=TF_CLV_QUALITY,
            source="sandbox/test",
            delta=None,
            sample_count=2,
        )
        latest2 = get_latest_patch_evaluation_gate_decision()
        assert latest2["task_id"] == "task_p23_t7b"
    finally:
        tm_module.MEMORY_PATH = orig


# ── Test 8: No external LLM called throughout full pipeline ──────────────────

def test_no_external_llm_called_during_gate_evaluation(tmp_path):
    """
    The full Phase 23 gate pipeline (evaluate + record) must not write to llm_usage.jsonl.
    """
    import orchestrator.llm_usage_logger as lul_module
    import orchestrator.training_memory as tm_module
    from orchestrator.training_memory import record_patch_evaluation_gate_decision

    llm_log = tmp_path / "llm_usage.jsonl"
    orig_log = lul_module._LOG_PATH
    orig_mem = tm_module.MEMORY_PATH
    lul_module._LOG_PATH = str(llm_log)
    tm_module.MEMORY_PATH = tmp_path / "training_memory.json"

    try:
        for ev_dec, sample, delta in [
            (ED_REJECT, 5, -0.001),
            (ED_MORE, 2, None),
            (ED_KEEP, 20, 0.003),
            (ED_KEEP, 60, 0.012),
        ]:
            ev = _make_eval(
                evaluation_decision=ev_dec,
                sample_count=sample,
                delta=delta,
                task_id=f"task_p23_t8_{ev_dec[:4]}_{sample}",
            )
            gate_result = evaluate_patch_evaluation_gate(ev)
            record_patch_evaluation_gate_decision(
                task_id=ev["task_id"],
                evaluation_decision=ev_dec,
                next_decision=gate_result["next_decision"],
                reason=gate_result["reason"],
                confidence=gate_result["confidence"],
                requires_human_review=gate_result["requires_human_review"],
                allowed_next_task_family=gate_result["allowed_next_task_family"],
                source=ev["source"],
                delta=delta,
                sample_count=sample,
            )

        assert not llm_log.exists(), (
            "LLM usage log created — LLM calls are forbidden in Phase 23 gate: "
            + (llm_log.read_text()[:200] if llm_log.exists() else "")
        )
    finally:
        lul_module._LOG_PATH = orig_log
        tm_module.MEMORY_PATH = orig_mem


# ── Test 9: PROMOTE always requires human review ──────────────────────────────

def test_promote_always_requires_human_review():
    """
    Every path that produces PROMOTE_TO_PRODUCTION_PROPOSAL must set
    requires_human_review=True and production_patch_allowed=False.
    """
    # Sandbox source with sufficient evidence
    ev_sandbox = _make_eval(
        evaluation_decision=ED_KEEP,
        sample_count=_PROMOTE_MIN_SANDBOX,
        delta=_MATERIAL_DELTA_THRESHOLD + 0.010,
        source="sandbox/test",
    )
    result_sb = evaluate_patch_evaluation_gate(ev_sandbox)
    assert result_sb["next_decision"] == ND_PROMOTE
    assert result_sb["requires_human_review"] is True
    assert result_sb["production_patch_allowed"] is False

    # Production source with sufficient evidence
    ev_prod = _make_eval(
        evaluation_decision=ED_KEEP,
        sample_count=120,
        delta=0.015,
        source="production",
    )
    result_prod = evaluate_patch_evaluation_gate(ev_prod)
    if result_prod["next_decision"] == ND_PROMOTE:
        assert result_prod["requires_human_review"] is True
        assert result_prod["production_patch_allowed"] is False

    # Ensure the gate constant is never overridden
    for _ in range(10):
        ev = _make_eval(
            evaluation_decision=ED_KEEP,
            sample_count=_PROMOTE_MIN_SANDBOX + 10,
            delta=_MATERIAL_DELTA_THRESHOLD + 0.020,
            source="sandbox/test",
        )
        r = evaluate_patch_evaluation_gate(ev)
        if r["next_decision"] == ND_PROMOTE:
            assert r["requires_human_review"] is True, (
                "PROMOTE must ALWAYS require human review — found requires_human_review=False"
            )
            assert r["production_patch_allowed"] is False
