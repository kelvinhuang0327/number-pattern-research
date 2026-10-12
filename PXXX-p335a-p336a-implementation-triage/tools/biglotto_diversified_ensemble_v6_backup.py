#!/usr/bin/env python3
"""
Biglotto Diversified Ensemble Predictor (Phase 18.5 - Optimal Baseline)
=====================================================================
The most robust configuration found during the 18.x series.
Focuses on Synergy Structural and Dynamic Pruning.
"""
import os
import sys
import numpy as np
import json
from collections import Counter
import random

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.unified_predictor import UnifiedPredictionEngine, predict_special_number
from lottery_api.models.biglotto_graph import BiglottoGraph

class DiversifiedEnsemble:
    def __init__(self, db_path=None, seed=42):
        if db_path is None:
            db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
        self.db = DatabaseManager(db_path=db_path)
        self.engine = UnifiedPredictionEngine()
        self.rules = get_lottery_rules('BIG_LOTTO')
        self.graph = BiglottoGraph()
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    def get_history(self, limit=1000):
        history = self.db.get_all_draws(lottery_type='BIG_LOTTO')
        return history[:limit]

    def detect_regime(self, history, window=10):
        imbalance_count = 0
        for d in history[:window]:
            nums = json.loads(d['numbers']) if isinstance(d['numbers'], str) else d.get('numbers', [])
            if nums:
                odd_ratio = sum(1 for n in nums if n % 2 == 1) / 6
                if odd_ratio >= 0.8 or odd_ratio <= 0.2:
                    imbalance_count += 1
        return "SKEWED" if imbalance_count >= 2 else "BALANCED"

    def validate_combination(self, numbers, stats):
        ac = self.engine.analyzer.calculate_ac_value(numbers)
        entropy = self.engine.analyzer.calculate_entropy(numbers, max_num=49)
        if (ac < stats['ac_avg'] - 1.5 * stats['ac_std'] or 
            entropy < stats['entropy_avg'] - 1.5 * stats['entropy_std']):
            return False
        return True

    def _get_structural_stats(self, history):
        acs = []
        entropies = []
        for d in history[:100]:
            nums = json.loads(d['numbers']) if isinstance(d['numbers'], str) else d.get('numbers', [])
            if nums:
                acs.append(self.engine.analyzer.calculate_ac_value(nums))
                entropies.append(self.engine.analyzer.calculate_entropy(nums, max_num=49))
        if not acs: return {'ac_avg': 8, 'ac_std': 1, 'entropy_avg': 2.5, 'entropy_std': 0.2}
        return {'ac_avg': np.mean(acs), 'ac_std': np.std(acs), 'entropy_avg': np.mean(entropies), 'entropy_std': np.std(entropies)}

    def predict_3bets(self, history=None):
        if history is None: history = self.get_history()
        random.seed(self.seed); np.random.seed(self.seed)
        regime = self.detect_regime(history)
        stats = self._get_structural_stats(history)
        
        # 1. Bet 1: Consensus (Bayesian + Frequency)
        bayesian = self.engine.bayesian_predict(history, self.rules)
        freq = self.engine.frequency_predict(history, self.rules)
        pool_1 = sorted(list(set(bayesian['numbers'][:12] + freq['numbers'][:12])))
        final_bet1 = sorted(pool_1[:6])
        for _ in range(150):
            sample = sorted(random.sample(pool_1, 6))
            if self.validate_combination(sample, stats):
                final_bet1 = sample
                break
        bet1 = {'numbers': final_bet1, 'special': bayesian['special'], 'type': f'Consensus ({regime})', 'strategy_id': 'DIVERSIFIED_BET_1'}

        # 2. Bet 2: Synergy (Graph Centrality)
        self.graph.build_from_history(history, lookback=500)
        props = self.graph.analyze_graph_properties()
        cen_scores = {n: props['degree_centrality'].get(n, 0) * 0.7 + props['betweenness_centrality'].get(n, 0) * 0.3 for n in range(1, 50)}
        pool_2 = [n for n, s in sorted(cen_scores.items(), key=lambda x: -x[1])[:20]]
        final_bet2 = sorted(pool_2[:6])
        for _ in range(150):
            sample = sorted(random.sample(pool_2, 6))
            if self.validate_combination(sample, stats):
                final_bet2 = sample
                break
        special_2 = predict_special_number(history, self.rules, strategy_name='markov')
        if isinstance(special_2, list): special_2 = special_2[0]
        bet2 = {'numbers': final_bet2, 'special': int(special_2), 'type': 'Synergy (Graph)', 'strategy_id': 'DIVERSIFIED_BET_2'}

        # 3. Bet 3: Disruptor (Tail Freq + Odd/Even Adaptive)
        tail_freq = Counter()
        for d in history[:100]:
            nums = json.loads(d['numbers']) if isinstance(d['numbers'], str) else d.get('numbers', [])
            tail_freq.update([n % 10 for n in nums])
        hot_tails = [t for t, f in tail_freq.most_common(5)]
        target_odd_count = 5 if regime == "SKEWED" else 3
        odd_nums = [n for n in range(1, 50) if n % 2 == 1]; even_nums = [n for n in range(1, 49) if n % 2 == 0]
        pool_3 = [n for n in (odd_nums + even_nums) if n % 10 in hot_tails]
        if len(pool_3) < 12: pool_3 = list(range(1, 50))
        final_bet3 = sorted(pool_3[:6])
        for _ in range(200):
            sample = sorted(random.sample(pool_3, 6))
            # Rough odd count check
            if sum(1 for n in sample if n % 2 == 1) >= target_odd_count:
                if self.validate_combination(sample, stats):
                    final_bet3 = sample
                    break
        special_3 = predict_special_number(history, self.rules, strategy_name='bayesian')
        if isinstance(special_3, list): special_3 = special_3[0]
        bet3 = {'numbers': final_bet3[:6], 'special': int(special_3), 'type': 'Disruptor (Entropy)', 'strategy_id': 'DIVERSIFIED_BET_3'}

        return [bet1, bet2, bet3]

if __name__ == '__main__':
    ensemble = DiversifiedEnsemble()
    bets = ensemble.predict_3bets()
    print(json.dumps(bets, indent=2))
