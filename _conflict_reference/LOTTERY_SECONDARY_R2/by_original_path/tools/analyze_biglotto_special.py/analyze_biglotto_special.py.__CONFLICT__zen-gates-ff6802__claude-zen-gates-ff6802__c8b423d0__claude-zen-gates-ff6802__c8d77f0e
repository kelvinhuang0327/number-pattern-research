import sys
import os
import io
import numpy as np

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def analyze_biglotto_special():
    print("=" * 60)
    print("🔬 Big Lotto (大樂透) Special Number Analysis")
    print("=" * 60)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    # Get all draws
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    
    specials = [d['special'] for d in all_draws if d.get('special')]
    total = len(specials)
    
    if total < 2:
        print("Not enough data.")
        return
        
    print(f"Total Samples: {total}")
    print(f"Pool Size: 49")
    print(f"Random Baseline: {1/49*100:.2f}%")
    
    # 1. Repeater Rate
    repeats = 0
    for i in range(1, total):
        if specials[i] == specials[i-1]:
            repeats += 1
            
    rep_rate = repeats / (total - 1) * 100
    print(f"\n[Repeater Strategy]")
    print(f"Repeats: {repeats}")
    print(f"Rate: {rep_rate:.2f}% (vs Baseline 2.04%)")
    
    if rep_rate > 2.5:
        print("⚠️ Surprise: Repeater might work?")
    else:
        print("❌ Expected: Repeater is statistically weak for large pools.")
        
    # 2. Markov Sparsity
    # 49x49 matrix = 2401 cells. With ~2000 draws, most cells are 0 or 1.
    matrix = np.zeros((50, 50))
    for i in range(total - 1):
        c = specials[i]
        n = specials[i+1]
        matrix[c][n] += 1
        
    # Count how many transitions have >= 2 occurrences (repeat patterns)
    significant_transitions = 0
    total_transitions = 0
    for r in range(1, 50):
        for c in range(1, 50):
            if matrix[r][c] > 0:
                total_transitions += 1
            if matrix[r][c] >= 3: # Arbitrary threshold for "pattern"
                significant_transitions += 1
                
    print(f"\n[Markov Matrix Properties]")
    print(f"Non-zero cells: {total_transitions}/2401 ({total_transitions/2401*100:.1f}%)")
    print(f"Cells with >=3 hits: {significant_transitions}")
    
    # Is there ANY number that predicts the next one with > 10% confidence?
    print("\n[Best Predictors]")
    found_good = False
    for r in range(1, 50):
        row_sum = matrix[r].sum()
        if row_sum < 10: continue # Ignore rare numbers
        
        best_next = np.argmax(matrix[r])
        prob = matrix[r][best_next] / row_sum * 100
        
        if prob > 10.0: # If we can get >10% accuracy (5x random), it's worth it
            print(f"  From {r} -> {best_next}: {prob:.1f}% ({int(matrix[r][best_next])}/{int(row_sum)})")
            found_good = True
            
    if not found_good:
        print("  No strong predictors found (>10%).")

if __name__ == "__main__":
    analyze_biglotto_special()
