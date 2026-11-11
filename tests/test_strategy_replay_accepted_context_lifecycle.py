from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_accepted_context_lifecycle import (
    NO_REAL_APPROVAL,
    PREVIEW_GENERATED_NOT_ENABLED,
    PREFLIGHT_BLOCKED,
    READY_FOR_OPERATOR_ENABLEMENT_REVIEW,
    build_accepted_context_preview_lifecycle_notice,
    classify_accepted_context_preview_state,
)
from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import evaluate_metadata_registry_acceptance
from wbc_backend.reporting.strategy_replay_real_approval_intake import build_acceptance_context_from_real_approval
from wbc_backend.reporting.strategy_replay_runtime_enablement_preflight import evaluate_runtime_enablement_preflight


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
CANDIDATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry.production_candidate.draft.json"
REAL_TEMPLATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.REAL_APPROVAL_TEMPLATE.json"
ROLLBACK_PLAN_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_rollback_plan.draft.md"
EVIDENCE_PACK_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_production_candidate_evidence_pack.md"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _candidate_records() -> list[dict[str, object]]:
    return _load(CANDIDATE_PATH)["records"]  # type: ignore[index]


def _real_form() -> dict[str, object]:
    return {
        "artifact_kind": "REAL_APPROVAL",
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
            "./.venv/bin/python -m pytest tests/test_strategy_replay_real_approval_intake.py tests/test_strategy_replay_metadata_registry_real_approval_preflight.py tests/test_strategy_replay_runtime_enablement_dry_run.py -q",
        ],
        "reviewer_notes": "Preview only; runtime enablement remains a later phase.",
        "real_approval": True,
        "simulation_only": False,
        "review_status": "submitted",
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
        "production_metadata_registry_accepted": False,
    }


def _preview_context() -> dict[str, object]:
    preview = build_acceptance_context_from_real_approval(_real_form(), _load(REAL_TEMPLATE_PATH))
    assert preview is not None
    return preview


def _accepted_gate() -> dict[str, object]:
    return evaluate_metadata_registry_acceptance(_candidate_records(), _preview_context())


def test_no_real_approval_maps_to_no_real_approval_state() -> None:
    notice = build_accepted_context_preview_lifecycle_notice(None, {})
    assert classify_accepted_context_preview_state(None) == NO_REAL_APPROVAL
    assert notice["lifecycle_state"] == NO_REAL_APPROVAL
    assert "NO_REAL_APPROVAL_FORM" in notice["blockers"]


def test_preview_context_without_enablement_maps_to_preview_state() -> None:
    preview = _preview_context()
    assert classify_accepted_context_preview_state(preview) == PREVIEW_GENERATED_NOT_ENABLED


def test_blocked_preflight_maps_to_prefight_blocked_state() -> None:
    preview = _preview_context()
    gate = _accepted_gate()
    preflight = evaluate_runtime_enablement_preflight(gate, preview)
    notice = build_accepted_context_preview_lifecycle_notice(preview, preflight)
    assert notice["lifecycle_state"] == PREFLIGHT_BLOCKED
    assert notice["production_enabled"] is False
    assert "RUNTIME_PREFLIGHT_BLOCKED" in notice["blockers"]
    assert "OPERATOR_SIGNOFF_REQUIRED" in notice["blockers"]


def test_preflight_pass_without_operator_signoff_maps_to_review_ready_state() -> None:
    preview = _preview_context()
    synthetic_preflight = {
        "runtime_enablement_ready": True,
        "blockers": [],
    }
    notice = build_accepted_context_preview_lifecycle_notice(preview, synthetic_preflight)
    assert notice["lifecycle_state"] == READY_FOR_OPERATOR_ENABLEMENT_REVIEW
    assert notice["production_enabled"] is False
    assert "OPERATOR_SIGNOFF_REQUIRED" in notice["blockers"]
    assert "PRODUCTION_CONFIG_CHANGE_NOT_ALLOWED" in notice["blockers"]


def test_helper_never_returns_production_enabled() -> None:
    preview = _preview_context()
    gate = _accepted_gate()
    preflight = evaluate_runtime_enablement_preflight(gate, preview)
    notice = build_accepted_context_preview_lifecycle_notice(preview, preflight)
    assert notice["production_enabled"] is False
    assert notice["production_enablement_allowed"] is False


def test_preview_context_is_not_production_enablement() -> None:
    preview = _preview_context()
    assert preview["production_enablement_allowed"] is False
    assert preview["runtime_config_change_allowed"] is False
    assert preview["ui_launch_allowed"] is False
    assert preview["production_migration_allowed"] is False


def test_ui_remains_blocked() -> None:
    preview = _preview_context()
    gate = _accepted_gate()
    preflight = evaluate_runtime_enablement_preflight(gate, preview)
    notice = build_accepted_context_preview_lifecycle_notice(preview, preflight)
    assert notice["ui_launch_allowed"] is False


def test_production_migration_remains_blocked() -> None:
    preview = _preview_context()
    gate = _accepted_gate()
    preflight = evaluate_runtime_enablement_preflight(gate, preview)
    notice = build_accepted_context_preview_lifecycle_notice(preview, preflight)
    assert notice["production_migration_allowed"] is False


def test_no_production_db_access() -> None:
    preview = _preview_context()
    assert "db" not in json.dumps(preview).lower()
