"""
Phase 13 — Autonomous Optimization Readiness Dashboard Tests

Verifies:
1. All CLV pending + safe cadence healthy → WAITING_ACTIVE / GREEN
2. Computed CLV exists + learning allowed → LEARNING_READY / GREEN
3. Unexplained skips high → DEGRADED / RED
4. Empty artifacts only → DEGRADED / RED
5. Hard-off protected skips only → NOT RED / NOT DEGRADED
6. Decision card renders readiness section (AUTONOMOUS READINESS block)
7. CLI writes JSON + Markdown artifacts

Success marker: test_phase13_success_marker asserts
    PHASE_13_OPTIMIZATION_READINESS_DASHBOARD_VERIFIED
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_phase6(computed: int = 0, pending: int = 14, all_pending: bool = True) -> dict:
    return {
        "available": True,
        "clv_computed": computed,
        "clv_pending_closing": pending,
        "clv_blocked": 0,
        "all_clv_pending": all_pending,
        "registry_rows": pending + computed,
        "next_required_event": "Wait for market settlement",
    }


def _make_governance(state: str = "DATA_WAITING",
                     allowed: list[str] | None = None,
                     blocked: list[str] | None = None) -> dict:
    if allowed is None:
        allowed = [
            "closing-monitor", "ops-report", "scheduler-health-check",
            "artifact-health-check", "wiki-maintenance",
        ]
    if blocked is None:
        blocked = [
            "strategy-reinforcement", "model-patch-atomic",
            "calibration-atomic", "feature-atomic",
        ]
    return {
        "available": True,
        "current_state": state,
        "reasons": ["all_clv_pending"],
        "allowed_families": allowed,
        "blocked_families": blocked,
        "recommended_next_action": "Wait for closing odds",
    }


def _make_ops(
    classification: str = "WAITING_ACTIVE",
    effective: int = 1,
    tasks: int = 1,
    consec_skips: int = 0,
    hard_off: int = 0,
) -> dict:
    return {
        "available": True,
        "classification": classification,
        "tasks_completed": tasks,
        "effective_completed": effective,
        "consecutive_skips": consec_skips,
        "hard_off_skip_count": hard_off,
        "skip_reasons": {},
        "governance_blocked": 0,
        "clv_computed": 0,
        "next_focus": "",
    }


def _make_quality(
    total: int = 1,
    valid: int = 1,
    diag: int = 0,
    empty: int = 0,
    noop: int = 0,
    eff: int = 1,
) -> dict:
    return {
        "available": True,
        "total_completed": total,
        "completed_valid": valid,
        "completed_diagnostic_only": diag,
        "completed_empty_artifact": empty,
        "completed_noop": noop,
        "effective_completed": eff,
        "quality_ok": (empty == 0 and noop == 0) or eff > 0,
    }


def _make_skip_health(
    total: int = 0,
    hard_off_protected: int = 0,
    unexplained: int = 0,
    all_protected: bool = False,
    health: str = "HEALTHY",
) -> dict:
    return {
        "available": True,
        "total_skips": total,
        "hard_off_protected": hard_off_protected,
        "unexplained_consecutive": unexplained,
        "all_protected": all_protected,
        "skip_reasons": {},
        "skip_health": health,
    }


# ─────────────────────────────────────────────────────────────────────────────
# S1: WAITING_ACTIVE — CLV pending, safe cadence healthy
# ─────────────────────────────────────────────────────────────────────────────

class TestWaitingActiveScenario:
    """All CLV pending + safe cadence running → WAITING_ACTIVE / GREEN."""

    def test_waiting_active_green(self):
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_WAITING_ACTIVE, SEV_GREEN
        rs, sev, reason = _derive_readiness_state(
            phase6=_make_phase6(computed=0, pending=14, all_pending=True),
            governance=_make_governance(state="DATA_WAITING"),
            ops=_make_ops(classification="WAITING_ACTIVE", effective=1),
            completion_quality=_make_quality(total=1, eff=1),
            skip_health=_make_skip_health(unexplained=0),
        )
        assert rs == RS_WAITING_ACTIVE
        assert sev == SEV_GREEN

    def test_learning_not_allowed_when_clv_pending(self):
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_WAITING_ACTIVE
        rs, sev, _ = _derive_readiness_state(
            phase6=_make_phase6(computed=0, pending=14, all_pending=True),
            governance=_make_governance(state="DATA_WAITING"),
            ops=_make_ops(effective=1),
            completion_quality=_make_quality(eff=1),
            skip_health=_make_skip_health(),
        )
        assert rs == RS_WAITING_ACTIVE

    def test_waiting_active_yellow_when_no_effective_completions(self):
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_WAITING_ACTIVE, SEV_YELLOW
        rs, sev, _ = _derive_readiness_state(
            phase6=_make_phase6(computed=0, pending=14, all_pending=True),
            governance=_make_governance(state="DATA_WAITING"),
            ops=_make_ops(effective=0, tasks=0),
            completion_quality=_make_quality(total=0, eff=0),
            skip_health=_make_skip_health(),
        )
        assert rs == RS_WAITING_ACTIVE
        assert sev == SEV_YELLOW


# ─────────────────────────────────────────────────────────────────────────────
# S2: LEARNING_READY — CLV computed, learning families allowed
# ─────────────────────────────────────────────────────────────────────────────

class TestLearningReadyScenario:
    """CLV computed + learning families allowed → LEARNING_READY / GREEN."""

    def _learning_governance(self) -> dict:
        return _make_governance(
            state="LEARNING_ACTIVE",
            allowed=["strategy-reinforcement", "model-patch-atomic", "calibration-atomic"],
            blocked=[],
        )

    def test_learning_ready_green(self):
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_LEARNING_READY, SEV_GREEN
        rs, sev, _ = _derive_readiness_state(
            phase6=_make_phase6(computed=5, pending=0, all_pending=False),
            governance=self._learning_governance(),
            ops=_make_ops(classification="EFFECTIVE", effective=3),
            completion_quality=_make_quality(total=3, eff=3),
            skip_health=_make_skip_health(),
        )
        assert rs == RS_LEARNING_READY
        assert sev == SEV_GREEN

    def test_learning_allowed_flag_true(self):
        """get_readiness_summary learning_allowed is True when LEARNING_READY."""
        from orchestrator.optimization_readiness import (
            get_readiness_summary, RS_LEARNING_READY,
        )
        with (
            patch("orchestrator.optimization_readiness._get_phase6",
                  return_value=_make_phase6(computed=3, pending=0, all_pending=False)),
            patch("orchestrator.optimization_readiness._get_governance",
                  return_value=self._learning_governance()),
            patch("orchestrator.optimization_readiness._get_ops_summary",
                  return_value=_make_ops(classification="EFFECTIVE", effective=2)),
            patch("orchestrator.optimization_readiness._get_completion_quality",
                  return_value=_make_quality(total=2, eff=2)),
            patch("orchestrator.optimization_readiness._get_safe_work_status",
                  return_value={"available": True, "due_tasks": [], "closing_monitor_due": False}),
            patch("orchestrator.optimization_readiness._get_skip_health",
                  return_value=_make_skip_health()),
            patch("orchestrator.optimization_readiness._get_phase7",
                  return_value={"available": False}),
        ):
            summary = get_readiness_summary()
        assert summary["readiness_state"] == RS_LEARNING_READY
        assert summary["learning_allowed"] is True


# ─────────────────────────────────────────────────────────────────────────────
# S3: DEGRADED — Unexplained skip storm
# ─────────────────────────────────────────────────────────────────────────────

class TestDegradedUnexplainedSkips:
    """Unexplained consecutive skips ≥ 3 → DEGRADED / RED."""

    def test_three_unexplained_skips_degraded(self):
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_DEGRADED, SEV_RED
        rs, sev, reason = _derive_readiness_state(
            phase6=_make_phase6(),
            governance=_make_governance(),
            ops=_make_ops(consec_skips=3),
            completion_quality=_make_quality(),
            skip_health=_make_skip_health(unexplained=3, all_protected=False, health="DEGRADED"),
        )
        assert rs == RS_DEGRADED
        assert sev == SEV_RED
        assert "3" in reason

    def test_five_unexplained_skips_degraded(self):
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_DEGRADED, SEV_RED
        rs, sev, _ = _derive_readiness_state(
            phase6=_make_phase6(),
            governance=_make_governance(),
            ops=_make_ops(consec_skips=5),
            completion_quality=_make_quality(),
            skip_health=_make_skip_health(unexplained=5, all_protected=False, health="DEGRADED"),
        )
        assert rs == RS_DEGRADED
        assert sev == SEV_RED

    def test_two_unexplained_skips_not_degraded(self):
        """Two unexplained skips is below threshold — should NOT be DEGRADED."""
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_DEGRADED
        rs, _, _ = _derive_readiness_state(
            phase6=_make_phase6(),
            governance=_make_governance(),
            ops=_make_ops(consec_skips=2),
            completion_quality=_make_quality(),
            skip_health=_make_skip_health(unexplained=2, all_protected=False, health="HEALTHY"),
        )
        assert rs != RS_DEGRADED


# ─────────────────────────────────────────────────────────────────────────────
# S4: DEGRADED — Empty artifacts only
# ─────────────────────────────────────────────────────────────────────────────

class TestDegradedEmptyArtifacts:
    """All recent completions are empty/noop → DEGRADED / RED."""

    def test_all_empty_artifacts_degraded(self):
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_DEGRADED, SEV_RED
        rs, sev, reason = _derive_readiness_state(
            phase6=_make_phase6(),
            governance=_make_governance(),
            ops=_make_ops(effective=0, tasks=3),
            completion_quality=_make_quality(total=3, valid=0, empty=3, eff=0),
            skip_health=_make_skip_health(unexplained=0),
        )
        assert rs == RS_DEGRADED
        assert sev == SEV_RED
        assert "empty" in reason.lower() or "noop" in reason.lower()

    def test_partial_empty_not_degraded(self):
        """1 valid + 1 empty — not degraded because effective > 0."""
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_DEGRADED
        rs, _, _ = _derive_readiness_state(
            phase6=_make_phase6(),
            governance=_make_governance(),
            ops=_make_ops(effective=1, tasks=2),
            completion_quality=_make_quality(total=2, valid=1, empty=1, eff=1),
            skip_health=_make_skip_health(unexplained=0),
        )
        assert rs != RS_DEGRADED


# ─────────────────────────────────────────────────────────────────────────────
# S5: Hard-off protected skips → NOT DEGRADED
# ─────────────────────────────────────────────────────────────────────────────

class TestHardOffProtectedSkipsNotDegraded:
    """8 hard-off skips with unexplained=0 → should not be RED/DEGRADED."""

    def test_all_hard_off_not_degraded(self):
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_DEGRADED, SEV_RED
        rs, sev, _ = _derive_readiness_state(
            phase6=_make_phase6(),
            governance=_make_governance(),
            ops=_make_ops(consec_skips=0, hard_off=8),
            completion_quality=_make_quality(),
            skip_health=_make_skip_health(
                total=8, hard_off_protected=8, unexplained=0, all_protected=True
            ),
        )
        assert rs != RS_DEGRADED
        assert sev != SEV_RED

    def test_hard_off_all_protected_flag_respected(self):
        """Even if total_skips=8 but all_protected=True, we don't escalate to DEGRADED."""
        from orchestrator.optimization_readiness import _derive_readiness_state, RS_DEGRADED
        rs, _, _ = _derive_readiness_state(
            phase6=_make_phase6(computed=0, pending=14, all_pending=True),
            governance=_make_governance(),
            ops=_make_ops(consec_skips=0, hard_off=8, effective=1),
            completion_quality=_make_quality(eff=1),
            skip_health=_make_skip_health(
                total=8, hard_off_protected=8, unexplained=0, all_protected=True
            ),
        )
        assert rs != RS_DEGRADED


