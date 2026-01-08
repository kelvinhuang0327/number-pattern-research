#!/usr/bin/env python3
"""
Transformer 注意力機制預測器
使用 Multi-Head Self-Attention 捕捉號碼之間的長距離依賴關係
"""
import sys
import os
import numpy as np
from collections import Counter
import math

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch 未安裝，Transformer 功能將無法使用")

class PositionalEncoding(nn.Module):
    """位置編碼層"""
    def __init__(self, d_model, max_len=5000):
        super(PositionalEncoding, self).__init__()
        
        # 創建位置編碼矩陣
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)
        
        self.register_buffer('pe', pe)
    
    def forward(self, x):
        # x shape: (batch, seq_len, d_model)
        return x + self.pe[:, :x.size(1), :]

class TransformerLotteryModel(nn.Module):
    """Transformer 威力彩預測模型"""
    def __init__(self, num_numbers=38, d_model=128, nhead=8, num_layers=4, dropout=0.1):
        super(TransformerLotteryModel, self).__init__()
        
        self.num_numbers = num_numbers
        self.d_model = d_model
        
        # 輸入嵌入層
        self.input_embedding = nn.Linear(num_numbers, d_model)
        
        # 位置編碼
        self.pos_encoder = PositionalEncoding(d_model)
        
        # Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # 輸出層
        self.fc1 = nn.Linear(d_model, d_model)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(dropout)
        self.fc2 = nn.Linear(d_model, num_numbers)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        # x shape: (batch, seq_len, num_numbers)
        
        # 嵌入
        x = self.input_embedding(x)  # (batch, seq_len, d_model)
        
        # 位置編碼
        x = self.pos_encoder(x)
        
        # Transformer 編碼
        x = self.transformer_encoder(x)  # (batch, seq_len, d_model)
        
        # 取最後一個時間步
        x = x[:, -1, :]  # (batch, d_model)
        
        # 輸出層
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.sigmoid(x)
        
        return x

