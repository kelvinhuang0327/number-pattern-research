"""
超級優化預測器 (Ultra Optimized Predictor)

基於歷史數據深度分析設計的預測方法，整合多種統計約束：
1. 和值約束: 根據彩券類型調整
2. 奇偶比: 優先 3:3 或 4:2
3. 連號預測: 主動預測連號組合
4. 上期重複: 包含 1-2 個上期號碼
5. 區間平衡: 目標均衡分佈
6. 動態集成: 根據近期表現調整權重

支援彩券類型:
- POWER_LOTTO (威力彩): 1-38 選 6，特別號 1-8
- BIG_LOTTO (大樂透): 1-49 選 6
- DAILY_539 (今彩539): 1-39 選 5
"""

import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Tuple, Set, Optional
import random
from itertools import combinations


# 各彩券類型的統計約束參數
LOTTERY_CONSTRAINTS = {
    'POWER_LOTTO': {
        'name': '威力彩',
        'pick_count': 6,
        'min_number': 1,
        'max_number': 38,
        'sum_range': (55, 155),             # 和值範圍 (根據2025數據: 55-152, 平均112.6)
        'preferred_odd_counts': [3, 4, 2, 5],  # 優先的奇數個數 (3:31%, 4:25%, 2:18%, 5:11%)
        'consecutive_prob': 0.58,           # 連號機率 58% (2025實際: 57.9%)
        'repeat_prob': 0.74,                # 與上期重複機率 74% (2025: 至少1個重複佔74%)
        'zones': [(1, 12), (13, 25), (26, 38)],  # 區間定義
        'zone_target': [2, 2, 2],           # 理想區間分佈 (但不強制)
        'zone_strict': False,               # 不嚴格要求區間分佈
    },
    'BIG_LOTTO': {
        'name': '大樂透',
        'pick_count': 6,
        'min_number': 1,
        'max_number': 49,
        'sum_range': (120, 180),
        'preferred_odd_counts': [3, 4, 2],
        'consecutive_prob': 0.55,
        'repeat_prob': 0.50,
        'zones': [(1, 16), (17, 33), (34, 49)],
        'zone_target': [2, 2, 2],
    },
    'DAILY_539': {
        'name': '今彩539',
        'pick_count': 5,
        'min_number': 1,
        'max_number': 39,
        'sum_range': (80, 130),
        'preferred_odd_counts': [2, 3],
        'consecutive_prob': 0.50,
        'repeat_prob': 0.45,
        'zones': [(1, 13), (14, 26), (27, 39)],
        'zone_target': [1, 2, 2],
    },
    'DEFAULT': {
        'name': '預設',
        'pick_count': 6,
        'min_number': 1,
        'max_number': 49,
        'sum_range': (100, 180),
        'preferred_odd_counts': [3, 4, 2],
        'consecutive_prob': 0.50,
        'repeat_prob': 0.50,
        'zones': [(1, 16), (17, 33), (34, 49)],
        'zone_target': [2, 2, 2],
    }
}


def detect_lottery_type(lottery_rules: Dict, history: Optional[List[Dict]] = None) -> str:
    """
    根據規則和歷史數據自動偵測彩券類型

    Args:
        lottery_rules: 彩券規則
        history: 歷史數據 (可選)

    Returns:
        彩券類型代碼
    """
    # 優先從 lottery_rules 中獲取類型
    if 'lotteryType' in lottery_rules:
        lt = lottery_rules['lotteryType'].upper().replace('-', '_')
        if lt in LOTTERY_CONSTRAINTS:
            return lt

    # 根據規則參數判斷
    max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 49))
    pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
    has_special = lottery_rules.get('hasSpecialNumber', False)
    special_max = lottery_rules.get('specialNumberMax', 0)

    # 威力彩: 1-38 選 6，特別號 1-8
    if max_num == 38 and pick_count == 6 and (has_special or special_max == 8):
        return 'POWER_LOTTO'

    # 大樂透: 1-49 選 6
    if max_num == 49 and pick_count == 6:
        return 'BIG_LOTTO'

    # 今彩539: 1-39 選 5
    if max_num == 39 and pick_count == 5:
        return 'DAILY_539'

    # 從歷史數據推斷
    if history and len(history) > 0:
        sample_nums = history[0].get('numbers', [])
        max_in_history = max(sample_nums) if sample_nums else 49
        pick_in_history = len(sample_nums)

        if max_in_history <= 38 and pick_in_history == 6:
            return 'POWER_LOTTO'
        if max_in_history <= 39 and pick_in_history == 5:
            return 'DAILY_539'

    return 'DEFAULT'


