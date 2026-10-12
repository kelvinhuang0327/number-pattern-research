import sys
import numpy as np
import time
from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.strategy_generator import (
    FrequencyStrategy, GapPressureStrategy, MarkovStrategy, CoOccurrenceStrategy, NegativeFilterStrategy
)
from evolving_strategy_engine.evaluator import quick_evaluate
import json

draws, meta = load_big_lotto_draws()

# Hardcoded best 7
existing_bets = [
    (1, 8, 28, 29, 31, 41),
    (7, 10, 17, 23, 34, 42),
    (8, 15, 22, 35, 41, 43),
    (1, 8, 20, 22, 23, 41),
    (10, 17, 19, 23, 42, 47),
    (11, 14, 19, 32, 39, 47),
    (20, 28, 29, 31, 35, 41)
]
seen = set(existing_bets)

new_strats = [
    GapPressureStrategy(1.5),
    GapPressureStrategy(2.0),
    MarkovStrategy(2, 0.4),
    MarkovStrategy(1, 0.8),
    NegativeFilterStrategy(FrequencyStrategy(50, 'hot'), 5, 20),
    CoOccurrenceStrategy(100, 2),
    CoOccurrenceStrategy(200, 3)
]

print('Hunting for more edges...', flush=True)

results = []
for s in new_strats:
    r = quick_evaluate(s, draws, n_test=100)
    nums = tuple(sorted(s.predict(draws, 6)))
    if nums not in seen:
        seen.add(nums)
        results.append((s.name, nums, r['edge_>=2']))

results.sort(key=lambda x: x[2], reverse=True)
for name, nums, edge in results[:3]:
    print(f'NEW BET: {nums} | {name} | edge: {edge:+.4f}')
