# P71 Controlled Apply Readiness Gate

## PROJECT_CONTEXT_LOCK

```
Project = LotteryNew
Canonical Repo = /Users/kelvin/Kelvin-WorkSpace/LotteryNew
Canonical Branch = main
This document applies ONLY to LotteryNew.
```

---

## Identity

| Field | Value |
|---|---|
| Task | P71_CONTROLLED_APPLY_READINESS_GATE |
| Created | 2026-05-26 |
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |
| Branch | p71-controlled-apply-readiness-gate |
| HEAD | origin/main:77eed80 |
| P70 Base Commit | 77eed80 |

---

## Authorization Mode

**READINESS_ONLY**

The phrase `YES apply P71 controlled replay rows` is absent from this task. No production DB write is authorized. This document represents a readiness gate only — it determines whether each candidate is prepared for a future controlled apply in P72+.

---

## Pre-flight Results

| Check | Result |
|---|---|
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew ✓ |
| Branch | p71-controlled-apply-readiness-gate ✓ |
| Production rows | 46960 ✓ |
| P58 controlled_apply_id rows | 1500 ✓ |
| P66 cold_complement rows | 1500 ✓ |
| P66 zonal_entropy rows | 1500 ✓ |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS ✓ |
| Branch governance | BRANCH_GOVERNANCE_PASS ✓ |
| Cross-project contamination | CLEAN (novel_hybrid_lotto = LotteryNew-internal) ✓ |

---

## P2 Audit Gate Summary

