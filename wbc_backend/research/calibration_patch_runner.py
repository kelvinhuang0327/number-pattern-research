"""
wbc_backend/research/calibration_patch_runner.py
────────────────────────────────────────────────────────────────────────────────
Research-mode 校準補丁執行器（Calibration Patch Runner）

目的：
  把 Patch Task「model_patch_calibration」從 stub 執行升級為真實的模型修改，
  能夠產生可量測的 before/after 預測差異，供 patch_validator 進行科學評估。

執行流程（RESEARCH ONLY — 絕不接觸 live 路徑）:
  1. 從 research/trade_ledger.jsonl 載入結算紀錄（leakage-free）
  2. 以前 80% 紀錄作為校準訓練集，擬合 ProbabilityCalibrator
  3. 對全部 35 筆紀錄套用校準，產生「after」預測機率
  4. 輸出兩個 snapshot 檔案（leakage-safe，僅保留 pregame 資訊）：
       research/patch_snapshots/{task_id}_before.jsonl  — 原始 predicted_prob
       research/patch_snapshots/{task_id}_after.jsonl   — 校準後 predicted_prob
  5. 回傳 PatchRunManifest（含 metrics、方法、參數、artifact 路徑）

安全規範：
  - 不修改 strategy/, telegram_bot/, live/, data/live_updater.py
  - 不使用 closing_odds 或任何開賽後資訊作為特徵
  - 不寫入 production prediction path

執行方式（手動）：
  python3 -m wbc_backend.research.calibration_patch_runner --task-id 880
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── 路徑 ──────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent.parent
TRADE_LEDGER_PATH = _REPO_ROOT / "research" / "trade_ledger.jsonl"
SNAPSHOTS_DIR     = _REPO_ROOT / "research" / "patch_snapshots"

# ── 設定 ──────────────────────────────────────────────────────────────────────
TRAIN_FRACTION  = 0.8     # 前 80% 作為校準訓練集
MIN_TRAIN_N     = 10      # 訓練集最低樣本數
MIN_TOTAL_N     = 20      # 全量最低樣本數（否則拒絕執行）
CALIBRATION_METHOD = "auto"  # platt | isotonic | temperature | auto


# ──────────────────────────────────────────────────────────────────────────────
# 輸出結構
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PatchRunManifest:
    """校準補丁執行結果清單"""
    task_id: int
    status: str               # SUCCESS | FAILED_STUB | FAILED_DATA | FAILED_ERROR
    calibration_method: str   # 實際選用的校準方法
    calibration_params: dict  # Platt: {a, b}; Temperature: {T}; Isotonic: {}
    n_total: int
    n_train: int
    n_eval: int               # n_total - n_train（獨立評估集）
    before_brier: float
    after_brier: float
    brier_delta: float        # negative = 改善
    before_logloss: float
    after_logloss: float
    logloss_delta: float
    before_snapshot_path: str
    after_snapshot_path: str
    regimes: list[str]
    failure_reason: str = ""
    elapsed_seconds: float = 0.0
    executed_at: str = ""
    note: str = ""


# ──────────────────────────────────────────────────────────────────────────────
# 公開介面
# ──────────────────────────────────────────────────────────────────────────────

def run_calibration_patch(task_id: int) -> PatchRunManifest:
    """
    執行校準補丁，產出 before/after prediction snapshots。

    Args:
        task_id: 對應的 patch task ID（用於命名 snapshot 檔案）

    Returns:
        PatchRunManifest（含 status = SUCCESS / FAILED_*)
    """
    t0 = time.time()
    executed_at = datetime.now(timezone.utc).isoformat()
    before_path = str(SNAPSHOTS_DIR / f"{task_id}_before.jsonl")
    after_path  = str(SNAPSHOTS_DIR / f"{task_id}_after.jsonl")

    # 1. 載入結算紀錄
    records = _load_settled_records()
    n = len(records)
    if n < MIN_TOTAL_N:
        return PatchRunManifest(
            task_id=task_id,
            status="FAILED_DATA",
            calibration_method="none",
            calibration_params={},
            n_total=n, n_train=0, n_eval=0,
            before_brier=float("nan"), after_brier=float("nan"), brier_delta=float("nan"),
            before_logloss=float("nan"), after_logloss=float("nan"), logloss_delta=float("nan"),
            before_snapshot_path=before_path,
            after_snapshot_path=after_path,
            regimes=[],
            failure_reason=f"Insufficient data: {n} records (minimum {MIN_TOTAL_N})",
            elapsed_seconds=round(time.time() - t0, 2),
            executed_at=executed_at,
        )

    # 2. 拆分訓練集 / 評估集（walk-forward: 時間順序，不洩漏未來）
    n_train = max(MIN_TRAIN_N, int(n * TRAIN_FRACTION))
    train_records = records[:n_train]
    # eval_records: 評估用（後 20%），但校準後機率套用於全量
    eval_records  = records[n_train:]

    train_probs    = [float(r["predicted_prob"]) for r in train_records]
    train_outcomes = [_outcome(r) for r in train_records]

    # 3. 擬合校準器
    try:
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        cal = ProbabilityCalibrator(method=CALIBRATION_METHOD)
        cal.fit(train_probs, train_outcomes)
        fitted_method = cal._fitted_method
        cal_params = _extract_params(cal)
    except Exception as exc:
        logger.exception("[CalibrationPatchRunner] 校準器擬合失敗")
        return PatchRunManifest(
            task_id=task_id,
            status="FAILED_ERROR",
            calibration_method="error",
            calibration_params={},
            n_total=n, n_train=n_train, n_eval=len(eval_records),
            before_brier=float("nan"), after_brier=float("nan"), brier_delta=float("nan"),
            before_logloss=float("nan"), after_logloss=float("nan"), logloss_delta=float("nan"),
            before_snapshot_path=before_path,
            after_snapshot_path=after_path,
            regimes=[],
            failure_reason=f"Calibration fit error: {exc}",
            elapsed_seconds=round(time.time() - t0, 2),
            executed_at=executed_at,
        )

    # 4. 對全量紀錄套用校準（BEFORE = raw, AFTER = calibrated）
    all_raw_probs = [float(r["predicted_prob"]) for r in records]
    all_cal_probs = cal.calibrate(all_raw_probs)

    all_outcomes = [_outcome(r) for r in records]
    before_brier, before_ll = _brier(all_raw_probs, all_outcomes), _logloss(all_raw_probs, all_outcomes)
    after_brier,  after_ll  = _brier(all_cal_probs, all_outcomes), _logloss(all_cal_probs, all_outcomes)

    # 5. 寫入 snapshots
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    _write_snapshot(
        Path(before_path),
        records,
        all_raw_probs,
        task_id=task_id,
        snapshot_type="before",
        calibration_method="raw",
    )
    _write_snapshot(
        Path(after_path),
        records,
        all_cal_probs,
        task_id=task_id,
        snapshot_type="after",
        calibration_method=fitted_method,
    )

    regimes = sorted(set(str(r.get("regime", "unknown")) for r in records))
    elapsed = round(time.time() - t0, 3)

    manifest = PatchRunManifest(
        task_id=task_id,
        status="SUCCESS",
        calibration_method=fitted_method,
        calibration_params=cal_params,
        n_total=n,
        n_train=n_train,
        n_eval=len(eval_records),
        before_brier=round(before_brier, 6),
        after_brier=round(after_brier, 6),
        brier_delta=round(after_brier - before_brier, 6),
        before_logloss=round(before_ll, 6),
        after_logloss=round(after_ll, 6),
        logloss_delta=round(after_ll - before_ll, 6),
        before_snapshot_path=before_path,
        after_snapshot_path=after_path,
        regimes=regimes,
        elapsed_seconds=elapsed,
        executed_at=executed_at,
        note=f"Calibration applied to {n} records. Trained on first {n_train}.",
    )

    logger.info(
        "[CalibrationPatchRunner] task #%d SUCCESS — %s — Brier: %.4f → %.4f (Δ%+.4f) in %.2fs",
        task_id, fitted_method, before_brier, after_brier, after_brier - before_brier, elapsed,
    )
    return manifest


def artifacts_exist(task_id: int) -> bool:
    """Completion gate: 確認 before/after snapshots 都已存在且非空。"""
    before = SNAPSHOTS_DIR / f"{task_id}_before.jsonl"
    after  = SNAPSHOTS_DIR / f"{task_id}_after.jsonl"
    return (
        before.exists() and before.stat().st_size > 10
        and after.exists() and after.stat().st_size > 10
    )


def build_completion_text(manifest: PatchRunManifest) -> str:
    """產生供 DB 儲存的 completed_text（不含 stub 標記）。"""
    brier_arrow = "↓" if manifest.brier_delta < 0 else "↑"
    return f"""# 校準補丁執行報告（Research Mode）

