"""
Advanced Feature Engineering for WBC.
Focuses on PA-level (Plate Appearance) interaction features.
"""
from typing import List, Dict, Tuple
from data.wbc_data import PitcherStats, BatterStats

def calculate_matchup_edge(batter: BatterStats, pitcher: PitcherStats) -> float:
    """
    Calculate the expected wOBA for a specific matchup.
    Formula: batter_wOBA * (pitcher_wOBA_allowed / league_avg_wOBA)
    Actually, we use a simplified version based on available fields.
    """
    # League average wOBA is roughly 0.320
    league_woba = 0.320
    
    # Pitcher wOBA allowed proxy: ERA / 4.0 adjusted by Stuff+
    # 100 Stuff+ is baseline. 120 is elite (-8% wOBA), 80 is poor (+8% wOBA)
    stuff_factor = 1.0 - (pitcher.stuff_plus - 100) / 250.0
    pitcher_factor = (pitcher.era / 4.2) * stuff_factor
    
    # Handedness adjustment (simplified)
    # If we had batter.vs_left_woba, we'd use it here.
    expected_woba = batter.woba * pitcher_factor
    
    # Floor/Ceiling to keep it realistic
    return max(0.200, min(0.500, expected_woba))

def aggregate_lineup_strength(lineup: List[BatterStats], pitcher: PitcherStats, default_woba: float = 0.320) -> float:
    """Aggregate the expected performance of a whole lineup against a pitcher."""
    if not lineup:
        # Fallback for backtesting/missing data
        return calculate_matchup_edge_simple(default_woba, pitcher)
    
    total_woba = sum(calculate_matchup_edge(b, pitcher) for b in lineup)
    return total_woba / len(lineup)

def calculate_matchup_edge_simple(base_woba: float, pitcher: PitcherStats) -> float:
    """Simplified matchup calculation for team-level wOBA."""
    pitcher_factor = (pitcher.era / 4.0) * (110 / pitcher.stuff_plus)
    return base_woba * pitcher_factor

def calculate_bullpen_fatigue_penalty(pitchers: List[PitcherStats]) -> float:
    """
    Calculate nonlinear bullpen fatigue penalty (§ P1 牛棚連鎖疲勞).

    Uses exponential model instead of linear:
      penalty = 1 + α * (1 - exp(-β * load))
    where load = normalized recent pitch count.

    Cascade effect: if multiple relievers are fatigued, the
    penalty compounds because the manager has fewer fresh options.
    """
    import math
    if not pitchers:
        return 1.0

    # α controls max penalty magnitude, β controls onset steepness
    ALPHA = 0.30   # max additional penalty = 30%
    BETA = 0.06    # steepness of fatigue curve
    FRESH_THRESHOLD = 20  # pitches below this = fully rested

    individual_fatigues = []
    fatigued_count = 0

    for p in pitchers:
        load = max(0, p.pitch_count_last_3d - FRESH_THRESHOLD)
        fatigue = ALPHA * (1.0 - math.exp(-BETA * load))
        individual_fatigues.append(fatigue)
        if load > 10:  # moderately fatigued
            fatigued_count += 1

    avg_fatigue = sum(individual_fatigues) / len(individual_fatigues)

    # Cascade effect: when >50% of pen is fatigued, penalty amplifies
    # because manager can't avoid tired arms
    fatigued_ratio = fatigued_count / len(pitchers)
    cascade_multiplier = 1.0 + 0.5 * max(0, fatigued_ratio - 0.5)

    penalty = 1.0 + avg_fatigue * cascade_multiplier
    return min(1.40, penalty)


# ── Climate Features ────────────────────────────────────

# WBC venue reference data (venue_id -> properties)
WBC_VENUES = {
    "tokyo_dome":       {"altitude_m": 40,  "dome": True,  "lat": 35.71},
    "taichung":         {"altitude_m": 84,  "dome": False, "lat": 24.18},
    "chase_field":      {"altitude_m": 331, "dome": True,  "lat": 33.45},
    "loanDepot_park":   {"altitude_m": 2,   "dome": True,  "lat": 25.78},
    "petco_park":       {"altitude_m": 7,   "dome": False, "lat": 32.71},
}

# Baseline: ~72°F, 50% humidity, 0 mph wind, sea level
_BASE_TEMP_F = 72.0
_BASE_HUMIDITY = 0.50
_BASE_ALTITUDE_M = 0


