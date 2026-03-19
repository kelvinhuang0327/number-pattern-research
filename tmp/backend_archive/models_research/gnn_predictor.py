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
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, GCNConv
from torch_geometric.data import Data

from models.lottery_graph import LotteryGraph

class GNNLotteryModel(nn.Module):
    """
    圖神經網路預測模型
    架構：GAT (注意號碼間關聯) + GCN (全局特徵傳播)
    """
    def __init__(self, num_features=5, hidden_dim1=64, hidden_dim2=32, hidden_dim3=16, heads=8, dropout=0.3):
        super(GNNLotteryModel, self).__init__()
        self.gat1 = GATConv(num_features, hidden_dim1, heads=heads, dropout=dropout)
        self.gat2 = GATConv(hidden_dim1 * heads, hidden_dim2, heads=heads, dropout=dropout)
        self.gcn = GCNConv(hidden_dim2 * heads, hidden_dim3)
        self.fc = nn.Linear(hidden_dim3, 1)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x, edge_index, edge_weight=None):
        x = F.elu(self.gat1(x, edge_index))
        x = self.dropout(x)
        x = F.elu(self.gat2(x, edge_index))
        x = self.dropout(x)
        x = F.elu(self.gcn(x, edge_index, edge_weight))
        x = torch.sigmoid(self.fc(x))
        return x

class GNNLotteryPredictor:
    """GNN 號碼預測器"""
    def __init__(self, device=None):
        if device is None:
            if torch.backends.mps.is_available():
                self.device = torch.device('mps')
            elif torch.cuda.is_available():
                self.device = torch.device('cuda')
            else:
                self.device = torch.device('cpu')
        else:
            self.device = torch.device(device)
            
        self.model = None
        self.graph_builder = None
        self.num_features = 5
    
    def _init_builder(self, lottery_rules):
        min_num = lottery_rules.get('minNumber', 1)
        max_num = lottery_rules.get('maxNumber', 38)
        if self.graph_builder is None or self.graph_builder.max_num != max_num:
            self.graph_builder = LotteryGraph(min_num=min_num, max_num=max_num)
            
    def prepare_data(self, history, lottery_rules, lookback=500):
        self._init_builder(lottery_rules)
        self.graph_builder.build_from_history(history, lookback=lookback)
        x, edge_index, edge_attr = self.graph_builder.get_pytorch_data()
        return x.to(self.device), edge_index.to(self.device), edge_attr.to(self.device)

    def train_model(self, history, lottery_rules, epochs=50, lr=0.005):
        print(f"🎓 GNN 訓練開始 (Device: {self.device})")
        x, edge_index, edge_attr = self.prepare_data(history, lottery_rules)
        
        if self.model is None:
            self.model = GNNLotteryModel(num_features=self.num_features).to(self.device)
            
        self.model.train()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.BCELoss()
        
        # 標籤：最新一期的號碼 (用於訓練收斂測試)
        target = torch.zeros(self.graph_builder.num_nodes, 1).to(self.device)
        latest_nums = history[-1]['numbers'] # history 預期為 ASC
        for n in latest_nums:
            idx = n - self.graph_builder.min_num
            if 0 <= idx < self.graph_builder.num_nodes:
                target[idx] = 1.0
                
        for epoch in range(epochs):
            optimizer.zero_grad()
            out = self.model(x, edge_index, edge_attr)
            loss = criterion(out, target)
            loss.backward()
            optimizer.step()
            if (epoch + 1) % 10 == 0:
                print(f"   Epoch {epoch+1:3d} | Loss: {loss.item():.6f}")
                
        self.save_model()

    def save_model(self, path=None):
        if path is None:
            path = os.path.join(project_root, 'ai_lab', 'gnn_model.pth')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save(self.model.state_dict(), path)

    def load_model(self, path=None):
        if path is None:
            path = os.path.join(project_root, 'ai_lab', 'gnn_model.pth')
        if not os.path.exists(path): return False
        if self.model is None:
            self.model = GNNLotteryModel(num_features=self.num_features).to(self.device)
        self.model.load_state_dict(torch.load(path, map_location=self.device))
        self.model.eval()
        return True

    def predict(self, history, lottery_rules):
        if not self.load_model():
            print("⚠️ 模型未訓練，執行首次訓練...")
            self.train_model(history, lottery_rules)
            
        x, edge_index, edge_attr = self.prepare_data(history, lottery_rules)
        self.model.eval()
        with torch.no_grad():
            probs = self.model(x, edge_index, edge_attr).cpu().numpy().flatten()
            
        pick_count = lottery_rules.get('pickCount', 6)
        top_indices = np.argsort(probs)[-pick_count:]
        numbers = sorted([int(idx + self.graph_builder.min_num) for idx in top_indices])
        
        return {
            'numbers': numbers,
            'confidence': float(np.mean(probs[top_indices])),
            'method': 'gnn_predict',
            'probabilities': probs.tolist()
        }

def gnn_predict(history, rules, **kwargs):
    predictor = GNNLotteryPredictor()
    return predictor.predict(history, rules)