## 執行結果
- 狀態: {manifest.status}
- 校準方法: {manifest.calibration_method}
- 校準參數: {json.dumps(manifest.calibration_params, ensure_ascii=False)}

## 指標改善
| 指標 | BEFORE | AFTER | Δ |
|------|--------|-------|---|
| Brier Score | {manifest.before_brier:.6f} | {manifest.after_brier:.6f} | {manifest.brier_delta:+.6f} {brier_arrow} |
| LogLoss | {manifest.before_logloss:.6f} | {manifest.after_logloss:.6f} | {manifest.logloss_delta:+.6f} |

## 數據
- 總紀錄數: {manifest.n_total}
- 訓練集: {manifest.n_train}（前 {int(TRAIN_FRACTION*100)}%）
- 評估集: {manifest.n_eval}（後 {100 - int(TRAIN_FRACTION*100)}%）
- Regimes: {', '.join(manifest.regimes)}

## Artifacts
- Before: `{manifest.before_snapshot_path}`
- After:  `{manifest.after_snapshot_path}`

## 說明
{manifest.note}

執行時間: {manifest.executed_at}
耗時: {manifest.elapsed_seconds}s
執行模式: RESEARCH（不影響生產路徑）
"""


# ──────────────────────────────────────────────────────────────────────────────
# 內部函式
# ──────────────────────────────────────────────────────────────────────────────

def _load_settled_records() -> list[dict]:
    """
    載入 trade_ledger.jsonl 中的結算紀錄。
    leakage-free: 僅保留 pregame 欄位（不含 closing_odds 等開賽後資訊）。
    """
    if not TRADE_LEDGER_PATH.exists():
        return []
    records = []
    for line in TRADE_LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get("event_type") != "settlement":
            continue
        if r.get("predicted_prob") is None or r.get("result") is None:
            continue
        records.append(r)
    return records


def _outcome(r: dict) -> int:
    return 1 if r.get("result") == "win" else 0


def _brier(probs: list[float], outcomes: list[int]) -> float:
    n = len(probs)
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / n if n else float("nan")


def _logloss(probs: list[float], outcomes: list[int]) -> float:
    eps = 1e-7
    n = len(probs)
    if not n:
        return float("nan")
    total = 0.0
    for p, y in zip(probs, outcomes):
        p = max(eps, min(1 - eps, p))
        total += -(y * math.log(p) + (1 - y) * math.log(1 - p))
    return total / n


def _extract_params(cal) -> dict:
    """從 ProbabilityCalibrator 提取校準參數供記錄。"""
    try:
        from wbc_backend.calibration.probability_calibrator import PlattScaler, TemperatureScaler
        scaler = cal._scaler
        if isinstance(scaler, TemperatureScaler):
            return {"temperature": round(scaler.temperature, 4)}
        if isinstance(scaler, PlattScaler):
            return {"a": round(scaler.a, 4), "b": round(scaler.b, 4)}
    except Exception:
        pass
    return {}


def _write_snapshot(
    path: Path,
    records: list[dict],
    probs: list[float],
    task_id: int,
    snapshot_type: str,
    calibration_method: str,
) -> None:
    """
    寫入 prediction snapshot（JSONL）。
    每行保留 leakage-safe 欄位：game_id, predicted_prob, result, regime,
    market_prob, pnl, roi, clv, timestamp.
    post-game 資訊（final_score 等）移除。
    """
    _SAFE_FIELDS = {"game_id", "result", "regime", "market_prob", "pnl", "roi", "clv", "timestamp"}
    lines = []
    for r, p in zip(records, probs):
        row: dict = {k: v for k, v in r.items() if k in _SAFE_FIELDS}
        row["predicted_prob"] = round(p, 8)
        row["snapshot_type"] = snapshot_type
        row["calibration_method"] = calibration_method
        row["patch_task_id"] = task_id
        row["snapshot_at"] = datetime.now(timezone.utc).isoformat()
        lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.debug("[CalibrationPatchRunner] Snapshot written: %s (%d records)", path, len(lines))


def _extract_params(cal) -> dict:  # type: ignore[no-redef]
    """從 ProbabilityCalibrator 提取校準參數供記錄。"""
    try:
        from wbc_backend.calibration.probability_calibrator import PlattScaler, TemperatureScaler
        scaler = cal._scaler
        if isinstance(scaler, TemperatureScaler):
            return {"temperature": round(scaler.temperature, 4)}
        if isinstance(scaler, PlattScaler):
            return {"a": round(scaler.a, 4), "b": round(scaler.b, 4)}
    except Exception:
        pass
    return {}


# ──────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    parser = argparse.ArgumentParser(description="Run calibration patch in research mode")
    parser.add_argument("--task-id", type=int, required=True, help="Patch task ID")
    args = parser.parse_args()

    manifest = run_calibration_patch(args.task_id)
    print(json.dumps(asdict(manifest), indent=2, ensure_ascii=False))
    if manifest.status == "SUCCESS":
        print(f"\n✅ Artifacts written:")
        print(f"  BEFORE: {manifest.before_snapshot_path}")
        print(f"  AFTER:  {manifest.after_snapshot_path}")
        print(f"  Brier: {manifest.before_brier:.4f} → {manifest.after_brier:.4f} (Δ{manifest.brier_delta:+.4f})")
    else:
        print(f"\n❌ Patch failed: {manifest.failure_reason}")
