"""Tests for P139: P10/P12 Multi-Bet Dry-Run Gate After Legacy Remark"""
import json
import sqlite3
from pathlib import Path

import pytest

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
P139_JSON = WORKTREE / "outputs/replay/p139_p10_p12_multibet_dry_run_gate_20260529.json"
P139_MD = WORKTREE / "docs/replay/p139_p10_p12_multibet_dry_run_gate_20260529.md"
P138B_JSON = WORKTREE / "outputs/replay/p138b_remark_p10_p12_legacy_rows_20260529.json"

EXPECTED_DB_ROWS = 85924


@pytest.fixture(scope="module")
def p139():
    assert P139_JSON.exists(), f"P139 JSON not found: {P139_JSON}"
    with open(P139_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


# --- Basic artifact checks ---

def test_p139_json_exists():
    assert P139_JSON.exists()


def test_p139_md_exists():
    assert P139_MD.exists()


def test_task_id(p139):
    assert p139["task_id"] == "P139"


def test_classification(p139):
    assert p139["classification"] == "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY"


# --- Repo / branch ---

def test_repo_ok(p139):
    assert p139["repo_branch_check"]["repo_ok"] is True


def test_branch_ok(p139):
    assert p139["repo_branch_check"]["branch_ok"] is True


def test_canonical_repo(p139):
    assert p139["canonical_repo"] == "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"


def test_canonical_branch(p139):
    assert p139["canonical_branch"] == "claude/zen-gates-ff6802"


# --- DB snapshot ---

def test_db_rows_snapshot(p139):
    assert p139["db_snapshot"]["total_rows"] == EXPECTED_DB_ROWS


def test_db_rows_ok(p139):
    assert p139["db_snapshot"]["rows_ok"] is True


def test_bet_index_schema(p139):
    assert p139["db_snapshot"]["bet_index_schema_present"] is True


def test_db_rows_live(conn):
    row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    assert row[0] == EXPECTED_DB_ROWS


def test_bet_index_live(conn):
    cols = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    names = [c[1] for c in cols]
    assert "bet_index" in names


# --- P138B source summary ---

def test_p138b_classification(p139):
    assert p139["p138b_source_summary"]["classification"] == "P138B_P10_P12_LEGACY_ROWS_REMARKED"


def test_p138b_classification_ok(p139):
    assert p139["p138b_source_summary"]["classification_ok"] is True


def test_p138b_rows_remarked(p139):
    assert p139["p138b_source_summary"]["actual_rows_remarked"] == 100


def test_p10_governance_resolved(p139):
    assert p139["p138b_source_summary"]["p10_governance_resolved"] is True


def test_p12_governance_resolved(p139):
    assert p139["p138b_source_summary"]["p12_governance_resolved"] is True


# --- P10/P12 current distribution ---

def test_p10_bet1_rows(p139):
    assert p139["p10_p12_current_distribution"]["power_precision_3bet_bet1_rows"] == 1550


def test_p10_bet2_plus_rows(p139):
    assert p139["p10_p12_current_distribution"]["power_precision_3bet_bet2_plus_rows"] == 0


def test_p12_bet1_rows(p139):
    assert p139["p10_p12_current_distribution"]["power_orthogonal_5bet_bet1_rows"] == 1550


def test_p12_bet2_plus_rows(p139):
    assert p139["p10_p12_current_distribution"]["power_orthogonal_5bet_bet2_plus_rows"] == 0


def test_p10_bet1_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_precision_3bet' AND bet_index=1"
    ).fetchone()
    assert row[0] == 1550


def test_p10_no_bet2_plus_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_precision_3bet' AND bet_index>1"
    ).fetchone()
    assert row[0] == 0


def test_p12_bet1_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_orthogonal_5bet' AND bet_index=1"
    ).fetchone()
    assert row[0] == 1550


def test_p12_no_bet2_plus_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='power_orthogonal_5bet' AND bet_index>1"
    ).fetchone()
    assert row[0] == 0


# --- Legacy unverified audit ---

