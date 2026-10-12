"""MLB Current Schedule and Odds Source Adapter.

Extensible adapter layer for MLB daily schedule + odds data.
Supports fixture, current (live API placeholder), and replay modes.

Design:
  - Fixture mode: load from JSON for adapter/schema/advisory integration testing
  - Current mode: probe live source (placeholder — no live API configured yet)
  - Replay mode: not applicable here; handled by mlb_daily_advisory via JSONL
  - All market coverage calculations produce explicit unavailable flags
  - External source calls are read-only; no sportsbook API writes

Safety:
  PRODUCTION_MODIFIED      = False
  CANDIDATE_PATCH_CREATED  = False
  NO_REAL_BET              = True
  PAPER_ONLY               = True
  NO_PROFIT_CLAIM          = True
  NO_EDGE_CLAIM            = True
"""
from __future__ import annotations

import datetime
import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Optional


# ─── Safety constants ─────────────────────────────────────────────────────────

PRODUCTION_MODIFIED: bool = False
CANDIDATE_PATCH_CREATED: bool = False
NO_REAL_BET: bool = True
PAPER_ONLY: bool = True
NO_PROFIT_CLAIM: bool = True
NO_EDGE_CLAIM: bool = True
DIAGNOSTIC_ONLY: bool = True

MODULE_VERSION: str = "mlb_current_sources_v1"
COMPLETION_MARKER: str = "MLB_CURRENT_SOURCE_ADAPTER_VERIFIED"

# ─── Gate constants (7 valid) ─────────────────────────────────────────────────

MLB_CURRENT_SOURCE_ADAPTER_READY: str = "MLB_CURRENT_SOURCE_ADAPTER_READY"
MLB_CURRENT_SOURCE_FIXTURE_READY: str = "MLB_CURRENT_SOURCE_FIXTURE_READY"
MLB_CURRENT_SOURCE_NEEDS_LIVE_API: str = "MLB_CURRENT_SOURCE_NEEDS_LIVE_API"
MLB_CURRENT_SOURCE_DATA_LIMITED: str = "MLB_CURRENT_SOURCE_DATA_LIMITED"
MLB_CURRENT_SOURCE_SCHEMA_CONFLICT: str = "MLB_CURRENT_SOURCE_SCHEMA_CONFLICT"
MLB_CURRENT_SOURCE_GOVERNANCE_RISK: str = "MLB_CURRENT_SOURCE_GOVERNANCE_RISK"
MLB_CURRENT_SOURCE_NOT_READY: str = "MLB_CURRENT_SOURCE_NOT_READY"

VALID_GATES: frozenset[str] = frozenset({
    MLB_CURRENT_SOURCE_ADAPTER_READY,
    MLB_CURRENT_SOURCE_FIXTURE_READY,
    MLB_CURRENT_SOURCE_NEEDS_LIVE_API,
    MLB_CURRENT_SOURCE_DATA_LIMITED,
    MLB_CURRENT_SOURCE_SCHEMA_CONFLICT,
    MLB_CURRENT_SOURCE_GOVERNANCE_RISK,
    MLB_CURRENT_SOURCE_NOT_READY,
})

# ─── Source mode constants ────────────────────────────────────────────────────

SOURCE_MODE_FIXTURE: str = "fixture"
SOURCE_MODE_CURRENT: str = "current"
SOURCE_MODE_REPLAY: str = "replay"

VALID_SOURCE_MODES: frozenset[str] = frozenset({
    SOURCE_MODE_FIXTURE,
    SOURCE_MODE_CURRENT,
    SOURCE_MODE_REPLAY,
})

# ─── Default paths ────────────────────────────────────────────────────────────

DEFAULT_FIXTURE_PATH: str = "data/fixtures/mlb_current_source_sample_20260507.json"


# ════════════════════════════════════════════════════════════════════════════
# SECTION A — Dataclasses
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class MarketCoverage:
    """Aggregate market coverage for a set of game snapshots."""
    moneyline_available: bool
    runline_available: bool
    total_available: bool
    result_available: bool
    odds_available: bool
    market_home_prob_available: bool
    closing_market_available: bool
    source_name: str
    source_mode: str
    unavailable_reasons: list[str] = field(default_factory=list)


