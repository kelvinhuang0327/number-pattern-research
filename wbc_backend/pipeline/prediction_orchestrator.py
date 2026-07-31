"""
統一預測管道 (Prediction Orchestrator) — Phase 7A
=================================================
整合所有 Phase 1-6 模組，提供單一入口點的棒球賽事預測服務。

模組整合架構：
  ┌─────────────────────────────────────────────────────────┐
  │              PredictionOrchestrator                      │
  │  ┌───────────┐  ┌────────────────┐  ┌────────────────┐  │
  │  │ WorldModel│  │ HierarchicalMC │  │ MARLPredictor  │  │
  │  │ (PA-level)│  │ (4-layer corr.)│  │ (ELO+Market+..)│  │
  │  └─────┬─────┘  └───────┬────────┘  └───────┬────────┘  │
  │        └────────────────┼───────────────────┘            │
  │                         ▼                                 │
  │              WeightedEnsembleResult                       │
  │  (home_win_prob CI / tail_risk / MARL signals)           │
  └─────────────────────────────────────────────────────────┘

輸入彈性：
  - 僅 GameRecord（MARL 模式，最輕量）
  - + 市場/KG/NLP 信號（HierarchicalMC 模式）
  - + PitcherSnapshot + BatterSnapshot（WorldModel 模式）

輸出 OrchestratorResult：
  - home_win_prob / away_win_prob（加權融合）
  - confidence_interval_95：(low, high) 95% CI
  - model_contributions：各模型貢獻度
  - tail_risk / blowout_prob（來自世界模型）
  - recommended_bet：建議下注方向 + Kelly 比例
  - audit_trail：完整稽核日誌
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
from league_adapters.base import LeagueContext
from league_adapters.registry import get_league_adapter, normalize_league_name
from wbc_backend.pipeline.game_classification import GameType, classify_game_type
from research.config import is_research_mode_enabled

logger = logging.getLogger(__name__)

# ── 模型權重預設值 ────────────────────────────────────────────────────────────
_DEFAULT_WEIGHTS = {
    "marl": 0.40,          # MARL PredictorAgent（最快，始終啟用）
    "hierarchical_mc": 0.35,  # 階層式蒙特卡洛（有市場/KG/NLP 時啟用）
    "world_model": 0.25,   # 棒球世界模型（有球員資料時啟用）
    "mlb_moneyline": 0.60,  # MLB 專用主模型（僅 MLB 時啟用）
    "mlb_regime_paper": 0.60,  # MLB regime-first paper model
}


# ══════════════════════════════════════════════════════════════════════════════
# 輸出結構
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ModelOutput:
    """單一模型的預測輸出"""
    model_name: str
    home_win_prob: float
    confidence: float      # 0-1，該模型的信心度
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrchestratorResult:
    """統一預測管道的最終輸出"""
    # 融合機率
    home_win_prob: float
    away_win_prob: float

    # 95% 信賴區間
    confidence_interval_95: tuple[float, float]

    # 各模型貢獻
    model_outputs: list[ModelOutput]
    model_weights_used: dict[str, float]
    models_activated: list[str]

    # 分佈型指標（來自世界模型，若啟用）
    tail_risk_score: float       # P(total >= 15)
    blowout_prob: float          # P(|diff| >= 7)
    shutout_prob: float          # P(either team scores 0)
    expected_total_runs: float

    # 建議下注
    recommended_side: str        # "home" | "away" | "pass"
    recommended_kelly_fraction: float
    edge_vs_market: float        # pred_prob - market_prob
    execution_mode: str = "LIVE"
    paper_side: str = "skip"
    paper_reason: str = ""
    paper_regime: str = ""
    applicable_regimes: list[str] = field(default_factory=list)
    governance_flags: dict[str, Any] = field(default_factory=dict)
    game_type: str = "MLB_REGULAR"
    metrics_pool: str = ""
    betting_advice: str = ""

    # 稽核
    audit_trail: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# 核心融合邏輯
# ══════════════════════════════════════════════════════════════════════════════

def _weighted_ensemble(
    outputs: list[ModelOutput],
    weights: dict[str, float],
) -> tuple[float, float, float]:
    """
    加權融合多個模型輸出。
    使用對數機率空間融合（Log-probability averaging），
    比線性融合更穩健（避免過度集中在 0/1 附近）。

    Returns:
        (home_win_prob, ci_low, ci_high)
    """
    if not outputs:
        return 0.5, 0.35, 0.65

    total_weight = sum(weights.get(o.model_name, 1.0) for o in outputs)
    if total_weight <= 0:
        return 0.5, 0.35, 0.65

    # 加權對數機率融合（Logit 空間平均）
    logit_sum = 0.0
    for o in outputs:
        w = weights.get(o.model_name, 1.0) / total_weight
        p = float(np.clip(o.home_win_prob, 0.01, 0.99))
        logit = math.log(p / (1 - p))
        logit_sum += w * logit

    fused_prob = 1.0 / (1.0 + math.exp(-logit_sum))

    # 信賴區間：基於模型間分歧（標準差）
    probs = [o.home_win_prob for o in outputs]
    if len(probs) >= 2:
        std = float(np.std(probs))
        ci_low = max(0.01, fused_prob - 1.96 * std)
        ci_high = min(0.99, fused_prob + 1.96 * std)
    else:
        # 單模型：使用 bootstrap-style ±5% 估算
        ci_low = max(0.01, fused_prob - 0.05)
        ci_high = min(0.99, fused_prob + 0.05)

    return round(fused_prob, 4), round(ci_low, 4), round(ci_high, 4)


# ══════════════════════════════════════════════════════════════════════════════
# 主要 Orchestrator 類別
# ══════════════════════════════════════════════════════════════════════════════

class PredictionOrchestrator:
    """
    統一預測管道。

    依據可用輸入自動選擇啟用哪些模型：
      - 始終啟用：MARL PredictorAgent
      - 有市場/KG/NLP 信號：啟用 HierarchicalMC
      - 有投手/打者資料：啟用 WorldModel

    Example:
        from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
        from wbc_backend.strategy.marl_optimizer import PredictorParams

        orc = PredictionOrchestrator(
            marl_predictor=PredictorParams(),
            model_weights={"marl": 0.5, "hierarchical_mc": 0.3, "world_model": 0.2},
        )
        result = orc.predict(game_record, market_signals={...})
    """

    def __init__(
        self,
        marl_predictor=None,         # PredictorParams | None（None = 預設參數）
        model_weights: Optional[dict[str, float]] = None,
        min_kelly_edge: float = 0.03,  # 最低邊緣才建議下注
        kelly_multiplier: float = 0.25,
    ):
        from wbc_backend.strategy.marl_optimizer import PredictorParams
        self.marl_predictor = marl_predictor or PredictorParams()
        self.model_weights = model_weights or _DEFAULT_WEIGHTS.copy()
        self.min_kelly_edge = min_kelly_edge
        self.kelly_multiplier = kelly_multiplier

    def predict(
        self,
        record: Any,                              # GameRecord（賽前特徵）
        market_signals: Optional[dict[str, float]] = None,  # Layer 2 市場信號
        kg_signals: Optional[dict[str, float]] = None,      # Layer 3 KG 信號
        nlp_signals: Optional[dict[str, float]] = None,     # Layer 4 NLP 信號
        home_sp=None,                             # PitcherSnapshot | None
        away_sp=None,
        home_batters: Optional[list] = None,      # list[BatterSnapshot] | None
        away_batters: Optional[list] = None,
        n_mc_simulations: int = 10_000,
        n_wm_simulations: int = 5_000,
        use_world_model: bool = True,
        use_hierarchical_mc: bool = True,
    ) -> OrchestratorResult:
        """
        執行統一預測。

        Args:
            record: GameRecord（含賽前 ELO/wOBA/FIP/market_prob 等特徵）
            market_signals: Layer 2 市場微結構信號 dict
            kg_signals: Layer 3 知識圖譜信號 dict
            nlp_signals: Layer 4 NLP 語義信號 dict
            home_sp / away_sp: 投手快照（啟用世界模型需要）
            home_batters / away_batters: 打線快照（啟用世界模型需要）
            n_mc_simulations: 階層式 MC 模擬次數
            n_wm_simulations: 世界模型模擬次數
            use_world_model: 是否嘗試啟用世界模型（需要球員資料）
            use_hierarchical_mc: 是否嘗試啟用階層式 MC

        Returns:
            OrchestratorResult（含融合預測 + 信賴區間 + 建議下注）
        """
        outputs: list[ModelOutput] = []
        activated: list[str] = []
        warnings: list[str] = []
        audit: dict[str, Any] = {}

        league = normalize_league_name(getattr(record, "league", "") or getattr(record, "tournament", "WBC"))
        adapter = get_league_adapter(league)
        context = LeagueContext(
            league=league,
            game_id=str(getattr(record, "game_id", "UNK")),
            home_team=str(getattr(record, "home_team", "HOME")),
            away_team=str(getattr(record, "away_team", "AWAY")),
            round_name=str(getattr(record, "round_name", "")),
            weather=getattr(record, "weather", {}) or {},
            odds=getattr(record, "odds", {}) or {},
            pitchers=getattr(record, "pitchers", {}) or {},
            lineups=getattr(record, "lineups", {}) or {},
            bullpen_usage=getattr(record, "bullpen_usage", {}) or {},
            injury_report=getattr(record, "injury_report", {}) or {},
        )
        missing_fields = adapter.validate_context(context)
        if missing_fields:
            warnings.append(f"{league} adapter missing fields: {missing_fields}")
        audit["league"] = league
        audit["league_adapter"] = adapter.name()
        audit["adapter_missing_fields"] = missing_fields

        market_prob = float(getattr(record, "market_home_prob", 0.5))

        # ── 模型 1：MARL PredictorAgent（始終啟用）────────────────────────────
        try:
            marl_prob = self.marl_predictor.predict(record)
            outputs.append(ModelOutput(
                model_name="marl",
                home_win_prob=marl_prob,
                confidence=0.7,
            ))
            activated.append("marl")
            audit["marl"] = {"home_win_prob": round(marl_prob, 4)}
        except Exception as e:
            warnings.append(f"MARL 預測失敗: {e}")
            outputs.append(ModelOutput("marl", 0.5, 0.3))
            activated.append("marl")

        game_type = classify_game_type(record)
        audit["game_type"] = game_type.value
        audit["output_mode"] = "spring_training_sandbox" if game_type == GameType.SPRING_TRAINING else "standard"

        paper_inference = None
        if league == "MLB" and game_type != GameType.SPRING_TRAINING:
            try:
                from wbc_backend.models.mlb_regime_paper import default_mlb_regime_paper_system

                paper_system = default_mlb_regime_paper_system()
                paper_inference = paper_system.predict_record(record)
                audit["mlb_regime_paper"] = {
                    "execution_mode": paper_inference.execution_mode,
                    "paper_side": paper_inference.paper_side,
                    "paper_regime": paper_inference.paper_regime,
                    "paper_prob": round(paper_inference.paper_prob, 4),
                    "edge_vs_market": round(paper_inference.edge_vs_market, 4),
                    "applicable_regimes": paper_inference.applicable_regimes,
                    "paper_reason": paper_inference.paper_reason,
                    "candidates": paper_inference.candidates,
                }
                audit["tradeability"] = "PAPER_ONLY"
                if paper_inference.paper_regime:
                    confidence = 0.65
                    if paper_inference.candidates:
                        chosen = next((c for c in paper_inference.candidates if c["regime"] == paper_inference.paper_regime), None)
                        if chosen is not None:
                            confidence = max(0.45, 1.0 - min(0.50, float(chosen.get("historical_fold_std", 0.20))))
                    outputs.append(
                        ModelOutput(
                            model_name="mlb_regime_paper",
                            home_win_prob=paper_inference.paper_prob,
                            confidence=confidence,
                            extra={
                                "league": "MLB",
                                "paper_side": paper_inference.paper_side,
                                "paper_regime": paper_inference.paper_regime,
                                "paper_reason": paper_inference.paper_reason,
                            },
                        )
                    )
                    activated.append("mlb_regime_paper")
            except Exception as e:
                warnings.append(f"MLB regime paper mode 失敗: {e}")

        # ── 模型 2：階層式蒙特卡洛 ───────────────────────────────────────────
        wm_result = None
        if use_hierarchical_mc:
            try:
                from wbc_backend.simulation.hierarchical_mc import (
                    run_hierarchical_monte_carlo,
                )
                from wbc_backend.domain.schemas import PredictionResult
                # 從 record 建構輕量 PredictionResult
                base_pred = PredictionResult(
                    game_id=getattr(record, "game_id", "UNK"),
                    home_win_prob=market_prob,
                    away_win_prob=1.0 - market_prob,
                    expected_home_runs=float(getattr(record, "ou_line", 8.5) * 0.53),
                    expected_away_runs=float(getattr(record, "ou_line", 8.5) * 0.47),
                    x_factors=[],
                    diagnostics={},
                )
                hmc = run_hierarchical_monte_carlo(
                    pred=base_pred,
                    simulations=n_mc_simulations,
                    market_signals=market_signals or {},
                    kg_signals=kg_signals or {},
                    nlp_signals=nlp_signals or {},
                    ci_bootstrap_runs=3,
                )
                # CI 寬度作為信心指標（CI 越窄越有信心）
                ci_width = hmc.home_win_prob_ci[1] - hmc.home_win_prob_ci[0]
                conf = max(0.4, 1.0 - ci_width * 2)
                outputs.append(ModelOutput(
                    model_name="hierarchical_mc",
                    home_win_prob=hmc.home_win_prob,
                    confidence=conf,
                    extra={"ci": hmc.home_win_prob_ci, "adj_magnitude": hmc.total_adjustment_magnitude},
                ))
                activated.append("hierarchical_mc")
                audit["hierarchical_mc"] = {
                    "home_win_prob": round(hmc.home_win_prob, 4),
                    "ci": hmc.home_win_prob_ci,
                    "total_adj": hmc.total_adjustment_magnitude,
                }
            except Exception as e:
                warnings.append(f"HierarchicalMC 失敗: {e}")

        # ── 模型 3：棒球世界模型 ──────────────────────────────────────────────
        tail_risk = 0.06
        blowout_prob = 0.12
        shutout_prob = 0.06
        expected_total = getattr(record, "ou_line", 8.5)

        if use_world_model and (home_sp or home_batters):
            try:
                from wbc_backend.simulation.world_model import (
                    run_world_model_from_snapshots, WorldModelConfig,
                )
                wm_result = run_world_model_from_snapshots(
                    home_sp=home_sp,
                    away_sp=away_sp,
                    home_batters=home_batters,
                    away_batters=away_batters,
                    n_simulations=n_wm_simulations,
                )
                # WorldModel 信心度：基於 std 的反比
                std_ratio = (wm_result.std_home_runs + wm_result.std_away_runs) / \
                             max(wm_result.expected_home_runs + wm_result.expected_away_runs, 1)
                conf_wm = max(0.35, 1.0 - std_ratio)

                outputs.append(ModelOutput(
                    model_name="world_model",
                    home_win_prob=wm_result.home_win_prob,
                    confidence=conf_wm,
                    extra={
                        "tail_risk": wm_result.tail_risk_score,
                        "blowout": wm_result.blowout_prob,
                    },
                ))
                activated.append("world_model")
                audit["world_model"] = {
                    "home_win_prob": round(wm_result.home_win_prob, 4),
                    "expected_home_runs": wm_result.expected_home_runs,
                    "tail_risk": wm_result.tail_risk_score,
                    "blowout_prob": wm_result.blowout_prob,
                }
                tail_risk = wm_result.tail_risk_score
                blowout_prob = wm_result.blowout_prob
                shutout_prob = (wm_result.shutout_prob_home + wm_result.shutout_prob_away) / 2
                expected_total = wm_result.expected_home_runs + wm_result.expected_away_runs

            except Exception as e:
                warnings.append(f"WorldModel 失敗: {e}")

        # ── 融合輸出 ──────────────────────────────────────────────────────────
        # 根據啟用模型調整權重
        active_weights = {k: v for k, v in self.model_weights.items() if k in activated}
        if league == "MLB" and "mlb_regime_paper" in activated:
            active_weights = {"mlb_regime_paper": 0.7, "marl": 0.3 if "marl" in activated else 0.0}
        fused_prob, ci_low, ci_high = _weighted_ensemble(outputs, active_weights)
        adjusted_probs = adapter.adjust_probabilities(
            {"home_win_prob": fused_prob, "away_win_prob": 1.0 - fused_prob},
            context,
        )
        fused_prob = float(adjusted_probs["home_win_prob"])

        # ── 建議下注 ──────────────────────────────────────────────────────────
        edge = fused_prob - market_prob
        execution_mode = "LIVE"
        paper_side = "skip"
        paper_reason = ""
        paper_regime = ""
        applicable_regimes: list[str] = []
        metrics_pool = ""
        betting_advice = ""
        if league == "MLB" and game_type != GameType.SPRING_TRAINING:
            from wbc_backend.mlb_data.governance import mlb_governance_flags

            flags = mlb_governance_flags()
            recommended_side = "pass"
            kelly_fraction = 0.0
            execution_mode = str(flags["execution_mode"])
            audit["tradeability"] = str(flags["execution_mode"])
            audit["mlb_governance"] = flags
            warnings.append("MLB guarded paper mode blocks live execution and bet sizing.")
            if paper_inference is not None:
                paper_side = paper_inference.paper_side
                paper_reason = paper_inference.paper_reason
                paper_regime = paper_inference.paper_regime
                applicable_regimes = list(paper_inference.applicable_regimes)
                edge = paper_inference.edge_vs_market
            governance_flags = flags
            metrics_pool = "MLB_PAPER_ONLY"
        elif game_type == GameType.SPRING_TRAINING:
            from wbc_backend.mlb_data.governance import spring_training_governance_flags

            flags = spring_training_governance_flags()
            recommended_side = "pass"
            kelly_fraction = 0.0
            execution_mode = str(flags["execution_mode"])
            betting_advice = str(flags["betting_advice"])
            metrics_pool = str(flags["metrics_pool"])
            paper_side = "skip"
            paper_reason = "spring_training_sandbox_only"
            paper_regime = "exhibition"
            applicable_regimes = ["exhibition"]
            audit["tradeability"] = execution_mode
            audit["spring_training_governance"] = flags
            audit["sandbox_output_layer"] = "spring_training_game_report"
            warnings.append("Spring training routed to sandbox output only; betting is disabled.")
            governance_flags = flags
        elif abs(edge) < self.min_kelly_edge:
            recommended_side = "pass"
            kelly_fraction = 0.0
            governance_flags = {}
        else:
            recommended_side = "home" if edge > 0 else "away"
            # Kelly = edge / odds（-110 賠率 ≈ 0.909）
            implied_odds = market_prob / (1 - market_prob + 1e-8) if edge > 0 \
                else (1 - market_prob) / (market_prob + 1e-8)
            raw_kelly = abs(edge) / max(implied_odds, 0.1)
            kelly_fraction = round(
                float(np.clip(self.kelly_multiplier * raw_kelly, 0.0, 0.10)), 4,
            )
            governance_flags = {}

        audit["metrics_pool"] = metrics_pool
        if betting_advice:
            audit["betting_advice"] = betting_advice

        result = OrchestratorResult(
            home_win_prob=fused_prob,
            away_win_prob=round(1 - fused_prob, 4),
            confidence_interval_95=(ci_low, ci_high),
            model_outputs=outputs,
            model_weights_used=active_weights,
            models_activated=activated,
            tail_risk_score=round(tail_risk, 4),
            blowout_prob=round(blowout_prob, 4),
            shutout_prob=round(shutout_prob, 4),
            expected_total_runs=round(float(expected_total), 2),
            recommended_side=recommended_side,
            recommended_kelly_fraction=kelly_fraction,
            edge_vs_market=round(edge, 4),
            execution_mode=execution_mode,
            paper_side=paper_side,
            paper_reason=paper_reason,
            paper_regime=paper_regime,
            applicable_regimes=applicable_regimes,
            governance_flags=governance_flags,
            game_type=game_type.value,
            metrics_pool=metrics_pool,
            betting_advice=betting_advice,
            audit_trail=audit,
            warnings=warnings,
        )

        if game_type == GameType.SPRING_TRAINING:
            try:
                from wbc_backend.reports.spring_training_game_report import build_spring_training_game_report

                spring_report = build_spring_training_game_report(
                    record=record,
                    orchestrator_result=result,
                )
                result.audit_trail["spring_training_report"] = spring_report
                result.audit_trail["spring_training_report_markdown"] = spring_report.get("markdown_report", "")
            except Exception as e:
                warnings.append(f"Spring training report generation failed: {e}")
                result.audit_trail["spring_training_report_error"] = str(e)

        if is_research_mode_enabled():
            try:
                from research.layer import capture as research_capture

                research_capture(result, record=record)
            except Exception as e:
                logger.debug("Research layer capture skipped: %s", e, exc_info=True)

        return result

    def predict_batch(
        self,
        records: list,
        **kwargs,
    ) -> list[OrchestratorResult]:
        """批次預測多場比賽（對未來賽事快速掃描用）"""
        return [self.predict(r, **kwargs) for r in records]
