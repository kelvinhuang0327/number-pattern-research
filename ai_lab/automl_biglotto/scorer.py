"""
四維度評分系統
Scorer: Stable / Burst / Conditional / Synergy
"""
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

from .backtest_engine import BacktestResult
from .config import SCORE_WEIGHTS


@dataclass
class StrategyScore:
    strategy_name: str = ''
    stable_score: float = 0.0
    burst_score: float = 0.0
    conditional_score: float = 0.0
    synergy_score: float = 0.0
    composite_score: float = 0.0
    classification: str = 'MIXED'

    def to_dict(self):
        return asdict(self)


class StrategyScorer:
    """四維度策略評分器"""

    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or SCORE_WEIGHTS

    def score(self, result: BacktestResult,
              multi_window_results: Optional[Dict[str, BacktestResult]] = None,
              synergy_data: Optional[Dict] = None) -> StrategyScore:
        """計算所有維度分數"""
        stable = self._stable_score(result, multi_window_results)
        burst = self._burst_score(result)
        conditional = self._conditional_score(result)
        synergy = self._synergy_score(result, synergy_data)

        composite = (
            self.weights['stable'] * stable +
            self.weights['burst'] * burst +
            self.weights['conditional'] * conditional +
            self.weights['synergy'] * synergy
        )

        # 分類
        if stable >= 60:
            classification = 'STABLE'
        elif burst >= 60:
            classification = 'BURST'
        elif conditional >= 60:
            classification = 'CONDITIONAL'
        elif synergy >= 60:
            classification = 'SYNERGY'
        else:
            classification = 'MIXED'

        return StrategyScore(
            strategy_name=result.strategy_name,
            stable_score=round(stable, 1),
            burst_score=round(burst, 1),
            conditional_score=round(conditional, 1),
            synergy_score=round(synergy, 1),
            composite_score=round(composite, 1),
            classification=classification,
        )

    def _stable_score(self, result: BacktestResult,
                      multi_window: Optional[Dict[str, BacktestResult]] = None) -> float:
        """
        穩定型評分 (0-100)
        = Edge 貢獻 (0-60) + 穩定度 (0-20) + 多窗口一致性 (0-20)
        """
        # Edge 貢獻：edge_pct * 20，上限 60
        edge_pts = min(result.edge_pct * 20, 60) if result.edge_pct > 0 else 0

        # 穩定度：cv 越小越穩定
        cv = result.cv if result.cv < 999 else 10
        stability_pts = max(0, (1 - min(cv, 5) / 5) * 20)

        # 多窗口一致性
        multi_pts = 0
        if multi_window:
            n_positive = sum(1 for r in multi_window.values() if r.edge > 0)
            n_total = len(multi_window)
            multi_pts = 20 * (n_positive / n_total) if n_total > 0 else 0

        return min(100, edge_pts + stability_pts + multi_pts)

    def _burst_score(self, result: BacktestResult) -> float:
        """
        爆發型評分 (0-100)
        = 連續M3+ (0-25) + 峰值30期率 (0-25) + M4+率 (0-25) + 偏度 (0-25)
        """
        baseline = result.baseline_rate
        if baseline <= 0:
            return 0

        # 連續 M3+
        expected_consec = 1.0 / (1 - result.m3_rate) if result.m3_rate < 1 else 100
        consec_ratio = result.burst_max_consecutive_m3 / max(expected_consec, 1)
        consec_pts = min(consec_ratio, 4) / 4 * 25

        # 峰值 30 期率
        peak_ratio = result.peak_30p_m3_rate / baseline if baseline > 0 else 0
        peak_pts = min(peak_ratio, 5) / 5 * 25

        # M4+ 率加成
        baseline_m4 = baseline * 0.1  # 粗略估計
        m4_ratio = result.m4_rate / max(baseline_m4, 0.001)
        m4_pts = min(m4_ratio, 3) / 3 * 25

        # 偏度（命中分布的正偏度表示爆發潛力）
        matches = result.per_period_best_match
        if len(matches) > 5:
            from scipy.stats import skew
            sk = skew(matches)
            skew_pts = min(abs(sk), 2) / 2 * 25
        else:
            skew_pts = 0

        return min(100, consec_pts + peak_pts + m4_pts + skew_pts)

    def _conditional_score(self, result: BacktestResult) -> float:
        """
        條件觸發型評分 (0-100)
        = 滾動方差 (0-40) + Train/Test差異 (0-30) + 非零edge條件 (0-30)
        """
        # 滾動方差：方差高 = 條件性強
        matches = result.per_period_best_match
        if len(matches) < 30:
            return 0

        m3_flags = [1 if m >= 3 else 0 for m in matches]
        rolling_rates = []
        for i in range(0, len(m3_flags) - 30 + 1, 15):
            chunk = m3_flags[i:i + 30]
            rolling_rates.append(sum(chunk) / len(chunk))

        rolling_var = np.var(rolling_rates) if rolling_rates else 0
        var_pts = min(rolling_var / 0.01, 1) * 40

        # Train/Test 差異：如果差異大，表示條件性
        edge_diff = abs(result.half1_edge - result.half2_edge)
        diff_pts = min(edge_diff / 0.02, 1) * 30

        # 正面 edge 的比例
        positive_chunks = sum(1 for r in rolling_rates if r > result.baseline_rate)
        pos_ratio = positive_chunks / len(rolling_rates) if rolling_rates else 0
        # 不是全正也不是全負 = 更條件化
        conditional_indicator = 1 - abs(pos_ratio - 0.5) * 2
        cond_pts = conditional_indicator * 30

        return min(100, var_pts + diff_pts + cond_pts)

    def _synergy_score(self, result: BacktestResult,
                       synergy_data: Optional[Dict] = None) -> float:
        """
        組合增益型評分 (0-100)
        = 獨特度 (0-40) + 邊際貢獻 (0-30) + 互補性 (0-30)
        """
        if synergy_data is None:
            # 無協同數據時，根據策略特性給予基本分
            return 30.0  # 預設中等分數

        # 獨特度 (1 - 平均overlap)
        avg_overlap = synergy_data.get('avg_overlap', 0.5)
        uniqueness_pts = (1 - avg_overlap) * 40

        # 邊際貢獻
        marginal = synergy_data.get('marginal_contribution', 0)
        marginal_pts = min(marginal / 0.02, 1) * 30

        # 互補性 (1 - 平均相關)
        avg_corr = synergy_data.get('avg_correlation', 0.5)
        complement_pts = (1 - abs(avg_corr)) * 30

        return min(100, uniqueness_pts + marginal_pts + complement_pts)


