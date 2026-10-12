"""
P76 — Corrected Tier C Final Rule Selection + 2026 Accumulation Plan
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True | NO_REAL_BET=True

Goals:
  1. Final tie-break between TIER_C_HOME_PLUS_AWAY_125 and TIER_C_HOME_PLUS_AWAY_100
     using a weighted scorecard (directional 30% / calibration 25% / coverage 20% /
     stability-risk 15% / future-readiness 10%).
  2. Define 2026 live accumulation plan (monthly cadence, Tier B n>=200 threshold, stop criteria).
  3. Document prediction-only research roadmap P76 → P81 through end-2026.
"""

from __future__ import annotations

import json
import math
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Governance constants — MUST stay paper_only=True / diagnostic_only=True
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

ALLOWED_CLASSIFICATIONS = [
    "P76_HOME_PLUS_AWAY_125_SELECTED_FOR_2026_SHADOW_TRACKING",
    "P76_HOME_PLUS_AWAY_100_SELECTED_FOR_2026_SHADOW_TRACKING",
    "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA",
    "P76_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
    "P76_FAILED_VALIDATION",
]

PREDICTION_BOUNDARY = (
    "P76 is a diagnostic selection and planning exercise only. "
    "'Selected rule' means the preferred shadow-tracking rule for 2026 accumulation — "
    "NOT a production deployment, NOT a betting recommendation, NOT a market-edge claim. "
    "paper_only=True, diagnostic_only=True."
)

# Scorecard axis weights
AXIS_WEIGHTS = {
    "directional": 0.30,
    "calibration": 0.25,
    "coverage": 0.20,
    "stability_risk": 0.15,
    "future_readiness": 0.10,
}

# Finalist rule IDs
FINALIST_RULE_IDS = ["TIER_C_HOME_PLUS_AWAY_125", "TIER_C_HOME_PLUS_AWAY_100"]

# Minimum scorecard delta to declare a clear winner (otherwise dual retention)
MIN_WINNER_DELTA = 0.02

# ---------------------------------------------------------------------------
# Source artifact paths
# ---------------------------------------------------------------------------
PATHS = {
    "p75b_json": ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_json": ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_json": ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json",
    "p73_json": ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_json": ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
    "p72a_json": ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
}

OUTPUT_JSON = ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json"
OUTPUT_REPORT = ROOT / "report/p76_corrected_tier_c_final_rule_selection_20260526.md"
PLAN_REPORT = ROOT / "00-BettingPlan/20260526/p76_corrected_tier_c_final_rule_selection_20260526.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Step 1 — Verify P75B finalist metrics
# ---------------------------------------------------------------------------
def step1_verify_p75b_finalists(p75b: dict) -> dict[str, dict]:
    """Extract and verify finalist metrics from P75B summary."""
    scorecard = p75b.get("step4_scorecard", {})
    scores = scorecard.get("scores", [])
    uncalibrated = p75b.get("step2_uncalibrated", {})

    # Coverage fractions from P75A (hardcoded from P75A validated output)
    coverage_fractions = {
        "TIER_C_HOME_PLUS_AWAY_125": 0.59,
        "TIER_C_HOME_PLUS_AWAY_100": 0.70,
    }
    # Monthly stability from P75A
    monthly_stabilities = {
        "TIER_C_HOME_PLUS_AWAY_125": "MODERATE",
        "TIER_C_HOME_PLUS_AWAY_100": "MODERATE",
    }
    # Cal method robustness: temperature > platt > isotonic for small-sample robustness
    cal_method_robustness = {
        "temperature": 0.80,
        "platt": 0.75,
        "isotonic": 0.60,
        "isotonic_kfold5": 0.55,
        "no_calibration": 0.40,
    }

    finalists: dict[str, dict] = {}
    for entry in scores:
        rule_id = entry.get("rule_id", "")
        if rule_id not in FINALIST_RULE_IDS:
            continue
        uncal = uncalibrated.get(rule_id, {})
        finalists[rule_id] = {
            "rule_id": rule_id,
            "n": entry["n"],
            "hit_rate": entry["hit_rate"],
            "hit_delta_vs_baseline": entry["hit_delta_vs_baseline"],
            "auc": entry["auc"],
            "cal_brier": entry["best_cal_brier"],
            "cal_ece": entry["best_cal_ece"],
            "cal_method": entry["best_cal_method"],
            "cal_method_robustness": cal_method_robustness.get(entry["best_cal_method"], 0.60),
            "cal_status": entry["cal_status"],
            "caveats": entry.get("caveats", []),
            "coverage_fraction": coverage_fractions.get(rule_id, 0.5),
            "monthly_stability": monthly_stabilities.get(rule_id, "MODERATE"),
            "hit_rate_ci_95": uncal.get("hit_rate_ci_95", []),
        }

    return finalists


