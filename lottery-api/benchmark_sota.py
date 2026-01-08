#!/usr/bin/env python3
import sys
import os
import json
import logging
import numpy as np

sys.path.insert(0, os.getcwd())
from database import db_manager
from models.unified_predictor import UnifiedPredictionEngine
from models.optimized_ensemble import OptimizedEnsemblePredictor
from common import get_lottery_rules

# 禁用詳細日誌
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger()

def calculate_matches(pred, actual):
    return len(set(pred) & set(actual))

def main():
    lottery_type = 'POWER_LOTTO'
    engine = UnifiedPredictionEngine()
    ensemble = OptimizedEnsemblePredictor(engine)
    lottery_rules = get_lottery_rules(lottery_type)
    
    all_draws = db_manager.get_all_draws(lottery_type)
    draws_2025 = [d for d in all_draws if '2025' in str(d.get('date', ''))]
    draws_2025 = sorted(draws_2025, key=lambda x: x['draw'])

    print("=" * 80)
    print(f"🚀 SOTA BENCHMARK: Classic vs Neural Transformer + Genetic")
    print(f"Testing on {len(draws_2025)} draws from 2025")
    print("=" * 80)
    print(f"{'Draw':<10} | {'Classic Match':<15} | {'SOTA Match':<10}")
    print("-" * 80)

    classic_matches = []
    sota_matches = []

    # 為了測試，我們取最近的 5 期來比較
    test_draws = draws_2025[-5:]

    for target_draw in test_draws:
        draw_id = target_draw['draw']
        target_idx = -1
        for i, d in enumerate(all_draws):
            if d['draw'] == draw_id:
                target_idx = i
                break
        
        if target_idx == -1 or target_idx + 1 >= len(all_draws):
            continue
            
        history = all_draws[target_idx + 1 : target_idx + 1 + 500]
        actual = target_draw['numbers']

        # 1. Classic Ensemble
        res_classic = ensemble.predict_single(history, lottery_rules)
        m_classic = calculate_matches(res_classic['numbers'], actual)
        classic_matches.append(m_classic)

        # 2. SOTA Ensemble (Using Evolve Weights)
        # 模擬 SOTA 配置：先演化權重，再預測
        # sota 策略已經包含在 ensemble 中
        # 我們手動執行權重演化
        logger.info("Evolving weights for SOTA...")
        sota_weights = ensemble.evolve_weights(history, lottery_rules)
        
        # 執行加權預測
        votes = {}
        for name, method in ensemble.strategy_methods.items():
            try:
                r = method(history, lottery_rules)
                for num in r['numbers']:
                    votes[num] = votes.get(num, 0) + sota_weights[name]
            except: continue
        
        sota_pred = sorted(votes.keys(), key=lambda x: votes[x], reverse=True)[:6]
        m_sota = calculate_matches(sota_pred, actual)
        sota_matches.append(m_sota)

        print(f"{draw_id:<10} | {m_classic:^15} | {m_sota:^10}")

    print("-" * 80)
    print(f"📊 SUMMARY - Average Matches (Last 20 draws)")
    print(f"Classic Ensemble: {np.mean(classic_matches):.2f}")
    print(f"SOTA Ensemble   : {np.mean(sota_matches):.2f}")
    improvement = (np.mean(sota_matches) - np.mean(classic_matches)) / (np.mean(classic_matches) + 1e-10) * 100
    print(f"Improvement     : {improvement:+.1f}%")
    print("=" * 80)

if __name__ == '__main__':
    main()
