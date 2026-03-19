# Cross-Game Strategy Transfer Comparison

Generated: 2026-03-16

## Signal Transfer Results

| Signal | 539 Edge | BIG_LOTTO Edge | BIG_LOTTO Verdict | POWER_LOTTO Edge | POWER_LOTTO Verdict |
|--------|----------|----------------|-------------------|------------------|---------------------|
| acb | +3.27% | +0.247% | MARGINAL (p=0.085) | -0.385% | NO_SIGNAL (p=0.680) |
| midfreq | +5.06% | +0.081% | NO_SIGNAL (p=0.400) | **+1.269%** | **SIGNAL_DETECTED (p=0.010)** |
| markov | ~0 | +0.192% | NO_SIGNAL (p=0.388) | +0.029% | NO_SIGNAL (p=0.622) |
| fourier | ~+1% | +0.414% | NO_SIGNAL (p=0.139) | **+1.033%** | **SIGNAL_DETECTED (p=0.035)** |

## Key Findings

### BIG_LOTTO (49C6, 2117 draws)
- **Signal transfer: FAILED.** No signal achieved p<0.05 on full 200-shuffle permutation test
- ACB is MARGINAL (p=0.085) — weakest of all games; the larger pool (49 vs 39) dilutes frequency signals
- Fourier shows positive three-window (150/500/1500 all positive) but fails permutation test
- 3-bet orthogonal (Fourier+ACB+Markov) has edge=+1.07% but p=0.055 — borderline
- Strategy evolution found no robust improvement: 300p overfit collapses on full OOS (+6.5% → +0.12%)
- **Economics**: Base ROI = -65.24%, breakeven requires +3.50% M3+ edge (current best: +0.41%)
- **Monte Carlo**: 100% ruin rate at all bankroll levels (5K/10K/50K NTD over 2000 draws)

### POWER_LOTTO (38C6, 1893 draws)
- **Signal transfer: PARTIAL SUCCESS.** MidFreq and Fourier both detected (p=0.010, p=0.035)
- MidFreq is strongest single signal: +1.27% edge, z=2.71, Cohen's d=2.75
- Fourier: +1.03% edge, z=2.20, Cohen's d=1.93
- ACB **fails completely** on POWER_LOTTO: -0.39% edge — boundary/mod3 heuristics don't transfer
- Markov is noise (p=0.622)
- **2-bet MidFreq+Fourier orthogonal**: edge=+2.27%, p=0.005, three-window PASS — **VALIDATED**
- **3-bet MidFreq+Fourier+Markov**: edge=+2.48%, p=0.015, three-window PASS — **VALIDATED**
- 4-bet adds ACB which is negative — diminishing returns below marginal threshold
- Strategy evolution 3-bet: +9.17% on 300p → +3.19% full OOS — promising but needs walk-forward confirmation
- **Economics**: Base ROI = -45.32%, breakeven requires +3.21% edge (current best: +2.48%)
- **Monte Carlo**: 100% ruin rate — prize structure gap too large for M3+ edge alone

## Multi-Bet Structures

### BIG_LOTTO Best Structure
| N-Bet | Baseline | Rate | Edge | z | 3-Win | Verdict |
|-------|----------|------|------|---|-------|---------|
| 1 | 1.86% | 2.28% | +0.41% | 1.30 | PASS | MARGINAL |
| 2 | 3.69% | 4.39% | +0.70% | 1.57 | PASS | MARGINAL |
| **3** | **5.49%** | **6.56%** | **+1.07%** | **1.99** | **PASS** | **BEST** |
| 4 | 7.25% | 8.11% | +0.86% | 1.41 | FAIL | DECLINING |

Optimal: 3 bets (Fourier + ACB + Markov) — but not significant (p=0.055)