# ---------------------------------------------------------------------------
# Step 2 — Weighted scorecard
# ---------------------------------------------------------------------------
def _directional_score(m: dict) -> tuple[float, dict]:
    """30% weight — AUC and hit_delta vs baseline."""
    auc_score = _clamp((m["auc"] - 0.50) / 0.15)           # [0.50, 0.65] → [0, 1]
    hit_delta_score = _clamp(m["hit_delta_vs_baseline"] / 0.10)  # [0, 0.10] → [0, 1]
    axis = (auc_score + hit_delta_score) / 2.0
    return axis, {"auc_score": round(auc_score, 4), "hit_delta_score": round(hit_delta_score, 4)}


def _calibration_score(m: dict) -> tuple[float, dict]:
    """25% weight — cal_brier and cal_ece (lower is better)."""
    brier_score = _clamp(1.0 - (m["cal_brier"] - 0.20) / 0.05)   # [0.20, 0.25] → [1, 0]
    ece_score = _clamp(1.0 - m["cal_ece"] / 0.15)                  # [0, 0.15] → [1, 0]
    axis = (brier_score + ece_score) / 2.0
    return axis, {"brier_score": round(brier_score, 4), "ece_score": round(ece_score, 4)}


def _coverage_score(m: dict) -> tuple[float, dict]:
    """20% weight — sample size n and coverage fraction."""
    n_score = _clamp(m["n"] / 400.0)
    cov_score = _clamp(m["coverage_fraction"])
    axis = (n_score + cov_score) / 2.0
    return axis, {"n_score": round(n_score, 4), "cov_score": round(cov_score, 4)}


def _stability_risk_score(m: dict) -> tuple[float, dict]:
    """15% weight — no severe caveats + monthly stability."""
    caveat_score = 0.80 if not m["caveats"] else 0.40
    stability_map = {"STABLE": 1.00, "MODERATE": 0.70, "UNSTABLE": 0.30}
    stab_score = stability_map.get(m["monthly_stability"], 0.50)
    axis = (caveat_score + stab_score) / 2.0
    return axis, {"caveat_score": round(caveat_score, 4), "stab_score": round(stab_score, 4)}


def _future_readiness_score(m: dict) -> tuple[float, dict]:
    """10% weight — AUC quality + calibration method robustness."""
    auc_score = _clamp((m["auc"] - 0.50) / 0.15)
    method_robustness = m["cal_method_robustness"]
    axis = (auc_score + method_robustness) / 2.0
    return axis, {"auc_score": round(auc_score, 4), "method_robustness": round(method_robustness, 4)}


