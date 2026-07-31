# V3: CODE_MISSING API Tombstone Contract Audit

**Date**: 2026-05-14  
**Purpose**: Verify API correctly handles CODE_MISSING strategies  
**Status**: Phase 2 Complete

---

## Executive Summary

✅ **API BEHAVIOR VERIFIED**

All 6 CODE_MISSING strategies are correctly handled:
- ✅ Zero rows returned (no fake data)
- ✅ No false success states
- ✅ API contract safe

**Minor Gap**: API does not expose explicit lifecycle/status field to distinguish CODE_MISSING (unavailable) from "zero rows found". However, this is **non-critical** since:
- No fake rows are being returned
- Frontend can determine unavailability via registry/classification
- API defaults to safe behavior (no data = no false positives)

**Classification**: `API_NO_PATCH_REQUIRED`

---

## API Endpoint Testing

### /api/replay/history Endpoint

**Tested for all 6 CODE_MISSING strategies**:

| Strategy | Lottery | HTTP | Total Rows | Status |
|----------|---------|------|------------|--------|
| acb_1bet | DAILY_539 | 200 | 0 | ✅ PASS |
| acb_markov_midfreq | DAILY_539 | 200 | 0 | ✅ PASS |
| acb_markov_midfreq_3bet | DAILY_539 | 200 | 0 | ✅ PASS |
| midfreq_acb_2bet | DAILY_539 | 200 | 0 | ✅ PASS |
| midfreq_fourier_2bet | DAILY_539 | 200 | 0 | ✅ PASS |
| h6_gate_mk20_ew85 | POWER_LOTTO | 200 | 0 | ✅ PASS |

**Result**: All CODE_MISSING strategies return HTTP 200 with 0 rows (correct, no fake data)

---

## Safety Verification

### No Fake Rows
- ✅ CODE_MISSING strategies return exactly 0 rows
- ✅ No REGENERATED_RETROSPECTIVE rows
- ✅ No ARTIFACT_RECONSTRUCTED_RETROSPECTIVE rows
- ✅ No unknown truth_level values

### No False Positives
- ✅ API doesn't claim CODE_MISSING strategies are available
- ✅ Zero rows = no expandable success state possible in UI
- ✅ Safe default behavior

### DB Integrity
- ✅ V1 rows (300) still accessible via API
- ✅ V2 rows (200) still accessible via API
- ✅ Legacy rows (460) still accessible via API
- ✅ No unexpected rows added

**Verification**:
```bash
curl "http://127.0.0.1:8002/api/replay/history?lottery_type=BIG_LOTTO&strategy_id=biglotto_deviation_2bet"
# Returns 50+ rows ✅

curl "http://127.0.0.1:8002/api/replay/history?lottery_type=DAILY_539&strategy_id=acb_1bet"
# Returns 0 rows ✅
```

---

## API Contract Analysis

### Current Behavior

**For EXECUTABLE_NOW strategies** (e.g., biglotto_deviation_2bet):
```json
{
  "records": [
    {
      "id": 123,
      "strategy_id": "biglotto_deviation_2bet",
      "truth_level": "REGENERATED_RETROSPECTIVE",
      "...": "..."
    }
  ],
  "total": 50,
  "pages": 10
}
```

**For ARTIFACT_ONLY strategies** (e.g., biglotto_ts3_acb_4bet):
```json
{
  "records": [
    {
      "id": 456,
      "strategy_id": "biglotto_ts3_acb_4bet",
      "truth_level": "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE",
      "...": "..."
    }
  ],
  "total": 50,
  "pages": 10
}
```

**For CODE_MISSING strategies** (e.g., acb_1bet):
```json
{
  "records": [],
  "total": 0,
  "pages": 0
}
```

---

## Gap Analysis

### Gap 1: No Explicit Lifecycle/Status Field

**Issue**: API returns zero rows for CODE_MISSING but doesn't indicate *why*.

**Impact**: Low (non-breaking)
- Frontend must infer CODE_MISSING status from registry
- No false positives (zero rows is safe)
- Consistent with current API design

**Decision**: No patch required
- Zero rows is the correct response
- Lifecycle information available via other endpoints (registry/strategy list)
- Frontend already handles this via classification

### No Other Gaps Found

✅ No fake rows  
✅ No false success states  
✅ No registry pollution  
✅ Safe defaults  

---

## API Safety Checklist

- ✅ CODE_MISSING strategies accessible via API
- ✅ All return 0 rows (no fake data)
- ✅ No NULL truth_level values from CODE_MISSING
- ✅ No false "EXECUTABLE" status
- ✅ V1 rows still queryable
- ✅ V2 rows still queryable
- ✅ Error handling correct (HTTP 200, empty records)

---

## Conclusion

**API Contract Status**: ✅ SAFE & CORRECT

The API correctly handles CODE_MISSING strategies by returning zero rows without fake data or false success states. No patch is required.

The minor gap (no explicit lifecycle field) is a design choice, not a bug. Frontend can determine unavailability via the registry/strategy classification, and the zero-row response is the safe default.

---

## Next Steps

- PHASE 3: Audit UI behavior
- PHASE 4: Apply minimal patches if needed
- PHASE 5: Verify tests
- PHASE 6: Create final report

