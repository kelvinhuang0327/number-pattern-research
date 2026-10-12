#!/usr/bin/env python3
"""
CLV 反向策略 — Closing Line Value 打敗市場

核心思路轉變:
  不再試圖「預測誰贏」→ 改為「找出市場定價錯誤的時機」

方法:
  1. 用市場盤口作為基準 (base truth)
  2. 只在特定數據 pattern 偏離市場時投注
  3. 利用「市場反應不足」的場景 (hot streak, SP dominance, fatigue)
  4. 嚴格控制: 只在高 edge + 高信心場次下注
  5. 用 LightGBM 學習「何時市場錯了」
"""
from __future__ import annotations

import warnings
from collections import defaultdict

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")


def american_to_decimal(ml: float) -> float:
    if ml >= 100:
        return 1.0 + ml / 100.0
    elif ml <= -100:
        return 1.0 + 100.0 / abs(ml)
    return 2.0


def load_data() -> pd.DataFrame:
    odds = pd.read_csv("data/mlb_2025/mlb_odds_2025_real.csv", encoding="latin1")
    for col in ["Home Score", "Away Score", "Away ML", "Home ML", "O/U"]:
        odds[col] = pd.to_numeric(odds[col], errors="coerce")
    odds = odds.dropna(subset=["Home Score", "Away Score", "Away ML", "Home ML"])
    odds["home_win"] = (odds["Home Score"] > odds["Away Score"]).astype(int)
    odds["total_runs"] = odds["Home Score"] + odds["Away Score"]
    odds["home_decimal"] = odds["Home ML"].apply(american_to_decimal)
    odds["away_decimal"] = odds["Away ML"].apply(american_to_decimal)
    odds["home_implied"] = 1.0 / odds["home_decimal"]
    odds["away_implied"] = 1.0 / odds["away_decimal"]
    total_imp = odds["home_implied"] + odds["away_implied"]
    odds["home_fair"] = odds["home_implied"] / total_imp
    odds["away_fair"] = odds["away_implied"] / total_imp
    return odds.reset_index(drop=True)


