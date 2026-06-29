#!/usr/bin/env python3
"""
p94b_powerlotto_all_strategy_betcount_benchmark.py
===================================================
P94B — Power Lotto All-Strategy × BetCount Benchmark

Evaluates ALL POWER_LOTTO strategies across:
  Bet counts:         1, 2, 3, 5
  Observation windows: 30, 100, 500, 1500 (latest N draws)

For each window × bet_count, produces ranked top-3 strategies.

Governance:
  - READ-ONLY: no writes to lottery_v2.db
  - Causal isolation: history MUST end BEFORE target draw
  - Multi-bet via adapter = memory-only, no DB insert
  - Rejected/offline strategies included in analysis, not promoted
"""
from __future__ import annotations

import sys
import json
import logging
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
LOTTERY_TYPE = "POWER_LOTTO"
MAIN_POOL = 38
MAIN_PICK = 6
SPECIAL_POOL = 8
BET_COUNTS = [1, 2, 3, 5]
WINDOWS = [30, 100, 500, 1500]
TODAY = datetime.now(timezone.utc).strftime("%Y%m%d")

OUTPUT_DIR = PROJECT_ROOT / "outputs" / "replay"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_JSON = OUTPUT_DIR / f"p94b_powerlotto_all_strategy_betcount_benchmark_{TODAY}.json"

# ─── Strategy Catalog ─────────────────────────────────────────────────────────
# Each entry: strategy_id, display_name, native_bets, lifecycle, adapter_type, special_support
# native_bets = how many bets the strategy natively generates
# adapter_type = "multibet_tool" | "single_bet_only" | "rows_only"

STRATEGY_CATALOG = [
    {
        "strategy_id": "power_precision_3bet",
        "display_name": "PP3 Precision 3注",
        "native_bets": 3,
        "lifecycle": "ONLINE",
        "adapter_type": "multibet_tool",
        "special_support": False,
    },
    {
        "strategy_id": "power_orthogonal_5bet",
        "display_name": "Power Orthogonal 5注",
        "native_bets": 5,
        "lifecycle": "ONLINE",
        "adapter_type": "multibet_tool",
        "special_support": False,
    },
    {
        "strategy_id": "fourier_rhythm_3bet",
        "display_name": "Fourier Rhythm 3注",
        "native_bets": 3,
        "lifecycle": "ONLINE",
        "adapter_type": "multibet_tool",
        "special_support": False,
    },
    {
        "strategy_id": "power_fourier_rhythm_2bet",
        "display_name": "Power Fourier Rhythm 2注",
        "native_bets": 2,
        "lifecycle": "DRY_RUN",
        "adapter_type": "multibet_tool",
        "special_support": False,
    },
    {
        "strategy_id": "zonal_entropy_2bet",
        "display_name": "Zonal Entropy 2注",
        "native_bets": 2,
        "lifecycle": "DRY_RUN",
        "adapter_type": "multibet_tool",
        "special_support": False,
    },
    {
        "strategy_id": "pp3_freqort_4bet",
        "display_name": "PP3+FreqOrt 4注",
        "native_bets": 4,
        "lifecycle": "DRY_RUN",
        "adapter_type": "single_bet_only",
        "special_support": True,
    },
    {
        "strategy_id": "midfreq_fourier_mk_3bet",
        "display_name": "MidFreq+Fourier+Markov 3注",
        "native_bets": 3,
        "lifecycle": "DRY_RUN",
        "adapter_type": "single_bet_only",
        "special_support": True,
    },
    {
        "strategy_id": "midfreq_fourier_2bet",
        "display_name": "MidFreq+Fourier 2注",
        "native_bets": 2,
        "lifecycle": "DRY_RUN",
        "adapter_type": "single_bet_only",
        "special_support": True,
    },
    {
        "strategy_id": "cold_complement_2bet",
        "display_name": "Cold Complement 2注",
        "native_bets": 2,
        "lifecycle": "DRY_RUN",
        "adapter_type": "single_bet_only",
        "special_support": True,
    },
    {
        "strategy_id": "fourier30_markov30_2bet",
        "display_name": "Fourier30+Markov30 2注",
        "native_bets": 2,
        "lifecycle": "DRY_RUN",
        "adapter_type": "single_bet_only",
        "special_support": True,
    },
]

# ─── DB Access ────────────────────────────────────────────────────────────────

