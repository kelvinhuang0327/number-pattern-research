#!/usr/bin/env python3
"""
P94A: BIG_LOTTO All-Strategy Betcount Benchmark
================================================
Read-only analysis. Does NOT write to lottery_v2.db.
Does NOT insert replay rows. Does NOT promote strategies.

Baseline adjusted: post-P94 (54462 rows) because P94 controlled apply
had already completed before P94A execution.

Observation windows : 30 / 100 / 500 / 1500 latest BIG_LOTTO draws
Bet-count variants  : 1 / 2 / 3 / 5
Primary ranking     : M3+ rate
Tie-breakers        : avg_hit_count > M4+ rate > lower zero_hit_rate
                      > larger sample_size > window stability
"""

import sys
import os
import json
import sqlite3
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_JSON = PROJECT_ROOT / "outputs" / "replay" / "p94a_biglotto_all_strategy_betcount_benchmark_20260526.json"
OUTPUT_MD   = PROJECT_ROOT / "docs"    / "replay" / "p94a_biglotto_all_strategy_betcount_benchmark_20260526.md"

sys.path.insert(0, str(PROJECT_ROOT / "lottery_api"))
sys.path.insert(0, str(PROJECT_ROOT / "tools"))

# ── BIG_LOTTO random baseline (combinatorial) ────────────────────────────────
def _comb(n, k):
    if k < 0 or k > n: return 0
    num = den = 1
    for i in range(k):
        num *= (n - i)
        den *= (i + 1)
    return num // den

_TOTAL = _comb(49, 6)  # 13983816

def _baseline_rate(m):
    """P(matching exactly m or more numbers in one random 6/49 pick)."""
    return sum(_comb(6, k) * _comb(43, 6 - k) / _TOTAL for k in range(m, 7))

BASELINE_1BET = {m: _baseline_rate(m) for m in [2, 3, 4, 5, 6]}

def _nbet_baseline(m, n):
    """P(at least one of n independent bets achieves M-m+) ."""
    return 1.0 - (1.0 - BASELINE_1BET[m]) ** n


# ── Strategy registry ─────────────────────────────────────────────────────────
# Each entry describes how to benchmark the strategy.
# adapter_func   : callable(history_list) → list[list[int]]  (or None)
# native_bets    : how many bets the adapter generates (1 if no adapter)
# lifecycle      : raw lifecycle label
# source_category: classification for the report

