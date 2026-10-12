"""
博彩市場代理人模擬器 (Betting Market Agent Simulator)
======================================================
借鑑 MiroFish 多智能體模擬框架思想，以純 Python 輕量化實作。
無 CAMEL/外部框架依賴，執行延遲 < 10 秒。

代理人類型（模擬博彩市場參與者）：
  PublicAgent (70%)  : 散戶，追主隊/媒體推薦，反應滯後
  SharpAgent  (20%)  : 大戶，Kelly 準則，快速反應有效資訊
  SyndicateAgent(10%): 財團，大量資金，觸發 Steam Move

模擬輸出：
  - 預測收盤賠率 (Predicted Closing Line)
  - 蒸氣移動機率 (Steam Move Probability)
  - 最佳下注時機 (Optimal Bet Timing)
  - CLV 估算 (Closing Line Value)

整合點：
  portfolio_risk.py → BetProposal 前置評估
  alpha_signals.py  → Category M 市場微結構特徵 (10 個)
"""
from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── 模擬參數 ──────────────────────────────────────────────────────────────────
_N_AGENTS = 1000        # 代理人數量（平衡精度與速度）
_N_ROUNDS = 60          # 模擬輪數（對應開賽前 60 分鐘）
_SEED = 42


# ══════════════════════════════════════════════════════════════════════════════
# 代理人類型
# ══════════════════════════════════════════════════════════════════════════════

class AgentType(Enum):
    PUBLIC = "public"
    SHARP = "sharp"
    SYNDICATE = "syndicate"


@dataclass
class MarketAgent:
    """
    單一市場代理人。

    每輪根據當前賠率、持有信念、個人閾值決定是否下注及方向。
    """
    agent_id: int
    agent_type: AgentType
    belief_home_prob: float   # 代理人對主隊勝率的主觀信念 [0,1]
    bankroll: float           # 初始資金
    reaction_speed: float     # 反應速度 [0,1]（越高越早行動）
    noise_std: float          # 信念雜訊標準差
    threshold: float          # 下注閾值（EV > threshold 才下注）

    # 狀態
    total_bet: float = 0.0
    bet_direction: int = 0   # +1=主隊, -1=客隊, 0=不下

    def update_belief(self, market_signal: float, round_num: int) -> None:
        """根據市場訊號更新信念（帶有延遲和雜訊）。"""
        # 散戶反應遲緩（round_num 越大才越注意）
        effective_weight = self.reaction_speed * (round_num / _N_ROUNDS)
        noise = np.random.normal(0, self.noise_std)

        self.belief_home_prob = float(np.clip(
            self.belief_home_prob * (1 - effective_weight) +
            (market_signal + noise) * effective_weight,
            0.05, 0.95
        ))

    def decide_bet(self, current_home_odds: float, current_away_odds: float) -> tuple[float, int]:
        """
        決定下注金額與方向。
        返回 (bet_amount, direction)，direction: +1=主隊, -1=客隊, 0=不押
        """
        if current_home_odds <= 1.0 or current_away_odds <= 1.0:
            return 0.0, 0

        implied_prob_home = 1.0 / current_home_odds
        implied_prob_away = 1.0 / current_away_odds

        ev_home = self.belief_home_prob * (current_home_odds - 1) - (1 - self.belief_home_prob)
        ev_away = (1 - self.belief_home_prob) * (current_away_odds - 1) - self.belief_home_prob

        # 選擇最高 EV 方向
        if ev_home >= ev_away and ev_home > self.threshold:
            # Kelly sizing（財團/大戶），散戶用固定比例
            if self.agent_type in (AgentType.SHARP, AgentType.SYNDICATE):
                edge = self.belief_home_prob - implied_prob_home
                kelly_f = max(0, edge / (current_home_odds - 1))
                kelly_f = min(kelly_f, 0.25)  # 上限 25%
                amount = self.bankroll * kelly_f
            else:
                amount = self.bankroll * random.uniform(0.01, 0.05)

            self.bet_direction = 1
            return amount, 1

        elif ev_away > ev_home and ev_away > self.threshold:
            if self.agent_type in (AgentType.SHARP, AgentType.SYNDICATE):
                edge = (1 - self.belief_home_prob) - implied_prob_away
                kelly_f = max(0, edge / (current_away_odds - 1))
                kelly_f = min(kelly_f, 0.25)
                amount = self.bankroll * kelly_f
            else:
                amount = self.bankroll * random.uniform(0.01, 0.05)

            self.bet_direction = -1
            return amount, -1

        return 0.0, 0


