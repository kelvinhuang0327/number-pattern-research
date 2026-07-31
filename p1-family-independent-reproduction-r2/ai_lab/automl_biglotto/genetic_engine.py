"""
Phase 2: 未知方法探索引擎
Genetic Programming + Random Formula Generator + Strategy Crossover
"""
import copy
import random
import numpy as np
from typing import List, Dict, Tuple, Callable, Optional
from collections import Counter

from .config import (MAX_NUM, PICK, SEED, GP_POPULATION, GP_GENERATIONS,
                     GP_TOURNAMENT_SIZE, GP_CROSSOVER_RATE, GP_MUTATION_RATE,
                     GP_ELITISM_RATE, GP_MAX_DEPTH, FEATURE_NAMES, NUM_FEATURES,
                     n_bet_baseline, MIN_HISTORY)
from .feature_library import FeatureLibrary


# ============================================================
# GP Tree Nodes
# ============================================================
class GPNode:
    """GP 表達式樹節點"""
    pass


class OperatorNode(GPNode):
    """算子節點"""
    BINARY_OPS = ['ADD', 'SUB', 'MUL', 'DIV', 'MAX', 'MIN']
    UNARY_OPS = ['ABS', 'NEG', 'SQRT', 'LOG', 'SQUARE']

    def __init__(self, op: str, children: list):
        self.op = op
        self.children = children

    def evaluate(self, features: np.ndarray) -> float:
        if self.op in self.BINARY_OPS:
            a = self.children[0].evaluate(features)
            b = self.children[1].evaluate(features)
            if self.op == 'ADD':
                return a + b
            elif self.op == 'SUB':
                return a - b
            elif self.op == 'MUL':
                return a * b
            elif self.op == 'DIV':
                return a / (b + 1e-10) if abs(b) > 1e-10 else 0
            elif self.op == 'MAX':
                return max(a, b)
            elif self.op == 'MIN':
                return min(a, b)
        else:
            a = self.children[0].evaluate(features)
            if self.op == 'ABS':
                return abs(a)
            elif self.op == 'NEG':
                return -a
            elif self.op == 'SQRT':
                return np.sqrt(abs(a))
            elif self.op == 'LOG':
                return np.log(abs(a) + 1e-10)
            elif self.op == 'SQUARE':
                return min(a * a, 1e6)
        return 0

    def depth(self) -> int:
        return 1 + max(c.depth() for c in self.children)

    def size(self) -> int:
        return 1 + sum(c.size() for c in self.children)

    def to_string(self) -> str:
        if self.op in self.BINARY_OPS:
            return f"({self.children[0].to_string()} {self.op} {self.children[1].to_string()})"
        return f"{self.op}({self.children[0].to_string()})"

    def clone(self):
        return OperatorNode(self.op, [c.clone() for c in self.children])


class FeatureNode(GPNode):
    """特徵引用節點"""
    def __init__(self, feature_idx: int):
        self.feature_idx = feature_idx

    def evaluate(self, features: np.ndarray) -> float:
        if self.feature_idx < len(features):
            return float(features[self.feature_idx])
        return 0

    def depth(self) -> int:
        return 1

    def size(self) -> int:
        return 1

    def to_string(self) -> str:
        if self.feature_idx < len(FEATURE_NAMES):
            return FEATURE_NAMES[self.feature_idx]
        return f"f{self.feature_idx}"

    def clone(self):
        return FeatureNode(self.feature_idx)


class ConstantNode(GPNode):
    """常數節點"""
    def __init__(self, value: float):
        self.value = value

    def evaluate(self, features: np.ndarray) -> float:
        return self.value

    def depth(self) -> int:
        return 1

    def size(self) -> int:
        return 1

    def to_string(self) -> str:
        return f"{self.value:.2f}"

    def clone(self):
        return ConstantNode(self.value)


