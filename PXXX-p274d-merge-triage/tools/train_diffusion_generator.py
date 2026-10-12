import os
import sys
import torch
import logging
from torch.utils.data import DataLoader, TensorDataset

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.diffusion_predictor import LotteryDiffusionGenerator
from lottery_api.database import DatabaseManager
from lottery_api.utils.backtest_safety import validate_chronological_order

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DiffusionTrainer')

def train_diffusion(periods: int = 1500):
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = validate_chronological_order(db.get_all_draws('POWER_LOTTO'))
    
    # Use more history for diffusion training to capture distributions
    history = all_draws[-periods:]
    
    model_dir = os.path.join(project_root, 'lottery_api', 'data', 'models')
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, 'diffusion_power.pth')
    
    generator = LotteryDiffusionGenerator(max_num=38, model_path=model_path)
    
    # Prepare training data
    train_data = []
    for draw in history:
        nums = sorted(draw['numbers'])
        if len(nums) == 6:
            # Normalize to -1 to 1
            norm_nums = generator.normalize(torch.tensor(nums, dtype=torch.float32))
            train_data.append(norm_nums)
            
    train_tensor = torch.stack(train_data)
    dataset = TensorDataset(train_tensor)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)
    
    optimizer = torch.optim.Adam(generator.model.parameters(), lr=1e-3)
    epochs = 200
    
    print(f"🚀 Training Diffusion Generator on {len(train_data)} samples for {epochs} epochs...")
    
    generator.model.train()
    for epoch in range(epochs):
        epoch_loss = 0
        for batch in dataloader:
            x_0 = batch[0].to(generator.device)
            optimizer.zero_grad()
            loss = generator.train_step(x_0)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
            
        if (epoch + 1) % 20 == 0:
            print(f"  Epoch {epoch+1}/{epochs} | Loss: {epoch_loss/len(dataloader):.6f}")
            
    # Save the model
    torch.save(generator.model.state_dict(), model_path)
    print(f"✅ Training Complete. Model saved to: {model_path}")

if __name__ == "__main__":
    # Use 1500 periods for a rich distribution
    train_diffusion(1500)
