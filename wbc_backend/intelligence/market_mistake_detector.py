"""
Market Mistake Detector — § 九 市場錯誤與仲裁偵測系統
==========================================
偵測盤口輸入錯誤 (Typo)、延遲 (Stale Line) 與 無風險套利 (Arbitrage) 機會。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from wbc_backend.domain.schemas import OddsLine

logger = logging.getLogger(__name__)

@dataclass
class MarketAnomaly:
    game_id: str
    anomaly_type: str        # TYPO | STALE | ARBITRAGE
    market: str
    side: str
    odds: float
    consensus_odds: float
    expected_gain: float
    urgency: int             # 1-10 (10 = highest)

class MarketMistakeDetector:
    """
    Scans real-time odds to find non-predictive Alpha (market errors).
    """
    def __init__(self, stale_threshold: float = 0.12, typo_threshold: float = 0.25):
        self.stale_threshold = stale_threshold
        self.typo_threshold = typo_threshold
        self.anomalies: list[MarketAnomaly] = []

    def scan_for_typos(self, game_id: str, odds: list[OddsLine], market_consensus: dict[str, float]) -> list[MarketAnomaly]:
        """
        Detects massive deviations from consensus (potential bookie typo).
        """
        found = []
        for o in odds:
            key = f"{o.market}_{o.side}"
            if key not in market_consensus:
                continue

            consensus = market_consensus[key]
            deviation = abs(o.decimal_odds - consensus) / consensus

            if deviation >= self.typo_threshold:
                anomaly = MarketAnomaly(
                    game_id=game_id,
                    anomaly_type="TYPO",
                    market=o.market, side=o.side,
                    odds=o.decimal_odds, consensus_odds=consensus,
                    expected_gain=deviation, urgency=10
                )
                found.append(anomaly)
                logger.warning("[MARKET MISTAKE] Potential TYPO detected: %s %s @ %.2f (Consensus %.2f)",
                               o.market, o.side, o.decimal_odds, consensus)
        return found

    def detect_arbitrage(self, game_id: str, odds: list[OddsLine]) -> list[MarketAnomaly]:
        """
        Checks if a risk-free profit exists across different books.
        Sum (1/Odds_i) < 1.0
        """
        # Group by market
        markets = {}
        for o in odds:
            m_key = o.market
            if m_key not in markets:
                markets[m_key] = {}
            if o.side not in markets[m_key]:
                markets[m_key][o.side] = []
            markets[m_key][o.side].append(o.decimal_odds)

        found = []
        for m, sides in markets.items():
            if len(sides) < 2:
                continue # Need at least 2 sides (e.g. Home vs Away)

            # Find best odds for each side
            best_odds = {side: max(prices) for side, prices in sides.items()}
            if len(best_odds) < 2:
                continue

            # Simple 2-way arbitrage calculation
            inv_sum = sum(1.0 / p for p in best_odds.values())

            if inv_sum < 0.98: # Margin of 2% profit
                gain = (1.0 / inv_sum) - 1.0
                anomaly = MarketAnomaly(
                    game_id=game_id,
                    anomaly_type="ARBITRAGE",
                    market=m, side="MULTIPLE",
                    odds=0.0, consensus_odds=0.0,
                    expected_gain=gain, urgency=9
                )
                found.append(anomaly)
                logger.info("[MARKET MISTAKE] ARBITRAGE found in %s! Expected ROI: %.1f%%", m, gain * 100)

        return found

    def detect_stale_tsl(self, tsl_odds: list[OddsLine], sharp_odds: list[OddsLine]) -> list[MarketAnomaly]:
        """
        Detects if TSL is laggy compared to the sharpest market (e.g. Pinnacle).
        """
        found = []
        for t in tsl_odds:
            for s in sharp_odds:
                if (t.market == s.market and t.side == s.side
                        and t.decimal_odds > s.decimal_odds * (1.0 + self.stale_threshold)):
                    found.append(MarketAnomaly(
                            game_id="live",
                            anomaly_type="STALE_TSL",
                            market=t.market, side=t.side,
                            odds=t.decimal_odds, consensus_odds=s.decimal_odds,
                            expected_gain=(t.decimal_odds/s.decimal_odds - 1),
                            urgency=8
                        ))
        return found
