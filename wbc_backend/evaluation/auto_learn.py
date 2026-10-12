#!/usr/bin/env python3
"""
自動學習優化系統 — Auto-Learn Optimizer v2

用真實 MLB 2025 數據 (2430 場 + 真實盤口) 自動搜索最佳模型組合。

策略:
  1. 從真實比賽數據建構 50+ 特徵
  2. 用 XGBoost 做 Walk-Forward CV 訓練
  3. 自動測試多組超參數
  4. 與真實盤口比較計算 CLV
  5. 只在高信心 + 有 edge 時投注
  6. 輸出最佳模型的真實回測勝率
"""
from __future__ import annotations

import math
import warnings
from collections import defaultdict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


# ═══════════════════════════════════════════════════════════════
# DATA LOADING
# ═══════════════════════════════════════════════════════════════

def load_data() -> pd.DataFrame:
    """Load and merge game results + real odds."""
    odds = pd.read_csv("data/mlb_2025/mlb_odds_2025_real.csv", encoding="latin1")
    odds["Home Score"] = pd.to_numeric(odds["Home Score"], errors="coerce")
    odds["Away Score"] = pd.to_numeric(odds["Away Score"], errors="coerce")
    odds["Away ML"] = pd.to_numeric(odds["Away ML"], errors="coerce")
    odds["Home ML"] = pd.to_numeric(odds["Home ML"], errors="coerce")
    odds["O/U"] = pd.to_numeric(odds["O/U"], errors="coerce")
    odds = odds.dropna(subset=["Home Score", "Away Score", "Away ML", "Home ML"])
    odds["home_win"] = (odds["Home Score"] > odds["Away Score"]).astype(int)
    odds["total_runs"] = odds["Home Score"] + odds["Away Score"]
    odds["margin"] = odds["Home Score"] - odds["Away Score"]

    # Convert American odds to decimal
    odds["home_decimal"] = odds["Home ML"].apply(american_to_decimal)
    odds["away_decimal"] = odds["Away ML"].apply(american_to_decimal)
    odds["home_implied"] = 1.0 / odds["home_decimal"]
    odds["away_implied"] = 1.0 / odds["away_decimal"]
    # Remove vig
    total_implied = odds["home_implied"] + odds["away_implied"]
    odds["home_fair"] = odds["home_implied"] / total_implied
    odds["away_fair"] = odds["away_implied"] / total_implied

    return odds.reset_index(drop=True)


def american_to_decimal(ml: float) -> float:
    if ml >= 100:
        return 1.0 + ml / 100.0
    elif ml <= -100:
        return 1.0 + 100.0 / abs(ml)
    return 2.0


# ═══════════════════════════════════════════════════════════════
# FEATURE ENGINEERING (50+ features)
# ═══════════════════════════════════════════════════════════════

