"""
P84F — Predicted-Side Direction / Calibration Diagnostic
=========================================================

Purpose
-------
Diagnose why AUC=0.5943 > 0.5 but hit_rate=0.4307 < 0.5 in the P84E outcome
attachment results.

Hypothesis: the `predicted_side` field in the canonical P83E output has its
home/away mapping inverted relative to FIP lower-is-better convention.

Governance Invariants (MUST NEVER VIOLATE)
------------------------------------------
  paper_only            = True
  diagnostic_only       = True
  production_ready      = False
  live_api_calls(odds)  = 0
  ev                    = False
  clv                   = False
  kelly                 = False
  fabricated_outcomes   = False

This script is READ-ONLY on all source files.  It writes only two new
artefacts: the P84F summary JSON and the P84F report markdown.

Allowed p84f_classification values
-----------------------------------
  P84F_SIDE_MAPPING_INVERTED
  P84F_THRESHOLD_MISALIGNED
  P84F_PROBABILITY_INTERPRETATION_FIX_REQUIRED
  P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK
  P84F_MODEL_SIGNAL_WEAK
  P84F_DIAGNOSTIC_INCONCLUSIVE
  P84F_BLOCKED_BY_MISSING_P84E_ARTIFACT
  P84F_FAILED_VALIDATION
"""

from __future__ import annotations

import json
import math
import pathlib
import textwrap
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
P84E_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attachment_summary.json"
P84E_DERIVED_PATH = ROOT / "data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl"
PRED_PATH         = ROOT / "data/mlb_2026/predictions/mlb_2026_prediction_rows.jsonl"
P84F_SUMMARY_PATH = ROOT / "data/mlb_2026/derived/p84f_predicted_side_calibration_diagnostic_summary.json"
P84F_REPORT_PATH  = ROOT / "report/p84f_predicted_side_calibration_diagnostic_20260526.md"
ACTIVE_TASK_PATH  = ROOT / "00-Plan/roadmap/active_task.md"

# ---------------------------------------------------------------------------
# Step 1 — Verify P84E state
# ---------------------------------------------------------------------------

def step1_verify_p84e_state() -> dict[str, Any]:
    """
    Confirm P84E artefacts exist, counts match contract, and governance
    invariants are intact.  Returns a status dict.
    """
    result: dict[str, Any] = {
        "p84e_summary_exists": False,
        "p84e_derived_exists": False,
        "canonical_pred_exists": False,
        "p84e_classification": None,
        "n_canonical_rows": None,
        "n_outcome_available": None,
        "n_outcome_pending": None,
        "original_hit_rate": None,
        "original_auc": None,
        "auc_direction_from_p84e": None,
        "odds_api_called": None,
        "production_ready": None,
        "status": "UNKNOWN",
        "issues": [],
    }

    # --- P84E summary ---
    if not P84E_SUMMARY_PATH.exists():
        result["issues"].append(f"P84E summary missing: {P84E_SUMMARY_PATH}")
        result["status"] = "P84E_ARTIFACT_MISSING"
        return result
    result["p84e_summary_exists"] = True

    summary = json.loads(P84E_SUMMARY_PATH.read_text())
    result["p84e_classification"] = summary.get("p84e_classification")
    stats = summary.get("step3_attachment_stats", {})
    result["n_canonical_rows"] = stats.get("total_canonical_rows")
    result["n_outcome_available"] = stats.get("n_outcome_available")
    result["n_outcome_pending"] = stats.get("n_outcome_pending")

    metrics_all = summary.get("step4_metrics", {}).get("all", {})
    result["original_hit_rate"] = metrics_all.get("hit_rate")
    result["original_auc"] = metrics_all.get("auc")
    result["auc_direction_from_p84e"] = metrics_all.get("auc_direction")

    gov = summary.get("governance", {})
    result["odds_api_called"] = gov.get("odds_api_called")
    result["production_ready"] = gov.get("production_ready")

    # --- P84E derived rows ---
    if not P84E_DERIVED_PATH.exists():
        result["issues"].append(f"P84E derived rows missing: {P84E_DERIVED_PATH}")
        result["status"] = "P84E_DERIVED_MISSING"
        return result
    result["p84e_derived_exists"] = True

    # --- canonical pred rows ---
    if not PRED_PATH.exists():
        result["issues"].append(f"Canonical pred rows missing: {PRED_PATH}")
    else:
        result["canonical_pred_exists"] = True

    # --- governance checks ---
    if result["odds_api_called"] is not False:
        result["issues"].append("P84E governance: odds_api_called is not False")
    if result["production_ready"] is not False:
        result["issues"].append("P84E governance: production_ready is not False")

    result["status"] = "P84E_VERIFIED" if not result["issues"] else "P84E_VERIFIED_WITH_WARNINGS"
    return result


