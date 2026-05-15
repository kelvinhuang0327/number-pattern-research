# P0 Strategy Historical Replay Product Plan — 2026-05-11

## 1. CTO Decision

The LotteryNew product priority is Strategy Historical Replay go-live.

The target user flow is:

1. Open the Strategy Historical Replay page.
2. Filter by lottery type, strategy lifecycle status, strategy, replay status, and date range.
3. Include every system-developed strategy that has a canonical lifecycle decision: `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, or `RETIRED`.
4. For each historical draw, show the strategy's historical prediction beside the actual draw result.
5. Keep the visual interaction aligned with the existing historical prediction list: dense table, pagination, details expansion, predictable filters.

This is an audit and traceability product surface. It must not execute strategy mining, must not perform lifecycle promotion, and must not treat replay metrics as a governance decision.

## 2. Current State

Already present:

- `index.html` has `#replay-section`, lifecycle filter, strategy filter, replay status filter, date filters, history table, pagination, and detail expansion.
- `lottery_api/routes/replay.py` exposes `/api/replay/strategies`, `/api/replay/history`, `/api/replay/summary`, `/api/replay/runs`, `/api/replay/freshness`.
- `lottery_api/models/replay_strategy_registry.py` supports canonical lifecycle values: `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED`.
- `tests/test_replay_api_contract.py` and replay browser tests already cover lifecycle filter behavior.
- PR #12 merged P0 replay product go-live infrastructure.

Known gap:

- Current data-health evidence shows replay rows only for `ONLINE`.
- `OFFLINE`, `REJECTED`, `OBSERVATION`, and `RETIRED` have honest empty states, but they do not yet have complete canonical catalog entries and replay rows.
- The page shell is close to the requested UX, but product completeness requires catalog/data population and non-empty validation for all lifecycle states.

## 3. Product Definition

The page is complete only when all of these are true:

