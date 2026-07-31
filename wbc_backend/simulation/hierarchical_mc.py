"""
階層式蒙特卡洛升級 (Hierarchical Monte Carlo) — Phase 5B
=========================================================
在現有 50,000 次 Gamma-Poisson 模擬基礎上，加入 K/L/M 修正層：

  Layer 1（現有）：逐局 Gamma-Poisson 50,000 次（不改動 monte_carlo.py）
  Layer 2（新增）：市場微結構修正（MarketSimResult → 調整 λ 參數）
  Layer 3（新增）：知識圖譜加權（歷史對決優勢 → 投打能力調整）
  Layer 4（新增）：NLP 情境修正（傷兵/天氣 → 標準差動態擴張）

設計原則：
  - 向後相容：不改動 monte_carlo.py，作為獨立包裝層
  - 每層修正最大幅度有限（防止過度修正：±15% λ，±10% variance）
  - 完整稽核日誌：layer_audit 記錄每層輸入/輸出
  - 信賴區間估算：bootstrap 重複模擬取 CI（預設 5 次，成本低）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from wbc_backend.domain.schemas import PredictionResult, SimulationSummary
from wbc_backend.simulation.monte_carlo import run_monte_carlo

logger = logging.getLogger(__name__)

# ── 各層修正上限（防止過度調整）──────────────────────────────────────────
_L2_MAX_ADJ = 0.15   # Layer 2 最大 λ 調整幅度 ±15%
_L3_MAX_ADJ = 0.08   # Layer 3 最大 λ 調整幅度 ±8%
_L4_VAR_MIN = 0.10   # Layer 4 方差最小值
_L4_VAR_MAX = 0.50   # Layer 4 方差最大值


# ══════════════════════════════════════════════════════════════════════════════
# 輸出結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class HierarchicalSimResult:
    """
    階層式模擬結果（含不確定性區間）。

    home_win_prob / over_prob 為主要預測值（已整合 L2/L3/L4 修正）。
    CI 為 95% 信賴區間（bootstrap 估算）。
    layer_audit 記錄每層修正詳情，供透明度稽核。
    """
    base_result: SimulationSummary         # Layer 1 原始 MC 結果

    # 修正後最終機率
    home_win_prob: float
    away_win_prob: float
    over_prob: float
    under_prob: float

    # 95% 信賴區間（bootstrap）
    home_win_prob_ci: tuple[float, float]
    over_prob_ci: tuple[float, float]

    # 每層修正幅度（供稽核）
    layer2_market_lambda_adj: float        # 市場修正 λ 總調整量
    layer3_kg_lambda_adj: float            # 知識圖譜修正 λ 總調整量
    layer4_nlp_variance_adj: float         # NLP 方差修正量
    total_adjustment_magnitude: float      # 三層合計

    mean_total_runs: float
    std_total_runs: float

    layer_audit: dict[str, Any] = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2：市場微結構修正
# ══════════════════════════════════════════════════════════════════════════════

def _layer2_market_correction(
    market_signals: dict[str, float],
    home_lam: float,
    away_lam: float,
) -> tuple[float, float, float]:
    """
    使用博彩市場代理人模擬輸出修正 λ。

    訊號說明：
      steam_move_prob    - 蒸氣移動機率（大戶資金動向）
      clv_estimate_home  - 主隊 CLV 估算（+CLV = 主隊被低估）
      line_movement_pct  - 賠率移動幅度（正 = 主隊賠率改善）

    邏輯：
      Steam Move (>0.3) 且 CLV 為正 → 主隊 λ 微增
      賠率移動方向 → 對應方 λ 微調
    """
    steam_prob = float(market_signals.get("steam_move_prob", 0.0))
    clv_home = float(market_signals.get("clv_estimate_home", 0.0))
    line_mv = float(market_signals.get("line_movement_pct", 0.0))

    steam_dir = np.sign(clv_home) if steam_prob > 0.3 else 0.0
    steam_adj = steam_prob * 0.05 * steam_dir
    line_adj = np.clip(line_mv * 0.02, -0.04, 0.04)

    home_mult = float(np.clip(1.0 + steam_adj + line_adj, 1 - _L2_MAX_ADJ, 1 + _L2_MAX_ADJ))
    away_mult = float(np.clip(1.0 - steam_adj * 0.5, 1 - _L2_MAX_ADJ, 1 + _L2_MAX_ADJ))

    new_home = home_lam * home_mult
    new_away = away_lam * away_mult
    magnitude = abs(new_home - home_lam) + abs(new_away - away_lam)
    return new_home, new_away, round(magnitude, 5)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3：知識圖譜修正
# ══════════════════════════════════════════════════════════════════════════════

def _layer3_kg_correction(
    kg_signals: dict[str, float],
    home_lam: float,
    away_lam: float,
) -> tuple[float, float, float]:
    """
    使用知識圖譜特徵修正 λ。

    訊號說明：
      h2h_home_win_rate      - 歷史對決主隊勝率 (0-1)
      legacy_advantage_score - 球隊歷史傳承優勢 (-1 to +1)
      roster_centrality_diff - 陣容核心中心性差值

    邏輯：
      歷史對決優勢強 → 主隊 λ 提升，客隊 λ 微降
      傳承優勢加成（相對較小）
    """
    h2h = float(kg_signals.get("h2h_home_win_rate", 0.5))
    legacy = float(kg_signals.get("legacy_advantage_score", 0.0))
    centrality = float(kg_signals.get("roster_centrality_diff", 0.0))

    h2h_adv = (h2h - 0.5) * 2.0   # -1 to +1
    home_adj = np.clip(h2h_adv * 0.06 + legacy * 0.02 + centrality * 0.01, -_L3_MAX_ADJ, _L3_MAX_ADJ)
    away_adj = np.clip(-h2h_adv * 0.04, -_L3_MAX_ADJ / 2, _L3_MAX_ADJ / 2)

    new_home = home_lam * (1.0 + float(home_adj))
    new_away = away_lam * (1.0 + float(away_adj))
    magnitude = abs(new_home - home_lam) + abs(new_away - away_lam)
    return new_home, new_away, round(magnitude, 5)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 4：NLP 情境方差修正
# ══════════════════════════════════════════════════════════════════════════════

def _layer4_nlp_variance_correction(
    nlp_signals: dict[str, float],
    base_variance: float,
) -> tuple[float, float]:
    """
    使用 NLP 語義特徵動態調整蒙特卡洛方差。

    訊號說明：
      injury_severity_score   - 傷兵嚴重度 (0-1)
      weather_impact_score    - 天氣影響度 (0-1)
      pregame_sentiment_score - 賽前情緒分數 (0=負面, 1=正面)

    邏輯：
      傷兵嚴重 → 不確定性增加 → variance_add 提升
      惡劣天氣 → 不確定性增加 → variance_add 提升
      正面情緒 → 輕微降低不確定性（相對穩定）
    """
    injury = float(np.clip(nlp_signals.get("injury_severity_score", 0.0), 0.0, 1.0))
    weather = float(np.clip(nlp_signals.get("weather_impact_score", 0.0), 0.0, 1.0))
    sentiment = float(np.clip(nlp_signals.get("pregame_sentiment_score", 0.5), 0.0, 1.0))

    adj = injury * 0.20 + weather * 0.15 - (sentiment - 0.5) * 0.10
    new_variance = float(np.clip(base_variance + adj, _L4_VAR_MIN, _L4_VAR_MAX))
    magnitude = abs(new_variance - base_variance)
    return new_variance, round(magnitude, 5)


# ══════════════════════════════════════════════════════════════════════════════
# 主要 API
# ══════════════════════════════════════════════════════════════════════════════

def run_hierarchical_monte_carlo(
    pred: PredictionResult,
    line_total: float = 7.5,
    line_spread_home: float = -1.5,
    simulations: int = 50_000,
    seed: int = 42,
    # Layer-specific inputs (None = 跳過該層修正)
    market_signals: Optional[dict[str, float]] = None,   # Layer 2
    kg_signals: Optional[dict[str, float]] = None,       # Layer 3
    nlp_signals: Optional[dict[str, float]] = None,      # Layer 4
    # 先發/牛棚疲勞（直接傳入 base MC）
    home_sp_fatigue: float = 0.0,
    away_sp_fatigue: float = 0.0,
    home_bullpen_stress: float = 0.0,
    away_bullpen_stress: float = 0.0,
    # 信賴區間 bootstrap 次數（少以節省時間）
    ci_bootstrap_runs: int = 5,
) -> HierarchicalSimResult:
    """
    執行階層式蒙特卡洛模擬（四層修正架構）。

    Args:
        pred: 基礎預測結果（含期望得分）
        line_total: 大小分盤口線
        line_spread_home: 讓分盤口線
        simulations: 模擬次數（推薦 50,000）
        seed: 亂數種子
        market_signals: Layer 2 市場微結構特徵 dict
          （鍵：steam_move_prob, clv_estimate_home, line_movement_pct）
        kg_signals: Layer 3 知識圖譜特徵 dict
          （鍵：h2h_home_win_rate, legacy_advantage_score, roster_centrality_diff）
        nlp_signals: Layer 4 NLP 語義特徵 dict
          （鍵：injury_severity_score, weather_impact_score, pregame_sentiment_score）
        home_sp_fatigue / away_sp_fatigue: 先發投手疲勞度 (0-1)
        home_bullpen_stress / away_bullpen_stress: 牛棚壓力 (0-1)
        ci_bootstrap_runs: CI 估算用的重複模擬次數（較少次保持效能）

    Returns:
        HierarchicalSimResult（含修正後機率、CI、稽核日誌）
    """
    market_signals = market_signals or {}
    kg_signals = kg_signals or {}
    nlp_signals = nlp_signals or {}

    base_lam_home = max(0.5, pred.expected_home_runs) / 9.0
    base_lam_away = max(0.5, pred.expected_away_runs) / 9.0
    base_variance = 0.18  # WBC 預設方差

    # ── Layer 2：市場修正 ────────────────────────────────────────────────────
    l2_home, l2_away, l2_mag = _layer2_market_correction(
        market_signals, base_lam_home, base_lam_away,
    )

    # ── Layer 3：知識圖譜修正 ─────────────────────────────────────────────────
    l3_home, l3_away, l3_mag = _layer3_kg_correction(
        kg_signals, l2_home, l2_away,
    )

    # ── Layer 4：NLP 方差修正 ─────────────────────────────────────────────────
    l4_variance, l4_mag = _layer4_nlp_variance_correction(nlp_signals, base_variance)

    # ── 建構修正後的 PredictionResult ────────────────────────────────────────
    adj_pred = PredictionResult(
        game_id=pred.game_id,
        home_win_prob=pred.home_win_prob,
        away_win_prob=pred.away_win_prob,
        expected_home_runs=float(l3_home * 9.0),
        expected_away_runs=float(l3_away * 9.0),
        x_factors=pred.x_factors,
        diagnostics=pred.diagnostics,
        sub_model_results=pred.sub_model_results,
        confidence_score=pred.confidence_score,
        market_bias_score=pred.market_bias_score,
    )

    # ── Layer 1：主模擬（含 L2/L3/L4 修正後參數）────────────────────────────
    base_result = run_monte_carlo(
        pred=adj_pred,
        line_total=line_total,
        line_spread_home=line_spread_home,
        simulations=simulations,
        seed=seed,
        home_sp_fatigue=home_sp_fatigue,
        away_sp_fatigue=away_sp_fatigue,
        home_bullpen_stress=home_bullpen_stress,
        away_bullpen_stress=away_bullpen_stress,
        wbc_variance_add=l4_variance,
    )

    # ── CI 估算（bootstrap）─────────────────────────────────────────────────
    hw_samples: list[float] = [base_result.home_win_prob]
    ov_samples: list[float] = [base_result.over_prob]
    mini_sims = max(5_000, simulations // 10)

    for i in range(1, ci_bootstrap_runs):
        bt = run_monte_carlo(
            pred=adj_pred,
            line_total=line_total,
            line_spread_home=line_spread_home,
            simulations=mini_sims,
            seed=seed + i * 1000,
            home_sp_fatigue=home_sp_fatigue,
            away_sp_fatigue=away_sp_fatigue,
            home_bullpen_stress=home_bullpen_stress,
            away_bullpen_stress=away_bullpen_stress,
            wbc_variance_add=l4_variance,
        )
        hw_samples.append(bt.home_win_prob)
        ov_samples.append(bt.over_prob)

    hw_arr = np.array(hw_samples)
    ov_arr = np.array(ov_samples)
    hw_ci = (
        round(float(np.percentile(hw_arr, 2.5)), 4),
        round(float(np.percentile(hw_arr, 97.5)), 4),
    )
    ov_ci = (
        round(float(np.percentile(ov_arr, 2.5)), 4),
        round(float(np.percentile(ov_arr, 97.5)), 4),
    )

    return HierarchicalSimResult(
        base_result=base_result,
        home_win_prob=round(base_result.home_win_prob, 4),
        away_win_prob=round(base_result.away_win_prob, 4),
        over_prob=round(base_result.over_prob, 4),
        under_prob=round(base_result.under_prob, 4),
        home_win_prob_ci=hw_ci,
        over_prob_ci=ov_ci,
        layer2_market_lambda_adj=l2_mag,
        layer3_kg_lambda_adj=l3_mag,
        layer4_nlp_variance_adj=l4_mag,
        total_adjustment_magnitude=round(l2_mag + l3_mag + l4_mag, 5),
        mean_total_runs=base_result.mean_total_runs,
        std_total_runs=base_result.std_total_runs,
        layer_audit={
            "layer2_market": {
                "signals": {k: round(v, 4) for k, v in market_signals.items()},
                "lam_home_before": round(base_lam_home, 4),
                "lam_home_after": round(l2_home, 4),
                "lam_away_before": round(base_lam_away, 4),
                "lam_away_after": round(l2_away, 4),
                "adj_magnitude": l2_mag,
            },
            "layer3_kg": {
                "signals": {k: round(v, 4) for k, v in kg_signals.items()},
                "lam_home_before": round(l2_home, 4),
                "lam_home_after": round(l3_home, 4),
                "lam_away_before": round(l2_away, 4),
                "lam_away_after": round(l3_away, 4),
                "adj_magnitude": l3_mag,
            },
            "layer4_nlp": {
                "signals": {k: round(v, 4) for k, v in nlp_signals.items()},
                "variance_before": round(base_variance, 4),
                "variance_after": round(l4_variance, 4),
                "adj_magnitude": l4_mag,
            },
        },
    )
