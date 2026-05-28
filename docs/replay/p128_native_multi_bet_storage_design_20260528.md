# P128: Native Multi-Bet Replay Storage Design

**Classification:** `P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY`
**Task ID:** P128
**Generated:** 2026-05-28T04:02:25.171714+00:00
**DB rows before / after:** 54462 / 54462 (no writes)

---

## 1. Executive Summary

P128 formally decides the native multi-bet replay storage format, resolving the RSR-1 and RSR-2 blockers
identified in P126. The recommended design is **one-row-per-bet with a schema migration** that adds a
`bet_index` column and updates the UNIQUE constraint.

Key decisions:
- ✅ **one-row-per-bet convention APPROVED** as the storage model
- ✅ **bet_index column required** — migration plan defined (not executed in P128)
- ✅ **Duplicate key contract defined**: `(lottery_type, target_draw, strategy_id, bet_index)` as UNIQUE
- ✅ **P126 apply is CONDITIONALLY READY** pending migration authorization + per-strategy auth phrases from Kelvin
- 🚫 **Zero DB writes** in P128 — design only

---

## 2. P124 / P125 / P126 Recap

| Task | Classification | Key Output |
|---|---|---|
| P124 | `P124_COVERAGE_MATRIX_READY` | 36-row matrix; 5 candidates with `available` adapters |
| P125 | `P125_ADAPTER_GAP_PLAN_READY` | 12 adapters need `get_all_bets()`; 5 Tier-B candidates identified |
| P126 | `P126_DRY_RUN_PLAN_READY` | +18000 rows estimated if all 5 applied; blocked by RSR-1 (no bet_index) |

P126 found that the current schema has no `bet_index` column and the UNIQUE constraint
`(lottery_type, target_draw, strategy_id, replay_run_id)` does not support multi-bet rows cleanly.
P128 resolves this.

---

## 3. Why P128 Is Required Before Apply

Current schema UNIQUE constraint: `UNIQUE(lottery_type, target_draw, strategy_id, replay_run_id)`

All 5 P94 Tier-B strategies have `replay_run_id = NULL`. SQLite treats NULLs as distinct in UNIQUE
constraints, which technically allows inserting multiple rows per `(strategy, draw)` when `replay_run_id`
is NULL. However:

1. **Accidental behavior** — relying on NULL-distinct semantics is a fragile side effect, not a contract
2. **No bet_index column** — without it, there is no way to distinguish bet-1, bet-2, bet-N in queries
3. **Consumer breakage** — API and dashboard assume one row per `(strategy, draw)`; multi-bet rows appear as duplicates
4. **Dedup is impossible** — without bet_index, the duplicate key contract cannot be enforced at the DB level

P128 defines the permanent solution.

---

## 4. Storage Options Considered

| Option | Approach | Migration? | Recommended |
|---|---|---|---|
| A | Schema Migration: add bet_index column + update UNIQUE constraint | Yes | ✅ YES |
| B | Interim workaround: encode bet_index in source/controlled_apply_id + exploit NULL uniqueness | No | ❌ NO |
| C | Array-of-arrays per row (compact multi-bet) | Yes | ❌ NO |

### Option A (Recommended): Schema Migration

Add `bet_index INTEGER NOT NULL DEFAULT 1` column.
Replace UNIQUE constraint with `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`.
All existing rows receive `bet_index=1` automatically via DEFAULT.

**Pros:** Clean, normalized, permanent, queryable, enforced at DB level.
**Cons:** Requires SQLite 12-step table recreation (one-time operation); API consumers need to add `bet_index=1` filter for single-bet views.

### Option B: Interim workaround (NULL replay_run_id exploit)

Encode bet_index in `source`/`controlled_apply_id` fields. Relies on SQLite NULL-distinct behavior.

**Pros:** No migration needed.
**Cons:** Fragile, no formal bet_index column, breaks consumer queries, technical debt, not maintainable.

### Option C: Array-of-arrays per row

Store all bets as JSON array-of-arrays in `predicted_numbers`.

**Cons:** Breaks all existing consumers, requires data migration of existing rows, no per-bet analysis. **NOT recommended.**

---

## 5. Recommended Design

**Option A: one-row-per-bet with bet_index schema migration.**

| Aspect | Decision |
|---|---|
| Storage model | one-row-per-bet |
| bet_index column | Required — INTEGER NOT NULL DEFAULT 1 |
| UNIQUE constraint | (lottery_type, target_draw, strategy_id, bet_index) |
| Existing rows | Unchanged — all receive bet_index=1 via migration |
| New multi-bet rows | bet_index=2, 3, ... N per draw |
| Row count after migration | 54462 (unchanged — migration copies, does not add) |