class FeatureEngine:
    """Build rolling features from game history."""

    def __init__(self):
        self.team_runs_for: dict[str, list[int]] = defaultdict(list)
        self.team_runs_against: dict[str, list[int]] = defaultdict(list)
        self.team_results: dict[str, list[int]] = defaultdict(list)  # 1=win
        self.team_margins: dict[str, list[int]] = defaultdict(list)
        self.team_totals: dict[str, list[float]] = defaultdict(list)
        self.h2h_results: dict[str, list[int]] = defaultdict(list)
        self.pitcher_results: dict[str, list[int]] = defaultdict(list)
        self.pitcher_runs: dict[str, list[int]] = defaultdict(list)
        self.team_games_as_home: dict[str, list[int]] = defaultdict(list)
        self.team_games_as_away: dict[str, list[int]] = defaultdict(list)
        # Elo
        self.elo: dict[str, float] = defaultdict(lambda: 1500.0)
        self.elo_k = 6.0

    def _rolling(self, data: list, w: int) -> list:
        return data[-w:] if data else []

    def _mean(self, data: list, w: int) -> float:
        d = self._rolling(data, w)
        return sum(d) / len(d) if d else 0.0

    def _std(self, data: list, w: int) -> float:
        d = self._rolling(data, w)
        if len(d) < 2:
            return 0.0
        m = sum(d) / len(d)
        return (sum((x - m) ** 2 for x in d) / len(d)) ** 0.5

    def build_features(self, home: str, away: str, home_sp: str, away_sp: str,
                       home_fair: float, ou_line: float) -> dict[str, float]:
        f = {}

        for w in [5, 10, 20, 40]:
            # RPG
            f[f"home_rpg_{w}"] = self._mean(self.team_runs_for[home], w)
            f[f"away_rpg_{w}"] = self._mean(self.team_runs_for[away], w)
            f[f"home_rapg_{w}"] = self._mean(self.team_runs_against[home], w)
            f[f"away_rapg_{w}"] = self._mean(self.team_runs_against[away], w)
            # Win pct
            f[f"home_wpct_{w}"] = self._mean(self.team_results[home], w)
            f[f"away_wpct_{w}"] = self._mean(self.team_results[away], w)
            # Margin
            f[f"home_margin_{w}"] = self._mean(self.team_margins[home], w)
            f[f"away_margin_{w}"] = self._mean(self.team_margins[away], w)

        # Differentials
        for w in [10, 20]:
            f[f"rpg_diff_{w}"] = f[f"home_rpg_{w}"] - f[f"away_rpg_{w}"]
            f[f"rapg_diff_{w}"] = f[f"home_rapg_{w}"] - f[f"away_rapg_{w}"]
            f[f"wpct_diff_{w}"] = f[f"home_wpct_{w}"] - f[f"away_wpct_{w}"]
            f[f"margin_diff_{w}"] = f[f"home_margin_{w}"] - f[f"away_margin_{w}"]

        # Run differential (strength indicator)
        f["home_run_diff_20"] = f["home_rpg_20"] - f["home_rapg_20"]
        f["away_run_diff_20"] = f["away_rpg_20"] - f["away_rapg_20"]
        f["run_diff_advantage"] = f["home_run_diff_20"] - f["away_run_diff_20"]

        # Volatility
        f["home_scoring_std_20"] = self._std(self.team_runs_for[home], 20)
        f["away_scoring_std_20"] = self._std(self.team_runs_for[away], 20)

        # Pythagorean expectation
        h_rpg = max(f["home_rpg_40"], 0.1)
        h_rapg = max(f["home_rapg_40"], 0.1)
        a_rpg = max(f["away_rpg_40"], 0.1)
        a_rapg = max(f["away_rapg_40"], 0.1)
        f["home_pythag"] = h_rpg ** 1.83 / (h_rpg ** 1.83 + h_rapg ** 1.83)
        f["away_pythag"] = a_rpg ** 1.83 / (a_rpg ** 1.83 + a_rapg ** 1.83)
        f["pythag_diff"] = f["home_pythag"] - f["away_pythag"]

        # Elo features
        f["home_elo"] = self.elo[home]
        f["away_elo"] = self.elo[away]
        f["elo_diff"] = self.elo[home] - self.elo[away]
        f["elo_prob"] = 1.0 / (1.0 + 10 ** (-f["elo_diff"] / 400.0))

        # Streak (last 5)
        last5_h = self._rolling(self.team_results[home], 5)
        last5_a = self._rolling(self.team_results[away], 5)
        # Current streak length
        h_streak = 0
        for r in reversed(last5_h):
            if r == (1 if last5_h and last5_h[-1] else 0):
                h_streak += 1
            else:
                break
        a_streak = 0
        for r in reversed(last5_a):
            if r == (1 if last5_a and last5_a[-1] else 0):
                a_streak += 1
            else:
                break
        f["home_streak"] = h_streak * (1 if last5_h and last5_h[-1] else -1)
        f["away_streak"] = a_streak * (1 if last5_a and last5_a[-1] else -1)
        f["streak_diff"] = f["home_streak"] - f["away_streak"]

        # Head-to-head
        h2h_key = f"{home}_vs_{away}"
        h2h = self._rolling(self.h2h_results.get(h2h_key, []), 10)
        f["h2h_home_wpct"] = sum(h2h) / len(h2h) if h2h else 0.5
        f["h2h_n"] = len(h2h)

        # Pitcher features
        h_sp_wins = self._rolling(self.pitcher_results.get(home_sp, []), 10)
        a_sp_wins = self._rolling(self.pitcher_results.get(away_sp, []), 10)
        h_sp_runs = self._rolling(self.pitcher_runs.get(home_sp, []), 10)
        a_sp_runs = self._rolling(self.pitcher_runs.get(away_sp, []), 10)
        f["home_sp_wpct"] = sum(h_sp_wins) / len(h_sp_wins) if h_sp_wins else 0.5
        f["away_sp_wpct"] = sum(a_sp_wins) / len(a_sp_wins) if a_sp_wins else 0.5
        f["home_sp_avg_runs"] = sum(h_sp_runs) / len(h_sp_runs) if h_sp_runs else 4.5
        f["away_sp_avg_runs"] = sum(a_sp_runs) / len(a_sp_runs) if a_sp_runs else 4.5
        f["sp_wpct_diff"] = f["home_sp_wpct"] - f["away_sp_wpct"]
        f["sp_runs_diff"] = f["away_sp_avg_runs"] - f["home_sp_avg_runs"]  # Positive = home advantage

        # Market features (use as additional signal)
        f["market_home_prob"] = home_fair
        f["market_away_prob"] = 1 - home_fair
        f["ou_line"] = ou_line

        # Home performance at home vs away performance away
        h_home = self._rolling(self.team_games_as_home.get(home, []), 20)
        a_away = self._rolling(self.team_games_as_away.get(away, []), 20)
        f["home_at_home_wpct"] = sum(h_home) / len(h_home) if h_home else 0.54
        f["away_on_road_wpct"] = sum(a_away) / len(a_away) if a_away else 0.46

        return f

    def update(self, home: str, away: str, home_score: int, away_score: int,
               home_sp: str, away_sp: str):
        hw = 1 if home_score > away_score else 0
        margin = home_score - away_score
        total = home_score + away_score

        self.team_runs_for[home].append(home_score)
        self.team_runs_for[away].append(away_score)
        self.team_runs_against[home].append(away_score)
        self.team_runs_against[away].append(home_score)
        self.team_results[home].append(hw)
        self.team_results[away].append(1 - hw)
        self.team_margins[home].append(margin)
        self.team_margins[away].append(-margin)
        self.team_totals[home].append(total)
        self.team_totals[away].append(total)
        self.team_games_as_home[home].append(hw)
        self.team_games_as_away[away].append(1 - hw)

        h2h_key = f"{home}_vs_{away}"
        self.h2h_results[h2h_key].append(hw)
        h2h_key_rev = f"{away}_vs_{home}"
        self.h2h_results[h2h_key_rev].append(1 - hw)

        # Pitcher tracking
        self.pitcher_results[home_sp].append(hw)
        self.pitcher_results[away_sp].append(1 - hw)
        self.pitcher_runs[home_sp].append(away_score)  # Runs allowed
        self.pitcher_runs[away_sp].append(home_score)

        # Elo update
        elo_exp = 1.0 / (1.0 + 10 ** (-(self.elo[home] - self.elo[away]) / 400.0))
        mov = 1.0 + 0.06 * min(abs(margin), 10)
        delta = self.elo_k * mov * (hw - elo_exp)
        self.elo[home] += delta
        self.elo[away] -= delta


