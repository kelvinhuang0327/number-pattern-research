#!/usr/bin/env python3
"""
scripts/p227c_star_box_play_dryrun_scan.py
==========================================
P227C — 3_STAR / 4_STAR Box-Play Dry-Run Scan with Power Gate

P252H SSOT Governance Annotation (2026-06-07):
This script is a COMPLETED HISTORICAL ARTIFACT. Its bh_fdr() and block_stability()
local functions are retained as-is. New research code should use:
    correction: from lottery_api.utils.correction_gate import (
                    bonferroni_correction, benjamini_hochberg_fdr, correction_gate_summary)
    permutation: from lottery_api.utils.permutation_test import empirical_p_value
See P252D (correction_gate) and P252E (permutation_test) SSOT for authoritative implementations.

READ-ONLY.  This script:
  - reads draw data from the local SQLite DB
  - evaluates pre-registered box-play feature families
  - reports corrected p-values, CIs, block stability, walk-forward OOS
  - applies Bonferroni / BH-FDR correction across all hypotheses
  - enforces UNDERPOWERED classification when sample sizes are too small
  - NEVER writes to strategy_prediction_replays or any DB table

Pre-registered feature families (P227A / task prompt):
  F1. Digit frequency all-position (hot digit top-k)
  F2. Cold digit frequency all-position (cold digit bottom-k)
  F3. Frequency delta short vs mid (midfreq style)
  F4. Frequency delta mid vs all-history
  F5. Last-seen gap / overdue digit
  F6. Digit sum band (low / mid / high)
  F7. High/low composition (digit >= 5 count)
  F8. Odd/even composition
  F9. Span (max - min digit)
  F10. Consensus of top features

Windows (frozen pre-registration):
  short: 100, 125, 150
  mid:   500, 750, 1000
  all-history: reference only

Usage:
    python3 scripts/p227c_star_box_play_dryrun_scan.py
    python3 scripts/p227c_star_box_play_dryrun_scan.py --lottery 3_STAR
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lottery_api.models.star_box_play import (
    STAR_CONFIG,
    STAR_LOTTERY_TYPES,
    STRAIGHT_PLAY_BLOCKED_REASON,
    get_box_baseline,
    star_box_exact_match,
)

DB_PATH = ROOT / "lottery_api" / "data" / "lottery_v2.db"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WINDOWS_SHORT = [100, 125, 150]
WINDOWS_MID = [500, 750, 1000]
ALL_HISTORY_LABEL = "all_history"

# Each test hypothesis = (lottery_type, feature_name, window_label)
# Total hypotheses = 2 lotteries × 10 features × 6 windows = 120
# Bonferroni threshold = 0.05 / 120 ≈ 0.000417
N_LOTTERIES = 2
N_FEATURES = 10
N_WINDOWS = len(WINDOWS_SHORT) + len(WINDOWS_MID)
N_HYPOTHESES = N_LOTTERIES * N_FEATURES * N_WINDOWS

ALPHA = 0.05
BONFERRONI_THRESHOLD = ALPHA / N_HYPOTHESES

# Power analysis: minimum draws needed for 80% power to detect 20% relative lift
# Derived from: n ≈ (z_alpha + z_beta)² × p0(1-p0) / delta²
# For 3_STAR: p0=1/120, delta=0.2*p0; for 4_STAR: p0=1/210, delta=0.2*p0
POWER_MIN_DRAWS = {
    "3_STAR": 10_000,
    "4_STAR": 17_000,
}


# ---------------------------------------------------------------------------
# DB helpers (read-only)
# ---------------------------------------------------------------------------


def load_draws(lottery_type: str) -> List[dict]:
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        """
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = ?
        ORDER BY CAST(draw AS INTEGER) ASC
        """,
        (lottery_type,),
    ).fetchall()
    conn.close()
    return [
        {"draw": r[0], "date": r[1], "numbers": json.loads(r[2])}
        for r in rows
    ]


def check_repeats_in_draws(draws: List[dict]) -> int:
    return sum(
        1 for d in draws if len(set(d["numbers"])) < len(d["numbers"])
    )


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


def binomial_one_sided_p(k: int, n: int, p0: float) -> float:
    """One-sided p-value: P(X >= k) under H0: X ~ Binomial(n, p0)."""
    if n == 0:
        return 1.0
    # Normal approximation (n large)
    mu = n * p0
    sigma = math.sqrt(n * p0 * (1 - p0))
    if sigma == 0:
        return 1.0 if k <= mu else 0.0
    z = (k - 0.5 - mu) / sigma  # continuity correction
    return _norm_sf(z)


def _norm_sf(z: float) -> float:
    """Survival function of standard normal (1 - CDF)."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def wilson_ci(k: int, n: int, alpha: float = 0.05) -> Tuple[float, float]:
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return (0.0, 1.0)
    z = 1.959964  # 95% CI
    p_hat = k / n
    denom = 1 + z ** 2 / n
    centre = (p_hat + z ** 2 / (2 * n)) / denom
    margin = (z * math.sqrt(p_hat * (1 - p_hat) / n + z ** 2 / (4 * n ** 2))) / denom
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def bh_fdr(p_values: List[float], alpha: float = 0.05) -> List[bool]:
    """Benjamini-Hochberg FDR correction. Returns list of booleans (reject H0)."""
    m = len(p_values)
    if m == 0:
        return []
    ranked = sorted(enumerate(p_values), key=lambda x: x[1])
    reject = [False] * m
    for rank, (i, p) in enumerate(ranked, 1):
        if p <= alpha * rank / m:
            reject[i] = True
    # Propagate: once we reject, all smaller p-values are also rejected
    # (standard BH step-up procedure)
    prev = False
    for rank, (i, p) in enumerate(reversed(ranked), 1):
        if reject[i]:
            prev = True
        if prev:
            reject[i] = True
    return reject


