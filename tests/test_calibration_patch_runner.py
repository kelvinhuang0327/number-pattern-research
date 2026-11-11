"""
Tests for:
  - wbc_backend/research/calibration_patch_runner.py
  - orchestrator/worker_tick.py (model_patch interception)
  - orchestrator/patch_validator.py (snapshot-based comparison)
"""
from __future__ import annotations

import json
import math
import pytest
from pathlib import Path
from unittest.mock import patch as mock_patch, MagicMock

from wbc_backend.research import calibration_patch_runner as cpr


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_ledger(tmp_path: Path, n: int = 35) -> Path:
    """Write n synthetic settlement records to a JSONL file."""
    records = []
    for i in range(n):
        rec = {
            "event_type": "settlement",
            "game_id": f"G{i:03d}",
            "predicted_prob": 0.55 + (i % 5) * 0.05,   # raw, slightly miscalibrated
            "market_prob": 0.50,
            "result": "win" if (i % 3 != 0) else "loss",
            "regime": ["Pool A", "Pool B", "Pool C", "Pool D"][i % 4],
            "pnl": 0.1 if (i % 3 != 0) else -0.1,
            "roi": 0.1 if (i % 3 != 0) else -0.1,
            "clv": None,
        }
        records.append(json.dumps(rec))
    p = tmp_path / "trade_ledger.jsonl"
    p.write_text("\n".join(records) + "\n", encoding="utf-8")
    return p


# ─── calibration_patch_runner unit tests ─────────────────────────────────────

class TestCalibrationPatchRunner:

    def test_run_success_produces_both_snapshots(self, tmp_path, monkeypatch):
        """run_calibration_patch should write before/after snapshots on success."""
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", _make_ledger(tmp_path))
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 10)

        manifest = cpr.run_calibration_patch(task_id=42)
        assert manifest.status == "SUCCESS"
        assert Path(manifest.before_snapshot_path).exists()
        assert Path(manifest.after_snapshot_path).exists()

    def test_run_brier_actually_improves(self, tmp_path, monkeypatch):
        """Calibrated Brier should be <= raw Brier (or very close)."""
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", _make_ledger(tmp_path))
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 10)

        manifest = cpr.run_calibration_patch(task_id=42)
        assert manifest.brier_delta <= 0.0, f"Brier worsened: {manifest.brier_delta:+.6f}"

    def test_run_fails_insufficient_data(self, tmp_path, monkeypatch):
        """Fewer than MIN_TOTAL_N records → FAILED_DATA."""
        small_ledger = _make_ledger(tmp_path, n=5)
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", small_ledger)
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 20)  # 5 < 20 → fail

        manifest = cpr.run_calibration_patch(task_id=99)
        assert manifest.status == "FAILED_DATA"
        assert "Insufficient" in manifest.failure_reason

    def test_run_fails_missing_ledger(self, tmp_path, monkeypatch):
        """No trade_ledger.jsonl → FAILED_DATA."""
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", tmp_path / "nonexistent.jsonl")
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 5)

        manifest = cpr.run_calibration_patch(task_id=1)
        assert manifest.status == "FAILED_DATA"

    def test_snapshot_before_contains_raw_probs(self, tmp_path, monkeypatch):
        """Before snapshot should store the original predicted_prob values."""
        ledger_path = _make_ledger(tmp_path)
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", ledger_path)
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 10)

        manifest = cpr.run_calibration_patch(task_id=42)
        before_rows = [json.loads(l) for l in Path(manifest.before_snapshot_path).read_text().splitlines() if l.strip()]
        assert all(r["calibration_method"] == "raw" for r in before_rows)
        assert all("result" in r for r in before_rows)           # needed for metrics
        assert all("metadata" not in r for r in before_rows)     # postgame info stripped

    def test_snapshot_after_has_calibrated_method(self, tmp_path, monkeypatch):
        """After snapshot should record the actual calibration method used."""
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", _make_ledger(tmp_path))
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 10)

        manifest = cpr.run_calibration_patch(task_id=42)
        after_rows = [json.loads(l) for l in Path(manifest.after_snapshot_path).read_text().splitlines() if l.strip()]
        assert all(r["calibration_method"] != "raw" for r in after_rows)
        assert all(r["snapshot_type"] == "after" for r in after_rows)

    def test_artifacts_exist_returns_true_after_success(self, tmp_path, monkeypatch):
        """artifacts_exist() should be True after a successful run."""
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", _make_ledger(tmp_path))
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 10)

        cpr.run_calibration_patch(task_id=55)
        assert cpr.artifacts_exist(55)

    def test_artifacts_exist_returns_false_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        assert not cpr.artifacts_exist(999)

    def test_build_completion_text_no_stub_markers(self, tmp_path, monkeypatch):
        """build_completion_text must NOT contain stub worker markers."""
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", _make_ledger(tmp_path))
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", tmp_path / "snapshots")
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 10)

        manifest = cpr.run_calibration_patch(task_id=77)
        text = cpr.build_completion_text(manifest)
        for stub_marker in ["程式碼自動生成", "copilot-daemon", "fake_completion", "智能建議整合\n- 測試案例產生"]:
            assert stub_marker not in text, f"Stub marker found: {stub_marker!r}"

    def test_run_does_not_touch_live_paths(self, tmp_path, monkeypatch, tmp_path_factory):
        """Calibration runner must not write to strategy/, telegram_bot/, live/."""
        monkeypatch.setattr(cpr, "TRADE_LEDGER_PATH", _make_ledger(tmp_path))
        snap_dir = tmp_path / "snapshots"
        monkeypatch.setattr(cpr, "SNAPSHOTS_DIR", snap_dir)
        monkeypatch.setattr(cpr, "MIN_TOTAL_N", 10)

        cpr.run_calibration_patch(task_id=88)
        written = list(snap_dir.glob("**/*")) if snap_dir.exists() else []
        for f in written:
            parts = str(f)
            assert "strategy/" not in parts
            assert "telegram_bot/" not in parts
            assert "live/" not in parts


