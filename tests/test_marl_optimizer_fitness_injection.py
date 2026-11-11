"""
P5-B — marl_optimizer.py fitness_fn 介面注入測試
=================================================
驗證最小化修改後的 optimizer 行為：
- 未傳 fitness_fn 時既有行為不變
- 傳入 fitness_fn 時使用 risk-adjusted score
- fitness_fn 回傳 insufficient_sample 結果時 blocked
- fitness_fn 回傳 CI 跨 0 結果時 blocked（透過 champion_gate 驗證）
- ev_proxy 欄位不允許通過
- paper_only=false 直接 fail
"""
import sys
import os
import math

# 確保 worktree 路徑在 sys.path 前列
_WORKTREE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _WORKTREE not in sys.path:
    sys.path.insert(0, _WORKTREE)

import pytest
from dataclasses import dataclass
from typing import Optional, Any


# ── 最小化 GameRecord stub（供 marl_optimizer 使用） ──────────────────────────

@dataclass
class _GameRecord:
    home_elo: float = 1500.0
    away_elo: float = 1500.0
    market_home_prob: float = 0.5
    home_woba: float = 0.317
    away_woba: float = 0.317
    home_fip: float = 4.20
    away_fip: float = 4.20
    home_rsi: float = 80.0
    away_rsi: float = 80.0
    actual_home_win: Optional[int] = 1


def _make_records(n: int = 60, seed: int = 0) -> list:
    """建立 n 筆 GameRecord stub，actual_home_win 交替 0/1。"""
    records = []
    for i in range(n):
        records.append(_GameRecord(
            home_elo=1500.0 + (i % 10) * 5,
            away_elo=1500.0 - (i % 7) * 3,
            market_home_prob=0.48 + (i % 5) * 0.01,
            actual_home_win=i % 2,
        ))
    return records


# ── Test 1: 未傳 fitness_fn 時既有行為不變 ───────────────────────────────────

def test_no_fitness_fn_uses_internal_episode_fitness():
    """未注入 fitness_fn 時，optimizer 使用內部 episode.fitness（原始行為）。"""
    from wbc_backend.strategy.marl_optimizer import MARLOptimizer

    records = _make_records(60)
    opt_default = MARLOptimizer(n_generations=2, n_candidates=3, seed=42)
    opt_no_fn = MARLOptimizer(n_generations=2, n_candidates=3, seed=42, fitness_fn=None)

    result_default = opt_default.optimize(records)
    result_no_fn = opt_no_fn.optimize(records)

    # fitness_fn=None 與不傳結果完全一致
    assert abs(result_default.best_fitness - result_no_fn.best_fitness) < 1e-9


# ── Test 2: 傳入 fitness_fn 時使用 risk-adjusted score ───────────────────────

def test_custom_fitness_fn_overrides_episode_fitness():
    """傳入自訂 fitness_fn 時，optimizer 使用其回傳分數。"""
    from wbc_backend.strategy.marl_optimizer import MARLOptimizer, EpisodeResult

    call_count = {"n": 0}

    def always_high_fitness(ep: EpisodeResult) -> float:
        """永遠回傳固定高分，確認 optimizer 使用此分數。"""
        call_count["n"] += 1
        return 999.0

    records = _make_records(60)
    opt = MARLOptimizer(n_generations=2, n_candidates=3, seed=42, fitness_fn=always_high_fitness)
    result = opt.optimize(records)

    # fitness_fn 被呼叫過（每代每個 candidate + 精英保留）
    assert call_count["n"] > 0
    # best_fitness 應等於 fitness_fn 回傳的分數
    assert result.best_fitness == pytest.approx(999.0, abs=1e-6)


# ── Test 3: fitness_fn 識別 insufficient_sample → champion gate 封鎖 ─────────

