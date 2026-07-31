# P251C — Evidence Dashboard API Payload Contract Plan

**Date:** 2026-06-06 19:30:48  
**Task:** `P251C`  
**Classification:** `EVIDENCE_DASHBOARD_API_PAYLOAD_CONTRACT_PLAN`  

## Executive Summary

This artifact defines the future-only read-only API payload contract that could serve the P251B evidence dashboard data to a UI later. It intentionally does not implement the route, UI, DB writes, registry changes, or strategy changes.

## Source Artifacts

- p250a_inventory: `outputs/research/p250a_cross_lottery_strategy_replay_inventory_20260606.json`
- p251a_contract: `outputs/research/p251a_cross_lottery_evidence_dashboard_dryrun_plan_20260606.json`
- p251b_dashboard_data: `outputs/research/p251b_cross_lottery_evidence_dashboard_data_20260606.json`
- current_state: `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
- active_task: `00-Plan/roadmap/active_task.md`

## Existing Route Convention Scan

- n/a /api/replay/* from `lottery_api/app.py`
  - read-only audit namespace
  - Replay router is mounted as a read-only audit family.
- GET /api/replay/strategies from `lottery_api/routes/replay.py`
  - strategy catalog / visibility list
  - List strategies with lifecycle filters; closest naming pattern for dashboard payloads.
- GET /api/replay/history from `lottery_api/routes/replay.py`
  - paged audit history
  - Supports page/page_size and lifecycle filters; proves existing query conventions.
- GET /api/replay/freshness from `lottery_api/routes/replay.py`
  - freshness / coverage advisory
  - Useful precedent for staleness and coverage banners in a read-only dashboard.
- GET /api/replay/strategy-catalog from `lottery_api/routes/replay.py`
  - read-only strategy catalog
  - Existing read-only catalog endpoint; strong convention match for future payloads.
- GET /api/best-strategy-overview from `lottery_api/routes/best_strategy_overview.py`
  - artifact-backed ranking cards
  - Shows the repo already uses artifact-backed read-only payload endpoints.
- GET /api/best-strategy-overview/meta/available-artifacts from `lottery_api/routes/best_strategy_overview.py`
  - artifact discovery metadata
  - Useful precedent for source_artifacts metadata without mutating state.
- GET /api/data/draws from `lottery_api/routes/data.py`
  - paged query with filters
  - General page/page_size pattern used elsewhere in the API.

## Proposed Future Endpoint

- Path: `/api/replay/evidence-dashboard`
- Method: `GET`
- Future only: `True`
- Namespace: `/api/replay/*`
- Reasoning: Matches the existing replay audit namespace and keeps the payload read-only and dashboard-focused.

## Response Schema

- schema_version
- task_id
- classification
- generated_at
- source_artifacts
- proposed_endpoint
- http_method
- route_convention_scan
- response_schema
- payload_field_contract
- lottery_card_schema
- strategy_row_schema
- lifecycle_filter_schema
- evidence_state_schema
- filter_sort_pagination_contract
- cache_and_staleness_policy
- validation_rules
- implementation_steps_future_only
- no_implementation_confirmed
- forbidden_actions_confirmed
- final_decision
- global_summary
- lottery_cards
- strategy_rows
- lifecycle_filter_options
- lifecycle_badge_vocabulary
- replay_coverage_summary
- draw_count_semantics
- evidence_state_summary
- stale_snapshot_warning
- no_exclusion_rules
- default_filter_state
- no_betting_advice_notice
- implementation_readiness

## Field Contract

### global_summary

- purpose: Top-level evidence summary carried forward from P251B.
- must_include: current_registry_entries
- must_include: historical_inventory_entries
- must_include: artifact_only_entries
- must_include: replay_rows_total
- must_include: draw_rows_total
- must_include: big_lotto_raw_draw_rows
- must_include: big_lotto_canonical_rows
- must_include: big_lotto_add_on_rows
- must_include: no_deployable_candidate
- must_include: no_prediction_edge_claim
- must_include: lifecycle_is_label_not_exclusion

### lottery_cards

- purpose: Per-lottery summary cards for BIG_LOTTO, DAILY_539, and POWER_LOTTO.
- must_include: lottery_type
- must_include: card_title
- must_include: strategy_cards_visible
- must_include: replay_strategy_entries
- must_include: replay_rows
- must_include: draw_rows
- must_include: canonical_rows
- must_include: artifact_only_rows_visible
- must_include: visible_by_default
- must_include: lifecycle_visibility_rule
- must_include: summary_notes

### strategy_rows

- purpose: Full visible inventory rows from P251B, including artifact-only evidence rows.
- must_include: strategy_id
- must_include: strategy_name
- must_include: lottery_type
- must_include: current_registry_lifecycle_status
- must_include: historical_snapshot_lifecycle_status
- must_include: latest_classification
- must_include: replay_presence
- must_include: replay_rows
- must_include: lottery_replay_rows
- must_include: lottery_draw_rows
- must_include: lottery_canonical_rows
- must_include: artifact_only_flag
- must_include: visible_by_default
- must_include: evidence_state
- must_include: badge
- must_include: filter_tags
- must_include: source_artifacts
- must_include: row_visibility

### lifecycle_filter_options

- purpose: Filter chips / badges that narrow the view without excluding historical rows by default.
- default_behavior: include all lifecycle statuses
- statuses: ONLINE, REJECTED, RETIRED, OBSERVATION, ARTIFACT_ONLY, LIFECYCLE_UNRESOLVED

### evidence_state

- purpose: Explicitly state live SSOT versus historical snapshot semantics.
- must_include: current_registry_is_live_ssot
- must_include: historical_scoreboard_is_snapshot
- must_include: artifact_only_visible_by_default
- must_include: lifecycle_never_excludes_historical_rows
- must_include: no_active_deployable_candidate
- must_include: no_prediction_edge_claim

### stale_snapshot_warning

- purpose: Warn that P232A/P251A historical evidence is stale relative to live registry SSOT.
- must_include: message
- must_include: current_registry_ssot
- must_include: historical_snapshot
- must_include: dashboard_behavior

### no_betting_advice_notice

- purpose: Prevent prediction or betting interpretation of the payload.
- must_include: message
- must_include: no_claims

## Filter/Sort/Pagination Behavior

- filters: {'lottery_type': 'optional string or multi-select (BIG_LOTTO, DAILY_539, POWER_LOTTO)', 'lifecycle_status': 'optional multi-select; default includes all statuses', 'artifact_only': 'optional tri-state; default includes visible artifact-only rows', 'visible_only': 'optional bool; default true for dashboard render'}
- sorting: {'default_sort': ['lottery_type', 'current_registry_lifecycle_status', 'strategy_id'], 'allowed_sort_keys': ['lottery_type', 'current_registry_lifecycle_status', 'historical_snapshot_lifecycle_status', 'strategy_id', 'strategy_name', 'replay_rows', 'draw_rows', 'canonical_rows'], 'allowed_sort_orders': ['asc', 'desc']}
- pagination: {'supports_pagination': True, 'default_page': 1, 'default_page_size': 50, 'max_page_size': 200, 'proposal_note': 'Pagination should be optional because the dashboard defaults to visible all-row evidence rendering.'}
- filtering_notes: ['Filtering narrows the view; it does not change lifecycle truth or hide evidence by default.', 'No filter should imply deployability or betting advice.']

## Validation Rules

- JSON must parse successfully.
- classification must equal EVIDENCE_DASHBOARD_API_PAYLOAD_CONTRACT_PLAN.
- proposed_endpoint must be future-only and remain unimplemented in P251C.
- response_schema must include global_summary, lottery_cards, strategy_rows, lifecycle_filter_options, no_exclusion_rules, and no_betting_advice_notice.
- strategy_rows validation must require at least 41 visible rows (41).
- Artifact-only rows must remain visible by default.
- Default lifecycle filter must include all statuses and must not exclude historical rows.
- BIG_LOTTO replay/draw/canonical/add-on semantics must remain separated.
- No DB write, registry mutation, strategy promotion, betting advice, or UI/API implementation may be claimed by the contract.

## No-Overclaim / No-Betting Notice

- No API route is implemented in P251C.
- No UI is implemented in P251C.
- No DB write, no registry mutation, no strategy promotion.
- No betting advice.

## Future Implementation Steps

- Define a FastAPI response model matching this contract in a future task.
- Add a future read-only endpoint under /api/replay/* that serializes the dashboard payload.
- Add route-level tests that enforce lifecycle visibility and no-exclusion defaults.
- Wire a UI consumer only after the API payload exists and remains read-only.
- Keep DB, registry, and strategy logic unchanged until a separate authorization is issued.

## Explicit Non-Actions

- DB write: `NOT PERFORMED`
- DB migration: `NOT PERFORMED`
- CREATE VIEW / CREATE TABLE: `NOT PERFORMED`
- registry mutation: `NOT PERFORMED`
- strategy logic change: `NOT PERFORMED`
- strategy promotion: `NOT PERFORMED`
- UI/API implementation: `NOT PERFORMED`
- production recommendation change: `NOT PERFORMED`
- betting advice: `NOT PERFORMED`
- controlled_apply: `NOT PERFORMED`

Final Classification: `EVIDENCE_DASHBOARD_API_PAYLOAD_CONTRACT_PLAN`