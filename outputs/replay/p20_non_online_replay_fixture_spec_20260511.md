# P20 Non-ONLINE Replay Fixture-Only Spec - 2026-05-11

## 1. Goal

Define a fixture-only replay spec for non-ONLINE lifecycle strategies.

This round is docs / governance / spec only:

- no DB writes
- no replay backfill
- no replay row generation into production history
- no scheduler or cron changes
- no strategy promotion, retirement, or reactivation actions
- no runtime code, dashboard, endpoint, registry adapter, package, or config changes

## 2. Main State

- `main` HEAD: `ce85c2d`
- latest commit message: `docs(replay): record P19 replay product follow-up decision (#49)`

## 3. Artifact Verification

Prerequisite artifacts are present on main:

- `outputs/replay/p17_strategy_history_replay_product_roadmap_20260511.md`
- `outputs/replay/p18_replay_product_gap_inventory_20260511.md`
- `outputs/replay/p19_replay_product_follow_up_20260511.md`

P19 markers confirmed in the follow-up report:

- `P19_REPLAY_PRODUCT_FOLLOW_UP_REVIEWED`
- `P19_NON_ONLINE_HISTORY_GAP_CONFIRMED`
- `P19_FIXTURE_ONLY_NEXT_STEP_RECOMMENDED`
- `P19_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P19_NO_PROMOTION_ACTION_CONFIRMED`

Artifact verification result: PASS.

## 4. Lifecycle Metadata Summary

Read-only inventory confirms the registry state:

- total strategies: 16
- ONLINE: 6
- REJECTED: 4
- OBSERVATION: 1
- RETIRED: 5
- OFFLINE: 0

Executable strategies are only the 6 ONLINE entries:

- `biglotto_deviation_2bet`
- `biglotto_triple_strike`
- `daily539_f4cold`
- `daily539_markov_cold`
- `power_orthogonal_5bet`
- `power_precision_3bet`

Non-executable strategies are the remaining 10 entries:

- REJECTED: `biglotto_ts3_acb_4bet`, `biglotto_ts3_markov_freq_5bet`, `power_shlc_midfreq`, `p1_deviation_2bet_539`
- RETIRED: `acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet`
- OBSERVATION: `h6_gate_mk20_ew85`

## 5. Non-ONLINE Gap Summary

Replay history is still ONLINE-only.

Observed gap:

- 460 replay rows total
- PREDICTED: 420
- REPLAY_ERROR: 40
- 10 non-ONLINE strategies still have 0 replay rows

That means the current product gap is not a metadata gap. Metadata is complete enough to identify the gap honestly; replay coverage is still missing for non-ONLINE strategies.

## 6. Fixture-Only Goal

The purpose of this P20 spec is to define a safe bridge for tests, docs, and staging evidence.

Fixture rows should let UI / tests show replay-history-like records for REJECTED, RETIRED, and OBSERVATION strategies without implying that production replay history has been backfilled.

This is representation only. It is not application of production truth.

## 7. Fixture Scope

Eligible lifecycle scope:

- REJECTED: 4 strategies
- RETIRED: 5 strategies
- OBSERVATION: 1 strategy

Excluded from fixture generation:

- OFFLINE: 0 strategies, so no fixture rows

The fixture scope is exactly the 10 non-ONLINE strategies already listed above.

## 8. Proposed Fixture Row Contract

Each fixture row should carry explicit provenance and anti-misuse fields.

| Field | Purpose |
|---|---|
| `strategy_id` | Identify the lifecycle strategy |
| `lottery_type` | Preserve the source lottery family |
| `lifecycle_status` | Preserve the original lifecycle state |
| `draw_id` / `draw_date` | Anchor the fixture row to a deterministic draw context |
| `predicted_numbers` or `prediction_payload` | Capture the synthetic prediction side |
| `actual_numbers` or `draw_result_payload` | Capture the comparison side |
| `hit_count` / `comparison_result` | Summarize the deterministic comparison outcome |
| `synthetic_only` | Hard flag that this is not production history |
| `fixture_only` | Hard flag that this exists only for fixture use |
| `fixture_version` | Version the fixture contract |
| `fixture_source` | Use `non_online_lifecycle_fixture` |
| `generated_at` | Record generation timestamp |
| `governance_marker` | Record the no-write governance decision |

