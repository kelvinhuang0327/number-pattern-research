"""
機率後校準模組 — Phase 8A
==========================
解決 Phase 7B 回測發現的問題：Brier Skill Score -14.1%（MARL 輸出未與市場校準對齊）。

三種校準方法（依資料量自動選擇）：
  1. Platt Scaling     — Logistic regression 後校準（sigmoid 映射）
  2. Isotonic Reg.     — 非參數等溫回歸（保序約束，需 sklearn）
  3. Temperature Scaling — 單參數 Logit 縮放（最快，WBC/小樣本首選）

校準流程：
  1. train(raw_probs, outcomes) — 在驗證集或訓練集的 holdout 上擬合校準器
  2. calibrate(raw_probs)       — 對測試集輸出校準後機率
  3. evaluate(cal_probs, mkt_probs, outcomes) — 計算 Brier Skill Score 等指標

資料需求：
  - Platt / Temperature：最低 20 樣本
  - Isotonic：最低 50 樣本（否則 fallback 至 Platt）

無外部依賴的 fallback：
  - 若 sklearn 不可用，自動使用純 Python 的 Platt Scaling 及 Temperature Scaling
"""
from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np

logger = logging.getLogger(__name__)

CalibrationMethod = Literal["platt", "isotonic", "temperature", "auto"]


# ══════════════════════════════════════════════════════════════════════════════
# 輸出結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CalibrationResult:
    """校準評估結果"""
    method: str
    n_samples: int
    # 校準前指標
    raw_brier: float
    raw_ece: float
    # 校準後指標
    cal_brier: float
    cal_ece: float
    # 市場基準 Brier（用於計算 Brier Skill Score）
    market_brier: float
    # 技術分數（相對市場）
    raw_brier_skill: float    # 1 - raw_brier / market_brier
    cal_brier_skill: float    # 1 - cal_brier / market_brier
    # 校準器內部參數
    params: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# 工具函數
# ══════════════════════════════════════════════════════════════════════════════

def _brier(probs: list[float], outcomes: list[int]) -> float:
    return float(np.mean([(p - y) ** 2 for p, y in zip(probs, outcomes)]))


def _ece(probs: list[float], outcomes: list[int], n_bins: int = 10) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(probs)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = [lo <= p < hi for p in probs]
        if not any(mask):
            continue
        bp = [p for p, m in zip(probs, mask) if m]
        bo = [y for y, m in zip(outcomes, mask) if m]
        ece += (len(bp) / n) * abs(float(np.mean(bp)) - float(np.mean(bo)))
    return round(ece, 6)


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-float(np.clip(x, -30, 30))))


def _logit(p: float, eps: float = 1e-7) -> float:
    p = float(np.clip(p, eps, 1 - eps))
    return math.log(p / (1 - p))


# ══════════════════════════════════════════════════════════════════════════════
# Temperature Scaling（單參數 Logit 縮放）
# ══════════════════════════════════════════════════════════════════════════════

class TemperatureScaler:
    """
    Temperature Scaling：scaled_logit = logit(p) / T
    T > 1 → 壓縮（降低信心）；T < 1 → 放大（提高信心）。
    最小化 Brier Score 以找最優 T（BFGS-like 手動梯度下降）。
    """

    def __init__(self) -> None:
        self.temperature: float = 1.0
        self._fitted: bool = False

    def fit(self, raw_probs: list[float], outcomes: list[int]) -> "TemperatureScaler":
        """以 Brier Score 為目標函數，Grid Search 最優 T"""
        best_t = 1.0
        best_brier = float("inf")
        # 粗粒度 grid 搜索 + 精細搜索
        for t_candidate in np.linspace(0.2, 4.0, 40):
            cal = [_sigmoid(_logit(p) / t_candidate) for p in raw_probs]
            b = _brier(cal, outcomes)
            if b < best_brier:
                best_brier = b
                best_t = float(t_candidate)
        # 在最佳附近精細搜索
        lo, hi = max(0.1, best_t - 0.2), best_t + 0.2
        for t_candidate in np.linspace(lo, hi, 20):
            cal = [_sigmoid(_logit(p) / t_candidate) for p in raw_probs]
            b = _brier(cal, outcomes)
            if b < best_brier:
                best_brier = b
                best_t = float(t_candidate)
        self.temperature = best_t
        self._fitted = True
        logger.debug(f"TemperatureScaler 最優 T={self.temperature:.3f}，Brier={best_brier:.4f}")
        return self

    def transform(self, raw_probs: list[float]) -> list[float]:
        if not self._fitted:
            raise RuntimeError("請先呼叫 fit()")
        return [_sigmoid(_logit(p) / self.temperature) for p in raw_probs]


