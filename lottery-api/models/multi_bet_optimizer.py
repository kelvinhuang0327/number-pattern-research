"""
多注覆蓋優化器 - 策略7

核心理念：
1. 單注預測準確率受限於彩票隨機性 (~4-5%)
2. 多注組合可以通過覆蓋更多號碼空間提高整體中獎率
3. 關鍵是生成足夠多樣化且互補的注組

設計原則：
1. 最大化號碼覆蓋率 - 多注組合應覆蓋更多不同號碼
2. 最小化重疊 - 減少注與注之間的重複號碼
3. 平衡策略多樣性 - 每注來自不同預測方法
4. 約束條件平衡 - 確保每注都符合統計規律

目標：6注組合達到 15%+ 中獎率 (至少1注中3個以上)
"""

import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set
from itertools import combinations
import random


class MultiBetOptimizer:
    """多注覆蓋優化器"""

    def __init__(self):
        self.name = "MultiBetOptimizer"
        self._load_strategies()

    def _load_strategies(self):
        """載入策略"""
        from .unified_predictor import prediction_engine
        from .enhanced_predictor import EnhancedPredictor

        self.enhanced = EnhancedPredictor()
        self.engine = prediction_engine

        # 定義策略池，按多樣性分組
        self.strategy_groups = {
            'frequency_based': [
                ('hot_cold_mix', lambda h, r: self.engine.hot_cold_mix_predict(h, r), 100),
                ('trend_predict', lambda h, r: self.engine.trend_predict(h, r), 200),
            ],
            'statistical': [
                ('zone_balance', lambda h, r: self.engine.zone_balance_predict(h, r), 500),
                ('sum_range', lambda h, r: self.engine.sum_range_predict(h, r), 100),
                ('odd_even', lambda h, r: self.engine.odd_even_balance_predict(h, r), 200),
            ],
            'probabilistic': [
                ('bayesian', lambda h, r: self.engine.bayesian_predict(h, r), 300),
                ('monte_carlo', lambda h, r: self.engine.monte_carlo_predict(h, r), 200),
            ],
            'pattern_based': [
                ('cold_comeback', lambda h, r: self.enhanced.cold_number_comeback_predict(h, r), 100),
                ('consecutive', lambda h, r: self.enhanced.consecutive_friendly_predict(h, r), 100),
            ],
            'ensemble': [
                ('ensemble', lambda h, r: self.engine.ensemble_predict(h, r), 200),
                ('constrained', lambda h, r: self.enhanced.constrained_predict(h, r), 100),
            ]
        }

    def generate_diversified_bets(self, draws: List[Dict], lottery_rules: Dict,
                                  num_bets: int = 6) -> Dict:
        """
        生成多樣化的多注組合

        Args:
            draws: 歷史數據
            lottery_rules: 彩票規則
            num_bets: 生成注數

        Returns:
            多注預測結果
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 收集所有策略的預測結果
        all_predictions = {}
        for group_name, strategies in self.strategy_groups.items():
            for name, func, window in strategies:
                try:
                    history = draws[:window]
                    result = func(history, lottery_rules)
                    all_predictions[name] = {
                        'numbers': set(result['numbers']),
                        'group': group_name,
                        'confidence': result.get('confidence', 0.5)
                    }
                except Exception as e:
                    continue

        # 計算號碼綜合分數
        number_scores = self._calculate_number_scores(all_predictions, min_num, max_num)

        # 生成多注組合
        bets = []
        used_combos = set()

        # 策略1: 每個策略組選一注 (保證多樣性)
        for group_name, strategies in self.strategy_groups.items():
            if len(bets) >= num_bets:
                break

            for name, _, _ in strategies:
                if name in all_predictions:
                    bet = sorted(all_predictions[name]['numbers'])
                    if tuple(bet) not in used_combos:
                        bets.append({
                            'numbers': bet,
                            'source': name,
                            'group': group_name
                        })
                        used_combos.add(tuple(bet))
                        break

        # 策略2: 高分號碼變異組合
        top_numbers = sorted(number_scores.keys(), key=lambda x: -number_scores[x])[:15]

        while len(bets) < num_bets:
            # 生成新組合，最小化與現有注的重疊
            best_combo = None
            best_diversity_score = -1

            for _ in range(100):  # 嘗試100次找最佳組合
                # 加權隨機選擇
                probs = np.array([number_scores[n] for n in top_numbers])
                probs = probs / probs.sum()

                try:
                    candidate = np.random.choice(top_numbers, size=pick_count, replace=False, p=probs)
                    candidate = tuple(sorted(candidate.tolist()))

                    if candidate in used_combos:
                        continue

                    # 計算多樣性分數 (與現有注的差異度)
                    diversity = self._calculate_diversity(candidate, [b['numbers'] for b in bets])

                    if diversity > best_diversity_score:
                        best_diversity_score = diversity
                        best_combo = candidate
                except:
                    continue

            if best_combo:
                bets.append({
                    'numbers': list(best_combo),
                    'source': 'diversity_optimized',
                    'diversity_score': best_diversity_score
                })
                used_combos.add(best_combo)
            else:
                # 備用：隨機生成
                remaining = list(set(range(min_num, max_num + 1)) -
                               set(n for b in bets for n in b['numbers']))
                if len(remaining) >= pick_count:
                    bet = sorted(random.sample(remaining, pick_count))
                else:
                    bet = sorted(random.sample(range(min_num, max_num + 1), pick_count))
                bets.append({
                    'numbers': bet,
                    'source': 'random_fill'
                })
                used_combos.add(tuple(bet))

        # 計算覆蓋統計
        all_covered = set()
        for bet in bets:
            all_covered.update(bet['numbers'])

        coverage = len(all_covered) / (max_num - min_num + 1)

        # 特別號預測
        specials = None
        if lottery_rules.get('hasSpecialNumber', False):
            specials = self._predict_multiple_specials(draws, lottery_rules, num_bets)

        return {
            'bets': bets[:num_bets],
            'specials': specials,
            'coverage': coverage,
            'covered_numbers': sorted(all_covered),
            'total_unique_numbers': len(all_covered),
            'strategies_used': list(set(b.get('source', 'unknown') for b in bets))
        }

    def _calculate_number_scores(self, predictions: Dict, min_num: int, max_num: int) -> Dict[int, float]:
        """計算號碼綜合分數"""
        scores = defaultdict(float)

        for name, data in predictions.items():
            confidence = data.get('confidence', 0.5)
            for num in data['numbers']:
                scores[num] += confidence

        # 確保所有號碼都有分數
        for num in range(min_num, max_num + 1):
            if num not in scores:
                scores[num] = 0.1

        return dict(scores)

    def _calculate_diversity(self, candidate: Tuple[int, ...], existing_bets: List[List[int]]) -> float:
        """計算候選組合與現有注的差異度"""
        if not existing_bets:
            return 1.0

        total_overlap = 0
        for existing in existing_bets:
            overlap = len(set(candidate) & set(existing))
            total_overlap += overlap

        avg_overlap = total_overlap / len(existing_bets)
        max_overlap = len(candidate)

        return 1 - (avg_overlap / max_overlap)

    def _predict_multiple_specials(self, draws: List[Dict], lottery_rules: Dict,
                                   num_bets: int) -> List[int]:
        """預測多個特別號"""
        special_min = lottery_rules.get('specialMinNumber', lottery_rules.get('specialMin', 1))
        special_max = lottery_rules.get('specialMaxNumber', lottery_rules.get('specialMax', 8))

        # 統計特別號頻率
        special_freq = Counter()
        for h in draws[:100]:
            special = h.get('special_number') or h.get('special')
            if special is not None:
                special_freq[special] += 1

        if not special_freq:
            return list(range(special_min, min(special_min + num_bets, special_max + 1)))

        # 選擇不同的特別號
        specials = []
        for num, _ in special_freq.most_common():
            if len(specials) >= num_bets:
                break
            specials.append(num)

        # 補足不夠的
        while len(specials) < num_bets:
            for num in range(special_min, special_max + 1):
                if num not in specials:
                    specials.append(num)
                    if len(specials) >= num_bets:
                        break

        return specials[:num_bets]

    def backtest_multi_bet(self, draws: List[Dict], lottery_rules: Dict,
                           num_bets: int = 6, test_periods: int = 100) -> Dict:
        """
        多注策略回測

        判定標準：任意一注中3個及以上視為中獎
        """
        results = []
        win_count = 0
        total_best_matches = 0

        print(f"\n多注覆蓋策略回測 ({num_bets} 注 × {test_periods} 期)")
        print("-" * 60)

        for i in range(test_periods):
            target = draws[i]
            target_numbers = set(target['numbers'])
            history = draws[i + 1:]

            if len(history) < 100:
                continue

            try:
                prediction = self.generate_diversified_bets(history, lottery_rules, num_bets)

                # 檢查每一注
                bet_matches = []
                best_match = 0
                best_bet_idx = -1

                for idx, bet in enumerate(prediction['bets']):
                    matches = len(set(bet['numbers']) & target_numbers)
                    bet_matches.append(matches)
                    if matches > best_match:
                        best_match = matches
                        best_bet_idx = idx

                total_best_matches += best_match

                # 任一注中3個及以上視為中獎
                if best_match >= 3:
                    win_count += 1
                    status = f"WIN (第{best_bet_idx+1}注, {best_match}個)"
                else:
                    status = ""

                results.append({
                    'draw': target['draw'],
                    'bet_matches': bet_matches,
                    'best_match': best_match,
                    'best_bet_idx': best_bet_idx,
                    'coverage': prediction['coverage'],
                    'won': best_match >= 3
                })

                if (i + 1) % 20 == 0:
                    current_win_rate = win_count / (i + 1) * 100
                    current_avg = total_best_matches / (i + 1)
                    print(f"進度: {i+1}/{test_periods}, "
                          f"中獎率: {current_win_rate:.2f}%, "
                          f"最佳匹配平均: {current_avg:.2f}")

            except Exception as e:
                print(f"錯誤 ({target['draw']}): {e}")

        test_count = len(results)

        # 分析每注位置的表現
        bet_position_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'total_matches': 0})
        for r in results:
            for idx, matches in enumerate(r['bet_matches']):
                bet_position_stats[idx]['count'] += 1
                bet_position_stats[idx]['total_matches'] += matches
                if matches >= 3:
                    bet_position_stats[idx]['wins'] += 1

        return {
            'num_bets': num_bets,
            'test_count': test_count,
            'win_count': win_count,
            'win_rate': win_count / test_count if test_count > 0 else 0,
            'avg_best_match': total_best_matches / test_count if test_count > 0 else 0,
            'bet_position_stats': dict(bet_position_stats),
            'details': results
        }


# 單例
multi_bet_optimizer = MultiBetOptimizer()


def test_multi_bet():
    """測試多注覆蓋策略"""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    print("=" * 80)
    print("多注覆蓋優化器測試 - 2025年大樂透")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n數據: {len(draws)} 期")

    # 篩選2025年
    draws_2025 = [d for d in draws if d['date'].startswith('2025') or d['date'].startswith('114')]
    print(f"2025年: {len(draws_2025)} 期")

    optimizer = MultiBetOptimizer()

    # 測試不同注數
    for num_bets in [3, 6, 8]:
        print(f"\n{'='*60}")
        print(f"測試 {num_bets} 注策略")
        print(f"{'='*60}")

        results = optimizer.backtest_multi_bet(draws, rules, num_bets, len(draws_2025))

        print(f"\n結果:")
        print(f"  中獎次數: {results['win_count']}/{results['test_count']}")
        print(f"  中獎率: {results['win_rate']*100:.2f}%")
        print(f"  最佳匹配平均: {results['avg_best_match']:.2f}")

        print(f"\n  各注位置表現:")
        for idx, stats in sorted(results['bet_position_stats'].items()):
            if stats['count'] > 0:
                avg_match = stats['total_matches'] / stats['count']
                win_rate = stats['wins'] / stats['count'] * 100
                print(f"    第{idx+1}注: 平均匹配 {avg_match:.2f}, 中獎率 {win_rate:.1f}%")

    return results


if __name__ == '__main__':
    test_multi_bet()
