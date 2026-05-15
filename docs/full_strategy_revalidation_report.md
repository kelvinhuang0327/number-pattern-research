# Phase R — Full Strategy Revalidation Report

**Date**: 2025-01  
**Scope**: All 24 strategies across 3 lotteries  
**Validation Windows**: 150 / 500 / 1500 draws  

---

## Executive Summary

Full re-audit of all strategies confirmed:
- **2 status mismatches corrected** (JSON data fixes)
- **2 critical code bugs fixed** (`_derive_strategy_status` in 2 files)
- **Ranking logic upgraded** (full tie-breaking per spec in 2 locations)
- All 24 strategies now show correct statuses and are properly ranked

---

## Validation Criteria (Spec)

| Status | Conditions |
|--------|-----------|
| VALIDATED | All 3 window edges > 0 AND perm_p < 0.05 AND mcnemar_p < 0.05 AND sharpe > 0 |
| WATCH | perm_p < 0.05 AND sharpe > 0 — but NOT all edges positive OR mcnemar_p ≥ 0.05 |
| REJECT | perm_p ≥ 0.05 (permutation test failed) |

Note: `perm_p = 0.0` is valid (extremely significant) — must NOT be treated as falsy.

---

## DAILY_539 — 6 Strategies

| Strategy | n | Status | e150 | e500 | e1500 | perm_p | mcn_p | sharpe | cs |
|----------|---|--------|------|------|-------|--------|-------|--------|----|
| f4cold_5bet | 5 | ✅ VALIDATED | 0.1028 | 0.1061 | 0.0861 | 0.0000 | 0.0000 | 0.1728 | 0.0936 |
| acb_markov_midfreq_3bet | 3 | ✅ VALIDATED | 0.0783 | 0.0519 | 0.0635 | 0.0000 | 0.0008 | 0.1316 | 0.0705 |
| acb_markov_fourier_3bet | 3 | ✅ VALIDATED | 0.0583 | 0.0458 | 0.0599 | 0.0000 | 0.0016 | 0.1243 | 0.0665 |
| midfreq_acb_2bet | 2 | ✅ VALIDATED | 0.0779 | 0.0615 | 0.0495 | 0.0000 | 0.0092 | 0.1121 | 0.0575 |
| f4cold_3bet | 3 | ✅ VALIDATED | 0.0250 | 0.0596 | 0.0471 | 0.0000 | 0.0168 | 0.0987 | 0.0520 |
| acb_1bet | 1 | ⚠️ WATCH | 0.0193 | 0.0245 | 0.0260 | 0.0007 | 0.1482 | 0.0749 | 0.0349 |

**Mismatches found**: 0  
**Status corrections**: None required  
**Best overall**: f4cold_5bet (VALIDATED, cs=0.0936)  
**Note**: No n=4 strategy exists for DAILY_539

---

## BIG_LOTTO — 11 Strategies

| Strategy | n | Status | e150 | e500 | e1500 | perm_p | mcn_p | sharpe | cs |
|----------|---|--------|------|------|-------|--------|-------|--------|----|
| p1_deviation_4bet | 4 | ✅ VALIDATED | 0.0342 | 0.0214 | 0.0233 | 0.0003 | 0.0253 | 0.0790 | 0.0343 |
| p1_dev_sum5bet | 5 | ⚠️ WATCH | 0.0471 | 0.0319 | 0.0274 | 0.0001 | 0.0634 | 0.0852 | 0.0386 |
| regime_2bet | 2 | ⚠️ WATCH | 0.0298 | 0.0139 | 0.0128 | 0.0049 | 0.1747 | 0.0589 | 0.0234 |
| p1_neighbor_cold_2bet | 2 | ⚠️ WATCH | 0.0164 | 0.0092 | 0.0122 | 0.0069 | 0.2016 | 0.0564 | 0.0223 |
| fourier_rhythm_2bet | 2 | ⚠️ WATCH | 0.0231 | 0.0092 | 0.0110 | 0.0131 | 0.2650 | 0.0514 | 0.0203 |
| ts3_markov_freq_5bet_w30 | 5 | ⚠️ WATCH | 0.0171 | 0.0196 | 0.0140 | 0.0273 | 0.5154 | 0.0461 | 0.0198 |
| ts3_regime_3bet | 3 | ⚠️ WATCH | 0.0318 | 0.0159 | 0.0112 | 0.0153 | 0.3033 | 0.0449 | 0.0182 |
| ts3_markov_4bet_w30 | 4 | ⚠️ WATCH | 0.0208 | 0.0183 | 0.0117 | 0.0388 | 0.2581 | 0.0423 | 0.0175 |
| triple_strike_3bet | 3 | ⚠️ WATCH | 0.0284 | 0.0128 | 0.0100 | 0.0262 | 0.3724 | 0.0404 | 0.0161 |
| echo_aware_3bet | 3 | ⚠️ WATCH | 0.0251 | 0.0205 | 0.0093 | 0.0169 | 0.4320 | 0.0381 | 0.0152 |
| deviation_complement_2bet | 2 | ❌ REJECT | 0.0031 | 0.0123 | 0.0043 | 0.0637 | 0.5827 | 0.0217 | 0.0080 |

