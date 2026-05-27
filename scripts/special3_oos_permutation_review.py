"""
P98 Special3 OOS + Permutation Review
dry_run_only=True — NO DB writes, NO replay row inserts.

Walk-forward OOS validation + binomial permutation test for 5 PROVISIONAL
Special3 strategies from P97. Ensemble v2 design (excluding REJECT strategy).

Outputs:
  outputs/replay/special3_oos_permutation_review_20260527.json
"""

import sqlite3
import json
import math
import pathlib
import itertools
import datetime
from collections import Counter, defaultdict
from scipy import stats

DRY_RUN = True
DB_PATH = "lottery_api/data/lottery_v2.db"
OUT_PATH = pathlib.Path("outputs/replay/special3_oos_permutation_review_20260527.json")
TODAY = "20260527"
RANDOM_SEED = 42

TOP_NS = [10, 20, 50, 100]
ALL_TICKETS = list(itertools.product(range(10), repeat=3))  # 1000 tickets

# P97 input (from special3_baseline_dryrun_20260527.json)
P97_PROVISIONAL = [
    "position_frequency_topk",
    "ensemble_rank_v1",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
]
P97_REJECT = ["position_cold_rebound_topk"]

# OOS folds: (train_end_fraction, test_start_fraction, test_end_fraction, fold_name)
OOS_FOLDS = [
    (1/3, 1/3, 1/2,  "fold_a_early"),
    (1/2, 1/2, 2/3,  "fold_b_mid"),
    (2/3, 2/3, 5/6,  "fold_c_late"),
    (5/6, 5/6, 1.0,  "fold_d_holdout"),
]


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


# ── Strategy implementations (replicated from P97 — no modifications) ─────────

def position_frequency_topk(window_draws, top_n):
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
    recent = window_draws[-recency:] if len(window_draws) >= recency else window_draws
    return position_frequency_topk(recent, top_n)


def position_cold_rebound_topk(window_draws, top_n):
    pos_last_seen = [{d: -1 for d in range(10)} for _ in range(3)]
    for i, draw in enumerate(window_draws):
        for p in range(3):
            pos_last_seen[p][draw["digits"][p]] = i
    pos_cold_rank = []
    for p in range(3):
        ranked = sorted(range(10), key=lambda d, p=p: pos_last_seen[p][d])
        pos_cold_rank.append(ranked)
    cold_rank_map = [{d: i for i, d in enumerate(ranked)} for ranked in pos_cold_rank]
    scored = []
    for t in ALL_TICKETS:
        score = sum(cold_rank_map[p][t[p]] for p in range(3))
        scored.append((score, t))
    scored.sort()
    return [t for _, t in scored[:top_n]]


def sum_band_frequency(window_draws, top_n):
    def sum_band(digits):
        s = sum(digits)
        if s <= 9: return 0
        elif s <= 17: return 1
        return 2
    band_counts = Counter(sum_band(d["digits"]) for d in window_draws)
    top_band = band_counts.most_common(1)[0][0]
    candidates = [t for t in ALL_TICKETS if sum_band(t) == top_band]
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
    def span_band(digits):
        sp = max(digits) - min(digits)
        if sp <= 3: return 0
        elif sp <= 6: return 1
        return 2
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
    """Original v1: includes position_cold_rebound_topk (for reference only)."""
    k = 60
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


def ensemble_rank_v2(window_draws, top_n):
    """V2: excludes position_cold_rebound_topk."""
    k = 60
    all_strategies = [
        position_frequency_topk(window_draws, 100),
        recent_position_hot_topk(window_draws, 100),
        sum_band_frequency(window_draws, 100),
        span_band_frequency(window_draws, 100),
    ]
    rrf_scores = defaultdict(float)
    for ranked_list in all_strategies:
        for rank, ticket in enumerate(ranked_list):
            rrf_scores[ticket] += 1.0 / (k + rank + 1)
    sorted_tickets = sorted(rrf_scores.keys(), key=lambda t: rrf_scores[t], reverse=True)
    return sorted_tickets[:top_n]


