# Phase V — Full Strategy Validation Report

Generated: 2026-04-16 17:53:58

---

## DAILY_539

- Total strategies: 6
- VALIDATED: 5
- WATCH: 1
- REJECTED: 0

### Validation Results

| Strategy | n_bets | edge_150p | edge_500p | edge_1500p | perm_p | mcnemar_p | sharpe | status |
|----------|--------|-----------|-----------|------------|--------|-----------|--------|--------|
| acb_1bet | 1 | +1.93% | +2.45% | +2.60% | 0.0007 | 0.1482 | 0.075 | WATCH |
| midfreq_acb_2bet | 2 | +7.79% | +6.15% | +4.95% | 0.0000 | 0.0092 | 0.112 | VALIDATED |
| acb_markov_fourier_3bet | 3 | +5.83% | +4.58% | +5.99% | 0.0000 | 0.0016 | 0.124 | VALIDATED |
| acb_markov_midfreq_3bet | 3 | +7.83% | +5.19% | +6.35% | 0.0000 | 0.0008 | 0.132 | VALIDATED |
| f4cold_3bet | 3 | +2.50% | +5.96% | +4.71% | 0.0000 | 0.0168 | 0.099 | VALIDATED |
| f4cold_5bet | 5 | +10.28% | +10.61% | +8.61% | 0.0000 | 0.0000 | 0.173 | VALIDATED |

### Best Strategy Per Bet Count (New Composite Logic)

| n_bets | strategy | validated_status | composite | edge_1500p | warning |
|--------|----------|-----------------|-----------|------------|---------|
| 1 | acb_1bet | WATCH | 0.0349 | +2.60% | NOT_FULLY_VALIDATED — best available WATCH strategy |
| 2 | midfreq_acb_2bet | VALIDATED | 0.0575 | +4.95% | — |
| 3 | acb_markov_midfreq_3bet | VALIDATED | 0.0705 | +6.35% | — |
| 5 | f4cold_5bet | VALIDATED | 0.0936 | +8.61% | — |

## BIG_LOTTO

- Total strategies: 10
- VALIDATED: 1
- WATCH: 9
- REJECTED: 0

### Validation Results

| Strategy | n_bets | edge_150p | edge_500p | edge_1500p | perm_p | mcnemar_p | sharpe | status |
|----------|--------|-----------|-----------|------------|--------|-----------|--------|--------|
| fourier_rhythm_2bet | 2 | +2.31% | +0.92% | +1.10% | 0.0131 | 0.2650 | 0.051 | WATCH |
| p1_neighbor_cold_2bet | 2 | +1.64% | +0.92% | +1.22% | 0.0069 | 0.2016 | 0.056 | WATCH |
| regime_2bet | 2 | +2.98% | +1.39% | +1.28% | 0.0049 | 0.1747 | 0.059 | WATCH |
| echo_aware_3bet | 3 | +2.51% | +2.05% | +0.93% | 0.0169 | 0.4320 | 0.038 | WATCH |
| triple_strike_3bet | 3 | +2.84% | +1.28% | +1.00% | 0.0262 | 0.3724 | 0.040 | WATCH |
| ts3_regime_3bet | 3 | +3.18% | +1.59% | +1.12% | 0.0153 | 0.3033 | 0.045 | WATCH |
| p1_deviation_4bet | 4 | +3.42% | +2.14% | +2.33% | 0.0003 | 0.0253 | 0.079 | VALIDATED |
| ts3_markov_4bet_w30 | 4 | +2.08% | +1.83% | +1.17% | 0.0388 | 0.2581 | 0.042 | WATCH |
| p1_dev_sum5bet | 5 | +4.71% | +3.19% | +2.74% | 0.0001 | 0.0634 | 0.085 | WATCH |
| ts3_markov_freq_5bet_w30 | 5 | +1.71% | +1.96% | +1.40% | 0.0273 | 0.5154 | 0.046 | WATCH |

### Best Strategy Per Bet Count (New Composite Logic)

| n_bets | strategy | validated_status | composite | edge_1500p | warning |
|--------|----------|-----------------|-----------|------------|---------|
| 2 | regime_2bet | WATCH | 0.0234 | +1.28% | NOT_FULLY_VALIDATED — best available WATCH strategy |
| 3 | ts3_regime_3bet | WATCH | 0.0182 | +1.12% | NOT_FULLY_VALIDATED — best available WATCH strategy |
| 4 | p1_deviation_4bet | VALIDATED | 0.0343 | +2.33% | — |
| 5 | p1_dev_sum5bet | WATCH | 0.0386 | +2.74% | NOT_FULLY_VALIDATED — best available WATCH strategy |

## POWER_LOTTO

- Total strategies: 7
- VALIDATED: 0
- WATCH: 7
- REJECTED: 0

### Validation Results

| Strategy | n_bets | edge_150p | edge_500p | edge_1500p | perm_p | mcnemar_p | sharpe | status |
|----------|--------|-----------|-----------|------------|--------|-----------|--------|--------|
| fourier30_markov30_2bet | 2 | +0.41% | -0.97% | +0.23% | 0.3762 | 0.2183 | 0.009 | WATCH |
| fourier_rhythm_2bet | 2 | +0.08% | +1.80% | +1.26% | 0.0319 | 0.3125 | 0.044 | WATCH |
| midfreq_fourier_2bet | 2 | +0.08% | +2.56% | +1.86% | 0.0032 | 0.1075 | 0.064 | WATCH |
| fourier_rhythm_3bet | 3 | +0.50% | +1.91% | +2.10% | 0.0045 | 0.2684 | 0.062 | WATCH |
| midfreq_fourier_mk_3bet | 3 | +2.16% | +3.29% | +2.59% | 0.0007 | 0.1285 | 0.075 | WATCH |
| pp3_freqort_4bet | 4 | +2.40% | +3.40% | +2.67% | 0.0014 | 0.2386 | 0.071 | WATCH |
| orthogonal_5bet | 5 | +2.76% | +2.86% | +3.48% | 0.0002 | 0.1548 | 0.085 | WATCH |

### Best Strategy Per Bet Count (New Composite Logic)

| n_bets | strategy | validated_status | composite | edge_1500p | warning |
|--------|----------|-----------------|-----------|------------|---------|
| 2 | midfreq_fourier_2bet | WATCH | 0.0279 | +1.86% | NOT_FULLY_VALIDATED — best available WATCH strategy |
| 3 | midfreq_fourier_mk_3bet | WATCH | 0.0347 | +2.59% | NOT_FULLY_VALIDATED — best available WATCH strategy |
| 4 | pp3_freqort_4bet | WATCH | 0.0338 | +2.67% | NOT_FULLY_VALIDATED — best available WATCH strategy |
| 5 | orthogonal_5bet | WATCH | 0.0419 | +3.48% | NOT_FULLY_VALIDATED — best available WATCH strategy |