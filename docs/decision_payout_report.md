# Decision & Payout Optimization Engine Report
**Generated:** 2026-03-18 15:44  |  seed=42  |  ZERO prediction engine modifications

---

## Executive Summary

- **S1/DAILY_539**: 🔶 WATCH
- **S2/DAILY_539**: ✅ PRODUCTION
- **S3/DAILY_539**: ⚪ NO_GAIN
- **S1/BIG_LOTTO**: ❌ REJECT
- **S2/BIG_LOTTO**: ✅ PRODUCTION
- **S3/BIG_LOTTO**: ✅ GAIN
- **S1/POWER_LOTTO**: ❌ REJECT
- **S2/POWER_LOTTO**: ✅ PRODUCTION
- **S3/POWER_LOTTO**: ⚪ NO_GAIN

---

## Stage 0 — Baseline Metrics

### DAILY_539

| Strategy | Bets | Hit Rate | Edge% | Mon.ROI% | Sharpe | MaxDD | RuinP |
|----------|------|----------|-------|----------|--------|-------|-------|
| f4cold_5bet | 5 | 0.522 | +6.8% | -83.3% | 0.136 | 6 | 1.000 |
| f4cold_3bet | 3 | 0.308 | +0.3% | -84.0% | 0.007 | 16 | 1.000 |
| acb_1bet | 1 | 0.148 | +3.4% | -83.7% | 0.095 | 28 | 1.000 |
| midfreq_acb_2bet | 2 | 0.302 | +8.7% | -81.0% | 0.188 | 14 | 1.000 |
| acb_markov_fourier_3bet | 3 | 0.365 | +6.0% | -82.0% | 0.124 | 10 | 1.000 |
| acb_markov_midfreq_3bet | 3 | 0.393 | +8.8% | -80.5% | 0.180 | 9 | 1.000 |

### BIG_LOTTO

| Strategy | Bets | Hit Rate | Edge% | Mon.ROI% | Sharpe | MaxDD | RuinP |
|----------|------|----------|-------|----------|--------|-------|-------|
| fourier_rhythm_2bet | 2 | 0.046 | +0.9% | -76.7% | 0.043 | 42 | 1.000 |
| deviation_complement_2bet | 2 | 0.046 | +0.9% | -81.6% | 0.043 | 72 | 1.000 |
| triple_strike_3bet | 3 | 0.071 | +1.6% | -74.6% | 0.061 | 42 | 1.000 |
| echo_aware_3bet | 3 | 0.074 | +1.9% | -76.3% | 0.072 | 43 | 1.000 |
| ts3_markov_4bet_w30 | 4 | 0.093 | +2.0% | -73.8% | 0.070 | 30 | 1.000 |
| ts3_markov_freq_5bet_w30 | 5 | 0.112 | +2.2% | -75.5% | 0.070 | 30 | 1.000 |
| p1_neighbor_cold_2bet | 2 | 0.042 | +0.5% | -78.2% | 0.024 | 48 | 1.000 |
| p1_deviation_4bet | 4 | 0.085 | +1.2% | -80.5% | 0.044 | 27 | 1.000 |
| p1_dev_sum5bet | 5 | 0.127 | +3.7% | -79.7% | 0.112 | 21 | 1.000 |
| regime_2bet | 2 | 0.073 | +3.6% | -65.7% | 0.138 | 42 | 1.000 |
| ts3_regime_3bet | 3 | 0.089 | +3.4% | -69.2% | 0.120 | 30 | 1.000 |

### POWER_LOTTO

| Strategy | Bets | Hit Rate | Edge% | Mon.ROI% | Sharpe | MaxDD | RuinP |
|----------|------|----------|-------|----------|--------|-------|-------|
| fourier_rhythm_2bet | 2 | 0.084 | +0.8% | -93.5% | 0.029 | 42 | 1.000 |
| fourier_rhythm_3bet | 3 | 0.142 | +3.0% | -90.0% | 0.087 | 31 | 1.000 |
| fourier30_markov30_2bet | 2 | 0.084 | +0.8% | -94.7% | 0.029 | 35 | 1.000 |
| orthogonal_5bet | 5 | 0.208 | +2.9% | -93.1% | 0.072 | 16 | 1.000 |
| pp3_freqort_4bet | 4 | 0.179 | +3.3% | -92.6% | 0.086 | 17 | 1.000 |
| midfreq_fourier_2bet | 2 | 0.076 | +0.1% | -90.4% | 0.002 | 44 | 1.000 |
| midfreq_fourier_mk_3bet | 3 | 0.130 | +1.8% | -91.8% | 0.053 | 31 | 1.000 |

## Stage 1 — Decision Layer (Confidence Score + Betting Gate)

### DAILY_539 — 🔶 WATCH

- Best strategy: `acb_markov_midfreq_3bet`
- Optimal gate threshold: **50**
- OOS draws analyzed: 218
- Flat ROI: -79.5%  |  Flat Sharpe: -1.940

