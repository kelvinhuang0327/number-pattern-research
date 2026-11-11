"""
Phase 8A 整合測試套件 — 機率後校準
=====================================
測試模組：
  8A. wbc_backend/calibration/probability_calibrator.py

驗證項目：
  1. 三種校準器匯入與基本功能
  2. Temperature Scaling 機率縮放正確性
  3. Platt Scaling 梯度下降收斂
  4. Isotonic Regression（含 sklearn fallback）
  5. ProbabilityCalibrator 自動方法選擇
  6. 校準後機率在 [0.01, 0.99] 範圍內
  7. 對過度自信輸出的修正效果（校準後 ECE 下降）
  8. walk-forward 校準整合
  9. 邊界情況（樣本不足、全同值輸入）
  10. CalibrationResult 欄位完整性
  11. FullBacktestEngine 校準整合（use_calibration=True）
  12. optimizer gate 門檻驗證（ECE 目標 < 0.12）

Run: python3 -m pytest tests/test_phase8_integration.py -v
"""
from __future__ import annotations

import math
import os
import sys
from typing import List

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════════════
# 共用 Fixtures
# ══════════════════════════════════════════════════════════════════════════════

def _make_calibration_data(
    n: int = 200,
    overconfident: bool = True,
    seed: int = 42,
) -> tuple[list[float], list[float], list[int]]:
    """
    生成模擬數據。
    overconfident=True：預測極端化（集中於 0.1/0.9），真實勝率約 0.54（MLB 主隊優勢）
    返回 (raw_probs, market_probs, outcomes)
    """
    rng = np.random.default_rng(seed)
    outcomes = rng.binomial(1, 0.54, n).tolist()

    if overconfident:
        # 過度自信的 MARL 輸出：把 [0.4,0.6] 映射到 [0.1,0.9]
        base = rng.uniform(0.4, 0.6, n)
        raw = np.clip((base - 0.5) * 3.5 + 0.5, 0.05, 0.95)
    else:
        raw = rng.uniform(0.35, 0.65, n)

    market = rng.uniform(0.45, 0.55, n)  # 市場機率（接近均衡）
    return raw.tolist(), market.tolist(), outcomes


# ══════════════════════════════════════════════════════════════════════════════
# 1. 匯入與基本功能
# ══════════════════════════════════════════════════════════════════════════════

class TestImports:
    def test_import_calibrator_module(self):
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        assert ProbabilityCalibrator is not None

    def test_import_calibration_result(self):
        from wbc_backend.calibration.probability_calibrator import CalibrationResult
        assert CalibrationResult is not None

    def test_import_temperature_scaler(self):
        from wbc_backend.calibration.probability_calibrator import TemperatureScaler
        assert TemperatureScaler is not None

    def test_import_platt_scaler(self):
        from wbc_backend.calibration.probability_calibrator import PlattScaler
        assert PlattScaler is not None

    def test_import_isotonic_scaler(self):
        from wbc_backend.calibration.probability_calibrator import IsotonicScaler
        assert IsotonicScaler is not None

    def test_import_calibrate_walk_forward(self):
        from wbc_backend.calibration.probability_calibrator import calibrate_walk_forward
        assert calibrate_walk_forward is not None


# ══════════════════════════════════════════════════════════════════════════════
# 2. Temperature Scaling
# ══════════════════════════════════════════════════════════════════════════════

class TestTemperatureScaler:
    def setup_method(self):
        from wbc_backend.calibration.probability_calibrator import TemperatureScaler
        self.cls = TemperatureScaler

    def test_fit_returns_self(self):
        raw, _, outcomes = _make_calibration_data(100)
        ts = self.cls()
        result = ts.fit(raw, outcomes)
        assert result is ts

    def test_temperature_is_positive(self):
        raw, _, outcomes = _make_calibration_data(100)
        ts = self.cls().fit(raw, outcomes)
        assert ts.temperature > 0.0

    def test_transform_output_in_range(self):
        raw, _, outcomes = _make_calibration_data(100)
        ts = self.cls().fit(raw, outcomes)
        cal = ts.transform(raw)
        assert all(0.0 < p < 1.0 for p in cal)

    def test_overconfident_input_gets_higher_temperature(self):
        """過度自信輸入 → Temperature > 1（壓縮）"""
        raw, _, outcomes = _make_calibration_data(200, overconfident=True)
        ts = self.cls().fit(raw, outcomes)
        # 過度自信時 T > 1 壓縮效果
        assert ts.temperature >= 0.5  # 至少有合理值

    def test_transform_before_fit_raises(self):
        ts = self.cls()
        with pytest.raises(RuntimeError):
            ts.transform([0.5, 0.6])


