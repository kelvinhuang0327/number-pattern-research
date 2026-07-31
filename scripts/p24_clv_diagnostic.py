"""
P24 CLV Robustness Diagnostic Script
Uses P23-pinned snapshot (first 2788 lines of tsl_odds_history.jsonl)
Outputs: bootstrap CI, trimmed mean, outlier sensitivity, per-market diagnostic
paper_only=true / diagnostic_only=true
"""
import json
import math
import random
from collections import defaultdict
from datetime import timezone
from dateutil.parser import parse as dtparse

# ── Config ──────────────────────────────────────────────────────────────────
P23_PINNED_LINE_COUNT = 2788
P23_PINNED_SHA256 = "ac1320de7efa23e645ffb81f27c9825634c3d63566ed8ccf5c62ee6cf7c94118"
PREGAME_MIN_HOURS = 2.0
CLOSING_WINDOW_HOURS = 2.0
BOOTSTRAP_N = 5000
random.seed(42)


def to_utc(s):
    if not s:
        return None
    try:
        dt = dtparse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def get_decimal_odds(record, market_code):
    markets = record.get("markets", [])
    for m in markets:
        if m.get("marketCode") == market_code:
            outcomes = m.get("outcomes", [])
            if len(outcomes) >= 2:
                try:
                    return [float(o["odds"]) for o in outcomes[:2]]
                except (ValueError, KeyError):
                    return None
    return None


def compute_clv(pre_odds_list, clo_odds_list):
    """CLV% for each outcome: (pregame_odds - closing_odds) / closing_odds * 100"""
    clv_values = []
    for pre, clo in zip(pre_odds_list, clo_odds_list):
        if clo > 0:
            clv_values.append((pre - clo) / clo * 100.0)
    return clv_values


def bootstrap_mean_ci(data, n=5000, ci=0.95):
    if not data:
        return None, None, None
    mu = sum(data) / len(data)
    boot_means = []
    n_data = len(data)
    for _ in range(n):
        sample = [random.choice(data) for _ in range(n_data)]
        boot_means.append(sum(sample) / n_data)
    boot_means.sort()
    lo_idx = int((1 - ci) / 2 * n)
    hi_idx = int((1 - (1 - ci) / 2) * n) - 1
    return mu, boot_means[lo_idx], boot_means[hi_idx]


def trimmed_mean(data, trim_pct=0.05):
    if not data:
        return None
    s = sorted(data)
    k = int(len(s) * trim_pct)
    trimmed = s[k: len(s) - k] if k > 0 else s
    return sum(trimmed) / len(trimmed) if trimmed else None


def bootstrap_rate_ci(positive, total, n=5000, ci=0.95):
    if total == 0:
        return None, None, None
    rate = positive / total
    boot_rates = []
    for _ in range(n):
        hits = sum(1 for _ in range(total) if random.random() < rate)
        boot_rates.append(hits / total)
    boot_rates.sort()
    lo_idx = int((1 - ci) / 2 * n)
    hi_idx = int((1 - (1 - ci) / 2) * n) - 1
    return rate, boot_rates[lo_idx], boot_rates[hi_idx]


# ── Load P23-pinned snapshot (first 2788 lines) ──────────────────────────────
print(f"[P24] Loading P23-pinned snapshot (first {P23_PINNED_LINE_COUNT} lines)...")
all_records = []
with open("data/tsl_odds_history.jsonl") as f:
    for i, line in enumerate(f):
        if i >= P23_PINNED_LINE_COUNT:
            break
        line = line.strip()
        if line:
            all_records.append(json.loads(line))

print(f"[P24] Loaded {len(all_records)} records")

by_mid = defaultdict(list)
for r in all_records:
    by_mid[r["match_id"]].append(r)

# ── Derive valid CLV pairs (same rule as P22/P23) ────────────────────────────
MARKET_CODES = ["MNL", "HDC", "OU", "OE", "TTO"]
valid_pairs = []

for mid, records in by_mid.items():
    game_time_str = records[0].get("game_time")
    if not game_time_str:
        continue
    game_dt = to_utc(game_time_str)
    if not game_dt:
        continue
    pregame_recs = []
    closing_recs = []
    for r in records:
        fat = to_utc(r.get("fetched_at", ""))
        if fat is None:
            continue
        dh = (game_dt - fat).total_seconds() / 3600
        if dh >= PREGAME_MIN_HOURS:
            pregame_recs.append((fat, r))
        if abs(dh) <= CLOSING_WINDOW_HOURS:
            closing_recs.append((fat, r))
    best_pre = max(pregame_recs, key=lambda x: x[0]) if pregame_recs else None
    best_clo = max(closing_recs, key=lambda x: x[0]) if closing_recs else None
    if best_pre and best_clo and best_pre[1].get("markets") and best_clo[1].get("markets"):
        valid_pairs.append({"mid": mid, "pre": best_pre[1], "clo": best_clo[1]})

print(f"[P24] Valid pairs: {len(valid_pairs)}")

