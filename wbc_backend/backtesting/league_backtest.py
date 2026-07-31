from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from league_adapters.registry import get_league_adapter
from baseball_scenario_engine.runner import ScenarioRequest, ScenarioRunner


@dataclass(frozen=True)
class BacktestConfig:
    league: str
    min_sample_size: int = 50
    kelly_fraction: float = 1 / 6
    max_single_bet_pct: float = 0.015


@dataclass
class BacktestResult:
    league: str
    n_games: int
    roi: float
    brier: float
    logloss: float
    clv: float
    drawdown: float
    notes: list[str] = field(default_factory=list)


class LeagueBacktestEngine:
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.adapter = get_league_adapter(config.league)
        self.scenario_runner = ScenarioRunner()

    def validate_records(self, records: list[Any]) -> None:
        if len(records) < self.config.min_sample_size:
            raise ValueError(f"Need at least {self.config.min_sample_size} records, got {len(records)}")
        missing = []
        for record in records:
            for field in ("game_id", "home_team", "away_team"):
                if getattr(record, field, None) in (None, ""):
                    missing.append((getattr(record, "game_id", "?"), field))
        if missing:
            raise ValueError(f"Missing required backtest fields: {missing[:5]}")

    def run(
        self,
        records: list[Any],
        predict_fn: Callable[[Any], dict[str, float]],
    ) -> BacktestResult:
        self.validate_records(records)
        briers: list[float] = []
        loglosses: list[float] = []
        pnls: list[float] = []
        clvs: list[float] = []
        bankroll = 1.0
        peak = 1.0

        for record in records:
            base_probs = predict_fn(record)
            req = ScenarioRequest(
                league=self.config.league,
                game_id=getattr(record, "game_id"),
                home_team=getattr(record, "home_team"),
                away_team=getattr(record, "away_team"),
                round_name=getattr(record, "round_name", ""),
                base_probs=base_probs,
                features=getattr(record, "features", {}) or {},
                context={
                    "weather": getattr(record, "weather", {}),
                    "odds": getattr(record, "odds", {}),
                    "pitchers": getattr(record, "pitchers", {}),
                    "lineups": getattr(record, "lineups", {}),
                    "bullpen_usage": getattr(record, "bullpen_usage", {}),
                },
            )
            scenario = self.scenario_runner.run(req)
            home_prob = float(scenario.adjustments.get("home_win_prob", base_probs.get("home_win_prob", 0.5)))
            actual = int(getattr(record, "actual_home_win", 0) or 0)
            briers.append((home_prob - actual) ** 2)
            home_prob = min(max(home_prob, 1e-6), 1 - 1e-6)
            loglosses.append(-(actual * np.log(home_prob) + (1 - actual) * np.log(1 - home_prob)))
            edge = home_prob - 0.5
            stake = min(self.config.max_single_bet_pct, abs(edge) * self.config.kelly_fraction)
            pnl = stake if (edge > 0 and actual == 1) or (edge <= 0 and actual == 0) else -stake
            bankroll += pnl
            peak = max(peak, bankroll)
            pnls.append(pnl)
            clvs.append(edge)

        roi = bankroll - 1.0
        drawdown = 0.0 if peak <= 0 else (peak - bankroll) / peak
        return BacktestResult(
            league=self.config.league,
            n_games=len(records),
            roi=float(roi),
            brier=float(np.mean(briers)) if briers else 0.0,
            logloss=float(np.mean(loglosses)) if loglosses else 0.0,
            clv=float(np.mean(clvs)) if clvs else 0.0,
            drawdown=float(drawdown),
            notes=[f"kelly_fraction={self.config.kelly_fraction}", f"max_single_bet_pct={self.config.max_single_bet_pct}"],
        )
