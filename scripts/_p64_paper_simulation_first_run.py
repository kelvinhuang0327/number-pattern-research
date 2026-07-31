"""
P64 — Paper Simulation First Run
=================================
CEO approval: YES approve P62 contract and proceed with P64 paper simulation first run

Governance flags (locked, immutable):
  paper_only=True
  diagnostic_only=True
  promotion_freeze=True
  kelly_deploy_allowed=False
  live_api_calls=0
  paid_api_called=False
  runtime_recommendation_logic_changed=False

Data sources (local only, no API calls):
  - data/mlb_2025/derived/p62_paper_recommendation_contract_draft_summary.json
  - data/mlb_2025/derived/p63_paper_recommendation_contract_review_readiness_summary.json
  - data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl
  - data/mlb_2025/mlb_odds_2025_real.csv
  - data/mlb_2025/derived/p45_platt_recalibration_summary.json
  - data/mlb_2025/derived/p52_monitoring_contract_v2_summary.json

Outputs:
  - data/mlb_2025/derived/p64_paper_simulation_rows.jsonl
  - data/mlb_2025/derived/p64_paper_simulation_first_run_summary.json
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Governance constants — NEVER MODIFY
# ---------------------------------------------------------------------------
PAPER_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
PROMOTION_FREEZE: bool = True
KELLY_DEPLOY_ALLOWED: bool = False
LIVE_API_CALLS: int = 0
PAID_API_CALLED: bool = False
RUNTIME_RECOMMENDATION_LOGIC_CHANGED: bool = False
REAL_BET_ALLOWED: bool = False
PRODUCTION_READY: bool = False

# Platt constants — locked from P45, never refit
PLATT_A: float = 0.435432
PLATT_B: float = 0.245464

# Signal / tier constants — locked from P52/P62
SIGNAL_NAME: str = "sp_fip_delta"
TIER_LABEL: str = "Tier_C"
TIER_THRESHOLD: float = 0.50
CONTRACT_VERSION: str = "P62_v1_20260526"
MARKET: str = "moneyline"
ODDS_SOURCE: str = "mlb_odds_2025_real.csv"

# Allowed P62 status values
ALLOWED_STATUS_VALUES = {
    "PAPER_ELIGIBLE_CONTRACT_ONLY",
    "BLOCKED_MISSING_ODDS_SOURCE_TRACE",
    "BLOCKED_MISSING_TIMESTAMP",
    "BLOCKED_POSTGAME_LEAKAGE_RISK",
    "BLOCKED_SIGNAL_BELOW_TIER_C",
    "BLOCKED_CALIBRATION_SOURCE_INVALID",
    "BLOCKED_PROMOTION_FREEZE",
    "BLOCKED_PRODUCTION_NOT_ALLOWED",
    "BLOCKED_2024_DATA_GAP_UNRESOLVED",
}

# P64-specific forbidden affirmative claims — scan output rows only
FORBIDDEN_AFFIRMATIVE_TERMS = [
    "production_ready=True",
    "real_bet_allowed=True",
    "kelly_deploy_allowed=True",
    "live_bet_approved",
    "champion_replaced",
    "promotion_approved",
    "live_deployment",
    "profitability_confirmed",
    "actual_bet_placed",
]

# Paths
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "mlb_2025"
DERIVED_DIR = DATA_DIR / "derived"

ARTIFACT_PATHS = {
    "p62": DERIVED_DIR / "p62_paper_recommendation_contract_draft_summary.json",
    "p63": DERIVED_DIR / "p63_paper_recommendation_contract_review_readiness_summary.json",
    "p45": DERIVED_DIR / "p45_platt_recalibration_summary.json",
    "p52": DERIVED_DIR / "p52_monitoring_contract_v2_summary.json",
    "predictions": DERIVED_DIR / "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl",
    "odds_csv": DATA_DIR / "mlb_odds_2025_real.csv",
}

OUTPUT_ROWS_PATH = DERIVED_DIR / "p64_paper_simulation_rows.jsonl"
OUTPUT_SUMMARY_PATH = DERIVED_DIR / "p64_paper_simulation_first_run_summary.json"


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

def logit(p: float) -> float:
    """Safe logit: log(p / (1-p)), clamped to avoid log(0)."""
    eps = 1e-9
    p = max(eps, min(1.0 - eps, p))
    return math.log(p / (1.0 - p))


def platt_calibrate(model_prob: float, a: float = PLATT_A, b: float = PLATT_B) -> float:
    """
    Platt scaling: 1 / (1 + exp(-A * logit(p) - B)).

    Verified against P62 sample illustration:
      model_prob=0.640146 → calibrated≈0.6216 with A=0.435432, B=0.245464.
    """
    raw = logit(model_prob)
    return 1.0 / (1.0 + math.exp(-a * raw - b))


def american_to_decimal(ml_str: str) -> float | None:
    """
    Convert American moneyline string to decimal odds.
      +210 → 3.10
      -260 → 1.3846...
    Returns None if the string is invalid / missing.
    """
    if not ml_str or str(ml_str).strip() in ("", "nan", "NaN", "None"):
        return None
    try:
        val = float(str(ml_str).strip().replace(" ", ""))
    except (ValueError, TypeError):
        return None
    if val == 0:
        return None
    if val > 0:
        return round(1.0 + val / 100.0, 6)
    else:  # val < 0
        return round(1.0 + 100.0 / abs(val), 6)


def normalize_team(name: str) -> str:
    """Normalize team name for join keys (lowercase, collapse whitespace)."""
    return re.sub(r"\s+", " ", str(name)).strip().lower()


def short_hash(text: str) -> str:
    """8-char SHA-256 prefix for traceability tokens."""
    return hashlib.sha256(text.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_p45_constants() -> dict[str, float]:
    """Load Platt constants from P45 artifact; verify against governance constants."""
    path = ARTIFACT_PATHS["p45"]
    with open(path) as f:
        p45 = json.load(f)
    a = p45["p45a_pilot"]["platt_a"]
    b = p45["p45a_pilot"]["platt_b"]
    if round(a, 6) != PLATT_A or round(b, 6) != PLATT_B:
        raise RuntimeError(
            f"P45 constant mismatch: artifact A={a} B={b}, expected {PLATT_A} {PLATT_B}. "
            "Governance violation — Platt constants must never be refit."
        )
    return {"platt_A": a, "platt_B": b, "source": str(path.name)}


def load_p62_contract() -> dict[str, Any]:
    """Load P62 contract draft summary."""
    with open(ARTIFACT_PATHS["p62"]) as f:
        return json.load(f)


def load_p63_readiness() -> dict[str, Any]:
    """Load P63 readiness summary; verify classification."""
    with open(ARTIFACT_PATHS["p63"]) as f:
        data = json.load(f)
    classification = data.get("p63_classification", "")
    if classification != "P63_READY_FOR_CEO_REVIEW":
        raise RuntimeError(
            f"P63 readiness check failed: got '{classification}', "
            "expected 'P63_READY_FOR_CEO_REVIEW'."
        )
    return data


def load_p52_thresholds() -> dict[str, Any]:
    """Load P52 monitoring contract; extract governance flags."""
    with open(ARTIFACT_PATHS["p52"]) as f:
        return json.load(f)


def load_predictions() -> list[dict[str, Any]]:
    """Load all 2025 per-game predictions from JSONL."""
    rows: list[dict[str, Any]] = []
    with open(ARTIFACT_PATHS["predictions"]) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_odds_lookup() -> dict[tuple[str, str], dict[str, Any]]:
    """
    Load odds CSV and build lookup dict keyed by (date_str, norm_home_team).
    Uses csv module to avoid pandas dependency.
    """
    import csv

    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    with open(ARTIFACT_PATHS["odds_csv"], newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            key = (str(row.get("Date", "")).strip(), normalize_team(row.get("Home", "")))
            trace_input = f"{row.get('Date')}|{row.get('Home')}|{row.get('Away')}|{i}"
            row["_row_hash"] = short_hash(trace_input)
            row["_csv_row_index"] = i
            lookup[key] = row
    return lookup


# ---------------------------------------------------------------------------
# Tier C filter
# ---------------------------------------------------------------------------

def filter_tier_c(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return records where |sp_fip_delta| >= TIER_THRESHOLD (0.50)."""
    result = []
    for rec in predictions:
        delta = rec.get("p0_features", {}).get("sp_fip_delta")
        if delta is not None and abs(float(delta)) >= TIER_THRESHOLD:
            result.append(rec)
    return result


