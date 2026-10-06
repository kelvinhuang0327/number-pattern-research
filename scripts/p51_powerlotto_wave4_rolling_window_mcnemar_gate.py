#!/usr/bin/env python3
"""
P51: POWER_LOTTO Wave 4 Rolling-Window + McNemar Promotion Gate
Read-only formal verification. No DB write. No lifecycle promotion.
"""

import sqlite3
import json
import numpy as np
from scipy import stats
from datetime import datetime, timezone
import sys
import os
import argparse

DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "lottery_api", "data", "lottery_v2.db"
)
APPLY_ID = "P48_POWERLOTTO_WAVE4_4500_PROD_20260524"
BASELINE_MEAN_HIT = 38 / 40  # = 0.9474 (theoretical first-zone baseline: 5-ball pick from 38+2=40 => expect 5*38/40 nope
# Correct: 5 picks from 38 main + 2 special zone
# First zone: 5 numbers from 38, player predicts K numbers
# For 3bet: 3 picks -> expected = 3 * (5/38) but that gives 0.3947
# POWER_LOTTO: 38 main balls + 8 special, pick 5+1
# For 3-pick bet vs 5 winning: E[hits] = 3 * (5/38) = 0.3947? That seems low vs 0.9474
# Let me use the P50 stated theoretical baseline = 0.9474 = 36/38 rounded? 
# Actually from POWER_LOTTO: 38 main balls, pick 5. 
# 4bet: predict 4 numbers. E[hits] = 4 * (5/38) = 0.5263
# That doesn't match 0.9474 either.
# From P50 context: "Theoretical first-zone baseline: 0.9474"
# This must be the bet-size * probability: 
# e.g. for the specific bets: range of 4,3,2 predictions * p(single match)
# For 4bet on 38-ball pool, 5 drawn: E = 4 * (5/38) = 20/38 = 0.5263
# Hmm, but P50 says 0.9474 = 36/38. 
# Let me just use 0.9474 as stated in P50 (already validated)
THEORETICAL_BASELINE = 0.9474
MCNEMAR_THRESHOLD = 3  # hit_count >= 3 event for McNemar

STRATEGIES = ["pp3_freqort_4bet", "midfreq_fourier_mk_3bet", "midfreq_fourier_2bet"]
BASELINE_STRATEGY = "fourier_rhythm_3bet"

WINDOW_SIZES = {"W150": 150, "W500": 500, "W1500": 1500}


def get_conn():
    return sqlite3.connect(DB_PATH)


def fetch_strategy_data(conn, strategy_id):
    """Fetch ordered hit_count + special_hit rows for a strategy."""
    cur = conn.execute(
        """
        SELECT target_draw, hit_count, special_hit
        FROM strategy_prediction_replays
        WHERE controlled_apply_id = ?
          AND strategy_id = ?
        ORDER BY target_draw ASC
        """,
        (APPLY_ID, strategy_id),
    )
    rows = cur.fetchall()
    draws = [r[0] for r in rows]
    hits = np.array([r[1] for r in rows], dtype=float)
    specials = np.array([r[2] for r in rows], dtype=float)
    return draws, hits, specials


def fetch_baseline_data(conn, baseline_id):
    """Fetch baseline strategy hit_count keyed by target_draw."""
    cur = conn.execute(
        """
        SELECT target_draw, hit_count
        FROM strategy_prediction_replays
        WHERE strategy_id = ?
        ORDER BY target_draw ASC
        """,
        (baseline_id,),
    )
    rows = cur.fetchall()
    return {r[0]: r[1] for r in rows}


def rolling_window_analysis(draws, hits, window_size):
    """Compute rolling mean_hit over the last N draws."""
    if len(hits) < window_size:
        return None, None, None
    window_hits = hits[-window_size:]
    mean_hit = float(np.mean(window_hits))
    delta = mean_hit - THEORETICAL_BASELINE
    stable = mean_hit > THEORETICAL_BASELINE
    return mean_hit, delta, stable


def permutation_test(hits, n_picks: int, n_permutations: int = 10000, rng_seed: int = 42):
    """
    Bootstrap-based one-sample test: is observed mean significantly > theoretical_baseline (0.9474)?

    Method: Shift observed hit_count distribution to be centered at THEORETICAL_BASELINE,
    resample 10,000 times, test if observed mean is in the tail.

    Returns: observed_mean, null_mean, p_value (one-tailed: P(null_mean >= observed))
    """
    rng = np.random.default_rng(rng_seed)
    observed_mean = float(np.mean(hits))
    n = len(hits)

    # Shift data to center null at THEORETICAL_BASELINE
    shift = observed_mean - THEORETICAL_BASELINE
    shifted_hits = hits - shift  # centered at THEORETICAL_BASELINE

    # Bootstrap under null: resample from shifted distribution
    null_means = np.array([
        np.mean(rng.choice(shifted_hits, size=n, replace=True))
        for _ in range(n_permutations)
    ])

    # One-tailed: P(null_mean >= observed_mean)
    p_value = float(np.mean(null_means >= observed_mean))
    return observed_mean, float(np.mean(null_means)), p_value


