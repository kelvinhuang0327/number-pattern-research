#!/usr/bin/env python3
"""
大乐透号码关联图构建器 (Biglotto Graph Builder)
Phase 1: 图构建与特征工程
"""
import sys
import os
import numpy as np
import networkx as nx
from collections import Counter, defaultdict
from itertools import combinations

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

class BiglottoGraph:
    """
    大乐透号码关联图
    
    核心功能：
    1. 构建号码共现图（节点=号码，边=共现关系）
    2. 提取节点特征（频率、周期、冷热指标）
    3. 计算边权重（共现频率）
    """
    
    def __init__(self, min_num=1, max_num=49):
        self.min_num = min_num
        self.max_num = max_num
        self.graph = nx.Graph()
        
        # 初始化所有节点
        for num in range(min_num, max_num + 1):
            self.graph.add_node(num)
        
        # 特征存储
        self.node_features = {}
        self.edge_weights = {}
    
    def build_from_history(self, history, lookback=500):
        """
        从历史数据构建图
        
        Args:
            history: 历史开奖数据
            lookback: 使用最近多少期数据
        """
        print(f"🔨 构建号码关联图 (使用最近 {lookback} 期数据)")
        
        # 使用最近的数据
        recent_history = history[:min(lookback, len(history))]
        
        # 1. 统计号码频率
        number_freq = Counter()
        for draw in recent_history:
            number_freq.update(draw['numbers'])
        
        # 2. 统计号码对共现
        pair_freq = Counter()
        for draw in recent_history:
            numbers = draw['numbers']
            for pair in combinations(sorted(numbers), 2):
                pair_freq[pair] += 1
        
        # 3. 计算最后出现期数
        last_seen = {}
        for i, draw in enumerate(recent_history):
            for num in draw['numbers']:
                if num not in last_seen:
                    last_seen[num] = i
        
        # 4. 提取节点特征
        total_draws = len(recent_history)
        
        for num in range(self.min_num, self.max_num + 1):
            freq = number_freq.get(num, 0)
            freq_ratio = freq / total_draws if total_draws > 0 else 0
            recency = last_seen.get(num, total_draws)  # 距今多少期
            
            # 冷热指标（最近30期的出现次数）
            recent_30 = [d for d in recent_history[:30]]
            hot_score = sum(1 for d in recent_30 if num in d['numbers'])
            
            self.node_features[num] = {
                'frequency': freq,
                'frequency_ratio': freq_ratio,
                'recency': recency,
                'hot_score': hot_score,
                'is_hot': hot_score >= 5,  # 最近30期出现>=5次
                'is_cold': recency >= 15,   # 15期未出现
            }
        
        # 5. 添加边（只添加共现次数 >= 阈值的边）
        min_cooccur = max(2, total_draws * 0.01)  # 至少共现2次或1%
        
        for (num1, num2), count in pair_freq.items():
            if count >= min_cooccur:
                # 边权重 = 共现次数 / 总期数
                weight = count / total_draws
                self.graph.add_edge(num1, num2, weight=weight, count=count)
                self.edge_weights[(num1, num2)] = weight
        
        print(f"✅ 图构建完成")
        print(f"   节点数: {self.graph.number_of_nodes()}")
        print(f"   边数: {self.graph.number_of_edges()}")
        print(f"   平均度: {sum(dict(self.graph.degree()).values()) / self.graph.number_of_nodes():.2f}")
    
    def get_node_feature_matrix(self):
        """
        获取节点特征矩阵（用于 GNN）
        
        Returns:
            numpy array (N x F) where N=49, F=特征数
        """
        features = []
        
        for num in range(self.min_num, self.max_num + 1):
            feat = self.node_features.get(num, {})
            features.append([
                feat.get('frequency_ratio', 0),
                feat.get('recency', 0) / 100,  # 归一化
                feat.get('hot_score', 0) / 10,  # 归一化
                1.0 if feat.get('is_hot', False) else 0.0,
                1.0 if feat.get('is_cold', False) else 0.0,
            ])
        
        return np.array(features, dtype=np.float32)
    
    def get_adjacency_matrix(self):
        """
        获取邻接矩阵（用于 GNN）
        
        Returns:
            numpy array (N x N) 带权重的邻接矩阵
        """
        N = self.max_num - self.min_num + 1
        adj = np.zeros((N, N), dtype=np.float32)
        
        for (num1, num2), weight in self.edge_weights.items():
            i = num1 - self.min_num
            j = num2 - self.min_num
            adj[i, j] = weight
            adj[j, i] = weight  # 无向图
        
        return adj
    
    def get_top_connected_numbers(self, num, top_k=5):
        """获取与指定号码最相关的其他号码"""
        neighbors = []
        
        for neighbor in self.graph.neighbors(num):
            weight = self.graph[num][neighbor]['weight']
            neighbors.append((neighbor, weight))
        
        neighbors.sort(key=lambda x: -x[1])
        return neighbors[:top_k]
    
    def analyze_graph_properties(self):
        """分析图的属性"""
        print("\n" + "=" * 60)
        print("📊 图属性分析")
        print("=" * 60)
        
        # 度中心性
        degree_cent = nx.degree_centrality(self.graph)
        top_degree = sorted(degree_cent.items(), key=lambda x: -x[1])[:5]
        
        print(f"\n🔗 度中心性 Top 5 (最多连接的号码):")
        for num, cent in top_degree:
            degree = self.graph.degree(num)
            print(f"   {num:2d}: {cent:.3f} (连接 {degree} 个号码)")
        
        # 介数中心性
        betweenness = nx.betweenness_centrality(self.graph, weight='weight')
        top_between = sorted(betweenness.items(), key=lambda x: -x[1])[:5]
        
        print(f"\n🌉 介数中心性 Top 5 (最重要的桥梁号码):")
        for num, cent in top_between:
            print(f"   {num:2d}: {cent:.3f}")
        
        # 聚类系数
        clustering = nx.clustering(self.graph, weight='weight')
        avg_clustering = sum(clustering.values()) / len(clustering)
        
        print(f"\n🔺 平均聚类系数: {avg_clustering:.3f}")
        
        # 社群检测
        try:
            communities = list(nx.community.greedy_modularity_communities(self.graph))
            print(f"\n👥 社群数量: {len(communities)}")
            for i, comm in enumerate(communities[:3], 1):
                print(f"   社群 {i}: {sorted(list(comm))[:10]}...")
        except:
            print("\n👥 社群检测: 跳过（需要更多边）")
        
        return {
            'degree_centrality': degree_cent,
            'betweenness_centrality': betweenness,
            'clustering': clustering,
        }

