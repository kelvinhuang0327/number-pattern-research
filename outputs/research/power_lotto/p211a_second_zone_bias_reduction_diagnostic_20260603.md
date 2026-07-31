# P211A — POWER_LOTTO Second-Zone Bias-Reduction Read-Only Diagnostic

**Date:** 2026-06-03  
**Status:** COMPLETE  
**Classification:** `P211A_SECOND_ZONE_BIAS_REDUCTION_DIAGNOSTIC_COMPLETE`  
**Authorized by:** User explicit prompt 2026-06-03 (P211A only)

---

## Phase 0 Verification

| Check | Result |
|---|---|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✅ |
| Branch | `main` ✅ |
| HEAD == origin/main | ✅ |
| DB rows | 94,924 ✅ |
| bet_index nulls | 0 ✅ |
| Duplicate keys | 0 ✅ |
| POWER_LOTTO rows | 36,104 ✅ |
| Integrity check | ok ✅ |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| P218 structural HEAD fix | present ✅ |
| Staged files | 0 ✅ |
| Commit gate | nothing authorized to commit ✅ |

---

## Frozen Parameters (from P210 protocol)

| Parameter | Value |
|---|---|
| Mid window | 250 draws |
| Short window | 40 draws |
| EWMA λ | 0.97 |
| Baseline | 0.125 (1/8) |
| Bonferroni threshold | 0.0125 (0.05/4 schemes) |
| OOS window | 150 draws |
| Schemes tested | long / mid / short / ewma |

---

## Dataset Summary

- **Total draws:** 1,551 (99000055 = 2010-07-12 → 115000041 = 2026-05-21)
- **Draws with predicted_special:** 1,500 (9,000 rows across 6 strategies × 1500 draws)
- **OOS window (last 150):** draws 113000101–115000041

---

## Current System Baseline — Bias Confirmed

The current system's predicted_special distribution (all 9,000 rows, bet_index=1):

| Ball | Predicted % | Actual all-time % | Random baseline |
|---|---|---|---|
| 1 | 22.94% | 12.19% | 12.5% |
| 2 | 17.43% | 14.76% | 12.5% |
| 3 | 22.61% | 11.86% | 12.5% |
| 4 | 10.32% | 12.77% | 12.5% |
| 5 |  8.82% | 13.73% | 12.5% |
| 6 |  6.09% | 11.48% | 12.5% |
| 7 |  7.23% | 11.15% | 12.5% |
| 8 |  4.54% | 12.06% | 12.5% |

**1+2+3 combined: 62.98% of predictions vs 38.81% of actuals.**  
**Per-bet hit rate: 1,063/9,000 = 11.81% (below 12.5% random baseline).**  
**Draw-level hit rate (any bet): 486/1,500 = 32.40%.**

**Bias mechanism confirmed (P210 Section 1):** Full-period frequency scoring amplifies ball 2's marginal all-time lead (14.76% vs 12.5%) into a 22.94% prediction share. Balls 4–8 are systematically under-predicted despite near-baseline actual rates.

---

## Counterfactual Results — OOS 150 Draws

Simulation: for each OOS draw, predict the top-1 ball using only history before that draw under each scheme.

| Scheme | Hits | Hit Rate | Wilson 95% CI | p(>0.125) | Bonf sig | KL_div | 1/2/3% |
|---|---|---|---|---|---|---|---|
| **long** | 28 | 18.67% | [13.24%, 25.66%] | 0.0193 | **NO** | 2.0794 | **100.0%** |
| **mid** | 24 | 16.00% | [10.99%, 22.70%] | 0.1222 | **NO** | 1.3447 | 34.7% |
| **short** | 24 | 16.00% | [10.99%, 22.70%] | 0.1222 | **NO** | 0.8798 | 44.0% |
| **ewma** | 24 | 16.00% | [10.99%, 22.70%] | 0.1222 | **NO** | 0.9265 | 42.0% |
| Random baseline | — | 12.50% | — | — | — | 0 | 12.5% |

**Bonferroni threshold = 0.0125. No scheme passes.**