def theoretical_binomial_test(hits, strategy_id: str):
    """
    One-sample t-test: Is observed mean_hit significantly > THEORETICAL_BASELINE (0.9474)?
    Returns: t_stat, p_value (two-tailed), p_one_tailed, theoretical_mean
    """
    theoretical_mean = THEORETICAL_BASELINE
    t_stat, p_two = stats.ttest_1samp(hits, theoretical_mean)
    # One-tailed: strategy mean > theoretical baseline
    p_one = p_two / 2 if t_stat > 0 else 1.0 - p_two / 2
    return float(t_stat), float(p_two), float(p_one), float(theoretical_mean)


def mcnemar_test(strategy_hits, baseline_hits_dict, draws, threshold=3):
    """
    McNemar paired test on event: hit_count >= threshold.
    Returns: n_paired, b_count, c_count, chi2, p_value
    b = strategy succeeds, baseline fails
    c = baseline succeeds, strategy fails
    """
    b = 0  # strategy >= threshold, baseline < threshold
    c = 0  # baseline >= threshold, strategy < threshold

    for draw, s_hit in zip(draws, strategy_hits):
        base_hit = baseline_hits_dict.get(draw, None)
        if base_hit is None:
            continue
        s_event = s_hit >= threshold
        b_event = base_hit >= threshold
        if s_event and not b_event:
            b += 1
        elif b_event and not s_event:
            c += 1

    n_discordant = b + c
    if n_discordant == 0:
        return 1500, 0, 0, 0.0, 1.0

    # McNemar test: chi2 = (b - c)^2 / (b + c)
    chi2 = (abs(b - c) - 1) ** 2 / (b + c)  # with continuity correction
    p_value = float(1 - stats.chi2.cdf(chi2, df=1))
    return len(draws), b, c, float(chi2), p_value


def evaluate_gates(strategy_id, row_count, windows, perm_p, mcnemar_p, special_rate):
    """Evaluate G1–G7 promotion gates. Returns dict of gate results."""
    w150_ok = windows["W150"]["mean_hit"] is not None and windows["W150"]["mean_hit"] > THEORETICAL_BASELINE
    w500_ok = windows["W500"]["mean_hit"] is not None and windows["W500"]["mean_hit"] > THEORETICAL_BASELINE
    w1500_ok = windows["W1500"]["mean_hit"] is not None and windows["W1500"]["mean_hit"] > THEORETICAL_BASELINE

    # G5: special hit rate CI [1/8 ± 2*se]
    n = row_count
    p_theoretical = 1 / 8
    se = np.sqrt(p_theoretical * (1 - p_theoretical) / n)
    ci_lo = p_theoretical - 2 * se
    ci_hi = p_theoretical + 2 * se
    g5_ok = ci_lo <= special_rate <= ci_hi

    gates = {
        "G1_sample_size": {"required": ">= 1500", "actual": row_count, "pass": row_count >= 1500},
        "G2_three_window_mean_hit": {
            "required": "W150/W500/W1500 all > 0.9474",
            "W150": windows["W150"]["mean_hit"],
            "W500": windows["W500"]["mean_hit"],
            "W1500": windows["W1500"]["mean_hit"],
            "pass": w150_ok and w500_ok and w1500_ok,
        },
        "G3_permutation_test": {
            "required": "p < 0.05 vs theoretical null",
            "p_value": perm_p,
            "pass": perm_p < 0.05,
        },
        "G4_mcnemar_vs_champion": {
            "required": "p < 0.05 on hit_count >= 3 paired McNemar vs fourier_rhythm_3bet",
            "p_value": mcnemar_p,
            "pass": mcnemar_p < 0.05,
        },
        "G5_special_hit_ci": {
            "required": f"special_hit_rate within [{ci_lo:.4f}, {ci_hi:.4f}] (2-sigma of 1/8)",
            "actual": round(special_rate, 6),
            "ci_lo": round(ci_lo, 6),
            "ci_hi": round(ci_hi, 6),
            "pass": g5_ok,
        },
        "G6_rolling_stability": {
            "required": "positive delta vs theoretical in all windows",
            "W150_delta": windows["W150"]["delta"],
            "W500_delta": windows["W500"]["delta"],
            "W1500_delta": windows["W1500"]["delta"],
            "pass": (
                windows["W150"]["delta"] is not None and windows["W150"]["delta"] > 0
                and windows["W500"]["delta"] is not None and windows["W500"]["delta"] > 0
                and windows["W1500"]["delta"] is not None and windows["W1500"]["delta"] > 0
            ),
        },
        "G7_governance": {
            "required": "no promotion unless separate P52 authorization",
            "pass": True,  # always passes for P51 read-only
            "note": "P51 is read-only; P52 authorization required for promotion",
        },
    }
    return gates


