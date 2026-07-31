# Executive Summary
PR #9's browser E2E failure was caused by the mocked replay history route not matching the real request URL once query parameters were added. The browser test now matches the history request by path, preserves the expected REJECTED lifecycle payload, and keeps Replay UI/API behavior unchanged.

# Latest Failure Summary
The latest browser CI failure occurred in `tests/test_replay_lifecycle_browser_e2e.py` at the assertion that the first lifecycle cell contains `REJECTED`. The cell text was `尚無記錄`, and the browser log showed `GET /api/replay/history?...lifecycle_status=REJECTED` returning 404.

# Root Cause
The route mock checked `url.endswith("/api/replay/history")`, but the real request includes query parameters, so the mock was bypassed and the request fell through to the local static server. That produced a 404 and left the table in its empty-state rendering.

# Mock Route / Payload Fix
The test now parses the request URL with `urlparse`, matches the history endpoint by path, and reads the `lifecycle_status` query parameter so the mocked payload stays aligned with the request. The mock still returns a REJECTED row with the same response shape expected by the browser UI, including `strategy_id`, `strategy_name`, `target_draw`, `replay_status`, `reject_reason`, `predicted_numbers`, `actual_numbers`, `hit_numbers`, `hit_count`, and `strategy_lifecycle_status`.

# Validation Result
Local syntax validation passed with `python3 -m py_compile tests/test_replay_lifecycle_browser_e2e.py`. The browser pytest command `/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest tests/test_replay_lifecycle_browser_e2e.py -q` completed with `1 skipped`, which is the honest local outcome when Playwright/browser tooling is unavailable. The default replay validation also passed with `57 passed, 32 skipped`.

# Diff Scope
Expected code diff before commit: only [tests/test_replay_lifecycle_browser_e2e.py](tests/test_replay_lifecycle_browser_e2e.py). Allowed report addition: this file.

# What Was Not Changed
Replay UI code was not changed. Replay API code was not changed. Lifecycle registry semantics were not changed. Active strategy state was not changed. Branch protection policy was not changed. DB artifacts were not changed.

# Remaining Risks
The fix addresses the current 404/mock-miss path. If the UI changes the history response shape or another endpoint becomes query-sensitive, the browser lane could still surface a new data mismatch on the next CI run.

# Recommended Next Action
Commit the browser test fix and this report, push to `codex/p0-replay-lifecycle-browser-e2e-ci-enablement`, then rerun PR #9 checks to confirm whether `replay-browser-e2e-validation` turns green.

# Final Marker
P0_REPLAY_LIFECYCLE_BROWSER_E2E_CI_PR9_MOCK_HISTORY_FIX_BLOCKED