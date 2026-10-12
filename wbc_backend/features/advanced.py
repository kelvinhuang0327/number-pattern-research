"""
Advanced Feature Engineering — § 三、進階特徵工程

Computes:
  • Pitcher Fatigue Score     (ERA penalty from 3-day workload)
  • Batter vs Pitcher Matchup Edge (wOBA, Stuff+, K%, Barrel%)
  • Bullpen Stress Score      (3-day workload × depth × ERA)
  • Clutch Index              (high-leverage situational performance)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from wbc_backend.domain.schemas import (
    BatterSnapshot, Matchup, PitcherSnapshot, TeamSnapshot,
)

logger = logging.getLogger(__name__)


@dataclass
class AdvancedFeatures:
    """All computed advanced features for a single matchup."""
    # Pitcher fatigue
    home_sp_fatigue: float = 0.0
    away_sp_fatigue: float = 0.0
    home_bullpen_fatigue: float = 0.0
    away_bullpen_fatigue: float = 0.0

    # Matchup edge
    home_matchup_edge: float = 0.0
    away_matchup_edge: float = 0.0
    home_bullpen_stress: float = 0.0
    away_bullpen_stress: float = 0.0

    # Travel & Environment
    home_travel_fatigue: float = 0.0
    away_travel_fatigue: float = 0.0
    park_factor: float = 1.0
    umpire_bias: float = 0.0

    # Clutch
    home_clutch_index: float = 0.0
    away_clutch_index: float = 0.0

    # Aggregated
    home_advantage_score: float = 0.0
    away_advantage_score: float = 0.0

    # High-value pitcher traits
    home_pitch_arsenal_entropy: float = 1.0
    away_pitch_arsenal_entropy: float = 1.0
    home_velocity_trend: float = 0.0
    away_velocity_trend: float = 0.0
    home_platoon_split: float = 0.320
    away_platoon_split: float = 0.320
    home_recent_inning_load: float = 1.0
    away_recent_inning_load: float = 1.0
    home_spin_rate_zscore: float = 0.0
    away_spin_rate_zscore: float = 0.0

    # Raw feature dict for ML models
    feature_dict: dict[str, float] = field(default_factory=dict)


def compute_pitcher_fatigue(pitcher: PitcherSnapshot | None) -> float:
    """
    Nonlinear pitcher fatigue score (0–1) using exponential decay (§ P1).

    Formula:
        load = max(0, pitch_count_3d - 20)
        base = 0.30 * (1 - exp(-0.06 * load))
        era_penalty = max(0, era_last_3 - career_era) / 3.0
        fatigue = clip(base + 0.3 * era_penalty, 0, 1)
    """
    import math
    if pitcher is None:
        return 0.0
    load = max(0, pitcher.pitch_count_last_3d - 20)
    base = 0.30 * (1.0 - math.exp(-0.06 * load))
    era_penalty = max(0.0, (pitcher.era_last_3 - pitcher.era)) / 3.0
    return min(1.0, base + 0.3 * era_penalty)


def compute_bullpen_fatigue(bullpen: list[PitcherSnapshot]) -> float:
    """
    Average nonlinear fatigue across bullpen with cascade effect.

    When >50% of arms are fatigued, penalty amplifies because
    the manager cannot avoid tired pitchers.
    """
    if not bullpen:
        return 0.0
    fatigues = [compute_pitcher_fatigue(p) for p in bullpen]
    avg = sum(fatigues) / len(fatigues)

    fatigued_count = sum(1 for f in fatigues if f > 0.15)
    fatigued_ratio = fatigued_count / len(bullpen)
    cascade = 1.0 + 0.5 * max(0, fatigued_ratio - 0.5)

    return min(1.0, avg * cascade)


def compute_matchup_edge(
    lineup: list[BatterSnapshot],
    opposing_sp: PitcherSnapshot | None,
) -> float:
    """
    Compute batter vs. pitcher matchup edge using:
      - wOBA differential
      - Stuff+ penalty
      - K% exposure
      - Barrel% offensive bonus
    """
    if not lineup or opposing_sp is None:
        return 0.0

    total_edge = 0.0
    for batter in lineup:
        # wOBA advantage: higher batter wOBA vs pitcher's expected allowed wOBA
        woba_diff = batter.woba - 0.320  # 0.320 = league average expected wOBA allowed

        # Stuff+ penalty: higher stuff+ means harder to hit
        stuff_penalty = (opposing_sp.stuff_plus - 100) / 200.0  # centered around 0

        # K% exposure: higher K/9 of pitcher penalises batters
        k_exposure = -(opposing_sp.k_per_9 - 8.5) / 20.0  # avg K/9 ~ 8.5

        # Barrel% bonus: higher barrel rate = more damage potential
        barrel_bonus = batter.barrel_pct / 50.0  # normalised

        edge = woba_diff - stuff_penalty + k_exposure + barrel_bonus
        total_edge += edge

    return total_edge / len(lineup)


def compute_bullpen_stress(
    team: TeamSnapshot,
    bullpen: list[PitcherSnapshot],
) -> float:
    """
    Bullpen Stress Score = workload_factor × inverse_depth × era_weight

    High stress → higher variance in bullpen performance.
    """
    workload = min(1.0, team.bullpen_pitches_3d / 250.0)
    depth_inv = 1.0 / max(1.0, team.bullpen_depth)
    era_weight = max(0.5, team.bullpen_era / 4.0)

    # Factor in individual reliever fatigue
    avg_fatigue = compute_bullpen_fatigue(bullpen)

    stress = workload * depth_inv * era_weight + 0.3 * avg_fatigue
    return min(1.0, stress)


def compute_clutch_index(
    team: TeamSnapshot,
    lineup: list[BatterSnapshot],
) -> float:
    """
    Clutch Index: team's ability to perform in high-leverage situations.

    Based on:
      - Team clutch wOBA vs baseline wOBA
      - Individual clutch wOBA in lineup
    """
    team_clutch_diff = team.clutch_woba - team.batting_woba

    if lineup:
        avg_clutch = sum(b.clutch_woba for b in lineup) / len(lineup)
        avg_base = sum(b.woba for b in lineup) / len(lineup)
        lineup_clutch_diff = avg_clutch - avg_base
    else:
        lineup_clutch_diff = 0.0

    # Scale to roughly [-0.5, 0.5] range
    return max(-0.5, min(0.5, 2.5 * team_clutch_diff + 1.5 * lineup_clutch_diff))


def compute_travel_fatigue(team: TeamSnapshot, current_tz: float) -> float:
    """
    Compute fatigue score from travel distance and time zone shifts.
    Formula:
        tz_delta = abs(team.time_zone_offset - current_tz)
        dist_factor = team.dist_traveled_prev_7d / 10000.0  # Normalized to 10k km
        return clip(0.15 * tz_delta + 0.1 * dist_factor, 0, 1)
    """
    tz_delta = abs(team.time_zone_offset - current_tz)
    dist_factor = team.dist_traveled_prev_7d / 10000.0
    return min(1.0, 0.15 * tz_delta + 0.1 * dist_factor)


def get_umpire_profile(umpire_id: str) -> float:
    """
    Returns strike zone bias (-1.0 to 1.0).
    Negative = wide (pitcher advantage), Positive = tight (batter advantage).
    """
    umpire_map = {
        "U-STRICT": 0.4,   # Tight zone -> more walks
        "U-WIDE": -0.5,    # Wide zone -> more K
    }
    return umpire_map.get(umpire_id, 0.0)


# ── High-Value Pitcher Features (§ P2) ──────────────────

def compute_pitch_arsenal_entropy(pitch_mix: dict[str, float]) -> float:
    """
    Pitch Arsenal Entropy — unpredictability of pitch selection.
    Higher entropy = harder for batters to sit on one pitch type.
    """
    import math as _math
    if not pitch_mix:
        return 1.0
    total = sum(pitch_mix.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for pct in pitch_mix.values():
        p = pct / total
        if p > 0:
            entropy -= p * _math.log(p)
    return round(entropy, 4)


def compute_velocity_trend(
    recent_velo: list[float],
    career_velo: float,
) -> float:
    """
    Velocity Trend — delta in mph vs career baseline.
    Negative = velocity drop (concern). > -1.5 is a strong negative signal.
    """
    if not recent_velo or career_velo <= 0:
        return 0.0
    return round(sum(recent_velo) / len(recent_velo) - career_velo, 2)


def compute_platoon_split_interaction(
    woba_vs_left: float,
    woba_vs_right: float,
    opponent_lhb_pct: float = 0.40,
) -> float:
    """
    Platoon Split — weighted wOBA-against based on opponent handedness mix.
    """
    return round(
        opponent_lhb_pct * woba_vs_left +
        (1 - opponent_lhb_pct) * woba_vs_right,
        4,
    )


def compute_recent_inning_load(
    innings_last_14d: float, season_avg_per_14d: float,
) -> float:
    """Recent Inning Load ratio. >1.2 = overuse, <0.8 = fresh."""
    if season_avg_per_14d <= 0:
        return 1.0
    return round(innings_last_14d / season_avg_per_14d, 3)


def compute_spin_rate_zscore(
    recent_spin: float, career_mean: float, career_std: float,
) -> float:
    """Spin Rate z-score from career baseline."""
    if career_std <= 0:
        return 0.0
    return round((recent_spin - career_mean) / career_std, 3)


def compute_climate_adjustment(
    temp_f: float = 72.0,
    humidity_pct: float = 0.50,
    wind_speed_mph: float = 0.0,
    wind_direction: str = "none",
    altitude_m: float = 0.0,
    is_dome: bool = False,
) -> dict[str, float]:
    """
    Climate-based run-scoring adjustment (§ P1 氣候特徵).

    Returns dict with run_factor, hr_factor, k_factor.
    """
    if is_dome:
        temp_f = 72.0
        humidity_pct = 0.50
        wind_speed_mph = 0.0
        wind_direction = "none"

    temp_delta = (temp_f - 72.0) / 10.0
    temp_adj = 1.0 + temp_delta * 0.015

    humid_delta = (humidity_pct - 0.50) / 0.10
    humid_adj = 1.0 - humid_delta * 0.005

    wind_adj = 1.0
    if wind_direction == "out":
        wind_adj = 1.0 + wind_speed_mph * 0.005
    elif wind_direction == "in":
        wind_adj = 1.0 - wind_speed_mph * 0.004

    alt_adj = 1.0 + (altitude_m / 1600.0) * 0.10

    run_factor = max(0.85, min(1.20, temp_adj * humid_adj * wind_adj * alt_adj))
    hr_factor = max(0.80, min(1.30, run_factor * 1.1))

    return {
        "run_factor": round(run_factor, 4),
        "hr_factor": round(hr_factor, 4),
        "k_factor": 1.0,
    }


def build_advanced_features(matchup: Matchup) -> AdvancedFeatures:
    """
    Compute all advanced features for a matchup.

    Returns an AdvancedFeatures object with all computed values
    and a flat feature_dict suitable for ML model input.
    """
    feats = AdvancedFeatures()

    # ── Pitcher Fatigue ──────────────────────────────────
    feats.home_sp_fatigue = compute_pitcher_fatigue(matchup.home_sp)
    feats.away_sp_fatigue = compute_pitcher_fatigue(matchup.away_sp)
    feats.home_bullpen_fatigue = compute_bullpen_fatigue(matchup.home_bullpen)
    feats.away_bullpen_fatigue = compute_bullpen_fatigue(matchup.away_bullpen)

    # ── Matchup Edge ─────────────────────────────────────
    feats.home_matchup_edge = compute_matchup_edge(
        matchup.home_lineup, matchup.away_sp,
    )
    feats.away_matchup_edge = compute_matchup_edge(
        matchup.away_lineup, matchup.home_sp,
    )

    # ── Bullpen Stress ───────────────────────────────────
    feats.home_bullpen_stress = compute_bullpen_stress(
        matchup.home, matchup.home_bullpen,
    )
    feats.away_bullpen_stress = compute_bullpen_stress(
        matchup.away, matchup.away_bullpen,
    )

    # ── Clutch Index ─────────────────────────────────────
    feats.home_clutch_index = compute_clutch_index(
        matchup.home, matchup.home_lineup,
    )
    feats.away_clutch_index = compute_clutch_index(
        matchup.away, matchup.away_lineup,
    )

    # ── High-Value Pitcher Features ─────────────────────
    home_lhb_pct = (
        sum(1 for batter in matchup.away_lineup if batter.vs_left_avg >= batter.vs_right_avg) / len(matchup.away_lineup)
        if matchup.away_lineup else 0.40
    )
    away_lhb_pct = (
        sum(1 for batter in matchup.home_lineup if batter.vs_left_avg >= batter.vs_right_avg) / len(matchup.home_lineup)
        if matchup.home_lineup else 0.40
    )

    if matchup.home_sp is not None:
        feats.home_pitch_arsenal_entropy = compute_pitch_arsenal_entropy(matchup.home_sp.pitch_mix)
        feats.home_velocity_trend = compute_velocity_trend(
            matchup.home_sp.recent_fastball_velos,
            matchup.home_sp.career_fastball_velo,
        )
        feats.home_platoon_split = compute_platoon_split_interaction(
            matchup.home_sp.woba_vs_left,
            matchup.home_sp.woba_vs_right,
            opponent_lhb_pct=home_lhb_pct,
        )
        feats.home_recent_inning_load = compute_recent_inning_load(
            matchup.home_sp.innings_last_14d,
            matchup.home_sp.season_avg_innings_per_14d,
        )
        feats.home_spin_rate_zscore = compute_spin_rate_zscore(
            matchup.home_sp.recent_spin_rate,
            matchup.home_sp.career_spin_rate_mean,
            matchup.home_sp.career_spin_rate_std,
        )

    if matchup.away_sp is not None:
        feats.away_pitch_arsenal_entropy = compute_pitch_arsenal_entropy(matchup.away_sp.pitch_mix)
        feats.away_velocity_trend = compute_velocity_trend(
            matchup.away_sp.recent_fastball_velos,
            matchup.away_sp.career_fastball_velo,
        )
        feats.away_platoon_split = compute_platoon_split_interaction(
            matchup.away_sp.woba_vs_left,
            matchup.away_sp.woba_vs_right,
            opponent_lhb_pct=away_lhb_pct,
        )
        feats.away_recent_inning_load = compute_recent_inning_load(
            matchup.away_sp.innings_last_14d,
            matchup.away_sp.season_avg_innings_per_14d,
        )
        feats.away_spin_rate_zscore = compute_spin_rate_zscore(
            matchup.away_sp.recent_spin_rate,
            matchup.away_sp.career_spin_rate_mean,
            matchup.away_sp.career_spin_rate_std,
        )

    # ── Travel & Environment ─────────────────────────────
    # Mock current venue TZ offset for calculation (e.g. Tokyo = +9)
    current_venue_tz = 9.0
    feats.home_travel_fatigue = compute_travel_fatigue(matchup.home, current_venue_tz)
    feats.away_travel_fatigue = compute_travel_fatigue(matchup.away, current_venue_tz)

    # Elevation: +10% park factor per 1000m elevation
    feats.park_factor = 1.0 + (matchup.elevation_m / 10000.0)
    feats.umpire_bias = get_umpire_profile(matchup.umpire_id)

    # ── Climate adjustment ───────────────────────────────
    climate = compute_climate_adjustment(
        temp_f=getattr(matchup, "temp_f", 72.0),
        humidity_pct=getattr(matchup, "humidity_pct", 0.50),
        wind_speed_mph=getattr(matchup, "wind_speed_mph", 0.0),
        wind_direction=getattr(matchup, "wind_direction", "none"),
        altitude_m=matchup.elevation_m,
        is_dome=getattr(matchup, "is_dome", False),
    )
    feats.park_factor *= climate["run_factor"]

    # ── Aggregate advantage scores ───────────────────────
    feats.home_advantage_score = (
        feats.home_matchup_edge
        + feats.home_clutch_index * 0.08
        - feats.home_sp_fatigue * 0.15
        - feats.home_travel_fatigue * 0.20 # Increased travel impact
    )
    feats.away_advantage_score = (
        feats.away_matchup_edge
        - feats.away_sp_fatigue * 0.15
        - feats.away_bullpen_stress * 0.10
        + feats.away_clutch_index * 0.08
    )

    # ── Flat feature dict for ML ─────────────────────────
    feats.feature_dict = {
        "home_sp_fatigue": round(feats.home_sp_fatigue, 4),
        "away_sp_fatigue": round(feats.away_sp_fatigue, 4),
        "home_bullpen_fatigue": round(feats.home_bullpen_fatigue, 4),
        "away_bullpen_fatigue": round(feats.away_bullpen_fatigue, 4),
        "home_matchup_edge": round(feats.home_matchup_edge, 4),
        "away_matchup_edge": round(feats.away_matchup_edge, 4),
        "home_bullpen_stress": round(feats.home_bullpen_stress, 4),
        "away_bullpen_stress": round(feats.away_bullpen_stress, 4),
        "home_clutch_index": round(feats.home_clutch_index, 4),
        "away_clutch_index": round(feats.away_clutch_index, 4),
        "sp_fatigue_diff": round(feats.home_sp_fatigue - feats.away_sp_fatigue, 4),
        "matchup_edge_diff": round(feats.home_matchup_edge - feats.away_matchup_edge, 4),
        "bullpen_stress_diff": round(feats.home_bullpen_stress - feats.away_bullpen_stress, 4),
        "clutch_diff": round(feats.home_clutch_index - feats.away_clutch_index, 4),
        "elo_diff": round(matchup.home.elo - matchup.away.elo, 1),
        "woba_diff": round(matchup.home.batting_woba - matchup.away.batting_woba, 4),
        "fip_diff": round(matchup.home.pitching_fip - matchup.away.pitching_fip, 2),
        "whip_diff": round(matchup.home.pitching_whip - matchup.away.pitching_whip, 2),
        "stuff_plus_diff": round(matchup.home.pitching_stuff_plus - matchup.away.pitching_stuff_plus, 1),
        "der_diff": round(matchup.home.der - matchup.away.der, 4),
        "bullpen_depth_diff": round(matchup.home.bullpen_depth - matchup.away.bullpen_depth, 1),
        "ops_plus_diff": round(matchup.home.batting_ops_plus - matchup.away.batting_ops_plus, 1),
        "rpg_diff": round(matchup.home.runs_per_game - matchup.away.runs_per_game, 2),
        "rapg_diff": round(matchup.home.runs_allowed_per_game - matchup.away.runs_allowed_per_game, 2),
        "roster_strength_diff": round(matchup.home.roster_strength_index - matchup.away.roster_strength_index, 1),
        "rest_days_diff": matchup.home.rest_days - matchup.away.rest_days,
        "win_pct_l10_diff": round(matchup.home.win_pct_last_10 - matchup.away.win_pct_last_10, 3),
        "travel_fatigue_diff": round(feats.home_travel_fatigue - feats.away_travel_fatigue, 4),
        "park_factor": round(feats.park_factor, 4),
        "umpire_bias": round(feats.umpire_bias, 4),
        "elevation_m": matchup.elevation_m,
        "is_neutral": 1.0 if matchup.neutral_site else 0.0,
        "climate_run_factor": climate["run_factor"],
        "climate_hr_factor": climate["hr_factor"],
        "pitch_arsenal_entropy_diff": round(feats.home_pitch_arsenal_entropy - feats.away_pitch_arsenal_entropy, 4),
        "velocity_trend_diff": round(feats.home_velocity_trend - feats.away_velocity_trend, 4),
        "platoon_split_diff": round(feats.home_platoon_split - feats.away_platoon_split, 4),
        "recent_inning_load_diff": round(feats.home_recent_inning_load - feats.away_recent_inning_load, 4),
        "spin_rate_zscore_diff": round(feats.home_spin_rate_zscore - feats.away_spin_rate_zscore, 4),
    }

    logger.debug("Advanced features for %s: %s", matchup.game_id, feats.feature_dict)
    return feats


# ── Utility: Feature names list for ML models ────────────────────────────────

FEATURE_NAMES = [
    "elo_diff", "woba_diff", "fip_diff", "whip_diff", "stuff_plus_diff",
    "der_diff", "bullpen_depth_diff", "ops_plus_diff", "rpg_diff", "rapg_diff",
    "home_sp_fatigue", "away_sp_fatigue", "sp_fatigue_diff",
    "home_matchup_edge", "away_matchup_edge", "matchup_edge_diff",
    "home_bullpen_stress", "away_bullpen_stress", "bullpen_stress_diff",
    "home_clutch_index", "away_clutch_index", "clutch_diff",
    "roster_strength_diff", "rest_days_diff", "win_pct_l10_diff",
    "travel_fatigue_diff", "park_factor", "umpire_bias", "elevation_m",
    "is_neutral", "climate_run_factor", "climate_hr_factor",
    "pitch_arsenal_entropy_diff", "velocity_trend_diff", "platoon_split_diff",
    "recent_inning_load_diff", "spin_rate_zscore_diff",
]
