#!/usr/bin/env python3
"""
Strategy Leaderboard (自動策略評分儀表板)
系統化自動回測所有已知預測模型，找出「當前最強 Edge」。
支持多種彩種 (POWER_LOTTO, BIG_LOTTO)。
"""
import os
import sys
import numpy as np
from collections import Counter
import random
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

class StrategyLeaderboard:
    def __init__(self, lottery_type='POWER_LOTTO', db_path=None):
        if db_path is None:
            db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
        self.db = DatabaseManager(db_path)
        self.lottery_type = lottery_type
        self.draws = self.db.get_all_draws(lottery_type)
        self.draws = sorted(self.draws, key=lambda x: (x['date'], x['draw']))
        
        # Determine rules and baselines (Updated with 2026-01-28 True Edge simulation)
        if lottery_type == 'BIG_LOTTO':
            self.max_num = 49
            self.baselines = {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 7: 0.1234}
            self.rules = {'minNumber': 1, 'maxNumber': 49, 'pickCount': 6, 'name': 'BIG_LOTTO'}
        else:
            self.max_num = 38
            self.baselines = {1: 0.0387, 2: 0.0759, 3: 0.1117, 4: 0.1460, 7: 0.2414}
            self.rules = {'minNumber': 1, 'maxNumber': 38, 'pickCount': 6, 'name': 'POWER_LOTTO'}

        self.rand_win_1 = self.baselines[1]
        self.rand_win_2 = self.baselines[2]

        # --- Phase 10: Universal Model Bridge ---
        self._init_deep_models()

    def _init_deep_models(self):
        """動態加載並封裝 50+ 個高級預測模型"""
        try:
            from lottery_api.models.unified_predictor import UnifiedPredictionEngine
            from lottery_api.models.advanced_strategies import AdvancedStrategies
            
            self.engine = UnifiedPredictionEngine()
            self.advanced = AdvancedStrategies(prediction_engine=self.engine)
            
            # 1. 封裝 UnifiedPredictionEngine 中的方法 (如 frequency_predict)
            for name in dir(self.engine):
                if name.endswith('_predict') and not name.startswith('_'):
                    method = getattr(self.engine, name)
                    setattr(self, f"strat_deep_{name.replace('_predict', '')}", 
                            self._wrap_engine_strategy(method))
            
            # 2. 封裝 AdvancedStrategies 中的方法 (如 entropy_analysis_predict)
            for name in dir(self.advanced):
                if name.endswith('_predict') and not name.startswith('_'):
                    method = getattr(self.advanced, name)
                    setattr(self, f"strat_adv_{name.replace('_predict', '')}", 
                            self._wrap_engine_strategy(method))
                            
        except Exception as e:
            print(f"⚠️ Warning: Deep Model Bridge partially failed: {e}")

    def _wrap_engine_strategy(self, engine_method):
        """將引擎方法包裝成 Leaderboard 格式: (history, n_bets, window)"""
        def wrapper(history, n_bets=1, window=100):
            # 1. 準備格式 (Deep models usually expect [Draw, Draw...])
            # window 參數用於截斷歷史，模擬其局部觀察能力
            recent_history = history[-window:] if window > 0 else history
            
            try:
                # 2. 執行預測
                res = engine_method(recent_history, self.rules)
                
                # 3. 處理結果
                # 大多數模型返回 {'numbers': [1,2,3,4,5,6], 'probabilities': [...]}
                if 'numbers' in res:
                    predicted_nums = res['numbers']
                    # 如果只有一注，但需要 n_bets，我們嘗試從機率分佈中提取更多
                    if n_bets > 1 and 'probabilities' in res and len(res['probabilities']) >= self.max_num:
                        probs = res['probabilities']
                        # 確保索引對齊
                        all_indices = np.arange(1, self.max_num + 1)
                        # 注意：有些 probabilities 是 List，索引 0 可能是 1 或空
                        # 這裡進行安全切片
                        if len(probs) > self.max_num: # 有些模型返回 0-max_num
                            scores = np.array(probs[1:self.max_num+1])
                        else:
                            scores = np.array(probs)
                        
                        sorted_indices = all_indices[np.argsort(scores)[::-1]]
                        bets = []
                        for i in range(n_bets):
                            bets.append(sorted(sorted_indices[i*6:(i+1)*6].tolist()))
                        return bets
                    else:
                        # 兜底：重複同一注或簡單位移
                        return [predicted_nums] * n_bets
                return []
            except:
                return []
        return wrapper

    def get_hits(self, selection, target):
        return len(set(selection) & set(target))

    # --- Strategy Implementations ---
    
    def strat_frequency_hot(self, history, n_bets=1, window=100):
        """熱門號策略"""
        recent = history[-window:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        sorted_nums = sorted(range(1, self.max_num + 1), key=lambda x: freq.get(x, 0), reverse=True)
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def strat_cold_numbers(self, history, n_bets=1, window=100):
        """冷門號策略"""
        recent = history[-window:]
        all_nums = [n for d in recent for n in d['numbers']]
        freq = Counter(all_nums)
        sorted_nums = sorted(range(1, self.max_num + 1), key=lambda x: freq.get(x, 0))
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def strat_twin_strike(self, history, n_bets=2, window=100):
        """冷號互補 (2注)"""
        return self.strat_cold_numbers(history, n_bets=2, window=window)

    def strat_cluster_pivot(self, history, n_bets=2, window=150):
        """聚類中心分析 (常用於大樂透)"""
        recent = history[-window:]
        cooccur = Counter()
        for d in recent:
            nums = sorted(d['numbers'])
            for pair in combinations(nums, 2):
                cooccur[pair] += 1
                
        num_scores = Counter()
        for (a, b), count in cooccur.items():
            num_scores[a] += count
            num_scores[b] += count
        centers = [num for num, _ in num_scores.most_common(n_bets)]
        
        bets = []
        exclude = set()
        for center in centers:
            candidates = Counter()
            for (a, b), count in cooccur.items():
                if a == center and b not in exclude: candidates[b] += count
                elif b == center and a not in exclude: candidates[a] += count
            
            # Expand to 6 numbers
            bet = [center]
            for n, _ in candidates.most_common(5):
                bet.append(n)
            
            # Fill if needed
            if len(bet) < 6:
                for n in range(1, self.max_num + 1):
                    if n not in bet and n not in exclude:
                        bet.append(n)
                    if len(bet) == 6: break
            
            bets.append(sorted(bet))
            exclude.update(bet[:2]) # Inter-ticket coverage diversity
        return bets

    def strat_markov(self, history, n_bets=1, window=100):
        """馬可夫轉移策略"""
        recent = history[-window:]
        transitions = Counter()
        for i in range(len(recent)-1):
            curr_set = set(recent[i]['numbers'])
            next_set = recent[i+1]['numbers']
            for n in next_set:
                for c in curr_set:
                    transitions[(c, n)] += 1
        
        last_draw = history[-1]['numbers']
        next_scores = Counter()
        for c in last_draw:
            for n in range(1, self.max_num + 1):
                next_scores[n] += transitions.get((c, n), 0)
        
        sorted_nums = sorted(range(1, self.max_num + 1), key=lambda x: next_scores[x], reverse=True)
        bets = []
        for i in range(n_bets):
            bets.append(sorted_nums[i*6 : (i+1)*6])
        return bets

    def strat_random(self, history, n_bets=1, **kwargs):
        """完全隨機 (對照組)"""
        bets = []
        for i in range(n_bets):
            bets.append(random.sample(range(1, self.max_num + 1), 6))
        return bets

    def strat_apriori(self, history, n_bets=2, window=150):
        """關聯規則策略 (Apriori 簡化版)"""
        recent = history[-window:]
        pair_counts = Counter()
        for d in recent:
            nums = sorted(d['numbers'])
            for pair in combinations(nums, 2): pair_counts[pair] += 1
            
        # Simplistic rule: If A appears, what B is most likely?
        # Use top pairs as "seeds"
        top_pairs = [p for p, _ in pair_counts.most_common(n_bets)]
        
        bets = []
        for seed_pair in top_pairs:
            # Expand seed pair into 6 numbers using freq or cooccur
            bet = list(seed_pair)
            exclude = set(bet)
            candidates = Counter()
            for (a, b), count in pair_counts.items():
                if a in bet and b not in exclude: candidates[b] += count
                elif b in bet and a not in exclude: candidates[a] += count
            
            for n, _ in candidates.most_common(4):
                bet.append(n)
            
            # Fill if needed
            if len(bet) < 6:
                for n in range(1, self.max_num + 1):
                    if n not in bet: bet.append(n)
                    if len(bet) == 6: break
            bets.append(sorted(bet))
        return bets

    def strat_cluster_apriori_hybrid(self, history, n_bets=2, window=150):
        """
        聚類-關聯雜交策略 (Cluster-Apriori Hybrid)
        1. 強關聯對 (Apriori Pairs) 作為核心種子
        2. 聚類共現 (Cluster Pivot) 進行廣度擴展
        3. 空間分佈多樣性過濾
        """
        recent = history[-window:]
        pair_counts = Counter()
        for d in recent:
            nums = sorted(d['numbers'])
            for pair in combinations(nums, 2):
                pair_counts[pair] += 1
        
        # 取得最強的 N 個號碼對作為「錨點」
        top_pairs = [p for p, _ in pair_counts.most_common(n_bets * 4)]
        
        bets = []
        used_anchors = set()
        
        for p in top_pairs:
            if len(bets) >= n_bets:
                break
                
            # 多樣性檢查：確保錨點號碼不重複過多 (增加覆蓋面)
            if len(set(p) & used_anchors) >= 1:
                continue
            
            p1, p2 = p
            bet = [p1, p2]
            exclude = set(bet)
            
            # 使用 Cluster 邏輯擴展剩下 4 個號碼
            candidates = Counter()
            for (a, b), count in pair_counts.items():
                if a in bet and b not in exclude: 
                    candidates[b] += count
                elif b in bet and a not in exclude: 
                    candidates[a] += count
            
            # 選取最強相關號碼
            for n, _ in candidates.most_common(4):
                bet.append(n)
                exclude.add(n)
            
            # 兜底填充
            if len(bet) < 6:
                for n in range(1, self.max_num + 1):
                    if n not in exclude:
                        bet.append(n)
                        exclude.add(n)
                    if len(bet) == 6: break
            
            bets.append(sorted(bet))
            used_anchors.update(p)
            
        return bets

    def strat_entropy_pivot(self, history, n_bets=1, window=150):
        """熵值聚類中心策略 (基於空間分佈均勻度)"""
        h_slice = history[-window:]
        all_nums = [n for d in h_slice for n in d['numbers']]
        from collections import Counter
        freq = Counter(all_nums)
        scores = np.zeros(self.max_num + 1)
        target_freq = (window * 6) / self.max_num
        for n in range(1, self.max_num + 1):
            f = freq.get(n, 0)
            scores[n] = 1.0 / (abs(f - target_freq) + 0.1)
        sorted_indices = np.argsort(scores[1:])[::-1] + 1
        return [sorted(sorted_indices[i*6:(i+1)*6].tolist()) for i in range(n_bets)]

    def strat_gap_reversion(self, history, n_bets=1, window=500):
        """遺漏回歸策略 (Lag Reversion)"""
        h_slice = history[-window:]
        last_seen = {i: -1 for i in range(1, self.max_num + 1)}
        intervals = {i: [] for i in range(1, self.max_num + 1)}
        for idx, d in enumerate(h_slice):
            for n in d['numbers']:
                if last_seen[n] != -1:
                    intervals[n].append(idx - last_seen[n])
                last_seen[n] = idx
        current_idx = len(h_slice)
        scores = np.zeros(self.max_num + 1)
        for n in range(1, self.max_num + 1):
            median_int = np.median(intervals[n]) if intervals[n] else (self.max_num / 6.0)
            current_lag = current_idx - last_seen[n]
            scores[n] = current_lag / (median_int + 0.1)
        sorted_indices = np.argsort(scores[1:])[::-1] + 1
        return [sorted(sorted_indices[i*6:(i+1)*6].tolist()) for i in range(n_bets)]

    def strat_optimized_ensemble(self, history, n_bets=2, window=150):
        """ROI 優化集成策略 (2026-02-04)"""
        try:
            from lottery_api.models.optimized_ensemble import OptimizedEnsemblePredictor
            predictor = OptimizedEnsemblePredictor(self.rules)
            res = predictor.predict(history, n_bets=n_bets)
            return res.get('all_bets', [])
        except Exception as e:
            print(f"⚠️ Optimized Ensemble failed: {e}")
            return self.strat_random(history, n_bets=n_bets)

    def strat_gum(self, history, n_bets=2, window=150):
        """
        共識集成策略 (Grand Unified Model) - 2026-01-28 Tuned Version
        威力彩最佳權重: Markov=0.25, Cluster=1.0, Cold=0.5
        """
        scores = np.zeros(self.max_num + 1)
        w_m, w_c, w_k = (0.25, 1.0, 0.5) if self.lottery_type == 'POWER_LOTTO' else (0.75, 0.75, 0.5)
        
        # Combine signals
        m_bets = self.strat_markov(history, n_bets=4, window=window)
        for b in m_bets:
            for n in b: scores[n] += w_m
        c_bets = self.strat_cluster_pivot(history, n_bets=4, window=window)
        for b in c_bets:
            for n in b: scores[n] += w_c
        k_bets = self.strat_cold_numbers(history, n_bets=4, window=window)
        for b in k_bets:
            for n in b: scores[n] += w_k
            
        all_indices = np.arange(1, self.max_num + 1)
        sorted_indices = all_indices[np.argsort(scores[1:])[::-1]]
        bets = []
        for i in range(n_bets):
            start = i * 6
            end = (i + 1) * 6
            bets.append(sorted(sorted_indices[start:end].tolist()))
        return bets

    def strat_fourier_rhythm(self, history, n_bets=2, window=500):
        """深層頻譜節奏策略 (FFT 週期性分析)"""
        if len(history) < window: window = len(history)
        h_slice = history[-window:]
        
        # 1. Detect periods for each ball
        scores = np.zeros(self.max_num + 1)
        for n in range(1, self.max_num + 1):
            bitstream = np.zeros(window)
            for i, d in enumerate(h_slice):
                if n in d['numbers']: bitstream[i] = 1
            
            if sum(bitstream) < 2: continue
            
            # FFT
            yf = np.fft.fft(bitstream - np.mean(bitstream))
            xf = np.fft.fftfreq(window, 1)
            idx = np.where(xf > 0)
            pos_xf, pos_yf = xf[idx], np.abs(yf[idx])
            
            freq = pos_xf[np.argmax(pos_yf)]
            if freq > 0:
                period = 1 / freq
                last_hit = np.where(bitstream == 1)[0][-1]
                gap = (window - 1) - last_hit
                # Proximity to next peak
                scores[n] = 1.0 / (abs(gap - period) + 1.0)
                
        sorted_indices = np.argsort(scores[1:])[::-1] + 1
        return [sorted(sorted_indices[i*6:(i+1)*6].tolist()) for i in range(n_bets)]

    def strat_fourier_advanced(self, history, n_bets=2, windows=[150, 300, 500]):
        """
        高階頻譜節奏策略 (Advanced Fourier Fusion)
        1. 多尺度窗口融合 (Multi-Window Fusion)
        2. 頻譜能量加權 (Intensity Weighting)
        3. 衰減補償 (Decay Compensation)
        """
        total_scores = np.zeros(self.max_num + 1)
        
        for window in windows:
            if len(history) < window: continue
            h_slice = history[-window:]
            win_weight = np.sqrt(window) # 給予長窗口較高權重
            
            for n in range(1, self.max_num + 1):
                bitstream = np.zeros(window)
                for i, d in enumerate(h_slice):
                    if n in d['numbers']: bitstream[i] = 1
                
                if sum(bitstream) < 3: continue
                
                # FFT
                yf = np.fft.fft(bitstream - np.mean(bitstream))
                xf = np.fft.fftfreq(window, 1)
                idx = np.where(xf > 0)
                pos_xf, pos_yf = xf[idx], np.abs(yf[idx])
                
                # 取得能量最高的前 2 個頻率
                top_indices = np.argsort(pos_yf)[-2:][::-1]
                
                for idx_peak in top_indices:
                    freq = pos_xf[idx_peak]
                    energy = pos_yf[idx_peak]
                    if freq > 0:
                        period = 1 / freq
                        last_hit = np.where(bitstream == 1)[0][-1]
                        gap = (window - 1) - last_hit
                        # 週期契合度 * 能量強度
                        proximity = 1.0 / (abs(gap - period) + 1.0)
                        total_scores[n] += proximity * energy * win_weight
                        
        all_indices = np.arange(1, self.max_num + 1)
        sorted_indices = all_indices[np.argsort(total_scores[1:])[::-1]]
        
        bets = []
        for i in range(n_bets):
            start = i * 6
            end = (i + 1) * 6
            bets.append(sorted(sorted_indices[start:end].tolist()))
        return bets

    def strat_wavelet_mra(self, history, n_bets=2, window=300):
        """多尺度分析策略 (Wavelet Transient Detection)"""
        import pywt
        if len(history) < window: window = len(history)
        h_slice = history[-window:]
        scales = np.arange(2, 32)
        scores = np.zeros(self.max_num + 1)
        
        for n in range(1, self.max_num + 1):
            bitstream = np.zeros(window)
            for i, d in enumerate(h_slice):
                if n in d['numbers']: bitstream[i] = 1
            
            if sum(bitstream) < 3: continue
            
            try:
                coef, _ = pywt.cwt(bitstream, scales, 'mexh')
                current_energy = np.abs(coef[:, -1])
                best_scale = scales[np.argmax(current_energy)]
                
                last_hit = np.where(bitstream == 1)[0][-1]
                gap = (window - 1) - last_hit
                
                # Phase + Energy
                scores[n] = (1.0 / (abs(gap - best_scale) + 1.0)) * (1 + np.log1p(current_energy[np.argmax(current_energy)]))
            except:
                pass
                
        sorted_indices = np.argsort(scores[1:])[::-1] + 1
        return [sorted(sorted_indices[i*6:(i+1)*6].tolist()) for i in range(n_bets)]

    def run_backtest(self, strategy_func, periods=150, **kwargs):
        hits_3_plus = 0
        total = 0
        for i in range(periods):
            idx = len(self.draws) - periods + i
            if idx <= 0: continue
            
            target = self.draws[idx]['numbers']
            history = self.draws[:idx]
            
            if len(history) < 150: continue # Standardize for Big Lotto
            
            bets = strategy_func(history, **kwargs)
            
            win = False
            for b in bets:
                if self.get_hits(b, target) >= 3:
                    win = True
                    break
            if win:
                hits_3_plus += 1
            total += 1
            
        return hits_3_plus / total if total > 0 else 0

    def generate_report(self, periods=150):
        if len(self.draws) < periods + 150:
            print(f"⚠️ Warning: Not enough history for {self.lottery_type}. Required: {periods + 150}, Found: {len(self.draws)}")
            
        print(f"\n📊 Strategy Leaderboard: {self.lottery_type} (N={periods})")
        print("="*75)
        print(f"{'Strategy Name':<30} | {'Bets':<5} | {'Win Rate':<10} | {'Edge vs Rand'}")
        print("-" * 75)
        
        strategies = [
            ("Cold Complement (Twin Strike)", self.strat_twin_strike, {"window": 150}, 2),
            ("Frequency (Hot) x2", self.strat_frequency_hot, {"n_bets": 2, "window": 150}, 2),
            ("Markov Transition x2", self.strat_markov, {"n_bets": 2, "window": 150}, 2),
            ("Fourier Advanced x2", self.strat_fourier_advanced, {"n_bets": 2}, 2),
            ("LSTM-AR (Sequential) x2", self.strat_lstm_ar, {"n_bets": 2, "window": 80}, 2),
            ("Random (Baseline) x2", self.strat_random, {"n_bets": 2}, 2),
            ("GUM Consensus Ensemble x2", self.strat_gum, {"n_bets": 2, "window": 150}, 2),
        ]
        
        if self.lottery_type == 'BIG_LOTTO':
            strategies.append(("Cluster Pivot x2 (Opt)", self.strat_cluster_pivot, {"n_bets": 2, "window": 50}, 2))
            strategies.append(("Cluster Pivot x7 (Opt)", self.strat_cluster_pivot, {"n_bets": 7, "window": 50}, 7))
            strategies.append(("Apriori (3-bet)", self.strat_apriori, {"n_bets": 3, "window": 150}, 3))
            strategies.append(("GUM Optimized x2", self.strat_gum, {"n_bets": 2, "window": 150}, 2))
        else:
            strategies.append(("GUM Optimized x2", self.strat_gum, {"n_bets": 2, "window": 150}, 2))
            strategies.append(("Fourier Advanced x2", self.strat_fourier_advanced, {"n_bets": 2}, 2))
        
        results = []
        for name, func, args, n_bets in strategies:
            rate = self.run_backtest(func, periods=periods, **args)
            baseline = self.baselines.get(n_bets, self.rand_win_1)
            edge = rate - baseline
            results.append((name, n_bets, rate, edge, baseline))
            
        results.sort(key=lambda x: x[3], reverse=True)
        for name, n_bets, rate, edge, baseline in results:
            edge_str = f"{edge*100:+.2f}%"
            print(f"{name:<30} | {n_bets:<5} | {rate*100:8.2f}% | {edge_str} (vs {baseline*100:5.2f}%)")
            
        print("="*75)
        print(f"Random Baseline: 1-bet={self.rand_win_1*100:.2f}%, 2-bet={self.rand_win_2*100:.2f}%")

    def strat_ev_optimized(self, history, n_bets=2, base_strat='cluster', window=150):
        """
        博弈期望值優化策略 (EV Optimized)
        1. 使用基礎策略產生較大的候選池
        2. 計算號碼的「稀缺性權重」(基於逆頻率)
        3. 重新計算組合的期望值並重排
        """
        # 1. 產生候選池 (限制候選注數，避免號碼不夠分)
        max_candidates = min(8, self.max_num // 6)
        if base_strat == 'cluster':
            candidates = self.strat_cluster_pivot(history, n_bets=max_candidates, window=window)
        elif base_strat == 'fourier':
            candidates = self.strat_fourier_advanced(history, n_bets=max_candidates)
        else:
            candidates = self.strat_frequency_hot(history, n_bets=max_candidates, window=window)
            
        if not candidates:
            return [list(range(1, 7))] * n_bets
            
        # 2. 計算稀缺性 (越高頻出的號碼，稀缺性越低)
        recent = history[-100:]
        counts = Counter([n for d in recent for n in d['numbers']])
        
        # Scarcity = 1 / (frequency + 1)
        scarcity = {n: 1.0 / (counts.get(n, 0) + 1.0) for n in range(1, self.max_num + 1)}
        
        # 3. 評分組合
        scored_candidates = []
        for bet in candidates:
            if not bet: continue
            ev_score = sum(np.log(scarcity[n] + 1e-9) for n in bet)
            scored_candidates.append((bet, ev_score))
            
        # 4. 取 EV 最高的前 N 注
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        final_bets = [c[0] for c in scored_candidates[:n_bets]]
        
        # 補足注數
        while len(final_bets) < n_bets:
            final_bets.append(final_bets[0] if final_bets else list(range(1, 7)))
            
        return final_bets

    def strat_lstm_ar(self, history, n_bets=2, window=100, epochs=5):
        """
        TensorFlow LSTM-AR (Autoregressive) 模型
        借鑑自回歸思想，模型預測第 i 個球時會參考當前注項已產生的第 0..i-1 個球。
        """
        import tensorflow as tf
        from tensorflow.keras import layers
        
        # 1. 準備訓練數據
        # 我們利用 window 內的歷史開獎，構造 (歷史背景, 當前注項前置號碼) -> 下一個號碼 的樣本
        train_slice = history[-window:]
        if len(train_slice) < 50: # 太少數據則退化為隨機
            return self.strat_random(history, n_bets)
            
        # 構造數據集：
        # X_hist: [batch, history_len, 6] (過去 N 期的號碼)
        # X_curr: [batch, 6] (當前注項的 Masked 號碼序列)
        # Y: [batch, max_num] (One-hot 下一個號碼)
        
        all_draws = [sorted(d['numbers']) for d in train_slice]
        max_val = self.max_num
        
        def encode_draw(nums):
            arr = np.zeros(max_val)
            for n in nums: arr[n-1] = 1
            return arr

        X_h, X_c, Y = [], [], []
        hist_len = 5
        for i in range(hist_len, len(all_draws)):
            h_context = [encode_draw(all_draws[j]) for j in range(i-hist_len, i)]
            current_draw = all_draws[i]
            
            # 對於當前開獎的每一個號碼，構造一個 AR 樣本
            current_prefix = np.zeros(max_val)
            for target_num in current_draw:
                X_h.append(h_context)
                X_c.append(current_prefix.copy())
                Y.append(target_num - 1)
                current_prefix[target_num - 1] = 1 # 填入已出現號碼
                
        X_h = np.array(X_h, dtype='float32') # [N, 5, max_val]
        X_c = np.array(X_c, dtype='float32') # [N, max_val]
        Y = np.array(Y, dtype='int32')
        
        # 2. 構建輕量級雙輸入模型
        input_h = layers.Input(shape=(hist_len, max_val))
        input_c = layers.Input(shape=(max_val,))
        
        # 歷史支路 (LSTM)
        h_feat = layers.LSTM(32)(input_h)
        
        # 當前支路 (Dense)
        c_feat = layers.Dense(32, activation='relu')(input_c)
        
        # 合併
        merged = layers.Concatenate()([h_feat, c_feat])
        merged = layers.Dense(64, activation='relu')(merged)
        output = layers.Dense(max_val, activation='softmax')(merged)
        
        model = tf.keras.Model(inputs=[input_h, input_c], outputs=output)
        model.compile(optimizer='adam', loss='sparse_categorical_crossentropy')
        
        # 3. 快速訓練
        model.fit([X_h, X_c], Y, epochs=epochs, batch_size=32, verbose=0)
        
        # 4. 自回歸推測 (Inference)
        last_h_context = np.array([[encode_draw(all_draws[j]) for j in range(len(all_draws)-hist_len, len(all_draws))]], dtype='float32')
        
        bets = []
        for _ in range(n_bets):
            current_prefix = np.zeros((1, max_val), dtype='float32')
            bet = []
            for _ in range(6):
                probs = model.predict([last_h_context, current_prefix], verbose=0)[0]
                # 排除已選號碼
                for n in bet: probs[n-1] = 0
                if np.sum(probs) > 0:
                    probs /= np.sum(probs)
                
                # 基於機率採樣 (增加多樣性)
                next_num = np.random.choice(range(1, max_val + 1), p=probs)
                bet.append(next_num)
                current_prefix[0, next_num-1] = 1
            bets.append(sorted(bet))
            
        return bets

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='POWER_LOTTO')
    parser.add_argument('--n', type=int, default=150)
    parser.add_argument('--deep', action='store_true', help='Run short/medium/long term audit')
    args = parser.parse_args()
    
    lb = StrategyLeaderboard(lottery_type=args.lottery)
    
    if args.deep:
        for n_term in [30, 150, 500]:
            print(f"\n--- Running {n_term}-period audit ---")
            lb.generate_report(periods=n_term)
    else:
        lb.generate_report(periods=args.n)
