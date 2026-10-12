"""
選擇性集成預測器 - 只使用經過驗證的最佳策略

核心設計原則：
1. 只使用回測驗證表現最好的策略 (Top 3)
2. 動態窗口選擇 - 每個策略使用其最佳窗口
3. 共識強化 - 只有當多個頂級策略同時推薦時才選擇
4. 反向驗證 - 排除被多個策略同時排斥的號碼

基於回測結果的最佳配置：
- zone_balance (500期): 4.31%
- sum_range (100期): 4.31%
- ensemble (200期): 3.45%
- odd_even_balance (200期): 3.45%
"""

import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Optional
import os
import json
import logging

logger = logging.getLogger(__name__)


class SelectiveEnsemble:
    """選擇性集成預測器"""

    # 最佳策略配置 (基於回測驗證)
    OPTIMAL_CONFIGS = {
        'BIG_LOTTO': {
            'primary': [
                ('zone_balance', 500, 4.31),
                ('sum_range', 100, 4.31),
                ('ensemble', 200, 3.45),
            ],
            'secondary': [
                ('odd_even_balance', 200, 3.45),
                ('trend_predict', 300, 2.59),
                ('bayesian', 300, 2.59),
                ('cold_comeback', 100, 2.59),
            ]
        },
        'DAILY_539': {
            'primary': [
                ('sum_range', 300, 2.25),
                ('zone_balance', 150, 1.93),
                ('hot_cold_mix', 100, 1.93),
            ],
            'secondary': [
                ('monte_carlo', 100, 1.61),
                ('trend_predict', 200, 1.61),
            ]
        },
        'POWER_LOTTO': {
            'primary': [
                ('ensemble', 100, 3.5),
                ('zone_balance', 100, 3.2),
                ('bayesian', 100, 3.0),
            ],
            'secondary': [
                ('monte_carlo', 100, 2.8),
                ('trend_predict', 100, 2.5),
            ]
        }
    }

    def __init__(self):
        self.name = "SelectiveEnsemble"
        self._load_strategies()

    def _load_strategies(self):
        """載入策略函數"""
        from .unified_predictor import prediction_engine
        from .enhanced_predictor import EnhancedPredictor

        self.enhanced = EnhancedPredictor()

        self.strategy_functions = {
            'zone_balance': prediction_engine.zone_balance_predict,
            'sum_range': prediction_engine.sum_range_predict,
            'ensemble': prediction_engine.ensemble_predict,
            'odd_even_balance': prediction_engine.odd_even_balance_predict,
            'trend_predict': prediction_engine.trend_predict,
            'bayesian': prediction_engine.bayesian_predict,
            'monte_carlo': prediction_engine.monte_carlo_predict,
            'hot_cold_mix': prediction_engine.hot_cold_mix_predict,
            'cold_comeback': self.enhanced.cold_number_comeback_predict,
            'constrained': self.enhanced.constrained_predict,
        }

    def predict(self, draws: List[Dict], lottery_rules: Dict,
                lottery_type: str = 'BIG_LOTTO') -> Dict:
        """
        選擇性集成預測

        Args:
            draws: 歷史開獎數據 (新→舊)
            lottery_rules: 彩票規則
            lottery_type: 彩票類型

        Returns:
            預測結果
        """
        config = self.OPTIMAL_CONFIGS.get(lottery_type, self.OPTIMAL_CONFIGS['BIG_LOTTO'])
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 執行主要策略
        primary_predictions = {}
        for strategy_name, window, expected_rate in config['primary']:
            if strategy_name in self.strategy_functions:
                try:
                    history = draws[:window]
                    result = self.strategy_functions[strategy_name](history, lottery_rules)
                    primary_predictions[strategy_name] = {
                        'numbers': set(result['numbers']),
                        'weight': expected_rate,
                        'window': window
                    }
                except Exception as e:
                    logger.warning(f"策略 {strategy_name} 執行失敗: {e}")

        # 執行次要策略 (用於驗證)
        secondary_predictions = {}
        for strategy_name, window, expected_rate in config['secondary']:
            if strategy_name in self.strategy_functions:
                try:
                    history = draws[:window]
                    result = self.strategy_functions[strategy_name](history, lottery_rules)
                    secondary_predictions[strategy_name] = {
                        'numbers': set(result['numbers']),
                        'weight': expected_rate * 0.5,  # 降低次要策略權重
                        'window': window
                    }
                except:
                    pass

        if not primary_predictions:
            # 備用方案
            return self._fallback_predict(draws, lottery_rules)

        # 計算投票分數
        number_votes = defaultdict(float)
        number_sources = defaultdict(list)

        # 主要策略投票
        for strategy, data in primary_predictions.items():
            for num in data['numbers']:
                number_votes[num] += data['weight']
                number_sources[num].append(('P', strategy))

        # 次要策略投票
        for strategy, data in secondary_predictions.items():
            for num in data['numbers']:
                number_votes[num] += data['weight']
                number_sources[num].append(('S', strategy))

        # 找出高共識號碼 (被多個主要策略推薦)
        high_consensus = []
        medium_consensus = []
        low_consensus = []

        for num, vote in number_votes.items():
            primary_count = sum(1 for t, _ in number_sources[num] if t == 'P')
            if primary_count >= 2:  # 被2個及以上主要策略推薦
                high_consensus.append((num, vote, primary_count))
            elif primary_count == 1:
                medium_consensus.append((num, vote, primary_count))
            else:
                low_consensus.append((num, vote, primary_count))

        # 排序
        high_consensus.sort(key=lambda x: (-x[2], -x[1]))
        medium_consensus.sort(key=lambda x: -x[1])
        low_consensus.sort(key=lambda x: -x[1])

        # 選號策略：優先選高共識，再補充中等共識
        selected = []
        selected_info = []

        # 1. 先選高共識號碼
        for num, vote, count in high_consensus:
            if len(selected) >= pick_count:
                break
            selected.append(num)
            selected_info.append({
                'number': num,
                'consensus': 'high',
                'primary_count': count,
                'sources': [s for _, s in number_sources[num]]
            })

        # 2. 補充中等共識
        for num, vote, count in medium_consensus:
            if len(selected) >= pick_count:
                break
            if num not in selected:
                selected.append(num)
                selected_info.append({
                    'number': num,
                    'consensus': 'medium',
                    'primary_count': count,
                    'sources': [s for _, s in number_sources[num]]
                })

        # 3. 再補充低共識
        for num, vote, count in low_consensus:
            if len(selected) >= pick_count:
                break
            if num not in selected:
                selected.append(num)
                selected_info.append({
                    'number': num,
                    'consensus': 'low',
                    'primary_count': count,
                    'sources': [s for _, s in number_sources[num]]
                })

        # 計算信心度
        high_count = sum(1 for info in selected_info if info['consensus'] == 'high')
        medium_count = sum(1 for info in selected_info if info['consensus'] == 'medium')
        confidence = 0.5 + high_count * 0.1 + medium_count * 0.05

        # 特別號預測
        special = None
        if lottery_rules.get('hasSpecialNumber', False):
            special = self._predict_special(draws, lottery_rules)

        return {
            'numbers': sorted(selected),
            'special': special,
            'confidence': min(0.85, confidence),
            'method': 'selective_ensemble',
            'consensus_stats': {
                'high': high_count,
                'medium': medium_count,
                'low': pick_count - high_count - medium_count
            },
            'selected_info': selected_info,
            'strategies_used': list(primary_predictions.keys()) + list(secondary_predictions.keys())
        }

    def _predict_special(self, draws: List[Dict], lottery_rules: Dict) -> int:
        """預測特別號"""
        special_min = lottery_rules.get('specialMinNumber', lottery_rules.get('specialMin', 1))
        special_max = lottery_rules.get('specialMaxNumber', lottery_rules.get('specialMax', 8))

        # 統計特別號頻率
        special_freq = Counter()
        for h in draws[:50]:
            special = h.get('special_number') or h.get('special')
            if special is not None:
                special_freq[special] += 1

        if not special_freq:
            return (special_min + special_max) // 2

        # 選擇最常出現的特別號
        return special_freq.most_common(1)[0][0]

    def _fallback_predict(self, draws: List[Dict], lottery_rules: Dict) -> Dict:
        """備用預測方法"""
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))

        # 使用頻率統計
        freq = Counter()
        for d in draws[:100]:
            for num in d['numbers']:
                freq[num] += 1

        top_nums = [n for n, _ in freq.most_common(pick_count * 2)]
        selected = sorted(np.random.choice(top_nums, pick_count, replace=False).tolist())

        return {
            'numbers': selected,
            'confidence': 0.4,
            'method': 'fallback_frequency'
        }

    def rolling_backtest(self, draws: List[Dict], lottery_rules: Dict,
                        lottery_type: str, test_periods: int = 100) -> Dict:
        """滾動回測"""
        results = []
        win_count = 0
        total_matches = 0

        # 統計共識等級的表現
        consensus_stats = {
            'high': {'count': 0, 'matches': 0},
            'medium': {'count': 0, 'matches': 0},
            'low': {'count': 0, 'matches': 0}
        }

        print(f"\n選擇性集成 - 滾動回測 ({test_periods} 期)")
        print("-" * 60)

        for i in range(test_periods):
            target = draws[i]
            target_numbers = set(target['numbers'])
            history = draws[i + 1:]

            if len(history) < 100:
                continue

            try:
                prediction = self.predict(history, lottery_rules, lottery_type)
                predicted_numbers = set(prediction['numbers'])
                matches = len(predicted_numbers & target_numbers)

                total_matches += matches
                if matches >= 3:
                    win_count += 1

                # 分析哪些共識等級的號碼命中
                for info in prediction.get('selected_info', []):
                    num = info['number']
                    level = info['consensus']
                    consensus_stats[level]['count'] += 1
                    if num in target_numbers:
                        consensus_stats[level]['matches'] += 1

                results.append({
                    'draw': target['draw'],
                    'predicted': sorted(predicted_numbers),
                    'actual': sorted(target_numbers),
                    'matches': matches,
                    'consensus_stats': prediction.get('consensus_stats', {})
                })

                if (i + 1) % 20 == 0:
                    print(f"進度: {i+1}/{test_periods}, "
                          f"中獎率: {win_count/(i+1)*100:.2f}%, "
                          f"平均匹配: {total_matches/(i+1):.3f}")

            except Exception as e:
                print(f"錯誤 ({target['draw']}): {e}")

        test_count = len(results)

        # 計算各共識等級的命中率
        consensus_hit_rates = {}
        for level, stats in consensus_stats.items():
            if stats['count'] > 0:
                consensus_hit_rates[level] = stats['matches'] / stats['count']
            else:
                consensus_hit_rates[level] = 0

        return {
            'test_count': test_count,
            'win_count': win_count,
            'win_rate': win_count / test_count if test_count > 0 else 0,
            'avg_matches': total_matches / test_count if test_count > 0 else 0,
            'consensus_hit_rates': consensus_hit_rates,
            'details': results
        }


