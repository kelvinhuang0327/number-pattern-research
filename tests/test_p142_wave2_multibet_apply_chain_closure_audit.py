"""
tests/test_p142_wave2_multibet_apply_chain_closure_audit.py
===========================================================
Verification tests for P142: Wave 2 multi-bet apply chain closure audit.

Validates the JSON artifact, Markdown report, and live DB state.
No DB writes. No controlled_apply.
"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "p142_wave2_multibet_apply_chain_closure_audit.py"
ARTIFACT = REPO_ROOT / "outputs" / "replay" / "p142_wave2_multibet_apply_chain_closure_audit_20260529.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p142_wave2_multibet_apply_chain_closure_audit_20260529.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CLASSIFICATION = "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED"
EXPECTED_ROWS = 94924


@pytest.fixture(scope="module", autouse=True)
def generate_p142_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "P142" in result.stdout or result.stdout.strip()


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P142 JSON not found: {ARTIFACT}"
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
    assert artifact["task_id"] == "P142"


def test_classification(artifact):
    assert artifact["classification"] == EXPECTED_CLASSIFICATION


# ── Repo / branch ─────────────────────────────────────────────────────────────

def test_repo_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(artifact):
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_canonical_repo(artifact):
    assert "zen-gates-ff6802" in artifact["canonical_repo"]


def test_canonical_branch(artifact):
    assert artifact["canonical_branch"] == "claude/zen-gates-ff6802"


# ── DB snapshot ───────────────────────────────────────────────────────────────

def test_db_total_rows(artifact):
    assert artifact["db_snapshot"]["total_rows"] == EXPECTED_ROWS


def test_db_rows_match_expected(artifact):
    assert artifact["db_snapshot"]["rows_match_expected"] is True


def test_bet_index_schema_exists(artifact):
    assert artifact["db_snapshot"]["bet_index_schema_exists"] is True


# ── Source artifact classifications ──────────────────────────────────────────

def test_p141_classification(artifact):
    assert artifact["source_artifact_summary"]["p141"]["classification"] == "P141_POWER_ORTHOGONAL_5BET_APPLIED"


def test_p141a_classification(artifact):
    assert artifact["source_artifact_summary"]["p141a"]["classification"] == "P141A_POWER_ORTHOGONAL_5BET_AUTHORIZATION_GATE_READY"


def test_p140_classification(artifact):
    assert artifact["source_artifact_summary"]["p140"]["classification"] == "P140_POWER_PRECISION_3BET_APPLIED"


def test_p139_classification(artifact):
    assert artifact["source_artifact_summary"]["p139"]["classification"] == "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY"


def test_p138b_classification(artifact):
    assert artifact["source_artifact_summary"]["p138b"]["classification"] == "P138B_P10_P12_LEGACY_ROWS_REMARKED"


def test_p134_classification(artifact):
    assert artifact["source_artifact_summary"]["p134"]["classification"] == "P134_FOURIER_RHYTHM_3BET_APPLIED"


def test_p133_classification(artifact):
    assert artifact["source_artifact_summary"]["p133"]["classification"] == "P133_PP3_FREQORT_4BET_APPLIED"


def test_p132_classification(artifact):
    assert artifact["source_artifact_summary"]["p132"]["classification"] == "P132_MIDFREQ_FOURIER_MK_3BET_APPLIED"


def test_p131_classification(artifact):
    assert artifact["source_artifact_summary"]["p131"]["classification"] == "P131_ACB_MARKOV_MIDFREQ_3BET_APPLIED"


def test_all_classifications_pass(artifact):
    assert artifact["source_artifact_summary"]["all_required_classifications_pass"] is True


# ── Wave 2 safe candidate closure ─────────────────────────────────────────────

def test_wave2_safe_candidates_all_applied(artifact):
    wave2 = artifact["wave2_safe_candidate_closure"]
    assert wave2["p7_acb_markov_midfreq_3bet_status"] == "APPLIED"
    assert wave2["p8_midfreq_fourier_mk_3bet_status"] == "APPLIED"
    assert wave2["p9_fourier_rhythm_3bet_status"] == "APPLIED"
    assert wave2["p11_pp3_freqort_4bet_status"] == "APPLIED"
    assert wave2["all_safe_candidates_closed"] is True


def test_wave2_safe_candidates_total_rows(artifact):
    assert artifact["wave2_safe_candidate_closure"]["total_inserted_rows_p131_to_p134"] == 13502


def test_wave2_acb_distribution(artifact):
    dist = artifact["wave2_safe_candidate_closure"]["p7_bet_index_distribution"]
    # JSON keys are strings after deserialization
    assert dist == {"1": 1500, "2": 1500, "3": 1500}


def test_wave2_mk3_distribution(artifact):
    dist = artifact["wave2_safe_candidate_closure"]["p8_bet_index_distribution"]
    assert dist == {"1": 1500, "2": 1500, "3": 1500}


def test_wave2_fr3_distribution(artifact):
    dist = artifact["wave2_safe_candidate_closure"]["p9_bet_index_distribution"]
    assert dist == {"1": 1501, "2": 1501, "3": 1501}


def test_wave2_pp4_distribution(artifact):
    dist = artifact["wave2_safe_candidate_closure"]["p11_bet_index_distribution"]
    assert dist == {"1": 1500, "2": 1500, "3": 1500, "4": 1500}


# ── P10/P12 closure ───────────────────────────────────────────────────────────

def test_p10_p12_all_applied(artifact):
    p10p12 = artifact["p10_p12_closure"]
    assert p10p12["power_precision_3bet_status"] == "APPLIED"
    assert p10p12["power_orthogonal_5bet_status"] == "APPLIED"
    assert p10p12["p10_p12_final_apply_chain_completed"] is True


def test_p10_p12_total_rows(artifact):
    assert artifact["p10_p12_closure"]["total_inserted_rows_p140_to_p141"] == 9000


def test_power_precision_3bet_distribution(artifact):
    dist = artifact["p10_p12_closure"]["power_precision_3bet_bet_index_distribution"]
    assert dist == {"1": 1550, "2": 1500, "3": 1500}


def test_power_orthogonal_5bet_distribution(artifact):
    dist = artifact["p10_p12_closure"]["power_orthogonal_5bet_bet_index_distribution"]
    assert dist == {"1": 1550, "2": 1500, "3": 1500, "4": 1500, "5": 1500}


# ── Inserted rows summary ─────────────────────────────────────────────────────

def test_inserted_rows_p131(artifact):
    assert artifact["inserted_rows_summary"]["p131_rows"] == 3000


def test_inserted_rows_p132(artifact):
    assert artifact["inserted_rows_summary"]["p132_rows"] == 3000


def test_inserted_rows_p133(artifact):
    assert artifact["inserted_rows_summary"]["p133_rows"] == 4500


def test_inserted_rows_p134(artifact):
    assert artifact["inserted_rows_summary"]["p134_rows"] == 3002


def test_inserted_rows_p140(artifact):
    assert artifact["inserted_rows_summary"]["p140_rows"] == 3000


def test_inserted_rows_p141(artifact):
    assert artifact["inserted_rows_summary"]["p141_rows"] == 6000


def test_inserted_rows_total(artifact):
    assert artifact["inserted_rows_summary"]["total_wave2_multibet_inserted_rows"] == 22502


def test_inserted_rows_subtotal_p131_p134(artifact):
    assert artifact["inserted_rows_summary"]["p131_to_p134_subtotal"] == 13502


def test_inserted_rows_subtotal_p140_p141(artifact):
    assert artifact["inserted_rows_summary"]["p140_to_p141_subtotal"] == 9000


# ── DB row chain ──────────────────────────────────────────────────────────────

def test_db_row_chain_after_rsr6(artifact):
    assert artifact["db_row_chain"]["after_rsr6_cleanup_rows"] == 72422


def test_db_row_chain_after_p134(artifact):
    assert artifact["db_row_chain"]["after_p134_rows"] == 85924


def test_db_row_chain_after_p140(artifact):
    assert artifact["db_row_chain"]["after_p140_rows"] == 88924


def test_db_row_chain_after_p141(artifact):
    assert artifact["db_row_chain"]["after_p141_rows"] == 94924


def test_db_row_chain_current(artifact):
    assert artifact["db_row_chain"]["current_rows"] == EXPECTED_ROWS


def test_db_row_chain_consistent(artifact):
    assert artifact["db_row_chain"]["chain_consistent"] is True


# ── LEGACY_UNVERIFIED audit ───────────────────────────────────────────────────

def test_legacy_pp3_rows(artifact):
    assert artifact["legacy_unverified_audit"]["power_precision_3bet_legacy_unverified_rows"] == 50


def test_legacy_po5_rows(artifact):
    assert artifact["legacy_unverified_audit"]["power_orthogonal_5bet_legacy_unverified_rows"] == 50


def test_legacy_rows_modified_zero(artifact):
    assert artifact["legacy_unverified_audit"]["legacy_rows_modified_by_p140_p141"] == 0


def test_legacy_rows_excluded_from_apply_base(artifact):
    assert artifact["legacy_unverified_audit"]["legacy_rows_excluded_from_apply_base"] is True


def test_no_legacy_contamination(artifact):
    assert artifact["legacy_unverified_audit"]["no_legacy_contamination_in_multi_bet_rows"] is True


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write_in_p142(artifact):
    assert artifact["non_actions"]["db_write_in_p142"] is False


def test_no_controlled_apply_in_p142(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p142"] is False


def test_no_replay_rows_inserted(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p142"] == 0


def test_no_replay_rows_deleted(artifact):
    assert artifact["non_actions"]["replay_rows_deleted_in_p142"] == 0


def test_no_scheduler_installed(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_no_lifecycle_mutation(artifact):
    assert artifact["non_actions"]["lifecycle_champion_registry_mutation"] is False


def test_no_four_star(artifact):
    assert artifact["non_actions"]["four_star_executed"] is False


def test_no_p108(artifact):
    assert artifact["non_actions"]["p108_executed"] is False


# ── Drift guard ───────────────────────────────────────────────────────────────

def test_drift_guard_status(artifact):
    assert artifact["drift_guard_result"]["status"] == "PASS"


def test_drift_guard_classification(artifact):
    assert artifact["drift_guard_result"]["classification"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"


def test_drift_guard_total_rows(artifact):
    assert artifact["drift_guard_result"]["total_rows"] == EXPECTED_ROWS


# ── Dirty file hygiene ────────────────────────────────────────────────────────

def test_backups_untracked_not_staged(artifact):
    assert artifact["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_autouse_regen_risk_noted(artifact):
    assert artifact["dirty_file_hygiene"]["p135_p136_autouse_regen_risk_noted"] is True


def test_no_forbidden_files_staged(artifact):
    assert artifact["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ── Markdown ──────────────────────────────────────────────────────────────────

def test_markdown_exists():
    assert MD_PATH.exists()


def test_markdown_classification(artifact):
    text = MD_PATH.read_text(encoding="utf-8")
    assert EXPECTED_CLASSIFICATION in text


def test_markdown_sections():
    text = MD_PATH.read_text(encoding="utf-8")
    for section in [
        "Executive Summary",
        "Canonical Repo / Branch Confirmation",
        "P141 Recap",
        "P140 Recap",
        "P131–P134 Safe Candidate Recap",
        "Final Strategy Distribution Matrix",
        "Inserted Rows Summary",
        "DB Row Chain",
        "LEGACY_UNVERIFIED Audit",
        "Drift Guard Result",
        "Test Coverage Summary",
        "Dirty File Hygiene Note",
        "Explicit Non-Actions",
        "Remaining Risks",
        "Recommended Next Task",
        "Final Classification",
    ]:
        assert section in text, f"Missing Markdown section: {section}"


def test_markdown_db_row_chain_values():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "72,422" in text
    assert "85,924" in text
    assert "88,924" in text
    assert "94,924" in text


def test_markdown_inserted_rows_total():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "22,502" in text


# ── Live DB constraints ───────────────────────────────────────────────────────

def test_live_db_total_rows(db_conn):
    count = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert count == EXPECTED_ROWS


def test_live_db_bet_index_schema(db_conn):
    cols = [row[1] for row in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    assert "bet_index" in cols


def test_live_db_acb_distribution(db_conn):
    for bi in (1, 2, 3):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            ("acb_markov_midfreq_3bet", bi),
        ).fetchone()[0]
        assert cnt == 1500


def test_live_db_mk3_distribution(db_conn):
    for bi in (1, 2, 3):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            ("midfreq_fourier_mk_3bet", bi),
        ).fetchone()[0]
        assert cnt == 1500


def test_live_db_fr3_distribution(db_conn):
    for bi in (1, 2, 3):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            ("fourier_rhythm_3bet", bi),
        ).fetchone()[0]
        assert cnt == 1501


def test_live_db_pp4_distribution(db_conn):
    for bi in (1, 2, 3, 4):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            ("pp3_freqort_4bet", bi),
        ).fetchone()[0]
        assert cnt == 1500


def test_live_db_pp3_distribution(db_conn):
    cnt_b1 = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_precision_3bet' AND bet_index=1",
    ).fetchone()[0]
    assert cnt_b1 == 1550
    for bi in (2, 3):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            ("power_precision_3bet", bi),
        ).fetchone()[0]
        assert cnt == 1500


def test_live_db_po5_distribution(db_conn):
    cnt_b1 = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_orthogonal_5bet' AND bet_index=1",
    ).fetchone()[0]
    assert cnt_b1 == 1550
    for bi in (2, 3, 4, 5):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            ("power_orthogonal_5bet", bi),
        ).fetchone()[0]
        assert cnt == 1500


def test_live_db_legacy_rows_pp3(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' AND truth_level='LEGACY_UNVERIFIED'",
    ).fetchone()[0]
    assert cnt == 50


def test_live_db_legacy_rows_po5(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND truth_level='LEGACY_UNVERIFIED'",
    ).fetchone()[0]
    assert cnt == 50


def test_live_db_no_legacy_in_multi_bet_pp3(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' AND truth_level='LEGACY_UNVERIFIED' AND bet_index > 1",
    ).fetchone()[0]
    assert cnt == 0


def test_live_db_no_legacy_in_multi_bet_po5(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND truth_level='LEGACY_UNVERIFIED' AND bet_index > 1",
    ).fetchone()[0]
    assert cnt == 0


# ── Forbidden file staging check ─────────────────────────────────────────────

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