def test_graph_builder():
    """测试图构建器"""
    from database import DatabaseManager
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = db.get_all_draws(lottery_type='BIG_LOTTO')
    
    print("=" * 60)
    print("🎰 大乐透号码关联图构建测试")
    print("=" * 60)
    print(f"历史数据: {len(history)} 期")
    
    # 构建图
    graph = BiglottoGraph()
    graph.build_from_history(history, lookback=500)
    
    # 分析图属性
    graph.analyze_graph_properties()
    
    # 测试节点特征
    print("\n" + "=" * 60)
    print("📋 节点特征示例")
    print("=" * 60)
    for num in [1, 13, 25, 37, 49]:
        feat = graph.node_features.get(num, {})
        print(f"\n号码 {num:2d}:")
        print(f"  频率: {feat.get('frequency', 0)} 次 ({feat.get('frequency_ratio', 0):.2%})")
        print(f"  最近出现: {feat.get('recency', 0)} 期前")
        print(f"  热度分数: {feat.get('hot_score', 0)}/30")
        print(f"  状态: {'🔥 热门' if feat.get('is_hot') else '❄️ 冷门' if feat.get('is_cold') else '⚖️ 正常'}")
        
        # 显示相关号码
        related = graph.get_top_connected_numbers(num, top_k=5)
        if related:
            print(f"  最相关号码: {[(n, f'{w:.2%}') for n, w in related]}")
    
    # 获取特征矩阵
    feature_matrix = graph.get_node_feature_matrix()
    adj_matrix = graph.get_adjacency_matrix()
    
    print("\n" + "=" * 60)
    print("✅ 图构建完成")
    print("=" * 60)
    print(f"特征矩阵: {feature_matrix.shape}")
    print(f"邻接矩阵: {adj_matrix.shape}")
    print(f"特征维度: {feature_matrix.shape[1]}")

if __name__ == '__main__':
    test_graph_builder()
