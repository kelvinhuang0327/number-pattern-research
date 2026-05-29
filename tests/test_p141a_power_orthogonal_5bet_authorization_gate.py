"""Tests for P141A power_orthogonal_5bet authorization artifact gate."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

WORKTREE = Path("/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802")
DB_PATH = WORKTREE / "lottery_api/data/lottery_v2.db"
ARTIFACT_JSON = WORKTREE / "outputs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.json"
ARTIFACT_MD = WORKTREE / "docs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.md"

AUTH_PHRASE = (
    "P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_BET3_BET4_BET5_"
    "USING_1500_PRODUCTION_BASE_20260529"
)


@pytest.fixture(scope="module")
def artifact():
    assert ARTIFACT_JSON.exists(), f"Missing: {ARTIFACT_JSON}"
    return json.loads(ARTIFACT_JSON.read_text())


@pytest.fixture(scope="module")
def conn():
    c = sqlite3.connect(DB_PATH)
    yield c
    c.close()


def test_json_exists():
    assert ARTIFACT_JSON.exists()


def test_md_exists():
    assert ARTIFACT_MD.exists()


def test_task_id(artifact):
    assert artifact["task_id"] == "P141A"


def test_classification(artifact):
    assert artifact["classification"] == "P141A_POWER_ORTHOGONAL_5BET_AUTHORIZATION_GATE_READY"


def test_repo_branch_ok(artifact):
    assert artifact["repo_branch_check"]["repo_ok"] is True
    assert artifact["repo_branch_check"]["branch_ok"] is True


def test_db_rows_88924(artifact, conn):
    assert artifact["db_snapshot"]["total_rows"] == 88924  # historical artifact value, fixed
    rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert rows == 94924  # post-P141: +6000 power_orthogonal_5bet rows


def test_bet_index_column_exists(conn):
    cols = [r[1] for r in conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()]
    assert "bet_index" in cols


def test_p140_validation(artifact):
    assert artifact["p140_source_summary"]["classification"] == "P140_POWER_PRECISION_3BET_APPLIED"
    assert artifact["p140_source_summary"]["classification_ok"] is True


def test_p140a_validation(artifact):
    assert artifact["p140a_source_summary"]["classification"] == "P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY"
    assert artifact["p140a_source_summary"]["classification_ok"] is True


def test_authorization_phrase_present(artifact):
    gate = artifact["authorization_gate"]
    assert gate["exact_required_phrase"] == AUTH_PHRASE
    assert gate["authorization_phrase_present"] is True
    assert gate["authorization_artifact_created"] is True
    assert gate["future_p141_apply_allowed_after_preflight"] is True
    assert gate["apply_executed_in_p141a"] is False


def test_apply_gate_status(artifact):
    gate = artifact["apply_gate_status"]
    assert gate["authorization_gate_only"] is True
    assert gate["controlled_apply_executed"] is False
    assert gate["replay_rows_inserted"] == 0
    assert gate["db_write_in_p141a"] is False
    assert gate["db_rows_before"] == 88924
    assert gate["db_rows_after"] == 88924
    assert gate["p141_apply_pending"] is True


def test_power_orthogonal_distribution(artifact):
    d = artifact["power_orthogonal_current_distribution"]
    assert d["strategy_id"] == "power_orthogonal_5bet"
    assert d["bet1_total_rows"] == 1550
    assert d["production_baseline_rows"] == 1500
    assert d["legacy_unverified_rows"] == 50
    assert d["bet2_plus_rows"] == 0


def test_scope_preview(artifact):
    p = artifact["p141_apply_scope_preview"]
    assert p["strategy_id"] == "power_orthogonal_5bet"
    assert p["target_bet_count"] == 5
    assert p["missing_bet_indices"] == [2, 3, 4, 5]
    assert p["expected_insert_rows"] == 6000
    assert p["db_rows_before_expected"] == 88924
    assert p["db_rows_after_expected"] == 94924
    assert p["legacy_unverified_excluded_from_apply_base"] is True
    assert p["production_baseline_rows_used"] == 1500
    assert p["per_strategy_authorization_required"] is True


def test_blocked_or_excluded(artifact):
    b = artifact["blocked_or_excluded"]
    assert b["backups_directory_untracked_but_not_staged"] is True
    assert b["4_STAR_excluded"] is True
    assert b["P108_not_run"] is True
    assert b["P117_not_run"] is True
    assert b["P118_not_run"] is True
    assert b["rejected_strategies_no_action"] is True


def test_markdown_contains_phrase_and_preview():
    text = ARTIFACT_MD.read_text()
    assert AUTH_PHRASE in text
    assert "P141 apply scope preview" in text or "P141 Apply Scope Preview" in text


def test_no_db_staged():
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=str(WORKTREE),
        capture_output=True,
        text=True,
        check=True,
    )
    staged = result.stdout
    assert "lottery_api/data/lottery_v2.db" not in staged
    for token in (".history", ".runtime", ".pid"):
        assert token not in staged

