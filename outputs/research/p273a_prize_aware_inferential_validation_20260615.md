# P273A Exact Distinct-Ticket Prize-Aware Inference

**Task:** `P273A_EXACT_DISTINCT_TICKET_PRIZE_AWARE_INFERENCE`
**Generated:** 2026-06-15
**Policy:** `primary_window_policy_v1_50_300_750`
**Branch:** `task/p273a-prize-aware-inferential-validation` (base `63452e7d589739b5ec3eb58035e7b8aff9014639`)
**Overall project classification:** `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING`
**Final classification:** `P273A_DISTINCT_TICKET_INFERENCE_COMPLETE_EDGE_SURVIVES_RESEARCH_ONLY`
**Canonical payload digest:** `5666e67c88e5f3b1233f2d6d5a5f86746c4f7605ae98bda3f2d59ec5aa0b2fb4`

> Retrospective research only. A descriptive observed rate is NOT a predictive edge. NULL and INSUFFICIENT_SUPPORT are valid, successful outcomes. 1500/all-history are reference-only and never drive a primary decision. SHORT-50 is a guardrail and can never independently trigger an EDGE or a GO candidate. No production apply, no prospective activation, no strategy reselection, no P273B. The production DB was never opened, queried, or written. Final inference uses the exact distinct-ticket without-replacement null; the independent approximation is rejected.

## 1. Primary question

Do any already-frozen strategies show a statistically credible prize-aware advantage over the governed random baseline (draw-level any-bet prize-aware success) under the owner-approved primary decision windows 50 (SHORT) / 300 (MID) / 750 (LONG)?

## 2. Window policy (owner-approved)

- **Primary decision windows:** 50 (SHORT), 300 (MID), 750 (LONG)
- **Reference-only (excluded from every primary decision):** 1500 draws; all-history frequency or distribution; any longer-horizon aggregate not in 50 / 300 / 750; the previous 100/500/1500 observed-counts artifact
- **Reference-only prohibited uses:** strategy_promotion, strategy_elimination, stability_pass_or_fail, go_recommendation, production_deployment_screening
- **Forbidden primary windows:** [100, 500, 1500]

## 3. Frozen setup (no outcome-based reselection)

- **Lotteries:** DAILY_539, BIG_LOTTO, POWER_LOTTO
- **Unit:** distinct_target_draw; **Outcome:** draw-level any-bet prize-aware success
- **Strategy universe:** 36 cells (`outputs/research/p267c_m3plus_strategy_revalidation_20260610.json`, sha256 `3769596df51f6eaa…`)
- **Primary observed counts:** `outputs/research/p273a_primary_window_observed_counts_20260615.json` (digest `65a4cc59f5ab64d6…`)
- **Distinct-ticket identities:** `outputs/research/p273a_distinct_ticket_identity_20260615.json` (digest `ad85e447dfc7db7a…`)

| Lottery | Endpoint | Condition |
|---|---|---|
| DAILY_539 | `D539_ANY_PRIZE_AWARE_WIN` | `hit_count >= 2` |
| BIG_LOTTO | `BIG_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count == 2 AND special_hit == 1)` |
| POWER_LOTTO | `POWER_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count >= 1 AND special_hit == 1)` |

## 4. Correction family and gates

- Family = (strategy x lottery) x primary window = 36 x 3 = **108** hypotheses (fixed; no post-outcome shrinkage)
- Family alpha = 0.05; Bonferroni per-test alpha = 0.000462962963; BH-FDR q = 0.1 (descriptive only)
- Minimum-support rule: support_draws >= 30 AND expected_successes >= 5.0

**Stability rule (owner pre-registered, frozen before outcomes):**

- 1. All three primary windows pass the minimum-support rule and are evaluable.
- 2. MID-300 absolute excess is strictly greater than 0.
- 3. LONG-750 absolute excess is strictly greater than 0.
- 4. SHORT-50 absolute excess is greater than or equal to 0.
- 5. At least one of MID-300 or LONG-750 has Bonferroni-corrected p-value <= 0.05 using the fixed family m=108.
- 6. SHORT-50 alone can never trigger correction-surviving edge or GO-candidate classification.
- 7. Any primary window that is significantly negative, insufficient-support, or unevaluable causes STABILITY_FAIL.
- 8. No window may be removed and no threshold/family may be changed after outcomes are observed.
- 9. The three nested windows represent cross-timescale directional consistency, not independent replications.
- 10. Passing stability creates at most a research GO candidate; it does not authorize production apply.