def load_all_draws() -> List[Dict[str, Any]]:
    """Load all POWER_LOTTO draws ordered by draw number (causal order)."""
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT draw, numbers, special
        FROM draws
        WHERE lottery_type = ?
        ORDER BY CAST(draw AS INTEGER) ASC
    """, (LOTTERY_TYPE,))
    rows = cur.fetchall()
    conn.close()
    draws = []
    for draw_str, numbers_json, special in rows:
        nums = json.loads(numbers_json) if isinstance(numbers_json, str) else numbers_json
        draws.append({
            "draw": str(draw_str),
            "numbers": nums,
            "special": special,
        })
    log.info("Loaded %d POWER_LOTTO draws from DB (latest: %s)", len(draws), draws[-1]["draw"] if draws else "N/A")
    return draws


def load_replay_rows_for_strategy(strategy_id: str) -> Dict[str, Dict[str, Any]]:
    """Load replay rows for a strategy, indexed by target_draw."""
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    cur = conn.cursor()
    cur.execute("""
        SELECT target_draw, predicted_numbers, predicted_special,
               actual_numbers, actual_special, hit_count, special_hit
        FROM strategy_prediction_replays
        WHERE lottery_type = ? AND strategy_id = ?
    """, (LOTTERY_TYPE, strategy_id))
    rows = cur.fetchall()
    conn.close()
    result = {}
    for target_draw, pred_json, pred_spl, act_json, act_spl, hit_count, special_hit in rows:
        result[str(target_draw)] = {
            "predicted": json.loads(pred_json) if isinstance(pred_json, str) else pred_json,
            "predicted_special": pred_spl,
            "actual": json.loads(act_json) if isinstance(act_json, str) else act_json,
            "actual_special": act_spl,
            "hit_count": hit_count or 0,
            "special_hit": special_hit or 0,
        }
    return result


def get_db_baseline_stats() -> Dict[str, Any]:
    """Get production DB baseline stats."""
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    total_rows = cur.fetchone()[0]
    cur.execute("""
        SELECT MAX(CAST(target_draw AS INTEGER))
        FROM strategy_prediction_replays
        WHERE lottery_type = ?
    """, (LOTTERY_TYPE,))
    max_draw = cur.fetchone()[0]
    conn.close()
    return {"total_replay_rows": total_rows, "max_draw": str(max_draw)}

# ─── Multi-bet Adapters ───────────────────────────────────────────────────────

def _get_multibet_function(strategy_id: str):
    """Return a callable(history) -> List[List[int]] for strategies with multibet support."""
    if strategy_id == "power_precision_3bet":
        from tools.predict_power_precision_3bet import generate_power_precision_3bet
        return generate_power_precision_3bet

    if strategy_id == "power_orthogonal_5bet":
        from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
        return generate_orthogonal_5bet

    if strategy_id == "fourier_rhythm_3bet":
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        return lambda history: fourier_rhythm_predict(history, n_bets=3, window=500)

    if strategy_id == "power_fourier_rhythm_2bet":
        from tools.power_fourier_rhythm import fourier_rhythm_predict
        return lambda history: fourier_rhythm_predict(history, n_bets=2, window=500)

    if strategy_id == "zonal_entropy_2bet":
        from tools.predict_power_zonal_entropy import entropy_predict
        return lambda history: entropy_predict(history, n_bets=2)

    return None


def compute_hit(predicted: List[int], actual: List[int]) -> int:
    """Count main number hits (intersection size)."""
    return len(set(predicted) & set(actual))


# ─── Metrics Computation ──────────────────────────────────────────────────────

def compute_metrics_1bet_from_rows(
    strategy_id: str,
    window_draws: List[Dict[str, Any]],
    replay_rows: Dict[str, Dict[str, Any]],
    special_support: bool,
) -> Dict[str, Any]:
    """Compute 1-bet metrics from existing replay rows for the given window draws."""
    hits = []
    special_hits = []
    covered_draws = []

    for d in window_draws:
        draw_id = d["draw"]
        if draw_id in replay_rows:
            row = replay_rows[draw_id]
            hits.append(row["hit_count"])
            special_hits.append(row["special_hit"] if special_support else 0)
            covered_draws.append(draw_id)

    n = len(hits)
    if n == 0:
        return _empty_metrics(reason="no_rows_in_window")

    return _build_metrics(
        hits=hits,
        special_hits=special_hits if special_support else None,
        sample_size=n,
        total_window=len(window_draws),
        covered_draws=covered_draws,
        special_support=special_support,
    )


def compute_metrics_multibet_via_adapter(
    strategy_id: str,
    all_draws: List[Dict[str, Any]],
    window_draws: List[Dict[str, Any]],
    bet_count: int,
    native_bets: int,
) -> Dict[str, Any]:
    """
    Compute multi-bet metrics by generating predictions in memory (no DB writes).
    Causal isolation: history ends BEFORE target draw.
    """
    if bet_count > native_bets:
        return _empty_metrics(reason=f"bet_count_{bet_count}_exceeds_native_{native_bets}")
    if bet_count == 1:
        # 1-bet should be handled by row-based path; this is a fallback
        pass

    gen_fn = _get_multibet_function(strategy_id)
    if gen_fn is None:
        return _empty_metrics(reason="no_multibet_adapter")

    # Build draw index for fast slicing
    draw_to_idx = {d["draw"]: i for i, d in enumerate(all_draws)}

    hits_best = []  # best hit across K bets per draw
    m3plus = 0
    m4plus = 0
    m5plus = 0
    m6plus = 0
    zero_hits = 0
    covered = []

    for target_draw_dict in window_draws:
        target_draw_id = target_draw_dict["draw"]
        target_idx = draw_to_idx.get(target_draw_id)
        if target_idx is None or target_idx == 0:
            continue

        history = all_draws[:target_idx]  # causal slice: BEFORE target draw
        actual_numbers = target_draw_dict["numbers"]

        try:
            all_bets = gen_fn(history)
        except Exception as e:
            log.debug("Strategy %s failed for draw %s: %s", strategy_id, target_draw_id, e)
            continue

        if not all_bets:
            continue

        # Take first bet_count bets (respect native limit)
        bets_to_eval = all_bets[:min(bet_count, len(all_bets))]

        # Compute hits for each bet, track best
        bet_hits = [compute_hit(bet, actual_numbers) for bet in bets_to_eval]
        best_hit = max(bet_hits)

        hits_best.append(best_hit)
        if best_hit == 0:
            zero_hits += 1
        if best_hit >= 3:
            m3plus += 1
        if best_hit >= 4:
            m4plus += 1
        if best_hit >= 5:
            m5plus += 1
        if best_hit == 6:
            m6plus += 1
        covered.append(target_draw_id)

    n = len(hits_best)
    if n == 0:
        return _empty_metrics(reason="no_predictions_generated")

    avg_hit = sum(hits_best) / n
    return {
        "sample_size": n,
        "total_window": len(window_draws),
        "coverage_pct": round(100.0 * n / len(window_draws), 2),
        "avg_best_main_hit": round(avg_hit, 4),
        "m3plus_rate": round(m3plus / n, 4),
        "m4plus_rate": round(m4plus / n, 4),
        "m5plus_rate": round(m5plus / n, 4),
        "m6_rate": round(m6plus / n, 4),
        "zero_hit_rate": round(zero_hits / n, 4),
        "special_support": False,
        "special_hit_rate": None,
        "blocker": None,
        "latest_draw_covered": covered[-1] if covered else None,
        "source": "multibet_adapter",
    }


def _build_metrics(
    hits: List[int],
    special_hits: Optional[List[int]],
    sample_size: int,
    total_window: int,
    covered_draws: List[str],
    special_support: bool,
) -> Dict[str, Any]:
    n = sample_size
    m3plus = sum(1 for h in hits if h >= 3)
    m4plus = sum(1 for h in hits if h >= 4)
    m5plus = sum(1 for h in hits if h >= 5)
    m6plus = sum(1 for h in hits if h == 6)
    zero_hits = sum(1 for h in hits if h == 0)
    avg_hit = sum(hits) / n

    spl_rate = None
    if special_support and special_hits:
        spl_rate = round(sum(special_hits) / n, 4)

    return {
        "sample_size": n,
        "total_window": total_window,
        "coverage_pct": round(100.0 * n / total_window, 2),
        "avg_best_main_hit": round(avg_hit, 4),
        "m3plus_rate": round(m3plus / n, 4),
        "m4plus_rate": round(m4plus / n, 4),
        "m5plus_rate": round(m5plus / n, 4),
        "m6_rate": round(m6plus / n, 4),
        "zero_hit_rate": round(zero_hits / n, 4),
        "special_support": special_support,
        "special_hit_rate": spl_rate,
        "blocker": None,
        "latest_draw_covered": covered_draws[-1] if covered_draws else None,
        "source": "replay_rows",
    }


def _empty_metrics(reason: str) -> Dict[str, Any]:
    return {
        "sample_size": 0,
        "total_window": 0,
        "coverage_pct": 0.0,
        "avg_best_main_hit": None,
        "m3plus_rate": None,
        "m4plus_rate": None,
        "m5plus_rate": None,
        "m6_rate": None,
        "zero_hit_rate": None,
        "special_support": False,
        "special_hit_rate": None,
        "blocker": reason,
        "latest_draw_covered": None,
        "source": "N/A",
    }


# ─── Ranking ──────────────────────────────────────────────────────────────────

def rank_strategies(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank strategies by:
      Primary:   m3plus_rate (higher = better)
      Tie-1:     avg_best_main_hit (higher = better)
      Tie-2:     m4plus_rate (higher = better)
      Tie-3:     special_hit_rate (higher = better, None treated as 0)
      Tie-4:     zero_hit_rate (lower = better)
      Tie-5:     sample_size (higher = better)
    """
    def sort_key(r):
        m = r["metrics"]
        if m["m3plus_rate"] is None:
            return (-1, -1, -1, -1, 1, -1)
        return (
            -(m["m3plus_rate"] or 0),
            -(m["avg_best_main_hit"] or 0),
            -(m["m4plus_rate"] or 0),
            -(m["special_hit_rate"] or 0),
            (m["zero_hit_rate"] or 0),
            -(m["sample_size"] or 0),
        )

    valid = [r for r in results if r["metrics"]["m3plus_rate"] is not None and r["metrics"]["sample_size"] > 0]
    invalid = [r for r in results if r["metrics"]["m3plus_rate"] is None or r["metrics"]["sample_size"] == 0]
    ranked_valid = sorted(valid, key=sort_key)
    return ranked_valid + invalid


