"""
tests/test_p145b_manual_on_demand_monitoring_authorization_gate.py
==================================================================
Verification tests for P145B: Manual on-demand monitoring authorization gate.

Validates the JSON artifact, Markdown report, and live DB state.
No DB writes. No monitoring executed. No scheduler installed.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "p145b_manual_on_demand_monitoring_authorization_gate.py"
ARTIFACT = REPO_ROOT / "outputs" / "replay" / "p145b_manual_on_demand_monitoring_authorization_gate_20260529.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p145b_manual_on_demand_monitoring_authorization_gate_20260529.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CLASSIFICATION = "P145B_MANUAL_ON_DEMAND_MONITORING_AUTHORIZATION_GATE_READY"
EXPECTED_ROWS = 94924
EXPECTED_CANDIDATE_COUNT = 6
EXPECTED_CANDIDATES = [
    "acb_markov_midfreq_3bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "pp3_freqort_4bet",
    "power_precision_3bet",
    "power_orthogonal_5bet",
]
EXPECTED_CONTRACT_FIELD_COUNT = 12
EXPECTED_AUTH_PHRASE = (
    "P145B_AUTHORIZED_MANUAL_ON_DEMAND_MONITORING_OBSERVATION_ONLY_FOR_6_WAVE2_CANDIDATES_20260529"
)


@pytest.fixture(scope="module", autouse=True)
def generate_p145b_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "P145B" in result.stdout or result.stdout.strip()


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P145B JSON not found: {ARTIFACT}"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


# ── Basic identity ────────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P145B"


def test_classification(artifact):
    assert artifact["classification"] == EXPECTED_CLASSIFICATION


# ── Repo / branch ─────────────────────────────────────────────────────────────

def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_canonical_branch(artifact):
    assert artifact["canonical_branch"] == "claude/zen-gates-ff6802"


# ── DB snapshot ───────────────────────────────────────────────────────────────

def test_db_total_rows(artifact):
    assert artifact["db_snapshot"]["total_rows"] == EXPECTED_ROWS


def test_bet_index_column_exists(artifact):
    assert artifact["db_snapshot"]["bet_index_column_exists"] is True


# ── P144B source summary ──────────────────────────────────────────────────────

def test_p144b_classification(artifact):
    assert artifact["p144b_source_summary"]["classification"] == "P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_READY"


def test_p144a_classification(artifact):
    assert artifact["p144a_source_summary"]["classification"] == "P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY"


def test_p143_classification(artifact):
    assert artifact["p143_source_summary"]["classification"] == "P143_POST_WAVE2_GOVERNANCE_READINESS_PLAN_READY"


# ── Monitoring candidate inventory ────────────────────────────────────────────

def test_candidate_inventory_count(artifact):
    assert len(artifact["monitoring_candidate_inventory"]) == EXPECTED_CANDIDATE_COUNT


def test_candidate_inventory_has_all_strategies(artifact):
    inv_ids = [item["strategy_id"] for item in artifact["monitoring_candidate_inventory"]]
    for sid in EXPECTED_CANDIDATES:
        assert sid in inv_ids, f"Missing candidate: {sid}"


def test_all_candidates_no_live_evidence(artifact):
    for item in artifact["monitoring_candidate_inventory"]:
        assert item["live_evidence_available_now"] is False, (
            f"{item['strategy_id']} unexpectedly has live evidence"
        )


def test_all_candidates_monitoring_candidate(artifact):
    for item in artifact["monitoring_candidate_inventory"]:
        assert item["live_monitoring_candidate"] is True


# ── Monitoring contract validation ────────────────────────────────────────────

def test_monitoring_contract_validation_exists(artifact):
    assert "monitoring_contract_validation" in artifact


def test_contract_fields_count(artifact):
    assert artifact["monitoring_contract_validation"]["required_contract_fields_count"] == EXPECTED_CONTRACT_FIELD_COUNT


def test_contract_complete(artifact):
    assert artifact["monitoring_contract_validation"]["contract_complete"] is True


def test_historical_backfill_is_not_live_evidence(artifact):
    assert artifact["monitoring_contract_validation"]["historical_backfill_is_not_live_evidence"] is True


def test_live_evidence_requires_monitoring_run(artifact):
    assert artifact["monitoring_contract_validation"]["live_evidence_requires_post_apply_monitoring_run"] is True


def test_contract_has_all_required_fields(artifact):
    required = artifact["monitoring_contract_validation"]["required_contract_fields"]
    expected = [
        "monitored_strategy_id", "lottery_type", "target_draw", "prediction_generated_at",
        "draw_result_available_at", "predicted_numbers", "actual_numbers", "hit_count",
        "evaluation_status", "source_trace", "monitoring_truth_level", "created_at",
    ]
    for f in expected:
        assert f in required, f"Contract missing field: {f}"


# ── Manual on-demand authorization gate ──────────────────────────────────────

def test_authorization_gate_exists(artifact):
    assert "manual_on_demand_authorization_gate" in artifact


def test_authorization_phrase_template(artifact):
    gate = artifact["manual_on_demand_authorization_gate"]
    assert gate["exact_authorization_phrase_template"] == EXPECTED_AUTH_PHRASE


def test_authorization_required_before_execution(artifact):
    assert artifact["manual_on_demand_authorization_gate"]["authorization_required_before_execution"] is True


def test_execution_not_performed_in_p145b(artifact):
    assert artifact["manual_on_demand_authorization_gate"]["execution_performed_in_p145b"] is False


def test_production_db_write_not_allowed(artifact):
    assert artifact["manual_on_demand_authorization_gate"]["production_db_write_allowed"] is False


def test_observation_only_file_artifact_allowed_later(artifact):
    assert artifact["manual_on_demand_authorization_gate"]["observation_only_file_artifact_allowed_later"] is True


# ── Observation-only execution plan ──────────────────────────────────────────

def test_observation_only_plan_exists(artifact):
    assert "observation_only_execution_plan" in artifact


def test_obs_plan_no_production_db_write(artifact):
    assert artifact["observation_only_execution_plan"]["production_db_write"] is False


def test_obs_plan_no_scheduler_install(artifact):
    assert artifact["observation_only_execution_plan"]["scheduler_install"] is False


def test_obs_plan_no_live_api_call(artifact):
    assert artifact["observation_only_execution_plan"]["live_api_call"] is False


def test_obs_plan_output_mode(artifact):
    assert artifact["observation_only_execution_plan"]["output_mode"] == "file_artifact_only"


def test_obs_plan_next_gate(artifact):
    assert artifact["observation_only_execution_plan"]["next_execution_gate"] == "P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION"


def test_obs_plan_recommended_directory(artifact):
    assert "live_monitoring_observation_only" in artifact["observation_only_execution_plan"]["recommended_output_directory"]


# ── Per-strategy monitoring plan ─────────────────────────────────────────────

def test_per_strategy_plan_count(artifact):
    assert len(artifact["per_strategy_monitoring_plan"]) == EXPECTED_CANDIDATE_COUNT


def test_per_strategy_plan_has_all_strategies(artifact):
    plan_ids = [ps["strategy_id"] for ps in artifact["per_strategy_monitoring_plan"]]
    for sid in EXPECTED_CANDIDATES:
        assert sid in plan_ids, f"Missing from per_strategy_monitoring_plan: {sid}"


def test_per_strategy_plan_no_db_write(artifact):
    for ps in artifact["per_strategy_monitoring_plan"]:
        assert ps["db_write_required"] is False, f"{ps['strategy_id']} unexpectedly has db_write_required=True"


def test_per_strategy_plan_no_scheduler(artifact):
    for ps in artifact["per_strategy_monitoring_plan"]:
        assert ps["scheduler_required"] is False, f"{ps['strategy_id']} unexpectedly has scheduler_required=True"


def test_per_strategy_plan_status_authorization_pending(artifact):
    for ps in artifact["per_strategy_monitoring_plan"]:
        assert ps["current_status"] == "authorization_pending", (
            f"{ps['strategy_id']} has unexpected status: {ps['current_status']}"
        )


def test_per_strategy_plan_monitoring_truth_level(artifact):
    for ps in artifact["per_strategy_monitoring_plan"]:
        assert ps["monitoring_truth_level"] == "LIVE_MONITORING_VERIFIED", (
            f"{ps['strategy_id']} has unexpected truth_level: {ps['monitoring_truth_level']}"
        )


# ── Runner availability assessment ───────────────────────────────────────────

def test_runner_availability_exists(artifact):
    assert "runner_availability_assessment" in artifact


def test_runner_implementation_required(artifact):
    assert artifact["runner_availability_assessment"]["implementation_required_before_execution"] is True


def test_runner_fields_present(artifact):
    runner = artifact["runner_availability_assessment"]
    assert "existing_runner_found" in runner
    assert "existing_runner_path" in runner
    assert "runner_missing" in runner
    assert "fixture_or_mock_available" in runner


def test_runner_found_missing_consistent(artifact):
    runner = artifact["runner_availability_assessment"]
    # existing_runner_found and runner_missing must be consistent (inverse of each other)
    assert runner["existing_runner_found"] != runner["runner_missing"]


# ── Authorization phrase templates ────────────────────────────────────────────

def test_authorization_phrase_templates_exist(artifact):
    assert "authorization_phrase_templates" in artifact


def test_auth_phrase_template_matches_gate(artifact):
    templates = artifact["authorization_phrase_templates"]
    gate = artifact["manual_on_demand_authorization_gate"]
    assert templates["manual_on_demand_observation_only"] == gate["exact_authorization_phrase_template"]


def test_auth_phrase_next_gate(artifact):
    assert artifact["authorization_phrase_templates"]["next_gate"] == "P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION"


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p145b"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p145b"] is False


def test_no_replay_rows_inserted(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p145b"] == 0


def test_no_replay_rows_deleted(artifact):
    assert artifact["non_actions"]["replay_rows_deleted_in_p145b"] == 0


def test_registry_update_not_executed(artifact):
    assert artifact["non_actions"]["registry_update_executed_in_p145b"] is False


def test_champion_promotion_not_executed(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p145b"] is False


def test_monitoring_run_not_executed(artifact):
    assert artifact["non_actions"]["monitoring_run_executed_in_p145b"] is False


def test_no_scheduler_installed(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_no_live_api_called(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_four_star(artifact):
    assert artifact["non_actions"]["four_star_executed"] is False


def test_no_p108(artifact):
    assert artifact["non_actions"]["p108_executed"] is False


def test_no_p117(artifact):
    assert artifact["non_actions"]["p117_executed"] is False


def test_no_p118(artifact):
    assert artifact["non_actions"]["p118_executed"] is False


# ── Dirty file hygiene ────────────────────────────────────────────────────────

def test_backups_untracked_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_autouse_regen_risk_noted(artifact):
    assert artifact["dirty_file_hygiene"]["p135_p136_p142_autouse_regen_risk_noted"] is True


def test_no_forbidden_files_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ── Markdown ──────────────────────────────────────────────────────────────────

def test_markdown_exists():
    assert MD_PATH.exists()


def test_markdown_classification():
    text = MD_PATH.read_text(encoding="utf-8")
    assert EXPECTED_CLASSIFICATION in text


def test_markdown_sections():
    text = MD_PATH.read_text(encoding="utf-8")
    for section in [
        "Executive Summary",
        "Canonical Repo / Branch Confirmation",
        "P144B Recap",
        "Monitoring Contract Validation",
        "Manual On-Demand Authorization Gate",
        "Observation-Only Execution Plan",
        "Per-Strategy Monitoring Plan",
        "Runner Availability Assessment",
        "Authorization Phrase Template",
        "Explicit Non-Actions",
        "Dirty File Hygiene Note",
        "Remaining Risks",
        "Recommended Next Task",
        "Final Classification",
    ]:
        assert section in text, f"Missing Markdown section: {section}"


def test_markdown_contains_all_candidates():
    text = MD_PATH.read_text(encoding="utf-8")
    for sid in EXPECTED_CANDIDATES:
        assert sid in text, f"Candidate {sid} missing from Markdown"


def test_markdown_contains_auth_phrase():
    text = MD_PATH.read_text(encoding="utf-8")
    assert EXPECTED_AUTH_PHRASE in text


def test_markdown_contains_next_gate():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "P146_LIVE_MONITORING_FIRST_DRAW_EVALUATION" in text


# ── Forbidden staging check ───────────────────────────────────────────────────

def test_no_forbidden_files_staged_git():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    staged = result.stdout.splitlines()
    forbidden = ("lottery_v2.db", ".history", ".pid", ".runtime")
    assert not any(any(token in item for token in forbidden) for item in staged)