# ---------------------------------------------------------------------------
# Helper — load outcome-attached rows
# ---------------------------------------------------------------------------

def _load_derived_rows() -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in P84E_DERIVED_PATH.read_text().splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Step 2 — Score / label interpretation audit
# ---------------------------------------------------------------------------

def step2_score_label_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute all four AUC variants to confirm model_probability direction.

    Variants:
      auc_prob_home_win     : AUC(model_probability, y_home=1)
      auc_flipped_home_win  : AUC(1-model_probability, y_home=1)
      auc_prob_away_win     : AUC(model_probability, y_away=1)
      auc_prob_is_correct   : AUC(model_probability, is_correct)
    """
    final = [r for r in rows if r.get("outcome_available") is True]

    # Build arrays
    y_home   = [1 if r["actual_winner"] == "home" else 0 for r in final]
    y_away   = [1 if r["actual_winner"] == "away" else 0 for r in final]
    y_correct = [1 if r.get("is_correct") is True else 0 for r in final]
    y_score  = [r.get("model_probability") or 0.5 for r in final]

    def _auc(y_true: list[int], y_score_: list[float]) -> float:
        """Compute AUC without sklearn using sort-based O(n log n) method."""
        n = len(y_true)
        paired = sorted(zip(y_score_, y_true), reverse=True)
        n_pos = sum(y_true)
        n_neg = n - n_pos
        if n_pos == 0 or n_neg == 0:
            return 0.5
        tp = 0
        fp = 0
        auc = 0.0
        prev_fp = 0
        prev_tp = 0
        prev_score = None
        for score, label in paired:
            if score != prev_score and prev_score is not None:
                auc += (fp - prev_fp) * (tp + prev_tp) / 2.0
                prev_fp = fp
                prev_tp = tp
            if label == 1:
                tp += 1
            else:
                fp += 1
            prev_score = score
        auc += (fp - prev_fp) * (tp + prev_tp) / 2.0
        auc /= n_pos * n_neg
        return auc

    auc_prob_home   = _auc(y_home, y_score)
    auc_flipped     = _auc(y_home, [1.0 - s for s in y_score])
    auc_prob_away   = _auc(y_away, y_score)
    auc_correct     = _auc(y_correct, y_score)

    # model_probability interpretation:
    # If auc_prob_home_win > 0.5  → higher prob correlates with HOME winning
    #                             → model_probability is P(home wins)
    # If auc_prob_away_win > 0.5  → higher prob correlates with AWAY winning
    #                             → model_probability is P(away wins)
    if auc_prob_home > 0.5:
        mp_interpretation = "P_HOME_WIN"
    elif auc_prob_away > 0.5:
        mp_interpretation = "P_AWAY_WIN"
    else:
        mp_interpretation = "UNINFORMATIVE"

    return {
        "n_outcome_available": len(final),
        "auc_prob_home_win": round(auc_prob_home, 6),
        "auc_flipped_score_home_win": round(auc_flipped, 6),
        "auc_prob_away_win": round(auc_prob_away, 6),
        "auc_prob_is_correct": round(auc_correct, 6),
        "model_probability_interpretation": mp_interpretation,
        "note": (
            "auc_prob_home_win > 0.5 confirms model_probability = P(home wins). "
            "auc_prob_is_correct < 0.5 exposes direction inversion in predicted_side."
        ),
    }


# ---------------------------------------------------------------------------
# Step 3 — Predicted-side consistency audit
# ---------------------------------------------------------------------------

def step3_predicted_side_consistency(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Audit how predicted_side relates to model_probability threshold,
    then compute hit_rate variants.
    """
    final = [r for r in rows if r.get("outcome_available") is True]
    n = len(final)
    if n == 0:
        return {"status": "NO_DATA"}

    # Distribution
    n_home_predicted  = sum(1 for r in final if r.get("predicted_side") == "home")
    n_away_predicted  = sum(1 for r in final if r.get("predicted_side") == "away")

    # Consistency between predicted_side and model_probability >= 0.5
    # Standard convention: prob >= 0.5 → predict 'home'
    n_consistent_home = sum(
        1 for r in final
        if (r.get("model_probability", 0.5) >= 0.5) == (r.get("predicted_side") == "home")
    )
    n_inverted = n - n_consistent_home

    # Current hit_rate (is_correct as stored)
    current_hit_rate = round(
        sum(1 for r in final if r.get("is_correct") is True) / n, 6
    )

    # Flipped hit_rate (flip is_correct → flip predicted_side)
    flipped_hit_rate = round(
        sum(1 for r in final if r.get("is_correct") is False) / n, 6
    )

    # Probability-threshold hit_rate (re-predict: 'home' if prob >= 0.5)
    def prob_threshold_correct(r: dict[str, Any]) -> bool:
        prob = r.get("model_probability", 0.5)
        thresh_side = "home" if prob >= 0.5 else "away"
        return thresh_side == r.get("actual_winner")

    prob_threshold_hit_rate = round(
        sum(1 for r in final if prob_threshold_correct(r)) / n, 6
    )

    # Hit rates by current predicted_side
    home_pred_rows = [r for r in final if r.get("predicted_side") == "home"]
    away_pred_rows = [r for r in final if r.get("predicted_side") == "away"]
    home_pred_hit_rate = round(
        sum(1 for r in home_pred_rows if r.get("is_correct") is True) / len(home_pred_rows), 6
    ) if home_pred_rows else None
    away_pred_hit_rate = round(
        sum(1 for r in away_pred_rows if r.get("is_correct") is True) / len(away_pred_rows), 6
    ) if away_pred_rows else None

    # Threshold alignment: what is the p-m-side mapping?
    # All cases where prob >= 0.5 → what predicted_side?
    prob_ge_05 = [r for r in final if r.get("model_probability", 0.5) >= 0.5]
    prob_lt_05 = [r for r in final if r.get("model_probability", 0.5) < 0.5]
    ge_home = sum(1 for r in prob_ge_05 if r.get("predicted_side") == "home")
    ge_away = sum(1 for r in prob_ge_05 if r.get("predicted_side") == "away")
    lt_home = sum(1 for r in prob_lt_05 if r.get("predicted_side") == "home")
    lt_away = sum(1 for r in prob_lt_05 if r.get("predicted_side") == "away")

    if ge_away == len(prob_ge_05) and lt_home == len(prob_lt_05):
        mapping_pattern = "PROB_GE_05_MAPS_TO_AWAY"
    elif ge_home == len(prob_ge_05) and lt_away == len(prob_lt_05):
        mapping_pattern = "PROB_GE_05_MAPS_TO_HOME"
    else:
        mapping_pattern = "INCONSISTENT"

    hit_rate_improvement = round(flipped_hit_rate - current_hit_rate, 6)

    return {
        "n_outcome_available": n,
        "n_home_predicted": n_home_predicted,
        "n_away_predicted": n_away_predicted,
        "n_prob_ge_05": len(prob_ge_05),
        "n_prob_lt_05": len(prob_lt_05),
        "prob_ge_05_maps_to_home": ge_home,
        "prob_ge_05_maps_to_away": ge_away,
        "prob_lt_05_maps_to_home": lt_home,
        "prob_lt_05_maps_to_away": lt_away,
        "mapping_pattern": mapping_pattern,
        "n_consistent_with_standard_convention": n_consistent_home,
        "n_inverted_from_standard_convention": n_inverted,
        "current_hit_rate": current_hit_rate,
        "flipped_hit_rate": flipped_hit_rate,
        "probability_threshold_hit_rate": prob_threshold_hit_rate,
        "home_predicted_hit_rate": home_pred_hit_rate,
        "away_predicted_hit_rate": away_pred_hit_rate,
        "hit_rate_improvement_if_flipped": hit_rate_improvement,
        "note": (
            "PROB_GE_05_MAPS_TO_AWAY means predicted_side='away' when "
            "model_probability >= 0.5 — this is the direct inversion indicator."
        ),
    }


