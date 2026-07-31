"""
Contract test for P184 — Controlled DB Migration Rehearsal (Temp Copy Only).

Verifies schema rehearsal completed on temp copy, production DB unchanged.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs/research/power_lotto/p184_controlled_db_migration_rehearsal_temp_copy_20260601.json"
ARTIFACT_MD = REPO_ROOT / "outputs/research/power_lotto/p184_controlled_db_migration_rehearsal_temp_copy_20260601.md"
TEMP_DB = REPO_ROOT / "outputs/research/power_lotto/p184_rehearsal/lottery_v2_p184_temp_rehearsal_20260601.db"
PROD_DB = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
ACTIVE_TASK = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

PROD_EXPECTED_ROWS = 54462
TEMP_EXPECTED_ROWS = 54302
ZEN_GATES_EXPECTED_ROWS = 94924
ROW_DELTA = 40462


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert ARTIFACT_JSON.exists(), f"P184 JSON artifact missing: {ARTIFACT_JSON}"
    return json.loads(ARTIFACT_JSON.read_text())


# ── Artifact existence ────────────────────────────────────────────────────────

def test_p184_json_exists():
    assert ARTIFACT_JSON.exists()


def test_p184_md_exists():
    assert ARTIFACT_MD.exists()


# ── Classification & authorization ───────────────────────────────────────────

def test_p184_final_classification(artifact):
    assert artifact["final_classification"] == "P184_CONTROLLED_DB_MIGRATION_REHEARSAL_TEMP_COPY_READY"


def test_p184_authorization_phrase(artifact):
    phrase = artifact["authorization_phrase_detected"]
    assert "YES start P184" in phrase
    assert "controlled DB migration rehearsal on temp copy only" in phrase


# ── Phase 0 ───────────────────────────────────────────────────────────────────

def test_p184_phase0_status(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_p184_phase0_branch(artifact):
    assert artifact["phase_0_verification"]["branch"] == "main"


def test_p184_phase0_not_worktree(artifact):
    assert artifact["phase_0_verification"]["is_worktree"] is False


# ── P183 referenced ───────────────────────────────────────────────────────────

def test_p184_p183_classification_referenced(artifact):
    assert artifact["p183_classification_referenced"] == "P183_CONTROLLED_DB_MIGRATION_REHEARSAL_PLAN_READY"


# ── Production DB rows before/after ──────────────────────────────────────────

def test_p184_production_rows_before(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["production_main_db_rows_before"] == PROD_EXPECTED_ROWS


def test_p184_production_rows_after(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["production_main_db_rows_after"] == PROD_EXPECTED_ROWS


def test_p184_production_db_unchanged(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["production_main_db_unchanged"] is True


def test_p184_production_bet_index_absent(artifact):
    assert artifact["phase_0_verification"]["main_bet_index_before"] == "ABSENT"


# ── Temp DB exists ────────────────────────────────────────────────────────────

def test_p184_temp_db_exists():
    assert TEMP_DB.exists(), f"Temp DB missing at {TEMP_DB}"


def test_p184_temp_db_in_rehearsal_dir():
    assert "p184_rehearsal" in str(TEMP_DB)


# ── Temp DB rows after schema migration ──────────────────────────────────────

def test_p184_temp_db_rows_after_migration(artifact):
    assert artifact["temp_rehearsal_db"]["rows_after_schema_migration"] == TEMP_EXPECTED_ROWS


def test_p184_temp_db_live_row_count():
    assert TEMP_DB.exists()
    conn = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == TEMP_EXPECTED_ROWS


# ── Temp DB bet_index present ─────────────────────────────────────────────────

def test_p184_temp_db_bet_index_present(artifact):
    assert artifact["temp_rehearsal_db"]["bet_index_after_migration"] == "PRESENT"


def test_p184_temp_db_bet_index_live():
    assert TEMP_DB.exists()
    conn = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    conn.close()
    assert "bet_index" in cols


# ── Duplicate check passed ────────────────────────────────────────────────────

def test_p184_duplicate_check_passed(artifact):
    schema_result = artifact["schema_rehearsal_result"]
    assert schema_result["schema_after_migration"]["duplicate_check"] == 0


def test_p184_duplicate_check_live():
    assert TEMP_DB.exists()
    conn = sqlite3.connect(f"file:{TEMP_DB}?mode=ro", uri=True)
    dup = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT lottery_type, target_draw, strategy_id, bet_index, COUNT(*)
            FROM strategy_prediction_replays
            GROUP BY lottery_type, target_draw, strategy_id, bet_index
            HAVING COUNT(*) > 1
        )
    """).fetchone()[0]
    conn.close()
    assert dup == 0


