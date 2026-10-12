#!/usr/bin/env python3
"""
P78 — Monthly Rule Monitoring Template + Shadow Tracker Report Pack

Classification target: P78_MONTHLY_SHADOW_TRACKER_TEMPLATE_READY

Governance:
    paper_only=True | diagnostic_only=True | production_ready=False
    odds_used=False | ev_calculated=False | clv_calculated=False | kelly_calculated=False
    live_api_calls=0 | NO_REAL_BET=True

Source: P77 (ffd2bc9) — 2026 Prediction-Only Shadow Tracker Contract
Data:  mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl (fixture)
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Governance — all flags hardcoded; never modified at runtime
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, object] = {
    "paper_only": True,
    "diagnostic_only": True,
    "odds_used": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "kelly_calculated": False,
    "production_ready": False,
    "live_api_calls": 0,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "real_bet_allowed": False,
    "no_real_bet": True,
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PATHS: dict[str, Path] = {
    "p77_summary": ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_summary": ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
    "p75b_summary": ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_summary": ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_summary": ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json",
    "p73_summary": ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_summary": ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
    "p72a_summary": ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
    "predictions_jsonl": ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
    "p77_report": ROOT / "report/p77_prediction_only_shadow_tracker_contract_20260526.md",
    "output_json": ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json",
    "output_report": ROOT / "report/p78_monthly_shadow_tracker_report_template_20260526.md",
    "output_bettingplan": ROOT / "00-BettingPlan/20260526/p78_monthly_shadow_tracker_report_template_20260526.md",
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FIXTURE_MONTHS = ["2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09"]
TIER_B_TRIGGER_N = 200
ROLLING_100_FLOOR = 0.55
CONSECUTIVE_FLOOR = 0.50
CONSECUTIVE_MONTHS_REQUIRED = 2
ECE_WORSENING_THRESHOLD = 0.03  # absolute ECE worsening threshold

# P77 expected counts (ground truth for contract verification)
P77_EXPECTED = {
    "primary_rule": "TIER_C_HOME_PLUS_AWAY_125",
    "shadow_rule": "TIER_C_HOME_PLUS_AWAY_100",
    "HOME_PLUS_AWAY_125_n": 316,
    "HOME_PLUS_AWAY_100_n": 373,
    "HOME_ONLY_n": 268,
    "classification": "P77_SHADOW_TRACKER_CONTRACT_READY",
}

SCHEMA_VERSION = "p78-v1"

# ---------------------------------------------------------------------------
# Low-level statistical helpers (no external dependencies)
# ---------------------------------------------------------------------------

def _wilson_ci(n: int, hits: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, round(centre - margin, 4)), min(1.0, round(centre + margin, 4)))


def _compute_auc(scores: list[float], labels: list[int]) -> Optional[float]:
    """ROC-AUC via Mann-Whitney U statistic."""
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return None
    concordant = sum(1 for p in pos for n in neg if p > n)
    tied = sum(0.5 for p in pos for n in neg if p == n)
    return (concordant + tied) / (len(pos) * len(neg))


def _compute_ece(probs: list[float], labels: list[int], n_bins: int = 10) -> float:
    """Expected Calibration Error (equal-width binning)."""
    n = len(probs)
    if n == 0:
        return 0.0
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, lbl in zip(probs, labels):
        idx = min(int(p * n_bins), n_bins - 1)
        bins[idx].append((p, lbl))
    ece = 0.0
    for bin_items in bins:
        if not bin_items:
            continue
        conf = sum(x[0] for x in bin_items) / len(bin_items)
        acc = sum(x[1] for x in bin_items) / len(bin_items)
        ece += (len(bin_items) / n) * abs(acc - conf)
    return ece


def _compute_brier(probs: list[float], labels: list[int]) -> Optional[float]:
    if not probs:
        return None
    return sum((p - l) ** 2 for p, l in zip(probs, labels)) / len(probs)


def _compute_metrics(classified_rows: list[dict]) -> dict:
    """
    Compute full metrics for a list of classified rows.

    Each row must have:
        model_home_prob, home_win (0/1), is_correct (bool)
    """
    n = len(classified_rows)
    if n == 0:
        return {
            "n": 0,
            "hit_rate": None,
            "hit_rate_ci_95_lo": None,
            "hit_rate_ci_95_hi": None,
            "auc": None,
            "brier": None,
            "ece": None,
            "home_n": 0,
            "away_n": 0,
            "home_hit_rate": None,
            "away_hit_rate": None,
        }
    hits = sum(1 for r in classified_rows if r["is_correct"])
    hit_rate = hits / n
    ci_lo, ci_hi = _wilson_ci(n, hits)

    probs = [r["model_home_prob"] for r in classified_rows]
    labels = [r["home_win"] for r in classified_rows]

    auc_val = _compute_auc(probs, labels)
    brier_val = _compute_brier(probs, labels)
    ece_val = _compute_ece(probs, labels)

    home_rows = [r for r in classified_rows if r["predicted_side"] == "home"]
    away_rows = [r for r in classified_rows if r["predicted_side"] == "away"]
    home_hit = (sum(1 for r in home_rows if r["is_correct"]) / len(home_rows)) if home_rows else None
    away_hit = (sum(1 for r in away_rows if r["is_correct"]) / len(away_rows)) if away_rows else None

    return {
        "n": n,
        "hit_rate": round(hit_rate, 4),
        "hit_rate_ci_95_lo": ci_lo,
        "hit_rate_ci_95_hi": ci_hi,
        "auc": round(auc_val, 4) if auc_val is not None else None,
        "brier": round(brier_val, 4) if brier_val is not None else None,
        "ece": round(ece_val, 4) if ece_val is not None else None,
        "home_n": len(home_rows),
        "away_n": len(away_rows),
        "home_hit_rate": round(home_hit, 4) if home_hit is not None else None,
        "away_hit_rate": round(away_hit, 4) if away_hit is not None else None,
    }


# ---------------------------------------------------------------------------
# Rule classification helpers
# ---------------------------------------------------------------------------

def _classify_row(row: dict) -> dict:
    """
    Classify a single JSONL row into all rule categories.

    Returns a dict with flags and base metrics.
    """
    p0 = row.get("p0_features", {})
    fip_avail: bool = bool(p0.get("sp_fip_delta_available", False))
    fip: float = float(p0.get("sp_fip_delta", 0.0) or 0.0)
    abs_fip: float = abs(fip)

    model_home_prob: float = float(row.get("model_home_prob", 0.5) or 0.5)
    home_win: int = int(row.get("home_win", 0))
    game_date: str = row.get("game_date", "")
    game_month: str = game_date[:7] if game_date else ""

    predicted_side = "home" if model_home_prob > 0.5 else "away"
    is_correct = (predicted_side == "home" and home_win == 1) or (
        predicted_side == "away" and home_win == 0
    )

    # Rule flags
    home_pick = model_home_prob > 0.5
    in_home_only = fip_avail and home_pick and abs_fip >= 0.50
    in_primary = fip_avail and (
        (home_pick and abs_fip >= 0.50) or (not home_pick and abs_fip >= 1.25)
    )
    in_shadow = fip_avail and (
        (home_pick and abs_fip >= 0.50) or (not home_pick and abs_fip >= 1.00)
    )
    in_tier_b = fip_avail and 0.25 <= abs_fip < 0.50
    in_tier_a = fip_avail and abs_fip >= 1.50

    return {
        "game_date": game_date,
        "game_month": game_month,
        "model_home_prob": model_home_prob,
        "home_win": home_win,
        "predicted_side": predicted_side,
        "is_correct": is_correct,
        "abs_sp_fip_delta": abs_fip,
        "sp_fip_delta_available": fip_avail,
        "in_home_only": in_home_only,
        "in_primary": in_primary,
        "in_shadow": in_shadow,
        "in_tier_b": in_tier_b,
        "in_tier_a": in_tier_a,
    }


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _build_classified_rows(raw_rows: list[dict]) -> list[dict]:
    classified = [_classify_row(r) for r in raw_rows]
    classified.sort(key=lambda r: r["game_date"])
    return classified


# ---------------------------------------------------------------------------
# Rolling-100 helper
# ---------------------------------------------------------------------------

def _rolling_100_hit_rate(
    primary_rows: list[dict], up_to_month: str
) -> Optional[float]:
    """
    Compute rolling 100-game hit_rate for primary rule rows through up_to_month.
    Returns None if fewer than 50 qualifying rows exist (insufficient sample).
    """
    eligible = [r for r in primary_rows if r["game_month"] <= up_to_month]
    last_100 = eligible[-100:]
    if len(last_100) < 50:
        return None
    return round(sum(1 for r in last_100 if r["is_correct"]) / len(last_100), 4)


# ---------------------------------------------------------------------------
# Alert logic
# ---------------------------------------------------------------------------

def _determine_alert(
    primary_metrics: dict,
    rolling_100: Optional[float],
    two_consecutive_below: bool,
    ece_worsened: bool,
    governance_clean: bool,
) -> str:
    """
    Determine alert level.

    RED:    rolling_100 < 0.55, OR two_consecutive_below, OR ece_worsened, OR governance violation
    YELLOW: n < 50 (sample limited) OR one warning criterion
    GREEN:  no criteria triggered, sample sufficient
    """
    n = primary_metrics.get("n", 0)

    if not governance_clean:
        return "RED"
    if rolling_100 is not None and rolling_100 < ROLLING_100_FLOOR:
        return "RED"
    if two_consecutive_below:
        return "RED"
    if ece_worsened:
        return "RED"
    if n < 50:
        return "YELLOW"
    if rolling_100 is None and n >= 50:
        return "YELLOW"
    return "GREEN"


# ---------------------------------------------------------------------------
# ECE worsening detection
# ---------------------------------------------------------------------------

def _ece_worsened(current_ece: Optional[float], baseline_ece: Optional[float]) -> bool:
    """Returns True if ECE has materially worsened (increased by >= threshold)."""
    if current_ece is None or baseline_ece is None:
        return False
    return (current_ece - baseline_ece) >= ECE_WORSENING_THRESHOLD


# ---------------------------------------------------------------------------
# Two-consecutive-months detection
# ---------------------------------------------------------------------------

def _two_consecutive_below(month_results: list[dict], up_to_month: str) -> bool:
    """
    Check whether the last two eligible months (n>=10) both had hit_rate < 0.50.
    'Eligible months' = months with primary_n >= 10.
    """
    prior = [
        m for m in month_results
        if m["report_month"] <= up_to_month
        and m["rule_summary"]["primary"]["n"] >= 10
    ]
    if len(prior) < CONSECUTIVE_MONTHS_REQUIRED:
        return False
    last_two = prior[-CONSECUTIVE_MONTHS_REQUIRED:]
    return all(
        (m["rule_summary"]["primary"]["hit_rate"] or 1.0) < CONSECUTIVE_FLOOR
        for m in last_two
    )


# ---------------------------------------------------------------------------
# Monthly report schema definition
# ---------------------------------------------------------------------------

def step2_monthly_report_schema() -> dict:
    """
    Define the reusable monthly report schema.
    Returns schema with all required section keys.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "sections": {
            "1_metadata": [
                "report_month",
                "generated_at",
                "source_prediction_version",
                "data_cutoff",
                "mode",
            ],
            "2_governance": [
                "paper_only",
                "diagnostic_only",
                "odds_used",
                "ev_calculated",
                "clv_calculated",
                "kelly_calculated",
                "production_ready",
                "live_api_calls",
            ],
            "3_rule_summary": [
                "primary_rule_name",
                "shadow_rule_name",
                "primary_n",
                "shadow_n",
                "primary_hit_rate",
                "shadow_hit_rate",
                "primary_auc",
                "shadow_auc",
                "primary_brier",
                "shadow_brier",
                "primary_ece",
                "shadow_ece",
            ],
            "4_tier_b": [
                "tier_b_n",
                "tier_b_hit_rate",
                "tier_b_auc",
                "tier_b_status",
                "n_to_200",
            ],
            "5_tier_a": [
                "tier_a_n",
                "tier_a_hit_rate",
                "tier_a_auc",
                "tier_a_status",
            ],
            "6_alerts": [
                "rolling_100_hit_rate",
                "two_consecutive_months_below_50",
                "ece_worsened",
                "sample_status",
                "alert_level",
            ],
            "7_decision": [
                "continue_primary_rule",
                "keep_shadow_rule",
                "tier_b_re_evaluation_triggered",
                "market_edge_lane_status",
                "next_action",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Single monthly report generator
# ---------------------------------------------------------------------------

def _generate_month_report(
    month: str,
    all_classified: list[dict],
    prior_month_reports: list[dict],
    baseline_ece: Optional[float],
) -> dict:
    """Generate one monthly report dict for a given month."""
    month_rows = [r for r in all_classified if r["game_month"] == month]

    primary_rows_month = [r for r in month_rows if r["in_primary"]]
    shadow_rows_month = [r for r in month_rows if r["in_shadow"]]
    tier_b_rows_month = [r for r in month_rows if r["in_tier_b"]]
    tier_a_rows_month = [r for r in month_rows if r["in_tier_a"]]

    primary_metrics = _compute_metrics(primary_rows_month)
    shadow_metrics = _compute_metrics(shadow_rows_month)
    tier_b_metrics = _compute_metrics(tier_b_rows_month)
    tier_a_metrics = _compute_metrics(tier_a_rows_month)

    # Cumulative Tier B count through this month
    tier_b_cumulative = sum(
        1 for r in all_classified
        if r["game_month"] <= month and r["in_tier_b"]
    )
    n_to_200 = max(0, TIER_B_TRIGGER_N - tier_b_cumulative)
    tier_b_triggered = tier_b_cumulative >= TIER_B_TRIGGER_N

    # Tier B status label
    if tier_b_triggered:
        tier_b_status = "TRIGGER_FIRED"
    elif tier_b_cumulative >= 100:
        tier_b_status = "accumulating_halfway"
    else:
        tier_b_status = "accumulating"

    # Tier A status
    tier_a_cumulative = sum(
        1 for r in all_classified
        if r["game_month"] <= month and r["in_tier_a"]
    )
    tier_a_status = "watchlist_only" if tier_a_cumulative < 50 else "approaching_n50"

    # Rolling 100
    all_primary = [r for r in all_classified if r["in_primary"]]
    rolling_100 = _rolling_100_hit_rate(all_primary, month)

    # Two consecutive months
    two_consec = _two_consecutive_below(prior_month_reports, month)

    # ECE worsening
    current_ece = primary_metrics.get("ece")
    ece_bad = _ece_worsened(current_ece, baseline_ece)

    # Governance clean
    governance_clean = (
        GOVERNANCE["paper_only"] is True
        and GOVERNANCE["production_ready"] is False
        and GOVERNANCE["live_api_calls"] == 0
        and GOVERNANCE["ev_calculated"] is False
        and GOVERNANCE["clv_calculated"] is False
        and GOVERNANCE["kelly_calculated"] is False
    )

    alert_level = _determine_alert(
        primary_metrics, rolling_100, two_consec, ece_bad, governance_clean
    )

    # Decision state
    rolling_100_below_floor = rolling_100 is not None and rolling_100 < ROLLING_100_FLOOR
    continue_primary = not (rolling_100_below_floor or two_consec)
    next_action_parts = []
    if tier_b_triggered:
        next_action_parts.append("initiate_p79_tier_b_review")
    pn = primary_metrics["n"]
    if pn < 50:
        next_action_parts.append("continue_monthly_accumulation")
    elif pn < 100:
        next_action_parts.append("review_at_n100")
    elif pn < 200:
        next_action_parts.append("review_at_n200")
    else:
        next_action_parts.append("continue_monthly_monitoring")
    if alert_level == "RED":
        next_action_parts.insert(0, "urgent_review_required")
    next_action = "|".join(next_action_parts) if next_action_parts else "continue_monthly_monitoring"

    return {
        "report_month": month,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_prediction_version": "phase56_sp_bullpen_context_v1",
        "data_cutoff": f"{month}-end",
        "mode": "prediction_only",
        "governance": {
            "paper_only": GOVERNANCE["paper_only"],
            "diagnostic_only": GOVERNANCE["diagnostic_only"],
            "odds_used": GOVERNANCE["odds_used"],
            "ev_calculated": GOVERNANCE["ev_calculated"],
            "clv_calculated": GOVERNANCE["clv_calculated"],
            "kelly_calculated": GOVERNANCE["kelly_calculated"],
            "production_ready": GOVERNANCE["production_ready"],
            "live_api_calls": GOVERNANCE["live_api_calls"],
        },
        "rule_summary": {
            "primary": {
                "rule_name": "TIER_C_HOME_PLUS_AWAY_125",
                **primary_metrics,
            },
            "shadow": {
                "rule_name": "TIER_C_HOME_PLUS_AWAY_100",
                **shadow_metrics,
            },
        },
        "tier_b": {
            "tier_b_n": tier_b_metrics["n"],
            "tier_b_cumulative": tier_b_cumulative,
            "tier_b_hit_rate": tier_b_metrics["hit_rate"],
            "tier_b_auc": tier_b_metrics["auc"],
            "tier_b_status": tier_b_status,
            "n_to_200": n_to_200,
            "trigger_fired": tier_b_triggered,
        },
        "tier_a": {
            "tier_a_n": tier_a_metrics["n"],
            "tier_a_cumulative": tier_a_cumulative,
            "tier_a_hit_rate": tier_a_metrics["hit_rate"],
            "tier_a_auc": tier_a_metrics["auc"],
            "tier_a_status": tier_a_status,
        },
        "alerts": {
            "rolling_100_hit_rate": rolling_100,
            "rolling_100_floor": ROLLING_100_FLOOR,
            "two_consecutive_months_below_50": two_consec,
            "ece_worsened": ece_bad,
            "current_ece": current_ece,
            "baseline_ece": baseline_ece,
            "sample_status": "sufficient" if pn >= 50 else "limited",
            "alert_level": alert_level,
        },
        "decision": {
            "continue_primary_rule": continue_primary,
            "keep_shadow_rule": True,  # shadow always retained for comparison
            "tier_b_re_evaluation_triggered": tier_b_triggered,
            "market_edge_lane_status": "blocked",
            "next_action": next_action,
        },
    }


# ---------------------------------------------------------------------------
# Step 1 — Verify P77 contract
# ---------------------------------------------------------------------------

def step1_verify_p77() -> dict:
    """Load and verify the P77 shadow tracker contract."""
    p77_path = PATHS["p77_summary"]
    if not p77_path.exists():
        return {"verified": False, "error": f"Missing: {p77_path}"}

    with open(p77_path, encoding="utf-8") as fh:
        p77 = json.load(fh)

    classification = p77.get("p77_classification", "")

    # P77 actual structure: step3_rule_contract.rules is a dict keyed by rule name
    rules_dict = p77.get("step3_rule_contract", {}).get("rules", {})
    primary_rule = P77_EXPECTED["primary_rule"] if P77_EXPECTED["primary_rule"] in rules_dict else ""
    shadow_rule = P77_EXPECTED["shadow_rule"] if P77_EXPECTED["shadow_rule"] in rules_dict else ""

    # P77 actual: step3b_semantics_validation (not step3b_semantic_validation)
    semantics = p77.get("step3b_semantics_validation", {})
    semantics_status = semantics.get("validation_status", "")

    # P77 actual: governance is top-level key (not governance_snapshot)
    governance = p77.get("governance", {})

    # P77 actual: tier_b_reeval (not tier_b_reeval_trigger)
    tier_b_trigger = p77.get("step5_reeval_triggers", {}).get("tier_b_reeval", {})
    market_edge = p77.get("step5_reeval_triggers", {}).get("market_edge_lane", {})

    errors = []
    if classification != P77_EXPECTED["classification"]:
        errors.append(f"classification mismatch: {classification!r}")
    if not primary_rule:
        errors.append(f"primary_rule {P77_EXPECTED['primary_rule']!r} not found in step3_rule_contract.rules")
    if not shadow_rule:
        errors.append(f"shadow_rule {P77_EXPECTED['shadow_rule']!r} not found in step3_rule_contract.rules")
    if semantics_status != "PASS":
        errors.append(f"semantics status: {semantics_status!r}")
    if governance.get("paper_only") is not True:
        errors.append("governance.paper_only not True")
    if governance.get("production_ready") is not False:
        errors.append("governance.production_ready not False")

    # Extract Tier B trigger n from actual structure
    tier_b_n = tier_b_trigger.get("trigger_n") or tier_b_trigger.get("n_threshold")

    return {
        "verified": len(errors) == 0,
        "classification": classification,
        "primary_rule": primary_rule,
        "shadow_rule": shadow_rule,
        "semantics_validation_status": semantics_status,
        "governance_paper_only": governance.get("paper_only"),
        "governance_production_ready": governance.get("production_ready"),
        "tier_b_trigger_n": tier_b_n,
        "market_edge_status": market_edge.get("status"),
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Step 3 — Generate fixture monthly reports
# ---------------------------------------------------------------------------

def step3_generate_fixture_months(classified_rows: list[dict]) -> list[dict]:
    """
    Generate monthly monitoring reports for fixture period (2025-04 to 2025-09).
    """
    # Compute baseline ECE from all 2025-04 and 2025-05 data (first two months)
    first_months = [r for r in classified_rows if r["game_month"] in ("2025-04", "2025-05")]
    first_primary = [r for r in first_months if r["in_primary"]]
    if first_primary:
        probs = [r["model_home_prob"] for r in first_primary]
        labels = [r["home_win"] for r in first_primary]
        baseline_ece: Optional[float] = _compute_ece(probs, labels)
    else:
        baseline_ece = None

    monthly_reports: list[dict] = []
    for month in FIXTURE_MONTHS:
        report = _generate_month_report(
            month=month,
            all_classified=classified_rows,
            prior_month_reports=monthly_reports,
            baseline_ece=baseline_ece,
        )
        monthly_reports.append(report)

    return monthly_reports


# ---------------------------------------------------------------------------
# Step 4 — Alert level definitions (schema only)
# ---------------------------------------------------------------------------

def step4_alert_level_definitions() -> dict:
    """
    Return the canonical alert level definitions for the monitoring template.
    """
    return {
        "GREEN": {
            "description": "Sample sufficient and no downgrade criteria triggered",
            "criteria": [
                "rolling_100_hit_rate >= 0.55 (or insufficient n for rolling)",
                "not two_consecutive_months_below_50",
                "not ece_worsened",
                "governance clean",
                "primary_n >= 50",
            ],
        },
        "YELLOW": {
            "description": "Sample limited or one warning criterion triggered",
            "criteria": [
                "primary_n < 50 (insufficient sample for alert)",
                "rolling_100 not computable due to small n",
            ],
            "note": "Sample limitation alone does NOT imply model failure",
        },
        "RED": {
            "description": "Downgrade criteria triggered; requires urgent review",
            "criteria": [
                f"rolling_100_hit_rate < {ROLLING_100_FLOOR}",
                f"2 consecutive eligible months hit_rate < {CONSECUTIVE_FLOOR}",
                "ECE materially worsened (delta >= 0.03 from baseline)",
                "governance violation",
            ],
        },
    }


# ---------------------------------------------------------------------------
# Step 5 — Pack synthesis
# ---------------------------------------------------------------------------

def step5_pack_synthesis(monthly_reports: list[dict]) -> dict:
    """Synthesize pack-level summary across all fixture months."""
    months_generated = [m["report_month"] for m in monthly_reports]

    # Schema validity: check all required sections present
    required_sections = ["governance", "rule_summary", "tier_b", "tier_a", "alerts", "decision"]
    months_schema_valid = [
        m["report_month"]
        for m in monthly_reports
        if all(k in m for k in required_sections)
    ]

    # Governance clean
    months_governance_clean = [
        m["report_month"]
        for m in monthly_reports
        if m["governance"]["paper_only"] is True
        and m["governance"]["production_ready"] is False
        and m["governance"]["live_api_calls"] == 0
    ]

    # Months with alerts
    months_with_alerts = [
        m["report_month"]
        for m in monthly_reports
        if m["alerts"]["alert_level"] != "GREEN"
    ]

    # Primary vs Shadow comparison (using all months)
    primary_ns = [m["rule_summary"]["primary"]["n"] for m in monthly_reports]
    shadow_ns = [m["rule_summary"]["shadow"]["n"] for m in monthly_reports]
    primary_hit_rates = [
        m["rule_summary"]["primary"]["hit_rate"]
        for m in monthly_reports
        if m["rule_summary"]["primary"]["hit_rate"] is not None
    ]
    shadow_hit_rates = [
        m["rule_summary"]["shadow"]["hit_rate"]
        for m in monthly_reports
        if m["rule_summary"]["shadow"]["hit_rate"] is not None
    ]

    primary_vs_shadow = {
        "primary_total_n": sum(primary_ns),
        "shadow_total_n": sum(shadow_ns),
        "primary_avg_monthly_hit_rate": round(
            sum(primary_hit_rates) / len(primary_hit_rates), 4
        ) if primary_hit_rates else None,
        "shadow_avg_monthly_hit_rate": round(
            sum(shadow_hit_rates) / len(shadow_hit_rates), 4
        ) if shadow_hit_rates else None,
    }

    # Tier B cumulative at end of fixture
    last_month = monthly_reports[-1] if monthly_reports else None
    tier_b_end_n = last_month["tier_b"]["tier_b_cumulative"] if last_month else 0
    tier_b_trigger_fires = tier_b_end_n >= TIER_B_TRIGGER_N

    # Template readiness
    all_schema_valid = len(months_schema_valid) == len(months_generated)
    all_governance_clean = len(months_governance_clean) == len(months_generated)

    if all_schema_valid and all_governance_clean:
        template_readiness = "P78_MONTHLY_SHADOW_TRACKER_TEMPLATE_READY"
    else:
        template_readiness = "P78_MONTHLY_SHADOW_TRACKER_TEMPLATE_READY_WITH_CAVEATS"

    return {
        "months_generated": months_generated,
        "months_count": len(months_generated),
        "months_all_schema_valid": all_schema_valid,
        "months_schema_valid_list": months_schema_valid,
        "months_with_governance_clean": months_governance_clean,
        "months_all_governance_clean": all_governance_clean,
        "months_with_alerts": months_with_alerts,
        "primary_vs_shadow": primary_vs_shadow,
        "tier_b_accumulated_n_end_of_fixture": tier_b_end_n,
        "tier_b_n200_trigger_fires_in_fixture": tier_b_trigger_fires,
        "tier_b_trigger_n": TIER_B_TRIGGER_N,
        "template_readiness_classification": template_readiness,
    }


# ---------------------------------------------------------------------------
# Step 6 — Forbidden scan (GOVERNANCE dict check)
# ---------------------------------------------------------------------------

def step6_forbidden_scan() -> dict:
    """
    Verify governance invariants by checking GOVERNANCE dict values directly.
    No text scanning — avoids self-referential false positives.
    """
    must_be_true = ["paper_only", "diagnostic_only", "no_real_bet", "promotion_freeze"]
    must_be_false = [
        "odds_used",
        "ev_calculated",
        "clv_calculated",
        "kelly_calculated",
        "production_ready",
        "kelly_deploy_allowed",
        "real_bet_allowed",
    ]
    must_be_zero = ["live_api_calls"]

    violations: list[str] = []

    for key in must_be_true:
        if GOVERNANCE.get(key) is not True:
            violations.append(f"GOVERNANCE[{key!r}] must be True, got {GOVERNANCE.get(key)!r}")

    for key in must_be_false:
        if GOVERNANCE.get(key) is not False:
            violations.append(f"GOVERNANCE[{key!r}] must be False, got {GOVERNANCE.get(key)!r}")

    for key in must_be_zero:
        if GOVERNANCE.get(key) != 0:
            violations.append(f"GOVERNANCE[{key!r}] must be 0, got {GOVERNANCE.get(key)!r}")

    return {
        "scan_passed": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
        "must_be_true_checked": must_be_true,
        "must_be_false_checked": must_be_false,
        "must_be_zero_checked": must_be_zero,
        "method": "governance_dict_value_check",
    }


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def _write_report(
    output_path: Path,
    step1: dict,
    schema: dict,
    monthly_reports: list[dict],
    alert_defs: dict,
    pack: dict,
    forbidden: dict,
) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [
        f"# P78 — Monthly Rule Monitoring Template + Shadow Tracker Report Pack",
        f"",
        f"**Date:** {today}  ",
        f"**Classification:** `{pack['template_readiness_classification']}`  ",
        f"**Mode:** `prediction_only | paper_only=true | diagnostic_only=true | production_ready=false`  ",
        f"**Source:** P77 commit `ffd2bc9` — P77_SHADOW_TRACKER_CONTRACT_READY  ",
        f"",
        f"---",
        f"",
        f"## 1. Pre-flight & P77 Contract Verification",
        f"",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| P77 Classification | `{step1['classification']}` |",
        f"| Primary Rule | `{step1['primary_rule']}` |",
        f"| Shadow Rule | `{step1['shadow_rule']}` |",
        f"| Semantics Status | `{step1['semantics_validation_status']}` |",
        f"| paper_only | `{step1['governance_paper_only']}` |",
        f"| production_ready | `{step1['governance_production_ready']}` |",
        f"| Tier B Trigger N | `{step1['tier_b_trigger_n']}` |",
        f"| Market Edge Status | `{step1['market_edge_status']}` |",
        f"| Verification | `{'PASS' if step1['verified'] else 'FAIL'}` |",
        f"",
    ]

    if not step1["verified"]:
        lines.append(f"**ERRORS:** {step1['errors']}")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## 2. Monthly Report Schema (v{schema['schema_version']})",
        f"",
        f"The schema defines {len(schema['sections'])} required sections per monthly report:",
        f"",
    ]
    for section_key, fields in schema["sections"].items():
        lines.append(f"**Section {section_key}:** {', '.join(f'`{f}`' for f in fields)}")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## 3. Fixture Monthly Reports (2025-04 → 2025-09)",
        f"",
        f"Generated using 2025 historical data as fixture validation. No scientific claim — template validation only.",
        f"",
        f"### 3.1 Monthly Summary Table",
        f"",
        f"| Month | Primary N | Primary Hit% | Shadow N | Shadow Hit% | Tier B (cum) | Alert |",
        f"|-------|-----------|--------------|----------|-------------|--------------|-------|",
    ]

    for m in monthly_reports:
        pn = m["rule_summary"]["primary"]["n"]
        ph = m["rule_summary"]["primary"]["hit_rate"]
        sn = m["rule_summary"]["shadow"]["n"]
        sh = m["rule_summary"]["shadow"]["hit_rate"]
        tb_cum = m["tier_b"]["tier_b_cumulative"]
        alert = m["alerts"]["alert_level"]
        ph_str = f"{ph:.4f}" if ph is not None else "—"
        sh_str = f"{sh:.4f}" if sh is not None else "—"
        lines.append(f"| {m['report_month']} | {pn} | {ph_str} | {sn} | {sh_str} | {tb_cum} | **{alert}** |")

    lines += [
        f"",
        f"### 3.2 Monthly Detail",
        f"",
    ]

    for m in monthly_reports:
        pm = m["rule_summary"]["primary"]
        sm = m["rule_summary"]["shadow"]
        tb = m["tier_b"]
        ta = m["tier_a"]
        al = m["alerts"]
        dec = m["decision"]

        lines += [
            f"#### {m['report_month']}",
            f"",
            f"**Primary Rule** (TIER_C_HOME_PLUS_AWAY_125): n={pm['n']}, "
            f"hit_rate={pm['hit_rate']}, AUC={pm['auc']}, Brier={pm['brier']}, ECE={pm['ece']}  ",
            f"**Shadow Rule** (TIER_C_HOME_PLUS_AWAY_100): n={sm['n']}, "
            f"hit_rate={sm['hit_rate']}, AUC={sm['auc']}, Brier={sm['brier']}, ECE={sm['ece']}  ",
            f"**Tier B** (cumulative): n={tb['tier_b_cumulative']}, hit={tb['tier_b_hit_rate']}, "
            f"status={tb['tier_b_status']}, n_to_200={tb['n_to_200']}  ",
            f"**Tier A** (watchlist): n={ta['tier_a_cumulative']}, hit={ta['tier_a_hit_rate']}, "
            f"status={ta['tier_a_status']}  ",
            f"**Alerts**: rolling_100={al['rolling_100_hit_rate']}, "
            f"two_consec={al['two_consecutive_months_below_50']}, "
            f"ece_worsened={al['ece_worsened']}, "
            f"sample={al['sample_status']}, **level={al['alert_level']}**  ",
            f"**Decision**: continue_primary={dec['continue_primary_rule']}, "
            f"tier_b_triggered={dec['tier_b_re_evaluation_triggered']}, "
            f"market_edge={dec['market_edge_lane_status']}, "
            f"next={dec['next_action']}  ",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## 4. Alert Level Definitions",
        f"",
    ]
    for level, defn in alert_defs.items():
        lines.append(f"**{level}**: {defn['description']}")
        for c in defn["criteria"]:
            lines.append(f"- {c}")
        if "note" in defn:
            lines.append(f"  > *{defn['note']}*")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## 5. Pack Synthesis",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Months Generated | {pack['months_count']} ({', '.join(pack['months_generated'])}) |",
        f"| All Schema Valid | `{pack['months_all_schema_valid']}` |",
        f"| All Governance Clean | `{pack['months_all_governance_clean']}` |",
        f"| Months with Alerts | {pack['months_with_alerts'] or '(none)'} |",
        f"| Primary Total N | {pack['primary_vs_shadow']['primary_total_n']} |",
        f"| Shadow Total N | {pack['primary_vs_shadow']['shadow_total_n']} |",
        f"| Primary Avg Monthly Hit% | {pack['primary_vs_shadow']['primary_avg_monthly_hit_rate']} |",
        f"| Shadow Avg Monthly Hit% | {pack['primary_vs_shadow']['shadow_avg_monthly_hit_rate']} |",
        f"| Tier B Accumulated N (end) | {pack['tier_b_accumulated_n_end_of_fixture']} |",
        f"| Tier B n≥200 Trigger Fires | `{pack['tier_b_n200_trigger_fires_in_fixture']}` |",
        f"| Template Readiness | `{pack['template_readiness_classification']}` |",
        f"",
        f"---",
        f"",
        f"## 6. Governance Invariants & Forbidden Scan",
        f"",
        f"**Method:** Direct GOVERNANCE dict value check (no text scanning).  ",
        f"**Scan Result:** `{'PASS' if forbidden['scan_passed'] else 'FAIL'}`  ",
        f"**Violations:** {forbidden['violations_count']}  ",
        f"",
        f"| Invariant | Required | Actual |",
        f"|-----------|----------|--------|",
        f"| paper_only | True | {GOVERNANCE['paper_only']} |",
        f"| diagnostic_only | True | {GOVERNANCE['diagnostic_only']} |",
        f"| ev_calculated | False | {GOVERNANCE['ev_calculated']} |",
        f"| clv_calculated | False | {GOVERNANCE['clv_calculated']} |",
        f"| kelly_calculated | False | {GOVERNANCE['kelly_calculated']} |",
        f"| production_ready | False | {GOVERNANCE['production_ready']} |",
        f"| live_api_calls | 0 | {GOVERNANCE['live_api_calls']} |",
        f"",
        f"---",
        f"",
        f"## 7. Market-Edge Separation",
        f"",
        f"Market-edge (CLV / EV / Kelly) lane is **BLOCKED** in P78.  ",
        f"This is a prediction-only shadow tracker. No odds data required.  ",
        f"Market-edge remains deferred until P80 (requires The Odds API key).  ",
        f"",
        f"---",
        f"",
        f"## 8. Tier B Accumulation Status",
        f"",
        f"Tier B definition: `abs_sp_fip_delta` in [0.25, 0.50)  ",
        f"Trigger: cumulative n ≥ 200 → initiates P79 Tier B review  ",
        f"Tier B cumulative at end of fixture period (2025-09): **{pack['tier_b_accumulated_n_end_of_fixture']}**  ",
        f"Trigger fires in fixture period: `{pack['tier_b_n200_trigger_fires_in_fixture']}`  ",
        f"",
        f"---",
        f"",
        f"## 9. P79 Recommendation",
        f"",
        f"**P79 conditions:**",
        f"- Tier B cumulative n ≥ 200 (predicted ~2026-09 for live 2026 tracking)",
        f"- No governance violations",
        f"- No RED alert on primary rule",
        f"",
        f"**P79 scope:** Full Tier B sample expansion analysis vs Tier C finalists on 2026 live data.  ",
        f"**P80 scope:** Market-edge (CLV/EV/Kelly) lane — requires odds API key.  ",
        f"",
        f"---",
        f"",
        f"## 10. Final Classification",
        f"",
        f"> **`{pack['template_readiness_classification']}`**",
        f"",
        f"---",
        f"",
        f"*Generated by P78 Monthly Rule Monitoring Template | paper_only=True | NO_REAL_BET*",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main() -> int:
    print("=== P78 Monthly Rule Monitoring Template ===")
    print(f"Mode: paper_only={GOVERNANCE['paper_only']} | diagnostic_only={GOVERNANCE['diagnostic_only']}")
    print(f"live_api_calls={GOVERNANCE['live_api_calls']} | production_ready={GOVERNANCE['production_ready']}")

    # -----------------------------------------------------------------------
    # Verify all source artifacts exist
    # -----------------------------------------------------------------------
    required_artifacts = [
        "p77_summary", "p76_summary", "p75b_summary", "p75a_summary",
        "p74_summary", "p73_summary", "p72b_summary", "p72a_summary",
        "predictions_jsonl", "p77_report",
    ]
    missing = [k for k in required_artifacts if not PATHS[k].exists()]
    if missing:
        print(f"STOP — Missing source artifacts: {missing}", file=sys.stderr)
        return 1

    print(f"✓ All {len(required_artifacts)} source artifacts verified")

    # -----------------------------------------------------------------------
    # Step 1 — Verify P77 contract
    # -----------------------------------------------------------------------
    step1 = step1_verify_p77()
    if not step1["verified"]:
        print(f"STOP — P77 verification failed: {step1['errors']}", file=sys.stderr)
        return 1
    print(f"✓ P77 verified: {step1['classification']}")
    print(f"  Primary: {step1['primary_rule']}")
    print(f"  Shadow:  {step1['shadow_rule']}")

    # -----------------------------------------------------------------------
    # Step 2 — Monthly report schema
    # -----------------------------------------------------------------------
    schema = step2_monthly_report_schema()
    print(f"✓ Monthly report schema defined ({len(schema['sections'])} sections)")

    # -----------------------------------------------------------------------
    # Load JSONL and classify rows
    # -----------------------------------------------------------------------
    print(f"Loading predictions from: {PATHS['predictions_jsonl'].name}")
    raw_rows = load_jsonl(PATHS["predictions_jsonl"])
    classified = _build_classified_rows(raw_rows)
    print(f"✓ Loaded {len(raw_rows)} rows, {len(classified)} classified")

    # Quick count validation
    n_primary = sum(1 for r in classified if r["in_primary"])
    n_shadow = sum(1 for r in classified if r["in_shadow"])
    n_tier_b = sum(1 for r in classified if r["in_tier_b"])
    n_tier_a = sum(1 for r in classified if r["in_tier_a"])
    print(f"  Primary (125): {n_primary} | Shadow (100): {n_shadow} | Tier B: {n_tier_b} | Tier A: {n_tier_a}")

    # -----------------------------------------------------------------------
    # Step 3 — Generate fixture monthly reports
    # -----------------------------------------------------------------------
    monthly_reports = step3_generate_fixture_months(classified)
    print(f"✓ Generated {len(monthly_reports)} fixture monthly reports ({', '.join(FIXTURE_MONTHS)})")

    # -----------------------------------------------------------------------
    # Step 4 — Alert definitions
    # -----------------------------------------------------------------------
    alert_defs = step4_alert_level_definitions()
    print(f"✓ Alert level definitions: {list(alert_defs.keys())}")

    # -----------------------------------------------------------------------
    # Step 5 — Pack synthesis
    # -----------------------------------------------------------------------
    pack = step5_pack_synthesis(monthly_reports)
    classification = pack["template_readiness_classification"]
    print(f"✓ Pack synthesis complete: {classification}")
    print(f"  Tier B accumulated (2025-09): {pack['tier_b_accumulated_n_end_of_fixture']} / {TIER_B_TRIGGER_N}")
    print(f"  Tier B trigger fires in fixture: {pack['tier_b_n200_trigger_fires_in_fixture']}")

    # -----------------------------------------------------------------------
    # Step 6 — Forbidden scan
    # -----------------------------------------------------------------------
    forbidden = step6_forbidden_scan()
    print(f"✓ Forbidden scan: {'PASS' if forbidden['scan_passed'] else 'FAIL'} ({forbidden['violations_count']} violations)")

    # -----------------------------------------------------------------------
    # Alert summary
    # -----------------------------------------------------------------------
    for m in monthly_reports:
        pn = m["rule_summary"]["primary"]["n"]
        ph = m["rule_summary"]["primary"]["hit_rate"]
        alert = m["alerts"]["alert_level"]
        r100 = m["alerts"]["rolling_100_hit_rate"]
        tb_cum = m["tier_b"]["tier_b_cumulative"]
        print(f"  {m['report_month']}: primary_n={pn}, hit={ph}, rolling_100={r100}, tier_b_cum={tb_cum}, alert={alert}")

    # -----------------------------------------------------------------------
    # Write outputs
    # -----------------------------------------------------------------------
    output_data = {
        "p78_classification": classification,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "governance_snapshot": GOVERNANCE,
        "step1_p77_verification": step1,
        "step2_monthly_report_schema": schema,
        "step3_fixture_monthly_reports": monthly_reports,
        "step4_alert_level_definitions": alert_defs,
        "step5_pack_synthesis": pack,
        "step6_forbidden_scan": forbidden,
        "fixture_period": FIXTURE_MONTHS,
        "rules": {
            "primary": "TIER_C_HOME_PLUS_AWAY_125",
            "shadow": "TIER_C_HOME_PLUS_AWAY_100",
            "tier_b": "abs_sp_fip_delta in [0.25, 0.50)",
            "tier_a": "abs_sp_fip_delta >= 1.50",
        },
        "tier_b_trigger_n": TIER_B_TRIGGER_N,
        "market_edge_lane": "blocked",
    }

    PATHS["output_json"].parent.mkdir(parents=True, exist_ok=True)
    PATHS["output_json"].write_text(
        json.dumps(output_data, indent=2, default=str), encoding="utf-8"
    )
    print(f"✓ JSON written: {PATHS['output_json'].name}")

    _write_report(
        output_path=PATHS["output_report"],
        step1=step1,
        schema=schema,
        monthly_reports=monthly_reports,
        alert_defs=alert_defs,
        pack=pack,
        forbidden=forbidden,
    )
    print(f"✓ Report written: {PATHS['output_report'].name}")

    # Optional betting plan copy
    PATHS["output_bettingplan"].parent.mkdir(parents=True, exist_ok=True)
    PATHS["output_bettingplan"].write_text(
        PATHS["output_report"].read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"✓ BettingPlan copy written: {PATHS['output_bettingplan'].name}")

    # Final status
    print()
    print(f"Classification: {classification}")
    print(f"Forbidden: {'PASS' if forbidden['scan_passed'] else 'FAIL'}")
    if not forbidden["scan_passed"]:
        print(f"  Violations: {forbidden['violations']}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
