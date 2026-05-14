# V2: ARTIFACT_ONLY Controlled Apply — Readiness Report

**Date**: 2026-05-14  
**Status**: READY FOR APPLY (authorization pending)  
**Classification**: V2_CONTROLLED_APPLY_READY_BUT_AUTHORIZATION_MISSING

---

## Executive Summary

✅ **V2 ARTIFACT_ONLY Controlled Apply is READY for production**

All pre-apply validation phases (0-4) have been completed successfully:
- Baseline verified (main branch synced with V1 + V2 commits)
- Candidate artifacts validated (200 rows, 4 strategies × 50)
- Database snapshot created and restore tested
- Schema compatibility confirmed
- Controlled apply script tested in dry-run mode
- Zero blocking issues detected

**Status**: Awaiting explicit user authorization to proceed with live apply.

---

## Phase Completion Summary

| Phase | Objective | Status | Evidence |
|-------|-----------|--------|----------|
| **0** | Baseline & branch sync | ✅ PASS | Commit 8ccdf88 (V1) + 7cdbbbe (V2) on main |
| **1** | Candidate artifact validation | ✅ PASS | 200 rows, 4×50 per strategy, 100% valid |
| **2** | DB snapshot & restore test | ✅ PASS | Hash verified (e564ee5e9ee67dacf7b653617af71668) |
| **3** | Schema compatibility | ✅ PASS | All 11 required columns present |
| **4** | Controlled apply dry-run | ✅ PASS | 200/200 would insert, 0 invalid, 0 skip |

---

## Validation Results

### PHASE 0: Baseline Verification ✅

**Branch**: main  
**Commits**:
- 8ccdf88: V1 Complete P6-lite replay truth-level closure
- 7cdbbbe: V2 Add ARTIFACT_ONLY parser dry-run evidence

**Status**: ✅ SYNCED & VERIFIED

### PHASE 1: Candidate Artifact Validation ✅

**File**: outputs/replay/v2_artifact_only_candidate_rows_20260514.jsonl

| Metric | Value | Status |
|--------|-------|--------|
| Total rows | 200 | ✅ Correct |
| biglotto_ts3_acb_4bet | 50 | ✅ |
| biglotto_ts3_markov_freq_5bet | 50 | ✅ |
| p1_deviation_2bet_539 | 50 | ✅ |
| power_shlc_midfreq | 50 | ✅ |
| dry_run_only=true | 200/200 | ✅ 100% |
| leakage_guard_pass=true | 200/200 | ✅ 100% |
| controlled_apply_id=null | 200/200 | ✅ 100% |
| truth_level consistent | 200/200 | ✅ 100% |
| required fields present | 200/200 | ✅ 100% |

**Status**: ✅ ALL PASS

### PHASE 2: DB Snapshot & Restore Test ✅

**Database**: lottery_api/data/lottery_v2.db

**Pre-Apply State**:
- Total rows: 760
  - V1 controlled: 300 (truth_level='REGENERATED_RETROSPECTIVE')
  - Legacy null: 460 (truth_level=NULL)
  - V2 controlled: 0 (not yet applied)

**Snapshot Evidence**:
- Path: /tmp/lottery_v2.db.v2_artifact_snapshot_20260514_134528
- Hash (MD5): e564ee5e9ee67dacf7b653617af71668
- Hash verified: ✅ Match
- Restore test: ✅ 760 rows recovered

**Rollback Path**: Restore from snapshot or selective DELETE by controlled_apply_id

**Status**: ✅ SNAPSHOT CREATED & VERIFIED

### PHASE 3: Schema Compatibility ✅

**Table**: strategy_prediction_replays

**Required Columns** (all present):
1. ✅ strategy_id (TEXT)
2. ✅ target_draw (TEXT)
3. ✅ predicted_numbers (TEXT, JSON)
4. ✅ actual_numbers (TEXT, JSON)
5. ✅ hit_count (INTEGER)
6. ✅ truth_level (TEXT)
7. ✅ source (TEXT)
8. ✅ provenance_hash (TEXT)
9. ✅ provenance_source (TEXT)
10. ✅ controlled_apply_id (TEXT)
11. ✅ dry_run_only (INTEGER)

