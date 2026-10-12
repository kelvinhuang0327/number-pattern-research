#!/usr/bin/env python3
"""
雙注策略：正常模式 + 異常模式
基於 115000005 期回溯分析的建議實作

策略:
- Bet 1: 優化的 Bayesian 預測（主流模式）
- Bet 2: 異常模式預測（罕見特徵組合）
"""
import sys
import os
from typing import List, Dict, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from models.optimized_bayesian_predictor import OptimizedBayesianPredictor
from models.improved_special_predictor import ImprovedSpecialPredictor
from collections import Counter
import random


class DualBetAnomalyStrategy:
    """雙注異常模式策略"""
    
    def __init__(self):
        self.min_num = 1
        self.max_num = 38
        self.pick_count = 6
        self.bayesian_predictor = OptimizedBayesianPredictor()
        self.special_predictor = ImprovedSpecialPredictor()
    
    def predict_two_bets(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        生成雙注預測
        
        Returns:
            {
                'bet1': {...},  # 主流預測
                'bet2': {...},  # 異常預測
                'strategy': 'dual_bet_anomaly'
            }
        """
        if len(history) < 50:
            return self._fallback_two_bets()
        
        # Bet 1: 主流預測（優化Bayesian）
        bet1 = self.bayesian_predictor.predict(history, lottery_rules)
        bet1['source'] = 'optimized_bayesian'
        
        # Bet 2: 異常模式預測
        bet2 = self._predict_anomaly(history, lottery_rules)
        bet2['source'] = 'anomaly_pattern'
        
        return {
            'bet1': bet1,
            'bet2': bet2,
            'strategy': 'dual_bet_anomaly',
            'overlap': len(set(bet1['numbers']) & set(bet2['numbers'])),
            'coverage': len(set(bet1['numbers']) | set(bet2['numbers']))
        }
    
    def _predict_anomaly(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        異常模式預測
        
        異常特徵:
        1. 極端奇偶比 (1:5 或 5:1)
        2. 無連號
        3. 高區集中 (Zone3 有 3-4 個)
        4. 冷門號組合
        """
        # 分析歷史數據
        freq = Counter()
        for d in history[:100]:
            freq.update(d.get('numbers', []))
        
        expected_freq = 100 * 6 / 38
        
        # 識別冷門號（頻率 < 期望值 70%）
        cold_numbers = [
            n for n in range(self.min_num, self.max_num + 1)
            if freq.get(n, 0) < expected_freq * 0.7
        ]
        
        # 隨機選擇異常模式類型
        anomaly_type = random.choice(['extreme_even', 'extreme_odd', 'high_zone', 'cold_cluster'])
        
        if anomaly_type == 'extreme_even':
            combo = self._generate_extreme_even(freq, cold_numbers)
        elif anomaly_type == 'extreme_odd':
            combo = self._generate_extreme_odd(freq, cold_numbers)
        elif anomaly_type == 'high_zone':
            combo = self._generate_high_zone_cluster(freq, cold_numbers)
        else:
            combo = self._generate_cold_cluster(freq, cold_numbers)
        
        # 預測第二區
        special_result = self.special_predictor.predict_with_confidence(history, combo)
        
        return {
            'numbers': sorted(combo),
            'special': special_result['special'],
            'confidence': 0.45,  # 異常模式信心度較低
            'method': f'anomaly_{anomaly_type}',
            'anomaly_features': self._analyze_features(combo)
        }
    
    def _generate_extreme_even(self, freq: Counter, cold_numbers: List[int]) -> List[int]:
        """生成極端偶數組合 (5-6 個偶數)"""
        even_nums = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0]
        odd_nums = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
        
        # 權重：冷門號略高
        even_weights = [1.3 if n in cold_numbers else 1.0 for n in even_nums]
        odd_weights = [1.3 if n in cold_numbers else 1.0 for n in odd_nums]
        
        # 選擇 5 個偶數 + 1 個奇數（無連號）
        selected_evens = self._weighted_sample_no_consecutive(even_nums, even_weights, 5)
        selected_odds = self._weighted_sample_no_consecutive(odd_nums, odd_weights, 1)
        
        return selected_evens + selected_odds
    
    def _generate_extreme_odd(self, freq: Counter, cold_numbers: List[int]) -> List[int]:
        """生成極端奇數組合 (5-6 個奇數)"""
        even_nums = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 0]
        odd_nums = [n for n in range(self.min_num, self.max_num + 1) if n % 2 == 1]
        
        even_weights = [1.3 if n in cold_numbers else 1.0 for n in even_nums]
        odd_weights = [1.3 if n in cold_numbers else 1.0 for n in odd_nums]
        
        # 選擇 5 個奇數 + 1 個偶數（無連號）
        selected_odds = self._weighted_sample_no_consecutive(odd_nums, odd_weights, 5)
        selected_evens = self._weighted_sample_no_consecutive(even_nums, even_weights, 1)
        
        return selected_odds + selected_evens
    
    def _generate_high_zone_cluster(self, freq: Counter, cold_numbers: List[int]) -> List[int]:
        """生成高區集中組合 (Zone3 有 3-4 個)"""
        zone1 = list(range(1, 14))   # 1-13
        zone2 = list(range(14, 26))  # 14-25
        zone3 = list(range(26, 39))  # 26-38
        
        # 高區選 3-4 個
        zone3_count = random.choice([3, 4])
        zone3_weights = [1.3 if n in cold_numbers else 1.0 for n in zone3]
        selected_z3 = self._weighted_sample_no_consecutive(zone3, zone3_weights, zone3_count)
        
        # 其餘區間分配
        remaining = 6 - zone3_count
        if remaining == 2:
            zone1_weights = [1.3 if n in cold_numbers else 1.0 for n in zone1]
            zone2_weights = [1.3 if n in cold_numbers else 1.0 for n in zone2]
            selected_others = (
                self._weighted_sample_no_consecutive(zone1, zone1_weights, 1) +
                self._weighted_sample_no_consecutive(zone2, zone2_weights, 1)
            )
        else:  # remaining == 3
            zone1_weights = [1.3 if n in cold_numbers else 1.0 for n in zone1]
            zone2_weights = [1.3 if n in cold_numbers else 1.0 for n in zone2]
            selected_others = (
                self._weighted_sample_no_consecutive(zone1, zone1_weights, 2) +
                self._weighted_sample_no_consecutive(zone2, zone2_weights, 1)
            )
        
        return selected_z3 + selected_others
    
    def _generate_cold_cluster(self, freq: Counter, cold_numbers: List[int]) -> List[int]:
        """生成冷門號集中組合 (4-5 個冷門號)"""
        if len(cold_numbers) < 5:
            # 冷門號不足，降低標準
            expected_freq = 100 * 6 / 38
            cold_numbers = [
                n for n in range(self.min_num, self.max_num + 1)
                if freq.get(n, 0) < expected_freq * 0.85
            ]
        
        if len(cold_numbers) < 4:
            # 仍不足，隨機生成
            return sorted(random.sample(range(self.min_num, self.max_num + 1), self.pick_count))
        
        # 選 4-5 個冷門號
        cold_count = min(random.choice([4, 5]), len(cold_numbers))
        weights = [1.0] * len(cold_numbers)
        selected_cold = self._weighted_sample_no_consecutive(cold_numbers, weights, cold_count)
        
        # 補足正常號
        normal_numbers = [n for n in range(self.min_num, self.max_num + 1) 
                         if n not in selected_cold]
        remaining = 6 - len(selected_cold)
        normal_weights = [1.0] * len(normal_numbers)
        selected_normal = self._weighted_sample_no_consecutive(normal_numbers, normal_weights, remaining)
        
        return selected_cold + selected_normal
    
    def _weighted_sample_no_consecutive(self, numbers: List[int], 
                                       weights: List[float], k: int) -> List[int]:
        """加權抽樣（無連號、無放回）"""
        if not numbers or k == 0:
            return []
        
        selected = []
        remaining_nums = numbers.copy()
        remaining_weights = weights.copy()
        
        for _ in range(k):
            if not remaining_nums:
                break
            
            # 過濾連號
            filtered_nums = []
            filtered_weights = []
            
            for num, weight in zip(remaining_nums, remaining_weights):
                is_consecutive = any(abs(num - s) == 1 for s in selected)
                if not is_consecutive:
                    filtered_nums.append(num)
                    filtered_weights.append(weight)
            
            if not filtered_nums:
                # 無法避免連號，使用原列表
                filtered_nums = remaining_nums
                filtered_weights = remaining_weights
            
            # 加權抽樣
            total_weight = sum(filtered_weights)
            if total_weight == 0:
                idx = random.randint(0, len(filtered_nums) - 1)
            else:
                probs = [w / total_weight for w in filtered_weights]
                import numpy as np
                idx = np.random.choice(len(filtered_nums), p=probs)
            
            selected_num = filtered_nums[idx]
            selected.append(selected_num)
            
            # 移除已選號碼
            orig_idx = remaining_nums.index(selected_num)
            remaining_nums.pop(orig_idx)
            remaining_weights.pop(orig_idx)
        
        return sorted(selected)
    
    def _analyze_features(self, combo: List[int]) -> Dict:
        """分析組合特徵"""
        odd_count = sum(1 for n in combo if n % 2 == 1)
        
        zone_counts = [0, 0, 0]
        for n in combo:
            if n <= 13:
                zone_counts[0] += 1
            elif n <= 25:
                zone_counts[1] += 1
            else:
                zone_counts[2] += 1
        
        consecutive_pairs = 0
        for i in range(len(combo) - 1):
            if combo[i+1] - combo[i] == 1:
                consecutive_pairs += 1
        
        return {
            'odd_ratio': f'{odd_count}:{6-odd_count}',
            'zone_distribution': zone_counts,
            'consecutive_pairs': consecutive_pairs,
            'sum': sum(combo)
        }
    
    def _fallback_two_bets(self) -> Dict:
        """備用雙注"""
        bet1_nums = sorted(random.sample(range(self.min_num, self.max_num + 1), self.pick_count))
        bet2_nums = sorted(random.sample(range(self.min_num, self.max_num + 1), self.pick_count))
        
        return {
            'bet1': {
                'numbers': bet1_nums,
                'special': random.randint(1, 8),
                'confidence': 0.3,
                'source': 'fallback'
            },
            'bet2': {
                'numbers': bet2_nums,
                'special': random.randint(1, 8),
                'confidence': 0.3,
                'source': 'fallback'
            },
            'strategy': 'dual_bet_fallback',
            'overlap': len(set(bet1_nums) & set(bet2_nums)),
            'coverage': len(set(bet1_nums) | set(bet2_nums))
        }


