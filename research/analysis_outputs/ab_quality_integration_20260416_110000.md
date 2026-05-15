# Phase M — Winning Quality Integration A/B Report
**Date**: 2026-04-16 11:02:08
**Elapsed**: 127.5s
**Draws per lottery**: 300
**Permutation tests**: 10000

## Global Verdict
**MARGINAL_ACCEPT**
- Total B wins: 97 vs A wins: 97 (B ratio: 50.0%)
- Total pred changes: 818/900 (90.9%)

## DAILY_539
**Verdict**: NEUTRAL
- Popularity improved: True
- EV improved: True
- Prediction changes: 251/300 (83.7%)
- B wins: 17 vs A wins: 25
- Perm p-value: 0.5465
- McNemar: chi2=1.5312, p=0.2159

**Quality Metrics**
- Avg popularity A: 56.15
- Avg popularity B: 53.14
- Popularity delta: -3.01 (negative = less popular = better EV)
- Avg EV ratio B: 1.1425 (>1.0 = better than random)
- Avg birthday nums A: 4.02
- Avg birthday nums B: 3.91

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0622 | 0.0288 | -0.0333 | -1.5471 | -1.5652 | -0.0181 |
| W100 | 0.0155 | 0.0055 | -0.0100 | -2.3602 | -2.3702 | -0.0101 |
| W300 | 0.0488 | 0.0222 | -0.0267 | -2.1212 | -2.3536 | -0.2324 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 23 | 21 |
| 1 | 171 | 181 |
| 2 | 95 | 89 |
| 3 | 11 | 9 |

## BIG_LOTTO
**Verdict**: MARGINAL
- Popularity improved: True
- EV improved: True
- Prediction changes: 292/300 (97.3%)
- B wins: 44 vs A wins: 38
- Perm p-value: 0.7375
- McNemar: chi2=0.2667, p=0.6056

**Quality Metrics**
- Avg popularity A: 52.48
- Avg popularity B: 45.78
- Popularity delta: -6.7 (negative = less popular = better EV)
- Avg EV ratio B: 1.2051 (>1.0 = better than random)
- Avg birthday nums A: 3.93
- Avg birthday nums B: 3.64

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0119 | 0.0119 | +0.0000 | -1.2361 | -1.2361 | +0.0000 |
| W100 | -0.0048 | 0.0152 | +0.0200 | -1.4912 | -1.1954 | +0.2958 |
| W300 | 0.0152 | 0.0052 | -0.0100 | -1.1954 | -0.6255 | +0.5699 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 20 | 15 |
| 1 | 151 | 154 |
| 2 | 108 | 113 |
| 3 | 21 | 16 |
| 4 | 0 | 2 |

## POWER_LOTTO
**Verdict**: MARGINAL
- Popularity improved: True
- EV improved: True
- Prediction changes: 275/300 (91.7%)
- B wins: 36 vs A wins: 34
- Perm p-value: 1.0000
- McNemar: chi2=0.0385, p=0.8445

**Quality Metrics**
- Avg popularity A: 66.89
- Avg popularity B: 63.22
- Popularity delta: -3.68 (negative = less popular = better EV)
- Avg EV ratio B: 1.1465 (>1.0 = better than random)
- Avg birthday nums A: 4.89
- Avg birthday nums B: 4.76

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0883 | 0.0550 | -0.0333 | 0.0729 | -0.0801 | -0.1530 |
| W100 | 0.0083 | 0.0083 | +0.0000 | -0.2339 | -0.3718 | -0.1379 |
| W300 | 0.0083 | 0.0083 | +0.0000 | -0.3150 | -0.3150 | +0.0000 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 4 | 6 |
| 1 | 117 | 112 |
| 2 | 143 | 146 |
| 3 | 32 | 32 |
| 4 | 4 | 4 |
