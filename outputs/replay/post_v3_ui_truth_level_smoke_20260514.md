# Post-V3 UI Truth-Level Smoke Report

**Date**: 2026-05-14  
**Session**: Post-V3 Truth-Level API Closure  
**Backend**: http://127.0.0.1:8002 (live, patched)  
**Frontend**: http://127.0.0.1:3000 (live, HTTP 200)

---

## UI Smoke Status

| Area | Status | Notes |
|------|--------|-------|
| Frontend reachable | ✅ PASS | HTTP 200 at :3000 |
| Backend patched & running | ✅ PASS | HTTP 200 at :8002 |
| V1 strategies visible (API) | ✅ PASS | All 6, page 1 correct |
| V1 truth_level badge data | ✅ PASS | REGENERATED_RETROSPECTIVE |
| V2 strategies visible (API) | ✅ PASS | All 4, 4/4 regression |
| V3 tombstones (0 rows) | ✅ PASS | All 6, 0 rows returned |
| Lifecycle endpoint | ✅ PASS | 6 executable, no_db_write |

---

## V1 Strategies — truth_level badge contract

| Strategy | Lottery | Page 1 Rows | truth_level | controlled_apply_id |
|----------|---------|-------------|-------------|---------------------|
| biglotto_deviation_2bet | BIG_LOTTO | 50 | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ |
| biglotto_triple_strike | BIG_LOTTO | 50 | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ |
| daily539_f4cold | DAILY_539 | 50 | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ |
| daily539_markov_cold | DAILY_539 | 50 | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ |
| power_orthogonal_5bet | POWER_LOTTO | 50 | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ |
| power_precision_3bet | POWER_LOTTO | 50 | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ |

---

## V3 CODE_MISSING — tombstone contract

| Strategy | Lottery | Total Rows | Expected |
|----------|---------|------------|----------|
| acb_1bet | DAILY_539 | 0 | 0 ✅ |
| acb_markov_midfreq | DAILY_539 | 0 | 0 ✅ |
| acb_markov_midfreq_3bet | DAILY_539 | 0 | 0 ✅ |
| midfreq_acb_2bet | DAILY_539 | 0 | 0 ✅ |
| midfreq_fourier_2bet | DAILY_539 | 0 | 0 ✅ |
| h6_gate_mk20_ew85 | POWER_LOTTO | 0 | 0 ✅ |

---

## Lifecycle Endpoint Contract

- Total strategies: 16 (6 V1 EXECUTABLE_NOW + 4 V2 ARTIFACT_ONLY + 6 V3 CODE_MISSING)
- Executable strategies: 6 (V1 only)
- no_db_write: true ✅

---

## Legacy Row Protection

Legacy rows (null truth_level) are protected and visible on later pages.  
They do NOT mask V1 controlled rows. V1 rows appear on page 1 (higher draw numbers = 115000001+).  
Legacy rows appear on pages 2–3 (lower draw numbers = 99000056–99000105).  
No reclassification occurred. No DB mutation.

---

## In-Browser Visual Testing

Full interactive browser testing was NOT performed (automated API-level smoke only).  
To verify truth_level badge rendering:
1. Open http://127.0.0.1:3000
2. Navigate to replay history for any V1 strategy
3. Verify badge shows "REGENERATED RETROSPECTIVE" on page 1 records
4. Verify V3 strategies show "unavailable" / empty state (no fake rows)

---

## Fake Data Check

- No fake rows introduced ✅
- No DB writes performed ✅
- No new strategies added ✅
- Registry unchanged ✅

---

**UI Smoke Result**: ✅ API-LEVEL PASS  
**Visual browser inspection**: NOT RUN (automated only)  
**DB write**: NONE ✅
