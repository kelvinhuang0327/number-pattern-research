#!/usr/bin/env python3
"""
MLB 2025 完整回測執行腳本 — Phase 7B
======================================
Usage:
    python scripts/run_mlb_backtest.py
    python scripts/run_mlb_backtest.py --windows 5 --gen 20
    python scripts/run_mlb_backtest.py --output report/custom_report.md

Output:
    - 終端機：回測摘要表格
    - Markdown 檔案：report/mlb_2025_full_backtest.md
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

# ── 設定路徑 ──────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_DEFAULT_OUTPUT = os.path.join(_ROOT, "report", "mlb_2025_full_backtest.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MLB 2025 Walk-Forward 回測")
    parser.add_argument(
        "--windows", type=int, default=5,
        help="Walk-Forward 視窗數（預設 5）",
    )
    parser.add_argument(
        "--gen", type=int, default=15,
        help="每個視窗的 MARL 演化代數（預設 15）",
    )
    parser.add_argument(
        "--output", type=str, default=_DEFAULT_OUTPUT,
        help=f"Markdown 輸出路徑（預設 {_DEFAULT_OUTPUT}）",
    )
    parser.add_argument(
        "--no-save", action="store_true",
        help="不寫入 Markdown 檔案，僅輸出到終端機",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = None if args.no_save else args.output

    logger.info("=" * 60)
    logger.info("MLB 2025 完整回測 — 啟動")
    logger.info(f"  Walk-Forward 視窗數：{args.windows}")
    logger.info(f"  MARL 演化代數：    {args.gen}")
    logger.info(f"  輸出路徑：          {output_path or '（不儲存）'}")
    logger.info("=" * 60)

    t0 = time.time()

    # ── 載入資料 ─────────────────────────────────────────────────────────────
    logger.info("步驟 1/3：載入 MLB 2025 真實賽事資料...")
    try:
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records()
        logger.info(f"  ✅ 載入完成：{len(records):,} 筆記錄")
    except Exception as e:
        logger.error(f"  ❌ 資料載入失敗：{e}")
        sys.exit(1)

    # ── 執行回測 ─────────────────────────────────────────────────────────────
    logger.info("步驟 2/3：執行 Walk-Forward 回測...")
    try:
        from wbc_backend.evaluation.full_backtest import FullBacktestEngine, generate_markdown_report
        engine = FullBacktestEngine(
            n_windows=args.windows,
            marl_n_generations=args.gen,
        )
        report = engine.run(records)
        elapsed = time.time() - t0
        logger.info(f"  ✅ 回測完成（{elapsed:.1f} 秒）")
    except Exception as e:
        logger.error(f"  ❌ 回測失敗：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # ── 輸出報告 ─────────────────────────────────────────────────────────────
    logger.info("步驟 3/3：生成回測報告...")
    md_text = generate_markdown_report(report)

    if output_path:
        import pathlib
        pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(output_path).write_text(md_text, encoding="utf-8")
        logger.info(f"  ✅ Markdown 報告已儲存 → {output_path}")

    # ── 終端機摘要 ───────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("⚾  MLB 2025 Walk-Forward 回測結果")
    print("=" * 60)
    print(f"  總場數：      {report.n_games_total:,} 場")
    print(f"  日期範圍：    {report.date_range}")
    print(f"  整體準確率：  {report.accuracy:.1%}")
    print(f"  Brier Score：{report.brier_score:.4f}  |  市場基準：{report.market_brier_score:.4f}")
    print(f"  Brier Skill：{report.brier_skill_score:+.1%}")
    print(f"  Log Loss：   {report.log_loss:.4f}")
    print(f"  校準誤差：   {report.calibration_ece:.4f}")
    print("-" * 60)
    print(f"  總 ROI：      {report.roi:+.1%}  CI: [{report.roi_ci_95[0]:+.1%}, {report.roi_ci_95[1]:+.1%}]")
    print(f"  Sharpe Ratio：{report.sharpe_ratio:.2f}")
    print(f"  最大回撤：    {report.max_drawdown:.1%}")
    print(f"  下注場數：    {report.n_bets_total:,}")
    print(f"  下注勝率：    {report.n_bets_won / max(report.n_bets_total, 1):.1%}")
    print(f"  最終資金：    {report.final_bankroll:.4f}（初始 1.0000）")
    print(f"  p-value：     {report.p_value_vs_random:.4f}")
    print("=" * 60)

    # 判定
    print()
    if report.p_value_vs_random < 0.05 and report.brier_skill_score > 0:
        print("✅ 結論：模型預測顯著優於市場，具備實戰參考價值")
    elif report.accuracy > 0.535:
        print("⚠️  結論：準確率尚可，建議繼續優化特徵工程")
    else:
        print("❌ 結論：模型未達統計顯著性，仍在市場效率範圍內")
    print()
    print(f"⏱  總耗時：{time.time() - t0:.1f} 秒")

    if output_path:
        print(f"📄 完整報告：{output_path}")
    print()


if __name__ == "__main__":
    main()