## 5. Exact distinct-ticket null

Final per-draw null: `q_N = 1 - C(T-W,N) / C(T,N)`. Actual `N` comes from each supported draw in the immutable identity artifact.

| Lottery | T total identities | W winning identities | W/T |
|---|---:|---:|---:|
| DAILY_539 | 575757 | 65621 | 0.113973429763 |
| BIG_LOTTO | 13983816 | 432824 | 0.030951780258 |
| POWER_LOTTO | 22085448 | 2602320 | 0.117829622474 |

Exact versus rejected independent approximation for every used N:

| Lottery | N | q_distinct | q_independent (rejected) | Abs diff | Rel diff |
|---|---:|---:|---:|---:|---:|
| DAILY_539 | 1 | 0.113973429763 | 0.113973429763 | 0 | 0 |
| DAILY_539 | 3 | 0.304431435743 | 0.304430969534 | 4.66209e-07 | 1.53141e-06 |
| DAILY_539 | 5 | 0.453949563750 | 0.453948343768 | 1.219982e-06 | 2.68749e-06 |
| BIG_LOTTO | 1 | 0.030951780258 | 0.030951780258 | 0 | 0 |
| BIG_LOTTO | 3 | 0.090010961105 | 0.090010954869 | 6.236e-09 | 6.9275e-08 |
| BIG_LOTTO | 4 | 0.118176747916 | 0.118176735831 | 1.2085e-08 | 1.02262e-07 |
| POWER_LOTTO | 1 | 0.117829622474 | 0.117829622474 | 0 | 0 |

## 6. Result summary

- **Overall project classification:** `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING`
- **Evaluable primary windows:** 86 / 108
- **Correction-surviving edge found:** True
- **Stability:** PASS=3, FAIL=33

Per-window decision counts:

| Decision | Count |
|---|---|
| `PRIZE_AWARE_DESCRIPTIVE_ONLY` | 17 |
| `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | 4 |
| `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | 22 |
| `PRIZE_AWARE_NULL` | 65 |

Overall group decision counts:

| Group decision | Count |
|---|---|
| `DESCRIPTIVE_ONLY` | 16 |
| `GO_CANDIDATE_RESEARCH_ONLY` | 3 |
| `INSUFFICIENT_SUPPORT` | 14 |
| `NULL` | 3 |

GO_CANDIDATE_RESEARCH_ONLY groups: **3** — DAILY_539/acb_markov_midfreq_3bet, DAILY_539/daily539_f4cold_3bet, DAILY_539/daily539_f4cold_5bet

## 7. Rejected provisional-result reconciliation

- Status: `PROVISIONAL_INDEPENDENT_NULL_REJECTED`
- Provisionally promoted groups audited: **3**

| Lottery | Strategy | Rejected stability | Exact stability | Transition |
|---|---|---|---|---|
| DAILY_539 | acb_markov_midfreq_3bet | STABILITY_PASS | STABILITY_PASS | `GO_CANDIDATE_RESEARCH_ONLY -> GO_CANDIDATE_RESEARCH_ONLY` |
| DAILY_539 | daily539_f4cold_3bet | STABILITY_PASS | STABILITY_PASS | `GO_CANDIDATE_RESEARCH_ONLY -> GO_CANDIDATE_RESEARCH_ONLY` |
| DAILY_539 | daily539_f4cold_5bet | STABILITY_PASS | STABILITY_PASS | `GO_CANDIDATE_RESEARCH_ONLY -> GO_CANDIDATE_RESEARCH_ONLY` |

### DAILY_539 / acb_markov_midfreq_3bet