| Field | Value |
|---|---|
| Source | outputs/replay/p2_prediction_helpfulness_audit_20260526.json |
| Merged at | a736621 (PR #189) |
| Total strategies audited | 31 |
| Prediction-helpful count | 8 |
| Sub-baseline count | 5 |
| Insufficient-evidence count | 18 |
| Gate | PASSED |

---

## P69 Dry-Run Plan Summary

| Field | Value |
|---|---|
| Source | outputs/replay/p69_all_strategy_dry_run_batch_plan_20260526.json |
| Merged at | d729a4c (PR #191) |
| Authorized candidates | 8 |
| Batch A (POWER_LOTTO) | 2 strategies |
| Batch B (DAILY_539) | 6 strategies |
| Production rows unchanged | true |
| Classification | P69_ALL_STRATEGY_DRY_RUN_BATCH_PLAN_MERGED_TO_MAIN |

---

## P70 Controlled Apply Proposal Summary

| Field | Value |
|---|---|
| Source | outputs/replay/p70_controlled_apply_proposal_20260526.json |
| Merged at | 77eed80 (PR #192) |
| Authorized candidates | 8 |
| Batch sequence | A → B1 → B2 → B3 |
| Production rows unchanged | true |
| Classification | P70_CONTROLLED_APPLY_PROPOSAL_MERGED_TO_MAIN |

---

## Candidate List (8 Authorized)

### POWER_LOTTO (Batch A)

| strategy_id | lifecycle | m3+% | vs baseline | existing rows | apply_id | readiness |
|---|---|---|---|---|---|---|
| fourier_rhythm_3bet | ONLINE | 4.93% | +1.06% | 1500 | P19B | READY_FOR_CONTROLLED_APPLY |
| fourier30_markov30_2bet | ACTIVE | 4.07% | +0.20% | 1500 | P58 | READY_FOR_CONTROLLED_APPLY |

### DAILY_539 Batch B1 (ACTIVE)

| strategy_id | lifecycle | m3+% | vs baseline | existing rows | apply_id | readiness |
|---|---|---|---|---|---|---|
| 539_3bet_orthogonal | ACTIVE | 1.07% | +0.07% | 1500 | P37 | READY_FOR_CONTROLLED_APPLY |
| acb_single_539 | ACTIVE | 1.07% | +0.07% | 1500 | P37 | READY_FOR_CONTROLLED_APPLY |

### DAILY_539 Batch B2 (RETIRED — high margin)

| strategy_id | lifecycle | m3+% | vs baseline | existing rows | apply_id | readiness |
|---|---|---|---|---|---|---|
| midfreq_acb_2bet | RETIRED | 1.27% | +0.27% | 1500 | P31B | READY_AFTER_TEMP_REHEARSAL |
| midfreq_fourier_2bet | RETIRED | 1.27% | +0.27% | 1500 | P31B | READY_AFTER_TEMP_REHEARSAL ⚠️ dual ID |

### DAILY_539 Batch B3 (RETIRED — standard margin)

| strategy_id | lifecycle | m3+% | vs baseline | existing rows | apply_id | readiness |
|---|---|---|---|---|---|---|
| acb_1bet | RETIRED | 1.07% | +0.07% | 1500 | P31B | READY_AFTER_TEMP_REHEARSAL |
| acb_markov_midfreq_3bet | RETIRED | 1.07% | +0.07% | 1500 | P31B | READY_AFTER_TEMP_REHEARSAL |

---

## Exclusions

| strategy / scope | reason | classification |
|---|---|---|
| BIG_LOTTO (all strategies) | Signal space exhausted — all ≤ 2.40% baseline | EXCLUDED_SIGNAL_SATURATION |
| cold_complement_2bet | Sub-baseline: 3.67% vs 3.87% (−0.20%) | EXCLUDED_SUB_BASELINE |
| zonal_entropy_2bet | Fallback-equivalent: 3.67% vs 3.87% (−0.20%) | EXCLUDED_FALLBACK_EQUIVALENT |
| midfreq_fourier_mk_3bet | Deferred pending OOS at 150/300/500 draws (4.40%, +0.53%) | EXCLUDED_DEFERRED_OOS |

---

## Per-Strategy Readiness Detail

### fourier_rhythm_3bet (POWER_LOTTO)

| Field | Value |
|---|---|
| Lifecycle | ONLINE |
| m3+ confirmed | 74/1500 = 4.93% |
| Draw range | 101000002 – 115000040 |
| Adapter | lottery_api/models/p47_wave4_powerlotto_adapters.py |
| Temp rehearsal | NOT required |
| Duplicate check | Required vs P19B rows |
| Rollback | Required |
| API verification | Required |
| Blockers | None |
| **Readiness** | **READY_FOR_CONTROLLED_APPLY** |

### fourier30_markov30_2bet (POWER_LOTTO)

| Field | Value |
|---|---|
| Lifecycle | ACTIVE |
| m3+ confirmed | 61/1500 = 4.07% |
| Draw range | 101000002 – 115000040 |
| Adapter | lottery_api/models/p56_wave5_powerlotto_adapters.py |
| Temp rehearsal | NOT required |
| Duplicate check | Required vs P58 rows |
| Rollback | Required |
| API verification | Required |
| Blockers | None |
| **Readiness** | **READY_FOR_CONTROLLED_APPLY** |

### 539_3bet_orthogonal (DAILY_539)

| Field | Value |
|---|---|
| Lifecycle | ACTIVE |
| m3+ confirmed | 16/1500 = 1.07% |
| Draw range | 110000190 – 115000121 |
| Adapter | lottery_api/models/p36_daily539_wave2_adapters.py |
| Temp rehearsal | NOT required |
| Duplicate check | Required vs P37 rows |
| Rollback | Required |
| API verification | Required |
| Blockers | None |
| **Readiness** | **READY_FOR_CONTROLLED_APPLY** |

### acb_single_539 (DAILY_539)

| Field | Value |
|---|---|
| Lifecycle | ACTIVE |
| m3+ confirmed | 16/1500 = 1.07% |
| Draw range | 110000190 – 115000121 |
| Adapter | lottery_api/models/p36_daily539_wave2_adapters.py |
| Temp rehearsal | NOT required |
| Duplicate check | Required vs P37 rows |
| Rollback | Required |
| API verification | Required |
| Blockers | None |
| **Readiness** | **READY_FOR_CONTROLLED_APPLY** |

### midfreq_acb_2bet (DAILY_539)

| Field | Value |
|---|---|
| Lifecycle | RETIRED |
| m3+ confirmed | 19/1500 = 1.27% |
| Draw range | 110000190 – 115000121 |
| Adapter | lottery_api/models/p31a_daily539_wave1_adapters.py |
| Temp rehearsal | **REQUIRED** |
| Duplicate check | Required vs P31B rows |
| Rollback | Required |
| API verification | Required |
| Blockers | lifecycle_promotion_gate_not_yet_executed; temp_rehearsal_not_yet_passed |
| **Readiness** | **READY_AFTER_TEMP_REHEARSAL** |

### midfreq_fourier_2bet (DAILY_539) ⚠️ DUAL STRATEGY_ID RISK

| Field | Value |
|---|---|
| Lifecycle | RETIRED (DAILY_539) |
| m3+ confirmed | 19/1500 = 1.27% (DAILY_539) |
| POWER_LOTTO rows | 1500 (P48, 4.67% — EXCLUDED from P70, must remain unchanged) |
| Draw range | 110000190 – 115000121 (DAILY_539) |
| Adapter | lottery_api/models/p31a_daily539_wave1_adapters.py |
| Temp rehearsal | **REQUIRED** |
| Duplicate check | Required vs P31B DAILY_539 rows only |
| Rollback | Required |
| API verification | Required |
| Blockers | lifecycle_promotion_gate; temp_rehearsal; **lottery_type_filter_gate** |
| **Readiness** | **READY_AFTER_TEMP_REHEARSAL** |

> **CRITICAL**: Any future apply MUST use `WHERE lottery_type = 'DAILY_539'` filter. Post-apply verification must confirm POWER_LOTTO rows remain at 1500. This is a mandatory pre-apply gate.

### acb_1bet (DAILY_539)

| Field | Value |
|---|---|
| Lifecycle | RETIRED |
| m3+ confirmed | 16/1500 = 1.07% |
| Draw range | 110000190 – 115000121 |
| Adapter | lottery_api/models/p31a_daily539_wave1_adapters.py |
| Temp rehearsal | **REQUIRED** |
| Duplicate check | Required vs P31B rows |
| Rollback | Required |
| API verification | Required |
| Blockers | lifecycle_promotion_gate_not_yet_executed; temp_rehearsal_not_yet_passed |
| **Readiness** | **READY_AFTER_TEMP_REHEARSAL** |

### acb_markov_midfreq_3bet (DAILY_539)

| Field | Value |
|---|---|
| Lifecycle | RETIRED |
| m3+ confirmed | 16/1500 = 1.07% |
| Draw range | 110000190 – 115000121 |
| Adapter | lottery_api/models/p31a_daily539_wave1_adapters.py |
| Temp rehearsal | **REQUIRED** |
| Duplicate check | Required vs P31B rows |
| Rollback | Required |
| API verification | Required |
| Blockers | lifecycle_promotion_gate_not_yet_executed; temp_rehearsal_not_yet_passed |
| **Readiness** | **READY_AFTER_TEMP_REHEARSAL** |

---

## Batch Sequencing Recommendation

Apply in strict order. Do NOT skip batches. Validate each batch before proceeding.

| Order | Batch | Strategies | Lifecycle | Readiness | New Rows | Prerequisite |
|---|---|---|---|---|---|---|
| 1 | A | fourier_rhythm_3bet, fourier30_markov30_2bet | ONLINE, ACTIVE | READY | 3000 | explicit_apply_auth + duplicate_check + rollback_plan |
| 2 | B1 | 539_3bet_orthogonal, acb_single_539 | ACTIVE, ACTIVE | READY | 3000 | Batch A verified + explicit_apply_auth |
| 3 | B2 | midfreq_acb_2bet, midfreq_fourier_2bet | RETIRED, RETIRED | AFTER_REHEARSAL | 3000 | B1 verified + promotion_gate + temp_rehearsal + lottery_type_filter (midfreq_fourier_2bet) |
| 4 | B3 | acb_1bet, acb_markov_midfreq_3bet | RETIRED, RETIRED | AFTER_REHEARSAL | 3000 | B2 verified + promotion_gate + temp_rehearsal |

**Recommendation**: Apply batches A and B1 (4 strategies, 6000 rows) as an initial controlled wave. Gate B2/B3 behind separate lifecycle promotion authorization and temp rehearsal results.

---

## Proposed Row Impact (If Later Authorized)

| Scenario | New Rows | Rows After |
|---|---|---|
| All 8 strategies @ 1500 each | +12000 | 58960 |
| Active lifecycle only (Batch A + B1, 4 strategies) | +6000 | 52960 |
| Batch A only (2 POWER_LOTTO) | +3000 | 49960 |

Current production rows: **46960** (unchanged in P71)

---

## Controlled Apply ID Naming Scheme

Pattern: `P{N}_{LOTTERY_TYPE}_{BATCH_LABEL}_{TOTAL_ROWS}_PROD_{YYYYMMDD}`

| Future Batch | Naming Example |
|---|---|
| A (POWER_LOTTO) | P72_POWERLOTTO_BATCHA_3000_PROD_YYYYMMDD |
| B1 (DAILY_539 ACTIVE) | P72_DAILY539_BATCHB1_3000_PROD_YYYYMMDD |
| B2 (DAILY_539 RETIRED high) | P72_DAILY539_BATCHB2_RETIRED_3000_PROD_YYYYMMDD |
| B3 (DAILY_539 RETIRED std) | P72_DAILY539_BATCHB3_RETIRED_3000_PROD_YYYYMMDD |

Notes:
- P-number increments with each new authorized apply task
- YYYYMMDD = apply execution date
- Total rows = strategies_in_batch × 1500

---

## Required Gates Before Real Apply

### All Batches

1. `explicit_apply_authorization_phrase_in_future_task`
2. `dry_run_artifact_present`
3. `temp_db_rehearsal_pass`
4. `duplicate_check_pass` (vs existing rows in each batch's controlled_apply_id window)
5. `rollback_plan_confirmed`
6. `branch_governance_guard_pass`
7. `replay_lifecycle_drift_guard_pass`
8. `api_verification_pass`
9. `post_apply_row_count_verification`

### Retired Lifecycle Batches (B2 + B3) Additional

10. `lifecycle_promotion_gate`
11. `promotion_evidence_documented`
12. `temp_rehearsal_evidence_committed`

### midfreq_fourier_2bet Additional

13. `lottery_type_filter_confirmed_DAILY_539`
14. `power_lotto_rows_unaffected_pre_verification` (confirm 1500 before apply)
15. `post_apply_power_lotto_rows_still_1500`

---

## Rollback / Duplicate Prevention / API Verification Plan

### Rollback

- Pre-apply: backup `lottery_api/data/lottery_v2.db` to `lottery_v2.db.bak_p72_{timestamp}`
- Trigger: post-apply row count ≠ expected OR drift guard fails
- Method: `DELETE FROM strategy_prediction_replays WHERE controlled_apply_id = '{P72_APPLY_ID}'`
- Requires explicit rollback authorization in future task

### Duplicate Prevention

- Method: UNIQUE constraint on `(lottery_type, target_draw, strategy_id, replay_run_id)`
- Pre-apply query: `SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='{id}' AND lottery_type='{type}' AND target_draw IN ({new_draw_range})`
- Expected result: 0 before any apply
- If overlap detected: STOP apply, resolve overlap first

### API Verification

- After any apply: verify predictions are accessible via API for new draw range
- Confirm no regression in existing draw predictions
- Run `tests/test_replay_lifecycle_drift_guard.py` post-apply

---

## Risk Table

| Risk | Severity | Affected | Mitigation |
|---|---|---|---|
| RETIRED lifecycle apply without promotion gate | HIGH | acb_1bet, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet | READY_AFTER_TEMP_REHEARSAL status blocks until lifecycle_promotion_gate passed |
| midfreq_fourier_2bet dual strategy_id contaminates POWER_LOTTO | HIGH | midfreq_fourier_2bet | lottery_type_filter_confirmed_DAILY_539 + post-apply POWER_LOTTO row count check |
| Duplicate rows from overlapping draw windows | MEDIUM | All 8 | duplicate_check_pass required before any DB write |
| Row count drift from apply error | MEDIUM | All 8 | post_apply_row_count_verification; bak file required |
| Adapter incompatibility for RETIRED strategies | LOW | B2/B3 strategies | temp_db_rehearsal_pass required; use original p31a adapters |

---

## Governance Confirmations

| Governance Rule | Status |
|---|---|
| No DB write in P71 | CONFIRMED |
| No force push | CONFIRMED |
| No lifecycle promotion | CONFIRMED |
| No champion replacement | CONFIRMED |
| No registry mutation | CONFIRMED |
| No production apply without explicit phrase | CONFIRMED |
| Future apply requires separate authorization | CONFIRMED |
| P6 remote sync debt not modified | CONFIRMED |

---

## Production Rows

| Phase | Rows |
|---|---|
| Before P71 | 46960 |
| After P71 (readiness only) | 46960 |
| Change | 0 (no DB write) |

---

## Final Classification

**`P71_CONTROLLED_APPLY_READINESS_GATE_READY`**

Authorization mode: READINESS_ONLY

All 8 P70 candidates assessed. 4 candidates (Batch A + B1) are `READY_FOR_CONTROLLED_APPLY`. 4 candidates (Batch B2 + B3) are `READY_AFTER_TEMP_REHEARSAL`. No production DB write occurred. Future apply requires explicit authorization phrase in P72+.