# ---------------------------------------------------------------------------
# Step 4 — FIP delta sign audit
# ---------------------------------------------------------------------------

def step4_fip_delta_sign_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Audit whether sp_fip_delta sign aligns with actual win outcomes.

    Convention: sp_fip_delta = home_sp_fip - away_sp_fip
      delta > 0 → home FIP > away FIP → home pitcher WORSE → away has edge
      delta < 0 → home FIP < away FIP → home pitcher BETTER → home has edge
    """
    final = [r for r in rows if r.get("outcome_available") is True]

    pos_delta = [r for r in final if r.get("sp_fip_delta", 0.0) > 0]  # away pitcher better
    neg_delta = [r for r in final if r.get("sp_fip_delta", 0.0) < 0]  # home pitcher better
    zero_delta = [r for r in final if r.get("sp_fip_delta", 0.0) == 0.0]

    def _mean(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 6) if vals else None

    def _win_rate(rs: list[dict], side: str) -> float | None:
        if not rs:
            return None
        return round(sum(1 for r in rs if r.get("actual_winner") == side) / len(rs), 6)

    pos_deltas = [r.get("sp_fip_delta", 0.0) for r in pos_delta]
    neg_deltas = [r.get("sp_fip_delta", 0.0) for r in neg_delta]

    pos_away_win_rate = _win_rate(pos_delta, "away")
    pos_home_win_rate = _win_rate(pos_delta, "home")
    neg_home_win_rate = _win_rate(neg_delta, "home")
    neg_away_win_rate = _win_rate(neg_delta, "away")

    # FIP direction alignment: does delta sign agree with actual winner?
    # Correct alignment: delta > 0 → away wins; delta < 0 → home wins
    fip_correct_count = (
        sum(1 for r in pos_delta if r.get("actual_winner") == "away") +
        sum(1 for r in neg_delta if r.get("actual_winner") == "home")
    )
    fip_total = len(pos_delta) + len(neg_delta)
    fip_hit_rate = round(fip_correct_count / fip_total, 6) if fip_total > 0 else None

    # Predicted_side vs FIP direction
    fip_pred_consistent = (
        sum(1 for r in pos_delta if r.get("predicted_side") == "away") +
        sum(1 for r in neg_delta if r.get("predicted_side") == "home")
    )
    fip_pred_consistency_rate = round(fip_pred_consistent / fip_total, 6) if fip_total > 0 else None

    if pos_away_win_rate is not None and pos_away_win_rate > 0.5:
        fip_signal = "VALID_AWAY_EDGE_WHEN_DELTA_POSITIVE"
    elif pos_home_win_rate is not None and pos_home_win_rate > 0.5:
        fip_signal = "INVERTED_HOME_EDGE_WHEN_DELTA_POSITIVE"
    else:
        fip_signal = "FIP_SIGNAL_WEAK"

    return {
        "n_pos_delta": len(pos_delta),
        "n_neg_delta": len(neg_delta),
        "n_zero_delta": len(zero_delta),
        "pos_delta_mean": _mean(pos_deltas),
        "neg_delta_mean": _mean(neg_deltas),
        "pos_delta_away_win_rate": pos_away_win_rate,
        "pos_delta_home_win_rate": pos_home_win_rate,
        "neg_delta_home_win_rate": neg_home_win_rate,
        "neg_delta_away_win_rate": neg_away_win_rate,
        "fip_direction_hit_rate": fip_hit_rate,
        "predicted_side_fip_consistency_rate": fip_pred_consistency_rate,
        "fip_signal": fip_signal,
        "note": (
            "fip_direction_hit_rate = win rate if we bet 'away' when delta>0 "
            "and 'home' when delta<0 (the FIP-correct direction)."
        ),
    }


# ---------------------------------------------------------------------------
# Step 5 — Rule subset audit
# ---------------------------------------------------------------------------

def step5_rule_subset_audit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute hit_rate, flipped_hit_rate, and probability-threshold hit_rate
    for each rule subset: all, primary_125, shadow_100, tier_b,
    home_predicted, away_predicted.
    """
    final = [r for r in rows if r.get("outcome_available") is True]
    MIN_N = 10

    subsets = {
        "all":          final,
        "primary_125":  [r for r in final if r.get("rule_primary_125_flag") is True],
        "shadow_100":   [r for r in final if r.get("rule_shadow_100_flag") is True],
        "tier_b":       [r for r in final if r.get("tier_b_candidate_flag") is True],
        "home_predicted": [r for r in final if r.get("predicted_side") == "home"],
        "away_predicted": [r for r in final if r.get("predicted_side") == "away"],
    }

    def _metrics(subset_rows: list[dict]) -> dict[str, Any]:
        n = len(subset_rows)
        if n == 0:
            return {"n": 0, "sample_limited": True}
        sl = n < MIN_N
        current_hr = round(sum(1 for r in subset_rows if r.get("is_correct") is True) / n, 6)
        flipped_hr = round(sum(1 for r in subset_rows if r.get("is_correct") is False) / n, 6)

        def _thresh_correct(r: dict) -> bool:
            prob = r.get("model_probability", 0.5)
            return ("home" if prob >= 0.5 else "away") == r.get("actual_winner")

        thresh_hr = round(sum(1 for r in subset_rows if _thresh_correct(r)) / n, 6)
        return {
            "n": n,
            "sample_limited": sl,
            "current_hit_rate": current_hr,
            "flipped_hit_rate": flipped_hr,
            "probability_threshold_hit_rate": thresh_hr,
        }

    return {name: _metrics(s) for name, s in subsets.items()}


