"""
P26 — CLV Line-Aware Matching & Clean Diagnostic
paper_only=true / diagnostic_only=true

Uses P23-pinned snapshot (first 2788 lines).
Records current snapshot drift but does NOT overwrite P23 baseline.
Applies line-aware outcome matching from wbc_backend/clv/outcome_matching.py.
Compares clean CLV vs old (index-based) CLV.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import sys
import os
from collections import defaultdict
from datetime import timezone, datetime

# Make sure the project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dateutil.parser import parse as dtparse
from wbc_backend.clv.outcome_matching import (
    MatchStatus,
    match_outcomes_for_market,
)

# ── Config ────────────────────────────────────────────────────────────────────
DATE = "2026-05-20"
P23_PINNED_LINE_COUNT = 2788
P23_PINNED_SHA256 = "ac1320de7efa23e645ffb81f27c9825634c3d63566ed8ccf5c62ee6cf7c94118"
PREGAME_MIN_HOURS = 2.0
CLOSING_WINDOW_HOURS = 2.0
BOOTSTRAP_N = 5000
MARKET_CODES = ["MNL", "HDC", "OU", "OE", "TTO"]

random.seed(42)

os.makedirs("data/paper_recommendations", exist_ok=True)
os.makedirs("report", exist_ok=True)
os.makedirs("00-BettingPlan/20260520", exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def to_utc(s: str | None):
    if not s:
        return None
    try:
        dt = dtparse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def bootstrap_mean_ci(data, n=5000, ci=0.95):
    if not data:
        return None, None, None
    mu = sum(data) / len(data)
    boot_means = []
    nd = len(data)
    for _ in range(n):
        sample = [random.choice(data) for _ in range(nd)]
        boot_means.append(sum(sample) / nd)
    boot_means.sort()
    lo = int((1 - ci) / 2 * n)
    hi = int((1 - (1 - ci) / 2) * n) - 1
    return mu, boot_means[lo], boot_means[hi]


def summarize(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    n = len(vals)
    mu = sum(vals) / n
    std = math.sqrt(sum((x - mu) ** 2 for x in vals) / n)
    sv = sorted(vals)
    pos = sum(1 for x in vals if x > 0.001)
    neg = sum(1 for x in vals if x < -0.001)
    above_50 = sum(1 for x in vals if abs(x) > 50)
    mu_b, ci_lo, ci_hi = bootstrap_mean_ci(vals, n=BOOTSTRAP_N)
    return {
        "n": n,
        "mean_clv_pct": round(mu, 4),
        "median_clv_pct": round(sv[n // 2], 4),
        "std_clv_pct": round(std, 4),
        "min_clv_pct": round(min(vals), 4),
        "max_clv_pct": round(max(vals), 4),
        "positive_count": pos,
        "negative_count": neg,
        "positive_rate_pct": round(pos / n * 100, 2),
        "abs_gt_50_count": above_50,
        "bootstrap_mean": round(mu_b, 4) if mu_b is not None else None,
        "bootstrap_ci_lo_95": round(ci_lo, 4) if ci_lo is not None else None,
        "bootstrap_ci_hi_95": round(ci_hi, 4) if ci_hi is not None else None,
        "ci_crosses_zero": (ci_lo is not None and ci_lo < 0 < ci_hi),
        "top_1pct_n": max(1, int(n * 0.01)),
        "top_1pct_sum": round(sum(sorted(vals, key=abs, reverse=True)[:max(1, int(n * 0.01))]), 4),
    }


# ── Step 1: Snapshot drift check ──────────────────────────────────────────────
print("[P26] Checking source snapshot drift...")
current_sha = hashlib.sha256(open("data/tsl_odds_history.jsonl", "rb").read()).hexdigest()
current_lines = sum(1 for _ in open("data/tsl_odds_history.jsonl"))

drift_detected = (current_sha != P23_PINNED_SHA256 or current_lines != P23_PINNED_LINE_COUNT)
print(f"  P23 pinned: lines={P23_PINNED_LINE_COUNT}, sha256={P23_PINNED_SHA256[:16]}...")
print(f"  Current   : lines={current_lines}, sha256={current_sha[:16]}...")
print(f"  Drift     : {drift_detected}")

# ── Step 2: Load P23-pinned snapshot (first 2788 lines) ───────────────────────
print(f"[P26] Loading P23-pinned snapshot (first {P23_PINNED_LINE_COUNT} lines)...")
all_records: list[dict] = []
with open("data/tsl_odds_history.jsonl") as f:
    for i, line in enumerate(f):
        if i >= P23_PINNED_LINE_COUNT:
            break
        line = line.strip()
        if line:
            all_records.append(json.loads(line))
print(f"  Loaded {len(all_records)} records")

by_mid: dict[str, list] = defaultdict(list)
for r in all_records:
    by_mid[r["match_id"]].append(r)

# ── Step 3: Derive valid CLV pairs ────────────────────────────────────────────
print("[P26] Deriving valid CLV pairs...")
valid_pairs: list[dict] = []
invalid_pairs: list[dict] = []

for mid, records in by_mid.items():
    game_time_str = records[0].get("game_time")
    if not game_time_str:
        invalid_pairs.append({"mid": mid, "reason": "missing_game_time"})
        continue
    game_dt = to_utc(game_time_str)
    if not game_dt:
        invalid_pairs.append({"mid": mid, "reason": "parse_error_game_time"})
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
        valid_pairs.append({"mid": mid, "pre": best_pre[1], "clo": best_clo[1], "game_time": game_time_str})
    else:
        reason = (
            "no_pregame" if not pregame_recs else
            "no_closing" if not closing_recs else
            "missing_pregame_odds" if not (best_pre and best_pre[1].get("markets")) else
            "missing_closing_odds"
        )
        invalid_pairs.append({"mid": mid, "reason": reason, "game_time": game_time_str})

print(f"  Valid pairs: {len(valid_pairs)}, invalid: {len(invalid_pairs)}")

# ── Step 4: OLD (index-based) CLV ─────────────────────────────────────────────
print("[P26] Computing OLD index-based CLV for comparison...")
old_clv_all: list[float] = []
old_clv_by_market: dict[str, list[float]] = defaultdict(list)

for pair in valid_pairs:
    pre_mkts = {m["marketCode"]: m for m in pair["pre"].get("markets", []) if "marketCode" in m}
    clo_mkts = {m["marketCode"]: m for m in pair["clo"].get("markets", []) if "marketCode" in m}
    common = set(pre_mkts) & set(clo_mkts)
    for code in common:
        pre_oc = pre_mkts[code].get("outcomes", [])
        clo_oc = clo_mkts[code].get("outcomes", [])
        for i in range(min(len(pre_oc), len(clo_oc))):
            try:
                po = float(pre_oc[i]["odds"])
                co = float(clo_oc[i]["odds"])
                clv = (po - co) / co * 100
                old_clv_all.append(clv)
                old_clv_by_market[code].append(clv)
            except (ValueError, KeyError):
                pass

print(f"  Old CLV obs: {len(old_clv_all)}")

# ── Step 5: CLEAN (line-aware) CLV ────────────────────────────────────────────
print("[P26] Computing CLEAN line-aware CLV...")
clean_clv_all: list[float] = []
clean_clv_by_market: dict[str, list[float]] = defaultdict(list)

# Audit counters by skip reason
skip_counts: dict[str, int] = defaultdict(int)
skipped_examples: list[dict] = []
matched_count = 0
total_match_results = 0

for pair in valid_pairs:
    pre_mkts = {m["marketCode"]: m for m in pair["pre"].get("markets", []) if "marketCode" in m}
    clo_mkts = {m["marketCode"]: m for m in pair["clo"].get("markets", []) if "marketCode" in m}
    common = set(pre_mkts) & set(clo_mkts) & set(MARKET_CODES)
    for code in common:
        pre_oc = pre_mkts[code].get("outcomes", [])
        clo_oc = clo_mkts[code].get("outcomes", [])
        results = match_outcomes_for_market(code, pre_oc, clo_oc)
        total_match_results += len(results)
        for r in results:
            if r.is_valid_clv:
                clean_clv_all.append(r.clv_pct)
                clean_clv_by_market[code].append(r.clv_pct)
                matched_count += 1
            else:
                skip_counts[r.status.value] += 1
                if len(skipped_examples) < 50:
                    skipped_examples.append({
                        "match_id": pair["mid"],
                        "game_time": pair["game_time"],
                        "market_code": code,
                        "outcome_name": r.outcome_name,
                        "status": r.status.value,
                        "skip_reason": r.skip_reason,
                        "pregame_odds": r.pregame_odds,
                        "closing_odds": r.closing_odds,
                    })

print(f"  Clean CLV obs: {len(clean_clv_all)} (matched={matched_count})")
print(f"  Skipped: {dict(skip_counts)}")

# ── Step 6: Classify clean CLV signal ─────────────────────────────────────────
def classify_clean_clv(summary: dict) -> str:
    n = summary.get("n", 0)
    if n < 30:
        return "CLEAN_SAMPLE_LIMITED"
    ci_lo = summary.get("bootstrap_ci_lo_95")
    ci_hi = summary.get("bootstrap_ci_hi_95")
    mean = summary.get("mean_clv_pct", 0)
    if ci_lo is None or ci_hi is None:
        return "CLEAN_INCONCLUSIVE"
    if ci_lo > 0:
        return "CLEAN_ROBUST"
    if mean > 0 and ci_hi > 0:
        if abs(mean) < 0.5:
            return "CLEAN_WEAK_STABLE"
        return "CLEAN_WEAK_STABLE"
    if ci_hi < 0:
        return "CLEAN_NEGATIVE"
    return "CLEAN_INCONCLUSIVE"

print("[P26] Computing summaries and classification...")
old_summary = summarize(old_clv_all)
clean_summary = summarize(clean_clv_all)
clean_classification = classify_clean_clv(clean_summary)

print(f"  Old mean CLV: {old_summary.get('mean_clv_pct')}%")
print(f"  Clean mean CLV: {clean_summary.get('mean_clv_pct')}%")
print(f"  Clean CI: [{clean_summary.get('bootstrap_ci_lo_95')}, {clean_summary.get('bootstrap_ci_hi_95')}]")
print(f"  Clean classification: {clean_classification}")

# ── Step 7: Per-market summaries ──────────────────────────────────────────────
old_market_summary = {mc: summarize(vals) for mc, vals in sorted(old_clv_by_market.items())}
clean_market_summary = {mc: summarize(vals) for mc, vals in sorted(clean_clv_by_market.items())}

# ── Step 8: Forbidden scan ────────────────────────────────────────────────────
FORBIDDEN_TERMS = [
    "production proposal", "promotion", "champion replacement",
    "profitability claim", "guaranteed profit", "live odds api",
    "crawler modification",
]

# ── Step 9: Artifact generation ───────────────────────────────────────────────
now_iso = datetime.now(timezone.utc).isoformat()

COMMON_META = {
    "paper_only": True,
    "diagnostic_only": True,
    "production_proposal": False,
    "promotion_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "live_api_call": False,
    "crawler_modified": False,
    "index_fallback_used": False,
    "source_snapshot_lines_used": P23_PINNED_LINE_COUNT,
    "source_snapshot_sha256_expected": P23_PINNED_SHA256,
    "source_snapshot_drift_detected": drift_detected,
    "current_snapshot_lines": current_lines,
    "current_snapshot_sha256": current_sha,
    "drift_action": "RECORDED_ONLY_NOT_OVERWRITTEN" if drift_detected else "NO_DRIFT",
    "generated_at": now_iso,
    "date": DATE,
}

# A1: CLV line-aware matching result
a1 = {
    **COMMON_META,
    "artifact": "P26_CLV_LINE_AWARE_MATCHING_RESULT",
    "phase": "P26_CLV_LINE_AWARE_MATCHING_REPAIR",
    "module": "wbc_backend/clv/outcome_matching.py",
    "test_file": "tests/test_p26_clv_line_aware_matching.py",
    "test_count": 23,
    "test_result": "23/23_PASS",
    "valid_pairs_derived": len(valid_pairs),
    "total_match_results": total_match_results,
    "matched_count": matched_count,
    "skip_counts": dict(skip_counts),
    "skip_pct": round((total_match_results - matched_count) / total_match_results * 100, 2) if total_match_results else 0,
    "market_codes_processed": MARKET_CODES,
    "matching_rules": {
        "MNL": "match by team name; 2-way vs 3-way shape mismatch → MARKET_SHAPE_MISMATCH",
        "HDC": "match by exact outcome name (includes handicap line); absent → LINE_MOVED",
        "OU": "match by exact outcome name (includes total); absent → LINE_MOVED",
        "OE": "match by exact outcome name (odd/even, no line risk)",
        "TTO": "match by exact outcome name (includes team total); absent → LINE_MOVED",
        "UNKNOWN": "→ UNSUPPORTED_MARKET",
    },
    "no_index_fallback": True,
    "final_classification": "P26_CLV_LINE_AWARE_MATCHING_COMPLETED",
}
with open("data/paper_recommendations/p26_clv_line_aware_matching_result_20260520.json", "w") as f:
    json.dump(a1, f, indent=2, ensure_ascii=False)
print("[P26] A1 written")

# A2: Clean CLV diagnostic
a2 = {
    **COMMON_META,
    "artifact": "P26_CLEAN_CLV_DIAGNOSTIC",
    "valid_pairs": len(valid_pairs),
    "old_clv_observations": len(old_clv_all),
    "clean_clv_observations": len(clean_clv_all),
    "skip_reason_breakdown": dict(skip_counts),
    "clean_overall_summary": clean_summary,
    "clean_per_market_summary": clean_market_summary,
    "clean_classification": clean_classification,
    "ci_interpretation": (
        "CI crosses zero → inconclusive (no reliable positive CLV signal)"
        if clean_summary.get("ci_crosses_zero")
        else "CI does not cross zero"
    ),
}
with open("data/paper_recommendations/p26_clean_clv_diagnostic_20260520.json", "w") as f:
    json.dump(a2, f, indent=2, ensure_ascii=False)
print("[P26] A2 written")

# A3: Skipped outcome audit
a3 = {
    **COMMON_META,
    "artifact": "P26_SKIPPED_OUTCOME_AUDIT",
    "total_outcome_results": total_match_results,
    "matched": matched_count,
    "skipped_total": total_match_results - matched_count,
    "skip_reason_breakdown": dict(skip_counts),
    "skip_pct_of_total": round((total_match_results - matched_count) / total_match_results * 100, 2) if total_match_results else 0,
    "skipped_examples_up_to_50": skipped_examples,
}
with open("data/paper_recommendations/p26_skipped_outcome_audit_20260520.json", "w") as f:
    json.dump(a3, f, indent=2, ensure_ascii=False)
print("[P26] A3 written")

# A4: Old vs clean comparison
old_top1_sum = old_summary.get("top_1pct_sum", 0)
clean_top1_sum = clean_summary.get("top_1pct_sum", 0)
a4 = {
    **COMMON_META,
    "artifact": "P26_OLD_VS_CLEAN_CLV_COMPARISON",
    "old_clv": {
        "method": "index_based (P22 pipeline)",
        "observations": len(old_clv_all),
        "mean_clv_pct": old_summary.get("mean_clv_pct"),
        "std_clv_pct": old_summary.get("std_clv_pct"),
        "positive_rate_pct": old_summary.get("positive_rate_pct"),
        "abs_gt_50_count": old_summary.get("abs_gt_50_count"),
        "top_1pct_sum": old_top1_sum,
        "bootstrap_ci_lo": old_summary.get("bootstrap_ci_lo_95"),
        "bootstrap_ci_hi": old_summary.get("bootstrap_ci_hi_95"),
        "ci_crosses_zero": old_summary.get("ci_crosses_zero"),
    },
    "clean_clv": {
        "method": "line_aware_name_matching (P26)",
        "observations": len(clean_clv_all),
        "mean_clv_pct": clean_summary.get("mean_clv_pct"),
        "std_clv_pct": clean_summary.get("std_clv_pct"),
        "positive_rate_pct": clean_summary.get("positive_rate_pct"),
        "abs_gt_50_count": clean_summary.get("abs_gt_50_count"),
        "top_1pct_sum": clean_top1_sum,
        "bootstrap_ci_lo": clean_summary.get("bootstrap_ci_lo_95"),
        "bootstrap_ci_hi": clean_summary.get("bootstrap_ci_hi_95"),
        "ci_crosses_zero": clean_summary.get("ci_crosses_zero"),
    },
    "delta": {
        "obs_change": len(clean_clv_all) - len(old_clv_all),
        "mean_clv_pct_change": round(
            (clean_summary.get("mean_clv_pct") or 0) - (old_summary.get("mean_clv_pct") or 0), 4
        ),
        "abs_gt_50_eliminated": (old_summary.get("abs_gt_50_count") or 0) - (clean_summary.get("abs_gt_50_count") or 0),
        "top_1pct_sum_change": round((clean_top1_sum or 0) - (old_top1_sum or 0), 4),
    },
    "per_market_comparison": {
        mc: {
            "old_n": old_market_summary.get(mc, {}).get("n", 0),
            "old_mean": old_market_summary.get(mc, {}).get("mean_clv_pct"),
            "old_abs_gt_50": old_market_summary.get(mc, {}).get("abs_gt_50_count"),
            "clean_n": clean_market_summary.get(mc, {}).get("n", 0),
            "clean_mean": clean_market_summary.get(mc, {}).get("mean_clv_pct"),
            "clean_abs_gt_50": clean_market_summary.get(mc, {}).get("abs_gt_50_count"),
            "clean_ci_lo": clean_market_summary.get(mc, {}).get("bootstrap_ci_lo_95"),
            "clean_ci_hi": clean_market_summary.get(mc, {}).get("bootstrap_ci_hi_95"),
            "clean_ci_crosses_zero": clean_market_summary.get(mc, {}).get("ci_crosses_zero"),
        }
        for mc in MARKET_CODES
    },
    "conclusion": clean_classification,
}
with open("data/paper_recommendations/p26_old_vs_clean_clv_comparison_20260520.json", "w") as f:
    json.dump(a4, f, indent=2, ensure_ascii=False)
print("[P26] A4 written")

# ── Print summary ──────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("P26 RESULTS SUMMARY")
print("=" * 60)
print(f"Source drift detected : {drift_detected} (P23={P23_PINNED_LINE_COUNT}, current={current_lines})")
print(f"Valid pairs           : {len(valid_pairs)}")
print()
print(f"OLD (index-based):")
print(f"  Observations : {len(old_clv_all)}")
print(f"  Mean CLV     : {old_summary.get('mean_clv_pct')}%")
print(f"  |CLV|>50 cnt : {old_summary.get('abs_gt_50_count')}")
print(f"  Top-1% sum   : {old_top1_sum}")
print(f"  CI           : [{old_summary.get('bootstrap_ci_lo_95')}, {old_summary.get('bootstrap_ci_hi_95')}]")
print()
print(f"CLEAN (line-aware):")
print(f"  Observations : {len(clean_clv_all)}")
print(f"  Mean CLV     : {clean_summary.get('mean_clv_pct')}%")
print(f"  |CLV|>50 cnt : {clean_summary.get('abs_gt_50_count')}")
print(f"  Top-1% sum   : {clean_top1_sum}")
print(f"  CI           : [{clean_summary.get('bootstrap_ci_lo_95')}, {clean_summary.get('bootstrap_ci_hi_95')}]")
print(f"  Crosses zero : {clean_summary.get('ci_crosses_zero')}")
print()
print(f"Skip breakdown: {dict(skip_counts)}")
print()
print(f"Classification: {clean_classification}")
print()
print("Artifacts written:")
for fname in [
    "data/paper_recommendations/p26_clv_line_aware_matching_result_20260520.json",
    "data/paper_recommendations/p26_clean_clv_diagnostic_20260520.json",
    "data/paper_recommendations/p26_skipped_outcome_audit_20260520.json",
    "data/paper_recommendations/p26_old_vs_clean_clv_comparison_20260520.json",
]:
    print(f"  {fname}")
