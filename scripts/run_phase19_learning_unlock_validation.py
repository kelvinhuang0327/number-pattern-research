"""
Phase 19 E2E Validation Script: Learning Unlock Simulation / COMPUTED CLV Readiness Drill

驗證 Pipeline:
  1. Sandbox COMPUTED CLV fixture 有效 (get_phase6_status 可讀取)
  2. COMPUTED CLV → WAITING_ACTIVE 轉換為 LEARNING_READY
  3. Governance 允許 model-validation-atomic, strategy-reinforcement, feedback-atomic
  4. PENDING_CLOSING 無法解鎖 learning (負向驗證)
  5. Strategy feedback 濾掉 PENDING_CLOSING，僅使用 COMPUTED
  6. Training memory 能以 source=sandbox/test 記錄 CLV outcome
  7. 生產 CLV 文件未被異動

最終裁定: PHASE_19_LEARNING_UNLOCK_SIMULATION_VERIFIED
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# ──────────────────────────────────────────────────────────────
# ANSI colours
# ──────────────────────────────────────────────────────────────

_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"

_SANDBOX_DATE = "2026-05-01"
_PENDING_DATE = "2026-05-02"


def _ok(msg: str) -> None:
    print(f"  {_GREEN}✓{_RESET} {msg}")


def _fail(msg: str) -> None:
    print(f"  {_RED}✗{_RESET} {msg}")


def _section(title: str) -> None:
    print(f"\n{_BOLD}[{title}]{_RESET}")


# ──────────────────────────────────────────────────────────────
# Helpers (sandbox fixture builders)
# ──────────────────────────────────────────────────────────────

def _make_sandbox_reports_dir(d: Path) -> Path:
    """3 COMPUTED CLV records in a temp reports_dir."""
    d.mkdir(parents=True, exist_ok=True)

    reg = d / f"prediction_registry_6t_{_SANDBOX_DATE}.jsonl"
    reg.write_text(
        json.dumps({
            "prediction_id": "sandbox_pred_001",
            "governance_status": "VALIDATED_ML_ONLY",
        }) + "\n",
        encoding="utf-8",
    )

    clv = d / f"clv_validation_records_6u_{_SANDBOX_DATE}.jsonl"
    rows = [
        json.dumps({
            "prediction_id": f"sandbox_pred_{i:03d}",
            "clv_status": "COMPUTED",
            "clv_value": round(0.020 + i * 0.005, 4),
            "prediction_time_utc": "2026-04-30T10:00:00+00:00",
            "closing_odds_time_utc": "2026-04-30T20:00:00+00:00",
        })
        for i in range(1, 4)
    ]
    clv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return d


def _make_upgraded_dir(d: Path) -> Path:
    """Mixed upgraded JSONL (COMPUTED + PENDING) for strategy_tick test."""
    d.mkdir(parents=True, exist_ok=True)
    upgraded = d / f"clv_validation_records_6u_upgraded_{_SANDBOX_DATE}.jsonl"
    rows = [
        json.dumps({"prediction_id": "c1", "clv_status": "COMPUTED",       "clv_value": 0.030}),
        json.dumps({"prediction_id": "p1", "clv_status": "PENDING_CLOSING", "clv_value": None}),
        json.dumps({"prediction_id": "c2", "clv_status": "COMPUTED",       "clv_value": 0.015}),
    ]
    upgraded.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return d


# ──────────────────────────────────────────────────────────────
# Validation steps
# ──────────────────────────────────────────────────────────────

def _check_sandbox_fixture(sandbox_dir: Path) -> bool:
    """Step 1: sandbox fixture → get_phase6_status returns clv_computed >= 1."""
    _section("Step 1: Sandbox Fixture Validity")
    from orchestrator.phase6_data_registry import get_phase6_status

    status = get_phase6_status(reports_dir=sandbox_dir)
    computed = status.get("clv_computed", 0)
    pending  = status.get("clv_pending_closing", 0)
    all_pend = status.get("all_clv_pending", True)

    if computed >= 1 and pending == 0 and all_pend is False:
        _ok(f"get_phase6_status → clv_computed={computed}, all_clv_pending=False")
        return True
    _fail(f"Fixture invalid: clv_computed={computed}, clv_pending={pending}, all_clv_pending={all_pend}")
    return False


def _check_learning_ready_transition(sandbox_status: dict) -> bool:
    """Step 2: COMPUTED CLV → readiness_state = LEARNING_READY."""
    _section("Step 2: WAITING_ACTIVE → LEARNING_READY Transition")
    import unittest.mock as mock
    import orchestrator.phase6_data_registry as p6_module
    from orchestrator.optimization_readiness import get_readiness_summary

    with mock.patch.object(p6_module, "get_phase6_status", return_value=sandbox_status):
        summary = get_readiness_summary()

    state   = summary.get("readiness_state", "?")
    allowed = summary.get("learning_allowed", False)
    sev     = summary.get("severity", "?")

    ok = (state == "LEARNING_READY" and allowed is True and sev == "GREEN")
    if ok:
        _ok(f"readiness_state={state}, learning_allowed={allowed}, severity={sev}")
    else:
        _fail(f"readiness_state={state}, learning_allowed={allowed}, severity={sev}")
    return ok


def _check_governance_unlock(sandbox_dir: Path) -> bool:
    """Step 3: classify(reports_dir=sandbox) → DATA_READY + learning families allowed."""
    _section("Step 3: Governance Unlock (model-validation, strategy-reinforcement, feedback)")
    from orchestrator.optimization_state import classify

    result  = classify(reports_dir=sandbox_dir)
    state   = result.get("state", "?")
    allowed = result.get("allowed_task_families", [])

    targets = ["model-validation-atomic", "strategy-reinforcement", "feedback-atomic"]
    all_ok  = (state == "DATA_READY") and all(t in allowed for t in targets)

    if state == "DATA_READY":
        _ok(f"classify() → state=DATA_READY")
    else:
        _fail(f"classify() → state={state} (reasons: {result.get('reasons', [])})")

    for t in targets:
        if t in allowed:
            _ok(f"  allowed: {t}")
        else:
            _fail(f"  NOT allowed: {t}")

    return all_ok


def _check_pending_blocks_learning() -> bool:
    """Step 4: clv_computed=0 → readiness_state = WAITING_ACTIVE."""
    _section("Step 4: Pending-Only Does NOT Unlock Learning (negative check)")
    import unittest.mock as mock
    import orchestrator.phase6_data_registry as p6_module
    from orchestrator.optimization_readiness import get_readiness_summary

    pending_status = {
        "clv_computed": 0,
        "clv_pending_closing": 5,
        "clv_blocked": 0,
        "all_clv_pending": True,
        "dates": [_PENDING_DATE],
    }
    with mock.patch.object(p6_module, "get_phase6_status", return_value=pending_status):
        summary = get_readiness_summary()

    state   = summary.get("readiness_state", "?")
    allowed = summary.get("learning_allowed", True)

    ok = (state == "WAITING_ACTIVE" and allowed is False)
    if ok:
        _ok(f"readiness_state={state}, learning_allowed={allowed}")
    else:
        _fail(f"readiness_state={state}, learning_allowed={allowed}")
    return ok


def _check_strategy_feedback_filters_computed(upgraded_dir: Path) -> bool:
    """Step 5: _load_computed_clv_records() returns only COMPUTED rows."""
    _section("Step 5: Strategy Feedback Filters COMPUTED Only")
    from orchestrator.strategy_tick import _load_computed_clv_records  # type: ignore[attr-defined]

    rows = _load_computed_clv_records(reports_dir=upgraded_dir)
    computed_ids = {r["prediction_id"] for r in rows}
    pending_leaked = any(r.get("clv_status") != "COMPUTED" for r in rows)

    if len(rows) == 2 and computed_ids == {"c1", "c2"} and not pending_leaked:
        _ok(f"_load_computed_clv_records → {len(rows)} COMPUTED rows, no PENDING leaked")
        return True
    _fail(f"rows={len(rows)}, ids={computed_ids}, pending_leaked={pending_leaked}")
    return False


def _check_training_memory(mem_path: Path) -> bool:
    """Step 6: Training memory records COMPUTED CLV outcome with source=sandbox/test."""
    _section("Step 6: Training Memory Records COMPUTED CLV Outcome")
    import unittest.mock as mock
    import orchestrator.training_memory as tm_module

    with mock.patch.object(tm_module, "MEMORY_PATH", mem_path):
        tm_module.record_clv_outcome(
            prediction_id="phase19_validation_001",
            clv_value=0.030,
            clv_direction="positive",
            source="sandbox/test",
            regime="sandbox",
        )
        outcomes = tm_module.get_clv_outcomes(n=10)
        summary  = tm_module.get_clv_outcome_summary()

    ok = (
        len(outcomes) >= 1
        and outcomes[-1]["source"] == "sandbox/test"
        and summary["total"] >= 1
        and summary["avg_clv"] is not None
    )
    if ok:
        _ok(f"outcome recorded: source={outcomes[-1]['source']}, avg_clv={summary['avg_clv']:.4f}")
    else:
        _fail(f"outcomes={len(outcomes)}, summary={summary}")
    return ok


def _check_production_not_mutated(sandbox_dir: Path, mem_path: Path) -> bool:
    """Step 7: Production CLV files unchanged after all sandbox ops."""
    _section("Step 7: Production CLV Files Not Mutated")
    import unittest.mock as mock
    import orchestrator.phase6_data_registry as p6_module
    import orchestrator.training_memory as tm_module
    from orchestrator.phase6_data_registry import get_phase6_status
    from orchestrator.optimization_state import classify
    from orchestrator.optimization_readiness import get_readiness_summary

    production_reports = _REPO_ROOT / "data" / "wbc_backend" / "reports"

    def _snapshot(d: Path) -> dict[str, float]:
        if not d.exists():
            return {}
        return {
            str(p.relative_to(d)): p.stat().st_mtime
            for p in sorted(d.rglob("*.jsonl"))
        }

    before = _snapshot(production_reports)

    # All sandbox ops
    _ = get_phase6_status(reports_dir=sandbox_dir)
    _ = classify(reports_dir=sandbox_dir)
    s = {"clv_computed": 3, "clv_pending_closing": 0, "clv_blocked": 0,
         "all_clv_pending": False, "dates": [_SANDBOX_DATE]}
    with mock.patch.object(p6_module, "get_phase6_status", return_value=s):
        _ = get_readiness_summary()
    with mock.patch.object(tm_module, "MEMORY_PATH", mem_path):
        tm_module.record_clv_outcome(
            prediction_id="isolation_probe_001",
            clv_value=0.005,
            clv_direction="flat",
            source="sandbox/test",
        )

    after = _snapshot(production_reports)

    if before == after:
        _ok(f"Production files unchanged ({len(before)} JSONL tracked)")
        return True
    new_files = set(after) - set(before)
    _fail(f"Production files mutated! new={new_files}")
    return False


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def run_validation() -> int:
    """
    Run Phase 19 validation pipeline.
    Returns 0 if VERIFIED, 1 if any step fails.
    """
    print(f"\n{_BOLD}{'='*65}{_RESET}")
    print(f"{_BOLD}  Phase 19: Learning Unlock Simulation{_RESET}")
    print(f"{_BOLD}{'='*65}{_RESET}")

    with tempfile.TemporaryDirectory() as tmpdir:
        base         = Path(tmpdir)
        sandbox_dir  = _make_sandbox_reports_dir(base / "sandbox")
        upgraded_dir = _make_upgraded_dir(base / "upgraded")
        mem_path     = base / "training_memory.json"

        sandbox_status = {
            "clv_computed": 3,
            "clv_pending_closing": 0,
            "clv_blocked": 0,
            "all_clv_pending": False,
            "dates": [_SANDBOX_DATE],
            "latest_clv_date": _SANDBOX_DATE,
        }

        results = [
            _check_sandbox_fixture(sandbox_dir),
            _check_learning_ready_transition(sandbox_status),
            _check_governance_unlock(sandbox_dir),
            _check_pending_blocks_learning(),
            _check_strategy_feedback_filters_computed(upgraded_dir),
            _check_training_memory(mem_path),
            _check_production_not_mutated(sandbox_dir, mem_path),
        ]

    passed = sum(results)
    total  = len(results)
    failed = total - passed

    print(f"\n{_BOLD}{'='*65}{_RESET}")
    if failed == 0:
        verdict = "PHASE_19_LEARNING_UNLOCK_SIMULATION_VERIFIED"
        print(f"{_GREEN}{_BOLD}  ✅ VERDICT: {verdict}{_RESET}")
        rc = 0
    else:
        verdict = "PHASE_19_LEARNING_UNLOCK_SIMULATION_FAILED"
        print(f"{_RED}{_BOLD}  ❌ VERDICT: {verdict}{_RESET}")
        print(f"{_RED}  {failed}/{total} steps failed{_RESET}")
        rc = 1
    print(f"{_BOLD}{'='*65}{_RESET}\n")
    return rc


if __name__ == "__main__":
    sys.exit(run_validation())
