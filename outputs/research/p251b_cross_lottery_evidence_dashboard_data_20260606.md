# P251B — Cross-Lottery Evidence Dashboard Data Artifact

**Date:** 2026-06-06 19:21:30  
**Task:** `P251B`  
**Classification:** `CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT`  

## Executive Summary

This artifact transforms the published P250A inventory and the P251A dashboard contract into a concrete dashboard-ready JSON shape. It keeps every historical strategy row visible, separates replay / draw / canonical semantics, and preserves the rule that lifecycle is a badge/filter only.

## Source Artifacts Used

- p250a_inventory: `outputs/research/p250a_cross_lottery_strategy_replay_inventory_20260606.json`
- p251a_contract: `outputs/research/p251a_cross_lottery_evidence_dashboard_dryrun_plan_20260606.json`
- current_state: `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
- active_task: `00-Plan/roadmap/active_task.md`
- roadmap: `00-Plan/roadmap/roadmap.md`

## Dashboard-Ready Data Shape

- `global_summary`
- `lottery_cards`
- `strategy_rows`
- `lifecycle_filter_options`
- `lifecycle_badge_vocabulary`
- `replay_coverage_summary`
- `draw_count_semantics`
- `evidence_state_summary`
- `stale_snapshot_warning`
- `no_exclusion_rules`
- `default_filter_state`
- `no_betting_advice_notice`
- `implementation_readiness`
- `forbidden_actions_confirmed`
- `final_decision`

## Global Summary

- source_of_truth: `P250A inventory artifact published on main`
- current_registry_is_live_ssot: `True`
- historical_scoreboard_is_snapshot: `True`
- current_registry_entries: `38`
- historical_inventory_entries: `41`
- artifact_only_entries: `3`
- replay_rows_total: `94924`
- draw_rows_total: `64361`
- big_lotto_raw_draw_rows: `22238`
- big_lotto_canonical_rows: `2113`
- big_lotto_add_on_rows: `19100`
- no_deployable_candidate: `True`
- no_prediction_edge_claim: `True`
- lifecycle_is_label_not_exclusion: `True`

## Lottery Cards Summary

### BIG_LOTTO

- strategy_cards_visible: `13`
- replay_rows: `24140`
- draw_rows: `22238`
- canonical_rows: `2113`
- artifact_only_rows_visible: `False`
- lifecycle_visibility_rule: `badge/filter only; never exclusion`
- note: replay rows are strategy_prediction_replays rows, not draw rows
- note: raw BIG_LOTTO draw rows remain 22,238; canonical main-draw rows are 2,113
- note: 19,100 add-on/special-prize rows stay raw-accessible and are excluded from canonical 6/49 research
- note: P249B fixes the replay-row vs draw-row label ambiguity

### DAILY_539

- strategy_cards_visible: `16`
- replay_rows: `34680`
- draw_rows: `5879`
- canonical_rows: `None`
- artifact_only_rows_visible: `False`
- lifecycle_visibility_rule: `badge/filter only; never exclusion`
- note: replay rows are strategy_prediction_replays rows, not draw rows
- note: no canonical/raw split currently tracked beyond the draw table count
- note: P230C closed the prior DAILY_539 survivor as rejected/historical artifact

### POWER_LOTTO

- strategy_cards_visible: `12`
- replay_rows: `36104`
- draw_rows: `1916`
- canonical_rows: `None`
- artifact_only_rows_visible: `True`
- lifecycle_visibility_rule: `badge/filter only; never exclusion`
- note: replay rows are strategy_prediction_replays rows, not draw rows
- note: three P47 artifact-only strategies remain in the historical inventory
- note: current registry has no active deployable candidate

## Lifecycle Filter Behavior

The default view includes every lifecycle status. Filters only narrow the view; they never hide historical replay/catalog rows by default.

## Strategy Row Preservation Rules

- All 41 P250A inventory rows remain visible in `strategy_rows`.
- Current registry entries stay represented.
- Artifact-only rows remain visible by default.
- No-data and unresolved historical rows are preserved as evidence rows.

## Replay/Draw/Canonical Row Semantics

- replay_rows: Rows in strategy_prediction_replays; one replayed bet record per strategy/bet/draw row.
- draw_rows: Rows in draws; raw draw-table counts and source-of-truth for lottery history volume.
- canonical_rows: Filtered BIG_LOTTO research sample from draws_big_lotto_canonical_main.
- add_on_rows: BIG_LOTTO hyphenated add-on / special-prize records; raw-accessible and preserved.
- note: Replays, raw draws, canonical rows, and add-on rows must remain distinct in the dashboard.

## No-Overclaim Statement

BIG_LOTTO canonical randomness GREEN remains a data-quality confirmation only; it does not authorize a predictive edge. DAILY_539 remains rejected, POWER_LOTTO has no active deployable candidate, and 3_STAR/4_STAR have no current registry/replay entries.

## Future Implementation Candidates

- Wire this JSON into a future read-only API payload.
- Render lifecycle badges and filter chips without hiding historical rows.
- Add a stale snapshot banner next to the live registry SSOT indicator.

## Explicit Non-Actions

- No DB write
- No registry mutation
- No UI/API implementation
- No betting advice

## Compliance

- DB write: `NOT PERFORMED`
- DB migration: `NOT PERFORMED`
- CREATE VIEW / CREATE TABLE: `NOT PERFORMED`
- registry mutation: `NOT PERFORMED`
- strategy logic change: `NOT PERFORMED`
- UI/API implementation: `NOT PERFORMED`
- production recommendation change: `NOT PERFORMED`
- strategy promotion: `NOT PERFORMED`
- betting advice: `NOT PERFORMED`
- controlled_apply: `NOT PERFORMED`

Final Classification: `CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT`