#!/usr/bin/env python3
"""
共現圖分析模組 (Co-occurrence Graph Analysis)
============================================

核心理念：
將號碼視為圖的節點，共現次數作為邊權重，
使用圖算法找出「核心」號碼和「社區」結構。

方法：
1. 度中心性 (Degree Centrality) - 找出與最多號碼共現的號碼
2. 介數中心性 (Betweenness) - 找出「橋接」不同群落的號碼
3. 社區檢測 (Community Detection) - 找出號碼群落
4. PageRank - 找出「重要」號碼

使用方式：
    from lottery_api.models.cooccurrence_graph import GraphPredictor

    predictor = GraphPredictor()
    bets = predictor.predict(history, num_bets=4)
"""

import random
import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict, Set, Tuple
from itertools import combinations


class CooccurrenceGraph:
    """共現圖"""

    def __init__(self, max_num: int = 49):
        self.max_num = max_num
        self.edges = defaultdict(int)  # (a, b) -> weight
        self.node_weights = Counter()  # node -> total weight

    def build_from_history(self, history: List[Dict], window: int = 100):
        """從歷史數據建立圖"""
        self.edges.clear()
        self.node_weights.clear()

        for d in history[-window:]:
            nums = d.get('numbers', [])
            if isinstance(nums, str):
                nums = eval(nums)

            for a, b in combinations(sorted(nums), 2):
                self.edges[(a, b)] += 1
                self.node_weights[a] += 1
                self.node_weights[b] += 1

    def degree_centrality(self) -> Dict[int, float]:
        """計算度中心性"""
        degrees = Counter()
        for (a, b), w in self.edges.items():
            degrees[a] += w
            degrees[b] += w

        max_degree = max(degrees.values()) if degrees else 1
        return {n: d / max_degree for n, d in degrees.items()}

    def get_neighbors(self, node: int) -> List[Tuple[int, int]]:
        """獲取節點的鄰居及權重"""
        neighbors = []
        for (a, b), w in self.edges.items():
            if a == node:
                neighbors.append((b, w))
            elif b == node:
                neighbors.append((a, w))
        return sorted(neighbors, key=lambda x: -x[1])

    def pagerank(self, damping: float = 0.85, iterations: int = 100) -> Dict[int, float]:
        """計算 PageRank"""
        nodes = set()
        for (a, b) in self.edges:
            nodes.add(a)
            nodes.add(b)

        n = len(nodes)
        if n == 0:
            return {}

        nodes = list(nodes)
        node_idx = {n: i for i, n in enumerate(nodes)}

        # 初始化
        pr = {n: 1/n for n in nodes}

        # 建立鄰接列表
        adj = defaultdict(list)
        for (a, b), w in self.edges.items():
            adj[a].append((b, w))
            adj[b].append((a, w))

        # 迭代
        for _ in range(iterations):
            new_pr = {}
            for node in nodes:
                # 計算入邊貢獻
                rank = (1 - damping) / n
                for neighbor, weight in adj[node]:
                    out_sum = sum(w for _, w in adj[neighbor])
                    if out_sum > 0:
                        rank += damping * pr[neighbor] * weight / out_sum
                new_pr[node] = rank
            pr = new_pr

        return pr

    def find_communities(self, threshold: float = 0.3) -> List[Set[int]]:
        """簡單社區檢測（基於邊權重閾值）"""
        # 找出強連接的節點對
        max_weight = max(self.edges.values()) if self.edges else 1
        strong_edges = {
            (a, b) for (a, b), w in self.edges.items()
            if w / max_weight > threshold
        }

        # 使用 Union-Find 合併
        parent = {}

        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for (a, b) in strong_edges:
            union(a, b)

        # 收集社區
        communities = defaultdict(set)
        for (a, b) in strong_edges:
            communities[find(a)].add(a)
            communities[find(a)].add(b)

        return list(communities.values())


