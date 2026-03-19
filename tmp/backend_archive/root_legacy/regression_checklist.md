# Regression Checklist (Phase 5)

Date: 2026-03-13
Scope: Frontend-only safe refactor in `index.html` + `src/**`

## Automated Checks
- [x] Static error check on `src/config/apiConfig.js`
- [x] Static error check on `src/core/App.js` after patch
- [x] Search check: no remaining `getDataFromIndexedDB(` references in `src/**`
- [x] Search check: no hardcoded `http://localhost:8002` / `127.0.0.1:8002` in `src/**` except shared config origin
- [x] Static error check on `src/ui/AutoLearningManager.js` after sync-path patch
- [x] Static error check confirms `runSimulation()` complexity warning removed
- [x] Static error check on `src/core/handlers/SimulationHandler.js` after extraction
- [x] Delegation check: `App.runSimulation()` and `App.runCollaborativeSimulation()` route to handler
- [x] Static error check on `src/core/handlers/PredictionHandler.js` after extraction
- [x] Delegation check: `App.runPrediction()` and `App.generateNextPeriodPrediction(...)` route to handler
- [x] Static error check on `index.html` after header structure cleanup
- [x] Static error check on `styles_trend_2026.css` after contrast/accessibility tuning
- [x] Inline-style reduction applied to simulation/smartbetting/autolearning with utility classes
- [x] Label association check passed for upgraded form controls (`for`/`id` linkage)
- [x] Autolearning advanced panels migrated to utility classes without changing control IDs
- [x] Static error check remained clean after autolearning utility migration
- [x] Schedule-row and best-config panels migrated to utility classes
- [x] Static error check remained clean after autolearning final migration slice
- [x] Prediction action row and confidence-note styling migrated to utility classes
- [x] Smartbetting strategy-row label/button inline styles migrated to utility classes
- [x] Smartbetting analysis dashboard template migrated to utility classes
- [x] Autolearning dual-bet detail panel migrated to utility classes
- [x] Autolearning top-card hidden/spacing utility migration completed
- [x] Static error check remained clean after latest utility additions
- [x] Method-description and simulation-next-prediction inline styles migrated to utility classes
- [x] Static error check remained clean after simulation detail migration
- [x] Smartbetting dual-bet/entropy result blocks migrated to utility classes
- [x] Autolearning advanced optimization and KPI display styles migrated to utility classes
- [x] Header/upload/play-mode inline styles migrated to utility classes
- [x] Hidden nav/section toggles standardized to `ui-hidden`
- [x] Static error check remained clean after thirteenth/fourteenth-round migration
- [x] Prediction/smartbetting section hidden-state inline styles migrated to utility classes
- [x] Record modal hidden/grid inline styles migrated to utility classes
- [x] Root `index.html` inline-style scan shows only a small intentional residual set (play-mode accents + upload select)
- [x] Upload-filter and play-mode residual inline styles migrated to utility classes
- [x] Root `index.html` inline-style scan now returns zero results
- [x] Static error check remained clean after final inline-style elimination

## Manual Functional Checks (To Execute in Browser)
- [ ] Upload TXT/CSV and verify validation + upload success
- [ ] Open history page and test create/update/delete draw record
- [ ] Run prediction using range-based flow (`optimized_ensemble`)
- [ ] Run smart betting entropy 8-bet generation
- [ ] Run auto-learning sync data action
- [ ] Trigger auto-learning evaluate strategies
- [ ] Validate backend health degradation/recovery notification

## Known Non-Blocking Existing Issue
- None detected in patched frontend files via static diagnostics.
