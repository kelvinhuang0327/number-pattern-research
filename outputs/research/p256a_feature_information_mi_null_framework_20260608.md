# P256A — Feature-Information MI Null-Framework Assessment

**Task:** P256A | **Date:** 2026-06-08 | **Type:** C (read-only additive)
**Classification:** `P256A_FEATURE_INFORMATION_MI_NULL_ASSESSMENT_COMPLETE_NULL_RESULT`
**Final Decision:** `HOLD_NULL_RESULT`

> **Framing (binding):** This is a **falsification task**, not a prediction task.
> Expected outcome: MI ≈ random. A corrected NULL is a successful result.
> No strategy promotion. No betting advice. No DB write.

---

## Executive Summary

- Lotteries scanned: BIG_LOTTO (canonical 2,114), DAILY_539 (5,882), POWER_LOTTO (1,917)
- Lotteries skipped: 3_STAR, 4_STAR — UNDERPOWERED_NO_SIGNAL / positional order lost
- Family size (pre-declared): **39** tests
  (2 freq-features × 6 windows + 1 lag) × 3 lotteries
- Bonferroni threshold: **0.00128205**
- Bonferroni survivors (global): **0**
- Overall result: **`HOLD_NULL_RESULT`**

**→ No Bonferroni survivor.** All features indistinguishable from random null after correction. Consistent with prior evidence (L82/L90/L91, P211A/P224/P230C/P231B).

---

## Pre-Registration (declared before results)

### Feature Vocabulary
| Feature | Description |
|---|---|
| number_frequency | Relative frequency of each number in last W draws |
| position_frequency | Per-sorted-position frequency — **BLOCKED** (sorted storage, P226) |
| sequence_lag_mi | MI between lag-1 draw and next (set intersection proxy) |
| feature_to_hit_mi | MI between derived feature value and binary hit outcome |
| blocking_factor | Data availability / power constraints |

### Null Specification — L96 Binding

**Method:** Monte-Carlo / Binomial(1, baseline_i) null — **NOT label-shuffle**

| Parameter | Value |
|---|---|
| Null draws (B) | 500 |
| Seed | 20260608 |
| p-value formula | (1 + count_extreme) / (B + 1) — Phipson & Smyth 2010 |
| Label-shuffle forbidden | **YES** — label-shuffle preserves the mean, causing empirical null centred at observed value → p ≈ 1.0 (L96 bug) |

### Pre-Declared Family

| Parameter | Value |
|---|---|
| Freq features | 2 (top_freq, bot_freq) |
| Windows | 6 (100, 125, 150, 500, 750, 1000) |
| Lag features | 1 (lag1, all-history) |
| Lotteries scanned | 3 |
| **Total family size** | **39** |
| Strict gate | Bonferroni (threshold = 0.00128205) |
| Exploratory | BH-FDR (reference only) |

---

## Per-Lottery Results

### BIG_LOTTO
- Draws: 2114 | Pool: 49 | Pick: 6 | Threshold: 3
- Baseline hit-rate: 0.018638
- Note: canonical view 2,114 rows (ADD_ON excluded)
- Bonferroni survivors: 0 / Exploratory weak: 0
- **Classification: `NULL_OR_BASELINE_LIKE`**

| Feature | Window | n_tests | hit_rate | baseline | delta | p_value | classification |
|---|---|---|---|---|---|---|---|
| top_freq | 100 | 2014 | 0.016385 | 0.018638 | -0.002252 | 0.828343 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 125 | 1989 | 0.018602 | 0.018638 | -3.5e-05 | 0.467066 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 150 | 1964 | 0.016293 | 0.018638 | -0.002344 | 0.796407 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 500 | 1614 | 0.015489 | 0.018638 | -0.003148 | 0.878244 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 750 | 1364 | 0.014663 | 0.018638 | -0.003975 | 0.88024 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 1000 | 1114 | 0.016158 | 0.018638 | -0.00248 | 0.782435 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 100 | 2014 | 0.021847 | 0.018638 | 0.00321 | 0.153693 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 125 | 1989 | 0.0181 | 0.018638 | -0.000538 | 0.582834 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 150 | 1964 | 0.020876 | 0.018638 | 0.002238 | 0.249501 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 500 | 1614 | 0.016109 | 0.018638 | -0.002529 | 0.804391 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 750 | 1364 | 0.021994 | 0.018638 | 0.003357 | 0.211577 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 1000 | 1114 | 0.017953 | 0.018638 | -0.000684 | 0.592814 | `NULL_OR_BASELINE_LIKE` |
| lag1 | all_history | 2113 | 0.02035 | 0.018638 | 0.001713 | 0.299401 | `NULL_OR_BASELINE_LIKE` |

