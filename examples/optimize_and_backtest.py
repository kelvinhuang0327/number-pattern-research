from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from wbc_backend.optimization.walkforward import run_walkforward_backtest


def main() -> None:
    # Optimized robust setting from grid search on 2025 MLB final odds/results.
    summary, artifacts = run_walkforward_backtest(
        path="data/mlb_2025/mlb_odds_2025_real.csv",
        min_train_games=240,
        retrain_every=40,
        ev_threshold=0.03,
        lookback=12,
        min_confidence=0.0,
        markets=("ML",),
    )

    out_dir = Path("data/wbc_backend")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "walkforward_summary.json").write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "model_artifacts.json").write_text(
        json.dumps(artifacts, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Optimization + backtest complete")
    print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
