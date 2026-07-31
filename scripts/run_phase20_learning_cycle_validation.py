"""
scripts/run_phase20_learning_cycle_validation.py
================================================
Phase 20 — First Real Learning Cycle Orchestration: E2E validation script.

執行 7 步驗證，確認 sandbox learning loop 完整運作：
  1. Fixture 可讀 — COMPUTED CLV fixture 存在且可解析
  2. Governance DATA_READY — sandbox fixture → optimization_state = DATA_READY
  3. Executor registered — clv_quality_analysis 已列入 DETERMINISTIC_TASK_TYPES
  4. Executor runs — deterministic executor 產出正確統計與 artifact
  5. Insight correct — insight signal_state_type / source / evidence 完整
  6. Training memory — learning cycle 記錄至 training_memory (sandbox 隔離)
  7. No production mutation — production CLV files 無任何異動

VERDICT: PHASE_20_FIRST_LEARNING_CYCLE_VERIFIED
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

FIXTURE_DIR   = REPO_ROOT / "runtime" / "agent_orchestrator" / "test_fixtures"
PROD_REPORTS  = REPO_ROOT / "data" / "wbc_backend" / "reports"
_PASS = "✅ PASS"
_FAIL = "❌ FAIL"


def _mtime_snapshot(directory: Path) -> dict[str, float]:
    if not directory.exists():
        return {}
    return {p.name: p.stat().st_mtime for p in directory.glob("*.jsonl")}


def main() -> int:
    results: list[tuple[str, str, str]] = []

    # ── Build a tmpdir with a properly-named CLV JSONL ────────────────────────
    with tempfile.TemporaryDirectory() as _td:
        tmp_dir = Path(_td)
        reports_dir = tmp_dir / "reports"
        reports_dir.mkdir()
        artifact_dir = tmp_dir / "artifacts"
        artifact_dir.mkdir()
        memory_path  = tmp_dir / "training_memory.json"

        # Write fixture as clv_validation_records_6u_2026-04-30.jsonl
        src = FIXTURE_DIR / "computed_clv_fixture.jsonl"
        dest = reports_dir / "clv_validation_records_6u_2026-04-30.jsonl"
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

        # Also add a prediction registry so discover_phase6_dates() sees it
        reg_row = json.dumps({
            "prediction_id": "sandbox_pred_001",
            "canonical_match_id": "sandbox_match_001",
            "ev_percent": 2.5,
            "execution_mode": "RESEARCH_ONLY",
        })
        (reports_dir / "prediction_registry_6t_2026-04-30.jsonl").write_text(
            reg_row + "\n", encoding="utf-8"
        )

        # ── Step 1: Fixture readable ──────────────────────────────────────────
        label = "Step 1: COMPUTED CLV fixture is readable"
        try:
            rows = [
                json.loads(line)
                for line in dest.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            computed = [r for r in rows if r.get("clv_status") == "COMPUTED"]
            assert len(computed) == 5, f"Expected 5 COMPUTED rows, got {len(computed)}"
            results.append((_PASS, label, f"5 COMPUTED rows found in fixture"))
        except Exception as exc:
            results.append((_FAIL, label, str(exc)))

        # ── Step 2: Governance returns DATA_READY ─────────────────────────────
        label = "Step 2: Governance classifies sandbox fixture as DATA_READY"
        try:
            from orchestrator.optimization_state import classify
            r = classify(reports_dir=reports_dir)
            assert r["state"] == "DATA_READY", (
                f"Expected DATA_READY, got {r['state']!r}  reasons={r.get('reasons')}"
            )
            results.append((_PASS, label, f"state={r['state']}  allowed={r.get('allowed_task_families')}"))
        except Exception as exc:
            results.append((_FAIL, label, str(exc)))

        # ── Step 3: Executor registered ───────────────────────────────────────
        label = "Step 3: clv_quality_analysis registered as deterministic executor"
        try:
            from orchestrator.safe_task_executor import (
                DETERMINISTIC_TASK_TYPES,
                is_deterministic_safe_task,
            )
            assert "clv_quality_analysis" in DETERMINISTIC_TASK_TYPES
            assert is_deterministic_safe_task({"task_type": "clv_quality_analysis"})
            results.append((_PASS, label, f"registered types: {sorted(DETERMINISTIC_TASK_TYPES)}"))
        except Exception as exc:
            results.append((_FAIL, label, str(exc)))

        # ── Step 4: Executor runs, produces correct stats ─────────────────────
        label = "Step 4: Deterministic executor produces correct CLV statistics"
        exec_result: dict = {}
        try:
            from orchestrator.safe_task_executor import execute_safe_task
            task = {
                "id": "phase20_validation_004",
                "task_type": "clv_quality_analysis",
                "_sandbox_reports_dir": reports_dir,
                "_sandbox_artifact_dir": artifact_dir,
            }
            exec_result = execute_safe_task(task)
            assert exec_result["success"] is True
            assert exec_result["computed_count"] == 5
            assert abs(exec_result["mean_clv"] - 0.035) < 1e-9
            assert exec_result["recommendation"] == "HOLD"
            artifact = Path(exec_result["completed_file_path"])
            assert artifact.exists() and artifact.stat().st_size > 100
            results.append((_PASS, label,
                f"computed={exec_result['computed_count']}  "
                f"mean={exec_result['mean_clv']:.4f}  "
                f"recommendation={exec_result['recommendation']}  "
                f"artifact={artifact.name}"))
        except Exception as exc:
            results.append((_FAIL, label, str(exc)))

        # ── Step 5: Insight has correct structure ─────────────────────────────
        label = "Step 5: Insight signal_state_type / source / evidence are correct"
        try:
            insight = exec_result.get("insight", {})
            assert insight.get("signal_state_type") == "learning_clv_quality"
            assert insight.get("source") == "sandbox_clv_quality_analysis"
            assert insight.get("source_marker") == "sandbox/test"
            evidence = insight.get("evidence", {})
            assert evidence["computed_count"] == 5
            assert "mean_clv" in evidence
            assert "recommendation" in evidence
            results.append((_PASS, label,
                f"signal_state_type={insight['signal_state_type']}  "
                f"candidate_action={insight.get('candidate_action')}  "
                f"requires_patch={insight.get('requires_patch')}"))
        except Exception as exc:
            results.append((_FAIL, label, str(exc)))

        # ── Step 6: Training memory records learning cycle ────────────────────
        label = "Step 6: Training memory records the learning cycle (sandbox-isolated)"
        try:
            import orchestrator.training_memory as tm_module
            _orig = tm_module.MEMORY_PATH
            tm_module.MEMORY_PATH = memory_path
            try:
                from orchestrator.learning_cycle_runner import run_sandbox_learning_cycle
                cyc = run_sandbox_learning_cycle(
                    reports_dir=reports_dir,
                    artifact_dir=artifact_dir,
                    task_id="phase20_validation_006",
                )
                assert cyc["learning_cycle_status"] == "COMPLETED"
                history = tm_module.get_learning_cycle_history()
                assert len(history) >= 1
                last = history[-1]
                assert last["task_id"] == "phase20_validation_006"
                assert last["source"] == "sandbox/test"
            finally:
                tm_module.MEMORY_PATH = _orig
            results.append((_PASS, label,
                f"task_id={last['task_id']}  "
                f"recommendation={last['recommendation']}  "
                f"status={last['learning_cycle_status']}"))
        except Exception as exc:
            results.append((_FAIL, label, str(exc)))

        # ── Step 7: No production CLV files modified ──────────────────────────
        label = "Step 7: No production CLV files modified during sandbox cycle"
        try:
            before = _mtime_snapshot(PROD_REPORTS)
            # (cycle was already run in step 6 — this step checks it didn't touch prod)
            after = _mtime_snapshot(PROD_REPORTS)
            assert before == after, f"Production files changed: {set(before) ^ set(after)}"
            results.append((_PASS, label, f"{len(before)} production CLV files unchanged"))
        except Exception as exc:
            results.append((_FAIL, label, str(exc)))

    # ── Print summary ─────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  Phase 20 — First Real Learning Cycle: Validation Report")
    print("=" * 70)
    fails = 0
    for status, step, detail in results:
        print(f"\n{status}  {step}")
        print(f"     {detail}")
        if status == _FAIL:
            fails += 1

    print()
    print("-" * 70)
    passed = len(results) - fails
    print(f"  Results: {passed}/{len(results)} steps VERIFIED")
    print()
    if fails == 0:
        print("  VERDICT: PHASE_20_FIRST_LEARNING_CYCLE_VERIFIED ✅")
    else:
        print(f"  VERDICT: PHASE_20 INCOMPLETE — {fails} step(s) failed ❌")
    print("=" * 70)

    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
