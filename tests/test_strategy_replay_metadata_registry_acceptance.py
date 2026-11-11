from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_metadata_registry import build_strategy_metadata_record
from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import (
    build_metadata_registry_acceptance_checklist,
    evaluate_metadata_registry_acceptance,
    identify_metadata_registry_acceptance_blockers,
    summarize_metadata_registry_acceptance,
)


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
EXAMPLE_REGISTRY_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry.example.json"


def _valid_record(**overrides: object) -> dict[str, object]:
    record = build_strategy_metadata_record(
        strategy_id="strategy.pool_c.ml_v1",
        strategy_name="Pool C ML v1",
        current_lifecycle_state="online",
        lifecycle_state_source="explicit_registry",
        lifecycle_state_updated_at="2026-05-10T08:00:00Z",
        owner_module="wbc_backend.reporting.strategy_registry",
        audit_source="strategy_registry_seed",
        allowed_for_future_writes=True,
    )
    record.update(overrides)
    return record


def _acceptance_context(**overrides: object) -> dict[str, object]:
    context = {
        "registry_path": str(EXAMPLE_REGISTRY_PATH),
        "registry_owner": "wbc_backend.reporting.strategy_registry",
        "reviewer": "strategy.replay.acceptance",
        "approval_timestamp": "2026-05-10T13:00:00Z",
        "production_candidate": True,
        "non_production_example": False,
        "audit_evidence_refs": ["P28C fixture validation report"],
        "lifecycle_source_refs": ["explicit_registry", "runtime_metadata_injection"],
        "runtime_injection_test_passed": True,
        "e2e_fixture_validation_passed": True,
        "explicit_human_approval": True,
        "rollback_plan_ref": "rollback-plan-v1",
        "allowed_for_future_writes_only": True,
        "allowed_for_historical_backfill": False,
    }
    context.update(overrides)
    return context


def _example_registry_records() -> list[dict[str, object]]:
    payload = json.loads(EXAMPLE_REGISTRY_PATH.read_text(encoding="utf-8"))
    return [dict(record) for record in payload["records"]]


def test_example_registry_is_rejected() -> None:
    gate = evaluate_metadata_registry_acceptance(_example_registry_records(), _acceptance_context(non_production_example=True, production_candidate=False))
    assert gate["production_metadata_registry_accepted"] is False
    assert any("non-production example" in blocker for blocker in gate["blockers"])


def test_missing_human_approval_rejects() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context(explicit_human_approval=False))
    assert gate["accepted"] is False
    assert "explicit_human_approval must be true" in gate["blockers"]


def test_missing_owner_rejects() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context(registry_owner=""))
    assert "registry_owner is required" in gate["blockers"]


def test_missing_reviewer_rejects() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context(reviewer=""))
    assert "reviewer is required" in gate["blockers"]


def test_missing_audit_evidence_rejects() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context(audit_evidence_refs=[]))
    assert "audit_evidence_refs must not be empty" in gate["blockers"]


def test_missing_lifecycle_source_refs_rejects() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context(lifecycle_source_refs=[]))
    assert "lifecycle_source_refs must not be empty" in gate["blockers"]


def test_runtime_injection_not_passed_rejects() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context(runtime_injection_test_passed=False))
    assert "runtime_injection_test_passed must be true" in gate["blockers"]


def test_fixture_validation_not_passed_rejects() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context(e2e_fixture_validation_passed=False))
    assert "e2e_fixture_validation_passed must be true" in gate["blockers"]


def test_historical_backfill_true_rejects() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context(allowed_for_historical_backfill=True))
    assert "allowed_for_historical_backfill must be false" in gate["blockers"]


def test_invalid_record_rejects() -> None:
    invalid_record = _valid_record(strategy_name="")
    gate = evaluate_metadata_registry_acceptance([invalid_record], _acceptance_context())
    assert gate["accepted"] is False
    assert any("record 1 invalid" in blocker for blocker in gate["blockers"])


def test_valid_production_candidate_accepts() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context())
    assert gate["production_metadata_registry_accepted"] is True
    assert gate["blockers"] == []


def test_acceptance_checklist_includes_blockers() -> None:
    checklist_result = build_metadata_registry_acceptance_checklist(
        _example_registry_records(),
        _acceptance_context(non_production_example=True, production_candidate=False, registry_owner=""),
    )
    checklist_names = {item["check"] for item in checklist_result["checklist"]}
    assert "production_candidate" in checklist_names
    assert "registry_owner" in checklist_names
    assert checklist_result["blockers"]


def test_summary_shapes_acceptance_result_without_db_access() -> None:
    gate = evaluate_metadata_registry_acceptance([_valid_record()], _acceptance_context())
    summary = summarize_metadata_registry_acceptance(gate)
    assert summary["production_metadata_registry_accepted"] is True
    assert summary["record_count"] == 1
    assert "db" not in json.dumps(summary).lower()
