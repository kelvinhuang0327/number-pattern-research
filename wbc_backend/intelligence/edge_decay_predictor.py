"""
Edge Decay Predictor — Institutional Intelligence Module
==========================================================
Predicts how long a detected betting edge will remain exploitable
before market efficiency erodes it.

Architecture:
  ┌──────────────────────────────────────────────────────────┐
  │ INPUTS                                                   │
  │ • Market micro: velocity, accel, liquidity, book count   │
  │ • Model agreement: stddev, mean‑drift, momentum          │
  │ • Market signals: sharp %, RLM, steam, time‑to‑game      │
  │ • Historical memory: similar edges, league decay profile  │
  └────────────────────────┬─────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
      ┌─────▼─────┐ ┌─────▼─────┐ ┌─────▼─────┐
      │ Survival  │ │ Hazard    │ │ Volatility│
      │ Regress.  │ │ Function  │ │ Model     │
      └─────┬─────┘ └─────┬─────┘ └─────┬─────┘
            │              │              │
            └──────┬───────┘──────────────┘
                   │
          ┌────────▼──────────┐
          │ Weighted Ensemble │
          └────────┬──────────┘
                   │
          ┌────────▼──────────────────────────┐
          │ OUTPUT                            │
          │ • half_life_seconds: float        │
          │ • decay_curve: list[float]        │
          │ • confidence_score: 0‑100         │
          │ • urgency_level: UrgencyLevel     │
          │ • lower / upper bounds (seconds)  │
          └───────────────────────────────────┘

Decision rules:
  half_life < 180 s   → EXECUTE_IMMEDIATELY
  half_life < 600 s   → EXECUTE_SOON
  half_life < 3600 s  → MONITOR
  half_life < 14400 s → WAIT
  otherwise           → EXPIRED  (edge already gone)
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from enum import Enum


# ═══════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ═══════════════════════════════════════════════════════════════

class UrgencyLevel(Enum):
    """How urgently the edge must be acted upon."""
    EXECUTE_IMMEDIATELY = "EXECUTE_IMMEDIATELY"
    EXECUTE_SOON = "EXECUTE_SOON"
    MONITOR = "MONITOR"
    WAIT = "WAIT"
    EXPIRED = "EXPIRED"


# Urgency thresholds (seconds)
_URGENCY_THRESHOLDS: list[tuple[float, UrgencyLevel]] = [
    (180.0, UrgencyLevel.EXECUTE_IMMEDIATELY),
    (600.0, UrgencyLevel.EXECUTE_SOON),
    (3600.0, UrgencyLevel.MONITOR),
    (14400.0, UrgencyLevel.WAIT),
]

# Ensemble weights for three sub-models
_SURVIVAL_WEIGHT = 0.40
_HAZARD_WEIGHT = 0.35
_VOLATILITY_WEIGHT = 0.25

# League-level baseline decay profiles (median half-life in seconds)
LEAGUE_DECAY_PROFILES: dict[str, float] = {
    "MLB": 1200.0,
    "NPB": 2400.0,
    "KBO": 2100.0,
    "WBC": 900.0,       # international = faster information flow
    "NFL": 600.0,
    "NBA": 480.0,
    "DEFAULT": 1500.0,
}

# Decay curve resolution (number of time-steps)
DECAY_CURVE_STEPS = 20


# ═══════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════

@dataclass
class EdgeDecayInput:
    """All features required for decay prediction."""
    # ── Market microstructure ──────────────────────────────────
    odds_velocity: float = 0.0            # implied-prob change / minute
    odds_acceleration: float = 0.0        # second derivative of odds movement
    liquidity_score: float = 0.5          # 0-1 market depth proxy
    book_count: int = 3                   # number of active sportsbooks
    spread_width: float = 0.04            # cross-book odds spread %

    # ── Model agreement ───────────────────────────────────────
    ensemble_stddev: float = 0.02         # σ of sub-model probabilities
    ensemble_mean_drift: float = 0.0      # change in mean prob over last N snapshots
    prediction_momentum: float = 0.0      # direction & magnitude of prob trend

    # ── Market signals ────────────────────────────────────────
    sharp_money_pct: float = 0.0          # estimated % of handle from sharps
    reverse_line_moves: int = 0
    steam_moves: int = 0
    time_to_game_seconds: float = 86400.0 # seconds until first pitch

    # ── Historical memory ─────────────────────────────────────
    past_similar_edges: int = 0           # count of past similar edge occurrences
    historical_decay_times: list[float] | None = None  # past half-lives (sec)
    league: str = "WBC"                   # league for baseline profile

    # ── Current edge magnitude ────────────────────────────────
    edge_pct: float = 0.0                 # raw model edge %
    edge_score: float = 0.0               # composite score from edge_validator

    # ── Reproducibility ───────────────────────────────────────
    seed: int | None = None


@dataclass
class EdgeDecayForecast:
    """Predicted edge decay timeline."""
    half_life_seconds: float = 0.0
    decay_curve: list[float] = field(default_factory=list)   # len=DECAY_CURVE_STEPS, 1→0
    confidence_score: float = 0.0       # 0-100
    urgency_level: UrgencyLevel = UrgencyLevel.MONITOR

    # Confidence bounds
    lower_bound_seconds: float = 0.0
    upper_bound_seconds: float = 0.0

    # Sub-model outputs (transparency)
    survival_half_life: float = 0.0
    hazard_half_life: float = 0.0
    volatility_half_life: float = 0.0

    # Diagnostics
    details: dict[str, str] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
# SUB-MODEL 1: SURVIVAL REGRESSION
# ═══════════════════════════════════════════════════════════════

def _survival_regression(inp: EdgeDecayInput, rng: random.Random) -> float:
    """
    Accelerated failure time (AFT) inspired survival model.

    Models edge lifetime as a log-normal process:
        ln(T) = β₀ + β·X + σ·ε

    Higher market pressure → shorter survival time.
    """
    baseline = math.log(max(LEAGUE_DECAY_PROFILES.get(inp.league,
                        LEAGUE_DECAY_PROFILES["DEFAULT"]), 60.0))

    # Covariates (negative = shorten life)
    velocity_effect = -12.0 * abs(inp.odds_velocity)
    accel_effect = -8.0 * abs(inp.odds_acceleration)
    liquidity_effect = -1.5 * inp.liquidity_score   # liquid = faster absorption
    books_effect = -0.08 * max(inp.book_count - 1, 0)
    spread_effect = 2.0 * inp.spread_width          # wide spread = slower
    sharp_effect = -3.0 * inp.sharp_money_pct
    steam_effect = -0.5 * inp.steam_moves
    rlm_effect = -0.3 * inp.reverse_line_moves

    # Time-to-game: closer = faster decay
    ttg_hours = inp.time_to_game_seconds / 3600.0
    ttg_effect = 0.4 * math.log1p(ttg_hours)        # more time = longer life

    # Model disagreement lengthens survival (market confused → slow convergence)
    disagreement_effect = 5.0 * inp.ensemble_stddev

    # Historical memory
    if inp.historical_decay_times and len(inp.historical_decay_times) >= 3:
        hist_median = statistics.median(inp.historical_decay_times)
        hist_effect = 0.3 * (math.log(max(hist_median, 60.0)) - baseline)
    else:
        hist_effect = 0.0

    log_t = (
        baseline
        + velocity_effect
        + accel_effect
        + liquidity_effect
        + books_effect
        + spread_effect
        + sharp_effect
        + steam_effect
        + rlm_effect
        + ttg_effect
        + disagreement_effect
        + hist_effect
    )

    # Add noise (σ·ε)
    noise = rng.gauss(0, 0.15)
    log_t += noise

    return max(math.exp(log_t), 30.0)   # floor at 30 seconds


# ═══════════════════════════════════════════════════════════════
# SUB-MODEL 2: HAZARD FUNCTION
# ═══════════════════════════════════════════════════════════════

def _hazard_function(inp: EdgeDecayInput, rng: random.Random) -> float:
    """
    Weibull proportional hazard model.

    h(t|X) = λ · k · (λt)^{k-1} · exp(β·X)

    Derives half-life from baseline hazard scaled by covariates.
    """
    # Weibull shape: k > 1 ⇒ increasing hazard (edge degrades faster over time)
    k = 1.4

    # Baseline scale (λ) from league profile
    baseline_hl = LEAGUE_DECAY_PROFILES.get(inp.league,
                                             LEAGUE_DECAY_PROFILES["DEFAULT"])
    lam = math.log(2.0) ** (1.0 / k) / max(baseline_hl, 60.0)

    # Covariate-adjusted hazard ratio
    risk_score = 0.0
    risk_score += 10.0 * abs(inp.odds_velocity)
    risk_score += 6.0 * abs(inp.odds_acceleration)
    risk_score += 1.0 * inp.liquidity_score
    risk_score += 0.15 * max(inp.book_count - 1, 0)
    risk_score += 2.5 * inp.sharp_money_pct
    risk_score += 0.4 * inp.steam_moves
    risk_score += 0.25 * inp.reverse_line_moves

    # Protective factors
    risk_score -= 3.0 * inp.ensemble_stddev
    risk_score -= 1.5 * inp.spread_width

    # Clamp risk score to prevent extreme values
    risk_score = max(min(risk_score, 5.0), -3.0)

    hazard_ratio = math.exp(risk_score)

    adjusted_lam = lam * hazard_ratio

    # Half-life from Weibull: t_{0.5} = (ln2 / λ^k)^{1/k}
    # But with adjusted λ:
    if adjusted_lam > 0:
        half_life = (math.log(2.0) / (adjusted_lam ** k)) ** (1.0 / k)
    else:
        half_life = baseline_hl

    # Small noise
    half_life *= math.exp(rng.gauss(0, 0.10))

    return max(half_life, 30.0)


# ═══════════════════════════════════════════════════════════════
# SUB-MODEL 3: TIME-SERIES VOLATILITY MODEL
# ═══════════════════════════════════════════════════════════════

def _volatility_model(inp: EdgeDecayInput, rng: random.Random) -> float:
    """
    GARCH-inspired volatility model.

    Estimates odds volatility regime; high vol → shorter edge life
    because the market is actively re-pricing.
    """
    baseline_hl = LEAGUE_DECAY_PROFILES.get(inp.league,
                                             LEAGUE_DECAY_PROFILES["DEFAULT"])

    # Estimate current odds volatility (σ²)
    vol_components = [
        abs(inp.odds_velocity) * 60.0,       # normalise to per-hour
        abs(inp.odds_acceleration) * 3600.0,  # normalise to per-hour²
        inp.spread_width * 5.0,               # spread is a vol proxy
    ]
    sigma_sq = sum(vol_components) / max(len(vol_components), 1)

    # Vol regime multiplier
    if sigma_sq > 0.3:
        vol_mult = 0.30   # extreme vol → very short life
    elif sigma_sq > 0.15:
        vol_mult = 0.55
    elif sigma_sq > 0.05:
        vol_mult = 0.80
    else:
        vol_mult = 1.20   # quiet market → longer life

    # Adjust for momentum (strong momentum = edge moving away)
    momentum_adj = 1.0 - 2.0 * abs(inp.prediction_momentum)
    momentum_adj = max(momentum_adj, 0.3)

    # Adjust for sharp activity (sharps cause vol)
    sharp_adj = 1.0 - 0.5 * inp.sharp_money_pct
    sharp_adj = max(sharp_adj, 0.4)

    half_life = baseline_hl * vol_mult * momentum_adj * sharp_adj

    # Time-to-game scaling
    ttg_ratio = inp.time_to_game_seconds / 86400.0
    if ttg_ratio < 0.05:     # < ~1.2 hours
        half_life *= 0.4     # very close to game = volatile
    elif ttg_ratio < 0.25:   # < ~6 hours
        half_life *= 0.7

    # Noise
    half_life *= math.exp(rng.gauss(0, 0.12))

    return max(half_life, 30.0)


# ═══════════════════════════════════════════════════════════════
# ENSEMBLE & CONFIDENCE
# ═══════════════════════════════════════════════════════════════

def _compute_confidence(
    survival_hl: float,
    hazard_hl: float,
    volatility_hl: float,
    inp: EdgeDecayInput,
) -> float:
    """
    Confidence in the half-life estimate (0-100).

    High confidence when:
      - sub-models agree
      - historical data available
      - market signals are clear
    """
    hls = [survival_hl, hazard_hl, volatility_hl]
    mean_hl = statistics.mean(hls)
    stddev_hl = statistics.stdev(hls) if len(hls) > 1 else mean_hl * 0.5

    # Agreement score (0-40): low cv = high agreement
    cv = stddev_hl / max(mean_hl, 1.0)
    agreement = max(0.0, 40.0 * (1.0 - min(cv, 1.0)))

    # Data richness (0-25)
    data_score = 0.0
    if inp.historical_decay_times:
        n = len(inp.historical_decay_times)
        data_score += min(n / 10.0, 1.0) * 15.0
    if inp.past_similar_edges > 0:
        data_score += min(inp.past_similar_edges / 5.0, 1.0) * 10.0
    data_score = min(data_score, 25.0)

    # Signal clarity (0-20): strong directional signals = clear
    signal_score = 0.0
    if abs(inp.odds_velocity) > 0.01:
        signal_score += 5.0
    if inp.steam_moves > 0:
        signal_score += 5.0
    if inp.sharp_money_pct > 0.15:
        signal_score += 5.0
    if inp.book_count >= 3:
        signal_score += 5.0
    signal_score = min(signal_score, 20.0)

    # Time-to-game stability (0-15): predictions are more reliable far from game
    ttg_hours = inp.time_to_game_seconds / 3600.0
    if ttg_hours > 12:
        ttg_score = 15.0
    elif ttg_hours > 4:
        ttg_score = 10.0
    elif ttg_hours > 1:
        ttg_score = 5.0
    else:
        ttg_score = 2.0

    return min(agreement + data_score + signal_score + ttg_score, 100.0)


def _classify_urgency(half_life: float) -> UrgencyLevel:
    """Map half-life (seconds) → UrgencyLevel."""
    for threshold, level in _URGENCY_THRESHOLDS:
        if half_life < threshold:
            return level
    return UrgencyLevel.EXPIRED


def _build_decay_curve(half_life: float, steps: int = DECAY_CURVE_STEPS) -> list[float]:
    """
    Build an exponential decay curve from 1.0 → ~0.
    Each step covers (3 * half_life / steps) seconds.
    curve[i] = fraction of edge remaining at step i.
    """
    curve: list[float] = []
    total_time = 3.0 * half_life   # cover ~3 half-lives (87.5 % decay)
    dt = total_time / max(steps, 1)
    decay_rate = math.log(2.0) / max(half_life, 1.0)
    for i in range(steps):
        t = dt * (i + 1)
        remaining = math.exp(-decay_rate * t)
        curve.append(round(remaining, 4))
    return curve


# ═══════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════

def predict_edge_decay(inp: EdgeDecayInput) -> EdgeDecayForecast:
    """
    Predict how long the current edge will remain exploitable.

    Args:
        inp: EdgeDecayInput with all market & model features.

    Returns:
        EdgeDecayForecast with half-life, decay curve, confidence,
        urgency level, and confidence bounds.
    """
    rng = random.Random(inp.seed) if inp.seed is not None else random.Random()

    # ── Run three sub-models ──────────────────────────────────
    survival_hl = _survival_regression(inp, rng)
    hazard_hl = _hazard_function(inp, rng)
    volatility_hl = _volatility_model(inp, rng)

    # ── Weighted ensemble ─────────────────────────────────────
    half_life = (
        _SURVIVAL_WEIGHT * survival_hl
        + _HAZARD_WEIGHT * hazard_hl
        + _VOLATILITY_WEIGHT * volatility_hl
    )

    # ── Confidence bounds (empirical ±1σ from sub-model spread) ──
    hls = [survival_hl, hazard_hl, volatility_hl]
    std = statistics.stdev(hls) if len(hls) > 1 else half_life * 0.3
    lower = max(half_life - 1.5 * std, 30.0)
    upper = half_life + 1.5 * std

    # ── Confidence score ──────────────────────────────────────
    confidence = _compute_confidence(survival_hl, hazard_hl, volatility_hl, inp)

    # ── Urgency ───────────────────────────────────────────────
    urgency = _classify_urgency(half_life)

    # ── Decay curve ───────────────────────────────────────────
    curve = _build_decay_curve(half_life)

    # ── Build forecast ────────────────────────────────────────
    forecast = EdgeDecayForecast(
        half_life_seconds=round(half_life, 1),
        decay_curve=curve,
        confidence_score=round(confidence, 1),
        urgency_level=urgency,
        lower_bound_seconds=round(lower, 1),
        upper_bound_seconds=round(upper, 1),
        survival_half_life=round(survival_hl, 1),
        hazard_half_life=round(hazard_hl, 1),
        volatility_half_life=round(volatility_hl, 1),
        details={
            "survival_hl": f"{survival_hl:.0f}s",
            "hazard_hl": f"{hazard_hl:.0f}s",
            "volatility_hl": f"{volatility_hl:.0f}s",
            "ensemble_hl": f"{half_life:.0f}s",
            "confidence_bounds": f"[{lower:.0f}s, {upper:.0f}s]",
            "league_baseline": f"{LEAGUE_DECAY_PROFILES.get(inp.league, 1500):.0f}s",
            "urgency": urgency.value,
        },
    )
    return forecast
