# P17 Strategy Historical Replay Product Roadmap — 2026-05-11

## 1. CTO Decision

The next product direction must return from lifecycle dashboard closure to Strategy Historical Replay completion.

The requested product is not only a lifecycle dashboard. The user-facing goal is:

- show all system-developed strategies across lifecycle states;
- allow filters for `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED`;
- for each historical draw, show the strategy prediction beside the actual draw result;
- keep the UI shape aligned with the existing historical prediction list.

Current conclusion:

- Lifecycle metadata/dashboard work is effectively closed after P16, pending PR #46 merge approval.
- Strategy Historical Replay product is only partially complete because replay history rows exist only for current executable `ONLINE` strategies.
- The next engineering focus should be a no-write product gap closure plan that bridges lifecycle metadata to replay history rows without writing production DB or running uncontrolled backfill.

## 2. Current Verified State

Verified from current branch and GitHub on 2026-05-11:

- PR #46 is open, mergeable, `mergeStateStatus=CLEAN`.
- PR #46 diff scope is docs-only:
  - `outputs/replay/p16_lifecycle_dashboard_closure_summary_20260511.md`
- PR #46 checks:
  - `replay-default-validation`: pass
  - `replay-browser-e2e-validation`: pass
  - `replay-dedicated-db-validation`: skipped
- PR #46 was not merged because no explicit user `YES` was provided.

Lifecycle metadata CLI smoke:

```json
{
  "ONLINE": 6,
  "REJECTED": 4,
  "OBSERVATION": 1,
  "RETIRED": 5,
  "total": 16
}
```

Replay DB row state:

```text
strategy_prediction_replays total rows: 460
PREDICTED rows: 420
REPLAY_ERROR rows: 40
strategy ids with replay rows:
- daily539_f4cold: 90
- daily539_markov_cold: 90
- biglotto_deviation_2bet: 70
- biglotto_triple_strike: 70
- power_orthogonal_5bet: 70
- power_precision_3bet: 70
```

Product implication:

- `ONLINE` replay history is populated.
- `REJECTED`, `OBSERVATION`, and `RETIRED` strategies are visible in lifecycle metadata but do not yet have replay history rows.
- `OFFLINE` has no canonical strategy entry yet.

## 3. Roadmap Alignment Assessment

Aligned:

- P6/P9/P10/P11/P12/P13/P14/P15/P16 lifecycle dashboard closure artifacts are present and consistent.
- P15 marker split is acceptable as semantic equivalent via P16.
- Read-only lifecycle endpoint/dashboard validation is strong: targeted lifecycle tests passed in the handoff, and PR #46 checks are clean.
- The no-write/no-backfill/no-promotion discipline remains correct.

Misaligned or incomplete:

- Dashboard closure does not equal full historical replay product completion.
- Lifecycle metadata completeness does not imply replay row completeness.
- The current replay history table can render prediction-vs-actual rows, but only where `strategy_prediction_replays` rows exist.
- Current roadmap language risks over-claiming "all strategies" unless it distinguishes metadata visibility from replay row availability.
- `OFFLINE` is part of the requested lifecycle filter set, but currently has zero canonical entries.

## 4. Reordered P0-P10

| Priority | Focus | Decision | Acceptance Criteria |
|---|---|---|---|
| P0 | PR #46 YES-gated closure | PR #46 is ready but must not merge without explicit YES | diff is P16 docs-only; checks pass/skipped as expected; no DB/backfill/promotion |
| P1 | Replay product gap inventory | Inventory lifecycle metadata versus replay rows | 16 lifecycle strategies mapped to replay row availability; OFFLINE gap explicitly classified |
| P2 | Non-ONLINE replay row policy | Decide how REJECTED/OBSERVATION/RETIRED histories should appear | dry-run-only policy defines generated, imported, unavailable, or evidence-only rows |
| P3 | Catalog-to-history bridge design | Connect lifecycle metadata to replay history UX without overclaiming | API can show strategy metadata even when replay rows are absent; UI labels missing history honestly |
| P4 | No-write replay row dry-run | Produce dry-run manifest for missing lifecycle replay rows | candidate counts, blocked reasons, provenance, DB hash unchanged |
| P5 | Fixture coverage for all lifecycle states | Prove UI table can render rows for every lifecycle status | fixture has `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED` history rows; browser/static tests pass |
| P6 | Actual row population gate | Defer real row population until dry-run and approval | no production DB write; no real apply; no `runtime_write_allowed=true` |
| P7 | httpx live smoke decision | Decide whether to add HTTP transport smoke | either add declared dependency + live smoke or record formal deferral |
| P8 | Local runtime dirt cleanup | Isolate local workspace hygiene from product PRs | `data/lottery_v2.db` and P2 manifest dirt handled only by explicit cleanup task |
| P9 | Replay SOP update | Document operator reading of metadata vs row availability | SOP explains lifecycle metadata, replay rows, missing-history states, failed legacy rows |
| P10 | Real backfill governance | Keep production mutation as separate future gate | no scheduler activation, no strategy promotion, no uncontrolled replay generation |

