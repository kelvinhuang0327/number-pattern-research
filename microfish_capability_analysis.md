# MicroFish Capability Analysis
## Phase 1 — Framework Design & Implementation Report
### 2026-03-15

---

## 1. Background

"MicroFish" does not exist as an external library, PyPI package, or third-party framework.
It was built from scratch for this project as an evolutionary strategy search engine
specifically designed to discover micro-edges in lottery prediction systems.

The design draws from:
- Genetic algorithm / evolutionary strategy literature
- The project's existing `exhaustive_lottery_research_engine.py` (19 features, 8 models)
- The `unified_lottery_research_engine.py` (14 methods, single mutation)
- DEAP (Distributed Evolutionary Algorithms in Python) API patterns
- Optuna-style hyperparameter search concepts

## 2. Architecture

```
┌──────────────────────────────────────────────────┐
│            MicroFish Engine                       │
├──────────────────────────────────────────────────┤
│ Phase 2: Feature Space Generator                  │
│   13 families → 200+ features [T, N, F] tensor    │
│   Strict temporal isolation: F[t] uses [0..t-1]   │
├──────────────────────────────────────────────────┤
│ Phase 3: Evolutionary Search                      │
│   Population: 200, Generations: 50                │
│   Genome = {feature_indices[], weights[]}          │
│   Mutation: swap/add/remove/perturb               │
│   Crossover: uniform feature, blended weights     │
│   Selection: tournament (k=5)                     │
│   Elite preservation: top 10%                     │
├──────────────────────────────────────────────────┤
│ Phase 4: Statistical Validator                    │
│   3-window: 150/500/1500 periods                  │
│   Permutation: 200 shuffles                       │
│   Gate: all_positive AND perm_p < 0.05            │
├──────────────────────────────────────────────────┤
│ Phase 5: Micro-Edge Scanner                       │
│   Single-feature exhaustive scan                  │
│   Lift threshold: >= 1.02                         │
├──────────────────────────────────────────────────┤
│ Phase 6: Combination Tester                       │
│   Pair exhaustive: C(top_12, 2) = 66 combos       │
│   Triple exhaustive: C(top_8, 3) = 56 combos      │
│   Best combo validated with perm test             │
└──────────────────────────────────────────────────┘
```

## 3. Search Mechanisms

### Genome Representation
- `features: int[]` — indices into the 200+ feature space
- `weights: float[]` — normalized to sum=1
- Genome size: 2-8 features (bounded complexity)

### Fitness Function
- M2+ hit rate on 1500-period walk-forward evaluation
- Score = F[t, :, features].dot(weights) → top-5 numbers
- Binary hit: predicted & actual >= 2 numbers

### Selection
- Tournament selection (k=5) from top 50% of population
- Parents selected independently for crossover

### Reproduction
- **Crossover (60%)**: Uniform feature selection from union of parents + weight blending
- **Mutation only (40%)**: Copy parent + mutate

### Mutation Operators
| Operator | Probability | Effect |
|----------|------------|--------|
| Feature removal | 30% | Drop random feature, renormalize weights |
| Feature addition | 20% | Add random new feature with exponential weight |
| Feature swap | 25% | Replace one feature with random alternative |
| Weight perturbation | 25% | Gaussian noise σ=0.12 on weights |

### Elite Preservation
- Top 10% (20 individuals) survive unchanged each generation
- Prevents loss of best solutions

## 4. Feature Space (Phase 2)

### Feature Families

| Family | Count | Description |
|--------|-------|-------------|
| freq | 27 | Raw/deficit/z-score × 9 windows |
| gap | 27 | Current/ratio/pressure × 9 windows |
| parity | 18 | Even rate/boost × 9 windows |
| zone | 27 | Deficit/entropy/concentration × 9 windows |
| sum | 18 | Mean/z-score × 9 windows |
| tail | 18 | Deficit/entropy × 9 windows |
| consec | 9 | Neighbor hit × 9 windows |
| markov | 9 | Lag 1/2/3 × window 30/100/300 |
| fourier | 3 | Frequency/amplitude/phase alignment |
| entropy | 18 | Binary/inverted × 9 windows |
| ac | 3 | AC mean × 3 windows |
| ix (interaction) | 20 | Product of base feature pairs |
| nl (nonlinear) | 24 | log/sqrt/sq/tanh of 6 base features |

**Total: ~220 features**

### Temporal Isolation
- All features at time t computed using data [0..t-1] exclusively
- No future data leakage
- Walk-forward evaluation only

## 5. Evaluation Pipeline

```
For each time step t in [eval_start, eval_end):
  1. Extract features F[t, :, selected_features]  → [39, K]
  2. Compute scores = F[t, :, fi].dot(weights)    → [39]
  3. Select top-5 numbers by score
  4. Compare with actual draw numbers
  5. Record M2+ hit (match >= 2)

Fitness = sum(hits) / total_steps
Baseline = 11.40% (hypergeometric M2+ for 5/39)
Edge = fitness - baseline
```

### Validation Gates
| Gate | Criterion | Purpose |
|------|-----------|---------|
| S1: Three-window | edge > 0 at 150/500/1500p | Stability |
| S2: Permutation | p < 0.05 (200 shuffles) | Signal vs noise |
| S3: All positive | 3/3 windows positive | Consistency |

## 6. Comparison with Existing Engines

| Dimension | MicroFish | Exhaustive Engine | Unified Engine |
|-----------|-----------|-------------------|----------------|
| Features | 220 | 19 | 14 |
| Search method | Evolutionary (200×50) | Brute-force | Single mutation |
| Candidates | 10,000 | 19+8 = 27 | 14+2 = 16 |
| Population | 200 | N/A | N/A |
| Mutation | 4 operators | 4-weight evolution | Weight blend |
| Feature combos | Automated | Manual interaction | None |
| Multi-bet | No | No | Yes (2-3 bet) |
| Validation | perm 200 + 3-window | perm 300 + Bonferroni | perm 40 + binomial |
| ML models | None (linear score) | 6 models | None |

## 7. Known Limitations

1. **Single-bet only**: Does not optimize multi-bet portfolios
2. **Linear aggregation**: Features combined via weighted sum, no nonlinear models
3. **Bounded genome**: Max 8 features per strategy
4. **Fixed feature pool**: No automated feature construction
5. **No regime awareness**: Static feature selection across all market conditions
6. **Limited population**: 200 individuals × 50 generations = 10,000 evaluations
7. **No gradient information**: Evolutionary search is gradient-free

## 8. Expected Outcomes

Based on information-theoretic analysis of lottery systems:
- Lottery draws are designed to be independent and uniformly distributed
- True edge (if any) is extremely small (< 3-5% above baseline)
- MicroFish is expected to confirm whether the current system is near the ceiling
- Discovery of novel signals is possible but unlikely to exceed current ACB edge significantly
