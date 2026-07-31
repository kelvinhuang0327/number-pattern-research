#!/usr/bin/env python3
"""
P207-A CLI — 執行本機 MLB 重訓 + 預測 scorecard 並寫出報告。

用法（自 repo 根目錄）：
    python3 scripts/run_mlb_local_retrain_scorecard.py

僅讀取 repo 內 tracked 本機檔案，無網路、無 live provider、無官方 deadline 查詢、
無 DB / registry / production 變更、無發布。純本機歷史描述性回測。

輸出（report/ 下 5 檔）：
    p207a_local_retrain_scorecard.md
    p207a_local_retrain_scorecard.json
    p207a_local_retrain_predictions.csv
    p207a_local_retrain_model_comparison.csv
    p207a_local_retrain_data_inventory.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.local_retrain_scorecard import (  # noqa: E402
    run_scorecard,
    write_reports,
)

DATA_DIR = ROOT / "data" / "mlb_2025"
WARMUP = DATA_DIR / "mlb-2024-asplayed.csv"          # 前一季，Elo 暖身（含 home_win）
EVAL = DATA_DIR / "mlb_odds_2025_real.csv"           # 本季，tracked：比分→賽果 + ML→市場參考
OUT_DIR = ROOT / "report"


def main() -> int:
    missing = [p for p in (WARMUP, EVAL) if not p.exists()]
    if missing:
        print("P207A_BLOCKED_NO_LOCAL_DATA: missing tracked input(s):", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 2

    result = run_scorecard(WARMUP, EVAL)
    written = write_reports(result, OUT_DIR)

    sp = result.split
    print("=" * 76)
    print("P207-A LOCAL MLB RETRAIN + PREDICTION SCORECARD  (local historical backtest only)")
    print("=" * 76)
    print(f"warmup(Elo seed): {result.warmup_rows}   eval universe: {result.eval_rows}")
    print(f"TRAIN {sp['train_period'][0]}→{sp['train_period'][1]} ({sp['train_rows']})   "
          f"TEST {sp['test_period'][0]}→{sp['test_period'][1]} ({sp['test_rows']})")
    print(f"train home-win prior={result.train_home_win_prior:.4f}   "
          f"Platt A={result.platt['A']:.4f} B={result.platt['B']:.4f}")
    print(f"odds_metrics_status={result.odds_metrics_status}   "
          f"outcome_metrics_status={result.outcome_metrics_status}")
    print("-" * 76)
    hdr = f"{'model':<34}{'acc':>8}{'logloss':>9}{'brier':>8}{'ECE':>8}{'cov':>6}"
    print(hdr)
    print("-" * len(hdr))
    for m in result.comparison:
        print(f"{m['model_name']:<34}{m['accuracy']:>8.4f}{m['log_loss']:>9.4f}"
              f"{m['brier_score']:>8.4f}{m['calibration_error']:>8.4f}{m['coverage']:>6.2f}")
    if result.market_reference:
        mr = result.market_reference
        print(f"{mr['model_name']:<34}{mr['accuracy']:>8.4f}{mr['log_loss']:>9.4f}"
              f"{mr['brier_score']:>8.4f}{mr['calibration_error']:>8.4f}{mr['coverage']:>6.2f}")
    print("-" * len(hdr))
    print(f"BEST(Brier)={result.best_by_brier}")
    print(f"confidence bands(best): {result.confidence_band_breakdown}")
    print(f"selected_side(best): {result.selected_side_distribution}")
    print("-" * 76)
    print(f"wrote {len(written)} report files → {OUT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
