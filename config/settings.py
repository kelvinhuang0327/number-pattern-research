"""
Global configuration for WBC Betting Engine.
"""

# ── Bankroll ──────────────────────────────────────────────
INITIAL_BANKROLL = 100_000          # 初始資金 (TWD or unit)
MAX_SINGLE_BET_PCT = 0.015          # 單場上限 1.5%
MAX_DAILY_EXPOSURE_PCT = 0.04       # 同日上限 4%
CONSECUTIVE_LOSS_THRESHOLD = 3      # 連敗幾場降注
CONSECUTIVE_LOSS_REDUCTION = 0.50   # 降注比例
DRAWDOWN_MAX = 0.20                 # V3 Drawdown Adaptive Kelly: 20% D_max threshold
DRAWDOWN_K_FACTOR = 2.0             # V3 Drawdown Adaptive Kelly: quadratic decay (k=2)

# ── Value Bet Thresholds ─────────────────────────────────
EV_STRONG = 0.07     # ≥7% → 強下注
EV_MEDIUM = 0.03     # 3~7% → 中下注
EV_SMALL  = 0.01     # 1~3% → 小下注
EV_PASS   = 0.01     # <1% → 不下注

# ── Kelly Criterion ──────────────────────────────────────
KELLY_FRACTION = 0.15               # V3: 使用 1/6 Kelly (Institutionally conservative)

# ── Risk Control ─────────────────────────────────────────
DAILY_LOSS_STOP_PCT = 0.15          # 當日虧損 ≥15% 停止
MODEL_ERROR_THRESHOLD = 0.20        # 預測誤差門檻
MODEL_ERROR_CONSECUTIVE = 3         # 連續幾場觸發停止
MARKET_ANOMALY_LIMIT = 3            # 異常訊號上限

# ── Live Betting ─────────────────────────────────────────
LIVE_EV_TRIGGER = 0.10              # Live EV ≥10% 觸發

# ── Monte Carlo ──────────────────────────────────────────
MC_SIMULATIONS = 1000

# ── WBC Pitch Count Limits ───────────────────────────────
# Official WBC pitch-count rules per tournament round
WBC_PITCH_LIMITS = {
    "Pool":          {"max_pitches": 65,  "rest_30": 1, "rest_50": 4},
    "Quarter-Final": {"max_pitches": 80,  "rest_30": 1, "rest_50": 4},
    "Semi-Final":    {"max_pitches": 95,  "rest_30": 1, "rest_50": 4},
    "Final":         {"max_pitches": 95,  "rest_30": 1, "rest_50": 4},
}

# Estimated SP innings per round (based on ~16 pitches/inning)
WBC_SP_EXPECTED_INNINGS = {
    "Pool":          3.5,   # 65球 ÷ ~18 球/局 ≈ 3.6
    "Quarter-Final": 4.5,   # 80球 ÷ ~18 球/局 ≈ 4.4
    "Semi-Final":    5.5,   # 95球 ÷ ~17 球/局 ≈ 5.6
    "Final":         5.5,
}

# ── WBC Adjustment Coefficients ──────────────────────────
WBC_STARTER_IMPACT   = 0.70         # 先發投手影響 ×0.7 (預賽更低)
WBC_BULLPEN_IMPACT   = 1.40         # 牛棚影響 ×1.4
WBC_SCORE_VARIANCE   = 0.18         # 分數變異數 +18%
WBC_STRIKEOUT_ADJ    = 0.06         # 三振率 +6% (國際賽陌生度)
WBC_XBH_ADJ          = -0.04        # 長打率 −4% (國際賽陌生度)

# Per-round overrides: pool play amplifies bullpen, dampens SP further
WBC_ROUND_ADJUSTMENTS = {
    "Pool":          {"starter_impact": 0.55, "bullpen_impact": 1.60, "variance_add": 0.22},
    "Quarter-Final": {"starter_impact": 0.65, "bullpen_impact": 1.45, "variance_add": 0.18},
    "Semi-Final":    {"starter_impact": 0.75, "bullpen_impact": 1.30, "variance_add": 0.14},
    "Final":         {"starter_impact": 0.75, "bullpen_impact": 1.30, "variance_add": 0.14},
}

# ── Data Recency Weights ─────────────────────────────────
# WBC is held in Feb-Mar; current form matters most
DATA_WEIGHTS = {
    "premier12_2025":    0.30,   # 2025 世界12強賽 (最近國際賽)
    "season_2025":       0.35,   # 2025 MLB/NPB/KBO 完整球季
    "spring_training":   0.25,   # 2026 春訓 & 熱身賽 (當下狀態)
    "historical_wbc":    0.10,   # 歷屆 WBC 表現
}

# ── Roster Volatility ────────────────────────────────────
# Star player impact multiplier on team win probability
STAR_PLAYER_IMPACT = {
    "mvp_caliber":     0.06,   # e.g. Ohtani, Soto — 勝率影響 ±6%
    "all_star":        0.03,   # e.g. 佐佐木朗希, 古林睿煬
    "key_role_player": 0.015,  # e.g. setup man, leadoff hitter
}

# ── Ensemble Model Weights (initial) ────────────────────
MODEL_WEIGHTS = {
    "elo":        0.20,
    "bayesian":   0.25,
    "poisson":    0.20,
    "gbm":        0.15,
    "monte_carlo": 0.20,
}

# ── Data sources (placeholder URLs) ─────────────────────
DATA_SOURCES = {
    "stats_api":    "https://statsapi.mlb.com/api/v1",
    "odds_api":     "https://api.the-odds-api.com/v4/sports",
    "wbc_schedule": "https://www.worldbaseballclassic.com/schedule",
}
