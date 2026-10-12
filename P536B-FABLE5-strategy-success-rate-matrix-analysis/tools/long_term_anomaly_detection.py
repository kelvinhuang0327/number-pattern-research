#!/usr/bin/env python3
"""
威力彩長期異常檢測 - 尋找物理偏差

基於1874期歷史數據，檢驗每個號碼是否顯著偏離期望頻率。
如果某些號碼長期顯著偏高/偏低，可能表示：
- 球的重量差異
- 搖獎機的物理偏差
- 可利用的系統性偏差

統計方法：卡方檢驗 (Chi-square test)
"""
import sys
import os
import json
import numpy as np
from collections import Counter
from scipy import stats
from typing import Dict, List

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager


class LongTermAnomalyDetector:
    """長期異常檢測器"""
    
    def __init__(self, lottery_type: str = 'POWER_LOTTO'):
        self.lottery_type = lottery_type
        self.num_range = (1, 38) if lottery_type == 'POWER_LOTTO' else (1, 49)
        self.picks_per_draw = 6
        self.special_range = (1, 8) if lottery_type == 'POWER_LOTTO' else None
    
    def analyze_long_term_bias(self, history: List[Dict]) -> Dict:
        """
        分析長期偏差
        
        Returns:
            {
                'main_numbers': {...},
                'special_numbers': {...},
                'summary': {...}
            }
        """
        print(f"分析 {len(history)} 期歷史數據...")
        
        # 分析第一區號碼
        main_analysis = self._analyze_main_numbers(history)
        
        # 分析第二區號碼（如果有）
        special_analysis = None
        if self.special_range:
            special_analysis = self._analyze_special_numbers(history)
        
        # 總結
        summary = self._generate_summary(main_analysis, special_analysis)
        
        return {
            'total_draws': len(history),
            'main_numbers': main_analysis,
            'special_numbers': special_analysis,
            'summary': summary
        }
    
    def _analyze_main_numbers(self, history: List[Dict]) -> Dict:
        """分析第一區號碼的長期分布"""
        # 統計每個號碼出現次數
        freq = Counter()
        for draw in history:
            nums = draw.get('numbers', [])
            freq.update(nums)
        
        total_draws = len(history)
        total_balls = total_draws * self.picks_per_draw
        
        # 期望頻率（每個號碼）
        num_count = self.num_range[1] - self.num_range[0] + 1
        expected_freq = total_balls / num_count
        
        # 卡方檢驗
        observed = []
        expected = []
        numbers = []
        
        for num in range(self.num_range[0], self.num_range[1] + 1):
            observed.append(freq.get(num, 0))
            expected.append(expected_freq)
            numbers.append(num)
        
        chi2_stat, p_value = stats.chisquare(observed, expected)
        
        # 分析每個號碼的顯著性
        anomalies = []
        z_scores = []
        
        std_dev = np.sqrt(expected_freq)
        
        for num, obs in zip(numbers, observed):
            z = (obs - expected_freq) / std_dev
            z_scores.append(z)
            
            # 雙尾檢驗：|z| > 2.576 (p<0.01, 99% 信賴)
            if abs(z) > 2.576:
                anomalies.append({
                    'number': num,
                    'observed': obs,
                    'expected': expected_freq,
                    'deviation': obs - expected_freq,
                    'z_score': z,
                    'p_value': 2 * (1 - stats.norm.cdf(abs(z))),
                    'direction': 'over' if z > 0 else 'under',
                    'significance': '***' if abs(z) > 3.29 else '**'
                })
        
        # 找出最高頻和最低頻
        max_idx = np.argmax(observed)
        min_idx = np.argmin(observed)
        
        return {
            'chi_square': chi2_stat,
            'p_value': p_value,
            'significant': p_value < 0.01,
            'expected_freq': expected_freq,
            'total_picks': total_balls,
            'anomalies': sorted(anomalies, key=lambda x: abs(x['z_score']), reverse=True),
            'highest': {
                'number': numbers[max_idx],
                'count': observed[max_idx],
                'z_score': z_scores[max_idx]
            },
            'lowest': {
                'number': numbers[min_idx],
                'count': observed[min_idx],
                'z_score': z_scores[min_idx]
            },
            'distribution': {
                'numbers': numbers,
                'observed': observed,
                'expected': [expected_freq] * len(numbers),
                'z_scores': z_scores
            }
        }
    
    def _analyze_special_numbers(self, history: List[Dict]) -> Dict:
        """分析第二區號碼的長期分布"""
        freq = Counter()
        for draw in history:
            special = draw.get('special')
            if special:
                freq[special] += 1
        
        total_draws = len(history)
        num_count = self.special_range[1] - self.special_range[0] + 1
        expected_freq = total_draws / num_count
        
        # 卡方檢驗
        observed = [freq.get(i, 0) for i in range(1, 9)]
        expected = [expected_freq] * num_count
        
        chi2_stat, p_value = stats.chisquare(observed, expected)
        
        # 分析每個特別號
        anomalies = []
        std_dev = np.sqrt(expected_freq)
        
        for num in range(1, 9):
            obs = freq.get(num, 0)
            z = (obs - expected_freq) / std_dev
            
            if abs(z) > 2.576:
                anomalies.append({
                    'number': num,
                    'observed': obs,
                    'expected': expected_freq,
                    'z_score': z,
                    'p_value': 2 * (1 - stats.norm.cdf(abs(z))),
                    'direction': 'over' if z > 0 else 'under'
                })
        
        return {
            'chi_square': chi2_stat,
            'p_value': p_value,
            'significant': p_value < 0.01,
            'expected_freq': expected_freq,
            'anomalies': sorted(anomalies, key=lambda x: abs(x['z_score']), reverse=True),
            'distribution': dict(freq)
        }
    
    def _generate_summary(self, main: Dict, special: Dict) -> Dict:
        """生成總結"""
        has_main_bias = main['significant']
        has_special_bias = special['significant'] if special else False
        
        main_anomaly_count = len(main['anomalies'])
        special_anomaly_count = len(special['anomalies']) if special else 0
        
        # 結論
        if has_main_bias or has_special_bias:
            conclusion = "發現顯著統計異常！可能存在物理偏差"
            recommendation = "建議利用異常號碼進行優化預測"
        elif main_anomaly_count > 0 or special_anomaly_count > 0:
            conclusion = "發現個別號碼異常，但整體分布正常"
            recommendation = "可謹慎利用異常號碼，但改善可能有限"
        else:
            conclusion = "未發現顯著異常，分布接近隨機"
            recommendation = "無可利用的系統性偏差，建議放棄預測優化"
        
        return {
            'has_bias': has_main_bias or has_special_bias,
            'main_anomaly_count': main_anomaly_count,
            'special_anomaly_count': special_anomaly_count,
            'conclusion': conclusion,
            'recommendation': recommendation
        }


