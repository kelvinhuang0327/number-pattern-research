#!/usr/bin/env python3
"""
擴展驗證：頻率法 vs 其他方法
- 測試最大可用期數 (目標500+)
- K-fold 交叉驗證
- 統計顯著性檢驗
- 多方法對比
"""
import sys
import os
import json
import numpy as np
from collections import Counter
from scipy.stats import binomtest, ttest_ind
from typing import List, Dict, Tuple

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules


class ExtendedValidator:
    """擴展驗證器"""
    
    def __init__(self):
        self.min_num = 1
        self.max_num = 38
        self.pick_count = 6
        
    def frequency_predict(self, history: List[Dict], window: int = 100) -> List[int]:
        """簡單頻率法"""
        recent = history[:min(window, len(history))]
        freq = Counter()
        for d in recent:
            freq.update(d.get('numbers', []))
        
        # 選前6高頻
        top6 = [n for n, _ in freq.most_common(6)]
        return sorted(top6)
    
    def frequency_secondary_predict(self, history: List[Dict], exclude: List[int], window: int = 100) -> List[int]:
        """次高頻法（排除已選）"""
        recent = history[:min(window, len(history))]
        freq = Counter()
        for d in recent:
            freq.update(d.get('numbers', []))
        
        # 排除已選號碼
        candidates = [(n, c) for n, c in freq.items() if n not in exclude]
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return sorted([n for n, _ in candidates[:6]])
    
    def random_predict(self) -> List[int]:
        """純隨機"""
        import random
        return sorted(random.sample(range(1, 39), 6))
    
    def backtest_method(self, method_name: str, predict_func, history: List[Dict], 
                       test_size: int) -> List[Dict]:
        """回測單一方法"""
        results = []
        
        for i in range(test_size):
            train = history[i+1:]
            test = history[i]
            
            actual = set(test.get('numbers', []))
            
            try:
                if method_name == 'Random':
                    pred = predict_func()
                elif 'Secondary' in method_name:
                    # 次高頻需要先選Frequency
                    freq_pred = self.frequency_predict(train)
                    pred = predict_func(train, freq_pred)
                else:
                    pred = predict_func(train)
                
                hits = len(set(pred) & actual)
                results.append({
                    'draw': test.get('draw'),
                    'hits': hits,
                    'match_3plus': hits >= 3
                })
            except Exception as e:
                continue
        
        return results
    
    def k_fold_cross_validation(self, history: List[Dict], k: int = 5) -> Dict:
        """K-fold 交叉驗證"""
        total_size = len(history)
        fold_size = total_size // k
        
        methods = {
            'Frequency_100': lambda h: self.frequency_predict(h, 100),
            'Frequency_50': lambda h: self.frequency_predict(h, 50),
            'Frequency_200': lambda h: self.frequency_predict(h, 200),
            'Frequency_Secondary': lambda h, e: self.frequency_secondary_predict(h, e, 100),
            'Random': lambda: self.random_predict()
        }
        
        fold_results = {method: [] for method in methods}
        
        print(f"\n執行 {k}-fold 交叉驗證...")
        
        for fold_idx in range(k):
            start = fold_idx * fold_size
            end = start + fold_size if fold_idx < k-1 else total_size
            
            test_data = history[start:end]
            
            print(f"  Fold {fold_idx + 1}/{k}: 測試 {len(test_data)} 期...", end='', flush=True)
            
            for method_name, predict_func in methods.items():
                for i, test_draw in enumerate(test_data):
                    # 訓練集：排除測試集
                    train = history[:start] + history[end:]
                    train = train[:min(len(train), 200)]  # 限制訓練集大小
                    
                    if not train:
                        continue
                    
                    actual = set(test_draw.get('numbers', []))
                    
                    try:
                        if method_name == 'Random':
                            pred = predict_func()
                        elif 'Secondary' in method_name:
                            freq_pred = self.frequency_predict(train)
                            pred = predict_func(train, freq_pred)
                        else:
                            pred = predict_func(train)
                        
                        hits = len(set(pred) & actual)
                        fold_results[method_name].append(hits)
                    except:
                        continue
            
            print(" ✓")
        
        return fold_results
    
    def calculate_statistics(self, results: List[int]) -> Dict:
        """計算統計指標"""
        mean_hits = np.mean(results)
        std_hits = np.std(results, ddof=1)
        match_3plus = sum(1 for h in results if h >= 3)
        match_3plus_rate = match_3plus / len(results) if results else 0
        
        # 95% CI
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
    print("擴展驗證：頻率法 vs 其他方法")
    print("=" * 100)
    
    # 載入數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not all_history:
        print("❌ 無法載入歷史數據")
        return
    
    print(f"\n總歷史數據: {len(all_history)} 期")
    print(f"期數範圍: {all_history[-1]['draw']} ~ {all_history[0]['draw']}")
    
    # 決定測試規模
    max_test = min(500, len(all_history) - 50)
    history = all_history[:max_test + 50]
    
    print(f"\n測試規模: {max_test} 期")
    print(f"測試範圍: {history[max_test-1]['draw']} ~ {history[0]['draw']}")
    
    validator = ExtendedValidator()
    
    # === 1. 長期回測 ===
    print("\n" + "=" * 100)
    print(f"1. 長期回測 ({max_test}期)")
    print("=" * 100)
    
    methods = {
        'Frequency_100': lambda h: validator.frequency_predict(h, 100),
        'Frequency_50': lambda h: validator.frequency_predict(h, 50),
        'Frequency_200': lambda h: validator.frequency_predict(h, 200),
        'Frequency_Secondary': lambda h, e: validator.frequency_secondary_predict(h, e, 100),
    }
    
    long_term_results = {}
    
    for method_name, predict_func in methods.items():
        print(f"\n回測 {method_name}...", end='', flush=True)
        results = validator.backtest_method(method_name, predict_func, history, max_test)
        long_term_results[method_name] = results
        
        hits_list = [r['hits'] for r in results]
        stats = validator.calculate_statistics(hits_list)
        
        print(f" ✓")
        print(f"  平均: {stats['mean']:.3f}/6, 3+: {stats['match_3plus_rate']:.1%} ({stats['match_3plus']}/{stats['count']})")
    
    # === 2. K-fold 交叉驗證 ===
    print("\n" + "=" * 100)
    print("2. K-fold 交叉驗證 (k=5)")
    print("=" * 100)
    
    # 使用更多數據進行交叉驗證
    cv_history = all_history[:min(800, len(all_history))]
    cv_results = validator.k_fold_cross_validation(cv_history, k=5)
    
    # === 3. 統計分析 ===
    print("\n" + "=" * 100)
    print("3. 統計分析與顯著性檢驗")
    print("=" * 100)
    
    print(f"\n{'方法':<25} | {'平均命中':<12} | {'95% CI':<25} | {'3+率':<12} | 樣本數")
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
    
    # 統計檢驗：Frequency vs Random
    print("\n" + "=" * 100)
    print("4. 統計顯著性檢驗")
    print("=" * 100)
    
    # 找出最佳Frequency方法
    freq_methods = {k: v for k, v in all_stats.items() if k.startswith('Frequency')}
    best_freq_method = max(freq_methods.items(), key=lambda x: x[1]['mean'])
    best_freq_name = best_freq_method[0]
    best_freq_stats = best_freq_method[1]
    
    random_stats = all_stats.get('Random', {})
    
    if random_stats:
        # t-test
        freq_hits = cv_results[best_freq_name]
        random_hits = cv_results['Random']
        
        t_stat, p_value = ttest_ind(freq_hits, random_hits)
        
        print(f"\n最佳頻率法: {best_freq_name}")
        print(f"  平均命中: {best_freq_stats['mean']:.3f}/6")
        print(f"  95% CI: [{best_freq_stats['ci_95'][0]:.3f}, {best_freq_stats['ci_95'][1]:.3f}]")
        print(f"  3+率: {best_freq_stats['match_3plus_rate']:.2%}")
        
        print(f"\n隨機法:")
        print(f"  平均命中: {random_stats['mean']:.3f}/6")
        print(f"  95% CI: [{random_stats['ci_95'][0]:.3f}, {random_stats['ci_95'][1]:.3f}]")
        print(f"  3+率: {random_stats['match_3plus_rate']:.2%}")
        
        print(f"\nt-test 結果:")
        print(f"  t-statistic: {t_stat:.3f}")
        print(f"  p-value: {p_value:.4f}")
        print(f"  顯著性: {'✓ 顯著差異 (p<0.05)' if p_value < 0.05 else '✗ 無顯著差異 (p≥0.05)'}")
        
        # 效應量
        pooled_std = np.sqrt((best_freq_stats['std']**2 + random_stats['std']**2) / 2)
        cohens_d = (best_freq_stats['mean'] - random_stats['mean']) / pooled_std if pooled_std > 0 else 0
        print(f"  Cohen's d: {cohens_d:.3f} ({'negligible' if abs(cohens_d) < 0.2 else 'small' if abs(cohens_d) < 0.5 else 'medium'})")
    
    # 3+率二項檢驗
    print(f"\n3+率 vs 理論隨機 (3.87%):")
    for method in ['Frequency_100', 'Frequency_Secondary', 'Random']:
        if method in all_stats:
            stats = all_stats[method]
            result = binomtest(stats['match_3plus'], stats['count'], 0.0387, alternative='greater')
            
            print(f"  {method:<25}: {stats['match_3plus_rate']:.2%} (p={result.pvalue:.4f}) " +
                  ('✓' if result.pvalue < 0.05 else '✗'))
    
    # === 總結 ===
    print("\n" + "=" * 100)
    print("5. 總結")
    print("=" * 100)
    
    print(f"\n測試規模:")
    print(f"  - 長期回測: {max_test} 期")
    print(f"  - 交叉驗證: 5-fold, ~{cv_results[best_freq_name].__len__()} 樣本")
    
    print(f"\n最佳方法: {best_freq_name}")
    print(f"  - 平均命中: {best_freq_stats['mean']:.3f}/6")
    print(f"  - 3+命中率: {best_freq_stats['match_3plus_rate']:.2%}")
    print(f"  - vs Random: p={p_value:.4f} {'(顯著)' if p_value < 0.05 else '(不顯著)'}")
    
    if p_value < 0.05:
        print(f"\n✅ 結論: 頻率法**顯著優於**隨機 (p<0.05)")
    else:
        print(f"\n⚠️ 結論: 頻率法**未顯著優於**隨機 (p≥0.05)")
        print(f"   差異可能只是統計噪音")
    
    # 保存結果
    output = {
        'test_size': max_test,
        'cv_folds': 5,
        'methods': {k: validator.calculate_statistics(cv_results[k]) for k in cv_results},
        'best_method': best_freq_name,
        'statistical_test': {
            't_statistic': float(t_stat) if random_stats else None,
            'p_value': float(p_value) if random_stats else None,
            'cohens_d': float(cohens_d) if random_stats else None,
            'significant': p_value < 0.05 if random_stats else False
        }
    }
    
    output_file = os.path.join(project_root, 'tools', 'extended_validation_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        def convert(obj):
            if isinstance(obj, (np.integer, np.int64)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64)):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert(item) for item in obj]
            return obj
        
        json.dump(convert(output), f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 詳細結果已保存: {output_file}")
    print("=" * 100)


if __name__ == '__main__':
    main()
