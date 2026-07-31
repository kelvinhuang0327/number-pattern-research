import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Any
from itertools import combinations
import logging
import random

logger = logging.getLogger(__name__)

class SGPStrategy:
    """
    Spectral Gap Pressure (SGP) Strategy - Phase 68 (Orthogonal Hybrid)
    V11 正交混合版：
    1. 信號正交：Bet 1 (時間週期) vs Bet 2 (空間分佈) vs Bet 3 (時空轉折)。
    2. 核心修正：Bet 2 改回 PP3 成功的 Echo/Cold 空間分散模型，修正 V10 的 Fourier 重疊錯誤。
    3. SGP 增強：Bet 3 作為補償注，使用 Period-Gap Pressure 與長效共現矩陣。
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self._synergy_cache = {} # (draw_id, lookback): matrix
        
    def detect_regime(self, history: List[Dict]) -> str:
        """
        環境偵測器 (Regime Detector)
        """
        if len(history) < 10: return "STABLE"
            
        echo_indices = []
        for i in range(min(10, len(history)-1)):
            overlap = len(set(history[i]['numbers']) & set(history[i+1]['numbers']))
            echo_indices.append(overlap)
        avg_echo = np.mean(echo_indices)
        
        if avg_echo < 0.5: return "COOLING"
        elif avg_echo > 1.5: return "HOT"
        else: return "STABLE"

    def _build_synergy_matrix(self, history: List[Dict], max_num: int, lookback: int = 1000) -> np.ndarray:
        """長效共現矩陣 (1000期回溯)"""
        draw_id = history[0].get('draw') if history else 'none'
        cache_key = (draw_id, lookback, max_num)
        if cache_key in self._synergy_cache:
            return self._synergy_cache[cache_key]

        matrix = np.ones((max_num + 1, max_num + 1))
        counts = Counter()
        pair_counts = Counter()
        
        limited_history = history[:lookback]
        total = len(limited_history)
        if total == 0: return matrix
        
        for d in limited_history:
            nums = sorted([n for n in d['numbers'] if n <= max_num])
            for n in nums: counts[n] += 1
            for pair in combinations(nums, 2):
                pair_counts[pair] += 1
                
        for (a, b), count in pair_counts.items():
            prob_a = counts[a] / total
            prob_b = counts[b] / total
            prob_ab = count / total
            if prob_a > 0 and prob_b > 0:
                lift = prob_ab / (prob_a * prob_b)
                lift = max(0.5, min(2.5, lift)) 
                matrix[a][b] = lift
                matrix[b][a] = lift
            
        self._synergy_cache[cache_key] = matrix
        return matrix

    def calculate_sgp_scores(self, history: List[Dict], max_num: int = 38) -> Dict[int, float]:
        """
        🚀 V8: 使用 Power Precision 的核心 Period-Gap 匹配邏輯
        """
        # 1. 取得 Fourier Period-Gap 匹配分
        f_scores = self._calculate_precision_fourier_scores(history, max_num)
        
        # 2. 根據環境偵測動態權重
        from .regime_detector import RegimeDetector
        rd = RegimeDetector()
        regime_info = rd.detect_regime(history)
        regime = regime_info['regime'] 
        
        # 3. 取得遺漏壓力
        gap_scores = self._calculate_gap_pressure(history, max_num)
        
        final_scores = {}
        for n in range(1, max_num + 1):
            f = f_scores.get(n, 0)
            g = gap_scores.get(n, 0)
            
            # SGP 精髓：將傅立葉規律與轉折壓力結合
            # 在 CHAOS 模式下強化壓力權重
            if regime == "CHAOS":
                final_scores[n] = f * 0.4 + (g/2.5) * 0.6
            else:
                final_scores[n] = f * 0.8 + (g/2.5) * 0.2
            
        return final_scores

    def _calculate_precision_fourier_scores(self, history: List[Dict], max_num: int, window: int = 500) -> Dict[int, float]:
        """完美複刻 Power Precision 的傅立葉邏輯"""
        from scipy.fft import fft, fftfreq
        h_slice = history[:window] # history 是倒序，即最後 500 期
        w = len(h_slice)
        
        bitstreams = {i: np.zeros(w) for i in range(1, max_num + 1)}
        for idx, d in enumerate(h_slice):
            for n in d['numbers']:
                if n <= max_num:
                    # 轉為正序時間軸用於標註：最後一期 index 為 w-1
                    bitstreams[n][(w-1) - idx] = 1
                    
        scores = {}
        for n in range(1, max_num + 1):
            bh = bitstreams[n]
            if np.sum(bh) < 2:
                scores[n] = 0.05
                continue
            
            # FFT 分析
            yf = fft(bh - np.mean(bh))
            xf = fftfreq(w, 1)
            idx_pos = np.where(xf > 0)
            pos_xf = xf[idx_pos]
            pos_yf = np.abs(yf[idx_pos])
            
            if len(pos_yf) == 0:
                scores[n] = 0.05
                continue
                
            peak_idx = np.argmax(pos_yf)
            freq_val = pos_xf[peak_idx]
            
            if freq_val == 0:
                scores[n] = 0.05
                continue
                
            period = 1.0 / freq_val
            
            # 找到正序下最後一次命中的位置
            # last_hit_idx = np.where(bh == 1)[0][-1]
            # 當前遺漏 gap = (w-1) - last_hit_idx
            # 在倒序 history 中，這剛好是 np.where(正序bh==1)[0][-1] 與 w-1 的距離
            last_hit_in_正序 = np.where(bh == 1)[0][-1]
            gap = (w - 1) - last_hit_in_正序
            
            # 匹配分公式
            scores[n] = 1.0 / (abs(gap - period) + 1.0)
            
        return scores

    def _calculate_entropy_scores(self, history: List[Dict], max_num: int) -> Dict[int, float]:
        """計算號碼間的互信息 (Entropy/Mutual Information)"""
        if len(history) < 200: return {n: 0.0 for n in range(1, max_num + 1)}
        
        # 簡化版互信息：計算 A 出現後 B 出現的 conditional probability vs marginal
        total_draws = len(history)
        counts = Counter(n for d in history for n in d['numbers'] if n <= max_num)
        marginal_p = {n: counts[n] / total_draws for n in range(1, max_num + 1)}
        
        # 上一期號碼
        last_draw = history[0]['numbers']
        
        # 統計共現轉移
        # P(N|Last)
        conditional_counts = Counter()
        matches = 0
        for i in range(len(history)-1):
            if any(n in history[i+1]['numbers'] for n in last_draw):
                matches += 1
                for n in history[i]['numbers']:
                    if n <= max_num:
                        conditional_counts[n] += 1
        
        mi_scores = {}
        for n in range(1, max_num + 1):
            p_n = marginal_p[n]
            if p_n == 0 or matches == 0:
                mi_scores[n] = 0
                continue
            p_n_given_last = conditional_counts[n] / matches
            # MI proxy: P(N|Last) / P(N)
            mi_scores[n] = p_n_given_last / (p_n + 0.01)
            
        max_mi = max(mi_scores.values()) if mi_scores else 1
        return {n: mi_scores[n]/max_mi for n in range(1, max_num + 1)}

    def _calculate_markov_scores(self, history: List[Dict], max_num: int) -> Dict[int, float]:
        """計算一階馬可夫轉移分"""
        if len(history) < 30: return {n: 0.0 for n in range(1, max_num + 1)}
        
        transitions = defaultdict(Counter)
        for i in range(len(history)-1):
            prev = history[i+1]['numbers']
            curr = history[i]['numbers']
            for p in prev:
                for c in curr:
                    if p <= max_num and c <= max_num:
                        transitions[p][c] += 1
                        
        last_nums = history[0]['numbers']
        scores = Counter()
        for p in last_nums:
            if p <= max_num:
                for c, count in transitions[p].items():
                    scores[c] += count
        
        max_c = max(scores.values()) if scores else 1
        return {n: scores[n] / max_c for n in range(1, max_num + 1)}

    def _calculate_gap_pressure(self, history: List[Dict], max_num: int) -> Dict[int, float]:
        """計算遺漏壓力 (進階版)"""
        scores = {n: 0.05 for n in range(1, max_num + 1)}
        if len(history) < 50: return scores
        
        num_indices = defaultdict(list)
        for i, d in enumerate(history):
            for n in d['numbers']:
                if n <= max_num:
                    num_indices[n].append(i)
                    
        for n in range(1, max_num + 1):
            indices = num_indices.get(n, [])
            if len(indices) < 5: continue
            
            gaps = [indices[i+1] - indices[i] for i in range(len(indices)-1)]
            avg_gap, std_gap = np.mean(gaps), np.std(gaps)
            current_gap = indices[0]
            
            # 壓力計算：當前遺漏距離平均遺漏的偏差
            pressure = (current_gap - avg_gap) / (std_gap + 1.0)
            scores[n] = max(0.01, min(2.5, 1.0 + pressure))
        return scores

    def _pick_synergistic_bet(self, sgp_scores: Dict[int, float], matrix: np.ndarray, pick_count: int, max_num: int, forbidden: set = None) -> List[int]:
        """
        🚀 協同挑選演算法 (確定性版本)
        """
        forbidden = forbidden or set()
        candidates = [n for n in range(1, max_num + 1) if n not in forbidden]
        
        # 1. 挑選最強種子號 (不使用隨機)
        top_seed = sorted(candidates, key=lambda x: sgp_scores.get(x, 0), reverse=True)[0]
        selected = [top_seed]
        
        # 2. 迭代挑選
        while len(selected) < pick_count:
            best_score = -1e9
            best_n = -1
            
            for n in candidates:
                if n in selected: continue
                avg_lift = np.mean([matrix[n][s] for s in selected])
                # 綜合分 = 基礎 SGP * 協同係數
                synergy_score = sgp_scores.get(n, 0) * (avg_lift ** 1.2)
                
                if synergy_score > best_score:
                    best_score = synergy_score
                    best_n = n
            
            if best_n != -1:
                selected.append(best_n)
            else:
                break
        return sorted(selected)

    def generate_bets(self, history: List[Dict], n_bets: int = 3, lottery_type: str = 'POWER_LOTTO') -> List[List[int]]:
        """
        生成 V11 預測注項 (Orthogonal PP-SGP)
        """
        max_num = 38 if 'POWER' in lottery_type else 49
        
        # --- Bet 1: Fourier Rank 1-6 (時間錨點) ---
        f_scores = self._calculate_precision_fourier_scores(history, max_num)
        f_ranked = sorted([n for n in range(1, max_num+1)], key=lambda x: f_scores.get(x, 0), reverse=True)
        bet1 = sorted(f_ranked[:6])
        
        bets = [bet1]
        if n_bets < 2: return bets

        # --- Bet 2: Echo/Cold 空間分佈 (空間錨點 - 復刻 PP3 成功基因) ---
        used = set(bet1)
        if len(history) >= 2:
            echo_nums = [n for n in history[1]['numbers'] if n <= max_num and n not in used]
        else:
            echo_nums = []
            
        recent = history[:100]
        freq = Counter(n for d in recent for n in d['numbers'] if n <= max_num)
        candidates = [n for n in range(1, max_num+1) if n not in used and n not in echo_nums]
        candidates.sort(key=lambda x: freq.get(x, 0)) # Coldest first
        
        bet2 = sorted((echo_nums + candidates)[:6])
        bets.append(bet2)
        if n_bets < 3: return bets

        # --- Bet 3: SGP Boosted (週期性壓力補償) ---
        used.update(bet2)
        gp_scores = self._calculate_gap_pressure(history, max_num)
        pcm_matrix = self._build_synergy_matrix(history, max_num)
        
        final_b3_scores = Counter()
        # Lag-2 Echo (如果 Bet 2 沒用完)
        if len(history) >= 2:
            for n in history[1]['numbers']:
                if n <= max_num and n not in used:
                    final_b3_scores[n] += 10.0
                    
        # Gap Pressure
        for n in range(1, max_num + 1):
            if n not in used:
                final_b3_scores[n] += gp_scores.get(n, 0.05)
                
        # 協同挑選
        bet3 = self._pick_synergistic_bet(dict(final_b3_scores), pcm_matrix, 6, max_num, forbidden=used)
        bets.append(bet3)
        
        return bets

