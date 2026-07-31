from __future__ import annotations

from dataclasses import dataclass

from wbc_backend.domain.schemas import BetRecommendation


@dataclass
class BacktestResult:
    total_bets: int
    avg_ev: float


def run_backtest(recommendations: list[BetRecommendation]) -> BacktestResult:
    if not recommendations:
        return BacktestResult(total_bets=0, avg_ev=0.0)
    avg_ev = sum(b.ev for b in recommendations) / len(recommendations)
    return BacktestResult(total_bets=len(recommendations), avg_ev=round(avg_ev, 4))