STRATEGY_FNS = {
    "position_frequency_topk": position_frequency_topk,
    "recent_position_hot_topk": recent_position_hot_topk,
    "sum_band_frequency": sum_band_frequency,
    "span_band_frequency": span_band_frequency,
    "ensemble_rank_v1": ensemble_rank_v1,
    "ensemble_rank_v2": ensemble_rank_v2,
}


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(strategy_fn, train_draws, test_draws, top_n):
    """Compute hit rates and auxiliary metrics for a single strategy on a test window."""
    if len(train_draws) < 10:
        return None
    predictions = strategy_fn(train_draws, top_n)
    pred_set = set(predictions)
    direct_hits = sum(1 for d in test_draws if d["digits"] in pred_set)
    box_hits = sum(
        1 for d in test_draws
        if any(sorted(p) == sorted(d["digits"]) for p in predictions)
    )
    n = len(test_draws)
    if n == 0:
        return None
    random_baseline = top_n / 1000.0
    direct_rate = direct_hits / n
    box_rate = box_hits / n
    edge = direct_rate - random_baseline

    # Position digit accuracy
    pos_acc_list = []
    for d in test_draws:
        best = max(
            sum(p == a for p, a in zip(t, d["digits"])) / 3.0
            for t in predictions
        ) if predictions else 0.0
        pos_acc_list.append(best)
    pos_acc = sum(pos_acc_list) / len(pos_acc_list)

    # Sum band accuracy (did best prediction match actual sum band?)
    def sum_band(digits):
        s = sum(digits)
        return 0 if s <= 9 else (1 if s <= 17 else 2)

    # Span band accuracy
    def span_band(digits):
        sp = max(digits) - min(digits)
        return 0 if sp <= 3 else (1 if sp <= 6 else 2)

    sb_hits = sum(1 for d in test_draws if sum_band(d["digits"]) in {sum_band(t) for t in predictions})
    spb_hits = sum(1 for d in test_draws if span_band(d["digits"]) in {span_band(t) for t in predictions})

    return {
        "n_train": len(train_draws),
        "n_test": n,
        "direct_hits": direct_hits,
        "direct_hit_rate": round(direct_rate, 6),
        "box_hit_rate": round(box_rate, 6),
        "position_digit_accuracy": round(pos_acc, 6),
        "sum_band_accuracy": round(sb_hits / n, 6),
        "span_band_accuracy": round(spb_hits / n, 6),
        "random_baseline": random_baseline,
        "edge_vs_random": round(edge, 6),
    }


# ── Binomial permutation test (analytical) ────────────────────────────────────

def binomial_permutation_test(direct_hits, n_test, random_baseline):
    """
    One-sided binomial test: H0: p = random_baseline, H1: p > random_baseline.
    Returns p-value, effect_size (Cohen's h), and confidence level.
    Analytical equivalent — no slow MC simulation.
    """
    if n_test == 0:
        return {"p_value": 1.0, "effect_size": 0.0, "test_type": "binomial_analytical",
                "significant_p05": False, "significant_p01": False}
    result = stats.binomtest(
        k=direct_hits,
        n=n_test,
        p=random_baseline,
        alternative="greater"
    )
    p_val = result.pvalue
    # Cohen's h effect size
    p_hat = direct_hits / n_test
    h = 2 * (math.asin(math.sqrt(p_hat)) - math.asin(math.sqrt(random_baseline)))
    return {
        "p_value": round(float(p_val), 8),
        "effect_size_cohens_h": round(h, 6),
        "test_type": "binomial_one_sided_greater",
        "significant_p05": bool(p_val < 0.05),
        "significant_p01": bool(p_val < 0.01),
        "observed_rate": round(p_hat, 6),
        "null_rate": random_baseline,
        "n_test": n_test,
        "direct_hits": direct_hits,
    }


# ── Walk-forward OOS ──────────────────────────────────────────────────────────

def run_oos_folds(draws, strategy_name, strategy_fn):
    n = len(draws)
    fold_results = {}
    combined_hits = {tn: 0 for tn in TOP_NS}
    combined_n = {tn: 0 for tn in TOP_NS}

    for (train_end_frac, test_start_frac, test_end_frac, fold_name) in OOS_FOLDS:
        train_end = int(n * train_end_frac)
        test_start = int(n * test_start_frac)
        test_end = int(n * test_end_frac)
        train = draws[:train_end]
        test = draws[test_start:test_end]

        fold_data = {
            "train_size": len(train),
            "test_size": len(test),
            "train_end_idx": train_end,
            "test_start_idx": test_start,
            "test_end_idx": test_end,
        }
        for top_n in TOP_NS:
            metrics = compute_metrics(strategy_fn, train, test, top_n)
            if metrics:
                fold_data[f"top{top_n}"] = metrics
                combined_hits[top_n] += metrics["direct_hits"]
                combined_n[top_n] += metrics["n_test"]
        fold_results[fold_name] = fold_data

    # Combined OOS permutation test across all folds
    permutation_tests = {}
    for top_n in TOP_NS:
        baseline = top_n / 1000.0
        permutation_tests[f"top{top_n}"] = binomial_permutation_test(
            combined_hits[top_n], combined_n[top_n], baseline
        )

    return fold_results, permutation_tests, combined_hits, combined_n


# ── Per-strategy decision ─────────────────────────────────────────────────────

