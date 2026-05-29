"""
tests/test_p136_post_rsr6_p10_p12_baseline_reevaluation.py
===========================================================
Verification tests for P136 post-RSR6 P10/P12 baseline re-evaluation.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "p136_post_rsr6_p10_p12_baseline_reevaluation.py"
ARTIFACT = REPO_ROOT / "outputs" / "replay" / "p136_post_rsr6_p10_p12_baseline_reevaluation_20260529.json"
MD_PATH = REPO_ROOT / "docs" / "replay" / "p136_post_rsr6_p10_p12_baseline_reevaluation_20260529.md"
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

EXPECTED_CLASSIFICATION = "P136_POST_RSR6_P10_P12_REEVALUATION_READY"
EXPECTED_ROWS = 85924


@pytest.fixture(scope="module", autouse=True)
def generate_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "P136" in result.stdout or result.stdout.strip()


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT.exists(), f"P136 JSON not found: {ARTIFACT}"
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"DB not found: {DB_PATH}"
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


def test_artifact_exists():
    assert ARTIFACT.exists()


def test_task_id_and_classification(artifact):
    assert artifact["task_id"] == "P136"
    assert artifact["classification"] == EXPECTED_CLASSIFICATION


def test_db_snapshot(artifact):
    db = artifact["db_snapshot"]
    assert db["total_rows"] == EXPECTED_ROWS
    assert db["rows_match_expected"] is True
    assert db["bet_index_schema_exists"] is True


def test_p135_source_validation(artifact):
    src = artifact["p135_source_summary"]
    assert src["classification"] == "P135_WAVE2_SAFE_CANDIDATES_CLOSED_P10_P12_REEVALUATION_PLAN_READY"
    assert src["classification_pass"] is True
    assert src["commit"] == "25c8d2b71ca958bd17cf52d0b6c516739745812e"


def test_rsr6_source_validation(artifact):
    src = artifact["rsr6_cleanup_source_summary"]
    assert src["classification"] == "RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED"
    assert src["classification_pass"] is True
    assert src["deleted_rows"] == 40


def test_distribution(artifact):
    d = artifact["p10_p12_current_distribution"]
    assert d["power_precision_3bet_bet1_rows"] == 1550
    assert d["power_precision_3bet_bet2_plus_rows"] == 0
    assert d["power_orthogonal_5bet_bet1_rows"] == 1550
    assert d["power_orthogonal_5bet_bet2_plus_rows"] == 0


def test_baseline_row_audit(artifact):
    b = artifact["baseline_row_audit"]
    assert b["production_baseline_rows_per_strategy"] == 1500
    assert b["null_provenance_legacy_rows_per_strategy"] == 50
    assert b["total_rows_per_strategy"] == 1550
    assert b["db_write_in_p136"] is False


def test_null_provenance_legacy_audit(artifact):
    a = artifact["null_provenance_legacy_audit"]
    pp = a["power_precision_3bet"]
    po = a["power_orthogonal_5bet"]
    assert pp["production_baseline_rows"] == 1500
    assert po["production_baseline_rows"] == 1500
    assert pp["null_provenance_legacy_rows"] == 50
    assert po["null_provenance_legacy_rows"] == 50
    assert a["summary"]["legacy_rows_keepable_in_p136"] is True


def test_per_strategy_reevaluation_matrix(artifact):
    m = artifact["per_strategy_reevaluation_matrix"]
    for sid in ("power_precision_3bet", "power_orthogonal_5bet"):
        assert m[sid]["baseline_valid_for_future_dry_run"] is True
        assert m[sid]["requires_remark_plan"] is True
        assert m[sid]["requires_quarantine_plan"] is True
        assert m[sid]["requires_cleanup_authorization"] is True
        assert m[sid]["remains_apply_blocked"] is True


def test_apply_gate_status(artifact):
    g = artifact["apply_gate_status"]
    assert g["controlled_apply_executed"] is False
    assert g["replay_rows_inserted"] == 0
    assert g["power_precision_3bet_apply_ready"] is False
    assert g["power_orthogonal_5bet_apply_ready"] is False
    assert g["per_strategy_authorization_required_later"] is True
    assert g["production_db_rows_expected"] == EXPECTED_ROWS
    assert g["production_db_rows_after"] == EXPECTED_ROWS


def test_blocked_or_excluded(artifact):
    b = artifact["blocked_or_excluded"]
    assert b["no_db_write_in_p136"] is True
    assert b["no_controlled_apply_in_p136"] is True
    assert b["no_replay_rows_inserted"] is True
    assert b["4_STAR_excluded"] is True
    assert b["P108_not_run"] is True
    assert b["P117_not_run"] is True
    assert b["P118_not_run"] is True
    assert b["rejected_strategies_no_action"] is True
    assert b["no_scheduler_install"] is True
    assert b["no_lifecycle_champion_registry_mutation"] is True


def test_markdown_exists_and_sections():
    assert MD_PATH.exists()
    md = MD_PATH.read_text(encoding="utf-8")
    assert "Executive Summary" in md
    assert "P135 Recap" in md
    assert "RSR-6 Cleanup Recap" in md
    assert "Baseline Row Audit" in md
    assert "Future Dry-run Gate Checklist" in md
    assert EXPECTED_CLASSIFICATION in md


def test_live_db_constraints(db_conn):
    rows = db_conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert rows == EXPECTED_ROWS
    cols = [r[1] for r in db_conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    assert "bet_index" in cols
    for sid in ("power_precision_3bet", "power_orthogonal_5bet"):
        bet1 = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index=1",
            (sid,),
        ).fetchone()[0]
        bet2p = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND bet_index>1",
            (sid,),
        ).fetchone()[0]
        assert bet1 == 1550
        assert bet2p == 0


def test_no_forbidden_files_staged():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    staged = result.stdout.splitlines()
    for token in ("lottery_v2.db", ".history", ".runtime", ".pid"):
        assert not any(token in path for path in staged), f"Forbidden staged path includes {token}"
