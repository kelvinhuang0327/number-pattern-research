# Frontend Risk Register (Phase 4)

Date: 2026-03-13

## R-001 API origin misconfiguration
- Severity: High
- Likelihood: Medium
- Description: Wrong origin selection can break all API requests.
- Mitigation: `src/config/apiConfig.js` keeps deterministic localhost/prod mapping.
- Verification: grep check for hardcoded hosts in `src/**` and smoke test key flows.

## R-002 Large payload during auto-learning sync
- Severity: Medium
- Likelihood: Medium
- Description: `getDataRange('all', lotteryType)` may produce large request body.
- Mitigation: Existing optimization data caps and backend handling retained.
- Verification: manual sync test in auto-learning panel.

## R-003 Simulation regression after method split
- Severity: Medium
- Likelihood: Low
- Description: Refactor could alter target loop and success count semantics.
- Mitigation: helper methods keep same conditions and side effects.
- Verification: run simulation on known month/year and compare result shape.

## R-004 Legacy dual-bet hidden paths
- Severity: Medium
- Likelihood: Medium
- Description: hidden UI + active handlers can still trigger edge cases.
- Mitigation: keep HIDE-first; do not remove until product confirmation.
- Verification: explicit manual test for dual-bet actions and empty-state handling.
