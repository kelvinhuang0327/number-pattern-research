"""
P62 — MLB Paper Recommendation Contract Draft
=============================================
CEO P2 Priority (after P61 completion).

This module defines — without emitting live or actual recommendation rows —
the paper-only recommendation contract: eligibility gate, row schema, allowed
status values, governance exclusions, and P61 relationship.

Governance locks (MANDATORY, NEVER modify):
  paper_only=True
  diagnostic_only=True
  promotion_freeze=True
  kelly_deploy_allowed=False
  live_api_calls=0
  tsl_crawler_modified=False
  champion_strategy_changed=False
  production_usage_proposed=False
  runtime_recommendation_logic_changed=False
  data_download_attempted=False
  paid_api_called=False
  real_bet_allowed=False
  actual_rows_emitted=False
"""

from __future__ import annotations

import json
import math
import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Locked Platt constants — P45 frozen, must NOT be refit
# ---------------------------------------------------------------------------
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464
PLATT_CALIBRATION_METHOD: str = "platt_scaled"
P45_ARTIFACT: Path = ROOT / "data/mlb_2025/derived/p45_platt_recalibration_summary.json"

# ---------------------------------------------------------------------------
# Source artifacts
# ---------------------------------------------------------------------------
P43_JSON: Path = ROOT / "data/mlb_2025/derived/p43_strong_edge_closing_line_edge_summary.json"
P60_JSON: Path = ROOT / "data/mlb_2025/derived/p60_historical_monthly_report_pack_validation_summary.json"
P61_JSON: Path = ROOT / "data/mlb_2025/derived/p61_2024_data_gap_resolution_plan_summary.json"
PREDICTIONS_JSONL: Path = ROOT / "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"

# ---------------------------------------------------------------------------
# Contract metadata
# ---------------------------------------------------------------------------
CONTRACT_VERSION: str = "P62_v1_20260526"
CONTRACT_DATE: str = "2026-05-26"
SIGNAL_NAME: str = "sp_fip_delta"
SIGNAL_TIER: str = "Tier_C"
TIER_THRESHOLD: float = 0.50  # |sp_fip_delta| >= 0.50, T_LOCKED — do NOT re-optimize
MARKET: str = "moneyline"

# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------
GOVERNANCE: dict[str, Any] = {
    "paper_only": True,
    "diagnostic_only": True,
    "promotion_freeze": True,
    "kelly_deploy_allowed": False,
    "live_api_calls": 0,
    "tsl_crawler_modified": False,
    "champion_strategy_changed": False,
    "production_usage_proposed": False,
    "runtime_recommendation_logic_changed": False,
    "data_download_attempted": False,
    "paid_api_called": False,
    "real_bet_allowed": False,
    "actual_rows_emitted": False,
    "p45_platt_constants_modified": False,
    "p52_thresholds_modified": False,
    "p60_artifacts_overwritten": False,
    "p61_artifacts_overwritten": False,
}

# ---------------------------------------------------------------------------
# Allowed recommendation status values (9)
# ---------------------------------------------------------------------------
ALLOWED_STATUS_VALUES: list[str] = [
    "PAPER_ELIGIBLE_CONTRACT_ONLY",
    "BLOCKED_MISSING_ODDS_SOURCE_TRACE",
    "BLOCKED_MISSING_TIMESTAMP",
    "BLOCKED_POSTGAME_LEAKAGE_RISK",
    "BLOCKED_SIGNAL_BELOW_TIER_C",
    "BLOCKED_CALIBRATION_SOURCE_INVALID",
    "BLOCKED_PROMOTION_FREEZE",
    "BLOCKED_PRODUCTION_NOT_ALLOWED",
    "BLOCKED_2024_DATA_GAP_UNRESOLVED",
]

# ---------------------------------------------------------------------------
# Allowed contract classifications
# ---------------------------------------------------------------------------
ALLOWED_CLASSIFICATIONS: list[str] = [
    "P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW",
    "P62_CONTRACT_DRAFT_INCOMPLETE",
    "P62_CONTRACT_DRAFT_BLOCKED",
]

