# P251D — Evidence Dashboard Read-only API Route

**Date:** 2026-06-08 13:01:45  
**Task:** `P251D`  
**Classification:** `EVIDENCE_DASHBOARD_READONLY_API_ROUTE_IMPLEMENTED`  

## Executive Summary

P251D implements the read-only replay endpoint `/api/replay/evidence-dashboard` and serves the published P251B dashboard artifact directly, following the P251C contract path and preserving all no-overclaim semantics.

## Source Artifacts

- p251b_dashboard_data: `outputs/research/p251b_cross_lottery_evidence_dashboard_data_20260606.json`
- p251c_contract_plan: `outputs/research/p251c_evidence_dashboard_api_payload_contract_plan_20260606.json`

## Existing Route Convention Scan

- route_file: `lottery_api/routes/replay.py`
- existing_replay_namespace: `/api/replay/*`
- implemented_endpoint_present: `True`
- strategy_catalog_present: `True`
- freshness_present: `True`
- artifact_loader_present: `True`
- forbidden_imports_present: `[]`

## Implemented Endpoint

- path: `/api/replay/evidence-dashboard`
- http_method: `GET`
- route_file: `lottery_api/routes/replay.py`
- artifact_backed: `True`
- db_query_performed: `False`

## Response Payload Summary

- task_id: `P251B`
- classification: `CROSS_LOTTERY_EVIDENCE_DASHBOARD_DATA_ARTIFACT`
- strategy_rows_len: `41`
- artifact_only_visible_count: `3`
- default_lifecycle_statuses: `['ONLINE', 'REJECTED', 'RETIRED', 'OBSERVATION', 'ARTIFACT_ONLY', 'LIFECYCLE_UNRESOLVED']`
- exclude_by_lifecycle: `False`
- big_lotto_replay_rows: `24140`
- big_lotto_draw_rows: `22238`
- big_lotto_canonical_rows: `2113`
- big_lotto_add_on_rows: `19100`
- no_deployable_candidate: `True`
- no_betting_advice_notice_present: `True`
- contract_path_matches_p251c: `True`

## P251B Semantic Preservation

- Strategy rows remain >= 41 and artifact-only rows remain visible.
- Lifecycle remains badge/filter only and does not exclude by default.
- BIG_LOTTO replay/raw/canonical/add-on counts remain separated.

## No-Overclaim / No-Betting Notice

- No DB write
- No registry mutation
- No strategy promotion
- No UI implementation
- No betting advice

## Files Changed

- `lottery_api/routes/replay.py`
- `analysis/p251d_evidence_dashboard_readonly_api_route.py`
- `outputs/research/p251d_evidence_dashboard_readonly_api_route_20260606.json`
- `outputs/research/p251d_evidence_dashboard_readonly_api_route_20260606.md`
- `tests/test_p251d_evidence_dashboard_readonly_api_route.py`

## Tests

- targeted_route_tests: `tests/test_p251d_evidence_dashboard_readonly_api_route.py`
- p251c_regression: `tests/test_p251c_evidence_dashboard_api_payload_contract_plan.py`
- p251b_regression: `tests/test_p251b_cross_lottery_evidence_dashboard_data_builder.py`

## Explicit Non-Actions

- Did not query or write the database for this endpoint.
- Did not mutate registry or strategy logic.
- Did not implement frontend/UI.
- Did not generate predictions or betting advice.

Final Classification: `EVIDENCE_DASHBOARD_READONLY_API_ROUTE_IMPLEMENTED`