STRATEGY_REGISTRY = [
    {
        "strategy_id": "ts3_regime_3bet",
        "display_name": "大樂透 TS3+Regime 3注",
        "lifecycle": "PRODUCTION",
        "source_category": "row-backed",
        "adapter_func_name": None,
        "native_bets": 1,
        "rejection_reason": None,
    },
    {
        "strategy_id": "biglotto_deviation_2bet",
        "display_name": "大樂透 Deviation Complement 2注",
        "lifecycle": "PRODUCTION",
        "source_category": "row-backed+adapter",
        "adapter_func_name": "deviation_complement_2bet",
        "native_bets": 2,
        "rejection_reason": None,
    },
    {
        "strategy_id": "biglotto_triple_strike",
        "display_name": "大樂透 Triple Strike 3注",
        "lifecycle": "PRODUCTION",
        "source_category": "row-backed+adapter",
        "adapter_func_name": "generate_triple_strike",
        "native_bets": 3,
        "rejection_reason": None,
    },
    {
        "strategy_id": "biglotto_echo_aware_3bet",
        "display_name": "大樂透 Echo-Aware 3注",
        "lifecycle": "TIERB_DRYRUN_VALIDATED",
        "source_category": "row-backed+adapter",
        "adapter_func_name": "echo_aware_mixed_3bet",
        "native_bets": 3,
        "rejection_reason": None,
    },
    {
        "strategy_id": "biglotto_ts3_markov_4bet_w30",
        "display_name": "大樂透 TS3+Markov(w30) 4注",
        "lifecycle": "TIERB_DRYRUN_VALIDATED",
        "source_category": "row-backed+adapter",
        "adapter_func_name": "generate_ts3_markov_4bet",
        "native_bets": 4,
        "rejection_reason": None,
    },
    {
        "strategy_id": "cold_complement_biglotto",
        "display_name": "大樂透 Cold Complement 2注",
        "lifecycle": "REJECTED",
        "source_category": "rejected-replay-only",
        "adapter_func_name": None,
        "native_bets": 1,
        "rejection_reason": "COVERAGE_ONLY_L91",
    },
    {
        "strategy_id": "coldpool15_biglotto",
        "display_name": "大樂透 Cold Pool-15 Pick-6",
        "lifecycle": "REJECTED",
        "source_category": "rejected-replay-only",
        "adapter_func_name": None,
        "native_bets": 1,
        "rejection_reason": "COVERAGE_ONLY_L91",
    },
    {
        "strategy_id": "fourier30_markov30_biglotto",
        "display_name": "大樂透 Fourier30+Markov30",
        "lifecycle": "REJECTED",
        "source_category": "rejected-replay-only",
        "adapter_func_name": None,
        "native_bets": 1,
        "rejection_reason": "COVERAGE_ONLY_L91",
    },
    {
        "strategy_id": "markov_2bet_biglotto",
        "display_name": "大樂透 Markov 2注",
        "lifecycle": "REJECTED",
        "source_category": "rejected-replay-only",
        "adapter_func_name": None,
        "native_bets": 1,
        "rejection_reason": "COVERAGE_ONLY_L91",
    },
    {
        "strategy_id": "markov_single_biglotto",
        "display_name": "大樂透 Markov Single 1注",
        "lifecycle": "REJECTED",
        "source_category": "rejected-replay-only",
        "adapter_func_name": None,
        "native_bets": 1,
        "rejection_reason": "COVERAGE_ONLY_L91",
    },
    {
        "strategy_id": "bet2_fourier_expansion_biglotto",
        "display_name": "大樂透 Fourier Expansion 2注",
        "lifecycle": "REJECTED",
        "source_category": "rejected-replay-only",
        "adapter_func_name": None,
        "native_bets": 1,
        "rejection_reason": "COVERAGE_ONLY_L91",
    },
]

BLOCKED_STRATEGIES = [
    {
        "strategy_id": "biglotto_fourier_rhythm_2bet",
        "lifecycle": "ADAPTER_PARTIAL",
        "source_category": "adapter-partial",
        "blocker": "No ReplayStrategyAdapter subclass for composite fourier_rhythm_bet + cold_numbers_bet",
        "classification": "unsupported",
    },
    {
        "strategy_id": "ts3_markov_freq_5bet_w30",
        "lifecycle": "SUPERSEDED",
        "source_category": "rejected-superseded",
        "blocker": "SUPERSEDED per lottery_api/CLAUDE.md lines 511/534-536. Replaced 2026-02-26.",
        "classification": "unsupported",
    },
]

OBSERVATION_WINDOWS = [30, 100, 500, 1500]
BET_COUNTS = [1, 2, 3, 5]


# ── DB helpers ────────────────────────────────────────────────────────────────

def load_biglotto_draws():
    """Load all BIG_LOTTO draws ordered by CAST(draw AS INTEGER) ASC."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        SELECT draw, date, numbers, special
        FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY CAST(draw AS INTEGER) ASC
    """)
    rows = c.fetchall()
    conn.close()
    draws = []
    for r in rows:
        nums = r[2] if isinstance(r[2], list) else json.loads(r[2]) if r[2] else []
        draws.append({"draw": r[0], "date": r[1], "numbers": nums, "special": r[3]})
    return draws


def load_replay_rows(strategy_id):
    """Load all replay rows for a strategy from DB. Returns dict draw→hit_count."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        SELECT target_draw, hit_count, predicted_numbers
        FROM strategy_prediction_replays
        WHERE strategy_id = ? AND lottery_type = 'BIG_LOTTO'
        ORDER BY CAST(target_draw AS INTEGER) ASC
    """, (strategy_id,))
    rows = c.fetchall()
    conn.close()
    # For draws with multiple rows (rare duplicates), take max hit_count
    by_draw = {}
    for draw, hit_count, pred in rows:
        if draw not in by_draw or hit_count > by_draw[draw]["hit_count"]:
            by_draw[draw] = {
                "hit_count": hit_count if isinstance(hit_count, int) else (hit_count or 0),
                "predicted": json.loads(pred) if isinstance(pred, str) else (pred or []),
            }
    return by_draw