### POWER_LOTTO Best Structure
| N-Bet | Baseline | Rate | Edge | z | 3-Win | Verdict |
|-------|----------|------|------|---|-------|---------|
| 1 | 3.87% | 5.14% | +1.27% | 2.71 | FAIL | STRONG but unstable |
| **2** | **7.59%** | **9.86%** | **+2.27%** | **3.53** | **PASS** | **VALIDATED p=0.005** |
| **3** | **11.17%** | **13.64%** | **+2.48%** | **3.24** | **PASS** | **VALIDATED p=0.015** |
| 4 | 14.60% | 15.95% | +1.34% | 1.57 | FAIL | ACB drags down |

Optimal: 2-3 bets (MidFreq + Fourier ± Markov)

## Efficiency Frontier Comparison

| Game | 1-bet eff | 2-bet eff | 3-bet eff | Optimal |
|------|-----------|-----------|-----------|---------|
| 539 | ~2.87 | ~4.07 | ~5.67 | 3-bet |
| BIG_LOTTO | 0.83 | 0.70 | 0.71 | 1-bet (marginal) |
| POWER_LOTTO | 1.27 | 1.14 | 0.83 | 2-bet |

## Final Answers

1. **Do 539 signals transfer to BIG_LOTTO or POWER_LOTTO?**
   - **BIG_LOTTO: NO.** All signals fail statistical validation (p>0.05). The larger pool (49 numbers) dilutes signal strength below detection threshold.
   - **POWER_LOTTO: PARTIALLY YES.** MidFreq (p=0.010) and Fourier (p=0.035) transfer successfully. ACB and Markov do not.

2. **Are there new signals unique to these games?**
   - No new signal families were discovered. The study used the same 4 signal families from 539. Game-specific signals (e.g., sum regime, parity constraints) were not tested in this transfer — they are already in production.

3. **Best multi-bet structure for each game?**
   - **BIG_LOTTO**: 3-bet Fourier+ACB+Markov (edge=+1.07%, but p=0.055 — MARGINAL, not deployable)
   - **POWER_LOTTO**: 2-bet MidFreq+Fourier (edge=+2.27%, p=0.005 — VALIDATED and deployable)

4. **Is there any statistically validated edge?**
   - **BIG_LOTTO**: NO validated edge passes the p<0.05 permutation gate
   - **POWER_LOTTO**: YES — MidFreq single-bet (p=0.010), Fourier single-bet (p=0.035), 2-bet orthogonal (p=0.005), 3-bet orthogonal (p=0.015) all pass

5. **Does any strategy reduce the house edge meaningfully?**
   - **NO.** Neither game's prediction edge overcomes the house edge:
     - BIG_LOTTO: needs +3.50% edge, best is +0.41% (12% of required)
     - POWER_LOTTO: needs +3.21% edge, best is +2.48% (77% of required — closest but still negative EV)
   - Monte Carlo confirms: 100% bankroll ruin rate for all tested configurations

## Lessons Learned

- **L83**: MidFreq signal transfers from 539 to POWER_LOTTO (38C6) with p=0.010 — the "anti-extreme frequency" principle is game-invariant for similar pool sizes
- **L84**: ACB signal does NOT transfer to POWER_LOTTO — boundary bonus (n≤6, n≥33) and mod3 heuristics are 539-specific artifacts
- **L85**: No signal achieves validation on BIG_LOTTO (49C6) — the larger number pool dilutes all frequency-based signals below the detection threshold
- **L86**: Strategy evolution overfits on 300p eval window for low-baseline games: +6.5% (300p) → +0.12% (full OOS) for BIG_LOTTO. Use wider eval window for 49C6.
- **L87**: Both games are deeply negative EV. Even the best validated prediction edge (+2.48% for POWER_LOTTO 3-bet) covers only 77% of the house edge deficit.

## Actionable Next Steps

1. **POWER_LOTTO 2-bet MidFreq+Fourier**: Consider adding to RSM monitoring for live tracking (signal is validated)
2. **POWER_LOTTO evolution 3-bet**: Run full walk-forward validation with wider eval window to confirm +3.19% edge
3. **BIG_LOTTO**: Continue with existing production strategies (Regime, TS3) — the transferred signals add no value
4. **Future research**: For BIG_LOTTO, try game-specific signals (structural position, pair co-occurrence) rather than transferring 539 signals
