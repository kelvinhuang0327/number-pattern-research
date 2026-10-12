"""
P72A — Odds-Free Strategy Accuracy Backtest
============================================
CEO direction: Find which MLB strategy is most accurate at predicting game
outcomes WITHOUT using betting odds.

This module evaluates pure outcome-prediction accuracy metrics only.
No EV, CLV, Kelly, or market-edge calculations.
No odds API key required.

Governance locks (MANDATORY):
  paper_only=True
  diagnostic_only=True
  uses_historical_odds=False
  live_api_calls=0
  paid_api_called=False
  the_odds_api_key_required=False
  market_edge_calculated=False
  ev_calculated=False
  clv_calculated=False
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
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Source artifact
# ---------------------------------------------------------------------------
PREDICTIONS_JSONL = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
P45_JSON = ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"

# ---------------------------------------------------------------------------
# Platt constants (locked from P45)
# ---------------------------------------------------------------------------
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464
CLIP_EPS: float = 1e-9

# ---------------------------------------------------------------------------
# Strategy definitions
# ---------------------------------------------------------------------------
STRATEGIES: list[dict[str, Any]] = [
    {
        "strategy_id": "S00_BASELINE_ALL",
        "description": "Baseline: all games, model_home_prob predicts home win",
        "tier_label": "ALL",
        "filter_fn_name": "all_games",
        "threshold": 0.0,
        "directional": False,
    },
    {
        "strategy_id": "S01_TIER_C_DIRECTIONAL",
        "description": "Tier C directional: |sp_fip_delta|>=0.50, pick team model favors",
        "tier_label": "Tier_C",
        "filter_fn_name": "tier_c",
        "threshold": 0.50,
        "directional": True,
    },
    {
        "strategy_id": "S02_TIER_B_DIRECTIONAL",
        "description": "Tier B directional: |sp_fip_delta|>=1.25, pick team model favors",
        "tier_label": "Tier_B",
        "filter_fn_name": "tier_b",
        "threshold": 1.25,
        "directional": True,
    },
    {
        "strategy_id": "S03_TIER_A_DIRECTIONAL",
        "description": "Tier A directional: |sp_fip_delta|>=1.50, pick team model favors",
        "tier_label": "Tier_A",
        "filter_fn_name": "tier_a",
        "threshold": 1.50,
        "directional": True,
    },
    {
        "strategy_id": "S04_TIER_C_PLATT_CALIBRATED",
        "description": "Tier C with Platt-calibrated prob (P45 locked constants)",
        "tier_label": "Tier_C_Platt",
        "filter_fn_name": "tier_c",
        "threshold": 0.50,
        "directional": False,
        "use_platt": True,
    },
    {
        "strategy_id": "S05_HOME_FAVOR_STRONG",
        "description": "sp_fip_delta >= 0.50 (home team strongly favored by FIP delta)",
        "tier_label": "Home_Strong",
        "filter_fn_name": "home_favor_strong",
        "threshold": 0.50,
        "directional": True,
        "direction_fixed": "home",
    },
    {
        "strategy_id": "S06_AWAY_FAVOR_STRONG",
        "description": "sp_fip_delta <= -0.50 (away team strongly favored by FIP delta)",
        "tier_label": "Away_Strong",
        "filter_fn_name": "away_favor_strong",
        "threshold": 0.50,
        "directional": True,
        "direction_fixed": "away",
    },
]

ALLOWED_CLASSIFICATIONS = [
    "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED",
    "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_WEAK",
    "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_INCONCLUSIVE",
    "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_NEGATIVE",
    "P72A_BLOCKED_BY_MISSING_OUTCOME_DATA",
    "P72A_BLOCKED_BY_TEST_FAILURE",
    "P72A_BLOCKED_BY_SCOPE_VIOLATION",
]

GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "paid_api_called": False,
    "the_odds_api_key_required": False,
    "market_edge_calculated": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
}

# ---------------------------------------------------------------------------
# Platt calibration
# ---------------------------------------------------------------------------

def _logit(p: float) -> float:
    p = max(CLIP_EPS, min(1 - CLIP_EPS, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def platt_calibrate(raw_prob: float) -> float:
    """Apply locked P45 Platt constants."""
    return _sigmoid(PLATT_A * _logit(raw_prob) + PLATT_B)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_records() -> list[dict[str, Any]]:
    """Load all prediction records with outcome, sp_fip_delta, model_home_prob."""
    records: list[dict[str, Any]] = []
    with PREDICTIONS_JSONL.open() as f:
        for line in f:
            r = json.loads(line)
            p0 = r.get("p0_features") or {}
            sp_fip_delta = p0.get("sp_fip_delta")
            sp_available = p0.get("sp_fip_delta_available", True)
            home_win = r.get("home_win")
            model_prob_home = r.get("model_home_prob")
            game_date = r.get("game_date", "")
            month = game_date[:7] if game_date else "UNKNOWN"

            if home_win is None or model_prob_home is None:
                continue
            if sp_fip_delta is None or not sp_available:
                sp_fip_delta = 0.0  # will be excluded by tier filters

            # Compute Platt-calibrated prob (always from home perspective)
            platt_prob_home = platt_calibrate(model_prob_home)

            records.append({
                "game_id": r.get("game_id", ""),
                "game_date": game_date,
                "month": month,
                "home_team": r.get("home_team", ""),
                "away_team": r.get("away_team", ""),
                "home_win": int(home_win),
                "sp_fip_delta": float(sp_fip_delta),
                "sp_available": bool(sp_available),
                "model_prob_home": float(model_prob_home),
                "platt_prob_home": float(platt_prob_home),
            })
    return records


# ---------------------------------------------------------------------------
# Strategy filters — return (filtered records, predicted_prob, actual_outcome)
# ---------------------------------------------------------------------------

def _get_strategy_rows(records: list[dict[str, Any]], strat: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Filter records per strategy and annotate each with:
      - predicted_prob: probability for the "model side"
      - predicted_win:  1/0 binary pick (model favored side wins?)
      - actual_outcome: did the model's favored side win? (1/0)
    """
    fn = strat["filter_fn_name"]
    thresh = strat["threshold"]
    use_platt = strat.get("use_platt", False)
    direction_fixed = strat.get("direction_fixed")
    directional = strat.get("directional", True)

    result = []
    for r in records:
        delta = r["sp_fip_delta"]
        prob_home_raw = r["platt_prob_home"] if use_platt else r["model_prob_home"]

        # Filter
        if fn == "all_games":
            pass  # keep all
        elif fn == "tier_c":
            if abs(delta) < 0.50:
                continue
        elif fn == "tier_b":
            if abs(delta) < 1.25:
                continue
        elif fn == "tier_a":
            if abs(delta) < 1.50:
                continue
        elif fn == "home_favor_strong":
            if delta < 0.50:
                continue
        elif fn == "away_favor_strong":
            if delta > -0.50:
                continue

        home_win = r["home_win"]

        if directional and direction_fixed is None:
            # Directional: model favors whichever side has positive sp_fip_delta
            # sp_fip_delta > 0 → home is "better" pitcher matchup
            if delta > 0:
                predicted_side = "home"
                predicted_prob = prob_home_raw
                actual_outcome = home_win
            else:
                predicted_side = "away"
                predicted_prob = 1.0 - prob_home_raw
                actual_outcome = 1 - home_win
        elif direction_fixed == "home":
            predicted_side = "home"
            predicted_prob = prob_home_raw
            actual_outcome = home_win
        elif direction_fixed == "away":
            predicted_side = "away"
            predicted_prob = 1.0 - prob_home_raw
            actual_outcome = 1 - home_win
        else:
            # Non-directional: use home prob, home win as outcome
            predicted_side = "home"
            predicted_prob = prob_home_raw
            actual_outcome = home_win

        result.append({
            **r,
            "predicted_side": predicted_side,
            "predicted_prob": predicted_prob,
            "actual_outcome": actual_outcome,
        })
    return result


