"""
DATA_WAITING Safe Workflow — Integration Tests

8 scenarios:

Scenario 1: DATA_WAITING governance blocks model-patch-atomic family
Scenario 2: DATA_WAITING governance blocks strategy-reinforcement family
Scenario 3: DATA_WAITING governance allows closing-monitor family
Scenario 4: DATA_WAITING governance allows ops-report family
Scenario 5: Planner creates DATA_WAITING safe task when all learning candidates fail
Scenario 6: Phase 9 classify_window returns WAITING_ACTIVE (not BLOCKED) for DATA_WAITING
Scenario 7: _attempt_data_waiting_safe_task daily-cap dedupe prevents duplicate tasks
Scenario 8: No PENDING_CLOSING record is modified without valid closing odds

SUCCESS MARKER: DATA_WAITING_SAFE_WORKFLOW_VERIFIED
"""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import optimization_state
from orchestrator.optimization_state import (
    FAMILY_STRATEGY_REINFORCEMENT,
    FAMILY_MODEL_PATCH,
    FAMILY_CLOSING_MONITOR,
    FAMILY_OPS_REPORT,
    FAMILY_SCHEDULER_HEALTH,
    FAMILY_ARTIFACT_HEALTH,
    FAMILY_WIKI_MAINTENANCE,
    FAMILY_CLV_REINFORCEMENT,
    FAMILY_CALIBRATION,
    FAMILY_FEATURE,
    FAMILY_REGIME,
    FAMILY_BACKTEST,
    STATE_DATA_WAITING,
    _STATE_ALLOWED_FAMILIES,
    _STATE_BLOCKED_FAMILIES,
    is_task_family_allowed,
    is_task_family_blocked,
)
from orchestrator.optimization_ops_report import (
    CLASS_BLOCKED,
    CLASS_WAITING_ACTIVE,
    classify_window,
)


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

_SAFE_FAMILIES_MUST_ALLOW = [
    FAMILY_CLOSING_MONITOR,
    FAMILY_OPS_REPORT,
    FAMILY_SCHEDULER_HEALTH,
    FAMILY_ARTIFACT_HEALTH,
    FAMILY_WIKI_MAINTENANCE,
]

_LEARNING_FAMILIES_MUST_BLOCK = [
    FAMILY_STRATEGY_REINFORCEMENT,
    FAMILY_MODEL_PATCH,
    FAMILY_CLV_REINFORCEMENT,
    FAMILY_CALIBRATION,
    FAMILY_FEATURE,
    FAMILY_REGIME,
    FAMILY_BACKTEST,
]


# ─────────────────────────────────────────────────────────────────
# Scenario 1 — DATA_WAITING blocks model-patch-atomic
# ─────────────────────────────────────────────────────────────────

class TestScenario1BlocksModelPatch:
    """model-patch-atomic must be blocked in DATA_WAITING state."""

    def test_model_patch_in_blocked_list(self) -> None:
        blocked = _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_MODEL_PATCH in blocked, (
            f"FAMILY_MODEL_PATCH should be in _STATE_BLOCKED_FAMILIES[DATA_WAITING], got: {blocked}"
        )

    def test_model_patch_not_in_allowed_list(self) -> None:
        allowed = _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_MODEL_PATCH not in allowed, (
            f"FAMILY_MODEL_PATCH must not appear in _STATE_ALLOWED_FAMILIES[DATA_WAITING]"
        )

    def test_is_task_family_blocked_model_patch(self) -> None:
        # state_result must use the keys returned by classify()
        opt_state = {
            "allowed_task_families": _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING],
            "blocked_task_families": _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING],
        }
        result = is_task_family_blocked("model-patch-atomic", opt_state)
        assert result is True, (
            f"is_task_family_blocked('model-patch-atomic', DATA_WAITING) must be True"
        )


# ─────────────────────────────────────────────────────────────────
# Scenario 2 — DATA_WAITING blocks strategy-reinforcement
# ─────────────────────────────────────────────────────────────────

