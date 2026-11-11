from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_metadata_registry import validate_strategy_metadata_registry
from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import evaluate_metadata_registry_acceptance


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
CANDIDATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry.production_candidate.draft.json"
CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.draft.json"


def _load_candidate() -> dict[str, object]:
    return json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))


def _load_context() -> dict[str, object]:
    return json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))


def test_candidate_draft_has_required_registry_shape() -> None:
    candidate = _load_candidate()
    assert candidate["production_candidate"] is True
    assert candidate["accepted"] is False
    assert candidate["runtime_enabled"] is False
    assert candidate["non_production_example"] is False
    assert candidate["review_status"] == "draft_only"
    assert isinstance(candidate["records"], list)
    summary = validate_strategy_metadata_registry(candidate["records"])
    assert summary["invalid_records"] == 0


def test_candidate_records_keep_future_writes_only_and_no_backfill() -> None:
    candidate = _load_candidate()
    for record in candidate["records"]:
        assert record["allowed_for_future_writes"] is True
        assert record["allowed_for_historical_backfill"] is False


def test_candidate_draft_is_not_runtime_enabled() -> None:
    candidate = _load_candidate()
    assert candidate["runtime_enabled"] is False


def test_context_without_human_approval_is_rejected() -> None:
    candidate = _load_candidate()
    gate = evaluate_metadata_registry_acceptance(candidate["records"], _load_context())
    assert gate["production_metadata_registry_accepted"] is False
    assert "explicit_human_approval must be true" in gate["blockers"]
    assert "rollback_plan_ref is required" in gate["blockers"]


def test_no_production_db_access() -> None:
    candidate = _load_candidate()
    assert "db" not in json.dumps(candidate).lower()
