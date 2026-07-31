# P233A — Lifecycle-Unresolved Registry Hygiene Plan

**Date:** 20260604  
**Task:** `P233A_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_PLAN`  
**Status:** PLAN ONLY / READ-ONLY / ZERO REGISTRY WRITE / ZERO DB WRITE

> **No registry changes in P233A.** This document records the evidence-based lifecycle suggestion for each of the 20 LIFECYCLE_UNRESOLVED entries. Actual registry stub additions require a separate P233B task with explicit user authorization. Not betting advice. Not deployment authorization.

## Executive Summary

| Metric | Value |
|---|---|
| LIFECYCLE_UNRESOLVED entries | 20 |
| Suggested REJECTED | 12 |
| Suggested RETIRED | 8 |
| DB write performed | False |
| Registry modified | False |

## Why 20 LIFECYCLE_UNRESOLVED Entries Exist

These strategy+lottery combos have replay rows in the production DB but are absent from the current `_ALL_ADAPTERS` list in `replay_strategy_registry.py`. Two root causes:
1. **Prior governance decisions** — strategy was evaluated and REJECTED; a `rejected/` archive JSON was recorded but the strategy was never added to `_NON_EXECUTABLE_STUBS` (or was later removed).
2. **Production-applied and superseded** — strategy was applied to the production DB via authorized controlled apply (P59/P66/P79/P94/P126D), accumulated replay rows, and was then superseded by newer ONLINE strategies without a RETIRED stub being registered.

## Evidence Sources (all read-only)

- `rejected/` directory: presence of `{strategy_id}.json` = prior REJECTED decision
- `scripts/replay_lifecycle_drift_guard.py`: comments record P59/P66/P79/P94/P126D production applies
- `scripts/p94_tierb_controlled_apply.py`: Tier-B adapter list
- `tools/quick_predict.py`, `tools/backtest_power_5bet_stack.py`, `tools/rsm_bootstrap.py`: production prediction functions
- git log: ratified P93/P94/P59/P66 controlled apply commits

## BIG_LOTTO — 8 LIFECYCLE_UNRESOLVED Entries

| Strategy ID | Draws | Rows | BetIdx | RowMean | Δbaseline | Has rejected/ | Suggestion |
|---|---:|---:|---|---:|---:|---|---|
| `bet2_fourier_expansion_biglotto` | 1500 | 1500 | 1 | 0.7240 | -0.0107 | ✓ | **REJECTED** |
| `biglotto_echo_aware_3bet` | 1500 | 4500 | 1,2,3 | 0.7478 | +0.0131 | — | **RETIRED** |
| `biglotto_ts3_markov_4bet_w30` | 1500 | 6000 | 1,2,3,4 | 0.7330 | -0.0017 | — | **RETIRED** |
| `cold_complement_biglotto` | 1500 | 1500 | 1 | 0.7353 | +0.0006 | ✓ | **REJECTED** |
| `coldpool15_biglotto` | 1500 | 1500 | 1 | 0.7353 | +0.0006 | ✓ | **REJECTED** |
| `fourier30_markov30_biglotto` | 1500 | 1500 | 1 | 0.7213 | -0.0134 | ✓ | **REJECTED** |
| `markov_2bet_biglotto` | 1500 | 1500 | 1 | 0.7280 | -0.0067 | ✓ | **REJECTED** |
| `markov_single_biglotto` | 1500 | 1500 | 1 | 0.7280 | -0.0067 | ✓ | **REJECTED** |

### BIG_LOTTO — Evidence Details

**`bet2_fourier_expansion_biglotto`** (REJECTED)
- rejected/bet2_fourier_expansion_biglotto.json exists in archive directory — prior governance REJECTED decision recorded.

**`biglotto_echo_aware_3bet`** (RETIRED)
- P93/P94 Tier-B Controlled Replay Apply (commit cd981f3); referenced in scripts/p93_tierb_dryrun_rehearsal.py and scripts/p94a_biglotto_all_strategy_betcount_benchmark.py. Superseded by biglotto_deviation_2bet / ts3_regime_3bet (ONLINE).

**`biglotto_ts3_markov_4bet_w30`** (RETIRED)
- P93/P94 Tier-B Controlled Replay Apply (commit cd981f3); referenced in scripts/p93_tierb_dryrun_rehearsal.py and scripts/p113_p112_action_decision_matrix.py. 4-bet variant superseded by current BIG_LOTTO ONLINE strategies.

