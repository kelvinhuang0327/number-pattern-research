# Post-V3 UI Regression Checklist

**Date**: 2026-05-14  
**Phase**: Post-V3 Release Audit — PHASE 3  
**Status**: Checklist Created  
**Classification**: UI_REGRESSION_VERIFICATION

---

## Executive Summary

Comprehensive UI regression checklist for all 16 lottery prediction strategies across three lifecycle categories (V1, V2, V3). This document provides:

1. **Visual Verification Tasks** — Manual checklist for UI testing
2. **Automated API Verification** — Backend contract validation ✅ PASS
3. **Data Integrity Checks** — Row count and schema validation
4. **Regression Tests** — Verify no breaking changes to existing UI

**Status**: ✅ API backend verified (16/16 strategies pass) | ⏳ Visual UI testing (user-dependent)

---

## Backend Verification Status (Automated)

✅ **API Regression Tests**: 16/16 PASS
- V1: 6/6 strategies return HTTP 200 with correct truth_level
- V2: 4/4 strategies return HTTP 200 with correct truth_level
- V3: 6/6 strategies return HTTP 200 with 0 rows (tombstone safe)

✅ **Response Contracts Verified**:
- All strategy endpoints accessible and returning valid JSON
- No fake or unexpected data
- truth_level field present and correct for V1/V2
- V3 tombstones properly isolated (0 rows, no expandable state)

---

## V1 EXECUTABLE_NOW — Visual Verification Checklist

**Category**: 6 strategies (biglotto_deviation_2bet, biglotto_triple_strike, daily539_f4cold, daily539_markov_cold, power_orthogonal_5bet, power_precision_3bet)

### Task V1-1: Strategy Selector Display

**What to test**: Strategy list in UI sidebar/dropdown

**Expected behavior**:
- [ ] All 6 V1 strategies appear in strategy selector dropdown
- [ ] Strategies listed under correct lottery (BIG_LOTTO, DAILY_539, POWER_LOTTO)
- [ ] Strategy names match registry exactly (no typos, correct case)
- [ ] Strategies are clickable (not disabled)

**How to verify**:
```
Frontend URL: http://localhost:3000
Location: Strategy Selector (sidebar or dropdown menu)
Expected: All 6 V1 strategies listed and selectable
```

**Status**: ⏳ Awaiting visual verification

---

### Task V1-2: V1 Badge Display

**What to test**: Badge/label showing "V1" or "REGENERATED_RETROSPECTIVE"

**Expected behavior**:
- [ ] Each V1 strategy displays a V1 badge (e.g., "V1", "REGENERATED", or similar)
- [ ] Badge color/styling is distinct from V2/V3 (e.g., different color scheme)
- [ ] Badge is visible on strategy list/card view
- [ ] Badge indicates: "This is a controlled/regenerated record"

**How to verify**:
```
Frontend: Hover over or click a V1 strategy to see badge/label
Expected display: V1 badge with distinct styling
```

**Status**: ⏳ Awaiting visual verification

---

### Task V1-3: V1 Expandable History View

**What to test**: Ability to expand and view prediction history

**Expected behavior**:
- [ ] V1 strategy shows "Expand" arrow or clickable area
- [ ] Clicking expands to show prediction history rows
- [ ] History table displays 50 rows (or paginated view)
- [ ] Columns present: target_draw, predicted_numbers, actual_numbers, hit_count
- [ ] truth_level column shows "REGENERATED_RETROSPECTIVE"
- [ ] No pagination errors (if rows > page_size)

**How to verify**:
```
Frontend: Click on a V1 strategy, then click expand arrow/button
Expected: History table appears with 50+ rows
Verify: truth_level column shows REGENERATED_RETROSPECTIVE for all rows
```

**Status**: ⏳ Awaiting visual verification

---

### Task V1-4: No Regression — V1 Still Works Post-V2/V3

**What to test**: V1 functionality unchanged after V2/V3 additions

**Expected behavior**:
- [ ] V1 history still expands (no regression)
- [ ] Row counts still show 50 per strategy
- [ ] truth_level field displays correctly
- [ ] V1 badge still visible (not removed/hidden)
- [ ] No 404 errors or broken links
- [ ] Performance not degraded (page load time acceptable)

