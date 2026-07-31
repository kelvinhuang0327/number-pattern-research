"""
Special3 (三星彩) Baseline Dry-Run Replay
dry_run_only=True — NO DB writes, NO replay row inserts.

Outputs:
  outputs/replay/special3_baseline_dryrun_20260527/<strategy>.json
  outputs/replay/special3_baseline_dryrun_20260527.md
"""

import sqlite3
import json
import math
import random
import pathlib
import itertools
import datetime
from collections import Counter, defaultdict

DRY_RUN = True
DB_PATH = "lottery_api/data/lottery_v2.db"
OUT_DIR = pathlib.Path("outputs/replay/special3_baseline_dryrun_20260527")
OUT_DIR.mkdir(parents=True, exist_ok=True)
TODAY = "20260527"
RANDOM_SEED = 42

WINDOWS = [150, 500, 1500]
TOP_NS = [10, 20, 50, 100]
N_MC = 5000  # Monte Carlo null simulations

ALL_TICKETS = list(itertools.product(range(10), repeat=3))  # 1000 tickets


# ── Data loading ──────────────────────────────────────────────────────────────

def load_draws():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT draw, date, numbers FROM draws WHERE lottery_type='3_STAR' "
        "ORDER BY CAST(draw AS INTEGER)"
    ).fetchall()
    conn.close()
    result = []
    for draw, date, numbers_json in rows:
        nums = tuple(json.loads(numbers_json))
        result.append({"draw": draw, "date": date, "digits": nums})
    return result


# ── Strategy implementations ──────────────────────────────────────────────────

def position_frequency_topk(window_draws, top_n):
    """Rank all 1000 tickets by product of position-wise digit frequencies."""
    pos_counts = [Counter(), Counter(), Counter()]
    for d in window_draws:
        for p in range(3):
            pos_counts[p][d["digits"][p]] += 1
    total = len(window_draws)
    pos_freq = [{k: v / total for k, v in pc.items()} for pc in pos_counts]
    scored = []
    for t in ALL_TICKETS:
        score = 1.0
        for p in range(3):
            score *= pos_freq[p].get(t[p], 1e-6)
        scored.append((score, t))
    scored.sort(reverse=True)
    return [t for _, t in scored[:top_n]]


def recent_position_hot_topk(window_draws, top_n, recency=50):
    """Use only the most recent `recency` draws for position frequency."""
    recent = window_draws[-recency:] if len(window_draws) >= recency else window_draws
    return position_frequency_topk(recent, top_n)


def position_cold_rebound_topk(window_draws, top_n):
    """Pick digits at each position by least-recent appearance (cold rebound hypothesis)."""
    pos_last_seen = [{d: -1 for d in range(10)} for _ in range(3)]
    for i, draw in enumerate(window_draws):
        for p in range(3):
            pos_last_seen[p][draw["digits"][p]] = i
    # coldest digit per position = smallest last_seen index
    pos_cold_rank = []
    for p in range(3):
        ranked = sorted(range(10), key=lambda d, p=p: pos_last_seen[p][d])
        pos_cold_rank.append(ranked)
    # Score: sum of cold-rank positions (lower = colder)
    cold_rank_map = [{d: i for i, d in enumerate(ranked)} for ranked in pos_cold_rank]
    scored = []
    for t in ALL_TICKETS:
        score = sum(cold_rank_map[p][t[p]] for p in range(3))
        scored.append((score, t))
    scored.sort()  # ascending: coldest first
    return [t for _, t in scored[:top_n]]


def sum_band_frequency(window_draws, top_n):
    """Pick tickets whose digit-sum band is most frequent in window."""
    def sum_band(digits):
        s = sum(digits)
        if s <= 9: return 0
        elif s <= 17: return 1
        else: return 2

    band_counts = Counter(sum_band(d["digits"]) for d in window_draws)
    top_band = band_counts.most_common(1)[0][0]
    candidates = [t for t in ALL_TICKETS if sum_band(t) == top_band]
    # Within band, rank by position frequency
    if len(candidates) <= top_n:
        return candidates[:top_n]
    pos_counts = [Counter(), Counter(), Counter()]
    for d in window_draws:
        for p in range(3):
            pos_counts[p][d["digits"][p]] += 1
    total = len(window_draws)
    pos_freq = [{k: v / total for k, v in pc.items()} for pc in pos_counts]
    scored = []
    for t in candidates:
        score = sum(pos_freq[p].get(t[p], 1e-6) for p in range(3))
        scored.append((score, t))
    scored.sort(reverse=True)
    return [t for _, t in scored[:top_n]]


