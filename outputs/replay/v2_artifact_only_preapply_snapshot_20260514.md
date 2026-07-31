# V2: ARTIFACT_ONLY Pre-Apply Snapshot & Restore Test

**Date**: 2026-05-14  
**Purpose**: Document DB state before V2 controlled apply  
**Status**: VERIFIED

---

## Snapshot Information

| Item | Value |
|------|-------|
| **Database** | lottery_api/data/lottery_v2.db |
| **Snapshot Path** | /tmp/lottery_v2.db.v2_artifact_snapshot_20260514_134528 |
| **Snapshot Time** | 2026-05-14 13:45:28 |
| **DB Hash (MD5)** | e564ee5e9ee67dacf7b653617af71668 |

---

## Pre-Apply Database State

### strategy_prediction_replays Table

```sql
SELECT COUNT(*) FROM strategy_prediction_replays;
-- Result: 760 rows
```

**Breakdown**:
- V1 Controlled Rows: 300 (truth_level='REGENERATED_RETROSPECTIVE', controlled_apply_id='20260514033100-13acaf34996e')
- Legacy Rows: 460 (truth_level=NULL)
- V2 Controlled Rows: 0 (not yet applied)

### Registry State

**File**: lottery_api/models/replay_strategy_registry.py  
**Hash (MD5)**: 3ea71cfc20c882714f3824ad68202f6e  
**Status**: Unchanged (expected)

---

## Snapshot Verification

### Hash Consistency

```bash
# Before creating snapshot
md5sum lottery_api/data/lottery_v2.db
# e564ee5e9ee67dacf7b653617af71668  lottery_api/data/lottery_v2.db

# Snapshot created
cp lottery_api/data/lottery_v2.db /tmp/lottery_v2.db.v2_artifact_snapshot_20260514_134528

# Verify snapshot hash
md5sum /tmp/lottery_v2.db.v2_artifact_snapshot_20260514_134528
# e564ee5e9ee67dacf7b653617af71668  /tmp/lottery_v2.db.v2_artifact_snapshot_20260514_134528

# Result: ✅ HASH MATCH
```

### Restore Test

```sql
-- Restore snapshot to test DB
cp /tmp/lottery_v2.db.v2_artifact_snapshot_20260514_134528 /tmp/v2_restore_test.db

-- Query restored DB
sqlite3 /tmp/v2_restore_test.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
-- Result: 760 rows
```

**Status**: ✅ Restore test successful

---

## Rollback Path

To restore original DB state if needed:

```bash
# Rollback procedure (if V2 apply fails)
cp /tmp/lottery_v2.db.v2_artifact_snapshot_20260514_134528 lottery_api/data/lottery_v2.db

# Verify restoration
md5sum lottery_api/data/lottery_v2.db
# Should return: e564ee5e9ee67dacf7b653617af71668
```

---

## Sign-Off

**Snapshot Status**: ✅ CREATED & VERIFIED  
**Hash Verified**: ✅ YES  
**Restore Test**: ✅ PASSED  
**Ready for Apply**: ✅ YES