**Support Columns**:
- ✅ lottery_type, target_date, predicted_special, actual_special
- ✅ hit_numbers, special_hit
- ✅ generated_at (auto-populated)

**Insert Strategy**:
- JSON serialization for number arrays
- Idempotency: Skip if (strategy_id, target_draw, truth_level) exists
- Controlled apply tracking via controlled_apply_id

**Status**: ✅ SCHEMA OK (no alterations required)

### PHASE 4: Controlled Apply Dry-run ✅

**Script**: scripts/v2_artifact_only_apply_rows.py

**Dry-run Results**:
```
Would insert: 200
Would skip (existing): 0
Invalid rows: 0

Per-Strategy:
- biglotto_ts3_acb_4bet: 50 would insert
- biglotto_ts3_markov_freq_5bet: 50 would insert
- p1_deviation_2bet_539: 50 would insert
- power_shlc_midfreq: 50 would insert
```

**Status**: ✅ DRYRUN PASS (Ready for controlled apply)

---

## Readiness Checklist

### Candidate Artifacts ✅
- ✅ All 200 rows valid
- ✅ No EXECUTABLE_NOW strategies mixed in
- ✅ No CODE_MISSING strategies mixed in
- ✅ All rows marked dry_run_only=true
- ✅ All rows have null controlled_apply_id

### Database Safety ✅
- ✅ Snapshot created
- ✅ Restore capability verified
- ✅ Registry unchanged (not to be modified)
- ✅ V1 rows protected (300 controlled rows)
- ✅ Legacy rows preserved (460 null rows)

### Schema ✅
- ✅ All required columns exist
- ✅ No schema alterations needed
- ✅ Backward compatible
- ✅ Insert mappings defined
- ✅ Idempotency strategy documented

### Application Script ✅
- ✅ Dry-run validation passed
- ✅ Transaction support implemented
- ✅ Controlled apply ID generation ready
- ✅ Rollback capability built-in
- ✅ Apply log creation ready

---

## Controlled Apply Script Capabilities

### Command: Apply

```bash
python3 scripts/v2_artifact_only_apply_rows.py --apply
```

**Behavior**:
- Generates V2 controlled_apply_id (timestamp-based)
- Validates each of 200 rows before insert
- Inserts all 200 rows in single transaction
- Sets dry_run_only=0 (production)
- Sets source='v2_artifact_only_controlled_apply'
- Sets controlled_apply_id on each row
- Writes apply log (JSONL format)
- Verifies insertion post-commit

**Expected Output**:
- Inserted: 200
- Skipped: 0
- Invalid: 0
- controlled_apply_id: <timestamp-hash>

### Command: Rollback

```bash
python3 scripts/v2_artifact_only_apply_rows.py --rollback <apply_id>
```

**Behavior**:
- Deletes only rows matching the V2 controlled_apply_id
- Does NOT touch V1 controlled rows
- Does NOT touch legacy null rows
- Single transaction
- Verifies deletion post-commit

**Expected Output**:
- Deleted: 200 rows (or 0 if not found)
- Registry unchanged
- V1 rows untouched

---

## Post-Apply Verification Plan

### Expected State After Apply

| Metric | Before | After | Check |
|--------|--------|-------|-------|
| Total rows | 760 | 960 | +200 |
| V1 controlled (300) | 300 | 300 | Unchanged |
| Legacy null (460) | 460 | 460 | Unchanged |
| V2 controlled | 0 | 200 | New |
| strategies | 6 | 10 | +4 (ARTIFACT_ONLY) |

### API Verification (PHASE 6)

Will verify:
- HTTP 200 on /api/replay/history for each V2 strategy
- truth_level='ARTIFACT_RECONSTRUCTED_RETROSPECTIVE'
- predicted_numbers, actual_numbers, hit_count present
- V1 rows still accessible for original 6 strategies

