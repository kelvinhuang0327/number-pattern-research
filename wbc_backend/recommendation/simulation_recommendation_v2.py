"""
SimulationRecommendationV2 — P2 獨立機率推薦資料結構

與 P0 RecommendationRow 的核心差異：
  - model_prob 必須來自獨立模型（Elo / Orchestrator），絕不由 odds 反推
  - model_source 欄位強制標記機率來源
  - home_win_ci_95 / world_model_score_dist / marl_strategy_weight 新增下游欄位

硬性約束：
  - paper_only 永遠 True
  - model_source 不得含 "PROXY_DERIVED" 字串
  - odds_quality_tier 不得為空
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SimulationRecommendationV2:
    """單場比賽 P2 策略模擬推薦資料列。

    所有欄位均為 paper-only 用途，禁止寫入任何生產下注 channel。
    model_prob 必須來自獨立模型（Elo / Orchestrator），不得由 odds 反推。
    """

    # ── 基本識別 ──────────────────────────────────────────────────────────────
    game_id: str
    game_date: str
    market: str = "ML"
    side: str = ""              # "home" | "away" | ""（NO_BET）

    # ── 獨立模型機率（核心差異）──────────────────────────────────────────────
    model_prob: float = 0.0     # 獨立模型 p(home_win)
    implied_prob: float = 0.0   # 隱含勝率（去 vig 後的 proxy closing price）
    edge: float = 0.0           # model_prob - implied_prob

    # ── Kelly / 倉位 ──────────────────────────────────────────────────────────
    kelly_fraction: float = 0.0
    stake_unit: float = 0.0     # 實際倉位（已套用 kelly_cap）

    # ── 品質標記 ──────────────────────────────────────────────────────────────
    odds_quality_tier: str = "POST_GAME_PROXY"
    paper_only: bool = True     # 永遠 True

    # ── Gate 過濾資訊 ─────────────────────────────────────────────────────────
    gates_passed: list = field(default_factory=list)
    rejected_reason: Optional[str] = None

    # ── 執行批次追蹤 ──────────────────────────────────────────────────────────
    simulation_run_id: str = ""
    model_source: str = ""          # 例："SimplifiedElo_v1" | "PredictionOrchestrator_v1"
    walk_forward_fold: int = 0      # Walk-Forward fold 編號（0 = 無 WF 分層）
    generated_at_utc: str = ""
    source_trace: str = ""          # 詳細機率推導來源說明

    # ── 下游 MARL 欄位 ───────────────────────────────────────────────────────
    home_win_ci_95: Optional[tuple] = None       # (ci_low, ci_high)
    world_model_score_dist: Optional[dict] = None
    marl_strategy_weight: Optional[float] = None

    # ── P0 相容欄位 ──────────────────────────────────────────────────────────
    home_team: str = ""
    away_team: str = ""
    home_ml_odds: float = 0.0
    away_ml_odds: float = 0.0
    bet_side: str = "NO_BET"        # "HOME" | "AWAY" | "NO_BET"
    ev: float = 0.0
    ece: float = 0.0
    blowout_propensity: float = 0.0
    brier_score: Optional[float] = None
    home_elo: float = 1500.0
    away_elo: float = 1500.0

    def __post_init__(self) -> None:
        assert self.paper_only is True, "paper_only must always be True"
        assert self.odds_quality_tier != "", "odds_quality_tier is required"
        assert self.model_source != "", "model_source must be specified"
        if "PROXY_DERIVED" in self.model_source:
            raise ValueError(
                f"model_prob must not be derived from proxy odds. "
                f"model_source='{self.model_source}' is forbidden."
            )
        if not self.generated_at_utc:
            self.generated_at_utc = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """序列化為 dict（供 JSONL 輸出）。"""
        return {
            "game_id": self.game_id,
            "game_date": self.game_date,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "market": self.market,
            "side": self.side,
            "bet_side": self.bet_side,
            "model_prob": round(self.model_prob, 4),
            "implied_prob": round(self.implied_prob, 4),
            "edge": round(self.edge, 4),
            "kelly_fraction": round(self.kelly_fraction, 4),
            "stake_unit": round(self.stake_unit, 4),
            "ev": round(self.ev, 4),
            "home_ml_odds": self.home_ml_odds,
            "away_ml_odds": self.away_ml_odds,
            "odds_quality_tier": self.odds_quality_tier,
            "paper_only": self.paper_only,
            "model_source": self.model_source,
            "simulation_run_id": self.simulation_run_id,
            "walk_forward_fold": self.walk_forward_fold,
            "generated_at_utc": self.generated_at_utc,
            "source_trace": self.source_trace,
            "ece": round(self.ece, 4),
            "blowout_propensity": round(self.blowout_propensity, 4),
            "brier_score": self.brier_score,
            "home_elo": self.home_elo,
            "away_elo": self.away_elo,
            "home_win_ci_95": list(self.home_win_ci_95) if self.home_win_ci_95 else None,
            "world_model_score_dist": self.world_model_score_dist,
            "marl_strategy_weight": self.marl_strategy_weight,
            "gates_passed": list(self.gates_passed),
            "rejected_reason": self.rejected_reason,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)
