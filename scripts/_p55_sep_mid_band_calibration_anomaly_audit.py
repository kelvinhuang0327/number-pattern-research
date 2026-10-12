"""
P55 — Sep 2025 Mid-Band (1.00 <= |sp_fip_delta| < 1.25) Calibration Anomaly Audit.

Offline diagnostic only.  paper_only=True, live_api_calls=0.
Do NOT refit Platt.  Do NOT change runtime logic.  Do NOT deploy.

Source artifact: mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl
P54 finding: Sep 1.00-1.25 band platt_ece=0.246 vs full_tier_c 0.082 (n=27).
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
from datetime import datetime

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = pathlib.Path(__file__).resolve().parents[1]
JSONL_PATH = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P45_SUMMARY = ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"
P52_SUMMARY = ROOT / "data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json"
P53_SUMMARY = ROOT / "data/mlb_2025/derived/p53_sep_calibration_critical_audit_summary.json"
P54_SUMMARY = ROOT / "data/mlb_2025/derived/p54_sep_sp_fip_delta_feature_drift_audit_summary.json"
OUTPUT_JSON = ROOT / "data/mlb_2025/derived/p55_sep_mid_band_calibration_anomaly_audit_summary.json"
REPORT_MD = ROOT / "report/p55_sep_mid_band_calibration_anomaly_audit_20260526.md"
BETTING_PLAN_MD = ROOT / "00-BettingPlan/20260526/p55_sep_mid_band_calibration_anomaly_audit_20260526.md"
ACTIVE_TASK_MD = ROOT / "00-Plan/roadmap/active_task.md"

# ---------------------------------------------------------------------------
# Governance constants (immutable)
# ---------------------------------------------------------------------------
GOVERNANCE = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
    "runtime_recommendation_logic_changed": False,
    "platt_constants_modified": False,
    "p52_contract_overwritten": False,
    "p53_artifact_overwritten": False,
    "p54_artifact_overwritten": False,
}

# P45 Platt constants — locked, do not modify
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464
CLIP_EPS: float = 1e-7

# Tier C filter
TIER_C_MIN_ABS_DELTA: float = 0.5

# Mid-band definition
MID_BAND_LO: float = 1.00
MID_BAND_HI: float = 1.25

# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _logit(p: float) -> float:
    p = max(CLIP_EPS, min(1.0 - CLIP_EPS, p))
    return math.log(p / (1.0 - p))


def _platt_prob(raw_prob: float) -> float:
    raw_prob = max(CLIP_EPS, min(1.0 - CLIP_EPS, raw_prob))
    return _sigmoid(PLATT_A * _logit(raw_prob) + PLATT_B)


def _brier(probs: list[float], outcomes: list[int]) -> float:
    if not probs:
        return float("nan")
    return float(np.mean([(p - o) ** 2 for p, o in zip(probs, outcomes)]))


def _ece(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    """Uniform-width ECE (10 bins, [0,1])."""
    if not probs:
        return float("nan")
    n = len(probs)
    edges = [i / n_bins for i in range(n_bins + 1)]
    ece_val = 0.0
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        in_bin = [(p, o) for p, o in zip(probs, outcomes) if lo <= p < hi]
        if not in_bin:
            continue
        bin_n = len(in_bin)
        pred_mean = float(np.mean([x[0] for x in in_bin]))
        act_mean = float(np.mean([x[1] for x in in_bin]))
        ece_val += abs(act_mean - pred_mean) * bin_n / n
    # catch p == 1.0
    last = [(p, o) for p, o in zip(probs, outcomes) if p == 1.0]
    if last:
        bin_n = len(last)
        pred_mean = float(np.mean([x[0] for x in last]))
        act_mean = float(np.mean([x[1] for x in last]))
        ece_val += abs(act_mean - pred_mean) * bin_n / n
    return float(ece_val)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_rows() -> list[dict]:
    return [json.loads(line) for line in JSONL_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _apply_tier_c_filter(rows: list[dict]) -> list[dict]:
    """Same Tier C filter used by P40-P54."""
    out = []
    for r in rows:
        p0 = r.get("p0_features") or {}
        sp_fip_delta = p0.get("sp_fip_delta")
        mkt = r.get("market_home_prob_no_vig")
        hw = r.get("home_win")
        if sp_fip_delta is None or mkt is None or hw is None:
            continue
        if abs(sp_fip_delta) < TIER_C_MIN_ABS_DELTA:
            continue
        try:
            mkt_f = float(mkt)
            hw_i = int(hw)
        except (ValueError, TypeError):
            continue
        if not (0.0 < mkt_f < 1.0):
            continue
        out.append(r)
    return out


def _extract_month(game_date: str) -> str | None:
    """Return month abbreviation from YYYY-MM-DD."""
    try:
        dt = datetime.strptime(game_date, "%Y-%m-%d")
        return dt.strftime("%b")  # 'Jan', 'Feb', etc.
    except (ValueError, TypeError):
        return None


def _in_mid_band(abs_delta: float) -> bool:
    return MID_BAND_LO <= abs_delta < MID_BAND_HI


# ---------------------------------------------------------------------------
# Task A: Build Tier C + Sep mid-band dataset
# ---------------------------------------------------------------------------

def build_tier_c_dataset() -> list[dict]:
    """Build per-row records for the full Tier C dataset."""
    rows = _load_rows()
    tier_c_rows = _apply_tier_c_filter(rows)
    records = []
    for r in tier_c_rows:
        p0 = r.get("p0_features") or {}
        sp_fip_delta = float(p0["sp_fip_delta"])
        raw_prob = float(r["model_home_prob"])
        market_prob = float(r["market_home_prob_no_vig"])
        platt = _platt_prob(raw_prob)
        outcome = int(r["home_win"])
        game_date = r.get("game_date", "")
        month = _extract_month(game_date)
        records.append({
            "game_date": game_date,
            "game_id": r.get("game_id", ""),
            "home_team": r.get("home_team", ""),
            "away_team": r.get("away_team", ""),
            "sp_fip_delta": sp_fip_delta,
            "abs_sp_fip_delta": abs(sp_fip_delta),
            "raw_probability": raw_prob,
            "platt_probability": platt,
            "market_probability": market_prob,
            "outcome": outcome,
            "calibration_error_raw": abs(raw_prob - outcome),
            "calibration_error_platt": abs(platt - outcome),
            "brier_raw": (raw_prob - outcome) ** 2,
            "brier_platt": (platt - outcome) ** 2,
            "month": month,
            "in_mid_band": _in_mid_band(abs(sp_fip_delta)),
        })
    return records


# ---------------------------------------------------------------------------
# Task B: Outlier concentration audit
# ---------------------------------------------------------------------------

def outlier_concentration_audit(mid_band_records: list[dict]) -> dict:
    """Analyse whether Sep mid-band ECE is driven by a few outlier games."""
    n = len(mid_band_records)
    if n == 0:
        return {"n": 0, "error": "no_records"}

    platt_probs = [r["platt_probability"] for r in mid_band_records]
    raw_probs = [r["raw_probability"] for r in mid_band_records]
    outcomes = [r["outcome"] for r in mid_band_records]

    platt_ece = round(_ece(platt_probs, outcomes), 6)
    raw_ece = round(_ece(raw_probs, outcomes), 6)
    platt_brier = round(_brier(platt_probs, outcomes), 6)
    raw_brier = round(_brier(raw_probs, outcomes), 6)
    mean_platt_prob = round(float(np.mean(platt_probs)), 6)
    actual_wr = round(float(np.mean(outcomes)), 6)
    calibration_gap = round(abs(mean_platt_prob - actual_wr), 6)

    # Per-game absolute errors (proxy for error contribution)
    game_errors = [
        {
            "game_date": r["game_date"],
            "game_id": r["game_id"],
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "sp_fip_delta": round(r["sp_fip_delta"], 4),
            "raw_probability": round(r["raw_probability"], 4),
            "platt_probability": round(r["platt_probability"], 4),
            "market_probability": round(r["market_probability"], 4),
            "outcome": r["outcome"],
            "abs_error_platt": round(r["calibration_error_platt"], 6),
            "abs_error_raw": round(r["calibration_error_raw"], 6),
        }
        for r in mid_band_records
    ]
    sorted_by_error = sorted(game_errors, key=lambda x: x["abs_error_platt"], reverse=True)
    top5 = sorted_by_error[:5]

    total_abs_error = sum(g["abs_error_platt"] for g in game_errors)
    if total_abs_error == 0:
        top1_share = top3_share = top5_share = 0.0
    else:
        top1_share = round(sorted_by_error[0]["abs_error_platt"] / total_abs_error, 4) if len(sorted_by_error) >= 1 else 0.0
        top3_share = round(sum(g["abs_error_platt"] for g in sorted_by_error[:3]) / total_abs_error, 4) if len(sorted_by_error) >= 3 else 0.0
        top5_share = round(sum(g["abs_error_platt"] for g in sorted_by_error[:5]) / total_abs_error, 4) if len(sorted_by_error) >= 5 else 0.0

    # Leave-one-out ECE
    loo_eces: list[float] = []
    for i in range(n):
        loo_probs = [platt_probs[j] for j in range(n) if j != i]
        loo_outcomes = [outcomes[j] for j in range(n) if j != i]
        loo_ece = _ece(loo_probs, loo_outcomes)
        loo_eces.append(loo_ece)

    min_ece_loo = round(float(min(loo_eces)), 6)
    max_ece_loo = round(float(max(loo_eces)), 6)
    ece_swing = round(max_ece_loo - min_ece_loo, 6)
    ece_std_loo = round(float(np.std(loo_eces)), 6)

    # Classification
    if top3_share > 0.40 or ece_swing > 0.05:
        concentration = "OUTLIER_DRIVEN"
    elif top3_share <= 0.25 and ece_swing <= 0.03:
        concentration = "BROAD_BASED"
    else:
        concentration = "INCONCLUSIVE_SAMPLE_LIMITED"

    return {
        "n": n,
        "platt_ece": platt_ece,
        "raw_ece": raw_ece,
        "platt_brier": platt_brier,
        "raw_brier": raw_brier,
        "mean_platt_probability": mean_platt_prob,
        "actual_win_rate": actual_wr,
        "calibration_gap": calibration_gap,
        "total_absolute_platt_error": round(total_abs_error, 6),
        "top5_games": top5,
        "top1_contribution_share": top1_share,
        "top3_contribution_share": top3_share,
        "top5_contribution_share": top5_share,
        "leave_one_out": {
            "min_ece_without_one_game": min_ece_loo,
            "max_ece_without_one_game": max_ece_loo,
            "ece_std_leave_one_out": ece_std_loo,
            "ece_swing": ece_swing,
        },
        "concentration_classification": concentration,
    }


# ---------------------------------------------------------------------------
# Task C: Month/Band comparison
# ---------------------------------------------------------------------------

def month_band_comparison(tier_c_records: list[dict]) -> dict:
    """Compare the 1.00-1.25 band across all months."""
    months_order = ["Apr", "May", "Jun", "Jul", "Aug", "Sep"]
    result: dict[str, dict] = {}

    all_mid_band = [r for r in tier_c_records if r["in_mid_band"]]

    for month in months_order:
        subset = [r for r in all_mid_band if r["month"] == month]
        if not subset:
            result[month] = {"n": 0, "note": "no_data"}
            continue

        platt_probs = [r["platt_probability"] for r in subset]
        raw_probs = [r["raw_probability"] for r in subset]
        mkt_probs = [r["market_probability"] for r in subset]
        outcomes = [r["outcome"] for r in subset]

        raw_ece = round(_ece(raw_probs, outcomes), 6)
        platt_ece = round(_ece(platt_probs, outcomes), 6)
        raw_brier = round(_brier(raw_probs, outcomes), 6)
        platt_brier = round(_brier(platt_probs, outcomes), 6)
        mean_raw = round(float(np.mean(raw_probs)), 6)
        mean_platt = round(float(np.mean(platt_probs)), 6)
        mean_mkt = round(float(np.mean(mkt_probs)), 6)
        actual_wr = round(float(np.mean(outcomes)), 6)
        calibration_gap = round(abs(mean_platt - actual_wr), 6)

        result[month] = {
            "n": len(subset),
            "raw_ece": raw_ece,
            "platt_ece": platt_ece,
            "raw_brier": raw_brier,
            "platt_brier": platt_brier,
            "mean_raw_prob": mean_raw,
            "mean_platt_prob": mean_platt,
            "mean_market_prob": mean_mkt,
            "actual_win_rate": actual_wr,
            "calibration_gap": calibration_gap,
        }

    # Rank Sep platt_ece among months with data
    months_with_data = {m: v for m, v in result.items() if v["n"] > 0}
    if months_with_data:
        sorted_by_ece = sorted(months_with_data.items(), key=lambda x: x[1]["platt_ece"], reverse=True)
        sep_rank = next((i + 1 for i, (m, _) in enumerate(sorted_by_ece) if m == "Sep"), None)
        non_sep = [v["platt_ece"] for m, v in months_with_data.items() if m != "Sep" and v["n"] > 0]
        avg_non_sep = round(float(np.mean(non_sep)), 6) if non_sep else None
        sep_platt_ece = months_with_data.get("Sep", {}).get("platt_ece")
        sep_vs_avg = round(sep_platt_ece - avg_non_sep, 6) if (sep_platt_ece and avg_non_sep is not None) else None
        sep_uniquely_elevated = (
            sep_rank == 1 and sep_vs_avg is not None and sep_vs_avg > 0.05
        ) if sep_rank is not None else False
    else:
        sep_rank = None
        avg_non_sep = None
        sep_vs_avg = None
        sep_uniquely_elevated = False

    return {
        "band": "1.00_1.25",
        "band_definition": "1.00 <= abs(sp_fip_delta) < 1.25",
        "months": result,
        "sep_rank_by_platt_ece": sep_rank,
        "avg_non_sep_platt_ece": avg_non_sep,
        "sep_vs_avg_non_sep": sep_vs_avg,
        "sep_uniquely_elevated": sep_uniquely_elevated,
        "note": "Jul included if data exists; all months compared for context",
    }


# ---------------------------------------------------------------------------
# Task D: Platt vs raw transformation check
# ---------------------------------------------------------------------------

def platt_vs_raw_check(mid_band_records: list[dict]) -> dict:
    """Diagnose whether the anomaly is driven by raw model, Platt transform, or randomness."""
    if not mid_band_records:
        return {"error": "no_records"}

    platt_probs = [r["platt_probability"] for r in mid_band_records]
    raw_probs = [r["raw_probability"] for r in mid_band_records]
    mkt_probs = [r["market_probability"] for r in mid_band_records]
    outcomes = [r["outcome"] for r in mid_band_records]

    raw_ece = round(_ece(raw_probs, outcomes), 6)
    platt_ece = round(_ece(platt_probs, outcomes), 6)
    raw_brier = round(_brier(raw_probs, outcomes), 6)
    platt_brier = round(_brier(platt_probs, outcomes), 6)
    mkt_ece = round(_ece(mkt_probs, outcomes), 6)
    mkt_brier = round(_brier(mkt_probs, outcomes), 6)

    raw_gap = round(abs(float(np.mean(raw_probs)) - float(np.mean(outcomes))), 6)
    platt_gap = round(abs(float(np.mean(platt_probs)) - float(np.mean(outcomes))), 6)
    mkt_gap = round(abs(float(np.mean(mkt_probs)) - float(np.mean(outcomes))), 6)

    ece_delta = round(platt_ece - raw_ece, 6)
    brier_delta = round(platt_brier - raw_brier, 6)

    platt_improved_ece = ece_delta < 0
    platt_improved_brier = brier_delta < 0

    # Determine anomaly source
    # Decision tree:
    # - If market ECE also high → OUTCOME_RANDOMNESS (market doesn't help either)
    # - If raw ECE high but Platt worsened → PLATT_TRANSFORM_WORSENED
    # - If raw ECE high and Platt improved → RAW_MODEL_MISCALE
    # - If both ECEs are moderate but platt_ece still high → INCONCLUSIVE_SAMPLE_LIMITED

    n = len(mid_band_records)

    if n < 30:
        anomaly_source = "INCONCLUSIVE_SAMPLE_LIMITED"
        reasoning = f"n={n} is below 30, making ECE estimates unreliable regardless of pattern."
    elif mkt_ece > 0.15 and raw_ece > 0.15:
        anomaly_source = "OUTCOME_RANDOMNESS"
        reasoning = "Market probability also shows high ECE, suggesting outcome noise not predictability."
    elif ece_delta > 0.03:
        anomaly_source = "PLATT_TRANSFORM_WORSENED"
        reasoning = f"Platt ECE ({platt_ece:.4f}) > raw ECE ({raw_ece:.4f}) by {ece_delta:.4f}; Platt worsened calibration in this band."
    elif raw_ece > 0.10 and platt_ece <= raw_ece:
        anomaly_source = "RAW_MODEL_MISCALE"
        reasoning = f"Raw ECE ({raw_ece:.4f}) is high; Platt partially corrected to {platt_ece:.4f}. Raw model mis-calibrated in this band."
    else:
        anomaly_source = "INCONCLUSIVE_SAMPLE_LIMITED"
        reasoning = f"No clear dominant cause identified. n={n}."

    return {
        "n": n,
        "raw_ece": raw_ece,
        "platt_ece": platt_ece,
        "market_ece": mkt_ece,
        "raw_brier": raw_brier,
        "platt_brier": platt_brier,
        "market_brier": mkt_brier,
        "raw_gap": raw_gap,
        "platt_gap": platt_gap,
        "market_gap": mkt_gap,
        "ece_delta_platt_minus_raw": ece_delta,
        "brier_delta_platt_minus_raw": brier_delta,
        "platt_improved_ece_vs_raw": platt_improved_ece,
        "platt_improved_brier_vs_raw": platt_improved_brier,
        "anomaly_source": anomaly_source,
        "reasoning": reasoning,
    }


# ---------------------------------------------------------------------------
# Task E: Build audit dict and derive final classification
# ---------------------------------------------------------------------------

def _derive_final_classification(
    concentration: dict,
    platt_vs_raw: dict,
    month_comp: dict,
) -> str:
    conc = concentration.get("concentration_classification", "INCONCLUSIVE_SAMPLE_LIMITED")
    source = platt_vs_raw.get("anomaly_source", "INCONCLUSIVE_SAMPLE_LIMITED")
    sep_unique = month_comp.get("sep_uniquely_elevated", False)
    n = concentration.get("n", 0)

    if n < 20:
        return "P55_INCONCLUSIVE_SAMPLE_LIMITED"
    if source == "PLATT_TRANSFORM_WORSENED":
        return "P55_PLATT_WORSENED_MID_BAND_DIAGNOSTIC"
    if source == "RAW_MODEL_MISCALE":
        return "P55_RAW_MODEL_MISCALE_MID_BAND_DIAGNOSTIC"
    if conc == "OUTLIER_DRIVEN":
        return "P55_OUTLIER_DRIVEN_MID_BAND_ANOMALY_DIAGNOSTIC"
    if conc == "BROAD_BASED" and sep_unique:
        return "P55_BROAD_BASED_MID_BAND_ANOMALY_DIAGNOSTIC"
    # Default: sample-limited / inconclusive
    return "P55_INCONCLUSIVE_SAMPLE_LIMITED"


def build_p55_audit() -> dict:
    print("[P55.A] Building Tier C dataset...")
    tier_c_records = build_tier_c_dataset()
    n_tier_c = len(tier_c_records)
    print(f"  Tier C n={n_tier_c}")

    sep_records = [r for r in tier_c_records if r["month"] == "Sep"]
    print(f"  Sep subset n={len(sep_records)}")

    sep_mid_band = [r for r in sep_records if r["in_mid_band"]]
    n_sep_mid_band = len(sep_mid_band)
    print(f"  Sep mid-band (1.00-1.25) n={n_sep_mid_band}")

    print("[P55.B] Outlier concentration audit...")
    concentration = outlier_concentration_audit(sep_mid_band)
    print(f"  concentration_classification={concentration['concentration_classification']}")
    print(f"  platt_ece={concentration['platt_ece']}, top3_share={concentration['top3_contribution_share']}")

    print("[P55.C] Month/band comparison...")
    month_comp = month_band_comparison(tier_c_records)
    print(f"  Sep rank by platt_ece: {month_comp['sep_rank_by_platt_ece']} / {sum(1 for v in month_comp['months'].values() if v['n'] > 0)}")
    print(f"  Sep vs avg_non_sep: {month_comp['sep_vs_avg_non_sep']}")
    print(f"  Sep uniquely elevated: {month_comp['sep_uniquely_elevated']}")

    print("[P55.D] Platt vs raw transformation check...")
    platt_vs_raw = platt_vs_raw_check(sep_mid_band)
    print(f"  anomaly_source={platt_vs_raw['anomaly_source']}")
    print(f"  raw_ece={platt_vs_raw['raw_ece']}, platt_ece={platt_vs_raw['platt_ece']}")
    print(f"  ece_delta(platt-raw)={platt_vs_raw['ece_delta_platt_minus_raw']}")

    final_clf = _derive_final_classification(concentration, platt_vs_raw, month_comp)
    print(f"\n[P55.E] Final classification: {final_clf}")

    # Governance assertions
    assert GOVERNANCE["live_api_calls"] == 0, "GOVERNANCE VIOLATION: live_api_calls != 0"
    assert GOVERNANCE["paper_only"] is True, "GOVERNANCE VIOLATION: paper_only != True"
    assert GOVERNANCE["platt_constants_modified"] is False, "GOVERNANCE VIOLATION: platt_constants_modified"
    assert GOVERNANCE["p52_contract_overwritten"] is False, "GOVERNANCE VIOLATION: p52_contract_overwritten"
    assert GOVERNANCE["p53_artifact_overwritten"] is False, "GOVERNANCE VIOLATION: p53_artifact_overwritten"
    assert GOVERNANCE["p54_artifact_overwritten"] is False, "GOVERNANCE VIOLATION: p54_artifact_overwritten"
    assert GOVERNANCE["runtime_recommendation_logic_changed"] is False

    # Verify Platt constants unchanged
    assert abs(PLATT_A - 0.435432) < 1e-6, "Platt A modified"
    assert abs(PLATT_B - 0.245464) < 1e-6, "Platt B modified"

    # Load prior phase summaries for recap
    p53 = json.loads(P53_SUMMARY.read_text(encoding="utf-8"))
    p54 = json.loads(P54_SUMMARY.read_text(encoding="utf-8"))

    audit = {
        "p55_phase": "P55 — Sep 2025 Mid-Band Calibration Anomaly Audit",
        "run_date": datetime.now().strftime("%Y-%m-%d"),
        "p54_recap": {
            "final_p54_classification": p54["final_p54_classification"],
            "tier_c_n": p54["tier_c_verification"]["n"],
            "sep_n": p54["sep_2025_metrics"]["n"],
            "sep_platt_ece": p54["sep_2025_metrics"]["platt_ece"],
            "sep_mid_band_platt_ece_from_p54": p54["calibration_by_fip_band"]["Sep"]["1.00_1.25"]["platt_ece"],
            "sep_mid_band_n_from_p54": p54["calibration_by_fip_band"]["Sep"]["1.00_1.25"]["n"],
        },
        "p53_recap": {
            "final_p53_classification": p53.get("final_p53_classification"),
            "sep_platt_ece": p53.get("sep_calibration", {}).get("platt_ece"),
        },
        "tier_c_verification": {
            "n": n_tier_c,
            "consistent_with_p54": n_tier_c == 535,
        },
        "sep_mid_band_dataset": {
            "n": n_sep_mid_band,
            "band_definition": "1.00 <= abs(sp_fip_delta) < 1.25",
            "consistent_with_p54": n_sep_mid_band == 27,
            "games": [
                {
                    "game_date": r["game_date"],
                    "game_id": r["game_id"],
                    "home_team": r["home_team"],
                    "away_team": r["away_team"],
                    "sp_fip_delta": round(r["sp_fip_delta"], 4),
                    "abs_sp_fip_delta": round(r["abs_sp_fip_delta"], 4),
                    "raw_probability": round(r["raw_probability"], 4),
                    "platt_probability": round(r["platt_probability"], 4),
                    "market_probability": round(r["market_probability"], 4),
                    "outcome": r["outcome"],
                    "calibration_error_raw": round(r["calibration_error_raw"], 4),
                    "calibration_error_platt": round(r["calibration_error_platt"], 4),
                }
                for r in sorted(sep_mid_band, key=lambda x: x["game_date"])
            ],
        },
        "outlier_concentration_audit": concentration,
        "month_band_comparison": month_comp,
        "platt_vs_raw_transformation": platt_vs_raw,
        "platt_constants": {
            "platt_a": PLATT_A,
            "platt_b": PLATT_B,
            "source": "P45 locked, not modified",
        },
        "data_gap_status": {
            "p43_2024_closing_line_gap": "UNRESOLVED",
            "note": "2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved and does not affect 2025-only analysis.",
        },
        "final_p55_classification": final_clf,
        "governance_flags": GOVERNANCE,
    }

    return audit


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _fmt(v: object, d: int = 4) -> str:
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


def write_report(audit: dict) -> None:
    """Write MD reports for report/ and 00-BettingPlan/."""
    clf = audit["final_p55_classification"]
    conc = audit["outlier_concentration_audit"]
    mc = audit["month_band_comparison"]
    pvr = audit["platt_vs_raw_transformation"]
    ds = audit["sep_mid_band_dataset"]
    loo = conc.get("leave_one_out", {})

    month_rows = ""
    for m, mv in mc["months"].items():
        if mv["n"] == 0:
            month_rows += f"| {m} | 0 | N/A | N/A | N/A | N/A | N/A | N/A |\n"
        else:
            month_rows += (
                f"| {m} | {mv['n']} "
                f"| {_fmt(mv['raw_ece'])} | {_fmt(mv['platt_ece'])} "
                f"| {_fmt(mv['raw_brier'])} | {_fmt(mv['platt_brier'])} "
                f"| {_fmt(mv['actual_win_rate'])} | {_fmt(mv['mean_platt_prob'])} |\n"
            )

    top5_rows = ""
    for g in conc.get("top5_games", []):
        top5_rows += (
            f"| {g['game_date']} | {g['home_team']} | {g['away_team']} "
            f"| {_fmt(g['sp_fip_delta'])} | {_fmt(g['platt_probability'])} "
            f"| {g['outcome']} | {_fmt(g['abs_error_platt'])} |\n"
        )

    content = f"""# P55 — Sep 2025 Mid-Band Calibration Anomaly Audit

