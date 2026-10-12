#!/usr/bin/env python3
"""
Entropy Transformer 訓練腳本
PyTorch-based Training Script for Entropy-Driven Prediction Model

功能：
1. 從數據庫載入歷史開獎數據
2. 使用 12 維特徵提取器生成訓練數據
3. 多任務學習優化 3/4/5 中獎率
4. Early stopping 防止過擬合
5. 模型保存至 models/checkpoints/
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import argparse
import logging
from datetime import datetime
import numpy as np

from database import db_manager
from common import get_lottery_rules

# Check PyTorch availability
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("⚠️  PyTorch 不可用，請安裝: pip install torch")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LotteryDataset(Dataset):
    """彩票歷史數據集"""
    
    def __init__(self, history, feature_extractor, lookback=20):
        """
        Args:
            history: 歷史開獎數據列表
            feature_extractor: 特徵提取器實例
            lookback: 用於特徵提取的回看期數
        """
        self.samples = []
        self.labels = []
        self.lookback = lookback
        self.max_num = feature_extractor.max_num
        
        # 生成訓練樣本：用 t-lookback ~ t-1 期的數據預測第 t 期
        for i in range(lookback, len(history)):
            # 歷史窗口（按時間順序，從舊到新）
            window = history[i-lookback:i]
            
            # 提取特徵
            features = feature_extractor.extract_all_features(window)
            self.samples.append(features)
            
            # 標籤：第 t 期的號碼（multi-hot encoding）
            target_numbers = history[i]['numbers']
            label = np.zeros(self.max_num, dtype=np.float32)
            for num in target_numbers:
                if 1 <= num <= self.max_num:
                    label[num - 1] = 1.0
            self.labels.append(label)
        
        logger.info(f"✅ 生成 {len(self.samples)} 個訓練樣本")
    
    def __len__(self):
        return len(self.samples)
    
    def __getitem__(self, idx):
        return (
            torch.tensor(self.samples[idx], dtype=torch.float32),
            torch.tensor(self.labels[idx], dtype=torch.float32)
        )


class EntropyTransformer(nn.Module):
    """熵驅動 Transformer 模型"""
    
    def __init__(self, num_features=12, max_num=49, d_model=128, nhead=4, num_layers=2):
        super().__init__()
        
        self.max_num = max_num
        
        # 特徵嵌入
        self.embedding = nn.Linear(num_features, d_model)
        
        # Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=d_model * 4,
            dropout=0.1,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # 多任務輸出頭
        self.head_3match = nn.Linear(d_model, max_num)  # 優化 3 中
        self.head_4match = nn.Linear(d_model, max_num)  # 優化 4 中
        self.head_5match = nn.Linear(d_model, max_num)  # 優化 5 中
        
        # 融合層
        self.fusion = nn.Linear(max_num * 3, max_num)
        
    def forward(self, x):
        # x: [batch, num_features]
        x = self.embedding(x)  # [batch, d_model]
        x = x.unsqueeze(1)     # [batch, 1, d_model]
        x = self.transformer(x)
        x = x.squeeze(1)       # [batch, d_model]
        
        # 多任務預測
        out_3 = torch.sigmoid(self.head_3match(x))
        out_4 = torch.sigmoid(self.head_4match(x))
        out_5 = torch.sigmoid(self.head_5match(x))
        
        # 融合
        combined = torch.cat([out_3, out_4, out_5], dim=-1)
        output = torch.sigmoid(self.fusion(combined))
        
        return output, (out_3, out_4, out_5)


class EarlyStopping:
    """早停機制"""
    
    def __init__(self, patience=10, min_delta=0.001):
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_loss = None
        self.should_stop = False
        
    def __call__(self, val_loss):
        if self.best_loss is None:
            self.best_loss = val_loss
        elif val_loss > self.best_loss - self.min_delta:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        else:
            self.best_loss = val_loss
            self.counter = 0
        return self.should_stop


def train_model(lottery_type='BIG_LOTTO', epochs=100, batch_size=32, learning_rate=0.001):
    """訓練模型主函數"""
    
    if not TORCH_AVAILABLE:
        print("❌ PyTorch 不可用，無法訓練模型")
        return None
    
    print("=" * 80)
    print("🧠 熵驅動 Transformer 模型訓練")
    print("=" * 80)
    print()
    
    # 1. 載入數據
    print("📊 載入歷史數據...")
    all_draws = db_manager.get_all_draws(lottery_type)
    
    if not all_draws or len(all_draws) < 100:
        print(f"❌ 數據不足，需要至少 100 期數據（當前: {len(all_draws) if all_draws else 0}）")
        return None
    
    print(f"✅ 載入 {len(all_draws)} 期數據")
    
    lottery_rules = get_lottery_rules(lottery_type)
    max_num = lottery_rules.get('maxNumber', 49)
    
    # 2. 初始化特徵提取器
    print("🔧 初始化特徵提取器...")
    from models.entropy_transformer import InnovativeFeatureExtractor
    feature_extractor = InnovativeFeatureExtractor(max_num=max_num, recent_window=20)
    
    # 3. 準備數據集
    print("📦 準備訓練數據集...")
    
    # 訓練集：前 80%，驗證集：後 20%
    split_idx = int(len(all_draws) * 0.8)
    train_history = all_draws[:split_idx]
    val_history = all_draws[split_idx:]
    
    train_dataset = LotteryDataset(train_history, feature_extractor)
    val_dataset = LotteryDataset(val_history, feature_extractor)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    print(f"   訓練集: {len(train_dataset)} 樣本")
    print(f"   驗證集: {len(val_dataset)} 樣本")
    print()
    
    # 4. 初始化模型
    print("🏗️  初始化模型...")
    device = torch.device('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu')
    print(f"   使用設備: {device}")
    
    model = EntropyTransformer(num_features=12, max_num=max_num)
    model = model.to(device)
    
    # 5. 損失函數和優化器
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    early_stopping = EarlyStopping(patience=15)
    
    # 6. 訓練循環
    print()
    print("🚀 開始訓練...")
    print("-" * 80)
    
    best_val_loss = float('inf')
    checkpoint_dir = os.path.join(os.path.dirname(__file__), 'models', 'checkpoints')
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    for epoch in range(epochs):
        # 訓練階段
        model.train()
        train_loss = 0.0
        
        for features, labels in train_loader:
            features = features.to(device)
            labels = labels.to(device)
            
            optimizer.zero_grad()
            output, (out_3, out_4, out_5) = model(features)
            
            # 主損失 + 多任務損失
            main_loss = criterion(output, labels)
            aux_loss = (criterion(out_3, labels) + criterion(out_4, labels) + criterion(out_5, labels)) / 3
            loss = main_loss + 0.3 * aux_loss
            
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
        
        train_loss /= len(train_loader)
        
        # 驗證階段
        model.eval()
        val_loss = 0.0
        
        with torch.no_grad():
            for features, labels in val_loader:
                features = features.to(device)
                labels = labels.to(device)
                
                output, _ = model(features)
                loss = criterion(output, labels)
                val_loss += loss.item()
        
        val_loss /= len(val_loader)
        
        # 學習率調度
        scheduler.step(val_loss)
        
        # 打印進度
        if (epoch + 1) % 10 == 0 or epoch == 0:
            lr = optimizer.param_groups[0]['lr']
            print(f"Epoch {epoch+1:3d}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | LR: {lr:.6f}")
        
        # 保存最佳模型
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            checkpoint_path = os.path.join(checkpoint_dir, f'entropy_transformer_{lottery_type}.pt')
            torch.save({
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'val_loss': val_loss,
                'lottery_type': lottery_type,
                'max_num': max_num
            }, checkpoint_path)
        
        # 早停檢查
        if early_stopping(val_loss):
            print(f"\n⏹️  早停觸發於 Epoch {epoch+1}")
            break
    
    print("-" * 80)
    print()
    
    # 7. 訓練完成
    print("=" * 80)
    print("✅ 訓練完成!")
    print("=" * 80)
    print()
    print(f"📁 模型已保存至: {checkpoint_path}")
    print(f"📉 最佳驗證損失: {best_val_loss:.4f}")
    print()
    
    return model


def load_trained_model(lottery_type='BIG_LOTTO'):
    """載入已訓練的模型"""
    
    if not TORCH_AVAILABLE:
        return None
    
    checkpoint_dir = os.path.join(os.path.dirname(__file__), 'models', 'checkpoints')
    checkpoint_path = os.path.join(checkpoint_dir, f'entropy_transformer_{lottery_type}.pt')
    
    if not os.path.exists(checkpoint_path):
        logger.warning(f"找不到模型檢查點: {checkpoint_path}")
        return None
    
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    max_num = checkpoint.get('max_num', 49)
    
    model = EntropyTransformer(num_features=12, max_num=max_num)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()
    
    logger.info(f"✅ 載入模型: epoch={checkpoint['epoch']}, val_loss={checkpoint['val_loss']:.4f}")
    
    return model


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='訓練熵驅動 Transformer 模型')
    parser.add_argument('--lottery', default='BIG_LOTTO', help='彩票類型')
    parser.add_argument('--epochs', type=int, default=100, help='訓練輪數')
    parser.add_argument('--batch-size', type=int, default=32, help='批次大小')
    parser.add_argument('--lr', type=float, default=0.001, help='學習率')
    
    args = parser.parse_args()
    
    train_model(
        lottery_type=args.lottery,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr
    )