**`cold_complement_biglotto`** (REJECTED)
- rejected/cold_complement_biglotto.json exists in archive directory. Also referenced in scripts/p44_wave3_biglotto_performance_analysis.py Wave 3 analysis (prior to current ONLINE strategies).

**`coldpool15_biglotto`** (REJECTED)
- rejected/coldpool15_biglotto.json exists. tools/backtest_biglotto_coldpool_15.py explicitly labels action as '→ 歸檔 rejected/coldpool15_biglotto.json'.

**`fourier30_markov30_biglotto`** (REJECTED)
- rejected/fourier30_markov30_biglotto.json exists. Referenced in scripts/p44_wave3_biglotto_performance_analysis.py Wave 3 analysis.

**`markov_2bet_biglotto`** (REJECTED)
- rejected/markov_2bet_biglotto.json exists. Referenced in scripts/p44_wave3_biglotto_performance_analysis.py.

**`markov_single_biglotto`** (REJECTED)
- rejected/markov_single_biglotto.json exists. Referenced in scripts/p44_wave3_biglotto_performance_analysis.py.

## DAILY_539 — 8 LIFECYCLE_UNRESOLVED Entries

| Strategy ID | Draws | Rows | BetIdx | RowMean | Δbaseline | Has rejected/ | Suggestion |
|---|---:|---:|---|---:|---:|---|---|
| `539_3bet_orthogonal` | 1500 | 1500 | 1 | 0.6720 | +0.0310 | ✓ | **REJECTED** |
| `acb_single_539` | 1500 | 1500 | 1 | 0.6720 | +0.0310 | ✓ | **REJECTED** |
| `daily539_f4cold_3bet` | 1500 | 4500 | 1,2,3 | 0.6558 | +0.0148 | — | **RETIRED** |
| `daily539_f4cold_5bet` | 1500 | 7500 | 1,2,3,4,5 | 0.6492 | +0.0082 | — | **RETIRED** |
| `markov_1bet_539` | 1500 | 1500 | 1 | 0.6340 | -0.0070 | ✓ | **REJECTED** |
| `p0b_539_3bet_f_cold_fmid` | 1500 | 1500 | 1 | 0.6773 | +0.0363 | ✓ | **REJECTED** |
| `p0c_539_3bet_f_cold_x2` | 1500 | 1500 | 1 | 0.6773 | +0.0363 | ✓ | **REJECTED** |
| `zone_gap_3bet_539` | 1500 | 1500 | 1 | 0.6287 | -0.0124 | ✓ | **REJECTED** |

### DAILY_539 — Evidence Details

**`539_3bet_orthogonal`** (REJECTED)
- rejected/539_3bet_orthogonal.json exists in archive directory — prior governance REJECTED decision recorded.

**`acb_single_539`** (REJECTED)
- rejected/acb_single_539.json exists in archive directory. Likely an earlier ACB single-bet variant before acb_1bet (RETIRED).

**`daily539_f4cold_3bet`** (RETIRED)
- Referenced in scripts/p94_tierb_controlled_apply.py Tier-B apply list (P94_TIER_B_CONTROLLED_APPLY_SUCCESS, commit cd981f3). Also scripts/replay_lifecycle_drift_guard.py line ~98: 'P126D: DAILY_539 f4cold_3bet multi-bet (3000 rows)'. Superseded by daily539_f4cold (ONLINE).

**`daily539_f4cold_5bet`** (RETIRED)
- Referenced in scripts/p94_tierb_controlled_apply.py Tier-B apply list (P94_TIER_B_CONTROLLED_APPLY_SUCCESS). 5-bet multi-bet variant. Superseded by daily539_f4cold (ONLINE).

**`markov_1bet_539`** (REJECTED)
- rejected/markov_1bet_539.json exists in archive directory — prior governance REJECTED decision recorded.

**`p0b_539_3bet_f_cold_fmid`** (REJECTED)
- rejected/p0b_539_3bet_f_cold_fmid.json exists in archive directory. git history shows it was previously a _LifecycleStub in replay_strategy_registry.py before being removed.