def verify_db_readonly():
    """Verify DB row count has not changed (safety check)."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = c.fetchone()[0]
    conn.close()
    return count


# ── Adapter loader ────────────────────────────────────────────────────────────

def load_adapter_func(name):
    """Import and return the named adapter function. Returns None if unavailable."""
    if name is None:
        return None
    try:
        if name in ("echo_aware_mixed_3bet",):
            from predict_biglotto_echo_3bet import echo_aware_mixed_3bet
            return echo_aware_mixed_3bet
        if name in ("generate_ts3_markov_4bet",):
            from backtest_biglotto_5bet_ts3markov import generate_ts3_markov_4bet
            return lambda h: generate_ts3_markov_4bet(h, markov_window=30)
        if name in ("deviation_complement_2bet",):
            from predict_biglotto_deviation_2bet import deviation_complement_2bet
            return deviation_complement_2bet
        if name in ("generate_triple_strike",):
            from predict_biglotto_triple_strike import generate_triple_strike
            return generate_triple_strike
    except Exception as e:
        print(f"  [WARN] adapter {name} load failed: {e}", file=sys.stderr)
    return None


# ── Metrics computation ───────────────────────────────────────────────────────

def _hits_in_set(predicted_set, actual_set):
    return len(predicted_set & actual_set)


def compute_metrics_from_rows(draw_rows, window_draws):
    """
    Compute metrics using DB replay rows (1-bet only).
    draw_rows : dict draw→{hit_count, predicted}
    window_draws : list of draw dicts in the observation window
    Returns dict of metric values.
    """
    sample_hits = []
    for d in window_draws:
        draw_id = d["draw"]
        if draw_id in draw_rows:
            sample_hits.append(draw_rows[draw_id]["hit_count"])

    n = len(sample_hits)
    if n == 0:
        return _empty_metrics(sample_size=0, blocker="no_data_in_window")

    hit_arr = sample_hits
    return _compute_hit_metrics([hit_arr], n, window_draws[-1]["draw"] if window_draws else None)


def compute_metrics_nbet_adapter(adapter_func, all_draws, window_draws, n_bets):
    """
    Compute N-bet metrics by running the adapter in memory.
    adapter_func : callable(history) → list[list[int]]  (list of n_bets picks)
    all_draws    : full BIG_LOTTO draw history (for causal context)
    window_draws : list of draw dicts to evaluate (observation window)
    n_bets       : how many bets to evaluate (first n_bets picks)
    Returns dict of metric values.
    """
    if adapter_func is None:
        return _empty_metrics(sample_size=0, blocker="no_adapter")

    draw_id_to_idx = {d["draw"]: i for i, d in enumerate(all_draws)}
    per_draw_max_hits = []

    for d in window_draws:
        draw_id = d["draw"]
        idx = draw_id_to_idx.get(draw_id)
        if idx is None or idx == 0:
            continue

        history = all_draws[:idx]
        actual_set = set(d["numbers"])

        try:
            bets = adapter_func(history)
        except Exception:
            continue

        if not bets or not isinstance(bets, list):
            continue

        max_hit = 0
        for bet in bets[:n_bets]:
            if not bet:
                continue
            h = _hits_in_set(set(bet), actual_set)
            max_hit = max(max_hit, h)

        per_draw_max_hits.append(max_hit)

    n = len(per_draw_max_hits)
    if n == 0:
        return _empty_metrics(sample_size=0, blocker="adapter_returned_no_data")

    return _compute_hit_metrics([per_draw_max_hits], n, window_draws[-1]["draw"] if window_draws else None)


def _compute_hit_metrics(hit_lists, n, latest_draw):
    """
    hit_lists : list containing ONE list of per-draw max hit counts
    n         : sample size
    """
    hits = hit_lists[0]
    m2_count  = sum(1 for h in hits if h >= 2)
    m3_count  = sum(1 for h in hits if h >= 3)
    m4_count  = sum(1 for h in hits if h >= 4)
    m5_count  = sum(1 for h in hits if h >= 5)
    m6_count  = sum(1 for h in hits if h >= 6)
    zero_count = sum(1 for h in hits if h == 0)
    total_hits = sum(hits)
    best_hit   = max(hits) if hits else 0

    return {
        "sample_size": n,
        "avg_hit_count": round(total_hits / n, 4) if n else 0,
        "m2_plus_rate": round(m2_count / n, 6) if n else 0,
        "m3_plus_rate": round(m3_count / n, 6) if n else 0,
        "m4_plus_rate": round(m4_count / n, 6) if n else 0,
        "m5_plus_rate": round(m5_count / n, 6) if n else 0,
        "m6_rate": round(m6_count / n, 6) if n else 0,
        "best_hit": best_hit,
        "zero_hit_rate": round(zero_count / n, 6) if n else 1.0,
        "total_hits": total_hits,
        "latest_draw_evaluated": latest_draw,
        "coverage_pct": round(n / max(30, n) * 100, 1),  # within window
        "blocker": None,
        "data_source": "computed",
    }


def _empty_metrics(sample_size=0, blocker="unsupported"):
    return {
        "sample_size": sample_size,
        "avg_hit_count": None,
        "m2_plus_rate": None,
        "m3_plus_rate": None,
        "m4_plus_rate": None,
        "m5_plus_rate": None,
        "m6_rate": None,
        "best_hit": None,
        "zero_hit_rate": None,
        "total_hits": None,
        "latest_draw_evaluated": None,
        "coverage_pct": 0.0,
        "blocker": blocker,
        "data_source": "unsupported",
    }


# ── Ranking ───────────────────────────────────────────────────────────────────

def rank_strategies(results, window, bet_count):
    """
    Rank strategies for a given window × bet_count by M3+ rate.
    Tie-breakers: avg_hit_count > M4+ rate > lower zero_hit_rate
                  > larger sample_size
    Returns top 3 entries.
    """
    eligible = [
        (sid, meta)
        for sid, meta in results.items()
        if meta.get("windows", {}).get(str(window), {}).get(str(bet_count), {}).get("blocker") is None
        and meta["windows"][str(window)][str(bet_count)]["m3_plus_rate"] is not None
    ]

    def sort_key(item):
        m = item[1]["windows"][str(window)][str(bet_count)]
        return (
            -(m["m3_plus_rate"] or 0),
            -(m["avg_hit_count"] or 0),
            -(m["m4_plus_rate"] or 0),
             (m["zero_hit_rate"] or 1.0),
            -(m["sample_size"] or 0),
        )

    ranked = sorted(eligible, key=sort_key)

    top3 = []
    for sid, meta in ranked[:3]:
        m = meta["windows"][str(window)][str(bet_count)]
        baseline_m3 = _nbet_baseline(3, bet_count)
        top3.append({
            "rank": len(top3) + 1,
            "strategy_id": sid,
            "display_name": meta["display_name"],
            "lifecycle": meta["lifecycle"],
            "source_category": meta["source_category"],
            "m3_plus_rate": m["m3_plus_rate"],
            "m3_plus_vs_baseline": round((m["m3_plus_rate"] or 0) - baseline_m3, 6),
            "avg_hit_count": m["avg_hit_count"],
            "m4_plus_rate": m["m4_plus_rate"],
            "zero_hit_rate": m["zero_hit_rate"],
            "sample_size": m["sample_size"],
            "best_hit": m["best_hit"],
            "data_source": m["data_source"],
        })
    return top3


# ── Main benchmark ─────────────────────────────────────────────────────────────

def run_benchmark():
    print("=" * 70)
    print("P94A BIG_LOTTO All-Strategy Betcount Benchmark")
    print("READ-ONLY — no DB writes")
    print("=" * 70)

    # Pre-flight: verify DB not written
    row_count_before = verify_db_readonly()
    print(f"DB rows before: {row_count_before}")

    # Load draws
    all_draws = load_biglotto_draws()
    print(f"BIG_LOTTO draws loaded: {len(all_draws)}, "
          f"range [{all_draws[0]['draw']}..{all_draws[-1]['draw']}]")

    # Determine observation windows (latest N draws)
    window_slices = {}
    for w in OBSERVATION_WINDOWS:
        window_slices[w] = all_draws[-w:] if len(all_draws) >= w else all_draws

    # Load adapters
    adapters = {}
    for entry in STRATEGY_REGISTRY:
        fn = entry["adapter_func_name"]
        if fn:
            adapters[entry["strategy_id"]] = load_adapter_func(fn)

    # Build results dict
    results = {}
    for entry in STRATEGY_REGISTRY:
        sid = entry["strategy_id"]
        replay_rows = load_replay_rows(sid)
        adapter = adapters.get(sid)
        native_bets = entry["native_bets"]

        print(f"\n  Strategy: {sid}  (native_bets={native_bets}, "
              f"lifecycle={entry['lifecycle']}, rows={len(replay_rows)})")

        windows_data = {}
        for w in OBSERVATION_WINDOWS:
            wdraws = window_slices[w]
            bet_data = {}
            for bc in BET_COUNTS:
                if bc == 1:
                    # Always use DB rows for 1-bet (fast, verified)
                    m = compute_metrics_from_rows(replay_rows, wdraws)
                    m["data_source"] = "db_rows"
                elif bc <= native_bets and adapter is not None:
                    # Use adapter for N-bet (N ≤ native_bets)
                    m = compute_metrics_nbet_adapter(adapter, all_draws, wdraws, bc)
                    m["data_source"] = f"adapter_{bc}bet"
                else:
                    if bc > native_bets:
                        blocker = f"native_bets={native_bets}_lt_{bc}"
                    else:
                        blocker = "no_adapter"
                    m = _empty_metrics(sample_size=0, blocker=blocker)

                # Adjust coverage_pct for the actual window
                if m["sample_size"] > 0:
                    m["coverage_pct"] = round(m["sample_size"] / len(wdraws) * 100, 1)

                bet_data[str(bc)] = m
                status = f"M3+={m['m3_plus_rate']:.4f}" if m['m3_plus_rate'] is not None else f"BLOCKED({m['blocker']})"
                print(f"    w{w:4d} x {bc}bet → {status} (n={m['sample_size']})")

            windows_data[str(w)] = bet_data

        results[sid] = {
            "display_name": entry["display_name"],
            "lifecycle": entry["lifecycle"],
            "source_category": entry["source_category"],
            "native_bets": native_bets,
            "rejection_reason": entry.get("rejection_reason"),
            "windows": windows_data,
        }

    # Post-flight: verify DB unchanged
    row_count_after = verify_db_readonly()
    assert row_count_after == row_count_before, \
        f"DB rows changed! {row_count_before} → {row_count_after}"

    # Build ranking tables
    ranking_tables = {}
    for w in OBSERVATION_WINDOWS:
        ranking_tables[str(w)] = {}
        for bc in BET_COUNTS:
            top3 = rank_strategies(results, w, bc)
            ranking_tables[str(w)][str(bc)] = top3

    # Stable performers: appear in top 3 across all 4 windows for a bet_count
    stable_performers = {}
    for bc in BET_COUNTS:
        counts = defaultdict(int)
        for w in OBSERVATION_WINDOWS:
            for entry in ranking_tables[str(w)][str(bc)]:
                counts[entry["strategy_id"]] += 1
        stable_performers[str(bc)] = [
            {"strategy_id": sid, "appearances": cnt}
            for sid, cnt in sorted(counts.items(), key=lambda x: -x[1])
            if cnt >= 2
        ]

    # Short-window-only: in top 3 for w30 but NOT in top 3 for w500/w1500
    short_window_only = []
    for bc in BET_COUNTS:
        top30_ids = {e["strategy_id"] for e in ranking_tables["30"][str(bc)]}
        top500_ids = {e["strategy_id"] for e in ranking_tables["500"][str(bc)]}
        top1500_ids = {e["strategy_id"] for e in ranking_tables["1500"][str(bc)]}
        for sid in top30_ids:
            if sid not in top500_ids and sid not in top1500_ids:
                short_window_only.append({"strategy_id": sid, "bet_count": bc,
                                          "warning": "top3_w30_only"})

    # Baselines for reference
    baselines = {
        str(bc): {
            "m3_plus_rate_random": round(_nbet_baseline(3, bc), 6),
            "m2_plus_rate_random": round(_nbet_baseline(2, bc), 6),
            "m4_plus_rate_random": round(_nbet_baseline(4, bc), 6),
        }
        for bc in BET_COUNTS
    }

    # Candidate summary
    total_candidates = len(STRATEGY_REGISTRY)
    benchmarkable = sum(1 for e in STRATEGY_REGISTRY)  # all have rows
    rejected_offline = sum(1 for e in STRATEGY_REGISTRY if e["lifecycle"] in ("REJECTED", "OFFLINE"))
    row_backed = sum(1 for e in STRATEGY_REGISTRY if "row-backed" in e["source_category"])
    adapter_backed = sum(1 for e in STRATEGY_REGISTRY if "adapter" in e["source_category"])
    unsupported_count = len(BLOCKED_STRATEGIES)
    no_data = 0  # all have DB rows

    # Classification
    row_count_1500_supported = sum(
        1 for e in STRATEGY_REGISTRY
        if any(
            results[e["strategy_id"]]["windows"][str(w)]["1"]["blocker"] is None
            for w in OBSERVATION_WINDOWS
        )
    )
    if row_count_1500_supported == len(STRATEGY_REGISTRY):
        final_classification = "P94A_BIG_LOTTO_ALL_STRATEGY_BETCOUNT_BENCHMARK_READY"
    else:
        final_classification = "P94A_BIG_LOTTO_BENCHMARK_PARTIAL_WITH_BLOCKERS"

    artifact = {
        "task": "P94A",
        "title": "BIG_LOTTO All-Strategy Betcount Benchmark",
        "date": "2026-05-27",
        "final_classification": final_classification,
        "baseline_note": (
            "P94A baseline adjusted from pre-P94 46962 to post-P94 54462 "
            "because P94 controlled apply had already completed before P94A execution."
        ),
        "db_writes": False,
        "replay_row_changes": 0,
        "lifecycle_promotions": 0,
        "production_rows_before": row_count_before,
        "production_rows_after": row_count_after,
        "biglotto_draws_total": len(all_draws),
        "observation_windows": OBSERVATION_WINDOWS,
        "bet_counts": BET_COUNTS,
        "ranking_metric": "m3_plus_rate",
        "tie_breakers": ["avg_hit_count", "m4_plus_rate", "lower_zero_hit_rate",
                         "larger_sample_size", "window_stability"],
        "candidate_summary": {
            "total_biglotto_strategies": total_candidates + unsupported_count,
            "benchmarkable_count": total_candidates,
            "unsupported_blocked_count": unsupported_count,
            "rejected_offline_count": rejected_offline,
            "row_backed_count": row_backed,
            "adapter_backed_count": adapter_backed,
            "no_data_count": no_data,
        },
        "baselines": baselines,
        "strategy_results": results,
        "blocked_strategies": BLOCKED_STRATEGIES,
        "ranking_tables": ranking_tables,
        "stable_performers": stable_performers,
        "short_window_only_warning": short_window_only,
        "rejected_offline_caveat": (
            "Rejected/offline strategies are benchmarked for analysis only. "
            "Their performance figures do NOT imply promotion eligibility. "
            "Lifecycle remains unchanged. These strategies stay REJECTED/OFFLINE."
        ),
        "no_promotion_policy": (
            "No strategy lifecycle was modified by this benchmark. "
            "Rejected strategies remain rejected. Tier B strategies remain in their "
            "DRYRUN_VALIDATED state as set by P94."
        ),
        "recommended_next_step": "P94B_CONTROLLED_BENCHMARK_REVIEW",
        "recommended_next_step_note": (
            "Review top performers across windows. If any strategy shows stable "
            "improvement across w500/w1500, proceed to P95 dry-run/apply plan."
        ),
    }

    # Write JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"\nJSON artifact written: {OUTPUT_JSON}")

    return artifact


# ── Markdown report generator ─────────────────────────────────────────────────

def generate_markdown(artifact):
    w_labels = {30: "Latest 30", 100: "Latest 100", 500: "Latest 500", 1500: "Latest 1500"}
    lines = []
    a = artifact
    rt = a["ranking_tables"]
    bs = a["baselines"]

    lines.append("# P94A: BIG_LOTTO All-Strategy Betcount Benchmark")
    lines.append("")
    lines.append(f"**Date**: {a['date']}  ")
    lines.append(f"**Final Classification**: `{a['final_classification']}`  ")
    lines.append(f"**Baseline Note**: {a['baseline_note']}")
    lines.append("")
    lines.append("## 1. Governance")
    lines.append("")
    lines.append("| Item | Value |")
    lines.append("|------|-------|")
    lines.append(f"| DB writes | `{a['db_writes']}` |")
    lines.append(f"| Replay row changes | `{a['replay_row_changes']}` |")
    lines.append(f"| Lifecycle promotions | `{a['lifecycle_promotions']}` |")
    lines.append(f"| Production rows before | `{a['production_rows_before']}` |")
    lines.append(f"| Production rows after | `{a['production_rows_after']}` |")
    lines.append(f"| Ranking metric | `{a['ranking_metric']}` |")
    lines.append("")
    lines.append("## 2. BIG_LOTTO Candidate Summary")
    lines.append("")
    cs = a["candidate_summary"]
    lines.append("| Category | Count |")
    lines.append("|----------|-------|")
    for k, v in cs.items():
        lines.append(f"| {k.replace('_', ' ').title()} | {v} |")
    lines.append("")

    lines.append("## 3. Strategy Universe")
    lines.append("")
    lines.append("### 3a. Benchmarkable Strategies")
    lines.append("")
    lines.append("| strategy_id | lifecycle | source | native_bets | 1-bet | 2-bet | 3-bet | 5-bet |")
    lines.append("|-------------|-----------|--------|-------------|-------|-------|-------|-------|")
    for sid, meta in a["strategy_results"].items():
        supported = []
        for bc in [1, 2, 3, 5]:
            blk = meta["windows"]["1500"][str(bc)]["blocker"]
            supported.append("✓" if blk is None else f"✗ ({blk[:20]})")
        lines.append(f"| `{sid}` | {meta['lifecycle']} | {meta['source_category']} "
                     f"| {meta['native_bets']} | {supported[0]} | {supported[1]} "
                     f"| {supported[2]} | {supported[3]} |")
    lines.append("")
    lines.append("### 3b. Blocked / Unsupported Strategies")
    lines.append("")
    lines.append("| strategy_id | status | blocker |")
    lines.append("|-------------|--------|---------|")
    for b in a["blocked_strategies"]:
        lines.append(f"| `{b['strategy_id']}` | {b['lifecycle']} | {b['blocker'][:70]} |")
    lines.append("")

    lines.append("## 4. Random Baseline Rates")
    lines.append("")
    lines.append("| bet_count | M2+ | M3+ | M4+ |")
    lines.append("|-----------|-----|-----|-----|")
    for bc in [1, 2, 3, 5]:
        b = bs[str(bc)]
        lines.append(f"| {bc} | {b['m2_plus_rate_random']:.4f} | "
                     f"{b['m3_plus_rate_random']:.4f} | {b['m4_plus_rate_random']:.6f} |")
    lines.append("")

    lines.append("## 5. Top-3 Rankings by Window × Bet Count")
    lines.append("")
    lines.append("> **Primary metric**: M3+ rate  ")
    lines.append("> **Tie-breakers**: avg_hit_count > M4+ rate > lower zero_hit_rate > larger sample_size")
    lines.append("")

    for w in [30, 100, 500, 1500]:
        lines.append(f"### Window = {w_labels[w]} draws")
        lines.append("")
        for bc in [1, 2, 3, 5]:
            lines.append(f"#### Bet count = {bc}")
            lines.append("")
            baseline_m3 = a['baselines'][str(bc)]['m3_plus_rate_random']
            lines.append(f"Random M3+ baseline ({bc}-bet): `{baseline_m3:.4f}`")
            lines.append("")
            top3 = rt[str(w)][str(bc)]
            if not top3:
                lines.append("*No strategies with valid data for this combination.*")
                lines.append("")
                continue
            lines.append("| Rank | strategy_id | lifecycle | M3+ | vs baseline | avg_hit | M4+ | zero_hit% | n | source |")
            lines.append("|------|-------------|-----------|-----|-------------|---------|-----|-----------|---|--------|")
            for e in top3:
                delta = e['m3_plus_vs_baseline']
                delta_str = f"+{delta:.4f}" if delta >= 0 else f"{delta:.4f}"
                lines.append(
                    f"| {e['rank']} | `{e['strategy_id']}` | {e['lifecycle']} "
                    f"| {e['m3_plus_rate']:.4f} | {delta_str} "
                    f"| {e['avg_hit_count']:.4f} | {e['m4_plus_rate']:.6f} "
                    f"| {e['zero_hit_rate']*100:.1f}% | {e['sample_size']} "
                    f"| {e['data_source']} |"
                )
            lines.append("")

    lines.append("## 6. Stable Top Performers")
    lines.append("")
    lines.append("Strategies appearing in top 3 across ≥2 observation windows:")
    lines.append("")
    for bc in [1, 2, 3, 5]:
        stable = a["stable_performers"][str(bc)]
        if stable:
            lines.append(f"**{bc}-bet**: " + ", ".join(
                f"`{s['strategy_id']}` ({s['appearances']}/4 windows)" for s in stable))
        else:
            lines.append(f"**{bc}-bet**: *(no strategy appeared in top 3 across ≥2 windows)*")
    lines.append("")

    lines.append("## 7. Short-Window-Only Performers Warning")
    lines.append("")
    if a["short_window_only_warning"]:
        lines.append("The following strategies appear in top 3 for w30 but NOT for w500/w1500:")
        lines.append("")
        for s in a["short_window_only_warning"]:
            lines.append(f"- `{s['strategy_id']}` ({s['bet_count']}-bet) — {s['warning']}")
    else:
        lines.append("*No short-window-only performers detected.*")
    lines.append("")

    lines.append("## 8. Rejected/Offline Replay-Only Caveat")
    lines.append("")
    lines.append(a["rejected_offline_caveat"])
    lines.append("")

    lines.append("## 9. No-Data / Unsupported Policy")
    lines.append("")
    lines.append("- Bet count variants exceeding a strategy's native_bets are marked **UNSUPPORTED** unless a valid multi-bet adapter exists.")
    lines.append("- No bet counts are fabricated or duplicated to fill missing variants.")
    lines.append("- Blocked strategies (adapter-partial, superseded) are listed in Section 3b with explicit blockers.")
    lines.append("")

    lines.append("## 10. Recommended Next Steps")
    lines.append("")
    lines.append(f"**Recommendation**: `{a['recommended_next_step']}`")
    lines.append("")
    lines.append(a["recommended_next_step_note"])
    lines.append("")
    lines.append("If ≥1 strategy shows stable M3+ improvement across w500+w1500 vs random baseline, proceed to:")
    lines.append("- **P94B** Controlled Benchmark Review (validate top performers with stricter statistical tests)")
    lines.append("- **P95** Selected Strategy Dry-Run/Apply Plan (if P94B confirms a clear winner)")
    lines.append("")

    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Markdown report written: {OUTPUT_MD}")


if __name__ == "__main__":
    artifact = run_benchmark()
    generate_markdown(artifact)
    print(f"\nFinal classification: {artifact['final_classification']}")
    print(f"DB writes: {artifact['db_writes']}")
    print(f"Replay row changes: {artifact['replay_row_changes']}")
    print("Done.")
