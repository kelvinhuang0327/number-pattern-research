"""
Contract test for P189 — Post-Migration Verification and Commit Readiness Audit.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).parent.parent
ART_JSON    = REPO_ROOT / "outputs/research/power_lotto/p189_post_migration_verification_and_commit_readiness_20260601.json"
ART_MD      = REPO_ROOT / "outputs/research/power_lotto/p189_post_migration_verification_and_commit_readiness_20260601.md"
PROD_DB     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_DB   = REPO_ROOT / "backups" / "p188_lottery_v2_backup_20260601_153821.db"
DRIFT_GUARD = REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"
ACTIVE_TASK = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP     = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS= REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

PROD_ROWS  = 94924
BACKUP_ROWS = 54462


@pytest.fixture(scope="module")
def art() -> dict:
    assert ART_JSON.exists()
    return json.loads(ART_JSON.read_text())


# ── Artifacts ─────────────────────────────────────────────────────────────────
def test_p189_json_exists(): assert ART_JSON.exists()
def test_p189_md_exists():   assert ART_MD.exists()

# ── Classification ────────────────────────────────────────────────────────────
def test_p189_classification(art):
    assert art["final_classification"] == "P189_POST_MIGRATION_VERIFICATION_COMMIT_READINESS_READY"

def test_p189_auth_phrase(art):
    assert "YES start P189" in art["authorization_phrase_detected"]
    assert "post-migration verification and commit readiness audit" in art["authorization_phrase_detected"]

# ── Phase 0 ───────────────────────────────────────────────────────────────────
def test_p189_phase0_pass(art):
    assert art["phase_0_verification"]["status"] == "PASS"

# ── P188 referenced ───────────────────────────────────────────────────────────
def test_p189_p188_referenced(art):
    assert art["p188_classification_referenced"] == "P188_PRODUCTION_DB_MIGRATION_EXECUTED_RECONCILED_94924"

# ── Post-migration DB state ───────────────────────────────────────────────────
def test_p189_db_rows(art):
    assert art["post_migration_db_state"]["db_rows"] == PROD_ROWS

def test_p189_bet_index_present(art):
    assert art["post_migration_db_state"]["bet_index_present"] is True

def test_p189_bet_index_null_count(art):
    assert art["post_migration_db_state"]["bet_index_null_count"] == 0

def test_p189_duplicate_count(art):
    assert art["post_migration_db_state"]["duplicate_count"] == 0

# ── Live DB checks ────────────────────────────────────────────────────────────
def test_p189_prod_rows_live():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == PROD_ROWS

def test_p189_prod_bet_index_present_live():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    conn.close()
    assert "bet_index" in cols

def test_p189_prod_bet_index_null_live():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index IS NULL;").fetchone()[0]
    conn.close()
    assert n == 0

def test_p189_prod_duplicate_live():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    dup = conn.execute("SELECT COUNT(*) FROM (SELECT lottery_type,target_draw,strategy_id,bet_index,COUNT(*) FROM strategy_prediction_replays GROUP BY lottery_type,target_draw,strategy_id,bet_index HAVING COUNT(*)>1)").fetchone()[0]
    conn.close()
    assert dup == 0

# ── Backup verification ───────────────────────────────────────────────────────
def test_p189_backup_path(art):
    bp = REPO_ROOT / art["backup_verification"]["backup_path"]
    assert bp.exists()

def test_p189_backup_rows(art):
    assert art["backup_verification"]["backup_rows"] == BACKUP_ROWS

def test_p189_backup_bet_index_absent(art):
    assert art["backup_verification"]["backup_bet_index_absent"] is True

# ── Drift guard updated ───────────────────────────────────────────────────────
def test_p189_drift_guard_updated(art):
    assert art["drift_guard_update_result"]["status"] == "UPDATED_AND_PASS"

def test_p189_drift_guard_94924(art):
    guard_text = DRIFT_GUARD.read_text()
    assert "94924" in guard_text

def test_p189_drift_guard_legacy_420(art):
    guard_text = DRIFT_GUARD.read_text()
    assert "420" in guard_text

def test_p189_drift_guard_p126b(art):
    guard_text = DRIFT_GUARD.read_text()
    assert "P126B" in guard_text

# ── Stale test repair result ──────────────────────────────────────────────────
def test_p189_stale_tests_repaired(art):
    assert art["stale_tests_repair_result"]["status"] == "REPAIRED"
    assert art["stale_tests_repair_result"]["tests_fixed"] == 9

# ── Full test result ──────────────────────────────────────────────────────────
def test_p189_full_test_result(art):
    result = art["full_test_result"]["p178a_to_p188_tests"]
    assert "600 passed" in result
    assert "0 failed" in result

# ── Commit readiness ──────────────────────────────────────────────────────────
def test_p189_db_reconciliation_complete(art):
    assert art["commit_readiness_audit"]["db_level_reconciliation_completed"] is True

def test_p189_parity_complete(art):
    assert art["commit_readiness_audit"]["code_docs_tests_parity_completed_in_p182"] is True

def test_p189_backup_exists(art):
    assert art["commit_readiness_audit"]["p188_backup_exists"] is True

def test_p189_drift_guard_updated_in_audit(art):
    assert art["commit_readiness_audit"]["drift_guard_updated"] is True

def test_p189_tests_updated(art):
    assert art["commit_readiness_audit"]["tests_updated"] is True

def test_p189_no_stage_commit_push(art):
    assert art["commit_readiness_audit"]["no_stage_commit_push_yet"] is True
    assert art["commit_readiness_audit"]["staged_files"] == 0
    assert art["commit_readiness_audit"]["committed_files"] == 0
    assert art["commit_readiness_audit"]["pushed_files"] == 0

# ── Governance ────────────────────────────────────────────────────────────────
def test_p189_no_db_write(art):
    assert art["governance_confirmations"]["no_db_write_in_p189"] is True

def test_p189_no_controlled_apply(art):
    assert art["governance_confirmations"]["no_controlled_apply"] is True

def test_p189_no_research_rerun(art):
    assert art["governance_confirmations"]["no_research_rerun"] is True

def test_p189_no_stage(art):   assert art["governance_confirmations"]["no_stage"] is True
def test_p189_no_commit(art):  assert art["governance_confirmations"]["no_commit"] is True
def test_p189_no_push(art):    assert art["governance_confirmations"]["no_push"] is True

def test_p189_db_reconciled(art):
    assert art["governance_confirmations"]["main_zen_gates_split_reconciled_at_db_level"] is True

def test_p189_power_lotto_closed(art):
    assert art["governance_confirmations"]["power_lotto_research_closed"] is True

# ── P190 options ──────────────────────────────────────────────────────────────
def test_p189_p190_options(art):
    assert len(art["next_task_options"]) >= 4

def test_p189_p190_blocked(art):
    assert art["next_task_blocked_by_user_authorization"] is True

# ── Roadmap docs ──────────────────────────────────────────────────────────────
def test_p189_active_task_done():
    assert "P189" in ACTIVE_TASK.read_text()

def test_p189_active_task_p190_blocked():
    c = ACTIVE_TASK.read_text()
    assert "P190" in c and "BLOCKED" in c

def test_p189_roadmap_p189():
    assert "P189" in ROADMAP.read_text()

def test_p189_cto_p189():
    assert "P189" in CTO_ANALYSIS.read_text()

# ── No wagering ───────────────────────────────────────────────────────────────
def test_p189_no_wagering():
    c = ART_MD.read_text().lower()
    assert "guaranteed win" not in c
    assert "betting advice" not in c
