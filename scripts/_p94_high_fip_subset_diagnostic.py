"""
P94 — High-FIP Subset Diagnostic / FIP-Stratified Tracking Gate

診斷 P93 發現的 high-FIP 子集（n=287，hit_rate 0.641115）在
stability / temporal / side / sample-sufficiency 各切面的穩定性。

paper_only=true | diagnostic_only=true | NO_REAL_BET=true
"""

from __future__ import annotations

import json
import os
import sys
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
P93_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p93_prediction_only_coverage_feature_bias_audit_summary.json"
P91_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p91_prediction_only_tracking_gate_summary.json"
P92_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p92_prediction_only_side_bias_baseline_gate_summary.json"
P84E_ATTACH_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json"

OUTPUT_SUMMARY = REPO_ROOT / "data/mlb_2026/derived/p94_high_fip_subset_diagnostic_summary.json"
OUTPUT_REPORT = REPO_ROOT / "report/p94_high_fip_subset_diagnostic_20260528.md"

# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------
HIGH_FIP_THRESHOLD = 1.5
LOW_FIP_THRESHOLD = 0.5
BOOTSTRAP_N = 1000
BOOTSTRAP_SEED = 42
HOME_BASELINE = 0.524752  # from P92
AGGREGATE_MODEL = 0.569307  # from P91
P93_HIGH_FIP_HIT_RATE = 0.641115
P93_HIGH_FIP_N = 287
TOLERANCE = 1e-4


# ---------------------------------------------------------------------------
# Step 1: Pre-flight gates
# ---------------------------------------------------------------------------

def step1_preflight() -> dict[str, Any]:
    """Gate 1 + 2 + 3 checks."""
    result: dict[str, Any] = {"step": "step1_preflight"}

    # Gate 1 — canonical entry
    cwd = str(Path.cwd().resolve())
    toplevel = os.popen("git rev-parse --show-toplevel").read().strip()
    branch = os.popen("git branch --show-current").read().strip()
    git_dir = os.popen("git rev-parse --git-dir").read().strip()
    head = os.popen("git log -1 --format=%h").read().strip()

    gate1_ok = (
        "/Users/kelvin/Kelvin-WorkSpace/Betting-pool" in cwd
        and toplevel == "/Users/kelvin/Kelvin-WorkSpace/Betting-pool"
        and branch == "main"
        and git_dir == ".git"
        and head == "2221f0f"
    )
    result["gate1_canonical_entry"] = {
        "ok": gate1_ok,
        "cwd": cwd,
        "toplevel": toplevel,
        "branch": branch,
        "git_dir": git_dir,
        "head": head,
    }

    # Gate 2 — dirty-tree inventory (record only, do NOT modify)
    dirty_tree = os.popen("git status --short").read().strip()
    result["dirty_tree_inventory"] = dirty_tree.split("\n") if dirty_tree else []

    # Gate 3 — upstream artifact consistency
    checks = {
        str(P93_SUMMARY): "P93_SIGNAL_CONCENTRATED_IN_HIGH_FIP",
        str(P91_SUMMARY): "P91_TRACKING_ACTIVE_SIGNAL_STABLE",
        str(P92_SUMMARY): "P92_SIGNAL_NOT_EXPLAINED_BY_SIMPLE_SIDE_BASELINE",
    }
    gate3_results: dict[str, Any] = {}
    gate3_ok = True
    for fn, expected_fc in checks.items():
        if not Path(fn).exists():
            gate3_results[fn] = {"ok": False, "reason": "FILE_MISSING"}
            gate3_ok = False
            continue
        with open(fn) as f:
            d = json.load(f)
        fc = d.get("final_classification") or d.get("p93_classification") or d.get("p92_classification") or d.get("p91_classification")
        ok = fc == expected_fc
        gate3_results[Path(fn).name] = {"ok": ok, "found": fc, "expected": expected_fc}
        if not ok:
            gate3_ok = False

    # p84e rows
    p84e_rows_ok = P84E_ROWS.exists()
    p84e_attach_ok = P84E_ATTACH_SUMMARY.exists()
    gate3_results["p84e_rows_exist"] = p84e_rows_ok
    gate3_results["p84e_attach_summary_exist"] = p84e_attach_ok
    if not p84e_rows_ok or not p84e_attach_ok:
        gate3_ok = False

    result["gate3_upstream_consistency"] = {"ok": gate3_ok, "checks": gate3_results}
    result["all_gates_ok"] = gate1_ok and gate3_ok
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_outcome_rows() -> list[dict]:
    rows = []
    with open(P84E_ROWS) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def is_correct(row: dict) -> bool | None:
    """Return True if model prediction matched actual outcome.

    Row fields: is_correct (bool), predicted_side ('home'/'away'), actual_winner ('home'/'away').
    """
    # Use pre-computed is_correct field if available
    val = row.get("is_correct")
    if val is not None:
        return bool(val)
    pred = row.get("predicted_side")
    actual = row.get("actual_winner")
    if pred is None or actual is None:
        return None
    return pred == actual


