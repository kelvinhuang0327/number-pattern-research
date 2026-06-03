# P221F — Freeze Cross-Lottery Feature Discovery Protocol

**Date:** 2026-06-03  
**Task:** `P221F_CROSS_LOTTERY_FEATURE_DISCOVERY_PROTOCOL_FREEZE`  
**Status:** PLAN-ONLY / READ-ONLY / PROTOCOL FROZEN  
**Classification:** `P221F_PROTOCOL_FROZEN_FOR_P222_READ_ONLY_SCAN`  
**Authorized by:** User explicit task prompt 2026-06-03  

This document freezes the protocol for a future read-only P222 scan. It does not run P222, does not change DB state, does not change registry state, and does not promote any strategy.

## Phase 0 Verification

| Check | Expected | Actual | Result |
|---|---:|---:|---|
| repo root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | PASS |
| branch before creation | `main` | `main` | PASS |
| git dir | `.git` | `.git` | PASS |
| HEAD == origin/main | yes | yes | PASS |
| staged files | 0 | 0 | PASS |
| total replay rows | 94924 | 94924 | PASS |
| BIG_LOTTO rows | 24140 | 24140 | PASS |
| DAILY_539 rows | 34680 | 34680 | PASS |
| POWER_LOTTO rows | 36104 | 36104 | PASS |
| `bet_index` nulls | 0 | 0 | PASS |
| duplicate replay keys | 0 | 0 | PASS |
| PRAGMA integrity_check | `ok` | `ok` | PASS |
| drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` | PASS |
| P211A artifacts exist and are tracked | yes | yes | PASS |

## Protocol Purpose

P221F freezes the rules for a future cross-lottery, read-only feature discovery scan. The goal is to search broadly across lottery types, strategies, replay rows, historical windows, and feature families without turning the scan into a false-positive factory.

The scan must remain descriptive and leakage-safe. It may identify candidate signals, but it may not promote them, deploy them, or turn them into betting advice.

## Hard Stops

P222 must stop immediately if any of the following occur:

- repo / branch / HEAD / DB baseline diverges from Phase 0
- drift guard fails
- staged files are non-empty before the run
- the scan requires DB write, registry write, production write, or strategy promotion
- the scan tries to use post-hoc window selection
- the scan omits zero-row / no-data strategies from the catalog
- the scan silently excludes lifecycle labels
- the scan mixes row-level, draw-level, strategy-level, or bet-index-level metrics without labeling the unit
- the scan begins promoting special-zone results into scoring or recommendation logic

## Universe Definition

### Lottery universe

P222 must include:

- `BIG_LOTTO`
- `DAILY_539`
- `POWER_LOTTO`
- `3_STAR`
- `4_STAR`
- any other `lottery_type` present in `strategy_prediction_replays`
- any other `lottery_type` surfaced by the registry or related catalog data

### Strategy universe

P222 must include:

- all `strategy_id` values appearing in replay rows
- all `bet_index` values appearing in replay rows
- all lifecycle labels as labels, not exclusion filters
- zero-row and no-data strategies as explicit report rows

### Current observed replay universe snapshot

- replay `lottery_type` values currently present in the DB: `BIG_LOTTO`, `DAILY_539`, `POWER_LOTTO`
- replay `bet_index` values currently present in the DB: `1`, `2`, `3`, `4`, `5`
- registry lifecycle labels currently observed: `ONLINE`, `RETIRED`, `REJECTED`, `OBSERVATION`

Any additional lifecycle or catalog label encountered during the P222 scan must be preserved as a label and reported honestly.

## Window Families

P222 primary windows are frozen as follows:

- short: `100`, `125`, `150`
- mid: `500`, `750`, `1000`
- all-history: baseline / reference only

Rules:

- the window set above is fixed before the scan starts
- no post-hoc selection of the best-looking window
- optional sensitivity windows may only be listed as future follow-up
- sensitivity windows are not part of the P222 primary scan
- all-history may be used only as a reference baseline, not as the primary selector

## Feature Families

### A. Frequency / Recency

- hot number frequency
- cold number frequency
- frequency delta short vs mid
- frequency delta mid vs all-history
- EWMA frequency
- overdue / gap length
- last-seen distance

### B. Distribution / Structure

- odd/even balance
- high/low balance
- sum range
- span
- consecutive count
- repeated last digit
- modulo bucket
- prime count
- number-zone coverage

### C. Co-occurrence

- pair frequency
- triple frequency
- number cluster stability
- co-hit patterns by strategy

### D. Strategy Behavior

- `strategy_id`
- lifecycle
- `bet_index`
- strategy family
- prediction concentration
- prediction entropy
- strategy diversity
- consensus between strategies

### E. Time Stability

- draw era
- rolling-window stability
- OOS block stability
- monthly drift if dates exist
- yearly drift if dates exist
- cross-year validation if enough data exists

### F. Special-Zone

- POWER_LOTTO second-zone remains display-only
- special-zone metrics may be reported separately
- special-zone metrics must not affect scoring
- special-zone metrics must not affect recommendation promotion

## Outcome Metrics

P222 must report the following, with the unit always labeled:

- hit_count distribution
- M1+ / M2+ / M3+ thresholds by lottery type where meaningful
- exact-hit metrics for `3_STAR` / `4_STAR` if applicable
- special_hit separated from main-number outcomes
- draw-level metrics
- row-level metrics
- strategy-level metrics
- bet-index-level metrics

Rules:

- do not mix units without labeling
- do not compare row-level and draw-level hit rates as if they were the same object
- do not collapse special-zone and main-number results into one score

## Baselines

P222 must compare candidates against all of the following:

- random baseline by lottery type
- simple uniform baseline
- all-history reference baseline
- best single pre-existing strategy baseline
- lifecycle-stratified baseline
- recent-window baseline
- consensus baseline

Rules:

- baselines must be predeclared
- baselines must be reported per lottery type
- no baseline may be retrofitted after seeing the outputs

## Reporting Rules

The P222 report must:

- remain read-only
- identify every source universe explicitly
- keep lifecycle labels visible
- keep zero-row / no-data strategies visible
- separate descriptive findings from significance claims
- distinguish artifact counts, replay rows, draws, strategies, and bets
- state NULL honestly when the evidence is null
- avoid any betting advice or guaranteed prediction claims

## Validation Gates

P222 is only valid if all of the following hold:

1. Phase 0 checks pass.
2. DB and registry remain unchanged.
3. The scan uses only frozen windows and frozen universe rules.
4. The scan reports every lifecycle label as a label.
5. The scan reports zero-row / no-data strategies instead of dropping them.
6. The scan uses labeled units for every metric.
7. The scan does not promote second-zone special metrics into scoring logic.
8. The scan does not use post-hoc selection.

## Required Completion Check

When this protocol is frozen, the completion report must state:

1. 是否真的完成
2. 測試結果 PASS / FAIL / NOT RUN
3. 仍卡住的唯一問題
4. 修改檔案清單
5. staged / commit / push 狀態
6. 是否允許進入下一輪
7. Final Classification

## Final Notes

This file freezes the protocol only. It authorizes a future read-only P222 scan, but it does not authorize any scan execution here.