def test_insufficient_sample_fitness_blocked_by_champion_gate():
    """
    fitness_fn 回傳 insufficient_sample 結果（fitness_score=-999）時，
    champion gate 應封鎖升級。
    """
    from wbc_backend.recommendation.optimizer_fitness import champion_gate

    champion = {
        "roi": 0.018384, "ci_low": -0.03895, "ci_high": 0.076413,
        "p_value": 0.535846, "sample_size": 1319,
        "status": "ok", "positive_fold_ratio": 0.571,
        "fitness_score": -0.03895,
    }
    challenger = {
        "roi": 0.05, "ci_low": -999.0, "ci_high": 999.0,
        "p_value": 1.0, "sample_size": 10,
        "status": "insufficient_sample", "positive_fold_ratio": 0.0,
        "fitness_score": -999.0,
    }
    result = champion_gate(champion, challenger)
    assert result["upgrade"] is False
    assert "insufficient_sample" in result["reason"]


# ── Test 4: fitness_fn 回傳 CI 跨 0 → champion gate 封鎖 ────────────────────

def test_ci_crosses_zero_fitness_blocked_by_champion_gate():
    """
    challenger ci_low <= 0 時 champion gate 封鎖，即使 raw ROI 較高。
    """
    from wbc_backend.recommendation.optimizer_fitness import champion_gate

    champion = {
        "roi": 0.018384, "ci_low": -0.03895,
        "p_value": 0.535846, "sample_size": 1319,
        "status": "ok", "positive_fold_ratio": 0.571,
        "fitness_score": -0.03895,
    }
    challenger = {
        "roi": 0.10,       # raw ROI 較高
        "ci_low": -0.02,   # 但 CI 跨 0
        "p_value": 0.08,
        "sample_size": 200,
        "status": "ok",
        "positive_fold_ratio": 0.6,
        "fitness_score": -0.02,
    }
    result = champion_gate(champion, challenger)
    assert result["upgrade"] is False
    assert "CI 跨 0" in result["reason"] or "ci_low" in result["reason"]


# ── Test 5: ev_proxy 欄位不允許進入 fitness 計算 ─────────────────────────────

def test_ev_proxy_field_raises_in_fitness():
    """任何含 ev_proxy_* 欄位的 records 傳入 compute_risk_adjusted_fitness 應 raise。"""
    from wbc_backend.recommendation.optimizer_fitness import compute_risk_adjusted_fitness

    records = [
        {
            "paper_only": True,
            "ambiguous_doubleheader": False,
            "actual_home_win": 1,
            "bet_side": "HOME",
            "stake_unit": 0.05,
            "home_ml_odds": -110.0,
            "walk_forward_fold": 1,
            "ev_proxy_roi": 0.12,    # 禁止欄位
        }
    ]
    with pytest.raises(ValueError, match="ev_proxy"):
        compute_risk_adjusted_fitness(records)


# ── Test 6: paper_only=false 直接 fail ──────────────────────────────────────

def test_paper_only_false_raises_in_fitness():
    """paper_only=false 記錄傳入 compute_risk_adjusted_fitness 應 raise。"""
    from wbc_backend.recommendation.optimizer_fitness import compute_risk_adjusted_fitness

    records = [
        {
            "paper_only": False,    # 禁止
            "ambiguous_doubleheader": False,
            "actual_home_win": 1,
            "bet_side": "HOME",
            "stake_unit": 0.05,
            "home_ml_odds": -110.0,
            "walk_forward_fold": 1,
        }
    ]
    with pytest.raises(ValueError, match="paper_only=false"):
        compute_risk_adjusted_fitness(records)


# ── Test 7: optimize_strategy 傳 fitness_fn 的介面簽章正確 ─────────────────

def test_optimize_strategy_accepts_fitness_fn_kwarg():
    """optimize_strategy() 接受 fitness_fn 參數，不 raise TypeError。"""
    from wbc_backend.strategy.marl_optimizer import optimize_strategy, EpisodeResult

    records = _make_records(60)

    def dummy_fn(ep: EpisodeResult) -> float:
        return ep.roi  # 以 ROI 作為 fitness

    # 不應拋出 TypeError
    result = optimize_strategy(records, n_generations=2, n_candidates=3, seed=42, fitness_fn=dummy_fn)
    assert hasattr(result, "best_fitness")