---

## 6. One-Row-Per-Bet Convention Decision

**APPROVED**: one-row-per-bet is the canonical storage convention for multi-bet replay rows.

Rationale:
- Consistent with existing single-bet rows (bet_index=1 = current rows)
- Enables per-bet hit analysis, per-bet performance comparison
- Preserves all existing query patterns with `WHERE bet_index = 1`
- Scales to N-bet strategies (N up to ~10 safely; higher N requires storage impact review)
- P126's +18,000 row estimate is based on this convention and is correct

---

## 7. Bet Index Representation

| Field | Value | Note |
|---|---|---|
| `bet_index` column | `1` (existing bet) / `2`, `3`, ... N (new bets) | New column after migration |
| `controlled_apply_id` | `P94_TIERB_CONTROLLED_APPLY_20260526` | Same for all bets (identifies apply batch) |
| `source` | `P94_TIERB_CONTROLLED_APPLY` | Same for all bets |
| `provenance_hash` | SHA256(strategy_id + target_draw + bet_index + predicted_numbers + controlled_apply_id) | Per-bet hash |

**No encoding hack needed** — bet_index is a proper column after migration.
Interim (before migration): if Option B workaround is authorized, encode as `source = 'P94_TIERB_CONTROLLED_APPLY_BET_N'`
and note the technical debt in the apply record.

---

## 8. Duplicate / Provenance Guard Contract

Full dedup tuple: `(lottery_type, target_draw, strategy_id, bet_index, predicted_numbers_fingerprint, provenance_hash)`

| Layer | Mechanism | Enforcement |
|---|---|---|
| 1 | UNIQUE(lottery_type, target_draw, strategy_id, bet_index) | DB engine — rejects on INSERT |
| 2 | provenance_hash pre-insert check | Application level — skip if hash exists |
| 3 | predicted_numbers fingerprint | Application level — reject same numbers for same bet_index |
| 4 | controlled_apply_id prefix guard | Application level — must match P94_TIERB_CONTROLLED_APPLY prefix |

Forbidden duplicates:
- Same (strategy, draw, bet_index) with different predicted_numbers → ERROR (bet slot collision)
- Same (strategy, draw) with same predicted_numbers for bet_index > 1 → WARN (likely duplicate bet)
- Any row with provenance_hash=NULL after migration → ERROR

---

## 9. Migration Plan

**Migration type:** SQLite 12-step table recreation (standard SQLite migration pattern).
**Status in P128:** DESIGN ONLY — not executed.
**Authorization required:** `YES authorize migration_plan_p128 because <reason>`

### Migration Steps (18 steps)

| Step | SQL | Purpose |
|---|---|---|
| 1 | `PRAGMA foreign_keys = OFF` | Disable FK checks during table recreation |
| 2 | `BEGIN TRANSACTION` | Atomic migration |
| 3 | `CREATE TABLE strategy_prediction_replays_new (
  id INTEGER PRIMARY KEY AUTOINCR...` | Create new table with bet_index and updated UNIQUE constraint |
| 4 | `INSERT INTO strategy_prediction_replays_new SELECT id, lottery_type, target_draw...` | Copy all existing rows with bet_index=1 |
| 5 | `DROP TABLE strategy_prediction_replays` | Remove old table |
| 6 | `ALTER TABLE strategy_prediction_replays_new RENAME TO strategy_prediction_replay...` | Rename new table to production name |
| 7 | `CREATE INDEX idx_spr_lottery ON strategy_prediction_replays(lottery_type)` | Recreate index |
| 8 | `CREATE INDEX idx_spr_strategy ON strategy_prediction_replays(strategy_id)` | Recreate index |
| 9 | `CREATE INDEX idx_spr_draw ON strategy_prediction_replays(target_draw)` | Recreate index |
| 10 | `CREATE INDEX idx_spr_status ON strategy_prediction_replays(replay_status)` | Recreate index |
| 11 | `CREATE INDEX idx_spr_run ON strategy_prediction_replays(replay_run_id)` | Recreate index |
| 12 | `CREATE INDEX idx_spr_hit ON strategy_prediction_replays(hit_count)` | Recreate index |
| 13 | `CREATE INDEX idx_spr_controlled_apply_id ON strategy_prediction_replays(controll...` | Recreate index |
| 14 | `CREATE INDEX idx_spr_truth_level ON strategy_prediction_replays(truth_level)` | Recreate index |
| 15 | `CREATE INDEX idx_spr_bet_index ON strategy_prediction_replays(bet_index)` | New index for bet_index filtering |
| 16 | `COMMIT` | Commit atomic migration |
| 17 | `PRAGMA foreign_keys = ON` | Re-enable FK constraints |
| 18 | `SELECT COUNT(*) FROM strategy_prediction_replays` | Post-migration invariant check — must equal 54462 |