def step2_build_scorecard(finalists: dict[str, dict]) -> dict:
    """Compute weighted scorecard for each finalist rule."""
    scorecard: dict[str, Any] = {}

    for rule_id, m in finalists.items():
        dir_score, dir_detail = _directional_score(m)
        cal_score, cal_detail = _calibration_score(m)
        cov_score, cov_detail = _coverage_score(m)
        risk_score, risk_detail = _stability_risk_score(m)
        fut_score, fut_detail = _future_readiness_score(m)

        weighted_total = (
            dir_score * AXIS_WEIGHTS["directional"]
            + cal_score * AXIS_WEIGHTS["calibration"]
            + cov_score * AXIS_WEIGHTS["coverage"]
            + risk_score * AXIS_WEIGHTS["stability_risk"]
            + fut_score * AXIS_WEIGHTS["future_readiness"]
        )

        scorecard[rule_id] = {
            "rule_id": rule_id,
            "axes": {
                "directional": {
                    "raw_score": round(dir_score, 4),
                    "weight": AXIS_WEIGHTS["directional"],
                    "weighted": round(dir_score * AXIS_WEIGHTS["directional"], 4),
                    "detail": dir_detail,
                },
                "calibration": {
                    "raw_score": round(cal_score, 4),
                    "weight": AXIS_WEIGHTS["calibration"],
                    "weighted": round(cal_score * AXIS_WEIGHTS["calibration"], 4),
                    "detail": cal_detail,
                },
                "coverage": {
                    "raw_score": round(cov_score, 4),
                    "weight": AXIS_WEIGHTS["coverage"],
                    "weighted": round(cov_score * AXIS_WEIGHTS["coverage"], 4),
                    "detail": cov_detail,
                },
                "stability_risk": {
                    "raw_score": round(risk_score, 4),
                    "weight": AXIS_WEIGHTS["stability_risk"],
                    "weighted": round(risk_score * AXIS_WEIGHTS["stability_risk"], 4),
                    "detail": risk_detail,
                },
                "future_readiness": {
                    "raw_score": round(fut_score, 4),
                    "weight": AXIS_WEIGHTS["future_readiness"],
                    "weighted": round(fut_score * AXIS_WEIGHTS["future_readiness"], 4),
                    "detail": fut_detail,
                },
            },
            "weighted_total": round(weighted_total, 4),
        }

    return scorecard


# ---------------------------------------------------------------------------
# Step 3 — Tie-break decision
# ---------------------------------------------------------------------------
def step3_decision(
    scorecard: dict[str, dict],
    finalists: dict[str, dict],
) -> dict:
    """Decide: select winner or retain dual finalists."""
    r125 = "TIER_C_HOME_PLUS_AWAY_125"
    r100 = "TIER_C_HOME_PLUS_AWAY_100"

    score_125 = scorecard[r125]["weighted_total"]
    score_100 = scorecard[r100]["weighted_total"]
    delta = abs(score_125 - score_100)

    if delta >= MIN_WINNER_DELTA:
        winner = r125 if score_125 > score_100 else r100
        shadow = r100 if winner == r125 else r125
        classification = (
            "P76_HOME_PLUS_AWAY_125_SELECTED_FOR_2026_SHADOW_TRACKING"
            if winner == r125
            else "P76_HOME_PLUS_AWAY_100_SELECTED_FOR_2026_SHADOW_TRACKING"
        )
    else:
        winner = None
        shadow = None
        classification = "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA"

    # Per-axis wins
    axis_wins: dict[str, str] = {}
    for axis in AXIS_WEIGHTS:
        s125 = scorecard[r125]["axes"][axis]["raw_score"]
        s100 = scorecard[r100]["axes"][axis]["raw_score"]
        if abs(s125 - s100) < 0.001:
            axis_wins[axis] = "TIE"
        elif s125 > s100:
            axis_wins[axis] = r125
        else:
            axis_wins[axis] = r100

    return {
        "classification": classification,
        "score_125": score_125,
        "score_100": score_100,
        "score_delta": round(delta, 4),
        "winner": winner,
        "shadow_rule": shadow,
        "dual_finalists": winner is None,
        "axis_wins": axis_wins,
        "decision_reason": _build_decision_reason(winner, delta, score_125, score_100, axis_wins),
    }


