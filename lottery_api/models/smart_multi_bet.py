"""
智能多組號碼系統 - 通過多組預測提高覆蓋率

核心思路：
1. 單組預測很難命中多個號碼
2. 使用多組「互補」的號碼組合提高整體覆蓋率
3. 基於 Wheeling System 的覆蓋設計理念
4. 結合多種預測方法的優勢
"""

import numpy as np
from collections import Counter
from typing import List, Dict, Set, Tuple
import random
from itertools import combinations


class SmartMultiBetSystem:
    """智能多組號碼系統"""

    def __init__(self):
        self.name = "SmartMultiBetSystem"

    def generate_smart_bets(
        self,
        history: List[Dict],
        lottery_rules: Dict,
        num_bets: int = 5
    ) -> List[Dict]:
        """
        生成智能多組號碼

        Args:
            history: 歷史開獎數據
            lottery_rules: 彩票規則
            num_bets: 要生成的組數

        Returns:
            多組號碼預測結果
        """
        pick_count = lottery_rules.get('pick_count', 6)
        min_num = lottery_rules.get('min_number', 1)
        max_num = lottery_rules.get('max_number', 49)

        # 1. 分析歷史數據建立號碼池
        candidate_pool = self._build_candidate_pool(history, min_num, max_num)

        # 2. 生成互補的多組號碼
        bets = self._generate_complementary_bets(
            candidate_pool, pick_count, num_bets, history
        )

        return bets

    def _build_candidate_pool(
        self,
        history: List[Dict],
        min_num: int,
        max_num: int
    ) -> Dict[str, List[int]]:
        """建立候選號碼池（分層）"""

        # 頻率分析
        freq_counter = Counter()
        for h in history[:50]:
            for n in h['numbers']:
                freq_counter[n] += 1

        # 近期熱門（近 20 期）
        recent_counter = Counter()
        for h in history[:20]:
            for n in h['numbers']:
                recent_counter[n] += 1

        # 分類號碼
        all_nums = list(range(min_num, max_num + 1))

        # 熱門號碼（頻率前 15）
        hot_numbers = [n for n, c in freq_counter.most_common(15)]

        # 冷門號碼（頻率後 15）
        cold_numbers = [n for n, c in freq_counter.most_common()[-15:]]

        # 中間號碼
        mid_numbers = [n for n in all_nums if n not in hot_numbers and n not in cold_numbers]

        # 近期活躍（近 20 期出現 2+ 次）
        recent_active = [n for n, c in recent_counter.items() if c >= 2]

        # 上期號碼
        last_numbers = list(history[0]['numbers']) if history else []

        # 即將回歸的冷號（間隔接近平均值）
        comeback_candidates = self._find_comeback_candidates(history, min_num, max_num)

        return {
            'hot': hot_numbers,
            'cold': cold_numbers,
            'mid': mid_numbers,
            'recent_active': recent_active,
            'last_draw': last_numbers,
            'comeback': comeback_candidates,
            'all': all_nums
        }

    def _find_comeback_candidates(
        self,
        history: List[Dict],
        min_num: int,
        max_num: int
    ) -> List[int]:
        """找出即將回歸的號碼"""
        candidates = []

        for num in range(min_num, max_num + 1):
            # 計算當前間隔
            current_gap = 0
            for i, h in enumerate(history):
                if num in h['numbers']:
                    current_gap = i
                    break
            else:
                current_gap = len(history)

            # 計算平均間隔
            appearances = [i for i, h in enumerate(history) if num in h['numbers']]
            if len(appearances) >= 3:
                gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
                avg_gap = np.mean(gaps)

                # 如果當前間隔接近或超過平均間隔
                if current_gap >= avg_gap * 0.9:
                    candidates.append((num, current_gap / avg_gap))

        # 按回歸優先級排序
        candidates.sort(key=lambda x: -x[1])
        return [c[0] for c in candidates[:15]]

    def _generate_complementary_bets(
        self,
        pool: Dict[str, List[int]],
        pick_count: int,
        num_bets: int,
        history: List[Dict]
    ) -> List[Dict]:
        """生成互補的多組號碼"""
        bets = []
        used_numbers = set()

        strategies = [
            ('熱門主導', self._strategy_hot_dominant, pool),
            ('均衡覆蓋', self._strategy_balanced, pool),
            ('冷號回歸', self._strategy_cold_comeback, pool),
            ('連號策略', self._strategy_consecutive, pool, history),
            ('區間覆蓋', self._strategy_zone_coverage, pool),
            ('統計約束', self._strategy_constrained, pool, history),
        ]

        for i in range(num_bets):
            strategy_name, strategy_func, *args = strategies[i % len(strategies)]

            # 生成號碼
            numbers = strategy_func(*args, pick_count, used_numbers)

            # 確保號碼有效
            if len(numbers) == pick_count:
                bets.append({
                    'numbers': sorted(numbers),
                    'strategy': strategy_name,
                    'bet_index': i + 1
                })
                used_numbers.update(numbers)

        # 計算覆蓋統計
        all_selected = set()
        for bet in bets:
            all_selected.update(bet['numbers'])

        coverage_rate = len(all_selected) / 49 * 100

        return {
            'bets': bets,
            'total_bets': len(bets),
            'unique_numbers': len(all_selected),
            'coverage_rate': coverage_rate,
            'numbers_list': sorted(all_selected)
        }

    def _strategy_hot_dominant(
        self,
        pool: Dict,
        pick_count: int,
        used: Set[int]
    ) -> List[int]:
        """熱門主導策略：4 熱 + 2 中"""
        result = []

        # 4 個熱門
        hot_candidates = [n for n in pool['hot'] if n not in used]
        result.extend(random.sample(hot_candidates, min(4, len(hot_candidates))))

        # 2 個中間
        mid_candidates = [n for n in pool['mid'] if n not in used and n not in result]
        result.extend(random.sample(mid_candidates, min(pick_count - len(result), len(mid_candidates))))

        # 補足
        if len(result) < pick_count:
            remaining = [n for n in pool['all'] if n not in result]
            result.extend(random.sample(remaining, pick_count - len(result)))

        return result[:pick_count]

    def _strategy_balanced(
        self,
        pool: Dict,
        pick_count: int,
        used: Set[int]
    ) -> List[int]:
        """均衡策略：2 熱 + 2 中 + 2 冷"""
        result = []

        for category, count in [('hot', 2), ('mid', 2), ('cold', 2)]:
            candidates = [n for n in pool[category] if n not in used and n not in result]
            result.extend(random.sample(candidates, min(count, len(candidates))))

        if len(result) < pick_count:
            remaining = [n for n in pool['all'] if n not in result]
            result.extend(random.sample(remaining, pick_count - len(result)))

        return result[:pick_count]

    def _strategy_cold_comeback(
        self,
        pool: Dict,
        pick_count: int,
        used: Set[int]
    ) -> List[int]:
        """冷號回歸策略：主打即將回歸的號碼"""
        result = []

        # 3-4 個回歸候選
        comeback = [n for n in pool['comeback'] if n not in used]
        result.extend(comeback[:4])

        # 補充熱門號碼穩定
        hot = [n for n in pool['hot'] if n not in used and n not in result]
        result.extend(hot[:pick_count - len(result)])

        if len(result) < pick_count:
            remaining = [n for n in pool['all'] if n not in result]
            result.extend(random.sample(remaining, pick_count - len(result)))

        return result[:pick_count]

    def _strategy_consecutive(
        self,
        pool: Dict,
        history: List[Dict],
        pick_count: int,
        used: Set[int]
    ) -> List[int]:
        """連號策略：包含上期號碼"""
        result = []

        # 1-2 個上期號碼
        last = [n for n in pool['last_draw'] if n not in used]
        result.extend(last[:2])

        # 補充近期活躍
        recent = [n for n in pool['recent_active'] if n not in used and n not in result]
        result.extend(recent[:2])

        # 補充熱門
        hot = [n for n in pool['hot'] if n not in used and n not in result]
        result.extend(hot[:pick_count - len(result)])

        if len(result) < pick_count:
            remaining = [n for n in pool['all'] if n not in result]
            result.extend(random.sample(remaining, pick_count - len(result)))

        return result[:pick_count]

    def _strategy_zone_coverage(
        self,
        pool: Dict,
        pick_count: int,
        used: Set[int]
    ) -> List[int]:
        """區間覆蓋策略：確保覆蓋所有區間"""
        zones = [
            list(range(1, 11)),
            list(range(11, 21)),
            list(range(21, 31)),
            list(range(31, 41)),
            list(range(41, 50))
        ]

        result = []

        # 從每個區間選 1 個
        for zone in zones:
            candidates = [n for n in zone if n not in used and n not in result]
            # 優先選熱門
            hot_in_zone = [n for n in candidates if n in pool['hot']]
            if hot_in_zone:
                result.append(random.choice(hot_in_zone))
            elif candidates:
                result.append(random.choice(candidates))

        # 補足到 6 個
        if len(result) < pick_count:
            hot = [n for n in pool['hot'] if n not in result]
            result.extend(random.sample(hot, min(pick_count - len(result), len(hot))))

        return result[:pick_count]

    def _strategy_constrained(
        self,
        pool: Dict,
        history: List[Dict],
        pick_count: int,
        used: Set[int]
    ) -> List[int]:
        """約束策略：滿足統計約束條件"""
        best_combo = None
        best_score = -1

        for _ in range(200):
            # 從各類別隨機選擇
            candidates = []
            candidates.extend(random.sample(pool['hot'], min(3, len(pool['hot']))))
            candidates.extend(random.sample(pool['mid'], min(2, len(pool['mid']))))
            candidates.extend(random.sample(pool['comeback'], min(2, len(pool['comeback']))))

            # 去重並選 6 個
            candidates = list(set(candidates))
            if len(candidates) < pick_count:
                remaining = [n for n in pool['all'] if n not in candidates]
                candidates.extend(random.sample(remaining, pick_count - len(candidates)))

            combo = random.sample(candidates, pick_count)

            # 評估約束
            score = self._evaluate_combo(combo, history)
            if score > best_score:
                best_score = score
                best_combo = combo

        return best_combo or random.sample(pool['all'], pick_count)

    def _evaluate_combo(self, numbers: List[int], history: List[Dict]) -> float:
        """評估號碼組合的質量"""
        score = 0

        # 奇偶平衡
        odd = sum(1 for n in numbers if n % 2 == 1)
        if odd in [3, 4]:
            score += 20

        # 和值範圍
        total = sum(numbers)
        if 128 <= total <= 173:
            score += 20
        elif 100 <= total <= 200:
            score += 10

        # 區間分佈
        zones = [(1, 10), (11, 20), (21, 30), (31, 40), (41, 49)]
        covered = sum(1 for z_min, z_max in zones
                     if any(z_min <= n <= z_max for n in numbers))
        score += covered * 5

        return score


