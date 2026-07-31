#!/usr/bin/env python3
"""
Auto-Discovery Agent for Power Lotto (威力彩自動探索代理)
專門針對威力彩 (POWER_LOTTO) 設計的遺傳算法搜尋器。

目標：
1. 自動找出最佳的「雙軌制」參數 (Dual-Path Parameters)。
2. 整合 Negative Selector (殺號) 參數。
3. 針對第二區進行全排列搜尋。
"""
import sys
import os
import random
import json
import heapq
from datetime import datetime
from typing import List, Dict, Tuple
from copy import deepcopy

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

# 配置常數
POPULATION_SIZE = 30
GENERATIONS = 10
ELITE_SIZE = 5
MUTATION_RATE = 0.3

class PowerStrategyGenome:
    """威力彩策略基因組"""
    def __init__(self, params: Dict = None):
        if params:
            self.params = params
        else:
            self.params = self.random_init()
        self.fitness = 0.0
        self.metrics = {}

    def random_init(self) -> Dict:
        return {
            # === 第一區策略權重 ===
            'w_trend': random.uniform(0.0, 1.0),
            'w_freq': random.uniform(0.0, 1.0),
            'w_markov': random.uniform(0.0, 1.0),
            'w_deviation': random.uniform(0.0, 1.0),
            
            # === 窗口參數 ===
            'trend_window': random.choice([20, 50, 100, 200]),
            'markov_order': random.choice([1, 2, 3]),
            
            # === 過濾器開關 ===
            'enable_kill': random.choice([True, False]),
            'kill_count': random.randint(5, 12),
            
            # === 雙軌策略開關 ===
            # Dual Path: 同時保留 "Top N" (High Prob) 和 "Bottom M" (Mean Reversion)
            'enable_dual_path': random.choice([True, False]),
            'top_n': random.randint(4, 8),
            'bottom_m': random.randint(1, 4), # 逆勢選號數量
            
            # === 第二區策略 ===
            # Second Zone: 1=Hot, 2=Cold, 3=Recent, 4=Random
            'zone2_strategy': random.choice([1, 2, 3]) 
        }

    def mutate(self):
        """隨機變異"""
        key = random.choice(list(self.params.keys()))
        
        # 數值型變異
        if key.startswith('w_'):
            self.params[key] = max(0.0, min(1.5, self.params[key] + random.uniform(-0.2, 0.2)))
        elif key == 'trend_window':
            self.params[key] = random.choice([20, 50, 100, 200, 300])
        elif key == 'markov_order':
            self.params[key] = random.choice([1, 2, 3])
        elif key == 'kill_count':
            self.params[key] = max(0, min(15, self.params[key] + random.choice([-1, 1])))
        elif key in ['enable_kill', 'enable_dual_path']:
             self.params[key] = not self.params[key]
        elif key == 'zone2_strategy':
            self.params[key] = random.choice([1, 2, 3, 4])
        elif key == 'top_n':
             self.params[key] = max(1, min(10, self.params[key] + random.choice([-1, 1])))
        elif key == 'bottom_m':
             self.params[key] = max(0, min(6, self.params[key] + random.choice([-1, 1])))