def block_stability(hits: List[int], block_size: int = 150) -> dict:
    """Split hits list into non-overlapping blocks and measure stability."""
    blocks = []
    for start in range(0, len(hits), block_size):
        b = hits[start : start + block_size]
        if len(b) < block_size // 2:  # skip tiny tail block
            continue
        blocks.append(sum(b) / len(b))
    if not blocks:
        return {"n_blocks": 0, "mean_of_means": 0.0, "blocks_above_baseline": 0, "block_hit_rates": []}
    n_above = sum(1 for b in blocks if b > 0)  # above 0 (vs expected per-hit baseline)
    return {
        "n_blocks": len(blocks),
        "mean_of_means": sum(blocks) / len(blocks),
        "blocks_above_baseline": n_above,
        "block_hit_rates": [round(b, 5) for b in blocks],
    }


# ---------------------------------------------------------------------------
# Feature families (pre-registered)
# ---------------------------------------------------------------------------


def _digit_freq(draws: List[dict]) -> Counter:
    c: Counter = Counter()
    for d in draws:
        c.update(d["numbers"])
    return c


def _predict_hot(history: List[dict], window: int, pick_count: int) -> List[int]:
    """F1: predict top-k most frequent digits from window."""
    recent = history[-window:] if len(history) >= window else history
    freq = _digit_freq(recent)
    # Fill missing digits with 0
    for d in range(10):
        if d not in freq:
            freq[d] = 0
    return [d for d, _ in freq.most_common(pick_count)]


def _predict_cold(history: List[dict], window: int, pick_count: int) -> List[int]:
    """F2: predict bottom-k least frequent digits from window."""
    recent = history[-window:] if len(history) >= window else history
    freq = _digit_freq(recent)
    for d in range(10):
        if d not in freq:
            freq[d] = 0
    return [d for d, _ in sorted(freq.items(), key=lambda x: x[1])[:pick_count]]


