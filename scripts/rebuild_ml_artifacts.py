#!/usr/bin/env python3
"""
ML Artifact 統一重建腳本
========================
每次修改以下任一文件後，必須重跑此腳本讓 deployment gate 讀到新值：

  - wbc_backend/optimization/walkforward.py   (BacktestSummary / 回測邏輯)
  - wbc_backend/optimization/tuning.py        (compare_calibration_methods)
  - wbc_backend/optimization/modeling.py      (特徵 / 模型)
  - data/mlb_2025/mlb_odds_2025_real.csv      (歷史資料更新)

輸出：
  data/wbc_backend/walkforward_summary.json   ← gate 讀 brier / ece / games
  data/wbc_backend/calibration_compare.json   ← gate 讀 ml_roi / ece（per method）
  data/wbc_backend/model_artifacts.json       ← 備用 artifact 紀錄

使用方式：
  python scripts/rebuild_ml_artifacts.py
  python scripts/rebuild_ml_artifacts.py --data data/mlb_2025/mlb_odds_2025_real.csv
  python scripts/rebuild_ml_artifacts.py --verify-gate   # 重建後直接驗證 gate

排程整合：
  由 wbc_backend/scheduler/jobs.py artifact_rebuild 任務每週觸發，
  或在 git hook post-merge 中呼叫（若 walkforward.py 有異動）。
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wbc_backend.optimization.walkforward import run_walkforward_backtest
from wbc_backend.optimization.tuning import compare_calibration_methods

logger = logging.getLogger(__name__)

_DEFAULT_DATA_PATH = "data/mlb_2025/mlb_odds_2025_real.csv"
_OUT_DIR = Path("data/wbc_backend")
_REQUIRED_FIELDS = {"brier", "ece", "games", "ml_roi"}


def rebuild_walkforward(data_path: str) -> dict:
    logger.info("⏳ 重建 walkforward_summary.json …")
    summary, artifacts = run_walkforward_backtest(
        path=data_path,
        min_train_games=240,
        retrain_every=40,
        ev_threshold=0.02,
    )
    payload = asdict(summary)
    out = _OUT_DIR / "walkforward_summary.json"
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (_OUT_DIR / "model_artifacts.json").write_text(
        json.dumps(artifacts, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(
        "✅ walkforward_summary.json  games=%d  brier=%.4f  ece=%.4f  ml_roi=%+.4f",
        payload["games"], payload["brier"], payload["ece"], payload["ml_roi"],
    )
    return payload


def rebuild_calibration(data_path: str) -> dict:
    logger.info("⏳ 重建 calibration_compare.json …")
    cmp = compare_calibration_methods(data_path)
    out = _OUT_DIR / "calibration_compare.json"
    out.write_text(json.dumps(cmp, indent=2, ensure_ascii=False), encoding="utf-8")
    for method, payload in cmp.items():
        s = payload.get("summary", {})
        logger.info(
            "✅ calibration[%s]  ece=%.4f  brier=%.4f  ml_roi=%+.4f",
            method, s.get("ece", float("nan")), s.get("brier", float("nan")), s.get("ml_roi", float("nan")),
        )
    return cmp


def verify_artifacts(wf: dict, cal: dict) -> bool:
    """確認兩份 artifact 都有必要欄位（ece 尤其關鍵）。"""
    ok = True
    # walkforward
    missing_wf = _REQUIRED_FIELDS - {"ml_roi"} - set(wf.keys())  # wf 用 ml_roi 不同鍵
    # calibration
    for method, payload in cal.items():
        s = payload.get("summary", {})
        missing_cal = _REQUIRED_FIELDS - set(s.keys())
        if missing_cal:
            logger.error("❌ calibration[%s] 缺少欄位：%s", method, missing_cal)
            ok = False
    if "ece" not in wf:
        logger.error("❌ walkforward_summary.json 缺少 ece 欄位")
        ok = False
    return ok


def run_gate_check() -> bool:
    """重建完成後立即驗證 deployment gate。"""
    from wbc_backend.config.settings import AppConfig, DataSourceConfig, DeploymentGateConfig
    from wbc_backend.pipeline.deployment_gate import evaluate_deployment_gate

    sources = DataSourceConfig(
        model_artifacts_dir=str(_OUT_DIR / "artifacts"),
        walkforward_summary_json=str(_OUT_DIR / "walkforward_summary.json"),
        calibration_compare_json=str(_OUT_DIR / "calibration_compare.json"),
        prediction_registry_jsonl=str(_OUT_DIR / "reports/prediction_registry.jsonl"),
    )
    gate_cfg = DeploymentGateConfig(
        enabled=True,
        min_walkforward_games=500,
        max_walkforward_brier=0.255,
        min_best_calibration_ml_roi=0.0,
        max_calibration_ece=0.12,
        require_artifact_schema_match=False,
    )
    config = AppConfig(sources=sources, deployment_gate=gate_cfg)
    report = evaluate_deployment_gate(config)

    print(f"\n{'='*55}")
    print(f"  Deployment Gate: {report.status}  ({report.selected_calibration})")
    print(f"{'='*55}")
    for check in report.checks:
        icon = "✅" if check.passed else "❌"
        print(f"  {icon} [{check.name}]")
        print(f"      {check.details}")
    print(f"{'='*55}\n")
    return report.status == "READY"


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = argparse.ArgumentParser(description="ML artifact 統一重建")
    parser.add_argument("--data", default=_DEFAULT_DATA_PATH, help="MLB 歷史賠率 CSV 路徑")
    parser.add_argument("--verify-gate", action="store_true", help="重建後執行 deployment gate 驗證")
    parser.add_argument("--skip-calibration", action="store_true", help="僅重建 walkforward（略過 calibration）")
    args = parser.parse_args()

    if not Path(args.data).exists():
        logger.error("資料文件不存在：%s", args.data)
        return 1

    _OUT_DIR.mkdir(parents=True, exist_ok=True)

    wf = rebuild_walkforward(args.data)
    cal: dict = {}
    if not args.skip_calibration:
        cal = rebuild_calibration(args.data)
    else:
        existing = _OUT_DIR / "calibration_compare.json"
        if existing.exists():
            cal = json.loads(existing.read_text(encoding="utf-8"))

    if not verify_artifacts(wf, cal):
        logger.error("Artifact 驗證失敗，請檢查以上錯誤")
        return 1

    logger.info("🎉 Artifact 重建完成，所有必要欄位已就位")

    if args.verify_gate:
        gate_ok = run_gate_check()
        return 0 if gate_ok else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