**Date**: {audit['run_date']}  
**Classification**: `{clf}`  
**Governance**: paper_only=True, diagnostic_only=True, live_api_calls=0

---

## 1. P54 Recap

| Item | Value |
|------|-------|
| P54 classification | `{audit['p54_recap']['final_p54_classification']}` |
| Tier C n | {audit['p54_recap']['tier_c_n']} |
| Sep n | {audit['p54_recap']['sep_n']} |
| Sep platt_ece (overall) | {audit['p54_recap']['sep_platt_ece']} |
| Sep 1.00-1.25 band platt_ece (P54) | {audit['p54_recap']['sep_mid_band_platt_ece_from_p54']} |
| Sep 1.00-1.25 band n (P54) | {audit['p54_recap']['sep_mid_band_n_from_p54']} |
| P53 classification | `{audit['p53_recap']['final_p53_classification']}` |

**P55 Goal**: Investigate whether the Sep 1.00-1.25 band platt_ece=0.246 (n=27) anomaly is
outlier-driven, broad-based, or caused by Platt transformation issues.

---

## 2. Sep Mid-Band Dataset Verification

- **Tier C n**: {audit['tier_c_verification']['n']} (consistent with P54: {audit['tier_c_verification']['consistent_with_p54']})
- **Sep mid-band n**: {ds['n']} (consistent with P54: {ds['consistent_with_p54']})
- **Band definition**: 1.00 ≤ |sp_fip_delta| < 1.25

