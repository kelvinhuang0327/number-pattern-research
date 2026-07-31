"""
Contract test for P185 — Row Delta Import Rehearsal (Temp Copy Only).
Verifies full migration path (dedup + schema + import) on temp DB; production DB untouched.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT   = Path(__file__).parent.parent
ART_JSON    = REPO_ROOT / "outputs/research/power_lotto/p185_row_delta_import_rehearsal_temp_copy_20260601.json"
ART_MD      = REPO_ROOT / "outputs/research/power_lotto/p185_row_delta_import_rehearsal_temp_copy_20260601.md"
TEMP_DB     = REPO_ROOT / "outputs/research/power_lotto/p185_rehearsal/lottery_v2_p185_temp_rehearsal_20260601.db"
PROD_DB     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
ACTIVE_TASK = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP     = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS= REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

PROD_ROWS   = 54462
BASE_ROWS   = 54302
IMPORT_ROWS = 40622
FINAL_ROWS  = 94924


@pytest.fixture(scope="module")
def art() -> dict:
    assert ART_JSON.exists()
    return json.loads(ART_JSON.read_text())


# ── Artifacts exist ───────────────────────────────────────────────────────────
def test_p185_json_exists(): assert ART_JSON.exists()
def test_p185_md_exists():   assert ART_MD.exists()

# ── Classification ────────────────────────────────────────────────────────────
def test_p185_final_classification(art):
    assert art["final_classification"] == "P185_ROW_DELTA_IMPORT_REHEARSAL_TEMP_COPY_READY"

def test_p185_authorization_phrase(art):
    phrase = art["authorization_phrase_detected"]
    assert "YES start P185" in phrase
    assert "row delta import rehearsal on temp copy only" in phrase

# ── Phase 0 ───────────────────────────────────────────────────────────────────
def test_p185_phase0_pass(art):
    assert art["phase_0_verification"]["status"] == "PASS"

def test_p185_phase0_branch(art):
    assert art["phase_0_verification"]["branch"] == "main"

# ── P184 referenced ───────────────────────────────────────────────────────────
def test_p185_p184_referenced(art):
    assert art["p184_classification_referenced"] == "P184_CONTROLLED_DB_MIGRATION_REHEARSAL_TEMP_COPY_READY"

# ── Production DB rows before/after ──────────────────────────────────────────
def test_p185_prod_rows_before(art):
    assert art["governance_confirmations"]["production_main_db_rows_before"] == PROD_ROWS

def test_p185_prod_rows_after(art):
    assert art["governance_confirmations"]["production_main_db_rows_after"] == PROD_ROWS

def test_p185_prod_db_unchanged(art):
    assert art["governance_confirmations"]["production_main_db_unchanged"] is True

def test_p185_prod_bet_index_absent(art):
    assert art["governance_confirmations"]["production_main_bet_index_before"] == "ABSENT"
    assert art["governance_confirmations"]["production_main_bet_index_after"] == "ABSENT"

# ── Production DB live check ──────────────────────────────────────────────────
def test_p185_prod_rows_live():
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == 94924, f"Expected 94924 (post-P188 migrated), got {n}"

def test_p185_prod_bet_index_now_present():  # renamed: post-P188 bet_index PRESENT
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    conn.close()
    assert "bet_index" in cols, "bet_index must be PRESENT after P188 migration"

# ── Temp DB ───────────────────────────────────────────────────────────────────
def test_p185_temp_db_exists():
    assert TEMP_DB.exists(), f"Temp DB missing: {TEMP_DB}"

def test_p185_temp_db_in_p185_rehearsal_dir():
    assert "p185_rehearsal" in str(TEMP_DB)

def test_p185_temp_db_not_in_production_path():
    assert "lottery_api" not in str(TEMP_DB)

# ── Duplicate groups ──────────────────────────────────────────────────────────
def test_p185_duplicate_groups(art):
    assert art["duplicate_dedup_result"]["duplicate_groups"] == 120

def test_p185_duplicate_rows(art):
    assert art["duplicate_dedup_result"]["rows_in_dup_groups"] == 280

def test_p185_dropped_rows(art):
    assert art["duplicate_dedup_result"]["dropped_rows"] == 160

# ── Dedup base rows ───────────────────────────────────────────────────────────
def test_p185_base_dedup_rows(art):
    assert art["duplicate_dedup_result"]["base_rows_after_dedup"] == BASE_ROWS

def test_p185_post_dedup_matches_zen_b1(art):
    assert art["duplicate_dedup_result"]["post_dedup_matches_zen_gates_bet_index_1"] is True

def test_p185_per_lottery_base_match(art):
    for lt in ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]:
        assert art["duplicate_dedup_result"]["per_lottery_type_base_match"][lt]["match"] is True

# ── Row import ────────────────────────────────────────────────────────────────
def test_p185_imported_rows(art):
    assert art["row_delta_import_result"]["imported_rows"] == IMPORT_ROWS

def test_p185_final_temp_rows(art):
    assert art["row_delta_import_result"]["final_temp_rows"] == FINAL_ROWS

# ── Temp DB live checks ───────────────────────────────────────────────────────
def test_p185_temp_final_rows_live():
    conn = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == FINAL_ROWS

def test_p185_temp_bet_index_present_live():
    conn = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    conn.close()
    assert "bet_index" in cols

def test_p185_temp_duplicate_check_live():
    conn = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    dup = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT lottery_type,target_draw,strategy_id,bet_index,COUNT(*)
            FROM strategy_prediction_replays
            GROUP BY lottery_type,target_draw,strategy_id,bet_index
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    conn.close()
    assert dup == 0

def test_p185_temp_per_lottery_live():
    conn = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    expected = {"BIG_LOTTO": 24140, "DAILY_539": 34680, "POWER_LOTTO": 36104}
    for lt, exp in expected.items():
        n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type=?", (lt,)).fetchone()[0]
        assert n == exp, f"{lt}: expected {exp}, got {n}"
    conn.close()

def test_p185_temp_bet_index_distribution_live():
    conn = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    expected = {1: 54302, 2: 16581, 3: 15041, 4: 6000, 5: 3000}
    for bi, exp in expected.items():
        n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index=?", (bi,)).fetchone()[0]
        assert n == exp, f"bet_index={bi}: expected {exp}, got {n}"
    conn.close()

# ── Aggregate comparison ──────────────────────────────────────────────────────
def test_p185_aggregate_comparison_pass(art):
    assert art["aggregate_comparison_result"]["status"] == "PASS"

def test_p185_bet_index_distribution_match(art):
    dist = art["aggregate_comparison_result"]["bet_index_distribution"]
    for bi in ["1","2","3","4","5"]:
        assert dist[bi]["match"] is True

# ── Unique target semantics ───────────────────────────────────────────────────
def test_p185_unique_target_semantics(art):
    c = art["temp_rehearsal_db"]["unique_constraint_after_migration"]
    for field in ["lottery_type","target_draw","strategy_id","bet_index"]:
        assert field in c

# ── Duplicate check final ────────────────────────────────────────────────────
def test_p185_duplicate_check_final(art):
    assert art["aggregate_comparison_result"]["duplicate_check_final"] == 0

# ── Governance ────────────────────────────────────────────────────────────────
def test_p185_no_production_write(art): assert art["governance_confirmations"]["no_production_db_write"] is True
def test_p185_no_copy_to_production(art): assert art["governance_confirmations"]["no_db_copy_to_production"] is True
def test_p185_no_controlled_apply(art): assert art["governance_confirmations"]["no_controlled_apply"] is True
def test_p185_no_registry_mutation(art): assert art["governance_confirmations"]["no_registry_mutation"] is True
def test_p185_no_merge(art): assert art["governance_confirmations"]["no_merge"] is True
def test_p185_no_stage(art): assert art["governance_confirmations"]["no_stage"] is True
def test_p185_no_commit(art): assert art["governance_confirmations"]["no_commit"] is True
def test_p185_no_push(art): assert art["governance_confirmations"]["no_push"] is True
def test_p185_power_lotto_closed(art): assert art["governance_confirmations"]["power_lotto_research_closed"] is True
def test_p185_split_unresolved(art): assert art["governance_confirmations"]["main_zen_gates_split_still_unresolved"] is True

# ── P186 options ──────────────────────────────────────────────────────────────
def test_p185_p186_options_present(art):
    assert len(art["next_task_options"]) >= 4

def test_p185_p186_auth_gate_option(art):
    phrases = [o["phrase"] for o in art["next_task_options"]]
    assert any("P186" in p and "production DB migration authorization gate" in p for p in phrases)

def test_p185_p186_blocked(art):
    assert art["next_task_blocked_by_user_authorization"] is True

# ── Roadmap docs ──────────────────────────────────────────────────────────────
def test_p185_active_task_p185_done():
    assert "P185" in ACTIVE_TASK.read_text()

def test_p185_active_task_p186_blocked():
    content = ACTIVE_TASK.read_text()
    assert "P186" in content and "BLOCKED" in content

def test_p185_roadmap_includes_p185():
    assert "P185" in ROADMAP.read_text()

def test_p185_cto_includes_p185():
    assert "P185" in CTO_ANALYSIS.read_text()

# ── No wagering ───────────────────────────────────────────────────────────────
def test_p185_no_wagering_in_md():
    content = ART_MD.read_text().lower()
    assert "guaranteed win" not in content
    assert "betting advice" not in content
    assert "win is guaranteed" not in content

def test_p185_schema_migration_result(art):
    assert art["acceptance_criteria_result"]["no_production_db_write"] is True
    assert art["acceptance_criteria_result"]["temp_db_final_rows"] == FINAL_ROWS
