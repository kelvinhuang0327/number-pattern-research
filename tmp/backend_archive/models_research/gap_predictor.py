"""
間隔分析預測器 (Gap Analysis Predictor)

原理：
- 每個號碼都有「平均出現間隔」（期望值）
- 當某號碼的「缺席期數」超過平均間隔時，可能「該出現了」
- 結合組合約束（奇偶比、總和範圍）提高預測品質

P0 新增功能
"""

import random
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
import logging

logger = logging.getLogger(__name__)


class GapAnalysisPredictor:
    """
    間隔分析預測器

    基於號碼缺席期數的統計分析，選擇「該出現了」的號碼
    """

    def __init__(self):
        self.name = "gap_analysis"
        self.optimal_window = 300  # 較長窗口才能準確計算平均間隔

    def calculate_gaps(self, history: List[Dict], max_number: int) -> Dict[int, Dict]:
        """
        計算每個號碼的間隔統計

        Returns:
            {
                號碼: {
                    'current_gap': 當前缺席期數,
                    'avg_gap': 平均出現間隔,
                    'max_gap': 歷史最大間隔,
                    'total_appearances': 總出現次數,
                    'gap_ratio': 當前缺席/平均間隔 (>1 表示超過預期)
                }
            }
        """
        if not history:
            return {}

        # 初始化
        gaps = {num: {'appearances': [], 'last_seen': None} for num in range(1, max_number + 1)}

        # 從舊到新遍歷，記錄每個號碼的出現位置
        for i, draw in enumerate(reversed(history)):
            numbers = draw.get('numbers', [])
            for num in numbers:
                if 1 <= num <= max_number:
                    if gaps[num]['last_seen'] is not None:
                        gap = i - gaps[num]['last_seen']
                        gaps[num]['appearances'].append(gap)
                    gaps[num]['last_seen'] = i

        # 計算統計量
        total_periods = len(history)
        result = {}

        for num in range(1, max_number + 1):
            appearances = gaps[num]['appearances']
            last_seen = gaps[num]['last_seen']

            # 當前缺席期數
            current_gap = total_periods - 1 - last_seen if last_seen is not None else total_periods

            # 平均間隔（如果沒有足夠數據，使用理論期望值）
            if len(appearances) >= 3:
                avg_gap = sum(appearances) / len(appearances)
                max_gap = max(appearances)
            else:
                # 理論期望間隔 = 總號碼數 / 每期選號數
                # 例如：39/5 ≈ 7.8 (今彩539)
                avg_gap = max_number / 5  # 近似值
                max_gap = avg_gap * 3

            # 間隔比率
            gap_ratio = current_gap / avg_gap if avg_gap > 0 else 0

            result[num] = {
                'current_gap': current_gap,
                'avg_gap': round(avg_gap, 2),
                'max_gap': max_gap,
                'total_appearances': len(appearances) + (1 if last_seen is not None else 0),
                'gap_ratio': round(gap_ratio, 2)
            }

        return result

    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        基於間隔分析的預測

        策略：
        1. 優先選擇 gap_ratio > 1.5 的號碼（超過預期間隔 50%）
        2. 應用組合約束（奇偶比、總和範圍）
        3. 如果候選不足，補充 gap_ratio > 1.0 的號碼
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 39)
        pick_count = lottery_rules.get('pickCount', 5)

        # 計算間隔
        gap_stats = self.calculate_gaps(history, max_num)

        # 按 gap_ratio 排序（選擇「該出現了」的號碼）
        candidates = sorted(
            gap_stats.items(),
            key=lambda x: x[1]['gap_ratio'],
            reverse=True
        )

        # 第一輪：選擇 gap_ratio > 1.5 的號碼
        high_priority = [num for num, stats in candidates if stats['gap_ratio'] > 1.5]

        # 第二輪：選擇 gap_ratio > 1.0 的號碼
        medium_priority = [num for num, stats in candidates if 1.0 < stats['gap_ratio'] <= 1.5]

        # 合併候選
        all_candidates = high_priority + medium_priority

        # 應用組合約束選擇最終號碼
        selected = self._select_with_constraints(
            all_candidates,
            pick_count,
            min_num,
            max_num,
            history
        )

        # 計算置信度
        avg_gap_ratio = sum(gap_stats[n]['gap_ratio'] for n in selected) / len(selected) if selected else 0
        confidence = min(0.9, 0.5 + avg_gap_ratio * 0.1)

        return {
            'numbers': sorted(selected),
            'confidence': round(confidence, 2),
            'method': 'gap_analysis',
            'gap_stats': {n: gap_stats[n] for n in selected}
        }

    def _select_with_constraints(
        self,
        candidates: List[int],
        pick_count: int,
        min_num: int,
        max_num: int,
        history: List[Dict]
    ) -> List[int]:
        """
        應用組合約束選擇號碼

        約束條件：
        1. 奇偶比：2-3個奇數（5選時）
        2. 總和範圍：在統計熱區內
        3. 區間分布：不過度集中
        """
        if len(candidates) < pick_count:
            # 候選不足，補充隨機號碼
            remaining = [n for n in range(min_num, max_num + 1) if n not in candidates]
            random.shuffle(remaining)
            candidates = candidates + remaining

        # 計算歷史總和範圍
        sums = [sum(d.get('numbers', [])) for d in history[:50] if d.get('numbers')]
        if sums:
            avg_sum = sum(sums) / len(sums)
            sum_range = (avg_sum * 0.7, avg_sum * 1.3)
        else:
            sum_range = (pick_count * (min_num + max_num) / 2 * 0.7,
                        pick_count * (min_num + max_num) / 2 * 1.3)

        # 嘗試找到符合約束的組合
        best_combo = None
        best_score = -1

        # 貪婪選擇 + 約束檢查
        for _ in range(100):  # 最多嘗試 100 次
            selected = []
            odd_count = 0
            remaining = candidates.copy()

            while len(selected) < pick_count and remaining:
                # 優先選擇可以平衡奇偶的號碼
                for num in remaining:
                    is_odd = num % 2 == 1

                    # 奇偶平衡檢查
                    if is_odd and odd_count >= 3:
                        continue
                    if not is_odd and (len(selected) - odd_count) >= 3:
                        continue

                    selected.append(num)
                    if is_odd:
                        odd_count += 1
                    remaining.remove(num)
                    break
                else:
                    # 沒有符合條件的，隨機選一個
                    if remaining:
                        num = remaining.pop(0)
                        selected.append(num)
                        if num % 2 == 1:
                            odd_count += 1

            # 計算組合得分
            if len(selected) == pick_count:
                total = sum(selected)
                in_range = sum_range[0] <= total <= sum_range[1]
                odd_balanced = 2 <= odd_count <= 3

                score = (1 if in_range else 0) + (1 if odd_balanced else 0)

                if score > best_score:
                    best_score = score
                    best_combo = selected.copy()

                if score == 2:  # 完美組合
                    break

            # 打亂候選順序進行下一次嘗試
            random.shuffle(candidates)

        return best_combo if best_combo else candidates[:pick_count]

    def get_overdue_numbers(self, history: List[Dict], lottery_rules: Dict, threshold: float = 1.5) -> List[Dict]:
        """
        獲取「超期」號碼列表（用於分析展示）

        Args:
            threshold: gap_ratio 門檻，預設 1.5 表示超過平均間隔 50%

        Returns:
            [
                {'number': 號碼, 'current_gap': 缺席期數, 'avg_gap': 平均間隔, 'gap_ratio': 比率},
                ...
            ]
        """
        max_num = lottery_rules.get('maxNumber', 39)
        gap_stats = self.calculate_gaps(history, max_num)

        overdue = []
        for num, stats in gap_stats.items():
            if stats['gap_ratio'] >= threshold:
                overdue.append({
                    'number': num,
                    'current_gap': stats['current_gap'],
                    'avg_gap': stats['avg_gap'],
                    'gap_ratio': stats['gap_ratio']
                })

        return sorted(overdue, key=lambda x: -x['gap_ratio'])


