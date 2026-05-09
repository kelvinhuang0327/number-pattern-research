# P0 Replay Lifecycle Forbidden Language Sweep
**Date:** 2026-05-09  
**Branch:** codex/p0-replay-lifecycle-catalog-population-plan  
**Mode:** read-only verification

Some governance/wiki source evidence was read from sibling canonical worktree /Users/kelvin/Kelvin-WorkSpace/LotteryNew because the corresponding files were missing in LotteryNew-main-postmerge.

## 1. Terms to Avoid

The following phrases overstate what the repo can prove right now:

- `all lifecycle states are populated`
- `complete lifecycle catalog`
- `production-ready catalog`
- `zero gaps across all lifecycle buckets`
- `OFFLINE and RETIRED are confirmed populated`
- `WATCH evidence is canonical OBSERVATION`

## 2. Required Replacements

Use the following phrasing instead:

- `canonical ONLINE and REJECTED evidence are present`
- `OBSERVATION has candidate evidence only`
- `OFFLINE and RETIRED are currently empty in trusted sources`
- `no production writes were performed`
- `dry-run population plan only`

## 3. Sweep Targets

| target | what to check |
|--------|---------------|
| `outputs/replay/p0_replay_lifecycle_catalog_truth_inventory_20260509.md` | must not claim full lifecycle completeness |
| `outputs/replay/p0_replay_lifecycle_catalog_population_plan_20260509.md` | must not include DB mutation language |
| `outputs/replay/p0_replay_lifecycle_empty_state_spec_20260509.md` | must preserve honest empty-state copy |
| `outputs/replay/p0_replay_lifecycle_forbidden_language_sweep_20260509.md` | must clearly distinguish candidate evidence from canonical rows |

## 4. Verification Result

Pass criteria for this dry-run:

- canonical ONLINE rows are sourced from the replay registry
- REJECTED rows are sourced from `rejected/`
- WATCH / PROVISIONAL rows remain candidates unless explicitly mapped
- OFFLINE / RETIRED remain empty where no trusted row exists

Fail criteria:

- any synthetic row inserted to fill an empty bucket
- any statement that converts archive policy into runtime state
- any language that implies production DB writes happened