# ---------------------------------------------------------------------------
# Metric computations (no sklearn, pure Python)
# ---------------------------------------------------------------------------

def compute_hit_rate(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return float("nan")
    hits = sum(1 for r in rows if r["actual_outcome"] == 1)
    return hits / len(rows)


def compute_brier_score(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return float("nan")
    return sum((r["predicted_prob"] - r["actual_outcome"]) ** 2 for r in rows) / len(rows)


def compute_log_loss(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return float("nan")
    total = 0.0
    for r in rows:
        p = max(CLIP_EPS, min(1 - CLIP_EPS, r["predicted_prob"]))
        y = r["actual_outcome"]
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / len(rows)


def compute_auc(rows: list[dict[str, Any]]) -> float:
    """Compute AUC using Mann-Whitney U statistic (exact, O(n^2) but feasible for n<600)."""
    if len(rows) < 4:
        return float("nan")
    pos = [r["predicted_prob"] for r in rows if r["actual_outcome"] == 1]
    neg = [r["predicted_prob"] for r in rows if r["actual_outcome"] == 0]
    if not pos or not neg:
        return float("nan")
    # For large sets use the sorted trapezoidal AUC
    n_pos = len(pos)
    n_neg = len(neg)
    if n_pos * n_neg > 200_000:
        return _auc_trapezoid(rows)
    # Mann-Whitney
    correct = sum(1 for p in pos for n in neg if p > n)
    tied = sum(1 for p in pos for n in neg if p == n)
    return (correct + 0.5 * tied) / (n_pos * n_neg)


def _auc_trapezoid(rows: list[dict[str, Any]]) -> float:
    """Trapezoidal AUC via sorted thresholds."""
    sorted_rows = sorted(rows, key=lambda r: r["predicted_prob"], reverse=True)
    n_pos = sum(1 for r in rows if r["actual_outcome"] == 1)
    n_neg = len(rows) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    tp = fp = 0
    prev_tp = prev_fp = 0
    auc = 0.0
    for r in sorted_rows:
        if r["actual_outcome"] == 1:
            tp += 1
        else:
            fp += 1
        auc += (fp - prev_fp) * (tp + prev_tp) / 2.0
        prev_tp, prev_fp = tp, fp
    return auc / (n_pos * n_neg)


def compute_ece(rows: list[dict[str, Any]], n_bins: int = 10) -> float:
    """Expected Calibration Error using equal-width bins."""
    if len(rows) < 20:
        return float("nan")
    bins: list[list[dict]] = [[] for _ in range(n_bins)]
    for r in rows:
        idx = min(int(r["predicted_prob"] * n_bins), n_bins - 1)
        bins[idx].append(r)
    ece = 0.0
    n = len(rows)
    for b in bins:
        if len(b) < 2:
            continue
        mean_pred = sum(r["predicted_prob"] for r in b) / len(b)
        mean_actual = sum(r["actual_outcome"] for r in b) / len(b)
        ece += (len(b) / n) * abs(mean_pred - mean_actual)
    return ece


def bootstrap_ci(values: list[float], stat_fn, n_boot: int = 2000, seed: int = 42,
                 ci: float = 0.95) -> tuple[float, float]:
    """Bootstrap CI for a statistic function applied to a list of values."""
    rng = random.Random(seed)
    if len(values) < 5:
        return (float("nan"), float("nan"))
    boot_stats = []
    for _ in range(n_boot):
        sample = [rng.choice(values) for _ in range(len(values))]
        boot_stats.append(stat_fn(sample))
    boot_stats.sort()
    lo = boot_stats[int((1 - ci) / 2 * n_boot)]
    hi = boot_stats[int((1 + ci) / 2 * n_boot) - 1]
    return (lo, hi)


def bootstrap_hit_rate_ci(rows: list[dict[str, Any]], n_boot: int = 2000, seed: int = 42):
    outcomes = [r["actual_outcome"] for r in rows]
    return bootstrap_ci(outcomes, lambda xs: sum(xs) / len(xs) if xs else 0.0,
                        n_boot=n_boot, seed=seed)


def bootstrap_auc_ci(rows: list[dict[str, Any]], n_boot: int = 1000, seed: int = 42):
    if len(rows) < 20:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    boot_aucs = []
    for _ in range(n_boot):
        sample = [rng.choice(rows) for _ in range(len(rows))]
        boot_aucs.append(compute_auc(sample))
    boot_aucs = [x for x in boot_aucs if not math.isnan(x)]
    if not boot_aucs:
        return (float("nan"), float("nan"))
    boot_aucs.sort()
    lo = boot_aucs[int(0.025 * len(boot_aucs))]
    hi = boot_aucs[int(0.975 * len(boot_aucs)) - 1]
    return (lo, hi)


# ---------------------------------------------------------------------------
# Monthly stability
# ---------------------------------------------------------------------------

def compute_monthly_stability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    months_data: dict[str, list] = {}
    for r in rows:
        m = r["month"]
        months_data.setdefault(m, []).append(r)

    monthly: list[dict] = []
    for month in sorted(months_data.keys()):
        mrows = months_data[month]
        n = len(mrows)
        hr = compute_hit_rate(mrows)
        monthly.append({
            "month": month,
            "n": n,
            "hit_rate": round(hr, 4) if not math.isnan(hr) else None,
            "brier": round(compute_brier_score(mrows), 4) if n >= 5 else None,
        })

    hit_rates = [m["hit_rate"] for m in monthly if m["hit_rate"] is not None]
    stability: str
    if len(hit_rates) >= 3:
        hr_range = max(hit_rates) - min(hit_rates)
        if hr_range <= 0.10:
            stability = "STABLE"
        elif hr_range <= 0.20:
            stability = "MODERATE"
        else:
            stability = "UNSTABLE"
    else:
        stability = "INSUFFICIENT_MONTHS"

    return {"monthly_breakdown": monthly, "stability_classification": stability}


# ---------------------------------------------------------------------------
# Thirds stability
# ---------------------------------------------------------------------------

def compute_thirds_stability(rows: list[dict[str, Any]]) -> list[dict]:
    if len(rows) < 9:
        return []
    n = len(rows)
    t1 = rows[: n // 3]
    t2 = rows[n // 3: 2 * n // 3]
    t3 = rows[2 * n // 3:]
    thirds = []
    for i, chunk in enumerate([t1, t2, t3], 1):
        thirds.append({
            "third": i,
            "n": len(chunk),
            "hit_rate": round(compute_hit_rate(chunk), 4),
        })
    return thirds


# ---------------------------------------------------------------------------
# Failure segment analysis
# ---------------------------------------------------------------------------

def compute_failure_segments(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # By month
    by_month: dict[str, list] = {}
    for r in rows:
        by_month.setdefault(r["month"], []).append(r)
    month_hr = {m: compute_hit_rate(v) for m, v in by_month.items()}

    # By side
    home_rows = [r for r in rows if r["predicted_side"] == "home"]
    away_rows = [r for r in rows if r["predicted_side"] == "away"]

    # By tier (inferred from abs delta)
    tier_c = [r for r in rows if abs(r["sp_fip_delta"]) >= 0.50]
    tier_b = [r for r in rows if abs(r["sp_fip_delta"]) >= 1.25]
    tier_a = [r for r in rows if abs(r["sp_fip_delta"]) >= 1.50]

    return {
        "worst_month": min(month_hr, key=month_hr.get) if month_hr else None,
        "best_month": max(month_hr, key=month_hr.get) if month_hr else None,
        "home_hit_rate": round(compute_hit_rate(home_rows), 4) if home_rows else None,
        "away_hit_rate": round(compute_hit_rate(away_rows), 4) if away_rows else None,
        "n_home_picks": len(home_rows),
        "n_away_picks": len(away_rows),
        "tier_c_hit_rate": round(compute_hit_rate(tier_c), 4) if tier_c else None,
        "tier_b_hit_rate": round(compute_hit_rate(tier_b), 4) if tier_b else None,
        "tier_a_hit_rate": round(compute_hit_rate(tier_a), 4) if tier_a else None,
    }


# ---------------------------------------------------------------------------
# Per-strategy label
# ---------------------------------------------------------------------------
RANDOM_BASELINE_HIT_RATE = 0.530  # empirical home win rate


def classify_strategy(hit_rate: float, auc: float, hr_ci_low: float, n: int) -> str:
    """Classify predictive signal quality (odds-free, accuracy only)."""
    if n < 10:
        return "PREDICTIVE_SIGNAL_INCONCLUSIVE"
    if math.isnan(hit_rate):
        return "PREDICTIVE_SIGNAL_INCONCLUSIVE"

    # AUC-based primary signal
    if not math.isnan(auc):
        if auc >= 0.56:
            return "PREDICTIVE_SIGNAL_CONFIRMED"
        if auc >= 0.52:
            return "PREDICTIVE_SIGNAL_WEAK"
        if auc >= 0.50:
            return "PREDICTIVE_SIGNAL_INCONCLUSIVE"
        return "PREDICTIVE_SIGNAL_NEGATIVE"
    else:
        # Fall back to hit rate vs random baseline
        if hit_rate >= RANDOM_BASELINE_HIT_RATE + 0.05 and not math.isnan(hr_ci_low) and hr_ci_low > RANDOM_BASELINE_HIT_RATE:
            return "PREDICTIVE_SIGNAL_CONFIRMED"
        if hit_rate >= RANDOM_BASELINE_HIT_RATE + 0.02:
            return "PREDICTIVE_SIGNAL_WEAK"
        if hit_rate >= RANDOM_BASELINE_HIT_RATE - 0.02:
            return "PREDICTIVE_SIGNAL_INCONCLUSIVE"
        return "PREDICTIVE_SIGNAL_NEGATIVE"


# ---------------------------------------------------------------------------
# Full strategy evaluation
# ---------------------------------------------------------------------------

def evaluate_strategy(strat: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    rows = _get_strategy_rows(records, strat)
    n = len(rows)
    total_games = len(records)
    coverage = n / total_games if total_games > 0 else 0.0

    hit_rate = compute_hit_rate(rows)
    brier = compute_brier_score(rows)
    log_loss_val = compute_log_loss(rows)
    auc = compute_auc(rows)
    ece = compute_ece(rows)

    hr_ci = bootstrap_hit_rate_ci(rows) if n >= 10 else (float("nan"), float("nan"))
    auc_ci = bootstrap_auc_ci(rows) if n >= 20 else (float("nan"), float("nan"))

    monthly = compute_monthly_stability(rows)
    thirds = compute_thirds_stability(rows)
    failure_segs = compute_failure_segments(rows)

    signal_label = classify_strategy(
        hit_rate, auc,
        hr_ci[0] if not math.isnan(hr_ci[0]) else float("nan"),
        n
    )

    def fmt(v) -> Any:
        if math.isnan(v):
            return None
        return round(v, 6)

    def fmt4(v) -> Any:
        if math.isnan(v):
            return None
        return round(v, 4)

    return {
        "strategy_id": strat["strategy_id"],
        "description": strat["description"],
        "tier_label": strat["tier_label"],
        "n": n,
        "coverage": round(coverage, 4),
        "hit_rate": fmt4(hit_rate),
        "hit_rate_ci_95": [fmt4(hr_ci[0]), fmt4(hr_ci[1])],
        "auc": fmt4(auc),
        "auc_ci_95": [fmt4(auc_ci[0]), fmt4(auc_ci[1])],
        "brier_score": fmt4(brier),
        "log_loss": fmt4(log_loss_val),
        "ece": fmt4(ece),
        "monthly_stability": monthly,
        "thirds_stability": thirds,
        "failure_segments": failure_segs,
        "signal_label": signal_label,
        "note_no_odds_used": True,
        "note_not_ev_or_clv": "This is accuracy-only. Positive hit rate does NOT imply positive EV against market.",
    }


# ---------------------------------------------------------------------------
# Overall classification
# ---------------------------------------------------------------------------

def classify_overall(strategy_results: list[dict[str, Any]]) -> str:
    """Classify overall P72A result based on best non-baseline strategy."""
    non_baseline = [s for s in strategy_results if s["strategy_id"] != "S00_BASELINE_ALL"]
    if not non_baseline:
        return "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_INCONCLUSIVE"

    labels = [s["signal_label"] for s in non_baseline]
    confirmed = labels.count("PREDICTIVE_SIGNAL_CONFIRMED")
    weak = labels.count("PREDICTIVE_SIGNAL_WEAK")
    negative = labels.count("PREDICTIVE_SIGNAL_NEGATIVE")

    # Best AUC among non-baseline
    aucs = [s["auc"] for s in non_baseline if s["auc"] is not None]
    best_auc = max(aucs) if aucs else 0.0

    if confirmed >= 1 and best_auc >= 0.56:
        return "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_CONFIRMED"
    if confirmed >= 1 or weak >= 2:
        return "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_WEAK"
    if negative >= len(non_baseline) // 2:
        return "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_NEGATIVE"
    return "P72A_ODDS_FREE_PREDICTIVE_SIGNAL_INCONCLUSIVE"


# ---------------------------------------------------------------------------
# Build full summary
# ---------------------------------------------------------------------------

def build_summary() -> dict[str, Any]:
    records = load_records()
    total_games = len(records)

    strategy_results = [evaluate_strategy(strat, records) for strat in STRATEGIES]

    final_classification = classify_overall(strategy_results)

    # Best / worst by AUC
    ranked = sorted(
        [s for s in strategy_results if s["strategy_id"] != "S00_BASELINE_ALL" and s["auc"] is not None],
        key=lambda s: s["auc"],
        reverse=True,
    )
    best_strategy = ranked[0]["strategy_id"] if ranked else None
    worst_strategy = ranked[-1]["strategy_id"] if ranked else None

    return {
        "phase": "P72A",
        "task": "Odds-Free Strategy Accuracy Backtest",
        "date": "2026-05-26",
        "governance": GOVERNANCE,
        "source_artifact": str(PREDICTIONS_JSONL.relative_to(ROOT)),
        "total_games": total_games,
        "date_range": {
            "start": min(r["game_date"] for r in records),
            "end": max(r["game_date"] for r in records),
        },
        "months_covered": sorted(set(r["month"] for r in records)),
        "home_win_rate_empirical": round(sum(r["home_win"] for r in records) / total_games, 4),
        "platt_constants_used": {
            "platt_A": PLATT_A,
            "platt_B": PLATT_B,
            "source": "P45 locked constants — not refit in P72A",
        },
        "strategy_results": strategy_results,
        "best_strategy": best_strategy,
        "worst_strategy": worst_strategy,
        "final_classification": final_classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "interpretation_note": (
            "These metrics measure outcome-prediction accuracy only. "
            "A hit rate above random baseline or AUC > 0.50 means the model has "
            "directional predictive skill. This does NOT imply positive EV against "
            "market odds. Market edge requires comparing model probabilities to odds-implied "
            "probabilities, which is a separate analysis requiring historical odds data."
        ),
        "odds_used": False,
        "api_key_required": False,
        "ev_calculated": False,
        "clv_calculated": False,
        "market_edge_calculated": False,
    }


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

def write_outputs() -> dict[str, Path]:
    summary = build_summary()

    json_path = ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w") as f:
        json.dump(summary, f, indent=2)

    report_md = _build_report(summary)
    r1 = ROOT / "report/p72a_odds_free_strategy_accuracy_backtest_20260526.md"
    r1.parent.mkdir(parents=True, exist_ok=True)
    r1.write_text(report_md, encoding="utf-8")

    r2 = ROOT / "00-BettingPlan/20260526/p72a_odds_free_strategy_accuracy_backtest_20260526.md"
    r2.parent.mkdir(parents=True, exist_ok=True)
    r2.write_text(report_md, encoding="utf-8")

    return {"json": json_path, "report_1": r1, "report_2": r2}


def _build_report(s: dict[str, Any]) -> str:
    lines = [
        "# P72A — Odds-Free Strategy Accuracy Backtest",
        "",
        f"**Date**: {s['date']}  ",
        f"**Classification**: `{s['final_classification']}`",
        "",
        "---",
        "",
        "## Pre-flight",
        "",
        "| Check | Value |",
        "|---|---|",
        "| Repo | /Users/kelvin/Kelvin-WorkSpace/Betting-pool |",
        "| Branch | main |",
        "| HEAD | 1d8adb8 |",
        "| paper_only | True |",
        "| uses_historical_odds | **False** |",
        "| the_odds_api_key_required | **False** |",
        "",
        "---",
        "",
        "## Source Artifacts",
        "",
        f"- `{s['source_artifact']}` — {s['total_games']} games ({s['date_range']['start']} to {s['date_range']['end']})",
        f"- Months covered: {', '.join(s['months_covered'])}",
        f"- Empirical home win rate: {s['home_win_rate_empirical']}",
        "",
        "---",
        "",
        "## ⚠️ Interpretation Note",
        "",
        s["interpretation_note"],
        "",
        "**This analysis does NOT use odds, does NOT calculate EV or CLV, ",
        "and does NOT constitute a betting recommendation.**",
        "",
        "---",
        "",
        "## Strategies Evaluated",
        "",
        "| Strategy | Description | Threshold |",
        "|---|---|---|",
    ]
    for strat in STRATEGIES:
        lines.append(f"| `{strat['strategy_id']}` | {strat['description']} | {strat['threshold']} |")

    lines += [
        "",
        "---",
        "",
        "## Metrics Table",
        "",
        "| Strategy | n | Coverage | Hit Rate | AUC | Brier | Log-Loss | ECE | Signal |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in s["strategy_results"]:
        hr = r["hit_rate"] if r["hit_rate"] is not None else "N/A"
        auc = r["auc"] if r["auc"] is not None else "N/A"
        brier = r["brier_score"] if r["brier_score"] is not None else "N/A"
        ll = r["log_loss"] if r["log_loss"] is not None else "N/A"
        ece = r["ece"] if r["ece"] is not None else "N/A"
        lines.append(
            f"| `{r['strategy_id']}` | {r['n']} | {r['coverage']} | "
            f"{hr} | {auc} | {brier} | {ll} | {ece} | **{r['signal_label']}** |"
        )

    lines += [
        "",
        "Hit Rate CI (95%) and AUC CI (95%) from bootstrap (n_boot=2000/1000, seed=42):",
        "",
        "| Strategy | Hit Rate | HR CI [lo, hi] | AUC | AUC CI [lo, hi] |",
        "|---|---|---|---|---|",
    ]
    for r in s["strategy_results"]:
        hr = r["hit_rate"] if r["hit_rate"] is not None else "N/A"
        hr_ci = r["hit_rate_ci_95"]
        auc = r["auc"] if r["auc"] is not None else "N/A"
        auc_ci = r["auc_ci_95"]
        lines.append(
            f"| `{r['strategy_id']}` | {hr} | [{hr_ci[0]}, {hr_ci[1]}] | {auc} | [{auc_ci[0]}, {auc_ci[1]}] |"
        )

    lines += [
        "",
        "---",
        "",
        "## Monthly Stability Table",
        "",
        "| Strategy | Month | n | Hit Rate | Brier |",
        "|---|---|---|---|---|",
    ]
    for r in s["strategy_results"]:
        for m in r["monthly_stability"]["monthly_breakdown"]:
            lines.append(
                f"| `{r['strategy_id']}` | {m['month']} | {m['n']} | "
                f"{m['hit_rate'] if m['hit_rate'] is not None else 'N/A'} | "
                f"{m['brier'] if m['brier'] is not None else 'N/A'} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Thirds Stability",
        "",
        "| Strategy | Third | n | Hit Rate |",
        "|---|---|---|---|",
    ]
    for r in s["strategy_results"]:
        for t in r["thirds_stability"]:
            lines.append(
                f"| `{r['strategy_id']}` | {t['third']} | {t['n']} | {t['hit_rate']} |"
            )

    lines += [
        "",
        "---",
        "",
        "## Best and Worst Strategy",
        "",
        f"- **Best predictive strategy**: `{s['best_strategy']}`",
        f"- **Worst predictive strategy**: `{s['worst_strategy']}`",
        "",
        "---",
        "",
        "## Failure Segment Analysis",
        "",
        "| Strategy | Worst Month | Best Month | Home Hit | Away Hit | Tier C | Tier B | Tier A |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in s["strategy_results"]:
        fs = r["failure_segments"]
        lines.append(
            f"| `{r['strategy_id']}` | {fs['worst_month']} | {fs['best_month']} | "
            f"{fs['home_hit_rate']} | {fs['away_hit_rate']} | "
            f"{fs['tier_c_hit_rate']} | {fs['tier_b_hit_rate']} | {fs['tier_a_hit_rate']} |"
        )

    lines += [
        "",
        "---",
        "",
        "## Governance",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    for k, v in s["governance"].items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "---",
        "",
        "## Key Disclaimers",
        "",
        "- **Odds used**: NO — this backtest uses no betting odds.",
        "- **API key required**: NO — `the_odds_api_key_required=False`.",
        "- **EV / CLV**: NOT calculated. Accuracy != profitability.",
        "- **Betting recommendation**: This is a diagnostic accuracy study, NOT a betting strategy.",
        "- Positive AUC or hit rate above baseline means the model has directional skill.",
        "  It does NOT mean bets on this model would be profitable against market lines.",
        "",
        "---",
        "",
        f"## Final Classification: `{s['final_classification']}`",
        "",
        "---",
        "",
        "## CTO Agent 10-Line Summary",
        "",
        f"1. Source: {s['total_games']} MLB 2025 games (Apr–Sep), zero odds data used.",
        "2. 7 strategies evaluated: ALL, Tier C/B/A directional, Tier C Platt, Home/Away strong.",
        f"3. Best strategy by AUC: `{s['best_strategy']}`.",
        f"4. Worst strategy by AUC: `{s['worst_strategy']}`.",
        "5. Empirical home win baseline: {:.3f} — used as random baseline reference.".format(s["home_win_rate_empirical"]),
        "6. All metrics are accuracy-only: hit rate, AUC, Brier, log-loss, ECE.",
        "7. No EV, CLV, Kelly, or profit/ROI calculated — those require odds data.",
        "8. Monthly stability and thirds stability reported per strategy.",
        "9. Interpretation: AUC > 0.50 = directional skill; does NOT imply +EV vs market.",
        f"10. P72A classification: `{s['final_classification']}`.",
        "",
        "*paper_only=True | diagnostic_only=True | uses_historical_odds=False | live_api_calls=0*",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    paths = write_outputs()
    summary = json.loads(paths["json"].read_text())
    print(f"P72A complete: {summary['final_classification']}")
    for r in summary["strategy_results"]:
        print(f"  {r['strategy_id']}: n={r['n']}, hit_rate={r['hit_rate']}, "
              f"auc={r['auc']}, signal={r['signal_label']}")