**How to verify**:
```
1. Refresh browser
2. Navigate to "Replay History" or similar page
3. Click each V1 strategy
4. Verify expand/collapse works and data loads
5. Check console for JavaScript errors (F12 → Console tab)
```

**Status**: ⏳ Awaiting visual verification

---

## V2 ARTIFACT_ONLY — Visual Verification Checklist

**Category**: 4 strategies (biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, p1_deviation_2bet_539, power_shlc_midfreq)

### Task V2-1: V2 Strategy Visibility

**What to test**: V2 strategies appear in strategy selector

**Expected behavior**:
- [ ] All 4 V2 strategies appear in strategy selector
- [ ] Strategies are new (not duplicates of V1)
- [ ] Listed under correct lottery type
- [ ] Strategies are clickable

**How to verify**:
```
Frontend: Open strategy selector
Verify: See biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, etc.
```

**Status**: ⏳ Awaiting visual verification

---

### Task V2-2: V2 Badge Display

**What to test**: Badge/label showing "V2" or "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"

**Expected behavior**:
- [ ] Each V2 strategy displays a V2 badge (different from V1)
- [ ] Badge color/styling distinct from V1 (e.g., different color)
- [ ] Badge indicates: "This is artifact-reconstructed data"
- [ ] Badge visible on strategy list/card

**How to verify**:
```
Frontend: Hover over or click a V2 strategy
Expected: V2 badge appears with distinct styling (e.g., orange vs blue for V1)
```

**Status**: ⏳ Awaiting visual verification

---

### Task V2-3: V2 Expandable History View

**What to test**: V2 history expansion and display

**Expected behavior**:
- [ ] V2 strategy shows "Expand" arrow or clickable area
- [ ] Clicking expands to show prediction history rows
- [ ] History table displays 50 rows
- [ ] truth_level column shows "ARTIFACT_RECONSTRUCTED_RETROSPECTIVE"
- [ ] Other columns match V1 (target_draw, predicted_numbers, actual_numbers, hit_count)

**How to verify**:
```
Frontend: Click on a V2 strategy, then expand
Expected: History table appears with 50 rows
Verify: truth_level = ARTIFACT_RECONSTRUCTED_RETROSPECTIVE for all rows
```

**Status**: ⏳ Awaiting visual verification

---

### Task V2-4: No Collision With V1

**What to test**: V1 and V2 strategies don't interfere with each other

**Expected behavior**:
- [ ] V1 and V2 strategies are clearly separated (different badges)
- [ ] Clicking V1 doesn't show V2 data and vice versa
- [ ] No duplicate rows between V1 and V2
- [ ] Row counts correct for each (50 rows each)

**How to verify**:
```
1. Click V1 strategy, count rows
2. Click V2 strategy, count rows
3. Verify row counts match expected (50 for each)
4. Verify badge changes based on selection
```

**Status**: ⏳ Awaiting visual verification

---

## V3 CODE_MISSING — Visual Verification Checklist

**Category**: 6 strategies (acb_1bet, acb_markov_midfreq, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet, h6_gate_mk20_ew85)

### Task V3-1: V3 Strategies Listed But Unavailable

**What to test**: V3 strategies appear in list but marked unavailable

**Expected behavior**:
- [ ] All 6 V3 strategies appear in strategy registry/selector
- [ ] Each strategy displays "Unavailable" or "Code Missing" label
- [ ] Strategies are NOT clickable or expand-able (greyed out/disabled)
- [ ] Clear reason shown: "Implementation not available" or similar
- [ ] No expandable arrow or expand button for V3

**How to verify**:
```
Frontend: Open strategy selector
Verify: See acb_1bet, acb_markov_midfreq, etc.
Verify: Each shows "Unavailable" label
Verify: Cannot click to expand (button disabled or greyed out)
```

**Status**: ⏳ Awaiting visual verification

---

### Task V3-2: No False Empty Result

**What to test**: V3 doesn't show "no history found" or empty expanded state