class ConstrainedPredictor:
    """
    組合約束預測器

    在任何基礎預測方法上套用組合約束，提高預測品質
    """

    def __init__(self):
        self.name = "constrained"
        self.optimal_window = 200

    def apply_constraints(
        self,
        base_numbers: List[int],
        lottery_rules: Dict,
        history: List[Dict],
        constraints: Dict = None
    ) -> List[int]:
        """
        對基礎預測結果應用約束

        Args:
            base_numbers: 基礎預測的號碼（可能超過需要的數量）
            lottery_rules: 彩票規則
            history: 歷史數據（用於計算統計約束）
            constraints: 約束條件

        Returns:
            符合約束的號碼列表
        """
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 39)
        pick_count = lottery_rules.get('pickCount', 5)

        # 預設約束
        if constraints is None:
            constraints = self._get_default_constraints(history, pick_count)

        # 過濾並選擇符合約束的組合
        valid_numbers = [n for n in base_numbers if min_num <= n <= max_num]

        if len(valid_numbers) < pick_count:
            # 補充號碼
            all_nums = set(range(min_num, max_num + 1))
            remaining = list(all_nums - set(valid_numbers))
            random.shuffle(remaining)
            valid_numbers.extend(remaining[:pick_count - len(valid_numbers)])

        # 嘗試找到符合所有約束的組合
        from itertools import combinations

        best_combo = None
        best_violations = float('inf')

        # 如果候選太多，只取前 20 個
        candidates = valid_numbers[:20]

        for combo in combinations(candidates, pick_count):
            violations = self._count_violations(combo, constraints)
            if violations < best_violations:
                best_violations = violations
                best_combo = list(combo)
            if violations == 0:
                break

        return sorted(best_combo) if best_combo else sorted(valid_numbers[:pick_count])

    def _get_default_constraints(self, history: List[Dict], pick_count: int) -> Dict:
        """獲取基於歷史數據的預設約束"""
        # 計算歷史總和
        sums = [sum(d.get('numbers', [])) for d in history[:100] if d.get('numbers')]
        avg_sum = sum(sums) / len(sums) if sums else 100

        # 計算歷史奇偶比
        odd_counts = []
        for d in history[:100]:
            nums = d.get('numbers', [])
            if nums:
                odd_counts.append(sum(1 for n in nums if n % 2 == 1))
        avg_odd = sum(odd_counts) / len(odd_counts) if odd_counts else pick_count / 2

        return {
            'odd_even_range': (max(1, int(avg_odd) - 1), min(pick_count - 1, int(avg_odd) + 1)),
            'sum_range': (avg_sum * 0.75, avg_sum * 1.25),
            'max_consecutive': 2,
            'same_ending_max': 2,
        }

    def _count_violations(self, combo: Tuple[int, ...], constraints: Dict) -> int:
        """計算違反約束的數量"""
        violations = 0

        # 奇偶比約束
        odd_count = sum(1 for n in combo if n % 2 == 1)
        odd_range = constraints.get('odd_even_range', (1, 4))
        if not (odd_range[0] <= odd_count <= odd_range[1]):
            violations += 1

        # 總和約束
        total = sum(combo)
        sum_range = constraints.get('sum_range', (50, 150))
        if not (sum_range[0] <= total <= sum_range[1]):
            violations += 1

        # 連號約束
        sorted_combo = sorted(combo)
        max_consecutive = constraints.get('max_consecutive', 2)
        consecutive = 1
        for i in range(1, len(sorted_combo)):
            if sorted_combo[i] == sorted_combo[i-1] + 1:
                consecutive += 1
                if consecutive > max_consecutive:
                    violations += 1
                    break
            else:
                consecutive = 1

        # 同尾號約束
        endings = [n % 10 for n in combo]
        ending_counts = Counter(endings)
        same_ending_max = constraints.get('same_ending_max', 2)
        if max(ending_counts.values()) > same_ending_max:
            violations += 1

        return violations


