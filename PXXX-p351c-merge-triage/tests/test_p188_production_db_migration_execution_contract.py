"""
Contract test for P188 — Production DB Migration Execution.
Verifies migration succeeded: 94924 rows, bet_index present, backup exists.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).parent.parent
ART_JSON    = REPO_ROOT / "outputs/research/power_lotto/p188_production_db_migration_execution_20260601.json"
ART_MD      = REPO_ROOT / "outputs/research/power_lotto/p188_production_db_migration_execution_20260601.md"
PROD_DB     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
BACKUP_PATH = REPO_ROOT / "backups" / "p188_lottery_v2_backup_20260601_153821.db"
SQL_LOG     = REPO_ROOT / "outputs/research/power_lotto/p188_production_db_migration_sql_log_20260601.sql"
ACTIVE_TASK = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP     = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS= REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

ROWS_BEFORE  = 54462
ROWS_AFTER   = 94924
DROPPED_ROWS = 160
IMPORT_ROWS  = 40622


@pytest.fixture(scope="module")
def art() -> dict:
    assert ART_JSON.exists()
    return json.loads(ART_JSON.read_text())


# ── Artifacts ─────────────────────────────────────────────────────────────────
def test_p188_json_exists(): assert ART_JSON.exists()
def test_p188_md_exists():   assert ART_MD.exists()
def test_p188_sql_log_exists(): assert SQL_LOG.exists()

# ── Classification ────────────────────────────────────────────────────────────
def test_p188_classification(art):
    assert art["final_classification"] == "P188_PRODUCTION_DB_MIGRATION_EXECUTED_RECONCILED_94924"

def test_p188_auth_phrase(art):
    p = art["exact_authorization_phrase_detected"]
    assert "YES execute P188" in p
    assert "54462" in p and "94924" in p
    assert "P185 rehearsal SQL" in p
    assert "MAX(id) dedup" in p
    assert "160 null-provenance" in p
    assert "timestamped backup" in p
    assert "no controlled_apply" in p

# ── Backup ────────────────────────────────────────────────────────────────────
def test_p188_backup_path_exists(art):
    bp = REPO_ROOT / art["backup_path"]
    assert bp.exists(), f"Backup file missing: {bp}"

def test_p188_backup_sha256_exists(art):
    sp = REPO_ROOT / art["backup_sha256_path"] if "backup_sha256_path" in art["backup_result"] else REPO_ROOT / "backups/p188_lottery_v2_backup_20260601_153821.db.sha256"
    assert sp.exists()

def test_p188_backup_rows(art):
    assert art["backup_result"]["backup_rows"] == ROWS_BEFORE

def test_p188_backup_bet_index_absent(art):
    assert art["backup_result"]["backup_bet_index"] == "ABSENT"

def test_p188_backup_integrity(art):
    assert art["backup_result"]["backup_integrity"] == "ok"

def test_p188_backup_verified_before_migration(art):
    assert art["backup_result"]["verified_before_migration"] is True

# ── Production DB rows after ──────────────────────────────────────────────────
def test_p188_db_rows_after(art):
    assert art["db_rows_after"] == ROWS_AFTER

def test_p188_db_rows_before(art):
    assert art["db_rows_before"] == ROWS_BEFORE

def test_p188_bet_index_after(art):
    assert art["bet_index_after"] == "PRESENT"

# ── Live DB checks ────────────────────────────────────────────────────────────
def test_p188_prod_rows_live():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == ROWS_AFTER

def test_p188_prod_bet_index_present():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    conn.close()
    assert "bet_index" in cols

def test_p188_prod_bet_index_null_count():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index IS NULL;").fetchone()[0]
    conn.close()
    assert n == 0

def test_p188_prod_duplicate_check():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    dup = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT lottery_type,target_draw,strategy_id,bet_index,COUNT(*)
            FROM strategy_prediction_replays
            GROUP BY lottery_type,target_draw,strategy_id,bet_index HAVING COUNT(*)>1
        )""").fetchone()[0]
    conn.close()
    assert dup == 0

