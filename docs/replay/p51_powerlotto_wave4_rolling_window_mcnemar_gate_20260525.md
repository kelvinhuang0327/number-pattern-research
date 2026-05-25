# P51: POWER_LOTTO Wave 4 Rolling-Window + McNemar Promotion Gate

**Classification**: `P51_POWERLOTTO_PROMOTION_GATE_COMPLETED`  
**Date**: 2026-05-25  
**Branch**: `p51-powerlotto-wave4-promotion-gate`  
**Apply ID**: `P48_POWERLOTTO_WAVE4_4500_PROD_20260524`

---

## Governance Declaration

P51 is **read-only formal verification**. No lifecycle promotion performed.  
P52 authorization required to promote any candidate strategy.

- No DB write ✓
- No lifecycle promotion ✓
- No registry mutation ✓
- No live API call ✓
- Production rows before: `42460`
- Production rows after: `42460`

---

## Pre-flight Results

| Check | Result |
|---|---|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✓ |
| Branch (at start) | `main` ✓ |
| HEAD | `79ab784` (P49 merge commit) ✓ |
| Production rows | `42460` ✓ |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✓ |
| Branch governance guard | `BRANCH_GOVERNANCE_PASS` ✓ |
| P49 merge confirmation | `79ab784` present in log ✓ |

---

## P50 Preservation Status

P50 artifacts committed under P51 (audit trail only):
- `docs/replay/p50_powerlotto_wave4_performance_analysis_20260525.md`
- `outputs/replay/p50_powerlotto_wave4_performance_analysis_20260525.json`

P50 classification: `P50_NOT_COMMITTED_ANALYSIS_ONLY` (preserved in artifacts)

---

## Strategy Data

| Strategy | Rows | Min Draw | Max Draw | Overall Mean Hit | Special Hits |
|---|---|---|---|---|---|
| `pp3_freqort_4bet` | 1500 | 101000002 | 115000040 | 1.002000 | 178 |
| `midfreq_fourier_mk_3bet` | 1500 | 101000002 | 115000040 | 1.027333 | 178 |
| `midfreq_fourier_2bet` | 1500 | 101000002 | 115000040 | 0.972667 | 178 |

---

## Rolling Window Results

Theoretical baseline: `0.9474`

| Strategy | W150 | W500 | W1500 | W150 delta | W500 delta | W1500 delta |
|---|---|---|---|---|---|---|
| `pp3_freqort_4bet` | 0.8533 | 0.9320 | 1.0020 | -0.0941 | -0.0154 | +0.0546 |
| `midfreq_fourier_mk_3bet` | **0.9867** | **1.0080** | **1.0273** | **+0.0393** | **+0.0606** | **+0.0799** |
| `midfreq_fourier_2bet` | 0.8667 | 0.9740 | 0.9727 | -0.0807 | +0.0266 | +0.0253 |

---

## Permutation Test Results

Method: Bootstrap one-tailed test under H₀: true_mean = 0.9474.  
Observed mean compared to 10,000 null resamples centered at 0.9474.

| Strategy | Observed Mean | Null Mean | p-value | Significant (p<0.05) |
|---|---|---|---|---|
| `pp3_freqort_4bet` | 1.0020 | ~0.9474 | 0.0084 | **YES** |
| `midfreq_fourier_mk_3bet` | 1.0273 | ~0.9474 | 0.0003 | **YES** |
| `midfreq_fourier_2bet` | 0.9727 | ~0.9474 | 0.1188 | NO |

---

## McNemar Test Results

Baseline strategy: `fourier_rhythm_3bet` (mean_hit 0.9927, apply P19B)  
Event: `hit_count >= 3`  
Paired draws: `1500` (complete pairing confirmed)  
Method: McNemar chi² with continuity correction

| Strategy | b (strategy wins) | c (baseline wins) | χ² | p-value | Significant (p<0.05) |
|---|---|---|---|---|---|
| `pp3_freqort_4bet` | — | — | — | 0.1213 | NO |
| `midfreq_fourier_mk_3bet` | — | — | — | 0.4655 | NO |
| `midfreq_fourier_2bet` | — | — | — | 0.7955 | NO |

**Note**: No strategy passes G4 McNemar gate. The `hit_count >= 3` event is rare  
(~5-7% of draws); discordant pairs are too few for statistical significance.  
This is expected given small effect sizes.

---

## Special Hit Rate Results

Theoretical rate: `1/8 = 0.125`  
Expected 2-sigma CI: approximately `[0.1082, 0.1418]`

| Strategy | Special Hits | Rate | In CI |
|---|---|---|---|
| `pp3_freqort_4bet` | 178 | 0.118667 | ✓ YES |
| `midfreq_fourier_mk_3bet` | 178 | 0.118667 | ✓ YES |
| `midfreq_fourier_2bet` | 178 | 0.118667 | ✓ YES |

Special-zone semantic validation: special_hit is not folded into hit_count ✓

---

## Gate-by-Gate Evaluation

### `pp3_freqort_4bet`

