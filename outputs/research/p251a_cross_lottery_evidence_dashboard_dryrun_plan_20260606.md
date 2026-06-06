# P251A — Cross-Lottery Evidence Dashboard Dry-Run Plan

**Date:** 2026-06-06 19:11:18  
**Task:** `P251A`  
**Classification:** `CROSS_LOTTERY_EVIDENCE_DASHBOARD_DRYRUN_PLAN`  

## Executive Summary

This is a read-only dashboard data-contract dry-run plan. It uses the published P250A inventory artifact as evidence and defines how a future dashboard should show current registry state, historical snapshot state, lifecycle badges, and replay/draw/canonical evidence without hiding historical entries.

## global_summary

- source_of_truth: `P250A inventory artifact (published on main)`
- current_registry_is_live_ssot: `True`
- historical_scoreboard_is_snapshot: `True`
- inventory_entries: `41`
- current_registry_entries: `38`
- artifact_only_entries: `3`
- replay_rows_total: `94924`
- draw_rows_total: `64361`
- canonical_big_lotto_rows: `2113`
- no_deployable_candidate: `True`
- no_prediction_edge_claim: `True`
- lifecycle_is_label_not_exclusion: `True`

## lottery_summary

### BIG_LOTTO

- cards_to_show: `13`
- replay_strategy_entries: `11`
- replay_rows: `24140`
- draw_rows: `22238`
- canonical_rows: `2113`
- distinct_replay_draws: `1552`
- visible_rows_by_default: `True`
- lifecycle_visibility_rule: `label/filter only; never exclusion`
- artifact_only_entries_visible: `False`
- note: replay rows are strategy_prediction_replays rows, not draw rows
- note: raw BIG_LOTTO draw rows remain 22,238; canonical main-draw rows are 2,113
- note: 19,100 add-on/special-prize rows stay raw-accessible and are excluded from canonical 6/49 research
- note: P249B fixes the replay-row vs draw-row label ambiguity

### DAILY_539

- cards_to_show: `16`
- replay_strategy_entries: `15`
- replay_rows: `34680`
- draw_rows: `5879`
- canonical_rows: `None`
- distinct_replay_draws: `1550`
- visible_rows_by_default: `True`
- lifecycle_visibility_rule: `label/filter only; never exclusion`
- artifact_only_entries_visible: `False`
- note: replay rows are strategy_prediction_replays rows, not draw rows
- note: no canonical/raw split currently tracked beyond the draw table count
- note: P230C closed the prior DAILY_539 survivor as rejected/historical artifact

### POWER_LOTTO

- cards_to_show: `12`
- replay_strategy_entries: `10`
- replay_rows: `36104`
- draw_rows: `1916`
- canonical_rows: `None`
- distinct_replay_draws: `1551`
- visible_rows_by_default: `True`
- lifecycle_visibility_rule: `label/filter only; never exclusion`
- artifact_only_entries_visible: `True`
- note: replay rows are strategy_prediction_replays rows, not draw rows
- note: three P47 artifact-only strategies remain in the historical inventory
- note: current registry has no active deployable candidate

## lifecycle_badge_vocabulary

- `ONLINE` → `active`: Currently active in the current registry; does not imply a betting edge.
- `REJECTED` → `rejected`: Evaluated and rejected; remains visible in historical replay views.
- `RETIRED` → `retired`: Formerly used, now retired; historical rows remain visible.
- `OBSERVATION` → `observation`: Shadow / observation-only; visible but non-promotional.
- `ARTIFACT_ONLY` → `artifact-only`: Evidence-only row or snapshot entry that should remain visible.
- `LIFECYCLE_UNRESOLVED` → `historical-snapshot`: Legacy snapshot state; use the live registry status alongside it.

## strategy_table_columns

- `strategy_id`
- `strategy_name`
- `lottery_type`
- `current_registry_lifecycle_status`
- `historical_snapshot_lifecycle_status`
- `latest_classification`
- `replay_presence`
- `replay_rows`
- `draw_rows`
- `canonical_rows`
- `artifact_only_flag`
- `evidence_state`
- `badge`
- `filter_tags`
- `source_artifacts`

## evidence_state_columns

- `current_registry_presence`
- `historical_scoreboard_presence`
- `current_registry_lifecycle_status`
- `historical_snapshot_lifecycle_status`
- `current_lifecycle_source`
- `catalog_source_snapshot`
- `replay_presence`
- `replay_rows`
- `distinct_target_draws`
- `draw_rows`
- `canonical_rows`
- `status_note`
- `latest_classification`
- `included_in_historical_replay_or_catalog_views`

## filter_semantics

- default_behavior: include all rows/cards by default; filters narrow the view but do not hide historical entries automatically
- lifecycle_filter: badge/filter only; never an exclusion rule
- registry_filter: can show current-registry-only rows, but should never erase historical snapshot rows unless user explicitly asks
- snapshot_filter: can reveal historical snapshot state side-by-side with current registry status
- lottery_filter: scope by lottery_type without changing visibility rules
- artifact_only_filter: must keep artifact-only rows visible by default and explicitly labeled

## no_exclusion_rules

- Do not exclude strategies because they are retired, rejected, offline, observation, unresolved, or artifact-only.
- Do not hide replay-backed historical rows when lifecycle is not ONLINE.
- Do not infer deployability from inventory presence, row counts, or historical classifications alone.
- Do not treat P232A as live state; it is a historical snapshot and must not replace the current registry SSOT.
- Do not hide BIG_LOTTO add-on / canonical split information; display it as evidence state.

## stale_snapshot_warning

- message: `P232A is a historical replay snapshot from 20260604 and is stale relative to the live registry SSOT published in P250A/P250B.`
- current_registry_ssot: `lottery_api/models/replay_strategy_registry.py`
- historical_snapshot: `outputs/research/p232a_all_catalog_strategy_replay_scoreboard_20260604.json`
- dashboard_behavior: `show both states together, with the current registry as primary and the snapshot as evidence context.`

## no_betting_advice_notice

- message: This dashboard is an evidence contract, not betting advice.
- No predictive edge is claimed.
- No strategy promotion is implied.
- No production recommendation is changed.
- GREEN canonical randomness remains a data-quality result, not a signal.
- Current inventory has no active deployable candidate.

## implementation_candidates_for_future

### 1. Cross-lottery evidence dashboard UI

- why: Render the contract as a registry-aware evidence table with badges and snapshot state.
- scope: Frontend only; no new prediction logic.

### 2. Evidence dashboard API payload

- why: Serve the same contract as a read-only JSON payload for UI and reports.
- scope: API contract only; no DB writes.

### 3. Badge legend and filter chips

- why: Make lifecycle visible without hiding historical rows.
- scope: Display layer only.

### 4. Stale snapshot banner

- why: Warn users that P232A is historical and the current registry is live SSOT.
- scope: Display layer only.

## preserved_p250a_conclusions

- current_registry_is_live_ssot: `True`
- p232a_scoreboard_is_historical_snapshot: `True`
- artifact_only_entries_must_remain_visible: `True`
- lifecycle_is_label_not_exclusion: `True`
- no_active_deployable_candidate: `True`

## compliance

- read_only: `True`
- no_db_write: `True`
- no_registry_mutation: `True`
- no_strategy_logic_change: `True`
- no_production_recommendation_change: `True`
- no_betting_advice: `True`

Final Classification: `CROSS_LOTTERY_EVIDENCE_DASHBOARD_DRYRUN_PLAN`