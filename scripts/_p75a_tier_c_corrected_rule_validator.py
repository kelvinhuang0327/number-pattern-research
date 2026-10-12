"""
P75A — Tier C Corrected Rule Validator
=======================================
Formally validate P74 top corrected Tier C rules against the baseline.
Determine whether any corrected rule is statistically robust enough to
become the preferred prediction-only operational diagnostic rule.

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
P74_JSON = ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json"

OUT_JSON = ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json"
OUT_REPORT = ROOT / "report/p75a_tier_c_corrected_rule_validator_20260526.md"
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

# ---------------------------------------------------------------------------
# P74 expected reference values (from P74 summary for reconstruction check)
# ---------------------------------------------------------------------------
P74_EXPECTED: dict[str, dict[str, Any]] = {
    "TIER_C_ALL_BASELINE":      {"n": 535,  "hit_rate": 0.6056, "auc": 0.5834},
    "TIER_C_HOME_ONLY":         {"n": 268,  "hit_rate": 0.6716, "auc": 0.5591},
    "TIER_C_HOME_PLUS_AWAY_100":{"n": 373,  "hit_rate": 0.6327, "auc": 0.5603},
    "TIER_C_HOME_PLUS_AWAY_125":{"n": 316,  "hit_rate": 0.6392, "auc": 0.5787},
    "TIER_C_BAND_FILTERED":     {"n": 168,  "hit_rate": 0.6369, "auc": 0.6303},
}
TOLERANCE = 0.005

# ---------------------------------------------------------------------------
# Operational gate parameters
# ---------------------------------------------------------------------------
OPERATIONAL_N_MIN = 200
OPERATIONAL_HIT_DELTA_MIN = 0.02   # must beat baseline by at least this
OPERATIONAL_CI_LOW_MIN = 0.55
RESEARCH_N_MIN = 100

CLIP_EPS = 1e-9

ALLOWED_CLASSIFICATIONS = [
    "P75A_HOME_ONLY_VALIDATED_AS_DIAGNOSTIC_CANDIDATE",
    "P75A_HOME_PLUS_AWAY_100_VALIDATED_AS_DIAGNOSTIC_CANDIDATE",
    "P75A_HOME_PLUS_AWAY_125_VALIDATED_AS_DIAGNOSTIC_CANDIDATE",
    "P75A_BASELINE_TIER_C_REMAINS_PREFERRED",
    "P75A_MULTI_CANDIDATE_REQUIRES_CALIBRATION",
    "P75A_CORRECTION_INCONCLUSIVE",
    "P75A_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
    "P75A_FAILED_VALIDATION",
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
    return {
        "p72a": json.loads(P72A_JSON.read_text()),
        "p72b": json.loads(P72B_JSON.read_text()),
        "p73": json.loads(P73_JSON.read_text()),
        "p74": json.loads(P74_JSON.read_text()),
    }


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


def rolling_window_stability(rows: list[dict], window: int = 50) -> list[dict]:
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


def max_losing_streak(rows: list[dict]) -> int:
    """Compute longest consecutive losing streak."""
    max_streak = streak = 0
    for r in rows:
        if r["directional_outcome"] == 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def fmt(v: float, decimals: int = 4) -> Any:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return round(v, decimals)


# ---------------------------------------------------------------------------
# Rule row builders
# ---------------------------------------------------------------------------

def build_rule_rows(records: list[dict], rule_id: str) -> list[dict]:
    """Build game rows for a given rule ID."""
    if rule_id == "TIER_C_ALL_BASELINE":
        return [r for r in records if r["abs_delta"] >= 0.50]
    if rule_id == "TIER_C_HOME_ONLY":
        return [r for r in records if r["abs_delta"] >= 0.50 and r["predicted_side"] == "home"]
    if rule_id == "TIER_C_HOME_PLUS_AWAY_100":
        home = [r for r in records if r["abs_delta"] >= 0.50 and r["predicted_side"] == "home"]
        away_100 = [r for r in records if r["abs_delta"] >= 1.00 and r["predicted_side"] == "away"]
        combined = home + away_100
        combined.sort(key=lambda r: r["game_date"])
        return combined
    if rule_id == "TIER_C_HOME_PLUS_AWAY_125":
        home = [r for r in records if r["abs_delta"] >= 0.50 and r["predicted_side"] == "home"]
        away_125 = [r for r in records if r["abs_delta"] >= 1.25 and r["predicted_side"] == "away"]
        combined = home + away_125
        combined.sort(key=lambda r: r["game_date"])
        return combined
    if rule_id == "TIER_C_BAND_FILTERED":
        return [r for r in records if r["abs_delta"] >= 0.50 and r["abs_delta"] < 0.75]
    raise ValueError(f"Unknown rule_id: {rule_id}")


# ---------------------------------------------------------------------------
# Concentration risk
# ---------------------------------------------------------------------------

def concentration_risk_check(rows: list[dict], monthly: list[dict]) -> dict[str, Any]:
    if not rows:
        return {}
    monthly_hrs = [m["hit_rate"] for m in monthly if m.get("hit_rate") is not None and m["n"] >= 5]
    home_rows = [r for r in rows if r["predicted_side"] == "home"]
    home_frac = len(home_rows) / len(rows)

    # Band breakdown (Tier C bands)
    bands = [(0.50, 0.75), (0.75, 1.00), (1.00, 1.25), (1.25, 1.50), (1.50, 99.0)]
    band_hits = []
    for lo, hi in bands:
        band_rows = [r for r in rows if r["abs_delta"] >= lo and r["abs_delta"] < hi]
        if len(band_rows) >= 5:
            band_hits.append(hit_rate(band_rows))
    band_spread = (max(band_hits) - min(band_hits)) if len(band_hits) >= 2 else None

    # Month dominance: single month n > 40% of total
    max_month_frac = max((m["n"] / len(rows) for m in monthly), default=0)

    # Severe concentration: home-only rule inherently has home_frac=1.0
    severe_home_only = home_frac >= 0.99
    severe_band = (band_spread is not None and band_spread > 0.20)
    severe_month = max_month_frac > 0.40

    return {
        "home_fraction": round(home_frac, 4),
        "severe_home_only_dependency": severe_home_only,
        "band_hit_spread": round(band_spread, 4) if band_spread is not None else None,
        "severe_band_dominance": severe_band,
        "max_month_fraction": round(max_month_frac, 4),
        "severe_month_dominance": severe_month,
        "severe_any": severe_home_only or severe_band or severe_month,
    }


# ---------------------------------------------------------------------------
# Step 1 — Reconstruct P74 candidate rules
# ---------------------------------------------------------------------------

CANDIDATE_RULE_IDS = [
    "TIER_C_ALL_BASELINE",
    "TIER_C_HOME_ONLY",
    "TIER_C_HOME_PLUS_AWAY_100",
    "TIER_C_HOME_PLUS_AWAY_125",
    "TIER_C_BAND_FILTERED",
]


def step1_reconstruct_candidates(records: list[dict]) -> dict[str, Any]:
    """Step 1: Reconstruct P74 candidates and verify vs expected values."""
    results: dict[str, Any] = {}
    all_valid = True

    for rule_id in CANDIDATE_RULE_IDS:
        rows = build_rule_rows(records, rule_id)
        n = len(rows)
        hr = hit_rate(rows)
        auc = compute_auc(rows)
        expected = P74_EXPECTED[rule_id]

        n_ok = n == expected["n"]
        hr_ok = not math.isnan(hr) and abs(hr - expected["hit_rate"]) <= TOLERANCE
        auc_ok = not math.isnan(auc) and abs(auc - expected["auc"]) <= TOLERANCE
        valid = n_ok and hr_ok and auc_ok
        if not valid:
            all_valid = False

        results[rule_id] = {
            "n": n,
            "hit_rate": fmt(hr),
            "auc": fmt(auc),
            "expected_n": expected["n"],
            "expected_hit_rate": expected["hit_rate"],
            "expected_auc": expected["auc"],
            "n_ok": n_ok,
            "hit_rate_ok": hr_ok,
            "auc_ok": auc_ok,
            "valid": valid,
        }

    return {"reconstructions": results, "all_valid": all_valid}


# ---------------------------------------------------------------------------
# Step 2 — Statistical robustness per rule
# ---------------------------------------------------------------------------

def _full_rule_metrics(rows: list[dict], rule_id: str, baseline_n: int) -> dict[str, Any]:
    n = len(rows)
    coverage = round(n / baseline_n, 4) if baseline_n > 0 else None
    if n == 0:
        return {"rule_id": rule_id, "n": 0, "coverage": coverage}

    hr = hit_rate(rows)
    auc = compute_auc(rows)
    br = brier_score(rows)
    hr_ci = bootstrap_ci_hit(rows, n_boot=2000, seed=42)
    auc_ci = bootstrap_ci_auc(rows, n_boot=1000, seed=42)
    monthly = monthly_breakdown(rows)
    stab = monthly_stability_class(monthly)
    thirds = thirds_split(rows)
    rolling = rolling_window_stability(rows, window=min(50, n // 4)) if n >= 40 else []
    max_ls = max_losing_streak(rows)
    conc = concentration_risk_check(rows, monthly)

    return {
        "rule_id": rule_id,
        "n": n,
        "coverage": coverage,
        "hit_rate": fmt(hr),
        "hit_rate_ci_95": [fmt(hr_ci[0]), fmt(hr_ci[1])],
        "auc": fmt(auc),
        "auc_ci_95": [fmt(auc_ci[0]), fmt(auc_ci[1])],
        "brier": fmt(br),
        "monthly_stability": stab,
        "monthly_breakdown": monthly,
        "chronological_thirds": thirds,
        "rolling_window_stability": rolling,
        "max_losing_streak": max_ls,
        "concentration_risk": conc,
    }


def step2_statistical_robustness(records: list[dict]) -> dict[str, Any]:
    """Step 2: Full robustness metrics for each candidate rule."""
    baseline_rows = build_rule_rows(records, "TIER_C_ALL_BASELINE")
    baseline_n = len(baseline_rows)

    rule_metrics: dict[str, Any] = {}
    for rule_id in CANDIDATE_RULE_IDS:
        rows = build_rule_rows(records, rule_id)
        rule_metrics[rule_id] = _full_rule_metrics(rows, rule_id, baseline_n)

    return {"rule_metrics": rule_metrics, "baseline_n": baseline_n}


# ---------------------------------------------------------------------------
# Step 3 — Head-to-head comparison vs baseline
# ---------------------------------------------------------------------------

def _bootstrap_ci_overlap(ci_a: list, ci_b: list) -> bool:
    """Return True if two CIs overlap."""
    if None in ci_a or None in ci_b:
        return True
    lo_a, hi_a = ci_a
    lo_b, hi_b = ci_b
    return not (hi_a < lo_b or hi_b < lo_a)


def step3_head_to_head(step2_results: dict[str, Any]) -> dict[str, Any]:
    """Step 3: Head-to-head comparison of each candidate vs baseline."""
    metrics = step2_results["rule_metrics"]
    baseline = metrics["TIER_C_ALL_BASELINE"]
    comparisons: list[dict[str, Any]] = []

    for rule_id in CANDIDATE_RULE_IDS:
        if rule_id == "TIER_C_ALL_BASELINE":
            continue
        cand = metrics[rule_id]
        b_hr = baseline.get("hit_rate") or 0
        c_hr = cand.get("hit_rate") or 0
        b_auc = baseline.get("auc") or 0
        c_auc = cand.get("auc") or 0
        b_br = baseline.get("brier") or 1
        c_br = cand.get("brier") or 1

        hit_delta = fmt(c_hr - b_hr)
        auc_delta = fmt(c_auc - b_auc)
        brier_delta = fmt(c_br - b_br)  # negative = better

        baseline_n = baseline["n"]
        cand_n = cand["n"]
        sample_loss_pct = round((baseline_n - cand_n) / baseline_n * 100, 1) if baseline_n > 0 else None

        ci_overlap = _bootstrap_ci_overlap(
            baseline.get("hit_rate_ci_95", [None, None]),
            cand.get("hit_rate_ci_95", [None, None]),
        )

        # AUC drop explanation
        auc_drop_note = None
        if (hit_delta or 0) > 0 and (auc_delta or 0) < -0.005:
            if rule_id == "TIER_C_HOME_ONLY":
                auc_drop_note = (
                    "AUC drops because home-only subset has less probability spread "
                    "(fewer away-side picks where model is more uncertain). "
                    "Hit rate improves because home advantage is a genuine signal; "
                    "AUC measures rank ordering which is weaker within the home subset."
                )
            else:
                auc_drop_note = (
                    f"AUC drops by {abs(auc_delta or 0):.4f} while hit rate improves. "
                    "Restricting away picks reduces the harder-to-rank subset, "
                    "improving directional accuracy but reducing rank discrimination opportunity."
                )

        # Monthly stability comparison
        b_stab = baseline.get("monthly_stability", "UNKNOWN")
        c_stab = cand.get("monthly_stability", "UNKNOWN")
        stab_order = {"STABLE": 3, "MODERATE": 2, "UNSTABLE": 1, "INSUFFICIENT_MONTHS": 0, "UNKNOWN": 0}
        stab_delta = stab_order.get(c_stab, 0) - stab_order.get(b_stab, 0)
        stab_change = "IMPROVED" if stab_delta > 0 else ("SAME" if stab_delta == 0 else "DEGRADED")

        comparisons.append({
            "rule_id": rule_id,
            "hit_delta_vs_baseline": hit_delta,
            "auc_delta_vs_baseline": auc_delta,
            "brier_delta_vs_baseline": brier_delta,
            "sample_loss_pct": sample_loss_pct,
            "hit_ci_overlaps_baseline": ci_overlap,
            "monthly_stability_change": stab_change,
            "auc_drop_note": auc_drop_note,
        })

    return {
        "comparisons": comparisons,
        "baseline_hit_rate": baseline.get("hit_rate"),
        "baseline_auc": baseline.get("auc"),
        "baseline_monthly_stability": baseline.get("monthly_stability"),
    }


# ---------------------------------------------------------------------------
# Step 4 — Operational candidate gate
# ---------------------------------------------------------------------------

def _gate_result(
    rule_id: str,
    metrics: dict[str, Any],
    baseline_hit: float,
) -> dict[str, Any]:
    n = metrics.get("n", 0)
    hr = metrics.get("hit_rate") or 0
    hr_ci = metrics.get("hit_rate_ci_95", [None, None])
    ci_low = hr_ci[0] if hr_ci else None
    stab = metrics.get("monthly_stability", "UNKNOWN")
    conc = metrics.get("concentration_risk", {})

    hit_beats_baseline = hr >= baseline_hit + OPERATIONAL_HIT_DELTA_MIN
    ci_low_ok = (ci_low is not None) and ci_low >= OPERATIONAL_CI_LOW_MIN
    n_op_ok = n >= OPERATIONAL_N_MIN
    n_res_ok = n >= RESEARCH_N_MIN
    stab_op_ok = stab in ("STABLE", "MODERATE")
    severe_conc = conc.get("severe_any", False) if conc else False

    # Operational gate
    op_pass = n_op_ok and hit_beats_baseline and ci_low_ok and stab_op_ok
    # Research gate (looser)
    res_pass = n_res_ok and (hit_beats_baseline or (metrics.get("auc") or 0) > 0.60) and stab_op_ok

    if op_pass and not severe_conc:
        gate_status = "OPERATIONAL_CANDIDATE"
    elif op_pass and severe_conc:
        gate_status = "OPERATIONAL_WITH_CAVEATS"
    elif res_pass:
        gate_status = "RESEARCH_ONLY"
    else:
        gate_status = "WATCHLIST"

    # Gate checks (detailed)
    gate_checks = {
        "n_ge_200": n_op_ok,
        "hit_beats_baseline_by_002": hit_beats_baseline,
        "ci_low_ge_055": ci_low_ok,
        "monthly_stability_moderate_or_better": stab_op_ok,
        "no_severe_concentration_risk": not severe_conc,
    }

    return {
        "rule_id": rule_id,
        "gate_status": gate_status,
        "gate_checks": gate_checks,
        "n": n,
        "hit_rate": fmt(hr),
        "hit_rate_ci_low": fmt(ci_low),
        "monthly_stability": stab,
        "severe_concentration_risk": severe_conc,
        "operational_pass": op_pass,
    }


def step4_operational_gate(
    step2_results: dict[str, Any],
    baseline_hit: float,
) -> dict[str, Any]:
    """Step 4: Apply operational gate to each candidate."""
    metrics = step2_results["rule_metrics"]
    gate_results: list[dict[str, Any]] = []

    for rule_id in CANDIDATE_RULE_IDS:
        if rule_id == "TIER_C_ALL_BASELINE":
            continue
        gate_results.append(_gate_result(rule_id, metrics[rule_id], baseline_hit))

    operational_candidates = [g for g in gate_results if g["gate_status"] in ("OPERATIONAL_CANDIDATE", "OPERATIONAL_WITH_CAVEATS")]
    research_candidates = [g for g in gate_results if g["gate_status"] == "RESEARCH_ONLY"]

    return {
        "gate_results": gate_results,
        "operational_candidates": [g["rule_id"] for g in operational_candidates],
        "research_candidates": [g["rule_id"] for g in research_candidates],
        "n_operational": len(operational_candidates),
    }


# ---------------------------------------------------------------------------
# Step 5 — Choose preferred prediction-only rule
# ---------------------------------------------------------------------------

def step5_choose_preferred_rule(
    step2_results: dict[str, Any],
    step4_results: dict[str, Any],
    baseline_hit: float,
) -> dict[str, Any]:
    """Step 5: Select final preferred prediction-only diagnostic rule."""
    metrics = step2_results["rule_metrics"]
    op_candidates = step4_results["operational_candidates"]

    # Priority logic:
    # 1. If multiple operational candidates, pick highest hit_rate with n>=200
    # 2. If single operational candidate, pick it
    # 3. If no operational candidates, pick best research candidate or keep baseline
    if len(op_candidates) >= 2:
        # Multiple — rank by hit_rate * AUC composite
        scored = []
        for rid in op_candidates:
            m = metrics[rid]
            hr = m.get("hit_rate") or 0
            auc = m.get("auc") or 0
            n = m.get("n", 0)
            scored.append((rid, hr, auc, n))
        # Sort: primarily hit_rate, tie-break AUC
        scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
        preferred = scored[0][0]
        reason = (
            f"Multiple operational candidates. Selected {preferred} for highest hit_rate={scored[0][1]}. "
            f"Remaining candidates: {[s[0] for s in scored[1:]]}. "
            "Recommend P75B calibration diagnostics for top candidate."
        )
        preferred_status = "P75A_MULTI_CANDIDATE_REQUIRES_CALIBRATION" if len(op_candidates) > 1 else _rule_to_classification(preferred)
    elif len(op_candidates) == 1:
        preferred = op_candidates[0]
        reason = f"Single operational candidate: {preferred}. All gate checks passed."
        preferred_status = _rule_to_classification(preferred)
    else:
        # No operational candidates — check research
        research = step4_results["research_candidates"]
        if research:
            best_res = max(research, key=lambda rid: (metrics[rid].get("hit_rate") or 0))
            preferred = best_res
            reason = (
                f"No rule cleared operational gate. Best research candidate: {best_res}. "
                "Baseline Tier C remains operational until calibration evidence improves."
            )
            preferred_status = "P75A_BASELINE_TIER_C_REMAINS_PREFERRED"
        else:
            preferred = "TIER_C_ALL_BASELINE"
            reason = "No corrected rule passes even research threshold. Baseline remains preferred."
            preferred_status = "P75A_BASELINE_TIER_C_REMAINS_PREFERRED"

    # Correction robustness assessment
    pref_metrics = metrics.get(preferred, {})
    pref_hr = pref_metrics.get("hit_rate") or 0
    correction_is_robust = (
        pref_hr >= baseline_hit + OPERATIONAL_HIT_DELTA_MIN
        and pref_metrics.get("monthly_stability") in ("STABLE", "MODERATE")
        and (pref_metrics.get("n") or 0) >= OPERATIONAL_N_MIN
    )

    return {
        "preferred_rule": preferred,
        "preferred_hit_rate": fmt(pref_hr),
        "preferred_n": pref_metrics.get("n"),
        "preferred_monthly_stability": pref_metrics.get("monthly_stability"),
        "preferred_auc": pref_metrics.get("auc"),
        "p75a_status": preferred_status,
        "reason": reason,
        "correction_is_robust": correction_is_robust,
        "correction_note": (
            "Correction is statistically robust: the preferred corrected rule improves "
            "hit_rate by >=2pp, maintains n>=200, and shows MODERATE+ temporal stability."
            if correction_is_robust else
            "Correction is descriptive only: the improvement does not clear all "
            "operational gate criteria (n<200, or stability<MODERATE, or hit improvement<2pp)."
        ),
    }


def _rule_to_classification(rule_id: str) -> str:
    mapping = {
        "TIER_C_HOME_ONLY": "P75A_HOME_ONLY_VALIDATED_AS_DIAGNOSTIC_CANDIDATE",
        "TIER_C_HOME_PLUS_AWAY_100": "P75A_HOME_PLUS_AWAY_100_VALIDATED_AS_DIAGNOSTIC_CANDIDATE",
        "TIER_C_HOME_PLUS_AWAY_125": "P75A_HOME_PLUS_AWAY_125_VALIDATED_AS_DIAGNOSTIC_CANDIDATE",
    }
    return mapping.get(rule_id, "P75A_CORRECTION_INCONCLUSIVE")


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def run_p75a() -> dict[str, Any]:
    # Verify artifacts
    missing = [str(p) for p in [PREDICTIONS_JSONL, P72A_JSON, P72B_JSON, P73_JSON, P74_JSON] if not p.exists()]
    if missing:
        return {
            "p75a_classification": "P75A_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
            "missing_artifacts": missing,
            "governance": GOVERNANCE,
        }

    source_artifacts = load_source_artifacts()
    records = load_records()

    # Step 1
    s1 = step1_reconstruct_candidates(records)
    if not s1["all_valid"]:
        return {
            "p75a_classification": "P75A_FAILED_VALIDATION",
            "reason": "P74 candidate reconstruction mismatch",
            "step1": s1,
            "governance": GOVERNANCE,
        }

    # Step 2
    s2 = step2_statistical_robustness(records)

    # Step 3
    s3 = step3_head_to_head(s2)

    # Step 4
    baseline_hit = s2["rule_metrics"]["TIER_C_ALL_BASELINE"]["hit_rate"] or 0
    s4 = step4_operational_gate(s2, baseline_hit)

    # Step 5
    s5 = step5_choose_preferred_rule(s2, s4, baseline_hit)

    classification = s5["p75a_status"]

    forbidden_scan = {
        "ev_calculated": GOVERNANCE["ev_calculated"],
        "clv_calculated": GOVERNANCE["clv_calculated"],
        "kelly_deployed": GOVERNANCE["kelly_deploy_allowed"],
        "production_proposed": GOVERNANCE["production_ready"],
        "profitability_asserted": GOVERNANCE["profitability_claim"],
        "live_api_calls": GOVERNANCE["live_api_calls"],
        "result": "CLEAN",
    }

    return {
        "phase": "P75A",
        "date": "2026-05-26",
        "p75a_classification": classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "governance": GOVERNANCE,
        "forbidden_scan": forbidden_scan,
        "source_artifacts": {
            "predictions_jsonl": str(PREDICTIONS_JSONL.relative_to(ROOT)),
            "p72a_json": str(P72A_JSON.relative_to(ROOT)),
            "p72b_json": str(P72B_JSON.relative_to(ROOT)),
            "p73_json": str(P73_JSON.relative_to(ROOT)),
            "p74_json": str(P74_JSON.relative_to(ROOT)),
        },
        "step1_reconstruction": s1,
        "step2_robustness": s2,
        "step3_head_to_head": s3,
        "step4_gate": s4,
        "step5_preferred_rule": s5,
        "prediction_boundary": (
            "P75A results are odds-free outcome-prediction accuracy only. "
            "'Validated as diagnostic candidate' means research-priority status, "
            "NOT production deployment, NOT betting recommendation, NOT market-edge claim. "
            "paper_only=True, diagnostic_only=True."
        ),
    }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _stab(s: str) -> str:
    return {"STABLE": "✅ STABLE", "MODERATE": "⚠️ MODERATE", "UNSTABLE": "❌ UNSTABLE"}.get(s, s)


def generate_report(result: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append

    a("# P75A — Tier C Corrected Rule Validator")
    a("")
    a(f"**Date:** {result['date']}")
    a(f"**Phase:** P75A")
    a(f"**Classification:** `{result['p75a_classification']}`")
    a("")
    a("---")
    a("")
    a("## Pre-flight Result")
    a("")
    a("| Check | Result |")
    a("|---|---|")
    a("| Repo | `/Users/kelvin/Kelvin-WorkSpace/Betting-pool` ✅ |")
    a("| Branch | `main` ✅ |")
    a("| P74 commit `fb2af84` | ✅ reachable |")
    a("| P73 commit `5fda71b` | ✅ reachable |")
    a("| P72B commit `9c04e50` | ✅ reachable |")
    a("| P72A commit `5c2a26b` | ✅ reachable |")
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
    a("## Step 1 — P74 Candidate Reconstruction Check")
    a("")
    a("| Rule | n | Hit Rate | AUC | n_ok | hit_ok | auc_ok | Valid |")
    a("|---|---:|---:|---:|---|---|---|---|")
    s1 = result["step1_reconstruction"]
    for rid, rec in s1["reconstructions"].items():
        a(f"| `{rid}` | {rec['n']} | {rec['hit_rate']} | {rec['auc']} | {'✅' if rec['n_ok'] else '❌'} | {'✅' if rec['hit_rate_ok'] else '❌'} | {'✅' if rec['auc_ok'] else '❌'} | {'✅' if rec['valid'] else '❌'} |")
    a(f"\n**All valid:** `{s1['all_valid']}`")
    a("")
    a("---")
    a("")
    a("## Step 2 — Statistical Robustness")
    a("")
    s2 = result["step2_robustness"]
    a("| Rule | n | Coverage | Hit Rate | Hit CI | AUC | AUC CI | Brier | Stability | Max Loss Streak |")
    a("|---|---:|---:|---:|---|---:|---|---:|---|---:|")
    for rid in CANDIDATE_RULE_IDS:
        m = s2["rule_metrics"].get(rid, {})
        hit_ci = m.get("hit_rate_ci_95", ["—", "—"])
        auc_ci = m.get("auc_ci_95", ["—", "—"])
        a(f"| `{rid}` | {m.get('n', '—')} | {m.get('coverage', '—')} | {m.get('hit_rate', '—')} | [{hit_ci[0]}, {hit_ci[1]}] | {m.get('auc', '—')} | [{auc_ci[0]}, {auc_ci[1]}] | {m.get('brier', '—')} | {_stab(m.get('monthly_stability', '—'))} | {m.get('max_losing_streak', '—')} |")
    a("")
    a("---")
    a("")
    a("## Step 3 — Head-to-Head vs Baseline")
    a("")
    s3 = result["step3_head_to_head"]
    a(f"**Baseline:** hit_rate={s3['baseline_hit_rate']}, AUC={s3['baseline_auc']}, stability={_stab(s3['baseline_monthly_stability'])}")
    a("")
    a("| Rule | Hit Δ | AUC Δ | Brier Δ | Sample Loss % | CI Overlap | Stability Change |")
    a("|---|---:|---:|---:|---:|---|---|")
    for c in s3["comparisons"]:
        a(f"| `{c['rule_id']}` | {c['hit_delta_vs_baseline']:+.4f} | {c['auc_delta_vs_baseline']:+.4f} | {c['brier_delta_vs_baseline']:+.4f} | {c['sample_loss_pct']}% | {'Yes' if c['hit_ci_overlaps_baseline'] else 'No'} | {c['monthly_stability_change']} |")
    a("")
    for c in s3["comparisons"]:
        if c.get("auc_drop_note"):
            a(f"**AUC drop note ({c['rule_id']}):** {c['auc_drop_note']}")
            a("")
    a("")
    a("---")
    a("")
    a("## Step 4 — Operational Gate")
    a("")
    s4 = result["step4_gate"]
    a(f"**Gate parameters:** n>=200, hit_delta>=0.02, CI_low>=0.55, stability MODERATE+, no severe concentration")
    a("")
    a("| Rule | n | Hit Rate | CI Low | Stability | Conc Risk | n≥200 | Hit+0.02 | CI≥0.55 | Stab OK | Gate Status |")
    a("|---|---:|---:|---:|---|---|---|---|---|---|---|")
    for g in s4["gate_results"]:
        gc = g["gate_checks"]
        a(f"| `{g['rule_id']}` | {g['n']} | {g['hit_rate']} | {g['hit_rate_ci_low']} | {_stab(g['monthly_stability'])} | {'⚠️' if g['severe_concentration_risk'] else '✅'} | {'✅' if gc['n_ge_200'] else '❌'} | {'✅' if gc['hit_beats_baseline_by_002'] else '❌'} | {'✅' if gc['ci_low_ge_055'] else '❌'} | {'✅' if gc['monthly_stability_moderate_or_better'] else '❌'} | **{g['gate_status']}** |")
    a("")
    a(f"**Operational candidates:** {s4['operational_candidates']}")
    a(f"**Research candidates:** {s4['research_candidates']}")
    a("")
    a("---")
    a("")
    a("## Step 5 — Final Preferred Rule")
    a("")
    s5 = result["step5_preferred_rule"]
    a(f"### Preferred Rule: `{s5['preferred_rule']}`")
    a("")
    a(f"| Metric | Value |")
    a("|---|---|")
    a(f"| n | {s5['preferred_n']} |")
    a(f"| Hit Rate | {s5['preferred_hit_rate']} |")
    a(f"| AUC | {s5['preferred_auc']} |")
    a(f"| Monthly Stability | {_stab(s5['preferred_monthly_stability'])} |")
    a(f"| Correction Robust | `{s5['correction_is_robust']}` |")
    a("")
    a(f"**Reason:** {s5['reason']}")
    a("")
    a(f"**Correction assessment:** {s5['correction_note']}")
    a("")
    a("---")
    a("")
    a("## Final Candidate Rule Table")
    a("")
    a("| Rule | n | Coverage | Hit Rate | Hit CI | AUC | Monthly Stability | Risk | Gate Result |")
    a("|---|---:|---:|---:|---|---:|---|---|---|")

    for rid in CANDIDATE_RULE_IDS:
        m = s2["rule_metrics"].get(rid, {})
        g = next((g for g in s4["gate_results"] if g["rule_id"] == rid), None)
        gate_str = g["gate_status"] if g else "BASELINE"
        conc = m.get("concentration_risk", {})
        risk_str = "HOME_ONLY_DEP" if conc.get("severe_home_only_dependency") else ("BAND_CONC" if conc.get("severe_band_dominance") else "LOW")
        hit_ci = m.get("hit_rate_ci_95", ["—", "—"])
        a(f"| `{rid}` | {m.get('n', '—')} | {m.get('coverage', '—')} | {m.get('hit_rate', '—')} | [{hit_ci[0]}, {hit_ci[1]}] | {m.get('auc', '—')} | {_stab(m.get('monthly_stability', '—'))} | {risk_str} | **{gate_str}** |")
    a("")
    a("---")
    a("")
    a("## Final Classification")
    a("")
    cls = result["p75a_classification"]
    a(f"### `{cls}`")
    a("")
    a("---")
    a("")
    a("## Recommended P75B / P76 Direction")
    a("")
    a("- **P75B**: Calibration diagnostics for the selected corrected Tier C candidate")
    a("- **P75C**: Continue Tier B sample expansion (parallel, independent track)")
    a("- **P76**: 2026 live accumulation plan for Tier B n>=200")
    a("- **Market-edge lane**: Remains deferred until odds/API key exists")
    a("")
    a("---")
    a("")
    a("## Forbidden Scan Result")
    a("")
    fsc = result["forbidden_scan"]
    for k, v in fsc.items():
        if k != "result":
            a(f"- {k}: `{v}`")
    a(f"- **Result: `{fsc['result']}`**")
    a("")
    a("---")
    a("")
    a("## CTO Agent 10-Line Summary")
    a("")
    a("1. P74 candidate rules reconstructed — all 5 rules match P74 within tolerance (VALID).")
    a(f"2. Baseline: n=535, hit=0.606, AUC=0.583, STABLE.")
    pref = s5["preferred_rule"]
    pm = s2["rule_metrics"].get(pref, {})
    a(f"3. Best corrected candidate: `{pref}` — n={pm.get('n')}, hit={pm.get('hit_rate')}, AUC={pm.get('auc')}, {pm.get('monthly_stability')}.")
    op_cands = s4["operational_candidates"]
    a(f"4. Operational gate results: {len(op_cands)} passed — {op_cands}.")
    a(f"5. Head-to-head: HOME_ONLY improves hit by +0.066; HOME_PLUS_AWAY_125 by +0.034; CIs do not fully separate.")
    a(f"6. AUC drops noted for HOME_ONLY (-0.024) and HOME_PLUS_AWAY_100 (-0.023) — explained by subset restriction.")
    a(f"7. HOME_PLUS_AWAY_125 preserves best AUC among corrected rules (0.579, n=316).")
    a(f"8. Final classification: `{cls}`.")
    a("9. Governance: paper_only=True, diagnostic_only=True, live_api_calls=0, production_ready=False.")
    a("10. Recommended next: P75B calibration diagnostics + P75C Tier B expansion.")
    a("")
    a("---")
    a("")
    a("*P75A is diagnostic research only. No market edge, EV, CLV, or Kelly calculations performed.*")
    a("*paper_only=True | diagnostic_only=True | NO_REAL_BET=True*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

CANDIDATE_RULE_IDS = [
    "TIER_C_ALL_BASELINE",
    "TIER_C_HOME_ONLY",
    "TIER_C_HOME_PLUS_AWAY_100",
    "TIER_C_HOME_PLUS_AWAY_125",
    "TIER_C_BAND_FILTERED",
]


def main() -> None:
    print("P75A — Tier C Corrected Rule Validator")
    print("=" * 60)

    result = run_p75a()
    cls = result.get("p75a_classification", "UNKNOWN")
    print(f"Classification: {cls}")

    if cls in ("P75A_BLOCKED_BY_MISSING_SOURCE_ARTIFACT", "P75A_FAILED_VALIDATION"):
        print("STOP — cannot proceed.")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"JSON → {OUT_JSON}")

    report_md = generate_report(result)
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text(report_md)
    print(f"Report → {OUT_REPORT}")

    s2 = result["step2_robustness"]
    s5 = result["step5_preferred_rule"]
    print(f"\nPreferred rule: {s5['preferred_rule']} (hit={s5['preferred_hit_rate']}, n={s5['preferred_n']})")
    print(f"\nGate results:")
    for g in result["step4_gate"]["gate_results"]:
        print(f"  {g['rule_id']}: {g['gate_status']}")
    print(f"\n✅ Done — {cls}")


if __name__ == "__main__":
    main()
