# P72 Controlled Apply Rehearsal Gate
**Date**: 2026-05-26  
**Branch**: p72-controlled-apply-rehearsal  
**HEAD**: 80201f7  

---

## PROJECT_CONTEXT_LOCK

| Field | Value |
|---|---|
| Project | LotteryNew |
| Canonical Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |
| Canonical Branch | main |
| Task | P72_CONTROLLED_APPLY_REHEARSAL |

This document applies ONLY to LotteryNew.

---

## Identity

| Field | Value |
|---|---|
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |
| Branch | p72-controlled-apply-rehearsal |
| HEAD | 80201f7 |
| Authorization Mode | **REHEARSAL_ONLY** |
| Production Rows Before | 46960 |
| Production Rows After (P72 rehearsal) | 46960 |

---

## Authorization Mode: REHEARSAL_ONLY

Phrase `YES apply P71 controlled replay rows` is **ABSENT** from this task.

Therefore:
- No production DB write
- No replay row insert into production
- No lifecycle promotion
- No champion replacement
- No registry mutation
- No force push
- No P6 remote sync debt resolution

Future production apply requires explicit phrase: `YES apply P71 controlled replay rows`

---

## Pre-flight Results

| Check | Result |
|---|---|
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew ✓ |
| Branch (p72 created) | p72-controlled-apply-rehearsal ✓ |
| Production rows | 46960 ✓ |
| P58 controlled_apply_id rows | 1500 ✓ |
| P66 cold_complement rows | 1500 ✓ |
| P66 zonal_entropy rows | 1500 ✓ |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS ✓ |
| Branch governance | BRANCH_GOVERNANCE_PASS ✓ |
| Cross-project contamination | CLEAN (novel_hybrid_lotto = LotteryNew-internal) ✓ |

---

## P71 Summary

| Field | Value |
|---|---|
| PR | #193 |
| HEAD | 80201f7 |
| Classification | P71_CONTROLLED_APPLY_READINESS_GATE_MERGED_TO_MAIN |
| Production rows | 46960 |
| Authorization mode | READINESS_ONLY |
| Tests | 100/100 PASS |

---

## P72 Candidate Scope (8 Strategies)

### Batch A — POWER_LOTTO (Sequence 1)

| strategy_id | lifecycle | existing_rows | P71 readiness | temp_rehearsal_req | gate_result |
|---|---|---|---|---|---|
| fourier_rhythm_3bet | ONLINE | 1500 | READY_FOR_CONTROLLED_APPLY | No | REHEARSAL_READY |
| fourier30_markov30_2bet | ACTIVE | 1500 | READY_FOR_CONTROLLED_APPLY | No | REHEARSAL_READY |

### Batch B1 — DAILY_539 (Sequence 2)

| strategy_id | lifecycle | existing_rows | P71 readiness | temp_rehearsal_req | gate_result |
|---|---|---|---|---|---|
| 539_3bet_orthogonal | ACTIVE | 1500 | READY_FOR_CONTROLLED_APPLY | No | REHEARSAL_READY |
| acb_single_539 | ACTIVE | 1500 | READY_FOR_CONTROLLED_APPLY | No | REHEARSAL_READY |

### Batch B2 — DAILY_539 (Sequence 3) ⚠️ RETIRED lifecycle + dual ID risk

| strategy_id | lifecycle | existing_rows | P71 readiness | temp_rehearsal_req | gate_result |
|---|---|---|---|---|---|
| midfreq_acb_2bet | RETIRED | 1500 | READY_AFTER_TEMP_REHEARSAL | Yes | REHEARSAL_READY |
| midfreq_fourier_2bet | RETIRED | 1500 | READY_AFTER_TEMP_REHEARSAL | Yes | REHEARSAL_READY ⚠️ |

### Batch B3 — DAILY_539 (Sequence 4) ⚠️ RETIRED lifecycle

| strategy_id | lifecycle | existing_rows | P71 readiness | temp_rehearsal_req | gate_result |
|---|---|---|---|---|---|
| acb_1bet | RETIRED | 1500 | READY_AFTER_TEMP_REHEARSAL | Yes | REHEARSAL_READY |
| acb_markov_midfreq_3bet | RETIRED | 1500 | READY_AFTER_TEMP_REHEARSAL | Yes | REHEARSAL_READY |

---

## Excluded Strategies

