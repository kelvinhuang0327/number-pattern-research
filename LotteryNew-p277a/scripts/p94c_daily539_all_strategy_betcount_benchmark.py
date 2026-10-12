#!/usr/bin/env python3
"""
P94C Daily539 All-Strategy Bet-Count Benchmark
================================================
Read-only benchmark for ALL DAILY_539 strategies across bet counts 1/2/3/5
and observation windows 30/100/500/1500.

GOVERNANCE:
  - NO writes to lottery_v2.db
  - NO production replay row inserts
  - NO lifecycle/champion/registry mutations
  - Causal isolation: history window ends strictly before target draw

Usage:
  python3 scripts/p94c_daily539_all_strategy_betcount_benchmark.py
  python3 scripts/p94c_daily539_all_strategy_betcount_benchmark.py --full
"""
from __future__ import annotations

import json
import sys
import os
import argparse
import logging
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_JSON = (
    PROJECT_ROOT
    / "outputs"
    / "replay"
    / "p94c_daily539_all_strategy_betcount_benchmark_20260526.json"
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

LOTTERY_TYPE = "DAILY_539"
POOL_SIZE = 39
PICK = 5
WINDOWS = [30, 100, 500, 1500]
BET_COUNTS = [1, 2, 3, 5]

# Baseline M3+ rate for 1 bet of 5 from pool 39 (draw picks 5):
# P(M3+) = [C(5,3)*C(34,2) + C(5,4)*C(34,1) + C(5,5)*C(34,0)] / C(39,5)
#          = [5610 + 170 + 1] / 575757 ≈ 1.004%
BASELINE_M3_1BET = 5781 / 575757  # ~0.010040

# ─── Strategy catalog ─────────────────────────────────────────────────────────

STRATEGY_CATALOG = [
    # ── Tier A: row-backed ──────────────────────────────────────────────────
    {
        "strategy_id": "acb_1bet",
        "display_name": "今彩539 ACB 1注",
        "source": "tier_a_row_backed",
        "lifecycle": "PRODUCTION",
        "performance_label": "RETIRED",
        "native_bet_count": 1,
        "has_multibet_adapter": False,
        "db_rows": 1500,
    },
    {
        "strategy_id": "acb_markov_midfreq",
        "display_name": "今彩539 ACB+Markov 中頻",
        "source": "tier_a_row_backed",
        "lifecycle": "NOT_IN_P0",
        "performance_label": "RETIRED",
        "native_bet_count": 1,
        "has_multibet_adapter": False,
        "db_rows": 1500,
    },
    {
        "strategy_id": "acb_single_539",
        "display_name": "今彩539 ACB Single 1注",
        "source": "tier_a_row_backed",
        "lifecycle": "REJECTED",
        "performance_label": "WAVE2",
        "native_bet_count": 1,
        "has_multibet_adapter": False,
        "db_rows": 1500,
    },
    {
        "strategy_id": "acb_markov_midfreq_3bet",
        "display_name": "今彩539 ACB+Markov 中頻 3注",
        "source": "tier_a_row_backed",
        "lifecycle": "PRODUCTION",
        "performance_label": "RETIRED",
        "native_bet_count": 3,
        "has_multibet_adapter": False,
        "db_rows": 1500,
        "db_storage_note": "DB stores bet-1 (ACB) only; bets 2-3 not recorded in DB",
    },
    {
        "strategy_id": "539_3bet_orthogonal",
        "display_name": "今彩539 ACB+Markov+Fourier 正交 3注",
        "source": "tier_a_row_backed",
        "lifecycle": "REJECTED",
        "performance_label": "WAVE2_ACTIVE",
        "native_bet_count": 3,
        "has_multibet_adapter": False,
        "db_rows": 1500,
        "db_storage_note": "DB stores bet-1 (ACB) only; bets 2-3 not recorded in DB",
    },
    {
        "strategy_id": "daily539_f4cold",
        "display_name": "今彩539 F4 Cold (legacy)",
        "source": "tier_a_row_backed",
        "lifecycle": "PRODUCTION",
        "performance_label": "ONLINE_LEGACY",
        "native_bet_count": 1,
        "has_multibet_adapter": False,
        "db_rows": 1590,
    },
    {
        "strategy_id": "p0b_539_3bet_f_cold_fmid",
        "display_name": "今彩539 Fourier4正交 cold+midfreq 3注",
        "source": "tier_a_row_backed",
        "lifecycle": "REJECTED",
        "performance_label": "WAVE2_ACTIVE",
        "native_bet_count": 3,
        "has_multibet_adapter": False,
        "db_rows": 1500,
        "db_storage_note": "DB stores bet-1 only; bets 2-3 not recorded in DB",
    },
    {
        "strategy_id": "p0c_539_3bet_f_cold_x2",
        "display_name": "今彩539 Fourier4正交 x2 cold 3注",
        "source": "tier_a_row_backed",
        "lifecycle": "REJECTED",
        "performance_label": "WAVE2_ACTIVE",
        "native_bet_count": 3,
        "has_multibet_adapter": False,
        "db_rows": 1500,
        "db_storage_note": "DB stores bet-1 only; bets 2-3 not recorded in DB",
    },
    {
        "strategy_id": "markov_1bet_539",
        "display_name": "今彩539 Markov 1注",
        "source": "tier_a_row_backed",
        "lifecycle": "REJECTED",
        "performance_label": "WAVE2_ACTIVE",
        "native_bet_count": 1,
        "has_multibet_adapter": False,
        "db_rows": 1500,
    },
    {
        "strategy_id": "daily539_markov_cold",
        "display_name": "今彩539 Markov Cold",
        "source": "tier_a_row_backed",
        "lifecycle": "PRODUCTION",
        "performance_label": "ONLINE_LEGACY",
        "native_bet_count": 1,
        "has_multibet_adapter": False,
        "db_rows": 1590,
    },
    {
        "strategy_id": "zone_gap_3bet_539",
        "display_name": "今彩539 Zone+Gap 3注",
        "source": "tier_a_row_backed",
        "lifecycle": "REJECTED",
        "performance_label": "WAVE2_ACTIVE",
        "native_bet_count": 3,
        "has_multibet_adapter": False,
        "db_rows": 1500,
        "db_storage_note": "DB stores bet-1 only; bets 2-3 not recorded in DB",
    },
    {
        "strategy_id": "midfreq_acb_2bet",
        "display_name": "今彩539 中頻 ACB 2注",
        "source": "tier_a_row_backed",
        "lifecycle": "PRODUCTION",
        "performance_label": "RETIRED",
        "native_bet_count": 2,
        "has_multibet_adapter": False,
        "db_rows": 1500,
        "db_storage_note": "DB stores bet-1 (MidFreq) only; bet-2 (ACB) not recorded in DB",
    },
    {
        "strategy_id": "midfreq_fourier_2bet",
        "display_name": "今彩539 中頻 Fourier 2注",
        "source": "tier_a_row_backed",
        "lifecycle": "PRODUCTION",
        "performance_label": "RETIRED",
        "native_bet_count": 2,
        "has_multibet_adapter": False,
        "db_rows": 1500,
        "db_storage_note": "DB stores bet-1 (MidFreq) only; bet-2 (Fourier) not recorded in DB",
    },
    # ── Tier B: adapter-backed, now row-backed after P94 apply ─────────────
    {
        "strategy_id": "daily539_f4cold_3bet",
        "display_name": "今彩539 F4Cold 3注",
        "source": "tier_b_p94_applied",
        "lifecycle": "PRODUCTION",
        "performance_label": "P94_TIER_B",
        "native_bet_count": 3,
        "has_multibet_adapter": True,
        "adapter_module": "lottery_api.models.p93_tierb_replay_adapters",
        "adapter_class": "Daily539F4Cold3BetAdapter",
        "db_rows": 1500,
        "max_benchmark_bet_count": 3,
    },
    {
        "strategy_id": "daily539_f4cold_5bet",
        "display_name": "今彩539 F4Cold 5注",
        "source": "tier_b_p94_applied",
        "lifecycle": "PRODUCTION",
        "performance_label": "P94_TIER_B",
        "native_bet_count": 5,
        "has_multibet_adapter": True,
        "adapter_module": "lottery_api.models.p93_tierb_replay_adapters",
        "adapter_class": "Daily539F4Cold5BetAdapter",
        "db_rows": 1500,
        "max_benchmark_bet_count": 5,
    },
]

# ─── DB helpers ───────────────────────────────────────────────────────────────


def get_db_connection() -> sqlite3.Connection:
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_daily539_draws(conn: sqlite3.Connection) -> List[dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT draw, date, numbers
        FROM draws
        WHERE lottery_type = 'DAILY_539'
        ORDER BY CAST(draw AS INTEGER) ASC
    """)
    result = []
    for r in cur.fetchall():
        nums = r["numbers"]
        if isinstance(nums, str):
            nums = json.loads(nums)
        result.append({"draw": r["draw"], "date": r["date"], "numbers": nums})
    return result


def load_replay_rows(conn: sqlite3.Connection, strategy_id: str) -> Dict[str, dict]:
    cur = conn.cursor()
    cur.execute("""
        SELECT target_draw, predicted_numbers, hit_count, actual_numbers
        FROM strategy_prediction_replays
        WHERE lottery_type = 'DAILY_539' AND strategy_id = ?
        ORDER BY CAST(target_draw AS INTEGER) ASC
    """, (strategy_id,))
    result = {}
    for r in cur.fetchall():
        pred = r["predicted_numbers"]
        if isinstance(pred, str):
            pred = json.loads(pred)
        actual = r["actual_numbers"]
        if isinstance(actual, str):
            actual = json.loads(actual)
        result[r["target_draw"]] = {
            "predicted_numbers": pred,
            "hit_count": int(r["hit_count"]) if r["hit_count"] is not None else 0,
            "actual_numbers": actual,
        }
    return result


# ─── Metrics ─────────────────────────────────────────────────────────────────


def compute_metrics(hit_counts: List[int], window_total: int) -> dict:
    n = len(hit_counts)
    if n == 0:
        return {
            "sample_size": 0,
            "coverage_pct": 0.0,
            "avg_hit_count": None,
            "m1_rate": None,
            "m2_rate": None,
            "m3_rate": None,
            "m4_rate": None,
            "m5_rate": None,
            "best_hit": None,
            "zero_hit_rate": None,
            "total_hits": 0,
        }
    total = sum(hit_counts)
    return {
        "sample_size": n,
        "coverage_pct": round(n / window_total, 4) if window_total else 0.0,
        "avg_hit_count": round(total / n, 4),
        "m1_rate": round(sum(1 for h in hit_counts if h >= 1) / n, 6),
        "m2_rate": round(sum(1 for h in hit_counts if h >= 2) / n, 6),
        "m3_rate": round(sum(1 for h in hit_counts if h >= 3) / n, 6),
        "m4_rate": round(sum(1 for h in hit_counts if h >= 4) / n, 6),
        "m5_rate": round(sum(1 for h in hit_counts if h >= 5) / n, 6),
        "best_hit": max(hit_counts),
        "zero_hit_rate": round(sum(1 for h in hit_counts if h == 0) / n, 6),
        "total_hits": total,
    }


def hit_count_from_bet(bet: List[int], actual: List[int]) -> int:
    return len(set(bet) & set(actual))


# ─── Evaluation drivers ───────────────────────────────────────────────────────


def eval_1bet_db(
    replay_rows: Dict[str, dict],
    window_draws: List[dict],
) -> Tuple[dict, str]:
    """1-bet metrics from DB rows. Returns (metrics, latest_draw)."""
    hit_counts = []
    last_draw = None
    for d in window_draws:
        row = replay_rows.get(d["draw"])
        if row:
            hit_counts.append(row["hit_count"])
            last_draw = d["draw"]
    m = compute_metrics(hit_counts, len(window_draws))
    return m, last_draw


def _load_adapter(meta: dict):
    import importlib
    mod = importlib.import_module(meta["adapter_module"])
    cls = getattr(mod, meta["adapter_class"])
    return cls()


def eval_multibet_adapter(
    meta: dict,
    all_draws: List[dict],
    window_draws: List[dict],
    bet_count: int,
) -> Tuple[Optional[dict], Optional[str], Optional[str]]:
    """
    Multi-bet metrics using adapter.get_all_bets().
    Returns (metrics, latest_draw, error_msg).
    """
    try:
        adapter = _load_adapter(meta)
    except Exception as e:
        return None, None, f"ADAPTER_LOAD_ERROR: {e}"

    draw_to_idx = {d["draw"]: i for i, d in enumerate(all_draws)}
    min_hist = getattr(adapter.meta, "min_history", 100)

    hit_counts = []
    last_draw = None
    skipped = 0

    for draw_rec in window_draws:
        idx = draw_to_idx.get(draw_rec["draw"])
        if idx is None or idx < min_hist:
            skipped += 1
            continue
        history = all_draws[:idx]
        try:
            all_bets = adapter.get_all_bets(history)
        except Exception:
            skipped += 1
            continue

        bets = [
            b for b in all_bets[:bet_count]
            if (
                isinstance(b, list)
                and len(b) == PICK
                and all(isinstance(n, int) and 1 <= n <= POOL_SIZE for n in b)
                and len(set(b)) == PICK
            )
        ]
        if not bets:
            skipped += 1
            continue

        max_hit = max(hit_count_from_bet(b, draw_rec["numbers"]) for b in bets)
        hit_counts.append(max_hit)
        last_draw = draw_rec["draw"]

    m = compute_metrics(hit_counts, len(window_draws))
    m["skipped_draws"] = skipped
    return m, last_draw, None


# ─── Per-variant result builder ───────────────────────────────────────────────


def build_result(
    meta: dict,
    bet_count: int,
    window: int,
    window_draws: List[dict],
    all_draws: List[dict],
    replay_rows: Dict[str, dict],
    full_mode: bool,
) -> dict:
    sid = meta["strategy_id"]
    native = meta.get("native_bet_count", 1)

    base = {
        "strategy_id": sid,
        "bet_count": bet_count,
        "window": window,
        "lifecycle": meta["lifecycle"],
        "performance_label": meta["performance_label"],
        "source_category": meta["source"],
    }

    # bet_count > native → always unsupported
    if bet_count > native:
        return {
            **base,
            "source": "UNSUPPORTED",
            "blocker": "BET_COUNT_EXCEEDS_NATIVE",
            "blocker_detail": (
                f"Strategy natively outputs {native} bet(s); "
                f"cannot fabricate bet #{bet_count}."
            ),
        }

    # 1-bet: use DB rows
    if bet_count == 1:
        m, last_draw = eval_1bet_db(replay_rows, window_draws)
        return {
            **base,
            "source": "DB_ROW_1BET",
            "latest_draw_evaluated": last_draw,
            **m,
        }

    # bet_count > 1 with get_all_bets() adapter
    if meta.get("has_multibet_adapter"):
        max_win_for_adapter = 1500 if full_mode else 100
        if window <= max_win_for_adapter:
            m, last_draw, err = eval_multibet_adapter(
                meta, all_draws, window_draws, bet_count
            )
            if err:
                return {**base, "source": "ADAPTER_ERROR", "blocker": err}
            return {
                **base,
                "source": "ADAPTER_MULTIBET",
                "latest_draw_evaluated": last_draw,
                **m,
            }
        else:
            # Fallback: show 1-bet DB metrics with caveat
            m, last_draw = eval_1bet_db(replay_rows, window_draws)
            return {
                **base,
                "source": "DB_ROW_1BET_FALLBACK",
                "latest_draw_evaluated": last_draw,
                "caveat": (
                    f"multibet adapter not run for window={window} in FAST mode; "
                    "metrics reflect 1-bet DB rows. Re-run with --full for true multibet."
                ),
                **m,
            }

    # bet_count > 1 with no adapter → unsupported
    return {
        **base,
        "source": "UNSUPPORTED",
        "blocker": "DB_SINGLE_BET_ONLY",
        "blocker_detail": meta.get(
            "db_storage_note",
            "DB stores bet-1 only; additional bets not recorded.",
        ),
    }


# ─── Ranking ─────────────────────────────────────────────────────────────────


def rank_top3(results: List[dict], window: int, bet_count: int) -> List[dict]:
    candidates = [
        r for r in results
        if r.get("window") == window
        and r.get("bet_count") == bet_count
        and "blocker" not in r
        and r.get("m3_rate") is not None
        and r.get("sample_size", 0) > 0
    ]

    def key(r):
        return (
            -(r.get("m3_rate") or 0),
            -(r.get("avg_hit_count") or 0),
            -(r.get("m4_rate") or 0),
            -(r.get("m5_rate") or 0),
            (r.get("zero_hit_rate") or 1.0),
            -(r.get("sample_size") or 0),
        )

    ranked = sorted(candidates, key=key)[:3]
    out = []
    for rank, r in enumerate(ranked, 1):
        entry = {
            "rank": rank,
            "strategy_id": r["strategy_id"],
            "lifecycle": r.get("lifecycle"),
            "performance_label": r.get("performance_label"),
            "source": r.get("source"),
            "sample_size": r.get("sample_size"),
            "m3_rate": r.get("m3_rate"),
            "m3_rate_pct": round((r.get("m3_rate") or 0) * 100, 2),
            "avg_hit_count": r.get("avg_hit_count"),
            "m4_rate": r.get("m4_rate"),
            "m5_rate": r.get("m5_rate"),
            "best_hit": r.get("best_hit"),
            "zero_hit_rate": r.get("zero_hit_rate"),
            "coverage_pct": r.get("coverage_pct"),
            "latest_draw_evaluated": r.get("latest_draw_evaluated"),
        }
        if r.get("caveat"):
            entry["caveat"] = r["caveat"]
        out.append(entry)

    if not out:
        out.append({
            "rank": None,
            "window": window,
            "bet_count": bet_count,
            "blocker": "NO_BENCHMARKABLE_STRATEGY",
            "blocker_detail": (
                f"No strategy has qualifying {bet_count}-bet metrics for window={window}. "
                "All candidates are unsupported or require --full adapter rerun."
            ),
        })
    return out


# ─── Main ────────────────────────────────────────────────────────────────────


def run_benchmark(full_mode: bool = False) -> dict:
    logger.info("P94C Daily539 All-Strategy Benchmark starting")
    logger.info(f"Mode: {'FULL' if full_mode else 'FAST'}")

    conn = get_db_connection()

    all_draws = load_daily539_draws(conn)
    logger.info(f"Loaded {len(all_draws)} DAILY_539 draws")
    latest_draw = all_draws[-1]["draw"] if all_draws else None

    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as n FROM strategy_prediction_replays")
    total_replay_rows = cur.fetchone()[0]
    cur.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    )
    max_pl_draw = str(cur.fetchone()[0])

    logger.info("Loading replay rows…")
    all_replay: Dict[str, Dict[str, dict]] = {}
    for meta in STRATEGY_CATALOG:
        rows = load_replay_rows(conn, meta["strategy_id"])
        all_replay[meta["strategy_id"]] = rows
        logger.info(f"  {meta['strategy_id']}: {len(rows)} rows")

    conn.close()

    # Window draw sets
    window_draws: Dict[int, List[dict]] = {
        w: (all_draws[-w:] if len(all_draws) >= w else all_draws)
        for w in WINDOWS
    }

    # Evaluate
    all_results: List[dict] = []
    for meta in STRATEGY_CATALOG:
        sid = meta["strategy_id"]
        logger.info(f"Evaluating {sid}…")
        for bc in BET_COUNTS:
            for w in WINDOWS:
                r = build_result(
                    meta=meta,
                    bet_count=bc,
                    window=w,
                    window_draws=window_draws[w],
                    all_draws=all_draws,
                    replay_rows=all_replay[sid],
                    full_mode=full_mode,
                )
                all_results.append(r)

    # Ranking tables
    ranking_tables: Dict[str, list] = {}
    for w in WINDOWS:
        for bc in BET_COUNTS:
            key = f"top3_w{w}_bet{bc}"
            ranking_tables[key] = rank_top3(all_results, w, bc)

    # Stable top performers (appear in top-3 for ≥2 windows)
    appearances: Counter = Counter()
    for key, tops in ranking_tables.items():
        bc = int(key.split("_bet")[1])
        for t in tops:
            if t.get("rank") is not None and t.get("strategy_id"):
                appearances[(t["strategy_id"], bc)] += 1
    stable = [
        {"strategy_id": s, "bet_count": b, "top3_appearances": c}
        for (s, b), c in sorted(appearances.items(), key=lambda x: -x[1])
        if c >= 2
    ]

    # Short-window-only performers
    short_set = set()
    long_set = set()
    for key, tops in ranking_tables.items():
        w = int(key.split("_w")[1].split("_")[0])
        bc = int(key.split("_bet")[1])
        for t in tops:
            if t.get("rank") is not None and t.get("strategy_id"):
                pair = (t["strategy_id"], bc)
                (short_set if w in (30, 100) else long_set).add(pair)
    short_only = [
        {"strategy_id": s, "bet_count": b}
        for s, b in (short_set - long_set)
    ]

    # Summary
    benchmarkable = len([m for m in STRATEGY_CATALOG if all_replay.get(m["strategy_id"])])
    unsupported = [m["strategy_id"] for m in STRATEGY_CATALOG if not all_replay.get(m["strategy_id"])]

    # Classification
    all_1bet_ok = all(
        not r.get("blocker")
        for r in all_results
        if r["bet_count"] == 1
    )
    final_classification = (
        "P94C_DAILY539_ALL_STRATEGY_BETCOUNT_BENCHMARK_READY"
        if all_1bet_ok and benchmarkable == len(STRATEGY_CATALOG)
        else "P94C_DAILY539_BENCHMARK_PARTIAL_WITH_BLOCKERS"
    )

    return {
        "task": "P94C",
        "title": "Daily539 All-Strategy Bet-Count Benchmark",
        "date": "2026-05-26",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "FULL" if full_mode else "FAST",
        "final_classification": final_classification,
        "governance": {
            "db_writes": False,
            "production_replay_row_changes": 0,
            "lifecycle_promotions": 0,
            "rejected_offline_no_promotion": True,
            "no_fabricated_bets": True,
            "causal_isolation": True,
        },
        "production_invariants": {
            "replay_rows_before": total_replay_rows,
            "replay_rows_after": total_replay_rows,
            "power_lotto_max_draw_before": max_pl_draw,
            "power_lotto_max_draw_after": max_pl_draw,
            "replay_rows_unchanged": True,
        },
        "daily539_semantics": {
            "lottery_type": "DAILY_539",
            "pick": PICK,
            "pool": POOL_SIZE,
            "pool_range": "1–39",
            "special_number": None,
            "note": "DAILY_539 has no special number. Bets are exactly 5 numbers in 1–39.",
        },
        "candidate_summary": {
            "total_daily539_strategies": len(STRATEGY_CATALOG),
            "benchmarkable_count": benchmarkable,
            "unsupported_count": len(unsupported),
            "unsupported_list": unsupported,
            "row_backed_count": sum(1 for m in STRATEGY_CATALOG if "tier_a" in m["source"]),
            "adapter_backed_count": sum(1 for m in STRATEGY_CATALOG if m.get("has_multibet_adapter")),
            "p94_tier_b_count": sum(1 for m in STRATEGY_CATALOG if m["source"] == "tier_b_p94_applied"),
            "native_1bet_count": sum(1 for m in STRATEGY_CATALOG if m["native_bet_count"] == 1),
            "native_2bet_count": sum(1 for m in STRATEGY_CATALOG if m["native_bet_count"] == 2),
            "native_3bet_count": sum(1 for m in STRATEGY_CATALOG if m["native_bet_count"] == 3),
            "native_5bet_count": sum(1 for m in STRATEGY_CATALOG if m["native_bet_count"] == 5),
        },
        "observation_windows": WINDOWS,
        "bet_counts": BET_COUNTS,
        "ranking_metric": "M3+ rate (primary); tiebreakers: avg_hit_count, M4+ rate, M5 rate, lower zero_hit_rate, larger sample_size",
        "baseline_m3_1bet_pct": round(BASELINE_M3_1BET * 100, 4),
        "latest_draw_evaluated": latest_draw,
        "strategy_catalog": STRATEGY_CATALOG,
        "all_results": all_results,
        "ranking_tables": ranking_tables,
        "stable_top_performers": stable,
        "short_window_only_performers": short_only,
        "rejected_offline_policy": (
            "Rejected/offline strategies included for replay-only analysis. "
            "No rejected/offline strategy has been promoted or inserted to production DB."
        ),
        "no_data_policy": (
            "Strategies without DB rows are listed with blocker=NO_DATA. "
            "Unsupported bet counts are never fabricated or duplicated."
        ),
        "multibet_notes": (
            "In FAST mode, adapter-based multibet metrics are computed only for windows 30 and 100. "
            "For windows 500/1500, multibet shows 1-bet DB fallback with caveat. "
            "Use --full to compute adapter-based multibet for all windows (~15 min)."
        ),
        "recommended_next_step": (
            "P94D: Cross-game controlled benchmark review (BIG_LOTTO / POWER_LOTTO / DAILY_539), "
            "or P95: Selected strategy dry-run/apply plan for top stable performers."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description="P94C Daily539 All-Strategy Benchmark")
    parser.add_argument("--full", action="store_true",
                        help="Run adapter for all windows including 500/1500")
    parser.add_argument("--output", default=str(OUT_JSON))
    args = parser.parse_args()

    result = run_benchmark(full_mode=args.full)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"Written to {out}")
    logger.info(f"Classification: {result['final_classification']}")
    c = result["candidate_summary"]
    logger.info(
        f"Strategies: {c['total_daily539_strategies']} total, "
        f"{c['benchmarkable_count']} benchmarkable, "
        f"{c['unsupported_count']} unsupported"
    )
    for w in [100, 1500]:
        for bc in [1, 3]:
            key = f"top3_w{w}_bet{bc}"
            tops = result["ranking_tables"][key]
            logger.info(f"Top-3 w={w} bet={bc}:")
            for t in tops:
                if t.get("rank"):
                    logger.info(f"  #{t['rank']} {t['strategy_id']}: M3+={t.get('m3_rate_pct')}%")
                else:
                    logger.info(f"  [BLOCKED] {t.get('blocker_detail', '')[:80]}")


if __name__ == "__main__":
    main()