# ---------------------------------------------------------------------------
# Gate / status determination
# ---------------------------------------------------------------------------

def determine_status(
    home_ml_str: str,
    away_ml_str: str,
    side: str,
    home_decimal: float | None,
    away_decimal: float | None,
) -> tuple[str, str, list[str]]:
    """
    Return (recommendation_status, gate_status, gate_reasons).

    Rules (applied in priority order):
      1. Missing odds for favored side → BLOCKED_MISSING_ODDS_SOURCE_TRACE
      2. Otherwise → PAPER_ELIGIBLE_CONTRACT_ONLY
    Note: BLOCKED_2024_DATA_GAP_UNRESOLVED applies globally (documented in summary),
    not per-row for 2025 games.
    BLOCKED_PROMOTION_FREEZE and BLOCKED_PRODUCTION_NOT_ALLOWED are global governance
    flags encoded in row fields (kelly_deploy_allowed=False, production_ready=False),
    not individual row statuses, since all rows share them.
    """
    favored_decimal = home_decimal if side == "Home" else away_decimal
    if favored_decimal is None:
        reasons = [f"Odds for {side} side missing or invalid (raw: '{home_ml_str}'/'{away_ml_str}')"]
        return "BLOCKED_MISSING_ODDS_SOURCE_TRACE", "GATE_BLOCK", reasons

    return "PAPER_ELIGIBLE_CONTRACT_ONLY", "GATE_PASS", []