def _build_decision_reason(winner, delta, score_125, score_100, axis_wins) -> str:
    r125 = "TIER_C_HOME_PLUS_AWAY_125"
    r100 = "TIER_C_HOME_PLUS_AWAY_100"
    if winner is None:
        wins_125 = [ax for ax, w in axis_wins.items() if w == r125]
        wins_100 = [ax for ax, w in axis_wins.items() if w == r100]
        return (
            f"Score delta {delta:.4f} < threshold {MIN_WINNER_DELTA}. "
            f"HOME_PLUS_AWAY_125 wins axes: {wins_125} (score={score_125:.4f}); "
            f"HOME_PLUS_AWAY_100 wins axes: {wins_100} (score={score_100:.4f}). "
            "Dual finalists retained pending 2026 live accumulation data."
        )
    loser = r100 if winner == r125 else r125
    loser_score = score_100 if winner == r125 else score_125
    return (
        f"{winner} selected (score={max(score_125, score_100):.4f}) over {loser} "
        f"(score={loser_score:.4f}) by margin {delta:.4f} >= threshold {MIN_WINNER_DELTA}."
    )


# ---------------------------------------------------------------------------
# Step 4 — 2026 Accumulation Plan
# ---------------------------------------------------------------------------
def step4_accumulation_plan(decision: dict, finalists: dict[str, dict]) -> dict:
    """Define 2026 live accumulation plan."""
    r125 = "TIER_C_HOME_PLUS_AWAY_125"
    r100 = "TIER_C_HOME_PLUS_AWAY_100"

    if decision["winner"] is not None:
        primary_rule = decision["winner"]
        shadow_rules = [decision["shadow_rule"]] if decision["shadow_rule"] else []
    else:
        primary_rule = r125   # by default track 125 as primary if dual-retained
        shadow_rules = [r100]

    # Stop-loss criteria for primary rule (rolling 100-game window)
    stop_criteria = {
        "rolling_window_games": 100,
        "hit_rate_floor": 0.55,
        "description": (
            "If rolling 100-game hit_rate falls below 0.55, halt primary rule tracking "
            "and escalate to P_REVIEW phase."
        ),
    }

    # Tier B growth criteria (from P73B: need n>=200 for P78 analysis)
    tier_b_threshold = {
        "min_n": 200,
        "tier_b_rule": "TIER_B_ABS_DELTA_025_050",
        "expected_reach_month": "2026-09",  # approximate
        "description": (
            "Tier B (|sp_fip_delta| 0.25–0.50) requires n>=200 before P78 full analysis. "
            "Currently tracking monthly accumulation since 2026 regular season start."
        ),
    }

    # Monthly cadence
    monthly_cadence = [
        {"month": "2026-06", "action": "First mid-season check-in (P77). Collect Tier C 2026 games."},
        {"month": "2026-07", "action": "Tier B count check. Rolling accuracy monitor."},
        {"month": "2026-08", "action": "Mid-season stability review. Adjust shadow rule if needed."},
        {"month": "2026-09", "action": "P78 trigger: if Tier B n>=200, run sample expansion analysis."},
        {"month": "2026-10", "action": "End-season consolidation. Final 2026 accuracy report."},
        {"month": "2026-11", "action": "P80 trigger: if odds API key acquired, run market-edge analysis."},
    ]

    # Market-edge resume criteria
    market_edge_resume = {
        "required_condition": "THE_ODDS_API_KEY acquired AND historical odds for 2025-2026 available",
        "minimum_odds_snapshots": 4,
        "minimum_pregame_hours_before_game": 3,
        "status": "DEFERRED",
        "description": (
            "Market-edge (CLV/EV) analysis deferred until external odds provider key available. "
            "No live API calls in current pipeline."
        ),
    }

    return {
        "primary_rule": primary_rule,
        "shadow_rules": shadow_rules,
        "monthly_cadence": monthly_cadence,
        "tier_b_threshold": tier_b_threshold,
        "stop_criteria": stop_criteria,
        "market_edge_resume": market_edge_resume,
        "accumulation_start": "2026-04-01",
        "accumulation_end_target": "2026-10-31",
    }