def decide_strategy(strategy_name, fold_results, permutation_tests, combined_hits, combined_n):
    """
    Decision logic:
    - ADVANCE_TO_P99_CANDIDATE: p_value < 0.05 at top20 AND edge > 0 in all folds at top20
    - HOLD_FOR_MORE_EVIDENCE: mixed results or borderline
    - REJECT_CONFIRMED: consistent negative edge
    """
    # Top20 combined stats
    top20_hits = combined_hits.get(20, 0)
    top20_n = combined_n.get(20, 0)
    top20_perm = permutation_tests.get("top20", {})
    top20_sig = top20_perm.get("significant_p05", False)
    top20_edge = (top20_hits / top20_n - 0.02) if top20_n > 0 else 0

    # Check consistency: how many folds have positive edge at top20?
    fold_edges_top20 = []
    for fold_name, fold_data in fold_results.items():
        if "top20" in fold_data:
            e = fold_data["top20"].get("edge_vs_random", 0)
            fold_edges_top20.append(e)

    n_positive_folds = sum(1 for e in fold_edges_top20 if e > 0)
    n_folds = len(fold_edges_top20)

    # P99 candidate threshold: significant AND consistent across folds
    if top20_sig and n_positive_folds == n_folds and top20_edge > 0.05:
        decision = "ADVANCE_TO_P99_CANDIDATE"
        reason = (f"p_value={top20_perm.get('p_value', 'N/A'):.4f} < 0.05, "
                  f"edge={top20_edge:.4f} > 0.05 threshold, "
                  f"all {n_folds}/{n_folds} OOS folds positive")
    elif top20_edge < -0.01:
        decision = "REJECT_CONFIRMED"
        reason = f"Consistent negative edge at top20: {top20_edge:.4f}"
    else:
        decision = "HOLD_FOR_MORE_EVIDENCE"
        reason = (f"p_value={top20_perm.get('p_value', 'N/A')}, "
                  f"positive_folds={n_positive_folds}/{n_folds}, "
                  f"edge={top20_edge:.4f}")

    return {
        "decision": decision,
        "reason": reason,
        "top20_combined_hits": top20_hits,
        "top20_combined_n": top20_n,
        "top20_edge_vs_random": round(top20_edge, 6),
        "n_positive_folds": n_positive_folds,
        "n_total_folds": n_folds,
        "p_value_top20": top20_perm.get("p_value"),
        "significant_p05": top20_sig,
        "effect_size_cohens_h": top20_perm.get("effect_size_cohens_h"),
    }


# ── Ensemble v2 design ────────────────────────────────────────────────────────