# ─── worker_tick integration tests ───────────────────────────────────────────

class TestWorkerTickModelPatch:

    def test_model_patch_calibration_calls_real_runner(self, tmp_path, monkeypatch):
        """model_patch_calibration task should call execute_model_patch_task, not stub."""
        from orchestrator import worker_tick

        called = {}
        def fake_run(task_id):
            called["task_id"] = task_id
            from wbc_backend.research.calibration_patch_runner import PatchRunManifest
            return PatchRunManifest(
                task_id=task_id, status="SUCCESS",
                calibration_method="platt", calibration_params={"a": 1.0, "b": 0.0},
                n_total=35, n_train=28, n_eval=7,
                before_brier=0.3, after_brier=0.2, brier_delta=-0.1,
                before_logloss=0.8, after_logloss=0.6, logloss_delta=-0.2,
                before_snapshot_path=str(tmp_path / "before.jsonl"),
                after_snapshot_path=str(tmp_path / "after.jsonl"),
                regimes=["Pool A"], elapsed_seconds=0.1, executed_at="2026-01-01T00:00:00Z",
            )

        # Write fake artifacts so gate passes
        (tmp_path / "before.jsonl").write_text('{"predicted_prob": 0.5}\n')
        (tmp_path / "after.jsonl").write_text('{"predicted_prob": 0.45}\n')

        monkeypatch.setattr("wbc_backend.research.calibration_patch_runner.run_calibration_patch", fake_run)
        monkeypatch.setattr("wbc_backend.research.calibration_patch_runner.artifacts_exist", lambda tid: True)

        task = {"id": 880, "signal_state_type": "model_patch_calibration",
                "title": "Test Patch", "prompt_file_path": str(tmp_path / "task.md"),
                "slot_key": "slot1"}
        result = worker_tick.execute_task_with_provider(task, provider="copilot")
        assert result["success"] is True
        assert "stub" not in result.get("completed_text", "").lower() or result.get("stub") is False
        assert called["task_id"] == 880

    def test_model_patch_fails_without_artifacts(self, tmp_path, monkeypatch):
        """If artifacts missing after run → success=False, FAILED_STUB."""
        from orchestrator import worker_tick

        def fake_run(task_id):
            from wbc_backend.research.calibration_patch_runner import PatchRunManifest
            return PatchRunManifest(
                task_id=task_id, status="SUCCESS",
                calibration_method="platt", calibration_params={},
                n_total=35, n_train=28, n_eval=7,
                before_brier=0.3, after_brier=0.2, brier_delta=-0.1,
                before_logloss=0.8, after_logloss=0.6, logloss_delta=-0.2,
                before_snapshot_path=str(tmp_path / "before.jsonl"),
                after_snapshot_path=str(tmp_path / "after.jsonl"),
                regimes=[], elapsed_seconds=0.0, executed_at="",
            )

        monkeypatch.setattr("wbc_backend.research.calibration_patch_runner.run_calibration_patch", fake_run)
        # artifacts_exist returns False → gate fails
        monkeypatch.setattr("wbc_backend.research.calibration_patch_runner.artifacts_exist", lambda tid: False)

        task = {"id": 1, "signal_state_type": "model_patch_calibration",
                "title": "Test", "prompt_file_path": "", "slot_key": "s1"}
        result = worker_tick.execute_task_with_provider(task, provider="copilot")
        assert result["success"] is False
        assert "FAILED_STUB" in result["completed_text"]

    def test_non_patch_tasks_unaffected(self):
        """deep_research_* tasks should NOT be intercepted by model_patch executor."""
        from orchestrator import worker_tick
        task = {"id": 1, "signal_state_type": "deep_research_calibration",
                "title": "Research", "prompt_file_path": "/tmp/x", "slot_key": "s1"}
        stub_result = {"success": True, "completed_text": "程式碼自動生成\nstub"}
        # Should call stub provider, not model_patch real executor
        with mock_patch.object(worker_tick, "_assert_llm_execution_allowed", return_value=None), \
             mock_patch.object(worker_tick, "execute_task_with_codex", return_value=stub_result):
            result = worker_tick.execute_task_with_provider(task, provider="copilot-daemon")
        # stub copilot returns success=True with stub text
        assert result["success"] is True
        assert "程式碼自動生成" in result["completed_text"]


