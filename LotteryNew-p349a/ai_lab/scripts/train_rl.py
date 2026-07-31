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
from scripts.train_hybrid import HybridLotteryDataset

class RLLotteryDataset(HybridLotteryDataset):
    """
    Subclass of HybridLotteryDataset that calculates rewards for each sample.
    """
    def __getitem__(self, idx):
        context_tensor, stats_tensor, target_label = super().__getitem__(idx)
        
        # Calculate 'Potential Reward' for this target
        # If the target draw is 'strong' (high match potential), we weight it more
        # This is a proxy for RL: Reward-Weighted Supervised Learning
        target_indices = (target_label == 1.0).nonzero(as_tuple=True)[0].tolist()
        
        # We don't know the future during training, but we know the target.
        # We want the model to learn FAVORABLE windows more intensely.
        # For simplicity, we assign a high weight to ALL historical wins.
        # In a real RL loop, we would sample, but here we 'Force Learn' from success.
        
        return context_tensor, stats_tensor, target_label

def train_rl():
    data_file = os.path.join(os.path.dirname(__file__), '../data/real_biglotto.json')
    model_path = os.path.join(os.path.dirname(__file__), '../ai_models/hybrid_best.pth')
    
    if not os.path.exists(data_file) or not os.path.exists(model_path):
        print("Required files missing.")
        return

    device = torch.device("cpu")
    
    dataset = RLLotteryDataset(data_file)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    model = HybridLotteryTransformer().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    
    optimizer = optim.Adam(model.parameters(), lr=0.0001, weight_decay=1e-5)
    
    # Custom RL Loss function
    def rl_match_loss(logits, targets):
        """
        Custom loss that penalizes misses more heavily on winning numbers.
        It's essentially 'Differentiable Match Count' maximization.
        """
        # Standard BCE
        bce = nn.BCEWithLogitsLoss(reduction='none')(logits, targets)
        
        # Boost weight for target numbers (the 6 winners)
        # Instead of 1.0, we weight the '1's much higher to focus on finding them
        weights = torch.ones_like(targets)
        weights[targets == 1.0] = 50.0 # Extreme focus on the 6 numbers
        
        weighted_loss = (bce * weights).mean()
        return weighted_loss

    epochs = 10
    print(f"Starting Phase 9: RL-Weighted Reward Optimization for {epochs} epochs...")
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for x, s, y in dataloader:
            x, s, y = x.to(device), s.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x, s)
            loss = rl_match_loss(logits, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        print(f"Epoch {epoch+1} | RL Loss: {total_loss / len(dataloader):.4f}")

    # Save Gen-3 Model
    save_path = os.path.join(os.path.dirname(__file__), '../ai_models/rl_gen3_best.pth')
    torch.save(model.state_dict(), save_path)
    print(f"Gen-3 RL Model saved to {save_path}")

if __name__ == "__main__":
    train_rl()
