#!/usr/bin/env python3
"""
P46 — Isotonic Regression Recalibration Comparison (Paper-Only Diagnostic)

P45 Platt baseline: test ECE=0.0701, 5-fold mean ECE=0.0862
Goal: compare isotonic regression vs Platt scaling; diagnose if ECE < 0.05 is achievable.

Four sub-tasks:
  P46.A — 80/20 train/test comparison (Platt vs Isotonic)
  P46.B — 5-fold CV comparison
  P46.C — Walk-forward monthly comparison (Apr-Sep 2025)
  P46.D — Final diagnostic recommendation

Governance:
  - No live API calls
  - No champion replacement
  - No production proposal
  - Diagnostic only
"""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scipy.optimize import minimize

# ---------------------------------------------------------------------------
# Governance (locked)
# ---------------------------------------------------------------------------

GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
}

for k, v in [
    ("paper_only", True), ("diagnostic_only", True), ("promotion_freeze", True),
    ("kelly_deploy_allowed", False), ("live_api_calls", 0),
    ("tsl_crawler_modified", False), ("champion_strategy_changed", False),
    ("production_usage_proposed", False),
]:
    assert GOVERNANCE[k] == v, f"Governance violation: {k}={GOVERNANCE[k]}"

ROOT = Path(__file__).resolve().parents[1]
FILE_PHASE56 = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
FILE_CLOSING = ROOT / "data/mlb_2025/mlb_odds_2025_real.csv"

OUT_JSON = ROOT / "data/mlb_2025/derived/p46_isotonic_recalibration_summary.json"
OUT_REPORT = ROOT / "report/p46_isotonic_recalibration_comparison_20260526.md"
OUT_BETTINGPLAN = ROOT / "00-BettingPlan/20260526/p46_isotonic_recalibration_comparison_20260526.md"

SEED = 42
TIER_C_THRESHOLD = 0.50
SIGMOID_K = 0.8
CLIP_EPS = 1e-7
N_FOLDS = 5
N_CALIB_BINS = 10
MIN_BIN_FOR_ECE = 5

# P44/P45 baselines
P44_RAW_ECE = 0.0953
P44_RAW_BRIER = 0.2481
P45_PLATT_TEST_ECE = 0.0701
P45_PLATT_CV_MEAN_ECE = 0.0862

ALLOWED_P46_CLASSIFICATIONS = frozenset([
    "P46_ISOTONIC_SUPERIOR_DIAGNOSTIC",
    "P46_PLATT_PREFERRED_DIAGNOSTIC",
    "P46_MIXED_RECALIBRATION_DIAGNOSTIC",
    "P46_SAMPLE_LIMITED",
])


# ---------------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------------

@dataclass
class CalibRecord:
    game_date: str
    month: str
    model_prob: float
    actual_home_win: int


# ---------------------------------------------------------------------------
# Data loading (mirrors P44/P45 logic)
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-SIGMOID_K * x))


def _american_to_prob(s: str | None) -> float | None:
    if not s:
        return None
    try:
        odds = int(str(s).strip())
    except ValueError:
        return None
    if odds > 0:
        return 100.0 / (odds + 100.0)
    if odds < 0:
        a = abs(odds)
        return a / (a + 100.0)
    return None


def _closing_market_home_prob(hml: str | None, aml: str | None) -> float | None:
    hp = _american_to_prob(hml)
    ap = _american_to_prob(aml)
    if hp is None or ap is None:
        return None
    s = hp + ap
    return (hp / s) if s > 0 else None


