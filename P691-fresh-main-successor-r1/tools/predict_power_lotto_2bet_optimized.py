#!/usr/bin/env python3
"""
威力彩雙注優化預測器

設計原則：
1. 最大化覆蓋率 - 兩注之間盡量不重疊
2. 不過度工程化 - 避免「無連號」等錯誤假設
3. 基於實際歷史分布 - 使用驗證有效的方法
4. 互補設計 - 一注偏熱門，一注偏冷門回補

驗證方法組合 (根據 CLAUDE.md 記錄):
- Statistical + Frequency: 10.00% Match-3+ (150期驗證)
"""

import os
import sys
from collections import Counter
from typing import List, Dict, Tuple, Set
import random

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine


class PowerLotto2BetOptimizer:
    """威力彩雙注優化器 - 最大化覆蓋率"""

    def __init__(self):
        self.engine = UnifiedPredictionEngine()
        self.min_num = 1
        self.max_num = 38
        self.pick_count = 6
        self.special_min = 1
        self.special_max = 8

    def predict_2bets(self, history: List[Dict], rules: Dict) -> Dict:
        """
        生成優化的雙注預測

        策略：
        - 注1: Statistical (統計綜合) - 捕捉主流模式
        - 注2: 覆蓋優化 - 最大化與注1的互補性
        """
        # 注1: Statistical 方法
        bet1_result = self.engine.statistical_predict(history, rules)
        bet1_numbers = sorted(bet1_result['numbers'][:6])
        bet1_special = self._predict_special(history, bet1_numbers, method='frequency')

        # 注2: 最大化覆蓋率的互補注
        bet2_numbers, bet2_special = self._generate_complementary_bet(
            history, rules, bet1_numbers, bet1_special
        )

        # 計算覆蓋分析
        overlap = len(set(bet1_numbers) & set(bet2_numbers))
        total_coverage = len(set(bet1_numbers) | set(bet2_numbers))

        return {
            'bets': [
                {
                    'bet_number': 1,
                    'numbers': bet1_numbers,
                    'special': bet1_special,
                    'method': 'Statistical',
                    'description': '統計綜合 - 主流模式'
                },
                {
                    'bet_number': 2,
                    'numbers': bet2_numbers,
                    'special': bet2_special,
                    'method': 'Coverage-Optimized',
                    'description': '覆蓋優化 - 互補設計'
                }
            ],
            'coverage_analysis': {
                'overlap': overlap,
                'total_coverage': total_coverage,
                'coverage_rate': f'{total_coverage}/38 ({total_coverage/38*100:.1f}%)',
                'special_coverage': 2 if bet1_special != bet2_special else 1
            }
        }

    def _generate_complementary_bet(
        self,
        history: List[Dict],
        rules: Dict,
        bet1_numbers: List[int],
        bet1_special: int
    ) -> Tuple[List[int], int]:
        """
        生成與注1互補的注2

        策略：
        1. 從候選池中排除注1的號碼
        2. 使用 Frequency 方法選出剩餘高頻號
        3. 確保區間分布合理
        """
        bet1_set = set(bet1_numbers)

        # 計算所有號碼頻率 (近 100 期)
        recent_history = history[-100:] if len(history) > 100 else history
        freq = Counter()
        for draw in recent_history:
            nums = draw.get('numbers', [])
            freq.update(nums)

        # 計算冷號 (近 30 期未出現)
        recent_30 = history[-30:] if len(history) > 30 else history
        recent_nums = set()
        for draw in recent_30:
            recent_nums.update(draw.get('numbers', []))
        cold_numbers = [n for n in range(1, 39) if n not in recent_nums]

        # 候選池：排除注1的號碼
        candidates = [n for n in range(1, 39) if n not in bet1_set]

        # 按頻率排序
        candidates.sort(key=lambda x: freq.get(x, 0), reverse=True)

        # 分區選擇 (確保區間分布)
        zones = [(1, 13), (14, 25), (26, 38)]
        selected = []

        for zone_start, zone_end in zones:
            zone_candidates = [n for n in candidates if zone_start <= n <= zone_end]
            # 每區選 2 個高頻號
            zone_pick = zone_candidates[:2]
            selected.extend(zone_pick)

        # 如果不夠 6 個，從剩餘高頻號補充
        remaining = [n for n in candidates if n not in selected]
        while len(selected) < 6 and remaining:
            selected.append(remaining.pop(0))

        # 如果有冷號且少於 1 個冷號在選中，替換一個
        cold_in_selected = [n for n in selected if n in cold_numbers]
        if len(cold_in_selected) == 0 and cold_numbers:
            # 用一個冷號替換最後一個熱號
            cold_to_add = cold_numbers[0]
            if cold_to_add not in bet1_set:
                selected[-1] = cold_to_add

        bet2_numbers = sorted(selected[:6])

        # 第二區：選擇與注1不同的號碼
        bet2_special = self._predict_special(history, bet2_numbers, method='markov')
        if bet2_special == bet1_special:
            # 選擇次優的特別號
            bet2_special = (bet1_special % 8) + 1

        return bet2_numbers, bet2_special

    def _predict_special(self, history: List[Dict], main_numbers: List[int], method: str = 'frequency') -> int:
        """預測第二區號碼"""
        if len(history) < 10:
            return random.randint(1, 8)

        # 統計特別號頻率
        special_freq = Counter()
        for draw in history[-100:]:
            s = draw.get('special')
            if s:
                special_freq[s] += 1

        if method == 'frequency':
            # 選最高頻的
            if special_freq:
                return special_freq.most_common(1)[0][0]
            return random.randint(1, 8)

        elif method == 'markov':
            # 基於轉移機率
            if len(history) < 2:
                return random.randint(1, 8)

            last_special = history[-1].get('special', 1)
            transitions = Counter()

            for i in range(1, len(history)):
                prev = history[i-1].get('special')
                curr = history[i].get('special')
                if prev == last_special and curr:
                    transitions[curr] += 1

            if transitions:
                return transitions.most_common(1)[0][0]
            return random.randint(1, 8)

        return random.randint(1, 8)


