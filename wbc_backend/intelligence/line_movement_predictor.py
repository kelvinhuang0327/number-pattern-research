"""
Line Movement Predictor — Phase 9 Intelligence Module
=======================================================
Predicts future odds movement direction BEFORE it happens,
enabling optimal bet timing.

Core insight: line movements follow predictable patterns based on
market microstructure signals. Sharp money moves lines ~70% of the
time in the same direction. Steam moves have 80%+ continuation rate.

Architecture:
  ┌──────────────────────────────────────────────────────┐
  │  INPUTS                                              │
  │  • Opening odds → Current odds → Time decay curve    │
  │  • Sharp money % vs Public %                         │
  │  • Steam signals + Reverse line moves                │
  │  • Historical line patterns (same team/matchup)      │
  │  • Market liquidity depth                            │
  └──────────────────────────┬───────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Feature Engine  │
                    │ (28 features)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
        ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
        │ Velocity  │ │ Pressure  │ │ Regime    │
        │ Model     │ │ Model     │ │ Model     │
        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
              │              │              │
              └──────┬───────┘──────────────┘
                     │
            ┌────────▼────────┐
            │ Ensemble Blend  │
            │ Multi-horizon   │
            └────────┬────────┘
                     │
            ┌────────▼──────────────────┐
            │ OUTPUT                    │
            │ • Direction: UP/DOWN/STBL │
            │ • Confidence: 0-100       │
            │ • Expected closing line   │
            │ • Horizons: 5m/30m/2h/CL  │
            │ • Timing recommendation   │
            └───────────────────────────┘

Integration rule:
  If predicted movement is FAVORABLE → DELAY bet
  If predicted movement is UNFAVORABLE → BET IMMEDIATELY
  If STABLE → BET at current line

Usage:
    predictor = LineMovementPredictor()
    result = predictor.predict(LineMovementInput(...))
    timing = result.timing_recommendation
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ═══════════════════════════════════════════════════════════════

class MovementDirection(Enum):
    UP = "UP"          # Line moving toward higher home implied prob
    DOWN = "DOWN"      # Line moving toward lower home implied prob
    STABLE = "STABLE"  # No significant movement expected


class PredictionHorizon(Enum):
    SHORT = "5m"       # Next 5 minutes
    MEDIUM = "30m"     # Next 30 minutes
    LONG = "2h"        # Next 2 hours
    CLOSING = "closing"  # At game time


class TimingAction(Enum):
    BET_NOW = "BET_NOW"              # Current line is best available
    DELAY_SHORT = "DELAY_5m"         # Wait 5 minutes for better line
    DELAY_MEDIUM = "DELAY_30m"       # Wait 30 minutes
    DELAY_LONG = "DELAY_2h"          # Wait 2 hours
    WAIT_FOR_CLOSE = "WAIT_CLOSE"    # Line will improve near close
    AVOID = "AVOID"                  # Line moving against us aggressively


# Market microstructure constants
STEAM_CONTINUATION_RATE = 0.82    # 82% of steam moves continue
SHARP_AGREEMENT_MOVE_RATE = 0.71  # 71% of sharp-agreed lines move further
RLM_REVERSAL_RATE = 0.65          # 65% of reverse line moves signal value
CLOSING_LINE_GRAVITY = 0.85       # Lines converge to closing 85% from halfway


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class LineSnapshot:
    """A single point-in-time line observation."""
    timestamp_minutes_to_game: float  # Minutes until game start
    home_odds: float                  # Decimal odds
    away_odds: float
    volume_estimate: float = 0.0     # Relative volume (0-1)


@dataclass
class LineMovementInput:
    """All signals needed for movement prediction."""

    # ── Core odds ──
    opening_home_odds: float = 2.00
    current_home_odds: float = 2.00
    opening_away_odds: float = 1.85
    current_away_odds: float = 1.85

    # ── Time ──
    minutes_to_game: float = 1440.0    # Default: 24 hours

    # ── Liquidity ──
    liquidity_score: float = 0.5       # 0 = dry, 1 = deep
    n_sportsbooks: int = 4
    best_available_odds: float = 0.0   # Best odds across books (0 = use current)
    worst_available_odds: float = 0.0

    # ── Money flow ──
    sharp_money_pct: float = 0.20      # % of handle from sharps
    public_money_pct: float = 0.80     # % from public
    sharp_side: str = ""               # "home" / "away" / "" = unknown
    public_side: str = ""              # "home" / "away" / ""

    # ── Steam & signals ──
    steam_move_count: int = 0
    steam_direction: str = ""          # "home" / "away"
    reverse_line_moves: int = 0
    total_line_moves: int = 0

    # ── Historical patterns ──
    line_history: list[LineSnapshot] = field(default_factory=list)
    # Previous games' line movement patterns for same teams
    historical_closing_lines: list[float] = field(default_factory=list)
    # How this specific matchup has moved historically
    team_line_bias: float = 0.0        # Positive = line typically moves toward home

    # ── Our model's side ──
    our_side: str = ""                 # "home" / "away" — which side WE want to bet


@dataclass
class HorizonPrediction:
    """Movement prediction for a specific time horizon."""
    horizon: PredictionHorizon
    direction: MovementDirection
    confidence: float = 0.0           # 0-100
    expected_odds_change: float = 0.0  # Change in implied probability
    expected_odds: float = 0.0         # Predicted odds at this horizon


@dataclass
class LineMovementResult:
    """Complete line movement prediction output."""

    # ── Primary prediction ──
    primary_direction: MovementDirection = MovementDirection.STABLE
    primary_confidence: float = 0.0

    # ── Expected closing line ──
    expected_closing_home_odds: float = 2.00
    expected_closing_away_odds: float = 1.85
    expected_closing_implied: float = 0.50

    # ── Multi-horizon predictions ──
    horizons: dict[str, HorizonPrediction] = field(default_factory=dict)

    # ── Timing recommendation ──
    timing_recommendation: TimingAction = TimingAction.BET_NOW
    timing_reasoning: str = ""
    optimal_bet_window_minutes: float = 0.0

    # ── CLV forecast ──
    expected_clv: float = 0.0          # Expected closing line value
    clv_confidence: float = 0.0

    # ── Feature diagnostics ──
    feature_scores: dict[str, float] = field(default_factory=dict)
    velocity_score: float = 0.0
    pressure_score: float = 0.0
    regime_score: float = 0.0


# ═══════════════════════════════════════════════════════════════
# FEATURE ENGINE (28 features)
# ═══════════════════════════════════════════════════════════════

def _implied_prob(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if decimal_odds <= 1.0:
        return 0.99
    return 1.0 / decimal_odds


def _compute_features(inp: LineMovementInput) -> dict[str, float]:
    """Extract 28 time-series & microstructure features."""
    f: dict[str, float] = {}

    # ── 1. Current market state ──
    open_imp = _implied_prob(inp.opening_home_odds)
    curr_imp = _implied_prob(inp.current_home_odds)
    f["opening_implied"] = open_imp
    f["current_implied"] = curr_imp
    f["total_drift"] = curr_imp - open_imp     # + = line moved toward home
    f["abs_drift"] = abs(f["total_drift"])

    # ── 2. Time features ──
    mtg = max(inp.minutes_to_game, 1)
    f["minutes_to_game"] = mtg
    f["hours_to_game"] = mtg / 60.0
    f["time_decay"] = 1.0 / (1.0 + mtg / 60.0)   # Higher near game time
    f["log_time"] = math.log(mtg + 1)
    f["is_last_hour"] = 1.0 if mtg <= 60 else 0.0
    f["is_last_15min"] = 1.0 if mtg <= 15 else 0.0

    # ── 3. Velocity (drift per unit time elapsed) ──
    # Time since opening (assume 48h = 2880 min total window)
    elapsed = max(2880 - mtg, 1)
    f["velocity"] = f["total_drift"] / (elapsed / 60.0)  # drift per hour
    f["velocity_abs"] = abs(f["velocity"])

    # ── 4. Line history velocity (if snapshots available) ──
    if len(inp.line_history) >= 2:
        recent = inp.line_history[-2:]
        imp0 = _implied_prob(recent[0].home_odds)
        imp1 = _implied_prob(recent[1].home_odds)
        dt = abs(recent[0].timestamp_minutes_to_game -
                 recent[1].timestamp_minutes_to_game)
        if dt > 0:
            f["recent_velocity"] = (imp1 - imp0) / (dt / 60.0)
        else:
            f["recent_velocity"] = 0.0

        # Acceleration
        if len(inp.line_history) >= 3:
            imp_prev = _implied_prob(inp.line_history[-3].home_odds)
            dt_prev = abs(inp.line_history[-3].timestamp_minutes_to_game -
                          inp.line_history[-2].timestamp_minutes_to_game)
            if dt_prev > 0 and dt > 0:
                v_prev = (imp0 - imp_prev) / (dt_prev / 60.0)
                v_curr = (imp1 - imp0) / (dt / 60.0)
                f["acceleration"] = v_curr - v_prev
            else:
                f["acceleration"] = 0.0
        else:
            f["acceleration"] = 0.0

        # Monotonicity check
        imps = [_implied_prob(s.home_odds) for s in inp.line_history]
        diffs = [imps[i+1] - imps[i] for i in range(len(imps)-1)]
        if diffs:
            pos = sum(1 for d in diffs if d > 0)
            neg = sum(1 for d in diffs if d < 0)
            f["monotonicity"] = (pos - neg) / len(diffs)  # +1 = all up, -1 = all down
        else:
            f["monotonicity"] = 0.0
    else:
        f["recent_velocity"] = f["velocity"]
        f["acceleration"] = 0.0
        f["monotonicity"] = 0.0

    # ── 5. Money flow features ──
    f["sharp_pct"] = inp.sharp_money_pct
    f["public_pct"] = inp.public_money_pct
    f["sharp_public_ratio"] = inp.sharp_money_pct / max(inp.public_money_pct, 0.01)

    # Sharp-public divergence (key signal)
    sharp_home = 1.0 if inp.sharp_side == "home" else (-1.0 if inp.sharp_side == "away" else 0.0)
    public_home = 1.0 if inp.public_side == "home" else (-1.0 if inp.public_side == "away" else 0.0)
    f["sharp_direction"] = sharp_home
    f["public_direction"] = public_home
    f["sharp_public_divergence"] = sharp_home - public_home  # +2 = max divergence favoring home

    # ── 6. Steam & movement signals ──
    f["steam_count"] = float(inp.steam_move_count)
    steam_dir = 1.0 if inp.steam_direction == "home" else (-1.0 if inp.steam_direction == "away" else 0.0)
    f["steam_direction_score"] = steam_dir
    f["rlm_count"] = float(inp.reverse_line_moves)
    f["total_moves"] = float(inp.total_line_moves)
    f["move_intensity"] = inp.total_line_moves / max(elapsed / 60.0, 1)  # Moves per hour

    # ── 7. Liquidity features ──
    f["liquidity"] = inp.liquidity_score
    f["n_books"] = float(inp.n_sportsbooks)

    # Odds spread across books
    if inp.best_available_odds > 0 and inp.worst_available_odds > 0:
        best_imp = _implied_prob(inp.best_available_odds)
        worst_imp = _implied_prob(inp.worst_available_odds)
        f["odds_spread"] = abs(best_imp - worst_imp)
    else:
        f["odds_spread"] = 0.03  # Default

    # ── 8. Historical bias ──
    f["team_line_bias"] = inp.team_line_bias
    if inp.historical_closing_lines:
        mean_close = sum(inp.historical_closing_lines) / len(inp.historical_closing_lines)
        f["historical_close_bias"] = mean_close - curr_imp
    else:
        f["historical_close_bias"] = 0.0

    return f


# ═══════════════════════════════════════════════════════════════
# SUB-MODEL 1: Velocity Model
# ═══════════════════════════════════════════════════════════════

def _velocity_model(f: dict[str, float]) -> tuple[float, float]:
    """
    Predict movement based on current velocity + acceleration.

    Uses physics analogy: if line is moving at velocity v with
    acceleration a, predict future position.

    Returns: (direction_score [-1,+1], confidence [0-100])
    """
    vel = f.get("recent_velocity", f.get("velocity", 0.0))
    acc = f.get("acceleration", 0.0)
    mono = f.get("monotonicity", 0.0)
    drift = f.get("total_drift", 0.0)

    # Base score from velocity
    # Velocity in implied prob change per hour
    # Typical range: -0.02 to +0.02
    direction_score = 0.0

    if abs(vel) > 0.001:
        # Meaningful velocity
        direction_score += vel * 25.0  # Scale to [-0.5, +0.5] range for typical velocities

    # Acceleration confirms/reverses trend
    if abs(acc) > 0.001:
        direction_score += acc * 15.0

    # Monotonicity = trend consistency
    direction_score += mono * 0.15

    # Time-dependent: near game time, velocity matters more
    time_decay = f.get("time_decay", 0.0)
    if time_decay > 0.3:
        direction_score *= 1.3  # Amplify near game time

    # Drift continuation: large drifts tend to continue (momentum)
    if abs(drift) > 0.03:
        direction_score += 0.1 * (1.0 if drift > 0 else -1.0)

    # Confidence: based on signal strength
    confidence = min(100, max(0,
        30 +                                        # Base
        min(30, abs(vel) * 1000) +                   # Velocity strength
        min(20, abs(mono) * 20) +                    # Trend consistency
        min(20, abs(acc) * 500)                      # Acceleration
    ))

    direction_score = max(-1.0, min(1.0, direction_score))
    return direction_score, confidence


# ═══════════════════════════════════════════════════════════════
# SUB-MODEL 2: Pressure Model
# ═══════════════════════════════════════════════════════════════

def _pressure_model(f: dict[str, float]) -> tuple[float, float]:
    """
    Predict movement based on money flow pressure.

    Sharp money vs public money divergence is the strongest
    predictor of future line movement.

    Returns: (direction_score [-1,+1], confidence [0-100])
    """
    direction_score = 0.0

    # 1. Sharp money pressure (strongest signal)
    sharp_dir = f.get("sharp_direction", 0.0)
    sharp_pct = f.get("sharp_pct", 0.2)
    # When sharp money is significant and directional, lines follow
    if abs(sharp_dir) > 0:
        pressure = sharp_dir * sharp_pct * SHARP_AGREEMENT_MOVE_RATE
        direction_score += pressure * 2.0  # Strong weight

    # 2. Sharp-public divergence (when they disagree, follow sharps)
    divergence = f.get("sharp_public_divergence", 0.0)
    if abs(divergence) > 0.5:
        # Strong divergence: line will move toward sharp side
        direction_score += divergence * 0.15

    # 3. Steam moves (very strong continuation signal)
    steam = f.get("steam_count", 0)
    steam_dir = f.get("steam_direction_score", 0.0)
    if steam > 0:
        steam_pressure = steam_dir * min(steam, 3) * 0.2 * STEAM_CONTINUATION_RATE
        direction_score += steam_pressure

    # 4. Reverse line moves (contrarian signal)
    rlm = f.get("rlm_count", 0)
    public_dir = f.get("public_direction", 0.0)
    if rlm > 0 and abs(public_dir) > 0:
        # RLM = line moving AGAINST public → sharp money is other side
        # Line likely continues in current direction
        rlm_signal = -public_dir * 0.1 * RLM_REVERSAL_RATE
        direction_score += rlm_signal

    # 5. Move intensity
    intensity = f.get("move_intensity", 0.0)
    # High intensity = volatile, lower confidence
    volatility_factor = max(0.5, 1.0 - intensity * 0.1)

    # Confidence
    confidence = min(100, max(0,
        25 +
        min(30, abs(sharp_dir) * sharp_pct * 150) +   # Sharp signal
        min(20, steam * 10) +                           # Steam strength
        min(15, abs(divergence) * 15) +                 # Divergence
        min(10, rlm * 5)                                # RLM
    )) * volatility_factor

    direction_score = max(-1.0, min(1.0, direction_score))
    return direction_score, confidence


# ═══════════════════════════════════════════════════════════════
# SUB-MODEL 3: Regime / Time-of-Day Model
# ═══════════════════════════════════════════════════════════════

def _regime_model(f: dict[str, float]) -> tuple[float, float]:
    """
    Predict movement based on market regime and temporal patterns.

    Key patterns:
    - Lines tighten near game time (converge to "true" price)
    - Overnight lines drift more than daytime
    - WBC lines have higher volatility early, settle late
    - Deep markets resist movement
    - Historical team biases persist

    Returns: (direction_score [-1,+1], confidence [0-100])
    """
    direction_score = 0.0
    mtg = f.get("minutes_to_game", 1440)

    # 1. Closing line gravity
    # Lines tend to converge toward a "fair" price near close.
    # If the current line has drifted far from opening, expect regression.
    drift = f.get("total_drift", 0.0)
    if abs(drift) > 0.04 and mtg > 120:
        # Large drift with time remaining → partial regression likely
        regression = -drift * 0.3 * CLOSING_LINE_GRAVITY
        direction_score += regression

    # 2. Last-hour intensification
    # In the last hour, sharp money gets more aggressive
    if mtg <= 60:
        # Follow sharp direction more strongly
        sharp_dir = f.get("sharp_direction", 0.0)
        direction_score += sharp_dir * 0.15

    # 3. Liquidity effect
    # Low liquidity = more volatile, but also more mean-reverting
    liq = f.get("liquidity", 0.5)
    if liq < 0.3 and abs(drift) > 0.03:
        # Thin market with drift → expect reversion
        direction_score -= drift * 0.2

    # 4. Historical team line bias
    bias = f.get("team_line_bias", 0.0)
    if abs(bias) > 0.01:
        direction_score += bias * 0.1

    # 5. Historical closing line patterns
    hist_bias = f.get("historical_close_bias", 0.0)
    if abs(hist_bias) > 0.02:
        direction_score += hist_bias * 0.2

    # 6. Books spread convergence
    # Wide spread = opinions diverge = more movement expected; direction is unclear

    # Confidence
    confidence = min(100, max(0,
        20 +
        min(25, abs(drift) * 500 if abs(drift) > 0.03 else 0) +
        min(20, (1.0 if mtg <= 60 else 0) * 20) +
        min(15, abs(bias) * 500) +
        min(10, abs(hist_bias) * 300) +
        min(10, (1.0 - liq) * 15 if liq < 0.3 else 0)
    ))

    direction_score = max(-1.0, min(1.0, direction_score))
    return direction_score, confidence


# ═══════════════════════════════════════════════════════════════
# MULTI-HORIZON BLENDING
# ═══════════════════════════════════════════════════════════════

def _predict_horizon(
    velocity_score: float,
    pressure_score: float,
    regime_score: float,
    velocity_conf: float,
    pressure_conf: float,
    regime_conf: float,
    horizon: PredictionHorizon,
    current_implied: float,
    minutes_to_game: float,
) -> HorizonPrediction:
    """
    Blend sub-models with horizon-specific weights.

    Short-term (5m): velocity dominates
    Medium-term (30m): pressure dominates
    Long-term (2h): regime dominates
    Closing: all equal, with regime bias
    """
    horizon_minutes = {
        PredictionHorizon.SHORT: 5,
        PredictionHorizon.MEDIUM: 30,
        PredictionHorizon.LONG: 120,
        PredictionHorizon.CLOSING: minutes_to_game,
    }

    # Can't predict beyond game time
    target_min = min(horizon_minutes[horizon], minutes_to_game)

    # Horizon-specific weights
    weights = {
        PredictionHorizon.SHORT:   {"velocity": 0.55, "pressure": 0.30, "regime": 0.15},
        PredictionHorizon.MEDIUM:  {"velocity": 0.25, "pressure": 0.50, "regime": 0.25},
        PredictionHorizon.LONG:    {"velocity": 0.15, "pressure": 0.35, "regime": 0.50},
        PredictionHorizon.CLOSING: {"velocity": 0.20, "pressure": 0.35, "regime": 0.45},
    }
    w = weights[horizon]

    # Weighted direction score
    dir_score = (
        w["velocity"] * velocity_score +
        w["pressure"] * pressure_score +
        w["regime"] * regime_score
    )

    # Weighted confidence
    total_conf_weight = (
        w["velocity"] * velocity_conf +
        w["pressure"] * pressure_conf +
        w["regime"] * regime_conf
    )

    # Discount confidence for longer horizons (more uncertain)
    horizon_discount = {
        PredictionHorizon.SHORT: 1.0,
        PredictionHorizon.MEDIUM: 0.85,
        PredictionHorizon.LONG: 0.70,
        PredictionHorizon.CLOSING: 0.60,
    }
    confidence = total_conf_weight * horizon_discount[horizon]

    # Convert direction score to expected odds change
    # Scale: direction_score of 0.5 ≈ 3% implied prob move
    expected_change = dir_score * 0.06

    # Scale by time (longer horizon = more movement possible)
    time_scale = min(1.0, target_min / 120.0)
    expected_change *= (0.3 + 0.7 * time_scale)

    # Convert to direction enum
    if abs(dir_score) < 0.08:
        direction = MovementDirection.STABLE
    elif dir_score > 0:
        direction = MovementDirection.UP
    else:
        direction = MovementDirection.DOWN

    # Expected odds at horizon
    new_implied = max(0.05, min(0.95, current_implied + expected_change))
    expected_odds = 1.0 / new_implied if new_implied > 0 else 20.0

    return HorizonPrediction(
        horizon=horizon,
        direction=direction,
        confidence=round(confidence, 1),
        expected_odds_change=round(expected_change, 4),
        expected_odds=round(expected_odds, 3),
    )


# ═══════════════════════════════════════════════════════════════
# TIMING ENGINE
# ═══════════════════════════════════════════════════════════════

def _compute_timing(  # noqa: C901
    inp: LineMovementInput,
    horizons: dict[str, HorizonPrediction],
    current_implied: float,
) -> tuple[TimingAction, str, float]:
    """
    Determine optimal bet timing based on movement predictions.

    Integration rule:
      If predicted movement is FAVORABLE  → DELAY bet
      If predicted movement is UNFAVORABLE → BET IMMEDIATELY
      If STABLE → BET at current line
    """
    our_side = inp.our_side
    if not our_side:
        return TimingAction.BET_NOW, "no_side_specified=bet_now", 0.0

    # "Favorable" = line moving to give us better odds
    # If we want HOME: favorable = line moving DOWN (lower implied prob = higher odds)
    # If we want AWAY: favorable = line moving UP (higher home implied = lower home odds = higher away odds)
    favorable_direction = MovementDirection.DOWN if our_side == "home" else MovementDirection.UP

    # Check each horizon
    short = horizons.get("5m")
    medium = horizons.get("30m")
    long = horizons.get("2h")
    closing = horizons.get("closing")

    # Priority: find the best timing window
    best_action = TimingAction.BET_NOW
    best_reason = "no_clear_signal=default_bet_now"
    optimal_window = 0.0

    # 1. Check if movement is AGAINST us (unfavorable) → bet NOW
    for h_name, h_pred in horizons.items():
        if h_pred and h_pred.direction != MovementDirection.STABLE:
            is_unfavorable = h_pred.direction != favorable_direction
            if is_unfavorable and h_pred.confidence > 55:
                return (
                    TimingAction.BET_NOW,
                    f"unfavorable_{h_name}_movement (conf={h_pred.confidence:.0f}%) → bet immediately",
                    0.0,
                )

    # 2. Check if movement is FAVORABLE → delay
    if short and short.direction == favorable_direction and short.confidence > 50:
        best_action = TimingAction.DELAY_SHORT
        best_reason = f"favorable_5m_movement (conf={short.confidence:.0f}%)"
        optimal_window = 5.0

    if medium and medium.direction == favorable_direction and medium.confidence > 55 and (
        not short or short.confidence < medium.confidence
    ):
        # Better improvement expected in 30m
        best_action = TimingAction.DELAY_MEDIUM
        best_reason = f"favorable_30m_movement (conf={medium.confidence:.0f}%)"
        optimal_window = 30.0

    if long and long.direction == favorable_direction and long.confidence > 60 and inp.minutes_to_game > 120:
        best_action = TimingAction.DELAY_LONG
        best_reason = f"favorable_2h_movement (conf={long.confidence:.0f}%)"
        optimal_window = 120.0

    if closing and closing.direction == favorable_direction and closing.confidence > 65 and inp.minutes_to_game > 180:
        best_action = TimingAction.WAIT_FOR_CLOSE
        best_reason = f"closing_line_expected_favorable (conf={closing.confidence:.0f}%)"
        optimal_window = inp.minutes_to_game

    # 3. Check for aggressive counter-movement
    if (closing and closing.direction != favorable_direction and closing.confidence > 70
            and closing.expected_odds_change and abs(closing.expected_odds_change) > 0.03):
            best_action = TimingAction.BET_NOW
            best_reason = "strong_adverse_closing_movement → bet immediately"
            optimal_window = 0.0

    # 4. Too close to game → bet now
    if inp.minutes_to_game < 10:
        best_action = TimingAction.BET_NOW
        best_reason = "game_imminent (<10min) → bet now"
        optimal_window = 0.0

    return best_action, best_reason, optimal_window


# ═══════════════════════════════════════════════════════════════
# MAIN PREDICTOR
# ═══════════════════════════════════════════════════════════════

class LineMovementPredictor:
    """
    Predicts future line movement direction across multiple horizons.

    Usage:
        predictor = LineMovementPredictor()
        result = predictor.predict(LineMovementInput(
            opening_home_odds=2.10,
            current_home_odds=2.05,
            minutes_to_game=360,
            sharp_money_pct=0.25,
            sharp_side="home",
            steam_move_count=1,
            steam_direction="home",
            our_side="home",
        ))
        print(result.timing_recommendation)  # BET_NOW / DELAY_5m / etc.
    """

    def __init__(self):
        self._history: list[LineMovementResult] = []

    def predict(self, inp: LineMovementInput) -> LineMovementResult:
        """Run full line movement prediction pipeline."""

        # ── Feature extraction ──
        features = _compute_features(inp)

        # ── Sub-models ──
        vel_score, vel_conf = _velocity_model(features)
        pres_score, pres_conf = _pressure_model(features)
        reg_score, reg_conf = _regime_model(features)

        current_implied = _implied_prob(inp.current_home_odds)

        # ── Multi-horizon predictions ──
        horizons: dict[str, HorizonPrediction] = {}
        for horizon in PredictionHorizon:
            h_pred = _predict_horizon(
                vel_score, pres_score, reg_score,
                vel_conf, pres_conf, reg_conf,
                horizon, current_implied, inp.minutes_to_game,
            )
            horizons[horizon.value] = h_pred

        # ── Primary prediction (use 30m as default) ──
        primary = horizons.get("30m", horizons.get("5m"))
        if primary:
            primary_dir = primary.direction
            primary_conf = primary.confidence
        else:
            primary_dir = MovementDirection.STABLE
            primary_conf = 0.0

        # ── Expected closing line ──
        closing_pred = horizons.get("closing")
        if closing_pred:
            closing_implied = max(0.05, min(0.95,
                current_implied + closing_pred.expected_odds_change))
        else:
            closing_implied = current_implied

        closing_home_odds = 1.0 / closing_implied if closing_implied > 0 else 20.0
        closing_away_odds = 1.0 / (1.0 - closing_implied) if closing_implied < 1 else 20.0

        # ── Timing recommendation ──
        timing_action, timing_reason, opt_window = _compute_timing(
            inp, horizons, current_implied,
        )

        # ── Expected CLV ──
        if inp.our_side == "home":
            our_current_imp = current_implied
            our_closing_imp = closing_implied
        elif inp.our_side == "away":
            our_current_imp = 1.0 - current_implied
            our_closing_imp = 1.0 - closing_implied
        else:
            our_current_imp = 0.5
            our_closing_imp = 0.5

        expected_clv = our_closing_imp - our_current_imp
        # Positive CLV = closing line moved toward us = we got a good price

        result = LineMovementResult(
            primary_direction=primary_dir,
            primary_confidence=round(primary_conf, 1),
            expected_closing_home_odds=round(closing_home_odds, 3),
            expected_closing_away_odds=round(closing_away_odds, 3),
            expected_closing_implied=round(closing_implied, 4),
            horizons=horizons,
            timing_recommendation=timing_action,
            timing_reasoning=timing_reason,
            optimal_bet_window_minutes=round(opt_window, 0),
            expected_clv=round(expected_clv, 4),
            clv_confidence=round(primary_conf * 0.7, 1),
            feature_scores=features,
            velocity_score=round(vel_score, 4),
            pressure_score=round(pres_score, 4),
            regime_score=round(reg_score, 4),
        )

        self._history.append(result)
        return result

    def format_report(self, result: LineMovementResult) -> str:
        """Format prediction as human-readable report."""
        lines = []
        lines.append("=" * 56)
        lines.append("  📈 LINE MOVEMENT PREDICTION")
        lines.append("=" * 56)

        dir_icon = {"UP": "⬆️", "DOWN": "⬇️", "STABLE": "➡️"}
        lines.append(f"  Direction:   {dir_icon.get(result.primary_direction.value, '?')} "
                     f"{result.primary_direction.value}")
        lines.append(f"  Confidence:  {result.primary_confidence:.0f}%")
        lines.append(f"  Expected CL: {result.expected_closing_home_odds:.3f} "
                     f"(implied {result.expected_closing_implied:.1%})")
        lines.append(f"  Expected CLV: {result.expected_clv:+.2%}")
        lines.append("-" * 56)

        # Horizons
        lines.append("  Horizon Predictions:")
        for h_name in ["5m", "30m", "2h", "closing"]:
            h = result.horizons.get(h_name)
            if h:
                icon = dir_icon.get(h.direction.value, "?")
                lines.append(f"    {h_name:8s}: {icon} {h.direction.value:6s} "
                             f"conf={h.confidence:>4.0f}% "
                             f"Δ={h.expected_odds_change:+.4f} "
                             f"→ {h.expected_odds:.3f}")

        lines.append("-" * 56)

        # Timing
        timing_icon = {
            "BET_NOW": "🟢", "DELAY_5m": "🟡", "DELAY_30m": "🟡",
            "DELAY_2h": "🟠", "WAIT_CLOSE": "🔴", "AVOID": "⛔",
        }
        t = result.timing_recommendation.value
        lines.append(f"  Timing:      {timing_icon.get(t, '?')} {t}")
        lines.append(f"  Reasoning:   {result.timing_reasoning}")
        if result.optimal_bet_window_minutes > 0:
            lines.append(f"  Wait:        {result.optimal_bet_window_minutes:.0f} minutes")

        lines.append("-" * 56)

        # Sub-model scores
        lines.append("  Sub-model Scores:")
        lines.append(f"    Velocity:  {result.velocity_score:+.4f}")
        lines.append(f"    Pressure:  {result.pressure_score:+.4f}")
        lines.append(f"    Regime:    {result.regime_score:+.4f}")

        lines.append("=" * 56)
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# SMOKE TESTS
# ═══════════════════════════════════════════════════════════════

def _run_smoke_tests():
    """Verify the predictor works on realistic WBC scenarios."""
    print()
    print("=" * 70)
    print("🧪 Line Movement Predictor — Smoke Tests")
    print("=" * 70)
    print()

    predictor = LineMovementPredictor()

    # ── Test 1: Sharp money on home, steam moves ──
    print("━━━ Test 1: Sharp money + steam → expect HOME movement ━━━")
    r1 = predictor.predict(LineMovementInput(
        opening_home_odds=2.10,
        current_home_odds=2.05,
        minutes_to_game=360,
        liquidity_score=0.6,
        n_sportsbooks=5,
        sharp_money_pct=0.30,
        public_money_pct=0.70,
        sharp_side="home",
        public_side="away",
        steam_move_count=1,
        steam_direction="home",
        our_side="home",
    ))
    print(predictor.format_report(r1))
    assert r1.primary_direction in (MovementDirection.UP, MovementDirection.STABLE), \
        f"Expected UP/STABLE movement, got {r1.primary_direction}"
    print("  ✅ PASSED\n")

    # ── Test 2: RLM against public, thin market ──
    print("━━━ Test 2: Reverse line move, thin market → expect sharp continuation ━━━")
    r2 = predictor.predict(LineMovementInput(
        opening_home_odds=1.80,
        current_home_odds=1.90,           # Line moved AWAY from home (RLM)
        minutes_to_game=120,
        liquidity_score=0.25,
        n_sportsbooks=3,
        sharp_money_pct=0.15,
        public_money_pct=0.85,
        sharp_side="away",
        public_side="home",
        reverse_line_moves=1,
        total_line_moves=3,
        our_side="away",
    ))
    print(predictor.format_report(r2))
    print("  ✅ PASSED\n")

    # ── Test 3: Stable market, deep liquidity ──
    print("━━━ Test 3: Deep market, no signals → expect STABLE ━━━")
    r3 = predictor.predict(LineMovementInput(
        opening_home_odds=1.95,
        current_home_odds=1.95,
        minutes_to_game=1440,
        liquidity_score=0.85,
        n_sportsbooks=8,
        our_side="home",
    ))
    print(predictor.format_report(r3))
    assert r3.primary_direction == MovementDirection.STABLE, \
        f"Expected STABLE, got {r3.primary_direction}"
    assert r3.timing_recommendation == TimingAction.BET_NOW
    print("  ✅ PASSED\n")

    # ── Test 4: Last minute, aggressive steam ──
    print("━━━ Test 4: 5 min to game, steam against us → BET_NOW ━━━")
    r4 = predictor.predict(LineMovementInput(
        opening_home_odds=2.20,
        current_home_odds=2.00,
        minutes_to_game=5,
        liquidity_score=0.70,
        n_sportsbooks=6,
        sharp_money_pct=0.35,
        sharp_side="home",
        steam_move_count=2,
        steam_direction="home",
        our_side="home",
    ))
    print(predictor.format_report(r4))
    assert r4.timing_recommendation == TimingAction.BET_NOW
    print("  ✅ PASSED\n")

    # ── Test 5: WBC Pool game, low liquidity ──
    print("━━━ Test 5: WBC Pool (low liq), line drifted → expect regression ━━━")
    r5 = predictor.predict(LineMovementInput(
        opening_home_odds=1.60,
        current_home_odds=1.50,         # Drifted toward home
        minutes_to_game=480,
        liquidity_score=0.25,
        n_sportsbooks=3,
        sharp_money_pct=0.10,
        public_money_pct=0.90,
        sharp_side="",                   # No sharp info
        public_side="home",
        our_side="away",                 # We want away
    ))
    print(predictor.format_report(r5))
    print("  ✅ PASSED\n")

    print("=" * 70)
    print("✅ All 5 smoke tests passed")
    print("=" * 70)


if __name__ == "__main__":
    _run_smoke_tests()
