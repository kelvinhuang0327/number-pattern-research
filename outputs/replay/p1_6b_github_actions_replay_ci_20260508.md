# P1-6B GitHub Actions Replay CI Workflow Report

Date: 2026-05-08  
Branch: `main`  
Workspace: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge`

## 1. Executive Summary
P1-6B completed by adding a GitHub Actions workflow that wires the replay validation matrix into CI with two auditable lanes:
- default replay validation lane (DB optional; `requires_db` skips allowed),
- dedicated DB validation lane (manual dispatch; DB fixture required; fail-fast when unavailable).

This round does not implement DB fixture provisioning itself.

## 2. P1-6A Baseline
From P1-6A:
- `scripts/run_replay_ci_default_validation.py`
- `scripts/run_replay_ci_db_validation.py`
- `outputs/replay/p1_6a_db_ci_hardening_20260508.md`

Behavior baseline:
- default script: `57 passed, 32 skipped` profile in DB-absent environment.
- dedicated script: exits with non-zero (`2`) when DB fixture is missing.

## 3. Workflow Created
Created:
- `.github/workflows/replay-governance-ci.yml`

Triggers:
- `pull_request`
- `push` on `main`
- `workflow_dispatch` (with optional `db_path` input)

## 4. CI Matrix Design
Two-lane design:

1. `replay-default-validation`
   - Runs on PR and main push.
   - Executes `python scripts/run_replay_ci_default_validation.py`.
   - Allows `requires_db` skip behavior while still enforcing non-DB governance checks.

2. `replay-dedicated-db-validation`
   - Runs only on `workflow_dispatch`.
   - Accepts optional `db_path` via dispatch input -> `LOTTERY_TEST_DB_PATH`.
   - Executes `python scripts/run_replay_ci_db_validation.py`.
   - If fixture is missing, lane fails explicitly (no silent pass).

## 5. Default Validation Lane
Purpose:
- Preserve current CI-safe replay governance validation in DB-absent environments.

Execution path:
- checkout
- setup python
- install validation dependencies
- run default script

Expected in DB-absent environment:
- `57 passed, 32 skipped` (or equivalent non-DB pass + requires_db skip profile)

## 6. Dedicated DB Validation Lane
Purpose:
- Provide an auditable DB-required validation path for `requires_db` tests.

Execution path:
- checkout
- setup python
- install validation dependencies
- map workflow input `db_path` to `LOTTERY_TEST_DB_PATH`
- run dedicated script

Behavior:
- Missing DB fixture -> script exits code `2` with explicit error.
- Dedicated lane therefore cannot appear green without actual DB fixture.

## 7. DB Fixture Policy
This round intentionally does NOT provide fixture implementation or DB artifact download.
Only a controlled interface is reserved:
- `workflow_dispatch` input: `db_path`
- env: `LOTTERY_TEST_DB_PATH`

No DB files are committed.

## 8. Why Dedicated Lane Does Not Fake Pass
`scripts/run_replay_ci_db_validation.py` enforces:
1. pre-run DB existence check,
2. non-zero exit when fixture missing,
3. DB lane test run with `-m requires_db`,
4. non-zero exit if skip count remains > 0.

This prevents silent skip / fake green outcomes in the dedicated lane.

## 9. Validation Results
Local validation for this round:

1. Default script smoke:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py
```
Result:
- `57 passed, 32 skipped, 1 warning`

2. Dedicated DB script smoke:
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_db_validation.py
```
Result:
- exit code `2`
- explicit error: DB fixture not found

3. Workflow structure check:
- inspected workflow file content directly (`sed -n`) to confirm trigger, jobs, and lane commands.

## 10. Files Changed
- Added `.github/workflows/replay-governance-ci.yml`
- Added `outputs/replay/p1_6b_github_actions_replay_ci_20260508.md`

## 11. What Was Not Changed
- no replay generation
- no strategy mining
- no edge discovery
- no Replay API behavior change
- no active strategy state change
- no DB files committed
- no production outcome write
- no `test_mab_ensemble.py` changes
- no `index.html` changes

## 12. Remaining Risks
1. Dedicated lane needs controlled fixture provisioning before full CI-green enforcement.
2. Dependency installation list in workflow is minimal and may need refinement if replay tests add new imports.
3. Dedicated lane currently manual (`workflow_dispatch`) by design; org policy may later require scheduled/PR-gated DB lane.

## 13. Follow-up Tasks
1. Define secure fixture source strategy (artifact download or managed path).
2. Add guarded enforcement policy for dedicated DB lane once fixture supply is stable.
3. Optionally add branch protection integration for replay lanes after stabilization.

## 14. Final Recommendation
Adopt this workflow as the replay governance CI baseline immediately:
- default lane guards ongoing non-DB governance regressions,
- dedicated lane now has explicit, auditable fail-fast semantics for missing DB fixture.

Dedicated DB lane requires controlled fixture provisioning before full CI green enforcement.
