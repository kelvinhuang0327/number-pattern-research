========================================================================
Phase K — Learning Amplification Test
Run date: 2026-04-16T10:10:49.180723
Amplification factors tested: [1.0, 2.0, 3.0]
========================================================================

## 1. Amplification Factor Comparison

Factor   | Pred Changes   | Change Rate  | B wins   A wins   B ratio  | Avg Edge Δ@300   Avg Sharpe Δ@300   Avg DD Δ@300  
------------------------------------------------------------------------------------------------------------------------
1.0      |   398/900      | 0.4422       | 135      74       0.6459   | 0.021111++++++++ 0.187762++++++++++ -25.6667++++++
2.0      |   451/900      | 0.5011       | 141      82       0.6323   | 0.022222++++++++ 0.171113++++++++++ -28.7778++++++
3.0      |   485/900      | 0.5389       | 150      85       0.6383   | 0.026666++++++++ 0.210589++++++++++ -33.7778++++++

## 2. Per-Lottery × Per-Factor Metrics

### Amplification Factor = 1.0

#### DAILY_539 (amp=1.0)
  Pred changes: 70/300 (23.3%)
  When diff: B wins=4, A wins=4, ties=62
  Bonuses (amp×1.0): avg=0.015848, max=0.021131
    W30: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=11/30, B hit=11/30)
    W100: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=32/100, B hit=32/100)
    W300: edge Δ=-0.00333  sharpe Δ=-0.00267  DD Δ=+0.3333  (A hit=107/300, B hit=106/300)
  Permutation p=1.000000
  McNemar: b01=2, b10=3, p=1.0
  Sample diff draw=114000115:
    A: [[6, 9, 10, 14, 39], [5, 12, 18, 28, 37], [1, 17, 23, 29, 33]] → hit=2
    B: [[6, 9, 10, 14, 39], [5, 12, 18, 28, 37], [17, 23, 24, 29, 33]] → hit=2

#### BIG_LOTTO (amp=1.0)
  Pred changes: 70/300 (23.3%)
  When diff: B wins=21, A wins=17, ties=32
  Bonuses (amp×1.0): avg=0.000714, max=0.000952
    W30: edge Δ=+0.03333  sharpe Δ=+0.66729  DD Δ=-3.3333  (A hit=1/30, B hit=2/30)
    W100: edge Δ=+0.01000  sharpe Δ=+0.21834  DD Δ=-2.6667  (A hit=4/100, B hit=5/100)
    W300: edge Δ=+0.00333  sharpe Δ=+0.04069  DD Δ=-2.6667  (A hit=20/300, B hit=21/300)
  Permutation p=1.000000
  McNemar: b01=3, b10=2, p=1.0
  Sample diff draw=112000099:
    A: [[8, 10, 16, 27, 33, 45], [17, 23, 24, 28, 30, 36], [1, 3, 11, 20, 26, 40]] → hit=1
    B: [[10, 16, 23, 27, 33, 45], [8, 17, 24, 28, 30, 36], [1, 3, 11, 20, 26, 40]] → hit=1

#### POWER_LOTTO (amp=1.0)
  Pred changes: 258/300 (86.0%)
  When diff: B wins=110, A wins=53, ties=95
  Bonuses (amp×1.0): avg=0.008900, max=0.011867
    W30: edge Δ=+0.06667  sharpe Δ=+0.78380  DD Δ=-12.6667  (A hit=4/30, B hit=6/30)
    W100: edge Δ=+0.06000  sharpe Δ=+1.09254  DD Δ=-29.3333  (A hit=6/100, B hit=12/100)
    W300: edge Δ=+0.06333  sharpe Δ=+0.52526  DD Δ=-74.6667  (A hit=17/300, B hit=36/300)
  Permutation p=0.008900
  McNemar: b01=31, b10=12, p=0.006052
  Sample diff draw=112000049:
    A: [[3, 4, 5, 14, 19, 29], [15, 22, 27, 28, 30, 38], [6, 9, 11, 13, 25, 34]] → hit=1
    B: [[3, 4, 5, 14, 19, 29], [15, 22, 27, 28, 30, 38], [6, 9, 11, 13, 34, 37]] → hit=1

