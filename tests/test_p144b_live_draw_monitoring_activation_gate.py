"""
tests/test_p144b_live_draw_monitoring_activation_gate.py
=========================================================
Verification tests for P144B: Live draw monitoring activation gate.

Validates the JSON artifact, Markdown report, and live DB state.
No DB writes. No monitoring activated. No scheduler installed.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "p144b_live_draw_monitoring_activation_gate.py"
ARTIFACT = REPO_ROOT / "outputs" / "replay" / "p144b_live_draw_monitoring_activation_gate_20260529.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p144b_live_draw_monitoring_activation_gate_20260529.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CLASSIFICATION = "P144B_LIVE_DRAW_MONITORING_ACTIVATION_GATE_READY"
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

REQUIRED_CONTRACT_FIELDS = [
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


@pytest.fixture(scope="module", autouse=True)
def generate_p144b_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "P144B" in result.stdout or result.stdout.strip()


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P144B JSON not found: {ARTIFACT}"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ── Basic identity ────────────────────────────────────────────────────────────

def test_artifact_exists():
    assert ARTIFACT.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P144B"


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


# ── Predecessor source summaries ──────────────────────────────────────────────

def test_p144a_classification(artifact):
    assert artifact["p144a_source_summary"]["classification"] == "P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY"


def test_p143_classification(artifact):
    assert artifact["p143_source_summary"]["classification"] == "P143_POST_WAVE2_GOVERNANCE_READINESS_PLAN_READY"


def test_p142_classification(artifact):
    assert artifact["p142_source_summary"]["classification"] == "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED"


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


# ── Live monitoring contract ──────────────────────────────────────────────────

def test_live_monitoring_contract_exists(artifact):
    assert "live_monitoring_contract" in artifact


def test_live_monitoring_contract_has_all_required_fields(artifact):
    contract_fields = artifact["live_monitoring_contract"]["fields"]
    for field in REQUIRED_CONTRACT_FIELDS:
        assert field in contract_fields, f"Contract missing field: {field}"


def test_live_monitoring_contract_monitored_strategy_id(artifact):
    assert "monitored_strategy_id" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_lottery_type(artifact):
    assert "lottery_type" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_target_draw(artifact):
    assert "target_draw" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_prediction_generated_at(artifact):
    assert "prediction_generated_at" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_draw_result_available_at(artifact):
    assert "draw_result_available_at" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_predicted_numbers(artifact):
    assert "predicted_numbers" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_actual_numbers(artifact):
    assert "actual_numbers" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_hit_count(artifact):
    assert "hit_count" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_evaluation_status(artifact):
    assert "evaluation_status" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_source_trace(artifact):
    assert "source_trace" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_monitoring_truth_level(artifact):
    assert "monitoring_truth_level" in artifact["live_monitoring_contract"]["fields"]


def test_live_monitoring_contract_created_at(artifact):
    assert "created_at" in artifact["live_monitoring_contract"]["fields"]


# ── Historical vs live data boundary ─────────────────────────────────────────

def test_boundary_historical_backfill_is_not_live_evidence(artifact):
    assert artifact["historical_vs_live_data_boundary"]["historical_backfill_is_not_live_evidence"] is True


def test_boundary_live_evidence_requires_monitoring_run(artifact):
    assert artifact["historical_vs_live_data_boundary"]["live_evidence_requires_post_apply_monitoring_run"] is True


def test_boundary_champion_eval_not_ready_from_live_data(artifact):
    assert artifact["historical_vs_live_data_boundary"]["champion_eval_ready_from_live_data"] is False


def test_boundary_historical_backfill_actual_numbers_may_exist(artifact):
    assert artifact["historical_vs_live_data_boundary"]["historical_backfill_actual_numbers_count_may_exist"] is True


# ── Live monitoring readiness matrix ─────────────────────────────────────────

def test_readiness_matrix_count(artifact):
    assert len(artifact["live_monitoring_readiness_matrix"]) == EXPECTED_CANDIDATE_COUNT


def test_readiness_matrix_has_all_strategies(artifact):
    matrix_ids = [row["strategy_id"] for row in artifact["live_monitoring_readiness_matrix"]]
    for sid in EXPECTED_CANDIDATES:
        assert sid in matrix_ids, f"Missing from matrix: {sid}"


def test_all_matrix_entries_monitoring_not_ready(artifact):
    for row in artifact["live_monitoring_readiness_matrix"]:
        assert row["monitoring_ready"] is False, (
            f"{row['strategy_id']} unexpectedly monitoring_ready=True"
        )


def test_all_matrix_entries_no_live_evidence(artifact):
    for row in artifact["live_monitoring_readiness_matrix"]:
        assert row["live_evidence_available_now"] is False, (
            f"{row['strategy_id']} unexpectedly live_evidence_available_now=True"
        )


def test_all_matrix_entries_authorization_required_later(artifact):
    for row in artifact["live_monitoring_readiness_matrix"]:
        assert row["authorization_required_later"] is True, (
            f"{row['strategy_id']} unexpectedly authorization_required_later=False"
        )


# ── Monitoring activation options ────────────────────────────────────────────

def test_activation_options_has_option_a(artifact):
    assert "option_a_manual_on_demand_monitoring" in artifact["monitoring_activation_options"]


def test_activation_options_has_option_b(artifact):
    assert "option_b_scheduled_monitoring_after_authorization" in artifact["monitoring_activation_options"]


def test_activation_options_has_option_c(artifact):
    assert "option_c_observation_only_file_artifact_before_db_write" in artifact["monitoring_activation_options"]


def test_option_a_no_db_write(artifact):
    assert artifact["monitoring_activation_options"]["option_a_manual_on_demand_monitoring"]["db_write_in_p144b"] is False


def test_option_b_no_db_write(artifact):
    assert artifact["monitoring_activation_options"]["option_b_scheduled_monitoring_after_authorization"]["db_write_in_p144b"] is False


def test_option_c_no_db_write(artifact):
    assert artifact["monitoring_activation_options"]["option_c_observation_only_file_artifact_before_db_write"]["db_write_in_p144b"] is False


def test_option_c_zero_risk(artifact):
    assert artifact["monitoring_activation_options"]["option_c_observation_only_file_artifact_before_db_write"]["risk"] == "ZERO"


def test_recommended_monitoring_path(artifact):
    assert artifact["recommended_monitoring_path"] == "option_c"


# ── Authorization phrase templates ────────────────────────────────────────────

def test_authorization_templates_exist(artifact):
    assert "authorization_phrase_templates" in artifact


def test_authorization_templates_not_executed(artifact):
    templates = artifact["authorization_phrase_templates"]
    assert "P145B" in templates.get("execution_gate", "")


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p144b"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p144b"] is False


def test_no_replay_rows_inserted(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p144b"] == 0


def test_no_replay_rows_deleted(artifact):
    assert artifact["non_actions"]["replay_rows_deleted_in_p144b"] == 0


def test_registry_update_not_executed(artifact):
    assert artifact["non_actions"]["registry_update_executed_in_p144b"] is False


def test_champion_promotion_not_executed(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p144b"] is False


def test_monitoring_not_activated(artifact):
    assert artifact["non_actions"]["monitoring_activated_in_p144b"] is False


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


# ── Drift guard ───────────────────────────────────────────────────────────────

def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_result"]["status"] == "PASS"


def test_drift_guard_total_rows(artifact):
    assert artifact["drift_guard_result"]["total_rows"] == EXPECTED_ROWS


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
        "Predecessor Artifact Summaries",
        "Monitoring Candidate Inventory",
        "Historical vs Live Data Boundary",
        "Live Monitoring Contract",
        "Live Monitoring Readiness Matrix",
        "Monitoring Activation Options",
        "Authorization Phrase Templates",
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


def test_markdown_contains_option_c():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "Observation-Only File Artifact" in text or "option_c" in text


# ── Live DB constraints ───────────────────────────────────────────────────────

def test_live_db_total_rows(db_conn):
    count = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert count == EXPECTED_ROWS


def test_live_db_bet_index_schema(db_conn):
    cols = [row[1] for row in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    assert "bet_index" in cols


def test_live_db_all_candidates_present(db_conn):
    for sid in EXPECTED_CANDIDATES:
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
            (sid,),
        ).fetchone()[0]
        assert cnt > 0, f"Strategy {sid} has no rows in DB"


def test_live_db_no_live_monitoring_rows(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE truth_level='LIVE_MONITORING_VERIFIED'"
    ).fetchone()[0]
    assert cnt == 0, f"Expected 0 LIVE_MONITORING_VERIFIED rows, got {cnt}"


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
