"""
Tests for P144D: Keep legacy unverified as governed baseline — Option A decision recorded.

All assertions read from the generated JSON artifact.
No DB writes. No remediation executed.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs/replay/p144d_keep_legacy_unverified_governed_baseline_20260529.json"
MD_PATH = REPO_ROOT / "docs/replay/p144d_keep_legacy_unverified_governed_baseline_20260529.md"


def _load() -> dict:
    assert JSON_PATH.exists(), f"P144D JSON artifact not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


# ---- Existence ----

def test_p144d_json_exists():
    assert JSON_PATH.exists(), f"P144D JSON not found: {JSON_PATH}"


def test_p144d_md_exists():
    assert MD_PATH.exists(), f"P144D Markdown not found: {MD_PATH}"


# ---- Task identity ----

def test_task_id():
    d = _load()
    assert d["task_id"] == "P144D"


def test_classification():
    d = _load()
    assert d["classification"] == "P144D_LEGACY_UNVERIFIED_KEEP_GOVERNED_BASELINE_DECISION_RECORDED"


# ---- Authorization ----

def test_authorization_present():
    d = _load()
    assert d["authorization"]["authorization_present"] is True


def test_authorization_decision_allowed():
    d = _load()
    assert d["authorization"]["decision_allowed"] is True


# ---- Repo / branch ----

def test_repo_branch_repo_ok():
    d = _load()
    assert d["repo_branch_check"]["repo_ok"] is True


def test_repo_branch_branch_ok():
    d = _load()
    assert d["repo_branch_check"]["branch_ok"] is True


# ---- DB snapshot ----

def test_db_total_rows():
    d = _load()
    assert d["db_snapshot"]["total_rows"] == 94924


def test_db_bet_index_column_exists():
    d = _load()
    assert d["db_snapshot"]["bet_index_column_exists"] is True


# ---- P144C source summary ----

def test_p144c_classification():
    d = _load()
    assert d["p144c_source_summary"]["classification"] == "P144C_LEGACY_UNVERIFIED_REMEDIATION_AUTHORIZATION_GATE_READY"


# ---- Legacy unverified current state ----

def test_legacy_power_precision_3bet_rows():
    d = _load()
    assert d["legacy_unverified_current_state"]["power_precision_3bet_legacy_unverified_rows"] == 50


def test_legacy_power_orthogonal_5bet_rows():
    d = _load()
    assert d["legacy_unverified_current_state"]["power_orthogonal_5bet_legacy_unverified_rows"] == 50


def test_legacy_total_rows():
    d = _load()
    assert d["legacy_unverified_current_state"]["total_legacy_unverified_rows"] == 100


def test_legacy_all_bet_index_1():
    d = _load()
    assert d["legacy_unverified_current_state"]["all_rows_bet_index_1"] is True


def test_legacy_no_multi_bet_contamination():
    d = _load()
    assert d["legacy_unverified_current_state"]["p140_p141_multi_bet_contamination"] is False


def test_legacy_counts_ok():
    d = _load()
    assert d["legacy_unverified_current_state"]["counts_ok"] is True


# ---- Selected remediation option ----

def test_selected_option():
    d = _load()
    assert d["selected_remediation_option"]["selected_option"] == "option_a_keep_governed_legacy_baseline"


def test_db_mutation_required():
    d = _load()
    assert d["selected_remediation_option"]["db_mutation_required"] is False


def test_row_count_impact():
    d = _load()
    assert d["selected_remediation_option"]["row_count_impact"] == 0


def test_remediation_mutation_performed():
    d = _load()
    assert d["selected_remediation_option"]["remediation_mutation_performed"] is False


def test_execution_performed_in_p144d():
    d = _load()
    assert d["selected_remediation_option"]["execution_performed_in_p144d"] is True


def test_risk_level_none():
    d = _load()
    assert d["selected_remediation_option"]["risk_level"] == "NONE"


# ---- Governed baseline policy ----

def test_governed_keep_legacy_rows():
    d = _load()
    assert d["governed_baseline_policy"]["keep_legacy_unverified_rows"] is True


def test_governed_exclude_from_champion_eval():
    d = _load()
    assert d["governed_baseline_policy"]["exclude_from_champion_evaluation"] is True


def test_governed_exclude_from_apply_base():
    d = _load()
    assert d["governed_baseline_policy"]["exclude_from_apply_base"] is True


def test_governed_live_monitoring_not_blocked():
    d = _load()
    assert d["governed_baseline_policy"]["live_monitoring_blocked_by_legacy_rows"] is False


def test_governed_registry_not_blocked():
    d = _load()
    assert d["governed_baseline_policy"]["registry_update_blocked_by_legacy_rows"] is False


def test_governed_future_remediation_allowed():
    d = _load()
    assert d["governed_baseline_policy"]["future_remediation_allowed_with_new_authorization"] is True


# ---- Champion / monitoring impact ----

def test_champion_promotion_not_allowed_in_p144d():
    d = _load()
    assert d["champion_monitoring_impact"]["champion_promotion_allowed_in_p144d"] is False


def test_champion_eval_requires_live_monitoring():
    d = _load()
    assert d["champion_monitoring_impact"]["champion_eval_still_requires_live_monitoring_verified"] is True


def test_live_monitoring_can_continue():
    d = _load()
    assert d["champion_monitoring_impact"]["live_monitoring_can_continue"] is True


def test_p147_blocked_until_live_monitoring_verified():
    d = _load()
    assert d["champion_monitoring_impact"]["p147_blocked_until_live_monitoring_verified"] is True


# ---- Non-actions ----

def test_no_db_write():
    d = _load()
    assert d["non_actions"]["db_write_in_p144d"] is False


def test_no_controlled_apply():
    d = _load()
    assert d["non_actions"]["controlled_apply_executed_in_p144d"] is False


def test_no_remediation_mutation():
    d = _load()
    assert d["non_actions"]["remediation_mutation_executed_in_p144d"] is False


def test_zero_rows_inserted():
    d = _load()
    assert d["non_actions"]["replay_rows_inserted_in_p144d"] == 0


def test_zero_rows_updated():
    d = _load()
    assert d["non_actions"]["replay_rows_updated_in_p144d"] == 0


def test_zero_rows_deleted():
    d = _load()
    assert d["non_actions"]["replay_rows_deleted_in_p144d"] == 0


def test_no_registry_update():
    d = _load()
    assert d["non_actions"]["registry_update_executed_in_p144d"] is False


def test_no_champion_promotion():
    d = _load()
    assert d["non_actions"]["champion_promotion_executed_in_p144d"] is False


def test_no_monitoring_run():
    d = _load()
    assert d["non_actions"]["monitoring_run_executed_in_p144d"] is False


def test_no_scheduler():
    d = _load()
    assert d["non_actions"]["scheduler_installed"] is False


def test_no_live_api():
    d = _load()
    assert d["non_actions"]["live_api_called"] is False


def test_no_four_star():
    d = _load()
    assert d["non_actions"]["four_star_executed"] is False


def test_no_p108():
    d = _load()
    assert d["non_actions"]["p108_executed"] is False


def test_no_p117():
    d = _load()
    assert d["non_actions"]["p117_executed"] is False


def test_no_p118():
    d = _load()
    assert d["non_actions"]["p118_executed"] is False


# ---- Dirty file hygiene ----

def test_backups_untracked_not_staged():
    d = _load()
    assert d["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_forbidden_files_not_staged():
    d = _load()
    assert d["dirty_file_hygiene"]["forbidden_files_staged"] is False


# ---- Next task ----

def test_next_recommended_task():
    d = _load()
    assert d["next_recommended_task"] == "P147_CHAMPION_EVALUATION_GATE"
