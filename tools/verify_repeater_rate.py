import sys
import os
import io
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def verify_repeater():
    print("=" * 60)
    print("🔬 Power Lotto Special Number Repeater Analysis (Full History)")
    print("=" * 60)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    # Get all draws, order Old -> New
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    
    specials = [d['special'] for d in all_draws if d.get('special')]
    
    total_draws = len(specials)
    if total_draws < 2:
        print("❌ Not enough data.")
        return

    repeats = 0
    intervals = [] # Distance between repeats
    
    last_repeat_idx = -1
    
    for i in range(1, total_draws):
        if specials[i] == specials[i-1]:
            repeats += 1
            if last_repeat_idx != -1:
                intervals.append(i - last_repeat_idx)
            last_repeat_idx = i
            
    rate = repeats / (total_draws - 1) * 100
    baseline = 1/8 * 100
    
    print(f"Total Draws: {total_draws}")
    print(f"Repeats: {repeats}")
    print(f"Repeater Rate: {rate:.2f}%")
    print(f"Baseline (1/8): {baseline:.2f}%")
    print(f"Difference: {rate - baseline:+.2f}%")
    
    print("-" * 60)
    if rate > baseline:
        print("✅ Hypothesis Supported: Repeater rate is higher than random.")
        # Check significance roughly (binomial test logic approximation)
        # N=1876, p=0.125. StdDev = sqrt(N*p*(1-p)) = sqrt(1876*0.125*0.875) = 14.3
        # Expected Hits = 234.5
        # Actual Hits = repeats
        expected = (total_draws - 1) * 0.125
        sigma = ((total_draws - 1) * 0.125 * 0.875) ** 0.5
        z_score = (repeats - expected) / sigma
        print(f"Z-Score: {z_score:.2f} (Sigma)")
        
        if z_score > 1.96:
            print("🌟 Statistically Significant (95% CI)")
        elif z_score > 1.0:
            print("⚠️ Positive Trend but not Significant (Signal < 2 Sigma)")
        else:
            print("❌ Within Noise levels")
    else:
        print("❌ Hypothesis Rejected: Repeater rate is NOT higher than random.")

if __name__ == '__main__':
    verify_repeater()
