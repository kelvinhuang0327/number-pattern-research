========================================================================
Phase K — Learning Amplification Test
Run date: 2026-04-16T15:48:05.846012
Amplification factors tested: [1.0, 2.0, 3.0]
========================================================================

## 1. Amplification Factor Comparison

Factor   | Pred Changes   | Change Rate  | B wins   A wins   B ratio  | Avg Edge Δ@300   Avg Sharpe Δ@300   Avg DD Δ@300  
------------------------------------------------------------------------------------------------------------------------
1.0      |   378/900      | 0.4200       | 146      61       0.7053   | 0.028889++++++++ 0.341292++++++++++ -33.8889++++++
2.0      |   447/900      | 0.4967       | 150      64       0.7009   | 0.030000++++++++ 0.321168++++++++++ -32.5556++++++
3.0      |   498/900      | 0.5533       | 152      64       0.7037   | 0.025556++++++++ 0.337171++++++++++ -33.3333++++++

## 2. Per-Lottery × Per-Factor Metrics

### Amplification Factor = 1.0

#### DAILY_539 (amp=1.0)
  Pred changes: 56/300 (18.7%)
  When diff: B wins=7, A wins=2, ties=47
  Bonuses (amp×1.0): avg=0.015848, max=0.021131
    W30: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=6/30, B hit=6/30)
    W100: edge Δ=+0.00000  sharpe Δ=+0.00755  DD Δ=-5.0000  (A hit=29/100, B hit=29/100)
    W300: edge Δ=+0.00000  sharpe Δ=+0.00595  DD Δ=-6.6666  (A hit=105/300, B hit=105/300)
  Permutation p=1.000000
  McNemar: b01=2, b10=2, p=0.617075
  Sample diff draw=114000114:
    A: [[17, 18, 31, 37, 39], [10, 14, 23, 25, 35], [6, 12, 15, 16, 32]] → hit=0
    B: [[17, 18, 31, 37, 39], [10, 14, 23, 25, 35], [5, 6, 12, 16, 32]] → hit=0

#### BIG_LOTTO (amp=1.0)
  Pred changes: 63/300 (21.0%)
  When diff: B wins=26, A wins=16, ties=21
  Bonuses (amp×1.0): avg=0.000714, max=0.000952
    W30: edge Δ=+0.10000  sharpe Δ=+1.19246  DD Δ=-8.0000  (A hit=1/30, B hit=4/30)
    W100: edge Δ=+0.04000  sharpe Δ=+0.82704  DD Δ=-10.0000  (A hit=3/100, B hit=7/100)
    W300: edge Δ=+0.01333  sharpe Δ=+0.07574  DD Δ=-10.0000  (A hit=14/300, B hit=18/300)
  Permutation p=0.584400
  McNemar: b01=6, b10=2, p=0.288844
  Sample diff draw=112000105:
    A: [[2, 15, 21, 30, 35, 46], [10, 16, 23, 27, 31, 48], [7, 8, 14, 24, 32, 33]] → hit=2
    B: [[2, 15, 21, 30, 35, 46], [10, 16, 23, 27, 31, 33], [7, 8, 14, 24, 32, 48]] → hit=2

#### POWER_LOTTO (amp=1.0)
  Pred changes: 259/300 (86.3%)
  When diff: B wins=113, A wins=43, ties=103
  Bonuses (amp×1.0): avg=0.008900, max=0.011867
    W30: edge Δ=-0.03333  sharpe Δ=+0.44235  DD Δ=-5.6667  (A hit=5/30, B hit=4/30)
    W100: edge Δ=+0.03000  sharpe Δ=+0.78022  DD Δ=-13.0000  (A hit=7/100, B hit=10/100)
    W300: edge Δ=+0.07333  sharpe Δ=+0.94218  DD Δ=-85.0000  (A hit=19/300, B hit=41/300)
  Permutation p=0.003800
  McNemar: b01=32, b10=10, p=0.001194
  Sample diff draw=112000051:
    A: [[3, 15, 18, 22, 25, 38], [11, 14, 19, 33, 35, 36], [4, 5, 13, 26, 29, 30]] → hit=1
    B: [[3, 15, 19, 22, 25, 38], [11, 14, 18, 33, 35, 36], [4, 5, 13, 26, 29, 30]] → hit=1

