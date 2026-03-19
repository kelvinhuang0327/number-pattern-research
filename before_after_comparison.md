# Before/After Comparison (Phase 5)

Date: 2026-03-13

## 1) API Host Management
Before:
- API origins hardcoded in many files (`App`, `DataProcessor`, `RecordManager`, `SmartBettingComponent`, strategy classes, auto-learning manager).

After:
- Added shared resolver `src/config/apiConfig.js`.
- Refactored key modules to use `getApiOrigin()` / `getApiUrl()`.
- Result: consistent backend target and lower env drift risk.

## 2) Auto-Learning Data Sync Stability
Before:
- `AutoLearningManager.syncDataToBackend()` called nonexistent `dataProcessor.getDataFromIndexedDB(...)`.

After:
- Replaced with existing `dataProcessor.getDataRange('all', lotteryType)`.
- Result: removed confirmed runtime dead path.

## 3) Endpoint Consistency in Strategies
Before:
- Strategy classes used mixed endpoint conventions (`localhost`, `127.0.0.1`, relative path).

After:
- Unified endpoint construction in key strategy classes through shared API helper.
- Result: predictable network behavior across strategy selection.

## 4) User-Visible Behavior
Before:
- Behavior relied on mixed URL assumptions.

After:
- No intentional business logic changes.
- UI/feature set preserved; only transport and broken call path stabilized.

## 5) Risk Delta
- Reduced: host mismatch, CORS drift, dead sync call.
- Residual: `App.js` complexity remains high, dual-bet legacy path still broad.

## 6) Visual System Modernization
Before:
- Mixed dark-theme tokens and many inline style blocks causing inconsistent visual hierarchy.
- Duplicate header markup increased layout fragility.

After:
- Added `styles_trend_2026.css` as a non-breaking override layer (modern light editorial style + data cockpit accents).
- Updated font system to `Sora` + `Noto Serif TC` for clearer hierarchy.
- Added accessibility polish (`:focus-visible`, contrast tuning) and mobile one-column fallbacks for complex grid blocks.
- Removed duplicate header markup and kept `Master Guide` entry in the primary header flow.
