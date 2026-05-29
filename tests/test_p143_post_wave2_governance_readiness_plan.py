"""
tests/test_p143_post_wave2_governance_readiness_plan.py
=======================================================
Verification tests for P143: Post-Wave2 governance readiness plan.

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
SCRIPT = REPO_ROOT / "scripts" / "p143_post_wave2_governance_readiness_plan.py"
ARTIFACT = REPO_ROOT / "outputs" / "replay" / "p143_post_wave2_governance_readiness_plan_20260529.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p143_post_wave2_governance_readiness_plan_20260529.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CLASSIFICATION = "P143_POST_WAVE2_GOVERNANCE_READINESS_PLAN_READY"
EXPECTED_ROWS = 94924


@pytest.fixture(scope="module", autouse=True)
def generate_p143_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "P143" in result.stdout or result.stdout.strip()


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P143 JSON not found: {ARTIFACT}"
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
    assert artifact["task_id"] == "P143"


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


def test_bet_index_schema_exists(artifact):
    assert artifact["db_snapshot"]["bet_index_schema_exists"] is True


# ── Source artifact classification ────────────────────────────────────────────

def test_p142_classification(artifact):
    assert artifact["source_artifact_summary"]["p142"]["classification"] == "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED"


def test_p141_classification(artifact):
    assert artifact["source_artifact_summary"]["p141"]["classification"] == "P141_POWER_ORTHOGONAL_5BET_APPLIED"


def test_p140_classification(artifact):
    assert artifact["source_artifact_summary"]["p140"]["classification"] == "P140_POWER_PRECISION_3BET_APPLIED"


def test_all_classifications_pass(artifact):
    assert artifact["source_artifact_summary"]["all_required_classifications_pass"] is True


# ── Wave2 chain closure summary ───────────────────────────────────────────────

def test_wave2_chain_p142_classification(artifact):
    assert artifact["wave2_chain_closure_summary"]["p142_classification"] == "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED"


def test_wave2_chain_current_rows(artifact):
    assert artifact["wave2_chain_closure_summary"]["current_rows"] == EXPECTED_ROWS


def test_total_wave2_multibet_inserted_rows(artifact):
    assert artifact["wave2_chain_closure_summary"]["total_wave2_multibet_inserted_rows"] == 22502


def test_p10_p12_final_apply_chain_completed(artifact):
    assert artifact["wave2_chain_closure_summary"]["p10_p12_final_apply_chain_completed"] is True


def test_wave2_chain_row_breakdown(artifact):
    s = artifact["wave2_chain_closure_summary"]
    assert s["p131_rows"] == 3000
    assert s["p132_rows"] == 3000
    assert s["p133_rows"] == 4500
    assert s["p134_rows"] == 3002
    assert s["p140_rows"] == 3000
    assert s["p141_rows"] == 6000


# ── Governance readiness matrix ───────────────────────────────────────────────

def test_governance_matrix_has_registry(artifact):
    assert "strategy_champion_registry_update" in artifact["governance_readiness_matrix"]


def test_governance_matrix_has_monitoring(artifact):
    assert "live_draw_monitoring_activation" in artifact["governance_readiness_matrix"]


def test_governance_matrix_has_legacy_remediation(artifact):
    assert "legacy_unverified_remediation" in artifact["governance_readiness_matrix"]


def test_governance_registry_not_started(artifact):
    assert artifact["governance_readiness_matrix"]["strategy_champion_registry_update"]["current_status"] == "NOT_STARTED"


def test_governance_monitoring_not_started(artifact):
    assert artifact["governance_readiness_matrix"]["live_draw_monitoring_activation"]["current_status"] == "NOT_STARTED"


def test_governance_legacy_pending_decision(artifact):
    assert artifact["governance_readiness_matrix"]["legacy_unverified_remediation"]["current_status"] == "PENDING_DECISION"


def test_governance_registry_db_mutation_false(artifact):
    assert artifact["governance_readiness_matrix"]["strategy_champion_registry_update"]["db_mutation_required"] is False


def test_governance_monitoring_db_mutation_false(artifact):
    assert artifact["governance_readiness_matrix"]["live_draw_monitoring_activation"]["db_mutation_required"] is False


def test_governance_legacy_db_mutation_required(artifact):
    assert artifact["governance_readiness_matrix"]["legacy_unverified_remediation"]["db_mutation_required"] is True


# ── Champion registry readiness ───────────────────────────────────────────────

def test_registry_update_not_executed(artifact):
    assert artifact["champion_registry_readiness"]["registry_update_executed_in_p143"] is False


def test_registry_total_candidates(artifact):
    assert artifact["champion_registry_readiness"]["total_candidates"] == 6


def test_registry_authorization_required(artifact):
    assert artifact["champion_registry_readiness"]["authorization_required_later"] is True


def test_registry_no_eval_ready(artifact):
    assert artifact["champion_registry_readiness"]["champion_eval_ready_count"] == 0


def test_registry_wave2_safe_candidates_present(artifact):
    cands = artifact["champion_registry_readiness"]["wave2_safe_candidates"]
    assert "acb_markov_midfreq_3bet" in cands
    assert "midfreq_fourier_mk_3bet" in cands
    assert "fourier_rhythm_3bet" in cands
    assert "pp3_freqort_4bet" in cands


def test_registry_p10_p12_strategies_present(artifact):
    strats = artifact["champion_registry_readiness"]["p10_p12_strategies"]
    assert "power_precision_3bet" in strats
    assert "power_orthogonal_5bet" in strats


# ── Live monitoring readiness ─────────────────────────────────────────────────

def test_monitoring_not_activated(artifact):
    assert artifact["live_monitoring_readiness"]["monitoring_activated_in_p143"] is False


def test_monitoring_no_scheduler(artifact):
    assert artifact["live_monitoring_readiness"]["scheduler_installed"] is False


def test_monitoring_authorization_required(artifact):
    assert artifact["live_monitoring_readiness"]["authorization_required_later"] is True


def test_monitoring_db_prereq_satisfied(artifact):
    assert artifact["live_monitoring_readiness"]["db_rows_prerequisite"]["satisfied"] is True


def test_monitoring_drift_guard_prereq_satisfied(artifact):
    assert artifact["live_monitoring_readiness"]["drift_guard_prerequisite"]["satisfied"] is True


def test_monitoring_infra_not_met(artifact):
    assert artifact["live_monitoring_readiness"]["infrastructure_prerequisites_met"] is False


# ── LEGACY_UNVERIFIED remediation readiness ───────────────────────────────────

def test_legacy_total_rows(artifact):
    assert artifact["legacy_unverified_remediation_readiness"]["legacy_unverified_rows_total"] == 100


def test_legacy_pp3_rows(artifact):
    assert artifact["legacy_unverified_remediation_readiness"]["power_precision_3bet_legacy_rows"] == 50


def test_legacy_po5_rows(artifact):
    assert artifact["legacy_unverified_remediation_readiness"]["power_orthogonal_5bet_legacy_rows"] == 50


def test_legacy_remediation_not_executed(artifact):
    assert artifact["legacy_unverified_remediation_readiness"]["remediation_executed_in_p143"] is False


def test_legacy_db_write_false(artifact):
    assert artifact["legacy_unverified_remediation_readiness"]["db_write_in_p143"] is False


def test_legacy_options_present(artifact):
    opts = artifact["legacy_unverified_remediation_readiness"]["options"]
    assert "keep" in opts
    assert "remark" in opts
    assert "quarantine" in opts
    assert "archive" in opts


def test_legacy_authorization_required(artifact):
    assert artifact["legacy_unverified_remediation_readiness"]["authorization_required_later"] is True


def test_legacy_recommended_option(artifact):
    assert artifact["legacy_unverified_remediation_readiness"]["recommended_option"] == "remark"


# ── Non-actions ───────────────────────────────────────────────────────────────

def test_no_db_write_in_p143(artifact):
    assert artifact["non_actions"]["db_write_in_p143"] is False


def test_no_controlled_apply_in_p143(artifact):
    assert artifact["non_actions"]["controlled_apply_executed_in_p143"] is False


def test_no_replay_rows_inserted(artifact):
    assert artifact["non_actions"]["replay_rows_inserted_in_p143"] == 0


def test_no_replay_rows_deleted(artifact):
    assert artifact["non_actions"]["replay_rows_deleted_in_p143"] == 0


def test_no_registry_update(artifact):
    assert artifact["non_actions"]["registry_update_executed_in_p143"] is False


def test_no_monitoring_activated(artifact):
    assert artifact["non_actions"]["monitoring_activated_in_p143"] is False


def test_no_scheduler_installed(artifact):
    assert artifact["non_actions"]["scheduler_installed"] is False


def test_no_four_star(artifact):
    assert artifact["non_actions"]["four_star_executed"] is False


def test_no_p108(artifact):
    assert artifact["non_actions"]["p108_executed"] is False


# ── Drift guard ───────────────────────────────────────────────────────────────

def test_drift_guard_status(artifact):
    assert artifact["drift_guard_result"]["status"] == "PASS"


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


def test_markdown_classification():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "P143_POST_WAVE2_GOVERNANCE_READINESS_PLAN_READY" in text


def test_markdown_sections():
    text = MD_PATH.read_text(encoding="utf-8")
    for section in [
        "Executive Summary",
        "Canonical Repo / Branch Confirmation",
        "P142 Closure Recap",
        "Final Wave 2 Chain Summary",
        "Final Strategy Distribution Matrix",
        "Governance Readiness Matrix",
        "Champion Registry Readiness",
        "Live Draw Monitoring Readiness",
        "LEGACY_UNVERIFIED Remediation Readiness",
        "Explicit Non-Actions",
        "Dirty File Hygiene Note",
        "Remaining Risks",
        "Recommended Next Task",
        "Final Classification",
    ]:
        assert section in text, f"Missing Markdown section: {section}"


def test_markdown_total_inserted_rows():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "22,502" in text


def test_markdown_governance_readiness_matrix():
    text = MD_PATH.read_text(encoding="utf-8")
    assert "Strategy champion registry update" in text
    assert "Live draw monitoring activation" in text
    assert "LEGACY_UNVERIFIED" in text


# ── Live DB constraints ───────────────────────────────────────────────────────

def test_live_db_total_rows(db_conn):
    count = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert count == EXPECTED_ROWS


def test_live_db_bet_index_schema(db_conn):
    cols = [row[1] for row in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    assert "bet_index" in cols


def test_live_db_legacy_pp3(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_precision_3bet' AND truth_level='LEGACY_UNVERIFIED'",
    ).fetchone()[0]
    assert cnt == 50


def test_live_db_legacy_po5(db_conn):
    cnt = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND truth_level='LEGACY_UNVERIFIED'",
    ).fetchone()[0]
    assert cnt == 50


def test_live_db_po5_distribution(db_conn):
    for bi in (2, 3, 4, 5):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            ("power_orthogonal_5bet", bi),
        ).fetchone()[0]
        assert cnt == 1500


def test_live_db_pp3_distribution(db_conn):
    for bi in (2, 3):
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=?",
            ("power_precision_3bet", bi),
        ).fetchone()[0]
        assert cnt == 1500


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