def load_tier_c_records() -> tuple[list[CalibRecord], dict[str, int]]:
    market: dict[tuple[str, str, str], dict[str, str]] = {}
    with FILE_CLOSING.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (str(row.get("Date", "")), str(row.get("Away", "")), str(row.get("Home", "")))
            market[key] = dict(row)

    inv = {"phase56_rows": 0, "quality_rows": 0, "joined_rows": 0, "tier_c_rows": 0}
    records: list[CalibRecord] = []

    with FILE_PHASE56.open("r", encoding="utf-8") as f:
        for line in f:
            inv["phase56_rows"] += 1
            r = json.loads(line)
            p0 = r.get("p0_features", {})
            if not p0.get("sp_fip_delta_available"):
                continue
            if p0.get("sp_context_source", "") == "league_average_fallback":
                continue
            delta = p0.get("sp_fip_delta")
            if delta is None or r.get("home_win") is None:
                continue
            inv["quality_rows"] += 1

            key = (str(r.get("game_date", "")), str(r.get("away_team", "")), str(r.get("home_team", "")))
            mrow = market.get(key)
            if mrow is None:
                continue
            if _closing_market_home_prob(mrow.get("Home ML"), mrow.get("Away ML")) is None:
                continue
            hs, aw = mrow.get("Home Score"), mrow.get("Away Score")
            if not hs or not aw or str(hs).strip() == "" or str(aw).strip() == "":
                continue
            inv["joined_rows"] += 1

            if abs(float(delta)) < TIER_C_THRESHOLD:
                continue
            inv["tier_c_rows"] += 1

            gd = str(r.get("game_date", ""))
            records.append(CalibRecord(
                game_date=gd,
                month=gd[:7] if len(gd) >= 7 else "unknown",
                model_prob=_sigmoid(float(delta)),
                actual_home_win=int(int(hs) > int(aw)),
            ))

    return records, inv


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_ece(
    probs: list[float],
    labels: list[int],
    n_bins: int = N_CALIB_BINS,
    min_bin: int = MIN_BIN_FOR_ECE,
) -> float:
    n = len(probs)
    if n == 0:
        return float("nan")
    edges = [i / n_bins for i in range(n_bins + 1)]
    ece = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        idx = [j for j in range(n) if (lo <= probs[j] < hi) or (i == n_bins - 1 and probs[j] == hi)]
        if len(idx) < min_bin:
            continue
        pm = sum(probs[j] for j in idx) / len(idx)
        ar = sum(labels[j] for j in idx) / len(idx)
        ece += (len(idx) / n) * abs(pm - ar)
    return ece


def compute_brier(probs: list[float], labels: list[int]) -> float:
    if not probs:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, labels)) / len(probs)


# ---------------------------------------------------------------------------
# Platt scaling (reuse from P45 pattern)
# ---------------------------------------------------------------------------

def _logit(p: float) -> float:
    p = max(CLIP_EPS, min(1.0 - CLIP_EPS, p))
    return math.log(p / (1.0 - p))


def _platt_apply(p: float, a: float, b: float) -> float:
    logit_val = a * _logit(p) + b
    return max(CLIP_EPS, min(1.0 - CLIP_EPS, 1.0 / (1.0 + math.exp(-logit_val / SIGMOID_K))))