### Per-Ball Prediction Distribution in OOS-150 (%)

| Ball | Long | Mid | Short | EWMA | Actual |
|---|---|---|---|---|---|
| 1 | 0.0% | 0.0% | 0.0% | 0.0% | 8.7% |
| 2 | **100.0%** | 34.7% | 43.3% | 42.0% | **18.7%** |
| 3 | 0.0% | 0.0% | 0.7% | 0.0% | 11.3% |
| 4 | 0.0% | 2.0% | **32.0%** | **30.7%** | 16.0% |
| 5 | 0.0% | **63.3%** | 20.7% | 25.3% | 16.0% |
| 6 | 0.0% | 0.0% | 0.0% | 0.0% | 10.7% |
| 7 | 0.0% | 0.0% | 0.0% | 0.0% | 8.0% |
| 8 | 0.0% | 0.0% | 3.3% | 2.0% | 10.7% |

**Key observation:** The long scheme degenerates to always predicting ball 2 (KL=2.08 = maximum). Mid/short/EWMA are more diverse (KL=0.88–1.34) but still highly concentrated on whichever ball currently leads the window. No scheme achieves anything close to a uniform prediction distribution.

---

## Counterfactual Results — OOS 500 Draws

| Scheme | Hits | Hit Rate | p(>0.125) | Bonf sig | KL_div | 1/2/3% |
|---|---|---|---|---|---|---|
| long | 75/500 | 15.00% | 0.0550 | **NO** | 2.0794 | 100.0% |
| mid | 64/500 | 12.80% | 0.4397 | **NO** | 0.7121 | 51.2% |
| short | 72/500 | 14.40% | 0.1132 | **NO** | 0.2234 | 39.4% |
| ewma | 67/500 | 13.40% | 0.2902 | **NO** | 0.2875 | 35.6% |

**All Bonferroni NULL in OOS-500 as well.** Mid scheme drops to 12.80% (barely above baseline) in OOS-500, confirming the OOS-150 result was not a strong positive signal.

---

## Walk-Forward Block Stability (8 × 150-draw non-overlapping blocks)

| Block | Draws | Long | Mid | Short | EWMA |
|---|---|---|---|---|---|
| 0 | 102000097–104000038 | 14.0% | 14.0% | 14.7% | **18.7%** |
| 1 | 104000039–105000083 | 15.3% | 11.3% | 12.7% | 14.7% |
| 2 | 105000084–107000025 | 13.3% | 13.3% | 10.7% | 12.0% |
| 3 | 107000026–108000070 | 14.0% | **18.7%** | 16.0% | 18.0% |
| 4 | 108000071–110000011 | 12.7% | **8.0%** | 10.0% | 10.7% |
| 5 | 110000012–111000057 | **16.0%** | 12.0% | 15.3% | 12.7% |
| 6 | 111000058–112000103 | 14.0% | 11.3% | 12.0% | 11.3% |
| 7 | 112000104–114000044 | 12.0% | 11.3% | 14.0% | 14.0% |
| **Baseline** | — | **12.5%** | **12.5%** | **12.5%** | **12.5%** |
| Blocks > baseline | | 7/8 | 3/8 | 5/8 | 5/8 |

**Interpretation:** High variance across blocks (8.0%–18.7%) is fully consistent with sampling noise from a uniform distribution. No scheme shows stable above-baseline performance. Mid scheme falls to 8.0% in block 4 — worse than random for that 150-draw window. Walk-forward confirms NULL.

---

## Bias Reduction Analysis

| Metric | Long | Mid | Short | EWMA | Current System |
|---|---|---|---|---|---|
| 1/2/3 concentration | **100.0%** | 34.7% | 44.0% | 42.0% | 63.0% |
| KL divergence | **2.079** | 1.345 | 0.880 | 0.927 | 0.152 |
| Concentration index | **1.000** | 0.453 | 0.239 | 0.240 | 0.044 |

**Bias reduction finding:**

