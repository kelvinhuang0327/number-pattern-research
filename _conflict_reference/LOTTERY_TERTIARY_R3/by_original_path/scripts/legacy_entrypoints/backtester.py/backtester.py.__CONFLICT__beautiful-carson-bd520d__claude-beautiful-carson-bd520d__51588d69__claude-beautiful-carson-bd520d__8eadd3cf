"""
WBC Backtesting System v1.2.
Evaluates prediction performance for Money Line (ML) and Run Line (RL).

§ 核心規範 01: 嚴禁合成數據進入回測。
"""
from typing import List, Dict
from data.historical_data import HISTORICAL_WBC_2023, HISTORICAL_PREMIER12_2024, HISTORICAL_2025_SEASON
from data.wbc_historical_multiyear import (
    ALL_WBC_HISTORICAL, WBC_TEAM_META,
    HISTORICAL_WBC_2009, HISTORICAL_WBC_2013, HISTORICAL_WBC_2017, HISTORICAL_WBC_2023_FULL,
)
from data.wbc_data import fetch_latest_wbc_match
from models import ensemble


# ── Synthetic Data Guard ─────────────────────────────────
_SYNTHETIC_MARKERS = {"synthetic", "fallback", "generated", "mock_auto", "seed_auto"}


def _assert_no_synthetic(matches: List[Dict], title: str) -> None:
    """Raise if any match record is flagged as synthetic / generated."""
    for m in matches:
        source = str(m.get("data_source", "")).lower()
        if any(marker in source for marker in _SYNTHETIC_MARKERS):
            raise ValueError(
                f"[{title}] 回測數據污染: match {m.get('match_id', '?')} "
                f"標記為合成數據 (data_source={m.get('data_source')}). "
                f"合成數據嚴禁進入回測流程 (核心規範 01)."
            )
        if m.get("is_synthetic", False):
            raise ValueError(
                f"[{title}] 回測數據污染: match {m.get('match_id', '?')} "
                f"is_synthetic=True. 合成數據嚴禁進入回測流程."
            )


