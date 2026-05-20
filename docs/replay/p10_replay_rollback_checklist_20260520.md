# P10 Replay Rollback Checklist — 2026-05-20

**Use this checklist if P7 ONLINE apply must be reversed.**  
**Rollback is only needed after a successful apply (rows = 488).**

---

## 1. Rollback Triggers

Execute rollback if ANY of the following conditions occur after apply:

| Trigger | Action |
|---------|--------|
| Post-apply rows ≠ 488 | Immediate rollback |
| API contract tests fail after apply | Immediate rollback |
| Drift guard fails after apply | Immediate rollback |
| RETIRED rows found in P7 ONLINE batch | Immediate rollback |
| Duplicate rows detected | Immediate rollback |
| `fake_success_count` > 0 after apply | Immediate rollback |
| UI shows incorrect data for new strategies | Investigate, then rollback if root cause unclear |

---

## 2. Pre-Rollback: Backup Verification

Before rolling back, verify the backup exists and is intact:

```bash
# Verify backup file exists
ls -la backups/lottery_v2_pre_p7_controlled_apply_20260520.db

# Verify backup row count = 460
sqlite3 backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"
# MUST return: 460
# If backup is missing or count ≠ 460, escalate to CTO before proceeding
```

---

## 3. Identify controlled_apply_id

The P7 apply tags every inserted row with a unique `controlled_apply_id`. Find it:

```bash
# From the apply result JSON
python3 -c "
import json
result = json.load(open('outputs/replay/p7_authorized_apply_result_20260520.json'))
print('rollback_batch_id:', result.get('rollback_batch_id'))
print('planned_insert_count:', result.get('planned_insert_count'))
"

# Cross-verify from DB
sqlite3 lottery_api/data/lottery_v2.db "
  SELECT DISTINCT controlled_apply_id, COUNT(*) as cnt
  FROM strategy_prediction_replays
  WHERE source='P7_CONTROLLED_APPLY'
  GROUP BY controlled_apply_id;
"
```

---

## 4. Rollback Strategy — Option A: Script-Based (Preferred)

```bash
# Dry-run preview (shows what would be deleted, no actual delete)
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --rollback-plan <controlled_apply_id> \
  --db lottery_api/data/lottery_v2.db

# Execute rollback
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --apply \
  --rollback-plan <controlled_apply_id> \
  --rollback-apply \
  --backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  --db lottery_api/data/lottery_v2.db
```

---

## 5. Rollback Strategy — Option B: SQL-Based (Fallback)

Use only if Option A fails:

```bash
# Preview rows to delete
sqlite3 lottery_api/data/lottery_v2.db "
  SELECT id, strategy_id, target_draw, lottery_type, controlled_apply_id
  FROM strategy_prediction_replays
  WHERE controlled_apply_id = '<controlled_apply_id>'
  ORDER BY id;
"

# Execute delete
sqlite3 lottery_api/data/lottery_v2.db "
  DELETE FROM strategy_prediction_replays
  WHERE controlled_apply_id = '<controlled_apply_id>';
"
```

---

## 6. Rollback Strategy — Option C: Full Restore from Backup (Emergency)

Use only if Options A and B fail or if data integrity is uncertain:

```bash
# STOP: confirm backup is intact first (step 2)
# Then restore from backup
cp lottery_api/data/lottery_v2.db \
   backups/lottery_v2_post_p7_pre_rollback_$(date +%Y%m%d_%H%M).db

sqlite3 backups/lottery_v2_pre_p7_controlled_apply_20260520.db ".dump" \
  | sqlite3 lottery_api/data/lottery_v2.db
```

---

## 7. Post-Rollback Row Count Check

```bash
sqlite3 lottery_api/data/lottery_v2.db \
  "SELECT COUNT(*) FROM strategy_prediction_replays;"
# MUST return: 460
# If ≠ 460, escalate immediately — data may be in inconsistent state
```

---

## 8. Post-Rollback Drift Guard

```bash
.venv/bin/python scripts/replay_lifecycle_drift_guard.py \
  --strict --json-out /tmp/post_rollback_drift_$(date +%Y%m%d_%H%M).json
# MUST return: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
```

---

## 9. Post-Rollback API Contract

```bash
.venv/bin/python -m pytest -q tests/test_replay_api_contract.py
# MUST return: 44/44 PASS
```

---

## 10. Incident Note Template

After rollback, file an incident note. Include:

```
INCIDENT: P7 ONLINE Apply Rollback — <date>

Trigger: <which condition from section 1>

Actions taken:
  1. <option used: A/B/C>
  2. controlled_apply_id: <value>
  3. Rows deleted: <count>

Post-rollback state:
  - Rows: 460
  - Drift guard: PASS/FAIL
  - API contract: PASS/FAIL

Root cause analysis:
  <describe what went wrong>

Next steps:
  <what needs to be fixed before re-attempting apply>
```

---

## Scope Reminders

These apply to rollback as well as forward apply:

- Rollback ONLY removes rows with the specific `controlled_apply_id`
- Do NOT delete any legacy rows (those with `controlled_apply_id = NULL`)
- Do NOT delete rows from other sources
- The 460 baseline rows must be preserved at all times