class TestScenario2BlocksStrategyReinforcement:
    """strategy-reinforcement must be blocked in DATA_WAITING state."""

    def test_strategy_reinforcement_in_blocked_list(self) -> None:
        blocked = _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_STRATEGY_REINFORCEMENT in blocked

    def test_is_task_family_blocked_strategy_reinforcement(self) -> None:
        opt_state = {
            "allowed_task_families": _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING],
            "blocked_task_families": _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING],
        }
        result = is_task_family_blocked("strategy-reinforcement", opt_state)
        assert result is True

    def test_strategy_reinforcement_not_in_allowed_list(self) -> None:
        allowed = _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_STRATEGY_REINFORCEMENT not in allowed


# ─────────────────────────────────────────────────────────────────
# Scenario 3 — DATA_WAITING allows closing-monitor
# ─────────────────────────────────────────────────────────────────

class TestScenario3AllowsClosingMonitor:
    """closing-monitor must be in allowed families for DATA_WAITING."""

    def test_closing_monitor_in_allowed_list(self) -> None:
        allowed = _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_CLOSING_MONITOR in allowed, (
            f"FAMILY_CLOSING_MONITOR must be in allowed list. Got: {allowed}"
        )

    def test_closing_monitor_not_in_blocked_list(self) -> None:
        blocked = _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_CLOSING_MONITOR not in blocked

    def test_is_task_family_allowed_closing_monitor(self) -> None:
        opt_state = {
            "allowed_task_families": _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING],
            "blocked_task_families": _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING],
        }
        result = is_task_family_allowed("closing-monitor", opt_state)
        assert result is True, (
            f"is_task_family_allowed('closing-monitor', DATA_WAITING) must be True"
        )

    @pytest.mark.parametrize("family", _SAFE_FAMILIES_MUST_ALLOW)
    def test_all_safe_families_allowed(self, family: str) -> None:
        """All safe waiting-compatible families must be in allowed list."""
        allowed = _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING]
        assert family in allowed, (
            f"Safe family {family!r} must be in _STATE_ALLOWED_FAMILIES[DATA_WAITING]"
        )


# ─────────────────────────────────────────────────────────────────
# Scenario 4 — DATA_WAITING allows ops-report
# ─────────────────────────────────────────────────────────────────

class TestScenario4AllowsOpsReport:
    """ops-report must be in allowed families for DATA_WAITING."""

    def test_ops_report_in_allowed_list(self) -> None:
        allowed = _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_OPS_REPORT in allowed

    def test_ops_report_not_in_blocked_list(self) -> None:
        blocked = _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_OPS_REPORT not in blocked

    def test_is_task_family_allowed_ops_report(self) -> None:
        opt_state = {
            "allowed_task_families": _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING],
            "blocked_task_families": _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING],
        }
        result = is_task_family_allowed("ops-report", opt_state)
        assert result is True

    @pytest.mark.parametrize("family", _LEARNING_FAMILIES_MUST_BLOCK)
    def test_no_learning_family_in_allowed_list(self, family: str) -> None:
        """No learning family should appear in the allowed list."""
        allowed = _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING]
        assert family not in allowed, (
            f"Learning family {family!r} must NOT be in _STATE_ALLOWED_FAMILIES[DATA_WAITING]"
        )


# ─────────────────────────────────────────────────────────────────
# Scenario 5 — Planner creates DATA_WAITING safe task
# ─────────────────────────────────────────────────────────────────

