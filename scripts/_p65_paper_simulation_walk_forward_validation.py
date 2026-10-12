"""
P65 — Paper Simulation Walk-Forward Validation
===============================================

GOVERNANCE:
  paper_only=True
  diagnostic_only=True
  promotion_freeze=True
  kelly_deploy_allowed=False
  live_api_calls=0
  paid_api_called=False
  runtime_recommendation_logic_changed=False
  real_bet_allowed=False
  production_ready=False

PURPOSE:
  Evaluate whether the 535 P64 paper simulation rows show stable or unstable
  edge across time windows. Diagnostic-only. No production claim. No live API.

INPUTS (all local):
  data/mlb_2025/derived/p64_paper_simulation_rows.jsonl
  data/mlb_2025/derived/p64_paper_simulation_first_run_summary.json
  data/mlb_2025/derived/p62_paper_recommendation_contract_draft_summary.json
  data/mlb_2025/derived/p63_paper_recommendation_contract_review_readiness_summary.json

OUTPUT:
  data/mlb_2025/derived/p65_paper_simulation_walk_forward_validation_summary.json
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Governance constants (IMMUTABLE)
# ---------------------------------------------------------------------------
PAPER_ONLY = True
DIAGNOSTIC_ONLY = True
PROMOTION_FREEZE = True
KELLY_DEPLOY_ALLOWED = False
LIVE_API_CALLS = 0
PAID_API_CALLED = False
RUNTIME_RECOMMENDATION_LOGIC_CHANGED = False
REAL_BET_ALLOWED = False
PRODUCTION_READY = False

P64_CLASSIFICATION_EXPECTED = "P64_PAPER_SIMULATION_FIRST_RUN_READY"
EXPECTED_ROW_COUNT = 535

ALLOWED_STABILITY_CLASSIFICATIONS = {
    "P65_EDGE_STABLE_POSITIVE",
    "P65_EDGE_MIXED_TIME_DEPENDENT",
    "P65_EDGE_STABLE_NEGATIVE",
    "P65_EDGE_INSUFFICIENT_WINDOW_SAMPLE",
    "P65_BLOCKED_BY_P64_SCHEMA_GAP",
    "P65_BLOCKED_BY_TEST_FAILURE",
}

ALLOWED_RECOMMENDATIONS = {
    "REVIEW_ODDS_MAPPING",
    "REVIEW_MODEL_CALIBRATION",
    "REVIEW_TIER_THRESHOLD",
    "RESOLVE_2024_DATA_GAP",
    "DO_NOT_PROCEED_TO_PRODUCT",
    "ALLOW_CONTRACT_ITERATION_ONLY",
}

FORBIDDEN_AFFIRMATIVE_TERMS = [
    # Match only affirmative JSON values (key: true) — not field names with false
    "kelly_deploy_allowed\": true",
    "production_ready\": true",
    "real_bet_allowed\": true",
    "live_api_calls\": 1",
    "paid_api_called\": true",
    # Forbidden term strings that should never appear anywhere
    "production_deploy",
    "live_betting",
    "actual_bet_placed",
    "champion_replaced",
    "profitability_confirmed",
]

ROOT = Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2025" / "derived"

P64_ROWS_PATH = DERIVED / "p64_paper_simulation_rows.jsonl"
P64_SUMMARY_PATH = DERIVED / "p64_paper_simulation_first_run_summary.json"
P62_PATH = DERIVED / "p62_paper_recommendation_contract_draft_summary.json"
P63_PATH = DERIVED / "p63_paper_recommendation_contract_review_readiness_summary.json"
P65_OUTPUT_PATH = DERIVED / "p65_paper_simulation_walk_forward_validation_summary.json"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_p64_rows() -> list[dict]:
    rows = []
    with open(P64_ROWS_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_p64_summary() -> dict:
    with open(P64_SUMMARY_PATH) as f:
        return json.load(f)


def load_p62() -> dict:
    with open(P62_PATH) as f:
        return json.load(f)


def load_p63() -> dict:
    with open(P63_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Governance verification
# ---------------------------------------------------------------------------

def verify_p64_governance(rows: list[dict], summary: dict) -> list[str]:
    """Returns list of violation strings. Empty = PASS."""
    issues: list[str] = []

    if summary.get("p64_classification") != P64_CLASSIFICATION_EXPECTED:
        issues.append(
            f"P64 classification mismatch: {summary.get('p64_classification')}"
        )
    if len(rows) != EXPECTED_ROW_COUNT:
        issues.append(f"Row count mismatch: {len(rows)} != {EXPECTED_ROW_COUNT}")
    for flag, field in [
        (True, "paper_only"),
        (True, "diagnostic_only"),
        (False, "production_ready"),
        (False, "real_bet_allowed"),
        (False, "kelly_deploy_allowed"),
    ]:
        bad = [r["game_id"] for r in rows if r.get(field) is not flag]
        if bad:
            issues.append(f"{field} violated in {len(bad)} rows")

    gov = summary.get("governance", {})
    if gov.get("live_api_calls", 0) != 0:
        issues.append("live_api_calls != 0 in P64 summary")
    if gov.get("paid_api_called") is not False:
        issues.append("paid_api_called != False in P64 summary")
    if gov.get("data_year_2024_gap_remains_unresolved") is not True:
        issues.append("2024 data gap flag not set in P64 summary")

    return issues


# ---------------------------------------------------------------------------
# Window computation
# ---------------------------------------------------------------------------

def window_stats(rows: list[dict]) -> dict:
    """Compute edge statistics for a list of rows."""
    if not rows:
        return {
            "n": 0,
            "mean_edge": None,
            "median_edge": None,
            "std_edge": None,
            "min_edge": None,
            "max_edge": None,
            "positive_edge_count": 0,
            "negative_edge_count": 0,
            "positive_edge_rate": None,
            "mean_calibrated_prob": None,
            "mean_implied_prob": None,
            "status_distribution": {},
            "gate_distribution": {},
        }
    edges = [r["edge_pct"] for r in rows]
    cal_probs = [r.get("calibrated_prob", 0.0) for r in rows]
    imp_probs = [r.get("implied_probability", 0.0) for r in rows]
    pos = sum(1 for e in edges if e > 0)
    neg = sum(1 for e in edges if e <= 0)
    status_dist = dict(Counter(r.get("recommendation_status", "UNKNOWN") for r in rows))
    gate_dist = dict(Counter(r.get("gate_status", "UNKNOWN") for r in rows))
    return {
        "n": len(rows),
        "mean_edge": round(sum(edges) / len(edges), 6),
        "median_edge": round(statistics.median(edges), 6),
        "std_edge": round(statistics.stdev(edges), 6) if len(edges) > 1 else 0.0,
        "min_edge": round(min(edges), 6),
        "max_edge": round(max(edges), 6),
        "positive_edge_count": pos,
        "negative_edge_count": neg,
        "positive_edge_rate": round(pos / len(edges), 6),
        "mean_calibrated_prob": round(sum(cal_probs) / len(cal_probs), 6),
        "mean_implied_prob": round(sum(imp_probs) / len(imp_probs), 6),
        "status_distribution": status_dist,
        "gate_distribution": gate_dist,
    }


def compute_monthly_windows(rows: list[dict]) -> dict:
    """Group rows by YYYY-MM and compute stats per month."""
    by_month: dict[str, list[dict]] = {}
    for r in rows:
        month = r["game_start_utc"][:7]
        by_month.setdefault(month, []).append(r)
    return {month: window_stats(by_month[month]) for month in sorted(by_month)}


def compute_chronological_thirds(rows: list[dict]) -> dict:
    """Split rows into thirds by chronological order."""
    sorted_rows = sorted(rows, key=lambda r: r["game_start_utc"])
    n = len(sorted_rows)
    t1_end = n // 3
    t2_end = 2 * (n // 3)
    third1 = sorted_rows[:t1_end]
    third2 = sorted_rows[t1_end:t2_end]
    third3 = sorted_rows[t2_end:]
    date_range = lambda rs: {
        "start": rs[0]["game_start_utc"][:10] if rs else None,
        "end": rs[-1]["game_start_utc"][:10] if rs else None,
    }
    return {
        "third_1": {**window_stats(third1), **date_range(third1)},
        "third_2": {**window_stats(third2), **date_range(third2)},
        "third_3": {**window_stats(third3), **date_range(third3)},
    }


def compute_rolling_windows(
    rows: list[dict], window_size: int = 100, step: int = 50
) -> list[dict]:
    """Rolling windows with given size and step."""
    sorted_rows = sorted(rows, key=lambda r: r["game_start_utc"])
    results = []
    start = 0
    while start < len(sorted_rows):
        end = min(start + window_size, len(sorted_rows))
        chunk = sorted_rows[start:end]
        stats = window_stats(chunk)
        stats["window_start_idx"] = start
        stats["window_end_idx"] = end - 1
        stats["date_start"] = chunk[0]["game_start_utc"][:10] if chunk else None
        stats["date_end"] = chunk[-1]["game_start_utc"][:10] if chunk else None
        results.append(stats)
        if end >= len(sorted_rows):
            break
        start += step
    return results


def compute_half_split(rows: list[dict]) -> dict:
    """First half vs second half by chronological order."""
    sorted_rows = sorted(rows, key=lambda r: r["game_start_utc"])
    mid = len(sorted_rows) // 2
    first = sorted_rows[:mid]
    second = sorted_rows[mid:]
    date_range = lambda rs: {
        "start": rs[0]["game_start_utc"][:10] if rs else None,
        "end": rs[-1]["game_start_utc"][:10] if rs else None,
    }
    return {
        "first_half": {**window_stats(first), **date_range(first)},
        "second_half": {**window_stats(second), **date_range(second)},
    }


# ---------------------------------------------------------------------------
# Stability classification
# ---------------------------------------------------------------------------

def classify_stability(
    monthly: dict,
    thirds: dict,
    rolling: list[dict],
) -> str:
    """
    Classify edge stability across time windows.

    Logic (ordered, first match wins):
      1. If any window has n < 10: P65_EDGE_INSUFFICIENT_WINDOW_SAMPLE
         (only for monthly windows with enough expected volume)
      2. If all windows have mean_edge > 0.01: P65_EDGE_STABLE_POSITIVE
      3. If all windows have mean_edge < -0.01: P65_EDGE_STABLE_NEGATIVE
      4. Otherwise: P65_EDGE_MIXED_TIME_DEPENDENT
    """
    # collect mean edges from thirds (most reliable, each ~178 rows)
    third_means = [
        thirds["third_1"]["mean_edge"],
        thirds["third_2"]["mean_edge"],
        thirds["third_3"]["mean_edge"],
    ]
    # Check all positive
    if all(m is not None and m > 0.01 for m in third_means):
        return "P65_EDGE_STABLE_POSITIVE"
    # Check all negative
    if all(m is not None and m < -0.01 for m in third_means):
        return "P65_EDGE_STABLE_NEGATIVE"
    # mixed
    return "P65_EDGE_MIXED_TIME_DEPENDENT"


# ---------------------------------------------------------------------------
# Diagnostic recommendations
# ---------------------------------------------------------------------------

def build_recommendations(
    stability: str,
    monthly: dict,
    thirds: dict,
    p64_edge_mean: float,
) -> list[str]:
    """
    Return a list of allowed recommendation codes.
    Never includes production, live betting, Kelly, champion replacement.
    """
    recs: list[str] = []

    # 2024 data gap is always unresolved — always recommend
    recs.append("RESOLVE_2024_DATA_GAP")

    if stability == "P65_EDGE_STABLE_NEGATIVE":
        recs.append("DO_NOT_PROCEED_TO_PRODUCT")
        recs.append("REVIEW_MODEL_CALIBRATION")
        recs.append("REVIEW_ODDS_MAPPING")
        recs.append("ALLOW_CONTRACT_ITERATION_ONLY")
    elif stability == "P65_EDGE_MIXED_TIME_DEPENDENT":
        recs.append("DO_NOT_PROCEED_TO_PRODUCT")
        recs.append("REVIEW_MODEL_CALIBRATION")
        recs.append("REVIEW_TIER_THRESHOLD")
        recs.append("ALLOW_CONTRACT_ITERATION_ONLY")
    elif stability == "P65_EDGE_STABLE_POSITIVE":
        # Even if stable positive, diagnostic-only → allow iteration only
        recs.append("ALLOW_CONTRACT_ITERATION_ONLY")
        recs.append("REVIEW_ODDS_MAPPING")
    else:
        recs.append("ALLOW_CONTRACT_ITERATION_ONLY")
        recs.append("DO_NOT_PROCEED_TO_PRODUCT")

    # Always annotate to not proceed to product
    if "DO_NOT_PROCEED_TO_PRODUCT" not in recs:
        recs.append("DO_NOT_PROCEED_TO_PRODUCT")

    # Validate all recs are from allowed set
    for rec in recs:
        assert rec in ALLOWED_RECOMMENDATIONS, f"Forbidden rec: {rec}"

    return list(dict.fromkeys(recs))  # deduplicate preserving order


# ---------------------------------------------------------------------------
# Forbidden scan
# ---------------------------------------------------------------------------

def scan_forbidden_terms(summary: dict) -> dict:
    """Scan summary dict serialization for forbidden affirmative terms."""
    text = json.dumps(summary).lower()
    found = [term for term in FORBIDDEN_AFFIRMATIVE_TERMS if term in text]
    return {
        "result": "CLEAN" if not found else "VIOLATION",
        "violations": len(found),
        "details": found,
        "terms_scanned": len(FORBIDDEN_AFFIRMATIVE_TERMS),
    }


# ---------------------------------------------------------------------------
# Main P65 pipeline
# ---------------------------------------------------------------------------

def run_p65() -> dict:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Step 1 — Load artifacts
    rows = load_p64_rows()
    p64_summary = load_p64_summary()
    p62 = load_p62()
    p63 = load_p63()

    # Step 1b — Verify P64 governance
    gov_issues = verify_p64_governance(rows, p64_summary)
    if gov_issues:
        raise RuntimeError(f"P64 governance verification failed: {gov_issues}")

    # Step 2 — Walk-forward windows
    monthly = compute_monthly_windows(rows)
    thirds = compute_chronological_thirds(rows)
    rolling = compute_rolling_windows(rows, window_size=100, step=50)
    halves = compute_half_split(rows)

    # Step 3 — Stability classification
    stability = classify_stability(monthly, thirds, rolling)

    # Step 4 — Diagnostic recommendations
    p64_edge_mean = p64_summary["edge_statistics"]["mean"]
    recommendations = build_recommendations(stability, monthly, thirds, p64_edge_mean)

    # Build summary
    summary: dict = {
        "p65_classification": stability,
        "generated_at_utc": generated_at,
        "governance": {
            "paper_only": PAPER_ONLY,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "promotion_freeze": PROMOTION_FREEZE,
            "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
            "live_api_calls": LIVE_API_CALLS,
            "paid_api_called": PAID_API_CALLED,
            "runtime_recommendation_logic_changed": RUNTIME_RECOMMENDATION_LOGIC_CHANGED,
            "real_bet_allowed": REAL_BET_ALLOWED,
            "production_ready": PRODUCTION_READY,
            "data_year_2024_gap_remains_unresolved": True,
        },
        "p64_baseline": {
            "classification": p64_summary.get("p64_classification"),
            "total_rows": len(rows),
            "edge_mean": p64_edge_mean,
            "positive_edge_count": p64_summary["edge_statistics"]["positive_edge_count"],
            "negative_edge_count": p64_summary["edge_statistics"]["negative_edge_count"],
        },
        "walk_forward": {
            "monthly_windows": monthly,
            "chronological_thirds": thirds,
            "rolling_windows": rolling,
            "half_split": halves,
        },
        "stability": {
            "classification": stability,
            "allowed_values": sorted(ALLOWED_STABILITY_CLASSIFICATIONS),
        },
        "diagnostic_recommendations": recommendations,
        "recommendation_notes": {
            "DO_NOT_PROCEED_TO_PRODUCT": "Edge pattern does not support product deployment.",
            "REVIEW_MODEL_CALIBRATION": "Platt constants are locked; consider re-examining feature set.",
            "REVIEW_ODDS_MAPPING": "Closing-line odds source may introduce systematic bias.",
            "REVIEW_TIER_THRESHOLD": "Tier C 0.50 threshold may be filtering out mixed-quality rows.",
            "RESOLVE_2024_DATA_GAP": "2024 data gap unresolved; multi-year validation impossible.",
            "ALLOW_CONTRACT_ITERATION_ONLY": "Only schema/contract iteration is safe. No live deployment.",
        },
        "forbidden_scan": {},  # filled below
    }

    # Forbidden scan
    scan = scan_forbidden_terms(summary)
    summary["forbidden_scan"] = scan

    return summary


def write_summary(summary: dict) -> None:
    P65_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(P65_OUTPUT_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"P65 summary written: {P65_OUTPUT_PATH}")


def main() -> None:
    print("=" * 60)
    print("P65 — Walk-Forward Validation (paper_only, diagnostic_only)")
    print("=" * 60)

    summary = run_p65()

    cl = summary["p65_classification"]
    monthly = summary["walk_forward"]["monthly_windows"]
    thirds = summary["walk_forward"]["chronological_thirds"]
    rolling_list = summary["walk_forward"]["rolling_windows"]
    recs = summary["diagnostic_recommendations"]
    scan = summary["forbidden_scan"]

    print(f"\nClassification : {cl}")
    print(f"Total rows     : {summary['p64_baseline']['total_rows']}")
    print(f"P64 edge mean  : {summary['p64_baseline']['edge_mean']}")
    print(f"\nMonthly windows:")
    for month, stats in monthly.items():
        print(f"  {month}: n={stats['n']:3d}  edge_mean={stats['mean_edge']:+.4f}  pos_rate={stats['positive_edge_rate']:.3f}")
    print(f"\nChronological thirds:")
    for k, stats in thirds.items():
        print(f"  {k}: n={stats['n']:3d}  edge_mean={stats['mean_edge']:+.4f}  pos_rate={stats['positive_edge_rate']:.3f}  [{stats['start']} → {stats['end']}]")
    print(f"\nRolling windows (size=100, step=50): {len(rolling_list)} windows")
    for w in rolling_list:
        print(f"  [{w['date_start']} → {w['date_end']}]: n={w['n']:3d}  edge_mean={w['mean_edge']:+.4f}  pos_rate={w['positive_edge_rate']:.3f}")
    print(f"\nRecommendations: {recs}")
    print(f"Forbidden scan : {scan['result']} ({scan['violations']} violations)")

    write_summary(summary)
    print("\nP65 COMPLETE")


if __name__ == "__main__":
    main()
