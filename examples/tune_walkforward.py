from __future__ import annotations

import itertools
import json
from dataclasses import asdict

from wbc_backend.optimization.walkforward import run_walkforward_backtest


DATA = "data/mlb_2025/mlb_odds_2025_real.csv"


def score(summary: dict) -> float:
    # prioritize positive ROI and calibration quality
    return summary["ml_roi"] * 100.0 - summary["brier"] * 10.0 + summary["ml_hit_rate"] * 2.0


def main() -> None:
    best = None
    all_rows = []

    for lookback, retrain_every, ev_threshold, min_confidence in itertools.product(
        [8, 12, 15, 20],
        [20, 40, 60],
        [0.015, 0.02, 0.03, 0.04],
        [0.00, 0.03, 0.05, 0.07],
    ):
        summary, artifacts = run_walkforward_backtest(
            path=DATA,
            min_train_games=240,
            retrain_every=retrain_every,
            ev_threshold=ev_threshold,
            lookback=lookback,
            min_confidence=min_confidence,
            markets=("ML",),
        )
        payload = asdict(summary)
        payload.update(artifacts["params"])
        payload["score"] = score(payload)
        all_rows.append(payload)

        if best is None or payload["score"] > best["score"]:
            best = payload

    all_rows = sorted(all_rows, key=lambda x: x["score"], reverse=True)
    top10 = all_rows[:10]

    with open("data/wbc_backend/tune_results_top10.json", "w", encoding="utf-8") as f:
        json.dump(top10, f, ensure_ascii=False, indent=2)

    print("Best config:")
    print(json.dumps(best, indent=2))
    print("Saved top 10: data/wbc_backend/tune_results_top10.json")


if __name__ == "__main__":
    main()
