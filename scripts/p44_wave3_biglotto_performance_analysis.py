"""
P44 Wave 3 BIG_LOTTO Performance Analysis
Read-only — no DB writes.

Analyzes 6 Wave 3 BIG_LOTTO DRY_RUN strategies:
  markov_single_biglotto, markov_2bet_biglotto, bet2_fourier_expansion_biglotto,
  fourier30_markov30_biglotto, cold_complement_biglotto, coldpool15_biglotto

Three-window metrics: 150 / 500 / 1500 rows
Edge vs BIG_LOTTO baseline (6/49 = 0.7347), permutation test (MC null), Sharpe-like.
Per L91: BIG_LOTTO 49C6 signal space is exhausted — near-random expected.
"""

import sqlite3
import json
import random
import math
from datetime import datetime
from pathlib import Path


def _repo_root():
    return Path(__file__).resolve().parent.parent


def _canonical_db_path():
    return _repo_root() / "lottery_api" / "data" / "lottery_v2.db"


def _resolve_db_path(db_path=None):
    candidate = _canonical_db_path() if db_path is None else Path(db_path)
    if db_path is not None and not candidate.is_absolute():
        raise ValueError("db_path must be absolute; use None for the canonical lottery_v2.db")
    if not candidate.exists():
        raise FileNotFoundError(f"Lottery DB path does not exist: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Lottery DB path is not a regular file: {candidate}")
    return str(candidate)

DB_PATH = None

WAVE3_STRATEGIES = [
    "markov_single_biglotto",
    "markov_2bet_biglotto",
    "bet2_fourier_expansion_biglotto",
    "fourier30_markov30_biglotto",
    "cold_complement_biglotto",
    "coldpool15_biglotto",
]

# BIG_LOTTO 6/49: expected average hits per draw = 6 * 6/49
BIGLOTTO_BASELINE_HIT_RATE = 6 * 6 / 49  # ≈ 0.7347
BIGLOTTO_POOL = 49
BIGLOTTO_PICK = 6
WINDOWS = [150, 500, 1500]
N_PERM = 2000


def load_rows(conn, strategy_id):
    """Load all rows for strategy, ordered by draw number ascending (CAST to INT)."""
    rows = conn.execute(
        """SELECT target_draw, target_date, hit_count, special_hit
           FROM strategy_prediction_replays
           WHERE strategy_id = ?
           ORDER BY CAST(target_draw AS INTEGER) ASC""",
        (strategy_id,)
    ).fetchall()
    return rows


def perm_test_mc(hit_counts, n_perm=N_PERM, seed=42):
    """
    Monte Carlo permutation test under null hypothesis.
    Null: each draw hit_count ~ Binomial(BIGLOTTO_PICK, BIGLOTTO_PICK/BIGLOTTO_POOL).
    p_value = P(null_mean >= observed_mean).
    """
    n = len(hit_counts)
    if n == 0:
        return 1.0
    observed_mean = sum(hit_counts) / n
    p_per_ball = BIGLOTTO_PICK / BIGLOTTO_POOL  # 6/49

    rng = random.Random(seed)
    null_means = []
    for _ in range(n_perm):
        sample_hits = 0
        for _ in range(n * BIGLOTTO_PICK):
            if rng.random() < p_per_ball:
                sample_hits += 1
        # Each draw contributes BIGLOTTO_PICK independent Bernoulli trials
        # Total hits / n = mean hits per draw
        null_means.append(sample_hits / n)

    p_value = sum(1 for nm in null_means if nm >= observed_mean) / n_perm
    return p_value


def compute_metrics(rows, window_size):
    """Compute performance metrics for last `window_size` rows."""
    if not rows:
        return None
    subset = rows[-window_size:] if len(rows) >= window_size else rows
    n = len(subset)

    hit_counts = [int(r["hit_count"] or 0) for r in subset]
    special_hits = [int(r["special_hit"] or 0) for r in subset]

    avg_hits = sum(hit_counts) / n
    edge = avg_hits - BIGLOTTO_BASELINE_HIT_RATE
    edge_pct = (edge / BIGLOTTO_BASELINE_HIT_RATE) * 100

    # Hit distribution
    dist = {"0": 0, "1": 0, "2": 0, "3": 0, "4+": 0}
    for hc in hit_counts:
        if hc >= 4:
            dist["4+"] += 1
        elif hc == 3:
            dist["3"] += 1
        elif hc == 2:
            dist["2"] += 1
        elif hc == 1:
            dist["1"] += 1
        else:
            dist["0"] += 1
    dist_rates = {k: round(v / n, 4) for k, v in dist.items()}

    # Sharpe-like: (mean - baseline) / std_of_hits
    if n > 1:
        variance = sum((hc - avg_hits) ** 2 for hc in hit_counts) / (n - 1)
        std = math.sqrt(variance) if variance > 0 else 1e-6
        sharpe = (avg_hits - BIGLOTTO_BASELINE_HIT_RATE) / std
    else:
        sharpe = 0.0

    # Special hit rate
    special_hit_rate = sum(special_hits) / n

    # Permutation test
    p_value = perm_test_mc(hit_counts, n_perm=N_PERM, seed=42)

    # t-statistic (one-sample t-test vs baseline)
    if n > 1:
        se = std / math.sqrt(n)
        t_stat = (avg_hits - BIGLOTTO_BASELINE_HIT_RATE) / se if se > 0 else 0.0
    else:
        t_stat = 0.0

    return {
        "window": window_size,
        "n_rows": n,
        "avg_hit_count": round(avg_hits, 4),
        "baseline_hit_rate": round(BIGLOTTO_BASELINE_HIT_RATE, 4),
        "edge": round(edge, 4),
        "edge_pct": round(edge_pct, 2),
        "sharpe": round(sharpe, 4),
        "t_stat": round(t_stat, 4),
        "special_hit_rate": round(special_hit_rate, 4),
        "hit_distribution": dist_rates,
        "perm_p_value": round(p_value, 4),
        "perm_gate": "PASS" if p_value < 0.05 else "FAIL",
    }


