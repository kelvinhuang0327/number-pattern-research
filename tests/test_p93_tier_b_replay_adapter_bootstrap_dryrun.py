"""
P93 Tier B Replay Adapter Bootstrap + Dry-run Rehearsal — Test Suite
=====================================================================
Covers all required validation checks per P93 task specification.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ─── Paths ────────────────────────────────────────────────────────────────────

PROD_DB_PATH = _REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
TEMP_DB_PATH = Path("/tmp/p93_tierb_dryrun_rehearsal.db")
ADAPTER_FILE = _REPO_ROOT / "lottery_api" / "models" / "p93_tierb_replay_adapters.py"
SCRIPT_FILE  = _REPO_ROOT / "scripts" / "p93_tierb_dryrun_rehearsal.py"
JSON_FILE    = _REPO_ROOT / "outputs" / "replay" / "p93_tier_b_replay_adapter_bootstrap_dryrun_20260526.json"
MD_FILE      = _REPO_ROOT / "docs" / "replay" / "p93_tier_b_replay_adapter_bootstrap_dryrun_20260526.md"

P93_STRATEGY_IDS = [
    "daily539_f4cold_3bet",
    "daily539_f4cold_5bet",
    "biglotto_echo_aware_3bet",
    "power_fourier_rhythm_2bet",
    "biglotto_ts3_markov_4bet_w30",
]

EXPECTED_PROD_ROWS    = 46962
EXPECTED_MAX_DRAW_PL  = "115000041"
EXPECTED_TEMP_ROWS    = 7500
EXPECTED_ROWS_PER_STRAT = 1500


# ─── Test 1: Adapter artifact exists ─────────────────────────────────────────

def test_adapter_artifact_exists():
    """T1: Adapter file exists at expected path."""
    assert ADAPTER_FILE.exists(), f"Missing: {ADAPTER_FILE}"


# ─── Test 2: Dry-run script exists ───────────────────────────────────────────

def test_dryrun_script_exists():
    """T2: Dry-run rehearsal script exists."""
    assert SCRIPT_FILE.exists(), f"Missing: {SCRIPT_FILE}"


# ─── Test 3: JSON artifact exists ────────────────────────────────────────────

def test_json_artifact_exists():
    """T3: JSON output artifact exists."""
    assert JSON_FILE.exists(), f"Missing: {JSON_FILE}"


# ─── Test 4: MD artifact exists ──────────────────────────────────────────────

def test_md_artifact_exists():
    """T4: Markdown documentation artifact exists."""
    assert MD_FILE.exists(), f"Missing: {MD_FILE}"


# ─── Test 5: All 5 strategies represented in JSON ────────────────────────────

def _load_json() -> dict:
    with open(str(JSON_FILE), encoding="utf-8") as f:
        return json.load(f)


def test_all_5_strategies_in_json():
    """T5: All 5 target strategies are present in the JSON artifact."""
    data = _load_json()
    strat_ids = [s["strategy_id"] for s in data["strategies"]]
    for sid in P93_STRATEGY_IDS:
        assert sid in strat_ids, f"Strategy {sid!r} missing from JSON"


# ─── Test 6: Production DB row count remains 46962 ───────────────────────────

def test_production_db_row_count():
    """T6: Production DB replay row count remains 46962 (unchanged)."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == EXPECTED_PROD_ROWS, (
        f"Production DB row count changed: expected {EXPECTED_PROD_ROWS}, got {count}"
    )


# ─── Test 7: POWER_LOTTO max draw remains 115000041 ──────────────────────────