# ══════════════════════════════════════════════════════════════════════════════
# 賠率市場引擎
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OddsEngine:
    """
    簡化博彩市場賠率定價引擎。

    根據下注量差值調整賠率（Balanced Book 模型）。
    """
    home_prob: float       # 開盤隱含主隊勝率
    vig: float = 0.045     # 莊家抽水（4.5%）

    def _prob_to_decimal(self, prob: float) -> float:
        return 1.0 / max(prob, 0.01)

    def get_odds(self, home_prob: float) -> tuple[float, float]:
        """返回 (home_decimal, away_decimal) 含 vig。"""
        away_prob = 1.0 - home_prob
        total = home_prob + away_prob + self.vig
        h = self._prob_to_decimal(home_prob / total * (1 + self.vig))
        a = self._prob_to_decimal(away_prob / total * (1 + self.vig))
        return h, a

    def adjust_for_imbalance(
        self,
        current_home_prob: float,
        net_home_exposure: float,
        total_market_volume: float,
        sharp_net: float,
    ) -> float:
        """
        根據下注量不平衡調整賠率。

        - net_home_exposure > 0: 主隊獲得更多資金 → 主隊賠率下降（勝率上升）
        - sharp_net: 大戶淨下注（對賠率影響更大）
        """
        if total_market_volume < 1e-3:
            return current_home_prob

        # 公眾下注影響（較弱）
        public_adjustment = (net_home_exposure / total_market_volume) * 0.03

        # 大戶下注影響（較強，3倍）
        sharp_adjustment = (sharp_net / max(total_market_volume * 0.3, 1.0)) * 0.09

        new_prob = current_home_prob + public_adjustment + sharp_adjustment
        return float(np.clip(new_prob, 0.10, 0.90))


# ══════════════════════════════════════════════════════════════════════════════
# 輸出資料結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketPrediction:
    """市場模擬預測結果。"""
    # 賠率預測
    opening_home_prob: float             # 開盤主隊隱含勝率
    predicted_closing_home_prob: float   # 預測收盤主隊勝率
    predicted_home_decimal: float        # 預測收盤主隊賠率（小數）
    predicted_away_decimal: float        # 預測收盤客隊賠率（小數）

    # 市場動態指標
    steam_move_probability: float        # Steam Move 發生機率 [0,1]
    sharp_consensus_direction: int       # 大戶共識方向: +1=主隊, -1=客隊, 0=無共識
    public_fade_opportunity: bool        # 是否有逆公眾下注機會
    reverse_line_move: bool              # 反向賠率移動（公眾押主隊但線路反向）

    # CLV 估算
    clv_estimate_home: float             # 主隊押注 CLV 估算 [%]
    clv_estimate_away: float             # 客隊押注 CLV 估算 [%]

    # 最佳時機
    optimal_bet_round: int               # 建議下注輪次（0-60）
    optimal_bet_timing_pct: float        # 建議下注時機（0=開盤, 1=收盤）

    # 診斷
    total_volume_simulated: float        # 模擬總下注量
    sharp_volume_fraction: float         # 大戶資金佔比
    n_steam_events: int                  # 蒸氣移動次數
    odds_movement_home: float            # 主隊賠率移動幅度（相對開盤）

    def to_feature_dict(self) -> dict[str, float]:
        """轉換為 Category M 市場微結構特徵（10 個）。"""
        return {
            "mkt_predicted_home_prob":       round(self.predicted_closing_home_prob, 4),
            "mkt_prob_drift":                round(self.predicted_closing_home_prob - self.opening_home_prob, 4),
            "mkt_steam_probability":         round(self.steam_move_probability, 4),
            "mkt_sharp_direction":           float(self.sharp_consensus_direction),
            "mkt_public_fade_signal":        float(self.public_fade_opportunity),
            "mkt_reverse_line_move":         float(self.reverse_line_move),
            "mkt_clv_home":                  round(self.clv_estimate_home, 4),
            "mkt_clv_away":                  round(self.clv_estimate_away, 4),
            "mkt_sharp_volume_fraction":     round(self.sharp_volume_fraction, 4),
            "mkt_optimal_timing":            round(self.optimal_bet_timing_pct, 4),
        }