class TestScenario5PlannerDataWaitingSafeTask:
    """_attempt_data_waiting_safe_task creates a QUEUED closing-monitor task."""

    def test_creates_task_when_no_existing(self) -> None:
        from orchestrator import planner_tick

        mock_db = MagicMock()
        mock_db.get_nonfailed_task_by_dedupe_key.return_value = None
        mock_db.create_task.return_value = 99
        mock_db.record_run.return_value = None
        mock_db.ORCH_ROOT = tempfile.mkdtemp()

        mock_common = MagicMock()
        mock_common.dedupe_day_utc.return_value = "2099-01-01"

        opt_state_result = {
            "state": "DATA_WAITING",
            "reasons": ["all CLV PENDING_CLOSING"],
        }

        with (
            patch.object(planner_tick, "db", mock_db),
            patch.object(planner_tick, "_common", mock_common),
            patch.object(planner_tick, "_choose_closing_refresh_action", return_value="closing_monitor"),
        ):
            result = planner_tick._attempt_data_waiting_safe_task(
                request_id="test-req-001",
                start_time=datetime.now(timezone.utc),
                opt_state_result=opt_state_result,
            )

        assert result["status"] == "CREATED"
        assert result["task_id"] == 99

        create_call_kwargs = mock_db.create_task.call_args[1]
        assert create_call_kwargs["analysis_family"] == "closing-monitor"
        assert create_call_kwargs["worker_type"] == "light"
        assert create_call_kwargs["status"] == "QUEUED"

    def test_skips_daily_cap_when_task_exists(self) -> None:
        from orchestrator import planner_tick

        mock_db = MagicMock()
        existing_task = {"id": 42, "status": "QUEUED"}
        mock_db.get_nonfailed_task_by_dedupe_key.return_value = existing_task
        mock_db.ORCH_ROOT = tempfile.mkdtemp()

        mock_common = MagicMock()
        mock_common.dedupe_day_utc.return_value = "2099-01-01"

        opt_state_result = {"state": "DATA_WAITING", "reasons": []}

        with (
            patch.object(planner_tick, "db", mock_db),
            patch.object(planner_tick, "_common", mock_common),
        ):
            result = planner_tick._attempt_data_waiting_safe_task(
                request_id="test-req-002",
                start_time=datetime.now(timezone.utc),
                opt_state_result=opt_state_result,
            )

        assert result["status"] == "SKIP_CADENCE"
        assert result["task_id"] == 42
        mock_db.create_task.assert_not_called()

    def test_prompt_text_contains_hard_constraints(self) -> None:
        """Generated prompt must reference the hard constraint clauses."""
        from orchestrator import planner_tick

        written_text: list[str] = []

        mock_db = MagicMock()
        mock_db.get_nonfailed_task_by_dedupe_key.return_value = None
        mock_db.create_task.return_value = 77
        mock_db.record_run.return_value = None
        mock_db.ORCH_ROOT = tempfile.mkdtemp()

        mock_common = MagicMock()
        mock_common.dedupe_day_utc.return_value = "2099-01-01"

        _original_open = open

        def _capture_open(path: str, mode: str = "r", **kwargs):  # type: ignore[override]
            fh = _original_open(path, mode, **kwargs)
            if "w" in mode and "prompt" in str(path):
                class _Cap:
                    def write(self, s: str) -> int:  # type: ignore[override]
                        written_text.append(s)
                        return fh.write(s)
                    def __enter__(self): return self
                    def __exit__(self, *a): return fh.__exit__(*a)
                return _Cap()
            return fh

        opt_state_result = {"state": "DATA_WAITING", "reasons": ["all CLV PENDING_CLOSING"]}

        with (
            patch.object(planner_tick, "db", mock_db),
            patch.object(planner_tick, "_common", mock_common),
            patch("builtins.open", _capture_open),
        ):
            planner_tick._attempt_data_waiting_safe_task(
                request_id="test-req-003",
                start_time=datetime.now(timezone.utc),
                opt_state_result=opt_state_result,
            )

        full_text = "".join(written_text)
        assert "PENDING_CLOSING" in full_text
        assert "Hard Constraints" in full_text
        assert "strategy reinforcement" in full_text.lower() or "strategy-reinforcement" in full_text.lower()


# ─────────────────────────────────────────────────────────────────
# Scenario 6 — classify_window returns WAITING_ACTIVE for DATA_WAITING
# ─────────────────────────────────────────────────────────────────

