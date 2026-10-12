import os
import sys
import logging
import json
import random
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Set

# Setup paths
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.unified_predictor import UnifiedPredictionEngine
from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.utils.backtest_safety import (
    validate_chronological_order, 
    get_safe_backtest_slice,
    isolate_mab_state,
    cleanup_backtest_state
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('ClusterFusionResearch')

class ClusterFusionPredictor:
    def __init__(self, lottery_type: str = 'BIG_LOTTO'):
        self.lottery_type = lottery_type
        self.rules = get_lottery_rules(lottery_type)
        self.engine = UnifiedPredictionEngine()
        self.max_num = self.rules['maxNumber']
        self.pick_count = self.rules['pickCount']

    def build_matrices(self, history: List[Dict]):
        """Builds both pair and triad co-occurrence matrices."""
        pairs = Counter()
        triads = Counter()
        for draw in history:
            nums = sorted(draw['numbers'])
            for p in combinations(nums, 2):
                pairs[p] += 1
            for t in combinations(nums, 3):
                triads[t] += 1
        return pairs, triads

    def get_ensemble_momentum(self, history: List[Dict]) -> Dict[int, float]:
        """Calculates momentum scores internally."""
        if not history:
            return {i: 0.0 for i in range(1, self.max_num + 1)}

        lambda_val = 0.05
        trend_weighted = Counter()
        for i, draw in enumerate(reversed(history[-100:])):
            weight = np.exp(-lambda_val * i)
            for num in draw['numbers']:
                trend_weighted[num] += weight
        
        expected_freq = (len(history) * self.pick_count) / self.max_num
        all_nums = [n for d in history for n in d['numbers']]
        counts = Counter(all_nums)
        
        sum_sq_diff = 0
        for i in range(1, self.max_num + 1):
            diff = counts.get(i, 0) - expected_freq
            sum_sq_diff += diff * diff
        std_dev = (sum_sq_diff / self.max_num)**0.5
        
        momentum = {}
        for num in range(1, self.max_num + 1):
            t_score = trend_weighted.get(num, 0)
            z = (counts.get(num, 0) - expected_freq) / std_dev if std_dev > 0 else 0
            d_score = 0.8 if z < -1.5 else (0.6 if z < 0 else 0.4)
            momentum[num] = (t_score * 0.7) + (d_score * 0.3)
            
        return momentum

    def fusion_v2_predict(self, history: List[Dict], num_bets: int = 4) -> List[List[int]]:
        pairs, _ = self.build_matrices(history)
        momentum = self.get_ensemble_momentum(history)
        
        num_scores = Counter()
        for (a, b), count in pairs.items():
            num_scores[a] += count
            num_scores[b] += count
        centers = [n for n, _ in num_scores.most_common(num_bets * 2)]
        
        bets = []
        used = set()
        for center in centers:
            if len(bets) >= num_bets: break
            partners = []
            for (a, b), count in pairs.items():
                if a == center: partners.append((b, count))
                elif b == center: partners.append((a, count))
            if not partners: continue
            
            partners = sorted(partners, key=lambda x: x[1], reverse=True)[:12]
            partner_nums = [p[0] for p in partners]
            ranked_partners = sorted(partner_nums, key=lambda x: momentum.get(x, 0), reverse=True)
            
            bet = [center]
            for p in ranked_partners:
                if p not in bet: bet.append(p)
                if len(bet) >= self.pick_count: break
            
            if len(bet) == self.pick_count:
                if not used or len(set(bet) - used) >= 3:
                    bets.append(sorted(bet))
                    used.update(bet)
        return bets

    def triad_predict(self, history: List[Dict], num_bets: int = 4) -> List[List[int]]:
        _, triads = self.build_matrices(history)
        top_triads = [t for t, _ in triads.most_common(num_bets)]
        pairs, _ = self.build_matrices(history)
        
        bets = []
        for triad in top_triads:
            bet = list(triad)
            candidates = Counter()
            for t_num in triad:
                for (a, b), count in pairs.items():
                    if a == t_num and b not in bet: candidates[b] += count
                    elif b == t_num and a not in bet: candidates[a] += count
            
            for num, _ in candidates.most_common(self.pick_count - 3):
                bet.append(num)
            
            while len(bet) < self.pick_count:
                for n in range(1, self.max_num + 1):
                    if n not in bet: bet.append(n)
                    if len(bet) >= self.pick_count: break
            bets.append(sorted(bet))
        return bets

    def cycle_aware_filter(self, history: List[Dict], candidates: List[int]) -> List[int]:
        if not history: return candidates
        last_seen = {i: -1 for i in range(1, self.max_num + 1)}
        for i, draw in enumerate(reversed(history)):
            for n in draw['numbers']:
                if last_seen[n] == -1: last_seen[n] = i
        
        filtered = []
        for n in candidates:
            gap = last_seen.get(n, 100)
            if gap < 25: filtered.append(n)
            elif gap > 40: continue
            else: filtered.append(n)
        return filtered

    def structural_hybrid_v3_predict(self, history: List[Dict]) -> List[List[int]]:
        pairs_all, triads_all = self.build_matrices(history)
        pairs_recent, _ = self.build_matrices(history[-50:])
        bets = []
        used = set()
        
        def expand_safe(anchor, matrix, history, count=5, exclude=None):
            if exclude is None: exclude = set()
            cands = Counter()
            for (a, b), c in matrix.items():
                if a == anchor and b not in exclude: cands[b] += c
                elif b == anchor and a not in exclude: cands[a] += c
            
            sorted_cands = [n for n, _ in cands.most_common(20)]
            filtered_cands = self.cycle_aware_filter(history, sorted_cands)
            res = [anchor]
            for n in filtered_cands:
                if n not in res: res.append(n)
                if len(res) >= self.pick_count: break
            if len(res) < self.pick_count:
                for n, _ in cands.most_common(20):
                    if n not in res: res.append(n)
                    if len(res) >= self.pick_count: break
            return sorted(res)
            
        num_scores_all = Counter()
        for (a, b), count in pairs_all.items():
            num_scores_all[a] += count
            num_scores_all[b] += count
        
        if num_scores_all:
            center1 = num_scores_all.most_common(1)[0][0]
            bet1 = expand_safe(center1, pairs_all, history)
            bets.append(bet1)
            used.update(bet1)
        
        if triads_all:
            triad2 = triads_all.most_common(1)[0][0]
            bet2 = list(triad2)
            triad_cands = Counter()
            for t_num in triad2:
                for (a, b), c in pairs_all.items():
                    if a == t_num and b not in bet2: triad_cands[b] += c
                    elif b == t_num and a not in bet2: triad_cands[a] += c
            sorted_triad_cands = [n for n, _ in triad_cands.most_common(15)]
            filtered_triad = self.cycle_aware_filter(history, sorted_triad_cands)
            for n in filtered_triad:
                if n not in bet2: bet2.append(n)
                if len(bet2) >= self.pick_count: break
            if len(bet2) < self.pick_count:
                for n in sorted_triad_cands:
                    if n not in bet2: bet2.append(n)
                    if len(bet2) >= self.pick_count: break
            bets.append(sorted(bet2))
            used.update(bet2)
        
        num_scores_recent = Counter()
        for (a, b), count in pairs_recent.items():
            num_scores_recent[a] += count
            num_scores_recent[b] += count
        if num_scores_recent:
            center3 = num_scores_recent.most_common(1)[0][0]
            bet3 = expand_safe(center3, pairs_recent, history)
            bets.append(bet3)
            used.update(bet3)
        
        potential_centers = num_scores_all.most_common(25)
        for cand_center, _ in potential_centers:
            if len(bets) >= 4: break
            if cand_center not in used:
                bet4 = expand_safe(cand_center, pairs_all, history)
                bets.append(bet4)
                used.update(bet4)
        
        while len(bets) < 4:
             bets.append(expand_safe(random.randint(1,49), pairs_all, history))
        return bets

    def anomaly_structural_ensemble_predict(self, history: List[Dict]) -> List[List[int]]:
        v3_bets = self.structural_hybrid_v3_predict(history)
        all_nums = [n for d in history for n in d['numbers']]
        recent_nums = [n for d in history[-30:] for n in d['numbers']]
        long_counts = Counter(all_nums)
        recent_counts = Counter(recent_nums)
        
        anomaly_scores = {}
        for n in range(1, self.max_num + 1):
            expected = long_counts.get(n, 0) / max(1, len(history))
            actual = recent_counts.get(n, 0) / 30
            anomaly_scores[n] = abs(actual - expected)
            
        top_anomaly = sorted(anomaly_scores.items(), key=lambda x: x[1], reverse=True)[0][0]
        pairs_all, _ = self.build_matrices(history)
        
        def expand_simple(anchor, matrix):
            cands = Counter()
            for (a, b), c in matrix.items():
                if a == anchor: cands[b] += c
                elif b == anchor: cands[a] += c
            return sorted([anchor] + [n for n, _ in cands.most_common(5)])
            
        bet3 = expand_simple(top_anomaly, pairs_all)
        return [v3_bets[0], v3_bets[1], bet3, v3_bets[2]]

def run_research_backtest(periods: int = 150):
    db = DatabaseManager(os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = validate_chronological_order(db.get_all_draws('BIG_LOTTO'))
    predictor = ClusterFusionPredictor('BIG_LOTTO')
    
    results = {
        'Fusion V2 (4注)': {'m3+': 0, 'm4+': 0},
        'Triad (4注)': {'m3+': 0, 'm4+': 0},
        'Hybrid V3 (4注)': {'m3+': 0, 'm4+': 0},
        'Anomaly-Cluster (4注)': {'m3+': 0, 'm4+': 0},
    }
    
    test_data = all_draws[-periods:]
    logger.info(f"🚀 Starting Research Backtest: {periods} periods")
    
    for i, target_draw in enumerate(test_data):
        target_idx = all_draws.index(target_draw)
        history = get_safe_backtest_slice(all_draws, target_idx)
        actual = set(target_draw['numbers'])
        
        # 1. Fusion V2
        fusion_bets = predictor.fusion_v2_predict(history, num_bets=4)
        max_h = 0
        for b in fusion_bets: max_h = max(max_h, len(set(b) & actual))
        if max_h >= 3: results['Fusion V2 (4注)']['m3+'] += 1
        if max_h >= 4: results['Fusion V2 (4注)']['m4+'] += 1
        
        # 2. Triad
        triad_bets = predictor.triad_predict(history, num_bets=4)
        max_h = 0
        for b in triad_bets: max_h = max(max_h, len(set(b) & actual))
        if max_h >= 3: results['Triad (4注)']['m3+'] += 1
        if max_h >= 4: results['Triad (4注)']['m4+'] += 1
        
        # 3. Hybrid V3
        hybrid_bets = predictor.structural_hybrid_v3_predict(history)
        max_h = 0
        for b in hybrid_bets: max_h = max(max_h, len(set(b) & actual))
        if max_h >= 3: results['Hybrid V3 (4注)']['m3+'] += 1
        if max_h >= 4: results['Hybrid V3 (4注)']['m4+'] += 1

        # 4. Anomaly-Cluster
        anomaly_bets = predictor.anomaly_structural_ensemble_predict(history)
        max_h = 0
        for b in anomaly_bets: max_h = max(max_h, len(set(b) & actual))
        if max_h >= 3: results['Anomaly-Cluster (4注)']['m3+'] += 1
        if max_h >= 4: results['Anomaly-Cluster (4注)']['m4+'] += 1
        
        if (i+1) % 20 == 0: logger.info(f"Progress: {i+1}/{periods}...")

    print("\n" + "="*60)
    print(f"{'Strategy':25} | {'M3+':5} | {'M4+':5} | {'M3 Rate':8}")
    print("-" * 60)
    for name, stat in results.items():
        rate = (stat['m3+'] / periods) * 100
        print(f"{name:25} | {stat['m3+']:5d} | {stat['m4+']:5d} | {rate:7.2f}%")
    print("="*60)

if __name__ == "__main__":
    run_research_backtest(150)