**Expected behavior**:
- [ ] V3 strategies DO NOT have an "expand" arrow
- [ ] V3 strategies DO NOT show a table with 0 rows (no false success state)
- [ ] V3 strategies clearly marked as "Unavailable" (not "No data found")
- [ ] Reason visible: "Code/implementation missing" or similar tooltip

**How to verify**:
```
Frontend: Look at V3 strategy in list
Verify: NOT expandable (no arrow)
Verify: Shows "Unavailable" label (not "No results")
Verify: Cannot click to reveal empty table
```

**Status**: ⏳ Awaiting visual verification

---

### Task V3-3: No V3 Badge on Results

**What to test**: V3 strategies don't show truth_level badges

**Expected behavior**:
- [ ] V3 strategies do NOT display truth_level badges (no "V3" label)
- [ ] Do NOT show "REGENERATED" or "ARTIFACT" badges
- [ ] Clear "Unavailable" status is the primary indicator
- [ ] No confusing badge that implies data exists

**How to verify**:
```
Frontend: Check V3 strategy display
Verify: No V1/V2-style badges present
Verify: Only "Unavailable" label shown
```

**Status**: ⏳ Awaiting visual verification

---

### Task V3-4: Safe Tombstone Behavior

**What to test**: V3 design prevents accidental user confusion

**Expected behavior**:
- [ ] Hovering over V3 shows tooltip: "This strategy is not available"
- [ ] Clicking V3 (if clickable) shows message, doesn't expand
- [ ] No way to trigger false success state
- [ ] UI clearly communicates: "code missing, not zero data"

**How to verify**:
```
1. Hover over V3 strategy name
2. Check for tooltip/explanation
3. Try clicking (if allowed)
4. Verify user gets clear message
```

**Status**: ⏳ Awaiting visual verification

---

## Cross-Category Regression Tests

### Task X-1: No Breaking Changes to Existing UI

**What to test**: Adding V2/V3 didn't break V1 functionality

**Expected behavior**:
- [ ] V1 strategies still display correctly
- [ ] V1 history still expands and shows data
- [ ] V1 badges still visible
- [ ] No JavaScript console errors when navigating
- [ ] Page load times acceptable (no performance regression)

**How to verify**:
```
1. Open DevTools (F12)
2. Go to Console tab
3. Click through V1 strategies
4. Verify no errors in console
5. Check Network tab for failed requests (should be 0)
```

**Status**: ⏳ Awaiting visual verification

---

### Task X-2: Strategy Count Correct

**What to test**: Total strategy count reflects 16 strategies

**Expected behavior**:
- [ ] Strategy selector shows 16 total strategies
  - [ ] 6 V1 (EXECUTABLE_NOW)
  - [ ] 4 V2 (ARTIFACT_ONLY)
  - [ ] 6 V3 (CODE_MISSING)
- [ ] Count is accurate (not 10, not 20)

**How to verify**:
```
Frontend: Count visible strategies in dropdown/list
Expected: 16 total
Breakdown:
- BIG_LOTTO: 4 (2 V1 + 2 V2)
- DAILY_539: 6 (2 V1 + 1 V2 + 3 V3)
- POWER_LOTTO: 6 (2 V1 + 1 V2 + 3 V3)
```

**Status**: ⏳ Awaiting visual verification

---

### Task X-3: Lottery Type Distribution Correct

**What to test**: Strategies distributed correctly across lottery types

**Expected behavior**:
- [ ] BIG_LOTTO: 4 strategies (2 V1 + 2 V2)
- [ ] DAILY_539: 6 strategies (2 V1 + 1 V2 + 3 V3)
- [ ] POWER_LOTTO: 6 strategies (2 V1 + 1 V2 + 3 V3)

**How to verify**:
```
Frontend: Filter by lottery type
Count strategies in each category
Verify totals match expected breakdown
```

**Status**: ⏳ Awaiting visual verification

---

### Task X-4: Responsive UI on Mobile

**What to test**: UI works on mobile/tablet devices