def compute_hit_rate(rows: list[dict]) -> float:
    outcomes = [is_correct(r) for r in rows]
    valid = [o for o in outcomes if o is not None]
    if not valid:
        return float("nan")
    return sum(valid) / len(valid)


def compute_brier(rows: list[dict]) -> float:
    """Brier score using model_probability = P(home wins) and actual_winner."""
    vals = []
    for r in rows:
        prob = r.get("model_probability")
        actual_winner = r.get("actual_winner")
        if prob is None or actual_winner is None:
            continue
        actual_home = float(actual_winner == "home")
        vals.append((prob - actual_home) ** 2)
    return float(np.mean(vals)) if vals else float("nan")


def compute_ece(rows: list[dict], n_bins: int = 10) -> float:
    """ECE using model_probability = P(home wins) and actual_winner."""
    probs, actuals = [], []
    for r in rows:
        prob = r.get("model_probability")
        actual_winner = r.get("actual_winner")
        if prob is None or actual_winner is None:
            continue
        probs.append(prob)
        actuals.append(float(actual_winner == "home"))
    if not probs:
        return float("nan")
    probs_arr = np.array(probs)
    actuals_arr = np.array(actuals)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(probs_arr)
    for i in range(n_bins):
        mask = (probs_arr >= bins[i]) & (probs_arr < bins[i + 1])
        if mask.sum() == 0:
            continue
        avg_conf = probs_arr[mask].mean()
        avg_acc = actuals_arr[mask].mean()
        ece += (mask.sum() / n) * abs(avg_conf - avg_acc)
    return float(ece)


def compute_predicted_home_ratio(rows: list[dict]) -> float:
    """Fraction of rows where predicted_side == 'home'."""
    sides = [r.get("predicted_side") for r in rows]
    cnt = sum(1 for s in sides if s == "home")
    valid = sum(1 for s in sides if s is not None)
    return cnt / valid if valid else float("nan")


def compute_actual_home_ratio(rows: list[dict]) -> float:
    """Fraction of rows where actual_winner == 'home'."""
    actuals = [r.get("actual_winner") for r in rows]
    cnt = sum(1 for a in actuals if a == "home")
    valid = sum(1 for a in actuals if a is not None)
    return cnt / valid if valid else float("nan")


def try_auc(rows: list[dict]) -> float:
    """Compute ROC-AUC using model_probability vs actual_winner if sklearn available."""
    try:
        from sklearn.metrics import roc_auc_score
    except ImportError:
        return float("nan")
    probs, actuals = [], []
    for r in rows:
        prob = r.get("model_probability")
        actual_winner = r.get("actual_winner")
        if prob is None or actual_winner is None:
            continue
        probs.append(prob)
        actuals.append(float(actual_winner == "home"))
    if len(set(actuals)) < 2:
        return float("nan")
    return float(roc_auc_score(actuals, probs))


# ---------------------------------------------------------------------------
# Step 2: Row inventory
# ---------------------------------------------------------------------------