# 測試與主程式
if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    import json
    
    print("=" * 80)
    print("雙注異常策略測試 - 威力彩")
    print("=" * 80)
    
    # 載入數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    
    if not history:
        print("❌ 無法獲取歷史數據")
        sys.exit(1)
    
    strategy = DualBetAnomalyStrategy()
    
    print(f"\n使用歷史數據: {len(history)} 期")
    print(f"最新期數: {history[0]['draw']}\n")
    
    # 生成雙注預測
    result = strategy.predict_two_bets(history, rules)
    
    print("📊 雙注預測結果:")
    print("=" * 80)
    
    # Bet 1
    bet1 = result['bet1']
    print(f"\n注1 (主流模式 - {bet1['source']}):")
    print(f"  第一區: {', '.join([f'{n:02d}' for n in bet1['numbers']])}")
    print(f"  第二區: {bet1['special']:02d}")
    print(f"  信心度: {bet1['confidence']:.3f}")
    
    # Bet 2
    bet2 = result['bet2']
    print(f"\n注2 (異常模式 - {bet2['source']}):")
    print(f"  第一區: {', '.join([f'{n:02d}' for n in bet2['numbers']])}")
    print(f"  第二區: {bet2['special']:02d}")
    print(f"  信心度: {bet2['confidence']:.3f}")
    
    if 'anomaly_features' in bet2:
        features = bet2['anomaly_features']
        print(f"  異常特徵:")
        print(f"    - 奇偶比: {features['odd_ratio']}")
        print(f"    - 區間分布: Zone1={features['zone_distribution'][0]}, "
              f"Zone2={features['zone_distribution'][1]}, Zone3={features['zone_distribution'][2]}")
        print(f"    - 連號對數: {features['consecutive_pairs']}")
        print(f"    - 和值: {features['sum']}")
    
    # 覆蓋分析
    print(f"\n📈 覆蓋分析:")
    print(f"  重疊號碼: {result['overlap']} 個")
    print(f"  總覆蓋: {result['coverage']}/38 個號碼 ({result['coverage']/38*100:.1f}%)")
    
    # 保存結果
    output_file = os.path.join(project_root, 'tools', 'dual_bet_prediction.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        # 將結果轉換為可序列化格式
        output = {
            'draw_number': 'next',
            'strategy': result['strategy'],
            'bets': [
                {
                    'numbers': bet1['numbers'],
                    'special': int(bet1['special']),
                    'source': bet1['source'],
                    'confidence': float(bet1['confidence'])
                },
                {
                    'numbers': bet2['numbers'],
                    'special': int(bet2['special']),
                    'source': bet2['source'],
                    'confidence': float(bet2['confidence']),
                    'anomaly_features': bet2.get('anomaly_features', {})
                }
            ],
            'coverage_stats': {
                'overlap': result['overlap'],
                'total_coverage': result['coverage']
            }
        }
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 預測結果已保存: {output_file}")
    print("=" * 80)
