# P1 Catalog Visibility Registry Expansion Report (2026-05-18)

## Final Classification

**P1_CATALOG_VISIBILITY_PLAN_COMPLETED + APPLY_COMPLETED**

## P0 Baseline (unchanged throughout)

| Check | Status |
|-------|--------|
| API contract tests | 44/44 PASS |
| Drift guard (pre) | PASS |
| Drift guard (post) | PASS |
| Runtime canonical strategies | 18 |

## Catalog Expansion Plan

| Metric | Value |
|--------|-------|
| Runtime canonical (before) | 18 |
| Artifact candidates found | 71 |
| Planned new registry entries | 71 |
| Planned NO_DATA entries | 83 |
| Skipped (bogus/unsafe) | 4 |
| Total entries in P1 catalog | 89 |

## DB After Apply

| lifecycle_state | catalog_visibility_state | count |
|-----------------|--------------------------|-------|
| ONLINE | REGISTERED_WITH_REPLAY_ROWS | 6 |
| ONLINE | REGISTERED_NO_DATA | 2 |
| REJECTED | ARTIFACT_CANDIDATE | 71 |
| REJECTED | REGISTERED_NO_DATA | 4 |
| RETIRED | REGISTERED_NO_DATA | 5 |
| OBSERVATION | REGISTERED_NO_DATA | 1 |

## Lifecycle Handling

- **ONLINE (8)**: 6 have replay rows (REGISTERED_WITH_REPLAY_ROWS), 2 have no rows yet (REGISTERED_NO_DATA)
- **REJECTED (75)**: 4 in code registry (REGISTERED_NO_DATA), 71 artifact-only (ARTIFACT_CANDIDATE)
- **RETIRED (5)**: all REGISTERED_NO_DATA (in code registry, no backfill yet)
- **OBSERVATION (1)**: REGISTERED_NO_DATA
- **ARTIFACT_ONLY**: all mapped to ARTIFACT_CANDIDATE visibility

## Apply Status

| Item | Value |
|------|-------|
| Mode | APPLY (--apply flag) |
| Backup path | `lottery_api/data/backups/lottery_v2_pre_p1_20260518T081805.db` |
| Rows inserted | 89 (first run) |
| Rows inserted (second run) | 0 (idempotent) |
| Idempotency | PASS |
| Rollback plan | `DROP TABLE strategy_catalog_p1` — zero impact on existing tables |

## API/UI Impact

- Existing 44/44 API contract tests: all PASS (no existing table modified)
- `strategy_catalog_p1` is a NEW additive table
- `strategy_replay_runs`, `prediction_runs`, `prediction_items` — UNTOUCHED
- NO replay rows fabricated for any entry
- All artifact-only entries have `catalog_visibility_state=ARTIFACT_CANDIDATE`
- All entries without replay rows have `no_data_reason` set

## Modified/Created Files

| File | Action |
|------|--------|
| `lottery_api/models/replay_strategy_catalog_contract.py` | NEW |
| `scripts/p1_catalog_visibility_plan.py` | NEW |
| `scripts/apply_p1_catalog_visibility.py` | NEW |
| `tests/test_p1_catalog_visibility_contract.py` | NEW |
| `tests/test_p1_catalog_visibility_plan.py` | NEW |
| `tests/test_apply_p1_catalog_visibility.py` | NEW |
| `outputs/replay/p1_catalog_visibility_plan_20260518.json` | GENERATED |
| `outputs/replay/p1_catalog_visibility_apply_dry_run_20260518.json` | GENERATED |
| `outputs/replay/p1_catalog_visibility_apply_result_20260518.json` | GENERATED |
| `docs/replay/p1_catalog_visibility_plan_20260518.md` | GENERATED |
| `docs/replay/p1_catalog_visibility_report_20260518.md` | THIS FILE |

## Verification Results

| Check | Result |
|-------|--------|
| Drift guard (post-apply) | PASS |
| API contract (post-apply) | 44/44 PASS |
| P1 contract tests | 61/61 PASS |
| P0 tests | N/A (no p0_canonical files from today) |
| Full test suite (pre-existing failures) | 33 failed (same as main branch baseline) |

## Safety Confirmation

1. **No draw import**: CONFIRMED — no draws were imported
2. **No replay row generation**: CONFIRMED — strategy_replay_runs untouched
3. **No prediction update**: CONFIRMED — prediction_runs/prediction_items untouched
4. **No strategy execution**: CONFIRMED — adapters not invoked
5. **No DB binary in git**: CONFIRMED — DB not staged for commit
6. **DB write only if --apply**: CONFIRMED — dry-run verified first

## CTO 10-Line Summary

1. **P0 baseline preserved**: 18 canonical strategies, 44/44 API tests, drift guard PASS throughout.
2. **New additive table**: `strategy_catalog_p1` created — zero impact on existing tables.
3. **89 total entries**: 18 existing code registry + 71 artifact candidates (REJECTED strategies from governance history).
4. **71 new ARTIFACT_CANDIDATE entries**: all from `rejected/` JSON inventory, all NO_DATA (no replay rows fabricated).
5. **0 ONLINE guesses**: no artifact entry was promoted to ONLINE — all new entries use REJECTED/RETIRED/OBSERVATION/ARTIFACT_ONLY.
6. **Apply idempotent**: second run inserts 0 rows, idempotency confirmed in tests.
7. **Rollback trivial**: `DROP TABLE strategy_catalog_p1` fully reverts P1 with zero collateral damage.
8. **61 new tests**: all pass — contract, planner, and apply covered.
9. **Pre-existing failures unchanged**: 33 test failures existed on main before P1; P1 did not add or remove any.
10. **Next step**: P2 = API endpoint to expose `strategy_catalog_p1` to replay page UI (read-only, NO_DATA status surfaced).
