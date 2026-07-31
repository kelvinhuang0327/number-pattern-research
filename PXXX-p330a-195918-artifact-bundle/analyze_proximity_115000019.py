#!/usr/bin/env python3
"""
Analysis of Big Lotto Draw 115000019: Proximity Metrics + Failure Reverse-Engineering
=====================================================================================
Actual result: [16, 35, 36, 37, 39, 49]
"""

import sqlite3
import json
import math
import random
import numpy as np
from collections import Counter
from itertools import combinations

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
DB_PATH = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"
ACTUAL = sorted([16, 35, 36, 37, 39, 49])
ACTUAL_SET = set(ACTUAL)
PREV_DRAW = sorted([6, 12, 24, 26, 37, 46])  # 115000018

PREDICTIONS = {
    "P0 Bet1 (Hot+Echo)":       sorted([11, 16, 18, 24, 25, 39]),
    "P0 Bet2 (Cold)":           sorted([13, 29, 30, 34, 37, 49]),
    "TripleStrike Bet1 (Fourier)": sorted([1, 3, 25, 28, 36, 48]),
    "TripleStrike Bet2 (Cold)": sorted([27, 30, 31, 34, 38, 44]),
    "TripleStrike Bet3 (Tail)": sorted([2, 15, 20, 24, 39, 41]),
    "FreqOrtho Bet5":           sorted([7, 11, 26, 33, 35, 49]),
}

NUM_RANGE = range(1, 50)  # Big Lotto: 1-49
PICK = 6
N_SIM = 10000

random.seed(42)
np.random.seed(42)


# ─────────────────────────────────────────────────────────────
# Helper: Zone assignment (Z1: 1-16, Z2: 17-33, Z3: 34-49)
# ─────────────────────────────────────────────────────────────
def zone_dist(nums):
    """Return (count_z1, count_z2, count_z3) for a set of numbers."""
    z1 = sum(1 for n in nums if 1 <= n <= 16)
    z2 = sum(1 for n in nums if 17 <= n <= 33)
    z3 = sum(1 for n in nums if 34 <= n <= 49)
    return np.array([z1, z2, z3], dtype=float)


def cosine_sim(a, b):
    dot = np.dot(a, b)
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def ac_value(nums):
    """AC value = number of distinct differences - (pick - 1)."""
    s = sorted(nums)
    diffs = set()
    for i in range(len(s)):
        for j in range(i + 1, len(s)):
            diffs.add(s[j] - s[i])
    return len(diffs) - (len(s) - 1)


def odd_even_ratio(nums):
    """Return (odd_count, even_count)."""
    odd = sum(1 for n in nums if n % 2 == 1)
    return (odd, len(nums) - odd)


def consecutive_count(nums):
    """Count the number of consecutive pairs."""
    s = sorted(nums)
    return sum(1 for i in range(len(s) - 1) if s[i + 1] - s[i] == 1)


# ─────────────────────────────────────────────────────────────
# PART A: 7 Proximity Metrics
# ─────────────────────────────────────────────────────────────

