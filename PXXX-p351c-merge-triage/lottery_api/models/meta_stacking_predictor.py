import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import List, Dict, Tuple
import os
import logging

logger = logging.getLogger(__name__)

class MetaStackingNet(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 128):
        super(MetaStackingNet, self).__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.relu = nn.ReLU()
        self.dropout1 = nn.Dropout(0.2)
        self.fc2 = nn.Linear(hidden_size, hidden_size // 2)
        self.dropout2 = nn.Dropout(0.1)
        self.fc3 = nn.Linear(hidden_size // 2, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        out = self.fc1(x)
        out = self.relu(out)
        out = self.dropout1(out)
        out = self.fc2(out)
        out = self.relu(out)
        out = self.dropout2(out)
        out = self.fc3(out)
        return self.sigmoid(out)

class MetaStackingPredictor:
    def __init__(self, strategy_names: List[str], model_path: str = None):
        self.strategy_names = strategy_names
        self.regimes = ['ORDER', 'CHAOS', 'TRANSITION', 'GLOBAL']
        # Input: strategies + regime one-hot (4) + structural (Entropy, Volatility)
        self.input_size = len(strategy_names) + len(self.regimes) + 2
        self.model = MetaStackingNet(self.input_size)
        self.model_path = model_path
        
        if model_path and os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path))
                self.model.eval()
                logger.info(f"成功加載 Meta-Stacking 模型: {model_path}")
            except Exception as e:
                logger.error(f"加載 Meta-Stacking 模型失敗: {e}")

    def _prepare_features(self, strategy_scores: Dict[str, Dict[int, float]], 
                        structural_features: Dict[str, Dict[int, float]],
                        regime: str, max_num: int) -> torch.Tensor:
        """
        將預測結果與環境轉化為神經網路輸入
        structural_features: {'entropy': {1: 0.5, ...}, 'volatility': {1: 0.2, ...}}
        """
        features = []
        # Regime one-hot
        regime_vec = [0.0] * len(self.regimes)
        if regime in self.regimes:
            regime_vec[self.regimes.index(regime)] = 1.0
        else:
            regime_vec[self.regimes.index('GLOBAL')] = 1.0

        for n in range(1, max_num + 1):
            n_feature = []
            for s in self.strategy_names:
                # 獲取各策略對該號碼的分數
                s_scores = strategy_scores.get(s, {})
                n_feature.append(float(s_scores.get(n, 0.0)))
            
            # Add structural features
            n_feature.append(float(structural_features.get('entropy', {}).get(n, 0.0)))
            n_feature.append(float(structural_features.get('volatility', {}).get(n, 0.0)))
            
            n_feature.extend(regime_vec)
            features.append(n_feature)
            
        return torch.tensor(features, dtype=torch.float32)

    def predict_refined_scores(self, strategy_scores: Dict[str, Dict[int, float]], 
                             structural_features: Dict[str, Dict[int, float]],
                             regime: str, max_num: int) -> Dict[int, float]:
        """
        使用 Meta-Learner 優化最終得分
        """
        self.model.eval()
        with torch.no_grad():
            x = self._prepare_features(strategy_scores, structural_features, regime, max_num)
            refined_probs = self.model(x).squeeze().tolist()
            
        score_dict = {i+1: float(prob) for i, prob in enumerate(refined_probs)}
        return score_dict

    def train_model(self, train_data: List[Tuple[Dict[str, Dict[int, float]], Dict[str, Dict[int, float]], str, List[int], int]], epochs: int = 100):
        """
        訓練 Meta-Learner (含 Early Stopping 與 Dropout)
        train_data: [(strategy_scores, structural_features, regime, actual_numbers, max_num), ...]
        """
        # Split into train and validation
        split = int(len(train_data) * 0.8)
        train_set = train_data[:split]
        val_set = train_data[split:]

        self.model.train()
        criterion = nn.BCELoss()
        optimizer = optim.Adam(self.model.parameters(), lr=0.0005, weight_decay=1e-5)

        best_val_loss = float('inf')
        patience = 15
        patience_counter = 0

        for epoch in range(epochs):
            self.model.train()
            total_train_loss = 0
            for strategy_scores, structural_features, regime, actual_numbers, max_num in train_set:
                optimizer.zero_grad()
                
                x = self._prepare_features(strategy_scores, structural_features, regime, max_num)
                target = torch.zeros(max_num, 1)
                for n in actual_numbers:
                    if 1 <= n <= max_num:
                        target[n-1] = 1.0
                
                output = self.model(x)
                loss = criterion(output, target)
                loss.backward()
                optimizer.step()
                total_train_loss += loss.item()

            # Validation
            self.model.eval()
            total_val_loss = 0
            with torch.no_grad():
                for strategy_scores, structural_features, regime, actual_numbers, max_num in val_set:
                    x = self._prepare_features(strategy_scores, structural_features, regime, max_num)
                    target = torch.zeros(max_num, 1)
                    for n in actual_numbers:
                        if 1 <= n <= max_num:
                            target[n-1] = 1.0
                    output = self.model(x)
                    total_val_loss += criterion(output, target).item()
            
            avg_val_loss = total_val_loss / len(val_set) if val_set else 0
            
            if (epoch + 1) % 5 == 0:
                logger.info(f"Epoch {epoch+1}/{epochs} | Train Loss: {total_train_loss/len(train_set):.4f} | Val Loss: {avg_val_loss:.4f}")

            # Early stopping
            if avg_val_loss < best_val_loss:
                best_val_loss = avg_val_loss
                patience_counter = 0
                if self.model_path:
                    torch.save(self.model.state_dict(), self.model_path)
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    break
