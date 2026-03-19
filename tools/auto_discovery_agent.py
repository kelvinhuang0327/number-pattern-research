#!/usr/bin/env python3
"""
Auto-Discovery Agent (自動探索代理)
利用遺傳算法 (Genetic Algorithm) 自動搜尋大樂透最佳預測參數組合。

目標：
找出比人工設定更優的參數組合 (e.g., Weights, Window Sizes)
並將最佳策略保存至 Leaderboard。
"""
import sys
import os
import random
import json
import argparse
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple
from copy import deepcopy

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine

# 配置常數
POPULATION_SIZE = 20  # 種群大小
GENERATIONS = 5      # 迭代代數 (Demo用，實際可設更大)
ELITE_SIZE = 4        # 精英保留數
MUTATION_RATE = 0.2   # 變異率

class StrategyGenome:
    """策略基因組: 代表一組參數配置"""
    def __init__(self, params: Dict = None):
        if params:
            self.params = params
        else:
            # 隨機初始化基因
            self.params = {
                'trend_window': random.choice([50, 100, 200, 300, 500]),
                'gap_window': random.choice([30, 50, 100]),
                'weight_trend': random.uniform(0.1, 1.0),
                'weight_gap': random.uniform(0.1, 1.0),
                'weight_freq': random.uniform(0.1, 1.0),
                'elite_pool_size': random.choice([24, 30, 36])
            }
        self.fitness = 0.0

    def mutate(self):
        """隨機變異"""
        key = random.choice(list(self.params.keys()))
        if key == 'trend_window':
            self.params[key] = random.choice([50, 100, 200, 300, 500])
        elif key == 'gap_window':
            self.params[key] = random.choice([30, 50, 100])
        elif key == 'elite_pool_size':
            self.params[key] = random.choice([24, 30, 36])
        else:
            # 權重變異
            self.params[key] = max(0.0, min(2.0, self.params[key] + random.uniform(-0.2, 0.2)))

class AutoDiscoveryAgent:
    def __init__(self):
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.engine = UnifiedPredictionEngine()
        self.history = self.db.get_all_draws(lottery_type='BIG_LOTTO')
        self.rules = get_lottery_rules('BIG_LOTTO')
        
        # 準備訓練數據 (最近 100 期作為驗證集)
        self.train_history = self.history[:-100]
        self.val_history = self.history[-100:]
        
        print(f"🧬 Auto-Discovery Agent 初始化完成")
        print(f"📊 訓練集: {len(self.train_history)} 期, 驗證集: {len(self.val_history)} 期")

    def evaluate_fitness(self, genome: StrategyGenome) -> float:
        """評估適應度 (Win Rate on Validation Set)"""
        # 這裡簡化模擬：使用參數權重組合成一個簡單的加權分數預測
        # 實際應調用完整的預測邏輯
        
        wins = 0
        total = 0
        
        # 模擬快速回測 (只測驗證集)
        # 為了速度，這裡使用簡化的評估邏輯
        # 注意: 這是 Genetic Algorithm 的核心瓶頸，真實場景需要並行計算
        
        for target_draw in self.val_history:
            target_idx = self.history.index(target_draw)
            current_history = self.history[:target_idx]
            
            # 使用基因參數進行預測
            # 1. 模擬精英池選擇 (根據 genome.elite_pool_size)
            # 這裡簡化為隨機+權重模擬效果 (真實應調用 SmartSelector)
            
            # 為了演示，我們使用一個基於參數的簡單邏輯
            # 如果參數好，勝率高 (這裡用隨機擾動模擬，真實應接入 PredictionEngine)
            # 在真實實作中，這裡必須是 Real Prediction
            
            # 這裡我們接入真實的 UnifiedEngine 的部分組件
            # 但為了性能，我們只測 20 期
            if total >= 20: break 
            
            # 實際預測:
            # 使用 Trend (weighted freq)
            trend_win = genome.params['trend_window']
            trend_res = self.engine.trend_predict(current_history[-trend_win:], self.rules)
            
            # 使用 Freq
            freq_res = self.engine.frequency_predict(current_history, self.rules)
            
            # 綜合
            scores = {}
            for n in trend_res['numbers']: scores[n] = scores.get(n, 0) + genome.params['weight_trend']
            for n in freq_res['numbers']: scores[n] = scores.get(n, 0) + genome.params['weight_freq']
            
            # 選前 6
            best_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:6]
            pred_nums = set([n for n, s in best_nums])
            actual_nums = set(target_draw['numbers'])
            
            if len(pred_nums & actual_nums) >= 3:
                wins += 1
            total += 1
            
        return (wins / total) * 100 if total > 0 else 0

    def crossover(self, parent1: StrategyGenome, parent2: StrategyGenome) -> StrategyGenome:
        """交叉繁殖"""
        child_params = {}
        for key in parent1.params:
            if random.random() > 0.5:
                child_params[key] = parent1.params[key]
            else:
                child_params[key] = parent2.params[key]
        return StrategyGenome(child_params)

    def run_optimization(self):
        print("🌱 初始化種群...")
        population = [StrategyGenome() for _ in range(POPULATION_SIZE)]
        
        for generation in range(GENERATIONS):
            print(f"\n🔄 Generation {generation + 1}/{GENERATIONS}")
            
            # 評估適應度
            for i, genome in enumerate(population):
                genome.fitness = self.evaluate_fitness(genome)
                print(f"   Genome {i+1}: Fitness = {genome.fitness:.2f}% (TrendWin={genome.params['trend_window']}, W_Trend={genome.params['weight_trend']:.2f})")
            
            # 排序
            population.sort(key=lambda x: x.fitness, reverse=True)
            best_genome = population[0]
            print(f"   🏆 Generation Best: {best_genome.fitness:.2f}%")
            
            # 精英保留
            new_population = population[:ELITE_SIZE]
            
            # 繁殖
            while len(new_population) < POPULATION_SIZE:
                parent1 = random.choice(population[:10]) # Top 50%
                parent2 = random.choice(population[:10])
                child = self.crossover(parent1, parent2)
                if random.random() < MUTATION_RATE:
                    child.mutate()
                new_population.append(child)
                
            population = new_population
            
        best = population[0]
        print("\n" + "="*50)
        print("🎉 Optimization Complete")
        print(f"Best Fitness: {best.fitness:.2f}%")
        print("Best Parameters:")
        print(json.dumps(best.params, indent=2))
        
        # 保存到 Leaderboard
        self.save_to_leaderboard(best)

    def save_to_leaderboard(self, best_genome):
        path = os.path.join(project_root, 'docs', 'BEST_STRATEGY_LEADERBOARD.json')
        leaderboard = []
        if os.path.exists(path):
            with open(path, 'r') as f:
                try: leaderboard = json.load(f)
                except: pass
        
        entry = {
            'date': datetime.now().isoformat(),
            'fitness': best_genome.fitness,
            'params': best_genome.params,
            'lottery': 'BIG_LOTTO'
        }
        leaderboard.append(entry)
        leaderboard.sort(key=lambda x: x.get('fitness', 0), reverse=True)
        
        with open(path, 'w') as f:
            json.dump(leaderboard[:10], f, indent=2)
        print(f"💾 Saved to {path}")

if __name__ == '__main__':
    agent = AutoDiscoveryAgent()
    agent.run_optimization()