class UltraOptimizedPredictor:
    """
    超級優化預測器

    自動偵測彩券類型並套用對應的統計約束
    """

    def __init__(self, lottery_type: Optional[str] = None):
        """
        初始化預測器

        Args:
            lottery_type: 指定彩券類型，若為 None 則自動偵測
        """
        self.name = "UltraOptimizedPredictor"
        self.fixed_lottery_type = lottery_type
        self.constraints = None  # 延遲載入

    def _get_constraints(self, lottery_rules: Dict, history: List[Dict] = None) -> Dict:
        """獲取對應彩券類型的約束參數"""
        if self.fixed_lottery_type:
            lottery_type = self.fixed_lottery_type
        else:
            lottery_type = detect_lottery_type(lottery_rules, history)

        self.current_lottery_type = lottery_type
        return LOTTERY_CONSTRAINTS.get(lottery_type, LOTTERY_CONSTRAINTS['DEFAULT'])

    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """
        主預測方法 - 綜合所有優化策略

        自動偵測彩券類型並套用對應約束
        """
        # 獲取彩券類型專屬約束
        constraints = self._get_constraints(lottery_rules, history)

        pick_count = constraints['pick_count']
        min_num = constraints['min_number']
        max_num = constraints['max_number']

        if len(history) < 50:
            return {
                'numbers': random.sample(range(min_num, max_num + 1), pick_count),
                'confidence': 0.5,
                'method': 'ultra_optimized_random',
                'lottery_type': self.current_lottery_type
            }

        # 收集各策略的候選號碼和分數
        candidate_scores = self._calculate_candidate_scores(history, constraints)

        # 生成多組候選組合，選擇最優
        best_combo = None
        best_score = -float('inf')

        # 嘗試生成符合約束的組合
        for _ in range(2000):
            combo = self._generate_constrained_combo(
                candidate_scores, history, constraints
            )
            if combo:
                score = self._evaluate_combo(combo, candidate_scores, history, constraints)
                if score > best_score:
                    best_score = score
                    best_combo = combo

        if best_combo is None:
            # Fallback: 使用高分號碼
            sorted_nums = sorted(candidate_scores.keys(), key=lambda x: -candidate_scores[x])
            best_combo = sorted_nums[:pick_count]

        return {
            'numbers': sorted(best_combo),
            'confidence': min(0.85, 0.6 + best_score / 1000),
            'method': f'ultra_optimized_{self.current_lottery_type.lower()}',
            'lottery_type': self.current_lottery_type,
            'lottery_name': constraints['name']
        }

    def _calculate_candidate_scores(self, history: List[Dict],
                                    constraints: Dict) -> Dict[int, float]:
        """計算每個號碼的綜合分數"""
        min_num = constraints['min_number']
        max_num = constraints['max_number']

        scores = defaultdict(float)

        # 1. 頻率分數 (近50期)
        freq_50 = Counter()
        for h in history[:50]:
            for n in h['numbers']:
                freq_50[n] += 1

        # 2. 近期趨勢 (近10期) - 加重權重
        freq_10 = Counter()
        for h in history[:10]:
            for n in h['numbers']:
                freq_10[n] += 1

        # 3. 極近期趨勢 (近5期) - 更高權重
        freq_5 = Counter()
        for h in history[:5]:
            for n in h['numbers']:
                freq_5[n] += 1

        # 4. 冷號回歸分數
        gap_scores = self._calculate_gap_scores(history, constraints)

        # 5. 配對頻率分數
        pair_freq = self._calculate_pair_frequency(history[:100])

        # 6. 週期性分析 (某些號碼有規律出現)
        cycle_scores = self._calculate_cycle_scores(history, constraints)

        # 綜合計算
        for num in range(min_num, max_num + 1):
            # 頻率分數
            scores[num] += freq_50.get(num, 0) * 2
            scores[num] += freq_10.get(num, 0) * 8   # 增加近期權重
            scores[num] += freq_5.get(num, 0) * 12   # 極近期更高權重

            # 冷號回歸分數 (優先選擇即將回歸的號碼)
            scores[num] += gap_scores.get(num, 0) * 4

            # 週期性分數
            scores[num] += cycle_scores.get(num, 0) * 3

            # 熱門配對加成
            for other in range(min_num, max_num + 1):
                if other != num:
                    pair = tuple(sorted([num, other]))
                    scores[num] += pair_freq.get(pair, 0) * 0.5

        return dict(scores)

    def _calculate_cycle_scores(self, history: List[Dict],
                                constraints: Dict) -> Dict[int, float]:
        """計算號碼的週期性分數 - 某些號碼有規律間隔出現"""
        min_num = constraints['min_number']
        max_num = constraints['max_number']

        cycle_scores = {}

        for num in range(min_num, max_num + 1):
            # 找出該號碼的所有出現位置
            appearances = [i for i, h in enumerate(history) if num in h['numbers']]

            if len(appearances) < 3:
                cycle_scores[num] = 5
                continue

            # 計算間隔
            gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]

            if len(gaps) < 2:
                cycle_scores[num] = 5
                continue

            # 檢查間隔是否有規律 (標準差小表示規律性高)
            avg_gap = np.mean(gaps)
            std_gap = np.std(gaps)

            # 當前間隔
            current_gap = appearances[0] if appearances else 999

            # 計算與平均間隔的偏差
            if avg_gap > 0:
                deviation = abs(current_gap - avg_gap) / avg_gap
                regularity = 1 / (1 + std_gap)  # 間隔越規律，分數越高

                # 如果當前間隔接近平均間隔，且該號碼規律性高，給高分
                if deviation < 0.3 and regularity > 0.15:
                    cycle_scores[num] = 25
                elif deviation < 0.5 and regularity > 0.1:
                    cycle_scores[num] = 15
                else:
                    cycle_scores[num] = 5
            else:
                cycle_scores[num] = 5

        return cycle_scores

    def _calculate_gap_scores(self, history: List[Dict],
                              constraints: Dict) -> Dict[int, float]:
        """計算冷號回歸分數"""
        min_num = constraints['min_number']
        max_num = constraints['max_number']
        pick_count = constraints['pick_count']

        gap_scores = {}

        for num in range(min_num, max_num + 1):
            # 計算當前間隔
            current_gap = 0
            for h in history:
                if num in h['numbers']:
                    break
                current_gap += 1

            # 計算平均間隔
            appearances = [i for i, h in enumerate(history) if num in h['numbers']]
            if len(appearances) >= 2:
                gaps = [appearances[i+1] - appearances[i] for i in range(len(appearances)-1)]
                avg_gap = np.mean(gaps)
            else:
                avg_gap = max_num / pick_count  # 根據彩券類型計算預設平均間隔

            # 間隔比評分
            if avg_gap > 0:
                ratio = current_gap / avg_gap
                if 1.0 <= ratio < 1.5:
                    gap_scores[num] = 30  # 最佳回歸時機
                elif 1.5 <= ratio < 2.0:
                    gap_scores[num] = 25
                elif 0.8 <= ratio < 1.0:
                    gap_scores[num] = 20
                elif ratio >= 2.0:
                    gap_scores[num] = 15
                else:
                    gap_scores[num] = 5
            else:
                gap_scores[num] = 10

        return gap_scores

    def _calculate_pair_frequency(self, history: List[Dict]) -> Dict[Tuple[int, int], int]:
        """計算號碼配對出現頻率"""
        pair_freq = Counter()
        for h in history:
            nums = h['numbers']
            for pair in combinations(nums, 2):
                pair_freq[tuple(sorted(pair))] += 1
        return pair_freq

    def _generate_constrained_combo(self, candidate_scores: Dict[int, float],
                                    history: List[Dict],
                                    constraints: Dict) -> List[int]:
        """生成符合約束條件的組合"""
        min_num = constraints['min_number']
        max_num = constraints['max_number']
        pick_count = constraints['pick_count']
        consecutive_prob = constraints['consecutive_prob']
        repeat_prob = constraints['repeat_prob']

        last_numbers = set(history[0]['numbers']) if history else set()

        # 準備候選池
        all_nums = list(range(min_num, max_num + 1))
        weights = [candidate_scores.get(n, 1) + 1 for n in all_nums]
        total_weight = sum(weights)
        probs = [w / total_weight for w in weights]

        # 嘗試生成
        for _ in range(50):
            selected = set()

            # 策略1: 根據彩券類型的重複機率決定是否加入上期號碼
            # 2025數據顯示 74% 有至少1個重複
            if random.random() < repeat_prob:
                repeat_count = random.choice([1, 1, 2])  # 偏向1個
                last_nums_list = list(last_numbers & set(all_nums))
                if last_nums_list:
                    # 從上期號碼中加權選擇（高分號碼機率較高但非強制）
                    last_weights = [candidate_scores.get(n, 1) + 50 for n in last_nums_list]
                    total_w = sum(last_weights)
                    last_probs = [w / total_w for w in last_weights]
                    chosen_repeats = np.random.choice(
                        last_nums_list,
                        size=min(repeat_count, len(last_nums_list)),
                        replace=False,
                        p=last_probs
                    )
                    selected.update(chosen_repeats)

            # 策略2: 根據彩券類型的連號機率決定是否加入連號
            # 2025數據顯示 58% 有連號
            if random.random() < consecutive_prob:
                # 隨機選擇起始點，但給高分區域較高機率
                consecutive_starts = list(range(min_num, max_num))
                start_weights = [candidate_scores.get(s, 0) + candidate_scores.get(s+1, 0) + 10
                                for s in consecutive_starts]
                total_w = sum(start_weights)
                start_probs = [w / total_w for w in start_weights]

                consecutive_start = np.random.choice(consecutive_starts, p=start_probs)

                if consecutive_start not in selected and (consecutive_start + 1) not in selected:
                    selected.add(consecutive_start)
                    selected.add(consecutive_start + 1)

            # 策略3: 填充剩餘號碼
            remaining_nums = [n for n in all_nums if n not in selected]
            remaining_weights = [candidate_scores.get(n, 1) + 1 for n in remaining_nums]
            total_w = sum(remaining_weights)
            remaining_probs = [w / total_w for w in remaining_weights]

            while len(selected) < pick_count and remaining_nums:
                chosen = np.random.choice(remaining_nums, p=remaining_probs)
                selected.add(chosen)
                idx = remaining_nums.index(chosen)
                remaining_nums.pop(idx)
                remaining_probs.pop(idx)
                if remaining_probs:
                    total_w = sum(remaining_probs)
                    remaining_probs = [p / total_w for p in remaining_probs]

            if len(selected) == pick_count:
                combo = list(selected)
                # 檢查約束條件
                if self._check_constraints(combo, constraints):
                    return combo

        return None

    def _check_constraints(self, combo: List[int], constraints: Dict) -> bool:
        """檢查組合是否符合約束條件 (根據彩券類型)"""
        sum_range = constraints['sum_range']
        preferred_odd_counts = constraints['preferred_odd_counts']
        zones = constraints['zones']
        pick_count = constraints['pick_count']
        zone_strict = constraints.get('zone_strict', True)

        # 1. 和值約束 (寬鬆)
        total_sum = sum(combo)
        if not (sum_range[0] <= total_sum <= sum_range[1]):
            return False

        # 2. 奇偶比約束 (寬鬆 - 接受 0-6 任何值)
        odd_count = sum(1 for n in combo if n % 2 == 1)
        if odd_count not in preferred_odd_counts:
            # 允許不在優先列表但不是極端值 (0 或 6)
            if odd_count == 0 or odd_count == pick_count:
                return False

        # 3. 區間分佈約束 (根據 zone_strict 設定)
        zone_counts = []
        for zone_min, zone_max in zones:
            count = sum(1 for n in combo if zone_min <= n <= zone_max)
            zone_counts.append(count)

        if zone_strict:
            # 嚴格模式：每個區間至少1個
            max_per_zone = (pick_count // 2) + 1
            for count in zone_counts:
                if count == 0:
                    return False
                if count > max_per_zone:
                    return False
        else:
            # 寬鬆模式：只要不是全部集中在一個區間
            if max(zone_counts) >= pick_count:
                return False

        return True

    def _evaluate_combo(self, combo: List[int],
                        candidate_scores: Dict[int, float],
                        history: List[Dict],
                        constraints: Dict) -> float:
        """評估組合的綜合分數 (根據彩券類型)"""
        score = 0
        sum_range = constraints['sum_range']
        preferred_odd_counts = constraints['preferred_odd_counts']

        # 1. 候選分數總和
        score += sum(candidate_scores.get(n, 0) for n in combo)

        # 2. 連號加分
        sorted_combo = sorted(combo)
        has_consecutive = any(sorted_combo[i+1] - sorted_combo[i] == 1
                             for i in range(len(sorted_combo) - 1))
        if has_consecutive:
            score += 50

        # 3. 與上期重複加分
        if history:
            last_nums = set(history[0]['numbers'])
            repeat_count = len(set(combo) & last_nums)
            if repeat_count in [1, 2]:
                score += 30

        # 4. 和值接近範圍中心加分
        combo_sum = sum(combo)
        sum_center = (sum_range[0] + sum_range[1]) / 2
        sum_diff = abs(combo_sum - sum_center)
        if sum_diff <= 10:
            score += 40
        elif sum_diff <= 20:
            score += 20

        # 5. 奇偶比符合最佳加分
        odd_count = sum(1 for n in combo if n % 2 == 1)
        if odd_count == preferred_odd_counts[0]:
            score += 30
        elif len(preferred_odd_counts) > 1 and odd_count == preferred_odd_counts[1]:
            score += 20

        return score

    def predict_multi_bet(self, history: List[Dict], lottery_rules: Dict,
                          num_bets: int = 6) -> Dict:
        """
        生成多組互補的預測號碼
        """
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 38))

        candidate_scores = self._calculate_candidate_scores(history, min_num, max_num)

        bets = []
        used_combos = set()

        # 不同策略生成不同組
        strategies = [
            ('balanced', self._generate_balanced_combo),
            ('hot_focused', self._generate_hot_focused_combo),
            ('cold_focused', self._generate_cold_focused_combo),
            ('consecutive', self._generate_consecutive_combo),
            ('zone_spread', self._generate_zone_spread_combo),
            ('random_constrained', self._generate_random_constrained_combo),
        ]

        for i in range(num_bets):
            strategy_name, strategy_func = strategies[i % len(strategies)]

            for _ in range(100):
                combo = strategy_func(history, candidate_scores, min_num, max_num, pick_count)
                if combo and tuple(sorted(combo)) not in used_combos:
                    used_combos.add(tuple(sorted(combo)))
                    bets.append({
                        'numbers': sorted(combo),
                        'strategy': strategy_name
                    })
                    break

        # 計算覆蓋率
        all_numbers = set()
        for bet in bets:
            all_numbers.update(bet['numbers'])

        return {
            'bets': bets,
            'total_bets': len(bets),
            'unique_numbers': len(all_numbers),
            'coverage_rate': len(all_numbers) / max_num,
            'method': 'ultra_optimized_multi_bet'
        }

    def _generate_balanced_combo(self, history, scores, min_num, max_num, pick_count):
        """平衡策略：各指標均衡"""
        return self._generate_constrained_combo(scores, history, min_num, max_num, pick_count)

    def _generate_hot_focused_combo(self, history, scores, min_num, max_num, pick_count):
        """熱門策略：偏重高頻號碼"""
        freq = Counter()
        for h in history[:30]:
            for n in h['numbers']:
                freq[n] += 1

        hot_scores = {n: scores.get(n, 0) + freq.get(n, 0) * 10 for n in range(min_num, max_num + 1)}
        return self._generate_constrained_combo(hot_scores, history, min_num, max_num, pick_count)

    def _generate_cold_focused_combo(self, history, scores, min_num, max_num, pick_count):
        """冷號策略：偏重冷號回歸"""
        gap_scores = self._calculate_gap_scores(history, min_num, max_num)
        cold_scores = {n: scores.get(n, 0) + gap_scores.get(n, 0) * 5 for n in range(min_num, max_num + 1)}
        return self._generate_constrained_combo(cold_scores, history, min_num, max_num, pick_count)

    def _generate_consecutive_combo(self, history, scores, min_num, max_num, pick_count):
        """連號策略：確保有連號"""
        for _ in range(50):
            combo = self._generate_constrained_combo(scores, history, min_num, max_num, pick_count)
            if combo:
                sorted_combo = sorted(combo)
                has_consecutive = any(sorted_combo[i+1] - sorted_combo[i] == 1
                                     for i in range(len(sorted_combo) - 1))
                if has_consecutive:
                    return combo
        return None

    def _generate_zone_spread_combo(self, history, scores, min_num, max_num, pick_count):
        """區間分散策略：確保 2-2-2 分佈"""
        for _ in range(100):
            zone1 = random.sample([n for n in range(1, 13)], 2)
            zone2 = random.sample([n for n in range(13, 26)], 2)
            zone3 = random.sample([n for n in range(26, 39) if n <= max_num], 2)
            combo = zone1 + zone2 + zone3
            if self._check_constraints(combo):
                return combo
        return None

    def _generate_random_constrained_combo(self, history, scores, min_num, max_num, pick_count):
        """隨機約束策略：隨機但符合約束"""
        for _ in range(100):
            combo = random.sample(range(min_num, max_num + 1), pick_count)
            if self._check_constraints(combo):
                return combo
        return None