## 5. Key Blockers

- **Approval blocker:** PR #46 cannot be merged until explicit `YES`.
- **Replay row blocker:** only 6 `ONLINE` strategy IDs currently have replay history rows.
- **OFFLINE blocker:** the requested lifecycle includes `OFFLINE`, but the current canonical lifecycle metadata has no OFFLINE strategy.
- **Policy blocker:** non-ONLINE strategies need a formal rule: display-only metadata, dry-run-generated history, imported historical evidence, or unavailable with honest reason.
- **Safety blocker:** row population must not skip the no-write dry-run gate.
- **Dependency blocker:** live HTTP smoke remains deferred because `httpx` is not installed/declared.
- **Workspace blocker:** local runtime dirt exists and can confuse status reads if not isolated.

## 6. Most Valuable Next Engineering Step

After PR #46 is merged with explicit YES, the next substantive product task is:

```text
P17-A Replay Product Gap Inventory
```

This task should produce:

- `outputs/replay/p17_strategy_replay_gap_inventory_20260511.md`
- `outputs/replay/p17_strategy_replay_gap_inventory_20260511.json`

The inventory must join:

- lifecycle registry metadata;
- replay DB strategy row counts;
- replay statuses;
- lifecycle status;
- executable versus display-only status;
- source/provenance;
- missing-history reason.

It must answer:

1. Which strategies appear in lifecycle dashboard?
2. Which strategies appear in replay history rows?
3. Which strategies have no replay rows?
4. Which lifecycle states are missing entirely?
5. Which missing rows can be dry-run generated later?
6. Which missing rows should remain unavailable because source/provenance is insufficient?

## 7. Stop Rules

- Do not merge PR #46 without explicit YES.
- Do not write DB.
- Do not run replay backfill.
- Do not run strategy mining.
- Do not add strategy promotion/retirement actions.
- Do not modify active strategy state.
- Do not modify dashboard or endpoint in this roadmap step.
- Do not commit local runtime dirt.
- Do not claim full replay product completion until non-ONLINE replay row availability is resolved.

## 8. Next Executable Prompt

```text
# ROLE
You are LotteryNew's P17 Replay Product Gap Inventory Agent.

# MISSION
Create a no-write inventory that compares lifecycle dashboard strategies against replay history row availability. The goal is to identify exactly what remains before the Strategy Historical Replay page can show all developed strategies across ONLINE/OFFLINE/REJECTED/OBSERVATION/RETIRED with prediction-vs-actual rows.

# STRICT RULES
- Do not write DB.
- Do not run replay backfill.
- Do not run strategy mining.
- Do not modify runtime code.
- Do not modify dashboard.
- Do not modify endpoint.
- Do not modify active strategy state.
- Do not merge PRs.
- Do not commit data/lottery_v2.db.
- Do not commit outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json.

# REQUIRED INPUTS
- scripts/report_strategy_lifecycle_registry.py --json
- lottery_api/data/lottery_v2.db read-only queries:
  - strategy_prediction_replays by strategy_id and replay_status
  - strategy_replay_runs by status
- docs/replay/strategy_lifecycle_endpoint_contract.md
- outputs/replay/p16_lifecycle_dashboard_closure_summary_20260511.md if PR #46 is merged, otherwise PR #46 diff

# OUTPUTS
- outputs/replay/p17_strategy_replay_gap_inventory_20260511.md
- outputs/replay/p17_strategy_replay_gap_inventory_20260511.json

# ACCEPTANCE
- Inventory lists all lifecycle strategies.
- Inventory lists replay row counts by strategy.
- Inventory marks ONLINE/REJECTED/OBSERVATION/RETIRED/OFFLINE coverage.
- Missing rows have blocked reason or dry-run candidate status.
- No DB writes, no backfill, no promotion action.

# FINAL MARKER
P17_STRATEGY_REPLAY_GAP_INVENTORY_READY
or
P17_STRATEGY_REPLAY_GAP_INVENTORY_BLOCKED_<reason>
```

## 9. Final Marker

P17_STRATEGY_HISTORY_REPLAY_PRODUCT_ROADMAP_READY
