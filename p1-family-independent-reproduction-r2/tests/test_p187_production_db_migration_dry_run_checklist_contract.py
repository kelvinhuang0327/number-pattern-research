"""
Contract test for P187 — Production DB Migration Dry-Run Checklist (Plan Only).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).parent.parent
ART_JSON    = REPO_ROOT / "outputs/research/power_lotto/p187_production_db_migration_dry_run_checklist_20260601.json"
ART_MD      = REPO_ROOT / "outputs/research/power_lotto/p187_production_db_migration_dry_run_checklist_20260601.md"
PROD_DB     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
ACTIVE_TASK = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP     = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS= REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

PROD_ROWS   = 54462
FINAL_ROWS  = 94924
DROPPED     = 160
IMPORT_ROWS = 40622

DESTRUCTIVE_PHRASE = (
    "YES execute P188 production DB migration from main 54462 to reconciled 94924 "
    "using P185 rehearsal SQL, approve MAX(id) dedup dropping 160 null-provenance "
    "duplicate rows, create timestamped backup, no controlled_apply"
)


@pytest.fixture(scope="module")
def art() -> dict:
    assert ART_JSON.exists()
    return json.loads(ART_JSON.read_text())


# ── Artifacts ────────────────────────────────────────────────────────────────
def test_p187_json_exists(): assert ART_JSON.exists()
def test_p187_md_exists():   assert ART_MD.exists()

# ── Classification ────────────────────────────────────────────────────────────
def test_p187_classification(art):
    assert art["final_classification"] == "P187_PRODUCTION_DB_MIGRATION_DRY_RUN_CHECKLIST_READY"

def test_p187_authorization_phrase(art):
    p = art["authorization_phrase_detected"]
    assert "YES start P187" in p
    assert "production DB migration dry-run checklist only" in p

# ── Phase 0 ───────────────────────────────────────────────────────────────────
def test_p187_phase0_pass(art):
    assert art["phase_0_verification"]["status"] == "PASS"

def test_p187_phase0_branch(art):
    assert art["phase_0_verification"]["branch"] == "main"

# ── P186 referenced ───────────────────────────────────────────────────────────
def test_p187_p186_referenced(art):
    assert art["p186_classification_referenced"] == "P186_PRODUCTION_DB_MIGRATION_AUTHORIZATION_GATE_READY"

# ── Production DB rows before/after ──────────────────────────────────────────
def test_p187_prod_rows_before(art):
    gov = art["governance_confirmations"]
    assert gov["production_main_db_rows_before"] == PROD_ROWS

def test_p187_prod_rows_after(art):
    gov = art["governance_confirmations"]
    assert gov["production_main_db_rows_after"] == PROD_ROWS

def test_p187_prod_db_unchanged(art):
    assert art["governance_confirmations"]["production_main_db_unchanged"] is True

def test_p187_prod_bet_index_absent(art):
    gov = art["governance_confirmations"]
    assert gov["production_main_bet_index_before"] == "ABSENT"
    assert gov["production_main_bet_index_after"] == "ABSENT"

# ── Production DB live check ──────────────────────────────────────────────────
def test_p187_prod_rows_live():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == 94924, f"Expected 94924 (post-P188 migrated), got {n}"

def test_p187_prod_bet_index_now_present():  # renamed: post-P188 bet_index PRESENT
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    conn.close()
    assert "bet_index" in cols, "bet_index must be PRESENT after P188 migration"

# ── Dry-run checklist has >= 13 items ────────────────────────────────────────
def test_p187_checklist_has_13_items(art):
    items = art["dry_run_checklist"]["items"]
    assert len(items) >= 13

def test_p187_checklist_has_drc01(art):
    assert "DRC-01_dispatch" in art["dry_run_checklist"]["items"]

def test_p187_checklist_has_drc13_go_no_go(art):
    assert "DRC-13_go_no_go" in art["dry_run_checklist"]["items"]

def test_p187_checklist_has_backup_item(art):
    items = art["dry_run_checklist"]["items"]
    assert "DRC-11_create_backup" in items

def test_p187_checklist_stop_on_failure(art):
    assert art["dry_run_checklist"]["description"] is not None

# ── SQL review checklist has required items ───────────────────────────────────
def test_p187_sql_checklist_has_12_items(art):
    assert len(art["sql_review_checklist"]["items"]) >= 12

def test_p187_sql_table_recreation(art):
    items = art["sql_review_checklist"]["items"]
    checks = [i["item"] for i in items]
    assert "table_recreation" in checks

def test_p187_sql_max_id_dedup(art):
    items = art["sql_review_checklist"]["items"]
    checks = [i["item"] for i in items]
    assert "max_id_dedup" in checks

def test_p187_sql_bet_index_column(art):
    items = art["sql_review_checklist"]["items"]
    checks = [i["item"] for i in items]
    assert "bet_index_column" in checks

def test_p187_sql_unique_constraint(art):
    items = art["sql_review_checklist"]["items"]
    checks = [i["item"] for i in items]
    assert "unique_constraint" in checks

def test_p187_sql_import_filter(art):
    items = art["sql_review_checklist"]["items"]
    checks = [i["item"] for i in items]
    assert "import_filter" in checks

# ── Backup / rollback checklist present ──────────────────────────────────────
def test_p187_backup_rollback_present(art):
    assert "backup_rollback_checklist" in art
    assert "backup" in art["backup_rollback_checklist"]
    assert "rollback_triggers" in art["backup_rollback_checklist"]
    assert "rollback_procedure" in art["backup_rollback_checklist"]

def test_p187_backup_stop_on_failure(art):
    assert art["backup_rollback_checklist"]["backup"]["stop_if_backup_fails"] is True

# ── Destructive phrase is next option only, NOT current authorization ─────────
def test_p187_destructive_phrase_not_current_auth(art):
    detected = art["authorization_phrase_detected"]
    assert "YES execute P188" not in detected, \
        "Destructive phrase must NOT appear as current authorization"

def test_p187_destructive_phrase_listed_as_next_option(art):
    options = art["next_task_options"]
    phrases = [o["phrase"] for o in options]
    assert any("YES execute P188" in p and "production DB migration" in p for p in phrases)

def test_p187_destructive_phrase_is_not_current_authorization(art):
    options = art["next_task_options"]
    destructive_opt = next((o for o in options if "YES execute P188" in o["phrase"]), None)
    assert destructive_opt is not None
    assert destructive_opt.get("is_current_authorization") is False

# ── Governance ────────────────────────────────────────────────────────────────
def test_p187_no_production_write(art):
    assert art["governance_confirmations"]["no_production_db_write"] is True

def test_p187_no_migration_executed(art):
    assert art["governance_confirmations"]["no_db_migration_executed"] is True

def test_p187_no_backup_created(art):
    assert art["governance_confirmations"]["no_backup_created"] is True

def test_p187_no_schema_change(art):
    assert art["governance_confirmations"]["no_schema_change"] is True

def test_p187_no_row_insert(art):
    assert art["governance_confirmations"]["no_row_insert"] is True

def test_p187_no_controlled_apply(art):
    assert art["governance_confirmations"]["no_controlled_apply"] is True

def test_p187_no_merge(art):  assert art["governance_confirmations"]["no_merge"] is True
def test_p187_no_stage(art):  assert art["governance_confirmations"]["no_stage"] is True
def test_p187_no_commit(art): assert art["governance_confirmations"]["no_commit"] is True
def test_p187_no_push(art):   assert art["governance_confirmations"]["no_push"] is True

def test_p187_power_lotto_closed(art):
    assert art["governance_confirmations"]["power_lotto_research_closed"] is True

def test_p187_split_unresolved(art):
    assert art["governance_confirmations"]["main_zen_gates_split_still_unresolved"] is True

# ── P188 options ──────────────────────────────────────────────────────────────
def test_p187_p188_options_present(art):
    assert len(art["next_task_options"]) >= 4

def test_p187_p188_blocked(art):
    assert art["next_task_blocked_by_user_authorization"] is True

# ── Roadmap docs ──────────────────────────────────────────────────────────────
def test_p187_active_task_done():
    assert "P187" in ACTIVE_TASK.read_text()

def test_p187_active_task_p188_blocked():
    content = ACTIVE_TASK.read_text()
    assert "P188" in content and "BLOCKED" in content

def test_p187_roadmap_includes_p187():
    assert "P187" in ROADMAP.read_text()

def test_p187_cto_includes_p187():
    assert "P187" in CTO_ANALYSIS.read_text()

# ── No wagering ───────────────────────────────────────────────────────────────
def test_p187_no_wagering():
    c = ART_MD.read_text().lower()
    assert "guaranteed win" not in c
    assert "betting advice" not in c
    assert "win is guaranteed" not in c