def analyze_strategy(conn, strategy_id):
    rows = load_rows(conn, strategy_id)
    total_rows = len(rows)

    windows = {}
    for w in WINDOWS:
        result = compute_metrics(rows, w)
        windows[str(w)] = result

    # Three-window criteria: all edges positive + best p < 0.05
    valid_windows = [windows[str(w)] for w in WINDOWS if windows[str(w)] is not None]
    all_edge_positive = all(m["edge"] > 0 for m in valid_windows)
    best_p = min(m["perm_p_value"] for m in valid_windows) if valid_windows else 1.0
    three_window_consistent = all_edge_positive

    if all_edge_positive and best_p < 0.05:
        recommendation = "promotion_consideration"
        promotion_candidate = True
    elif all_edge_positive:
        recommendation = "monitor_longer"
        promotion_candidate = False
    elif best_p < 0.05:
        recommendation = "manual_review"
        promotion_candidate = False
    else:
        recommendation = "keep_dry_run"
        promotion_candidate = False

    return {
        "strategy_id": strategy_id,
        "total_rows": total_rows,
        "windows": windows,
        "three_window_consistent": three_window_consistent,
        "best_perm_p_value": round(best_p, 4),
        "promotion_candidate": promotion_candidate,
        "promotion_reason": recommendation,
        "mcnemar_gate": "INCONCLUSIVE_NO_BASELINE_STRATEGY",
        "note_l91": "BIG_LOTTO 49C6 signal boundary exhausted per L91 — near-random expected",
    }


def main():
    conn = sqlite3.connect(_resolve_db_path(DB_PATH))
    conn.row_factory = sqlite3.Row

    # Verify production row count before analysis
    total_rows_db = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    results = {}
    for sid in WAVE3_STRATEGIES:
        print(f"Analyzing {sid}...")
        results[sid] = analyze_strategy(conn, sid)

    conn.close()

    promotion_candidates = [sid for sid, r in results.items() if r["promotion_candidate"]]
    keep_dry_run = [sid for sid, r in results.items() if not r["promotion_candidate"]]

    output = {
        "p44_version": "20260523",
        "analysis_date": datetime.utcnow().isoformat() + "Z",
        "production_rows_verified": total_rows_db,
        "wave3_strategies_analyzed": len(WAVE3_STRATEGIES),
        "lottery_type": "BIG_LOTTO",
        "baseline_hit_rate": round(BIGLOTTO_BASELINE_HIT_RATE, 4),
        "baseline_formula": "6 * 6/49 = 0.7347 (BIG_LOTTO 6/49 expected avg hits per draw)",
        "analysis_note": (
            "Wave 3 BIG_LOTTO strategies use DRY_RUN rows (replay_status=PREDICTED, dry_run=0). "
            "Per L91, BIG_LOTTO 49C6 pool is near-random — all 7 signals exhausted with zero p<0.05 in prior research."
        ),
        "permutation_test_config": {
            "method": "Monte Carlo null (Binomial draws)",
            "n_perm": N_PERM,
            "seed": 42,
            "null_model": f"hit_count ~ Binomial({BIGLOTTO_PICK}, {BIGLOTTO_PICK}/{BIGLOTTO_POOL})",
        },
        "strategies": results,
        "promotion_candidates": promotion_candidates,
        "keep_dry_run": keep_dry_run,
        "classification": "P44_WAVE3_BIGLOTTO_PERFORMANCE_ANALYSIS_MERGED_TO_MAIN",
    }

    out_path = "outputs/replay/p44_wave3_biglotto_performance_analysis_20260523.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n=== P44 Analysis Complete ===")
    print(f"Production rows verified: {total_rows_db}")
    print(f"Baseline hit rate: {BIGLOTTO_BASELINE_HIT_RATE:.4f}")
    print(f"Promotion candidates: {promotion_candidates}")
    print(f"Keep DRY_RUN: {keep_dry_run}")
    print(f"\nPer-strategy summary (1500-window):")
    for sid, r in results.items():
        w1500 = r["windows"].get("1500")
        if w1500:
            print(
                f"  {sid}: edge={w1500['edge']:+.4f} ({w1500['edge_pct']:+.2f}%) "
                f"perm_p={w1500['perm_p_value']:.4f} gate={w1500['perm_gate']} "
                f"sharpe={w1500['sharpe']:.4f}"
            )
    print(f"\nOutput: {out_path}")
    return output


if __name__ == "__main__":
    main()
