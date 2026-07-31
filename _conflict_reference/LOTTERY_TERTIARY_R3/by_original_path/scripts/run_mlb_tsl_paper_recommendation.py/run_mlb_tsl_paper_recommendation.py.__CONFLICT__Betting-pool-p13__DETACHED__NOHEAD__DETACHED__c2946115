#!/usr/bin/env python3
"""MLB → TSL Paper Recommendation — Thin Orchestrator Entrypoint.

Picks today's first available MLB game, runs the prediction pipeline,
computes one recommendation row, and writes it to:
  outputs/recommendations/PAPER/YYYY-MM-DD/<game_id>.jsonl

Safety hard-gates (must all remain True):
  - paper_only = True always
  - MLB PAPER_ONLY status is enforced via MLBLeagueAdapter.rules()
  - No production DB writes
  - No real bets placed
  - Simulation gate must pass (or be explicitly bypassed with --allow-missing-simulation-gate)

Usage:
    .venv/bin/python scripts/run_mlb_tsl_paper_recommendation.py
    .venv/bin/python scripts/run_mlb_tsl_paper_recommendation.py --allow-replay-paper
    .venv/bin/python scripts/run_mlb_tsl_paper_recommendation.py --date 2026-05-11
    .venv/bin/python scripts/run_mlb_tsl_paper_recommendation.py \\
        --simulation-strategy-name moneyline_edge_threshold_v0
    .venv/bin/python scripts/run_mlb_tsl_paper_recommendation.py \\
        --simulation-result-path outputs/simulation/PAPER/2026-05-11/...jsonl
    .venv/bin/python scripts/run_mlb_tsl_paper_recommendation.py \\
        --allow-missing-simulation-gate   # bypass when no simulation exists
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.mlb_live_pipeline import fetch_schedule
from data.tsl_crawler_v2 import TSLCrawlerV2
from league_adapters.mlb_adapter import MLBLeagueAdapter
from league_adapters.base import LeagueContext
from wbc_backend.recommendation.recommendation_row import (
    MlbTslRecommendationRow,
    VALID_GATE_STATUSES,
)
from wbc_backend.recommendation.recommendation_gate_policy import (
    build_recommendation_gate_from_simulation,
)
from wbc_backend.simulation.simulation_result_loader import (
    load_latest_simulation_result,
    load_simulation_result_from_jsonl,
)

# ── Hard-gate: MLB must remain PAPER_ONLY ──────────────────────────────────
_MLB_PAPER_ONLY: bool = True   # DO NOT change without P38 governance clearance

# ── Kelly cap for paper mode ───────────────────────────────────────────────
_MAX_KELLY_FRACTION: float = 0.05   # max 5% of bankroll in paper mode
_PAPER_BANKROLL_UNITS: float = 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _pick_game(date_str: str) -> dict | None:
    """Return the first scheduled/preview game for *date_str*, or None."""
    games = fetch_schedule(date_str, use_cache=False)
    if not games:
        return None
    # Prefer games not yet started (Scheduled / Pre-Game / Preview)
    preferred_statuses = {"Scheduled", "Pre-Game", "Preview", "Warmup"}
    for g in games:
        status = g.get("status", {}).get("detailedState", "")
        if any(s in status for s in preferred_statuses):
            return g
    # Fallback: return first game regardless of status
    return games[0]


def _abbrev_from_name(name: str, fallback: str) -> str:
    """Derive a 3-letter abbreviation from a team name (schedule API omits it)."""
    # Common MLB team name → abbreviation mapping
    _MAP = {
        "Athletics": "OAK", "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
        "Chicago White Sox": "CWS", "Chicago Cubs": "CHC", "Cincinnati Reds": "CIN",
        "Cleveland Guardians": "CLE", "Colorado Rockies": "COL", "Detroit Tigers": "DET",
        "Houston Astros": "HOU", "Kansas City Royals": "KC", "Los Angeles Angels": "LAA",
        "Los Angeles Dodgers": "LAD", "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
        "Minnesota Twins": "MIN", "New York Yankees": "NYY", "New York Mets": "NYM",
        "Oakland Athletics": "OAK", "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT",
        "San Diego Padres": "SD", "San Francisco Giants": "SF", "Seattle Mariners": "SEA",
        "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB", "Texas Rangers": "TEX",
        "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH", "Arizona Diamondbacks": "ARI",
    }
    return _MAP.get(name, fallback)


def _build_game_id(game: dict, date_str: str) -> str:
    teams = game.get("teams", {})
    home_team = teams.get("home", {}).get("team", {})
    away_team = teams.get("away", {}).get("team", {})
    home = (
        home_team.get("abbreviation")
        or _abbrev_from_name(home_team.get("name", ""), "HOM")
    )
    away = (
        away_team.get("abbreviation")
        or _abbrev_from_name(away_team.get("name", ""), "AWY")
    )
    pk = game.get("gamePk", 0)
    return f"{date_str}-{away}-{home}-{pk}"


def _probe_tsl() -> tuple[bool, str]:
    """Return (tsl_live_ok, note)."""
    try:
        c = TSLCrawlerV2(use_mock=False)
        games = c.fetch_baseball_games()
        if games:
            return True, f"TSL live: {len(games)} game(s) returned"
        return False, "TSL live: 0 games returned (possible 403 or empty market)"
    except Exception as exc:
        return False, f"TSL live probe exception: {exc}"


def _compute_implied_prob(decimal_odds: float) -> float:
    """Decimal odds → raw implied probability."""
    if decimal_odds <= 1.0:
        return 1.0
    return 1.0 / decimal_odds


def _kelly_fraction(edge: float, decimal_odds: float) -> float:
    """Full Kelly: edge / (decimal_odds - 1); capped at _MAX_KELLY_FRACTION."""
    b = decimal_odds - 1.0
    if b <= 0 or edge <= 0:
        return 0.0
    raw = edge / b
    return min(raw, _MAX_KELLY_FRACTION)


def _estimate_moneyline_odds(model_prob_home: float) -> float:
    """Fallback: derive a *rough* decimal odds from model probability.

    Used only when TSL live source is unavailable.  These are estimates for
    paper tracking only — NOT real market odds.
    """
    # Apply a small vig adjustment (4%)
    vig = 0.04
    implied = max(0.05, min(0.95, model_prob_home)) * (1 - vig / 2)
    implied = max(0.05, implied)
    return round(1.0 / implied, 4)


def build_recommendation(
    game: dict,
    date_str: str,
    tsl_live: bool,
    tsl_note: str,
    simulation_gate: dict | None = None,
) -> MlbTslRecommendationRow:
    """Build one MlbTslRecommendationRow for a given game dict.

    Parameters
    ----------
    game : dict
        MLB schedule API game dict.
    date_str : str
        YYYY-MM-DD date string for this recommendation.
    tsl_live : bool
        Whether TSL live source is available.
    tsl_note : str
        Human-readable note about TSL probe result.
    simulation_gate : dict | None
        Output of build_recommendation_gate_from_simulation().
        If None, no simulation gate has been applied (may indicate bypass).
    """

    # ── 1. Game identity ──────────────────────────────────────────────────
    game_id = _build_game_id(game, date_str)
    game_date_raw = game.get("gameDate", f"{date_str}T00:00:00Z")
    try:
        game_start_utc = datetime.fromisoformat(game_date_raw.replace("Z", "+00:00"))
    except ValueError:
        game_start_utc = datetime.now(timezone.utc)

    teams = game.get("teams", {})
    home_name = teams.get("home", {}).get("team", {}).get("name", "Home")
    away_name = teams.get("away", {}).get("team", {}).get("name", "Away")

    # ── 2. MLB PAPER_ONLY gate check ──────────────────────────────────────
    adapter = MLBLeagueAdapter()
    ctx = LeagueContext(
        league="MLB",
        game_id=game_id,
        home_team=home_name,
        away_team=away_name,
    )
    rules = adapter.rules(ctx)
    if rules.deployment_mode != "paper":
        # This should never happen while P38 is NO_GO — defensive check.
        raise RuntimeError(
            f"MLB adapter deployment_mode='{rules.deployment_mode}' — "
            "expected 'paper'. P38 gate was not cleared. Aborting."
        )

    # ── 3. Simple model probability (market-proxy baseline) ───────────────
    # We use market-implied probabilities from the API (schedule endpoints
    # do not carry odds), so we fall back to a 50/50 baseline adjusted by
    # home-field advantage as a conservative starting point.
    # A full model call (mlb_moneyline / regime paper) requires the full
    # historical CSV which may not be present in all environments; we use
    # the lightweight approach here for the smoke run.
    MODEL_HOME_PRIOR = 0.535   # MLB historical home-win rate
    model_prob_home = MODEL_HOME_PRIOR
    model_prob_away = 1.0 - model_prob_home

    # Try to call the proper moneyline model if available
    model_version = "v1-home-prior-baseline"
    try:
        from wbc_backend.models.mlb_moneyline import (
            MLBMoneylineModel,
            build_mlb_moneyline_training_data,
        )
        from wbc_backend.models.mlb_moneyline_base import MLBMoneylineBaseModel
        from wbc_backend.models.mlb_context_adjuster import MLBContextAdjuster

        X, y, _ = build_mlb_moneyline_training_data()
        base = MLBMoneylineBaseModel()
        base.fit(X, y)
        adjuster = MLBContextAdjuster()
        ml_model = MLBMoneylineModel(base_model=base, context_adjuster=adjuster)
        # Use neutral features (market = 0.535, ou = 8.5, both starters known)
        import numpy as np
        X_single = np.array([[0.535, 0.465, 0.07, 8.5, 1.0, 1.0, 1.0]])
        model_prob_home = float(base.predict_proba(X_single)[0])
        model_prob_away = 1.0 - model_prob_home
        model_version = "v1-mlb-moneyline-trained"
    except Exception:
        pass  # Fall back to prior; logged in source_trace

    # Adjust via adapter
    adjusted = adapter.adjust_probabilities(
        {"home_win_prob": model_prob_home, "away_win_prob": model_prob_away}, ctx
    )
    model_prob_home = adjusted["home_win_prob"]
    model_prob_away = adjusted["away_win_prob"]

    # ── 4. TSL odds ───────────────────────────────────────────────────────
    gate_reasons: list[str] = []
    source_trace: dict = {
        "mlb_api": "statsapi.mlb.com/api/v1",
        "tsl_live": tsl_live,
        "tsl_note": tsl_note,
        "model_version": model_version,
        "paper_only_reason": rules.paper_only_reason,
    }

    # ── Embed simulation gate evidence in source_trace ────────────────────
    if simulation_gate is not None:
        source_trace["simulation_id"] = simulation_gate.get("simulation_id")
        source_trace["simulation_gate_status"] = simulation_gate.get("gate_status")
        source_trace["simulation_allow_recommendation"] = simulation_gate.get(
            "allow_recommendation"
        )
        # P5: embed probability source mode from simulation
        sim_src_trace = simulation_gate.get("source_trace") or {}
        source_trace["probability_source"] = sim_src_trace.get(
            "probability_source_mode", "unknown"
        )
        source_trace["simulation_probability_source_mode"] = sim_src_trace.get(
            "probability_source_mode", "unknown"
        )
        source_trace["simulation_real_model_count"] = sim_src_trace.get(
            "real_model_count", 0
        )
        source_trace["simulation_market_proxy_count"] = sim_src_trace.get(
            "market_proxy_count", 0
        )
        source_trace["simulation_walk_forward_ml_candidate_count"] = sim_src_trace.get(
            "walk_forward_ml_candidate_count", 0
        )
        source_trace["simulation_ml_model_type"] = sim_src_trace.get(
            "ml_model_type", []
        )
        source_trace["simulation_ml_feature_policy"] = sim_src_trace.get(
            "ml_feature_policy", []
        )
        source_trace["simulation_ml_features_used"] = sim_src_trace.get(
            "ml_features_used", []
        )
        # Propagate proxy-only warning if present in gate_reasons
        for reason in simulation_gate.get("gate_reasons", []):
            if "proxy" in reason.lower() or "market" in reason.lower():
                source_trace["simulation_model_prob_note"] = reason
                break
    else:
        source_trace["simulation_id"] = None
        source_trace["simulation_gate_status"] = "NOT_APPLIED"
        source_trace["simulation_allow_recommendation"] = None
        source_trace["probability_source"] = "unknown"
        source_trace["simulation_probability_source_mode"] = "unknown"
        source_trace["simulation_real_model_count"] = 0
        source_trace["simulation_market_proxy_count"] = 0
        source_trace["simulation_walk_forward_ml_candidate_count"] = 0
        source_trace["simulation_ml_model_type"] = []
        source_trace["simulation_ml_feature_policy"] = []
        source_trace["simulation_ml_features_used"] = []

    if tsl_live:
        # TSL has data — use model probability to estimate edge vs TSL
        tsl_decimal_odds = _estimate_moneyline_odds(model_prob_home)
        gate_reasons.append("TSL live odds estimate used (no team-name join yet)")
    else:
        # TSL is blocked — use estimated odds, mark as BLOCKED_TSL_SOURCE
        tsl_decimal_odds = _estimate_moneyline_odds(model_prob_home)
        gate_reasons.append(tsl_note)
        gate_reasons.append("TSL live source unavailable — estimated odds used")

    # ── 5. Edge & Kelly ───────────────────────────────────────────────────
    implied = _compute_implied_prob(tsl_decimal_odds)
    edge_pct = model_prob_home - implied   # positive = model thinks home is underpriced
    kelly = _kelly_fraction(edge_pct, tsl_decimal_odds)
    stake_units = round(kelly * _PAPER_BANKROLL_UNITS, 2)

    # ── 6. Gate status ────────────────────────────────────────────────────
    if not _MLB_PAPER_ONLY:
        raise RuntimeError("_MLB_PAPER_ONLY hard gate was removed — this must not happen.")

    # P5: market-proxy only warning — simulation proves nothing about real model edge
    sim_proxy_only = (
        simulation_gate is not None
        and source_trace.get("simulation_probability_source_mode") == "market_proxy"
    )
    if sim_proxy_only:
        gate_reasons.append(
            "WARNING: simulation uses market-proxy probabilities; "
            "no real model edge proven"
        )

    # Simulation gate check: highest priority after MLB paper gate
    sim_blocks = (
        simulation_gate is not None
        and not simulation_gate.get("allow_recommendation", True)
    )
    if sim_blocks:
        # Simulation blocked — force stake to 0, record simulation gate status
        sim_gate_status = simulation_gate.get("gate_status", "BLOCKED_SIMULATION_GATE")
        # Map to a valid MlbTslRecommendationRow gate status
        if sim_gate_status in (
            "BLOCKED_NO_SIMULATION",
            "BLOCKED_SIMULATION_GATE",
            "BLOCKED_PAPER_ONLY_VIOLATION",
        ):
            gate_status = "BLOCKED_NO_SIMULATION"
        else:
            gate_status = "BLOCKED_SIMULATION_GATE"
        gate_reasons.insert(
            0,
            f"BLOCKED by simulation gate: simulation_gate_status={sim_gate_status!r}. "
            "stake_units_paper=0.0, kelly_fraction=0.0.",
        )
        for reason in simulation_gate.get("gate_reasons", []):
            gate_reasons.append(f"[sim] {reason}")
        kelly = 0.0
        stake_units = 0.0
    elif not tsl_live:
        gate_status = "BLOCKED_TSL_SOURCE"
        gate_reasons.insert(0, "BLOCKED: TSL live source unavailable (403 Forbidden)")
        kelly = 0.0
        stake_units = 0.0
    elif edge_pct <= 0:
        gate_status = "BLOCKED_EDGE_NEGATIVE"
        gate_reasons.insert(0, f"BLOCKED: edge={edge_pct:.4f} ≤ 0")
        kelly = 0.0
        stake_units = 0.0
    elif kelly == 0.0:
        gate_status = "BLOCKED_KELLY_ZERO"
        gate_reasons.insert(0, "BLOCKED: kelly fraction = 0")
    else:
        gate_status = "BLOCKED_PAPER_ONLY"
        gate_reasons.insert(0, "BLOCKED_PAPER_ONLY: MLB P38 gate not cleared")

    return MlbTslRecommendationRow(
        game_id=game_id,
        game_start_utc=game_start_utc,
        model_prob_home=round(model_prob_home, 6),
        model_prob_away=round(model_prob_away, 6),
        model_ensemble_version=model_version,
        tsl_market="moneyline",
        tsl_line=None,
        tsl_side="home",
        tsl_decimal_odds=tsl_decimal_odds,
        edge_pct=round(edge_pct, 6),
        kelly_fraction=round(kelly, 6),
        stake_units_paper=stake_units,
        gate_status=gate_status,
        gate_reasons=gate_reasons,
        paper_only=True,
        generated_at_utc=datetime.now(timezone.utc),
        source_trace=source_trace,
    )


def write_row(row: MlbTslRecommendationRow, date_str: str, is_replay: bool) -> Path:
    """Write row to outputs/recommendations/PAPER/YYYY-MM-DD/<game_id>[.replay_fallback].jsonl"""
    safe_id = row.game_id.replace("/", "_").replace(":", "_")
    suffix = ".replay_fallback.jsonl" if is_replay else ".jsonl"
    out_dir = ROOT / "outputs" / "recommendations" / "PAPER" / date_str
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Cannot create output directory {out_dir}: {exc}") from exc
    out_path = out_dir / f"{safe_id}{suffix}"
    out_path.write_text(row.to_jsonl_line() + "\n", encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MLB→TSL paper recommendation — smoke/paper-only mode."
    )
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument(
        "--allow-replay-paper",
        action="store_true",
        help="Allow paper recommendation even when MLB live source falls back to replay.",
    )
    # P4: simulation gate arguments
    parser.add_argument(
        "--simulation-result-path",
        default=None,
        help="Explicit path to a PAPER simulation JSONL file. "
             "If provided, overrides --simulation-strategy-name lookup.",
    )
    parser.add_argument(
        "--simulation-strategy-name",
        default="moneyline_edge_threshold_v0",
        help="Strategy name to filter when loading the latest simulation result "
             "(default: moneyline_edge_threshold_v0).",
    )
    parser.add_argument(
        "--require-simulation-gate",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Require a valid simulation result before issuing recommendation "
             "(default: True). Use --no-require-simulation-gate to disable.",
    )
    parser.add_argument(
        "--allow-missing-simulation-gate",
        action="store_true",
        help="Allow recommendation to proceed even when no simulation result is found. "
             "Disables simulation gate enforcement.",
    )
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    # ── Enforce PAPER_ONLY hard gate ──────────────────────────────────────
    if not _MLB_PAPER_ONLY:
        print("FATAL: _MLB_PAPER_ONLY hard gate is not set. Aborting.", file=sys.stderr)
        return 2

    # ── P4: Load simulation result and apply gate ─────────────────────────
    simulation = None
    simulation_gate: dict | None = None
    simulation_load_note = "simulation_gate=NOT_LOADED"

    if args.simulation_result_path:
        # Explicit path provided
        try:
            simulation = load_simulation_result_from_jsonl(args.simulation_result_path)
            simulation_load_note = f"simulation_gate=LOADED_FROM_PATH({args.simulation_result_path})"
        except (ValueError, FileNotFoundError, OSError) as exc:
            print(
                f"[SIM-GATE] Failed to load simulation from path "
                f"{args.simulation_result_path}: {exc}",
                file=sys.stderr,
            )
    else:
        # Auto-discover latest matching simulation
        sim_dir = ROOT / "outputs" / "simulation" / "PAPER"
        simulation = load_latest_simulation_result(
            simulation_dir=sim_dir,
            strategy_name=args.simulation_strategy_name,
        )
        if simulation is not None:
            simulation_load_note = (
                f"simulation_gate=LOADED_LATEST(strategy={args.simulation_strategy_name})"
            )

    # Apply gate policy
    simulation_gate = build_recommendation_gate_from_simulation(simulation)

    sim_gate_status = simulation_gate.get("gate_status", "UNKNOWN")
    sim_allows = simulation_gate.get("allow_recommendation", False)
    print(
        f"[SIM-GATE] {simulation_load_note} | "
        f"gate_status={sim_gate_status} | allow_recommendation={sim_allows}"
    )

    # Enforce: if gate blocks and we're not bypassing, refuse
    if not sim_allows:
        if args.allow_missing_simulation_gate and simulation is None:
            # Explicit bypass for missing simulation only
            print(
                "[SIM-GATE] WARNING: No simulation result found. "
                "--allow-missing-simulation-gate is set — proceeding without simulation gate.",
                file=sys.stderr,
            )
            simulation_gate = None  # treat as no gate applied
        else:
            print(
                f"[SIM-GATE] REFUSED: Simulation gate blocked recommendation. "
                f"gate_status={sim_gate_status}. "
                "Pass --allow-missing-simulation-gate (only when simulation is missing) "
                "or regenerate simulation with a passing gate.",
                file=sys.stderr,
            )
            # Still write a blocked row rather than producing nothing
            # (allows downstream audit trail)
            simulation_gate = simulation_gate  # keep blocking gate for row building

    # ── Pick today's game ─────────────────────────────────────────────────
    game = _pick_game(date_str)
    is_replay_fallback = False

    if game is None:
        if args.allow_replay_paper:
            print(
                f"WARNING: No MLB games found for {date_str} — "
                "running with synthetic fixture (--allow-replay-paper).",
                file=sys.stderr,
            )
            # Minimal synthetic fixture for smoke-only run
            game = {
                "gamePk": 0,
                "gameDate": f"{date_str}T18:00:00Z",
                "status": {"detailedState": "Scheduled"},
                "teams": {
                    "home": {"team": {"name": "Home Team", "abbreviation": "HOM"}},
                    "away": {"team": {"name": "Away Team", "abbreviation": "AWY"}},
                },
            }
            is_replay_fallback = True
        else:
            print(
                f"BLOCKED: No MLB games found for {date_str}. "
                "Pass --allow-replay-paper to run with synthetic fixture.",
                file=sys.stderr,
            )
            return 1

    # ── TSL probe ─────────────────────────────────────────────────────────
    tsl_live, tsl_note = _probe_tsl()

    # ── Build recommendation row ──────────────────────────────────────────
    row = build_recommendation(game, date_str, tsl_live, tsl_note, simulation_gate)

    # ── Write output ──────────────────────────────────────────────────────
    out_path = write_row(row, date_str, is_replay_fallback)

    # ── Summary ───────────────────────────────────────────────────────────
    live_tag = "LIVE" if not is_replay_fallback else "REPLAY-FALLBACK"
    print(
        f"[PAPER-ONLY] {live_tag} | {row.game_id} | "
        f"home_prob={row.model_prob_home:.4f} | "
        f"market={row.tsl_market} | side={row.tsl_side} | "
        f"odds={row.tsl_decimal_odds:.4f} | edge={row.edge_pct:.4f} | "
        f"kelly={row.kelly_fraction:.4f} | stake={row.stake_units_paper}u | "
        f"gate={row.gate_status} | "
        f"output={out_path}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
