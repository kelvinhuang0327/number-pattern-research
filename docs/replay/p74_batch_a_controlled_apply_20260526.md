# P74 Batch A Controlled Apply Gate

**Date:** 2026-05-26  
**Task:** P74 — Batch A Controlled Apply  
**Branch:** `p74-batch-a-controlled-apply`  
**Authorization Mode:** `APPLY_AUTHORIZED_BUT_BLOCKED`

---

## Pre-flight Summary

| Check | Result |
|---|---|
| Drift guard (pre-flight) | ✅ PASS |
| Branch governance (pre-flight, main=46960) | ✅ PASS |
| Branch governance (p74-batch-a-controlled-apply=46960) | ✅ PASS |
| Cross-project contamination scan | ✅ CLEAN |
| DB backup created | ✅ `lottery_api/data/lottery_v2.db.bak_p74_pre_batch_a_20260526_125453` |
| Backup verified (rows=46960) | ✅ PASS |
| P74 controlled_apply_id duplicate check | ✅ 0 P74 rows exist |
| P74 apply script available | ❌ NOT FOUND |
| P74 source data available | ❌ NOT FOUND |

---

## Authorization Mode

Both authorization phrases are present in the P74 task spec:

1. `YES create new branch for P74 batch A controlled apply` — **present** → branch creation authorized
2. `YES apply P71 controlled replay rows` — **present** → apply authorized in principle

**Decision: `APPLY_AUTHORIZED_BUT_BLOCKED`**

Apply is blocked because neither a P74-specific apply script nor source data (prediction rows for draws > 115000040) exists. The `p7_controlled_replay_row_apply.py` script reads from a P7-era JSON plan and cannot be reused for P74 without a new plan JSON.

---

## Candidate Table — Batch A

| strategy_id | batch | lottery_type | lifecycle | existing_controlled_apply_id | existing_rows | draw_range | proposed_P74_id |
|---|---|---|---|---|---|---|---|
| fourier_rhythm_3bet | A | POWER_LOTTO | ONLINE | P19B_POWERLOTTO_FOURIER_1500_PROD_20260520 | 1500 | 101000002–115000040 | P74_POWERLOTTO_BATCH_A_FOURIER_RHYTHM_1500_PROD_20260526 |
| fourier30_markov30_2bet | A | POWER_LOTTO | ACTIVE | P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525 | 1500 | 101000002–115000040 | P74_POWERLOTTO_BATCH_A_FOURIER30_MARKOV30_1500_PROD_20260526 |

### Draw Overlap Risk

Both Batch A strategies already have **1500 rows covering draws 101000002–115000040** under pre-P74 controlled_apply_ids. Any P74 apply that targets the same draws would result in **0 net insertions** (duplicate skip by strategy_id + target_draw + lottery_type). P74 must target draws **strictly after 115000040**.

---

## Excluded Strategies (unchanged from P71/P72/P73)

| strategy_id | reason |
|---|---|
| cold_complement_2bet | sub-baseline |
| zonal_entropy_2bet | fallback-equivalent |
| midfreq_fourier_mk_3bet | OOS deferred |
| midfreq_acb_2bet | RETIRED lifecycle gate (B2 blocked) |
| midfreq_fourier_2bet | RETIRED lifecycle gate (B2 blocked) |
| acb_1bet | RETIRED lifecycle gate (B3 blocked) |
| acb_markov_midfreq_3bet | RETIRED lifecycle gate (B3 blocked) |
| Any DAILY_539 strategy | out of P74 scope |
| Any BIG_LOTTO strategy | out of P74 scope |

---

## DB State

| Metric | Value |
|---|---|
| production_rows_before | 46960 |
| production_rows_after | 46960 (no write occurred) |
| expected_rows_after_if_applied | 49960 |
| db_write_occurred | false |

---

## Rollback Plan

1. Stop immediately if apply is ever attempted and post-apply row count ≠ 49960
2. Restore: `cp lottery_api/data/lottery_v2.db.bak_p74_pre_batch_a_20260526_125453 lottery_api/data/lottery_v2.db`
3. Verify restored row count = 46960
4. Run drift guard to confirm PASS
5. Document rollback event before any retry

---

## Required Next Steps Before Apply Can Proceed

1. **Create P74 apply plan JSON** with 1500 predictions per strategy for draws > 115000040
2. **Create `scripts/p74_batch_a_controlled_apply.py`** reading the P74 plan JSON (same safety constraints as p7 apply script: duplicate skip, backup required, dry-run default, --apply flag for write)
3. **Run dry-run mode** to confirm 0 duplicate collisions (strategy_id + target_draw + lottery_type)
4. **Re-obtain both authorization phrases** in a new task session after script + data are ready
5. Backup already exists at `bak_p74_pre_batch_a_20260526_125453` — must verify it still matches row count before next apply session

---

## Governance Flags

| Flag | Status |
|---|---|
| no_reset_hard | ✅ true |
| no_git_clean | ✅ true |
| no_force_push | ✅ true |
| no_lifecycle_promotion | ✅ true |
| no_champion_replacement | ✅ true |
| no_registry_mutation | ✅ true |
| no_unscoped_strategy_apply | ✅ true |
| no_daily_539 | ✅ true |
| no_big_lotto | ✅ true |

---

## Final Classification

```
P74_BATCH_A_READY_WAITING_FOR_APPLY_AUTHORIZATION
```

**Reason:** Apply authorized by phrase presence but mechanically blocked. No P74 apply script or source data exists. DB rows unchanged at 46960. All governance guardrails maintained.

---

**PROJECT_CONTEXT_LOCK = LotteryNew**