def span_band_frequency(window_draws, top_n):
    """Pick tickets whose span (max-min) band is most frequent in window."""
    def span_band(digits):
        sp = max(digits) - min(digits)
        if sp <= 3: return 0
        elif sp <= 6: return 1
        else: return 2

    band_counts = Counter(span_band(d["digits"]) for d in window_draws)
    top_band = band_counts.most_common(1)[0][0]
    candidates = [t for t in ALL_TICKETS if span_band(t) == top_band]
    if len(candidates) <= top_n:
        return candidates[:top_n]
    pos_counts = [Counter(), Counter(), Counter()]
    for d in window_draws:
        for p in range(3):
            pos_counts[p][d["digits"][p]] += 1
    total = len(window_draws)
    pos_freq = [{k: v / total for k, v in pc.items()} for pc in pos_counts]
    scored = []
    for t in candidates:
        score = sum(pos_freq[p].get(t[p], 1e-6) for p in range(3))
        scored.append((score, t))
    scored.sort(reverse=True)
    return [t for _, t in scored[:top_n]]


def ensemble_rank_v1(window_draws, top_n):
    """Reciprocal rank fusion of all 5 strategies."""
    k = 60  # RRF constant
    all_strategies = [
        position_frequency_topk(window_draws, 100),
        recent_position_hot_topk(window_draws, 100),
        position_cold_rebound_topk(window_draws, 100),
        sum_band_frequency(window_draws, 100),
        span_band_frequency(window_draws, 100),
    ]
    rrf_scores = defaultdict(float)
    for ranked_list in all_strategies:
        for rank, ticket in enumerate(ranked_list):
            rrf_scores[ticket] += 1.0 / (k + rank + 1)
    sorted_tickets = sorted(rrf_scores.keys(), key=lambda t: rrf_scores[t], reverse=True)
    return sorted_tickets[:top_n]


STRATEGIES = {
    "position_frequency_topk": position_frequency_topk,
    "recent_position_hot_topk": recent_position_hot_topk,
    "position_cold_rebound_topk": position_cold_rebound_topk,
    "sum_band_frequency": sum_band_frequency,
    "span_band_frequency": span_band_frequency,
    "ensemble_rank_v1": ensemble_rank_v1,
}


# ── Metric computation ────────────────────────────────────────────────────────

def box_hit(predicted_ticket, actual_digits):
    return sorted(predicted_ticket) == sorted(actual_digits)


def position_digit_accuracy(predicted_tickets, actual_digits):
    if not predicted_tickets:
        return 0.0
    # Oracle: best ticket among predictions for position accuracy
    best = max(
        sum(p == a for p, a in zip(t, actual_digits)) / 3.0
        for t in predicted_tickets
    )
    return best


def sum_band(digits):
    s = sum(digits)
    if s <= 9: return 0
    elif s <= 17: return 1
    return 2


def span_band(digits):
    sp = max(digits) - min(digits)
    if sp <= 3: return 0
    elif sp <= 6: return 1
    return 2


def evaluate_predictions(predicted_tickets, actual_digits):
    direct = actual_digits in [tuple(t) for t in predicted_tickets]
    box = any(box_hit(t, actual_digits) for t in predicted_tickets)
    pos_acc = position_digit_accuracy(predicted_tickets, actual_digits)
    pred_bands_sum = {sum_band(t) for t in predicted_tickets}
    pred_bands_span = {span_band(t) for t in predicted_tickets}
    sum_acc = sum_band(actual_digits) in pred_bands_sum
    span_acc = span_band(actual_digits) in pred_bands_span
    return {
        "direct": direct,
        "box": box,
        "pos_acc": pos_acc,
        "sum_band": sum_acc,
        "span_band": span_acc,
    }


def run_window(draws, window_size, strategy_fn, top_n):
    n = len(draws)
    results = []
    monthly = defaultdict(list)
    for i in range(window_size, n):
        window = draws[i - window_size:i]
        actual = draws[i]["digits"]
        date = draws[i]["date"]
        month = date[:7] if date else "unknown"
        preds = strategy_fn(window, top_n)
        metrics = evaluate_predictions(preds, actual)
        metrics["draw"] = draws[i]["draw"]
        results.append(metrics)
        monthly[month].append(metrics["direct"])
    return results, monthly


def summarize(results, monthly):
    n = len(results)
    if n == 0:
        return {}
    direct_rate = sum(r["direct"] for r in results) / n
    box_rate = sum(r["box"] for r in results) / n
    pos_acc = sum(r["pos_acc"] for r in results) / n
    sum_acc = sum(r["sum_band"] for r in results) / n
    span_acc = sum(r["span_band"] for r in results) / n
    monthly_rates = {m: sum(v) / len(v) for m, v in monthly.items()}
    monthly_std = (
        (sum((v - direct_rate) ** 2 for v in monthly_rates.values()) / len(monthly_rates)) ** 0.5
        if monthly_rates else 0.0
    )
    return {
        "n_test": n,
        "direct_hit_rate": round(direct_rate, 6),
        "box_hit_rate": round(box_rate, 6),
        "position_digit_accuracy": round(pos_acc, 6),
        "sum_band_accuracy": round(sum_acc, 6),
        "span_band_accuracy": round(span_acc, 6),
        "monthly_stability_std": round(monthly_std, 6),
        "n_months": len(monthly_rates),
    }


