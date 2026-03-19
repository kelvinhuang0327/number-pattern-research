import sys
import os
import io
import numpy as np
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_features():
    print("=" * 60)
    print("🔬 Power Lotto Special Number Deep Dive Analysis")
    print("=" * 60)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    # Get all draws, order Old -> New
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    
    specials = [d['special'] for d in all_draws if d.get('special')]
    total = len(specials)
    
    print(f"Total Samples: {total}")
    
    # 1. Odd vs Even
    odds = sum(1 for x in specials if x % 2 != 0)
    evens = sum(1 for x in specials if x % 2 == 0)
    print("\n[Odd/Even Balance]")
    print(f"Odd  (1,3,5,7): {odds} ({odds/total*100:.2f}%)")
    print(f"Even (2,4,6,8): {evens} ({evens/total*100:.2f}%)")
    print(f"Diff: {abs(odds-evens)}")
    
    # 2. Big vs Small
    small = sum(1 for x in specials if 1 <= x <= 4)
    big = sum(1 for x in specials if 5 <= x <= 8)
    print("\n[Big/Small Balance]")
    print(f"Small (1-4): {small} ({small/total*100:.2f}%)")
    print(f"Big   (5-8): {big} ({big/total*100:.2f}%)")
    
    # 3. Markov Transitions (Top Pairs)
    print("\n[Significant Transitions (A -> B)]")
    # Matrix counts
    matrix = np.zeros((9, 9)) # 1-indexed, so 9x9
    
    for i in range(total - 1):
        curr = specials[i]
        nxt = specials[i+1]
        matrix[curr][nxt] += 1
        
    # Calculate probabilities and highlight strong ones
    row_sums = matrix.sum(axis=1)
    
    strong_transitions = []
    
    for r in range(1, 9):
        total_row = row_sums[r]
        if total_row == 0: continue
        
        print(f"From {r}: ", end="")
        for c in range(1, 9):
            count = matrix[r][c]
            prob = count / total_row * 100
            
            # Highlight if significantly > 12.5% (e.g., > 16%)
            if prob > 15.0:
                print(f"->{c}({prob:.1f}%) ", end="")
                strong_transitions.append((r, c, prob))
        print()
        
    print("\n🏆 Top 5 Strongest Transitions:")
    strong_transitions.sort(key=lambda x: x[2], reverse=True)
    for r, c, p in strong_transitions[:5]:
        print(f"  {r} -> {c} : {p:.1f}% (Expected 12.5%)")

    # 4. Repeater Breakdown
    print("\n[Repeater by Number]")
    for n in range(1, 9):
        repeats = matrix[n][n]
        total_n = row_sums[n]
        rate = repeats / total_n * 100 if total_n > 0 else 0
        print(f"  Number {n}: Repeat Rate {rate:.1f}% ({int(repeats)}/{int(total_n)})")

if __name__ == "__main__":
    analyze_features()
