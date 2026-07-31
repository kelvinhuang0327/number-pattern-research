# P0 Replay Lifecycle Browser E2E CI Enablement

## 1. Executive Summary

This change enables real Replay Lifecycle browser E2E execution in CI-capable environments by adding a dedicated GitHub Actions job that installs Playwright and Chromium before running the lifecycle browser E2E test. Local or tooling-poor environments still behave honestly: the browser test continues to skip when Playwright is unavailable, and it never reports a false `PASS` unless the browser path actually runs.

The current local environment does not have the `playwright` Python package installed, so the browser test currently resolves to an honest `SKIP` here. The CI job fills that gap without changing Replay UI/API behavior, lifecycle registry semantics, or branch protection.

## 2. Browser Tooling Diagnosis

Local tooling status in this workspace:

- `playwright` Python package: missing
- `playwright.sync_api`: missing
- Chromium/browser launch: not runnable locally because the Playwright package is absent

Observed failure / skip reason:

- Python import check failed with `ModuleNotFoundError: No module named 'playwright'`
- The browser E2E test therefore remains an honest skip in this environment via `pytest.importorskip("playwright.sync_api", reason="Playwright browser tooling unavailable")`

## 3. CI-Capable Setup Path

Added a dedicated workflow job to `.github/workflows/replay-governance-ci.yml`:

- job name: `replay-browser-e2e-validation`
- installs validation dependencies plus `playwright`
- runs `python -m playwright install --with-deps chromium`
- executes `python -m pytest tests/test_replay_lifecycle_browser_e2e.py -q`

This is the minimal scoped setup path because it keeps browser enablement inside CI, avoids broad dependency churn, and leaves the test itself responsible for honest skipping when tooling is absent.

## 4. Validation Evidence

Tooling and validation commands run in this workspace:

- Local browser tooling check:
  - result: `playwright` missing
  - browser E2E remains `SKIP`
- Mismatch fixture validation:
  - build: `synthetic_only=1`
  - integrity: `PASS`
  - drift guard: `BLOCKED`
- Aligned fixture validation:
  - build: `synthetic_only=1`
  - integrity: `PASS`
  - drift guard: `PASS`
- Multi-state fixture validation:
  - build: `synthetic_only=1`
  - integrity: `PASS`
  - drift guard: `PASS`
  - lifecycle coverage: `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED`
- Focused pytest bundle:
  - `4 passed, 1 skipped`
  - browser E2E skip reason remains explicit and honest
- Current focused validation snapshot:
  - `python3 -m py_compile tests/test_replay_lifecycle_browser_e2e.py` PASS
  - `/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest tests/test_replay_lifecycle_browser_e2e.py -q` SKIPPED because Playwright/browser tooling is unavailable locally
  - `/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py` PASS with `57 passed, 32 skipped`
- Replay default validation:
  - `57 passed, 32 skipped`

## 5. PASS / SKIP Distinction

The browser path did not claim a full pass locally. It stayed skipped because Playwright is absent in this environment. That is the correct behavior for non-CI-capable setups.

The new workflow job is what allows the browser path to become a real execution lane in CI-capable environments.

## 6. What Was Not Changed

- Replay UI behavior
- Replay API behavior
- lifecycle registry semantics
- production DB data
- DB binaries
- replay generation
- strategy mining or edge discovery
- branch protection
- required checks policy

## 7. Remaining Risks

- Browser E2E still depends on CI/browser tooling availability for real execution.
- The local workspace remains unable to launch Chromium until Playwright is installed.
- The browser lane is informative for now; it should not be promoted to required until a successful CI run proves stability.

## 8. Recommendation

Keep the browser lane as a non-required CI validation job for now. After at least one successful CI run on pull request and push events, and after the failure mode remains limited to honest skips only in tooling-poor environments, the lane can be considered for promotion to required status.

## 9. Files Changed

- [.github/workflows/replay-governance-ci.yml](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge/.github/workflows/replay-governance-ci.yml)

## 10. Final Marker

P0_REPLAY_LIFECYCLE_BROWSER_E2E_CI_ENABLEMENT_READY