# P14C — Big Lotto Single Strategy Temp-DB Rehearsal

**Date:** 2026-05-20  
**Phase:** P14C_BIGLOTTO_SINGLE_STRATEGY_TEMPDB_REHEARSAL  
**Classification:** P14C_TEMP_DB_REHEARSAL_READY

---

## 1. Objective

P14C rehearses the full insert lifecycle for the 1500 BIG_LOTTO dry-run
candidates produced in P14B — but against a **temporary copy** of the
production DB, never the production DB itself.

Three phases are executed in sequence:
1. **Apply** — insert 1500 rows into temp DB (460 → 1960)
2. **Rerun** — idempotency check (0 new inserts, 1500 duplicates detected)
3. **Rollback** — delete by `controlled_apply_id` (1960 → 460)

Goal: prove that when production apply is eventually authorized (`YES apply Big
Lotto single strategy replay rows`), the script will behave correctly and
cleanly.

---

## 2. P14B → P14C Transition

P14B established that:
- 1500 READY candidates can be generated for `ts3_regime_3bet` (ONLINE, BIG_LOTTO)
- Each candidate has real `predicted_numbers` (from adapter) and real
  `actual_numbers` (from DB)
- `hit_count` math is correct: `hit_numbers = predicted ∩ actual`
- No production rows were written; `production_rows = 460` throughout

P14C takes the same candidate pool and validates that the **insert mechanism
itself** works: schema compatibility, duplicate detection, rollback, and
production DB isolation.

---

## 3. Selected Strategy

| Field | Value |
|-------|-------|
| strategy_id | `ts3_regime_3bet` |
| strategy_name | 大樂透 TS3+Regime 3注 |
| lifecycle_status | ONLINE |
| RSM edge (300p) | +3.51% |
| Sharpe | 0.123 |
| Adapter | `_BigLottoTs3Regime3BetAdapter` (P1.4 safe reconstruction) |

---

## 4. Planned Rows

| Metric | Value |
|--------|-------|
| planned_insert_count | 1500 |
| BIG_LOTTO draws available | 2135 |
| Target window | 1500 most recent draws |
| controlled_apply_id | `P14C_BIGLOTTO_TS3_1500_TEMP_REHEARSAL_20260520` |
| truth_level | `TEMP_REHEARSAL_REPLAY_BACKFILL` |
| source | `P14B_BIGLOTTO_SINGLE_STRATEGY_REPLAY_DRY_RUN` |

---

## 5. Temp DB Apply Result

| Metric | Value |
|--------|-------|
| rows_before | 460 |
| inserted_count | **1500** ✓ |
| duplicate_count | 0 |
| error_count | 0 |
| rows_after_apply | **1960** ✓ |

All 1500 candidates inserted cleanly. No schema errors, no constraint violations.

---

## 6. Idempotency Rerun Result

| Metric | Value |
|--------|-------|
| rerun_inserted_count | **0** ✓ |
| rerun_duplicate_count | **1500** ✓ |
| rows_after_rerun | 1960 (unchanged) ✓ |

Duplicate detection uses `(strategy_id, lottery_type, target_draw)` as the
natural key. On rerun, all 1500 rows are detected as duplicates and skipped.
The temp DB row count does not change.

---

## 7. Rollback Result

| Metric | Value |
|--------|-------|
| rollback_deleted_count | **1500** ✓ |
| rows_after_rollback | **460** ✓ |

Rollback deletes all rows matching `controlled_apply_id =
P14C_BIGLOTTO_TS3_1500_TEMP_REHEARSAL_20260520`. The temp DB returns to its
original state (460 rows). This confirms that a production apply can be
cleanly reversed if needed.

---

## 8. Why Production DB Was Not Touched

- The script always checks `db.resolve() == PROD_DB.resolve()` and raises
  `RuntimeError("SAFETY STOP")` if they match.
- All operations targeted `/tmp/lottery_v2_p14c_biglotto_rehearsal.db`
  (a one-time copy of the production DB, not tracked in git).
- `production_rows_after = 460` confirmed post-rehearsal.
- No `strategy_prediction_replays` rows were inserted, updated, or deleted in
  the production DB.

---

## 9. Safety Gates

The P14C script enforces the following safety gates before any write:

| Gate | Trigger |
|------|---------|
| Refuse production DB | `db.resolve() == PROD_DB.resolve()` → `RuntimeError` |
| Row count mismatch | actual rows ≠ `--expected-rows` → `RuntimeError` |
| Wrong candidate count | P14B input has ≠ 1500 READY → `sys.exit(2)` |

---

## 10. Next Recommendations

### P14D — Big Lotto Production Apply Readiness Review

Before writing to the production DB, review:
- Are 1500 new rows acceptable? (would bring total to 1960)
- Is `ts3_regime_3bet` the correct strategy for this batch?
- Is `controlled_apply_id = P14C_BIGLOTTO_TS3_1500_TEMP_REHEARSAL_20260520`
  the intended label, or should a production apply use a different ID?
- Authorization required: `YES apply Big Lotto single strategy replay rows`

### P15 — Big Lotto Replay Page/API Integration

Use the `page_ready_sample` from P14B and the temp DB schema verified in P14C
to test the replay list page end-to-end:
- Does the API serve `DRY_RUN_REPLAY_BACKFILL` rows correctly?
- Does the UI display `hit_count`, `predicted_numbers`, `actual_numbers`?
- Does `display_status = SHOW_REPLAY_DRY_RUN` render correctly?

**Recommended order:** P14D readiness review → (if approved) production apply
→ P15 page/API integration verification with real production rows.

---

## 11. Verification Summary

| Check | Result |
|-------|--------|
| production rows before | 460 |
| production rows after rehearsal | 460 |
| temp apply: 460 → 1960 | ✓ |
| temp rerun: 0 inserted, 1500 dupes | ✓ |
| temp rollback: 1960 → 460 | ✓ |
| drift guard pre | PASS |
| governance guard pre | PASS |
| drift guard post | PASS |
| governance guard post | PASS |
| baseline + P14B + P14C tests | PASS |
| no DB / backup / pid staged | ✓ |
| no production apply | ✓ |
| final_classification | P14C_TEMP_DB_REHEARSAL_READY |
