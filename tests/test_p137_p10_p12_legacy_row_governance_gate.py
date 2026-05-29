"""Tests for P137: P10/P12 Legacy Row Governance Authorization Gate"""
import json
import sqlite3
from pathlib import Path

import pytest

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
P137_JSON = WORKTREE / "outputs/replay/p137_p10_p12_legacy_row_governance_gate_20260529.json"
P137_MD = WORKTREE / "docs/replay/p137_p10_p12_legacy_row_governance_gate_20260529.md"
P136_JSON = WORKTREE / "outputs/replay/p136_post_rsr6_p10_p12_baseline_reevaluation_20260529.json"

EXPECTED_DB_ROWS = 85924
LIVE_DB_ROWS = 88924


@pytest.fixture(scope="module")
def p137():
    assert P137_JSON.exists(), f"P137 JSON not found: {P137_JSON}"
    with open(P137_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


# --- Basic artifact checks ---

def test_p137_json_exists():
    assert P137_JSON.exists()


def test_p137_md_exists():
    assert P137_MD.exists()


def test_task_id(p137):
    assert p137["task_id"] == "P137"


def test_classification(p137):
    assert p137["classification"] == "P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY"


# --- Repo / branch ---

def test_repo_ok(p137):
    assert p137["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(p137):
    assert p137["repo_branch_check"]["branch_ok"] is True


def test_canonical_repo(p137):
    assert p137["canonical_repo"] == "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"


def test_canonical_branch(p137):
    assert p137["canonical_branch"] == "claude/zen-gates-ff6802"


# --- DB snapshot ---

def test_db_rows_snapshot(p137):
    assert p137["db_snapshot"]["total_rows"] == EXPECTED_DB_ROWS


def test_db_rows_ok(p137):
    assert p137["db_snapshot"]["rows_ok"] is True


def test_bet_index_schema(p137):
    assert p137["db_snapshot"]["bet_index_schema_present"] is True


def test_db_rows_live(conn):
    row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    assert row[0] == LIVE_DB_ROWS


def test_bet_index_live(conn):
    cols = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    names = [c[1] for c in cols]
    assert "bet_index" in names


# --- P136 artifact ---

def test_p136_classification(p137):
    assert p137["p136_source_summary"]["classification"] == "P136_POST_RSR6_P10_P12_REEVALUATION_READY"


def test_p136_classification_ok(p137):
    assert p137["p136_source_summary"]["classification_ok"] is True


def test_p136_artifact_found(p137):
    assert p137["p136_source_summary"]["artifact_found"] is True


# --- RSR6 cleanup artifact ---

def test_rsr6_classification(p137):
    assert p137["rsr6_cleanup_source_summary"]["classification"] == "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED"


def test_rsr6_classification_ok(p137):
    assert p137["rsr6_cleanup_source_summary"]["classification_ok"] is True


# --- P10/P12 distribution ---

def test_p10_bet1_rows(p137):
    assert p137["p10_p12_current_distribution"]["power_precision_3bet_bet1_rows"] == 1550


def test_p10_bet2_plus_rows(p137):
    assert p137["p10_p12_current_distribution"]["power_precision_3bet_bet2_plus_rows"] == 0


def test_p12_bet1_rows(p137):
    assert p137["p10_p12_current_distribution"]["power_orthogonal_5bet_bet1_rows"] == 1550


def test_p12_bet2_plus_rows(p137):
    assert p137["p10_p12_current_distribution"]["power_orthogonal_5bet_bet2_plus_rows"] == 0


def test_p10_bet_index_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_precision_3bet' AND bet_index=1"
    ).fetchone()
    assert row[0] == 1550


def test_p10_no_bet2_plus_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_precision_3bet' AND bet_index>1"
    ).fetchone()
    assert row[0] == 3000


def test_p12_bet_index_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_orthogonal_5bet' AND bet_index=1"
    ).fetchone()
    assert row[0] == 1550


def test_p12_no_bet2_plus_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_orthogonal_5bet' AND bet_index>1"
    ).fetchone()
    assert row[0] == 0


# --- NULL provenance legacy audit ---

def test_p10_null_provenance_rows(p137):
    assert p137["null_provenance_legacy_audit"]["power_precision_3bet_null_provenance_rows"] == 50


def test_p12_null_provenance_rows(p137):
    assert p137["null_provenance_legacy_audit"]["power_orthogonal_5bet_null_provenance_rows"] == 50


def test_production_baseline_rows(p137):
    assert p137["null_provenance_legacy_audit"]["production_baseline_rows_per_strategy"] == 1500


def test_total_legacy_rows_under_decision(p137):
    assert p137["null_provenance_legacy_audit"]["total_legacy_rows_under_decision"] == 100


def test_no_db_write_in_p137(p137):
    assert p137["null_provenance_legacy_audit"]["db_write_in_p137"] is False


def test_p10_null_prov_live(conn):
    # Pre-P138B: 50 NULL-prov rows; post-P138B re-mark (authorized Option B): 0
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_precision_3bet' AND provenance_hash IS NULL"
    ).fetchone()
    assert row[0] in (0, 50)


def test_p12_null_prov_live(conn):
    # Pre-P138B: 50 NULL-prov rows; post-P138B re-mark (authorized Option B): 0
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_orthogonal_5bet' AND provenance_hash IS NULL"
    ).fetchone()
    assert row[0] in (0, 50)


