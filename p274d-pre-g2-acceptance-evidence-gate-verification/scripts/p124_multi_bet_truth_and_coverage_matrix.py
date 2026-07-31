#!/usr/bin/env python3
"""
P124: Multi-Bet Replay Truth Model + Coverage Matrix
=====================================================
Read-only analysis. Does NOT write to lottery_v2.db.
Does NOT insert replay rows. Does NOT promote strategies.

Produces:
  outputs/replay/p124_multi_bet_truth_and_coverage_matrix_20260528.json
  docs/replay/p124_multi_bet_truth_and_coverage_matrix_20260528.md
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_JSON = (
    PROJECT_ROOT
    / "outputs"
    / "replay"
    / "p124_multi_bet_truth_and_coverage_matrix_20260528.json"
)
OUTPUT_MD = (
    PROJECT_ROOT
    / "docs"
    / "replay"
    / "p124_multi_bet_truth_and_coverage_matrix_20260528.md"
)

# ── Expected invariants ───────────────────────────────────────────────────────
EXPECTED_REPLAY_ROWS = 54462
EXPECTED_3STAR = {"count": 4179, "max_draw": "115000106"}
EXPECTED_4STAR = {"count": 2922, "max_draw": "115000103"}
EXPECTED_POWER_LOTTO = {"count": 1913, "max_draw": "115000041"}

# ── Truth model label definitions ─────────────────────────────────────────────
TRUTH_MODEL_LABELS = {
    "native_multi_bet": (
        "Strategy has an adapter that natively produces N bets for the specified bet_count, "
        "AND replay rows exist that store all N bets honestly (each distinguishable from first-bet-only rows)."
    ),
    "first_bet_only_fallback": (
        "Strategy is named or marketed as N-bet, but current replay rows store only bet-1. "
        "The remaining bets are not recorded in the DB."
    ),
    "adapter_missing": (
        "Strategy is implemented but no adapter currently produces replay rows for this bet_count."
    ),
    "already_covered": (
        "This bet_count is the strategy's native bet count and replay rows are present and honest."
    ),
    "unsupported": (
        "Strategy logically cannot produce this bet_count "
        "(e.g. a 2-bet strategy cannot expand to 5-bet without fabrication)."
    ),
    "rejected": (
        "Strategy was rejected by prior governance and must not be expanded."
    ),
    "retired": (
        "Strategy was retired; recorded by id only, not expanded to 1-5 bet columns."
    ),
    "source_unknown": (
        "Strategy or lottery is currently source_unknown (e.g. 4_STAR); analysis is forbidden."
    ),
    "fabrication_prohibited": (
        "Producing rows for this bet_count would require fabricated bets. "
        "This label MUST NOT be promoted to any other label inside this task."
    ),
}

# ── P112 quality labels ────────────────────────────────────────────────────────
P112_QUALITY = {
    ("POWER_LOTTO", "cold_complement_2bet"): "fallback_equivalent",
    ("POWER_LOTTO", "fourier30_markov30_2bet"): "watchlist",
    ("POWER_LOTTO", "fourier_rhythm_3bet"): "watchlist",
    ("POWER_LOTTO", "midfreq_fourier_2bet"): "watchlist",
    ("POWER_LOTTO", "midfreq_fourier_mk_3bet"): "prediction_helpful",
    ("POWER_LOTTO", "power_fourier_rhythm_2bet"): "watchlist",
    ("POWER_LOTTO", "power_orthogonal_5bet"): "watchlist",
    ("POWER_LOTTO", "power_precision_3bet"): "watchlist",
    ("POWER_LOTTO", "pp3_freqort_4bet"): "prediction_helpful",
    ("POWER_LOTTO", "zonal_entropy_2bet"): "fallback_equivalent",
    ("DAILY_539", "539_3bet_orthogonal"): "watchlist",
    ("DAILY_539", "acb_1bet"): "watchlist",
    ("DAILY_539", "acb_markov_midfreq"): "fallback_equivalent",
    ("DAILY_539", "acb_markov_midfreq_3bet"): "watchlist",
    ("DAILY_539", "acb_single_539"): "watchlist",
    ("DAILY_539", "daily539_f4cold"): "watchlist",
    ("DAILY_539", "daily539_f4cold_3bet"): "watchlist",
    ("DAILY_539", "daily539_f4cold_5bet"): "watchlist",
    ("DAILY_539", "daily539_markov_cold"): "fallback_equivalent",
    ("DAILY_539", "markov_1bet_539"): "fallback_equivalent",
    ("DAILY_539", "midfreq_acb_2bet"): "watchlist",
    ("DAILY_539", "midfreq_fourier_2bet"): "watchlist",
    ("DAILY_539", "p0b_539_3bet_f_cold_fmid"): "watchlist",
    ("DAILY_539", "p0c_539_3bet_f_cold_x2"): "watchlist",
    ("DAILY_539", "zone_gap_3bet_539"): "sub_baseline",
    ("BIG_LOTTO", "bet2_fourier_expansion_biglotto"): "sub_baseline",
    ("BIG_LOTTO", "biglotto_deviation_2bet"): "watchlist",
    ("BIG_LOTTO", "biglotto_echo_aware_3bet"): "fallback_equivalent",
    ("BIG_LOTTO", "biglotto_triple_strike"): "fallback_equivalent",
    ("BIG_LOTTO", "biglotto_ts3_markov_4bet_w30"): "sub_baseline",
    ("BIG_LOTTO", "cold_complement_biglotto"): "fallback_equivalent",
    ("BIG_LOTTO", "coldpool15_biglotto"): "fallback_equivalent",
    ("BIG_LOTTO", "fourier30_markov30_biglotto"): "sub_baseline",
    ("BIG_LOTTO", "markov_2bet_biglotto"): "fallback_equivalent",
    ("BIG_LOTTO", "markov_single_biglotto"): "fallback_equivalent",
    ("BIG_LOTTO", "ts3_regime_3bet"): "sub_baseline",
}

# ── Actual replay rows per strategy×lottery (from DB snapshot) ────────────────
REPLAY_ROWS_DB = {
    ("DAILY_539", "539_3bet_orthogonal"): 1500,
    ("DAILY_539", "acb_1bet"): 1500,
    ("DAILY_539", "acb_markov_midfreq"): 1500,
    ("DAILY_539", "acb_markov_midfreq_3bet"): 1500,
    ("DAILY_539", "acb_single_539"): 1500,
    ("BIG_LOTTO", "bet2_fourier_expansion_biglotto"): 1500,
    ("BIG_LOTTO", "biglotto_deviation_2bet"): 1570,
    ("BIG_LOTTO", "biglotto_echo_aware_3bet"): 1500,
    ("BIG_LOTTO", "biglotto_triple_strike"): 1570,
    ("BIG_LOTTO", "biglotto_ts3_markov_4bet_w30"): 1500,
    ("POWER_LOTTO", "cold_complement_2bet"): 1500,
    ("BIG_LOTTO", "cold_complement_biglotto"): 1500,
    ("BIG_LOTTO", "coldpool15_biglotto"): 1500,
    ("DAILY_539", "daily539_f4cold"): 1590,
    ("DAILY_539", "daily539_f4cold_3bet"): 1500,
    ("DAILY_539", "daily539_f4cold_5bet"): 1500,
    ("DAILY_539", "daily539_markov_cold"): 1590,
    ("POWER_LOTTO", "fourier30_markov30_2bet"): 1501,
    ("BIG_LOTTO", "fourier30_markov30_biglotto"): 1500,
    ("POWER_LOTTO", "fourier_rhythm_3bet"): 1501,
    ("DAILY_539", "markov_1bet_539"): 1500,
    ("BIG_LOTTO", "markov_2bet_biglotto"): 1500,
    ("BIG_LOTTO", "markov_single_biglotto"): 1500,
    ("DAILY_539", "midfreq_acb_2bet"): 1500,
    ("DAILY_539", "midfreq_fourier_2bet"): 1500,
    ("POWER_LOTTO", "midfreq_fourier_2bet"): 1500,
    ("POWER_LOTTO", "midfreq_fourier_mk_3bet"): 1500,
    ("DAILY_539", "p0b_539_3bet_f_cold_fmid"): 1500,
    ("DAILY_539", "p0c_539_3bet_f_cold_x2"): 1500,
    ("POWER_LOTTO", "power_fourier_rhythm_2bet"): 1500,
    ("POWER_LOTTO", "power_orthogonal_5bet"): 1570,
    ("POWER_LOTTO", "power_precision_3bet"): 1570,
    ("POWER_LOTTO", "pp3_freqort_4bet"): 1500,
    ("BIG_LOTTO", "ts3_regime_3bet"): 1500,
    ("POWER_LOTTO", "zonal_entropy_2bet"): 1500,
    ("DAILY_539", "zone_gap_3bet_539"): 1500,
}

# ── Strategy definitions ───────────────────────────────────────────────────────
STRATEGIES = [
    # ── DAILY_539 ──────────────────────────────────────────────────────────────
    {
        "strategy_id": "acb_1bet",
        "lottery_type": "DAILY_539",
        "native_bet_count": 1,
        "lifecycle": "PRODUCTION",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "1-bet strategy; already_covered at bet-1",
    },
    {
        "strategy_id": "acb_markov_midfreq",
        "lottery_type": "DAILY_539",
        "native_bet_count": 1,
        "lifecycle": "NOT_IN_P0",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "1-bet strategy; already_covered at bet-1",
    },
    {
        "strategy_id": "acb_single_539",
        "lottery_type": "DAILY_539",
        "native_bet_count": 1,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected strategy",
    },
    {
        "strategy_id": "acb_markov_midfreq_3bet",
        "lottery_type": "DAILY_539",
        "native_bet_count": 3,
        "lifecycle": "PRODUCTION",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores bet-1 (ACB) only; bets 2-3 not recorded",
    },
    {
        "strategy_id": "539_3bet_orthogonal",
        "lottery_type": "DAILY_539",
        "native_bet_count": 3,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected; DB stores bet-1 only",
    },
    {
        "strategy_id": "daily539_f4cold",
        "lottery_type": "DAILY_539",
        "native_bet_count": 1,
        "lifecycle": "PRODUCTION",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "1-bet strategy; already_covered at bet-1",
    },
    {
        "strategy_id": "p0b_539_3bet_f_cold_fmid",
        "lottery_type": "DAILY_539",
        "native_bet_count": 3,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected; DB stores bet-1 only",
    },
    {
        "strategy_id": "p0c_539_3bet_f_cold_x2",
        "lottery_type": "DAILY_539",
        "native_bet_count": 3,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected; DB stores bet-1 only",
    },
    {
        "strategy_id": "markov_1bet_539",
        "lottery_type": "DAILY_539",
        "native_bet_count": 1,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected 1-bet strategy",
    },
    {
        "strategy_id": "daily539_markov_cold",
        "lottery_type": "DAILY_539",
        "native_bet_count": 1,
        "lifecycle": "PRODUCTION",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "1-bet strategy; already_covered at bet-1",
    },
    {
        "strategy_id": "zone_gap_3bet_539",
        "lottery_type": "DAILY_539",
        "native_bet_count": 3,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected; DB stores bet-1 only",
    },
    {
        "strategy_id": "midfreq_acb_2bet",
        "lottery_type": "DAILY_539",
        "native_bet_count": 2,
        "lifecycle": "PRODUCTION",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores bet-1 (MidFreq) only; bet-2 (ACB) not recorded",
    },
    {
        "strategy_id": "midfreq_fourier_2bet",
        "lottery_type": "DAILY_539",
        "native_bet_count": 2,
        "lifecycle": "PRODUCTION",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores bet-1 (MidFreq) only; bet-2 (Fourier) not recorded",
    },
    {
        "strategy_id": "daily539_f4cold_3bet",
        "lottery_type": "DAILY_539",
        "native_bet_count": 3,
        "lifecycle": "PRODUCTION",
        "adapter_status": "available",
        "has_tier_b_adapter": True,
        "adapter_class": "Daily539F4Cold3BetAdapter",
        "db_storage_note": "P94 Tier-B adapter exists; currently stores bet-1 only per row",
    },
    {
        "strategy_id": "daily539_f4cold_5bet",
        "lottery_type": "DAILY_539",
        "native_bet_count": 5,
        "lifecycle": "PRODUCTION",
        "adapter_status": "available",
        "has_tier_b_adapter": True,
        "adapter_class": "Daily539F4Cold5BetAdapter",
        "db_storage_note": "P94 Tier-B adapter exists; currently stores bet-1 only per row",
    },
    # ── BIG_LOTTO ──────────────────────────────────────────────────────────────
    {
        "strategy_id": "ts3_regime_3bet",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 1,
        "lifecycle": "PRODUCTION",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "Named 3bet but natively generates 1 bet; row-backed only",
    },
    {
        "strategy_id": "biglotto_deviation_2bet",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 2,
        "lifecycle": "PRODUCTION",
        "adapter_status": "partial",
        "has_tier_b_adapter": False,
        "adapter_func": "deviation_complement_2bet",
        "db_storage_note": "Adapter exists; stores 1 bet per row (first_bet_only_fallback)",
    },
    {
        "strategy_id": "biglotto_triple_strike",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 3,
        "lifecycle": "PRODUCTION",
        "adapter_status": "partial",
        "has_tier_b_adapter": False,
        "adapter_func": "generate_triple_strike",
        "db_storage_note": "Adapter exists; stores 1 bet per row (first_bet_only_fallback)",
    },
    {
        "strategy_id": "biglotto_echo_aware_3bet",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 3,
        "lifecycle": "TIERB_DRYRUN_VALIDATED",
        "adapter_status": "available",
        "has_tier_b_adapter": True,
        "adapter_func": "echo_aware_mixed_3bet",
        "db_storage_note": "P94 Tier-B adapter exists; currently stores bet-1 only per row",
    },
    {
        "strategy_id": "biglotto_ts3_markov_4bet_w30",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 4,
        "lifecycle": "TIERB_DRYRUN_VALIDATED",
        "adapter_status": "available",
        "has_tier_b_adapter": True,
        "adapter_func": "generate_ts3_markov_4bet",
        "db_storage_note": "P94 Tier-B adapter exists; currently stores bet-1 only per row",
    },
    {
        "strategy_id": "cold_complement_biglotto",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 1,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected (COVERAGE_ONLY_L91)",
    },
    {
        "strategy_id": "coldpool15_biglotto",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 1,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected (COVERAGE_ONLY_L91)",
    },
    {
        "strategy_id": "fourier30_markov30_biglotto",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 1,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected (COVERAGE_ONLY_L91)",
    },
    {
        "strategy_id": "markov_2bet_biglotto",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 1,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected (COVERAGE_ONLY_L91); named 2bet but native=1",
    },
    {
        "strategy_id": "markov_single_biglotto",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 1,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected (COVERAGE_ONLY_L91)",
    },
    {
        "strategy_id": "bet2_fourier_expansion_biglotto",
        "lottery_type": "BIG_LOTTO",
        "native_bet_count": 1,
        "lifecycle": "REJECTED",
        "adapter_status": "rejected",
        "has_tier_b_adapter": False,
        "db_storage_note": "Rejected (COVERAGE_ONLY_L91); named bet2 but native=1",
    },
    # ── POWER_LOTTO ────────────────────────────────────────────────────────────
    {
        "strategy_id": "power_precision_3bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 3,
        "lifecycle": "ONLINE",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bet-2 and bet-3 not recorded",
    },
    {
        "strategy_id": "power_orthogonal_5bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 5,
        "lifecycle": "ONLINE",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bets 2-5 not recorded",
    },
    {
        "strategy_id": "fourier_rhythm_3bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 3,
        "lifecycle": "ONLINE",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bet-2 and bet-3 not recorded",
    },
    {
        "strategy_id": "power_fourier_rhythm_2bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 2,
        "lifecycle": "DRY_RUN",
        "adapter_status": "available",
        "has_tier_b_adapter": True,
        "db_storage_note": "P94 Tier-B adapter exists; currently stores bet-1 only per row",
    },
    {
        "strategy_id": "zonal_entropy_2bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 2,
        "lifecycle": "DRY_RUN",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bet-2 not recorded",
    },
    {
        "strategy_id": "pp3_freqort_4bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 4,
        "lifecycle": "DRY_RUN",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bets 2-4 not recorded",
    },
    {
        "strategy_id": "midfreq_fourier_mk_3bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 3,
        "lifecycle": "DRY_RUN",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bet-2 and bet-3 not recorded",
    },
    {
        "strategy_id": "midfreq_fourier_2bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 2,
        "lifecycle": "DRY_RUN",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bet-2 not recorded (cross-game from DAILY_539)",
    },
    {
        "strategy_id": "cold_complement_2bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 2,
        "lifecycle": "DRY_RUN",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bet-2 not recorded",
    },
    {
        "strategy_id": "fourier30_markov30_2bet",
        "lottery_type": "POWER_LOTTO",
        "native_bet_count": 2,
        "lifecycle": "DRY_RUN",
        "adapter_status": "missing",
        "has_tier_b_adapter": False,
        "db_storage_note": "DB stores 1 bet per row; bet-2 not recorded",
    },
]


def _bet_label(strategy: dict, bet_n: int) -> str:
    """Return the truth-model label for bet_N of this strategy."""
    native = strategy["native_bet_count"]
    adapter_status = strategy["adapter_status"]

    if adapter_status == "rejected":
        return "rejected"

    if bet_n > native:
        return "unsupported"

    # bet_n <= native
    if native == 1 and bet_n == 1:
        return "already_covered"

    # Multi-bet strategy: all bets currently stored as first-bet-only
    return "first_bet_only_fallback"


def _proposed_action(strategy: dict) -> str:
    """Return proposed_next_action_type."""
    adapter_status = strategy["adapter_status"]
    native = strategy["native_bet_count"]

    if adapter_status == "rejected":
        return "no_action"
    if native == 1:
        return "no_action"
    if strategy.get("has_tier_b_adapter"):
        return "controlled_apply"
    if adapter_status == "partial":
        return "relabel_first_bet_only"
    return "adapter_build"


def _blocker(strategy: dict) -> str:
    """Return blocker description."""
    adapter_status = strategy["adapter_status"]
    lifecycle = strategy["lifecycle"]
    native = strategy["native_bet_count"]

    if adapter_status == "rejected":
        return f"Rejected by governance (lifecycle={lifecycle}); expansion forbidden"
    if native == 1:
        return "1-bet strategy; no multi-bet expansion needed"
    if strategy.get("has_tier_b_adapter"):
        return (
            "P94 Tier-B adapter available but currently writes 1 row/draw (bet-1 only); "
            "need controlled_apply to record all N bets per draw"
        )
    if adapter_status == "partial":
        return (
            "Adapter function exists but replay pipeline writes only bet-1 per draw; "
            "need adapter upgrade to expose get_all_bets()"
        )
    return (
        f"No multi-bet adapter; strategy natively has {native} bets but only bet-1 stored; "
        "need new ReplayStrategyAdapter subclass"
    )


def _replay_rows_per_bet_str(strategy: dict) -> str:
    """Return a string like '1500/0/0/0/0' showing which bet slots have rows."""
    total = REPLAY_ROWS_DB.get((strategy["lottery_type"], strategy["strategy_id"]), 0)
    parts = [str(total)] + ["0", "0", "0", "0"]
    return "/".join(parts)


def build_coverage_matrix() -> list:
    """Build the full coverage matrix."""
    matrix = []
    for s in STRATEGIES:
        sid = s["strategy_id"]
        lt = s["lottery_type"]
        adapter_status = s["adapter_status"]
        total_rows = REPLAY_ROWS_DB.get((lt, sid), 0)

        if adapter_status == "rejected":
            quality = "coverage_only"
        else:
            quality = P112_QUALITY.get((lt, sid), "unknown")

        row = {
            "strategy_id": sid,
            "lottery_type": lt,
            "native_bet_count": s["native_bet_count"],
            "adapter_status": adapter_status,
            "bet_1_label": _bet_label(s, 1),
            "bet_2_label": _bet_label(s, 2),
            "bet_3_label": _bet_label(s, 3),
            "bet_4_label": _bet_label(s, 4),
            "bet_5_label": _bet_label(s, 5),
            "replay_rows_total": total_rows,
            "replay_rows_per_bet": _replay_rows_per_bet_str(s),
            "quality_label": quality,
            "blocker": _blocker(s),
            "proposed_next_action_type": _proposed_action(s),
        }
        matrix.append(row)
    return matrix


def db_preflight() -> dict:
    """Run read-only DB checks. Returns snapshot dict. Raises on invariant drift."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    replay_rows = c.fetchone()[0]

    c.execute(
        "SELECT lottery_type, COUNT(*), MAX(CAST(draw AS INTEGER)) "
        "FROM draws WHERE lottery_type IN ('3_STAR','4_STAR','POWER_LOTTO','BIG_LOTTO','DAILY_539') "
        "GROUP BY lottery_type"
    )
    draws_data = {row[0]: {"count": row[1], "max_draw": str(row[2])} for row in c.fetchall()}
    conn.close()

    snapshot = {
        "replay_rows": replay_rows,
        "3_STAR": draws_data.get("3_STAR", {}),
        "4_STAR": draws_data.get("4_STAR", {}),
        "POWER_LOTTO": draws_data.get("POWER_LOTTO", {}),
        "BIG_LOTTO": draws_data.get("BIG_LOTTO", {}),
        "DAILY_539": draws_data.get("DAILY_539", {}),
    }

    errors = []
    if replay_rows != EXPECTED_REPLAY_ROWS:
        errors.append(f"replay_rows={replay_rows} expected={EXPECTED_REPLAY_ROWS}")
    star3 = draws_data.get("3_STAR", {})
    if (
        star3.get("count") != EXPECTED_3STAR["count"]
        or star3.get("max_draw") != EXPECTED_3STAR["max_draw"]
    ):
        errors.append(f"3_STAR drift: got {star3} expected {EXPECTED_3STAR}")
    star4 = draws_data.get("4_STAR", {})
    if (
        star4.get("count") != EXPECTED_4STAR["count"]
        or star4.get("max_draw") != EXPECTED_4STAR["max_draw"]
    ):
        errors.append(f"4_STAR drift: got {star4} expected {EXPECTED_4STAR}")
    pl = draws_data.get("POWER_LOTTO", {})
    if (
        pl.get("count") != EXPECTED_POWER_LOTTO["count"]
        or pl.get("max_draw") != EXPECTED_POWER_LOTTO["max_draw"]
    ):
        errors.append(f"POWER_LOTTO drift: got {pl} expected {EXPECTED_POWER_LOTTO}")

    if errors:
        raise RuntimeError("DB invariant drift: " + "; ".join(errors))

    return snapshot


