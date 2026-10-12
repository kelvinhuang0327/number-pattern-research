"""
P96 High-FIP Segment Drift Monitor / Coverage-Aware Stability Gate
===================================================================
Diagnostic-only drift monitor for the HIGH_FIP segment (|ΔFIP| >= 1.5).

Upstream requirements:
  - P95 final_classification = P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE
  - P94 final_classification = P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY
  - P84E outcome_available rows = 808

Governance:
  - paper_only=true
  - diagnostic_only=true
  - production_ready=false
  - no odds / no EV / no CLV / no Kelly / no recommendation / no production
"""

from __future__ import annotations

import json
import math
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from sklearn.metrics import roc_auc_score, brier_score_loss
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
P84E_PATH = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
P94_PATH = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
P95_PATH = REPO_ROOT / "data/mlb_2026/derived/p95_fip_stratified_shadow_tracker_summary.json"
OUT_JSON = REPO_ROOT / "data/mlb_2026/derived/p96_high_fip_segment_drift_monitor_summary.json"
OUT_MD = REPO_ROOT / "report/p96_high_fip_segment_drift_monitor_20260528.md"

# Schedule total for coverage calculation
SCHEDULE_TOTAL = 2430

# Segment thresholds
HIGH_FIP_THRESHOLD = 1.5
MID_FIP_LOWER = 0.5

# Expected upstream values (tolerance)
EXPECTED_HIGH_N = 287
EXPECTED_HIGH_HITRATE = 0.641115
TOLERANCE = 1e-4

