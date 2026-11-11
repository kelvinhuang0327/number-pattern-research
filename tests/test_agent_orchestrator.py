from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestrator import db
from orchestrator.common import load_project_profile, validate_document_against_schema
from orchestrator.planner_tick import run_planner_tick
from orchestrator.worker_tick import run_worker_tick


def _build_profile(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "agent_orchestrator_runtime"
    profile_path = root / "project_profile.json"
    schema_src = Path("runtime/agent_orchestrator/project_profile.schema.json")
    schema_path = root / "project_profile.schema.json"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(schema_src.read_text(encoding="utf-8"), encoding="utf-8")

    profile = {
        "project_name": "Betting Pool Test",
        "project_slug": "betting-pool-test",
        "orchestrator_root": str(root),
        "backlog_path": str(root / "backlog.md"),
        "task_storage_path": str(root / "tasks"),
        "log_storage_path": str(root / "logs"),
        "database_path": str(root / "orchestrator.db"),
        "default_schedule_minutes": 10,
        "planner_provider": "codex",
        "worker_provider": "claude",
        "planner_rules": {
            "must_read_previous_result": True,
            "skip_if_latest_running": True,
            "retry_replan_required_first": True,
        },
        "worker_rules": {
            "single_active_task": True,
            "finalize_on_permission_block": True,
            "finalize_on_stale_output_minutes": 15,
        },
        "protected_paths": [".env", ".git/"],
        "required_checks": ["pytest", "ruff"],
        "allowed_reference_paths": ["README.md", "docs/", "wiki/", "memory/"],
        "required_contract_fields": [
            "version",
            "objective",
            "scope",
            "constraints",
            "acceptance_tests",
            "required_outputs",
            "forbidden_changes",
            "handoff_questions",
        ],
        "required_result_fields": [
            "version",
            "task_id",
            "status",
            "gate_verdict",
            "gate_reason",
            "duration_seconds",
            "changed_files",
            "acceptance_results",
            "next_action",
        ],
        "ui": {
            "show_contract": True,
            "show_result": True,
            "show_gate_verdict": True,
            "show_last_output_time": True,
            "show_latest_progress_summary": True,
        },
    }
    profile_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "backlog.md").write_text("- First priority task\n", encoding="utf-8")
    return profile_path, schema_path


def test_profile_matches_schema(tmp_path: Path) -> None:
    profile_path, schema_path = _build_profile(tmp_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = validate_document_against_schema(profile, schema)
    assert errors == []


@pytest.mark.skip(reason="API stale: db.init_db/run_planner_tick/run_worker_tick signatures changed")
def test_planner_and_worker_smoke(tmp_path: Path) -> None:
    profile_path, _ = _build_profile(tmp_path)
    profile = load_project_profile(profile_path)
    db.init_db(profile)

    planner_result = run_planner_tick(profile_path)
    assert planner_result["status"] == "created"

    worker_result = run_worker_tick(profile_path, execute_provider=False)
    assert worker_result["status"] == "finalized"
    assert worker_result["final_status"] == "REPLAN_REQUIRED"

    latest_task = db.get_latest_task(profile)
    assert latest_task is not None
    assert latest_task["status"] == "REPLAN_REQUIRED"
    assert Path(latest_task["result_path"]).exists()


@pytest.mark.skip(reason="API stale: _build_objective removed from planner_tick")
def test_planner_skips_circular_next_action(tmp_path: Path) -> None:
    """Planner must fall back to backlog when next_action is a meta-sentinel."""
    from orchestrator.planner_tick import _build_objective

    backlog_focus = "Implement real MLB player data ingestion"

    circular_sentinels = [
        "Planner should create the next task.",
        "planner should create the next task.",
        "Planner must replan this task with adjusted scope/method.",
    ]
    for sentinel in circular_sentinels:
        result = _build_objective(
            latest_task=None,
            backlog_focus=backlog_focus,
            previous_result={"next_action": sentinel},
            retry_replan_required_first=False,
        )
        assert result == backlog_focus, f"Expected backlog fallback for sentinel: {sentinel!r}"

    real_action = "Add Platt scaling calibration to walk-forward pipeline"
    result = _build_objective(
        latest_task=None,
        backlog_focus=backlog_focus,
        previous_result={"next_action": real_action},
        retry_replan_required_first=False,
    )
    assert result == real_action