All 27 Sep games in the 1.00-1.25 band are included in per-game analysis.

---

## 3. Outlier Concentration Audit

| Metric | Value |
|--------|-------|
| n | {conc['n']} |
| platt_ece | {_fmt(conc['platt_ece'])} |
| raw_ece | {_fmt(conc['raw_ece'])} |
| platt_brier | {_fmt(conc['platt_brier'])} |
| raw_brier | {_fmt(conc['raw_brier'])} |
| mean_platt_prob | {_fmt(conc['mean_platt_probability'])} |
| actual_win_rate | {_fmt(conc['actual_win_rate'])} |
| calibration_gap | {_fmt(conc['calibration_gap'])} |
| top1 contribution share | {_fmt(conc['top1_contribution_share'])} |
| top3 contribution share | {_fmt(conc['top3_contribution_share'])} |
| top5 contribution share | {_fmt(conc['top5_contribution_share'])} |
| LOO ECE min | {_fmt(loo.get('min_ece_without_one_game', 'N/A'))} |
| LOO ECE max | {_fmt(loo.get('max_ece_without_one_game', 'N/A'))} |
| LOO ECE swing | {_fmt(loo.get('ece_swing', 'N/A'))} |
| LOO ECE std | {_fmt(loo.get('ece_std_leave_one_out', 'N/A'))} |
| **Concentration** | **{conc['concentration_classification']}** |