# ══════════════════════════════════════════════════════════════════════════════
# 主模擬器
# ══════════════════════════════════════════════════════════════════════════════

class BettingMarketSimulator:
    """
    博彩市場代理人模擬器。

    1000 代理人 × 60 輪 ≈ 3-8 秒（純 Python NumPy）

    使用方法：
        sim = BettingMarketSimulator()
        result = sim.run(
            opening_home_prob=0.55,
            model_home_prob=0.62,
            public_bet_pct_home=0.65,
            is_sharp_on_home=True,
        )
        features = result.to_feature_dict()
    """

    def __init__(
        self,
        n_agents: int = _N_AGENTS,
        n_rounds: int = _N_ROUNDS,
        seed: Optional[int] = _SEED,
    ) -> None:
        self.n_agents = n_agents
        self.n_rounds = n_rounds
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

    def _create_agents(
        self,
        opening_home_prob: float,
        public_bet_pct_home: float,
        is_sharp_on_home: bool,
    ) -> list[MarketAgent]:
        """初始化三類代理人。"""
        agents: list[MarketAgent] = []
        n_public = int(self.n_agents * 0.70)
        n_sharp = int(self.n_agents * 0.20)
        n_syndicate = self.n_agents - n_public - n_sharp

        # ── 散戶：信念偏向公眾下注方向 ──────────────────────────────────────
        for i in range(n_public):
            # 散戶信念分佈：圍繞公眾傾向 + 較大雜訊
            belief = float(np.clip(np.random.normal(
                public_bet_pct_home,
                0.12
            ), 0.10, 0.90))
            agents.append(MarketAgent(
                agent_id=i,
                agent_type=AgentType.PUBLIC,
                belief_home_prob=belief,
                bankroll=random.uniform(500, 5_000),
                reaction_speed=random.uniform(0.05, 0.30),   # 慢
                noise_std=0.08,
                threshold=0.02,   # 低閾值，容易下注
            ))

        # ── 大戶：信念接近模型真實值，反應快 ──────────────────────────────────
        sharp_belief_center = 0.60 if is_sharp_on_home else 0.40
        for i in range(n_sharp):
            belief = float(np.clip(np.random.normal(
                sharp_belief_center, 0.05
            ), 0.10, 0.90))
            agents.append(MarketAgent(
                agent_id=n_public + i,
                agent_type=AgentType.SHARP,
                belief_home_prob=belief,
                bankroll=random.uniform(10_000, 100_000),
                reaction_speed=random.uniform(0.70, 0.95),   # 快
                noise_std=0.03,
                threshold=0.04,   # 高閾值，只押有優勢的
            ))

        # ── 財團：大量資金，有時觸發 Steam Move ──────────────────────────────
        for i in range(n_syndicate):
            # 財團跟著大戶信念
            belief = float(np.clip(np.random.normal(
                sharp_belief_center, 0.02
            ), 0.15, 0.85))
            agents.append(MarketAgent(
                agent_id=n_public + n_sharp + i,
                agent_type=AgentType.SYNDICATE,
                belief_home_prob=belief,
                bankroll=random.uniform(200_000, 1_000_000),
                reaction_speed=random.uniform(0.80, 1.00),
                noise_std=0.01,
                threshold=0.05,
            ))

        return agents

    def run(
        self,
        opening_home_prob: float,
        model_home_prob: float,
        public_bet_pct_home: float = 0.55,
        is_sharp_on_home: bool = True,
        vig: float = 0.045,
    ) -> MarketPrediction:
        """
        執行市場模擬。

        Args:
            opening_home_prob:   開盤隱含主隊勝率（由賠率換算）
            model_home_prob:     我方模型的主隊勝率估算
            public_bet_pct_home: 公眾下注主隊比例（0-1）
            is_sharp_on_home:    大戶是否押主隊
            vig:                 莊家抽水

        Returns:
            MarketPrediction
        """
        engine = OddsEngine(home_prob=opening_home_prob, vig=vig)
        agents = self._create_agents(opening_home_prob, public_bet_pct_home, is_sharp_on_home)

        current_home_prob = opening_home_prob
        home_odds, away_odds = engine.get_odds(current_home_prob)

        # 記錄各輪狀態
        prob_history: list[float] = [current_home_prob]
        volume_history: list[float] = []
        steam_events: int = 0
        optimal_round: int = 0
        best_clv: float = -999.0

        total_home_volume = 0.0
        total_away_volume = 0.0
        sharp_home_volume = 0.0
        sharp_away_volume = 0.0

        for rnd in range(self.n_rounds):
            round_home_vol = 0.0
            round_away_vol = 0.0
            round_sharp_net = 0.0

            # 市場訊號（模型勝率 → 緩慢滲透市場）
            info_penetration = rnd / self.n_rounds
            market_signal = opening_home_prob * (1 - info_penetration) + model_home_prob * info_penetration

            for agent in agents:
                agent.update_belief(market_signal, rnd + 1)
                amount, direction = agent.decide_bet(home_odds, away_odds)

                if direction == 1:
                    round_home_vol += amount
                    if agent.agent_type in (AgentType.SHARP, AgentType.SYNDICATE):
                        sharp_home_volume += amount
                        round_sharp_net += amount
                elif direction == -1:
                    round_away_vol += amount
                    if agent.agent_type in (AgentType.SHARP, AgentType.SYNDICATE):
                        sharp_away_volume += amount
                        round_sharp_net -= amount

            total_home_volume += round_home_vol
            total_away_volume += round_away_vol
            volume_history.append(round_home_vol + round_away_vol)

            # 更新賠率
            round_total = round_home_vol + round_away_vol
            net_home = round_home_vol - round_away_vol
            current_home_prob = engine.adjust_for_imbalance(
                current_home_prob,
                net_home,
                round_total,
                round_sharp_net,
            )
            home_odds, away_odds = engine.get_odds(current_home_prob)
            prob_history.append(current_home_prob)

            # Steam Move 偵測（3 輪內賠率移動 > 3%）
            if rnd >= 2:
                recent_drift = abs(prob_history[-1] - prob_history[-3])
                if recent_drift > 0.03:
                    steam_events += 1

            # 追蹤最佳下注時機（我方 CLV 最高的時機）
            our_edge = model_home_prob - (1.0 / home_odds) if is_sharp_on_home else \
                       (1 - model_home_prob) - (1.0 / away_odds)
            if our_edge > best_clv:
                best_clv = our_edge
                optimal_round = rnd

        # ── 計算最終指標 ──────────────────────────────────────────────────────
        final_home_prob = current_home_prob
        final_home_odds, final_away_odds = engine.get_odds(final_home_prob)

        total_volume = total_home_volume + total_away_volume
        sharp_total = sharp_home_volume + sharp_away_volume
        sharp_fraction = sharp_total / max(total_volume, 1.0)

        # Steam Move 機率
        steam_prob = min(1.0, steam_events / max(1, self.n_rounds * 0.1))

        # 大戶共識方向
        if sharp_home_volume > sharp_away_volume * 1.3:
            sharp_direction = 1
        elif sharp_away_volume > sharp_home_volume * 1.3:
            sharp_direction = -1
        else:
            sharp_direction = 0

        # 逆公眾機會（公眾大量押主隊，但大戶押客隊）
        public_on_home = total_home_volume > total_away_volume * 1.2
        fade_opportunity = public_on_home and sharp_direction == -1

        # 反向賠率移動
        rlm = (public_bet_pct_home > 0.60) and (final_home_prob < opening_home_prob - 0.02)

        # CLV 估算（最終賠率 vs 開盤賠率）
        opening_home_odds, opening_away_odds = engine.get_odds(opening_home_prob)
        clv_home = float((opening_home_odds - final_home_odds) / opening_home_odds * 100)
        clv_away = float((opening_away_odds - final_away_odds) / opening_away_odds * 100)

        # 最佳下注時機（百分比）
        optimal_pct = optimal_round / max(1, self.n_rounds)

        return MarketPrediction(
            opening_home_prob=opening_home_prob,
            predicted_closing_home_prob=final_home_prob,
            predicted_home_decimal=final_home_odds,
            predicted_away_decimal=final_away_odds,
            steam_move_probability=steam_prob,
            sharp_consensus_direction=sharp_direction,
            public_fade_opportunity=fade_opportunity,
            reverse_line_move=rlm,
            clv_estimate_home=clv_home,
            clv_estimate_away=clv_away,
            optimal_bet_round=optimal_round,
            optimal_bet_timing_pct=optimal_pct,
            total_volume_simulated=total_volume,
            sharp_volume_fraction=sharp_fraction,
            n_steam_events=steam_events,
            odds_movement_home=float(final_home_prob - opening_home_prob),
        )


