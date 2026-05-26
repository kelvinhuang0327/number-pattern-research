# P70 Controlled Apply Proposal

## PROJECT_CONTEXT_LOCK

**Project**: LotteryNew
**Repo**: /Users/kelvin/Kelvin-WorkSpace/LotteryNew
**Branch**: p70-controlled-apply-proposal
**HEAD**: origin/main:d729a4c (P69 merge)
**Date**: 2026-05-26

---

## Pre-flight Results

| Check | Result |
|---|---|
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew ✓ |
| Branch | p70-controlled-apply-proposal ✓ |
| Production rows before | 46960 ✓ |
| Production rows after (P70) | 46960 (no DB write) ✓ |
| P58 controlled_apply_id rows | 1500 ✓ |
| P66 COLD_COMPLEMENT rows | 1500 ✓ |
| P66 ZONAL_ENTROPY rows | 1500 ✓ |
| Drift guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS ✓ |
| Branch governance | BRANCH_GOVERNANCE_PASS rows=46960 ✓ |
| Cross-project contamination | CLEAN (novel_hybrid_lotto and "novel axis" are LotteryNew-internal) ✓ |

---

## P2 Audit Gate Summary

- **Source**: `outputs/replay/p2_prediction_helpfulness_audit_20260526.json`
- **Merged at**: a736621 (PR #189)
- **Total strategies audited**: 31
- **Prediction-helpful**: 8
- **Sub-baseline**: 5
- **Insufficient evidence**: 18
- **Gate**: PASSED

---

## P69 Dry-Run Plan Summary

- **Source**: `outputs/replay/p69_all_strategy_dry_run_batch_plan_20260526.json`
- **Merged at**: d729a4c (PR #191)
- **Authorized candidates**: 8
- **Batch A (POWER_LOTTO)**: 2
- **Batch B (DAILY_539)**: 6
- **Production rows unchanged**: 46960 → 46960
- **Classification**: P69_ALL_STRATEGY_DRY_RUN_BATCH_PLAN_MERGED_TO_MAIN

---

## Authorized Candidates (8)

All candidates are from P2 prediction-helpfulness audit and P69 dry-run batch plan.

| # | strategy_id | game | lifecycle | m3+% | vs baseline | p69 batch | final recommendation |
|---|---|---|---|---|---|---|---|
| 1 | fourier_rhythm_3bet | POWER_LOTTO | ONLINE | 4.93% | +1.06% | A | **propose-apply-next** |
| 2 | fourier30_markov30_2bet | POWER_LOTTO | ACTIVE | 4.07% | +0.20% | A | **propose-apply-next** |
| 3 | 539_3bet_orthogonal | DAILY_539 | ACTIVE | 1.07% | +0.07% | B1 | **propose-apply-next** |
| 4 | acb_single_539 | DAILY_539 | ACTIVE | 1.07% | +0.07% | B1 | **propose-apply-next** |
| 5 | midfreq_acb_2bet | DAILY_539 | RETIRED | 1.27% | +0.27% | B2 | **propose-temp-rehearsal-first** |
| 6 | midfreq_fourier_2bet | DAILY_539 | RETIRED | 1.27% | +0.27% | B2 | **propose-temp-rehearsal-first** |
| 7 | acb_1bet | DAILY_539 | RETIRED | 1.07% | +0.07% | B3 | **propose-temp-rehearsal-first** |
| 8 | acb_markov_midfreq_3bet | DAILY_539 | RETIRED | 1.07% | +0.07% | B3 | **propose-temp-rehearsal-first** |

POWER_LOTTO baseline: 3.87% | DAILY_539 baseline: 1.00%

---

## Explicit Exclusions

| strategy_id | game | reason | action |
|---|---|---|---|
| BIG_LOTTO (all strategies) | BIG_LOTTO | signal space exhausted — all at or below 2.40% baseline | **block** |
| cold_complement_2bet | POWER_LOTTO | sub-baseline (3.67%, −0.20% vs baseline) | **block** |
| zonal_entropy_2bet | POWER_LOTTO | fallback-equivalent (3.67%, −0.20% vs baseline) | **block** |
| midfreq_fourier_mk_3bet | POWER_LOTTO | deferred pending OOS gates at 150/300/500 draws (4.40%, +0.53%) | **defer** |

---

## Per-Strategy Apply Proposal

### Strategy 1: fourier_rhythm_3bet (POWER_LOTTO)

| Field | Value |
|---|---|
| Game type | POWER_LOTTO |
| P2 label | prediction-helpful |
| Lifecycle | ONLINE |
| P69 batch | A |
| m3+ hit rate | 4.93% |
| vs baseline | +1.06% above 3.87% |
| Current production rows | 1500 (P19B_POWERLOTTO_FOURIER_1500_PROD_20260520) |
| Adapter | p47_wave4_powerlotto_adapters.py |
| Proposed apply depth | 1500 draws |
| Expected new rows (if applied) | 1500 |
| Duplicate prevention | REQUIRED — verify no overlap with existing P19B rows |
| Rollback plan | REQUIRED |
| Temp rehearsal | Not required (ONLINE lifecycle) |
| API verification | REQUIRED |
| UI labeling | REQUIRED |
| Risk | LOW |
| **Final recommendation** | **propose-apply-next** |

Notes: Strongest POWER_LOTTO signal. ONLINE lifecycle means proven adapter and no promotion gate needed.

---

### Strategy 2: fourier30_markov30_2bet (POWER_LOTTO)

| Field | Value |
|---|---|
| Game type | POWER_LOTTO |
| P2 label | prediction-helpful |
| Lifecycle | ACTIVE |
| P69 batch | A |
| m3+ hit rate | 4.07% |
| vs baseline | +0.20% above 3.87% |
| Current production rows | 1500 (P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525) |
| Adapter | p56_wave5_powerlotto_adapters.py |
| Proposed apply depth | 1500 draws |
| Expected new rows (if applied) | 1500 |
| Duplicate prevention | REQUIRED — verify no overlap with existing P58 rows |
| Rollback plan | REQUIRED |
| Temp rehearsal | Not required (ACTIVE lifecycle) |
| API verification | REQUIRED |
| UI labeling | REQUIRED |
| Risk | LOW |
| **Final recommendation** | **propose-apply-next** |

Notes: Recently applied via P58 (Wave 5). ACTIVE lifecycle, solid signal margin.

---

### Strategy 3: 539_3bet_orthogonal (DAILY_539)

| Field | Value |
|---|---|
| Game type | DAILY_539 |
| P2 label | prediction-helpful |
| Lifecycle | ACTIVE |
| P69 batch | B1 |
| m3+ hit rate | 1.07% |
| vs baseline | +0.07% above 1.00% |
| Current production rows | 1500 (P37_DAILY539_WAVE2_9000_PROD_20260523) |
| Adapter | p36_wave2_daily539_adapters.py |
| Proposed apply depth | 1500 draws |
| Expected new rows (if applied) | 1500 |
| Duplicate prevention | REQUIRED |
| Rollback plan | REQUIRED |
| Temp rehearsal | Not required (ACTIVE lifecycle) |
| API verification | REQUIRED |
| UI labeling | REQUIRED |
| Risk | LOW |
| **Final recommendation** | **propose-apply-next** |

Notes: ACTIVE lifecycle with P37 Wave 2 adapter. Apply after Batch A validates.

---

### Strategy 4: acb_single_539 (DAILY_539)

| Field | Value |
|---|---|
| Game type | DAILY_539 |
| P2 label | prediction-helpful |
| Lifecycle | ACTIVE |
| P69 batch | B1 |
| m3+ hit rate | 1.07% |
| vs baseline | +0.07% above 1.00% |
| Current production rows | 1500 (P37_DAILY539_WAVE2_9000_PROD_20260523) |
| Adapter | p36_wave2_daily539_adapters.py |
| Proposed apply depth | 1500 draws |
| Expected new rows (if applied) | 1500 |
| Duplicate prevention | REQUIRED |
| Rollback plan | REQUIRED |
| Temp rehearsal | Not required (ACTIVE lifecycle) |
| API verification | REQUIRED |
| UI labeling | REQUIRED |
| Risk | LOW |
| **Final recommendation** | **propose-apply-next** |

Notes: Shares P37 adapter with 539_3bet_orthogonal. Apply in same Batch B1 sweep.

---

### Strategy 5: midfreq_acb_2bet (DAILY_539)

| Field | Value |
|---|---|
| Game type | DAILY_539 |
| P2 label | prediction-helpful |
| Lifecycle | RETIRED |
| P69 batch | B2 |
| m3+ hit rate | 1.27% |
| vs baseline | +0.27% above 1.00% — highest DAILY_539 signal |
| Current production rows | 1500 (P31B_DAILY539_RETIRED_7500_PROD_20260523) |
| Adapter | p31a_wave1_retired_adapters.py |
| Proposed apply depth | 1500 draws |
| Expected new rows (if applied) | 1500 |
| Duplicate prevention | REQUIRED |
| Rollback plan | REQUIRED |
| Temp rehearsal | **REQUIRED** (RETIRED lifecycle) |
| Lifecycle promotion gate | **REQUIRED** before production apply |
| API verification | REQUIRED |
| UI labeling | REQUIRED |
| Risk | MEDIUM |
| **Final recommendation** | **propose-temp-rehearsal-first** |

Notes: Highest DAILY_539 signal at +0.27%. RETIRED lifecycle requires promotion gate before production apply. Priority in Batch B2 due to signal strength.

---

### Strategy 6: midfreq_fourier_2bet (DAILY_539)

| Field | Value |
|---|---|
| Game type | DAILY_539 |
| P2 label | prediction-helpful |
| Lifecycle | RETIRED |
| P69 batch | B2 |
| m3+ hit rate | 1.27% |
| vs baseline | +0.27% above 1.00% — highest DAILY_539 signal |
| Current production rows | 1500 DAILY_539 + 1500 POWER_LOTTO (dual strategy_id) |
| Adapter | p31a_wave1_retired_adapters.py |
| Proposed apply depth | 1500 draws (DAILY_539 only) |
| Expected new rows (if applied) | 1500 (DAILY_539 only) |
| Duplicate prevention | REQUIRED |
| Rollback plan | REQUIRED |
| Temp rehearsal | **REQUIRED** (RETIRED lifecycle) |
| Lifecycle promotion gate | **REQUIRED** before production apply |
| Lottery type filter gate | **REQUIRED — DAILY_539 only** |
| API verification | REQUIRED |
| UI labeling | REQUIRED |
| Risk | MEDIUM-HIGH |
| **Final recommendation** | **propose-temp-rehearsal-first** |

⚠️ **WARNING**: This strategy_id exists in both POWER_LOTTO (4.67% m3+, P48 apply, ACTIVE) and DAILY_539 (1.27% m3+, P31B apply, RETIRED). P70 targets the **DAILY_539 version ONLY**. A mandatory `lottery_type_filter_confirmed_DAILY_539` gate must be confirmed before any apply. POWER_LOTTO rows must remain unaffected.

---

### Strategy 7: acb_1bet (DAILY_539)

| Field | Value |
|---|---|
| Game type | DAILY_539 |
| P2 label | prediction-helpful |
| Lifecycle | RETIRED |
| P69 batch | B3 |
| m3+ hit rate | 1.07% |
| vs baseline | +0.07% above 1.00% |
| Current production rows | 1500 (P31B_DAILY539_RETIRED_7500_PROD_20260523) |
| Adapter | p31a_wave1_retired_adapters.py |
| Proposed apply depth | 1500 draws |
| Expected new rows (if applied) | 1500 |
| Duplicate prevention | REQUIRED |
| Rollback plan | REQUIRED |
| Temp rehearsal | **REQUIRED** (RETIRED lifecycle) |
| Lifecycle promotion gate | **REQUIRED** before production apply |
| API verification | REQUIRED |
| UI labeling | REQUIRED |
| Risk | MEDIUM |
| **Final recommendation** | **propose-temp-rehearsal-first** |

Notes: Standard margin at +0.07%. Apply in Batch B3 after Batch B2 validates.

---

### Strategy 8: acb_markov_midfreq_3bet (DAILY_539)

| Field | Value |
|---|---|
| Game type | DAILY_539 |
| P2 label | prediction-helpful |
| Lifecycle | RETIRED |
| P69 batch | B3 |
| m3+ hit rate | 1.07% |
| vs baseline | +0.07% above 1.00% |
| Current production rows | 1500 (P31B_DAILY539_RETIRED_7500_PROD_20260523) |
| Adapter | p31a_wave1_retired_adapters.py |
| Proposed apply depth | 1500 draws |
| Expected new rows (if applied) | 1500 |
| Duplicate prevention | REQUIRED |
| Rollback plan | REQUIRED |
| Temp rehearsal | **REQUIRED** (RETIRED lifecycle) |
| Lifecycle promotion gate | **REQUIRED** before production apply |
| API verification | REQUIRED |
| UI labeling | REQUIRED |
| Risk | MEDIUM |
| **Final recommendation** | **propose-temp-rehearsal-first** |

Notes: Standard margin at +0.07%. Apply in Batch B3 after Batch B2 validates.

---

## Batch Sequencing Recommendation

Apply in 4 sequential batches:

```
Batch A  ──► Batch B1  ──► Batch B2 (after promotion gate)  ──► Batch B3 (after promotion gate)
```

| Batch | Game | Strategies | Lifecycle | Sequence | Prerequisite | Depth | New Rows |
|---|---|---|---|---|---|---|---|
| A | POWER_LOTTO | fourier_rhythm_3bet, fourier30_markov30_2bet | ONLINE/ACTIVE | 1st | explicit apply authorization | 1500 each | 3000 |
| B1 | DAILY_539 | 539_3bet_orthogonal, acb_single_539 | ACTIVE/ACTIVE | 2nd | Batch A verified | 1500 each | 3000 |
| B2 | DAILY_539 | midfreq_acb_2bet, midfreq_fourier_2bet | RETIRED/RETIRED | 3rd | B1 verified + promotion gate + temp rehearsal | 1500 each | 3000 |
| B3 | DAILY_539 | acb_1bet, acb_markov_midfreq_3bet | RETIRED/RETIRED | 4th | B2 verified + promotion gate + temp rehearsal | 1500 each | 3000 |

---

## Expected Production Row Impact (If Later Authorized)

> **⚠ P70 does NOT write production rows. These are proposed values only.**

| Scenario | New Rows | Before | After |
|---|---|---|---|
| All 8 applied at 1500 draws | 12000 | 46960 | **58960** |
| Batch A + B1 only (4 ACTIVE strategies) | 6000 | 46960 | **52960** |
| Batch A only (2 POWER_LOTTO) | 3000 | 46960 | **49960** |

---

## Required Gates Before Real Apply

### All Batches

1. **Explicit apply authorization** — separate authorization phrase in a future P71+ task
2. **Dry-run artifact present** — P70 proposal document committed and merged
3. **Temp DB rehearsal pass** — temp DB write verified before production write
4. **Duplicate check pass** — verify no draw overlap with existing rows
5. **Rollback plan confirmed** — snapshot or backup prior to apply
6. **Branch governance guard pass** — `scripts/replay_branch_governance_guard.py`
7. **Replay lifecycle drift guard pass** — `scripts/replay_lifecycle_drift_guard.py`
8. **API verification pass** — HTTP endpoints return correct new rows
9. **Post-apply row-count verification** — `SELECT COUNT(*) FROM strategy_prediction_replays` matches expected

### Batch B2 and B3 Additional Gates

10. **Lifecycle promotion gate** — RETIRED → documented promotion evidence
11. **Promotion evidence committed** — promotion decision documented in `docs/replay/`

### midfreq_fourier_2bet Specific Gate

12. **lottery_type_filter_confirmed_DAILY_539** — explicit confirmation apply targets DAILY_539 only
13. **POWER_LOTTO rows unaffected verification** — verify midfreq_fourier_2bet POWER_LOTTO rows unchanged after apply

---

## Risk Table

| Risk | Severity | Affected Strategies | Mitigation |
|---|---|---|---|
| RETIRED lifecycle apply without promotion gate | HIGH | acb_1bet, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet | Batch B2/B3 gated behind lifecycle_promotion_gate |
| midfreq_fourier_2bet dual strategy_id contaminates POWER_LOTTO rows | HIGH | midfreq_fourier_2bet | lottery_type_filter_confirmed_DAILY_539 mandatory gate |
| Duplicate rows from overlapping draw windows | MEDIUM | All 8 candidates | duplicate_check_pass required for all batches |
| Production row count drift from apply error | MEDIUM | All 8 candidates | post_apply_row_count_verification; rollback_plan required |
| Adapter incompatibility after wave upgrade | LOW | acb_1bet, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet | temp_db_rehearsal_pass; use original controlled_apply_id adapters |
| P6 remote sync debt conflicts during PR | LOW | All | P70 branch created from origin/main; P6 debt not resolved in P70 |

---

## Governance Confirmations

| Constraint | Status |
|---|---|
| No DB write | CONFIRMED |
| No production replay row insert | CONFIRMED |
| No force push | CONFIRMED |
| No lifecycle promotion | CONFIRMED |
| No champion replacement | CONFIRMED |
| No registry mutation | CONFIRMED |
| No controlled apply execution | CONFIRMED |
| No UI/browser smoke | CONFIRMED |
| No P6 remote sync debt resolution | CONFIRMED |
| Requires future explicit apply authorization | CONFIRMED |
| P70 is proposal-only and evidence-only | CONFIRMED |

---

## Final Classification

**P70_CONTROLLED_APPLY_PROPOSAL_READY**

Future production apply requires a separate explicit authorization phrase in P71 or later.
