# Decision & Payout Engine — Strict Validation Report
**Generated:** 2026-03-18 16:04  |  seed=42  |  N_PERM=1000

> **Key principle**: Conditional edge ≠ real edge.
> All gains must be positive both conditionally AND unconditionally.
> Any gain that disappears in the unconditional metric is labeled ADVISORY_ONLY.

---

## Final Classification Table

| Stage | Game | Verdict | Cond.Edge% | Uncond.Edge% | Perm p | McNemar net | N | Deployable? |
|-------|------|---------|-----------|-------------|--------|------------|---|-------------|
| Stage 2 (Position Sizing) | DAILY_539 | ⚪ ADVISORY_ONLY | +13.20% | -3.65% | 0.0220 | -14 | 100 | ⚪ ADVISORY |
| Stage 2 (Position Sizing) | BIG_LOTTO | ⚪ ADVISORY_ONLY | +5.37% | -1.55% | 0.2400 | -3 | 70 | ⚪ ADVISORY |
| Stage 2 (Position Sizing) | POWER_LOTTO | ⚪ ADVISORY_ONLY | +12.48% | -7.14% | 0.1310 | -10 | 63 | ⚪ ADVISORY |
| Stage 3 (Anti-Crowd Payout) | BIG_LOTTO | ⚪ ADVISORY_ONLY | — | (ROI Δ+1.04%) | 0.2570 | — | 307 | ⚪ ADVISORY |

---

## Stage 2 — Position Sizing Detail

### DAILY_539 — ⚪ ADVISORY_ONLY

- Boundaries: `[40, 45, 50]`  | n_bet=100/218 (skip=54%)
- Power: SUFFICIENT  (min detectable edge: 11.9%)

| Metric | Conditional | Unconditional | Flat Baseline |
|--------|------------|---------------|---------------|
| Hit rate | 0.390 | 0.179 | 0.317 |
| Baseline | 0.258 | 0.215 | 0.215 |
| Edge | **+13.20%** | **-3.65%** | +10.11% |

**Statistical tests:**
- Permutation: obs_edge=+13.20%  null_95pct=+11.20%  p=0.0220  ✅
- McNemar: b=10 c=24 net=-14  p=0.0243  ✅
- Sharpe (cond): -0.661 vs flat -1.788  ✅
- Sharpe (uncond): -0.661  ✅

**Window stability (conditional / unconditional):**
- w150: cond=-20.43% ❌  uncond=-6.87% ❌
- w500: ⚠️ DATA_INSUFFICIENT (only 218 draws available)
- w1500: ⚠️ DATA_INSUFFICIENT (only 218 draws available)

**Gate summary** (4/8 pass):
- cond_edge_positive: ✅
- uncond_edge_positive: ❌
- perm_p05: ✅
- mcnemar_net_pos: ❌
- sharpe_cond_beats_flat: ✅
- sharpe_uncond_beats_flat: ✅
- window_cond_stable: ❌
- window_uncond_stable: ❌

> **Reason**: Conditional edge exists (+13.20%) but disappears unconditionally (-3.65%). Gain is an artifact of bet-selection, not real edge.

---

### BIG_LOTTO — ⚪ ADVISORY_ONLY

- Boundaries: `[40, 45, 60]`  | n_bet=70/203 (skip=66%)
- Power: MARGINAL  (min detectable edge: 14.2%)

| Metric | Conditional | Unconditional | Flat Baseline |
|--------|------------|---------------|---------------|
| Hit rate | 0.114 | 0.039 | 0.089 |
| Baseline | 0.061 | 0.055 | 0.055 |
| Edge | **+5.37%** | **-1.55%** | +3.38% |

**Statistical tests:**
- Permutation: obs_edge=+5.37%  null_95pct=+6.87%  p=0.2400  ❌
- McNemar: b=4 c=7 net=-3  p=0.5488  ❌
- Sharpe (cond): -0.202 vs flat -0.604  ✅
- Sharpe (uncond): -0.202  ✅

**Window stability (conditional / unconditional):**
- w150: cond=+6.11% ✅  uncond=-1.49% ❌
- w500: ⚠️ DATA_INSUFFICIENT (only 203 draws available)
- w1500: ⚠️ DATA_INSUFFICIENT (only 203 draws available)

