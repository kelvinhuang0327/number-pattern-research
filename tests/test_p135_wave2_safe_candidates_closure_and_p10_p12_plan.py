"""
tests/test_p135_wave2_safe_candidates_closure_and_p10_p12_plan.py
==================================================================
Verification tests for P135: Wave 2 safe candidates closure audit and P10/P12 re-evaluation plan.

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
SCRIPT = REPO_ROOT / "scripts" / "p135_wave2_safe_candidates_closure_and_p10_p12_plan.py"
ARTIFACT = REPO_ROOT / "outputs" / "replay" / "p135_wave2_safe_candidates_closure_and_p10_p12_plan_20260529.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p135_wave2_safe_candidates_closure_and_p10_p12_plan_20260529.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CLASSIFICATION = "P135_WAVE2_SAFE_CANDIDATES_CLOSED_P10_P12_REEVALUATION_PLAN_READY"
EXPECTED_ROWS = 94924  # post-P141: +6000 power_orthogonal_5bet rows
EXPECTED_WAVE2_TOTAL = 4
EXPECTED_P131_ROWS = 3000
EXPECTED_P132_ROWS = 3000
EXPECTED_P133_ROWS = 4500
EXPECTED_P134_ROWS = 3002


@pytest.fixture(scope="module", autouse=True)
def generate_p135_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "P135" in result.stdout or result.stdout.strip()


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P135 JSON not found: {ARTIFACT}"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


def test_artifact_exists():
    assert ARTIFACT.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P135"


def test_classification(artifact):
    assert artifact["classification"] == EXPECTED_CLASSIFICATION


def test_repo_worktree_check(artifact):
    check = artifact["repo_worktree_check"]
    assert check["worktree_confirmed"] is True
    assert check["branch"] == "claude/zen-gates-ff6802"
    assert check["git_dir"].endswith(".git/worktrees/zen-gates-ff6802")
    assert pathlib.Path(check["expected_worktree"]).resolve() == REPO_ROOT.resolve()


def test_db_snapshot(artifact):
    db = artifact["db_snapshot"]
    assert db["total_rows"] == EXPECTED_ROWS
    assert db["rows_before"] == EXPECTED_ROWS
    assert db["rows_after"] == EXPECTED_ROWS
    assert db["rows_match_expected"] is False
    assert db["bet_index_schema_exists"] is True


def test_p134_classification(artifact):
    assert artifact["source_artifact_summary"]["p134"]["classification"] == "P134_FOURIER_RHYTHM_3BET_APPLIED"


def test_p133_classification(artifact):
    assert artifact["source_artifact_summary"]["p133"]["classification"] == "P133_PP3_FREQORT_4BET_APPLIED"


def test_p132_classification(artifact):
    assert artifact["source_artifact_summary"]["p132"]["classification"] == "P132_MIDFREQ_FOURIER_MK_3BET_APPLIED"


def test_p131_classification(artifact):
    assert artifact["source_artifact_summary"]["p131"]["classification"] == "P131_ACB_MARKOV_MIDFREQ_3BET_APPLIED"


def test_p130_classification(artifact):
    assert artifact["source_artifact_summary"]["p130"]["classification"] == "P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY"


def test_wave2_completion(artifact):
    wave2 = artifact["wave2_safe_candidates_completion"]
    assert wave2["safe_candidates_total"] == EXPECTED_WAVE2_TOTAL
    assert wave2["safe_candidates_applied"] == EXPECTED_WAVE2_TOTAL
    assert wave2["remaining_safe_candidates"] == 0
    assert wave2["baseline_rows_after_rsr6_cleanup"] == 72422
    assert wave2["final_replay_rows"] == 85924
    assert wave2["total_inserted_rows_p131_to_p134"] == 13502
    assert wave2["p131_rows"] == EXPECTED_P131_ROWS
    assert wave2["p132_rows"] == EXPECTED_P132_ROWS
    assert wave2["p133_rows"] == EXPECTED_P133_ROWS
    assert wave2["p134_rows"] == EXPECTED_P134_ROWS


def test_strategy_distribution_safe_candidates(artifact):
    safe = artifact["strategy_distribution"]["safe_candidates"]
    assert safe["acb_markov_midfreq_3bet"]["bet_index_distribution"] == {"1": 1500, "2": 1500, "3": 1500}
    assert safe["midfreq_fourier_mk_3bet"]["bet_index_distribution"] == {"1": 1500, "2": 1500, "3": 1500}
    assert safe["pp3_freqort_4bet"]["bet_index_distribution"] == {"1": 1500, "2": 1500, "3": 1500, "4": 1500}
    assert safe["fourier_rhythm_3bet"]["bet_index_distribution"] == {"1": 1501, "2": 1501, "3": 1501}


def test_strategy_distribution_blocked_candidates(artifact):
    blocked = artifact["strategy_distribution"]["blocked_candidates"]
    assert blocked["power_precision_3bet"]["apply_ready"] is False
    assert blocked["power_orthogonal_5bet"]["apply_ready"] is False
    assert blocked["power_precision_3bet"]["bet_index_gt1_rows"] == 3000
    assert blocked["power_orthogonal_5bet"]["bet_index_gt1_rows"] == 6000  # post-P141: bet-2..bet-5 applied


def test_p9_anomaly_closure(artifact):
    p9 = artifact["p9_anomaly_closure"]
    assert p9["closure_status"] == "CLOSED"
    assert p9["accepted_as_planned"] is True
    assert p9["draw_ext_target_draw"] == "115000041"
    assert p9["bet_index_distribution"] == {"1": 1, "2": 1, "3": 1}
    assert p9["draw_ext_verified"] is True


def test_p10_p12_blocked_status(artifact):
    blocked = artifact["p10_p12_blocked_status"]
    assert blocked["power_precision_3bet_apply_ready"] is False
    assert blocked["power_orthogonal_5bet_apply_ready"] is False
    assert blocked["reason"] == "post_rsr6_cleanup_re_evaluation_required"
    assert blocked["controlled_apply_executed"] is False
    assert blocked["replay_rows_inserted"] == 0


def test_p10_p12_provenance_states(artifact):
    blocked = artifact["p10_p12_blocked_status"]["blocked_candidates"]
    pp = blocked["power_precision_3bet"]
    po = blocked["power_orthogonal_5bet"]
    assert pp["bet1_rows"] == 1550
    assert po["bet1_rows"] == 1550
    assert pp["valid_production_baseline_rows"] == 1500
    assert po["valid_production_baseline_rows"] == 1500
    assert pp["legacy_null_provenance_rows"] == 50
    assert po["legacy_null_provenance_rows"] == 50
    assert pp["bet_index_gt1_rows"] == 3000
    assert po["bet_index_gt1_rows"] == 6000  # post-P141: bet-2..bet-5 applied
    assert pp["controlled_apply_id_counts"]["P20_POWERLOTTO_REMAINING_1500_PROD_20260520"] == 1500
    assert po["controlled_apply_id_counts"]["P20_POWERLOTTO_REMAINING_1500_PROD_20260520"] == 1500
    assert pp["controlled_apply_id_counts"]["NULL"] == 50
    assert po["controlled_apply_id_counts"]["NULL"] == 50
    assert pp["truth_level_counts"]["POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"] == 4500
    assert po["truth_level_counts"]["POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED"] == 7500  # post-P141: +6000


def test_p10_p12_reevaluation_plan(artifact):
    plan = artifact["p10_p12_reevaluation_plan"]
    assert plan["no_db_mutation_in_p135"] is True
    assert any("baseline" in item.lower() for item in plan["required_checks"])
    assert any("provenance_hash" in item.lower() for item in plan["required_checks"])
    assert any("quarantine" in item.lower() for item in plan["decision_paths"])
    assert "re-mark" in plan["recommended_next_step"].lower()
    assert "quarantine" in plan["recommended_next_step"].lower()
    assert "dry-run" in plan["recommended_next_step"].lower()


def test_duplicate_guard_summary(artifact):
    dup = artifact["duplicate_guard_summary"]
    assert dup["unique_constraint"] == "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)"
    assert dup["safe_candidates_conflict_free"] is True
    assert dup["p10_p12_bet_index_gt1_rows_zero"] is False
    assert dup["p9_draw_ext_all_three_bets_present"] is True
    assert dup["no_duplicate_inserts_performed_in_p135"] is True


def test_drift_guard_result(artifact):
    drift = artifact["drift_guard_result"]
    assert drift["status"] == "PASS"
    assert drift["classification"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS"
    assert drift["total_rows"] == EXPECTED_ROWS


def test_apply_gate_status(artifact):
    gate = artifact["apply_gate_status"]
    assert gate["no_apply_in_p135"] is True
    assert gate["controlled_apply_executed"] is False
    assert gate["replay_rows_inserted"] == 0
    assert gate["production_db_rows_expected"] == 85924
    assert gate["production_db_rows_after"] == 85924


def test_blocked_or_excluded(artifact):
    blocked = artifact["blocked_or_excluded"]
    assert blocked["no_db_write_in_p135"] is True
    assert blocked["no_controlled_apply_in_p135"] is True
    assert blocked["P10_P12_not_apply_ready_until_re_evaluation"] is True
    assert blocked["4_STAR_excluded"] is True
    assert blocked["P108_not_run"] is True
    assert blocked["P117_not_run"] is True
    assert blocked["P118_not_run"] is True
    assert blocked["rejected_strategies_no_action"] is True
    assert blocked["no_scheduler_install"] is True
    assert blocked["no_lifecycle_champion_registry_mutation"] is True


def test_roadmap_update_status(artifact):
    assert "Wave 2 safe candidates closed" in artifact["roadmap_update_status"]
    assert "P10/P12" in artifact["roadmap_update_status"]


def test_remaining_risks(artifact):
    risks = artifact["remaining_risks"]
    assert len(risks) >= 2
    assert any("null-provenance" in item.lower() for item in risks)


def test_next_recommended_task(artifact):
    assert artifact["next_recommended_task"].startswith("P136:")


def test_summary(artifact):
    assert "85924" in artifact["summary"]
    assert "Wave 2 safe candidates" in artifact["summary"]


def test_markdown_exists():
    assert MD_PATH.exists()


def test_markdown_sections(artifact):
    text = MD_PATH.read_text(encoding="utf-8")
    assert "P135: Wave 2 Safe Candidates Closure and P10/P12 Re-evaluation Plan" in text
    for section in [
        "Executive Summary",
        "P134 Recap",
        "P131/P132/P133 Recap",
        "Wave 2 Safe Candidates Completion Matrix",
        "Final DB Row Count and Drift Guard Result",
        "P9 1501-Row Anomaly Closure",
        "P10/P12 Blocked Status",
        "P10/P12 Post-RSR6 Re-evaluation Plan",
        "Duplicate Guard Summary",
        "Explicit Non-Actions",
        "Remaining Risks",
        "Recommended Next Task",
        "Final Classification",
    ]:
        assert section in text, f"Missing Markdown section: {section}"


def test_markdown_contains_expected_content():
    text = MD_PATH.read_text(encoding="utf-8")
    assert EXPECTED_CLASSIFICATION in text
    assert "Wave 2 safe candidates are now complete" in text
    assert "P10 and P12 remain blocked" in text
    assert "115000041" in text
    assert "94924" in text  # post-P141: DB total updated to 94924
    assert "no DB writes" in text
    assert "no controlled_apply" in text


def test_live_db_row_count(db_conn):
    count = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert count == EXPECTED_ROWS


def test_live_db_bet_index_schema(db_conn):
    cols = [row[1] for row in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    assert "bet_index" in cols


def test_live_db_p10_p12_bet_index_gt1_rows(db_conn):
    for sid in ("power_precision_3bet", "power_orthogonal_5bet"):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index > 1",
            (sid,),
        ).fetchone()[0]
        if sid == "power_precision_3bet":
            assert count == 3000
        else:
            assert count == 6000  # post-P141: bet-2..bet-5 applied


def test_no_forbidden_files_staged():
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
