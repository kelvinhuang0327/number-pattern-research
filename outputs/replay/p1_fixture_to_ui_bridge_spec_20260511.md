# P1 Fixture-to-UI Bridge Spec - 2026-05-11

## 1. Problem Definition

Current UI behavior:

- the dashboard reads replay history rows from `strategy_prediction_replays`
- fixture artifact exists at `outputs/replay/non_online_replay_fixture_20260511.json`
- the artifact covers 10 non-ONLINE strategies
- UI cannot read those records today, so REJECTED / RETIRED / OBSERVATION views stay empty

Consequence:

- switching the UI to non-ONLINE lifecycle states produces empty history even though fixture data exists
- the fixture is visible as an output artifact, but not bridged into the UI read path

This spec defines the smallest safe bridge for fixture mode only.

## 2. Candidate Paths

### a) Endpoint-level fixture mode

Add `?fixture_mode=true` to `/api/replay/history` and let the endpoint return JSON fixture-backed records instead of DB-backed rows.

Pros:

- no DB mutation
- explicit toggle boundary
- easiest to isolate and remove
- safest for browser smoke tests

Cons:

- two response paths must be maintained
- must carry an advisory label to prevent accidental production-style use

### b) Read-only catalog merge

Read DB rows first, then fill any non-ONLINE lifecycle gaps from the JSON artifact when the DB has no row for that strategy.

Pros:

- UI does not need a separate mode toggle
- existing callers keep the same route

Cons:

- introduces fallback logic into the normal read path
- harder to reason about provenance
- easier to contaminate production-style behavior

### c) In-memory fixture loader at startup

Load the JSON artifact into memory at app boot and expose it through a read-only adapter.

Pros:

- keeps DB untouched
- keeps API surface stable

Cons:

- JSON changes require restart
- fixture mode becomes less explicit
- runtime state is more coupled to process lifecycle

## 3. CTO Recommendation

Recommended path: a) Endpoint-level fixture mode

Rationale:

- boundary is explicit through a query parameter
- production DB read path stays clean
- browser smoke testing is straightforward
- the feature is easy to disable or remove later
- advisory-only labeling is natural at the endpoint boundary

## 4. Bridge UI Labels

Any `fixture_mode=true` response must include:

- `source`: `synthetic_fixture`
- `advisory_only`: `true`
- `production_db_write`: `false`

UI must show the following banner or equivalent copy:

- `⚠ FIXTURE MODE — 合成資料、僅供驗收，不代表真實預測`

## 5. Acceptance

All fixture-mode responses remain read-only and must not change registry state.

Required GET examples:

1. `GET /api/replay/history?lifecycle_status=REJECTED&fixture_mode=true`
   - returns 4 strategy records
   - response includes `source=synthetic_fixture`
   - response includes `advisory_only=true`
   - response includes `production_db_write=false`

2. `GET /api/replay/history?lifecycle_status=RETIRED&fixture_mode=true`
   - returns 5 strategy records
   - response includes `source=synthetic_fixture`
   - response includes `advisory_only=true`
   - response includes `production_db_write=false`

3. `GET /api/replay/history?lifecycle_status=OBSERVATION&fixture_mode=true`
   - returns 1 strategy record
   - response includes `source=synthetic_fixture`
   - response includes `advisory_only=true`
   - response includes `production_db_write=false`

4. `GET /api/replay/history?lifecycle_status=REJECTED`
   - default `fixture_mode=false`
   - behavior remains unchanged from the current DB-backed path
   - no synthetic labels are injected

5. `GET /api/replay/history?fixture_mode=true`
   - returns fixture-backed history according to the requested lifecycle scope or default view behavior
   - every response carries `advisory_only=true`
   - every response carries `source=synthetic_fixture`
   - no DB write occurs

Additional acceptance rules:

- `fixture_mode` defaults to `false`
- the response must never write to DB
- the response must never alter registry state
- the response must never imply promotion, retirement, or active-state changes

## 6. Not in Scope

Explicitly out of scope for this spec:

- production DB backfill
- strategy promotion
- scheduler or cron changes
- active strategy state changes
- registry expansion or adapter changes
- strategy mining or edge discovery
- any write into `data/lottery_v2.db`

## 7. Final Marker

- `P1_FIXTURE_TO_UI_BRIDGE_SPEC_READY`
