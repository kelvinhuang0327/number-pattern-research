#!/usr/bin/env python3
"""
Attention LSTM 預測模型 (PyTorch 版本)
======================================
架構:
- Input: 滑動窗口 (過去 N 期的 One-Hot 編碼)
- Bidirectional LSTM + Attention 機制
- Output: 號碼機率分佈
"""
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# 設置設備
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')


class AttentionLayer(nn.Module):
    """自定義 Attention 層"""

    def __init__(self, hidden_size, bidirectional=True):
        super().__init__()
        self.bidirectional = bidirectional
        self.attention = nn.Linear(hidden_size * (2 if bidirectional else 1), 1)

    def forward(self, lstm_output):
        """
        Args:
            lstm_output: [batch, seq_len, hidden_size * num_directions]
        """
        # 計算注意力分數
        attention_weights = torch.tanh(self.attention(lstm_output))  # [batch, seq_len, 1]
        attention_weights = torch.softmax(attention_weights, dim=1)

        # 加權求和
        context = torch.sum(attention_weights * lstm_output, dim=1)  # [batch, hidden_size * num_directions]

        return context, attention_weights


class AttentionLSTM(nn.Module):
    """Attention LSTM 模型"""

    def __init__(self, input_size=38, hidden_size=64, num_layers=1,
                 dropout=0.3, output_size=38, bidirectional=True):
        super().__init__()

        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
            bidirectional=bidirectional
        )

        self.attention = AttentionLayer(hidden_size, bidirectional=bidirectional)

        self.dropout = nn.Dropout(dropout)

        self.fc = nn.Linear(hidden_size * (2 if bidirectional else 1), output_size)

        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        """
        Args:
            x: [batch, seq_len, input_size]
        """
        # LSTM
        lstm_out, _ = self.lstm(x)  # [batch, seq_len, hidden_size * num_directions]

        # Attention
        context, _ = self.attention(lstm_out)  # [batch, hidden_size * num_directions]

        # Dropout
        context = self.dropout(context)

        # Output
        output = self.fc(context)  # [batch, output_size]
        output = self.sigmoid(output)

        return output


class AttentionLSTMPredictor:
    """
    Attention LSTM 預測器 (PyTorch 版)
    """

    def __init__(self, num_balls=38, window_size=5, hidden_size=64,
                 dropout=0.3, num_layers=1, bidirectional=False):
        # ⚠️ bidirectional 默認為 False，因為 Bi-LSTM 已被驗證無效
        self.num_balls = num_balls
        self.window_size = window_size
        self.hidden_size = hidden_size
        self.dropout = dropout
        self.num_layers = num_layers
        self.bidirectional = bidirectional
        self.model = None
        self.is_trained = False

    def _one_hot_encode(self, numbers):
        """One-Hot 編碼"""
        one_hot = np.zeros(self.num_balls)
        for n in numbers:
            if 1 <= n <= self.num_balls:
                one_hot[n - 1] = 1
        return one_hot

    def _prepare_data(self, history):
        """準備訓練數據"""
        if len(history) < self.window_size + 1:
            return None, None

        # One-Hot 編碼
        encoded = []
        for draw in history:
            nums = [n for n in draw['numbers'] if n <= self.num_balls]
            encoded.append(self._one_hot_encode(nums))

        encoded = np.array(encoded, dtype=np.float32)

        # 滑動窗口
        X, y = [], []
        for i in range(len(encoded) - self.window_size):
            X.append(encoded[i:i + self.window_size])
            y.append(encoded[i + self.window_size])

        return np.array(X), np.array(y)

    def train(self, history, epochs=30, batch_size=16, lr=0.001, verbose=0):
        """訓練模型"""
        X, y = self._prepare_data(history)
        if X is None or len(X) == 0:
            return None

        # 轉換為 Tensor
        X_tensor = torch.tensor(X, dtype=torch.float32).to(DEVICE)
        y_tensor = torch.tensor(y, dtype=torch.float32).to(DEVICE)

        # 分割訓練/驗證
        split = int(0.8 * len(X_tensor))
        if split == 0: split = 1 # 確保至少有一個
        train_dataset = TensorDataset(X_tensor[:split], y_tensor[:split])
        
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        # 建立模型
        self.model = AttentionLSTM(
            input_size=self.num_balls,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            dropout=self.dropout,
            output_size=self.num_balls,
            bidirectional=self.bidirectional
        ).to(DEVICE)

        # 損失函數和優化器
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=lr, weight_decay=0.0001)

        # 訓練
        for epoch in range(epochs):
            self.model.train()
            train_loss = 0
            for X_batch, y_batch in train_loader:
                optimizer.zero_grad()
                outputs = self.model(X_batch)
                loss = criterion(outputs, y_batch)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            if verbose and (epoch + 1) % 10 == 0:
                print(f"Epoch {epoch+1}/{epochs} - Train Loss: {train_loss / len(train_loader):.4f}")

        self.is_trained = True
        return True

    def predict_proba(self, history):
        """預測機率分佈"""
        if not self.is_trained or self.model is None:
            return None

        recent = history[-self.window_size:]
        encoded = []
        for draw in recent:
            nums = [n for n in draw['numbers'] if n <= self.num_balls]
            encoded.append(self._one_hot_encode(nums))

        X = np.array([encoded], dtype=np.float32)
        X_tensor = torch.tensor(X).to(DEVICE)

        self.model.eval()
        with torch.no_grad():
            proba = self.model(X_tensor).cpu().numpy()[0]

        return proba

    def predict(self, history, n_numbers=6):
        """預測號碼"""
        proba = self.predict_proba(history)
        if proba is None:
            return []

        # Top-N
        indices = np.argsort(proba)[::-1][:n_numbers]
        numbers = sorted([int(i + 1) for i in indices])

        return numbers

def attention_lstm_predict(history, rules=None, n_numbers=6, **kwargs):
    """
    Attention LSTM 預測函數 (供回測框架使用)
    """
    train_window = kwargs.get('train_window', 100)
    window_size = kwargs.get('window_size', 5)

    train_data = history[-train_window:] if len(history) > train_window else history

    if len(train_data) < window_size + 5:
        from collections import Counter
        freq = Counter()
        for d in train_data:
            for n in d['numbers']:
                freq[n] += 1
        return {
            'numbers': [n for n, _ in freq.most_common(n_numbers)],
            'method': 'attention_lstm_fallback'
        }

    predictor = AttentionLSTMPredictor(
        num_balls=rules.get('maxNumber', 38) if rules else 38,
        window_size=window_size,
        hidden_size=64,
        dropout=0.3
    )

    predictor.train(train_data, epochs=30, verbose=0)
    numbers = predictor.predict(train_data, n_numbers=n_numbers)

    return {
        'numbers': numbers,
        'method': 'attention_lstm_torch_bi'
    }