**`p0c_539_3bet_f_cold_x2`** (REJECTED)
- rejected/p0c_539_3bet_f_cold_x2.json exists in archive directory. Paired with p0b as P0C variant; likely same rejection round.

**`zone_gap_3bet_539`** (REJECTED)
- rejected/zone_gap_3bet_539.json exists in archive directory — prior governance REJECTED decision recorded.

## POWER_LOTTO — 4 LIFECYCLE_UNRESOLVED Entries

| Strategy ID | Draws | Rows | BetIdx | RowMean | Δbaseline | Has rejected/ | Suggestion |
|---|---:|---:|---|---:|---:|---|---|
| `cold_complement_2bet` | 1500 | 1500 | 1 | 0.9407 | -0.0067 | — | **RETIRED** |
| `fourier30_markov30_2bet` | 1501 | 1501 | 1 | 0.9647 | +0.0173 | — | **RETIRED** |
| `power_fourier_rhythm_2bet` | 1500 | 3000 | 1,2 | 0.9633 | +0.0160 | — | **RETIRED** |
| `zonal_entropy_2bet` | 1500 | 1500 | 1 | 0.9460 | -0.0014 | — | **RETIRED** |

### POWER_LOTTO — Evidence Details

**`cold_complement_2bet`** (RETIRED)
- scripts/replay_lifecycle_drift_guard.py line ~86: 'P66: POWER_LOTTO Wave 6 controlled production apply — cold_complement_2bet + zonal_entropy_2bet (3000 rows) (2026-05-25)'. Was production-applied; superseded by fourier_rhythm_3bet / power_orthogonal_5bet (ONLINE).

**`fourier30_markov30_2bet`** (RETIRED)
- scripts/replay_lifecycle_drift_guard.py line ~84: 'P59: POWER_LOTTO Wave 5 controlled production apply — fourier30_markov30_2bet (1500 rows) (2026-05-25)'. Also P79 Batch A draw-ext apply (line ~89/134). Was production-applied; superseded by fourier_rhythm_3bet (ONLINE).

**`power_fourier_rhythm_2bet`** (RETIRED)
- tools/quick_predict.py defines power_fourier_rhythm_2bet() — a 2-bet production prediction function. git history shows it was previously a _LifecycleStub in replay_strategy_registry.py before being removed. Superseded by fourier_rhythm_3bet (ONLINE).

**`zonal_entropy_2bet`** (RETIRED)
- scripts/replay_lifecycle_drift_guard.py line ~86: 'P66: POWER_LOTTO Wave 6 controlled production apply — cold_complement_2bet + zonal_entropy_2bet (3000 rows) (2026-05-25)'. Was production-applied; superseded by ONLINE strategies.

## Proposed P233B Allowlist (if user authorizes execution)

> P233B is NOT authorized by this P233A plan alone. It requires separate explicit user authorization.

If authorized, P233B should be restricted to:
- `lottery_api/models/replay_strategy_registry.py`
- `outputs/research/p233b_lifecycle_unresolved_registry_hygiene_execute_YYYYMMDD.json`
- `outputs/research/p233b_lifecycle_unresolved_registry_hygiene_execute_YYYYMMDD.md`
- `tests/test_p233b_lifecycle_unresolved_registry_hygiene_execute.py`

P233B action: add `_LifecycleStub` entries to `_NON_EXECUTABLE_STUBS` list in `replay_strategy_registry.py` for each of the 20 entries with their suggested lifecycle status. No DB write. No executable adapters. No production / recommendation logic change.

## Caveats

- P233A is a PLAN ONLY — no registry file is modified.
- lifecycle suggestions are conservative governance labels for future _NON_EXECUTABLE_STUB additions; they do not affect any production system.
- REJECTED suggestion = evidence of prior governance rejection decision (rejected/ archive file exists).
- RETIRED suggestion = strategy was production-applied via authorized controlled apply (P59/P66/P79/P94/P126D) and has been superseded by current ONLINE strategies.
- No strategy is suggested as ONLINE, DEPLOYABLE, or any promotion label.
- P233B execution (actual registry edits) requires separate explicit user authorization.
- Historical replay metrics do not authorize deployment — they are evidence only.

## Final Classification
`P233A_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_PLAN_COMPLETE`

> DB write: **False** | Registry modified: **False**