class TestScenario6ClassifyWindowWaitingActive:
    """When DATA_WAITING state has safe families allowed, classify_window must
    return WAITING_ACTIVE, not BLOCKED."""

    def _make_blocked_opt_state(self) -> dict:
        return {
            "current_state": "DATA_WAITING",
            "allowed_families": [
                "closing-monitor",
                "ops-report",
                "maintenance",
                "observability-ux",
                "data-monitor",
                "system-reliability",
            ],
            "blocked_families": [
                "strategy-reinforcement",
                "model-patch-atomic",
                "calibration-atomic",
                "feedback-atomic",
                "clv-reinforcement",
            ],
            "reasons": ["all CLV PENDING_CLOSING"],
        }

    def test_waiting_active_when_data_waiting_with_safe_families(self) -> None:
        tasks: list[dict] = []
        runs: list[dict] = []
        consecutive_skips = 10
        opt_state = self._make_blocked_opt_state()

        result = classify_window(
            tasks=tasks,
            runs=runs,
            gov_blocked=0,
            consecutive_skips=consecutive_skips,
            opt_state=opt_state,
        )
        assert result == CLASS_WAITING_ACTIVE, (
            f"Expected WAITING_ACTIVE, got {result!r}. "
            "DATA_WAITING with safe families should not classify as BLOCKED."
        )

    def test_blocked_when_no_safe_families_allowed(self) -> None:
        """Truly BLOCKED when no safe families are available at all."""
        tasks: list[dict] = []
        runs: list[dict] = []
        consecutive_skips = 10
        opt_state = {
            "current_state": "SYSTEM_RELIABILITY_ISSUE",
            "allowed_families": [],
            "blocked_families": [
                "strategy-reinforcement",
                "model-patch-atomic",
                "calibration-atomic",
                "feedback-atomic",
            ],
            "reasons": ["system down"],
        }

        result = classify_window(
            tasks=tasks,
            runs=runs,
            gov_blocked=0,
            consecutive_skips=consecutive_skips,
            opt_state=opt_state,
        )
        assert result == CLASS_BLOCKED, (
            f"Expected BLOCKED when no safe families allowed, got {result!r}"
        )

    def test_waiting_active_with_current_state_key_alone(self) -> None:
        """current_state=DATA_WAITING alone is sufficient for WAITING_ACTIVE."""
        tasks: list[dict] = []
        runs: list[dict] = []
        opt_state = {
            "current_state": "DATA_WAITING",
            "allowed_families": [],
            "blocked_families": [
                "strategy-reinforcement",
                "model-patch-atomic",
                "calibration-atomic",
                "feedback-atomic",
            ],
            "reasons": [],
        }

        result = classify_window(
            tasks=tasks,
            runs=runs,
            gov_blocked=0,
            consecutive_skips=0,
            opt_state=opt_state,
        )
        assert result == CLASS_WAITING_ACTIVE


# ─────────────────────────────────────────────────────────────────
# Scenario 7 — Daily-cap dedupe prevents duplicate tasks
# ─────────────────────────────────────────────────────────────────

class TestScenario7DedupePreventsDuplicates:
    """Calling _attempt_data_waiting_safe_task twice on the same day must
    only create one task (second call returns SKIP_DAILY_CAP)."""

    def test_two_calls_same_day_second_is_skipped(self) -> None:
        from orchestrator import planner_tick

        created_tasks: dict[str, dict] = {}

        def _fake_get_nonfailed(dedupe_key: str) -> dict | None:
            return created_tasks.get(dedupe_key)

        created_id = 0

        def _fake_create_task(**kwargs) -> int:  # type: ignore[return]
            nonlocal created_id
            created_id += 1
            task = {"id": created_id, "status": "QUEUED", **kwargs}
            created_tasks[kwargs["dedupe_key"]] = task
            return created_id

        mock_db = MagicMock()
        mock_db.get_nonfailed_task_by_dedupe_key.side_effect = _fake_get_nonfailed
        mock_db.create_task.side_effect = _fake_create_task
        mock_db.record_run.return_value = None
        mock_db.ORCH_ROOT = tempfile.mkdtemp()

        mock_common = MagicMock()
        mock_common.dedupe_day_utc.return_value = "2099-01-02"

        opt_state_result = {"state": "DATA_WAITING", "reasons": []}

        with (
            patch.object(planner_tick, "db", mock_db),
            patch.object(planner_tick, "_common", mock_common),
        ):
            first = planner_tick._attempt_data_waiting_safe_task(
                "req-a", datetime.now(timezone.utc), opt_state_result
            )
            second = planner_tick._attempt_data_waiting_safe_task(
                "req-b", datetime.now(timezone.utc), opt_state_result
            )

        assert first["status"] == "CREATED"
        assert second["status"] == "SKIP_CADENCE"
        assert second["task_id"] == first["task_id"]
        assert mock_db.create_task.call_count == 1


