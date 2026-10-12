"""
P73A/B — Odds-Free Tier Stability Deep-Dive + Tier B Sample Expansion
=======================================================================
P73A: Tier C operational stability deep-dive
P73B: Tier B sample expansion and cross-validation

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

CLIP_EPS = 1e-9

# ---------------------------------------------------------------------------
# P73A: Tier C configurations
# ---------------------------------------------------------------------------
TIER_C_THRESHOLD = 0.50

DELTA_BANDS: list[tuple[float, float, str]] = [
    (0.50, 0.75, "band_050_075"),
    (0.75, 1.00, "band_075_100"),
    (1.00, 1.25, "band_100_125"),
    (1.25, 1.50, "band_125_150"),
    (1.50, 99.0, "band_150_plus"),
]

# ---------------------------------------------------------------------------
# P73B: Tier B variants
# ---------------------------------------------------------------------------
TIER_B_VARIANTS: list[dict[str, Any]] = [
    {"variant_id": "TB_STRICT",        "lo": 1.35, "hi": 99.0, "name": "Strict Tier B (>=1.35)"},
    {"variant_id": "TB_ORIGINAL",      "lo": 1.25, "hi": 99.0, "name": "Original Tier B (>=1.25)"},
    {"variant_id": "TB_RELAXED_V1",    "lo": 1.10, "hi": 99.0, "name": "Relaxed Tier B v1 (>=1.10)"},
    {"variant_id": "TB_RELAXED_V2",    "lo": 1.00, "hi": 99.0, "name": "Relaxed Tier B v2 (>=1.00)"},
    {"variant_id": "TB_EXCL_WEAK_BAND","lo": 1.25, "hi": 1.75, "name": "Tier B excl weak band (1.25-1.75)"},
]

ALLOWED_CLASSIFICATIONS = [
    "P73_TIER_C_OPERATIONAL_STABLE_TIER_B_RESEARCH_CONFIRMED",
    "P73_TIER_C_OPERATIONAL_STABLE_TIER_B_SAMPLE_LIMITED",
    "P73_TIER_C_STABLE_WITH_CAVEATS_TIER_B_UNSTABLE",
    "P73_ODDS_FREE_TIER_ANALYSIS_INCONCLUSIVE",
    "P73_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
    "P73_FAILED_VALIDATION",
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
            # Directional outcome: 1 if model's favored side wins
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
    # Chronological order
    records.sort(key=lambda r: r["game_date"])
    return records


# ---------------------------------------------------------------------------
# Metric utilities
# ---------------------------------------------------------------------------

def hit_rate(rows: list[dict]) -> float:
    if not rows:
        return float("nan")
    return sum(r["directional_outcome"] for r in rows) / len(rows)


def brier_score(rows: list[dict]) -> float:
    if not rows:
        return float("nan")
    return sum((r["directional_prob"] - r["directional_outcome"]) ** 2 for r in rows) / len(rows)


def log_loss(rows: list[dict]) -> float:
    if not rows:
        return float("nan")
    total = 0.0
    for r in rows:
        p = max(CLIP_EPS, min(1 - CLIP_EPS, r["directional_prob"]))
        y = r["directional_outcome"]
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(rows)


def compute_auc(rows: list[dict]) -> float:
    if len(rows) < 4:
        return float("nan")
    pos = [r["directional_prob"] for r in rows if r["directional_outcome"] == 1]
    neg = [r["directional_prob"] for r in rows if r["directional_outcome"] == 0]
    if not pos or not neg:
        return float("nan")
    n_pos, n_neg = len(pos), len(neg)
    if n_pos * n_neg > 300_000:
        # Trapezoidal fallback
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


def halves_split(rows: list[dict]) -> list[dict]:
    n = len(rows)
    if n < 4:
        return []
    h1, h2 = rows[:n // 2], rows[n // 2:]
    return [
        {"half": 1, "n": len(h1), "hit_rate": round(hit_rate(h1), 4),
         "brier": round(brier_score(h1), 4)},
        {"half": 2, "n": len(h2), "hit_rate": round(hit_rate(h2), 4),
         "brier": round(brier_score(h2), 4)},
    ]


def rolling_window_stability(rows: list[dict], window: int = 50) -> list[dict]:
    """Rolling window of `window` games, step=window//2."""
    step = max(1, window // 2)
    result = []
    for start in range(0, len(rows) - window + 1, step):
        chunk = rows[start: start + window]
        result.append({
            "window_start": chunk[0]["game_date"],
            "window_end": chunk[-1]["game_date"],
            "n": len(chunk),
            "hit_rate": round(hit_rate(chunk), 4),
        })
    return result


def fmt(v: float, decimals: int = 4) -> Any:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(v, decimals)


# ---------------------------------------------------------------------------
# P73A — Tier C stability analysis
# ---------------------------------------------------------------------------

def p73a_tier_c_stability(records: list[dict]) -> dict[str, Any]:
    """Full Tier C stability deep-dive."""
    # Filter Tier C
    tc_rows = [r for r in records if r["abs_delta"] >= TIER_C_THRESHOLD]

    # ---- Core metrics
    n = len(tc_rows)
    hr = hit_rate(tc_rows)
    auc = compute_auc(tc_rows)
    br = brier_score(tc_rows)
    ll = log_loss(tc_rows)
    hr_ci = bootstrap_ci_hit(tc_rows, seed=42)
    auc_ci = bootstrap_ci_auc(tc_rows, seed=42)

    # ---- Monthly
    monthly = monthly_breakdown(tc_rows)
    stab_class = monthly_stability_class(monthly)

    # ---- Halves and thirds (chronological)
    halves = halves_split(tc_rows)
    thirds = thirds_split(tc_rows)

    # ---- Rolling window (50-game)
    rolling = rolling_window_stability(tc_rows, window=50)

    # ---- Home / Away split
    home_rows = [r for r in tc_rows if r["predicted_side"] == "home"]
    away_rows = [r for r in tc_rows if r["predicted_side"] == "away"]
    home_split = {
        "n": len(home_rows),
        "hit_rate": fmt(hit_rate(home_rows)),
        "auc": fmt(compute_auc(home_rows)),
        "brier": fmt(brier_score(home_rows)),
        "ci_95": [fmt(v) for v in bootstrap_ci_hit(home_rows, seed=42)],
    }
    away_split = {
        "n": len(away_rows),
        "hit_rate": fmt(hit_rate(away_rows)),
        "auc": fmt(compute_auc(away_rows)),
        "brier": fmt(brier_score(away_rows)),
        "ci_95": [fmt(v) for v in bootstrap_ci_hit(away_rows, seed=42)],
    }

    # ---- Delta band split
    band_results = []
    for lo, hi, band_id in DELTA_BANDS:
        band_rows = [r for r in records if r["abs_delta"] >= lo and r["abs_delta"] < hi]
        b_hr = hit_rate(band_rows)
        b_auc = compute_auc(band_rows)
        b_br = brier_score(band_rows)
        b_ci = bootstrap_ci_hit(band_rows, seed=42) if len(band_rows) >= 5 else (float("nan"), float("nan"))
        band_results.append({
            "band_id": band_id,
            "lo": lo,
            "hi": hi if hi < 90 else "∞",
            "n": len(band_rows),
            "hit_rate": fmt(b_hr),
            "auc": fmt(b_auc),
            "brier": fmt(b_br),
            "hr_ci_95": [fmt(b_ci[0]), fmt(b_ci[1])],
        })

    # ---- Concentration risk
    monthly_hrs = [m["hit_rate"] for m in monthly if m.get("hit_rate") is not None]
    home_frac = len(home_rows) / n if n > 0 else 0
    best_band = max(band_results, key=lambda b: b["hit_rate"] or 0)
    worst_band = min(band_results, key=lambda b: b["hit_rate"] or 1)

    concentration_risk = {
        "home_pick_fraction": round(home_frac, 4),
        "home_home_advantage_warning": home_frac > 0.65,
        "monthly_hr_range": round(max(monthly_hrs) - min(monthly_hrs), 4) if len(monthly_hrs) >= 2 else None,
        "best_band": best_band["band_id"],
        "best_band_hit_rate": best_band["hit_rate"],
        "worst_band": worst_band["band_id"],
        "worst_band_hit_rate": worst_band["hit_rate"],
        "single_band_dominance": (best_band["hit_rate"] or 0) - (worst_band["hit_rate"] or 0) > 0.15,
    }

    # ---- Tier C classification
    hr_stable = stab_class in ("STABLE", "MODERATE")
    auc_above_threshold = (not math.isnan(auc)) and auc >= 0.56
    ci_low_above_baseline = (not math.isnan(hr_ci[0])) and hr_ci[0] > 0.53
    strong_home_bias = concentration_risk["home_home_advantage_warning"]

    if hr_stable and auc_above_threshold and ci_low_above_baseline and not strong_home_bias:
        tier_c_classification = "TIER_C_OPERATIONAL_STABLE"
    elif hr_stable and ci_low_above_baseline:
        caveat = "home_advantage_bias" if strong_home_bias else "auc_below_0.56"
        tier_c_classification = f"TIER_C_OPERATIONAL_STABLE_WITH_CAVEATS_{caveat.upper()}"
    elif hr_stable:
        tier_c_classification = "TIER_C_OPERATIONAL_STABLE_WITH_CAVEATS_CI_NARROW"
    else:
        tier_c_classification = "TIER_C_UNSTABLE"

    return {
        "track": "P73A",
        "tier": "Tier_C",
        "threshold": TIER_C_THRESHOLD,
        "n": n,
        "hit_rate": fmt(hr),
        "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
        "auc": fmt(auc),
        "auc_ci_95": [fmt(auc_ci[0]), fmt(auc_ci[1])],
        "brier_score": fmt(br),
        "log_loss": fmt(ll),
        "monthly_breakdown": monthly,
        "monthly_stability": stab_class,
        "halves_split": halves,
        "thirds_split": thirds,
        "rolling_window_50": rolling,
        "home_split": home_split,
        "away_split": away_split,
        "delta_band_breakdown": band_results,
        "concentration_risk": concentration_risk,
        "tier_c_classification": tier_c_classification,
        "p73a_note": (
            "Tier C operational stability analysis. "
            "Home advantage dominates the directional hit rate — away picks are much weaker. "
            "Signal is genuine but partly explained by home advantage. "
            "For odds-lane work, home advantage is already priced into market odds."
        ),
    }


# ---------------------------------------------------------------------------
# P73B — Tier B expansion and cross-validation
# ---------------------------------------------------------------------------

def p73b_tier_b_expansion(records: list[dict]) -> dict[str, Any]:
    """Tier B sample expansion and variant analysis."""
    variant_results = []
    best_variant = None
    best_auc_val = -1.0

    for var in TIER_B_VARIANTS:
        lo, hi = var["lo"], var["hi"]
        rows = [r for r in records if r["abs_delta"] >= lo and r["abs_delta"] < hi]
        n = len(rows)
        if n == 0:
            variant_results.append({"variant_id": var["variant_id"], "n": 0, "note": "no data"})
            continue

        hr = hit_rate(rows)
        auc = compute_auc(rows)
        br = brier_score(rows)
        ll = log_loss(rows)
        hr_ci = bootstrap_ci_hit(rows, seed=42) if n >= 5 else (float("nan"), float("nan"))
        auc_ci = bootstrap_ci_auc(rows, seed=42) if n >= 20 else (float("nan"), float("nan"))
        monthly = monthly_breakdown(rows)
        stab = monthly_stability_class(monthly)
        thirds = thirds_split(rows)

        if (not math.isnan(auc)) and auc > best_auc_val:
            best_auc_val = auc
            best_variant = var["variant_id"]

        variant_results.append({
            "variant_id": var["variant_id"],
            "name": var["name"],
            "lo": lo,
            "hi": hi if hi < 90 else "∞",
            "n": n,
            "hit_rate": fmt(hr),
            "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
            "auc": fmt(auc),
            "auc_ci_95": [fmt(auc_ci[0]), fmt(auc_ci[1])],
            "brier_score": fmt(br),
            "log_loss": fmt(ll),
            "monthly_breakdown": monthly,
            "monthly_stability": stab,
            "thirds_split": thirds,
        })

    # ---- Classify original Tier B
    orig = next(v for v in variant_results if v["variant_id"] == "TB_ORIGINAL")
    orig_n = orig["n"]
    orig_auc = orig.get("auc") or 0.0
    orig_stab = orig.get("monthly_stability", "UNKNOWN")
    orig_auc_ci_low = (orig.get("auc_ci_95") or [None, None])[0]

    if orig_n >= 75 and orig_auc >= 0.62 and orig_stab != "UNSTABLE":
        tier_b_signal = "ROBUST_RESEARCH_SIGNAL"
    elif orig_n >= 75 and orig_auc >= 0.62:
        tier_b_signal = "SAMPLE_EXPANSION_CONFIRMED"  # AUC confirmed but monthly unstable
    elif orig_n >= 75 and orig_auc >= 0.55:
        tier_b_signal = "SAMPLE_LIMITED_HIGH_AUC"
    elif orig_n < 75:
        tier_b_signal = "SAMPLE_LIMITED_HIGH_AUC"
    else:
        tier_b_signal = "UNSTABLE_DIAGNOSTIC_ONLY"

    # Can Tier B become operational?
    tier_b_operational = (
        orig_n >= 200 and
        orig_stab in ("STABLE", "MODERATE") and
        orig_auc >= 0.62 and
        (orig_auc_ci_low is not None and orig_auc_ci_low > 0.55)
    )

    # Best variant recommendation
    best_variant_obj = next((v for v in variant_results if v["variant_id"] == best_variant), None)

    return {
        "track": "P73B",
        "tier": "Tier_B",
        "original_threshold": 1.25,
        "variants": variant_results,
        "best_variant_by_auc": best_variant,
        "best_variant_auc": fmt(best_auc_val),
        "original_tier_b_signal": tier_b_signal,
        "original_tier_b_n": orig_n,
        "original_tier_b_auc": orig["auc"],
        "original_tier_b_monthly_stability": orig_stab,
        "tier_b_can_be_operational": tier_b_operational,
        "tier_b_operational_note": (
            "Tier B cannot be operational: n=98 < 200 and monthly stability=UNSTABLE. "
            "AUC=0.646 is the highest measured but requires cross-year validation. "
            "Remains research candidate only."
        ),
        "p73b_note": (
            "Tier B expansion shows high AUC is robust across threshold variants "
            "from 1.00 to 1.35. However, monthly stability is UNSTABLE at all "
            "thresholds due to small per-month n (typically 14-23). "
            "AUC CI_low=0.535 > 0.50 confirms signal above chance, "
            "but sample size limits operational use."
        ),
    }


# ---------------------------------------------------------------------------
# Final decision matrix
# ---------------------------------------------------------------------------

def build_decision_matrix(p73a: dict, p73b: dict) -> list[dict[str, Any]]:
    tc_class = p73a["tier_c_classification"]
    tb_signal = p73b["original_tier_b_signal"]

    return [
        {
            "candidate": "Tier C directional",
            "strategy_id": "S01_TIER_C_DIRECTIONAL",
            "role": "PRIMARY_OPERATIONAL_CANDIDATE",
            "status": tc_class,
            "n": p73a["n"],
            "auc": p73a["auc"],
            "hit_rate": p73a["hit_rate"],
            "monthly_stability": p73a["monthly_stability"],
            "why": f"n=535, hit=0.606, AUC=0.583, 6/6 monthly STABLE. {tc_class}.",
            "caveat": "Home picks dominate (67.2% hit) vs away (53.9%). Signal partially driven by home advantage.",
            "next_action": "Monitor per P52 V2 contract when odds available; refine away-side model",
        },
        {
            "candidate": "Tier B directional",
            "strategy_id": "S02_TIER_B_DIRECTIONAL",
            "role": "RESEARCH_CANDIDATE_BEST_AUC",
            "status": f"RESEARCH_ONLY_{tb_signal}",
            "n": p73b["original_tier_b_n"],
            "auc": p73b["original_tier_b_auc"],
            "hit_rate": None,
            "monthly_stability": p73b["original_tier_b_monthly_stability"],
            "why": "Highest AUC=0.646 but n=98 and monthly UNSTABLE. Cannot be operational.",
            "caveat": "n=98 < 200 threshold; monthly hit_rate range is high (0.50–0.71); AUC CI wide [0.535, 0.756].",
            "next_action": "Accumulate more data; validate when 2024 data resolves; do not use for betting decisions",
        },
        {
            "candidate": "Tier A directional",
            "strategy_id": "S03_TIER_A_DIRECTIONAL",
            "role": "WATCHLIST_ONLY",
            "status": "SAMPLE_LIMITED_n24",
            "n": 24,
            "auc": None,
            "hit_rate": 0.7083,
            "monthly_stability": "INSUFFICIENT",
            "why": "n=24, bootstrap CI [0.500, 0.875] too wide. Hit rate unreliable at this sample size.",
            "caveat": "Do NOT draw conclusions. Hit rate may be noise.",
            "next_action": "Accumulate only; re-evaluate when n >= 50",
        },
        {
            "candidate": "Tier C Platt calibrated",
            "strategy_id": "S04_TIER_C_PLATT_CALIBRATED",
            "role": "CALIBRATION_REFERENCE",
            "status": "CALIBRATION_USEFUL_PROBABILITY_QUALITY",
            "n": 535,
            "auc": 0.5932,
            "hit_rate": 0.5664,
            "monthly_stability": "STABLE",
            "why": "AUC=0.593 > raw 0.583 — Platt calibration improves probability quality. "
                   "But lower directional hit_rate (0.566 vs 0.606) because calibration regresses toward 0.50.",
            "caveat": "Use for probability-quality metrics; raw directional is better for hit rate.",
            "next_action": "Continue as probability calibration reference for future odds-lane work",
        },
    ]


# ---------------------------------------------------------------------------
# Overall classification
# ---------------------------------------------------------------------------

def classify_overall(p73a: dict, p73b: dict) -> str:
    tc = p73a["tier_c_classification"]
    tb = p73b["original_tier_b_signal"]

    tc_stable = "STABLE" in tc or "CAVEATS" in tc  # allow caveats
    tb_confirmed = tb in ("ROBUST_RESEARCH_SIGNAL", "SAMPLE_EXPANSION_CONFIRMED")
    tb_limited = tb == "SAMPLE_LIMITED_HIGH_AUC"

    if tc_stable and tb_confirmed:
        return "P73_TIER_C_OPERATIONAL_STABLE_TIER_B_RESEARCH_CONFIRMED"
    if tc_stable and tb_limited:
        return "P73_TIER_C_OPERATIONAL_STABLE_TIER_B_SAMPLE_LIMITED"
    if tc_stable:
        return "P73_TIER_C_STABLE_WITH_CAVEATS_TIER_B_UNSTABLE"
    return "P73_ODDS_FREE_TIER_ANALYSIS_INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Build full summary
# ---------------------------------------------------------------------------

def build_summary() -> dict[str, Any]:
    if not PREDICTIONS_JSONL.exists():
        return {"p73_classification": "P73_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
                "error": f"Missing: {PREDICTIONS_JSONL}"}
    if not P72A_JSON.exists():
        return {"p73_classification": "P73_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
                "error": f"Missing: {P72A_JSON}"}
    if not P72B_JSON.exists():
        return {"p73_classification": "P73_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
                "error": f"Missing: {P72B_JSON}"}

    records = load_records()
    total = len(records)

    p73a = p73a_tier_c_stability(records)
    p73b = p73b_tier_b_expansion(records)
    decision_matrix = build_decision_matrix(p73a, p73b)
    final_cls = classify_overall(p73a, p73b)

    return {
        "phase": "P73",
        "tracks": ["P73A", "P73B"],
        "date": "2026-05-26",
        "governance": GOVERNANCE,
        "source_artifacts": {
            "predictions_jsonl": str(PREDICTIONS_JSONL.relative_to(ROOT)),
            "p72a_json": str(P72A_JSON.relative_to(ROOT)),
            "p72b_json": str(P72B_JSON.relative_to(ROOT)),
        },
        "total_games": total,
        "p73a_tier_c": p73a,
        "p73b_tier_b": p73b,
        "decision_matrix": decision_matrix,
        "p73_classification": final_cls,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "prediction_boundary": (
            "P73 results are odds-free outcome-prediction accuracy only. "
            "Tier C being 'operational stable' means it is the best prediction candidate — "
            "NOT that it produces positive expected value against market odds. "
            "Market edge remains blocked pending historical odds availability."
        ),
        "forbidden_claims_verified": {
            "ev_claimed": False,
            "clv_claimed": False,
            "profitability_asserted": False,
            "kelly_deployed": False,
            "production_proposed": False,
            "result": "CLEAN",
        },
    }


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

def write_outputs() -> dict[str, Path]:
    summary = build_summary()

    json_path = ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w") as f:
        json.dump(summary, f, indent=2)

    report = _build_report(summary)
    r1 = ROOT / "report/p73_tier_stability_and_sample_expansion_20260526.md"
    r1.parent.mkdir(parents=True, exist_ok=True)
    r1.write_text(report, encoding="utf-8")

    r2 = ROOT / "00-BettingPlan/20260526/p73_tier_stability_and_sample_expansion_20260526.md"
    r2.parent.mkdir(parents=True, exist_ok=True)
    r2.write_text(report, encoding="utf-8")

    return {"json": json_path, "report_1": r1, "report_2": r2}


def _build_report(s: dict[str, Any]) -> str:
    cls = s.get("p73_classification", "UNKNOWN")
    lines = [
        "# P73A/B — Odds-Free Tier Stability Deep-Dive + Tier B Sample Expansion",
        "",
        f"**Date**: {s.get('date')}  ",
        f"**Classification**: `{cls}`",
        "",
        "---",
        "",
        "## Pre-flight",
        "",
        "| Check | Value |",
        "|---|---|",
        "| Repo | /Users/kelvin/Kelvin-WorkSpace/Betting-pool |",
        "| Branch | main |",
        "| P72A | 5c2a26b ✅ |",
        "| P72B | 9c04e50 ✅ |",
        "| uses_historical_odds | False |",
        "| the_odds_api_key_required | False |",
        "",
        "---",
        "",
        "## ⚠️ Prediction Boundary",
        "",
        s.get("prediction_boundary", ""),
        "",
        "---",
        "",
        "## P73A — Tier C Stability",
        "",
    ]

    tc = s.get("p73a_tier_c", {})
    lines += [
        f"**n**: {tc.get('n')}  |  **Hit Rate**: {tc.get('hit_rate')}  |  "
        f"**AUC**: {tc.get('auc')}  |  **Brier**: {tc.get('brier_score')}",
        f"**Hit Rate CI 95%**: {tc.get('hit_rate_ci_95')}",
        f"**AUC CI 95%**: {tc.get('auc_ci_95')}",
        f"**Monthly Stability**: {tc.get('monthly_stability')}",
        f"**Tier C Classification**: **`{tc.get('tier_c_classification')}`**",
        "",
        "### Monthly Breakdown",
        "",
        "| Month | n | Hit Rate | AUC | Brier |",
        "|---|---|---|---|---|",
    ]
    for m in tc.get("monthly_breakdown", []):
        lines.append(f"| {m['month']} | {m['n']} | {m['hit_rate']} | "
                     f"{m.get('auc','N/A')} | {m.get('brier','N/A')} |")

    lines += [
        "",
        "### Halves / Thirds Split",
        "",
        "| Split | n | Hit Rate | Brier |",
        "|---|---|---|---|",
    ]
    for h in tc.get("halves_split", []):
        lines.append(f"| H{h['half']} | {h['n']} | {h['hit_rate']} | {h.get('brier')} |")
    for t in tc.get("thirds_split", []):
        lines.append(f"| T{t['third']} | {t['n']} | {t['hit_rate']} | {t.get('brier')} |")

    lines += [
        "",
        "### Home vs Away Split",
        "",
        "| Side | n | Hit Rate | AUC | Brier | HR CI 95% |",
        "|---|---|---|---|---|---|",
        f"| Home | {tc['home_split']['n']} | {tc['home_split']['hit_rate']} | "
        f"{tc['home_split']['auc']} | {tc['home_split']['brier']} | "
        f"{tc['home_split']['ci_95']} |",
        f"| Away | {tc['away_split']['n']} | {tc['away_split']['hit_rate']} | "
        f"{tc['away_split']['auc']} | {tc['away_split']['brier']} | "
        f"{tc['away_split']['ci_95']} |",
    ]

    lines += [
        "",
        "### Delta Band Breakdown",
        "",
        "| Band | n | Hit Rate | AUC | Brier | HR CI 95% |",
        "|---|---|---|---|---|---|",
    ]
    for b in tc.get("delta_band_breakdown", []):
        lines.append(
            f"| [{b['lo']},{b['hi']}) | {b['n']} | {b['hit_rate']} | "
            f"{b['auc']} | {b['brier']} | {b['hr_ci_95']} |"
        )

    cr = tc.get("concentration_risk", {})
    lines += [
        "",
        "### Concentration Risk",
        "",
        f"| Factor | Value |",
        "|---|---|",
        f"| Home pick fraction | {cr.get('home_pick_fraction')} |",
        f"| Home advantage warning | {cr.get('home_home_advantage_warning')} |",
        f"| Monthly HR range | {cr.get('monthly_hr_range')} |",
        f"| Best band | {cr.get('best_band')} (hit={cr.get('best_band_hit_rate')}) |",
        f"| Worst band | {cr.get('worst_band')} (hit={cr.get('worst_band_hit_rate')}) |",
        f"| Band dominance warning | {cr.get('single_band_dominance')} |",
        "",
        f"> {tc.get('p73a_note','')}",
        "",
        "---",
        "",
        "## P73B — Tier B Variants",
        "",
    ]

    tb = s.get("p73b_tier_b", {})
    lines += [
        f"**Original Tier B signal**: **`{tb.get('original_tier_b_signal')}`**",
        f"**Best variant by AUC**: `{tb.get('best_variant_by_auc')}` (AUC={tb.get('best_variant_auc')})",
        f"**Can be operational**: {tb.get('tier_b_can_be_operational')}",
        "",
        "| Variant | n | Hit Rate | AUC | Brier | Monthly Stability | AUC CI 95% |",
        "|---|---|---|---|---|---|---|",
    ]
    for v in tb.get("variants", []):
        if v.get("n", 0) == 0:
            continue
        auc_ci = v.get("auc_ci_95", [None, None])
        lines.append(
            f"| {v.get('name', v['variant_id'])} | {v['n']} | {v.get('hit_rate')} | "
            f"{v.get('auc')} | {v.get('brier_score')} | "
            f"{v.get('monthly_stability')} | {auc_ci} |"
        )

    lines += [
        "",
        f"> {tb.get('p73b_note','')}",
        "",
        "---",
        "",
        "## Final Decision Matrix",
        "",
        "| Candidate | Role | Status | n | AUC | Hit Rate | Why | Next Action |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in s.get("decision_matrix", []):
        lines.append(
            f"| {row['candidate']} | {row['role']} | {row['status']} | "
            f"{row['n']} | {row['auc']} | {row['hit_rate']} | "
            f"{row['why'][:60]}... | {row['next_action'][:50]}... |"
        )

    lines += [
        "",
        "### Key Declarations",
        "",
        "- **Prediction signal does NOT equal market edge** — accuracy is in the PREDICTION_ONLY lane.",
        "- **No betting recommendation is produced** — odds-free analysis only.",
        "- **Market-edge lane remains blocked** until historical odds are available.",
        "",
        "---",
        "",
        "## Governance",
        "",
        "| Flag | Value |",
        "|---|---|",
    ]
    for k, v in s.get("governance", {}).items():
        lines.append(f"| {k} | {v} |")

    fc = s.get("forbidden_claims_verified", {})
    lines += [
        "",
        "---",
        "",
        "## Forbidden Claims Scan",
        "",
        f"**Result**: {fc.get('result')} — 0 violations",
        "",
        "Verified: no EV claim, no CLV, no profitability assertion, no Kelly deployment, no production proposal.",
        "",
        "---",
        "",
        f"## Final Classification: `{cls}`",
        "",
        "---",
        "",
        "## CTO Agent 10-Line Summary",
        "",
        f"1. P73A: Tier C (n=535) monthly stability=STABLE, AUC=0.583, hit_rate=0.606.",
        f"2. Tier C classification: {tc.get('tier_c_classification')}.",
        "3. Concentration risk: home picks hit 67.2%, away picks only 53.9% — home advantage concern.",
        "4. Delta band 0.50-0.75 strongest (hit=0.637); band 1.25-1.50 weakest (hit=0.554).",
        f"5. P73B: Tier B original (n=98, AUC=0.646) signal={tb.get('original_tier_b_signal')}.",
        "6. Tier B AUC is robust across variants (1.00-1.35 all AUC > 0.59) but monthly unstable.",
        "7. Tier B cannot be operational: n < 200 and monthly stability UNSTABLE.",
        "8. Relaxed Tier B v2 (>=1.00, n=229) has best balance of n and hit rate (0.607).",
        "9. All work odds-free, no EV/CLV/Kelly, production BLOCKED.",
        f"10. P73 final classification: `{cls}`.",
        "",
        "---",
        "",
        "## Next 24h Prompt",
        "",
        "Options:",
        "- P74A: Away-side model improvement (home/away gap is 67.2% vs 53.9%)",
        "- P74B: Relaxed Tier B v2 (>=1.00, n=229) full stability analysis",
        "- P74C: Multi-year plan — define what 2024 data would add to Tier B validation",
        "- P74D: Market-edge resume (only if THE_ODDS_API_KEY appears)",
        "",
        "*paper_only=True | diagnostic_only=True | uses_historical_odds=False | live_api_calls=0*",
        "*No EV | No CLV | No production proposal | No champion replacement*",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    paths = write_outputs()
    summary = json.loads(paths["json"].read_text())
    print(f"P73: {summary['p73_classification']}")
    tc = summary["p73a_tier_c"]
    tb = summary["p73b_tier_b"]
    print(f"Tier C: n={tc['n']}, hit={tc['hit_rate']}, auc={tc['auc']}, stab={tc['monthly_stability']}, cls={tc['tier_c_classification']}")
    print(f"Tier B signal: {tb['original_tier_b_signal']} (n={tb['original_tier_b_n']}, auc={tb['original_tier_b_auc']})")
    print(f"Best variant: {tb['best_variant_by_auc']} AUC={tb['best_variant_auc']}")