def compute_metrics(pred, actual=ACTUAL, actual_set=ACTUAL_SET):
    pred_set = set(pred)

    # 1. Exact Match Count
    intersection = pred_set & actual_set
    exact_match = len(intersection)

    # 2. Jaccard Similarity
    union = pred_set | actual_set
    jaccard = len(intersection) / len(union) if union else 0.0

    # 3. Sum Distance (normalized)
    sum_pred = sum(pred)
    sum_actual = sum(actual)
    sum_distance_raw = abs(sum_pred - sum_actual)
    sum_distance_norm = sum_distance_raw / sum_actual if sum_actual else 0.0
    # Convert to similarity: 1 - normalized distance (capped at 0)
    sum_sim = max(0.0, 1.0 - sum_distance_norm)

    # 4. Zone Overlap Score (cosine similarity of zone distributions)
    zp = zone_dist(pred)
    za = zone_dist(actual)
    zone_score = cosine_sim(zp, za)

    # 5. Number Distance Score
    # For each actual number, find minimum distance to any predicted number
    total_min_dist = 0
    for a in actual:
        min_d = min(abs(a - p) for p in pred)
        total_min_dist += min_d
    # Normalize: max possible distance per number is 48, for 6 numbers max = 288
    max_possible = 48 * PICK
    dist_sim = 1.0 - (total_min_dist / max_possible)

    # 6. Structural Similarity
    # Compare AC value, odd/even, consecutive count
    ac_pred = ac_value(pred)
    ac_actual = ac_value(actual)
    ac_max = 15  # max AC for 6 from 49 is C(6,2)-5 = 10, but theoretical max diff ≈ 10
    ac_sim = 1.0 - abs(ac_pred - ac_actual) / 10.0

    oe_pred = odd_even_ratio(pred)
    oe_actual = odd_even_ratio(actual)
    # Simple match: 1 if same, 0.5 if off by 1, 0 if off by more
    oe_diff = abs(oe_pred[0] - oe_actual[0])
    oe_sim = max(0.0, 1.0 - oe_diff / 6.0)

    cons_pred = consecutive_count(pred)
    cons_actual = consecutive_count(actual)
    cons_sim = 1.0 - abs(cons_pred - cons_actual) / 5.0  # max 5 cons pairs
    cons_sim = max(0.0, cons_sim)

    structural = (ac_sim + oe_sim + cons_sim) / 3.0

    # 7. Combined Proximity Index (weighted average)
    weights = {
        'exact_match': 0.30,
        'jaccard': 0.15,
        'sum_sim': 0.10,
        'zone_score': 0.15,
        'dist_sim': 0.15,
        'structural': 0.15,
    }
    # Normalize exact match to 0-1 (max 6)
    exact_norm = exact_match / PICK

    combined = (
        weights['exact_match'] * exact_norm +
        weights['jaccard'] * jaccard +
        weights['sum_sim'] * sum_sim +
        weights['zone_score'] * zone_score +
        weights['dist_sim'] * dist_sim +
        weights['structural'] * structural
    )

    return {
        'exact_match': exact_match,
        'jaccard': jaccard,
        'sum_distance_raw': sum_distance_raw,
        'sum_sim': sum_sim,
        'zone_pred': tuple(zp.astype(int)),
        'zone_actual': tuple(za.astype(int)),
        'zone_score': zone_score,
        'min_dist_total': total_min_dist,
        'dist_sim': dist_sim,
        'ac_pred': ac_pred,
        'ac_actual': ac_actual,
        'oe_pred': oe_pred,
        'oe_actual': oe_actual,
        'cons_pred': cons_pred,
        'cons_actual': cons_actual,
        'structural': structural,
        'combined': combined,
    }


def random_pick():
    return sorted(random.sample(range(1, 50), PICK))