class GraphPredictor:
    """基於圖分析的預測器"""

    def __init__(self, max_num: int = 49, pick_count: int = 6):
        self.max_num = max_num
        self.pick_count = pick_count
        self.graph = CooccurrenceGraph(max_num)

    def predict(self, history: List[Dict], num_bets: int = 4) -> List[List[int]]:
        """
        使用多種圖分析方法生成預測

        策略：
        - Bet 1: 基於 PageRank 的高重要性號碼
        - Bet 2: 基於度中心性的高連接號碼
        - Bet 3: 基於社區檢測的群落組合
        - Bet 4+: 混合策略
        """
        self.graph.build_from_history(history, window=100)

        predictions = []

        # 方法 1: PageRank
        pr_pred = self._pagerank_predict()
        if pr_pred:
            predictions.append(pr_pred)

        # 方法 2: 度中心性
        dc_pred = self._degree_centrality_predict()
        if dc_pred and dc_pred not in predictions:
            predictions.append(dc_pred)

        # 方法 3: 社區組合
        comm_preds = self._community_predict(num_bets=2)
        for pred in comm_preds:
            if pred not in predictions:
                predictions.append(pred)

        # 方法 4: 混合 (PageRank + 隨機擴展)
        while len(predictions) < num_bets:
            mixed = self._mixed_predict(history)
            if mixed and mixed not in predictions:
                predictions.append(mixed)
            else:
                # 防止無限循環
                break

        return predictions[:num_bets]

    def _pagerank_predict(self) -> List[int]:
        """基於 PageRank 的預測"""
        pr = self.graph.pagerank()
        if not pr:
            return []

        # 選擇 PageRank 最高的號碼
        top_nodes = sorted(pr.items(), key=lambda x: -x[1])[:self.pick_count]
        return sorted([n for n, _ in top_nodes])

    def _degree_centrality_predict(self) -> List[int]:
        """基於度中心性的預測"""
        dc = self.graph.degree_centrality()
        if not dc:
            return []

        top_nodes = sorted(dc.items(), key=lambda x: -x[1])[:self.pick_count]
        return sorted([n for n, _ in top_nodes])

    def _community_predict(self, num_bets: int = 2) -> List[List[int]]:
        """基於社區的預測"""
        communities = self.graph.find_communities(threshold=0.2)
        if not communities:
            return []

        predictions = []

        # 從每個社區選擇代表性號碼
        for comm in sorted(communities, key=len, reverse=True)[:num_bets]:
            if len(comm) >= self.pick_count:
                # 社區足夠大，直接選
                pred = sorted(list(comm)[:self.pick_count])
            else:
                # 社區太小，補充鄰居
                pred = list(comm)
                for node in comm:
                    neighbors = self.graph.get_neighbors(node)
                    for n, _ in neighbors:
                        if n not in pred:
                            pred.append(n)
                        if len(pred) >= self.pick_count:
                            break
                    if len(pred) >= self.pick_count:
                        break

                # 仍不夠則隨機補充
                while len(pred) < self.pick_count:
                    for n in range(1, self.max_num + 1):
                        if n not in pred:
                            pred.append(n)
                            break

            predictions.append(sorted(pred[:self.pick_count]))

        return predictions

    def _mixed_predict(self, history: List[Dict]) -> List[int]:
        """混合預測"""
        pr = self.graph.pagerank()
        if not pr:
            return sorted(random.sample(range(1, self.max_num + 1), self.pick_count))

        # 選擇 top-20 作為候選池
        candidates = [n for n, _ in sorted(pr.items(), key=lambda x: -x[1])[:20]]

        # 加權隨機選擇
        weights = [pr.get(n, 0) for n in candidates]
        total = sum(weights)
        if total == 0:
            probs = [1/len(candidates)] * len(candidates)
        else:
            probs = [w/total for w in weights]

        try:
            selected = np.random.choice(
                candidates,
                size=min(self.pick_count, len(candidates)),
                replace=False,
                p=probs
            )
            return sorted(selected.tolist())
        except:
            return sorted(random.sample(candidates, min(self.pick_count, len(candidates))))


# ============================================================
# 便捷函數
# ============================================================

def graph_predict(history: List[Dict], rules: Dict, num_bets: int = 4) -> List[List[int]]:
    """便捷函數"""
    max_num = rules.get('maxNumber', 49)
    predictor = GraphPredictor(max_num=max_num)
    return predictor.predict(history, num_bets)


# ============================================================
# 測試
# ============================================================

if __name__ == '__main__':
    import sys
    import os
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

    from lottery_api.utils.benchmark_framework import quick_benchmark

    # 測試圖分析
    def graph_strategy(history, rules):
        return graph_predict(history, rules, num_bets=4)

    result = quick_benchmark(
        strategy_fn=graph_strategy,
        strategy_name='Graph_Analysis_4bet',
        lottery_type='BIG_LOTTO',
        num_bets=4
    )
