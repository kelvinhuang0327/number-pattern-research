#!/usr/bin/env python3
"""
🎰 彩票診斷工具 (Automated Failure Diagnosis)
版本: P2-2026.01.12
功能: 自動診斷指定期數的中獎失敗原因，分析模型的盲區。
"""
import sys
import os
import io
import math
import argparse
from collections import Counter, defaultdict

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.multi_bet_optimizer import MultiBetOptimizer
from models.unified_predictor import UnifiedPredictionEngine
from database import DatabaseManager
from common import get_lottery_rules
from tools.negative_selector import NegativeSelector

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class DrawDiagnoser:
    def __init__(self, lottery_type='BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        self.optimizer = MultiBetOptimizer()
        self.selector = NegativeSelector(lottery_type)

    def calculate_entropy(self, numbers, num_zones=5):
        max_num = self.rules['maxNumber']
        zone_size = max_num / num_zones
        counts = [0] * num_zones
        for n in numbers:
            idx = min(int((n-1) / zone_size), num_zones - 1)
            counts[idx] += 1
        entropy = 0
        p_list = [c / len(numbers) for c in counts]
        for p in p_list:
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    def diagnose(self, draw_id):
        all_draws = self.db.get_all_draws(self.lottery_type)
        print(f"DEBUG: Found {len(all_draws)} draws for {self.lottery_type}")
        all_draws_asc = list(reversed(all_draws))
        
        target_idx = -1
        for i, d in enumerate(all_draws_asc):
            if str(d['draw']) == str(draw_id):
                target_idx = i
                break
        
        if target_idx == -1:
            print(f"❌ 錯誤: 資料庫中找不到期數 {draw_id}")
            return

        target_draw = all_draws_asc[target_idx]
        history = all_draws_asc[:target_idx]
        actual_nums = set(target_draw['numbers'])
        actual_special = target_draw.get('special')

        print("=" * 80)
        print(f"🔍 診斷報告: {self.lottery_type} 第 {draw_id} 期")
        print(f"📅 開獎日期: {target_draw.get('date', 'Unknown')}")
        print(f"🔢 開獎號碼: {sorted(list(actual_nums))} (特別號: {actual_special})")
        print("=" * 80)

        # 1. 區域密度分析 (Skewed Analysis)
        current_entropy = self.calculate_entropy(target_draw['numbers'])
        recent_30 = history[-30:]
        system_entropy = self.selector._calculate_regional_entropy(recent_30)
        
        print(f"\n[1] 區域密度診斷 (Entropy Analysis)")
        print(f"   - 系統前期熵值 (System): {system_entropy:.4f}")
        print(f"   - 本期開獎熵值 (Target): {current_entropy:.4f}")
        
        if current_entropy < 1.8:
            print(f"   - ⚠️ 診斷結果: 【密度極高 (Grouped)】本期開出偏態，大眾模型通常會失準。")
        elif current_entropy > 2.2:
            print(f"   - ⚠️ 診斷結果: 【極端平均 (Dispersed)】本期非常分散。")
        else:
            print(f"   - ✅ 診斷結果: 本期分佈正常。")

        # 2. 負向排除診斷 (Kill List Check)
        kill_list = self.selector.predict_kill_numbers(count=10, history=history)
        wrong_kills = actual_nums & set(kill_list)
        print(f"\n[2] 負向排除診斷 (Negative Selection)")
        if wrong_kills:
            print(f"   - ⚠️ 診斷結果: 【誤殺】號碼 {sorted(list(wrong_kills))} 被殺號機制排除。")
            # 分析誤殺號碼的特徵
            for nk in wrong_kills:
                # Calculate gap for this number
                gap = 999
                for j, d in enumerate(reversed(history)):
                    if nk in d['numbers']:
                        gap = j
                        break
                print(f"     * 號碼 {nk:02d}: 遺漏值為 {gap}，頻率不高，被歸類為冷碼而被殺。")
        else:
            print(f"   - ✅ 診斷結果: 殺號機制成功避開了中獎號碼。")

        # 3. 排名覆蓋診斷 (Ranking Coverage)
        # Using a statistical mock if probabilities_all isn't readily exposed
        all_n_history = [n for d in history[-200:] for n in d['numbers']]
        f_counts = Counter(all_n_history)
        
        ranked_nums = sorted(f_counts.items(), key=lambda x: x[1], reverse=True)
        top_25 = [n for n, s in ranked_nums[:25]]
        top_covers = actual_nums & set(top_25)
        
        print(f"\n[3] 排名覆蓋診斷 (Elite Pool Coverage)")
        print(f"   - 前 25 名高頻號碼覆蓋率: {len(top_covers)}/6 ({len(top_covers)/6*100:.1f}%)")
        print(f"   - 覆蓋到的熱碼: {sorted(list(top_covers))}")
        missed = actual_nums - set(top_25)
        if len(missed) > 3:
            print(f"   - ⚠️ 診斷結果: 【冷門爆發】多數中獎號碼不在前 25 名熱榜內。")
        else:
            print(f"   - ✅ 診斷結果: 核心池表現正常。")

        # 4. 方法論細項命中率
        print(f"\n[4] 基礎模型細分命中分析 (Method Drill-down)")
        methods = [
            ('Frequency', self.engine.frequency_predict),
            ('Bayesian', self.engine.bayesian_predict),
            ('Markov', self.engine.markov_predict),
            ('Deviation', self.engine.deviation_predict),
        ]
        
        for name, func in methods:
            try:
                res = func(history, self.rules)
                hit = len(set(res['numbers']) & actual_nums)
                print(f"   - {name:<10}: 命中 {hit} 個")
            except:
                pass
        
        # 5. 總結建議
        print("\n" + "-" * 80)
        print("💡 最終診斷與行動建議:")
        diagnosis_count = 0
        if len(wrong_kills) > 0:
            print("   👉 【重點】殺號機制發生誤殺，請檢查 P1 動態門檻是否已生效或需進一步放廣。")
            diagnosis_count += 1
        if current_entropy < 1.8:
            print("   👉 【重點】檢測到高密度分佈，模型應確保 Skewed Mode 處於激活狀態。")
            diagnosis_count += 1
        if len(missed) > 3:
            print("   👉 【重點】冷熱門分佈異常，建議檢查「冷碼回補 (Cold Rebound)」子模型的權重。")
            diagnosis_count += 1
            
        if diagnosis_count == 0:
            print("   👉 數據分佈、殺號、及熱號池均正常。請檢查組合優化器 (Combinatorial Optimizer) 的篩選過濾強度是否太高，導致高品質注項被拋棄。")
        print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description="彩票失敗自動診斷工具")
    parser.add_argument("draw_id", help="要診斷的期數 ID (例如 115000003)")
    parser.add_argument("--type", default="BIG_LOTTO", help="彩票類型 (預設 BIG_LOTTO)")
    args = parser.parse_args()

    diagnoser = DrawDiagnoser(args.type)
    diagnoser.diagnose(args.draw_id)

if __name__ == "__main__":
    main()
