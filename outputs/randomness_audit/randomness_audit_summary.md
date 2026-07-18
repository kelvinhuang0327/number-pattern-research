# Lottery Randomness Audit Report — Current Executable Path

**Current executable audit timestamp (UTC):** 2026-07-18T10:35:40Z
**Task:** `P691_RANDOMNESS_EXISTING_LOGIC_TRANSFER_R1`
**Type:** existing-logic migration; not historical 44-test reproduction
**Current scope:** canonical BIG_LOTTO only; P246K controls statistical behavior
**Current classification:** `P246K_CANONICAL_BIG_LOTTO_RANDOMNESS_AUDIT_GREEN_RANDOM_COMPATIBLE`
**New statistical procedure introduced:** NO
**Database write performed:** NO

## Current Executable Audit Result

| Existing P246K check | Result |
| --- | --- |
| Draw-sum KS | GREEN |
| Number-frequency chi-square | GREEN |
| Runs test | GREEN |
| Ljung-Box lag 10 | GREEN |
| Shannon entropy | GREEN |

P246K summary: **5/5 GREEN**, **0 YELLOW**. This is a randomness diagnostic, not a prediction, strategy, or betting recommendation.

## Canonical Input Provenance

- Logical DB identity: `canonical_big_lotto_store`
- SQLite mode: URI `mode=ro&immutable=1&cache=private`; `PRAGMA query_only=ON` verified; WAL empty/absent precondition enforced
- Selected population: `BIG_LOTTO/CANONICAL_MAIN_DRAW`
- Canonical rows: `2125`
- Raw BIG_LOTTO rows observed: `3150`
- P246K compatibility note: its unchanged nested payload retains a historical 22,238-row raw-access sentence and legacy aggregate exclusion field name; the SQL-derived counts above are the current provenance values.
- Boundary: `96000001` through `115000070`
- Selected-row stream SHA-256: `7d48306f31746ec3ea8976b4d0b88f2577decd52191391ee5c059f2fd4588a09`
- P246K semantic output SHA-256: `48f72f61764e09de20702a853d124930eb3275ce49eb7e9b4b9e26e84f5d9dd1`
- Exact canonical SQL:

```sql
SELECT draw, date, numbers, special
FROM draws_big_lotto_canonical_main
ORDER BY CAST(draw AS INTEGER) DESC, draw DESC
```

## Source Implementations

- `P246K` `analysis/p246k_canonical_big_lotto_nist_reaudit.py::run_canonical_nist_reaudit` SHA-256 `3ddd1453ae562c0ac6bec1ada0bc6c2ca3339012ec8a2a26dc233bc1fac83157` — unchanged_through_read_only_population_adapter
- `P238B` `scripts/p238b_nist_randomness_audit_artifact_build.py::_connect_ro` SHA-256 `6eee50f61101b016737863eb426da6a0e893bc2d3f38387aa232ac1b4b86dcd8` — unchanged

## Cadence

The next real executable audit is due at **14 calendar days** or **50 new canonical BIG_LOTTO draws**, whichever occurs first. Timestamp-only re-attestation is non-gating and resets neither trigger.
- Executable anchor timestamp: `2026-07-18T10:35:40Z`
- Executable anchor canonical rows: `2125`
- Cadence policy identity: `whichever_occurs_first`
- Every future or incompatible executable anchor fails closed.

## Historical 44-Test Evidence

The historical 44-test values below are immutable legacy evidence. Their producing implementation is not committed, so they are not reproducible from repository source and are not claimed equivalent to the current P246K executable audit.

<!-- P691_LEGACY_44_TEST_SUMMARY_BEGIN -->
# Lottery Randomness Audit Report

**Run timestamp:** 2026-06-02T06:57:02.982982
**Re-attestation timestamp:** 2026-06-30T13:42:02.321987
**Simulations:** 2,000 (seed=42)
**Alpha:** 0.05
**Total confirmatory tests:** 44
**Bonferroni threshold:** 1.1364e-03

---
### Re-attestation Disclosure (P275E-A, 2026-06-16)

This document is a **human re-attestation** of unchanged committed statistical evidence.
It is **not** a new statistical analysis or a new audit run.

