#!/usr/bin/env python3
import random
import json
import os
import argparse
from typing import List, Dict
import numpy as np

class SyntheticLotteryGenerator:
    """
    Generates millions of synthetic lottery draws for Deep Learning pre-training.
    Supports injecting 'hidden' patterns that simulate physical machine biases.
    """
    
    def __init__(self, max_num: int = 49, pick_count: int = 6):
        self.max_num = max_num
        self.pick_count = pick_count
        
    def generate_pure_random(self, count: int) -> List[List[int]]:
        """Baseline: Pure i.i.d. draws."""
        data = []
        for _ in range(count):
            draw = sorted(random.sample(range(1, self.max_num + 1), self.pick_count))
            data.append(draw)
        return data

    def generate_with_zonal_bias(self, count: int, bias_zone: str = 'low') -> List[List[int]]:
        """Simulates a machine biased towards a specific zone."""
        z1 = self.max_num // 3
        z2 = 2 * (self.max_num // 3)
        
        zones = {
            'low': range(1, z1 + 1),
            'mid': range(z1 + 1, z2 + 1),
            'high': range(z2 + 1, self.max_num + 1)
        }
        
        data = []
        target_pool = list(zones[bias_zone])
        other_pool = [i for i in range(1, self.max_num + 1) if i not in target_pool]
        
        for _ in range(count):
            # 50% chance of being zone-heavy
            if random.random() < 0.5:
                # Pick 4 from target_zone, 2 from others
                draw = random.sample(target_pool, 4) + random.sample(other_pool, 2)
            else:
                draw = random.sample(range(1, self.max_num + 1), self.pick_count)
            data.append(sorted(draw))
        return data

    def generate_with_temporal_resonance(self, count: int, resonance_order: int = 2) -> List[List[int]]:
        """Simulates short-term state transitions (Markovian)."""
        data = []
        last_draw = random.sample(range(1, self.max_num + 1), self.pick_count)
        data.append(sorted(last_draw))
        
        for i in range(count - 1):
            # 30% chance that the next draw depends on the last one
            if random.random() < 0.3:
                # Simple transition: pick numbers 'near' last numbers or related by offset
                candidates = []
                for n in last_draw:
                    candidates.extend([max(1, n-2), max(1, n-1), n, min(self.max_num, n+1), min(self.max_num, n+2)])
                candidates = list(set(candidates))
                draw = random.sample(candidates, 3) + random.sample(range(1, self.max_num + 1), 3)
                # Ensure uniqueness
                draw = list(set(draw))
                while len(draw) < self.pick_count:
                    draw.append(random.randint(1, self.max_num))
                    draw = list(set(draw))
            else:
                draw = random.sample(range(1, self.max_num + 1), self.pick_count)
            
            last_draw = sorted(draw[:self.pick_count])
            data.append(last_draw)
        return data

def save_dataset(data: List[List[int]], filename: str):
    path = os.path.join(os.path.dirname(__file__), '..', 'data', filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f)
    print(f"Dataset saved to {path} ({len(data)} samples)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Lottery Data Generator")
    parser.add_argument("--count", type=int, default=10000, help="Number of draws to generate")
    parser.add_argument("--type", type=str, default="random", choices=["random", "zonal", "temporal"], help="Type of bias")
    parser.add_argument("--output", type=str, default="synthetic_data.json", help="Output filename")
    
    args = parser.parse_args()
    
    gen = SyntheticLotteryGenerator()
    if args.type == "random":
        dataset = gen.generate_pure_random(args.count)
    elif args.type == "zonal":
        dataset = gen.generate_with_zonal_bias(args.count)
    elif args.type == "temporal":
        dataset = gen.generate_with_temporal_resonance(args.count)
    
    save_dataset(dataset, args.output)
