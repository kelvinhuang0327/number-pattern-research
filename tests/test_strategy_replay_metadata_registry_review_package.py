from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_metadata_registry import validate_strategy_metadata_registry
from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import evaluate_metadata_registry_acceptance


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
APPROVAL_FORM_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_human_approval_form.template.json"
CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.review_ready.draft.json"
CANDIDATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry.production_candidate.draft.json"


def test_approval_form_defaults_to_reject() -> None:
    approval_form = json.loads(APPROVAL_FORM_PATH.read_text(encoding="utf-8"))
    assert approval_form["approval_decision"] == "REJECT"
    assert approval_form["explicit_human_approval"] is False
    assert approval_form["production_metadata_registry_accepted"] is False


def test_review_ready_context_includes_rollback_plan_ref() -> None:
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    assert context["rollback_plan_ref"].endswith("strategy_replay_metadata_registry_rollback_plan.draft.md")
    assert context["allowed_for_historical_backfill"] is False


def test_review_ready_context_still_fails_without_human_fields() -> None:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    gate = evaluate_metadata_registry_acceptance(candidate["records"], context)
    assert gate["accepted"] is False
    assert "reviewer is required" in gate["blockers"]
    assert "approval_timestamp is required" in gate["blockers"]
    assert "explicit_human_approval must be true" in gate["blockers"]
    assert "rollback_plan_ref is required" not in gate["blockers"]


def test_review_package_registry_shape_remains_valid() -> None:
    candidate = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    summary = validate_strategy_metadata_registry(candidate["records"])
    assert summary["invalid_records"] == 0


def test_no_production_db_access() -> None:
    approval_form = json.loads(APPROVAL_FORM_PATH.read_text(encoding="utf-8"))
    assert "db" not in json.dumps(approval_form).lower()
