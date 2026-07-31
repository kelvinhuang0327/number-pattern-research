"""MLB Daily Advisory Dry-run MVP.

Replay-first dry-run advisory system for MLB games.
All outputs are paper-only / no-real-bet / no-profit-claim.

Design:
  - Replay mode is first-class: uses 2025 historical prediction JSONL
  - Today mode auto-degrades to replay if current-day schedule unavailable
  - append-only paper betting ledger (JSONL)
  - Post-game review: PENDING_REVIEW (today) vs REVIEWED (replay)
  - Metrics via orchestrator.metrics_ssot (Brier score)
  - Phase71/72 de-risk guard applied when model_home_prob ∈ [0.65, 0.70)

Safety guarantees:
  PRODUCTION_MODIFIED        = False
  CANDIDATE_PATCH_CREATED    = False
  ALPHA_MODIFIED             = False
  PREDICTION_JSONL_OVERWRITTEN = False
  NO_EDGE_CLAIM              = True
  NO_PROFIT_CLAIM            = True
  PAPER_ONLY                 = True
  NO_REAL_BET                = True
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from typing import Any

# Import Metrics SSOT for canonical Brier calculation
from orchestrator.metrics_ssot import (
    calculate_brier_score,
    NO_PROFIT_CLAIM as _SSOT_NO_PROFIT_CLAIM,
    PRODUCTION_MODIFIED as _SSOT_PROD_MODIFIED,
)

# ─── Safety constants ─────────────────────────────────────────────────────────

PRODUCTION_MODIFIED: bool = False
CANDIDATE_PATCH_CREATED: bool = False
ALPHA_MODIFIED: bool = False
PREDICTION_JSONL_OVERWRITTEN: bool = False
NO_EDGE_CLAIM: bool = True
NO_PROFIT_CLAIM: bool = True
DIAGNOSTIC_ONLY: bool = True
PAPER_ONLY: bool = True
NO_REAL_BET: bool = True

MODULE_VERSION: str = "mlb_daily_advisory_v1"
COMPLETION_MARKER: str = "MLB_DAILY_ADVISORY_REPLAY_LEDGER_VERIFIED"

# ─── Gate constants (7 valid) ─────────────────────────────────────────────────

MLB_DAILY_ADVISORY_LEDGER_READY: str = "MLB_DAILY_ADVISORY_LEDGER_READY"
MLB_DAILY_ADVISORY_DRY_RUN_READY: str = "MLB_DAILY_ADVISORY_DRY_RUN_READY"
MLB_DAILY_ADVISORY_DATA_LIMITED: str = "MLB_DAILY_ADVISORY_DATA_LIMITED"
MLB_DAILY_ADVISORY_GOVERNANCE_RISK: str = "MLB_DAILY_ADVISORY_GOVERNANCE_RISK"
MLB_DAILY_ADVISORY_NEEDS_ODDS_SOURCE: str = "MLB_DAILY_ADVISORY_NEEDS_ODDS_SOURCE"
MLB_DAILY_ADVISORY_NEEDS_RESULT_SOURCE: str = "MLB_DAILY_ADVISORY_NEEDS_RESULT_SOURCE"
MLB_DAILY_ADVISORY_NOT_READY: str = "MLB_DAILY_ADVISORY_NOT_READY"

VALID_GATES: frozenset[str] = frozenset({
    MLB_DAILY_ADVISORY_LEDGER_READY,
    MLB_DAILY_ADVISORY_DRY_RUN_READY,
    MLB_DAILY_ADVISORY_DATA_LIMITED,
    MLB_DAILY_ADVISORY_GOVERNANCE_RISK,
    MLB_DAILY_ADVISORY_NEEDS_ODDS_SOURCE,
    MLB_DAILY_ADVISORY_NEEDS_RESULT_SOURCE,
    MLB_DAILY_ADVISORY_NOT_READY,
})

# ─── Default paths ────────────────────────────────────────────────────────────

DEFAULT_PREDICTION_JSONL: str = (
    "data/mlb_2025/derived/"
    "mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl"
)
DEFAULT_LEDGER_PATH: str = "reports/mlb_paper_betting_ledger.jsonl"

# ─── Advisory thresholds ──────────────────────────────────────────────────────

LEAN_THRESHOLD: float = 0.10       # model-market gap required for LEAN
WATCH_THRESHOLD: float = 0.05      # model-market gap required for WATCH_ONLY
DERISK_BAND_LOW: float = 0.65      # Phase71/72 de-risk band lower bound
DERISK_BAND_HIGH: float = 0.70     # Phase71/72 de-risk band upper bound (exclusive)
MIN_GAMES_FOR_METRICS: int = 3     # minimum games needed for Brier score

# ─── Market type identifiers ─────────────────────────────────────────────────

MARKET_MONEYLINE: str = "moneyline"
MARKET_RUNLINE: str = "runline"
MARKET_TOTAL: str = "total"

# ─── Recommendation values ────────────────────────────────────────────────────

REC_PASS: str = "PASS"
REC_WATCH_ONLY: str = "WATCH_ONLY"
REC_LEAN_HOME: str = "LEAN_HOME"
REC_LEAN_AWAY: str = "LEAN_AWAY"
REC_MARKET_ONLY_SHADOW: str = "MARKET_ONLY_SHADOW"
REC_UNAVAILABLE: str = "UNAVAILABLE"

# ════════════════════════════════════════════════════════════════════════════
# SECTION A — Data Loading
# ════════════════════════════════════════════════════════════════════════════


def load_prediction_rows(jsonl_path: str) -> list[dict]:
    """Load prediction rows from JSONL. Returns empty list if file missing."""
    rows: list[dict] = []
    if not os.path.exists(jsonl_path):
        return rows
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def find_games_for_date(rows: list[dict], date_str: str) -> list[dict]:
    """Filter prediction rows to a specific game_date."""
    return [r for r in rows if r.get("game_date") == date_str]


def get_all_dates(rows: list[dict]) -> list[str]:
    """Return sorted list of unique game_dates available in the dataset."""
    return sorted(set(r["game_date"] for r in rows if r.get("game_date")))


def get_latest_replay_date(rows: list[dict]) -> str | None:
    """Return the most recent available game_date (for replay fallback)."""
    dates = get_all_dates(rows)
    return dates[-1] if dates else None


def determine_effective_mode(
    rows: list[dict],
    date_str: str,
    requested_mode: str,
) -> tuple[str, bool, str | None]:
    """
    Determine whether the advisory can run as requested.

    Returns:
        effective_mode: 'today' or 'replay'
        actual_today_schedule_unavailable: True if today's data was missing
        actual_date_used: the date actually used for game lookup
    """
    games = find_games_for_date(rows, date_str)
    if games:
        return requested_mode, False, date_str

    # No data for requested date — auto-fallback to replay
    fallback_date = get_latest_replay_date(rows)
    return "replay", True, fallback_date


# ════════════════════════════════════════════════════════════════════════════
# SECTION B — Advisory Computation
# ════════════════════════════════════════════════════════════════════════════


def build_confidence_band(model_home_prob: float) -> str:
    """Classify model probability into a named confidence band."""
    if model_home_prob >= DERISK_BAND_HIGH:
        return "VERY_STRONG_HOME_GTE_0.70"
    elif model_home_prob >= DERISK_BAND_LOW:
        return "STRONG_HOME_0.65_0.70_DERISK"
    elif model_home_prob >= 0.55:
        return "MODERATE_HOME_0.55_0.65"
    elif model_home_prob >= 0.50:
        return "SLIGHT_HOME_0.50_0.55"
    elif model_home_prob >= 0.45:
        return "NEAR_PICK_EM_0.45_0.50"
    else:
        return "SLIGHT_AWAY_LT_0.45"


def check_phase71_derisk_flag(model_home_prob: float) -> bool:
    """True if model_home_prob is in Phase71/72 de-risk band [0.65, 0.70)."""
    return DERISK_BAND_LOW <= model_home_prob < DERISK_BAND_HIGH


def build_risk_flags(
    row: dict,
    model_home_prob: float,
    market_home_prob: float,
    model_minus_market: float,
    phase71_flag: bool,
) -> list[str]:
    """Build list of risk flags for a game advisory."""
    flags: list[str] = []
    if phase71_flag:
        flags.append("IN_PHASE71_DERISK_BAND")
    if abs(model_minus_market) < 0.02:
        flags.append("MODEL_MARKET_NEAR_IDENTICAL")
    p0 = row.get("p0_features", {})
    if not p0.get("sp_fip_delta_available", False):
        flags.append("SP_FIP_DELTA_UNAVAILABLE")
    if not p0.get("park_factor_available", False):
        flags.append("PARK_FACTOR_UNAVAILABLE")
    if not (0.0 < market_home_prob < 1.0):
        flags.append("MARKET_PROB_OUT_OF_RANGE")
    return flags


def determine_moneyline_recommendation(
    model_minus_market: float,
    phase71_derisk_flag: bool,
    risk_flags: list[str],
    model_home_prob: float,
    market_home_prob: float,
) -> tuple[str, str, str | None]:
    """
    Apply conservative moneyline recommendation rules.

    Returns:
        recommendation: one of PASS / WATCH_ONLY / LEAN_HOME / LEAN_AWAY / MARKET_ONLY_SHADOW
        reason: human-readable rationale string
        paper_selection: 'HOME', 'AWAY', or None
    """
    # Phase71/72 de-risk band always triggers MARKET_ONLY_SHADOW — no lean allowed
    if phase71_derisk_flag:
        reason = (
            f"model_home_prob={model_home_prob:.3f} in Phase71/72 de-risk band "
            f"[{DERISK_BAND_LOW},{DERISK_BAND_HIGH}); "
            "G1_band_shadow applied per Phase72 guard spec; "
            "market is historically superior in this band (5/5 windows per Phase71); "
            "no lean generated — market-only shadow recorded"
        )
        return REC_MARKET_ONLY_SHADOW, reason, None

    # Block lean if major risk flags present
    major_flags = [f for f in risk_flags if f == "MARKET_PROB_OUT_OF_RANGE"]

    if not major_flags:
        if model_minus_market >= LEAN_THRESHOLD:
            reason = (
                f"model({model_home_prob:.3f}) exceeds market({market_home_prob:.3f}) "
                f"by {model_minus_market:.3f} >= LEAN_THRESHOLD={LEAN_THRESHOLD}; "
                "no major risk flags; conservative lean applied"
            )
            return REC_LEAN_HOME, reason, "HOME"
        elif model_minus_market <= -LEAN_THRESHOLD:
            reason = (
                f"market({market_home_prob:.3f}) exceeds model({model_home_prob:.3f}) "
                f"by {abs(model_minus_market):.3f} >= LEAN_THRESHOLD={LEAN_THRESHOLD}; "
                "no major risk flags; conservative lean applied"
            )
            return REC_LEAN_AWAY, reason, "AWAY"

    # WATCH_ONLY — observable signal but insufficient for lean
    if abs(model_minus_market) >= WATCH_THRESHOLD:
        reason = (
            f"model-market gap={abs(model_minus_market):.3f} in "
            f"[{WATCH_THRESHOLD},{LEAN_THRESHOLD}); "
            "signal present but insufficient evidence for lean"
        )
        return REC_WATCH_ONLY, reason, None

    # PASS — default, no actionable signal
    reason = (
        f"model-market gap={abs(model_minus_market):.3f} < {WATCH_THRESHOLD}; "
        "no actionable signal"
    )
    return REC_PASS, reason, None


def build_market_coverage_matrix(row: dict) -> dict:
    """
    Build market coverage matrix for a single game.
    Explicitly documents what data is available vs unavailable.
    """
    market_prob = row.get("market_home_prob_no_vig")
    has_market_prob = isinstance(market_prob, (int, float)) and 0.0 < float(market_prob) < 1.0
    has_raw_odds = bool(row.get("home_ml")) and row.get("home_ml") != ""
    has_result = (
        row.get("home_win") is not None
        and row.get("home_win") != ""
    )
    return {
        "moneyline_available": has_market_prob,
        "runline_available": False,        # run line spread/odds not in prediction JSONL
        "total_available": False,           # totals line/odds not in prediction JSONL
        "result_available": has_result,
        "odds_available": has_raw_odds,     # raw ML odds (home_ml/away_ml)
        "market_home_prob_available": has_market_prob,
        "closing_market_available": False,  # no separate closing odds data
    }


def _derive_paper_odds(market_prob: float, side: str) -> float | None:
    """Derive implied fair decimal odds from market probability (no vig)."""
    if side == "HOME" and 0.0 < market_prob < 1.0:
        return round(1.0 / market_prob, 3)
    elif side == "AWAY" and 0.0 < market_prob < 1.0:
        return round(1.0 / (1.0 - market_prob), 3)
    return None


def _make_advisory_id(game_date: str, game_id: str) -> str:
    """Generate deterministic advisory_id from game_date + game_id."""
    source = f"{game_date}|{game_id}"
    return "ADV_" + hashlib.sha256(source.encode()).hexdigest()[:12]


def build_advisory(
    row: dict,
    advisory_idx: int,
    effective_mode: str,
) -> dict:
    """
    Build a single game advisory from a prediction row.
    All outputs are paper_only=True, no_real_bet=True.
    """
    game_date = row.get("game_date", "")
    game_id = row.get("game_id", f"GAME_{advisory_idx:04d}")
    home_team = row.get("home_team", "")
    away_team = row.get("away_team", "")

    # Pitcher info from p0_features
    p0: dict = row.get("p0_features", {})
    probable_home_pitcher: str | None = p0.get("sp_home_pitcher") or None
    probable_away_pitcher: str | None = p0.get("sp_away_pitcher") or None

    model_home_prob = float(row.get("model_home_prob", 0.5))
    market_home_prob = float(row.get("market_home_prob_no_vig", 0.5))
    model_minus_market = round(model_home_prob - market_home_prob, 4)

    confidence_band = build_confidence_band(model_home_prob)
    phase71_flag = check_phase71_derisk_flag(model_home_prob)
    risk_flags = build_risk_flags(
        row, model_home_prob, market_home_prob, model_minus_market, phase71_flag
    )

    # Favorite determination
    if model_home_prob > 0.52:
        favorite_side = "HOME"
        favorite_prob = round(model_home_prob, 4)
    elif model_home_prob < 0.48:
        favorite_side = "AWAY"
        favorite_prob = round(1.0 - model_home_prob, 4)
    else:
        favorite_side = "PICK"
        favorite_prob = round(model_home_prob, 4)

    # Moneyline recommendation
    ml_rec, ml_reason, ml_selection = determine_moneyline_recommendation(
        model_minus_market, phase71_flag, risk_flags, model_home_prob, market_home_prob
    )

    # RunLine and Total: data unavailable in prediction JSONL
    unavailable_fields = [
        "runline_spread",
        "runline_odds_home",
        "runline_odds_away",
        "total_line",
        "total_odds_over",
        "total_odds_under",
    ]

    # Phase72 guard applied
    phase72_guard: str | None = "G1_band_shadow" if phase71_flag else None

    advisory_id = _make_advisory_id(game_date, game_id)
    coverage_matrix = build_market_coverage_matrix(row)

    # Model prediction availability (set by current/fixture source adapter)
    model_prediction_available: bool = row.get("_model_prediction_available", True)

    # Force PASS when no model prediction available (market-only advisory card)
    if not model_prediction_available:
        ml_rec = REC_PASS
        ml_reason = (
            "model_prediction_unavailable: market-only advisory card; "
            "no model prediction for this game; LEAN not allowed"
        )
        ml_selection = None

    return {
        "advisory_id": advisory_id,
        "game_id": game_id,
        "game_date": game_date,
        "home_team": home_team,
        "away_team": away_team,
        "probable_home_pitcher": probable_home_pitcher,
        "probable_away_pitcher": probable_away_pitcher,
        "model_home_prob": model_home_prob,
        "market_home_prob": market_home_prob,
        "model_minus_market": model_minus_market,
        "confidence_band": confidence_band,
        "favorite_side": favorite_side,
        "favorite_prob": favorite_prob,
        "phase71_market_derisk_flag": phase71_flag,
        "phase72_guard_candidate_applied": phase72_guard,
        "moneyline_recommendation": ml_rec,
        "moneyline_paper_selection": ml_selection,
        "runline_recommendation": REC_UNAVAILABLE,
        "total_recommendation": REC_UNAVAILABLE,
        "recommendation_reason": ml_reason,
        "risk_flags": risk_flags,
        "unavailable_fields": unavailable_fields,
        "market_coverage_matrix": coverage_matrix,
        "model_prediction_available": model_prediction_available,
        "paper_only": True,
        "no_real_bet": True,
        # Internal fields for post-game review (stripped from JSON output)
        "_home_win": row.get("home_win"),
        "_effective_mode": effective_mode,
    }


# ════════════════════════════════════════════════════════════════════════════
# SECTION C — Paper Betting Ledger
# ════════════════════════════════════════════════════════════════════════════


def load_existing_ledger_ids(ledger_path: str) -> set[str]:
    """Load existing ledger_ids from JSONL to prevent duplicate append."""
    existing: set[str] = set()
    if not os.path.exists(ledger_path):
        return existing
    with open(ledger_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    entry = json.loads(line)
                    lid = entry.get("ledger_id", "")
                    if lid:
                        existing.add(lid)
                except json.JSONDecodeError:
                    continue
    return existing


def compute_result_status(
    paper_selection: str | None,
    home_win: Any,
    effective_mode: str,
) -> str:
    """
    Determine result_status.
    Only replay mode with available home_win yields WON/LOST.
    """
    if paper_selection is None:
        return "UNKNOWN"
    if home_win is None or home_win == "":
        return "PENDING"
    if effective_mode != "replay":
        return "PENDING"
    try:
        hw = int(home_win)
    except (ValueError, TypeError):
        return "UNKNOWN"
    if paper_selection == "HOME":
        return "WON" if hw == 1 else "LOST"
    elif paper_selection == "AWAY":
        return "WON" if hw == 0 else "LOST"
    return "UNKNOWN"


def build_ledger_entry(
    advisory: dict,
    market_type: str,
    recommendation: str,
    paper_selection: str | None,
    existing_ids: set[str],
    created_at: str,
) -> dict | None:
    """
    Build a single paper betting ledger entry.

    Returns None if:
      - recommendation is PASS or UNAVAILABLE (nothing to track)
      - ledger_id already exists (duplicate prevention)
    """
    if recommendation in {REC_PASS, REC_UNAVAILABLE}:
        return None

    advisory_id = advisory["advisory_id"]
    ledger_id = f"{advisory_id}_{market_type.upper()}"
    if ledger_id in existing_ids:
        return None  # duplicate — skip

    effective_mode = advisory.get("_effective_mode", "replay")
    home_win = advisory.get("_home_win")
    result_status = compute_result_status(paper_selection, home_win, effective_mode)

    # Review status
    if result_status == "PENDING":
        review_status = "PENDING_REVIEW"
        realized_outcome = None
        paper_profit_loss_units = None
    else:
        review_status = "REVIEWED"
        realized_outcome = (
            "home_win" if home_win == 1 else "away_win"
        ) if home_win is not None and home_win != "" else None
        # Paper P&L: ±1 unit notation — paper-only, no real money
        market_prob = advisory.get("market_home_prob", 0.5)
        if result_status == "WON":
            odds = _derive_paper_odds(market_prob, paper_selection or "HOME")
            paper_profit_loss_units = round((odds - 1.0), 3) if odds else 1.0
        elif result_status == "LOST":
            paper_profit_loss_units = -1.0
        else:
            paper_profit_loss_units = None

    # Derive paper_odds from market probability (not actual market odds)
    market_prob = advisory.get("market_home_prob", 0.5)
    paper_odds = _derive_paper_odds(market_prob, paper_selection or "HOME") if paper_selection else None

    return {
        "ledger_id": ledger_id,
        "advisory_id": advisory_id,
        "game_id": advisory["game_id"],
        "game_date": advisory["game_date"],
        "market_type": market_type,
        "recommendation": recommendation,
        "paper_selection": paper_selection,
        "paper_odds": paper_odds,
        "paper_odds_note": "derived_from_market_prob_no_vig_not_actual_market_odds",
        "model_prob": advisory.get("model_home_prob"),
        "market_prob": advisory.get("market_home_prob"),
        "closing_market_prob": None,
        "result_status": result_status,
        "realized_outcome": realized_outcome,
        "paper_profit_loss_units": paper_profit_loss_units,
        "paper_profit_note": "1_unit_notation_paper_only_no_real_money",
        "clv": None,
        "review_status": review_status,
        "created_at": created_at,
        "paper_only": True,
        "no_real_bet": True,
    }


def write_ledger_entries(entries: list[dict], ledger_path: str) -> int:
    """Append new entries to the paper betting ledger JSONL. Returns count written."""
    if not entries:
        return 0
    dirpath = os.path.dirname(ledger_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return len(entries)


# ════════════════════════════════════════════════════════════════════════════
# SECTION D — Review, Metrics, and Feedback Loop
# ════════════════════════════════════════════════════════════════════════════


def build_review_summary(
    advisories: list[dict],
    ledger_entries: list[dict],
) -> dict:
    """
    Build review summary from advisories and ledger entries.
    Uses metrics_ssot.calculate_brier_score for Brier metrics.
    """
    ml_recs = [a["moneyline_recommendation"] for a in advisories]

    pass_count = ml_recs.count(REC_PASS)
    watch_only_count = ml_recs.count(REC_WATCH_ONLY)
    lean_count = ml_recs.count(REC_LEAN_HOME) + ml_recs.count(REC_LEAN_AWAY)
    market_shadow_count = ml_recs.count(REC_MARKET_ONLY_SHADOW)

    pending_review_entries = [e for e in ledger_entries if e["review_status"] == "PENDING_REVIEW"]
    reviewed_entries = [e for e in ledger_entries if e["review_status"] == "REVIEWED"]

    wins = sum(1 for e in reviewed_entries if e["result_status"] == "WON")
    losses = sum(1 for e in reviewed_entries if e["result_status"] == "LOST")
    pushes = sum(1 for e in reviewed_entries if e["result_status"] == "PUSH")

    # Brier score using metrics_ssot (moneyline model_home_prob)
    reviewed_with_result = [
        a for a in advisories
        if a.get("_home_win") is not None and a.get("_home_win") != ""
    ]
    brier_result: dict | None = None
    if len(reviewed_with_result) >= MIN_GAMES_FOR_METRICS:
        probs = [float(a["model_home_prob"]) for a in reviewed_with_result]
        outcomes = [int(a["_home_win"]) for a in reviewed_with_result]
        br = calculate_brier_score(probs, outcomes)
        brier_result = {
            "n": br.n,
            "brier": round(br.brier, 4),
            "baseline_brier": round(br.baseline_brier, 4),
            "bss_vs_baseline": round(br.bss_vs_baseline, 4),
            "market": "moneyline_model_home_prob",
            "ssot_function": "calculate_brier_score",
        }

    # Lean accuracy
    lean_advisories = [
        a for a in advisories
        if a["moneyline_recommendation"] in {REC_LEAN_HOME, REC_LEAN_AWAY}
        and a.get("_home_win") is not None
        and a.get("_home_win") != ""
    ]
    correct_leans = 0
    for a in lean_advisories:
        hw = int(a["_home_win"])
        rec = a["moneyline_recommendation"]
        if (rec == REC_LEAN_HOME and hw == 1) or (rec == REC_LEAN_AWAY and hw == 0):
            correct_leans += 1
    lean_accuracy = (correct_leans / len(lean_advisories)) if lean_advisories else None

    return {
        "total_advisories": len(advisories),
        "total_paper_bets": len(ledger_entries),
        "pass_count": pass_count,
        "watch_only_count": watch_only_count,
        "lean_count": lean_count,
        "market_only_shadow_count": market_shadow_count,
        "pending_result_count": len(pending_review_entries),
        "reviewed_count": len(reviewed_entries),
        "win_loss_push_summary": {
            "won": wins,
            "lost": losses,
            "push": pushes,
            "unknown": len(reviewed_entries) - wins - losses - pushes,
        },
        "brier_by_market_type": {
            "moneyline": brier_result,
            "runline": None,
            "total": None,
        },
        "recommendation_accuracy": {
            "lean_count": len(lean_advisories),
            "lean_correct": correct_leans,
            "lean_accuracy": round(lean_accuracy, 3) if lean_accuracy is not None else None,
        },
        "clv_summary": None,
        "metrics_ssot_used": True,
        "metrics_ssot_module": "orchestrator.metrics_ssot",
    }


def build_failure_notes(
    advisories: list[dict],
    ledger_entries: list[dict],
    review_summary: dict,
) -> dict:
    """
    Build feedback loop failure notes.
    GOVERNANCE: no auto-model modification, no alpha change, no stake sizing.
    """
    lean_advisories = [
        a for a in advisories
        if a["moneyline_recommendation"] in {REC_LEAN_HOME, REC_LEAN_AWAY}
    ]
    lost_leans = [
        e for e in ledger_entries
        if e.get("review_status") == "REVIEWED" and e.get("result_status") == "LOST"
    ]

    observations: list[str] = []
    suspected_failure_modes: list[str] = []

    if lean_advisories:
        lean_acc = review_summary["recommendation_accuracy"].get("lean_accuracy")
        observations.append(
            f"{len(lean_advisories)} LEAN recommendation(s) generated; "
            f"lean_accuracy={lean_acc}"
        )

    if lost_leans:
        observations.append(f"{len(lost_leans)} paper bet(s) resulted in LOST outcome this session")
        suspected_failure_modes.append(
            "model-market divergence at open may not persist to game time; "
            "line movement risk not modeled"
        )

    shadow_count = review_summary.get("market_only_shadow_count", 0)
    if shadow_count:
        observations.append(
            f"{shadow_count} game(s) in Phase71/72 de-risk band [0.65,0.70); "
            "MARKET_ONLY_SHADOW applied; no lean generated per Phase72 governance"
        )

    if not observations:
        observations.append("No significant failure pattern detected in this session")

    if not suspected_failure_modes:
        suspected_failure_modes.append("Insufficient sample to determine failure mode")

    return {
        "observation": observations,
        "suspected_failure_mode": suspected_failure_modes,
        "proposed_next_audit": [
            "Accumulate 30+ replay sessions to evaluate lean accuracy stability",
            "Cross-reference LEAN outcomes with Phase71 market superiority segments",
            "Monitor MARKET_ONLY_SHADOW outcomes vs LEAN outcomes across sessions",
            "Evaluate whether model-market gap > 0.10 is predictive in out-of-band games",
        ],
        "blocked_auto_change_reason": (
            "human_review_required: governance rules prohibit auto-modification of "
            "model, alpha, or stake sizing based on dry-run advisory results"
        ),
        "human_review_required": True,
        "alpha_change_blocked": True,
        "model_change_blocked": True,
        "stake_change_blocked": True,
    }


def determine_gate(
    advisories: list[dict],
    ledger_entries: list[dict],
    effective_mode: str,
) -> tuple[str, str]:
    """Determine the gate and rationale. Gate must be in VALID_GATES."""
    if not advisories:
        return (
            MLB_DAILY_ADVISORY_NOT_READY,
            "No advisories generated; check prediction JSONL path and date",
        )

    # Safety check: governance
    all_safe = all(
        a.get("paper_only") is True and a.get("no_real_bet") is True
        for a in advisories
    )
    if not all_safe:
        return (
            MLB_DAILY_ADVISORY_GOVERNANCE_RISK,
            "Some advisories missing paper_only or no_real_bet safety flags",
        )

    has_reviewed_results = any(
        a.get("_home_win") is not None and a.get("_home_win") != ""
        for a in advisories
    )
    has_ledger = len(ledger_entries) > 0

    # Replay mode with reviewed results → LEDGER_READY (full closed-loop)
    if effective_mode == "replay" and has_reviewed_results and has_ledger:
        return (
            MLB_DAILY_ADVISORY_LEDGER_READY,
            "Replay mode produced: advisory + append-only ledger + reviewed results "
            "+ Brier metrics (metrics_ssot) + failure notes + paper-only safety flags",
        )

    # Advisory + ledger work, results pending (today mode)
    if has_ledger and not has_reviewed_results:
        return (
            MLB_DAILY_ADVISORY_DRY_RUN_READY,
            "Daily advisory and paper ledger operational; results pending for today's games",
        )

    # Advisory + ledger + partial review
    if has_ledger:
        return (
            MLB_DAILY_ADVISORY_LEDGER_READY,
            "Advisory + ledger + review operational",
        )

    # Advisory works but all PASS (no ledger entries) — still functional
    return (
        MLB_DAILY_ADVISORY_DRY_RUN_READY,
        "Daily advisory operational; all games returned PASS (no ledger entries written)",
    )


# ════════════════════════════════════════════════════════════════════════════
# SECTION E — Markdown Report
# ════════════════════════════════════════════════════════════════════════════


def generate_markdown_report(payload: dict, md_path: str) -> None:
    """Write a human-readable markdown report from the advisory payload."""
    req_date = payload.get("requested_date", "")
    eff_mode = payload.get("effective_mode", "")
    req_mode = payload.get("requested_mode", "")
    actual_unavail = payload.get("actual_today_schedule_unavailable", False)
    actual_date = payload.get("actual_date_used", "")
    total_adv = payload.get("total_advisories", 0)
    gate = payload.get("gate", "")
    rs = payload.get("review_summary", {})
    cov = payload.get("market_coverage_matrix_summary", {})
    fn = payload.get("failure_notes", {})

    lines: list[str] = []
    lines.append("# MLB Daily Advisory — Dry-run MVP Report")
    lines.append("")
    lines.append("> **⚠️ PAPER-ONLY — DRY-RUN — NO REAL BET — NO PROFIT CLAIM**")
    lines.append(">")
    lines.append("> 本報告所有投注建議均為 paper-only 模擬，不代表任何真實下注、")
    lines.append("> 真實獲利、或真實 edge 聲明。所有結果僅供研究與回測使用。")
    lines.append("")
    lines.append(f"**Date:** {req_date}")
    lines.append(f"**Requested Mode:** {req_mode}")
    lines.append(f"**Effective Mode:** {eff_mode}")
    if actual_unavail:
        lines.append(f"**actual_today_schedule_unavailable:** true")
        lines.append(f"**Replay Fallback Date:** {actual_date}")
    lines.append(f"**Total Advisories:** {total_adv}")
    lines.append(f"**Report Generated:** {payload.get('run_timestamp_utc', '')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Safety Flags")
    lines.append("")
    safety = payload.get("safety", {})
    for k, v in safety.items():
        lines.append(f"- **{k}**: `{v}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Market Coverage Matrix")
    lines.append("")
    lines.append("| Market | Available | Notes |")
    lines.append("|--------|-----------|-------|")
    cov_notes = cov.get("coverage_notes", [])
    for market in ["moneyline", "runline", "total", "result", "odds", "market_home_prob", "closing_market"]:
        key = f"{market}_available"
        avail = cov.get(key, False)
        avail_str = "✅ YES" if avail else "❌ NO"
        note = next((n for n in cov_notes if market in n), "")
        lines.append(f"| {market} | {avail_str} | {note[:80]} |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Advisory Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total Advisories | {rs.get('total_advisories', 0)} |")
    lines.append(f"| PASS | {rs.get('pass_count', 0)} |")
    lines.append(f"| WATCH_ONLY | {rs.get('watch_only_count', 0)} |")
    lines.append(f"| LEAN (HOME+AWAY) | {rs.get('lean_count', 0)} |")
    lines.append(f"| MARKET_ONLY_SHADOW | {rs.get('market_only_shadow_count', 0)} |")
    lines.append(f"| Ledger Entries Written | {payload.get('total_ledger_entries_written', 0)} |")
    lines.append(f"| Pending Review | {rs.get('pending_result_count', 0)} |")
    lines.append(f"| Reviewed | {rs.get('reviewed_count', 0)} |")
    lines.append("")
    wl = rs.get("win_loss_push_summary", {})
    if wl.get("won", 0) + wl.get("lost", 0) > 0:
        lines.append(f"**Paper bet W/L:** {wl.get('won',0)}W / {wl.get('lost',0)}L / {wl.get('push',0)}P")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Brier Score (Metrics SSOT)")
    lines.append("")
    brier_ml = rs.get("brier_by_market_type", {}).get("moneyline")
    if brier_ml:
        lines.append(f"- **n**: {brier_ml['n']}")
        lines.append(f"- **brier**: {brier_ml['brier']}")
        lines.append(f"- **baseline_brier**: {brier_ml['baseline_brier']}")
        lines.append(f"- **bss_vs_baseline**: {brier_ml['bss_vs_baseline']}")
        lines.append(f"- **ssot_function**: `{brier_ml.get('ssot_function','calculate_brier_score')}`")
    else:
        lines.append("Brier score: unavailable (insufficient reviewed games or no moneyline data)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Game Advisories")
    lines.append("")
    advisories = payload.get("advisories", [])
    if advisories:
        lines.append("| # | Date | Away | Home | Model | Market | Gap | ML Rec | Risk Flags |")
        lines.append("|---|------|------|------|-------|--------|-----|--------|------------|")
        for i, adv in enumerate(advisories):
            flags_str = ", ".join(adv.get("risk_flags", []))[:40] or "—"
            lines.append(
                f"| {i+1} | {adv.get('game_date','')} | {adv.get('away_team','')} | "
                f"{adv.get('home_team','')} | {adv.get('model_home_prob',0):.3f} | "
                f"{adv.get('market_home_prob',0):.3f} | {adv.get('model_minus_market',0):+.3f} | "
                f"**{adv.get('moneyline_recommendation','')}** | {flags_str} |"
            )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Feedback Loop — Failure Notes")
    lines.append("")
    lines.append("### Observations")
    for obs in fn.get("observation", []):
        lines.append(f"- {obs}")
    lines.append("")
    lines.append("### Suspected Failure Modes")
    for sfm in fn.get("suspected_failure_mode", []):
        lines.append(f"- {sfm}")
    lines.append("")
    lines.append("### Proposed Next Audit")
    for pna in fn.get("proposed_next_audit", []):
        lines.append(f"- {pna}")
    lines.append("")
    lines.append(f"**Blocked Auto Change:** {fn.get('blocked_auto_change_reason','')}")
    lines.append(f"**human_review_required:** `{fn.get('human_review_required', True)}`")
    lines.append(f"**alpha_change_blocked:** `{fn.get('alpha_change_blocked', True)}`")
    lines.append(f"**model_change_blocked:** `{fn.get('model_change_blocked', True)}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Phase Chain")
    lines.append("")
    for k, v in payload.get("phase_chain", {}).items():
        lines.append(f"- **{k}**: `{v}`")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Gate Conclusion")
    lines.append("")
    lines.append(f"**Gate: `{gate}`**")
    lines.append("")
    lines.append(f"> {payload.get('gate_rationale', '')}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## No Profit Claim")
    lines.append("")
    lines.append(
        "本系統不聲稱已找到可盈利的投注 edge。"
        "所有 paper advisory 均為研究目的，不代表任何真實獲利預期。"
        "Brier score 與其他 metrics 僅為統計診斷工具。"
    )
    lines.append("")
    lines.append("**NO_PROFIT_CLAIM = True**")
    lines.append("**NO_EDGE_CLAIM = True**")
    lines.append("**PAPER_ONLY = True**")
    lines.append("**NO_REAL_BET = True**")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"## Completion Marker")
    lines.append("")
    lines.append(f"`{COMPLETION_MARKER}`")
    lines.append("")

    dirpath = os.path.dirname(md_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


# ════════════════════════════════════════════════════════════════════════════
# SECTION F — Main Orchestration
# ════════════════════════════════════════════════════════════════════════════


def run_mlb_daily_advisory(
    date_str: str,
    mode: str = "today",
    limit: int = 15,
    prediction_jsonl_path: str = DEFAULT_PREDICTION_JSONL,
    ledger_path: str = DEFAULT_LEDGER_PATH,
    report_path: str | None = None,
    markdown_path: str | None = None,
    *,
    write_reports: bool = True,
    # Current source integration parameters (optional)
    override_games: list[dict] | None = None,
    source_mode: str = "replay",
    fixture_source_used: bool = False,
    current_source_reachable: bool = False,
    model_prediction_available: bool = True,
) -> dict:
    """
    Main orchestration function for MLB Daily Advisory dry-run.

    Args:
        date_str: Target date YYYY-MM-DD
        mode: 'today' or 'replay'
        limit: Maximum games to process
        prediction_jsonl_path: Path to prediction JSONL
        ledger_path: Path to append-only paper betting ledger
        report_path: Path to write JSON report (None = don't write)
        markdown_path: Path to write markdown report (None = don't write)
        write_reports: If False, skip all disk writes (for unit tests)

    Returns:
        Full report payload dict (paper-only / no-real-bet)
    """
    run_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if override_games is not None:
        # Current/fixture source path: games pre-loaded by caller
        games = override_games[:limit]
        effective_mode = mode
        actual_today_unavailable = False
        actual_date_used = date_str
    else:
        # Normal JSONL replay path
        all_rows = load_prediction_rows(prediction_jsonl_path)
        effective_mode, actual_today_unavailable, actual_date_used = determine_effective_mode(
            all_rows, date_str, mode
        )
        games = []
        if actual_date_used:
            games = find_games_for_date(all_rows, actual_date_used)[:limit]

    # Build advisories
    advisories = [
        build_advisory(row, idx, effective_mode)
        for idx, row in enumerate(games)
    ]

    # Load existing ledger IDs for duplicate prevention
    existing_ids: set[str] = set()
    if write_reports:
        existing_ids = load_existing_ledger_ids(ledger_path)

    # Build ledger entries
    new_entries: list[dict] = []
    duplicated_skipped = 0

    for advisory in advisories:
        # Only moneyline (runline/total are UNAVAILABLE)
        ml_rec = advisory["moneyline_recommendation"]
        ml_sel = advisory.get("moneyline_paper_selection")

        already_seen = existing_ids | {e["ledger_id"] for e in new_entries}
        ml_entry = build_ledger_entry(
            advisory, MARKET_MONEYLINE, ml_rec, ml_sel, already_seen, run_ts
        )
        if ml_entry is not None:
            new_entries.append(ml_entry)
        elif ml_rec not in {REC_PASS, REC_UNAVAILABLE}:
            duplicated_skipped += 1

    # Write ledger (append-only)
    entries_written = 0
    if write_reports:
        entries_written = write_ledger_entries(new_entries, ledger_path)
    else:
        entries_written = len(new_entries)

    # Build review summary (uses metrics_ssot internally)
    review_summary = build_review_summary(advisories, new_entries)

    # Build failure notes
    failure_notes = build_failure_notes(advisories, new_entries, review_summary)

    # Determine gate
    gate, gate_rationale = determine_gate(advisories, new_entries, effective_mode)
    assert gate in VALID_GATES, f"Gate {gate!r} not in VALID_GATES"

    # Build report payload
    # Strip internal "_" keys from advisory output
    clean_advisories = [
        {k: v for k, v in a.items() if not k.startswith("_")}
        for a in advisories
    ]

    payload = {
        "module_version": MODULE_VERSION,
        "run_timestamp_utc": run_ts,
        "requested_date": date_str,
        "requested_mode": mode,
        "effective_mode": effective_mode,
        "actual_today_schedule_unavailable": actual_today_unavailable,
        "actual_date_used": actual_date_used,
        "data_source": prediction_jsonl_path,
        "limit_applied": limit,
        "total_games_loaded": len(games),
        "total_advisories": len(advisories),
        "total_ledger_entries_written": entries_written,
        "duplicated_skipped_count": duplicated_skipped,
        "safety": {
            "production_modified": PRODUCTION_MODIFIED,
            "candidate_patch_created": CANDIDATE_PATCH_CREATED,
            "alpha_modified": ALPHA_MODIFIED,
            "prediction_jsonl_overwritten": PREDICTION_JSONL_OVERWRITTEN,
            "no_edge_claim": NO_EDGE_CLAIM,
            "no_profit_claim": NO_PROFIT_CLAIM,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "paper_only": PAPER_ONLY,
            "no_real_bet": NO_REAL_BET,
        },
        "phase_chain": {
            "phase69_gate": "CALIBRATION_OBJECTIVE_NOT_PROMISING",
            "phase70_gate": "MARKET_ONLY_SUPERIOR",
            "phase71_gate": "MARKET_DE_RISK_GUARD_PROMISING",
            "phase72_gate": "MARKET_DERISK_GUARD_SPEC_READY",
            "metrics_ssot_gate": "METRICS_SSOT_FOUNDATION_READY",
        },
        "market_coverage_matrix_summary": {
            "source_name": source_mode,
            "source_mode": source_mode,
            "fixture_source_used": fixture_source_used,
            "current_source_reachable": current_source_reachable,
            "model_prediction_available": model_prediction_available,
            "moneyline_available": True,
            "runline_available": False,
            "total_available": False,
            "result_available": effective_mode == "replay",
            "odds_available": fixture_source_used,
            "market_home_prob_available": True,
            "closing_market_available": False,
            "coverage_notes": [
                "moneyline: available via model_home_prob + market_home_prob_no_vig",
                "runline: UNAVAILABLE — run line spread/odds not in prediction JSONL",
                "total: UNAVAILABLE — totals line/odds not in prediction JSONL",
                "closing_line: UNAVAILABLE — no separate closing odds data source",
                f"odds (raw): {'fixture American odds available' if fixture_source_used else 'UNAVAILABLE — home_ml/away_ml empty in backtest data'}",
                f"source_mode: {source_mode}",
                f"fixture_source_used: {fixture_source_used}",
            ],
        },
        "thresholds": {
            "lean_threshold": LEAN_THRESHOLD,
            "watch_threshold": WATCH_THRESHOLD,
            "derisk_band_low": DERISK_BAND_LOW,
            "derisk_band_high": DERISK_BAND_HIGH,
        },
        "advisories": clean_advisories,
        "ledger_entries_this_run": new_entries,
        "ledger_path": ledger_path,
        "review_summary": review_summary,
        "failure_notes": failure_notes,
        "source_mode": source_mode,
        "fixture_source_used": fixture_source_used,
        "current_source_reachable": current_source_reachable,
        "model_prediction_available": model_prediction_available,
        "gate": gate,
        "gate_rationale": gate_rationale,
        "completion_marker": COMPLETION_MARKER,
    }

    # Write JSON report
    if write_reports and report_path:
        dirpath = os.path.dirname(report_path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)

    # Write markdown report
    if write_reports and markdown_path:
        generate_markdown_report(payload, markdown_path)

    return payload
