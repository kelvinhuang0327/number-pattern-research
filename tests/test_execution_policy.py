from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator import execution_policy


def test_safe_run_blocks_background_when_scheduler_disabled(monkeypatch) -> None:
    monkeypatch.setattr(execution_policy.db, "get_scheduler_enabled", lambda: False)
    monkeypatch.setattr(execution_policy.db, "get_cto_scheduler_enabled", lambda: True)
    monkeypatch.setattr(execution_policy.db, "get_llm_execution_mode", lambda: "safe-run")
    monkeypatch.setattr(execution_policy.db, "get_setting", lambda key, default="": default)

    decision = execution_policy.evaluate_execution(
        runner="worker_tick",
        requires_llm=True,
        background=True,
        manual_override=False,
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "scheduler-disabled"


def test_safe_run_allows_manual_override_when_scheduler_disabled(monkeypatch) -> None:
    monkeypatch.setattr(execution_policy.db, "get_scheduler_enabled", lambda: False)
    monkeypatch.setattr(execution_policy.db, "get_cto_scheduler_enabled", lambda: True)
    monkeypatch.setattr(execution_policy.db, "get_llm_execution_mode", lambda: "safe-run")
    monkeypatch.setattr(execution_policy.db, "get_setting", lambda key, default="": default)

    decision = execution_policy.evaluate_execution(
        runner="worker_tick",
        requires_llm=True,
        background=True,
        manual_override=True,
    )

    assert decision["allowed"] is True
    assert decision["reason"] is None


def test_hard_off_blocks_manual_and_background(monkeypatch) -> None:
    monkeypatch.setattr(execution_policy.db, "get_scheduler_enabled", lambda: True)
    monkeypatch.setattr(execution_policy.db, "get_cto_scheduler_enabled", lambda: True)
    monkeypatch.setattr(execution_policy.db, "get_llm_execution_mode", lambda: "hard-off")
    monkeypatch.setattr(execution_policy.db, "get_setting", lambda key, default="": default)

    decision = execution_policy.evaluate_execution(
        runner="telegram_bot",
        requires_llm=True,
        background=False,
        manual_override=True,
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "hard-off"


def test_is_manual_run_checks_force_run_env() -> None:
    env = {
        "ORCHESTRATOR_FORCE_RUN": "1",
        "ORCHESTRATOR_MANUAL_RUN": "0",
    }

    assert execution_policy.is_manual_run(env) is True


def test_cto_scope_respects_cto_scheduler(monkeypatch) -> None:
    monkeypatch.setattr(execution_policy.db, "get_scheduler_enabled", lambda: True)
    monkeypatch.setattr(execution_policy.db, "get_cto_scheduler_enabled", lambda: False)
    monkeypatch.setattr(execution_policy.db, "get_llm_execution_mode", lambda: "safe-run")
    monkeypatch.setattr(execution_policy.db, "get_setting", lambda key, default="": default)

    decision = execution_policy.evaluate_execution(
        runner="cto_review_tick",
        background=True,
        manual_override=False,
        scheduler_scope="cto",
    )

    assert decision["allowed"] is False
    assert decision["reason"] == "cto-scheduler-disabled"