def build_summary(matrix: list) -> dict:
    action_counts: dict = {}
    label_counts: dict = {}
    for row in matrix:
        a = row["proposed_next_action_type"]
        action_counts[a] = action_counts.get(a, 0) + 1
        for b in range(1, 6):
            lbl = row[f"bet_{b}_label"]
            label_counts[lbl] = label_counts.get(lbl, 0) + 1

    first_bet_only_strategies = sum(
        1 for r in matrix
        if r["adapter_status"] not in ("rejected",) and r["native_bet_count"] > 1
    )
    adapter_build_needed = sum(
        1 for r in matrix if r["proposed_next_action_type"] == "adapter_build"
    )
    controlled_apply_ready = sum(
        1 for r in matrix if r["proposed_next_action_type"] == "controlled_apply"
    )
    rejected_count = sum(1 for r in matrix if r["adapter_status"] == "rejected")

    return {
        "total_strategy_lottery_pairs": len(matrix),
        "rejected_count": rejected_count,
        "first_bet_only_multi_bet_strategies": first_bet_only_strategies,
        "native_multi_bet_count": 0,
        "adapter_build_needed": adapter_build_needed,
        "controlled_apply_ready": controlled_apply_ready,
        "action_counts": action_counts,
        "bet_label_counts": label_counts,
        "key_finding": (
            "All 36 implemented strategy×lottery pairs store exactly 1 predicted_numbers list per row. "
            "Zero strategies currently achieve native_multi_bet storage. "
            f"{first_bet_only_strategies} multi-bet strategies use first_bet_only_fallback. "
            f"{controlled_apply_ready} have Tier-B adapters ready for controlled_apply. "
            f"{adapter_build_needed} require new adapter builds."
        ),
    }


