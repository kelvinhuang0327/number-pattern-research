# PR Draft: Replay Strategy Catalog Stabilization — P0 through P10

**Branch**: `feat/p0-single-repo-stabilization-p1-catalog-plan-20260519` → `main`  
**Commits**: 11 ahead of main  
**Tests**: 303/303 PASS  
**DB change**: NONE

---

## Summary

This PR stabilizes the Replay Track strategy catalog and execution pipeline across
10 phases (P0–P10). It establishes the governance, test suite, visibility classification,
coverage matrix, API enrichment, operations runbook, and apply gate for the replay
system — while keeping production DB unchanged at 460 rows.

The P7 ONLINE apply (28 new rows, 460→488) is ready but **blocked by design** until CEO
authorization is received via exact phrase. That apply can be executed from main after merge.

---

## What Changed

### Code
- `lottery_api/routes/replay.py`: Added 4 non-breaking fields to `GET /api/replay/history`
  response (`visibility_state`, `display_status`, `should_count_as_success`, `source_trace`).

### Scripts (14 new — all read-only dry-run)
- `p7_controlled_replay_row_apply.py` — gate-protected production apply (default: dry-run)
- `p7_controlled_replay_row_apply_dry_run.py` — plan-only preview
- `p2_full_catalog_visibility_plan.py` — 59-strategy 4-state visibility classifier
- `p3_per_draw_all_strategy_coverage_matrix.py` — 1,288-cell coverage matrix builder
- `p5_replay_visual_api_verification.py` — API gap auditor
- `p6_catalog_apply_plan_v1.py` — apply decision planner
- `p8_reconstructible_backfill_dry_run.py` — 121-candidate payload previewer
- `replay_lifecycle_drift_guard.py` — schema + row count drift detector (minor update)
- + 6 additional planning scripts

### Tests (11 new test files, 303 total)
- `test_p7_controlled_apply_actual_gate.py` (17) — P7 apply safety gate
- `test_p2_full_catalog_visibility_plan.py` (24)
- `test_p3_per_draw_all_strategy_coverage_matrix.py` (32)
- `test_p6_catalog_apply_plan_v1.py` (31)
- `test_p8_reconstructible_backfill_dry_run.py` (37)
- `test_p9_replay_launch_readiness_lock.py` (68)
- `test_p10_replay_operations_readiness.py` (50)
- + 4 existing test files (unchanged or minor updates)

### Documentation (27 docs in `docs/replay/`)
- P1b registry reconciliation (16 vs 18 resolved)
- P2–P10 phase reports and plans
- P10 operations runbook, monitoring plan, rollback checklist
- P9 canonical artifact index and source-of-truth lock

### Outputs (18 JSONs in `outputs/replay/`)
- Dry-run plans, coverage matrices, visibility plans, gate reviews
- All marked `dry_run_only: true`

---

## Safety Guarantees

| Guarantee | Verified By |
|-----------|------------|
| Production DB = 460 rows (unchanged) | `sqlite3` + drift guard + 7 test suites |
| No DB files in PR | `git diff main..HEAD --name-only \| grep '\.db$'` → 0 |
| `fake_success_count` = 0 | 32 tests in `test_p3` |
| P7 apply requires explicit `--apply` flag + CEO phrase | 17 tests in `test_p7_controlled_apply_actual_gate` |
| RETIRED rows never mixed into ONLINE apply | Hard scope gate in apply script |
| API change is additive-only (no breaking change) | 44 API contract tests |
| No strategy logic modified | Diff contains no changes to strategy engine files |

---

## Test Results

```
303/303 PASS
Drift guard: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
API contract: 44/44 PASS
```

---

## Production DB Status

```
strategy_prediction_replays: 460 rows
```

**This PR does not modify the production database.**

Post-merge, the P7 ONLINE apply (28 rows, 460→488) can be executed by:
1. CEO issues: `YES apply P7 controlled replay rows`
2. Running: `python scripts/p7_controlled_replay_row_apply.py --apply --scope ONLINE_ONLY --backup <backup_path> --expected-rows 460`

---

## Out of Scope

- P7 ONLINE apply (+28 rows) — intentionally deferred; requires CEO phrase
- P7 RETIRED apply (+93 rows) — requires separate human review + authorization
- ARTIFACT_ONLY strategy governance (41 strategies) — requires registry registration
- UI major redesign — deferred
- New crawler / external data — out of scope

---

## Risk / Rollback

**Merge risk**: LOW. All changes are additive (scripts, tests, docs, 4 API fields).

**Rollback plan**: If the API 4-field addition causes issues:
```python
# Remove the 4 added lines from get_replay_history() in lottery_api/routes/replay.py
# "visibility_state", "display_status", "should_count_as_success", "source_trace"
```
No DB rollback needed — no DB changes in this PR.

---

## CEO Authorization Status

P7 ONLINE apply is **BLOCKED** until:
```
YES apply P7 controlled replay rows
```
is received from the CEO/operator. This can happen before or after merge.

---

## Required Post-Merge Actions

1. Confirm `git diff main HEAD -- lottery_api/data/lottery_v2.db` is empty
2. Run full test suite on main: `pytest -q tests/`
3. Run drift guard: `python scripts/replay_lifecycle_drift_guard.py --strict`
4. Await CEO authorization phrase for P7 ONLINE apply
5. After P7 apply: run post-apply verification per `p10_replay_operations_runbook_20260520.md`

---

## Reviewers

Please verify:
- [ ] No `.db` files staged
- [ ] API change is additive-only (confirm `test_replay_api_contract.py` still 44/44)
- [ ] P7 apply script default is dry-run (no `--apply` flag = no write)
- [ ] `fake_success_count` remains 0 in P3 matrix
- [ ] `p10_replay_rollback_checklist_20260520.md` covers rollback scenarios

🤖 Generated with [Claude Code](https://claude.com/claude-code)