class Tracker:
    def __init__(self):
        self.runs_for: dict[str, list[int]] = defaultdict(list)
        self.runs_against: dict[str, list[int]] = defaultdict(list)
        self.results: dict[str, list[int]] = defaultdict(list)
        self.margins: dict[str, list[int]] = defaultdict(list)
        self.sp_wins: dict[str, list[int]] = defaultdict(list)
        self.sp_runs: dict[str, list[int]] = defaultdict(list)
        self.sp_starts: dict[str, int] = defaultdict(int)
        self.elo: dict[str, float] = defaultdict(lambda: 1500.0)
        self.home_results: dict[str, list[int]] = defaultdict(list)
        self.away_results: dict[str, list[int]] = defaultdict(list)
        self.vs_market: dict[str, list[float]] = defaultdict(list)  # actual - implied

    def _avg(self, data: list, w: int) -> float:
        d = data[-w:] if data else []
        return sum(d) / len(d) if d else 0.0

    def _std(self, data: list, w: int) -> float:
        d = data[-w:]
        if len(d) < 2:
            return 0.0
        m = sum(d) / len(d)
        return (sum((x - m) ** 2 for x in d) / len(d)) ** 0.5

    def build_edge_features(self, home: str, away: str, home_sp: str, away_sp: str,
                             home_fair: float, ou_line: float) -> dict[str, float]:
        """Build features focused on where market might be wrong."""
        f = {}

        # ── MARKET AS BASELINE ──
        f["market_prob"] = home_fair

        # ── MOMENTUM vs MARKET (market slow to react to streaks) ──
        for w in [5, 10, 15]:
            h_wpct = self._avg(self.results[home], w)
            a_wpct = self._avg(self.results[away], w)
            f[f"home_momentum_{w}"] = h_wpct - home_fair      # Positive = team hotter than market thinks
            f[f"away_momentum_{w}"] = a_wpct - (1 - home_fair)
            f[f"momentum_gap_{w}"] = f[f"home_momentum_{w}"] - f[f"away_momentum_{w}"]

        # ── RUN DIFF vs MARKET EXPECTATION ──
        for w in [10, 20, 30]:
            h_rd = self._avg(self.runs_for[home], w) - self._avg(self.runs_against[home], w)
            a_rd = self._avg(self.runs_for[away], w) - self._avg(self.runs_against[away], w)
            f[f"home_run_diff_{w}"] = h_rd
            f[f"away_run_diff_{w}"] = a_rd
            f[f"run_diff_gap_{w}"] = h_rd - a_rd

        # ── PYTHAGOREAN vs MARKET ──
        for w in [20, 40]:
            h_rpg = max(self._avg(self.runs_for[home], w), 0.1)
            h_rapg = max(self._avg(self.runs_against[home], w), 0.1)
            a_rpg = max(self._avg(self.runs_for[away], w), 0.1)
            a_rapg = max(self._avg(self.runs_against[away], w), 0.1)
            h_pyth = h_rpg ** 1.83 / (h_rpg ** 1.83 + h_rapg ** 1.83)
            a_pyth = a_rpg ** 1.83 / (a_rpg ** 1.83 + a_rapg ** 1.83)
            # Log5
            p_hat = h_pyth * (1 - a_pyth) / (h_pyth * (1 - a_pyth) + a_pyth * (1 - h_pyth)) if (h_pyth + a_pyth > 0) else 0.5
            f[f"pythag_vs_market_{w}"] = p_hat - home_fair  # KEY: positive = market undervalues home

        # ── ELO vs MARKET ──
        elo_diff = self.elo[home] - self.elo[away]
        elo_prob = 1.0 / (1.0 + 10 ** (-elo_diff / 400.0))
        f["elo_vs_market"] = elo_prob - home_fair

        # ── STARTING PITCHER EDGE ──
        h_sp_team_wpct = self._avg(self.sp_wins.get(home_sp, []), 8)
        a_sp_team_wpct = self._avg(self.sp_wins.get(away_sp, []), 8)
        h_sp_ra = self._avg(self.sp_runs.get(home_sp, []), 8)
        a_sp_ra = self._avg(self.sp_runs.get(away_sp, []), 8)
        h_sp_n = self.sp_starts.get(home_sp, 0)
        a_sp_n = self.sp_starts.get(away_sp, 0)
        f["sp_wpct_edge"] = h_sp_team_wpct - a_sp_team_wpct
        f["sp_ra_edge"] = a_sp_ra - h_sp_ra  # Positive = home SP better
        f["home_sp_n"] = min(h_sp_n, 30)
        f["away_sp_n"] = min(a_sp_n, 30)

        # ── HOME/AWAY SPLIT ──
        h_home_wpct = self._avg(self.home_results[home], 20)
        a_away_wpct = self._avg(self.away_results[away], 20)
        f["home_venue_edge"] = h_home_wpct - home_fair
        f["away_venue_weakness"] = a_away_wpct - (1 - home_fair)

        # ── SCORING VOLATILITY (volatile teams = more upset potential) ──
        f["home_scoring_vol"] = self._std(self.runs_for[home], 20)
        f["away_scoring_vol"] = self._std(self.runs_for[away], 20)

        # ── HISTORICAL MARKET ACCURACY for each team ──
        # How well has the market priced this team recently?
        f["home_vs_market_bias"] = self._avg(self.vs_market[home], 20)  # Positive = team beats expectations
        f["away_vs_market_bias"] = self._avg(self.vs_market[away], 20)

        # ── O/U line as proxy for game environment ──
        f["ou_line"] = ou_line
        h_total = self._avg(self.runs_for[home], 15) + self._avg(self.runs_against[home], 15)
        a_total = self._avg(self.runs_for[away], 15) + self._avg(self.runs_against[away], 15)
        f["total_vs_ou"] = (h_total + a_total) / 2 - ou_line

        # ── STREAK FEATURES ──
        streak = 0
        for r in reversed(self.results[home][-10:]):
            if r == (self.results[home][-1] if self.results[home] else 0):
                streak += 1
            else:
                break
        f["home_streak"] = streak * (1 if self.results[home] and self.results[home][-1] else -1)

        streak = 0
        for r in reversed(self.results[away][-10:]):
            if r == (self.results[away][-1] if self.results[away] else 0):
                streak += 1
            else:
                break
        f["away_streak"] = streak * (1 if self.results[away] and self.results[away][-1] else -1)

        return f

    def update(self, home, away, hs, aws, home_sp, away_sp, home_fair):
        hw = 1 if hs > aws else 0
        margin = hs - aws

        self.runs_for[home].append(hs)
        self.runs_for[away].append(aws)
        self.runs_against[home].append(aws)
        self.runs_against[away].append(hs)
        self.results[home].append(hw)
        self.results[away].append(1 - hw)
        self.margins[home].append(margin)
        self.margins[away].append(-margin)
        self.home_results[home].append(hw)
        self.away_results[away].append(1 - hw)

        self.sp_wins[home_sp].append(hw)
        self.sp_wins[away_sp].append(1 - hw)
        self.sp_runs[home_sp].append(aws)
        self.sp_runs[away_sp].append(hs)
        self.sp_starts[home_sp] += 1
        self.sp_starts[away_sp] += 1

        # Market bias tracking
        self.vs_market[home].append(hw - home_fair)
        self.vs_market[away].append((1 - hw) - (1 - home_fair))

        # Elo
        elo_exp = 1.0 / (1.0 + 10 ** (-(self.elo[home] - self.elo[away]) / 400.0))
        mov = 1.0 + 0.06 * min(abs(margin), 10)
        delta = 6.0 * mov * (hw - elo_exp)
        self.elo[home] += delta
        self.elo[away] -= delta