# ══════════════════════════════════════════════════════════════════════════════
# Platt Scaling（Logistic Regression 後校準）
# ══════════════════════════════════════════════════════════════════════════════

class PlattScaler:
    """
    Platt Scaling：先把 raw_prob → logit，再做一維 Logistic Regression。
    等同學習 a * logit(p) + b → sigmoid → calibrated_prob。
    """

    def __init__(self) -> None:
        self.a: float = 1.0
        self.b: float = 0.0
        self._fitted: bool = False

    def fit(self, raw_probs: list[float], outcomes: list[int],
            lr: float = 0.05, n_iter: int = 300) -> "PlattScaler":
        """梯度下降擬合 a, b（最小化交叉熵）"""
        logits = [_logit(p) for p in raw_probs]
        a, b = 1.0, 0.0
        for _ in range(n_iter):
            grad_a, grad_b = 0.0, 0.0
            for x, y in zip(logits, outcomes):
                pred = _sigmoid(a * x + b)
                err = pred - y
                grad_a += err * x
                grad_b += err
            n = len(logits)
            a -= lr * grad_a / n
            b -= lr * grad_b / n
        self.a = a
        self.b = b
        self._fitted = True
        logger.debug(f"PlattScaler 擬合完成：a={self.a:.3f}, b={self.b:.3f}")
        return self

    def transform(self, raw_probs: list[float]) -> list[float]:
        if not self._fitted:
            raise RuntimeError("請先呼叫 fit()")
        return [_sigmoid(self.a * _logit(p) + self.b) for p in raw_probs]


# ══════════════════════════════════════════════════════════════════════════════
# Isotonic Regression（等溫回歸）
# ══════════════════════════════════════════════════════════════════════════════

class IsotonicScaler:
    """
    Isotonic Regression：保序映射，利用 sklearn.isotonic.IsotonicRegression。
    若 sklearn 不可用，自動 fallback 至 PlattScaler。
    """

    def __init__(self) -> None:
        self._model = None
        self._fallback: Optional[PlattScaler] = None
        self._fitted: bool = False

    def fit(self, raw_probs: list[float], outcomes: list[int]) -> "IsotonicScaler":
        try:
            from sklearn.isotonic import IsotonicRegression
            ir = IsotonicRegression(out_of_bounds="clip")
            ir.fit(raw_probs, outcomes)
            self._model = ir
        except ImportError:
            logger.warning("sklearn 不可用，Isotonic Scaler fallback 至 Platt Scaling")
            self._fallback = PlattScaler().fit(raw_probs, outcomes)
        self._fitted = True
        return self

    def transform(self, raw_probs: list[float]) -> list[float]:
        if not self._fitted:
            raise RuntimeError("請先呼叫 fit()")
        if self._model is not None:
            result = self._model.transform(raw_probs)
            return [float(np.clip(v, 0.01, 0.99)) for v in result]
        return self._fallback.transform(raw_probs)  # type: ignore[union-attr]


# ══════════════════════════════════════════════════════════════════════════════
# 主要校準器（自動方法選擇）
# ══════════════════════════════════════════════════════════════════════════════

