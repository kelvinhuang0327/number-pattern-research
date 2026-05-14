# Phase 6: Commit & Push Checklist

**Date**: 2026-05-14  
**Status**: READY FOR EXECUTION (pending Phase 3 verification in deployment environment)  
**Branch**: `feature/phase4-required-check-20260509`  

---

## Pre-Commit Verification

### Code Changes Summary

**Files Modified**:
1. ✅ `lottery_api/routes/replay.py`
   - Line 152: Added `"truth_level": "FIXTURE_SYNTHETIC",` (fixture records)
   - Line 435: Added `truth_level` to SELECT clause (DB projection)
   - Line 467: Added `"truth_level": r["truth_level"],` (response serialization)

**Files Unchanged** (confirmed):
- ❌ DB schema files (no migration needed)
- ❌ `replay_strategy_registry.py` (no registry changes)
- ❌ Any write-path endpoints (read-only patch)

### Patch Syntax Verification

```python
# Line 152 - Fixture record
"truth_level": "FIXTURE_SYNTHETIC",  ✅ Correct JSON field

# Line 435 - SELECT clause
SELECT
    id, lottery_type, target_draw, target_date,
    strategy_id, strategy_name, strategy_version,
    history_cutoff_draw, replay_status, reject_reason,
    predicted_numbers, predicted_special,
    actual_numbers, actual_special,
    hit_numbers, hit_count, special_hit,
    replay_run_id, generated_at, truth_level  ✅ Correct projection
FROM strategy_prediction_replays

# Line 467 - Response dict
"truth_level": r["truth_level"],  ✅ Correct dict mapping
```

### Data Integrity Status

**DB State**:
- ✅ 300 controlled rows with `truth_level='REGENERATED_RETROSPECTIVE'`
- ✅ 460 legacy rows preserved (not modified)
- ✅ Controlled apply ID: `20260514033100-13acaf34996e`

**Generated Documentation**:
- ✅ `outputs/replay/p6_lite_api_truth_level_patch_report_20260514.md` (patch details)
- ✅ `outputs/replay/p6_lite_controlled_apply_report_20260514.md` (DB state & closure)
- ✅ `outputs/replay/p6_phase3_manual_testing_guide_20260514.md` (verification steps)
- ✅ `outputs/replay/p6_phase6_commit_checklist_20260514.md` (this document)

---

## Commit Message

```
V1: Expose replay truth_level and verify API schema (P6 closure)

Minimal patch: add truth_level field exposure to /api/replay/history endpoint.

**Changes**:
- Line 152: Add truth_level='FIXTURE_SYNTHETIC' to fixture records
- Line 435: Project truth_level column from DB SELECT
- Line 467: Include truth_level in response DTO serialization

**Verification**:
- DB: 300 controlled rows (20260514033100-13acaf34996e) with truth_level='REGENERATED_RETROSPECTIVE'
- Code: Patch applied to both LotteryNew-clean and LotteryNew repos
- Docs: P6 closure report, manual Phase 3 testing guide, all evidence generated
- Phase 3 live API verification: READY (manual curl tests in deployment environment)
- Phase 4 UI smoke test: PENDING Phase 3 verification

**Impact**:
- Read-only endpoint enhancement
- No DB mutations
- No schema changes
- Backward compatible

**Classification**: V1_API_TRUTH_LEVEL_PATCHED (awaiting Phase 3 verification)
```

---

## Git Status Before Commit

Run these to verify current state:

```bash
# Staged changes
git status

# Check only replay.py was modified
git diff --cached lottery_api/routes/replay.py

# Verify both repos are in sync
diff -u \
  /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/lottery_api/routes/replay.py \
  /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/routes/replay.py | head -50
```

---

## Steps to Commit (Execute in Order)

### Step 1: Stage the Changed File

```bash
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean

# Stage the patch file
git add lottery_api/routes/replay.py

# Verify it's staged
git status
# Expected output:
#   modified:   lottery_api/routes/replay.py (staged)
```

### Step 2: Stage Generated Documentation

```bash
# Stage the Phase 6 closure report and evidence files
git add outputs/replay/p6_lite_api_truth_level_patch_report_20260514.md
git add outputs/replay/p6_lite_controlled_apply_report_20260514.md
git add outputs/replay/p6_phase3_manual_testing_guide_20260514.md
git add outputs/replay/p6_phase6_commit_checklist_20260514.md

# Verify all staged
git status
```

### Step 3: Create Commit

```bash
git commit -m "V1: Expose replay truth_level and verify API schema (P6 closure)

Minimal patch: add truth_level field exposure to /api/replay/history endpoint.

**Changes**:
- Line 152: Add truth_level='FIXTURE_SYNTHETIC' to fixture records
- Line 435: Project truth_level column from DB SELECT
- Line 467: Include truth_level in response DTO serialization

**Verification**:
- DB: 300 controlled rows (20260514033100-13acaf34996e) with truth_level='REGENERATED_RETROSPECTIVE'
- Code: Patch applied to both LotteryNew-clean and LotteryNew repos
- Docs: P6 closure report, manual Phase 3 testing guide, all evidence generated
- Phase 3 live API verification: READY (manual curl tests in deployment environment)
- Phase 4 UI smoke test: PENDING Phase 3 verification

**Impact**:
- Read-only endpoint enhancement
- No DB mutations
- No schema changes
- Backward compatible

**Classification**: V1_API_TRUTH_LEVEL_PATCHED (awaiting Phase 3 verification)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

### Step 4: Verify Commit

```bash
# Check commit was created
git log --oneline -1
# Expected: V1: Expose replay truth_level...

