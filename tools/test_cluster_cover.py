#!/usr/bin/env python3
"""
🧪 Cluster-Cover Optimizer (Experimental)
Goal: Maximally exploit the Top 18 Pool using Co-occurrence Clustering.
"""
import sys
import os
import io
from collections import Counter, defaultdict
from itertools import combinations

# Add project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.biglotto_3bet_optimizer import BigLotto3BetOptimizer

# Fix encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class ClusterCoverOptimizer(BigLotto3BetOptimizer):
    def _build_cooccurrence_matrix(self, history):
        matrix = defaultdict(Counter)
        for d in history[-200:]: # Use last 200 for local patterns
            nums = d['numbers']
            for a, b in combinations(sorted(nums), 2):
                matrix[a][b] += 1
                matrix[b][a] += 1
        return matrix

    def predict_3bets_cluster_cover(self, history, rules, use_kill=True):
        # 1. Get Top 18 Candidates (Using P1 Kill)
        res = self.predict_3bets_diversified(history, rules, use_kill=use_kill)
        top_18 = res['candidates']
        
        # 2. Build Co-occurrence Matrix
        matrix = self._build_cooccurrence_matrix(history)
        
        # 3. Clustering Logic
        # Strategy: Pick Top 3 as Anchors for 3 Bets.
        anchors = top_18[:3]
        remaining = top_18[3:]
        
        bets = [[a] for a in anchors]
        available = set(remaining)
        
        # Round-robin fill based on highest sum of co-occurrence with current bet members
        for _ in range(5): # 5 more numbers per bet
            for b_idx in range(3):
                if not available: break
                
                best_cand = None
                max_score = -1
                
                for cand in available:
                    score = sum(matrix[cand][member] for member in bets[b_idx])
                    if score > max_score:
                        max_score = score
                        best_cand = cand
                
                if best_cand:
                    bets[b_idx].append(best_cand)
                    available.remove(best_cand)
        
        return {
            'bets': [{'numbers': sorted(b)} for b in bets],
            'candidates': top_18
        }

def test_cluster_cover(test_periods=150):
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')
    
    optimizer = ClusterCoverOptimizer()
    
    total = 0
    match_3_plus = 0
    match_dist = Counter()
    
    print(f"🔬 Testing Cluster-Cover Strategy over {test_periods} periods...")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0: continue
        
        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):
                res = optimizer.predict_3bets_cluster_cover(history, rules)
            
            best_match = 0
            for b in res['bets']:
                match = len(set(b['numbers']) & actual)
                if match > best_match:
                    best_match = match
            
            if best_match >= 3:
                match_3_plus += 1
            match_dist[best_match] += 1
            total += 1
            
            if (i+1) % 50 == 0:
                print(f"進度: {i+1}/{test_periods} | M-3+: {match_3_plus/total*100:.2f}%")
        except:
            continue

    print("\n" + "=" * 60)
    print(f"📊 Cluster-Cover Performance Report")
    print("-" * 60)
    print(f"Total Periods: {total}")
    print(f"Match-3+ Rate: {match_3_plus/total*100:.2f}% ({match_3_plus} times)")
    print("-" * 40)
    print("Match Dist:")
    for m in sorted(match_dist.keys(), reverse=True):
        print(f"  Match {m}: {match_dist[m]} 次")
    print("=" * 60)

if __name__ == '__main__':
    test_cluster_cover(200)