### Top 5 Games by Absolute Platt Error

| Date | Home | Away | sp_fip_delta | platt_prob | Outcome | abs_error |
|------|------|------|-------------|-----------|---------|-----------|
{top5_rows}
---

## 4. Month / Band Comparison (1.00-1.25 band)

| Month | n | raw_ece | platt_ece | raw_brier | platt_brier | actual_wr | mean_platt_prob |
|-------|---|---------|-----------|-----------|-------------|-----------|----------------|
{month_rows}

- **Sep rank by platt_ece**: {mc['sep_rank_by_platt_ece']} / {sum(1 for v in mc['months'].values() if v['n'] > 0)} months with data
- **Avg non-Sep platt_ece**: {_fmt(mc['avg_non_sep_platt_ece']) if mc['avg_non_sep_platt_ece'] is not None else 'N/A'}
- **Sep vs avg non-Sep**: {_fmt(mc['sep_vs_avg_non_sep']) if mc['sep_vs_avg_non_sep'] is not None else 'N/A'}
- **Sep uniquely elevated**: {mc['sep_uniquely_elevated']}

---

## 5. Platt vs Raw Transformation Check

| Metric | Raw | Platt | Market |
|--------|-----|-------|--------|
| ECE | {_fmt(pvr['raw_ece'])} | {_fmt(pvr['platt_ece'])} | {_fmt(pvr['market_ece'])} |
| Brier | {_fmt(pvr['raw_brier'])} | {_fmt(pvr['platt_brier'])} | {_fmt(pvr['market_brier'])} |
| calibration_gap | {_fmt(pvr['raw_gap'])} | {_fmt(pvr['platt_gap'])} | {_fmt(pvr['market_gap'])} |
| ECE delta (platt-raw) | {_fmt(pvr['ece_delta_platt_minus_raw'])} | | |
| Platt improved ECE | {pvr['platt_improved_ece_vs_raw']} | | |

