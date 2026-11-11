from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import evaluate_metadata_registry_acceptance
from wbc_backend.reporting.strategy_replay_runtime_enablement_preflight import evaluate_runtime_enablement_preflight


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
SIM_CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.SIMULATION_ONLY.json"
REAL_TEMPLATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.REAL_APPROVAL_TEMPLATE.json"
REVIEW_READY_CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.review_ready.draft.json"
CANDIDATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry.production_candidate.draft.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _accepted_gate() -> dict[str, object]:
    candidate = _load(CANDIDATE_PATH)
    simulation_context = _load(SIM_CONTEXT_PATH)
    return evaluate_metadata_registry_acceptance(candidate["records"], simulation_context)


def _rejected_gate() -> dict[str, object]:
    candidate = _load(CANDIDATE_PATH)
    review_ready_context = _load(REVIEW_READY_CONTEXT_PATH)
    return evaluate_metadata_registry_acceptance(candidate["records"], review_ready_context)


def _runtime_context(**overrides: object) -> dict[str, object]:
    context = {
        "accepted_registry_path": str(CANDIDATE_PATH),
        "accepted_acceptance_context_path": str(SIM_CONTEXT_PATH),
        "acceptance_gate_passed": True,
        "acceptance_gate_pass_evidence_refs": ["P32_STRATEGY_REPLAY_METADATA_REGISTRY_APPROVAL_SIMULATION_READY"],
        "runtime_metadata_registry_path": str(CANDIDATE_PATH),
        "runtime_metadata_registry_path_configured_explicitly": True,
        "strict_mode_enabled": True,
        "non_strict_fallback_allowed": False,
        "rollback_switch_available": True,
        "fixture_validation_rerun_passed": True,
        "synthetic_future_row_dry_run_passed": True,
        "historical_backfill_disabled": True,
        "production_ui_launch_blocked": True,
        "production_migration_blocked": True,
        "monitoring_audit_log_plan_ready": True,
        "operator_signoff": False,
    }
    context.update(overrides)
    return context


def test_real_approval_template_defaults_rejected() -> None:
    template = _load(REAL_TEMPLATE_PATH)
    assert template["approval_decision"] == "REJECT"
    assert template["explicit_human_approval"] is False
    assert template["production_enablement_allowed"] is False
    assert template["runtime_config_change_allowed"] is False
    assert template["ui_launch_allowed"] is False
    assert template["production_migration_allowed"] is False
    assert template["production_metadata_registry_accepted"] is False


def test_real_approval_template_does_not_pass_acceptance_gate() -> None:
    candidate = _load(CANDIDATE_PATH)
    real_template = _load(REAL_TEMPLATE_PATH)
    gate = evaluate_metadata_registry_acceptance(candidate["records"], real_template)
    assert gate["accepted"] is False
    assert gate["production_metadata_registry_accepted"] is False
    assert real_template["reviewer"] == "TBD_REAL_REVIEWER"
    assert "approval_timestamp is required" in gate["blockers"]
    assert "explicit_human_approval must be true" in gate["blockers"]


def test_simulation_only_approval_is_not_real_approval() -> None:
    simulation_context = _load(SIM_CONTEXT_PATH)
    assert simulation_context["real_approval"] is False
    assert simulation_context["production_enablement_allowed"] is False
    assert simulation_context["runtime_config_change_allowed"] is False
    assert simulation_context["ui_launch_allowed"] is False
    assert simulation_context["production_migration_allowed"] is False


def test_runtime_enablement_preflight_requires_accepted_registry() -> None:
    gate = _rejected_gate()
    preflight = evaluate_runtime_enablement_preflight(
        gate,
        _runtime_context(acceptance_gate_passed=False),
    )
    assert preflight["runtime_enablement_ready"] is False
    assert "accepted registry gate must pass" in preflight["blockers"]
    assert "operator_signoff must be true" in preflight["blockers"]


def test_runtime_enablement_preflight_blocks_ui_and_production_migration() -> None:
    gate = _accepted_gate()
    preflight = evaluate_runtime_enablement_preflight(gate, _runtime_context())
    assert any("production_ui_launch_blocked" not in blocker for blocker in preflight["blockers"])
    assert "operator_signoff must be true" in preflight["blockers"]


def test_review_ready_context_stays_unapproved() -> None:
    context = _load(REVIEW_READY_CONTEXT_PATH)
    assert context["explicit_human_approval"] is False
    assert context["reviewer"] == ""


def test_no_production_db_access() -> None:
    template = _load(REAL_TEMPLATE_PATH)
    assert "db" not in json.dumps(template).lower()
