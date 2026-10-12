"""
WBC-specific adjustment engine.

Applies international-tournament coefficients to raw model outputs
to account for WBC-unique factors:
  • Round-specific pitch-count / inning limits on starters
  • Piggyback starter (第二先發) quality impact
  • Elevated bullpen importance (scales with round)
  • Short-series variance inflation
  • Cross-league unfamiliarity
  • Roster strength index differential
"""
from __future__ import annotations
from typing import Dict, Tuple

from config.settings import (
    WBC_ROUND_ADJUSTMENTS,
    WBC_SP_EXPECTED_INNINGS,
    WBC_PITCH_LIMITS,
    WBC_STRIKEOUT_ADJ,
    WBC_XBH_ADJ,
    STAR_PLAYER_IMPACT,
)
from data.wbc_data import MatchData


def _round_key(round_name: str) -> str:
    """Map MatchData.round_name → config key (Pool/Quarter-Final/Semi-Final/Final)."""
    rn = round_name.lower()
    if "pool" in rn:
        return "Pool"
    elif "quarter" in rn:
        return "Quarter-Final"
    elif "semi" in rn:
        return "Semi-Final"
    elif "final" in rn:
        return "Final"
    return "Pool"  # default


def adjusted_probabilities(
    match: MatchData,
    away_wp: float,
    home_wp: float,
) -> Tuple[float, float, Dict]:
    """
    Shift ensemble probabilities using round-specific WBC adjustments.

    Returns adjusted (away_wp, home_wp, adjustment_details).
    """
    rk = _round_key(match.round_name)
    round_cfg = WBC_ROUND_ADJUSTMENTS.get(rk, WBC_ROUND_ADJUSTMENTS["Pool"])
    pitch_cfg = WBC_PITCH_LIMITS.get(rk, WBC_PITCH_LIMITS["Pool"])
    sp_inn = WBC_SP_EXPECTED_INNINGS.get(rk, 3.5)

    starter_impact = round_cfg["starter_impact"]
    bullpen_impact = round_cfg["bullpen_impact"]
    variance_add = round_cfg.get("variance_add", 0.05)

    # ── 1. Starter-impact discount (round-specific) ──────
    # In Pool round (65 pitches), SP covers only ~3.5 IP → huge dampening
    sp_dampening = 1.0 - starter_impact

    # ── 2. Piggyback (第二先發) Quality Adjustment ────────
    # Better piggyback → team retains more of its SP advantage
    pb_away_era = match.away_piggyback.era if match.away_piggyback else 4.50
    pb_home_era = match.home_piggyback.era if match.home_piggyback else 4.50
    pb_diff = (pb_home_era - pb_away_era) * 0.008  # positive = away PB better
    # Dampen by how many innings PB will actually throw (~2-3 IP)
    pb_inn_share = max(0, (9.0 - sp_inn * 2)) / 9.0  # share of game for PBs
    pb_adjustment = pb_diff * pb_inn_share

    # ── 3. Bullpen fatigue amplification (round-specific) ─
    bp_total_away = sum(p.pitch_count_last_3d for p in match.away_bullpen)
    bp_total_home = sum(p.pitch_count_last_3d for p in match.home_bullpen)

    # Fatigue penalty scaled by bullpen_impact (higher in Pool = 1.60)
    bp_penalty_away = bp_total_away / 800.0 * bullpen_impact * 0.05
    bp_penalty_home = bp_total_home / 800.0 * bullpen_impact * 0.05

    # ── 4. Roster Strength & Non-Linear Collapse ──────────
    rsi_away = match.away.roster_vol.roster_strength_index if match.away.roster_vol else 75
    rsi_home = match.home.roster_vol.roster_strength_index if match.home.roster_vol else 75
    rsi_diff_raw = rsi_away - rsi_home
    rsi_diff = rsi_diff_raw / 100.0 * 0.04  # base ±4% shift

    # Non-linear collapse factor (The "13-0 / 14-0" effect)
    # If a team's RSI is significantly lower, they are prone to blowouts
    collapse_shift = 0.0
    if rsi_diff_raw > 25: # Away is much stronger
        collapse_shift = 0.015  # Additional 1.5% shift to Away
    elif rsi_diff_raw < -25: # Home is much stronger
        collapse_shift = -0.015
    
    # Team chemistry bonus
    chem_away = match.away.roster_vol.team_chemistry if match.away.roster_vol else 0.70
    chem_home = match.home.roster_vol.team_chemistry if match.home.roster_vol else 0.70
    chem_bonus = (chem_away - chem_home) * 0.02  # up to ±2% shift

    # ── 5. Variance inflation → regress toward 50% ───────
    regress = variance_add * 0.5
    away_adj = away_wp * (1.0 - regress) + 0.5 * regress
    home_adj = home_wp * (1.0 - regress) + 0.5 * regress

    # ── 6. Apply adjustments ─────────────────────────────
    away_adj += pb_adjustment
    away_adj -= bp_penalty_away
    away_adj += bp_penalty_home
    away_adj += rsi_diff
    away_adj += collapse_shift
    away_adj += chem_bonus

    home_adj -= pb_adjustment
    home_adj -= bp_penalty_home
    home_adj += bp_penalty_away
    home_adj -= rsi_diff
    home_adj -= collapse_shift
    home_adj -= chem_bonus

    # ── 7. Normalize ─────────────────────────────────────
    total = away_adj + home_adj
    if total > 0:
        away_adj /= total
        home_adj /= total
    else:
        away_adj = home_adj = 0.5

    details = {
        "round": rk,
        "pitch_limit": pitch_cfg["max_pitches"],
        "sp_expected_innings": sp_inn,
        "starter_impact_factor": round(starter_impact, 3),
        "bullpen_impact_factor": round(bullpen_impact, 3),
        "sp_dampening": round(sp_dampening, 3),
        "piggyback_away": match.away_piggyback.name if match.away_piggyback else "N/A",
        "piggyback_home": match.home_piggyback.name if match.home_piggyback else "N/A",
        "piggyback_adjustment": round(pb_adjustment, 4),
        "bullpen_fatigue_away_3d": bp_total_away,
        "bullpen_fatigue_home_3d": bp_total_home,
        "bp_penalty_away": round(bp_penalty_away, 4),
        "bp_penalty_home": round(bp_penalty_home, 4),
        "roster_strength_away": rsi_away,
        "roster_strength_home": rsi_home,
        "rsi_adjustment": round(rsi_diff + collapse_shift, 4),
        "collapse_shift": round(collapse_shift, 4),
        "chemistry_bonus": round(chem_bonus, 4),
        "variance_regression": round(regress, 4),
        "strikeout_adj": f"+{WBC_STRIKEOUT_ADJ*100:.0f}%",
        "xbh_adj": f"{WBC_XBH_ADJ*100:.0f}%",
        "pre_adjust_away": round(away_wp, 4),
        "pre_adjust_home": round(home_wp, 4),
        "post_adjust_away": round(away_adj, 4),
        "post_adjust_home": round(home_adj, 4),
    }

    return away_adj, home_adj, details


def adjusted_total_runs(
    lambda_away: float,
    lambda_home: float,
    round_name: str = "Pool",
) -> Tuple[float, float]:
    """
    Inflate run lambdas by round-specific WBC variance coefficient.
    """
    rk = _round_key(round_name)
    round_cfg = WBC_ROUND_ADJUSTMENTS.get(rk, WBC_ROUND_ADJUSTMENTS["Pool"])
    variance_add = round_cfg.get("variance_add", 0.05)
    factor = 1.0 + variance_add
    return lambda_away * factor, lambda_home * factor