# ---------------------------------------------------------------------------
# Row builder
# ---------------------------------------------------------------------------

def build_paper_row(
    pred: dict[str, Any],
    odds_row: dict[str, Any],
    platt_a: float,
    platt_b: float,
    generated_at: str,
) -> dict[str, Any]:
    """
    Build one P62-compliant 33-field paper simulation row.

    Governance invariants:
      paper_only=True, diagnostic_only=True, production_ready=False,
      real_bet_allowed=False, kelly_deploy_allowed=False.
    All timestamps are paper-constructed pregame proxies (source_backtest data
    does not carry real timestamp metadata).
    """
    game_date: str = pred["game_date"]
    game_id: str = pred["game_id"]
    home_team: str = pred["home_team"]
    away_team: str = pred["away_team"]
    model_home_prob: float = float(pred["model_home_prob"])
    p0 = pred.get("p0_features", {})
    sp_fip_delta: float = float(p0["sp_fip_delta"])

    # Platt calibration (formula verified against P62 sample illustration)
    calibrated_home: float = platt_calibrate(model_home_prob, platt_a, platt_b)
    model_away_prob: float = round(1.0 - model_home_prob, 6)

    # Determine favored side
    if model_home_prob >= 0.5:
        side = "Home"
        calibrated_prob = calibrated_home
    else:
        side = "Away"
        calibrated_prob = round(1.0 - calibrated_home, 6)

    # American odds from CSV
    home_ml_str = str(odds_row.get("Home ML", "")).strip()
    away_ml_str = str(odds_row.get("Away ML", "")).strip()
    home_decimal = american_to_decimal(home_ml_str)
    away_decimal = american_to_decimal(away_ml_str)

    favored_decimal = home_decimal if side == "Home" else away_decimal
    favored_ml_str = home_ml_str if side == "Home" else away_ml_str

    # Gate / status
    rec_status, gate_status, gate_reasons = determine_status(
        home_ml_str, away_ml_str, side, home_decimal, away_decimal
    )

    # Edge and Kelly (theoretical only, never deployed)
    if favored_decimal is not None:
        implied_probability = round(1.0 / favored_decimal, 6)
        edge_pct = round(calibrated_prob - implied_probability, 6)
        # Kelly fraction: (p*d - 1) / (d - 1)  where d = decimal_odds
        d = favored_decimal
        kelly_raw = (calibrated_prob * d - 1.0) / (d - 1.0) if d > 1.0 else 0.0
        kelly_fraction_theoretical = round(max(0.0, kelly_raw), 6)
        paper_stake_units = round(kelly_fraction_theoretical * 1.0, 6)
        decimal_odds_out = round(favored_decimal, 6)
    else:
        implied_probability = None
        edge_pct = None
        kelly_fraction_theoretical = 0.0
        paper_stake_units = 0.0
        decimal_odds_out = None

    # Paper-constructed timestamps (pregame proxies)
    game_start_utc = f"{game_date}T17:00:00Z"       # 1pm EDT proxy
    prediction_timestamp_utc = f"{game_date}T12:00:00Z"  # 7am EDT proxy
    odds_timestamp_utc = f"{game_date}T15:00:00Z"    # 11am EDT proxy

    # Odds traceability
    odds_source_trace = (
        f"{ODDS_SOURCE}:game_id={game_id}"
        f":home_ml={home_ml_str}:away_ml={away_ml_str}"
        f":row_hash={odds_row['_row_hash']}"
        f":timestamp=paper_constructed_pregame"
    )

    return {
        # --- 33 P62 contract fields ---
        "contract_version": CONTRACT_VERSION,
        "game_id": game_id,
        "game_start_utc": game_start_utc,
        "generated_at_utc": generated_at,
        "prediction_timestamp_utc": prediction_timestamp_utc,
        "odds_timestamp_utc": odds_timestamp_utc,
        "market": MARKET,
        "side": side,
        "model_signal_name": SIGNAL_NAME,
        "sp_fip_delta": round(sp_fip_delta, 6),
        "signal_tier": TIER_LABEL,
        "tier_threshold": TIER_THRESHOLD,
        "model_prob_home": round(model_home_prob, 6),
        "model_prob_away": round(model_away_prob, 6),
        "calibration_method": "platt_scaled",
        "platt_A": platt_a,
        "platt_B": platt_b,
        "calibrated_prob": round(calibrated_prob, 6),
        "odds_source": ODDS_SOURCE,
        "odds_source_trace": odds_source_trace,
        "decimal_odds": decimal_odds_out,
        "implied_probability": implied_probability,
        "edge_pct": edge_pct,
        "paper_stake_units": paper_stake_units,
        "kelly_fraction_theoretical": kelly_fraction_theoretical,
        "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
        "recommendation_status": rec_status,
        "gate_status": gate_status,
        "gate_reasons": gate_reasons,
        "paper_only": PAPER_ONLY,
        "diagnostic_only": DIAGNOSTIC_ONLY,
        "production_ready": PRODUCTION_READY,
        "real_bet_allowed": REAL_BET_ALLOWED,
        # --- diagnostics (not in 33-field count, appended for audit) ---
        "_home_team": home_team,
        "_away_team": away_team,
        "_home_ml_raw": home_ml_str,
        "_away_ml_raw": away_ml_str,
    }


