# P0 Replay Lifecycle Catalog Truth Inventory
**Date:** 2026-05-09  
**Branch:** codex/p0-replay-lifecycle-catalog-population-plan  
**Mode:** read-only dry-run  
**Authority:** `wiki/README.md` → `wiki/system/governance.md` → `wiki/system/validation_gates.md` → `wiki/system/strategy_retirement_policy.md`

Some governance/wiki source evidence was read from sibling canonical worktree /Users/kelvin/Kelvin-WorkSpace/LotteryNew because the corresponding files were missing in LotteryNew-main-postmerge.

## 1. Inventory Summary

This inventory only includes evidence that is directly supported by trusted repo sources. It does not promote WATCH or PROVISIONAL items into canonical lifecycle rows unless the source itself already labels them that way.

| lifecycle bucket | trusted count | evidence class | source path(s) | population decision |
|------------------|-------------:|----------------|-----------------|---------------------|
| ONLINE | 6 | canonical registry rows | `lottery_api/models/replay_strategy_registry.py`, `outputs/replay/p0_replay_lifecycle_coverage_20260509.md` | populate as canonical ONLINE |
| REJECTED | 42 | archive index rows | `rejected/README.md`, `rejected/*.json` | populate as canonical REJECTED |
| OBSERVATION | 0 canonical rows, 2 candidate rows | watch / provisional evidence only | `rejected/power_z3gap_watch.json`, `provisional/pp3_sum_reversal_power.json` | keep as OBSERVATION candidate only; do not coerce to ONLINE/OFFLINE/RETIRED |
| OFFLINE | 0 | no concrete trusted row | none | leave empty |
| RETIRED | 0 | policy exists, but no concrete trusted row | `wiki/system/strategy_retirement_policy.md` | leave empty |

## 2. Canonical Evidence

### ONLINE

The current replay registry exposes six canonical ONLINE adapters:

| strategy_id | lottery_type | source path |
|-------------|--------------|-------------|
| biglotto_deviation_2bet | BIG_LOTTO | `lottery_api/models/replay_strategy_registry.py` |
| biglotto_triple_strike | BIG_LOTTO | `lottery_api/models/replay_strategy_registry.py` |
| daily539_f4cold | DAILY_539 | `lottery_api/models/replay_strategy_registry.py` |
| daily539_markov_cold | DAILY_539 | `lottery_api/models/replay_strategy_registry.py` |
| power_orthogonal_5bet | POWER_LOTTO | `lottery_api/models/replay_strategy_registry.py` |
| power_precision_3bet | POWER_LOTTO | `lottery_api/models/replay_strategy_registry.py` |

### REJECTED

The archive index contains 42 rejected strategy rows across all three games. The archive is evidence-rich, but it is still an archive: it documents rejected or paused research, not live replay generation.

Representative source paths:

| source path | reason class | notes |
|-------------|--------------|-------|
| `rejected/gap_rebound_powerlotto.json` | INEFFECTIVE | gap pressure failed to add gain |
| `rejected/p1_conditional_branch_powerlotto.json` | STATISTICAL_ILLUSION | Bonferroni wipeout |
| `rejected/core_satellite_biglotto.json` | INEFFECTIVE | coverage loss dominated |
| `rejected/markov_1bet_539.json` | MARGINAL | z/p not significant |
| `rejected/acb_single_539.json` | INEFFECTIVE | residual pool efficiency too low |

### OBSERVATION candidate evidence

These rows are useful for a future OBSERVATION bucket, but they are not yet canonical lifecycle rows:

| source path | current label | why it is not canonical yet |
|-------------|---------------|-----------------------------|
| `rejected/power_z3gap_watch.json` | WATCH | status is a monitoring label, not a lifecycle registry row |
| `provisional/pp3_sum_reversal_power.json` | PROVISIONAL | explicitly provisional; McNemar not significant |

## 3. Empty Buckets

OFFLINE and RETIRED are intentionally left empty in this dry-run because no concrete trusted strategy row exists for either bucket in the current repo. The existence of policy text for RETIRED does not create a row.

## 4. Do Not Infer

- Do not infer OFFLINE from maintenance-only game wiki text.
- Do not infer RETIRED from archive status alone.
- Do not infer OBSERVATION from WATCH unless the target catalog schema explicitly accepts that mapping.
- Do not create synthetic rows to fill a visually empty state.
