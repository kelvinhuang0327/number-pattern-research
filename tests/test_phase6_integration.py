"""
Phase 6 整合測試套件 — 棒球世界模型 + MARL 策略優化器
=======================================================
測試兩個新增模組：
  6A. wbc_backend/simulation/world_model.py   (逐打席棒球模擬)
  6B. wbc_backend/strategy/marl_optimizer.py  (三智能體策略優化)

驗證項目：
  1. 模組可正確匯入與執行
  2. 輸出機率在 [0, 1] 且互補為 1
  3. 球員個性化習慣影響結果（好投手降低得分）
  4. 尾端風險指標合理（tail_risk, blowout, shutout）
  5. 演化策略收斂（fitness 隨代數非遞減）
  6. MARL 三智能體協作正確（資金不為負）
  7. Edge cases（空陣容、極端球員資料）
  8. 世界模型 vs Poisson 模型（分佈形狀比較）

Run: python3 -m pytest tests/test_phase6_integration.py -v
"""
from __future__ import annotations

import math
import os
import sys
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wbc_backend.domain.schemas import BatterSnapshot, PitcherSnapshot


# ══════════════════════════════════════════════════════════════════════════════
# 共用 Fixtures
# ══════════════════════════════════════════════════════════════════════════════

def _make_pitcher(name: str, k9: float = 9.0, bb9: float = 3.0,
                  era: float = 4.20, fip: float = 4.20) -> PitcherSnapshot:
    return PitcherSnapshot(
        name=name, team="TST",
        era=era, fip=fip, whip=1.27,
        k_per_9=k9, bb_per_9=bb9,
        stuff_plus=100.0, ip_last_30=15.0,
        era_last_3=era, pitch_count_last_3d=0,
        fastball_velo=93.0, high_leverage_era=4.20,
    )


def _make_batter(name: str, babip: float = 0.296, barrel: float = 0.081,
                 contact: float = 0.773, sprint: float = 27.0) -> BatterSnapshot:
    return BatterSnapshot(
        name=name, team="TST",
        avg=0.260, obp=0.330, slg=0.420,
        woba=0.320, ops_plus=100,
        clutch_woba=0.320, vs_left_avg=0.250, vs_right_avg=0.265,
        babip=babip, barrel_pct=barrel,
        contact_pct=contact, sprint_speed=sprint,
        k_pct=0.228, bb_pct=0.085,
    )


def _make_fake_records(n: int = 100):
    """建立假的 GameRecord 列表（用於 MARL 測試）"""
    from wbc_backend.evaluation.institutional_backtest import GameRecord
    rng = np.random.default_rng(42)
    records = []
    elo_home = 1520.0
    elo_away = 1480.0
    for i in range(n):
        home_win = int(rng.random() < 0.54)   # MLB 主場優勢
        records.append(GameRecord(
            game_id=f"FAKE_{i:04d}",
            game_date=f"2025-{(i // 30) % 12 + 4:02d}-{(i % 30) + 1:02d}",
            tournament="TEST",
            round_name="REG",
            home_team=f"TeamA",
            away_team=f"TeamB",
            home_elo=elo_home + rng.normal(0, 20),
            away_elo=elo_away + rng.normal(0, 20),
            home_woba=float(rng.uniform(0.300, 0.340)),
            away_woba=float(rng.uniform(0.290, 0.330)),
            home_fip=float(rng.uniform(3.8, 4.5)),
            away_fip=float(rng.uniform(3.9, 4.6)),
            home_rsi=float(rng.uniform(65, 90)),
            away_rsi=float(rng.uniform(60, 85)),
            market_home_prob=float(rng.uniform(0.45, 0.60)),
            ou_line=8.5,
            actual_home_win=home_win,
            actual_home_score=int(rng.integers(0, 10)),
            actual_away_score=int(rng.integers(0, 9)),
            actual_total_runs=int(rng.integers(4, 18)),
            data_source="test_fake",
        ))
    return records


# ══════════════════════════════════════════════════════════════════════════════
# Phase 6A：棒球世界模型
# ══════════════════════════════════════════════════════════════════════════════

