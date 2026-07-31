#!/usr/bin/env python3
"""
P228-A CLI — 執行 Run Line 穩健性與 train-fold-only 校準 paper-only scorecard 並寫出報告。

用法（自 repo 根目錄）：
    python3 scripts/run_mlb_run_line_robustness_scorecard.py

僅讀取 repo 內 tracked 本機檔案，無網路、無 live provider、無 DB / registry /
production 變更、無發布。純本機歷史描述性回測；不修改 P226-A / P227-A 檔案。

輸出（report/ 下 4 檔）：
    p228a_run_line_robustness_scorecard.md
    p228a_run_line_robustness_scorecard.json
    p228a_run_line_robustness_splits.csv
    p228a_run_line_robustness_predictions.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.run_line_robustness_scorecard import (  # noqa: E402
    run_robustness_scorecard,
    write_reports,
)

DATA_DIR = ROOT / "data" / "mlb_2025"
WARMUP = DATA_DIR / "mlb-2024-asplayed.csv"
EVAL = DATA_DIR / "mlb_odds_2025_real.csv"
OUT_DIR = ROOT / "report"


def main() -> int:
    missing = [p for p in (WARMUP, EVAL) if not p.exists()]
    if missing:
        print("P228A_BLOCKED_NO_LOCAL_DATA: missing tracked input(s):", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 2

    result = run_robustness_scorecard(WARMUP, EVAL, strict_gate0=True)
    written = write_reports(result, OUT_DIR)

    print("=" * 84)
    print("P228-A RUN LINE ROBUSTNESS & CALIBRATION  (local historical paper-only backtest)")
    print("=" * 84)
    g0 = result.gate0
    print(f"Gate0 anchor train_frac={g0['anchor_train_frac']}   status={g0['status']}")
    print(f"  coinflip: acc={g0['coinflip_accuracy']:.4f} brier={g0['coinflip_brier']:.4f}")
    print(f"  poisson : acc={g0['poisson_accuracy']:.4f} brier={g0['poisson_brier']:.4f} "
          f"ece={g0['poisson_ece']:.4f}")
    print("-" * 84)
    print("[SPLIT GRID]")
    hdr = f"{'train_frac':>10}{'test_rows':>10}{'coinflip_brier':>16}{'poisson_brier':>16}{'beats':>8}"
    print(hdr)
    print("-" * len(hdr))
    for e in result.split_grid:
        print(f"{e.train_frac:>10}{e.test_rows:>10}{e.coinflip_brier:>16.4f}"
              f"{e.poisson_brier:>16.4f}{('YES' if e.poisson_beats_coinflip_brier else 'no'):>8}")
    print("-" * 84)
    print("[MONTHLY WINDOWS]")
    hdr2 = f"{'window':<10}{'status':>28}{'test_rows':>10}{'poisson_brier':>16}{'beats':>8}"
    print(hdr2)
    print("-" * len(hdr2))
    for w in result.monthly_windows:
        pb = f"{w.poisson_brier:.4f}" if w.poisson_brier is not None else "—"
        beats = ("YES" if w.poisson_beats_coinflip_brier else "no") \
            if w.poisson_beats_coinflip_brier is not None else "—"
        print(f"{w.window_id:<10}{w.status:>28}{w.test_rows:>10}{pb:>16}{beats:>8}")
    print("-" * 84)
    c = result.calibration
    print(f"[CALIBRATION] platt_a={c.platt_a:.6f} platt_b={c.platt_b:.6f}")
    print(f"  raw        : acc={c.raw['accuracy']:.4f} brier={c.raw['brier_score']:.4f} "
          f"ece={c.raw['calibration_error']:.4f}")
    print(f"  calibrated : acc={c.calibrated['accuracy']:.4f} brier={c.calibrated['brier_score']:.4f} "
          f"ece={c.calibrated['calibration_error']:.4f}")
    print(f"  beats_raw_brier={c.calibration_beats_raw_brier}  beats_raw_ece={c.calibration_beats_raw_ece}")
    print("-" * 84)
    print(f"ROBUSTNESS CONCLUSION = {result.conclusion['label']}")
    print(f"wrote {len(written)} report files → {OUT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
