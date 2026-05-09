# Executive Summary
PR #9's browser E2E lane was still failing because the lifecycle row assertion was reading a table cell from a broader `tbody` scope instead of the replay history table body. The test now scopes the row assertion to `#rp-hist-body`, preserving the existing UI behavior and keeping Replay UI/API semantics unchanged.

# Latest Failure Summary
The latest browser CI failure was `assert 'REJECTED' in (first_row_lifecycle.text_content() or '')`, where the actual text was `尚無記錄`. That meant the locator had resolved to an empty-state row outside the intended replay history table scope.

# Root Cause
The locator `tbody tr:not(.rp-detail-row) td` was too broad. On this page, it can resolve to other history-related tables or empty-state content, so the assertion was reading the wrong DOM subtree instead of the replay history table body.

# Row Locator Scope Fix
The browser test now uses `#rp-hist-body tr:not(.rp-detail-row) td` for the lifecycle row assertion and the companion cell check. The test still requires `REJECTED` to appear in the mocked replay history row and does not accept `尚無記錄` as a passing result.

# Validation Result
Local syntax validation passed with `python3 -m py_compile tests/test_replay_lifecycle_browser_e2e.py`. The browser pytest command `/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest tests/test_replay_lifecycle_browser_e2e.py -q` returned `1 skipped`, which is the honest local result when Playwright/browser tooling is unavailable. Default replay validation also passed with `57 passed, 32 skipped`.

# Diff Scope
Expected code diff before commit: only [tests/test_replay_lifecycle_browser_e2e.py](tests/test_replay_lifecycle_browser_e2e.py). Allowed report addition: this file.

# What Was Not Changed
Replay UI code was not changed. Replay API code was not changed. Lifecycle registry semantics were not changed. Active strategy state was not changed. Branch protection policy was not changed. DB artifacts were not changed.

# Remaining Risks
The fix addresses the current locator-scope mismatch. If the browser UI changes the replay history table structure, the selector may need to be updated again on the next CI run.

# Recommended Next Action
Commit the row-scope fix and report, push to `codex/p0-replay-lifecycle-browser-e2e-ci-enablement`, then rerun PR #9 checks.

# Final Marker
P0_REPLAY_LIFECYCLE_BROWSER_E2E_CI_PR9_ROW_SCOPE_FIX_BLOCKED