def fit_platt(probs: list[float], labels: list[int]) -> tuple[float, float]:
    def nll(params: list[float]) -> float:
        a, b = params[0], params[1]
        total = 0.0
        for p, y in zip(probs, labels):
            cp = max(CLIP_EPS, min(1.0 - CLIP_EPS, _platt_apply(p, a, b)))
            total += -(y * math.log(cp) + (1 - y) * math.log(1 - cp))
        return total

    res = minimize(nll, x0=[1.0, 0.0], method="Nelder-Mead",
                   options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": 10000})
    return float(res.x[0]), float(res.x[1])


def apply_platt(probs: list[float], a: float, b: float) -> list[float]:
    return [_platt_apply(p, a, b) for p in probs]


# ---------------------------------------------------------------------------
# Isotonic regression (pure Python implementation)
# ---------------------------------------------------------------------------

def fit_isotonic(probs: list[float], labels: list[int]) -> tuple[list[float], list[float]]:
    """
    Pool Adjacent Violators (PAV) algorithm for isotonic regression.
    Returns (thresholds, calibrated_values) for prediction.

    Inputs are sorted by model_prob; output is monotone non-decreasing.
    Returns the isotonic mapping as parallel lists (knot_probs, knot_cals).
    """
    if not probs:
        return [], []

    # Sort by model_prob
    pairs = sorted(zip(probs, labels), key=lambda x: x[0])
    sorted_probs = [p for p, _ in pairs]
    sorted_labels = [y for _, y in pairs]
    n = len(sorted_probs)

    # PAV: merge blocks where monotonicity is violated
    # Each block: (mean_prob, mean_label, count)
    blocks: list[list[float | int]] = [[sorted_probs[i], float(sorted_labels[i]), 1] for i in range(n)]

    changed = True
    while changed:
        changed = False
        i = 0
        new_blocks: list[list[float | int]] = []
        while i < len(blocks):
            if i + 1 < len(blocks) and blocks[i][1] > blocks[i + 1][1]:
                # Merge
                b1, b2 = blocks[i], blocks[i + 1]
                total = b1[2] + b2[2]
                merged_prob = (b1[0] * b1[2] + b2[0] * b2[2]) / total
                merged_label = (b1[1] * b1[2] + b2[1] * b2[2]) / total
                new_blocks.append([merged_prob, merged_label, total])
                i += 2
                changed = True
            else:
                new_blocks.append(blocks[i])
                i += 1
        blocks = new_blocks

    # Extract knot points (mean prob → mean label)
    knot_probs = [float(b[0]) for b in blocks]
    knot_cals = [float(b[1]) for b in blocks]
    return knot_probs, knot_cals


def apply_isotonic(probs: list[float], knot_probs: list[float], knot_cals: list[float]) -> list[float]:
    """Apply isotonic calibration via linear interpolation between knots."""
    if not knot_probs:
        return list(probs)

    calibrated: list[float] = []
    for p in probs:
        if p <= knot_probs[0]:
            calibrated.append(max(CLIP_EPS, min(1.0 - CLIP_EPS, knot_cals[0])))
        elif p >= knot_probs[-1]:
            calibrated.append(max(CLIP_EPS, min(1.0 - CLIP_EPS, knot_cals[-1])))
        else:
            # Binary search for surrounding knots
            lo, hi = 0, len(knot_probs) - 1
            while lo + 1 < hi:
                mid = (lo + hi) // 2
                if knot_probs[mid] <= p:
                    lo = mid
                else:
                    hi = mid
            # Linear interpolation
            t = (p - knot_probs[lo]) / (knot_probs[hi] - knot_probs[lo] + 1e-15)
            interp = knot_cals[lo] + t * (knot_cals[hi] - knot_cals[lo])
            calibrated.append(max(CLIP_EPS, min(1.0 - CLIP_EPS, interp)))
    return calibrated


# ---------------------------------------------------------------------------
# Combined metrics helper
# ---------------------------------------------------------------------------

def _compare_metrics(
    raw_probs: list[float],
    platt_probs: list[float],
    iso_probs: list[float],
    labels: list[int],
) -> dict[str, float]:
    return {
        "raw_ece": round(compute_ece(raw_probs, labels), 6),
        "platt_ece": round(compute_ece(platt_probs, labels), 6),
        "isotonic_ece": round(compute_ece(iso_probs, labels), 6),
        "raw_brier": round(compute_brier(raw_probs, labels), 6),
        "platt_brier": round(compute_brier(platt_probs, labels), 6),
        "isotonic_brier": round(compute_brier(iso_probs, labels), 6),
    }


def _add_improvements(m: dict[str, float]) -> dict[str, float]:
    m["isotonic_vs_raw_ece_improvement"] = round(m["raw_ece"] - m["isotonic_ece"], 6)
    m["isotonic_vs_platt_ece_improvement"] = round(m["platt_ece"] - m["isotonic_ece"], 6)
    m["isotonic_vs_raw_brier_improvement"] = round(m["raw_brier"] - m["isotonic_brier"], 6)
    m["isotonic_vs_platt_brier_improvement"] = round(m["platt_brier"] - m["isotonic_brier"], 6)
    return m


# ---------------------------------------------------------------------------
# P46.A — Train/test 80/20 comparison
# ---------------------------------------------------------------------------

def train_test_comparison(records: list[CalibRecord]) -> dict[str, Any]:
    n = len(records)
    rng = random.Random(SEED)
    idx = list(range(n))
    rng.shuffle(idx)
    split = int(n * 0.8)
    train_idx, test_idx = idx[:split], idx[split:]

    train_probs = [records[i].model_prob for i in train_idx]
    train_labels = [records[i].actual_home_win for i in train_idx]
    test_raw = [records[i].model_prob for i in test_idx]
    test_labels = [records[i].actual_home_win for i in test_idx]

    # Platt
    pa, pb = fit_platt(train_probs, train_labels)
    test_platt = apply_platt(test_raw, pa, pb)

    # Isotonic
    kp, kc = fit_isotonic(train_probs, train_labels)
    test_iso = apply_isotonic(test_raw, kp, kc)

    metrics = _compare_metrics(test_raw, test_platt, test_iso, test_labels)
    _add_improvements(metrics)

    return {
        "train_n": len(train_idx),
        "test_n": len(test_idx),
        "split_seed": SEED,
        "platt_a": round(pa, 6),
        "platt_b": round(pb, 6),
        "isotonic_knot_count": len(kp),
        "isotonic_min_cal_prob": round(min(kc), 6) if kc else None,
        "isotonic_max_cal_prob": round(max(kc), 6) if kc else None,
        **metrics,
    }


# ---------------------------------------------------------------------------
# P46.B — 5-fold CV comparison
# ---------------------------------------------------------------------------

def _cv_classification(
    mean_iso_ece: float,
    mean_platt_ece: float,
    iso_beats_platt_count: int,
) -> str:
    diff = mean_platt_ece - mean_iso_ece
    if diff > 0.01 and iso_beats_platt_count >= 4:
        return "ISOTONIC_SUPERIOR"
    if abs(diff) < 0.01:
        return "ISOTONIC_COMPARABLE"
    if diff < -0.01 or iso_beats_platt_count <= 1:
        return "PLATT_PREFERRED"
    return "ISOTONIC_COMPARABLE"


def five_fold_cv(records: list[CalibRecord]) -> dict[str, Any]:
    n = len(records)
    rng = random.Random(SEED)
    idx = list(range(n))
    rng.shuffle(idx)

    folds: list[dict[str, Any]] = []
    fold_size = n // N_FOLDS

    for k in range(N_FOLDS):
        test_idx = idx[k * fold_size: (k + 1) * fold_size]
        train_idx = idx[:k * fold_size] + idx[(k + 1) * fold_size:]

        train_probs = [records[i].model_prob for i in train_idx]
        train_labels = [records[i].actual_home_win for i in train_idx]
        test_raw = [records[i].model_prob for i in test_idx]
        test_labels = [records[i].actual_home_win for i in test_idx]

        if len(test_idx) < 10:
            folds.append({"fold_id": k + 1, "train_n": len(train_idx), "test_n": len(test_idx), "classification": "SAMPLE_LIMITED"})
            continue

        pa, pb = fit_platt(train_probs, train_labels)
        test_platt = apply_platt(test_raw, pa, pb)
        kp, kc = fit_isotonic(train_probs, train_labels)
        test_iso = apply_isotonic(test_raw, kp, kc)

        m = _compare_metrics(test_raw, test_platt, test_iso, test_labels)
        _add_improvements(m)

        folds.append({
            "fold_id": k + 1,
            "train_n": len(train_idx),
            "test_n": len(test_idx),
            "platt_a": round(pa, 6),
            "platt_b": round(pb, 6),
            "isotonic_knot_count": len(kp),
            **m,
        })

    valid = [f for f in folds if "raw_ece" in f]
    if not valid:
        return {"folds": folds, "aggregate": {}, "classification": "SAMPLE_LIMITED"}

    agg_keys = ["raw_ece", "platt_ece", "isotonic_ece", "raw_brier", "platt_brier", "isotonic_brier"]
    agg: dict[str, Any] = {f"mean_{k}": round(sum(f[k] for f in valid) / len(valid), 6) for k in agg_keys}
    agg["fold_count"] = len(valid)

    iso_beats_ece = sum(1 for f in valid if f["isotonic_ece"] < f["platt_ece"])
    iso_beats_brier = sum(1 for f in valid if f["isotonic_brier"] < f["platt_brier"])
    agg["isotonic_beats_platt_fold_count_ece"] = iso_beats_ece
    agg["isotonic_beats_platt_fold_count_brier"] = iso_beats_brier

    cls = _cv_classification(agg["mean_isotonic_ece"], agg["mean_platt_ece"], iso_beats_ece)
    return {"folds": folds, "aggregate": agg, "classification": cls}


# ---------------------------------------------------------------------------
# P46.C — Walk-forward monthly comparison
# ---------------------------------------------------------------------------

def _wf_classification(results: list[dict[str, Any]]) -> str:
    valid = [r for r in results if "raw_ece" in r]
    if len(valid) < 2:
        return "SAMPLE_LIMITED"
    iso_better = sum(1 for r in valid if r["isotonic_ece"] < r["platt_ece"])
    platt_better = sum(1 for r in valid if r["platt_ece"] < r["isotonic_ece"])
    total = len(valid)
    if iso_better >= total * 0.6:
        return "ISOTONIC_WALK_FORWARD_HELPFUL"
    if platt_better >= total * 0.6:
        return "PLATT_WALK_FORWARD_PREFERRED"
    return "MIXED_RECALIBRATION_RESULT"


def walk_forward_monthly(records: list[CalibRecord]) -> dict[str, Any]:
    by_month: dict[str, list[CalibRecord]] = defaultdict(list)
    for r in records:
        by_month[r.month].append(r)

    months = sorted(by_month.keys())
    results: list[dict[str, Any]] = []

    for i in range(1, len(months)):
        train_months = months[:i]
        eval_month = months[i]
        train_recs = [r for m in train_months for r in by_month[m]]
        eval_recs = by_month[eval_month]

        if len(train_recs) < 10 or len(eval_recs) < 5:
            results.append({
                "train_months": train_months, "eval_month": eval_month,
                "train_n": len(train_recs), "eval_n": len(eval_recs),
                "classification": "SAMPLE_LIMITED",
            })
            continue

        train_probs = [r.model_prob for r in train_recs]
        train_labels = [r.actual_home_win for r in train_recs]
        eval_raw = [r.model_prob for r in eval_recs]
        eval_labels = [r.actual_home_win for r in eval_recs]

        pa, pb = fit_platt(train_probs, train_labels)
        eval_platt = apply_platt(eval_raw, pa, pb)
        kp, kc = fit_isotonic(train_probs, train_labels)
        eval_iso = apply_isotonic(eval_raw, kp, kc)

        m = _compare_metrics(eval_raw, eval_platt, eval_iso, eval_labels)
        _add_improvements(m)

        best_ece = "isotonic" if m["isotonic_ece"] < m["platt_ece"] else "platt"
        best_brier = "isotonic" if m["isotonic_brier"] < m["platt_brier"] else "platt"

        results.append({
            "train_months": train_months,
            "eval_month": eval_month,
            "train_n": len(train_recs),
            "eval_n": len(eval_recs),
            "platt_a": round(pa, 6),
            "platt_b": round(pb, 6),
            "isotonic_knot_count": len(kp),
            "best_method_by_ece": best_ece,
            "best_method_by_brier": best_brier,
            **m,
        })

    return {"walk_forward_results": results, "classification": _wf_classification(results)}


# ---------------------------------------------------------------------------
# P46.D — Final classification
# ---------------------------------------------------------------------------

def p46_final_classification(cv_cls: str, wf_cls: str) -> str:
    iso_signals = 0
    platt_signals = 0
    if "ISOTONIC_SUPERIOR" in cv_cls:
        iso_signals += 2
    elif "PLATT_PREFERRED" in cv_cls:
        platt_signals += 2
    if "ISOTONIC_WALK_FORWARD_HELPFUL" in wf_cls:
        iso_signals += 2
    elif "PLATT_WALK_FORWARD_PREFERRED" in wf_cls:
        platt_signals += 2

    if iso_signals > platt_signals and iso_signals >= 3:
        return "P46_ISOTONIC_SUPERIOR_DIAGNOSTIC"
    if platt_signals > iso_signals and platt_signals >= 3:
        return "P46_PLATT_PREFERRED_DIAGNOSTIC"
    if cv_cls == "SAMPLE_LIMITED" or wf_cls == "SAMPLE_LIMITED":
        return "P46_SAMPLE_LIMITED"
    return "P46_MIXED_RECALIBRATION_DIAGNOSTIC"


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _icon(s: str) -> str:
    m = {
        "ISOTONIC_SUPERIOR": "✅", "ISOTONIC_COMPARABLE": "⚠️", "PLATT_PREFERRED": "⚠️",
        "ISOTONIC_WALK_FORWARD_HELPFUL": "✅", "PLATT_WALK_FORWARD_PREFERRED": "⚠️",
        "MIXED_RECALIBRATION_RESULT": "⚠️", "SAMPLE_LIMITED": "⚠️",
        "P46_ISOTONIC_SUPERIOR_DIAGNOSTIC": "✅", "P46_PLATT_PREFERRED_DIAGNOSTIC": "⚠️",
        "P46_MIXED_RECALIBRATION_DIAGNOSTIC": "⚠️", "P46_SAMPLE_LIMITED": "⚠️",
    }
    return m.get(s, "")


def build_report(
    inv: dict[str, int],
    pilot: dict[str, Any],
    cv: dict[str, Any],
    wf: dict[str, Any],
    p46_cls: str,
) -> str:
    L: list[str] = []
    L.append("# P46 Isotonic Regression Recalibration Comparison")
    L.append("")
    L.append("**Date:** 2026-05-26")
    L.append("**Phase:** P46 (diagnostic-only, paper_only=true)")
    L.append("")

    L.append("## Governance Flags")
    for k, v in GOVERNANCE.items():
        L.append(f"- {k}: `{v}`")
    L.append("")

    L.append("## Baselines (P44/P45 Reference)")
    L.append(f"- P44 raw ECE: `{P44_RAW_ECE}`, raw Brier: `{P44_RAW_BRIER}`")
    L.append(f"- P45 Platt test ECE: `{P45_PLATT_TEST_ECE}`")
    L.append(f"- P45 Platt 5-fold mean ECE: `{P45_PLATT_CV_MEAN_ECE}`")
    L.append("")

    L.append("## Data Inventory")
    L.append(f"- Phase56 rows: {inv['phase56_rows']}")
    L.append(f"- Quality rows: {inv['quality_rows']}")
    L.append(f"- Joined rows: {inv['joined_rows']}")
    L.append(f"- Tier C rows (|delta|>=0.50): {inv['tier_c_rows']}")
    L.append("")

    L.append("## P46.A — Train/Test Comparison (80/20, seed=42)")
    L.append("")
    L.append(f"- Train n: {pilot['train_n']}, Test n: {pilot['test_n']}")
    L.append(f"- Isotonic knot count: {pilot['isotonic_knot_count']}")
    L.append(f"- Cal prob range: [{pilot['isotonic_min_cal_prob']}, {pilot['isotonic_max_cal_prob']}]")
    L.append("")
    L.append("| Method | ECE | Brier |")
    L.append("|--------|-----|-------|")
    L.append(f"| Raw sigmoid | {pilot['raw_ece']:.4f} | {pilot['raw_brier']:.4f} |")
    L.append(f"| Platt (P45) | {pilot['platt_ece']:.4f} | {pilot['platt_brier']:.4f} |")
    L.append(f"| Isotonic (P46) | {pilot['isotonic_ece']:.4f} | {pilot['isotonic_brier']:.4f} |")
    L.append(f"\n- Isotonic vs Platt ECE Δ: `{pilot['isotonic_vs_platt_ece_improvement']:+.4f}`")
    L.append(f"- Isotonic vs Raw ECE Δ: `{pilot['isotonic_vs_raw_ece_improvement']:+.4f}`")
    L.append("")

    L.append("## P46.B — 5-Fold CV Comparison")
    L.append("")
    L.append("| Fold | Train n | Test n | Raw ECE | Platt ECE | Iso ECE | Iso−Platt ECE Δ | Knots |")
    L.append("|------|---------|--------|---------|-----------|---------|-----------------|-------|")
    for f in cv["folds"]:
        if "raw_ece" not in f:
            L.append(f"| {f['fold_id']} | {f['train_n']} | {f['test_n']} | — | — | — | — | — |")
        else:
            L.append(
                f"| {f['fold_id']} | {f['train_n']} | {f['test_n']} | "
                f"{f['raw_ece']:.4f} | {f['platt_ece']:.4f} | {f['isotonic_ece']:.4f} | "
                f"{f['isotonic_vs_platt_ece_improvement']:+.4f} | {f['isotonic_knot_count']} |"
            )
    L.append("")
    agg = cv.get("aggregate", {})
    if agg:
        L.append(f"**CV Aggregate:**")
        L.append(f"| Mean Raw ECE | Mean Platt ECE | Mean Iso ECE | Iso beats Platt (folds) |")
        L.append(f"|---|---|---|---|")
        L.append(f"| {agg['mean_raw_ece']:.4f} | {agg['mean_platt_ece']:.4f} | {agg['mean_isotonic_ece']:.4f} | {agg['isotonic_beats_platt_fold_count_ece']}/{agg['fold_count']} |")
    cv_cls = cv.get("classification", "UNKNOWN")
    L.append(f"\n**CV Classification:** {_icon(cv_cls)} `{cv_cls}`")
    L.append("")

    L.append("## P46.C — Walk-Forward Monthly Comparison")
    L.append("")
    L.append("| Train Months | Eval Month | Eval n | Raw ECE | Platt ECE | Iso ECE | Best ECE |")
    L.append("|-------------|------------|--------|---------|-----------|---------|----------|")
    for r in wf["walk_forward_results"]:
        tm = "+".join(r["train_months"])
        if "raw_ece" not in r:
            L.append(f"| {tm} | {r['eval_month']} | {r['eval_n']} | — | — | — | — |")
        else:
            L.append(
                f"| {tm} | {r['eval_month']} | {r['eval_n']} | "
                f"{r['raw_ece']:.4f} | {r['platt_ece']:.4f} | {r['isotonic_ece']:.4f} | "
                f"{r['best_method_by_ece']} |"
            )
    wf_cls = wf.get("classification", "UNKNOWN")
    L.append(f"\n**Walk-Forward Classification:** {_icon(wf_cls)} `{wf_cls}`")
    L.append("")

    L.append("## Overfit Risk Discussion")
    knot_count = pilot.get("isotonic_knot_count", 0)
    if knot_count > len([r for r in ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]]) * 50:
        L.append("⚠️ High knot count suggests potential overfit. Walk-forward generalization test is critical.")
    else:
        L.append(f"✅ Isotonic knot count ({knot_count}) is reasonable relative to dataset size.")
    L.append("- Isotonic regression is monotone by construction but can memorize training data finely.")
    L.append("- Walk-forward evaluation tests temporal generalization on unseen future months.")
    L.append("- 5-fold CV provides out-of-fold ECE estimate; instability across folds indicates overfit.")
    L.append("")

    L.append("## Final P46 Classification")
    L.append(f"\n**P46 Classification:** {_icon(p46_cls)} `{p46_cls}`")
    L.append("")

    L.append("## Known Limitations")
    L.append("- 2024 closing-line data gap **remains unresolved** — analysis covers 2025 only.")
    L.append("- Isotonic calibration is diagnostic only; no recalibrated model is deployed.")
    L.append("- Both methods applied to closing-line edge dataset, not independent test set.")
    L.append("- **No production deployment. No champion replacement. Paper-only.**")
    L.append("")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[P46] Loading Tier C records...")
    records, inv = load_tier_c_records()
    print(f"[P46] Tier C n={len(records)}")

    print("[P46.A] Train/test comparison...")
    pilot = train_test_comparison(records)
    print(f"[P46.A] Raw ECE={pilot['raw_ece']}, Platt ECE={pilot['platt_ece']}, Iso ECE={pilot['isotonic_ece']}")
    print(f"[P46.A] Iso knots={pilot['isotonic_knot_count']}, cal range=[{pilot['isotonic_min_cal_prob']}, {pilot['isotonic_max_cal_prob']}]")

    print("[P46.B] 5-fold CV comparison...")
    cv = five_fold_cv(records)
    agg = cv.get("aggregate", {})
    if agg:
        print(f"[P46.B] Mean ECE: raw={agg['mean_raw_ece']}, platt={agg['mean_platt_ece']}, iso={agg['mean_isotonic_ece']}")
        print(f"[P46.B] Iso beats Platt (ECE): {agg['isotonic_beats_platt_fold_count_ece']}/5, CV cls={cv['classification']}")

    print("[P46.C] Walk-forward monthly comparison...")
    wf = walk_forward_monthly(records)
    print(f"[P46.C] WF classification: {wf['classification']}")

    p46_cls = p46_final_classification(cv["classification"], wf["classification"])
    assert p46_cls in ALLOWED_P46_CLASSIFICATIONS, f"Illegal P46 classification: {p46_cls}"
    print(f"[P46] Final classification: {p46_cls}")

    summary: dict[str, Any] = {
        "version": "p46_v1",
        "governance": GOVERNANCE,
        "baselines": {
            "p44_raw_ece": P44_RAW_ECE,
            "p44_raw_brier": P44_RAW_BRIER,
            "p45_platt_test_ece": P45_PLATT_TEST_ECE,
            "p45_platt_cv_mean_ece": P45_PLATT_CV_MEAN_ECE,
        },
        "data_inventory": inv,
        "tier_c_n": len(records),
        "p46a_pilot": pilot,
        "p46b_cv": cv,
        "p46c_walk_forward": wf,
        "p46_classification": p46_cls,
        "allowed_classifications": sorted(ALLOWED_P46_CLASSIFICATIONS),
        "framing_note": (
            "Isotonic vs Platt recalibration diagnostic on 2025 Tier C (|sp_fip_delta|>=0.50). "
            "No champion replacement. No production proposal. Paper-only. "
            "2024 closing-line data gap remains unresolved."
        ),
        "limitation": "2024_closing_line_data_unavailable",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[P46] Saved: {OUT_JSON}")

    report_md = build_report(inv, pilot, cv, wf, p46_cls)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md, encoding="utf-8")
    OUT_BETTINGPLAN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BETTINGPLAN.write_text(report_md, encoding="utf-8")
    print(f"[P46] Reports saved.")


if __name__ == "__main__":
    main()