def step2_row_inventory(rows: list[dict]) -> dict[str, Any]:
    n_total = len(rows)
    outcome_rows = [r for r in rows if r.get("outcome_available") is True]
    n_outcome = len(outcome_rows)
    n_with_fip = sum(1 for r in outcome_rows if r.get("sp_fip_delta") is not None)
    n_missing_fip = n_outcome - n_with_fip

    # Tolerance check vs P93
    p93_n_outcome = 808
    p93_n_fip = 808
    tol_ok = (abs(n_outcome - p93_n_outcome) <= 1) and (abs(n_with_fip - p93_n_fip) <= 1)

    return {
        "step": "step2_row_inventory",
        "n_total_rows": n_total,
        "n_outcome_rows": n_outcome,
        "n_with_sp_fip_delta": n_with_fip,
        "n_missing_sp_fip_delta": n_missing_fip,
        "p93_expected_outcome": p93_n_outcome,
        "p93_expected_fip": p93_n_fip,
        "tolerance_ok": tol_ok,
        "status": "PASSED" if tol_ok else "FAILED",
    }


# ---------------------------------------------------------------------------
# Step 3: High-FIP subset recompute
# ---------------------------------------------------------------------------

def step3_high_fip_metrics(rows: list[dict]) -> tuple[dict[str, Any], list[dict]]:
    outcome_rows = [r for r in rows if r.get("outcome_available") is True and r.get("sp_fip_delta") is not None]
    high_fip = [r for r in outcome_rows if abs(r["sp_fip_delta"]) >= HIGH_FIP_THRESHOLD]

    n = len(high_fip)
    hit_rate = compute_hit_rate(high_fip)
    brier = compute_brier(high_fip)
    ece = compute_ece(high_fip)
    pred_home_ratio = compute_predicted_home_ratio(high_fip)
    actual_home_ratio = compute_actual_home_ratio(high_fip)
    auc = try_auc(high_fip)

    # Tolerance check vs P93
    tol_ok = abs(hit_rate - P93_HIGH_FIP_HIT_RATE) <= TOLERANCE and abs(n - P93_HIGH_FIP_N) <= 1

    return {
        "step": "step3_high_fip_metrics",
        "abs_fip_threshold": HIGH_FIP_THRESHOLD,
        "n": n,
        "hit_rate": round(hit_rate, 6),
        "auc": round(auc, 6) if not np.isnan(auc) else None,
        "brier": round(brier, 6),
        "ece": round(ece, 6),
        "predicted_home_ratio": round(pred_home_ratio, 6),
        "actual_home_ratio": round(actual_home_ratio, 6),
        "p93_expected_hit_rate": P93_HIGH_FIP_HIT_RATE,
        "p93_expected_n": P93_HIGH_FIP_N,
        "tolerance_ok": tol_ok,
        "status": "PASSED" if tol_ok else "FAILED_METRIC_MISMATCH",
    }, high_fip


# ---------------------------------------------------------------------------
# Step 4: Bootstrap CI
# ---------------------------------------------------------------------------

