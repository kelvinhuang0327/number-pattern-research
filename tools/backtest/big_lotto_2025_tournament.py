#!/usr/bin/env python3
import sys
import os
import json
import numpy as np
from collections import defaultdict, Counter
from datetime import datetime

# Add lottery-api to path
base_path = os.getcwd()
sys.path.insert(0, os.path.join(base_path, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import prediction_engine, UnifiedPredictionEngine
from models.advanced_strategies import AdvancedStrategies

class BigLottoCVAA:
    """Physics-based Centroid Velocity for Big Lotto (49 numbers)"""
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
        
        # Simple weighted selection near centroid
        all_nums = [n for d in history for n in d['numbers']]
        counts = Counter(all_nums)
        candidates = sorted(range(self.min_num, self.max_num + 1), 
                            key=lambda x: abs(x - c_predicted) * 1.5 - counts.get(x, 0) * 0.1)
        return {"numbers": sorted(candidates[:self.pick_count]), "confidence": 0.60}

class TournamentRunner:
    def __init__(self):
        self.db_path = 'lottery-api/data/lottery_v2.db'
        self.db = DatabaseManager(db_path=self.db_path)
        self.rules = get_lottery_rules('BIG_LOTTO')
        self.engine = prediction_engine
        self.advanced = AdvancedStrategies(self.engine)
        self.cvaa = BigLottoCVAA(self.rules)
        
        self.strategies = {
            "frequency": self.engine.frequency_predict,
            "trend": self.engine.trend_predict,
            "bayesian": self.engine.bayesian_predict,
            "markov": self.engine.markov_predict,
            "monte_carlo": self.engine.monte_carlo_predict,
            "deviation": self.engine.deviation_predict,
            "statistical": self.engine.statistical_predict,
            "hot_cold": self.engine.hot_cold_mix_predict,
            "zone_balance": self.engine.zone_balance_predict,
            "entropy_analysis": self.advanced.entropy_analysis_predict,
            "clustering": self.advanced.clustering_predict,
            "dynamic_ensemble": self.advanced.dynamic_ensemble_predict,
            "temporal_enhanced": self.advanced.temporal_enhanced_predict,
            "feature_engineering": self.advanced.feature_engineering_predict,
            "cvaa_physics": lambda h, r: self.cvaa.predict(h)
        }
        
        self.history_scores = defaultdict(lambda: []) # Track success (0 or 1) per strategy
        self.stats = {name: {"matches": 0, "wins": 0, "total": 0} for name in self.strategies}
        self.stats["Meta_BestRecent"] = {"matches": 0, "wins": 0, "total": 0}
        self.stats["Meta_Top2_DualBet"] = {"matches": 0, "wins": 0, "total": 0}

    def run_rolling_2025(self):
        all_draws = self.db.get_all_draws('BIG_LOTTO')
        # Reverse to chronological order for the loop
        all_draws_chrono = list(reversed(all_draws))
        
        # Find 2025 start
        start_idx = 0
        for i, d in enumerate(all_draws_chrono):
            if '2025' in d['date'] or d['draw'].startswith('114'):
                start_idx = i
                break
        
        test_draws = all_draws_chrono[start_idx:]
        print(f"🏟 Starting Tournament for {len(test_draws)} draws in 2025...")
        
        for i, target in enumerate(test_draws):
            current_history = all_draws_chrono[:start_idx + i]
            # Use last 300 for training
            training_data = current_history[-300:]
            
            if len(training_data) < 50: continue
            
            # Predict with all
            preds = {}
            for name, func in self.strategies.items():
                try:
                    p = func(training_data, self.rules)
                    if not p or 'numbers' not in p: continue
                    
                    preds[name] = p
                except Exception as e:
                    pass
            
            # 🤖 Meta Strategy: Rank strategies by RECENT PAST draws (Before appending current result)
            ranked_strategies = sorted(self.strategies.keys(), 
                                      key=lambda n: sum(self.history_scores[n][-10:]), 
                                      reverse=True)
            
            # 1. Best Recent (Single Bet)
            best_s = ranked_strategies[0]
            if best_s in preds:
                p1 = preds[best_s]
                hits1 = len(set(p1['numbers']) & set(target['numbers']))
                is_win_meta = 1 if hits1 >= 3 else 0
                self.stats["Meta_BestRecent"]["matches"] += hits1
                self.stats["Meta_BestRecent"]["wins"] += is_win_meta
                self.stats["Meta_BestRecent"]["total"] += 1
                
                if is_win_meta:
                    print(f"🎯 WIN! Draw {target['draw']} ({target['date']}) | Method: {best_s}")
                    print(f"   Predicted: {sorted(p1['numbers'])}")
                    print(f"   Actual:    {sorted(target['numbers'])}")
                    print(f"   Matches:   {hits1}")

            # 2. Update individual strategy history (After choice is made for Meta)
            for name, p in preds.items():
                hits = len(set(p['numbers']) & set(target['numbers']))
                is_win = 1 if hits >= 3 else 0
                self.stats[name]["matches"] += hits
                self.stats[name]["wins"] += is_win
                self.stats[name]["total"] += 1
                self.history_scores[name].append(is_win)

            # 2. Top 2 Combined (Dual Bet)
            top2 = ranked_strategies[:2]
            combined_win = 0
            combined_matches = 0
            valid_bets = 0
            for name in top2:
                if name in preds:
                    p = preds[name]
                    hits = len(set(p['numbers']) & set(target['numbers']))
                    if hits >= 3: combined_win = 1
                    combined_matches += hits
                    valid_bets += 1
            
            if valid_bets > 0:
                self.stats["Meta_Top2_DualBet"]["matches"] += (combined_matches / valid_bets) # Avg quality
                self.stats["Meta_Top2_DualBet"]["wins"] += combined_win
                self.stats["Meta_Top2_DualBet"]["total"] += 1

            if (i+1) % 5 == 0:
                print(f"  Progress: {i+1}/{len(test_draws)} draws evaluated.")

        self.report()

    def report(self):
        print("\n" + "="*80)
        print("🏆 BIG LOTTO 2025 STRATEGY TOURNAMENT RESULTS")
        print("="*80)
        
        sorted_stats = sorted(self.stats.items(), key=lambda x: (x[1]['wins']/x[1]['total'] if x[1]['total']>0 else 0), reverse=True)
        
        print(f"{'Strategy Name':<25} | {'Avg Matches':<12} | {'Win Rate (3+Match)':<18}")
        print("-" * 65)
        for name, s in sorted_stats:
            if s['total'] == 0: continue
            wr = s['wins'] / s['total']
            avg = s['matches'] / s['total']
            marker = "⭐" if "Meta" in name or name == sorted_stats[0][0] else "  "
            print(f"{marker} {name:<22} | {avg:<12.3f} | {wr:<18.2%}")
        
if __name__ == "__main__":
    runner = TournamentRunner()
    runner.run_rolling_2025()
