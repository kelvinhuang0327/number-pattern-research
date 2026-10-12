"""
Risk Control Module — § 五 投注風險控制

Provides:
  • Max drawdown limiting
  • Bankroll allocation management
  • Volatility control
  • Consecutive loss handling
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from wbc_backend.config.settings import BankrollConfig

logger = logging.getLogger(__name__)


@dataclass
class BankrollState:
    """Tracks current bankroll state for risk management."""
    initial: float = 100_000.0
    current: float = 100_000.0
    peak: float = 100_000.0
    daily_start: float = 100_000.0
    consecutive_losses: int = 0
    total_bets_today: int = 0
    daily_exposure: float = 0.0
    is_conservative_mode: bool = False
    recent_results: list[float] = field(default_factory=list)  # P&L of recent bets

    @property
    def drawdown(self) -> float:
        """Current drawdown from peak."""
        if self.peak <= 0:
            return 0.0
        return (self.peak - self.current) / self.peak

    @property
    def daily_pnl_pct(self) -> float:
        """Today's P&L as percentage of start-of-day bankroll."""
        if self.daily_start <= 0:
            return 0.0
        return (self.current - self.daily_start) / self.daily_start

    @property
    def daily_exposure_pct(self) -> float:
        """Today's total exposure as percentage of bankroll."""
        if self.current <= 0:
            return 0.0
        return self.daily_exposure / self.current


def check_risk_limits(
    state: BankrollState,
    proposed_stake: float,
    config: BankrollConfig,
) -> tuple[float, list[str]]:
    """
    Check all risk limits and adjust the proposed stake if necessary.

    Returns
    -------
    (adjusted_stake, warnings)
    """
    warnings: list[str] = []
    adjusted = proposed_stake

    # ── 1. Max single bet ────────────────────────────────
    max_bet = state.current * config.max_single_bet_pct
    if adjusted > max_bet:
        adjusted = max_bet
        warnings.append(f"Stake capped at {config.max_single_bet_pct*100:.0f}% of bankroll: ${max_bet:.0f}")

    # ── 2. Daily exposure limit ──────────────────────────
    remaining_exposure = state.current * config.max_daily_exposure_pct - state.daily_exposure
    if adjusted > remaining_exposure:
        adjusted = max(0, remaining_exposure)
        warnings.append(f"Daily exposure limit reached ({config.max_daily_exposure_pct*100:.0f}%)")

    # ── 3. Daily loss stop ───────────────────────────────
    if state.daily_pnl_pct <= -config.daily_loss_stop_pct:
        adjusted = 0
        warnings.append(f"DAILY LOSS STOP: Down {abs(state.daily_pnl_pct)*100:.1f}% today")

    # ── 4. Consecutive loss reduction ────────────────────
    if state.consecutive_losses >= config.consecutive_loss_threshold:
        reduction = config.consecutive_loss_reduction
        adjusted *= reduction
        warnings.append(
            f"Consecutive loss reduction ({state.consecutive_losses} losses): "
            f"stake reduced to {reduction*100:.0f}%"
        )

    # ── 5. Drawdown conservative mode ────────────────────
    if state.drawdown >= config.drawdown_conservative_pct:
        state.is_conservative_mode = True
        adjusted *= 0.5
        warnings.append(
            f"CONSERVATIVE MODE: Drawdown {state.drawdown*100:.1f}% "
            f"exceeds {config.drawdown_conservative_pct*100:.0f}% threshold"
        )

    # ── 6. Minimum stake check ───────────────────────────
    if adjusted < 0:
        adjusted = 0

    if warnings:
        for w in warnings:
            logger.warning("RISK: %s", w)

    return round(adjusted, 2), warnings


def compute_volatility(results: list[float], lookback: int = 30) -> float:
    """Compute rolling volatility of recent bet results."""
    if len(results) < 2:
        return 0.0

    recent = results[-lookback:]
    mean = sum(recent) / len(recent)
    variance = sum((r - mean) ** 2 for r in recent) / len(recent)
    return variance ** 0.5


def update_bankroll(
    state: BankrollState,
    pnl: float,
    stake: float,
) -> BankrollState:
    """Update bankroll state after a bet resolves."""
    state.current += pnl
    state.peak = max(state.peak, state.current)
    state.daily_exposure += stake
    state.total_bets_today += 1
    state.recent_results.append(pnl)

    if pnl < 0:
        state.consecutive_losses += 1
    else:
        state.consecutive_losses = 0

    # Check if we can exit conservative mode
    if state.is_conservative_mode and state.drawdown < 0.05:
        state.is_conservative_mode = False
        logger.info("Exiting conservative mode: drawdown recovered to %.1f%%",
                     state.drawdown * 100)

    return state


def reset_daily(state: BankrollState) -> BankrollState:
    """Reset daily tracking (call at start of each day)."""
    state.daily_start = state.current
    state.daily_exposure = 0.0
    state.total_bets_today = 0
    return state