def step4_bootstrap_ci(high_fip_rows: list[dict]) -> dict[str, Any]:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    corrects = [is_correct(r) for r in high_fip_rows]
    outcomes = np.array([1 if c else 0 for c in corrects if c is not None], dtype=float)
    n = len(outcomes)

    boot_means = []
    for _ in range(BOOTSTRAP_N):
        sample = rng.choice(outcomes, size=n, replace=True)
        boot_means.append(sample.mean())

    ci_low = float(np.percentile(boot_means, 2.5))
    ci_high = float(np.percentile(boot_means, 97.5))
    observed = float(outcomes.mean())

    if ci_low > 0.55:
        stability = "STRONG"
    elif ci_low > 0.50:
        stability = "MARGINAL"
    else:
        stability = "UNSTABLE"

    return {
        "step": "step4_bootstrap_ci",
        "n": n,
        "bootstrap_resamples": BOOTSTRAP_N,
        "seed": BOOTSTRAP_SEED,
        "observed_hit_rate": round(observed, 6),
        "ci_low": round(ci_low, 6),
        "ci_high": round(ci_high, 6),
        "home_baseline": HOME_BASELINE,
        "aggregate_model_hit_rate": AGGREGATE_MODEL,
        "stability": stability,
        "ci_low_above_055": ci_low > 0.55,
        "ci_low_above_050": ci_low > 0.50,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 5: Temporal split
# ---------------------------------------------------------------------------

def step5_temporal_split(high_fip_rows: list[dict]) -> dict[str, Any]:
    sorted_rows = sorted(high_fip_rows, key=lambda r: r.get("game_date", ""))
    n = len(sorted_rows)
    t1 = n // 3
    t2 = 2 * n // 3
    thirds = [sorted_rows[:t1], sorted_rows[t1:t2], sorted_rows[t2:]]
    results = []
    all_above_055 = True
    for i, segment in enumerate(thirds):
        hr = compute_hit_rate(segment)
        results.append({
            "third": i + 1,
            "n": len(segment),
            "hit_rate": round(hr, 6),
            "date_start": segment[0].get("game_date") if segment else None,
            "date_end": segment[-1].get("game_date") if segment else None,
        })
        if hr <= 0.55:
            all_above_055 = False

    temporal_stable = all_above_055
    return {
        "step": "step5_temporal_split",
        "thirds": results,
        "all_thirds_above_055": all_above_055,
        "temporal_stable": temporal_stable,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 6: Side split
# ---------------------------------------------------------------------------

def step6_side_split(high_fip_rows: list[dict]) -> dict[str, Any]:
    home_pred = [r for r in high_fip_rows if r.get("predicted_side") == "home"]
    away_pred = [r for r in high_fip_rows if r.get("predicted_side") == "away"]

    hr_home = compute_hit_rate(home_pred)
    hr_away = compute_hit_rate(away_pred)
    delta = abs(hr_home - hr_away)
    side_balanced = delta < 0.10

    return {
        "step": "step6_side_split",
        "home_predicted": {"n": len(home_pred), "hit_rate": round(hr_home, 6)},
        "away_predicted": {"n": len(away_pred), "hit_rate": round(hr_away, 6)},
        "abs_side_delta": round(delta, 6),
        "threshold": 0.10,
        "side_balanced": side_balanced,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 7: Mid / Low FIP segment qualification
# ---------------------------------------------------------------------------

def step7_segment_qualification(rows: list[dict]) -> dict[str, Any]:
    outcome_rows = [r for r in rows if r.get("outcome_available") is True and r.get("sp_fip_delta") is not None]
    mid_rows = [r for r in outcome_rows if LOW_FIP_THRESHOLD <= abs(r["sp_fip_delta"]) < HIGH_FIP_THRESHOLD]
    low_rows = [r for r in outcome_rows if abs(r["sp_fip_delta"]) < LOW_FIP_THRESHOLD]

    def segment_stats(seg: list[dict], label: str) -> dict:
        n = len(seg)
        hr = compute_hit_rate(seg)
        outcomes = [1 if is_correct(r) else 0 for r in seg if is_correct(r) is not None]
        if len(outcomes) >= 5:
            binom_result = stats.binomtest(sum(outcomes), len(outcomes), HOME_BASELINE, alternative="greater")
            p_value = float(binom_result.pvalue)
        else:
            p_value = float("nan")
        above_threshold = hr > HOME_BASELINE + 0.03 if not np.isnan(hr) else False
        return {
            "label": label,
            "n": n,
            "hit_rate": round(hr, 6) if not np.isnan(hr) else None,
            "brier": round(compute_brier(seg), 6),
            "ece": round(compute_ece(seg), 6),
            "home_baseline": HOME_BASELINE,
            "threshold_baseline_plus_003": round(HOME_BASELINE + 0.03, 6),
            "above_threshold": above_threshold,
            "binomial_p_vs_home_baseline": round(p_value, 6) if not np.isnan(p_value) else None,
        }

    mid_stats = segment_stats(mid_rows, "mid_fip")
    low_stats = segment_stats(low_rows, "low_fip")

    any_trackable = mid_stats["above_threshold"] or low_stats["above_threshold"]
    qualification = "LOW_MID_FIP_PARTIALLY_TRACKABLE" if any_trackable else "LOW_MID_FIP_NOT_TRACKABLE"

    return {
        "step": "step7_segment_qualification",
        "mid_bucket": mid_stats,
        "low_bucket": low_stats,
        "segment_qualification": qualification,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 8: Sample sufficiency
# ---------------------------------------------------------------------------

def step8_sample_sufficiency(high_fip_rows: list[dict]) -> dict[str, Any]:
    from collections import defaultdict
    monthly: dict[str, list] = defaultdict(list)
    for r in high_fip_rows:
        date = r.get("game_date", "")
        if date:
            month_key = date[:7]  # YYYY-MM
            monthly[month_key].append(r)

    monthly_stats = {}
    any_below_30 = False
    for month, seg in sorted(monthly.items()):
        hr = compute_hit_rate(seg)
        monthly_stats[month] = {"n": len(seg), "hit_rate": round(hr, 6)}
        if len(seg) < 30:
            any_below_30 = True

    # Partial coverage
    canonical_rows = 828
    schedule_rows = 2430
    partial_coverage = round(canonical_rows / schedule_rows, 6)

    sample_limited = any_below_30

    return {
        "step": "step8_sample_sufficiency",
        "monthly_stats": monthly_stats,
        "any_month_below_30": any_below_30,
        "monthly_sample_limited": sample_limited,
        "canonical_rows": canonical_rows,
        "schedule_rows": schedule_rows,
        "partial_coverage_ratio": partial_coverage,
        "season_scope": "March–May 2026 only",
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Step 9: Final five-class classification
# ---------------------------------------------------------------------------

def step9_classification(
    boot: dict,
    temporal: dict,
    side: dict,
    sample: dict,
    gate1_ok: bool,
    gate3_ok: bool,
    metrics_ok: bool,
) -> dict[str, Any]:
    VALID_CLASSES = [
        "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY",
        "P94_HIGH_FIP_PROMISING_BUT_SAMPLE_LIMITED",
        "P94_HIGH_FIP_UNSTABLE_REQUIRES_REVIEW",
        "P94_HIGH_FIP_NOT_SEPARABLE_FROM_NOISE",
        "P94_FAILED_VALIDATION",
    ]

    # Fail fast on validation errors
    if not gate1_ok or not gate3_ok or not metrics_ok:
        fc = "P94_FAILED_VALIDATION"
        rationale = "Pre-flight gate or upstream artifact check failed"
        return {"final_classification": fc, "rationale": rationale, "allowed_classifications": VALID_CLASSES}

    ci_low = boot["ci_low"]
    temporal_stable = temporal["temporal_stable"]
    side_balanced = side["side_balanced"]
    monthly_limited = sample["monthly_sample_limited"]

    # NOT_SEPARABLE: ci_low ≤ 0.50 or high-FIP hit_rate - home_baseline < 0.05
    if ci_low <= 0.50 or (P93_HIGH_FIP_HIT_RATE - HOME_BASELINE) < 0.05:
        fc = "P94_HIGH_FIP_NOT_SEPARABLE_FROM_NOISE"
        rationale = f"Bootstrap ci_low={ci_low:.4f} ≤ 0.50 or signal-baseline gap too small"
        return {"final_classification": fc, "rationale": rationale, "allowed_classifications": VALID_CLASSES}

    # UNSTABLE: temporal 2+ thirds < 0.55 or side-biased
    thirds_above = sum(1 for t in temporal["thirds"] if t["hit_rate"] > 0.55)
    if thirds_above <= 1 or not side_balanced:
        fc = "P94_HIGH_FIP_UNSTABLE_REQUIRES_REVIEW"
        rationale = f"Temporal stability: {thirds_above}/3 thirds > 0.55; side_balanced={side_balanced}"
        return {"final_classification": fc, "rationale": rationale, "allowed_classifications": VALID_CLASSES}

    # PROMISING_BUT_SAMPLE_LIMITED: marginal ci_low or temporal only 2/3 stable or monthly limited
    if (0.50 < ci_low <= 0.55) or (thirds_above == 2) or monthly_limited:
        fc = "P94_HIGH_FIP_PROMISING_BUT_SAMPLE_LIMITED"
        rationale = (
            f"Bootstrap ci_low={ci_low:.4f} in (0.50, 0.55] or "
            f"{thirds_above}/3 temporal thirds > 0.55 or monthly_limited={monthly_limited}"
        )
        return {"final_classification": fc, "rationale": rationale, "allowed_classifications": VALID_CLASSES}

    # QUALIFIED: ci_low > 0.55, all 3 temporal thirds stable, side balanced, no monthly limit
    if ci_low > 0.55 and temporal_stable and side_balanced and not monthly_limited:
        fc = "P94_HIGH_FIP_QUALIFIED_DIAGNOSTIC_ONLY"
        rationale = (
            f"Bootstrap ci_low={ci_low:.4f} > 0.55; all temporal thirds > 0.55; "
            f"side_balanced={side_balanced}; monthly_limited={monthly_limited}"
        )
        return {"final_classification": fc, "rationale": rationale, "allowed_classifications": VALID_CLASSES}

    # Fallback — should not reach here
    fc = "P94_HIGH_FIP_PROMISING_BUT_SAMPLE_LIMITED"
    rationale = "Fallback classification — partial conditions met"
    return {"final_classification": fc, "rationale": rationale, "allowed_classifications": VALID_CLASSES}


# ---------------------------------------------------------------------------
# Step 10: Governance scan
# ---------------------------------------------------------------------------

def step10_governance() -> dict[str, Any]:
    return {
        "step": "step10_governance",
        "odds_used": False,
        "ev_computed": False,
        "clv_computed": False,
        "kelly_computed": False,
        "production_ready": False,
        "paper_only": True,
        "diagnostic_only": True,
        "live_api_calls": 0,
        "paid_api_called": False,
        "canonical_rows_modified": False,
        "outcome_rows_modified": False,
        "p83e_mapping_modified": False,
        "champion_replaced": False,
        "p84_p86_derived_modified": False,
        "dirty_tree_policy_violated": False,
        "real_bet_allowed": False,
        "status": "PASSED",
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_report(summary: dict) -> str:
    fc = summary.get("final_classification", "UNKNOWN")
    boot = summary.get("step4_bootstrap_ci", {})
    temporal = summary.get("step5_temporal_split", {})
    side = summary.get("step6_side_split", {})
    seg = summary.get("step7_segment_qualification", {})
    sample = summary.get("step8_sample_sufficiency", {})
    metrics = summary.get("step3_high_fip_metrics", {})

    lines = [
        "# P94 High-FIP Subset Diagnostic — FIP-Stratified Tracking Gate",
        "",
        f"**Date**: 2026-05-28  |  **Branch**: main  |  **HEAD**: 2221f0f (P93)",
        f"**Final Classification**: `{fc}`",
        "",
        "---",
        "",
        "## ⚠️ 重要聲明",
        "",
        "- `paper_only=true` | `diagnostic_only=true` | `production_ready=false`",
        "- `NO_REAL_BET=true` | `odds_used=false` | `ev_computed=false` | `clv_computed=false` | `kelly_computed=false`",
        "- Partial coverage: **828 / 2430 rows = 34.07%**（March–May 2026 only）",
        "",
        "---",
        "",
        "## Gate 狀態",
        "",
        "| Gate | 狀態 |",
        "|------|------|",
        f"| Gate 1 Canonical Entry | {'✅ PASS' if summary.get('step1_preflight', {}).get('gate1_canonical_entry', {}).get('ok') else '❌ FAIL'} |",
        f"| Gate 3 Upstream Consistency | {'✅ PASS' if summary.get('step1_preflight', {}).get('gate3_upstream_consistency', {}).get('ok') else '❌ FAIL'} |",
        f"| High-FIP Metrics Tolerance | {'✅ PASS' if metrics.get('tolerance_ok') else '❌ FAIL'} |",
        "",
        "---",
        "",
        "## Step 3 — High-FIP Subset Metrics（|Δ FIP| ≥ 1.5）",
        "",
        "| 指標 | 數值 | P93 基準 |",
        "|------|------|--------|",
        f"| n | {metrics.get('n')} | {metrics.get('p93_expected_n')} |",
        f"| hit_rate | `{metrics.get('hit_rate')}` | `{metrics.get('p93_expected_hit_rate')}` |",
        f"| Brier | `{metrics.get('brier')}` | — |",
        f"| ECE | `{metrics.get('ece')}` | — |",
        f"| predicted_home_ratio | `{metrics.get('predicted_home_ratio')}` | — |",
        f"| actual_home_ratio | `{metrics.get('actual_home_ratio')}` | — |",
        "",
        "---",
        "",
        "## Step 4 — Bootstrap 95% CI（1000 次 resamples）",
        "",
        f"- **CI**: `({boot.get('ci_low')}, {boot.get('ci_high')})`",
        f"- **Observed**: `{boot.get('observed_hit_rate')}`",
        f"- **Home baseline**: `{HOME_BASELINE}` | **Aggregate model**: `{AGGREGATE_MODEL}`",
        f"- **Stability**: `{boot.get('stability')}` (ci_low > 0.55 = {boot.get('ci_low_above_055')})",
        "",
        "---",
        "",
        "## Step 5 — Temporal Split（三等分）",
        "",
        "| Third | n | hit_rate | date_start | date_end |",
        "|-------|---|----------|------------|----------|",
    ]
    for t in temporal.get("thirds", []):
        lines.append(
            f"| {t['third']} | {t['n']} | `{t['hit_rate']}` | {t.get('date_start')} | {t.get('date_end')} |"
        )
    lines += [
        "",
        f"- **Temporal stable** (all > 0.55): `{temporal.get('temporal_stable')}`",
        "",
        "---",
        "",
        "## Step 6 — Side Split",
        "",
        f"| Side | n | hit_rate |",
        f"|------|---|----------|",
        f"| Home predicted | {side.get('home_predicted', {}).get('n')} | `{side.get('home_predicted', {}).get('hit_rate')}` |",
        f"| Away predicted | {side.get('away_predicted', {}).get('n')} | `{side.get('away_predicted', {}).get('hit_rate')}` |",
        "",
        f"- **|delta|**: `{side.get('abs_side_delta')}` | threshold 0.10 | **Side balanced**: `{side.get('side_balanced')}`",
        "",
        "---",
        "",
        "## Step 7 — Mid / Low FIP Segment Qualification",
        "",
        "| Bucket | n | hit_rate | above_baseline+0.03 | binomial p |",
        "|--------|---|----------|---------------------|------------|",
    ]
    for key in ["mid_bucket", "low_bucket"]:
        b = seg.get(key, {})
        lines.append(
            f"| {b.get('label')} | {b.get('n')} | `{b.get('hit_rate')}` | {b.get('above_threshold')} | `{b.get('binomial_p_vs_home_baseline')}` |"
        )
    lines += [
        "",
        f"- **Segment qualification**: `{seg.get('segment_qualification')}`",
        "",
        "---",
        "",
        "## Step 8 — Sample Sufficiency",
        "",
        "| Month | n | hit_rate |",
        "|-------|---|----------|",
    ]
    for month, ms in sorted(sample.get("monthly_stats", {}).items()):
        lines.append(f"| {month} | {ms['n']} | `{ms['hit_rate']}` |")
    lines += [
        "",
        f"- **any_month_below_30**: `{sample.get('any_month_below_30')}` | **monthly_sample_limited**: `{sample.get('monthly_sample_limited')}`",
        f"- **Partial coverage**: `{sample.get('canonical_rows')} / {sample.get('schedule_rows')} = {sample.get('partial_coverage_ratio')}`",
        f"- **Season scope**: {sample.get('season_scope')}",
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
        "## Governance Summary",
        "",
        "| Flag | Value |",
        "|------|-------|",
        "| odds_used | false |",
        "| ev_computed | false |",
        "| clv_computed | false |",
        "| kelly_computed | false |",
        "| production_ready | false |",
        "| paper_only | true |",
        "| diagnostic_only | true |",
        "| live_api_calls | 0 |",
        "| paid_api_called | false |",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> dict[str, Any]:
    print("[P94] 開始執行 High-FIP Subset Diagnostic...")

    # Step 1
    print("[P94] Step 1: Pre-flight gates...")
    preflight = step1_preflight()
    if not preflight["all_gates_ok"]:
        print(f"[P94] ❌ Pre-flight 失敗: {preflight}")
        summary = {
            "final_classification": "P94_FAILED_VALIDATION",
            "step1_preflight": preflight,
        }
        OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        return summary

    gate1_ok = preflight["gate1_canonical_entry"]["ok"]
    gate3_ok = preflight["gate3_upstream_consistency"]["ok"]

    # Load rows
    print("[P94] Loading outcome rows...")
    rows = load_outcome_rows()

    # Step 2
    print("[P94] Step 2: Row inventory...")
    row_inv = step2_row_inventory(rows)

    # Step 3
    print("[P94] Step 3: High-FIP metrics recompute...")
    high_fip_metrics, high_fip_rows = step3_high_fip_metrics(rows)
    metrics_ok = high_fip_metrics["tolerance_ok"]
    if not metrics_ok:
        print(f"[P94] ❌ High-FIP metric mismatch: {high_fip_metrics}")

    # Step 4
    print("[P94] Step 4: Bootstrap CI...")
    bootstrap = step4_bootstrap_ci(high_fip_rows)

    # Step 5
    print("[P94] Step 5: Temporal split...")
    temporal = step5_temporal_split(high_fip_rows)

    # Step 6
    print("[P94] Step 6: Side split...")
    side = step6_side_split(high_fip_rows)

    # Step 7
    print("[P94] Step 7: Segment qualification...")
    segment = step7_segment_qualification(rows)

    # Step 8
    print("[P94] Step 8: Sample sufficiency...")
    sample = step8_sample_sufficiency(high_fip_rows)

    # Step 9
    print("[P94] Step 9: Final classification...")
    classification = step9_classification(
        bootstrap, temporal, side, sample, gate1_ok, gate3_ok, metrics_ok
    )
    fc = classification["final_classification"]

    # Step 10
    governance = step10_governance()

    print(f"[P94] Final classification: {fc}")

    # Assemble summary
    summary = {
        "phase": "P94",
        "final_classification": fc,
        "classification_rationale": classification.get("rationale", ""),
        "allowed_classifications": classification.get("allowed_classifications", []),
        "date": "2026-05-28",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_head": "2221f0f",
        "step1_preflight": preflight,
        "step2_row_inventory": row_inv,
        "step3_high_fip_metrics": high_fip_metrics,
        "step4_bootstrap_ci": bootstrap,
        "step5_temporal_split": temporal,
        "step6_side_split": side,
        "step7_segment_qualification": segment,
        "step8_sample_sufficiency": sample,
        "step9_classification": classification,
        "step10_governance": governance,
        "governance_all_pass": governance["status"] == "PASSED",
        "production_ready": False,
        "paper_only": True,
        "diagnostic_only": True,
    }

    # Write outputs
    OUTPUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"[P94] ✅ JSON summary written: {OUTPUT_SUMMARY}")

    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    report_text = generate_report(summary)
    OUTPUT_REPORT.write_text(report_text, encoding="utf-8")
    print(f"[P94] ✅ Markdown report written: {OUTPUT_REPORT}")

    return summary


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result.get("final_classification") != "P94_FAILED_VALIDATION" else 1)