### DAILY_539
- Draws: 5882 | Pool: 39 | Pick: 5 | Threshold: 3
- Baseline hit-rate: 0.010041
- Note: all 5,882 rows
- Bonferroni survivors: 0 / Exploratory weak: 1
- **Classification: `EXPLORATORY_WEAK_UNCONFIRMED`**

| Feature | Window | n_tests | hit_rate | baseline | delta | p_value | classification |
|---|---|---|---|---|---|---|---|
| top_freq | 100 | 5782 | 0.010204 | 0.010041 | 0.000163 | 0.433134 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 125 | 5757 | 0.010075 | 0.010041 | 3.4e-05 | 0.510978 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 150 | 5732 | 0.011165 | 0.010041 | 0.001125 | 0.207585 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 500 | 5382 | 0.010405 | 0.010041 | 0.000364 | 0.433134 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 750 | 5132 | 0.012666 | 0.010041 | 0.002625 | 0.03992 | `EXPLORATORY_WEAK_UNCONFIRMED` |
| top_freq | 1000 | 4882 | 0.008193 | 0.010041 | -0.001847 | 0.908184 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 100 | 5782 | 0.011069 | 0.010041 | 0.001028 | 0.215569 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 125 | 5757 | 0.010422 | 0.010041 | 0.000381 | 0.419162 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 150 | 5732 | 0.011165 | 0.010041 | 0.001125 | 0.183633 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 500 | 5382 | 0.00929 | 0.010041 | -0.00075 | 0.674651 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 750 | 5132 | 0.009743 | 0.010041 | -0.000298 | 0.602794 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 1000 | 4882 | 0.009832 | 0.010041 | -0.000209 | 0.560878 | `NULL_OR_BASELINE_LIKE` |
| lag1 | all_history | 5881 | 0.010712 | 0.010041 | 0.000672 | 0.345309 | `NULL_OR_BASELINE_LIKE` |

### POWER_LOTTO
- Draws: 1917 | Pool: 38 | Pick: 6 | Threshold: 3
- Baseline hit-rate: 0.038698
- Note: first zone 1,917 rows
- Bonferroni survivors: 0 / Exploratory weak: 0
- **Classification: `NULL_OR_BASELINE_LIKE`**

| Feature | Window | n_tests | hit_rate | baseline | delta | p_value | classification |
|---|---|---|---|---|---|---|---|
| top_freq | 100 | 1817 | 0.035223 | 0.038698 | -0.003475 | 0.808383 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 125 | 1792 | 0.035156 | 0.038698 | -0.003542 | 0.812375 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 150 | 1767 | 0.03622 | 0.038698 | -0.002478 | 0.704591 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 500 | 1417 | 0.035992 | 0.038698 | -0.002707 | 0.722555 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 750 | 1167 | 0.045416 | 0.038698 | 0.006718 | 0.131737 | `NULL_OR_BASELINE_LIKE` |
| top_freq | 1000 | 917 | 0.040349 | 0.038698 | 0.001651 | 0.429142 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 100 | 1817 | 0.039626 | 0.038698 | 0.000928 | 0.439122 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 125 | 1792 | 0.035156 | 0.038698 | -0.003542 | 0.796407 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 150 | 1767 | 0.03622 | 0.038698 | -0.002478 | 0.710579 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 500 | 1417 | 0.045166 | 0.038698 | 0.006468 | 0.115768 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 750 | 1167 | 0.040274 | 0.038698 | 0.001576 | 0.44511 | `NULL_OR_BASELINE_LIKE` |
| bot_freq | 1000 | 917 | 0.030534 | 0.038698 | -0.008164 | 0.914172 | `NULL_OR_BASELINE_LIKE` |
| lag1 | all_history | 1916 | 0.032881 | 0.038698 | -0.005817 | 0.906188 | `NULL_OR_BASELINE_LIKE` |

