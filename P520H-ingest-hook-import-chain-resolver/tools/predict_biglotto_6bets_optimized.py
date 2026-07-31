#!/usr/bin/env python3
"""
大樂透六注精銳策略 (The Hexa-Core)
策略架構：由 6 位不同領域的專家各出一注，確保策略正交性 (Orthogonality)
1. 正統注 (Optimal Coverage): 雙注策略中的穩健冠軍
2. 威力注 (Power Pivot): 移植自威力彩的三錨點策略 (針對大獎)
3. 激進注 (Radical Gap): 專抓斷層與冷號回補
4. AI 注 (Machine Learning): 深度學習/統計模型預測
5. 平衡注 (Zone Balance): 強制區間平衡 (針對 01-19 空開的防禦)
6. 混沌注 (High Entropy): 高熵值隨機 (對抗完全隨機性)
"""
import sys
import os
import random
import logging
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.multi_bet_optimizer import MultiBetOptimizer
# Import prototypes
from tools.predict_biglotto_radical import RadicalPredictor
from tools.backtest_power_pivot_biglotto import get_deep_correlation_maps

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class BigLotto6BetOptimizer:
    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        self.optimizer = MultiBetOptimizer()
        self.radical_engine = RadicalPredictor()
        
    def generate_6bets(self, history: List[Dict], rules: Dict) -> Dict:
        """生成 6 注精銳組合"""
        print("🚀 正在生成六注精銳 (Hexa-Core) 預測...")
        bets = []
        
        # --- 1. 正統注 (Optimal Coverage - Best of 2-Bet) ---
        # 使用 MultiBetOptimizer 的 generate_power_dual_max_bets 或類似邏輯
        # 這裡為了單注最優，我們取 "Consensus" (共識) 最高的 Top 6
        print("  🔹 1. 正統注 (Optimal Coverage)...")
        res_stat = self.engine.statistical_predict(history, rules)
        res_freq = self.engine.frequency_predict(history, rules)
        res_dev = self.engine.deviation_predict(history, rules)
        
        # 簡單加權共識
        candidates = {}
        for n in res_stat['numbers']: candidates[n] = candidates.get(n, 0) + 1.5
        for n in res_freq['numbers']: candidates[n] = candidates.get(n, 0) + 1.0
        for n in res_dev['numbers']: candidates[n] = candidates.get(n, 0) + 1.2
        
        bet1_nums = sorted([n for n, s in sorted(candidates.items(), key=lambda x: x[1], reverse=True)[:6]])
        bets.append({'numbers': bet1_nums, 'strategy': 'Optimal Consensus (正統穩健)'})
        
        # --- 2. 威力注 (Power Pivot - Anchor Strategy) ---
        print("  🔹 2. 威力注 (Power Pivot)...")
        # 直接調用移植過來的邏輯 (需要部分重寫適配，這裡簡化調用 MultiBetOptimizer Cluster Pivot)
        try:
            c_map, t_map = get_deep_correlation_maps(history[-300:])
            meta = {
                'method': 'cluster_pivot',
                'anchor_count': 3, # 進取型錨點
                'correlation_map': c_map,
                'trio_correlation_map': t_map
            }
            # 生成 1 注
            res_power = self.optimizer.generate_diversified_bets(history, rules, num_bets=1, meta_config=meta)
            bet2 = res_power['bets'][0]
            bet2['strategy'] = 'Power Pivot (威力錨點)'
            bets.append(bet2)
        except Exception as e:
            print(f"    ⚠️ Power Pivot 生成失敗: {e}, 使用備用方案")
            bets.append({'numbers': sorted(random.sample(range(1, 50), 6)), 'strategy': 'Power Pivot (Fallback)'})

        # --- 3. 激進注 (Radical Gap - Anomaly Hunter) ---
        print("  🔹 3. 激進注 (Radical Gap)...")
        # 檢測最近是否有 Gap，如果沒有顯著 Gap，則默認針對 "遺漏值" 最大的區間
        # 這裡直接調用 RadicalPredictor (Gap Strategy)
        # 用 115000007 的經驗，針對 First Zone
        res_radical = self.radical_engine.predict_gap_strategy(history, rules, gap_zone=1) # 暫時固定 Gap 1 測試
        bets.append({'numbers': res_radical['numbers'], 'strategy': 'Radical Gap (激進斷層)'})

        # --- 4. AI 注 (Probability Model - Markov/Bayesian) ---
        print("  🔹 4. AI 注 (Machine Learning)...")
        # 結合 Bayesian 和 Markov
        res_bayesian = self.engine.bayesian_predict(history, rules)
        res_markov = self.engine.markov_predict(history, rules)
        # 取兩者交集或高分合集
        ai_pool = set(res_bayesian['numbers']) | set(res_markov['numbers'])
        if len(ai_pool) >= 6:
            bet4_nums = sorted(list(ai_pool)[:6]) # 簡單取前 6，可優化
        else:
            bet4_nums = sorted(list(ai_pool) + [n for n in range(1, 50) if n not in ai_pool][:6-len(ai_pool)])
        bets.append({'numbers': bet4_nums, 'strategy': 'AI Ensemble (貝葉斯+馬可夫)'})

        # --- 5. 平衡注 (Zone Balance - Defensive) ---
        print("  🔹 5. 平衡注 (Zone Balance)...")
        res_zone = self.engine.zone_balance_predict(history, rules)
        bets.append({'numbers': res_zone['numbers'], 'strategy': 'Zone Balance (區域平衡)'})

        # --- 6. 混沌注 (Chaos Hedge - Randomness) ---
        print("  🔹 6. 混沌注 (High Entropy)...")
        # 使用熵值選號 (Entropy) 或 Random
        res_entropy = self.engine.entropy_predict(history, rules)
        if res_entropy and res_entropy.get('numbers'):
             bets.append({'numbers': res_entropy['numbers'], 'strategy': 'Max Entropy (高熵值)'})
        else:
             # Fallback
             bets.append({'numbers': sorted(random.sample(range(1, 50), 6)), 'strategy': 'Random Chaos'})

        return bets

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    optimizer = BigLotto6BetOptimizer()
    bets = optimizer.generate_6bets(history, rules)

    print("\n" + "="*60)
    print("🎰 六注精銳 (Hexa-Core) 預測結果")
    print("="*60)
    for i, bet in enumerate(bets, 1):
        print(f"注 {i} [{bet['strategy']}]:")
        print(f"👉 {bet['numbers']}")
        print("-" * 30)
        
    # JSON Output logic would go here

if __name__ == '__main__':
    main()
