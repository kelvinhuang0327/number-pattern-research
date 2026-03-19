#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from ai_lab.adapter import AIAdapter
from ai_lab.scripts.orthogonal_portfolio import OrthogonalPortfolio

def predict_next():
    # 1. Setup
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    last_draw = all_draws[-1]
    print(f"DEBUG: Draw Keys: {last_draw.keys()}")
    draw_id_key = 'draw_period' if 'draw_period' in last_draw else 'draw_id'
    if draw_id_key not in last_draw:
        # Fallback for Big Lotto which might use just 'id' or different schema
        print(f"WARN: Could not find draw_id. Using placeholders.")
        current_id = 115000004 
    else:
        current_id = last_draw[draw_id_key]

    print(f"📊 Latest Data: Draw {current_id} ({last_draw.get('date', 'Unknown')})")
    print(f"   Numbers: {last_draw['numbers']}")
    print("-" * 50)
    
    # 2. Initialize Engine
    print("🚀 Initializing Orthogonal Expert Portfolio (Phase 23)...")
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    predictor = OrthogonalPortfolio(engine, ai_adapter)
    
    # 3. Generate Prediction
    target_draw_id = int(str(current_id)) + 1
    print(f"🔮 Generating Prediction for Draw {target_draw_id}...")
    
    res = predictor.predict_orthogonal_3bet(all_draws, rules)
    bets = res['bets']
    details = res['details']
    
    print("\n" + "="*50)
    print(f"🎯 ORTHOGONAL 3-BET PREDICTION (Draw {target_draw_id})")
    print("="*50)
    
    labels = ['Structural AI (Momentum)', 'HPSB DMS (Reversion)', 'Hybrid Balance (Coverage)']
    
    for i, bet in enumerate(bets):
        formatted_bet = ", ".join(f"{n:02d}" for n in sorted(bet))
        print(f"Bet {i+1} [{labels[i]}]:")
        print(f"👉  {formatted_bet}")
        print(f"    (Source: {details.get(f'bet{i+1}', 'N/A')})")
        print("-" * 30)
        
    print("\n🍀 Good Luck!")
    print("="*50)

if __name__ == "__main__":
    predict_next()