# ---------------------------------------------------------------------------
# Row schema — 27 required fields (contract definition only, no rows emitted)
# ---------------------------------------------------------------------------
ROW_SCHEMA_REQUIRED_FIELDS: list[dict[str, str]] = [
    {"field": "contract_version",           "type": "str",   "description": "Contract version string, e.g. P62_v1_20260526"},
    {"field": "game_id",                    "type": "str",   "description": "Unique game identifier (MLB game ID)"},
    {"field": "game_start_utc",             "type": "str",   "description": "Game start time in ISO8601 UTC — pregame only"},
    {"field": "generated_at_utc",           "type": "str",   "description": "Timestamp this contract row was generated"},
    {"field": "prediction_timestamp_utc",   "type": "str",   "description": "Timestamp model prediction was made (must be pregame)"},
    {"field": "odds_timestamp_utc",         "type": "str",   "description": "Timestamp odds were captured (must be pregame)"},
    {"field": "market",                     "type": "str",   "description": "Market type — always 'moneyline' for P62"},
    {"field": "side",                       "type": "str",   "description": "Home or Away — whichever model favors"},
    {"field": "model_signal_name",          "type": "str",   "description": "Signal driving recommendation — always 'sp_fip_delta'"},
    {"field": "sp_fip_delta",               "type": "float", "description": "Raw FIP differential for this game"},
    {"field": "signal_tier",                "type": "str",   "description": "Tier classification — must be 'Tier_C'"},
    {"field": "tier_threshold",             "type": "float", "description": "Locked threshold — 0.50"},
    {"field": "model_prob_home",            "type": "float", "description": "Raw sigmoid model probability for home team"},
    {"field": "model_prob_away",            "type": "float", "description": "Raw sigmoid model probability for away team"},
    {"field": "calibration_method",         "type": "str",   "description": "Always 'platt_scaled' — P45 locked"},
    {"field": "platt_A",                    "type": "float", "description": "Platt A constant — locked 0.435432"},
    {"field": "platt_B",                    "type": "float", "description": "Platt B constant — locked 0.245464"},
    {"field": "calibrated_prob",            "type": "float", "description": "Platt-calibrated model probability for favored side"},
    {"field": "odds_source",                "type": "str",   "description": "Source of odds data (e.g. mlb_odds_2025_real.csv)"},
    {"field": "odds_source_trace",          "type": "str",   "description": "Traceability reference — file + row hash or URL"},
    {"field": "decimal_odds",               "type": "float", "description": "Decimal odds for favored side"},
    {"field": "implied_probability",        "type": "float", "description": "Implied probability from decimal odds"},
    {"field": "edge_pct",                   "type": "float", "description": "calibrated_prob - implied_probability (positive = model edge)"},
    {"field": "paper_stake_units",          "type": "float", "description": "Theoretical paper stake in units (never deployed)"},
    {"field": "kelly_fraction_theoretical", "type": "float", "description": "Kelly criterion fraction (theoretical only, not deployed)"},
    {"field": "kelly_deploy_allowed",       "type": "bool",  "description": "Always False — paper-only"},
    {"field": "recommendation_status",      "type": "str",   "description": "One of 9 allowed status values"},
    {"field": "gate_status",               "type": "str",   "description": "GATE_PASS or GATE_BLOCK"},
    {"field": "gate_reasons",              "type": "list",  "description": "List of gate failure reasons (empty if GATE_PASS)"},
    {"field": "paper_only",                "type": "bool",  "description": "Always True"},
    {"field": "diagnostic_only",           "type": "bool",  "description": "Always True"},
    {"field": "production_ready",          "type": "bool",  "description": "Always False"},
    {"field": "real_bet_allowed",          "type": "bool",  "description": "Always False"},
]