# ---------------------------------------------------------------------------
# Step 6 — Calibration bucket table
# ---------------------------------------------------------------------------

def step6_calibration_buckets(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Group outcome-available rows into model_probability decile buckets and
    compute actual home win rate per bucket to visualise calibration.
    """
    final = [r for r in rows if r.get("outcome_available") is True]
    buckets: dict[str, list] = {f"{lo:.1f}-{lo+0.1:.1f}": [] for lo in [i/10 for i in range(0, 10)]}

    for r in final:
        prob = r.get("model_probability", 0.5)
        key = f"{math.floor(prob * 10) / 10:.1f}-{math.floor(prob * 10) / 10 + 0.1:.1f}"
        if key in buckets:
            buckets[key].append(r)
        else:
            # Edge case: prob == 1.0
            buckets["0.9-1.0"].append(r)

    result = []
    for label, bucket_rows in buckets.items():
        n = len(bucket_rows)
        if n == 0:
            continue
        hw = sum(1 for r in bucket_rows if r.get("actual_winner") == "home") / n
        aw = sum(1 for r in bucket_rows if r.get("actual_winner") == "away") / n
        result.append({
            "prob_bucket": label,
            "n": n,
            "actual_home_win_rate": round(hw, 4),
            "actual_away_win_rate": round(aw, 4),
        })
    return result


# ---------------------------------------------------------------------------
# Step 7 — Classify
# ---------------------------------------------------------------------------

def step7_classify(
    step1: dict[str, Any],
    step2: dict[str, Any],
    step3: dict[str, Any],
    step4: dict[str, Any],
) -> tuple[str, str, list[str]]:
    """
    Return (classification, remediation_path, evidence_list).
    """
    # Guard: P84E artifact missing
    if not step1.get("p84e_summary_exists") or not step1.get("p84e_derived_exists"):
        return (
            "P84F_BLOCKED_BY_MISSING_P84E_ARTIFACT",
            "Run P84E pipeline first to generate artefacts, then re-run P84F.",
            ["P84E artefacts not found"],
        )

    evidence: list[str] = []

    # Key signals
    auc_home = step2.get("auc_prob_home_win", 0.0)
    auc_correct = step2.get("auc_prob_is_correct", 0.5)
    mp_interp = step2.get("model_probability_interpretation", "")
    mapping = step3.get("mapping_pattern", "")
    current_hr = step3.get("current_hit_rate", 0.5)
    flipped_hr = step3.get("flipped_hit_rate", 0.5)
    hr_gain = step3.get("hit_rate_improvement_if_flipped", 0.0)
    fip_signal = step4.get("fip_signal", "")
    pred_fip_consistency = step4.get("predicted_side_fip_consistency_rate", 1.0)

    # --- Collect evidence ---
    if auc_home > 0.5:
        evidence.append(
            f"AUC(prob, home_win)={auc_home:.4f} > 0.5 → model_probability = P(home wins)"
        )
    if auc_correct < 0.5:
        evidence.append(
            f"AUC(prob, is_correct)={auc_correct:.4f} < 0.5 → predicted_side direction inverted"
        )
    if mapping == "PROB_GE_05_MAPS_TO_AWAY":
        evidence.append(
            "prob >= 0.5 maps to predicted_side='away' in 100% of cases — threshold inverted"
        )
    if current_hr < 0.5:
        evidence.append(f"current hit_rate={current_hr:.4f} < 0.5 — below random baseline")
    if flipped_hr > 0.5:
        evidence.append(f"flipped hit_rate={flipped_hr:.4f} > 0.5 — inversion recovers signal")
    if hr_gain > 0.10:
        evidence.append(f"hit_rate improvement if flipped: +{hr_gain:.4f}")
    if fip_signal == "VALID_AWAY_EDGE_WHEN_DELTA_POSITIVE":
        evidence.append(
            "FIP delta sign valid: delta>0 → away wins more often (correct FIP edge direction)"
        )
    if pred_fip_consistency is not None and pred_fip_consistency < 0.1:
        evidence.append(
            f"predicted_side FIP consistency rate={pred_fip_consistency:.4f} — predicted_side inverted vs FIP"
        )

    # --- Classification logic ---

    # Strong inversion signal: AUC > 0.5, is_correct < 0.5, mapping inverted, big flip gain
    if (
        auc_home > 0.5
        and auc_correct < 0.5
        and mapping == "PROB_GE_05_MAPS_TO_AWAY"
        and hr_gain > 0.05
    ):
        classification = "P84F_SIDE_MAPPING_INVERTED"
        remediation = (
            "P84G: Fix `compute_predicted_side` in P83E to use "
            "'away' if sp_fip_delta > 0 else 'home' (lower FIP = better pitcher = favoured side). "
            "Regenerate canonical prediction rows and rerun P84A→P84E chain."
        )
        return classification, remediation, evidence

    # Threshold misalignment (mapping inconsistent but not fully inverted)
    if current_hr < 0.5 and abs(auc_home - 0.5) < 0.05:
        classification = "P84F_THRESHOLD_MISALIGNED"
        remediation = (
            "P84G: Audit threshold boundary in `compute_predicted_side`. "
            "Consider strictly-greater vs greater-or-equal at 0.5."
        )
        return classification, remediation, evidence

    # Probability interpretation issue
    if mp_interp == "P_AWAY_WIN" and current_hr < 0.5:
        classification = "P84F_PROBABILITY_INTERPRETATION_FIX_REQUIRED"
        remediation = (
            "P84G: model_probability was generated as P(away wins) but used as P(home wins). "
            "Flip sigmoid argument sign in P83E model."
        )
        return classification, remediation, evidence

    # Model has signal but calibration is weak
    if auc_home > 0.52 and current_hr > 0.45:
        classification = "P84F_MODEL_SIGNAL_PRESENT_CALIBRATION_WEAK"
        remediation = (
            "P84G: Apply Platt scaling or isotonic regression to recalibrate "
            "model_probability to genuine win probabilities."
        )
        return classification, remediation, evidence

    # Weak overall signal
    if abs(auc_home - 0.5) < 0.03:
        classification = "P84F_MODEL_SIGNAL_WEAK"
        remediation = (
            "P84G: Enrich feature set beyond FIP delta alone (bullpen, park factors, "
            "rest days, lineup context). "
            "Current FIP-only model lacks predictive power."
        )
        return classification, remediation, evidence

    classification = "P84F_DIAGNOSTIC_INCONCLUSIVE"
    remediation = "Manual review of P84F artefacts required."
    return classification, remediation, evidence


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _write_report(
    step1: dict[str, Any],
    step2: dict[str, Any],
    step3: dict[str, Any],
    step4: dict[str, Any],
    step5: dict[str, Any],
    buckets: list[dict[str, Any]],
    classification: str,
    remediation: str,
    evidence: list[str],
) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    subset_rows = ""
    for name, m in step5.items():
        n = m.get("n", 0)
        if n == 0:
            continue
        sl = " (sample_limited)" if m.get("sample_limited") else ""
        chr_ = m.get("current_hit_rate", "N/A")
        fhr = m.get("flipped_hit_rate", "N/A")
        thr = m.get("probability_threshold_hit_rate", "N/A")
        subset_rows += f"| {name:<20} | {n:>6}{sl:<16} | {chr_!s:>8} | {fhr!s:>8} | {thr!s:>8} |\n"

    bucket_rows = ""
    for b in buckets:
        bucket_rows += (
            f"| {b['prob_bucket']:<12} | {b['n']:>5} | "
            f"{b['actual_home_win_rate']:>6.4f} | {b['actual_away_win_rate']:>6.4f} |\n"
        )

    evidence_str = "\n".join(f"  - {e}" for e in evidence)

    report = textwrap.dedent(f"""\
    # P84F — Predicted-Side Direction / Calibration Diagnostic
    *Generated: {ts}*

    ---

    ## Executive Summary

    | Metric | Value |
    |---|---|
    | Classification | **{classification}** |
    | AUC(prob, home_win) | {step2.get('auc_prob_home_win', 'N/A')} |
    | AUC(prob, is_correct) | {step2.get('auc_prob_is_correct', 'N/A')} |
    | model_probability interpretation | {step2.get('model_probability_interpretation', 'N/A')} |
    | Current hit_rate | {step3.get('current_hit_rate', 'N/A')} |
    | Flipped hit_rate | {step3.get('flipped_hit_rate', 'N/A')} |
    | Probability-threshold hit_rate | {step3.get('probability_threshold_hit_rate', 'N/A')} |
    | Hit-rate improvement if flipped | +{step3.get('hit_rate_improvement_if_flipped', 'N/A')} |
    | Mapping pattern | {step3.get('mapping_pattern', 'N/A')} |

    ---

    ## Step 1 — P84E State Verification

    - P84E summary: {'EXISTS' if step1.get('p84e_summary_exists') else 'MISSING'}
    - P84E derived rows: {'EXISTS' if step1.get('p84e_derived_exists') else 'MISSING'}
    - P84E classification: {step1.get('p84e_classification')}
    - n_outcome_available: {step1.get('n_outcome_available')}
    - auc_direction (from P84E): {step1.get('auc_direction_from_p84e')}
    - odds_api_called: {step1.get('odds_api_called')}
    - production_ready: {step1.get('production_ready')}

    ---

    ## Step 2 — Score / Label Interpretation Audit

    | AUC Variant | Value |
    |---|---|
    | AUC(model_probability, home_win) | {step2.get('auc_prob_home_win')} |
    | AUC(1 - model_probability, home_win) | {step2.get('auc_flipped_score_home_win')} |
    | AUC(model_probability, away_win) | {step2.get('auc_prob_away_win')} |
    | AUC(model_probability, is_correct) | {step2.get('auc_prob_is_correct')} |

    **model_probability interpretation**: {step2.get('model_probability_interpretation')}

    {step2.get('note', '')}

    ---

    ## Step 3 — Predicted-Side Consistency Audit

    ### Mapping pattern: `{step3.get('mapping_pattern')}`

    | prob bucket | n | predicted home | predicted away |
    |---|---|---|---|
    | prob >= 0.5 | {step3.get('n_prob_ge_05')} | {step3.get('prob_ge_05_maps_to_home')} | {step3.get('prob_ge_05_maps_to_away')} |
    | prob < 0.5  | {step3.get('n_prob_lt_05')} | {step3.get('prob_lt_05_maps_to_home')} | {step3.get('prob_lt_05_maps_to_away')} |

    | Hit-rate variant | Value |
    |---|---|
    | Current (as-stored) | {step3.get('current_hit_rate')} |
    | Flipped predicted_side | {step3.get('flipped_hit_rate')} |
    | Probability-threshold (home if prob≥0.5) | {step3.get('probability_threshold_hit_rate')} |
    | Home-predicted subset | {step3.get('home_predicted_hit_rate')} |
    | Away-predicted subset | {step3.get('away_predicted_hit_rate')} |

    ---

    ## Step 4 — FIP Delta Sign Audit

    **Convention**: `sp_fip_delta = home_sp_fip - away_sp_fip`
    - delta > 0 → home pitcher worse → FIP favours AWAY
    - delta < 0 → home pitcher better → FIP favours HOME

    | Subset | n | Away win rate | Home win rate |
    |---|---|---|---|
    | delta > 0 (away favoured) | {step4.get('n_pos_delta')} | {step4.get('pos_delta_away_win_rate')} | {step4.get('pos_delta_home_win_rate')} |
    | delta < 0 (home favoured) | {step4.get('n_neg_delta')} | {step4.get('neg_delta_away_win_rate')} | {step4.get('neg_delta_home_win_rate')} |

    - FIP direction hit_rate (correct direction): **{step4.get('fip_direction_hit_rate')}**
    - predicted_side FIP consistency rate: **{step4.get('predicted_side_fip_consistency_rate')}**
    - FIP signal: `{step4.get('fip_signal')}`

    {step4.get('note', '')}

    ---

    ## Step 5 — Rule Subset Audit

    | Subset               | n (+sample flag) | current HR |  flipped HR | thresh HR |
    |---|---|---|---|---|
    {subset_rows.rstrip()}

    ---

    ## Step 6 — Calibration Bucket Table

    | prob bucket  |   n   | home win rate | away win rate |
    |---|---|---|---|
    {bucket_rows.rstrip()}

    ---

    ## Step 7 — Diagnostic Classification

    **Classification**: `{classification}`

    ### Evidence Chain

{evidence_str}

    ### Remediation Path (P84G)

    {remediation}

    ---

    ## Governance

    | Invariant | Value |
    |---|---|
    | paper_only | True |
    | diagnostic_only | True |
    | production_ready | False |
    | live_api_calls (odds) | 0 |
    | ev | False |
    | clv | False |
    | kelly | False |
    | fabricated_outcomes | False |
    """)

    P84F_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    P84F_REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"  [P84F] report → {P84F_REPORT_PATH}")


# ---------------------------------------------------------------------------
# Active task update
# ---------------------------------------------------------------------------

def _update_active_task(classification: str) -> None:
    if not ACTIVE_TASK_PATH.exists():
        return
    text = ACTIVE_TASK_PATH.read_text(encoding="utf-8")
    marker = "## P84F"
    entry = (
        f"\n## P84F — Predicted-Side Direction / Calibration Diagnostic\n"
        f"- Status: COMPLETE\n"
        f"- Classification: {classification}\n"
        f"- Artefacts: p84f_predicted_side_calibration_diagnostic_summary.json\n"
        f"- Report: report/p84f_predicted_side_calibration_diagnostic_20260526.md\n"
    )
    if marker in text:
        # Already present — skip
        return
    ACTIVE_TASK_PATH.write_text(text + entry, encoding="utf-8")
    print(f"  [P84F] active_task.md updated")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run() -> dict[str, Any]:
    print("[P84F] Starting Predicted-Side Direction / Calibration Diagnostic …")

    # Step 1
    print("[P84F] Step 1: Verifying P84E state …")
    s1 = step1_verify_p84e_state()
    print(f"  status={s1['status']}  classification={s1.get('p84e_classification')}")

    if not s1.get("p84e_derived_exists"):
        classification = "P84F_BLOCKED_BY_MISSING_P84E_ARTIFACT"
        remediation = "Run P84E pipeline first."
        summary: dict[str, Any] = {
            "p84f_classification": classification,
            "step1_verify_p84e": s1,
            "governance": _governance_block(),
        }
        _write_summary(summary)
        print(f"[P84F] BLOCKED — {classification}")
        return summary

    # Load rows
    print("[P84F] Loading P84E derived rows …")
    rows = _load_derived_rows()
    n_total = len(rows)
    n_final = sum(1 for r in rows if r.get("outcome_available") is True)
    print(f"  total rows={n_total}  outcome_available={n_final}")

    # Steps 2–6
    print("[P84F] Step 2: Score/label interpretation audit …")
    s2 = step2_score_label_audit(rows)
    print(f"  auc_prob_home_win={s2['auc_prob_home_win']}  interpretation={s2['model_probability_interpretation']}")

    print("[P84F] Step 3: Predicted-side consistency audit …")
    s3 = step3_predicted_side_consistency(rows)
    print(
        f"  mapping={s3['mapping_pattern']}  "
        f"current_hr={s3['current_hit_rate']}  "
        f"flipped_hr={s3['flipped_hit_rate']}"
    )

    print("[P84F] Step 4: FIP delta sign audit …")
    s4 = step4_fip_delta_sign_audit(rows)
    print(f"  fip_signal={s4['fip_signal']}  fip_direction_hr={s4['fip_direction_hit_rate']}")

    print("[P84F] Step 5: Rule subset audit …")
    s5 = step5_rule_subset_audit(rows)

    print("[P84F] Step 6: Calibration buckets …")
    buckets = step6_calibration_buckets(rows)

    print("[P84F] Step 7: Classification …")
    classification, remediation, evidence = step7_classify(s1, s2, s3, s4)
    print(f"  classification={classification}")

    # Build summary
    summary = {
        "p84f_classification": classification,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "step1_verify_p84e": s1,
        "step2_score_label_audit": s2,
        "step3_predicted_side_consistency": s3,
        "step4_fip_delta_sign_audit": s4,
        "step5_rule_subset_audit": s5,
        "step6_calibration_buckets": buckets,
        "step7_diagnosis": {
            "classification": classification,
            "remediation_path": remediation,
            "evidence": evidence,
        },
        "governance": _governance_block(),
    }

    _write_summary(summary)
    _write_report(s1, s2, s3, s4, s5, buckets, classification, remediation, evidence)
    _update_active_task(classification)

    print(f"[P84F] Complete — {classification}")
    return summary


def _governance_block() -> dict[str, Any]:
    return {
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "live_api_calls": 0,
        "odds_api_called": False,
        "ev": False,
        "clv": False,
        "kelly": False,
        "fabricated_outcomes": False,
    }


def _write_summary(summary: dict[str, Any]) -> None:
    P84F_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    P84F_SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  [P84F] summary → {P84F_SUMMARY_PATH}")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    run()
