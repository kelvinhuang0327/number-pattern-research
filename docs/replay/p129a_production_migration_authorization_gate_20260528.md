# P129A — Production Migration Authorization Gate

**Task ID:** P129A
**Classification:** `P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION`
**Generated:** 2026-05-28 07:50 UTC

---

## 1. Executive Summary

P129A is the authorization gate between the completed P129 rehearsal and the actual
production schema migration. The gate checks:
1. P129 rehearsal passed with all 54462 rows preserved
2. The corrected ROW_NUMBER() COPY SQL is documented
3. Production DB is unchanged (no bet_index column, 54462 rows)
4. Kelvin's exact migration authorization phrase is present

**Gate status:** `WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION` —
authorization phrase is **ABSENT ← gate blocked here**

| Check | Result |
|---|---|
| P129 classification confirmed | ✓ PASS |
| P129 migration rehearsal OK | ✓ PASS |
| P129 rows preserved (54462) | ✓ PASS |
| P129 production DB untouched | ✓ PASS |
| ROW_NUMBER() fix required | ✓ PASS |
| Production DB rows now (54462) | ✓ PASS |
| Production DB has no bet_index | ✓ PASS |
| Kelvin authorization present | **ABSENT ← gate blocked here** |
| Migration execution performed | ✓ PASS |
| Production DB modified | ✓ PASS |

---

## 2. P129 Rehearsal Recap

- **P129 commit:** `a3f8561`
- **Classification:** `P129_BET_INDEX_SCHEMA_MIGRATION_REHEARSAL_READY`
- **18-step migration:** all steps OK on temp DB copy
- **Rows preserved in rehearsal:** 54462
- **Production DB modified in P129:** `false`
- **Rehearsal DB:** ephemeral temp copy (not production)

---

## 3. Key Finding: 120 Duplicate Groups Make Naive Migration Fail

P129 rehearsal discovered that the production DB contains
**120 duplicate (lottery_type, target_draw, strategy_id) groups**
with **160 extra rows** from old replay runs.

**Root cause:** Old replay runs produced multiple rows per (strategy, draw) with different
`replay_run_id` values. The current UNIQUE constraint allows this because `replay_run_id`
values differ. However, the P128 naive COPY step (`1 AS bet_index`) fails with:

```
UNIQUE constraint failed: strategy_prediction_replays_new.lottery_type,
strategy_prediction_replays_new.target_draw,
strategy_prediction_replays_new.strategy_id,
strategy_prediction_replays_new.bet_index
```

because all rows would get `bet_index=1`, and the new constraint treats `1 == 1` as a collision.

---

## 4. Required Fix: ROW_NUMBER() bet_index Assignment

**P128 original step 4 (FAILS):**

```sql
INSERT INTO strategy_prediction_replays_new
SELECT id, lottery_type, target_draw, ...,
  1 AS bet_index          -- ← FAILS for 120 duplicate groups
FROM strategy_prediction_replays
```

**Corrected step 4 for production migration (P129 rehearsal confirmed this works):**

```sql
INSERT INTO strategy_prediction_replays_new
SELECT id, lottery_type, target_draw, ...,
  ROW_NUMBER() OVER (
    PARTITION BY lottery_type, target_draw, strategy_id
    ORDER BY id
  ) AS bet_index           -- ← assigns 1,2,3... per group; preserves all 54462 rows
FROM strategy_prediction_replays
```

**Result after corrected migration (verified in P129 rehearsal):**

| Group | Rows | bet_index |
|---|---|---|
| Non-duplicate (54302 rows) | 54302 | = 1 |
| Old dup-run second rows (160 rows) | 160 | = 2 |
| Invalid (NULL or < 1) | 0 | — |
| **Total** | **54462** | **all valid** |

---

## 5. Production DB Non-Action Confirmation

**The production database has NOT been modified in P129A.**

| Metric | Before P129A | After P129A |
|---|---|---|
| replay_rows | 54462 | 54462 |
| has bet_index column | False | False |
| production_db_modified | — | `false` |

---

## 6. Authorization Gate Status

**Current status: `WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION`**

| Field | Value |
|---|---|
| Exact required phrase | `YES authorize migration_plan_p128 because <reason>` |
| Authorization present | `False` |
| Migration allowed | `False` |
| Stop reason | `WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION` |

The gate is **BLOCKED**. No migration will proceed until the exact phrase is provided.

---

## 7. Exact Required Kelvin Authorization Phrase

To authorize production migration, Kelvin must state **exactly**:

```
YES authorize migration_plan_p128 because <reason>
```

Replace `<reason>` with a real justification (e.g., "rehearsal confirmed 54462 rows preserved
and ROW_NUMBER() fix is validated"). The prompt text itself does not constitute authorization.

---

## 8. Why P126 Apply Remains Blocked

P126 apply requires **both** conditions to be met:

1. **Schema migration authorized + executed (P129A → P129B gate)**
   - Status: `BLOCKED` — authorization phrase not yet provided
2. **Per-strategy Kelvin authorization phrases (5 required)**
   - Status: `NOT YET PROVIDED`

P126 will add an estimated **+18,000 rows** across 5 strategies (total 72,462), but only
after the schema migration is live in production and all authorization phrases are received.

Blocked strategies pending P126 apply:
- `biglotto_echo_aware_3bet` (+3000 rows)
- `daily539_f4cold_5bet` (+6000 rows)
- `daily539_f4cold_3bet` (+3000 rows)
- `power_fourier_rhythm_2bet` (+1500 rows)
- `biglotto_ts3_markov_4bet_w30` (+4500 rows)

---

## 9. Explicit Non-Actions

The following were **NOT** performed in P129A:

| Item | Status |
|---|---|
| Production DB schema migration | NOT EXECUTED — gate not passed |
| Production DB INSERT / UPDATE / DELETE | NOT DONE |
| P126 controlled apply | NOT EXECUTED |
| 4_STAR work | BLOCKED |
| P108 execution | BLOCKED |
| P117 execution | BLOCKED |
| P118 execution | BLOCKED |
| Scheduler / cron / launchd install | NOT DONE |
| Strategy promotion / lifecycle / champion / registry mutation | NOT DONE |

---

## 10. Final Classification

```
P129A_WAITING_FOR_KELVIN_MIGRATION_AUTHORIZATION
```

P129A gate confirmed: rehearsal valid, production DB clean, corrected SQL documented.
Waiting for Kelvin to provide:
```
YES authorize migration_plan_p128 because <reason>
```
