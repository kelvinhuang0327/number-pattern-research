"""
滾動回測引擎
Rolling Backtest Engine with Permutation Test, Noise Injection, Multi-Window
"""
import os
import sys
import json
import copy
import sqlite3
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Callable, Optional
from collections import Counter

from .config import MAX_NUM, PICK, P_SINGLE_M3, SEED, MIN_HISTORY, n_bet_baseline


@dataclass
class BacktestResult:
    """回測結果"""
    strategy_name: str = ''
    n_bets: int = 1
    test_periods: int = 0
    total_valid: int = 0
    m3_count: int = 0
    m3_rate: float = 0.0
    baseline_rate: float = 0.0
    edge: float = 0.0
    edge_pct: float = 0.0
    z_score: float = 0.0
    p_value: float = 0.0
    match_distribution: Dict[int, int] = field(default_factory=dict)
    per_period_best_match: List[int] = field(default_factory=list)
    special_hits: int = 0
    stability_std: float = 0.0
    cv: float = 0.0
    max_drought: int = 0
    sharpe_like: float = 0.0
    burst_max_consecutive_m3: int = 0
    peak_30p_m3_rate: float = 0.0
    half1_edge: float = 0.0
    half2_edge: float = 0.0
    m4_count: int = 0
    m4_rate: float = 0.0

    def to_dict(self):
        d = asdict(self)
        d['match_distribution'] = {str(k): v for k, v in self.match_distribution.items()}
        d.pop('per_period_best_match', None)
        return d


def load_draws(db_path: Optional[str] = None) -> List[Dict]:
    """從 SQLite 載入所有大樂透開獎資料，依日期升序"""
    if db_path is None:
        project_root = Path(__file__).parent.parent.parent
        db_path = str(project_root / 'lottery_api' / 'data' / 'lottery_v2.db')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws "
        "WHERE lottery_type=? ORDER BY date ASC, draw ASC",
        ('BIG_LOTTO',)
    )
    draws = []
    for row in cursor.fetchall():
        draws.append({
            'draw': row[0],
            'date': row[1],
            'numbers': json.loads(row[2]) if isinstance(row[2], str) else row[2],
            'special': row[3] or 0,
            'lotteryType': 'BIG_LOTTO',
        })
    conn.close()

    for d in draws:
        if len(d['numbers']) > PICK:
            d['numbers'] = d['numbers'][:PICK]

    return draws


