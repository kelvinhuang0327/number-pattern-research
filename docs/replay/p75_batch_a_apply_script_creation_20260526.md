# P75 Batch A Apply Script Creation — 20260526

**PROJECT_CONTEXT_LOCK: LotteryNew**

---

## Summary

P75 creates the apply script and plan scaffolding for Batch A POWER_LOTTO predictions. Both artifact types are ready but blocked by a source data gap: zero POWER_LOTTO draws > 115000040 exist in the DB. No DB write occurs in P75. P76 can proceed once new draws are ingested and the plan JSON is regenerated.

---

## Context

| Item | Value |
|------|-------|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` |
| Branch | `p75-batch-a-apply-script-creation` |
| Base HEAD | `5ce3e09` (P74 merge) |
| Rows before | 46960 |
| Rows after | 46960 |

---

## P74 Blocker Summary

P74 (PR #196) authorized Batch A apply but was blocked because:
1. No P74-specific apply script existed.
2. No POWER_LOTTO draws > 115000040 existed in the DB.

Both strategies already had full 1500-row coverage via earlier controlled applies:

| Strategy | Controlled Apply ID | Rows | Draw Range |
|----------|-------------------|------|-----------|
| `fourier_rhythm_3bet` | `P19B_POWERLOTTO_FOURIER_1500_PROD_20260520` | 1500 | 101000002–115000040 |
| `fourier30_markov30_2bet` | `P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525` | 1500 | 101000002–115000040 |

---

## Source Draw Discovery

```sql
SELECT CAST(MIN(draw) AS INTEGER), CAST(MAX(draw) AS INTEGER), COUNT(*)
FROM draws
WHERE lottery_type='POWER_LOTTO';
-- Result: 97000001 | 115000040 | 1912

SELECT COUNT(*) FROM draws
WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER) > 115000040;
-- Result: 0
```

**Finding:** The DB max POWER_LOTTO draw is 115000040. Zero draws exist beyond this point. All eligible draws (101000002–115000040) are already fully covered by existing replay rows. No new rows can be generated until future lottery results are ingested.

> **Note on `draws` table:** The `draw` column type is TEXT. Lexicographic comparison (`> '115000040'`) returns incorrect results (307 false positives from 97xxx/98xxx/99xxx draws). All draw comparisons must use `CAST(draw AS INTEGER)`.

---

## Apply Plan

**File:** `outputs/replay/p74_batch_a_apply_plan_20260526.json`

| Field | Value |
|-------|-------|
| `final_plan_status` | `PLAN_BLOCKED_BY_SOURCE_DATA_GAP` |
| `total_plan_insert_rows` | 0 |
| `eligible_draws_for_plan` | 0 |
| `generation_mode` | `PLAN_ONLY` |

---

## Apply Script

**File:** `scripts/p74_batch_a_controlled_apply.py`

Modeled on `scripts/p7_controlled_replay_row_apply.py`. Key behaviors:

- **Dry-run by default.** `--apply` flag required for any DB write.
- **Backup required for apply.** `--backup <path>` must exist and contain 46960 rows.
- **Row count guard.** Refuses `--apply` if live rows ≠ 46960.
- **P74 collision guard.** Refuses `--apply` if any P74 `controlled_apply_id` rows already exist.
- **Duplicate detection.** By `(strategy_id, lottery_type, target_draw, controlled_apply_id)`.
- **Plan status gate.** Refuses `--apply` unless plan is `PLAN_READY_FOR_P76_APPLY`.
- **Batch A scope only.** Only inserts `fourier_rhythm_3bet` and `fourier30_markov30_2bet` POWER_LOTTO rows.
- **No lifecycle/champion/registry.** Script has no imports or calls to those layers.

---

## Dry-Run Execution

```
P74 BATCH A CONTROLLED APPLY — DRY-RUN MODE
NO DB WRITE IN THIS MODE.

Plan status : PLAN_BLOCKED_BY_SOURCE_DATA_GAP
Total plan rows : 0

PLAN NOT READY — status is 'PLAN_BLOCKED_BY_SOURCE_DATA_GAP'.
No rows available to preview.

Source draw discovery:
  draws > 115000040 : 0
  gap_reason        : DB max POWER_LOTTO draw is 115000040. All eligible draws
                      are already covered by existing replay rows.

Pre-flight (dry-run):
  live_rows              : 46960 (expected 46960) — OK
  p74_existing_rows      : 0 (expected 0) — OK

Dry-run row analysis:
  total plan rows : 0
  eligible (no dup) : 0
  would be skipped  : 0
  rows after apply (if applied) : 46960

DRY-RUN RESULT: 0 eligible rows.
Apply would make no changes to the DB.
Classification: PLAN_BLOCKED_BY_SOURCE_DATA_GAP

NO DB WRITE OCCURRED.
```

---

## No-DB-Write Confirmation

- Dry-run result: 0 rows, 0 writes.
- `--apply` flag was NOT passed.
- `PRAGMA query_only = ON` used for all DB opens in this session.
- DB row count after P75: **46960** (unchanged).

---

## Guardrails

| Guard | Status |
|-------|--------|
| No `git reset --hard` | ✅ |
| No `git clean` | ✅ |
| No `--force-push` | ✅ |
| No lifecycle promotion | ✅ |
| No champion replacement | ✅ |
| No registry mutation | ✅ |
| Drift guard | PASS |
| Branch governance | PASS |

---

## P76 Readiness

**Status: NOT READY**

Blockers:
1. Must ingest ≥1500 new POWER_LOTTO draws with `draw_id > 115000040` into the `draws` table.
2. Must run prediction engine to generate `prediction_items` for those draws (for both strategies).
3. Must re-generate `p74_batch_a_apply_plan_20260526.json` — update `plan_insert_rows_by_strategy` from empty to actual rows; set `final_plan_status = PLAN_READY_FOR_P76_APPLY`.
4. Must verify 0 duplicate collisions in a new dry-run.
5. Must re-obtain both P74 authorization phrases.
6. Then run: `p74_batch_a_controlled_apply.py --backup <path> --apply`

---

## Final Classification

**`P75_BLOCKED_BY_SOURCE_DATA_GAP`**