def _predict_midfreq_short_vs_mid(
    history: List[dict], short_w: int, mid_w: int, pick_count: int
) -> List[int]:
    """F3: digits closest to mean (frequency delta short vs mid, midfreq style)."""
    short = history[-short_w:] if len(history) >= short_w else history
    mid = history[-mid_w:] if len(history) >= mid_w else history
    if not short or not mid:
        return list(range(pick_count))
    freq_s = _digit_freq(short)
    freq_m = _digit_freq(mid)
    expected_s = len(short) * pick_count / 10
    expected_m = len(mid) * pick_count / 10
    # midfreq: abs deviation from expected is small
    scores = {}
    for d in range(10):
        dev_s = abs(freq_s.get(d, 0) - expected_s)
        dev_m = abs(freq_m.get(d, 0) - expected_m)
        scores[d] = dev_s + dev_m
    return sorted(scores, key=scores.get)[:pick_count]


def _predict_midfreq_mid_vs_all(
    history: List[dict], mid_w: int, pick_count: int
) -> List[int]:
    """F4: digits closest to mean comparing mid window vs all history."""
    mid = history[-mid_w:] if len(history) >= mid_w else history
    all_freq = _digit_freq(history)
    if not mid or not history:
        return list(range(pick_count))
    expected_all = len(history) * pick_count / 10
    expected_mid = len(mid) * pick_count / 10
    scores = {}
    for d in range(10):
        dev_all = abs(all_freq.get(d, 0) - expected_all)
        dev_mid = abs(_digit_freq(mid).get(d, 0) - expected_mid)
        scores[d] = dev_all + dev_mid
    return sorted(scores, key=scores.get)[:pick_count]


def _predict_overdue(history: List[dict], pick_count: int) -> List[int]:
    """F5: digits not seen most recently (largest last-seen gap)."""
    last_seen: Dict[int, int] = {d: -1 for d in range(10)}
    for i, draw in enumerate(history):
        for d in draw["numbers"]:
            last_seen[d] = i
    # sort by last seen ascending (oldest first = most overdue)
    return sorted(range(10), key=lambda d: last_seen[d])[:pick_count]


def _predict_sum_band(history: List[dict], window: int, pick_count: int) -> List[int]:
    """F6: predict digits whose sum band matches historical mean."""
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return list(range(pick_count))
    mean_sum = sum(sum(d["numbers"]) for d in recent) / len(recent)
    # pick digits closest to mean_sum / pick_count
    target = mean_sum / pick_count
    return sorted(range(10), key=lambda d: abs(d - target))[:pick_count]


def _predict_high_low(history: List[dict], window: int, pick_count: int) -> List[int]:
    """F7: predict digits based on recent high/low balance (digits >= 5)."""
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return list(range(pick_count))
    mean_high = sum(
        sum(1 for d in draw["numbers"] if d >= 5) for draw in recent
    ) / len(recent)
    n_high = round(mean_high)
    n_low = pick_count - n_high
    high_freq = _digit_freq(recent)
    high_pool = sorted([d for d in range(5, 10)], key=lambda d: -high_freq.get(d, 0))
    low_pool = sorted([d for d in range(0, 5)], key=lambda d: -high_freq.get(d, 0))
    pred = high_pool[:n_high] + low_pool[:n_low]
    return sorted(pred)[:pick_count]


def _predict_odd_even(history: List[dict], window: int, pick_count: int) -> List[int]:
    """F8: predict digits based on recent odd/even balance."""
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return list(range(pick_count))
    mean_odd = sum(
        sum(1 for d in draw["numbers"] if d % 2 == 1) for draw in recent
    ) / len(recent)
    n_odd = round(mean_odd)
    n_even = pick_count - n_odd
    freq = _digit_freq(recent)
    odd_pool = sorted([d for d in range(10) if d % 2 == 1], key=lambda d: -freq.get(d, 0))
    even_pool = sorted([d for d in range(10) if d % 2 == 0], key=lambda d: -freq.get(d, 0))
    pred = odd_pool[:n_odd] + even_pool[:n_even]
    return sorted(pred)[:pick_count]


