# P1 Replay Lifecycle Hardening Diff Finalization

## Completed

The remaining helper diffs were inspected and kept because they are required to reproduce the synthetic-fixture validation result. The drift guard now honors `LOTTERY_TEST_DB_PATH`, the CLI no longer lets a default DB path override the fixture override, and the drift guard tests accept the expected `BLOCKED` state for the synthetic fixture.

## Modified Helper Files

- `scripts/check_replay_lifecycle_drift.py`
- `tests/test_replay_lifecycle_drift_guard.py`

## Diff Decision

Keep both helper files.

They are required because they:

- make `LOTTERY_TEST_DB_PATH` work correctly
- prevent CLI defaults from overriding the fixture env path
- convert synthetic fixture drift from crash/fail into explicit `BLOCKED` status
- make the tests accept the expected `BLOCKED` state for the synthetic fixture
- preserve reproducibility for the committed validation JSON and report

## Validation Result After Decision

Validation was rerun against the synthetic fixture and the current project venv.

- Drift guard script: `BLOCKED` on the synthetic fixture, with unknown synthetic strategy IDs reported as expected
- Drift guard test: `3 passed in 0.02s`
- Browser E2E: `1 skipped in 0.03s` because Playwright/browser tooling is unavailable
- Baseline replay bundle: `34 passed, 29 skipped in 0.32s`
- Syntax check: passed for the touched helper files

## Files Committed / Reverted

Committed in this finalization:

- `scripts/check_replay_lifecycle_drift.py`
- `tests/test_replay_lifecycle_drift_guard.py`
- `outputs/replay/p1_replay_lifecycle_hardening_diff_finalization_20260509.md`

Not reverted:

- `outputs/replay/p1_replay_lifecycle_drift_guard_20260509.json`

## What Was Not Changed

- Replay UI code was not modified.
- Replay API code was not modified.
- Lifecycle registry code was not modified.
- Branch protection was not modified.
- Main was not pushed directly.
- No force push or admin override was used.
- No DB binary was committed.
- No strategy mining or replay generation was run.
- Browser E2E was not claimed as passing because the browser toolchain is unavailable here.

## Remaining Risks

- The synthetic fixture remains intentionally registry-misaligned, so `BLOCKED` is the correct guard output rather than `PASS`.
- Browser E2E still depends on a workspace with Playwright/browser tooling installed.
- The committed JSON/report are only reproducible if the helper changes are present, which is why they were retained.

## Recommended Next Action

Push the finalized branch to `codex/p1-replay-lifecycle-hardening` and keep the helper files as part of the branch history.

## Final Marker

P1_REPLAY_LIFECYCLE_HARDENING_DIFF_FINALIZED