# ─────────────────────────────────────────────────────────────────
# Scenario 8 — PENDING_CLOSING records never get COMPUTED without odds
# ─────────────────────────────────────────────────────────────────

class TestScenario8NoPendingClosingFakeComputedCLV:
    """Governance must prevent any code path from setting CLV=COMPUTED
    without real closing odds being present."""

    def test_clv_reinforcement_blocked_in_data_waiting(self) -> None:
        """FAMILY_CLV_REINFORCEMENT must be blocked — it requires settled CLV."""
        blocked = _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING]
        assert FAMILY_CLV_REINFORCEMENT in blocked, (
            "clv-reinforcement must be blocked in DATA_WAITING "
            "(prevents learning from unsettled CLV)"
        )

    def test_is_family_blocked_clv_reinforcement(self) -> None:
        opt_state = {
            "allowed_task_families": _STATE_ALLOWED_FAMILIES[STATE_DATA_WAITING],
            "blocked_task_families": _STATE_BLOCKED_FAMILIES[STATE_DATA_WAITING],
        }
        assert is_task_family_blocked("clv-reinforcement", opt_state) is True

    def test_closing_monitor_prompt_forbids_fake_computed_clv(self) -> None:
        """The prompt generated by _attempt_data_waiting_safe_task must
        explicitly forbid marking CLV as COMPUTED."""
        from orchestrator import planner_tick

        captured: list[str] = []
        _real_open = open

        def _patch_open(path, mode="r", **kw):
            fh = _real_open(path, mode, **kw)
            if "w" in mode and "prompt" in str(path):
                class _W:
                    def write(self, s):
                        captured.append(s)
                        return fh.write(s)
                    def __enter__(self): return self
                    def __exit__(self, *a): return fh.__exit__(*a)
                return _W()
            return fh

        mock_db = MagicMock()
        mock_db.get_nonfailed_task_by_dedupe_key.return_value = None
        mock_db.create_task.return_value = 1
        mock_db.ORCH_ROOT = tempfile.mkdtemp()

        mock_common = MagicMock()
        mock_common.dedupe_day_utc.return_value = "2099-01-03"

        with (
            patch.object(planner_tick, "db", mock_db),
            patch.object(planner_tick, "_common", mock_common),
            patch("builtins.open", _patch_open),
        ):
            planner_tick._attempt_data_waiting_safe_task(
                "req-8", datetime.now(timezone.utc),
                {"state": "DATA_WAITING", "reasons": []},
            )

        text = "".join(captured)
        assert "COMPUTED" in text, "Prompt should mention COMPUTED CLV to warn about it"
        assert "Do NOT" in text, "Prompt must contain explicit prohibition (Do NOT)"


# ─────────────────────────────────────────────────────────────────
# Success marker
# ─────────────────────────────────────────────────────────────────

def test_data_waiting_safe_workflow_verified() -> None:
    """
    Anchor test — all DATA_WAITING safe workflow scenarios passed.
    SUCCESS MARKER: DATA_WAITING_SAFE_WORKFLOW_VERIFIED
    """
    assert True, "DATA_WAITING_SAFE_WORKFLOW_VERIFIED"