# ---------------------------------------------------------------------------
# Step 5 — End-2026 Roadmap (P76 → P81)
# ---------------------------------------------------------------------------
def step5_roadmap() -> list[dict]:
    """Document prediction-only research roadmap P76 → P81."""
    return [
        {
            "phase": "P76",
            "name": "Corrected Tier C Final Rule Selection + 2026 Accumulation Plan",
            "status": "CURRENT",
            "date_target": "2026-05-26",
            "goal": "Tie-break HOME_PLUS_AWAY_125 vs HOME_PLUS_AWAY_100; define accumulation plan.",
            "output": "Selected rule for shadow tracking; 2026 monthly cadence defined.",
            "gate": "Scorecard delta >= 0.02 for selection; else dual retention.",
        },
        {
            "phase": "P77",
            "name": "2026 Mid-Season Check-in (Tier C Live Accumulation)",
            "status": "PLANNED",
            "date_target": "2026-06-30",
            "goal": "First live accuracy check on primary selected rule using 2026 season games.",
            "output": "2026 hit_rate vs 2025 baseline; rolling accuracy plot; Tier B count update.",
            "gate": "n>=30 games in 2026 season. Rolling hit_rate > 0.55.",
        },
        {
            "phase": "P78",
            "name": "Tier B Sample Expansion Analysis",
            "status": "PLANNED",
            "date_target": "2026-09-30",
            "goal": "Full Tier B (|sp_fip_delta| 0.25–0.50) analysis when n>=200.",
            "output": "Tier B operational gate result; comparison to Tier C.",
            "gate": "Tier B n>=200 confirmed by P77 accumulation.",
        },
        {
            "phase": "P79",
            "name": "Combined Tier Analysis (Tier B + Tier C)",
            "status": "PLANNED",
            "date_target": "2026-10-31",
            "goal": "Evaluate combined Tier B + Tier C rule vs separate-tier strategy.",
            "output": "Combined vs separate tier comparison; recommend optimal tier configuration.",
            "gate": "Both Tier B and Tier C have n>=200 in 2026 data.",
        },
        {
            "phase": "P80",
            "name": "Market-Edge Integration (Odds-Lane)",
            "status": "DEFERRED",
            "date_target": "2026-11-30",
            "goal": "Integrate historical/live odds for CLV and edge estimation.",
            "output": "CLV correlation with prediction accuracy; EV distribution analysis.",
            "gate": "Requires THE_ODDS_API_KEY and >=100 games with pregame odds.",
        },
        {
            "phase": "P81",
            "name": "Strategy Finalization + Research Archive",
            "status": "PLANNED",
            "date_target": "2026-12-31",
            "goal": "Finalize optimal prediction rule; archive research chain P72A→P81.",
            "output": "Final recommended rule; full chain report; deployment readiness checklist.",
            "gate": "All prior phases complete; paper_only=True maintained throughout.",
        },
    ]


# ---------------------------------------------------------------------------
# Forbidden phrase scan
# ---------------------------------------------------------------------------
FORBIDDEN_PHRASES = [
    "expected_value",
    "closing_line_value",
    '"clv_calculated": true',
    "kelly fraction",
    '"kelly_deploy_allowed": true',
    '"production_ready": true',
    "profitability confirmed",
    '"real_bet_allowed": true',
    '"champion_replacement_allowed": true',
]