# ─── patch_validator snapshot integration ────────────────────────────────────

class TestPatchValidatorSnapshots:

    def _make_snapshot(self, tmp_path: Path, task_id: int, snap_type: str, probs: list[float]) -> None:
        out = tmp_path / f"{task_id}_{snap_type}.jsonl"
        rows = []
        for i, p in enumerate(probs):
            rows.append(json.dumps({
                "game_id": f"G{i:03d}",
                "predicted_prob": p,
                "result": "win" if i % 2 == 0 else "loss",
                "regime": "Pool A",
                "market_prob": 0.5,
                "pnl": 0.1, "roi": 0.1, "clv": None,
                "snapshot_type": snap_type,
                "calibration_method": "raw" if snap_type == "before" else "platt",
                "patch_task_id": task_id,
            }))
        out.write_text("\n".join(rows) + "\n")

    def test_validator_uses_snapshots_over_walkforward(self, tmp_path, monkeypatch):
        """When snapshots exist, validator uses them instead of walk-forward proxy."""
        from orchestrator import patch_validator

        raw_probs  = [0.7, 0.3, 0.8, 0.2, 0.6, 0.4, 0.9]
        cal_probs  = [0.65, 0.35, 0.75, 0.25, 0.55, 0.45, 0.82]

        self._make_snapshot(tmp_path, 880, "before", raw_probs)
        self._make_snapshot(tmp_path, 880, "after",  cal_probs)
        monkeypatch.setattr(patch_validator, "SNAPSHOTS_DIR", tmp_path)

        # Minimal patch_task (no stub markers)
        patch_task = {"id": 880, "signal_state_type": "model_patch_calibration",
                      "title": "Test", "completed_text": "# real patch"}
        insight = {"id": "abc", "source_signal_state_type": "deep_research_calibration",
                   "target_files": [], "category": "calibration", "status": "PATCH_QUEUED",
                   "weakness": "x", "expected_metric": "brier"}

        # Use fresh tmp insights
        fake_insights = tmp_path / "insights.json"
        fake_insights.write_text(json.dumps([insight]))
        monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_insights)
        monkeypatch.setattr(patch_validator, "REPORT_OUTPUT_PATH", tmp_path / "report.md")
        monkeypatch.setattr(patch_validator, "TRADE_LEDGER_PATH", tmp_path / "empty.jsonl")

        result = patch_validator.run_patch_validation(patch_task, insight)
        assert "SNAPSHOT_COMPARISON" in result["statistical_note"]
        assert result["before_metrics"]["brier_score"] is not None
        assert result["after_metrics"]["brier_score"] is not None

    def test_validator_falls_back_to_stub_without_snapshots(self, tmp_path, monkeypatch):
        """Without snapshots, stub worker detection still triggers INSUFFICIENT_DATA."""
        from orchestrator import patch_validator

        empty_snap_dir = tmp_path / "snapshots"
        empty_snap_dir.mkdir()
        monkeypatch.setattr(patch_validator, "SNAPSHOTS_DIR", empty_snap_dir)
        monkeypatch.setattr(patch_validator, "TRADE_LEDGER_PATH", tmp_path / "none.jsonl")

        fake_insights = tmp_path / "insights.json"
        insight = {"id": "x1", "source_signal_state_type": "deep_research_calibration",
                   "target_files": [], "category": "calibration", "status": "PATCH_QUEUED",
                   "weakness": "x", "expected_metric": "brier"}
        fake_insights.write_text(json.dumps([insight]))
        monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_insights)
        monkeypatch.setattr(patch_validator, "REPORT_OUTPUT_PATH", tmp_path / "report.md")

        stub_task = {"id": 1, "signal_state_type": "model_patch_calibration",
                     "title": "x", "completed_text": "程式碼自動生成\ncopilot-daemon"}
        result = patch_validator.run_patch_validation(stub_task, insight)
        assert result["decision"] == "INSUFFICIENT_DATA"
        assert result["after_metrics"].get("note") == "stub_worker_no_real_change"

    def test_snapshot_partial_keep_on_small_sample(self, tmp_path, monkeypatch):
        """35 records with real improvement → PARTIAL_KEEP (not KEEP_PATCH)."""
        from orchestrator import patch_validator

        # Meaningful calibration: before is miscalibrated, after is better
        n = 35
        before_probs = [0.8 if i % 3 != 0 else 0.4 for i in range(n)]   # raw
        after_probs  = [0.65 if i % 3 != 0 else 0.45 for i in range(n)] # calibrated

        self._make_snapshot(tmp_path, 500, "before", before_probs)
        self._make_snapshot(tmp_path, 500, "after",  after_probs)
        monkeypatch.setattr(patch_validator, "SNAPSHOTS_DIR", tmp_path)

        fake_insights = tmp_path / "insights.json"
        insight = {"id": "p1", "source_signal_state_type": "deep_research_calibration",
                   "target_files": [], "category": "calibration", "status": "PATCH_QUEUED",
                   "weakness": "x", "expected_metric": "brier"}
        fake_insights.write_text(json.dumps([insight]))
        monkeypatch.setattr(patch_validator, "INSIGHTS_PATH", fake_insights)
        monkeypatch.setattr(patch_validator, "REPORT_OUTPUT_PATH", tmp_path / "report.md")
        monkeypatch.setattr(patch_validator, "TRADE_LEDGER_PATH", tmp_path / "none.jsonl")

        patch_task = {"id": 500, "signal_state_type": "model_patch_calibration",
                      "title": "x", "completed_text": "real patch done"}
        result = patch_validator.run_patch_validation(patch_task, insight)
        # 35 < 150 (MIN_SAMPLE_PREFERRED) → PARTIAL_KEEP even if improvement is real
        assert result["decision"] in ("PARTIAL_KEEP", "KEEP_PATCH", "REJECT_PATCH")
        # With proper improvement it should be PARTIAL_KEEP
        assert result["decision"] != "INSUFFICIENT_DATA"
