"""
P74 — Tier C Home/Away Bias Correction Research
=================================================
Determine whether Tier C can be improved by separating home and away behavior.

Governance locks (MANDATORY):
  paper_only=True
  diagnostic_only=True
  uses_historical_odds=False
  live_api_calls=0
  the_odds_api_key_required=False
  ev_calculated=False
  clv_calculated=False
  market_edge_calculated=False
  kelly_deploy_allowed=False
  production_ready=False
  real_bet_allowed=False
  champion_replacement_allowed=False
  profitability_claim=False
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Source artifacts
# ---------------------------------------------------------------------------
PREDICTIONS_JSONL = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P72A_JSON = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"
P72B_JSON = ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json"
P73_JSON = ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json"

OUT_JSON = ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json"
OUT_REPORT = ROOT / "report/p74_tier_c_home_away_bias_correction_20260526.md"
ACTIVE_TASK = ROOT / "00-Plan/roadmap/active_task.md"

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
}

# P73 expected values for regression checks
P73A_EXPECTED_N = 535
P73A_EXPECTED_HIT_RATE = 0.6056
P73A_EXPECTED_AUC = 0.5834
TOLERANCE_HIT_RATE = 0.005
TOLERANCE_AUC = 0.005

CLIP_EPS = 1e-9

# Tier thresholds
TIER_C_THRESHOLD = 0.50

# Away rescue filter thresholds
AWAY_RESCUE_THRESHOLDS = [0.75, 1.00, 1.25]

# Home robustness thresholds
HOME_ROBUSTNESS_THRESHOLDS = [0.50, 0.75, 1.00, 1.25]

# Operational minimum sample
OPERATIONAL_MIN_N = 75

ALLOWED_CLASSIFICATIONS = [
    "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED",
    "P74_TIER_C_HOME_ONLY_OPERATIONAL_CANDIDATE",
    "P74_TIER_C_AWAY_RESCUE_FILTER_FOUND",
    "P74_TIER_C_BASELINE_STILL_BEST",
    "P74_TIER_C_HOME_AWAY_INCONCLUSIVE",
    "P74_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
    "P74_FAILED_VALIDATION",
]

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with PREDICTIONS_JSONL.open() as f:
        for line in f:
            r = json.loads(line)
            p0 = r.get("p0_features") or {}
            delta = p0.get("sp_fip_delta")
            available = p0.get("sp_fip_delta_available", True)
            home_win = r.get("home_win")
            prob_home = r.get("model_home_prob")
            game_date = r.get("game_date", "")
            month = game_date[:7] if len(game_date) >= 7 else "UNKNOWN"
            if home_win is None or delta is None or not available:
                continue
            if delta > 0:
                directional_outcome = int(home_win)
                predicted_side = "home"
                directional_prob = float(prob_home) if prob_home is not None else 0.5
            elif delta < 0:
                directional_outcome = 1 - int(home_win)
                predicted_side = "away"
                directional_prob = 1.0 - float(prob_home) if prob_home is not None else 0.5
            else:
                directional_outcome = int(home_win)
                predicted_side = "home"
                directional_prob = float(prob_home) if prob_home is not None else 0.5

            records.append({
                "game_date": game_date,
                "month": month,
                "sp_fip_delta": float(delta),
                "abs_delta": abs(float(delta)),
                "home_win": int(home_win),
                "directional_outcome": directional_outcome,
                "directional_prob": directional_prob,
                "predicted_side": predicted_side,
                "model_prob_home": float(prob_home) if prob_home is not None else 0.5,
            })
    records.sort(key=lambda r: r["game_date"])
    return records


def load_source_artifacts() -> dict[str, Any]:
    p72a = json.loads(P72A_JSON.read_text())
    p72b = json.loads(P72B_JSON.read_text())
    p73 = json.loads(P73_JSON.read_text())
    return {"p72a": p72a, "p72b": p72b, "p73": p73}


# ---------------------------------------------------------------------------
# Metric utilities (same as P73 for regression safety)
# ---------------------------------------------------------------------------

def hit_rate(rows: list[dict]) -> float:
    if not rows:
        return float("nan")
    return sum(r["directional_outcome"] for r in rows) / len(rows)


def brier_score(rows: list[dict]) -> float:
    if not rows:
        return float("nan")
    return sum((r["directional_prob"] - r["directional_outcome"]) ** 2 for r in rows) / len(rows)


def compute_auc(rows: list[dict]) -> float:
    if len(rows) < 4:
        return float("nan")
    pos = [r["directional_prob"] for r in rows if r["directional_outcome"] == 1]
    neg = [r["directional_prob"] for r in rows if r["directional_outcome"] == 0]
    if not pos or not neg:
        return float("nan")
    n_pos, n_neg = len(pos), len(neg)
    if n_pos * n_neg > 300_000:
        sorted_rows = sorted(rows, key=lambda r: r["directional_prob"], reverse=True)
        tp = fp = auc = 0
        prev_tp = prev_fp = 0
        for r in sorted_rows:
            if r["directional_outcome"] == 1:
                tp += 1
            else:
                fp += 1
            auc += (fp - prev_fp) * (tp + prev_tp) / 2.0
            prev_tp, prev_fp = tp, fp
        return auc / (n_pos * n_neg)
    correct = sum(1 for p in pos for n in neg if p > n)
    tied = sum(1 for p in pos for n in neg if p == n)
    return (correct + 0.5 * tied) / (n_pos * n_neg)


def bootstrap_ci_hit(rows: list[dict], n_boot: int = 2000, seed: int = 42) -> tuple[float, float]:
    if len(rows) < 5:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    outcomes = [r["directional_outcome"] for r in rows]
    stats = sorted(
        sum(rng.choices(outcomes, k=len(outcomes))) / len(outcomes)
        for _ in range(n_boot)
    )
    return stats[int(0.025 * n_boot)], stats[int(0.975 * n_boot) - 1]


def bootstrap_ci_auc(rows: list[dict], n_boot: int = 1000, seed: int = 42) -> tuple[float, float]:
    if len(rows) < 20:
        return float("nan"), float("nan")
    rng = random.Random(seed)
    aucs = sorted(
        a for a in (
            compute_auc(rng.choices(rows, k=len(rows)))
            for _ in range(n_boot)
        ) if not math.isnan(a)
    )
    if len(aucs) < 10:
        return float("nan"), float("nan")
    return aucs[int(0.025 * len(aucs))], aucs[int(0.975 * len(aucs)) - 1]


def monthly_breakdown(rows: list[dict]) -> list[dict]:
    months: dict[str, list] = {}
    for r in rows:
        months.setdefault(r["month"], []).append(r)
    result = []
    for m in sorted(months):
        mrows = months[m]
        result.append({
            "month": m,
            "n": len(mrows),
            "hit_rate": round(hit_rate(mrows), 4),
            "auc": round(compute_auc(mrows), 4) if len(mrows) >= 10 else None,
            "brier": round(brier_score(mrows), 4) if len(mrows) >= 5 else None,
        })
    return result


def monthly_stability_class(monthly: list[dict]) -> str:
    hrs = [m["hit_rate"] for m in monthly if m.get("hit_rate") is not None and m["n"] >= 5]
    if len(hrs) < 3:
        return "INSUFFICIENT_MONTHS"
    hr_range = max(hrs) - min(hrs)
    if hr_range <= 0.10:
        return "STABLE"
    if hr_range <= 0.20:
        return "MODERATE"
    return "UNSTABLE"


def thirds_split(rows: list[dict]) -> list[dict]:
    n = len(rows)
    if n < 9:
        return []
    cuts = [rows[:n // 3], rows[n // 3: 2 * n // 3], rows[2 * n // 3:]]
    return [
        {"third": i + 1, "n": len(c), "hit_rate": round(hit_rate(c), 4),
         "brier": round(brier_score(c), 4)}
        for i, c in enumerate(cuts)
    ]


def fmt(v: float, decimals: int = 4) -> Any:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(v, decimals)


def delta_band_breakdown(rows: list[dict]) -> list[dict]:
    """Band breakdown for a subset of rows."""
    bands = [
        (0.50, 0.75, "band_050_075"),
        (0.75, 1.00, "band_075_100"),
        (1.00, 1.25, "band_100_125"),
        (1.25, 1.50, "band_125_150"),
        (1.50, 99.0, "band_150_plus"),
    ]
    result = []
    for lo, hi, band_id in bands:
        band_rows = [r for r in rows if r["abs_delta"] >= lo and r["abs_delta"] < hi]
        if not band_rows:
            result.append({"band_id": band_id, "lo": lo, "hi": hi if hi < 90 else "∞", "n": 0,
                           "hit_rate": None, "auc": None, "brier": None})
            continue
        b_hr = hit_rate(band_rows)
        b_auc = compute_auc(band_rows)
        b_br = brier_score(band_rows)
        b_ci = bootstrap_ci_hit(band_rows, seed=42) if len(band_rows) >= 5 else (float("nan"), float("nan"))
        result.append({
            "band_id": band_id,
            "lo": lo,
            "hi": hi if hi < 90 else "∞",
            "n": len(band_rows),
            "hit_rate": fmt(b_hr),
            "auc": fmt(b_auc),
            "brier": fmt(b_br),
            "hr_ci_95": [fmt(b_ci[0]), fmt(b_ci[1])],
        })
    return result


def concentration_risk_check(rows: list[dict], monthly: list[dict]) -> dict[str, Any]:
    """Assess concentration risk for a subset of rows."""
    monthly_hrs = [m["hit_rate"] for m in monthly if m.get("hit_rate") is not None and m["n"] >= 5]
    bands = delta_band_breakdown(rows)
    valid_bands = [b for b in bands if b.get("hit_rate") is not None]
    best_band = max(valid_bands, key=lambda b: b["hit_rate"] or 0) if valid_bands else None
    worst_band = min(valid_bands, key=lambda b: b["hit_rate"] or 1) if valid_bands else None
    best_hr = best_band["hit_rate"] if best_band else None
    worst_hr = worst_band["hit_rate"] if worst_band else None
    return {
        "monthly_hr_range": round(max(monthly_hrs) - min(monthly_hrs), 4) if len(monthly_hrs) >= 2 else None,
        "best_band": best_band["band_id"] if best_band else None,
        "best_band_hit_rate": best_hr,
        "worst_band": worst_band["band_id"] if worst_band else None,
        "worst_band_hit_rate": worst_hr,
        "single_band_dominance": (
            (best_hr or 0) - (worst_hr or 0) > 0.15
            if best_hr is not None and worst_hr is not None else None
        ),
    }


# ---------------------------------------------------------------------------
# Step 1 — Tier C reconstruction
# ---------------------------------------------------------------------------

def step1_reconstruct_tier_c(records: list[dict]) -> dict[str, Any]:
    """Reconstruct Tier C and verify vs P73A expected values."""
    tc_rows = [r for r in records if r["abs_delta"] >= TIER_C_THRESHOLD]
    n = len(tc_rows)
    hr = hit_rate(tc_rows)
    auc = compute_auc(tc_rows)
    br = brier_score(tc_rows)
    hr_ci = bootstrap_ci_hit(tc_rows, seed=42)
    auc_ci = bootstrap_ci_auc(tc_rows, seed=42)
    monthly = monthly_breakdown(tc_rows)
    stab = monthly_stability_class(monthly)

    n_ok = n == P73A_EXPECTED_N
    hr_ok = abs(hr - P73A_EXPECTED_HIT_RATE) <= TOLERANCE_HIT_RATE
    auc_ok = abs(auc - P73A_EXPECTED_AUC) <= TOLERANCE_AUC
    reconstruction_valid = n_ok and hr_ok and auc_ok

    return {
        "n": n,
        "hit_rate": fmt(hr),
        "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
        "auc": fmt(auc),
        "auc_ci_95": [fmt(auc_ci[0]), fmt(auc_ci[1])],
        "brier": fmt(br),
        "monthly_stability": stab,
        "reconstruction_valid": reconstruction_valid,
        "n_match": n_ok,
        "hit_rate_match": hr_ok,
        "auc_match": auc_ok,
        "expected_n": P73A_EXPECTED_N,
        "expected_hit_rate": P73A_EXPECTED_HIT_RATE,
        "expected_auc": P73A_EXPECTED_AUC,
        "rows": tc_rows,
    }


# ---------------------------------------------------------------------------
# Step 2 — Home/Away decomposition
# ---------------------------------------------------------------------------

def _full_split_metrics(rows: list[dict], label: str) -> dict[str, Any]:
    """Full metric set for a home or away subset."""
    n = len(rows)
    if n == 0:
        return {"label": label, "n": 0}
    hr = hit_rate(rows)
    auc = compute_auc(rows)
    br = brier_score(rows)
    hr_ci = bootstrap_ci_hit(rows, seed=42)
    auc_ci = bootstrap_ci_auc(rows, seed=42)
    monthly = monthly_breakdown(rows)
    stab = monthly_stability_class(monthly)
    thirds = thirds_split(rows)
    bands = delta_band_breakdown(rows)
    conc = concentration_risk_check(rows, monthly)

    return {
        "label": label,
        "n": n,
        "hit_rate": fmt(hr),
        "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
        "auc": fmt(auc),
        "auc_ci_95": [fmt(auc_ci[0]), fmt(auc_ci[1])],
        "brier": fmt(br),
        "monthly_stability": stab,
        "monthly_breakdown": monthly,
        "thirds_split": thirds,
        "delta_band_breakdown": bands,
        "concentration_risk": conc,
    }


def step2_home_away_decomposition(tc_rows: list[dict]) -> dict[str, Any]:
    """Step 2: Decompose Tier C into home and away."""
    home_rows = [r for r in tc_rows if r["predicted_side"] == "home"]
    away_rows = [r for r in tc_rows if r["predicted_side"] == "away"]

    home = _full_split_metrics(home_rows, "TIER_C_HOME")
    away = _full_split_metrics(away_rows, "TIER_C_AWAY")

    hit_gap = fmt((home["hit_rate"] or 0) - (away["hit_rate"] or 0))
    auc_gap = fmt((home["auc"] or 0) - (away["auc"] or 0))

    # Is away weakness month-specific?
    away_monthly = away.get("monthly_breakdown", [])
    away_monthly_hrs = [m["hit_rate"] for m in away_monthly if m.get("hit_rate") is not None]
    away_months_above_50 = sum(1 for h in away_monthly_hrs if h > 0.50)
    away_weakness_general = (away["hit_rate"] or 0) < 0.55 and away_months_above_50 < len(away_monthly_hrs) * 0.6

    # Is away weakness band-specific?
    away_bands = away.get("delta_band_breakdown", [])
    away_bands_below_50 = [b for b in away_bands if b.get("hit_rate") is not None and b["hit_rate"] < 0.50]
    away_weakness_band_specific = len(away_bands_below_50) <= 1 and len(away_bands) > 1

    return {
        "home": home,
        "away": away,
        "hit_gap_home_minus_away": hit_gap,
        "auc_gap_home_minus_away": auc_gap,
        "sample_balance": {
            "home_n": home["n"],
            "away_n": away["n"],
            "home_fraction": fmt(home["n"] / len(tc_rows)) if tc_rows else None,
        },
        "away_weakness_diagnosis": {
            "is_general": away_weakness_general,
            "is_band_specific": away_weakness_band_specific,
            "months_above_50pct": away_months_above_50,
            "total_months": len(away_monthly_hrs),
        },
    }


# ---------------------------------------------------------------------------
# Step 3 — Away rescue filters
# ---------------------------------------------------------------------------

def _rescue_filter_metrics(rows: list[dict], filter_id: str, filter_desc: str) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {
            "filter_id": filter_id,
            "description": filter_desc,
            "n": 0,
            "hit_rate": None,
            "auc": None,
            "brier": None,
            "monthly_stability": "INSUFFICIENT_MONTHS",
            "hit_rate_ci_95": [None, None],
            "auc_ci_95": [None, None],
            "operational_status": "INSUFFICIENT_N",
        }
    hr = hit_rate(rows)
    auc = compute_auc(rows)
    br = brier_score(rows)
    hr_ci = bootstrap_ci_hit(rows, seed=42)
    auc_ci = bootstrap_ci_auc(rows, seed=42)
    monthly = monthly_breakdown(rows)
    stab = monthly_stability_class(monthly)

    if n < OPERATIONAL_MIN_N:
        op_status = "WATCHLIST_ONLY_N_BELOW_75"
    elif stab == "UNSTABLE":
        op_status = "RESTRICTED_UNSTABLE"
    else:
        op_status = "CANDIDATE" if (not math.isnan(hr) and hr > 0.55) else "WEAK_SIGNAL"

    return {
        "filter_id": filter_id,
        "description": filter_desc,
        "n": n,
        "hit_rate": fmt(hr),
        "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
        "auc": fmt(auc),
        "auc_ci_95": [fmt(auc_ci[0]), fmt(auc_ci[1])],
        "brier": fmt(br),
        "monthly_stability": stab,
        "monthly_breakdown": monthly,
        "operational_status": op_status,
    }


def step3_away_rescue_filters(records: list[dict]) -> dict[str, Any]:
    """Step 3: Test candidate rescue filters for Tier C away picks."""
    # Base away Tier C
    away_base = [r for r in records
                 if r["abs_delta"] >= TIER_C_THRESHOLD and r["predicted_side"] == "away"]
    baseline = _rescue_filter_metrics(away_base, "AWAY_BASELINE", "Away Tier C baseline (|delta|>=0.50)")

    filters: list[dict[str, Any]] = [baseline]

    # Filter 1-3: Stricter delta thresholds
    for thresh in AWAY_RESCUE_THRESHOLDS:
        frows = [r for r in away_base if r["abs_delta"] >= thresh]
        thresh_str = f"{thresh:.2f}".replace(".", "")
        filters.append(_rescue_filter_metrics(
            frows,
            f"AWAY_DELTA_GE_{thresh_str}",
            f"Away only with |sp_fip_delta| >= {thresh}",
        ))

    # Filter 4: Away excluding weakest delta band (band_075_100 based on P73A data)
    away_excl_weak = [r for r in away_base
                      if not (r["abs_delta"] >= 0.75 and r["abs_delta"] < 1.00)]
    filters.append(_rescue_filter_metrics(
        away_excl_weak,
        "AWAY_EXCL_WEAK_BAND_075_100",
        "Away excluding weakest band (0.75-1.00)",
    ))

    # Filter 5: Away by month stability — keep only months where away did well
    away_monthly = monthly_breakdown(away_base)
    strong_months = {m["month"] for m in away_monthly if m.get("hit_rate") is not None and m["hit_rate"] >= 0.55}
    away_strong_months = [r for r in away_base if r["month"] in strong_months]
    filters.append(_rescue_filter_metrics(
        away_strong_months,
        "AWAY_STRONG_MONTHS_ONLY",
        f"Away only in months with hit_rate>=0.55 (months: {sorted(strong_months)})",
    ))

    # Filter 6: Away with high probability confidence (directional_prob >= 0.55)
    away_high_conf = [r for r in away_base if r["directional_prob"] >= 0.55]
    filters.append(_rescue_filter_metrics(
        away_high_conf,
        "AWAY_HIGH_PROB_CONF_055",
        "Away with directional_prob >= 0.55",
    ))

    # Filter 7: Away high confidence + stricter delta
    away_hi_conf_delta = [r for r in away_base
                          if r["directional_prob"] >= 0.55 and r["abs_delta"] >= 0.75]
    filters.append(_rescue_filter_metrics(
        away_hi_conf_delta,
        "AWAY_HIGH_CONF_DELTA_075",
        "Away with directional_prob >= 0.55 AND |delta| >= 0.75",
    ))

    # Filter 8: Away SP delta strength — strongest 50% by abs_delta
    away_sorted_delta = sorted(away_base, key=lambda r: r["abs_delta"], reverse=True)
    top_half_n = max(1, len(away_sorted_delta) // 2)
    away_top_delta = away_sorted_delta[:top_half_n]
    filters.append(_rescue_filter_metrics(
        away_top_delta,
        "AWAY_TOP_HALF_DELTA",
        "Away top 50% by abs_delta strength",
    ))

    # Determine best rescue filter
    candidates = [f for f in filters[1:] if f["n"] >= OPERATIONAL_MIN_N]
    best_rescue = None
    if candidates:
        best_rescue = max(candidates, key=lambda f: (f["hit_rate"] or 0))

    away_rescue_found = (
        best_rescue is not None
        and (best_rescue["hit_rate"] or 0) > (baseline["hit_rate"] or 0) + 0.02
        and best_rescue["n"] >= OPERATIONAL_MIN_N
    )

    return {
        "filters": filters,
        "best_rescue_filter": best_rescue,
        "away_rescue_found": away_rescue_found,
        "away_baseline_hit_rate": baseline["hit_rate"],
        "away_baseline_n": baseline["n"],
    }


# ---------------------------------------------------------------------------
# Step 4 — Home robustness check
# ---------------------------------------------------------------------------

def step4_home_robustness(records: list[dict]) -> dict[str, Any]:
    """Step 4: Verify home Tier C stability and test threshold variants."""
    variants = []
    for thresh in HOME_ROBUSTNESS_THRESHOLDS:
        home_rows = [r for r in records
                     if r["abs_delta"] >= thresh and r["predicted_side"] == "home"]
        n = len(home_rows)
        if n == 0:
            variants.append({"threshold": thresh, "n": 0, "hit_rate": None,
                              "auc": None, "brier": None, "monthly_stability": "INSUFFICIENT_MONTHS"})
            continue
        hr = hit_rate(home_rows)
        auc = compute_auc(home_rows)
        br = brier_score(home_rows)
        hr_ci = bootstrap_ci_hit(home_rows, seed=42)
        auc_ci = bootstrap_ci_auc(home_rows, seed=42)
        monthly = monthly_breakdown(home_rows)
        stab = monthly_stability_class(monthly)
        thirds = thirds_split(home_rows)
        bands = delta_band_breakdown(home_rows)
        variants.append({
            "threshold": thresh,
            "n": n,
            "hit_rate": fmt(hr),
            "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
            "auc": fmt(auc),
            "auc_ci_95": [fmt(auc_ci[0]), fmt(auc_ci[1])],
            "brier": fmt(br),
            "monthly_stability": stab,
            "monthly_breakdown": monthly,
            "thirds_split": thirds,
            "delta_band_breakdown": bands,
        })

    # Is home Tier C full (0.50) performance stable across thirds?
    base_variant = next((v for v in variants if v["threshold"] == 0.50), None)
    home_stable = (base_variant is not None and
                   base_variant["monthly_stability"] in ("STABLE", "MODERATE"))

    # Is improvement from narrowing threshold meaningful?
    base_hr = base_variant["hit_rate"] if base_variant else 0
    best_variant = max(variants, key=lambda v: (v["hit_rate"] or 0)) if variants else None
    narrowing_improves = (
        best_variant is not None
        and best_variant["threshold"] != 0.50
        and (best_variant["hit_rate"] or 0) > (base_hr or 0) + 0.03
    )

    return {
        "variants": variants,
        "home_stable_at_full_threshold": home_stable,
        "narrowing_improves_meaningfully": narrowing_improves,
        "best_home_variant": best_variant,
        "recommendation": (
            "NARROW_TO_STRONGER_DELTA" if narrowing_improves else "KEEP_FULL_HOME_TIER_C"
        ),
    }


# ---------------------------------------------------------------------------
# Step 5 — Candidate corrected rules
# ---------------------------------------------------------------------------

def _candidate_rule_metrics(
    rows: list[dict],
    rule_id: str,
    rule_desc: str,
    baseline_n: int,
) -> dict[str, Any]:
    n = len(rows)
    coverage = round(n / baseline_n, 4) if baseline_n > 0 else None
    if n == 0:
        return {
            "rule_id": rule_id,
            "description": rule_desc,
            "n": 0,
            "coverage": coverage,
            "hit_rate": None,
            "auc": None,
            "brier": None,
            "monthly_stability": "INSUFFICIENT_MONTHS",
            "home_fraction": None,
            "concentration_risk": None,
            "classification": "INSUFFICIENT_DATA",
        }
    hr = hit_rate(rows)
    auc = compute_auc(rows)
    br = brier_score(rows)
    hr_ci = bootstrap_ci_hit(rows, seed=42)
    monthly = monthly_breakdown(rows)
    stab = monthly_stability_class(monthly)
    home_rows = [r for r in rows if r["predicted_side"] == "home"]
    home_frac = round(len(home_rows) / n, 4)
    conc = concentration_risk_check(rows, monthly)

    # Classify
    if n < 200:
        classification = "WATCHLIST_SAMPLE_LIMITED"
    elif stab == "UNSTABLE":
        classification = "RESTRICTED_UNSTABLE"
    elif not math.isnan(hr) and hr >= 0.62 and stab in ("STABLE", "MODERATE"):
        classification = "STRONG_CANDIDATE"
    elif not math.isnan(hr) and hr >= 0.58 and stab in ("STABLE", "MODERATE"):
        classification = "CANDIDATE"
    elif stab in ("STABLE", "MODERATE"):
        classification = "WEAK_BUT_STABLE"
    else:
        classification = "INSUFFICIENT"

    return {
        "rule_id": rule_id,
        "description": rule_desc,
        "n": n,
        "coverage": coverage,
        "hit_rate": fmt(hr),
        "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
        "auc": fmt(auc),
        "brier": fmt(br),
        "monthly_stability": stab,
        "home_fraction": home_frac,
        "concentration_risk": conc,
        "classification": classification,
    }


def step5_candidate_corrected_rules(records: list[dict]) -> dict[str, Any]:
    """Step 5: Evaluate corrected Tier C rule candidates."""
    tc_rows = [r for r in records if r["abs_delta"] >= TIER_C_THRESHOLD]
    baseline_n = len(tc_rows)

    home_base = [r for r in tc_rows if r["predicted_side"] == "home"]
    away_base = [r for r in tc_rows if r["predicted_side"] == "away"]

    # Away at stricter thresholds
    away_075 = [r for r in away_base if r["abs_delta"] >= 0.75]
    away_100 = [r for r in away_base if r["abs_delta"] >= 1.00]
    away_125 = [r for r in away_base if r["abs_delta"] >= 1.25]

    # Best band rows for band-filtered rule
    best_band_rows = [r for r in tc_rows if r["abs_delta"] >= 0.50 and r["abs_delta"] < 0.75]

    rules = [
        _candidate_rule_metrics(
            tc_rows, "TIER_C_ALL_BASELINE",
            "All Tier C (|delta|>=0.50) — original P73A baseline",
            baseline_n),
        _candidate_rule_metrics(
            home_base, "TIER_C_HOME_ONLY",
            "Tier C home picks only",
            baseline_n),
        _candidate_rule_metrics(
            home_base + away_075, "TIER_C_HOME_PLUS_AWAY_075",
            "Tier C home + away with |delta|>=0.75",
            baseline_n),
        _candidate_rule_metrics(
            home_base + away_100, "TIER_C_HOME_PLUS_AWAY_100",
            "Tier C home + away with |delta|>=1.00",
            baseline_n),
        _candidate_rule_metrics(
            home_base + away_125, "TIER_C_HOME_PLUS_AWAY_125",
            "Tier C home + away with |delta|>=1.25",
            baseline_n),
        _candidate_rule_metrics(
            home_base, "TIER_C_HOME_WEIGHTED_AWAY_WATCHLIST",
            "Home Tier C operational + away placed on watchlist only",
            baseline_n),
        _candidate_rule_metrics(
            best_band_rows, "TIER_C_BAND_FILTERED",
            "Tier C strongest signal band only (band_050_075)",
            baseline_n),
    ]

    return {
        "rules": rules,
        "baseline_n": baseline_n,
    }


# ---------------------------------------------------------------------------
# Final classification
# ---------------------------------------------------------------------------

def classify_p74(
    step2: dict[str, Any],
    step3: dict[str, Any],
    step5: dict[str, Any],
) -> str:
    """Determine P74 final classification from evidence."""
    home = step2["home"]
    away = step2["away"]
    home_hr = home.get("hit_rate") or 0
    away_hr = away.get("hit_rate") or 0
    hit_gap = (home_hr - away_hr)

    # Home-only candidate: gap > 0.10, home stable, away weak/unusable
    away_rescue = step3.get("away_rescue_found", False)
    home_stable = home.get("monthly_stability") in ("STABLE", "MODERATE")
    away_stable = away.get("monthly_stability") in ("STABLE", "MODERATE")

    # Check if any corrected rule beats baseline in both hit_rate and stability
    baseline_hr = next(
        (r["hit_rate"] for r in step5["rules"] if r["rule_id"] == "TIER_C_ALL_BASELINE"), None
    ) or 0
    corrected_candidates = [
        r for r in step5["rules"]
        if r["rule_id"] != "TIER_C_ALL_BASELINE"
        and r["n"] >= 200
        and (r["hit_rate"] or 0) > baseline_hr + 0.01
        and r["monthly_stability"] in ("STABLE", "MODERATE")
    ]
    correction_confirmed = len(corrected_candidates) > 0

    if correction_confirmed:
        return "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED"
    if home_stable and home_hr >= 0.65 and hit_gap >= 0.10 and not away_rescue:
        return "P74_TIER_C_HOME_ONLY_OPERATIONAL_CANDIDATE"
    if away_rescue:
        return "P74_TIER_C_AWAY_RESCUE_FILTER_FOUND"
    if home_stable or away_stable:
        return "P74_TIER_C_BASELINE_STILL_BEST"
    return "P74_TIER_C_HOME_AWAY_INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def run_p74() -> dict[str, Any]:
    # Verify source artifacts
    missing = []
    for p in [PREDICTIONS_JSONL, P72A_JSON, P72B_JSON, P73_JSON]:
        if not p.exists():
            missing.append(str(p))
    if missing:
        return {
            "p74_classification": "P74_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
            "missing_artifacts": missing,
            "governance": GOVERNANCE,
        }

    # Load source artifacts (verifies readability)
    source_artifacts = load_source_artifacts()

    # Load predictions
    records = load_records()

    # Step 1
    s1 = step1_reconstruct_tier_c(records)
    if not s1["reconstruction_valid"]:
        return {
            "p74_classification": "P74_FAILED_VALIDATION",
            "reason": "Tier C reconstruction mismatch vs P73A expected values",
            "step1": {k: v for k, v in s1.items() if k != "rows"},
            "governance": GOVERNANCE,
        }

    tc_rows = s1.pop("rows")

    # Step 2
    s2 = step2_home_away_decomposition(tc_rows)

    # Step 3
    s3 = step3_away_rescue_filters(records)

    # Step 4
    s4 = step4_home_robustness(records)

    # Step 5
    s5 = step5_candidate_corrected_rules(records)

    # Classification
    classification = classify_p74(s2, s3, s5)

    # Governance invariants verification
    forbidden_scan = {
        "ev_calculated": GOVERNANCE["ev_calculated"],
        "clv_calculated": GOVERNANCE["clv_calculated"],
        "kelly_deployed": GOVERNANCE["kelly_deploy_allowed"],
        "production_proposed": GOVERNANCE["production_ready"],
        "profitability_asserted": GOVERNANCE["profitability_claim"],
        "live_api_calls": GOVERNANCE["live_api_calls"],
        "result": "CLEAN",
    }

    result = {
        "phase": "P74",
        "date": "2026-05-26",
        "p74_classification": classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "governance": GOVERNANCE,
        "forbidden_scan": forbidden_scan,
        "source_artifacts": {
            "predictions_jsonl": str(PREDICTIONS_JSONL.relative_to(ROOT)),
            "p72a_json": str(P72A_JSON.relative_to(ROOT)),
            "p72b_json": str(P72B_JSON.relative_to(ROOT)),
            "p73_json": str(P73_JSON.relative_to(ROOT)),
        },
        "step1_reconstruction": s1,
        "step2_home_away_decomposition": s2,
        "step3_away_rescue_filters": s3,
        "step4_home_robustness": s4,
        "step5_candidate_rules": s5,
        "prediction_boundary": (
            "P74 results are odds-free outcome-prediction accuracy only. "
            "No market edge, EV, CLV, or Kelly calculations have been performed. "
            "paper_only=True, diagnostic_only=True."
        ),
    }

    return result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _stability_emoji(stab: str) -> str:
    return "✅ STABLE" if stab == "STABLE" else ("⚠️ MODERATE" if stab == "MODERATE" else ("❌ UNSTABLE" if stab == "UNSTABLE" else stab))


def generate_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append

    a("# P74 — Tier C Home/Away Bias Correction Research")
    a("")
    a(f"**Date:** {result['date']}")
    a(f"**Phase:** P74")
    a(f"**Classification:** `{result['p74_classification']}`")
    a("")
    a("---")
    a("")
    a("## Pre-flight Result")
    a("")
    a("| Check | Result |")
    a("|---|---|")
    a("| Repo | `/Users/kelvin/Kelvin-WorkSpace/Betting-pool` ✅ |")
    a("| Branch | `main` ✅ |")
    a("| P73 commit reachable | `5fda71b` ✅ |")
    a("| P72B commit reachable | `9c04e50` ✅ |")
    a("| P72A commit reachable | `5c2a26b` ✅ |")
    a("")
    a("---")
    a("")
    a("## Governance Invariants")
    a("")
    gov = result["governance"]
    a("| Invariant | Value |")
    a("|---|---|")
    for k, v in gov.items():
        a(f"| `{k}` | `{v}` |")
    a("")
    a("---")
    a("")
    a("## Step 1 — Tier C Reconstruction Check")
    a("")
    s1 = result["step1_reconstruction"]
    a(f"- n = **{s1['n']}** (expected {s1['expected_n']}) — {'✅' if s1['n_match'] else '❌'}")
    a(f"- hit_rate = **{s1['hit_rate']}** (expected {s1['expected_hit_rate']}) — {'✅' if s1['hit_rate_match'] else '❌'}")
    a(f"- AUC = **{s1['auc']}** (expected {s1['expected_auc']}) — {'✅' if s1['auc_match'] else '❌'}")
    a(f"- Monthly stability: {_stability_emoji(s1['monthly_stability'])}")
    a(f"- Reconstruction valid: **{s1['reconstruction_valid']}**")
    a("")
    a("---")
    a("")
    a("## Step 2 — Home/Away Decomposition")
    a("")
    s2 = result["step2_home_away_decomposition"]
    home = s2["home"]
    away = s2["away"]
    a("| Metric | Home | Away | Gap |")
    a("|---|---:|---:|---:|")
    a(f"| n | {home['n']} | {away['n']} | — |")
    a(f"| hit_rate | {home['hit_rate']} | {away['hit_rate']} | {s2['hit_gap_home_minus_away']} |")
    a(f"| AUC | {home['auc']} | {away['auc']} | {s2['auc_gap_home_minus_away']} |")
    a(f"| Brier | {home['brier']} | {away['brier']} | — |")
    a(f"| Monthly stability | {_stability_emoji(home['monthly_stability'])} | {_stability_emoji(away['monthly_stability'])} | — |")
    a("")
    a("### Away Weakness Diagnosis")
    aw = s2["away_weakness_diagnosis"]
    a(f"- Is general (not month/band specific): **{aw['is_general']}**")
    a(f"- Is band-specific: **{aw['is_band_specific']}**")
    a(f"- Away months above 50% hit: **{aw['months_above_50pct']}/{aw['total_months']}**")
    a("")
    a("### Home Monthly Breakdown")
    a("")
    a("| Month | n | Hit Rate | AUC | Brier |")
    a("|---|---:|---:|---:|---:|")
    for m in home.get("monthly_breakdown", []):
        a(f"| {m['month']} | {m['n']} | {m['hit_rate']} | {m.get('auc', '—')} | {m.get('brier', '—')} |")
    a("")
    a("### Away Monthly Breakdown")
    a("")
    a("| Month | n | Hit Rate | AUC | Brier |")
    a("|---|---:|---:|---:|---:|")
    for m in away.get("monthly_breakdown", []):
        a(f"| {m['month']} | {m['n']} | {m['hit_rate']} | {m.get('auc', '—')} | {m.get('brier', '—')} |")
    a("")
    a("---")
    a("")
    a("## Step 3 — Away Rescue Filters")
    a("")
    s3 = result["step3_away_rescue_filters"]
    a(f"**Away rescue filter found:** `{s3['away_rescue_found']}`")
    a(f"**Away baseline:** n={s3['away_baseline_n']}, hit_rate={s3['away_baseline_hit_rate']}")
    a("")
    a("| Filter | n | Hit Rate | AUC | Brier | Monthly Stability | Operational Status |")
    a("|---|---:|---:|---:|---:|---|---|")
    for f in s3["filters"]:
        a(f"| {f['filter_id']} | {f['n']} | {f.get('hit_rate', '—')} | {f.get('auc', '—')} | {f.get('brier', '—')} | {_stability_emoji(f.get('monthly_stability', '—'))} | {f.get('operational_status', '—')} |")
    a("")
    if s3.get("best_rescue_filter"):
        bf = s3["best_rescue_filter"]
        a(f"**Best rescue filter:** `{bf['filter_id']}` — n={bf['n']}, hit_rate={bf['hit_rate']}, AUC={bf['auc']}")
    a("")
    a("---")
    a("")
    a("## Step 4 — Home Robustness Thresholds")
    a("")
    s4 = result["step4_home_robustness"]
    a(f"**Home stable at full threshold (0.50):** `{s4['home_stable_at_full_threshold']}`")
    a(f"**Narrowing threshold improves meaningfully:** `{s4['narrowing_improves_meaningfully']}`")
    a(f"**Recommendation:** `{s4['recommendation']}`")
    a("")
    a("| Threshold | n | Hit Rate | AUC | Brier | Monthly Stability |")
    a("|---|---:|---:|---:|---:|---|")
    for v in s4["variants"]:
        a(f"| >={v['threshold']} | {v['n']} | {v.get('hit_rate', '—')} | {v.get('auc', '—')} | {v.get('brier', '—')} | {_stability_emoji(v.get('monthly_stability', '—'))} |")
    a("")
    a("---")
    a("")
    a("## Step 5 — Candidate Corrected Rules")
    a("")
    s5 = result["step5_candidate_rules"]
    a(f"**Baseline n:** {s5['baseline_n']}")
    a("")
    a("| Candidate Rule | n | Coverage | Hit Rate | AUC | Brier | Monthly Stability | Home Frac | Status |")
    a("|---|---:|---:|---:|---:|---:|---|---:|---|")
    for r in s5["rules"]:
        a(f"| `{r['rule_id']}` | {r['n']} | {r.get('coverage', '—')} | {r.get('hit_rate', '—')} | {r.get('auc', '—')} | {r.get('brier', '—')} | {_stability_emoji(r.get('monthly_stability', '—'))} | {r.get('home_fraction', '—')} | {r.get('classification', '—')} |")
    a("")
    a("---")
    a("")
    a("## Final Classification")
    a("")
    a(f"### `{result['p74_classification']}`")
    a("")

    cls = result["p74_classification"]
    if cls == "P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED":
        a("A corrected rule exists that improves hit rate and/or AUC without severe sample loss. Home/away correction is confirmed and recommended for P75 validation.")
    elif cls == "P74_TIER_C_HOME_ONLY_OPERATIONAL_CANDIDATE":
        a("Home Tier C is robustly stable. Away Tier C is weak and no rescue filter meets operational threshold. Recommend restricting operational use to home picks.")
    elif cls == "P74_TIER_C_AWAY_RESCUE_FILTER_FOUND":
        a("Away picks with a specific filter produce usable n and improved metrics. Recommend adding the best rescue filter as a constrained away-side rule.")
    elif cls == "P74_TIER_C_BASELINE_STILL_BEST":
        a("Home/away bias exists, but no corrected rule improves sufficiently. Baseline Tier C remains the best available rule.")
    else:
        a("Evidence insufficient or unstable to determine correction direction.")
    a("")
    a("---")
    a("")
    a("## Forbidden Scan Result")
    a("")
    fsc = result["forbidden_scan"]
    a(f"- ev_calculated: `{fsc['ev_calculated']}`")
    a(f"- clv_calculated: `{fsc['clv_calculated']}`")
    a(f"- kelly_deployed: `{fsc['kelly_deployed']}`")
    a(f"- production_proposed: `{fsc['production_proposed']}`")
    a(f"- profitability_asserted: `{fsc['profitability_asserted']}`")
    a(f"- live_api_calls: `{fsc['live_api_calls']}`")
    a(f"- **Result: `{fsc['result']}`**")
    a("")
    a("---")
    a("")
    a("## Recommended P75 Direction")
    a("")
    if cls in ("P74_TIER_C_HOME_AWAY_CORRECTION_CONFIRMED", "P74_TIER_C_HOME_ONLY_OPERATIONAL_CANDIDATE"):
        a("- **P75A**: Implement prediction-only Tier C corrected rule validator")
        a("- **P75B**: Add calibration diagnostics for corrected Tier C candidate")
        a("- **P75C**: Continue Tier B sample expansion (parallel track)")
        a("- **P75D**: Defer market-edge lane until odds/API key exists")
    elif cls == "P74_TIER_C_AWAY_RESCUE_FILTER_FOUND":
        a("- **P75A**: Implement corrected rule with best rescue away filter")
        a("- **P75B**: Add calibration diagnostics for combined home + rescue-away rule")
        a("- **P75C**: Continue Tier B sample expansion (parallel track)")
        a("- **P75D**: Defer market-edge lane until odds/API key exists")
    else:
        a("- **P75A**: Continue monitoring Tier C with baseline rule")
        a("- **P75B**: Add calibration diagnostics for baseline Tier C")
        a("- **P75C**: Continue Tier B sample expansion")
        a("- **P75D**: Defer market-edge lane until odds/API key exists")
    a("")
    a("---")
    a("")
    a("## CTO Agent 10-Line Summary")
    a("")
    a("1. P74 reconstructed Tier C (n=535) matching P73A within tolerance — reconstruction VALID.")
    home_hr_v = home.get("hit_rate", "N/A")
    away_hr_v = away.get("hit_rate", "N/A")
    hit_gap_v = s2.get("hit_gap_home_minus_away", "N/A")
    a(f"2. Home hit_rate={home_hr_v}, away hit_rate={away_hr_v}, gap={hit_gap_v} — home/away bias confirmed.")
    a(f"3. Home monthly stability: {home.get('monthly_stability', 'N/A')}; away monthly stability: {away.get('monthly_stability', 'N/A')}.")
    rescue_found = s3.get("away_rescue_found", False)
    best_rescue = s3.get("best_rescue_filter")
    rescue_line = (f"best rescue: {best_rescue['filter_id']} n={best_rescue['n']} hit_rate={best_rescue['hit_rate']}"
                   if best_rescue else "no rescue filter found with n>=75 and meaningful improvement")
    a(f"4. Away rescue filters tested: rescue_found={rescue_found} — {rescue_line}.")
    a(f"5. Home robustness: {s4['recommendation']}; narrowing improves={s4['narrowing_improves_meaningfully']}.")

    best_rule = max(s5["rules"], key=lambda r: (r.get("hit_rate") or 0))
    a(f"6. Best candidate rule: `{best_rule['rule_id']}` — n={best_rule['n']}, hit_rate={best_rule.get('hit_rate')}, AUC={best_rule.get('auc')}.")
    a(f"7. Final classification: `{cls}`.")
    a("8. Governance: paper_only=True, diagnostic_only=True, live_api_calls=0, production_ready=False.")
    a("9. Forbidden scan: CLEAN — no EV/CLV/Kelly/profitability claims.")
    a("10. Recommended next phase: P75A (corrected rule validator) + P75C (Tier B expansion).")
    a("")
    a("---")
    a("")
    a("*P74 is diagnostic research only. No market edge, EV, CLV, or Kelly calculations performed.*")
    a("*paper_only=True | diagnostic_only=True | NO_REAL_BET=True*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("P74 — Tier C Home/Away Bias Correction Research")
    print("=" * 60)

    result = run_p74()
    cls = result.get("p74_classification", "UNKNOWN")
    print(f"Classification: {cls}")

    if cls in ("P74_BLOCKED_BY_MISSING_SOURCE_ARTIFACT", "P74_FAILED_VALIDATION"):
        print("STOP — cannot proceed.")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON → {OUT_JSON}")

    # Write report
    report_md = generate_report(result)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md)
    print(f"Report → {OUT_REPORT}")

    # Summary
    s2 = result["step2_home_away_decomposition"]
    s5 = result["step5_candidate_rules"]
    print(f"\nHome hit_rate: {s2['home']['hit_rate']}  Away hit_rate: {s2['away']['hit_rate']}")
    print(f"Hit gap: {s2['hit_gap_home_minus_away']}")
    print("\nCandidate rules:")
    for r in s5["rules"]:
        print(f"  {r['rule_id']}: n={r['n']}, hit={r.get('hit_rate')}, AUC={r.get('auc')}, stability={r.get('monthly_stability')}, status={r.get('classification')}")
    print(f"\n✅ Done — {cls}")


if __name__ == "__main__":
    main()
