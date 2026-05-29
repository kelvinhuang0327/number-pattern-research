"""Tests for P138B: P10/P12 legacy row re-mark as LEGACY_UNVERIFIED"""
import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
P138B_JSON = WORKTREE / "outputs/replay/p138b_remark_p10_p12_legacy_rows_20260529.json"
P138B_MD = WORKTREE / "docs/replay/p138b_remark_p10_p12_legacy_rows_20260529.md"

EXPECTED_DB_ROWS = 85924
P10_ID = "power_precision_3bet"
P12_ID = "power_orthogonal_5bet"


@pytest.fixture(scope="module")
def p138b():
    assert P138B_JSON.exists(), f"P138B JSON not found: {P138B_JSON}"
    with open(P138B_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


# --- Artifact existence ---

def test_p138b_json_exists():
    assert P138B_JSON.exists()


def test_p138b_md_exists():
    assert P138B_MD.exists()


# --- Basic fields ---

def test_task_id(p138b):
    assert p138b["task_id"] == "P138B"


def test_classification(p138b):
    assert p138b["classification"] == "P138B_P10_P12_LEGACY_ROWS_REMARKED"


# --- Authorization ---

def test_authorization_present(p138b):
    assert p138b["authorization"]["authorization_present"] is True


def test_remark_allowed(p138b):
    assert p138b["authorization"]["remark_allowed"] is True


def test_exact_required_phrase(p138b):
    assert p138b["authorization"]["exact_required_phrase"] == (
        "P137_AUTHORIZED_OPTION_B_REMARK_P10_P12_LEGACY_ROWS_AS_LEGACY_UNVERIFIED_20260529"
    )


def test_authorization_text_observed(p138b):
    assert p138b["authorization"]["authorization_text_observed"] == (
        "P137_AUTHORIZED_OPTION_B_REMARK_P10_P12_LEGACY_ROWS_AS_LEGACY_UNVERIFIED_20260529"
    )


# --- Repo / branch ---

def test_repo_ok(p138b):
    assert p138b["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(p138b):
    assert p138b["repo_branch_check"]["branch_ok"] is True


# --- DB snapshot before ---

def test_db_rows_before(p138b):
    assert p138b["db_snapshot_before"]["total_rows"] == EXPECTED_DB_ROWS


def test_db_rows_before_ok(p138b):
    assert p138b["db_snapshot_before"]["rows_ok"] is True


# --- Backup ---

def test_backup_created(p138b):
    assert p138b["backup"]["backup_created"] is True


def test_backup_row_count(p138b):
    assert p138b["backup"]["backup_row_count"] == EXPECTED_DB_ROWS


def test_backup_row_count_ok(p138b):
    assert p138b["backup"]["backup_row_count_ok"] is True


def test_backup_file_exists(p138b):
    backup_path = Path(p138b["backup"]["backup_path"])
    assert backup_path.exists(), f"Backup file not found: {backup_path}"


# --- P137 source ---

def test_p137_classification_ok(p138b):
    assert p138b["p137_source_summary"]["classification_ok"] is True


def test_p137_recommended_option(p138b):
    assert p138b["p137_source_summary"]["recommended_option"] == "option_b"


# --- Remark scope ---

def test_expected_rows_to_remark(p138b):
    assert p138b["remark_scope"]["expected_rows_to_remark"] == 100


def test_actual_rows_remarked(p138b):
    assert p138b["remark_scope"]["actual_rows_remarked"] == 100


def test_rows_inserted(p138b):
    assert p138b["remark_scope"]["rows_inserted"] == 0


def test_rows_deleted(p138b):
    assert p138b["remark_scope"]["rows_deleted"] == 0


def test_mutation_type(p138b):
    assert p138b["remark_scope"]["mutation_type"] == "UPDATE_ONLY"


# --- DB snapshot after ---

def test_db_rows_after(p138b):
    assert p138b["db_snapshot_after"]["total_rows"] == EXPECTED_DB_ROWS


def test_db_rows_unchanged(p138b):
    assert p138b["db_snapshot_after"]["rows_unchanged"] is True


# --- Selector validation after ---

def test_null_prov_after_zero(p138b):
    assert p138b["selector_validation_after"]["null_prov_after"] == 0


def test_null_prov_selector_zero(p138b):
    assert p138b["selector_validation_after"]["null_prov_selector_zero"] is True


def test_legacy_unverified_total(p138b):
    assert p138b["selector_validation_after"]["legacy_unverified_total"] == 100


def test_legacy_unverified_equals_100(p138b):
    assert p138b["selector_validation_after"]["legacy_unverified_equals_100"] is True


def test_p10_unverified_count(p138b):
    assert p138b["selector_validation_after"]["per_strategy_unverified"].get(P10_ID) == 50


def test_p12_unverified_count(p138b):
    assert p138b["selector_validation_after"]["per_strategy_unverified"].get(P12_ID) == 50


# --- Live DB checks ---

def test_db_rows_live(conn):
    row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    assert row[0] == EXPECTED_DB_ROWS


def test_null_prov_live_zero(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
        "AND provenance_hash IS NULL"
    ).fetchone()
    assert row[0] == 0


def test_legacy_unverified_live_100(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE truth_level='LEGACY_UNVERIFIED'"
    ).fetchone()
    assert row[0] == 100


def test_p10_legacy_unverified_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' AND truth_level='LEGACY_UNVERIFIED'"
    ).fetchone()
    assert row[0] == 50


def test_p12_legacy_unverified_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND truth_level='LEGACY_UNVERIFIED'"
    ).fetchone()
    assert row[0] == 50