| Window | Support | Observed | Distinct N dist | Old base | Exact base | Old exp | Exact exp | Old raw p | Exact raw p | Old Bonf p | Exact Bonf p | Old decision | Exact decision |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 50 | 50 | 18 | `{"3": 50}` | 0.304430969534 | 0.304431435743 | 15.22154848 | 15.22157179 | 0.23883256 | 0.23883482 | 1 | 1 | `PRIZE_AWARE_NULL` | `PRIZE_AWARE_NULL` |
| 300 | 300 | 120 | `{"3": 300}` | 0.304430969534 | 0.304431435743 | 91.32929086 | 91.32943072 | 0.00027352687 | 0.00027354514 | 0.029540902 | 0.029542875 | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` |
| 750 | 750 | 268 | `{"3": 750}` | 0.304430969534 | 0.304431435743 | 228.32322715 | 228.32357681 | 0.0010758193 | 0.0010759207 | 0.11618848 | 0.11619943 | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | `PRIZE_AWARE_DESCRIPTIVE_ONLY` |

### DAILY_539 / daily539_f4cold_3bet

| Window | Support | Observed | Distinct N dist | Old base | Exact base | Old exp | Exact exp | Old raw p | Exact raw p | Old Bonf p | Exact Bonf p | Old decision | Exact decision |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 50 | 50 | 23 | `{"3": 50}` | 0.304430969534 | 0.304431435743 | 15.22154848 | 15.22157179 | 0.014728437 | 0.014728715 | 1 | 1 | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | `PRIZE_AWARE_DESCRIPTIVE_ONLY` |
| 300 | 300 | 101 | `{"3": 300}` | 0.304430969534 | 0.304431435743 | 91.32929086 | 91.32943072 | 0.12543614 | 0.1254398 | 1 | 1 | `PRIZE_AWARE_NULL` | `PRIZE_AWARE_NULL` |
| 750 | 750 | 275 | `{"3": 750}` | 0.304430969534 | 0.304431435743 | 228.32322715 | 228.32357681 | 0.00015461141 | 0.00015462822 | 0.016698032 | 0.016699848 | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` |

### DAILY_539 / daily539_f4cold_5bet

| Window | Support | Observed | Distinct N dist | Old base | Exact base | Old exp | Exact exp | Old raw p | Exact raw p | Old Bonf p | Exact Bonf p | Old decision | Exact decision |
|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 50 | 50 | 35 | `{"5": 50}` | 0.453948343768 | 0.453949563750 | 22.69741719 | 22.69747819 | 0.00038120209 | 0.00038122605 | 0.041169825 | 0.041172413 | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | `PRIZE_AWARE_DESCRIPTIVE_ONLY` |
| 300 | 300 | 170 | `{"5": 300}` | 0.453948343768 | 0.453949563750 | 136.18450313 | 136.18486912 | 5.8202894e-05 | 5.8213025e-05 | 0.0062859125 | 0.0062870067 | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` |
| 750 | 750 | 425 | `{"5": 750}` | 0.453948343768 | 0.453949563750 | 340.46125783 | 340.46217281 | 3.94e-10 | 3.94e-10 | 4.2559e-08 | 4.2577e-08 | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` |

## 8. Per-cell primary-window inference (all 108 windows)

Columns: support / observed / distinct-ticket distribution / obs-rate / exact baseline-rate / excess(pp) / raw-p(upper) / Bonferroni-p / stat-status / decision. SHORT rows are guardrail-only.

