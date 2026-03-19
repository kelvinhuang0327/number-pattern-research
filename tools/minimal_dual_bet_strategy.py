#!/usr/bin/env python3
"""
威力彩極簡雙注策略 - Coverage優於Accuracy

設計原則:
1. 極簡方法 - 僅用頻率統計，無複雜算法
2. 最大化覆蓋 - 兩注重疊<=1個號碼
3. 區間平衡 - 每注覆蓋低中高三區
4. 統計驗證 - binomial test + 分別統計兩注表現
"""
import sys
import os
import json
from collections import Counter
from typing import List, Dict, Tuple
from scipy.stats import binomtest

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules


class MinimalDualBetStrategy:
    """極簡雙注策略"""
    
    def __init__(self):
        self.min_num = 1
        self.max_num = 38
        self.pick_count = 6
    
    def predict_dual_bets(self, history: List[Dict]) -> Dict:
        """
        生成雙注預測
        
        Returns:
            {
                'bet1': {'numbers': [...], 'special': int},
                'bet2': {'numbers': [...], 'special': int},
                'coverage': {...}
            }
        """
        # 計算頻率 (近100期)
        recent = history[:min(100, len(history))]
        freq = Counter()
        for d in recent:
            freq.update(d.get('numbers', []))
        
        # 按頻率排序所有號碼
        sorted_nums = sorted(range(1, 39), key=lambda x: freq.get(x, 0), reverse=True)
        
        # 注1: 高頻號 + 區間平衡
        bet1_nums = self._select_with_zone_balance(sorted_nums[:20], target=6)
        
        # 注2: 排除注1，從剩餘號碼中選次高頻 + 區間平衡
        remaining = [n for n in sorted_nums if n not in bet1_nums]
        bet2_nums = self._select_with_zone_balance(remaining[:20], target=6)
        
        # 第二區: 高頻特別號
        special_freq = Counter()
        for d in history[:min(100, len(history))]:
            s = d.get('special')
            if s:
                special_freq[s] += 1
        
        top_specials = [s for s, _ in special_freq.most_common(2)]
        bet1_special = top_specials[0] if top_specials else 2
        bet2_special = top_specials[1] if len(top_specials) > 1 else (bet1_special % 8) + 1
        
        # 確保第二區不同
        if bet2_special == bet1_special:
            bet2_special = (bet1_special % 8) + 1
        
        # 計算覆蓋
        overlap = len(set(bet1_nums) & set(bet2_nums))
        total_coverage = len(set(bet1_nums) | set(bet2_nums))
        
        return {
            'bet1': {
                'numbers': sorted(bet1_nums),
                'special': bet1_special,
                'method': 'Frequency-Top'
            },
            'bet2': {
                'numbers': sorted(bet2_nums),
                'special': bet2_special,
                'method': 'Frequency-Secondary'
            },
            'coverage': {
                'overlap': overlap,
                'total_numbers': total_coverage,
                'coverage_rate': total_coverage / 38,
                'special_coverage': 2 if bet1_special != bet2_special else 1
            }
        }
    
    def _select_with_zone_balance(self, candidates: List[int], target: int = 6) -> List[int]:
        """
        從候選中選擇號碼，確保區間平衡
        
        區間: 低[1-13], 中[14-25], 高[26-38]
        目標分配: 每區2個
        """
        zones = {
            'low': (1, 13),
            'mid': (14, 25),
            'high': (26, 38)
        }
        
        selected = []
        
        # 每區選2個
        for zone_name, (start, end) in zones.items():
            zone_candidates = [n for n in candidates if start <= n <= end and n not in selected]
            picked = zone_candidates[:2]
            selected.extend(picked)
        
        # 如果不足6個，從剩餘候選補充
        while len(selected) < target and candidates:
            remaining = [c for c in candidates if c not in selected]
            if not remaining:
                break
            selected.append(remaining[0])
        
        return selected[:target]