@dataclass
class GameMarketSnapshot:
    """Normalized odds/schedule snapshot for a single MLB game."""
    game_id: str
    game_date: str
    home_team: str
    away_team: str
    scheduled_start_time: Optional[str]
    home_moneyline_odds: Optional[float]   # American odds (e.g., -140, +120)
    away_moneyline_odds: Optional[float]
    home_implied_prob: Optional[float]
    away_implied_prob: Optional[float]
    market_home_prob_no_vig: Optional[float]
    runline_spread: Optional[float]
    runline_home_odds: Optional[float]
    runline_away_odds: Optional[float]
    total_line: Optional[float]
    over_odds: Optional[float]
    under_odds: Optional[float]
    result_home_score: Optional[int]
    result_away_score: Optional[int]
    result_status: str                     # "scheduled", "live", "final", "unknown"
    source_name: str
    source_timestamp: str
    unavailable_fields: list[str] = field(default_factory=list)


@dataclass
class SourceHealth:
    """Health report for a schedule/odds source probe."""
    source_name: str
    source_mode: str
    checked_at: str
    reachable: bool
    total_games: int
    moneyline_games: int
    runline_games: int
    total_games_with_total: int
    result_games: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ════════════════════════════════════════════════════════════════════════════
# SECTION B — Math Helpers
# ════════════════════════════════════════════════════════════════════════════


def american_odds_to_implied_prob(odds: float) -> float:
    """
    Convert American odds to implied probability.

    Positive odds (underdog): prob = 100 / (odds + 100)
    Negative odds (favorite): prob = |odds| / (|odds| + 100)
    """
    if odds > 0:
        return 100.0 / (odds + 100.0)
    else:
        return abs(odds) / (abs(odds) + 100.0)


def normalize_two_way_no_vig(
    home_implied: float,
    away_implied: float,
) -> tuple[float, float]:
    """
    Remove vig from a two-way market.

    home_no_vig = home_implied / (home_implied + away_implied)
    away_no_vig = away_implied / (home_implied + away_implied)

    Returns (0.5, 0.5) if total is invalid to avoid division by zero.
    """
    total = home_implied + away_implied
    if total <= 0.0 or math.isnan(total) or math.isinf(total):
        return 0.5, 0.5
    return home_implied / total, away_implied / total


# ════════════════════════════════════════════════════════════════════════════
# SECTION C — Internal Normalization
# ════════════════════════════════════════════════════════════════════════════


def _normalize_game_from_dict(
    game: dict,
    source_name: str,
    source_mode: str,
    timestamp: str,
) -> GameMarketSnapshot:
    """Build a GameMarketSnapshot from a raw game dict, computing implied probs."""
    unavailable: list[str] = []

    home_ml = game.get("home_moneyline_odds")
    away_ml = game.get("away_moneyline_odds")

    # Compute implied probabilities from American odds
    home_implied: Optional[float] = None
    away_implied: Optional[float] = None
    market_home_no_vig: Optional[float] = None

    if home_ml is not None and away_ml is not None:
        home_implied = american_odds_to_implied_prob(float(home_ml))
        away_implied = american_odds_to_implied_prob(float(away_ml))
        market_home_no_vig, _ = normalize_two_way_no_vig(home_implied, away_implied)
    else:
        if home_ml is None:
            unavailable.append("home_moneyline_odds")
        if away_ml is None:
            unavailable.append("away_moneyline_odds")
        unavailable.extend([
            "home_implied_prob",
            "away_implied_prob",
            "market_home_prob_no_vig",
        ])

    # Runline fields
    runline_spread = game.get("runline_spread")
    runline_home_odds = game.get("runline_home_odds")
    runline_away_odds = game.get("runline_away_odds")
    for fname, val in [
        ("runline_spread", runline_spread),
        ("runline_home_odds", runline_home_odds),
        ("runline_away_odds", runline_away_odds),
    ]:
        if val is None and fname not in unavailable:
            unavailable.append(fname)

    # Total fields
    total_line = game.get("total_line")
    over_odds = game.get("over_odds")
    under_odds = game.get("under_odds")
    for fname, val in [
        ("total_line", total_line),
        ("over_odds", over_odds),
        ("under_odds", under_odds),
    ]:
        if val is None and fname not in unavailable:
            unavailable.append(fname)

    return GameMarketSnapshot(
        game_id=game.get("game_id", "UNKNOWN"),
        game_date=game.get("game_date", ""),
        home_team=game.get("home_team", ""),
        away_team=game.get("away_team", ""),
        scheduled_start_time=game.get("scheduled_start_time"),
        home_moneyline_odds=float(home_ml) if home_ml is not None else None,
        away_moneyline_odds=float(away_ml) if away_ml is not None else None,
        home_implied_prob=round(home_implied, 6) if home_implied is not None else None,
        away_implied_prob=round(away_implied, 6) if away_implied is not None else None,
        market_home_prob_no_vig=round(market_home_no_vig, 6) if market_home_no_vig is not None else None,
        runline_spread=float(runline_spread) if runline_spread is not None else None,
        runline_home_odds=float(runline_home_odds) if runline_home_odds is not None else None,
        runline_away_odds=float(runline_away_odds) if runline_away_odds is not None else None,
        total_line=float(total_line) if total_line is not None else None,
        over_odds=float(over_odds) if over_odds is not None else None,
        under_odds=float(under_odds) if under_odds is not None else None,
        result_home_score=game.get("result_home_score"),
        result_away_score=game.get("result_away_score"),
        result_status=game.get("result_status", "unknown"),
        source_name=source_name,
        source_timestamp=timestamp,
        unavailable_fields=unavailable,
    )