def test_p10_legacy_unverified_rows(p139):
    assert p139["legacy_unverified_audit"]["power_precision_3bet_legacy_unverified_rows"] == 50


def test_p12_legacy_unverified_rows(p139):
    assert p139["legacy_unverified_audit"]["power_orthogonal_5bet_legacy_unverified_rows"] == 50


def test_total_legacy_unverified_rows(p139):
    assert p139["legacy_unverified_audit"]["total_legacy_unverified_rows"] == 100


def test_null_provenance_selector_zero(p139):
    assert p139["legacy_unverified_audit"]["null_provenance_selector_count"] == 0


def test_no_db_write_in_p139(p139):
    assert p139["legacy_unverified_audit"]["db_write_in_p139"] is False


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


def test_no_null_prov_p10_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' AND provenance_hash IS NULL"
    ).fetchone()
    assert row[0] == 0


def test_no_null_prov_p12_live(conn):
    row = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND provenance_hash IS NULL"
    ).fetchone()
    assert row[0] == 0


# --- Adapter contract status ---

def test_p10_adapter_function_exists(p139):
    assert p139["adapter_contract_status"]["power_precision_3bet"]["function_exists"] is True


def test_p12_adapter_function_exists(p139):
    assert p139["adapter_contract_status"]["power_orthogonal_5bet"]["function_exists"] is True


def test_p10_adapter_ready(p139):
    assert p139["adapter_contract_status"]["power_precision_3bet"]["adapter_ready_for_dry_run"] is True


def test_p12_adapter_ready(p139):
    assert p139["adapter_contract_status"]["power_orthogonal_5bet"]["adapter_ready_for_dry_run"] is True


def test_adapter_module(p139):
    assert "p128_wave2_phase2_adapters" in p139["adapter_contract_status"]["adapter_module"]


def test_gap_note_draw_context_key(p139):
    assert "history" in p139["adapter_contract_status"]["gap_note"]
    assert "historical_draws" in p139["adapter_contract_status"]["gap_note"]


# --- Dry run plan: P10 ---