def backtest_dual_strategy(test_size: int = 150) -> Dict:
    """
    150期回測 - 正確的統計方法
    
    分別計算:
    1. 單注命中率 (bet1, bet2各自)
    2. 雙注組合命中率 (至少一注命中)
    3. 統計顯著性檢驗
    """
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    all_history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if len(all_history) < test_size + 20:
        return {'error': f'數據不足，需要至少{test_size + 20}期'}
    
    history = all_history[:test_size + 20]
    strategy = MinimalDualBetStrategy()
    
    # 統計容器
    bet1_hits = []  # 每期bet1的命中數
    bet2_hits = []  # 每期bet2的命中數
    bet1_special_hits = 0
    bet2_special_hits = 0
    dual_best_hits = []  # 每期兩注中較好的命中數
    
    bet1_3plus = 0
    bet2_3plus = 0
    dual_3plus = 0  # 至少一注3+
    
    results_detail = []
    
    print(f"回測中...", end='', flush=True)
    
    for i in range(test_size):
        if (i + 1) % 30 == 0:
            print(f" {i+1}", end='', flush=True)
        
        train = history[i+1:]
        test = history[i]
        
        actual_nums = set(test.get('numbers', []))
        actual_special = test.get('special')
        
        try:
            pred = strategy.predict_dual_bets(train)
            
            # 計算bet1命中
            bet1_match = len(set(pred['bet1']['numbers']) & actual_nums)
            bet1_special_match = (pred['bet1']['special'] == actual_special)
            
            # 計算bet2命中
            bet2_match = len(set(pred['bet2']['numbers']) & actual_nums)
            bet2_special_match = (pred['bet2']['special'] == actual_special)
            
            # 記錄
            bet1_hits.append(bet1_match)
            bet2_hits.append(bet2_match)
            
            if bet1_special_match:
                bet1_special_hits += 1
            if bet2_special_match:
                bet2_special_hits += 1
            
            # 雙注最佳命中
            best_match = max(bet1_match, bet2_match)
            dual_best_hits.append(best_match)
            
            # 3+命中統計
            if bet1_match >= 3:
                bet1_3plus += 1
            if bet2_match >= 3:
                bet2_3plus += 1
            if best_match >= 3:
                dual_3plus += 1
            
            results_detail.append({
                'draw': test.get('draw'),
                'bet1_match': bet1_match,
                'bet2_match': bet2_match,
                'best_match': best_match
            })
            
        except Exception as e:
            print(f"\n錯誤: {e}")
            continue
    
    print(" ✓")
    
    # 統計分析
    import numpy as np
    
    total = len(bet1_hits)
    
    # Bet1統計
    bet1_mean = np.mean(bet1_hits)
    bet1_std = np.std(bet1_hits, ddof=1)
    bet1_3plus_rate = bet1_3plus / total
    bet1_special_rate = bet1_special_hits / total
    
    # Bet2統計
    bet2_mean = np.mean(bet2_hits)
    bet2_std = np.std(bet2_hits, ddof=1)
    bet2_3plus_rate = bet2_3plus / total
    bet2_special_rate = bet2_special_hits / total
    
    # 雙注統計
    dual_mean = np.mean(dual_best_hits)
    dual_3plus_rate = dual_3plus / total
    
    # 二項檢驗 (第二區)
    bet1_binom = binomtest(bet1_special_hits, total, 0.125, alternative='greater')
    bet2_binom = binomtest(bet2_special_hits, total, 0.125, alternative='greater')
    
    return {
        'test_size': total,
        'bet1': {
            'mean_hits': bet1_mean,
            'std': bet1_std,
            '3plus_rate': bet1_3plus_rate,
            '3plus_count': bet1_3plus,
            'special_rate': bet1_special_rate,
            'special_pvalue': bet1_binom.pvalue
        },
        'bet2': {
            'mean_hits': bet2_mean,
            'std': bet2_std,
            '3plus_rate': bet2_3plus_rate,
            '3plus_count': bet2_3plus,
            'special_rate': bet2_special_rate,
            'special_pvalue': bet2_binom.pvalue
        },
        'dual': {
            'mean_best_hits': dual_mean,
            '3plus_rate': dual_3plus_rate,
            '3plus_count': dual_3plus,
            'description': '至少一注達到該命中數'
        },
        'results_detail': results_detail[:10]  # 僅保存前10筆樣本
    }


