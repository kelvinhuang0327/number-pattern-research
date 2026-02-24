"""
Strategy Base Classes & Feature Library
策略基類與特徵庫
"""
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Set, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import hashlib, json, time


@dataclass
class StrategyResult:
    """策略評估結果"""
    name: str
    category: str  # stable/burst/conditional/synergy
    numbers: List[int]  # predicted numbers for next draw
    confidence: float
    features_used: List[str]
    params: Dict[str, Any]
    
    # Backtest metrics (filled by evaluator)
    hit_rates: Dict[str, float] = field(default_factory=dict)
    edges: Dict[str, float] = field(default_factory=dict)
    short_hit: float = 0.0
    mid_hit: float = 0.0
    long_hit: float = 0.0
    volatility: float = 0.0
    extreme_best: int = 0
    extreme_worst: int = 0
    relative_random_edge: float = 0.0
    p_value: float = 1.0
    generation: int = 0
    parent_id: str = ""
    mutation_type: str = ""
    
    @property
    def strategy_id(self):
        def _to_json_safe(obj):
            if isinstance(obj, np.integer): return int(obj)
            if isinstance(obj, np.floating): return float(obj)
            if isinstance(obj, np.ndarray): return obj.tolist()
            if isinstance(obj, list): return [_to_json_safe(x) for x in obj]
            return obj
        clean_params = {k: _to_json_safe(v) for k, v in self.params.items()}
        s = f"{self.name}_{json.dumps(clean_params, sort_keys=True)}"
        return hashlib.md5(s.encode()).hexdigest()[:12]


class BaseStrategy(ABC):
    """策略基類"""
    
    def __init__(self, name: str, category: str = "unknown"):
        self.name = name
        self.category = category
        self.params: Dict[str, Any] = {}
    
    @abstractmethod
    def predict(self, draws: np.ndarray, n_select: int = 6) -> List[int]:
        """給定歷史開獎, 預測下一期號碼"""
        pass
    
    def get_features(self, draws: np.ndarray) -> Dict[str, np.ndarray]:
        """提取特徵 (可選覆寫)"""
        return {}
    
    def mutate(self, rng: np.random.Generator) -> 'BaseStrategy':
        """自我突變 (預設: 回傳自身)"""
        return self
    
    def to_result(self, draws: np.ndarray) -> StrategyResult:
        nums = self.predict(draws)
        return StrategyResult(
            name=self.name, category=self.category,
            numbers=nums, confidence=0.5,
            features_used=list(self.get_features(draws).keys()),
            params=self.params.copy()
        )


# ═══════════════════════════════════════
# Feature Library (可被任何策略組合使用)
# ═══════════════════════════════════════

