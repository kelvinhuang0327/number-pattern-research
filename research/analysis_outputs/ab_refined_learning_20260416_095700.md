========================================================================
Phase J — A/B Validation: Refined Learning vs Baseline
Run date: 2026-04-16T09:57:00.819547
========================================================================

## 1. Executive Summary

Verdict: **CONDITIONAL_ACCEPT**
Reason: Composite score positive: edge +0/-2, Sharpe +3/-0, DD improved 3/9. When bets differ: B wins 13 vs A wins 7. 140/900 prediction changes.
Windows tested: 9
  Edge: +0 / -2
  Sharpe: +3 / -0
  DD improved: 3/9
  Composite: +6 / -2
  Significant: False
Total prediction changes: 140/900 draws
When bets differ: B wins 13 vs A wins 7

## 2. A/B Metrics Table

### DAILY_539 (3-bet)

Window     | A edge       B edge       Δ edge       | A sharpe     B sharpe     Δ sharpe     | A DD     B DD     Δ DD    
-------------------------------------------------------------------------------------------------------------------------
30         | +0.06217     +0.06217     +0.00000     | -1.54715     -1.54715     +0.00000     | 23.0000   23.0000   +0.0000
100        | +0.01551     +0.01551     +0.00000     | -2.36016     -2.36016     +0.00000     | 84.3333   84.3333   +0.0000
300        | +0.05217     +0.04884     -0.00333     | -2.11849     -2.12116     -0.00267     | 246.0000   246.3333   +0.3333

  Hit rates:
    30: A=0.3667 (11/30) B=0.3667 (11/30) baseline=0.3045
    100: A=0.3200 (32/100) B=0.3200 (32/100) baseline=0.3045
    300: A=0.3567 (107/300) B=0.3533 (106/300) baseline=0.3045

  Permutation p-value: 1.000000
  McNemar: chi2=0.0, p=1.0, b01(A_miss→B_hit)=2, b10(A_hit→B_miss)=3
### BIG_LOTTO (3-bet)

Window     | A edge       B edge       Δ edge       | A sharpe     B sharpe     Δ sharpe     | A DD     B DD     Δ DD    
-------------------------------------------------------------------------------------------------------------------------
30         | +0.01190     +0.01190     +0.00000     | -1.23608     -1.23608     +0.00000     | 23.6667   23.6667   +0.0000
100        | -0.00477     -0.00477     +0.00000     | -1.49120     -1.49120     +0.00000     | 88.3333   88.3333   +0.0000
300        | +0.01523     +0.01523     +0.00000     | -1.19539     -1.19539     +0.00000     | 243.0000   243.0000   +0.0000

  Hit rates:
    30: A=0.0667 (2/30) B=0.0667 (2/30) baseline=0.0548
    100: A=0.0500 (5/100) B=0.0500 (5/100) baseline=0.0548
    300: A=0.0700 (21/300) B=0.0700 (21/300) baseline=0.0548

  Permutation p-value: 1.000000
  McNemar: chi2=0, p=1.0, b01(A_miss→B_hit)=0, b10(A_hit→B_miss)=0
### POWER_LOTTO (3-bet)

Window     | A edge       B edge       Δ edge       | A sharpe     B sharpe     Δ sharpe     | A DD     B DD     Δ DD    
-------------------------------------------------------------------------------------------------------------------------
30         | +0.08833     +0.08833     +0.00000     | -0.43750     +0.07287     +0.51038     | 15.6667   9.0000   -6.6667
100        | +0.01834     +0.00834     -0.01000     | -0.72851     -0.23385     +0.49466     | 64.3333   53.6667   -10.6666
300        | +0.00834     +0.00834     +0.00000     | -0.56613     -0.31497     +0.25116     | 192.3333   168.3333   -24.0000

  Hit rates:
    30: A=0.2000 (6/30) B=0.2000 (6/30) baseline=0.1117
    100: A=0.1300 (13/100) B=0.1200 (12/100) baseline=0.1117
    300: A=0.1200 (36/300) B=0.1200 (36/300) baseline=0.1117

  Permutation p-value: 1.000000
  McNemar: chi2=0.25, p=0.617075, b01(A_miss→B_hit)=2, b10(A_hit→B_miss)=2

## 3. Δ Analysis

### DAILY_539
  Prediction changes: 70/300 (23.33%)
  When different: A wins=4, B wins=4, ties=62
### BIG_LOTTO
  Prediction changes: 21/300 (7.0%)
  When different: A wins=1, B wins=1, ties=19
### POWER_LOTTO
  Prediction changes: 49/300 (16.33%)
  When different: A wins=2, B wins=8, ties=39

## 4. Learning Behavior Audit

### DAILY_539
  Draws tested: 300
  Prediction change rate: 0.2333
  Avg bonus magnitude: 0.015848
  Max bonus magnitude: 0.021131
  Bonuses applied: {'consensus_signal': 0.021131, 'midfreq': 0.01937, 'weibull_gap': 0.017609, 'acb': 0.015848, 'fourier': 0.014088, 'markov': 0.012327, 'markov2': 0.010566}
  Sample diff draw=114000115:
    A: [[6, 9, 10, 14, 39], [5, 12, 18, 28, 37], [1, 17, 23, 29, 33]] → hit=2
    B: [[6, 9, 10, 14, 39], [5, 12, 18, 28, 37], [17, 23, 24, 29, 33]] → hit=2
### BIG_LOTTO
  Draws tested: 300
  Prediction change rate: 0.0700
  Avg bonus magnitude: 0.000714
  Max bonus magnitude: 0.000952
  Bonuses applied: {'cold': 0.000952, 'neighbor': 0.000873, 'weibull_gap': 0.000794, 'fourier': 0.000714, 'markov': 0.000635, 'markov2': 0.000556, 'consensus_signal': 0.000476}
  Sample diff draw=112000099:
    A: [[8, 10, 16, 27, 33, 45], [17, 23, 24, 28, 30, 36], [1, 3, 11, 20, 26, 40]] → hit=1
    B: [[10, 16, 23, 27, 33, 45], [8, 17, 24, 28, 30, 36], [1, 3, 11, 20, 26, 40]] → hit=1
### POWER_LOTTO
  Draws tested: 300
  Prediction change rate: 0.1633
  Avg bonus magnitude: 0.008900
  Max bonus magnitude: 0.011867
  Bonuses applied: {'fourier': -0.011867, 'markov': -0.01068, 'markov2': -0.009494, 'consensus_signal': -0.008307, 'cold': -0.00712, 'weibull_gap': -0.005933}
  Sample diff draw=112000049:
    A: [[3, 4, 5, 14, 19, 29], [15, 22, 27, 28, 30, 38], [6, 9, 11, 13, 25, 34]] → hit=1
    B: [[3, 4, 5, 14, 19, 29], [15, 22, 27, 28, 30, 38], [6, 9, 11, 13, 34, 37]] → hit=1

## 5. Final Verdict

  CONDITIONAL_ACCEPT
  Composite score positive: edge +0/-2, Sharpe +3/-0, DD improved 3/9. When bets differ: B wins 13 vs A wins 7. 140/900 prediction changes.