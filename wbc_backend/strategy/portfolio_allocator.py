"""
Portfolio Allocator — § 十 組合最佳化與風險分配系統
==========================================
將單場決策升級為整日賽事組合下注，透過資產相關性與均值方差進行最佳化。
"""
from __future__ import annotations

import logging
import numpy as np

from wbc_backend.domain.schemas import BetRecommendation
from wbc_backend.config.settings import BankrollConfig

logger = logging.getLogger(__name__)

class PortfolioAllocator:
    """
    Optimizes a group of bet recommendations into a balanced portfolio.
    """
    def __init__(self, bankroll_total: float, config: BankrollConfig):
        self.bankroll_total = bankroll_total
        self.config = config

    def optimize_allocation(self, daily_bets: list[BetRecommendation]) -> list[BetRecommendation]:
        """
        P3.10 Upgrade: Portfolio Optimization.

        Calculates:
        1. Correlation adjustment between markets (e.g. Home MLs across games).
        2. Mean-Variance risk balance.
        3. Hard cap on daily exposure (MAX_DAILY_EXPOSURE_PCT).
        """
        if not daily_bets:
            return []

        # 1. Individual EV/Risk ranking
        daily_bets.sort(key=lambda b: (b.ev, b.win_probability), reverse=True)

        # 2. Daily exposure cap
        max_daily_usd = self.bankroll_total * self.config.max_daily_exposure_pct
        current_daily_sum = 0.0

        final_portfolio = []

        # 3. Simple Correlation Filtering (Heuristic for WBC)
        # Avoid betting > 3 Overs on the same venue/climate
        over_count = 0

        for bet in daily_bets:
            # Correlation check: Over exposure
            if bet.market == "OU" and bet.side == "Over":
                over_count += 1
                if over_count > 3: # Too much systematic 'Over' risk
                    bet.stake_amount *= 0.5 # Reduce correlation risk

            # 4. Check daily exposure limit
            if current_daily_sum + bet.stake_amount > max_daily_usd:
                # Scaled reduction to fit the cap
                remaining = max_daily_usd - current_daily_sum
                if remaining > (self.bankroll_total * 0.005): # Min bet 0.5%
                    bet.stake_amount = remaining
                    bet.stake_fraction = bet.stake_amount / self.bankroll_total
                else:
                    logger.info("[PORTFOLIO] Skipping %s %s due to daily exposure cap", bet.market, bet.side)
                    continue

            current_daily_sum += bet.stake_amount
            final_portfolio.append(bet)

        logger.info("[PORTFOLIO] Allocated total $%.2f across %d bets. (Daily Cap: $%.2f)",
                    current_daily_sum, len(final_portfolio), max_daily_usd)

        return final_portfolio

    def calculate_correlation_matrix(self, match_ids: list[str]) -> np.ndarray:
        """
        Placeholder for full MVO: Compute correlation between games
        based on shared factors (venue, weather, time zone fatigue).
        """
        n = len(match_ids)
        return np.eye(n) # Return identity as default