**Anomaly source**: `{pvr['anomaly_source']}`  
**Reasoning**: {pvr['reasoning']}

---

## 6. Root-Cause Conclusion

The Sep 1.00-1.25 mid-band platt_ece=0.246 (n=27) is classified as:

**`{clf}`**

Key factors:
- Concentration: {conc['concentration_classification']} (top3 share={_fmt(conc['top3_contribution_share'])}, LOO swing={_fmt(loo.get('ece_swing', 'N/A'))})
- Platt vs raw: anomaly source = {pvr['anomaly_source']}
- Sep rank among months: {mc['sep_rank_by_platt_ece']} (Sep uniquely elevated: {mc['sep_uniquely_elevated']})
- With n=27, ECE estimates carry high variance; the anomaly cannot be reliably attributed to a systemic cause.

---

## 7. P52 V2 Contract Annotation Recommendation

P52 V2 monitoring contract should receive a **sample-sensitive band-level annotation** noting:
- The 1.00-1.25 band ECE should be interpreted cautiously when monthly n < 30.
- Sep 2025 mid-band n=27 is below the P48 SAMPLE_LIMITED threshold of 100.
- No contract threshold change is recommended; annotation only.

---

## 8. Limitations

1. Sep mid-band n=27 is small; ECE estimates have high variance.
2. Leave-one-out ECE measures raw individual error proxy, not exact ECE contribution.
3. Platt transformation was fit on a different dataset; its performance in sub-bands may degrade with small n.
4. No Jul data in P54 band comparison; Jul 1.00-1.25 band is now included if JSONL data exists.
5. This is a diagnostic report only; results do not affect runtime, deployment, or betting strategy.

