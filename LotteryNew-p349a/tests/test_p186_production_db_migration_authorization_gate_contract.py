"""
Contract test for P186 — Production DB Migration Authorization Gate (Plan Only).
Verifies the gate artifact is complete and all 12 conditions are documented.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).parent.parent
ART_JSON    = REPO_ROOT / "outputs/research/power_lotto/p186_production_db_migration_authorization_gate_20260601.json"
ART_MD      = REPO_ROOT / "outputs/research/power_lotto/p186_production_db_migration_authorization_gate_20260601.md"
ACTIVE_TASK = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP     = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS= REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"
PROD_DB     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

PROD_ROWS   = 54462
DEDUP_ROWS  = 54302
DROPPED     = 160
IMPORT_ROWS = 40622
FINAL_ROWS  = 94924

EXACT_AUTH_PHRASE = (
    "YES execute P187 production DB migration from main 54462 to reconciled 94924 "
    "using P185 rehearsal SQL, approve MAX(id) dedup dropping 160 null-provenance "
    "duplicate rows, create timestamped backup, no controlled_apply"
)


@pytest.fixture(scope="module")
def art() -> dict:
    assert ART_JSON.exists()
    return json.loads(ART_JSON.read_text())


# ── Artifacts exist ───────────────────────────────────────────────────────────
def test_p186_json_exists(): assert ART_JSON.exists()
def test_p186_md_exists():   assert ART_MD.exists()

# ── Classification ────────────────────────────────────────────────────────────
def test_p186_final_classification(art):
    assert art["final_classification"] == "P186_PRODUCTION_DB_MIGRATION_AUTHORIZATION_GATE_READY"

def test_p186_authorization_phrase(art):
    phrase = art["authorization_phrase_detected"]
    assert "YES start P186" in phrase
    assert "production DB migration authorization gate only" in phrase

# ── Phase 0 ───────────────────────────────────────────────────────────────────
def test_p186_phase0_pass(art):
    assert art["phase_0_verification"]["status"] == "PASS"

def test_p186_phase0_branch(art):
    assert art["phase_0_verification"]["branch"] == "main"

# ── P185 referenced ───────────────────────────────────────────────────────────
def test_p186_p185_referenced(art):
    assert art["p185_classification_referenced"] == "P185_ROW_DELTA_IMPORT_REHEARSAL_TEMP_COPY_READY"

# ── P185 rehearsal summary ────────────────────────────────────────────────────
def test_p186_p185_summary_prod_unchanged(art):
    s = art["p185_rehearsal_summary"]
    assert s["production_main_db_rows_unchanged"] == PROD_ROWS

def test_p186_p185_summary_dedup_dropped(art):
    assert art["p185_rehearsal_summary"]["dedup_dropped_rows"] == DROPPED

def test_p186_p185_summary_imported(art):
    assert art["p185_rehearsal_summary"]["imported_rows"] == IMPORT_ROWS

def test_p186_p185_summary_temp_final(art):
    assert art["p185_rehearsal_summary"]["temp_final_rows"] == FINAL_ROWS

# ── Gate conditions ───────────────────────────────────────────────────────────
def test_p186_gate_has_12_conditions(art):
    gate = art["production_migration_gate"]["conditions"]
    assert len(gate) >= 12

def test_p186_gate_g1_dedup_approval(art):
    assert "G1_approve_dedup_policy" in art["production_migration_gate"]["conditions"]

def test_p186_gate_g6_timestamped_backup(art):
    g6 = art["production_migration_gate"]["conditions"]["G6_approve_backup"]
    assert "timestamped" in g6["description"].lower() or "backup" in g6["description"].lower()
    assert g6["required"] is True

def test_p186_gate_g7_production_lock(art):
    g7 = art["production_migration_gate"]["conditions"]["G7_approve_production_lock"]
    assert g7["required"] is True

def test_p186_gate_g8_exact_sql(art):
    g8 = art["production_migration_gate"]["conditions"]["G8_approve_exact_sql"]
    assert "p185" in g8["sql_log_path"].lower()
    assert g8["required"] is True

def test_p186_all_conditions_required(art):
    gate = art["production_migration_gate"]
    assert gate["all_conditions_must_be_met"] is True

# ── Exact P187 authorization phrase ──────────────────────────────────────────
def test_p186_exact_authorization_phrase_present(art):
    phrase = art["exact_authorization_phrase"]["phrase"]
    assert "YES execute P187" in phrase
    assert "54462" in phrase
    assert "94924" in phrase
    assert "P185 rehearsal SQL" in phrase
    assert "MAX(id) dedup" in phrase
    assert "160" in phrase
    assert "null-provenance" in phrase
    assert "timestamped backup" in phrase
    assert "no controlled_apply" in phrase

def test_p186_exact_phrase_required_verbatim(art):
    assert art["exact_authorization_phrase"]["required_verbatim"] is True

def test_p186_exact_phrase_in_md():
    content = ART_MD.read_text()
    assert "YES execute P187" in content
    assert "54462" in content
    assert "94924" in content
    assert "P185 rehearsal SQL" in content

# ── Governance ────────────────────────────────────────────────────────────────
def test_p186_prod_rows_before(art):
    assert art["governance_confirmations"]["production_main_db_rows_before"] == PROD_ROWS

def test_p186_prod_rows_after(art):
    assert art["governance_confirmations"]["production_main_db_rows_after"] == PROD_ROWS

def test_p186_prod_db_unchanged(art):
    assert art["governance_confirmations"]["production_main_db_unchanged"] is True

def test_p186_no_production_write(art):
    assert art["governance_confirmations"]["no_production_db_write"] is True

def test_p186_no_migration_executed(art):
    assert art["governance_confirmations"]["no_db_migration_executed"] is True

def test_p186_no_controlled_apply(art):
    assert art["governance_confirmations"]["no_controlled_apply"] is True

def test_p186_no_registry_mutation(art):
    assert art["governance_confirmations"]["no_registry_mutation"] is True

def test_p186_no_merge(art):  assert art["governance_confirmations"]["no_merge"] is True
def test_p186_no_stage(art):  assert art["governance_confirmations"]["no_stage"] is True
def test_p186_no_commit(art): assert art["governance_confirmations"]["no_commit"] is True
def test_p186_no_push(art):   assert art["governance_confirmations"]["no_push"] is True

def test_p186_power_lotto_closed(art):
    assert art["governance_confirmations"]["power_lotto_research_closed"] is True

def test_p186_split_unresolved(art):
    assert art["governance_confirmations"]["main_zen_gates_split_still_unresolved"] is True

# ── P187 options ──────────────────────────────────────────────────────────────
def test_p186_p187_options_present(art):
    assert len(art["next_task_options"]) >= 4

def test_p186_p187_production_migration_option(art):
    phrases = [o["phrase"] for o in art["next_task_options"]]
    assert any("YES execute P187" in p and "production DB migration" in p for p in phrases)

def test_p186_p187_blocked(art):
    assert art["next_task_blocked_by_user_authorization"] is True

# ── Production DB live check ──────────────────────────────────────────────────
def test_p186_prod_db_rows_live():
    import sqlite3
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == 94924, f"Expected 94924 (post-P188 migrated), got {n}"

def test_p186_prod_bet_index_now_present():  # renamed: post-P188 bet_index PRESENT
    import sqlite3
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    conn.close()
    assert "bet_index" in cols, "bet_index must be PRESENT after P188 migration"

# ── Roadmap docs ──────────────────────────────────────────────────────────────
def test_p186_active_task_p186_done():
    assert "P186" in ACTIVE_TASK.read_text()

def test_p186_active_task_p187_blocked():
    content = ACTIVE_TASK.read_text()
    assert "P187" in content and "BLOCKED" in content

def test_p186_roadmap_includes_p186():
    assert "P186" in ROADMAP.read_text()

def test_p186_cto_includes_p186():
    assert "P186" in CTO_ANALYSIS.read_text()

# ── No wagering / win guarantee ───────────────────────────────────────────────
def test_p186_no_wagering_in_md():
    content = ART_MD.read_text().lower()
    assert "guaranteed win" not in content
    assert "betting advice" not in content
    assert "win is guaranteed" not in content
