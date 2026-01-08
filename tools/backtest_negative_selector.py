#!/usr/bin/env python3
"""
Negative Selection Backtest & Optimizer (2025)
目標：驗證並優化「殺號機制」，確保排除的號碼真的不會開出
"""
import sys
import os
import io
import logging
from collections import Counter
import numpy as np

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from database import DatabaseManager
from common import get_lottery_rules

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class NegativeSelectorBacktester:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        
    def get_data(self):
        # Get data ASC (Oldest -> Newest)
        draws_desc = self.db.get_all_draws(lottery_type=self.lottery_type)
        return list(reversed(draws_desc))
        
    def strategy_cold_simple(self, history, kill_count=15):
        """策略1: 純冷門殺號 (近100期頻率最低)"""
        if len(history) < 100:
            return []
            
        freq = Counter([n for d in history[-100:] for n in d['numbers']])
        
        scores = []
        min_num = self.rules['minNumber']
        max_num = self.rules['maxNumber']
        for n in range(min_num, max_num + 1):
            scores.append((n, freq.get(n, 0)))
            
        # 頻率越低越容易被殺
        scores.sort(key=lambda x: x[1])
        return [n for n, s in scores[:kill_count]]

    def strategy_cold_smart(self, history, kill_count=15):
        """策略2: 聰明殺號 (避開極限遺漏值)"""
        # 如果一個號碼很久沒開 (Gap > Threshold)，它可能會強勢回歸，不能殺
        if len(history) < 100:
            return []
            
        # 1. 計算頻率
        freq = Counter([n for d in history[-100:] for n in d['numbers']])
        
        # 2. 計算遺漏值
        gaps = {}
        min_num = self.rules['minNumber']
        max_num = self.rules['maxNumber']
        for n in range(min_num, max_num + 1):
            gaps[n] = len(history) # Default
            for i, draw in enumerate(reversed(history)):
                if n in draw['numbers']:
                    gaps[n] = i
                    break
        
        scores = []
        for n in range(min_num, max_num + 1):
            f = freq.get(n, 0)
            g = gaps[n]
            
            # 危險檢查
            # Gap > 20 的號碼非常危險 (隨時回補)，不要殺
            is_dangerous = g > 20
            
            if is_dangerous:
                # 給予極高分，避免被選中殺掉
                scores.append((n, 9999))
            else:
                scores.append((n, f)) # 頻率越低分越低 -> 殺掉
                
        scores.sort(key=lambda x: x[1])
        return [n for n, s in scores[:kill_count]]

    def run_backtest(self, year=2025, strategy='simple', kill_count=15):
        all_draws = self.get_data()
        test_draws = [d for d in all_draws if d['date'].startswith(str(year))]
        
        if not test_draws:
            print(f"No data for {year}")
            return

        print(f"啟動 {year} 回測 | 策略: {strategy} | 殺號數: {kill_count}")
        print("-" * 60)
        
        total_rounds = 0
        clean_rounds = 0
        total_killed_hits = 0
        
        # Start index for simulation
        start_idx = all_draws.index(test_draws[0])
        
        for i, target_draw in enumerate(test_draws):
            # Training data: everything before this draw
            # Use current_idx to slice properly
            current_idx = start_idx + i
            history = all_draws[:current_idx]
            
            if strategy == 'simple':
                kill_nums = self.strategy_cold_simple(history, kill_count)
            else:
                kill_nums = self.strategy_cold_smart(history, kill_count)
                
            winning_nums = set(target_draw['numbers'])
            hits = len(set(kill_nums) & winning_nums)
            
            total_rounds += 1
            total_killed_hits += hits
            if hits == 0:
                clean_rounds += 1
                
        accuracy = (clean_rounds / total_rounds) * 100
        avg_leaks = total_killed_hits / total_rounds
        
        print(f"測試期數: {total_rounds}")
        print(f"完全殺對期數: {clean_rounds}")
        print(f"殺號成功率 (Clean Kill Rate): {accuracy:.2f}%")
        print(f"平均每期誤殺 (Leaks): {avg_leaks:.2f} 個")
        print("-" * 60)
        
        return accuracy, avg_leaks

def main():
    backtester = NegativeSelectorBacktester()
    
    # Compare Configurations
    configs = [
        ('simple', 10),
        ('simple', 12),
        ('simple', 15),
        ('smart', 10),
        ('smart', 12),
        ('smart', 15),
        ('smart', 18) # Push limits
    ]
    
    results = []
    print("================================================================================")
    print("負向排除模型參數優化報告 (2025)")
    print("================================================================================")

    for strat, count in configs:
        acc, leaks = backtester.run_backtest(year=2025, strategy=strat, kill_count=count)
        results.append({
            'config': f"{strat}_{count}",
            'accuracy': acc,
            'leaks': leaks
        })
        
    print("\n🏆 最終排名 (按 Clean Kill Rate 排序)")
    results.sort(key=lambda x: x['accuracy'], reverse=True)
    
    print(f"{'Rank':<5} | {'Config':<15} | {'Clean Rate':<12} | {'Avg Leaks'}")
    print("-" * 60)
    for i, res in enumerate(results):
        print(f"{i+1:<5} | {res['config']:<15} | {res['accuracy']:6.2f}%      | {res['leaks']:.2f}")

    best = results[0]
    print("\n最佳建議:")
    print(f"使用配置: {best['config']}")
    print(f"預期每 {100/best['accuracy']:.1f} 期才會失誤一次 (會有漏網之魚)")
    print(f"平均每期只損失 {best['leaks']:.2f} 個中獎號碼")

if __name__ == '__main__':
    main()
