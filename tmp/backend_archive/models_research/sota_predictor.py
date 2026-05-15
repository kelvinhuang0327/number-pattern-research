import torch
import torch.nn as nn
import numpy as np
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class TransformerPredictor(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int, n_heads: int, n_layers: int, s1_dim: int, s2_dim: int):
        super(TransformerPredictor, self).__init__()
        self.embedding = nn.Linear(input_dim, hidden_dim)
        encoder_layers = nn.TransformerEncoderLayer(d_model=hidden_dim, nhead=n_heads, batch_first=True)
        self.transformer_encoder = nn.TransformerEncoder(encoder_layers, num_layers=n_layers)
        
        # 雙頭輸出：一區 (S1) 與 二區 (S2)
        self.fc_s1 = nn.Linear(hidden_dim, s1_dim)
        self.fc_s2 = nn.Linear(hidden_dim, s2_dim)
        self.dropout = nn.Dropout(0.1)

    def forward(self, x):
        # x shape: (batch, seq_len, input_dim)
        x = self.embedding(x)
        x = self.transformer_encoder(x)
        
        # 取最後一個序列位置的輸出 (代表最新隱藏狀態)
        x = x[:, -1, :]
        x = self.dropout(x)
        
        # 獨立預測兩區
        out_s1 = torch.sigmoid(self.fc_s1(x))
        out_s2 = torch.sigmoid(self.fc_s2(x))
        
        return out_s1, out_s2

class PatternAwareTransformerPredictor:
    """
    SOTA 預測器：基於 Transformer 的模式識別引擎
    """
    def __init__(self, lottery_rules: Dict):
        self.lottery_rules = lottery_rules
        self.min_num = lottery_rules.get('minNumber', 1)
        self.max_num = lottery_rules.get('maxNumber', 38)
        self.s1_range = self.max_num - self.min_num + 1
        self.s2_range = 8 # 威力彩固定為 8
        
        # 設置模型參數
        # 輸入維度包含了 一區號碼(38) + 二區號碼(8)
        self.input_dim = self.s1_range + self.s2_range
        self.hidden_dim = 128
        self.n_heads = 4
        self.n_layers = 3 # 增加深度以捕捉兩區獨立模式
        self.seq_len = 15 # 增加序列長度
        
        self.model = TransformerPredictor(
            input_dim=self.input_dim,
            hidden_dim=self.hidden_dim,
            n_heads=self.n_heads,
            n_layers=self.n_layers,
            s1_dim=self.s1_range,
            s2_dim=self.s2_range
        )
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

    def _prepare_data(self, history: List[Dict]):
        """將歷史數據轉換為 Multi-hot 序列 (包含一區與二區)"""
        data = []
        for draw in history:
            vec = np.zeros(self.input_dim)
            # 一區填充 (0~37)
            for num in draw.get('numbers', []):
                if self.min_num <= num <= self.max_num:
                    vec[num - self.min_num] = 1.0
            # 二區填充 (38~45)
            special = draw.get('special')
            if special:
                special_val = int(special)
                if 1 <= special_val <= 8:
                    vec[self.s1_range + special_val - 1] = 1.0
            data.append(vec)
        return np.array(data)

    def predict(self, history: List[Dict]) -> Dict:
        """
        執行 SOTA 預測
        """
        if len(history) < self.seq_len:
            return None # 數據量不足
            
        self.model.eval()
        data = self._prepare_data(history)
        
        # 取最近的一組序列
        seq = data[:self.seq_len][::-1].copy() # 轉為時間正序 (最新在後) 並複製以轉為正步長
        input_tensor = torch.FloatTensor(seq).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            out_s1, out_s2 = self.model(input_tensor)
            probs_s1 = out_s1.squeeze().cpu().numpy()
            probs_s2 = out_s2.squeeze().cpu().numpy()
            
        # 映射回號碼 - 一區
        s1_probs = {i + self.min_num: float(probs_s1[i]) for i in range(self.s1_range)}
        sorted_s1 = sorted(s1_probs.items(), key=lambda x: x[1], reverse=True)
        
        # 映射回號碼 - 二區
        s2_probs = {i + 1: float(probs_s2[i]) for i in range(self.s2_range)}
        sorted_s2 = sorted(s2_probs.items(), key=lambda x: x[1], reverse=True)
        
        pick_count = self.lottery_rules.get('pickCount', 6)
        predicted_numbers = sorted([num for num, _ in sorted_s1[:pick_count]])
        predicted_special = sorted_s2[0][0] # 取機率最高者
        
        return {
            'numbers': predicted_numbers,
            'special': predicted_special,
            'confidence': float(np.mean([p for _, p in sorted_s1[:pick_count]])),
            'method': 'SOTA Transformer (Dual-Head 增強版)',
            's1_probabilities': [p for _, p in sorted_s1[:pick_count]],
            's2_probabilities': [float(p) for _, p in sorted_s2[:3]]
        }

    def train_on_history(self, history: List[Dict], epochs: int = 5):
        """
        在歷史數據上快速在線微調模型
        """
        self.model.train()
        data = self._prepare_data(history)
        
        if len(data) < self.seq_len + 1:
            return
            
        optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
        criterion = nn.BCELoss()
        
        # 簡單的樣本生成
        X, y = [], []
        for i in range(len(data) - self.seq_len):
            X.append(data[i+1 : i+1+self.seq_len][::-1].copy()) # X 是序列，確保步長為正
            y.append(data[i]) # y 是目標
            
        X_tensor = torch.FloatTensor(np.array(X)).to(self.device)
        y_vec = np.array(y)
        y_s1_tensor = torch.FloatTensor(y_vec[:, :self.s1_range]).to(self.device)
        y_s2_tensor = torch.FloatTensor(y_vec[:, self.s1_range:]).to(self.device)
        
        logger.info(f"📊 SOTA Model Training on {len(X)} samples for {epochs} epochs...")
        
        for epoch in range(epochs):
            optimizer.zero_grad()
            out_s1, out_s2 = self.model(X_tensor)
            
            # 多任務損失 (MTL): 一區與二區共同優化
            loss_s1 = criterion(out_s1, y_s1_tensor)
            loss_s2 = criterion(out_s2, y_s2_tensor)
            total_loss = loss_s1 + 0.5 * loss_s2 # 二區權重稍輕，因為模式較單一
            
            total_loss.backward()
            optimizer.step()
            
        logger.info(f"✨ SOTA Model Training completed. Final Total Loss: {total_loss.item():.4f}")
