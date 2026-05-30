"""
Tests for P148C: Local Draw Result Source Audit Gate
"""

import json
import os
import glob
import sqlite3

import pytest

REPO_ROOT = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
P148C_JSON = os.path.join(
    REPO_ROOT,
    "outputs/replay/p148c_local_draw_result_source_audit_gate_20260529.json",
)
P148C_MD = os.path.join(
    REPO_ROOT,
    "docs/replay/p148c_local_draw_result_source_audit_gate_20260529.md",
)
DB_PATH = os.path.join(REPO_ROOT, "lottery_api/data/lottery_v2.db")

ALLOWED_CLASSIFICATIONS = {
    "P148C_LOCAL_DRAW_RESULT_SOURCE_FOUND_READY_FOR_P148D",
    "P148C_LOCAL_DRAW_RESULT_FOUND_BUT_NOT_LIVE_VERIFIED_ELIGIBLE",
    "P148C_BLOCKED_PENDING_MANUAL_DRAW_RESULT_INPUT",
}


@pytest.fixture(scope="module")
def p148c_data():
    assert os.path.exists(P148C_JSON), f"P148C JSON not found: {P148C_JSON}"
    with open(P148C_JSON) as f:
        return json.load(f)


# ---- Core artifact existence ----

def test_p148c_json_exists():
    assert os.path.exists(P148C_JSON), f"P148C JSON not found: {P148C_JSON}"


def test_p148c_markdown_exists():
    assert os.path.exists(P148C_MD), f"P148C Markdown not found: {P148C_MD}"


# ---- Task identity ----

def test_task_id(p148c_data):
    assert p148c_data["task_id"] == "P148C"


def test_classification_is_allowed(p148c_data):
    cls = p148c_data["classification"]
    assert cls in ALLOWED_CLASSIFICATIONS, (
        f"Unexpected classification: {cls}. Allowed: {ALLOWED_CLASSIFICATIONS}"
    )


# ---- Repo / branch ----

