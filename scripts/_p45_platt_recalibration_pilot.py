#!/usr/bin/env python3
"""
P45 — Platt Scaling Recalibration Pilot (Paper-Only Diagnostic)

P44 baseline: ECE=0.0953, Brier=0.2481, MODERATE_MISCALIBRATED
Goal: diagnose whether Platt scaling reduces ECE without overfit.

Three sub-tasks:
  P45.A — 80/20 train/test Platt pilot
  P45.B — 5-fold cross-validation
  P45.C — Walk-forward monthly calibration (Apr→May, Apr+May→Jun, ...)

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
}

assert GOVERNANCE["paper_only"] is True
assert GOVERNANCE["diagnostic_only"] is True
assert GOVERNANCE["promotion_freeze"] is True
assert GOVERNANCE["kelly_deploy_allowed"] is False
assert GOVERNANCE["live_api_calls"] == 0
assert GOVERNANCE["tsl_crawler_modified"] is False
assert GOVERNANCE["champion_strategy_changed"] is False

ROOT = Path(__file__).resolve().parents[1]
FILE_2025_PHASE56 = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
FILE_2025_CLOSING = ROOT / "data/mlb_2025/mlb_odds_2025_real.csv"

OUT_JSON = ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"
OUT_REPORT = ROOT / "report/p45_platt_recalibration_pilot_20260526.md"
OUT_BETTINGPLAN = ROOT / "00-BettingPlan/20260526/p45_platt_recalibration_pilot_20260526.md"

SEED = 42
TIER_C_THRESHOLD = 0.50
SIGMOID_K = 0.8
CLIP_EPS = 1e-7
N_FOLDS = 5
MIN_BIN_FOR_ECE = 5
N_CALIB_BINS = 10

# P44 baseline reference
P44_BASELINE_ECE = 0.0953
P44_BASELINE_BRIER = 0.2481


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class CalibRecord:
    game_date: str
    month: str
    model_prob: float       # sigmoid(0.8 * sp_fip_delta)
    actual_home_win: int


# ---------------------------------------------------------------------------
# Data loading (mirrors P44 logic)
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


def _closing_market_home_prob(home_ml: str | None, away_ml: str | None) -> float | None:
    hp = _american_to_prob(home_ml)
    ap = _american_to_prob(away_ml)
    if hp is None or ap is None:
        return None
    s = hp + ap
    return (hp / s) if s > 0 else None


def load_tier_c_records() -> tuple[list[CalibRecord], dict[str, int]]:
    market: dict[tuple[str, str, str], dict[str, str]] = {}
    with FILE_2025_CLOSING.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (str(row.get("Date", "")), str(row.get("Away", "")), str(row.get("Home", "")))
            market[key] = dict(row)

    inv = {
        "phase56_rows": 0,
        "phase56_quality_rows": 0,
        "phase56_joined_rows": 0,
        "phase56_tier_c_rows": 0,
    }
    records: list[CalibRecord] = []

    with FILE_2025_PHASE56.open("r", encoding="utf-8") as f:
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
            inv["phase56_quality_rows"] += 1

            key = (str(r.get("game_date", "")), str(r.get("away_team", "")), str(r.get("home_team", "")))
            mrow = market.get(key)
            if mrow is None:
                continue
            if _closing_market_home_prob(mrow.get("Home ML"), mrow.get("Away ML")) is None:
                continue
            hs, aw = mrow.get("Home Score"), mrow.get("Away Score")
            if not hs or not aw or str(hs).strip() == "" or str(aw).strip() == "":
                continue
            inv["phase56_joined_rows"] += 1

            if abs(float(delta)) < TIER_C_THRESHOLD:
                continue
            inv["phase56_tier_c_rows"] += 1

            game_date = str(r.get("game_date", ""))
            records.append(CalibRecord(
                game_date=game_date,
                month=game_date[:7] if len(game_date) >= 7 else "unknown",
                model_prob=_sigmoid(float(delta)),
                actual_home_win=int(int(hs) > int(aw)),
            ))

    return records, inv


# ---------------------------------------------------------------------------
# Platt scaling core
# ---------------------------------------------------------------------------

def _logit(p: float) -> float:
    p = max(CLIP_EPS, min(1.0 - CLIP_EPS, p))
    return math.log(p / (1.0 - p))


def _platt_prob(model_prob: float, a: float, b: float) -> float:
    return _sigmoid((a * _logit(model_prob) + b) / SIGMOID_K)


def fit_platt(
    probs: list[float],
    labels: list[int],
) -> tuple[float, float]:
    """
    Fit Platt scaling via NLL minimization.
    Returns (platt_a, platt_b) for: calibrated = sigmoid(a * logit(p) + b)
    """
    def nll(params: list[float]) -> float:
        a, b = params[0], params[1]
        total = 0.0
        for p, y in zip(probs, labels):
            cp = _platt_prob(p, a, b)
            cp = max(CLIP_EPS, min(1.0 - CLIP_EPS, cp))
            total += -(y * math.log(cp) + (1 - y) * math.log(1 - cp))
        return total

    result = minimize(nll, x0=[1.0, 0.0], method="Nelder-Mead",
                      options={"xatol": 1e-8, "fatol": 1e-8, "maxiter": 10000})
    return float(result.x[0]), float(result.x[1])


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


def calibration_metrics(
    raw_probs: list[float],
    cal_probs: list[float],
    labels: list[int],
) -> dict[str, float]:
    raw_ece = compute_ece(raw_probs, labels)
    cal_ece = compute_ece(cal_probs, labels)
    raw_brier = compute_brier(raw_probs, labels)
    cal_brier = compute_brier(cal_probs, labels)
    return {
        "raw_ece": round(raw_ece, 6),
        "calibrated_ece": round(cal_ece, 6),
        "ece_improvement": round(raw_ece - cal_ece, 6),
        "raw_brier": round(raw_brier, 6),
        "calibrated_brier": round(cal_brier, 6),
        "brier_improvement": round(raw_brier - cal_brier, 6),
    }


# ---------------------------------------------------------------------------
# P45.A — Train/test 80/20 pilot
# ---------------------------------------------------------------------------

def train_test_platt_pilot(records: list[CalibRecord]) -> dict[str, Any]:
    n = len(records)
    rng = random.Random(SEED)
    indices = list(range(n))
    rng.shuffle(indices)
    split = int(n * 0.8)
    train_idx = indices[:split]
    test_idx = indices[split:]

    train_probs = [records[i].model_prob for i in train_idx]
    train_labels = [records[i].actual_home_win for i in train_idx]
    test_probs_raw = [records[i].model_prob for i in test_idx]
    test_labels = [records[i].actual_home_win for i in test_idx]

    a, b = fit_platt(train_probs, train_labels)
    test_probs_cal = [_platt_prob(p, a, b) for p in test_probs_raw]

    metrics = calibration_metrics(test_probs_raw, test_probs_cal, test_labels)
    metrics.update({"platt_a": round(a, 6), "platt_b": round(b, 6)})

    return {
        "train_n": len(train_idx),
        "test_n": len(test_idx),
        "split_seed": SEED,
        "platt_a": round(a, 6),
        "platt_b": round(b, 6),
        **metrics,
    }


# ---------------------------------------------------------------------------
# P45.B — 5-fold cross validation
# ---------------------------------------------------------------------------

def _classify_cv(mean_ece_imp: float, mean_cal_ece: float, mean_raw_ece: float) -> str:
    if mean_ece_imp > 0.02 and mean_cal_ece < mean_raw_ece:
        return "RECALIBRATION_HELPFUL"
    if abs(mean_ece_imp) <= 0.02:
        return "RECALIBRATION_NEUTRAL"
    if mean_cal_ece >= mean_raw_ece:
        return "RECALIBRATION_HARMFUL"
    return "RECALIBRATION_NEUTRAL"


def five_fold_cv(records: list[CalibRecord]) -> dict[str, Any]:
    n = len(records)
    rng = random.Random(SEED)
    indices = list(range(n))
    rng.shuffle(indices)

    fold_size = n // N_FOLDS
    folds_data: list[dict[str, Any]] = []

    for k in range(N_FOLDS):
        test_idx = indices[k * fold_size: (k + 1) * fold_size]
        train_idx = indices[:k * fold_size] + indices[(k + 1) * fold_size:]

        train_probs = [records[i].model_prob for i in train_idx]
        train_labels = [records[i].actual_home_win for i in train_idx]
        test_probs_raw = [records[i].model_prob for i in test_idx]
        test_labels = [records[i].actual_home_win for i in test_idx]

        if len(test_idx) < 10:
            folds_data.append({
                "fold_id": k + 1,
                "train_n": len(train_idx),
                "test_n": len(test_idx),
                "classification": "SAMPLE_LIMITED",
            })
            continue

        a, b = fit_platt(train_probs, train_labels)
        test_probs_cal = [_platt_prob(p, a, b) for p in test_probs_raw]
        metrics = calibration_metrics(test_probs_raw, test_probs_cal, test_labels)

        folds_data.append({
            "fold_id": k + 1,
            "train_n": len(train_idx),
            "test_n": len(test_idx),
            "platt_a": round(a, 6),
            "platt_b": round(b, 6),
            **metrics,
        })

    valid_folds = [f for f in folds_data if "raw_ece" in f]
    if not valid_folds:
        return {"folds": folds_data, "aggregate": {}, "classification": "SAMPLE_LIMITED"}

    mean_raw_ece = sum(f["raw_ece"] for f in valid_folds) / len(valid_folds)
    mean_cal_ece = sum(f["calibrated_ece"] for f in valid_folds) / len(valid_folds)
    mean_ece_imp = sum(f["ece_improvement"] for f in valid_folds) / len(valid_folds)
    mean_raw_brier = sum(f["raw_brier"] for f in valid_folds) / len(valid_folds)
    mean_cal_brier = sum(f["calibrated_brier"] for f in valid_folds) / len(valid_folds)
    mean_brier_imp = sum(f["brier_improvement"] for f in valid_folds) / len(valid_folds)

    cls = _classify_cv(mean_ece_imp, mean_cal_ece, mean_raw_ece)

    return {
        "folds": folds_data,
        "aggregate": {
            "fold_count": len(valid_folds),
            "mean_raw_ece": round(mean_raw_ece, 6),
            "mean_calibrated_ece": round(mean_cal_ece, 6),
            "mean_ece_improvement": round(mean_ece_imp, 6),
            "mean_raw_brier": round(mean_raw_brier, 6),
            "mean_calibrated_brier": round(mean_cal_brier, 6),
            "mean_brier_improvement": round(mean_brier_imp, 6),
        },
        "classification": cls,
    }


# ---------------------------------------------------------------------------
# P45.C — Walk-forward monthly calibration
# ---------------------------------------------------------------------------

def _classify_wf(results: list[dict[str, Any]]) -> str:
    valid = [r for r in results if "raw_ece" in r]
    if len(valid) < 2:
        return "SAMPLE_LIMITED"
    helpful = sum(1 for r in valid if r["ece_improvement"] > 0.005)
    harmful = sum(1 for r in valid if r["ece_improvement"] < -0.005)
    if helpful > harmful and helpful >= len(valid) // 2:
        return "WALK_FORWARD_HELPFUL"
    if harmful > helpful:
        return "WALK_FORWARD_HARMFUL"
    return "WALK_FORWARD_MIXED"


def walk_forward_monthly(records: list[CalibRecord]) -> dict[str, Any]:
    from collections import defaultdict
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

        train_probs = [r.model_prob for r in train_recs]
        train_labels = [r.actual_home_win for r in train_recs]
        eval_probs_raw = [r.model_prob for r in eval_recs]
        eval_labels = [r.actual_home_win for r in eval_recs]

        if len(train_recs) < 10 or len(eval_recs) < 5:
            results.append({
                "train_months": train_months,
                "eval_month": eval_month,
                "train_n": len(train_recs),
                "eval_n": len(eval_recs),
                "classification": "SAMPLE_LIMITED",
            })
            continue

        a, b = fit_platt(train_probs, train_labels)
        eval_probs_cal = [_platt_prob(p, a, b) for p in eval_probs_raw]
        metrics = calibration_metrics(eval_probs_raw, eval_probs_cal, eval_labels)

        results.append({
            "train_months": train_months,
            "eval_month": eval_month,
            "train_n": len(train_recs),
            "eval_n": len(eval_recs),
            "platt_a": round(a, 6),
            "platt_b": round(b, 6),
            **metrics,
        })

    cls = _classify_wf(results)
    return {"walk_forward_results": results, "classification": cls}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _cls_icon(cls: str) -> str:
    icons = {
        "RECALIBRATION_HELPFUL": "✅",
        "RECALIBRATION_NEUTRAL": "⚠️",
        "RECALIBRATION_HARMFUL": "❌",
        "WALK_FORWARD_HELPFUL": "✅",
        "WALK_FORWARD_MIXED": "⚠️",
        "WALK_FORWARD_HARMFUL": "❌",
        "SAMPLE_LIMITED": "⚠️",
    }
    return icons.get(cls, "")


def build_report(
    inv: dict[str, int],
    pilot: dict[str, Any],
    cv: dict[str, Any],
    wf: dict[str, Any],
    p45_cls: str,
) -> str:
    lines: list[str] = []
    lines.append("# P45 Platt Scaling Recalibration Pilot")
    lines.append("")
    lines.append("**Date:** 2026-05-26")
    lines.append("**Phase:** P45 (diagnostic-only, paper_only=true)")
    lines.append("")

    lines.append("## Governance Flags")
    for k, v in GOVERNANCE.items():
        lines.append(f"- {k}: `{v}`")
    lines.append("")

    lines.append("## P44 Baseline Reference")
    lines.append(f"- ECE: `{P44_BASELINE_ECE}`")
    lines.append(f"- Brier: `{P44_BASELINE_BRIER}`")
    lines.append(f"- Classification: `MODERATE_MISCALIBRATED`")
    lines.append("")

    lines.append("## Data Inventory")
    lines.append(f"- Phase56 rows: {inv['phase56_rows']}")
    lines.append(f"- Quality rows: {inv['phase56_quality_rows']}")
    lines.append(f"- Joined rows: {inv['phase56_joined_rows']}")
    lines.append(f"- Tier C rows (|delta|>=0.50): {inv['phase56_tier_c_rows']}")
    lines.append("")

    lines.append("## P45.A — Train/Test Platt Pilot (80/20)")
    lines.append("")
    lines.append(f"- Train n: {pilot['train_n']}, Test n: {pilot['test_n']}")
    lines.append(f"- platt_a: `{pilot['platt_a']}`, platt_b: `{pilot['platt_b']}`")
    lines.append(f"- Raw ECE (test): `{pilot['raw_ece']}`")
    lines.append(f"- Calibrated ECE (test): `{pilot['calibrated_ece']}`")
    lines.append(f"- ECE Improvement: `{pilot['ece_improvement']}`")
    lines.append(f"- Raw Brier (test): `{pilot['raw_brier']}`")
    lines.append(f"- Calibrated Brier (test): `{pilot['calibrated_brier']}`")
    lines.append(f"- Brier Improvement: `{pilot['brier_improvement']}`")
    lines.append("")

    lines.append("## P45.B — 5-Fold Cross Validation")
    lines.append("")
    lines.append("| Fold | Train n | Test n | Raw ECE | Cal ECE | ECE Δ | Raw Brier | Cal Brier |")
    lines.append("|------|---------|--------|---------|---------|-------|-----------|-----------|")
    for f in cv["folds"]:
        if "raw_ece" not in f:
            lines.append(f"| {f['fold_id']} | {f['train_n']} | {f['test_n']} | — | — | — | — | — |")
        else:
            lines.append(
                f"| {f['fold_id']} | {f['train_n']} | {f['test_n']} | "
                f"{f['raw_ece']:.4f} | {f['calibrated_ece']:.4f} | "
                f"{f['ece_improvement']:+.4f} | {f['raw_brier']:.4f} | {f['calibrated_brier']:.4f} |"
            )
    lines.append("")
    agg = cv.get("aggregate", {})
    if agg:
        lines.append(f"**CV Aggregate:**")
        lines.append(f"- Mean Raw ECE: `{agg['mean_raw_ece']}`")
        lines.append(f"- Mean Calibrated ECE: `{agg['mean_calibrated_ece']}`")
        lines.append(f"- Mean ECE Improvement: `{agg['mean_ece_improvement']}`")
        lines.append(f"- Mean Brier Improvement: `{agg['mean_brier_improvement']}`")
    cv_cls = cv.get("classification", "UNKNOWN")
    lines.append(f"- **CV Classification:** {_cls_icon(cv_cls)} `{cv_cls}`")
    lines.append("")

    lines.append("## P45.C — Walk-Forward Monthly Calibration")
    lines.append("")
    lines.append("| Train Months | Eval Month | Train n | Eval n | Raw ECE | Cal ECE | ECE Δ |")
    lines.append("|-------------|------------|---------|--------|---------|---------|-------|")
    for r in wf["walk_forward_results"]:
        tm = "+".join(r["train_months"])
        if "raw_ece" not in r:
            lines.append(f"| {tm} | {r['eval_month']} | {r['train_n']} | {r['eval_n']} | — | — | — |")
        else:
            lines.append(
                f"| {tm} | {r['eval_month']} | {r['train_n']} | {r['eval_n']} | "
                f"{r['raw_ece']:.4f} | {r['calibrated_ece']:.4f} | {r['ece_improvement']:+.4f} |"
            )
    wf_cls = wf.get("classification", "UNKNOWN")
    lines.append(f"\n**Walk-Forward Classification:** {_cls_icon(wf_cls)} `{wf_cls}`")
    lines.append("")

    lines.append("## Overfit Risk Discussion")
    lines.append("")
    a_val = abs(pilot.get("platt_a", 1.0))
    b_val = abs(pilot.get("platt_b", 0.0))
    if a_val > 3.0 or b_val > 2.0:
        lines.append("⚠️ Platt coefficients show potential overfit: |a| > 3 or |b| > 2.")
    else:
        lines.append("✅ Platt coefficients are within reasonable range (|a| <= 3, |b| <= 2).")
    lines.append("- 5-fold CV provides out-of-fold ECE estimate, reducing overfit risk.")
    lines.append("- Walk-forward evaluation tests temporal generalization.")
    lines.append("- Monthly walk-forward uses only prior data for fitting (no look-ahead).")
    lines.append("")

    lines.append("## Final P45 Classification")
    lines.append(f"\n**P45 Classification:** `{p45_cls}`")
    lines.append("")

    lines.append("## Known Limitations")
    lines.append("- 2024 closing-line data gap **remains unresolved** — analysis covers 2025 only.")
    lines.append("- Platt scaling is diagnostic only; no recalibrated model is deployed.")
    lines.append("- ECE computed on same dataset as edge; not an independent market test.")
    lines.append("- **No production deployment proposal. No champion replacement. Paper-only.**")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

def _p45_classification(
    cv_cls: str,
    wf_cls: str,
    mean_cal_ece: float | None,
    pilot_ece_imp: float,
) -> str:
    if cv_cls == "RECALIBRATION_HARMFUL" or wf_cls == "WALK_FORWARD_HARMFUL":
        return "P45_RECALIBRATION_HARMFUL"
    if cv_cls == "RECALIBRATION_HELPFUL" and wf_cls == "WALK_FORWARD_HELPFUL":
        if mean_cal_ece is not None and mean_cal_ece < 0.05:
            return "P45_RECALIBRATION_HELPFUL_WELL_CALIBRATED"
        return "P45_RECALIBRATION_HELPFUL"
    if cv_cls == "RECALIBRATION_NEUTRAL" and wf_cls == "WALK_FORWARD_MIXED":
        return "P45_RECALIBRATION_MARGINAL"
    return "P45_RECALIBRATION_MIXED"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[P45] Loading Tier C records...")
    records, inv = load_tier_c_records()
    print(f"[P45] Tier C n={len(records)}")

    print("[P45.A] Train/test Platt pilot...")
    pilot = train_test_platt_pilot(records)
    print(f"[P45.A] platt_a={pilot['platt_a']}, platt_b={pilot['platt_b']}")
    print(f"[P45.A] Raw ECE={pilot['raw_ece']}, Cal ECE={pilot['calibrated_ece']}, Δ={pilot['ece_improvement']}")

    print("[P45.B] 5-fold CV...")
    cv = five_fold_cv(records)
    agg = cv.get("aggregate", {})
    if agg:
        print(f"[P45.B] Mean ECE: raw={agg['mean_raw_ece']}, cal={agg['mean_calibrated_ece']}, CV cls={cv['classification']}")

    print("[P45.C] Walk-forward monthly calibration...")
    wf = walk_forward_monthly(records)
    print(f"[P45.C] Walk-forward classification: {wf['classification']}")

    mean_cal_ece = agg.get("mean_calibrated_ece") if agg else None
    p45_cls = _p45_classification(
        cv["classification"], wf["classification"],
        mean_cal_ece, pilot["ece_improvement"]
    )
    print(f"[P45] Final classification: {p45_cls}")

    summary = {
        "version": "p45_v1",
        "governance": GOVERNANCE,
        "p44_baseline": {
            "ece": P44_BASELINE_ECE,
            "brier": P44_BASELINE_BRIER,
            "classification": "MODERATE_MISCALIBRATED",
        },
        "data_inventory": inv,
        "tier_c_n": len(records),
        "p45a_pilot": pilot,
        "p45b_cv": cv,
        "p45c_walk_forward": wf,
        "p45_classification": p45_cls,
        "framing_note": (
            "Platt scaling diagnostic on 2025 Tier C (|sp_fip_delta| >= 0.50). "
            "No champion replacement. No production proposal. Paper-only. "
            "2024 closing-line data gap remains unresolved."
        ),
        "limitation": "2024_closing_line_data_unavailable",
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[P45] Saved: {OUT_JSON}")

    report_md = build_report(inv, pilot, cv, wf, p45_cls)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md, encoding="utf-8")
    print(f"[P45] Saved report: {OUT_REPORT}")

    OUT_BETTINGPLAN.parent.mkdir(parents=True, exist_ok=True)
    OUT_BETTINGPLAN.write_text(report_md, encoding="utf-8")
    print(f"[P45] Saved betting plan: {OUT_BETTINGPLAN}")


if __name__ == "__main__":
    main()
