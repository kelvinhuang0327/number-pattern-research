#!/usr/bin/env python3
"""
P232-A CLI — 執行 2025 單一球季 Run Line 特徵消融 paper-only scorecard 並寫出報告。

用法（自 repo 根目錄）：
    python3 scripts/run_mlb_run_line_feature_ablation_scorecard.py

僅讀取 repo 內 tracked 本機檔案，無網路、無 live provider、無 DB / registry /
production 變更、無發布。純本機歷史描述性回測、單一球季（2025）；不修改
P226-A / P227-A / P228-A / P229-A / P230-A 檔案。

輸出（report/ 下 4 檔）：
    p232a_run_line_feature_ablation_scorecard.md
    p232a_run_line_feature_ablation_scorecard.json
    p232a_run_line_feature_ablation_comparison.csv
    p232a_run_line_feature_ablation_predictions.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wbc_backend.recommendation.run_line_feature_ablation_scorecard import (  # noqa: E402
    run_feature_ablation_scorecard,
    write_reports,
)

DATA_DIR = ROOT / "data" / "mlb_2025"
WARMUP = DATA_DIR / "mlb-2024-asplayed.csv"          # 前一季，球隊得失分率暖身（不計分）
EVAL = DATA_DIR / "mlb_odds_2025_real.csv"           # 2025 單一球季：比分 + RL 同列
OUT_DIR = ROOT / "report"


def main() -> int:
    missing = [p for p in (WARMUP, EVAL) if not p.exists()]
    if missing:
        print("P232A_BLOCKED_NO_LOCAL_DATA: missing tracked input(s):", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 2

    result = run_feature_ablation_scorecard(WARMUP, EVAL, strict_gate0=True)
    written = write_reports(result, OUT_DIR)

    print("=" * 84)
    print("P232-A 2025 SINGLE-SEASON RUN LINE FEATURE ABLATION  (local historical paper-only)")
    print("=" * 84)
    g0 = result.gate0
    print(f"Gate0 anchor train_frac={g0['anchor_train_frac']}   status={g0['status']}")
    print(f"  coinflip  : brier={g0['coinflip_brier']:.4f}")
    print(f"  full_model: acc={g0['poisson_accuracy']:.4f} brier={g0['poisson_brier']:.4f} "
          f"ece={g0['poisson_ece']:.4f}")
    if "calibrated_brier" in g0:
        print(f"  calibrated: brier={g0['calibrated_brier']:.4f}   status={g0['calibrated_status']}")
    print("-" * 84)
    hdr = f"{'variant':<28}{'frac':>6}{'dec':>6}{'acc':>8}{'brier':>8}{'d_brier':>10}{'beats':>7}"
    print(hdr)
    print("-" * len(hdr))
    for r in result.ablation_results:
        acc = f"{r.accuracy:.4f}" if r.accuracy is not None else "—"
        brier = f"{r.brier_score:.4f}" if r.brier_score is not None else "—"
        dbrier = f"{r.delta_brier_vs_full:+.4f}" if r.delta_brier_vs_full is not None else "—"
        beats = "YES" if r.beats_coinflip_brier else "no"
        print(f"{r.variant:<28}{r.train_frac:>6}{r.decided_count:>6}{acc:>8}{brier:>8}{dbrier:>10}{beats:>7}")
    print("-" * 84)
    interp = result.interpretation
    print(f"INTERPRETATION = {interp['label']}")
    print(f"  robust_variants={interp['robust_variants']}")
    print(f"  fragile_variants={interp['fragile_variants']}")
    print(f"wrote {len(written)} report files -> {OUT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