def compute_synergy_data(result: BacktestResult,
                         other_results: List[BacktestResult]) -> Dict:
    """計算策略的協同數據"""
    if not other_results or not result.per_period_best_match:
        return {'avg_overlap': 0.5, 'marginal_contribution': 0, 'avg_correlation': 0.5}

    my_flags = np.array([1 if m >= 3 else 0 for m in result.per_period_best_match])

    overlaps = []
    correlations = []

    for other in other_results:
        if not other.per_period_best_match:
            continue
        other_flags = np.array([1 if m >= 3 else 0 for m in other.per_period_best_match])

        # 對齊長度
        min_len = min(len(my_flags), len(other_flags))
        if min_len == 0:
            continue

        a = my_flags[:min_len]
        b = other_flags[:min_len]

        # Overlap: 同時 M3+ 的比例
        both_hit = np.sum((a == 1) & (b == 1))
        any_hit = np.sum((a == 1) | (b == 1))
        overlap = both_hit / any_hit if any_hit > 0 else 0
        overlaps.append(overlap)

        # 相關性
        if np.std(a) > 0 and np.std(b) > 0:
            corr = np.corrcoef(a, b)[0, 1]
            correlations.append(corr)

    avg_overlap = np.mean(overlaps) if overlaps else 0.5
    avg_corr = np.mean(correlations) if correlations else 0.5

    return {
        'avg_overlap': float(avg_overlap),
        'marginal_contribution': float(result.edge),  # 簡化：以自身 edge 代替
        'avg_correlation': float(avg_corr),
    }
