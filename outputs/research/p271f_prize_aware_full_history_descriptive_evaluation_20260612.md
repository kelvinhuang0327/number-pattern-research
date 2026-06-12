# P271F — Prize-Aware Full Eligible-History Descriptive Evaluation

**Task ID:** P271F_PRIZE_AWARE_FULL_HISTORY_DESCRIPTIVE_EVALUATION  
**Date:** 2026-06-12  
**Branch:** `task/p271f-prize-aware-full-history-descriptive-eval`  
**Status:** P271F_COMPLETE_WITH_POWER_ELIGIBLE_SUBSET_ONLY

---

## 1. Executive Summary

P271F ran a read-only, aggregate-only descriptive evaluation of all structurally eligible historical replay rows in the canonical DB using the P271E adapter and P271C scorer.

All structurally eligible historical rows were processed.
POWER_LOTTO results apply only to rows with a stored prediction-time second-zone value.
Missing POWER second-zone predictions were excluded and never filled.
Output is aggregate only. No raw predicted or actual number arrays were exported.
No strategy-level aggregation, comparison, or ranking was performed.
No random/null baseline was calculated. No inferential test was run.

---

## 2. Preregistered Scope and Metrics

**Authorized evaluation scope:**
- BIG_LOTTO: all structurally eligible rows
- DAILY_539: all structurally eligible rows
- POWER_LOTTO: only rows with a stored prediction-time second-zone value

**Preregistered metric contract:**
Structural metrics (9): total_replay_rows, structurally_eligible_rows, structurally_excluded_rows, exclusion_counts_by_reason, eligible_percentage, distinct_target_draws, processed_rows, causality_violation_count, ambiguous_join_count.

Prize-aware result metrics (10): main_hit_count_counts, auxiliary_hit_false_count, auxiliary_hit_true_count, any_prize_aware_win_count, any_prize_aware_win_rate, prize_tier_counts, prize_tier_rates, tier_class_counts, tier_class_rates.

M3+ coexistence metrics (4): m3_plus_false_count, m3_plus_true_count, m3_plus_rate, prize_aware_and_m3_overlap_matrix.

No additional metric was added after viewing evaluation results.

---

## 3. Canonical DB Snapshot and Read-Only Guarantees

**Canonical DB path:** `lottery_api/data/lottery_v2.db`  
**DB open mode:** sqlite3 URI mode=ro  
**Evaluation started:** 2026-06-12T11:52:04.298204+00:00  
**Evaluation finished:** 2026-06-12T11:52:05.893967+00:00  
**SQLite data_version (start):** 2  
**SQLite data_version (end):** 2  
**DB file size before:** 99368960 bytes  
**DB file size after:** 99368960 bytes  
**DB SHA-256 before:** `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e`  
**DB SHA-256 after:** `3209a533b15e7b12bb8336a6f0cf92114d18dc0ae544de71f04954bdaa1d430e`  

P271F connection is strictly read-only. No INSERT, UPDATE, DELETE, or DDL was issued.
Relevant row counts are verified unchanged before and after the evaluation.

---

## 4. Eligibility and Exclusions

| Lottery | Total Rows | Eligible | Excluded | Eligible % |
|---|---|---|---|---|
| POWER_LOTTO | 36104 | 9000 | 27104 | 24.93% |
| BIG_LOTTO | 24140 | 24140 | 0 | 100.00% |
| DAILY_539 | 34680 | 34680 | 0 | 100.00% |

**POWER_LOTTO exclusions:**

Rows excluded for `MISSING_PREDICTED_SECOND_ZONE`: 27104 (never filled, defaulted, inferred, or replaced).

---

## 5. POWER_LOTTO Eligible-Subset-Only Results

**Scope:** eligible-subset-only descriptive evaluation  
**Processed rows:** 9000  
**Distinct target draws:** 1500  
**Prize-aware win rate:** 1069/9000 = 0.118778  
**M3+ rate:** 388/9000 = 0.043111  

**Prize tier distribution:**

| Tier | Count | Rate |
|---|---|---|
| POWER_CONSOLATION_PRIZE | 485 | 0.053889 |
| POWER_EIGHTH_PRIZE | 196 | 0.021778 |
| POWER_FIFTH_PRIZE | 3 | 0.000333 |
| POWER_NINTH_PRIZE | 326 | 0.036222 |
| POWER_NO_PRIZE | 7931 | 0.881222 |
| POWER_SEVENTH_PRIZE | 42 | 0.004667 |
| POWER_SIXTH_PRIZE | 17 | 0.001889 |

**M3+ coexistence matrix:**

| | M3+ False | M3+ True |
|---|---|---|
| Prize False | 7931 | 0 |
| Prize True  | 681 | 388 |

---

## 6. BIG_LOTTO Full Eligible-History Results

**Scope:** full eligible-history descriptive evaluation  
**Processed rows:** 24140  
**Distinct target draws:** 1552  
**Prize-aware win rate:** 756/24140 = 0.031317  
**M3+ rate:** 487/24140 = 0.020174  

**Prize tier distribution:**

