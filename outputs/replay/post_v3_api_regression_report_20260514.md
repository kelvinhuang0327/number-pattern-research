# Post-V3 Replay API Regression Report
**Date**: 2026-05-14 14:48:28
**Status**: ✅ ALL PASS

---
## Executive Summary
- V1 EXECUTABLE_NOW: 6/6
- V2 ARTIFACT_ONLY: 4/4
- V3 CODE_MISSING: 6/6
- **Total: 16/16**

## V1: EXECUTABLE_NOW Results (6 strategies)
| Strategy | Lottery | HTTP | Records | Schema | Truth Level | No Fake | Pass |
|----------|---------|------|---------|--------|-------------|---------|------|
| biglotto_deviation_2bet | BIG_LOTTO | 200 | 50 | ✅ | ✅ | ✅ | ✅ |
| biglotto_triple_strike | BIG_LOTTO | 200 | 50 | ✅ | ✅ | ✅ | ✅ |
| daily539_f4cold | DAILY_539 | 200 | 50 | ✅ | ✅ | ✅ | ✅ |
| daily539_markov_cold | DAILY_539 | 200 | 50 | ✅ | ✅ | ✅ | ✅ |
| power_orthogonal_5bet | POWER_LOTTO | 200 | 50 | ✅ | ✅ | ✅ | ✅ |
| power_precision_3bet | POWER_LOTTO | 200 | 50 | ✅ | ✅ | ✅ | ✅ |

## V2: ARTIFACT_ONLY Results (4 strategies)
| Strategy | Lottery | HTTP | Records | Schema | Truth Level | No Fake | Pass |
|----------|---------|------|---------|--------|-------------|---------|------|
| biglotto_ts3_acb_4bet | BIG_LOTTO | 200 | 50 | ✅ | ✅ | ✅ | ✅ |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | 200 | 50 | ✅ | ✅ | ✅ | ✅ |
| p1_deviation_2bet_539 | DAILY_539 | 200 | 50 | ✅ | ✅ | ✅ | ✅ |
| power_shlc_midfreq | POWER_LOTTO | 200 | 50 | ✅ | ✅ | ✅ | ✅ |

## V3: CODE_MISSING Results (6 strategies)
| Strategy | Lottery | HTTP | Records | Tombstone | No Fake | Pass |
|----------|---------|------|---------|-----------|---------|------|
| acb_1bet | DAILY_539 | 200 | 0 | ✅ | ✅ | ✅ |
| acb_markov_midfreq | DAILY_539 | 200 | 0 | ✅ | ✅ | ✅ |
| acb_markov_midfreq_3bet | DAILY_539 | 200 | 0 | ✅ | ✅ | ✅ |
| midfreq_acb_2bet | DAILY_539 | 200 | 0 | ✅ | ✅ | ✅ |
| midfreq_fourier_2bet | DAILY_539 | 200 | 0 | ✅ | ✅ | ✅ |
| h6_gate_mk20_ew85 | POWER_LOTTO | 200 | 0 | ✅ | ✅ | ✅ |

## Verification Checklist
- ✅ V1 strategies accessible (all 6 return HTTP 200)
- ✅ V2 strategies accessible (all 4 return HTTP 200)
- ✅ V3 strategies return 0 rows (safe tombstones)
- ✅ V1 truth_level correct (REGENERATED_RETROSPECTIVE)
- ✅ V2 truth_level correct (ARTIFACT_RECONSTRUCTED_RETROSPECTIVE)
- ✅ No fake data in any response

---
**Result**: ✅ API REGRESSION TEST PASSED