# 動態權重集成預測器
class DynamicEnsemblePredictor:
    """
    動態權重集成預測器
    根據各方法近期表現動態調整權重
    """

    def __init__(self):
        self.name = "DynamicEnsemblePredictor"
        self.ultra = UltraOptimizedPredictor()

    def predict(self, history: List[Dict], lottery_rules: Dict) -> Dict:
        """使用動態權重集成預測"""
        pick_count = lottery_rules.get('pickCount', lottery_rules.get('pick_count', 6))
        min_num = lottery_rules.get('minNumber', lottery_rules.get('min_number', 1))
        max_num = lottery_rules.get('maxNumber', lottery_rules.get('max_number', 38))

        if len(history) < 100:
            return self.ultra.predict(history, lottery_rules)

        # 載入各預測器
        from models.enhanced_predictor import EnhancedPredictor
        from models.unified_predictor import prediction_engine

        enhanced = EnhancedPredictor()

        # 定義各預測方法
        methods = {
            'ultra': lambda h, r: self.ultra.predict(h, r),
            'cold_comeback': lambda h, r: enhanced.cold_number_comeback_predict(h, r),
            'temporal': lambda h, r: prediction_engine.temporal_predict(h, r),
            'frequency': lambda h, r: prediction_engine.frequency_predict(h, r),
            'enhanced_ensemble': lambda h, r: enhanced.enhanced_ensemble_predict(h, r),
        }

        # 計算各方法近期表現 (用過去20期驗證)
        method_scores = defaultdict(float)

        for i in range(20, min(40, len(history))):
            test_history = history[i+1:]  # 用於預測
            actual = set(history[i]['numbers'])  # 實際結果

            for method_name, method_func in methods.items():
                try:
                    result = method_func(test_history, lottery_rules)
                    predicted = set(result['numbers'][:pick_count])
                    matches = len(predicted & actual)
                    method_scores[method_name] += matches
                except:
                    pass

        # 正規化權重
        total_score = sum(method_scores.values())
        if total_score == 0:
            weights = {m: 1.0 / len(methods) for m in methods}
        else:
            weights = {m: s / total_score for m, s in method_scores.items()}

        # 收集各方法預測
        votes = Counter()

        for method_name, method_func in methods.items():
            try:
                result = method_func(history, lottery_rules)
                for num in result['numbers'][:pick_count]:
                    votes[num] += weights.get(method_name, 0.1) * 10
            except:
                pass

        # 選擇得分最高的號碼
        sorted_nums = sorted(votes.keys(), key=lambda x: -votes[x])

        # 應用約束條件選擇最佳組合
        best_combo = None
        best_score = -1

        for _ in range(500):
            # 從高分號碼中加權選擇
            top_candidates = sorted_nums[:20]
            selected = set()

            while len(selected) < pick_count and top_candidates:
                weights_list = [votes.get(n, 1) + 1 for n in top_candidates if n not in selected]
                if not weights_list:
                    break
                remaining = [n for n in top_candidates if n not in selected]
                total_w = sum(weights_list)
                probs = [w / total_w for w in weights_list]
                chosen = np.random.choice(remaining, p=probs)
                selected.add(chosen)

            if len(selected) == pick_count:
                combo = list(selected)
                if self.ultra._check_constraints(combo):
                    score = sum(votes.get(n, 0) for n in combo)
                    if score > best_score:
                        best_score = score
                        best_combo = combo

        if best_combo is None:
            best_combo = sorted_nums[:pick_count]

        return {
            'numbers': sorted(best_combo),
            'confidence': 0.75,
            'method': 'dynamic_ensemble_v1',
            'weights': weights
        }
