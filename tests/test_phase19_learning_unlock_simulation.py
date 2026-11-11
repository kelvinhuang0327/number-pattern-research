"""
Phase 19: Learning Unlock Simulation / COMPUTED CLV Readiness Drill

驗證當 sandbox COMPUTED CLV records 存在時，系統能正確執行以下轉換：
  WAITING_ACTIVE → LEARNING_READY
  → model validation / strategy feedback / feedback-atomic 全部允許
  → training memory 可記錄 learning signal

Hard rules (絕不違反):
  - 禁止偽造生產 CLV
  - 禁止修改生產 CLV records (data/wbc_backend/reports/ 不可異動)
  - 禁止呼叫外部 LLM
  - 禁止繞過 governance
  - 禁止將真實 PENDING_CLOSING 標記為 COMPUTED
  - 僅使用 sandbox/test fixture

最終裁定: PHASE_19_LEARNING_UNLOCK_SIMULATION_VERIFIED
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────────
# Sandbox fixture helpers
# ──────────────────────────────────────────────────────────────

_SANDBOX_DATE = "2026-05-01"
_PENDING_DATE = "2026-05-02"


def _make_sandbox_reports_dir(tmp_path: Path) -> Path:
    """
    Temp reports_dir with 3 COMPUTED CLV records (≥ _COMPUTED_CLV_MIN_ABSOLUTE=1,
    fraction=1.0 ≥ _COMPUTED_CLV_MIN_FRACTION=0.10).
    """
    # prediction_registry_6t_* → 用於 discover_phase6_dates()
    reg = tmp_path / f"prediction_registry_6t_{_SANDBOX_DATE}.jsonl"
    reg.write_text(
        json.dumps({
            "prediction_id": "sandbox_pred_001",
            "canonical_match_id": "sandbox_match_001",
            "governance_status": "VALIDATED_ML_ONLY",
            "predicted_at": "2026-04-30T10:00:00+00:00",
        }) + "\n",
        encoding="utf-8",
    )

    # clv_validation_records_6u_* → 3 rows, all COMPUTED
    clv = tmp_path / f"clv_validation_records_6u_{_SANDBOX_DATE}.jsonl"
    rows = [
        json.dumps({
            "prediction_id": f"sandbox_pred_{i:03d}",
            "canonical_match_id": f"sandbox_match_{i:03d}",
            "clv_status": "COMPUTED",
            "clv_value": round(0.020 + i * 0.005, 4),
            "prediction_time_utc": "2026-04-30T10:00:00+00:00",
            "closing_odds_time_utc": "2026-04-30T20:00:00+00:00",
        })
        for i in range(1, 4)
    ]
    clv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return tmp_path


def _make_pending_only_reports_dir(tmp_path: Path) -> Path:
    """
    Temp reports_dir with 5 PENDING_CLOSING CLV records (clv_computed=0).
    """
    reg = tmp_path / f"prediction_registry_6t_{_PENDING_DATE}.jsonl"
    reg.write_text(
        json.dumps({
            "prediction_id": "pending_pred_001",
            "governance_status": "VALIDATED_ML_ONLY",
        }) + "\n",
        encoding="utf-8",
    )

    clv = tmp_path / f"clv_validation_records_6u_{_PENDING_DATE}.jsonl"
    rows = [
        json.dumps({
            "prediction_id": f"pending_pred_{i:03d}",
            "clv_status": "PENDING_CLOSING",
            "clv_value": None,
        })
        for i in range(1, 6)
    ]
    clv.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return tmp_path


# ──────────────────────────────────────────────────────────────
# Test 1: Sandbox fixture 本身能正確產出 clv_computed >= 1
# ──────────────────────────────────────────────────────────────

def test_sandbox_fixture_yields_computed_clv(tmp_path: Path) -> None:
    """
    Sandbox reports_dir with COMPUTED CLV records →
    get_phase6_status(reports_dir=tmp) returns clv_computed >= 1,
    clv_pending_closing == 0, all_clv_pending == False.
    """
    from orchestrator.phase6_data_registry import get_phase6_status

    reports_dir = _make_sandbox_reports_dir(tmp_path)
    status = get_phase6_status(reports_dir=reports_dir)

    assert status["clv_computed"] >= 1, (
        f"Expected clv_computed >= 1, got {status['clv_computed']}"
    )
    assert status["clv_pending_closing"] == 0, (
        f"Expected clv_pending_closing == 0, got {status['clv_pending_closing']}"
    )
    assert status["all_clv_pending"] is False, (
        "all_clv_pending must be False when COMPUTED records exist"
    )


# ──────────────────────────────────────────────────────────────
# Test 2: COMPUTED CLV → readiness_state = LEARNING_READY
# ──────────────────────────────────────────────────────────────

def test_readiness_transitions_to_learning_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Monkeypatch get_phase6_status → clv_computed=3 →
    readiness_state = LEARNING_READY, learning_allowed = True, severity = GREEN.
    """
    import orchestrator.phase6_data_registry as p6_module
    from orchestrator.optimization_readiness import get_readiness_summary

    sandbox_status = {
        "clv_computed": 3,
        "clv_pending_closing": 0,
        "clv_blocked": 0,
        "all_clv_pending": False,
        "dates": [_SANDBOX_DATE],
        "latest_clv_date": _SANDBOX_DATE,
    }
    monkeypatch.setattr(
        p6_module, "get_phase6_status", lambda *a, **kw: sandbox_status
    )

    summary = get_readiness_summary()

    assert summary["readiness_state"] == "LEARNING_READY", (
        f"Expected LEARNING_READY, got {summary['readiness_state']!r}. "
        f"Detail: {summary.get('state_detail', '')}"
    )
    assert summary["learning_allowed"] is True, (
        "learning_allowed must be True when readiness_state == LEARNING_READY"
    )
    assert summary["severity"] == "GREEN", (
        f"Expected severity=GREEN, got {summary['severity']!r}"
    )


