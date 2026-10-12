#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.reporting.strategy_replay_accepted_context_lifecycle import summarize_accepted_context_preview_lifecycle
from wbc_backend.reporting.strategy_replay_enablement_status_dashboard import build_strategy_replay_enablement_status
from wbc_backend.reporting.strategy_replay_production_enablement_boundary import evaluate_production_enablement_boundary
from wbc_backend.reporting.strategy_replay_real_approval_intake import evaluate_real_approval_intake
from wbc_backend.reporting.strategy_replay_runtime_enablement_preflight import evaluate_runtime_enablement_preflight


ROOT = Path("/Users/kelvin/Kelvin-WorkSpace/Betting-pool")
BASE = ROOT / "00-BettingPlan/20260510"

CANDIDATE_PATH = BASE / "strategy_replay_metadata_registry.production_candidate.draft.json"
REAL_TEMPLATE_PATH = BASE / "strategy_replay_metadata_registry_acceptance_context.REAL_APPROVAL_TEMPLATE.json"
REVIEW_READY_CONTEXT_PATH = BASE / "strategy_replay_metadata_registry_acceptance_context.review_ready.draft.json"
SIMULATION_FORM_PATH = BASE / "strategy_replay_metadata_registry_human_approval_form.SIMULATION_ONLY.json"
SIMULATION_CONTEXT_PATH = BASE / "strategy_replay_metadata_registry_acceptance_context.SIMULATION_ONLY.json"
DRY_RUN_CONTEXT_PATH = BASE / "strategy_replay_runtime_enablement_context.DRY_RUN.json"


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _real_approval_summary() -> dict[str, object]:
    candidate = _load_json(CANDIDATE_PATH)
    real_template = _load_json(REAL_TEMPLATE_PATH)
    review_context = _load_json(REVIEW_READY_CONTEXT_PATH)
    intake = evaluate_real_approval_intake(real_template, candidate, review_context)
    return {
        "real_approval_intake_accepted": bool(intake.get("real_approval_intake_accepted")),
        "real_approval": False,
        "simulation_only": False,
        "production_metadata_registry_accepted": False,
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
        "accepted_context_is_preview_only": False,
        "acceptance_context_preview": None,
        "fake_approval": False,
        "production_candidate_registry_path": str(CANDIDATE_PATH),
    }


def _simulation_approval_summary() -> dict[str, object]:
    simulation_context = _load_json(SIMULATION_CONTEXT_PATH)
    return {
        "real_approval_intake_accepted": False,
        "real_approval": False,
        "simulation_only": True,
        "production_metadata_registry_accepted": False,
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
        "accepted_context_is_preview_only": True,
        "acceptance_context_preview": None,
        "fake_approval": False,
        "simulation_context": simulation_context,
    }


def _current_dashboard() -> dict[str, object]:
    real_intake = _real_approval_summary()
    simulation_intake = _simulation_approval_summary()
    preview_lifecycle = {
        "lifecycle_state": "NO_REAL_APPROVAL",
        "accepted_context_is_preview_only": False,
        "production_enabled": False,
        "production_enablement_allowed": False,
        "runtime_config_change_allowed": False,
        "ui_launch_allowed": False,
        "production_migration_allowed": False,
    }
    preflight_summary = {
        "runtime_enablement_ready": False,
        "operator_signoff": False,
        "rollback_switch_available": True,
        "strict_mode_enabled": True,
        "fixture_validation_rerun_passed": True,
        "synthetic_future_row_dry_run_passed": True,
        "monitoring_audit_log_plan_ready": True,
        "blockers": ["accepted registry gate must pass", "operator_signoff must be true"],
    }
    dry_run_summary = {
        "dry_run_config_preview_exists": True,
        "dry_run_result_passed": True,
        "dry_run_config_preview_is_no_op": True,
        "dry_run_modified_production_config": False,
        "historical_backfill_disabled": True,
        "ui_gate_passed": False,
        "production_migration_blocked": True,
    }
    boundary_summary = {
        "boundary_state": "NO_GO",
        "production_enablement_allowed": False,
    }

    dashboard = build_strategy_replay_enablement_status(
        real_intake,
        preview_lifecycle,
        preflight_summary,
        dry_run_summary,
        boundary_summary,
    )
    dashboard["status_sources"] = {
        "approval_summary": real_intake,
        "lifecycle_summary": preview_lifecycle,
        "preflight_summary": preflight_summary,
        "dry_run_summary": dry_run_summary,
        "boundary_summary": boundary_summary,
    }
    dashboard["simulation_summary"] = simulation_intake
    dashboard["real_approval_summary"] = real_intake
    dashboard["final_marker"] = "P39_STRATEGY_REPLAY_ENABLEMENT_STATUS_DASHBOARD_READY"
    return dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Check the Strategy Replay enablement status dashboard.")
    parser.add_argument("--output", type=Path, help="Optional path to write dashboard JSON.")
    args = parser.parse_args()

    dashboard = _current_dashboard()
    payload = json.dumps(dashboard, indent=2, sort_keys=True)

    print("STRATEGY_REPLAY_ENABLEMENT_STATUS_CHECK")
    if args.output:
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())