| Field | Value |
|---|---|
| Original audit run | 2026-06-02T06:57:02.982982 (Run timestamp above) |
| Re-attestation performed | 2026-06-30T13:42:02.321987 (Re-attestation timestamp above) |
| Reanalysis performed | **NO** — statistical values were not recomputed |
| New draws analyzed | **NO** — data through 2026-04-29 only |
| Audit script status | `scripts/randomness_audit.py` is absent from this repository (never existed) |
| Re-attestation basis | Human review confirmed the committed statistical evidence remains the current committed state. Precedent: P203 commit `d119ea6`. |

**Limitation:** This re-attestation does not establish that the prior verdict
(`WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION`) holds for draws added after
the original audit date (through 2026-04-29). Draws ingested since that date have
not been statistically tested.

---
## FINAL VERDICT

**🔶 WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION**

> Strategy implication: NO_EXPLOITABLE_EDGE_FROM_DRAW_PROCESS

---
## Phase 1 — Data Validation

| Game | Rows | Date Min | Date Max | Dup IDs | Missing | Dup Draws | OOR Balls | Status |
|------|------|----------|----------|---------|---------|-----------|-----------|--------|
| power_lotto | 1906 | 2008-01-24 | 2026-04-27 | 0 | 0 | 0 | 0 | WARN |
| big_lotto | 2130 | 2007-01-02 | 2026-04-28 | 0 | 0 | 0 | 0 | WARN |
| daily_539 | 5849 | 2007-01-01 | 2026-04-29 | 0 | 0 | 33 | 0 | WARN |

**power_lotto issues:** 316 draws where special ball appears in main balls
**big_lotto issues:** 243 draws with special out of range [1..43]
**daily_539 issues:** 33 duplicated ball combinations

---
## Phase 2 — Uniformity Tests

> **Note:** Per-position tests are labeled [SORTED-ORDER-ARTIFACT] because draws are stored in sorted order, making positional frequency non-uniform by construction.

| Label | chi2 | df | p_raw | p_bonferroni | q_bh_fdr | Verdict |
|-------|------|-----|-------|-------------|----------|---------|
| power_lotto overall_frequency | 32.264 | 37 | 0.6906 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto position_1 [SORTED-ORDER-ARTIFACT] | 4904.693 | 37 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| power_lotto position_2 [SORTED-ORDER-ARTIFACT] | 1945.438 | 37 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| power_lotto position_3 [SORTED-ORDER-ARTIFACT] | 1400.558 | 37 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| power_lotto position_4 [SORTED-ORDER-ARTIFACT] | 1389.114 | 37 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| power_lotto position_5 [SORTED-ORDER-ARTIFACT] | 1875.658 | 37 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| power_lotto position_6 [SORTED-ORDER-ARTIFACT] | 4875.465 | 37 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| power_lotto special_ball | 9.333 | 7 | 0.2296 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto overall_frequency | 35.172 | 48 | 0.9160 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto position_1 [SORTED-ORDER-ARTIFACT] | 5412.779 | 48 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| big_lotto position_2 [SORTED-ORDER-ARTIFACT] | 1919.562 | 48 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| big_lotto position_3 [SORTED-ORDER-ARTIFACT] | 1454.039 | 48 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| big_lotto position_4 [SORTED-ORDER-ARTIFACT] | 1407.294 | 48 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| big_lotto position_5 [SORTED-ORDER-ARTIFACT] | 2006.152 | 48 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| big_lotto position_6 [SORTED-ORDER-ARTIFACT] | 5072.908 | 48 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| big_lotto special_ball | 56.933 | 42 | 0.0619 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 overall_frequency | 32.657 | 38 | 0.7146 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 position_1 [SORTED-ORDER-ARTIFACT] | 11554.248 | 38 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| daily_539 position_2 [SORTED-ORDER-ARTIFACT] | 4021.254 | 38 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| daily_539 position_3 [SORTED-ORDER-ARTIFACT] | 2995.385 | 38 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| daily_539 position_4 [SORTED-ORDER-ARTIFACT] | 3881.790 | 38 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |
| daily_539 position_5 [SORTED-ORDER-ARTIFACT] | 11459.259 | 38 | 0.0000 | 0.0000 | 0.0000 | SIGNIFICANT_DEVIATION_REQUIRES_REVIEW |

---
## Phase 3 — Structural Pattern Tests