**Gate summary** (4/8 pass):
- cond_edge_positive: ✅
- uncond_edge_positive: ❌
- perm_p05: ❌
- mcnemar_net_pos: ❌
- sharpe_cond_beats_flat: ✅
- sharpe_uncond_beats_flat: ✅
- window_cond_stable: ✅
- window_uncond_stable: ❌

> **Reason**: Conditional edge exists (+5.37%) but disappears unconditionally (-1.55%). Gain is an artifact of bet-selection, not real edge.

---

### POWER_LOTTO — ⚪ ADVISORY_ONLY

- Boundaries: `[50, 75, 80]`  | n_bet=63/201 (skip=69%)
- Power: MARGINAL  (min detectable edge: 15.0%)

| Metric | Conditional | Unconditional | Flat Baseline |
|--------|------------|---------------|---------------|
| Hit rate | 0.238 | 0.075 | 0.184 |
| Baseline | 0.113 | 0.146 | 0.146 |
| Edge | **+12.48%** | **-7.14%** | +3.81% |

**Statistical tests:**
- Permutation: obs_edge=+12.48%  null_95pct=+14.06%  p=0.1310  ❌
- McNemar: b=2 c=12 net=-10  p=0.0129  ✅
- Sharpe (cond): -0.560 vs flat -2.859  ✅
- Sharpe (uncond): -0.560  ✅

**Window stability (conditional / unconditional):**
- w150: cond=-11.38% ❌  uncond=-6.60% ❌
- w500: ⚠️ DATA_INSUFFICIENT (only 201 draws available)
- w1500: ⚠️ DATA_INSUFFICIENT (only 201 draws available)

**Gate summary** (3/8 pass):
- cond_edge_positive: ✅
- uncond_edge_positive: ❌
- perm_p05: ❌
- mcnemar_net_pos: ❌
- sharpe_cond_beats_flat: ✅
- sharpe_uncond_beats_flat: ✅
- window_cond_stable: ❌
- window_uncond_stable: ❌

> **Reason**: Conditional edge exists (+12.48%) but disappears unconditionally (-7.14%). Gain is an artifact of bet-selection, not real edge.

---

## Stage 3 — BIG_LOTTO Anti-Crowd Payout Detail

### BIG_LOTTO — ⚪ ADVISORY_ONLY

- Strategy: `p1_dev_sum5bet`  n=307  swap_rate=16.0%
- Original ROI: -79.67%  → Swapped ROI: -78.63%  (Δ+1.04%)
- Permutation test: p=0.2570  ❌
- All windows positive: ✅

**Window stability:**
- w100: Δ=+0.00%  ✅
- w200: Δ=+0.80%  ✅
- wfull: Δ=+1.04%  ✅

**Threshold sensitivity (popularity score threshold → ROI delta):**

| Threshold | Orig ROI% | Swap ROI% | Δ ROI% | Swap rate |
|-----------|-----------|-----------|--------|-----------|
| 0 | -79.67% | -78.63% | +1.04% | 0.7% |
| 20 | -79.67% | -78.63% | +1.04% | 0.7% |
| 30 | -79.67% | -78.63% | +1.04% | 0.7% |
| 40 | -79.67% | -78.63% | +1.04% | 0.7% |
| 50 | -79.67% | -78.63% | +1.04% | 0.7% |
| 60 | -79.67% | -79.67% | +0.00% | 0.0% |
| 70 | -79.67% | -79.67% | +0.00% | 0.0% |

**Gate summary** (4/5 pass):
- roi_delta_positive: ✅
- perm_p05: ❌
- three_windows_pos: ✅
- swap_rate_meaningful: ✅
- popularity_reduced: ✅

> **Reason**: ROI delta=+1.04% positive but NOT statistically significant (perm p=0.2570). Effect size too small for current n=307.

---

## Interpretation Guide

| Verdict | Meaning |
|---------|---------|
| PRODUCTION_CANDIDATE | Both conditional and unconditional edge positive, perm p<0.05, McNemar improvement. Ready for shadow deployment. |
| WATCH | Conditional edge real, unconditional borderline. Continue monitoring with more data. |
| ADVISORY_ONLY | Gain exists conditionally only — artifact of bet selection, not signal quality. Use as informational only. |
| GAIN_VALIDATED (Stage 3) | ROI uplift present but permutation not significant — effect real but small. ADVISORY use. |
| REJECT | No consistent improvement. Do not deploy. |

---
*Generated by `analysis/decision_payout_validation.py` — seed=42, N_PERM=1000*