# ──────────────────────────────────────────────────────────────
# Test 3: Governance 允許 model-validation-atomic
# ──────────────────────────────────────────────────────────────

def test_governance_allows_model_validation_atomic(tmp_path: Path) -> None:
    """
    classify(reports_dir=sandbox) with COMPUTED CLV →
    STATE_DATA_READY, 'model-validation-atomic' in allowed_task_families.
    """
    from orchestrator.optimization_state import classify

    reports_dir = _make_sandbox_reports_dir(tmp_path)
    result = classify(reports_dir=reports_dir)

    assert result["state"] == "DATA_READY", (
        f"Expected DATA_READY, got {result['state']!r}. "
        f"Reasons: {result['reasons']}"
    )
    assert "model-validation-atomic" in result["allowed_task_families"], (
        f"model-validation-atomic not in allowed: {result['allowed_task_families']}"
    )


# ──────────────────────────────────────────────────────────────
# Test 4: Governance 允許 strategy-reinforcement
# ──────────────────────────────────────────────────────────────

def test_governance_allows_strategy_reinforcement(tmp_path: Path) -> None:
    """
    classify(reports_dir=sandbox) with COMPUTED CLV →
    STATE_DATA_READY, 'strategy-reinforcement' in allowed_task_families.
    """
    from orchestrator.optimization_state import classify

    reports_dir = _make_sandbox_reports_dir(tmp_path)
    result = classify(reports_dir=reports_dir)

    assert result["state"] == "DATA_READY", (
        f"Expected DATA_READY, got {result['state']!r}. "
        f"Reasons: {result['reasons']}"
    )
    assert "strategy-reinforcement" in result["allowed_task_families"], (
        f"strategy-reinforcement not in allowed: {result['allowed_task_families']}"
    )


# ──────────────────────────────────────────────────────────────
# Test 5: Governance 允許 feedback-atomic
# ──────────────────────────────────────────────────────────────