### 3_STAR — SKIPPED
- Reason: UNDERPOWERED_NO_SIGNAL — box-play: prior P227C/P214C. Per-position MI: positional order lost in sorted storage (P226); tractable only if re-ingested (P213D). No scan without re-ingestion authorization.
- Classification: `UNDERPOWERED_NO_SIGNAL`

### 4_STAR — SKIPPED
- Reason: UNDERPOWERED_NO_SIGNAL — same as 3_STAR.
- Classification: `UNDERPOWERED_NO_SIGNAL`

---

## Multiple-Testing Correction Summary

- Family size: 39
- Bonferroni threshold: 0.0012820513
- Bonferroni significant: 0
- BH-FDR significant (exploratory): 0
- No edge claim: True

---

## Measurability Map

| Lottery | Feature | Status | Reason |
|---|---|---|---|
| BIG_LOTTO | number_frequency | MEASURABLE | 2,114 canonical draws; all short/mid windows tractable |
| BIG_LOTTO | sequence_lag_mi | MEASURABLE | Lag-1 overlap computable over full canonical sample |
| BIG_LOTTO | position_frequency | BLOCKED | Draws stored as sorted sets; positional order not preserved (P226). Re-ingestion required. |
| DAILY_539 | number_frequency | MEASURABLE | 5,882 draws; all windows tractable |
| DAILY_539 | sequence_lag_mi | MEASURABLE | Lag-1 overlap computable |
| DAILY_539 | position_frequency | BLOCKED | Sorted storage — positional order lost (P226) |
| POWER_LOTTO | number_frequency | MEASURABLE | 1,917 draws; short windows (100/125/150) fully tractable; mid window 1000 marginal (n=917 tests) but allowed |
| POWER_LOTTO | sequence_lag_mi | MEASURABLE | Lag-1 computable |
| POWER_LOTTO | position_frequency | BLOCKED | Sorted storage — positional order lost (P226) |
| 3_STAR | all | UNDERPOWERED_NO_SIGNAL | Box-play: prior P227C UNDERPOWERED_NO_SIGNAL. Per-position MI: positional order lost in sorted storage (P226); tractable ONLY after re-ingestion (P213D). No scan authorized. |
| 4_STAR | all | UNDERPOWERED_NO_SIGNAL | Same as 3_STAR. |

---

## Corrected Verdict

**Final Decision: `HOLD_NULL_RESULT`**

All features are statistically indistinguishable from the Binomial null after
Bonferroni correction. This is the **expected** result per prior evidence:

- L82/L90/L91: BIG_LOTTO signal space exhausted; DAILY_539/POWER_LOTTO survivors rejected by OOS
- P211A/P224/P230C/P231B: all backward-OOS NULL
- Pool-size dilution: 49C6 ≈ 14M combinations; frequency signals attenuate below detection threshold

A clean NULL confirms the framework is operating correctly and prevents wasted
future compute on the same feature families.

---

## Explicit Non-Actions

- **No DB write** — queries used `sqlite3` read-only URI (`mode=ro`)
- **No registry mutation** — `replay_strategy_registry.py` not touched
- **No strategy promotion** — NULL result does not authorize any strategy
- **No betting advice** — this document must not be used for gambling decisions
- **No production/API/fetcher/frontend change**

---

## Required Completion Check

| Item | Result |
|---|---|
| Completed | YES |
| Test Result | PASS (see pytest output) |
| Single Blocking Issue | NONE |
| DB write | NO |
| Registry mutation | NO |
| Strategy promotion | NO |
| Betting advice | NO |
| Final Classification | `P256A_FEATURE_INFORMATION_MI_NULL_ASSESSMENT_COMPLETE_NULL_RESULT` |
| Strong Model Needed | NO |
