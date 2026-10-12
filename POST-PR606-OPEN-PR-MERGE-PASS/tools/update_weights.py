import re

path = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/models/optimized_ensemble.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

new_weights = """        'POWER_LOTTO': {
            # === 🥇 核心贏家 (Proven Edge / Trusted Synergy) ===
            'markov': 0.20,             # ⛓️ 馬可夫鏈 (長期穩定)
            'dynamic_ensemble': 0.18,   # 🥇 平均命中穩定
            'fourier_main': 0.15,       # 🌊 傅立葉 (2注版本有 +1.91% Edge，單注已拒絕)
            
            # === 🥈 模式識別 (AI Models) ===
            'sota': 0.12,               # 🚀 Transformer
            'maml': 0.10,               # 🧠 元學習
            'anomaly': 0.08,            # 🔍 異常檢測
            
            # === 🥉 監控/拒絕 (Failed Audits) ===
            'lag_reversion': 0.01,      # ❌ 已拒絕 (3.20% < 3.87%)
            'clustering': 0.05,         
            'anti_consensus': 0.05,     
            'cluster_pivot': 0.03,      
            'bayesian': 0.03,           
        },"""

# 使用正則表達式替換整個 POWER_LOTTO 區塊
pattern = r"        'POWER_LOTTO': \{.*?        \},"
new_content = re.sub(pattern, new_weights, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print("Updated successfully")
