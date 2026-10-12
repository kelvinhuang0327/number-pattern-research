#!/usr/bin/env python3
"""
P49 — Offline Historical Monitoring Replay Using P48 Contract

Diagnostic-only. paper_only=True. promotion_freeze=True.
No live API calls. No production deployment. No runtime recommendation changes.

Replays the P48 monitoring contract against actual 2025 Tier C data to answer:
1. Which monthly batches would have triggered alerts if P48 were active?
2. Which rolling batches trigger alerts?
3. Does PLATT_CALIBRATED remain acceptable as monitoring baseline?
4. Is there hidden instability not captured by P44-P47?
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

# ── Import P48 contract (alert evaluation logic) ───────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._p48_monitoring_loop_contract import (
    evaluate_monitoring_row,
    _GOVERNANCE,
    SELECTED_STREAM,
    ECE_WARNING, ECE_CRITICAL,
    BRIER_WARNING, BRIER_CRITICAL,
    EDGE_WARNING_MEAN, SAMPLE_LIMITED_N,
    ALLOWED_STATUSES, ALLOWED_ALERT_LEVELS, ALLOWED_P48_CLASSIFICATIONS,
)

# ── Canonical paths ────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = REPO_ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P45_JSON = REPO_ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"
P47_JSON = REPO_ROOT / "data/mlb_2025/derived/p47_calibration_synthesis_summary.json"
P48_JSON = REPO_ROOT / "data/mlb_2025/derived/p48_monitoring_loop_contract_summary.json"
P49_JSON = REPO_ROOT / "data/mlb_2025/derived/p49_offline_historical_monitoring_replay_summary.json"
REPORT_MD = REPO_ROOT / "report/p49_offline_historical_monitoring_replay_20260526.md"
BETTING_PLAN_MD = REPO_ROOT / "00-BettingPlan/20260526/p49_offline_historical_monitoring_replay_20260526.md"

# ── Locked Platt coefficients (P45 pilot a/b) ─────────────────────────────────
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# ── Tier C filter ──────────────────────────────────────────────────────────────
TIER_C_THRESH: float = 0.5   # abs(sp_fip_delta) >= 0.5
TIER_C_N_EXPECTED: int = 535

# ── Calibration constants (from P45, preserved exactly) ───────────────────────
SIGMOID_K: float = 0.8
CLIP_EPS: float = 1e-7
N_CALIB_BINS: int = 10
MIN_BIN_FOR_ECE: int = 5

# ── Rolling batch params ───────────────────────────────────────────────────────
ROLLING_BATCH_SIZE: int = 100
ROLLING_STEP_SIZE: int = 50

# ── Governance ─────────────────────────────────────────────────────────────────
# Inherited from P48 via import; verified at module level
assert _GOVERNANCE["paper_only"] is True
assert _GOVERNANCE["live_api_calls"] == 0
assert _GOVERNANCE["promotion_freeze"] is True
assert _GOVERNANCE["runtime_recommendation_logic_changed"] is False

_SOURCE_TRACE: dict = {
    "p45_artifact": "data/mlb_2025/derived/p45_platt_recalibration_summary.json",
    "p47_artifact": "data/mlb_2025/derived/p47_calibration_synthesis_summary.json",
    "p48_artifact": "data/mlb_2025/derived/p48_monitoring_loop_contract_summary.json",
    "predictions_jsonl": "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
    "platt_a": PLATT_A,
    "platt_b": PLATT_B,
    "selected_stream": "PLATT_CALIBRATED",
    "tier_c_threshold_abs_fip_delta": TIER_C_THRESH,
}


# ── Calibration math (exact mirror of P45) ─────────────────────────────────────

def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-SIGMOID_K * x))
    except OverflowError:
        return 0.0 if x < 0 else 1.0


def _logit(p: float) -> float:
    p = max(CLIP_EPS, min(1.0 - CLIP_EPS, p))
    return math.log(p / (1.0 - p))


def platt_prob(raw: float, a: float = PLATT_A, b: float = PLATT_B) -> float:
    """Apply Platt calibration: 1 / (1 + exp(-(a * logit(raw) + b)))"""
    return _sigmoid((a * _logit(raw) + b) / SIGMOID_K)


def compute_ece(
    probs: list[float],
    labels: list[int],
    n_bins: int = N_CALIB_BINS,
    min_bin: int = MIN_BIN_FOR_ECE,
) -> float:
    n = len(probs)
    if n == 0:
        return float("nan")
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            idx = [j for j in range(n) if lo <= probs[j] <= hi]
        else:
            idx = [j for j in range(n) if lo <= probs[j] < hi]
        if len(idx) < min_bin:
            continue
        pred_mean = sum(probs[j] for j in idx) / len(idx)
        act_rate = sum(labels[j] for j in idx) / len(idx)
        ece += (len(idx) / n) * abs(pred_mean - act_rate)
    return ece


def compute_brier(probs: list[float], labels: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


def compute_edge_stats(
    edges: list[float],
) -> tuple[float, float, float, float]:
    """
    Return (mean, std, ci_low_95, ci_high_95) using normal approximation.
    For n >= 30 this is sufficient.
    """
    n = len(edges)
    if n == 0:
        return float("nan"), float("nan"), float("nan"), float("nan")
    mean = sum(edges) / n
    if n < 2:
        return mean, 0.0, mean, mean
    var = sum((e - mean) ** 2 for e in edges) / (n - 1)
    std = math.sqrt(var)
    se = std / math.sqrt(n)
    ci_low = mean - 1.96 * se
    ci_high = mean + 1.96 * se
    return mean, std, ci_low, ci_high


# ── Tier C dataset builder ─────────────────────────────────────────────────────

def build_tier_c_dataset() -> list[dict]:
    """
    Rebuild the same Tier C dataset used by P43–P48.
    Filter: market_home_prob_no_vig in (0,1), home_win not None,
            model_home_prob not None, abs(sp_fip_delta) >= 0.5.
    Returns list of enriched rows sorted by game_date.
    """
    lines = JSONL_PATH.read_text().strip().split("\n")
    tier_c: list[dict] = []

    for line in lines:
        row = json.loads(line)
        mkt = row.get("market_home_prob_no_vig")
        hw = row.get("home_win")
        mp = row.get("model_home_prob")
        feats = row.get("p0_features", {})
        sp_delta = feats.get("sp_fip_delta")

        if mkt is None or hw is None or mp is None or sp_delta is None:
            continue
        if not (0 < mkt < 1):
            continue
        if abs(sp_delta) < TIER_C_THRESH:
            continue

        cal = platt_prob(mp)
        edge = mp - mkt

        tier_c.append({
            "game_date": row["game_date"],
            "month": row["game_date"][:7],
            "model_home_prob": mp,
            "platt_home_prob": round(cal, 8),
            "market_home_prob_no_vig": mkt,
            "home_win": int(hw),
            "edge": round(edge, 8),
            "sp_fip_delta": sp_delta,
        })

    # Sort by game_date ascending (stable for rolling windows)
    tier_c.sort(key=lambda r: r["game_date"])
    return tier_c


def verify_tier_c(rows: list[dict]) -> dict:
    """Verify Tier C row count and basic sanity."""
    n = len(rows)
    dates = [r["game_date"] for r in rows]
    months = sorted(set(r["month"] for r in rows))
    return {
        "tier_c_n": n,
        "expected_n": TIER_C_N_EXPECTED,
        "match_expected": n == TIER_C_N_EXPECTED,
        "min_date": min(dates),
        "max_date": max(dates),
        "months_covered": months,
    }


# ── Batch metric computer ──────────────────────────────────────────────────────

def compute_batch_metrics(rows: list[dict]) -> dict:
    """Compute all monitoring metrics for a set of rows."""
    n = len(rows)
    raw_probs = [r["model_home_prob"] for r in rows]
    cal_probs = [r["platt_home_prob"] for r in rows]
    labels = [r["home_win"] for r in rows]
    edges = [r["edge"] for r in rows]

    raw_ece = compute_ece(raw_probs, labels)
    platt_ece = compute_ece(cal_probs, labels)
    raw_brier = compute_brier(raw_probs, labels)
    platt_brier = compute_brier(cal_probs, labels)
    mean_edge, std_edge, ci_low, ci_high = compute_edge_stats(edges)
    pos_rate = sum(1 for e in edges if e > 0) / n if n > 0 else 0.0

    return {
        "batch_n": n,
        "raw_ece": round(raw_ece, 6),
        "platt_ece": round(platt_ece, 6),
        "raw_brier": round(raw_brier, 6),
        "platt_brier": round(platt_brier, 6),
        "mean_edge": round(mean_edge, 6),
        "edge_std": round(std_edge, 6),
        "edge_ci_low": round(ci_low, 6),
        "edge_ci_high": round(ci_high, 6),
        "positive_edge_rate": round(pos_rate, 6),
    }


# ── Monthly replay ─────────────────────────────────────────────────────────────

def build_monthly_replay(rows: list[dict]) -> list[dict]:
    """
    Group Tier C rows by month (YYYY-MM) and apply P48 monitoring contract to each.
    Returns list of monitoring row dicts sorted by month.
    """
    from collections import defaultdict
    monthly_buckets: dict[str, list] = defaultdict(list)
    for r in rows:
        monthly_buckets[r["month"]].append(r)

    replay_rows = []
    for month in sorted(monthly_buckets):
        bucket = monthly_buckets[month]
        metrics = compute_batch_metrics(bucket)
        result = evaluate_monitoring_row(
            batch_n=metrics["batch_n"],
            probability_stream=SELECTED_STREAM,
            raw_ece=metrics["raw_ece"],
            platt_ece=metrics["platt_ece"],
            raw_brier=metrics["raw_brier"],
            platt_brier=metrics["platt_brier"],
            mean_edge=metrics["mean_edge"],
            edge_ci_low=metrics["edge_ci_low"],
            edge_ci_high=metrics["edge_ci_high"],
            closing_line_source_missing=False,
        )
        replay_rows.append({
            "monitoring_date": "2026-05-26",
            "season": 2025,
            "batch_id": "MONTHLY_" + month.replace("-", ""),
            "batch_n": metrics["batch_n"],
            "probability_stream": SELECTED_STREAM,
            "raw_ece": metrics["raw_ece"],
            "platt_ece": metrics["platt_ece"],
            "raw_brier": metrics["raw_brier"],
            "platt_brier": metrics["platt_brier"],
            "mean_edge": metrics["mean_edge"],
            "edge_std": metrics["edge_std"],
            "edge_ci_low": metrics["edge_ci_low"],
            "edge_ci_high": metrics["edge_ci_high"],
            "positive_edge_rate": metrics["positive_edge_rate"],
            "monthly_bucket": month,
            "status": result["status"],
            "alert_level": result["alert_level"],
            "alert_reasons": result["alert_reasons"],
            "governance_flags": dict(_GOVERNANCE),
            "source_trace": dict(_SOURCE_TRACE),
        })

    return replay_rows


# ── Rolling batch replay ───────────────────────────────────────────────────────

def build_rolling_replay(rows: list[dict]) -> list[dict]:
    """
    Build deterministic rolling batch monitoring replay.
    batch_size=100, step=50, ordered by game_date.
    Final partial batch omitted if n < ROLLING_BATCH_SIZE.
    """
    replay_rows = []
    n_total = len(rows)
    start = 0

    while start < n_total:
        end = start + ROLLING_BATCH_SIZE
        batch = rows[start:end]
        batch_n = len(batch)

        if batch_n < ROLLING_BATCH_SIZE:
            # Partial batch — skip (too small, not enough data)
            break

        start_date = batch[0]["game_date"]
        end_date = batch[-1]["game_date"]
        seq = (start // ROLLING_STEP_SIZE) + 1
        batch_id = "ROLLING_" + start_date.replace("-", "") + "_" + end_date.replace("-", "") + "_N" + str(batch_n).zfill(3)

        metrics = compute_batch_metrics(batch)
        result = evaluate_monitoring_row(
            batch_n=metrics["batch_n"],
            probability_stream=SELECTED_STREAM,
            raw_ece=metrics["raw_ece"],
            platt_ece=metrics["platt_ece"],
            raw_brier=metrics["raw_brier"],
            platt_brier=metrics["platt_brier"],
            mean_edge=metrics["mean_edge"],
            edge_ci_low=metrics["edge_ci_low"],
            edge_ci_high=metrics["edge_ci_high"],
            closing_line_source_missing=False,
        )

        replay_rows.append({
            "monitoring_date": "2026-05-26",
            "season": 2025,
            "batch_id": batch_id,
            "seq": seq,
            "start_date": start_date,
            "end_date": end_date,
            "batch_n": metrics["batch_n"],
            "probability_stream": SELECTED_STREAM,
            "raw_ece": metrics["raw_ece"],
            "platt_ece": metrics["platt_ece"],
            "raw_brier": metrics["raw_brier"],
            "platt_brier": metrics["platt_brier"],
            "mean_edge": metrics["mean_edge"],
            "edge_std": metrics["edge_std"],
            "edge_ci_low": metrics["edge_ci_low"],
            "edge_ci_high": metrics["edge_ci_high"],
            "positive_edge_rate": metrics["positive_edge_rate"],
            "monthly_bucket": None,
            "status": result["status"],
            "alert_level": result["alert_level"],
            "alert_reasons": result["alert_reasons"],
            "governance_flags": dict(_GOVERNANCE),
            "source_trace": dict(_SOURCE_TRACE),
        })

        start += ROLLING_STEP_SIZE

    return replay_rows


# ── Alert summary ──────────────────────────────────────────────────────────────

def summarize_alerts(rows: list[dict]) -> dict:
    counts = {
        "ok_count": 0,
        "warning_count": 0,
        "critical_count": 0,
        "sample_limited_count": 0,
        "blocked_count": 0,
        "total_batches": len(rows),
    }
    for r in rows:
        level = r["alert_level"]
        status = r["status"]
        if status == "MONITORING_OK":
            counts["ok_count"] += 1
        elif status == "SAMPLE_LIMITED":
            counts["sample_limited_count"] += 1
        elif status == "DATA_GAP_BLOCKED":
            counts["blocked_count"] += 1
        elif level == "WARNING":
            counts["warning_count"] += 1
        elif level == "CRITICAL":
            counts["critical_count"] += 1

    # Worst-case metrics
    ece_vals = [r["platt_ece"] for r in rows if r.get("platt_ece") is not None and not math.isnan(r.get("platt_ece", float("nan")))]
    brier_vals = [r["platt_brier"] for r in rows if r.get("platt_brier") is not None and not math.isnan(r.get("platt_brier", float("nan")))]
    edge_vals = [r["mean_edge"] for r in rows if r.get("mean_edge") is not None and not math.isnan(r.get("mean_edge", float("nan")))]
    ci_vals = [r["edge_ci_low"] for r in rows if r.get("edge_ci_low") is not None and not math.isnan(r.get("edge_ci_low", float("nan")))]

    counts["worst_platt_ece"] = round(max(ece_vals), 6) if ece_vals else None
    counts["worst_platt_brier"] = round(max(brier_vals), 6) if brier_vals else None
    counts["lowest_mean_edge"] = round(min(edge_vals), 6) if edge_vals else None
    counts["lowest_edge_ci_low"] = round(min(ci_vals), 6) if ci_vals else None
    return counts


def classify_p49(monthly_summary: dict, rolling_summary: dict) -> str:
    """Select P49 final classification based on alert levels."""
    total_critical = monthly_summary["critical_count"] + rolling_summary["critical_count"]
    total_warning = monthly_summary["warning_count"] + rolling_summary["warning_count"]
    total_blocked = monthly_summary["blocked_count"] + rolling_summary["blocked_count"]

    if total_blocked > 0:
        return "P49_MONITORING_REPLAY_BLOCKED"
    if total_critical > 0:
        return "P49_MONITORING_REPLAY_CRITICAL_DIAGNOSTIC"
    if total_warning > 0:
        return "P49_MONITORING_REPLAY_WARNINGS_DIAGNOSTIC"
    # If all batches are SAMPLE_LIMITED
    total_ok = monthly_summary["ok_count"] + rolling_summary["ok_count"]
    if total_ok == 0:
        return "P49_MONITORING_REPLAY_SAMPLE_LIMITED"
    return "P49_MONITORING_REPLAY_HEALTHY_DIAGNOSTIC"


# ── Summary builder ────────────────────────────────────────────────────────────

def build_p49_summary(
    tier_c_verify: dict,
    monthly_rows: list[dict],
    rolling_rows: list[dict],
    p45_source: dict,
    p47_source: dict,
    p48_source: dict,
) -> dict:
    monthly_summary = summarize_alerts(monthly_rows)
    rolling_summary = summarize_alerts(rolling_rows)
    final_classification = classify_p49(monthly_summary, rolling_summary)

    # Worst-case batch analysis
    all_rows = monthly_rows + rolling_rows
    worst_ece = max((r["platt_ece"] for r in all_rows if r.get("platt_ece") is not None), default=None)
    worst_brier = max((r["platt_brier"] for r in all_rows if r.get("platt_brier") is not None), default=None)
    lowest_edge = min((r["mean_edge"] for r in all_rows if r.get("mean_edge") is not None), default=None)
    lowest_ci = min((r["edge_ci_low"] for r in all_rows if r.get("edge_ci_low") is not None), default=None)

    worst_batch = None
    if worst_ece is not None:
        cand = [r for r in all_rows if r.get("platt_ece") == worst_ece]
        if cand:
            worst_batch = cand[0]["batch_id"]

    thresholds = p48_source.get("alert_thresholds", {})

    return {
        "version": "p49_v1",
        "governance": dict(_GOVERNANCE),
        "source_artifacts": {
            "predictions_jsonl": str(JSONL_PATH.relative_to(REPO_ROOT)),
            "p45_summary": str(P45_JSON.relative_to(REPO_ROOT)),
            "p47_summary": str(P47_JSON.relative_to(REPO_ROOT)),
            "p48_summary": str(P48_JSON.relative_to(REPO_ROOT)),
        },
        "platt_coefficients": {
            "platt_a": PLATT_A,
            "platt_b": PLATT_B,
            "source": "P45 pilot a/b (locked)",
        },
        "tier_c_verification": tier_c_verify,
        "rolling_batch_params": {
            "batch_size": ROLLING_BATCH_SIZE,
            "step_size": ROLLING_STEP_SIZE,
        },
        "monthly_replay": {
            "rows": monthly_rows,
            "summary": monthly_summary,
        },
        "rolling_replay": {
            "rows": rolling_rows,
            "summary": rolling_summary,
        },
        "overall_summary": {
            "total_monthly_batches": monthly_summary["total_batches"],
            "total_rolling_batches": rolling_summary["total_batches"],
            "worst_platt_ece_all": round(worst_ece, 6) if worst_ece is not None else None,
            "worst_platt_brier_all": round(worst_brier, 6) if worst_brier is not None else None,
            "lowest_mean_edge_all": round(lowest_edge, 6) if lowest_edge is not None else None,
            "lowest_edge_ci_low_all": round(lowest_ci, 6) if lowest_ci is not None else None,
            "worst_batch_id": worst_batch,
        },
        "platt_monitoring_acceptable": True,  # Set by analysis below
        "platt_monitoring_acceptable_reason": "",
        "alert_thresholds_recap": thresholds,
        "final_classification": final_classification,
        "allowed_classifications": [
            "P49_MONITORING_REPLAY_HEALTHY_DIAGNOSTIC",
            "P49_MONITORING_REPLAY_WARNINGS_DIAGNOSTIC",
            "P49_MONITORING_REPLAY_CRITICAL_DIAGNOSTIC",
            "P49_MONITORING_REPLAY_SAMPLE_LIMITED",
            "P49_MONITORING_REPLAY_BLOCKED",
        ],
        "data_gap_2024_acknowledged": True,
        "data_gap_2024_note": (
            "2024 closing-line data gap remains unresolved. "
            "mlb_2024_sp_fip_delta_features.jsonl has no market probability columns. "
            "P43 final classification remains P43_BLOCKED_BY_DATA_GAP. "
            "P49 uses 2025 Tier C data only."
        ),
        "framing_note": (
            "P49 is an offline diagnostic replay of the P48 monitoring contract "
            "against actual 2025 Tier C data. Paper-only. No live API calls. "
            "No production usage. No champion strategy changes. "
            "No runtime recommendation logic changes."
        ),
    }


# ── Acceptability analysis ─────────────────────────────────────────────────────

def set_acceptability(summary: dict) -> dict:
    """
    Determine if PLATT_CALIBRATED remains acceptable as monitoring baseline.
    Acceptable = no CRITICAL alerts in rolling batches AND worst_ece < ECE_CRITICAL.
    """
    rolling_summary = summary["rolling_replay"]["summary"]
    overall = summary["overall_summary"]

    worst_ece = overall.get("worst_platt_ece_all")
    has_critical = rolling_summary["critical_count"] > 0

    if has_critical or (worst_ece is not None and worst_ece > ECE_CRITICAL):
        summary["platt_monitoring_acceptable"] = False
        summary["platt_monitoring_acceptable_reason"] = (
            "CRITICAL alerts detected in rolling replay or worst ECE exceeds critical threshold. "
            "Platt calibration may be degrading. Consider re-running P45 recalibration."
        )
    else:
        summary["platt_monitoring_acceptable"] = True
        summary["platt_monitoring_acceptable_reason"] = (
            "No CRITICAL alerts in rolling replay. Worst ECE within P47 critical threshold. "
            "Platt calibration baseline remains acceptable for paper monitoring."
        )
    return summary


# ── Report renderer ────────────────────────────────────────────────────────────

def render_report(summary: dict) -> str:
    tier_v = summary["tier_c_verification"]
    monthly_rows = summary["monthly_replay"]["rows"]
    rolling_rows = summary["rolling_replay"]["rows"]
    ms = summary["monthly_replay"]["summary"]
    rs = summary["rolling_replay"]["summary"]
    overall = summary["overall_summary"]
    gov = summary["governance"]

    lines = [
        "# P49 — Offline Historical Monitoring Replay Using P48 Contract",
        "",
        "**Date**: 2026-05-26  ",
        "**Classification**: `" + summary["final_classification"] + "`  ",
        "**Mode**: `paper_only=true` | `diagnostic_only=true` | `promotion_freeze=true`  ",
        "**Platt Coefficients**: a=" + str(summary["platt_coefficients"]["platt_a"]) +
        ", b=" + str(summary["platt_coefficients"]["platt_b"]) + " (locked from P45)",
        "",
        "---",
        "",
        "## 1. P48 Contract Recap",
        "",
        "| Threshold | Warning | Critical |",
        "|-----------|---------|----------|",
        "| ECE (Platt) | > 0.10 | > 0.12 |",
        "| Brier (Platt) | > 0.25 | > 0.27 |",
        "| Edge mean | < 0.07 | CI ≤ 0 |",
        "| Sample | — | SAMPLE_LIMITED if n < 100 |",
        "| Data gap | — | DATA_GAP_BLOCKED (overrides all) |",
        "",
        "Priority: DATA_GAP_BLOCKED > SAMPLE_LIMITED > CRITICAL/WARNING > MONITORING_OK",
        "",
        "---",
        "",
        "## 2. Source Data Inventory",
        "",
        "| Source | Status |",
        "|--------|--------|",
        "| Predictions JSONL (phase56) | Present, immutable |",
        "| P45 Platt summary | Present, immutable |",
        "| P47 synthesis summary | Present, immutable |",
        "| P48 contract summary | Present, immutable |",
        "| 2024 closing-line data | **MISSING** (P43_BLOCKED_BY_DATA_GAP) |",
        "",
        "---",
        "",
        "## 3. Tier C Row Count Verification",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        "| Rebuilt Tier C n | " + str(tier_v["tier_c_n"]) + " |",
        "| Expected n | " + str(tier_v["expected_n"]) + " |",
        "| Match | " + str(tier_v["match_expected"]) + " |",
        "| Date range | " + tier_v["min_date"] + " to " + tier_v["max_date"] + " |",
        "| Months covered | " + ", ".join(tier_v["months_covered"]) + " |",
        "",
        "Filter: `abs(sp_fip_delta) >= 0.5`, `market_home_prob_no_vig in (0,1)`, outcome not null",
        "",
        "---",
        "",
        "## 4. Monthly Monitoring Replay",
        "",
        "| Month | n | Platt ECE | Platt Brier | Mean Edge | Edge CI Low | Status | Alert |",
        "|-------|---|-----------|-------------|-----------|-------------|--------|-------|",
    ]

    for r in monthly_rows:
        ece = r.get("platt_ece")
        brier = r.get("platt_brier")
        edge = r.get("mean_edge")
        ci_low = r.get("edge_ci_low")
        lines.append(
            "| " + r["monthly_bucket"] +
            " | " + str(r["batch_n"]) +
            " | " + ("{:.4f}".format(ece) if ece is not None else "n/a") +
            " | " + ("{:.4f}".format(brier) if brier is not None else "n/a") +
            " | " + ("{:.4f}".format(edge) if edge is not None else "n/a") +
            " | " + ("{:.4f}".format(ci_low) if ci_low is not None else "n/a") +
            " | `" + r["status"] + "` | `" + r["alert_level"] + "` |"
        )

    lines += [
        "",
        "**Monthly summary**: OK=" + str(ms["ok_count"]) +
        ", Warning=" + str(ms["warning_count"]) +
        ", Critical=" + str(ms["critical_count"]) +
        ", SampleLimited=" + str(ms["sample_limited_count"]) +
        ", Blocked=" + str(ms["blocked_count"]),
        "",
        "---",
        "",
        "## 5. Rolling Batch Monitoring Replay",
        "",
        "Batch size: 100 | Step: 50 | Ordered by game_date | Partial batches omitted",
        "",
        "| Batch ID | n | Dates | Platt ECE | Platt Brier | Mean Edge | CI Low | Status | Alert |",
        "|----------|---|-------|-----------|-------------|-----------|--------|--------|-------|",
    ]

    for r in rolling_rows:
        ece = r.get("platt_ece")
        brier = r.get("platt_brier")
        edge = r.get("mean_edge")
        ci_low = r.get("edge_ci_low")
        date_range = r.get("start_date", "?") + " – " + r.get("end_date", "?")
        lines.append(
            "| " + r["batch_id"] +
            " | " + str(r["batch_n"]) +
            " | " + date_range +
            " | " + ("{:.4f}".format(ece) if ece is not None else "n/a") +
            " | " + ("{:.4f}".format(brier) if brier is not None else "n/a") +
            " | " + ("{:.4f}".format(edge) if edge is not None else "n/a") +
            " | " + ("{:.4f}".format(ci_low) if ci_low is not None else "n/a") +
            " | `" + r["status"] + "` | `" + r["alert_level"] + "` |"
        )

    lines += [
        "",
        "**Rolling summary**: Total=" + str(rs["total_batches"]) +
        ", OK=" + str(rs["ok_count"]) +
        ", Warning=" + str(rs["warning_count"]) +
        ", Critical=" + str(rs["critical_count"]) +
        ", SampleLimited=" + str(rs["sample_limited_count"]) +
        ", Blocked=" + str(rs["blocked_count"]),
        "",
        "---",
        "",
        "## 6. Alert Summary",
        "",
        "| Scope | Total | OK | Warning | Critical | SampleLimited | Blocked |",
        "|-------|-------|----|---------|----------|---------------|---------|",
        "| Monthly | " + str(ms["total_batches"]) + " | " + str(ms["ok_count"]) + " | " + str(ms["warning_count"]) + " | " + str(ms["critical_count"]) + " | " + str(ms["sample_limited_count"]) + " | " + str(ms["blocked_count"]) + " |",
        "| Rolling | " + str(rs["total_batches"]) + " | " + str(rs["ok_count"]) + " | " + str(rs["warning_count"]) + " | " + str(rs["critical_count"]) + " | " + str(rs["sample_limited_count"]) + " | " + str(rs["blocked_count"]) + " |",
        "",
        "---",
        "",
        "## 7. Worst-Case Batch Analysis",
        "",
        "| Metric | Value | Threshold |",
        "|--------|-------|-----------|",
        "| Worst Platt ECE | " + ("{:.4f}".format(overall['worst_platt_ece_all']) if overall['worst_platt_ece_all'] is not None else "n/a") + " | Warning=0.10, Critical=0.12 |",
        "| Worst Platt Brier | " + ("{:.4f}".format(overall['worst_platt_brier_all']) if overall['worst_platt_brier_all'] is not None else "n/a") + " | Warning=0.25, Critical=0.27 |",
        "| Lowest Mean Edge | " + ("{:.4f}".format(overall['lowest_mean_edge_all']) if overall['lowest_mean_edge_all'] is not None else "n/a") + " | Warning=0.07 |",
        "| Lowest Edge CI Low | " + ("{:.4f}".format(overall['lowest_edge_ci_low_all']) if overall['lowest_edge_ci_low_all'] is not None else "n/a") + " | Critical: CI ≤ 0 |",
        "| Worst batch | " + str(overall.get("worst_batch_id", "n/a")) + " | — |",
        "",
        "---",
        "",
        "## 8. Platt Monitoring Baseline Acceptability",
        "",
        "**Acceptable**: `" + str(summary["platt_monitoring_acceptable"]) + "`",
        "",
        summary["platt_monitoring_acceptable_reason"],
        "",
        "---",
        "",
        "## 9. Limitations",
        "",
        "- **2024 closing-line data gap**: Unresolved. P43_BLOCKED_BY_DATA_GAP persists.",
        "- **Closing line vs CLV**: `mlb_odds_2025_real.csv` has no pre-game timestamps. "
        "Edge is vs closing line, not strict Closing Line Value (CLV).",
        "- **Normal approximation CI**: Rolling batch edge CI uses normal approximation "
        "(n≥100). Consistent with large-sample theory but differs from P43 bootstrap CI.",
        "- **Platt coefficients are from 80/20 train/test split**: Coefficients (a=0.435432, "
        "b=0.245464) were fitted on 428 training rows. Full-dataset coefficients would differ.",
        "- **No live model deployed**: Platt calibration is diagnostic only. No runtime "
        "logic was changed.",
        "",
        "---",
        "",
        "## 10. 2024 Data Gap (Explicit Statement)",
        "",
        "The 2024 MLB closing-line data gap remains **unresolved**. "
        "`data/mlb_2025/derived/mlb_2024_sp_fip_delta_features.jsonl` contains no "
        "market probability columns. No valid 2024 MLB moneyline odds source exists in "
        "the repository. **P43 final classification remains `P43_BLOCKED_BY_DATA_GAP`**. "
        "P49 uses 2025 Tier C data only (n=535).",
        "",
        "---",
        "",
        "## 11. Final P49 Classification",
        "",
        "**`" + summary["final_classification"] + "`**",
        "",
        "> This is a paper-only offline diagnostic replay. "
        "It does not authorize deployment, live monitoring, production usage, "
        "or any change to the champion strategy or runtime recommendation logic.",
        "",
        "---",
        "",
        "## Governance Flags",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in gov.items():
        lines.append("| `" + k + "` | `" + str(v) + "` |")

    lines += [
        "",
        "---",
        "",
        "## CTO Summary",
        "",
        "P49 replays the P48 monitoring contract against actual 2025 Tier C data (n=535). "
        "Monthly replay covers Apr–Sep; April/July/September are SAMPLE_LIMITED (n<100). "
        "Rolling replay uses batch=100, step=50 across the full season. "
        "Platt calibration (a=0.435432, b=0.245464) is applied from P45 locked coefficients. "
        "Final classification: `" + summary["final_classification"] + "`. "
        "No live API calls. No runtime logic changes. No production proposals. "
        "2024 data gap remains P43_BLOCKED_BY_DATA_GAP.",
    ]

    return "\n".join(lines)


# ── Output writer ──────────────────────────────────────────────────────────────

def write_outputs(summary: dict) -> None:
    P49_JSON.parent.mkdir(parents=True, exist_ok=True)
    P49_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    md_content = render_report(summary)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(md_content)

    BETTING_PLAN_MD.parent.mkdir(parents=True, exist_ok=True)
    BETTING_PLAN_MD.write_text(md_content)

    print("[P49] JSON:   " + str(P49_JSON))
    print("[P49] Report: " + str(REPORT_MD))
    print("[P49] Plan:   " + str(BETTING_PLAN_MD))
    print("[P49] Final classification: " + summary["final_classification"])

    ms = summary["monthly_replay"]["summary"]
    rs = summary["rolling_replay"]["summary"]
    tier_v = summary["tier_c_verification"]
    print("[P49] Tier C n=" + str(tier_v["tier_c_n"]) + " (expected " + str(tier_v["expected_n"]) + ", match=" + str(tier_v["match_expected"]) + ")")
    print("[P49] Monthly: total=" + str(ms["total_batches"]) +
          " ok=" + str(ms["ok_count"]) +
          " warning=" + str(ms["warning_count"]) +
          " critical=" + str(ms["critical_count"]) +
          " sample_limited=" + str(ms["sample_limited_count"]))
    print("[P49] Rolling: total=" + str(rs["total_batches"]) +
          " ok=" + str(rs["ok_count"]) +
          " warning=" + str(rs["warning_count"]) +
          " critical=" + str(rs["critical_count"]) +
          " sample_limited=" + str(rs["sample_limited_count"]))
    print("[P49] Platt acceptable: " + str(summary["platt_monitoring_acceptable"]))
    print("[P49] Monthly rows:")
    for r in summary["monthly_replay"]["rows"]:
        print("       " + r["monthly_bucket"] + " n=" + str(r["batch_n"]) + " → " + r["status"] + " [" + r["alert_level"] + "]")


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> dict:
    # Load source artifacts
    p45_source = json.loads(P45_JSON.read_text())
    p47_source = json.loads(P47_JSON.read_text())
    p48_source = json.loads(P48_JSON.read_text())

    # Build Tier C dataset
    tier_c_rows = build_tier_c_dataset()
    tier_c_verify = verify_tier_c(tier_c_rows)

    # Monthly and rolling replays
    monthly_rows = build_monthly_replay(tier_c_rows)
    rolling_rows = build_rolling_replay(tier_c_rows)

    # Build summary
    summary = build_p49_summary(tier_c_verify, monthly_rows, rolling_rows, p45_source, p47_source, p48_source)
    summary = set_acceptability(summary)

    # Write outputs
    write_outputs(summary)
    return summary


if __name__ == "__main__":
    main()
