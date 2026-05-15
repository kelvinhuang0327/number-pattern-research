# BIG_LOTTO Full Strategy Pipeline Report

Generated: 2026-03-16 14:04

## Game Parameters
- Pool: 49C6, M3+ baseline = 1.864%
- Cost: 50 NTD | Data: 2117 draws

## Phase 2: Signal Benchmark (Single Bet)

| Signal | Full Edge | z | 150p | 500p | 1500p | 3-Win | Perm p | Verdict |
|--------|-----------|---|------|------|-------|-------|--------|---------|
| acb | +0.303% | 0.95 | -1.86% | +0.34% | +0.40% | FAIL | 0.06 | MARGINAL |
| midfreq | +0.081% | 0.25 | +0.80% | +0.74% | -0.06% | FAIL | 0.4 | NO_SIGNAL |
| markov | +0.192% | 0.60 | +0.80% | +0.54% | +0.14% | PASS | 0.42 | NO_SIGNAL |
| fourier | +0.414% | 1.30 | +2.14% | +0.54% | +0.54% | PASS | 0.14 | NO_SIGNAL |
| regime | +0.081% | 0.25 | -1.86% | +0.34% | +0.14% | FAIL | 0.27 | NO_SIGNAL |
| p1_neighbor | +0.081% | 0.25 | +0.14% | +0.34% | +0.00% | PASS | 0.48 | NO_SIGNAL |
| microfish | +0.303% | 0.95 | +2.80% | +3.14% | +0.34% | PASS | 0.28 | NO_SIGNAL |

### MicroFish
- Features: 33, eval_window=500p
- Evolution edge (500p): +3.136%
- Full OOS edge: +0.303%

## Phase 3: Multi-Bet Orthogonal

| N-Bet | Baseline | Rate | Edge | z | 3-Win |
|-------|----------|------|------|---|-------|
| 1 | 1.864% | 2.278% | +0.414% | 1.30 | PASS |
| 2 | 3.693% | 4.333% | +0.641% | 1.44 | PASS |
| 3 | 5.488% | 6.222% | +0.735% | 1.37 | PASS |
| 4 | 7.249% | 8.000% | +0.751% | 1.23 | PASS |
| 5 | 8.978% | 9.500% | +0.522% | 0.78 | FAIL |

## Phase 4: Strategy Evolution (500p eval)

### 1-bet
- 500p edge: +3.136%, full OOS: +0.303%
- weights: [0.381, 0.142, 0.185, 0.011, 0.01, 0.266, 0.005]
- fusion=rank_product, nl=log, gate=6
- Overfit ratio: 10.35x

### 2-bet
- 500p edge: +4.907%, full OOS: +0.585%
- weights: [0.181, 0.129, 0.178, 0.213, 0.084, 0.115, 0.102]
- fusion=voting, nl=square, gate=6
- Overfit ratio: 8.39x

### 3-bet
- 500p edge: +6.112%, full OOS: +1.179%
- weights: [0.125, 0.216, 0.098, 0.238, 0.107, 0.116, 0.099]
- fusion=voting, nl=square, gate=6
- Overfit ratio: 5.18x

## Phase 5: Efficiency Frontier

| N-Bet | Edge | Marginal | Cost | Eff |
|-------|------|----------|------|-----|
| 1 | +0.414% | +0.414% | 50 | 0.828 |
| 2 | +0.641% | +0.227% | 100 | 0.641 |
| 3 | +0.735% | +0.094% | 150 | 0.490 |
| 4 | +0.751% | +0.016% | 200 | 0.376 |
| 5 | +0.522% | -0.229% | 250 | 0.209 |

## Phase 6: Statistical Validation

- **fourier_perm200**: edge=+0.414%, p=0.1393 → NO_SIGNAL
- **acb_perm200**: edge=+0.303%, p=0.0697 → MARGINAL
- **microfish_perm200**: edge=+0.303%, p=0.2786 → NO_SIGNAL
- **mcnemar_top2**: net=2, p=0.9087
- **2bet_perm200**: edge=+0.641%, p=0.0697 → MARGINAL
- **3bet_perm200**: edge=+0.735%, p=0.1244 → NO_SIGNAL
- **mcnemar_vs_production_3bet**: net=-6, p=0.6061

## Phase 7: Economic Reality Check
- Base EV: 17.38 NTD, ROI: -65.24%
- Best edge EV: 21.24 NTD, ROI: -57.52%

- Bankroll 5000: ruin=99.96%, median_final=50
- Bankroll 10000: ruin=99.91%, median_final=50
- Bankroll 50000: ruin=97.72%, median_final=50

## Final Answers

1. **Does any signal pass statistical validation on BIG_LOTTO?**
   - **NO.** Zero signals achieve p<0.05 on 200-shuffle permutation test.
   - Best single: Fourier +0.414% (p=0.14), ACB +0.303% (p=0.06 MARGINAL)
   - MicroFish evolution: +3.14% on 500p → +0.303% full OOS (overfit ratio 10.35x)

2. **Do BIG_LOTTO-specific signals (Regime, P1_Neighbor) help?**
   - **NO.** Both show edge=+0.081%, p>0.27. Regime's sum mean-reversion and P1 neighbor pool add no value.

3. **Optimal multi-bet architecture?**
   - 1-bet Fourier is the most efficient (eff=0.828), but not significant (p=0.14)
   - 2-bet Fourier+ACB: edge=+0.641%, p=0.0697 MARGINAL
   - Marginal returns collapse after 2 bets; 5-bet turns negative
   - **No multi-bet structure reaches p<0.05**

4. **Does evolution + MicroFish discover hidden structure?**
   - **NO.** All evolution genomes suffer severe overfit (5-10x ratio even with 500p eval).
   - Best evolved 3-bet: +6.11% (500p) → +1.18% (full OOS) — consistent with L86 but worse.
   - McNemar vs ts3_regime_3bet: net=-6, p=0.606 — **no improvement over production**.

5. **Can any strategy reduce the house edge?**
   - **NO.** Base ROI = -65.24%, best strategy ROI = -57.52%.
   - Breakeven requires +3.50% edge; best validated edge is +0.414% (12% of required).
   - Monte Carlo: 97-100% bankroll ruin across all bankroll levels.

## Conclusions

- **BIG_LOTTO is the hardest game**: 49C6 pool dilutes all frequency-based signals below detection threshold
- **Current production strategies (regime_2bet, ts3_regime_3bet, p1_dev_sum5bet) remain best**: No new signal or combination improves upon them
- **Research status: EXHAUSTED** for the current signal families (ACB, MidFreq, Markov, Fourier, Regime, P1_Neighbor, MicroFish)
- **Future research**: Would require fundamentally different signal families (e.g., structural pair co-occurrence, external data sources, or pool reduction techniques)