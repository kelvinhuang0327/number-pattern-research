# Post-V3 Replay Lifecycle Stabilization Report

**Date:** 2026-05-14  
**Classification:** POST_V3_STABILIZATION_DRIFT_GUARD_PR_READY  
**Author:** Stabilization Agent (Claude Sonnet 4.6)

---

## 1. Current Release State

### PR Merge Status
| PR | Title | State | Merge Commit | Merged At |
|----|-------|-------|-------------|-----------|
| #97 | fix(replay): close Post-V3 truth-level API contract | MERGED | 2ff4422 | 2026-05-14T08:01:27Z |
| #98 | docs(replay): record Post-V3 release tag closure | MERGED | 2bb6289 | 2026-05-14T09:21:52Z |

### Release Tag
- **Tag name:** `post-v3-replay-lifecycle-release-20260514`
- **Tagged commit:** `5809445` (docs: add PR97 post-merge API regression + UI smoke reports + truth badge patch)
- **Tag exists locally:** YES
- **Tag exists on remote (origin):** YES (`b48daf4` annotated tag object → `5809445^{}`)

### origin/main HEAD
- `2bb6289` — Merge commit of PR #98 (docs: record Post-V3 release tag closure)

### Working Tree
- Clean — no staged forbidden files (.db, .sqlite, .pid, logs)

### UI Patch
- Truth-level badge patch landed in PR #97 (commit `5809445`)
- `REGENERATED_RETROSPECTIVE` and `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` display correctly in the replay history UI

---

## 2. Baseline Verification

### API Regression (16/16 PASS)
Run: `python3 scripts/post_v3_replay_api_regression.py --strict --json-out outputs/replay/post_v3_release_stabilization_api_regression_20260514.json`

| Tier | Count | Result |
|------|-------|--------|
| V1 EXECUTABLE_NOW | 6/6 | ALL PASS |
| V2 ARTIFACT_ONLY | 4/4 | ALL PASS |
| V3 CODE_MISSING | 6/6 | ALL PASS (tombstone contract verified) |
| **Total** | **16/16** | **ALL PASS** |

### Pytest (87/87 PASS)
Suites run:
- `tests/test_replay_lifecycle_drift_guard.py` — 6 tests
- `tests/test_replay_truth_level_contract.py` — existing suite
- `tests/test_replay_api_contract.py` — existing suite

**87 passed, 1 warning (PendingDeprecationWarning from starlette, non-blocking)**

### DB Baseline Counts
| Segment | Count | Expected | Status |
|---------|-------|----------|--------|
| V1 (controlled_apply_id=`20260514033100-13acaf34996e`) | 300 | 300 | PASS |
| V2 (controlled_apply_id=`20260514134953-cf683424`) | 200 | 200 | PASS |
| legacy (controlled_apply_id IS NULL) | 460 | 460 | PASS |
| **Total** | **960** | **960** | **PASS** |

truth_level distribution:
- `REGENERATED_RETROSPECTIVE`: 300 rows (V1 batch)
- `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`: 200 rows (V2 batch)
- `NULL`: 460 rows (legacy — production-protected)

V3 tombstone strategies (all 6 have 0 rows): CONFIRMED

---

## 3. Drift Guard Purpose

The drift guard (`scripts/replay_lifecycle_drift_guard.py`) is a **read-only** DB integrity checkpoint that:

1. Confirms the Post-V3 row count baseline has not been altered (V1=300, V2=200, legacy=460, total=960)
2. Verifies all 6 known V3 `CODE_MISSING` (tombstone) strategy IDs have exactly 0 rows in `strategy_prediction_replays`
3. Validates that `truth_level` values are only from the approved enum (`REGENERATED_RETROSPECTIVE`, `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`, or NULL)
4. Checks that no unexpected `controlled_apply_id` values have appeared

It enforces no DB writes, no API calls, no external services, and no imports of lottery_api modules. It is safe to run in any environment that has read access to the DB.

---

## 4. Rerun Command

```bash
python3 scripts/replay_lifecycle_drift_guard.py --strict --json-out outputs/replay/replay_lifecycle_drift_guard_YYYYMMDD.json
```

Example for today:

```bash
python3 scripts/replay_lifecycle_drift_guard.py --strict --json-out outputs/replay/replay_lifecycle_drift_guard_20260514.json
```

Exit code 0 = PASS. Exit code 1 = FAIL (drift detected).

---

## 5. Expected PASS Criteria

A drift guard run is `PASS` if and only if all of the following hold:

