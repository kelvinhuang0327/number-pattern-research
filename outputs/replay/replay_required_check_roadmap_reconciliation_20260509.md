# Replay Required-Check Roadmap Reconciliation

Date: 2026-05-09
Role: CTO daily review / roadmap reconciliation
Scope: report-only; no replay UI/API code, tests, DB, branch protection, replay generation, or strategy-mining changes.

## 1. Executive Summary

The supplied handoff says the `replay-default-validation` required-check rollout is complete, browser lane has CI `PASS`, PR #1 was merged at `e765b3b...`, and post-enactment stability monitoring is healthy. Current GitHub/repo verification does **not** support that state for this repository.

Verified current state after checking PR #9 run `25602048716`:

- `origin/main` remains at `cbe51713db0950f021ef8f52a9fc99e6e399c9ac` (PR #8 merge), not `e765b3b...`.
- PR #9 (`test(replay): enable lifecycle browser e2e ci path`) is `OPEN`, not merged.
- PR #9 latest head is `2cd730b3682e083160953a6f71b651d56b64cbaf`.
- PR #9 check rollup:
  - `replay-default-validation`: `SUCCESS`
  - `replay-browser-e2e-validation`: `FAILURE`
  - `replay-dedicated-db-validation`: `SKIPPED`
- Branch protection on `main` currently requires only `replay-default-validation`, with strict mode and admin enforcement enabled.

CTO decision: do **not** proceed to P4 browser scenario coverage planning yet. The next-stage P0 must be PR #9 browser E2E failure closure and PR merge readiness. Scenario planning becomes useful only after the browser lane is green and the required-check rollout state is actually merged/observed on `main`.

## 2. Source Alignment Check

| Claimed in handoff | Current verified state | CTO interpretation |
| :-- | :-- | :-- |
| Browser lane CI `PASS` | PR #9 run `25602048716` has `replay-browser-e2e-validation = FAILURE` | rollout is not complete |
| PR #1 merged with `e765b3b...` | Current PR #1 in repo is an older merged release PR; browser E2E work is PR #9 open | PR numbering/context mismatch |
| `origin/main` points to `e765b3b...` | `origin/main` points to `cbe5171...` | main does not include browser E2E enablement |
| Required-check rollout completed | branch protection requires `replay-default-validation`, but browser lane is not merged/green | governance foundation exists; browser evidence is still blocked |
| P4 scenario planning should start | PR #9 still failing | P4 should wait |

## 3. Current System Status

### Main branch

- `origin/main`: `cbe51713db0950f021ef8f52a9fc99e6e399c9ac`
- Main currently includes PR #3/#5/#6/#7/#8 replay lifecycle foundation.
- Main does not yet include PR #9 browser E2E CI enablement commits.

### Branch protection

- required status check: `replay-default-validation`
- strict mode: enabled
- admin enforcement: enabled
- force pushes: disabled
- deletions: disabled
- conversation resolution: required

### PR #9

- title: `test(replay): enable lifecycle browser e2e ci path`
- state: `OPEN`
- merge state: `UNSTABLE`
- latest head: `2cd730b3682e083160953a6f71b651d56b64cbaf`
- latest run: `25602048716`
- latest CI:
  - `replay-default-validation`: success
  - `replay-browser-e2e-validation`: failure
  - `replay-dedicated-db-validation`: skipped

### Latest browser failure

The latest browser E2E failure has progressed from empty-state rendering to a UI display contract mismatch. The scoped row locator now reaches the correct table row, but the UI renders the localized lifecycle label `拒絕` while the test still expects the raw enum `REJECTED`.

Observed failure:

```text
FAILED tests/test_replay_lifecycle_browser_e2e.py::test_lifecycle_filter_browser_e2e
AssertionError: assert 'REJECTED' in '拒絕'
```

The previous query-string mock fix and row-scope fix were necessary and moved the lane forward. Current evidence suggests the remaining blocker is not request mocking or empty-state selection; it is that the test assertion is checking the internal enum while the UI displays a localized value. P0 should fix the browser test to assert the intended user-visible lifecycle label, or explicitly assert both the selected filter enum and displayed localized row value.

## 4. Roadmap Alignment

Original post-PR8 roadmap was directionally right:

1. Browser E2E CI enablement
2. Dedicated DB lane evidence
3. Lifecycle DB/audit design
4. Scenario coverage planning

The handoff report advanced too far by treating browser E2E enablement and required-check rollout as completed. Actual progress is earlier:

- PR #3-#8 replay lifecycle foundation: complete
- Browser E2E CI enablement: in progress, blocked by PR #9 failure
- Required-check rollout: not complete for browser work; branch protection currently gates only default replay validation
- Scenario coverage planning: premature

Roadmap adjustment: make PR #9 failure closure the only P0. Keep P4 planning as a later planning task after green CI and main observation evidence.

## 5. Reordered P0-P10 Roadmap

| Priority | Roadmap item | New status | Why | Exit criteria |
| :-- | :-- | :-- | :-- | :-- |
| P0 | PR #9 browser E2E display-contract assertion fix | Active blocker | browser lane is failing because UI displays `拒絕` while test expects `REJECTED` | `replay-browser-e2e-validation` true `PASS`, no false skip/pass |
| P1 | PR #9 merge readiness and protected merge | Next | browser enablement must land before rollout claims | PR #9 clean/green and merged into `main` |
| P2 | Main branch post-merge observation | After merge | verify browser lane on main, not only PR merge ref | at least one `main` push run green; browser lane true `PASS` or documented non-required behavior |
| P3 | Required-check rollout verification | After main observation | verify branch protection and required check names after merge | `replay-default-validation` still required; no rollback needed |
| P4 | Browser scenario coverage planning | Deferred | useful only after current browser lane is stable | scenario matrix/report only; no new tests yet |
| P5 | Dedicated DB lane observation evidence | Deferred | current DB lane remains skipped | observation evidence without production DB writes |
| P6 | Lifecycle DB migration / audit trail design | Later | durable audit model is needed after validation lanes stabilize | design doc only, no production migration |
| P7 | non-ONLINE production catalog population plan | Later | multi-state fixture is synthetic-only | plan real catalog population safely |
| P8 | Replay coverage gap report across lifecycle states | Later | quantify real lifecycle coverage after catalog plan | coverage report by lifecycle status |
| P9 | CI summary annotation / reviewer UX | Later / parallel | reduce reviewer friction once lanes are stable | PR summary clearly shows mismatch/aligned/multistate/browser |
| P10 | Maintenance / cleanup / branch hygiene | Ongoing | many report/feature branches exist | cleanup plan after CTO approval |

## 6. Key Blockers

1. PR #9 browser E2E job is failing.
2. `origin/main` does not include browser E2E enablement.
3. The supplied handoff references commit/PR state not present in current verified repo state.
4. Branch protection gates `replay-default-validation`, but browser E2E is currently a separate failing lane.
5. Local browser tooling is unavailable, so local validation still produces honest `SKIP`; CI is the source of truth for browser behavior.
6. Current failure is now a test expectation mismatch between raw lifecycle enum and localized UI label.

## 7. What Not To Do Next

- Do not start P4 scenario coverage planning as the next active workstream.
- Do not claim required-check rollout completed.
- Do not claim long-term or short-term stability for a rollout not present on `main`.
- Do not change branch protection while PR #9 browser lane is failing.
- Do not add more browser scenarios before the single current browser path is green.
- Do not write production DB or commit DB binaries.
- Do not run replay generation, strategy mining, or edge discovery.

## 8. Recommended Immediate Technical Direction

Focus on one narrow engineering task:

**Fix PR #9 browser E2E display-contract assertion until `replay-browser-e2e-validation` is a true CI `PASS`.**

The likely investigation path:

1. Confirm the selected filter remains raw enum `REJECTED`.
2. Confirm the row lifecycle cell intentionally displays localized `拒絕`.
3. Update the browser test to assert the user-visible localized value, or assert both filter enum and localized row label.
4. Keep the scoped locator `#rp-hist-body`.
5. Do not change Replay UI/API behavior unless a selector-only test hook is strictly necessary.

## 9. Latest Task Prompt

```text
# ROLE
You are LotteryNew's P0 Replay Browser E2E Failure Closure Agent, reporting to the CTO agent.

# MISSION
Close PR #9's failing `replay-browser-e2e-validation` lane by fixing the current lifecycle display assertion mismatch, and restore a true CI browser PASS without changing replay semantics, branch protection, production DB, or strategy logic.

# CURRENT VERIFIED STATE
- origin/main = cbe51713db0950f021ef8f52a9fc99e6e399c9ac
- PR #9 is OPEN: `test(replay): enable lifecycle browser e2e ci path`
- PR #9 head = 2cd730b3682e083160953a6f71b651d56b64cbaf
- latest run = 25602048716
- PR #9 check rollup:
  - replay-default-validation = SUCCESS
  - replay-browser-e2e-validation = FAILURE
  - replay-dedicated-db-validation = SKIPPED
- Latest browser failure:
  - selected filter enum = `REJECTED`
  - row lifecycle cell text = `拒絕`
  - test currently expects raw enum `REJECTED`

# HARD SCOPE
Do not:
- change branch protection
- write production DB
- commit DB binaries
- run replay generation
- run strategy mining or edge discovery
- change lifecycle registry semantics
- claim PASS if browser test skipped
- expand browser scenario coverage beyond the current failing path

# TASKS
1. Inspect PR #9 run `25602048716` browser failure logs and current `tests/test_replay_lifecycle_browser_e2e.py`.
2. Confirm that `#rp-hist-body` now renders the expected row.
3. Treat the remaining failure as a UI display-contract mismatch unless new evidence says otherwise.
4. Apply the smallest browser test fix: keep asserting filter enum `REJECTED`, but assert row display text `拒絕` or a documented localized lifecycle label mapping.
5. Keep Replay UI/API behavior unchanged unless a selector-only test hook is strictly required and documented.
6. Run local validation; local browser may honestly SKIP if Playwright is unavailable.
7. Push the fix to PR #9 and verify GitHub Actions.
8. Produce a report under `outputs/replay/` documenting:
   - root cause
   - exact fix
   - local result
   - CI result
   - PASS vs SKIP distinction
   - no branch protection / DB / replay generation / strategy mining changes

# ACCEPTANCE CRITERIA
- `replay-browser-e2e-validation` is true CI PASS.
- `replay-default-validation` remains PASS.
- `replay-dedicated-db-validation` remains explicitly understood as SKIPPED unless separately handled.
- PR #9 reaches merge-ready state.
- No forbidden side effects.

# FINAL MARKER
P0_REPLAY_BROWSER_E2E_FAILURE_CLOSED_READY
```

## 10. CTO 10-Line Summary

1. The latest handoff's "run pending" state is now resolved: run `25602048716` failed.
2. `origin/main` is still PR #8 at `cbe5171`, not a browser-E2E merge commit.
3. Browser E2E enablement is PR #9, and PR #9 is still open.
4. PR #9 default validation passes, dedicated DB is skipped, browser E2E fails.
5. The latest failure is now `REJECTED` expected vs localized `拒絕` displayed.
6. The row-scope fix worked enough to reach the correct row; this is progress.
7. P4 scenario planning remains premature.
8. P0 is now a small browser-test display-contract assertion fix.
9. P1 becomes PR #9 merge readiness after true browser CI PASS.
10. Next task marker: `P0_REPLAY_BROWSER_E2E_FAILURE_CLOSED_READY`.

## 11. Final Marker

REPLAY_REQUIRED_CHECK_ROADMAP_RECONCILIATION_20260509_READY