class ConsensusPredictor:
    """
    共識投票預測器

    執行多個預測方法，選擇最多方法推薦的號碼
    """

    def __init__(self):
        self.name = "consensus"
        self.optimal_window = 200

    def predict(self, history: List[Dict], lottery_rules: Dict, methods: List = None) -> Dict:
        """
        共識投票預測

        Args:
            methods: 預測方法列表，每個元素是 (method_func, weight)
        """
        from .unified_predictor import prediction_engine as engine
        pick_count = lottery_rules.get('pickCount', 5)

        # 預設方法及權重
        if methods is None:
            methods = [
                (engine.trend_predict, 2.0),
                (engine.zone_balance_predict, 1.8),
                (engine.bayesian_predict, 1.5),
                (engine.hot_cold_mix_predict, 1.2),
                (engine.monte_carlo_predict, 1.0),
            ]

        # 收集所有預測
        vote_scores = defaultdict(float)

        for method_func, weight in methods:
            try:
                result = method_func(history, lottery_rules)
                for num in result.get('numbers', []):
                    vote_scores[num] += weight
            except Exception as e:
                logger.warning(f"Method {method_func.__name__} failed: {e}")
                continue

        # 按得分排序
        ranked = sorted(vote_scores.items(), key=lambda x: -x[1])

        # 選擇得分最高的號碼
        selected = [num for num, _ in ranked[:pick_count]]

        # 計算共識程度
        if ranked:
            top_score = ranked[0][1]
            avg_score = sum(s for _, s in ranked[:pick_count]) / pick_count
            consensus_level = avg_score / top_score if top_score > 0 else 0
        else:
            consensus_level = 0

        # 應用組合約束
        constrained = ConstrainedPredictor()
        final_numbers = constrained.apply_constraints(
            [num for num, _ in ranked[:pick_count * 2]],
            lottery_rules,
            history
        )

        return {
            'numbers': sorted(final_numbers),
            'confidence': round(0.5 + consensus_level * 0.3, 2),
            'method': 'consensus',
            'vote_scores': dict(ranked[:10]),
            'consensus_level': round(consensus_level, 2)
        }


