# P329A Console Log Summary

Captured via `--enable-logging=stderr --v=1` while headless Chrome loaded `http://127.0.0.1:8931/index.html` (full log: `chrome_console_stderr.log`, 14,757 lines including Chromium's own internal component/signin verbose logging — filtered below to page `CONSOLE` entries).

## Page console activity (app JS, not Chromium internals)
- Normal app-init logs from `App.js`, `AutoLearningManager.js`, `DataProcessor.js`, `UIManager.js`, `ApiClient.js` — instantiation, method setup, catalog fetch attempts.
- Several `TypeError: Failed to fetch` / `Network error, retrying...` entries — **expected**: no backend API server (`:8002`) was started for this task (only a static file server was run, per the read-only/no-new-analysis constraint). These affect health-check/backend-driven panels (AutoLearningManager, live prediction fetch), not the static D5 baseline artifacts.
- `[P29] catalog load failed (non-blocking): TypeError: Failed to fetch` and `[waterline] update skipped: Failed to fetch` — same cause (no backend), explicitly logged as non-blocking by the app itself.

## D5-baseline-specific check
Filtered all console lines for `d5|baseline|p325a|p326a|p320a|p299a`: **zero matches**. No error or warning was logged for the D5 baseline UI's own data path — its data loads from the static `public/demo-data/lottery-d5/...` JSON files (served by the temporary static server), independent of the unavailable backend API.

## Conclusion
No loader-failure string, error, or warning is associated with the D5 Budget Bias / Equal-Budget Baseline feature itself. All console errors present are attributable to the intentionally-not-started backend API and are unrelated to the values being verified.