Required invariants:

- `synthetic_only = true`
- `fixture_only = true`
- `fixture_source = non_online_lifecycle_fixture`
- lifecycle status must not change
- fixture rows must never be mixed with production replay_history rows
- fixture rows must not imply strategy edge, promotion, or reactivation

## 9. Deterministic Generation Policy

The fixture design must be reproducible and isolated:

- deterministic
- seeded
- reproducible
- no external API calls
- no production writes
- no scheduler dependencies
- no real strategy mining
- no implicit backfill

Recommended generation model:

- use a fixed seed per strategy_id and draw anchor
- derive fixture payloads from the seed only
- keep generation logic in isolated output artifacts or test helpers
- keep production replay history untouched

## 10. UI / Dashboard Expectation

Fixture mode may show rows for REJECTED, RETIRED, and OBSERVATION strategies.

Production mode must remain honest:

- empty for non-ONLINE replay history until a separately approved path exists
- clearly labeled so fixture rows are visibly synthetic
- no suggestion that fixture rows equal canonical production replay history

The dashboard should label fixture rows clearly enough that users cannot confuse them with real replay execution evidence.

## 11. Test Plan

Required coverage for the P20 direction:

- fixture generation dry-run test
- no DB write spy
- no production DB file mutation test
- UI fixture-mode smoke
- lifecycle status preserved test
- no promotion action test

Suggested test assertions:

- fixture output contains `synthetic_only` and `fixture_only`
- no sqlite write path is invoked
- production DB path remains untouched
- non-ONLINE lifecycle status remains unchanged
- no scheduler or promotion code path appears

## 12. Stop Rules

Stop immediately if any of the following occurs:

- DB write occurs
- production DB path is touched
- lifecycle status changes
- scheduler or promotion path appears
- fixture rows lack the synthetic flag
- fixture rows are presented as production replay history

## 13. No-Write Evidence

Read-only evidence used for this round:

- `git checkout main` and `git pull --ff-only`
- artifact existence checks for P17, P18, and P19
- P19 marker verification
- `scripts/report_strategy_lifecycle_registry.py --json`
- direct read-only Python summary of the registry

The registry CLI reports:

- `no_db_write: true`
- `no_db_write_note: All data sourced from in-memory registry. No sqlite3 connection opened. No file written (unless --output specified). No replay execution performed.`

## 14. No-Backfill Evidence

No backfill was run in this round.

The observed gap still exists:

- 10 non-ONLINE strategies have 0 replay rows
- replay history remains ONLINE-only
- the registry and inventory are already sufficient to expose the gap honestly

That means the next step remains a spec-only bridge, not a production mutation.

## 15. No-Promotion Evidence

No promotion, retirement, reactivation, or strategy action was performed.

The fixture contract must not:

- promote a strategy into ONLINE
- imply a strategy has earned edge
- imply lifecycle metadata changed
- trigger scheduler or replay execution behavior

## 16. Risks and Limitations

- OFFLINE remains unpopulated, so the taxonomy still has a visible zero-state.
- A fixture-only design can support evidence and UI development, but it cannot close the production gap by itself.
- The boundary between fixture representation and production replay history must stay explicit.
- If P20 bleeds into a real backfill path, it will violate the governance contract established in P18 and P19.

## 17. P21 Recommendation

P21 should implement the fixture generator in an isolated output-only path:

- output JSON or CSV fixture only
- no SQLite write
- no production DB write
- no runtime endpoint change unless separately approved
- no dashboard mutation unless separately approved
- no strategy promotion

The recommended direction is to keep the first implementation purely in fixture artifacts and tests, then decide later whether any read-only UI integration is warranted.

## 18. Final Markers

- `P20_NON_ONLINE_FIXTURE_SPEC_REVIEWED`
- `P20_NON_ONLINE_STRATEGY_SCOPE_CONFIRMED`
- `P20_FIXTURE_ONLY_NO_WRITE_CONTRACT_DEFINED`
- `P20_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P20_NO_PROMOTION_ACTION_CONFIRMED`