def main():
    print("=" * 100)
    print("威力彩長期異常檢測 - 尋找物理偏差")
    print("=" * 100)
    
    # 載入數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not history:
        print("❌ 無法載入歷史數據")
        return
    
    detector = LongTermAnomalyDetector('POWER_LOTTO')
    
    print(f"\n載入歷史數據: {len(history)} 期")
    print(f"期數範圍: {history[-1]['draw']} ~ {history[0]['draw']}")
    print(f"總抽取球數: {len(history) * 6} 個\n")
    
    # 執行分析
    result = detector.analyze_long_term_bias(history)
    
    # 顯示結果 - 第一區
    print("\n" + "=" * 100)
    print("第一區號碼分布分析 (1-38)")
    print("=" * 100)
    
    main = result['main_numbers']
    print(f"\n整體卡方檢驗:")
    print(f"  χ² = {main['chi_square']:.2f}")
    print(f"  p-value = {main['p_value']:.6f}")
    print(f"  顯著性: {'✓ 顯著異常 (p<0.01)' if main['significant'] else '✗ 無顯著異常'}")
    print(f"\n期望頻率: {main['expected_freq']:.2f} 次/號碼")
    
    print(f"\n最高頻號碼:")
    print(f"  號碼 {main['highest']['number']:02d}: {main['highest']['count']} 次 (z={main['highest']['z_score']:.2f})")
    
    print(f"\n最低頻號碼:")
    print(f"  號碼 {main['lowest']['number']:02d}: {main['lowest']['count']} 次 (z={main['lowest']['z_score']:.2f})")
    
    if main['anomalies']:
        print(f"\n發現 {len(main['anomalies'])} 個顯著異常號碼 (|z| > 2.576, p<0.01):")
        print(f"  {'號碼':<6} {'實際':<8} {'期望':<8} {'偏差':<8} {'z-score':<10} {'方向':<6} {'顯著性'}")
        print("-" * 70)
        for anom in main['anomalies'][:10]:  # 最多顯示10個
            print(f"  {anom['number']:02d}     "
                  f"{anom['observed']:<8.0f} "
                  f"{anom['expected']:<8.2f} "
                  f"{anom['deviation']:+8.2f} "
                  f"{anom['z_score']:+9.3f} "
                  f"{anom['direction']:<6} "
                  f"{anom['significance']}")
    else:
        print("\n✓ 未發現顯著異常號碼")
    
    # 顯示結果 - 第二區
    if result['special_numbers']:
        print("\n" + "=" * 100)
        print("第二區號碼分布分析 (1-8)")
        print("=" * 100)
        
        special = result['special_numbers']
        print(f"\n整體卡方檢驗:")
        print(f"  χ² = {special['chi_square']:.2f}")
        print(f"  p-value = {special['p_value']:.6f}")
        print(f"  顯著性: {'✓ 顯著異常' if special['significant'] else '✗ 無顯著異常'}")
        
        if special['anomalies']:
            print(f"\n發現 {len(special['anomalies'])} 個顯著異常號碼:")
            for anom in special['anomalies']:
                print(f"  號碼 {anom['number']}: {anom['observed']:.0f} 次 (期望 {anom['expected']:.2f}, z={anom['z_score']:+.2f})")
        else:
            print("\n✓ 未發現顯著異常號碼")
    
    # 總結
    print("\n" + "=" * 100)
    print("總結與建議")
    print("=" * 100)
    
    summary = result['summary']
    print(f"\n結論: {summary['conclusion']}")
    print(f"建議: {summary['recommendation']}")
    
    # 保存結果
    output_file = os.path.join(project_root, 'tools', 'long_term_anomaly_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        def convert(obj):
            if isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            elif isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert(item) for item in obj]
            return obj
        
        json.dump(convert(result), f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 詳細結果已保存: {output_file}")
    print("=" * 100)


if __name__ == '__main__':
    main()