# View commit details
git show --stat
# Expected: lottery_api/routes/replay.py, outputs/replay/...
```

### Step 5: Verify Both Repos in Sync (Optional)

```bash
# Copy patch to main repo if using separate workspaces
cp /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/lottery_api/routes/replay.py \
   /Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/routes/replay.py

# Commit in main repo too (if required)
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew
git add lottery_api/routes/replay.py
git commit -m "V1: Expose replay truth_level and verify API schema (P6 closure)

[Same commit message as above]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Phase 3 Verification Prerequisites (Before Push)

**✅ DO NOT push until:**

1. Manual Phase 3 testing completed in deployment environment with proper Python/fastapi setup
2. All 6 strategy curl tests return 200 with `"truth_level": "REGENERATED_RETROSPECTIVE"`
3. Fixture mode test confirms `"truth_level": "FIXTURE_SYNTHETIC"`
4. Phase 3 results documented in `outputs/replay/p6_phase3_api_verification_results_20260514.md`

**If Phase 3 cannot be completed before push:**
- Push with current status: `V1_API_TRUTH_LEVEL_PATCHED` (code verified, live verification deferred)
- Document deferral reason in commit message or separate file
- Mark in PR description: "Phase 3 verification pending deployment environment"

---

## Push Instructions (After Phase 3 Complete)

```bash
# Verify no uncommitted changes
git status
# Expected: nothing to commit, working tree clean

# Push to feature branch
git push origin feature/phase4-required-check-20260509

# Expected output:
# branch 'feature/phase4-required-check-20260509' set up to track 'origin/feature/phase4-required-check-20260509'.
```

---

## Post-Commit Actions

### Create Pull Request (Optional)

If using GitHub, create PR with:
- **Title**: `V1: Expose replay truth_level and complete API schema`
- **Base**: `main`
- **Head**: `feature/phase4-required-check-20260509`

**Description**:
```markdown
## Summary

Expose `truth_level` field in `/api/replay/history` endpoint to complete Phase 8 API contract verification.

- ✅ Code patch: minimal 3-line change (SELECT, response dict, fixtures)
- ✅ DB integrity: 300 controlled rows verified
- ✅ Documentation: closure report + manual testing guide
- ⏳ Phase 3 verification: pending deployment environment setup

## Test Plan

- [ ] Phase 3 live verification: 6 curl tests for all strategies
- [ ] Fixture mode: verify `truth_level='FIXTURE_SYNTHETIC'`
- [ ] Row count: confirm 50 rows per strategy
- [ ] Legacy rows: confirm 460 legacy rows preserved
- [ ] Phase 4 UI smoke: verify badge renders correctly

See: `outputs/replay/p6_phase3_manual_testing_guide_20260514.md` for detailed instructions.

🤖 Generated with Claude Code
```

### Merge Strategy

After Phase 3 verification completes:

```bash
# Switch to main
git checkout main

# Pull latest
git pull origin main

# Merge feature branch
git merge --no-ff feature/phase4-required-check-20260509 \
  -m "Merge V1 API truth_level patch (Phase 6 closure)"

# Push to main
git push origin main
```

---

## Rollback Plan (If Needed)

### Before Push

```bash
# Undo last commit (keep changes staged)
git reset --soft HEAD~1

# Or undo completely
git reset --hard HEAD~1
```

### After Push (Hard Reset - Use with Caution)

```bash
# Only if push was rejected or needs immediate correction
git reset --hard <previous-commit-hash>
git push --force origin feature/phase4-required-check-20260509
```

**Database Rollback** (if needed):

```bash
# Script-based
bash tools/rollback_apply_20260514033100.sh

# Or snapshot-based
sqlite3 lottery_api/data/lottery_v2.db < \
  outputs/replay/p6_lite_preapply_snapshot_20260514.md
```

---

## Success Criteria

✅ **V1_API_TRUTH_LEVEL_PATCHED** (Current)
- Code patch applied and committed
- DB state verified
- Documentation complete

✅ **V1_API_TRUTH_LEVEL_VERIFIED** (After Phase 3)
- Live curl tests pass on all 6 strategies
- `truth_level` field present and correct value
- HTTP 200 response confirmed

✅ **V1_UI_SMOKE_PASS** (After Phase 4)
- Frontend displays 6 strategies with 50 rows each
- Truth-level badge renders correctly

✅ **V1_CLOSURE_COMPLETE** (After Phase 6)
- Merged to main
- All documentation in place
- Project marked as complete

---

## Notes

- **Phase 3 Blocker**: Local environment lacks fastapi/uvicorn. Manual testing guide prepared for deployment environment execution.
- **Current Working Directory**: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean`
- **Branch Name**: `feature/phase4-required-check-20260509`
- **Commit Author**: Claude Sonnet 4.6
- **Timeline**: Phase 3 verification required before final merge

