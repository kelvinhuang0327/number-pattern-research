from __future__ import annotations

import json
from pathlib import Path

from wbc_backend.optimization.tuning import compare_calibration_methods, optimize_with_optuna


def main() -> None:
    data_path = "data/mlb_2025/mlb_odds_2025_real.csv"
    out_dir = Path("data/wbc_backend")
    out_dir.mkdir(parents=True, exist_ok=True)

    calibration_cmp = compare_calibration_methods(data_path)
    (out_dir / "calibration_compare.json").write_text(
        json.dumps(calibration_cmp, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Calibration comparison written.")

    try:
        result = optimize_with_optuna(data_path, n_trials=20)
    except RuntimeError as err:
        print(str(err))
        return

    (out_dir / "optuna_pareto.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Optuna pareto front written.")


if __name__ == "__main__":
    main()