def backtest_2bet(periods: int = 150) -> Dict:
    """回測雙注策略"""
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')

    optimizer = PowerLotto2BetOptimizer()

    wins = 0
    total = 0
    match_dist = Counter()
    method_wins = {'Statistical': 0, 'Coverage-Optimized': 0}

    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        if target_idx < 100:
            continue

        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]

        actual = set(target_draw.get('numbers', []))
        actual_special = target_draw.get('special')

        try:
            result = optimizer.predict_2bets(history, rules)

            round_best = 0
            hit = False

            for bet in result['bets']:
                bet_set = set(bet['numbers'])
                m = len(bet_set & actual)

                # 加上特別號匹配
                special_match = 1 if bet['special'] == actual_special else 0

                if m > round_best:
                    round_best = m

                if m >= 3:
                    hit = True
                    method_wins[bet['method']] += 1

            if hit:
                wins += 1
            match_dist[round_best] += 1
            total += 1

        except Exception as e:
            continue

    rate = wins / total * 100 if total > 0 else 0

    return {
        'periods': total,
        'wins': wins,
        'rate': rate,
        'match_distribution': dict(match_dist),
        'method_contribution': method_wins
    }


def main():
    """主函數：生成預測並進行回測驗證"""
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')

    optimizer = PowerLotto2BetOptimizer()

    print("=" * 70)
    print("🎯 威力彩雙注優化預測")
    print("=" * 70)

    # 使用全部歷史數據生成預測
    result = optimizer.predict_2bets(all_draws, rules)

    print(f"\n📊 預測目標: 第 {int(all_draws[-1]['draw']) + 1} 期")
    print(f"📅 基於數據: {all_draws[0]['draw']} ~ {all_draws[-1]['draw']} ({len(all_draws)} 期)")

    print("\n" + "-" * 70)
    print("🎰 雙注預測號碼:")
    print("-" * 70)

    for bet in result['bets']:
        numbers_str = ', '.join(f'{n:02d}' for n in bet['numbers'])
        print(f"\n  注{bet['bet_number']} ({bet['method']}):")
        print(f"    第一區: {numbers_str}")
        print(f"    第二區: {bet['special']:02d}")
        print(f"    說明: {bet['description']}")

    print("\n" + "-" * 70)
    print("📈 覆蓋分析:")
    print("-" * 70)
    analysis = result['coverage_analysis']
    print(f"  號碼重疊: {analysis['overlap']} 個")
    print(f"  總覆蓋數: {analysis['total_coverage']} 個 ({analysis['coverage_rate']})")
    print(f"  第二區覆蓋: {analysis['special_coverage']}/8")

    # 執行回測驗證
    print("\n" + "=" * 70)
    print("🔬 回測驗證 (150期)")
    print("=" * 70)

    backtest_result = backtest_2bet(150)

    print(f"\n  測試期數: {backtest_result['periods']}")
    print(f"  Match-3+ 次數: {backtest_result['wins']}")
    print(f"  Match-3+ 率: {backtest_result['rate']:.2f}%")

    print(f"\n  命中分布:")
    for m in sorted(backtest_result['match_distribution'].keys(), reverse=True):
        count = backtest_result['match_distribution'][m]
        print(f"    Match-{m}: {count} 次")

    print(f"\n  方法貢獻:")
    for method, wins in backtest_result['method_contribution'].items():
        print(f"    {method}: {wins} 次命中")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
