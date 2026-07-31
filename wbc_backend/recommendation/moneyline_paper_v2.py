"""
MoneylinePaperRecommenderV2 — PROXY_ONLY 版本

所有 odds 均為 POST_GAME_PROXY（賽後代理值），paper_only 永遠為 True。
本模組不得寫入任何 production channel。

Gate 邏輯（依序過濾）：
  1. ECE gate：ece > 0.12 → reject
  2. Blowout gate：blowout_propensity > 0.65 → reject
  3. Edge gate：edge < edge_threshold → reject
  4. Kelly cap：stake_fraction 不得超過 kelly_cap
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

# 常數
_ECE_REJECT_THRESHOLD = 0.12
_BLOWOUT_REJECT_THRESHOLD = 0.65
_DEFAULT_EDGE_THRESHOLD = 0.01   # 1%
_DEFAULT_KELLY_CAP = 0.05        # 最大 5% 倉位
_ODDS_QUALITY_TIER_DEFAULT: Literal["POST_GAME_PROXY"] = "POST_GAME_PROXY"


@dataclass
class RecommendationRow:
    """單場比賽 Moneyline 推薦資料列。

    所有欄位均為 paper-only / proxy-only 用途，禁止用於生產下注。
    """
    game_id: str
    home_team: str
    away_team: str
    game_date: str

    # 機率
    p_home_win: float
    p_away_win: float

    # Odds（POST_GAME_PROXY）
    home_ml_odds: float          # 美式盤口（如 -150, +130）
    away_ml_odds: float

    # 推薦側
    bet_side: Literal["HOME", "AWAY", "NO_BET"]
    edge: float                  # 模型勝率 - 隱含勝率
    kelly_fraction: float        # 原始 Kelly f*
    stake_fraction: float        # 實際倉位（已套用 kelly_cap）
    ev: float                    # 期望值

    # 品質標記
    odds_quality_tier: str = _ODDS_QUALITY_TIER_DEFAULT
    paper_only: bool = True      # 永遠 True

    # 輸入品質
    ece: float = 0.0
    blowout_propensity: float = 0.0
    brier_score: float | None = None

    # Gate 過濾資訊
    rejected: bool = False
    reject_reason: str = ""
    gates_passed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """序列化為 dict（供 JSONL 輸出）。"""
        return {
            "game_id": self.game_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "game_date": self.game_date,
            "p_home_win": round(self.p_home_win, 4),
            "p_away_win": round(self.p_away_win, 4),
            "home_ml_odds": self.home_ml_odds,
            "away_ml_odds": self.away_ml_odds,
            "bet_side": self.bet_side,
            "edge": round(self.edge, 4),
            "kelly_fraction": round(self.kelly_fraction, 4),
            "stake_fraction": round(self.stake_fraction, 4),
            "ev": round(self.ev, 4),
            "odds_quality_tier": self.odds_quality_tier,
            "paper_only": self.paper_only,
            "ece": round(self.ece, 4),
            "blowout_propensity": round(self.blowout_propensity, 4),
            "brier_score": round(self.brier_score, 4) if self.brier_score is not None else None,
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
            "gates_passed": self.gates_passed,
        }


def _american_to_implied_prob(american_odds: float) -> float:
    """美式盤口 → 隱含機率（含 vig）。"""
    if american_odds >= 100:
        return 100.0 / (american_odds + 100.0)
    else:
        return abs(american_odds) / (abs(american_odds) + 100.0)


def _american_to_decimal(american_odds: float) -> float:
    """美式盤口 → 小數賠率。"""
    if american_odds >= 100:
        return (american_odds / 100.0) + 1.0
    else:
        return (100.0 / abs(american_odds)) + 1.0


def _kelly_fraction(p: float, decimal_odds: float) -> float:
    """Kelly 公式：f* = (p * b - (1 - p)) / b，b = decimal_odds - 1。"""
    b = decimal_odds - 1.0
    if b <= 0:
        return 0.0
    f = (p * b - (1.0 - p)) / b
    return max(0.0, f)


class MoneylinePaperRecommenderV2:
    """Moneyline Paper Recommender V2（PROXY_ONLY）。

    Parameters
    ----------
    edge_threshold : float
        最小 edge 要求，低於此值 reject。預設 0.01（1%）。
    kelly_cap : float
        Kelly 倉位上限，預設 0.05（5%）。
    ece_threshold : float
        ECE 拒絕門檻，預設 0.12。
    blowout_threshold : float
        Blowout propensity 拒絕門檻，預設 0.65。
    """

    def __init__(
        self,
        edge_threshold: float = _DEFAULT_EDGE_THRESHOLD,
        kelly_cap: float = _DEFAULT_KELLY_CAP,
        ece_threshold: float = _ECE_REJECT_THRESHOLD,
        blowout_threshold: float = _BLOWOUT_REJECT_THRESHOLD,
    ) -> None:
        self.edge_threshold = edge_threshold
        self.kelly_cap = kelly_cap
        self.ece_threshold = ece_threshold
        self.blowout_threshold = blowout_threshold

    def recommend(
        self,
        game_id: str,
        p_home_win: float,
        p_away_win: float,
        home_ml_odds: float,
        away_ml_odds: float,
        blowout_propensity: float = 0.0,
        ece: float = 0.0,
        brier_score: float | None = None,
        home_team: str = "",
        away_team: str = "",
        game_date: str = "",
    ) -> RecommendationRow:
        """產生單場推薦（或 NO_BET）。

        所有返回的 RecommendationRow 均帶有：
        - odds_quality_tier = "POST_GAME_PROXY"
        - paper_only = True

        Returns
        -------
        RecommendationRow
            rejected=True 表示未通過 gate；rejected=False 表示有效推薦。
        """
        gates_passed: list[str] = []

        # ── Gate 1: ECE ──────────────────────────────────────────────────────
        if ece > self.ece_threshold:
            logger.debug("[%s] ECE gate reject: ece=%.4f > %.4f", game_id, ece, self.ece_threshold)
            return RecommendationRow(
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                game_date=game_date,
                p_home_win=p_home_win,
                p_away_win=p_away_win,
                home_ml_odds=home_ml_odds,
                away_ml_odds=away_ml_odds,
                bet_side="NO_BET",
                edge=0.0,
                kelly_fraction=0.0,
                stake_fraction=0.0,
                ev=0.0,
                odds_quality_tier=_ODDS_QUALITY_TIER_DEFAULT,
                paper_only=True,
                ece=ece,
                blowout_propensity=blowout_propensity,
                brier_score=brier_score,
                rejected=True,
                reject_reason=f"ece_gate: {ece:.4f} > {self.ece_threshold}",
                gates_passed=gates_passed,
            )
        gates_passed.append("ece_pass")

        # ── Gate 2: Blowout ──────────────────────────────────────────────────
        if blowout_propensity > self.blowout_threshold:
            logger.debug("[%s] Blowout gate reject: bp=%.4f > %.4f", game_id, blowout_propensity, self.blowout_threshold)
            return RecommendationRow(
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                game_date=game_date,
                p_home_win=p_home_win,
                p_away_win=p_away_win,
                home_ml_odds=home_ml_odds,
                away_ml_odds=away_ml_odds,
                bet_side="NO_BET",
                edge=0.0,
                kelly_fraction=0.0,
                stake_fraction=0.0,
                ev=0.0,
                odds_quality_tier=_ODDS_QUALITY_TIER_DEFAULT,
                paper_only=True,
                ece=ece,
                blowout_propensity=blowout_propensity,
                brier_score=brier_score,
                rejected=True,
                reject_reason=f"blowout_gate: bp={blowout_propensity:.4f} > {self.blowout_threshold}",
                gates_passed=gates_passed,
            )
        gates_passed.append("blowout_pass")

        # ── 計算兩側 edge ────────────────────────────────────────────────────
        home_implied = _american_to_implied_prob(home_ml_odds)
        away_implied = _american_to_implied_prob(away_ml_odds)
        home_edge = p_home_win - home_implied
        away_edge = p_away_win - away_implied

        # 選最優邊
        if home_edge >= away_edge:
            best_side: Literal["HOME", "AWAY"] = "HOME"
            best_edge = home_edge
            best_p = p_home_win
            best_odds = home_ml_odds
        else:
            best_side = "AWAY"
            best_edge = away_edge
            best_p = p_away_win
            best_odds = away_ml_odds

        # ── Gate 3: Edge ─────────────────────────────────────────────────────
        if best_edge < self.edge_threshold:
            return RecommendationRow(
                game_id=game_id,
                home_team=home_team,
                away_team=away_team,
                game_date=game_date,
                p_home_win=p_home_win,
                p_away_win=p_away_win,
                home_ml_odds=home_ml_odds,
                away_ml_odds=away_ml_odds,
                bet_side="NO_BET",
                edge=best_edge,
                kelly_fraction=0.0,
                stake_fraction=0.0,
                ev=0.0,
                odds_quality_tier=_ODDS_QUALITY_TIER_DEFAULT,
                paper_only=True,
                ece=ece,
                blowout_propensity=blowout_propensity,
                brier_score=brier_score,
                rejected=True,
                reject_reason=f"edge_gate: edge={best_edge:.4f} < {self.edge_threshold}",
                gates_passed=gates_passed,
            )
        gates_passed.append("edge_pass")

        # ── Kelly sizing ─────────────────────────────────────────────────────
        decimal_odds = _american_to_decimal(best_odds)
        raw_kelly = _kelly_fraction(best_p, decimal_odds)
        stake = min(raw_kelly, self.kelly_cap)

        # ── EV ───────────────────────────────────────────────────────────────
        ev = best_p * (decimal_odds - 1.0) - (1.0 - best_p)

        logger.info(
            "[%s] 推薦 %s: edge=%.4f kelly=%.4f→%.4f ev=%.4f odds_tier=POST_GAME_PROXY paper_only=True",
            game_id, best_side, best_edge, raw_kelly, stake, ev,
        )

        return RecommendationRow(
            game_id=game_id,
            home_team=home_team,
            away_team=away_team,
            game_date=game_date,
            p_home_win=p_home_win,
            p_away_win=p_away_win,
            home_ml_odds=home_ml_odds,
            away_ml_odds=away_ml_odds,
            bet_side=best_side,
            edge=best_edge,
            kelly_fraction=raw_kelly,
            stake_fraction=stake,
            ev=ev,
            odds_quality_tier=_ODDS_QUALITY_TIER_DEFAULT,
            paper_only=True,
            ece=ece,
            blowout_propensity=blowout_propensity,
            brier_score=brier_score,
            rejected=False,
            reject_reason="",
            gates_passed=gates_passed,
        )
