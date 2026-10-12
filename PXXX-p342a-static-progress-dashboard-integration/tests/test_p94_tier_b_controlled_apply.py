"""
P94 Tier B Controlled Replay Apply — Test Suite
================================================
All required validation checks per P94 task specification.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ─── Paths ────────────────────────────────────────────────────────────────────

PROD_DB_PATH = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_FILE    = _REPO_ROOT / "outputs" / "replay" / "p94_tier_b_controlled_apply_20260526.json"
MD_FILE      = _REPO_ROOT / "docs"    / "replay" / "p94_tier_b_controlled_apply_20260526.md"

P94_STRATEGY_IDS = [
    "daily539_f4cold_3bet",
    "daily539_f4cold_5bet",
    "biglotto_echo_aware_3bet",
    "power_fourier_rhythm_2bet",
    "biglotto_ts3_markov_4bet_w30",
]

EXPECTED_BEFORE        = 46962
EXPECTED_AFTER         = 54462
EXPECTED_INSERT        = 7500
EXPECTED_PER_STRATEGY  = 1500
EXPECTED_MAX_DRAW_PL   = "115000041"
CONTROLLED_APPLY_ID    = "P94_TIERB_CONTROLLED_APPLY_20260526"
TRUTH_LEVEL            = "TIERB_DRYRUN_VALIDATED"


def _load_json() -> dict:
    with open(str(JSON_FILE), encoding="utf-8") as f:
        return json.load(f)


# ─── T1: JSON artifact exists ────────────────────────────────────────────────

def test_json_artifact_exists():
    assert JSON_FILE.exists(), f"Missing: {JSON_FILE}"


# ─── T2: Markdown artifact exists ────────────────────────────────────────────

def test_md_artifact_exists():
    assert MD_FILE.exists(), f"Missing: {MD_FILE}"


# ─── T3: Classification correct ──────────────────────────────────────────────

def test_classification():
    data = _load_json()
    assert data["final_classification"] == "P94_TIER_B_CONTROLLED_APPLY_SUCCESS", (
        f"Unexpected classification: {data['final_classification']!r}"
    )


# ─── T4: Backup path present ─────────────────────────────────────────────────

def test_backup_path_present():
    data = _load_json()
    bp = data.get("db_backup_path", "")
    assert bp, "db_backup_path is empty"
    assert "p94_pre_apply" in bp, f"Unexpected backup path: {bp!r}"


# ─── T5: controlled_apply_id present ─────────────────────────────────────────

def test_controlled_apply_id():
    data = _load_json()
    assert data.get("controlled_apply_id") == CONTROLLED_APPLY_ID


# ─── T6: Inserted row count = 7500 ───────────────────────────────────────────

def test_inserted_row_count():
    data = _load_json()
    assert data.get("total_inserted") == EXPECTED_INSERT, (
        f"total_inserted={data.get('total_inserted')} expected {EXPECTED_INSERT}"
    )


# ─── T7: Before row count = 46962 ────────────────────────────────────────────

def test_before_row_count():
    data = _load_json()
    assert data.get("production_rows_before") == EXPECTED_BEFORE


# ─── T8: After row count = 54462 ─────────────────────────────────────────────

def test_after_row_count_json():
    data = _load_json()
    assert data.get("production_rows_after") == EXPECTED_AFTER, (
        f"production_rows_after={data.get('production_rows_after')} expected {EXPECTED_AFTER}"
    )


# ─── T9: Each target strategy has exactly 1500 production rows ───────────────

def test_per_strategy_counts_json():
    data = _load_json()
    per = data.get("per_strategy_production_rows", {})
    for sid in P94_STRATEGY_IDS:
        assert per.get(sid) == EXPECTED_PER_STRATEGY, (
            f"{sid}: JSON says {per.get(sid)} rows, expected {EXPECTED_PER_STRATEGY}"
        )


# ─── T9b: Verify per-strategy counts in production DB ───────────────────────

def test_per_strategy_counts_in_db():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        for sid in P94_STRATEGY_IDS:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND dry_run=0",
                (sid,),
            ).fetchone()[0]
            assert count == EXPECTED_PER_STRATEGY, (
                f"{sid}: DB has {count} production rows, expected {EXPECTED_PER_STRATEGY}"
            )
    finally:
        conn.close()


# ─── T10: truth_level = TIERB_DRYRUN_VALIDATED ───────────────────────────────

def test_truth_level():
    data = _load_json()
    assert data.get("truth_level") == TRUTH_LEVEL
    # Spot-check in DB
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        row = conn.execute(
            "SELECT truth_level FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? LIMIT 1",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()
        assert row and row[0] == TRUTH_LEVEL, f"truth_level in DB={row}"
    finally:
        conn.close()


# ─── T11: Rollback SQL present ───────────────────────────────────────────────

def test_rollback_sql_present():
    data = _load_json()
    sql = data.get("rollback_sql", "")
    assert CONTROLLED_APPLY_ID in sql, "rollback SQL must reference controlled_apply_id"
    assert "DELETE FROM strategy_prediction_replays" in sql


# ─── T12: P79 sentinel rows unchanged ────────────────────────────────────────

def test_p79_sentinels_intact():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        for row_id, expected_sid, expected_tl in [
            (46961, "fourier_rhythm_3bet",      "POWERLOTTO_DRAW_EXT_VERIFIED"),
            (46962, "fourier30_markov30_2bet",   "POWERLOTTO_DRAW_EXT_VERIFIED"),
        ]:
            row = conn.execute(
                "SELECT strategy_id, dry_run, truth_level FROM strategy_prediction_replays WHERE id=?",
                (row_id,),
            ).fetchone()
            assert row, f"P79 sentinel id={row_id} missing"
            assert row[0] == expected_sid, f"P79 row {row_id} strategy_id mismatch: {row[0]}"
            assert row[1] == 0,             f"P79 row {row_id} dry_run={row[1]} expected 0"
            assert row[2] == expected_tl,   f"P79 row {row_id} truth_level={row[2]}"
    finally:
        conn.close()


# ─── T13: POWER_LOTTO max draw unchanged ─────────────────────────────────────

def test_max_draw_unchanged():
    data = _load_json()
    assert data.get("power_lotto_max_draw_before") == EXPECTED_MAX_DRAW_PL
    assert data.get("power_lotto_max_draw_after")  == EXPECTED_MAX_DRAW_PL
    # Live DB check
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        row = conn.execute(
            "SELECT draw FROM draws WHERE lottery_type='POWER_LOTTO' "
            "ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1"
        ).fetchone()
        assert row and row[0] == EXPECTED_MAX_DRAW_PL
    finally:
        conn.close()


# ─── T14: No lifecycle mutation ──────────────────────────────────────────────

def test_no_lifecycle_mutation():
    data = _load_json()
    gov = data.get("governance", {})
    assert gov.get("no_lifecycle_mutation") is True
    # MD must state it
    content = MD_FILE.read_text(encoding="utf-8")
    assert "No Lifecycle Mutation" in content or "no_lifecycle_mutation" in content.lower() or \
        "lifecycle" in content.lower(), "MD must reference lifecycle mutation status"


# ─── T15: No draw mutation ───────────────────────────────────────────────────

def test_no_draw_mutation():
    data = _load_json()
    gov = data.get("governance", {})
    assert gov.get("no_draw_table_mutation") is True
    assert data.get("draw_table_unchanged") is True


# ─── T16: Production DB row count = 54462 (live) ─────────────────────────────

def test_production_db_row_count():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert count == EXPECTED_AFTER, (
            f"Production DB has {count} rows, expected {EXPECTED_AFTER}"
        )
    finally:
        conn.close()


# ─── T17: dry_run=0 on all P94 rows ──────────────────────────────────────────

def test_all_p94_rows_dry_run_zero():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        bad = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND dry_run!=0",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        assert bad == 0, f"{bad} P94 rows have dry_run!=0"
    finally:
        conn.close()


# ─── T18: Controlled apply rows count in DB ──────────────────────────────────

def test_controlled_apply_rows_in_db():
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (CONTROLLED_APPLY_ID,),
        ).fetchone()[0]
        assert count == EXPECTED_INSERT, (
            f"controlled_apply_id rows={count} expected {EXPECTED_INSERT}"
        )
    finally:
        conn.close()


# ─── T19: No DB/backup/runtime files staged ──────────────────────────────────

def test_no_db_backup_staged():
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT)
    )
    staged = result.stdout.strip().split("\n") if result.stdout.strip() else []
    forbidden = [
        f for f in staged
        if any(f.endswith(ext) for ext in (".db", ".bak", ".pid", ".lock", ".log"))
        or ("lottery_v2" in f)
        or ("/data/" in f and f.endswith(".db"))
    ]
    assert not forbidden, f"Forbidden staged files: {forbidden}"


# ─── T20: Rollback SQL in MD ─────────────────────────────────────────────────

def test_rollback_sql_in_md():
    content = MD_FILE.read_text(encoding="utf-8")
    assert CONTROLLED_APPLY_ID in content, "rollback SQL controlled_apply_id not in MD"
    assert "DELETE FROM strategy_prediction_replays" in content


# ─── T21: P93 artifacts still present ────────────────────────────────────────

def test_p93_artifacts_present():
    p93_files = [
        _REPO_ROOT / "lottery_api" / "models" / "p93_tierb_replay_adapters.py",
        _REPO_ROOT / "outputs" / "replay" / "p93_tier_b_replay_adapter_bootstrap_dryrun_20260526.json",
        _REPO_ROOT / "tests" / "test_p93_tier_b_replay_adapter_bootstrap_dryrun.py",
    ]
    for f in p93_files:
        assert f.exists(), f"P93 artifact missing: {f}"


# ─── T22: Per-strategy rows have correct lottery_type ────────────────────────

def test_per_strategy_lottery_type_in_db():
    expected_types = {
        "daily539_f4cold_3bet":          "DAILY_539",
        "daily539_f4cold_5bet":          "DAILY_539",
        "biglotto_echo_aware_3bet":      "BIG_LOTTO",
        "power_fourier_rhythm_2bet":     "POWER_LOTTO",
        "biglotto_ts3_markov_4bet_w30":  "BIG_LOTTO",
    }
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        for sid, expected_lt in expected_types.items():
            row = conn.execute(
                "SELECT DISTINCT lottery_type FROM strategy_prediction_replays "
                "WHERE strategy_id=? AND controlled_apply_id=?",
                (sid, CONTROLLED_APPLY_ID),
            ).fetchone()
            assert row and row[0] == expected_lt, (
                f"{sid}: lottery_type={row} expected {expected_lt!r}"
            )
    finally:
        conn.close()


# ─── T23: P94 recommendation in JSON ─────────────────────────────────────────

def test_p95_recommendation_present():
    data = _load_json()
    p95 = data.get("p95_recommendation")
    assert p95, "p95_recommendation block missing from JSON"
    assert "scope" in p95
    assert "api_query_example" in p95