class TransformerLotteryPredictor:
    """Transformer 預測器封裝"""
    
    def __init__(self, num_numbers=38, sequence_length=50, d_model=128, nhead=8, num_layers=4):
        self.num_numbers = num_numbers
        self.sequence_length = sequence_length
        
        if TORCH_AVAILABLE:
            self.model = TransformerLotteryModel(
                num_numbers=num_numbers,
                d_model=d_model,
                nhead=nhead,
                num_layers=num_layers
            )
            self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.0001, weight_decay=0.01)
            self.criterion = nn.BCELoss()
            self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
                self.optimizer, mode='min', factor=0.5, patience=5
            )
        else:
            self.model = None
    
    def prepare_data(self, history):
        """準備訓練數據"""
        X, y = [], []
        
        for i in range(len(history) - self.sequence_length):
            # 輸入序列
            sequence = []
            for j in range(i, i + self.sequence_length):
                one_hot = np.zeros(self.num_numbers)
                for num in history[j]['numbers']:
                    if 1 <= num <= self.num_numbers:
                        one_hot[num - 1] = 1
                sequence.append(one_hot)
            
            # 目標
            target = np.zeros(self.num_numbers)
            for num in history[i + self.sequence_length]['numbers']:
                if 1 <= num <= self.num_numbers:
                    target[num - 1] = 1
            
            X.append(sequence)
            y.append(target)
        
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)
    
    def train(self, history, epochs=100, batch_size=16, validation_split=0.2):
        """訓練 Transformer 模型"""
        if not TORCH_AVAILABLE:
            print("⚠️ PyTorch 未安裝，無法訓練")
            return
        
        X, y = self.prepare_data(history)
        
        if len(X) == 0:
            print("⚠️ 訓練數據不足")
            return
        
        # 分割訓練/驗證集
        split_idx = int(len(X) * (1 - validation_split))
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        print(f"📊 訓練數據: {len(X_train)} 樣本, 驗證數據: {len(X_val)} 樣本")
        
        X_train_tensor = torch.FloatTensor(X_train)
        y_train_tensor = torch.FloatTensor(y_train)
        X_val_tensor = torch.FloatTensor(X_val)
        y_val_tensor = torch.FloatTensor(y_val)
        
        best_val_loss = float('inf')
        patience_counter = 0
        max_patience = 10
        
        for epoch in range(epochs):
            # 訓練模式
            self.model.train()
            total_train_loss = 0
            num_batches = len(X_train) // batch_size
            
            for batch_idx in range(num_batches):
                start_idx = batch_idx * batch_size
                end_idx = start_idx + batch_size
                
                batch_X = X_train_tensor[start_idx:end_idx]
                batch_y = y_train_tensor[start_idx:end_idx]
                
                # Forward
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                
                # Backward
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                
                total_train_loss += loss.item()
            
            # 驗證模式
            self.model.eval()
            with torch.no_grad():
                val_outputs = self.model(X_val_tensor)
                val_loss = self.criterion(val_outputs, y_val_tensor).item()
            
            # 學習率調整
            self.scheduler.step(val_loss)
            
            # Early Stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
            
            if (epoch + 1) % 10 == 0:
                avg_train_loss = total_train_loss / num_batches if num_batches > 0 else 0
                print(f"Epoch [{epoch+1}/{epochs}], Train Loss: {avg_train_loss:.4f}, Val Loss: {val_loss:.4f}")
            
            if patience_counter >= max_patience:
                print(f"⏹️ Early stopping at epoch {epoch+1}")
                break
    
    def predict(self, history, lottery_rules):
        """預測下一期號碼"""
        if not TORCH_AVAILABLE or self.model is None:
            return self._statistical_fallback(history, lottery_rules)
        
        if len(history) < self.sequence_length:
            return self._statistical_fallback(history, lottery_rules)
        
        # 準備序列
        sequence = []
        for i in range(self.sequence_length):
            one_hot = np.zeros(self.num_numbers)
            for num in history[i]['numbers']:
                if 1 <= num <= self.num_numbers:
                    one_hot[num - 1] = 1
            sequence.append(one_hot)
        
        X = np.array([sequence], dtype=np.float32)
        X_tensor = torch.FloatTensor(X)
        
        # 預測
        self.model.eval()
        with torch.no_grad():
            probabilities = self.model(X_tensor)[0].numpy()
        
        # 選擇號碼
        pick_count = lottery_rules.get('pickCount', 6)
        top_indices = np.argsort(probabilities)[-pick_count:]
        numbers = sorted([int(idx + 1) for idx in top_indices])
        
        # 特別號
        special_counter = Counter()
        for draw in history[:30]:
            special_counter[draw.get('special', 1)] += 1
        special = special_counter.most_common(1)[0][0] if special_counter else 1
        
        avg_confidence = float(np.mean(probabilities[top_indices]))
        
        return {
            'numbers': numbers,
            'special': special,
            'confidence': avg_confidence,
            'method': 'transformer_predict',
            'probabilities': probabilities.tolist(),
            'attention_weights': None  # 可以提取注意力權重進行可視化
        }
    
    def _statistical_fallback(self, history, lottery_rules):
        """降級方案"""
        pick_count = lottery_rules.get('pickCount', 6)
        
        freq_counter = Counter()
        for draw in history[:100]:
            freq_counter.update(draw['numbers'])
        
        numbers = sorted([n for n, _ in freq_counter.most_common(pick_count)])
        
        special_counter = Counter()
        for draw in history[:30]:
            special_counter[draw.get('special', 1)] += 1
        special = special_counter.most_common(1)[0][0] if special_counter else 1
        
        return {
            'numbers': numbers,
            'special': special,
            'confidence': 0.5,
            'method': 'statistical_fallback'
        }

if __name__ == '__main__':
    from database import DatabaseManager
    from common import get_lottery_rules
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery-api', 'data', 'lottery_v2.db'))
    history = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')
    
    print("=" * 60)
    print("🤖 Transformer 威力彩預測模型")
    print("=" * 60)
    
    predictor = TransformerLotteryPredictor(
        num_numbers=38,
        sequence_length=30,
        d_model=128,
        nhead=8,
        num_layers=4
    )
    
    if TORCH_AVAILABLE and len(history) >= 50:
        print("\n🔧 開始訓練 Transformer 模型...")
        predictor.train(history, epochs=50, batch_size=8)
    
    print("\n🎯 生成預測...")
    result = predictor.predict(history, rules)
    
    print(f"\n預測號碼: {result['numbers']}")
    print(f"特別號: {result['special']}")
    print(f"信心度: {result['confidence']:.2%}")
    print(f"方法: {result['method']}")