### Amplification Factor = 2.0

#### DAILY_539 (amp=2.0)
  Pred changes: 110/300 (36.7%)
  When diff: B wins=8, A wins=7, ties=95
  Bonuses (amp×2.0): avg=0.031697, max=0.042263
    W30: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=11/30, B hit=11/30)
    W100: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=32/100, B hit=32/100)
    W300: edge Δ=+0.00000  sharpe Δ=-0.09719  DD Δ=+1.6667  (A hit=107/300, B hit=107/300)
  Permutation p=1.000000
  McNemar: b01=5, b10=5, p=0.75183
  Sample diff draw=114000109:
    A: [[6, 17, 23, 29, 38], [13, 18, 22, 32, 39], [8, 9, 14, 34, 36]] → hit=0
    B: [[6, 17, 23, 29, 38], [13, 18, 22, 32, 39], [8, 14, 25, 34, 36]] → hit=0

#### BIG_LOTTO (amp=2.0)
  Pred changes: 76/300 (25.3%)
  When diff: B wins=22, A wins=19, ties=35
  Bonuses (amp×2.0): avg=0.001429, max=0.001905
    W30: edge Δ=+0.03333  sharpe Δ=+0.66729  DD Δ=-3.3333  (A hit=1/30, B hit=2/30)
    W100: edge Δ=+0.01000  sharpe Δ=+0.21834  DD Δ=-2.6667  (A hit=4/100, B hit=5/100)
    W300: edge Δ=+0.00333  sharpe Δ=+0.04069  DD Δ=-2.6667  (A hit=20/300, B hit=21/300)
  Permutation p=1.000000
  McNemar: b01=3, b10=2, p=1.0
  Sample diff draw=112000099:
    A: [[8, 10, 16, 27, 33, 45], [17, 23, 24, 28, 30, 36], [1, 3, 11, 20, 26, 40]] → hit=1
    B: [[10, 16, 23, 27, 33, 45], [8, 17, 24, 28, 30, 36], [1, 3, 11, 20, 26, 40]] → hit=1

#### POWER_LOTTO (amp=2.0)
  Pred changes: 265/300 (88.3%)
  When diff: B wins=111, A wins=56, ties=98
  Bonuses (amp×2.0): avg=0.017800, max=0.023734
    W30: edge Δ=+0.06667  sharpe Δ=+0.78380  DD Δ=-12.6667  (A hit=4/30, B hit=6/30)
    W100: edge Δ=+0.06000  sharpe Δ=+1.09254  DD Δ=-29.3333  (A hit=6/100, B hit=12/100)
    W300: edge Δ=+0.06333  sharpe Δ=+0.56984  DD Δ=-85.3333  (A hit=17/300, B hit=36/300)
  Permutation p=0.008900
  McNemar: b01=31, b10=12, p=0.006052
  Sample diff draw=112000044:
    A: [[3, 15, 19, 22, 26, 38], [11, 27, 29, 30, 31, 36], [4, 10, 33, 34, 35, 37]] → hit=2
    B: [[3, 15, 19, 22, 26, 38], [27, 29, 30, 31, 35, 36], [4, 10, 11, 33, 34, 37]] → hit=2

### Amplification Factor = 3.0

