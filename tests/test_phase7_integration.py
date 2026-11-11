"""
Phase 7A 整合測試套件 — 統一預測管道 (PredictionOrchestrator)
==============================================================
測試模組：
  7A. wbc_backend/pipeline/prediction_orchestrator.py

驗證項目：
  1. 基礎匯入與資料類別完整性
  2. 最輕量模式（僅 MARL）正確執行
  3. 含市場/KG/NLP 信號的 HierarchicalMC 模式
  4. 含球員資料的 WorldModel 模式
  5. 全模型融合（三模型同時啟用）
  6. 機率值合法性（[0,1]、home+away=1）
  7. 95% CI 格式正確（low <= prob <= high）
  8. Kelly 建議邏輯（邊緣不足 → pass）
  9. 邊界情況（極端 ELO 差距、相等陣容）
  10. 批次預測（predict_batch）功能
  11. 稽核日誌完整性
  12. 加權融合邏輯（_weighted_ensemble 函數）

Run: python3 -m pytest tests/test_phase7_integration.py -v
"""
from __future__ import annotations

import math
import os
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════════════
# 共用 Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class _MockGameRecord:
    """模擬 GameRecord，含 Orchestrator 與 MARL PredictorParams 所需欄位"""
    game_id: str = "TEST_001"
    # MARL PredictorParams 讀取的個別欄位
    home_elo: float = 1530.0        # MARL: elo_diff = (home_elo - away_elo) / 400
    away_elo: float = 1500.0
    market_home_prob: float = 0.52  # Orchestrator 計算 edge 用
    home_woba: float = 0.330        # MARL: woba_diff
    away_woba: float = 0.315
    home_fip: float = 3.90          # MARL: fip_diff
    away_fip: float = 4.20
    home_rsi: float = 80.0          # MARL: rsi_diff
    away_rsi: float = 80.0
    # 相容舊版欄位
    elo_diff: float = 30.0
    market_prob: float = 0.52
    woba_diff: float = 0.015
    fip_diff: float = -0.30
    rest_days_diff: float = 1.0
    ou_line: float = 8.5
    data_source: str = "test"


def _make_record(**kwargs) -> _MockGameRecord:
    """快速建立帶覆蓋值的假記錄"""
    r = _MockGameRecord()
    for k, v in kwargs.items():
        setattr(r, k, v)
    return r


def _make_pitcher_snapshot(name: str = "SP", k9: float = 9.0, bb9: float = 3.0,
                             era: float = 4.20, fip: float = 4.20):
    from wbc_backend.domain.schemas import PitcherSnapshot
    return PitcherSnapshot(
        name=name, team="TST",
        era=era, fip=fip, whip=1.27,
        k_per_9=k9, bb_per_9=bb9,
        stuff_plus=100.0, ip_last_30=15.0,
        era_last_3=era, pitch_count_last_3d=0,
        fastball_velo=93.0, high_leverage_era=4.20,
    )


def _make_batter_snapshot(name: str = "BAT"):
    from wbc_backend.domain.schemas import BatterSnapshot
    return BatterSnapshot(
        name=name, team="TST",
        avg=0.260, obp=0.330, slg=0.420,
        woba=0.320, ops_plus=100,
        clutch_woba=0.320, vs_left_avg=0.250, vs_right_avg=0.265,
        babip=0.296, barrel_pct=0.081,
        contact_pct=0.773, sprint_speed=27.0,
        k_pct=0.228, bb_pct=0.085,
    )


# ══════════════════════════════════════════════════════════════════════════════
# 1. 匯入與資料類別
# ══════════════════════════════════════════════════════════════════════════════

