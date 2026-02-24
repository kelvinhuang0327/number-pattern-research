import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import json
import os
import sys
import numpy as np
from typing import List, Tuple
from torch.optim.swa_utils import AveragedModel, SWALR

# Add paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from ai_models.transformer_v2 import HybridLotteryTransformer

class HybridV3Dataset(Dataset):
    """
    Enhanced Dataset for Hybrid v3 features.
    9-Channel feature vector: 
    [Low, Mid, High, Odd, Mean, Std, Repeats, Entropy, Velocity]
    """
    def __init__(self, data_path: str, seq_len: int = 15):
        with open(data_path, 'r') as f:
            self.draws = json.load(f)
        self.seq_len = seq_len
        self.max_num = 49
        
    def _extract_v3_stats(self, draw: List[int], prev_draw: List[int] = None) -> List[float]:
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
        
        # 7: Repeat Count
        repeats = len(set(draw) & set(prev_draw)) if prev_draw else 0
        
        # 8: Zonal Entropy (Cross 7 zones)
        zone_counts = [0] * 7
        for n in draw:
            z_idx = min((n - 1) // 7, 6)
            zone_counts[z_idx] += 1
        probs = [c/6 for c in zone_counts if c > 0]
        entropy = -sum(p * np.log(p) for p in probs) / np.log(6) if probs else 0
        
        # 9: Velocity (Change in mean)
        velocity = 0
        if prev_draw:
            velocity = (np.mean(draw) - np.mean(prev_draw)) / self.max_num
            
        return [float(low)/6, float(mid)/6, float(high)/6, float(odd)/6, mean_val, std_val, float(repeats)/6, float(entropy), float(velocity)]

    def __len__(self):
        return len(self.draws) - self.seq_len
        
    def __getitem__(self, idx):
        context_draws = self.draws[idx : idx + self.seq_len]
        stats = []
        for i in range(len(context_draws)):
            prev = self.draws[idx + i - 1] if (idx + i) > 0 else None
            stats.append(self._extract_v3_stats(context_draws[i], prev))
            
        target_draw = self.draws[idx + self.seq_len]
        target = torch.zeros(50)
        for num in target_draw:
            if num < 50: target[num] = 1.0
                
        return torch.tensor(context_draws, dtype=torch.long), torch.tensor(stats, dtype=torch.float), target

def train_v3():
    data_file = os.path.join(os.path.dirname(__file__), '../data/real_biglotto.json')
    device = torch.device("cpu")
    
    # Proper Chronological Split for Phase 10
    full_dataset = HybridV3Dataset(data_file)
    # Reserve last 200 for benchmark, use others for training
    train_size = len(full_dataset) - 200
    train_dataset = torch.utils.data.Subset(full_dataset, range(train_size))
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)

    model = HybridLotteryTransformer().to(device)
    # Load previous best RL weights as baseline if available
    rl_path = os.path.join(os.path.dirname(__file__), '../ai_models/rl_gen3_best.pth')
    if os.path.exists(rl_path):
        # Need to handle stat_dim change... actually v2 weights won't load directly 
        # because stat_projector input changed from 7 to 9. 
        # We start fresh or partial load. Let's start fresh for V3 architecture.
        print("Starting V3 Fresh Training (New Architecture)")
    
    optimizer = optim.Adam(model.parameters(), lr=0.0005, weight_decay=1e-4)
    criterion = nn.BCEWithLogitsLoss(reduction='none')
    
    # 1. SWA Setup
    swa_model = AveragedModel(model)
    swa_start = 10
    swa_scheduler = SWALR(optimizer, swa_lr=0.0001)

    epochs = 30
    print(f"Training U-HPE V3 (Entropy + SWA) with 200-period out-of-sample split for {epochs} epochs...")
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for x, s, y in train_loader:
            x, s, y = x.to(device), s.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x, s)
            
            # RL-Weighted Loss
            bce = criterion(logits, y)
            weights = torch.ones_like(y)
            weights[y == 1.0] = 75.0 # Even stronger reward for winners
            loss = (bce * weights).mean()
            
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        
        if epoch >= swa_start:
            swa_model.update_parameters(model)
            swa_scheduler.step()
            
        print(f"Epoch {epoch+1} | Loss: {total_loss / len(train_loader):.4f}")

    # Finalize SWA
    torch.optim.swa_utils.update_bn(train_loader, swa_model) # Not needed for Transformer but good practice
    
    save_path = os.path.join(os.path.dirname(__file__), '../ai_models/v3_deep_resonance.pth')
    torch.save(swa_model.module.state_dict(), save_path)
    print(f"U-HPE V3 Model saved to {save_path}")

if __name__ == "__main__":
    train_v3()
