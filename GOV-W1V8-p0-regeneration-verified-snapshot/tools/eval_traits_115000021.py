import sys
import os
import numpy as np
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evolving_strategy_engine.data_loader import load_big_lotto_draws

def extract_traits(draws, target_nums):
    flat = draws.flatten()
    
    # 1. Frequency (w=30, w=100)
    counts_30 = collections.Counter(draws[-30:].flatten())
    counts_100 = collections.Counter(draws[-100:].flatten())
    
    # 2. Gap (waiting time)
    gaps = {}
    for num in range(1, 50):
        appearances = np.where(draws == num)[0]
        if len(appearances) > 0:
            gaps[num] = len(draws) - 1 - appearances[-1]
        else:
            gaps[num] = len(draws)
            
    # 3. Last Draw relation
    last_draw = draws[-1]
    
    print("Traits of the winning numbers:")
    for num in target_nums:
        c30 = counts_30.get(num, 0)
        c100 = counts_100.get(num, 0)
        gap = gaps.get(num, -1)
        in_last = num in last_draw
        print(f"Num {num:02d}: Freq(30)={c30} | Freq(100)={c100} | Gap={gap} | InLast={in_last}")

if __name__ == "__main__":
    draws, _ = load_big_lotto_draws()
    # 13, 15, 18, 24, 33, 49
    extract_traits(draws, [13, 15, 18, 24, 33, 49, 10])
