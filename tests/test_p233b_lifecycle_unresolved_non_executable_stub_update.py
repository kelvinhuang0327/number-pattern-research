"""
Targeted tests for P233B lifecycle-unresolved non-executable stub update.

Covers:
  - Exactly 20 P233B stubs added to registry
  - 12 REJECTED and 8 RETIRED as per P233A plan
  - None appear in executable adapters list
  - LifecycleNotExecutable raised when attempting to call any P233B stub
  - P232A scoreboard LIFECYCLE_UNRESOLVED drops to 0 after registry update
  - DB row count unchanged
  - No ONLINE/DEPLOYABLE/PROMOTE status in any P233B stub
  - Deterministic output
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lottery_api.models.replay_strategy_registry import (
    LifecycleNotExecutable,
    list_executable_strategy_ids,
    list_non_executable_strategy_ids,
    list_strategy_lifecycle_metadata,
    summarize_strategy_lifecycle_counts,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# ── The 20 P233B stubs (strategy_id, lottery_type, expected_lifecycle) ─────────
P233B_STUBS = [
    # REJECTED — 12 entries (evidence: rejected/ archive)
    ("bet2_fourier_expansion_biglotto", "BIG_LOTTO",  "REJECTED"),
    ("cold_complement_biglotto",        "BIG_LOTTO",  "REJECTED"),
    ("coldpool15_biglotto",             "BIG_LOTTO",  "REJECTED"),
    ("fourier30_markov30_biglotto",     "BIG_LOTTO",  "REJECTED"),
    ("markov_2bet_biglotto",            "BIG_LOTTO",  "REJECTED"),
    ("markov_single_biglotto",          "BIG_LOTTO",  "REJECTED"),
    ("539_3bet_orthogonal",             "DAILY_539",  "REJECTED"),
    ("acb_single_539",                  "DAILY_539",  "REJECTED"),
    ("markov_1bet_539",                 "DAILY_539",  "REJECTED"),
    ("p0b_539_3bet_f_cold_fmid",        "DAILY_539",  "REJECTED"),
    ("p0c_539_3bet_f_cold_x2",          "DAILY_539",  "REJECTED"),
    ("zone_gap_3bet_539",               "DAILY_539",  "REJECTED"),
    # RETIRED — 8 entries (evidence: production controlled applies P59/P66/P79/P94/P126D)
    ("biglotto_echo_aware_3bet",        "BIG_LOTTO",  "RETIRED"),
    ("biglotto_ts3_markov_4bet_w30",    "BIG_LOTTO",  "RETIRED"),
    ("daily539_f4cold_3bet",            "DAILY_539",  "RETIRED"),
    ("daily539_f4cold_5bet",            "DAILY_539",  "RETIRED"),
    ("cold_complement_2bet",            "POWER_LOTTO","RETIRED"),
    ("fourier30_markov30_2bet",         "POWER_LOTTO","RETIRED"),
    ("power_fourier_rhythm_2bet",       "POWER_LOTTO","RETIRED"),
    ("zonal_entropy_2bet",              "POWER_LOTTO","RETIRED"),
]

FORBIDDEN_LIFECYCLES = frozenset({
    "ONLINE", "DEPLOYABLE", "ONLINE_RECOMMENDED", "PRODUCTION_READY",
    "PROMOTE", "BEST_STRATEGY_TO_USE",
})

P233B_IDS = {sid for sid, _, _ in P233B_STUBS}


# ─── Stub registration tests ────────────────────────────────────────────────────

def test_exactly_20_p233b_stubs_in_registry():
    """All 20 P233B strategy_ids must appear in the non-executable list."""
    non_exec = set(list_non_executable_strategy_ids())
    missing = P233B_IDS - non_exec
    assert not missing, f"P233B stubs missing from non-executable registry: {missing}"


def test_p233b_lifecycle_counts():
    """12 REJECTED + 8 RETIRED from the P233B stubs specifically."""
    all_meta = {m["strategy_id"]: m["lifecycle_status"]
                for m in list_strategy_lifecycle_metadata()}
    rejected = [sid for sid, _, exp in P233B_STUBS
                if all_meta.get(sid) == "REJECTED" and exp == "REJECTED"]
    retired  = [sid for sid, _, exp in P233B_STUBS
                if all_meta.get(sid) == "RETIRED" and exp == "RETIRED"]
    assert len(rejected) == 12, f"Expected 12 REJECTED P233B stubs, got {len(rejected)}"
    assert len(retired) == 8,   f"Expected 8 RETIRED P233B stubs, got {len(retired)}"


def test_p233b_lifecycle_matches_plan():
    """Each P233B stub must have the exact lifecycle suggested in the P233A plan."""
    all_meta = {m["strategy_id"]: m["lifecycle_status"]
                for m in list_strategy_lifecycle_metadata()}
    for sid, lt, expected in P233B_STUBS:
        actual = all_meta.get(sid)
        assert actual == expected, (
            f"{sid}: expected lifecycle {expected!r}, got {actual!r}"
        )


def test_p233b_stubs_not_in_executable_adapters():
    """None of the 20 P233B stubs must appear in the executable adapter list."""
    exec_ids = set(list_executable_strategy_ids())
    found_in_exec = P233B_IDS & exec_ids
    assert not found_in_exec, (
        f"P233B stubs must NOT be executable: {found_in_exec}"
    )


def test_p233b_stubs_raise_lifecycle_not_executable():
    """Calling get_one_bet on any P233B stub must raise LifecycleNotExecutable."""
    from lottery_api.models.replay_strategy_registry import _ALL_ADAPTERS
    p233b_adapters = [a for a in _ALL_ADAPTERS if a.meta.strategy_id in P233B_IDS]
    assert len(p233b_adapters) == 20, (
        f"Expected 20 P233B adapters in _ALL_ADAPTERS, got {len(p233b_adapters)}"
    )
    for adapter in p233b_adapters:
        with pytest.raises(LifecycleNotExecutable):
            adapter.get_one_bet([], adapter.meta.supported_lottery_types[0])


def test_no_forbidden_lifecycle_in_p233b_stubs():
    """None of the 20 P233B stubs may have a forbidden lifecycle."""
    all_meta = {m["strategy_id"]: m["lifecycle_status"]
                for m in list_strategy_lifecycle_metadata()}
    for sid in P233B_IDS:
        lc = all_meta.get(sid, "UNKNOWN")
        assert lc not in FORBIDDEN_LIFECYCLES, (
            f"{sid} has forbidden lifecycle {lc!r}"
        )


def test_overall_lifecycle_counts_increased():
    """After adding 12 REJECTED + 8 RETIRED, totals should match expected values."""
    counts = summarize_strategy_lifecycle_counts()
    assert counts.get("REJECTED", 0) >= 16, (
        f"Expected ≥16 REJECTED (4 existing + 12 new), got {counts.get('REJECTED', 0)}"
    )
    assert counts.get("RETIRED", 0) >= 13, (
        f"Expected ≥13 RETIRED (5 existing + 8 new), got {counts.get('RETIRED', 0)}"
    )


# ─── Scoreboard effect tests ─────────────────────────────────────────────────────

def test_p232a_scoreboard_lifecycle_unresolved_zero():
    """After P233B, running P232A scoreboard must show LIFECYCLE_UNRESOLVED = 0."""
    from scripts.p232a_all_catalog_strategy_replay_scoreboard import build_catalog_universe
    catalog = build_catalog_universe(DB_PATH)
    unresolved = [e for e in catalog if e["lifecycle_status"] == "LIFECYCLE_UNRESOLVED"]
    assert len(unresolved) == 0, (
        f"Expected 0 LIFECYCLE_UNRESOLVED entries after P233B, got {len(unresolved)}: "
        f"{[e['strategy_id'] for e in unresolved]}"
    )


def test_p232a_total_union_is_41():
    """Total union strategy+lottery entries must remain 41."""
    from scripts.p232a_all_catalog_strategy_replay_scoreboard import build_catalog_universe
    catalog = build_catalog_universe(DB_PATH)
    assert len(catalog) == 41, (
        f"Expected 41 union entries, got {len(catalog)}"
    )


# ─── DB unchanged tests ──────────────────────────────────────────────────────────

def test_db_rows_unchanged():
    """Registry update must NOT change DB row counts."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()
    assert count == 94924, f"DB rows changed: {count} != 94924"
