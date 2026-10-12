#!/usr/bin/env python3
"""
P227-A CLI — 執行 Total over-dispersion 校準 paper-only MVP 並寫出報告。

用法（自 repo 根目錄）：
    python3 scripts/run_mlb_total_calibration_scorecard.py

僅讀取 repo 內 tracked 本機檔案，無網路、無 live provider、無 DB / registry /
production 變更、無發布。純本機歷史描述性回測；不修改 P226-A 檔案。

輸出（report/ 下 4 檔）：
    p227a_total_calibration_scorecard.md
    p227a_total_calibration_scorecard.json
    p227a_total_calibration_model_comparison.csv
    p227a_total_calibration_predictions.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.total_calibration_scorecard import (  # noqa: E402
    run_calibration_scorecard,
    write_reports,
)

DATA_DIR = ROOT / "data" / "mlb_2025"
WARMUP = DATA_DIR / "mlb-2024-asplayed.csv"
EVAL = DATA_DIR / "mlb_odds_2025_real.csv"
OUT_DIR = ROOT / "report"


def main() -> int:
    missing = [p for p in (WARMUP, EVAL) if not p.exists()]
    if missing:
        print("P227A_BLOCKED_NO_LOCAL_DATA: missing tracked input(s):", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 2

    result = run_calibration_scorecard(WARMUP, EVAL)
    written = write_reports(result, OUT_DIR)

    print("=" * 84)
    print("P227-A TOTAL OVER-DISPERSION CALIBRATION  (local historical paper-only backtest)")
    print("=" * 84)
    sp = result.gate0_split
    print(f"Gate0 TRAIN {sp['train_period'][0]}→{sp['train_period'][1]} ({sp['train_rows']})   "
          f"TEST {sp['test_period'][0]}→{sp['test_period'][1]} ({sp['test_rows']})")
    print(f"home_adv={result.gate0_home_adv:.4f}")
    print(f"phi_hat={result.phi_hat:.6f}   platt_a={result.platt_a:.6f}   platt_b={result.platt_b:.6f}")
    print("-" * 84)
    hdr = f"{'model':<34}{'dec':>6}{'push':>6}{'acc':>8}{'brier':>8}{'ECE':>8}"
    print(hdr)
    print("-" * len(hdr))
    for m in result.model_comparison:
        print(f"{m['model_name']:<34}{m['decided_count']:>6}{m['push_count']:>6}"
              f"{m['accuracy']:>8.4f}{m['brier_score']:>8.4f}{m['calibration_error']:>8.4f}")
    print("-" * 84)
    print(f"BEST(Brier)={result.best_by_brier}")
    print(f"beats_poisson_brier(0.2637)={result.beats_poisson_brier}")
    print(f"beats_coinflip_brier(0.2500)={result.beats_coinflip_brier}")
    print(f"wrote {len(written)} report files → {OUT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