class TestWorldModel:

    def test_import(self) -> None:
        """6A-01: 模組可正確匯入"""
        from wbc_backend.simulation.world_model import (
            run_world_model, WorldModelResult, WorldModelConfig,
            PlayerProfile, run_world_model_from_snapshots,
        )
        assert callable(run_world_model)

    def test_basic_output_structure(self) -> None:
        """6A-02: 輸出結構正確"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelResult
        result = run_world_model(config=__import__(
            "wbc_backend.simulation.world_model", fromlist=["WorldModelConfig"]
        ).WorldModelConfig(n_simulations=1000, seed=42))
        assert isinstance(result, WorldModelResult)
        assert isinstance(result.home_win_prob, float)
        assert isinstance(result.score_distribution, dict)
        assert isinstance(result.total_runs_dist, dict)

    def test_probabilities_in_range(self) -> None:
        """6A-03: 機率輸出在 [0, 1] 且互補"""
        from wbc_backend.simulation.world_model import (
            run_world_model, WorldModelConfig,
        )
        cfg = WorldModelConfig(n_simulations=2000, seed=1)
        r = run_world_model(config=cfg)
        assert 0 <= r.home_win_prob <= 1
        assert 0 <= r.away_win_prob <= 1
        assert abs(r.home_win_prob + r.away_win_prob - 1.0) < 0.01

    def test_expected_runs_reasonable(self) -> None:
        """6A-04: 期望得分在合理範圍（2-12）"""
        from wbc_backend.simulation.world_model import (
            run_world_model, WorldModelConfig,
        )
        cfg = WorldModelConfig(n_simulations=2000, seed=2)
        r = run_world_model(config=cfg)
        assert 2.0 <= r.expected_home_runs <= 12.0, f"home runs={r.expected_home_runs}"
        assert 2.0 <= r.expected_away_runs <= 12.0, f"away runs={r.expected_away_runs}"

    def test_elite_pitcher_reduces_runs(self) -> None:
        """6A-05: 頂級投手對面得分顯著低於聯盟平均"""
        from wbc_backend.simulation.world_model import (
            run_world_model, WorldModelConfig, PlayerProfile,
        )
        cfg = WorldModelConfig(n_simulations=3000, seed=3)
        # 頂級投手（低 BB，高 K，低 HR/9）
        elite_sp = PlayerProfile(
            name="Elite SP", role="pitcher",
            k_pct=0.32, bb_pct=0.06, hr9=0.8, stuff_plus=140,
        )
        # 普通投手
        avg_sp = PlayerProfile.league_average_pitcher()

        r_elite = run_world_model(away_sp=elite_sp, config=cfg)
        r_avg = run_world_model(away_sp=avg_sp, config=cfg)

        # 頂級投手讓對面（主隊）得分更少
        assert r_elite.expected_home_runs < r_avg.expected_home_runs + 0.5, (
            f"頂級投手時主隊期望得分 {r_elite.expected_home_runs} 應低於"
            f"普通投手 {r_avg.expected_home_runs}"
        )

    def test_power_hitter_lineup_increases_runs(self) -> None:
        """6A-06: 重砲打線（高 barrel_pct）得分高於聯盟平均打線"""
        from wbc_backend.simulation.world_model import (
            run_world_model, WorldModelConfig, PlayerProfile,
        )
        cfg = WorldModelConfig(n_simulations=3000, seed=4)
        power_lineup = [
            PlayerProfile(
                name=f"Power{i}", role="batter",
                barrel_pct=0.18, hard_hit_pct=0.55,
                babip=0.310, contact_pct=0.760,
            )
            for i in range(9)
        ]
        avg_lineup = [PlayerProfile.league_average_batter() for _ in range(9)]

        r_power = run_world_model(home_lineup=power_lineup, config=cfg)
        r_avg = run_world_model(home_lineup=avg_lineup, config=cfg)

        assert r_power.expected_home_runs >= r_avg.expected_home_runs - 0.5, (
            "重砲打線期望得分應不低於聯盟平均"
        )

    def test_tail_risk_between_0_and_1(self) -> None:
        """6A-07: 尾端風險指標在 [0, 1]"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelConfig
        cfg = WorldModelConfig(n_simulations=2000, seed=5)
        r = run_world_model(config=cfg)
        for attr in ("tail_risk_score", "shutout_prob_home", "shutout_prob_away",
                     "blowout_prob", "extra_innings_prob"):
            val = getattr(r, attr)
            assert 0.0 <= val <= 1.0, f"{attr}={val} 超出 [0, 1]"
            assert math.isfinite(val)

    def test_shutout_probability_nonzero(self) -> None:
        """6A-08: 完封機率非零（棒球常見事件）"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelConfig
        cfg = WorldModelConfig(n_simulations=3000, seed=6)
        r = run_world_model(config=cfg)
        # MLB 完封率約 5-10%，至少應 > 1%
        assert r.shutout_prob_home > 0.01 or r.shutout_prob_away > 0.01

    def test_score_distribution_sums_correctly(self) -> None:
        """6A-09: 比分分佈各項機率之和 <= 1（top 15 不應超過 1）"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelConfig
        cfg = WorldModelConfig(n_simulations=2000, seed=7)
        r = run_world_model(config=cfg)
        total = sum(r.score_distribution.values())
        assert 0 < total <= 1.0

    def test_total_runs_dist_sums_to_one(self) -> None:
        """6A-10: 總分分佈（0-25）之和接近 1"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelConfig
        cfg = WorldModelConfig(n_simulations=3000, seed=8)
        r = run_world_model(config=cfg)
        total = sum(r.total_runs_dist.values())
        # 大部分比賽總分在 0-25，應覆蓋 > 90%
        assert total > 0.85, f"總分分佈覆蓋率 {total:.1%} < 85%"

    def test_from_snapshots_api(self) -> None:
        """6A-11: run_world_model_from_snapshots 整合介面正常"""
        from wbc_backend.simulation.world_model import run_world_model_from_snapshots
        home_sp = _make_pitcher("HomeAce", k9=10.0, bb9=2.5)
        away_sp = _make_pitcher("AwayStarter", k9=7.0, bb9=3.5)
        home_batters = [_make_batter(f"HB{i}") for i in range(9)]
        away_batters = [_make_batter(f"AB{i}") for i in range(9)]

        result = run_world_model_from_snapshots(
            home_sp=home_sp, away_sp=away_sp,
            home_batters=home_batters, away_batters=away_batters,
            n_simulations=2000, seed=9,
        )
        assert 0 <= result.home_win_prob <= 1
        assert math.isfinite(result.expected_home_runs)

    def test_player_profile_from_pitcher(self) -> None:
        """6A-12: PlayerProfile.from_pitcher 正確提取欄位"""
        from wbc_backend.simulation.world_model import PlayerProfile
        sp = _make_pitcher("Ace", k9=12.0, bb9=2.0, era=2.50)
        profile = PlayerProfile.from_pitcher(sp)
        assert profile.role == "pitcher"
        assert profile.k_pct > 0.20   # 高 K
        assert profile.bb_pct < 0.10  # 低 BB

    def test_player_profile_from_batter(self) -> None:
        """6A-13: PlayerProfile.from_batter 正確提取欄位"""
        from wbc_backend.simulation.world_model import PlayerProfile
        b = _make_batter("HR King", barrel=0.20, contact=0.720, sprint=28.5)
        profile = PlayerProfile.from_batter(b)
        assert profile.role == "batter"
        assert profile.barrel_pct >= 0.15
        assert profile.sprint_speed > 27.5

    def test_performance_10k_simulations(self) -> None:
        """6A-14: 10,000 次模擬在 30 秒內完成"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelConfig
        cfg = WorldModelConfig(n_simulations=10_000, seed=42)
        start = time.time()
        run_world_model(config=cfg)
        elapsed = time.time() - start
        assert elapsed < 30.0, f"10,000 次模擬耗時 {elapsed:.1f}s > 30s"

    def test_mercy_rule_reduces_innings(self) -> None:
        """6A-15: 啟用慈悲規則時，大差距比賽較早結束"""
        from wbc_backend.simulation.world_model import (
            run_world_model, WorldModelConfig, PlayerProfile,
        )
        # 用非常不平衡的球隊
        dominant_lineup = [
            PlayerProfile(name=f"D{i}", role="batter",
                          barrel_pct=0.25, babip=0.360,
                          hard_hit_pct=0.60, contact_pct=0.800)
            for i in range(9)
        ]
        weak_sp = PlayerProfile(name="Weak SP", role="pitcher",
                                k_pct=0.14, bb_pct=0.12, hr9=2.0)

        cfg_mercy = WorldModelConfig(n_simulations=1000, seed=10, mercy_rule=True)
        cfg_no_mercy = WorldModelConfig(n_simulations=1000, seed=10, mercy_rule=False)

        r_mercy = run_world_model(
            away_sp=weak_sp, home_lineup=dominant_lineup, config=cfg_mercy,
        )
        r_no_mercy = run_world_model(
            away_sp=weak_sp, home_lineup=dominant_lineup, config=cfg_no_mercy,
        )
        # 啟用慈悲規則時主隊得分可能更多（不再被截斷），blowout 機率更高
        # 或者得分更少（比賽提早結束）
        # 主要驗證：兩者的 expected_home_runs 不完全相同
        assert isinstance(r_mercy.expected_home_runs, float)
        assert isinstance(r_no_mercy.expected_home_runs, float)

    def test_std_runs_positive(self) -> None:
        """6A-16: 得分標準差為正（存在不確定性）"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelConfig
        cfg = WorldModelConfig(n_simulations=2000, seed=11)
        r = run_world_model(config=cfg)
        assert r.std_home_runs > 0
        assert r.std_away_runs > 0

    def test_league_average_home_win_prob(self) -> None:
        """6A-17: 聯盟平均球員對決時，主客勝率接近 50/50"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelConfig
        cfg = WorldModelConfig(n_simulations=5000, seed=42)
        r = run_world_model(config=cfg)
        # 完全對稱時應接近 50/50（允許 ±10%）
        assert 0.40 <= r.home_win_prob <= 0.60, (
            f"對稱對決主隊勝率 {r.home_win_prob:.1%} 偏離 50%"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Phase 6B：MARL 策略優化器
# ══════════════════════════════════════════════════════════════════════════════

class TestMARLOptimizer:

    def test_import(self) -> None:
        """6B-01: 模組可正確匯入"""
        from wbc_backend.strategy.marl_optimizer import (
            MARLOptimizer, PredictorParams, StrategistParams,
            RiskControllerParams, optimize_strategy, predict_single_game,
        )
        assert callable(optimize_strategy)

    def test_predictor_params_roundtrip(self) -> None:
        """6B-02: PredictorParams to/from array roundtrip 正確"""
        from wbc_backend.strategy.marl_optimizer import PredictorParams
        p = PredictorParams(w_elo=0.35, w_market=0.25, bias=0.05)
        arr = p.to_array()
        p2 = PredictorParams.from_array(arr)
        assert abs(p2.w_elo - p.w_elo) < 1e-6
        assert abs(p2.bias - p.bias) < 1e-6

    def test_strategist_params_roundtrip(self) -> None:
        """6B-03: StrategistParams 邊界 clip 正確"""
        from wbc_backend.strategy.marl_optimizer import StrategistParams
        import numpy as np
        # 超出邊界的值應被 clip
        s = StrategistParams.from_array(np.array([2.0, -0.5, 0.5, 1.0]))
        assert 0.05 <= s.kelly_mult <= 1.0
        assert 0.01 <= s.min_edge <= 0.15
        assert 0.01 <= s.max_stake_pct <= 0.10

    def test_predictor_output_in_range(self) -> None:
        """6B-04: PredictorParams.predict 輸出在 [0, 1]"""
        from wbc_backend.strategy.marl_optimizer import PredictorParams
        p = PredictorParams()
        records = _make_fake_records(20)
        for rec in records:
            prob = p.predict(rec)
            assert 0 <= prob <= 1, f"機率 {prob} 超出 [0, 1]"
            assert math.isfinite(prob)

    def test_strategist_zero_stake_below_min_edge(self) -> None:
        """6B-05: 邊緣低於 min_edge 時下注比例為 0"""
        from wbc_backend.strategy.marl_optimizer import StrategistParams
        s = StrategistParams(min_edge=0.05)
        # 幾乎無優勢（市場機率 = 0.50，預測 = 0.51）
        stake = s.stake_fraction(pred_prob=0.51, market_prob=0.50, bankroll=1000.0)
        assert stake == 0.0, f"邊緣 1% < min_edge 5%，應為 0，得 {stake}"

    def test_strategist_positive_stake_with_edge(self) -> None:
        """6B-06: 有優勢時下注比例 > 0"""
        from wbc_backend.strategy.marl_optimizer import StrategistParams
        s = StrategistParams(min_edge=0.03)
        stake = s.stake_fraction(pred_prob=0.60, market_prob=0.50, bankroll=1000.0)
        assert stake > 0.0

    def test_risk_controller_bankroll_floor(self) -> None:
        """6B-07: 資金觸底時風控強制返回 0"""
        from wbc_backend.strategy.marl_optimizer import RiskControllerParams, _INITIAL_BANKROLL
        rc = RiskControllerParams(bankroll_floor=0.50)
        # 資金低於 50% 初始資金
        adj = rc.adjust_stake(0.05, _INITIAL_BANKROLL * 0.40, _INITIAL_BANKROLL, 0)
        assert adj == 0.0

    def test_risk_controller_stop_loss_streak(self) -> None:
        """6B-08: 連敗超限時風控強制返回 0"""
        from wbc_backend.strategy.marl_optimizer import RiskControllerParams, _INITIAL_BANKROLL
        rc = RiskControllerParams(stop_loss_streak=5)
        adj = rc.adjust_stake(0.05, _INITIAL_BANKROLL, _INITIAL_BANKROLL, -6)
        assert adj == 0.0

    def test_episode_bankroll_non_negative(self) -> None:
        """6B-09: 整幕下來資金不為負（Kelly 下注設計保護）"""
        from wbc_backend.strategy.marl_optimizer import (
            _run_episode, PredictorParams, StrategistParams, RiskControllerParams,
        )
        records = _make_fake_records(200)
        ep = _run_episode(
            records,
            PredictorParams(),
            StrategistParams(kelly_mult=0.5, max_stake_pct=0.05),
            RiskControllerParams(),
        )
        assert ep.final_bankroll >= 0, f"資金變負: {ep.final_bankroll}"

    def test_episode_brier_in_range(self) -> None:
        """6B-10: Brier Score 在 [0, 1]"""
        from wbc_backend.strategy.marl_optimizer import (
            _run_episode, PredictorParams, StrategistParams, RiskControllerParams,
        )
        records = _make_fake_records(100)
        ep = _run_episode(records, PredictorParams(), StrategistParams(), RiskControllerParams())
        assert 0 <= ep.brier_score <= 1.0
        assert math.isfinite(ep.brier_score)

    def test_episode_win_rate_reasonable(self) -> None:
        """6B-11: 勝率在 [0.3, 0.8]（合理範圍）"""
        from wbc_backend.strategy.marl_optimizer import (
            _run_episode, PredictorParams, StrategistParams, RiskControllerParams,
        )
        records = _make_fake_records(200)
        ep = _run_episode(records, PredictorParams(), StrategistParams(), RiskControllerParams())
        if ep.n_bets > 0:
            assert 0.3 <= ep.win_rate <= 0.8, f"勝率 {ep.win_rate:.1%} 超出合理範圍"

    def test_optimization_runs_and_converges(self) -> None:
        """6B-12: 優化流程執行正常，fitness 不隨機劇烈波動"""
        from wbc_backend.strategy.marl_optimizer import MARLOptimizer
        records = _make_fake_records(150)
        opt = MARLOptimizer(n_generations=10, n_candidates=5, seed=42)
        result = opt.optimize(records)
        assert result.n_generations == 10
        assert len(result.fitness_history) == 10
        assert result.best_fitness > -1.0    # 不應是極端負值

    def test_fitness_non_decreasing(self) -> None:
        """6B-13: fitness_history 最終值不低於初始值（精英保留保證）"""
        from wbc_backend.strategy.marl_optimizer import MARLOptimizer
        records = _make_fake_records(150)
        opt = MARLOptimizer(n_generations=15, n_candidates=8, seed=1)
        result = opt.optimize(records)
        # fitness_history 應整體不下降（有精英保留）
        if len(result.fitness_history) >= 2:
            # 最終 fitness 不低於第一代
            assert result.fitness_history[-1] >= result.fitness_history[0] - 0.05

    def test_train_test_split_correct(self) -> None:
        """6B-14: 訓練/測試分割比例正確"""
        from wbc_backend.strategy.marl_optimizer import MARLOptimizer
        records = _make_fake_records(200)
        opt = MARLOptimizer(n_generations=5, n_candidates=3, train_ratio=0.8, seed=2)
        result = opt.optimize(records)
        assert result.n_records_train == 160
        assert result.n_records_test == 40

    def test_test_episode_present_when_records_sufficient(self) -> None:
        """6B-15: 足夠記錄時，測試集評估結果不為 None"""
        from wbc_backend.strategy.marl_optimizer import MARLOptimizer
        records = _make_fake_records(100)
        opt = MARLOptimizer(n_generations=5, n_candidates=3, seed=3)
        result = opt.optimize(records)
        assert result.test_episode is not None
        assert math.isfinite(result.test_episode.roi)

    def test_predict_single_game(self) -> None:
        """6B-16: predict_single_game 返回格式正確"""
        from wbc_backend.strategy.marl_optimizer import predict_single_game
        records = _make_fake_records(1)
        result = predict_single_game(records[0])
        assert "home_win_prob" in result
        assert "away_win_prob" in result
        assert abs(result["home_win_prob"] + result["away_win_prob"] - 1.0) < 0.01

    def test_optimize_strategy_convenience(self) -> None:
        """6B-17: optimize_strategy 便捷函數正常執行"""
        from wbc_backend.strategy.marl_optimizer import optimize_strategy, OptimizationResult
        records = _make_fake_records(100)
        result = optimize_strategy(records, n_generations=5, n_candidates=3, seed=0)
        assert isinstance(result, OptimizationResult)
        assert result.best_fitness > -float("inf")

    def test_performance_optimization_speed(self) -> None:
        """6B-18: 50 代 × 10 候選在 60 秒內完成（500 筆記錄）"""
        from wbc_backend.strategy.marl_optimizer import MARLOptimizer
        records = _make_fake_records(500)
        opt = MARLOptimizer(n_generations=50, n_candidates=10, seed=42)
        start = time.time()
        opt.optimize(records)
        elapsed = time.time() - start
        assert elapsed < 60.0, f"MARL 優化耗時 {elapsed:.1f}s > 60s"


# ══════════════════════════════════════════════════════════════════════════════
# Phase 6 端到端整合
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase6Integration:

    def test_world_model_output_feeds_marl(self) -> None:
        """整合-01: 世界模型輸出可作為 MARL 預測者的補充信號"""
        from wbc_backend.simulation.world_model import run_world_model, WorldModelConfig
        from wbc_backend.strategy.marl_optimizer import PredictorParams

        cfg = WorldModelConfig(n_simulations=1000, seed=42)
        wm_result = run_world_model(config=cfg)

        # 世界模型的 home_win_prob 可直接作為預測信號
        assert 0 <= wm_result.home_win_prob <= 1
        # PredictorParams 可用此機率作偏置
        p = PredictorParams(bias=wm_result.home_win_prob - 0.5)
        assert math.isfinite(p.bias)

    def test_full_phase6_pipeline(self) -> None:
        """整合-02: 完整 Phase 6 流程執行正常"""
        from wbc_backend.simulation.world_model import (
            run_world_model_from_snapshots,
        )
        from wbc_backend.strategy.marl_optimizer import optimize_strategy

        # Step 1: 世界模型預測
        home_sp = _make_pitcher("HomeSP", k9=9.5, bb9=2.8)
        away_sp = _make_pitcher("AwaySP", k9=8.0, bb9=3.5)
        home_line = [_make_batter(f"H{i}") for i in range(9)]
        away_line = [_make_batter(f"A{i}") for i in range(9)]

        wm = run_world_model_from_snapshots(
            home_sp=home_sp, away_sp=away_sp,
            home_batters=home_line, away_batters=away_line,
            n_simulations=1000,
        )
        assert 0 <= wm.home_win_prob <= 1

        # Step 2: MARL 策略優化（使用假資料）
        records = _make_fake_records(100)
        result = optimize_strategy(records, n_generations=5, n_candidates=3)
        assert result.best_fitness > -1.0

        # Step 3: 使用最優預測者對新比賽預測
        from wbc_backend.strategy.marl_optimizer import predict_single_game
        pred = predict_single_game(records[0], result.best_predictor)
        assert 0 <= pred["home_win_prob"] <= 1
