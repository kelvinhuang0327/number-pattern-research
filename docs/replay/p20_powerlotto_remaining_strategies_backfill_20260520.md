# P20 — Power Lotto Remaining ONLINE Strategies Backfill

**Date:** 2026-05-20  
**Phase:** P20_POWERLOTTO_REMAINING_STRATEGIES  
**Classification:** P20_PRODUCTION_APPLY_COMPLETE

---

## 1. Objective

Complete the POWER_LOTTO replay coverage by applying 1500-draw backfill for
the two remaining ONLINE strategies: `power_precision_3bet` and
`power_orthogonal_5bet`. Pattern follows P14B→P14C→P14D pipeline.

---

## 2. Remaining Strategies

| strategy_id | lifecycle_status | Legacy rows | In 1500-window | New inserts |
|-------------|-----------------|-------------|----------------|-------------|
| `power_precision_3bet` | ONLINE | 70 | 0 (outside window) | **1500** |
| `power_orthogonal_5bet` | ONLINE | 70 | 0 (outside window) | **1500** |

Total new rows: **3000**

---

## 3. Dry-Run Result

| Metric | Value |
|--------|-------|
| generated_candidates | 3000 |
| ready_candidates | **3000** ✓ |
| blocked_candidates | 0 ✓ |
| duplicate_existing_count | 0 ✓ |
| fake_success_count | 0 ✓ |

---

## 4. Existing Duplicate Analysis

The 70 legacy rows per strategy fall OUTSIDE the most recent 1500-draw window
(draws 101000002–115000040). Duplicate detection finds 0 overlap →
all 1500 draws per strategy are new inserts.

---

## 5. Planned Insert Count

1500 × 2 strategies = **3000 rows**

---

## 6. Temp DB Rehearsal

| Phase | Metric | Value |
|-------|--------|-------|
| R1 Apply | inserted_count | **3000** ✓ |
| R1 Apply | rows_after (6460→9460) | **9460** ✓ |
| R2 Rerun | inserted_count | **0** ✓ |
| R2 Rerun | duplicate_count | **3000** ✓ |
| Rollback | deleted_count | **3000** ✓ |
| Rollback | rows_after (9460→6460) | **6460** ✓ |

---

## 7. Production Apply Result

| Metric | Value |
|--------|-------|
| rows_before | 6460 |
| inserted_count | **3000** ✓ |
| duplicate_count | 0 |
| rows_after | **9460** ✓ |
| controlled_apply_id | `P20_POWERLOTTO_REMAINING_1500_PROD_20260520` |
| truth_level | `POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED` |
| prediction_cutoff_date | populated for all 3000 rows ✓ |
| dry_run flag | 0 (production rows) ✓ |

---

## 8. API/Page Implication

All 3 POWER_LOTTO ONLINE strategies now have 1500+ replay rows in production:
- `fourier_rhythm_3bet`: 1500 rows (P19B)
- `power_precision_3bet`: 1500 rows (P20) + 70 legacy = 1570 total
- `power_orthogonal_5bet`: 1500 rows (P20) + 70 legacy = 1570 total

The UI timestamp badge (`prediction_cutoff_date`, `prediction_generated_at`)
will show correctly for all P20 rows.

---

## 9. Next Recommendation

### P21 — DAILY_539 Replay Backfill

Extend the pipeline to DAILY_539 ONLINE strategies:
- `daily539_f4cold`
- `daily539_markov_cold`

This completes full three-lottery-type replay coverage.
