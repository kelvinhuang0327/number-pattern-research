# Change Impact Log (Phase 4)

Date: 2026-03-13
Scope: Frontend-only refactor and stabilization

## Change Set A: API Origin Unification
Files:
- `src/config/apiConfig.js` (new)
- `src/services/ApiClient.js`
- `src/core/App.js`
- `src/core/DataProcessor.js`
- `src/ui/RecordManager.js`
- `src/ui/components/SmartBettingComponent.js`
- `src/ui/AutoLearningManager.js`
- `src/engine/strategies/APIStrategy.js`
- `src/engine/strategies/BackendOptimizedStrategy.js`
- `src/engine/strategies/CoreSatelliteStrategy.js`
- `src/engine/strategies/ZoneSplitStrategy.js`

Impact:
- Positive: removes endpoint fragmentation and host drift.
- Risk: any module expecting relative `/api` semantics now depends on explicit origin helper.
- Mitigation: helper centralizes local/prod host logic; quick revert is localized.

## Change Set B: Auto-learning Sync Dead Path Fix
File:
- `src/ui/AutoLearningManager.js`

Impact:
- Positive: removes runtime break from nonexistent `getDataFromIndexedDB` call.
- Risk: data volume from `getDataRange('all', lotteryType)` may be large.
- Mitigation: existing backend sync endpoint handles bulk upload; keep existing MAX optimization safeguards.

## Change Set C: App Simulation Flow Decomposition
File:
- `src/core/App.js`

Refactor:
- `runSimulation()` split into helpers:
  - `getSimulationAllData()`
  - `getSimulationTargetsByYear(...)`
  - `runSimulationByTargets(...)`
  - `runSingleSimulationTarget(...)`

Impact:
- Positive: lower complexity, easier testing and debugging.
- Risk: subtle behavior change in per-target loop ordering or skip rules.
- Mitigation: preserved logs, preserved training-data threshold, preserved scoring and side effects.