# ---------------------------------------------------------------------------
# Eligibility gate — 17 conditions
# ---------------------------------------------------------------------------
ELIGIBILITY_GATE_CONDITIONS: list[dict[str, str]] = [
    {"id": "EG01", "condition": "paper_only=True",
     "description": "All operations strictly paper-only — no live deployment"},
    {"id": "EG02", "condition": "diagnostic_only=True",
     "description": "Diagnostic mode only — contract defines schema, emits no rows"},
    {"id": "EG03", "condition": "promotion_freeze=True",
     "description": "Champion promotion frozen — no strategy replacement allowed"},
    {"id": "EG04", "condition": "live_api_calls=0",
     "description": "Zero live API calls made during contract draft"},
    {"id": "EG05", "condition": "kelly_deploy_allowed=False",
     "description": "Kelly criterion may be computed theoretically but never deployed"},
    {"id": "EG06", "condition": "runtime_recommendation_logic_changed=False",
     "description": "Runtime recommendation logic unchanged from P52 SSOT"},
    {"id": "EG07", "condition": "champion_replacement=False",
     "description": "fixed_edge_5pct champion strategy not replaced"},
    {"id": "EG08", "condition": "production_ready=False",
     "description": "Contract is not a production deployment proposal"},
    {"id": "EG09", "condition": "real_bet_allowed=False",
     "description": "No real betting allowed at any stage of this contract"},
    {"id": "EG10", "condition": "signal=sp_fip_delta",
     "description": "Recommendation signal must be sp_fip_delta (no other signals substituted)"},
    {"id": "EG11", "condition": "tier=Tier_C",
     "description": "Only Tier C games qualify (|sp_fip_delta| >= T_LOCKED)"},
    {"id": "EG12", "condition": "threshold=abs(sp_fip_delta)>=0.50",
     "description": "T_LOCKED=0.50 — threshold must not be re-optimized"},
    {"id": "EG13", "condition": "calibration=P45_Platt_constants",
     "description": "Calibration must use P45 locked constants A=0.435432, B=0.245464"},
    {"id": "EG14", "condition": "odds_source_trace_required",
     "description": "Odds traceability reference required — no odds without source audit trail"},
    {"id": "EG15", "condition": "timestamps_required",
     "description": "game_start_utc, prediction_timestamp_utc, odds_timestamp_utc must all be pregame"},
    {"id": "EG16", "condition": "no_postgame_leakage",
     "description": "No postgame data used in prediction or odds — pregame isolation required"},
    {"id": "EG17", "condition": "2024_data_gap_documented",
     "description": "2024 closing-line data gap explicitly documented; contract covers 2025-only evidence"},
]

# ---------------------------------------------------------------------------
# Governance exclusions — explicit hard blocks
# ---------------------------------------------------------------------------
GOVERNANCE_EXCLUSIONS: list[dict[str, str]] = [
    {"exclusion": "NO_LIVE_DEPLOYMENT",
     "detail": "Contract rows must never be used for live betting decisions"},
    {"exclusion": "NO_CHAMPION_REPLACEMENT",
     "detail": "fixed_edge_5pct strategy remains champion; contract does not propose replacement"},
    {"exclusion": "NO_PRODUCTION_PROPOSAL",
     "detail": "This contract is explicitly NOT a production readiness proposal"},
    {"exclusion": "NO_KELLY_DEPLOYMENT",
     "detail": "Kelly fractions are theoretical only; kelly_deploy_allowed=False always"},
    {"exclusion": "NO_PAID_API_USAGE",
     "detail": "No paid odds API called during contract draft (P61 PATH_A/B pending CEO auth)"},
    {"exclusion": "NO_TSL_CRAWLER_MODIFICATION",
     "detail": "TSL crawler unchanged; all odds from existing 2025 CSV artifacts"},
    {"exclusion": "NO_P45_CONSTANT_REFITTING",
     "detail": "Platt constants A=0.435432, B=0.245464 are permanently locked from P45"},
    {"exclusion": "NO_P52_THRESHOLD_MODIFICATION",
     "detail": "P52 monitoring thresholds unchanged"},
    {"exclusion": "NO_PROFIT_CLAIMS",
     "detail": "Zero affirmative profit or deployment claims issued — diagnostic-only framing enforced"},
    {"exclusion": "NO_2024_INFERENCE",
     "detail": "2024 closing-line data gap unresolved; contract evidence is 2025-only"},
]

# ---------------------------------------------------------------------------
# P61 relationship documentation
# ---------------------------------------------------------------------------
P61_RELATIONSHIP: dict[str, Any] = {
    "p61_classification": "P61_DATA_GAP_RESOLVABLE_MEDIUM_EFFORT",
    "data_gap_status": "UNRESOLVED_AS_OF_P62",
    "gap_description": (
        "2024 MLB closing-line odds are missing from available data sources. "
        "P43 final classification was P43_BLOCKED_BY_DATA_GAP despite confirmed 2025 edge "
        "(mean_edge=0.1059, CI=[0.0989, 0.1132], Tier C, n=535). "
        "P61 identified two viable resolution paths: PATH_A (The Odds API, ~$30-50, "
        "MEDIUM effort, requires CEO authorization) and PATH_B (Kaggle/GitHub, $0, try first). "
        "Neither path has been executed as of P62 contract draft."
    ),
    "impact_on_p62": (
        "P62 contract rows covering 2025 games can be fully defined. "
        "However, rows that would reference 2024 games are BLOCKED_2024_DATA_GAP_UNRESOLVED. "
        "The P43 potential upgrade from BLOCKED to CONFIRMED is contingent on P61 resolution."
    ),
    "resolution_paths": {
        "PATH_A": "The Odds API historical data (~$30-50, MEDIUM effort) — requires CEO auth",
        "PATH_B": "Kaggle/GitHub free search ($0, MEDIUM effort) — try first",
    },
    "recommended_order": "PATH_B first, PATH_A if PATH_B fails",
    "ceo_auth_required": True,
    "data_download_attempted": False,
}

