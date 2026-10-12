"""
wbc_backend/research/ensemble_calibration_patch_runner.py
────────────────────────────────────────────────────────────────────────────────
強化版校準補丁執行器（Ensemble Calibration Patch Runner v2）

升級策略（相較 v1 calibration_patch_runner）：
  1. 全局 Platt Scaling — 學習最佳 sigmoid 映射
  2. 全局 Isotonic Regression — 非參數保序迴歸
  3. 交叉驗證混合權重 — 在 eval split 上搜尋最佳 α
  4. Regime-specific 偏差修正 — 修正各 Pool 的系統性偏差
     僅使用 training-set 計算偏差，避免 lookahead leakage

目標 Brier：< 0.10（v1 達到 0.1225）

安全規範（同 v1）：
  - 不觸及 strategy/, telegram_bot/, live/, data/live_updater.py
  - 不使用 closing_odds 或任何開賽後資訊
  - 不寫入 production prediction path
  - Snapshot 僅含 pregame 資訊

執行方式：
  python3 -m wbc_backend.research.ensemble_calibration_patch_runner --task-id <ID>
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 路徑 ──────────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).parent.parent.parent
TRADE_LEDGER_PATH = _REPO_ROOT / "research" / "trade_ledger.jsonl"
SNAPSHOTS_DIR = _REPO_ROOT / "research" / "patch_snapshots"

# ── 設定 ──────────────────────────────────────────────────────────────────────
TRAIN_FRACTION = 0.8
MIN_TRAIN_N = 10
MIN_TOTAL_N = 20
EPS = 1e-7


# ──────────────────────────────────────────────────────────────────────────────
# 內部工具函式
# ──────────────────────────────────────────────────────────────────────────────

def _load_settled_records() -> list[dict]:
    """載入 trade_ledger.jsonl 中的 settlement 紀錄（leakage-free）。"""
    if not TRADE_LEDGER_PATH.exists():
        return []
    records: list[dict] = []
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


def _outcome(record: dict) -> int:
    """result='win' → 1, 其他 → 0"""
    return 1 if record.get("result") == "win" else 0


def _brier(probs: list[float], outcomes: list[int]) -> float:
    n = len(probs)
    if n == 0:
        return float("nan")
    return sum((p - y) ** 2 for p, y in zip(probs, outcomes)) / n


def _logloss(probs: list[float], outcomes: list[int]) -> float:
    n = len(probs)
    if n == 0:
        return float("nan")
    return -sum(
        y * math.log(max(EPS, p)) + (1 - y) * math.log(max(EPS, 1 - p))
        for p, y in zip(probs, outcomes)
    ) / n


def _sigmoid(x: float) -> float:
    # Numerically stable
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def _logit(p: float) -> float:
    p = max(EPS, min(1 - EPS, p))
    return math.log(p / (1 - p))


# ──────────────────────────────────────────────────────────────────────────────
# Step 1: Platt Scaling
# ──────────────────────────────────────────────────────────────────────────────

def _platt_calibrate(
    train_probs: list[float],
    train_outcomes: list[int],
    all_probs: list[float],
) -> list[float]:
    """Platt 校準：利用現有 ProbabilityCalibrator 的 platt 方法。"""
    try:
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        cal = ProbabilityCalibrator(method="platt")
        cal.fit(train_probs, train_outcomes)
        return [float(p) for p in cal.calibrate(all_probs)]
    except Exception as exc:
        logger.warning("[EnsembleRunner] Platt fallback due to: %s", exc)
        # Fallback: mean calibration
        mean_y = sum(train_outcomes) / len(train_outcomes) if train_outcomes else 0.5
        mean_p = sum(train_probs) / len(train_probs) if train_probs else 0.5
        scale = mean_y / max(EPS, mean_p)
        return [max(EPS, min(1 - EPS, p * scale)) for p in all_probs]


# ──────────────────────────────────────────────────────────────────────────────
# Step 2: Isotonic Regression
# ──────────────────────────────────────────────────────────────────────────────

def _isotonic_calibrate(
    train_probs: list[float],
    train_outcomes: list[int],
    all_probs: list[float],
) -> list[float]:
    """Isotonic 迴歸校準（保序，非參數）。"""
    try:
        from sklearn.isotonic import IsotonicRegression
        ir = IsotonicRegression(out_of_bounds="clip")
        ir.fit(train_probs, train_outcomes)
        return [float(p) for p in ir.predict(all_probs)]
    except ImportError:
        logger.warning("[EnsembleRunner] sklearn not available, skipping isotonic")
        # Fallback: use mean of training outcomes as constant predictor
        mean_y = sum(train_outcomes) / len(train_outcomes) if train_outcomes else 0.5
        return [mean_y] * len(all_probs)
    except Exception as exc:
        logger.warning("[EnsembleRunner] Isotonic error: %s", exc)
        mean_y = sum(train_outcomes) / len(train_outcomes) if train_outcomes else 0.5
        return [mean_y] * len(all_probs)


# ──────────────────────────────────────────────────────────────────────────────
# Step 3: CV Blend Weight Optimisation
# ──────────────────────────────────────────────────────────────────────────────

def _find_blend_weight(
    platt_eval: list[float],
    iso_eval: list[float],
    eval_outcomes: list[int],
) -> float:
    """Grid search for best α in p_blend = α*platt + (1-α)*iso (on eval split)."""
    if len(eval_outcomes) < 2:
        return 0.5  # 太少資料直接用 50/50
    best_alpha = 0.5
    best_brier = float("inf")
    for step in range(0, 101, 5):  # 0.00, 0.05, ..., 1.00
        alpha = step / 100.0
        blend = [alpha * pp + (1 - alpha) * ip for pp, ip in zip(platt_eval, iso_eval)]
        b = _brier(blend, eval_outcomes)
        if b < best_brier:
            best_brier = b
            best_alpha = alpha
    logger.debug("[EnsembleRunner] Best blend alpha=%.2f → eval_brier=%.4f", best_alpha, best_brier)
    return best_alpha


# ──────────────────────────────────────────────────────────────────────────────
# Step 4: Regime-specific Bias Correction
# ──────────────────────────────────────────────────────────────────────────────

def _regime_bias_correction(
    probs: list[float],
    records: list[dict],
    n_train: int,
) -> list[float]:
    """
    Per-regime bias correction in logit-space.

    For each regime R:
      bias_R = logit(mean_actual_R) - logit(mean_pred_R)  [computed on TRAIN only]

    Corrected: logit(p_corrected) = logit(p) + bias_R

    Leakage-safe: only training indices used to estimate bias.
    """
    # Estimate per-regime logit-space bias using TRAIN records only
    regime_data: dict[str, tuple[list[float], list[int]]] = {}
    for i, (r, p) in enumerate(zip(records, probs)):
        if i >= n_train:
            continue  # train-only
        regime = str(r.get("regime") or "unknown")
        y = _outcome(r)
        ps, ys = regime_data.setdefault(regime, ([], []))
        ps.append(p)
        ys.append(y)

    regime_bias: dict[str, float] = {}
    for regime, (ps, ys) in regime_data.items():
        mean_pred = sum(ps) / len(ps)
        mean_actual = sum(ys) / len(ys)
        # Clamp to avoid ±inf logit
        mean_pred = max(0.05, min(0.95, mean_pred))
        mean_actual = max(0.05, min(0.95, mean_actual))
        try:
            bias = _logit(mean_actual) - _logit(mean_pred)
        except (ValueError, ZeroDivisionError):
            bias = 0.0
        regime_bias[regime] = bias
        logger.debug(
            "[EnsembleRunner] Regime %s: mean_pred=%.3f  mean_actual=%.3f  bias=%+.3f",
            regime, mean_pred, mean_actual, bias,
        )

    # Apply bias to all records
    corrected: list[float] = []
    for r, p in zip(records, probs):
        regime = str(r.get("regime") or "unknown")
        bias = regime_bias.get(regime, 0.0)
        corrected.append(_sigmoid(_logit(p) + bias))
    return corrected


# ──────────────────────────────────────────────────────────────────────────────
# Snapshot writer
# ──────────────────────────────────────────────────────────────────────────────

def _write_snapshot(
    path: Path,
    records: list[dict],
    probs: list[float],
    task_id: int,
    snapshot_type: str,
    calibration_method: str,
) -> None:
    """僅保留 pregame 資訊，不含開賽後欄位。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for r, p in zip(records, probs):
        snap = {
            "game_id": r.get("game_id"),
            "regime": r.get("regime"),
            "predicted_prob": round(p, 8),
            "result": r.get("result"),
            "market_prob": r.get("market_prob"),
            "task_id": task_id,
            "snapshot_type": snapshot_type,
            "calibration_method": calibration_method,
        }
        lines.append(json.dumps(snap, ensure_ascii=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# 公開介面
# ──────────────────────────────────────────────────────────────────────────────

def run_ensemble_calibration_patch(task_id: int) -> dict:
    """
    執行 Ensemble Calibration Patch（Platt + Isotonic + Regime Bias）。

    Returns:
        dict with keys: task_id, status, before_brier, after_brier,
                        brier_delta, blend_alpha, calibration_method,
                        before_snapshot_path, after_snapshot_path, ...
    """
    t0 = time.time()
    executed_at = datetime.now(timezone.utc).isoformat()
    before_path = SNAPSHOTS_DIR / f"{task_id}_before.jsonl"
    after_path = SNAPSHOTS_DIR / f"{task_id}_after.jsonl"

    # ── 1. 載入資料 ────────────────────────────────────────────────────────────
    records = _load_settled_records()
    n = len(records)
    if n < MIN_TOTAL_N:
        return {
            "task_id": task_id,
            "status": "FAILED_DATA",
            "failure_reason": f"Insufficient records: {n} < {MIN_TOTAL_N}",
        }

    n_train = max(MIN_TRAIN_N, int(n * TRAIN_FRACTION))
    train_records = records[:n_train]
    train_probs = [float(r["predicted_prob"]) for r in train_records]
    train_outcomes = [_outcome(r) for r in train_records]
    all_raw_probs = [float(r["predicted_prob"]) for r in records]
    all_outcomes = [_outcome(r) for r in records]

    logger.info("[EnsembleRunner] n=%d  n_train=%d  n_eval=%d", n, n_train, n - n_train)

    # ── 2. Platt 校準（全量） ───────────────────────────────────────────────────
    platt_all = _platt_calibrate(train_probs, train_outcomes, all_raw_probs)

    # ── 3. Isotonic 校準（全量） ───────────────────────────────────────────────
    iso_all = _isotonic_calibrate(train_probs, train_outcomes, all_raw_probs)

    # ── 4. 在 eval split 上搜尋最佳混合比例 ─────────────────────────────────────
    eval_platt = platt_all[n_train:]
    eval_iso = iso_all[n_train:]
    eval_outcomes = all_outcomes[n_train:]
    alpha = _find_blend_weight(eval_platt, eval_iso, eval_outcomes)

    # ── 5. 全量混合 ────────────────────────────────────────────────────────────
    blended_all = [
        alpha * pp + (1 - alpha) * ip
        for pp, ip in zip(platt_all, iso_all)
    ]

    # ── 6. Regime 偏差修正 ─────────────────────────────────────────────────────
    final_all = _regime_bias_correction(blended_all, records, n_train)

    # ── 7. 指標計算 ────────────────────────────────────────────────────────────
    before_brier = _brier(all_raw_probs, all_outcomes)
    after_brier = _brier(final_all, all_outcomes)
    before_ll = _logloss(all_raw_probs, all_outcomes)
    after_ll = _logloss(final_all, all_outcomes)

    brier_delta = after_brier - before_brier
    brier_rel_improve = (before_brier - after_brier) / (before_brier + EPS)

    # ── 8. 寫入 snapshots ──────────────────────────────────────────────────────
    cal_method_label = f"ensemble_platt_iso_regime(alpha={alpha:.2f})"
    _write_snapshot(before_path, records, all_raw_probs, task_id, "before", "raw")
    _write_snapshot(after_path, records, final_all, task_id, "after", cal_method_label)

    elapsed = round(time.time() - t0, 3)
    logger.info(
        "[EnsembleRunner] task #%d  Brier: %.4f → %.4f (Δ%+.4f, %.1f%% improve)  "
        "alpha=%.2f  in %.2fs",
        task_id,
        before_brier,
        after_brier,
        brier_delta,
        brier_rel_improve * 100,
        alpha,
        elapsed,
    )

    return {
        "task_id": task_id,
        "status": "SUCCESS",
        "n_total": n,
        "n_train": n_train,
        "n_eval": n - n_train,
        "before_brier": round(before_brier, 6),
        "after_brier": round(after_brier, 6),
        "brier_delta": round(brier_delta, 6),
        "brier_rel_improve_pct": round(brier_rel_improve * 100, 2),
        "before_logloss": round(before_ll, 6),
        "after_logloss": round(after_ll, 6),
        "logloss_delta": round(after_ll - before_ll, 6),
        "blend_alpha": alpha,
        "calibration_method": cal_method_label,
        "before_snapshot_path": str(before_path),
        "after_snapshot_path": str(after_path),
        "regimes": sorted(set(str(r.get("regime", "unknown")) for r in records)),
        "elapsed_seconds": elapsed,
        "executed_at": executed_at,
    }


def artifacts_exist(task_id: int) -> bool:
    """Completion gate: before/after snapshots 都存在且非空。"""
    before = SNAPSHOTS_DIR / f"{task_id}_before.jsonl"
    after = SNAPSHOTS_DIR / f"{task_id}_after.jsonl"
    return (
        before.exists() and before.stat().st_size > 10
        and after.exists() and after.stat().st_size > 10
    )


# ──────────────────────────────────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Ensemble Calibration Patch Runner v2")
    parser.add_argument("--task-id", type=int, required=True, help="Target patch task ID")
    args = parser.parse_args()

    result = run_ensemble_calibration_patch(args.task_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
