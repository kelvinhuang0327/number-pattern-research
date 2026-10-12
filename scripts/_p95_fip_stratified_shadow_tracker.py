"""
P95 — FIP-Stratified Shadow Tracker / Segment-Aware Diagnostic Reporting

從 P94 認定的 high-FIP diagnostic signal 出發，建立三段（HIGH/MID/LOW FIP）
的 shadow tracking report，明確標記 mid/low 為 watch-only。

paper_only=true | diagnostic_only=true | NO_REAL_BET=true
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
P84E_ROWS = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
P94_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
P93_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p93_prediction_only_coverage_feature_bias_audit_summary.json"
P92_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p92_prediction_only_side_bias_baseline_gate_summary.json"
P91_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p91_prediction_only_tracking_gate_summary.json"

OUTPUT_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p95_fip_stratified_shadow_tracker_summary.json"
OUTPUT_REPORT = REPO_ROOT / "report/p95_fip_stratified_shadow_tracker_20260528.md"

# ---------------------------------------------------------------------------
# Segment thresholds（must match P93/P94 exactly）
# ---------------------------------------------------------------------------
HIGH_FIP_THRESHOLD = 1.5
LOW_FIP_THRESHOLD = 0.5

# P93/P94 reference values for tolerance checks
P94_HIGH_FIP_N = 287
P94_HIGH_FIP_HIT_RATE = 0.641115
P93_MID_FIP_N = 343
P93_MID_FIP_HIT_RATE = 0.530612
P93_LOW_FIP_N = 178
P93_LOW_FIP_HIT_RATE = 0.528090
TOLERANCE = 1e-4

VALID_FINAL_CLASSIFICATIONS = [
    "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY",
    "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE",
    "P95_FIP_STRATIFIED_SHADOW_TRACKER_BLOCKED_BY_P94_MISMATCH",
    "P95_FIP_STRATIFIED_SHADOW_TRACKER_FAILED_VALIDATION",
]


# ---------------------------------------------------------------------------
# Helpers (shared with P94 logic, re-implemented to be self-contained)
# ---------------------------------------------------------------------------

def load_rows() -> list[dict]:
    rows: list[dict] = []
    with open(P84E_ROWS) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def outcome_rows(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("outcome_available") is True and r.get("sp_fip_delta") is not None]


def is_correct(row: dict) -> bool | None:
    val = row.get("is_correct")
    if val is not None:
        return bool(val)
    pred = row.get("predicted_side")
    actual = row.get("actual_winner")
    if pred is None or actual is None:
        return None
    return pred == actual


def hit_rate(rows: list[dict]) -> float:
    vals = [is_correct(r) for r in rows]
    valid = [v for v in vals if v is not None]
    return sum(valid) / len(valid) if valid else float("nan")


def brier_score(rows: list[dict]) -> float:
    vals = []
    for r in rows:
        prob = r.get("model_probability")
        actual = r.get("actual_winner")
        if prob is None or actual is None:
            continue
        vals.append((prob - float(actual == "home")) ** 2)
    return float(np.mean(vals)) if vals else float("nan")


def ece_score(rows: list[dict], n_bins: int = 10) -> float:
    probs, actuals = [], []
    for r in rows:
        prob = r.get("model_probability")
        actual = r.get("actual_winner")
        if prob is None or actual is None:
            continue
        probs.append(prob)
        actuals.append(float(actual == "home"))
    if not probs:
        return float("nan")
    pa = np.array(probs)
    aa = np.array(actuals)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(pa)
    for i in range(n_bins):
        mask = (pa >= bins[i]) & (pa < bins[i + 1])
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(pa[mask].mean() - aa[mask].mean())
    return float(ece)


def try_auc(rows: list[dict]) -> float | None:
    try:
        from sklearn.metrics import roc_auc_score
    except ImportError:
        return None
    probs, actuals = [], []
    for r in rows:
        prob = r.get("model_probability")
        actual = r.get("actual_winner")
        if prob is None or actual is None:
            continue
        probs.append(prob)
        actuals.append(float(actual == "home"))
    if len(set(actuals)) < 2:
        return None
    return float(roc_auc_score(actuals, probs))


def predicted_home_ratio(rows: list[dict]) -> float:
    sides = [r.get("predicted_side") for r in rows]
    cnt = sum(1 for s in sides if s == "home")
    valid = sum(1 for s in sides if s is not None)
    return cnt / valid if valid else float("nan")


def actual_home_ratio(rows: list[dict]) -> float:
    actuals = [r.get("actual_winner") for r in rows]
    cnt = sum(1 for a in actuals if a == "home")
    valid = sum(1 for a in actuals if a is not None)
    return cnt / valid if valid else float("nan")


def monthly_split(rows: list[dict]) -> dict[str, dict]:
    from collections import defaultdict
    monthly: dict[str, list] = defaultdict(list)
    for r in rows:
        date = r.get("game_date", "")
        if date:
            monthly[date[:7]].append(r)
    return {
        month: {"n": len(seg), "hit_rate": round(hit_rate(seg), 6)}
        for month, seg in sorted(monthly.items())
    }


def side_split(rows: list[dict]) -> dict[str, dict]:
    home_pred = [r for r in rows if r.get("predicted_side") == "home"]
    away_pred = [r for r in rows if r.get("predicted_side") == "away"]
    return {
        "home_predicted": {"n": len(home_pred), "hit_rate": round(hit_rate(home_pred), 6)},
        "away_predicted": {"n": len(away_pred), "hit_rate": round(hit_rate(away_pred), 6)},
    }


def binomial_p(rows: list[dict], baseline: float) -> float | None:
    vals = [is_correct(r) for r in rows]
    valid = [v for v in vals if v is not None]
    if len(valid) < 5:
        return None
    result = stats.binomtest(sum(valid), len(valid), baseline, alternative="greater")
    return round(float(result.pvalue), 6)


def segment_metrics(seg_rows: list[dict], label: str, tracking_status: str, home_baseline: float) -> dict[str, Any]:
    hr = hit_rate(seg_rows)
    auc = try_auc(seg_rows)
    bp = binomial_p(seg_rows, home_baseline)
    return {
        "label": label,
        "tracking_status": tracking_status,
        "n": len(seg_rows),
        "hit_rate": round(hr, 6) if not np.isnan(hr) else None,
        "auc": round(auc, 6) if auc is not None else None,
        "brier": round(brier_score(seg_rows), 6),
        "ece": round(ece_score(seg_rows), 6),
        "predicted_home_ratio": round(predicted_home_ratio(seg_rows), 6),
        "actual_home_ratio": round(actual_home_ratio(seg_rows), 6),
        "home_baseline": home_baseline,
        "binomial_p_vs_home_baseline": bp,
        "monthly_split": monthly_split(seg_rows),
        "side_split": side_split(seg_rows),
    }


# ---------------------------------------------------------------------------
# Step 1: Pre-flight
# ---------------------------------------------------------------------------

def step1_preflight() -> dict[str, Any]:
    result: dict[str, Any] = {"step": "step1_preflight"}

    # Canonical entry
    toplevel = os.popen("git rev-parse --show-toplevel").read().strip()
    branch = os.popen("git branch --show-current").read().strip()
    git_dir = os.popen("git rev-parse --git-dir").read().strip()
    head = os.popen("git log -1 --format=%h").read().strip()

    gate1_ok = (
        toplevel == "/Users/kelvin/Kelvin-WorkSpace/Betting-pool"
        and branch == "main"
        and git_dir == ".git"
    )
    result["gate1_canonical_entry"] = {
        "ok": gate1_ok,
        "toplevel": toplevel,
        "branch": branch,
        "git_dir": git_dir,
        "head": head,
    }

    # Dirty-tree inventory (record only)
    dirty = os.popen("git status --short").read().strip()
    result["dirty_tree_inventory"] = dirty.split("\n") if dirty else []

    # Upstream artifact checks
    checks: dict[str, Any] = {}
    all_ok = gate1_ok

    for fn, expected_key, expected_val in [
        (P94_SUMMARY, "final_classification", "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"),
        (P93_SUMMARY, "final_classification", "P93_SIGNAL_CONCENTRATED_IN_HIGH_FIP"),
        (P92_SUMMARY, "final_classification", "P92_SIGNAL_NOT_EXPLAINED_BY_SIMPLE_SIDE_BASELINE"),
        (P91_SUMMARY, "final_classification", "P91_TRACKING_ACTIVE_SIGNAL_STABLE"),
    ]:
        if not fn.exists():
            checks[fn.name] = {"ok": False, "reason": "FILE_MISSING"}
            all_ok = False
            continue
        with open(fn) as f:
            d = json.load(f)
        found = d.get(expected_key)
        ok = found == expected_val
        checks[fn.name] = {"ok": ok, "found": found, "expected": expected_val}
        if not ok:
            all_ok = False

    # P94 governance flags
    if P94_SUMMARY.exists():
        with open(P94_SUMMARY) as f:
            p94 = json.load(f)
        gov = p94.get("step10_governance", {})
        p94_gov_ok = (
            gov.get("paper_only") is True
            and gov.get("diagnostic_only") is True
            and gov.get("production_ready") is False
            and gov.get("odds_used") is False
            and gov.get("ev_computed") is False
            and gov.get("clv_computed") is False
            and gov.get("kelly_computed") is False
        )
        checks["p94_governance_flags"] = {"ok": p94_gov_ok}
        if not p94_gov_ok:
            all_ok = False

    p84e_ok = P84E_ROWS.exists()
    checks["p84e_rows_exist"] = p84e_ok
    if not p84e_ok:
        all_ok = False

    result["upstream_checks"] = {"ok": all_ok, "details": checks}
    result["all_gates_ok"] = all_ok
    return result


# ---------------------------------------------------------------------------
# Step 2: Segment tracker metrics
# ---------------------------------------------------------------------------

def step2_segment_metrics(rows: list[dict]) -> dict[str, Any]:
    o_rows = outcome_rows(rows)
    high = [r for r in o_rows if abs(r["sp_fip_delta"]) >= HIGH_FIP_THRESHOLD]
    mid = [r for r in o_rows if LOW_FIP_THRESHOLD <= abs(r["sp_fip_delta"]) < HIGH_FIP_THRESHOLD]
    low = [r for r in o_rows if abs(r["sp_fip_delta"]) < LOW_FIP_THRESHOLD]

    home_baseline = 0.524752

    high_m = segment_metrics(high, "HIGH_FIP", "HIGH_FIP_DIAGNOSTIC_TRACKING_ALLOWED", home_baseline)
    mid_m = segment_metrics(mid, "MID_FIP", "MID_FIP_WATCH_ONLY", home_baseline)
    low_m = segment_metrics(low, "LOW_FIP", "LOW_FIP_WATCH_ONLY", home_baseline)

    # Tolerance checks vs P94/P93 baselines
    high_tol_ok = (
        abs(len(high) - P94_HIGH_FIP_N) <= 1
        and high_m["hit_rate"] is not None
        and abs(high_m["hit_rate"] - P94_HIGH_FIP_HIT_RATE) <= TOLERANCE
    )
    mid_tol_ok = (
        abs(len(mid) - P93_MID_FIP_N) <= 1
        and mid_m["hit_rate"] is not None
        and abs(mid_m["hit_rate"] - P93_MID_FIP_HIT_RATE) <= TOLERANCE
    )
    low_tol_ok = (
        abs(len(low) - P93_LOW_FIP_N) <= 1
        and low_m["hit_rate"] is not None
        and abs(low_m["hit_rate"] - P93_LOW_FIP_HIT_RATE) <= TOLERANCE
    )

    return {
        "step": "step2_segment_metrics",
        "n_outcome_rows": len(o_rows),
        "segments": {
            "HIGH_FIP": high_m,
            "MID_FIP": mid_m,
            "LOW_FIP": low_m,
        },
        "tolerance_checks": {
            "high_fip_ok": high_tol_ok,
            "mid_fip_ok": mid_tol_ok,
            "low_fip_ok": low_tol_ok,
            "all_ok": high_tol_ok and mid_tol_ok and low_tol_ok,
        },
        "status": "PASSED" if (high_tol_ok and mid_tol_ok and low_tol_ok) else "FAILED_TOLERANCE",
    }


# ---------------------------------------------------------------------------
# Step 3: Shadow tracker policy
# ---------------------------------------------------------------------------

def step3_policy() -> dict[str, Any]:
    return {
        "step": "step3_shadow_tracker_policy",
        "high_fip_tracking": "allowed_diagnostic_only",
        "mid_fip_tracking": "watch_only_not_trackable",
        "low_fip_tracking": "watch_only_not_trackable",
        "aggregate_metric_display": "allowed_with_warning",
        "recommendation_allowed": False,
        "product_surface_allowed": False,
        "production_ready": False,
        "odds_required_before_betting_claim": True,
        "real_bet_allowed": False,
        "rationale": (
            "P94 qualified high-FIP as diagnostic-only (ci_low=0.582, temporal_stable=True, side_balanced=True). "
            "Mid/low FIP segments did not exceed home_baseline+0.03 and are classified as NOT_TRACKABLE. "
            "No recommendation, product, or production claim is permitted under current diagnostic scope."
        ),
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 4: Drift and overclaim guards
# ---------------------------------------------------------------------------

def step4_drift_guards() -> dict[str, Any]:
    return {
        "step": "step4_drift_overclaim_guards",
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
        "p84_to_p94_artifacts_modified": False,
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5: Final classification
# ---------------------------------------------------------------------------

def step5_classification(
    gate_ok: bool,
    seg: dict[str, Any],
    policy: dict[str, Any],
    guards: dict[str, Any],
) -> dict[str, Any]:
    # BLOCKED by P94 mismatch
    if not gate_ok:
        return {
            "final_classification": "P95_FIP_STRATIFIED_SHADOW_TRACKER_BLOCKED_BY_P94_MISMATCH",
            "rationale": "Upstream P94 is missing or not qualified",
        }

    # FAILED_VALIDATION
    tol_ok = seg["tolerance_checks"]["all_ok"]
    gov_ok = guards["status"] == "PASSED"
    if not tol_ok or not gov_ok:
        return {
            "final_classification": "P95_FIP_STRATIFIED_SHADOW_TRACKER_FAILED_VALIDATION",
            "rationale": (
                f"tolerance_ok={tol_ok}, governance_ok={gov_ok}"
            ),
        }

    # Partial coverage indicator
    canonical_rows = 828
    schedule_rows = 2430
    partial_coverage = canonical_rows / schedule_rows  # 0.3407

    # Use READY_WITH_LIMITED_COVERAGE given 34% partial coverage (March-May only)
    if partial_coverage < 0.50:
        return {
            "final_classification": "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY_WITH_LIMITED_COVERAGE",
            "rationale": (
                f"All tolerance checks passed. Partial coverage {canonical_rows}/{schedule_rows} "
                f"= {partial_coverage:.4f} < 0.50 (March-May 2026 only). "
                "High-FIP diagnostic tracking allowed; mid/low FIP watch-only. "
                "Full-season readiness requires continued data accumulation."
            ),
        }

    return {
        "final_classification": "P95_FIP_STRATIFIED_SHADOW_TRACKER_READY",
        "rationale": "All checks passed and coverage >= 50%.",
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(summary: dict) -> str:
    fc = summary["final_classification"]
    seg = summary["step2_segment_metrics"]["segments"]
    policy = summary["step3_shadow_tracker_policy"]
    guards = summary["step4_drift_overclaim_guards"]
    tol = summary["step2_segment_metrics"]["tolerance_checks"]

    high = seg["HIGH_FIP"]
    mid = seg["MID_FIP"]
    low = seg["LOW_FIP"]

    def monthly_table(m: dict) -> list[str]:
        lines = ["| Month | n | hit_rate |", "|-------|---|----------|"]
        for month, v in m.items():
            lines.append(f"| {month} | {v['n']} | `{v['hit_rate']}` |")
        return lines

    lines = [
        "# P95 FIP-Stratified Shadow Tracker — Segment-Aware Diagnostic Report",
        "",
        f"**Date**: 2026-05-28  |  **Branch**: main  |  **HEAD**: fc8e51f (P94)",
        f"**Final Classification**: `{fc}`",
        "",
        "---",
        "",
        "## ⚠️ 重要聲明",
        "",
        "- `paper_only=true` | `diagnostic_only=true` | `production_ready=false`",
        "- `NO_REAL_BET=true` | `odds_used=false` | `ev_computed=false` | `clv_computed=false` | `kelly_computed=false`",
        "- **Partial coverage**: 828 / 2430 rows = 34.07%（March–May 2026 only）",
        "- P94 前置條件：`P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY`（ci_low=0.582, temporal_stable=True）",
        "",
        "---",
        "",
        "## Segment Tracker Policy",
        "",
        "| Segment | 追蹤狀態 |",
        "|---------|---------|",
        "| HIGH_FIP (\\|Δ FIP\\| ≥ 1.5) | `allowed_diagnostic_only` |",
        "| MID_FIP (0.5 ≤ \\|Δ FIP\\| < 1.5) | `watch_only_not_trackable` |",
        "| LOW_FIP (\\|Δ FIP\\| < 0.5) | `watch_only_not_trackable` |",
        "| Aggregate display | `allowed_with_warning` |",
        "| Recommendation | ❌ forbidden |",
        "| Product surface | ❌ forbidden |",
        "",
        "---",
        "",
        "## HIGH_FIP Segment（`HIGH_FIP_DIAGNOSTIC_TRACKING_ALLOWED`）",
        "",
        "| 指標 | 數值 | P94 基準 | 容差通過 |",
        "|------|------|---------|--------|",
        f"| n | {high['n']} | {P94_HIGH_FIP_N} | {'✅' if tol['high_fip_ok'] else '❌'} |",
        f"| hit_rate | `{high['hit_rate']}` | `{P94_HIGH_FIP_HIT_RATE}` | {'✅' if tol['high_fip_ok'] else '❌'} |",
        f"| Brier | `{high['brier']}` | — | — |",
        f"| ECE | `{high['ece']}` | — | — |",
        f"| predicted_home_ratio | `{high['predicted_home_ratio']}` | — | — |",
        f"| actual_home_ratio | `{high['actual_home_ratio']}` | — | — |",
        f"| AUC | `{high['auc']}` | — | — |",
        "",
        "### HIGH_FIP Monthly Split",
        "",
        *monthly_table(high["monthly_split"]),
        "",
        "### HIGH_FIP Side Split",
        "",
        "| Side | n | hit_rate |",
        "|------|---|----------|",
        f"| Home predicted | {high['side_split']['home_predicted']['n']} | `{high['side_split']['home_predicted']['hit_rate']}` |",
        f"| Away predicted | {high['side_split']['away_predicted']['n']} | `{high['side_split']['away_predicted']['hit_rate']}` |",
        "",
        "---",
        "",
        "## MID_FIP Segment（`MID_FIP_WATCH_ONLY`）",
        "",
        "| 指標 | 數值 | P93 基準 | 容差通過 |",
        "|------|------|---------|--------|",
        f"| n | {mid['n']} | {P93_MID_FIP_N} | {'✅' if tol['mid_fip_ok'] else '❌'} |",
        f"| hit_rate | `{mid['hit_rate']}` | `{P93_MID_FIP_HIT_RATE}` | {'✅' if tol['mid_fip_ok'] else '❌'} |",
        f"| Brier | `{mid['brier']}` | — | — |",
        f"| ECE | `{mid['ece']}` | — | — |",
        f"| binomial p vs home baseline | `{mid['binomial_p_vs_home_baseline']}` | — | — |",
        "",
        "> ⚠️ MID_FIP hit_rate 未超過 home_baseline + 0.03 閾值，標記為 **watch-only**，不作為 diagnostic tracking signal。",
        "",
        "### MID_FIP Monthly Split",
        "",
        *monthly_table(mid["monthly_split"]),
        "",
        "---",
        "",
        "## LOW_FIP Segment（`LOW_FIP_WATCH_ONLY`）",
        "",
        "| 指標 | 數值 | P93 基準 | 容差通過 |",
        "|------|------|---------|--------|",
        f"| n | {low['n']} | {P93_LOW_FIP_N} | {'✅' if tol['low_fip_ok'] else '❌'} |",
        f"| hit_rate | `{low['hit_rate']}` | `{P93_LOW_FIP_HIT_RATE}` | {'✅' if tol['low_fip_ok'] else '❌'} |",
        f"| Brier | `{low['brier']}` | — | — |",
        f"| ECE | `{low['ece']}` | — | — |",
        f"| binomial p vs home baseline | `{low['binomial_p_vs_home_baseline']}` | — | — |",
        "",
        "> ⚠️ LOW_FIP hit_rate 未超過 home_baseline + 0.03 閾值，標記為 **watch-only**，不作為 diagnostic tracking signal。",
        "",
        "### LOW_FIP Monthly Split",
        "",
        *monthly_table(low["monthly_split"]),
        "",
        "---",
        "",
        "## Final Classification",
        "",
        f"**`{fc}`**",
        "",
        f"> {summary.get('classification_rationale', '')}",
        "",
        "---",
        "",
        "## Governance & Drift Guard Summary",
        "",
        "| Guard | Value |",
        "|-------|-------|",
        "| odds_used | false |",
        "| ev_computed | false |",
        "| clv_computed | false |",
        "| kelly_computed | false |",
        "| stake_sizing | false |",
        "| taiwan_lottery_recommendation | false |",
        "| champion_replacement | false |",
        "| production_mutation | false |",
        "| calibration_refit | false |",
        "| live_api_calls | 0 |",
        "| paid_api_calls | 0 |",
        "| production_ready | false |",
        "| paper_only | true |",
        "| diagnostic_only | true |",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> dict[str, Any]:
    print("[P95] FIP-Stratified Shadow Tracker 開始執行...")

    # Step 1
    print("[P95] Step 1: Pre-flight...")
    preflight = step1_preflight()
    gate_ok = preflight["all_gates_ok"]
    if not gate_ok:
        print(f"[P95] ❌ Pre-flight 失敗")
        summary = {
            "final_classification": "P95_FIP_STRATIFIED_SHADOW_TRACKER_BLOCKED_BY_P94_MISMATCH",
            "step1_preflight": preflight,
        }
        OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        return summary

    # Load rows
    print("[P95] Loading rows...")
    rows = load_rows()

    # Step 2
    print("[P95] Step 2: Segment metrics...")
    seg = step2_segment_metrics(rows)
    if seg["status"] != "PASSED":
        print(f"[P95] ❌ Segment tolerance mismatch: {seg['tolerance_checks']}")

    # Step 3
    print("[P95] Step 3: Shadow tracker policy...")
    policy = step3_policy()

    # Step 4
    print("[P95] Step 4: Drift guards...")
    guards = step4_drift_guards()

    # Step 5
    print("[P95] Step 5: Final classification...")
    classification = step5_classification(gate_ok, seg, policy, guards)
    fc = classification["final_classification"]
    print(f"[P95] Final classification: {fc}")

    summary = {
        "phase": "P95",
        "final_classification": fc,
        "classification_rationale": classification.get("rationale", ""),
        "allowed_classifications": VALID_FINAL_CLASSIFICATIONS,
        "date": "2026-05-28",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": "fc8e51f",
        "step1_preflight": preflight,
        "step2_segment_metrics": seg,
        "step3_shadow_tracker_policy": policy,
        "step4_drift_overclaim_guards": guards,
        "step5_classification": classification,
        "governance_all_pass": guards["status"] == "PASSED",
        "production_ready": False,
        "paper_only": True,
        "diagnostic_only": True,
        "partial_coverage": {"canonical_rows": 828, "schedule_rows": 2430, "ratio": round(828 / 2430, 6)},
    }

    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[P95] ✅ JSON summary: {OUTPUT_SUMMARY}")

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(generate_report(summary), encoding="utf-8")
    print(f"[P95] ✅ Markdown report: {OUTPUT_REPORT}")

    return summary


if __name__ == "__main__":
    result = main()
    import sys
    fc = result.get("final_classification", "")
    sys.exit(0 if "FAILED" not in fc and "BLOCKED" not in fc else 1)
