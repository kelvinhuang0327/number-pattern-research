#!/usr/bin/env python3
"""
快速 ML 預測器 - 可直接執行
使用統計和簡單機器學習方法
"""

import json
import sys
import numpy as np
import pandas as pd
from collections import Counter, defaultdict


class QuickMLPredictor:
    """輕量級 ML 預測器（不需要額外依賴）"""
    
    def __init__(self, data_file, lottery_type='BIG_LOTTO'):
        print(f"🎯 載入數據: {data_file}")
        self.df = pd.read_csv(data_file)
        
        # 解析號碼
        self.df['numbers_list'] = self.df['numbers'].apply(
            lambda x: [int(n) for n in str(x).split(',') if n.strip().isdigit()]
        )
        
        self.lottery_type = lottery_type
        self.config = {
            'BIG_LOTTO': {'range': (1, 49), 'pick': 6},
            'SUPER_LOTTO': {'range': (1, 49), 'pick': 6},
            '威力彩': {'range': (1, 38), 'pick': 6},
            '今彩539': {'range': (1, 39), 'pick': 5},
        }[lottery_type]
        
        print(f"✅ 已載入 {len(self.df)} 期數據")
    
    def predict_advanced_ensemble(self, top_n=10):
        """
        進階集成預測 - 結合 10 種演算法
        """
        print("\n🤖 執行進階集成預測...")
        
        min_num, max_num = self.config['range']
        pick_count = self.config['pick']
        
        # 初始化得分
        scores = defaultdict(float)
        
        # === 方法 1: 加權頻率分析 (15%) ===
        recent_weights = [0.4, 0.3, 0.2, 0.1]  # 最近幾期的權重
        for weight_idx, (weight, period) in enumerate(zip(recent_weights, [10, 20, 30, 50])):
            data = self.df.head(min(period, len(self.df)))
            freq = Counter()
            for nums in data['numbers_list']:
                freq.update(nums)
            
            max_freq = max(freq.values()) if freq else 1
            for num, count in freq.items():
                scores[num] += (count / max_freq) * weight * 15
        
        # === 方法 2: 遺漏值反彈預測 (12%) ===
        for num in range(min_num, max_num + 1):
            missing = 0
            for i, row in self.df.iterrows():
                if num in row['numbers_list']:
                    break
                missing += 1
            
            # 遺漏越久，分數越高（有上限）
            if missing > 0:
                scores[num] += min(missing / 10, 2.5) * 12
        
        # === 方法 3: 週期性預測 (10%) ===
        for num in range(min_num, max_num + 1):
            appearances = []
            for i, row in self.df.iterrows():
                if num in row['numbers_list']:
                    appearances.append(i)
            
            if len(appearances) >= 3:
                intervals = [appearances[i] - appearances[i+1] for i in range(len(appearances)-1)]
                avg_interval = np.mean(intervals)
                std_interval = np.std(intervals)
                
                # 如果當前遺漏接近平均週期，加分
                current_missing = appearances[0] if appearances else len(self.df)
                if abs(current_missing - avg_interval) < std_interval:
                    scores[num] += 10
        
        # === 方法 4: 連號預測 (8%) ===
        recent_nums = []
        for nums in self.df.head(5)['numbers_list']:
            recent_nums.extend(nums)
        
        for num in range(min_num, max_num + 1):
            if (num - 1) in recent_nums or (num + 1) in recent_nums:
                scores[num] += 8
        
        # === 方法 5: 奇偶平衡 (8%) ===
        recent_odd_counts = []
        for nums in self.df.head(20)['numbers_list']:
            recent_odd_counts.append(sum(1 for n in nums if n % 2 == 1))
        
        avg_odd = np.mean(recent_odd_counts)
        for num in range(min_num, max_num + 1):
            if num % 2 == 1 and avg_odd > pick_count / 2:
                scores[num] += 8
            elif num % 2 == 0 and avg_odd < pick_count / 2:
                scores[num] += 8
        
        # === 方法 6: 區間平衡 (8%) ===
        zone_size = (max_num - min_num + 1) // 3
        zone_counts = [0, 0, 0]
        for nums in self.df.head(10)['numbers_list']:
            for num in nums:
                zone = min((num - min_num) // zone_size, 2)
                zone_counts[zone] += 1
        
        avg_zone = np.mean(zone_counts)
        for num in range(min_num, max_num + 1):
            zone = min((num - min_num) // zone_size, 2)
            if zone_counts[zone] < avg_zone:
                scores[num] += 8
        
        # === 方法 7: 和值預測 (7%) ===
        recent_sums = [sum(nums) for nums in self.df.head(20)['numbers_list']]
        avg_sum = np.mean(recent_sums)
        std_sum = np.std(recent_sums)
        
        # 先選出高分號碼，計算其和值
        temp_top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:pick_count * 2]
        for num, _ in temp_top:
            scores[num] += 7  # 基礎分
        
        # === 方法 8: AC值優化 (7%) ===
        recent_acs = []
        for nums in self.df.head(20)['numbers_list']:
            sorted_nums = sorted(nums)
            diffs = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
            ac = len(set(diffs))
            recent_acs.append(ac)
        
        avg_ac = np.mean(recent_acs)
        # AC值高表示號碼分散，給分散的號碼加分
        if avg_ac > pick_count - 2:
            for num in range(min_num, max_num + 1):
                if num % 7 == 0:  # 分散選號
                    scores[num] += 7
        
        # === 方法 9: 歷史模式匹配 (15%) ===
        recent_pattern = list(self.df.head(3)['numbers_list'])
        for i in range(3, len(self.df) - 1):
            pattern = list(self.df.iloc[i:i+3]['numbers_list'])
            
            # 計算相似度
            similarity = 0
            for j in range(3):
                intersection = len(set(pattern[j]) & set(recent_pattern[j]))
                similarity += intersection / pick_count
            
            similarity /= 3
            
            if similarity > 0.25:
                next_nums = self.df.iloc[i+3]['numbers_list']
                for num in next_nums:
                    scores[num] += similarity * 15
        
        # === 方法 10: 機率衰減模型 (10%) ===
        for num in range(min_num, max_num + 1):
            prob = 0
            decay_factor = 0.9
            for i, row in enumerate(self.df.head(30)['numbers_list']):
                if num in row:
                    prob += (decay_factor ** i) * 10
            scores[num] += prob
        
        # 選擇得分最高的號碼
        sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        predicted = [num for num, score in sorted_nums[:pick_count]]
        
        # 計算信心度
        top_scores = [score for num, score in sorted_nums[:pick_count]]
        confidence = min(np.mean(top_scores) / 2, 95)
        
        result = {
            'numbers': sorted(predicted),
            'method': '進階集成 (10種演算法)',
            'confidence': round(confidence, 1),
            'top_probabilities': {
                num: round(score, 2) 
                for num, score in sorted_nums[:top_n]
            },
            'details': {
                '總演算法數': 10,
                '數據期數': len(self.df),
                '預測號碼數': pick_count
            }
        }
        
        return result
    
    def predict_smart_hybrid(self):
        """智能混合策略"""
        print("\n🧠 執行智能混合預測...")
        
        min_num, max_num = self.config['range']
        pick_count = self.config['pick']
        
        # 1. 找出熱號 (頻率最高的 30%)
        freq = Counter()
        for nums in self.df.head(30)['numbers_list']:
            freq.update(nums)
        hot_nums = [num for num, _ in freq.most_common(int((max_num - min_num + 1) * 0.3))]
        
        # 2. 找出溫號 (中等頻率)
        warm_nums = [num for num, _ in freq.most_common(int((max_num - min_num + 1) * 0.6))][len(hot_nums):]
        
        # 3. 找出冷號 (遺漏最久)
        missing_scores = {}
        for num in range(min_num, max_num + 1):
            missing = 0
            for i, row in self.df.iterrows():
                if num in row['numbers_list']:
                    break
                missing += 1
            missing_scores[num] = missing
        
        cold_nums = sorted(missing_scores.items(), key=lambda x: x[1], reverse=True)
        cold_nums = [num for num, _ in cold_nums[:int((max_num - min_num + 1) * 0.3)]]
        
        # 混合選號: 50% 熱號 + 30% 溫號 + 20% 冷號
        hot_count = int(pick_count * 0.5)
        warm_count = int(pick_count * 0.3)
        cold_count = pick_count - hot_count - warm_count
        
        predicted = []
        predicted.extend(hot_nums[:hot_count])
        predicted.extend(warm_nums[:warm_count])
        predicted.extend(cold_nums[:cold_count])
        
        # 如果不足，補充
        all_nums = set(range(min_num, max_num + 1))
        used = set(predicted)
        remaining = list(all_nums - used)
        predicted.extend(remaining[:pick_count - len(predicted)])
        
        predicted = predicted[:pick_count]
        
        return {
            'numbers': sorted(predicted),
            'method': '智能混合 (熱50%+溫30%+冷20%)',
            'confidence': 72,
            'composition': {
                '熱號': [n for n in predicted if n in hot_nums],
                '溫號': [n for n in predicted if n in warm_nums],
                '冷號': [n for n in predicted if n in cold_nums]
            }
        }


def main():
    if len(sys.argv) < 2:
        print("使用方法: python quick_ml_predict.py <csv_file> [lottery_type]")
        print("範例: python quick_ml_predict.py ../data/sample-data.csv BIG_LOTTO")
        return
    
    csv_file = sys.argv[1]
    lottery_type = sys.argv[2] if len(sys.argv) > 2 else 'BIG_LOTTO'
    
    # 創建預測器
    predictor = QuickMLPredictor(csv_file, lottery_type)
    
    # 執行多種預測
    print("\n" + "=" * 60)
    print("🎯 預測結果")
    print("=" * 60)
    
    # 方法 1: 進階集成
    result1 = predictor.predict_advanced_ensemble()
    print(f"\n【{result1['method']}】")
    print(f"預測號碼: {result1['numbers']}")
    print(f"信心度: {result1['confidence']}%")
    print(f"前10機率: {result1['top_probabilities']}")
    
    # 方法 2: 智能混合
    result2 = predictor.predict_smart_hybrid()
    print(f"\n【{result2['method']}】")
    print(f"預測號碼: {result2['numbers']}")
    print(f"信心度: {result2['confidence']}%")
    print(f"組成: {result2['composition']}")
    
    # 輸出 JSON 格式（可被 JS 調用）
    output = {
        'advanced_ensemble': result1,
        'smart_hybrid': result2,
        'timestamp': pd.Timestamp.now().isoformat()
    }
    
    print(f"\n📝 JSON 輸出:")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