class PowerDiscoveryAgent:
    def __init__(self):
        self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db') # Default to standard db
        if not os.path.exists(self.db_path):
             self.db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
             
        self.db = DatabaseManager(db_path=self.db_path)
        self.engine = UnifiedPredictionEngine()
        self.rules = get_lottery_rules('POWER_LOTTO')
        self.history = self.db.get_all_draws(lottery_type='POWER_LOTTO')
        
        # Split Train/Val
        # Train: Past 300 to Past 50
        # Val: Past 50 to Now
        self.train_data = self.history[-(300+50):-50] 
        self.val_data = self.history[-50:]
        
        print(f"🧬 Power Lotto Auto-Discovery Started")
        print(f"📚 Total Draws: {len(self.history)}")
        print(f"📊 Training Set: {len(self.train_data)}, Validation Set: {len(self.val_data)}")

    def _simulate_zone2(self, history, strategy_code):
        """模擬第二區預測"""
        # Simple simulation for speed
        if not history: return [random.randint(1, 8)]
        
        recents = [d.get('second_zone', d.get('special', 0)) for d in history[-20:]]
        counts = {}
        for x in recents: counts[x] = counts.get(x, 0) + 1
        
        if strategy_code == 1: # Hot
            best = sorted(counts.items(), key=lambda x: x[1], reverse=True)
            return [best[0][0]] if best else [random.randint(1, 8)]
        elif strategy_code == 2: # Cold
            all_nums = set(range(1, 9))
            seen = set(counts.keys())
            unseen = list(all_nums - seen)
            if unseen: return [random.choice(unseen)]
            least = sorted(counts.items(), key=lambda x: x[1])
            return [least[0][0]]
        elif strategy_code == 3: # Recent Repeater
            return [history[-1].get('second_zone', history[-1].get('special'))]
        else:
            return [random.randint(1, 8)]

    def _predict_with_genome(self, genome: PowerStrategyGenome, history) -> dict:
        """
        使用基因參數執行一次預測
        Return: {'numbers': [1,2,3,4,5,6], 'special': 8}
        """
        params = genome.params
        
        # 1. 基礎模型分數
        # 為了效能，這裡我們不做完整的 Engine call，而是做一個輕量級模擬
        # (但在真實上線版應該 call engine)
        
        # 模擬：取出最近 Trend Window 的熱號
        all_nums = [n for d in history[-params['trend_window']:] for n in d['numbers']]
        counts = {}
        for n in all_nums: counts[n] = counts.get(n, 0) + 1
        
        scores = {n: 0 for n in range(1, self.rules['maxNumber'] + 1)}
        
        # Trend Score
        for n, c in counts.items():
            scores[n] += c * params['w_trend']
            
        # Markov (Simplified: Assume last draw neighbors have higher weight)
        if history:
            prev_nums = history[-1]['numbers']
            for pn in prev_nums:
                # 簡單模擬 Markov 轉移：相鄰號碼加分
                if pn + 1 <= 38: scores[pn+1] += params['w_markov']
                if pn - 1 >= 1: scores[pn-1] += params['w_markov']
                
        # 2. 殺號 (Negative Selection)
        if params['enable_kill']:
            # 簡單模擬殺號：殺掉最冷門的 N 個 (Bottom N Frequency)
            sorted_by_freq = sorted(counts.items(), key=lambda x: x[1])
            kill_candidates = [x[0] for x in sorted_by_freq[:params['kill_count']]]
            for kn in kill_candidates:
                scores[kn] = -999 # Kill
                
        # 3. 選號 (Dual Path)
        final_picks = []
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        # Path A: Top N (Hot/High Prob)
        path_a = [x[0] for x in sorted_scores if x[1] > -900][:params['top_n']]
        final_picks.extend(path_a)
        
        # Path B: Bottom M (Cold/Reversion) - 從非殺號區選分數最低的
        if params['enable_dual_path']:
            # 排除掉已選的 Path A 和被殺掉的號碼
            candidates = [x for x in sorted_scores if x[0] not in path_a and x[1] > -900]
            # 取最後 M 個 (分數最低但未被殺)
            path_b = [x[0] for x in candidates[-params['bottom_m']:]]
            final_picks.extend(path_b)
            
        # 確保數量足夠 (6個)
        final_picks = list(set(final_picks)) # 去重
        if len(final_picks) < 6:
            remaining = [x[0] for x in sorted_scores if x[0] not in final_picks and x[1] > -900]
            exclude_len = 6 - len(final_picks)
            final_picks.extend(remaining[:exclude_len])
            
        # 截斷多餘的 (如果 Dual Path 選太多)
        final_picks = final_picks[:6]
        
        # 4. 第二區
        z2 = self._simulate_zone2(history, params['zone2_strategy'])
        
        return {
            'numbers': sorted(final_picks),
            'special': z2[0]
        }

    def evaluate(self, genome: PowerStrategyGenome, dataset) -> float:
        """評估基因適應度 (Win Rate + Match Count)"""
        total_score = 0
        total_hits = 0
        z2_hits = 0
        
        # 隨機採樣 30 期進行快速評估 (避免跑太久)
        sample_size = min(len(dataset), 30)
        # 用固定的間隔採樣以保持穩定性
        step = len(dataset) // sample_size
        samples = [dataset[i*step] for i in range(sample_size)]
        
        for target in samples:
            # Reconstruct history implicitly (Simulation)
            # In real backtest we need strict history slicing.
            # Here we just use the 'dataset' index which is tricky.
            # Let's use the real index from self.history
            idx = self.history.index(target)
            current_history = self.history[:idx]
            
            prediction = self._predict_with_genome(genome, current_history)
            
            # Check Zone 1
            actual = set(target['numbers'])
            hit_count = len(actual & set(prediction['numbers']))
            
            # Check Zone 2
            actual_z2 = target.get('second_zone', target.get('special'))
            hit_z2 = (prediction['special'] == actual_z2)
            
            # Scoring
            # Match 3: 100 pts
            # Match 4: 1000 pts
            # Zone 2 Hit: 200 pts
            if hit_count >= 3: total_score += 100 * (10**(hit_count-3))
            elif hit_count == 2 and hit_z2: total_score += 50 # 普獎: 2+1
            
            if hit_z2: 
                total_score += 50
                z2_hits += 1
                
            total_hits += hit_count
            
        # Normalize score
        fitness = total_score / sample_size
        
        # Save detailed metrics
        genome.metrics = {
            'avg_hits': total_hits / sample_size,
            'z2_accuracy': z2_hits / sample_size
        }
        
        return fitness

    def crossover(self, p1: PowerStrategyGenome, p2: PowerStrategyGenome) -> PowerStrategyGenome:
        child_params = {}
        for k in p1.params:
            child_params[k] = p1.params[k] if random.random() > 0.5 else p2.params[k]
        return PowerStrategyGenome(child_params)

    def run(self):
        # 1. Init Population
        population = [PowerStrategyGenome() for _ in range(POPULATION_SIZE)]
        
        print("\n🚀 Starting Evolution...")
        
        for gen in range(GENERATIONS):
            # Evaluate
            for i, genome in enumerate(population):
                genome.fitness = self.evaluate(genome, self.train_data)
                
            # Sort
            population.sort(key=lambda x: x.fitness, reverse=True)
            best = population[0]
            
            print(f"Gen {gen+1}: Best Fitness {best.fitness:.1f} | Params: Kill={best.params['enable_kill']}, Dual={best.params['enable_dual_path']}, Z2_Strat={best.params['zone2_strategy']}")
            
            # Elitism
            new_pop = population[:ELITE_SIZE]
            
            # Crossover & Mutate
            while len(new_pop) < POPULATION_SIZE:
                parents = random.sample(population[:15], 2)
                child = self.crossover(parents[0], parents[1])
                if random.random() < MUTATION_RATE:
                    child.mutate()
                new_pop.append(child)
            population = new_pop
            
        # Final Validation
        best = population[0]
        print("\n🏆 Evolution Complete! validating on strictly unseen data...")
        final_score = self.evaluate(best, self.val_data)
        
        print(f"✅ Final Validation Fitness: {final_score:.1f}")
        print(f"📊 Validation Metrics: AvgMatch={best.metrics['avg_hits']:.2f}, Zone2={best.metrics['z2_accuracy']*100:.1f}%")
        print("\n📝 Best Strategy Genome:")
        print(json.dumps(best.params, indent=2))
        
        # Save to file
        output_file = 'power_lotto_best_genome.json'
        with open(output_file, 'w') as f:
            json.dump(best.params, f, indent=2)
        print(f"💾 Saved to {output_file}")

if __name__ == '__main__':
    agent = PowerDiscoveryAgent()
    agent.run()