- Every canonical strategy has a stable `strategy_id`, display name, lottery type, lifecycle status, version/source, and replay eligibility metadata.
- The strategy dropdown can list all canonical strategies, including non-`ONLINE` strategies.
- The history table can show rows for `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, and `RETIRED` when canonical replay rows exist.
- Each row displays:
  - target draw
  - target date
  - strategy name / id
  - lifecycle status
  - replay status
  - predicted numbers
  - actual numbers
  - hit numbers
  - hit count
  - detail row with run id, history cutoff, generated timestamp, and reject reason when applicable
- Empty states remain honest for lifecycle states that have catalog entries but no replay rows yet.
- `outputs/replay/` files remain evidence artifacts only, never runtime data sources.

## 4. Reordered P0-P10

| Priority | Focus | Decision | Acceptance Criteria |
|---|---|---|---|
| P0 | Product data completeness plan | Define how all developed strategies become canonical catalog rows without runtime writes | Inventory exists; lifecycle source/provenance recorded; missing data classified |
| P1 | Canonical strategy lifecycle catalog | Add or migrate a read-only catalog source for all lifecycle states | API `/strategies` returns non-empty entries for all approved lifecycle states; non-`ONLINE` entries are not generation eligible by default |
| P2 | Replay row backfill dry-run design | Plan how historical prediction-vs-actual rows will be generated or imported without writing production DB | dry-run manifest includes candidate counts, blocked reasons, source hashes, and no-write proof |
| P3 | Non-empty lifecycle fixture | Build fixture coverage for `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED` | API/browser tests prove the table renders non-empty rows for each lifecycle status |
| P4 | UI table parity | Align replay table with historical prediction list density and behavior | visible lifecycle/status columns, pagination, detail expansion, date and strategy filters pass browser smoke |
| P5 | Source-of-truth and provenance | Keep DB/catalog as runtime source; evidence artifacts remain evidence only | No API/UI reads from `outputs/replay/`; provenance fields available for catalog rows |
| P6 | Safety gates | Prevent accidental backfill/apply/DB writes while planning | no production DB write; no registry mutation unless explicitly in catalog PR; no active strategy state change |
| P7 | PR queue cleanup | Prevent stale docs PRs from blocking product work | #25 remains superseded by #26; #33/#34 remain unmerged unless explicit YES |
| P8 | Freshness and coverage reporting | Make product status transparent | `/freshness` reports coverage mode, stale status, legacy errors, and lifecycle filter consistently |
| P9 | Operational SOP update | Document how operators should read and troubleshoot the page | SOP explains catalog gaps, failed legacy rows, limited coverage, and no-write backfill flow |
| P10 | Real apply governance | Defer any production mutation to a separate approval phase | no real apply, no production DB write, no `runtime_write_allowed=true` in current product planning phase |

## 5. Immediate Implementation Plan

### P0-A — Strategy Inventory

Create a read-only inventory report that scans and classifies strategy sources:

- replay registry adapters
- strategy state JSON files
- rejected strategy archives
- strategy reports under `strategies/`
- prediction logs and replay rows
- existing P2 dry-run manifest rows

Output:

- `outputs/replay/p0_strategy_lifecycle_inventory_20260511.md`
- `outputs/replay/p0_strategy_lifecycle_inventory_20260511.json`

Each candidate must include:

- `strategy_id`
- display name
- lottery type
- lifecycle status
- source path
- source hash or provenance note
- replay row availability
- blocked reason if not catalog-ready

### P0-B — Catalog Contract

Define the canonical catalog contract before modifying runtime code:

- lifecycle enum
- generation eligibility flag
- replay display eligibility flag
- provenance fields
- last reviewed timestamp
- blocked reason / repair note

Output:

- `outputs/replay/p0_strategy_lifecycle_catalog_contract_20260511.md`

### P1-A — Runtime Catalog Implementation

After P0-A/P0-B are approved, implement one runtime catalog path:

- either extend `replay_strategy_registry.py` with display-only lifecycle entries, or
- add a small versioned catalog file loaded by replay routes, or
- add a DB-backed `strategy_lifecycle_catalog` only after migration approval.

Default recommendation:

- Use a versioned catalog file first for reviewability.
- Keep generation eligibility separate from display eligibility.
- Do not let `REJECTED`, `OFFLINE`, `OBSERVATION`, or `RETIRED` entries enter replay generation automatically.

### P2-A — Replay Row Population Plan

Plan the data path for missing lifecycle rows:

- existing replay rows remain source-of-truth.
- missing rows require a dry-run generator/report first.
- blocked rows stay blocked until source provenance and schema requirements are satisfied.
- no production DB write occurs in this phase.

### P3-A — Non-Empty Fixture and Tests

Add fixture-only tests that prove the requested UX:

- one row for each lifecycle status
- prediction-vs-actual columns visible
- lifecycle filter changes row set
- strategy dropdown includes non-`ONLINE` display-only entries
- detail row includes provenance/reject reason where relevant

## 6. Key Blockers

- **Catalog blocker:** the system does not yet have a complete canonical list of all developed strategies across lifecycle states.
- **Data blocker:** current replay store has non-empty rows only for `ONLINE`; other statuses are honest empty states.
- **Provenance blocker:** rejected/offline/observation candidates must not be invented from reports without source traceability.
- **Safety blocker:** real backfill/apply/production DB writes remain out of scope.
- **Queue blocker:** open docs PRs are piling up; PR #25 remains a mistaken-merge risk because it is superseded by PR #26.

## 7. What Not To Do

- Do not execute real backfill.
- Do not write production DB.
- Do not modify active strategy state.
- Do not run strategy mining.
- Do not use `outputs/replay/` as runtime source.
- Do not make non-`ONLINE` strategies generation eligible by accident.
- Do not merge PRs without explicit `YES`.
- Do not close PR #25 without explicit instruction.

## 8. Next Executable Prompt

```text
# ROLE
You are LotteryNew's Strategy Historical Replay Product Implementation Planner.

# MISSION
Create the strategy lifecycle inventory and catalog contract needed for the replay page to display all developed strategies across ONLINE, OFFLINE, REJECTED, OBSERVATION, and RETIRED states.

# STRICT RULES
- Do not execute backfill.
- Do not write DB.
- Do not write production DB.
- Do not modify active strategy state.
- Do not run strategy mining.
- Do not merge PRs.
- Do not treat outputs/replay evidence as runtime source.

# OUTPUTS
- outputs/replay/p0_strategy_lifecycle_inventory_20260511.md
- outputs/replay/p0_strategy_lifecycle_inventory_20260511.json
- outputs/replay/p0_strategy_lifecycle_catalog_contract_20260511.md

# ACCEPTANCE
- Inventory covers registry, strategy state files, rejected archives, strategies folder, prediction/replay rows, and P2 manifest candidates.
- Every candidate has lifecycle, source path, provenance, replay row availability, and blocked reason if incomplete.
- Catalog contract separates display eligibility from generation eligibility.
- No runtime code changes yet.

# FINAL MARKER
P0_STRATEGY_HISTORY_REPLAY_INVENTORY_AND_CATALOG_CONTRACT_READY
or
P0_STRATEGY_HISTORY_REPLAY_BLOCKED_<reason>
```

## 9. Final Marker

P0_STRATEGY_HISTORY_REPLAY_PRODUCT_PLAN_20260511_READY
