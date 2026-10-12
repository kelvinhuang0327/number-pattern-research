from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from wbc_backend.optimization.walkforward import run_walkforward_backtest


def run_market(market: str) -> dict:
    summary, _ = run_walkforward_backtest(
        path="data/mlb_2025/mlb_odds_2025_real.csv",
        min_train_games=240,
        retrain_every=40,
        ev_threshold=0.03,
        lookback=12,
        min_confidence=0.0,
        markets=(market,),
    )
    return asdict(summary)


def main() -> None:
    payload = {
        "ML": run_market("ML"),
        "RL": run_market("RL"),
        "OU": run_market("OU"),
    }
    out = Path("data/wbc_backend/market_validation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