| Tier | Count | Rate |
|---|---|---|
| BIG_CONSOLATION_PRIZE | 269 | 0.011143 |
| BIG_FIFTH_PRIZE | 38 | 0.001574 |
| BIG_NO_PRIZE | 23384 | 0.968683 |
| BIG_SEVENTH_PRIZE | 421 | 0.017440 |
| BIG_SIXTH_PRIZE | 28 | 0.001160 |

**M3+ coexistence matrix:**

| | M3+ False | M3+ True |
|---|---|---|
| Prize False | 23384 | 0 |
| Prize True  | 269 | 487 |

---

## 7. DAILY_539 Full Eligible-History Results

**Scope:** full eligible-history descriptive evaluation  
**Processed rows:** 34680  
**Distinct target draws:** 1550  
**Prize-aware win rate:** 4333/34680 = 0.124942  
**M3+ rate:** 389/34680 = 0.011217  

**Prize tier distribution:**

| Tier | Count | Rate |
|---|---|---|
| D539_FOURTH_PRIZE | 3944 | 0.113725 |
| D539_NO_PRIZE | 30347 | 0.875058 |
| D539_SECOND_PRIZE | 4 | 0.000115 |
| D539_THIRD_PRIZE | 385 | 0.011101 |

**M3+ coexistence matrix:**

| | M3+ False | M3+ True |
|---|---|---|
| Prize False | 30347 | 0 |
| Prize True  | 3944 | 389 |

---

## 8. Prize-Aware and M3+ Coexistence Matrix

Each cell shows the count of rows in that intersection, per lottery type.

**POWER_LOTTO:**

| | M3+ False | M3+ True |
|---|---|---|
| Prize False | 7931 | 0 |
| Prize True  | 681 | 388 |

**BIG_LOTTO:**

| | M3+ False | M3+ True |
|---|---|---|
| Prize False | 23384 | 0 |
| Prize True  | 269 | 487 |

**DAILY_539:**

| | M3+ False | M3+ True |
|---|---|---|
| Prize False | 30347 | 0 |
| Prize True  | 3944 | 389 |

---

## 9. Invariant Verification

| Lottery | processed=eligible | excl+elig=total | main_hit_sum | aux_sum | tier_sum | m3_sum | overlap_sum | any_win_matches | All Pass |
|---|---|---|---|---|---|---|---|---|---|
| POWER_LOTTO | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| BIG_LOTTO | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| DAILY_539 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**All invariants pass across all lottery types:** YES

---

## 10. Interpretation Limits

- POWER_LOTTO results apply only to the eligible subset (~24.93% of total rows). Results must not be generalized to the full POWER_LOTTO replay population.
- Descriptive observed rates do not demonstrate predictive improvement, statistical uplift, or strategy effectiveness.
- No random/null baseline was calculated. Observed rates cannot be interpreted as evidence of above-chance performance without a separate inferential analysis.
- Official prize tier rules are sourced from internal documentation (MANUAL_VERIFICATION_REQUIRED). Tier counts may differ from official payouts if the internal rules diverge from current official rules.
- Temporal stability of rates is unknown. Rates were computed over all available eligible history as a single aggregate.

---

## 11. Explicit Non-Actions

- **All structurally eligible historical rows were processed.**
- **POWER_LOTTO results apply only to rows with a stored prediction-time second-zone value.**
- **Missing POWER second-zone predictions were excluded and never filled.**
- **Output is aggregate only.**
- **No raw predicted or actual number arrays were exported.**
- **No strategy-level aggregation, comparison, or ranking was performed.**
- **No random/null baseline was calculated.**
- **No p-value, confidence interval, lift, or multiple-testing correction was calculated.**
- **Descriptive observed rates do not demonstrate predictive improvement.**
- **Existing replay.py, adapter, scorer, and M3+ semantics remain unchanged.**
- **DB access was read-only and no DB write occurred.**
- **No registry or production integration was added.**
- **No prize amount, EV, ROI, or betting advice was calculated.**
- **Official source status remains MANUAL_VERIFICATION_REQUIRED.**
- **P270C remains unauthorized.**
- **Temporal-window research and feature mining were not started.**

---

## 12. Recommended Next Task

HOLD / WAITING_FOR_USER_AUTHORIZATION.

Possible next directions (each requiring new explicit authorization):
1. Temporal-window stratified analysis (P271G or similar).
2. Strategy-level aggregation feasibility study.
3. P271G prize-amount integration if official prize table is machine-verified (requires P270C authorization and MANUAL_VERIFICATION_REQUIRED resolution).

---

## 13. Final Classification

**P271F_COMPLETE_WITH_POWER_ELIGIBLE_SUBSET_ONLY**

BIG_LOTTO and DAILY_539: all structurally eligible rows processed.
POWER_LOTTO: only valid stored-second-zone subset processed.
All invariants pass.

---

## Tests

**File:** `tests/test_p271f_prize_aware_full_history_descriptive_evaluation.py`

**Focused P271F result:** 81 passed, 0 skipped

**Combined P271A–F contract result:** 472 passed

**Full-repo suite:** NOT RUN
