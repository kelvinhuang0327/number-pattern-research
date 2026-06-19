# P280X BIG 6/49 One-Shot Publication Runner Design

## Status

`P280X_BIG649_ONE_SHOT_DRY_RUN_RUNNER_PR_OPEN_NOT_ACTIVATED`

This is a dry-run-only publication runner design. It does not authorize a real target selection, a real ticket, an official deadline lookup, future evaluation, activation, registry work, ONLINE changes, production changes, deployment, or controlled_apply.

## Verified State

- Repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- Branch: `task/p280x-big649-one-shot-publication-runner-dry-run`
- Canonical branch: `main`
- `origin/main`: `4a7c534b5fa53425aa1bb1d4981ed2b830a62170`
- Real target selected: `false`
- Real ticket published: `false`
- Official deadline lookup: `false`
- Future evaluation started: `false`
- Dry-run warning: `NOT_A_REAL_PREDICTION`
- Publication status: `NOT_PUBLISHED`
- Publication guard state: `DRY_RUN_ONLY_NOT_PUBLISHED`
- Zero-DB guard: `true`
- No GitHub publication side effect: `true`

## Runner Contract

- Game: `BIG / 大樂透 / 6-49`
- Endpoint: `BIG_ANY_PRIZE_AWARE_WIN`
- Primary budget: `1`
- `bet_index`: `1`
- Strategy count: `11`
- Strategy set: the exact frozen 11 BIG strategy IDs
- Manifest hash: `aaac655bf5a2dbd9de95b4fbdef56cb350fd95f5d2e6545cbbeceb2444810a6f`

## Guardrails

- Duplicate check before write
- Idempotency check before write
- Randomness policy check before write
- Deterministic rerun difference means STOP
- Stochastic rerun difference is allowed only with recorded seed/policy
- Missing strategy means STOP
- Extra strategy means STOP
- Invalid ticket means STOP
- Any DB path touched means STOP
- Real publication requires separate explicit Owner authorization

## Public Helpers

- `build_dry_run_manifest(...)`
- `validate_manifest(...)`
- `check_duplicate_manifest(...)`
- `check_idempotency(...)`
- `classify_randomness(...)`
- `stop_on_unexplained_difference(...)`

## Validation Summary

- P280X focused tests: `PASS` (`10` passed, `0` failed)
- Python compile check: `PASS`
- Runner source scan: `PASS`
- Runbook scan: `PASS`
- Publication PR scan: `PASS` on deliverables excluding the negative-assertion test harness
- DB access scan: `PASS` on deliverables excluding the negative-assertion test harness
- JSON parse: `NOT RUN` at authoring time
- Markdown readability scan: `NOT RUN` at authoring time
- Source-contract tests: `NOT RUN`
- P280D focused tests: `NOT RUN`
- Regressions: `NOT RUN`
- Full suite: `NOT RUN`
- Dedicated DB: `SKIPPED`
- DB opened / queried / copied / written: `NO / NO / NO / NO`

## Worktree Observation

- Launch worktree remained unchanged during this task, but its observed dirty snapshot differs from the historical 23-file fingerprint baseline and was not modified.
- P280K worktree remained clean.
- P280X worktree stayed on the dry-run branch and only carries the intended task files.
- The test harness intentionally includes forbidden token names in negative assertions; the publication PR and DB scans exclude that harness file.

## Next Recommended Step

`P280L_BIG649_PUBLICATION_DRY_RUN_REHEARSAL_ONLY`

## Notes

- No real target was selected.
- No official deadline was looked up.
- No real ticket was published.
- No future evaluation was started.
- Real publication remains unauthorized.
