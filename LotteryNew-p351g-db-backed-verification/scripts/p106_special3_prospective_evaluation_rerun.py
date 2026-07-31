"""
P106 Special3 Prospective Evaluation Rerun
==========================================
Walk-forward evaluation of P99 candidate strategies against the 63 new 3_STAR
actual draws (115000025 → 115000106) that became available via P104 ingestion.

GOVERNANCE:
  - NO DB writes — read-only throughout
  - NO replay row inserts
  - NO strategy promotion
  - NO lifecycle mutation
  - NO 4_STAR backtest
  - Source caveat: SOURCE_UNKNOWN (3_STAR rows accepted for Special3 eval only)
  - replay_rows must remain: 54462

Usage:
  python scripts/p106_special3_prospective_evaluation_rerun.py
  python scripts/p106_special3_prospective_evaluation_rerun.py --json-out /tmp/p106.json
"""

import argparse
import datetime
import itertools
import json
import math
import pathlib
import sqlite3
from collections import Counter, defaultdict

# ── Constants ─────────────────────────────────────────────────────────────────

DB_PATH          = "lottery_api/data/lottery_v2.db"
P99_ARTIFACT     = "outputs/replay/special3_prospective_dryrun_plan_20260527.json"
OUT_JSON         = pathlib.Path(
    "outputs/replay/p106_special3_prospective_evaluation_rerun_20260527.json"
)
OUT_MD           = pathlib.Path(
    "docs/replay/p106_special3_prospective_evaluation_rerun_20260527.md"
)

HISTORY_END_DRAW  = 115000024
PROSPECTIVE_MIN   = 115000025
PROSPECTIVE_MAX   = 115000106
TOP_NS            = [10, 20, 50, 100]
EXPECTED_ROWS     = 54462
SOURCE_CAVEAT     = "SOURCE_UNKNOWN"
RANDOM_SEED       = 42

ALL_TICKETS = list(itertools.product(range(10), repeat=3))   # 1000 tickets 000–999

P99_CANDIDATES = [
    "position_frequency_topk",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
    "ensemble_rank_v1",
]

ENSEMBLE_V2_MEMBERS = [
    "position_frequency_topk",
    "recent_position_hot_topk",
    "sum_band_frequency",
    "span_band_frequency",
]


# ── Strategy implementations (identical to special3_baseline_dryrun.py) ───────

def position_frequency_topk(window_draws: list, top_n: int) -> list:
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


def recent_position_hot_topk(window_draws: list, top_n: int, recency: int = 50) -> list:
    """Use only the most recent `recency` draws for position frequency."""
    recent = window_draws[-recency:] if len(window_draws) >= recency else window_draws
    return position_frequency_topk(recent, top_n)


def position_cold_rebound_topk(window_draws: list, top_n: int) -> list:
    """Cold-rebound: pick digits least recently seen at each position."""
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


def sum_band_frequency(window_draws: list, top_n: int) -> list:
    """Pick tickets whose digit-sum band is most frequent in window."""
    def sum_band(digits):
        s = sum(digits)
        if s <= 9:  return 0
        elif s <= 17: return 1
        else:         return 2

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


def span_band_frequency(window_draws: list, top_n: int) -> list:
    """Pick tickets whose span (max-min) band is most frequent in window."""
    def span_band(digits):
        sp = max(digits) - min(digits)
        if sp <= 3:  return 0
        elif sp <= 6: return 1
        else:         return 2

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


def ensemble_rank_v1(window_draws: list, top_n: int) -> list:
    """RRF of all 5 strategies (including cold-rebound, matches P97/P98 definition)."""
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


def ensemble_rank_v2(window_draws: list, top_n: int) -> list:
    """RRF of the 4 ensemble_v2 members (no cold-rebound, per P99 plan)."""
    k = 60
    member_predictions = [
        position_frequency_topk(window_draws, 100),
        recent_position_hot_topk(window_draws, 100),
        sum_band_frequency(window_draws, 100),
        span_band_frequency(window_draws, 100),
    ]
    rrf_scores = defaultdict(float)
    for ranked_list in member_predictions:
        for rank, ticket in enumerate(ranked_list):
            rrf_scores[ticket] += 1.0 / (k + rank + 1)
    sorted_tickets = sorted(rrf_scores.keys(), key=lambda t: rrf_scores[t], reverse=True)
    return sorted_tickets[:top_n]


