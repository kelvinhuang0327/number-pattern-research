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
from lottery_api.models.advanced_strategies import AdvancedStrategies

class DiversifiedEnsemble:
    def __init__(self, db_path=None, seed=42):
        if db_path is None:
            db_path = os.path.join(project_root, 'lottery_api/data/lottery_v2.db')
        self.db = DatabaseManager(db_path=db_path)
        self.engine = UnifiedPredictionEngine()
        self.advanced = AdvancedStrategies(self.engine)
        self.rules = get_lottery_rules('BIG_LOTTO')
        self.graph = BiglottoGraph(min_num=1, max_num=49)
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)

    def get_history(self, limit=1000):
        history = self.db.get_all_draws(lottery_type='BIG_LOTTO')
        return history[:limit]

    def detect_regime(self, history, window=10):
        imbalance_count = 0
        for d in history[-window:] if len(history) >= window else history:
            nums = json.loads(d['numbers']) if isinstance(d['numbers'], str) else d.get('numbers', [])
            if nums:
                odd_ratio = sum(1 for n in nums if n % 2 == 1) / 6
                if odd_ratio >= 0.8 or odd_ratio <= 0.2:
                    imbalance_count += 1
        return "SKEWED" if imbalance_count >= 2 else "BALANCED"

    def calculate_max_gap(self, numbers):
        """Calculates the maximum interval between adjacent sorted numbers."""
        sorted_nums = sorted(numbers)
        gaps = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
        return max(gaps) if gaps else 0

    def _get_transition_matrix(self, history, window=200):
        matrix = {i: Counter() for i in range(1, 50)}
        recent_history = history[-window:] if len(history) > window else history
        for i in range(len(recent_history) - 1):
            prev_nums = [n for n in (json.loads(recent_history[i]['numbers']) if isinstance(recent_history[i]['numbers'], str) else recent_history[i]['numbers'])]
            next_nums = [n for n in (json.loads(recent_history[i+1]['numbers']) if isinstance(recent_history[i+1]['numbers'], str) else recent_history[i+1]['numbers'])]
            for p in prev_nums:
                matrix[p].update(next_nums)
        return matrix

    def _get_exposure_counts(self, history, window=6):
        exposure = Counter()
        for d in history[-window:] if len(history) >= window else history:
            nums = json.loads(d['numbers']) if isinstance(d['numbers'], str) else d.get('numbers', [])
            exposure.update(nums)
        return exposure

    def _get_consensus_scores(self, history):
        votes = Counter()
        # Module 1: Bayesian
        bayesian = self.engine.bayesian_predict(history, self.rules)
        votes.update(bayesian['numbers'][:15])
        
        # Module 2: Frequency
        freq_res = self.engine.frequency_predict(history, self.rules)
        votes.update(freq_res['numbers'][:15])
        
        # Module 3: Clustering
        cluster_res = self.advanced.clustering_predict(history, self.rules)
        active_candidates = cluster_res.get('details', {}).get('top_cluster_numbers', [])
        votes.update(active_candidates[:15])
        
        # Module 4: Graph Centrality
        self.graph.build_from_history(history, lookback=250)
        props = self.graph.analyze_graph_properties()
        cen_top = sorted(range(1, 50), key=lambda n: props['degree_centrality'].get(n, 0), reverse=True)[:15]
        votes.update(cen_top)
        
        return votes

    def _get_edge_momentum(self, history, window=100):
        pairs = Counter()
        recent = history[-window:]
        for d in recent:
            nums = sorted(json.loads(d['numbers']) if isinstance(d['numbers'], str) else d['numbers'])
            for i in range(len(nums)):
                for j in range(i+1, len(nums)):
                    pairs[(nums[i], nums[j])] += 1
        return pairs

    def _get_skip_repeat_scores(self, history):
        scores = Counter()
        if len(history) < 5: return scores
        
        d1 = set(json.loads(history[-1]['numbers']) if isinstance(history[-1]['numbers'], str) else history[-1]['numbers'])
        d2 = set(json.loads(history[-2]['numbers']) if isinstance(history[-2]['numbers'], str) else history[-2]['numbers'])
        d3 = set(json.loads(history[-3]['numbers']) if isinstance(history[-3]['numbers'], str) else history[-3]['numbers'])
        
        # Numbers that hit in D2/D3 but skipped D1
        skipped = (d2 | d3) - d1
        for n in skipped:
            scores[n] += 10
            
        return scores

    def _pick_zonal_balanced(self, score_dict, exposure, pruned_numbers):
        # Pick top 2 from each zone: 1-16, 17-32, 33-49
        z1 = [n for n in range(1, 17) if n not in pruned_numbers]
        z2 = [n for n in range(17, 33) if n not in pruned_numbers]
        z3 = [n for n in range(33, 50) if n not in pruned_numbers]
        
        result = []
        for zone in [z1, z2, z3]:
            # Sort zone by score
            sorted_zone = sorted(zone, key=lambda n: score_dict.get(n, 0), reverse=True)
            result.extend(sorted_zone[:2])
        return result

    def _get_cold_numbers(self, history, window=15):
        recent_nums = set([n for d in history[-window:] for n in (json.loads(d['numbers']) if isinstance(d['numbers'], str) else d['numbers'])])
        all_nums = set(range(1, 50))
        return list(all_nums - recent_nums)

    def _get_resonant_triplets(self, history, window=150):
        triplets = Counter()
        recent = history[-window:]
        for d in recent:
            nums = sorted(json.loads(d['numbers']) if isinstance(d['numbers'], str) else d['numbers'])
            # Generate all triplets
            for i in range(len(nums)):
                for j in range(i+1, len(nums)):
                    for k in range(j+1, len(nums)):
                        triplets[(nums[i], nums[j], nums[k])] += 1
        return {t: c for t, c in triplets.items() if c >= 2}

    def _get_adaptive_ac_range(self, history, window=20):
        ac_values = []
        for d in history[-window:]:
            nums = json.loads(d['numbers']) if isinstance(d['numbers'], str) else d['numbers']
            ac_values.append(self.engine.analyzer.calculate_ac_value(nums))
        if not ac_values: return 6, 11
        return min(ac_values), max(ac_values)

    def _get_special_synergy_scores(self, history, window=150, graph=None):
        """
        Calculates candidates for the Special Number (7th draw)
        using GNN topology and transition likelihood.
        """
        # ... (implementation logic)
        special_history = [d.get('special', 0) for d in history if d.get('special', 0) > 0]
        if not special_history: return {}
        
        last_special = special_history[-1]
        transitions = Counter()
        for i in range(len(special_history)-1):
            if special_history[i] == last_special:
                transitions[special_history[i+1]] += 1
                
        # Use provided graph or build a temporary one
        if graph is None:
            self.graph.build_from_history(history[-window:], lookback=window)
            graph_obj = self.graph.graph
        else:
            graph_obj = graph.graph if hasattr(graph, 'graph') else graph
            
        import networkx as nx
        centrality = nx.degree_centrality(graph_obj)
        betweenness = nx.betweenness_centrality(graph_obj)
        
        # Synergy Score = (0.5 * Markov) + (0.5 * High Betweenness / Low Degree)
        scores = {}
        for n in range(1, 50):
            m_score = transitions.get(n, 0) / (sum(transitions.values()) + 1)
            b_score = betweenness.get(n, 0)
            d_score = 1.0 - centrality.get(n, 1.0)
            # Mix: Topological bridge potential + Markov momentum
            scores[n] = m_score * 0.4 + (b_score * d_score) * 0.6
            
        return scores

    def validate_combination(self, numbers, stats, regime="BALANCED", level="STRICT", ac_range=None):
        # Final production validation for Big Lotto
        ac = self.engine.analyzer.calculate_ac_value(numbers)
        if ac < 5.5 or ac > 11: return False
        
        # AC standard deviation filter
        if (ac < stats['ac_avg'] - 1.2 * stats['ac_std'] or 
            ac > stats['ac_avg'] + 2.0 * stats['ac_std']):
            return False
        
        return True
            
        # 2. Sequential Constraint
        sorted_nums = sorted(numbers)
        consecutive_count = 0
        for i in range(len(sorted_nums)-1):
            if sorted_nums[i+1] - sorted_nums[i] == 1:
                consecutive_count += 1
            else:
                consecutive_count = 0
            
            # Level-based pruning
            limit = 2 if level == "STRICT" else 3
            if consecutive_count >= limit:
                return False

        # 3. Dynamic Max Gap Filter
        max_gap = self.calculate_max_gap(numbers)
        gap_limit = 1.2 if level == "STRICT" else 1.8
        if (max_gap < stats['max_gap_avg'] - 1.0 * stats['max_gap_std'] or 
            max_gap > stats['max_gap_avg'] + gap_limit * stats['max_gap_std']):
            return False

        # 4. Broadened Sum Range (110-240)
        total_sum = sum(numbers)
        if not (110 <= total_sum <= 240):
            return False
            
        # 5. Regime-Aware Zonal Balance
        z1 = sum(1 for n in numbers if 1 <= n <= 16)
        z2 = sum(1 for n in numbers if 17 <= n <= 32)
        z3 = sum(1 for n in numbers if 33 <= n <= 49)
        
        max_zone = 5 if regime == "SKEWED" else 4
        if max(z1, z2, z3) > max_zone:
            return False
            
        return True

    def find_stable_candidate(self, pool, stats, regime="BALANCED", max_tries=500, level="STRICT", ac_range=None):
        """Samples until one structurally sound candidate is found."""
        if len(pool) < 6:
            pool = list(range(1, 50))
            
        for _ in range(max_tries):
            candidate = sorted(random.sample(pool, 6))
            if self.validate_combination(candidate, stats, regime=regime, level=level, ac_range=ac_range):
                return candidate
        return sorted(random.sample(pool, 6))

    def _get_structural_stats(self, history):
        acs = []
        max_gaps = []
        # Use recent 100 for stats (ASC order)
        for d in history[-100:] if len(history) >= 100 else history:
            nums = json.loads(d['numbers']) if isinstance(d['numbers'], str) else d.get('numbers', [])
            if nums:
                acs.append(self.engine.analyzer.calculate_ac_value(nums))
                max_gaps.append(self.calculate_max_gap(nums))
        
        if not acs: 
            return {'ac_avg': 8, 'ac_std': 1, 'max_gap_avg': 15, 'max_gap_std': 3}
            
        return {
            'ac_avg': np.mean(acs), 
            'ac_std': np.std(acs),
            'max_gap_avg': np.mean(max_gaps),
            'max_gap_std': np.std(max_gaps)
        }


    def predict_3bets(self, history=None):
        if history is None: 
            history = self.get_history()
        else:
            # Ensure ASC order (oldest at 0) for stable sorting
            history = sorted(list(history), key=lambda x: str(x.get('date', '')).replace('/', '-'))
        
        regime = self.detect_regime(history)
        stats = self._get_structural_stats(history)
        exposure = self._get_exposure_counts(history)
        pruned_numbers = set([n for n, c in exposure.items() if c >= 3])

        # 1. Pool Generation: Consolidated Consensus
        votes = self._get_consensus_scores(history)
        triplets = self._get_resonant_triplets(history)
        
        triplet_nums = Counter()
        for t, c in triplets.items():
            for n in t: triplet_nums[n] += c
            
        pool_scores = Counter()
        for n, v in votes.items():
            if n in pruned_numbers: continue
            score = v * 5 + triplet_nums.get(n, 0) * 10
            pool_scores[n] = score
            
        top_12 = [n for n, s in pool_scores.most_common(12)]
        if len(top_12) < 12:
            extra = [n for n in range(1, 50) if n not in top_12 and n not in pruned_numbers]
            top_12.extend(extra[:(12-len(top_12))])

        # Bet 1: Consensus Prime (High consistency floor)
        final_bet1 = self.find_stable_candidate(top_12[:8], stats, regime=regime, level="STRICT")
        bet1 = {'numbers': final_bet1, 'type': 'Consensus Prime', 'strategy_id': 'DIVERSIFIED_BET_1'}

        # Shared Graph Building for GNN and Special Synergy
        self.graph.build_from_history(history, lookback=250)
        
        # Bet 2: GNN-Structural Flux + Special Synergy (Prize Reach)
        gnn_res = self.advanced.gnn_propagation_predict(history, self.rules, graph=self.graph)
        gnn_base = gnn_res['numbers']
        
        # Inject Special Synergy candidate
        special_scores = self._get_special_synergy_scores(history, graph=self.graph)
        top_specials = sorted(special_scores.items(), key=lambda x: x[1], reverse=True)
        # Avoid pruned numbers and take top candidate
        special_inject = next((n for n, s in top_specials if n not in pruned_numbers and n not in gnn_base), None)
        
        final_bet2_nums = list(gnn_base)
        if special_inject:
            # Replace the weakest GNN number with the special candidate
            final_bet2_nums[-1] = special_inject
        
        final_bet2 = self.find_stable_candidate(final_bet2_nums, stats, regime=regime, level="STRICT")
        bet2 = {'numbers': final_bet2, 'type': 'GNN-Structural Flux', 'strategy_id': 'DIVERSIFIED_BET_2'}

        # Bet 3: Entropy Outlier (Outlier Hunter for ROI Alpha)
        outlier_res = self.advanced.entropy_outlier_predict(history, self.rules)
        pool_3 = [n for n in outlier_res['numbers'] if n not in pruned_numbers]
        if len(pool_3) < 6:
            pool_3 = outlier_res['numbers']
            
        final_bet3 = self.find_stable_candidate(pool_3, stats, regime=regime, level="STRICT")
        bet3 = {'numbers': final_bet3, 'type': 'Entropy Outlier', 'strategy_id': 'DIVERSIFIED_BET_3'}

        return [bet1, bet2, bet3]

if __name__ == '__main__':
    ensemble = DiversifiedEnsemble()
    bets = ensemble.predict_3bets()
    print(json.dumps(bets, indent=2))
