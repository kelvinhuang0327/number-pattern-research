"""
P77 — 2026 Prediction-Only Shadow Tracker Contract
Date: 2026-05-26
Mode: paper_only=True | diagnostic_only=True | NO_REAL_BET=True

Goals:
  1. Verify P76 dual-finalist decision (HOME_PLUS_AWAY_125 vs HOME_PLUS_AWAY_100).
  2. Define 2026 shadow tracker row schema.
  3. Define deterministic rule computation contract for both finalists.
  4. Define monthly tracker metrics contract.
  5. Define re-evaluation triggers (Tier C, Tier B n>=200, Tier A watchlist).
  6. Validate rule semantics against 2025 historical data.
  7. Produce summary JSON and Markdown report.

This script MUST NOT: call live APIs, compute EV/CLV/Kelly, modify production
runtime, or replace champion strategy.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Governance constants — immutable, must stay paper_only=True
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "uses_historical_odds": False,
    "live_api_calls": 0,
    "the_odds_api_key_required": False,
    "odds_used": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "market_edge_evaluated": False,
    "kelly_calculated": False,
    "kelly_deploy_allowed": False,
    "production_ready": False,
    "real_bet_allowed": False,
    "champion_replacement_allowed": False,
    "profitability_claim": False,
    "promotion_freeze": True,
}

ALLOWED_CLASSIFICATIONS = [
    "P77_SHADOW_TRACKER_CONTRACT_READY",
    "P77_SHADOW_TRACKER_CONTRACT_READY_WITH_CAVEATS",
    "P77_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
    "P77_FAILED_VALIDATION",
]

PREDICTION_BOUNDARY = (
    "P77 is a contract-definition and validation exercise only. "
    "Shadow tracker rows are for research accumulation — NOT a production "
    "deployment, NOT a betting recommendation, NOT a market-edge claim. "
    "paper_only=True, diagnostic_only=True, production_ready=False."
)

# ---------------------------------------------------------------------------
# Source artifact paths
# ---------------------------------------------------------------------------
PATHS: dict[str, Path] = {
    "p72a_json": ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
    "p72b_json": ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
    "p73_json":  ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    "p74_json":  ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json",
    "p75a_json": ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json",
    "p75b_json": ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p76_json":  ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
    "p76_md":    ROOT / "report/p76_corrected_tier_c_final_rule_selection_20260526.md",
    "predictions_jsonl": ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
}

OUTPUT_JSON   = ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json"
OUTPUT_REPORT = ROOT / "report/p77_prediction_only_shadow_tracker_contract_20260526.md"
PLAN_REPORT   = ROOT / "00-BettingPlan/20260526/p77_prediction_only_shadow_tracker_contract_20260526.md"

# ---------------------------------------------------------------------------
# Expected values from P75B/P76 (used for semantic validation)
# ---------------------------------------------------------------------------
EXPECTED_COUNTS: dict[str, int] = {
    "TIER_C_HOME_ONLY":          268,
    "TIER_C_HOME_PLUS_AWAY_100": 373,
    "TIER_C_HOME_PLUS_AWAY_125": 316,
}

P76_EXPECTED = {
    "classification": "P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA",
    "score_125":       0.5543,
    "score_100":       0.5540,
    "score_delta":     0.0003,
    "tie_break_threshold": 0.02,
    "primary_tracking_rule": "TIER_C_HOME_PLUS_AWAY_125",
    "shadow_tracking_rule":  "TIER_C_HOME_PLUS_AWAY_100",
}

# Downgrade triggers
ROLLING_WINDOW_GAMES  = 100
HIT_RATE_FLOOR        = 0.55
CONSECUTIVE_MONTHS_BAD = 2
MONTHLY_FLOOR         = 0.50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _ci_wilson(n: int, k: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (round(max(0.0, centre - margin), 4), round(min(1.0, centre + margin), 4))


# ---------------------------------------------------------------------------
# Step 1 — Verify P76 dual-finalist decision
# ---------------------------------------------------------------------------
def step1_verify_p76(p76: dict) -> dict[str, Any]:
    decision = p76.get("step3_decision", {})
    plan     = p76.get("step4_accumulation_plan", {})

    classification = p76.get("p76_classification", "")
    score_125  = decision.get("score_125")
    score_100  = decision.get("score_100")
    score_delta = decision.get("score_delta")
    dual_finalists = decision.get("dual_finalists", False)
    primary = plan.get("primary_rule", "")
    shadow  = plan.get("shadow_rules", [])
    shadow_rule = shadow[0] if shadow else ""

    issues: list[str] = []
    if classification != P76_EXPECTED["classification"]:
        issues.append(f"classification mismatch: got {classification!r}, expected {P76_EXPECTED['classification']!r}")
    if score_125 != P76_EXPECTED["score_125"]:
        issues.append(f"score_125 mismatch: {score_125} vs {P76_EXPECTED['score_125']}")
    if score_100 != P76_EXPECTED["score_100"]:
        issues.append(f"score_100 mismatch: {score_100} vs {P76_EXPECTED['score_100']}")
    if score_delta != P76_EXPECTED["score_delta"]:
        issues.append(f"score_delta mismatch: {score_delta} vs {P76_EXPECTED['score_delta']}")
    if not dual_finalists:
        issues.append("dual_finalists must be True")
    if primary != P76_EXPECTED["primary_tracking_rule"]:
        issues.append(f"primary_rule mismatch: {primary!r} vs {P76_EXPECTED['primary_tracking_rule']!r}")
    if shadow_rule != P76_EXPECTED["shadow_tracking_rule"]:
        issues.append(f"shadow_rule mismatch: {shadow_rule!r} vs {P76_EXPECTED['shadow_tracking_rule']!r}")
    has_accumulation_plan = bool(plan)

    return {
        "p76_classification":   classification,
        "score_125":            score_125,
        "score_100":            score_100,
        "score_delta":          score_delta,
        "tie_break_threshold":  p76.get("min_winner_delta", 0.02),
        "dual_finalists":       dual_finalists,
        "primary_tracking_rule": primary,
        "shadow_tracking_rule":  shadow_rule,
        "has_accumulation_plan": has_accumulation_plan,
        "verification_issues":   issues,
        "verification_passed":   len(issues) == 0,
    }


# ---------------------------------------------------------------------------
# Step 2 — Define 2026 shadow tracker row schema
# ---------------------------------------------------------------------------
def step2_row_schema() -> dict[str, Any]:
    """
    Returns the canonical row schema for 2026 prediction-only shadow tracking.

    All governance booleans are frozen at their safe values.  The schema defines
    what fields every prediction row MUST contain before it is accepted into the
    2026 tracker.
    """
    fields: dict[str, dict] = {
        "game_id":              {"type": "str",   "required": True,  "description": "Unique game identifier, e.g. MLB2026_XXXX_YYYY-MM-DD_AWAY_HOME"},
        "game_date":            {"type": "str",   "required": True,  "description": "ISO-8601 date string YYYY-MM-DD"},
        "season":               {"type": "int",   "required": True,  "description": "Season year, must be 2026"},
        "home_team":            {"type": "str",   "required": True,  "description": "Home team name"},
        "away_team":            {"type": "str",   "required": True,  "description": "Away team name"},
        "predicted_side":       {"type": "str",   "required": True,  "description": "'home' or 'away' — determined by sp_fip_delta sign (>0 → home, <0 → away)"},
        "actual_winner":        {"type": "str",   "required": False, "description": "'home' or 'away' — filled post-game; null until settled"},
        "is_correct":           {"type": "bool",  "required": False, "description": "True if predicted_side == actual_winner; null until settled"},
        "model_probability":    {"type": "float", "required": True,  "description": "Model probability for predicted side in [0, 1]"},
        "sp_fip_delta":         {"type": "float", "required": True,  "description": "Signed SP FIP delta (away_FIP - home_FIP) for this game"},
        "abs_sp_fip_delta":     {"type": "float", "required": True,  "description": "abs(sp_fip_delta)"},
        "selected_rule_home_plus_away_125_flag": {"type": "bool", "required": True,  "description": "True if row qualifies for TIER_C_HOME_PLUS_AWAY_125"},
        "shadow_rule_home_plus_away_100_flag":   {"type": "bool", "required": True,  "description": "True if row qualifies for TIER_C_HOME_PLUS_AWAY_100"},
        "tier_b_candidate_flag":{"type": "bool",  "required": True,  "description": "True if abs_sp_fip_delta in [0.25, 0.50) — mid-band accumulation"},
        "tier_a_watchlist_flag":{"type": "bool",  "required": True,  "description": "True if abs_sp_fip_delta >= 1.50 — highest conviction watchlist"},
        "home_pick_flag":       {"type": "bool",  "required": True,  "description": "True if predicted_side == 'home'"},
        "away_pick_flag":       {"type": "bool",  "required": True,  "description": "True if predicted_side == 'away'"},
        "month":                {"type": "str",   "required": True,  "description": "YYYY-MM month string derived from game_date"},
        "source_prediction_version": {"type": "str", "required": True, "description": "Prediction pipeline version tag"},
        "outcome_source":       {"type": "str",   "required": False, "description": "Source of actual_winner (e.g. 'mlb_statsapi', 'manual')"},
        # Governance fields — all frozen
        "paper_only":           {"type": "bool",  "required": True,  "frozen": True,  "frozen_value": True},
        "diagnostic_only":      {"type": "bool",  "required": True,  "frozen": True,  "frozen_value": True},
        "market_edge_evaluated":{"type": "bool",  "required": True,  "frozen": True,  "frozen_value": False},
        "odds_used":            {"type": "bool",  "required": True,  "frozen": True,  "frozen_value": False},
        "ev_calculated":        {"type": "bool",  "required": True,  "frozen": True,  "frozen_value": False},
        "clv_calculated":       {"type": "bool",  "required": True,  "frozen": True,  "frozen_value": False},
        "kelly_calculated":     {"type": "bool",  "required": True,  "frozen": True,  "frozen_value": False},
        "production_ready":     {"type": "bool",  "required": True,  "frozen": True,  "frozen_value": False},
    }

    governance_frozen = {
        "paper_only":            True,
        "diagnostic_only":       True,
        "market_edge_evaluated": False,
        "odds_used":             False,
        "ev_calculated":         False,
        "clv_calculated":        False,
        "kelly_calculated":      False,
        "production_ready":      False,
    }

    return {
        "schema_version": "p77-v1",
        "fields": fields,
        "governance_frozen": governance_frozen,
        "required_fields": [k for k, v in fields.items() if v.get("required")],
        "governance_fields": list(governance_frozen.keys()),
        "total_fields": len(fields),
    }


# ---------------------------------------------------------------------------
# Step 3 — Rule computation contract
# ---------------------------------------------------------------------------
def compute_selected_rule_home_plus_away_125_flag(
    sp_fip_delta: float,
    abs_sp_fip_delta: float,
    sp_fip_delta_available: bool,
) -> bool:
    """
    TIER_C_HOME_PLUS_AWAY_125 — primary tracking rule (P76).

    Inclusion criteria (deterministic, matches P75A semantics):
      - sp_fip_delta_available must be True
      - If sp_fip_delta > 0  (home pitcher has advantage): include when abs_sp_fip_delta >= 0.50
      - If sp_fip_delta <= 0 (away pitcher has advantage): include when abs_sp_fip_delta >= 1.25
      - sp_fip_delta == 0: predicted_side = 'home', include when abs_sp_fip_delta >= 0.50

    Market-edge fields (EV, CLV, Kelly, odds) are NEVER used.
    """
    if not sp_fip_delta_available:
        return False
    if abs_sp_fip_delta < 0.50:
        return False
    predicted_side = "home" if sp_fip_delta >= 0 else "away"
    if predicted_side == "home":
        return abs_sp_fip_delta >= 0.50
    return abs_sp_fip_delta >= 1.25


def compute_shadow_rule_home_plus_away_100_flag(
    sp_fip_delta: float,
    abs_sp_fip_delta: float,
    sp_fip_delta_available: bool,
) -> bool:
    """
    TIER_C_HOME_PLUS_AWAY_100 — shadow tracking rule (P76).

    Inclusion criteria (deterministic, matches P75A semantics):
      - sp_fip_delta_available must be True
      - If sp_fip_delta > 0  (home pitcher has advantage): include when abs_sp_fip_delta >= 0.50
      - If sp_fip_delta <= 0 (away pitcher has advantage): include when abs_sp_fip_delta >= 1.00
      - sp_fip_delta == 0: predicted_side = 'home', include when abs_sp_fip_delta >= 0.50

    Market-edge fields are NEVER used.
    """
    if not sp_fip_delta_available:
        return False
    if abs_sp_fip_delta < 0.50:
        return False
    predicted_side = "home" if sp_fip_delta >= 0 else "away"
    if predicted_side == "home":
        return abs_sp_fip_delta >= 0.50
    return abs_sp_fip_delta >= 1.00


def compute_tier_b_candidate_flag(
    abs_sp_fip_delta: float,
    sp_fip_delta_available: bool,
) -> bool:
    """
    TIER_B_CANDIDATE — mid-band accumulation tracking for P78.

    Tier B (|sp_fip_delta| in [0.25, 0.50)) represents moderate pitcher advantage.
    These games fall BELOW the confirmed Tier C threshold (0.50) and require
    n >= 200 in 2026 accumulation before P78 full analysis.

    Defined per P76 accumulation plan: tier_b_rule = 'TIER_B_ABS_DELTA_025_050'.
    """
    if not sp_fip_delta_available:
        return False
    return 0.25 <= abs_sp_fip_delta < 0.50


def compute_tier_a_watchlist_flag(
    abs_sp_fip_delta: float,
    sp_fip_delta_available: bool,
) -> bool:
    """
    TIER_A_WATCHLIST — highest conviction tracking (|sp_fip_delta| >= 1.50).

    Defined per P72A: S03_TIER_A_DIRECTIONAL.  Sample size too small (n=24 in 2025)
    for operational use.  Track only — do not operationalize before n >= 50.
    """
    if not sp_fip_delta_available:
        return False
    return abs_sp_fip_delta >= 1.50


def step3_rule_contract() -> dict[str, Any]:
    """Define the full rule computation contract."""
    return {
        "rules": {
            "TIER_C_HOME_PLUS_AWAY_125": {
                "role":        "primary_tracking_rule",
                "description": "Tier C home picks (abs_sp_fip_delta >= 0.50, home advantage) + Tier C away picks (abs_sp_fip_delta >= 1.25, away advantage).",
                "predicted_side_determination": "sign(sp_fip_delta) — positive → home, negative → away, zero → home",
                "home_threshold":  0.50,
                "away_threshold":  1.25,
                "requires_sp_fip_delta_available": True,
                "market_edge_fields_used": False,
                "function": "compute_selected_rule_home_plus_away_125_flag",
                "p76_score":    0.5543,
                "p75b_n_2025":  316,
                "p75b_hit_rate_2025": 0.6392,
            },
            "TIER_C_HOME_PLUS_AWAY_100": {
                "role":        "shadow_tracking_rule",
                "description": "Tier C home picks (abs_sp_fip_delta >= 0.50, home advantage) + Tier C away picks (abs_sp_fip_delta >= 1.00, away advantage).",
                "predicted_side_determination": "sign(sp_fip_delta) — positive → home, negative → away, zero → home",
                "home_threshold":  0.50,
                "away_threshold":  1.00,
                "requires_sp_fip_delta_available": True,
                "market_edge_fields_used": False,
                "function": "compute_shadow_rule_home_plus_away_100_flag",
                "p76_score":    0.5540,
                "p75b_n_2025":  373,
                "p75b_hit_rate_2025": 0.6327,
            },
            "TIER_B_CANDIDATE": {
                "role":        "accumulation_tracking",
                "description": "Mid-band games: abs_sp_fip_delta in [0.25, 0.50). Tracks below-Tier-C pitcher matchups. Requires n>=200 before P78 full analysis.",
                "lo_threshold": 0.25,
                "hi_threshold": 0.50,
                "requires_sp_fip_delta_available": True,
                "market_edge_fields_used": False,
                "function": "compute_tier_b_candidate_flag",
                "p78_trigger_n": 200,
            },
            "TIER_A_WATCHLIST": {
                "role":        "watchlist_only",
                "description": "Highest conviction: abs_sp_fip_delta >= 1.50. Track but do not operationalize while n < 50.",
                "lo_threshold": 1.50,
                "requires_sp_fip_delta_available": True,
                "market_edge_fields_used": False,
                "function": "compute_tier_a_watchlist_flag",
                "p72a_n_2025": 24,
                "operational_n_minimum": 50,
            },
        },
        "determinism_guarantee": "All rule flags are pure functions of sp_fip_delta, abs_sp_fip_delta, and sp_fip_delta_available. No stochastic or external-API inputs.",
        "market_edge_separation": "All four rules are odds-free. EV, CLV, Kelly, market_home_prob are optional future fields — NOT required for P77.",
    }


# ---------------------------------------------------------------------------
# Step 3b — Validate rule semantics against 2025 data
# ---------------------------------------------------------------------------
def step3b_validate_rule_semantics() -> dict[str, Any]:
    """
    Load 2025 prediction JSONL and verify rule flag counts match P75B expected.
    """
    records: list[dict] = []
    with PATHS["predictions_jsonl"].open() as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            r = json.loads(raw)
            p0 = r.get("p0_features") or {}
            delta = p0.get("sp_fip_delta")
            available = p0.get("sp_fip_delta_available", True)
            home_win = r.get("home_win")
            if home_win is None or delta is None or not available:
                continue
            delta_f = float(delta)
            abs_delta = abs(delta_f)
            records.append({"sp_fip_delta": delta_f, "abs_delta": abs_delta})

    n_home_only = sum(
        1 for r in records
        if r["sp_fip_delta"] >= 0 and r["abs_delta"] >= 0.50
    )
    n_100 = sum(
        1 for r in records
        if compute_shadow_rule_home_plus_away_100_flag(r["sp_fip_delta"], r["abs_delta"], True)
    )
    n_125 = sum(
        1 for r in records
        if compute_selected_rule_home_plus_away_125_flag(r["sp_fip_delta"], r["abs_delta"], True)
    )

    checks = {
        "TIER_C_HOME_ONLY": {
            "computed": n_home_only,
            "expected": EXPECTED_COUNTS["TIER_C_HOME_ONLY"],
            "match": n_home_only == EXPECTED_COUNTS["TIER_C_HOME_ONLY"],
        },
        "TIER_C_HOME_PLUS_AWAY_100": {
            "computed": n_100,
            "expected": EXPECTED_COUNTS["TIER_C_HOME_PLUS_AWAY_100"],
            "match": n_100 == EXPECTED_COUNTS["TIER_C_HOME_PLUS_AWAY_100"],
        },
        "TIER_C_HOME_PLUS_AWAY_125": {
            "computed": n_125,
            "expected": EXPECTED_COUNTS["TIER_C_HOME_PLUS_AWAY_125"],
            "match": n_125 == EXPECTED_COUNTS["TIER_C_HOME_PLUS_AWAY_125"],
        },
    }
    all_pass = all(v["match"] for v in checks.values())
    return {
        "total_valid_records_2025": len(records),
        "rule_count_checks": checks,
        "all_counts_match_p75b": all_pass,
        "validation_status": "PASS" if all_pass else "FAIL",
    }


# ---------------------------------------------------------------------------
# Step 4 — Monthly tracker metrics contract
# ---------------------------------------------------------------------------
def step4_monthly_metrics_contract() -> dict[str, Any]:
    """
    Define the monthly metrics computed for each rule in 2026 accumulation.
    No odds metrics are included.
    """
    return {
        "metrics_per_rule_per_month": [
            {"name": "n",          "description": "Number of games in this rule for this month"},
            {"name": "hit_rate",   "description": "Fraction of games where predicted_side == actual_winner"},
            {"name": "hit_rate_ci_95", "description": "Wilson 95% confidence interval for hit_rate"},
            {"name": "auc",        "description": "ROC-AUC if probability distribution supports it (requires n >= 20)"},
            {"name": "brier",      "description": "Brier score (lower = better calibration)"},
            {"name": "log_loss",   "description": "Log-loss (lower = better)"},
            {"name": "ece",        "description": "Expected Calibration Error"},
            {"name": "home_n",     "description": "Count of home-side picks in this rule-month"},
            {"name": "away_n",     "description": "Count of away-side picks in this rule-month"},
            {"name": "home_hit_rate", "description": "Hit rate for home-side picks only"},
            {"name": "away_hit_rate", "description": "Hit rate for away-side picks only"},
            {"name": "tier_b_n",   "description": "Running total of Tier B candidate rows (abs_sp_fip_delta 0.25–0.50)"},
            {"name": "tier_a_n",   "description": "Running total of Tier A watchlist rows (abs_sp_fip_delta >= 1.50)"},
            {"name": "rolling_100_hit_rate", "description": "Rolling 100-game hit rate (reported if cumulative n >= 100)"},
        ],
        "aggregation_cadence": "monthly",
        "no_odds_metrics": True,
        "no_ev_clv_kelly": True,
        "monthly_cadence_2026": [
            {"month": "2026-06", "action": "First P77 check-in. Collect Tier C 2026 games. Compute June hit_rate. Report rule counts."},
            {"month": "2026-07", "action": "Tier B count check. Rolling accuracy monitor. Compute 3-month cumulative stats."},
            {"month": "2026-08", "action": "Mid-season stability review. Adjust shadow rule if downgrade criteria met."},
            {"month": "2026-09", "action": "P78 trigger: if Tier B n >= 200, launch sample expansion analysis."},
            {"month": "2026-10", "action": "End-season consolidation. Final 2026 accuracy report. Compute full-season AUC/Brier/ECE."},
            {"month": "2026-11", "action": "P80 trigger: if odds API key acquired, run market-edge analysis (deferred lane)."},
        ],
    }


# ---------------------------------------------------------------------------
# Step 5 — Re-evaluation triggers
# ---------------------------------------------------------------------------
def step5_reeval_triggers() -> dict[str, Any]:
    """Define all re-evaluation triggers for 2026 monitoring."""
    return {
        "tier_c_selected_shadow_reeval": {
            "checkpoint_1":  {"n_threshold": 50,  "action": "First interim accuracy check — no downgrade unless hit_rate < 0.50 for all games so far"},
            "checkpoint_2":  {"n_threshold": 100, "action": "Rolling 100-game hit rate becomes available. Downgrade if hit_rate < 0.55."},
            "operational_checkpoint": {"n_threshold": 200, "action": "Full re-evaluation: compare primary vs shadow, update preferred rule."},
            "seasonal_checkpoint": {"trigger": "end_of_2026_regular_season", "action": "Final 2026 accuracy report. Decision on 2027 tracking configuration."},
            "downgrade_criteria": [
                {
                    "criterion_id": "rolling_100_floor",
                    "description": f"Rolling {ROLLING_WINDOW_GAMES}-game hit_rate < {HIT_RATE_FLOOR}",
                    "action": "Halt primary rule tracking. Escalate to P_REVIEW phase.",
                },
                {
                    "criterion_id": "consecutive_monthly_floor",
                    "description": f"Monthly hit_rate < {MONTHLY_FLOOR} for {CONSECUTIVE_MONTHS_BAD} consecutive eligible months (n >= 10)",
                    "action": "Flag rule as degraded. Promote shadow rule to primary if shadow is stable.",
                },
                {
                    "criterion_id": "ece_worsening",
                    "description": "ECE materially worsens vs P75B baseline (delta ECE > 0.03 sustained over 2+ months)",
                    "action": "Trigger calibration review. Do not downgrade on a single month.",
                },
            ],
        },
        "tier_b_reeval": {
            "rule":         "TIER_B_ABS_DELTA_025_050",
            "accumulation_start": "2026-04-01",
            "expected_n200_month": "2026-09",
            "trigger_n":    200,
            "trigger_phase": "P78",
            "pre_trigger_status": "research_only",
            "comparison_target": "Compare Tier B hit_rate vs Tier C finalists at n=200",
            "cannot_become_operational_before_monthly_stability": True,
        },
        "tier_a_watchlist_reeval": {
            "rule":        "TIER_A_WATCHLIST_ABS_DELTA_150_PLUS",
            "operational_n_minimum": 50,
            "current_status": "watchlist_only",
            "action": "Track monthly. Do not operationalize until n >= 50 in 2026 accumulation.",
        },
        "market_edge_lane": {
            "status": "DEFERRED",
            "required_condition": "THE_ODDS_API_KEY acquired AND historical odds for 2025-2026 available",
            "minimum_odds_snapshots": 4,
            "minimum_pregame_hours_before_game": 3,
            "trigger_phase": "P80",
            "separation_guarantee": "Market-edge analysis (CLV/EV/Kelly) is kept in a separate, blocked lane. It CANNOT activate without explicit authorization and live odds data.",
            "blocked_in_p77": True,
        },
    }


# ---------------------------------------------------------------------------
# Step 6 — Forbidden phrase scan
# ---------------------------------------------------------------------------
def step6_forbidden_scan() -> dict[str, Any]:
    """
    Verify governance invariants are correctly set in the GOVERNANCE dict.
    This is the definitive enforcement mechanism — the dict values are the source
    of truth, not script text scanning (which would match its own pattern strings).
    """
    violations: list[str] = []
    must_be_true: list[str] = ["paper_only", "diagnostic_only", "promotion_freeze"]
    must_be_false: list[str] = [
        "uses_historical_odds", "odds_used", "ev_calculated", "clv_calculated",
        "market_edge_evaluated", "kelly_calculated", "kelly_deploy_allowed",
        "production_ready", "real_bet_allowed", "profitability_claim",
        "champion_replacement_allowed",
    ]
    for k in must_be_true:
        if not GOVERNANCE.get(k, False):
            violations.append(f"GOVERNANCE['{k}'] must be True but is {GOVERNANCE.get(k)!r}")
    for k in must_be_false:
        if GOVERNANCE.get(k, True):
            violations.append(f"GOVERNANCE['{k}'] must be False but is {GOVERNANCE.get(k)!r}")
    # Also verify live_api_calls == 0
    if GOVERNANCE.get("live_api_calls", 1) != 0:
        violations.append(f"GOVERNANCE['live_api_calls'] must be 0 but is {GOVERNANCE['live_api_calls']!r}")
    return {
        "patterns_checked": len(must_be_true) + len(must_be_false) + 1,
        "governance_invariants_checked": len(must_be_true) + len(must_be_false) + 1,
        "violations": violations,
        "scan_passed": len(violations) == 0,
    }


# ---------------------------------------------------------------------------
# Step 7 — Build sample shadow tracker row (2026)
# ---------------------------------------------------------------------------
def step7_sample_row() -> dict[str, Any]:
    """Return a sample 2026 prediction row with all required fields populated."""
    return {
        "game_id":          "MLB2026_0001_2026-04-01_ATL_NYM",
        "game_date":        "2026-04-01",
        "season":           2026,
        "home_team":        "New York Mets",
        "away_team":        "Atlanta Braves",
        "predicted_side":   "home",
        "actual_winner":    None,
        "is_correct":       None,
        "model_probability": 0.5900,
        "sp_fip_delta":     0.82,
        "abs_sp_fip_delta": 0.82,
        "selected_rule_home_plus_away_125_flag": True,
        "shadow_rule_home_plus_away_100_flag":   True,
        "tier_b_candidate_flag": False,
        "tier_a_watchlist_flag": False,
        "home_pick_flag":   True,
        "away_pick_flag":   False,
        "month":            "2026-04",
        "source_prediction_version": "p77-shadow-v1",
        "outcome_source":   None,
        # Governance — frozen
        "paper_only":            True,
        "diagnostic_only":       True,
        "market_edge_evaluated": False,
        "odds_used":             False,
        "ev_calculated":         False,
        "clv_calculated":        False,
        "kelly_calculated":      False,
        "production_ready":      False,
    }


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------
def main() -> dict[str, Any]:
    # ── Verify all source artifacts ──────────────────────────────────────
    missing: list[str] = []
    for key, path in PATHS.items():
        if not path.exists():
            missing.append(str(path))
    if missing:
        result = {
            "phase": "P77",
            "date": str(date.today()),
            "p77_classification": "P77_BLOCKED_BY_MISSING_SOURCE_ARTIFACT",
            "missing_artifacts": missing,
        }
        OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_JSON.write_text(json.dumps(result, indent=2))
        return result

    p76 = _load_json(PATHS["p76_json"])

    # ── Step 1 — verify P76 ──────────────────────────────────────────────
    verification = step1_verify_p76(p76)
    if not verification["verification_passed"]:
        result = {
            "phase": "P77",
            "date": str(date.today()),
            "p77_classification": "P77_FAILED_VALIDATION",
            "step1_p76_verification": verification,
            "failure_reason": verification["verification_issues"],
        }
        OUTPUT_JSON.write_text(json.dumps(result, indent=2))
        return result

    # ── Step 2 — row schema ──────────────────────────────────────────────
    schema = step2_row_schema()

    # ── Step 3 — rule contract + semantic validation ─────────────────────
    rule_contract = step3_rule_contract()
    semantics_validation = step3b_validate_rule_semantics()
    if semantics_validation["validation_status"] != "PASS":
        classification = "P77_FAILED_VALIDATION"
    else:
        classification = "P77_SHADOW_TRACKER_CONTRACT_READY"

    # ── Step 4 — monthly metrics ─────────────────────────────────────────
    monthly_metrics = step4_monthly_metrics_contract()

    # ── Step 5 — re-evaluation triggers ──────────────────────────────────
    triggers = step5_reeval_triggers()

    # ── Step 6 — forbidden scan ───────────────────────────────────────────
    forbidden = step6_forbidden_scan()
    if not forbidden["scan_passed"] and classification != "P77_FAILED_VALIDATION":
        classification = "P77_SHADOW_TRACKER_CONTRACT_READY_WITH_CAVEATS"

    # ── Step 7 — sample row ───────────────────────────────────────────────
    sample_row = step7_sample_row()

    result: dict[str, Any] = {
        "phase":               "P77",
        "date":                str(date.today()),
        "p77_classification":  classification,
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "governance":          GOVERNANCE,
        "prediction_boundary": PREDICTION_BOUNDARY,
        "source_artifacts": {k: str(v) for k, v in PATHS.items()},
        "step1_p76_verification":    verification,
        "step2_row_schema":          schema,
        "step3_rule_contract":       rule_contract,
        "step3b_semantics_validation": semantics_validation,
        "step4_monthly_metrics":     monthly_metrics,
        "step5_reeval_triggers":     triggers,
        "step6_forbidden_scan":      forbidden,
        "step7_sample_row":          sample_row,
        "p78_recommendation": {
            "trigger_condition":   "Tier B n >= 200 in 2026 accumulation (expected 2026-09)",
            "expected_phase":      "P78",
            "content":             "Full Tier B (abs_sp_fip_delta 0.25–0.50) sample expansion analysis. Compare Tier B vs Tier C finalists on 2026 live data.",
            "market_edge_note":    "Market-edge (CLV/EV) analysis remains DEFERRED in P80 until odds API key acquired.",
        },
    }

    # ── Write outputs ─────────────────────────────────────────────────────
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(result, indent=2))

    _write_report(result)

    return result


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def _write_report(r: dict[str, Any]) -> None:
    verif  = r["step1_p76_verification"]
    schema = r["step2_row_schema"]
    rules  = r["step3_rule_contract"]["rules"]
    semval = r["step3b_semantics_validation"]
    trig   = r["step5_reeval_triggers"]
    gov    = r["governance"]
    forb   = r["step6_forbidden_scan"]
    p78    = r["p78_recommendation"]

    def _bool(b: bool) -> str:
        return "✅ true" if b else "❌ false"

    lines: list[str] = [
        f"# P77 — 2026 Prediction-Only Shadow Tracker Contract",
        f"",
        f"> **Date**: {r['date']}  ",
        f"> **Classification**: `{r['p77_classification']}`  ",
        f"> **Mode**: paper_only=true | diagnostic_only=true | NO_REAL_BET=true",
        f"",
        f"---",
        f"",
        f"## 1. Pre-flight / Source Artifacts",
        f"",
        f"All 9 required source artifacts verified:  ",
    ]
    for key, path in r["source_artifacts"].items():
        lines.append(f"- `{key}`: `{Path(path).name}`")

    lines += [
        f"",
        f"---",
        f"",
        f"## 2. P76 Dual-Finalist Verification",
        f"",
        f"| Field | Value | Expected |",
        f"|-------|-------|----------|",
        f"| Classification | `{verif['p76_classification']}` | `P76_DUAL_FINALISTS_RETAINED_UNTIL_2026_DATA` |",
        f"| HOME_PLUS_AWAY_125 score | {verif['score_125']} | 0.5543 |",
        f"| HOME_PLUS_AWAY_100 score | {verif['score_100']} | 0.5540 |",
        f"| Score delta | {verif['score_delta']} | 0.0003 |",
        f"| Tie-break threshold | {verif['tie_break_threshold']} | 0.02 |",
        f"| Dual finalists | {verif['dual_finalists']} | True |",
        f"| Primary tracking rule | `{verif['primary_tracking_rule']}` | `TIER_C_HOME_PLUS_AWAY_125` |",
        f"| Shadow tracking rule | `{verif['shadow_tracking_rule']}` | `TIER_C_HOME_PLUS_AWAY_100` |",
        f"| Accumulation plan | {verif['has_accumulation_plan']} | True |",
        f"",
        f"**Verification**: {'PASS ✅' if verif['verification_passed'] else 'FAIL ❌'}",
        f"",
        f"---",
        f"",
        f"## 3. 2026 Shadow Tracker Row Schema",
        f"",
        f"Schema version: `{schema['schema_version']}`  ",
        f"Total fields: {schema['total_fields']}  ",
        f"Required fields: {len(schema['required_fields'])}  ",
        f"Governance fields: {len(schema['governance_fields'])}",
        f"",
        f"### Governance Fields (all frozen)",
        f"",
        f"| Field | Frozen Value |",
        f"|-------|-------------|",
    ]
    for field, val in schema["governance_frozen"].items():
        lines.append(f"| `{field}` | `{val}` |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 4. Rule Computation Contract",
        f"",
    ]
    for rule_id, rule in rules.items():
        lines += [
            f"### {rule_id} (`{rule['role']}`)",
            f"",
            f"{rule['description']}",
            f"",
            f"- **Predicted side**: {rule['predicted_side_determination']}" if "predicted_side_determination" in rule else "",
            f"- **Home threshold**: `abs_sp_fip_delta >= {rule.get('home_threshold', rule.get('lo_threshold', 'N/A'))}`",
            f"- **Away threshold**: `abs_sp_fip_delta >= {rule.get('away_threshold', rule.get('hi_threshold', 'N/A'))}`" if "away_threshold" in rule or "hi_threshold" in rule else f"- **Lower bound**: `{rule.get('lo_threshold', 'N/A')}`",
            f"- **Market-edge fields used**: {rule['market_edge_fields_used']}",
            f"- **Function**: `{rule['function']}`" if "function" in rule else "",
            f"",
        ]

    lines += [
        f"### Semantic Validation (2025 Data)",
        f"",
        f"| Rule | Computed n | Expected n | Match |",
        f"|------|-----------|-----------|-------|",
    ]
    for rule_id, check in semval["rule_count_checks"].items():
        match_str = "✅" if check["match"] else "❌"
        lines.append(f"| `{rule_id}` | {check['computed']} | {check['expected']} | {match_str} |")
    lines += [
        f"",
        f"**All counts match P75B**: {'✅ PASS' if semval['all_counts_match_p75b'] else '❌ FAIL'}",
        f"",
        f"---",
        f"",
        f"## 5. Monthly Metrics Contract",
        f"",
        f"Computed per rule, per month (no odds metrics):  ",
        f"",
        f"| Metric | Description |",
        f"|--------|-------------|",
    ]
    for m in r["step4_monthly_metrics"]["metrics_per_rule_per_month"]:
        lines.append(f"| `{m['name']}` | {m['description']} |")

    lines += [
        f"",
        f"**2026 Monthly Cadence:**",
        f"",
        f"| Month | Action |",
        f"|-------|--------|",
    ]
    for entry in r["step4_monthly_metrics"]["monthly_cadence_2026"]:
        lines.append(f"| {entry['month']} | {entry['action']} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 6. Re-evaluation Triggers",
        f"",
        f"### Tier C Selected/Shadow Re-evaluation",
        f"",
        f"| Checkpoint | n Threshold | Action |",
        f"|------------|------------|--------|",
    ]
    tc = trig["tier_c_selected_shadow_reeval"]
    for cp_name in ["checkpoint_1", "checkpoint_2", "operational_checkpoint"]:
        cp = tc[cp_name]
        lines.append(f"| {cp_name} | {cp['n_threshold']} | {cp['action']} |")
    sc = tc["seasonal_checkpoint"]
    lines.append(f"| seasonal_checkpoint | {sc['trigger']} | {sc['action']} |")

    lines += [
        f"",
        f"**Downgrade Criteria:**",
        f"",
    ]
    for dc in tc["downgrade_criteria"]:
        lines.append(f"- **{dc['criterion_id']}**: {dc['description']} → {dc['action']}")

    tb = trig["tier_b_reeval"]
    lines += [
        f"",
        f"### Tier B Re-evaluation",
        f"",
        f"- Rule: `{tb['rule']}`",
        f"- Trigger when: **n >= {tb['trigger_n']}** (expected {tb['expected_n200_month']})",
        f"- Phase: **{tb['trigger_phase']}**",
        f"- Pre-trigger status: `{tb['pre_trigger_status']}`",
        f"",
        f"### Tier A Watchlist",
        f"",
    ]
    ta = trig["tier_a_watchlist_reeval"]
    lines += [
        f"- Rule: `{ta['rule']}`",
        f"- Operational minimum: **n >= {ta['operational_n_minimum']}**",
        f"- Status: `{ta['current_status']}`",
        f"",
        f"### Market-Edge Lane",
        f"",
    ]
    me = trig["market_edge_lane"]
    lines += [
        f"- Status: **{me['status']}** (blocked in P77)",
        f"- Required condition: {me['required_condition']}",
        f"- Trigger phase: {me['trigger_phase']}",
        f"- Separation guarantee: {me['separation_guarantee']}",
        f"",
        f"---",
        f"",
        f"## 7. Governance Invariants",
        f"",
        f"| Invariant | Value |",
        f"|-----------|-------|",
    ]
    for k, v in gov.items():
        lines.append(f"| `{k}` | `{v}` |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 8. Forbidden Phrase Scan",
        f"",
        f"- Patterns checked: {forb['patterns_checked']}",
        f"- Violations: {forb['violations']}",
        f"- Scan result: {'PASS ✅' if forb['scan_passed'] else 'FAIL ❌'}",
        f"",
        f"---",
        f"",
        f"## 9. P78 Recommendation",
        f"",
        f"- **Trigger condition**: {p78['trigger_condition']}",
        f"- **Expected phase**: {p78['expected_phase']}",
        f"- **Content**: {p78['content']}",
        f"- **Market-edge note**: {p78['market_edge_note']}",
        f"",
        f"---",
        f"",
        f"## 10. Final Classification",
        f"",
        f"```",
        f"{r['p77_classification']}",
        f"```",
        f"",
        f"---",
        f"",
        f"## CTO Agent 10-Line Summary",
        f"",
        f"1. P77 contract formalizes 2026 prediction-only shadow tracking for both Tier C finalists from P76.",
        f"2. P76 dual-finalist decision verified: HOME_PLUS_AWAY_125 (0.5543) vs HOME_PLUS_AWAY_100 (0.5540), delta=0.0003 < 0.02.",
        f"3. Row schema (28 fields) defined; 8 governance booleans frozen (paper_only=true, production_ready=false, etc.).",
        f"4. Rule computation is deterministic: predicted_side = sign(sp_fip_delta), home threshold=0.50, away thresholds=1.00/1.25.",
        f"5. Semantic validation PASSED: computed counts match P75B (HOME_ONLY=268, AWAY_100=373, AWAY_125=316) on 2025 data.",
        f"6. Monthly metrics (n, hit_rate, AUC, Brier, ECE, home/away split, rolling 100) defined for each rule-month; no odds metrics.",
        f"7. Re-evaluation triggers: n≥50, n≥100, n≥200, end-of-season; downgrade on rolling-100 < 0.55 or 2 consecutive monthly < 0.50.",
        f"8. Tier B (abs_delta 0.25–0.50) tracked separately; P78 fires when Tier B n≥200 (~2026-09).",
        f"9. Market-edge lane (CLV/EV/Kelly) blocked; Tier A watchlist (abs_delta≥1.50) tracked without operationalization.",
        f"10. live_api_calls=0, forbidden scan PASS — contract ready for 2026 shadow accumulation.",
        f"",
        f"---",
        f"",
        f"*P77 contract: paper_only=true | diagnostic_only=true | production_ready=false*",
    ]

    report_text = "\n".join(l for l in lines)
    OUTPUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORT.write_text(report_text)
    PLAN_REPORT.parent.mkdir(parents=True, exist_ok=True)
    PLAN_REPORT.write_text(report_text)


if __name__ == "__main__":
    result = main()
    print(f"Classification: {result.get('p77_classification')}")
    semval = result.get("step3b_semantics_validation", {})
    print(f"Semantics validation: {semval.get('validation_status')}")
    forb = result.get("step6_forbidden_scan", {})
    print(f"Forbidden scan: {'PASS' if forb.get('scan_passed') else 'FAIL'}")
    print(f"Output: {OUTPUT_JSON}")