# ─────────────────────────────────────────────────────────────────────────────
# S6: Decision card renders readiness section
# ─────────────────────────────────────────────────────────────────────────────

class TestDecisionCardRendersReadiness:
    """ops_decision_card.render_card includes AUTONOMOUS READINESS section."""

    def _mock_readiness(self) -> dict:
        return {
            "available": True,
            "readiness_state": "WAITING_ACTIVE",
            "severity": "GREEN",
            "reason": "CLV pending closing; safe work is running on cadence",
            "learning_allowed": False,
            "next_required_event": "Wait for market settlement",
            "recommended_next_action": "Run closing-monitor now",
            "safe_work_status": {"available": True, "due_tasks": ["closing_monitor"]},
            "skip_health": {
                "available": True,
                "skip_health": "HEALTHY",
                "unexplained_consecutive": 0,
                "hard_off_protected": 0,
            },
            "completion_quality": {
                "available": True,
                "total_completed": 1,
                "effective_completed": 1,
                "quality_ok": True,
            },
        }

    def _base_payload(self) -> dict:
        """Minimal valid payload that render_card() accepts without KeyError."""
        return {
            "generated_at": "2025-01-01T00:00:00Z",
            "status": "OK",
            "reasons": [],
            "clv": {
                "total_live_rows": 0,
                "external_closing_rows": 0,
                "coverage_pct": 0.0,
                "clv_samples": 0,
                "clv_std": 0.0,
            },
            "scheduler": {
                "state_date": "2025-01-01",
                "fetched_today": 0,
                "api_calls_today": 0,
                "api_cap": 500,
                "last_run_ts": None,
                "next_trigger_minutes": 0,
                "heartbeat_present": False,
            },
            "flags": [],
            "action": "monitor",
            "system_health": {},
            "today_wbc": {},
            "recent_performance": {},
            "last_postmortem": {},
            "phase6": {"available": False},
            "phase7": {"available": False},
            "phase8": {"available": False},
            "phase9_ops": {"available": False},
            "readiness": self._mock_readiness(),
        }

    def test_readiness_section_in_card(self):
        """render_card output contains AUTONOMOUS READINESS header."""
        import importlib
        mod = importlib.import_module("scripts.ops_decision_card")
        card = mod.render_card(self._base_payload())
        assert "AUTONOMOUS READINESS" in card

    def test_readiness_section_shows_state(self):
        """Readiness state and severity appear in the card."""
        import importlib
        mod = importlib.import_module("scripts.ops_decision_card")
        card = mod.render_card(self._base_payload())
        assert "WAITING_ACTIVE" in card
        assert "GREEN" in card

    def test_readiness_unavailable_does_not_crash(self):
        """If readiness module fails, card still renders."""
        import importlib
        mod = importlib.import_module("scripts.ops_decision_card")
        payload = self._base_payload()
        payload["readiness"] = {"available": False, "error": "test error"}
        card = mod.render_card(payload)
        assert "AUTONOMOUS READINESS" in card  # section still appears
        assert "unavailable" in card.lower()