**Mismatches found before fix**: 1  
**Status corrections**:
- `deviation_complement_2bet`: WATCH → **REJECT** (perm_p=0.0637 ≥ 0.05)

**Best overall**: p1_deviation_4bet (VALIDATED, cs=0.0343)

---

## POWER_LOTTO — 7 Strategies

| Strategy | n | Status | e150 | e500 | e1500 | perm_p | mcn_p | sharpe | cs |
|----------|---|--------|------|------|-------|--------|-------|--------|----|
| orthogonal_5bet | 5 | ⚠️ WATCH | 0.0409 | 0.0309 | 0.0382 | 0.0050 | 0.1548 | 0.0850 | 0.0419 |
| midfreq_fourier_mk_3bet | 3 | ⚠️ WATCH | 0.0083 | 0.0343 | 0.0243 | 0.0100 | 0.1285 | 0.0751 | 0.0347 |
| pp3_freqort_4bet | 4 | ⚠️ WATCH | 0.0406 | 0.0300 | 0.0320 | 0.0000 | 0.2386 | 0.0707 | 0.0338 |
| fourier_rhythm_3bet | 3 | ⚠️ WATCH | 0.0083 | 0.0143 | 0.0250 | 0.0000 | 0.2684 | 0.0620 | 0.0283 |
| midfreq_fourier_2bet | 2 | ⚠️ WATCH | -0.0092 | 0.0241 | 0.0194 | 0.0032 | 0.1075 | 0.0637 | 0.0279 |
| fourier_rhythm_2bet | 2 | ⚠️ WATCH | 0.0041 | 0.0101 | 0.0154 | 0.0350 | 0.3125 | 0.0443 | 0.0189 |
| fourier30_markov30_2bet | 2 | ❌ REJECT | -0.0159 | -0.0059 | -0.0012 | 0.3762 | 0.2183 | 0.0085 | 0.0025 |

**Mismatches found before fix**: 1  
**Status corrections**:
- `fourier30_markov30_2bet`: WATCH → **REJECT** (perm_p=0.3762 ≥ 0.05; all edges negative)

**Best overall**: orthogonal_5bet (WATCH only — no VALIDATED strategies)

---

## Code Bugs Fixed

### Bug 1 & 2: `_derive_strategy_status()` — WATCH → PRODUCTION via dead field

**Location**: `lottery_api/routes/prediction.py:2125` and `lottery_api/engine/prediction_tracker.py:61`

**Root cause**: When `validated_status == "WATCH"`, the function read `edge_300p` (obsolete field,
never populated since Phase V migration) and returned "PRODUCTION" when `edge_300p > 0`. 
Since `edge_300p` defaults to 0, this caused unpredictable behavior depending on whether old data existed.

**Fix applied**:
```python
# BEFORE (BUGGY)
if vs == "WATCH":
    edge = state.get("edge_300p", 0) or 0  # obsolete field!
    alert = state.get("alert", False)
    return "WATCH" if (alert or edge <= 0) else "PRODUCTION"  # wrong promotion

# AFTER (CORRECT)
if vs == "WATCH":
    return "WATCH"  # WATCH never promotes to PRODUCTION
```

### Bug 3 & 4: `_rank_key()` / `_rank_key_phase_v()` — incomplete ranking

**Location**: `lottery_api/routes/decision.py:128` and `lottery_api/engine/prediction_tracker.py:86`

**Root cause**: Ranking only used `(priority, composite_score)`. Spec requires full tie-breaking with
`edge_1500p`, `sharpe`, and `max_drawdown_rate` (lower is better).

**Fix applied**:
```python
# AFTER (CORRECT)
return (priority, cs, e1500, sharpe, -dd)
```

### Additional fix in `decision.py`: REJECT excluded from best-strategy

REJECT strategies are now explicitly excluded when selecting the `best_strategy` field.
Previously they could appear as best if all VALIDATED/WATCH strategies were filtered out.

---

## Post-Fix Verification

Re-ran `python3 tmp/full_audit.py` after all fixes:
- DAILY_539: 0 mismatches ✅
- BIG_LOTTO: 0 mismatches ✅
- POWER_LOTTO: 0 mismatches ✅
- Total: **0 mismatches across all 24 strategies**
