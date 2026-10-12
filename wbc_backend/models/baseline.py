"""
Baseline Heuristics Model

Simple rule-based prediction using:
  - Team win percentage
  - Home/away advantage
  - Recent 10-game form
  - Rest days
"""
from __future__ import annotations

from wbc_backend.domain.schemas import Matchup, SubModelResult


def predict(matchup: Matchup) -> SubModelResult:
    h = matchup.home
    a = matchup.away

    # Win pct component
    wp_base = 0.5
    wp_base += (h.win_pct_last_10 - a.win_pct_last_10) * 0.30

    # Home advantage (WBC mostly neutral)
    if not matchup.neutral_site:
        wp_base += 0.025

    # Rest days
    rest_diff = h.rest_days - a.rest_days
    wp_base += rest_diff * 0.01

    # RPG differential
    rpg_edge = (h.runs_per_game - h.runs_allowed_per_game) - (a.runs_per_game - a.runs_allowed_per_game)
    wp_base += rpg_edge * 0.03

    home_wp = max(0.10, min(0.90, wp_base))

    return SubModelResult(
        model_name="baseline",
        home_win_prob=round(home_wp, 4),
        away_win_prob=round(1.0 - home_wp, 4),
        confidence=0.4,
        diagnostics={"baseline_raw": round(wp_base, 4)},
    )
