# P27A — Replay Page UI Console 404 Cleanup

**Date**: 2026-05-21  
**Branch**: `p27a-replay-ui-console-404-cleanup`  
**Classification**: `P27A_REPLAY_UI_CONSOLE_404_CLEANUP_MERGED_TO_MAIN`  
**Tests**: 13/13 PASS  
**Production rows**: 12460 (unchanged)  
**DB writes**: None  

---

## Problem

When a real user navigates the replay page, five browser console errors appear:

1. `❌ Missing elements for method description card` — fired from `App.js` when card DOM elements absent
2. `Failed to load resource: 404` — browser-native, caused by wrong-port fetches
3. `[replay] freshness load failed` — `index.html` IIFE uses `window.API_BASE` but it was never set; `BASE` resolved to `/api/replay` (relative), hitting port 8081 (static server) instead of 8002
4. `[P7] lifecycle registry load error:` — same root cause + logged as `console.error`
5. `/api/performance/regime 404` — `UIManager.js` used bare relative URL `/api/performance/regime`, hitting port 8081

---

## Root Cause

The replay page IIFE reads `window.API_BASE` but it was never written in the HTML. When the app is served via a static file server on port 8081, relative `/api/...` paths hit 8081 (no API routes) → 404.

`UIManager.js` independently hardcoded a bare relative path for `/api/performance/regime`.

---

## Fixes

### Fix 1 — `src/core/App.js`
Removed `console.error('❌ Missing elements for method description card')`. Now silently returns when DOM elements are absent (expected on non-prediction pages).

### Fix 2 & 3 — `src/ui/UIManager.js`
- Added `import { apiClient }` from `ApiClient.js` (which already holds `http://127.0.0.1:8002`)
- Changed `fetch('/api/performance/regime')` → ``fetch(`${apiClient.baseUrl}/api/performance/regime`)``
- Demoted waterline catch from `console.error` → `console.warn`

### Fix 4 & 5 — `index.html`
- Injected `window.API_BASE` early in `<head>` before any scripts:
  ```js
  if (typeof window !== 'undefined' && window.location.port !== '8002') {
    window.API_BASE = window.location.protocol + '//' + window.location.hostname + ':8002';
  }
  ```
  This sets the correct API origin when the frontend is served from a different port (8081). When served from the backend directly, it's a no-op.
- Demoted `[P7] lifecycle registry load error` from `console.error` → `console.warn`

---

## Tests

File: `tests/test_p27a_replay_ui_console_404_cleanup.py`

| Class | Test | Result |
|-------|------|--------|
| TestMethodDescriptionCard | test_no_console_error_missing_elements | PASS |
| TestMethodDescriptionCard | test_silent_return_on_missing_elements | PASS |
| TestWaterlineApiUrl | test_no_bare_relative_regime_url | PASS |
| TestWaterlineApiUrl | test_uses_apiclient_base | PASS |
| TestWaterlineApiUrl | test_imports_apiclient | PASS |
| TestWaterlineApiUrl | test_waterline_error_demoted_to_warn | PASS |
| TestIndexHtmlFixes | test_window_api_base_script_present | PASS |
| TestIndexHtmlFixes | test_api_base_uses_port_8002 | PASS |
| TestIndexHtmlFixes | test_api_base_script_before_replay_iife | PASS |
| TestIndexHtmlFixes | test_lifecycle_error_demoted | PASS |
| TestIndexHtmlFixes | test_freshness_still_warn | PASS |
| TestIndexHtmlFixes | test_no_console_error_in_replay_iife | PASS |
| TestIndexHtmlFixes | test_production_rows_unchanged | PASS |

**13/13 PASS**

---

## Files Changed

- `index.html` — Added `window.API_BASE` injection; demoted lifecycle console.error → warn
- `src/ui/UIManager.js` — Absolute URL for regime endpoint; import apiClient; demoted error → warn
- `src/core/App.js` — Silent return (no console.error) for missing method description card DOM

## Files Added

- `tests/test_p27a_replay_ui_console_404_cleanup.py`
- `outputs/replay/p27a_replay_ui_console_404_cleanup_20260521.json`
- `docs/replay/p27a_replay_ui_console_404_cleanup_20260521.md`