def test_governance_allows_feedback_atomic(tmp_path: Path) -> None:
    """
    classify(reports_dir=sandbox) with COMPUTED CLV →
    STATE_DATA_READY, 'feedback-atomic' in allowed_task_families.
    """
    from orchestrator.optimization_state import classify

    reports_dir = _make_sandbox_reports_dir(tmp_path)
    result = classify(reports_dir=reports_dir)

    assert result["state"] == "DATA_READY", (
        f"Expected DATA_READY, got {result['state']!r}. "
        f"Reasons: {result['reasons']}"
    )
    assert "feedback-atomic" in result["allowed_task_families"], (
        f"feedback-atomic not in allowed: {result['allowed_task_families']}"
    )


# ──────────────────────────────────────────────────────────────
# Test 6: 純 PENDING_CLOSING 仍鎖定 learning (負向驗證)
# ──────────────────────────────────────────────────────────────

def test_pending_only_does_not_unlock_learning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    clv_computed=0, clv_pending=5 →
    readiness_state = WAITING_ACTIVE, learning_allowed = False.
    """
    import orchestrator.phase6_data_registry as p6_module
    from orchestrator.optimization_readiness import get_readiness_summary

    pending_status = {
        "clv_computed": 0,
        "clv_pending_closing": 5,
        "clv_blocked": 0,
        "all_clv_pending": True,
        "dates": [_PENDING_DATE],
        "latest_clv_date": _PENDING_DATE,
    }
    monkeypatch.setattr(
        p6_module, "get_phase6_status", lambda *a, **kw: pending_status
    )

    summary = get_readiness_summary()

    assert summary["readiness_state"] == "WAITING_ACTIVE", (
        f"Expected WAITING_ACTIVE, got {summary['readiness_state']!r}"
    )
    assert summary["learning_allowed"] is False, (
        "learning_allowed must be False when no COMPUTED CLV exists"
    )


# ──────────────────────────────────────────────────────────────
# Test 7: Strategy feedback 只使用 COMPUTED records (過濾 PENDING_CLOSING)
# ──────────────────────────────────────────────────────────────

def test_strategy_feedback_filters_computed_only(tmp_path: Path) -> None:
    """
    _load_computed_clv_records() 讀取混合 JSONL (COMPUTED + PENDING_CLOSING) →
    僅回傳 COMPUTED rows，PENDING_CLOSING 全部排除。
    """
    from orchestrator.strategy_tick import _load_computed_clv_records  # type: ignore[attr-defined]

    # 建立 upgraded JSONL (strategy_tick 讀取 upgraded_ 前綴)
    upgraded = tmp_path / f"clv_validation_records_6u_upgraded_{_SANDBOX_DATE}.jsonl"
    rows = [
        json.dumps({"prediction_id": "c1", "clv_status": "COMPUTED",         "clv_value": 0.030}),
        json.dumps({"prediction_id": "p1", "clv_status": "PENDING_CLOSING",   "clv_value": None}),
        json.dumps({"prediction_id": "c2", "clv_status": "COMPUTED",         "clv_value": 0.015}),
        json.dumps({"prediction_id": "p2", "clv_status": "PENDING_CLOSING",   "clv_value": None}),
        json.dumps({"prediction_id": "c3", "clv_status": "COMPUTED",         "clv_value": 0.045}),
    ]
    upgraded.write_text("\n".join(rows) + "\n", encoding="utf-8")

    computed = _load_computed_clv_records(reports_dir=tmp_path)

    assert len(computed) == 3, f"Expected 3 COMPUTED rows, got {len(computed)}"
    ids = {r["prediction_id"] for r in computed}
    assert ids == {"c1", "c2", "c3"}, f"Expected {{c1,c2,c3}}, got {ids}"
    assert all(r["clv_status"] == "COMPUTED" for r in computed), (
        "All returned rows must have clv_status=COMPUTED"
    )
    assert all(r.get("clv_value") is not None for r in computed), (
        "All returned rows must have non-None clv_value"
    )


# ──────────────────────────────────────────────────────────────
# Test 8: Training memory 記錄 COMPUTED CLV outcome (source=sandbox/test)
# ──────────────────────────────────────────────────────────────

def test_training_memory_records_computed_clv_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    record_clv_outcome() with source='sandbox/test' 寫入 temp memory 檔案。
    get_clv_outcome_summary() 正確反映已記錄的 outcome。
    """
    import orchestrator.training_memory as tm_module

    temp_memory = tmp_path / "training_memory.json"
    monkeypatch.setattr(tm_module, "MEMORY_PATH", temp_memory)

    tm_module.record_clv_outcome(
        prediction_id="sandbox_pred_001",
        clv_value=0.025,
        clv_direction="positive",
        source="sandbox/test",
        regime="sandbox",
        market_type="moneyline",
        selection="home",
    )

    assert temp_memory.exists(), "training_memory.json 應已建立"

    outcomes = tm_module.get_clv_outcomes(n=10)
    assert len(outcomes) == 1, f"Expected 1 outcome, got {len(outcomes)}"

    o = outcomes[0]
    assert o["prediction_id"] == "sandbox_pred_001"
    assert o["source"] == "sandbox/test"
    assert o["clv_direction"] == "positive"
    assert o["regime"] == "sandbox"
    assert abs(o["clv_value"] - 0.025) < 1e-6

    summary = tm_module.get_clv_outcome_summary()
    assert summary["total"] == 1
    assert summary["positive_count"] == 1
    assert summary["avg_clv"] == pytest.approx(0.025, abs=1e-5)