def _scan_forbidden(text: str) -> dict:
    violations = [p for p in FORBIDDEN_PHRASES if p.lower() in text.lower()]
    return {"violations": violations, "result": "CLEAN" if not violations else "VIOLATION_FOUND"}


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def _generate_report(result: dict) -> str:
    lines: list[str] = []
    a = lines.append

    finalists = result["step1_finalists"]
    scorecard = result["step2_scorecard"]
    decision = result["step3_decision"]
    plan = result["step4_accumulation_plan"]
    roadmap = result["step5_roadmap"]

    a(f"# P76 — Corrected Tier C Final Rule Selection + 2026 Accumulation Plan")
    a(f"**Date:** 2026-05-26  ")
    a(f"**Phase:** P76  ")
    a(f"**Classification:** `{decision['classification']}`  ")
    a(f"**Mode:** paper_only=True | diagnostic_only=True | NO_REAL_BET=True")
    a("")
    a("---")
    a("")
    a("## Executive Summary")
    a("")
    if decision["winner"]:
        winner_m = finalists[decision["winner"]]
        a(
            f"`{decision['winner']}` selected as primary rule for 2026 shadow tracking "
            f"(scorecard score={decision['score_125'] if '125' in decision['winner'] else decision['score_100']:.4f}, "
            f"delta={decision['score_delta']:.4f} >= {MIN_WINNER_DELTA}). "
            f"Hit={winner_m['hit_rate']:.3f}, AUC={winner_m['auc']:.3f}, "
            f"cal_brier={winner_m['cal_brier']:.4f}, cal_ece={winner_m['cal_ece']:.4f}."
        )
    else:
        a(
            f"Scorecard delta = {decision['score_delta']:.4f} < threshold {MIN_WINNER_DELTA} — "
            "margin is too narrow to declare a clear winner. "
            "**Dual finalists retained** until 2026 live accumulation provides discriminating evidence. "
            f"HOME_PLUS_AWAY_125 score={decision['score_125']:.4f}; "
            f"HOME_PLUS_AWAY_100 score={decision['score_100']:.4f}."
        )

    a("")
    a("---")
    a("")
    a("## Finalist Metrics (from P75B)")
    a("")
    a("| Rule | n | Hit | AUC | Cal Brier | Cal ECE | Cal Method | Coverage | Status |")
    a("|---|---:|---:|---:|---:|---:|---|---:|---|")
    for rule_id, m in finalists.items():
        cal_status = m.get("cal_status", "—")
        a(
            f"| `{rule_id}` | {m['n']} | {m['hit_rate']:.3f} | {m['auc']:.3f} | "
            f"{m['cal_brier']:.4f} | {m['cal_ece']:.4f} | {m['cal_method']} | "
            f"{m['coverage_fraction']:.2f} | **{cal_status}** |"
        )

    a("")
    a("---")
    a("")
    a("## Weighted Scorecard")
    a("")
    a(f"Axis weights: Directional={AXIS_WEIGHTS['directional']:.0%} | "
      f"Calibration={AXIS_WEIGHTS['calibration']:.0%} | "
      f"Coverage={AXIS_WEIGHTS['coverage']:.0%} | "
      f"Stability/Risk={AXIS_WEIGHTS['stability_risk']:.0%} | "
      f"Future Readiness={AXIS_WEIGHTS['future_readiness']:.0%}")
    a("")
    a("| Axis | Weight | HOME_PLUS_AWAY_125 | HOME_PLUS_AWAY_100 | Winner |")
    a("|---|---:|---:|---:|---|")
    for axis_name, weight in AXIS_WEIGHTS.items():
        s125 = scorecard["TIER_C_HOME_PLUS_AWAY_125"]["axes"][axis_name]["raw_score"]
        s100 = scorecard["TIER_C_HOME_PLUS_AWAY_100"]["axes"][axis_name]["raw_score"]
        winner_axis = decision["axis_wins"].get(axis_name, "—")
        if winner_axis == "TIER_C_HOME_PLUS_AWAY_125":
            winner_label = "125 ✓"
        elif winner_axis == "TIER_C_HOME_PLUS_AWAY_100":
            winner_label = "100 ✓"
        else:
            winner_label = "TIE"
        a(f"| {axis_name} | {weight:.0%} | {s125:.3f} | {s100:.3f} | {winner_label} |")
    a(f"| **TOTAL** | **100%** | **{decision['score_125']:.4f}** | **{decision['score_100']:.4f}** | "
      f"**{'DUAL' if not decision['winner'] else ('125' if '125' in decision['winner'] else '100')}** |")

    a("")
    a("---")
    a("")
    a("## Decision")
    a("")
    a(f"> {decision['decision_reason']}")
    a("")
    a(f"**Classification:** `{decision['classification']}`")

    a("")
    a("---")
    a("")
    a("## 2026 Accumulation Plan")
    a("")
    a(f"- **Primary rule:** `{plan['primary_rule']}`")
    shadow_str = ", ".join(f"`{r}`" for r in plan["shadow_rules"]) if plan["shadow_rules"] else "None"
    a(f"- **Shadow rule(s):** {shadow_str}")
    a(f"- **Accumulation window:** {plan['accumulation_start']} → {plan['accumulation_end_target']}")
    a(f"- **Stop criteria:** Rolling {plan['stop_criteria']['rolling_window_games']}-game hit_rate < "
      f"{plan['stop_criteria']['hit_rate_floor']} → halt + P_REVIEW")
    a(f"- **Tier B trigger:** n >= {plan['tier_b_threshold']['min_n']} (expected ~{plan['tier_b_threshold']['expected_reach_month']})")
    a(f"- **Market-edge:** {plan['market_edge_resume']['status']} — {plan['market_edge_resume']['required_condition']}")
    a("")
    a("### Monthly Cadence")
    a("")
    a("| Month | Action |")
    a("|---|---|")
    for item in plan["monthly_cadence"]:
        a(f"| {item['month']} | {item['action']} |")

    a("")
    a("---")
    a("")
    a("## Research Roadmap P76 → P81")
    a("")
    a("| Phase | Name | Target | Gate | Status |")
    a("|---|---|---|---|---|")
    for phase in roadmap:
        a(
            f"| **{phase['phase']}** | {phase['name']} | {phase['date_target']} | "
            f"{phase['gate'][:60]}... | {phase['status']} |"
        )

    a("")
    a("---")
    a("")
    a("*paper_only=True | diagnostic_only=True | NO_REAL_BET=True*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run_p76() -> dict:
    # Load source artifacts
    missing = [k for k, p in PATHS.items() if not p.exists()]
    if missing:
        result = {
            "phase": "P76",
            "date": str(date.today()),
            "p76_classification": "P76_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
            "missing_artifacts": missing,
            "governance": GOVERNANCE,
        }
        return result

    p75b = _load_json(PATHS["p75b_json"])
    p75a = _load_json(PATHS["p75a_json"])

    # Step 1
    finalists = step1_verify_p75b_finalists(p75b)

    # Step 2
    scorecard = step2_build_scorecard(finalists)

    # Step 3
    decision = step3_decision(scorecard, finalists)

    # Step 4
    plan = step4_accumulation_plan(decision, finalists)

    # Step 5
    roadmap = step5_roadmap()

    result: dict[str, Any] = {
        "phase": "P76",
        "date": "2026-05-26",
        "p76_classification": decision["classification"],
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "governance": GOVERNANCE,
        "prediction_boundary": PREDICTION_BOUNDARY,
        "source_artifacts": {k: str(p) for k, p in PATHS.items()},
        "step1_finalists": finalists,
        "step2_scorecard": scorecard,
        "step3_decision": decision,
        "step4_accumulation_plan": plan,
        "step5_roadmap": roadmap,
        "axis_weights": AXIS_WEIGHTS,
        "min_winner_delta": MIN_WINNER_DELTA,
    }

    # Forbidden scan on JSON output
    result_text = json.dumps(result, indent=2)
    scan = _scan_forbidden(result_text)
    result["forbidden_scan"] = scan

    return result


def main() -> None:
    result = run_p76()
    classification = result.get("p76_classification", "UNKNOWN")
    print(f"[P76] Classification: {classification}")

    # Write JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[P76] JSON → {OUTPUT_JSON}")

    # Write reports
    if classification not in ("P76_BLOCKED_BY_MISSING_SOURCE_ARTIFACT", "P76_FAILED_VALIDATION"):
        report_text = _generate_report(result)

        OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_REPORT, "w") as f:
            f.write(report_text)
        print(f"[P76] Report → {OUTPUT_REPORT}")

        PLAN_REPORT.parent.mkdir(parents=True, exist_ok=True)
        with open(PLAN_REPORT, "w") as f:
            f.write(report_text)
        print(f"[P76] Plan report → {PLAN_REPORT}")

    scan = result.get("forbidden_scan", {})
    if scan.get("result") != "CLEAN":
        print(f"[P76] FORBIDDEN PHRASE VIOLATION: {scan.get('violations')}")
        sys.exit(1)
    else:
        print("[P76] Forbidden scan: CLEAN")

    print("[P76] Done.")


if __name__ == "__main__":
    main()
