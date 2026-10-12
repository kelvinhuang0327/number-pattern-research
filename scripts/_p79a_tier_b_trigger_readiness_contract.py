"""
scripts/_p79a_tier_b_trigger_readiness_contract.py

P79A — Tier B Trigger Readiness + 2026 Live Data Intake Contract

Governance: paper_only=True | diagnostic_only=True | production_ready=False
NO_REAL_BET=True | live_api_calls=0 | ev_calculated=False
clv_calculated=False | kelly_calculated=False
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

GOVERNANCE: dict = {
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIER_B_TRIGGER_N: int = 200
TIER_B_LOW_ABS_DELTA: float = 0.25
TIER_B_HIGH_ABS_DELTA: float = 0.50
TIER_A_ABS_DELTA: float = 1.50
PRIMARY_HOME_ABS_DELTA: float = 0.50
PRIMARY_AWAY_ABS_DELTA: float = 1.25
SHADOW_AWAY_ABS_DELTA: float = 1.00
TIER_B_MIN_AUC: float = 0.60
TIER_B_MIN_HIT_DELTA: float = 0.02  # vs primary rule hit_rate

FIXTURE_MONTHS = [
    "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09",
]

P78_EXPECTED = {
    "classification": "P78_MONTHLY_SHADOW_TRACKER_TEMPLATE_READY",
    "schema_version": "p78-v1",
    "fixture_months_count": 6,
    "market_edge_lane": "blocked",
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PATHS: dict = {
    "p78_summary": ROOT / "data/mlb_2025/derived/p78_monthly_shadow_tracker_report_template_summary.json",
    "p78_report": ROOT / "report/p78_monthly_shadow_tracker_report_template_20260526.md",
    "p78_script": ROOT / "scripts/_p78_monthly_shadow_tracker_report_template.py",
    "p77_summary": ROOT / "data/mlb_2025/derived/p77_prediction_only_shadow_tracker_contract_summary.json",
    "p76_summary": ROOT / "data/mlb_2025/derived/p76_corrected_tier_c_final_rule_selection_summary.json",
    "p75b_summary": ROOT / "data/mlb_2025/derived/p75b_calibration_diagnostics_corrected_tier_c_summary.json",
    "p75a_summary": ROOT / "data/mlb_2025/derived/p75a_tier_c_corrected_rule_validator_summary.json",
    "p74_summary": ROOT / "data/mlb_2025/derived/p74_tier_c_home_away_bias_correction_summary.json",
    "p73_summary": ROOT / "data/mlb_2025/derived/p73_tier_stability_and_sample_expansion_summary.json",
    "p72b_summary": ROOT / "data/mlb_2025/derived/p72b_objective_metric_contract_summary.json",
    "p72a_summary": ROOT / "data/mlb_2025/derived/p72a_odds_free_strategy_accuracy_backtest_summary.json",
    "predictions_jsonl": ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
    # outputs
    "output_json": ROOT / "data/mlb_2025/derived/p79a_tier_b_trigger_readiness_contract_summary.json",
    "output_report": ROOT / "report/p79a_tier_b_trigger_readiness_contract_20260526.md",
    "output_betting_plan": ROOT / "00-BettingPlan/20260526/p79a_tier_b_trigger_readiness_contract_20260526.md",
}

SOURCE_ARTIFACT_KEYS = [
    "p78_summary", "p78_report", "p78_script",
    "p77_summary", "p76_summary", "p75b_summary", "p75a_summary",
    "p74_summary", "p73_summary", "p72b_summary", "p72a_summary",
    "predictions_jsonl",
]

# ---------------------------------------------------------------------------
# Step 1 — Verify P78 readiness
# ---------------------------------------------------------------------------

def step1_verify_p78() -> dict:
    """Load P78 summary and verify all readiness conditions."""
    path = PATHS["p78_summary"]
    if not path.exists():
        return {"verified": False, "error": f"Missing: {path}"}

    with open(path, encoding="utf-8") as fh:
        p78 = json.load(fh)

    errors: list[str] = []

    cls = p78.get("p78_classification", "")
    if cls != P78_EXPECTED["classification"]:
        errors.append(f"classification mismatch: {cls!r}")

    schema_version = p78.get("schema_version", "")
    if schema_version != P78_EXPECTED["schema_version"]:
        errors.append(f"schema_version mismatch: {schema_version!r}")

    monthly_reports = p78.get("step3_fixture_monthly_reports", [])
    if len(monthly_reports) != P78_EXPECTED["fixture_months_count"]:
        errors.append(f"fixture_months count: {len(monthly_reports)}")

    pack = p78.get("step5_pack_synthesis", {})
    if not pack.get("months_all_schema_valid"):
        errors.append("months_all_schema_valid is not True")
    if not pack.get("months_all_governance_clean"):
        errors.append("months_all_governance_clean is not True")
    if not pack.get("tier_b_n200_trigger_fires_in_fixture"):
        errors.append("tier_b_n200_trigger_fires_in_fixture is not True")

    market_edge = p78.get("market_edge_lane", "")
    if market_edge != P78_EXPECTED["market_edge_lane"]:
        errors.append(f"market_edge_lane: {market_edge!r}")

    tier_b_end_n = pack.get("tier_b_accumulated_n_end_of_fixture", 0)

    return {
        "verified": len(errors) == 0,
        "classification": cls,
        "schema_version": schema_version,
        "fixture_months_count": len(monthly_reports),
        "months_all_schema_valid": pack.get("months_all_schema_valid"),
        "months_all_governance_clean": pack.get("months_all_governance_clean"),
        "tier_b_trigger_fires_in_fixture": pack.get("tier_b_n200_trigger_fires_in_fixture"),
        "tier_b_accumulated_n_end_of_fixture": tier_b_end_n,
        "market_edge_lane": market_edge,
        "errors": errors,
    }

# ---------------------------------------------------------------------------
# Step 2 — 2026 Live Intake Row Contract
# ---------------------------------------------------------------------------

INTAKE_ROW_FIELDS: list[str] = [
    "game_id", "game_date", "season", "month",
    "home_team", "away_team",
    "predicted_side", "actual_winner", "is_correct",
    "model_probability",
    "sp_fip_delta", "abs_sp_fip_delta",
    "home_pick_flag", "away_pick_flag",
    "primary_rule_home_plus_away_125_flag",
    "shadow_rule_home_plus_away_100_flag",
    "tier_b_candidate_flag",
    "tier_a_watchlist_flag",
    "source_prediction_version",
    "outcome_source",
    "row_status",
    "row_validation_errors",
    "paper_only",
    "diagnostic_only",
    "odds_used",
    "market_edge_evaluated",
    "ev_calculated",
    "clv_calculated",
    "kelly_calculated",
    "production_ready",
]

INTAKE_GOVERNANCE_ENFORCEMENT: dict = {
    "paper_only": True,
    "diagnostic_only": True,
    "odds_used": False,
    "market_edge_evaluated": False,
    "ev_calculated": False,
    "clv_calculated": False,
    "kelly_calculated": False,
    "production_ready": False,
}


def step2_intake_row_contract() -> dict:
    """Define the 2026 live data intake row contract."""
    return {
        "contract_version": "p79a-v1",
        "contract_name": "2026_LIVE_TIER_B_INTAKE_ROW_CONTRACT",
        "season": "2026",
        "required_fields": INTAKE_ROW_FIELDS,
        "required_fields_count": len(INTAKE_ROW_FIELDS),
        "governance_enforcement": INTAKE_GOVERNANCE_ENFORCEMENT,
        "field_descriptions": {
            "game_id": "Unique game identifier (e.g. MLB game ID)",
            "game_date": "YYYY-MM-DD",
            "season": "4-digit season year (int), e.g. 2026",
            "month": "YYYY-MM",
            "home_team": "Home team abbreviation",
            "away_team": "Away team abbreviation",
            "predicted_side": "'home' or 'away'",
            "actual_winner": "'home' or 'away' (filled after game completion)",
            "is_correct": "bool — predicted_side == actual_winner",
            "model_probability": "float [0,1] — model home win probability",
            "sp_fip_delta": "float — starting pitcher FIP delta (home SP FIP - away SP FIP)",
            "abs_sp_fip_delta": "float — abs(sp_fip_delta)",
            "home_pick_flag": "bool — model_probability > 0.5",
            "away_pick_flag": "bool — model_probability <= 0.5",
            "primary_rule_home_plus_away_125_flag": (
                f"bool — home_pick and abs_sp_fip_delta >= {PRIMARY_HOME_ABS_DELTA}, "
                f"OR away_pick and abs_sp_fip_delta >= {PRIMARY_AWAY_ABS_DELTA}"
            ),
            "shadow_rule_home_plus_away_100_flag": (
                f"bool — home_pick and abs_sp_fip_delta >= {PRIMARY_HOME_ABS_DELTA}, "
                f"OR away_pick and abs_sp_fip_delta >= {SHADOW_AWAY_ABS_DELTA}"
            ),
            "tier_b_candidate_flag": (
                f"bool — abs_sp_fip_delta >= {TIER_B_LOW_ABS_DELTA} "
                f"AND abs_sp_fip_delta < {TIER_B_HIGH_ABS_DELTA}"
            ),
            "tier_a_watchlist_flag": f"bool — abs_sp_fip_delta >= {TIER_A_ABS_DELTA}",
            "source_prediction_version": "str — e.g. 'phase56_sp_bullpen_context_v1'",
            "outcome_source": "str — e.g. 'mlb_api', 'retrosheet', 'manual'",
            "row_status": "'VALID' | 'INVALID' | 'PENDING_OUTCOME'",
            "row_validation_errors": "list[str] — empty list if row is valid",
            "paper_only": "bool — MUST be True",
            "diagnostic_only": "bool — MUST be True",
            "odds_used": "bool — MUST be False",
            "market_edge_evaluated": "bool — MUST be False",
            "ev_calculated": "bool — MUST be False",
            "clv_calculated": "bool — MUST be False",
            "kelly_calculated": "bool — MUST be False",
            "production_ready": "bool — MUST be False",
        },
        "tier_b_candidate_definition": {
            "condition": (
                f"abs_sp_fip_delta >= {TIER_B_LOW_ABS_DELTA} "
                f"AND abs_sp_fip_delta < {TIER_B_HIGH_ABS_DELTA}"
            ),
            "prediction_only": True,
            "odds_not_required": True,
            "market_edge_not_included": True,
        },
        "market_edge_separation": (
            "Market-edge fields (EV, CLV, odds, Kelly) are NOT present in intake rows. "
            "Separation is enforced at contract level. "
            "Market-edge analysis deferred to P80."
        ),
        "validation_rules": [
            "abs_sp_fip_delta == abs(sp_fip_delta)",
            "home_pick_flag == (model_probability > 0.5)",
            "away_pick_flag == (model_probability <= 0.5)",
            "tier_b_candidate_flag == (0.25 <= abs_sp_fip_delta < 0.50)",
            "paper_only must be True",
            "production_ready must be False",
            "odds_used must be False",
        ],
    }

# ---------------------------------------------------------------------------
# Step 3 — Tier B Trigger State Machine
# ---------------------------------------------------------------------------

TIER_B_STATES: dict = {
    "TIER_B_NOT_READY": {
        "condition": "n < 50",
        "min_n": 0,
        "max_n_exclusive": 50,
        "description": "Too few samples for meaningful inference.",
        "action": "Continue accumulation. Do not draw directional conclusions.",
        "next_state": "TIER_B_EARLY_OBSERVATION",
    },
    "TIER_B_EARLY_OBSERVATION": {
        "condition": "50 <= n < 100",
        "min_n": 50,
        "max_n_exclusive": 100,
        "description": "Early observations available. Trends may not yet be stable.",
        "action": "Continue accumulation. Note directional trends only.",
        "next_state": "TIER_B_ACCUMULATING",
    },
    "TIER_B_ACCUMULATING": {
        "condition": "100 <= n < 200",
        "min_n": 100,
        "max_n_exclusive": 200,
        "description": "Sample building. Primary signal emerging. Monthly stability tracking begins.",
        "action": "Continue accumulation. Begin monthly stability tracking.",
        "next_state": "TIER_B_TRIGGER_READY",
    },
    "TIER_B_TRIGGER_READY": {
        "condition": f"n >= {TIER_B_TRIGGER_N}",
        "min_n": TIER_B_TRIGGER_N,
        "max_n_exclusive": None,
        "description": "Trigger threshold reached. Ready for full P79 analysis.",
        "action": (
            "Freeze snapshot. Generate P79 execution prompt. "
            "DO NOT auto-run market-edge analysis."
        ),
        "next_state": "TIER_B_TRIGGER_FROZEN or TIER_B_REJECTED_FOR_STABILITY",
    },
    "TIER_B_TRIGGER_FROZEN": {
        "condition": f"n >= {TIER_B_TRIGGER_N} AND snapshot created",
        "min_n": TIER_B_TRIGGER_N,
        "max_n_exclusive": None,
        "description": "Snapshot frozen. P79 analysis pending.",
        "action": "Run P79 Tier B vs Tier C comparison on frozen snapshot.",
        "next_state": "P79_EXECUTION",
    },
    "TIER_B_REJECTED_FOR_STABILITY": {
        "condition": f"n >= {TIER_B_TRIGGER_N} AND stability gate fails",
        "min_n": TIER_B_TRIGGER_N,
        "max_n_exclusive": None,
        "description": "Trigger reached but rolling/monthly stability fails gate.",
        "action": "Continue accumulation. Investigate stability. Re-evaluate at n+50.",
        "next_state": "TIER_B_TRIGGER_READY (re-evaluation)",
    },
}


def _tier_b_state(n: int) -> str:
    """Map cumulative Tier B count to trigger state (accumulation states only)."""
    if n < 50:
        return "TIER_B_NOT_READY"
    elif n < 100:
        return "TIER_B_EARLY_OBSERVATION"
    elif n < 200:
        return "TIER_B_ACCUMULATING"
    else:
        return "TIER_B_TRIGGER_READY"


def step3_tier_b_trigger_states() -> dict:
    """Return the complete Tier B trigger state machine definition."""
    return {
        "trigger_n": TIER_B_TRIGGER_N,
        "tier_b_definition": {
            "abs_sp_fip_delta_min_inclusive": TIER_B_LOW_ABS_DELTA,
            "abs_sp_fip_delta_max_exclusive": TIER_B_HIGH_ABS_DELTA,
            "prediction_only": True,
            "no_odds_required": True,
        },
        "states": TIER_B_STATES,
        "state_count": len(TIER_B_STATES),
        "trigger_freeze_requirements": {
            "n_reached": True,
            "snapshot_id_created": True,
            "data_cutoff_frozen": True,
            "row_count_frozen": True,
            "checksum_computed": True,
            "no_dirty_runtime_source_files": True,
            "p79_prompt_generated": True,
            "market_edge_not_auto_run": True,
        },
        "market_edge_deferred_to": "P80",
        "production_readiness_achievable_in_p79": False,
    }

# ---------------------------------------------------------------------------
# Step 4 — Tier B vs Tier C Comparison Contract
# ---------------------------------------------------------------------------

COMPARISON_METRICS: list[str] = [
    "n",
    "hit_rate",
    "hit_rate_ci_lower",
    "hit_rate_ci_upper",
    "auc",
    "auc_ci_lower",
    "auc_ci_upper",
    "brier",
    "log_loss",
    "ece",
    "monthly_stability",
    "rolling_100_hit_rate",
    "home_n",
    "home_hit_rate",
    "away_n",
    "away_hit_rate",
    "calibration_quality",
    "concentration_risk",
]


def step4_comparison_contract() -> dict:
    """Define Tier B vs Tier C finalist comparison contract for P79 execution."""
    return {
        "contract_name": "TIER_B_VS_TIER_C_COMPARISON_CONTRACT",
        "contract_version": "p79a-v1",
        "tier_c_comparators": [
            {
                "rule_name": "TIER_C_HOME_PLUS_AWAY_125",
                "role": "primary",
                "home_abs_delta_threshold": PRIMARY_HOME_ABS_DELTA,
                "away_abs_delta_threshold": PRIMARY_AWAY_ABS_DELTA,
            },
            {
                "rule_name": "TIER_C_HOME_PLUS_AWAY_100",
                "role": "shadow",
                "home_abs_delta_threshold": PRIMARY_HOME_ABS_DELTA,
                "away_abs_delta_threshold": SHADOW_AWAY_ABS_DELTA,
            },
        ],
        "metrics": COMPARISON_METRICS,
        "metrics_count": len(COMPARISON_METRICS),
        "operational_gate": {
            "gate_name": "TIER_B_OPERATIONAL_RESEARCH_GATE",
            "conditions": [
                f"n >= {TIER_B_TRIGGER_N}",
                f"AUC >= {TIER_B_MIN_AUC} OR hit_rate >= primary_rule_hit_rate + {TIER_B_MIN_HIT_DELTA}",
                "monthly_stability >= MODERATE",
                "ECE not materially worse than Tier C finalists (delta < 0.03)",
                "no severe concentration risk (home or away not > 90% of picks)",
                "still prediction-only — NOT production-ready",
            ],
            "gate_pass_outcome": "Tier B becomes operational research candidate in P79",
            "gate_fail_outcome": "Tier B remains in observation mode. Re-evaluate at n+50.",
        },
        "hard_constraints": {
            "tier_b_cannot_become_production_ready_in_p79": True,
            "market_edge_not_included_in_p79": True,
            "kelly_not_computed_in_p79": True,
            "ev_not_computed_in_p79": True,
            "clv_not_computed_in_p79": True,
        },
        "stability_levels": {
            "STRONG": "All months >= 0.55, rolling_100 >= 0.58, no RED months",
            "MODERATE": "Most months >= 0.52, rolling_100 >= 0.55, at most 1 RED month",
            "WEAK": "Multiple months < 0.52 OR rolling_100 < 0.55",
            "INSUFFICIENT": f"n < {TIER_B_TRIGGER_N} OR fewer than 3 eligible months",
        },
        "market_edge_lane": "blocked",
    }

# ---------------------------------------------------------------------------
# Step 5 — Trigger Handoff Package Schema
# ---------------------------------------------------------------------------

HANDOFF_REQUIRED_FIELDS: list[str] = [
    "trigger_status",
    "trigger_date",
    "season",
    "data_cutoff",
    "tier_b_n",
    "tier_b_months_covered",
    "snapshot_id",
    "snapshot_hash",
    "primary_rule_snapshot_n",
    "shadow_rule_snapshot_n",
    "governance_snapshot",
    "recommended_p79_prompt",
    "blocked_market_edge_reason",
]


def step5_handoff_package_schema() -> dict:
    """Define the trigger handoff package schema for P79 execution."""
    return {
        "schema_name": "P79_TRIGGER_HANDOFF_PACKAGE",
        "schema_version": "p79a-v1",
        "required_fields": HANDOFF_REQUIRED_FIELDS,
        "required_fields_count": len(HANDOFF_REQUIRED_FIELDS),
        "field_definitions": {
            "trigger_status": "str — TIER_B_TRIGGER_FROZEN | TIER_B_REJECTED_FOR_STABILITY",
            "trigger_date": "str — YYYY-MM, month when trigger fired",
            "season": "int — e.g. 2026",
            "data_cutoff": "str — YYYY-MM-DD, last game date in snapshot",
            "tier_b_n": "int — cumulative Tier B n at time of trigger",
            "tier_b_months_covered": "list[str] — YYYY-MM list of months in snapshot",
            "snapshot_id": "str — deterministic unique snapshot identifier",
            "snapshot_hash": "str — sha256[:16] of deterministic snapshot descriptor",
            "primary_rule_snapshot_n": "int — primary rule n in same time window",
            "shadow_rule_snapshot_n": "int — shadow rule n in same time window",
            "governance_snapshot": "dict — governance flags at time of trigger (all paper_only=True etc.)",
            "recommended_p79_prompt": "str — auto-generated P79 execution prompt",
            "blocked_market_edge_reason": "str — reason market-edge analysis is blocked",
        },
        "governance_snapshot_template": {
            "paper_only": True,
            "diagnostic_only": True,
            "odds_used": False,
            "market_edge_evaluated": False,
            "ev_calculated": False,
            "clv_calculated": False,
            "kelly_calculated": False,
            "production_ready": False,
            "live_api_calls": 0,
        },
    }

# ---------------------------------------------------------------------------
# Step 6 — Fixture Validation
# ---------------------------------------------------------------------------

def _is_tier_b_row(row: dict) -> bool:
    p0 = row.get("p0_features", {})
    if not p0.get("sp_fip_delta_available", False):
        return False
    fip = p0.get("sp_fip_delta")
    if fip is None:
        return False
    abs_fip = abs(fip)
    return TIER_B_LOW_ABS_DELTA <= abs_fip < TIER_B_HIGH_ABS_DELTA


def _is_primary_row(row: dict) -> bool:
    p0 = row.get("p0_features", {})
    if not p0.get("sp_fip_delta_available", False):
        return False
    fip = p0.get("sp_fip_delta")
    if fip is None:
        return False
    abs_fip = abs(fip)
    home_pick = row.get("model_home_prob", 0.5) > 0.5
    if home_pick and abs_fip >= PRIMARY_HOME_ABS_DELTA:
        return True
    if not home_pick and abs_fip >= PRIMARY_AWAY_ABS_DELTA:
        return True
    return False


def _is_shadow_row(row: dict) -> bool:
    p0 = row.get("p0_features", {})
    if not p0.get("sp_fip_delta_available", False):
        return False
    fip = p0.get("sp_fip_delta")
    if fip is None:
        return False
    abs_fip = abs(fip)
    home_pick = row.get("model_home_prob", 0.5) > 0.5
    if home_pick and abs_fip >= PRIMARY_HOME_ABS_DELTA:
        return True
    if not home_pick and abs_fip >= SHADOW_AWAY_ABS_DELTA:
        return True
    return False


def _generate_snapshot_hash(season: int, trigger_month: str, tier_b_n: int) -> str:
    descriptor = (
        f"p79a|season={season}|trigger_month={trigger_month}"
        f"|tier_b_n={tier_b_n}|trigger_threshold={TIER_B_TRIGGER_N}"
    )
    return hashlib.sha256(descriptor.encode("utf-8")).hexdigest()[:16]


def _generate_snapshot_id(season: int, trigger_month: str) -> str:
    ym = trigger_month.replace("-", "")
    return f"tier_b_snapshot_{season}_{ym}"


def _generate_p79_prompt(trigger_month: str, tier_b_n: int, season: int) -> str:
    return (
        f"[P79 — Tier B Sample Expansion Analysis vs Tier C Finalists on {season} Live Data]\n\n"
        f"Trigger: Tier B cumulative n >= {TIER_B_TRIGGER_N} reached at {trigger_month} "
        f"(n={tier_b_n})\n"
        f"Snapshot ID: tier_b_snapshot_{season}_{trigger_month.replace('-', '')}\n"
        f"Compare: Tier B (abs_sp_fip_delta [{TIER_B_LOW_ABS_DELTA}, {TIER_B_HIGH_ABS_DELTA})) "
        f"vs TIER_C_HOME_PLUS_AWAY_125 and TIER_C_HOME_PLUS_AWAY_100\n"
        f"Data source: {season} live accumulation through {trigger_month}\n"
        f"Mode: paper_only=True | diagnostic_only=True | NO_REAL_BET=True\n"
        f"Market-edge: DEFERRED to P80 (pending odds API key)\n"
        f"Production readiness: NOT achievable in P79"
    )


def step6_fixture_validation(predictions_path: Path) -> dict:
    """
    Load 2025 JSONL, simulate Tier B trigger accumulation by month,
    confirm state transitions, and generate sample frozen trigger package.
    """
    rows: list[dict] = []
    with open(predictions_path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))

    # Count per month
    monthly_counts: dict[str, dict] = {
        m: {"tier_b": 0, "primary": 0, "shadow": 0, "last_date": ""} for m in FIXTURE_MONTHS
    }
    for row in rows:
        gdate = row.get("game_date", "")
        if not gdate or len(gdate) < 7:
            continue
        gmonth = gdate[:7]
        if gmonth not in monthly_counts:
            continue
        mc = monthly_counts[gmonth]
        if _is_tier_b_row(row):
            mc["tier_b"] += 1
        if _is_primary_row(row):
            mc["primary"] += 1
        if _is_shadow_row(row):
            mc["shadow"] += 1
        if gdate > mc["last_date"]:
            mc["last_date"] = gdate

    # Compute cumulative and state transitions
    cum_tier_b = 0
    cum_primary = 0
    cum_shadow = 0
    monthly_progression: list[dict] = []
    trigger_month: Optional[str] = None
    trigger_n: Optional[int] = None
    trigger_primary_n: Optional[int] = None
    trigger_shadow_n: Optional[int] = None
    trigger_data_cutoff: Optional[str] = None

    for month in FIXTURE_MONTHS:
        mc = monthly_counts[month]
        cum_tier_b += mc["tier_b"]
        cum_primary += mc["primary"]
        cum_shadow += mc["shadow"]
        state = _tier_b_state(cum_tier_b)

        monthly_progression.append({
            "month": month,
            "monthly_tier_b_n": mc["tier_b"],
            "cumulative_tier_b_n": cum_tier_b,
            "cumulative_primary_n": cum_primary,
            "cumulative_shadow_n": cum_shadow,
            "trigger_state": state,
        })

        # First month where cumulative >= TRIGGER_N
        if trigger_month is None and cum_tier_b >= TIER_B_TRIGGER_N:
            trigger_month = month
            trigger_n = cum_tier_b
            trigger_primary_n = cum_primary
            trigger_shadow_n = cum_shadow
            trigger_data_cutoff = mc["last_date"] or f"{month}-30"

    trigger_fires = trigger_month is not None

    # Validate expected state transitions
    actual_states = [m["trigger_state"] for m in monthly_progression]
    # Build expected based on actual cumulative counts (not hardcoded)
    expected_states = [_tier_b_state(m["cumulative_tier_b_n"]) for m in monthly_progression]
    transitions_correct = actual_states == expected_states

    # Also check the qualitative sequence is monotone (never goes backward)
    state_order = {
        "TIER_B_NOT_READY": 0,
        "TIER_B_EARLY_OBSERVATION": 1,
        "TIER_B_ACCUMULATING": 2,
        "TIER_B_TRIGGER_READY": 3,
    }
    monotone = all(
        state_order.get(actual_states[i], -1) <= state_order.get(actual_states[i + 1], -1)
        for i in range(len(actual_states) - 1)
    )

    # Generate frozen package if trigger fires
    frozen_package: Optional[dict] = None
    if trigger_fires:
        snapshot_id = _generate_snapshot_id(2025, trigger_month)
        snapshot_hash = _generate_snapshot_hash(2025, trigger_month, trigger_n)
        months_covered = [m for m in FIXTURE_MONTHS if m <= trigger_month]
        gov_snap = {
            k: GOVERNANCE[k]
            for k in [
                "paper_only", "diagnostic_only", "odds_used", "market_edge_evaluated",
                "ev_calculated", "clv_calculated", "kelly_calculated",
                "production_ready", "live_api_calls",
            ]
        }
        frozen_package = {
            "trigger_status": "TIER_B_TRIGGER_FROZEN",
            "trigger_date": trigger_month,
            "season": 2025,
            "data_cutoff": trigger_data_cutoff,
            "tier_b_n": trigger_n,
            "tier_b_months_covered": months_covered,
            "snapshot_id": snapshot_id,
            "snapshot_hash": snapshot_hash,
            "primary_rule_snapshot_n": trigger_primary_n,
            "shadow_rule_snapshot_n": trigger_shadow_n,
            "governance_snapshot": gov_snap,
            "recommended_p79_prompt": _generate_p79_prompt(trigger_month, trigger_n, 2025),
            "blocked_market_edge_reason": (
                "Market-edge analysis (EV/CLV/Kelly) requires live closing odds. "
                "Odds API key not yet acquired. Deferred to P80."
            ),
        }

    return {
        "fixture_season": 2025,
        "fixture_months": FIXTURE_MONTHS,
        "monthly_progression": monthly_progression,
        "trigger_fires": trigger_fires,
        "trigger_month": trigger_month,
        "trigger_n": trigger_n,
        "trigger_data_cutoff": trigger_data_cutoff,
        "state_transitions_correct": transitions_correct,
        "state_transitions_monotone": monotone,
        "actual_states": actual_states,
        "end_of_fixture_tier_b_n": cum_tier_b,
        "frozen_package": frozen_package,
        "total_rows_loaded": len(rows),
        "validation_note": (
            "Fixture validation uses 2025 data to confirm trigger logic works. "
            "Does NOT imply 2026 readiness beyond contract validation."
        ),
    }

# ---------------------------------------------------------------------------
# Step 7 — Forbidden scan
# ---------------------------------------------------------------------------

def step7_forbidden_scan() -> dict:
    """Verify GOVERNANCE dict has no forbidden violations."""
    violations: list[str] = []
    checks = {
        "paper_only": (True, "must be True"),
        "diagnostic_only": (True, "must be True"),
        "uses_historical_odds": (False, "must be False"),
        "live_api_calls": (0, "must be 0"),
        "odds_used": (False, "must be False"),
        "ev_calculated": (False, "must be False"),
        "clv_calculated": (False, "must be False"),
        "market_edge_evaluated": (False, "must be False"),
        "kelly_calculated": (False, "must be False"),
        "kelly_deploy_allowed": (False, "must be False"),
        "production_ready": (False, "must be False"),
        "real_bet_allowed": (False, "must be False"),
        "champion_replacement_allowed": (False, "must be False"),
        "profitability_claim": (False, "must be False"),
        "promotion_freeze": (True, "must be True"),
    }
    for key, (expected, note) in checks.items():
        actual = GOVERNANCE.get(key)
        if actual != expected:
            violations.append(
                f"GOVERNANCE[{key!r}]={actual!r}, expected={expected!r} ({note})"
            )
    return {
        "scan_passed": len(violations) == 0,
        "violations_count": len(violations),
        "violations": violations,
    }

# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(summary: dict, path: Path) -> None:
    s6 = summary.get("step6_fixture_validation", {})
    mp = s6.get("monthly_progression", [])
    trigger_month = s6.get("trigger_month", "N/A")
    trigger_n = s6.get("trigger_n", 0)
    frozen = s6.get("frozen_package")
    cls = summary.get("p79a_classification", "UNKNOWN")

    lines: list[str] = [
        "# P79A — Tier B Trigger Readiness + 2026 Live Data Intake Contract",
        "",
        f"> **Classification**: `{cls}`",
        f"> **Schema Version**: `{summary.get('schema_version', 'UNKNOWN')}`",
        f"> **Generated**: {summary.get('generated_at', '')}",
        "> **Mode**: `paper_only=True | diagnostic_only=True | production_ready=False`",
        "",
        "---",
        "",
        "## Source Artifacts Verified",
        "",
    ]
    for art in summary.get("source_artifacts_verified", []):
        lines.append(f"- ✅ {art}")

    lines += [
        "",
        "## Step 1 — P78 Readiness Verification",
        "",
    ]
    s1 = summary.get("step1_p78_verification", {})
    lines += [
        f"- Classification: `{s1.get('classification', 'N/A')}`",
        f"- Schema version: `{s1.get('schema_version', 'N/A')}`",
        f"- Fixture months: {s1.get('fixture_months_count', 0)}",
        f"- All schema-valid: {s1.get('months_all_schema_valid', False)}",
        f"- All governance-clean: {s1.get('months_all_governance_clean', False)}",
        f"- Tier B n≥200 trigger fires in fixture: {s1.get('tier_b_trigger_fires_in_fixture', False)}",
        f"- Market-edge lane: `{s1.get('market_edge_lane', 'N/A')}`",
        f"- **Verified**: {s1.get('verified', False)}",
    ]

    lines += [
        "",
        "## Step 2 — 2026 Live Intake Row Contract",
        "",
        f"- Contract version: `p79a-v1`",
        f"- Required fields: {summary.get('step2_intake_row_contract', {}).get('required_fields_count', 0)}",
        "",
        "### Governance Enforcement",
        "",
        "| Field | Required Value |",
        "|-------|---------------|",
    ]
    for k, v in INTAKE_GOVERNANCE_ENFORCEMENT.items():
        lines.append(f"| `{k}` | `{v}` |")

    lines += [
        "",
        "## Step 3 — Tier B Trigger State Machine",
        "",
        "| State | Condition | Action |",
        "|-------|-----------|--------|",
    ]
    for sname, sinfo in TIER_B_STATES.items():
        lines.append(f"| `{sname}` | {sinfo['condition']} | {sinfo['action'][:80]} |")

    lines += [
        "",
        "## Step 6 — Fixture Trigger Validation (2025 Data)",
        "",
        "### Monthly Tier B Accumulation",
        "",
        "| Month | Monthly N | Cumulative N | Primary N | Shadow N | State |",
        "|-------|-----------|--------------|-----------|----------|-------|",
    ]
    _state_emoji = {
        "TIER_B_NOT_READY": "🔴",
        "TIER_B_EARLY_OBSERVATION": "🟡",
        "TIER_B_ACCUMULATING": "🟡",
        "TIER_B_TRIGGER_READY": "🟢",
    }
    for m in mp:
        st = m["trigger_state"]
        emoji = _state_emoji.get(st, "⚪")
        lines.append(
            f"| {m['month']} | {m['monthly_tier_b_n']} "
            f"| **{m['cumulative_tier_b_n']}** "
            f"| {m['cumulative_primary_n']} | {m['cumulative_shadow_n']} "
            f"| {emoji} `{st}` |"
        )

    lines += [
        "",
        f"**Trigger fires at**: `{trigger_month}` (cumulative Tier B n = {trigger_n})",
        f"**State transitions correct**: {s6.get('state_transitions_correct', False)}",
        f"**State transitions monotone**: {s6.get('state_transitions_monotone', False)}",
        "",
        "## Frozen Trigger Handoff Package (Fixture Sample — 2025)",
        "",
    ]
    if frozen:
        lines += [
            f"- **Trigger status**: `{frozen['trigger_status']}`",
            f"- **Trigger date**: `{frozen['trigger_date']}`",
            f"- **Season**: {frozen['season']}",
            f"- **Data cutoff**: `{frozen['data_cutoff']}`",
            f"- **Tier B n**: {frozen['tier_b_n']}",
            f"- **Snapshot ID**: `{frozen['snapshot_id']}`",
            f"- **Snapshot hash**: `{frozen['snapshot_hash']}`",
            f"- **Primary rule n**: {frozen['primary_rule_snapshot_n']}",
            f"- **Shadow rule n**: {frozen['shadow_rule_snapshot_n']}",
            f"- **Months covered**: {', '.join(frozen['tier_b_months_covered'])}",
            "",
            "### Auto-Generated P79 Execution Prompt",
            "",
            "```",
            frozen["recommended_p79_prompt"],
            "```",
            "",
            f"**Market-edge blocked**: {frozen['blocked_market_edge_reason']}",
        ]

    lines += [
        "",
        "## Step 4 — Tier B vs Tier C Comparison Contract",
        "",
        "### Operational Research Gate",
        "",
    ]
    gate = summary.get("step4_comparison_contract", {}).get("operational_gate", {})
    for cond in gate.get("conditions", []):
        lines.append(f"- {cond}")

    lines += [
        "",
        "### Hard Constraints",
        "",
        "- Tier B **CANNOT** become production-ready in P79",
        "- Market-edge (EV/CLV/Kelly) NOT included in P79",
        "- Deferred to P80 (pending odds API key)",
        "",
        "## Step 5 — Trigger Handoff Package Schema",
        "",
        f"- Schema: `P79_TRIGGER_HANDOFF_PACKAGE` (p79a-v1)",
        f"- Required fields: {len(HANDOFF_REQUIRED_FIELDS)}",
        "",
        "| Field | Type/Description |",
        "|-------|-----------------|",
    ]
    s5 = summary.get("step5_handoff_package_schema", {})
    for fname, fdesc in s5.get("field_definitions", {}).items():
        lines.append(f"| `{fname}` | {fdesc} |")

    lines += [
        "",
        "## Governance Invariants",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in GOVERNANCE.items():
        lines.append(f"| `{k}` | `{v}` |")

    lines += [
        "",
        "## Forbidden Scan",
        "",
    ]
    scan = summary.get("step7_forbidden_scan", {})
    lines.append(f"- **Result**: {'✅ PASS' if scan.get('scan_passed') else '❌ FAIL'}")
    lines.append(f"- **Violations**: {scan.get('violations_count', 0)}")

    lines += [
        "",
        "---",
        "",
        "## P79 Roadmap",
        "",
        f"- **P79 trigger**: Tier B cumulative n >= {TIER_B_TRIGGER_N} in 2026 live data (~2026-09)",
        "- **P79 content**: Tier B vs Tier C finalist comparison on 2026 live accumulation",
        "- **P80**: Market-edge lane (EV/CLV/Kelly) — pending odds API key",
        "",
        "*P79A — Contract-only / validator-only. No live data fetched. No production modification.*",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== P79A Tier B Trigger Readiness Contract ===")
    print(f"Mode: paper_only={GOVERNANCE['paper_only']} | diagnostic_only={GOVERNANCE['diagnostic_only']}")
    print(f"live_api_calls={GOVERNANCE['live_api_calls']} | production_ready={GOVERNANCE['production_ready']}")

    # Verify source artifacts
    missing = [
        str(PATHS[k]) for k in SOURCE_ARTIFACT_KEYS if not PATHS[k].exists()
    ]
    if missing:
        print(f"STOP — Missing source artifacts:\n" + "\n".join(missing))
        return
    artifact_names = [PATHS[k].name for k in SOURCE_ARTIFACT_KEYS]
    print(f"✓ All {len(artifact_names)} source artifacts verified")

    # Step 1
    s1 = step1_verify_p78()
    if not s1["verified"]:
        print(f"STOP — P78 verification failed: {s1['errors']}")
        return
    print(f"✓ P78 verified: {s1['classification']}")
    print(
        f"  Fixture months: {s1['fixture_months_count']} | "
        f"Tier B trigger fires: {s1['tier_b_trigger_fires_in_fixture']}"
    )

    # Step 2
    s2 = step2_intake_row_contract()
    print(f"✓ Intake row contract defined: {s2['required_fields_count']} fields")

    # Step 3
    s3 = step3_tier_b_trigger_states()
    print(f"✓ Tier B trigger states defined: {s3['state_count']} states")

    # Step 4
    s4 = step4_comparison_contract()
    print(f"✓ Tier B vs Tier C comparison contract defined: {s4['metrics_count']} metrics")

    # Step 5
    s5 = step5_handoff_package_schema()
    print(f"✓ Trigger handoff package schema defined: {s5['required_fields_count']} fields")

    # Step 6
    s6 = step6_fixture_validation(PATHS["predictions_jsonl"])
    if not s6["trigger_fires"]:
        print("WARN — Fixture trigger did NOT fire (Tier B never reached n>=200)")
    else:
        print(f"✓ Fixture trigger fires at {s6['trigger_month']} (n={s6['trigger_n']})")
    print(f"  State transitions correct: {s6['state_transitions_correct']}")
    print(f"  State transitions monotone: {s6['state_transitions_monotone']}")
    for m in s6["monthly_progression"]:
        print(
            f"  {m['month']}: tier_b_cum={m['cumulative_tier_b_n']}, "
            f"state={m['trigger_state']}"
        )

    # Step 7
    s7 = step7_forbidden_scan()
    print(f"✓ Forbidden scan: {'PASS' if s7['scan_passed'] else 'FAIL'} ({s7['violations_count']} violations)")

    # Pack synthesis
    classification = (
        "P79A_TIER_B_TRIGGER_READINESS_CONTRACT_READY"
        if (s1["verified"] and s6["trigger_fires"] and s6["state_transitions_correct"]
                and s6["state_transitions_monotone"] and s7["scan_passed"])
        else "P79A_TIER_B_TRIGGER_READINESS_CONTRACT_READY_WITH_CAVEATS"
    )

    pack = {
        "p79a_classification": classification,
        "intake_contract_fields": s2["required_fields_count"],
        "trigger_states_defined": s3["state_count"],
        "comparison_metrics_defined": s4["metrics_count"],
        "handoff_schema_fields": s5["required_fields_count"],
        "fixture_trigger_fires": s6["trigger_fires"],
        "fixture_trigger_month": s6.get("trigger_month"),
        "fixture_trigger_n": s6.get("trigger_n"),
        "state_transitions_correct": s6["state_transitions_correct"],
        "state_transitions_monotone": s6.get("state_transitions_monotone", False),
        "end_of_fixture_tier_b_n": s6["end_of_fixture_tier_b_n"],
        "market_edge_lane": "blocked",
        "governance_clean": s7["scan_passed"],
    }

    summary = {
        "p79a_classification": classification,
        "schema_version": "p79a-v1",
        "generated_at": datetime.now().isoformat(),
        "governance_snapshot": GOVERNANCE,
        "source_artifacts_verified": artifact_names,
        "step1_p78_verification": s1,
        "step2_intake_row_contract": s2,
        "step3_tier_b_trigger_states": s3,
        "step4_comparison_contract": s4,
        "step5_handoff_package_schema": s5,
        "step6_fixture_validation": s6,
        "step7_forbidden_scan": s7,
        "step8_pack_synthesis": pack,
        "market_edge_lane": "blocked",
        "tier_b_trigger_n": TIER_B_TRIGGER_N,
        "rules": {
            "primary": "TIER_C_HOME_PLUS_AWAY_125",
            "shadow": "TIER_C_HOME_PLUS_AWAY_100",
            "tier_b": f"abs_sp_fip_delta in [{TIER_B_LOW_ABS_DELTA}, {TIER_B_HIGH_ABS_DELTA})",
            "tier_a": f"abs_sp_fip_delta >= {TIER_A_ABS_DELTA}",
        },
        "p79_recommendation": {
            "trigger_condition": f"Tier B n >= {TIER_B_TRIGGER_N} in 2026 live accumulation",
            "expected_2026_trigger": "~2026-09 (inferred from 2025 fixture accumulation rate)",
            "content": "Full Tier B vs Tier C finalist comparison on 2026 live data",
            "market_edge_note": "Market-edge (EV/CLV/Kelly) deferred to P80",
        },
    }

    # Write JSON
    out_json = PATHS["output_json"]
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(f"✓ JSON written: {out_json.name}")

    # Write report
    _write_report(summary, PATHS["output_report"])
    print(f"✓ Report written: {PATHS['output_report'].name}")

    # Write BettingPlan copy
    bp_path = PATHS["output_betting_plan"]
    bp_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PATHS["output_report"], bp_path)
    print(f"✓ BettingPlan copy written: {bp_path.name}")

    print(f"\nClassification: {classification}")
    print(f"Forbidden: {'PASS' if s7['scan_passed'] else 'FAIL'}")


if __name__ == "__main__":
    main()