| strategy_id | reason | classification |
|---|---|---|
| BIG_LOTTO (all) | BIG_LOTTO excluded per P71 | EXCLUDED_BIG_LOTTO |
| cold_complement_2bet | sub-baseline performance | EXCLUDED_SUB_BASELINE |
| zonal_entropy_2bet | fallback-equivalent performance | EXCLUDED_FALLBACK_EQUIVALENT |
| midfreq_fourier_mk_3bet | deferred pending OOS gates | EXCLUDED_DEFERRED_OOS |

---

## Per-Strategy Rehearsal Detail

### fourier_rhythm_3bet

| Field | Value |
|---|---|
| lottery_type | POWER_LOTTO |
| lifecycle | ONLINE |
| existing_rows | 1500 (P19B) |
| proposed_rows | 1500 |
| proposed_controlled_apply_id | P72_POWERLOTTO_BATCHA_FOURIER_RHYTHM_3BET_1500_REHEARSAL_20260526 |
| duplicate_risk | LOW |
| lifecycle_gate | PASS |
| gate_result | REHEARSAL_READY |
| rollback | DELETE WHERE controlled_apply_id = P72_POWERLOTTO_BATCHA_FOURIER_RHYTHM_3BET_1500_REHEARSAL_20260526 |

### fourier30_markov30_2bet

| Field | Value |
|---|---|
| lottery_type | POWER_LOTTO |
| lifecycle | ACTIVE |
| existing_rows | 1500 (P58) |
| proposed_rows | 1500 |
| proposed_controlled_apply_id | P72_POWERLOTTO_BATCHA_FOURIER30_MARKOV30_2BET_1500_REHEARSAL_20260526 |
| duplicate_risk | LOW |
| lifecycle_gate | PASS |
| gate_result | REHEARSAL_READY |
| rollback | DELETE WHERE controlled_apply_id = P72_POWERLOTTO_BATCHA_FOURIER30_MARKOV30_2BET_1500_REHEARSAL_20260526 |

### 539_3bet_orthogonal

| Field | Value |
|---|---|
| lottery_type | DAILY_539 |
| lifecycle | ACTIVE |
| existing_rows | 1500 (P37) |
| proposed_rows | 1500 |
| proposed_controlled_apply_id | P72_539_BATCHB1_539_3BET_ORTHOGONAL_1500_REHEARSAL_20260526 |
| duplicate_risk | LOW |
| lifecycle_gate | PASS |
| gate_result | REHEARSAL_READY |
| rollback | DELETE WHERE controlled_apply_id = P72_539_BATCHB1_539_3BET_ORTHOGONAL_1500_REHEARSAL_20260526 |

### acb_single_539

| Field | Value |
|---|---|
| lottery_type | DAILY_539 |
| lifecycle | ACTIVE |
| existing_rows | 1500 (P37) |
| proposed_rows | 1500 |
| proposed_controlled_apply_id | P72_539_BATCHB1_ACB_SINGLE_539_1500_REHEARSAL_20260526 |
| duplicate_risk | LOW |
| lifecycle_gate | PASS |
| gate_result | REHEARSAL_READY |
| rollback | DELETE WHERE controlled_apply_id = P72_539_BATCHB1_ACB_SINGLE_539_1500_REHEARSAL_20260526 |

### midfreq_acb_2bet

| Field | Value |
|---|---|
| lottery_type | DAILY_539 |
| lifecycle | RETIRED |
| existing_rows | 1500 (P31B) |
| proposed_rows | 1500 |
| proposed_controlled_apply_id | P72_539_BATCHB2_MIDFREQ_ACB_2BET_1500_REHEARSAL_20260526 |
| duplicate_risk | LOW |
| lifecycle_gate | RETIRED_PROMOTION_REQUIRED_BEFORE_PRODUCTION |
| gate_result | REHEARSAL_READY |
| rollback | DELETE WHERE controlled_apply_id = P72_539_BATCHB2_MIDFREQ_ACB_2BET_1500_REHEARSAL_20260526 |

### midfreq_fourier_2bet ⚠️ DUAL STRATEGY_ID RISK