class ProbabilityCalibrator:
    """
    統一機率校準介面。

    依樣本數自動選擇最佳方法（method="auto"）：
      - n >= 100: Isotonic（最靈活）
      - 20 <= n < 100: Platt（穩健）
      - n < 20: Temperature（最少過擬合風險）

    Example:
        cal = ProbabilityCalibrator(method="auto")
        cal.fit(raw_probs_train, outcomes_train)
        cal_probs_test = cal.calibrate(raw_probs_test)
        report = cal.evaluate(cal_probs_test, market_probs_test, outcomes_test)
    """

    def __init__(self, method: CalibrationMethod = "auto") -> None:
        self.method = method
        self._scaler: Optional[TemperatureScaler | PlattScaler | IsotonicScaler] = None
        self._fitted_method: str = "none"
        self._fitted: bool = False

    def fit(
        self,
        raw_probs: list[float],
        outcomes: list[int],
    ) -> "ProbabilityCalibrator":
        """在驗證集上擬合校準器"""
        n = len(raw_probs)
        if n < 10:
            raise ValueError(f"校準樣本不足（{n} < 10）")

        # 決定方法
        method = self.method
        if method == "auto":
            if n >= 100:
                method = "isotonic"
            elif n >= 20:
                method = "platt"
            else:
                method = "temperature"

        if method == "temperature":
            self._scaler = TemperatureScaler().fit(raw_probs, outcomes)
        elif method == "platt":
            self._scaler = PlattScaler().fit(raw_probs, outcomes)
        else:  # isotonic
            self._scaler = IsotonicScaler().fit(raw_probs, outcomes)

        self._fitted_method = method
        self._fitted = True
        logger.info(f"ProbabilityCalibrator 使用方法：{method}（n={n}）")
        return self

    def calibrate(self, raw_probs: list[float]) -> list[float]:
        """對新的原始機率序列進行校準"""
        if not self._fitted:
            raise RuntimeError("請先呼叫 fit()")
        cal = self._scaler.transform(raw_probs)  # type: ignore[union-attr]
        return [float(np.clip(p, 0.01, 0.99)) for p in cal]

    def evaluate(
        self,
        cal_probs: list[float],
        market_probs: list[float],
        outcomes: list[int],
        raw_probs: Optional[list[float]] = None,
    ) -> CalibrationResult:
        """
        計算校準前後的 Brier / ECE / Brier Skill Score 對比。

        Args:
            cal_probs: 校準後機率
            market_probs: 市場隱含機率（作為基準）
            outcomes: 實際結果（0/1）
            raw_probs: 原始未校準機率（若提供則計算改善量）
        """
        n = len(cal_probs)
        market_brier = _brier(market_probs, outcomes)

        raw_b = _brier(raw_probs, outcomes) if raw_probs else float("nan")
        raw_e = _ece(raw_probs, outcomes) if raw_probs else float("nan")
        raw_skill = (1 - raw_b / market_brier) if (raw_probs and market_brier > 0) else float("nan")

        cal_b = _brier(cal_probs, outcomes)
        cal_e = _ece(cal_probs, outcomes)
        cal_skill = (1 - cal_b / market_brier) if market_brier > 0 else 0.0

        # 收集校準器參數
        params: dict = {}
        if isinstance(self._scaler, TemperatureScaler):
            params["temperature"] = round(self._scaler.temperature, 4)
        elif isinstance(self._scaler, PlattScaler):
            params["a"] = round(self._scaler.a, 4)
            params["b"] = round(self._scaler.b, 4)

        notes: list[str] = []
        if not math.isnan(raw_b):
            improvement = raw_b - cal_b
            notes.append(
                f"Brier 改善：{improvement:+.4f}（{raw_b:.4f} → {cal_b:.4f}）"
            )
        if cal_skill > 0:
            notes.append(f"✅ 校準後超越市場：Brier Skill Score = {cal_skill:+.1%}")
        elif cal_skill > -0.05:
            notes.append(f"➡️ 校準後接近市場：Brier Skill Score = {cal_skill:+.1%}")
        else:
            notes.append(f"❌ 仍低於市場：Brier Skill Score = {cal_skill:+.1%}")

        return CalibrationResult(
            method=self._fitted_method,
            n_samples=n,
            raw_brier=round(raw_b, 4) if not math.isnan(raw_b) else 0.0,
            raw_ece=round(raw_e, 4) if not math.isnan(raw_e) else 0.0,
            cal_brier=round(cal_b, 4),
            cal_ece=round(cal_e, 4),
            market_brier=round(market_brier, 4),
            raw_brier_skill=round(raw_skill, 4) if not math.isnan(raw_skill) else 0.0,
            cal_brier_skill=round(cal_skill, 4),
            params=params,
            notes=notes,
        )


# ══════════════════════════════════════════════════════════════════════════════
# Walk-Forward 校準整合（與 FullBacktestEngine 配合使用）
# ══════════════════════════════════════════════════════════════════════════════

def calibrate_walk_forward(
    train_probs: list[float],
    train_outcomes: list[int],
    test_probs: list[float],
    test_outcomes: list[int],
    test_market_probs: list[float],
    method: CalibrationMethod = "auto",
) -> tuple[list[float], CalibrationResult]:
    """
    單一 Walk-Forward 視窗的校準流程。

    Args:
        train_probs: 訓練集原始預測機率
        train_outcomes: 訓練集實際結果
        test_probs: 測試集原始預測機率
        test_outcomes: 測試集實際結果（用於評估）
        test_market_probs: 測試集市場機率（用於計算 Skill Score）
        method: 校準方法

    Returns:
        (calibrated_test_probs, CalibrationResult)
    """
    cal = ProbabilityCalibrator(method=method)
    # 若訓練集太小，使用 temperature scaling
    eff_method = method
    if method == "auto" and len(train_probs) < 20:
        eff_method = "temperature"
        cal = ProbabilityCalibrator(method=eff_method)

    cal.fit(train_probs, train_outcomes)
    cal_probs = cal.calibrate(test_probs)
    result = cal.evaluate(cal_probs, test_market_probs, test_outcomes, test_probs)
    return cal_probs, result