| Game | Pattern | Obs Mean | Exp Mean | Exp SD | z_score | p_raw | p_bonferroni | q_bh_fdr | Verdict |
|------|---------|----------|----------|--------|---------|-------|-------------|----------|---------|
| power_lotto | consecutive_count | 0.7592 | 0.7897 | 0.0183 | -1.670 | 0.0950 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | same_tail_count | 1.1469 | 1.1529 | 0.0210 | -0.284 | 0.7764 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | odd_count | 2.9874 | 2.9995 | 0.0262 | -0.462 | 0.6443 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | low_count | 3.0163 | 3.0000 | 0.0265 | 0.616 | 0.5380 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | sum | 116.6653 | 117.0079 | 0.5791 | -0.592 | 0.5541 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | span | 27.9213 | 27.8596 | 0.1292 | 0.477 | 0.6331 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | repeat_from_prev | 0.9328 | 0.9462 | 0.0190 | -0.705 | 0.4811 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | pair_cooccurrence_gini | 0.0858 | 0.0877 | 0.0029 | -0.654 | 0.5134 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | gap_distribution | 5.5843 | 5.5719 | 0.0258 | 0.477 | 0.6331 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | consecutive_count | 0.6263 | 0.6132 | 0.0153 | 0.856 | 0.3922 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | same_tail_count | 1.2225 | 1.2249 | 0.0211 | -0.112 | 0.9108 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | odd_count | 3.0915 | 3.0614 | 0.0248 | 1.214 | 0.2249 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | low_count | 2.9324 | 2.9381 | 0.0249 | -0.230 | 0.8184 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | sum | 150.0728 | 150.0094 | 0.7066 | 0.090 | 0.9286 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | span | 35.7169 | 35.7139 | 0.1599 | 0.019 | 0.9852 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | repeat_from_prev | 0.7357 | 0.7342 | 0.0167 | 0.086 | 0.9317 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | pair_cooccurrence_gini | 0.1034 | 0.1072 | 0.0028 | -1.361 | 0.1735 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | gap_distribution | 7.1434 | 7.1428 | 0.0320 | 0.019 | 0.9852 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | consecutive_count | 0.5076 | 0.5134 | 0.0084 | -0.693 | 0.4883 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | same_tail_count | 0.7817 | 0.7694 | 0.0102 | 1.198 | 0.2310 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | odd_count | 2.5716 | 2.5643 | 0.0144 | 0.504 | 0.6141 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | low_count | 2.4401 | 2.4358 | 0.0139 | 0.305 | 0.7602 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | sum | 99.9195 | 100.0009 | 0.3109 | -0.262 | 0.7935 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | span | 26.7326 | 26.6659 | 0.0844 | 0.790 | 0.4298 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | repeat_from_prev | 0.6459 | 0.6405 | 0.0093 | 0.581 | 0.5612 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | pair_cooccurrence_gini | 0.0607 | 0.0634 | 0.0019 | -1.424 | 0.1543 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | gap_distribution | 6.6832 | 6.6665 | 0.0211 | 0.790 | 0.4298 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |

---
## Phase 4 — Serial Dependence Tests

| Game | Test | Lag/Window | Statistic | p_raw | p_bonferroni | q_bh_fdr | Verdict |
|------|------|------------|-----------|-------|-------------|----------|---------|
| power_lotto | sum_autocorrelation_ljungbox | 20 | 14.9447 | 0.7796 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | odd_count_runs_test | N/A | 0.4261 | 0.6701 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | repeat_overlap_runs_test | N/A | 1.2066 | 0.2276 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto | rolling_window_drift | first_half_953_vs_second_half_953 | 27.3679 | 0.8761 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | sum_autocorrelation_ljungbox | 20 | 12.9020 | 0.8815 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | odd_count_runs_test | N/A | 2.7717 | 0.0056 | 0.2454 | 0.2454 | WEAK_DEVIATION_NOT_SIGNIFICANT_AFTER_CORRECTION |
| big_lotto | repeat_overlap_runs_test | N/A | 0.3524 | 0.7246 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto | rolling_window_drift | first_half_1065_vs_second_half_1065 | 41.2658 | 0.7433 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | sum_autocorrelation_ljungbox | 20 | 10.2750 | 0.9629 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | odd_count_runs_test | N/A | -0.0058 | 0.9954 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | repeat_overlap_runs_test | N/A | 0.4216 | 0.6733 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539 | rolling_window_drift | first_half_2924_vs_second_half_2925 | 34.7540 | 0.6203 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |

---
## Phase 5 — Physical Bias Candidate Detection

> ⚠️  **EXPLORATORY ONLY** — Not included in multiple testing correction for confirmatory tests. These are hypothesis-generating observations only. No trading or prediction decision should be made based solely on this section.