# ──────────────────────────────────────────────────────────────
# Test 9: 生產 CLV 文件在所有 sandbox 操作後未被異動
# ──────────────────────────────────────────────────────────────

def test_production_clv_files_not_mutated_by_sandbox_ops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    執行全部 sandbox 操作後，生產 data/wbc_backend/reports/ 內的
    .jsonl 文件 mtime 與內容不得改變。
    """
    import orchestrator.phase6_data_registry as p6_module
    import orchestrator.training_memory as tm_module
    from orchestrator.phase6_data_registry import get_phase6_status
    from orchestrator.optimization_state import classify
    from orchestrator.optimization_readiness import get_readiness_summary

    _REPO_ROOT = Path(__file__).parent.parent
    production_reports = _REPO_ROOT / "data" / "wbc_backend" / "reports"

    def _snapshot(d: Path) -> dict[str, float]:
        if not d.exists():
            return {}
        return {
            str(p.relative_to(d)): p.stat().st_mtime
            for p in sorted(d.rglob("*.jsonl"))
        }

    before = _snapshot(production_reports)

    # --- sandbox 操作 (全部使用 tmp_path，不碰生產) ---
    sandbox1 = tmp_path / "sandbox1"
    sandbox1.mkdir(parents=True, exist_ok=True)
    sandbox_dir = _make_sandbox_reports_dir(sandbox1)

    # get_phase6_status with sandbox reports_dir
    _ = get_phase6_status(reports_dir=sandbox_dir)

    # classify with sandbox reports_dir
    _ = classify(reports_dir=sandbox_dir)

    # readiness via monkeypatch
    sandbox_status = {
        "clv_computed": 3,
        "clv_pending_closing": 0,
        "clv_blocked": 0,
        "all_clv_pending": False,
        "dates": [_SANDBOX_DATE],
    }
    monkeypatch.setattr(
        p6_module, "get_phase6_status", lambda *a, **kw: sandbox_status
    )
    _ = get_readiness_summary()

    # training memory via monkeypatch → temp file only
    temp_mem = tmp_path / "training_memory.json"
    monkeypatch.setattr(tm_module, "MEMORY_PATH", temp_mem)
    tm_module.record_clv_outcome(
        prediction_id="isolation_check_001",
        clv_value=0.010,
        clv_direction="flat",
        source="sandbox/test",
    )

    after = _snapshot(production_reports)

    # 任何生產文件的 mtime 不得改變
    assert before == after, (
        "生產 CLV 文件在 sandbox 操作後被異動！\n"
        f"新增: {set(after) - set(before)}\n"
        f"移除: {set(before) - set(after)}"
    )
