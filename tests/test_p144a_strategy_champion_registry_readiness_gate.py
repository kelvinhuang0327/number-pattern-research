"""
tests/test_p144a_strategy_champion_registry_readiness_gate.py
=============================================================
Verification tests for P144A: Strategy champion registry readiness gate.

Validates the JSON artifact, Markdown report, and live DB state.
No DB writes. No registry mutation. No champion promotion.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "p144a_strategy_champion_registry_readiness_gate.py"
ARTIFACT = REPO_ROOT / "outputs" / "replay" / "p144a_strategy_champion_registry_readiness_gate_20260529.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p144a_strategy_champion_registry_readiness_gate_20260529.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CLASSIFICATION = "P144A_STRATEGY_CHAMPION_REGISTRY_READINESS_GATE_READY"
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


@pytest.fixture(scope="module", autouse=True)
def generate_p144a_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "P144A" in result.stdout or result.stdout.strip()


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P144A JSON not found: {ARTIFACT}"
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
    assert artifact["task_id"] == "P144A"


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


def test_bet_index_schema_exists(artifact):
    assert artifact["db_snapshot"]["bet_index_schema_exists"] is True


# ── Source summaries ──────────────────────────────────────────────────────────

def test_p143_classification(artifact):
    assert artifact["p143_source_summary"]["classification"] == "P143_POST_WAVE2_GOVERNANCE_READINESS_PLAN_READY"


def test_p143_no_registry_update(artifact):
    assert artifact["p143_source_summary"]["registry_update_executed_in_p143"] is False


def test_p142_classification(artifact):
    assert artifact["p142_source_summary"]["classification"] == "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED"


def test_p142_total_inserted_rows(artifact):
    assert artifact["p142_source_summary"]["total_wave2_multibet_inserted_rows"] == 22502


# ── Candidate strategy inventory ─────────────────────────────────────────────

def test_candidate_inventory_count(artifact):
    assert len(artifact["candidate_strategy_inventory"]) == EXPECTED_CANDIDATE_COUNT


def test_candidate_inventory_has_all_strategies(artifact):
    inv = artifact["candidate_strategy_inventory"]
    for sid in EXPECTED_CANDIDATES:
        assert sid in inv, f"Missing candidate: {sid}"


def test_acb_markov_inventory(artifact):
    row = artifact["candidate_strategy_inventory"]["acb_markov_midfreq_3bet"]
    assert row["lottery_type"] == "DAILY_539"
    assert row["bet_count"] == 3
    assert row["wave2_task_source"] == "P131"
    assert row["inserted_rows"] == 3000
    assert row["legacy_unverified_rows"] == 0


def test_power_orthogonal_inventory(artifact):
    row = artifact["candidate_strategy_inventory"]["power_orthogonal_5bet"]
    assert row["lottery_type"] == "POWER_LOTTO"
    assert row["bet_count"] == 5
    assert row["wave2_task_source"] == "P141"
    assert row["inserted_rows"] == 6000
    assert row["legacy_unverified_rows"] == 50


def test_power_precision_inventory(artifact):
    row = artifact["candidate_strategy_inventory"]["power_precision_3bet"]
    assert row["lottery_type"] == "POWER_LOTTO"
    assert row["bet_count"] == 3
    assert row["wave2_task_source"] == "P140"
    assert row["inserted_rows"] == 3000
    assert row["legacy_unverified_rows"] == 50


def test_all_candidates_no_live_draw_data(artifact):
    for sid in EXPECTED_CANDIDATES:
        row = artifact["candidate_strategy_inventory"][sid]
        assert row["live_draw_data_available"] is False, f"{sid} unexpectedly has live draw data"


def test_all_candidates_not_champion_eval_ready(artifact):
    for sid in EXPECTED_CANDIDATES:
        row = artifact["candidate_strategy_inventory"][sid]
        assert row["champion_eval_ready"] is False


def test_all_candidates_registry_update_not_allowed_now(artifact):
    for sid in EXPECTED_CANDIDATES:
        row = artifact["candidate_strategy_inventory"][sid]
        assert row["registry_update_allowed_now"] is False


# ── Champion registry readiness matrix ───────────────────────────────────────

def test_matrix_count(artifact):
    assert len(artifact["champion_registry_readiness_matrix"]) == EXPECTED_CANDIDATE_COUNT


def test_matrix_has_all_strategies(artifact):
    matrix = artifact["champion_registry_readiness_matrix"]
    for sid in EXPECTED_CANDIDATES:
        assert sid in matrix, f"Missing from matrix: {sid}"


def test_matrix_all_status_no_live_data(artifact):
    matrix = artifact["champion_registry_readiness_matrix"]
    for sid in EXPECTED_CANDIDATES:
        assert matrix[sid]["current_status"] == "REPLAY_ROWS_APPLIED_NO_LIVE_DATA"


def test_matrix_all_not_eval_ready(artifact):
    matrix = artifact["champion_registry_readiness_matrix"]
    for sid in EXPECTED_CANDIDATES:
        assert matrix[sid]["champion_eval_ready"] is False


def test_matrix_all_not_update_allowed(artifact):
    matrix = artifact["champion_registry_readiness_matrix"]
    for sid in EXPECTED_CANDIDATES:
        assert matrix[sid]["registry_update_allowed_now"] is False


def test_matrix_recommended_action(artifact):
    matrix = artifact["champion_registry_readiness_matrix"]
    for sid in EXPECTED_CANDIDATES:
        assert matrix[sid]["recommended_action"] == "ADD_TO_OBSERVATION_WATCHLIST"


# ── Registry update options ───────────────────────────────────────────────────

def test_registry_options_has_option_a(artifact):
    assert "option_a_wait_for_live_monitoring_data" in artifact["registry_update_options"]


def test_registry_options_has_option_b(artifact):
    assert "option_b_observation_only_watchlist" in artifact["registry_update_options"]


def test_registry_options_has_option_c(artifact):
    assert "option_c_promote_after_minimum_live_draw_threshold" in artifact["registry_update_options"]


def test_option_a_no_registry_mutation(artifact):
    assert artifact["registry_update_options"]["option_a_wait_for_live_monitoring_data"]["registry_mutation"] is False


def test_option_b_no_registry_mutation(artifact):
    assert artifact["registry_update_options"]["option_b_observation_only_watchlist"]["registry_mutation"] is False


def test_option_c_registry_mutation_required(artifact):
    assert artifact["registry_update_options"]["option_c_promote_after_minimum_live_draw_threshold"]["registry_mutation"] is True


def test_option_a_recommended(artifact):
    assert artifact["registry_update_options"]["option_a_wait_for_live_monitoring_data"]["recommended"] is True


def test_option_b_recommended(artifact):
    assert artifact["registry_update_options"]["option_b_observation_only_watchlist"]["recommended"] is True


# ── Recommended registry path ─────────────────────────────────────────────────

def test_recommended_path_no_registry_mutation(artifact):
    assert artifact["recommended_registry_path"]["registry_mutation_in_p144a"] is False


def test_recommended_path_next_gate(artifact):
    assert "P145" in artifact["recommended_registry_path"]["next_gate"]


# ── Authorization gate required later ────────────────────────────────────────

def test_auth_gate_p144b_present(artifact):
    assert "p144b_live_monitoring_gate" in artifact["authorization_gate_required_later"]


def test_auth_gate_p144c_present(artifact):
    assert "p144c_legacy_unverified_remediation_gate" in artifact["authorization_gate_required_later"]


def test_auth_gate_p145_present(artifact):
    assert "p145_observation_watchlist_and_live_monitoring_gate" in artifact["authorization_gate_required_later"]


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write(artifact):
    assert artifact["non_actions"]["db_write_in_p144a"] is False


def test_no_controlled_apply(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p144a"] is False


def test_no_replay_rows_inserted(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p144a"] == 0


def test_no_replay_rows_deleted(artifact):
    assert artifact["non_actions"]["replay_rows_deleted_in_p144a"] == 0


def test_registry_update_not_executed(artifact):
    assert artifact["non_actions"]["registry_update_executed_in_p144a"] is False


def test_champion_promotion_not_executed(artifact):
    assert artifact["non_actions"]["champion_promotion_executed_in_p144a"] is False


def test_no_monitoring_activated(artifact):
    assert artifact["non_actions"]["monitoring_activated_in_p144a"] is False


def test_no_scheduler_installed(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_no_four_star(artifact):
    assert artifact["non_actions"]["four_star_executed"] is False


# ── Drift guard ───────────────────────────────────────────────────────────────

def test_drift_guard_pass(artifact):
    assert artifact["drift_guard_result"]["status"] == "PASS"


def test_drift_guard_total_rows(artifact):
    assert artifact["drift_guard_result"]["total_rows"] == EXPECTED_ROWS


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
        "P143 Recap",
        "P142 Closure Recap",
        "Candidate Strategy Inventory",
        "Champion Registry Readiness Matrix",
        "Registry Update Options",
        "Recommended Registry Path",
        "Authorization Gate Required Later",
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


def test_markdown_contains_option_b():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "Observation-Only Watchlist" in text


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


def test_live_db_legacy_rows(db_conn):
    for sid in ("power_precision_3bet", "power_orthogonal_5bet"):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id=? AND truth_level='LEGACY_UNVERIFIED'",
            (sid,),
        ).fetchone()[0]
        assert cnt == 50


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
