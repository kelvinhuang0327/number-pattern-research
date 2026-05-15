# Unused or Legacy Features (Phase 1)

Date: 2026-03-13
Policy: uncertain items default to `HIDE`, not `REMOVE`

## High-Confidence Legacy/Risk Items

1. Missing data access method
- Location: `src/ui/AutoLearningManager.js`
- Evidence: calls `dataProcessor.getDataFromIndexedDB(...)`, method not implemented.
- Current impact: sync flow can fail at runtime.
- Classification: `FIX_REQUIRED` (not a removable feature).

2. Hardcoded API hosts spread across modules
- Locations:
  - `src/core/App.js`
  - `src/core/DataProcessor.js`
  - `src/ui/RecordManager.js`
  - `src/ui/components/SmartBettingComponent.js`
  - `src/ui/AutoLearningManager.js`
  - `src/services/ApiClient.js`
- Impact: environment inconsistency and brittle behavior.
- Classification: `MERGE_TO_SHARED_CONFIG`.

3. Backup source file in active tree
- Location: `src/core/App.js.backup`
- Impact: maintenance confusion.
- Classification: `HIDE_FROM_BUILD` / archive outside source path later.

## Medium-Confidence Legacy Items

1. Dual-bet path complexity under partially hidden UI
- Locations: `App.js`, `UIDisplayHandler.js`, `AutoLearningManager.js`, `index.html`
- Evidence: handlers and DOM bindings still active; some navigation entries hidden.
- Impact: high test burden, unclear product intent.
- Classification: `HIDE_FIRST`, defer remove until product confirmation.

2. Mixed endpoint selection logic in strategy classes
- Locations: `APIStrategy`, `BackendOptimizedStrategy`, `CoreSatelliteStrategy`, `ZoneSplitStrategy`
- Impact: duplicate endpoint conventions and drift risk.
- Classification: `MERGE_TO_SHARED_ORIGIN_RESOLVER`.

## Keep List (Confirmed Active)
- Upload/validation flow (`/api/data/validate-csv`, `/api/data/upload`)
- History CRUD (`/api/draws*`)
- Prediction and range prediction (`/api/predict*`, `/api/predict-with-range`)
- Auto-learning schedule and optimize (`/api/auto-learning/*`)
- Smart betting wheel endpoints (`/api/wheel/*`)
