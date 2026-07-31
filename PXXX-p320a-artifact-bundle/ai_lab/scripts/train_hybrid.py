import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import json
import os
import sys
import numpy as np
from typing import List, Tuple

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from ai_models.transformer_v2 import HybridLotteryTransformer

class HybridLotteryDataset(Dataset):
    """
    Dataset for hybrid lottery sequences.
    Extracts statistical features on the fly.
    """
    def __init__(self, data_path: str, seq_len: int = 15):
        with open(data_path, 'r') as f:
            self.draws = json.load(f)
        self.seq_len = seq_len
        self.max_num = 49
        
    def _extract_stats(self, draw: List[int], prev_draw: List[int] = None) -> List[float]:
        # 1-3: Zonal Counts
        z1, z2 = self.max_num // 3, 2 * (self.max_num // 3)
        low = sum(1 for n in draw if 1 <= n <= z1)
        mid = sum(1 for n in draw if z1 < n <= z2)
        high = sum(1 for n in draw if z2 < n <= self.max_num)
        
        # 4: Odd Count
        odd = sum(1 for n in draw if n % 2 != 0)
        
        # 5-6: Mean & Std (Normalized)
        mean_val = np.mean(draw) / self.max_num
        std_val = np.std(draw) / self.max_num
        
        # 7: Repeat Count (compared to prev draw)
        repeats = 0
        if prev_draw:
            repeats = len(set(draw) & set(prev_draw))
            
        return [float(low)/6, float(mid)/6, float(high)/6, float(odd)/6, mean_val, std_val, float(repeats)/6]

    def __len__(self):
        return len(self.draws) - self.seq_len
        
    def __getitem__(self, idx):
        # Slice context draws
        context_draws = self.draws[idx : idx + self.seq_len]
        
        # Extract features for each context draw
        stats = []
        for i in range(len(context_draws)):
            prev = self.draws[idx + i - 1] if (idx + i) > 0 else None
            stats.append(self._extract_stats(context_draws[i], prev))
            
        # Target: The next draw's numbers (multi-label)
        target_draw = self.draws[idx + self.seq_len]
        target = torch.zeros(50)
        for num in target_draw:
            if num < 50:
                target[num] = 1.0
                
        return torch.tensor(context_draws, dtype=torch.long), torch.tensor(stats, dtype=torch.float), target

def train():
    data_file = os.path.join(os.path.dirname(__file__), '../data/real_biglotto.json')
    if not os.path.exists(data_file):
        print("Data file not found.")
        return

    device = torch.device("cpu") # Use CPU for stability in this env
    
    dataset = HybridLotteryDataset(data_file)
    train_size = int(0.9 * len(dataset))
    val_size = len(dataset) - train_size
    train_ds, val_ds = torch.utils.data.random_split(dataset, [train_size, val_size])
    
    train_loader = DataLoader(train_ds, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=32, shuffle=False)

    model = HybridLotteryTransformer().to(device)
    # L2 Regularization (weight_decay) added to Adam
    optimizer = optim.Adam(model.parameters(), lr=0.0005, weight_decay=1e-5)
    
    # Learning Rate Scheduler
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=2)
    
    criterion = nn.BCEWithLogitsLoss()

    epochs = 20
    print(f"Fine-tuning Hybrid Transformer (v2) with Stability Strengthening for {epochs} epochs...")
    
    best_loss = float('inf')
    for epoch in range(epochs):
        model.train()
        t_loss = 0
        for x, s, y in train_loader:
            x, s, y = x.to(device), s.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x, s)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            t_loss += loss.item()
            
        model.eval()
        v_loss = 0
        with torch.no_grad():
            for x, s, y in val_loader:
                logits = model(x.to(device), s.to(device))
                v_loss += criterion(logits, y.to(device)).item()
        
        avg_t = t_loss / len(train_loader)
        avg_v = v_loss / len(val_loader)
        print(f"Epoch {epoch+1} | Train: {avg_t:.4f} | Val: {avg_v:.4f} | LR: {optimizer.param_groups[0]['lr']:.6f}")
        
        # Step the scheduler
        scheduler.step(avg_v)
        
        if avg_v < best_loss:
            best_loss = avg_v
            torch.save(model.state_dict(), os.path.join(os.path.dirname(__file__), '../ai_models/hybrid_best.pth'))

    print(f"Training Complete. Best Hybrid model saved.")

if __name__ == "__main__":
    train()
