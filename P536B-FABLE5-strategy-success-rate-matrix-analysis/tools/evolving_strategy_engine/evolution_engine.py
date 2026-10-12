"""
Evolution Engine - 策略族群演化系統
淘汰、突變、重組、進化 - M3+ 嚴格驗證與統計檢驗版
"""
import numpy as np
import sys
from typing import List, Dict, Tuple, Optional
from .strategy_base import BaseStrategy, StrategyResult
from .strategy_generator import (
    generate_seed_population, WeightedEnsembleStrategy, NegativeFilterStrategy
)
from .evaluator import StrategyEvaluator, quick_evaluate
from .data_loader import load_big_lotto_draws
import json, os, time
from datetime import datetime


def _print(msg):
    """Flush print to avoid buffering"""
    print(msg, flush=True)


class EvolutionEngine:
    """自我演化引擎"""
    
    def __init__(self, draws=None, meta=None, seed=42):
        if draws is None:
            draws, meta = load_big_lotto_draws()
        self.draws = draws
        self.meta = meta
        self.rng = np.random.default_rng(seed)
        self.evaluator = StrategyEvaluator(draws, meta)
        
        self.population: List[BaseStrategy] = []
        self.results: List[StrategyResult] = []
        self.hall_of_fame: List[StrategyResult] = []
        self.graveyard: List[str] = []
        self.generation = 0
        self.history: List[Dict] = []
        # Need to store raw hits array for permutation tests later
        self.hof_hits_array = {}
    
    def initialize(self, pop_size=80):
        _print(f"[Gen 0] Generating seed population (n={pop_size})...")
        self.population = generate_seed_population(self.rng, pop_size)
        _print(f"[Gen 0] Created {len(self.population)} strategies")
    
    def evaluate_population(self, quick=True, n_test=1500):
        _print(f"[Gen {self.generation}] Evaluating {len(self.population)} strategies...")
        self.results = []
        
        for i, strat in enumerate(self.population):
            try:
                metrics = quick_evaluate(strat, self.draws, n_test)
                r = StrategyResult(
                    name=strat.name, category=strat.category,
                    numbers=strat.predict(self.draws, 6),
                    confidence=0.5, features_used=[], params=strat.params,
                    generation=self.generation
                )
                r.relative_random_edge = metrics.get('edge_>=3', -1.0)
                r.short_hit = metrics.get('hit_>=3', 0.0)
                r.extreme_best = metrics.get('max_hit', 0)
                r.volatility = 0.0 # simplified out volatility to focus on hits
                r.hit_rates = {
                    '>=2': metrics.get('hit_>=2', 0),
                    '>=3': metrics.get('hit_>=3', 0),
                    'edge_>=3': metrics.get('edge_>=3', 0),
                    'leakage_flag': metrics.get('leakage_flag', False)
                }
                r.edges = {'quick_>=3_edge': metrics.get('edge_>=3', 0)}
                self.results.append(r)
                
                # store hits for possible elite
                if r.relative_random_edge > 0.001 and not r.hit_rates['leakage_flag']:
                    self.hof_hits_array[r.strategy_id] = metrics.get('hits_array', [])
                    
            except Exception as e:
                _print(f"  ! Error evaluating {strat.name}: {e}")
            
            if (i + 1) % 20 == 0:
                _print(f"  ... evaluated {i+1}/{len(self.population)}")
        
        _print(f"[Gen {self.generation}] Evaluated {len(self.results)} strategies")
    
    def select_survivors(self, keep_ratio=0.5, elite_count=5):
        if not self.results:
            return
        
        # Filter out massive leakage cheating
        valid_results = [r for r in self.results if not r.hit_rates.get('leakage_flag', False)]
        ranked = sorted(valid_results, key=lambda r: r.relative_random_edge, reverse=True)
        
        elites = ranked[:elite_count]
        for e in elites:
            if e.relative_random_edge > 0:
                self.hall_of_fame.append(e)
        
        n_keep = max(elite_count, int(len(ranked) * keep_ratio))
        survivors_results = ranked[:n_keep]
        eliminated = ranked[n_keep:] + [r for r in self.results if r.hit_rates.get('leakage_flag', False)]
        
        for e in eliminated:
            self.graveyard.append(e.name)
        
        survivor_names = set(r.name for r in survivors_results)
        self.population = [s for s in self.population if s.name in survivor_names]
        self.results = survivors_results
        
        _print(f"[Gen {self.generation}] Kept {len(self.population)}, eliminated {len(eliminated)}")
    
    def mutate_population(self, mutation_rate=0.4):
        new_strats = []
        for strat in self.population:
            if self.rng.random() < mutation_rate:
                mutant = strat.mutate(self.rng)
                mutant.category = strat.category
                new_strats.append(mutant)
        self.population.extend(new_strats)
        _print(f"[Gen {self.generation}] Created {len(new_strats)} mutants")
    
    def crossover(self, n_offspring=15):
        if len(self.population) < 2:
            return
        
        new_strats = []
        for _ in range(n_offspring):
            idx = self.rng.choice(len(self.population), 2, replace=False)
            s1, s2 = self.population[idx[0]], self.population[idx[1]]
            w = [self.rng.uniform(0.3, 0.7)]
            w.append(1.0 - w[0])
            new_strats.append(WeightedEnsembleStrategy([s1, s2], w))
        
        if len(self.population) >= 3:
            for _ in range(min(5, n_offspring // 2)):
                idx = self.rng.choice(len(self.population), 3, replace=False)
                strats = [self.population[i] for i in idx]
                w = self.rng.dirichlet([1, 1, 1]).tolist()
                new_strats.append(WeightedEnsembleStrategy(strats, w))
        
        for _ in range(min(5, n_offspring // 3)):
            base = self.rng.choice(self.population)
            new_strats.append(NegativeFilterStrategy(
                base, kill_count=self.rng.choice([3, 5, 7]),
                kill_window=self.rng.choice([20, 30, 50])
            ))
        
        self.population.extend(new_strats)
        _print(f"[Gen {self.generation}] Created {len(new_strats)} crossover offspring")
    
    def evolve_one_generation(self, quick=True, n_test=1500):
        self.generation += 1
        t0 = time.time()
        
        self.evaluate_population(quick=True, n_test=n_test)
        self.select_survivors()
        self.mutate_population()
        self.crossover()
        
        best = max(self.results, key=lambda r: r.relative_random_edge) if self.results else None
        gen_stats = {
            'generation': self.generation,
            'pop_size': len(self.population),
            'best_name': best.name if best else 'N/A',
            'best_edge': best.relative_random_edge if best else 0,
            'best_hit3': best.hit_rates.get('>=3', 0) if best else 0,
            'elapsed': time.time() - t0,
        }
        self.history.append(gen_stats)
        
        _print(f"[Gen {self.generation}] Best: {gen_stats['best_name']} "
              f"(M3+ edge={gen_stats['best_edge']:+.4f}, hit3={gen_stats['best_hit3']:.4f}) "
              f"| Pop={gen_stats['pop_size']} | {gen_stats['elapsed']:.1f}s")
        
        return gen_stats
    
    def run(self, n_generations=10, quick=True, n_test=1500, pop_size=80):
        _print("=" * 60)
        _print("  Self-Evolving Strategy Discovery Engine (Strict Mode)")
        _print("  Metric: M3+ OOS Testing with Permutation Verification")
        _print(f"  Generations: {n_generations}")
        _print("=" * 60)
        
        self.initialize(pop_size)
        
        for g in range(n_generations):
            self.evolve_one_generation(quick=True, n_test=n_test)
        
        return self.generate_report()
    
    def generate_report(self) -> Dict:
        seen = set()
        unique_hof = []
        for r in sorted(self.hall_of_fame, key=lambda x: x.relative_random_edge, reverse=True):
            if r.strategy_id not in seen:
                seen.add(r.strategy_id)
                unique_hof.append(r)
        
        # Permutation Test with Bonferroni Correction
        total_strategies = len(self.graveyard) + len(self.population)
        bonferroni_p = 0.05 / max(1, total_strategies)
        
        final_valid_hof = []
        pattern_exists = False
        why_no_pattern = "All strategies failed the P3 Permutation test or Bonferroni corrected significance threshold. No predictive edge above M3+ 1.86% baseline."
        
        for r in unique_hof:
            hits_arr = self.hof_hits_array.get(r.strategy_id, [])
            if hits_arr:
                p_val = self.evaluator.run_permutation_test(hits_arr, n_permutations=300)
                r.params['p_value'] = p_val
                if p_val < bonferroni_p:
                    pattern_exists = True
                    why_no_pattern = f"Significant pattern found! Strategy '{r.name}' passed stringent OOS and Permutation threshold (p < {bonferroni_p:.6f})."
                    final_valid_hof.append(r)
                elif p_val < 0.05:
                    final_valid_hof.append(r) # Include marginally significant for reporting, but don't declare pattern
                    
        if not final_valid_hof:
            final_valid_hof = unique_hof[:5] # at least show the top ones even if they failed p-value
            
        final_valid_hof.sort(key=lambda r: (r.params.get('p_value', 1.0), -r.relative_random_edge))
            
        report = {
            'timestamp': datetime.now().isoformat(),
            'total_draws': len(self.draws),
            'total_strategies_tested': total_strategies,
            'bonferroni_threshold': bonferroni_p,
            'generations': self.generation,
            
            '1_leaderboard': [self._result_to_dict(r) for r in final_valid_hof[:10]],
            '6_pattern_exists': pattern_exists,
            '8_why_no_pattern': why_no_pattern,
            
            'evolution_history': self.history,
        }
        
        return report
    
    def _result_to_dict(self, r: StrategyResult) -> Dict:
        return {
            'name': r.name,
            'numbers': r.numbers,
            'edge_>=3': r.relative_random_edge,
            'hit_rates': r.hit_rates,
            'extreme_best': r.extreme_best,
            'generation': r.generation,
            'params': r.params,
        }