def run_clv_strategy():  # noqa: C901
    print()
    print("=" * 70)
    print("💎 CLV 反向策略 — 找出市場定價偏差")
    print("   不是「預測誰贏」，而是「找出市場錯在哪」")
    print("=" * 70)
    print()

    df = load_data()
    print(f"✅ 載入 {len(df)} 場 MLB 2025 + 真實盤口")
    print()

    import lightgbm as lgb

    tracker = Tracker()
    warm_up = 250

    all_features = []
    all_labels = []
    feature_names = None

    # Strategy configs to test
    strategies = [
        {"name": "S1: 嚴格 (edge≥5%, conf≥58%)", "edge": 0.05, "conf": 0.58, "kelly": 0.10, "max_stake": 0.03},
        {"name": "S2: 中等 (edge≥4%, conf≥56%)", "edge": 0.04, "conf": 0.56, "kelly": 0.12, "max_stake": 0.035},
        {"name": "S3: 寬鬆 (edge≥3%, conf≥54%)", "edge": 0.03, "conf": 0.54, "kelly": 0.15, "max_stake": 0.04},
        {"name": "S4: 極嚴格 (edge≥7%, conf≥62%)", "edge": 0.07, "conf": 0.62, "kelly": 0.08, "max_stake": 0.025},
    ]

    # First pass: train model
    model = None
    predictions = []

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
            if idx >= 50:
                feat = tracker.build_edge_features(home, away, home_sp, away_sp, home_fair, ou_line)
                all_features.append(feat)
                all_labels.append(hw)
            tracker.update(home, away, hs, aws, home_sp, away_sp, home_fair)
            continue

        feat = tracker.build_edge_features(home, away, home_sp, away_sp, home_fair, ou_line)
        if feature_names is None:
            feature_names = sorted(feat.keys())

        X_row = np.array([feat.get(f, 0.0) for f in feature_names]).reshape(1, -1)

        # Retrain every 40 games
        if (model is None or (idx - warm_up) % 40 == 0) and len(all_features) >= 80:
            X_train = np.array([[f.get(fn, 0.0) for fn in feature_names] for f in all_features[-800:]])
            y_train = np.array(all_labels[-800:])
            model = lgb.LGBMClassifier(
                n_estimators=200, max_depth=3, learning_rate=0.03,
                subsample=0.85, colsample_bytree=0.75, min_child_weight=10,
                reg_alpha=0.5, reg_lambda=2.0, random_state=42,
                num_leaves=8, verbose=-1,
            )
            model.fit(X_train, y_train)

        if model is not None:
            prob_home = float(model.predict_proba(X_row)[0, 1])
        else:
            prob_home = home_fair

        prob_home = max(0.05, min(0.95, prob_home))

        predictions.append({
            "idx": idx, "home": home, "away": away,
            "prob": prob_home, "actual": hw,
            "home_fair": home_fair, "home_dec": home_dec, "away_dec": away_dec,
        })

        all_features.append(feat)
        all_labels.append(hw)
        tracker.update(home, away, hs, aws, home_sp, away_sp, home_fair)

    # ─── Test each betting strategy ──────────────────────
    print(f"  預測場數: {len(predictions)}")
    correct = sum(1 for p in predictions if (p['prob'] > 0.5) == (p['actual'] == 1))
    print(f"  整體準確率: {correct/len(predictions):.1%}")
    print()

    best_strategy = None
    best_score = -999

    for strat in strategies:
        bankroll = 100_000.0
        peak = 100_000.0
        max_dd = 0.0
        total_staked = 0.0
        total_pnl = 0.0
        bet_count = 0
        bet_wins = 0

        for p in predictions:
            edge_home = p["prob"] - p["home_fair"]
            edge_away = (1 - p["prob"]) - (1 - p["home_fair"])

            bet_side = None
            bet_prob = 0.0
            bet_odds = 1.0

            if edge_home >= strat["edge"] and p["prob"] >= strat["conf"]:
                bet_side = "home"
                bet_prob = p["prob"]
                bet_odds = p["home_dec"]
            elif edge_away >= strat["edge"] and (1 - p["prob"]) >= strat["conf"]:
                bet_side = "away"
                bet_prob = 1 - p["prob"]
                bet_odds = p["away_dec"]

            if bet_side and bet_odds > 1.0:
                b = bet_odds - 1
                k = max(0, (b * bet_prob - (1 - bet_prob)) / b) * strat["kelly"]
                stake = bankroll * min(k, strat["max_stake"])

                if stake >= 10:
                    won = (bet_side == "home" and p["actual"] == 1) or (bet_side == "away" and p["actual"] == 0)
                    pnl = stake * (bet_odds - 1) if won else -stake

                    bankroll += pnl
                    total_staked += stake
                    total_pnl += pnl
                    bet_count += 1
                    if won:
                        bet_wins += 1
                    peak = max(peak, bankroll)
                    dd = (peak - bankroll) / peak
                    max_dd = max(max_dd, dd)

        roi = total_pnl / total_staked if total_staked > 0 else 0
        bet_acc = bet_wins / bet_count if bet_count > 0 else 0

        # Score: prioritize ROI and low drawdown
        score = roi * 10 - max_dd * 2 + (bet_acc - 0.5) * 5

        marker = ""
        if score > best_score:
            best_score = score
            best_strategy = strat["name"]
            marker = " 🏆"

        print(f"  {strat['name']}{marker}")
        print(f"    投注: {bet_count}場  |  勝率: {bet_acc:.1%}  |  "
              f"ROI: {roi:+.2%}  |  淨利: ${total_pnl:+,.0f}  |  DD: {max_dd:.1%}")
        print()

    # ─── Feature importance ──────────────────────────────
    if model is not None:
        print("━" * 60)
        print("🧬 市場定價偏差最重要信號 (Top 15)")
        print("━" * 60)
        imp = dict(zip(feature_names, model.feature_importances_))
        sorted_imp = sorted(imp.items(), key=lambda x: -x[1])[:15]
        max_imp = sorted_imp[0][1] if sorted_imp else 1
        for name, v in sorted_imp:
            bar = "█" * int(v / max_imp * 30)
            print(f"  {name:30s}: {v:4d} {bar}")

    print()
    print("=" * 70)
    print(f"🏆 最佳策略: {best_strategy}")
    print("=" * 70)


if __name__ == "__main__":
    run_clv_strategy()
