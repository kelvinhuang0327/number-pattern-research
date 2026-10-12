
import os
import sys
import torch
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
from lotto_gpt import LottoGPTLite

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

class LotteryDataset(Dataset):
    def __init__(self, history, block_size):
        self.data = []
        for draw in history:
            # 將每期 6 個號碼排序後加入序列
            nums = sorted(draw['numbers'])
            self.data.extend(nums)
            
        self.block_size = block_size
        self.vocab_size = 50 # 1-49
        
    def __len__(self):
        return len(self.data) - self.block_size

    def __getitem__(self, idx):
        chunk = self.data[idx:idx + self.block_size + 1]
        x = torch.tensor(chunk[:-1], dtype=torch.long)
        y = torch.tensor(chunk[1:], dtype=torch.long)
        return x, y

def train():
    # 準備數據
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path=db_path)
    history = db.get_all_draws('BIG_LOTTO')
    
    # 超參數
    BLOCK_SIZE = 12 # 以前 2 期 (12號碼) 預測下一個
    BATCH_SIZE = 32
    EPOCHS = 50
    LEARNING_RATE = 3e-4
    
    dataset = LotteryDataset(history, BLOCK_SIZE)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    
    device = 'cpu' # M1/M2 可以試試 'mps'，但數據量小 CPU 足矣
    model = LottoGPTLite(vocab_size=50, block_size=BLOCK_SIZE).to(device)
    optimizer = optim.AdamW(model.parameters(), lr=LEARNING_RATE)
    
    print(f"🚀 開始訓練 LottoGPT-Lite (Epochs={EPOCHS})...")
    
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        for x, y in loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits, loss = model(x, y)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            
        if (epoch+1) % 10 == 0:
            print(f"Epoch {epoch+1}/{EPOCHS}, Loss: {total_loss/len(loader):.4f}")
            
    print("✅ 訓練完成，模型已保存為 'ai_lab/lotto_gpt.pth'")
    torch.save(model.state_dict(), os.path.join(project_root, 'ai_lab', 'lotto_gpt.pth'))
    
    # 簡單預測演示
    model.eval()
    last_draw = sorted(history[0]['numbers'] + history[1]['numbers']) # 最近2期
    context = torch.tensor(last_draw[-BLOCK_SIZE:], dtype=torch.long).unsqueeze(0).to(device)
    
    print("\n🔮 生成下期預測序列 (AI 實驗):")
    generated = model.generate(context, max_new_tokens=6)
    pred_nums = generated[0, -6:].tolist()
    print(f"預測: {pred_nums}")

if __name__ == '__main__':
    train()