### power_lotto

**Top 5 Overrepresented:**
| Number | Observed | Expected | Residual | Std Residual | p_binom | q_bh_fdr | Verdict |
|--------|----------|----------|----------|-------------|---------|----------|---------|
| 24 | 332 | 300.9 | 31.1 | 1.951 | 0.0573 | 0.7426 | NO_PHYSICAL_BIAS_SIGNAL |
| 3 | 328 | 300.9 | 27.1 | 1.699 | 0.0978 | 0.7426 | NO_PHYSICAL_BIAS_SIGNAL |
| 38 | 326 | 300.9 | 25.1 | 1.574 | 0.1253 | 0.7426 | NO_PHYSICAL_BIAS_SIGNAL |
| 14 | 322 | 300.9 | 21.1 | 1.322 | 0.1983 | 0.8371 | NO_PHYSICAL_BIAS_SIGNAL |
| 4 | 319 | 300.9 | 18.1 | 1.134 | 0.2708 | 0.9053 | NO_PHYSICAL_BIAS_SIGNAL |

**Top 5 Underrepresented:**
| Number | Observed | Expected | Residual | Std Residual | p_binom | q_bh_fdr | Verdict |
|--------|----------|----------|----------|-------------|---------|----------|---------|
| 9 | 261 | 300.9 | -39.9 | -2.509 | 0.0118 | 0.4494 | NO_PHYSICAL_BIAS_SIGNAL |
| 5 | 273 | 300.9 | -27.9 | -1.756 | 0.0820 | 0.7426 | NO_PHYSICAL_BIAS_SIGNAL |
| 32 | 276 | 300.9 | -24.9 | -1.567 | 0.1221 | 0.7426 | NO_PHYSICAL_BIAS_SIGNAL |
| 2 | 277 | 300.9 | -23.9 | -1.504 | 0.1384 | 0.7426 | NO_PHYSICAL_BIAS_SIGNAL |
| 34 | 278 | 300.9 | -22.9 | -1.441 | 0.1563 | 0.7426 | NO_PHYSICAL_BIAS_SIGNAL |

### big_lotto

**Top 5 Overrepresented:**
| Number | Observed | Expected | Residual | Std Residual | p_binom | q_bh_fdr | Verdict |
|--------|----------|----------|----------|-------------|---------|----------|---------|
| 8 | 290 | 260.8 | 29.2 | 1.929 | 0.0607 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |
| 2 | 283 | 260.8 | 22.2 | 1.466 | 0.1542 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |
| 15 | 283 | 260.8 | 22.2 | 1.466 | 0.1542 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |
| 41 | 281 | 260.8 | 20.2 | 1.334 | 0.1951 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |
| 1 | 280 | 260.8 | 19.2 | 1.268 | 0.2184 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |

**Top 5 Underrepresented:**
| Number | Observed | Expected | Residual | Std Residual | p_binom | q_bh_fdr | Verdict |
|--------|----------|----------|----------|-------------|---------|----------|---------|
| 4 | 229 | 260.8 | -31.8 | -2.103 | 0.0358 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |
| 6 | 230 | 260.8 | -30.8 | -2.037 | 0.0423 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |
| 9 | 234 | 260.8 | -26.8 | -1.773 | 0.0789 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |
| 17 | 237 | 260.8 | -23.8 | -1.574 | 0.1204 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |
| 24 | 240 | 260.8 | -20.8 | -1.376 | 0.1770 | 0.9164 | NO_PHYSICAL_BIAS_SIGNAL |

### daily_539

**Top 5 Overrepresented:**
| Number | Observed | Expected | Residual | Std Residual | p_binom | q_bh_fdr | Verdict |
|--------|----------|----------|----------|-------------|---------|----------|---------|
| 37 | 809 | 749.9 | 59.1 | 2.313 | 0.0230 | 0.6254 | NO_PHYSICAL_BIAS_SIGNAL |
| 5 | 798 | 749.9 | 48.1 | 1.882 | 0.0641 | 0.6254 | NO_PHYSICAL_BIAS_SIGNAL |
| 17 | 790 | 749.9 | 40.1 | 1.569 | 0.1228 | 0.8283 | NO_PHYSICAL_BIAS_SIGNAL |
| 34 | 784 | 749.9 | 34.1 | 1.335 | 0.1896 | 0.8283 | NO_PHYSICAL_BIAS_SIGNAL |
| 1 | 782 | 749.9 | 32.1 | 1.257 | 0.2170 | 0.8283 | NO_PHYSICAL_BIAS_SIGNAL |

