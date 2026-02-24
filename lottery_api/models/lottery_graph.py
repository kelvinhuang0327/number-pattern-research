#!/usr/bin/env python3
"""
通用號碼關聯圖構建器 (Lottery Graph Builder)
適用於 1-38 (威力彩) 或 1-49 (大樂透)
"""
import numpy as np
import networkx as nx
from collections import Counter, defaultdict
from itertools import combinations
import torch

class LotteryGraph:
    """
    通用號碼關聯圖
    核心功能：
    1. 構建號碼共現圖 (節點=號碼, 邊=共現關係)
    2. 提取節點特徵 (頻率、週期、冷熱指標)
    3. 計算邊權重 (共現頻率)
    """
    
    def __init__(self, min_num=1, max_num=38):
        self.min_num = min_num
        self.max_num = max_num
        self.num_nodes = max_num - min_num + 1
        self.graph = nx.Graph()
        
        # 初始化所有節點
        for num in range(min_num, max_num + 1):
            self.graph.add_node(num)
        
        self.node_features = {}
        self.edge_weights = {}
    
    def build_from_history(self, history, lookback=500):
        """從歷史數據構建圖"""
        self.graph.clear()
        self.node_features = {}
        self.edge_weights = {}
        
        for num in range(self.min_num, self.max_num + 1):
            self.graph.add_node(num)
            
        recent_history = history[-lookback:] if len(history) > lookback else history
        total_draws = len(recent_history)
        
        if total_draws == 0:
            return
            
        # 1. 統計號碼頻率
        number_freq = Counter()
        for draw in recent_history:
            number_freq.update(draw['numbers'])
        
        # 2. 統計號碼對共現
        pair_freq = Counter()
        for draw in recent_history:
            numbers = draw['numbers']
            for pair in combinations(sorted(numbers), 2):
                pair_freq[pair] += 1
        
        # 3. 統計最近出現
        last_seen = {}
        for i, draw in enumerate(reversed(recent_history)):
            for num in draw['numbers']:
                if num not in last_seen:
                    last_seen[num] = i
        
        # 4. 提取節點特徵
        for num in range(self.min_num, self.max_num + 1):
            freq = number_freq.get(num, 0)
            freq_ratio = freq / total_draws
            recency = last_seen.get(num, total_draws)
            
            recent_30 = recent_history[-30:] if len(recent_history) > 30 else recent_history
            hot_score = sum(1 for d in recent_30 if num in d.get('numbers', []))
            
            self.node_features[num] = {
                'frequency_ratio': freq_ratio,
                'recency': recency,
                'hot_score': hot_score,
                'is_hot': hot_score >= 5,
                'is_cold': recency >= 15,
            }
        
        # 5. 添加邊
        min_cooccur = max(2, total_draws * 0.01)
        for (num1, num2), count in pair_freq.items():
            if count >= min_cooccur:
                weight = count / total_draws
                self.graph.add_edge(num1, num2, weight=weight, count=count)
                self.edge_weights[(num1, num2)] = weight
    
    def get_pytorch_data(self):
        """獲取 PyTorch Geometric 所需的 Data 對象"""
        # Node Features (N, 5)
        x = []
        for num in range(self.min_num, self.max_num + 1):
            feat = self.node_features.get(num, {})
            x.append([
                feat.get('frequency_ratio', 0),
                min(1.0, feat.get('recency', 0) / 30.0),
                feat.get('hot_score', 0) / 10.0,
                1.0 if feat.get('is_hot', False) else 0.0,
                1.0 if feat.get('is_cold', False) else 0.0,
            ])
        x = torch.tensor(x, dtype=torch.float)
        
        # Edge Index (2, E)
        edge_index = []
        edge_attr = []
        for (u, v), w in self.edge_weights.items():
            # Convert ball numbers to 0-indexed indices
            u_idx, v_idx = u - self.min_num, v - self.min_num
            edge_index.append([u_idx, v_idx])
            edge_index.append([v_idx, u_idx])
            edge_attr.append([w])
            edge_attr.append([w])
            
        if not edge_index:
            # Fallback if no edges exist
            edge_index = torch.zeros((2, 0), dtype=torch.long)
            edge_attr = torch.zeros((0, 1), dtype=torch.float)
        else:
            edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
            edge_attr = torch.tensor(edge_attr, dtype=torch.float)
            
        return x, edge_index, edge_attr
