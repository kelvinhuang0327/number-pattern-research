#!/usr/bin/env python3
"""
Power Lotto Grand Slam Strategy Generator (Production)
======================================================
Implements the "Grand Slam Dual-Path Strategy" validated on Draw 115000007.

Strategy Overview:
------------------
1. Path Alpha (Hot): Uses True Frequency (Window 50) to select Top 12 numbers.
   - Foundation Bet (Bet 1): Alpha Rank 1-6 (Most Hot)
   - Secondary Bet (Bet 2): Alpha Rank 7-12 (Secondary Hot - often missed/undervalued)
2. Path Beta (Cold): Uses Deviation V2 model to select Top 6 numbers.
   - Rebound Bet (Bet 3): Beta Rank 1-6 (Cold/Gap Rebound)
3. Zone 2 (Special): Uses True Frequency (Window 50) Top 4 + Markov Top 1.

Usage:
------
python3 tools/predict_power_grand_slam.py
"""
import sys
import os
import json
import logging
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine, predict_pool_numbers

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_next_draw_info(latest_draw_id: str) -> str:
    # Simple logic to increment draw ID
    try:
        prefix = latest_draw_id[:7] # '1150000'
        seq = int(latest_draw_id[7:]) # '07' -> 7
        return f"{prefix}{seq+1:02d}"
    except:
        return "Unknown"

def main():
    print("=" * 60)
    print("⚾️ Power Lotto Grand Slam Prediction System ⚾️")
    print("=" * 60)
    
    # 1. Load History
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not all_history:
        print("❌ No history found.")
        return
        
    latest_draw = all_history[0]
    next_draw_id = get_next_draw_info(latest_draw['draw'])
    
    print(f"📚 Data Source: {len(all_history)} periods")
    print(f"🔄 Latest Draw: {latest_draw['draw']} ({latest_draw['date']})")
    print(f"🎯 Target Draw: {next_draw_id}")
    print("-" * 60)
    
    # 2. Initialize Engine
    engine = UnifiedPredictionEngine()
    rules = get_lottery_rules('POWER_LOTTO')
    
    # 3. Path Alpha: True Frequency (Hot)
    print("\n[Path Alpha] Analyzing Hot Numbers (True Frequency)...")
    # Request Top 15 to be safe
    rules['pickCount'] = 15
    rules['frequency_window'] = 50
    
    pred_alpha = engine.true_frequency_predict(all_history, rules)
    alpha_nums = pred_alpha['ranked_list'] # Full ordered list
    
    # Segment Alpha
    bet1_foundation = sorted(alpha_nums[:6])
    bet2_secondary = sorted(alpha_nums[6:12])
    
    print(f"🔥 Alpha Analysis Complete. Top 12 Candidate Pool: {sorted(alpha_nums[:12])}")
    
    # 4. Path Beta: Deviation (Cold)
    print("\n[Path Beta] Analyzing Cold Numbers (Deviation V2)...")
    rules['pickCount'] = 6
    pred_beta = engine.deviation_predict(all_history, rules)
    bet3_rebound = sorted(pred_beta['numbers'])
    
    # 5. Zone 2 (Special) Strategy
    print("\n[Zone 2] Analyzing Special Numbers...")
    # New Strategy: Smart Markov (Hybrid Repeater/Transition)
    
    # Needs History New -> Old? Engine usually handles it, but let's check.
    # The unified predictor expects a list of dicts.
    # history used here is all_history (New -> Old)
    
    pred_special = engine.smart_markov_predict(all_history, {'pickCount': 1})
    best_special = pred_special['numbers'][0]
    
    print(f"🔮 Special Candidates: [{best_special}]")
    print(f"   - Primary Recommendation: {best_special:02d} ({pred_special['method']})")
    print(f"   - Confidence: {pred_special['confidence']*100:.1f}%")

    
    # 6. Generate Bets
    print("\n" + "=" * 60)
    print(f"🎰 Suggested Bets for Draw {next_draw_id}")
    print("=" * 60)
    
    print("\n🎫 Bet 1: Foundation (Alpha Hot Top 6)")
    print(f"   Numbers: {bet1_foundation}")
    print(f"   Special: {best_special:02d}")
    print("   Goal: Capture reliable hot numbers.")
    
    print("\n🎫 Bet 2: Secondary Hot (Alpha Hot Rank 7-12)")
    print(f"   Numbers: {bet2_secondary}")
    print(f"   Special: {best_special:02d}")
    print("   Goal: Capture 'Secondary Hot' numbers often missed by models (The 'Grand Slam' Key).")
    
    print("\n🎫 Bet 3: Rebound (Beta Cold Top 6)")
    print(f"   Numbers: {bet3_rebound}")
    print(f"   Special: {best_special:02d}")
    print("   Goal: Capture cold numbers rebounding (e.g., Deviation).")
    
    # JSON Output for other tools
    output = {
        'draw': next_draw_id,
        'bets': [
            {'type': 'Foundation (Hot)', 'numbers': bet1_foundation, 'special': best_special},
            {'type': 'Secondary (Hot)', 'numbers': bet2_secondary, 'special': best_special},
            {'type': 'Rebound (Cold)', 'numbers': bet3_rebound, 'special': best_special}
        ],
        'special_candidates': [best_special]
    }
    
    json_path = os.path.join(project_root, 'predictions', f'power_grand_slam_{next_draw_id}.json')
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n📁 Prediction saved to {json_path}")

if __name__ == '__main__':
    main()
