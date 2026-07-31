"""
多智能體強化學習策略優化器 (MARL Optimizer) — Phase 6B
=======================================================
讓三個協作智能體透過演化策略（ES）在歷史資料上自我對弈，
湧現最優下注參數組合。

智能體設計：
  Agent 1 — PredictorAgent（預測者）
    目標：最大化預測精度（最小化 Brier Score）
    參數：ELO/市場/RSI/wOBA/FIP 各特徵的加權係數

  Agent 2 — StrategistAgent（策略者）
    目標：最大化期望 ROI
    參數：Kelly 乘數、最低邊緣門檻（min_edge）、單場最大曝險

  Agent 3 — RiskControllerAgent（風控者）
    目標：最小化破產機率（最大化 Sharpe Ratio）
    參數：最大回撤門檻、曝險上限、最低資金底線

協作機制：
  PredictorAgent → 輸出預測機率
  StrategistAgent → 基於機率決定是否下注及大小
  RiskControllerAgent → 審核並調整下注金額

優化算法：
  CMA-ES 輕量版（Evolution Strategy + 協方差自適應）
  → 無梯度，適合非可微目標函數
  → 純 Python + NumPy，無需 PyTorch/TF

輸入：list[GameRecord]（機構回測格式）
輸出：OptimizationResult（含最優參數 + 各 Agent 最終表現）
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── 全域設定 ─────────────────────────────────────────────────────────────────
_INITIAL_BANKROLL = 1000.0
_BRIER_WEIGHT = 0.4      # Brier Score 在 fitness 中的權重
_ROI_WEIGHT = 0.4        # ROI 的權重
_SHARPE_WEIGHT = 0.2     # Sharpe Ratio 的權重


# ══════════════════════════════════════════════════════════════════════════════
# 智能體參數（各智能體的可學習參數）
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class PredictorParams:
    """
    預測者智能體參數。
    預測機率 = sigmoid(w_elo * elo_diff + w_market * market_prob + ...)
    """
    w_elo: float = 0.40          # ELO 差值的權重
    w_market: float = 0.30       # 市場隱含機率的權重
    w_woba: float = 0.15         # wOBA 差值的權重
    w_fip: float = 0.10          # FIP 差值的權重（負相關）
    w_rsi: float = 0.05          # RSI（動量）的權重
    bias: float = 0.0            # 偏置項

    def to_array(self) -> np.ndarray:
        return np.array([self.w_elo, self.w_market, self.w_woba,
                         self.w_fip, self.w_rsi, self.bias])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "PredictorParams":
        return cls(
            w_elo=float(arr[0]),
            w_market=float(arr[1]),
            w_woba=float(arr[2]),
            w_fip=float(arr[3]),
            w_rsi=float(arr[4]),
            bias=float(arr[5]),
        )

    def predict(self, record: Any) -> float:
        """
        給定一筆 GameRecord 輸出主隊勝率預測 [0, 1]。
        使用 Logistic 函數確保輸出有界。
        """
        elo_diff = (getattr(record, "home_elo", 1500) -
                    getattr(record, "away_elo", 1500)) / 400.0
        market = getattr(record, "market_home_prob", 0.5)
        woba_diff = (getattr(record, "home_woba", 0.317) -
                     getattr(record, "away_woba", 0.317)) * 5.0  # 放大
        fip_diff = -(getattr(record, "home_fip", 4.20) -
                     getattr(record, "away_fip", 4.20)) * 0.2    # 負相關
        rsi_diff = (getattr(record, "home_rsi", 80) -
                    getattr(record, "away_rsi", 80)) / 100.0

        score = (self.w_elo * elo_diff +
                 self.w_market * (market - 0.5) * 2 +
                 self.w_woba * woba_diff +
                 self.w_fip * fip_diff +
                 self.w_rsi * rsi_diff +
                 self.bias)
        return float(1.0 / (1.0 + math.exp(-score * 2.0)))


@dataclass
class StrategistParams:
    """
    策略者智能體參數。
    下注大小 = kelly_mult × Kelly_fraction
    """
    kelly_mult: float = 0.25     # Kelly 乘數（0.25 = 1/4 Kelly）
    min_edge: float = 0.03       # 最低優勢門檻（低於此不下注）
    max_stake_pct: float = 0.05  # 單場最大下注比例（資金的 5%）
    fade_public: float = 0.0     # 逆公眾下注力度（0 = 不逆，正 = 逆公眾）

    def to_array(self) -> np.ndarray:
        return np.array([self.kelly_mult, self.min_edge,
                         self.max_stake_pct, self.fade_public])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "StrategistParams":
        return cls(
            kelly_mult=float(np.clip(arr[0], 0.05, 1.0)),
            min_edge=float(np.clip(arr[1], 0.01, 0.15)),
            max_stake_pct=float(np.clip(arr[2], 0.01, 0.10)),
            fade_public=float(np.clip(arr[3], -0.5, 0.5)),
        )

    def stake_fraction(
        self,
        pred_prob: float,
        market_prob: float,
        bankroll: float,
    ) -> float:
        """
        計算建議下注比例（占當前資金）。
        Kelly = edge / odds
        """
        edge = pred_prob - market_prob
        # 逆公眾修正（公眾下注方向已知時）
        edge += self.fade_public * (0.5 - market_prob) * 0.3

        if edge < self.min_edge:
            return 0.0

        # Kelly Criterion（正常賭注 -110，隱含賠率 ≈ 0.909）
        implied_odds = market_prob / (1 - market_prob + 1e-8)
        kelly = edge / max(implied_odds, 0.1)
        fraction = self.kelly_mult * kelly
        return float(np.clip(fraction, 0.0, self.max_stake_pct))


@dataclass
class RiskControllerParams:
    """
    風控者智能體參數。
    """
    max_drawdown: float = 0.20   # 最大允許回撤（20% 資金）
    bankroll_floor: float = 0.50 # 資金不得低於初始的 50%
    max_daily_exposure: float = 0.15  # 單日最大曝險（15% 資金）
    stop_loss_streak: int = 5    # 連敗多少場後暫停

    def to_array(self) -> np.ndarray:
        return np.array([self.max_drawdown, self.bankroll_floor,
                         self.max_daily_exposure, float(self.stop_loss_streak)])

    @classmethod
    def from_array(cls, arr: np.ndarray) -> "RiskControllerParams":
        return cls(
            max_drawdown=float(np.clip(arr[0], 0.05, 0.50)),
            bankroll_floor=float(np.clip(arr[1], 0.20, 0.80)),
            max_daily_exposure=float(np.clip(arr[2], 0.05, 0.30)),
            stop_loss_streak=int(np.clip(arr[3], 2, 15)),
        )

    def adjust_stake(
        self,
        proposed_fraction: float,
        bankroll: float,
        peak_bankroll: float,
        current_streak: int,
    ) -> float:
        """
        審核並調整下注比例。
        若觸發任何風控條件，縮減或歸零下注。
        """
        if bankroll < _INITIAL_BANKROLL * self.bankroll_floor:
            return 0.0   # 觸碰資金底線，停止下注

        if current_streak <= -self.stop_loss_streak:
            return 0.0   # 連敗超限，暫停

        drawdown = (peak_bankroll - bankroll) / (peak_bankroll + 1e-8)
        if drawdown > self.max_drawdown:
            return proposed_fraction * 0.5   # 大回撤時縮半

        return proposed_fraction


# ══════════════════════════════════════════════════════════════════════════════
# 輸出結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EpisodeResult:
    """單次優化幕（episode）的結果"""
    final_bankroll: float
    peak_bankroll: float
    roi: float               # (final - initial) / initial
    n_bets: int
    n_wins: int
    brier_score: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    fitness: float           # 綜合 fitness 分數（越高越好）


@dataclass
class OptimizationResult:
    """MARL 優化完整結果"""
    best_predictor: PredictorParams
    best_strategist: StrategistParams
    best_risk_controller: RiskControllerParams
    best_fitness: float
    best_episode: EpisodeResult
    # 訓練曲線（每代最佳 fitness）
    fitness_history: list[float] = field(default_factory=list)
    # 最終評估（測試集）
    test_episode: Optional[EpisodeResult] = None
    n_generations: int = 0
    n_records_train: int = 0
    n_records_test: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# 模擬幕（Episode）
# ══════════════════════════════════════════════════════════════════════════════

def _run_episode(
    records: list,
    predictor: PredictorParams,
    strategist: StrategistParams,
    risk_ctrl: RiskControllerParams,
    initial_bankroll: float = _INITIAL_BANKROLL,
) -> EpisodeResult:
    """
    執行一幕：按時序遍歷所有 GameRecord，三個智能體協作下注。

    每一場比賽：
      1. Predictor → 預測主隊勝率
      2. Strategist → 決定下注大小（含邊緣門檻）
      3. RiskController → 審核並調整
      4. 結算：比賽結果更新資金

    Args:
        records: 按日期排序的 GameRecord 列表
        predictor / strategist / risk_ctrl: 各智能體當前參數
        initial_bankroll: 起始資金

    Returns:
        EpisodeResult（含 ROI、Brier、Sharpe 等指標）
    """
    bankroll = initial_bankroll
    peak_bankroll = initial_bankroll

    brier_sum = 0.0
    returns: list[float] = []    # 每筆下注的回報率（用於 Sharpe）
    n_bets = 0
    n_wins = 0
    current_streak = 0          # 正=連勝，負=連敗
    min_bankroll = bankroll

    for rec in records:
        # ── Predictor：預測主隊勝率 ──────────────────────────────────────────
        pred_prob = predictor.predict(rec)
        actual_win = getattr(rec, "actual_home_win", None)
        if actual_win is None:
            continue

        # Brier Score 累積
        brier_sum += (pred_prob - actual_win) ** 2

        # ── Strategist：決定下注方向和大小 ──────────────────────────────────
        market_prob = getattr(rec, "market_home_prob", 0.5)
        fraction = strategist.stake_fraction(pred_prob, market_prob, bankroll)

        # ── RiskController：審核 ─────────────────────────────────────────────
        fraction = risk_ctrl.adjust_stake(
            fraction, bankroll, peak_bankroll, current_streak,
        )

        if fraction <= 0 or bankroll < 10:
            continue   # 不下注

        stake = bankroll * fraction
        n_bets += 1

        # ── 結算（假設賠率 -110，勝率 10/11 ≈ 0.909） ────────────────────────
        # 若預測主隊且主隊勝 → 贏錢；否則輸 stake
        bet_on_home = pred_prob > market_prob
        if bet_on_home:
            if actual_win == 1:
                pnl = stake * (100 / 110)   # -110 賠率
                n_wins += 1
                current_streak = max(0, current_streak) + 1
            else:
                pnl = -stake
                current_streak = min(0, current_streak) - 1
        else:
            # 下注客隊
            if actual_win == 0:
                pnl = stake * (100 / 110)
                n_wins += 1
                current_streak = max(0, current_streak) + 1
            else:
                pnl = -stake
                current_streak = min(0, current_streak) - 1

        bankroll += pnl
        returns.append(pnl / (stake + 1e-8))   # 單筆回報率

        peak_bankroll = max(peak_bankroll, bankroll)
        min_bankroll = min(min_bankroll, bankroll)

    # ── 計算績效指標 ──────────────────────────────────────────────────────────
    n_records = len(records)
    brier_score = brier_sum / max(n_records, 1)
    roi = (bankroll - initial_bankroll) / initial_bankroll

    if len(returns) >= 2:
        ret_arr = np.array(returns)
        sharpe = (float(ret_arr.mean()) / (float(ret_arr.std()) + 1e-8)) * math.sqrt(252)
    else:
        sharpe = 0.0

    max_drawdown = (peak_bankroll - min_bankroll) / (peak_bankroll + 1e-8)
    win_rate = n_wins / max(n_bets, 1)

    # ── 綜合 Fitness（越高越好） ──────────────────────────────────────────────
    # ROI（正 = 好，限制 [-0.5, 2.0]）
    roi_norm = float(np.clip(roi, -0.5, 2.0)) / 2.0
    # Brier（越低越好，正規化後反轉）
    brier_norm = max(0.0, 1.0 - brier_score / 0.25)
    # Sharpe（限制 [-1, 3]，正規化）
    sharpe_norm = float(np.clip(sharpe, -1.0, 3.0)) / 3.0

    fitness = (
        _BRIER_WEIGHT * brier_norm +
        _ROI_WEIGHT * roi_norm +
        _SHARPE_WEIGHT * sharpe_norm
    )

    return EpisodeResult(
        final_bankroll=round(bankroll, 2),
        peak_bankroll=round(peak_bankroll, 2),
        roi=round(roi, 4),
        n_bets=n_bets,
        n_wins=n_wins,
        brier_score=round(brier_score, 5),
        sharpe_ratio=round(sharpe, 3),
        max_drawdown=round(max_drawdown, 4),
        win_rate=round(win_rate, 4),
        fitness=round(fitness, 5),
    )


# ══════════════════════════════════════════════════════════════════════════════
# 演化策略優化
# ══════════════════════════════════════════════════════════════════════════════

def _perturb(arr: np.ndarray, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """加入高斯噪音（Evolution Strategy 擾動）"""
    return arr + rng.normal(0, sigma, size=arr.shape)


class MARLOptimizer:
    """
    三智能體協作演化策略優化器。

    算法：(1 + λ)-ES
      - 每代：從當前最優解產生 λ 個擾動候選
      - 各候選在訓練集上執行一幕
      - 保留最優候選更新當前解
      - 重複 n_generations 代
    """

    def __init__(
        self,
        n_generations: int = 50,
        n_candidates: int = 10,    # 每代候選數（λ）
        sigma_init: float = 0.10,  # 初始擾動幅度
        sigma_decay: float = 0.98, # 擾動衰減率（模擬退火）
        train_ratio: float = 0.80, # 訓練/測試分割比
        seed: int = 42,
    ):
        self.n_generations = n_generations
        self.n_candidates = n_candidates
        self.sigma = sigma_init
        self.sigma_decay = sigma_decay
        self.train_ratio = train_ratio
        self.rng = np.random.default_rng(seed)

    def optimize(self, records: list) -> OptimizationResult:
        """
        在 GameRecord 列表上執行完整優化流程。

        Args:
            records: 已按日期排序的 GameRecord 列表（需 >= 50 筆）

        Returns:
            OptimizationResult（含最優參數和測試集表現）
        """
        n = len(records)
        if n < 50:
            logger.warning("記錄數 %d < 50，優化結果可信度低", n)

        # 訓練/測試分割（Walk-Forward：訓練在前）
        split = int(n * self.train_ratio)
        train_records = records[:split]
        test_records = records[split:]

        logger.info(
            "MARL 優化開始：%d 訓練 / %d 測試，%d 代 × %d 候選",
            len(train_records), len(test_records),
            self.n_generations, self.n_candidates,
        )

        # 初始化最優解（預設參數）
        best_pred = PredictorParams()
        best_strat = StrategistParams()
        best_risk = RiskControllerParams()
        best_fitness = -float("inf")
        fitness_history: list[float] = []

        for gen in range(self.n_generations):
            # 產生 λ 個候選解
            candidates: list[tuple[PredictorParams, StrategistParams, RiskControllerParams]] = []
            for _ in range(self.n_candidates):
                p_arr = _perturb(best_pred.to_array(), self.sigma, self.rng)
                s_arr = _perturb(best_strat.to_array(), self.sigma, self.rng)
                r_arr = _perturb(best_risk.to_array(), self.sigma, self.rng)
                candidates.append((
                    PredictorParams.from_array(p_arr),
                    StrategistParams.from_array(s_arr),
                    RiskControllerParams.from_array(r_arr),
                ))

            # 也加入當前最優（精英保留）
            candidates.append((best_pred, best_strat, best_risk))

            # 評估每個候選
            gen_best_fitness = -float("inf")
            gen_best_pred, gen_best_strat, gen_best_risk = best_pred, best_strat, best_risk

            for pred, strat, risk in candidates:
                ep = _run_episode(train_records, pred, strat, risk)
                if ep.fitness > gen_best_fitness:
                    gen_best_fitness = ep.fitness
                    gen_best_pred = pred
                    gen_best_strat = strat
                    gen_best_risk = risk

            # 更新全局最優
            if gen_best_fitness > best_fitness:
                best_fitness = gen_best_fitness
                best_pred = gen_best_pred
                best_strat = gen_best_strat
                best_risk = gen_best_risk

            fitness_history.append(round(best_fitness, 5))
            self.sigma *= self.sigma_decay  # 逐漸縮小擾動

            if (gen + 1) % 10 == 0:
                logger.info(
                    "第 %d/%d 代 | 最優 Fitness=%.4f | σ=%.4f",
                    gen + 1, self.n_generations, best_fitness, self.sigma,
                )

        # 最優解在訓練集上的完整結果
        best_episode = _run_episode(train_records, best_pred, best_strat, best_risk)

        # 測試集評估
        test_episode: Optional[EpisodeResult] = None
        if test_records:
            test_episode = _run_episode(test_records, best_pred, best_strat, best_risk)
            logger.info(
                "測試集結果 | ROI=%.1f%% | Brier=%.4f | Sharpe=%.2f | 下注=%d",
                test_episode.roi * 100, test_episode.brier_score,
                test_episode.sharpe_ratio, test_episode.n_bets,
            )

        return OptimizationResult(
            best_predictor=best_pred,
            best_strategist=best_strat,
            best_risk_controller=best_risk,
            best_fitness=best_fitness,
            best_episode=best_episode,
            fitness_history=fitness_history,
            test_episode=test_episode,
            n_generations=self.n_generations,
            n_records_train=len(train_records),
            n_records_test=len(test_records),
        )


# ══════════════════════════════════════════════════════════════════════════════
# 便捷函數
# ══════════════════════════════════════════════════════════════════════════════

def optimize_strategy(
    records: list,
    n_generations: int = 50,
    n_candidates: int = 10,
    seed: int = 42,
) -> OptimizationResult:
    """
    快速優化入口。載入 GameRecord 後直接呼叫即可。

    Example:
        from data.mlb_data_loader import load_mlb_records
        from wbc_backend.strategy.marl_optimizer import optimize_strategy

        records = load_mlb_records()
        result = optimize_strategy(records, n_generations=30)
        print(f"測試 ROI: {result.test_episode.roi:.1%}")
    """
    optimizer = MARLOptimizer(
        n_generations=n_generations,
        n_candidates=n_candidates,
        seed=seed,
    )
    return optimizer.optimize(records)


def predict_single_game(
    record: Any,
    predictor: Optional[PredictorParams] = None,
) -> dict[str, float]:
    """
    使用 PredictorAgent 對單場比賽輸出預測。
    predictor=None 時使用預設權重。
    """
    if predictor is None:
        predictor = PredictorParams()
    prob = predictor.predict(record)
    return {
        "home_win_prob": round(prob, 4),
        "away_win_prob": round(1.0 - prob, 4),
    }