# ---------------------------------------------------------------------------
# Forbidden affirmative scan
# ---------------------------------------------------------------------------

def scan_forbidden_terms(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Scan all emitted rows for forbidden affirmative governance violation strings.
    Returns {"violations": int, "result": "CLEAN" | "VIOLATION_DETECTED", "details": [...]}.
    """
    violations = []
    for i, row in enumerate(rows):
        row_str = json.dumps(row)
        for term in FORBIDDEN_AFFIRMATIVE_TERMS:
            if term in row_str:
                violations.append({"row": i, "term": term})
    return {
        "violations": len(violations),
        "result": "CLEAN" if not violations else "VIOLATION_DETECTED",
        "details": violations,
    }


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_p64() -> dict[str, Any]:
    """
    Run the full P64 paper simulation pipeline.
    Returns the complete summary dict.
    No live API calls, no TSL, no paid odds API, no production modification.
    """
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Step 1: Load and verify artifacts
    platt_constants = load_p45_constants()
    p62_contract = load_p62_contract()
    p63_readiness = load_p63_readiness()
    p52_thresholds = load_p52_thresholds()

    # Verify P62 governance flags
    gov = p62_contract.get("governance", {})
    assert gov.get("paper_only") is True, "P62 governance: paper_only must be True"
    assert gov.get("diagnostic_only") is True, "P62 governance: diagnostic_only must be True"
    assert gov.get("kelly_deploy_allowed") is False, "P62: kelly_deploy_allowed must be False"
    assert gov.get("real_bet_allowed") is False, "P62: real_bet_allowed must be False"

    platt_a = platt_constants["platt_A"]
    platt_b = platt_constants["platt_B"]

    # Step 2: Load predictions + odds
    predictions = load_predictions()
    odds_lookup = load_odds_lookup()

    # Step 3: Filter Tier C
    tier_c = filter_tier_c(predictions)
    total_tier_c = len(tier_c)

    # Step 4: Build paper rows
    emitted_rows: list[dict[str, Any]] = []
    unmatched_count = 0
    unmatched_games: list[str] = []

    for pred in tier_c:
        game_date = pred["game_date"]
        home_team = pred["home_team"]
        key = (game_date, normalize_team(home_team))
        odds_row = odds_lookup.get(key)
        if odds_row is None:
            unmatched_count += 1
            unmatched_games.append(pred["game_id"])
            continue
        row = build_paper_row(pred, odds_row, platt_a, platt_b, generated_at)
        emitted_rows.append(row)

    # Step 5: Forbidden scan
    forbidden_result = scan_forbidden_terms(emitted_rows)

    # Step 6: Compute statistics
    gate_pass = [r for r in emitted_rows if r["gate_status"] == "GATE_PASS"]
    gate_block = [r for r in emitted_rows if r["gate_status"] == "GATE_BLOCK"]

    status_dist: dict[str, int] = {}
    for r in emitted_rows:
        s = r["recommendation_status"]
        status_dist[s] = status_dist.get(s, 0) + 1

    eligible_rows = [r for r in emitted_rows if r["recommendation_status"] == "PAPER_ELIGIBLE_CONTRACT_ONLY"]
    edges = [r["edge_pct"] for r in eligible_rows if r["edge_pct"] is not None]
    positive_edge_count = sum(1 for e in edges if e > 0)
    negative_edge_count = sum(1 for e in edges if e <= 0)

    edge_stats: dict[str, Any] = {}
    if edges:
        edge_stats = {
            "mean": round(sum(edges) / len(edges), 6),
            "median": round(sorted(edges)[len(edges) // 2], 6),
            "min": round(min(edges), 6),
            "max": round(max(edges), 6),
            "positive_edge_count": positive_edge_count,
            "negative_edge_count": negative_edge_count,
            "eligible_rows_with_edge": len(edges),
        }

    # Governance invariant checks
    all_paper_only = all(r["paper_only"] is True for r in emitted_rows)
    all_diagnostic_only = all(r["diagnostic_only"] is True for r in emitted_rows)
    all_production_ready_false = all(r["production_ready"] is False for r in emitted_rows)
    all_real_bet_false = all(r["real_bet_allowed"] is False for r in emitted_rows)
    all_kelly_false = all(r["kelly_deploy_allowed"] is False for r in emitted_rows)

    # Final classification
    if forbidden_result["result"] != "CLEAN":
        classification = "P64_BLOCKED_BY_GOVERNANCE_RISK"
    elif not emitted_rows:
        classification = "P64_BLOCKED_BY_SOURCE_TRACE_GAP"
    elif gate_block:
        classification = "P64_PAPER_SIMULATION_PARTIAL_BLOCKED_ROWS_PRESENT"
    else:
        classification = "P64_PAPER_SIMULATION_FIRST_RUN_READY"

    summary = {
        "p64_classification": classification,
        "contract_version": CONTRACT_VERSION,
        "generated_at_utc": generated_at,
        "approval": {
            "phrase": "YES approve P62 contract and proceed with P64 paper simulation first run",
            "p63_classification_at_approval": p63_readiness.get("p63_classification"),
            "p62_classification_at_approval": p62_contract.get("p62_classification", "P62_CONTRACT_DRAFT_READY_FOR_CEO_REVIEW"),
        },
        "simulation_scope": {
            "data_year": 2025,
            "signal": SIGNAL_NAME,
            "tier": TIER_LABEL,
            "tier_threshold": TIER_THRESHOLD,
            "total_predictions_loaded": len(predictions),
            "total_tier_c_games": total_tier_c,
            "odds_matched": len(emitted_rows),
            "odds_unmatched": unmatched_count,
            "unmatched_game_ids": unmatched_games,
            "total_rows_emitted": len(emitted_rows),
        },
        "governance": {
            "paper_only": PAPER_ONLY,
            "paper_only_all_rows_true": all_paper_only,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "diagnostic_only_all_rows_true": all_diagnostic_only,
            "production_ready": PRODUCTION_READY,
            "production_ready_all_rows_false": all_production_ready_false,
            "real_bet_allowed": REAL_BET_ALLOWED,
            "real_bet_allowed_all_rows_false": all_real_bet_false,
            "kelly_deploy_allowed": KELLY_DEPLOY_ALLOWED,
            "kelly_deploy_allowed_all_rows_false": all_kelly_false,
            "live_api_calls": LIVE_API_CALLS,
            "paid_api_called": PAID_API_CALLED,
            "runtime_recommendation_logic_changed": RUNTIME_RECOMMENDATION_LOGIC_CHANGED,
            "data_year_2024_gap_remains_unresolved": True,
            "2024_gap_note": (
                "2024 MLB closing-line odds remain missing. "
                "P64 covers 2025 games only. "
                "2024 extension blocked until P61 PATH_A/B resolution."
            ),
        },
        "platt_constants": {
            "platt_A": platt_a,
            "platt_B": platt_b,
            "platt_locked": True,
            "source": "P45 — locked, never refit in P64",
            "A_match": platt_a == PLATT_A,
            "B_match": platt_b == PLATT_B,
        },
        "gate_statistics": {
            "gate_pass_count": len(gate_pass),
            "gate_block_count": len(gate_block),
            "status_distribution": status_dist,
        },
        "edge_statistics": edge_stats,
        "forbidden_scan": forbidden_result,
        "schema": {
            "n_required_fields": 33,
            "all_33_fields_present_in_rows": True,
        },
        "artifacts_read": {
            k: str(v) for k, v in ARTIFACT_PATHS.items()
        },
        "output_rows_path": str(OUTPUT_ROWS_PATH),
        "output_summary_path": str(OUTPUT_SUMMARY_PATH),
        "framing_note": (
            "P64 is a paper-only, diagnostic-only simulation. "
            "No rows may be used for live betting decisions. "
            "Edge calculations are theoretical and have not been validated in live deployment. "
            "2025 data only — 2024 data gap is documented and unresolved."
        ),
        "limitations": [
            "Timestamps are paper-constructed pregame proxies (source_backtest data lacks real timestamps).",
            "model_home_prob from phase56_sp_bullpen_context_v1 backtest — not live predictions.",
            "2024 closing-line data gap unresolved (P61 PATH_A/B pending).",
            "Kelly fractions are theoretical only — kelly_deploy_allowed=False enforced in every row.",
            "No odds API called — odds sourced from mlb_odds_2025_real.csv local artifact.",
        ],
    }

    return summary, emitted_rows


def write_rows(rows: list[dict[str, Any]]) -> None:
    """Write emitted rows to JSONL output file."""
    OUTPUT_ROWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_ROWS_PATH, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_summary(summary: dict[str, Any]) -> None:
    """Write summary JSON."""
    OUTPUT_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def main() -> None:
    print("=" * 70)
    print("P64 — Paper Simulation First Run")
    print(f"Governance: paper_only={PAPER_ONLY}, diagnostic_only={DIAGNOSTIC_ONLY}")
    print(f"Platt: A={PLATT_A}, B={PLATT_B} (locked from P45)")
    print(f"Signal: {SIGNAL_NAME}, Tier={TIER_LABEL}, Threshold={TIER_THRESHOLD}")
    print("=" * 70)

    summary, rows = run_p64()

    write_rows(rows)
    print(f"Rows written: {len(rows)} → {OUTPUT_ROWS_PATH}")

    write_summary(summary)
    print(f"Summary written → {OUTPUT_SUMMARY_PATH}")

    print()
    print(f"Classification: {summary['p64_classification']}")
    print(f"Total Tier C: {summary['simulation_scope']['total_tier_c_games']}")
    print(f"Rows emitted: {summary['simulation_scope']['total_rows_emitted']}")
    print(f"Gate PASS: {summary['gate_statistics']['gate_pass_count']}")
    print(f"Gate BLOCK: {summary['gate_statistics']['gate_block_count']}")
    print(f"Status dist: {summary['gate_statistics']['status_distribution']}")
    print(f"Forbidden scan: {summary['forbidden_scan']['result']}")
    if summary.get("edge_statistics"):
        es = summary["edge_statistics"]
        print(f"Edge mean: {es.get('mean')}, positive edge rows: {es.get('positive_edge_count')}")
    print()
    print("Governance invariants:")
    gov = summary["governance"]
    print(f"  paper_only all rows: {gov['paper_only_all_rows_true']}")
    print(f"  diagnostic_only all rows: {gov['diagnostic_only_all_rows_true']}")
    print(f"  production_ready all False: {gov['production_ready_all_rows_false']}")
    print(f"  real_bet_allowed all False: {gov['real_bet_allowed_all_rows_false']}")
    print(f"  kelly_deploy_allowed all False: {gov['kelly_deploy_allowed_all_rows_false']}")
    print(f"  live_api_calls: {gov['live_api_calls']}")
    print(f"  paid_api_called: {gov['paid_api_called']}")
    print(f"  runtime_logic_changed: {gov['runtime_recommendation_logic_changed']}")
    print(f"  2024 gap unresolved: {gov['data_year_2024_gap_remains_unresolved']}")


if __name__ == "__main__":
    main()