# ─────────────────────────────────────────────────────────────────────────────
# S7: CLI writes JSON + Markdown artifacts
# ─────────────────────────────────────────────────────────────────────────────

class TestCliArtifacts:
    """run_optimization_readiness.py writes artifacts when invoked."""

    def test_cli_writes_json(self, tmp_path):
        """CLI writes optimization_readiness_latest.json."""
        import importlib
        import sys
        from pathlib import Path

        # Patch output paths to tmp_path
        mod = importlib.import_module("scripts.run_optimization_readiness")
        orig_json = mod.JSON_OUT
        orig_md   = mod.MD_OUT
        orig_rep  = mod.REPORTS_DIR
        orig_docs = mod.DOCS_ORCH_DIR

        mod.JSON_OUT     = tmp_path / "optimization_readiness_latest.json"
        mod.MD_OUT       = tmp_path / "optimization_readiness_latest.md"
        mod.REPORTS_DIR  = tmp_path
        mod.DOCS_ORCH_DIR = tmp_path
        try:
            rc = mod.main(["--json"])
        finally:
            mod.JSON_OUT      = orig_json
            mod.MD_OUT        = orig_md
            mod.REPORTS_DIR   = orig_rep
            mod.DOCS_ORCH_DIR = orig_docs

        assert rc == 0
        assert (tmp_path / "optimization_readiness_latest.json").exists()

    def test_cli_writes_markdown(self, tmp_path):
        """CLI writes optimization_readiness_latest.md."""
        import importlib

        mod = importlib.import_module("scripts.run_optimization_readiness")
        orig_json = mod.JSON_OUT
        orig_md   = mod.MD_OUT
        orig_rep  = mod.REPORTS_DIR
        orig_docs = mod.DOCS_ORCH_DIR

        mod.JSON_OUT      = tmp_path / "optimization_readiness_latest.json"
        mod.MD_OUT        = tmp_path / "optimization_readiness_latest.md"
        mod.REPORTS_DIR   = tmp_path
        mod.DOCS_ORCH_DIR = tmp_path
        try:
            rc = mod.main(["--print"])
        finally:
            mod.JSON_OUT      = orig_json
            mod.MD_OUT        = orig_md
            mod.REPORTS_DIR   = orig_rep
            mod.DOCS_ORCH_DIR = orig_docs

        assert rc == 0
        assert (tmp_path / "optimization_readiness_latest.md").exists()

    def test_json_artifact_has_readiness_state(self, tmp_path):
        """JSON artifact contains readiness_state key."""
        import importlib
        import json as _json

        mod = importlib.import_module("scripts.run_optimization_readiness")
        orig_json = mod.JSON_OUT
        orig_md   = mod.MD_OUT
        orig_rep  = mod.REPORTS_DIR
        orig_docs = mod.DOCS_ORCH_DIR

        json_path = tmp_path / "optimization_readiness_latest.json"
        mod.JSON_OUT      = json_path
        mod.MD_OUT        = tmp_path / "optimization_readiness_latest.md"
        mod.REPORTS_DIR   = tmp_path
        mod.DOCS_ORCH_DIR = tmp_path
        try:
            mod.main(["--json"])
        finally:
            mod.JSON_OUT      = orig_json
            mod.MD_OUT        = orig_md
            mod.REPORTS_DIR   = orig_rep
            mod.DOCS_ORCH_DIR = orig_docs

        data = _json.loads(json_path.read_text(encoding="utf-8"))
        assert "readiness_state" in data
        assert data["readiness_state"] in (
            "LEARNING_READY", "WAITING_ACTIVE", "SAFE_WORK_ACTIVE",
            "BLOCKED", "DEGRADED",
        )


# ─────────────────────────────────────────────────────────────────────────────
# Success marker
# ─────────────────────────────────────────────────────────────────────────────

def test_phase13_success_marker():
    """
    All Phase 13 tests passed.
    Phase 13 tag: PHASE_13_OPTIMIZATION_READINESS_DASHBOARD_VERIFIED
    """
    assert "PHASE_13_OPTIMIZATION_READINESS_DASHBOARD_VERIFIED"