| Lottery | Strategy | Win | Lbl | Supp | Obs | Distinct N | ObsRate | Exact Base | Excess(pp) | RawP | BonfP | Status | Decision | Stability |
|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|---|
| DAILY_539 | 539_3bet_orthogonal | 50 | SHORT | 50 | 8 | `{"1": 50}` | 0.1600 | 0.1140 | +4.6027 | 0.205 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | 539_3bet_orthogonal | 300 | MID | 300 | 39 | `{"1": 300}` | 0.1300 | 0.1140 | +1.6027 | 0.2142 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | 539_3bet_orthogonal | 750 | LONG | 750 | 93 | `{"1": 750}` | 0.1240 | 0.1140 | +1.0027 | 0.2084 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_1bet | 50 | SHORT | 50 | 8 | `{"1": 50}` | 0.1600 | 0.1140 | +4.6027 | 0.205 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_1bet | 300 | MID | 300 | 39 | `{"1": 300}` | 0.1300 | 0.1140 | +1.6027 | 0.2142 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_1bet | 750 | LONG | 750 | 93 | `{"1": 750}` | 0.1240 | 0.1140 | +1.0027 | 0.2084 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_markov_midfreq | 50 | SHORT | 50 | 0 | `{"1": 50}` | 0.0000 | 0.1140 | -11.3973 | 1 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_markov_midfreq | 300 | MID | 300 | 32 | `{"1": 300}` | 0.1067 | 0.1140 | -0.7307 | 0.6812 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_markov_midfreq | 750 | LONG | 750 | 74 | `{"1": 750}` | 0.0987 | 0.1140 | -1.5307 | 0.9179 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_markov_midfreq_3bet | 50 | SHORT | 50 | 18 | `{"3": 50}` | 0.3600 | 0.3044 | +5.5569 | 0.2388 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_PASS |
| DAILY_539 | acb_markov_midfreq_3bet | 300 | MID | 300 | 120 | `{"3": 300}` | 0.4000 | 0.3044 | +9.5569 | 0.0002735 | 0.02954 | SIGNIFICANT_POSITIVE_CORRECTED | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | STABILITY_PASS |
| DAILY_539 | acb_markov_midfreq_3bet | 750 | LONG | 750 | 268 | `{"3": 750}` | 0.3573 | 0.3044 | +5.2902 | 0.001076 | 0.1162 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_PASS |
| DAILY_539 | acb_single_539 | 50 | SHORT | 50 | 8 | `{"1": 50}` | 0.1600 | 0.1140 | +4.6027 | 0.205 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_single_539 | 300 | MID | 300 | 39 | `{"1": 300}` | 0.1300 | 0.1140 | +1.6027 | 0.2142 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | acb_single_539 | 750 | LONG | 750 | 93 | `{"1": 750}` | 0.1240 | 0.1140 | +1.0027 | 0.2084 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | daily539_f4cold | 50 | SHORT | 50 | 11 | `{"1": 50}` | 0.2200 | 0.1140 | +10.6027 | 0.0232 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | daily539_f4cold | 300 | MID | 300 | 44 | `{"1": 300}` | 0.1467 | 0.1140 | +3.2693 | 0.04913 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | daily539_f4cold | 750 | LONG | 750 | 105 | `{"1": 750}` | 0.1400 | 0.1140 | +2.6027 | 0.01637 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | daily539_f4cold_3bet | 50 | SHORT | 50 | 23 | `{"3": 50}` | 0.4600 | 0.3044 | +15.5569 | 0.01473 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_PASS |
| DAILY_539 | daily539_f4cold_3bet | 300 | MID | 300 | 101 | `{"3": 300}` | 0.3367 | 0.3044 | +3.2235 | 0.1254 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_PASS |
| DAILY_539 | daily539_f4cold_3bet | 750 | LONG | 750 | 275 | `{"3": 750}` | 0.3667 | 0.3044 | +6.2235 | 0.0001546 | 0.0167 | SIGNIFICANT_POSITIVE_CORRECTED | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | STABILITY_PASS |
| DAILY_539 | daily539_f4cold_5bet | 50 | SHORT | 50 | 35 | `{"5": 50}` | 0.7000 | 0.4539 | +24.6050 | 0.0003812 | 0.04117 | SIGNIFICANT_POSITIVE_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_PASS |
| DAILY_539 | daily539_f4cold_5bet | 300 | MID | 300 | 170 | `{"5": 300}` | 0.5667 | 0.4539 | +11.2717 | 5.821e-05 | 0.006287 | SIGNIFICANT_POSITIVE_CORRECTED | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | STABILITY_PASS |
| DAILY_539 | daily539_f4cold_5bet | 750 | LONG | 750 | 425 | `{"5": 750}` | 0.5667 | 0.4539 | +11.2717 | 3.94e-10 | 4.258e-08 | SIGNIFICANT_POSITIVE_CORRECTED | `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING` | STABILITY_PASS |
| DAILY_539 | daily539_markov_cold | 50 | SHORT | 50 | 4 | `{"1": 50}` | 0.0800 | 0.1140 | -3.3973 | 0.8364 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | daily539_markov_cold | 300 | MID | 300 | 38 | `{"1": 300}` | 0.1267 | 0.1140 | +1.2693 | 0.269 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | daily539_markov_cold | 750 | LONG | 750 | 81 | `{"1": 750}` | 0.1080 | 0.1140 | -0.5973 | 0.713 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | markov_1bet_539 | 50 | SHORT | 50 | 4 | `{"1": 50}` | 0.0800 | 0.1140 | -3.3973 | 0.8364 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | markov_1bet_539 | 300 | MID | 300 | 38 | `{"1": 300}` | 0.1267 | 0.1140 | +1.2693 | 0.269 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | markov_1bet_539 | 750 | LONG | 750 | 81 | `{"1": 750}` | 0.1080 | 0.1140 | -0.5973 | 0.713 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | midfreq_acb_2bet | 50 | SHORT | 50 | 6 | `{"1": 50}` | 0.1200 | 0.1140 | +0.6027 | 0.5119 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | midfreq_acb_2bet | 300 | MID | 300 | 48 | `{"1": 300}` | 0.1600 | 0.1140 | +4.6027 | 0.01011 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | midfreq_acb_2bet | 750 | LONG | 750 | 101 | `{"1": 750}` | 0.1347 | 0.1140 | +2.0693 | 0.04464 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | midfreq_fourier_2bet | 50 | SHORT | 50 | 6 | `{"1": 50}` | 0.1200 | 0.1140 | +0.6027 | 0.5119 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | midfreq_fourier_2bet | 300 | MID | 300 | 48 | `{"1": 300}` | 0.1600 | 0.1140 | +4.6027 | 0.01011 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | midfreq_fourier_2bet | 750 | LONG | 750 | 101 | `{"1": 750}` | 0.1347 | 0.1140 | +2.0693 | 0.04464 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 50 | SHORT | 50 | 11 | `{"1": 50}` | 0.2200 | 0.1140 | +10.6027 | 0.0232 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 300 | MID | 300 | 45 | `{"1": 300}` | 0.1500 | 0.1140 | +3.6027 | 0.03422 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 750 | LONG | 750 | 106 | `{"1": 750}` | 0.1413 | 0.1140 | +2.7360 | 0.01244 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 50 | SHORT | 50 | 11 | `{"1": 50}` | 0.2200 | 0.1140 | +10.6027 | 0.0232 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 300 | MID | 300 | 45 | `{"1": 300}` | 0.1500 | 0.1140 | +3.6027 | 0.03422 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 750 | LONG | 750 | 106 | `{"1": 750}` | 0.1413 | 0.1140 | +2.7360 | 0.01244 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| DAILY_539 | zone_gap_3bet_539 | 50 | SHORT | 50 | 8 | `{"1": 50}` | 0.1600 | 0.1140 | +4.6027 | 0.205 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | zone_gap_3bet_539 | 300 | MID | 300 | 31 | `{"1": 300}` | 0.1033 | 0.1140 | -1.0640 | 0.7447 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| DAILY_539 | zone_gap_3bet_539 | 750 | LONG | 750 | 76 | `{"1": 750}` | 0.1013 | 0.1140 | -1.2640 | 0.8754 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 50 | SHORT | 50 | 4 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 300 | MID | 300 | 10 | `{"1": 300}` | 0.0333 | 0.0310 | +0.2382 | 0.4507 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 750 | LONG | 750 | 25 | `{"1": 750}` | 0.0333 | 0.0310 | +0.2382 | 0.3815 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_deviation_2bet | 50 | SHORT | 50 | 2 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_deviation_2bet | 300 | MID | 300 | 10 | `{"1": 300}` | 0.0333 | 0.0310 | +0.2382 | 0.4507 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_deviation_2bet | 750 | LONG | 750 | 32 | `{"1": 750}` | 0.0427 | 0.0310 | +1.1715 | 0.04548 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_DESCRIPTIVE_ONLY` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_echo_aware_3bet | 50 | SHORT | 50 | 4 | `{"3": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_echo_aware_3bet | 300 | MID | 300 | 33 | `{"3": 300}` | 0.1100 | 0.0900 | +1.9989 | 0.1347 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_echo_aware_3bet | 750 | LONG | 750 | 75 | `{"3": 750}` | 0.1000 | 0.0900 | +0.9989 | 0.1852 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_triple_strike | 50 | SHORT | 50 | 4 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_triple_strike | 300 | MID | 300 | 10 | `{"1": 300}` | 0.0333 | 0.0310 | +0.2382 | 0.4507 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_triple_strike | 750 | LONG | 750 | 22 | `{"1": 750}` | 0.0293 | 0.0310 | -0.1618 | 0.6301 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 50 | SHORT | 50 | 5 | `{"4": 50}` | 0.1000 | 0.1182 | -1.8177 | 0.7191 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 300 | MID | 300 | 38 | `{"4": 300}` | 0.1267 | 0.1182 | +0.8490 | 0.3499 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 750 | LONG | 750 | 99 | `{"4": 750}` | 0.1320 | 0.1182 | +1.3823 | 0.1328 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | cold_complement_biglotto | 50 | SHORT | 50 | 2 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | cold_complement_biglotto | 300 | MID | 300 | 10 | `{"1": 300}` | 0.0333 | 0.0310 | +0.2382 | 0.4507 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | cold_complement_biglotto | 750 | LONG | 750 | 21 | `{"1": 750}` | 0.0280 | 0.0310 | -0.2952 | 0.7087 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | coldpool15_biglotto | 50 | SHORT | 50 | 2 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | coldpool15_biglotto | 300 | MID | 300 | 10 | `{"1": 300}` | 0.0333 | 0.0310 | +0.2382 | 0.4507 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | coldpool15_biglotto | 750 | LONG | 750 | 21 | `{"1": 750}` | 0.0280 | 0.0310 | -0.2952 | 0.7087 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | fourier30_markov30_biglotto | 50 | SHORT | 50 | 1 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | fourier30_markov30_biglotto | 300 | MID | 300 | 6 | `{"1": 300}` | 0.0200 | 0.0310 | -1.0952 | 0.9041 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | fourier30_markov30_biglotto | 750 | LONG | 750 | 19 | `{"1": 750}` | 0.0253 | 0.0310 | -0.5618 | 0.8401 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | markov_2bet_biglotto | 50 | SHORT | 50 | 1 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | markov_2bet_biglotto | 300 | MID | 300 | 9 | `{"1": 300}` | 0.0300 | 0.0310 | -0.0952 | 0.5839 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | markov_2bet_biglotto | 750 | LONG | 750 | 18 | `{"1": 750}` | 0.0240 | 0.0310 | -0.6952 | 0.8894 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | markov_single_biglotto | 50 | SHORT | 50 | 1 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | markov_single_biglotto | 300 | MID | 300 | 9 | `{"1": 300}` | 0.0300 | 0.0310 | -0.0952 | 0.5839 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | markov_single_biglotto | 750 | LONG | 750 | 18 | `{"1": 750}` | 0.0240 | 0.0310 | -0.6952 | 0.8894 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | ts3_regime_3bet | 50 | SHORT | 50 | 4 | `{"1": 50}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| BIG_LOTTO | ts3_regime_3bet | 300 | MID | 300 | 10 | `{"1": 300}` | 0.0333 | 0.0310 | +0.2382 | 0.4507 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| BIG_LOTTO | ts3_regime_3bet | 750 | LONG | 750 | 22 | `{"1": 750}` | 0.0293 | 0.0310 | -0.1618 | 0.6301 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | cold_complement_2bet | 50 | SHORT | 50 | 3 | `{"1": 50}` | 0.0600 | 0.1178 | -5.7830 | 0.944 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | cold_complement_2bet | 300 | MID | 300 | 36 | `{"1": 300}` | 0.1200 | 0.1178 | +0.2170 | 0.4801 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | cold_complement_2bet | 750 | LONG | 750 | 86 | `{"1": 750}` | 0.1147 | 0.1178 | -0.3163 | 0.6226 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | fourier30_markov30_2bet | 50 | SHORT | 49 | 4 | `{"1": 49}` | 0.0816 | 0.1178 | -3.6197 | 0.8444 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | fourier30_markov30_2bet | 300 | MID | 299 | 35 | `{"1": 299}` | 0.1171 | 0.1178 | -0.0773 | 0.5432 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | fourier30_markov30_2bet | 750 | LONG | 749 | 84 | `{"1": 749}` | 0.1121 | 0.1178 | -0.5680 | 0.7014 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | fourier_rhythm_3bet | 50 | SHORT | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | fourier_rhythm_3bet | 300 | MID | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | fourier_rhythm_3bet | 750 | LONG | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | midfreq_fourier_2bet | 50 | SHORT | 50 | 5 | `{"1": 50}` | 0.1000 | 0.1178 | -1.7830 | 0.7166 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | midfreq_fourier_2bet | 300 | MID | 300 | 30 | `{"1": 300}` | 0.1000 | 0.1178 | -1.7830 | 0.8533 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | midfreq_fourier_2bet | 750 | LONG | 750 | 84 | `{"1": 750}` | 0.1120 | 0.1178 | -0.5830 | 0.706 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 50 | SHORT | 50 | 7 | `{"1": 50}` | 0.1400 | 0.1178 | +2.2170 | 0.3749 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 300 | MID | 300 | 34 | `{"1": 300}` | 0.1133 | 0.1178 | -0.4496 | 0.6219 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 750 | LONG | 750 | 101 | `{"1": 750}` | 0.1347 | 0.1178 | +1.6837 | 0.08662 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | power_fourier_rhythm_2bet | 50 | SHORT | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | power_fourier_rhythm_2bet | 300 | MID | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | power_fourier_rhythm_2bet | 750 | LONG | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | power_orthogonal_5bet | 50 | SHORT | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | power_orthogonal_5bet | 300 | MID | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | power_orthogonal_5bet | 750 | LONG | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | power_precision_3bet | 50 | SHORT | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | power_precision_3bet | 300 | MID | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | power_precision_3bet | 750 | LONG | 0 | 0 | `{}` | — | — | — | — | — | INSUFFICIENT_SUPPORT | `PRIZE_AWARE_INSUFFICIENT_SUPPORT` | STABILITY_FAIL |
| POWER_LOTTO | pp3_freqort_4bet | 50 | SHORT | 50 | 6 | `{"1": 50}` | 0.1200 | 0.1178 | +0.2170 | 0.5459 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | pp3_freqort_4bet | 300 | MID | 300 | 28 | `{"1": 300}` | 0.0933 | 0.1178 | -2.4496 | 0.9238 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | pp3_freqort_4bet | 750 | LONG | 750 | 95 | `{"1": 750}` | 0.1267 | 0.1178 | +0.8837 | 0.2415 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | zonal_entropy_2bet | 50 | SHORT | 50 | 6 | `{"1": 50}` | 0.1200 | 0.1178 | +0.2170 | 0.5459 | 1 | POSITIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | zonal_entropy_2bet | 300 | MID | 300 | 35 | `{"1": 300}` | 0.1167 | 0.1178 | -0.1163 | 0.5515 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |
| POWER_LOTTO | zonal_entropy_2bet | 750 | LONG | 750 | 80 | `{"1": 750}` | 0.1067 | 0.1178 | -1.1163 | 0.8426 | 1 | NEGATIVE_NOT_CORRECTED | `PRIZE_AWARE_NULL` | STABILITY_FAIL |

## 9. Disclaimers

- Retrospective research only.
- Primary observed counts come from the immutable 50/300/750 observed-counts artifact.
- Ticket multiplicities come only from the immutable distinct-ticket identity artifact.
- The exact distinct-ticket without-replacement null is used for final inference.
- The independent-with-replacement approximation is rejected for final inference.
- 1500-draw and all-history horizons are REFERENCE-ONLY and never drive a primary decision.
- The production DB was not opened, queried, or written.
- A descriptive observed rate is NOT a predictive edge.
- Bonferroni family is fixed at m=108 (36 cells x 3 primary windows); no post-outcome shrinkage.
- BH-FDR is descriptive only and cannot promote an edge.
- The three nested windows are cross-timescale consistency checks, not independent replications.
- SHORT-50 is a recent-direction guardrail and can never independently trigger an EDGE or a GO candidate.
- NULL and INSUFFICIENT_SUPPORT are valid, successful outcomes.
- No strategy reselection was performed.
- No prospective activation is authorized.
- No production apply is authorized; GO_CANDIDATE_RESEARCH_ONLY is not deployment authorization.
- P273B (replay feature mining) is NOT started.
