# Phase L — Learning → Decision Integration A/B Report
**Date**: 2026-04-16 10:24:41
**Elapsed**: 126.2s
**Draws per lottery**: 300
**Permutation tests**: 10000

## Global Verdict
**CONDITIONAL_REJECT**
- Total B wins: 10 vs A wins: 60 (B ratio: 14.3%)
- Total pred changes: 391/900 (43.4%)

## DAILY_539
**Verdict**: INSUFFICIENT_DATA
- Learning score: 0.007924
- Amp factor: 0.5
- Adjusted confidence: 0.5008
- Concentration top_n: 14
- Prediction changes: 70/300 (23.3%)
- B wins: 4 vs A wins: 4
- N-bets changes: 0
- Perm p-value: 1.0000
- McNemar: chi2=0.0, p=1.0000

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0622 | 0.0622 | +0.0000 | -1.5471 | -1.5471 | +0.0000 |
| W100 | 0.0155 | 0.0155 | +0.0000 | -2.3602 | -2.3602 | +0.0000 |
| W300 | 0.0522 | 0.0488 | -0.0033 | -2.1185 | -2.1212 | -0.0027 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 24 | 23 |
| 1 | 169 | 171 |
| 2 | 96 | 95 |
| 3 | 11 | 11 |

**Applied Bonuses**
- acb: +0.015848
- consensus_signal: +0.021131
- fourier: +0.014088
- markov: +0.012327
- markov2: +0.010566
- midfreq: +0.019370
- weibull_gap: +0.017609

## BIG_LOTTO
**Verdict**: INSUFFICIENT_DATA
- Learning score: 0.002143
- Amp factor: 3.0
- Adjusted confidence: 0.5
- Concentration top_n: 15
- Prediction changes: 21/300 (7.0%)
- B wins: 1 vs A wins: 1
- N-bets changes: 0
- Perm p-value: 1.0000
- McNemar: chi2=0, p=1.0000

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0119 | 0.0119 | +0.0000 | -1.2361 | -1.2361 | +0.0000 |
| W100 | -0.0048 | -0.0048 | +0.0000 | -1.4912 | -1.4912 | +0.0000 |
| W300 | 0.0152 | 0.0152 | +0.0000 | -1.1954 | -1.1954 | +0.0000 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 20 | 20 |
| 1 | 151 | 151 |
| 2 | 108 | 108 |
| 3 | 21 | 21 |

**Applied Bonuses**
- cold: +0.000952
- consensus_signal: +0.000476
- fourier: +0.000714
- markov: +0.000635
- markov2: +0.000556
- neighbor: +0.000873
- weibull_gap: +0.000794

## POWER_LOTTO
**Verdict**: REJECT
- Learning score: -0.0178
- Amp factor: 2.0
- Adjusted confidence: 0.4982
- Concentration top_n: 17
- Prediction changes: 300/300 (100.0%)
- B wins: 5 vs A wins: 55
- N-bets changes: 300
- Perm p-value: 0.0741
- McNemar: chi2=10.5625, p=0.0012

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0883 | 0.0550 | -0.0333 | -0.4375 | -0.0801 | +0.3574 |
| W100 | 0.0183 | -0.0317 | -0.0500 | -0.7285 | -0.4613 | +0.2672 |
| W300 | 0.0083 | -0.0383 | -0.0467 | -0.5661 | -0.4773 | +0.0888 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 5 | 18 |
| 1 | 118 | 148 |
| 2 | 141 | 112 |
| 3 | 35 | 19 |
| 4 | 1 | 3 |

**Applied Bonuses**
- cold: -0.007120
- consensus_signal: -0.008307
- fourier: -0.011867
- markov: -0.010680
- markov2: -0.009494
- weibull_gap: -0.005933