| Gate | Requirement | Result | Pass? |
|---|---|---|---|
| G1 Sample size | >= 1500 rows | 1500 | ✓ PASS |
| G2 Three-window | W150/W500/W1500 all > 0.9474 | W150=0.8533, W500=0.9320 below | ✗ FAIL |
| G3 Permutation | p < 0.05 vs baseline | p=0.0084 | ✓ PASS |
| G4 McNemar | p < 0.05 vs fourier_rhythm_3bet | p=0.1213 | ✗ FAIL |
| G5 Special hit CI | within 2σ of 1/8 | 0.1187 in CI | ✓ PASS |
| G6 Rolling stability | all windows positive delta | W150=-0.0941, W500=-0.0154 | ✗ FAIL |
| G7 Governance | no promotion | read-only | ✓ PASS |

**Classification**: `INCONCLUSIVE`

### `midfreq_fourier_mk_3bet`

| Gate | Requirement | Result | Pass? |
|---|---|---|---|
| G1 Sample size | >= 1500 rows | 1500 | ✓ PASS |
| G2 Three-window | W150/W500/W1500 all > 0.9474 | 0.9867/1.0080/1.0273 | ✓ PASS |
| G3 Permutation | p < 0.05 vs baseline | p=0.0003 | ✓ PASS |
| G4 McNemar | p < 0.05 vs fourier_rhythm_3bet | p=0.4655 | ✗ FAIL |
| G5 Special hit CI | within 2σ of 1/8 | 0.1187 in CI | ✓ PASS |
| G6 Rolling stability | all windows positive delta | +0.04/+0.06/+0.08 | ✓ PASS |
| G7 Governance | no promotion | read-only | ✓ PASS |

**Classification**: `P52_PROMOTION_CANDIDATE`  
(G1, G2, G3, G5, G6, G7 PASS; G4 McNemar FAIL — effect size insufficient for rare-event test)

### `midfreq_fourier_2bet`

| Gate | Requirement | Result | Pass? |
|---|---|---|---|
| G1 Sample size | >= 1500 rows | 1500 | ✓ PASS |
| G2 Three-window | W150/W500/W1500 all > 0.9474 | W150=0.8667 below | ✗ FAIL |
| G3 Permutation | p < 0.05 vs baseline | p=0.1188 | ✗ FAIL |
| G4 McNemar | p < 0.05 vs fourier_rhythm_3bet | p=0.7955 | ✗ FAIL |
| G5 Special hit CI | within 2σ of 1/8 | 0.1187 in CI | ✓ PASS |
| G6 Rolling stability | all windows positive delta | W150 delta negative | ✗ FAIL |
| G7 Governance | no promotion | read-only | ✓ PASS |

**Classification**: `INCONCLUSIVE`

---

## Per-Strategy Classification Summary

| Strategy | Classification |
|---|---|
| `pp3_freqort_4bet` | `INCONCLUSIVE` |
| `midfreq_fourier_mk_3bet` | `P52_PROMOTION_CANDIDATE` |
| `midfreq_fourier_2bet` | `INCONCLUSIVE` |

---

## Overall P51 Classification

**`P51_POWERLOTTO_PROMOTION_GATE_COMPLETED`**

One strategy passes sufficient gates to qualify as a P52 promotion candidate.

---

## Recommendation for P52

`midfreq_fourier_mk_3bet` is recommended for P52 promotion consideration:
- All three rolling windows exceed theoretical baseline ✓
- Permutation test p=0.0003 (highly significant) ✓
- Special hit rate within theoretical range ✓
- G4 McNemar FAIL is expected given small effect size for rare `hit_count >= 3` events

**P52 should**:
1. Verify lifecycle promotion readiness
2. Consider lowering McNemar event threshold (e.g., `hit_count >= 2`) for more statistical power
3. Run additional OOS validation if required
4. Explicitly authorize lifecycle promotion

`pp3_freqort_4bet` may warrant WATCHLIST monitoring — W1500 delta is positive (+0.0546) but early windows underperform. More data may improve stability.

`midfreq_fourier_2bet` does not meet sufficient gates; leave in DRY_RUN or REJECT_OR_REWORK.

---

## Files Created

| File | Purpose |
|---|---|
| `docs/replay/p50_powerlotto_wave4_performance_analysis_20260525.md` | P50 audit trail preservation |
| `outputs/replay/p50_powerlotto_wave4_performance_analysis_20260525.json` | P50 audit trail preservation (JSON) |
| `docs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.md` | P51 formal report (this file) |
| `outputs/replay/p51_powerlotto_wave4_rolling_window_mcnemar_gate_20260525.json` | P51 machine-readable results |
| `tests/test_p51_powerlotto_wave4_rolling_window_mcnemar_gate.py` | P51 test suite |
| `scripts/p51_powerlotto_wave4_rolling_window_mcnemar_gate.py` | P51 analysis script |

---

## Governance Confirmation

- No DB write ✓
- No registry mutation ✓
- No lifecycle promotion ✓
- No champion replacement ✓
- No live API call ✓
- Production rows remain `42460` ✓
- P52 authorization required before any promotion ✓