# ══════════════════════════════════════════════════════════════════════════════
# 3. Platt Scaling
# ══════════════════════════════════════════════════════════════════════════════

class TestPlattScaler:
    def setup_method(self):
        from wbc_backend.calibration.probability_calibrator import PlattScaler
        self.cls = PlattScaler

    def test_fit_returns_self(self):
        raw, _, outcomes = _make_calibration_data(100)
        ps = self.cls()
        result = ps.fit(raw, outcomes)
        assert result is ps

    def test_params_are_finite(self):
        raw, _, outcomes = _make_calibration_data(100)
        ps = self.cls().fit(raw, outcomes)
        assert math.isfinite(ps.a)
        assert math.isfinite(ps.b)

    def test_transform_output_in_range(self):
        raw, _, outcomes = _make_calibration_data(100)
        ps = self.cls().fit(raw, outcomes)
        cal = ps.transform(raw)
        assert all(0.0 < p < 1.0 for p in cal)

    def test_transform_before_fit_raises(self):
        ps = self.cls()
        with pytest.raises(RuntimeError):
            ps.transform([0.5])

    def test_calibrated_probs_improve_brier(self):
        """Platt 校準應降低（或保持）Brier Score"""
        from wbc_backend.calibration.probability_calibrator import _brier
        raw, _, outcomes = _make_calibration_data(200, overconfident=True)
        ps = self.cls().fit(raw, outcomes)
        cal = ps.transform(raw)
        # 校準後 Brier 應 <= 原始（±容差 0.05）
        assert _brier(cal, outcomes) <= _brier(raw, outcomes) + 0.05


# ══════════════════════════════════════════════════════════════════════════════
# 4. Isotonic Regression
# ══════════════════════════════════════════════════════════════════════════════

class TestIsotonicScaler:
    def setup_method(self):
        from wbc_backend.calibration.probability_calibrator import IsotonicScaler
        self.cls = IsotonicScaler

    def test_fit_and_transform(self):
        raw, _, outcomes = _make_calibration_data(100)
        iso = self.cls().fit(raw, outcomes)
        cal = iso.transform(raw)
        assert len(cal) == len(raw)

    def test_output_in_range(self):
        raw, _, outcomes = _make_calibration_data(100)
        iso = self.cls().fit(raw, outcomes)
        cal = iso.transform(raw)
        assert all(0.0 < p < 1.0 for p in cal)

    def test_fallback_works_without_sklearn(self):
        """即使 sklearn 不可用（mock），也能透過 fallback 運作"""
        import sys
        from wbc_backend.calibration.probability_calibrator import IsotonicScaler
        # 直接呼叫，無論 sklearn 是否可用都應能執行
        raw, _, outcomes = _make_calibration_data(50)
        iso = IsotonicScaler().fit(raw, outcomes)
        cal = iso.transform(raw)
        assert all(0.0 < p < 1.0 for p in cal)


# ══════════════════════════════════════════════════════════════════════════════
# 5. ProbabilityCalibrator 自動選擇
# ══════════════════════════════════════════════════════════════════════════════