# ============================================================
# GP Tree Generation
# ============================================================
def random_tree(max_depth: int, method: str = 'grow', rng=None) -> GPNode:
    """生成隨機 GP 樹"""
    if rng is None:
        rng = np.random.RandomState()

    if max_depth <= 1 or (method == 'grow' and rng.random() < 0.4):
        # Terminal
        if rng.random() < 0.7:
            return FeatureNode(rng.randint(0, NUM_FEATURES))
        else:
            return ConstantNode(float(rng.uniform(-2, 2)))

    # Operator
    if rng.random() < 0.7:
        op = rng.choice(OperatorNode.BINARY_OPS)
        return OperatorNode(op, [
            random_tree(max_depth - 1, method, rng),
            random_tree(max_depth - 1, method, rng)
        ])
    else:
        op = rng.choice(OperatorNode.UNARY_OPS)
        return OperatorNode(op, [random_tree(max_depth - 1, method, rng)])


def get_all_nodes(tree: GPNode) -> List[Tuple[GPNode, GPNode, int]]:
    """取得所有節點及其父節點"""
    result = []

    def _walk(node, parent, child_idx):
        result.append((node, parent, child_idx))
        if isinstance(node, OperatorNode):
            for i, c in enumerate(node.children):
                _walk(c, node, i)

    _walk(tree, None, -1)
    return result


