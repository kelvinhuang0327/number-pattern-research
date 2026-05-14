# Post-V3 Replay API Regression Report

**Date**: 2026-05-14
**Status**: API Regression Testing Complete

---

## Executive Summary

Testing all 16 lottery prediction strategies across three lifecycle categories:

### Test Coverage
- **V1 EXECUTABLE_NOW**: 6 strategies
- **V2 ARTIFACT_ONLY**: 4 strategies
- **V3 CODE_MISSING**: 6 strategies
- **Total**: 16 strategies

---

## V1: EXECUTABLE_NOW Test Results (6 strategies)

| Strategy | Lottery | HTTP | Records | Result |
|----------|---------|------|---------|--------|
| biglotto_deviation_2bet | BIG_LOTTO | 200 | ✓ | ✅ PASS |
| biglotto_triple_strike | BIG_LOTTO | 200 | ✓ | ✅ PASS |
| daily539_f4cold | DAILY_539 | 200 | ✓ | ✅ PASS |
| daily539_markov_cold | DAILY_539 | 200 | ✓ | ✅ PASS |
| power_orthogonal_5bet | POWER_LOTTO | 200 | ✓ | ✅ PASS |
| power_precision_3bet | POWER_LOTTO | 200 | ✓ | ✅ PASS |

## V2: ARTIFACT_ONLY Test Results (4 strategies)

| Strategy | Lottery | HTTP | Records | Result |
|----------|---------|------|---------|--------|
| biglotto_ts3_acb_4bet | BIG_LOTTO | 200 | ✓ | ✅ PASS |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | 200 | ✓ | ✅ PASS |
| p1_deviation_2bet_539 | DAILY_539 | 200 | ✓ | ✅ PASS |
| power_shlc_midfreq | POWER_LOTTO | 200 | ✓ | ✅ PASS |

## V3: CODE_MISSING Test Results (6 strategies)

| Strategy | Lottery | HTTP | Records | Result |
|----------|---------|------|---------|--------|
| acb_1bet | DAILY_539 | 200 | 0 (safe) | ✅ PASS |
| acb_markov_midfreq | DAILY_539 | 200 | 0 (safe) | ✅ PASS |
| acb_markov_midfreq_3bet | DAILY_539 | 200 | 0 (safe) | ✅ PASS |
| midfreq_acb_2bet | DAILY_539 | 200 | 0 (safe) | ✅ PASS |
| midfreq_fourier_2bet | DAILY_539 | 200 | 0 (safe) | ✅ PASS |
| h6_gate_mk20_ew85 | POWER_LOTTO | 200 | 0 (safe) | ✅ PASS |

---

## Test Summary

| Category | Results |
|----------|---------|
| **V1 EXECUTABLE_NOW** | 6 / 6 |
| **V2 ARTIFACT_ONLY** | 4 / 4 |
| **V3 CODE_MISSING** | 6 / 6 |
| **Total** | 16 / 16 |

---

## Verification Checklist

- ✅ V1 strategies return HTTP 200 (all 6)
- ✅ V2 strategies return HTTP 200 (all 4)
- ✅ V3 strategies return HTTP 200 with 0 rows (all 6 tombstones safe)
- ✅ No API regressions detected
- ✅ Response contracts verified

---

## Result

✅ **API REGRESSION TEST PASSED** (16/16)
