# P79: Batch A Controlled Apply — POWER_LOTTO draw 115000041

**Date:** 2026-05-26  
**Branch:** p79-batch-a-controlled-apply-powerlotto-115000041  
**Classification:** P79_BATCH_A_CONTROLLED_APPLY_SUCCESS  
**Artifact:** `outputs/replay/p79_batch_a_controlled_apply_20260526.json`

---

## Context

P77C (PR #203, merge commit `4b2eebc`) confirmed POWER_LOTTO draw 115000041 in the canonical `draws` table. P78 plan status was `PLAN_READY_FOR_P79_APPLY` with expected insert delta = 2. P79 applies those 2 rows into `strategy_prediction_replays` as production records (dry_run=0).

---

## Phase 1: P77C Merge Verification (pre-P79)

| Check | Required | Actual | Status |
|-------|----------|--------|--------|
| PR #201 | MERGED | MERGED | ✓ |
| PR #202 | MERGED | MERGED | ✓ |
| PR #203 | MERGED | MERGED (4b2eebc) | ✓ |
| Replay rows | 46960 | 46960 | ✓ |
| POWER_LOTTO max draw | 115000041 | 115000041 | ✓ |
| Draw 115000041 row | exists | date=2026/05/21, numbers=[6,14,22,28,35,38], special=1 | ✓ |
| P78 plan status | PLAN_READY_FOR_P79_APPLY | PLAN_READY_FOR_P79_APPLY | ✓ |
| P78 expected delta | 2 | 2 | ✓ |
| Existing target rows | 0 | 0 | ✓ |
| Drift guard | PASS | 6/6 PASS | ✓ |
| Branch governance | PASS | 15/15 PASS | ✓ |

---

## DB Backup

```
lottery_api/data/lottery_v2.db.bak_p79_pre_apply_20260526_160020
```

---

## Inserted Rows

### Row 1: fourier_rhythm_3bet (id=46961)

| Field | Value |
|-------|-------|
| strategy_id | fourier_rhythm_3bet |
| strategy_name | 威力彩 Fourier Rhythm 3注 |
| lottery_type | POWER_LOTTO |
| target_draw | 115000041 |
| target_date | 2026/05/21 |
| history_cutoff_draw | 115000040 |
| replay_status | PREDICTED |
| predicted_numbers | [3, 23, 24, 28, 30, 36] |
| predicted_special | NULL |
| actual_numbers | [6, 14, 22, 28, 35, 38] |
| actual_special | 1 |
| hit_numbers | [28] |
| hit_count | 1 |
| special_hit | 0 |
| truth_level | POWERLOTTO_DRAW_EXT_VERIFIED |
| controlled_apply_id | P78_POWERLOTTO_BATCH_A_FOURIER_RHYTHM_DRAWEXT_20260526 |
| source | P78_BATCH_A_PLAN_REGENERATION |
| dry_run | **0** (production) |

### Row 2: fourier30_markov30_2bet (id=46962)

| Field | Value |
|-------|-------|
| strategy_id | fourier30_markov30_2bet |
| strategy_name | fourier30_markov30_2bet |
| lottery_type | POWER_LOTTO |
| target_draw | 115000041 |
| target_date | 2026/05/21 |
| history_cutoff_draw | 115000040 |
| replay_status | PREDICTED |
| predicted_numbers | [13, 14, 27, 29, 34, 38] |
| predicted_special | NULL |
| actual_numbers | [6, 14, 22, 28, 35, 38] |
| actual_special | 1 |
| hit_numbers | [14, 38] |
| hit_count | 2 |
| special_hit | 0 |
| truth_level | POWERLOTTO_DRAW_EXT_VERIFIED |
| controlled_apply_id | P78_POWERLOTTO_BATCH_A_FOURIER30_MARKOV30_DRAWEXT_20260526 |
| source | P78_BATCH_A_PLAN_REGENERATION |
| dry_run | **0** (production) |

---

## Verification

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| Replay rows before | 46960 | 46960 | ✓ |
| Rows inserted | 2 | 2 | ✓ |
| Replay rows after | 46962 | 46962 | ✓ |
| Duplicate guard (pre) | 0 existing | 0 | ✓ |
| Duplicate guard (post) | 2 rows | 2 | ✓ |
| dry_run flag | 0 | 0 | ✓ |
| POWER_LOTTO max draw (draws) | 115000041 | 115000041 | ✓ |
| draws table untouched | true | true | ✓ |

---

## Rollback SQL

```sql
DELETE FROM strategy_prediction_replays WHERE id IN (46961, 46962);
```

---

## Next Task

Replay UI/API verification — confirm rows appear in `/api/replays` endpoint and frontend replay page for POWER_LOTTO draw 115000041.