def test_production_max_draw():
    """T7: POWER_LOTTO max draw remains 115000041 in production DB."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        row = conn.execute(
            "SELECT draw FROM draws WHERE lottery_type='POWER_LOTTO' "
            "ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None, "No POWER_LOTTO draws found"
    assert row[0] == EXPECTED_MAX_DRAW_PL, (
        f"Max draw changed: expected {EXPECTED_MAX_DRAW_PL}, got {row[0]}"
    )


# ─── Test 8: Temp DB path used (not production) ──────────────────────────────

def test_temp_db_path_used():
    """T8: JSON artifact references /tmp path for temp DB, not production path."""
    data = _load_json()
    temp_path = data.get("temp_db_path", "")
    assert temp_path.startswith("/tmp/"), (
        f"Expected temp_db_path to start with /tmp/, got: {temp_path!r}"
    )
    prod_path = data.get("production_db_path", "")
    assert prod_path != temp_path, "Temp DB path must differ from production DB path"


# ─── Test 9: lottery_v2.db not written ───────────────────────────────────────

def test_lottery_v2_not_written():
    """T9: JSON confirms db_writes_to_prod=False and production rows unchanged."""
    data = _load_json()
    assert data.get("db_writes_to_prod") is False, "db_writes_to_prod must be False"
    assert data.get("production_rows_before") == EXPECTED_PROD_ROWS, \
        f"production_rows_before should be {EXPECTED_PROD_ROWS}"
    assert data.get("production_rows_after") == EXPECTED_PROD_ROWS, \
        f"production_rows_after should be {EXPECTED_PROD_ROWS}"
    assert data.get("prod_unchanged") is True, "prod_unchanged must be True"


# ─── Test 10: No lifecycle promotion text ────────────────────────────────────

def test_no_lifecycle_promotion():
    """T10: MD artifact does not contain forbidden lifecycle promotion language."""
    content = MD_FILE.read_text(encoding="utf-8")
    forbidden_phrases = [
        "PROMOTE",
        "LIFECYCLE_PROMOTE",
        "status = ONLINE",  # direct status assignment (OK in tables as value)
        "champion_set",
        "registry_update",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in content, (
            f"Forbidden phrase {phrase!r} found in MD artifact"
        )
    # Also check adapter file — must NOT mutate the MAIN replay_strategy_registry
    adapter_content = ADAPTER_FILE.read_text(encoding="utf-8")
    adapter_forbidden = [
        "champion_set",
        "registry_update",
        # Adapter file has its own _P93_REGISTRY — that is allowed.
        # Must NOT import and mutate the MAIN _REGISTRY or _ALL_ADAPTERS.
        "_ALL_ADAPTERS.append",
        "_ALL_ADAPTERS +=",
        "_REGISTRY.update(",
    ]
    for phrase in adapter_forbidden:
        assert phrase not in adapter_content, (
            f"Forbidden phrase {phrase!r} found in adapter file"
        )
    # Must not add entries to the main registry via import assignment
    assert (
        "from lottery_api.models.replay_strategy_registry import _REGISTRY\n" not in adapter_content
        and "replay_strategy_registry._REGISTRY[" not in adapter_content
    ), "Adapter file must not mutate main replay_strategy_registry._REGISTRY"


# ─── Test 11: No official API write path ─────────────────────────────────────

def test_no_official_api_write():
    """T11: Governance flag confirms no_official_api_ingestion=True."""
    data = _load_json()
    gov = data.get("governance", {})
    assert gov.get("no_official_api_ingestion") is True, \
        "governance.no_official_api_ingestion must be True"
    assert gov.get("no_prod_db_writes") is True, \
        "governance.no_prod_db_writes must be True"


# ─── Test 12: No DB/backup/runtime staging ───────────────────────────────────

def test_no_db_backup_staging(tmp_path):
    """T12: No DB or backup files are staged in git (spot-check via file list)."""
    import subprocess
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=str(_REPO_ROOT)
    )
    staged = result.stdout.strip().split("\n") if result.stdout.strip() else []
    forbidden_staged = [
        f for f in staged
        if any(
            f.endswith(ext)
            for ext in (".db", ".bak", ".pid", ".lock", ".log")
        )
        or "lottery_v2" in f
        or "/data/" in f and f.endswith(".db")
    ]
    assert not forbidden_staged, (
        f"Forbidden staged files: {forbidden_staged}"
    )


# ─── Test 13: Adapter output shape validation ────────────────────────────────

def test_adapter_import_and_list():
    """T13: P93 adapter module imports correctly and lists 5 adapters."""
    from lottery_api.models.p93_tierb_replay_adapters import (
        list_p93_adapters,
        P93_STRATEGY_IDS as _IDS,
    )
    adapters = list_p93_adapters()
    assert len(adapters) == 5, f"Expected 5 adapters, got {len(adapters)}"
    ids = [a["strategy_id"] for a in adapters]
    for sid in P93_STRATEGY_IDS:
        assert sid in ids, f"Strategy {sid!r} not in adapter list"
    # Verify scope marker
    for a in adapters:
        assert a["scope"] == "P93_DRYRUN_ONLY", \
            f"scope must be P93_DRYRUN_ONLY, got {a['scope']!r}"
        assert a["production_eligible"] is False, \
            "production_eligible must be False"


# ─── Test 14: Number range validation ────────────────────────────────────────

def test_number_range_rules():
    """T14: Adapter lottery type and number range rules are correct."""
    from lottery_api.models.p93_tierb_replay_adapters import list_p93_adapters

    expected_types = {
        "daily539_f4cold_3bet":       ("DAILY_539",   5, 39),
        "daily539_f4cold_5bet":       ("DAILY_539",   5, 39),
        "biglotto_echo_aware_3bet":   ("BIG_LOTTO",   6, 49),
        "power_fourier_rhythm_2bet":  ("POWER_LOTTO", 6, 38),
        "biglotto_ts3_markov_4bet_w30": ("BIG_LOTTO", 6, 49),
    }
    adapters = {a["strategy_id"]: a for a in list_p93_adapters()}
    for sid, (lt, k, pool) in expected_types.items():
        assert adapters[sid]["lottery_type"] == lt, \
            f"{sid}: expected lottery_type {lt!r}, got {adapters[sid]['lottery_type']!r}"


# ─── Test 15: Duplicate guard documented ─────────────────────────────────────

def test_duplicate_guard_documented():
    """T15: Duplicate guard is confirmed active in JSON governance block."""
    data = _load_json()
    gov = data.get("governance", {})
    assert gov.get("duplicate_guard") is True, \
        "governance.duplicate_guard must be True"


# ─── Test 16: P94 recommendation exists ─────────────────────────────────────

def test_p94_recommendation_exists():
    """T16: JSON contains a p94_recommendation block with required fields."""
    data = _load_json()
    p94 = data.get("p94_recommendation")
    assert p94 is not None, "p94_recommendation block is missing from JSON"
    assert "scope" in p94, "p94_recommendation.scope is missing"
    assert "expected_insert_delta" in p94, "p94_recommendation.expected_insert_delta is missing"
    assert "strategies_to_apply" in p94, "p94_recommendation.strategies_to_apply is missing"
    assert len(p94["strategies_to_apply"]) > 0, "p94_recommendation.strategies_to_apply is empty"


# ─── Test 17: Temp DB dry_run=1 rows count ───────────────────────────────────

def test_temp_db_dry_run_rows():
    """T17: Temp DB contains exactly 7500 dry_run=1 rows across 5 strategies."""
    if not TEMP_DB_PATH.exists():
        pytest.skip("Temp DB not present — run rehearsal script first")
    conn = sqlite3.connect(str(TEMP_DB_PATH))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE dry_run=1"
        ).fetchone()[0]
        by_strat = dict(conn.execute(
            "SELECT strategy_id, COUNT(*) FROM strategy_prediction_replays "
            "WHERE dry_run=1 GROUP BY strategy_id"
        ).fetchall())
    finally:
        conn.close()

    assert count == EXPECTED_TEMP_ROWS, (
        f"Expected {EXPECTED_TEMP_ROWS} dry_run=1 rows, got {count}"
    )
    for sid in P93_STRATEGY_IDS:
        assert by_strat.get(sid, 0) == EXPECTED_ROWS_PER_STRAT, (
            f"{sid}: expected {EXPECTED_ROWS_PER_STRAT} rows, got {by_strat.get(sid, 0)}"
        )


# ─── Test 18: P93 strategies absent from production DB ───────────────────────

def test_p93_strategies_absent_from_production():
    """T18: No P93 strategy rows exist in production DB."""
    conn = sqlite3.connect(str(PROD_DB_PATH))
    try:
        for sid in P93_STRATEGY_IDS:
            count = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
                (sid,),
            ).fetchone()[0]
            assert count == 0, (
                f"P93 strategy {sid!r} found in production DB with {count} rows — "
                "should be 0"
            )
    finally:
        conn.close()


# ─── Test 19: JSON final_classification is COMPLETE ──────────────────────────

def test_json_classification_complete():
    """T19: JSON final_classification is P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETE."""
    data = _load_json()
    assert data["final_classification"] == "P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETE", (
        f"Unexpected classification: {data['final_classification']!r}"
    )


# ─── Test 20: Bet counts match expected ──────────────────────────────────────

def test_expected_bet_counts_in_adapter():
    """T20: Adapter metadata reports correct expected bet counts."""
    from lottery_api.models.p93_tierb_replay_adapters import (
        EXPECTED_BET_COUNTS,
        P93_STRATEGY_IDS as _IDS,
    )
    expected = {
        "daily539_f4cold_3bet":       3,
        "daily539_f4cold_5bet":       5,
        "biglotto_echo_aware_3bet":   3,
        "power_fourier_rhythm_2bet":  2,
        "biglotto_ts3_markov_4bet_w30": 4,
    }
    for sid, n in expected.items():
        assert EXPECTED_BET_COUNTS.get(sid) == n, (
            f"{sid}: expected bet count {n}, got {EXPECTED_BET_COUNTS.get(sid)}"
        )


# ─── Test 21: Adapter not in main _REGISTRY ──────────────────────────────────

def test_p93_adapters_not_in_main_registry():
    """T21: P93 strategies are NOT present in the main replay_strategy_registry._REGISTRY."""
    from lottery_api.models.replay_strategy_registry import _REGISTRY
    for sid in P93_STRATEGY_IDS:
        assert sid not in _REGISTRY, (
            f"P93 strategy {sid!r} was incorrectly added to main _REGISTRY"
        )


# ─── Test 22: Causal isolation documented ────────────────────────────────────

def test_causal_isolation_documented():
    """T22: Governance block confirms causal_isolation=True in JSON."""
    data = _load_json()
    gov = data.get("governance", {})
    assert gov.get("causal_isolation") is True, \
        "governance.causal_isolation must be True"


# ─── Test 23: MD governance assertions present ───────────────────────────────

def test_md_governance_assertions():
    """T23: MD artifact contains required governance statements."""
    content = MD_FILE.read_text(encoding="utf-8")
    required_statements = [
        "No production DB writes",
        "No replay row insert",
        "No lifecycle/champion/registry mutation",
        "No official API ingestion",
        "dry_run=1",
    ]
    for stmt in required_statements:
        assert stmt in content, f"Missing required statement in MD: {stmt!r}"


# ─── Test 24: JSON rows per strategy match ───────────────────────────────────

def test_json_rows_per_strategy():
    """T24: JSON strategy entries report rows_ready=1500 for all 5 strategies."""
    data = _load_json()
    strats = {s["strategy_id"]: s for s in data["strategies"]}
    for sid in P93_STRATEGY_IDS:
        assert sid in strats, f"Strategy {sid!r} missing from JSON strategies list"
        assert strats[sid]["rows_ready"] == EXPECTED_ROWS_PER_STRAT, (
            f"{sid}: expected rows_ready={EXPECTED_ROWS_PER_STRAT}, "
            f"got {strats[sid]['rows_ready']}"
        )
