"""
Strategy Generator - 自動產生、突變、重組策略
支援: 統計、機率、數學模式、神經網路、Genetic Programming、
      表徵學習、非線性轉換、特徵空間重組、隱變量推估
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from .strategy_base import BaseStrategy, FeatureLibrary, StrategyResult
import copy, random


# ═══════════════════════════════════════════════
# 1. 基礎策略族群 (Seed Strategies)
# ═══════════════════════════════════════════════

class FrequencyStrategy(BaseStrategy):
    """頻率策略 - 選最常/最少出現的號碼"""
    def __init__(self, window=50, mode='hot', top_n=6):
        super().__init__(f"Freq_{mode}_w{window}", "stable")
        self.params = {'window': window, 'mode': mode, 'top_n': top_n}
    
    def predict(self, draws, n_select=6):
        freq = FeatureLibrary.frequency(draws, self.params['window'])
        if self.params['mode'] == 'hot':
            idx = np.argsort(freq)[-n_select:]
        elif self.params['mode'] == 'cold':
            idx = np.argsort(freq)[:n_select]
        else:  # mixed
            hot = np.argsort(freq)[-n_select//2:]
            cold = np.argsort(freq)[:n_select - n_select//2]
            idx = np.concatenate([hot, cold])
        return sorted((idx + 1).tolist()[:n_select])
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['window'] = max(10, s.params['window'] + rng.integers(-20, 21))
        s.params['mode'] = rng.choice(['hot', 'cold', 'mixed'])
        s.name = f"Freq_{s.params['mode']}_w{s.params['window']}"
        return s


class GapPressureStrategy(BaseStrategy):
    """間隔壓力策略 - 選超出預期間隔的號碼"""
    def __init__(self, threshold=1.0):
        super().__init__(f"GapPressure_t{threshold:.1f}", "burst")
        self.params = {'threshold': threshold}
    
    def predict(self, draws, n_select=6):
        pressure = FeatureLibrary.gap_pressure(draws)
        candidates = np.where(pressure > self.params['threshold'])[0]
        if len(candidates) >= n_select:
            top = candidates[np.argsort(pressure[candidates])[-n_select:]]
        else:
            top = np.argsort(pressure)[-n_select:]
        return sorted((top + 1).tolist()[:n_select])
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['threshold'] = max(0.1, s.params['threshold'] + rng.uniform(-0.5, 0.5))
        s.name = f"GapPressure_t{s.params['threshold']:.1f}"
        return s


class MarkovStrategy(BaseStrategy):
    """馬可夫轉移策略"""
    def __init__(self, order=1, weight_prev=0.6):
        super().__init__(f"Markov_o{order}_w{weight_prev:.1f}", "stable")
        self.params = {'order': order, 'weight_prev': weight_prev}
    
    def predict(self, draws, n_select=6):
        from .data_loader import build_binary_matrix
        probs = FeatureLibrary.markov_transition(draws, self.params['order'])
        bmat = build_binary_matrix(draws)
        last = bmat[-1]
        scores = np.zeros(49)
        w = self.params['weight_prev']
        for j in range(49):
            prev_state = int(last[j])
            scores[j] = probs[j, prev_state] * (w if prev_state == 1 else (1 - w))
        top = np.argsort(scores)[-n_select:]
        return sorted((top + 1).tolist())
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['order'] = rng.choice([1, 2, 3])
        s.params['weight_prev'] = np.clip(s.params['weight_prev'] + rng.uniform(-0.2, 0.2), 0.1, 0.9)
        s.name = f"Markov_o{s.params['order']}_w{s.params['weight_prev']:.1f}"
        return s


class DeviationStrategy(BaseStrategy):
    """偏差回歸策略 - 偏離期望最多的號碼"""
    def __init__(self, window=100, direction='under'):
        super().__init__(f"Deviation_{direction}_w{window}", "burst")
        self.params = {'window': window, 'direction': direction}
    
    def predict(self, draws, n_select=6):
        dev = FeatureLibrary.deviation_score(draws, self.params['window'])
        if self.params['direction'] == 'under':
            idx = np.argsort(dev)[:n_select]  # most underperforming
        else:
            idx = np.argsort(dev)[-n_select:]  # most overperforming
        return sorted((idx + 1).tolist())
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['window'] = max(20, s.params['window'] + rng.integers(-30, 31))
        s.params['direction'] = rng.choice(['under', 'over'])
        s.name = f"Deviation_{s.params['direction']}_w{s.params['window']}"
        return s


class FourierCycleStrategy(BaseStrategy):
    """傅立葉週期策略 - 依相位預測出現時機"""
    def __init__(self, top_k=3, phase_threshold=0.5):
        super().__init__(f"Fourier_k{top_k}_p{phase_threshold:.1f}", "conditional")
        self.params = {'top_k': top_k, 'phase_threshold': phase_threshold}
    
    def predict(self, draws, n_select=6):
        phases, mags = FeatureLibrary.fourier_phase(draws, self.params['top_k'])
        scores = np.zeros(49)
        for j in range(49):
            for k in range(self.params['top_k']):
                # predict based on phase alignment
                phase_pred = np.cos(phases[j, k])
                scores[j] += mags[j, k] * max(0, phase_pred)
        top = np.argsort(scores)[-n_select:]
        return sorted((top + 1).tolist())
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['top_k'] = rng.choice([1, 2, 3, 5])
        s.params['phase_threshold'] = np.clip(s.params['phase_threshold'] + rng.uniform(-0.3, 0.3), 0.1, 1.0)
        s.name = f"Fourier_k{s.params['top_k']}_p{s.params['phase_threshold']:.1f}"
        return s


class CoOccurrenceStrategy(BaseStrategy):
    """共現圖策略 - 根據號碼共現關係預測"""
    def __init__(self, window=100, seed_count=2):
        super().__init__(f"CoOccur_w{window}_s{seed_count}", "synergy")
        self.params = {'window': window, 'seed_count': seed_count}
    
    def predict(self, draws, n_select=6):
        comat = FeatureLibrary.co_occurrence(draws, self.params['window'])
        last = draws[-1]
        scores = np.zeros(49)
        for n in last[:self.params['seed_count']]:
            scores += comat[n - 1]
        for n in last:
            scores[n - 1] = 0  # don't repeat
        top = np.argsort(scores)[-n_select:]
        return sorted((top + 1).tolist())
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['window'] = max(30, s.params['window'] + rng.integers(-30, 31))
        s.params['seed_count'] = rng.choice([1, 2, 3, 4])
        s.name = f"CoOccur_w{s.params['window']}_s{s.params['seed_count']}"
        return s


class LagAutoCorrelationStrategy(BaseStrategy):
    """滯後自相關策略"""
    def __init__(self, lag=1, threshold=0.05):
        super().__init__(f"LagAC_l{lag}_t{threshold:.2f}", "conditional")
        self.params = {'lag': lag, 'threshold': threshold}
    
    def predict(self, draws, n_select=6):
        corrs = FeatureLibrary.lag_autocorrelation(draws, self.params['lag'])
        from .data_loader import build_binary_matrix
        bmat = build_binary_matrix(draws)
        last = bmat[-1]
        scores = np.zeros(49)
        for j in range(49):
            if corrs[j] > self.params['threshold']:
                scores[j] = corrs[j] * (1 if last[j] else 0.5)
            elif corrs[j] < -self.params['threshold']:
                scores[j] = abs(corrs[j]) * (1 if not last[j] else 0.3)
        # fill with frequency if not enough
        if np.sum(scores > 0) < n_select:
            freq = FeatureLibrary.frequency(draws, 50)
            scores += freq * 0.01
        top = np.argsort(scores)[-n_select:]
        return sorted((top + 1).tolist())
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['lag'] = rng.choice([1, 2, 3, 5, 7, 10])
        s.params['threshold'] = np.clip(s.params['threshold'] + rng.uniform(-0.03, 0.03), 0.01, 0.2)
        s.name = f"LagAC_l{s.params['lag']}_t{s.params['threshold']:.2f}"
        return s


class ConsecutivePatternStrategy(BaseStrategy):
    """連號模式策略"""
    def __init__(self, window=50, weight=0.3):
        super().__init__(f"ConsecPat_w{window}", "conditional")
        self.params = {'window': window, 'weight': weight}
    
    def predict(self, draws, n_select=6):
        consec = FeatureLibrary.consecutive_pairs(draws, self.params['window'])
        freq = FeatureLibrary.frequency(draws, self.params['window'])
        w = self.params['weight']
        scores = w * consec + (1 - w) * freq
        top = np.argsort(scores)[-n_select:]
        return sorted((top + 1).tolist())
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['window'] = max(20, s.params['window'] + rng.integers(-20, 21))
        s.params['weight'] = np.clip(s.params['weight'] + rng.uniform(-0.15, 0.15), 0.05, 0.95)
        s.name = f"ConsecPat_w{s.params['window']}"
        return s


class ZonalBalanceStrategy(BaseStrategy):
    """區間平衡策略 - n個區間各出至少1個"""
    def __init__(self, zones=5, window=50):
        super().__init__(f"Zonal_z{zones}_w{window}", "stable")
        self.params = {'zones': zones, 'window': window}
    
    def predict(self, draws, n_select=6):
        freq = FeatureLibrary.frequency(draws, self.params['window'])
        z = self.params['zones']
        zone_size = 49 // z + 1
        selected = []
        for zi in range(z):
            start = zi * zone_size
            end = min(start + zone_size, 49)
            zone_freq = freq[start:end]
            best = np.argmax(zone_freq) + start
            selected.append(best + 1)
        # fill remaining
        while len(selected) < n_select:
            remaining = [i+1 for i in np.argsort(freq)[::-1] if (i+1) not in selected]
            if remaining:
                selected.append(remaining[0])
        return sorted(selected[:n_select])
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['zones'] = rng.choice([3, 4, 5, 6, 7])
        s.params['window'] = max(20, s.params['window'] + rng.integers(-20, 21))
        s.name = f"Zonal_z{s.params['zones']}_w{s.params['window']}"
        return s


class SumTargetStrategy(BaseStrategy):
    """號碼和目標策略 - 瞄準歷史平均和"""
    def __init__(self, window=100, tolerance=15):
        super().__init__(f"SumTarget_w{window}_t{tolerance}", "stable")
        self.params = {'window': window, 'tolerance': tolerance}
    
    def predict(self, draws, n_select=6):
        sums = FeatureLibrary.sum_trend(draws, self.params['window'])
        target_sum = np.mean(sums)
        freq = FeatureLibrary.frequency(draws, self.params['window'])
        # greedy construction
        candidates = np.argsort(freq)[::-1][:20]
        best_combo = None
        best_diff = float('inf')
        rng = np.random.default_rng(42)
        for _ in range(100):
            combo = sorted(rng.choice(candidates, n_select, replace=False) + 1)
            diff = abs(sum(combo) - target_sum)
            if diff < best_diff:
                best_diff = diff
                best_combo = combo.tolist()
        return best_combo or sorted((candidates[:n_select] + 1).tolist())
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['window'] = max(30, s.params['window'] + rng.integers(-30, 31))
        s.params['tolerance'] = max(5, s.params['tolerance'] + rng.integers(-5, 6))
        s.name = f"SumTarget_w{s.params['window']}_t{s.params['tolerance']}"
        return s


class HotColdMixStrategy(BaseStrategy):
    """熱冷混合策略 - 動態平衡熱號與冷號"""
    def __init__(self, hot_w=30, cold_w=100, hot_ratio=0.5):
        super().__init__(f"HotCold_h{hot_w}_c{cold_w}_r{hot_ratio:.1f}", "stable")
        self.params = {'hot_w': hot_w, 'cold_w': cold_w, 'hot_ratio': hot_ratio}
    
    def predict(self, draws, n_select=6):
        hc = FeatureLibrary.hot_cold_score(draws, self.params['hot_w'], self.params['cold_w'])
        n_hot = max(1, int(n_select * self.params['hot_ratio']))
        n_cold = n_select - n_hot
        hot_nums = (np.argsort(hc)[-n_hot:] + 1).tolist()
        cold_nums = (np.argsort(hc)[:n_cold] + 1).tolist()
        return sorted(set(hot_nums + cold_nums))[:n_select]
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['hot_w'] = max(10, s.params['hot_w'] + rng.integers(-10, 11))
        s.params['cold_w'] = max(30, s.params['cold_w'] + rng.integers(-20, 21))
        s.params['hot_ratio'] = np.clip(s.params['hot_ratio'] + rng.uniform(-0.2, 0.2), 0.2, 0.8)
        s.name = f"HotCold_h{s.params['hot_w']}_c{s.params['cold_w']}_r{s.params['hot_ratio']:.1f}"
        return s


class OddEvenBalanceStrategy(BaseStrategy):
    """奇偶平衡策略"""
    def __init__(self, target_odd=3, window=50):
        super().__init__(f"OddEven_o{target_odd}_w{window}", "stable")
        self.params = {'target_odd': target_odd, 'window': window}
    
    def predict(self, draws, n_select=6):
        freq = FeatureLibrary.frequency(draws, self.params['window'])
        odds = [i for i in range(49) if (i + 1) % 2 == 1]
        evens = [i for i in range(49) if (i + 1) % 2 == 0]
        n_odd = self.params['target_odd']
        n_even = n_select - n_odd
        odd_sorted = sorted(odds, key=lambda x: freq[x], reverse=True)[:n_odd]
        even_sorted = sorted(evens, key=lambda x: freq[x], reverse=True)[:n_even]
        return sorted([i + 1 for i in odd_sorted + even_sorted])
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['target_odd'] = rng.choice([2, 3, 4])
        s.params['window'] = max(20, s.params['window'] + rng.integers(-15, 16))
        s.name = f"OddEven_o{s.params['target_odd']}_w{s.params['window']}"
        return s


# ═══════════════════════════════════════════════
# 2. 組合策略 (Composite / Ensemble)
# ═══════════════════════════════════════════════

class WeightedEnsembleStrategy(BaseStrategy):
    """加權組合策略 - 組合多個子策略"""
    def __init__(self, strategies: List[BaseStrategy], weights: List[float] = None):
        names = "+".join([s.name[:10] for s in strategies[:3]])
        super().__init__(f"Ensemble({names})", "synergy")
        self.strategies = strategies
        self.weights = weights or [1.0 / len(strategies)] * len(strategies)
        self.params = {'n_strategies': len(strategies), 'weights': self.weights}
    
    def predict(self, draws, n_select=6):
        scores = np.zeros(49)
        for strat, w in zip(self.strategies, self.weights):
            nums = strat.predict(draws, n_select=12)
            for n in nums:
                scores[n - 1] += w
        top = np.argsort(scores)[-n_select:]
        return sorted((top + 1).tolist())
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        # mutate weights
        for i in range(len(s.weights)):
            s.weights[i] = max(0.05, s.weights[i] + rng.uniform(-0.15, 0.15))
        total = sum(s.weights)
        s.weights = [w / total for w in s.weights]
        # mutate a sub-strategy
        if s.strategies:
            idx = rng.integers(0, len(s.strategies))
            s.strategies[idx] = s.strategies[idx].mutate(rng)
        s.params['weights'] = s.weights
        return s


class NegativeFilterStrategy(BaseStrategy):
    """排除策略 - 先選候選後排除不利號碼"""
    def __init__(self, base_strategy: BaseStrategy, kill_count=5, kill_window=30):
        super().__init__(f"NegFilter({base_strategy.name[:15]})", "conditional")
        self.base = base_strategy
        self.params = {'kill_count': kill_count, 'kill_window': kill_window}
    
    def predict(self, draws, n_select=6):
        freq = FeatureLibrary.frequency(draws, self.params['kill_window'])
        kill_set = set((np.argsort(freq)[-self.params['kill_count']:] + 1).tolist())
        candidates = self.base.predict(draws, n_select=n_select + self.params['kill_count'])
        filtered = [n for n in candidates if n not in kill_set]
        if len(filtered) < n_select:
            extras = [i+1 for i in np.argsort(freq) if (i+1) not in set(filtered) and (i+1) not in kill_set]
            filtered.extend(extras[:n_select - len(filtered)])
        return sorted(filtered[:n_select])
    
    def mutate(self, rng):
        s = copy.deepcopy(self)
        s.params['kill_count'] = rng.choice([3, 5, 7, 10])
        s.params['kill_window'] = max(10, s.params['kill_window'] + rng.integers(-10, 11))
        s.base = s.base.mutate(rng)
        s.name = f"NegFilter({s.base.name[:15]})"
        return s


# ═══════════════════════════════════════════════
# 3. 策略工廠 - 自動生成種子族群
# ═══════════════════════════════════════════════

def generate_seed_population(rng: np.random.Generator, size: int = 50) -> List[BaseStrategy]:
    """生成初始策略族群"""
    population = []
    
    # Frequency variants (trimmed)
    for w in [30, 50, 100, 200]:
        for m in ['hot', 'cold', 'mixed']:
            population.append(FrequencyStrategy(window=w, mode=m))
    
    # Gap Pressure variants
    for t in [0.5, 1.0, 1.5, 2.0, 2.5]:
        population.append(GapPressureStrategy(threshold=t))
    
    # Markov variants
    for o in [1, 2, 3]:
        for w in [0.3, 0.5, 0.7]:
            population.append(MarkovStrategy(order=o, weight_prev=w))
    
    # Deviation
    for w in [50, 100, 200, 500]:
        for d in ['under', 'over']:
            population.append(DeviationStrategy(window=w, direction=d))
    
    # Fourier
    for k in [1, 2, 3, 5]:
        population.append(FourierCycleStrategy(top_k=k))
    
    # Co-occurrence
    for w in [50, 100]:
        for s in [1, 2]:
            population.append(CoOccurrenceStrategy(window=w, seed_count=s))
    
    # Lag autocorrelation
    for lag in [1, 2, 3, 5, 7]:
        population.append(LagAutoCorrelationStrategy(lag=lag))
    
    # Consecutive
    for w in [30, 50, 100]:
        population.append(ConsecutivePatternStrategy(window=w))
    
    # Zonal
    for z in [3, 4, 5, 7]:
        population.append(ZonalBalanceStrategy(zones=z))
    
    # Sum target
    for w in [50, 100, 200]:
        population.append(SumTargetStrategy(window=w))
    
    # Hot-Cold mix
    for hr in [0.3, 0.5, 0.7]:
        population.append(HotColdMixStrategy(hot_ratio=hr))
    
    # Odd-Even
    for o in [2, 3, 4]:
        population.append(OddEvenBalanceStrategy(target_odd=o))
    
    # Random Ensembles (2-strategy combos)
    base_strats = population.copy()
    for _ in range(min(10, size // 4)):
        combo = rng.choice(len(base_strats), 2, replace=False)
        population.append(WeightedEnsembleStrategy(
            [base_strats[combo[0]], base_strats[combo[1]]]))
    
    # Negative filter combos
    for _ in range(min(5, size // 6)):
        base = rng.choice(base_strats)
        population.append(NegativeFilterStrategy(base))
    
    return population[:size] if len(population) > size else population