def test_p188_prod_integrity():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    result = conn.execute("PRAGMA integrity_check;").fetchone()[0]
    conn.close()
    assert result == "ok"

def test_p188_prod_per_lottery():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    expected = {"BIG_LOTTO": 24140, "DAILY_539": 34680, "POWER_LOTTO": 36104}
    for lt, exp in expected.items():
        n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type=?", (lt,)).fetchone()[0]
        assert n == exp, f"{lt}: expected {exp}, got {n}"
    conn.close()

def test_p188_prod_bet_index_distribution():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    expected = {1: 54302, 2: 16581, 3: 15041, 4: 6000, 5: 3000}
    for bi, exp in expected.items():
        n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index=?", (bi,)).fetchone()[0]
        assert n == exp, f"bet_index={bi}: expected {exp}, got {n}"
    conn.close()

# ── Migration result ──────────────────────────────────────────────────────────
def test_p188_imported_rows(art):
    assert art["imported_rows"] == IMPORT_ROWS

def test_p188_dropped_rows(art):
    assert art["dropped_duplicate_rows"] == DROPPED_ROWS

def test_p188_migration_status(art):
    assert art["migration_execution_result"]["status"] == "PASS"

# ── Governance ────────────────────────────────────────────────────────────────
def test_p188_migration_executed(art):
    assert art["governance_confirmations"]["production_db_migration_executed"] is True

def test_p188_backup_created(art):
    assert art["governance_confirmations"]["backup_created"] is True

def test_p188_dedup_policy(art):
    assert art["governance_confirmations"]["max_id_dedup_policy_used"] is True

def test_p188_dropped_160(art):
    assert art["governance_confirmations"]["dropped_160_null_provenance_duplicates"] is True

def test_p188_imported_40622(art):
    assert art["governance_confirmations"]["imported_40622_rows"] is True

def test_p188_no_controlled_apply(art):
    assert art["governance_confirmations"]["no_controlled_apply"] is True

def test_p188_no_registry_mutation(art):
    assert art["governance_confirmations"]["no_registry_mutation"] is True

def test_p188_no_research_rerun(art):
    assert art["governance_confirmations"]["no_research_rerun"] is True

def test_p188_no_stage(art):   assert art["governance_confirmations"]["no_stage"] is True
def test_p188_no_commit(art):  assert art["governance_confirmations"]["no_commit"] is True
def test_p188_no_push(art):    assert art["governance_confirmations"]["no_push"] is True

def test_p188_db_reconciled(art):
    assert art["governance_confirmations"]["main_zen_gates_split_reconciled_at_db_level"] is True

def test_p188_p182_parity(art):
    assert art["governance_confirmations"]["code_docs_tests_parity_previously_completed"] is True

def test_p188_power_lotto_closed(art):
    assert art["governance_confirmations"]["power_lotto_research_closed"] is True

# ── P189 options ──────────────────────────────────────────────────────────────
def test_p188_p189_options(art):
    assert len(art["next_task_options"]) >= 4

def test_p188_p189_blocked(art):
    assert art["next_task_blocked_by_user_authorization"] is True

# ── Roadmap docs ──────────────────────────────────────────────────────────────
def test_p188_active_task_done():
    assert "P188" in ACTIVE_TASK.read_text()

def test_p188_active_task_p189_blocked():
    c = ACTIVE_TASK.read_text()
    assert "P189" in c and "BLOCKED" in c

def test_p188_roadmap_p188():
    assert "P188" in ROADMAP.read_text()

def test_p188_cto_p188():
    assert "P188" in CTO_ANALYSIS.read_text()

# ── No wagering ───────────────────────────────────────────────────────────────
def test_p188_no_wagering():
    c = ART_MD.read_text().lower()
    assert "guaranteed win" not in c
    assert "betting advice" not in c