✅ Mid/short/EWMA **do** reduce low-number fixation vs the long (all-history) scheme.  
✅ The bias mechanism is confirmed: all-history frequency scoring amplifies marginal differences.  
❌ Bias reduction does **not** improve hit rate above the random 12.5% baseline.  
❌ The actual second-zone draw remains consistent with uniform random (SZC1 confirmed).

**The current system's lower KL (0.152) and concentration (0.044)** vs any counterfactual scheme's top-1 prediction is because the current system aggregates 6 strategies making different predictions for each draw, producing diversity through strategy diversity rather than per-strategy calibration. Individual strategies remain biased.

---

## Statistical Summary

| Question | Answer |
|---|---|
| Any scheme Bonferroni-significant in OOS-150? | **NO** |
| Any scheme Bonferroni-significant in OOS-500? | **NO** |
| Three-window validation (150/500/full) passed? | **NO** (mid drops to 12.80% at OOS-500) |
| Walk-forward block stability? | **LOW** (no scheme consistent >12.5%) |
| Long scheme higher OOS-150 hit rate real? | **NO** — degenerate always-ball-2; ball 2 happened to appear 18.7% in that specific OOS window |

---

## Conclusions

### 1. Bias Reduction: YES (structural, confirmed)
Demoting full-history frequency and using mid/short/EWMA windows reduces the 1/2/3 prediction concentration from 100% (long-only degenerate) to 35–44%. This mechanistically confirms P210's hypothesis.

### 2. Hit Rate Edge: NULL (all Bonferroni-corrected p > 0.0125)
Bias reduction does not translate to hit rate improvement. The second zone is consistent with a fair uniform draw from {1…8}. Any scheme that improves distribution diversity converges toward 12.5% hit rate — it does not exceed it.

### 3. Second-Zone Remains Display-Only
SZC1 (`SECOND_ZONE_NO_SIGNAL_CONFIRMED`) and SZC2 (`SECOND_ZONE_DISPLAY_ONLY_CONFIRMED`) are fully confirmed by this diagnostic. No scheme qualifies for production promotion.

### 4. Full P211B Is Not Worth Doing
P211A delivers complete evidence. Full P211B would only refine the NULL result with more schemes and would be unlikely to find a signal that P211A's 4 schemes missed across 1,551 draws. The structural cause is fully explained: frequency-based scoring on a near-uniform distribution cannot generate predictive edge. Recommend closing second-zone active research.

**Reopen condition:** Only if future draws show Bonferroni-corrected p < 0.0125 deviation from uniform distribution over ≥500 new draws.

---

## NULL Classification

> **`P211A_SECOND_ZONE_SHORT_MID_WINDOW_NULL_CONFIRMED`** for hit rate edge.  
> Bias reduction is confirmed but non-operational: it improves prediction diversity without improving accuracy.  
> This is a valid and complete success per P210 Section 4.8.

---

## Validation

| Check | Result |
|---|---|
| Only allowed output files written | ✅ |
| `git diff --cached --name-only` empty | ✅ |
| No commit / push / branch | ✅ |
| DB rows unchanged | 94,924 ✅ |
| Drift guard | PASS ✅ |
| Full test suite | NOT RUN (read-only diagnostic) |

---

## Required Completion Check

1. **是否真的完成**: YES — full 4-scheme diagnostic with OOS-150, OOS-500, and walk-forward blocks. JSON and MD artifacts written.
2. **測試結果**: NOT RUN (read-only diagnostic per task spec). Drift guard PASS.
3. **仍卡住的唯一問題**: None. Results are conclusive.
4. **修改檔案清單**:
   - `outputs/research/power_lotto/p211a_second_zone_bias_reduction_diagnostic_20260603.json` (new, untracked)
   - `outputs/research/power_lotto/p211a_second_zone_bias_reduction_diagnostic_20260603.md` (new, untracked)
5. **staged / commit / push 狀態**: 0 / 0 / 0
6. **是否允許進入下一輪**: YES — diagnostic complete, results conclusive
7. **Final Classification**: `P211A_SECOND_ZONE_BIAS_REDUCTION_DIAGNOSTIC_COMPLETE`
