# V3: CODE_MISSING Tombstone Inventory

**Date**: 2026-05-14  
**Purpose**: Identify and classify CODE_MISSING strategies for V3 hardening  
**Status**: Phase 1 Complete

---

## Summary

**Total Strategies**: 16
- EXECUTABLE_NOW: 6 (completed V1)
- ARTIFACT_ONLY: 4 (completed V2)
- CODE_MISSING: 6 (V3 target)

**V3 Focus**: 6 CODE_MISSING strategies requiring tombstone hardening

---

## CODE_MISSING Strategies

### Overview Table

| ID | Strategy | Lottery | Status | Reason | Expected |
|---|----------|---------|--------|--------|----------|
| 1 | acb_1bet | DAILY_539 | TOMBSTONE | No executable code | Unavailable |
| 2 | acb_markov_midfreq | DAILY_539 | TOMBSTONE | No executable code | Unavailable |
| 3 | acb_markov_midfreq_3bet | DAILY_539 | TOMBSTONE | No executable code | Unavailable |
| 4 | midfreq_acb_2bet | DAILY_539 | TOMBSTONE | No executable code | Unavailable |
| 5 | midfreq_fourier_2bet | DAILY_539 | TOMBSTONE | No executable code | Unavailable |
| 6 | h6_gate_mk20_ew85 | POWER_LOTTO | TOMBSTONE | No executable code | Unavailable |

---

## Detailed Strategy Analysis

### 1. acb_1bet (DAILY_539)

**Status**: CODE_MISSING (Tombstone)  
**Lottery Type**: DAILY_539  
**Expected Rows**: 0 (no rows in DB for this strategy)  
**Registry Status**: Present (as _LifecycleStub, non-executable)  

**Why CODE_MISSING**:
- No ACB (Anomaly Capture Bet) implementation for DAILY_539
- Strategy executor code not available
- Only metadata stub in registry

**Expected API/UI Behavior**:
- Should NOT appear in available strategies list
- Should NOT have expandable rows
- Should NOT show zero-row success state
- If listed at all, should show explicit "UNAVAILABLE - CODE_MISSING" status

---

### 2. acb_markov_midfreq (DAILY_539)

**Status**: CODE_MISSING (Tombstone)  
**Lottery Type**: DAILY_539  
**Expected Rows**: 0 (no rows in DB for this strategy)  
**Registry Status**: Present (as _LifecycleStub, non-executable)  

**Why CODE_MISSING**:
- Combination of ACB + Markov + Midfrequency not implemented
- No strategy executor available
- Marked as stub only

**Expected API/UI Behavior**:
- Explicitly unavailable, not silently absent
- No fake history rows
- Clear tombstone reason in lifecycle/status field

---

### 3. acb_markov_midfreq_3bet (DAILY_539)

**Status**: CODE_MISSING (Tombstone)  
**Lottery Type**: DAILY_539  
**Expected Rows**: 0 (no rows in DB for this strategy)  
**Registry Status**: Present (as _LifecycleStub, non-executable)  

**Why CODE_MISSING**:
- 3-bet variant of acb_markov_midfreq not implemented
- No code path available
- Strategy stub only

**Expected API/UI Behavior**:
- Marked as unavailable/tombstone
- No rows in any endpoint response
- Clear unavailability reason

---

### 4. midfreq_acb_2bet (DAILY_539)

**Status**: CODE_MISSING (Tombstone)  
**Lottery Type**: DAILY_539  
**Expected Rows**: 0 (no rows in DB for this strategy)  
**Registry Status**: Present (as _LifecycleStub, non-executable)  

**Why CODE_MISSING**:
- Midfrequency + ACB combination not executable
- Strategy source code not integrated
- Stub entry only

**Expected API/UI Behavior**:
- Should be explicitly marked as unavailable
- Not expandable
- Reason: code not available

---

### 5. midfreq_fourier_2bet (DAILY_539)

**Status**: CODE_MISSING (Tombstone)  
**Lottery Type**: DAILY_539  
**Expected Rows**: 0 (no rows in DB for this strategy)  
**Registry Status**: Present (as _LifecycleStub, non-executable)  

**Why CODE_MISSING**:
- Midfrequency + Fourier + 2-bet combination not available
- No executor code
- Metadata stub only

**Expected API/UI Behavior**:
- Unavailable status
- No rows returned
- Explicit tombstone reason

---

### 6. h6_gate_mk20_ew85 (POWER_LOTTO)

**Status**: CODE_MISSING (Tombstone)  
**Lottery Type**: POWER_LOTTO  
**Expected Rows**: 0 (no rows in DB for this strategy)  
**Registry Status**: Present (as _LifecycleStub, non-executable)  

**Why CODE_MISSING**:
- H6 gate with mk20→ew85 configuration not implemented
- Strategy code not available
- Stub entry only

**Expected API/UI Behavior**:
- Explicitly unavailable
- No fake rows
- Clear reason: code/implementation missing

---

## Comparison: CODE_MISSING vs ARTIFACT_ONLY vs EXECUTABLE_NOW

| Aspect | EXECUTABLE_NOW (V1) | ARTIFACT_ONLY (V2) | CODE_MISSING (V3) |
|--------|-------|-------|-----------|
| **Rows in DB** | Yes (50 each) | Yes (50 each) | No (0) |
| **truth_level** | REGENERATED_RETROSPECTIVE | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | N/A |
| **controlled_apply_id** | 20260514033100-13acaf34996e | 20260514134953-cf683424 | N/A |
| **API Response** | Returns rows | Returns rows | Tombstone/unavailable |
| **UI Behavior** | Expandable with rows | Expandable with rows | Not expandable, marked unavailable |
| **Registry** | Executable adapter | REJECTED stub | _LifecycleStub (non-executable) |

---

## V3 Hardening Objectives

For each CODE_MISSING strategy:

1. **API Contract**: Ensure endpoints clearly expose tombstone status
2. **UI Behavior**: Ensure UI displays unavailable/tombstone reason, not silent absence
3. **Test Coverage**: Lock in expected behavior with tests
4. **No DB Changes**: No rows added, no registry mutation without explicit review
5. **Clear Reason**: Tombstone reason documented and exposed

---

## Files Generated

- outputs/replay/v3_code_missing_inventory_20260514.md (this file)
- outputs/replay/v3_code_missing_inventory_20260514.json (structured data)

---

## Next Steps

1. **PHASE 2**: Audit API tombstone contract
2. **PHASE 3**: Audit UI tombstone behavior
3. **PHASE 4**: Apply minimal hardening patches if needed
4. **PHASE 5**: Verify tests
5. **PHASE 6**: Create final report
6. **PHASE 7**: Commit

