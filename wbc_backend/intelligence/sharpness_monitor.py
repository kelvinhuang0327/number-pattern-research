"""
Phase 6 — Sharpness Monitor
===============================
Tracks whether the model is ahead of or behind the market.

Core metrics:
  1. Closing Line Value (CLV)     — did we beat the closing line?
  2. Odds Movement Alignment      — does line movement agree with our prediction?
  3. Prediction Decay Rate         — how quickly does our edge erode?
  4. Sharp Money Co-movement       — are we on the same side as sharps?

If the market has adapted (CLV turning negative over time):
  → Lower bet frequency (raise edge threshold)
  → Flag for meta-learning retrain

This is the "canary in the coal mine" — if CLV is consistently negative,
our model is stale.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum


# ─── Configuration ──────────────────────────────────────────────────────────

SHARPNESS_CONFIG = {
    "clv_window": 50,                  # trailing games for CLV
    "clv_alarm_threshold": -0.015,     # negative CLV below this → alarm
    "decay_lookback_hours": [1, 3, 6, 12, 24],  # hours before game
    "alignment_window": 30,            # games for movement alignment
    "min_clv_samples": 10,             # minimum samples for CLV calculation
    "edge_raise_pct": 0.10,            # raise edge threshold by 10% on alarm
    "auto_pause_clv": -0.03,           # auto-pause betting below this CLV
}


# ─── Data Structures ────────────────────────────────────────────────────────

class SharpnessLevel(Enum):
    AHEAD_OF_MARKET = "AHEAD_OF_MARKET"    # CLV positive, we're sharp
    EVEN_WITH_MARKET = "EVEN_WITH_MARKET"  # CLV ~0, marginal
    BEHIND_MARKET = "BEHIND_MARKET"        # CLV negative, market adapted
    CRITICALLY_STALE = "CRITICALLY_STALE"  # persistent negative CLV


@dataclass
class CLVEntry:
    """Single closing-line-value observation."""
    game_id: str = ""
    timestamp: float = 0.0

    # Our bet details
    bet_odds: float = 2.0
    bet_implied_prob: float = 0.50

    # Closing line
    closing_odds: float = 2.0
    closing_implied_prob: float = 0.50

    # CLV = our_implied - closing_implied (positive = we beat closing)
    clv: float = 0.0

    # How far before game did we bet?
    hours_before_close: float = 24.0

    # Line movement info
    opening_odds: float = 2.0
    movement_direction: str = ""      # TOWARD_US / AWAY_FROM_US / NEUTRAL
    our_prediction_side: str = ""     # HOME / AWAY


@dataclass
class DecayPoint:
    """Edge at a specific time before game."""
    hours_before: float = 24.0
    edge_pct: float = 0.05
    implied_prob: float = 0.50


@dataclass
class SharpnessReport:
    """Complete sharpness assessment."""
    level: SharpnessLevel = SharpnessLevel.EVEN_WITH_MARKET

    # CLV metrics
    trailing_clv: float = 0.0          # mean CLV over window
    clv_trend: str = "STABLE"          # IMPROVING / STABLE / DECLINING
    clv_std: float = 0.0
    clv_positive_rate: float = 0.50    # % of bets with positive CLV
    clv_samples: int = 0

    # Movement alignment
    movement_alignment_rate: float = 0.50  # % of games where movement agreed
    sharp_co_movement: float = 0.50        # % aligned with sharp money

    # Prediction decay
    decay_curve: list[DecayPoint] = field(default_factory=list)
    half_life_hours: float = 12.0      # hours until edge halves

    # Actions
    should_pause: bool = False
    edge_threshold_adjustment: float = 0.0  # add this to edge threshold
    frequency_adjustment: float = 1.0       # multiply bet frequency by this
    alert_message: str = ""
    recommendations: list[str] = field(default_factory=list)


# ─── CLV Tracking ──────────────────────────────────────────────────────────

class SharpnessMonitor:
    """Stateful monitor that accumulates CLV data and provides assessments."""

    def __init__(self):
        self.clv_history: list[CLVEntry] = []
        self.movement_history: list[dict] = []
        self.decay_snapshots: dict[str, list[DecayPoint]] = {}
        self._last_report: SharpnessReport | None = None

    def record_clv(
        self,
        game_id: str,
        bet_odds: float,
        closing_odds: float,
        opening_odds: float = 0.0,
        our_side: str = "",
        hours_before_close: float = 24.0,
    ) -> CLVEntry:
        """Record a CLV observation after a game's line closes."""
        bet_implied = 1.0 / bet_odds if bet_odds > 1 else 0.99
        close_implied = 1.0 / closing_odds if closing_odds > 1 else 0.99

        clv = bet_implied - close_implied  # positive = we beat closing

        # Movement direction
        if opening_odds > 0:
            open_implied = 1.0 / opening_odds if opening_odds > 1 else 0.99
            shift = close_implied - open_implied
            if our_side in ("HOME", "OVER"):
                direction = "TOWARD_US" if shift > 0.01 else (
                    "AWAY_FROM_US" if shift < -0.01 else "NEUTRAL"
                )
            else:
                direction = "TOWARD_US" if shift < -0.01 else (
                    "AWAY_FROM_US" if shift > 0.01 else "NEUTRAL"
                )
        else:
            direction = "NEUTRAL"

        entry = CLVEntry(
            game_id=game_id,
            timestamp=time.time(),
            bet_odds=bet_odds,
            bet_implied_prob=round(bet_implied, 4),
            closing_odds=closing_odds,
            closing_implied_prob=round(close_implied, 4),
            clv=round(clv, 4),
            hours_before_close=hours_before_close,
            opening_odds=opening_odds,
            movement_direction=direction,
            our_prediction_side=our_side,
        )

        self.clv_history.append(entry)

        # Keep buffer manageable
        max_history = SHARPNESS_CONFIG["clv_window"] * 3
        if len(self.clv_history) > max_history:
            self.clv_history = self.clv_history[-max_history:]

        return entry

    def record_decay_snapshot(
        self,
        game_id: str,
        hours_before: float,
        current_odds: float,
        our_model_prob: float,
    ) -> None:
        """Record edge decay at a point in time before game start."""
        implied = 1.0 / current_odds if current_odds > 1 else 0.99
        edge = our_model_prob - implied

        point = DecayPoint(
            hours_before=hours_before,
            edge_pct=round(edge, 4),
            implied_prob=round(implied, 4),
        )

        if game_id not in self.decay_snapshots:
            self.decay_snapshots[game_id] = []
        self.decay_snapshots[game_id].append(point)

    def assess(self) -> SharpnessReport:
        """Generate a full sharpness assessment."""
        report = SharpnessReport()
        window = SHARPNESS_CONFIG["clv_window"]
        min_samples = SHARPNESS_CONFIG["min_clv_samples"]

        recent = self.clv_history[-window:]
        report.clv_samples = len(recent)

        if len(recent) < min_samples:
            report.level = SharpnessLevel.EVEN_WITH_MARKET
            report.alert_message = f"Insufficient CLV data ({len(recent)} < {min_samples})"
            self._last_report = report
            return report

        # ── CLV stats ──
        clvs = [e.clv for e in recent]
        report.trailing_clv = sum(clvs) / len(clvs)
        report.clv_positive_rate = sum(1 for c in clvs if c > 0) / len(clvs)

        mean_clv = report.trailing_clv
        var = sum((c - mean_clv) ** 2 for c in clvs) / len(clvs)
        report.clv_std = math.sqrt(var) if var > 0 else 0.0

        # CLV trend: compare first half vs second half
        mid = len(clvs) // 2
        first_half = sum(clvs[:mid]) / max(mid, 1)
        second_half = sum(clvs[mid:]) / max(len(clvs) - mid, 1)
        if second_half > first_half + 0.005:
            report.clv_trend = "IMPROVING"
        elif second_half < first_half - 0.005:
            report.clv_trend = "DECLINING"
        else:
            report.clv_trend = "STABLE"

        # ── Movement alignment ──
        toward = sum(1 for e in recent if e.movement_direction == "TOWARD_US")
        report.movement_alignment_rate = toward / len(recent) if recent else 0.5

        # ── Decay curve (aggregate across games) ──
        report.decay_curve = self._compute_aggregate_decay()
        report.half_life_hours = self._estimate_half_life(report.decay_curve)

        # ── Sharpness level classification ──
        alarm = SHARPNESS_CONFIG["clv_alarm_threshold"]
        auto_pause = SHARPNESS_CONFIG["auto_pause_clv"]

        if report.trailing_clv > 0.01:
            report.level = SharpnessLevel.AHEAD_OF_MARKET
        elif report.trailing_clv > alarm:
            report.level = SharpnessLevel.EVEN_WITH_MARKET
        elif report.trailing_clv > auto_pause:
            report.level = SharpnessLevel.BEHIND_MARKET
        else:
            report.level = SharpnessLevel.CRITICALLY_STALE

        # ── Actions & recommendations ──
        if report.level == SharpnessLevel.AHEAD_OF_MARKET:
            report.frequency_adjustment = 1.0
            report.edge_threshold_adjustment = 0.0
            report.recommendations.append("Model is sharp — maintain current strategy")

        elif report.level == SharpnessLevel.EVEN_WITH_MARKET:
            report.frequency_adjustment = 0.9
            report.edge_threshold_adjustment = 0.0
            report.recommendations.append("Marginal edge — consider reducing volume slightly")

        elif report.level == SharpnessLevel.BEHIND_MARKET:
            raise_pct = SHARPNESS_CONFIG["edge_raise_pct"]
            report.edge_threshold_adjustment = raise_pct
            report.frequency_adjustment = 0.7
            report.recommendations.append(
                f"Edge is eroding — raise threshold by {raise_pct:.0%}"
            )
            report.recommendations.append("Trigger accelerated meta-learning retrain")
            report.alert_message = (
                f"⚠ SHARPNESS ALARM: CLV={report.trailing_clv:.4f}, "
                f"trend={report.clv_trend}"
            )

        elif report.level == SharpnessLevel.CRITICALLY_STALE:
            report.should_pause = True
            report.frequency_adjustment = 0.0
            report.edge_threshold_adjustment = 0.20
            report.recommendations.append("CRITICAL: Model is stale — PAUSE all betting")
            report.recommendations.append("Mandatory full retrain before resuming")
            report.alert_message = (
                f"🚨 CRITICAL STALE: CLV={report.trailing_clv:.4f}, "
                f"positive_rate={report.clv_positive_rate:.0%}"
            )

        # Declining trend accelerates actions
        if report.clv_trend == "DECLINING":
            report.frequency_adjustment = max(0.0, report.frequency_adjustment - 0.1)
            report.recommendations.append("CLV trend declining — accelerate retrain")

        self._last_report = report
        return report

    def _compute_aggregate_decay(self) -> list[DecayPoint]:
        """Average decay curve across all tracked games."""
        hour_buckets = SHARPNESS_CONFIG["decay_lookback_hours"]
        aggregated = []

        for h in hour_buckets:
            edges = []
            for _game_id, points in self.decay_snapshots.items():
                # Find closest point to this hour bucket
                closest = min(points, key=lambda p: abs(p.hours_before - h), default=None)
                if closest and abs(closest.hours_before - h) < h * 0.3:
                    edges.append(closest.edge_pct)

            if edges:
                aggregated.append(DecayPoint(
                    hours_before=h,
                    edge_pct=round(sum(edges) / len(edges), 4),
                ))

        return aggregated

    def _estimate_half_life(self, curve: list[DecayPoint]) -> float:
        """Estimate the half-life of edge in hours."""
        if len(curve) < 2:
            return 12.0  # default

        # Find where edge drops to half of max
        max_edge = max(p.edge_pct for p in curve)
        if max_edge <= 0:
            return 0.0

        half = max_edge / 2
        for p in sorted(curve, key=lambda x: x.hours_before):
            if p.edge_pct <= half:
                return p.hours_before

        return curve[-1].hours_before  # never fully decays within window

    def get_quick_status(self) -> dict:
        """Quick status for dashboard."""
        if self._last_report:
            r = self._last_report
            return {
                "level": r.level.value,
                "trailing_clv": r.trailing_clv,
                "clv_trend": r.clv_trend,
                "positive_rate": r.clv_positive_rate,
                "should_pause": r.should_pause,
                "half_life_hours": r.half_life_hours,
                "samples": r.clv_samples,
            }
        return {"level": "UNKNOWN", "samples": 0}
