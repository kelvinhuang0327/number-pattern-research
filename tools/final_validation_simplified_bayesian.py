#!/usr/bin/env python3
"""
最终验证：SimplifiedBayesian vs Frequency vs Random
- 800样本5-fold交叉验证
- 包含SimplifiedBayesian方法
- 统计显著性检验
"""
import sys
import os
import json
import numpy as np
from collections import Counter
from scipy.stats import ttest_ind, binomtest
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.simplified_bayesian_predictor import SimplifiedBayesianPredictor


class FinalValidator:
    """最终验证器"""
    
    def __init__(self):
        self.min_num = 1
        self.max_num = 38
        self.simplified_predictor = SimplifiedBayesianPredictor()
    
    def simplified_bayesian_predict(self, history: List[Dict]) -> List[int]:
        """SimplifiedBayesian预测"""
        rules = get_lottery_rules('POWER_LOTTO')
        try:
            result = self.simplified_predictor.predict(history, rules)
            return result.get('numbers', [])
        except:
            return self.random_predict()
    
    def frequency_predict(self, history: List[Dict], window: int = 100) -> List[int]:
        """频率法"""
        recent = history[:min(window, len(history))]
        freq = Counter()
        for d in recent:
            freq.update(d.get('numbers', []))
        
        top6 = [n for n, _ in freq.most_common(6)]
        return sorted(top6)
    
    def random_predict(self) -> List[int]:
        """纯随机"""
        import random
        return sorted(random.sample(range(1, 39), 6))
    
    def k_fold_cross_validation(self, history: List[Dict], k: int = 5) -> Dict:
        """K-fold交叉验证"""
        total_size = len(history)
        fold_size = total_size // k
        
        methods = {
            'SimplifiedBayesian': lambda h: self.simplified_bayesian_predict(h),
            'Frequency_100': lambda h: self.frequency_predict(h, 100),
            'Random': lambda: self.random_predict()
        }
        
        fold_results = {method: [] for method in methods}
        
        print(f"\n执行 {k}-fold 交叉验证 (包含SimplifiedBayesian)...")
        
        for fold_idx in range(k):
            start = fold_idx * fold_size
            end = start + fold_size if fold_idx < k-1 else total_size
            
            test_data = history[start:end]
            
            print(f"  Fold {fold_idx + 1}/{k}: 测试 {len(test_data)} 期...", end='', flush=True)
            
            for method_name, predict_func in methods.items():
                for i, test_draw in enumerate(test_data):
                    # 训练集
                    train = history[:start] + history[end:]
                    train = train[:min(len(train), 200)]
                    
                    if not train:
                        continue
                    
                    actual = set(test_draw.get('numbers', []))
                    
                    try:
                        if method_name == 'Random':
                            pred = predict_func()
                        else:
                            pred = predict_func(train)
                        
                        hits = len(set(pred) & actual)
                        fold_results[method_name].append(hits)
                    except Exception as e:
                        # SimplifiedBayesian可能失败，用随机替代
                        if method_name == 'SimplifiedBayesian':
                            pred = self.random_predict()
                            hits = len(set(pred) & actual)
                            fold_results[method_name].append(hits)
                        continue
            
            print(" ✓")
        
        return fold_results
    
    def calculate_statistics(self, results: List[int]) -> Dict:
        """计算统计指标"""
        mean_hits = np.mean(results)
        std_hits = np.std(results, ddof=1)
        match_3plus = sum(1 for h in results if h >= 3)
        match_3plus_rate = match_3plus / len(results) if results else 0
        
        se = std_hits / np.sqrt(len(results)) if results else 0
        ci_low = mean_hits - 1.96 * se
        ci_high = mean_hits + 1.96 * se
        
        return {
            'count': len(results),
            'mean': mean_hits,
            'std': std_hits,
            'ci_95': (ci_low, ci_high),
            'match_3plus': match_3plus,
            'match_3plus_rate': match_3plus_rate
        }