# 便捷函數
def gap_predict(history: List[Dict], lottery_rules: Dict) -> Dict:
    """間隔分析預測的便捷函數"""
    predictor = GapAnalysisPredictor()
    return predictor.predict(history, lottery_rules)


def consensus_predict(history: List[Dict], lottery_rules: Dict) -> Dict:
    """共識投票預測的便捷函數"""
    predictor = ConsensusPredictor()
    return predictor.predict(history, lottery_rules)


# 測試
if __name__ == '__main__':
    # 模擬測試數據
    import random

    history = []
    for i in range(100):
        numbers = sorted(random.sample(range(1, 40), 5))
        history.append({
            'draw': f'test_{100-i:03d}',
            'date': f'2025-01-{(i%28)+1:02d}',
            'numbers': numbers
        })

    rules = {
        'minNumber': 1,
        'maxNumber': 39,
        'pickCount': 5,
        'hasSpecialNumber': False
    }

    # 測試間隔分析
    gap_predictor = GapAnalysisPredictor()
    result = gap_predictor.predict(history, rules)
    print(f"間隔分析預測: {result['numbers']}")
    print(f"置信度: {result['confidence']}")

    # 測試超期號碼
    overdue = gap_predictor.get_overdue_numbers(history, rules)
    print(f"\n超期號碼 (top 5):")
    for item in overdue[:5]:
        print(f"  號碼 {item['number']:2d}: 缺席 {item['current_gap']:2d} 期, "
              f"平均 {item['avg_gap']:.1f} 期, 比率 {item['gap_ratio']:.2f}")

    # 測試共識預測
    consensus = ConsensusPredictor()
    result = consensus.predict(history, rules)
    print(f"\n共識預測: {result['numbers']}")
    print(f"共識程度: {result['consensus_level']}")
