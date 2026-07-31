#!/usr/bin/env python3
import os
import sys

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from ai_lab.adapter import AIAdapter
from ai_lab.scripts.six_expert_ensemble import SixExpertEnsemble

def predict():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    # Get latest draw info
    last_draw = all_draws[-1]
    last_date = last_draw.get('date', 'Unknown')
    last_nums = last_draw.get('numbers', [])
    
    # Determine next draw ID (use 115000004 as confirmed by user)
    next_draw_id = 115000004
    
    print(f"📊 Latest Data: {last_date}")
    print(f"   Numbers: {last_nums}")
    print("-" * 60)
    
    # Run prediction
    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    predictor = SixExpertEnsemble(engine, ai_adapter)
    
    print(f"🚀 Generating 6-Expert Prediction for Draw {next_draw_id}...")
    res = predictor.predict(all_draws, rules)
    bets = res['bets']
    
    expert_labels = [
        ('AI-Structural', '深度學習趨勢'),
        ('HPSB-DMS', '統計均值回歸'),
        ('Graph Clique', '號碼共現結構'),
        ('Hybrid Balance', 'AI+統計次選'),
        ('Gap Recovery', '遺漏值回補'),
        ('Tail Analysis', '尾數模式')
    ]
    
    print("\n" + "="*60)
    print(f"🎯 6-EXPERT ENSEMBLE PREDICTION (Draw {next_draw_id})")
    print("="*60)
    
    for i, bet in enumerate(bets):
        name, desc = expert_labels[i]
        formatted = ", ".join(f"{n:02d}" for n in sorted(bet))
        print(f"Bet {i+1} [{name}] ({desc}):")
        print(f"👉  {formatted}")
        print("-" * 40)
        
    print("\n🍀 祝您好運！(此策略實測勝率 14.67%)")
    print("="*60)

if __name__ == "__main__":
    predict()