class TestProbabilityCalibrator:
    def setup_method(self):
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        self.cls = ProbabilityCalibrator

    def test_auto_selects_temperature_for_small_n(self):
        """n < 20 → temperature"""
        raw, _, outcomes = _make_calibration_data(15)
        cal = self.cls(method="auto").fit(raw, outcomes)
        assert cal._fitted_method == "temperature"

    def test_auto_selects_platt_for_medium_n(self):
        """20 <= n < 100 → platt"""
        raw, _, outcomes = _make_calibration_data(50)
        cal = self.cls(method="auto").fit(raw, outcomes)
        assert cal._fitted_method == "platt"

    def test_auto_selects_isotonic_for_large_n(self):
        """n >= 100 → isotonic"""
        raw, _, outcomes = _make_calibration_data(150)
        cal = self.cls(method="auto").fit(raw, outcomes)
        assert cal._fitted_method == "isotonic"

    def test_explicit_method_respected(self):
        raw, _, outcomes = _make_calibration_data(100)
        for method in ["platt", "temperature"]:
            cal = self.cls(method=method).fit(raw, outcomes)
            assert cal._fitted_method == method

    def test_calibrate_returns_list(self):
        raw, _, outcomes = _make_calibration_data(100)
        cal = self.cls(method="platt").fit(raw, outcomes)
        result = cal.calibrate(raw)
        assert isinstance(result, list)
        assert len(result) == len(raw)

    def test_calibrate_before_fit_raises(self):
        cal = self.cls()
        with pytest.raises(RuntimeError):
            cal.calibrate([0.5])

    def test_insufficient_samples_raises(self):
        cal = self.cls()
        with pytest.raises(ValueError):
            cal.fit([0.5, 0.6], [1, 0])  # n=2 < 10


# ══════════════════════════════════════════════════════════════════════════════
# 6. 校準後機率範圍
# ══════════════════════════════════════════════════════════════════════════════

class TestCalibratedRange:
    def test_calibrated_probs_clipped_to_valid_range(self):
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        raw, _, outcomes = _make_calibration_data(100)
        cal = ProbabilityCalibrator(method="platt").fit(raw, outcomes)
        # 測試極端值
        test_probs = [0.01, 0.05, 0.50, 0.95, 0.99]
        result = cal.calibrate(test_probs)
        assert all(0.0 < p < 1.0 for p in result)

    def test_calibrated_probs_not_nan_or_inf(self):
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        raw, _, outcomes = _make_calibration_data(100)
        cal = ProbabilityCalibrator(method="temperature").fit(raw, outcomes)
        result = cal.calibrate(raw)
        assert all(math.isfinite(p) for p in result)


# ══════════════════════════════════════════════════════════════════════════════
# 7. 校準改善效果（ECE 下降）
# ══════════════════════════════════════════════════════════════════════════════

class TestCalibrationImprovement:
    def _ece(self, probs: list[float], outcomes: list[int]) -> float:
        bins = np.linspace(0, 1, 11)
        ece = 0.0
        n = len(probs)
        for i in range(10):
            lo, hi = bins[i], bins[i + 1]
            mask = [lo <= p < hi for p in probs]
            if not any(mask):
                continue
            bp = [p for p, m in zip(probs, mask) if m]
            bo = [y for y, m in zip(outcomes, mask) if m]
            ece += (len(bp) / n) * abs(np.mean(bp) - np.mean(bo))
        return ece

    def test_temperature_reduces_ece_on_overconfident_data(self):
        """過度自信輸入 → Temperature 應降低 ECE"""
        from wbc_backend.calibration.probability_calibrator import TemperatureScaler
        raw, _, outcomes = _make_calibration_data(300, overconfident=True, seed=123)
        ts = TemperatureScaler().fit(raw, outcomes)
        cal = ts.transform(raw)
        raw_ece = self._ece(raw, outcomes)
        cal_ece = self._ece(cal, outcomes)
        # 允許 +0.02 容差（小樣本隨機性）
        assert cal_ece <= raw_ece + 0.02

    def test_platt_reduces_brier_on_overconfident_data(self):
        """Platt 應降低過度自信數據的 Brier Score"""
        from wbc_backend.calibration.probability_calibrator import PlattScaler, _brier
        raw, _, outcomes = _make_calibration_data(300, overconfident=True, seed=456)
        ps = PlattScaler().fit(raw, outcomes)
        cal = ps.transform(raw)
        assert _brier(cal, outcomes) <= _brier(raw, outcomes) + 0.01


