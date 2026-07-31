# Executive Summary
PR #9's browser E2E lane had a third current-head failure caused by a hidden lifecycle header, `生命週期`, being treated as if it needed to become visible. The local fix changes the test to wait for the header to be attached, which preserves the existing UI behavior and keeps Replay UI/API semantics unchanged.

# Third Failure Summary
The current-head browser run failed at the lifecycle table assertion because the test waited for `th:has-text("生命週期")` to become visible, but the header is intentionally present in the DOM while hidden. This is the third browser-only failure in the PR #9 lane.

# Root Cause
The browser test used a visibility-based wait on a DOM node that exists but is hidden. That assumption does not match the Replay page behavior, so Playwright timed out even though the header was already attached.

# Fix Applied
The test in [tests/test_replay_lifecycle_browser_e2e.py](tests/test_replay_lifecycle_browser_e2e.py) now waits for `th:has-text("生命週期")` with `state='attached'` instead of the default visible state. No Replay UI, API, or lifecycle registry code was changed.

# Validation Result
Local syntax validation passed with `python3 -m py_compile tests/test_replay_lifecycle_browser_e2e.py`. Browser pytest also ran with `/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest tests/test_replay_lifecycle_browser_e2e.py -q` and was skipped because the local Playwright browser was unavailable.

# Diff Scope
Expected code diff before commit: only [tests/test_replay_lifecycle_browser_e2e.py](tests/test_replay_lifecycle_browser_e2e.py). Allowed report addition: this file.

# What Was Not Changed
Replay UI code was not changed. Replay API code was not changed. Lifecycle registry semantics were not changed. Active strategy state was not changed. Branch protection policy was not changed. Production DB artifacts were not changed.

# Remaining Risks
The browser CI lane still needs to rerun after push. If another hidden-DOM assumption exists in the same flow, the next CI run will expose it.

# Recommended Next Action
Push this fix to `codex/p0-replay-lifecycle-browser-e2e-ci-enablement`, then rerun PR #9 checks and confirm whether `replay-browser-e2e-validation` turns green.

# Final Marker
P0_REPLAY_LIFECYCLE_BROWSER_E2E_CI_PR9_CHECKS_PENDING