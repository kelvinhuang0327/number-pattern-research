# Phase M — Winning Quality Integration A/B Report
**Date**: 2026-04-16 11:05:39
**Elapsed**: 170.9s
**Draws per lottery**: 300
**Permutation tests**: 10000

## Global Verdict
**CONDITIONAL_REJECT**
- Total B wins: 34 vs A wins: 38 (B ratio: 47.2%)
- Total pred changes: 398/900 (44.2%)

## DAILY_539
**Verdict**: NEUTRAL
- Popularity improved: True
- EV improved: True
- Prediction changes: 88/300 (29.3%)
- B wins: 7 vs A wins: 8
- Perm p-value: 0.9328
- McNemar: chi2=0.0714, p=0.7893

**Quality Metrics**
- Avg popularity A: 56.15
- Avg popularity B: 55.4
- Popularity delta: -0.75 (negative = less popular = better EV)
- Avg EV ratio B: 1.1313 (>1.0 = better than random)
- Avg birthday nums A: 4.02
- Avg birthday nums B: 4.0

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0622 | 0.0622 | +0.0000 | -1.5471 | -1.5471 | +0.0000 |
| W100 | 0.0155 | 0.0055 | -0.0100 | -2.3602 | -2.3702 | -0.0101 |
| W300 | 0.0488 | 0.0422 | -0.0067 | -2.1212 | -2.1265 | -0.0054 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 23 | 22 |
| 1 | 171 | 174 |
| 2 | 95 | 93 |
| 3 | 11 | 11 |

## BIG_LOTTO
**Verdict**: MARGINAL
- Popularity improved: True
- EV improved: True
- Prediction changes: 173/300 (57.7%)
- B wins: 18 vs A wins: 16
- Perm p-value: 1.0000
- McNemar: chi2=0.1, p=0.7518

**Quality Metrics**
- Avg popularity A: 52.48
- Avg popularity B: 50.54
- Popularity delta: -1.95 (negative = less popular = better EV)
- Avg EV ratio B: 1.1864 (>1.0 = better than random)
- Avg birthday nums A: 3.93
- Avg birthday nums B: 3.84

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0119 | -0.0214 | -0.0333 | -1.2361 | -1.9034 | -0.6673 |
| W100 | -0.0048 | -0.0148 | -0.0100 | -1.4912 | -1.7095 | -0.2183 |
| W300 | 0.0152 | 0.0152 | +0.0000 | -1.1954 | -0.7711 | +0.4242 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 20 | 17 |
| 1 | 151 | 156 |
| 2 | 108 | 106 |
| 3 | 21 | 20 |
| 4 | 0 | 1 |

## POWER_LOTTO
**Verdict**: REJECT
- Popularity improved: True
- EV improved: True
- Prediction changes: 137/300 (45.7%)
- B wins: 9 vs A wins: 14
- Perm p-value: 1.0000
- McNemar: chi2=0.0, p=1.0000

**Quality Metrics**
- Avg popularity A: 66.89
- Avg popularity B: 65.93
- Popularity delta: -0.96 (negative = less popular = better EV)
- Avg EV ratio B: 1.1349 (>1.0 = better than random)
- Avg birthday nums A: 4.89
- Avg birthday nums B: 4.87

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0883 | 0.0550 | -0.0333 | 0.0729 | -0.0801 | -0.1530 |
| W100 | 0.0083 | -0.0117 | -0.0200 | -0.2339 | -0.4152 | -0.1813 |
| W300 | 0.0083 | 0.0050 | -0.0033 | -0.3150 | -0.3789 | -0.0639 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 4 | 6 |
| 1 | 117 | 116 |
| 2 | 143 | 143 |
| 3 | 32 | 32 |
| 4 | 4 | 3 |