| Field | Value |
|---|---|
| lottery_type | DAILY_539 (enforce via filter) |
| lifecycle | RETIRED |
| existing_rows (DAILY_539) | 1500 (P31B) |
| existing_rows (POWER_LOTTO) | 1500 (P48) — MUST REMAIN UNCHANGED |
| proposed_rows | 1500 (DAILY_539 only) |
| proposed_controlled_apply_id | P72_539_BATCHB2_MIDFREQ_FOURIER_2BET_1500_REHEARSAL_20260526 |
| dual_strategy_id_risk | TRUE — exists in both POWER_LOTTO and DAILY_539 |
| required_filter | lottery_type = 'DAILY_539' |
| post_apply_verification | SELECT COUNT(*) ... WHERE strategy_id='midfreq_fourier_2bet' AND lottery_type='POWER_LOTTO'; must be 1500 |
| lifecycle_gate | RETIRED_PROMOTION_REQUIRED_BEFORE_PRODUCTION |
| gate_result | REHEARSAL_READY |
| rollback | DELETE WHERE controlled_apply_id = P72_539_BATCHB2_MIDFREQ_FOURIER_2BET_1500_REHEARSAL_20260526 |

### acb_1bet

| Field | Value |
|---|---|
| lottery_type | DAILY_539 |
| lifecycle | RETIRED |
| existing_rows | 1500 (P31B) |
| proposed_rows | 1500 |
| proposed_controlled_apply_id | P72_539_BATCHB3_ACB_1BET_1500_REHEARSAL_20260526 |
| duplicate_risk | LOW |
| lifecycle_gate | RETIRED_PROMOTION_REQUIRED_BEFORE_PRODUCTION |
| gate_result | REHEARSAL_READY |
| rollback | DELETE WHERE controlled_apply_id = P72_539_BATCHB3_ACB_1BET_1500_REHEARSAL_20260526 |

### acb_markov_midfreq_3bet

| Field | Value |
|---|---|
| lottery_type | DAILY_539 |
| lifecycle | RETIRED |
| existing_rows | 1500 (P31B) |
| proposed_rows | 1500 |
| proposed_controlled_apply_id | P72_539_BATCHB3_ACB_MARKOV_MIDFREQ_3BET_1500_REHEARSAL_20260526 |
| duplicate_risk | LOW |
| lifecycle_gate | RETIRED_PROMOTION_REQUIRED_BEFORE_PRODUCTION |
| gate_result | REHEARSAL_READY |
| rollback | DELETE WHERE controlled_apply_id = P72_539_BATCHB3_ACB_MARKOV_MIDFREQ_3BET_1500_REHEARSAL_20260526 |

---

## Batch B2 Dual Strategy_id Mitigation

`midfreq_fourier_2bet` exists in **both** POWER_LOTTO and DAILY_539:

| scope | rows | source |
|---|---|---|
| DAILY_539 | 1500 | P31B — target for apply |
| POWER_LOTTO | 1500 | P48 — must remain 1500 |

**Required action on any future apply**:
1. Enforce `WHERE lottery_type = 'DAILY_539'` on all INSERT/SELECT
2. Post-apply: `SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='midfreq_fourier_2bet' AND lottery_type='POWER_LOTTO';` — must return 1500
3. If not 1500 → rollback immediately

---

## Batch B2/B3 Lifecycle Gate Notes

Batches B2 and B3 contain **RETIRED** strategies sourced from P31B.

| Aspect | Status |
|---|---|
| Rehearsal allowed | YES — RETIRED strategies may participate in temp rehearsal |
| Production apply allowed | NO — requires lifecycle promotion authorization |
| Required gate before production | `lifecycle_promotion_authorized` in future task |
| Lifecycle promotion phrase required | (to be defined in P73+) |

---

## Proposed Row Impact (Rehearsal — No Rows Written)

| Scenario | New Rows | Rows After Apply |
|---|---|---|
| P72 rehearsal (REHEARSAL_ONLY) | 0 | **46960** |
| If all 8 × 1500 applied (future) | 12000 | 58960 |
| If active lifecycle 4 × 1500 only (future) | 6000 | 52960 |

---

## Controlled Apply ID Naming Scheme

| Scheme | Pattern |
|---|---|
| Rehearsal | `P72_<LOTTERY>_<BATCH>_<STRATEGY>_<ROWS>_REHEARSAL_<YYYYMMDD>` |
| Production | `P72_<LOTTERY>_<BATCH>_<STRATEGY>_<ROWS>_PROD_<YYYYMMDD>` |

Examples:

