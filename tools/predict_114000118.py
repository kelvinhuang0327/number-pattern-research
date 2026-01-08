#!/usr/bin/env python3
import sys
import os
import json
import numpy as np
from collections import defaultdict, Counter

# Add lottery-api to path
base_path = os.getcwd()
sys.path.insert(0, os.path.join(base_path, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine
from models.advanced_strategies import AdvancedStrategies

class BigLottoCVAA:
    def __init__(self, rules):
        self.rules = rules
        self.pick_count = rules.get('pickCount', 6)
        self.min_num = rules.get('minNumber', 1)
        self.max_num = rules.get('maxNumber', 49)

    def predict(self, history):
        if len(history) < 20: return None
        centroids = [np.mean(d['numbers']) for d in history]
        velocities = np.diff(centroids)
        v_next = np.mean(velocities[-5:])
        c_predicted = centroids[-1] + v_next
        c_predicted = max(self.min_num + 10, min(self.max_num - 10, c_predicted))
        
        all_nums = [n for d in history for n in d['numbers']]
        counts = Counter(all_nums)
        candidates = sorted(range(self.min_num, self.max_num + 1), 
                            key=lambda x: abs(x - c_predicted) * 1.5 - counts.get(x, 0) * 0.1)
        return {"numbers": sorted(candidates[:self.pick_count]), "confidence": 0.60}

def predict_114000118():
    db_path = 'lottery-api/data/lottery_v2.db'
    db = DatabaseManager(db_path=db_path)
    rules = get_lottery_rules('BIG_LOTTO')
    
    # 1. Get All History
    all_draws = db.get_all_draws('BIG_LOTTO')
    all_draws_chrono = list(reversed(all_draws))
    
    print(f"📊 Loaded {len(all_draws_chrono)} draws. Latest: {all_draws_chrono[-1]['draw']} ({all_draws_chrono[-1]['date']})")
    print(f"Latest Numbers: {all_draws_chrono[-1]['numbers']}")
    
    # 2. Setup Strategies
    engine = prediction_engine
    advanced = AdvancedStrategies(engine)
    cvaa = BigLottoCVAA(rules)
    
    strategies = {
        "frequency": engine.frequency_predict,
        "trend": engine.trend_predict,
        "bayesian": engine.bayesian_predict,
        "markov": engine.markov_predict,
        "monte_carlo": engine.monte_carlo_predict,
        "deviation": engine.deviation_predict,
        "statistical": engine.statistical_predict,
        "hot_cold": engine.hot_cold_mix_predict,
        "zone_balance": engine.zone_balance_predict,
        "entropy_analysis": advanced.entropy_analysis_predict,
        "clustering": advanced.clustering_predict,
        "dynamic_ensemble": advanced.dynamic_ensemble_predict,
        "temporal_enhanced": advanced.temporal_enhanced_predict,
        "feature_engineering": advanced.feature_engineering_predict,
        "cvaa_physics": lambda h, r: cvaa.predict(h)
    }
    
    # 3. Evaluate Recent Performance (Last 10 Draws)
    # To evaluate fairly, for each of the last 10 draws, we use data before it to predict it.
    recent_eval_window = 10
    strategy_scores = defaultdict(int)
    
    print(f"📡 Evaluating strategy performance over the last {recent_eval_window} draws...")
    
    for i in range(len(all_draws_chrono) - recent_eval_window, len(all_draws_chrono)):
        target = all_draws_chrono[i]
        training_data = all_draws_chrono[:i]
        # Use last 300 for training consistency with tournament
        training_slice = training_data[-300:]
        
        for name, func in strategies.items():
            try:
                p = func(training_slice, rules)
                if p and 'numbers' in p:
                    hits = len(set(p['numbers']) & set(target['numbers']))
                    if hits >= 3:
                        strategy_scores[name] += 1
            except:
                pass
                
    # 4. Select Best Strategy (Meta-Selector)
    ranked_strategies = sorted(strategies.keys(), key=lambda n: strategy_scores[n], reverse=True)
    best_strategy_name = ranked_strategies[0]
    second_best_strategy_name = ranked_strategies[1]
    
    print("\n🏆 Top Strategies (Recent 10 Draws Win Count):")
    for name in ranked_strategies[:5]:
        print(f" - {name:<20}: {strategy_scores[name]} wins")
        
    # 5. Generate Predictions for 114000118
    print(f"\n🔮 Generating Prediction for Draw 114000118 using '{best_strategy_name}'...")
    
    final_training_data = all_draws_chrono[-300:]
    
    # Best Single Bet
    try:
        pred_best = strategies[best_strategy_name](final_training_data, rules)
        print("\n" + "="*50)
        print(f"🎯 推薦單注 (Meta_BestRecent):")
        print(f"   號碼: {', '.join([f'{n:02d}' for n in pred_best['numbers']])}")
        print(f"   策略: {best_strategy_name}")
        print("="*50)
        
        # Dual Bet Backup (Second Best)
        pred_second = strategies[second_best_strategy_name](final_training_data, rules)
        print(f"\n🥈 備選第二注 (Meta_Top2_DualBet):")
        print(f"   號碼: {', '.join([f'{n:02d}' for n in pred_second['numbers']])}")
        print(f"   策略: {second_best_strategy_name}")
        print("="*50)
        
    except Exception as e:
        print(f"❌ Error generating prediction: {e}")

if __name__ == "__main__":
    predict_114000118()
