from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import evaluate_metadata_registry_acceptance


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
REVIEW_READY_CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.review_ready.draft.json"
SIM_CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.SIMULATION_ONLY.json"
APPROVAL_FORM_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_human_approval_form.SIMULATION_ONLY.json"
CANDIDATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry.production_candidate.draft.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_real_review_ready_context_remains_rejected() -> None:
    candidate = _load(CANDIDATE_PATH)
    context = _load(REVIEW_READY_CONTEXT_PATH)
    gate = evaluate_metadata_registry_acceptance(candidate["records"], context)
    assert gate["accepted"] is False
    assert gate["production_metadata_registry_accepted"] is False
    assert gate["blockers"] == [
        "reviewer is required",
        "approval_timestamp is required",
        "explicit_human_approval must be true",
    ]


def test_simulation_only_context_satisfies_structural_gate() -> None:
    candidate = _load(CANDIDATE_PATH)
    context = _load(SIM_CONTEXT_PATH)
    gate = evaluate_metadata_registry_acceptance(candidate["records"], context)
    assert gate["accepted"] is True
    assert gate["production_metadata_registry_accepted"] is True
    assert gate["blockers"] == []


def test_simulation_only_approval_does_not_enable_production_controls() -> None:
    approval_form = _load(APPROVAL_FORM_PATH)
    context = _load(SIM_CONTEXT_PATH)
    assert approval_form["production_enablement_allowed"] is False
    assert approval_form["runtime_config_change_allowed"] is False
    assert approval_form["ui_launch_allowed"] is False
    assert approval_form["production_migration_allowed"] is False
    assert context["production_enablement_allowed"] is False
    assert context["runtime_config_change_allowed"] is False
    assert context["ui_launch_allowed"] is False
    assert context["production_migration_allowed"] is False
    assert context["real_approval"] is False


def test_real_review_ready_context_file_remains_unapproved() -> None:
    context = _load(REVIEW_READY_CONTEXT_PATH)
    assert context["explicit_human_approval"] is False
    assert context["reviewer"] == ""
    assert context["approval_timestamp"] in (None, "")


def test_no_production_db_access() -> None:
    approval_form = _load(APPROVAL_FORM_PATH)
    assert "db" not in json.dumps(approval_form).lower()