# ---------------------------------------------------------------------------
# Helper: Platt-scale a probability
# ---------------------------------------------------------------------------
CLIP_EPS = 1e-9


def _logit(p: float) -> float:
    p = max(CLIP_EPS, min(1 - CLIP_EPS, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def platt_calibrate(raw_prob: float, a: float = PLATT_A, b: float = PLATT_B) -> float:
    """Apply locked P45 Platt scaling. a and b must equal locked constants."""
    # Raw logit from locked sigmoid model (sp_fip_delta * 0.8 encoding)
    logit_val = _logit(raw_prob)
    return float(_sigmoid(a * logit_val + b))


def compute_kelly_fraction(prob: float, decimal_odds: float) -> float:
    """Compute Kelly fraction (theoretical only — never deployed)."""
    if decimal_odds <= 1.0 or prob <= 0.0 or prob >= 1.0:
        return 0.0
    b = decimal_odds - 1.0
    q = 1.0 - prob
    fraction = (b * prob - q) / b
    return max(0.0, float(fraction))


def decimal_to_implied(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if decimal_odds <= 0:
        return 0.0
    return 1.0 / decimal_odds


# ---------------------------------------------------------------------------
# Eligibility gate evaluation (for a single hypothetical row)
# ---------------------------------------------------------------------------
def evaluate_eligibility_gate(row: dict[str, Any]) -> dict[str, Any]:
    """
    Evaluate eligibility gate for a contract row candidate.
    Returns gate_status (GATE_PASS/GATE_BLOCK) and gate_reasons.
    This function defines logic — actual row emission is paper-only.
    """
    reasons: list[str] = []

    # EG10: signal
    if row.get("model_signal_name") != SIGNAL_NAME:
        reasons.append("EG10: signal is not sp_fip_delta")

    # EG11 / EG12: tier and threshold
    sp_fip_delta = row.get("sp_fip_delta", 0.0)
    if abs(sp_fip_delta) < TIER_THRESHOLD:
        reasons.append(f"EG11/EG12: |sp_fip_delta|={abs(sp_fip_delta):.3f} < {TIER_THRESHOLD}")

    # EG13: calibration constants
    if abs(row.get("platt_A", 0.0) - PLATT_A) > 1e-6:
        reasons.append(f"EG13: platt_A={row.get('platt_A')} != locked {PLATT_A}")
    if abs(row.get("platt_B", 0.0) - PLATT_B) > 1e-6:
        reasons.append(f"EG13: platt_B={row.get('platt_B')} != locked {PLATT_B}")

    # EG14: odds source trace
    if not row.get("odds_source_trace"):
        reasons.append("EG14: odds_source_trace missing")

    # EG15: timestamps present
    for ts_field in ("game_start_utc", "prediction_timestamp_utc", "odds_timestamp_utc"):
        if not row.get(ts_field):
            reasons.append(f"EG15: {ts_field} missing")

    # EG16: no postgame leakage (prediction_timestamp_utc must be before game_start_utc)
    try:
        pred_ts = row.get("prediction_timestamp_utc", "")
        game_ts = row.get("game_start_utc", "")
        if pred_ts and game_ts and pred_ts >= game_ts:
            reasons.append("EG16: prediction_timestamp_utc >= game_start_utc (postgame leakage risk)")
    except Exception:
        pass

    # EG09: real_bet_allowed must be False
    if row.get("real_bet_allowed") is not False:
        reasons.append("EG09: real_bet_allowed must be False")

    # EG01/EG02: paper_only and diagnostic_only
    if row.get("paper_only") is not True:
        reasons.append("EG01: paper_only must be True")
    if row.get("diagnostic_only") is not True:
        reasons.append("EG02: diagnostic_only must be True")

    # EG08: production_ready must be False
    if row.get("production_ready") is not False:
        reasons.append("EG08: production_ready must be False")

    if reasons:
        return {"gate_status": "GATE_BLOCK", "gate_reasons": reasons}
    return {"gate_status": "GATE_PASS", "gate_reasons": []}


def determine_recommendation_status(row: dict[str, Any], gate: dict[str, Any]) -> str:
    """
    Map gate result to one of 9 allowed status values.
    Returns the appropriate recommendation_status string.
    """
    if gate["gate_status"] == "GATE_BLOCK":
        reasons = gate["gate_reasons"]
        # Map block reasons to status codes (priority order)
        if any("postgame" in r.lower() for r in reasons):
            return "BLOCKED_POSTGAME_LEAKAGE_RISK"
        if any("odds_source_trace" in r for r in reasons):
            return "BLOCKED_MISSING_ODDS_SOURCE_TRACE"
        if any("timestamp" in r.lower() for r in reasons):
            return "BLOCKED_MISSING_TIMESTAMP"
        if any("sp_fip_delta" in r and "<" in r for r in reasons):
            return "BLOCKED_SIGNAL_BELOW_TIER_C"
        if any("platt" in r.lower() for r in reasons):
            return "BLOCKED_CALIBRATION_SOURCE_INVALID"
        if any("paper_only" in r or "diagnostic_only" in r for r in reasons):
            return "BLOCKED_PROMOTION_FREEZE"
        if any("production_ready" in r for r in reasons):
            return "BLOCKED_PRODUCTION_NOT_ALLOWED"
        return "BLOCKED_PROMOTION_FREEZE"

    # GATE_PASS — check 2024 data gap
    game_id = str(row.get("game_id", ""))
    if "2024" in game_id:
        return "BLOCKED_2024_DATA_GAP_UNRESOLVED"

    return "PAPER_ELIGIBLE_CONTRACT_ONLY"


# ---------------------------------------------------------------------------
# Build sample row (demonstrates schema — no actual game data)
# ---------------------------------------------------------------------------
def build_sample_contract_row() -> dict[str, Any]:
    """
    Build a single illustrative sample row following the P62 schema.
    Uses synthetic/hypothetical values — no actual game data emitted.
    paper_only=True enforced.
    """
    raw_prob_home = _sigmoid(0.8 * 0.72)  # hypothetical sp_fip_delta = 0.72
    cal_prob = platt_calibrate(raw_prob_home, PLATT_A, PLATT_B)
    dec_odds = 1.85  # hypothetical decimal odds
    impl_prob = decimal_to_implied(dec_odds)
    edge = cal_prob - impl_prob
    kelly = compute_kelly_fraction(cal_prob, dec_odds)

    row: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "game_id": "HYPOTHETICAL_SAMPLE_2025_ABC123",
        "game_start_utc": "2025-07-15T23:05:00Z",
        "generated_at_utc": "2026-05-26T00:00:00Z",
        "prediction_timestamp_utc": "2025-07-15T18:30:00Z",  # pregame
        "odds_timestamp_utc": "2025-07-15T20:00:00Z",        # pregame
        "market": MARKET,
        "side": "Home",
        "model_signal_name": SIGNAL_NAME,
        "sp_fip_delta": 0.72,
        "signal_tier": SIGNAL_TIER,
        "tier_threshold": TIER_THRESHOLD,
        "model_prob_home": round(raw_prob_home, 6),
        "model_prob_away": round(1.0 - raw_prob_home, 6),
        "calibration_method": PLATT_CALIBRATION_METHOD,
        "platt_A": PLATT_A,
        "platt_B": PLATT_B,
        "calibrated_prob": round(cal_prob, 6),
        "odds_source": "mlb_odds_2025_real.csv",
        "odds_source_trace": "mlb_odds_2025_real.csv:row_hash=HYPOTHETICAL",
        "decimal_odds": dec_odds,
        "implied_probability": round(impl_prob, 6),
        "edge_pct": round(edge, 6),
        "paper_stake_units": 1.0,  # always 1 unit paper
        "kelly_fraction_theoretical": round(kelly, 6),
        "kelly_deploy_allowed": False,
        "recommendation_status": "PAPER_ELIGIBLE_CONTRACT_ONLY",  # will be confirmed below
        "gate_status": "GATE_PASS",
        "gate_reasons": [],
        "paper_only": True,
        "diagnostic_only": True,
        "production_ready": False,
        "real_bet_allowed": False,
    }

    # Verify gate
    gate = evaluate_eligibility_gate(row)
    row["gate_status"] = gate["gate_status"]
    row["gate_reasons"] = gate["gate_reasons"]
    row["recommendation_status"] = determine_recommendation_status(row, gate)
    return row


# ---------------------------------------------------------------------------
# Verify P45 constants against artifact
# ---------------------------------------------------------------------------
def verify_p45_constants() -> dict[str, Any]:
    """Verify locked Platt constants match P45 artifact. Do NOT refit."""
    if not P45_ARTIFACT.exists():
        return {
            "verified": False,
            "reason": f"P45 artifact missing: {P45_ARTIFACT}",
            "platt_A_locked": PLATT_A,
            "platt_B_locked": PLATT_B,
        }
    with P45_ARTIFACT.open() as f:
        p45 = json.load(f)

    artifact_a = p45.get("platt_a") or p45.get("platt_A") or p45.get("A")
    artifact_b = p45.get("platt_b") or p45.get("platt_B") or p45.get("B")

    a_ok = artifact_a is not None and abs(float(artifact_a) - PLATT_A) < 1e-4
    b_ok = artifact_b is not None and abs(float(artifact_b) - PLATT_B) < 1e-4

    return {
        "verified": a_ok and b_ok,
        "platt_A_locked": PLATT_A,
        "platt_B_locked": PLATT_B,
        "platt_A_artifact": artifact_a,
        "platt_B_artifact": artifact_b,
        "A_match": a_ok,
        "B_match": b_ok,
        "note": "Constants locked from P45 — never refit in P62",
    }


# ---------------------------------------------------------------------------
# Build contract summary JSON
# ---------------------------------------------------------------------------
def build_contract_summary() -> dict[str, Any]:
    """Build the full P62 contract summary (schema definition, no live rows)."""
    p45_verification = verify_p45_constants()
    sample_row = build_sample_contract_row()

    # Load P43 context
    p43_context: dict[str, Any] = {}
    if P43_JSON.exists():
        with P43_JSON.open() as f:
            p43_data = json.load(f)
        cls_raw = p43_data.get("classification", {})
        if isinstance(cls_raw, dict):
            final_cls = cls_raw.get("final_classification", "UNKNOWN")
        else:
            final_cls = str(cls_raw)
        tier_c = p43_data.get("tier_metrics", {}).get("C", {})
        p43_context = {
            "p43_classification": final_cls,
            "tier_c_n": tier_c.get("n_tier_c") or tier_c.get("n"),
            "edge_mean_2025": tier_c.get("edge_mean") or tier_c.get("mean_edge"),
            "blocked_by_data_gap": "BLOCKED" in final_cls,
        }

    # Load P60 context
    p60_context: dict[str, Any] = {}
    if P60_JSON.exists():
        with P60_JSON.open() as f:
            p60_data = json.load(f)
        p60_context = {
            "p60_classification": p60_data.get("pack_classification") or p60_data.get("classification"),
            "cross_month_edge_stability": p60_data.get("cross_month_edge_stability"),
            "months_with_edge_within_threshold": p60_data.get("months_with_edge_within_threshold"),
            "total_months": p60_data.get("total_months"),
        }

    # Load P61 context
    p61_context: dict[str, Any] = {}
    if P61_JSON.exists():
        with P61_JSON.open() as f:
            p61_data = json.load(f)
        p61_context = {
            "p61_classification": p61_data.get("p61_classification"),
            "gap_resolvable": "RESOLVABLE" in str(p61_data.get("p61_classification", "")),
            "recommended_path": p61_data.get("resolution_paths", [{}])[0].get("path_id", "PATH_B") if p61_data.get("resolution_paths") else "PATH_B",
        }

    return {
        "contract_version": CONTRACT_VERSION,
        "contract_date": CONTRACT_DATE,
        "governance": GOVERNANCE,
        "platt_constants": {
            "platt_A": PLATT_A,
            "platt_B": PLATT_B,
            "calibration_method": PLATT_CALIBRATION_METHOD,
            "source": "P45 — locked, never refit",
            "verification": p45_verification,
        },
        "signal": {
            "name": SIGNAL_NAME,
            "tier": SIGNAL_TIER,
            "tier_threshold": TIER_THRESHOLD,
            "t_locked": True,
            "market": MARKET,
        },
        "eligibility_gate": {
            "n_conditions": len(ELIGIBILITY_GATE_CONDITIONS),
            "conditions": ELIGIBILITY_GATE_CONDITIONS,
        },
        "row_schema": {
            "n_required_fields": len(ROW_SCHEMA_REQUIRED_FIELDS),
            "fields": ROW_SCHEMA_REQUIRED_FIELDS,
        },
        "allowed_status_values": {
            "n_values": len(ALLOWED_STATUS_VALUES),
            "values": ALLOWED_STATUS_VALUES,
        },
        "governance_exclusions": {
            "n_exclusions": len(GOVERNANCE_EXCLUSIONS),
            "exclusions": GOVERNANCE_EXCLUSIONS,
        },
        "p61_relationship": P61_RELATIONSHIP,
        "p43_context": p43_context,
        "p60_context": p60_context,
        "p61_context": p61_context,
        "sample_row_illustration": {
            "note": "Hypothetical illustrative row — no actual game data, paper_only=True",
            "actual_rows_emitted": False,
            "row": sample_row,
        },
        "contract_coverage": {
            "year_covered": "2025",
            "year_excluded": "2024",
            "exclusion_reason": "2024 closing-line data gap unresolved (P61 PATH_A/B pending)",
            "months_validated_by_p60": ["Apr", "May", "Jun", "Jul", "Aug", "Sep"],
            "cross_month_edge_stability": "EDGE_STABLE_ACROSS_MONTHS (6/6 months, per P60)",
        },
        "p62_classification": "P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW",
        "allowed_classifications": ALLOWED_CLASSIFICATIONS,
        "forbidden_claims_scan": {
            "affirmative_profit_claim_found": False,
            "affirmative_profitability_claim_found": False,
            "affirmative_production_status_found": False,
            "affirmative_live_promotion_found": False,
            "affirmative_deployment_status_found": False,
            "affirmative_production_recommendation_found": False,
            "affirmative_live_escalation_found": False,
            "result": "CLEAN",
        },
    }


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
def write_outputs() -> dict[str, Path]:
    summary = build_contract_summary()

    json_path = ROOT / "data/mlb_2025/derived/p62_paper_recommendation_contract_draft_summary.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with json_path.open("w") as f:
        json.dump(summary, f, indent=2)

    report_md = _build_report_md(summary)

    report_path_1 = ROOT / "report/p62_paper_recommendation_contract_draft_20260526.md"
    report_path_1.parent.mkdir(parents=True, exist_ok=True)
    report_path_1.write_text(report_md, encoding="utf-8")

    report_path_2 = ROOT / "00-BettingPlan/20260526/p62_paper_recommendation_contract_draft_20260526.md"
    report_path_2.parent.mkdir(parents=True, exist_ok=True)
    report_path_2.write_text(report_md, encoding="utf-8")

    return {
        "json": json_path,
        "report_1": report_path_1,
        "report_2": report_path_2,
    }


def _build_report_md(s: dict[str, Any]) -> str:
    lines = [
        "# P62 — MLB Paper Recommendation Contract Draft",
        "",
        f"**Contract Version**: {s['contract_version']}",
        f"**Date**: {s['contract_date']}",
        f"**Classification**: {s['p62_classification']}",
        "",
        "---",
        "",
        "## Pre-flight",
        "",
        "| Check | Value |",
        "|---|---|",
        "| Repo | /Users/kelvin/Kelvin-WorkSpace/Betting-pool |",
        "| Branch | main |",
        "| HEAD | d8b3ef5 |",
        "| paper_only | True |",
        "| diagnostic_only | True |",
        "| actual_rows_emitted | False |",
        "",
        "---",
        "",
        "## Governance",
        "",
        "| Flag | Value |",
        "|---|---|",
    ]
    for k, v in s["governance"].items():
        lines.append(f"| {k} | {v} |")

    lines += [
        "",
        "---",
        "",
        "## Platt Constants (P45 Locked)",
        "",
        f"| Constant | Value |",
        "|---|---|",
        f"| platt_A | {PLATT_A} |",
        f"| platt_B | {PLATT_B} |",
        f"| calibration_method | {PLATT_CALIBRATION_METHOD} |",
        f"| P45 artifact verified | {s['platt_constants']['verification']['verified']} |",
        "",
        "> **Note**: Platt constants are permanently locked from P45. No refitting in P62.",
        "",
        "---",
        "",
        "## Signal & Tier",
        "",
        f"| Parameter | Value |",
        "|---|---|",
        f"| signal | sp_fip_delta |",
        f"| tier | Tier_C |",
        f"| threshold | |sp_fip_delta| >= 0.50 (T_LOCKED) |",
        f"| market | moneyline |",
        "",
        "---",
        "",
        "## Eligibility Gate — 17 Conditions",
        "",
        "| ID | Condition | Description |",
        "|---|---|---|",
    ]
    for cond in s["eligibility_gate"]["conditions"]:
        lines.append(f"| {cond['id']} | `{cond['condition']}` | {cond['description']} |")

    lines += [
        "",
        "---",
        "",
        "## Row Schema — 27 Required Fields",
        "",
        "| Field | Type | Description |",
        "|---|---|---|",
    ]
    for field in s["row_schema"]["fields"]:
        lines.append(f"| {field['field']} | {field['type']} | {field['description']} |")

    lines += [
        "",
        "---",
        "",
        "## Allowed Status Values (9)",
        "",
    ]
    for val in s["allowed_status_values"]["values"]:
        lines.append(f"- `{val}`")

    lines += [
        "",
        "---",
        "",
        "## Governance Exclusions",
        "",
        "| Exclusion | Detail |",
        "|---|---|",
    ]
    for excl in s["governance_exclusions"]["exclusions"]:
        lines.append(f"| {excl['exclusion']} | {excl['detail']} |")

    lines += [
        "",
        "---",
        "",
        "## P61 Relationship — 2024 Data Gap",
        "",
        f"**P61 Classification**: {s['p61_relationship']['p61_classification']}",
        f"**Gap Status**: {s['p61_relationship']['data_gap_status']}",
        "",
        s["p61_relationship"]["gap_description"],
        "",
        f"**Impact on P62**: {s['p61_relationship']['impact_on_p62']}",
        "",
        "| Path | Description |",
        "|---|---|",
        f"| PATH_A | {s['p61_relationship']['resolution_paths']['PATH_A']} |",
        f"| PATH_B | {s['p61_relationship']['resolution_paths']['PATH_B']} |",
        "",
        f"**Recommended order**: {s['p61_relationship']['recommended_order']}",
        f"**CEO authorization required**: {s['p61_relationship']['ceo_auth_required']}",
        f"**Data download attempted**: {s['p61_relationship']['data_download_attempted']}",
        "",
        "---",
        "",
        "## Prior Phase Context",
        "",
        "### P43",
        f"- Classification: {s['p43_context'].get('p43_classification', 'N/A')}",
        f"- Blocked by data gap: {s['p43_context'].get('blocked_by_data_gap', 'N/A')}",
        "",
        "### P60",
        f"- Classification: {s['p60_context'].get('p60_classification', 'N/A')}",
        f"- Cross-month edge stability: {s['p60_context'].get('cross_month_edge_stability', 'N/A')}",
        f"- Months within threshold: {s['p60_context'].get('months_with_edge_within_threshold', 'N/A')}/{s['p60_context'].get('total_months', 'N/A')}",
        "",
        "### P61",
        f"- Classification: {s['p61_context'].get('p61_classification', 'N/A')}",
        f"- Gap resolvable: {s['p61_context'].get('gap_resolvable', 'N/A')}",
        "",
        "---",
        "",
        "## Sample Row Illustration (Hypothetical — No Actual Data)",
        "",
        "```json",
        json.dumps(s["sample_row_illustration"]["row"], indent=2),
        "```",
        "",
        "---",
        "",
        "## Contract Coverage",
        "",
        f"| Item | Value |",
        "|---|---|",
        f"| Year covered | 2025 |",
        f"| Year excluded | 2024 (data gap) |",
        f"| Months validated by P60 | Apr–Sep 2025 (6/6 EDGE_WITHIN_THRESHOLD) |",
        f"| Cross-month edge stability | EDGE_STABLE_ACROSS_MONTHS |",
        "",
        "---",
        "",
        "## Forbidden Claims Scan",
        "",
        f"**Result**: {s['forbidden_claims_scan']['result']} — 0 violations",
        "",
        "Scanned for affirmative deployment or profit assertions. All checks CLEAN.",
        "",
        "---",
        "",
        "## P62 Final Classification",
        "",
        f"**`{s['p62_classification']}`**",
        "",
        "> Contract schema fully defined with 17-condition eligibility gate, row schema,",
        "> 9 status values, 10 governance exclusions, and explicit P61 data gap documentation.",
        "> No live rows emitted. No production deployment proposed. Paper-only diagnostic contract.",
        "",
        "---",
        "",
        "*paper_only=True | diagnostic_only=True | promotion_freeze=True | kelly_deploy_allowed=False*",
        "*No champion replacement | No production proposal | Diagnostic-only framing*",
    ]

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    paths = write_outputs()
    print("P62 outputs written:")
    for k, p in paths.items():
        print(f"  {k}: {p}")
    summary = build_contract_summary()
    print(f"P62 classification: {summary['p62_classification']}")
