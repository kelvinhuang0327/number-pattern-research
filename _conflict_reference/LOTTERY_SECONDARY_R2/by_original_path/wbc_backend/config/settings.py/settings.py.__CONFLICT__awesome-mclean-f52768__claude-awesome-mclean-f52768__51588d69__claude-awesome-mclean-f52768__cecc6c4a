"""
Global configuration for the WBC Automated Prediction Backend.

Centralises every tuneable parameter so the scheduler, trainer, optimizer
and self-improvement loop can all share a single source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ── Data Sources ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DataSourceConfig:
    mlb_2025_csv: str = "data/mlb_2025/mlb-2025-asplayed.csv"
    npb_2025_csv: str = "data/external/npb_2025.csv"
    kbo_2025_csv: str = "data/external/kbo_2025.csv"
    wbc_2025_csv: str = "data/external/wbc_2025.csv"
    wbc_authoritative_snapshot_json: str = "data/wbc_2026_authoritative_snapshot.json"
    allow_previous_lineup_fallback: bool = True
    wbc_2026_roster_url: str = "https://www.worldbaseballclassic.com/"
    wbc_2026_schedule_url: str = "https://www.worldbaseballclassic.com/schedule"
    mlb_stats_api: str = "https://statsapi.mlb.com/api/v1"
    odds_api: str = "https://api.the-odds-api.com/v4/sports"
    odds_api_key: str = ""
    data_dir: str = "data"
    model_artifacts_dir: str = "data/wbc_backend/artifacts"
    backtest_results_dir: str = "data/wbc_backend/backtest_results"
    reports_dir: str = "data/wbc_backend/reports"
    prediction_registry_jsonl: str = "data/wbc_backend/reports/prediction_registry.jsonl"
    postgame_results_jsonl: str = "data/wbc_backend/reports/postgame_results.jsonl"
    review_report_latest_md: str = "data/wbc_backend/reports/WBC_Review_Meeting_Latest.md"
    review_report_archive_dir: str = "data/wbc_backend/reports/review_archive"
    bankroll_storage_db: str = "data/wbc_backend/bankroll_v3.db"
    walkforward_summary_json: str = "data/wbc_backend/walkforward_summary.json"
    calibration_compare_json: str = "data/wbc_backend/calibration_compare.json"
    allow_seed_odds_for_live_predictions: bool = False
    min_data_completeness: float = 0.98  # 98% completeness required


# ── Model Config ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ModelConfig:
    # Monte Carlo
    mc_simulations: int = 50_000
    mc_seed: int = 42

    # Elo — WBC 2023 backtest: Elo alone = 72.3% (best single model)
    elo_k: float = 16.0          # Higher K for WBC (fewer games, higher info per game)
    elo_home_advantage: float = 0.0  # WBC = neutral site, no home advantage

    # Ensemble blending — WBC-optimised from 2023 backtest
    # Elo dominated (72.3%), Form was worst (48.9%)
    elo_weight: float = 0.45       # Up from 0.25 — strongest WBC signal
    baseruns_weight: float = 0.25  # Poisson/BaseRuns
    pythag_weight: float = 0.15   # Pythagorean (63.8% in WBC 2023)
    form_weight: float = 0.05     # Form — poor with small WBC samples
    star_weight: float = 0.10     # MLB star impact

    # ML training
    xgb_params: dict = field(default_factory=lambda: {
        "max_depth": 6,
        "learning_rate": 0.05,
        "n_estimators": 300,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "objective": "binary:logistic",
        "eval_metric": "logloss",
    })
    lgbm_params: dict = field(default_factory=lambda: {
        "max_depth": 6,
        "learning_rate": 0.05,
        "n_estimators": 300,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_samples": 10,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "objective": "binary",
        "metric": "binary_logloss",
        "verbosity": -1,
    })
    nn_params: dict = field(default_factory=lambda: {
        "hidden_layers": [128, 64, 32],
        "dropout": 0.3,
        "learning_rate": 0.001,
        "epochs": 100,
        "batch_size": 32,
    })

    # Stacking
    stacking_cv_folds: int = 5

    # Model elimination threshold (Brier score)
    model_eliminate_brier_threshold: float = 0.30

    # Auto-training toggle
    auto_retrain: bool = True


# ── Strategy Config ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyConfig:
    # WBC-optimised: only bet high confidence (92% acc at ≥70% conf)
    min_ev: float = 0.03           # Raised: require stronger edge
    edge_threshold: float = 0.05   # Raised from 0.03: WBC markets less efficient but high vig
    confidence_min: float = 0.58   # Only bet when model confidence ≥ 58%
    max_recommendations: int = 3
    fractional_kelly: float = 0.15  # More conservative Kelly (was 0.25)
    max_stake_fraction: float = 0.04  # Reduced from 0.05
    market_priority: dict[str, int] = field(default_factory=lambda: {
        "ML": 3, "RL": 2, "OU": 1, "F5": 4, "TT": 1,
        # OE 已移除：純隨機市場 + 最高 vig，無模型邊際
    })


# ── Bankroll & Risk Config ──────────────────────────────────────────────────

@dataclass(frozen=True)
class BankrollConfig:
    initial_bankroll: float = 100_000.0
    max_single_bet_pct: float = 0.04    # Reduced for WBC (fewer games to recover)
    max_daily_exposure_pct: float = 0.08  # Reduced from 0.12
    consecutive_loss_threshold: int = 2   # Tighter: only 2 losses before reducing
    consecutive_loss_reduction: float = 0.50
    drawdown_conservative_pct: float = 0.08  # Enter conservative mode earlier
    daily_loss_stop_pct: float = 0.10     # Stop earlier
    volatility_lookback_days: int = 10    # Shorter for WBC (tournament is ~2 weeks)


# ── WBC Adjustment Coefficients ─────────────────────────────────────────────

@dataclass(frozen=True)
class WBCAdjustmentConfig:
    starter_impact: float = 0.70
    bullpen_impact: float = 1.40
    score_variance: float = 0.18
    strikeout_adj: float = 0.06
    xbh_adj: float = -0.04

    # Edge Realism Gate — WBC-specific thresholds (calibrated from 2023 backtest)
    # MLB default = 65; WBC markets are less efficient → lower thresholds
    # v4 backtest: Gate blocked 3 FAKE_EDGE (all losses), passed 7 → 86% win, +8.1% ROI
    edge_realism_thresholds: dict = field(default_factory=lambda: {
        "Pool": 50,             # Strictest: block low-liquidity Pool FAKE_EDGE
        "Quarter-Final": 45,    # More liquid, lower threshold
        "Semi-Final": 43,       # Near-institutional liquidity
        "Final": 40,            # Best liquidity → lowest threshold
    })
    mlb_edge_realism_threshold: float = 65.0  # Standard MLB threshold
    pitch_limits: dict = field(default_factory=lambda: {
        "Pool": {"max_pitches": 65, "rest_30": 1, "rest_50": 4},
        "Quarter-Final": {"max_pitches": 80, "rest_30": 1, "rest_50": 4},
        "Semi-Final": {"max_pitches": 95, "rest_30": 1, "rest_50": 4},
        "Final": {"max_pitches": 95, "rest_30": 1, "rest_50": 4},
    })
    round_adjustments: dict = field(default_factory=lambda: {
        "Pool": {"starter_impact": 0.55, "bullpen_impact": 1.60, "variance_add": 0.22},
        "Quarter-Final": {"starter_impact": 0.65, "bullpen_impact": 1.45, "variance_add": 0.18},
        "Semi-Final": {"starter_impact": 0.75, "bullpen_impact": 1.30, "variance_add": 0.14},
        "Final": {"starter_impact": 0.75, "bullpen_impact": 1.30, "variance_add": 0.14},
    })


# ── Market Calibration Config ───────────────────────────────────────────────

@dataclass(frozen=True)
class MarketConfig:
    steam_move_threshold: float = 0.10       # 10% odds shift = steam move
    steam_move_window_minutes: int = 30
    steam_weight_boost: float = 0.15          # Boost market weight by 15% on steam
    market_bias_decay: float = 0.95           # Exponential decay for historical bias
    tsl_vig_estimate: float = 0.08            # TSL house edge estimate
    pinnacle_vig_estimate: float = 0.03       # Pinnacle house edge estimate


# ── Scheduler Config ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SchedulerConfig:
    data_refresh_interval_hours: int = 1       # Data update every 1 hour
    model_retrain_interval_hours: int = 24     # Model retrain daily
    weight_adjust_interval_hours: int = 168    # Weight adjustment weekly (7*24)
    backtest_interval_hours: int = 24          # Backtest daily
    self_improve_interval_hours: int = 168     # Self-improvement weekly
    research_cycle_interval_hours: int = 24    # V3 research phase-gate cycle daily
    postgame_sync_interval_hours: int = 2      # 賽後回寫 + retrainer 更新（每 2 小時）
    artifact_rebuild_interval_hours: int = 168  # ML artifact 重建（每週；有資料更新時手動提前觸發）


# ── Self-Improvement Config ──────────────────────────────────────────────────

@dataclass(frozen=True)
class SelfImproveConfig:
    feature_importance_threshold: float = 0.01    # Min feature importance to keep
    model_performance_window: int = 50            # Last N predictions to evaluate
    weight_rebalance_min_samples: int = 20        # Min samples before reweighting
    max_features_to_drop: int = 3                 # Max features to drop per cycle
    performance_metric: str = "brier_score"       # Primary metric


# ── Data Recency Weights ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class DataRecencyConfig:
    premier12_2025: float = 0.30
    season_2025: float = 0.35
    spring_training: float = 0.25
    historical_wbc: float = 0.10


@dataclass(frozen=True)
class DeploymentGateConfig:
    enabled: bool = True
    min_walkforward_games: int = 500
    max_walkforward_brier: float = 0.255
    min_best_calibration_ml_roi: float = 0.0
    max_calibration_ece: float = 0.12    # 目標 Platt Scaling 後達 0.08；當前系統 0.1447
    require_artifact_schema_match: bool = True


# ── LLM / NLP Config ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LLMConfig:
    """
    NLP 賽前特徵提取層的 LLM Provider 設定。

    Provider 優先順序（自動 fallback）：
      1. groq      — 免費，速度最快 (100+ tok/s)，推薦首選
      2. gemini    — Google 免費 tier (15 RPM)
      3. anthropic — Claude Haiku，最精準但需付費
      4. openrouter— 聚合器，部分模型免費
      5. ollama    — 本地端，需自行架設
      6. rule      — 純規則引擎（無 API 時的最終 fallback）

    API Key 從環境變數讀取（.env 設定）
    """
    # Provider 選擇: "groq" | "gemini" | "anthropic" | "openrouter" | "ollama" | "rule"
    provider: str = "groq"
    # 各 Provider 模型名稱
    groq_model: str = "llama-3.1-8b-instant"      # 免費，極快
    gemini_model: str = "gemini-1.5-flash"         # 免費 tier
    anthropic_model: str = "claude-haiku-4-5-20251001"  # 最便宜 Claude
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct:free"  # 免費模型
    ollama_model: str = "qwen2.5:7b"
    ollama_base_url: str = "http://localhost:11434"
    timeout_seconds: int = 30
    # 是否在賽前分析中啟用 LLM（False = 直接使用規則引擎）
    enabled: bool = True


# ── Master Config ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AppConfig:
    sources: DataSourceConfig = field(default_factory=DataSourceConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    bankroll: BankrollConfig = field(default_factory=BankrollConfig)
    wbc: WBCAdjustmentConfig = field(default_factory=WBCAdjustmentConfig)
    market: MarketConfig = field(default_factory=MarketConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    self_improve: SelfImproveConfig = field(default_factory=SelfImproveConfig)
    data_recency: DataRecencyConfig = field(default_factory=DataRecencyConfig)
    deployment_gate: DeploymentGateConfig = field(default_factory=DeploymentGateConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