def run_backtest(historical_matches: List[Dict], title: str = "Backtest"):
    """
    Run the prediction engine against a set of historical matches.
    """
    # § 核心規範 01: 斷言無合成數據
    _assert_no_synthetic(historical_matches, title)

    print(f"=== {title} ===")
    print(f"Total Matches: {len(historical_matches)}\n")
    
    ml_total_profit = 0.0
    rl_total_profit = 0.0
    ml_correct = 0
    rl_correct = 0
    evaluated_matches = 0

    # Historical Context Meta-data — use expanded multi-year team database
    team_meta = WBC_TEAM_META

    # Sort matches by date to simulate chronological learning
    historical_matches = sorted(historical_matches, key=lambda x: x["date"])
    
    # Tournament Momentum tracker (Team -> cumulative run diff)
    tournament_momentum = {}

    for m in historical_matches:
        match = fetch_latest_wbc_match(live=False)
        away_code, home_code = m["away_team"], m["home_team"]
        
        # Apply Momentum Adjustment to Elo
        # (Simulating real-time strength revision during tournament)
        mom_away = tournament_momentum.get(away_code, 0) * 15.0 # 15 Elo pts per run diff
        mom_home = tournament_momentum.get(home_code, 0) * 15.0
        
        # Update template to historical context
        for side, code in [("away", away_code), ("home", home_code)]:
            t = getattr(match, side)
            meta = team_meta.get(code, {"name": code, "elo": 1400, "rpg": 4.0, "era": 4.0, "woba": 0.320})
            t.name, t.code, t.elo, t.runs_per_game, t.team_woba = meta["name"], code, meta["elo"], meta["rpg"], meta["woba"]
            # Apply dynamic momentum
            if side == "away": t.elo += mom_away
            else: t.elo += mom_home
        
        match.away_sp.era = team_meta.get(away_code, {"era": 4.0})["era"]
        match.home_sp.era = team_meta.get(home_code, {"era": 4.0})["era"]
        match.away_lineup, match.home_lineup = [], []

        if m["match_id"].startswith(("MLB", "NPB")):
            match.game_type = "PROFESSIONAL"
            match.home_piggyback = None
            match.away_piggyback = None
        else:
            match.game_type = "INTERNATIONAL"
        
        match.steam_move = m.get("steam_move", 0.0)

        # 1. Predict
        away_wp, home_wp, details = ensemble.predict(match)
        print(f"DEBUG: {away_code} ({away_wp:.2f}) vs {home_code} ({home_wp:.2f})")
        
        # 2. Extract Outcomes
        actual_away, actual_home = m['actual_away_score'], m['actual_home_score']
        ml_winner = "HOME" if actual_home > actual_away else "AWAY"
        diff = actual_home - actual_away
        
        tsl_odds = m.get("tsl_odds") or {}
        if not m.get("odds_verified", False) or not tsl_odds:
            print(f"Match: {away_code} vs {home_code} | 跳過投注評估：無已驗證歷史盤口")
            continue
        evaluated_matches += 1
        
        # --- Evaluate Money Line (ML) ---
        ml_bet_on = home_code if home_wp > away_wp else away_code
        ml_won = (ml_bet_on == home_code and ml_winner == "HOME") or (ml_bet_on == away_code and ml_winner == "AWAY")
        ml_odds = tsl_odds.get(f"ML_{ml_bet_on}", 1.0)
        ml_profit = (ml_odds - 1.0) if ml_won else -1.0
        ml_total_profit += ml_profit
        if ml_won: ml_correct += 1

        # --- Evaluate Run Line (RL) ---
        line = tsl_odds.get("line", -1.5) 
        rl_bet_home = (home_wp > away_wp)
        rl_covered_home = (actual_home + line > actual_away)
        rl_won = (rl_bet_home == rl_covered_home)
        
        rl_bet_on = home_code if rl_bet_home else away_code
        rl_odds = tsl_odds.get(f"RL_{rl_bet_on}", 1.80)
        rl_profit = (rl_odds - 1.0) if rl_won else -1.0
        rl_total_profit += rl_profit
        if rl_won: rl_correct += 1

        # --- Update Tournament Momentum for next games ---
        diff_val = actual_home - actual_away
        tournament_momentum[home_code] = tournament_momentum.get(home_code, 0) + (diff_val / 5.0) # Normalized diff
        tournament_momentum[away_code] = tournament_momentum.get(away_code, 0) + (-diff_val / 5.0)

        print(f"Match: {away_code} vs {home_code} | ML: {'✅' if ml_won else '❌'} ({ml_profit:+.2f}) | RL({line}): {'✅' if rl_won else '❌'} ({rl_profit:+.2f})")

    # Summary
    n = evaluated_matches
    print(f"\n--- {title} Summary ---")
    if n == 0:
        print("No verified historical odds available. Results-only dataset retained; betting backtest skipped.")
        print("-" * 40 + "\n")
        return
    print(f"ML: Win Rate {ml_correct/n:.1%}, Profit {ml_total_profit:.2f}, ROI {ml_total_profit/n:.2%}")
    print(f"RL: Win Rate {rl_correct/n:.1%}, Profit {rl_total_profit:.2f}, ROI {rl_total_profit/n:.2%}")
    print("-" * 40 + "\n")

if __name__ == "__main__":
    # Full multi-year WBC backtest (§ 核心規範 02: ≥50 場)
    print(f"[INFO] Total WBC historical games: {len(ALL_WBC_HISTORICAL)}")
    run_backtest(HISTORICAL_WBC_2009, title="WBC 2009 Backtest (26 games)")
    run_backtest(HISTORICAL_WBC_2013, title="WBC 2013 Backtest (16 games)")
    run_backtest(HISTORICAL_WBC_2017, title="WBC 2017 Backtest (16 games)")
    run_backtest(HISTORICAL_WBC_2023_FULL, title="WBC 2023 Backtest (20 games)")
    run_backtest(ALL_WBC_HISTORICAL, title="ALL WBC Combined (78 games)")
    run_backtest(HISTORICAL_PREMIER12_2024, title="Premier12 2024 Backtest")
    run_backtest(HISTORICAL_2025_SEASON, title="2025 Seasonal Backtest (MLB/NPB/Qualifiers)")
