# P129B — Production bet_index Schema Migration Execution

**Task ID:** P129B
**Classification:** `P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED`
**Generated:** 2026-05-28 08:00 UTC

---

## 1. Executive Summary

P129B executed the corrected 18-step SQLite table-recreation migration on the **production database**.
The migration used ROW_NUMBER() in the COPY step (corrected by P129 rehearsal) to handle 120
duplicate (strategy, draw) groups safely.

| Check | Result |
|---|---|
| Authorization phrase present | ✓ PASS |
| Backup created and verified | ✓ PASS |
| 18-step migration completed | ✓ PASS |
| Corrected ROW_NUMBER() COPY used | ✓ PASS |
| bet_index column added | ✓ PASS |
| New UNIQUE constraint active | ✓ PASS |
| All 54462 rows preserved | ✓ PASS |
| bet_index distribution correct | ✓ PASS |
| No invalid bet_index rows | ✓ PASS |
| UNIQUE constraint rejects duplicates | ✓ PASS |
| Multi-bet (bet_index 1,2,3) allowed | ✓ PASS |
| P126 apply executed | ✗ BLOCKED (not executed — requires per-strategy phrases) |

---

## 2. Authorization Confirmation

| Field | Value |
|---|---|
| Exact required phrase | `YES authorize migration_plan_p128 because <reason>` |
| Authorization present | `True` |
| Migration allowed | `True` |
| Authorization text observed | `YES authorize migration_plan_p128 because P129A gate confirmed corrected ROW_NUMBER migration is required and rehearsal preserved all 54462 rows` |
| Reason | `P129A gate confirmed corrected ROW_NUMBER migration is required and rehearsal preserved all 54462 rows` |

---

## 3. P129A / P129 Rehearsal Recap

- **P129A:** `P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION` — gate confirmed rehearsal valid, migration blocked pending authorization
- **P129:** `P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY` — 18-step migration rehearsed on temp DB, all 54462 rows preserved
- **Key finding from P129:** 120 duplicate (strategy, draw) groups require ROW_NUMBER() COPY SQL
- **ROW_NUMBER() required:** `True`

---

## 4. Backup Creation and Verification

| Field | Value |
|---|---|
| Backup path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/backups/lottery_v2.db.p129b_backup_20260528T080035Z.db` |
| Backup created | `True` |
| Backup row count | `54462` |
| Backup verification | `PASS` |

**Rollback command (if needed):**
```bash
cp '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/backups/lottery_v2.db.p129b_backup_20260528T080035Z.db' '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db'
```

---

## 5. Corrected ROW_NUMBER() Migration SQL Summary

P128 original step 4 (WOULD FAIL for 120 duplicate groups):
```sql
-- NAIVE — fails with UNIQUE constraint for duplicate (strategy, draw) groups
INSERT INTO strategy_prediction_replays_new
SELECT ..., 1 AS bet_index FROM strategy_prediction_replays
```

**Corrected step 4 (used in P129B production migration):**
```sql
INSERT INTO strategy_prediction_replays_new
SELECT id, lottery_type, target_draw, target_date, strategy_id,
       strategy_name, strategy_version, history_cutoff_draw, replay_status,
       reject_reason, predicted_numbers, predicted_special, actual_numbers,
       actual_special, hit_numbers, hit_count, special_hit, replay_run_id,
       generated_at, truth_level, controlled_apply_id, source, provenance_hash,
       provenance_source, dry_run, prediction_cutoff_date, prediction_generated_at,
       ROW_NUMBER() OVER (
         PARTITION BY lottery_type, target_draw, strategy_id
         ORDER BY id
       ) AS bet_index
FROM strategy_prediction_replays
```

This assigns `bet_index = 1` to the first (lowest id) row per (strategy, draw) group,
and `bet_index = 2, 3, ...` to subsequent rows. All 54462 rows are preserved.

---

## 6. Schema Before / After

### Before Migration
- `bet_index` column: **NOT present**
- UNIQUE constraint: `UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)`
- Columns: 27

### After Migration
- `bet_index` column: **PRESENT** (`INTEGER NOT NULL DEFAULT 1`)
- UNIQUE constraint: `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`
- `replay_run_id` removed from UNIQUE (still a column, just not in the constraint)
- Columns: 28
- New index: `idx_spr_bet_index ON strategy_prediction_replays(bet_index)`
- All indexes: 10

---

## 7. bet_index Distribution

| bet_index | Rows | Notes |
|---|---|---|
| 1 | 54,302 | Primary/single-bet rows |
| 2 | 120 | Old multi-run duplicate rows |
| 3 | 40 | Old multi-run duplicate rows |

| Metric | Expected | Actual | Status |
|---|---|---|---|
| Total rows | 54,462 | 54,462 | ✓ PASS |
| Rows bet_index = 1 | 54,302 | 54,302 | ✓ PASS |
| Rows bet_index > 1 | 160 | 160 | ✓ PASS |
| Invalid (NULL / < 1) | 0 | 0 | ✓ PASS |

---

## 8. Replay Row Preservation Result

| Metric | Value |
|---|---|
| Expected rows | 54,462 |
| Actual rows after migration | 54,462 |
| Rows preserved | ✓ PASS |

**Result:** `✓ PASS`

---

## 9. Unique Constraint Validation

| Test | Result |
|---|---|
| Insert duplicate (strategy, draw, bet_index=1) × 2 → rejected | ✓ PASS |
| Insert (strategy, draw, bet_index=1,2,3) → all accepted | ✓ PASS |
| Constraint works as expected | ✓ PASS |

---

## 10. P126 Apply Remains Blocked

Schema migration is complete. However, P126 apply is **BLOCKED** pending 5 individual
per-strategy authorization phrases from Kelvin:

```
YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>
YES authorize controlled_apply for daily539_f4cold_5bet because <reason>
YES authorize controlled_apply for daily539_f4cold_3bet because <reason>
YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>
YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>
```

If all 5 apply phrases are provided, P126 will add an estimated **+18,000 rows**
(total 72,462). Each strategy must be authorized separately in a new P126A gate task.

---

## 11. Rollback Reference / Backup Path

**Backup:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/backups/lottery_v2.db.p129b_backup_20260528T080035Z.db`

To restore production DB to pre-migration state:
```bash
cp '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/backups/lottery_v2.db.p129b_backup_20260528T080035Z.db' '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db'
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
# must return 54462
```

---

## 12. Explicit Non-Actions

| Item | Status |
|---|---|
| P126 controlled apply | NOT EXECUTED — requires per-strategy phrases |
| 4_STAR work | BLOCKED |
| P108 execution | BLOCKED |
| P117 execution | BLOCKED |
| P118 execution | BLOCKED |
| Scheduler / cron / launchd install | NOT DONE |
| Strategy promotion / lifecycle / registry mutation | NOT DONE |

---

## 13. Final Classification

```
P129B_PRODUCTION_BET_INDEX_SCHEMA_MIGRATION_APPLIED
```

bet_index schema migration applied to production DB.
All 54462 rows preserved. UNIQUE(lottery_type, target_draw, strategy_id, bet_index) active.
Next step: provide per-strategy P126 authorization phrases to gate P126A apply.