# ═══════════════════════════════════════════════════════════════
# AUTO-LEARN: Hyperparameter Search
# ═══════════════════════════════════════════════════════════════

def walk_forward_backtest(  # noqa: C901
    df: pd.DataFrame,
    warm_up: int = 200,
    train_window: int = 400,
    retrain_every: int = 50,
    xgb_params: dict = None,
    bet_threshold: float = 0.03,
    confidence_min: float = 0.55,
    kelly_fraction: float = 0.15,
    verbose: bool = True,
) -> dict:
    """
    Walk-forward backtest with XGBoost.

    1. Use first `warm_up` games to build initial features
    2. Train XGBoost on rolling `train_window` games
    3. Retrain every `retrain_every` games
    4. Predict + bet on each subsequent game
    """
    import xgboost as xgb

    if xgb_params is None:
        xgb_params = {
            "n_estimators": 200,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 5,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
            "random_state": 42,
            "eval_metric": "logloss",
        }

    engine = FeatureEngine()
    model = None
    feature_names = None

    # Collect training data
    all_features = []
    all_labels = []

    # Results
    predictions = []
    total_pred = 0
    correct_pred = 0
    bankroll = 100_000.0
    peak = 100_000.0
    max_dd = 0.0
    total_staked = 0.0
    total_pnl = 0.0
    bet_count = 0
    bet_wins = 0
    bet_pnls = []

    for idx, row in df.iterrows():
        home = row["Home"]
        away = row["Away"]
        hs = int(row["Home Score"])
        aws = int(row["Away Score"])
        hw = int(row["home_win"])
        home_sp = str(row.get("Home Starter", ""))
        away_sp = str(row.get("Away Starter", ""))
        home_fair = float(row["home_fair"])
        ou_line = float(row["O/U"])
        home_dec = float(row["home_decimal"])
        away_dec = float(row["away_decimal"])

        if idx < warm_up:
            # Warm-up: build features, no prediction
            if idx >= 30:  # Need at least 30 games for features
                feat = engine.build_features(home, away, home_sp, away_sp, home_fair, ou_line)
                all_features.append(feat)
                all_labels.append(hw)
            engine.update(home, away, hs, aws, home_sp, away_sp)
            continue

        # ── Build features for this game ──
        feat = engine.build_features(home, away, home_sp, away_sp, home_fair, ou_line)
        if feature_names is None:
            feature_names = sorted(feat.keys())

        X_row = np.array([feat.get(f, 0.0) for f in feature_names]).reshape(1, -1)

        # ── Train/retrain model ──
        if (model is None or (idx - warm_up) % retrain_every == 0) and len(all_features) >= 50:
            X_train = np.array([[f.get(fn, 0.0) for fn in feature_names] for f in all_features])
            y_train = np.array(all_labels)

            # Use last train_window samples only
            if len(X_train) > train_window:
                X_train = X_train[-train_window:]
                y_train = y_train[-train_window:]

            model = xgb.XGBClassifier(**xgb_params, use_label_encoder=False, verbosity=0)
            model.fit(X_train, y_train, verbose=False)

        # ── Predict ──
        if model is not None:
            prob_home = float(model.predict_proba(X_row)[0, 1])
        else:
            prob_home = 0.5

        prob_home = max(0.05, min(0.95, prob_home))

        # ── Evaluate accuracy ──
        total_pred += 1
        predicted_home = prob_home > 0.5
        if predicted_home == (hw == 1):
            correct_pred += 1

        predictions.append({
            "idx": idx,
            "home": home,
            "away": away,
            "prob": prob_home,
            "actual": hw,
            "correct": predicted_home == (hw == 1),
            "home_fair": home_fair,
        })

        # ── Betting against real odds ──
        edge_home = prob_home - home_fair
        edge_away = (1 - prob_home) - (1 - home_fair)

        bet_side = None
        bet_prob = 0.0
        bet_odds = 1.0

        if edge_home > bet_threshold and prob_home > confidence_min:
            bet_side = "home"
            bet_prob = prob_home
            bet_odds = home_dec
        elif edge_away > bet_threshold and (1 - prob_home) > confidence_min:
            bet_side = "away"
            bet_prob = 1 - prob_home
            bet_odds = away_dec

        if bet_side and bet_odds > 1.0:
            b = bet_odds - 1
            k = max(0, (b * bet_prob - (1 - bet_prob)) / b) * kelly_fraction
            stake = bankroll * min(k, 0.04)

            if stake >= 10:
                won = (bet_side == "home" and hw == 1) or (bet_side == "away" and hw == 0)
                pnl = stake * (bet_odds - 1) if won else -stake

                bankroll += pnl
                total_staked += stake
                total_pnl += pnl
                bet_count += 1
                if won:
                    bet_wins += 1
                bet_pnls.append(pnl)
                peak = max(peak, bankroll)
                dd = (peak - bankroll) / peak
                max_dd = max(max_dd, dd)

        # ── Update history ──
        all_features.append(feat)
        all_labels.append(hw)
        engine.update(home, away, hs, aws, home_sp, away_sp)

    # ── Summary metrics ──
    accuracy = correct_pred / total_pred if total_pred else 0
    roi = total_pnl / total_staked if total_staked > 0 else 0
    bet_acc = bet_wins / bet_count if bet_count else 0

    if len(bet_pnls) >= 2:
        arr = np.array(bet_pnls)
        sharpe = (arr.mean() / max(arr.std(), 1e-8)) * math.sqrt(252)
    else:
        sharpe = 0.0

    # Brier & logloss
    probs = np.array([p["prob"] for p in predictions])
    actuals = np.array([p["actual"] for p in predictions])
    brier = float(np.mean((probs - actuals) ** 2))
    ll = float(np.mean(-(actuals * np.log(np.clip(probs, 1e-6, 1)) +
                          (1 - actuals) * np.log(np.clip(1 - probs, 1e-6, 1)))))

    # Confidence band accuracy
    conf_bands = {}
    for p in predictions:
        max_p = max(p["prob"], 1 - p["prob"])
        if max_p < 0.55:
            band = "uncertain"
        elif max_p < 0.60:
            band = "lean"
        elif max_p < 0.65:
            band = "moderate"
        elif max_p < 0.75:
            band = "strong"
        else:
            band = "very_strong"
        if band not in conf_bands:
            conf_bands[band] = {"correct": 0, "total": 0}
        conf_bands[band]["total"] += 1
        if p["correct"]:
            conf_bands[band]["correct"] += 1

    # Feature importance
    importance = {}
    if model is not None and hasattr(model, "feature_importances_"):
        for name, imp in zip(feature_names, model.feature_importances_):
            importance[name] = float(imp)

    result = {
        "accuracy": accuracy,
        "total_predictions": total_pred,
        "correct": correct_pred,
        "brier": brier,
        "logloss": ll,
        "bet_count": bet_count,
        "bet_wins": bet_wins,
        "bet_accuracy": bet_acc,
        "roi": roi,
        "total_pnl": total_pnl,
        "bankroll": bankroll,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "conf_bands": conf_bands,
        "importance": importance,
        "params": xgb_params,
    }

    return result


