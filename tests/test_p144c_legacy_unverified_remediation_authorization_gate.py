"""
Tests for P144C: Legacy unverified remediation authorization gate.

All assertions read from the generated JSON artifact.
No DB writes, no remediation executed — authorization gate only.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs/replay/p144c_legacy_unverified_remediation_authorization_gate_20260529.json"
MD_PATH = REPO_ROOT / "docs/replay/p144c_legacy_unverified_remediation_authorization_gate_20260529.md"


def _load() -> dict:
    assert JSON_PATH.exists(), f"P144C JSON artifact not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


# ---- Existence ----

def test_p144c_json_exists():
    assert JSON_PATH.exists(), f"P144C JSON not found: {JSON_PATH}"


def test_p144c_md_exists():
    assert MD_PATH.exists(), f"P144C Markdown not found: {MD_PATH}"


# ---- Task identity ----

def test_task_id():
    d = _load()
    assert d["task_id"] == "P144C"


def test_classification():
    d = _load()
    assert d["classification"] == "P144C_LEGACY_UNVERIFIED_REMEDIATION_AUTHORIZATION_GATE_READY"


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


# ---- Predecessor artifacts ----

def test_p146b_classification():
    d = _load()
    assert d["p146b_source_summary"]["classification"] == "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED"


def test_p142_classification():
    d = _load()
    assert d["p142_source_summary"]["classification"] == "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED"


def test_p138b_classification():
    d = _load()
    assert d["p138b_source_summary"]["classification"] == "P138B_P10_P12_LEGACY_ROWS_REMARKED"


# ---- LEGACY_UNVERIFIED current state ----

def test_power_precision_3bet_legacy_rows():
    d = _load()
    assert d["legacy_unverified_current_state"]["power_precision_3bet_legacy_unverified_rows"] == 50


def test_power_orthogonal_5bet_legacy_rows():
    d = _load()
    assert d["legacy_unverified_current_state"]["power_orthogonal_5bet_legacy_unverified_rows"] == 50


def test_total_legacy_unverified_rows():
    d = _load()
    assert d["legacy_unverified_current_state"]["total_legacy_unverified_rows"] == 100


def test_p140_p141_multi_bet_contamination():
    d = _load()
    assert d["legacy_unverified_current_state"]["p140_p141_multi_bet_contamination"] is False


def test_all_rows_bet_index_1():
    d = _load()
    assert d["legacy_unverified_current_state"]["all_rows_bet_index_1"] is True


def test_all_rows_controlled_apply_id_null():
    d = _load()
    assert d["legacy_unverified_current_state"]["all_rows_controlled_apply_id_null"] is True


# ---- Strict selector definitions ----

def test_strict_selector_definitions_present():
    d = _load()
    ssd = d["strict_selector_definitions"]
    assert ssd is not None
    assert "power_precision_3bet" in ssd["strategy_id_in"]
    assert "power_orthogonal_5bet" in ssd["strategy_id_in"]


def test_strict_selector_truth_level():
    d = _load()
    assert d["strict_selector_definitions"]["truth_level"] == "LEGACY_UNVERIFIED"


def test_strict_selector_bet_index():
    d = _load()
    assert d["strict_selector_definitions"]["bet_index"] == 1


# ---- Remediation option matrix ----

def test_option_a_present():
    d = _load()
    assert "option_a_keep_governed_legacy_baseline" in d["remediation_option_matrix"]


def test_option_b_present():
    d = _load()
    assert "option_b_enrich_provenance_metadata" in d["remediation_option_matrix"]


def test_option_c_present():
    d = _load()
    assert "option_c_quarantine_with_backup" in d["remediation_option_matrix"]


def test_option_d_present():
    d = _load()
    assert "option_d_delete_with_strict_selector" in d["remediation_option_matrix"]


def test_option_a_no_db_mutation():
    d = _load()
    opt_a = d["remediation_option_matrix"]["option_a_keep_governed_legacy_baseline"]
    assert opt_a["db_mutation_required"] is False
    assert opt_a["row_count_impact"] == 0
    assert opt_a["backup_required"] is False
    assert opt_a["risk_level"] == "NONE"


def test_option_d_high_risk():
    d = _load()
    opt_d = d["remediation_option_matrix"]["option_d_delete_with_strict_selector"]
    assert opt_d["db_mutation_required"] is True
    assert opt_d["row_count_impact"] == -100
    assert opt_d["backup_required"] is True


# ---- Authorization phrase templates ----

def test_auth_phrase_option_a():
    d = _load()
    phrases = list(d["authorization_phrase_templates"].values())
    assert "P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529" in phrases


def test_auth_phrase_option_b():
    d = _load()
    phrases = list(d["authorization_phrase_templates"].values())
    assert "P144C_AUTHORIZED_ENRICH_P10_P12_LEGACY_UNVERIFIED_PROVENANCE_20260529" in phrases


def test_auth_phrase_option_c():
    d = _load()
    phrases = list(d["authorization_phrase_templates"].values())
    assert "P144C_AUTHORIZED_QUARANTINE_P10_P12_LEGACY_UNVERIFIED_WITH_BACKUP_20260529" in phrases


def test_auth_phrase_option_d():
    d = _load()
    phrases = list(d["authorization_phrase_templates"].values())
    assert "P144C_AUTHORIZED_DELETE_P10_P12_LEGACY_UNVERIFIED_WITH_STRICT_SELECTOR_20260529" in phrases


def test_all_four_auth_phrases_present():
    d = _load()
    phrases = set(d["authorization_phrase_templates"].values())
    expected = {
        "P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529",
        "P144C_AUTHORIZED_ENRICH_P10_P12_LEGACY_UNVERIFIED_PROVENANCE_20260529",
        "P144C_AUTHORIZED_QUARANTINE_P10_P12_LEGACY_UNVERIFIED_WITH_BACKUP_20260529",
        "P144C_AUTHORIZED_DELETE_P10_P12_LEGACY_UNVERIFIED_WITH_STRICT_SELECTOR_20260529",
    }
    assert expected == phrases


# ---- Champion monitoring impact ----

def test_champion_promotion_not_allowed():
    d = _load()
    assert d["champion_monitoring_impact"]["champion_promotion_allowed_in_p144c"] is False


def test_live_monitoring_not_blocked():
    d = _load()
    assert d["champion_monitoring_impact"]["live_monitoring_blocked_by_legacy_rows"] is False


def test_registry_not_blocked():
    d = _load()
    assert d["champion_monitoring_impact"]["registry_update_blocked_by_legacy_rows"] is False


# ---- Non-actions ----

def test_no_db_write():
    d = _load()
    assert d["non_actions"]["db_write_in_p144c"] is False


def test_no_remediation_executed():
    d = _load()
    assert d["non_actions"]["remediation_executed_in_p144c"] is False


def test_replay_rows_updated_zero():
    d = _load()
    assert d["non_actions"]["replay_rows_updated_in_p144c"] == 0


def test_replay_rows_deleted_zero():
    d = _load()
    assert d["non_actions"]["replay_rows_deleted_in_p144c"] == 0


def test_no_four_star_executed():
    d = _load()
    assert d["non_actions"]["four_star_executed"] is False


def test_no_p108_executed():
    d = _load()
    assert d["non_actions"]["p108_executed"] is False


def test_no_p117_executed():
    d = _load()
    assert d["non_actions"]["p117_executed"] is False


def test_no_p118_executed():
    d = _load()
    assert d["non_actions"]["p118_executed"] is False


def test_no_controlled_apply_executed():
    d = _load()
    assert d["non_actions"]["controlled_apply_executed"] is False


# ---- Dirty file hygiene ----

def test_backups_untracked_not_staged():
    d = _load()
    assert d["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_forbidden_files_not_staged():
    d = _load()
    assert d["dirty_file_hygiene"]["forbidden_files_staged"] is False
