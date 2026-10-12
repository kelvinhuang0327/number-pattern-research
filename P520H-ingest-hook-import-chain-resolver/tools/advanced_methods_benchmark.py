#!/usr/bin/env python3
"""
Advanced Prediction Methods for 2-3 Bet Optimization
=====================================================

Implements cutting-edge methods that were not in the standard benchmark:
1. Reinforcement Learning (Contextual Bandit)
2. Copula Multivariate Analysis
3. Anomaly Detection
4. Graph-based Co-occurrence
5. Attention-weighted Scoring
"""

import os
import sys
import json
import sqlite3
import random
import numpy as np
from typing import List, Dict, Tuple, Set
from itertools import combinations
from collections import Counter, defaultdict
from scipy.stats import binomtest, norm, kendalltau
import logging

random.seed(42)
np.random.seed(42)

logging.basicConfig(level=logging.WARNING)

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

# =============================================================================
# DATA LOADING
# =============================================================================

def load_history(lottery_type: str, max_records: int = 2000) -> List[Dict]:
    db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT draw, numbers, special, date FROM draws 
        WHERE lottery_type = ? 
        ORDER BY draw DESC LIMIT ?
    """, (lottery_type, max_records))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        nums = json.loads(r[1]) if isinstance(r[1], str) else []
        special = r[2]
        if len(nums) == 6:
            history.append({
                'draw': r[0], 
                'numbers': nums, 
                'special': int(special) if special else None,
                'date': r[3]
            })
    return history

# =============================================================================
# ADVANCED METHOD 1: CONTEXTUAL BANDIT (RL-INSPIRED)
# =============================================================================

class ContextualBandit:
    """
    Simple contextual bandit for number selection.
    Context: recent frequency, gaps, last draw features
    Action: selecting a number
    Reward: +1 if selected number appears, 0 otherwise
    """
    
    def __init__(self, max_num: int, learning_rate: float = 0.1):
        self.max_num = max_num
        self.lr = learning_rate
        # Weights for each number x feature
        self.weights = np.zeros((max_num, 5))  # 5 context features
        
    def get_context(self, history: List[Dict], number: int) -> np.ndarray:
        """Extract context features for a number."""
        recent = history[:50]
        
        # Feature 1: Frequency in last 50
        counter = Counter()
        for d in recent:
            counter.update(d['numbers'])
        freq = counter.get(number, 0) / 50
        
        # Feature 2: Gap (draws since last appearance)
        gap = 0
        for i, d in enumerate(history):
            if number in d['numbers']:
                gap = i
                break
        else:
            gap = len(history)
        gap_normalized = min(gap / 50, 1.0)
        
        # Feature 3: In last draw
        in_last = 1.0 if (history and number in history[0]['numbers']) else 0.0
        
        # Feature 4: Odd/even indicator
        is_odd = 1.0 if number % 2 == 1 else 0.0
        
        # Feature 5: Zone (normalized position)
        zone = (number - 1) / self.max_num
        
        return np.array([freq, gap_normalized, in_last, is_odd, zone])
    
    def train(self, history: List[Dict], train_periods: int = 200):
        """Train on historical data."""
        for i in range(train_periods, len(history)):
            target = set(history[i-train_periods]['numbers'])
            context_hist = history[i-train_periods+1:]
            
            for num in range(1, self.max_num + 1):
                ctx = self.get_context(context_hist, num)
                pred = np.dot(self.weights[num-1], ctx)
                actual = 1.0 if num in target else 0.0
                error = actual - pred
                self.weights[num-1] += self.lr * error * ctx
    
    def predict(self, history: List[Dict], k: int = 6) -> List[int]:
        """Predict top k numbers."""
        scores = []
        for num in range(1, self.max_num + 1):
            ctx = self.get_context(history, num)
            score = np.dot(self.weights[num-1], ctx)
            scores.append((num, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return [num for num, _ in scores[:k]]

# =============================================================================
# ADVANCED METHOD 2: COPULA-BASED DEPENDENCY ANALYSIS
# =============================================================================

class CopulaAnalyzer:
    """
    Analyze dependencies between numbers using rank correlation (Kendall's tau).
    """
    
    def __init__(self, max_num: int):
        self.max_num = max_num
        self.tau_matrix = np.zeros((max_num, max_num))
        
    def train(self, history: List[Dict], window: int = 100):
        """Compute pairwise Kendall's tau."""
        # Create binary occurrence vectors
        vectors = np.zeros((window, self.max_num))
        for i, d in enumerate(history[:window]):
            for num in d['numbers']:
                vectors[i, num-1] = 1
        
        # Compute tau for each pair
        for i in range(self.max_num):
            for j in range(i+1, self.max_num):
                if np.std(vectors[:, i]) > 0 and np.std(vectors[:, j]) > 0:
                    tau, _ = kendalltau(vectors[:, i], vectors[:, j])
                    self.tau_matrix[i, j] = tau
                    self.tau_matrix[j, i] = tau
    
    def predict(self, history: List[Dict], k: int = 6) -> List[int]:
        """Select numbers with strong positive dependencies."""
        # Start with most frequent
        recent = history[:50]
        counter = Counter()
        for d in recent:
            counter.update(d['numbers'])
        
        sorted_nums = [n for n, _ in counter.most_common()]
        
        # Build selection by maximizing positive tau
        selected = [sorted_nums[0]] if sorted_nums else [1]
        
        while len(selected) < k and len(sorted_nums) > 0:
            best_next = None
            best_tau_sum = -float('inf')
            
            for num in sorted_nums:
                if num in selected:
                    continue
                
                tau_sum = sum(self.tau_matrix[num-1, s-1] for s in selected)
                if tau_sum > best_tau_sum:
                    best_tau_sum = tau_sum
                    best_next = num
            
            if best_next:
                selected.append(best_next)
                sorted_nums.remove(best_next)
            else:
                break
        
        return sorted(selected[:k])

# =============================================================================
# ADVANCED METHOD 3: ANOMALY DETECTION
# =============================================================================

class AnomalyDetector:
    """
    Detect draws that deviate from expected patterns.
    Use this to avoid "typical" numbers and bet on anomalies.
    """
    
    def __init__(self, max_num: int):
        self.max_num = max_num
        self.expected_probs = None
        
    def train(self, history: List[Dict]):
        """Learn expected probability distribution."""
        counter = Counter()
        total = 0
        for d in history:
            counter.update(d['numbers'])
            total += len(d['numbers'])
        
        self.expected_probs = np.array([
            counter.get(n, 0) / total for n in range(1, self.max_num + 1)
        ])
    
    def predict(self, history: List[Dict], k: int = 6) -> List[int]:
        """Select numbers that are anomalously underrepresented recently."""
        if self.expected_probs is None:
            return list(range(1, k+1))
        
        recent = history[:30]
        recent_counter = Counter()
        for d in recent:
            recent_counter.update(d['numbers'])
        
        recent_freq = np.array([
            recent_counter.get(n, 0) / (30 * 6) for n in range(1, self.max_num + 1)
        ])
        
        # Anomaly score: expected - recent (high = underrepresented)
        anomaly_scores = self.expected_probs - recent_freq
        
        indexed = [(i+1, anomaly_scores[i]) for i in range(len(anomaly_scores))]
        indexed.sort(key=lambda x: x[1], reverse=True)
        
        return [n for n, _ in indexed[:k]]

# =============================================================================
# ADVANCED METHOD 4: GRAPH CO-OCCURRENCE
# =============================================================================

class GraphCooccurrence:
    """
    Build a weighted graph of number co-occurrences.
    Use PageRank-inspired scoring.
    """
    
    def __init__(self, max_num: int):
        self.max_num = max_num
        self.adjacency = np.zeros((max_num, max_num))
        
    def train(self, history: List[Dict], window: int = 100):
        """Build co-occurrence graph."""
        for d in history[:window]:
            nums = d['numbers']
            for i, a in enumerate(nums):
                for b in nums[i+1:]:
                    self.adjacency[a-1, b-1] += 1
                    self.adjacency[b-1, a-1] += 1
    
    def pagerank(self, d: float = 0.85, iterations: int = 20) -> np.ndarray:
        """Compute PageRank scores."""
        n = self.max_num
        pr = np.ones(n) / n
        
        # Normalize adjacency
        row_sums = self.adjacency.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1
        trans = self.adjacency / row_sums
        
        for _ in range(iterations):
            pr = (1 - d) / n + d * trans.T @ pr
        
        return pr
    
    def predict(self, history: List[Dict], k: int = 6) -> List[int]:
        """Select top PageRank numbers."""
        pr = self.pagerank()
        indexed = [(i+1, pr[i]) for i in range(len(pr))]
        indexed.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in indexed[:k]]