**Top 5 Underrepresented:**
| Number | Observed | Expected | Residual | Std Residual | p_binom | q_bh_fdr | Verdict |
|--------|----------|----------|----------|-------------|---------|----------|---------|
| 30 | 701 | 749.9 | -48.9 | -1.911 | 0.0568 | 0.6254 | NO_PHYSICAL_BIAS_SIGNAL |
| 33 | 702 | 749.9 | -47.9 | -1.872 | 0.0622 | 0.6254 | NO_PHYSICAL_BIAS_SIGNAL |
| 3 | 720 | 749.9 | -29.9 | -1.168 | 0.2500 | 0.8283 | NO_PHYSICAL_BIAS_SIGNAL |
| 29 | 720 | 749.9 | -29.9 | -1.168 | 0.2500 | 0.8283 | NO_PHYSICAL_BIAS_SIGNAL |
| 13 | 724 | 749.9 | -25.9 | -1.012 | 0.3211 | 0.8283 | NO_PHYSICAL_BIAS_SIGNAL |

---
## Phase 6 — Formal Test Registry

Total confirmatory tests: **44**  |  Bonferroni threshold: **1.1364e-03**

| Test ID | Game | p_raw | p_bonferroni | q_bh_fdr | Verdict |
|---------|------|-------|-------------|----------|---------|
| power_lotto_overall_frequency | power_lotto | 0.6906 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_special_uniformity | power_lotto | 0.2296 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_consecutive_count | power_lotto | 0.0950 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_same_tail_count | power_lotto | 0.7764 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_odd_count | power_lotto | 0.6443 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_low_count | power_lotto | 0.5380 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_sum | power_lotto | 0.5541 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_span | power_lotto | 0.6331 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_repeat_from_prev | power_lotto | 0.4811 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_pair_cooccurrence_gini | power_lotto | 0.5134 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_pattern_gap_distribution | power_lotto | 0.6331 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_ljungbox_sum | power_lotto | 0.7796 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_runs_odd | power_lotto | 0.6701 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_runs_repeat | power_lotto | 0.2276 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| power_lotto_drift_halves | power_lotto | 0.8761 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_overall_frequency | big_lotto | 0.9160 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_special_uniformity | big_lotto | 0.0619 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_consecutive_count | big_lotto | 0.3922 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_same_tail_count | big_lotto | 0.9108 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_odd_count | big_lotto | 0.2249 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_low_count | big_lotto | 0.8184 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_sum | big_lotto | 0.9286 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_span | big_lotto | 0.9852 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_repeat_from_prev | big_lotto | 0.9317 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_pair_cooccurrence_gini | big_lotto | 0.1735 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_pattern_gap_distribution | big_lotto | 0.9852 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_ljungbox_sum | big_lotto | 0.8815 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_runs_odd | big_lotto | 0.0056 | 0.2454 | 0.2454 | WEAK_DEVIATION_NOT_SIGNIFICANT_AFTER_CORRECTION |
| big_lotto_runs_repeat | big_lotto | 0.7246 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| big_lotto_drift_halves | big_lotto | 0.7433 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_overall_frequency | daily_539 | 0.7146 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_consecutive_count | daily_539 | 0.4883 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_same_tail_count | daily_539 | 0.2310 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_odd_count | daily_539 | 0.6141 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_low_count | daily_539 | 0.7602 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_sum | daily_539 | 0.7935 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_span | daily_539 | 0.4298 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_repeat_from_prev | daily_539 | 0.5612 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_pair_cooccurrence_gini | daily_539 | 0.1543 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_pattern_gap_distribution | daily_539 | 0.4298 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_ljungbox_sum | daily_539 | 0.9629 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_runs_odd | daily_539 | 0.9954 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_runs_repeat | daily_539 | 0.6733 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |
| daily_539_drift_halves | daily_539 | 0.6203 | 1.0000 | 0.9954 | CONSISTENT_WITH_UNIFORM |

---
## Phase 7 — Output Files

- `outputs/randomness_audit/randomness_audit_summary.md` (this file)
- `outputs/randomness_audit/randomness_audit_results.json`

---
## Phase 8 — Memory/Wiki Update

✅ lessons.md and wiki/README.md updated.
<!-- P691_LEGACY_44_TEST_SUMMARY_END -->