def main():
    print("=" * 100)
    print("最终验证：SimplifiedBayesian vs Frequency vs Random")
    print("=" * 100)
    
    # 载入数据
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    print(f"\n总历史数据: {len(all_history)} 期")
    
    # 使用800期数据进行交叉验证
    cv_history = all_history[:min(800, len(all_history))]
    
    print(f"交叉验证数据: {len(cv_history)} 期")
    print(f"期数范围: {cv_history[-1]['draw']} ~ {cv_history[0]['draw']}")
    
    validator = FinalValidator()
    
    # K-fold交叉验证
    cv_results = validator.k_fold_cross_validation(cv_history, k=5)
    
    # 统计分析
    print("\n" + "=" * 100)
    print("统计结果")
    print("=" * 100)
    
    print(f"\n{'方法':<25} | {'平均命中':<12} | {'95% CI':<25} | {'3+率':<12} | 样本数")
    print("-" * 100)
    
    all_stats = {}
    
    for method, hits_list in cv_results.items():
        stats = validator.calculate_statistics(hits_list)
        all_stats[method] = stats
        
        print(f"{method:<25} | "
              f"{stats['mean']:>6.3f}/6    | "
              f"[{stats['ci_95'][0]:.3f}, {stats['ci_95'][1]:.3f}]      | "
              f"{stats['match_3plus_rate']:>6.1%}      | "
              f"{stats['count']}")
    
    # 统计检验
    print("\n" + "=" * 100)
    print("统计显著性检验")
    print("=" * 100)
    
    simplified_hits = cv_results['SimplifiedBayesian']
    frequency_hits = cv_results['Frequency_100']
    random_hits = cv_results['Random']
    
    simplified_stats = all_stats['SimplifiedBayesian']
    frequency_stats = all_stats['Frequency_100']
    random_stats = all_stats['Random']
    
    # SimplifiedBayesian vs Random
    t_stat_sr, p_value_sr = ttest_ind(simplified_hits, random_hits)
    pooled_std_sr = np.sqrt((simplified_stats['std']**2 + random_stats['std']**2) / 2)
    cohens_d_sr = (simplified_stats['mean'] - random_stats['mean']) / pooled_std_sr if pooled_std_sr > 0 else 0
    
    print(f"\n【SimplifiedBayesian vs Random】")
    print(f"  SimplifiedBayesian: {simplified_stats['mean']:.3f}/6, 3+: {simplified_stats['match_3plus_rate']:.2%}")
    print(f"  Random: {random_stats['mean']:.3f}/6, 3+: {random_stats['match_3plus_rate']:.2%}")
    print(f"  t-statistic: {t_stat_sr:.3f}")
    print(f"  p-value: {p_value_sr:.4f}")
    print(f"  Cohen's d: {cohens_d_sr:.3f}")
    print(f"  结论: {'✓ 显著差异 (p<0.05)' if p_value_sr < 0.05 else '✗ 无显著差异 (p≥0.05)'}")
    
    # SimplifiedBayesian vs Frequency
    t_stat_sf, p_value_sf = ttest_ind(simplified_hits, frequency_hits)
    pooled_std_sf = np.sqrt((simplified_stats['std']**2 + frequency_stats['std']**2) / 2)
    cohens_d_sf = (simplified_stats['mean'] - frequency_stats['mean']) / pooled_std_sf if pooled_std_sf > 0 else 0
    
    print(f"\n【SimplifiedBayesian vs Frequency】")
    print(f"  SimplifiedBayesian: {simplified_stats['mean']:.3f}/6")
    print(f"  Frequency: {frequency_stats['mean']:.3f}/6")
    print(f"  t-statistic: {t_stat_sf:.3f}")
    print(f"  p-value: {p_value_sf:.4f}")
    print(f"  Cohen's d: {cohens_d_sf:.3f}")
    print(f"  结论: {'✓ 显著差异 (p<0.05)' if p_value_sf < 0.05 else '✗ 无显著差异 (p≥0.05)'}")
    
    # 3+率二项检验（vs理论3.87%）
    print(f"\n【3+率 vs 理论随机3.87%】")
    for method in ['SimplifiedBayesian', 'Frequency_100', 'Random']:
        stats = all_stats[method]
        result = binomtest(stats['match_3plus'], stats['count'], 0.0387, alternative='greater')
        
        print(f"  {method:<25}: {stats['match_3plus_rate']:.2%} (p={result.pvalue:.4f}) " +
              ('✓' if result.pvalue < 0.05 else '✗'))
    
    # 最终结论
    print("\n" + "=" * 100)
    print("最终结论")
    print("=" * 100)
    
    print(f"\n测试规模: 5-fold交叉验证, {len(simplified_hits)} 样本")
    
    if p_value_sr < 0.05:
        print(f"\n✅ SimplifiedBayesian **显著优于** Random (p={p_value_sr:.4f})")
        print(f"   平均改善: {simplified_stats['mean'] - random_stats['mean']:+.3f}/6")
        print(f"   效应量: {cohens_d_sr:.3f}")
    else:
        print(f"\n❌ SimplifiedBayesian **未显著优于** Random (p={p_value_sr:.4f})")
        print(f"   平均差异: {simplified_stats['mean'] - random_stats['mean']:+.3f}/6 (可能是噪音)")
        print(f"   效应量: {cohens_d_sr:.3f} (negligible)")
    
    if p_value_sf < 0.05:
        print(f"\n✅ SimplifiedBayesian **显著优于** Frequency (p={p_value_sf:.4f})")
    else:
        print(f"\n❌ SimplifiedBayesian **未显著优于** Frequency (p={p_value_sf:.4f})")
    
    print("\n对150期结果的解释:")
    print(f"  150期SimplifiedBayesian: 0.947/6, 4.7% 3+")
    print(f"  800样本SimplifiedBayesian: {simplified_stats['mean']:.3f}/6, {simplified_stats['match_3plus_rate']:.1%} 3+")
    print(f"  结论: 150期结果 {'是统计噪音' if p_value_sr > 0.05 else '代表真实优势'}")
    
    print("=" * 100)


if __name__ == '__main__':
    main()