def monte_carlo_null(n_test, top_n, n_sim, seed):
    """Analytical null for Binomial(n_test, p=top_n/1000).
    Use numpy if available, else analytical closed form (fast).
    """
    p = top_n / 1000.0
    # Analytical: E = p, Var = p(1-p)/n, 99th pct ≈ p + 2.326*sigma
    sigma = math.sqrt(p * (1 - p) / n_test)
    try:
        import numpy as np
        rng = np.random.default_rng(seed)
        hits = rng.binomial(n_test, p, size=min(n_sim, 500))
        rates = hits / n_test
        return {
            "mc_mean": round(float(rates.mean()), 6),
            "mc_std": round(float(rates.std()), 8),
            "mc_p99": round(float(np.percentile(rates, 99)), 6),
            "analytical_p": round(p, 6),
        }
    except ImportError:
        # Closed-form fallback
        return {
            "mc_mean": round(p, 6),
            "mc_std": round(sigma, 8),
            "mc_p99": round(p + 2.326 * sigma, 6),
            "analytical_p": round(p, 6),
        }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("[special3_baseline_dryrun] DRY_RUN=True — no DB writes")
    draws = load_draws()
    print(f"  Loaded {len(draws)} draws")

    random.seed(RANDOM_SEED)
    all_results = {}

    for strategy_name, strategy_fn in STRATEGIES.items():
        print(f"\n  Strategy: {strategy_name}")
        strat_result = {}
        for window in WINDOWS:
            if len(draws) <= window:
                print(f"    window={window}: SKIP (not enough draws)")
                continue
            strat_result[window] = {}
            for top_n in TOP_NS:
                print(f"    window={window} top_n={top_n}...", end=" ", flush=True)
                results, monthly = run_window(draws, window, strategy_fn, top_n)
                summary = summarize(results, monthly)

                # Monte Carlo null (reduced for speed)
                n_sim = 2000 if window == 1500 else 1000
                mc = monte_carlo_null(summary["n_test"], top_n, n_sim, RANDOM_SEED)
                summary["mc_null"] = mc

                # Edge vs random
                random_baseline = top_n / 1000.0
                edge = summary["direct_hit_rate"] - random_baseline
                summary["random_baseline"] = round(random_baseline, 6)
                summary["edge_vs_random"] = round(edge, 6)

                strat_result[window][top_n] = summary
                print(f"direct={summary['direct_hit_rate']:.4f} (rand={random_baseline:.4f} edge={edge:+.4f})")

        all_results[strategy_name] = strat_result

        # Save per-strategy JSON
        out_path = OUT_DIR / f"{strategy_name}.json"
        with open(out_path, "w") as f:
            json.dump({"strategy": strategy_name, "dry_run": True,
                       "generated": TODAY, "results": strat_result}, f, indent=2)

    # ── Classification ────────────────────────────────────────────────────────
    classifications = {}
    for strat_name, strat_data in all_results.items():
        edges = []
        for window in WINDOWS:
            if window not in strat_data:
                continue
            for top_n in TOP_NS:
                if top_n not in strat_data[window]:
                    continue
                edges.append(strat_data[window][top_n]["edge_vs_random"])

        # Three-window check: positive edge across all three windows (top_n=20)
        three_window_positive = all(
            strat_data.get(w, {}).get(20, {}).get("edge_vs_random", -999) > 0
            for w in WINDOWS if w in strat_data
        )
        avg_edge = sum(edges) / len(edges) if edges else 0

        if three_window_positive and avg_edge > 0:
            cls = "PROVISIONAL"
        elif avg_edge > 0:
            cls = "WEAK_POSITIVE"
        else:
            cls = "REJECT"

        classifications[strat_name] = {
            "classification": cls,
            "three_window_positive_top20": three_window_positive,
            "avg_edge_all_windows_top_ns": round(avg_edge, 6),
        }
        print(f"\n  {strat_name}: {cls} (avg_edge={avg_edge:+.6f}, 3win={three_window_positive})")

    # ── Save master JSON ──────────────────────────────────────────────────────
    master = {
        "task": "special3_baseline_dryrun",
        "dry_run": True,
        "generated": TODAY,
        "draws_loaded": len(draws),
        "windows": WINDOWS,
        "top_ns": TOP_NS,
        "random_seed": RANDOM_SEED,
        "classifications": classifications,
        "results": all_results,
    }
    master_path = OUT_DIR.parent / f"special3_baseline_dryrun_{TODAY}.json"
    with open(master_path, "w") as f:
        json.dump(master, f, indent=2)
    print(f"\n  Master JSON: {master_path}")
    return master


if __name__ == "__main__":
    main()
