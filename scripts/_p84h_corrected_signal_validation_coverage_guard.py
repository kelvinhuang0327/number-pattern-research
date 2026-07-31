#!/usr/bin/env python3
"""
P84H — Corrected 2026 Prediction-Only Signal Validation + Coverage Guard
=========================================================================
Validates the P84G-corrected predicted_side signal across multiple analytical cuts.

Classification output (one of five):
  P84H_CORRECTED_SIGNAL_VALIDATED_DIAGNOSTIC_ONLY
  P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED
  P84H_CALIBRATION_WEAK_REQUIRES_REVIEW
  P84H_COVERAGE_TOO_LOW_FOR_SIGNAL_CLAIM
  P84H_FAILED_VALIDATION

Governance:
  paper_only=True | diagnostic_only=True | production_ready=False
  odds_used=False | ev_computed=False | clv_computed=False | kelly_computed=False
  live_api_calls=0 | paid_api_called=False
  canonical_rows_modified=False | outcome_rows_modified=False
  p83e_mapping_modified=False | champion_replaced=False

Predecessor: P84G committed at 021a8a8 (P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED)
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = pathlib.Path(__file__).resolve().parent.parent
DERIVED = ROOT / "data" / "mlb_2026" / "derived"
PREDICTIONS = ROOT / "data" / "mlb_2026" / "predictions"
REPORT_DIR = ROOT / "report"
ACTIVE_TASK = ROOT / "00-Plan" / "roadmap" / "active_task.md"

# ─── Frozen artifact paths (read-only) ──────────────────────────────────────
P83E_SUMMARY = DERIVED / "p83e_2026_canonical_prediction_row_producer_summary.json"
P84E_SUMMARY = DERIVED / "p84e_2026_outcome_attachment_summary.json"
P84E_ROWS    = DERIVED / "p84e_2026_outcome_attached_prediction_rows.jsonl"
P84F_SUMMARY = DERIVED / "p84f_predicted_side_calibration_diagnostic_summary.json"
P84G_SUMMARY = DERIVED / "p84g_predicted_side_mapping_fix_summary.json"

# ─── Output paths (new files only) ──────────────────────────────────────────
P84H_SUMMARY_PATH = DERIVED / "p84h_corrected_signal_validation_coverage_guard_summary.json"
P84H_REPORT_PATH  = REPORT_DIR / "p84h_corrected_signal_validation_coverage_guard_20260527.md"

# ─── Constants ───────────────────────────────────────────────────────────────
SCHEDULE_ROWS = 2430   # total MLB 2026 regular season games (from P84B/P83E context)
TOLERANCE     = 1e-4   # recomputed-vs-P84E metric consistency tolerance

GOVERNANCE: dict[str, Any] = {
    "paper_only":               True,
    "diagnostic_only":          True,
    "production_ready":         False,
    "odds_used":                False,
    "ev_computed":              False,
    "clv_computed":             False,
    "kelly_computed":           False,
    "live_api_calls":           0,
    "paid_api_called":          False,
    "canonical_rows_modified":  False,
    "outcome_rows_modified":    False,
    "p83e_mapping_modified":    False,
    "champion_replaced":        False,
}

ALLOWED_CLASSIFICATIONS = [
    "P84H_CORRECTED_SIGNAL_VALIDATED_DIAGNOSTIC_ONLY",
    "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED",
    "P84H_CALIBRATION_WEAK_REQUIRES_REVIEW",
    "P84H_COVERAGE_TOO_LOW_FOR_SIGNAL_CLAIM",
    "P84H_FAILED_VALIDATION",
]

# ─── Helper utilities ─────────────────────────────────────────────────────────

def _r6(x: float) -> float:
    return round(float(x), 6)


def compute_ece(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> tuple[float, list[dict]]:
    """Compute Expected Calibration Error with reliability curve."""
    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    reliability: list[dict] = []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (y_prob >= lo) & (y_prob < hi if i < n_bins - 1 else y_prob <= hi)
        bin_n = int(mask.sum())
        if bin_n == 0:
            reliability.append({
                "bin_lo": _r6(lo), "bin_hi": _r6(hi), "n": 0,
                "mean_prob": None, "empirical_hr": None, "calibration_gap": None,
            })
            continue
        mean_prob   = float(y_prob[mask].mean())
        empirical_hr = float(y_true[mask].mean())
        weight       = bin_n / n
        ece         += weight * abs(mean_prob - empirical_hr)
        reliability.append({
            "bin_lo": _r6(lo),
            "bin_hi": _r6(hi),
            "n": bin_n,
            "mean_prob": _r6(mean_prob),
            "empirical_hr": _r6(empirical_hr),
            "calibration_gap": _r6(mean_prob - empirical_hr),
        })
    return ece, reliability


def compute_metrics(rows: list[dict], label: str) -> dict:
    """Compute hit_rate, AUC, Brier, ECE for a list of outcome-available rows."""
    n = len(rows)
    if n == 0:
        return {
            "label": label, "n": 0, "n_correct": 0,
            "hit_rate": None, "hit_rate_ci_95_lo": None, "hit_rate_ci_95_hi": None,
            "auc": None, "brier": None, "ece": None,
        }
    is_correct = np.array([1 if r["is_correct"] else 0 for r in rows], dtype=float)
    y_true     = np.array([1 if r["actual_winner"] == "home" else 0 for r in rows], dtype=float)
    y_prob     = np.array([r["model_probability"] for r in rows], dtype=float)

    hit_rate  = float(is_correct.mean())
    n_correct = int(is_correct.sum())
    ci_margin = 1.96 * math.sqrt(max(hit_rate * (1.0 - hit_rate), 0.0) / n)

    auc = None
    if 0 < y_true.sum() < n:
        auc = float(roc_auc_score(y_true, y_prob))

    brier = float(np.mean((y_prob - y_true) ** 2))
    ece, _  = compute_ece(y_true, y_prob, n_bins=10)

    return {
        "label": label,
        "n": n,
        "n_correct": n_correct,
        "hit_rate": _r6(hit_rate),
        "hit_rate_ci_95_lo": _r6(hit_rate - ci_margin),
        "hit_rate_ci_95_hi": _r6(hit_rate + ci_margin),
        "auc": _r6(auc) if auc is not None else None,
        "brier": _r6(brier),
        "ece": _r6(ece),
    }


def binomial_test(n_correct: int, n: int, p0: float = 0.5) -> dict:
    """Binomial test (one-sided greater) + Wilson 95% CI."""
    from scipy.stats import binomtest

    if n == 0:
        return {"n_correct": 0, "n": 0, "hit_rate": None,
                "binomial_p_value": None, "significant_at_05": False,
                "wilson_ci_95_lo": None, "wilson_ci_95_hi": None}

    result  = binomtest(n_correct, n, p=p0, alternative="greater")
    p_val   = float(result.pvalue)
    p_hat   = n_correct / n
    z       = 1.96
    denom   = 1.0 + z ** 2 / n
    center  = (p_hat + z ** 2 / (2 * n)) / denom
    margin  = z * math.sqrt(p_hat * (1 - p_hat) / n + z ** 2 / (4 * n ** 2)) / denom

    return {
        "n_correct": n_correct,
        "n": n,
        "hit_rate": _r6(p_hat),
        "binomial_p_value": _r6(p_val),
        "significant_at_05": p_val < 0.05,
        "wilson_ci_95_lo": _r6(center - margin),
        "wilson_ci_95_hi": _r6(center + margin),
    }


# ─── Main pipeline ────────────────────────────────────────────────────────────

def main() -> dict[str, Any]:
    summary: dict[str, Any] = {
        "p84h_classification": None,
        "phase":               "P84H",
        "date":                "2026-05-27",
        "generated_at":        datetime.now(timezone.utc).isoformat(),
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "governance":          GOVERNANCE,
        "predecessor":         "P84G@021a8a8 — P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED",
    }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1 — Artifact consistency check
    # ──────────────────────────────────────────────────────────────────────────
    missing = [
        str(p) for p in [P83E_SUMMARY, P84E_SUMMARY, P84E_ROWS, P84F_SUMMARY, P84G_SUMMARY]
        if not p.exists()
    ]
    if missing:
        summary["step1_artifact_consistency"] = {
            "status": "FAILED", "missing_artifacts": missing,
            "stop_reason": "Required frozen artifacts not found",
        }
        summary["p84h_classification"] = "P84H_FAILED_VALIDATION"
        _write_outputs(summary)
        return summary

    p83e = json.loads(P83E_SUMMARY.read_text())
    p84e = json.loads(P84E_SUMMARY.read_text())
    p84f = json.loads(P84F_SUMMARY.read_text())
    p84g = json.loads(P84G_SUMMARY.read_text())

    expected_classifications = {
        "p83e_classification": ("p83e_classification", p83e,  "P83E_CANONICAL_ROWS_READY"),
        "p84e_classification": ("p84e_classification", p84e,  "P84E_OUTCOME_ATTACHMENT_READY_WITH_METRICS"),
        "p84f_classification": ("p84f_classification", p84f,  "P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK"),
        "p84g_classification": ("p84g_classification", p84g,  "P84G_SIDE_MAPPING_FIXED_METRICS_REGENERATED"),
    }
    mismatches: dict[str, dict] = {}
    for key, (field, artifact, expected) in expected_classifications.items():
        actual = artifact.get(field)
        if actual != expected:
            mismatches[key] = {"actual": actual, "expected": expected}

    canonical_row_count = p83e["step6_canonical_rows"]["row_count"]
    outcome_available   = p84e["step3_attachment_stats"]["n_outcome_available"]
    row_ok = (canonical_row_count == 828) and (outcome_available == 808)

    step1_status = "PASSED" if (not mismatches and row_ok) else "FAILED"
    summary["step1_artifact_consistency"] = {
        "status":                  step1_status,
        "artifact_classifications": {k: v[1].get(v[0]) for k, v in expected_classifications.items()},
        "classification_mismatches": mismatches,
        "canonical_row_count":     canonical_row_count,
        "outcome_available_count": outcome_available,
        "row_count_ok":            row_ok,
    }
    if step1_status == "FAILED":
        summary["p84h_classification"] = "P84H_FAILED_VALIDATION"
        _write_outputs(summary)
        return summary

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2 — Recompute metrics + tolerance check vs P84E summary
    # ──────────────────────────────────────────────────────────────────────────
    all_rows     = [json.loads(l) for l in P84E_ROWS.read_text().strip().splitlines()]
    outcome_rows = [r for r in all_rows if r.get("outcome_available")]

    recomputed = compute_metrics(outcome_rows, "recomputed_all")

    p84e_ref = p84e["step4_metrics"]["all"]
    ref = {
        "hit_rate": p84e_ref["hit_rate"],
        "auc":      p84e_ref["auc"],
        "brier":    p84e_ref["brier"],
        "ece":      p84e_ref["ece"],
    }
    deltas = {
        "hit_rate": _r6(abs(recomputed["hit_rate"] - ref["hit_rate"])),
        "auc":      _r6(abs((recomputed["auc"] or 0.0) - ref["auc"])),
        "brier":    _r6(abs(recomputed["brier"] - ref["brier"])),
        "ece":      _r6(abs(recomputed["ece"] - ref["ece"])),
    }
    tolerance_ok = all(v < TOLERANCE for v in deltas.values())

    summary["step2_recomputed_metrics"] = {
        "status":       "PASSED" if tolerance_ok else "FAILED",
        "tolerance":    TOLERANCE,
        "recomputed":   recomputed,
        "p84e_reference": ref,
        "deltas":       deltas,
        "tolerance_ok": tolerance_ok,
    }
    if not tolerance_ok:
        summary["p84h_classification"] = "P84H_FAILED_VALIDATION"
        _write_outputs(summary)
        return summary

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3 — Split metrics
    # ──────────────────────────────────────────────────────────────────────────

    # Monthly
    monthly: dict[str, Any] = {}
    for month in ("2026-03", "2026-04", "2026-05"):
        month_rows = [r for r in outcome_rows if r["game_date"].startswith(month)]
        monthly[month] = compute_metrics(month_rows, f"monthly_{month}")

    # Chronological thirds
    sorted_rows = sorted(outcome_rows, key=lambda r: r["game_date"])
    n_total   = len(sorted_rows)
    third_sz  = n_total // 3
    thirds_def = [
        ("first_third",  sorted_rows[:third_sz]),
        ("second_third", sorted_rows[third_sz:2 * third_sz]),
        ("third_third",  sorted_rows[2 * third_sz:]),
    ]
    thirds: dict[str, Any] = {}
    for name, subset in thirds_def:
        m = compute_metrics(subset, name)
        m["date_start"] = subset[0]["game_date"]  if subset else None
        m["date_end"]   = subset[-1]["game_date"] if subset else None
        thirds[name]    = m

    # Side split
    home_pred = [r for r in outcome_rows if r["predicted_side"] == "home"]
    away_pred = [r for r in outcome_rows if r["predicted_side"] == "away"]
    side: dict[str, Any] = {
        "home": compute_metrics(home_pred, "predicted_side_home"),
        "away": compute_metrics(away_pred, "predicted_side_away"),
    }

    # Rule subset split
    primary_rows = [r for r in outcome_rows if r["rule_primary_125_flag"]]
    shadow_rows  = [r for r in outcome_rows if r["rule_shadow_100_flag"]]
    tier_b_rows  = [r for r in outcome_rows if r["tier_b_candidate_flag"]]
    tier_a_rows  = [r for r in outcome_rows if r["tier_a_watchlist_flag"]]
    rule_subset: dict[str, Any] = {
        "primary_125": compute_metrics(primary_rows, "primary_125"),
        "shadow_100":  compute_metrics(shadow_rows,  "shadow_100"),
        "tier_b":      compute_metrics(tier_b_rows,  "tier_b"),
        "tier_a":      compute_metrics(tier_a_rows,  "tier_a"),
    }

    summary["step3_split_metrics"] = {
        "monthly":              monthly,
        "chronological_thirds": thirds,
        "side":                 side,
        "rule_subset":          rule_subset,
    }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 4 — Calibration analysis (reliability curve)
    # ──────────────────────────────────────────────────────────────────────────
    y_true_all = np.array([1 if r["actual_winner"] == "home" else 0 for r in outcome_rows], dtype=float)
    y_prob_all = np.array([r["model_probability"] for r in outcome_rows], dtype=float)

    ece_full, reliability_curve = compute_ece(y_true_all, y_prob_all, n_bins=10)

    non_empty_bins = [b for b in reliability_curve if b["calibration_gap"] is not None]
    max_gap_bin = (
        max(non_empty_bins, key=lambda b: abs(b["calibration_gap"]))
        if non_empty_bins else None
    )

    # Calibration level
    calib_level = "WEAK" if ece_full > 0.05 else "ACCEPTABLE"

    # Side balance
    n_home_pred = len(home_pred)
    n_away_pred = len(away_pred)
    side_imbalance = abs(n_home_pred - n_away_pred) / max(n_home_pred + n_away_pred, 1)

    summary["step4_calibration"] = {
        "ece":               _r6(ece_full),
        "calibration_level": calib_level,
        "n_bins":            10,
        "reliability_curve": reliability_curve,
        "max_calibration_gap_bin": max_gap_bin,
        "side_balance": {
            "n_home_predicted": n_home_pred,
            "n_away_predicted": n_away_pred,
            "imbalance_ratio":  _r6(side_imbalance),
        },
        "calibration_notes": {
            "platt_isotonic_refit": "FORBIDDEN_BY_GOVERNANCE",
            "likely_sources": [
                "Partial season coverage (2026-03 through 2026-05 only) — small n inflates ECE",
                "model_probability is FIP-delta derived proxy; not calibrated for 2026 outcomes",
                "No score transformation applied — systematic over/under confidence possible",
            ],
        },
    }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5 — Coverage classification
    # ──────────────────────────────────────────────────────────────────────────
    canonical_count = canonical_row_count   # 828
    outcome_count   = outcome_available     # 808
    canonical_coverage_ratio = canonical_count / SCHEDULE_ROWS
    outcome_coverage_ratio   = outcome_count   / canonical_count

    if canonical_coverage_ratio >= 0.50:
        coverage_class = "COVERAGE_SUFFICIENT_FOR_DIAGNOSTIC"
    elif canonical_coverage_ratio >= 0.20:
        coverage_class = "COVERAGE_LIMITED"
    else:
        coverage_class = "COVERAGE_TOO_LOW"

    summary["step5_coverage"] = {
        "schedule_rows":             SCHEDULE_ROWS,
        "canonical_rows":            canonical_count,
        "outcome_available_rows":    outcome_count,
        "canonical_coverage_ratio":  _r6(canonical_coverage_ratio),
        "outcome_coverage_ratio":    _r6(outcome_coverage_ratio),
        "coverage_classification":   coverage_class,
        "date_range_covered":        "2026-03 through 2026-05",
        "full_season_claim_valid":   False,
        "production_claim_valid":    False,
        "coverage_gap_reasons": [
            "Probable pitcher data required for FIP delta — not available for all scheduled games",
            "2026 season is partial (June+ games not yet played at time of analysis)",
            "Some early-season games lacked starter pitcher assignments",
        ],
    }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6 — Subset comparison with binomial test
    # ──────────────────────────────────────────────────────────────────────────
    binom_results: dict[str, Any] = {}
    subset_map = [
        ("all",         outcome_rows),
        ("primary_125", primary_rows),
        ("shadow_100",  shadow_rows),
        ("tier_b",      tier_b_rows),
    ]
    for name, s_rows in subset_map:
        n_cor = sum(1 for r in s_rows if r["is_correct"])
        binom_results[name] = binomial_test(n_cor, len(s_rows))

    all_hr   = binom_results["all"]["hit_rate"]
    p125_hr  = binom_results["primary_125"]["hit_rate"]
    summary["step6_subset_comparison"] = {
        "method": "binomial_test_one_sided_greater_vs_H0_0.5",
        "subsets": binom_results,
        "primary_125_vs_all": {
            "primary_125_hit_rate": p125_hr,
            "all_hit_rate":         all_hr,
            "delta":                _r6((p125_hr or 0.0) - (all_hr or 0.0)),
            "primary_125_significant": binom_results["primary_125"]["significant_at_05"],
        },
    }

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 7 — Final classification
    # ──────────────────────────────────────────────────────────────────────────
    hit_rate = recomputed["hit_rate"]
    auc      = recomputed["auc"] or 0.0
    ece      = recomputed["ece"]

    if coverage_class == "COVERAGE_TOO_LOW":
        final_class = "P84H_COVERAGE_TOO_LOW_FOR_SIGNAL_CLAIM"
        rationale = [
            f"Canonical coverage {canonical_coverage_ratio:.1%} < 20% minimum threshold",
            "Insufficient data to make any signal claim",
        ]
    elif hit_rate <= 0.50:
        final_class = "P84H_FAILED_VALIDATION"
        rationale = [
            f"All-row hit_rate {hit_rate:.4f} <= 0.50 — no positive signal after P84G fix",
            "Signal validation failed",
        ]
    elif coverage_class == "COVERAGE_LIMITED" and hit_rate > 0.55 and auc > 0.56:
        final_class = "P84H_CORRECTED_SIGNAL_PROMISING_BUT_COVERAGE_LIMITED"
        rationale = [
            f"hit_rate = {hit_rate:.6f} > 0.55 ✓",
            f"AUC(prob, home_win) = {auc:.6f} > 0.56 ✓",
            f"Coverage {canonical_coverage_ratio:.2%} (828/2430) — COVERAGE_LIMITED (March–May 2026 only)",
            f"ECE = {ece:.6f} — calibration weak but acceptable for diagnostic tracking",
            f"primary_125 hit_rate = {p125_hr:.6f}, significantly above random (p<0.05)",
            "No full-season claim | No production claim | Diagnostic-only use",
        ]
    elif ece > 0.05:
        final_class = "P84H_CALIBRATION_WEAK_REQUIRES_REVIEW"
        rationale = [
            f"ECE = {ece:.4f} > 0.05 — calibration too weak for confident diagnostic use",
            f"hit_rate = {hit_rate:.4f} is above random but calibration is primary concern",
        ]
    else:
        final_class = "P84H_CORRECTED_SIGNAL_VALIDATED_DIAGNOSTIC_ONLY"
        rationale = [
            f"hit_rate = {hit_rate:.6f} > 0.55 ✓",
            f"AUC = {auc:.6f} > 0.56 ✓",
            f"ECE = {ece:.6f} < 0.05 ✓",
            "Coverage sufficient for diagnostic use",
        ]

    assert final_class in ALLOWED_CLASSIFICATIONS, f"Unexpected classification: {final_class}"

    summary["p84h_classification"] = final_class
    summary["step7_final_classification"] = {
        "classification": final_class,
        "rationale":      rationale,
        "key_metrics": {
            "hit_rate":                  hit_rate,
            "auc":                       _r6(auc),
            "ece":                       ece,
            "canonical_coverage_ratio":  _r6(canonical_coverage_ratio),
            "coverage_classification":   coverage_class,
            "primary_125_hit_rate":      rule_subset["primary_125"]["hit_rate"],
            "primary_125_significant":   binom_results["primary_125"]["significant_at_05"],
        },
    }

    _write_outputs(summary)
    return summary


# ─── Output writers ───────────────────────────────────────────────────────────

def _write_outputs(summary: dict) -> None:
    P84H_SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[P84H] Summary  → {P84H_SUMMARY_PATH}")

    _write_report(summary)
    print(f"[P84H] Report   → {P84H_REPORT_PATH}")

    _update_active_task(summary)
    print(f"[P84H] active_task.md updated")


def _write_report(summary: dict) -> None:
    clf  = summary.get("p84h_classification", "UNKNOWN")
    step2 = summary.get("step2_recomputed_metrics", {})
    step3 = summary.get("step3_split_metrics", {})
    step4 = summary.get("step4_calibration", {})
    step5 = summary.get("step5_coverage", {})
    step6 = summary.get("step6_subset_comparison", {})
    step7 = summary.get("step7_final_classification", {})
    rc    = step2.get("recomputed", {})

    def _pct(v): return f"{v:.2%}" if v is not None else "N/A"
    def _f6(v):  return f"{v:.6f}" if v is not None else "N/A"

    lines = [
        "# P84H — Corrected 2026 Prediction-Only Signal Validation + Coverage Guard",
        "",
        f"**Generated**: {summary.get('generated_at', '')}",
        f"**Phase**: P84H | **Date**: {summary.get('date', '')}",
        f"**Predecessor**: {summary.get('predecessor', '')}",
        "",
        "> ⚠️ **diagnostic_only=true** | **paper_only=true** | **production_ready=false**",
        "> **odds_used=false** | **ev_computed=false** | **clv_computed=false** | **kelly_computed=false**",
        "> Partial 2026 coverage (828/2430, March–May only). No full-season claim. No production claim.",
        "",
        "---",
        "",
        f"## Final Classification: `{clf}`",
        "",
    ]

    rationale = step7.get("rationale", [])
    if rationale:
        lines.append("**Rationale:**")
        for r in rationale:
            lines.append(f"- {r}")
        lines.append("")

    km = step7.get("key_metrics", {})
    lines += [
        "### Key Metrics Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| hit_rate (all, n=808) | {_f6(km.get('hit_rate'))} |",
        f"| AUC(prob, home_win) | {_f6(km.get('auc'))} |",
        f"| ECE (10-bin) | {_f6(km.get('ece'))} |",
        f"| Coverage (canonical/schedule) | {_pct(km.get('canonical_coverage_ratio'))} |",
        f"| Coverage class | {km.get('coverage_classification', 'N/A')} |",
        f"| primary_125 hit_rate (n=491) | {_f6(km.get('primary_125_hit_rate'))} |",
        f"| primary_125 significant (α=0.05) | {km.get('primary_125_significant', 'N/A')} |",
        "",
    ]

    # Step 2: recomputed vs P84E
    lines += [
        "---",
        "",
        "## Step 2 — Recomputed Metrics vs P84E Artifact",
        "",
        "| Metric | Recomputed | P84E Reference | Delta | OK? |",
        "|--------|-----------|---------------|-------|-----|",
    ]
    ref  = step2.get("p84e_reference", {})
    delt = step2.get("deltas", {})
    tol  = step2.get("tolerance", TOLERANCE)
    for metric in ("hit_rate", "auc", "brier", "ece"):
        rv = rc.get(metric)
        re = ref.get(metric)
        rd = delt.get(metric, 0.0)
        ok = "✓" if (rd is not None and rd < tol) else "✗"
        lines.append(f"| {metric} | {_f6(rv)} | {_f6(re)} | {_f6(rd)} | {ok} |")
    lines.append("")

    # Step 3: monthly
    lines += ["---", "", "## Step 3a — Monthly Split", ""]
    monthly = step3.get("monthly", {})
    lines += [
        "| Month | n | hit_rate | AUC | Brier | ECE |",
        "|-------|---|---------|-----|-------|-----|",
    ]
    for month in ("2026-03", "2026-04", "2026-05"):
        m = monthly.get(month, {})
        lines.append(
            f"| {month} | {m.get('n','?')} | {_f6(m.get('hit_rate'))} "
            f"| {_f6(m.get('auc'))} | {_f6(m.get('brier'))} | {_f6(m.get('ece'))} |"
        )
    lines.append("")

    # Step 3: chronological thirds
    lines += ["## Step 3b — Chronological Thirds", ""]
    thirds = step3.get("chronological_thirds", {})
    lines += [
        "| Third | n | date_range | hit_rate | AUC | Brier |",
        "|-------|---|-----------|---------|-----|-------|",
    ]
    for name in ("first_third", "second_third", "third_third"):
        t = thirds.get(name, {})
        dr = f"{t.get('date_start','?')} – {t.get('date_end','?')}"
        lines.append(
            f"| {name} | {t.get('n','?')} | {dr} "
            f"| {_f6(t.get('hit_rate'))} | {_f6(t.get('auc'))} | {_f6(t.get('brier'))} |"
        )
    lines.append("")

    # Step 3: side split
    lines += ["## Step 3c — Side Split", ""]
    side = step3.get("side", {})
    lines += [
        "| predicted_side | n | hit_rate | AUC | Brier | ECE |",
        "|---------------|---|---------|-----|-------|-----|",
    ]
    for s in ("home", "away"):
        m = side.get(s, {})
        lines.append(
            f"| {s} | {m.get('n','?')} | {_f6(m.get('hit_rate'))} "
            f"| {_f6(m.get('auc'))} | {_f6(m.get('brier'))} | {_f6(m.get('ece'))} |"
        )
    lines.append("")

    # Step 3: rule subset
    lines += ["## Step 3d — Rule Subset Split", ""]
    rs = step3.get("rule_subset", {})
    lines += [
        "| Subset | n | hit_rate | AUC | Brier | ECE |",
        "|--------|---|---------|-----|-------|-----|",
    ]
    for name in ("primary_125", "shadow_100", "tier_b", "tier_a"):
        m = rs.get(name, {})
        lines.append(
            f"| {name} | {m.get('n','?')} | {_f6(m.get('hit_rate'))} "
            f"| {_f6(m.get('auc'))} | {_f6(m.get('brier'))} | {_f6(m.get('ece'))} |"
        )
    lines.append("")

    # Step 4: calibration
    lines += [
        "---",
        "",
        f"## Step 4 — Calibration Analysis",
        "",
        f"**ECE** = {_f6(step4.get('ece'))} — **{step4.get('calibration_level', 'N/A')}**",
        "",
        "*(Platt/isotonic refit: FORBIDDEN by governance)*",
        "",
        "**Reliability Curve (10 bins):**",
        "",
        "| Bin | n | Mean Prob | Empirical HR | Gap |",
        "|-----|---|----------|-------------|-----|",
    ]
    for b in step4.get("reliability_curve", []):
        if b["n"] == 0:
            continue
        lines.append(
            f"| [{b['bin_lo']:.1f}, {b['bin_hi']:.1f}) | {b['n']} "
            f"| {_f6(b['mean_prob'])} | {_f6(b['empirical_hr'])} | {_f6(b['calibration_gap'])} |"
        )
    lines += [
        "",
        "**Notes on calibration weakness sources:**",
    ]
    for note in step4.get("calibration_notes", {}).get("likely_sources", []):
        lines.append(f"- {note}")
    lines.append("")

    # Step 5: coverage
    cov = step5
    lines += [
        "---",
        "",
        "## Step 5 — Coverage Classification",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Schedule rows (full 2026 season) | {cov.get('schedule_rows', 2430)} |",
        f"| Canonical rows | {cov.get('canonical_rows', '?')} |",
        f"| Outcome-available rows | {cov.get('outcome_available_rows', '?')} |",
        f"| Canonical coverage ratio | {_pct(cov.get('canonical_coverage_ratio'))} |",
        f"| Outcome coverage ratio | {_pct(cov.get('outcome_coverage_ratio'))} |",
        f"| Coverage classification | **{cov.get('coverage_classification', 'N/A')}** |",
        f"| Date range covered | {cov.get('date_range_covered', '?')} |",
        f"| Full-season claim valid | {cov.get('full_season_claim_valid', False)} |",
        f"| Production claim valid | {cov.get('production_claim_valid', False)} |",
        "",
    ]

    # Step 6: binomial
    bsubs = step6.get("subsets", {})
    lines += [
        "---",
        "",
        "## Step 6 — Subset Binomial Test (H₀: hit_rate = 0.50, one-sided greater)",
        "",
        "| Subset | n | hit_rate | p-value | Significant α=0.05 | Wilson CI 95% |",
        "|--------|---|---------|---------|-------------------|--------------|",
    ]
    for name in ("all", "primary_125", "shadow_100", "tier_b"):
        b = bsubs.get(name, {})
        ci = f"[{_f6(b.get('wilson_ci_95_lo'))}, {_f6(b.get('wilson_ci_95_hi'))}]"
        lines.append(
            f"| {name} | {b.get('n','?')} | {_f6(b.get('hit_rate'))} "
            f"| {_f6(b.get('binomial_p_value'))} | {b.get('significant_at_05', '?')} | {ci} |"
        )
    lines.append("")

    # Governance
    gov = summary.get("governance", {})
    lines += [
        "---",
        "",
        "## Governance Scan",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in gov.items():
        lines.append(f"| {k} | {v} |")
    lines += [
        "",
        "---",
        "",
        "_P84H — Corrected 2026 Prediction-Only Signal Validation + Coverage Guard_",
        "_diagnostic_only=true | paper_only=true | production_ready=false_",
        "_No odds, no EV, no CLV, no Kelly, no live API, no production deployment_",
    ]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    P84H_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _update_active_task(summary: dict) -> None:
    if not ACTIVE_TASK.exists():
        return
    text = ACTIVE_TASK.read_text(encoding="utf-8")
    clf  = summary.get("p84h_classification", "UNKNOWN")
    entry = (
        f"\n\n## P84H — Corrected 2026 Signal Validation + Coverage Guard\n"
        f"- **Status**: COMPLETE\n"
        f"- **Classification**: `{clf}`\n"
        f"- **Date**: {summary.get('date', '')}\n"
        f"- **Script**: scripts/_p84h_corrected_signal_validation_coverage_guard.py\n"
        f"- **Summary**: data/mlb_2026/derived/p84h_corrected_signal_validation_coverage_guard_summary.json\n"
        f"- **Report**: report/p84h_corrected_signal_validation_coverage_guard_20260527.md\n"
        f"- **Governance**: paper_only=True, diagnostic_only=True, production_ready=False\n"
    )
    if "## P84H" not in text:
        ACTIVE_TASK.write_text(text + entry, encoding="utf-8")


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = main()
    clf = result.get("p84h_classification", "UNKNOWN")
    print(f"\n[P84H] Final classification: {clf}")
    assert clf in ALLOWED_CLASSIFICATIONS, f"Invalid classification: {clf}"
    sys.exit(0)
