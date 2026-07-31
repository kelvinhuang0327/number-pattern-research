"""
Closing Line Prediction Model — § 四 CLV Alpha 預測器
==========================================
預測比賽閉盤時的最終賠率。這是判斷當前賠率是否具有長期獲利價值 (CLV) 的核心組件。
"""
from __future__ import annotations

import logging
from pathlib import Path


from wbc_backend.config.settings import ModelConfig

logger = logging.getLogger(__name__)

class ClosingLineModel:
    """
    Predicts the expected closing price (fair market price)
    by analyzing current line movement and sharp indicators.
    """
    def __init__(self, config: ModelConfig | None = None):
        self.config = config or ModelConfig()
        self.artifact_path = Path("data/wbc_backend/artifacts/clv_model.pkl")
        self.model = None

    def predict_closing_odds(
        self,
        current_odds: float,
        time_to_start_hours: float,
        steam_signal_count: int,
        market_consensus_odds: float,
        sharp_momentum: float = 0.0,
    ) -> float:
        """
        Estimate the closing decimal odds.

        Alpha Logic:
        - If steam signals are high (e.g. Sharp money coming in),
          the line is likely to move further in that direction.
        - As time approaches start, the current market consensus
          becomes a stronger prior for the closing price.
        """
        # Feature vector for professional estimation
        # In production, this is a regression model.
        # Here we implement the institutional alpha logic:

        bias = 0.0
        # Steam signals strongly pull the closing line
        if steam_signal_count >= 2:
            bias -= 0.05 * steam_signal_count # Expect odds to drop (favoured by sharps)
        elif steam_signal_count <= -2:
            bias += 0.05 * abs(steam_signal_count) # Expect odds to rise

        # Consensus pull: Market tends towards the sharpest books (e.g. Pinnacle)
        consensus_drift = (market_consensus_odds - current_odds) * 0.4

        # Time decay impact on drift
        time_weight = max(0.2, 1.0 - time_to_start_hours / 24.0)

        expected_closing = current_odds + (bias + consensus_drift) * time_weight

        # Risk floor/ceiling
        expected_closing = max(1.01, min(20.0, expected_closing))

        return round(expected_closing, 3)

    def assess_clv_opportunity(
        self,
        current_odds: float,
        predicted_closing: float,
        threshold: float = 0.02
    ) -> bool:
        """
        Decision Logic:
        Only bet if current odds are significantly HIGHER than predicted closing odds.
        (i.e. we are getting better value NOW than we will at the start).
        """
        clv_edge = (current_odds / predicted_closing) - 1.0
        return clv_edge >= threshold

    def get_market_efficiency_score(
        self,
        bookie_variance: float,
        liquidity_depth: float = 1.0,
    ) -> float:
        """
        P1.5: Market Efficiency Scorer.
        Returns a score (0-1).
        1.0 = High efficiency (Hard to beat), 0.0 = Low efficiency (More errors).
        """
        # Low variance among books + high liquidity = high efficiency
        efficiency = (1.0 - min(0.5, bookie_variance * 5)) * 0.7 + (liquidity_depth * 0.3)
        return min(1.0, max(0.0, efficiency))