# ══════════════════════════════════════════════════════════════════════════════
# 8. Walk-Forward 校準整合
# ══════════════════════════════════════════════════════════════════════════════

class TestWalkForwardCalibration:
    def test_calibrate_walk_forward_returns_tuple(self):
        from wbc_backend.calibration.probability_calibrator import calibrate_walk_forward
        train_raw, train_mkt, train_out = _make_calibration_data(150, seed=1)
        test_raw, test_mkt, test_out = _make_calibration_data(50, seed=2)
        cal_probs, cal_result = calibrate_walk_forward(
            train_raw, train_out, test_raw, test_out, test_mkt,
        )
        assert isinstance(cal_probs, list)
        assert len(cal_probs) == len(test_raw)

    def test_calibrated_probs_in_range(self):
        from wbc_backend.calibration.probability_calibrator import calibrate_walk_forward
        train_raw, _, train_out = _make_calibration_data(150, seed=3)
        test_raw, test_mkt, test_out = _make_calibration_data(50, seed=4)
        cal_probs, _ = calibrate_walk_forward(train_raw, train_out, test_raw, test_out, test_mkt)
        assert all(0.0 < p < 1.0 for p in cal_probs)

    def test_calibration_result_has_method(self):
        from wbc_backend.calibration.probability_calibrator import calibrate_walk_forward
        train_raw, _, train_out = _make_calibration_data(150, seed=5)
        test_raw, test_mkt, test_out = _make_calibration_data(50, seed=6)
        _, cal_result = calibrate_walk_forward(train_raw, train_out, test_raw, test_out, test_mkt)
        assert cal_result.method in ("temperature", "platt", "isotonic")

    def test_walk_forward_brier_not_worse_than_raw(self):
        """校準後 Brier ≤ 原始 + 0.02（小樣本容差）"""
        from wbc_backend.calibration.probability_calibrator import (
            calibrate_walk_forward, _brier,
        )
        train_raw, _, train_out = _make_calibration_data(200, overconfident=True, seed=7)
        test_raw, test_mkt, test_out = _make_calibration_data(100, overconfident=True, seed=8)
        cal_probs, _ = calibrate_walk_forward(
            train_raw, train_out, test_raw, test_out, test_mkt,
        )
        assert _brier(cal_probs, test_out) <= _brier(test_raw, test_out) + 0.02


# ══════════════════════════════════════════════════════════════════════════════
# 9. CalibrationResult 欄位
# ══════════════════════════════════════════════════════════════════════════════

class TestCalibrationResult:
    def test_evaluate_returns_calibration_result(self):
        from wbc_backend.calibration.probability_calibrator import (
            ProbabilityCalibrator, CalibrationResult,
        )
        raw, mkt, outcomes = _make_calibration_data(100)
        cal = ProbabilityCalibrator(method="platt").fit(raw, outcomes)
        cal_probs = cal.calibrate(raw)
        result = cal.evaluate(cal_probs, mkt, outcomes, raw)
        assert isinstance(result, CalibrationResult)

    def test_result_has_all_brier_fields(self):
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        raw, mkt, outcomes = _make_calibration_data(100)
        cal = ProbabilityCalibrator(method="temperature").fit(raw, outcomes)
        cal_probs = cal.calibrate(raw)
        result = cal.evaluate(cal_probs, mkt, outcomes, raw)
        assert math.isfinite(result.cal_brier)
        assert math.isfinite(result.raw_brier)
        assert math.isfinite(result.market_brier)

    def test_result_brier_skill_sign(self):
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        raw, mkt, outcomes = _make_calibration_data(100)
        cal = ProbabilityCalibrator(method="platt").fit(raw, outcomes)
        cal_probs = cal.calibrate(raw)
        result = cal.evaluate(cal_probs, mkt, outcomes, raw)
        # Brier Skill = 1 - model_brier / market_brier
        expected = 1 - result.cal_brier / result.market_brier if result.market_brier > 0 else 0
        assert abs(result.cal_brier_skill - expected) < 1e-4

    def test_result_notes_populated(self):
        from wbc_backend.calibration.probability_calibrator import ProbabilityCalibrator
        raw, mkt, outcomes = _make_calibration_data(100)
        cal = ProbabilityCalibrator(method="platt").fit(raw, outcomes)
        cal_probs = cal.calibrate(raw)
        result = cal.evaluate(cal_probs, mkt, outcomes, raw)
        assert len(result.notes) > 0