def run_ensemble_v2_review(draws):
    """Compare ensemble_v2 vs ensemble_v1 OOS performance."""
    n = len(draws)
    # Use holdout fold (last 1/6)
    train_end = int(n * 5 / 6)
    test_start = train_end
    train = draws[:train_end]
    test = draws[test_start:]

    v1_results = {}
    v2_results = {}
    for top_n in TOP_NS:
        m1 = compute_metrics(ensemble_rank_v1, train, test, top_n)
        m2 = compute_metrics(ensemble_rank_v2, train, test, top_n)
        if m1:
            v1_results[f"top{top_n}"] = m1
        if m2:
            v2_results[f"top{top_n}"] = m2

    # Compare at top20
    v1_top20 = v1_results.get("top20", {})
    v2_top20 = v2_results.get("top20", {})
    v2_edge = v2_top20.get("edge_vs_random", 0)
    v1_edge = v1_top20.get("edge_vs_random", 0)
    delta = round(v2_edge - v1_edge, 6)

    recommendation = "PROCEED_TO_P99_DRY_RUN" if v2_edge > 0.05 else "HOLD_FOR_MORE_EVIDENCE"

    return {
        "description": "ensemble_rank_v2 (excludes position_cold_rebound_topk)",
        "members": [
            "position_frequency_topk",
            "recent_position_hot_topk",
            "sum_band_frequency",
            "span_band_frequency",
        ],
        "excluded": ["position_cold_rebound_topk"],
        "fusion_method": "reciprocal_rank_fusion",
        "rrf_k": 60,
        "holdout_fold_v1": v1_results,
        "holdout_fold_v2": v2_results,
        "top20_v1_edge": round(v1_edge, 6),
        "top20_v2_edge": round(v2_edge, 6),
        "top20_v2_vs_v1_delta": delta,
        "v2_improves_over_v1": delta > 0,
        "recommendation": recommendation,
        "expected_risks": [
            "4-member ensemble may underperform 5-member if removed strategy had residual positive signal in subsets",
            "RRF equally weights all 4 members; learned weights may improve performance",
            "OOS holdout fold is 1/6 of 4115 draws (~686 draws) — limited statistical power",
            "sum_band and span_band use same position_frequency secondary ranking — partial overlap",
        ],
        "required_future_validation": [
            "P99 controlled dry-run on new draws only (prospective)",
            "Walk-forward OOS on latest 500 draws to detect regime change",
            "Permutation test p < 0.05 in at least 3/4 OOS folds",
            "Monthly stability std < 0.12 over 12+ months",
            "Sharpe Ratio > 0 before VALIDATED label",
        ],
        "p99_dry_run_eligible": v2_edge > 0.05,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"[P98] Loading 3_STAR draws from {DB_PATH}...")
    draws = load_draws()
    n = len(draws)
    print(f"[P98] Loaded {n} draws")
    assert n >= 4000, f"Expected ~4115 draws, got {n}"

    strategy_results = {}
    strategy_decisions = {}

    print(f"[P98] Running OOS + permutation for {len(P97_PROVISIONAL)} PROVISIONAL strategies...")
    for strat_name in P97_PROVISIONAL:
        fn = STRATEGY_FNS[strat_name]
        print(f"  [P98] Strategy: {strat_name}")
        fold_results, permutation_tests, combined_hits, combined_n = run_oos_folds(draws, strat_name, fn)
        decision_data = decide_strategy(strat_name, fold_results, permutation_tests, combined_hits, combined_n)
        strategy_results[strat_name] = {
            "p97_classification": "PROVISIONAL",
            "oos_folds": fold_results,
            "permutation_tests": permutation_tests,
            "combined_hits": combined_hits,
            "combined_n": combined_n,
        }
        strategy_decisions[strat_name] = decision_data
        print(f"    → {decision_data['decision']}: {decision_data['reason'][:80]}")

    # REJECT strategy: include as reference, mark explicitly as NOT_REVIEWED
    strategy_results["position_cold_rebound_topk"] = {
        "p97_classification": "REJECT",
        "oos_review": "NOT_RUN",
        "reason": "REJECT in P97 — excluded from P98 OOS review and ensemble_v2",
    }
    strategy_decisions["position_cold_rebound_topk"] = {
        "decision": "REJECT_CONFIRMED",
        "reason": "REJECT confirmed in P97 (avg_edge=-0.044924). Not re-reviewed in P98.",
        "oos_review": "NOT_RUN",
    }

    # Ensemble v2
    print("[P98] Running ensemble_v2 design review...")
    ensemble_v2 = run_ensemble_v2_review(draws)
    print(f"  ensemble_v2 recommendation: {ensemble_v2['recommendation']}")

    # Overall P98 classification
    advance_count = sum(1 for d in strategy_decisions.values() if d.get("decision") == "ADVANCE_TO_P99_CANDIDATE")
    hold_count = sum(1 for d in strategy_decisions.values() if d.get("decision") == "HOLD_FOR_MORE_EVIDENCE")

    if advance_count >= 1:
        classification = "P98_SPECIAL3_OOS_PERMUTATION_REVIEW_READY"
    else:
        classification = "P98_SPECIAL3_OOS_REVIEW_INCONCLUSIVE"

    # Build output
    output = {
        "task": "special3_oos_permutation_review",
        "phase": "P98",
        "dry_run": True,
        "db_writes": False,
        "replay_rows_changed": 0,
        "no_production_promotion": True,
        "special4_status": "DATA_GAP_BLOCKING",
        "special4_backtest": "NOT_RUN",
        "generated": TODAY,
        "random_seed": RANDOM_SEED,
        "draws_loaded": n,
        "p97_input_summary": {
            "draws_used": n,
            "windows_used": [150, 500, 1500],
            "provisional_strategies": P97_PROVISIONAL,
            "rejected_strategies": P97_REJECT,
            "p97_classification": "P97_SPECIAL3_SPECIAL4_DRYRUN_CLOSURE_READY",
        },
        "oos_method": "walk_forward_4_fold_chronological",
        "permutation_method": "binomial_analytical_one_sided",
        "oos_folds_definition": [
            {"fold": "fold_a_early",  "train_frac": "0→1/3", "test_frac": "1/3→1/2"},
            {"fold": "fold_b_mid",    "train_frac": "0→1/2", "test_frac": "1/2→2/3"},
            {"fold": "fold_c_late",   "train_frac": "0→2/3", "test_frac": "2/3→5/6"},
            {"fold": "fold_d_holdout","train_frac": "0→5/6", "test_frac": "5/6→1"},
        ],
        "strategy_results": strategy_results,
        "strategy_decisions": strategy_decisions,
        "ensemble_v2": ensemble_v2,
        "summary": {
            "provisional_reviewed": len(P97_PROVISIONAL),
            "advance_to_p99": advance_count,
            "hold_for_evidence": hold_count,
            "reject_confirmed": 1,
            "ensemble_v2_recommendation": ensemble_v2["recommendation"],
            "ensemble_v2_p99_eligible": ensemble_v2["p99_dry_run_eligible"],
        },
        "classification": classification,
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"[P98] Output written: {OUT_PATH}")
    print(f"[P98] Classification: {classification}")
    return output


if __name__ == "__main__":
    main()