# ============================================================
# Genetic Engine
# ============================================================
class GeneticEngine:
    """Phase 2: GP 演化 + 隨機公式生成器"""

    def __init__(self, feature_library: FeatureLibrary,
                 all_draws: List[Dict],
                 config: dict = None):
        self.features = feature_library
        self.all_draws = all_draws
        cfg = config or {}
        self.pop_size = cfg.get('population', GP_POPULATION)
        self.generations = cfg.get('generations', GP_GENERATIONS)
        self.max_depth = cfg.get('max_depth', GP_MAX_DEPTH)
        self.tournament_size = cfg.get('tournament_size', GP_TOURNAMENT_SIZE)
        self.crossover_rate = cfg.get('crossover_rate', GP_CROSSOVER_RATE)
        self.mutation_rate = cfg.get('mutation_rate', GP_MUTATION_RATE)
        self.elitism_rate = cfg.get('elitism_rate', GP_ELITISM_RATE)

    def evolve(self, test_periods: int = 150, seed: int = SEED,
               verbose: bool = True) -> List[Dict]:
        """
        GP 演化主迴圈
        回傳 top formulas 列表 [{tree, formula, train_edge, test_edge, depth}]
        """
        rng = np.random.RandomState(seed)
        random.seed(seed)

        # 分割訓練/驗證
        total = len(self.all_draws) - MIN_HISTORY
        train_end = MIN_HISTORY + int(total * 0.6)
        test_start = train_end
        train_periods = min(test_periods, train_end - MIN_HISTORY)
        test_periods_actual = min(test_periods, len(self.all_draws) - test_start)

        if train_periods <= 0 or test_periods_actual <= 0:
            return []

        # 初始化群體
        population = self._init_population(rng)

        best_ever = []

        for gen in range(self.generations):
            # 評估適應度
            fitnesses = []
            for tree in population:
                train_edge = self._evaluate_tree(tree, 0, train_end, train_periods)
                test_edge = self._evaluate_tree(tree, test_start,
                                                len(self.all_draws), test_periods_actual)
                depth = tree.depth()
                fitness = min(train_edge, test_edge) - 0.001 * depth
                fitnesses.append({
                    'fitness': fitness,
                    'train_edge': train_edge,
                    'test_edge': test_edge,
                    'depth': depth,
                })

            # 排序
            ranked = sorted(zip(population, fitnesses),
                           key=lambda x: -x[1]['fitness'])

            # 記錄最佳
            top = ranked[0]
            if top[1]['train_edge'] > 0 and top[1]['test_edge'] > 0:
                best_ever.append({
                    'tree': top[0].clone(),
                    'formula': top[0].to_string(),
                    'train_edge': top[1]['train_edge'],
                    'test_edge': top[1]['test_edge'],
                    'depth': top[1]['depth'],
                    'generation': gen,
                })

            if verbose and gen % 10 == 0:
                print(f"  GP Gen {gen:>3}/{self.generations}: "
                      f"best_fit={top[1]['fitness']:.4f} "
                      f"train={top[1]['train_edge']*100:+.2f}% "
                      f"test={top[1]['test_edge']*100:+.2f}% "
                      f"depth={top[1]['depth']}")

            # 新世代
            n_elite = max(1, int(self.pop_size * self.elitism_rate))
            new_pop = [t.clone() for t, _ in ranked[:n_elite]]

            while len(new_pop) < self.pop_size:
                if rng.random() < self.crossover_rate:
                    p1 = self._tournament_select(population, fitnesses, rng)
                    p2 = self._tournament_select(population, fitnesses, rng)
                    child = self._crossover(p1, p2, rng)
                else:
                    parent = self._tournament_select(population, fitnesses, rng)
                    child = parent.clone()

                if rng.random() < self.mutation_rate:
                    child = self._mutate(child, rng)

                if child.depth() <= self.max_depth:
                    new_pop.append(child)

            population = new_pop[:self.pop_size]

        # 回傳 top 20（雙半都正的）
        valid = [b for b in best_ever if b['train_edge'] > 0 and b['test_edge'] > 0]
        valid.sort(key=lambda x: -min(x['train_edge'], x['test_edge']))
        # 去重（by formula string）
        seen = set()
        unique = []
        for b in valid:
            if b['formula'] not in seen:
                seen.add(b['formula'])
                unique.append(b)
        return unique[:20]

    def random_linear_formulas(self, n_formulas: int = 500,
                               test_periods: int = 150,
                               seed: int = SEED,
                               verbose: bool = True) -> List[Dict]:
        """隨機線性公式生成器"""
        rng = np.random.RandomState(seed)

        total = len(self.all_draws) - MIN_HISTORY
        train_end = MIN_HISTORY + int(total * 0.6)
        test_start = train_end
        train_periods = min(test_periods, train_end - MIN_HISTORY)
        test_periods_actual = min(test_periods, len(self.all_draws) - test_start)

        results = []
        for i in range(n_formulas):
            # 隨機選 5-10 個特徵
            n_feat = rng.randint(3, 10)
            feat_indices = rng.choice(NUM_FEATURES, size=n_feat, replace=False)
            weights = rng.uniform(-2, 2, size=n_feat)

            # 建構 tree
            tree = self._build_linear_tree(feat_indices, weights)

            train_edge = self._evaluate_tree(tree, 0, train_end, train_periods)
            test_edge = self._evaluate_tree(tree, test_start,
                                            len(self.all_draws), test_periods_actual)

            if train_edge > 0 and test_edge > 0:
                results.append({
                    'tree': tree,
                    'formula': tree.to_string(),
                    'train_edge': train_edge,
                    'test_edge': test_edge,
                    'depth': tree.depth(),
                    'origin': 'random_linear',
                })

            if verbose and (i + 1) % 100 == 0:
                print(f"  Random Linear: {i+1}/{n_formulas}, "
                      f"valid={len(results)}")

        results.sort(key=lambda x: -min(x['train_edge'], x['test_edge']))
        return results[:20]

    def tree_to_strategy(self, tree: GPNode) -> Callable:
        """將 GP 樹轉換為策略函數"""
        feature_lib = self.features

        def strategy(history):
            feat_matrix = feature_lib.extract_all(history)  # (49, n_features)
            scores = {}
            for num in range(1, MAX_NUM + 1):
                try:
                    scores[num] = tree.evaluate(feat_matrix[num - 1])
                except Exception:
                    scores[num] = 0
            ranked = sorted(scores.items(), key=lambda x: -x[1])
            return [sorted([n for n, _ in ranked[:PICK]])]

        return strategy

    def _evaluate_tree(self, tree: GPNode, start_idx: int, end_idx: int,
                       test_periods: int) -> float:
        """在指定範圍內評估 GP 樹的 edge"""
        feature_lib = self.features
        draws = self.all_draws[start_idx:end_idx]
        test_periods = min(test_periods, len(draws) - 50)
        if test_periods <= 0:
            return 0.0

        m3_count = 0
        total = 0

        for i in range(test_periods):
            target_idx = len(draws) - test_periods + i
            if target_idx <= 0:
                continue

            hist = self.all_draws[:start_idx + target_idx]
            target = draws[target_idx]

            if len(hist) < 50:
                continue

            try:
                feat_matrix = feature_lib.extract_all(hist)
                scores = {}
                for num in range(1, MAX_NUM + 1):
                    scores[num] = tree.evaluate(feat_matrix[num - 1])

                ranked = sorted(scores.items(), key=lambda x: -x[1])
                bet = sorted([n for n, _ in ranked[:PICK]])
                actual = set(target['numbers'][:PICK])
                mc = len(set(bet) & actual)
                if mc >= 3:
                    m3_count += 1
                total += 1
            except Exception:
                continue

        if total == 0:
            return 0.0

        m3_rate = m3_count / total
        baseline = n_bet_baseline(1)
        return m3_rate - baseline

    def _init_population(self, rng) -> List[GPNode]:
        """Ramped half-and-half 初始化"""
        pop = []
        for i in range(self.pop_size):
            depth = 2 + (i % (self.max_depth - 1))
            method = 'full' if i % 2 == 0 else 'grow'
            tree = random_tree(depth, method, rng)
            pop.append(tree)
        return pop

    def _tournament_select(self, population, fitnesses, rng) -> GPNode:
        """錦標賽選擇"""
        indices = rng.choice(len(population), size=min(self.tournament_size, len(population)),
                            replace=False)
        best_idx = max(indices, key=lambda i: fitnesses[i]['fitness'])
        return population[best_idx].clone()

    def _crossover(self, p1: GPNode, p2: GPNode, rng) -> GPNode:
        """子樹交叉"""
        child = p1.clone()
        nodes1 = get_all_nodes(child)
        nodes2 = get_all_nodes(p2)

        if len(nodes1) < 2 or len(nodes2) < 2:
            return child

        # 隨機選擇交叉點
        _, parent1, idx1 = nodes1[rng.randint(1, len(nodes1))]
        node2, _, _ = nodes2[rng.randint(0, len(nodes2))]

        if parent1 is not None and isinstance(parent1, OperatorNode):
            parent1.children[idx1] = node2.clone()

        return child

    def _mutate(self, tree: GPNode, rng) -> GPNode:
        """變異"""
        nodes = get_all_nodes(tree)
        if len(nodes) < 2:
            return tree

        idx = rng.randint(1, len(nodes))
        node, parent, child_idx = nodes[idx]

        if parent is not None and isinstance(parent, OperatorNode):
            # 子樹替換
            new_subtree = random_tree(3, 'grow', rng)
            parent.children[child_idx] = new_subtree

        return tree

    def _build_linear_tree(self, feat_indices, weights) -> GPNode:
        """建構線性組合的 GP 樹"""
        # score = w1*f1 + w2*f2 + ...
        terms = []
        for fi, w in zip(feat_indices, weights):
            term = OperatorNode('MUL', [
                ConstantNode(float(w)),
                FeatureNode(int(fi))
            ])
            terms.append(term)

        if len(terms) == 0:
            return ConstantNode(0)
        elif len(terms) == 1:
            return terms[0]

        tree = terms[0]
        for t in terms[1:]:
            tree = OperatorNode('ADD', [tree, t])
        return tree