# ─── Main Benchmark ───────────────────────────────────────────────────────────

def run_benchmark() -> Dict[str, Any]:
    log.info("=== P94B POWER_LOTTO All-Strategy BetCount Benchmark ===")

    # Pre-flight: verify DB
    baseline = get_db_baseline_stats()
    log.info("DB baseline: total_replay_rows=%d, max_draw=%s",
             baseline["total_replay_rows"], baseline["max_draw"])

    all_draws = load_all_draws()
    total_draws = len(all_draws)
    log.info("Total POWER_LOTTO draws: %d", total_draws)

    # Pre-load all replay rows per strategy
    log.info("Pre-loading replay rows for %d strategies...", len(STRATEGY_CATALOG))
    replay_rows_cache: Dict[str, Dict[str, Dict]] = {}
    for sc in STRATEGY_CATALOG:
        sid = sc["strategy_id"]
        replay_rows_cache[sid] = load_replay_rows_for_strategy(sid)
        log.info("  %s: %d rows", sid, len(replay_rows_cache[sid]))

    # Build results structure
    all_results: Dict[str, Any] = {
        "meta": {
            "task": "P94B_POWER_LOTTO_ALL_STRATEGY_BETCOUNT_BENCHMARK",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_baseline": baseline,
            "total_draws_in_db": total_draws,
            "latest_draw": all_draws[-1]["draw"] if all_draws else None,
            "oldest_draw": all_draws[0]["draw"] if all_draws else None,
            "strategy_count": len(STRATEGY_CATALOG),
            "bet_counts_evaluated": BET_COUNTS,
            "observation_windows": WINDOWS,
        },
        "strategies": [
            {
                "strategy_id": sc["strategy_id"],
                "display_name": sc["display_name"],
                "native_bets": sc["native_bets"],
                "lifecycle": sc["lifecycle"],
                "adapter_type": sc["adapter_type"],
                "special_support": sc["special_support"],
            }
            for sc in STRATEGY_CATALOG
        ],
        "window_results": {},
        "rankings": {},
    }

    # Evaluate each window × bet_count × strategy
    for window_size in WINDOWS:
        log.info("--- Window=%d ---", window_size)
        window_draws = all_draws[-window_size:] if len(all_draws) >= window_size else all_draws
        actual_window = len(window_draws)
        log.info("  Actual draws in window: %d", actual_window)

        window_key = f"window_{window_size}"
        all_results["window_results"][window_key] = {
            "window_size": window_size,
            "actual_draws": actual_window,
            "first_draw": window_draws[0]["draw"] if window_draws else None,
            "last_draw": window_draws[-1]["draw"] if window_draws else None,
            "bet_count_results": {},
        }
        all_results["rankings"][window_key] = {}

        for bet_count in BET_COUNTS:
            bc_key = f"bet_{bet_count}"
            log.info("  BetCount=%d", bet_count)
            bet_results = []

            for sc in STRATEGY_CATALOG:
                sid = sc["strategy_id"]
                native_bets = sc["native_bets"]
                adapter_type = sc["adapter_type"]
                special_support = sc["special_support"]

                if bet_count > native_bets:
                    # Can't evaluate more bets than strategy generates
                    metrics = _empty_metrics(
                        reason=f"bet_count_{bet_count}_exceeds_native_{native_bets}"
                    )
                elif bet_count == 1:
                    # Always use replay rows for 1-bet evaluation
                    metrics = compute_metrics_1bet_from_rows(
                        sid, window_draws, replay_rows_cache[sid], special_support
                    )
                else:
                    # Multi-bet: use adapter if available
                    if adapter_type == "multibet_tool":
                        log.info("    [%s] bet_count=%d via adapter (window=%d draws)", sid, bet_count, actual_window)
                        metrics = compute_metrics_multibet_via_adapter(
                            sid, all_draws, window_draws, bet_count, native_bets
                        )
                    else:
                        # single_bet_only adapter: cannot compute multi-bet
                        metrics = _empty_metrics(
                            reason=f"single_bet_only_adapter_no_bet{bet_count}_support"
                        )

                bet_results.append({
                    "strategy_id": sid,
                    "display_name": sc["display_name"],
                    "lifecycle": sc["lifecycle"],
                    "native_bets": native_bets,
                    "bet_count_evaluated": bet_count,
                    "metrics": metrics,
                })

            all_results["window_results"][window_key]["bet_count_results"][bc_key] = bet_results

            # Rank and store top 3
            ranked = rank_strategies(bet_results)
            top3 = []
            for rank_pos, r in enumerate(ranked[:3], start=1):
                m = r["metrics"]
                if m["m3plus_rate"] is None:
                    break
                top3.append({
                    "rank": rank_pos,
                    "strategy_id": r["strategy_id"],
                    "display_name": r["display_name"],
                    "lifecycle": r["lifecycle"],
                    "bet_count": bet_count,
                    "sample_size": m["sample_size"],
                    "coverage_pct": m["coverage_pct"],
                    "avg_best_main_hit": m["avg_best_main_hit"],
                    "m3plus_rate": m["m3plus_rate"],
                    "m4plus_rate": m["m4plus_rate"],
                    "m5plus_rate": m["m5plus_rate"],
                    "special_hit_rate": m["special_hit_rate"],
                    "zero_hit_rate": m["zero_hit_rate"],
                })

            all_results["rankings"][window_key][bc_key] = {
                "window_size": window_size,
                "bet_count": bet_count,
                "top3": top3,
            }
            log.info("    Rankings done. Top-1: %s (m3+: %.1f%%)",
                     top3[0]["strategy_id"] if top3 else "N/A",
                     (top3[0]["m3plus_rate"] * 100) if top3 else 0)

    # Determine classification
    # Count how many window×bet_count combinations have at least 3 ranked strategies
    total_combinations = len(WINDOWS) * len(BET_COUNTS)
    covered_combinations = sum(
        1
        for wk in all_results["rankings"].values()
        for bk in wk.values()
        if len(bk["top3"]) >= 1
    )
    classification = (
        "P94B_POWER_LOTTO_ALL_STRATEGY_BETCOUNT_BENCHMARK_READY"
        if covered_combinations == total_combinations
        else "P94B_POWER_LOTTO_BENCHMARK_PARTIAL_WITH_BLOCKERS"
    )
    all_results["meta"]["classification"] = classification
    all_results["meta"]["covered_combinations"] = covered_combinations
    all_results["meta"]["total_combinations"] = total_combinations

    log.info("Classification: %s (%d/%d combinations covered)",
             classification, covered_combinations, total_combinations)
    return all_results


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main():
    results = run_benchmark()

    # Write JSON output
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    log.info("JSON output: %s", OUTPUT_JSON)

    # Print summary table
    print("\n" + "=" * 80)
    print("P94B POWER_LOTTO ALL-STRATEGY BETCOUNT BENCHMARK — SUMMARY")
    print("=" * 80)
    print(f"Classification: {results['meta']['classification']}")
    print(f"Total draws: {results['meta']['total_draws_in_db']} | Latest: {results['meta']['latest_draw']}")
    print(f"DB rows: {results['meta']['db_baseline']['total_replay_rows']}")
    print()

    for window_size in WINDOWS:
        wk = f"window_{window_size}"
        rankings = results["rankings"][wk]
        print(f"{'─'*70}")
        print(f"Observation Window: {window_size} draws")
        print(f"{'─'*70}")
        for bet_count in BET_COUNTS:
            bk = f"bet_{bet_count}"
            top3 = rankings[bk]["top3"]
            print(f"  Bet={bet_count}: ", end="")
            if not top3:
                print("(no strategies evaluated)")
                continue
            print()
            for r in top3:
                print(f"    #{r['rank']} {r['strategy_id']:<35} "
                      f"M3+={r['m3plus_rate']*100:.1f}% "
                      f"avgHit={r['avg_best_main_hit']:.3f} "
                      f"n={r['sample_size']}")
        print()

    print(f"Output: {OUTPUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
