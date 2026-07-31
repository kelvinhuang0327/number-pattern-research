# Post-V3 Release Gate — Test Sweep

**Date**: 2026-05-14  
**Commit**: bb107ff  
**Mode**: READ-ONLY tests — no DB writes

---

## Test Run 1: Truth-Level Contract Tests (New)

**File**: `tests/test_replay_truth_level_contract.py`  
**Command**: `pytest tests/test_replay_truth_level_contract.py -v --tb=short`

### Results

| Test Class | Tests | PASS | FAIL |
|-----------|-------|------|------|
| `TestV1TruthLevelContract` | 24 | **24** | 0 |
| `TestV2TruthLevelContract` | 8 | **8** | 0 |
| `TestTruthLevelFieldsAlwaysPresent` | 5 | **5** | 0 |
| **Total** | **37** | **37** | **0** |

**Result**: ✅ 37/37 PASS (0.55s)

### Coverage

| Contract | Verified |
|----------|---------|
| V1 page-1 all REGENERATED_RETROSPECTIVE | ✅ 6 strategies |
| V1 page-1 all have controlled_apply_id=20260514033100-13acaf34996e | ✅ 6 strategies |
| V1 page-1 source and provenance_hash not null | ✅ 6 strategies |
| V1 records ordered by draw NUMERIC DESC (text-sort bug guard) | ✅ 6 strategies |
| V2 page-1 all ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | ✅ 4 strategies |
| V2 page-1 controlled_apply_id=20260514134953-cf683424 | ✅ 4 strategies |
| truth_level key always present in records | ✅ |
| controlled_apply_id key always present | ✅ |
| source key always present | ✅ |
| provenance_hash key always present | ✅ |
| Legacy rows have null truth_level (protected, not reclassified) | ✅ |

---

## Test Run 2: Existing Replay API Contract Tests

**File**: `tests/test_replay_api_contract.py`  
**Command**: `pytest tests/test_replay_api_contract.py -v --tb=short`

### Results

| Test Class | Tests | PASS | FAIL |
|-----------|-------|------|------|
| `TestFreshnessContract` | 14 | **14** | 0 |
| `TestSummaryContract` | 11 | **11** | 0 |
| `TestHistoryContract` | 12 | **12** | 0 |
| `TestHistoryFixtureModeContract` | 7 | **7** | 0 |
| **Total** | **44** | **44** | **0** |

**Result**: ✅ 44/44 PASS (0.30s)

---

## Combined Test Sweep Summary

| Suite | Tests | PASS | FAIL | Result |
|-------|-------|------|------|--------|
| truth-level contract | 37 | 37 | 0 | ✅ PASS |
| replay API contract | 44 | 44 | 0 | ✅ PASS |
| **Total** | **81** | **81** | **0** | ✅ **ALL PASS** |

---

**Test Sweep Result**: ✅ 81/81 PASS  
**No regressions introduced.** Existing contracts preserved. New truth-level contracts enforced.