# =============================================================================
# ADVANCED METHOD 5: ATTENTION-WEIGHTED SCORING
# =============================================================================

class AttentionScorer:
    """
    Attention mechanism: recent draws get more weight.
    Combine multiple signals with learned attention.
    """
    
    def __init__(self, max_num: int):
        self.max_num = max_num
    
    def predict(self, history: List[Dict], k: int = 6) -> List[int]:
        """Predict with exponential attention decay on history."""
        decay = 0.95
        scores = np.zeros(self.max_num)
        
        for i, d in enumerate(history[:100]):
            weight = decay ** i
            for num in d['numbers']:
                scores[num-1] += weight
        
        indexed = [(i+1, scores[i]) for i in range(len(scores))]
        indexed.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in indexed[:k]]

# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_advanced_benchmark(lottery_type: str, num_bets: int, periods: int = 500):
    """Run advanced methods benchmark."""
    
    print(f"\n{'='*70}")
    print(f"🚀 ADVANCED METHODS BENCHMARK: {lottery_type} | {num_bets}-bet | {periods}P")
    print('='*70)
    
    all_history = load_history(lottery_type, periods + 500)
    max_num = 38 if lottery_type == 'POWER_LOTTO' else 49
    
    # Calculate baselines
    baseline_1bet = 0.0387 if lottery_type == 'POWER_LOTTO' else 0.0186
    baseline_nbet = 1 - (1 - baseline_1bet) ** num_bets
    
    methods = {
        'Contextual Bandit': ContextualBandit(max_num),
        'Copula Analysis': CopulaAnalyzer(max_num),
        'Anomaly Detection': AnomalyDetector(max_num),
        'Graph PageRank': GraphCooccurrence(max_num),
        'Attention Scorer': AttentionScorer(max_num),
    }
    
    results = {}
    
    for name, method in methods.items():
        hits = 0
        
        for i in range(periods):
            context = all_history[i+1:]
            target = set(all_history[i]['numbers'])
            
            # Train if needed
            if hasattr(method, 'train'):
                try:
                    method.train(context[:200])
                except:
                    pass
            
            # Generate bets
            bets = []
            for _ in range(num_bets):
                try:
                    bet = method.predict(context, 6)
                    bets.append(bet)
                except:
                    bets.append(random.sample(range(1, max_num + 1), 6))
            
            is_win = any(len(set(bet) & target) >= 3 for bet in bets)
            if is_win:
                hits += 1
        
        rate = hits / periods
        edge = (rate - baseline_nbet) * 100
        results[name] = {'hits': hits, 'rate': rate, 'edge': edge}
    
    # Random baseline
    random_hits = 0
    for i in range(periods):
        target = set(all_history[i]['numbers'])
        bets = [sorted(random.sample(range(1, max_num + 1), 6)) for _ in range(num_bets)]
        if any(len(set(bet) & target) >= 3 for bet in bets):
            random_hits += 1
    
    results['Random Baseline'] = {
        'hits': random_hits,
        'rate': random_hits / periods,
        'edge': (random_hits / periods - baseline_nbet) * 100
    }
    
    # Print results
    print(f"\n{'Method':<25} {'Hits':<8} {'Rate':<10} {'Edge':<10}")
    print('-'*55)
    
    sorted_results = sorted(results.items(), key=lambda x: x[1]['rate'], reverse=True)
    for name, data in sorted_results:
        print(f"{name:<25} {data['hits']:<8} {data['rate']*100:>6.2f}%    {data['edge']:>+6.2f}%")
    
    print(f"\nBaseline ({num_bets}-bet): {baseline_nbet*100:.2f}%")
    
    return results

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Run all benchmarks
    for ltype in ['POWER_LOTTO', 'BIG_LOTTO']:
        for nbets in [2, 3]:
            run_advanced_benchmark(ltype, nbets, 500)
