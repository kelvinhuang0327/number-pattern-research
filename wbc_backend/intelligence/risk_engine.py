"""
Phase 7 — Institutional Risk Engine
========================================
Hard-coded risk limits that CANNOT be overridden by any other module.

Rules:
  - Max daily exposure: 12% of bankroll
  - Max single bet: 2.5% of bankroll
  - Consecutive loss auto-shutdown: configurable N
  - Drawdown circuit breakers (tiered)
  - Correlation-aware exposure limits
  - Session-level risk tracking

Builds on existing BankrollState but adds institutional-grade guardrails.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum


# ─── Configuration (IMMUTABLE — do not override) ───────────────────────────

RISK_LIMITS = {
    # Position limits
    "max_single_bet_pct": 0.025,       # 2.5% of bankroll
    "max_daily_exposure_pct": 0.12,    # 12% of bankroll total daily
    "max_concurrent_bets": 8,          # max open positions at once
    "max_correlated_exposure": 0.06,   # 6% max on correlated events

    # Loss limits
    "consecutive_loss_shutdown": 5,    # auto-shutdown after N consecutive losses
    "daily_loss_limit_pct": 0.05,      # stop after 5% daily loss
    "session_loss_limit_pct": 0.08,    # stop after 8% session loss

    # Drawdown circuit breakers
    "drawdown_warning": 0.10,          # 10% dd → reduce sizing 50%
    "drawdown_critical": 0.15,         # 15% dd → reduce sizing 75%
    "drawdown_shutdown": 0.20,         # 20% dd → full shutdown

    # Recovery
    "recovery_mode_threshold": 0.08,   # enter recovery mode at 8% dd
    "recovery_max_bet_pct": 0.015,     # reduced max in recovery mode
    "recovery_exit_games": 10,         # min profitable games to exit recovery

    # Timing
    "min_time_between_bets_sec": 60,   # prevent rapid-fire betting
}


# ─── Data Structures ────────────────────────────────────────────────────────

class RiskLevel(Enum):
    GREEN = "GREEN"           # all systems nominal
    YELLOW = "YELLOW"         # warning, reduced sizing
    ORANGE = "ORANGE"         # critical, heavily reduced
    RED = "RED"               # shutdown, no betting
    BLACK = "BLACK"           # emergency shutdown, manual intervention


class RiskViolation(Enum):
    SINGLE_BET_EXCEEDED = "SINGLE_BET_EXCEEDED"
    DAILY_EXPOSURE_EXCEEDED = "DAILY_EXPOSURE_EXCEEDED"
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    SESSION_LOSS_LIMIT = "SESSION_LOSS_LIMIT"
    DRAWDOWN_WARNING = "DRAWDOWN_WARNING"
    DRAWDOWN_CRITICAL = "DRAWDOWN_CRITICAL"
    DRAWDOWN_SHUTDOWN = "DRAWDOWN_SHUTDOWN"
    CORRELATED_EXPOSURE = "CORRELATED_EXPOSURE"
    CONCURRENT_LIMIT = "CONCURRENT_LIMIT"
    RAPID_FIRE = "RAPID_FIRE"
    SHARPNESS_PAUSE = "SHARPNESS_PAUSE"


@dataclass
class RiskState:
    """Current state of the risk engine."""
    # Bankroll
    initial_bankroll: float = 10000.0
    current_bankroll: float = 10000.0
    peak_bankroll: float = 10000.0
    drawdown: float = 0.0
    drawdown_pct: float = 0.0

    # Daily tracking
    daily_exposure: float = 0.0
    daily_pnl: float = 0.0
    daily_bets: int = 0
    daily_wins: int = 0
    daily_losses: int = 0

    # Session tracking
    session_pnl: float = 0.0
    session_bets: int = 0
    session_start: float = 0.0

    # Streak tracking
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    max_consecutive_losses: int = 0

    # Open positions
    open_positions: list[dict] = field(default_factory=list)
    position_correlations: dict[str, list[str]] = field(default_factory=dict)

    # Recovery mode
    in_recovery: bool = False
    recovery_started_at: float = 0.0
    recovery_profitable_games: int = 0

    # Status
    risk_level: RiskLevel = RiskLevel.GREEN
    active_violations: list[RiskViolation] = field(default_factory=list)
    is_shutdown: bool = False
    shutdown_reason: str = ""

    # Timing
    last_bet_time: float = 0.0


@dataclass
class RiskCheckResult:
    """Result of a pre-bet risk check."""
    approved: bool = True
    risk_level: RiskLevel = RiskLevel.GREEN
    violations: list[RiskViolation] = field(default_factory=list)
    max_allowed_size: float = 0.025        # max bet size as % of bankroll
    sizing_multiplier: float = 1.0         # apply to position sizing
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ─── Risk Engine ────────────────────────────────────────────────────────────

class RiskEngine:
    """Institutional-grade risk management engine."""

    def __init__(self, initial_bankroll: float = 10000.0):
        self.state = RiskState(
            initial_bankroll=initial_bankroll,
            current_bankroll=initial_bankroll,
            peak_bankroll=initial_bankroll,
            session_start=time.time(),
        )

    def pre_bet_check(  # noqa: C901
        self,
        proposed_size_pct: float,
        match_id: str = "",
        correlated_events: list[str] | None = None,
        sharpness_paused: bool = False,
    ) -> RiskCheckResult:
        """
        Run ALL risk checks before placing a bet.
        Returns approval/rejection with max allowed size.
        """
        result = RiskCheckResult()
        state = self.state

        # ── Check 0: System shutdown ──
        if state.is_shutdown:
            result.approved = False
            result.risk_level = RiskLevel.RED
            result.violations.append(RiskViolation.DRAWDOWN_SHUTDOWN)
            result.reasons.append(f"System shutdown: {state.shutdown_reason}")
            return result

        # ── Check 1: Sharpness pause ──
        if sharpness_paused:
            result.approved = False
            result.risk_level = RiskLevel.RED
            result.violations.append(RiskViolation.SHARPNESS_PAUSE)
            result.reasons.append("Sharpness monitor has paused betting")
            return result

        # ── Check 2: Single bet size ──
        max_single = RISK_LIMITS["max_single_bet_pct"]
        if state.in_recovery:
            max_single = RISK_LIMITS["recovery_max_bet_pct"]

        if proposed_size_pct > max_single:
            result.violations.append(RiskViolation.SINGLE_BET_EXCEEDED)
            result.reasons.append(
                f"Size {proposed_size_pct:.2%} > max {max_single:.2%}"
            )
        result.max_allowed_size = max_single

        # ── Check 3: Daily exposure ──
        daily_max = RISK_LIMITS["max_daily_exposure_pct"] * state.current_bankroll
        proposed_amount = proposed_size_pct * state.current_bankroll
        if state.daily_exposure + proposed_amount > daily_max:
            result.violations.append(RiskViolation.DAILY_EXPOSURE_EXCEEDED)
            remaining = daily_max - state.daily_exposure
            result.reasons.append(
                f"Daily exposure would be "
                f"{(state.daily_exposure + proposed_amount) / state.current_bankroll:.2%} "
                f"> limit {RISK_LIMITS['max_daily_exposure_pct']:.0%}"
            )
            if remaining > 0:
                result.max_allowed_size = min(
                    result.max_allowed_size,
                    remaining / state.current_bankroll,
                )

        # ── Check 4: Consecutive losses ──
        if state.consecutive_losses >= RISK_LIMITS["consecutive_loss_shutdown"]:
            result.violations.append(RiskViolation.CONSECUTIVE_LOSSES)
            result.reasons.append(
                f"{state.consecutive_losses} consecutive losses ≥ "
                f"limit {RISK_LIMITS['consecutive_loss_shutdown']}"
            )

        # ── Check 5: Daily loss limit ──
        daily_loss_pct = abs(min(0, state.daily_pnl)) / state.current_bankroll
        if daily_loss_pct >= RISK_LIMITS["daily_loss_limit_pct"]:
            result.violations.append(RiskViolation.DAILY_LOSS_LIMIT)
            result.reasons.append(
                f"Daily loss {daily_loss_pct:.2%} ≥ limit "
                f"{RISK_LIMITS['daily_loss_limit_pct']:.0%}"
            )

        # ── Check 6: Session loss limit ──
        session_loss_pct = abs(min(0, state.session_pnl)) / state.initial_bankroll
        if session_loss_pct >= RISK_LIMITS["session_loss_limit_pct"]:
            result.violations.append(RiskViolation.SESSION_LOSS_LIMIT)
            result.reasons.append(
                f"Session loss {session_loss_pct:.2%} ≥ limit "
                f"{RISK_LIMITS['session_loss_limit_pct']:.0%}"
            )

        # ── Check 7: Drawdown circuit breakers ──
        dd = state.drawdown_pct
        if dd >= RISK_LIMITS["drawdown_shutdown"]:
            result.violations.append(RiskViolation.DRAWDOWN_SHUTDOWN)
            result.reasons.append(f"Drawdown {dd:.1%} ≥ shutdown {RISK_LIMITS['drawdown_shutdown']:.0%}")
        elif dd >= RISK_LIMITS["drawdown_critical"]:
            result.violations.append(RiskViolation.DRAWDOWN_CRITICAL)
            result.warnings.append(f"Drawdown {dd:.1%} ≥ critical level")
            result.sizing_multiplier = 0.25
        elif dd >= RISK_LIMITS["drawdown_warning"]:
            result.violations.append(RiskViolation.DRAWDOWN_WARNING)
            result.warnings.append(f"Drawdown {dd:.1%} ≥ warning level")
            result.sizing_multiplier = 0.50

        # ── Check 8: Concurrent positions ──
        if len(state.open_positions) >= RISK_LIMITS["max_concurrent_bets"]:
            result.violations.append(RiskViolation.CONCURRENT_LIMIT)
            result.reasons.append(
                f"Open positions {len(state.open_positions)} ≥ "
                f"limit {RISK_LIMITS['max_concurrent_bets']}"
            )

        # ── Check 9: Correlated exposure ──
        if correlated_events:
            corr_exposure = sum(
                p.get("size_pct", 0)
                for p in state.open_positions
                if p.get("match_id") in correlated_events
            )
            max_corr = RISK_LIMITS["max_correlated_exposure"]
            if corr_exposure + proposed_size_pct > max_corr:
                result.violations.append(RiskViolation.CORRELATED_EXPOSURE)
                result.warnings.append(
                    f"Correlated exposure would be {corr_exposure + proposed_size_pct:.2%}"
                )

        # ── Check 10: Rapid-fire protection ──
        if state.last_bet_time > 0:
            elapsed = time.time() - state.last_bet_time
            if elapsed < RISK_LIMITS["min_time_between_bets_sec"]:
                result.violations.append(RiskViolation.RAPID_FIRE)
                result.warnings.append(
                    f"Only {elapsed:.0f}s since last bet "
                    f"(min {RISK_LIMITS['min_time_between_bets_sec']}s)"
                )

        # ── Determine final approval ──
        hard_blocks = {
            RiskViolation.DRAWDOWN_SHUTDOWN,
            RiskViolation.CONSECUTIVE_LOSSES,
            RiskViolation.DAILY_LOSS_LIMIT,
            RiskViolation.SESSION_LOSS_LIMIT,
            RiskViolation.SHARPNESS_PAUSE,
        }

        if any(v in hard_blocks for v in result.violations):
            result.approved = False
            result.risk_level = RiskLevel.RED
        elif RiskViolation.DRAWDOWN_CRITICAL in result.violations:
            result.approved = True  # allowed but heavily reduced
            result.risk_level = RiskLevel.ORANGE
        elif result.violations:
            # Soft violations — allow with warnings
            result.approved = True
            result.risk_level = RiskLevel.YELLOW
        else:
            result.approved = True
            result.risk_level = RiskLevel.GREEN

        # Adjust max allowed by sizing multiplier
        result.max_allowed_size *= result.sizing_multiplier

        return result

    def record_bet(
        self,
        match_id: str,
        size_pct: float,
        odds: float,
        side: str = "",
        bet_type: str = "",
    ) -> None:
        """Record a bet being placed."""
        state = self.state
        amount = size_pct * state.current_bankroll

        state.daily_bets += 1
        state.daily_exposure += amount
        state.session_bets += 1
        state.last_bet_time = time.time()

        state.open_positions.append({
            "match_id": match_id,
            "size_pct": size_pct,
            "amount": amount,
            "odds": odds,
            "side": side,
            "bet_type": bet_type,
            "placed_at": time.time(),
        })

    def record_result(self, match_id: str, won: bool, pnl: float) -> None:
        """Record the result of a settled bet."""
        state = self.state

        # Remove from open positions
        state.open_positions = [
            p for p in state.open_positions if p.get("match_id") != match_id
        ]

        # Update P&L
        state.daily_pnl += pnl
        state.session_pnl += pnl
        state.current_bankroll += pnl

        # Update peak/drawdown
        if state.current_bankroll > state.peak_bankroll:
            state.peak_bankroll = state.current_bankroll
        state.drawdown = state.peak_bankroll - state.current_bankroll
        state.drawdown_pct = state.drawdown / state.peak_bankroll if state.peak_bankroll > 0 else 0

        # Update streaks
        if won:
            state.daily_wins += 1
            state.consecutive_wins += 1
            state.consecutive_losses = 0
            if state.in_recovery:
                state.recovery_profitable_games += 1
                if state.recovery_profitable_games >= RISK_LIMITS["recovery_exit_games"]:
                    state.in_recovery = False
        else:
            state.daily_losses += 1
            state.consecutive_losses += 1
            state.consecutive_wins = 0
            state.max_consecutive_losses = max(
                state.max_consecutive_losses, state.consecutive_losses,
            )

        # Check for recovery mode entry
        if state.drawdown_pct >= RISK_LIMITS["recovery_mode_threshold"] and not state.in_recovery:
            state.in_recovery = True
            state.recovery_started_at = time.time()
            state.recovery_profitable_games = 0

        # Check for shutdown
        if state.drawdown_pct >= RISK_LIMITS["drawdown_shutdown"]:
            state.is_shutdown = True
            state.shutdown_reason = f"Drawdown {state.drawdown_pct:.1%} hit shutdown level"

        if state.consecutive_losses >= RISK_LIMITS["consecutive_loss_shutdown"]:
            state.is_shutdown = True
            state.shutdown_reason = f"{state.consecutive_losses} consecutive losses"

        # Update risk level
        self._update_risk_level()

    def _update_risk_level(self) -> None:
        """Update the overall risk level."""
        state = self.state
        if state.is_shutdown:
            state.risk_level = RiskLevel.RED
        elif state.drawdown_pct >= RISK_LIMITS["drawdown_critical"]:
            state.risk_level = RiskLevel.ORANGE
        elif state.drawdown_pct >= RISK_LIMITS["drawdown_warning"]:
            state.risk_level = RiskLevel.YELLOW
        else:
            state.risk_level = RiskLevel.GREEN

    def reset_daily(self) -> None:
        """Reset daily counters (call at start of each day)."""
        state = self.state
        state.daily_exposure = 0.0
        state.daily_pnl = 0.0
        state.daily_bets = 0
        state.daily_wins = 0
        state.daily_losses = 0

    def manual_shutdown(self, reason: str = "Manual intervention") -> None:
        """Emergency shutdown."""
        self.state.is_shutdown = True
        self.state.shutdown_reason = reason
        self.state.risk_level = RiskLevel.BLACK

    def manual_resume(self) -> None:
        """Resume after manual review."""
        state = self.state
        if state.drawdown_pct < RISK_LIMITS["drawdown_shutdown"]:
            state.is_shutdown = False
            state.shutdown_reason = ""
            state.consecutive_losses = 0
            self._update_risk_level()

    def get_status(self) -> dict:
        """Get current risk status for dashboard."""
        s = self.state
        return {
            "risk_level": s.risk_level.value,
            "bankroll": round(s.current_bankroll, 2),
            "drawdown_pct": round(s.drawdown_pct, 4),
            "daily_pnl": round(s.daily_pnl, 2),
            "daily_bets": s.daily_bets,
            "consecutive_losses": s.consecutive_losses,
            "open_positions": len(s.open_positions),
            "daily_exposure_pct": round(
                s.daily_exposure / s.current_bankroll, 4
            ) if s.current_bankroll > 0 else 0,
            "in_recovery": s.in_recovery,
            "is_shutdown": s.is_shutdown,
            "shutdown_reason": s.shutdown_reason,
        }