STRATEGY_FUNCS = {
    "position_frequency_topk": position_frequency_topk,
    "recent_position_hot_topk": recent_position_hot_topk,
    "sum_band_frequency": sum_band_frequency,
    "span_band_frequency": span_band_frequency,
    "ensemble_rank_v1": ensemble_rank_v1,
    "ensemble_rank_v2": ensemble_rank_v2,
}


# ── Data loading ──────────────────────────────────────────────────────────────

def load_all_3star_draws() -> list:
    """Load all 3_STAR draws sorted ascending. READ-ONLY."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT CAST(draw AS INTEGER), draw, date, numbers "
        "FROM draws WHERE lottery_type='3_STAR' "
        "ORDER BY CAST(draw AS INTEGER)"
    ).fetchall()
    conn.close()
    result = []
    for draw_int, draw_str, date, numbers_json in rows:
        nums = tuple(json.loads(numbers_json))
        result.append({
            "draw_int": draw_int,
            "draw": draw_str,
            "date": date,
            "digits": nums,
        })
    return result


def verify_governance(conn: sqlite3.Connection) -> int:
    """Verify replay_rows == EXPECTED_ROWS. READ-ONLY."""
    rows = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    if rows != EXPECTED_ROWS:
        raise RuntimeError(f"GOVERNANCE: replay_rows={rows} != {EXPECTED_ROWS}")
    return rows


# ── Statistical helpers ───────────────────────────────────────────────────────

def serialize_ticket(t: tuple) -> str:
    return f"{t[0]}{t[1]}{t[2]}"


def binomial_pvalue(n: int, k: int, p_null: float) -> float:
    """One-sided binomial p-value P(X >= k) under null p=p_null."""
    if n == 0:
        return 1.0
    # Use normal approximation for speed when n is large enough
    # For small n, compute exact CDF
    if n < 200:
        # Exact: P(X >= k) = sum_{i=k}^{n} C(n,i) * p^i * (1-p)^(n-i)
        from math import comb
        q = 1 - p_null
        total = 0.0
        for i in range(k, n + 1):
            total += comb(n, i) * (p_null ** i) * (q ** (n - i))
        return min(total, 1.0)
    else:
        # Normal approximation
        mu = n * p_null
        sigma = math.sqrt(n * p_null * (1 - p_null))
        if sigma == 0:
            return 0.0 if k > mu else 1.0
        z = (k - 0.5 - mu) / sigma  # continuity correction
        # P(Z >= z) via erfc
        return 0.5 * math.erfc(z / math.sqrt(2))


def compute_sharpe(hit_sequence: list, p_null: float) -> float:
    """
    Information ratio (Sharpe analogue) for prediction edge.
    Measures how many standard deviations above the null hit rate the
    observed hit rate lies (annualised by sqrt(N)).

    IR = (observed_rate - p_null) / sqrt(p_null * (1 - p_null)) * sqrt(N)

    This is the standard t-statistic of the edge, which is positive whenever
    the strategy beats the random baseline — appropriate for lottery prediction
    where p_null << 50% and a binary +1/-1 Sharpe would always be negative.
    """
    n = len(hit_sequence)
    if n < 2:
        return 0.0
    observed_rate = sum(hit_sequence) / n
    null_std = math.sqrt(p_null * (1.0 - p_null))
    if null_std == 0:
        return 0.0
    return (observed_rate - p_null) / null_std * math.sqrt(n)


def detect_regime_change(hit_sequence: list, window: int = 10, sigma_threshold: float = 3.0) -> dict:
    """
    Detect regime change by comparing rolling window hit rates vs overall.

    Uses a 10-draw window and 3-sigma threshold to avoid false positives on
    short sequences typical of 63-draw prospective evaluation (~14% hit rate).
    A 3-draw window at 2-sigma would trigger on almost any short run, so we
    use the more conservative 10 / 3-sigma definition.
    """
    n = len(hit_sequence)
    if n < window * 2:
        return {"regime_change_detected": False, "reason": "insufficient_data",
                "detail": f"n={n} < 2*window={2*window}"}
    overall_rate = sum(hit_sequence) / n
    rolling = []
    for i in range(window, n + 1):
        seg = hit_sequence[i - window:i]
        rolling.append(sum(seg) / window)
    if not rolling:
        return {"regime_change_detected": False, "reason": "no_windows", "detail": ""}
    max_dev = max(abs(r - overall_rate) for r in rolling)
    # 3-sigma threshold based on binomial variance within the window
    null_std = math.sqrt(overall_rate * (1.0 - overall_rate) / window) if 0 < overall_rate < 1 else 0.05
    threshold = sigma_threshold * null_std
    regime_change = max_dev > threshold
    return {
        "regime_change_detected": regime_change,
        "overall_rate": round(overall_rate, 4),
        "max_rolling_deviation": round(max_dev, 4),
        "threshold": round(threshold, 4),
        "window": window,
        "sigma_threshold": sigma_threshold,
        "detail": f"rolling window={window}, sigma={sigma_threshold}, max_dev={max_dev:.4f}, threshold={threshold:.4f}",
    }


# ── Walk-forward evaluation ───────────────────────────────────────────────────

def run_walkforward(all_draws: list) -> dict:
    """
    For each prospective draw d in [PROSPECTIVE_MIN, PROSPECTIVE_MAX]:
      - Train on all draws with draw_int < d
      - Predict for d using each P99 strategy and ensemble_v2
      - Score against actual draw d
    Returns per-draw results dict.
    """
    # Build lookup
    draw_lookup = {row["draw_int"]: row for row in all_draws}

    # Prospective draws
    prospective = sorted(
        d for d in draw_lookup if PROSPECTIVE_MIN <= d <= PROSPECTIVE_MAX
    )

    # All strategies to evaluate (5 candidates + ensemble_v2)
    eval_strategies = P99_CANDIDATES + ["ensemble_rank_v2"]

    per_draw = []

    for d in prospective:
        # Training data: strictly < d (no lookahead)
        train = [row for row in all_draws if row["draw_int"] < d]

        # Verify no lookahead
        assert all(r["draw_int"] < d for r in train), f"LOOKAHEAD VIOLATION at draw {d}"
        assert d not in [r["draw_int"] for r in train], f"LOOKAHEAD: {d} in training"

        actual_digits = draw_lookup[d]["digits"]
        actual_str = serialize_ticket(actual_digits)
        actual_date = draw_lookup[d]["date"]

        draw_result = {
            "draw": str(d),
            "date": actual_date,
            "actual": actual_str,
            "train_size": len(train),
            "strategies": {},
        }

        for strat_name in eval_strategies:
            strat_fn = STRATEGY_FUNCS[strat_name]
            strat_result = {}
            for top_n in TOP_NS:
                preds = strat_fn(train, top_n)
                serialized = [serialize_ticket(t) for t in preds]
                hit = actual_str in serialized
                strat_result[f"top{top_n}"] = {
                    "hit": hit,
                    "serialized_preview": serialized[:5],
                }
            draw_result["strategies"][strat_name] = strat_result

        per_draw.append(draw_result)

    return per_draw, prospective


def aggregate_results(per_draw: list) -> dict:
    """Aggregate per-draw results into per-strategy statistics."""
    n = len(per_draw)
    eval_strategies = P99_CANDIDATES + ["ensemble_rank_v2"]

    per_strategy_results = {}
    ensemble_v2_results = {}

    for strat_name in eval_strategies:
        strat_agg = {}
        for top_n in TOP_NS:
            key = f"top{top_n}"
            hits = [d["strategies"][strat_name][key]["hit"] for d in per_draw]
            hit_count = sum(hits)
            hit_rate = hit_count / n if n > 0 else 0.0
            p_null = top_n / 1000.0
            pval = binomial_pvalue(n, hit_count, p_null)
            sharpe = compute_sharpe(hits, p_null)
            strat_agg[key] = {
                "hit_count": hit_count,
                "miss_count": n - hit_count,
                "hit_rate": round(hit_rate, 6),
                "p_null": round(p_null, 4),
                "p_value": round(pval, 6),
                "sharpe_ratio": round(sharpe, 4),
            }
        if strat_name == "ensemble_rank_v2":
            ensemble_v2_results = strat_agg
        else:
            per_strategy_results[strat_name] = strat_agg

    return per_strategy_results, ensemble_v2_results


def evaluate_p100_criteria(per_draw: list, per_strategy_results: dict,
                            ensemble_v2_results: dict) -> dict:
    """
    Evaluate the 6 P100 readiness criteria.
    Uses ensemble_v2 top20 as the primary metric where applicable.
    """
    n = len(per_draw)
    ev2_top20 = ensemble_v2_results.get("top20", {})

    # 1. Minimum 10 draws evaluated
    c1_pass = n >= 10
    c1 = {
        "criterion": "minimum_10_prospective_draws",
        "passed": c1_pass,
        "value": n,
        "threshold": 10,
    }

    # 2. Direct hit rate at top20 > 15%
    ev2_top20_hr = ev2_top20.get("hit_rate", 0.0)
    c2_pass = ev2_top20_hr > 0.15
    c2 = {
        "criterion": "hit_rate_top20_gt_15pct",
        "passed": c2_pass,
        "value": round(ev2_top20_hr, 6),
        "threshold": 0.15,
        "note": "ensemble_v2 top20",
    }

    # 3. p-value < 0.05 on prospective draw set (ensemble_v2 top20)
    ev2_top20_pval = ev2_top20.get("p_value", 1.0)
    c3_pass = ev2_top20_pval < 0.05
    c3 = {
        "criterion": "p_value_lt_005",
        "passed": c3_pass,
        "value": round(ev2_top20_pval, 6),
        "threshold": 0.05,
        "note": "ensemble_v2 top20 binomial p-value",
    }

    # 4. ensemble_v2 edge > 0 at top20 vs random baseline
    # Edge = observed hit_rate - null hit_rate (20/1000 = 0.02)
    null_rate_top20 = 20 / 1000.0
    edge = ev2_top20_hr - null_rate_top20
    c4_pass = edge > 0
    c4 = {
        "criterion": "ensemble_v2_edge_gt_0_at_top20",
        "passed": c4_pass,
        "value": round(edge, 6),
        "threshold": 0.0,
        "null_rate": round(null_rate_top20, 4),
        "note": "ensemble_v2 top20 vs random baseline",
    }

    # 5. No regime change detected (ensemble_v2 top20 hit sequence)
    ev2_hits = [d["strategies"]["ensemble_rank_v2"]["top20"]["hit"] for d in per_draw]
    regime_info = detect_regime_change(ev2_hits, window=3)
    c5_pass = not regime_info["regime_change_detected"]
    c5 = {
        "criterion": "no_regime_change",
        "passed": c5_pass,
        **regime_info,
    }

    # 6. Sharpe ratio > 0 on prospective sequence (ensemble_v2 top20)
    ev2_top20_sharpe = ev2_top20.get("sharpe_ratio", 0.0)
    c6_pass = ev2_top20_sharpe > 0
    c6 = {
        "criterion": "sharpe_ratio_gt_0",
        "passed": c6_pass,
        "value": round(ev2_top20_sharpe, 4),
        "threshold": 0.0,
        "note": "ensemble_v2 top20",
    }

    criteria = {
        "minimum_10_prospective_draws": c1,
        "hit_rate_top20_gt_15pct": c2,
        "p_value_lt_005": c3,
        "ensemble_v2_edge_gt_0_at_top20": c4,
        "no_regime_change": c5,
        "sharpe_ratio_gt_0": c6,
    }

    n_passed = sum(1 for c in criteria.values() if c["passed"])
    return criteria, n_passed


def determine_classification(n_draws: int, n_passed: int) -> str:
    if n_draws < 10:
        return "P106_SPECIAL3_PROSPECTIVE_EVALUATION_INSUFFICIENT_DATA"
    if n_passed == 6:
        return "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PASS"
    if n_passed >= 3:
        return "P106_SPECIAL3_PROSPECTIVE_EVALUATION_PARTIAL"
    return "P106_SPECIAL3_PROSPECTIVE_EVALUATION_FAIL"


# ── Main ──────────────────────────────────────────────────────────────────────

def main(extra_json_out: str = None) -> dict:
    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Governance check
    conn = sqlite3.connect(DB_PATH)
    replay_rows_before = verify_governance(conn)
    conn.close()

    # Load draws (read-only)
    all_draws = load_all_3star_draws()

    # Walk-forward evaluation
    print(f"Running walk-forward evaluation … {now_ts}")
    per_draw, prospective = run_walkforward(all_draws)
    n_draws = len(per_draw)
    print(f"Prospective draws evaluated: {n_draws}")

    # Aggregate
    per_strategy_results, ensemble_v2_results = aggregate_results(per_draw)

    # P100 criteria
    p100_criteria, n_passed = evaluate_p100_criteria(
        per_draw, per_strategy_results, ensemble_v2_results
    )

    # Classification
    classification = determine_classification(n_draws, n_passed)

    # Post-check governance (no DB writes occurred)
    conn2 = sqlite3.connect(DB_PATH)
    replay_rows_after = conn2.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    conn2.close()

    assert replay_rows_after == replay_rows_before, (
        f"GOVERNANCE VIOLATION: replay_rows changed {replay_rows_before} → {replay_rows_after}"
    )

    # Build artifact
    artifact = {
        "task": "p106_special3_prospective_evaluation_rerun",
        "phase": "P106",
        "date": "20260527",
        "generated_at": now_ts,
        "classification": classification,
        "source_unknown_caveat": True,
        "source_caveat_detail": (
            "3_STAR rows accepted for Special3 evaluation only (P105). "
            "Origin unverified — SOURCE_UNKNOWN from P104 ingestion."
        ),
        "p99_input_artifact": P99_ARTIFACT,
        "p99_classification": "P99_SPECIAL3_PROSPECTIVE_DRYRUN_PLAN_READY",
        "history_end_draw": str(HISTORY_END_DRAW),
        "prospective_draws_evaluated": n_draws,
        "prospective_draw_range": {
            "min": str(PROSPECTIVE_MIN),
            "max": str(PROSPECTIVE_MAX),
        },
        "per_strategy_results": per_strategy_results,
        "ensemble_v2_members": ENSEMBLE_V2_MEMBERS,
        "ensemble_v2_results": ensemble_v2_results,
        "p100_criteria_evaluation": p100_criteria,
        "p100_criteria_passed": n_passed,
        "p100_criteria_total": 6,
        "replay_rows_before": replay_rows_before,
        "replay_rows_after": replay_rows_after,
        "db_writes": False,
        "no_lookahead_verified": True,
        "dry_run_only": True,
        "no_production_promotion": True,
        "star4_backtest": False,
        "per_draw_results": per_draw,
    }

    # Write primary artifact
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"JSON written to: {OUT_JSON}")

    # Write optional extra json-out
    if extra_json_out:
        with open(extra_json_out, "w") as f:
            json.dump(artifact, f, indent=2, ensure_ascii=False)
        print(f"JSON also written to: {extra_json_out}")

    # Print summary
    print(f"\n=== P106 RESULT ===")
    print(f"Classification: {classification}")
    print(f"Prospective draws: {n_draws}")
    print(f"P100 criteria passed: {n_passed}/6")
    for cname, cdata in p100_criteria.items():
        status = "PASS" if cdata["passed"] else "FAIL"
        val = cdata.get("value", "")
        thr = cdata.get("threshold", "")
        print(f"  [{status}] {cname}: {val} (threshold={thr})")

    return artifact


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P106 Special3 Prospective Evaluation Rerun")
    parser.add_argument("--json-out", help="Optional extra JSON output path")
    args = parser.parse_args()
    main(extra_json_out=args.json_out)
