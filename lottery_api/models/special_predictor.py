import random
import logging
import numpy as np
from typing import List, Dict, Optional
from collections import Counter, defaultdict
from .markov_2nd_special_predictor import MarkovChain2ndOrderPredictor

logger = logging.getLogger(__name__)

class PowerLottoSpecialPredictor:
    """
    威力彩第二區 (Section 2) 專屬預測器
    優化版：多策略融合 + 動態權重調整
    """
    def __init__(self, lottery_rules: Dict):
        self.min_num = lottery_rules.get('specialMinNumber', 1)
        self.max_num = lottery_rules.get('specialMaxNumber', 8)
        self.lottery_type = lottery_rules.get('name', '')
        self._weight_cache = {}
        self._shared_strategy_cache = {}
        self.markov2nd = MarkovChain2ndOrderPredictor() # ✨ Phase Zone2 Optimization

    def _ensure_asc(self, history: List[Dict]) -> List[Dict]:
        if not history: return history
        if history[0].get('date', '0') > history[-1].get('date', '9'):
            return list(reversed(history))
        return history

    def predict(self, history: List[Dict], main_numbers: List[int] = None) -> int:
        """預測最可能的單個第二區號碼"""
        history = self._ensure_asc(history)
        top_n = self.predict_top_n(history, n=1, main_numbers=main_numbers)
        return top_n[0]

    

    def _get_strategy_scores(self, strategy_id: str, history: List[Dict], main_numbers: List[int] = None) -> Dict[int, float]:
        """使用快取獲取策略分數"""
        if not history:
            return {num: 0.5 for num in range(self.min_num, self.max_num + 1)}
            
        draw_id = history[-1].get('draw')
        h_len = len(history)
        # 針對 sectional_corr，主號也是 key 的一部分
        main_key = tuple(sorted(main_numbers)) if main_numbers else None
        cache_key = (strategy_id, draw_id, h_len, main_key)
        
        if cache_key in self._shared_strategy_cache:
            return self._shared_strategy_cache[cache_key]
            
        # 執行實際策略
        if strategy_id == 'bias': res = self._calculate_long_term_bias(history)
        elif strategy_id == 'markov': res = self._markov_v1_strategy(history)
        elif strategy_id == 'hot': res = self._recent_hot_strategy(history[-15:])
        elif strategy_id == 'cycle': res = self._cycle_v2_strategy(history)
        elif strategy_id == 'corr': res = self._sectional_correlation_strategy(history, main_numbers)
        elif strategy_id == 'seasonal': res = self._seasonal_bias_strategy(history)
        elif strategy_id == 'gap': res = self._gap_pressure_strategy(history)
        elif strategy_id == 'fourier': res = self._fourier_rhythm_strategy_exec(history)
        elif strategy_id in ('oscillation', 'repeat'): res = self._oscillation_booster_strategy(history)
        elif strategy_id == 'sgp': res = self._spectral_gap_pressure_strategy(history)
        elif strategy_id == 'zonal_lift': res = self._zonal_sectional_lift_strategy(history)
        elif strategy_id == 'markov2nd': res = self.markov2nd.predict_with_confidence(history)['probabilities']
        elif strategy_id == 'modulo': res = self._modulo_parity_strategy(history)
        else: res = {num: 0.5 for num in range(self.min_num, self.max_num + 1)}
        
        # 限制快取
        if len(self._shared_strategy_cache) > 5000:
            self._shared_strategy_cache.clear()
            
        self._shared_strategy_cache[cache_key] = res
        return res

    def predict_top_n(self, history: List[Dict], n: int = 3, main_numbers: List[int] = None) -> List[int]:
        """
        預測前 N 個機率最高的第二區號碼 (Special V3 - RepeatBooster 增強版)
        """
        if not history:
            return [2, 5, 4][:n]
        history = self._ensure_asc(history)

        scores = {num: 0.0 for num in range(self.min_num, self.max_num + 1)}

        # 1. 獲取所有子策略的分數 (透過緩存包裝)
        bias_scores = self._get_strategy_scores('bias', history)
        markov_v1 = self._get_strategy_scores('markov', history)
        recent_hot = self._get_strategy_scores('hot', history)
        cycle = self._get_strategy_scores('cycle', history)
        sectional_corr = self._get_strategy_scores('corr', history, main_numbers)
        seasonal = self._get_strategy_scores('seasonal', history)
        gap_p = self._get_strategy_scores('gap', history)
        fourier = self._get_strategy_scores('fourier', history)
        oscillation = self._get_strategy_scores('oscillation', history)
        
        # 2. 獲取 Regime-Aware 混合權重
        weights = self._get_hybrid_regime_weights(history, main_numbers)
        
        for num in scores:
            scores[num] = (
                bias_scores[num] * weights['bias'] +
                markov_v1[num] * weights['markov'] +
                recent_hot[num] * weights['hot'] +
                cycle[num] * weights['cycle'] +
                sectional_corr[num] * weights['corr'] +
                seasonal[num] * weights['seasonal'] +
                gap_p[num] * weights['gap'] +
                fourier[num] * weights.get('fourier', 0.10) +
                oscillation[num] * weights.get('oscillation', 0.15) +
                self._get_strategy_scores('zonal_lift', history)[num] * weights.get('zonal_lift', 0.10) +
                self._get_strategy_scores('sgp', history)[num] * weights.get('sgp', 0.05) +
                self._get_strategy_scores('markov2nd', history)[num] * weights.get('markov2nd', 0.15) +
                self._get_strategy_scores('modulo', history)[num] * weights.get('modulo', 0.10)
            )

        # 排序並返回前 N 個
        sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_n = [item[0] for item in sorted_nums[:n]]

        # Cold Safety Net (020期優化): Gap≥20 的特別號強制納入候選
        # 回測驗證: Gap≥20 edge=+2.62% (最佳閾值)
        top_n = self._apply_cold_safety_net(history, top_n, gap_threshold=20)

        return top_n[:n]

    def _apply_cold_safety_net(self, history, top_n, gap_threshold=20):
        """Cold Safety Net: 極長遺漏特別號強制納入
        
        020期教訓: #8 連續21期未出, V3 MAB 未能預測
        Gap≥20 閾值是回測最佳點 (edge=+2.62%)
        """
        if not history:
            return top_n

        # history 已由 _ensure_asc 統一為 ASC (history[-1]=最新期)
        # 保留 LAST occurrence（最近），gap = len(history) - last_idx
        last_seen = {}
        for i, d in enumerate(history):
            sp_val = d.get('special')
            if sp_val:
                last_seen[sp_val] = i  # 持續覆蓋 → 最終保留最近出現的 index

        current_idx = len(history)
        cold_specials = []
        for n in range(self.min_num, self.max_num + 1):
            gap = current_idx - last_seen.get(n, -1)  # 從未出現 → len(history)+1
            if gap >= gap_threshold and n not in top_n:
                cold_specials.append((n, gap))

        if cold_specials:
            cold_specials.sort(key=lambda x: -x[1])
            coldest = cold_specials[0][0]
            # 替換 top_n 的最後一個
            result = list(top_n[:-1]) + [coldest]
            return result

        return top_n

    def _calculate_long_term_bias(self, history: List[Dict]) -> Dict[int, float]:
        """計算全歷史物理偏差"""
        # 根據 1875 期全歷史數據硬編碼的基礎偏差 (Base Prior)
        # 2: 14.0%, 5: 13.3%, 4: 13.0%, 3: 12.4%, 8: 11.9%, 7: 11.9%, 1: 11.8%, 6: 11.5% (約略)
        hardcoded_bias = {2: 1.0, 5: 0.9, 4: 0.85, 3: 0.8, 8: 0.7, 7: 0.7, 1: 0.65, 6: 0.5}
        
        # 如果歷史數據足夠長，則動態計算
        if len(history) > 500:
            specials = [d.get('special') for d in history if d.get('special')]
            counts = Counter(specials)
            return self._normalize({n: counts.get(n, 0) for n in range(1, 9)})
        
        return {n: hardcoded_bias.get(n, 0.5) for n in range(1, 9)}

    def _oscillation_booster_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """
        振盪增強引擎 (Oscillation Booster)
        不僅捕捉連開 (Repeat)，還識別 X -> Y -> X 振盪模式。
        """
        if not history: return {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        specials = [d.get('special') for d in reversed(history[-10:]) if d.get('special')]
        
        if len(specials) >= 1:
            # 1. 連開 (Repeat)
            last_s = specials[0]
            scores[last_s] += 0.5
            
            # 2. 振盪 (Oscillation: X -> Y -> X)
            if len(specials) >= 3:
                if specials[0] != specials[1] and specials[0] == specials[2]:
                    # 強烈振盪信號
                    scores[specials[0]] += 0.3
                    
            # 3. 三角回歸 (Triangle: X -> Y -> Z -> X)
            if len(specials) >= 4:
                if specials[0] == specials[3]:
                    scores[specials[0]] += 0.2
            
        return scores

    def _zonal_sectional_lift_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """
        🚀 Phase 62: Zonal Sectional Lift
        獲取主號區對特別號的跨區增益
        """
        from .zone_cluster import ZoneClusterRefiner
        refiner = ZoneClusterRefiner({'maxNumber': 38}) # Power Lotto
        return refiner.get_sectional_lift(history)

    def _spectral_gap_pressure_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """
        頻譜間隔壓力 (Spectral Gap Pressure - SGP)
        結合傅立葉主頻率週期 P 與當前遺漏 Gap。
        """
        if len(history) < 64: return {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        
        # 獲取基礎間隔得分
        gap_scores = self._gap_pressure_strategy(history)
        
        # 獲取傅立葉週期信息
        from .fourier_rhythm import fourier_predictor
        fourier_res = fourier_predictor.predict(history)
        
        scores = {}
        for n in range(self.min_num, self.max_num + 1):
            # 融合：如果傅立葉支持該號碼且間隔壓力大，則加乘
            # 本質是 P 與 Gap 的協同過濾
            scores[n] = gap_scores[n] * (1.0 + fourier_res.get(n, 0.125) * 2.0)
            
        return self._normalize(scores)

    def _modulo_parity_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """
        ✨ Phase Zone2 Optimization: Modulo & Parity Strategy
        基於近期 Odd/Even 趨勢與 Modulo 4 分佈進行預測。
        """
        if not history: return {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        recent_s = [d.get('special') for d in reversed(history[-10:]) if d.get('special')]
        
        if not recent_s: return scores
        
        # 1. Parity (Odd/Even Balance)
        odds = sum(1 for x in recent_s if x % 2 != 0)
        evens = len(recent_s) - odds
        
        # 如果最近嚴重失衡，則預期回歸
        if odds >= 7: # 過多奇數
            for n in range(1, 9):
                if n % 2 == 0: scores[n] += 0.3
        elif evens >= 7: # 過多偶數
            for n in range(1, 9):
                if n % 2 != 0: scores[n] += 0.3
                
        # 2. Modulo 4 Analysis (1-8 均勻分佈於 0,1,2,3 mod 4)
        mods = [x % 4 for x in recent_s]
        mod_counts = Counter(mods)
        for m in range(4):
            if mod_counts[m] == 0: # 該餘數近期未出
                for n in range(1, 9):
                    if n % 4 == m: scores[n] += 0.2
                    
        return self._normalize(scores)

    def _markov_v1_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """一階馬可夫鏈：A -> ? 的轉移概率"""
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        if not history: return scores
        
        specials = [d.get('special') for d in history if d.get('special')]
        if len(specials) < 2: return scores
        
        transitions = defaultdict(Counter)
        for i in range(len(specials) - 1):
            transitions[specials[i]][specials[i+1]] += 1
            
        last_num = specials[-1]
        if last_num in transitions:
            count_map = transitions[last_num]
            total = sum(count_map.values())
            for n, c in count_map.items():
                if self.min_num <= n <= self.max_num:
                    scores[n] = c / total
                    
        return self._normalize(scores)

    def _cycle_v2_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """威力彩專屬週期分析：針對 1-8 號的短間距規律"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if not history: return scores
        
        last_seen = {n: 99 for n in range(1, 9)}
        for i, d in enumerate(reversed(history)):
            s = d.get('special')
            if s and last_seen[s] == 99:
                last_seen[s] = i
                
        for n, gap in last_seen.items():
            # 1-8 號的平均間隔是 8。我們偏好間隔在 5-12 之間的號碼 (回暖區)
            if 5 <= gap <= 12: scores[n] = 1.0
            elif gap > 16: scores[n] = 0.5 # 遺漏過久，有壓力
            else: scores[n] = 0.2
            
        return scores

    def _anomaly_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """異常偏移偵測：計算每個號碼的 Z-score 分數"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if not history: return scores
        
        specials = [d.get('special') for d in history if d.get('special')]
        if not specials: return scores
        
        counts = Counter(specials)
        total = len(specials)
        avg = total / 8.0 # 1-8 均勻期望
        
        # 使用最近 20 期作為標竿，對比長期期望
        recent_counts = Counter(specials[-20:])
        
        for n in range(1, 9):
            # 長期偏移量
            long_term_diff = (counts.get(n, 0) - avg) / (avg**0.5 + 1)
            # 短期偏移量
            short_term_diff = (recent_counts.get(n, 0) - (20/8)) / ((20/8)**0.5 + 1)
            
            # 分數：捕捉正在「反彈」或「極端過熱」的信號
            # 我們這裡對長期冷號的中期反彈給予高分
            scores[n] = max(0, 0.5 - 0.2 * long_term_diff + 0.3 * short_term_diff)
            
        return self._normalize(scores)

    def _poisson_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """泊松分佈建模：預測在特定窗口內出現 X 次的概率"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if len(history) < 30: return scores
        
        specials = [d.get('special') for d in history if d.get('special')]
        # 計算 lambda (期望次數)
        lmbda = 10 / 8.0 # 在 10 期內的期望
        
        recent_10 = specials[-10:]
        recent_counts = Counter(recent_10)
        
        from scipy.stats import poisson
        for n in range(1, 9):
            # 如果最近 10 期出現 0 次，計算其概率
            # 概率越低 (1-P)，說明該號碼越「遲到」，反彈壓力越大
            k = recent_counts.get(n, 0)
            prob = poisson.pmf(k, lmbda)
            scores[n] = 1.0 - prob
            
        return self._normalize(scores)

    def _markov_high_order_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """2階馬可夫鏈：A -> B -> ? 的轉移概率"""
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        if len(history) < 50: return scores
        
        specials = [d.get('special') for d in history if d.get('special')]
        
        # 建立 2 階轉移矩陣
        transitions = defaultdict(Counter)
        for i in range(len(specials) - 2):
            key = (specials[i], specials[i+1])
            transitions[key][specials[i+2]] += 1
            
        # 獲取最近的兩個號碼
        last_pair = (specials[-2], specials[-1])
        if last_pair in transitions:
            count_map = transitions[last_pair]
            total = sum(count_map.values())
            for n, c in count_map.items():
                if self.min_num <= n <= self.max_num:
                    scores[n] = c / total
                    
        return self._normalize(scores)

    def _normalize(self, scores: Dict[int, float]) -> Dict[int, float]:
        """輔助函數：將分數正規化到 0-1"""
        if not scores: return {}
        vals = list(scores.values())
        min_v, max_v = min(vals), max(vals)
        if max_v > min_v:
            return {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}
        return {k: 0.5 for k in scores}

    def _recent_hot_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """近期熱號策略：最近出現過的號碼權重較高"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if not history:
            return scores

        for i, d in enumerate(reversed(history)):
            special = d.get('special')
            if special and self.min_num <= special <= self.max_num:
                weight = np.exp(-i * 0.2)
                scores[special] += weight

        # 正規化到 0-1
        max_score = max(scores.values()) if scores else 1
        if max_score > 0:
            scores = {k: v / max_score for k, v in scores.items()}

        return scores

    def _balance_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """平衡策略：出現次數較少的號碼權重較高"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if not history:
            return scores

        special_nums = [d.get('special') for d in history if d.get('special')]
        freq = Counter(special_nums)

        total = len(special_nums) if special_nums else 1
        expected = total / (self.max_num - self.min_num + 1)

        for num in range(self.min_num, self.max_num + 1):
            count = freq.get(num, 0)
            # 低於期望值的號碼獲得較高分數
            if expected > 0:
                deviation = (expected - count) / expected
                scores[num] = max(0, min(1, 0.5 + deviation * 0.5))
            else:
                scores[num] = 0.5

        return scores

    def _cycle_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """週期策略：分析號碼出現的週期性"""
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if len(history) < 10:
            return {n: 0.5 for n in range(self.min_num, self.max_num + 1)}

        for num in range(self.min_num, self.max_num + 1):
            # 找出這個號碼的出現位置
            positions = []
            for i, d in enumerate(history):
                if d.get('special') == num:
                    positions.append(i)

            if len(positions) >= 2:
                # 計算平均間隔
                intervals = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
                avg_interval = sum(intervals) / len(intervals)

                # 距離上次出現的期數
                last_gap = positions[0] if positions else len(history)

                # 如果接近平均間隔，給予較高分數
                if avg_interval > 0:
                    cycle_score = 1 - abs(last_gap - avg_interval) / avg_interval
                    scores[num] = max(0, min(1, cycle_score))
            else:
                scores[num] = 0.3  # 出現太少次，給予中等分數

        return scores

    def _trend_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """趨勢策略：分析數值的上升/下降趨勢"""
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        if len(history) < 5:
            return scores

        special_nums = [d.get('special') for d in history[-10:] if d.get('special')]
        if len(special_nums) < 3:
            return scores

        # 計算最近的趨勢 (上升/下降)
        recent_avg = sum(special_nums[-5:]) / 5 if len(special_nums) >= 5 else sum(special_nums) / len(special_nums)

        # 如果趨勢向上，給高數字較高分數
        # 如果趨勢向下，給低數字較高分數
        mid = (self.min_num + self.max_num) / 2

        for num in range(self.min_num, self.max_num + 1):
            if recent_avg > mid:
                # 趨勢向上，但可能回調
                scores[num] = 0.5 + (num - mid) / (self.max_num - mid) * 0.3
            else:
                # 趨勢向下，但可能反彈
                scores[num] = 0.5 + (mid - num) / (mid - self.min_num) * 0.3

        return scores

    def _main_association_strategy(self, history: List[Dict], main_numbers: List[int]) -> Dict[int, float]:
        """主號關聯策略：分析主號與特別號的關聯"""
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        if not history or not main_numbers:
            return scores

        # 統計當主號包含某些數字時，特別號的分布
        relevant_specials = []
        for d in history:
            main = set(d.get('numbers', []))
            overlap = len(main & set(main_numbers))
            if overlap >= 2:  # 至少有2個號碼重疊
                special = d.get('special')
                if special:
                    relevant_specials.append(special)

        if relevant_specials:
            freq = Counter(relevant_specials)
            max_freq = max(freq.values())
            for num in range(self.min_num, self.max_num + 1):
                scores[num] = freq.get(num, 0) / max_freq if max_freq > 0 else 0.5

        return scores

    def _sectional_correlation_strategy(self, history: List[Dict], main_predicted: List[int]) -> Dict[int, float]:
        """
        V4 進化：基於主特關聯的概率提升策略
        當主號區出現特定號碼時，對對應的特別號概率進行偏移修正。
        """
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if not history or not main_predicted:
            return {n: 0.5 for n in range(self.min_num, self.max_num + 1)}

        # 使用最近 1000 期進行動態訓練關聯矩陣
        correlation_map = defaultdict(Counter)
        n_total_counts = Counter()
        s_global_counts = Counter()
        sample_history = history[:1000]
        
        for d in sample_history:
            s_num = d.get('special')
            if not s_num: continue
            s_global_counts[s_num] += 1
            nums = d.get('numbers', [])
            if isinstance(nums, str):
                import json
                nums = json.loads(nums) if nums.startswith('[') else [int(n) for n in nums.split(',')]
            
            for n in nums:
                correlation_map[n][s_num] += 1
                n_total_counts[n] += 1
        
        # 根據預測的主號計算累積 Lift
        total_draws = len(sample_history)
        if total_draws == 0: return {n: 0.5 for n in range(self.min_num, self.max_num + 1)}

        lift_sum = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        for n in main_predicted:
            if n in correlation_map:
                n_count = n_total_counts[n]
                for s, count in correlation_map[n].items():
                    exp_prob = s_global_counts[s] / total_draws
                    obs_prob = count / n_count
                    if exp_prob > 0:
                        # 只有當觀測概率顯著高於期望時才加分
                        lift_sum[s] += (obs_prob / exp_prob - 1.0)

        # 將 Lift 映射到 0-1 區間
        return self._normalize({s: 1.0 + l for s, l in lift_sum.items()})

    def _seasonal_bias_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """
        V5 進化：月份與季節性偏差
        特定月份會對特定號碼產生額外權重 (例如 3 月對 Special 2 的 18% 強烈偏移)。
        """
        scores = {n: 0.5 for n in range(self.min_num, self.max_num + 1)}
        if not history: return scores
        
        from datetime import datetime
        # 獲取「當前預測月份」 (取歷史最後一期的下一個月份)
        try:
            last_date_str = history[0].get('date', '')
            if '/' in last_date_str: last_date = datetime.strptime(last_date_str, '%Y/%m/%d')
            else: last_date = datetime.strptime(last_date_str, '%Y-%m-%d')
            current_month = last_date.month
        except:
            current_month = datetime.now().month

        # 動態計算該月份的歷史分布
        monthly_counts = Counter()
        total_for_month = 0
        for d in history:
            d_date_str = d.get('date', '')
            try:
                if '/' in d_date_str: d_month = datetime.strptime(d_date_str, '%Y/%m/%d').month
                else: d_month = datetime.strptime(d_date_str, '%Y-%m-%d').month
                if d_month == current_month:
                    s = d.get('special')
                    if s:
                        monthly_counts[s] += 1
                        total_for_month += 1
            except: continue

        if total_for_month > 50:
            for n in range(1, 9):
                scores[n] = monthly_counts.get(n, 0) / total_for_month
                
        return self._normalize(scores)

    def _gap_pressure_strategy(self, history: List[Dict]) -> Dict[int, float]:
        """
        V5 進化：間隔壓力 (Gap Pressure)
        當一個號碼遺漏期數接近或超過其歷史最大遺漏值時，回歸壓力增大。
        """
        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}
        if len(history) < 200: return scores
        
        specials = [d.get('special') for d in history if d.get('special')]
        
        # 1. 計算每個號碼的歷史最大遺漏與平均遺漏
        max_gaps = {n: 0 for n in range(1, 9)}
        avg_gaps = {n: 8.0 for n in range(1, 9)}
        
        for n in range(1, 9):
            n_indices = [i for i, x in enumerate(specials) if x == n]
            if len(n_indices) > 2:
                gaps = [n_indices[i] - n_indices[i-1] for i in range(1, len(n_indices))]
                max_gaps[n] = max(gaps)
                avg_gaps[n] = sum(gaps) / len(gaps)
        
        # 2. 獲取當前遺漏期數
        current_gaps = {n: 99 for n in range(1, 9)}
        for n in range(1, 9):
            try: current_gaps[n] = len(specials) - 1 - max(i for i, x in enumerate(specials) if x == n)
            except: pass
            
        # 3. 計算壓力得分
        for n in range(1, 9):
            c_gap = current_gaps[n]
            m_gap = max_gaps[n]
            a_gap = avg_gaps[n]
            
            # 如果目前遺漏已經超過平均遺漏，開始施壓
            if c_gap > a_gap:
                # 壓力隨接近最大遺漏線性增加
                # 若超過最大遺漏，則維持最高壓力 1.0
                pressure = min(1.0, (c_gap - a_gap) / (max(1, m_gap - a_gap)))
                scores[n] = pressure
            else:
                scores[n] = 0.1
                
        return scores

    def _get_hybrid_regime_weights(self, history: List[Dict], main_numbers: List[int]) -> Dict[str, float]:
        """
        貝式環境切換 (Regime-Aware Hybrid Weights)
        根據近期熵值判斷環境，動態調整權重。
        """
        mab_weights = self._get_mab_weights(history, main_numbers)
        
        if len(history) < 20: return mab_weights
        
        # 1. 計算局部熵值 (Local Entropy)
        recent_s = [d.get('special') for d in history[-15:] if d.get('special')]
        counts = Counter(recent_s)
        probs = [c/len(recent_s) for c in counts.values()]
        entropy = -sum(p * np.log2(p) for p in probs)
        
        # 威力彩 1-8 碼均勻熵約為 3.0
        # 熵值低 (< 2.2) 代表規律性強 (連開、振盪多) -> 偏重 Oscillation
        # 熵值高 (> 2.8) 代表紊亂期 -> 偏重 Spectral Gap / Bias
        
        regime_weights = mab_weights.copy()
        
        if entropy < 2.2:
            # 規律期：加強振盪與馬可夫
            regime_weights['oscillation'] = regime_weights.get('repeat', 0.15) * 1.5
            regime_weights['markov'] = regime_weights['markov'] * 1.2
            regime_weights['sgp'] = 0.05
        elif entropy > 2.8:
            # 紊亂期：加強間隔與基礎統計
            regime_weights['sgp'] = 0.20
            regime_weights['gap'] = regime_weights['gap'] * 1.5
            regime_weights['bias'] = regime_weights['bias'] * 1.3
            regime_weights['oscillation'] = 0.05
        else:
            # 過渡期：使用 MAB 權重
            regime_weights['oscillation'] = regime_weights.get('repeat', 0.15)
            regime_weights['sgp'] = 0.10
            
        return regime_weights

    def _get_mab_weights(self, history: List[Dict], main_numbers: List[int]) -> Dict[str, float]:
        """
        多臂老虎機 (MAB) 基於歷史表現動態調整權重
        """
        default_weights = {
            'bias': 0.10, 'markov': 0.10, 'hot': 0.08, 
            'cycle': 0.07, 'corr': 0.12, 'seasonal': 0.08, 'gap': 0.10,
            'fourier': 0.10, 'oscillation': 0.15, 'sgp': 0.05,
            'markov2nd': 0.15, 'modulo': 0.10
        }
        
        if len(history) < 100:
            return default_weights

        # 緩存檢查
        cache_key = f"{history[0].get('draw')}_{len(history)}"
        if cache_key in self._weight_cache:
            return self._weight_cache[cache_key]
        # 初始化 Alpha (成功數) / Total (樣本數)
        arms = {k: {'win': 1, 'total': 2} for k in list(default_weights.keys())}
        
        # 為了效能，我們只測試最近 20 期
        for i in range(20):
            if len(history) - 1 - i < 0: break
            target = history[-(i+1)]
            # 使用滑動窗口，確保不洩露當前測試期的資訊 (取 target 之前的 150 期)
            prev_history = history[max(0, len(history)-151-i):-(i+1)] 
            actual = target.get('special')
            
            if not actual: continue
            
            # 各子策略獨立測試 (Top-2 涵蓋率作為 Reward)
            if actual in [item[0] for item in sorted(self._get_strategy_scores('bias', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['bias']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('markov', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['markov']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('hot', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['hot']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('cycle', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['cycle']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('corr', prev_history, main_numbers or [1,2,3,4,5,6]).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['corr']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('seasonal', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['seasonal']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('gap', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['gap']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('fourier', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['fourier']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('oscillation', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['oscillation']['win'] += 1
            if actual in [item[0] for item in sorted(self._get_strategy_scores('sgp', prev_history).items(), key=lambda x:x[1], reverse=True)[:2]]:
                arms['sgp']['win'] += 1
            
            for k in arms: arms[k]['total'] += 1

        # 2. 計算比例權重 (Win Rate 正規化)
        raw_win_rates = {k: arms[k]['win'] / arms[k]['total'] for k in arms}
        total_sum = sum(raw_win_rates.values())
        
        # 3. 混合默認權重 (防止過度波動，保持穩定性)
        mab_factor = 0.5
        final_weights = {}
        for k in default_weights:
            final_weights[k] = (raw_win_rates[k]/total_sum) * mab_factor + default_weights[k] * (1.0 - mab_factor)
            
        self._weight_cache[cache_key] = final_weights
        return final_weights

    def _fourier_rhythm_strategy_exec(self, history: List[Dict]) -> Dict[int, float]:
        """傅立葉規律策略 (Phase 39) - 實際執行"""
        from .fourier_rhythm import fourier_predictor
        return fourier_predictor.predict(history)


def get_enhanced_special_prediction(history: List[Dict], lottery_rules: Dict, main_predicted: List[int] = None) -> int:
    """
    獲取增強版特別號預測 (僅限威力彩)
    """
    lottery_name = lottery_rules.get('name', '')
    if 'POWER_LOTTO' in lottery_name or '威力彩' in lottery_name:
        predictor = PowerLottoSpecialPredictor(lottery_rules)
        return predictor.predict(history, main_numbers=main_predicted)
    return None