### Pre-conditions before execution

- Kelvin explicitly authorizes: YES authorize migration_plan_p128 because <reason>
- DB backup created and verified before execution
- All current DB invariants confirmed: replay_rows=54462
- No active replay job or write transaction on DB
- Drift guard expected count updated to 54462 + new_rows after migration + apply

### Post-migration invariants

- SELECT COUNT(*) FROM strategy_prediction_replays = 54462 (unchanged)
- All existing rows have bet_index = 1
- UNIQUE constraint is (lottery_type, target_draw, strategy_id, bet_index)
- All 8 original indexes + idx_spr_bet_index exist
- SQLite PRAGMA integrity_check = ok

---

## 10. P126 Apply Readiness After P128

**Overall readiness:** `CONDITIONALLY_READY`

P128 design is complete and resolves RSR-1 (storage format decided: one-row-per-bet with bet_index column) and RSR-2 (bet_index column defined with migration plan). P126 apply is CONDITIONALLY READY pending: (1) migration authorization, (2) migration execution, (3) per-strategy authorization phrases from Kelvin.

### Row delta (if all 5 P126 candidates applied)

| Strategy | Lottery | Bets | +New Rows | After Apply |
|---|---|---|---|---|
| `biglotto_echo_aware_3bet` | BIG_LOTTO | 3 | +3000 | — |
| `daily539_f4cold_5bet` | DAILY_539 | 5 | +6000 | — |
| `daily539_f4cold_3bet` | DAILY_539 | 3 | +3000 | — |
| `power_fourier_rhythm_2bet` | POWER_LOTTO | 2 | +1500 | — |
| `biglotto_ts3_markov_4bet_w30` | BIG_LOTTO | 4 | +4500 | — |
| **TOTAL** | | | **+18000** | **72462** |

### Preconditions for P126 apply

- **p128_migration_executed** [PENDING]: Schema migration must be authorized and executed before P126 apply. P128 design is now complete; migration plan is ready.
- **kelvin_migration_authorization** [REQUIRED]: Kelvin must state: YES authorize migration_plan_p128 because <reason>
- **kelvin_per_strategy_authorization_phrases** [REQUIRED]: 5 individual authorization phrases required — one per strategy
- **drift_guard_expected_count_update** [REQUIRED]: replay_lifecycle_drift_guard.py expected count must be updated to 72462 after apply
- **db_backup_before_migration** [REQUIRED]: Backup lottery_api/data/lottery_v2.db before executing migration plan
- **api_ui_consumer_review** [RECOMMENDED]: RSR-4: API endpoints and dashboard should be updated to filter bet_index=1 for single-bet views before or in parallel with apply

### Required authorization phrases (DO NOT apply until provided)

```
YES authorize migration_plan_p128 because <reason>
YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>
YES authorize controlled_apply for daily539_f4cold_5bet because <reason>
YES authorize controlled_apply for daily539_f4cold_3bet because <reason>
YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>
YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>
```

---

## 11. Explicit Non-Actions

The following were NOT performed in P128:

- 🚫 **4_STAR**: Explicitly excluded from all Tier-B multi-bet work per governance
- 🚫 **P108**: P108 execution blocked — not within P128 scope
- 🚫 **P117**: P117 execution blocked — not within P128 scope
- 🚫 **P118**: P118 execution blocked — not within P128 scope
- 🚫 **rejected_strategies**: No rejected strategies may be promoted or included in multi-bet apply
- 🚫 **strategy_promotion**: No lifecycle/champion/registry mutation in P128
- 🚫 **scheduler_cron_launchd**: No scheduler installation in P128
- 🚫 **db_writes**: P128 is design-only — zero DB writes permitted
- 🚫 **migration_execution**: Migration plan defined but not executed — requires separate authorization
- 🚫 **p126_apply**: P126 apply not executed in P128 — RSR-1/RSR-2 now resolved by design; execution requires authorization

---

## 12. Final Classification

```
task_id      : P128
classification: P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY
db_rows_before: 54462
db_rows_after : 54462
db_writes     : 0
migration_status: DESIGN_ONLY_NOT_EXECUTED
p126_readiness: CONDITIONALLY_READY
```

```text
P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY
```