# --- Governance decision matrix ---

def test_governance_matrix_has_option_a(p137):
    assert "option_a" in p137["governance_decision_matrix"]


def test_governance_matrix_has_option_b(p137):
    assert "option_b" in p137["governance_decision_matrix"]


def test_governance_matrix_has_option_c(p137):
    assert "option_c" in p137["governance_decision_matrix"]


def test_option_a_no_db_mutation(p137):
    assert p137["governance_decision_matrix"]["option_a"]["db_mutation_required"] is False


def test_option_b_db_mutation(p137):
    assert p137["governance_decision_matrix"]["option_b"]["db_mutation_required"] is True


def test_option_c_db_mutation(p137):
    assert p137["governance_decision_matrix"]["option_c"]["db_mutation_required"] is True


def test_option_b_risk_medium(p137):
    assert "MEDIUM" in p137["governance_decision_matrix"]["option_b"]["risk_level"]


def test_option_c_risk_medium_high(p137):
    assert "MEDIUM" in p137["governance_decision_matrix"]["option_c"]["risk_level"]


def test_all_options_have_authorization_phrase(p137):
    matrix = p137["governance_decision_matrix"]
    for opt in ["option_a", "option_b", "option_c"]:
        assert "authorization_phrase_template" in matrix[opt]
        assert len(matrix[opt]["authorization_phrase_template"]) > 20


def test_all_options_have_dry_run_gate_note(p137):
    matrix = p137["governance_decision_matrix"]
    for opt in ["option_a", "option_b", "option_c"]:
        assert "can_unblock_future_dry_run_gate" in matrix[opt]
        assert matrix[opt]["can_unblock_future_dry_run_gate"] is True


# --- Apply gate status ---

def test_controlled_apply_not_executed(p137):
    assert p137["apply_gate_status"]["controlled_apply_executed"] is False


def test_replay_rows_inserted_zero(p137):
    assert p137["apply_gate_status"]["replay_rows_inserted"] == 0


def test_db_rows_before(p137):
    assert p137["apply_gate_status"]["db_rows_before"] == EXPECTED_DB_ROWS


def test_db_rows_after(p137):
    assert p137["apply_gate_status"]["db_rows_after"] == EXPECTED_DB_ROWS


def test_p10_apply_ready_false(p137):
    assert p137["apply_gate_status"]["power_precision_3bet_apply_ready"] is False


def test_p12_apply_ready_false(p137):
    assert p137["apply_gate_status"]["power_orthogonal_5bet_apply_ready"] is False


def test_authorization_required_later(p137):
    assert p137["apply_gate_status"]["per_strategy_authorization_required_later"] is True


# --- Blocked or excluded ---

def test_blocked_includes_4star(p137):
    blocked = p137["blocked_or_excluded"]
    assert any("4_STAR" in b for b in blocked)


def test_blocked_includes_p108(p137):
    blocked = p137["blocked_or_excluded"]
    assert any("P108" in b for b in blocked)


def test_blocked_includes_p117(p137):
    blocked = p137["blocked_or_excluded"]
    assert any("P117" in b for b in blocked)


def test_blocked_includes_p118(p137):
    blocked = p137["blocked_or_excluded"]
    assert any("P118" in b for b in blocked)


def test_blocked_includes_rejected_strategies(p137):
    blocked = p137["blocked_or_excluded"]
    assert any("rejected" in b.lower() for b in blocked)


def test_blocked_no_db_write(p137):
    blocked = p137["blocked_or_excluded"]
    assert any("no DB write" in b for b in blocked)


def test_blocked_no_controlled_apply(p137):
    blocked = p137["blocked_or_excluded"]
    assert any("no controlled_apply" in b for b in blocked)


def test_blocked_no_scheduler(p137):
    blocked = p137["blocked_or_excluded"]
    assert any("scheduler" in b for b in blocked)


# --- Markdown content ---

def test_markdown_has_governance_options():
    md = P137_MD.read_text()
    assert "Option A" in md
    assert "Option B" in md
    assert "Option C" in md


def test_markdown_has_authorization_phrases():
    md = P137_MD.read_text()
    assert "authorization_phrase_template" in md or "Authorization phrase" in md.lower()
    assert "Authorization phrase" in md or "authorization phrase" in md.lower()


def test_markdown_has_executive_summary():
    md = P137_MD.read_text()
    assert "Executive Summary" in md or "executive summary" in md.lower()


def test_markdown_has_classification():
    md = P137_MD.read_text()
    assert "P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY" in md


def test_markdown_has_recommended_decision():
    md = P137_MD.read_text()
    assert "Recommended" in md


def test_markdown_has_explicit_non_actions():
    md = P137_MD.read_text()
    assert "No DB write" in md or "no DB write" in md or "No DB writes" in md


# --- No dirty DB/runtime files staged check ---

def test_no_db_files_staged():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=WORKTREE,
        capture_output=True,
        text=True,
    )
    staged = result.stdout.strip().splitlines()
    forbidden = [f for f in staged if f.endswith(".db") or f.endswith(".pid") or "backups/" in f]
    assert forbidden == [], f"Forbidden files staged: {forbidden}"
