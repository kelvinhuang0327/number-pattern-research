import pandas as pd
import numpy as np
import sys
import os
import json
from pathlib import Path

# Add root to path
sys.path.append(os.getcwd())

from data.wbc_data import fetch_latest_wbc_match, PitcherStats, PitchCountRule
from models import ensemble
from data.mlb_2025_preview import MLB_2025_PREVIEW_META
from data.mlb_2024_pitchers import MLB_2024_PITCHERS
import unicodedata

def normalize_name(name):
    if not isinstance(name, str): return ""
    return "".join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')

TEAM_MAP = {
    "Arizona Diamondbacks": "ARI", "Athletics": "OAK", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS", "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS", "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET", "Houston Astros": "HOU",
    "Kansas City Royals": "KCR", "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN",
    "New York Mets": "NYM", "New York Yankees": "NYY", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TBA",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSN"
}

def american_to_decimal(odds):
    try:
        val = float(odds)
        if val > 0:
            return 1 + (val / 100)
        else:
            return 1 + (100 / abs(val))
    except (ValueError, TypeError):
        return 1.0

def run_mlb_backtest(file_path, limit=None):
    meta_path = Path(file_path + ".metadata.json")
    if not meta_path.exists():
        raise RuntimeError("MLB 2025 metadata sidecar missing; backtest blocked.")

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    if not metadata.get("source_chain_verified", False):
        raise RuntimeError("MLB 2025 dataset provenance is not verified; backtest blocked.")

    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip()
    df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    
    df = df[df['Status'] == 'Final'].copy()
    if 'is_verified_real' not in df.columns:
        raise RuntimeError("MLB 2025 dataset missing is_verified_real column; backtest blocked.")
    if not df['is_verified_real'].fillna(False).astype(bool).all():
        raise RuntimeError("MLB 2025 dataset contains unverified rows; backtest blocked.")
    df['Away Score'] = pd.to_numeric(df['Away Score'], errors='coerce')
    df['Home Score'] = pd.to_numeric(df['Home Score'], errors='coerce')
    df = df.dropna(subset=['Away Score', 'Home Score'])
    
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')

    if limit:
        df = df.head(limit)
        
    print(f"Running MLB 2025 Backtest (with Value Betting & Momentum) on {len(df)} games...")
    print(f"DEBUG: Available teams in TEAM_MAP: {list(TEAM_MAP.keys())[:5]}... ({len(TEAM_MAP)} total)")
    
    ml_profit, rl_profit = 0.0, 0.0
    ml_correct, rl_correct = 0, 0
    total_ml_bets, total_rl_bets = 0, 0
    
    # Sure Bet Tracking (Gold/Bronze)
    sb_profit, sb_correct, total_sb_bets = 0.0, 0, 0
    
    total = 0
    
    tournament_momentum = {}
    mlb_rule = PitchCountRule(
        round_name="Regular Season", max_pitches=100,
        rest_after_30=0, rest_after_50=0, expected_sp_innings=6.0
    )

    for idx, row in df.iterrows():
        total += 1
        try:
            away_full, home_full = row['Away'], row['Home']
            
            if away_full not in TEAM_MAP or home_full not in TEAM_MAP:
                if total <= 10:
                    print(f"Game {total}: Skipping {away_full} vs {home_full} (Mapping Missing)")
                continue
            
            away_code, home_code = TEAM_MAP[away_full], TEAM_MAP[home_full]
            
            if total <= 10:
                print(f"Game {total}: Processing {away_code} @ {home_code}")
            
            away_code, home_code = TEAM_MAP[away_full], TEAM_MAP[home_full]
            if away_code not in MLB_2025_PREVIEW_META or home_code not in MLB_2025_PREVIEW_META:
                if total < 5:
                    print(f"  FAILED: Missing from PREVIEW_META. Away: {away_code} Home: {home_code}")
                continue

            away_meta = MLB_2025_PREVIEW_META.get(away_code)
            home_meta = MLB_2025_PREVIEW_META.get(home_code)

            mom_away = tournament_momentum.get(away_code, 0) * 10.0
            mom_home = tournament_momentum.get(home_code, 0) * 10.0

            match = fetch_latest_wbc_match(live=False)
            match.game_type, match.pitch_count_rule = "PROFESSIONAL", mlb_rule
            match.away.code, match.home.code = away_code, home_code
            match.away.elo, match.home.elo = away_meta["elo"] + mom_away, home_meta["elo"] + mom_home
            match.away.runs_per_game = away_meta["rpg"]
            match.home.runs_per_game = home_meta["rpg"]
            match.away.team_woba = away_meta["woba"]
            match.home.team_woba = home_meta["woba"]
            
            # Set Starter Info
            a_sp_name = normalize_name(row['Away Starter'])
            h_sp_name = normalize_name(row['Home Starter'])
            
            # Create a name lookup map
            PITCHER_MATCH = {normalize_name(k): v for k, v in MLB_2024_PITCHERS.items()}
            
            a_sp_stats = PITCHER_MATCH.get(a_sp_name, {"era": away_meta["era"], "whip": 1.30, "k9": 8.5})
            h_sp_stats = PITCHER_MATCH.get(h_sp_name, {"era": home_meta["era"], "whip": 1.30, "k9": 8.5})

            match.away_sp = PitcherStats(
                name=a_sp_name, team=away_code, era=a_sp_stats["era"], fip=a_sp_stats["era"], 
                whip=a_sp_stats["whip"], k_per_9=a_sp_stats["k9"], 
                bb_per_9=3.0, stuff_plus=100, ip_last_30=20, era_last_3=a_sp_stats["era"], spring_era=4.0, 
                pitch_count_last_3d=0, vs_left_ba=0.250, vs_right_ba=0.250, high_leverage_era=a_sp_stats["era"], 
                fastball_velo=93.0, role="SP"
            )
            match.home_sp = PitcherStats(
                name=h_sp_name, team=home_code, era=h_sp_stats["era"], fip=h_sp_stats["era"], 
                whip=h_sp_stats["whip"], k_per_9=h_sp_stats["k9"], 
                bb_per_9=3.0, stuff_plus=100, ip_last_30=20, era_last_3=h_sp_stats["era"], spring_era=4.0, 
                pitch_count_last_3d=0, vs_left_ba=0.250, vs_right_ba=0.250, high_leverage_era=h_sp_stats["era"], 
                fastball_velo=93.0, role="SP"
            )
            match.away_lineup, match.home_lineup = [], []
            match.home_piggyback, match.away_piggyback = None, None

            # 1. Predict
            away_wp, home_wp, details = ensemble.predict(match)
            
            if total < 10:
                print(f"Game {total}: {away_code} @ {home_code} | Pred: {away_wp:.2f}-{home_wp:.2f} | Odds: {odds_away:.2f}-{odds_home:.2f}")

            # 2. Results
            a_score, h_score = row['Away Score'], row['Home Score']
            ml_winner = "HOME" if h_score > a_score else "AWAY"
            
            # 3. ML Value Betting
            odds_away = american_to_decimal(row['Away ML'])
            odds_home = american_to_decimal(row['Home ML'])
            edge_away = away_wp - (1/odds_away)
            edge_home = home_wp - (1/odds_home)
            
            if total <= 10 or edge_away > 0.001 or edge_home > 0.001:
                print(f"Game {total}: {away_code} @ {home_code} | Pred: {away_wp:.3f} | Odds: {odds_away:.2f} | Edge: {edge_away:.4f}")

            if edge_away > 0.001:
                won = (ml_winner == "AWAY")
                ml_profit += (odds_away - 1) if won else -1
                if won: ml_correct += 1
                total_ml_bets += 1
            elif edge_home > 0.001:
                won = (ml_winner == "HOME")
                ml_profit += (odds_home - 1) if won else -1
                if won: ml_correct += 1
                total_ml_bets += 1
                
            # 3.5 Sure Bet Selection
            confidence = details.get("confidence_score", 0.0)
            if confidence >= 0.66:
                if edge_away >= 0.05:
                    won = (ml_winner == "AWAY")
                    sb_profit += (odds_away - 1) if won else -1
                    if won: sb_correct += 1
                    total_sb_bets += 1
                elif edge_home >= 0.05:
                    won = (ml_winner == "HOME")
                    sb_profit += (odds_home - 1) if won else -1
                    if won: sb_correct += 1
                    total_sb_bets += 1
                
            # 4. RL Value Betting
            spread = float(str(row['Home RL Spread']).replace('+', ''))
            rl_odds_away = american_to_decimal(row['RL Away'])
            rl_odds_home = american_to_decimal(row['RL Home'])
            
            mc = details.get("sub_models", {}).get("monte_carlo", {})
            away_dist, home_dist = mc.get("away_run_distribution", {}), mc.get("home_run_distribution", {})
            prob_home_cover = sum(ap*hp for ar, ap in away_dist.items() for hr, hp in home_dist.items() if float(hr)+spread > float(ar))
            
            edge_rl_home = prob_home_cover - (1/rl_odds_home)
            edge_rl_away = (1.0 - prob_home_cover) - (1/rl_odds_away)
            
            if edge_rl_home > 0.001:
                won = (h_score + spread > a_score)
                rl_profit += (rl_odds_home - 1) if won else -1
                if won: rl_correct += 1
                total_rl_bets += 1
            elif edge_rl_away > 0.04:
                won = (a_score > h_score + spread)
                rl_profit += (rl_odds_away - 1) if won else -1
                if won: rl_correct += 1
                total_rl_bets += 1
            
            # Update Momentum
            diff = h_score - a_score
            tournament_momentum[home_code] = tournament_momentum.get(home_code, 0) + (diff / 5.0)
            tournament_momentum[away_code] = tournament_momentum.get(away_code, 0) + (-diff / 5.0)

            if total % 100 == 0:
                print(f"Processed {total} games...")
                
        except Exception as e:
            if total <= 10:
                print(f"Game {total} ERROR: {e}")
            continue

    if total_ml_bets == 0 and total_rl_bets == 0:
        print("\n=== MLB 2025 Backtest: No bets placed ===")
        return

    print(f"\n=== MLB 2025 Value Betting Summary ({total} games processed) ===")
    if total_ml_bets > 0:
        print(f"ML: Bets {total_ml_bets}, Win Rate {ml_correct/total_ml_bets:.1%}, Profit {ml_profit:.2f}, ROI {ml_profit/total_ml_bets:.2%}")
    if total_sb_bets > 0:
        print(f"SURE BETS: Bets {total_sb_bets}, Win Rate {sb_correct/total_sb_bets:.1%}, Profit {sb_profit:.2f}, ROI {sb_profit/total_sb_bets:.2%}")
    if total_rl_bets > 0:
        print(f"RL: Bets {total_rl_bets}, Win Rate {rl_correct/total_rl_bets:.1%}, Profit {rl_profit:.2f}, ROI {rl_profit/total_rl_bets:.2%}")

if __name__ == "__main__":
    file_path = '/Users/kelvin/Kelvin-WorkSpace/Betting-pool/data/mlb_2025/mlb_odds_2025_real.csv'
    run_mlb_backtest(file_path)
