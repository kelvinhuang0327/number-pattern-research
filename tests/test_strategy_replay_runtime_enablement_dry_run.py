from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.reporting.strategy_replay_metadata_registry_acceptance import evaluate_metadata_registry_acceptance
from wbc_backend.reporting.strategy_replay_runtime_enablement_preflight import evaluate_runtime_enablement_preflight


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
CANDIDATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry.production_candidate.draft.json"
REAL_TEMPLATE_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.REAL_APPROVAL_TEMPLATE.json"
SIMULATION_CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_metadata_registry_acceptance_context.SIMULATION_ONLY.json"
DRY_RUN_CONTEXT_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_runtime_enablement_context.DRY_RUN.json"
CONFIG_PREVIEW_PATH = ROOT / "00-BettingPlan/20260510/strategy_replay_runtime_metadata_config_preview.DRY_RUN.json"


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _accepted_gate() -> dict[str, object]:
    candidate = _load(CANDIDATE_PATH)
    simulation_context = _load(SIMULATION_CONTEXT_PATH)
    return evaluate_metadata_registry_acceptance(candidate["records"], simulation_context)


def _rejected_gate() -> dict[str, object]:
    candidate = _load(CANDIDATE_PATH)
    real_template = _load(REAL_TEMPLATE_PATH)
    return evaluate_metadata_registry_acceptance(candidate["records"], real_template)


def test_real_approval_template_path_remains_blocked() -> None:
    gate = _rejected_gate()
    assert gate["accepted"] is False
    assert gate["production_metadata_registry_accepted"] is False
    assert gate["blockers"]


def test_simulation_only_path_passes_structural_acceptance() -> None:
    gate = _accepted_gate()
    assert gate["accepted"] is True
    assert gate["production_metadata_registry_accepted"] is True
    assert gate["blockers"] == []


def test_dry_run_context_blocks_production_enablement() -> None:
    gate = _rejected_gate()
    dry_run_context = _load(DRY_RUN_CONTEXT_PATH)
    preflight = evaluate_runtime_enablement_preflight(gate, dry_run_context)
    assert dry_run_context["mode"] == "DRY_RUN"
    assert dry_run_context["production_enablement_allowed"] is False
    assert dry_run_context["runtime_config_change_allowed"] is False
    assert dry_run_context["ui_launch_allowed"] is False
    assert dry_run_context["production_migration_allowed"] is False
    assert preflight["runtime_enablement_ready"] is False
    assert "accepted registry gate must pass" in preflight["blockers"]
    assert "operator_signoff must be true" in preflight["blockers"]


def test_dry_run_context_blocks_runtime_config_changes() -> None:
    dry_run_context = _load(DRY_RUN_CONTEXT_PATH)
    assert dry_run_context["runtime_config_change_allowed"] is False
    assert dry_run_context["strict_mode_enabled"] is True
    assert dry_run_context["historical_backfill_disabled"] is True


def test_dry_run_config_preview_is_no_op() -> None:
    preview = _load(CONFIG_PREVIEW_PATH)
    assert preview["artifact_kind"] == "DRY_RUN_NO_OP"
    assert preview["production_enabled"] is False
    assert preview["preview_only"] is True
    assert preview["env_preview"]["STRATEGY_REPLAY_METADATA_ENABLEMENT_MODE"] == "DRY_RUN"


def test_ui_and_production_migration_remain_blocked() -> None:
    dry_run_context = _load(DRY_RUN_CONTEXT_PATH)
    assert dry_run_context["ui_launch_allowed"] is False
    assert dry_run_context["production_migration_allowed"] is False


def test_no_production_db_access() -> None:
    preview = _load(CONFIG_PREVIEW_PATH)
    assert "db" not in json.dumps(preview).lower()