| Check | Expected |
|-------|----------|
| V1 row count | == 300 |
| V2 row count | == 200 |
| legacy row count | == 460 |
| total row count | == 960 |
| V3 tombstone strategies with 0 rows | 6/6 (acb_1bet, acb_markov_midfreq, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet, h6_gate_mk20_ew85) |
| truth_level values | Only: REGENERATED_RETROSPECTIVE, ARTIFACT_RECONSTRUCTED_RETROSPECTIVE, NULL |
| Unexpected controlled_apply_id values | None |
| violations list | Empty (`[]`) |
| final_classification | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` |

---

## 6. Known Intentional States

### V3 Tombstone (CODE_MISSING)
The 6 V3 strategies (`acb_1bet`, `acb_markov_midfreq`, `acb_markov_midfreq_3bet`, `midfreq_acb_2bet`, `midfreq_fourier_2bet`, `h6_gate_mk20_ew85`) are intentionally registered with `lifecycle_status=CODE_MISSING`. They appear in the API registry with the tombstone contract but have **zero rows** in `strategy_prediction_replays`. This is by design — no replay data was generated for them because their generator code no longer exists in the codebase. The drift guard enforces this invariant.

### Legacy Rows (production-protected)
The 460 rows with `controlled_apply_id IS NULL` are the original production replay rows that predate the V1/V2 controlled apply batches. They must not be modified, deleted, or assigned a `controlled_apply_id`. The drift guard monitors this count as an immutability signal.

### V1 Batch
300 rows with `truth_level=REGENERATED_RETROSPECTIVE` applied via controlled batch `20260514033100-13acaf34996e`. These represent strategies that were fully regenerated from historical draws.

### V2 Batch
200 rows with `truth_level=ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` applied via controlled batch `20260514134953-cf683424`. These represent strategies reconstructed from archived artifacts where full regeneration was not possible.

---

## 7. Forbidden Actions

The following actions are permanently forbidden without a new explicit release decision and PR:

| Action | Reason |
|--------|--------|
| Writing to `strategy_prediction_replays` outside a controlled apply batch | Will break drift guard row count baselines |
| Applying replay rows for V3 (`CODE_MISSING`) strategies | V3 tombstone invariant (0 rows) must be preserved |
| Deleting or modifying legacy rows (`controlled_apply_id IS NULL`) | Production-protected, immutable |
| Changing `truth_level` values outside the approved enum | truth_level enum contract enforced by tests |
| Assigning unexpected `controlled_apply_id` values | Only known V1/V2/NULL are allowed |
| Deleting or recreating the release tag | Tag is the immutable release reference |
| Merging the drift guard PR without CI green | CI gate is required |
| Force-pushing to main | Prohibited unconditionally |
| Committing `.db`, `.sqlite`, `.pid`, or log files | Forbidden from all commits |

---

## 8. Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| DB file replaced or restored from backup with different row counts | HIGH | Drift guard detects immediately on next run |
| New controlled apply batch applied without updating drift guard baseline | MEDIUM | Operator must update `BASELINE` dict in `replay_lifecycle_drift_guard.py` and bump expected counts |
| New truth_level enum value introduced without updating `ALLOWED_TRUTH_LEVELS` | LOW | Drift guard will flag it as a violation |
| V3 strategy code resurrected and replay rows applied without removing tombstone | MEDIUM | V3 row check will catch it |
| DB schema migration adds rows (e.g., via fixtures) before drift guard runs in CI | LOW | Drift guard CI job should run after migrations, not before |
| CI job not scheduled — drift runs only on PR | MEDIUM | Recommend scheduled nightly CI lane (Phase 9) |

---

## 9. Recommended Next Phase: Scheduled/Manual CI Monitoring Lane

The drift guard is currently invoked only:
- Manually (`python3 scripts/replay_lifecycle_drift_guard.py --strict`)
- As part of the PR pytest suite (`tests/test_replay_lifecycle_drift_guard.py`)

**Recommended next action:** Add a scheduled GitHub Actions job (e.g., nightly at 02:00 UTC) that:

1. Runs `python3 scripts/replay_lifecycle_drift_guard.py --strict --json-out outputs/replay/replay_lifecycle_drift_guard_$(date +%Y%m%d).json`
2. Uploads the JSON as a GitHub Actions artifact
3. Fails the workflow if exit code != 0
4. Posts a summary to the PR/commit or sends a Slack notification on FAIL

This converts the drift guard from a one-time check into a continuous integrity monitoring lane without requiring any new DB writes, API changes, or strategy mining.

**No further replay row applies, strategy mining, registry semantic changes, or UI behavior changes are recommended at this time.** The system is in maintenance mode for the replay lifecycle subsystem.

---

## Appendix: File Inventory for This Stabilization PR

| File | Purpose |
|------|---------|
| `scripts/replay_lifecycle_drift_guard.py` | Read-only DB drift guard script |
| `tests/test_replay_lifecycle_drift_guard.py` | 6 deterministic pytest tests |
| `outputs/replay/replay_lifecycle_drift_guard_20260514.json` | PASS baseline JSON (today's run) |
| `outputs/replay/post_v3_release_stabilization_api_regression_20260514.json` | 16/16 API regression result |
| `outputs/replay/post_v3_replay_lifecycle_stabilization_report_20260514.md` | This report |
