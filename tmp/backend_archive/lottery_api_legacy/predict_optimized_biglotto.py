#!/usr/bin/env python3
import asyncio
import sys
import os
import json
import logging
from typing import List, Dict

# Setup path
sys.path.insert(0, os.getcwd())

from database import db_manager
from models.advanced_auto_learning import AdvancedAutoLearningEngine
from common import load_backend_history, get_lottery_rules

# Configure logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

def generate_optimized_prediction():
    lottery_type = 'BIG_LOTTO'
    history, rules = load_backend_history(lottery_type)
    
    # Load optimal config
    history_file = "data/advanced_optimization_history.json"
    if not os.path.exists(history_file):
        print("❌ 找不到優化歷史文件，請先執行 self_optimization_demo.py")
        return

    with open(history_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        history_records = data.get('history', [])
        if not history_records:
            print("❌ 優化歷史為空")
            return
        
        # Get latest best config
        best_record = history_records[-1]
        config = best_record['config']
        fitness = best_record['best_fitness']
        
    print("=" * 60)
    print(f"🚀 使用「自動學習獲勝公式」生成大樂透預測")
    print(f"   (參考成功率: {fitness:.2%})")
    print("=" * 60)

    engine = AdvancedAutoLearningEngine()
    
    # Generate 8 bets using the learned config with slight mutations for diversity
    all_bets = []
    for i in range(8):
        # Slightly mutate config for each bet to get diversity
        mutated_config = config.copy()
        for k in mutated_config:
            if '_weight' in k:
                mutated_config[k] *= (0.9 + 0.2 * (i/8.0)) # Vary weight slightly
        
        # Predict
        predicted = engine._predict_with_config(
            mutated_config, history, 
            rules['pickCount'], rules['minNumber'], rules['maxNumber']
        )
        all_bets.append(sorted(predicted))

    # Remove duplicates
    unique_bets = []
    seen = set()
    for b in all_bets:
        t = tuple(b)
        if t not in seen:
            unique_bets.append(b)
            seen.add(t)

    # Print results
    for idx, bet in enumerate(unique_bets[:8], 1):
        bfmt = ", ".join(f"{n:02d}" for n in bet)
        print(f"Bet {idx}: {bfmt}")
    
    print("=" * 60)
    print("💡 這些號碼是基於「尾數規律」與「信息熵」權重優化後的結果。")

if __name__ == '__main__':
    generate_optimized_prediction()