| Batch | Example ID |
|---|---|
| Batch A #1 (rehearsal) | P72_POWERLOTTO_BATCHA_FOURIER_RHYTHM_3BET_1500_REHEARSAL_20260526 |
| Batch A #2 (rehearsal) | P72_POWERLOTTO_BATCHA_FOURIER30_MARKOV30_2BET_1500_REHEARSAL_20260526 |
| Batch B1 #1 (rehearsal) | P72_539_BATCHB1_539_3BET_ORTHOGONAL_1500_REHEARSAL_20260526 |
| Batch B1 #2 (rehearsal) | P72_539_BATCHB1_ACB_SINGLE_539_1500_REHEARSAL_20260526 |
| Batch B2 #1 (rehearsal) | P72_539_BATCHB2_MIDFREQ_ACB_2BET_1500_REHEARSAL_20260526 |
| Batch B2 #2 (rehearsal) | P72_539_BATCHB2_MIDFREQ_FOURIER_2BET_1500_REHEARSAL_20260526 |
| Batch B3 #1 (rehearsal) | P72_539_BATCHB3_ACB_1BET_1500_REHEARSAL_20260526 |
| Batch B3 #2 (rehearsal) | P72_539_BATCHB3_ACB_MARKOV_MIDFREQ_3BET_1500_REHEARSAL_20260526 |

---

## Duplicate Prevention Plan

1. Each apply uses a unique `controlled_apply_id` per strategy per run
2. Pre-apply check: `SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?; -- must be 0`
3. Row-level check: `SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND target_draw=? AND lottery_type=?`
4. Abort on any duplicate
5. Post-apply: verify total rows = expected (46960 + N × 1500)

---

## Rollback / Restore Plan

```sql
-- Pre-apply backup (before any write)
cp lottery_api/data/lottery_v2.db lottery_api/data/lottery_v2.db.bak_p72_<timestamp>

-- Full P72 rollback
DELETE FROM strategy_prediction_replays WHERE controlled_apply_id LIKE 'P72_%';
SELECT COUNT(*) FROM strategy_prediction_replays; -- must be 46960

-- Per-batch rollback
DELETE FROM strategy_prediction_replays WHERE controlled_apply_id LIKE 'P72_POWERLOTTO_BATCHA_%';
DELETE FROM strategy_prediction_replays WHERE controlled_apply_id LIKE 'P72_539_BATCHB1_%';
DELETE FROM strategy_prediction_replays WHERE controlled_apply_id LIKE 'P72_539_BATCHB2_%';
DELETE FROM strategy_prediction_replays WHERE controlled_apply_id LIKE 'P72_539_BATCHB3_%';
```

---

## Required Future Production Apply Gates

### All Batches

1. `explicit_apply_authorization_phrase_YES_apply_P71_controlled_replay_rows`
2. `temp_db_rehearsal_pass`
3. `duplicate_check_pass`
4. `rollback_plan_confirmed`
5. `drift_guard_pass`
6. `branch_governance_pass`
7. `post_apply_row_count_verified`
8. `api_verification_pass`

### Batch B2 + B3 Additional

1. `lifecycle_promotion_gate`
2. `temp_rehearsal_evidence_committed`
3. `retired_strategies_promotion_authorized`

### Batch B2 midfreq_fourier_2bet Additional

1. `lottery_type_filter_confirmed_DAILY_539`
2. `post_apply_power_lotto_rows_still_1500`

---

## Risk Table

| Risk | Level | Mitigation |
|---|---|---|
| midfreq_fourier_2bet dual ID contamination | HIGH | lottery_type filter enforced; post-apply POWER_LOTTO rows verified |
| RETIRED lifecycle promotion | MEDIUM | lifecycle gate required before production; rehearsal only in P72 |
| Duplicate row insertion | LOW | controlled_apply_id uniqueness pre-check |
| DB drift during apply | LOW | drift guard + pre/post row count |
| Batch B1 DAILY_539 m3+ baseline low (~1.07%) | LOW | acknowledged; still above random for 539 |

---

## Governance Confirmations

| Confirmation | Status |
|---|---|
| No DB write in P72 | ✓ CONFIRMED |
| No production replay row insert | ✓ CONFIRMED |
| No force push | ✓ CONFIRMED |
| No lifecycle promotion | ✓ CONFIRMED |
| No champion replacement | ✓ CONFIRMED |
| No registry mutation | ✓ CONFIRMED |
| No P6 remote sync debt resolution | ✓ CONFIRMED |
| Requires future explicit apply authorization | ✓ CONFIRMED |

---

## Final Classification

```
P72_CONTROLLED_APPLY_REHEARSAL_MERGED_TO_MAIN
```

Production rows: **46960 → 46960** (rehearsal-only, no DB write)
