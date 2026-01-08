#!/usr/bin/env python3
"""
深度特徵提取器 (Deep Feature Extractor)
提取連號模式、尾數分佈、區段冷熱、號碼間距等進階特徵
"""
import sys
import os
from collections import Counter, defaultdict
from itertools import combinations

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

class DeepFeatureExtractor:
    """深度特徵提取器"""
    
    def __init__(self, min_num=1, max_num=38):
        self.min_num = min_num
        self.max_num = max_num
    
    def extract_all_features(self, history):
        """提取所有深度特徵"""
        return {
            'consecutive_patterns': self.analyze_consecutive_patterns(history),
            'tail_distribution': self.analyze_tail_distribution(history),
            'zone_heat_cycles': self.analyze_zone_heat_cycles(history),
            'number_gaps': self.analyze_number_gaps(history)
        }
    
    def analyze_consecutive_patterns(self, history, lookback=100):
        """
        分析連號模式
        
        Returns:
            {
                'consecutive_2': [(6,7), (17,18), ...],
                'consecutive_3': [(5,6,7), ...],
                'freq_2': Counter,
                'freq_3': Counter,
                'last_seen_2': {(6,7): 5, ...},  # 最後出現在幾期前
                'hot_pairs': [(6,7), ...]  # 近期高頻連號對
            }
        """
        consecutive_2 = []
        consecutive_3 = []
        last_seen_2 = {}
        
        for idx, draw in enumerate(history[:lookback]):
            nums = sorted(draw['numbers'])
            
            # 檢測連續2號
            for i in range(len(nums)-1):
                if nums[i+1] - nums[i] == 1:
                    pair = (nums[i], nums[i+1])
                    consecutive_2.append(pair)
                    if pair not in last_seen_2:
                        last_seen_2[pair] = idx
            
            # 檢測連續3號
            for i in range(len(nums)-2):
                if nums[i+1] - nums[i] == 1 and nums[i+2] - nums[i+1] == 1:
                    triple = (nums[i], nums[i+1], nums[i+2])
                    consecutive_3.append(triple)
        
        freq_2 = Counter(consecutive_2)
        freq_3 = Counter(consecutive_3)
        
        # 找出近期高頻連號對（最近20期出現2次以上）
        recent_pairs = [p for p in consecutive_2[:20*6]]  # 假設每期平均可能有6個連號對
        hot_pairs = [pair for pair, count in Counter(recent_pairs).items() if count >= 2]
        
        return {
            'freq_2': freq_2,
            'freq_3': freq_3,
            'last_seen_2': last_seen_2,
            'hot_pairs': hot_pairs,
            'total_consecutive_2': len(consecutive_2),
            'total_consecutive_3': len(consecutive_3)
        }
    
    def analyze_tail_distribution(self, history, lookback=50):
        """
        分析尾數分佈
        
        Returns:
            {
                'tail_freq': {0: 45, 1: 52, ...},  # 各尾數出現次數
                'tail_balance_score': 0.85,  # 平衡度評分 (0-1)
                'missing_tails': [3, 7],  # 近期缺失的尾數
                'hot_tails': [1, 5, 9]  # 近期高頻尾數
            }
        """
        tail_counter = Counter()
        recent_tails = []
        
        for draw in history[:lookback]:
            tails = [n % 10 for n in draw['numbers']]
            tail_counter.update(tails)
            recent_tails.extend(tails)
        
        # 計算平衡度（標準差越小越平衡）
        tail_counts = [tail_counter.get(i, 0) for i in range(10)]
        avg = sum(tail_counts) / 10
        variance = sum((c - avg)**2 for c in tail_counts) / 10
        std_dev = variance ** 0.5
        balance_score = max(0, 1 - (std_dev / avg)) if avg > 0 else 0
        
        # 找出缺失和高頻尾數（最近10期）
        recent_10_tails = Counter(recent_tails[:60])  # 10期 x 6號碼
        all_tails = set(range(10))
        present_tails = set(recent_10_tails.keys())
        missing_tails = list(all_tails - present_tails)
        hot_tails = [t for t, c in recent_10_tails.most_common(3)]
        
        return {
            'tail_freq': dict(tail_counter),
            'tail_balance_score': balance_score,
            'missing_tails': missing_tails,
            'hot_tails': hot_tails
        }
    
    def analyze_zone_heat_cycles(self, history, lookback=50):
        """
        分析區段冷熱交替
        
        Zones: [1-10], [11-20], [21-30], [31-38]
        
        Returns:
            {
                'zone_density': {1: 0.35, 2: 0.25, 3: 0.25, 4: 0.15},
                'zone_trend': {1: 'heating', 2: 'cooling', ...},
                'cold_zones': [4],  # 即將反彈的冷區
                'hot_zones': [1]  # 當前熱區
            }
        """
        zones = {
            1: range(1, 11),
            2: range(11, 21),
            3: range(21, 31),
            4: range(31, 39)
        }
        
        zone_counts = {1: [], 2: [], 3: [], 4: []}
        
        for draw in history[:lookback]:
            period_counts = {1: 0, 2: 0, 3: 0, 4: 0}
            for num in draw['numbers']:
                for zone_id, zone_range in zones.items():
                    if num in zone_range:
                        period_counts[zone_id] += 1
            
            for zone_id in range(1, 5):
                zone_counts[zone_id].append(period_counts[zone_id])
        
        # 計算密度（平均每期出現數）
        zone_density = {
            z: sum(counts) / len(counts) if counts else 0 
            for z, counts in zone_counts.items()
        }
        
        # 判斷趨勢（比較最近10期 vs 前40期）
        zone_trend = {}
        for zone_id, counts in zone_counts.items():
            recent_avg = sum(counts[:10]) / 10 if len(counts) >= 10 else 0
            past_avg = sum(counts[10:]) / 40 if len(counts) >= 50 else 0
            
            if recent_avg > past_avg * 1.2:
                zone_trend[zone_id] = 'heating'
            elif recent_avg < past_avg * 0.8:
                zone_trend[zone_id] = 'cooling'
            else:
                zone_trend[zone_id] = 'stable'
        
        # 找出冷區（連續5期低密度）
        cold_zones = []
        for zone_id, counts in zone_counts.items():
            if len(counts) >= 5 and sum(counts[:5]) / 5 < 0.8:
                cold_zones.append(zone_id)
        
        # 找出熱區
        hot_zones = [z for z, d in sorted(zone_density.items(), key=lambda x: -x[1])[:2]]
        
        return {
            'zone_density': zone_density,
            'zone_trend': zone_trend,
            'cold_zones': cold_zones,
            'hot_zones': hot_zones
        }
    
    def analyze_number_gaps(self, history, lookback=50):
        """
        分析號碼間距
        
        Returns:
            {
                'avg_gap': 5.2,
                'std_gap': 2.1,
                'max_gap': 12,
                'min_gap': 1,
                'ideal_gap_range': (3, 8)
            }
        """
        all_gaps = []
        
        for draw in history[:lookback]:
            nums = sorted(draw['numbers'])
            gaps = [nums[i+1] - nums[i] for i in range(len(nums)-1)]
            all_gaps.extend(gaps)
        
        avg_gap = sum(all_gaps) / len(all_gaps) if all_gaps else 0
        variance = sum((g - avg_gap)**2 for g in all_gaps) / len(all_gaps) if all_gaps else 0
        std_gap = variance ** 0.5
        
        return {
            'avg_gap': avg_gap,
            'std_gap': std_gap,
            'max_gap': max(all_gaps) if all_gaps else 0,
            'min_gap': min(all_gaps) if all_gaps else 0,
            'ideal_gap_range': (max(1, int(avg_gap - std_gap)), int(avg_gap + std_gap))
        }