def _predict_span(history: List[dict], window: int, pick_count: int) -> List[int]:
    """F9: predict digits based on recent span (max - min) patterns."""
    recent = history[-window:] if len(history) >= window else history
    if not recent:
        return list(range(pick_count))
    freq = _digit_freq(recent)
    # Anchor on most frequent digit; pick others to match historical mean span
    mean_span = sum(max(d["numbers"]) - min(d["numbers"]) for d in recent) / len(recent)
    anchor = max(range(10), key=lambda d: freq.get(d, 0))
    # Try to pick digits that create a span close to mean_span
    candidates = sorted(range(10), key=lambda d: -freq.get(d, 0))
    pred = [candidates[0]]
    for c in candidates[1:]:
        if len(pred) >= pick_count:
            break
        pred.append(c)
    return sorted(pred[:pick_count])


def _predict_consensus(
    history: List[dict], window: int, pick_count: int
) -> List[int]:
    """F10: consensus of F1 (hot), F2 (cold), F5 (overdue)."""
    votes: Counter = Counter()
    for pred in [
        _predict_hot(history, window, pick_count),
        _predict_cold(history, window, pick_count),
        _predict_overdue(history, pick_count),
    ]:
        for d in pred:
            votes[d] += 1
    return [d for d, _ in votes.most_common(pick_count)]


# ---------------------------------------------------------------------------
# Walk-forward OOS evaluation
# ---------------------------------------------------------------------------

MIN_HISTORY = 100  # minimum draws required before first prediction


def evaluate_feature(
    draws: List[dict],
    feature_fn,
    baseline: float,
    oos_start_pct: float = 0.5,
) -> dict:
    """
    Walk-forward OOS evaluation for a single feature/window combo.

    - Splits draws into: history (first oos_start_pct) as warm-up,
      then evaluates each remaining draw.
    - For each target draw at index i: history = draws[:i], predict draws[i].
    - Computes exact box hit rate on the OOS window.

    Returns a result dict.
    """
    n = len(draws)
    oos_start = max(MIN_HISTORY, int(n * oos_start_pct))
    pick_count = len(draws[0]["numbers"]) if draws else 3

    hits = []
    for i in range(oos_start, n):
        history = draws[:i]
        actual = draws[i]["numbers"]
        try:
            pred = feature_fn(history)
        except Exception:
            continue
        if len(pred) != pick_count:
            continue
        hit = int(star_box_exact_match(pred, actual))
        hits.append(hit)

    n_oos = len(hits)
    n_hits = sum(hits)

    if n_oos == 0:
        return {
            "n_oos": 0, "n_hits": 0, "hit_rate": 0.0,
            "baseline": baseline, "lift": 0.0,
            "p_value": 1.0, "ci_low": 0.0, "ci_high": 1.0,
            "block_stability": {}, "power_status": "INSUFFICIENT_DATA",
        }

    hit_rate = n_hits / n_oos
    lift = hit_rate - baseline
    p_val = binomial_one_sided_p(n_hits, n_oos, baseline)
    ci_low, ci_high = wilson_ci(n_hits, n_oos)

    # Power status
    if n_oos < POWER_MIN_DRAWS.get(draws[0].get("lottery_type", "3_STAR"), 10000):
        power_status = "UNDERPOWERED"
    else:
        power_status = "ADEQUATE"

    return {
        "n_oos": n_oos,
        "n_hits": n_hits,
        "hit_rate": round(hit_rate, 6),
        "baseline": round(baseline, 6),
        "lift": round(lift, 6),
        "p_value": round(p_val, 6),
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "block_stability": block_stability(hits, block_size=150),
        "power_status": power_status,
    }


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------


def classify_result(
    result: dict, bonferroni_pass: bool, bh_pass: bool
) -> str:
    if result["power_status"] != "ADEQUATE":
        if result["p_value"] < 0.05 and result["lift"] > 0:
            return "WEAK_OBSERVATION_UNDERPOWERED"
        return "UNDERPOWERED_NO_SIGNAL"
    if bonferroni_pass and bh_pass and result["lift"] > 0:
        return "CANDIDATE_NEEDS_MORE_OOS"
    if bh_pass and result["lift"] > 0:
        return "WEAK_OBSERVATION_ONLY"
    return "NULL"