def test_repo_ok(p148c_data):
    assert p148c_data["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(p148c_data):
    assert p148c_data["repo_branch_check"]["branch_ok"] is True


# ---- DB snapshot ----

def test_db_rows_94924(p148c_data):
    assert p148c_data["db_snapshot"]["row_count"] == 94924


def test_bet_index_column_exists(p148c_data):
    assert p148c_data["db_snapshot"]["bet_index_column_exists"] is True


def test_drift_guard_pass(p148c_data):
    assert p148c_data["db_snapshot"]["drift_guard_pass"] is True


# ---- Predecessor artifact classifications ----

def test_p148b_classification(p148c_data):
    assert (
        p148c_data["p148b_source_summary"]["classification"]
        == "P148B_BLOCKED_PENDING_MANUAL_DRAW_RESULT_INPUT"
    )


def test_p148_classification(p148c_data):
    assert (
        p148c_data["p148_source_summary"]["classification"]
        == "P148_LIVE_MONITORING_VERIFIED_EVIDENCE_COLLECTION_GATE_READY"
    )


def test_p147_classification(p148c_data):
    assert (
        p148c_data["p147_source_summary"]["classification"]
        == "P147_CHAMPION_EVALUATION_BLOCKED_PENDING_LIVE_MONITORING_VERIFIED"
    )


# ---- Candidate strategy draw audit ----

def test_candidate_strategy_audit_has_6_strategies(p148c_data):
    audit = p148c_data["candidate_strategy_draw_audit"]
    assert len(audit) == 6, f"Expected 6 strategies, got {len(audit)}"


def test_candidate_strategy_ids_present(p148c_data):
    audit = p148c_data["candidate_strategy_draw_audit"]
    ids = {s["strategy_id"] for s in audit}
    expected = {
        "acb_markov_midfreq_3bet",
        "midfreq_fourier_mk_3bet",
        "fourier_rhythm_3bet",
        "pp3_freqort_4bet",
        "power_precision_3bet",
        "power_orthogonal_5bet",
    }
    assert ids == expected, f"Mismatch: got={ids}, expected={expected}"


# ---- P146B target draw audit ----

def test_p146b_daily539_target_draw(p148c_data):
    p146b = p148c_data["p146b_target_draw_audit"]
    assert "DAILY_539" in p146b
    assert p146b["DAILY_539"]["target_draw"] == "115000072"


def test_p146b_power_lotto_target_draw(p148c_data):
    p146b = p148c_data["p146b_target_draw_audit"]
    assert "POWER_LOTTO" in p146b
    assert p146b["POWER_LOTTO"]["target_draw"] == "1894"


def test_p146b_daily539_not_post_apply_eligible(p148c_data):
    p146b = p148c_data["p146b_target_draw_audit"]
    assert p146b["DAILY_539"]["is_post_apply_eligible"] is False


def test_p146b_power_lotto_not_post_apply_eligible(p148c_data):
    p146b = p148c_data["p146b_target_draw_audit"]
    assert p146b["POWER_LOTTO"]["is_post_apply_eligible"] is False


# ---- LIVE_MONITORING_VERIFIED status ----

def test_live_monitoring_verified_record_not_created_in_p148c(p148c_data):
    status = p148c_data["live_verified_evidence_creation_status"]
    assert status["live_monitoring_verified_record_created_in_p148c"] is False


def test_p148d_required_for_record_creation(p148c_data):
    status = p148c_data["live_verified_evidence_creation_status"]
    assert status["p148d_required_for_record_creation"] is True


def test_champion_evaluation_not_unlocked_in_p148c(p148c_data):
    status = p148c_data["live_verified_evidence_creation_status"]
    assert status["champion_evaluation_unlocked_in_p148c"] is False


# ---- Non-actions ----

def test_non_action_db_write(p148c_data):
    assert p148c_data["non_actions"]["db_write_in_p148c"] is False


def test_non_action_live_api_called(p148c_data):
    assert p148c_data["non_actions"]["live_api_called"] is False


def test_non_action_controlled_apply(p148c_data):
    assert p148c_data["non_actions"]["controlled_apply_executed_in_p148c"] is False


def test_non_action_registry_update(p148c_data):
    assert p148c_data["non_actions"]["registry_update_executed_in_p148c"] is False


def test_non_action_champion_promotion(p148c_data):
    assert p148c_data["non_actions"]["champion_promotion_executed_in_p148c"] is False


def test_non_action_scheduler(p148c_data):
    assert p148c_data["non_actions"]["scheduler_installed"] is False


def test_non_action_four_star(p148c_data):
    assert p148c_data["non_actions"]["four_star_executed"] is False


def test_non_action_p108(p148c_data):
    assert p148c_data["non_actions"]["p108_executed"] is False


def test_non_action_p117(p148c_data):
    assert p148c_data["non_actions"]["p117_executed"] is False


def test_non_action_p118(p148c_data):
    assert p148c_data["non_actions"]["p118_executed"] is False


# ---- Dirty file hygiene ----

def test_backups_untracked_not_staged(p148c_data):
    assert p148c_data["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


# ---- Markdown content checks ----

def test_markdown_contains_correction_of_p148b_assumption():
    with open(P148C_MD) as f:
        content = f.read()
    assert "Correction of P148B Assumption" in content or "P148B assumption" in content.lower() or "MOCK_OBSERVATION_ONLY" in content


def test_markdown_contains_explicit_non_actions():
    with open(P148C_MD) as f:
        content = f.read()
    assert "Explicit Non-Actions" in content or "non_actions" in content.lower() or "db_write_in_p148c" in content


def test_markdown_contains_classification():
    with open(P148C_MD) as f:
        content = f.read()
    assert "P148C_LOCAL_DRAW_RESULT_FOUND_BUT_NOT_LIVE_VERIFIED_ELIGIBLE" in content or \
           "P148C_LOCAL_DRAW_RESULT_SOURCE_FOUND_READY_FOR_P148D" in content or \
           "P148C_BLOCKED_PENDING_MANUAL_DRAW_RESULT_INPUT" in content


# ---- DB staging scan ----

def test_db_not_staged():
    """Verify DB file is not staged in git."""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    staged = result.stdout.strip().splitlines()
    db_files_staged = [f for f in staged if "lottery_v2.db" in f]
    assert not db_files_staged, f"DB file is staged: {db_files_staged}"


def test_history_files_not_staged():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    staged = result.stdout.strip().splitlines()
    history_files = [f for f in staged if "history" in f.lower() or ".pid" in f or "runtime" in f]
    assert not history_files, f"History/runtime/pid files staged: {history_files}"


def test_pycache_not_staged():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    staged = result.stdout.strip().splitlines()
    pycache_files = [f for f in staged if "__pycache__" in f or f.endswith(".pyc")]
    assert not pycache_files, f"Pycache files staged: {pycache_files}"


# ---- Live DB check ----

def test_no_live_monitoring_verified_in_db():
    """Verify no LIVE_MONITORING_VERIFIED rows exist in DB (P148C must not create any)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE truth_level = 'LIVE_MONITORING_VERIFIED';")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 0, f"Unexpected LIVE_MONITORING_VERIFIED rows: {count}"


def test_db_total_rows_still_94924():
    """Verify DB row count unchanged after P148C (no writes)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays;")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 94924, f"DB rows changed: {count} != 94924"
