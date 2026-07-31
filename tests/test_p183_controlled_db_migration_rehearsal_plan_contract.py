"""
Contract test for P183 — Controlled DB Migration Rehearsal Plan (Plan Only).

Verifies the rehearsal plan artifact is complete and all governance confirmations hold.
No DB migration was performed. No DB write. No rehearsal execution.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
ARTIFACT_JSON = REPO_ROOT / "outputs/research/power_lotto/p183_controlled_db_migration_rehearsal_plan_20260601.json"
ARTIFACT_MD = REPO_ROOT / "outputs/research/power_lotto/p183_controlled_db_migration_rehearsal_plan_20260601.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
ACTIVE_TASK = REPO_ROOT / "00-Plan" / "roadmap" / "active_task.md"
ROADMAP = REPO_ROOT / "00-Plan" / "roadmap" / "roadmap.md"
CTO_ANALYSIS = REPO_ROOT / "00-Plan" / "roadmap" / "CTO-Analysis.md"

MAIN_EXPECTED_ROWS = 54462
ZEN_GATES_EXPECTED_ROWS = 94924
ROW_DELTA = 40462


@pytest.fixture(scope="module")
def artifact() -> dict:
    assert ARTIFACT_JSON.exists(), f"P183 JSON artifact missing: {ARTIFACT_JSON}"
    return json.loads(ARTIFACT_JSON.read_text())


# ── Artifact existence ────────────────────────────────────────────────────────

def test_p183_json_artifact_exists():
    assert ARTIFACT_JSON.exists()


def test_p183_md_artifact_exists():
    assert ARTIFACT_MD.exists()


# ── Classification & authorization ───────────────────────────────────────────

def test_p183_final_classification(artifact):
    assert artifact["final_classification"] == "P183_CONTROLLED_DB_MIGRATION_REHEARSAL_PLAN_READY"


def test_p183_authorization_phrase(artifact):
    phrase = artifact["authorization_phrase_detected"]
    assert "YES start P183" in phrase
    assert "controlled DB migration rehearsal plan only" in phrase


# ── Phase 0 ───────────────────────────────────────────────────────────────────

def test_p183_phase0_status(artifact):
    assert artifact["phase_0_verification"]["status"] == "PASS"


def test_p183_phase0_branch(artifact):
    assert artifact["phase_0_verification"]["branch"] == "main"


def test_p183_phase0_not_worktree(artifact):
    assert artifact["phase_0_verification"]["is_worktree"] is False


# ── DB split summary ──────────────────────────────────────────────────────────

def test_p183_main_db_rows_before(artifact):
    assert artifact["phase_0_verification"]["main_db_rows_before"] == MAIN_EXPECTED_ROWS


def test_p183_main_db_rows_after(artifact):
    assert artifact["part_a_db_split_summary"]["main_db_rows"] == MAIN_EXPECTED_ROWS


def test_p183_main_bet_index_absent(artifact):
    assert artifact["part_a_db_split_summary"]["main_bet_index"] == "ABSENT"


def test_p183_zen_gates_db_rows(artifact):
    assert artifact["phase_0_verification"]["zen_gates_db_rows"] == ZEN_GATES_EXPECTED_ROWS


def test_p183_zen_gates_bet_index_present(artifact):
    assert artifact["phase_0_verification"]["zen_gates_bet_index"] == "PRESENT"


def test_p183_row_delta(artifact):
    split = artifact["part_a_db_split_summary"]
    assert split["row_delta"] == ROW_DELTA


# ── P182 referenced ───────────────────────────────────────────────────────────

def test_p183_p182_classification_referenced(artifact):
    assert artifact["phase_0_verification"]["p182_classification"] == "P182_CODE_DOCS_TESTS_PARITY_BACKPORT_READY"


# ── Governance: no DB write / migration / copy / rehearsal execution ──────────

def test_p183_no_db_write(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["db_write"] == 0


def test_p183_no_db_migration(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["db_migration_performed"] is False


def test_p183_no_db_copy(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["db_copy_performed"] is False


def test_p183_no_rehearsal_execution(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["rehearsal_execution_performed"] is False


def test_p183_no_row_insertion(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["row_insertion"] == 0


def test_p183_no_schema_change(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["schema_change"] is False


def test_p183_no_controlled_apply(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_controlled_apply"] is True


def test_p183_no_merge(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_merge"] is True


def test_p183_no_stage_commit_push(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_stage_commit_push"] is True


def test_p183_no_wagering(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_wagering_recommendation"] is True


def test_p183_no_win_guarantee(artifact):
    gov = artifact["governance_confirmations"]
    assert gov["no_win_guarantee"] is True


def test_p183_p178a_closure_active(artifact):
    gov = artifact["governance_confirmations"]
    assert "ACTIVE" in gov["p178a_closure_policy"]
    assert "CLOSED" in gov["p178a_closure_policy"]


def test_p183_split_unresolved(artifact):
    gov = artifact["governance_confirmations"]
    assert "UNRESOLVED" in gov["main_zen_gates_split"]


# ── Rehearsal plan has at least 11 steps ─────────────────────────────────────

def test_p183_rehearsal_plan_has_11_steps(artifact):
    steps = artifact["part_b_rehearsal_plan"]["steps"]
    assert len(steps) >= 11, f"Expected >= 11 steps, got {len(steps)}"


def test_p183_step1_preflight(artifact):
    steps = artifact["part_b_rehearsal_plan"]["steps"]
    assert "step_1_preflight_checks" in steps


def test_p183_step2_backup(artifact):
    steps = artifact["part_b_rehearsal_plan"]["steps"]
    assert "step_2_immutable_backup" in steps


def test_p183_step9_rollback(artifact):
    steps = artifact["part_b_rehearsal_plan"]["steps"]
    assert "step_9_rollback_plan" in steps


def test_p183_step10_acceptance(artifact):
    steps = artifact["part_b_rehearsal_plan"]["steps"]
    assert "step_10_post_rehearsal_acceptance" in steps


def test_p183_step11_production_auth_chain(artifact):
    steps = artifact["part_b_rehearsal_plan"]["steps"]
    assert "step_11_production_migration_authorization_chain" in steps


# ── Risk assessment ───────────────────────────────────────────────────────────

def test_p183_risk_schema_mismatch(artifact):
    risk = artifact["part_e_risk_assessment"]
    assert "schema_mismatch_risk" in risk
    assert risk["schema_mismatch_risk"]["level"] == "HIGH"


def test_p183_risk_row_count_drift(artifact):
    risk = artifact["part_e_risk_assessment"]
    assert "row_count_drift_risk" in risk


def test_p183_risk_duplicate_key(artifact):
    risk = artifact["part_e_risk_assessment"]
    assert "duplicate_key_risk" in risk


def test_p183_risk_rollback(artifact):
    risk = artifact["part_e_risk_assessment"]
    assert "backup_rollback_risk" in risk


# ── P184 authorization options ────────────────────────────────────────────────

def test_p183_p184_options_present(artifact):
    options = artifact["part_f_p184_authorization_options"]
    assert len(options) >= 4


def test_p183_p184_primary_option_rehearsal(artifact):
    options = artifact["part_f_p184_authorization_options"]
    phrases = [o["phrase"] for o in options]
    assert any("P184" in p and "rehearsal on temp copy only" in p for p in phrases)


def test_p183_p184_recommended_flag(artifact):
    options = artifact["part_f_p184_authorization_options"]
    recommended = [o for o in options if o.get("recommended") is True]
    assert len(recommended) == 1
    assert "temp copy" in recommended[0]["phrase"]


# ── Active task updated ───────────────────────────────────────────────────────

def test_p183_active_task_marks_p183_done():
    content = ACTIVE_TASK.read_text()
    assert "P183" in content


def test_p183_active_task_p184_blocked():
    content = ACTIVE_TASK.read_text()
    assert "P184" in content
    assert "BLOCKED" in content


# ── Roadmap and CTO updated ───────────────────────────────────────────────────

def test_p183_roadmap_includes_p183():
    content = ROADMAP.read_text()
    assert "P183" in content


def test_p183_cto_includes_p183():
    content = CTO_ANALYSIS.read_text()
    assert "P183" in content


# ── Main DB unchanged (live check) ───────────────────────────────────────────

def test_p183_main_db_rows_live_post_p188():  # post-P188: live DB = 94924
    assert DB_PATH.exists()
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays;").fetchone()[0]
    conn.close()
    assert n == 94924, f"Expected 94924 (post-P188 migrated), got {n}"


# ── No forbidden strings ──────────────────────────────────────────────────────

@pytest.mark.parametrize("term", [
    "guaranteed win",
    "betting advice",
    "win guarantee",
    "production migration authorized",
    "migration executed",
    "schema changed",
])
def test_p183_no_forbidden_strings_json(artifact, term):
    raw = json.dumps(artifact).lower()
    assert term.lower() not in raw, f"Forbidden term in JSON: {term}"


def test_p183_no_wagering_in_md():
    content = ARTIFACT_MD.read_text().lower()
    # Check for assertive guarantee claims — not governance table labels like "win guarantee | NONE"
    assert "guaranteed win" not in content
    assert "win is guaranteed" not in content
    assert "betting advice" not in content
    # "win guarantee" appears as a governance label (value=NONE) — check it's not asserted positively
    import re
    # Must not appear as a positive claim (e.g., "win guarantee: true" or "outcome guaranteed")
    assert not re.search(r"win guarantee.*true", content)
    assert not re.search(r"guaranteed.*outcome.*win", content)


# ── CTO recommendation present ────────────────────────────────────────────────

def test_p183_cto_recommendation_present(artifact):
    cto = artifact["part_g_cto_recommendation"]
    assert "primary" in cto
    assert "P184" in cto["primary"]
    assert "temp copy" in cto["primary"]