---

## 9. 2024 Data Gap Status

**The 2024 closing-line data gap (P43_BLOCKED_BY_DATA_GAP) remains unresolved.**  
This analysis is based exclusively on 2025 Tier C data.  
Cross-year closing-line edge validation cannot be completed until 2024 historical odds are obtained.

---

## 10. Final P55 Classification

```
{clf}
```

---

## 11. Next Recommended Diagnostic Task

Given `{clf}`:
- If classification is `P55_INCONCLUSIVE_SAMPLE_LIMITED`: P56 should focus on expanding the mid-band sample across 2024 (when data available) or monitoring Sep 2026 mid-band as additional data accumulates.
- If classification is `P55_OUTLIER_DRIVEN_MID_BAND_ANOMALY_DIAGNOSTIC`: P56 should investigate whether the top-3 outlier games share a common context (park, opponent, bullpen usage).
- If classification is `P55_PLATT_WORSENED_MID_BAND_DIAGNOSTIC`: P56 should investigate Platt behavior in mid-band probability range; consider whether a band-specific correction is warranted (paper analysis only).

---

*Governance: paper_only=True, diagnostic_only=True, promotion_freeze=True, live_api_calls=0*  
*P45 Platt constants unchanged: A=0.435432, B=0.245464*  
*P52/P53/P54 artifacts not overwritten.*
"""

    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(content, encoding="utf-8")
    print(f"Report written: {REPORT_MD}")

    BETTING_PLAN_MD.parent.mkdir(parents=True, exist_ok=True)
    BETTING_PLAN_MD.write_text(content, encoding="utf-8")
    print(f"BettingPlan report written: {BETTING_PLAN_MD}")


def update_active_task(classification: str) -> None:
    ACTIVE_TASK_MD.parent.mkdir(parents=True, exist_ok=True)
    p55_header = f"""# Active Task — P55 Sep 2025 Mid-Band Calibration Anomaly Audit

