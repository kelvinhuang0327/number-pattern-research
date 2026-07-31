# Post-V3 Release Gate — UI / Badge Smoke Revalidation

**Date**: 2026-05-14  
**Commit**: bb107ff  
**Backend**: http://127.0.0.1:8002 (live, patched)  
**Frontend**: http://127.0.0.1:3000 (live, HTTP 200)

---

## UI Smoke Status

| Area | Status | Notes |
|------|--------|-------|
| Frontend reachable | ✅ PASS | HTTP 200 at :3000 |
| Backend patched & running | ✅ PASS | HTTP 200 at :8002 |
| V1 truth_level badge (API) | ✅ PASS | REGENERATED_RETROSPECTIVE on page 1 for all 3 sampled strategies |
| controlled_apply_id in API | ✅ PASS | 20260514033100-13acaf34996e |
| source field present | ✅ PASS | non-null for V1 |
| provenance_hash field present | ✅ PASS | non-null for V1 |
| V3 tombstones (API) | ✅ PASS | 0 rows for acb_1bet, h6_gate_mk20_ew85 |
| Strategy lifecycle endpoint | ✅ PASS | 6 ONLINE, no_db_write=true |
| No fake rows introduced | ✅ PASS | No DB writes during smoke |

---

## V1 Strategies — truth_level badge contract (sampled)

| Strategy | Lottery | truth_level | controlled_apply_id | source | provenance_hash | total_rows |
|----------|---------|-------------|---------------------|--------|-----------------|------------|
| biglotto_deviation_2bet | BIG_LOTTO | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ | ✅ | ✅ | 120 |
| daily539_f4cold | DAILY_539 | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ | ✅ | ✅ | 140 |
| power_precision_3bet | POWER_LOTTO | REGENERATED_RETROSPECTIVE ✅ | 20260514033100-13acaf34996e ✅ | ✅ | ✅ | 120 |

---

## V3 CODE_MISSING — tombstone contract

| Strategy | Lottery | total_rows | Expected |
|----------|---------|------------|----------|
| acb_1bet | DAILY_539 | 0 | 0 ✅ |
| h6_gate_mk20_ew85 | POWER_LOTTO | 0 | 0 ✅ |

---

## Strategy Lifecycle Endpoint (`/api/replay/strategy-lifecycle`)

| Metric | Value |
|--------|-------|
| total strategies | 16 |
| ONLINE (V1 EXECUTABLE_NOW) | 6 |
| REJECTED (V2 ARTIFACT_ONLY) | 4 |
| RETIRED (V3 CODE_MISSING) | 5 |
| OBSERVATION | 1 (h6_gate_mk20_ew85) |
| no_db_write | true ✅ |

Executable strategy IDs: biglotto_deviation_2bet, biglotto_triple_strike, daily539_f4cold, daily539_markov_cold, power_orthogonal_5bet, power_precision_3bet

---

## In-Browser Visual Testing

Full interactive browser testing was NOT performed (automated API-level smoke only).  
To verify truth_level badge rendering:
1. Open http://127.0.0.1:3000
2. Navigate to replay history for any V1 strategy
3. Verify badge shows "REGENERATED RETROSPECTIVE" on page 1 records
4. Verify V3 strategies show "unavailable" / empty state

---

**UI Smoke Result**: ✅ API-LEVEL PASS  
**Visual browser inspection**: NOT RUN (automated only)  
**DB write**: NONE ✅  
**Fake rows**: NONE ✅
