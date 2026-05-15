# DAILY_539 H011 Weekday / Calendar Regime Research (2026-04-22)

**Verdict:** REJECT

## Summary

- Formal leakage checker: PASS (`tools/verify_no_data_leakage.py` -> `analysis/results/daily539_h011_weekday_no_leakage_20260422.txt`)
- Exploratory weekday screen: global chi-square p=0.9281, Bonferroni survivors=0.
- Decision rule applied: any window edge <= 0, permutation p >= 0.05, Cohen's d <= 1.0, or marginal efficiency < 80% blocks promotion.

## Candidate Results

### Weekday residual 1-bet — REJECT

- Incumbent comparator: `acb_1bet`
- Why not RSM: at least one window edge <= 0; permutation p-value failed in at least one window; Cohen's d <= 1.0 in at least one window

| Window | Edge | Sharpe | Perm p | Cohen's d | Hit rate | ROI | M2+/M3+/M4+/M5 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | -3.40% | -0.125 | 0.9602 | -1.472 | 8.00% | -85.33% | 12/2/0/0 |
| 500 | -1.60% | -0.054 | 0.7861 | -0.711 | 9.80% | -85.20% | 49/5/0/0 |
| 1500 | -0.27% | -0.008 | 0.7313 | -0.551 | 11.13% | -84.87% | 167/12/0/0 |

| Window | McNemar p vs incumbent | Net discordant wins |
|---:|---:|---:|
| 150 | 0.2632 | -6 |
| 500 | 0.0544 | -20 |
| 1500 | 0.0073 | -49 |

### ACB + calendar regime overlay 2-bet — REJECT

- Incumbent comparator: `midfreq_acb_2bet`
- Why not RSM: permutation p-value failed in at least one window; Cohen's d <= 1.0 in at least one window

| Window | Edge | Sharpe | Perm p | Cohen's d | Hit rate | ROI | M2+/M3+/M4+/M5 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | +1.13% | 0.027 | 0.8507 | -0.859 | 22.67% | -86.67% | 34/1/0/0 |
| 500 | +3.46% | 0.080 | 0.3134 | 0.601 | 25.00% | -82.20% | 125/10/0/0 |
| 1500 | +2.99% | 0.070 | 0.0149 | 2.162 | 24.53% | -83.00% | 368/27/0/0 |

| Window | Bet | Cum hit rate | Incremental efficiency |
|---:|---:|---:|---:|
| 150 | 1 | 12.00% | 100.00% |
| 150 | 2 | 22.67% | 105.19% |
| 500 | 1 | 13.80% | 100.00% |
| 500 | 2 | 25.00% | 110.45% |
| 1500 | 1 | 14.40% | 100.00% |
| 1500 | 2 | 24.53% | 99.93% |

| Window | McNemar p vs incumbent | Net discordant wins |
|---:|---:|---:|
| 150 | 0.1102 | -10 |
| 500 | 0.0549 | -21 |
| 1500 | 0.0263 | -39 |

### ACB + Markov + calendar regime 3-bet — REJECT

- Incumbent comparator: `acb_markov_midfreq_3bet`
- Why not RSM: permutation p-value failed in at least one window; Cohen's d <= 1.0 in at least one window

| Window | Edge | Sharpe | Perm p | Cohen's d | Hit rate | ROI | M2+/M3+/M4+/M5 |
|---:|---:|---:|---:|---:|---:|---:|---|
| 150 | +0.83% | 0.018 | 0.8706 | -0.890 | 31.33% | -84.67% | 47/4/0/0 |
| 500 | +4.30% | 0.090 | 0.6617 | -0.402 | 34.80% | -82.33% | 174/16/0/0 |
| 1500 | +4.70% | 0.098 | 0.0149 | 2.569 | 35.20% | -64.93% | 528/46/2/0 |

| Window | Bet | Cum hit rate | Incremental efficiency |
|---:|---:|---:|---:|
| 150 | 1 | 12.00% | 100.00% |
| 150 | 2 | 22.00% | 98.62% |
| 150 | 3 | 31.33% | 104.17% |
| 500 | 1 | 13.80% | 100.00% |
| 500 | 2 | 24.00% | 100.59% |
| 500 | 3 | 34.80% | 120.54% |
| 1500 | 1 | 14.40% | 100.00% |
| 1500 | 2 | 25.60% | 110.45% |
| 1500 | 3 | 35.20% | 107.14% |

| Window | McNemar p vs incumbent | Net discordant wins |
|---:|---:|---:|
| 150 | 0.1102 | -10 |
| 500 | 0.3149 | -11 |
| 1500 | 0.1237 | -26 |

## Next Planner Recommendation

REJECT weekday/calendar overlays for DAILY_539 under current data. Next H011 branch should move to cross-draw cluster structure or pool-size regime effects, not another weekday retry. With H001-H008 already exhausted and calendar family also failing, DAILY_539 is closer to a near-exhausted signal space.

## Handoff Notes

- This round switched away from blocked/repeated POWER_LOTTO work. Do not send `fourier_rhythm_3bet` 500p OOS or `Winning Quality P2-1` back unchanged next round.
- Wiki update: applied.
