import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import json
import os
import sys
from typing import List

# Add parent dir to path to import models
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from ai_models.transformer_v1 import LotteryTransformer
from scripts.train_transformer import LotteryDataset

def finetune():
    # 1. Configuration
    data_file = os.path.join(os.path.dirname(__file__), '../data/real_biglotto.json')
    pretrained_path = os.path.join(os.path.dirname(__file__), '../models/pretrained_v1.pth')
    
    if not os.path.exists(data_file):
        print(f"Error: Data file {data_file} not found. Run export_data.py first.")
        return
    if not os.path.exists(pretrained_path):
        print(f"Error: Pretrained model {pretrained_path} not found. Run train_transformer.py first.")
        return

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    # 2. Data Loading
    # Use a longer sequence length for real data to capture more context
    dataset = LotteryDataset(data_file, seq_len=15)
    # Split: Latest 150 draws for evaluation, others for training
    train_size = len(dataset) - 150
    train_dataset, val_dataset = torch.utils.data.dataset.random_split(dataset, [train_size, 150])
    
    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

    # 3. Model Initialization (Load Pretrained Weights)
    model = LotteryTransformer().to(device)
    model.load_state_dict(torch.load(pretrained_path, map_location=device))
    print(f"Loaded pretrained weights from {pretrained_path}")

    # 4. Fine-tuning Setup
    # Lower learning rate for fine-tuning
    optimizer = optim.Adam(model.parameters(), lr=0.0001)
    criterion = nn.BCEWithLogitsLoss()

    # 5. Fine-tuning Loop
    epochs = 10
    print(f"Starting fine-tuning on {train_size} real sequences for {epochs} epochs...")
    
    best_val_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0
        for context, target in train_loader:
            context, target = context.to(device), target.to(device)
            optimizer.zero_grad()
            logits = model(context)
            loss = criterion(logits, target)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            
        # Validation
        model.eval()
        val_loss = 0
        with torch.no_grad():
            for context, target in val_loader:
                context, target = context.to(device), target.to(device)
                logits = model(context)
                loss = criterion(logits, target)
                val_loss += loss.item()
        
        avg_train_loss = train_loss / len(train_loader)
        avg_val_loss = val_loss / len(val_loader)
        print(f"Epoch {epoch+1}/{epochs} | Train Loss: {avg_train_loss:.4f} | Val Loss: {avg_val_loss:.4f}")
        
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            # Save the best model
            best_path = os.path.join(os.path.dirname(__file__), '../models/finetuned_best.pth')
            torch.save(model.state_dict(), best_path)

    print(f"Fine-tuning complete. Best model saved to {best_path}")

if __name__ == "__main__":
    finetune()
