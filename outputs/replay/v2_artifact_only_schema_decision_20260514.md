# V2: ARTIFACT_ONLY Schema Compatibility Decision

**Date**: 2026-05-14  
**Purpose**: Document schema readiness for V2 controlled apply  
**Status**: APPROVED

---

## Schema Analysis

### Target Table

**Table**: strategy_prediction_replays  
**DB**: lottery_api/data/lottery_v2.db

### Required Fields for V2 Apply

| Field | Type | In Schema | Status |
|-------|------|-----------|--------|
| strategy_id | TEXT | ✅ | REQUIRED |
| target_draw | TEXT | ✅ | REQUIRED |
| predicted_numbers | TEXT | ✅ | JSON array (stored as TEXT) |
| actual_numbers | TEXT | ✅ | JSON array (stored as TEXT) |
| hit_count | INTEGER | ✅ | REQUIRED |
| truth_level | TEXT | ✅ | REQUIRED |
| source | TEXT | ✅ | REQUIRED |
| provenance_hash | TEXT | ✅ | REQUIRED |
| provenance_source | TEXT | ✅ | REQUIRED |
| controlled_apply_id | TEXT | ✅ | REQUIRED (FK for apply tracking) |
| dry_run_only | INTEGER | ✅ | REQUIRED (0=production, 1=dry-run) |

### Supporting Fields

| Field | Type | Purpose |
|-------|------|---------|
| lottery_type | TEXT | Lottery classification |
| target_date | TEXT | Human-readable draw date |
| predicted_special | INTEGER | Special ball (POWER_LOTTO) |
| actual_special | INTEGER | Actual special ball |
| hit_numbers | TEXT | JSON array of hit numbers |
| special_hit | INTEGER | Special ball match flag |

---

## Compatibility Verification

### Full Column List

```
0|id|INTEGER
1|lottery_type|TEXT
2|target_draw|TEXT
3|target_date|TEXT
4|strategy_id|TEXT
5|strategy_name|TEXT
6|strategy_version|TEXT
7|history_cutoff_draw|TEXT
8|replay_status|TEXT
9|reject_reason|TEXT
10|predicted_numbers|TEXT
11|predicted_special|INTEGER
12|actual_numbers|TEXT
13|actual_special|INTEGER
14|hit_numbers|TEXT
15|hit_count|INTEGER
16|special_hit|INTEGER
17|replay_run_id|INTEGER
18|generated_at|TEXT
19|truth_level|TEXT
20|source|TEXT
21|provenance_hash|TEXT
22|provenance_source|TEXT
23|controlled_apply_id|TEXT
24|dry_run_only|INTEGER
```

**Status**: ✅ All required fields present

---

## Insert Strategy

### For V2 ARTIFACT_ONLY Rows

**Source**: v2_artifact_only_candidate_rows_20260514.jsonl (200 rows)

**Column Mapping**:

| V2 Field | DB Column | Transformation |
|----------|-----------|-----------------|
| strategy_id | strategy_id | Direct |
| lottery_type | lottery_type | Direct |
| target_draw | target_draw | Direct |
| target_date | target_date | Direct |
| predicted_numbers (array) | predicted_numbers | JSON.stringify() |
| predicted_special | predicted_special | Direct (null for non-POWER) |
| actual_numbers (array) | actual_numbers | JSON.stringify() |
| actual_special | actual_special | Direct (null for non-POWER) |
| hit_numbers (array) | hit_numbers | JSON.stringify() |
| hit_count | hit_count | Direct |
| special_hit | special_hit | Direct |
| — | truth_level | Set to 'ARTIFACT_RECONSTRUCTED_RETROSPECTIVE' |
| — | source | Set to 'v2_artifact_only_controlled_apply' |
| provenance_source | provenance_source | Direct |
| provenance_hash | provenance_hash | Direct |
| — | controlled_apply_id | Generated (timestamp-based) |
| — | dry_run_only | Set to 0 (production) |

### Unchanged Columns

These columns will NOT be populated from V2 candidates:
- strategy_name (already filled from registry)
- strategy_version (already filled from registry)
- history_cutoff_draw (from artifact metadata)
- replay_status (default handling)
- reject_reason (N/A for artifact reconstruct)
- replay_run_id (N/A for artifact reconstruct)
- generated_at (auto-populated by DEFAULT)

---

## Data Integrity Checks

### No Breaking Changes

✅ No schema alteration required  
✅ No column additions required  
✅ No column deletions needed  
✅ All V2 fields map to existing columns

### Backward Compatibility

✅ V1 rows (300 in DB) unchanged  
✅ Legacy rows (460 in DB) unchanged  
✅ Registry unchanged  
✅ No constraints violated

### Idempotency

Strategy for insert idempotency:

```sql
-- Check before insert
SELECT COUNT(*) FROM strategy_prediction_replays
WHERE strategy_id = ? AND target_draw = ? AND truth_level = 'ARTIFACT_RECONSTRUCTED_RETROSPECTIVE'

-- If count > 0: SKIP (row already exists)
-- If count == 0: INSERT
```

---

## Post-Apply Expectations

After inserting 200 V2 rows:

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total rows | 760 | 960 | +200 |
| V1 controlled | 300 | 300 | +0 |
| Legacy null | 460 | 460 | +0 |
| V2 controlled | 0 | 200 | +200 |
| Strategies | 6 | 10 | +4 (ARTIFACT_ONLY) |

---

## Rollback Path

If any issue detected post-apply:

```bash
# Restore from snapshot
cp /tmp/lottery_v2.db.v2_artifact_snapshot_20260514_134528 lottery_api/data/lottery_v2.db

# Or selective delete
sqlite3 lottery_api/data/lottery_v2.db << 'SQL'
DELETE FROM strategy_prediction_replays
WHERE controlled_apply_id = '<V2_apply_id>';
SQL
```

---

## Sign-Off

**Schema Status**: ✅ APPROVED  
**Compatibility**: ✅ VERIFIED  
**Ready for Apply**: ✅ YES  
**Decision**: Proceed with controlled apply using existing schema