#### DAILY_539 (amp=3.0)
  Pred changes: 132/300 (44.0%)
  When diff: B wins=11, A wins=9, ties=112
  Bonuses (amp×3.0): avg=0.047545, max=0.063394
    W30: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=11/30, B hit=11/30)
    W100: edge Δ=+0.00000  sharpe Δ=-0.44884  DD Δ=+1.6667  (A hit=32/100, B hit=32/100)
    W300: edge Δ=+0.00000  sharpe Δ=+0.00000  DD Δ=+0.0000  (A hit=107/300, B hit=107/300)
  Permutation p=1.000000
  McNemar: b01=6, b10=6, p=0.77283
  Sample diff draw=114000109:
    A: [[6, 17, 23, 29, 38], [13, 18, 22, 32, 39], [8, 9, 14, 34, 36]] → hit=0
    B: [[6, 17, 23, 29, 38], [13, 18, 22, 32, 39], [8, 14, 25, 34, 36]] → hit=0

#### BIG_LOTTO (amp=3.0)
  Pred changes: 80/300 (26.7%)
  When diff: B wins=22, A wins=19, ties=39
  Bonuses (amp×3.0): avg=0.002143, max=0.002857
    W30: edge Δ=+0.03333  sharpe Δ=+0.66729  DD Δ=-3.3333  (A hit=1/30, B hit=2/30)
    W100: edge Δ=+0.01000  sharpe Δ=+0.21834  DD Δ=-2.6667  (A hit=4/100, B hit=5/100)
    W300: edge Δ=+0.00333  sharpe Δ=+0.04069  DD Δ=-2.6667  (A hit=20/300, B hit=21/300)
  Permutation p=1.000000
  McNemar: b01=3, b10=2, p=1.0
  Sample diff draw=112000099:
    A: [[8, 10, 16, 27, 33, 45], [17, 23, 24, 28, 30, 36], [1, 3, 11, 20, 26, 40]] → hit=1
    B: [[10, 16, 23, 27, 33, 45], [8, 17, 24, 28, 30, 36], [1, 3, 11, 20, 26, 40]] → hit=1

#### POWER_LOTTO (amp=3.0)
  Pred changes: 273/300 (91.0%)
  When diff: B wins=117, A wins=57, ties=99
  Bonuses (amp×3.0): avg=0.026701, max=0.035601
    W30: edge Δ=+0.03333  sharpe Δ=+0.75735  DD Δ=-10.6667  (A hit=4/30, B hit=5/30)
    W100: edge Δ=+0.05000  sharpe Δ=+1.07781  DD Δ=-29.3333  (A hit=6/100, B hit=11/100)
    W300: edge Δ=+0.07667  sharpe Δ=+0.59107  DD Δ=-98.6667  (A hit=17/300, B hit=40/300)
  Permutation p=0.002400
  McNemar: b01=36, b10=13, p=0.001673
  Sample diff draw=112000044:
    A: [[3, 15, 19, 22, 26, 38], [11, 27, 29, 30, 31, 36], [4, 10, 33, 34, 35, 37]] → hit=2
    B: [[3, 15, 19, 22, 26, 38], [27, 29, 30, 31, 35, 36], [4, 10, 11, 33, 34, 37]] → hit=2


## 3. Over-Amplification Instability Check

⚠️  WARNINGS DETECTED:

  - amp=2.0: pred_change_rate=50.1% (>50% — over-amplification risk)
  - amp=3.0: pred_change_rate=53.9% (>50% — over-amplification risk)

## 4. Key Questions

### Q1: Is ranking actually shifting?
  amp=1.0: 398/900 predictions differ (44.2%)
  amp=2.0: 451/900 predictions differ (50.1%)
  amp=3.0: 485/900 predictions differ (53.9%)
  → YES: Higher amplification increases ranking changes.

### Q2: Does Sharpe improve further?
  amp=1.0: avg Sharpe Δ@300 = +0.187762
  amp=2.0: avg Sharpe Δ@300 = +0.171113
  amp=3.0: avg Sharpe Δ@300 = +0.210589 ← best
  → Best Sharpe at amp=3.0

### Q3: Any over-amplification instability?
  → YES: 2 warning(s) detected.

## 5. Amplification Verdict

  RECOMMEND: amp=2.0 (highest stable factor)
  REASON: amp=3.0 shows instability warnings