# Frontend Audit Report (Phase 1)

Date: 2026-03-13
Scope: `index.html`, `src/**` frontend modules only
Mode: Non-destructive audit

## 1. Current Architecture Snapshot
- Runtime: Vanilla HTML + CSS + ES Modules (no React/TS/Tailwind runtime)
- Entry: `index.html` -> `src/main.js` -> `src/core/App.js`
- Composition:
  - App orchestration: `src/core/App.js`
  - Data layer: `src/core/DataProcessor.js`, `src/services/ApiClient.js`
  - UI layer: `src/ui/**`
  - Strategy/engine layer: `src/engine/**`
- Page style: Single-page, section-based navigation (`data-section` + `*-section`)

## 2. Page Inventory
- `upload-section` (active)
- `analysis-section` (hidden by default)
- `simulation-section`
- `prediction-section` (hidden by default)
- `history-section`
- `smartbetting-section` (hidden by default)
- `autolearning-section` (hidden by default)

## 3. Critical Findings

### High
1. API base URL fragmentation
- Hardcoded domains appear in multiple modules:
  - `http://localhost:8002`
  - `http://127.0.0.1:8002`
  - relative `/api/...`
- Risk: environment drift, CORS/IPv4 mismatch, maintenance overhead.

2. Missing method call in auto-learning sync path
- `src/ui/AutoLearningManager.js` calls `this.dataProcessor.getDataFromIndexedDB(...)`
- No implementation found in `src/core/DataProcessor.js` or other frontend modules.
- Risk: runtime failure when sync action is triggered.

### Medium
1. Over-coupled app orchestration
- `src/core/App.js` contains mixed concerns: section orchestration, prediction flow, smart dual-bet rendering, backend health checking.
- Risk: regression surface too wide for feature changes.

2. Mixed API access patterns
- Some modules use `apiClient`, others use direct `fetch`.
- Risk: timeout/retry/error behavior inconsistent.

3. Hidden but live feature logic
- Several dual-bet and smart-dual-bet handlers remain active in code while corresponding UI entry points are partially hidden.
- Risk: hard-to-test dormant paths.

### Low
1. Multiple backup/legacy files in source tree (e.g., `App.js.backup`)
- Risk: accidental reference or confusion during refactor.

## 4. Backend Contract Check (Summary)
Validated core frontend-referenced routes exist in backend routes:
- Data CRUD/upload/validate: `/api/data/*`, `/api/draws*`
- Prediction: `/api/predict*`, `/api/predict-with-range`
- Smart betting: `/api/wheel/*`, `/api/predict-entropy-8-bets`
- Auto learning: `/api/auto-learning/*`
- Admin health: `/health`, `/api/ping`

## 5. Refactor Safety Rules Applied
- Keep behavior and API contracts unchanged.
- Prefer central API URL resolution.
- Do not remove uncertain features; use HIDE-first strategy.
- Touch frontend only (`index.html`, `src/**`).

## 6. Recommended Immediate Fixes
1. Introduce single API origin resolver and reuse it across modules.
2. Replace broken `getDataFromIndexedDB` call with existing `getDataRange('all', lotteryType)` fallback path.
3. Keep dual-bet logic but add clear retirement classification and test checklist before removal.
