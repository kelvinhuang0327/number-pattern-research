"""
tests/test_p146a_observation_only_live_monitoring_runner.py
===========================================================
Verification tests for P146A: Observation-only live monitoring runner.

Validates the JSON artifact, Markdown report, and live DB state.
No DB writes. No monitoring executed. No scheduler installed. No live API called.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "p146a_observation_only_live_monitoring_runner.py"
ARTIFACT = (
    REPO_ROOT / "outputs" / "replay" /
    "p146a_observation_only_live_monitoring_runner_20260529.json"
)
MD_PATH = (
    REPO_ROOT / "docs" / "replay" /
    "p146a_observation_only_live_monitoring_runner_20260529.md"
)
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CLASSIFICATION = "P146A_OBSERVATION_ONLY_MONITORING_RUNNER_READY"
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
EXPECTED_OBSERVATION_FIELDS = [
    "monitored_strategy_id",
    "lottery_type",
    "target_draw",
    "prediction_generated_at",
    "draw_result_available_at",
    "predicted_numbers",
    "actual_numbers",
    "hit_count",
    "evaluation_status",
    "source_trace",
    "monitoring_truth_level",
    "created_at",
]
EXPECTED_AUTH_PHRASE = (
    "P145B_AUTHORIZED_MANUAL_ON_DEMAND_MONITORING_OBSERVATION_ONLY_FOR_6_WAVE2_CANDIDATES_20260529"
)


@pytest.fixture(scope="module", autouse=True)
def generate_p146a_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "P146A" in result.stdout or result.stdout.strip()


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P146A JSON not found: {ARTIFACT}"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


# ── Basic identity ─────────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P146A"


def test_classification(artifact):
    assert artifact["classification"] == EXPECTED_CLASSIFICATION


# ── Repo / branch ──────────────────────────────────────────────────────────────

def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


# ── DB snapshot ────────────────────────────────────────────────────────────────

def test_db_total_rows(artifact):
    assert artifact["db_snapshot"]["total_rows"] == EXPECTED_ROWS


def test_bet_index_column_exists(artifact):
    assert artifact["db_snapshot"]["bet_index_column_exists"] is True


# ── Predecessor artifacts ──────────────────────────────────────────────────────

def test_p145b_classification(artifact):
    assert (
        artifact["p145b_source_summary"]["classification"]
        == "P145B_MANUAL_ON_DEMAND_MONITORING_AUTHORIZATION_GATE_READY"
    )


def test_p144b_classification(artifact):
    assert (
        artifact["p144b_source_summary"]["classification"]
        == "P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_READY"
    )


# ── Monitoring candidate inventory ────────────────────────────────────────────

def test_candidate_inventory_count(artifact):
    assert len(artifact["monitoring_candidate_inventory"]) == EXPECTED_CANDIDATE_COUNT


def test_all_candidate_ids_present(artifact):
    ids = [c["strategy_id"] for c in artifact["monitoring_candidate_inventory"]]
    for expected_id in EXPECTED_CANDIDATES:
        assert expected_id in ids, f"Missing candidate: {expected_id}"


# ── Runner contract ────────────────────────────────────────────────────────────

def test_runner_contract_output_mode(artifact):
    assert artifact["runner_contract"]["output_mode"] == "file_artifact_only"


def test_runner_contract_no_db_write(artifact):
    assert artifact["runner_contract"]["production_db_write"] is False


def test_runner_contract_no_live_api(artifact):
    assert artifact["runner_contract"]["live_api_call"] is False


def test_runner_contract_supports_fixture(artifact):
    assert artifact["runner_contract"]["supports_fixture_input"] is True


# ── Observation record schema ─────────────────────────────────────────────────

def test_observation_schema_has_12_fields(artifact):
    fields = artifact["observation_record_schema"]["fields"]
    assert len(fields) == 12, f"Expected 12 fields, got {len(fields)}"


def test_observation_schema_all_required_fields(artifact):
    fields = artifact["observation_record_schema"]["fields"]
    for required_field in EXPECTED_OBSERVATION_FIELDS:
        assert required_field in fields, f"Missing required field: {required_field}"


# ── Historical vs live boundary ────────────────────────────────────────────────

def test_historical_backfill_not_live_evidence(artifact):
    assert artifact["historical_vs_live_boundary"]["historical_backfill_is_not_live_evidence"] is True


def test_mock_fixture_not_live_evidence(artifact):
    assert artifact["historical_vs_live_boundary"]["mock_fixture_is_not_live_evidence"] is True


def test_champion_eval_not_ready_from_p146a(artifact):
    assert artifact["historical_vs_live_boundary"]["champion_eval_ready_from_p146a"] is False


# ── Runner readiness matrix ────────────────────────────────────────────────────

def test_runner_readiness_matrix_count(artifact):
    assert len(artifact["runner_readiness_matrix"]) == EXPECTED_CANDIDATE_COUNT


def test_runner_readiness_all_supported(artifact):
    for row in artifact["runner_readiness_matrix"]:
        assert row["runner_supported"] is True, f"runner_supported False for {row['strategy_id']}"
        assert row["fixture_smoke_supported"] is True, f"fixture_smoke_supported False for {row['strategy_id']}"
        assert row["ready_for_authorized_p146b_run"] is True, f"p146b ready False for {row['strategy_id']}"


def test_runner_readiness_no_db_write(artifact):
    for row in artifact["runner_readiness_matrix"]:
        assert row["db_write_required"] is False, f"db_write_required True for {row['strategy_id']}"


# ── Fixture smoke result ───────────────────────────────────────────────────────

def test_smoke_no_live_api(artifact):
    assert artifact["fixture_smoke_result"]["live_api_called"] is False


def test_smoke_no_db_write(artifact):
    assert artifact["fixture_smoke_result"]["production_db_written"] is False


def test_smoke_schema_valid(artifact):
    assert artifact["fixture_smoke_result"]["output_record_schema_valid"] is True


def test_smoke_passed(artifact):
    assert artifact["fixture_smoke_result"]["smoke_passed"] is True


def test_smoke_monitoring_truth_level(artifact):
    assert artifact["fixture_smoke_result"]["monitoring_truth_level"] == "MOCK_OBSERVATION_ONLY"


# ── P146B execution plan ───────────────────────────────────────────────────────

def test_p146b_auth_phrase(artifact):
    assert artifact["p146b_execution_plan"]["required_authorization_phrase"] == EXPECTED_AUTH_PHRASE


def test_p146b_no_db_write(artifact):
    assert artifact["p146b_execution_plan"]["production_db_write_allowed"] is False


# ── Non-actions ────────────────────────────────────────────────────────────────

def test_no_db_write_in_p146a(artifact):
    assert artifact["non_actions"]["db_write_in_p146a"] is False


def test_no_live_api_called(artifact):
    assert artifact["non_actions"]["live_api_called"] is False


def test_no_scheduler_installed(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_no_live_monitoring_run(artifact):
    assert artifact["non_actions"]["live_monitoring_run_executed_in_p146a"] is False


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


def test_no_forbidden_files_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ── Markdown file ─────────────────────────────────────────────────────────────

def test_markdown_exists():
    assert MD_PATH.exists(), f"P146A Markdown not found: {MD_PATH}"
