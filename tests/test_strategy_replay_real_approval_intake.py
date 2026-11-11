from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import evaluate_metadata_registry_acceptance
from wbc_backend.reporting.strategy_replay_real_approval_intake import (
    build_acceptance_context_from_real_approval,
    evaluate_real_approval_intake,
)


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
CANDIDATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry.production_candidate.draft.json"
REAL_TEMPLATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.REAL_APPROVAL_TEMPLATE.json"
REVIEW_READY_CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.review_ready.draft.json"
SIMULATION_FORM_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_human_approval_form.SIMULATION_ONLY.json"
EVIDENCE_PACK_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_production_candidate_evidence_pack.md"
ROLLBACK_PLAN_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_rollback_plan.draft.md"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_records() -> list[dict[str, object]]:
    return _load(CANDIDATE_PATH)["records"]  # type: ignore[index]


def _base_context() -> dict[str, object]:
    return _load(REAL_TEMPLATE_PATH)


def _valid_real_form() -> dict[str, object]:
    return {
        "reviewer": "REAL_REVIEWER_001",
        "approval_timestamp": "2026-05-10T14:00:00Z",
        "explicit_human_approval": True,
        "approval_decision": "APPROVE",
        "approval_reason": "Reviewed candidate evidence, rollback, and safety gates.",
        "rollback_plan_ref": str(ROLLBACK_PLAN_PATH),
        "reviewed_registry_path": str(CANDIDATE_PATH),
        "reviewed_acceptance_context_path": str(REAL_TEMPLATE_PATH),
        "reviewed_evidence_pack_path": str(EVIDENCE_PACK_PATH),
        "reviewed_test_results": [
            "./.venv/bin/python -m pytest tests/test_strategy_replay_metadata_registry_real_approval_preflight.py tests/test_strategy_replay_runtime_enablement_dry_run.py -q",
        ],
        "reviewer_notes": "Approval intake preview only; runtime enablement remains a later phase.",
        "real_approval": True,
        "simulation_only": False,
        "review_status": "submitted",
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
        "production_metadata_registry_accepted": False,
    }


def _evaluate(form: dict[str, object]) -> dict[str, object]:
    return evaluate_real_approval_intake(form, _load(CANDIDATE_PATH), _base_context())


def test_template_approval_form_is_rejected_by_default() -> None:
    result = _evaluate(_load(REAL_TEMPLATE_PATH))
    assert result["real_approval_intake_accepted"] is False
    assert result["blockers"]
    assert "real_approval must be true" in result["blockers"]


def test_simulation_only_approval_form_is_rejected() -> None:
    result = _evaluate(_load(SIMULATION_FORM_PATH))
    assert result["real_approval_intake_accepted"] is False
    assert "simulation-only approval form is rejected by real intake" in result["blockers"]


def test_missing_reviewer_is_rejected() -> None:
    form = _valid_real_form()
    form["reviewer"] = ""
    result = _evaluate(form)
    assert result["real_approval_intake_accepted"] is False
    assert "reviewer is required and must not be TBD" in result["blockers"]


def test_tbd_reviewer_is_rejected() -> None:
    form = _valid_real_form()
    form["reviewer"] = "TBD_REAL_REVIEWER"
    result = _evaluate(form)
    assert result["real_approval_intake_accepted"] is False
    assert "reviewer is required and must not be TBD" in result["blockers"]


def test_missing_approval_timestamp_is_rejected() -> None:
    form = _valid_real_form()
    form["approval_timestamp"] = None
    result = _evaluate(form)
    assert result["real_approval_intake_accepted"] is False
    assert "approval_timestamp is required" in result["blockers"]


def test_explicit_human_approval_false_is_rejected() -> None:
    form = _valid_real_form()
    form["explicit_human_approval"] = False
    result = _evaluate(form)
    assert result["real_approval_intake_accepted"] is False
    assert "explicit_human_approval must be true" in result["blockers"]


def test_reject_decision_is_rejected() -> None:
    form = _valid_real_form()
    form["approval_decision"] = "REJECT"
    result = _evaluate(form)
    assert result["real_approval_intake_accepted"] is False
    assert "approval_decision must be APPROVE" in result["blockers"]


def test_missing_rollback_plan_ref_is_rejected() -> None:
    form = _valid_real_form()
    form["rollback_plan_ref"] = ""
    result = _evaluate(form)
    assert result["real_approval_intake_accepted"] is False
    assert "rollback_plan_ref is required" in result["blockers"]


def test_valid_real_approval_form_builds_acceptance_context_preview() -> None:
    result = _evaluate(_valid_real_form())
    preview = result["acceptance_context_preview"]
    assert result["real_approval_intake_accepted"] is True
    assert isinstance(preview, dict)
    assert preview["reviewer"] == "REAL_REVIEWER_001"
    assert preview["explicit_human_approval"] is True
    assert preview["production_enablement_allowed"] is False
    assert preview["ui_launch_allowed"] is False
    assert preview["production_migration_allowed"] is False


def test_generated_acceptance_context_passes_p29_structurally() -> None:
    result = _evaluate(_valid_real_form())
    preview = result["acceptance_context_preview"]
    gate = evaluate_metadata_registry_acceptance(_candidate_records(), preview)
    assert gate["accepted"] is True
    assert gate["production_metadata_registry_accepted"] is True
    assert gate["blockers"] == []


def test_generated_context_still_does_not_enable_runtime_production() -> None:
    result = _evaluate(_valid_real_form())
    preview = result["acceptance_context_preview"]
    preflight = result["runtime_enablement_preflight_result"]
    assert preview["production_enablement_allowed"] is False
    assert preview["runtime_config_change_allowed"] is False
    assert preflight["runtime_enablement_ready"] is False
    assert "operator_signoff must be true" in preflight["blockers"]


def test_ui_remains_blocked() -> None:
    result = _evaluate(_valid_real_form())
    preview = result["acceptance_context_preview"]
    assert preview["ui_launch_allowed"] is False
    assert result["ui_can_start"] is False


def test_production_migration_remains_blocked() -> None:
    result = _evaluate(_valid_real_form())
    preview = result["acceptance_context_preview"]
    assert preview["production_migration_allowed"] is False
    assert result["production_migration_can_start"] is False


def test_no_production_db_access() -> None:
    result = _evaluate(_valid_real_form())
    assert "db" not in json.dumps(result).lower()