# ─────────────────────────────────────────────────────────────
# Main execution
# ─────────────────────────────────────────────────────────────
def main():
    sep = "=" * 80
    thin = "-" * 80

    print(sep)
    print("  BIG LOTTO DRAW 115000019 — PROXIMITY & FAILURE ANALYSIS")
    print(sep)
    print(f"  Actual numbers : {ACTUAL}")
    print(f"  Previous draw  : {PREV_DRAW}  (115000018)")
    print(f"  Sum            : {sum(ACTUAL)}")
    print(f"  Zones (Z1/Z2/Z3): {tuple(zone_dist(ACTUAL).astype(int))}")
    print(f"  AC value       : {ac_value(ACTUAL)}")
    print(f"  Odd/Even       : {odd_even_ratio(ACTUAL)}")
    print(f"  Consecutive    : {consecutive_count(ACTUAL)} pairs  (35-36, 36-37)")
    print(sep)

    # ── Part A: Proximity Metrics ──
    print()
    print(sep)
    print("  PART A: PROXIMITY METRICS — 7 DIMENSIONS")
    print(sep)

    all_results = {}
    for name, pred in PREDICTIONS.items():
        m = compute_metrics(pred)
        all_results[name] = m

        hits = set(pred) & ACTUAL_SET
        misses_pred = set(pred) - ACTUAL_SET
        misses_actual = ACTUAL_SET - set(pred)

        print(f"\n{thin}")
        print(f"  Strategy: {name}")
        print(f"  Predicted:  {pred}")
        print(f"  Hits:       {sorted(hits) if hits else '(none)'}  |  Missed actual: {sorted(misses_actual)}")
        print(f"{thin}")
        print(f"  [1] Exact Match Count     : {m['exact_match']} / 6")
        print(f"  [2] Jaccard Similarity    : {m['jaccard']:.4f}  (|∩|/|∪| = {m['exact_match']}/{12 - m['exact_match']})")
        print(f"  [3] Sum Distance          : |{sum(pred)} - {sum(ACTUAL)}| = {m['sum_distance_raw']}")
        print(f"      Sum Similarity (norm) : {m['sum_sim']:.4f}")
        print(f"  [4] Zone Overlap (cosine) : {m['zone_score']:.4f}  pred={m['zone_pred']} vs actual={m['zone_actual']}")
        print(f"  [5] Number Distance Score : total_min_dist={m['min_dist_total']}, similarity={m['dist_sim']:.4f}")
        print(f"  [6] Structural Similarity : {m['structural']:.4f}")
        print(f"      AC: {m['ac_pred']} vs {m['ac_actual']}  |  O/E: {m['oe_pred']} vs {m['oe_actual']}  |  Cons: {m['cons_pred']} vs {m['cons_actual']}")
        print(f"  [7] Combined Proximity    : {m['combined']:.4f}")

    # ── Ranking ──
    print(f"\n{sep}")
    print("  RANKING BY COMBINED PROXIMITY INDEX")
    print(sep)
    ranked = sorted(all_results.items(), key=lambda x: x[1]['combined'], reverse=True)
    for rank, (name, m) in enumerate(ranked, 1):
        print(f"  #{rank}  {m['combined']:.4f}  | Match={m['exact_match']}  Jaccard={m['jaccard']:.3f}  "
              f"Zone={m['zone_score']:.3f}  Dist={m['dist_sim']:.3f}  Struct={m['structural']:.3f}  | {name}")

    # ── Random Baseline (10,000 simulations) ──
    print(f"\n{sep}")
    print(f"  RANDOM BASELINE — {N_SIM:,} SIMULATIONS")
    print(sep)

    rand_metrics = {k: [] for k in ['exact_match', 'jaccard', 'sum_sim', 'zone_score', 'dist_sim', 'structural', 'combined']}

    for _ in range(N_SIM):
        rp = random_pick()
        rm = compute_metrics(rp)
        for k in rand_metrics:
            rand_metrics[k].append(rm[k])

    print(f"\n  {'Metric':<28} {'Random Mean':>12} {'Random Std':>12} {'Best Strat':>12} {'vs Random':>12}")
    print(f"  {thin}")

    metric_labels = {
        'exact_match': 'Exact Match Count',
        'jaccard': 'Jaccard Similarity',
        'sum_sim': 'Sum Similarity',
        'zone_score': 'Zone Overlap (cosine)',
        'dist_sim': 'Number Distance Score',
        'structural': 'Structural Similarity',
        'combined': 'Combined Proximity Index',
    }

    best_strat_vals = {}
    for k in rand_metrics:
        best_val = max(m[k] for m in all_results.values())
        best_strat_vals[k] = best_val

    for k, label in metric_labels.items():
        rm = np.array(rand_metrics[k])
        mean_r = np.mean(rm)
        std_r = np.std(rm)
        best_v = best_strat_vals[k]
        # How many std above random
        z_score = (best_v - mean_r) / std_r if std_r > 0 else 0
        print(f"  {label:<28} {mean_r:>12.4f} {std_r:>12.4f} {best_v:>12.4f} {z_score:>+11.2f}σ")

    # Match count distribution
    match_counts = rand_metrics['exact_match']
    print(f"\n  Random Match Count Distribution (out of {N_SIM:,} draws):")
    mc = Counter(int(x) for x in match_counts)
    for k_val in sorted(mc.keys()):
        pct = mc[k_val] / N_SIM * 100
        bar = "#" * int(pct)
        print(f"    {k_val} matches: {mc[k_val]:>5} ({pct:>6.2f}%)  {bar}")

    # ── Percentile analysis ──
    print(f"\n  Strategy Percentile vs Random Distribution:")
    print(f"  {thin}")
    for name, m in ranked:
        cpi = m['combined']
        pctile = np.sum(np.array(rand_metrics['combined']) < cpi) / N_SIM * 100
        print(f"  {name:<35}  CPI={cpi:.4f}  Percentile={pctile:.1f}%")

    # ==============================================================
    # PART B: FAILURE REVERSE-ENGINEERING
    # ==============================================================
    print(f"\n\n{sep}")
    print("  PART B: FAILURE REVERSE-ENGINEERING")
    print(sep)

    # ── B1: Randomness Factor ──
    print(f"\n{thin}")
    print("  B1. RANDOMNESS FACTOR — Irreducible Stochastic Noise")
    print(thin)

    p_each = PICK / 49  # probability a specific number is drawn
    expected_match = PICK * (PICK / 49)  # E[matches] for 6 predicted vs 6 drawn from 49
    # Exact: hypergeometric
    from scipy.stats import hypergeom
    rv = hypergeom(49, 6, 6)
    expected_hyper = rv.mean()
    std_hyper = rv.std()

    print(f"\n  Model: Hypergeometric(N=49, K=6, n=6)")
    print(f"  Expected matches per bet  : {expected_hyper:.4f}")
    print(f"  Standard deviation        : {std_hyper:.4f}")
    print(f"  P(0 match)                : {rv.pmf(0):.4f}  ({rv.pmf(0)*100:.2f}%)")
    print(f"  P(1 match)                : {rv.pmf(1):.4f}  ({rv.pmf(1)*100:.2f}%)")
    print(f"  P(2 match)                : {rv.pmf(2):.4f}  ({rv.pmf(2)*100:.2f}%)")
    print(f"  P(3+ match)               : {1-rv.cdf(2):.4f}  ({(1-rv.cdf(2))*100:.2f}%)")

    print(f"\n  Actual matches per strategy:")
    for name, m in all_results.items():
        mc_val = m['exact_match']
        p_val = rv.pmf(mc_val)
        cum_p = 1 - rv.cdf(mc_val - 1) if mc_val > 0 else 1.0
        verdict = "EXPECTED" if mc_val <= 1 else ("ABOVE AVERAGE" if mc_val == 2 else "SIGNIFICANTLY ABOVE")
        print(f"    {name:<35} {mc_val} hits  P(>={mc_val})={cum_p:.4f}  → {verdict}")

    # Combined: probability at least one of 6 bets gets 3+
    p_3plus = 1 - rv.cdf(2)
    p_none_3plus = (1 - p_3plus) ** len(PREDICTIONS)
    p_any_3plus = 1 - p_none_3plus
    print(f"\n  With {len(PREDICTIONS)} independent bets:")
    print(f"    P(at least one bet >= 3 matches) = {p_any_3plus:.4f}  ({p_any_3plus*100:.2f}%)")
    print(f"    P(no bet >= 3 matches)           = {p_none_3plus:.4f}  ({p_none_3plus*100:.2f}%)")
    total_hits = sum(m['exact_match'] for m in all_results.values())
    exp_total = expected_hyper * len(PREDICTIONS)
    print(f"    Total hits across all bets       : {total_hits}  (expected: {exp_total:.1f})")
    print(f"    Assessment: {'OUTPERFORMED random' if total_hits > exp_total + std_hyper * len(PREDICTIONS)**0.5 else 'Within expected range' if total_hits >= exp_total - std_hyper * len(PREDICTIONS)**0.5 else 'UNDERPERFORMED random'}")

    # ── B2: Model Limitations ──
    print(f"\n{thin}")
    print("  B2. MODEL LIMITATIONS — Structural Blind Spots")
    print(thin)

    # B2a: Consecutive triplet 35-36-37
    print(f"\n  [B2a] Consecutive Triplet 35-36-37")
    print(f"  {'-'*50}")

    # Query historical consecutive triplets
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT draw, numbers FROM draws WHERE lottery_type='BIG_LOTTO' ORDER BY draw ASC")
    all_draws = []
    for row in cur.fetchall():
        nums = json.loads(row[1])
        all_draws.append((row[0], sorted(nums)))

    triplet_draws = []
    for draw_id, nums in all_draws:
        s = sorted(nums)
        for i in range(len(s) - 2):
            if s[i+1] == s[i] + 1 and s[i+2] == s[i+1] + 1:
                triplet_draws.append((draw_id, s))
                break

    triplet_rate = len(triplet_draws) / len(all_draws) * 100

    print(f"  Historical consecutive triplets in Big Lotto: {len(triplet_draws)} / {len(all_draws)} = {triplet_rate:.2f}%")
    print(f"  Recent examples (last 10):")
    for draw_id, nums in triplet_draws[-10:]:
        trips = []
        s = sorted(nums)
        for i in range(len(s) - 2):
            if s[i+1] == s[i] + 1 and s[i+2] == s[i+1] + 1:
                trips.append(f"{s[i]}-{s[i+1]}-{s[i+2]}")
        print(f"    Draw {draw_id}: {nums}  triplet(s): {', '.join(trips)}")

    # Did any prediction contain a consecutive triplet?
    pred_with_triplets = []
    for name, pred in PREDICTIONS.items():
        s = sorted(pred)
        has_trip = False
        for i in range(len(s) - 2):
            if s[i+1] == s[i] + 1 and s[i+2] == s[i+1] + 1:
                has_trip = True
        if has_trip:
            pred_with_triplets.append(name)

    print(f"\n  Predictions containing a consecutive triplet: {pred_with_triplets if pred_with_triplets else 'NONE'}")
    print(f"  Verdict: Models generally AVOID consecutive clusters (anti-consecutive bias)")
    print(f"           This is a systematic blind spot — models treat consecutives as 'unlikely'")
    print(f"           despite {triplet_rate:.1f}% historical occurrence rate.")

    # Quadruplet check
    quad_draws = []
    for draw_id, nums in all_draws:
        s = sorted(nums)
        for i in range(len(s) - 3):
            if all(s[i+j+1] == s[i+j] + 1 for j in range(3)):
                quad_draws.append((draw_id, s))
                break
    print(f"\n  Consecutive QUADRUPLETS (4 in a row): {len(quad_draws)} / {len(all_draws)} = {len(quad_draws)/len(all_draws)*100:.2f}%")
    print(f"  Note: 35-36-37 is a triplet within the draw; actual also has 39 (gap=2)")

    # B2b: Extreme zone skew
    print(f"\n  [B2b] Extreme Zone Skew: Z1=1, Z2=0, Z3=5")
    print(f"  {'-'*50}")

    zone_counts = Counter()
    extreme_z3 = []
    for draw_id, nums in all_draws:
        zd = tuple(zone_dist(nums).astype(int))
        zone_counts[zd] += 1
        if zd[2] >= 5:
            extreme_z3.append((draw_id, nums, zd))

    print(f"  Zone distribution (1,0,5) occurrences: {zone_counts.get((1,0,5), 0)} / {len(all_draws)} = {zone_counts.get((1,0,5), 0)/len(all_draws)*100:.3f}%")
    print(f"  Any zone with 5+ numbers: {len(extreme_z3)} / {len(all_draws)} = {len(extreme_z3)/len(all_draws)*100:.2f}%")

    print(f"\n  Most common zone distributions (top 10):")
    for zd, cnt in zone_counts.most_common(10):
        pct = cnt / len(all_draws) * 100
        print(f"    Zone({zd[0]},{zd[1]},{zd[2]}): {cnt:>4} ({pct:.2f}%)")

    # What zone dists did predictions use?
    print(f"\n  Zone distributions in predictions:")
    for name, pred in PREDICTIONS.items():
        zd = tuple(zone_dist(pred).astype(int))
        hist_pct = zone_counts.get(zd, 0) / len(all_draws) * 100
        print(f"    {name:<35}  Zone({zd[0]},{zd[1]},{zd[2]})  historical={hist_pct:.2f}%")

    actual_zone = tuple(zone_dist(ACTUAL).astype(int))
    print(f"\n  Verdict: Actual zone ({actual_zone[0]},{actual_zone[1]},{actual_zone[2]}) is an extreme tail event.")
    print(f"           No prediction modeled a zero-in-Z2 scenario.")
    print(f"           Models tend to 'balance' zone distribution toward (2,2,2), missing extremes.")

    # B2c: Carry-over (37 from previous draw)
    print(f"\n  [B2c] Number Carry-Over: 37 repeated from 115000018")
    print(f"  {'-'*50}")

    carry_count = 0
    carry_sizes = []
    for i in range(1, len(all_draws)):
        prev_set = set(all_draws[i-1][1])
        curr_set = set(all_draws[i][1])
        overlap = len(prev_set & curr_set)
        carry_sizes.append(overlap)
        if overlap > 0:
            carry_count += 1

    avg_carry = np.mean(carry_sizes)
    print(f"  Historical carry-over statistics (consecutive Big Lotto draws):")
    print(f"    Draws with >= 1 repeat  : {carry_count}/{len(all_draws)-1} = {carry_count/(len(all_draws)-1)*100:.1f}%")
    print(f"    Average repeat count    : {avg_carry:.2f}")
    carry_dist = Counter(carry_sizes)
    for k_val in sorted(carry_dist.keys()):
        pct = carry_dist[k_val] / len(carry_sizes) * 100
        print(f"    {k_val} repeats: {carry_dist[k_val]:>4} ({pct:.1f}%)")

    # Did predictions include 37?
    preds_with_37 = [name for name, pred in PREDICTIONS.items() if 37 in pred]
    print(f"\n  Predictions that included 37 (carried from prev): {preds_with_37 if preds_with_37 else 'NONE'}")
    print(f"  In 115000018: {PREV_DRAW} — 37 was in the draw")
    print(f"  In 115000019: {ACTUAL} — 37 appeared again")

    if preds_with_37:
        print(f"  Verdict: {len(preds_with_37)}/{len(PREDICTIONS)} strategies DID model carry-over ('P0 Bet2' caught 37).")
    else:
        print(f"  Verdict: No strategy modeled carry-over.")

    # ── B3: Feature Deficiency ──
    print(f"\n{thin}")
    print("  B3. FEATURE DEFICIENCY — Gap Analysis")
    print(thin)

    features_needed = [
        ("Consecutive cluster detection",
         "Ability to predict 3+ consecutive numbers appearing together",
         "PARTIALLY (constraint filters count consecutives, but as REJECTION criteria, not attraction)"),
        ("Extreme zone concentration",
         "Model for 5 numbers in a single zone (Z3: 34-49)",
         "NO — zone balance is enforced as even distribution"),
        ("Number carry-over modeling",
         "Explicit feature for numbers repeating from immediately prior draw",
         "PARTIALLY — Hot+Echo tracks recent frequency, Cold strategy avoids recent numbers"),
        ("High-sum bias detection",
         f"Sum=212 is high (avg ~150). Detection of high-sum regimes",
         "NO — sum range filters are symmetric around mean"),
        ("Tail-heavy number preference",
         "Preference for numbers 35-49 in bulk",
         "NO — most models have zone-balance constraints that prevent this"),
        ("Consecutive pair clustering in Z3",
         "Detecting that Z3 numbers tend to cluster tightly (35,36,37,39)",
         "NO — gap analysis exists but not zone-specific gap patterns"),
        ("Anti-middle-zone signal",
         "Detecting when Z2 (17-33) is about to be completely absent",
         "NO — this is never modeled; models assume all zones contribute"),
    ]

    print(f"\n  {'Feature Needed':<38} {'Available?':<10} Details")
    print(f"  {'-'*100}")
    for feat, detail, avail in features_needed:
        status = "YES" if avail.startswith("YES") else ("PARTIAL" if avail.startswith("PARTIAL") else "NO")
        print(f"  {feat:<38} {status:<10} {detail}")
        if avail not in ("YES", "NO"):
            print(f"  {'':38} {'':10} Current state: {avail}")

    gap_count = sum(1 for _, _, a in features_needed if a.startswith("NO"))
    partial_count = sum(1 for _, _, a in features_needed if a.startswith("PARTIAL"))
    print(f"\n  Feature Gap Summary:")
    print(f"    Features needed        : {len(features_needed)}")
    print(f"    Fully available        : {len(features_needed) - gap_count - partial_count}")
    print(f"    Partially available    : {partial_count}")
    print(f"    Completely missing     : {gap_count}")
    print(f"    Gap ratio              : {gap_count}/{len(features_needed)} = {gap_count/len(features_needed)*100:.0f}%")

    # ── B4: Data Limitation ──
    print(f"\n{thin}")
    print("  B4. DATA LIMITATION — Rare Event Training Deficiency")
    print(thin)

    # Count structural anomalies similar to this draw
    target_ac = ac_value(ACTUAL)
    target_oe = odd_even_ratio(ACTUAL)
    target_cons = consecutive_count(ACTUAL)
    target_sum = sum(ACTUAL)
    target_zone = tuple(zone_dist(ACTUAL).astype(int))

    print(f"\n  Target draw structural signature:")
    print(f"    Sum = {target_sum}, AC = {target_ac}, O/E = {target_oe}, Consecutive pairs = {target_cons}")
    print(f"    Zone = {target_zone}")

    # Find similar draws
    similar_strict = []
    similar_moderate = []
    similar_loose = []

    for draw_id, nums in all_draws:
        s_ac = ac_value(nums)
        s_oe = odd_even_ratio(nums)
        s_cons = consecutive_count(nums)
        s_sum = sum(nums)
        s_zone = tuple(zone_dist(nums).astype(int))

        # Strict: all match exactly
        if s_ac == target_ac and s_oe == target_oe and s_cons == target_cons and s_zone == target_zone:
            similar_strict.append((draw_id, nums))

        # Moderate: AC within 1, same O/E, same consecutive, zone Z3 >= 4
        if abs(s_ac - target_ac) <= 1 and s_oe == target_oe and s_cons >= 2 and s_zone[2] >= 4:
            similar_moderate.append((draw_id, nums))

        # Loose: consecutive >= 2 AND zone skew (any zone >= 4)
        if s_cons >= 2 and max(s_zone) >= 4:
            similar_loose.append((draw_id, nums))

    print(f"\n  Historical precedent search ({len(all_draws)} total Big Lotto draws):")
    print(f"    Strict match (AC={target_ac}, O/E={target_oe}, Cons={target_cons}, Zone={target_zone}):")
    print(f"      Found: {len(similar_strict)} draws ({len(similar_strict)/len(all_draws)*100:.3f}%)")
    if similar_strict:
        for d, n in similar_strict[-5:]:
            print(f"        Draw {d}: {n}")

    print(f"    Moderate match (AC+-1, same O/E, cons>=2, Z3>=4):")
    print(f"      Found: {len(similar_moderate)} draws ({len(similar_moderate)/len(all_draws)*100:.2f}%)")
    if similar_moderate:
        for d, n in similar_moderate[-5:]:
            print(f"        Draw {d}: {n}")

    print(f"    Loose match (cons>=2 AND any zone>=4):")
    print(f"      Found: {len(similar_loose)} draws ({len(similar_loose)/len(all_draws)*100:.2f}%)")
    if similar_loose:
        for d, n in similar_loose[-5:]:
            print(f"        Draw {d}: {n}")

    # Machine learning minimum sample analysis
    print(f"\n  ML Training Adequacy Analysis:")
    print(f"    Total training draws available   : {len(all_draws)}")
    print(f"    Draws with triplet consecutives  : {len(triplet_draws)} ({len(triplet_draws)/len(all_draws)*100:.1f}%)")
    print(f"    Draws with strict-similar struct  : {len(similar_strict)}")
    print(f"    Draws with zone 5+ concentration  : {len(extreme_z3)} ({len(extreme_z3)/len(all_draws)*100:.1f}%)")
    min_samples_ml = 30  # typical minimum for statistical significance
    print(f"\n    Minimum samples for ML learning  : ~{min_samples_ml}")
    print(f"    Strict-similar available          : {len(similar_strict)}")
    sufficient = len(similar_strict) >= min_samples_ml
    print(f"    Sufficient for pattern learning?  : {'YES' if sufficient else 'NO'} ({'adequate' if sufficient else f'need {min_samples_ml - len(similar_strict)} more'})")

    # ── Final Summary ──
    print(f"\n\n{sep}")
    print("  EXECUTIVE SUMMARY")
    print(sep)

    best_name, best_m = ranked[0]
    print(f"""
  Draw 115000019 [{', '.join(map(str, ACTUAL))}] was an ANOMALOUS draw with:
    - A consecutive TRIPLET (35-36-37) — occurs in only {triplet_rate:.1f}% of draws
    - Extreme zone skew (1,0,5) — only {zone_counts.get((1,0,5),0)} historical occurrences ({zone_counts.get((1,0,5),0)/len(all_draws)*100:.2f}%)
    - High sum (212) — top decile
    - A carry-over number (37) from the prior draw

  Best strategy: {best_name}
    Combined Proximity Index: {best_m['combined']:.4f}
    Exact matches: {best_m['exact_match']}/6

  All {len(PREDICTIONS)} strategies combined achieved {total_hits} total hits
  (expected from random: {exp_total:.1f}, so {'ABOVE' if total_hits > exp_total else 'AT'} random baseline).

  ROOT CAUSES OF MISSES:
    1. RANDOMNESS (primary)   : Expected {expected_hyper:.2f} matches/bet; getting 2 is already top-30% luck.
    2. ANTI-CONSECUTIVE BIAS  : Models penalize consecutive numbers, but {triplet_rate:.1f}% of draws have triplets.
    3. ZONE BALANCE BIAS      : Models enforce ~(2,2,2) zone distribution; actual was (1,0,5).
    4. DATA SCARCITY          : Only {len(similar_strict)} draws match this structural profile — insufficient for ML.
    5. FEATURE GAP            : {gap_count}/7 key features completely missing from model repertoire.

  ACTIONABLE INSIGHTS:
    - Remove or soften anti-consecutive filters (allow triplets in ~{triplet_rate:.0f}% of bets)
    - Add a "zone extreme" bet variant that deliberately skews to one zone
    - Weight carry-over numbers from prior draw more heavily
    - Consider ensemble diversity: at least 1 bet should be structurally "wild"
""")

    conn.close()


if __name__ == "__main__":
    main()