# ════════════════════════════════════════════════════════════════════════════
# SECTION D — Public Functions
# ════════════════════════════════════════════════════════════════════════════


def build_market_coverage(
    snapshots: list[GameMarketSnapshot],
    source_name: str,
    source_mode: str,
) -> MarketCoverage:
    """Build aggregate MarketCoverage from a list of GameMarketSnapshots."""
    if not snapshots:
        return MarketCoverage(
            moneyline_available=False,
            runline_available=False,
            total_available=False,
            result_available=False,
            odds_available=False,
            market_home_prob_available=False,
            closing_market_available=False,
            source_name=source_name,
            source_mode=source_mode,
            unavailable_reasons=["no_snapshots_loaded"],
        )

    ml_count = sum(1 for s in snapshots if s.market_home_prob_no_vig is not None)
    rl_count = sum(1 for s in snapshots if s.runline_spread is not None)
    tot_count = sum(1 for s in snapshots if s.total_line is not None)
    res_count = sum(
        1 for s in snapshots
        if s.result_status == "final" and s.result_home_score is not None
    )
    odds_count = sum(1 for s in snapshots if s.home_moneyline_odds is not None)

    unavailable_reasons: list[str] = []
    if ml_count == 0:
        unavailable_reasons.append("no_moneyline_odds_available")
    if rl_count == 0:
        unavailable_reasons.append("no_runline_data_available")
    if tot_count == 0:
        unavailable_reasons.append("no_total_data_available")
    if res_count == 0:
        unavailable_reasons.append("no_result_data_available_games_not_final")
    if odds_count == 0:
        unavailable_reasons.append("no_raw_moneyline_odds_available")

    return MarketCoverage(
        moneyline_available=ml_count > 0,
        runline_available=rl_count > 0,
        total_available=tot_count > 0,
        result_available=res_count > 0,
        odds_available=odds_count > 0,
        market_home_prob_available=ml_count > 0,
        closing_market_available=False,    # No closing line source available
        source_name=source_name,
        source_mode=source_mode,
        unavailable_reasons=unavailable_reasons,
    )


def load_fixture_schedule_odds(
    fixture_path: str = DEFAULT_FIXTURE_PATH,
) -> list[GameMarketSnapshot]:
    """
    Load fixture schedule/odds from a JSON file.

    Fixture data is for adapter/schema/advisory integration testing only.
    NOT real market odds. NOT suitable for real betting.
    Returns empty list if file missing.
    """
    if not os.path.exists(fixture_path):
        return []

    with open(fixture_path, encoding="utf-8") as fh:
        data = json.load(fh)

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    raw_games: list[dict] = data.get("games", [])

    snapshots: list[GameMarketSnapshot] = []
    for game in raw_games:
        snap = _normalize_game_from_dict(
            game,
            source_name="fixture",
            source_mode=SOURCE_MODE_FIXTURE,
            timestamp=timestamp,
        )
        snapshots.append(snap)

    return snapshots


def probe_current_mlb_source(date_str: str) -> SourceHealth:
    """
    Probe the live current MLB schedule/odds source.

    Currently returns reachable=False (no live API configured).
    Future extension: integrate with official MLB API or licensed odds provider.
    All probing is read-only; no sportsbook writes.
    """
    checked_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    return SourceHealth(
        source_name="current_mlb_api",
        source_mode=SOURCE_MODE_CURRENT,
        checked_at=checked_at,
        reachable=False,
        total_games=0,
        moneyline_games=0,
        runline_games=0,
        total_games_with_total=0,
        result_games=0,
        errors=[
            "live_api_not_configured: no current MLB schedule/odds API source available; "
            "fixture or replay mode required"
        ],
        warnings=[
            "system_in_dry_run_mode: only fixture or replay sources are operational",
            "no_real_bet: this system does not execute real bets under any mode",
        ],
    )