### UI Smoke Test (PHASE 7)

Will verify:
- 4 ARTIFACT_ONLY strategies now expandable
- Badge displays V2 truth_level correctly
- V1 6 strategies still functional
- CODE_MISSING remains tombstone

---

## Safety Measures

### Before Apply
- ✅ Database snapshot created
- ✅ Registry hash recorded
- ✅ Dry-run validation passed
- ✅ All rows certified valid

### During Apply
- ✅ Single transaction (ACID)
- ✅ Row validation before insert
- ✅ Idempotency check (skip if exists)
- ✅ Controlled apply ID tracking

### After Apply
- ✅ Verification query confirms count
- ✅ Apply log written (100% traceability)
- ✅ Rollback capability available
- ✅ Registry unchanged

### Rollback Available
- ✅ Restore from snapshot path
- ✅ Selective delete by controlled_apply_id
- ✅ V1 & legacy rows untouched

---

## Known Constraints

### No Modifications
- ❌ Registry: NOT modified
- ❌ CODE_MISSING strategies: NOT processed
- ❌ EXECUTABLE_NOW strategies: NOT included
- ❌ V1 rows: NOT modified
- ❌ Strategy mining: NOT performed

### Strictly Dry-run
- ❌ DB writes: Only with explicit --apply flag
- ❌ Early apply: Not permitted without authorization
- ❌ Partial apply: All-or-nothing (200 rows)

---

## Files Ready for Commit (After Apply)

```
scripts/v2_artifact_only_apply_rows.py
outputs/replay/v2_artifact_only_preapply_snapshot_20260514.md
outputs/replay/v2_artifact_only_schema_decision_20260514.md
outputs/replay/v2_artifact_only_controlled_apply_report_20260514.md
outputs/replay/v2_artifact_only_apply_log_<apply_id>.jsonl
```

---

## Authorization Required

### To Proceed with Live Apply

**Explicit user authorization needed**:

```
YES apply V2 ARTIFACT_ONLY controlled rows
```

**Without authorization**: This report documents readiness only; no DB modifications will occur.

---

## Success Markers Achieved (Readiness Phase)

✅ V2_CANDIDATE_ARTIFACT_VALIDATED  
✅ V2_SNAPSHOT_RESTORE_TESTED  
✅ V2_SCHEMA_OK  
✅ V2_DRYRUN_APPLY_PASS  
✅ V2_CONTROLLED_APPLY_READY_BUT_AUTHORIZATION_MISSING

---

## Next Steps

### If Authorization Received

Execute PHASE 5 (Apply Gate):
```bash
python3 scripts/v2_artifact_only_apply_rows.py --apply
```

Then proceed to:
- PHASE 6: API Verification
- PHASE 7: UI Smoke Testing  
- PHASE 8: Final Report & Commit

### If No Authorization

This readiness report documents:
- All pre-apply checks: PASS
- Candidate artifacts: VALID
- Database state: SAFE
- Schema: COMPATIBLE
- Application: TESTED & READY

---

## Final Classification

**V2_CONTROLLED_APPLY_READY_BUT_AUTHORIZATION_MISSING**

All readiness criteria met. Awaiting explicit user authorization to proceed with live controlled apply.

---

## Sign-Off

**Readiness Status**: ✅ COMPLETE  
**Date**: 2026-05-14  
**Authorization Status**: AWAITING  
**DB Modifications Made**: 0  
**Ready for Apply**: YES  

---

## Appendix: Supporting Documentation

1. `v2_artifact_only_preapply_snapshot_20260514.md` — Snapshot verification
2. `v2_artifact_only_schema_decision_20260514.md` — Schema analysis
3. `v2_artifact_only_parser_contract_20260514.md` — Row specification
4. `v2_artifact_only_dryrun_validation_report_20260514.md` — Dry-run evidence
5. `v2_artifact_only_parser_dryrun_report_20260514.md` — Parser completion

