"""
近鄰擾動優化器 (Wobble Optimizer) - P2增強版
核心理念：將「接近」轉化為「命中」。
當預測模型已正確定位能量區間（能量聚集於 ±1 鄰域）時，通過微調生成的注項來覆蓋物理誤差。

P2優化 (2026-01-04):
- 智能擾動：根據號碼頻率和遺漏值決定擾動優先級
- 方向性擾動：向熱門區域擾動
- 共現感知擾動：優先擾動到共現頻繁的號碼
"""

import random
from typing import List, Set, Dict, Optional
from collections import Counter


class WobbleOptimizer:
    def __init__(self, min_num: int = 1, max_num: int = 49):
        self.min_num = min_num
        self.max_num = max_num
        self._freq_cache = None
        self._cooccurrence_cache = None

    def set_history(self, history: List[Dict]):
        """設置歷史數據用於智能擾動"""
        self._history = history
        self._build_freq_cache()
        self._build_cooccurrence_cache()

    def _build_freq_cache(self):
        """建立號碼頻率緩存"""
        if not hasattr(self, '_history') or not self._history:
            self._freq_cache = {}
            return

        self._freq_cache = Counter()
        for d in self._history[:200]:
            self._freq_cache.update(d['numbers'])

    def _build_cooccurrence_cache(self):
        """建立號碼共現緩存"""
        if not hasattr(self, '_history') or not self._history:
            self._cooccurrence_cache = {}
            return

        from itertools import combinations
        self._cooccurrence_cache = Counter()
        for d in self._history[:200]:
            for pair in combinations(sorted(d['numbers']), 2):
                self._cooccurrence_cache[pair] += 1

    def generate_wobble_bets(self, base_bet: List[int], num_bets: int = 6) -> List[List[int]]:
        """
        基於基礎注項生成擾動變體
        """
        base_bet = sorted(list(set(base_bet)))
        bets = [base_bet] # 第一注永遠是原始預測

        if len(bets) >= num_bets:
            return bets[:num_bets]

        # 生成變體
        attempts = 0
        while len(bets) < num_bets and attempts < 100:
            attempts += 1
            new_bet = list(base_bet)

            # 隨機選擇 1 到 2 個位置進行擾動
            num_to_wobble = random.choice([1, 1, 2]) # 傾向於只動一個，保證「接近」的結構不被破壞
            indices = random.sample(range(len(new_bet)), num_to_wobble)

            valid_wobble = True
            for idx in indices:
                offset = random.choice([-1, 1])
                new_val = new_bet[idx] + offset

                # 檢查邊界與重複
                if new_val < self.min_num or new_val > self.max_num or new_val in new_bet:
                    valid_wobble = False
                    break
                new_bet[idx] = new_val

            if valid_wobble:
                new_bet_sorted = sorted(new_bet)
                if new_bet_sorted not in bets:
                    bets.append(new_bet_sorted)

        return bets

    def systematic_wobble(self, base_bet: List[int], num_bets: int = 6) -> List[List[int]]:
        """
        系統化擾動：優先對「遺留度」或「不確定性」高的號碼進行鄰域擴展
        """
        # 這裡可以傳入號碼的 confidence，但暫時使用均等機會
        base_bet = sorted(list(set(base_bet)))
        bets = [base_bet]

        # 遍歷每個號碼的 +1, -1 鄰居
        neighbors = []
        for i, num in enumerate(base_bet):
            for offset in [-1, 1]:
                neighbor_val = num + offset
                if self.min_num <= neighbor_val <= self.max_num and neighbor_val not in base_bet:
                    # 創建一個變體：替換第 i 個號碼
                    variant = list(base_bet)
                    variant[i] = neighbor_val
                    neighbors.append(sorted(variant))

        # 隨機或按某種準則從鄰居中選取
        random.shuffle(neighbors)
        for n in neighbors:
            if len(bets) >= num_bets:
                break
            if n not in bets:
                bets.append(n)

        return bets

    # ========================================================================
    # 🔥 P2優化: 智能擾動方法 (2026-01-04)
    # ========================================================================

    def smart_wobble(self, base_bet: List[int], num_bets: int = 6,
                     history: Optional[List[Dict]] = None) -> List[List[int]]:
        """
        智能擾動策略 - P2優化

        原理：
        1. 計算每個號碼的「擾動價值」= 鄰域頻率 + 共現加成
        2. 優先擾動價值高的號碼
        3. 向更熱門的方向擾動

        Args:
            base_bet: 基礎注項
            num_bets: 生成注數
            history: 歷史數據（用於計算頻率）

        Returns:
            擾動後的注項列表
        """
        if history:
            self.set_history(history)

        base_bet = sorted(list(set(base_bet)))
        bets = [base_bet]

        if len(bets) >= num_bets:
            return bets[:num_bets]

        # 計算每個位置的擾動候選及其價值
        wobble_candidates = []

        for i, num in enumerate(base_bet):
            for offset in [-1, 1]:
                neighbor_val = num + offset
                if self.min_num <= neighbor_val <= self.max_num and neighbor_val not in base_bet:
                    # 計算擾動價值
                    value = self._calculate_wobble_value(num, neighbor_val, base_bet)
                    wobble_candidates.append({
                        'position': i,
                        'original': num,
                        'target': neighbor_val,
                        'offset': offset,
                        'value': value
                    })

        # 按價值排序（高價值優先）
        wobble_candidates.sort(key=lambda x: -x['value'])

        # 生成變體
        used_combos = {tuple(base_bet)}

        for candidate in wobble_candidates:
            if len(bets) >= num_bets:
                break

            variant = list(base_bet)
            variant[candidate['position']] = candidate['target']
            variant_sorted = sorted(variant)
            variant_tuple = tuple(variant_sorted)

            if variant_tuple not in used_combos:
                bets.append(variant_sorted)
                used_combos.add(variant_tuple)

        # 如果還不夠，進行雙重擾動
        if len(bets) < num_bets:
            for i, cand1 in enumerate(wobble_candidates):
                if len(bets) >= num_bets:
                    break
                for cand2 in wobble_candidates[i+1:]:
                    if len(bets) >= num_bets:
                        break
                    if cand1['position'] == cand2['position']:
                        continue

                    variant = list(base_bet)
                    variant[cand1['position']] = cand1['target']
                    variant[cand2['position']] = cand2['target']
                    variant_sorted = sorted(variant)
                    variant_tuple = tuple(variant_sorted)

                    if variant_tuple not in used_combos:
                        bets.append(variant_sorted)
                        used_combos.add(variant_tuple)

        return bets[:num_bets]

    def _calculate_wobble_value(self, original: int, target: int, base_bet: List[int]) -> float:
        """
        計算擾動價值

        價值 = 目標頻率 + 共現加成 - 原始頻率差異懲罰
        """
        value = 0.0

        # 1. 目標號碼頻率加成
        if self._freq_cache:
            target_freq = self._freq_cache.get(target, 0)
            original_freq = self._freq_cache.get(original, 0)
            avg_freq = sum(self._freq_cache.values()) / max(len(self._freq_cache), 1)

            # 如果目標比原始更熱門，加分
            if target_freq > original_freq:
                value += (target_freq - original_freq) / max(avg_freq, 1) * 10
            else:
                value -= (original_freq - target_freq) / max(avg_freq, 1) * 5

        # 2. 共現加成：目標與其他號碼的共現頻率
        if self._cooccurrence_cache:
            cooccur_score = 0
            for other in base_bet:
                if other != original:
                    pair = tuple(sorted([target, other]))
                    cooccur_score += self._cooccurrence_cache.get(pair, 0)
            value += cooccur_score * 0.5

        # 3. 邊界號碼微調（避免極端號碼）
        if target <= 5 or target >= self.max_num - 4:
            value -= 2  # 極端號碼懲罰

        return value

    def cooccurrence_aware_wobble(self, base_bet: List[int], num_bets: int = 6,
                                   history: Optional[List[Dict]] = None) -> List[List[int]]:
        """
        共現感知擾動 - 優先擾動到與其他號碼共現頻繁的目標

        這個策略專門針對號碼社群結構，
        擾動時優先選擇與保留號碼有強共現關係的目標
        """
        if history:
            self.set_history(history)

        base_bet = sorted(list(set(base_bet)))
        bets = [base_bet]

        if not self._cooccurrence_cache:
            # 沒有共現數據，回退到普通擾動
            return self.systematic_wobble(base_bet, num_bets)

        # 對每個號碼，找到最佳的替換目標
        replacements = []

        for i, num in enumerate(base_bet):
            other_nums = [n for n in base_bet if n != num]

            # 找鄰域內共現分數最高的替換
            best_target = None
            best_score = -1

            for offset in [-1, 1]:
                target = num + offset
                if self.min_num <= target <= self.max_num and target not in base_bet:
                    # 計算與其他號碼的總共現分數
                    score = sum(
                        self._cooccurrence_cache.get(tuple(sorted([target, other])), 0)
                        for other in other_nums
                    )
                    if score > best_score:
                        best_score = score
                        best_target = target

            if best_target is not None:
                replacements.append({
                    'position': i,
                    'target': best_target,
                    'score': best_score
                })

        # 按共現分數排序
        replacements.sort(key=lambda x: -x['score'])

        # 生成變體
        used = {tuple(base_bet)}
        for rep in replacements:
            if len(bets) >= num_bets:
                break
            variant = list(base_bet)
            variant[rep['position']] = rep['target']
            variant_sorted = sorted(variant)
            if tuple(variant_sorted) not in used:
                bets.append(variant_sorted)
                used.add(tuple(variant_sorted))

        return bets[:num_bets]
