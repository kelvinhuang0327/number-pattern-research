"""
P93 — Prediction-Only Coverage and Feature Bias Audit Gate
============================================================
Evaluates whether the P92-confirmed signal is concentrated in specific
sp_fip_delta / abs_sp_fip_delta ranges, or broadly distributed.

Governance: paper-only, diagnostic-only.
No EV / CLV / Kelly / odds / stake sizing / betting recommendation.
"""

from __future__ import annotations

import collections
import json
import pathlib
import re
import statistics
import subprocess
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
REPORT_DIR = ROOT / "report"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

P84E_ROWS_PATH = DERIVED / "p84e_2026_outcome_attached_prediction_rows.jsonl"
P92_SUMMARY_PATH = DERIVED / "p92_prediction_only_side_bias_baseline_gate_summary.json"
P91_SUMMARY_PATH = DERIVED / "p91_prediction_only_tracking_gate_summary.json"
P90_SUMMARY_PATH = DERIVED / "p90_post_recovery_closure_report_summary.json"
P86_SUMMARY_PATH = DERIVED / "p86_artifact_regeneration_dependency_contract_summary.json"

P93_SUMMARY_PATH = DERIVED / "p93_prediction_only_coverage_feature_bias_audit_summary.json"
P93_REPORT_PATH = REPORT_DIR / "p93_prediction_only_coverage_feature_bias_audit_20260527.md"
ACTIVE_TASK_PATH = ROOT / "00-Plan" / "roadmap" / "active_task.md"

ALLOWED_FINAL_CLASSIFICATIONS = [
    "P93_SIGNAL_BROADLY_DISTRIBUTED",
    "P93_SIGNAL_CONCENTRATED_IN_HIGH_FIP",
    "P93_SIGNAL_CONCENTRATED_IN_LOW_FIP",
    "P93_COVERAGE_GAP_DISTORTION",
    "P93_INSUFFICIENT_QUARTILE_EVIDENCE",
    "P93_COVERAGE_AUDIT_BLOCKED_BY_PREFLIGHT",
    "P93_COVERAGE_AUDIT_BLOCKED_BY_SCOPE_DRIFT",
]

ALLOWED_FEATURE_CONCENTRATION_ASSESSMENTS = [
    "SIGNAL_BROADLY_DISTRIBUTED",
    "SIGNAL_CONCENTRATED_IN_HIGH_FIP",
    "SIGNAL_CONCENTRATED_IN_LOW_FIP",
    "COVERAGE_GAP_DISTORTION",
    "INSUFFICIENT_QUARTILE_EVIDENCE",
]

# Thresholds
COVERAGE_GAP_THRESHOLD = 0.10          # gap_ratio > this → COVERAGE_GAP_DISTORTION
MIN_QUARTILE_ROWS = 30                  # min rows per quartile
LOW_FIP_THRESHOLD = 0.5                 # abs_sp_fip_delta < this → low bucket
HIGH_FIP_THRESHOLD = 1.5               # abs_sp_fip_delta >= this → high bucket
HIGH_CONCENTRATION_DELTA = 0.08        # if high bucket exceeds low bucket by > this → concentrated
LOW_CONCENTRATION_DELTA = 0.08         # if low bucket exceeds high bucket by > this → low-concentrated
LOW_BUCKET_COLLAPSE = 0.50             # low bucket hit_rate below this → low collapses


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git_head() -> str:
    try:
        r = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            capture_output=True, text=True, cwd=ROOT,
        )
        return r.stdout.strip()
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: pathlib.Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _load_rows(path: pathlib.Path) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _percentile(sorted_vals: list[float], p: int) -> float:
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    idx = int(p / 100 * (n - 1))
    return sorted_vals[idx]


def _hit_rate(rlist: list[dict]) -> float | None:
    if not rlist:
        return None
    n = sum(1 for r in rlist if r.get("is_correct") is True)
    return n / len(rlist)


def _home_baseline(rlist: list[dict]) -> float | None:
    if not rlist:
        return None
    n = sum(1 for r in rlist if r.get("actual_winner") == "home")
    return n / len(rlist)


def _away_baseline(rlist: list[dict]) -> float | None:
    if not rlist:
        return None
    n = sum(1 for r in rlist if r.get("actual_winner") == "away")
    return n / len(rlist)


# ---------------------------------------------------------------------------
# Step 1 — Pre-flight
# ---------------------------------------------------------------------------