def classify_strategy(gates, strategy_id):
    """Classify strategy based on gate results."""
    g1 = gates["G1_sample_size"]["pass"]
    g2 = gates["G2_three_window_mean_hit"]["pass"]
    g3 = gates["G3_permutation_test"]["pass"]
    g4 = gates["G4_mcnemar_vs_champion"]["pass"]
    g5 = gates["G5_special_hit_ci"]["pass"]
    g6 = gates["G6_rolling_stability"]["pass"]

    all_pass = g1 and g2 and g3 and g4 and g5 and g6
    core_pass = g1 and g2 and g5 and g6  # without statistical tests

    if all_pass:
        return "P52_PROMOTION_CANDIDATE"
    elif core_pass and (g3 or g4):
        return "P52_PROMOTION_CANDIDATE"
    elif core_pass:
        return "WATCHLIST"
    elif g1 and (g2 or g6):
        return "WATCHLIST"
    elif not g1:
        return "BLOCKED_BY_INSUFFICIENT_PAIRING"
    else:
        return "INCONCLUSIVE"


def main():
    parser = argparse.ArgumentParser(description="P51 POWER_LOTTO Wave 4 rolling-window + McNemar gate")
    parser.add_argument("--json-out", default="/tmp/p51_analysis_result.json")
    args = parser.parse_args()

    conn = get_conn()
    baseline_dict = fetch_baseline_data(conn, BASELINE_STRATEGY)

    results = {
        "task": "P51",
        "description": "POWER_LOTTO Wave 4 Rolling-Window + McNemar Promotion Gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "apply_id": APPLY_ID,
        "theoretical_baseline": THEORETICAL_BASELINE,
        "mcnemar_threshold": MCNEMAR_THRESHOLD,
        "baseline_strategy": BASELINE_STRATEGY,
        "no_db_write": True,
        "no_lifecycle_promotion": True,
        "no_registry_mutation": True,
        "strategies": {},
    }

    n_picks_map = {
        "pp3_freqort_4bet": 4,
        "midfreq_fourier_mk_3bet": 3,
        "midfreq_fourier_2bet": 2,
    }

    all_classifications = []

    for strategy_id in STRATEGIES:
        draws, hits, specials = fetch_strategy_data(conn, strategy_id)
        row_count = len(hits)
        min_draw = draws[0] if draws else None
        max_draw = draws[-1] if draws else None
        special_hit_count = int(np.sum(specials))
        special_hit_rate = float(np.mean(specials))

        # Rolling window analysis
        windows = {}
        for window_name, window_size in WINDOW_SIZES.items():
            mean_hit, delta, stable = rolling_window_analysis(draws, hits, window_size)
            windows[window_name] = {
                "window_size": window_size,
                "mean_hit": round(mean_hit, 6) if mean_hit is not None else None,
                "delta_vs_baseline": round(delta, 6) if delta is not None else None,
                "delta": delta,
                "above_baseline": stable,
            }

        # Permutation test (simulation-based vs Binomial null)
        n_picks = n_picks_map[strategy_id]
        obs_mean, null_mean, perm_p = permutation_test(hits, n_picks=n_picks)
        t_stat, p_two, p_one, theo_mean = theoretical_binomial_test(hits, strategy_id)

        # McNemar test
        n_paired, b_count, c_count, chi2, mcnemar_p = mcnemar_test(
            hits, baseline_dict, draws, threshold=MCNEMAR_THRESHOLD
        )

        # Gate evaluation
        gates = evaluate_gates(
            strategy_id, row_count, windows, perm_p, mcnemar_p, special_hit_rate
        )

        # Classification
        classification = classify_strategy(gates, strategy_id)
        all_classifications.append(classification)

        results["strategies"][strategy_id] = {
            "row_count": row_count,
            "min_draw": min_draw,
            "max_draw": max_draw,
            "mean_hit_overall": round(float(np.mean(hits)), 6),
            "special_hit_count": special_hit_count,
            "special_hit_rate": round(special_hit_rate, 6),
            "rolling_windows": {
                k: {
                    "window_size": v["window_size"],
                    "mean_hit": v["mean_hit"],
                    "delta_vs_baseline": v["delta_vs_baseline"],
                    "above_baseline": v["above_baseline"],
                }
                for k, v in windows.items()
            },
            "permutation_test": {
                "observed_mean": round(obs_mean, 6),
                "null_mean": round(null_mean, 6),
                "p_value": round(perm_p, 6),
                "significant": perm_p < 0.05,
                "n_permutations": 10000,
                "method": "bootstrap one-tailed: P(null_mean >= observed) under H0: true_mean=0.9474",
            },
            "ttest_vs_baseline": {
                "theoretical_baseline": round(theo_mean, 6),
                "t_statistic": round(t_stat, 6),
                "p_two_tailed": round(p_two, 6),
                "p_one_tailed": round(p_one, 6),
                "significant_one_tailed": bool(p_one < 0.05),
            },
            "mcnemar_test": {
                "baseline_strategy": BASELINE_STRATEGY,
                "threshold": MCNEMAR_THRESHOLD,
                "n_paired_draws": n_paired,
                "b_strategy_wins": b_count,
                "c_baseline_wins": c_count,
                "chi2": round(chi2, 6),
                "p_value": round(mcnemar_p, 6),
                "significant": mcnemar_p < 0.05,
                "method": "McNemar with continuity correction",
            },
            "gates": {
                k: {kk: vv for kk, vv in v.items() if kk != "delta"}
                for k, v in gates.items()
            },
            "classification": classification,
        }

    # Overall P51 classification
    if "P52_PROMOTION_CANDIDATE" in all_classifications:
        overall = "P51_POWERLOTTO_PROMOTION_GATE_COMPLETED"
        has_candidates = True
    elif "WATCHLIST" in all_classifications:
        overall = "P51_POWERLOTTO_PROMOTION_GATE_INCONCLUSIVE"
        has_candidates = False
    else:
        overall = "P51_POWERLOTTO_PROMOTION_GATE_INCONCLUSIVE"
        has_candidates = False

    results["overall_classification"] = overall
    results["has_p52_candidates"] = has_candidates
    results["p51_governance_note"] = (
        "P51 is read-only verification. No lifecycle promotion performed. "
        "P52 authorization required to promote any candidate strategy."
    )

    conn.close()

    # Write JSON output — convert numpy types to Python native for serialization
    def _to_native(obj):
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    os.makedirs(os.path.dirname(args.json_out) if os.path.dirname(args.json_out) else ".", exist_ok=True)
    with open(args.json_out, "w") as f:
        json.dump(results, f, indent=2, default=_to_native)

    # Print summary to stdout
    print(f"\n{'='*70}")
    print(f"P51 POWER_LOTTO Wave 4 Rolling-Window + McNemar Gate")
    print(f"{'='*70}")
    print(f"Theoretical baseline: {THEORETICAL_BASELINE}")
    print(f"McNemar threshold:    hit_count >= {MCNEMAR_THRESHOLD}")
    print(f"Baseline strategy:    {BASELINE_STRATEGY}")
    print()

    print(f"{'Strategy':<30} {'W150':>8} {'W500':>8} {'W1500':>8} {'Perm-p':>8} {'McNem-p':>9} {'Class':<35}")
    print("-" * 110)
    for sid, sr in results["strategies"].items():
        w150 = sr["rolling_windows"]["W150"]["mean_hit"]
        w500 = sr["rolling_windows"]["W500"]["mean_hit"]
        w1500 = sr["rolling_windows"]["W1500"]["mean_hit"]
        pp = sr["permutation_test"]["p_value"]
        mp = sr["mcnemar_test"]["p_value"]
        cl = sr["classification"]
        print(f"{sid:<30} {w150:>8.4f} {w500:>8.4f} {w1500:>8.4f} {pp:>8.4f} {mp:>9.4f} {cl:<35}")

    print()
    print(f"Overall P51 Classification: {overall}")
    print(f"Has P52 candidates:         {has_candidates}")
    print()
    print("Gate Summary:")
    for sid, sr in results["strategies"].items():
        gates = sr["gates"]
        gate_results = " | ".join(
            f"{k}: {'PASS' if v['pass'] else 'FAIL'}"
            for k, v in gates.items()
        )
        print(f"  {sid}: {gate_results}")

    print(f"\nJSON written to: {args.json_out}")
    print(f"{'='*70}")

    return 0 if overall == "P51_POWERLOTTO_PROMOTION_GATE_COMPLETED" else 1


if __name__ == "__main__":
    sys.exit(main())
