# Portfolio Optimization Report
## Medium-Scale Strategy Evolution | DAILY_539 | 2026-03-15

---

## Executive Summary

Medium-scale evolutionary search (200 pop x 50 gen, ~10K candidates) explored weighted combination, rank fusion, voting, and nonlinear reweighting of 4 validated signals (MicroFish, MidFreq, Markov, ACB). **No statistically significant improvement found over current production strategies.** All 3 McNemar head-to-head tests show p > 0.05.

---

## 1. Best 1-Bet Strategy

| Metric | Evolved | Reference (MicroFish) | Delta |
|--------|---------|----------------------|-------|
| Edge (1500p) | +5.07% | +4.47% | +0.60pp |
| z-score | 6.18 | 5.45 | +0.73 |
| Edge/NTD | 0.001014 | 0.000894 | +13.4% |
| Permutation p | 0.010 | 0.005* | — |
| 150p/500p/1500p | +8.6%/+7.4%/+5.1% | +5.9%/+6.2%/+4.5% | — |
| McNemar | a_only=25 vs b_only=16 | χ²=1.98, **p=0.1599** | NOT significant |

*Prior validated perm_p from MicroFish Phase 1

### Evolved Genome
- **Fusion**: voting
- **Nonlinear**: square
- **Gate**: signal 0 (MicroFish) at threshold
- **Weights**: MF=0.095, MidFreq=0.274, Markov=0.345, ACB=0.287

### Analysis
The evolved 1-bet strategy weights Markov and ACB most heavily, with MidFreq secondary and MicroFish gating. The +0.60pp improvement over pure MicroFish is within noise (McNemar p=0.16). The voting fusion with squared scores favors signals that put numbers in strong top-10 positions.

### Recommendation
**Do not deploy.** Improvement is not significant. Keep MicroFish_1bet as production 1-bet.

---

## 2. Best 2-Bet Portfolio

| Metric | Evolved | Reference (MF+MidFreq) | Delta |
|--------|---------|----------------------|-------|
| Edge (1500p) | +5.10% | +6.77% | **-1.67pp** |
| z-score | 4.81 | 6.38 | -1.57 |
| Edge/NTD | 0.000510 | 0.000677 | -24.7% |
| 150p/500p/1500p | +16.5%/+8.3%/+5.1% | — | — |
| McNemar | a_only=107 vs b_only=132 | χ²=2.62, **p=0.1059** | NOT significant |

### Evolved Genome
- **Fusion**: voting
- **Nonlinear**: square
- **Gate**: none
- **Weights**: MF=0.366, MidFreq=0.325, Markov=0.081, ACB=0.228

### Analysis
The evolved 2-bet **underperforms** the reference by 1.67pp. This is because signal-fusion into a single ranking produces two bets from the same combined score, losing the orthogonality benefit. The reference strategy uses **independent** signals (MicroFish top-5 || MidFreq top-5 with exclusion), which captures more complementary coverage.

### Recommendation
**Do not deploy.** Reference is superior. The experiment confirms that **independent signal selection with exclusion > fused ranking** for multi-bet strategies.

---

## 3. Best 3-Bet Portfolio

| Metric | Evolved | Reference (MF+MidFreq+Markov) | Delta |
|--------|---------|-------------------------------|-------|
| Edge (1500p) | +8.96% | +8.29% | +0.67pp |
| z-score | 7.54 | 6.98 | +0.56 |
| Edge/NTD | 0.000597 | 0.000553 | +8.0% |
| 150p/500p/1500p | +14.9%/+13.4%/+9.0% | — | — |
| McNemar | a_only=198 vs b_only=188 | χ²=0.26, **p=0.6108** | NOT significant |

### Evolved Genome
- **Fusion**: voting
- **Nonlinear**: none
- **Gate**: none
- **Weights**: MF=0.394, MidFreq=0.231, Markov=0.208, ACB=0.166

### Analysis
The evolved 3-bet shows +0.67pp improvement, but the McNemar test (p=0.61) shows this is indistinguishable from noise. With 386 discordant pairs (198 vs 188), the difference is essentially a coin flip.

### Recommendation
**Do not deploy.** Improvement is not significant.

---

## 4. Marginal Utility Curve

```
Evolved strategies:
  1-bet → 2-bet: +0.04pp marginal  (near zero — 2nd bet adds almost nothing)
  2-bet → 3-bet: +3.85pp marginal  (significant jump)

Reference strategies:
  1-bet → 2-bet: +2.30pp marginal  (meaningful)
  2-bet → 3-bet: +1.52pp marginal  (modest)
```

The evolved strategy's 2-bet marginal is essentially zero because the fused ranking produces overlapping selections. The reference strategy's independent-signal approach is fundamentally better for multi-bet.

---

## 5. Evolution Convergence Analysis

| Bet Level | Gen 0 Best | Gen 10 Best | Gen 49 Best | Converged? |
|-----------|-----------|-------------|-------------|------------|
| 1-bet | +7.27% | +8.60% | +8.94% | Yes (gen 20) |
| 2-bet | +8.84% | +11.50% | +12.17% | Yes (gen 30) |
| 3-bet | +10.22% | +14.22% | +15.22% | Yes (gen 20) |

Note: Fast-eval edges (300p) are higher than full 1500p edges due to smaller validation window. All reported final edges are 1500p walk-forward.

Evolution converged strongly by generation 20-30 across all bet levels. The population became near-homogeneous (median ≈ best), indicating the fitness landscape has a single dominant peak in the explored space.

### Dominant Genome Pattern
All 3 evolved strategies converged to **voting fusion**. This suggests that for combining these 4 signals, having each signal independently vote for its top-10 numbers (weighted by signal importance) is the most effective fusion method. Score blending, rank fusion, and rank product were all inferior.

---

## 6. Key Finding: Signal Fusion vs Signal Independence

The most important result of this research is the **2-bet comparison**:

| Approach | Edge | Mechanism |
|----------|------|-----------|
| Reference MF+MidFreq 2-bet | **+6.77%** | Each signal select top-5 independently, with exclusion |
| Evolved fused 2-bet | +5.10% | Single fused ranking split into 2 bets |

**Independent signal selection with orthogonal exclusion dominates fused ranking** for multi-bet portfolios. This is because:

1. Each signal captures different aspects of the distribution (deficit vs mean-reversion vs transition)
2. Fusion into a single ranking loses the complementary coverage
3. Orthogonal exclusion forces diversity, which fused ranking cannot guarantee

This validates the current production architecture of **independent signals with sequential exclusion**.

---

## 7. Final Recommendations

| Item | Recommendation |
|------|---------------|
| 1-bet production | **Keep MicroFish** (evolved +0.60pp is not significant) |
| 2-bet production | **Keep MF+MidFreq** (evolved is worse) |
| 3-bet production | **Keep MF+MidFreq+Markov** (evolved +0.67pp is not significant) |
| Signal fusion | Voting is best fusion type, but independent signals remain superior for multi-bet |
| Further research | Not recommended — evolution converged, no significant gains found |

---

## Deliverables

| File | Content |
|------|---------|
| `tools/strategy_evolution_medium.py` | Evolution engine (Phases 1-5) |
| `evolved_strategy_population.json` | All results and metadata |
| `validated_evolved_strategies.json` | Validated strategies with comparisons |
| `portfolio_optimization_report.md` | This report |

---

*Generated by Medium-Scale Strategy Evolution Engine v2 | 2026-03-15 | 734s computation*
