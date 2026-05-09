# P1 Replay Lifecycle Hardening

## 1. Executive Summary

The Replay Lifecycle UI P0 work remains intact on `origin/main`, and the follow-up hardening slice was reduced to read-only guard work. I added a lifecycle drift guard script, a lifecycle-specific browser E2E test scaffold, and a JSON drift artefact. In this workspace, validation is environment-limited: `pytest` is not available, the local replay DB fixture is missing, and browser automation cannot be executed here. Nothing in the replay feature code, branch protection, or production data was changed.

## 2. Current Main Verification

- `origin/main` tip: `50a36fd docs(replay): record lifecycle ui merge and protection restoration (#5)`
- PR #3: `MERGED` with merge commit `d625a38078eaf50edccacba1959dff220eb424bf`
- PR #5: `MERGED` with merge commit `50a36fd7bcba4c2cb29c489486851b8e290f63ed`
- main protection remains restored with only `replay-default-validation` required
- lifecycle implementation is still present on `origin/main`:
  - `ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED`
  - `ACTIVE` alias normalises to `ONLINE`
  - `/api/replay/strategies` and `/api/replay/history` accept `lifecycle_status`
  - `index.html` contains `rp-lifecycle-select` and lifecycle badge rendering

## 3. Lifecycle Drift Guard

Added a read-only drift guard script:

- [scripts/check_replay_lifecycle_drift.py](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge/scripts/check_replay_lifecycle_drift.py)

What it checks:

- registry lifecycle statuses are traceable from replay row strategy IDs
- replay rows map back to canonical lifecycle values
- unknown strategy IDs are surfaced
- a JSON summary can be written without touching production data

Current artefact output:

- [outputs/replay/p1_replay_lifecycle_drift_guard_20260509.json](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge/outputs/replay/p1_replay_lifecycle_drift_guard_20260509.json)
- script result: `SKIPPED_ENV_UNAVAILABLE` because the local replay DB fixture is not present in this workspace

## 4. Browser E2E Result

Added a lifecycle-specific browser E2E scaffold:

- [tests/test_replay_lifecycle_browser_e2e.py](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge/tests/test_replay_lifecycle_browser_e2e.py)

What it is designed to verify when browser tooling is available:

- lifecycle dropdown exists
- URL state `rp_lc` restores correctly
- lifecycle badge column exists and renders the selected lifecycle state
- mocked replay API responses can drive the page without production writes

Current execution status in this workspace:

- `SKIPPED_ENV_UNAVAILABLE`
- `pytest` is not installed here
- browser automation cannot be exercised from this environment

## 5. Non-ONLINE Catalog Policy

I did not change production lifecycle data. The current policy remains fixture/sample only:

- UI/API support all lifecycle states
- current catalog population is still incomplete beyond the existing ONLINE data
- non-ONLINE states must be treated as infrastructure-ready, not as fully populated production catalog state
- any future sample catalog work must stay read-only and fixture-only

## 6. Validation Results

- `python3 -m py_compile scripts/check_replay_lifecycle_drift.py tests/test_replay_lifecycle_drift_guard.py tests/test_replay_lifecycle_browser_e2e.py` — PASS
- `python3 scripts/check_replay_lifecycle_drift.py --json-out outputs/replay/p1_replay_lifecycle_drift_guard_20260509.json` — PASS with skipped DB availability report
- `python3 -m pytest tests/test_replay_lifecycle_drift_guard.py tests/test_replay_lifecycle_browser_e2e.py -q` — SKIPPED_ENV_UNAVAILABLE (`pytest` not installed)
- `python3 -m pytest tests/test_replay_api_contract.py tests/test_replay_freshness_cadence.py tests/test_replay_browser_smoke.py -q` — SKIPPED_ENV_UNAVAILABLE (`pytest` not installed)

## 7. What Was Not Changed

- No replay API behavior was changed.
- No replay UI behavior was changed.
- No lifecycle registry data or production DB rows were changed.
- No strategy mining, edge discovery, or replay generation was run.
- No branch protection settings were changed.
- No direct push to `main`, force push, or admin override was used.

## 8. Remaining Risks

- local `pytest` is unavailable in this workspace
- the local replay DB fixture is missing, so the drift guard can only emit a skipped artefact here
- browser E2E remains unexecuted in this environment
- non-ONLINE lifecycle catalog population is still incomplete
- the audit trail for lifecycle work remains split across multiple report branches and PRs

## 9. Recommended Next Action

1. Run the new lifecycle drift guard and browser E2E in a workspace that has `pytest` and browser tooling installed.
2. If a fixture DB is available, rerun the drift guard against it and compare registry vs replay rows.
3. Keep future lifecycle work fixture-only and read-only unless a real P0 bug is documented.

## 10. Final Marker

P1_REPLAY_LIFECYCLE_HARDENING_BLOCKED_ENV