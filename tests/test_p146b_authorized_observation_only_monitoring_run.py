"""
Tests for P146B: Authorized observation-only monitoring run.

All assertions read from the generated JSON artifact.
No DB writes, no live API, no scheduler — observation-only.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = REPO_ROOT / "outputs/replay/p146b_authorized_observation_only_monitoring_run_20260529.json"
MD_PATH = REPO_ROOT / "docs/replay/p146b_authorized_observation_only_monitoring_run_20260529.md"

EXPECTED_6_STRATEGIES = {
    "acb_markov_midfreq_3bet",
    "midfreq_fourier_mk_3bet",
    "fourier_rhythm_3bet",
    "pp3_freqort_4bet",
    "power_precision_3bet",
    "power_orthogonal_5bet",
}


def _load() -> dict:
    assert JSON_PATH.exists(), f"P146B JSON artifact not found: {JSON_PATH}"
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_p146b_json_exists():
    assert JSON_PATH.exists(), f"P146B JSON not found: {JSON_PATH}"


def test_task_id():
    d = _load()
    assert d["task_id"] == "P146B"


def test_classification():
    d = _load()
    assert d["classification"] == "P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED"


def test_authorization_present():
    d = _load()
    assert d["authorization"]["authorization_present"] is True


def test_execution_allowed():
    d = _load()
    assert d["authorization"]["execution_allowed"] is True


def test_repo_ok():
    d = _load()
    assert d["repo_branch_check"]["repo_ok"] is True


def test_branch_ok():
    d = _load()
    assert d["repo_branch_check"]["branch_ok"] is True


def test_db_snapshot_total_rows():
    d = _load()
    assert d["db_snapshot"]["total_rows"] == 94924


def test_db_snapshot_bet_index_column():
    d = _load()
    assert d["db_snapshot"]["bet_index_column_exists"] is True


def test_p146a_source_classification():
    d = _load()
    assert d["p146a_source_summary"]["classification"] == "P146A_OBSERVATION_ONLY_MONITORING_RUNNER_READY"


def test_p145b_source_classification():
    d = _load()
    assert d["p145b_source_summary"]["classification"] == "P145B_MANUAL_ON_DEMAND_MONITORING_AUTHORIZATION_GATE_READY"


def test_monitoring_run_scope_output_mode():
    d = _load()
    assert d["monitoring_run_scope"]["output_mode"] == "file_artifact_only"


def test_monitoring_run_scope_no_db_write():
    d = _load()
    assert d["monitoring_run_scope"]["production_db_write"] is False


def test_monitoring_run_scope_no_live_api():
    d = _load()
    assert d["monitoring_run_scope"]["live_api_call"] is False


def test_monitoring_run_scope_executed():
    d = _load()
    assert d["monitoring_run_scope"]["monitoring_run_executed"] is True


def test_observation_output_no_db_written():
    d = _load()
    assert d["observation_output_summary"]["production_db_written"] is False


def test_observation_output_no_live_api():
    d = _load()
    assert d["observation_output_summary"]["live_api_called"] is False


def test_observation_output_schema_valid():
    d = _load()
    assert d["observation_output_summary"]["output_schema_valid"] is True


def test_per_strategy_count():
    d = _load()
    assert len(d["per_strategy_monitoring_results"]) == 6


def test_per_strategy_all_6_present():
    d = _load()
    found = {r["strategy_id"] for r in d["per_strategy_monitoring_results"]}
    assert found == EXPECTED_6_STRATEGIES


def test_per_strategy_all_not_champion_eligible():
    d = _load()
    for r in d["per_strategy_monitoring_results"]:
        assert r["champion_evidence_eligible"] is False, (
            f"Strategy {r['strategy_id']} should not be champion eligible"
        )


def test_historical_backfill_not_live_evidence():
    d = _load()
    assert d["historical_vs_live_boundary"]["historical_backfill_is_not_live_evidence"] is True


def test_observation_only_not_champion_promotion():
    d = _load()
    assert d["historical_vs_live_boundary"]["observation_only_is_not_champion_promotion"] is True


def test_champion_eval_not_ready_from_p146b():
    d = _load()
    assert d["historical_vs_live_boundary"]["champion_eval_ready_from_p146b"] is False


def test_champion_promotion_not_allowed():
    d = _load()
    assert d["champion_evaluation_impact"]["champion_promotion_allowed"] is False


def test_registry_update_not_allowed():
    d = _load()
    assert d["champion_evaluation_impact"]["registry_update_allowed"] is False


def test_non_action_no_db_write():
    d = _load()
    assert d["non_actions"]["db_write_in_p146b"] is False


def test_non_action_no_live_api():
    d = _load()
    assert d["non_actions"]["live_api_called"] is False


def test_non_action_no_scheduler():
    d = _load()
    assert d["non_actions"]["scheduler_installed"] is False


def test_non_action_no_four_star():
    d = _load()
    assert d["non_actions"]["four_star_executed"] is False


def test_non_action_no_p108():
    d = _load()
    assert d["non_actions"]["p108_executed"] is False


def test_non_action_no_p117():
    d = _load()
    assert d["non_actions"]["p117_executed"] is False


def test_non_action_no_p118():
    d = _load()
    assert d["non_actions"]["p118_executed"] is False


def test_dirty_hygiene_backups_untracked():
    d = _load()
    assert d["dirty_file_hygiene"]["backups_untracked_not_staged"] is True


def test_dirty_hygiene_no_forbidden_staged():
    d = _load()
    assert d["dirty_file_hygiene"]["forbidden_files_staged"] is False


def test_markdown_exists():
    assert MD_PATH.exists(), f"P146B Markdown not found: {MD_PATH}"