def test_p10_dry_run_plan_strategy_id(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["strategy_id"] == "power_precision_3bet"


def test_p10_target_bet_count(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["target_bet_count"] == 3


def test_p10_missing_bet_indices(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["missing_bet_indices"] == [2, 3]


def test_p10_apply_base_rows(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["apply_base_rows"] == 1500


def test_p10_estimated_insert_rows(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["estimated_insert_rows"] == 3000


def test_p10_legacy_handling_exclude(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["legacy_unverified_handling"]["decision"] == "EXCLUDE_FROM_APPLY_BASE"
    assert p139["dry_run_plan"]["power_precision_3bet"]["legacy_unverified_handling"]["excluded_rows"] == 50


def test_p10_dry_run_ready(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["dry_run_ready"] is True


def test_p10_apply_authorization_required(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["apply_authorization_required_later"] is True


def test_p10_no_db_write(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["db_write_in_p139"] is False


def test_p10_controlled_apply_id(p139):
    assert p139["dry_run_plan"]["power_precision_3bet"]["provenance_requirements"]["controlled_apply_id"] == "P140_APPLY_POWER_PRECISION_3BET_v1"


# --- Dry run plan: P12 ---

def test_p12_dry_run_plan_strategy_id(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["strategy_id"] == "power_orthogonal_5bet"


def test_p12_target_bet_count(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["target_bet_count"] == 5


def test_p12_missing_bet_indices(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["missing_bet_indices"] == [2, 3, 4, 5]


def test_p12_apply_base_rows(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["apply_base_rows"] == 1500


def test_p12_estimated_insert_rows(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["estimated_insert_rows"] == 6000


def test_p12_legacy_handling_exclude(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["legacy_unverified_handling"]["decision"] == "EXCLUDE_FROM_APPLY_BASE"
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["legacy_unverified_handling"]["excluded_rows"] == 50


def test_p12_dry_run_ready(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["dry_run_ready"] is True


def test_p12_apply_authorization_required(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["apply_authorization_required_later"] is True


def test_p12_no_db_write(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["db_write_in_p139"] is False


def test_p12_controlled_apply_id(p139):
    assert p139["dry_run_plan"]["power_orthogonal_5bet"]["provenance_requirements"]["controlled_apply_id"] == "P141_APPLY_POWER_ORTHOGONAL_5BET_v1"


# --- Legacy row handling decision ---

def test_legacy_handling_decision(p139):
    assert p139["legacy_row_handling_decision"]["decision"] == "EXCLUDE_FROM_APPLY_BASE"


def test_legacy_apply_base_rows(p139):
    assert p139["legacy_row_handling_decision"]["apply_base_rows"] == 1500


def test_legacy_excluded_count(p139):
    assert p139["legacy_row_handling_decision"]["excluded_row_count"] == 50


def test_legacy_excluded_truth_level(p139):
    assert p139["legacy_row_handling_decision"]["excluded_truth_level"] == "LEGACY_UNVERIFIED"


def test_apply_selector_has_production_truth_level(p139):
    selector = p139["legacy_row_handling_decision"]["apply_selector"]
    assert "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED" in selector


def test_apply_selector_has_controlled_apply_id(p139):
    selector = p139["legacy_row_handling_decision"]["apply_selector"]
    assert "P20_POWERLOTTO_REMAINING_1500_PROD_20260520" in selector


# --- Estimated insert rows summary ---

def test_p10_estimated_summary(p139):
    s = p139["estimated_insert_rows_summary"]["power_precision_3bet"]
    assert s["apply_base"] == 1500
    assert s["estimated_insert_rows"] == 3000
    assert s["db_total_after_apply"] == 88924


def test_p12_estimated_summary(p139):
    s = p139["estimated_insert_rows_summary"]["power_orthogonal_5bet"]
    assert s["apply_base"] == 1500
    assert s["estimated_insert_rows"] == 6000
    assert s["db_total_after_apply"] == 94924


def test_combined_total_insert(p139):
    assert p139["estimated_insert_rows_summary"]["combined_total_insert_rows"] == 9000


def test_db_total_after_both(p139):
    assert p139["estimated_insert_rows_summary"]["db_total_after_both"] == 94924


# --- Recommended apply order ---

def test_apply_order_p10_first(p139):
    assert p139["recommended_apply_order"]["recommendation"] == "P10_FIRST"


def test_apply_order_step1_p10(p139):
    order = p139["recommended_apply_order"]["apply_order"]
    assert order[0]["step"] == 1
    assert order[0]["strategy_id"] == "power_precision_3bet"
    assert order[0]["task_name"] == "P140"
    assert order[0]["estimated_rows"] == 3000
    assert order[0]["authorization_required"] is True


def test_apply_order_step2_p12(p139):
    order = p139["recommended_apply_order"]["apply_order"]
    assert order[1]["step"] == 2
    assert order[1]["strategy_id"] == "power_orthogonal_5bet"
    assert order[1]["task_name"] == "P141"
    assert order[1]["estimated_rows"] == 6000
    assert order[1]["authorization_required"] is True


# --- Authorization phrase templates ---

def test_p10_auth_phrase(p139):
    phrase = p139["authorization_phrase_templates"]["p10_apply_phrase"]
    assert phrase == "P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529"


def test_p12_auth_phrase(p139):
    phrase = p139["authorization_phrase_templates"]["p12_apply_phrase"]
    assert phrase == "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529"


def test_not_authorization_flag(p139):
    assert p139["authorization_phrase_templates"]["this_is_not_authorization"] is True


# --- Apply gate status ---

def test_dry_run_gate_only(p139):
    assert p139["apply_gate_status"]["dry_run_gate_only"] is True


def test_controlled_apply_not_executed(p139):
    assert p139["apply_gate_status"]["controlled_apply_executed"] is False


def test_replay_rows_inserted_zero(p139):
    assert p139["apply_gate_status"]["replay_rows_inserted"] == 0


def test_db_rows_before(p139):
    assert p139["apply_gate_status"]["db_rows_before"] == EXPECTED_DB_ROWS


def test_db_rows_after(p139):
    assert p139["apply_gate_status"]["db_rows_after"] == EXPECTED_DB_ROWS


def test_p10_dry_run_ready_flag(p139):
    assert p139["apply_gate_status"]["p10_dry_run_ready"] is True


def test_p12_dry_run_ready_flag(p139):
    assert p139["apply_gate_status"]["p12_dry_run_ready"] is True


def test_authorization_required_later(p139):
    assert p139["apply_gate_status"]["per_strategy_authorization_required_later"] is True


# --- Blocked or excluded ---

def test_blocked_no_db_write(p139):
    blocked = p139["blocked_or_excluded"]
    assert any("no DB write" in b for b in blocked)


def test_blocked_no_controlled_apply(p139):
    blocked = p139["blocked_or_excluded"]
    assert any("no controlled_apply" in b for b in blocked)


def test_blocked_4star(p139):
    blocked = p139["blocked_or_excluded"]
    assert any("4_STAR" in b for b in blocked)


def test_blocked_p108(p139):
    blocked = p139["blocked_or_excluded"]
    assert any("P108" in b for b in blocked)


def test_blocked_p117(p139):
    blocked = p139["blocked_or_excluded"]
    assert any("P117" in b for b in blocked)


def test_blocked_p118(p139):
    blocked = p139["blocked_or_excluded"]
    assert any("P118" in b for b in blocked)


def test_blocked_no_scheduler(p139):
    blocked = p139["blocked_or_excluded"]
    assert any("scheduler" in b for b in blocked)


# --- Drift guard ---

def test_drift_guard_pass(p139):
    assert p139["drift_guard_result"]["pass"] is True


def test_drift_guard_total_rows(p139):
    assert p139["drift_guard_result"]["total_rows"] == EXPECTED_DB_ROWS


# --- Duplicate guard ---

def test_p10_duplicate_guard_abort_on_conflict(p139):
    assert p139["duplicate_guard_summary"]["abort_on_conflict"] is True


def test_p10_duplicate_guard_check(p139):
    dg = p139["duplicate_guard_summary"]["power_precision_3bet"]
    assert dg["expected_count_before_apply"] == 0


def test_p12_duplicate_guard_check(p139):
    dg = p139["duplicate_guard_summary"]["power_orthogonal_5bet"]
    assert dg["expected_count_before_apply"] == 0


# --- Provenance readiness ---

def test_p10_provenance_ready(p139):
    assert p139["provenance_readiness_summary"]["power_precision_3bet"]["ready"] is True


def test_p12_provenance_ready(p139):
    assert p139["provenance_readiness_summary"]["power_orthogonal_5bet"]["ready"] is True


def test_p10_truth_level(p139):
    assert p139["provenance_readiness_summary"]["power_precision_3bet"]["truth_level"] == "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"


def test_p12_truth_level(p139):
    assert p139["provenance_readiness_summary"]["power_orthogonal_5bet"]["truth_level"] == "POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"


# --- Markdown content ---

def test_markdown_has_classification():
    md = P139_MD.read_text()
    assert "P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY" in md


def test_markdown_has_executive_summary():
    md = P139_MD.read_text()
    assert "Executive Summary" in md or "executive summary" in md.lower()


def test_markdown_has_legacy_handling():
    md = P139_MD.read_text()
    assert "EXCLUDE_FROM_APPLY_BASE" in md or "LEGACY_UNVERIFIED" in md


def test_markdown_has_auth_phrases():
    md = P139_MD.read_text()
    assert "P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET" in md
    assert "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET" in md


def test_markdown_has_recommended_order():
    md = P139_MD.read_text()
    assert "P140" in md
    assert "P141" in md


def test_markdown_has_no_db_write():
    md = P139_MD.read_text()
    assert "No DB write" in md or "no DB write" in md or "No DB writes" in md


def test_markdown_has_estimated_rows():
    md = P139_MD.read_text()
    assert "3000" in md
    assert "6000" in md


# --- No dirty DB/runtime files staged ---

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