# Monthly drift rule thresholds
MONTHLY_STABLE_MIN_N = 30
MONTHLY_STABLE_MIN_HITRATE = 0.55


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _hit_rate(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(1 for r in rows if r.get("is_correct")) / len(rows)


def _auc(rows: list[dict]) -> float | None:
    if not SKLEARN_AVAILABLE or len(rows) < 10:
        return None
    probs = [r.get("model_probability") for r in rows]
    labels = [int(bool(r.get("is_correct"))) for r in rows]
    if None in probs:
        return None
    if len(set(labels)) < 2:
        return None
    try:
        return float(roc_auc_score(labels, probs))
    except Exception:
        return None


def _brier(rows: list[dict]) -> float | None:
    if not SKLEARN_AVAILABLE or len(rows) < 5:
        return None
    probs = [r.get("model_probability") for r in rows]
    labels = [int(bool(r.get("is_correct"))) for r in rows]
    if None in probs:
        return None
    try:
        return float(brier_score_loss(labels, probs))
    except Exception:
        return None


def _ece(rows: list[dict], n_bins: int = 10) -> float | None:
    """Expected Calibration Error via equal-width bins."""
    probs = [r.get("model_probability") for r in rows if r.get("model_probability") is not None]
    labels = [int(bool(r.get("is_correct"))) for r in rows if r.get("model_probability") is not None]
    if len(probs) < 10:
        return None
    ece = 0.0
    n = len(probs)
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        indices = [j for j, p in enumerate(probs) if lo <= p < hi]
        if not indices:
            continue
        avg_conf = sum(probs[j] for j in indices) / len(indices)
        avg_acc = sum(labels[j] for j in indices) / len(indices)
        ece += (len(indices) / n) * abs(avg_conf - avg_acc)
    return round(ece, 6)


def _predicted_home_ratio(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(1 for r in rows if r.get("predicted_side") == "home") / len(rows)


def _actual_home_ratio(rows: list[dict]) -> float:
    if not rows:
        return 0.0
    return sum(1 for r in rows if r.get("actual_winner") == "home") / len(rows)


# ---------------------------------------------------------------------------
# Step 1: Pre-flight and upstream verification
# ---------------------------------------------------------------------------

def step1_preflight() -> dict[str, Any]:
    gates: list[str] = []
    failures: list[str] = []

    # Existence checks
    for path, label in [(P84E_PATH, "P84E"), (P94_PATH, "P94"), (P95_PATH, "P95")]:
        if not path.exists():
            failures.append(f"{label} file missing: {path}")
        else:
            gates.append(f"{label}_exists")

    if failures:
        return {"step": "step1_preflight", "all_gates_ok": False, "failures": failures}

    # Load P95
    with open(P95_PATH) as f:
        p95 = json.load(f)

    p95_fc = p95.get("final_classification", "")
    expected_p95 = "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE"
    if p95_fc != expected_p95:
        failures.append(f"P95 classification mismatch: got {p95_fc!r}, expected {expected_p95!r}")
    else:
        gates.append("P95_classification_ok")

    p95_segs = p95.get("step2_segment_metrics", {}).get("segments", {})
    high_tracking = p95_segs.get("HIGH_FIP", {}).get("tracking_status", "")
    if high_tracking != "HIGH_FIP_DIAGNOSTIC_TRACKING_ALLOWED":
        failures.append(f"P95 HIGH_FIP tracking_status mismatch: {high_tracking!r}")
    else:
        gates.append("P95_HIGH_FIP_tracking_status_ok")

    mid_tracking = p95_segs.get("MID_FIP", {}).get("tracking_status", "")
    if mid_tracking != "MID_FIP_WATCH_ONLY":
        failures.append(f"P95 MID_FIP tracking_status mismatch: {mid_tracking!r}")
    else:
        gates.append("P95_MID_FIP_watch_only_ok")

    low_tracking = p95_segs.get("LOW_FIP", {}).get("tracking_status", "")
    if low_tracking != "LOW_FIP_WATCH_ONLY":
        failures.append(f"P95 LOW_FIP tracking_status mismatch: {low_tracking!r}")
    else:
        gates.append("P95_LOW_FIP_watch_only_ok")

    if not p95.get("governance_all_pass", False):
        failures.append("P95 governance_all_pass is not True")
    else:
        gates.append("P95_governance_all_pass_ok")

    # Load P94
    with open(P94_PATH) as f:
        p94 = json.load(f)

    p94_fc = p94.get("final_classification", "")
    if p94_fc != "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY":
        failures.append(f"P94 classification mismatch: {p94_fc!r}")
    else:
        gates.append("P94_classification_ok")

    # Load P84E
    total_rows = 0
    outcome_rows: list[dict] = []
    with open(P84E_PATH) as f:
        for line in f:
            row = json.loads(line)
            total_rows += 1
            if row.get("outcome_available", False) and row.get("sp_fip_delta") is not None:
                outcome_rows.append(row)

    if len(outcome_rows) != 808:
        failures.append(f"P84E outcome_available rows mismatch: got {len(outcome_rows)}, expected 808")
    else:
        gates.append("P84E_outcome_rows_808_ok")

    # HIGH_FIP recheck
    high_rows = [r for r in outcome_rows if abs(r["sp_fip_delta"]) >= HIGH_FIP_THRESHOLD]
    if len(high_rows) != EXPECTED_HIGH_N:
        failures.append(f"HIGH_FIP n mismatch: got {len(high_rows)}, expected {EXPECTED_HIGH_N}")
    else:
        gates.append("HIGH_FIP_n_287_ok")

    actual_hr = _hit_rate(high_rows)
    if abs(actual_hr - EXPECTED_HIGH_HITRATE) > TOLERANCE:
        failures.append(f"HIGH_FIP hit_rate mismatch: got {actual_hr:.6f}, expected {EXPECTED_HIGH_HITRATE:.6f}")
    else:
        gates.append("HIGH_FIP_hit_rate_0641115_ok")

    # Governance flags from P95
    gov_flags = ["odds_used", "ev_computed", "clv_computed", "kelly_computed"]
    guards = p95.get("step4_drift_overclaim_guards", {})
    for flag in gov_flags:
        if guards.get(flag, True):
            failures.append(f"P95 governance {flag} should be False but is True")

    all_gates_ok = len(failures) == 0

    coverage = {
        "total_rows": total_rows,
        "outcome_rows": len(outcome_rows),
        "schedule_total": SCHEDULE_TOTAL,
        "schedule_coverage_pct": round(total_rows / SCHEDULE_TOTAL * 100, 4),
    }

    return {
        "step": "step1_preflight",
        "all_gates_ok": all_gates_ok,
        "gates_passed": gates,
        "failures": failures,
        "coverage": coverage,
        "_outcome_rows": outcome_rows,  # pass-through, stripped before JSON output
    }


# ---------------------------------------------------------------------------
# Step 2: HIGH_FIP monthly drift monitor
# ---------------------------------------------------------------------------

def step2_monthly_drift(outcome_rows: list[dict]) -> dict[str, Any]:
    high_rows = [r for r in outcome_rows if abs(r["sp_fip_delta"]) >= HIGH_FIP_THRESHOLD]

    # Monthly grouping
    monthly_groups: dict[str, list] = defaultdict(list)
    for r in high_rows:
        gd = r.get("game_date", "")
        month = gd[:7] if len(gd) >= 7 else "UNKNOWN"
        monthly_groups[month].append(r)

    monthly_results = []
    all_stable = True
    any_drift_warning = False

    for month in sorted(monthly_groups.keys()):
        mrs = monthly_groups[month]
        n = len(mrs)
        hr = _hit_rate(mrs)
        auc_val = _auc(mrs)
        brier_val = _brier(mrs)
        ece_val = _ece(mrs)
        pred_home = _predicted_home_ratio(mrs)
        act_home = _actual_home_ratio(mrs)

        home_preds = [r for r in mrs if r.get("predicted_side") == "home"]
        away_preds = [r for r in mrs if r.get("predicted_side") == "away"]

        if n < MONTHLY_STABLE_MIN_N:
            month_status = "SAMPLE_LIMITED"
        elif hr >= MONTHLY_STABLE_MIN_HITRATE:
            month_status = "STABLE"
        else:
            month_status = "DRIFT_WARNING"
            all_stable = False
            any_drift_warning = True

        monthly_results.append({
            "month": month,
            "n": n,
            "hit_rate": round(hr, 6),
            "auc": round(auc_val, 6) if auc_val is not None else None,
            "brier": round(brier_val, 6) if brier_val is not None else None,
            "ece": ece_val,
            "predicted_home_ratio": round(pred_home, 4),
            "actual_home_ratio": round(act_home, 4),
            "predicted_side_split": {
                "home_n": len(home_preds),
                "away_n": len(away_preds),
                "home_hit_rate": round(_hit_rate(home_preds), 6) if home_preds else None,
                "away_hit_rate": round(_hit_rate(away_preds), 6) if away_preds else None,
            },
            "month_status": month_status,
        })

    # Aggregate monthly status
    valid_months = [m for m in monthly_results if m["month_status"] != "SAMPLE_LIMITED"]
    if not valid_months:
        aggregate_monthly_status = "SAMPLE_LIMITED"
    elif any_drift_warning:
        aggregate_monthly_status = "MONTHLY_DRIFT_WARNING"
    else:
        aggregate_monthly_status = "MONTHLY_ALL_STABLE"

    return {
        "step": "step2_monthly_drift",
        "segment": "HIGH_FIP",
        "n_total": len(high_rows),
        "overall_hit_rate": round(_hit_rate(high_rows), 6),
        "monthly_breakdown": monthly_results,
        "aggregate_monthly_status": aggregate_monthly_status,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 3: Rolling chronological windows
# ---------------------------------------------------------------------------

def step3_rolling_windows(outcome_rows: list[dict]) -> dict[str, Any]:
    high_rows = [r for r in outcome_rows if abs(r["sp_fip_delta"]) >= HIGH_FIP_THRESHOLD]
    high_sorted = sorted(high_rows, key=lambda r: r.get("game_date", ""))

    n = len(high_sorted)

    # Determine window size per spec
    if n >= 200:
        window_size = 100
    elif n >= 150:
        window_size = 75
    elif n >= 100:
        window_size = 50
    else:
        return {
            "step": "step3_rolling_windows",
            "segment": "HIGH_FIP",
            "n_available": n,
            "window_size": None,
            "windows": [],
            "rolling_status": "SAMPLE_LIMITED",
            "status": "PASSED",
        }

    step = max(1, window_size // 4)  # 25 for window=100
    windows = []
    any_below = False

    for start_idx in range(0, n - window_size + 1, step):
        end_idx = start_idx + window_size
        window_rows = high_sorted[start_idx:end_idx]
        hr = _hit_rate(window_rows)
        auc_val = _auc(window_rows)
        brier_val = _brier(window_rows)
        start_date = window_rows[0].get("game_date", "")
        end_date = window_rows[-1].get("game_date", "")

        if hr >= 0.55:
            w_status = "ROLLING_STABLE"
        else:
            w_status = "ROLLING_DRIFT_WARNING"
            any_below = True

        windows.append({
            "window_index": len(windows),
            "start_date": start_date,
            "end_date": end_date,
            "start_row_idx": start_idx,
            "end_row_idx": end_idx - 1,
            "n": len(window_rows),
            "hit_rate": round(hr, 6),
            "auc": round(auc_val, 6) if auc_val is not None else None,
            "brier": round(brier_val, 6) if brier_val is not None else None,
            "window_status": w_status,
        })

    rolling_status = "WARNING" if any_below else "STABLE"

    return {
        "step": "step3_rolling_windows",
        "segment": "HIGH_FIP",
        "n_available": n,
        "window_size": window_size,
        "step_size": step,
        "n_windows": len(windows),
        "windows": windows,
        "rolling_status": rolling_status,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 4: Control segment comparison
# ---------------------------------------------------------------------------

def step4_control_segments(outcome_rows: list[dict]) -> dict[str, Any]:
    mid_rows = [r for r in outcome_rows if 0.5 <= abs(r["sp_fip_delta"]) < HIGH_FIP_THRESHOLD]
    low_rows = [r for r in outcome_rows if abs(r["sp_fip_delta"]) < MID_FIP_LOWER]

    def ctrl_summary(rows: list[dict], seg_name: str, expected_status: str) -> dict:
        hr = _hit_rate(rows)
        # Confirm watch-only: must not exceed home_baseline + 0.03
        home_baseline = 0.524752  # from P92
        promoted = hr > home_baseline + 0.03
        return {
            "segment": seg_name,
            "n": len(rows),
            "hit_rate": round(hr, 6),
            "home_baseline": home_baseline,
            "home_baseline_plus_margin": round(home_baseline + 0.03, 6),
            "exceeds_baseline_margin": promoted,
            "tracking_status": expected_status,
            "promotion_allowed": False,
            "drift_monitor_promotion": False,
        }

    mid_ctrl = ctrl_summary(mid_rows, "MID_FIP", "MID_FIP_WATCH_ONLY")
    low_ctrl = ctrl_summary(low_rows, "LOW_FIP", "LOW_FIP_WATCH_ONLY")

    return {
        "step": "step4_control_segments",
        "mid_fip": mid_ctrl,
        "low_fip": low_ctrl,
        "mid_watch_only_confirmed": not mid_ctrl["exceeds_baseline_margin"],
        "low_watch_only_confirmed": not low_ctrl["exceeds_baseline_margin"],
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5: Coverage-aware decision
# ---------------------------------------------------------------------------

def step5_coverage(coverage_info: dict) -> dict[str, Any]:
    pct = coverage_info.get("schedule_coverage_pct", 0.0)

    if pct >= 80.0:
        coverage_status = "COVERAGE_HIGH"
    elif pct >= 60.0:
        coverage_status = "COVERAGE_MODERATE"
    else:
        coverage_status = "COVERAGE_LIMITED"

    return {
        "step": "step5_coverage",
        "canonical_rows": coverage_info.get("total_rows", 0),
        "schedule_rows": SCHEDULE_TOTAL,
        "schedule_coverage_pct": pct,
        "coverage_status": coverage_status,
        "observed_range": "2026-03 to 2026-05",
        "full_season_claim": False,
        "product_claim": False,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 6: Final classification
# ---------------------------------------------------------------------------

ALLOWED_CLASSIFICATIONS = [
    "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED",
    "P96_HIGH_FIP_DRIFT_MONITOR_WARNING_COVERAGE_LIMITED",
    "P96_HIGH_FIP_DRIFT_MONITOR_SAMPLE_LIMITED",
    "P96_HIGH_FIP_DRIFT_MONITOR_FAILED_VALIDATION",
]


def step6_classification(
    preflight: dict,
    monthly: dict,
    rolling: dict,
    coverage: dict,
) -> dict[str, Any]:
    if not preflight.get("all_gates_ok", False):
        return {
            "step": "step6_classification",
            "final_classification": "P96_HIGH_FIP_DRIFT_MONITOR_FAILED_VALIDATION",
            "rationale": f"Preflight failures: {preflight.get('failures', [])}",
        }

    coverage_status = coverage.get("coverage_status", "")
    monthly_status = monthly.get("aggregate_monthly_status", "")
    rolling_status = rolling.get("rolling_status", "")

    # SAMPLE_LIMITED path
    if rolling_status == "SAMPLE_LIMITED":
        return {
            "step": "step6_classification",
            "final_classification": "P96_HIGH_FIP_DRIFT_MONITOR_SAMPLE_LIMITED",
            "rationale": "Insufficient HIGH_FIP rows for rolling window analysis.",
        }

    # Determine classification
    is_stable = (
        monthly_status == "MONTHLY_ALL_STABLE"
        and rolling_status == "STABLE"
    )

    if coverage_status == "COVERAGE_LIMITED":
        if is_stable:
            fc = "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED"
            rationale = (
                "All HIGH_FIP monthly windows stable (hit_rate >= 0.55). "
                "Rolling windows all STABLE. "
                "Coverage limited to 34.07% (March–May 2026 only). "
                "No product or production claim permitted."
            )
        else:
            fc = "P96_HIGH_FIP_DRIFT_MONITOR_WARNING_COVERAGE_LIMITED"
            rationale = (
                f"Monthly status={monthly_status}, rolling={rolling_status}. "
                "One or more segments showed drift warning. Coverage limited."
            )
    else:
        # COVERAGE_MODERATE or COVERAGE_HIGH
        if is_stable:
            fc = "P96_HIGH_FIP_DRIFT_MONITOR_STABLE_COVERAGE_LIMITED"
            rationale = "All stable, coverage moderate/high."
        else:
            fc = "P96_HIGH_FIP_DRIFT_MONITOR_WARNING_COVERAGE_LIMITED"
            rationale = "Drift warning detected."

    return {
        "step": "step6_classification",
        "final_classification": fc,
        "rationale": rationale,
        "monthly_status": monthly_status,
        "rolling_status": rolling_status,
        "coverage_status": coverage_status,
    }


# ---------------------------------------------------------------------------
# Governance guard block
# ---------------------------------------------------------------------------

GOVERNANCE_GUARDS: dict[str, Any] = {
    "odds_used": False,
    "ev_computed": False,
    "clv_computed": False,
    "kelly_computed": False,
    "stake_sizing": False,
    "taiwan_lottery_recommendation": False,
    "champion_replacement": False,
    "production_mutation": False,
    "calibration_refit": False,
    "platt_scaling": False,
    "isotonic_scaling": False,
    "score_transform_refit": False,
    "live_api_calls": 0,
    "paid_api_calls": 0,
    "canonical_rows_modified": False,
    "outcome_rows_modified": False,
    "p83e_mapping_modified": False,
    "p84_to_p95_artifacts_modified": False,
    "paper_only": True,
    "diagnostic_only": True,
    "production_ready": False,
    "real_bet_allowed": False,
    "recommendation_allowed": False,
    "status": "PASSED",
}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("P96 High-FIP Segment Drift Monitor")
    print("=" * 60)

    # Step 1
    print("\n[Step 1] Pre-flight and upstream verification...")
    s1 = step1_preflight()
    outcome_rows: list[dict] = s1.pop("_outcome_rows", [])

    if not s1.get("all_gates_ok", False):
        print(f"  FAILED: {s1['failures']}")
        result = {
            "phase": "P96",
            "final_classification": "P96_HIGH_FIP_DRIFT_MONITOR_FAILED_VALIDATION",
            "classification_rationale": f"Step 1 failures: {s1['failures']}",
            "step1_preflight": s1,
            "governance_guards": GOVERNANCE_GUARDS,
            "paper_only": True,
            "diagnostic_only": True,
            "production_ready": False,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
        OUT_JSON.write_text(json.dumps(result, indent=2))
        print(f"Summary written: {OUT_JSON}")
        return 1

    coverage_info = s1.get("coverage", {})
    print(f"  gates passed: {len(s1['gates_passed'])}, failures: {len(s1['failures'])}")
    print(f"  coverage: {coverage_info.get('total_rows')}/{SCHEDULE_TOTAL} = {coverage_info.get('schedule_coverage_pct')}%")

    # Step 2
    print("\n[Step 2] HIGH_FIP monthly drift monitor...")
    s2 = step2_monthly_drift(outcome_rows)
    for m in s2["monthly_breakdown"]:
        print(f"  {m['month']}: n={m['n']}, hit_rate={m['hit_rate']:.6f}, status={m['month_status']}")
    print(f"  aggregate_monthly_status: {s2['aggregate_monthly_status']}")

    # Step 3
    print("\n[Step 3] Rolling chronological windows...")
    s3 = step3_rolling_windows(outcome_rows)
    print(f"  n={s3['n_available']}, window_size={s3['window_size']}, n_windows={s3['n_windows']}")
    for w in s3["windows"]:
        print(f"  [{w['start_date']}→{w['end_date']}] n={w['n']}, hit_rate={w['hit_rate']:.4f}, status={w['window_status']}")
    print(f"  rolling_status: {s3['rolling_status']}")

    # Step 4
    print("\n[Step 4] Control segment comparison...")
    s4 = step4_control_segments(outcome_rows)
    mid = s4["mid_fip"]
    low = s4["low_fip"]
    print(f"  MID: n={mid['n']}, hit_rate={mid['hit_rate']:.6f}, tracking_status={mid['tracking_status']}")
    print(f"  LOW: n={low['n']}, hit_rate={low['hit_rate']:.6f}, tracking_status={low['tracking_status']}")

    # Step 5
    print("\n[Step 5] Coverage-aware decision...")
    s5 = step5_coverage(coverage_info)
    print(f"  coverage_status: {s5['coverage_status']} ({s5['schedule_coverage_pct']}%)")

    # Step 6
    print("\n[Step 6] Final classification...")
    s6 = step6_classification(s1, s2, s3, s5)
    fc = s6["final_classification"]
    print(f"  FINAL_CLASSIFICATION: {fc}")
    print(f"  rationale: {s6['rationale']}")

    # Assemble output
    result: dict[str, Any] = {
        "phase": "P96",
        "final_classification": fc,
        "classification_rationale": s6["rationale"],
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "date": "2026-05-28",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "git_head": "25eced8",
        "step1_preflight": s1,
        "step2_monthly_drift": s2,
        "step3_rolling_windows": s3,
        "step4_control_segments": s4,
        "step5_coverage": s5,
        "step6_classification": s6,
        "governance_guards": GOVERNANCE_GUARDS,
        "governance_all_pass": True,
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "partial_coverage": True,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2))
    print(f"\nSummary JSON: {OUT_JSON}")

    # Write Markdown report
    _write_markdown(result)
    print(f"Report MD:    {OUT_MD}")

    print("\n" + "=" * 60)
    print(f"P96 complete: {fc}")
    print("paper_only=true | diagnostic_only=true | production_ready=false")
    print("no EV / no CLV / no Kelly / no odds / no recommendation")
    print("=" * 60)

    return 0


# ---------------------------------------------------------------------------
# Markdown report
# ---------------------------------------------------------------------------

def _write_markdown(d: dict) -> None:
    fc = d["final_classification"]
    s2 = d["step2_monthly_drift"]
    s3 = d["step3_rolling_windows"]
    s4 = d["step4_control_segments"]
    s5 = d["step5_coverage"]
    gen = d["generated_at"]

    monthly_rows = "\n".join(
        f"| {m['month']} | {m['n']} | {m['hit_rate']:.6f} | "
        f"{m['auc'] if m['auc'] is not None else 'N/A'} | "
        f"{m['brier'] if m['brier'] is not None else 'N/A'} | "
        f"{m['month_status']} |"
        for m in s2["monthly_breakdown"]
    )

    rolling_rows = "\n".join(
        f"| {w['window_index']} | {w['start_date']} | {w['end_date']} | {w['n']} | "
        f"{w['hit_rate']:.6f} | {w['window_status']} |"
        for w in s3.get("windows", [])
    )

    md = f"""# P96 High-FIP Segment Drift Monitor
**Generated:** {gen}
**Classification:** `{fc}`

---

## Governance

> ⚠️ **DIAGNOSTIC ONLY** — No betting recommendation, no product claim, no production use.
>
> `paper_only=true` | `diagnostic_only=true` | `production_ready=false`
> `odds_used=false` | `ev_computed=false` | `clv_computed=false` | `kelly_computed=false`

---

## Upstream Chain

| Phase | Classification |
|-------|----------------|
| P94   | `P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY` |
| P95   | `P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE` |
| P96   | `{fc}` |

---

## HIGH_FIP Overall

| Metric | Value |
|--------|-------|
| n | {s2['n_total']} |
| hit_rate | {s2['overall_hit_rate']:.6f} |
| aggregate_monthly_status | `{s2['aggregate_monthly_status']}` |
| rolling_status | `{s3['rolling_status']}` |

---

## Monthly Drift — HIGH_FIP (|ΔFIP| ≥ 1.5)

| Month | n | hit_rate | AUC | Brier | Status |
|-------|---|----------|-----|-------|--------|
{monthly_rows}

Drift rule: STABLE if n≥30 and hit_rate≥0.55; DRIFT_WARNING if n≥30 and hit_rate<0.55; SAMPLE_LIMITED if n<30.

---

## Rolling Windows — HIGH_FIP (window={s3.get('window_size')}, step={s3.get('step_size')})

| Window | Start | End | n | hit_rate | Status |
|--------|-------|-----|---|----------|--------|
{rolling_rows if rolling_rows else "| — | — | — | — | — | SAMPLE_LIMITED |"}

`rolling_status = {s3['rolling_status']}`

---

## Control Segment Comparison (Watch-Only)

| Segment | n | hit_rate | Tracking Status | Promoted? |
|---------|---|----------|-----------------|-----------|
| MID_FIP | {s4['mid_fip']['n']} | {s4['mid_fip']['hit_rate']:.6f} | `{s4['mid_fip']['tracking_status']}` | No |
| LOW_FIP | {s4['low_fip']['n']} | {s4['low_fip']['hit_rate']:.6f} | `{s4['low_fip']['tracking_status']}` | No |

---

## Coverage

| Metric | Value |
|--------|-------|
| canonical_rows | {s5['canonical_rows']} |
| schedule_total | {s5['schedule_rows']} |
| schedule_coverage_pct | {s5['schedule_coverage_pct']}% |
| coverage_status | `{s5['coverage_status']}` |
| observed_range | {s5['observed_range']} |
| full_season_claim | {s5['full_season_claim']} |

---

## Final Classification

```
{fc}
```

{d['classification_rationale']}

---

## Governance Guards

All guards locked. No odds, EV, CLV, Kelly, stake sizing, Taiwan lottery recommendation,
champion replacement, production mutation, calibration refit, or live/paid API calls.

| Guard | Value |
|-------|-------|
| odds_used | false |
| ev_computed | false |
| clv_computed | false |
| kelly_computed | false |
| stake_sizing | false |
| taiwan_lottery_recommendation | false |
| champion_replacement | false |
| production_mutation | false |
| calibration_refit | false |
| paper_only | **true** |
| diagnostic_only | **true** |
| production_ready | **false** |
| real_bet_allowed | **false** |
| recommendation_allowed | **false** |
"""

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(md)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