if __name__ == '__main__':
    from database import DatabaseManager
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    extractor = DeepFeatureExtractor(min_num=1, max_num=38)
    features = extractor.extract_all_features(history)
    
    print("=" * 60)
    print("🔬 深度特徵分析報告")
    print("=" * 60)
    
    print("\n📊 連號模式:")
    cons = features['consecutive_patterns']
    print(f"  連續2號總數: {cons['total_consecutive_2']}")
    print(f"  連續3號總數: {cons['total_consecutive_3']}")
    print(f"  近期高頻連號對: {cons['hot_pairs'][:5]}")
    
    print("\n🎯 尾數分佈:")
    tail = features['tail_distribution']
    print(f"  平衡度評分: {tail['tail_balance_score']:.2f}")
    print(f"  缺失尾數: {tail['missing_tails']}")
    print(f"  高頻尾數: {tail['hot_tails']}")
    
    print("\n🌡️ 區段冷熱:")
    zone = features['zone_heat_cycles']
    print(f"  區段密度: {zone['zone_density']}")
    print(f"  冷區（即將反彈）: {zone['cold_zones']}")
    print(f"  熱區: {zone['hot_zones']}")
    
    print("\n📏 號碼間距:")
    gap = features['number_gaps']
    print(f"  平均間距: {gap['avg_gap']:.2f}")
    print(f"  理想間距範圍: {gap['ideal_gap_range']}")