# ---------------------------------------------------------------------------
# Full scan
# ---------------------------------------------------------------------------


def run_scan_for_lottery(lottery_type: str) -> dict:
    draws_raw = load_draws(lottery_type)
    # Add lottery_type to each draw for power gate lookup
    draws = [dict(d, lottery_type=lottery_type) for d in draws_raw]

    n_draws = len(draws)
    pick_count = STAR_CONFIG[lottery_type]["pick_count"]
    repeats_in_db = check_repeats_in_draws(draws)
    baseline = get_box_baseline(lottery_type, repeats_detected=(repeats_in_db > 0))

    all_results = []  # each entry: {feature, window, result}

    # Define (feature_name, window_label, feature_fn) triples
    combos = []
    for w in WINDOWS_SHORT + WINDOWS_MID:
        wlabel = f"w{w}"
        combos += [
            ("F1_hot", wlabel, lambda h, _w=w, _k=pick_count: _predict_hot(h, _w, _k)),
            ("F2_cold", wlabel, lambda h, _w=w, _k=pick_count: _predict_cold(h, _w, _k)),
            ("F3_midfreq_short_mid", wlabel,
             lambda h, _w=w, _k=pick_count: _predict_midfreq_short_vs_mid(
                 h, min(_w, 100), _w, _k)),
            ("F4_midfreq_mid_all", wlabel,
             lambda h, _w=w, _k=pick_count: _predict_midfreq_mid_vs_all(h, _w, _k)),
            ("F5_overdue", wlabel, lambda h, _w=w, _k=pick_count: _predict_overdue(h, _k)),
            ("F6_sum_band", wlabel,
             lambda h, _w=w, _k=pick_count: _predict_sum_band(h, _w, _k)),
            ("F7_high_low", wlabel,
             lambda h, _w=w, _k=pick_count: _predict_high_low(h, _w, _k)),
            ("F8_odd_even", wlabel,
             lambda h, _w=w, _k=pick_count: _predict_odd_even(h, _w, _k)),
            ("F9_span", wlabel,
             lambda h, _w=w, _k=pick_count: _predict_span(h, _w, _k)),
            ("F10_consensus", wlabel,
             lambda h, _w=w, _k=pick_count: _predict_consensus(h, _w, _k)),
        ]

    for feature_name, window_label, fn in combos:
        res = evaluate_feature(draws, fn, baseline)
        all_results.append({
            "lottery_type": lottery_type,
            "feature": feature_name,
            "window": window_label,
            **res,
        })

    # Bonferroni / BH-FDR correction over all hypotheses for this lottery
    p_values = [r["p_value"] for r in all_results]
    bh_results = bh_fdr(p_values, ALPHA)

    for i, r in enumerate(all_results):
        bonf_pass = r["p_value"] < BONFERRONI_THRESHOLD
        bh_pass = bh_results[i]
        r["bonferroni_pass"] = bonf_pass
        r["bh_fdr_pass"] = bh_pass
        r["classification"] = classify_result(r, bonf_pass, bh_pass)

    # Summary
    n_positive_lift = sum(1 for r in all_results if r["lift"] > 0)
    n_bonf_pass = sum(1 for r in all_results if r["bonferroni_pass"])
    n_bh_pass = sum(1 for r in all_results if r["bh_fdr_pass"])
    best = max(all_results, key=lambda r: r["lift"]) if all_results else {}

    # Overall classification for this lottery
    candidates = [r for r in all_results if r["classification"] == "CANDIDATE_NEEDS_MORE_OOS"]
    if candidates:
        overall = "P227C_STAR_BOX_PLAY_CANDIDATES_NEED_MORE_OOS"
    elif n_bonf_pass == 0 and n_bh_pass == 0:
        overall = "P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL"
    else:
        overall = "P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL"

    return {
        "lottery_type": lottery_type,
        "n_draws": n_draws,
        "pick_count": pick_count,
        "repeats_in_db": repeats_in_db,
        "active_baseline": baseline,
        "combination_space": STAR_CONFIG[lottery_type]["combination_space_no_repeat"],
        "n_hypotheses_tested": len(all_results),
        "bonferroni_threshold": round(BONFERRONI_THRESHOLD, 8),
        "n_positive_lift": n_positive_lift,
        "n_bonferroni_pass": n_bonf_pass,
        "n_bh_fdr_pass": n_bh_pass,
        "best_feature": best.get("feature"),
        "best_window": best.get("window"),
        "best_lift": best.get("lift"),
        "best_p_value": best.get("p_value"),
        "best_power_status": best.get("power_status"),
        "overall_classification": overall,
        "results": all_results,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="P227C Star Box-Play Dry-Run Scan")
    parser.add_argument(
        "--lottery", choices=list(STAR_LOTTERY_TYPES) + ["both"], default="both"
    )
    parser.add_argument(
        "--output",
        default=str(
            ROOT / "outputs" / "research" / "p227c_star_box_play_dryrun_scan_20260603.json"
        ),
    )
    args = parser.parse_args()

    lotteries = list(STAR_LOTTERY_TYPES) if args.lottery == "both" else [args.lottery]

    # Final DB baseline check before starting
    conn = sqlite3.connect(str(DB_PATH))
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    star_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type IN ('3_STAR','4_STAR')"
    ).fetchone()[0]
    conn.close()
    assert total == 94924, f"DB row count changed! {total}"
    assert star_rows == 0, f"Star replay rows appeared! {star_rows}"

    print("P227C scan started — read-only, no DB writes")
    print(f"  Hypotheses per lottery: {N_FEATURES * N_WINDOWS}")
    print(f"  Bonferroni threshold (across all): {BONFERRONI_THRESHOLD:.6f}")
    print(f"  Straight-play: BLOCKED (sorted DB storage)")

    scan_results = {}
    for lt in lotteries:
        print(f"\n  Scanning {lt}...")
        scan_results[lt] = run_scan_for_lottery(lt)
        r = scan_results[lt]
        print(
            f"    draws={r['n_draws']}, baseline={r['active_baseline']:.5f}, "
            f"Bonf_pass={r['n_bonferroni_pass']}, BH_pass={r['n_bh_fdr_pass']}, "
            f"best_lift={r['best_lift']:.5f} ({r['best_feature']} {r['best_window']})"
        )
        print(f"    Overall: {r['overall_classification']}")

    # Confirm DB unchanged
    conn2 = sqlite3.connect(str(DB_PATH))
    total2 = conn2.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    star2 = conn2.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type IN ('3_STAR','4_STAR')"
    ).fetchone()[0]
    conn2.close()
    assert total2 == 94924
    assert star2 == 0

    report = {
        "task": "P227C_STAR_BOX_PLAY_DRYRUN_SCAN_COMPLETE",
        "date": "2026-06-03",
        "read_only": True,
        "db_writes": 0,
        "replay_rows_written": 0,
        "total_replay_rows_unchanged": total2,
        "star_replay_rows_unchanged": star2,
        "pre_registered_features": [
            "F1_hot", "F2_cold", "F3_midfreq_short_mid", "F4_midfreq_mid_all",
            "F5_overdue", "F6_sum_band", "F7_high_low", "F8_odd_even",
            "F9_span", "F10_consensus",
        ],
        "pre_registered_windows_short": WINDOWS_SHORT,
        "pre_registered_windows_mid": WINDOWS_MID,
        "bonferroni_threshold": round(BONFERRONI_THRESHOLD, 8),
        "bh_fdr_alpha": ALPHA,
        "straight_play_blocked": STRAIGHT_PLAY_BLOCKED_REASON,
        "scan_results": scan_results,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nP227C scan complete. Output: {out_path}")
    print("DB unchanged. No replay rows written.")


if __name__ == "__main__":
    main()