# ══════════════════════════════════════════════════════════════════════════════
# Category M：整合至 alpha_signals.py 的入口
# ══════════════════════════════════════════════════════════════════════════════

def compute_market_simulation_signals(
    opening_home_prob: float,
    model_home_prob: float,
    public_bet_pct_home: float = 0.55,
    is_sharp_on_home: Optional[bool] = None,
    n_agents: int = _N_AGENTS,
    n_rounds: int = _N_ROUNDS,
) -> dict[str, float]:
    """
    Category M — 市場代理人模擬特徵 (10 個信號)

    Args:
        opening_home_prob:   開盤主隊隱含勝率
        model_home_prob:     模型預測主隊勝率
        public_bet_pct_home: 公眾下注主隊比例
        is_sharp_on_home:    None=自動推斷（模型勝率>開盤勝率）

    Returns:
        dict[str, float] — 可合併至 AlphaSignals.feature_dict
    """
    if is_sharp_on_home is None:
        is_sharp_on_home = model_home_prob > opening_home_prob

    sim = BettingMarketSimulator(n_agents=n_agents, n_rounds=n_rounds)
    try:
        prediction = sim.run(
            opening_home_prob=opening_home_prob,
            model_home_prob=model_home_prob,
            public_bet_pct_home=public_bet_pct_home,
            is_sharp_on_home=is_sharp_on_home,
        )
        return prediction.to_feature_dict()
    except Exception as e:
        logger.error("市場模擬失敗: %s", e)
        return _neutral_market_features(opening_home_prob)


def _neutral_market_features(opening_home_prob: float) -> dict[str, float]:
    """市場模擬失敗時的中性 fallback 特徵。"""
    return {
        "mkt_predicted_home_prob":   round(opening_home_prob, 4),
        "mkt_prob_drift":            0.0,
        "mkt_steam_probability":     0.0,
        "mkt_sharp_direction":       0.0,
        "mkt_public_fade_signal":    0.0,
        "mkt_reverse_line_move":     0.0,
        "mkt_clv_home":              0.0,
        "mkt_clv_away":              0.0,
        "mkt_sharp_volume_fraction": 0.3,
        "mkt_optimal_timing":        0.5,
    }
