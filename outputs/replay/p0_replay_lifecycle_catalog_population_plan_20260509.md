# P0 Replay Lifecycle Catalog Population Plan
**Date:** 2026-05-09  
**Branch:** codex/p0-replay-lifecycle-catalog-population-plan  
**Mode:** dry-run only  
**Goal:** build a truthful lifecycle catalog without fabricating missing states or touching production storage

Some governance/wiki source evidence was read from sibling canonical worktree /Users/kelvin/Kelvin-WorkSpace/LotteryNew because the corresponding files were missing in LotteryNew-main-postmerge.

## 1. Input Sources

Use only trusted evidence sources:

| source | purpose |
|--------|---------|
| `lottery_api/models/replay_strategy_registry.py` | canonical ONLINE registry rows and lifecycle enum |
| `outputs/replay/p0_replay_lifecycle_coverage_20260509.md` | current registry coverage snapshot |
| `wiki/games/big_lotto.md` | game-level maintenance / watch context |
| `wiki/games/daily_539.md` | game-level maintenance / watch context |
| `wiki/games/power_lotto.md` | game-level maintenance / watch context |
| `rejected/README.md` | archive index for rejected strategies |
| `rejected/*.json` | concrete rejected archive rows |
| `provisional/*.json` | provisional candidates under observation |
| `wiki/system/strategy_retirement_policy.md` | retirement policy, not row evidence |

## 2. Population Rules

| rule | action |
|------|--------|
| ACTIVE in registry | normalise to ONLINE |
| explicit registry ONLINE | populate canonical ONLINE |
| archive row in `rejected/` | populate canonical REJECTED |
| WATCH / PROVISIONAL evidence | keep as OBSERVATION candidate only if the target schema supports an observation bucket |
| no trusted concrete row | leave empty |
| RETIRED policy with no row | leave empty |

## 3. Dry-Run Workflow

1. Read each source file and extract only directly stated lifecycle evidence.
2. Separate canonical rows from candidate evidence.
3. Write catalog entries only for rows that can be justified by a trusted source path.
4. Preserve OBSERVATION as a candidate bucket unless a future canonical lifecycle source explicitly maps WATCH / PROVISIONAL into OBSERVATION.
5. Record OFFLINE and RETIRED as intentionally empty states.

## 4. No-Write Boundary

This task does not:

- modify any production DB or replay data store
- update runtime strategy state
- rewrite archive files
- convert WATCH / PROVISIONAL into RETIRED without policy evidence
- synthesize placeholder strategies for empty buckets

## 5. Output Contract

The population worker should emit:

- a truth inventory file
- a population plan file
- an empty-state spec
- a forbidden-language sweep

It should not emit DB mutations, migration SQL, or auto-generated status rows without source attribution.