# ═══════════════════════════════════════════════════════════════
# GRID SEARCH — Auto-learn best config
# ═══════════════════════════════════════════════════════════════

def auto_learn():
    print()
    print("=" * 70)
    print("🧬 自動學習優化系統 — Auto-Learn Optimizer")
    print("   MLB 2025 × 2430 場 × 真實盤口 × XGBoost Walk-Forward")
    print("=" * 70)
    print()

    df = load_data()
    print(f"✅ 載入 {len(df)} 場 (含真實 ML/RL/OU 盤口)")
    print()

    configs = [
        {
            "name": "Config A: Conservative (深度3, 慢學)",
            "params": {"n_estimators": 150, "max_depth": 3, "learning_rate": 0.03,
                       "subsample": 0.8, "colsample_bytree": 0.7, "min_child_weight": 8,
                       "reg_alpha": 0.5, "reg_lambda": 2.0, "random_state": 42, "eval_metric": "logloss"},
            "warm_up": 200, "train_window": 500, "retrain_every": 30,
            "bet_threshold": 0.04, "confidence_min": 0.57, "kelly_fraction": 0.12,
        },
        {
            "name": "Config B: Balanced (深度4, 中等)",
            "params": {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05,
                       "subsample": 0.8, "colsample_bytree": 0.8, "min_child_weight": 5,
                       "reg_alpha": 0.1, "reg_lambda": 1.0, "random_state": 42, "eval_metric": "logloss"},
            "warm_up": 200, "train_window": 400, "retrain_every": 50,
            "bet_threshold": 0.03, "confidence_min": 0.55, "kelly_fraction": 0.15,
        },
        {
            "name": "Config C: Aggressive (深度5, 快學)",
            "params": {"n_estimators": 300, "max_depth": 5, "learning_rate": 0.08,
                       "subsample": 0.7, "colsample_bytree": 0.7, "min_child_weight": 3,
                       "reg_alpha": 0.05, "reg_lambda": 0.5, "random_state": 42, "eval_metric": "logloss"},
            "warm_up": 150, "train_window": 300, "retrain_every": 40,
            "bet_threshold": 0.025, "confidence_min": 0.53, "kelly_fraction": 0.18,
        },
        {
            "name": "Config D: High-Filter (只投強信心)",
            "params": {"n_estimators": 200, "max_depth": 4, "learning_rate": 0.05,
                       "subsample": 0.85, "colsample_bytree": 0.8, "min_child_weight": 5,
                       "reg_alpha": 0.2, "reg_lambda": 1.5, "random_state": 42, "eval_metric": "logloss"},
            "warm_up": 250, "train_window": 600, "retrain_every": 40,
            "bet_threshold": 0.06, "confidence_min": 0.60, "kelly_fraction": 0.10,
        },
        {
            "name": "Config E: Wide Window (大樣本學習)",
            "params": {"n_estimators": 250, "max_depth": 4, "learning_rate": 0.04,
                       "subsample": 0.9, "colsample_bytree": 0.9, "min_child_weight": 6,
                       "reg_alpha": 0.1, "reg_lambda": 1.0, "random_state": 42, "eval_metric": "logloss"},
            "warm_up": 300, "train_window": 800, "retrain_every": 60,
            "bet_threshold": 0.035, "confidence_min": 0.56, "kelly_fraction": 0.12,
        },
    ]

    best_result = None
    best_name = ""
    all_results = []

    for cfg in configs:
        print(f"━━━ Testing: {cfg['name']} ━━━")
        result = walk_forward_backtest(
            df,
            warm_up=cfg["warm_up"],
            train_window=cfg["train_window"],
            retrain_every=cfg["retrain_every"],
            xgb_params=cfg["params"],
            bet_threshold=cfg["bet_threshold"],
            confidence_min=cfg["confidence_min"],
            kelly_fraction=cfg["kelly_fraction"],
            verbose=False,
        )
        result["name"] = cfg["name"]
        all_results.append(result)

        print(f"  準確率: {result['accuracy']:.1%}  |  "
              f"Brier: {result['brier']:.4f}  |  "
              f"投注: {result['bet_count']}場 {result['bet_accuracy']:.1%}  |  "
              f"ROI: {result['roi']:+.2%}  |  "
              f"DD: {result['max_dd']:.1%}")

        # Score: accuracy * 2 + ROI * 5 - max_dd * 1 (penalize drawdown)
        score = result["accuracy"] * 2 + max(0, result["roi"]) * 5 - result["max_dd"] * 1
        result["score"] = score

        if best_result is None or score > best_result["score"]:
            best_result = result
            best_name = cfg["name"]

    # ═══════════════════════════════════════════════════════
    # BEST MODEL REPORT
    # ═══════════════════════════════════════════════════════
    print()
    print("=" * 70)
    print(f"🏆 最佳模型: {best_name}")
    print("=" * 70)
    print()

    r = best_result

    print("━" * 60)
    print("🎯 預測準確度")
    print("━" * 60)
    print(f"  總預測場數:     {r['total_predictions']}")
    print(f"  整體準確率:     {r['accuracy']:.1%}  ({r['correct']}/{r['total_predictions']})")
    print(f"  Brier Score:    {r['brier']:.4f}  (隨機=0.2500)")
    print(f"  Log Loss:       {r['logloss']:.4f}  (隨機=0.6931)")
    print()

    print("━" * 60)
    print("📊 各信心度準確率")
    print("━" * 60)
    for band in ["uncertain", "lean", "moderate", "strong", "very_strong"]:
        if band in r["conf_bands"]:
            d = r["conf_bands"][band]
            acc = d["correct"] / d["total"] if d["total"] else 0
            marker = "🎯" if acc > 0.58 else "✅" if acc > 0.53 else "  "
            print(f"  {marker} {band:15s}: {acc:.1%}  ({d['correct']}/{d['total']})")
    print()

    print("━" * 60)
    print("💰 投注回測 (用真實盤口)")
    print("━" * 60)
    print(f"  投注場數:       {r['bet_count']}")
    print(f"  投注勝率:       {r['bet_accuracy']:.1%}  ({r['bet_wins']}/{r['bet_count']})")
    print(f"  ROI:            {r['roi']:+.2%}")
    print(f"  淨利:           ${r['total_pnl']:+,.0f}")
    print(f"  最終資金:       ${r['bankroll']:,.0f}")
    print(f"  Sharpe Ratio:   {r['sharpe']:.2f}")
    print(f"  Max Drawdown:   {r['max_dd']:.1%}")
    print()

    # Feature importance
    if r["importance"]:
        print("━" * 60)
        print("🧬 最重要特徵 (Top 15)")
        print("━" * 60)
        sorted_imp = sorted(r["importance"].items(), key=lambda x: -x[1])[:15]
        max_imp = sorted_imp[0][1] if sorted_imp else 1
        for name, imp in sorted_imp:
            bar = "█" * int(imp / max_imp * 30)
            print(f"  {name:30s}: {imp:.4f} {bar}")
        print()

    # ─── Comparison table ────────────────────────────────
    print("━" * 60)
    print("📋 所有配置比較")
    print("━" * 60)
    print(f"  {'Configuration':<40s} {'Acc':>6s} {'Brier':>7s} {'Bets':>5s} {'BetAcc':>7s} {'ROI':>8s} {'DD':>6s} {'Score':>7s}")
    print(f"  {'─'*40} {'─'*6} {'─'*7} {'─'*5} {'─'*7} {'─'*8} {'─'*6} {'─'*7}")
    for r2 in sorted(all_results, key=lambda x: -x["score"]):
        marker = "🏆" if r2["name"] == best_name else "  "
        print(f"  {marker}{r2['name']:<38s} {r2['accuracy']:>5.1%} {r2['brier']:>7.4f} "
              f"{r2['bet_count']:>5d} {r2['bet_accuracy']:>6.1%} {r2['roi']:>+7.2%} "
              f"{r2['max_dd']:>5.1%} {r2['score']:>7.3f}")

    print()
    print("=" * 70)
    print("✅ 自動學習完成")
    print("=" * 70)

    return best_result


if __name__ == "__main__":
    auto_learn()
