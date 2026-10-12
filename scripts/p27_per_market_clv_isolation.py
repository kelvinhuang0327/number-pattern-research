"""
P27 — Per-Market Clean CLV Isolation & OE Exclusion Study
paper_only=true / diagnostic_only=true

Uses P23/P26-pinned snapshot (first 2788 lines).
Applies P26 line-aware matching from wbc_backend/clv/outcome_matching.py.
Produces per-market CLV isolation and OE exclusion analysis.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dateutil.parser import parse as dtparse
from wbc_backend.clv.outcome_matching import MatchStatus, match_outcomes_for_market

# ── Config ────────────────────────────────────────────────────────────────────
DATE = "2026-05-20"
P23_PINNED_LINE_COUNT = 2788
P23_PINNED_SHA256 = "ac1320de7efa23e645ffb81f27c9825634c3d63566ed8ccf5c62ee6cf7c94118"
PREGAME_MIN_HOURS = 2.0
CLOSING_WINDOW_HOURS = 2.0
BOOTSTRAP_N = 5000
MARKET_CODES = ["MNL", "HDC", "OU", "OE", "TTO"]
SAMPLE_SUFFICIENT_N = 50

random.seed(42)

os.makedirs("data/paper_recommendations", exist_ok=True)
os.makedirs("report", exist_ok=True)
os.makedirs("00-BettingPlan/20260520", exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

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


def trimmed_mean(data: list[float], pct: float) -> float | None:
    if not data:
        return None
    s = sorted(data)
    k = int(len(s) * pct)
    trimmed = s[k: len(s) - k] if k > 0 else s
    return sum(trimmed) / len(trimmed) if trimmed else None


def bootstrap_mean_ci(data: list[float], n: int = 5000, ci: float = 0.95):
    if not data:
        return None, None, None
    mu = sum(data) / len(data)
    nd = len(data)
    boot = []
    for _ in range(n):
        sample = [random.choice(data) for _ in range(nd)]
        boot.append(sum(sample) / nd)
    boot.sort()
    lo = int((1 - ci) / 2 * n)
    hi = int((1 - (1 - ci) / 2) * n) - 1
    return mu, boot[lo], boot[hi]


def bootstrap_rate_ci(pos: int, total: int, n: int = 5000, ci: float = 0.95):
    if total == 0:
        return None, None, None
    rate = pos / total
    boot = []
    for _ in range(n):
        hits = sum(1 for _ in range(total) if random.random() < rate)
        boot.append(hits / total)
    boot.sort()
    lo = int((1 - ci) / 2 * n)
    hi = int((1 - (1 - ci) / 2) * n) - 1
    return rate, boot[lo], boot[hi]


def full_summary(vals: list[float], unique_matches: int, skipped: dict) -> dict:
    if not vals:
        return {
            "n": 0, "unique_match_count": unique_matches,
            "skipped_count": sum(skipped.values()),
            "skipped_reason_breakdown": skipped,
        }
    n = len(vals)
    sv = sorted(vals)
    mu = sum(vals) / n
    std = math.sqrt(sum((x - mu) ** 2 for x in vals) / n)
    pos = sum(1 for x in vals if x > 0.001)
    neg = sum(1 for x in vals if x < -0.001)
    gt10 = sum(1 for x in vals if abs(x) > 10)
    gt25 = sum(1 for x in vals if abs(x) > 25)
    gt50 = sum(1 for x in vals if abs(x) > 50)
    n_top1 = max(1, int(n * 0.01))
    top1_sum = sum(sorted(vals, key=abs, reverse=True)[:n_top1])

    mu_b, ci_lo, ci_hi = bootstrap_mean_ci(vals, n=BOOTSTRAP_N)
    rate, rate_lo, rate_hi = bootstrap_rate_ci(pos, n, n=BOOTSTRAP_N)
    tm5 = trimmed_mean(vals, 0.05)
    tm10 = trimmed_mean(vals, 0.10)

    return {
        "n": n,
        "unique_match_count": unique_matches,
        "skipped_count": sum(skipped.values()),
        "skipped_reason_breakdown": skipped,
        "mean_clv_pct": round(mu, 4),
        "median_clv_pct": round(sv[n // 2], 4),
        "std_clv_pct": round(std, 4),
        "trimmed_mean_5pct": round(tm5, 4) if tm5 is not None else None,
        "trimmed_mean_10pct": round(tm10, 4) if tm10 is not None else None,
        "min_clv_pct": round(min(vals), 4),
        "max_clv_pct": round(max(vals), 4),
        "positive_count": pos,
        "negative_count": neg,
        "positive_rate_pct": round(pos / n * 100, 2),
        "abs_gt_10_count": gt10,
        "abs_gt_25_count": gt25,
        "abs_gt_50_count": gt50,
        "top_1pct_n": n_top1,
        "top_1pct_sum": round(top1_sum, 4),
        "bootstrap_mean": round(mu_b, 4) if mu_b is not None else None,
        "bootstrap_ci_lo_95": round(ci_lo, 4) if ci_lo is not None else None,
        "bootstrap_ci_hi_95": round(ci_hi, 4) if ci_hi is not None else None,
        "ci_crosses_zero": (ci_lo is not None and ci_lo < 0 < ci_hi),
        "positive_rate_ci_lo_95": round(rate_lo, 4) if rate_lo is not None else None,
        "positive_rate_ci_hi_95": round(rate_hi, 4) if rate_hi is not None else None,
    }


def classify_market(s: dict) -> str:
    n = s.get("n", 0)
    if n < SAMPLE_SUFFICIENT_N:
        return "MARKET_SAMPLE_LIMITED"
    ci_lo = s.get("bootstrap_ci_lo_95")
    ci_hi = s.get("bootstrap_ci_hi_95")
    mean = s.get("mean_clv_pct", 0)
    if ci_lo is None:
        return "MARKET_CLEAN_INCONCLUSIVE"
    if ci_lo > 0:
        return "MARKET_CLEAN_ROBUST"
    if ci_hi < 0:
        return "MARKET_CLEAN_NEGATIVE"
    # CI crosses zero
    if mean > 0.5 and s.get("trimmed_mean_5pct", 0) > 0.3:
        return "MARKET_CLEAN_WEAK_STABLE"
    return "MARKET_CLEAN_INCONCLUSIVE"


def aggregate_summary(vals: list[float], unique_matches: int) -> dict:
    return full_summary(vals, unique_matches, {})


# ── Step 1: Snapshot drift record ─────────────────────────────────────────────
print("[P27] Checking source snapshot drift...")
current_sha = hashlib.sha256(open("data/tsl_odds_history.jsonl", "rb").read()).hexdigest()
current_lines = sum(1 for _ in open("data/tsl_odds_history.jsonl"))
drift = current_sha != P23_PINNED_SHA256 or current_lines != P23_PINNED_LINE_COUNT
print(f"  P23/P26 pinned: lines={P23_PINNED_LINE_COUNT}, sha={P23_PINNED_SHA256[:16]}...")
print(f"  Current:        lines={current_lines}, sha={current_sha[:16]}...")
print(f"  Drift: {drift} (+{current_lines - P23_PINNED_LINE_COUNT} records)")

DRIFT_META = {
    "artifact": "P27_SOURCE_SNAPSHOT_DRIFT",
    "phase": "P27_PER_MARKET_CLV_ISOLATION",
    "date": DATE,
    "paper_only": True,
    "diagnostic_only": True,
    "production_proposal": False,
    "profitability_claim": False,
    "champion_replacement_allowed": False,
    "promotion_allowed": False,
    "live_api_call": False,
    "crawler_modified": False,
    "p23_pinned_lines": P23_PINNED_LINE_COUNT,
    "p23_pinned_sha256": P23_PINNED_SHA256,
    "current_lines": current_lines,
    "current_sha256": current_sha,
    "drift_detected": drift,
    "drift_records": current_lines - P23_PINNED_LINE_COUNT,
    "action": "RECORDED_ONLY_NOT_OVERWRITTEN",
    "p27_uses_pinned_baseline": True,
    "generated_at": datetime.now(timezone.utc).isoformat(),
}
with open("data/paper_recommendations/p27_source_snapshot_drift_20260520.json", "w") as f:
    json.dump(DRIFT_META, f, indent=2)

# ── Step 2: Load P23-pinned snapshot ──────────────────────────────────────────
print(f"[P27] Loading P23-pinned snapshot (first {P23_PINNED_LINE_COUNT} lines)...")
records: list[dict] = []
with open("data/tsl_odds_history.jsonl") as f:
    for i, line in enumerate(f):
        if i >= P23_PINNED_LINE_COUNT:
            break
        line = line.strip()
        if line:
            records.append(json.loads(line))
print(f"  Loaded {len(records)} records")

by_mid: dict = defaultdict(list)
for r in records:
    by_mid[r["match_id"]].append(r)

# ── Step 3: Derive valid CLV pairs ────────────────────────────────────────────
print("[P27] Deriving valid CLV pairs...")
valid_pairs: list[dict] = []
for mid, recs in by_mid.items():
    gt_str = recs[0].get("game_time")
    if not gt_str:
        continue
    gt = to_utc(gt_str)
    if not gt:
        continue
    pre_recs, clo_recs = [], []
    for r in recs:
        fat = to_utc(r.get("fetched_at", ""))
        if fat is None:
            continue
        dh = (gt - fat).total_seconds() / 3600
        if dh >= PREGAME_MIN_HOURS:
            pre_recs.append((fat, r))
        if abs(dh) <= CLOSING_WINDOW_HOURS:
            clo_recs.append((fat, r))
    bp = max(pre_recs, key=lambda x: x[0]) if pre_recs else None
    bc = max(clo_recs, key=lambda x: x[0]) if clo_recs else None
    if bp and bc and bp[1].get("markets") and bc[1].get("markets"):
        valid_pairs.append({"mid": mid, "pre": bp[1], "clo": bc[1], "game_time": gt_str})

print(f"  Valid pairs: {len(valid_pairs)}")

# ── Step 4: Per-market CLV with P26 line-aware matching ───────────────────────
print("[P27] Computing per-market clean CLV...")

# market_clv[mc] = list of clv_pct values
market_clv: dict[str, list[float]] = defaultdict(list)
# market_mid_matched[mc] = set of match_ids that contributed ≥1 MATCHED outcome
market_mids: dict[str, set] = defaultdict(set)
# per-market skip counters
market_skips: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

for pair in valid_pairs:
    pre_mkts = {m["marketCode"]: m for m in pair["pre"].get("markets", []) if "marketCode" in m}
    clo_mkts = {m["marketCode"]: m for m in pair["clo"].get("markets", []) if "marketCode" in m}
    common = set(pre_mkts) & set(clo_mkts) & set(MARKET_CODES)
    for mc in common:
        pre_oc = pre_mkts[mc].get("outcomes", [])
        clo_oc = clo_mkts[mc].get("outcomes", [])
        results = match_outcomes_for_market(mc, pre_oc, clo_oc)
        has_match = False
        for r in results:
            if r.is_valid_clv:
                market_clv[mc].append(r.clv_pct)
                has_match = True
            else:
                market_skips[mc][r.status.value] += 1
        if has_match:
            market_mids[mc].add(pair["mid"])

for mc in MARKET_CODES:
    print(f"  {mc}: n={len(market_clv[mc])}, unique_matches={len(market_mids[mc])}, skips={dict(market_skips[mc])}")

# ── Step 5: Per-market summaries ──────────────────────────────────────────────
print("[P27] Computing per-market summaries & classifications...")
per_market: dict[str, dict] = {}
for mc in MARKET_CODES:
    vals = market_clv[mc]
    s = full_summary(vals, len(market_mids[mc]), dict(market_skips[mc]))
    s["market_code"] = mc
    s["classification"] = classify_market(s)
    per_market[mc] = s
    print(f"  {mc}: mean={s.get('mean_clv_pct')}%, CI=[{s.get('bootstrap_ci_lo_95')},{s.get('bootstrap_ci_hi_95')}], class={s['classification']}")

# ── Step 6: OE Exclusion Study aggregates ─────────────────────────────────────
print("[P27] Computing OE exclusion study...")

def agg_vals(codes: list[str]) -> tuple[list[float], set]:
    vals, mids = [], set()
    for mc in codes:
        vals.extend(market_clv.get(mc, []))
        mids |= market_mids.get(mc, set())
    return vals, mids


aggregates_def = {
    "all_markets":       MARKET_CODES,
    "exclude_oe":        ["MNL", "HDC", "OU", "TTO"],
    "mnl_hdc_ou_tto":    ["MNL", "HDC", "OU", "TTO"],
    "mnl_only":          ["MNL"],
    "hdc_only":          ["HDC"],
    "ou_only":           ["OU"],
    "oe_only":           ["OE"],
    "tto_only":          ["TTO"],
    "hdc_ou":            ["HDC", "OU"],
    "hdc_ou_tto":        ["HDC", "OU", "TTO"],
}

oe_study: dict[str, dict] = {}
for label, codes in aggregates_def.items():
    vals, mids = agg_vals(codes)
    s = full_summary(vals, len(mids), {})
    s["markets_included"] = codes
    s["classification"] = classify_market(s)
    oe_study[label] = s

oe_vals_all = market_clv.get("OE", [])
non_oe_vals = [v for mc in ["MNL", "HDC", "OU", "TTO"] for v in market_clv.get(mc, [])]

oe_mean = sum(oe_vals_all) / len(oe_vals_all) if oe_vals_all else None
oe_std = math.sqrt(sum((x - oe_mean) ** 2 for x in oe_vals_all) / len(oe_vals_all)) if oe_vals_all and oe_mean is not None else None

oe_dilution_analysis = {
    "oe_n": len(oe_vals_all),
    "oe_mean_clv_pct": round(oe_mean, 4) if oe_mean is not None else None,
    "oe_std_clv_pct": round(oe_std, 4) if oe_std is not None else None,
    "oe_positive_rate_pct": round(sum(1 for x in oe_vals_all if x > 0) / len(oe_vals_all) * 100, 2) if oe_vals_all else None,
    "non_oe_n": len(non_oe_vals),
    "non_oe_mean_clv_pct": round(sum(non_oe_vals) / len(non_oe_vals), 4) if non_oe_vals else None,
    "all_mean_clv_pct": oe_study["all_markets"].get("mean_clv_pct"),
    "exclude_oe_mean_clv_pct": oe_study["exclude_oe"].get("mean_clv_pct"),
    "oe_ci_crosses_zero": oe_study["oe_only"].get("ci_crosses_zero"),
    "exclude_oe_ci_crosses_zero": oe_study["exclude_oe"].get("ci_crosses_zero"),
    "exclude_oe_ci": [
        oe_study["exclude_oe"].get("bootstrap_ci_lo_95"),
        oe_study["exclude_oe"].get("bootstrap_ci_hi_95"),
    ],
    "is_oe_diluting": (
        oe_mean is not None and
        abs(oe_mean) < abs(oe_study["exclude_oe"].get("mean_clv_pct") or 0)
    ),
}

# OE investigation: does exclusion recover signal?
excl_ci_lo = oe_study["exclude_oe"].get("bootstrap_ci_lo_95")
excl_ci_hi = oe_study["exclude_oe"].get("bootstrap_ci_hi_95")
oe_dilution_analysis["signal_recovery_after_oe_exclusion"] = (
    "NO_RECOVERY" if (excl_ci_lo is not None and excl_ci_lo < 0) else "PARTIAL_RECOVERY"
)

# Answer the three required questions
oe_dilution_analysis["q1_oe_only_diluting"] = (
    "YES" if oe_dilution_analysis.get("is_oe_diluting") else "NO"
)
oe_dilution_analysis["q2_exclude_oe_ci_still_crosses_zero"] = (
    "YES" if oe_study["exclude_oe"].get("ci_crosses_zero") else "NO"
)
best_market_mean = max(
    (oe_study[f"{mc.lower()}_only"].get("mean_clv_pct") or 0)
    for mc in ["MNL", "HDC", "OU", "TTO"]
)
oe_dilution_analysis["q3_any_market_worth_model_repair"] = (
    "YES_WEAK" if best_market_mean > 0.2 else "NO_INCONCLUSIVE"
)

print(f"  OE dilution: {oe_dilution_analysis['q1_oe_only_diluting']}")
print(f"  Excl-OE CI crosses zero: {oe_dilution_analysis['q2_exclude_oe_ci_still_crosses_zero']}")
print(f"  Signal recovery: {oe_dilution_analysis['signal_recovery_after_oe_exclusion']}")

# ── Step 7: Market Readiness Decision ─────────────────────────────────────────
print("[P27] Computing market readiness decision...")

all_classifications = {mc: per_market[mc]["classification"] for mc in MARKET_CODES}
any_robust = any(c == "MARKET_CLEAN_ROBUST" for c in all_classifications.values())
any_weak_stable = any(c == "MARKET_CLEAN_WEAK_STABLE" for c in all_classifications.values())
any_sample_limited = any(c == "MARKET_SAMPLE_LIMITED" for c in all_classifications.values())
any_mapping_risk = any(c == "MARKET_MAPPING_RISK_REMAINING" for c in all_classifications.values())
all_inconclusive = all(c in ("MARKET_CLEAN_INCONCLUSIVE", "MARKET_CLEAN_NEGATIVE") for c in all_classifications.values())

# Overall final classification
if any_mapping_risk:
    final_class = "P27_MARKET_MAPPING_REPAIR_REQUIRED"
elif any_robust:
    final_class = "P27_MARKET_CLEAN_ROBUST"
elif any_sample_limited and not any_weak_stable:
    final_class = "P27_MARKET_SAMPLE_LIMITED"
elif any_weak_stable:
    final_class = "P27_MARKET_WEAK_STABLE_DIAGNOSTIC_ONLY"
else:
    final_class = "P27_ALL_MARKETS_CLEAN_CLV_INCONCLUSIVE"

# OE exclusion sub-classification
oe_final_class = (
    "P27_OE_EXCLUSION_NO_SIGNAL_RECOVERY"
    if oe_study["exclude_oe"].get("ci_crosses_zero")
    else "P27_OE_EXCLUSION_PARTIAL_SIGNAL_RECOVERY"
)

print(f"  Final classification: {final_class}")
print(f"  OE exclusion result: {oe_final_class}")

# ── Step 8: Common metadata ────────────────────────────────────────────────────
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
    "source_snapshot_drift_detected": drift,
    "current_snapshot_lines": current_lines,
    "drift_action": "RECORDED_ONLY_NOT_OVERWRITTEN",
    "generated_at": now_iso,
    "date": DATE,
}

# ── Step 9: Write artifacts ────────────────────────────────────────────────────

# A1: Per-market clean CLV isolation
a1 = {
    **COMMON_META,
    "artifact": "P27_PER_MARKET_CLEAN_CLV_ISOLATION",
    "phase": "P27_PER_MARKET_CLV_ISOLATION",
    "valid_pairs": len(valid_pairs),
    "market_codes": MARKET_CODES,
    "sample_sufficient_threshold": SAMPLE_SUFFICIENT_N,
    "matching_module": "wbc_backend/clv/outcome_matching.py",
    "per_market_results": per_market,
    "market_classifications": all_classifications,
    "any_robust": any_robust,
    "any_weak_stable": any_weak_stable,
    "any_sample_limited": any_sample_limited,
    "final_classification": final_class,
}
with open("data/paper_recommendations/p27_per_market_clean_clv_isolation_20260520.json", "w") as f:
    json.dump(a1, f, indent=2, ensure_ascii=False)
print("[P27] A1 written: per_market_clean_clv_isolation")

# A2: OE exclusion study
a2 = {
    **COMMON_META,
    "artifact": "P27_OE_EXCLUSION_STUDY",
    "valid_pairs": len(valid_pairs),
    "oe_dilution_analysis": oe_dilution_analysis,
    "aggregates": oe_study,
    "oe_final_classification": oe_final_class,
    "final_classification": final_class,
}
with open("data/paper_recommendations/p27_oe_exclusion_study_20260520.json", "w") as f:
    json.dump(a2, f, indent=2, ensure_ascii=False)
print("[P27] A2 written: oe_exclusion_study")

# A3: Market readiness decision
a3 = {
    **COMMON_META,
    "artifact": "P27_MARKET_READINESS_DECISION",
    "market_classifications": all_classifications,
    "any_robust": any_robust,
    "any_weak_stable": any_weak_stable,
    "any_sample_limited": any_sample_limited,
    "all_inconclusive": all_inconclusive,
    "oe_exclusion_result": oe_final_class,
    "per_market_ci": {
        mc: {
            "ci_lo": per_market[mc].get("bootstrap_ci_lo_95"),
            "ci_hi": per_market[mc].get("bootstrap_ci_hi_95"),
            "ci_crosses_zero": per_market[mc].get("ci_crosses_zero"),
            "mean": per_market[mc].get("mean_clv_pct"),
            "n": per_market[mc].get("n"),
        }
        for mc in MARKET_CODES
    },
    "next_round_recommendation": (
        "model_quality_repair_and_data_accumulation"
        if final_class == "P27_ALL_MARKETS_CLEAN_CLV_INCONCLUSIVE"
        else "focused_market_investigation"
    ),
    "champion": "fixed_edge_5pct",
    "champion_status": "PRESERVED",
    "promotion_frozen": True,
    "final_classification": final_class,
}
with open("data/paper_recommendations/p27_market_readiness_decision_20260520.json", "w") as f:
    json.dump(a3, f, indent=2, ensure_ascii=False)
print("[P27] A3 written: market_readiness_decision")

# ── Print summary ─────────────────────────────────────────────────────────────
print()
print("=" * 65)
print("P27 RESULTS SUMMARY")
print("=" * 65)
print(f"Source drift: {drift} (pinned=2788, current={current_lines})")
print(f"Valid pairs : {len(valid_pairs)}")
print()
print("Per-Market Clean CLV:")
print(f"{'Market':<8} {'N':>5} {'Mean%':>8} {'Median%':>8} {'CI_lo':>8} {'CI_hi':>8} {'CI∋0':>6} {'Class'}")
print("-" * 75)
for mc in MARKET_CODES:
    s = per_market[mc]
    ci_lo = s.get("bootstrap_ci_lo_95", "N/A")
    ci_hi = s.get("bootstrap_ci_hi_95", "N/A")
    crosses = s.get("ci_crosses_zero", "—")
    print(f"{mc:<8} {s.get('n',0):>5} {s.get('mean_clv_pct',0):>8.4f} "
          f"{s.get('median_clv_pct',0):>8.4f} {str(ci_lo):>8} {str(ci_hi):>8} "
          f"{'Yes' if crosses else 'No':>6}  {s['classification']}")
print()
print("OE Exclusion Study:")
for label in ["all_markets", "exclude_oe", "hdc_ou_tto", "hdc_only", "ou_only", "tto_only"]:
    s = oe_study[label]
    ci_lo = s.get("bootstrap_ci_lo_95")
    ci_hi = s.get("bootstrap_ci_hi_95")
    crosses = s.get("ci_crosses_zero")
    print(f"  {label:<20}: n={s.get('n',0):>4}, mean={s.get('mean_clv_pct',0):>7.4f}%, "
          f"CI=[{ci_lo},{ci_hi}], CI∋0={'Yes' if crosses else 'No'}")
print()
print(f"OE dilution q1 (OE diluting):          {oe_dilution_analysis['q1_oe_only_diluting']}")
print(f"OE exclusion q2 (CI still crosses 0):  {oe_dilution_analysis['q2_exclude_oe_ci_still_crosses_zero']}")
print(f"Best market worth model repair:         {oe_dilution_analysis['q3_any_market_worth_model_repair']}")
print()
print(f"Final classification : {final_class}")
print(f"OE excl. sub-class   : {oe_final_class}")
print()
print("Artifacts written:")
for f in [
    "data/paper_recommendations/p27_per_market_clean_clv_isolation_20260520.json",
    "data/paper_recommendations/p27_oe_exclusion_study_20260520.json",
    "data/paper_recommendations/p27_market_readiness_decision_20260520.json",
    "data/paper_recommendations/p27_source_snapshot_drift_20260520.json",
]:
    print(f"  {f}")
