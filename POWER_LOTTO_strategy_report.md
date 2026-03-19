# POWER_LOTTO Strategy Transfer Report

Generated: 2026-03-16 10:01

## Game Parameters
- Pool: 38 numbers, pick 6
- Match threshold: M3+
- Cost per bet: 100 NTD

## Phase 2: Signal Benchmark (Single Bet)

| Signal | Full Edge | z-score | 150p | 500p | 1500p | 3-Win | Perm p | Verdict |
|--------|-----------|---------|------|------|-------|-------|--------|---------|
| acb | -0.385% | -0.821 | -0.536 | -0.47000000000000003 | -0.40299999999999997 | FAIL | 0.68 | NO_SIGNAL |
| midfreq | +1.269% | 2.707 | -0.536 |  2.13 | 0.997 | FAIL | 0.02 | SIGNAL_DETECTED |
| markov | +0.029% | 0.061 | 1.464 |  0.33 | -0.27 | FAIL | 0.59 | NO_SIGNAL |
| fourier | +1.033% | 2.203 |  0.13 |  0.33 |  1.13 | PASS | 0.02 | SIGNAL_DETECTED |

## Phase 3: Multi-Bet Orthogonal

| N-Bet | Baseline | Rate | Edge | z-score | 3-Win | Marginal |
|-------|----------|------|------|---------|-------|----------|
| 1 | 3.870% | 5.139% | +1.269% | 2.707 | FAIL | +1.269% |
| 2 | 7.590% | 9.864% | +2.274% | 3.533 | PASS | +1.005% |
| 3 | 11.166% | 13.644% | +2.478% | 3.238 | PASS | +0.204% |
| 4 | 14.604% | 15.948% | +1.344% | 1.566 | FAIL | -1.134% |

## Phase 4: Strategy Evolution

### 1-bet Best Genome
- Edge (300p): +5.797%
- Edge (full OOS): +0.974%
- Weights: [0.418, 0.038, 0.199, 0.345]
- Fusion: weighted_rank, Nonlinear: log
- Gate: signal=2, threshold=0.38

### 2-bet Best Genome
- Edge (300p): +8.077%
- Edge (full OOS): +1.861%
- Weights: [0.63, 0.085, 0.056, 0.229]
- Fusion: weighted_rank, Nonlinear: sigmoid
- Gate: signal=1, threshold=0.60

### 3-bet Best Genome
- Edge (300p): +9.167%
- Edge (full OOS): +3.187%
- Weights: [0.223, 0.258, 0.191, 0.328]
- Fusion: score_blend, Nonlinear: none
- Gate: signal=1, threshold=0.54

## Phase 5: Strategy Space Exploration

### Efficiency Frontier
| N-Bet | Edge | Marginal | Cost | Efficiency |
|-------|------|----------|------|------------|
| 1 | +1.269% | +1.269% | 100 | 1.269 |
| 2 | +2.274% | +1.005% | 200 | 1.137 |
| 3 | +2.478% | +0.204% | 300 | 0.826 |
| 4 | +1.344% | -1.134% | 400 | 0.336 |
| 5 | -1.960% | -3.305% | 500 | -0.392 |

## Phase 6: Statistical Validation

- **midfreq_full_perm**: edge=+1.269%, p=0.01, SIGNAL_DETECTED
- **fourier_full_perm**: edge=+1.033%, p=0.0348, SIGNAL_DETECTED
- **markov_full_perm**: edge=+0.029%, p=0.6219, NO_SIGNAL
- **mcnemar_top2**: net=4, chi2=0.055, p=0.8148
- **2bet_perm**: edge=+2.274%, p=0.005, SIGNAL_DETECTED
- **3bet_perm**: edge=+2.478%, p=0.0149, SIGNAL_DETECTED

## Phase 7: Economic Reality Check

- Base EV: 54.68 NTD, ROI: -45.32%
- With best edge: EV=72.61 NTD, ROI: -27.39%

### Monte Carlo Bankroll Simulation
| Initial | Ruin Rate | Median Final | P5 Final | Max DD |
|---------|-----------|--------------|----------|--------|
| 5000 | 99.99% | 100 | 0 | 98.0% |
| 10000 | 100.0% | 100 | 0 | 99.0% |
| 50000 | 99.96% | 100 | 0 | 99.8% |
