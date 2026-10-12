import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import List, Dict, Tuple
import os
import logging

logger = logging.getLogger(__name__)

class DiffusionDenoisingNet(nn.Module):
    def __init__(self, input_size: int = 6, hidden_size: int = 256):
        super(DiffusionDenoisingNet, self).__init__()
        # Time embedding (simple scalar embedding)
        self.time_mlp = nn.Sequential(
            nn.Linear(1, 32),
            nn.ReLU(),
            nn.Linear(32, 32)
        )
        
        # Main Denoiser
        self.net = nn.Sequential(
            nn.Linear(input_size + 32, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size // 2),
            nn.ReLU(),
            nn.Linear(hidden_size // 2, input_size)
        )

    def forward(self, x, t):
        # x: (batch, 6), t: (batch, 1)
        t_emb = self.time_mlp(t)
        x_input = torch.cat([x, t_emb], dim=-1)
        return self.net(x_input)

class LotteryDiffusionGenerator:
    def __init__(self, max_num: int = 38, model_path: str = None):
        self.max_num = max_num
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = DiffusionDenoisingNet().to(self.device)
        self.model_path = model_path
        
        # Diffusion parameters
        self.T = 1000
        self.betas = torch.linspace(1e-4, 0.02, self.T).to(self.device)
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = torch.cumprod(self.alphas, dim=0)
        
        if model_path and os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path, map_location=self.device))
                self.model.eval()
                logger.info(f"成功加載 Diffusion 模型: {model_path}")
            except Exception as e:
                logger.error(f"加載 Diffusion 模型失敗: {e}")

    def normalize(self, x):
        # 1-38 -> -1 to 1
        return 2.0 * (x - 1) / (self.max_num - 1) - 1.0

    def denormalize(self, x):
        # -1 to 1 -> 1-38
        return (x + 1.0) / 2.0 * (self.max_num - 1) + 1.0

    def sample(self, num_samples: int = 1) -> List[List[int]]:
        self.model.eval()
        with torch.no_grad():
            # Start from noise
            x = torch.randn(num_samples, 6).to(self.device)
            
            for t in reversed(range(self.T)):
                t_tensor = (torch.ones(num_samples, 1) * t).to(self.device)
                predicted_noise = self.model(x, t_tensor / self.T)
                
                alpha = self.alphas[t]
                alpha_cumprod = self.alphas_cumprod[t]
                beta = self.betas[t]
                
                if t > 0:
                    noise = torch.randn_like(x)
                else:
                    noise = 0
                
                # DDPM sampling step
                x = (1 / torch.sqrt(alpha)) * (x - (1 - alpha) / torch.sqrt(1 - alpha_cumprod) * predicted_noise) + torch.sqrt(beta) * noise
                
            # Denormalize and clean
            samples = self.denormalize(x).cpu().numpy()
            final_bets = []
            for s in samples:
                nums = np.round(s).astype(int)
                # Ensure uniqueness and range
                nums = np.clip(nums, 1, self.max_num)
                # If duplicates, increment
                unique_nums = sorted(list(set(nums)))
                while len(unique_nums) < 6:
                    for i in range(1, self.max_num + 1):
                        if i not in unique_nums:
                            unique_nums.append(i)
                            break
                    unique_nums = sorted(unique_nums)
                final_bets.append(unique_nums[:6])
                
        return final_bets

    def train_step(self, x_0):
        # x_0: (batch, 6)
        batch_size = x_0.shape[0]
        t = torch.randint(0, self.T, (batch_size, 1)).to(self.device)
        noise = torch.randn_like(x_0).to(self.device)
        
        alpha_cumprod = self.alphas_cumprod[t.squeeze()].reshape(-1, 1)
        # Forward diffusion
        x_t = torch.sqrt(alpha_cumprod) * x_0 + torch.sqrt(1 - alpha_cumprod) * noise
        
        # Predict noise
        predicted_noise = self.model(x_t, t.float() / self.T)
        
        return nn.MSELoss()(predicted_noise, noise)