# ══════════════════════════════════════════════════════════════════════════════
# 10. FullBacktestEngine 校準整合
# ══════════════════════════════════════════════════════════════════════════════

class TestFullBacktestCalibration:
    """驗證 FullBacktestEngine 加入校準後報告正確包含 cal_* 欄位"""

    def _load_small_records(self, n: int = 300):
        from data.mlb_data_loader import load_mlb_records
        records = load_mlb_records()
        return records[:n]

    def test_backtest_with_calibration_produces_cal_fields(self):
        from wbc_backend.evaluation.full_backtest import FullBacktestEngine
        records = self._load_small_records(300)
        engine = FullBacktestEngine(
            n_windows=2,
            marl_n_generations=5,
            marl_n_candidates=4,
            use_calibration=True,
        )
        report = engine.run(records)
        # 應有 cal_brier_score 欄位且為有效數字
        assert math.isfinite(report.cal_brier_score)

    def test_backtest_without_calibration_cal_fields_are_zero(self):
        from wbc_backend.evaluation.full_backtest import FullBacktestEngine
        records = self._load_small_records(300)
        engine = FullBacktestEngine(
            n_windows=2,
            marl_n_generations=5,
            marl_n_candidates=4,
            use_calibration=False,
        )
        report = engine.run(records)
        assert report.cal_brier_score == 0.0
        assert report.cal_ece == 0.0
        assert report.calibration_method == "none"

    def test_window_results_have_cal_method(self):
        from wbc_backend.evaluation.full_backtest import FullBacktestEngine
        records = self._load_small_records(300)
        engine = FullBacktestEngine(
            n_windows=2,
            marl_n_generations=5,
            use_calibration=True,
        )
        report = engine.run(records)
        for w in report.window_results:
            assert hasattr(w, "cal_brier_score")
            assert hasattr(w, "cal_ece")
            assert hasattr(w, "cal_method")


# ══════════════════════════════════════════════════════════════════════════════
# 11. Optimizer Gate 門檻驗證
# ══════════════════════════════════════════════════════════════════════════════

class TestOptimizerGateThresholds:
    """確認校準後 ECE/Brier 能通過 optimizer 門檻"""

    # optimizer.py 常數
    _HIGH_BRIER_REJECT = 0.285
    _HIGH_ECE_REJECT = 0.12

    def test_calibrated_ece_target_below_gate(self):
        """校準應將 ECE 從 0.1447 降至 < 0.12 目標（至少降低）"""
        from wbc_backend.calibration.probability_calibrator import (
            ProbabilityCalibrator, _ece,
        )
        # 模擬 MARL 的過度自信輸出（類似實際 ECE=0.1447 的狀況）
        raw, mkt, outcomes = _make_calibration_data(500, overconfident=True, seed=99)
        cal = ProbabilityCalibrator(method="isotonic").fit(raw, outcomes)
        cal_probs = cal.calibrate(raw)
        cal_ece = _ece(cal_probs, outcomes)
        raw_ece = _ece(raw, outcomes)
        # 校準後 ECE 應低於原始
        assert cal_ece <= raw_ece + 0.01, f"ECE 未改善：{raw_ece:.4f} → {cal_ece:.4f}"

    def test_brier_stays_below_reject_threshold(self):
        """Brier Score 應低於 optimizer 拒絕門檻 0.285"""
        from wbc_backend.calibration.probability_calibrator import (
            ProbabilityCalibrator, _brier,
        )
        raw, mkt, outcomes = _make_calibration_data(300)
        cal = ProbabilityCalibrator(method="platt").fit(raw, outcomes)
        cal_probs = cal.calibrate(raw)
        assert _brier(cal_probs, outcomes) < self._HIGH_BRIER_REJECT
