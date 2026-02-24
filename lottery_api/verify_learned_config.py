#!/usr/bin/env python3
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

# Disable logs
logging.getLogger().setLevel(logging.ERROR)

def calculate_matches(predicted: List[int], actual: List[int]) -> int:
    return len(set(predicted) & set(actual))

def main():
    lottery_type = 'BIG_LOTTO'
    history, rules = load_backend_history(lottery_type)
    all_draws = db_manager.get_all_draws(lottery_type)
    all_draws.sort(key=lambda x: x['date'])

    # Load learned config
    history_file = "data/advanced_optimization_history.json"
    if not os.path.exists(history_file):
        print("❌ 找不到優化歷史")
        return

    with open(history_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        config = data['history'][-1]['config']
        claimed_fitness = data['history'][-1]['best_fitness']

    print("=" * 70)
    print(f"📊 驗證自動學習出的「獲勝公式」 (訓練集宣稱機率: {claimed_fitness:.2%})")
    print("=" * 70)

    engine = AdvancedAutoLearningEngine()
    test_draws = [d for d in all_draws if '2025' in str(d.get('date', ''))][-30:]
    
    hits_data = []
    wins = 0
    total_matches = 0

    print(f"{'Draw':<12} | {'Actual':<25} | {'Predicted':<25} | {'Match'}")
    print("-" * 75)

    for target_draw in test_draws:
        # Get history before this draw
        draw_id = target_draw['draw']
        idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == draw_id:
                idx = i; break
        
        if idx == -1: continue
        
        hist = all_draws[:idx]
        predicted = engine._predict_with_config(
            config, hist, rules['pickCount'], rules['minNumber'], rules['maxNumber']
        )
        actual = target_draw['numbers']
        
        m = calculate_matches(predicted, actual)
        total_matches += m
        if m >= 3: wins += 1
        
        act_str = ",".join(map(str, sorted(actual)))
        pre_str = ",".join(map(str, sorted(predicted)))
        print(f"{draw_id:<12} | {act_str:<25} | {pre_str:<25} | {m}")

    print("-" * 75)
    n = len(test_draws)
    real_rate = wins / n if n > 0 else 0
    avg_m = total_matches / n if n > 0 else 0

    print(f"驗證期數: {n} 期")
    print(f"平均命中: {avg_m:.2f} 號碼/期")
    print(f"實際成功率 (Match 3+): {real_rate:.2%}")
    print("=" * 70)

if __name__ == '__main__':
    main()
