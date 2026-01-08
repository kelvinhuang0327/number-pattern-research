import numpy as np
import random
import logging
from typing import List, Dict, Callable

logger = logging.getLogger(__name__)

class GeneticWeightOptimizer:
    """
    使用遺傳算法優化集成預測權重
    """
    def __init__(self, strategies: List[str], population_size: int = 10, generations: int = 3):
        self.strategies = strategies
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = 0.1

    def _generate_random_weights(self) -> Dict[str, float]:
        weights = {s: random.random() for s in self.strategies}
        total = sum(weights.values())
        return {s: w / total for s, w in weights.items()}

    def _evaluate_fitness(self, weights: Dict[str, float], fitness_fn: Callable[[Dict[str, float]], float]) -> float:
        return fitness_fn(weights)

    def optimize(self, fitness_fn: Callable[[Dict[str, float]], float]) -> Dict[str, float]:
        """
        主優化循環
        """
        # 初始化種群
        population = [self._generate_random_weights() for _ in range(self.population_size)]
        
        for gen in range(self.generations):
            # 評估適應度
            fitness_scores = [self._evaluate_fitness(p, fitness_fn) for p in population]
            
            # 選擇精英
            elite_indices = np.argsort(fitness_scores)[-2:]
            elites = [population[i] for i in elite_indices]
            
            new_population = list(elites)
            
            # 交叉與變異
            while len(new_population) < self.population_size:
                parent1, parent2 = random.sample(elites, 2)
                
                # 交叉
                child = {}
                for s in self.strategies:
                    child[s] = parent1[s] if random.random() > 0.5 else parent2[s]
                
                # 變異
                if random.random() < self.mutation_rate:
                    s_to_mutate = random.choice(self.strategies)
                    child[s_to_mutate] *= random.uniform(0.5, 1.5)
                
                # 正規化
                total = sum(child.values())
                child = {s: w / (total + 1e-10) for s, w in child.items()}
                new_population.append(child)
            
            population = new_population
            logger.info(f"Genetic Generation {gen+1}/{self.generations} completed. Best fitness: {max(fitness_scores):.4f}")
            
        # 返回最終最佳組合
        final_scores = [self._evaluate_fitness(p, fitness_fn) for p in population]
        return population[np.argmax(final_scores)]