### Amplification Factor = 2.0

#### DAILY_539 (amp=2.0)
  Pred changes: 105/300 (35.0%)
  When diff: B wins=10, A wins=4, ties=91
  Bonuses (amp×2.0): avg=0.031697, max=0.042263
    W30: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=6/30, B hit=6/30)
    W100: edge Δ=+0.00000  sharpe Δ=+0.00755  DD Δ=-5.0000  (A hit=29/100, B hit=29/100)
    W300: edge Δ=+0.00000  sharpe Δ=+0.00744  DD Δ=-8.3333  (A hit=105/300, B hit=105/300)
  Permutation p=1.000000
  McNemar: b01=4, b10=4, p=0.723674
  Sample diff draw=114000112:
    A: [[9, 12, 22, 28, 36], [14, 17, 23, 25, 38], [29, 30, 31, 34, 37]] → hit=2
    B: [[9, 12, 22, 28, 36], [14, 17, 23, 25, 38], [20, 30, 31, 34, 37]] → hit=2

#### BIG_LOTTO (amp=2.0)
  Pred changes: 74/300 (24.7%)
  When diff: B wins=27, A wins=16, ties=31
  Bonuses (amp×2.0): avg=0.001429, max=0.001905
    W30: edge Δ=+0.10000  sharpe Δ=+1.19246  DD Δ=-8.0000  (A hit=1/30, B hit=4/30)
    W100: edge Δ=+0.04000  sharpe Δ=+0.82704  DD Δ=-10.0000  (A hit=3/100, B hit=7/100)
    W300: edge Δ=+0.01333  sharpe Δ=+0.07574  DD Δ=-10.0000  (A hit=14/300, B hit=18/300)
  Permutation p=0.586700
  McNemar: b01=7, b10=3, p=0.342782
  Sample diff draw=112000105:
    A: [[2, 15, 21, 30, 35, 46], [10, 16, 23, 27, 31, 48], [7, 8, 14, 24, 32, 33]] → hit=2
    B: [[2, 15, 21, 30, 35, 46], [10, 16, 23, 27, 31, 33], [7, 8, 14, 24, 32, 48]] → hit=2

#### POWER_LOTTO (amp=2.0)
  Pred changes: 268/300 (89.3%)
  When diff: B wins=113, A wins=44, ties=111
  Bonuses (amp×2.0): avg=0.017800, max=0.023734
    W30: edge Δ=-0.03333  sharpe Δ=+0.44235  DD Δ=-5.3333  (A hit=5/30, B hit=4/30)
    W100: edge Δ=+0.05000  sharpe Δ=+0.82359  DD Δ=-20.6666  (A hit=7/100, B hit=12/100)
    W300: edge Δ=+0.07667  sharpe Δ=+0.88032  DD Δ=-79.3334  (A hit=19/300, B hit=42/300)
  Permutation p=0.002600
  McNemar: b01=33, b10=10, p=0.000794
  Sample diff draw=112000044:
    A: [[3, 15, 19, 22, 26, 38], [27, 29, 30, 31, 35, 36], [4, 11, 12, 33, 34, 37]] → hit=2
    B: [[3, 15, 19, 22, 26, 38], [27, 29, 30, 31, 35, 36], [4, 10, 11, 33, 34, 37]] → hit=2

### Amplification Factor = 3.0