def generate_recommendations(num_bets: int = 5):
    """生成推薦號碼"""
    import sqlite3
    import json

    # 載入數據
    conn = sqlite3.connect('data/lottery.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers, special, date
        FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date DESC
        LIMIT 300
    """)
    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        draw, numbers_str, special, draw_date = row
        numbers = json.loads(numbers_str) if numbers_str.startswith('[') else [int(x) for x in numbers_str.split(',')]
        history.append({
            'draw_id': draw,
            'numbers': numbers,
            'special_number': special,
            'draw_date': draw_date
        })

    lottery_rules = {
        'pick_count': 6,
        'min_number': 1,
        'max_number': 49,
        'has_special': True
    }

    system = SmartMultiBetSystem()
    result = system.generate_smart_bets(history, lottery_rules, num_bets)

    return result


if __name__ == '__main__':
    result = generate_recommendations(6)

    print('=' * 60)
    print('🎯 智能多組號碼推薦')
    print('=' * 60)
    print()

    for bet in result['bets']:
        print(f'第 {bet["bet_index"]} 組 ({bet["strategy"]}):')
        print(f'  號碼: {bet["numbers"]}')
        print()

    print('=' * 60)
    print(f'📊 覆蓋統計:')
    print(f'  總組數: {result["total_bets"]}')
    print(f'  覆蓋號碼數: {result["unique_numbers"]} / 49')
    print(f'  覆蓋率: {result["coverage_rate"]:.1f}%')
    print(f'  所有號碼: {result["numbers_list"]}')
    print('=' * 60)
