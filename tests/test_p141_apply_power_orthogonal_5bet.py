"""Tests for P141 apply power_orthogonal_5bet controlled replay rows."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
ARTIFACT_JSON = WORKTREE / "outputs/replay/p141_apply_power_orthogonal_5bet_20260529.json"
ARTIFACT_MD = WORKTREE / "docs/replay/p141_apply_power_orthogonal_5bet_20260529.md"

AUTH_PHRASE = (
    "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_BET3_BET4_BET5_USING_1500_"
    "PRODUCTION_BASE_20260529"
)


def _artifact():
    return json.loads(ARTIFACT_JSON.read_text())


def test_artifact_exists():
    assert ARTIFACT_JSON.exists()
    assert ARTIFACT_MD.exists()


def test_identity():
    a = _artifact()
    assert a["task_id"] == "P141"
    assert a["classification"] == "P141_POWER_ORTHOGONAL_5BET_APPLIED"


def test_authorization():
    a = _artifact()["authorization"]
    assert a["exact_required_phrase"] == AUTH_PHRASE
    assert a["authorization_present"] is True
    assert a["apply_allowed"] is True
    assert a["authorization_source_artifact"].endswith("p141a_power_orthogonal_5bet_authorization_gate_20260529.json")


def test_repo_branch():
    c = _artifact()["repo_branch_check"]
    assert c["repo_ok"] is True
    assert c["branch_ok"] is True


def test_backup():
    b = _artifact()["backup"]
    assert b["backup_created"] is True
    assert b["backup_row_count"] == 88924
    assert b["backup_verification"] == "PASS"


def test_counts_and_scope():
    a = _artifact()
    assert a["db_snapshot_before"]["replay_rows"] == 88924
    assert a["db_snapshot_after"]["replay_rows"] == 94924
    scope = a["apply_scope"]
    assert scope["expected_insert_rows"] == 6000
    assert scope["actual_insert_rows"] == 6000
    assert scope["rows_deleted"] == 0


def test_legacy_handling():
    h = _artifact()["legacy_unverified_handling"]
    assert h["legacy_unverified_excluded_from_apply_base"] is True
    assert h["production_baseline_rows_used"] == 1500
    assert h["legacy_rows_modified"] == 0


def test_db_distributions_live():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert total == 94924

    p12 = dict(
        conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='power_orthogonal_5bet' GROUP BY bet_index ORDER BY bet_index"
        ).fetchall()
    )
    assert p12[1] == 1550
    assert p12[2] == 1500
    assert p12[3] == 1500
    assert p12[4] == 1500
    assert p12[5] == 1500

    p12_legacy = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id='power_orthogonal_5bet' AND truth_level='LEGACY_UNVERIFIED'"
    ).fetchone()[0]
    assert p12_legacy == 50

    new_wrong_sid = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id='P141_APPLY_POWER_ORTHOGONAL_5BET_v1' "
        "AND strategy_id!='power_orthogonal_5bet'"
    ).fetchone()[0]
    assert new_wrong_sid == 0

    new_wrong_lottery = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id='P141_APPLY_POWER_ORTHOGONAL_5BET_v1' "
        "AND lottery_type!='POWER_LOTTO'"
    ).fetchone()[0]
    assert new_wrong_lottery == 0

    p10 = dict(
        conn.execute(
            "SELECT bet_index, COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='power_precision_3bet' GROUP BY bet_index ORDER BY bet_index"
        ).fetchall()
    )
    assert p10[1] == 1550 and p10[2] == 1500 and p10[3] == 1500
    conn.close()


def test_markdown_contains_required_text():
    txt = ARTIFACT_MD.read_text()
    assert AUTH_PHRASE in txt
    assert "LEGACY_UNVERIFIED exclusion rule" in txt
    assert "Rollback reference / backup path" in txt