def write_json(snapshot: dict, matrix: list) -> None:
    summary = build_summary(matrix)
    rejected_ids = [s["strategy_id"] for s in STRATEGIES if s["adapter_status"] == "rejected"]
    artifact = {
        "task_id": "P124",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY",
        "db_snapshot": snapshot,
        "truth_model": {
            "labels": TRUTH_MODEL_LABELS,
            "conventions": {
                "one_row_per_strategy_draw": True,
                "predicted_numbers_stores_single_bet": True,
                "power_lotto_special_field": (
                    "POWER_LOTTO uses predicted_special field for bonus ball (1-8). "
                    "Some strategies populate it (pp3_freqort_4bet, fourier30_markov30_2bet); "
                    "others do not (fourier_rhythm_3bet, power_precision_3bet, power_orthogonal_5bet). "
                    "Replay scoring must handle NULL predicted_special gracefully."
                ),
                "native_multi_bet_requirement": (
                    "To qualify as native_multi_bet: (1) adapter must expose all N bets via "
                    "get_all_bets() or equivalent method, AND (2) replay storage must record "
                    "each of the N bets in a way distinguishable from first-bet-only rows "
                    "(e.g. separate rows per bet, or a JSON array of N sublists)."
                ),
                "first_bet_only_dominant": (
                    "All 36 strategy×lottery_type pairs currently store exactly 1 list "
                    "per row in predicted_numbers. No strategy currently qualifies as "
                    "native_multi_bet. This is the dominant storage convention as of P94."
                ),
                "tier_b_adapter_status": (
                    "Five strategies have P94 Tier-B adapters (daily539_f4cold_3bet, "
                    "daily539_f4cold_5bet, biglotto_echo_aware_3bet, biglotto_ts3_markov_4bet_w30, "
                    "power_fourier_rhythm_2bet) that CAN generate multiple bets, "
                    "but current replay rows store only bet-1. "
                    "These are labelled adapter_status=available and are candidates "
                    "for controlled_apply to record all N bets."
                ),
            },
        },
        "coverage_matrix": matrix,
        "excluded_listings": {
            "rejected": rejected_ids,
            "retired": [],
            "source_unknown": ["4_STAR"],
            "notes": {
                "4_STAR": (
                    "4_STAR lottery type is source_unknown per P105-P107 governance. "
                    "Analysis, backtest, and adapter build are forbidden for this lottery type."
                ),
                "3_STAR": (
                    "3_STAR is evaluation_only_partial per P105-P107; "
                    "included in draws snapshot but not in coverage matrix expansion."
                ),
            },
        },
        "summary": summary,
        "governance": {
            "db_writes": 0,
            "replay_rows_before": snapshot["replay_rows"],
            "replay_rows_after": snapshot["replay_rows"],
            "no_strategy_promotion": True,
            "no_lifecycle_mutation": True,
            "no_registry_mutation": True,
            "no_4star_backtest": True,
            "no_special3_p108_rerun": True,
            "no_scheduler_install": True,
            "no_p117_p118_execution": True,
        },
        "next_task": "P125_ADAPTER_GAP_PLAN",
    }
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
    print(f"[P124] JSON written: {OUTPUT_JSON}")


