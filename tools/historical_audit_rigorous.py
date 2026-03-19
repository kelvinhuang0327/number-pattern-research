#!/usr/bin/env python3
"""
Rigorous Historical Audit Script
================================
1. 確保零資料洩漏 (Zero Data Leakage)。
2. 支援多個時間里程碑 (150, 500, 1000, Full History)。
3. 使用 AI 自主發現的「戰略食譜」進行極限壓力測試。
"""
import os
import sys
import json
import argparse
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.strategy_leaderboard import StrategyLeaderboard

class Auditor:
    def __init__(self, lottery_type='POWER_LOTTO'):
        self.lb = StrategyLeaderboard(lottery_type=lottery_type)
        self.lottery_type = lottery_type
        self.recipe = self.load_recipe()
        
    def load_recipe(self):
        file_path = os.path.join(project_root, 'tools', 'data', f"best_config_{self.lottery_type}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def validate_combination(self, nums):
        """統計剪枝過濾器：排除機率極低的組合"""
        s = sum(nums)
        if self.lottery_type == 'BIG_LOTTO':
            if not (100 <= s <= 200): return False
        else:
            if not (80 <= s <= 160): return False
        evens = len([n for n in nums if n % 2 == 0])
        if evens < 1 or evens > 5: return False
        nums_sorted = sorted(nums)
        consecutive_groups = 0
        for i in range(len(nums_sorted)-1):
            if nums_sorted[i+1] - nums_sorted[i] == 1: consecutive_groups += 1
        return consecutive_groups <= 2

    def execute_recipe(self, history, n_bets=2, use_pruning=True):
        """完全依照食譜進行選號 (加強剪枝驗證)"""
        if not self.recipe:
            return []
            
        scores = np.zeros(self.lb.max_num + 1)
        for comp in self.recipe["components"]:
            func = getattr(self.lb, comp["name"])
            bets = func(history, n_bets=4, window=comp["window"])
            for b in bets:
                for n in b:
                    scores[n] += (comp["weight"] / 4.0)
        
        all_indices = np.arange(1, self.lb.max_num + 1)
        sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
        
        if not use_pruning:
            bets = []
            for i in range(n_bets):
                start = i * 6
                end = (i + 1) * 6
                bets.append(sorted(sorted_indices[start:end].tolist()))
            return bets

        # Rank-Aware Pruned Selection
        bets = []
        next_start_idx = 0
        for b_idx in range(n_bets):
            found = False
            for offset in range(30):
                if found: break
                base_ptr = next_start_idx
                if base_ptr + 6 > len(sorted_indices): break
                
                candidate = sorted(sorted_indices[base_ptr : base_ptr+6].tolist())
                if self.validate_combination(candidate):
                    bets.append(candidate)
                    next_start_idx += 6
                    found = True
                else:
                    for swap_idx in range(base_ptr+6, min(base_ptr+12, len(sorted_indices))):
                        alt_candidate = sorted(sorted_indices[base_ptr:base_ptr+5].tolist() + [sorted_indices[swap_idx]])
                        if self.validate_combination(alt_candidate):
                            bets.append(alt_candidate)
                            next_start_idx = base_ptr + 6
                            found = True
                            break
            if not found:
                bets.append(sorted(sorted_indices[next_start_idx:next_start_idx+6].tolist()))
                next_start_idx += 6
        return bets

    def run_audit(self, periods):
        if periods > len(self.lb.draws):
            periods = len(self.lb.draws) - 200 # 保留一些歷史給第一個測試點
            
        print(f"\n🔍 Auditing {self.lottery_type} | Milestone: N={periods}")
        
        hits_3_plus = 0
        total = 0
        
        # 實施零洩漏回測協定
        for i in range(periods):
            idx = len(self.lb.draws) - periods + i
            if idx <= 0: continue
            
            target = self.lb.draws[idx]['numbers'] # 未來 (目標)
            history = self.lb.draws[:idx]          # 過去 (訓練資料) - 嚴格隔離
            
            # 對於需要 Window=150 的策略，確保歷史足夠
            if len(history) < 150: continue
            
            bets = self.execute_recipe(history, n_bets=2)
            
            win = False
            for b in bets:
                if self.lb.get_hits(b, target) >= 3:
                    win = True
                    break
            if win:
                hits_3_plus += 1
            total += 1
            
        rate = hits_3_plus / total if total > 0 else 0
        baseline = self.lb.rand_win_2 # 理論隨機基準 (2注)
        edge = rate - baseline
        
        return {
            "periods": periods,
            "win_rate": rate,
            "baseline": baseline,
            "edge": edge,
            "total_tested": total
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='POWER_LOTTO', choices=['POWER_LOTTO', 'BIG_LOTTO'])
    args = parser.parse_args()
    
    auditor = Auditor(lottery_type=args.lottery)
    if not auditor.recipe:
        print(f"❌ No recipe found for {args.lottery}. Run ai_config_optimizer first.")
        return

    milestones = [150, 500, 1000, 99999] # 99999 denotes 'Full'
    
    print("="*80)
    print(f"🚀 COMPREHENSIVE HISTORICAL AUDIT: {args.lottery}")
    print(f"Strategic Recipe: {[c['name'] for c in auditor.recipe['components']]}")
    print("="*80)
    print(f"{'Milestone':<12} | {'Tested':<8} | {'Win Rate':<10} | {'Baseline':<10} | {'Edge'}")
    print("-" * 80)
    
    for m in milestones:
        res = auditor.run_audit(m)
        label = f"N={m}" if m < 90000 else "Full History"
        edge_str = f"{res['edge']*100:+.2f}%"
        print(f"{label:<12} | {res['total_tested']:<8} | {res['win_rate']*100:8.2f}% | {res['baseline']*100:8.2f}% | {edge_str}")
    
    print("="*80)

if __name__ == "__main__":
    main()
