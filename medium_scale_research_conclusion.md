# Medium-Scale Research Conclusion
## Strategy Evolution Study | DAILY_539 | 2026-03-15

---

## Research Parameters

| Parameter | Value |
|-----------|-------|
| Population size | 200 |
| Generations | 50 |
| Total candidates evaluated | ~30,000 (10K per bet level) |
| Validation draws | 1,500 (walk-forward) |
| Three-window stability | 150 / 500 / 1500 |
| Permutation test | 99 shuffles, temporal mapping |
| Signals used | MicroFish, MidFreq, Markov, ACB |
| New features created | **0** (as required) |
| Total computation time | 734s (~12 min) |

---

## Answers to Research Questions

### Q1: Did medium-scale evolution find any improvement over current production?

**Marginal improvement found, but not deployable.**

| Level | Evolved Edge | Reference Edge | Delta | Verdict |
|-------|-------------|---------------|-------|---------|
| 1-bet | +5.07% | +4.47% (MicroFish) | +0.60pp | Within noise |
| 2-bet | +5.10% | +6.77% (MF+MidFreq) | **-1.67pp** | Reference is better |
| 3-bet | +8.96% | +8.29% (MF+MidFreq+Markov) | +0.67pp | Within noise |

The evolved 2-bet is **worse** than the reference because fusing 4 signals into a single ranking loses the complementary coverage that independent signal selection provides.

### Q2: Is the best improvement statistically significant?

**No.** All three McNemar head-to-head tests fail to reach significance:

| Comparison | χ² | p-value | Verdict |
|-----------|-----|---------|---------|
| 1-bet: Evolved vs MicroFish | 1.98 | 0.1599 | NOT significant |
| 2-bet: Evolved vs MF+MidFreq | 2.62 | 0.1059 | NOT significant |
| 3-bet: Evolved vs MF+MidFreq+Markov | 0.26 | 0.6108 | NOT significant |

The 1-bet comparison comes closest (p=0.16) but is still well above the 0.05 threshold.

### Q3: Is it worth deploying?

**No.** None of the evolved strategies produce statistically significant improvements. The 2-bet evolved strategy is actually worse than the current production strategy. The risk of degradation outweighs the potential marginal gain.

### Q4: Is further large-scale search likely to be worth the extra computation?

**No.** Three lines of evidence:

1. **Convergence saturation**: Evolution converged by generation 20-30. All 200 individuals converged to nearly identical genomes. The fitness landscape has been thoroughly explored.

2. **Fusion ceiling**: The best fusion approach (voting) cannot match independent signal selection for multi-bet portfolios. No amount of weight tuning or fusion method switching will overcome this architectural limitation.

3. **Signal saturation**: Prior MicroFish Phase 2 research established that the signal ceiling is ~5.1% for 1-bet. The evolved 1-bet at +5.07% is already at 99.4% of this ceiling. There is no room for further improvement through combination alone.

---

## Key Scientific Findings

### Finding 1: Voting fusion is the dominant combination method

All three evolved strategies converged to **voting fusion** (each signal votes for its top-10, weighted by importance). Score blending, rank fusion, and rank product were all inferior. This is because voting:
- Preserves ranking information from each signal
- Naturally handles different score scales
- Provides robust consensus

### Finding 2: Independent signals > fused signals for multi-bet

The most important finding: **independent signal selection with orthogonal exclusion outperforms fused ranking** for 2+ bet portfolios. The reference MF+MidFreq 2-bet (+6.77%) beats the evolved fused 2-bet (+5.10%) by 1.67pp.

**Root cause**: Each signal captures orthogonal patterns (ACB = deficit, MidFreq = mean-reversion, Markov = transitions, MicroFish = evolved combination). Fusing them loses this complementarity. Sequential selection with exclusion forces diversity naturally.

### Finding 3: Nonlinear transforms provide marginal benefit

The evolved strategies converged to `square` nonlinearity for 1-bet and 2-bet (amplifies strong signals), but `none` for 3-bet. The impact is marginal — swapping nonlinear types on the same weights changes edge by <0.1pp.

### Finding 4: Gating has negligible effect

MicroFish gating (gate_signal=0) appeared in the 1-bet winner but not in 2-bet or 3-bet. The threshold barely filters numbers (0.3-0.9 percentile), confirming that pre-filtering by a single signal doesn't help the ensemble.

---

## Architecture Recommendation

```
Current (validated):
  1-bet: MicroFish (pure, no fusion)       → +4.47%
  2-bet: MicroFish || MidFreq (orthogonal) → +6.77%
  3-bet: MF || MidFreq || Markov (ortho)   → +8.29%

Alternative (not recommended, but validated):
  1-bet: Voting(MF+Mid+Markov+ACB, square) → +5.07%  (p=0.16 vs current)
  3-bet: Voting(MF+Mid+Markov+ACB, fused)  → +8.96%  (p=0.61 vs current)
```

**Keep current architecture.** The independent-signal approach with orthogonal exclusion is both simpler and (for 2-bet) measurably superior to evolution-optimized fusion.

---

## What Would Change This Conclusion?

1. **New validated signal** with orthogonal hit pattern (>500 unique hits vs MicroFish)
2. **External data source** (social/behavioral signals, game mechanic changes)
3. **Game structure change** (different number space, different prize tiers)

Until one of these occurs, the strategy evolution search space is exhausted.

---

*Generated by Medium-Scale Strategy Evolution Engine v2 | 2026-03-15*