def write_md(snapshot: dict, matrix: list) -> None:
    summary = build_summary(matrix)
    rejected_count = summary["rejected_count"]
    first_bet_only = summary["first_bet_only_multi_bet_strategies"]
    controlled = summary["controlled_apply_ready"]
    adapter_build = summary["adapter_build_needed"]
    total = summary["total_strategy_lottery_pairs"]

    lines = [
        "# P124 Multi-Bet Replay Truth Model + Coverage Matrix",
        "",
        f"**Generated:** {datetime.now(timezone.utc).isoformat()}  ",
        "**Task ID:** P124  ",
        "**Classification:** P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        "**Key finding:** All 36 implemented strategy×lottery pairs store exactly "
        "**1 predicted_numbers list per row**. "
        "Zero strategies currently achieve `native_multi_bet` storage.",
        "",
        f"Of {total} strategy×lottery pairs in the matrix:",
        f"- {rejected_count} are rejected (expansion forbidden)",
        f"- {first_bet_only} multi-bet strategies use `first_bet_only_fallback`",
        f"- {controlled} have Tier-B adapters ready for `controlled_apply`",
        f"- {adapter_build} require new adapter builds",
        "",
        "**CEO mandate status:** Historical replay of all implemented strategies across all "
        "lottery types and 1-5 bet counts cannot be achieved without first resolving the "
        "`first_bet_only_fallback` gap for multi-bet strategies.",
        "",
        "---",
        "",
        "## DB Snapshot (Read-Only Pre-Flight)",
        "",
        "| Key | Value |",
        "|-----|-------|",
        f"| strategy_prediction_replays | {snapshot['replay_rows']} |",
        f"| 3_STAR draws | {snapshot['3_STAR'].get('count')} (max {snapshot['3_STAR'].get('max_draw')}) |",
        f"| 4_STAR draws | {snapshot['4_STAR'].get('count')} (max {snapshot['4_STAR'].get('max_draw')}) |",
        f"| POWER_LOTTO draws | {snapshot['POWER_LOTTO'].get('count')} (max {snapshot['POWER_LOTTO'].get('max_draw')}) |",
        f"| BIG_LOTTO draws | {snapshot['BIG_LOTTO'].get('count')} (max {snapshot['BIG_LOTTO'].get('max_draw')}) |",
        f"| DAILY_539 draws | {snapshot['DAILY_539'].get('count')} (max {snapshot['DAILY_539'].get('max_draw')}) |",
        "",
        "---",
        "",
        "## Truth Model",
        "",
        "### Storage Convention (Current)",
        "",
        "- **One replay row per strategy per draw** is the dominant convention.",
        "- `predicted_numbers` stores a **single list** of ball numbers (one bet) per row.",
        "- All 36 strategy×lottery_type pairs follow this convention as of P94.",
        "- **No strategy currently achieves `native_multi_bet` storage.**",
        "",
        "### POWER_LOTTO Special Number Semantics",
        "",
        "- `predicted_special` field stores the bonus ball (1-8).",
        "- Some strategies populate it (`pp3_freqort_4bet`, `fourier30_markov30_2bet`).",
        "- Others leave it NULL (`fourier_rhythm_3bet`, `power_precision_3bet`, `power_orthogonal_5bet`).",
        "- Replay scoring must handle NULL `predicted_special` gracefully.",
        "",
        "### Native Multi-Bet Requirement",
        "",
        "For a strategy to qualify as `native_multi_bet`:",
        "1. Adapter must expose all N bets (e.g. `get_all_bets()` method), **AND**",
        "2. Replay storage must record each of the N bets distinguishably",
        "   (e.g. separate rows per bet, or a JSON array of N sublists).",
        "",
        "### Label Definitions",
        "",
        "| Label | Meaning |",
        "|-------|---------|",
    ]
    for label, desc in TRUTH_MODEL_LABELS.items():
        short = desc[:100] + ("..." if len(desc) > 100 else "")
        lines.append(f"| `{label}` | {short} |")

    for lt_name in ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]:
        lines += [
            "",
            "---",
            "",
            f"## Coverage Matrix — {lt_name}",
            "",
            "| strategy_id | native | adapter | bet1 | bet2 | bet3 | bet4 | bet5 | rows | quality | next_action |",
            "|-------------|--------|---------|------|------|------|------|------|------|---------|-------------|",
        ]
        for row in matrix:
            if row["lottery_type"] != lt_name:
                continue
            lines.append(
                f"| {row['strategy_id']} | {row['native_bet_count']} | {row['adapter_status']}"
                f" | {row['bet_1_label']} | {row['bet_2_label']} | {row['bet_3_label']}"
                f" | {row['bet_4_label']} | {row['bet_5_label']}"
                f" | {row['replay_rows_total']} | {row['quality_label']}"
                f" | {row['proposed_next_action_type']} |"
            )

    rejected_ids = [s["strategy_id"] for s in STRATEGIES if s["adapter_status"] == "rejected"]
    lines += [
        "",
        "---",
        "",
        "## Excluded Listings",
        "",
        "### Rejected Strategies (no 1-5 bet expansion)",
        "",
    ]
    for sid in rejected_ids:
        lines.append(f"- `{sid}`")

    lines += [
        "",
        "### Source-Unknown (4_STAR)",
        "",
        "- `4_STAR` lottery is `source_unknown` per P105-P107. Analysis and adapter build forbidden.",
        "",
        "---",
        "",
        "## Gap Severity Analysis",
        "",
        "### Priority 1 — Controlled Apply Ready (Tier-B adapters available)",
        "",
        "| strategy_id | lottery_type | native_bets | quality |",
        "|-------------|-------------|------------|---------|",
    ]
    for row in matrix:
        if row["proposed_next_action_type"] == "controlled_apply":
            lines.append(
                f"| {row['strategy_id']} | {row['lottery_type']}"
                f" | {row['native_bet_count']} | {row['quality_label']} |"
            )

    lines += [
        "",
        "### Priority 2 — Adapter Build Required",
        "",
        "| strategy_id | lottery_type | native_bets | quality |",
        "|-------------|-------------|------------|---------|",
    ]
    for row in matrix:
        if row["proposed_next_action_type"] == "adapter_build":
            lines.append(
                f"| {row['strategy_id']} | {row['lottery_type']}"
                f" | {row['native_bet_count']} | {row['quality_label']} |"
            )

    lines += [
        "",
        "### Priority 3 — Relabel First-Bet-Only (partial adapters)",
        "",
        "| strategy_id | lottery_type | native_bets | quality |",
        "|-------------|-------------|------------|---------|",
    ]
    for row in matrix:
        if row["proposed_next_action_type"] == "relabel_first_bet_only":
            lines.append(
                f"| {row['strategy_id']} | {row['lottery_type']}"
                f" | {row['native_bet_count']} | {row['quality_label']} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Proposed P125 Follow-Up",
        "",
        "**Recommended next task:** `P125_ADAPTER_GAP_PLAN`",
        "",
        "P125 should:",
        "1. Plan controlled_apply passes for the 5 Tier-B adapter-ready strategies",
        "   (closes highest-value gap with lowest implementation risk).",
        "2. Define adapter build spec for remaining multi-bet strategies.",
        "3. Specify the storage schema change needed: each bet gets its own replay row",
        "   OR predicted_numbers stores a JSON array of N sublists.",
        "4. Confirm POWER_LOTTO predicted_special handling before any apply.",
        "",
        "---",
        "",
        "## Governance Confirmations",
        "",
        "- No DB writes performed",
        "- No strategy promotion or demotion",
        "- No lifecycle mutation",
        "- No registry mutation",
        "- No 4_STAR backtest",
        "- No P108 / P117 / P118 execution",
        "- No scheduler install",
        f"- replay_rows before = {snapshot['replay_rows']}, after = {snapshot['replay_rows']} (unchanged)",
    ]

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_MD.write_text("\n".join(lines) + "\n")
    print(f"[P124] MD written: {OUTPUT_MD}")


def main() -> int:
    print("[P124] Starting pre-flight checks...")
    try:
        snapshot = db_preflight()
    except RuntimeError as e:
        print(f"[P124] BLOCKED: {e}", file=sys.stderr)
        return 1

    print(f"[P124] DB invariants OK: replay_rows={snapshot['replay_rows']}")
    matrix = build_coverage_matrix()
    print(f"[P124] Coverage matrix: {len(matrix)} rows")
    write_json(snapshot, matrix)
    write_md(snapshot, matrix)
    print("[P124] Done. Classification: P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
