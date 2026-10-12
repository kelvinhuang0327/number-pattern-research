from __future__ import annotations

import pandas as pd


def run_f5_moneyline_validation(csv_path: str = "data/mlb_2025/mlb_odds_2025_real.csv") -> dict:
    df = pd.read_csv(csv_path, nrows=5)
    required = {"Home F5 Score", "Away F5 Score"}
    missing = sorted(required - set(df.columns))
    if missing:
        return {
            "model": "mlb_f5_moneyline",
            "status": "rejected",
            "reason": f"missing_required_labels:{','.join(missing)}",
            "n_games": 0,
            "roi": None,
            "brier": None,
            "logloss": None,
            "clv": None,
        }
    return {
        "model": "mlb_f5_moneyline",
        "status": "ready",
        "reason": "",
        "n_games": int(len(df)),
    }
