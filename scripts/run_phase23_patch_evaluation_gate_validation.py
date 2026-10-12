#!/usr/bin/env python3
"""
scripts/run_phase23_patch_evaluation_gate_validation.py
=======================================================
Phase 23 — Sandbox Patch Evaluation Decision Gate 驗證腳本。

執行 7 個步驟，每步驗證一條關鍵行為，最終輸出:
  PHASE_23_PATCH_EVALUATION_DECISION_GATE_VERIFIED

使用方式:
  python scripts/run_phase23_patch_evaluation_gate_validation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 確保 project root 在 sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

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
    _MATERIAL_DELTA_THRESHOLD,
    _PROMOTE_MIN_SANDBOX,
    evaluate_patch_evaluation_gate,
)

PASS = "✅ PASS"
FAIL = "❌ FAIL"

def _check(label: str, cond: bool, detail: str = "") -> bool:
    status = PASS if cond else FAIL
    suffix = f"  ({detail})" if detail else ""
    print(f"  {status}: {label}{suffix}")
    return cond


def step1_reject_creates_reject_decision() -> bool:
    print("\n[Step 1] REJECT_SANDBOX_CANDIDATE → REJECT decision, no task")
    ev = {"evaluation_decision": ED_REJECT, "sample_count": 5, "delta": -0.003,
          "source": "sandbox/test", "task_id": "p23_s1", "gate_decision_id": "g23_s1"}
    result = evaluate_patch_evaluation_gate(ev)
    ok = True
    ok &= _check("next_decision == REJECT", result["next_decision"] == ND_REJECT,
                 result["next_decision"])
    ok &= _check("allowed_next_task_family is None", result["allowed_next_task_family"] is None)
    ok &= _check("production_patch_allowed is False", result["production_patch_allowed"] is False)
    ok &= _check("requires_human_review is False", result["requires_human_review"] is False)
    return ok


def step2_need_more_data_creates_request_more() -> bool:
    print("\n[Step 2] NEED_MORE_DATA → REQUEST_MORE_DATA, clv-quality-analysis")
    ev = {"evaluation_decision": ED_MORE, "sample_count": 2, "delta": None,
          "source": "sandbox/test", "task_id": "p23_s2", "gate_decision_id": "g23_s2"}
    result = evaluate_patch_evaluation_gate(ev)
    ok = True
    ok &= _check("next_decision == REQUEST_MORE_DATA", result["next_decision"] == ND_REQUEST_MORE,
                 result["next_decision"])
    ok &= _check("allowed_next_task_family == clv-quality-analysis",
                 result["allowed_next_task_family"] == TF_CLV_QUALITY,
                 str(result["allowed_next_task_family"]))
    ok &= _check("production_patch_allowed is False", result["production_patch_allowed"] is False)
    return ok


def step3_keep_small_sample_human_review() -> bool:
    print(f"\n[Step 3] KEEP + sample_count < {_PROMOTE_MIN_SANDBOX} → HUMAN_REVIEW_REQUIRED")
    ev = {"evaluation_decision": ED_KEEP, "sample_count": 25,
          "delta": _MATERIAL_DELTA_THRESHOLD + 0.002,
          "source": "sandbox/test", "task_id": "p23_s3", "gate_decision_id": "g23_s3"}
    result = evaluate_patch_evaluation_gate(ev)
    ok = True
    ok &= _check("next_decision == HUMAN_REVIEW_REQUIRED",
                 result["next_decision"] == ND_HUMAN_REVIEW, result["next_decision"])
    ok &= _check("requires_human_review is True", result["requires_human_review"] is True)
    ok &= _check("production_patch_allowed is False", result["production_patch_allowed"] is False)
    return ok


def step4_keep_large_sample_promotes() -> bool:
    print(f"\n[Step 4] KEEP + sample_count >= {_PROMOTE_MIN_SANDBOX} + material delta → PROMOTE + human review")
    ev = {"evaluation_decision": ED_KEEP, "sample_count": _PROMOTE_MIN_SANDBOX,
          "delta": _MATERIAL_DELTA_THRESHOLD + 0.005,
          "source": "sandbox/test", "task_id": "p23_s4", "gate_decision_id": "g23_s4"}
    result = evaluate_patch_evaluation_gate(ev)
    ok = True
    ok &= _check("next_decision == PROMOTE_TO_PRODUCTION_PROPOSAL",
                 result["next_decision"] == ND_PROMOTE, result["next_decision"])
    ok &= _check("requires_human_review is True", result["requires_human_review"] is True)
    ok &= _check("allowed_next_task_family == production-proposal",
                 result["allowed_next_task_family"] == TF_PRODUCTION_PROPOSAL,
                 str(result["allowed_next_task_family"]))
    ok &= _check("production_patch_allowed is False", result["production_patch_allowed"] is False)
    return ok


def step5_sandbox_hard_rule_never_auto_patches() -> bool:
    print("\n[Step 5] Sandbox hard rule — production_patch_allowed ALWAYS False")
    cases = [
        (ED_KEEP, 200, 0.050, "sandbox/test"),
        (ED_KEEP, 200, 0.050, "sandbox"),
        (ED_REJECT, 5, -0.002, "sandbox/test"),
        (ED_MORE, 2, None, "sandbox"),
        (ED_KEEP, 10, 0.001, "sandbox/test"),
    ]
    ok = True
    for ev_dec, sample, delta, source in cases:
        ev = {"evaluation_decision": ev_dec, "sample_count": sample,
              "delta": delta, "source": source,
              "task_id": f"p23_s5_{ev_dec[:4]}", "gate_decision_id": "g23_s5"}
        result = evaluate_patch_evaluation_gate(ev)
        ok &= _check(
            f"production_patch_allowed=False (ev_dec={ev_dec!r}, sample={sample}, source={source!r})",
            result["production_patch_allowed"] is False,
        )
        ok &= _check(
            f"production_model_modified=False (ev_dec={ev_dec!r})",
            result.get("production_model_modified") is False,
        )
        ok &= _check(
            f"external_llm_called=False (ev_dec={ev_dec!r})",
            result.get("external_llm_called") is False,
        )
    return ok


def step6_training_memory_records_and_retrieves() -> bool:
    print("\n[Step 6] Training memory records and retrieves gate decision")
    import tempfile
    import orchestrator.training_memory as tm_module
    from orchestrator.training_memory import (
        record_patch_evaluation_gate_decision,
        get_latest_patch_evaluation_gate_decision,
        get_patch_evaluation_gate_history,
    )

    orig = tm_module.MEMORY_PATH
    with tempfile.TemporaryDirectory() as td:
        tm_module.MEMORY_PATH = Path(td) / "training_memory.json"
        try:
            ev = {"evaluation_decision": ED_KEEP, "sample_count": 60, "delta": 0.012,
                  "source": "sandbox/test", "task_id": "p23_s6", "gate_decision_id": "g23_s6"}
            gate_result = evaluate_patch_evaluation_gate(ev)
            record_patch_evaluation_gate_decision(
                task_id="p23_s6",
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
            history = get_patch_evaluation_gate_history(n=10)
            ok = True
            ok &= _check("latest gate decision retrieved", latest is not None)
            ok &= _check("task_id matches", (latest or {}).get("task_id") == "p23_s6")
            ok &= _check("production_patch_allowed is False",
                         (latest or {}).get("production_patch_allowed") is False)
            ok &= _check("production_model_modified is False",
                         (latest or {}).get("production_model_modified") is False)
            ok &= _check("external_llm_called is False",
                         (latest or {}).get("external_llm_called") is False)
            ok &= _check("recorded_at present", "recorded_at" in (latest or {}))
            ok &= _check("history length >= 1", len(history) >= 1)
        finally:
            tm_module.MEMORY_PATH = orig
    return ok


def step7_no_llm_called_end_to_end() -> bool:
    print("\n[Step 7] No external LLM called end-to-end")
    import tempfile
    import orchestrator.training_memory as tm_module
    from orchestrator.training_memory import record_patch_evaluation_gate_decision

    ok = True
    with tempfile.TemporaryDirectory() as td:
        llm_log = Path(td) / "llm_usage.jsonl"
        orig_mem = tm_module.MEMORY_PATH
        tm_module.MEMORY_PATH = Path(td) / "training_memory.json"

        try:
            import orchestrator.llm_usage_logger as lul_module
            orig_log = getattr(lul_module, "_LOG_PATH", None)
            lul_module._LOG_PATH = str(llm_log)
        except ImportError:
            orig_log = None
            lul_module = None  # type: ignore

        try:
            for ev_dec, sample, delta in [
                (ED_REJECT, 5, -0.002),
                (ED_MORE, 3, None),
                (ED_KEEP, 30, 0.003),
                (ED_KEEP, 70, 0.020),
            ]:
                ev = {"evaluation_decision": ev_dec, "sample_count": sample, "delta": delta,
                      "source": "sandbox/test",
                      "task_id": f"p23_s7_{ev_dec[:4]}_{sample}",
                      "gate_decision_id": f"g23_s7_{sample}"}
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
            llm_called = llm_log.exists()
            ok &= _check("No LLM usage log created", not llm_called,
                         "LLM log found!" if llm_called else "clean")
        finally:
            tm_module.MEMORY_PATH = orig_mem
            if lul_module is not None and orig_log is not None:
                lul_module._LOG_PATH = orig_log

    return ok


def main() -> int:
    print("=" * 65)
    print("Phase 23 — Sandbox Patch Evaluation Decision Gate Validation")
    print("=" * 65)

    steps = [
        ("Step 1", step1_reject_creates_reject_decision),
        ("Step 2", step2_need_more_data_creates_request_more),
        ("Step 3", step3_keep_small_sample_human_review),
        ("Step 4", step4_keep_large_sample_promotes),
        ("Step 5", step5_sandbox_hard_rule_never_auto_patches),
        ("Step 6", step6_training_memory_records_and_retrieves),
        ("Step 7", step7_no_llm_called_end_to_end),
    ]

    results: list[tuple[str, bool]] = []
    for name, fn in steps:
        try:
            passed = fn()
        except Exception as exc:
            print(f"  {FAIL}: {name} raised exception — {exc}")
            passed = False
        results.append((name, passed))

    print("\n" + "=" * 65)
    passed_count = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"Results: {passed_count}/{total} steps passed")

    for name, ok in results:
        status = PASS if ok else FAIL
        print(f"  {status} {name}")

    print()
    if passed_count == total:
        print("PHASE_23_PATCH_EVALUATION_DECISION_GATE_VERIFIED")
        return 0
    else:
        print("PHASE_23 VALIDATION FAILED — see errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