def calculate_climate_adjustment(
    temp_f: float = _BASE_TEMP_F,
    humidity_pct: float = _BASE_HUMIDITY,
    wind_speed_mph: float = 0.0,
    wind_direction: str = "none",  # "out", "in", "cross", "none"
    altitude_m: float = _BASE_ALTITUDE_M,
    is_dome: bool = False,
) -> Dict[str, float]:
    """
    Compute climate-based run-scoring adjustments.

    Returns dict with:
      - run_factor: multiplier on expected runs (1.0 = neutral)
      - hr_factor: multiplier on HR probability
      - k_factor: multiplier on strikeout probability
    """
    if is_dome:
        # Domed stadiums: only altitude matters
        temp_f = _BASE_TEMP_F
        humidity_pct = _BASE_HUMIDITY
        wind_speed_mph = 0.0
        wind_direction = "none"

    # Temperature effect: +1.5% runs per 10°F above baseline
    temp_delta = (temp_f - _BASE_TEMP_F) / 10.0
    temp_run_adj = 1.0 + temp_delta * 0.015

    # Humidity: high humidity → ball doesn't carry as well (dense air)
    # Each 10% above 50% → -0.5% runs
    humid_delta = (humidity_pct - _BASE_HUMIDITY) / 0.10
    humid_run_adj = 1.0 - humid_delta * 0.005

    # Wind: direction matters most
    wind_run_adj = 1.0
    if wind_direction == "out":
        wind_run_adj = 1.0 + wind_speed_mph * 0.005  # 10mph out → +5%
    elif wind_direction == "in":
        wind_run_adj = 1.0 - wind_speed_mph * 0.004  # 10mph in → -4%
    # cross wind: negligible

    # Altitude: air density decreases → ball carries
    # Coors Field (1600m) is ~10% boost; WBC venues mostly sea-level
    alt_run_adj = 1.0 + (altitude_m / 1600.0) * 0.10

    run_factor = temp_run_adj * humid_run_adj * wind_run_adj * alt_run_adj
    # Clamp to reasonable range
    run_factor = max(0.85, min(1.20, run_factor))

    hr_factor = max(0.80, min(1.30, run_factor * 1.1))  # HRs more sensitive
    k_factor = 1.0  # strikeouts not strongly weather-dependent

    return {
        "run_factor": round(run_factor, 4),
        "hr_factor": round(hr_factor, 4),
        "k_factor": round(k_factor, 4),
    }


# ── High-Value Pitcher Features (§ P2) ──────────────────

def calculate_pitch_arsenal_entropy(pitch_mix: Dict[str, float]) -> float:
    """
    Pitch Arsenal Entropy — measures how unpredictable a pitcher's
    pitch selection is. Higher entropy = harder to sit on one pitch.

    pitch_mix: {"FF": 0.55, "SL": 0.25, "CH": 0.15, "CU": 0.05}
    Returns entropy in [0, ~2.3] range (log base e).
    """
    import math
    if not pitch_mix:
        return 1.0  # default: moderate unpredictability
    total = sum(pitch_mix.values())
    if total <= 0:
        return 0.0
    entropy = 0.0
    for pct in pitch_mix.values():
        p = pct / total
        if p > 0:
            entropy -= p * math.log(p)
    return round(entropy, 4)


def calculate_velocity_trend(
    recent_velo: List[float],
    career_velo: float,
) -> float:
    """
    Velocity Trend — measures if pitcher is gaining or losing velocity.

    recent_velo: last 3 outings' avg fastball velocity (mph)
    career_velo: career avg fastball velocity

    Returns delta in mph (positive = gaining, negative = losing).
    A drop of >1.5 mph is a strong negative signal.
    """
    if not recent_velo or career_velo <= 0:
        return 0.0
    recent_avg = sum(recent_velo) / len(recent_velo)
    return round(recent_avg - career_velo, 2)


def calculate_platoon_split(
    woba_vs_left: float,
    woba_vs_right: float,
    opponent_lineup_lhb_pct: float = 0.40,
) -> float:
    """
    Platoon Split Interaction — weighted wOBA-against based on
    opponent lineup handedness composition.

    Returns expected wOBA-against for the specific lineup faced.
    Large splits (>0.040 wOBA) are exploitable.
    """
    return round(
        opponent_lineup_lhb_pct * woba_vs_left +
        (1 - opponent_lineup_lhb_pct) * woba_vs_right,
        4,
    )


def calculate_recent_inning_load(
    innings_last_14d: float,
    season_avg_innings_per_14d: float,
) -> float:
    """
    Recent Inning Load — ratio of recent workload to season average.

    > 1.2 indicates overuse risk, < 0.8 indicates fresh arm.
    """
    if season_avg_innings_per_14d <= 0:
        return 1.0
    return round(innings_last_14d / season_avg_innings_per_14d, 3)


def calculate_spin_rate_zscore(
    recent_spin: float,
    career_spin_mean: float,
    career_spin_std: float,
) -> float:
    """
    Spin Rate z-score — deviation from career baseline.

    Drop > 1.5 std indicates potential fatigue or injury concern.
    Rise > 1.5 std may indicate mechanical improvement.
    """
    if career_spin_std <= 0:
        return 0.0
    return round((recent_spin - career_spin_mean) / career_spin_std, 3)