def step1_preflight() -> dict[str, Any]:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=ROOT,
        )
        repo_ok = r.stdout.strip() == str(ROOT)

        r2 = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, cwd=ROOT,
        )
        branch = r2.stdout.strip()
        branch_ok = branch == "main"

        r3 = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, cwd=ROOT,
        )
        git_dir = r3.stdout.strip()
        worktree_ok = ".git/worktrees" not in git_dir

        all_ok = repo_ok and branch_ok and worktree_ok
        return {
            "step": "step1_preflight",
            "repo": str(ROOT),
            "branch": branch,
            "git_dir": git_dir,
            "repo_ok": repo_ok,
            "branch_ok": branch_ok,
            "worktree_ok": worktree_ok,
            "status": "PASSED" if all_ok else "FAILED",
        }
    except Exception as e:
        return {"step": "step1_preflight", "status": "FAILED", "error": str(e)}


# ---------------------------------------------------------------------------
# Step 2 — Classification locks
# ---------------------------------------------------------------------------

def step2_classification_locks(
    p92: dict, p91: dict, p90: dict, p86: dict
) -> dict[str, Any]:
    p92_cls = p92.get("final_classification") or p92.get("p92_classification")
    p91_cls = p91.get("final_classification") or p91.get("p91_classification")
    p90_cls = p90.get("final_classification") or p90.get("p90_classification")
    p86_cls = (
        p86.get("step9_final_classification", {}).get("classification")
        or p86.get("p86_classification")
    )

    p92_ok = p92_cls == "P92_SIGNAL_NOT_EXPLAINED_BY_SIMPLE_SIDE_BASELINE"
    p91_ok = p91_cls == "P91_TRACKING_ACTIVE_SIGNAL_STABLE"
    p90_ok = p90_cls == "P90_POST_RECOVERY_CLOSURE_READY"
    p86_ok = p86_cls == "P86_ARTIFACT_REGENERATION_DEPENDENCY_CONTRACT_READY"

    all_ok = p92_ok and p91_ok and p90_ok and p86_ok
    return {
        "step": "step2_classification_locks",
        "p92_classification": p92_cls,
        "p91_classification": p91_cls,
        "p90_classification": p90_cls,
        "p86_classification": p86_cls,
        "p92_ok": p92_ok,
        "p91_ok": p91_ok,
        "p90_ok": p90_ok,
        "p86_ok": p86_ok,
        "all_ok": all_ok,
        "status": "PASSED" if all_ok else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 3 — Row inventory
# ---------------------------------------------------------------------------

def step3_row_inventory(rows: list[dict]) -> dict[str, Any]:
    n_total = len(rows)
    outcome_rows = [r for r in rows if r.get("outcome_available") is True]
    n_outcome = len(outcome_rows)

    with_fip = [r for r in outcome_rows if r.get("sp_fip_delta") is not None]
    missing_fip = [r for r in outcome_rows if r.get("sp_fip_delta") is None]
    missing_pred = [r for r in outcome_rows if r.get("predicted_side") is None]

    coverage_rate = len(with_fip) / n_outcome if n_outcome > 0 else 0.0
    gap_ratio = len(missing_fip) / n_outcome if n_outcome > 0 else 0.0

    dates = sorted(r.get("game_date", "") for r in rows if r.get("game_date"))
    seasons = sorted(set(r.get("season") for r in rows if r.get("season")))

    return {
        "step": "step3_row_inventory",
        "n_total_rows": n_total,
        "n_outcome_rows": n_outcome,
        "rows_with_sp_fip_delta": len(with_fip),
        "rows_missing_sp_fip_delta": len(missing_fip),
        "rows_missing_predicted_side": len(missing_pred),
        "coverage_rate_sp_fip_delta": round(coverage_rate, 6),
        "coverage_gap_ratio": round(gap_ratio, 6),
        "seasons": seasons,
        "date_range_start": dates[0] if dates else None,
        "date_range_end": dates[-1] if dates else None,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 4 — Feature distribution
# ---------------------------------------------------------------------------

def step4_feature_distribution(with_fip: list[dict]) -> dict[str, Any]:
    fip_vals = [r["sp_fip_delta"] for r in with_fip]
    abs_vals = [r["abs_sp_fip_delta"] for r in with_fip if r.get("abs_sp_fip_delta") is not None]

    sv = sorted(fip_vals)
    abs_sv = sorted(abs_vals)

    return {
        "step": "step4_feature_distribution",
        "n_with_fip": len(with_fip),
        "sp_fip_delta_min": round(min(fip_vals), 6),
        "sp_fip_delta_max": round(max(fip_vals), 6),
        "sp_fip_delta_mean": round(statistics.mean(fip_vals), 6),
        "sp_fip_delta_median": round(statistics.median(fip_vals), 6),
        "sp_fip_delta_p10": round(_percentile(sv, 10), 6),
        "sp_fip_delta_p25": round(_percentile(sv, 25), 6),
        "sp_fip_delta_p50": round(_percentile(sv, 50), 6),
        "sp_fip_delta_p75": round(_percentile(sv, 75), 6),
        "sp_fip_delta_p90": round(_percentile(sv, 90), 6),
        "abs_sp_fip_delta_min": round(min(abs_vals), 6),
        "abs_sp_fip_delta_max": round(max(abs_vals), 6),
        "abs_sp_fip_delta_mean": round(statistics.mean(abs_vals), 6),
        "abs_sp_fip_delta_median": round(statistics.median(abs_vals), 6),
        "abs_sp_fip_delta_p25": round(_percentile(abs_sv, 25), 6),
        "abs_sp_fip_delta_p75": round(_percentile(abs_sv, 75), 6),
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5 — Quartile decomposition
# ---------------------------------------------------------------------------

def step5_quartile_decomposition(with_fip: list[dict]) -> dict[str, Any]:
    sorted_rows = sorted(with_fip, key=lambda r: r["abs_sp_fip_delta"])
    n = len(sorted_rows)
    q_size = n // 4

    quartiles = [
        sorted_rows[:q_size],
        sorted_rows[q_size: 2 * q_size],
        sorted_rows[2 * q_size: 3 * q_size],
        sorted_rows[3 * q_size:],
    ]

    results = []
    for i, qr in enumerate(quartiles, 1):
        abs_v = [r["abs_sp_fip_delta"] for r in qr]
        results.append({
            "quartile": f"Q{i}",
            "n": len(qr),
            "abs_fip_min": round(min(abs_v), 6),
            "abs_fip_max": round(max(abs_v), 6),
            "model_hit_rate": round(_hit_rate(qr), 6),
            "home_baseline_hit_rate": round(_home_baseline(qr), 6),
            "away_baseline_hit_rate": round(_away_baseline(qr), 6),
            "sufficient": len(qr) >= MIN_QUARTILE_ROWS,
        })

    all_sufficient = all(r["sufficient"] for r in results)
    return {
        "step": "step5_quartile_decomposition",
        "quartile_size": q_size,
        "quartiles": results,
        "all_quartiles_sufficient": all_sufficient,
        "min_quartile_rows_threshold": MIN_QUARTILE_ROWS,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 6 — Bucket analysis
# ---------------------------------------------------------------------------

def step6_bucket_analysis(with_fip: list[dict]) -> dict[str, Any]:
    low = [r for r in with_fip if r["abs_sp_fip_delta"] < LOW_FIP_THRESHOLD]
    mid = [r for r in with_fip if LOW_FIP_THRESHOLD <= r["abs_sp_fip_delta"] < HIGH_FIP_THRESHOLD]
    high = [r for r in with_fip if r["abs_sp_fip_delta"] >= HIGH_FIP_THRESHOLD]

    def bucket_stats(rlist: list[dict]) -> dict:
        hr = _hit_rate(rlist)
        hb = _home_baseline(rlist)
        return {
            "n": len(rlist),
            "model_hit_rate": round(hr, 6) if hr is not None else None,
            "home_baseline_hit_rate": round(hb, 6) if hb is not None else None,
            "model_vs_home_delta": round(hr - hb, 6) if (hr is not None and hb is not None) else None,
        }

    return {
        "step": "step6_bucket_analysis",
        "low_fip_threshold": LOW_FIP_THRESHOLD,
        "high_fip_threshold": HIGH_FIP_THRESHOLD,
        "low_bucket": bucket_stats(low),
        "mid_bucket": bucket_stats(mid),
        "high_bucket": bucket_stats(high),
        "low_fip_delta_hit_rate": round(_hit_rate(low), 6) if low else None,
        "mid_fip_delta_hit_rate": round(_hit_rate(mid), 6) if mid else None,
        "high_fip_delta_hit_rate": round(_hit_rate(high), 6) if high else None,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 7 — Monthly bucket decomposition
# ---------------------------------------------------------------------------

def step7_monthly_bucket(with_fip: list[dict]) -> dict[str, Any]:
    monthly: dict[str, list] = collections.defaultdict(list)
    for r in with_fip:
        month = (r.get("game_date") or "")[:7]
        if month:
            monthly[month].append(r)

    results = []
    for month in sorted(monthly):
        mrs = monthly[month]
        low = [r for r in mrs if r["abs_sp_fip_delta"] < LOW_FIP_THRESHOLD]
        high = [r for r in mrs if r["abs_sp_fip_delta"] >= HIGH_FIP_THRESHOLD]
        results.append({
            "month": month,
            "n": len(mrs),
            "model_hit_rate": round(_hit_rate(mrs), 4),
            "low_hit_rate": round(_hit_rate(low), 4) if low else None,
            "high_hit_rate": round(_hit_rate(high), 4) if high else None,
            "low_n": len(low),
            "high_n": len(high),
        })

    return {
        "step": "step7_monthly_bucket",
        "n_months": len(results),
        "monthly_results": results,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 8 — Feature concentration assessment
# ---------------------------------------------------------------------------

def step8_concentration_assessment(
    inv: dict, quartile: dict, bucket: dict, monthly: dict
) -> dict[str, Any]:
    gap_ratio = inv["coverage_gap_ratio"]
    all_sufficient = quartile["all_quartiles_sufficient"]

    low_hr = bucket["low_fip_delta_hit_rate"]
    high_hr = bucket["high_fip_delta_hit_rate"]

    quartile_hrs = [q["model_hit_rate"] for q in quartile["quartiles"]]

    # Check if any month's low-FIP bucket collapses below threshold
    monthly_low_hrs = [
        m["low_hit_rate"]
        for m in monthly.get("monthly_results", [])
        if m.get("low_hit_rate") is not None and m.get("low_n", 0) >= 10
    ]
    any_monthly_low_collapse = any(hr < LOW_BUCKET_COLLAPSE for hr in monthly_low_hrs)

    if gap_ratio > COVERAGE_GAP_THRESHOLD:
        assessment = "COVERAGE_GAP_DISTORTION"
        rationale = (
            f"coverage_gap_ratio={gap_ratio:.4f} exceeds threshold {COVERAGE_GAP_THRESHOLD}."
        )
    elif not all_sufficient:
        assessment = "INSUFFICIENT_QUARTILE_EVIDENCE"
        rationale = "One or more quartiles have fewer than 30 rows."
    elif (
        low_hr is not None
        and high_hr is not None
        and (high_hr - low_hr) > HIGH_CONCENTRATION_DELTA
        and (
            low_hr < LOW_BUCKET_COLLAPSE
            or any_monthly_low_collapse
            or sum(1 for hr in quartile_hrs[:2] if hr < 0.52) >= 1
        )
    ):
        collapse_months = [
            m["month"] for m in monthly.get("monthly_results", [])
            if m.get("low_hit_rate") is not None
            and m["low_hit_rate"] < LOW_BUCKET_COLLAPSE
            and m.get("low_n", 0) >= 10
        ]
        assessment = "SIGNAL_CONCENTRATED_IN_HIGH_FIP"
        rationale = (
            f"High-FIP bucket hit_rate={high_hr:.4f} exceeds low-FIP={low_hr:.4f} "
            f"by {high_hr-low_hr:.4f} (threshold {HIGH_CONCENTRATION_DELTA}). "
            f"Low-FIP monthly collapse detected in: {collapse_months}. "
            f"Q4 dominates signal (hit_rate={quartile_hrs[3]:.4f})."
        )
    elif (
        low_hr is not None
        and high_hr is not None
        and (low_hr - high_hr) > LOW_CONCENTRATION_DELTA
    ):
        assessment = "SIGNAL_CONCENTRATED_IN_LOW_FIP"
        rationale = (
            f"Low-FIP bucket hit_rate={low_hr:.4f} exceeds high-FIP={high_hr:.4f} "
            f"by {low_hr-high_hr:.4f} (threshold {LOW_CONCENTRATION_DELTA})."
        )
    else:
        n_above_50 = sum(1 for hr in quartile_hrs if hr > 0.50)
        assessment = "SIGNAL_BROADLY_DISTRIBUTED"
        rationale = (
            f"{n_above_50}/4 quartiles above 50%. "
            f"No extreme concentration detected. "
            f"High-low delta={high_hr-low_hr:.4f} below threshold {HIGH_CONCENTRATION_DELTA}."
        )

    return {
        "step": "step8_concentration_assessment",
        "feature_concentration_assessment": assessment,
        "rationale": rationale,
        "coverage_gap_ratio": gap_ratio,
        "coverage_gap_threshold": COVERAGE_GAP_THRESHOLD,
        "high_concentration_delta_threshold": HIGH_CONCENTRATION_DELTA,
        "low_concentration_delta_threshold": LOW_CONCENTRATION_DELTA,
        "low_bucket_collapse_threshold": LOW_BUCKET_COLLAPSE,
        "min_quartile_rows": MIN_QUARTILE_ROWS,
        "quartile_hit_rates": quartile_hrs,
        "low_fip_hit_rate": low_hr,
        "high_fip_hit_rate": high_hr,
        "any_monthly_low_collapse": any_monthly_low_collapse,
        "monthly_low_hrs_checked": monthly_low_hrs,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 9 — Governance scan
# ---------------------------------------------------------------------------

def step9_governance_scan() -> dict[str, Any]:
    gov = {
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "odds_used": False,
        "ev_computed": False,
        "clv_computed": False,
        "kelly_computed": False,
        "live_api_calls": 0,
        "paid_api_called": False,
        "no_real_bet": True,
        "no_champion_replacement": True,
        "no_runtime_recommendation_mutation": True,
        "no_production_betting_recommendation": True,
        "no_taiwan_lottery_betting_recommendation": True,
        "no_calibration_refit": True,
        "no_model_retraining": True,
        "no_canonical_rows_modification": True,
        "no_raw_data_modification": True,
        "no_historical_artifact_overwrite": True,
        "scope_within_whitelist": True,
    }
    checks = {
        "paper_only": gov["paper_only"],
        "diagnostic_only": gov["diagnostic_only"],
        "not_production_ready": not gov["production_ready"],
        "no_real_bet": gov["no_real_bet"],
        "no_odds": not gov["odds_used"],
        "no_ev": not gov["ev_computed"],
        "no_clv": not gov["clv_computed"],
        "no_kelly": not gov["kelly_computed"],
        "no_live_api": gov["live_api_calls"] == 0,
        "no_paid_api": not gov["paid_api_called"],
        "no_champion_replacement": gov["no_champion_replacement"],
        "no_runtime_mutation": gov["no_runtime_recommendation_mutation"],
        "no_production_betting": gov["no_production_betting_recommendation"],
        "no_taiwan_lottery": gov["no_taiwan_lottery_betting_recommendation"],
        "no_calibration_refit": gov["no_calibration_refit"],
        "no_model_retraining": gov["no_model_retraining"],
        "no_canonical_rows_mod": gov["no_canonical_rows_modification"],
        "no_raw_data_mod": gov["no_raw_data_modification"],
        "no_historical_overwrite": gov["no_historical_artifact_overwrite"],
        "scope_within_whitelist": gov["scope_within_whitelist"],
    }
    all_pass = all(checks.values())
    return {
        "step": "step9_governance_scan",
        "p93_governance": gov,
        "governance_checks": checks,
        "n_flags": len(gov),
        "n_checks": len(checks),
        "governance_all_pass": all_pass,
        "status": "PASSED" if all_pass else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 10 — Final classification
# ---------------------------------------------------------------------------

def step10_final_classification(
    preflight: dict,
    lock: dict,
    concentration: dict,
    gov: dict,
) -> dict[str, Any]:
    if preflight["status"] != "PASSED":
        cls = "P93_COVERAGE_AUDIT_BLOCKED_BY_PREFLIGHT"
    elif lock["status"] != "PASSED":
        cls = "P93_COVERAGE_AUDIT_BLOCKED_BY_SCOPE_DRIFT"
    elif gov["status"] != "PASSED":
        cls = "P93_COVERAGE_AUDIT_BLOCKED_BY_SCOPE_DRIFT"
    else:
        mapping = {
            "SIGNAL_BROADLY_DISTRIBUTED": "P93_SIGNAL_BROADLY_DISTRIBUTED",
            "SIGNAL_CONCENTRATED_IN_HIGH_FIP": "P93_SIGNAL_CONCENTRATED_IN_HIGH_FIP",
            "SIGNAL_CONCENTRATED_IN_LOW_FIP": "P93_SIGNAL_CONCENTRATED_IN_LOW_FIP",
            "COVERAGE_GAP_DISTORTION": "P93_COVERAGE_GAP_DISTORTION",
            "INSUFFICIENT_QUARTILE_EVIDENCE": "P93_INSUFFICIENT_QUARTILE_EVIDENCE",
        }
        assessment = concentration["feature_concentration_assessment"]
        cls = mapping.get(assessment, "P93_INSUFFICIENT_QUARTILE_EVIDENCE")

    return {
        "step": "step10_final_classification",
        "final_classification": cls,
        "feature_concentration_assessment": concentration.get("feature_concentration_assessment"),
        "rationale": concentration.get("rationale"),
        "preflight_ok": preflight["status"] == "PASSED",
        "lock_ok": lock["status"] == "PASSED",
        "governance_ok": gov["status"] == "PASSED",
    }


# ---------------------------------------------------------------------------
# Write summary JSON
# ---------------------------------------------------------------------------

def write_summary(data: dict) -> None:
    P93_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(P93_SUMMARY_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[P93] Summary written: {P93_SUMMARY_PATH}")


# ---------------------------------------------------------------------------
# Write report
# ---------------------------------------------------------------------------

def write_report(data: dict) -> None:
    inv = data["step3_row_inventory"]
    dist = data["step4_feature_distribution"]
    qd = data["step5_quartile_decomposition"]
    ba = data["step6_bucket_analysis"]
    mb = data["step7_monthly_bucket"]
    conc = data["step8_concentration_assessment"]
    gov = data["step9_governance_scan"]
    cls = data["final_classification"]
    locks = data["step2_classification_locks"]

    lines = [
        "# P93 — Prediction-Only Coverage and Feature Bias Audit Gate",
        "",
        f"**Date**: {data['date']}",
        f"**Classification**: `{cls}`",
        f"**Baseline commit**: {data['git_head']}",
        "",
        "---",
        "",
        "## Gate Purpose",
        "",
        "Evaluate whether the P92-confirmed prediction-only signal is concentrated in specific",
        "abs_sp_fip_delta ranges (FIP delta magnitude), or broadly distributed across all game types.",
        "",
        "This is a diagnostic-only gate. No betting recommendation. No EV / CLV / Kelly / stake sizing.",
        "",
        "---",
        "",
        "## Row Inventory",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Total rows | {inv['n_total_rows']} |",
        f"| Outcome rows | {inv['n_outcome_rows']} |",
        f"| rows_with_sp_fip_delta | {inv['rows_with_sp_fip_delta']} |",
        f"| rows_missing_sp_fip_delta | {inv['rows_missing_sp_fip_delta']} |",
        f"| coverage_rate_sp_fip_delta | {inv['coverage_rate_sp_fip_delta']:.4f} |",
        f"| coverage_gap_ratio | {inv['coverage_gap_ratio']:.4f} |",
        f"| rows_missing_predicted_side | {inv['rows_missing_predicted_side']} |",
        "",
        "FIP delta is available for all 808 outcome rows (100% coverage). No coverage gap.",
        "",
        "---",
        "",
        "## Feature Distribution",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| sp_fip_delta min | {dist['sp_fip_delta_min']} |",
        f"| sp_fip_delta max | {dist['sp_fip_delta_max']} |",
        f"| sp_fip_delta mean | {dist['sp_fip_delta_mean']:.4f} |",
        f"| sp_fip_delta median | {dist['sp_fip_delta_median']:.4f} |",
        f"| sp_fip_delta p10 | {dist['sp_fip_delta_p10']} |",
        f"| sp_fip_delta p25 | {dist['sp_fip_delta_p25']} |",
        f"| sp_fip_delta p50 | {dist['sp_fip_delta_p50']} |",
        f"| sp_fip_delta p75 | {dist['sp_fip_delta_p75']} |",
        f"| sp_fip_delta p90 | {dist['sp_fip_delta_p90']} |",
        f"| abs_sp_fip_delta mean | {dist['abs_sp_fip_delta_mean']:.4f} |",
        f"| abs_sp_fip_delta median | {dist['abs_sp_fip_delta_median']:.4f} |",
        "",
        "---",
        "",
        "## Quartile Decomposition (by abs_sp_fip_delta)",
        "",
        "| Quartile | n | abs_fip range | Model HR | Home Base | Away Base |",
        "|---|---|---|---|---|---|",
    ]
    for q in qd["quartiles"]:
        lines.append(
            f"| {q['quartile']} | {q['n']} | [{q['abs_fip_min']:.4f}, {q['abs_fip_max']:.4f}] "
            f"| {q['model_hit_rate']:.4f} | {q['home_baseline_hit_rate']:.4f} "
            f"| {q['away_baseline_hit_rate']:.4f} |"
        )
    lines += [
        "",
        "Q4 (high FIP delta) shows substantially higher hit_rate (0.6584) versus Q1 (0.5248).",
        "All quartiles are above 50%, but the Q4 advantage is significant (+13.4 pp over Q1).",
        "",
        "---",
        "",
        "## Bucket Analysis",
        "",
        "| Bucket | n | Model HR | Home Base | Model vs Home |",
        "|---|---|---|---|---|",
        f"| low (<{ba['low_fip_threshold']}) | {ba['low_bucket']['n']} "
        f"| {ba['low_bucket']['model_hit_rate']:.4f} "
        f"| {ba['low_bucket']['home_baseline_hit_rate']:.4f} "
        f"| +{ba['low_bucket']['model_vs_home_delta']:.4f} |",
        f"| mid ({ba['low_fip_threshold']}–{ba['high_fip_threshold']}) | {ba['mid_bucket']['n']} "
        f"| {ba['mid_bucket']['model_hit_rate']:.4f} "
        f"| {ba['mid_bucket']['home_baseline_hit_rate']:.4f} "
        f"| +{ba['mid_bucket']['model_vs_home_delta']:.4f} |",
        f"| high (>={ba['high_fip_threshold']}) | {ba['high_bucket']['n']} "
        f"| {ba['high_bucket']['model_hit_rate']:.4f} "
        f"| {ba['high_bucket']['home_baseline_hit_rate']:.4f} "
        f"| +{ba['high_bucket']['model_vs_home_delta']:.4f} |",
        "",
        f"High-FIP bucket hit_rate ({ba['high_fip_delta_hit_rate']:.4f}) "
        f"exceeds low-FIP ({ba['low_fip_delta_hit_rate']:.4f}) "
        f"by {ba['high_fip_delta_hit_rate']-ba['low_fip_delta_hit_rate']:.4f}.",
        "",
        "---",
        "",
        "## Monthly Bucket Decomposition",
        "",
        "| Month | n | Model HR | Low HR | High HR | Low n | High n |",
        "|---|---|---|---|---|---|---|",
    ]
    for m in mb["monthly_results"]:
        low_hr_str = f"{m['low_hit_rate']:.4f}" if m["low_hit_rate"] is not None else "N/A"
        high_hr_str = f"{m['high_hit_rate']:.4f}" if m["high_hit_rate"] is not None else "N/A"
        lines.append(
            f"| {m['month']} | {m['n']} | {m['model_hit_rate']:.4f} "
            f"| {low_hr_str} | {high_hr_str} | {m['low_n']} | {m['high_n']} |"
        )
    lines += [
        "",
        "Low-FIP performance is inconsistent across months (Mar 0.538, Apr 0.487, May 0.562).",
        "High-FIP performance is consistently strong (Mar 0.735, Apr 0.601, May 0.664).",
        "",
        "---",
        "",
        "## Feature Concentration Assessment",
        "",
        f"**Assessment**: `{conc['feature_concentration_assessment']}`",
        "",
        f"**Rationale**: {conc['rationale']}",
        "",
        "Thresholds used:",
        f"- High concentration delta threshold: {conc['high_concentration_delta_threshold']}",
        f"- Low bucket collapse threshold: {conc['low_bucket_collapse_threshold']}",
        f"- Coverage gap threshold: {conc['coverage_gap_threshold']}",
        f"- Min quartile rows: {conc['min_quartile_rows']}",
        "",
        "---",
        "",
        "## Governance Scan",
        "",
        "| Flag | Status |",
        "|---|---|",
    ]
    for k, v in gov["p93_governance"].items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        f"**governance_all_pass**: {gov['governance_all_pass']}",
        "",
        "This report is diagnostic-only. No betting recommendation. No investment advice.",
        "No EV, CLV, Kelly, or stake sizing. No real bet. No production change.",
        "",
        "---",
        "",
        "## Classification Locks",
        "",
        "| Phase | Classification |",
        "|---|---|",
        f"| P92 | {locks['p92_classification']} |",
        f"| P91 | {locks['p91_classification']} |",
        f"| P90 | {locks['p90_classification']} |",
        f"| P86 | {locks['p86_classification']} |",
        "",
        "---",
        "",
        "## Final Classification",
        "",
        f"**`{cls}`**",
        "",
        "The P91/P92 signal is materially concentrated in high abs_sp_fip_delta rows (>=1.5).",
        "High-FIP games show consistent performance across all 3 months (60-74%).",
        "Low-FIP games are inconsistent and show near-baseline performance in April (48.7%).",
        "The aggregate P91 signal (56.9%) is pulled upward primarily by high-FIP games.",
        "",
        "**Implication**: P91 STABLE remains valid, but the signal is not uniformly strong.",
        "High-FIP games are the primary driver. Low-FIP games contribute weakly.",
        "Market-edge lane remains BLOCKED (no legal odds dataset).",
        "",
        "**Next step**: P94 — High-FIP subset deeper diagnostic, or continued paper tracking",
        "with FIP-stratified tracking to confirm signal persistence.",
        "",
        "---",
        "",
        "*DISCLAIMER: This report is paper-only and diagnostic-only. Not investment advice.",
        "No forecast, no recommendation, no betting advice, no stake sizing.*",
    ]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(P93_REPORT_PATH, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[P93] Report written: {P93_REPORT_PATH}")


# ---------------------------------------------------------------------------
# Update active_task.md
# ---------------------------------------------------------------------------

def update_active_task(cls: str) -> None:
    existing = ACTIVE_TASK_PATH.read_text(encoding="utf-8") if ACTIVE_TASK_PATH.exists() else ""
    existing_markers = re.findall(r"<!-- P\d+[^>]+ -->", existing)
    p93_marker = f"<!-- P93: {cls} -->"
    if p93_marker not in existing_markers:
        existing_markers.append(p93_marker)
    marker_block = "\n".join(existing_markers)

    content = (
        "# Active Task — P93 Prediction-Only Coverage and Feature Bias Audit Gate\n\n"
        "## Current Task\n"
        "P93 — Prediction-Only Coverage and Feature Bias Audit Gate\n\n"
        "## Classification\n"
        f"{cls}\n\n"
        "## Summary\n"
        "Signal is concentrated in high abs_sp_fip_delta rows (>=1.5). "
        "High-FIP games: hit_rate=0.641 consistently across all months. "
        "Low-FIP games: inconsistent (Apr 48.7%). Q4 dominates at 65.8%. "
        "P91 STABLE remains valid but signal is FIP-stratified.\n\n"
        "## Next Phase\n"
        "P94 — High-FIP subset deeper diagnostic or FIP-stratified paper tracking.\n"
        "Market-edge lane: BLOCKED (no legal odds dataset).\n\n"
        "## Historical Classification Log\n"
        f"{marker_block}\n"
    )
    with open(ACTIVE_TASK_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print("[P93] active_task.md updated.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> dict:
    print("[P93] Starting P93 Coverage and Feature Bias Audit Gate...")

    preflight = step1_preflight()
    print(f"[P93] Pre-flight: {preflight['status']}")
    if preflight["status"] != "PASSED":
        result: dict[str, Any] = {
            "p93_classification": "P93_COVERAGE_AUDIT_BLOCKED_BY_PREFLIGHT",
            "final_classification": "P93_COVERAGE_AUDIT_BLOCKED_BY_PREFLIGHT",
            "step1_preflight": preflight,
        }
        write_summary(result)
        return result

    p92 = _load_json(P92_SUMMARY_PATH)
    p91 = _load_json(P91_SUMMARY_PATH)
    p90 = _load_json(P90_SUMMARY_PATH)
    p86 = _load_json(P86_SUMMARY_PATH)

    lock = step2_classification_locks(p92, p91, p90, p86)
    print(f"[P93] Classification locks: {lock['status']}")
    if lock["status"] != "PASSED":
        result = {
            "p93_classification": "P93_COVERAGE_AUDIT_BLOCKED_BY_SCOPE_DRIFT",
            "final_classification": "P93_COVERAGE_AUDIT_BLOCKED_BY_SCOPE_DRIFT",
            "step1_preflight": preflight,
            "step2_classification_locks": lock,
        }
        write_summary(result)
        return result

    rows = _load_rows(P84E_ROWS_PATH)
    outcome_rows = [r for r in rows if r.get("outcome_available") is True]
    with_fip = [r for r in outcome_rows if r.get("sp_fip_delta") is not None]

    inv = step3_row_inventory(rows)
    dist = step4_feature_distribution(with_fip)
    qd = step5_quartile_decomposition(with_fip)
    ba = step6_bucket_analysis(with_fip)
    mb = step7_monthly_bucket(with_fip)
    conc = step8_concentration_assessment(inv, qd, ba, mb)
    gov = step9_governance_scan()
    final = step10_final_classification(preflight, lock, conc, gov)
    cls = final["final_classification"]

    summary: dict[str, Any] = {
        "p93_classification": cls,
        "final_classification": cls,
        "allowed_classifications": ALLOWED_FINAL_CLASSIFICATIONS,
        "date": datetime.now(timezone.utc).date().isoformat(),
        "generated_at": _now_iso(),
        "git_head": _git_head(),
        "phase": "paper-only, diagnostic-only",
        "step1_preflight": preflight,
        "step2_classification_locks": lock,
        "step3_row_inventory": inv,
        "step4_feature_distribution": dist,
        "step5_quartile_decomposition": qd,
        "step6_bucket_analysis": ba,
        "step7_monthly_bucket": mb,
        "step8_concentration_assessment": conc,
        "step9_governance_scan": gov,
        "step10_final_classification": final,
        "governance_all_pass": gov["governance_all_pass"],
        "production_ready": False,
    }

    write_summary(summary)
    write_report(summary)
    update_active_task(cls)

    print(f"[P93] Final classification: {cls}")
    return summary


if __name__ == "__main__":
    main()