def main():
    print("=" * 80)
    print("威力彩極簡雙注策略 - Coverage優於Accuracy")
    print("=" * 80)
    
    # 載入數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws(lottery_type='POWER_LOTTO')
    
    if not history:
        print("❌ 無法載入歷史數據")
        return
    
    strategy = MinimalDualBetStrategy()
    
    # 生成預測
    print(f"\n使用歷史數據: {len(history)} 期")
    print(f"最新期數: {history[0]['draw']}\n")
    
    prediction = strategy.predict_dual_bets(history)
    
    print("🎯 雙注預測")
    print("-" * 80)
    
    for bet_name in ['bet1', 'bet2']:
        bet = prediction[bet_name]
        nums_str = ', '.join([f'{n:02d}' for n in bet['numbers']])
        print(f"\n{bet_name.upper()} ({bet['method']}):")
        print(f"  第一區: {nums_str}")
        print(f"  第二區: {bet['special']:02d}")
    
    print("\n📊 覆蓋分析")
    print("-" * 80)
    cov = prediction['coverage']
    print(f"  號碼重疊: {cov['overlap']} 個")
    print(f"  總覆蓋: {cov['total_numbers']}/38 ({cov['coverage_rate']:.1%})")
    print(f"  第二區覆蓋: {cov['special_coverage']}/8")
    
    # 回測驗證
    print("\n" + "=" * 80)
    print("📈 150期回測驗證 (統計嚴謹版)")
    print("=" * 80 + "\n")
    
    backtest = backtest_dual_strategy(150)
    
    if 'error' in backtest:
        print(f"❌ {backtest['error']}")
        return
    
    # 顯示結果
    print(f"\n測試期數: {backtest['test_size']}\n")
    
    print("【單注表現 - Bet1】")
    print(f"  平均命中: {backtest['bet1']['mean_hits']:.3f}/6")
    print(f"  3+命中率: {backtest['bet1']['3plus_rate']:.1%} ({backtest['bet1']['3plus_count']}/{backtest['test_size']})")
    print(f"  第二區命中率: {backtest['bet1']['special_rate']:.1%}")
    print(f"  第二區p-value: {backtest['bet1']['special_pvalue']:.4f} {'✓' if backtest['bet1']['special_pvalue'] < 0.05 else '✗'}")
    
    print("\n【單注表現 - Bet2】")
    print(f"  平均命中: {backtest['bet2']['mean_hits']:.3f}/6")
    print(f"  3+命中率: {backtest['bet2']['3plus_rate']:.1%} ({backtest['bet2']['3plus_count']}/{backtest['test_size']})")
    print(f"  第二區命中率: {backtest['bet2']['special_rate']:.1%}")
    print(f"  第二區p-value: {backtest['bet2']['special_pvalue']:.4f} {'✓' if backtest['bet2']['special_pvalue'] < 0.05 else '✗'}")
    
    print("\n【雙注組合 - 至少一注】")
    print(f"  最佳平均命中: {backtest['dual']['mean_best_hits']:.3f}/6")
    print(f"  至少一注3+率: {backtest['dual']['3plus_rate']:.1%} ({backtest['dual']['3plus_count']}/{backtest['test_size']})")
    
    # 對比隨機
    print("\n【對比分析】")
    random_3plus = 0.027  # 假設隨機單注3+率約2.7% (基於之前測試)
    random_dual = 1 - (1 - random_3plus) ** 2  # 兩注至少一中
    
    print(f"  隨機單注3+率 (估計): ~{random_3plus:.1%}")
    print(f"  隨機雙注至少一中 (估計): ~{random_dual:.1%}")
    print(f"  實際雙注至少一中: {backtest['dual']['3plus_rate']:.1%}")
    print(f"  改善: {(backtest['dual']['3plus_rate'] - random_dual) * 100:+.1f} percentage points")
    
    # 保存結果
    output_file = os.path.join(project_root, 'tools', 'minimal_dual_bet_results.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        # Convert numpy types
        def convert(obj):
            import numpy as np
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
        
        json.dump(convert(backtest), f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 詳細結果已保存: {output_file}")
    print("=" * 80)


if __name__ == '__main__':
    main()
