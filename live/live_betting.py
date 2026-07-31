"""
Live (In-Play) Betting Module.

Re-evaluates win probability, totals, and pitcher fatigue on a
per-inning basis.  Emits a live-bet signal when EV ≥ LIVE_EV_TRIGGER.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import math
from config import settings as cfg
from data.wbc_data import PitcherStats


@dataclass
class InningState:
    inning: int
    top_bottom: str           # "top" or "bottom"
    away_score: int = 0
    home_score: int = 0
    outs: int = 0
    runners: str = "---"      # e.g. "1-3" for runners on 1st/3rd
    away_hits: int = 0
    home_hits: int = 0


@dataclass
class LiveSignal:
    trigger: bool
    market: str
    side: str
    live_ev: float
    live_true_prob: float
    live_implied_prob: float
    live_odds: float
    description: str


@dataclass
class PitcherFatigue:
    name: str
    pitches_thrown: int
    innings_pitched: float
    fatigue_score: float       # 0 = fresh, 1 = gassed


def pitcher_fatigue(pitches: int, innings: float) -> float:
    """Compute fatigue score [0, 1] from pitch count & IP."""
    # WBC starters rarely exceed 75 pitches
    pitch_fatigue = min(1.0, pitches / 85.0)
    inn_fatigue = min(1.0, innings / 6.0)
    return 0.6 * pitch_fatigue + 0.4 * inn_fatigue


def live_win_probability(
    state: InningState,
    pregame_away_wp: float,
    away_runs_lambda: float,
    home_runs_lambda: float,
) -> tuple[float, float]:
    """
    Update win probability based on current game state.
    Uses remaining-innings Poisson projection.
    """
    innings_remaining = max(0, 9 - state.inning)
    if state.top_bottom == "top":
        innings_remaining += 0.5  # home still bats this inning

    # Remaining-run expectations
    per_inning_away = away_runs_lambda / 9.0
    per_inning_home = home_runs_lambda / 9.0

    proj_away = state.away_score + per_inning_away * innings_remaining
    proj_home = state.home_score + per_inning_home * innings_remaining

    # Win prob from projected scores (Normal approximation)
    diff = proj_away - proj_home
    sigma = math.sqrt(
        per_inning_away * innings_remaining +
        per_inning_home * innings_remaining +
        0.5
    )
    if sigma == 0:
        sigma = 0.01
    z = diff / sigma
    away_wp = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

    return away_wp, 1.0 - away_wp


def evaluate_live_bet(
    live_away_wp: float,
    live_odds_away: float,
    live_odds_home: float,
) -> List[LiveSignal]:
    """
    Check if any live-bet opportunity exceeds the trigger threshold.
    """
    signals: List[LiveSignal] = []

    # Away ML
    ip_away = 1.0 / live_odds_away if live_odds_away > 0 else 0
    ev_away = live_away_wp * (live_odds_away - 1) - (1 - live_away_wp)
    if ev_away >= cfg.LIVE_EV_TRIGGER:
        signals.append(LiveSignal(
            trigger=True,
            market="LIVE ML",
            side="AWAY",
            live_ev=round(ev_away, 4),
            live_true_prob=round(live_away_wp, 4),
            live_implied_prob=round(ip_away, 4),
            live_odds=live_odds_away,
            description=f"Live EV {ev_away:.1%} on Away ML @ {live_odds_away:.2f}",
        ))

    # Home ML
    home_wp = 1.0 - live_away_wp
    ip_home = 1.0 / live_odds_home if live_odds_home > 0 else 0
    ev_home = home_wp * (live_odds_home - 1) - (1 - home_wp)
    if ev_home >= cfg.LIVE_EV_TRIGGER:
        signals.append(LiveSignal(
            trigger=True,
            market="LIVE ML",
            side="HOME",
            live_ev=round(ev_home, 4),
            live_true_prob=round(home_wp, 4),
            live_implied_prob=round(ip_home, 4),
            live_odds=live_odds_home,
            description=f"Live EV {ev_home:.1%} on Home ML @ {live_odds_home:.2f}",
        ))

    if not signals:
        signals.append(LiveSignal(
            trigger=False,
            market="LIVE ML",
            side="NONE",
            live_ev=max(ev_away, ev_home),
            live_true_prob=0,
            live_implied_prob=0,
            live_odds=0,
            description="No live value found — standing by",
        ))

    return signals
