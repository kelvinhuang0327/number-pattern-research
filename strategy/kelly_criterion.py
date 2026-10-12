"""
Modified Kelly Criterion for bankroll management.

Uses fractional Kelly (default ¼) with hard caps on single-bet and
daily exposure.  Integrates loss-streak and drawdown circuit-breakers.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from config import settings as cfg
from strategy.value_detector import ValueBet


@dataclass
class BetSizing:
    bet: ValueBet
    kelly_full: float       # full Kelly fraction
    kelly_used: float       # fractional Kelly applied
    stake_pct: float        # final % of bankroll
    stake_amount: float     # monetary amount
    capped: bool = False    # was it capped by limits?


@dataclass
class BankrollState:
    initial: float = cfg.INITIAL_BANKROLL
    current: float = cfg.INITIAL_BANKROLL
    peak: float = cfg.INITIAL_BANKROLL
    consecutive_losses: int = 0
    daily_pnl: float = 0.0
    conservative_mode: bool = False
    bets_today: List[BetSizing] = None

    def __post_init__(self):
        if self.bets_today is None:
            self.bets_today = []

    @property
    def drawdown_pct(self) -> float:
        if self.peak == 0:
            return 0.0
        return (self.peak - self.current) / self.peak

    @property
    def daily_exposure(self) -> float:
        return sum(b.stake_pct for b in self.bets_today)

    def update_after_result(self, pnl: float, won: bool):
        self.current += pnl
        self.daily_pnl += pnl
        if self.current > self.peak:
            self.peak = self.current
        if won:
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
        # Check conservative mode/drawdown logic
        pass # conservative_mode is deprecated in favor of continuous Drawdown Adaptive Kelly


def kelly_fraction(true_prob: float, decimal_odds: float) -> float:
    """
    Full Kelly: f* = (bp − q) / b
    where b = decimal_odds − 1, p = true_prob, q = 1 − p.
    """
    b = decimal_odds - 1.0
    p = true_prob
    q = 1.0 - p
    if b <= 0:
        return 0.0
    f = (b * p - q) / b
    return max(0.0, f)


def size_bet(
    bet: ValueBet,
    state: BankrollState,
) -> BetSizing:
    """
    Compute stake for a single ValueBet given current bankroll state.
    """
    f_full = kelly_fraction(bet.true_prob, bet.decimal_odds)
    f_used = f_full * cfg.KELLY_FRACTION  # fractional Kelly

    # ── Drawdown Adaptive Kelly (V3) ─────────────────────
    # Formula: f_used *= max(0, 1 - (D_t / D_max))^k
    drawdown = state.drawdown_pct
    decay_multiplier = max(0.0, 1.0 - (drawdown / cfg.DRAWDOWN_MAX)) ** getattr(cfg, "DRAWDOWN_K_FACTOR", 2.0)
    f_used *= decay_multiplier

    # ── Consecutive-loss reduction ───────────────────────
    if state.consecutive_losses >= cfg.CONSECUTIVE_LOSS_THRESHOLD:
        f_used *= cfg.CONSECUTIVE_LOSS_REDUCTION

    # ── Hard caps ────────────────────────────────────────
    capped = False
    
    # Single-bet cap
    if f_used > cfg.MAX_SINGLE_BET_PCT:
        f_used = cfg.MAX_SINGLE_BET_PCT
        capped = True

    # Daily exposure cap
    remaining = cfg.MAX_DAILY_EXPOSURE_PCT - state.daily_exposure
    if f_used > remaining:
        f_used = max(0.0, remaining)
        capped = True

    # If tier is PASS or EV ≤ 0 or Market Restricted, change stake
    if bet.edge_tier == "PASS" or bet.ev <= 0 or "Restricted" in bet.edge_tier or "SECONDARY" in bet.edge_tier:
        if bet.edge_tier == "PASS" or bet.ev <= 0:
            f_used = 0.0
        else:
            # 降注觀察
            f_used = min(f_used, 0.005) # 給予極小的觀察注 0.5%

    stake_amount = round(f_used * state.current, 2)

    sizing = BetSizing(
        bet=bet,
        kelly_full=round(f_full, 6),
        kelly_used=round(f_used, 6),
        stake_pct=round(f_used, 6),
        stake_amount=stake_amount,
        capped=capped,
    )
    return sizing


def build_portfolio(
    bets: List[ValueBet],
    state: BankrollState,
) -> List[BetSizing]:
    """
    Size all bets and return the portfolio (only actionable bets).
    """
    portfolio: List[BetSizing] = []
    for b in bets:
        if b.edge_tier == "PASS":
            continue
        sizing = size_bet(b, state)
        if sizing.stake_amount > 0:
            portfolio.append(sizing)
            state.bets_today.append(sizing)
    return portfolio
