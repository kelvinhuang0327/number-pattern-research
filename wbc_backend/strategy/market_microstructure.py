"""
Market Microstructure Analysis Engine
=====================================
Institution-grade module for detecting:
  1. Line Movement Velocity (LMV) — rate of odds change over time
  2. Liquidity Estimation — proxy via odds spread & movement frequency
  3. Sharp Money Detection — reverse-engineer informed bettor flow
  4. Bookmaker Bias Model — systematic pricing inefficiencies per book

This module treats the betting market as a financial microstructure
problem, applying concepts from market-making theory to sports betting.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from wbc_backend.domain.schemas import OddsLine, OddsTimeSeries


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class LineMovement:
    """A single observed line change."""
    market: str
    side: str
    old_odds: float
    new_odds: float
    timestamp: float
    elapsed_sec: float  # seconds since prior snapshot
    velocity: float     # implied-prob change per minute
    magnitude: float    # absolute implied-prob shift


@dataclass
class LiquidityEstimate:
    """Proxy liquidity score for a market."""
    market: str
    spread_pct: float          # (worst_odds − best_odds) / midpoint
    movement_frequency: float  # movements per hour
    depth_score: float         # 0-1 (1 = deepest / most liquid)
    classification: str        # "DEEP" | "MODERATE" | "THIN"


@dataclass
class SharpSignal:
    """An identified sharp-money event."""
    market: str
    side: str
    signal_type: str       # "STEAM" | "REVERSE" | "WHALE" | "SYNDICATE"
    confidence: float      # 0-1
    velocity: float        # implied-prob change per minute at detection
    implied_prob_shift: float
    description: str
    severity: int          # 1-5


@dataclass
class BookmakerBias:
    """Systematic pricing bias for a specific bookmaker."""
    book: str
    market: str
    direction: str         # "FAV_INFLATE" | "DOG_INFLATE" | "NEUTRAL"
    bias_magnitude: float  # average excess margin on one side
    sample_size: int
    description: str


@dataclass
class MicrostructureReport:
    """Complete microstructure analysis for a game."""
    line_movements: list[LineMovement] = field(default_factory=list)
    liquidity: list[LiquidityEstimate] = field(default_factory=list)
    sharp_signals: list[SharpSignal] = field(default_factory=list)
    book_biases: list[BookmakerBias] = field(default_factory=list)
    overall_market_efficiency: float = 0.0   # 0-1 (1 = perfectly efficient)
    recommended_timing: str = "IMMEDIATE"    # or "WAIT" or "FADE"
    summary: str = ""


# ─── Constants ────────────────────────────────────────────────────────────────

STEAM_VELOCITY_THRESHOLD = 0.003   # 0.3% implied-prob shift per minute → steam
REVERSE_LINE_THRESHOLD = 0.02     # 2% reversal after steam → reverse signal
WHALE_MAGNITUDE_THRESHOLD = 0.05  # 5%+ single-tick move → whale
SYNDICATE_PATTERN_WINDOW = 5      # coordinated moves within 5 minutes

VIG_ESTIMATES = {
    "Pinnacle": 0.025,
    "TSL":      0.08,
    "Bet365":   0.06,
    "default":  0.05,
}


# ─── Line Movement Velocity ──────────────────────────────────────────────────

def compute_line_movements(time_series: list[OddsTimeSeries]) -> list[LineMovement]:
    """
    Compute the velocity and magnitude of line movements from snapshots.

    Parameters
    ----------
    time_series : list of OddsTimeSeries
        Each OddsTimeSeries has .snapshots = [(timestamp, odds_value), ...]

    Returns
    -------
    list of LineMovement
    """
    movements: list[LineMovement] = []

    for ts in time_series:
        if not hasattr(ts, "snapshots") or len(getattr(ts, "snapshots", [])) < 2:
            continue

        snaps = sorted(ts.snapshots, key=lambda s: s[0])
        for i in range(1, len(snaps)):
            t_prev, odds_prev = snaps[i - 1]
            t_curr, odds_curr = snaps[i]

            elapsed = max(t_curr - t_prev, 1)  # avoid division by zero
            elapsed_min = elapsed / 60.0

            ip_prev = 1.0 / max(odds_prev, 1.01)
            ip_curr = 1.0 / max(odds_curr, 1.01)

            delta = ip_curr - ip_prev
            magnitude = abs(delta)
            velocity = magnitude / max(elapsed_min, 0.01)

            if magnitude > 0.001:  # filter noise
                movements.append(LineMovement(
                    market=getattr(ts, "market", "ML"),
                    side=getattr(ts, "side", ""),
                    old_odds=odds_prev,
                    new_odds=odds_curr,
                    timestamp=t_curr,
                    elapsed_sec=elapsed,
                    velocity=velocity,
                    magnitude=magnitude,
                ))

    return sorted(movements, key=lambda m: -m.velocity)


# ─── Liquidity Estimation ────────────────────────────────────────────────────

def estimate_liquidity(
    odds_lines: list[OddsLine],
    movements: list[LineMovement],
    window_hours: float = 2.0,
) -> list[LiquidityEstimate]:
    """
    Estimate market liquidity per market type using spread & movement freq.

    Wider spreads → thinner markets.
    More movements → more price discovery → potentially deeper.
    """
    by_market: dict[str, list[OddsLine]] = {}
    for ol in odds_lines:
        mkey = getattr(ol, "market", "ML")
        by_market.setdefault(mkey, []).append(ol)

    estimates = []
    for market, lines in by_market.items():
        odds_vals = [getattr(ol, "decimal_odds", 1.9) for ol in lines]
        if len(odds_vals) < 2:
            estimates.append(LiquidityEstimate(
                market=market, spread_pct=1.0, movement_frequency=0.0,
                depth_score=0.2, classification="THIN",
            ))
            continue

        best = min(odds_vals)
        worst = max(odds_vals)
        midpoint = (best + worst) / 2.0
        spread_pct = (worst - best) / max(midpoint, 1.0)

        # Movement frequency
        market_moves = [m for m in movements if m.market == market]
        freq = len(market_moves) / max(window_hours, 0.1)

        # Composite depth score:  narrower spread + moderate freq → deeper
        spread_score = max(0, 1.0 - spread_pct * 5)  # 20% spread → 0
        freq_score = min(1.0, freq / 10.0)           # 10+ moves/hr → max
        depth = 0.6 * spread_score + 0.4 * freq_score

        if depth >= 0.7:
            cls = "DEEP"
        elif depth >= 0.4:
            cls = "MODERATE"
        else:
            cls = "THIN"

        estimates.append(LiquidityEstimate(
            market=market,
            spread_pct=round(spread_pct, 4),
            movement_frequency=round(freq, 2),
            depth_score=round(depth, 3),
            classification=cls,
        ))

    return estimates


# ─── Sharp Money Detection ───────────────────────────────────────────────────

def detect_sharp_money(  # noqa: C901
    movements: list[LineMovement],
    odds_lines: list[OddsLine],
) -> list[SharpSignal]:
    """
    Identify sharp-money patterns from line movement data.

    Patterns detected:
      STEAM    — rapid same-direction moves across multiple books
      REVERSE  — line moves back after initial steam (trap indicator)
      WHALE    — single large move (5%+ implied-prob)
      SYNDICATE — coordinated small moves within tight time window
    """
    signals: list[SharpSignal] = []

    # ── WHALE detection ──
    for mv in movements:
        if mv.magnitude >= WHALE_MAGNITUDE_THRESHOLD:
            direction = "toward" if mv.new_odds < mv.old_odds else "away from"
            signals.append(SharpSignal(
                market=mv.market,
                side=mv.side,
                signal_type="WHALE",
                confidence=min(0.95, mv.magnitude / 0.08),
                velocity=mv.velocity,
                implied_prob_shift=mv.magnitude,
                description=f"Large single-tick move: {mv.old_odds:.2f}→{mv.new_odds:.2f} "
                            f"({direction} side), {mv.magnitude:.1%} implied shift",
                severity=4 if mv.magnitude > 0.08 else 3,
            ))

    # ── STEAM detection ──
    for mv in movements:
        if mv.velocity >= STEAM_VELOCITY_THRESHOLD and mv.magnitude >= 0.015:
            signals.append(SharpSignal(
                market=mv.market,
                side=mv.side,
                signal_type="STEAM",
                confidence=min(0.90, mv.velocity / 0.01),
                velocity=mv.velocity,
                implied_prob_shift=mv.magnitude,
                description=f"Steam move: {mv.velocity:.4f}/min velocity, "
                            f"{mv.magnitude:.1%} shift in {mv.elapsed_sec:.0f}s",
                severity=3,
            ))

    # ── REVERSE detection ──
    steam_markets = {s.market for s in signals if s.signal_type == "STEAM"}
    for market in steam_markets:
        market_moves = [m for m in movements if m.market == market]
        if len(market_moves) >= 2:
            last = market_moves[-1]
            prev = market_moves[-2]
            # Check if last move reversed previous direction
            ip_last_delta = (1.0 / max(last.new_odds, 1.01)) - (1.0 / max(last.old_odds, 1.01))
            ip_prev_delta = (1.0 / max(prev.new_odds, 1.01)) - (1.0 / max(prev.old_odds, 1.01))
            if ip_last_delta * ip_prev_delta < 0 and abs(ip_last_delta) >= REVERSE_LINE_THRESHOLD:
                signals.append(SharpSignal(
                    market=market,
                    side=last.side,
                    signal_type="REVERSE",
                    confidence=0.75,
                    velocity=last.velocity,
                    implied_prob_shift=abs(ip_last_delta),
                    description=f"Reverse line: steam then pullback ({abs(ip_last_delta):.1%}). "
                                f"Possible trap line.",
                    severity=4,
                ))

    # ── SYNDICATE detection ──
    for i, m1 in enumerate(movements):
        cluster = [m1]
        for m2 in movements[i + 1:]:
            if abs(m2.timestamp - m1.timestamp) <= SYNDICATE_PATTERN_WINDOW * 60 and m2.market == m1.market:
                    cluster.append(m2)
        if len(cluster) >= 3:
            total_shift = sum(m.magnitude for m in cluster)
            if total_shift >= 0.03:
                signals.append(SharpSignal(
                    market=m1.market,
                    side=m1.side,
                    signal_type="SYNDICATE",
                    confidence=min(0.85, len(cluster) / 5.0),
                    velocity=max(m.velocity for m in cluster),
                    implied_prob_shift=total_shift,
                    description=f"Syndicate pattern: {len(cluster)} coordinated moves "
                                f"within {SYNDICATE_PATTERN_WINDOW}min, total shift {total_shift:.1%}",
                    severity=5,
                ))

    return sorted(signals, key=lambda s: (-s.severity, -s.confidence))


# ─── Bookmaker Bias Model ────────────────────────────────────────────────────

def analyze_bookmaker_bias(
    odds_lines: list[OddsLine],
    fair_prob_home: float,
) -> list[BookmakerBias]:
    """
    Detect systematic pricing biases per bookmaker.

    Compares each book's implied probability (vig-removed) against
    the model's fair probability to find consistent over/under-pricing.
    """
    biases: list[BookmakerBias] = []

    by_book: dict[str, list[OddsLine]] = {}
    for ol in odds_lines:
        book = getattr(ol, "sportsbook", getattr(ol, "book", "unknown"))
        by_book.setdefault(book, []).append(ol)

    for book, lines in by_book.items():
        ml_lines = [ln for ln in lines if getattr(ln, "market", "") == "ML"]

        if len(ml_lines) < 2:
            continue

        # Get home and away implied
        home_odds = [getattr(ln, "decimal_odds", 1.9) for ln in ml_lines
                     if "home" in getattr(ln, "side", "").lower()]
        away_odds = [getattr(ln, "decimal_odds", 2.0) for ln in ml_lines
                     if "away" in getattr(ln, "side", "").lower()]

        if not home_odds or not away_odds:
            continue

        ip_home = 1.0 / home_odds[0]
        ip_away = 1.0 / away_odds[0]
        total_ip = ip_home + ip_away
        # Remove vig proportionally
        fair_home_book = ip_home / total_ip

        # Compare against model
        model_home = fair_prob_home
        bias = fair_home_book - model_home

        if abs(bias) < 0.01:
            direction = "NEUTRAL"
            desc = f"{book}: pricing aligned with model (±{abs(bias):.1%})"
        elif bias > 0:
            direction = "FAV_INFLATE"
            desc = f"{book}: inflates favourite implied prob by {bias:.1%} (value on dog)"
        else:
            direction = "DOG_INFLATE"
            desc = f"{book}: inflates underdog implied prob by {abs(bias):.1%} (value on fav)"

        biases.append(BookmakerBias(
            book=book,
            market="ML",
            direction=direction,
            bias_magnitude=round(abs(bias), 4),
            sample_size=len(ml_lines),
            description=desc,
        ))

    return sorted(biases, key=lambda b: -b.bias_magnitude)


# ─── Market Efficiency Score ─────────────────────────────────────────────────

def compute_market_efficiency(
    liquidity: list[LiquidityEstimate],
    sharp_signals: list[SharpSignal],
    book_biases: list[BookmakerBias],
) -> float:
    """
    Composite market efficiency score 0–1.

    Efficient markets have: deep liquidity, few sharp signals, low bias.
    """
    # Liquidity component (≈40%)
    if liquidity:
        avg_depth = sum(le.depth_score for le in liquidity) / len(liquidity)
    else:
        avg_depth = 0.5

    # Sharp signal component (≈30%) — more signals = less efficient
    sharp_count = len(sharp_signals)
    sharp_penalty = min(1.0, sharp_count * 0.15)

    # Bias component (≈30%) — higher bias = less efficient
    if book_biases:
        max_bias = max(b.bias_magnitude for b in book_biases)
    else:
        max_bias = 0.0
    bias_penalty = min(1.0, max_bias * 5)  # 20% bias → penalty 1.0

    efficiency = 0.40 * avg_depth + 0.30 * (1.0 - sharp_penalty) + 0.30 * (1.0 - bias_penalty)
    return round(max(0.0, min(1.0, efficiency)), 3)


# ─── Timing Recommendation ──────────────────────────────────────────────────

def recommend_timing(
    sharp_signals: list[SharpSignal],
    efficiency: float,
) -> str:
    """
    Recommend bet placement timing based on market state.

    IMMEDIATE — market is efficiently priced, no expected further movement
    WAIT      — steam detected, wait for line to settle
    FADE      — reverse/trap detected, fade the movement direction
    """
    has_steam = any(s.signal_type == "STEAM" for s in sharp_signals)
    has_reverse = any(s.signal_type == "REVERSE" for s in sharp_signals)
    has_syndicate = any(s.signal_type == "SYNDICATE" for s in sharp_signals)

    if has_reverse:
        return "FADE"
    if has_syndicate or (has_steam and efficiency < 0.5):
        return "WAIT"
    return "IMMEDIATE"


# ─── Full Analysis Entrypoint ────────────────────────────────────────────────

def analyze_microstructure(
    odds_lines: list[OddsLine],
    time_series: list[OddsTimeSeries] | None = None,
    model_home_prob: float = 0.5,
) -> MicrostructureReport:
    """
    Run full microstructure analysis pipeline.

    Parameters
    ----------
    odds_lines : current odds snapshot
    time_series : historical odds snapshots (if available)
    model_home_prob : model's fair home win probability

    Returns
    -------
    MicrostructureReport with all sub-analyses
    """
    # 1. Line movements
    movements = compute_line_movements(time_series or [])

    # 2. Liquidity
    liquidity = estimate_liquidity(odds_lines, movements)

    # 3. Sharp money
    sharp = detect_sharp_money(movements, odds_lines)

    # 4. Bookmaker bias
    biases = analyze_bookmaker_bias(odds_lines, model_home_prob)

    # 5. Efficiency
    efficiency = compute_market_efficiency(liquidity, sharp, biases)

    # 6. Timing
    timing = recommend_timing(sharp, efficiency)

    # 7. Summary
    parts = []
    if sharp:
        top = sharp[0]
        parts.append(f"Top signal: {top.signal_type} ({top.confidence:.0%} conf)")
    if biases:
        top_bias = biases[0]
        parts.append(f"Bias: {top_bias.book} {top_bias.direction} ({top_bias.bias_magnitude:.1%})")
    parts.append(f"Efficiency: {efficiency:.0%}")
    parts.append(f"Timing: {timing}")

    return MicrostructureReport(
        line_movements=movements,
        liquidity=liquidity,
        sharp_signals=sharp,
        book_biases=biases,
        overall_market_efficiency=efficiency,
        recommended_timing=timing,
        summary=" | ".join(parts),
    )
