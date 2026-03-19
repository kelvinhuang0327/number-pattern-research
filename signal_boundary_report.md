# BIG_LOTTO (49C6) Signal Boundary Research Report

Generated: 2026-03-16 14:31
Data: 2117 draws | OOS after idx 300 (1817 periods)
Seed: 42
M3+ single-bet baseline: 1.864%

---

## Phase 1: Information Content Test

| Test | Verdict | Key Metric |
|------|---------|-----------|
| shannon_entropy | CONSISTENT_WITH_RANDOM | p=0.915603 |
| ljung_box | NO_AUTOCORRELATION | binomial_p=0.228714 |
| frequency_stability | STABLE | binomial_p=0.919005 |
| wald_wolfowitz_runs | INDEPENDENT | binomial_p=0.710124 |
| pair_correlation | NO_PAIR_STRUCTURE |  |
| permutation_entropy | HIGH_COMPLEXITY_RANDOM | PE_norm=0.999876 |

**Phase 1 Summary**: ALL TESTS CONSISTENT WITH RANDOM

---

## Phase 2: Signal Strength Estimation

- **Best MI**: 0.006348 bits (window_20)
- **Entropy reduction**: 1.1835% of baseline H
- **MC random baseline**: mean edge=-0.0016%, std=0.3178%
- 95th percentile edge: 0.5578%
- 99th percentile edge: 0.7780%
- 99.9th percentile edge: 1.0531%

**Hindsight Oracle** (static top-6 from each window):
- window_150: rate=4.667%, edge=+2.803%
- window_500: rate=4.200%, edge=+2.336%
- window_1500: rate=2.600%, edge=+0.736%
- window_1817: rate=2.917%, edge=+1.053%

---

## Phase 3: Method Space Coverage

- **Families tested**: 7
- **Total variants**: 33
- **Parameter configurations**: 155
- **Coverage ratio**: 0.886

| Family | Variants | Best Edge |
|--------|----------|-----------|
| frequency | 6 | +0.303% (ACB, p=0.07 MARGINAL) |
| gap | 5 | Absorbed by frequency signals |
| markov | 4 | +0.192% (p=0.42 NO_SIGNAL) |
| spectral | 4 | +0.414% (Fourier, p=0.14 NO_SIGNAL) |
| regime | 4 | +0.081% (p=0.27 NO_SIGNAL) |
| neighbor_structural | 5 | +0.081% (P1_Neighbor, p=0.48 NO_SIGNAL) |
| evolutionary | 5 | +0.303% (MicroFish, p=0.28, overfit 10.35x) |

**Untested areas**: Deep learning (LSTM/Transformer) — rejected: low baseline causes overfit (L89), Topological data analysis — not attempted, Causal inference — not applicable to iid-like data, External data sources — not available

---

## Phase 4: Overfitting Diagnosis

### Random Evolution Simulation (1000 strategies)
- Train (500p) edge: mean=-0.074%, p95=0.736%, p99=1.136%
- OOS edge: mean=-0.081%, p95=0.566%
- % random achieving >+3% on train: 0.0%
- % random achieving >+3% on OOS: 0.0%
- Median overfit ratio: -0.7x

### Multiple Testing Correction
- 7 signals tested, Bonferroni threshold: 0.0071
- **Bonferroni survivors: 0**
- **BH (FDR) survivors: 0**

### FDR Estimation
- Total hypotheses tested: 22
- Expected false positives at alpha=0.05: 1.1
- Observed positives: 0

---

## Phase 5: Signal Ceiling Estimation

- **Min detectable edge** (alpha=0.05, power=0.80, N=1817): 0.7889%
- **Noise ceiling** (99th pct of random): 0.7780%
- **Best observed**: 0.4140% (Fourier, p=0.14)
- Best vs noise: **WITHIN_NOISE**
- Best vs detection limit: **BELOW_DETECTION**

---

## Phase 6: FINAL VERDICT

### Verdict: **NO_EXPLOITABLE_SIGNAL**

### Definitive Answers

**1. Does BIG_LOTTO contain any detectable predictive signal?**
No. All 6 information content tests are consistent with a fair random process. No signal survives multiple testing correction.

**2. What is the estimated maximum edge?**
Theoretical maximum: 0.789% (minimum detectable). Empirical ceiling: 0.778% (99th pct of random). Best observed: +0.414% (Fourier, p=0.14). Even the best signal is indistinguishable from noise.

**3. Is the current system already near the ceiling?**
Yes. With 155 parameter configurations tested across 7 method families and 33 variants, the explored space covers ~89% of plausible methods. The ceiling appears to be the noise floor itself.

**4. Are further strategy searches likely to produce real improvements?**
No. The 0.0% of random strategies that achieve >+3% on 500p training window collapse to 0.0% on OOS. This is pure noise exploitation, not signal discovery.

**5. Is the game statistically indistinguishable from random noise?**
Yes. Within the limits of 2117 draws and the tested methodology, BIG_LOTTO 49C6 is indistinguishable from a fair random process. No exploitable predictive signal exists within current data limits.

---

## Recommendation

**CLOSE RESEARCH.** Enter permanent maintenance mode for BIG_LOTTO.
Re-evaluate only if:
- Dataset doubles to >4000 draws (improves detection power)
- Game rules or number pool changes
- Fundamentally new signal family (non-frequency-based) becomes available