class RollingBacktester:
    """滾動式回測引擎"""

    def __init__(self, db_path: Optional[str] = None):
        self.all_draws = load_draws(db_path)
        if not self.all_draws:
            raise RuntimeError("No BIG_LOTTO draws found in database")

    def run(self, strategy_func: Callable, test_periods: int = 150,
            seed: int = SEED, min_history: int = MIN_HISTORY,
            strategy_name: str = '') -> BacktestResult:
        """
        滾動回測核心：
        for i in range(test_periods):
            target_idx = len(all_draws) - test_periods + i
            hist = all_draws[:target_idx]
            target = all_draws[target_idx]
        """
        np.random.seed(seed)

        all_draws = self.all_draws
        test_periods = min(test_periods, len(all_draws) - min_history)
        if test_periods <= 0:
            return BacktestResult(strategy_name=strategy_name)

        match_dist = Counter()
        special_hits = 0
        total = 0
        per_period_best = []
        half_point = test_periods // 2
        half1_m3 = 0
        half1_total = 0
        half2_m3 = 0
        half2_total = 0
        n_bets_detected = 1

        for i in range(test_periods):
            target_idx = len(all_draws) - test_periods + i
            if target_idx <= 0:
                per_period_best.append(0)
                continue

            target_draw = all_draws[target_idx]
            hist = all_draws[:target_idx]

            if len(hist) < 10:
                per_period_best.append(0)
                continue

            try:
                bets = strategy_func(hist)
                if not bets:
                    per_period_best.append(0)
                    continue

                # 確保 bets 是 list of lists
                if isinstance(bets[0], int):
                    bets = [bets]

                n_bets_detected = len(bets)
                actual = set(target_draw['numbers'][:PICK])
                actual_special = target_draw.get('special', 0)

                best_match = 0
                any_special = False
                for bet in bets:
                    bet_set = set(bet)
                    mc = len(bet_set & actual)
                    best_match = max(best_match, mc)
                    if actual_special and actual_special in bet_set:
                        any_special = True

                match_dist[best_match] += 1
                if any_special:
                    special_hits += 1
                per_period_best.append(best_match)
                total += 1

                is_m3 = best_match >= 3
                if i < half_point:
                    half1_total += 1
                    if is_m3:
                        half1_m3 += 1
                else:
                    half2_total += 1
                    if is_m3:
                        half2_m3 += 1

            except Exception:
                per_period_best.append(0)
                continue

        if total == 0:
            return BacktestResult(strategy_name=strategy_name)

        # 計算統計
        m3_count = sum(match_dist[k] for k in match_dist if k >= 3)
        m4_count = sum(match_dist[k] for k in match_dist if k >= 4)
        m3_rate = m3_count / total
        m4_rate = m4_count / total
        baseline = n_bet_baseline(n_bets_detected)
        edge = m3_rate - baseline

        # z-score
        se = np.sqrt(baseline * (1 - baseline) / total) if total > 0 else 1
        z = edge / se if se > 0 else 0

        # p-value (one-tailed)
        from scipy.stats import norm
        p_val = 1 - norm.cdf(z)

        # 穩定度 (rolling 30-period windows)
        rolling_rates = []
        win_size = min(30, total // 3) if total >= 9 else total
        if win_size > 0:
            m3_flags = [1 if m >= 3 else 0 for m in per_period_best]
            for start in range(0, len(m3_flags) - win_size + 1, win_size):
                chunk = m3_flags[start:start + win_size]
                if len(chunk) > 0:
                    rolling_rates.append(sum(chunk) / len(chunk))

        stability_std = float(np.std(rolling_rates)) if rolling_rates else 0.0
        mean_rate = float(np.mean(rolling_rates)) if rolling_rates else 0.0
        cv = stability_std / mean_rate if mean_rate > 0 else 999.0
        sharpe = edge / stability_std if stability_std > 0 else 0.0

        # 最大乾旱期
        m3_flags_full = [1 if m >= 3 else 0 for m in per_period_best]
        max_drought = 0
        current_drought = 0
        for flag in m3_flags_full:
            if flag == 0:
                current_drought += 1
                max_drought = max(max_drought, current_drought)
            else:
                current_drought = 0

        # 最大連續 M3+
        max_consec = 0
        current_consec = 0
        for flag in m3_flags_full:
            if flag == 1:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0

        # 峰值 30 期 M3+ 率
        peak_30p = 0.0
        if len(m3_flags_full) >= 30:
            for start in range(len(m3_flags_full) - 30 + 1):
                chunk = m3_flags_full[start:start + 30]
                rate = sum(chunk) / 30
                peak_30p = max(peak_30p, rate)
        elif m3_flags_full:
            peak_30p = sum(m3_flags_full) / len(m3_flags_full)

        # Train/Test split edge
        h1_rate = half1_m3 / half1_total if half1_total > 0 else 0
        h2_rate = half2_m3 / half2_total if half2_total > 0 else 0
        half1_edge = h1_rate - baseline
        half2_edge = h2_rate - baseline

        return BacktestResult(
            strategy_name=strategy_name,
            n_bets=n_bets_detected,
            test_periods=test_periods,
            total_valid=total,
            m3_count=m3_count,
            m3_rate=m3_rate,
            baseline_rate=baseline,
            edge=edge,
            edge_pct=edge * 100,
            z_score=z,
            p_value=p_val,
            match_distribution=dict(match_dist),
            per_period_best_match=per_period_best,
            special_hits=special_hits,
            stability_std=stability_std,
            cv=cv,
            max_drought=max_drought,
            sharpe_like=sharpe,
            burst_max_consecutive_m3=max_consec,
            peak_30p_m3_rate=peak_30p,
            half1_edge=half1_edge,
            half2_edge=half2_edge,
            m4_count=m4_count,
            m4_rate=m4_rate,
        )

    def run_multi_window(self, strategy_func: Callable,
                         windows: Dict[str, int] = None,
                         strategy_name: str = '') -> Dict[str, BacktestResult]:
        """多時間尺度回測"""
        if windows is None:
            from .config import TEST_WINDOWS
            windows = TEST_WINDOWS

        results = {}
        for label, periods in windows.items():
            results[label] = self.run(
                strategy_func, test_periods=periods,
                strategy_name=f"{strategy_name}_{label}"
            )
        return results

    def run_multi_seed(self, strategy_func: Callable, test_periods: int = 150,
                       seeds: range = range(42, 52),
                       strategy_name: str = '') -> Dict:
        """多種子測試"""
        edges = []
        for s in seeds:
            r = self.run(strategy_func, test_periods=test_periods,
                         seed=s, strategy_name=strategy_name)
            edges.append(r.edge)
        return {
            'mean_edge': float(np.mean(edges)),
            'std_edge': float(np.std(edges)),
            'min_edge': float(np.min(edges)),
            'max_edge': float(np.max(edges)),
            'n_seeds': len(edges),
            'all_edges': edges,
        }

    def permutation_test(self, strategy_func: Callable, test_periods: int = 150,
                         n_shuffles: int = 100, seed: int = SEED,
                         strategy_name: str = '') -> Dict:
        """
        排列檢定 (P3-style shuffle test)
        打亂開獎號碼的時序指派，建立 null distribution
        """
        real_result = self.run(strategy_func, test_periods=test_periods,
                               seed=seed, strategy_name=strategy_name)
        real_edge = real_result.edge

        rng = np.random.RandomState(seed)
        shuffle_edges = []

        for s in range(n_shuffles):
            shuffled_draws = copy.deepcopy(self.all_draws)
            nums_pool = [d['numbers'][:] for d in shuffled_draws]
            specials_pool = [d.get('special', 0) for d in shuffled_draws]
            indices = rng.permutation(len(nums_pool))
            for i, d in enumerate(shuffled_draws):
                d['numbers'] = nums_pool[indices[i]]
                d['special'] = specials_pool[indices[i]]

            edge = self._run_on_data(shuffled_draws, strategy_func,
                                     test_periods, seed)
            shuffle_edges.append(edge)

        shuffle_edges = np.array(shuffle_edges)
        p_value = float(np.mean(shuffle_edges >= real_edge))
        cohens_d = float((real_edge - np.mean(shuffle_edges)) /
                         (np.std(shuffle_edges) + 1e-10))

        return {
            'real_edge': real_edge,
            'real_edge_pct': real_edge * 100,
            'shuffle_mean': float(np.mean(shuffle_edges)),
            'shuffle_std': float(np.std(shuffle_edges)),
            'p_value': p_value,
            'cohens_d': cohens_d,
            'n_shuffles': n_shuffles,
            'verdict': 'SIGNAL' if p_value < 0.05 else 'MARGINAL' if p_value < 0.10 else 'NO_SIGNAL',
            'strategy_name': strategy_name,
        }

    def noise_robustness_test(self, strategy_func: Callable, test_periods: int = 150,
                              noise_levels: List[float] = None,
                              seed: int = SEED,
                              strategy_name: str = '') -> Dict:
        """雜訊注入測試"""
        if noise_levels is None:
            noise_levels = [0.05, 0.10, 0.20]

        real_result = self.run(strategy_func, test_periods=test_periods,
                               seed=seed, strategy_name=strategy_name)
        real_edge = real_result.edge

        rng = np.random.RandomState(seed)
        results = {'real_edge': real_edge, 'levels': {}}

        for level in noise_levels:
            noisy_draws = copy.deepcopy(self.all_draws)
            for d in noisy_draws:
                if rng.random() < level:
                    d['numbers'] = sorted(rng.choice(range(1, MAX_NUM + 1),
                                                     size=PICK, replace=False).tolist())
                    d['special'] = int(rng.randint(1, MAX_NUM + 1))

            noisy_edge = self._run_on_data(noisy_draws, strategy_func,
                                            test_periods, seed)
            degradation = (real_edge - noisy_edge) / abs(real_edge) if abs(real_edge) > 1e-6 else 0
            results['levels'][level] = {
                'noisy_edge': noisy_edge,
                'degradation': degradation,
                'robust': degradation < 0.5,
            }

        all_robust = all(r['robust'] for r in results['levels'].values())
        results['overall_robust'] = all_robust
        return results

    def time_series_split_validation(self, strategy_func: Callable,
                                      n_splits: int = 3,
                                      strategy_name: str = '') -> Dict:
        """Walk-forward 時序驗證"""
        total = len(self.all_draws) - MIN_HISTORY
        if total <= n_splits:
            return {'splits': [], 'consistent': False}

        split_size = total // n_splits
        edges = []

        for s in range(n_splits):
            test_start = MIN_HISTORY + s * split_size
            test_end = min(test_start + split_size, len(self.all_draws))
            test_count = test_end - test_start

            m3_count = 0
            valid = 0
            n_bets = 1

            for i in range(test_count):
                idx = test_start + i
                if idx >= len(self.all_draws):
                    break

                hist = self.all_draws[:idx]
                target = self.all_draws[idx]

                try:
                    bets = strategy_func(hist)
                    if not bets:
                        continue
                    if isinstance(bets[0], int):
                        bets = [bets]
                    n_bets = len(bets)

                    actual = set(target['numbers'][:PICK])
                    best = max(len(set(b) & actual) for b in bets)
                    if best >= 3:
                        m3_count += 1
                    valid += 1
                except Exception:
                    continue

            rate = m3_count / valid if valid > 0 else 0
            baseline = n_bet_baseline(n_bets)
            edge_val = rate - baseline
            edges.append({
                'split': s,
                'test_range': f"{test_start}-{test_end}",
                'valid': valid,
                'm3_rate': rate,
                'edge': edge_val,
            })

        all_positive = all(e['edge'] > 0 for e in edges)
        return {
            'splits': edges,
            'n_splits': n_splits,
            'consistent': all_positive,
            'mean_edge': float(np.mean([e['edge'] for e in edges])),
            'std_edge': float(np.std([e['edge'] for e in edges])),
        }

    def decay_test(self, strategy_func: Callable,
                   windows: List[int] = None,
                   seed: int = SEED,
                   strategy_name: str = '') -> Dict:
        """
        多窗口衰減偵測 (Decay Detection)
        在 short/medium/long/ultra 四個窗口回測同一策略，
        偵測 edge 是否隨窗口拉長而衰減（SHORT_MOMENTUM 模式）。

        判定規則：
        - DECAYING：最短窗口 edge > 最長窗口 edge，且長窗口 edge <= 0
        - STABLE_POSITIVE：所有窗口 edge > 0
        - INVERTED：長窗口反而更好（罕見但可能）
        - FLAT_ZERO：所有窗口 edge ≈ 0
        """
        if windows is None:
            windows = [50, 150, 500, 1500]
        # Filter windows to those that fit data
        max_test = len(self.all_draws) - MIN_HISTORY
        windows = [w for w in windows if w <= max_test]
        if not windows:
            return {'verdict': 'INSUFFICIENT_DATA', 'windows': {}}

        results_by_window = {}
        for w in sorted(windows):
            result = self.run(strategy_func, test_periods=w,
                              seed=seed, strategy_name=f"{strategy_name}_{w}p")
            results_by_window[w] = {
                'test_periods': w,
                'edge': result.edge,
                'edge_pct': result.edge_pct,
                'z_score': result.z_score,
                'p_value': result.p_value,
                'm3_rate': result.m3_rate,
                'half1_edge': result.half1_edge,
                'half2_edge': result.half2_edge,
            }

        # Analyze decay pattern
        edges = [results_by_window[w]['edge'] for w in sorted(results_by_window.keys())]
        edge_pcts = [results_by_window[w]['edge_pct'] for w in sorted(results_by_window.keys())]
        sorted_windows = sorted(results_by_window.keys())

        shortest_edge = edges[0]
        longest_edge = edges[-1]

        # Decay rate: how much edge drops per unit window expansion
        if len(edges) >= 2 and abs(shortest_edge) > 1e-6:
            decay_ratio = (shortest_edge - longest_edge) / abs(shortest_edge)
        else:
            decay_ratio = 0.0

        # Verdict
        if len(edges) >= 3 and edges[0] > 0 and longest_edge <= 0 and decay_ratio > 0.5:
            verdict = 'DECAYING'
        elif all(e > 0 for e in edges):
            verdict = 'STABLE_POSITIVE'
        elif len(edges) >= 2 and edges[-1] > edges[0] and edges[-1] > 0:
            verdict = 'INVERTED'
        elif all(abs(e) < 0.005 for e in edges):
            verdict = 'FLAT_ZERO'
        elif longest_edge <= 0 and shortest_edge > 0:
            verdict = 'DECAYING'
        else:
            verdict = 'MIXED'

        # Is it adoptable? Only STABLE_POSITIVE passes
        adoptable = verdict == 'STABLE_POSITIVE'

        return {
            'strategy_name': strategy_name,
            'windows': results_by_window,
            'sorted_windows': sorted_windows,
            'edge_trajectory': edge_pcts,
            'decay_ratio': decay_ratio,
            'verdict': verdict,
            'adoptable': adoptable,
        }

    def _run_on_data(self, draws: List[Dict], strategy_func: Callable,
                     test_periods: int, seed: int) -> float:
        """在指定資料上執行回測，回傳 edge"""
        test_periods = min(test_periods, len(draws) - MIN_HISTORY)
        if test_periods <= 0:
            return 0.0

        m3_count = 0
        total = 0
        n_bets = 1

        for i in range(test_periods):
            target_idx = len(draws) - test_periods + i
            if target_idx <= 0:
                continue

            hist = draws[:target_idx]
            target = draws[target_idx]
            if len(hist) < 10:
                continue

            try:
                bets = strategy_func(hist)
                if not bets:
                    continue
                if isinstance(bets[0], int):
                    bets = [bets]
                n_bets = len(bets)
                actual = set(target['numbers'][:PICK])
                best = max(len(set(b) & actual) for b in bets)
                if best >= 3:
                    m3_count += 1
                total += 1
            except Exception:
                continue

        if total == 0:
            return 0.0

        m3_rate = m3_count / total
        baseline = n_bet_baseline(n_bets)
        return m3_rate - baseline
