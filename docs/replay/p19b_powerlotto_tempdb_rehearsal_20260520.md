# P19B — Power Lotto Temp-DB Rehearsal and Production Apply

**Date:** 2026-05-20  
**Phase:** P19B_POWERLOTTO_TEMPDB_REHEARSAL  
**Classification:** P19B_POWERLOTTO_PRODUCTION_APPLY_COMPLETE

---

## 1. Objective

Rehearse inserting 1500 `fourier_rhythm_3bet` POWER_LOTTO replay rows into a
temp copy of the production DB, then execute the authorized production apply.

---

## 2. P19 → P19B Transition

P19 established:
- 1500 READY POWER_LOTTO candidates for `fourier_rhythm_3bet`
- Real predicted_numbers, actual_numbers, hit_count verified
- prediction_cutoff_date and prediction_generated_at present
- No DB writes; production rows = 4960

P19B applies the same candidates to first a temp DB (rehearsal), then the
production DB (apply-authorized mode).

---

## 3. Selected Strategy

| Field | Value |
|-------|-------|
| strategy_id | `fourier_rhythm_3bet` |
| strategy_name | 威力彩 Fourier Rhythm 3注 |
| lifecycle_status | ONLINE |
| RSM edge (1000p) | +1.91% |

---

## 4. Planned Rows

| Metric | Value |
|--------|-------|
| planned_insert_count | 1500 |
| lottery_type | POWER_LOTTO |
| controlled_apply_id | `P19B_POWERLOTTO_FOURIER_1500_PROD_20260520` |
| truth_level | `POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` |
| source | `P19_POWERLOTTO_SINGLE_STRATEGY_REPLAY_DRY_RUN` |
| prediction_cutoff_date | derived from history[-1].date |
| dry_run | 0 (production rows) |

---

## 5. Temp DB Apply Result

| Metric | Value |
|--------|-------|
| rows_before | 4960 |
| inserted_count | **1500** ✓ |
| error_count | 0 ✓ |
| rows_after_apply | **6460** ✓ |

---

## 6. Idempotency Rerun Result

| Metric | Value |
|--------|-------|
| rerun_inserted_count | **0** ✓ |
| rerun_duplicate_count | **1500** ✓ |
| rows_after_rerun | 6460 (unchanged) ✓ |

---

## 7. Rollback Result

| Metric | Value |
|--------|-------|
| rollback_deleted_count | **1500** ✓ |
| rows_after_rollback | **4960** ✓ |

---

## 8. Production Apply

Apply authorized by: `YES apply POWER_LOTTO replay rows`

| Metric | Value |
|--------|-------|
| rows_before | 4960 |
| inserted_count | **1500** ✓ |
| duplicate_count | 0 |
| error_count | 0 |
| rows_after | **6460** ✓ |
| production_apply | true |
| dry_run flag on rows | 0 ✓ |

Production rows: 4960 → **6460**

---

## 9. Safety Gates

| Gate | Trigger |
|------|---------|
| Refuse prod DB without flag | RuntimeError if no `--allow-production` |
| Row count mismatch | RuntimeError if actual ≠ expected |
| Candidate count check | sys.exit(2) if P19 input ≠ 1500 READY |

---

## 10. Post-Apply Verification

| Check | Result |
|-------|--------|
| production rows | **6460** ✓ |
| P19B rows (POWER_LOTTO) | 1500 ✓ |
| prediction_cutoff_date populated | 1500/1500 ✓ |
| prediction_generated_at populated | 1500/1500 ✓ |
| cutoff > target_date violations | 0 ✓ |
| legacy rows unchanged | 460 ✓ |
| drift guard PASS | ✓ |
| governance guard PASS | ✓ |

## 11. Next Recommendations

### P20 — Remaining POWER_LOTTO Strategies

Apply the same dry-run → rehearsal → apply pipeline to the remaining two
ONLINE POWER_LOTTO strategies:
- `power_precision_3bet` (has 70 legacy rows)
- `power_orthogonal_5bet` (has 70 legacy rows)

### P21 — DAILY_539 Replay Backfill

After POWER_LOTTO pipeline is complete, extend to DAILY_539 ONLINE strategies
for full three-lottery-type replay coverage.