# ── Build per-market CLV observations ────────────────────────────────────────
market_clv: dict = defaultdict(list)
for pair in valid_pairs:
    for mc in MARKET_CODES:
        pre_odds = get_decimal_odds(pair["pre"], mc)
        clo_odds = get_decimal_odds(pair["clo"], mc)
        if pre_odds and clo_odds:
            clv_vals = compute_clv(pre_odds, clo_odds)
            market_clv[mc].extend(clv_vals)

all_clv = []
for v in market_clv.values():
    all_clv.extend(v)

print(f"[P24] Total CLV observations: {len(all_clv)}")
print(f"[P24] Per-market counts: { {k: len(v) for k, v in market_clv.items()} }")

# ── Overall diagnostics ──────────────────────────────────────────────────────
overall_n = len(all_clv)
overall_mean = sum(all_clv) / overall_n if overall_n else 0
overall_median = sorted(all_clv)[overall_n // 2] if overall_n else 0
overall_std = math.sqrt(sum((x - overall_mean) ** 2 for x in all_clv) / overall_n) if overall_n > 1 else 0
overall_min = min(all_clv) if all_clv else 0
overall_max = max(all_clv) if all_clv else 0
positive_count = sum(1 for x in all_clv if x > 0)
negative_count = sum(1 for x in all_clv if x < 0)
neutral_count = sum(1 for x in all_clv if x == 0)
positive_rate = positive_count / overall_n if overall_n else 0

# Bootstrap CI for mean
print("[P24] Running bootstrap CI for overall mean...")
mu, ci_lo, ci_hi = bootstrap_mean_ci(all_clv, n=BOOTSTRAP_N)

# Bootstrap CI for positive rate
print("[P24] Running bootstrap CI for positive rate...")
rate, rate_lo, rate_hi = bootstrap_rate_ci(positive_count, overall_n, n=BOOTSTRAP_N)

# Trimmed means
trim_5pct = trimmed_mean(all_clv, 0.05)
trim_10pct = trimmed_mean(all_clv, 0.10)

# ── Outlier sensitivity ──────────────────────────────────────────────────────
print("[P24] Running outlier sensitivity analysis...")
abs_clv = [(abs(x), x) for x in all_clv]
abs_clv_sorted = sorted(abs_clv, reverse=True)
n_top1 = max(1, int(len(all_clv) * 0.01))
n_top5 = max(1, int(len(all_clv) * 0.05))

top1_removed = [x for a, x in abs_clv_sorted[n_top1:]]
top5_removed = [x for a, x in abs_clv_sorted[n_top5:]]

mean_top1_removed = sum(top1_removed) / len(top1_removed) if top1_removed else 0
mean_top5_removed = sum(top5_removed) / len(top5_removed) if top5_removed else 0

# Winsorized (cap at 5th/95th percentile)
sorted_clv = sorted(all_clv)
p5 = sorted_clv[int(0.05 * len(sorted_clv))]
p95 = sorted_clv[int(0.95 * len(sorted_clv))]
winsorized = [max(p5, min(p95, x)) for x in all_clv]
mean_winsorized = sum(winsorized) / len(winsorized) if winsorized else 0

# Bootstrap CI for outlier-removed versions
_, ci_lo_top5, ci_hi_top5 = bootstrap_mean_ci(top5_removed, n=BOOTSTRAP_N)
_, ci_lo_win, ci_hi_win = bootstrap_mean_ci(winsorized, n=BOOTSTRAP_N)

# ── Per-market diagnostics ───────────────────────────────────────────────────
print("[P24] Per-market diagnostics...")
market_results = {}
for mc in MARKET_CODES:
    data = market_clv.get(mc, [])
    if not data:
        market_results[mc] = {"n": 0, "status": "NO_DATA"}
        continue
    n = len(data)
    mu_m = sum(data) / n
    std_m = math.sqrt(sum((x - mu_m) ** 2 for x in data) / n) if n > 1 else 0
    median_m = sorted(data)[n // 2]
    pos = sum(1 for x in data if x > 0)
    neg = sum(1 for x in data if x < 0)
    neu = sum(1 for x in data if x == 0)
    _, ci_lo_m, ci_hi_m = bootstrap_mean_ci(data, n=BOOTSTRAP_N)

    # Sign check: do a few outliers dominate?
    top5_abs = sorted([abs(x) for x in data], reverse=True)[:5]
    top5_sum = sum(top5_abs)
    total_abs = sum(abs(x) for x in data)
    top5_dominance_pct = (top5_sum / total_abs * 100) if total_abs > 0 else 0

    market_results[mc] = {
        "n": n,
        "mean_clv_pct": round(mu_m, 4),
        "median_clv_pct": round(median_m, 4),
        "std_clv_pct": round(std_m, 4),
        "min_clv_pct": round(min(data), 4),
        "max_clv_pct": round(max(data), 4),
        "positive_count": pos,
        "negative_count": neg,
        "neutral_count": neu,
        "positive_rate_pct": round(pos / n * 100, 2),
        "bootstrap_ci_95_lo": round(ci_lo_m, 4),
        "bootstrap_ci_95_hi": round(ci_hi_m, 4),
        "ci_crosses_zero": ci_lo_m < 0 < ci_hi_m,
        "top5_outlier_dominance_pct": round(top5_dominance_pct, 2),
        "status": "OK"
    }

# ── Sign sanity check ────────────────────────────────────────────────────────
# Check: are results driven by few extreme outliers?
sorted_abs = sorted(all_clv, key=abs, reverse=True)
top1pct_vals = sorted_abs[:n_top1]
top5pct_vals = sorted_abs[:n_top5]
sum_top1 = sum(top1pct_vals)
sum_top5 = sum(top5pct_vals)
sum_all = sum(all_clv)
contribution_top1 = (sum_top1 / sum_all * 100) if sum_all != 0 else float("inf")
contribution_top5 = (sum_top5 / sum_all * 100) if sum_all != 0 else float("inf")

# ── CLV classification ───────────────────────────────────────────────────────
ci_crosses_zero = ci_lo < 0 < ci_hi
sign_stable = mean_top5_removed > 0 and mean_winsorized > 0 and mu > 0
ci_positive = ci_lo > 0

if ci_positive and sign_stable:
    clv_classification = "ROBUST"
elif not ci_crosses_zero and mu > 0 and (mean_top5_removed > 0 or mean_winsorized > 0):
    clv_classification = "WEAK_STABLE"
elif ci_crosses_zero:
    clv_classification = "INCONCLUSIVE"
elif mu < 0 and mean_top5_removed < 0:
    clv_classification = "NEGATIVE"
else:
    clv_classification = "INCONCLUSIVE"

# Overall: mean is tiny (+0.23%), CI crosses zero, so:
# Given median=0.0 and very high neutral rate, this is likely INCONCLUSIVE

print(f"\n[P24] Overall mean CLV: {round(mu, 4)}%")
print(f"[P24] 95% Bootstrap CI: [{round(ci_lo, 4)}, {round(ci_hi, 4)}]")
print(f"[P24] CI crosses zero: {ci_crosses_zero}")
print(f"[P24] Trimmed mean (5%): {round(trim_5pct, 4)}%")
print(f"[P24] Mean after top-5% outlier removal: {round(mean_top5_removed, 4)}%")
print(f"[P24] Mean winsorized: {round(mean_winsorized, 4)}%")
print(f"[P24] Classification: {clv_classification}")

# ── Output results dict ──────────────────────────────────────────────────────
results = {
    "source_pinned": {
        "line_count": P23_PINNED_LINE_COUNT,
        "sha256": P23_PINNED_SHA256
    },
    "valid_pairs": len(valid_pairs),
    "total_observations": len(all_clv),
    "market_counts": {k: len(v) for k, v in market_clv.items()},
    "overall": {
        "n": overall_n,
        "mean_clv_pct": round(mu, 4),
        "median_clv_pct": round(overall_median, 4),
        "std_clv_pct": round(overall_std, 4),
        "min_clv_pct": round(overall_min, 4),
        "max_clv_pct": round(overall_max, 4),
        "positive_count": positive_count,
        "negative_count": negative_count,
        "neutral_count": neutral_count,
        "positive_rate_pct": round(positive_rate * 100, 2),
        "bootstrap_ci_95": {
            "lo": round(ci_lo, 4),
            "hi": round(ci_hi, 4),
            "crosses_zero": ci_crosses_zero
        },
        "bootstrap_rate_ci_95": {
            "rate": round(rate * 100, 2),
            "lo": round(rate_lo * 100, 2),
            "hi": round(rate_hi * 100, 2)
        },
        "trimmed_mean_5pct": round(trim_5pct, 4),
        "trimmed_mean_10pct": round(trim_10pct, 4)
    },
    "outlier_sensitivity": {
        "top1pct_removed_n": n_top1,
        "mean_after_top1_removed": round(mean_top1_removed, 4),
        "top5pct_removed_n": n_top5,
        "mean_after_top5_removed": round(mean_top5_removed, 4),
        "bootstrap_ci_95_top5_removed": {"lo": round(ci_lo_top5, 4), "hi": round(ci_hi_top5, 4)},
        "winsorize_bounds": {"p5": round(p5, 4), "p95": round(p95, 4)},
        "mean_winsorized": round(mean_winsorized, 4),
        "bootstrap_ci_95_winsorized": {"lo": round(ci_lo_win, 4), "hi": round(ci_hi_win, 4)},
        "top5_outlier_contribution_pct": round(contribution_top5, 2),
        "top1_outlier_contribution_pct": round(contribution_top1, 2)
    },
    "sign_sanity": {
        "overall_mean_positive": mu > 0,
        "top5_removed_mean_positive": mean_top5_removed > 0,
        "winsorized_mean_positive": mean_winsorized > 0,
        "outlier_dominated": abs(contribution_top1) > 200 or abs(contribution_top5) > 300
    },
    "per_market": market_results,
    "clv_classification": clv_classification,
}

# Print JSON
print("\n--- RESULTS JSON ---")
print(json.dumps(results, indent=2))