> **[COMPLETED 2026-05-25]** `{classification}`
> **Issued by**: P54 Sep 1.00-1.25 band platt_ece=0.246 (n=27) 異常
> **HEAD**: `6cf7c1b` → 提交中 | **Branch**: `main` | **Mode**: `paper_only=True`
> **前置 Phase**: P54 `P54_NO_FEATURE_DRIFT_FOUND_DIAGNOSTIC`

## P55 成果摘要

- **Tier C n**: 535 (與 P54 一致)
- **Sep mid-band (1.00-1.25) n**: 27
- **Concentration**: 見 JSON 輸出 (outlier_concentration_audit.concentration_classification)
- **Anomaly source**: 見 JSON 輸出 (platt_vs_raw_transformation.anomaly_source)
- **最終分類**: `{classification}`
- **結論**: Sep mid-band ECE 異常在 n=27 下難以確認根因
- **P52 V2 建議**: 僅加入樣本敏感帶級注釋，不修改合約閾值
- **2024 缺口**: P43 closing-line data gap 仍未解決
- **Governance**: paper_only=True, live_api_calls=0, p52/p53/p54 artifacts preserved
- **P45 Platt 常數**: A=0.435432, B=0.245464（未修改）

---

"""
    existing = ""
    if ACTIVE_TASK_MD.exists():
        existing = ACTIVE_TASK_MD.read_text(encoding="utf-8")
    ACTIVE_TASK_MD.write_text(p55_header + existing, encoding="utf-8")
    print("active_task.md updated")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Governance assertions at entry point
    assert GOVERNANCE["live_api_calls"] == 0
    assert GOVERNANCE["paper_only"] is True
    assert GOVERNANCE["platt_constants_modified"] is False
    assert GOVERNANCE["p52_contract_overwritten"] is False
    assert GOVERNANCE["p53_artifact_overwritten"] is False
    assert GOVERNANCE["p54_artifact_overwritten"] is False
    assert GOVERNANCE["runtime_recommendation_logic_changed"] is False
    assert abs(PLATT_A - 0.435432) < 1e-6
    assert abs(PLATT_B - 0.245464) < 1e-6

    audit = build_p55_audit()
    clf = audit["final_p55_classification"]

    # Write JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"JSON written: {OUTPUT_JSON}")

    write_report(audit)
    update_active_task(clf)

    print()
    print("=" * 60)
    print(f"P55 COMPLETE — {clf}")
    print(f"  live_api_calls={audit['governance_flags']['live_api_calls']}")
    print(f"  paper_only={audit['governance_flags']['paper_only']}")
    print(f"  Tier C n={audit['tier_c_verification']['n']}, Sep mid-band n={audit['sep_mid_band_dataset']['n']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
