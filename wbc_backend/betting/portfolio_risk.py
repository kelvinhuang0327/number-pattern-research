"""
Portfolio-Level Risk Management — Phase 7
==========================================
Institutional-grade risk framework implementing:

  1. Correlation-aware Kelly position sizing
     (multiple simultaneous bets with correlated outcomes)
  2. Drawdown management with circuit breakers
  3. Risk-of-ruin modeling
  4. Portfolio-level exposure control
  5. Variance targeting (volatility budget)

Theory:
  Individual Kelly: f* = (bp - q) / b
  Portfolio Kelly: f* = Σ^{-1} μ / τ
  where Σ = correlation matrix, μ = expected returns, τ = risk aversion

§ 核心規範 03: All positions sized through this module.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

BANKROLL_DB = Path("data/wbc_backend/portfolio_risk.json")

# Risk limits
MAX_SINGLE_BET_FRACTION = 0.05      # Never bet >5% on single game
MAX_PORTFOLIO_EXPOSURE = 0.20       # Never have >20% total open positions
MAX_DAILY_LOSS_PCT = 0.10           # Circuit breaker: stop if day loss >10%
MAX_DRAWDOWN_CIRCUIT_BREAKER = 0.20 # Hard stop if drawdown >20%
VARIANCE_TARGET_DAILY = 0.02        # Target 2% daily volatility

# Correlation assumptions (games in same tournament have correlated outcomes)
SAME_TOURNAMENT_CORR = 0.15         # WBC games in same pool are correlated
SAME_DAY_CORR = 0.10                # Same-day games have weather/field correlation
DEFAULT_CORR = 0.05                 # Default correlation between independent games


# ── Data Structures ────────────────────────────────────────────────────────

@dataclass
class BetProposal:
    """Single bet proposal before portfolio-level sizing."""
    game_id: str
    market: str           # ML | RL | OU | OE | F5
    side: str             # home | away | over | under
    win_prob: float       # Model's estimated win probability
    odds: float           # Decimal odds
    ev: float             # Expected value = win_prob * (odds - 1) - (1 - win_prob)
    edge: float           # Edge vs market = win_prob - implied_prob
    individual_kelly: float  # Raw Kelly fraction
    confidence: float     # Model confidence [0,1]
    tournament: str = "WBC"
    game_date: str = ""
    group: str = ""       # Tournament group/round for correlation grouping


@dataclass
class PortfolioPosition:
    """Active position after portfolio sizing."""
    bet: BetProposal
    portfolio_kelly: float   # Adjusted Kelly after correlation
    stake_fraction: float    # Final stake as % of bankroll
    stake_amount: float      # Dollar amount
    variance_contribution: float  # Contribution to portfolio variance


@dataclass
class PortfolioState:
    """Current portfolio state."""
    bankroll: float = 100_000.0
    initial_bankroll: float = 100_000.0
    total_exposure: float = 0.0      # Sum of open position sizes
    daily_pnl: float = 0.0
    peak_bankroll: float = 100_000.0
    current_drawdown: float = 0.0
    is_circuit_breaker_active: bool = False
    consecutive_losses: int = 0
    session_bets: int = 0
    session_wins: int = 0
    n_updates: int = 0

    @property
    def drawdown(self) -> float:
        if self.peak_bankroll <= 0:
            return 0.0
        return (self.peak_bankroll - self.bankroll) / self.peak_bankroll

    @property
    def risk_of_ruin_estimate(self) -> float:
        """Estimate risk of ruin using normal approximation."""
        if self.bankroll <= 0:
            return 1.0
        ruin_threshold = self.initial_bankroll * 0.10
        win_rate = self.session_wins / max(1, self.session_bets)
        if win_rate <= 0.5:
            return min(0.99, (1.0 - win_rate) / (win_rate + 1e-6))
        edge = 2 * win_rate - 1
        ratio = ruin_threshold / self.bankroll
        return max(0.0, min(1.0, ratio ** (edge * 2)))

    def to_dict(self) -> dict:
        return {
            "bankroll": self.bankroll,
            "initial_bankroll": self.initial_bankroll,
            "total_exposure": self.total_exposure,
            "daily_pnl": self.daily_pnl,
            "peak_bankroll": self.peak_bankroll,
            "current_drawdown": self.current_drawdown,
            "is_circuit_breaker_active": self.is_circuit_breaker_active,
            "consecutive_losses": self.consecutive_losses,
            "session_bets": self.session_bets,
            "session_wins": self.session_wins,
            "n_updates": self.n_updates,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PortfolioState:
        state = cls()
        for k, v in d.items():
            if hasattr(state, k):
                setattr(state, k, v)
        return state


@dataclass
class PortfolioSizingResult:
    """Result of portfolio-level position sizing."""
    positions: list[PortfolioPosition]
    total_exposure: float
    portfolio_variance: float
    expected_daily_return: float
    sharpe_estimate: float
    risk_level: str         # GREEN | YELLOW | RED
    circuit_breaker_active: bool
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)


# ── Portfolio Risk Engine ───────────────────────────────────────────────────

class PortfolioRiskManager:
    """
    Institutional portfolio-level risk management system.

    Handles correlation-aware Kelly sizing, drawdown management,
    and portfolio exposure control across multiple simultaneous bets.
    """

    def __init__(self, initial_bankroll: float = 100_000.0):
        self.state = self._load_or_initialize(initial_bankroll)

    def _load_or_initialize(self, initial_bankroll: float) -> PortfolioState:
        if BANKROLL_DB.exists():
            try:
                with open(BANKROLL_DB) as f:
                    data = json.load(f)
                state = PortfolioState.from_dict(data)
                logger.info("Portfolio state loaded: bankroll=%.2f, drawdown=%.2f%%",
                            state.bankroll, state.drawdown * 100)
                return state
            except Exception as e:
                logger.warning("Failed to load portfolio state: %s", e)

        state = PortfolioState(
            bankroll=initial_bankroll,
            initial_bankroll=initial_bankroll,
            peak_bankroll=initial_bankroll,
        )
        return state

    def size_portfolio(self, proposals: list[BetProposal]) -> PortfolioSizingResult:  # noqa: C901  # NOSONAR
        """
        Size a portfolio of simultaneous bet proposals.

        Algorithm:
          1. Filter out negative EV bets
          2. Compute pairwise correlation matrix
          3. Apply fractional Kelly with correlation adjustment
          4. Apply portfolio exposure constraint
          5. Apply variance target constraint
          6. Check circuit breakers
        """
        warnings: list[str] = []
        positions: list[PortfolioPosition] = []

        # Check circuit breakers first
        if self.state.is_circuit_breaker_active:
            warnings.append("CIRCUIT BREAKER ACTIVE — no bets allowed until reset")
            return PortfolioSizingResult(
                positions=[], total_exposure=0.0, portfolio_variance=0.0,
                expected_daily_return=0.0, sharpe_estimate=0.0,
                risk_level="RED", circuit_breaker_active=True, warnings=warnings
            )

        if self.state.drawdown > MAX_DRAWDOWN_CIRCUIT_BREAKER:
            self.state.is_circuit_breaker_active = True
            warnings.append(
                f"CIRCUIT BREAKER TRIGGERED: drawdown={self.state.drawdown:.1%} "
                f"> {MAX_DRAWDOWN_CIRCUIT_BREAKER:.1%} limit"
            )
            self.save()
            return PortfolioSizingResult(
                positions=[], total_exposure=0.0, portfolio_variance=0.0,
                expected_daily_return=0.0, sharpe_estimate=0.0,
                risk_level="RED", circuit_breaker_active=True, warnings=warnings
            )

        # Step 1: Filter valid proposals
        valid = [p for p in proposals if p.ev > 0 and p.edge > 0.01]
        if not valid:
            return PortfolioSizingResult(
                positions=[], total_exposure=0.0, portfolio_variance=0.0,
                expected_daily_return=0.0, sharpe_estimate=0.0,
                risk_level="GREEN", circuit_breaker_active=False,
                warnings=["No positive EV proposals"]
            )

        # Step 2: Compute correlation matrix
        corr_matrix = self._build_correlation_matrix(valid)

        # Step 3: Individual Kelly fractions
        raw_fractions = np.array([p.individual_kelly for p in valid])
        # Cap individual fractions
        raw_fractions = np.clip(raw_fractions, 0.0, MAX_SINGLE_BET_FRACTION)

        # Step 4: Correlation adjustment
        # Diversification benefit: σ_portfolio < Σσ_i when corr < 1
        n = len(valid)
        if n > 1:
            # Portfolio variance = f^T * Σ * f
            # where Σ = corr_matrix * (σ_i * σ_j) approx for unit variance
            stake_vec = raw_fractions.copy()
            portfolio_var = float(stake_vec @ corr_matrix @ stake_vec)

            # Target variance: adjust if too high
            if portfolio_var > 0:
                scale = min(1.0, VARIANCE_TARGET_DAILY / math.sqrt(portfolio_var))
                adjusted_fractions = raw_fractions * scale
            else:
                adjusted_fractions = raw_fractions
        else:
            adjusted_fractions = raw_fractions

        # Step 5: Portfolio exposure constraint
        total_exposure = float(adjusted_fractions.sum())
        if total_exposure > MAX_PORTFOLIO_EXPOSURE:
            scale = MAX_PORTFOLIO_EXPOSURE / total_exposure
            adjusted_fractions *= scale
            total_exposure = MAX_PORTFOLIO_EXPOSURE
            warnings.append(
                f"Portfolio exposure capped at {MAX_PORTFOLIO_EXPOSURE:.0%} "
                f"(original: {total_exposure:.1%})"
            )

        # Step 6: Confidence scaling
        confidence_scaled = np.array([
            frac * max(0.3, min(1.0, prop.confidence))
            for frac, prop in zip(adjusted_fractions, valid)
        ])

        # Step 7: Drawdown-aware scaling
        # As drawdown increases, reduce position sizes
        drawdown_scale = max(0.3, 1.0 - self.state.drawdown * 2.0)
        confidence_scaled *= drawdown_scale

        if self.state.drawdown > 0.10:
            warnings.append(
                f"Position sizes reduced by {(1-drawdown_scale):.0%} due to "
                f"{self.state.drawdown:.1%} drawdown"
            )

        # Build positions
        expected_return = 0.0
        for i, (prop, frac) in enumerate(zip(valid, confidence_scaled)):
            stake_fraction = float(frac)
            stake_amount = self.state.bankroll * stake_fraction
            var_contrib = float(frac * frac)  # simplified variance contribution

            pos = PortfolioPosition(
                bet=prop,
                portfolio_kelly=float(adjusted_fractions[i]),
                stake_fraction=stake_fraction,
                stake_amount=stake_amount,
                variance_contribution=var_contrib,
            )
            positions.append(pos)
            expected_return += stake_fraction * prop.ev

        # Portfolio metrics
        total_exposure_final = sum(p.stake_fraction for p in positions)
        if len(positions) > 1:
            stake_vec = np.array([p.stake_fraction for p in positions])
            portfolio_var_final = float(
                stake_vec.T @ corr_matrix[:len(positions), :len(positions)] @ stake_vec
            )
        elif positions:
            portfolio_var_final = positions[0].stake_fraction ** 2
        else:
            portfolio_var_final = 0.0

        sharpe = expected_return / (math.sqrt(portfolio_var_final) + 1e-9)

        # Risk level classification
        if self.state.drawdown > 0.15:
            risk_level = "RED"
        elif self.state.drawdown > 0.08 or total_exposure_final > 0.15:
            risk_level = "YELLOW"
        else:
            risk_level = "GREEN"

        return PortfolioSizingResult(
            positions=positions,
            total_exposure=total_exposure_final,
            portfolio_variance=portfolio_var_final,
            expected_daily_return=expected_return,
            sharpe_estimate=sharpe,
            risk_level=risk_level,
            circuit_breaker_active=False,
            warnings=warnings,
            diagnostics={
                "bankroll": self.state.bankroll,
                "drawdown": round(self.state.drawdown, 4),
                "consecutive_losses": float(self.state.consecutive_losses),
                "risk_of_ruin": round(self.state.risk_of_ruin_estimate, 4),
                "n_proposals": float(len(proposals)),
                "n_valid": float(len(valid)),
                "n_positions": float(len(positions)),
                "drawdown_scale": round(drawdown_scale, 4),
            },
        )

    def _build_correlation_matrix(self, proposals: list[BetProposal]) -> np.ndarray:
        """
        Build pairwise correlation matrix based on game metadata.

        Rules:
          - Same tournament + same date: 0.15 (pool standings correlated)
          - Same tournament, different date: 0.10
          - Different tournament: 0.05
        """
        n = len(proposals)
        corr = np.eye(n)

        for i in range(n):
            for j in range(i + 1, n):
                a, b = proposals[i], proposals[j]

                if a.tournament == b.tournament:
                    if a.game_date == b.game_date:
                        c = SAME_DAY_CORR
                    elif a.group == b.group:
                        c = SAME_TOURNAMENT_CORR
                    else:
                        c = SAME_TOURNAMENT_CORR * 0.7
                else:
                    c = DEFAULT_CORR

                corr[i, j] = c
                corr[j, i] = c

        return corr

    def record_outcome(self, game_id: str, pnl: float, stake_amount: float) -> None:
        """Record a bet outcome and update portfolio state."""
        logger.debug("Recording outcome game_id=%s stake_amount=%.2f pnl=%.2f", game_id, stake_amount, pnl)
        self.state.bankroll += pnl
        self.state.daily_pnl += pnl
        self.state.session_bets += 1

        if pnl > 0:
            self.state.session_wins += 1
            self.state.consecutive_losses = 0
        else:
            self.state.consecutive_losses += 1

        # Update peak and drawdown
        self.state.peak_bankroll = max(self.state.peak_bankroll, self.state.bankroll)
        self.state.current_drawdown = self.state.drawdown

        # Daily loss circuit breaker
        daily_loss_pct = -self.state.daily_pnl / self.state.bankroll
        if daily_loss_pct > MAX_DAILY_LOSS_PCT:
            self.state.is_circuit_breaker_active = True
            logger.warning(
                "DAILY LOSS CIRCUIT BREAKER: %.1f%% loss today", daily_loss_pct * 100
            )

        self.state.n_updates += 1

        if self.state.bankroll <= 0:
            logger.critical("BANKROLL DEPLETED — system halted")
            self.state.is_circuit_breaker_active = True

        self.save()

    def reset_daily_pnl(self) -> None:
        """Call at start of each new trading day."""
        self.state.daily_pnl = 0.0
        if self.state.is_circuit_breaker_active and self.state.drawdown < 0.15:
            self.state.is_circuit_breaker_active = False
            logger.info("Daily circuit breaker reset")
        self.save()

    def save(self) -> None:
        """Persist portfolio state."""
        BANKROLL_DB.parent.mkdir(parents=True, exist_ok=True)
        with open(BANKROLL_DB, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    def get_risk_report(self) -> dict:
        """Human-readable risk report."""
        return {
            "bankroll": round(self.state.bankroll, 2),
            "initial_bankroll": round(self.state.initial_bankroll, 2),
            "pnl": round(self.state.bankroll - self.state.initial_bankroll, 2),
            "roi_pct": round((self.state.bankroll - self.state.initial_bankroll) / self.state.initial_bankroll * 100, 2),
            "current_drawdown_pct": round(self.state.drawdown * 100, 2),
            "peak_bankroll": round(self.state.peak_bankroll, 2),
            "risk_of_ruin": round(self.state.risk_of_ruin_estimate * 100, 2),
            "circuit_breaker": self.state.is_circuit_breaker_active,
            "consecutive_losses": self.state.consecutive_losses,
            "win_rate_pct": round(
                self.state.session_wins / max(1, self.state.session_bets) * 100, 1
            ),
            "total_bets": self.state.session_bets,
        }


# ── Correlation-Aware Kelly (Markowitz-style) ────────────────────────────────

def correlation_kelly(proposals: list[BetProposal],
                       risk_aversion: float = 2.0) -> dict[str, float]:
    """
    Markowitz mean-variance portfolio optimization for Kelly betting.

    Solves: max (μ^T f - 0.5 * τ * f^T Σ f)
    subject to: 0 ≤ f_i ≤ 0.05, Σf_i ≤ 0.20

    where τ = risk_aversion, μ = expected returns, Σ = correlation matrix

    Returns dict of {game_id → stake_fraction}
    """
    if not proposals:
        return {}

    n = len(proposals)
    mu = np.array([p.ev for p in proposals])
    f_kelly = np.array([p.individual_kelly for p in proposals])

    # Build correlation matrix
    corr = np.eye(n)
    for i in range(n):
        for j in range(i + 1, n):
            if proposals[i].tournament == proposals[j].tournament:
                corr[i, j] = corr[j, i] = SAME_TOURNAMENT_CORR
            else:
                corr[i, j] = corr[j, i] = DEFAULT_CORR

    try:
        # Analytical solution: f* = Σ^{-1} μ / τ
        corr_inv = np.linalg.inv(corr + np.eye(n) * 0.01)  # ridge
        f_opt = corr_inv @ mu / risk_aversion
        f_opt = np.clip(f_opt, 0.0, MAX_SINGLE_BET_FRACTION)

        # Scale to portfolio constraint
        total = f_opt.sum()
        if total > MAX_PORTFOLIO_EXPOSURE:
            f_opt *= MAX_PORTFOLIO_EXPOSURE / total

    except np.linalg.LinAlgError:
        # Fallback to individual Kelly
        f_opt = np.clip(f_kelly * 0.25, 0.0, MAX_SINGLE_BET_FRACTION)

    return {p.game_id: float(round(f, 4)) for p, f in zip(proposals, f_opt)}


# ── Risk-of-Ruin Calculator ──────────────────────────────────────────────────

def compute_risk_of_ruin(bankroll: float,
                          avg_bet_size: float,
                          win_rate: float,
                          avg_odds: float,
                          ruin_threshold: float = 0.10) -> dict[str, float]:
    """
    Compute risk of ruin using exact Gambler's ruin formula.

    Ruin defined as bankroll falling below ruin_threshold * initial_bankroll.

    Parameters
    ----------
    bankroll : current bankroll
    avg_bet_size : average bet size (fraction of bankroll)
    win_rate : estimated win probability
    avg_odds : average decimal odds
    ruin_threshold : fraction of bankroll defining ruin

    Returns dict with probability estimates.
    """
    if win_rate <= 0 or win_rate >= 1:
        return {"risk_of_ruin": 1.0, "expected_bets_to_ruin": 0}

    p = win_rate
    q = 1.0 - p
    b = avg_odds - 1.0  # net payout

    ev_per_bet = p * b - q
    ruin_level = bankroll * ruin_threshold

    if ev_per_bet <= 0:
        # Negative EV → certain ruin eventually
        p_ruin = 1.0
    else:
        # Gambler's ruin: P(ruin | starting wealth W, absorbing barrier 0, target ∞)
        # For walk with drift: P(ruin from W) ≈ (q/p)^(W/u) where u = avg bet unit
        if p > q:
            unit = avg_bet_size * bankroll
            n_units_to_ruin = max(1, ruin_level / unit)
            ratio = q / p
            p_ruin = min(0.999, ratio ** n_units_to_ruin)
        else:
            p_ruin = 1.0

    # Expected bets until ruin or significant drawdown
    if ev_per_bet > 0:
        # Kelly growth rate: g = p * log(1 + b*f) + q * log(1 - f)
        f = min(avg_bet_size, 0.05)
        g = p * math.log1p(b * f) + q * math.log(max(1e-9, 1 - f))
        # Expected bets to double: log(2) / g
        bets_to_double = math.log(2.0) / max(1e-9, g)
    else:
        bets_to_double = float('inf')

    return {
        "risk_of_ruin": round(float(p_ruin), 4),
        "edge_per_bet": round(float(ev_per_bet), 4),
        "kelly_growth_rate": round(float(
            p * math.log1p(b * avg_bet_size) + q * math.log(max(1e-9, 1 - avg_bet_size))
        ), 6),
        "bets_to_double": round(float(bets_to_double), 1) if bets_to_double != float('inf') else None,
        "recommended_max_stake": round(float(ev_per_bet / b), 4),  # Full Kelly
    }
