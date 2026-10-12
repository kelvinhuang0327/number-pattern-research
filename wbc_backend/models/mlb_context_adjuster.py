from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wbc_backend.mlb_data.schema import MLBGameData


@dataclass(frozen=True)
class MLBContextAdjuster:
    lineup_weight: float = 0.020
    bullpen_weight: float = 0.025
    weather_park_weight: float = 0.015
    injury_rest_weight: float = 0.020
    market_pressure_weight: float = 0.020

    def adjust_home_prob(self, base_home_prob: float, row: MLBGameData) -> float:
        f = row.features
        delta = 0.0

        # lineup delta: confirmed lineups give modest confidence bonus
        if f.confirmed_home_lineup.available and f.confirmed_away_lineup.available:
            delta += self.lineup_weight

        # bullpen fatigue delta: lower recent usage for home is positive
        if f.bullpen_usage_last_3d_home.available and f.bullpen_usage_last_3d_away.available:
            try:
                h_use = float(f.bullpen_usage_last_3d_home.value)
                a_use = float(f.bullpen_usage_last_3d_away.value)
                delta += np.clip((a_use - h_use) / 200.0, -1.0, 1.0) * self.bullpen_weight
            except Exception:
                pass

        # weather + park: explicit but conservative
        if f.weather.available and f.park_factors.available and f.wind.available:
            delta += self.weather_park_weight * 0.25

        # injury/rest delta
        ir = f.injury_rest
        if ir.injury_report.available and ir.rest_days_home.available and ir.rest_days_away.available:
            try:
                h_rest = float(ir.rest_days_home.value)
                a_rest = float(ir.rest_days_away.value)
                delta += np.clip((h_rest - a_rest) / 3.0, -1.0, 1.0) * self.injury_rest_weight
            except Exception:
                pass

        # odds open->close pressure
        odds = f.odds
        if odds.opening_home_ml.available and odds.closing_home_ml.available:
            try:
                open_home = float(odds.opening_home_ml.value)
                close_home = float(odds.closing_home_ml.value)
                move = np.sign(close_home - open_home)
                delta += move * self.market_pressure_weight
            except Exception:
                pass

        adjusted = float(np.clip(base_home_prob + delta, 0.03, 0.97))
        return adjusted