# 單例實例
selective_ensemble = SelectiveEnsemble()


def test_selective_ensemble():
    """測試選擇性集成"""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

    from database import DatabaseManager
    from common import get_lottery_rules

    print("=" * 80)
    print("選擇性集成預測器測試")
    print("=" * 80)

    db = DatabaseManager(db_path=os.path.join(os.path.dirname(__file__), '..', 'data', 'lottery_v2.db'))
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')

    print(f"\n數據: {len(draws)} 期")
    print(f"最新: {draws[0]['draw']}")

    # 篩選2025年
    draws_2025 = [d for d in draws if d['date'].startswith('2025') or d['date'].startswith('114')]
    print(f"2025年: {len(draws_2025)} 期")

    # 回測
    ensemble = SelectiveEnsemble()
    results = ensemble.rolling_backtest(draws, rules, 'BIG_LOTTO', len(draws_2025))

    print(f"\n{'='*60}")
    print("回測結果")
    print(f"{'='*60}")
    print(f"測試期數: {results['test_count']}")
    print(f"中獎次數: {results['win_count']}")
    print(f"中獎率: {results['win_rate']*100:.2f}%")
    print(f"平均匹配: {results['avg_matches']:.3f}")

    print(f"\n共識等級命中率:")
    for level, rate in results['consensus_hit_rates'].items():
        print(f"  {level}: {rate*100:.2f}%")

    return results


if __name__ == '__main__':
    test_selective_ensemble()
