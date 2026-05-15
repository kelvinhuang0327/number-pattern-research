
import numpy as np
import sys
import os
import json
from collections import Counter, defaultdict
from tqdm import tqdm

# Setup path
lottery_api_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, lottery_api_dir)
os.chdir(lottery_api_dir)

from database import db_manager
db_manager.db_path = os.path.join(lottery_api_dir, "data", "lottery_v2.db")

from models.multi_bet_optimizer import MultiBetOptimizer
from common import load_backend_history, get_lottery_rules

def run_backtest(test_size=50):
    lottery_type = 'BIG_LOTTO'
    history, rules = load_backend_history(lottery_type)
    
    # Sort history by draw descending
    history = sorted(history, key=lambda x: int(x['draw']), reverse=True)
    
    # We will test the most recent 'test_size' draws
    test_draws = history[:test_size]
    remaining_history = history[test_size:]
    
    optimizer = MultiBetOptimizer()
    
    print(f"🚀 開始 大樂透 5注正交組合 回測")
    print(f"📊 測試期數: {test_size} | 歷史深度: {len(remaining_history)}")
    print("-" * 50)
    
    stats = {
        'total_draws': 0,
        'hit_0': 0,
        'hit_1': 0,
        'hit_2': 0,
        'hit_3': 0, # Match 3 (Winning)
        'hit_4': 0, # Match 4 (Winning)
        'hit_5': 0,
        'hit_6': 0,
        'any_win_3_plus': 0, # At least one bet has 3+ hits
        'union_hits': []     # Union of 5 bets hits per draw
    }
    
    draw_results = []
    
    for i in tqdm(range(len(test_draws))):
        target_draw = test_draws[i]
        target_numbers = set(target_draw['numbers'])
        
        # Use history PRIOR to this draw
        h_pred = history[i+1:]
        
        # Calculate number scores (simple freq for the optimizer)
        all_nums = [n for d in h_pred[:200] for n in d['numbers']]
        freq_counter = Counter(all_nums)
        number_scores = {n: freq_counter.get(n, 0) for n in range(1, 49 + 1)}
        
        # Generate 5-bet optimized (Phase 11)
        res = optimizer.generate_optimized_5bets_v11(h_pred, rules, number_scores)
        
        union_found = set()
        max_single_hit = 0
        
        for bet in res['bets']:
            hits = set(bet['numbers']) & target_numbers
            hit_count = len(hits)
            max_single_hit = max(max_single_hit, hit_count)
            union_found.update(hits)
            
            # Record individual hit stats
            # (Note: we only count the best hit per draw for the "win" stats)
            
        stats[f'hit_{max_single_hit}'] += 1
        if max_single_hit >= 3:
            stats['any_win_3_plus'] += 1
            
        stats['union_hits'].append(len(union_found))
        stats['total_draws'] += 1
        
        draw_results.append({
            'draw': target_draw['draw'],
            'target': sorted(list(target_numbers)),
            'max_hit': max_single_hit,
            'union_hit': len(union_found)
        })

    # Summary
    print("\n" + "=" * 50)
    print("📈 大樂透 5注正交組合 回測總結")
    print("=" * 50)
    print(f"測試總期數: {stats['total_draws']}")
    print("-" * 30)
    print(f"中獎率 (單注 3+): {stats['any_win_3_plus'] / stats['total_draws'] * 100:.1f}%")
    print(f"平均聯合命中: {np.mean(stats['union_hits']):.2f} / 6")
    print("-" * 30)
    print(f"最高命中 4 支期數: {stats['hit_4']}")
    print(f"最高命中 3 支期數: {stats['hit_3']}")
    print(f"最高命中 2 支期數: {stats['hit_2']}")
    print(f"最高命中 1 支期數: {stats['hit_1']}")
    print(f"完全落空期數: {stats['hit_0']}")
    print("=" * 50)
    
    # Save results
    with open('backtest_ortho_5bet_result.json', 'w') as f:
        json.dump({
            'summary': {
                'total': stats['total_draws'],
                'win_rate': stats['any_win_3_plus'] / stats['total_draws'],
                'avg_union': float(np.mean(stats['union_hits']))
            },
            'details': draw_results
        }, f, indent=4)

if __name__ == '__main__':
    run_backtest(50) # Balanced sample size for chat response
