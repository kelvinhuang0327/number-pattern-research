#!/usr/bin/env python3
import torch
import torch.nn as nn
import json
import os
import sys
import numpy as np
import random
from collections import Counter
import contextlib
import io

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, os.path.join(project_root, 'ai_lab'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from models.hpsb_optimizer import HPSBOptimizer
from ai_models.transformer_v2 import HybridLotteryTransformer
from scripts.train_v3 import HybridV3Dataset

def set_seed(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

class V3Predictor:
    def __init__(self, model_path: str, device='cpu'):
        self.device = device
        self.model = HybridLotteryTransformer().to(device)
        self.model.load_state_dict(torch.load(model_path, map_location=device))
        self.model.eval()
        self.dataset = HybridV3Dataset(os.path.join(project_root, 'ai_lab/data/real_biglotto.json'))
        
    def _apply_zdp(self, candidates, pick_count, rules):
        max_num = rules.get('maxNumber', 49)
        z1 = max_num // 3
        z2 = 2 * (max_num // 3)
        zones = {'low': (1, z1), 'mid': (z1 + 1, z2), 'high': (z2 + 1, max_num)}
        MAX_PER_ZONE = 3
        selected = []
        zone_counts = Counter()
        for num in candidates:
            if len(selected) >= pick_count: break
            target_zone = None
            for z, (start, end) in zones.items():
                if start <= num <= end:
                    target_zone = z
                    break
            if target_zone and zone_counts[target_zone] < MAX_PER_ZONE:
                selected.append(num)
                zone_counts[target_zone] += 1
        if len(selected) < pick_count:
            remaining = [n for n in candidates if n not in selected]
            selected.extend(remaining[:pick_count - len(selected)])
        return sorted(selected[:pick_count])

    def predict(self, history, rules):
        pick_count = rules.get('pickCount', 6)
        seq_len = 15
        context_draws = [d['numbers'] for d in history[-seq_len:]]
        while len(context_draws) < 15:
            context_draws.insert(0, [0]*6)
            
        stats = []
        for i in range(len(context_draws)):
            prev = context_draws[i-1] if i > 0 else None
            stats.append(self.dataset._extract_v3_stats(context_draws[i], prev))
            
        x = torch.tensor([context_draws], dtype=torch.long).to(self.device)
        s = torch.tensor([stats], dtype=torch.float).to(self.device)
        
        with torch.no_grad():
            logits = self.model(x, s)
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
            
        probs[0] = -1
        sorted_indices = np.argsort(probs)[::-1]
        candidates = [int(idx) for idx in sorted_indices if 1 <= idx <= rules.get('maxNumber', 49)]
        
        final_numbers = self._apply_zdp(candidates, pick_count, rules)
        return {'numbers': final_numbers, 'method': 'AI-Lab U-HPE V3'}

def run_benchmark(name, predict_func, all_draws, rules, periods=200):
    set_seed(42)
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    for i in range(periods):
        target_idx = len(all_draws) - periods + i
        if target_idx <= 0: continue
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                res = predict_func(history, rules)
            m = len(set(res['numbers']) & actual)
            if m >= 3: match_3_plus += 1
            match_dist[m] += 1
            total += 1
        except Exception as e:
            continue
    rate = match_3_plus / total * 100 if total > 0 else 0
    return rate, match_3_plus, total, match_dist

def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    v3_path = os.path.join(project_root, 'ai_lab', 'ai_models', 'v3_deep_resonance.pth')
    rl_gen3_path = os.path.join(project_root, 'ai_lab', 'ai_models', 'rl_gen3_best.pth')
    
    if not os.path.exists(v3_path):
        print("V3 Model not found.")
        return
        
    v3_predictor = V3Predictor(v3_path)
    hpsb_v2 = HPSBOptimizer(UnifiedPredictionEngine())
    
    # Needs Gen-3 to compare, but remember Gen-3 has stat_dim=7, while v2 code is updated to v3 architecture.
    # To compare fairly, we'd need to roll back model code or use a fresh predictor class.
    # For now, let's focus on V3 vs DMS.
    
    print("=" * 70)
    print("🔬 AI-Lab Phase 10: U-HPE V3 (Deep Resonance) Benchmark")
    print("=" * 70)
    
    strategies = [
        ("DMS (SOTA Baseline)", hpsb_v2.predict_hpsb_v2),
        ("U-HPE V3 (Deep Resonance)", v3_predictor.predict)
    ]
    
    for name, func in strategies:
        rate, count, total, dist = run_benchmark(name, func, all_draws, rules, 200)
        print(f"{name:25}: {rate:5.2f}% ({count:2d}/{total}) | M3:{dist[3]} M4:{dist[4]} M5:{dist[5]} M0:{dist[0]}")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