#### DAILY_539 (amp=3.0)
  Pred changes: 138/300 (46.0%)
  When diff: B wins=9, A wins=4, ties=125
  Bonuses (amp×3.0): avg=0.047545, max=0.063394
    W30: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=6/30, B hit=6/30)
    W100: edge Δ=+0.00000  sharpe Δ=+0.00755  DD Δ=-5.0000  (A hit=29/100, B hit=29/100)
    W300: edge Δ=-0.00333  sharpe Δ=+0.00715  DD Δ=-8.0000  (A hit=105/300, B hit=104/300)
  Permutation p=1.000000
  McNemar: b01=3, b10=4, p=1.0
  Sample diff draw=114000110:
    A: [[17, 25, 29, 32, 38], [9, 16, 22, 23, 34], [6, 11, 14, 36, 39]] → hit=1
    B: [[17, 25, 29, 32, 38], [9, 16, 22, 23, 34], [6, 11, 14, 18, 39]] → hit=1

#### BIG_LOTTO (amp=3.0)
  Pred changes: 81/300 (27.0%)
  When diff: B wins=28, A wins=16, ties=37
  Bonuses (amp×3.0): avg=0.002143, max=0.002857
    W30: edge Δ=+0.10000  sharpe Δ=+1.19246  DD Δ=-8.0000  (A hit=1/30, B hit=4/30)
    W100: edge Δ=+0.04000  sharpe Δ=+0.82704  DD Δ=-10.0000  (A hit=3/100, B hit=7/100)
    W300: edge Δ=+0.01333  sharpe Δ=+0.07574  DD Δ=-10.0000  (A hit=14/300, B hit=18/300)
  Permutation p=0.586700
  McNemar: b01=7, b10=3, p=0.342782
  Sample diff draw=112000105:
    A: [[2, 15, 21, 30, 35, 46], [10, 16, 23, 27, 31, 48], [7, 8, 14, 24, 32, 33]] → hit=2
    B: [[2, 15, 21, 30, 35, 46], [10, 16, 23, 27, 31, 33], [7, 8, 14, 24, 32, 48]] → hit=2

#### POWER_LOTTO (amp=3.0)
  Pred changes: 279/300 (93.0%)
  When diff: B wins=115, A wins=44, ties=120
  Bonuses (amp×3.0): avg=0.026701, max=0.035601
    W30: edge Δ=-0.03333  sharpe Δ=+0.44235  DD Δ=-5.3333  (A hit=5/30, B hit=4/30)
    W100: edge Δ=+0.04000  sharpe Δ=+0.94681  DD Δ=-28.6666  (A hit=7/100, B hit=11/100)
    W300: edge Δ=+0.06667  sharpe Δ=+0.92862  DD Δ=-82.0000  (A hit=19/300, B hit=39/300)
  Permutation p=0.008300
  McNemar: b01=32, b10=12, p=0.004179
  Sample diff draw=112000044:
    A: [[3, 15, 19, 22, 26, 38], [27, 29, 30, 31, 35, 36], [4, 11, 12, 33, 34, 37]] → hit=2
    B: [[3, 15, 19, 22, 26, 38], [27, 29, 30, 31, 35, 36], [4, 10, 11, 33, 34, 37]] → hit=2


## 3. Over-Amplification Instability Check

⚠️  WARNINGS DETECTED:

  - amp=3.0: pred_change_rate=55.3% (>50% — over-amplification risk)

## 4. Key Questions

### Q1: Is ranking actually shifting?
  amp=1.0: 378/900 predictions differ (42.0%)
  amp=2.0: 447/900 predictions differ (49.7%)
  amp=3.0: 498/900 predictions differ (55.3%)
  → YES: Higher amplification increases ranking changes.

### Q2: Does Sharpe improve further?
  amp=1.0: avg Sharpe Δ@300 = +0.341292 ← best
  amp=2.0: avg Sharpe Δ@300 = +0.321168
  amp=3.0: avg Sharpe Δ@300 = +0.337171
  → Best Sharpe at amp=1.0

### Q3: Any over-amplification instability?
  → YES: 1 warning(s) detected.

## 5. Amplification Verdict

  RECOMMEND: amp=1.0
  REASON: Best composite score (Sharpe Δ=+0.341292, B ratio=70.5%, Edge Δ=+0.028889)