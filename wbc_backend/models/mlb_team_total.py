from __future__ import annotations

import pandas as pd


def run_team_total_validation(csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv") -> dict:
    df = pd.read_csv(csv_path, nrows=5)
    required = {"Home Team Total Line", "Away Team Total Line"}
    missing = sorted(required - set(df.columns))
    if missing:
        return {
            "model": "mlb_team_total",
            "status": "blocked",
            "reason": f"missing_required_market_lines:{','.join(missing)}",
            "n_games": 0,
            "roi": None,
            "brier": None,
            "logloss": None,
            "clv": None,
        }
    return {
        "model": "mlb_team_total",
        "status": "ready",
        "reason": "",
        "n_games": int(len(df)),
    }
