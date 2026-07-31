from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from wbc_backend.optimization.walkforward import run_walkforward_backtest


def main() -> None:
    data_path = "data/mlb_2025/mlb_odds_2025_real.csv"
    summary, artifacts = run_walkforward_backtest(
        path=data_path,
        min_train_games=240,
        retrain_every=40,
        ev_threshold=0.02,
    )

    out_dir = Path("data/wbc_backend")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_path = out_dir / "walkforward_summary.json"
    artifact_path = out_dir / "model_artifacts.json"

    summary_payload = asdict(summary)
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    artifact_path.write_text(json.dumps(artifacts, indent=2), encoding="utf-8")

    print("Walk-forward backtest complete")
    print(json.dumps(summary_payload, indent=2))
    print(f"Saved: {summary_path}")
    print(f"Saved: {artifact_path}")


if __name__ == "__main__":
    main()