def test_source_p138b_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE source='P138B_LEGACY_REMARK'"
    ).fetchone()
    assert row[0] == 100


def test_provenance_hash_not_null_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') "
        "AND truth_level='LEGACY_UNVERIFIED' AND provenance_hash IS NOT NULL"
    ).fetchone()
    assert row[0] == 100


# --- Row preservation ---

def test_p10_bet1_rows_preserved(p138b):
    assert p138b["row_preservation_check"]["power_precision_3bet_bet1"] == 1550


def test_p12_bet1_rows_preserved(p138b):
    assert p138b["row_preservation_check"]["power_orthogonal_5bet_bet1"] == 1550


def test_p10_bet2_plus_zero(p138b):
    assert p138b["row_preservation_check"]["power_precision_3bet_bet2_plus"] == 0


def test_p12_bet2_plus_zero(p138b):
    assert p138b["row_preservation_check"]["power_orthogonal_5bet_bet2_plus"] == 0


def test_p10_prod_rows_ok(p138b):
    assert p138b["row_preservation_check"]["power_precision_3bet_prod_ok"] is True


def test_p12_prod_rows_ok(p138b):
    assert p138b["row_preservation_check"]["power_orthogonal_5bet_prod_ok"] is True


def test_p10_bet1_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' AND bet_index=1"
    ).fetchone()
    assert row[0] == 1550


def test_p12_bet1_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND bet_index=1"
    ).fetchone()
    assert row[0] == 1550


def test_p10_no_bet2_plus_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' AND bet_index>1"
    ).fetchone()
    assert row[0] == 0


def test_p12_no_bet2_plus_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND bet_index>1"
    ).fetchone()
    assert row[0] == 0


# --- Drift guard ---

def test_drift_guard_pass(p138b):
    assert p138b["drift_guard_result"]["pass"] is True


def test_drift_guard_total_rows(p138b):
    assert p138b["drift_guard_result"]["total_rows"] == EXPECTED_DB_ROWS


# --- Future dry-run gate impact ---

def test_p10_governance_resolved(p138b):
    assert p138b["future_dry_run_gate_impact"]["power_precision_3bet_legacy_governance_resolved"] is True


def test_p12_governance_resolved(p138b):
    assert p138b["future_dry_run_gate_impact"]["power_orthogonal_5bet_legacy_governance_resolved"] is True


def test_dry_run_gate_re_evaluation_allowed(p138b):
    assert p138b["future_dry_run_gate_impact"]["dry_run_gate_re_evaluation_allowed"] is True


def test_controlled_apply_not_executed(p138b):
    assert p138b["future_dry_run_gate_impact"]["controlled_apply_executed"] is False


def test_replay_rows_inserted_zero(p138b):
    assert p138b["future_dry_run_gate_impact"]["replay_rows_inserted"] == 0


def test_authorization_required_later(p138b):
    assert p138b["future_dry_run_gate_impact"]["per_strategy_authorization_required_later"] is True


# --- Blocked / excluded ---

def test_blocked_includes_4star(p138b):
    blocked = p138b["blocked_or_excluded"]
    assert any("4_STAR" in b for b in blocked)


def test_blocked_includes_p108(p138b):
    blocked = p138b["blocked_or_excluded"]
    assert any("P108" in b for b in blocked)


def test_blocked_includes_p117(p138b):
    blocked = p138b["blocked_or_excluded"]
    assert any("P117" in b for b in blocked)


def test_blocked_includes_p118(p138b):
    blocked = p138b["blocked_or_excluded"]
    assert any("P118" in b for b in blocked)


def test_blocked_includes_rejected(p138b):
    blocked = p138b["blocked_or_excluded"]
    assert any("rejected" in b.lower() for b in blocked)


def test_blocked_no_controlled_apply(p138b):
    blocked = p138b["blocked_or_excluded"]
    assert any("no controlled_apply" in b for b in blocked)


def test_blocked_no_rows_inserted(p138b):
    blocked = p138b["blocked_or_excluded"]
    assert any("no replay rows inserted" in b for b in blocked)


def test_blocked_no_rows_deleted(p138b):
    blocked = p138b["blocked_or_excluded"]
    assert any("no replay rows deleted" in b for b in blocked)


# --- Markdown content ---

def test_markdown_has_backup_path(p138b):
    md = P138B_MD.read_text()
    backup_path = p138b["backup"]["backup_path"]
    assert backup_path in md


def test_markdown_has_rollback_reference(p138b):
    md = P138B_MD.read_text()
    assert "Rollback" in md or "rollback" in md


def test_markdown_has_executive_summary():
    md = P138B_MD.read_text()
    assert "Executive Summary" in md


def test_markdown_has_authorization():
    md = P138B_MD.read_text()
    assert "Authorization" in md


def test_markdown_has_classification():
    md = P138B_MD.read_text()
    assert "P138B_P10_P12_LEGACY_ROWS_REMARKED" in md


def test_markdown_has_non_actions():
    md = P138B_MD.read_text()
    assert "No controlled_apply" in md or "no controlled_apply" in md.lower() or "Non-Actions" in md


# --- No forbidden files staged ---

def test_no_forbidden_files_staged():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=WORKTREE, capture_output=True, text=True,
    )
    staged = result.stdout.strip().splitlines()
    forbidden = [
        f for f in staged
        if (f.endswith(".db-shm") or f.endswith(".db-wal") or f.endswith(".pid")
            or "backups/" in f
            or (f.endswith(".db") and "lottery_v2.db" in f and "backups" not in f))
    ]
    assert forbidden == [], f"Forbidden non-lottery_v2.db files staged: {forbidden}"