**Expected behavior**:
- [ ] Strategy selector responsive (works on narrow screens)
- [ ] Badges/labels display correctly on mobile
- [ ] Expandable history view scrolls horizontally (tables don't overflow)
- [ ] Touch interactions work (tap to expand, etc.)

**How to verify**:
```
Chrome DevTools: Toggle device toolbar (Ctrl+Shift+M)
Test on: iPhone 12, iPad, Android device sizes
Verify: UI is readable and functional
```

**Status**: ⏳ Awaiting visual verification

---

## Data Integrity Verification

### Automated Checks ✅ PASS

**V1 Data**:
- ✅ 6 strategies × 50 rows = 300 rows in database
- ✅ All rows have truth_level = REGENERATED_RETROSPECTIVE
- ✅ All rows have controlled_apply_id = 20260514033100-13acaf34996e
- ✅ API returns 50 rows per strategy (correct pagination)

**V2 Data**:
- ✅ 4 strategies × 50 rows = 200 rows in database
- ✅ All rows have truth_level = ARTIFACT_RECONSTRUCTED_RETROSPECTIVE
- ✅ All rows have controlled_apply_id = 20260514134953-cf683424
- ✅ API returns 50 rows per strategy (correct pagination)

**V3 Data**:
- ✅ 6 strategies × 0 rows = 0 rows in database
- ✅ API returns 0 rows for all V3 strategies (safe tombstones)
- ✅ No fake rows present
- ✅ No false success states possible

**Legacy Data**:
- ✅ 460 legacy rows preserved (truth_level = NULL)
- ✅ No legacy data modified or deleted

**Total**: 960 rows confirmed ✅

---

## Visual Testing Environment Setup

### Prerequisites

1. **Frontend Running**:
   ```bash
   # Terminal 1: Start frontend
   cd frontend
   npm run dev
   # Accessible at: http://localhost:3000
   ```

2. **Backend Running**:
   ```bash
   # Terminal 2: Start backend
   cd lottery_api
   python -m uvicorn main:app --host 0.0.0.0 --port 8002
   # Accessible at: http://127.0.0.1:8002
   ```

3. **Browser DevTools**:
   - Open http://localhost:3000 in Chrome/Firefox
   - Open DevTools (F12)
   - Monitor Console for errors
   - Monitor Network for failed requests

---

## Regression Test Execution Order

1. **BACKEND FIRST** (Automated, Completed):
   - ✅ API endpoints all respond HTTP 200
   - ✅ Response schemas valid
   - ✅ Data integrity verified
   - ✅ V3 tombstones safe

2. **FRONTEND NEXT** (Manual, In Progress):
   - ⏳ V1 strategies display correctly
   - ⏳ V2 strategies display correctly
   - ⏳ V3 strategies marked unavailable
   - ⏳ No regressions from prior versions

3. **INTEGRATION FINAL** (Manual, In Progress):
   - ⏳ No console errors
   - ⏳ Page load performance acceptable
   - ⏳ Mobile responsiveness verified

---

## Sign-Off Checklist

### Ready for Visual Testing

- ✅ Backend API verified (16/16 endpoints)
- ✅ Data integrity confirmed (960 rows)
- ✅ Response contracts validated
- ✅ Checklist prepared for visual verification
- ✅ No blocking issues found

### Awaiting Visual Verification

- ⏳ V1 badge display
- ⏳ V1 expandable history
- ⏳ V2 badge display
- ⏳ V2 expandable history
- ⏳ V3 unavailable marking
- ⏳ V3 non-expandable state
- ⏳ No console errors
- ⏳ No regressions detected

---

## Next Steps

1. **User/Visual Testing**: Execute checklist items V1-1 through X-4
2. **Document Results**: Note any failures or unexpected behaviors
3. **Resolve Issues**: If failures detected, create bug report
4. **Approval**: Confirm all visual tests pass before release

---

## Sign-Off

**Status**: PHASE 3 COMPLETE — UI Regression Checklist Created  
**Date**: 2026-05-14  
**Backend Verification**: ✅ All 16 API endpoints PASS  
**Data Integrity**: ✅ 960 rows verified safe  
**Visual Testing**: ⏳ Ready for manual verification  
**Next**: PHASE 4 — Rollback Rehearsal Documentation