def normalize_current_source_games(
    raw_games: list[dict],
    source_name: str,
    source_mode: str,
    date_str: str,
) -> list[GameMarketSnapshot]:
    """
    Normalize raw game dicts from any source into GameMarketSnapshot list.

    Applies identical normalization to fixture loading. Suitable for future
    live source integration once an API is configured.
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    snapshots: list[GameMarketSnapshot] = []
    for game in raw_games:
        snap = _normalize_game_from_dict(
            game,
            source_name=source_name,
            source_mode=source_mode,
            timestamp=timestamp,
        )
        snapshots.append(snap)
    return snapshots


def merge_current_source_with_advisory_rows(
    snapshots: list[GameMarketSnapshot],
    advisory_rows: list[dict],
) -> list[dict]:
    """
    Merge market snapshot data with model prediction rows.

    For each snapshot:
    1. Attempt to find a matching prediction row by game_id or
       (home_team.lower(), away_team.lower(), game_date).
    2. If found: update market odds from snapshot; mark _model_prediction_available=True.
    3. If not found: create a market-only advisory row.

    Market-only rows (no prediction match):
    - model_home_prob = market_home_prob_no_vig  (gap = 0 → recommendation = PASS)
    - _model_prediction_available = False
    - moneyline recommendation will naturally be PASS (per advisory rules)
    - LEAN_HOME / LEAN_AWAY cannot be generated (gap = 0 < WATCH_THRESHOLD)

    Returns rows compatible with build_advisory().
    """
    # Build lookup indexes for matching
    row_by_game_id: dict[str, dict] = {}
    row_by_teams_date: dict[tuple[str, str, str], dict] = {}

    for row in advisory_rows:
        gid = row.get("game_id", "")
        if gid:
            row_by_game_id[gid] = row
        home = row.get("home_team", "").strip().lower()
        away = row.get("away_team", "").strip().lower()
        date = row.get("game_date", "")
        if home and date:
            row_by_teams_date[(home, away, date)] = row

    merged: list[dict] = []

    for snap in snapshots:
        # Attempt match
        matched_row: dict | None = None
        if snap.game_id in row_by_game_id:
            matched_row = dict(row_by_game_id[snap.game_id])
        else:
            key = (
                snap.home_team.strip().lower(),
                snap.away_team.strip().lower(),
                snap.game_date,
            )
            if key in row_by_teams_date:
                matched_row = dict(row_by_teams_date[key])

        if matched_row is not None:
            # Update market odds from snapshot where available
            merged_row = dict(matched_row)
            if snap.market_home_prob_no_vig is not None:
                merged_row["market_home_prob_no_vig"] = snap.market_home_prob_no_vig
            if snap.home_moneyline_odds is not None:
                merged_row["home_ml"] = snap.home_moneyline_odds
            if snap.away_moneyline_odds is not None:
                merged_row["away_ml"] = snap.away_moneyline_odds
            merged_row["_model_prediction_available"] = True
            merged_row["_source_name"] = snap.source_name
            merged_row["_source_mode"] = snap.source_name  # source_name carries mode token
            merged_row["_snapshot_game_id"] = snap.game_id
        else:
            # Market-only: no model prediction available
            market_prob = snap.market_home_prob_no_vig or 0.5
            merged_row = {
                "game_id": snap.game_id,
                "game_date": snap.game_date,
                "home_team": snap.home_team,
                "away_team": snap.away_team,
                "home_win": None,
                # Set model_home_prob = market to guarantee gap = 0 → PASS
                "model_home_prob": market_prob,
                "market_home_prob_no_vig": market_prob,
                "market_away_prob_no_vig": round(1.0 - market_prob, 6),
                "home_ml": snap.home_moneyline_odds if snap.home_moneyline_odds is not None else "",
                "away_ml": snap.away_moneyline_odds if snap.away_moneyline_odds is not None else "",
                "p0_features": {},
                "bullpen_features": {},
                "_model_prediction_available": False,
                "_source_name": snap.source_name,
                "_source_mode": snap.source_name,  # source_name carries mode token (e.g. "fixture")
                "_snapshot_game_id": snap.game_id,
            }

        merged.append(merged_row)

    return merged


def validate_market_snapshot(snapshot: GameMarketSnapshot) -> list[str]:
    """
    Validate a GameMarketSnapshot for schema correctness.
    Returns list of error strings; empty list means valid.
    """
    errors: list[str] = []

    if not snapshot.game_id:
        errors.append("game_id_missing")
    if not snapshot.game_date:
        errors.append("game_date_missing")
    if not snapshot.home_team:
        errors.append("home_team_missing")
    if not snapshot.away_team:
        errors.append("away_team_missing")
    if snapshot.home_implied_prob is not None and not (
        0.0 < snapshot.home_implied_prob < 1.0
    ):
        errors.append(f"home_implied_prob_out_of_range: {snapshot.home_implied_prob}")
    if snapshot.away_implied_prob is not None and not (
        0.0 < snapshot.away_implied_prob < 1.0
    ):
        errors.append(f"away_implied_prob_out_of_range: {snapshot.away_implied_prob}")
    if snapshot.market_home_prob_no_vig is not None and not (
        0.0 < snapshot.market_home_prob_no_vig < 1.0
    ):
        errors.append(
            f"market_home_prob_no_vig_out_of_range: {snapshot.market_home_prob_no_vig}"
        )
    if snapshot.source_name not in ("fixture", "current_mlb_api", "replay") and (
        snapshot.source_name not in VALID_SOURCE_MODES
        and snapshot.source_name != "current_mlb_api"
    ):
        errors.append(f"source_name_unrecognised: {snapshot.source_name}")

    return errors


def validate_source_health(health: SourceHealth) -> list[str]:
    """
    Validate a SourceHealth object for schema correctness.
    Returns list of error strings; empty list means valid.
    """
    errors: list[str] = []

    if not health.source_name:
        errors.append("source_name_missing")
    if health.source_mode not in VALID_SOURCE_MODES:
        errors.append(f"source_mode_invalid: {health.source_mode!r}")
    if not health.checked_at:
        errors.append("checked_at_missing")
    if health.total_games < 0:
        errors.append(f"total_games_negative: {health.total_games}")
    if health.moneyline_games < 0:
        errors.append(f"moneyline_games_negative: {health.moneyline_games}")
    if health.moneyline_games > health.total_games:
        errors.append(
            f"moneyline_games_exceeds_total: "
            f"{health.moneyline_games} > {health.total_games}"
        )
    if health.runline_games > health.total_games:
        errors.append(
            f"runline_games_exceeds_total: "
            f"{health.runline_games} > {health.total_games}"
        )

    return errors


# ════════════════════════════════════════════════════════════════════════════
# SECTION E — Gate Determination
# ════════════════════════════════════════════════════════════════════════════


def determine_gate(
    health: SourceHealth,
    snapshots: list[GameMarketSnapshot],
    coverage: MarketCoverage,
) -> tuple[str, str]:
    """
    Determine gate for the current source probe.
    Gate must be one of the 7 values in VALID_GATES.
    Conservative by design: prefer lower gates when uncertain.
    """
    # No snapshots loaded
    if not snapshots:
        if not health.reachable:
            return (
                MLB_CURRENT_SOURCE_NEEDS_LIVE_API,
                "No snapshots loaded; live API not configured; "
                "use --source fixture to validate adapter via fixture mode",
            )
        return (
            MLB_CURRENT_SOURCE_NOT_READY,
            "Source reports reachable but no snapshots loaded; "
            "check source configuration",
        )

    # Snapshots available — check coverage
    has_moneyline = coverage.moneyline_available
    is_fixture = coverage.source_mode == SOURCE_MODE_FIXTURE
    is_live = health.reachable

    if is_live and has_moneyline:
        return (
            MLB_CURRENT_SOURCE_ADAPTER_READY,
            "Live source reachable with moneyline data; "
            "source adapter fully operational",
        )

    if not is_live and is_fixture and has_moneyline:
        return (
            MLB_CURRENT_SOURCE_FIXTURE_READY,
            "Live source not configured; fixture source loaded with moneyline data; "
            "adapter/advisory integration validated via fixture mode; "
            "live API integration pending",
        )

    if not has_moneyline:
        return (
            MLB_CURRENT_SOURCE_DATA_LIMITED,
            "Source loaded but moneyline data unavailable; "
            "advisory market coverage limited to schedule-only",
        )

    # Default: fixture operational but coverage limited
    return (
        MLB_CURRENT_SOURCE_FIXTURE_READY,
        "Fixture source operational for adapter/advisory integration validation",
    )