class FeatureLibrary:
    """全域特徵庫 - 計算各種衍生特徵"""
    
    @staticmethod
    def frequency(draws, window=None):
        """頻率統計"""
        d = draws[-window:] if window else draws
        freq = np.zeros(49)
        for row in d:
            for n in row:
                freq[n - 1] += 1
        return freq / len(d)
    
    @staticmethod
    def gap_current(draws):
        """當前各號碼的間隔期數"""
        gaps = np.zeros(49, dtype=int)
        for j in range(49):
            for i in range(len(draws) - 1, -1, -1):
                if (j + 1) in draws[i]:
                    gaps[j] = len(draws) - 1 - i
                    break
            else:
                gaps[j] = len(draws)
        return gaps
    
    @staticmethod
    def gap_mean_std(draws):
        """各號碼平均間隔與標準差"""
        means = np.zeros(49)
        stds = np.zeros(49)
        for j in range(49):
            positions = [i for i in range(len(draws)) if (j + 1) in draws[i]]
            if len(positions) >= 2:
                gaps = np.diff(positions)
                means[j] = np.mean(gaps)
                stds[j] = np.std(gaps)
            else:
                means[j] = len(draws)
                stds[j] = 0
        return means, stds

    @staticmethod
    def hot_cold_score(draws, hot_w=30, cold_w=100):
        """熱冷號碼評分"""
        hot = FeatureLibrary.frequency(draws, hot_w)
        cold = FeatureLibrary.frequency(draws, cold_w)
        return hot - cold  # positive = hot trending

    @staticmethod
    def co_occurrence(draws, window=100):
        """共現矩陣 (49x49)"""
        d = draws[-window:]
        comat = np.zeros((49, 49), dtype=int)
        for row in d:
            for i, a in enumerate(row):
                for b in row[i+1:]:
                    comat[a-1, b-1] += 1
                    comat[b-1, a-1] += 1
        return comat

    @staticmethod
    def zone_distribution(draws, zones=5):
        """區間分佈 (最近N期)"""
        zone_size = 49 // zones + 1
        dist = np.zeros(zones)
        for n in draws[-1]:
            z = min((n - 1) // zone_size, zones - 1)
            dist[z] += 1
        return dist

    @staticmethod
    def odd_even_ratio(draws, window=20):
        """奇偶比"""
        d = draws[-window:]
        ratios = []
        for row in d:
            odd = sum(1 for n in row if n % 2 == 1)
            ratios.append(odd / 6.0)
        return np.array(ratios)
    
    @staticmethod
    def sum_trend(draws, window=30):
        """號碼和趨勢"""
        d = draws[-window:]
        return np.array([sum(row) for row in d])

    @staticmethod
    def consecutive_pairs(draws, window=50):
        """連號出現頻率"""
        d = draws[-window:]
        counts = np.zeros(49)
        for row in d:
            s = sorted(row)
            for i in range(len(s) - 1):
                if s[i+1] - s[i] == 1:
                    counts[s[i] - 1] += 1
                    counts[s[i+1] - 1] += 1
        return counts / len(d)

    @staticmethod
    def lag_autocorrelation(draws, lag=1):
        """滯後自相關 - 每個號碼在lag期前後的相關性"""
        from .data_loader import build_binary_matrix
        bmat = build_binary_matrix(draws)
        N, K = bmat.shape
        if N <= lag:
            return np.zeros(K)
        corrs = np.zeros(K)
        for j in range(K):
            x = bmat[lag:, j].astype(float)
            y = bmat[:-lag, j].astype(float)
            if x.std() > 0 and y.std() > 0:
                corrs[j] = np.corrcoef(x, y)[0, 1]
        return corrs
    
    @staticmethod
    def fourier_phase(draws, top_k=3):
        """傅立葉相位分析 - 各號碼的周期性"""
        from .data_loader import build_binary_matrix
        bmat = build_binary_matrix(draws)
        N, K = bmat.shape
        phases = np.zeros((K, top_k))
        magnitudes = np.zeros((K, top_k))
        for j in range(K):
            fft = np.fft.rfft(bmat[:, j])
            mag = np.abs(fft[1:])
            top_idx = np.argsort(mag)[-top_k:][::-1]
            for ki, idx in enumerate(top_idx):
                phases[j, ki] = np.angle(fft[idx + 1])
                magnitudes[j, ki] = mag[idx]
        return phases, magnitudes

    @staticmethod
    def markov_transition(draws, order=1):
        """馬可夫轉移機率"""
        from .data_loader import build_binary_matrix
        bmat = build_binary_matrix(draws)
        N, K = bmat.shape
        # P(appear | appeared/not last time)
        trans = np.zeros((K, 2, 2))  # [number][prev_state][curr_state]
        for j in range(K):
            for i in range(order, N):
                prev = int(bmat[i - order, j])
                curr = int(bmat[i, j])
                trans[j, prev, curr] += 1
        # normalize
        probs = np.zeros((K, 2))
        for j in range(K):
            for s in range(2):
                total = trans[j, s, :].sum()
                if total > 0:
                    probs[j, s] = trans[j, s, 1] / total
        return probs

    @staticmethod
    def deviation_score(draws, window=100):
        """偏差分數 - 與期望頻率的偏離程度"""
        expected = 6.0 / 49.0
        freq = FeatureLibrary.frequency(draws, window)
        return (freq - expected) / max(expected, 1e-10)

    @staticmethod
    def gap_pressure(draws):
        """Gap Pressure - 超過平均間隔多少個標準差"""
        curr_gaps = FeatureLibrary.gap_current(draws)
        means, stds = FeatureLibrary.gap_mean_std(draws)
        pressure = np.zeros(49)
        for j in range(49):
            if stds[j] > 0:
                pressure[j] = (curr_gaps[j] - means[j]) / stds[j]
            else:
                pressure[j] = 0
        return pressure

    @staticmethod
    def zonal_density_score(draws, window=10, zones=5):
        """板塊聚集度特徵 - 計算近期各區間出號密度與歷史均值的反差，尋找即將反彈的冷區"""
        d_recent = draws[-window:]
        zone_size = 49 // zones + 1
        
        # Calculate expected density across the entire history
        all_dist = np.zeros(zones)
        for row in draws:
            for n in row:
                z = min((n - 1) // zone_size, zones - 1)
                all_dist[z] += 1
        expected_prob = all_dist / np.sum(all_dist)
        
        # Calculate recent density
        recent_dist = np.zeros(zones)
        for row in d_recent:
            for n in row:
                z = min((n - 1) // zone_size, zones - 1)
                recent_dist[z] += 1
        recent_prob = recent_dist / max(1, np.sum(recent_dist))
        
        # Positive score means zone is colder than expected -> due for mean reversion
        zone_scores = expected_prob - recent_prob
        
        scores = np.zeros(49)
        for j in range(49):
            z = min(j // zone_size, zones - 1)
            scores[j] = zone_scores[z]
            
        return scores

    @staticmethod
    def gap_momentum(draws):
        """間隔動能特徵 - 計算 Gap 的改變速度 (前一次 Gap - 當前 Gap)"""
        momentum = np.zeros(49)
        for j in range(49):
            positions = [i for i in range(len(draws)) if (j + 1) in draws[i]]
            if len(positions) >= 2:
                current_gap = (len(draws) - 1) - positions[-1]
                prev_gap = positions[-1] - positions[-2] - 1
                
                # 如果 prev_gap 很大，但 current_gap 很小，代表號碼正在加速 (動能轉強)
                momentum[j] = prev_gap - current_gap
            else:
                momentum[j] = 0
        return momentum