# ── UNIQUE constraint semantics ───────────────────────────────────────────────

def test_p184_unique_target_semantics(artifact):
    constraint = artifact["temp_rehearsal_db"]["unique_constraint_after_migration"]
    assert "lottery_type" in constraint
    assert "target_draw" in constraint
    assert "strategy_id" in constraint
    assert "bet_index" in constraint


# ── Row delta audit ───────────────────────────────────────────────────────────

def test_p184_row_delta_present(artifact):
    audit = artifact["row_delta_audit"]
    assert audit["main_db_rows_original"] == PROD_EXPECTED_ROWS
    assert audit["zen_gates_total_rows"] == ZEN_GATES_EXPECTED_ROWS


def test_p184_post_dedup_matches_zen_gates_bet_index_1(artifact):
    validation = artifact["schema_rehearsal_result"]["critical_validation"]
    assert validation["post_dedup_matches_zen_gates_bet_index_1"] is True


def test_p184_all_lottery_types_exact_match(artifact):
    comp = artifact["schema_rehearsal_result"]["critical_validation"]["comparison"]
    for lt in ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]:
        assert comp[lt]["match"] is True


# ── Governance confirmations ──────────────────────────────────────────────────

def test_p184_no_production_db_write(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_production_db_write"] is True


def test_p184_no_db_copy_to_production(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_db_copy_to_production"] is True


def test_p184_no_controlled_apply(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_controlled_apply"] is True


def test_p184_no_registry_mutation(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_registry_mutation"] is True


def test_p184_no_merge(artifact):
    assert artifact["governance_confirmations"]["no_merge"] is True


def test_p184_no_stage(artifact):
    assert artifact["governance_confirmations"]["no_stage"] is True


def test_p184_no_commit(artifact):
    assert artifact["governance_confirmations"]["no_commit"] is True


def test_p184_no_push(artifact):
    assert artifact["governance_confirmations"]["no_push"] is True


def test_p184_power_lotto_research_closed(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["power_lotto_research_closed"] is True


def test_p184_split_unresolved(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["main_zen_gates_split_still_unresolved"] is True


# ── P185 options ──────────────────────────────────────────────────────────────

def test_p184_p185_options_present(artifact):
    options = artifact["next_task_options"]
    assert len(options) >= 4


def test_p184_p185_row_delta_rehearsal_option(artifact):
    phrases = [o["phrase"] for o in artifact["next_task_options"]]
    assert any("P185" in p and "row delta import rehearsal" in p for p in phrases)


def test_p184_p185_blocked(artifact):
    assert artifact["next_task_blocked_by_user_authorization"] is True


# ── Roadmap docs updated ──────────────────────────────────────────────────────

def test_p184_active_task_marks_p184_done():
    content = ACTIVE_TASK.read_text()
    assert "P184" in content


def test_p184_active_task_p185_blocked():
    content = ACTIVE_TASK.read_text()
    assert "P185" in content
    assert "BLOCKED" in content


def test_p184_roadmap_includes_p184():
    content = ROADMAP.read_text()
    assert "P184" in content


def test_p184_cto_includes_p184():
    content = CTO_ANALYSIS.read_text()
    assert "P184" in content


# ── Temp DB in allowed path (not production) ──────────────────────────────────

def test_p184_temp_db_not_in_production_path():
    assert "lottery_api" not in str(TEMP_DB)
    assert "outputs/research" in str(TEMP_DB)


# ── Production DB unchanged (live check) ─────────────────────────────────────

def test_p184_production_db_rows_live():
    assert PROD_DB.exists()
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == 94924, f"Expected 94924 (post-P188 migrated), got {n}"


def test_p184_production_db_bet_index_now_present():  # post-P188: bet_index PRESENT
    assert PROD_DB.exists()
    conn = sqlite3.connect(f"file:{PROD_DB}?mode=ro", uri=True)
    cols = [row[1] for row in conn.execute("PRAGMA table_info(strategy_prediction_replays);").fetchall()]
    conn.close()
    assert "bet_index" in cols, "bet_index must be PRESENT after P188 migration"


# ── No wagering / win guarantee ───────────────────────────────────────────────

def test_p184_no_wagering_in_md():
    content = ARTIFACT_MD.read_text().lower()
    assert "guaranteed win" not in content
    assert "betting advice" not in content
    assert "win is guaranteed" not in content


def test_p184_schema_migration_status(artifact):
    assert artifact["schema_rehearsal_result"]["status"] == "PASS"
