#!/usr/bin/env python3
"""
GNN 预测模型 (Phase 2)
使用图注意力网络进行大乐透预测
"""
import sys
import os
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, GCNConv
from torch_geometric.data import Data

from models.biglotto_graph import BiglottoGraph

class GNNLotteryModel(nn.Module):
    """
    图神经网络彩票预测模型
    
    架构：
    - Layer 1: Graph Attention (8 heads, 64 hidden)
    - Layer 2: Graph Attention (8 heads, 32 hidden)
    - Layer 3: Graph Convolution (16 hidden)
    - Output: Linear (16 → 1) + Sigmoid
    """
    
    def __init__(self, num_features=5, hidden_dim1=64, hidden_dim2=32, hidden_dim3=16, heads=8, dropout=0.3):
        super(GNNLotteryModel, self).__init__()
        
        # Layer 1: GAT
        self.gat1 = GATConv(num_features, hidden_dim1, heads=heads, dropout=dropout)
        
        # Layer 2: GAT
        self.gat2 = GATConv(hidden_dim1 * heads, hidden_dim2, heads=heads, dropout=dropout)
        
        # Layer 3: GCN
        self.gcn = GCNConv(hidden_dim2 * heads, hidden_dim3)
        
        # Output layer
        self.fc = nn.Linear(hidden_dim3, 1)
        
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x, edge_index, edge_weight=None):
        """
        Forward pass
        
        Args:
            x: 节点特征 (N x F)
            edge_index: 边索引 (2 x E)
            edge_weight: 边权重 (E,)
        
        Returns:
            节点预测概率 (N x 1)
        """
        # Layer 1: GAT
        x = self.gat1(x, edge_index)
        x = F.elu(x)
        x = self.dropout(x)
        
        # Layer 2: GAT
        x = self.gat2(x, edge_index)
        x = F.elu(x)
        x = self.dropout(x)
        
        # Layer 3: GCN
        x = self.gcn(x, edge_index, edge_weight)
        x = F.elu(x)
        
        # Output
        x = self.fc(x)
        x = torch.sigmoid(x)
        
        return x

class GNNLotteryPredictor:
    """GNN 彩票预测器"""
    
    def __init__(self, device='cpu'):
        self.device = device
        self.model = None
        self.graph_builder = BiglottoGraph()
    
    def prepare_graph_data(self, history, lookback=500):
        """
        准备图数据
        
        Returns:
            torch_geometric.data.Data
        """
        # 构建图
        self.graph_builder.build_from_history(history, lookback=lookback)
        
        # 获取特征和邻接矩阵
        node_features = self.graph_builder.get_node_feature_matrix()
        adj_matrix = self.graph_builder.get_adjacency_matrix()
        
        # 转换为 edge_index 格式
        edge_index = []
        edge_weight = []
        
        for i in range(adj_matrix.shape[0]):
            for j in range(i + 1, adj_matrix.shape[1]):
                if adj_matrix[i, j] > 0:
                    edge_index.append([i, j])
                    edge_index.append([j, i])  # 无向图
                    edge_weight.append(adj_matrix[i, j])
                    edge_weight.append(adj_matrix[i, j])
        
        edge_index = torch.tensor(edge_index, dtype=torch.long).t().contiguous()
        edge_weight = torch.tensor(edge_weight, dtype=torch.float)
        node_features = torch.tensor(node_features, dtype=torch.float)
        
        data = Data(x=node_features, edge_index=edge_index, edge_attr=edge_weight)
        
        return data
    
    def train_model(self, history, epochs=100, lr=0.001):
        """
        训练 GNN 模型
        
        Args:
            history: 历史数据
            epochs: 训练轮数
            lr: 学习率
        """
        print("=" * 60)
        print("🎓 GNN 模型训练")
        print("=" * 60)
        
        # 准备数据
        data = self.prepare_graph_data(history)
        
        # 初始化模型
        num_features = data.x.shape[1]
        self.model = GNNLotteryModel(num_features=num_features)
        self.model = self.model.to(self.device)
        data = data.to(self.device)
        
        # 优化器
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr, weight_decay=5e-4)
        
        # 准备训练标签（使用滑动窗口）
        # TODO: 实作完整的训练循环
        
        print(f"\n✅ 模型初始化完成")
        print(f"   参数数量: {sum(p.numel() for p in self.model.parameters())}")
        print(f"   设备: {self.device}")
    
    def predict(self, history, lottery_rules):
        """
        使用 GNN 预测
        
        Returns:
            {
                'numbers': [...],
                'confidence': 0.xx,
                'method': 'gnn_predict'
            }
        """
        if self.model is None:
            print("⚠️ 模型未训练，使用图中心性方法")
            return self._graph_centrality_fallback(history, lottery_rules)
        
        # 准备图数据
        data = self.prepare_graph_data(history)
        data = data.to(self.device)
        
        # 预测
        self.model.eval()
        with torch.no_grad():
            probs = self.model(data.x, data.edge_index, data.edge_attr)
        
        # 选择概率最高的号码
        probs = probs.cpu().numpy().flatten()
        pick_count = lottery_rules.get('pickCount', 6)
        
        top_indices = np.argsort(probs)[-pick_count:]
        numbers = sorted([int(idx + 1) for idx in top_indices])
        
        avg_confidence = float(np.mean(probs[top_indices]))
        
        return {
            'numbers': numbers,
            'confidence': avg_confidence,
            'method': 'gnn_predict',
            'probabilities': probs.tolist()
        }
    
    def _graph_centrality_fallback(self, history, lottery_rules):
        """
        基于图中心性的降级方案（不需要训练）
        """
        # 构建图
        self.graph_builder.build_from_history(history, lookback=500)
        
        # 计算度中心性和介数中心性
        graph = self.graph_builder.graph
        degree_cent = nx.degree_centrality(graph)
        
        # 结合节点特征评分
        scores = {}
        for num in range(1, 50):
            feat = self.graph_builder.node_features.get(num, {})
            score = (
                degree_cent.get(num, 0) * 2.0 +  # 中心性权重
                feat.get('frequency_ratio', 0) * 1.5 +  # 频率权重
                (1.0 if feat.get('is_hot', False) else 0.0) * 0.5  # 热门加成
            )
            scores[num] = score
        
        # 选择分数最高的号码
        pick_count = lottery_rules.get('pickCount', 6)
        top_numbers = sorted(scores.items(), key=lambda x: -x[1])[:pick_count]
        numbers = sorted([n for n, _ in top_numbers])
        
        return {
            'numbers': numbers,
            'confidence': 0.6,
            'method': 'graph_centrality_fallback'
        }

if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    print("=" * 60)
    print("🧠 GNN 彩票预测器测试")
    print("=" * 60)
    print(f"历史数据: {len(history)} 期")
    
    # 检测设备
    if torch.backends.mps.is_available():
        device = 'mps'
        print(f"🍎 使用 Apple Silicon GPU (MPS)")
    elif torch.cuda.is_available():
        device = 'cuda'
        print(f"🎮 使用 NVIDIA GPU (CUDA)")
    else:
        device = 'cpu'
        print(f"💻 使用 CPU")
    
    predictor = GNNLotteryPredictor(device=device)
    
    # 训练模型（简化版）
    predictor.train_model(history, epochs=10)
    
    # 预测
    result = predictor.predict(history, rules)
    print(f"\n🎯 预测结果:")
    print(f"   号码: {result['numbers']}")
    print(f"   方法: {result['method']}")
    print(f"   信心度: {result['confidence']:.2%}")
