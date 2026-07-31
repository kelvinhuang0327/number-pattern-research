# P223B - Candidate OOS / Cross-Year Validation

**Date:** 2026-06-03  
**Task:** `P223B_CANDIDATE_OOS_CROSS_YEAR_VALIDATION`  
**Status:** COMPLETE / READ-ONLY  
**Classification:** `P223B_CANDIDATE_OOS_VALIDATION_COMPLETE`  
**Authorized by:** User explicit task prompt 2026-06-03  

This report is read-only historical replay evidence. It does not modify the DB, registry, production state, recommendation logic, or any strategy. NULL is accepted as success and this is not betting advice.

## Phase 0 Verification

| Check | Result |
|---|---|
| repo root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` |
| branch | `main` |
| git dir | `.git` |
| head | `38535e5e18c3ce4f904997ed05bceae871f70700` |
| origin main | `38535e5e18c3ce4f904997ed05bceae871f70700` |
| staged files | `0` |
| replay rows | `94924` |
| BIG_LOTTO rows | `24140` |
| DAILY_539 rows | `34680` |
| POWER_LOTTO rows | `36104` |
| bet_index nulls | `0` |
| duplicate replay keys | `0` |
| PRAGMA integrity_check | `ok` |
| drift guard | `Status: PASS` |
| P221F artifacts tracked | `outputs/research/p221_cross_lottery_feature_discovery_protocol_20260603.md, outputs/research/p221_cross_lottery_feature_discovery_protocol_20260603.json` |

## Validation Method

- Scope: five P222 candidates only; no new feature families and no new windows.
- Tail OOS windows: last 150, 300, and 500 rows within the candidate grain.
- Cross-year split: 2024, 2025, and 2026 wherever dates exist.
- Baselines: lottery-level random/uniform, P222 row-level baseline, all-history reference, and best competing non-candidate baseline when available.
- Multiple testing: Bonferroni and BH-FDR across the five candidates.
- Unit labels are preserved explicitly: strategy-level, bet-index-level, row-level, and special-zone are not mixed.

## Summary

| Candidate | Type | Mean | Baseline | Raw p | Bonf q (5) | BH q (5) | Classification | Tail / Year synopsis |
|---|---|---:|---:|---:|---:|---:|---|---|
| midfreq_fourier_2bet | strategy | 0.8210 | 0.6410 | 5.18842e-35 | 2.59421e-34 | 2.59421e-34 | CROSS_YEAR_CONFIRMED | 150:above, 300:above, 500:above; 2024:above, 2025:above, 2026:above |
| midfreq_fourier_mk_3bet | strategy | 0.9896 | 0.9474 | 0.000844 | 0.004219 | 0.000844 | CANDIDATE_NEEDS_MORE_OOS | 150:above, 300:above, 500:above; 2024:above, 2025:below, 2026:above |
| DAILY_539 bet1 | bet-index | 0.6622 | 0.6410 | 9.78307e-06 | 4.89154e-05 | 1.63051e-05 | CANDIDATE_NEEDS_MORE_OOS | 150:above, 300:below, 500:above; 2024:below, 2025:above, 2026:above |
| POWER_LOTTO bet1 | bet-index | 0.9825 | 0.9474 | 2.59376e-07 | 1.29688e-06 | 6.4844e-07 | WEAK_OBSERVATION_ONLY | 150:below, 300:below, 500:above; 2024:above, 2025:below, 2026:below |
| POWER_LOTTO bet2 | bet-index | 0.9788 | 0.9474 | 0.000428 | 0.002138 | 0.000535 | REJECTED_NO_OOS_EDGE | 150:below, 300:below, 500:below; 2024:above, 2025:below, 2026:below |

## Per-Candidate Results

### midfreq_fourier_2bet

- Grain: strategy-level (row grain)
- Rows / distinct draws: `3000` / `2543`
- Overall mean hit count: `0.821000`
- 95% CI: `[ 0.792426, 0.849574 ]`
- Baseline random/uniform: `0.6410`
- P222 row-level baseline: `0.6410`
- All-history reference baseline: `0.625161`
- Best competing non-candidate baseline: `daily539_f4cold` at `0.678616`
- Raw p-value: `5.18842e-35`
- Bonferroni q (family=5): `2.59421e-34`
- BH q (family=5): `2.59421e-34`
- Classification: `CROSS_YEAR_CONFIRMED`
- Rationale: All tail windows are above baseline and 2024/2025/2026 annual means are above baseline, so this is the only clear cross-year survivor.

#### Tail OOS

| Window | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 150 | 150 | 0.866667 | [0.735134, 0.998199] | 0.000773 | above |
| 300 | 300 | 0.956667 | [0.860551, 1.052782] | 1.22266e-10 | above |
| 500 | 500 | 0.974000 | [0.896920, 1.051080] | 2.52406e-17 | above |

#### Cross-Year

| Year | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 2024 | 419 | 0.727924 | [0.652355, 0.803492] | 0.024208 | above |
| 2025 | 420 | 0.723810 | [0.652430, 0.795189] | 0.023019 | above |
| 2026 | 161 | 0.844720 | [0.723522, 0.965919] | 0.000988 | above |

### midfreq_fourier_mk_3bet

- Grain: strategy-level (row grain)
- Rows / distinct draws: `4500` / `1500`
- Overall mean hit count: `0.989556`
- 95% CI: `[ 0.964785, 1.014326 ]`
- Baseline random/uniform: `0.9474`
- P222 row-level baseline: `0.9474`
- All-history reference baseline: `0.946486`
- Best competing non-candidate baseline: `fourier_rhythm_3bet` at `0.974906`
- Raw p-value: `0.000844`
- Bonferroni q (family=5): `0.004219`
- BH q (family=5): `0.000844`
- Classification: `CANDIDATE_NEEDS_MORE_OOS`
- Rationale: Tail windows are above baseline, but the 2025 annual block falls below baseline and the cross-year support is not yet stable enough for confirmation.

#### Tail OOS

| Window | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 150 | 150 | 0.993333 | [0.849607, 1.137060] | 0.530783 | above |
| 300 | 300 | 0.966667 | [0.869397, 1.063936] | 0.697383 | above |
| 500 | 500 | 0.970000 | [0.895982, 1.044018] | 0.548991 | above |

#### Cross-Year

| Year | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 2024 | 315 | 0.980952 | [0.890382, 1.071523] | 0.467372 | above |
| 2025 | 312 | 0.942308 | [0.851066, 1.033550] | 0.913433 | below |
| 2026 | 120 | 0.950000 | [0.795310, 1.104690] | 0.973401 | above |

### DAILY_539 bet1

- Grain: bet-index-level (row grain)
- Rows / distinct draws: `22600` / `1550`
- Overall mean hit count: `0.662212`
- 95% CI: `[ 0.652822, 0.671603 ]`
- Baseline random/uniform: `0.6410`
- P222 row-level baseline: `0.6410`
- All-history reference baseline: `0.625161`
- Best competing non-candidate baseline: `DAILY_539 bet5` at `0.672667`
- Raw p-value: `9.78307e-06`
- Bonferroni q (family=5): `4.89154e-05`
- BH q (family=5): `1.63051e-05`
- Classification: `CANDIDATE_NEEDS_MORE_OOS`
- Rationale: Family correction survives, but the 2024 block is below baseline and the 300-row tail window is also below baseline, so the signal is not yet stable enough for confirmation.

#### Tail OOS

| Window | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 150 | 150 | 0.693333 | [0.572233, 0.814433] | 0.198494 | above |
| 300 | 300 | 0.580000 | [0.501307, 0.658693] | 0.935658 | below |
| 500 | 500 | 0.662000 | [0.597602, 0.726398] | 0.261361 | above |

#### Cross-Year

| Year | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 2024 | 4710 | 0.620807 | [0.600553, 0.641060] | 0.97466 | below |
| 2025 | 4740 | 0.667089 | [0.646427, 0.687750] | 0.006665 | above |
| 2026 | 1815 | 0.661708 | [0.628454, 0.694962] | 0.111134 | above |

### POWER_LOTTO bet1

- Grain: bet-index-level (row grain)
- Rows / distinct draws: `15102` / `1551`
- Overall mean hit count: `0.982519`
- 95% CI: `[ 0.969144, 0.995894 ]`
- Baseline random/uniform: `0.9474`
- P222 row-level baseline: `0.9474`
- All-history reference baseline: `0.946486`
- Best competing non-candidate baseline: `POWER_LOTTO bet5` at `0.940667`
- Raw p-value: `2.59376e-07`
- Bonferroni q (family=5): `1.29688e-06`
- BH q (family=5): `6.4844e-07`
- Classification: `WEAK_OBSERVATION_ONLY`
- Rationale: The family correction survives, but 150/300 tail windows are below baseline and the special-zone signal is below the 0.125 reference; this is too unstable for promotion.

#### Tail OOS

| Window | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 150 | 150 | 0.866667 | [0.737754, 0.995579] | 0.890178 | below |
| 300 | 300 | 0.923333 | [0.827930, 1.018737] | 0.689499 | below |
| 500 | 500 | 0.950000 | [0.871625, 1.028375] | 0.474079 | above |

#### Cross-Year

| Year | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 2024 | 1050 | 0.961905 | [0.912289, 1.011520] | 0.283324 | above |
| 2025 | 1040 | 0.882692 | [0.833704, 0.931681] | 0.995186 | below |
| 2026 | 403 | 0.940447 | [0.857542, 1.023351] | 0.565288 | below |

#### Special-Zone Tail

| Window | n | Mean special_hit | 95% CI | p vs 0.125 | Direction |
|---|---:|---:|---|---:|---|
| 150 | 150 | 0.073333 | [0.031615, 0.115051] | 0.992397 | below |
| 300 | 300 | 0.073333 | [0.043834, 0.102832] | 0.999701 | below |
| 500 | 500 | 0.066000 | [0.044237, 0.087763] | 1 | below |

### POWER_LOTTO bet2

- Grain: bet-index-level (row grain)
- Rows / distinct draws: `9001` / `1501`
- Overall mean hit count: `0.978780`
- 95% CI: `[ 0.961302, 0.996258 ]`
- Baseline random/uniform: `0.9474`
- P222 row-level baseline: `0.9474`
- All-history reference baseline: `0.946486`
- Best competing non-candidate baseline: `POWER_LOTTO bet5` at `0.940667`
- Raw p-value: `0.000428`
- Bonferroni q (family=5): `0.002138`
- BH q (family=5): `0.000535`
- Classification: `REJECTED_NO_OOS_EDGE`
- Rationale: All tail windows are below baseline, so this candidate does not survive OOS validation despite corrected in-sample support.

#### Tail OOS

| Window | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 150 | 150 | 0.913333 | [0.782749, 1.043917] | 0.695438 | below |
| 300 | 300 | 0.940000 | [0.841150, 1.038850] | 0.558326 | below |
| 500 | 500 | 0.942000 | [0.869791, 1.014209] | 0.558266 | below |

#### Cross-Year

| Year | n | Mean | 95% CI | p vs baseline | Direction |
|---|---:|---:|---|---:|---|
| 2024 | 630 | 0.953968 | [0.888438, 1.019499] | 0.422127 | above |
| 2025 | 624 | 0.886218 | [0.822236, 0.950199] | 0.969551 | below |
| 2026 | 242 | 0.929752 | [0.825463, 1.034042] | 0.629932 | below |

## Overall Recommendation

- P224 deeper validation candidate: `midfreq_fourier_2bet`
- Hold for more OOS: `midfreq_fourier_mk_3bet, DAILY_539 bet1`
- Weak observation only: `POWER_LOTTO bet1`
- Rejected: `POWER_LOTTO bet2`
- No strategy is deployable from P223B alone.
- No production or recommendation change is authorized.
- Results are historical replay evidence only, not betting advice.

## Required Completion Check

1. 是否真的完成: YES
2. 測試結果 PASS / FAIL / NOT RUN: PASS for read-only validation and JSON parse; full test suite NOT RUN
3. 仍卡住的唯一問題: none
4. 修改檔案清單:
   - `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/outputs/research/p223b_candidate_oos_cross_year_validation_20260603.md`
   - `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/outputs/research/p223b_candidate_oos_cross_year_validation_20260603.json`
5. staged / commit / push 狀態: `0 / 0 / 0`
6. 是否允許進入下一輪: YES
7. Final Classification: `P223B_CANDIDATE_OOS_VALIDATION_COMPLETE`