| Metric | Flat | Gated |
|--------|------|-------|
| Hit rate | — | 0.464 |
| ROI% | -79.5% | -76.8% |
| Sharpe | -1.940 | -1.854 |
| Skip rate | 0% | 68% |

**Validation gates:**
- three_window: ✅
- perm_p05: ❌
- mcnemar: ✅
- sharpe: ✅

---

### BIG_LOTTO — ❌ REJECT

- Best strategy: `p1_dev_sum5bet`
- Optimal gate threshold: **40**
- OOS draws analyzed: 203
- Flat ROI: -77.9%  |  Flat Sharpe: -1.413

| Metric | Flat | Gated |
|--------|------|-------|
| Hit rate | — | 0.100 |
| ROI% | -77.9% | -84.0% |
| Sharpe | -1.413 | -1.750 |
| Skip rate | 0% | 66% |

**Validation gates:**
- three_window: ❌
- perm_p05: ❌
- mcnemar: ❌
- sharpe: ❌

---

### POWER_LOTTO — ❌ REJECT

- Best strategy: `pp3_freqort_4bet`
- Optimal gate threshold: **50**
- OOS draws analyzed: 201
- Flat ROI: -91.0%  |  Flat Sharpe: -2.859

| Metric | Flat | Gated |
|--------|------|-------|
| Hit rate | — | 0.222 |
| ROI% | -91.0% | -88.9% |
| Sharpe | -2.859 | -2.499 |
| Skip rate | 0% | 69% |

**Validation gates:**
- three_window: ✅
- perm_p05: ❌
- mcnemar: ❌
- sharpe: ✅

---

## Stage 2 — Position Sizing

### DAILY_539

- Best boundaries: **[40, 45, 50]**
- Tier map: skip → acb_1bet → midfreq_acb_2bet → acb_markov_midfreq_3bet
- ROI vs flat: +9.6%  |  Sharpe vs flat: +1.127

### BIG_LOTTO

- Best boundaries: **[40, 45, 60]**
- Tier map: skip → regime_2bet → ts3_regime_3bet → p1_dev_sum5bet
- ROI vs flat: +115.4%  |  Sharpe vs flat: +0.402

### POWER_LOTTO

- Best boundaries: **[50, 75, 80]**
- Tier map: skip → fourier_rhythm_3bet → pp3_freqort_4bet → orthogonal_5bet
- ROI vs flat: +247.8%  |  Sharpe vs flat: +2.298

---

## Stage 3 — Payout Optimization (Anti-Crowd)

### DAILY_539 — ⚪ NO_GAIN

- Strategy: `acb_markov_midfreq_3bet`
- Swap rate: 3% of tickets
- Popularity score: 24.0 → 23.0 (Δ+1.0)
- Hit rate delta: +0.31%
- ROI delta: +0.10%

### BIG_LOTTO — ✅ GAIN

- Strategy: `p1_dev_sum5bet`
- Swap rate: 3% of tickets
- Popularity score: 24.1 → 23.1 (Δ+1.1)
- Hit rate delta: +0.65%
- ROI delta: +1.04%

### POWER_LOTTO — ⚪ NO_GAIN

- Strategy: `pp3_freqort_4bet`
- Swap rate: 3% of tickets
- Popularity score: 26.4 → 25.2 (Δ+1.1)
- Hit rate delta: +0.33%
- ROI delta: +0.08%

---

## Stage 4 — Cross-Game Allocation (Fractional Kelly)

| Game | Allocation | Edge 100p | Weekly Edge | Kelly f |
|------|------------|-----------|-------------|---------|
| DAILY_539 | **33%** | +6.50% | +45.50% | 0.0000 |
| BIG_LOTTO | **33%** | +4.04% | +8.08% | 0.0000 |
| POWER_LOTTO | **33%** | +3.40% | +6.80% | 0.0000 |

*Methodology: Fractional Kelly (f=0.25) on 100p weekly edge/vol*

---

## Deployment Recommendation

| Stage | Game | Verdict | Deploy? |
|-------|------|---------|---------|
| S1/DAILY_539 | — | 🔶 WATCH | ❌ NO |
| S2/DAILY_539 | — | ✅ PRODUCTION | ✅ YES |
| S3/DAILY_539 | — | ⚪ NO_GAIN | ❌ NO |
| S1/BIG_LOTTO | — | ❌ REJECT | ❌ NO |
| S2/BIG_LOTTO | — | ✅ PRODUCTION | ✅ YES |
| S3/BIG_LOTTO | — | ✅ GAIN | ✅ YES |
| S1/POWER_LOTTO | — | ❌ REJECT | ❌ NO |
| S2/POWER_LOTTO | — | ✅ PRODUCTION | ✅ YES |
| S3/POWER_LOTTO | — | ⚪ NO_GAIN | ❌ NO |

> **Core principle**: NO prediction engine modifications made.
> All stages are additive, try/except wrapped, and removable.

---
*Generated by `analysis/decision_payout_engine.py` — seed=42*