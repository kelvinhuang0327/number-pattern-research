# Phase M — Winning Quality Integration A/B Report
**Date**: 2026-04-16 11:08:42
**Elapsed**: 121.9s
**Draws per lottery**: 300
**Permutation tests**: 10000

## Global Verdict
**MARGINAL_ACCEPT**
- Total B wins: 149 vs A wins: 140 (B ratio: 51.6%)
- Total pred changes: 896/900 (99.6%)

## DAILY_539
**Verdict**: MARGINAL
- Popularity improved: True
- EV improved: True
- Prediction changes: 300/300 (100.0%)
- B wins: 52 vs A wins: 51
- Perm p-value: 1.0000
- McNemar: chi2=0.0, p=1.0000

**Quality Metrics**
- Avg popularity A: 56.15
- Avg popularity B: 45.59
- Popularity delta: -10.55 (negative = less popular = better EV)
- Avg EV ratio B: 1.1796 (>1.0 = better than random)
- Avg birthday nums A: 4.02
- Avg birthday nums B: 3.62

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0622 | -0.1045 | -0.1667 | -1.5471 | 0.1116 | +1.6587 |
| W100 | 0.0155 | -0.0145 | -0.0300 | -2.3602 | -0.0236 | +2.3365 |
| W300 | 0.0488 | 0.0455 | -0.0033 | -2.1212 | -0.1546 | +1.9666 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 23 | 22 |
| 1 | 171 | 173 |
| 2 | 95 | 92 |
| 3 | 11 | 12 |
| 4 | 0 | 1 |

## BIG_LOTTO
**Verdict**: MARGINAL
- Popularity improved: True
- EV improved: True
- Prediction changes: 298/300 (99.3%)
- B wins: 48 vs A wins: 47
- Perm p-value: 0.7405
- McNemar: chi2=0.2353, p=0.6276

**Quality Metrics**
- Avg popularity A: 52.48
- Avg popularity B: 42.34
- Popularity delta: -10.14 (negative = less popular = better EV)
- Avg EV ratio B: 1.2188 (>1.0 = better than random)
- Avg birthday nums A: 3.93
- Avg birthday nums B: 3.47

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0119 | 0.0786 | +0.0667 | -1.2361 | -0.7109 | +0.5252 |
| W100 | -0.0048 | 0.0152 | +0.0200 | -1.4912 | -1.1954 | +0.2958 |
| W300 | 0.0152 | 0.0052 | -0.0100 | -1.1954 | -0.8222 | +0.3732 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 20 | 12 |
| 1 | 151 | 163 |
| 2 | 108 | 107 |
| 3 | 21 | 17 |
| 4 | 0 | 1 |

## POWER_LOTTO
**Verdict**: MARGINAL
- Popularity improved: True
- EV improved: True
- Prediction changes: 298/300 (99.3%)
- B wins: 49 vs A wins: 42
- Perm p-value: 0.6349
- McNemar: chi2=0.5517, p=0.4576

**Quality Metrics**
- Avg popularity A: 66.89
- Avg popularity B: 59.51
- Popularity delta: -7.39 (negative = less popular = better EV)
- Avg EV ratio B: 1.1624 (>1.0 = better than random)
- Avg birthday nums A: 4.89
- Avg birthday nums B: 4.63

| Window | A edge | B edge | Δ edge | A Sharpe | B Sharpe | Δ Sharpe |
|--------|--------|--------|--------|---------|---------|----------|
| W30 | 0.0883 | 0.0217 | -0.0667 | 0.0729 | -0.1167 | -0.1895 |
| W100 | 0.0083 | -0.0117 | -0.0200 | -0.2339 | -0.4152 | -0.1813 |
| W300 | 0.0083 | 0.0250 | +0.0167 | -0.3150 | -0.3374 | -0.0225 |

**Hit Distribution**
| Hits | A count | B count |
|------|---------|---------|
| 0 | 4 | 6 |
| 1 | 117 | 112 |
| 2 | 143 | 141 |
| 3 | 32 | 38 |
| 4 | 4 | 3 |
