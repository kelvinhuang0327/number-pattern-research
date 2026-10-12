#!/usr/bin/env python3
"""
P226-A CLI — 執行 run line / total 機率模型 + paper 回測並寫出報告。

用法（自 repo 根目錄）：
    python3 scripts/run_mlb_run_line_total_scorecard.py

僅讀取 repo 內 tracked 本機檔案，無網路、無 live provider、無 DB / registry /
production 變更、無發布。純本機歷史描述性回測。

輸出（report/ 下 5 檔）：
    p226a_run_line_total_scorecard.md
    p226a_run_line_total_scorecard.json
    p226a_run_line_total_predictions.csv
    p226a_run_line_total_model_comparison.csv
    p226a_run_line_total_data_inventory.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.run_line_total_scorecard import (  # noqa: E402
    run_scorecard,
    write_reports,
)

DATA_DIR = ROOT / "data" / "mlb_2025"
WARMUP = DATA_DIR / "mlb-2024-asplayed.csv"          # 前一季，球隊得失分率暖身
EVAL = DATA_DIR / "mlb_odds_2025_real.csv"           # 本季：比分 + RL/O-U 同列
OUT_DIR = ROOT / "report"


def main() -> int:
    missing = [p for p in (WARMUP, EVAL) if not p.exists()]
    if missing:
        print("P226A_BLOCKED_NO_LOCAL_DATA: missing tracked input(s):", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 2

    result = run_scorecard(WARMUP, EVAL)
    written = write_reports(result, OUT_DIR)

    sp = result.split
    print("=" * 84)
    print("P226-A RUN LINE / TOTAL PROBABILITY MODEL + PAPER BACKTEST  (local historical backtest only)")
    print("=" * 84)
    print(f"warmup(rate seed): {result.warmup_rows}   eval universe: {result.eval_rows}")
    print(f"TRAIN {sp['train_period'][0]}→{sp['train_period'][1]} ({sp['train_rows']})   "
          f"TEST {sp['test_period'][0]}→{sp['test_period'][1]} ({sp['test_rows']})")
    print(f"home_adv={result.home_adv:.4f}")
    print("-" * 84)
    for market in ("run_line", "total"):
        label = "RUN LINE" if market == "run_line" else "TOTAL"
        print(f"[{label}]")
        hdr = f"{'model':<34}{'dec':>6}{'push':>6}{'acc':>8}{'brier':>8}{'ECE':>8}{'roi':>8}"
        print(hdr)
        print("-" * len(hdr))
        for m in result.market_comparison[market]:
            print(f"{m['model_name']:<34}{m['decided_count']:>6}{m['push_count']:>6}"
                  f"{m['accuracy']:>8.4f}{m['brier_score']:>8.4f}{m['calibration_error']:>8.4f}"
                  f"{(m['paper_roi'] if m['paper_roi'] is not None else 0.0):>8.4f}")
        ref = result.market_reference[market]
        if ref:
            print(f"{ref['model_name']:<34}{ref['decided_count']:>6}{ref['push_count']:>6}"
                  f"{ref['accuracy']:>8.4f}{ref['brier_score']:>8.4f}{ref['calibration_error']:>8.4f}"
                  f"{'—':>8}")
        print(f"BEST(Brier)={result.best_by_brier[market]}")
        print("-" * 84)
    print(f"wrote {len(written)} report files → {OUT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