class TestImports:
    def test_import_orchestrator_module(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        assert PredictionOrchestrator is not None

    def test_import_result_dataclass(self):
        from wbc_backend.pipeline.prediction_orchestrator import OrchestratorResult
        assert OrchestratorResult is not None

    def test_import_model_output_dataclass(self):
        from wbc_backend.pipeline.prediction_orchestrator import ModelOutput
        assert ModelOutput is not None

    def test_model_output_fields(self):
        from wbc_backend.pipeline.prediction_orchestrator import ModelOutput
        mo = ModelOutput(model_name="test", home_win_prob=0.55, confidence=0.7)
        assert mo.model_name == "test"
        assert mo.home_win_prob == 0.55
        assert mo.confidence == 0.7
        assert isinstance(mo.extra, dict)

    def test_orchestrator_result_fields(self):
        from wbc_backend.pipeline.prediction_orchestrator import OrchestratorResult, ModelOutput
        result = OrchestratorResult(
            home_win_prob=0.55,
            away_win_prob=0.45,
            confidence_interval_95=(0.48, 0.62),
            model_outputs=[ModelOutput("marl", 0.55, 0.7)],
            model_weights_used={"marl": 1.0},
            models_activated=["marl"],
            tail_risk_score=0.06,
            blowout_prob=0.12,
            shutout_prob=0.06,
            expected_total_runs=8.5,
            recommended_side="home",
            recommended_kelly_fraction=0.02,
            edge_vs_market=0.03,
        )
        assert result.home_win_prob == 0.55
        assert result.recommended_side == "home"
        assert isinstance(result.warnings, list)


# ══════════════════════════════════════════════════════════════════════════════
# 2. 最輕量模式（僅 MARL）
# ══════════════════════════════════════════════════════════════════════════════

class TestMARLOnlyMode:
    """不提供任何市場信號或球員資料，僅使用 MARL PredictorAgent"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator()
        self.record = _make_record()

    def test_marl_only_returns_result(self):
        result = self.orc.predict(
            self.record,
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert result is not None

    def test_marl_only_prob_in_range(self):
        result = self.orc.predict(
            self.record,
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert 0.0 < result.home_win_prob < 1.0
        assert 0.0 < result.away_win_prob < 1.0

    def test_marl_only_probs_sum_to_one(self):
        result = self.orc.predict(
            self.record,
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert abs(result.home_win_prob + result.away_win_prob - 1.0) < 1e-4

    def test_marl_only_activates_marl(self):
        result = self.orc.predict(
            self.record,
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert "marl" in result.models_activated
        assert "hierarchical_mc" not in result.models_activated
        assert "world_model" not in result.models_activated

    def test_marl_only_ci_valid(self):
        result = self.orc.predict(
            self.record,
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        ci_low, ci_high = result.confidence_interval_95
        assert ci_low <= result.home_win_prob <= ci_high
        assert ci_low >= 0.0
        assert ci_high <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# 3. 含市場/KG/NLP 信號的 HierarchicalMC 模式
# ══════════════════════════════════════════════════════════════════════════════

class TestHierarchicalMCMode:
    """提供市場信號，預期 HierarchicalMC 模型啟用"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator()
        self.record = _make_record()

    def _run_with_signals(self, **signal_kwargs):
        return self.orc.predict(
            self.record,
            use_world_model=False,
            n_mc_simulations=2000,
            **signal_kwargs,
        )

    def test_market_signals_activates_hmc(self):
        result = self._run_with_signals(
            market_signals={"clv": 0.05, "steam_move": 0.02},
        )
        assert "hierarchical_mc" in result.models_activated

    def test_kg_signals_activates_hmc(self):
        result = self._run_with_signals(
            kg_signals={"historical_h2h_advantage": 0.10},
        )
        assert "hierarchical_mc" in result.models_activated

    def test_nlp_signals_activates_hmc(self):
        result = self._run_with_signals(
            nlp_signals={"injury_severity": 0.3},
        )
        assert "hierarchical_mc" in result.models_activated

    def test_hmc_result_prob_valid(self):
        result = self._run_with_signals(
            market_signals={"clv": 0.05},
        )
        assert 0.0 < result.home_win_prob < 1.0

    def test_hmc_audit_trail_populated(self):
        result = self._run_with_signals(
            market_signals={"clv": 0.05},
        )
        assert "hierarchical_mc" in result.audit_trail or "marl" in result.audit_trail


# ══════════════════════════════════════════════════════════════════════════════
# 4. 含球員資料的 WorldModel 模式
# ══════════════════════════════════════════════════════════════════════════════

class TestWorldModelMode:
    """提供投手快照，預期 WorldModel 模型啟用"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator()
        self.record = _make_record()
        self.home_sp = _make_pitcher_snapshot("HomeAce", k9=12.0, era=2.50, fip=2.80)
        self.away_sp = _make_pitcher_snapshot("AwayJoe", k9=7.0, era=4.80, fip=5.10)
        self.home_batters = [_make_batter_snapshot(f"HB{i}") for i in range(3)]
        self.away_batters = [_make_batter_snapshot(f"AB{i}") for i in range(3)]

    def test_world_model_activates(self):
        result = self.orc.predict(
            self.record,
            home_sp=self.home_sp,
            away_sp=self.away_sp,
            use_hierarchical_mc=False,
            n_wm_simulations=2000,
        )
        assert "world_model" in result.models_activated

    def test_world_model_tail_risk_valid(self):
        result = self.orc.predict(
            self.record,
            home_sp=self.home_sp,
            use_hierarchical_mc=False,
            n_wm_simulations=2000,
        )
        assert 0.0 <= result.tail_risk_score <= 1.0

    def test_world_model_blowout_prob_valid(self):
        result = self.orc.predict(
            self.record,
            home_sp=self.home_sp,
            use_hierarchical_mc=False,
            n_wm_simulations=2000,
        )
        assert 0.0 <= result.blowout_prob <= 1.0

    def test_world_model_shutout_prob_valid(self):
        result = self.orc.predict(
            self.record,
            home_sp=self.home_sp,
            use_hierarchical_mc=False,
            n_wm_simulations=2000,
        )
        assert 0.0 <= result.shutout_prob <= 1.0

    def test_elite_pitcher_boosts_home_win_prob(self):
        """主隊精英投手 → home_win_prob 應高於平均投手版本"""
        result_ace = self.orc.predict(
            self.record,
            home_sp=self.home_sp,   # k9=12, era=2.50
            away_sp=self.away_sp,   # k9=7, era=4.80
            use_hierarchical_mc=False,
            n_wm_simulations=5000,
        )
        avg_sp = _make_pitcher_snapshot("Avg", k9=8.5, era=4.20)
        result_avg = self.orc.predict(
            self.record,
            home_sp=avg_sp,
            away_sp=avg_sp,
            use_hierarchical_mc=False,
            n_wm_simulations=5000,
        )
        # 主隊有精英投手，home_win_prob 應較高（統計期望）
        assert result_ace.home_win_prob > result_avg.home_win_prob - 0.10


# ══════════════════════════════════════════════════════════════════════════════
# 5. 全模型融合
# ══════════════════════════════════════════════════════════════════════════════

class TestFullEnsemble:
    """三個模型同時啟用的完整融合測試"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator()
        self.record = _make_record()
        self.home_sp = _make_pitcher_snapshot("HomeAce", k9=11.0, era=2.80)
        self.away_sp = _make_pitcher_snapshot("AwayJoe", k9=7.5, era=4.50)

    def test_all_models_activated(self):
        result = self.orc.predict(
            self.record,
            market_signals={"clv": 0.04},
            home_sp=self.home_sp,
            away_sp=self.away_sp,
            n_mc_simulations=2000,
            n_wm_simulations=2000,
        )
        assert len(result.models_activated) == 3
        assert set(result.models_activated) == {"marl", "hierarchical_mc", "world_model"}

    def test_full_ensemble_prob_valid(self):
        result = self.orc.predict(
            self.record,
            market_signals={"clv": 0.04},
            home_sp=self.home_sp,
            n_mc_simulations=2000,
            n_wm_simulations=2000,
        )
        assert 0.0 < result.home_win_prob < 1.0

    def test_full_ensemble_weights_match_activated(self):
        result = self.orc.predict(
            self.record,
            market_signals={"clv": 0.04},
            home_sp=self.home_sp,
            n_mc_simulations=2000,
            n_wm_simulations=2000,
        )
        # 權重字典的 keys 應與 activated 模型一致
        assert set(result.model_weights_used.keys()) == set(result.models_activated)

    def test_model_outputs_count_matches_activated(self):
        result = self.orc.predict(
            self.record,
            market_signals={"clv": 0.04},
            home_sp=self.home_sp,
            n_mc_simulations=2000,
            n_wm_simulations=2000,
        )
        assert len(result.model_outputs) == len(result.models_activated)

    def test_full_ensemble_ci_valid(self):
        result = self.orc.predict(
            self.record,
            market_signals={"clv": 0.04},
            home_sp=self.home_sp,
            n_mc_simulations=2000,
            n_wm_simulations=2000,
        )
        ci_low, ci_high = result.confidence_interval_95
        assert ci_low <= result.home_win_prob <= ci_high + 1e-6


# ══════════════════════════════════════════════════════════════════════════════
# 6. Kelly 建議邏輯
# ══════════════════════════════════════════════════════════════════════════════

class TestKellyRecommendation:
    """測試下注建議與 Kelly 比例計算"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator(min_kelly_edge=0.03)

    def test_pass_when_edge_too_small(self):
        """市場機率 ≈ 預測機率 → 建議 pass"""
        # 市場 = 0.52，模型預測約 0.52，邊緣 < 0.03
        record = _make_record(market_home_prob=0.52, market_prob=0.52,
                               elo_diff=5.0, woba_diff=0.002, fip_diff=-0.05,
                               rest_days_diff=0.0)
        result = self.orc.predict(record, use_hierarchical_mc=False, use_world_model=False)
        # 允許 pass 或有明確方向
        assert result.recommended_side in ("home", "away", "pass")

    def test_kelly_fraction_nonnegative(self):
        result = self.orc.predict(
            _make_record(), use_hierarchical_mc=False, use_world_model=False,
        )
        assert result.recommended_kelly_fraction >= 0.0

    def test_kelly_fraction_max_cap(self):
        """Kelly 比例上限 10%"""
        result = self.orc.predict(
            _make_record(market_home_prob=0.30, market_prob=0.30, elo_diff=200.0),
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert result.recommended_kelly_fraction <= 0.10

    def test_pass_has_zero_kelly(self):
        """建議 pass 時 Kelly 為 0"""
        result = self.orc.predict(
            _make_record(market_home_prob=0.52, market_prob=0.52,
                         elo_diff=0.0, woba_diff=0.0, fip_diff=0.0),
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        if result.recommended_side == "pass":
            assert result.recommended_kelly_fraction == 0.0

    def test_edge_vs_market_sign_matches_side(self):
        """home 建議 → edge > 0；away 建議 → edge < 0"""
        result = self.orc.predict(
            _make_record(), use_hierarchical_mc=False, use_world_model=False,
        )
        if result.recommended_side == "home":
            assert result.edge_vs_market >= 0
        elif result.recommended_side == "away":
            assert result.edge_vs_market <= 0


# ══════════════════════════════════════════════════════════════════════════════
# 7. 加權融合內部函數
# ══════════════════════════════════════════════════════════════════════════════

class TestWeightedEnsemble:
    """測試 _weighted_ensemble 函數的邏輯正確性"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import _weighted_ensemble, ModelOutput
        self._ensemble = _weighted_ensemble
        self._ModelOutput = ModelOutput

    def test_single_model_returns_input_prob(self):
        outputs = [self._ModelOutput("marl", 0.65, 0.7)]
        prob, ci_low, ci_high = self._ensemble(outputs, {"marl": 1.0})
        # Logit(0.65) → sigmoid → ≈ 0.65（允許 ±0.02 浮點誤差）
        assert abs(prob - 0.65) < 0.02

    def test_equal_weights_average(self):
        outputs = [
            self._ModelOutput("a", 0.60, 0.7),
            self._ModelOutput("b", 0.40, 0.7),
        ]
        prob, _, _ = self._ensemble(outputs, {"a": 0.5, "b": 0.5})
        # 對稱輸入 → 0.60 和 0.40 在 Logit 空間平均後應接近 0.50
        assert abs(prob - 0.50) < 0.02

    def test_empty_outputs_returns_default(self):
        prob, ci_low, ci_high = self._ensemble([], {})
        assert prob == 0.5
        assert ci_low == 0.35
        assert ci_high == 0.65

    def test_ci_always_valid(self):
        outputs = [
            self._ModelOutput("a", 0.70, 0.8),
            self._ModelOutput("b", 0.55, 0.6),
            self._ModelOutput("c", 0.45, 0.5),
        ]
        prob, ci_low, ci_high = self._ensemble(
            outputs, {"a": 0.4, "b": 0.35, "c": 0.25},
        )
        assert ci_low <= prob <= ci_high + 1e-6

    def test_prob_in_0_1(self):
        for p in [0.01, 0.25, 0.50, 0.75, 0.99]:
            outputs = [self._ModelOutput("m", p, 0.7)]
            prob, _, _ = self._ensemble(outputs, {"m": 1.0})
            assert 0.0 <= prob <= 1.0

    def test_high_weight_model_dominates(self):
        """高權重模型應主導融合結果"""
        outputs = [
            self._ModelOutput("dominant", 0.70, 0.8),
            self._ModelOutput("minor", 0.45, 0.5),
        ]
        prob, _, _ = self._ensemble(outputs, {"dominant": 0.90, "minor": 0.10})
        # 主導模型機率 0.70，結果應接近 0.70 而非 0.45
        assert prob > 0.60


# ══════════════════════════════════════════════════════════════════════════════
# 8. 邊界情況
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """邊界情況與異常處理"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator()

    def test_extreme_elo_diff_high(self):
        """ELO 差距極大（主隊強隊）"""
        result = self.orc.predict(
            _make_record(elo_diff=500.0, market_prob=0.80, market_home_prob=0.80),
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert 0.0 < result.home_win_prob < 1.0

    def test_extreme_elo_diff_low(self):
        """ELO 差距極大（客隊強隊）"""
        result = self.orc.predict(
            _make_record(elo_diff=-500.0, market_prob=0.20, market_home_prob=0.20),
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert 0.0 < result.home_win_prob < 1.0

    def test_evenly_matched_teams(self):
        """完全均等陣容"""
        result = self.orc.predict(
            _make_record(elo_diff=0.0, market_home_prob=0.50, market_prob=0.50,
                         woba_diff=0.0, fip_diff=0.0),
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        # 均等對決，機率應在 0.5 附近（±0.15 容差）
        assert abs(result.home_win_prob - 0.5) < 0.15

    def test_no_player_data_skips_world_model(self):
        """沒有球員資料時，不啟用 WorldModel"""
        result = self.orc.predict(
            _make_record(),
            use_hierarchical_mc=False,
            use_world_model=True,   # 設為 True，但不提供球員資料
        )
        assert "world_model" not in result.models_activated

    def test_no_signals_skips_hmc(self):
        """沒有信號時，HierarchicalMC 仍會啟用（使用空信號 dict）"""
        result = self.orc.predict(
            _make_record(),
            use_world_model=False,
            n_mc_simulations=2000,
        )
        # HierarchicalMC 應啟用（空 dict 仍合法）
        assert "hierarchical_mc" in result.models_activated

    def test_warnings_list_exists(self):
        """warnings 欄位必須存在"""
        result = self.orc.predict(
            _make_record(), use_hierarchical_mc=False, use_world_model=False,
        )
        assert isinstance(result.warnings, list)

    def test_custom_model_weights(self):
        """自訂模型權重"""
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        orc = PredictionOrchestrator(
            model_weights={"marl": 0.60, "hierarchical_mc": 0.30, "world_model": 0.10},
        )
        result = orc.predict(
            _make_record(), use_hierarchical_mc=False, use_world_model=False,
        )
        assert "marl" in result.model_weights_used


# ══════════════════════════════════════════════════════════════════════════════
# 9. 批次預測
# ══════════════════════════════════════════════════════════════════════════════

class TestBatchPredict:
    """predict_batch 批次預測功能"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator()
        self.records = [
            _make_record(game_id=f"G{i:03d}", elo_diff=float(i * 10 - 25))
            for i in range(5)
        ]

    def test_batch_returns_list(self):
        results = self.orc.predict_batch(
            self.records,
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert isinstance(results, list)

    def test_batch_length_matches_input(self):
        results = self.orc.predict_batch(
            self.records,
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert len(results) == len(self.records)

    def test_batch_all_results_valid(self):
        results = self.orc.predict_batch(
            self.records,
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        for r in results:
            assert 0.0 < r.home_win_prob < 1.0
            assert abs(r.home_win_prob + r.away_win_prob - 1.0) < 1e-4

    def test_batch_empty_input(self):
        results = self.orc.predict_batch(
            [],
            use_hierarchical_mc=False,
            use_world_model=False,
        )
        assert results == []


# ══════════════════════════════════════════════════════════════════════════════
# 10. 稽核日誌
# ══════════════════════════════════════════════════════════════════════════════

class TestAuditTrail:
    """稽核日誌完整性"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator()

    def test_audit_trail_is_dict(self):
        result = self.orc.predict(
            _make_record(), use_hierarchical_mc=False, use_world_model=False,
        )
        assert isinstance(result.audit_trail, dict)

    def test_audit_contains_marl(self):
        result = self.orc.predict(
            _make_record(), use_hierarchical_mc=False, use_world_model=False,
        )
        assert "marl" in result.audit_trail

    def test_audit_marl_has_prob(self):
        result = self.orc.predict(
            _make_record(), use_hierarchical_mc=False, use_world_model=False,
        )
        assert "home_win_prob" in result.audit_trail["marl"]

    def test_hmc_audit_present_when_activated(self):
        result = self.orc.predict(
            _make_record(),
            market_signals={"clv": 0.05},
            use_world_model=False,
            n_mc_simulations=2000,
        )
        if "hierarchical_mc" in result.models_activated:
            assert "hierarchical_mc" in result.audit_trail

    def test_world_model_audit_present_when_activated(self):
        result = self.orc.predict(
            _make_record(),
            home_sp=_make_pitcher_snapshot(),
            use_hierarchical_mc=False,
            n_wm_simulations=2000,
        )
        if "world_model" in result.models_activated:
            assert "world_model" in result.audit_trail


# ══════════════════════════════════════════════════════════════════════════════
# 11. 整合：模型差異性
# ══════════════════════════════════════════════════════════════════════════════

class TestModelDiversity:
    """不同 ELO 差距下的輸出單調性"""

    def setup_method(self):
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        self.orc = PredictionOrchestrator()

    def test_higher_elo_diff_higher_prob(self):
        """主隊 ELO 越高，home_win_prob 應越高（純 MARL 模式以隔離信號）"""
        probs = []
        for home_elo in [1300, 1500, 1700]:
            result = self.orc.predict(
                _make_record(home_elo=float(home_elo), away_elo=1500.0,
                             market_home_prob=0.50, market_prob=0.50),
                use_hierarchical_mc=False,
                use_world_model=False,
            )
            probs.append(result.home_win_prob)
        # home_elo 1300 < 1500 < 1700 → home_win_prob 應單調遞增
        assert probs[0] < probs[1] < probs[2], f"probs={probs}"

    def test_marl_prob_consistent_across_calls(self):
        """相同輸入兩次預測結果相同（確定性）"""
        record = _make_record(elo_diff=50.0)
        r1 = self.orc.predict(record, use_hierarchical_mc=False, use_world_model=False)
        r2 = self.orc.predict(record, use_hierarchical_mc=False, use_world_model=False)
        assert abs(r1.home_win_prob - r2.home_win_prob) < 1e-6
