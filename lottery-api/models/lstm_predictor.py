#!/usr/bin/env python3
"""
LSTM 時序預測模型 (LSTM Sequence Predictor)
使用深度學習預測威力彩號碼
"""
import sys
import os
import numpy as np
from collections import Counter

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️ PyTorch 未安裝，將使用統計方法替代")

class LSTMLotteryPredictor:
    """LSTM 威力彩預測模型"""
    
    def __init__(self, num_numbers=38, sequence_length=50, hidden_size=128):
        self.num_numbers = num_numbers
        self.sequence_length = sequence_length
        self.hidden_size = hidden_size
        
        if TORCH_AVAILABLE:
            self.model = self._build_model()
            self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
            self.criterion = nn.BCELoss()
        else:
            self.model = None
    
    def _build_model(self):
        """構建 LSTM 模型"""
        class LSTMModel(nn.Module):
            def __init__(self, input_size, hidden_size, output_size):
                super(LSTMModel, self).__init__()
                self.lstm1 = nn.LSTM(input_size, hidden_size, batch_first=True)
                self.lstm2 = nn.LSTM(hidden_size, hidden_size//2, batch_first=True)
                self.fc1 = nn.Linear(hidden_size//2, hidden_size)
                self.relu = nn.ReLU()
                self.dropout = nn.Dropout(0.3)
                self.fc2 = nn.Linear(hidden_size, output_size)
                self.sigmoid = nn.Sigmoid()
            
            def forward(self, x):
                # x shape: (batch, seq_len, input_size)
                out, _ = self.lstm1(x)
                out, _ = self.lstm2(out)
                out = out[:, -1, :]  # 取最後一個時間步
                out = self.fc1(out)
                out = self.relu(out)
                out = self.dropout(out)
                out = self.fc2(out)
                out = self.sigmoid(out)
                return out
        
        return LSTMModel(self.num_numbers, self.hidden_size, self.num_numbers)
    
    def prepare_data(self, history):
        """
        準備訓練數據
        
        Args:
            history: 歷史開獎記錄
        
        Returns:
            X: (num_samples, sequence_length, num_numbers)
            y: (num_samples, num_numbers)
        """
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
            
            # 目標（下一期）
            target = np.zeros(self.num_numbers)
            for num in history[i + self.sequence_length]['numbers']:
                if 1 <= num <= self.num_numbers:
                    target[num - 1] = 1
            
            X.append(sequence)
            y.append(target)
        
        return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)
    
    def train(self, history, epochs=50, batch_size=16):
        """訓練模型"""
        if not TORCH_AVAILABLE:
            print("⚠️ PyTorch 未安裝，跳過訓練")
            return
        
        X, y = self.prepare_data(history)
        
        if len(X) == 0:
            print("⚠️ 訓練數據不足")
            return
        
        print(f"📊 訓練數據: {len(X)} 樣本")
        
        # 轉換為 PyTorch tensors
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y)
        
        # 訓練循環
        self.model.train()
        for epoch in range(epochs):
            total_loss = 0
            num_batches = len(X) // batch_size
            
            for batch_idx in range(num_batches):
                start_idx = batch_idx * batch_size
                end_idx = start_idx + batch_size
                
                batch_X = X_tensor[start_idx:end_idx]
                batch_y = y_tensor[start_idx:end_idx]
                
                # Forward pass
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                
                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()
                
                total_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                avg_loss = total_loss / num_batches if num_batches > 0 else 0
                print(f"Epoch [{epoch+1}/{epochs}], Loss: {avg_loss:.4f}")
    
    def predict(self, history, lottery_rules):
        """
        預測下一期號碼
        
        Returns:
            {
                'numbers': [1, 5, 12, ...],
                'special': 3,
                'confidence': 0.65,
                'method': 'lstm_predict',
                'probabilities': [0.1, 0.05, ...]  # 各號碼的機率
            }
        """
        if not TORCH_AVAILABLE or self.model is None:
            # 降級為統計方法
            return self._statistical_fallback(history, lottery_rules)
        
        # 準備最近的序列
        if len(history) < self.sequence_length:
            return self._statistical_fallback(history, lottery_rules)
        
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
        
        # 選擇 top-k 號碼
        pick_count = lottery_rules.get('pickCount', 6)
        top_indices = np.argsort(probabilities)[-pick_count:]
        numbers = sorted([int(idx + 1) for idx in top_indices])
        
        # 預測特別號（簡單使用頻率）
        special_counter = Counter()
        for draw in history[:30]:
            special_counter[draw.get('special', 1)] += 1
        special = special_counter.most_common(1)[0][0] if special_counter else 1
        
        avg_confidence = float(np.mean(probabilities[top_indices]))
        
        return {
            'numbers': numbers,
            'special': special,
            'confidence': avg_confidence,
            'method': 'lstm_predict',
            'probabilities': probabilities.tolist()
        }
    
    def _statistical_fallback(self, history, lottery_rules):
        """統計方法降級方案"""
        pick_count = lottery_rules.get('pickCount', 6)
        
        # 使用頻率統計
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
    print("🤖 LSTM 威力彩預測模型")
    print("=" * 60)
    
    predictor = LSTMLotteryPredictor(num_numbers=38, sequence_length=30)
    
    if TORCH_AVAILABLE and len(history) >= 50:
        print("\n🔧 開始訓練模型...")
        predictor.train(history, epochs=20, batch_size=8)
    
    print("\n🎯 生成預測...")
    result = predictor.predict(history, rules)
    
    print(f"\n預測號碼: {result['numbers']}")
    print(f"特別號: {result['special']}")
    print(f"信心度: {result['confidence']:.2%}")
    print(f"方法: {result['method']}")
