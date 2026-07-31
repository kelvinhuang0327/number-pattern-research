"""
策略融合測試
Strategy Fusion: 雙策略/三策略組合、投票集成、條件切換、動態權重
"""
import numpy as np
from collections import Counter
from typing import List, Dict, Callable, Tuple
from itertools import combinations

from .config import MAX_NUM, PICK, n_bet_baseline
from .backtest_engine import RollingBacktester, BacktestResult


class StrategyFusion:
    """策略組合與融合測試器"""

    def __init__(self, backtester: RollingBacktester):
        self.backtester = backtester

    def test_all_pairs(self, top_strategies: Dict[str, Callable],
                       test_periods: int = 150,
                       max_pairs: int = 100,
                       verbose: bool = True) -> List[Dict]:
        """
        測試所有雙策略組合
        每對策略產生 2 注（各策略 1 注），回測 M3+ 率
        """
        names = list(top_strategies.keys())
        results = []
        pairs = list(combinations(names, 2))[:max_pairs]

        for i, (name_a, name_b) in enumerate(pairs):
            func_a = top_strategies[name_a]
            func_b = top_strategies[name_b]

            def combined(h, a=func_a, b=func_b):
                bets_a = a(h)
                bets_b = b(h)
                if isinstance(bets_a[0], int):
                    bets_a = [bets_a]
                if isinstance(bets_b[0], int):
                    bets_b = [bets_b]
                return [bets_a[0], bets_b[0]]

            combo_name = f"PAIR({name_a}+{name_b})"
            result = self.backtester.run(combined, test_periods=test_periods,
                                         strategy_name=combo_name)

            # 計算 overlap
            try:
                test_hist = self.backtester.all_draws[:-1]
                bets = combined(test_hist)
                overlap = len(set(bets[0]) & set(bets[1])) / PICK
            except Exception:
                overlap = 0

            results.append({
                'name': combo_name,
                'strategies': [name_a, name_b],
                'n_bets': result.n_bets,
                'edge_pct': result.edge_pct,
                'z_score': result.z_score,
                'p_value': result.p_value,
                'overlap': overlap,
                'result': result,
            })

            if verbose and (i + 1) % 20 == 0:
                print(f"  Pairs: {i+1}/{len(pairs)}")

        results.sort(key=lambda x: -x['edge_pct'])
        return results

    def test_all_triples(self, top_strategies: Dict[str, Callable],
                         test_periods: int = 150,
                         max_triples: int = 50,
                         verbose: bool = True) -> List[Dict]:
        """測試所有三策略組合"""
        names = list(top_strategies.keys())
        results = []
        triples = list(combinations(names, 3))[:max_triples]

        for i, (na, nb, nc) in enumerate(triples):
            fa, fb, fc = top_strategies[na], top_strategies[nb], top_strategies[nc]

            def combined(h, a=fa, b=fb, c=fc):
                ba = a(h)
                bb = b(h)
                bc = c(h)
                if isinstance(ba[0], int):
                    ba = [ba]
                if isinstance(bb[0], int):
                    bb = [bb]
                if isinstance(bc[0], int):
                    bc = [bc]
                return [ba[0], bb[0], bc[0]]

            combo_name = f"TRIPLE({na}+{nb}+{nc})"
            result = self.backtester.run(combined, test_periods=test_periods,
                                         strategy_name=combo_name)

            results.append({
                'name': combo_name,
                'strategies': [na, nb, nc],
                'n_bets': result.n_bets,
                'edge_pct': result.edge_pct,
                'z_score': result.z_score,
                'p_value': result.p_value,
                'result': result,
            })

            if verbose and (i + 1) % 10 == 0:
                print(f"  Triples: {i+1}/{len(triples)}")

        results.sort(key=lambda x: -x['edge_pct'])
        return results

    def voting_ensemble(self, strategies: Dict[str, Callable],
                        history: List[Dict], threshold: int = 3) -> List[int]:
        """投票集成：N 策略投票，選 >= threshold 的號碼"""
        votes = Counter()
        for name, func in strategies.items():
            try:
                bets = func(history)
                if isinstance(bets[0], int):
                    bets = [bets]
                for bet in bets:
                    for n in bet:
                        votes[n] += 1
            except Exception:
                continue

        # 選得票 >= threshold 的
        selected = [n for n, v in votes.items() if v >= threshold]
        if len(selected) < PICK:
            # 補充得票最多的
            remaining = sorted(votes.items(), key=lambda x: -x[1])
            for n, _ in remaining:
                if n not in selected and len(selected) < PICK:
                    selected.append(n)
        return sorted(selected[:PICK])

    def voting_ensemble_backtest(self, strategies: Dict[str, Callable],
                                 test_periods: int = 150,
                                 threshold: int = 3) -> BacktestResult:
        """投票集成的回測"""
        def voting_func(h):
            return [self.voting_ensemble(strategies, h, threshold)]

        return self.backtester.run(voting_func, test_periods=test_periods,
                                    strategy_name=f"VOTE(n={len(strategies)},t={threshold})")

    def conditional_switching_backtest(self, strategies: Dict[str, Callable],
                                       test_periods: int = 150) -> BacktestResult:
        """
        條件切換：偵測 regime (hot/cold/neutral) 並切換策略
        """
        strategy_list = list(strategies.items())
        if len(strategy_list) < 2:
            return BacktestResult()

        def switching_func(h):
            if len(h) < 30:
                return strategy_list[0][1](h)

            # 偵測 regime
            recent30 = h[-30:]
            freq = Counter(n for d in recent30 for n in d['numbers'][:PICK])
            top6_freq = sum(v for _, v in freq.most_common(6))
            total = sum(freq.values())
            concentration = top6_freq / total if total > 0 else 0

            if concentration > 0.20:
                # Hot regime: 用第一個策略
                return strategy_list[0][1](h)
            elif concentration < 0.14:
                # Cold regime: 用第二個策略
                return strategy_list[1][1](h)
            else:
                # Neutral: 用投票
                votes = Counter()
                for name, func in strategy_list[:3]:
                    try:
                        bets = func(h)
                        if isinstance(bets[0], int):
                            bets = [bets]
                        for b in bets:
                            for n in b:
                                votes[n] += 1
                    except Exception:
                        continue
                ranked = sorted(votes.items(), key=lambda x: -x[1])
                return [sorted([n for n, _ in ranked[:PICK]])]

        return self.backtester.run(switching_func, test_periods=test_periods,
                                    strategy_name="COND_SWITCH")

    def dynamic_weight_backtest(self, strategies: Dict[str, Callable],
                                 test_periods: int = 150,
                                 lookback: int = 30) -> BacktestResult:
        """
        動態權重：根據近期表現調整策略權重
        """
        strategy_list = list(strategies.items())

        def dynamic_func(h):
            if len(h) < lookback + 10:
                return strategy_list[0][1](h)

            # 評估每個策略在近 lookback 期的表現
            weights = {}
            for name, func in strategy_list:
                hits = 0
                for j in range(lookback):
                    idx = len(h) - lookback + j
                    if idx < 10:
                        continue
                    try:
                        bets = func(h[:idx])
                        if isinstance(bets[0], int):
                            bets = [bets]
                        actual = set(h[idx]['numbers'][:PICK])
                        best = max(len(set(b) & actual) for b in bets)
                        hits += best
                    except Exception:
                        continue
                weights[name] = hits + 1  # +1 smoothing

            # 加權投票
            total_w = sum(weights.values())
            scores = Counter()
            for name, func in strategy_list:
                try:
                    bets = func(h)
                    if isinstance(bets[0], int):
                        bets = [bets]
                    w = weights.get(name, 1) / total_w
                    for b in bets:
                        for n in b:
                            scores[n] += w
                except Exception:
                    continue

            ranked = sorted(scores.items(), key=lambda x: -x[1])
            return [sorted([n for n, _ in ranked[:PICK]])]

        return self.backtester.run(dynamic_func, test_periods=test_periods,
                                    strategy_name="DYN_WEIGHT")
