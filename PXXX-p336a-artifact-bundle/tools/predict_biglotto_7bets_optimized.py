#!/usr/bin/env python3
"""
大樂透七注衛星策略 (The Hepta-Slice)
策略架構：3核心 + 4衛星，追求最大化覆蓋範圍
1. 核心注 1 (Elite): 精英高分組合
2. 核心注 2 (Shadow): 影子互補組合 (與只有1不重疊)
3. 核心注 3 (Reversal): 反轉/冷門區塊捕捉
4-7. 衛星注 (Satellites): 對剩餘潛力號碼進行多樣化切片
"""
import sys
import os
import logging
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.multi_bet_optimizer import MultiBetOptimizer

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class BigLotto7BetOptimizer:
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        self.optimizer = MultiBetOptimizer()
        
    def generate_7bets(self, history: List[Dict], rules: Dict) -> Dict:
        """生成 7 注衛星組合"""
        print("🚀 正在生成七注衛星 (Hepta-Slice) 預測...")
        bets = []
        
        # --- Stage 1: Tri-Core (3 Bets) ---
        print("  🔹 Stage 1: 生成 3 核心 (Tri-Core)...")
        # 使用 MultiBetOptimizer 的 generate_tri_core_3bets
        # 但需要先計算分數
        # 這裡為了簡單，我們直接調用 MultiBetOptimizer.generate_diversified_bets 然後指定 num_bets=3 (它內部有 Tri-Core 路由)
        # 檢查 multi_bet_optimizer.py line 219:
        # if num_bets == 3 and ... return self.generate_tri_core_3bets(...)
        
        res_core = self.optimizer.generate_diversified_bets(history, rules, num_bets=3)
        core_bets = res_core['bets']
        
        # 標記策略
        core_bets[0]['strategy'] = 'Core 1 (Elite)'
        core_bets[1]['strategy'] = 'Core 2 (Shadow)'
        core_bets[2]['strategy'] = 'Core 3 (Reversal)'
        bets.extend(core_bets)
        
        # 獲取核心注已使用的號碼
        core_nums = set()
        for b in core_bets:
            core_nums.update(b['numbers'])
            
        print(f"    核心覆蓋: {len(core_nums)} 個號碼")

        # --- Stage 2: Satellites (4 Bets) ---
        print("  🔹 Stage 2: 生成 4 衛星 (Satellites)...")
        # 目標：從剩下的潛力號碼中挖掘
        # 1. 獲取所有號碼的評分
        # (這裡簡化，重新調用一次 statistical_predict 獲取排名，實際應複用)
        res_stat = self.engine.statistical_predict(history, rules)
        res_freq = self.engine.frequency_predict(history, rules)
        
        # 綜合評分榜
        candidates = {}
        for i, n in enumerate(res_stat['numbers']): candidates[n] = candidates.get(n, 0) + (50-i)
        for i, n in enumerate(res_freq['numbers']): candidates[n] = candidates.get(n, 0) + (50-i)
        
        sorted_candidates = [n for n, s in sorted(candidates.items(), key=lambda x: x[1], reverse=True)]
        
        # 過濾掉已經在核心注中的號碼 (或者是給它們較低權重？策略是"覆蓋"，所以優先選未覆蓋的)
        remaining_pool = [n for n in sorted_candidates if n not in core_nums]
        
        # 如果剩餘太少，補回核心號碼
        if len(remaining_pool) < 24: # 4注 * 6 = 24
             remaining_pool.extend([n for n in sorted_candidates if n in core_nums]) # 加回
        
        # 切片生成 4 注
        # Slice 1: Best of Rest
        bets.append({'numbers': sorted(remaining_pool[:6]), 'strategy': 'Satellite 1 (Best of Rest)'})
        # Slice 2: Mid Range
        bets.append({'numbers': sorted(remaining_pool[6:12]), 'strategy': 'Satellite 2 (Mid Range)'})
        # Slice 3: Longshots
        bets.append({'numbers': sorted(remaining_pool[12:18]), 'strategy': 'Satellite 3 (Longshots)'})
        # Slice 4: Zone Recovery (補缺區間)
        # 檢查前 6 注覆蓋了哪些區間
        all_covered = set().union(*[b['numbers'] for b in bets])
        zones_counts = [0]*5
        for n in all_covered: zones_counts[(n-1)//10] += 1
        coldest_zone = zones_counts.index(min(zones_counts))
        # 從 remaining_pool 中找屬於 coldest_zone 的號碼
        zone_nums = [n for n in remaining_pool[18:] if (n-1)//10 == coldest_zone]
        # 補滿 6 個
        if len(zone_nums) < 6:
            fillers = [n for n in remaining_pool[18:] if n not in zone_nums]
            zone_nums.extend(fillers[:6-len(zone_nums)])
            
        bets.append({'numbers': sorted(zone_nums[:6]), 'strategy': f'Satellite 4 (Zone {coldest_zone} Fill)'})
        
        return bets

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    optimizer = BigLotto7BetOptimizer()
    bets = optimizer.generate_7bets(history, rules)

    print("\n" + "="*60)
    print("🎰 七注衛星 (Hepta-Slice) 預測結果")
    print("="*60)
    for i, bet in enumerate(bets, 1):
        print(f"注 {i} [{bet['strategy']}]:")
        print(f"👉 {bet['numbers']}")
        print("-" * 30)

if __name__ == '__main__':
    main()
