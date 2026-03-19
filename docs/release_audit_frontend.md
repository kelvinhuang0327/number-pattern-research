# Frontend Release Audit
**Date**: 2026-03-19
**Auditor**: Claude Code

---

## 1. Entry Point Chain

```
index.html
  ├─ <link> styles.css?v=15
  ├─ <link> professional-design.css?v=15
  ├─ <link> src/ui/progress.css
  ├─ <script> https://unpkg.com/lucide@latest        (CDN icons)
  ├─ <script> cdn.jsdelivr.net/chart.js@4.4.0        (CDN charts)
  ├─ <script> cdn.jsdelivr.net/@tensorflow/tfjs@4.9.0 (CDN TF.js)
  └─ <script type="module"> src/main.js?v=11
       └─ import App from src/core/App.js
            ├─ src/core/DataProcessor.js
            ├─ src/data/StatisticsService.js
            ├─ src/engine/PredictionEngine.js
            │    ├─ src/engine/strategies/FrequencyStrategy.js
            │    ├─ src/engine/strategies/TrendStrategy.js
            │    ├─ src/engine/strategies/MarkovStrategy.js
            │    ├─ src/engine/strategies/MonteCarloStrategy.js
            │    ├─ src/engine/strategies/BayesianStrategy.js
            │    ├─ src/engine/strategies/DeviationStrategy.js
            │    ├─ src/engine/strategies/UnifiedEnsembleStrategy.js
            │    ├─ src/engine/strategies/MLStrategy.js
            │    ├─ src/engine/strategies/CollaborativeStrategy.js
            │    ├─ src/engine/strategies/AutoOptimizeStrategy.js
            │    ├─ src/engine/strategies/APIStrategy.js
            │    ├─ src/engine/strategies/BackendOptimizedStrategy.js
            │    ├─ src/engine/strategies/ZoneSplitStrategy.js
            │    ├─ src/engine/strategies/CoreSatelliteStrategy.js
            │    ├─ src/engine/strategies/OddEvenBalanceStrategy.js
            │    ├─ src/engine/strategies/ZoneBalanceStrategy.js
            │    ├─ src/engine/strategies/HotColdMixStrategy.js
            │    ├─ src/engine/strategies/SumRangeStrategy.js
            │    ├─ src/engine/strategies/WheelingStrategy.js
            │    ├─ src/engine/strategies/NumberPairsStrategy.js
            │    ├─ src/engine/strategies/StatisticalAnalysisStrategy.js
            │    └─ src/utils/Constants.js
            │         └─ src/utils/LotteryTypes.js  (re-exported)
            ├─ src/ui/UIManager.js
            │    └─ src/utils/LotteryTypes.js  (dynamic import)
            ├─ src/ui/ChartManager.js
            ├─ src/ui/components/SmartBettingComponent.js
            ├─ src/engine/QuickPredictionService.js
            │    └─ src/utils/LotteryTypes.js
            ├─ src/utils/Constants.js
            ├─ src/ui/AutoLearningManager.js
            │    └─ src/utils/LotteryTypes.js
            ├─ src/services/ApiClient.js
            ├─ src/ui/ProgressManager.js
            ├─ src/ui/RecordManager.js
            ├─ src/core/handlers/FileUploadHandler.js
            ├─ src/core/handlers/DataHandler.js
            ├─ src/core/handlers/UIDisplayHandler.js
            ├─ src/core/handlers/SimulationHandler.js
            ├─ src/core/handlers/PredictionHandler.js
            └─ src/config/apiConfig.js
```

---

## 2. Complete Active Frontend Files (38 files)

### Core (3)
| File | Status | Notes |
|------|--------|-------|
| src/main.js | ✅ ACTIVE | Entry point |
| src/core/App.js | ✅ ACTIVE | Main orchestrator |
| src/core/DataProcessor.js | ✅ ACTIVE | Data parsing & normalization |

### Handlers (5)
| File | Status | Notes |
|------|--------|-------|
| src/core/handlers/FileUploadHandler.js | ✅ ACTIVE | File upload logic |
| src/core/handlers/DataHandler.js | ✅ ACTIVE | Data operations |
| src/core/handlers/UIDisplayHandler.js | ✅ ACTIVE | UI display updates |
| src/core/handlers/SimulationHandler.js | ✅ ACTIVE | Simulation logic |
| src/core/handlers/PredictionHandler.js | ✅ ACTIVE | Prediction flow |

### Engine (2)
| File | Status | Notes |
|------|--------|-------|
| src/engine/PredictionEngine.js | ✅ ACTIVE | Strategy orchestrator |
| src/engine/QuickPredictionService.js | ✅ ACTIVE | Quick prediction |

### Strategies (21)
All 21 strategy files in `src/engine/strategies/` are **imported and instantiated** by PredictionEngine.js:
- FrequencyStrategy, TrendStrategy, MarkovStrategy, MonteCarloStrategy
- BayesianStrategy, DeviationStrategy, UnifiedEnsembleStrategy
- MLStrategy, CollaborativeStrategy, AutoOptimizeStrategy
- APIStrategy, BackendOptimizedStrategy, ZoneSplitStrategy, CoreSatelliteStrategy
- OddEvenBalanceStrategy, ZoneBalanceStrategy, HotColdMixStrategy
- SumRangeStrategy, WheelingStrategy, NumberPairsStrategy, StatisticalAnalysisStrategy

### UI (5)
| File | Status | Notes |
|------|--------|-------|
| src/ui/UIManager.js | ✅ ACTIVE | Main UI orchestrator |
| src/ui/ChartManager.js | ✅ ACTIVE | Chart rendering |
| src/ui/AutoLearningManager.js | ✅ ACTIVE | Auto-learning UI |
| src/ui/RecordManager.js | ✅ ACTIVE | Record management |
| src/ui/ProgressManager.js | ✅ ACTIVE | Progress display |

### UI Components (1 active, 1 uncertain)
| File | Status | Notes |
|------|--------|-------|
| src/ui/components/SmartBettingComponent.js | ✅ ACTIVE | Imported by App.js |
| src/ui/components/AssetDoublingPlanComponent.js | ⚠️ UNSURE | Uses `window.` global reg, not in App.js import chain. Likely loaded via dynamic script OR dead code. |

### Services (1)
| File | Status | Notes |
|------|--------|-------|
| src/services/ApiClient.js | ✅ ACTIVE | API communication |

### Data Layer (1)
| File | Status | Notes |
|------|--------|-------|
| src/data/StatisticsService.js | ✅ ACTIVE | Statistics calculations |

### Utils (2 active, 1 dead)
| File | Status | Notes |
|------|--------|-------|
| src/utils/Constants.js | ✅ ACTIVE | Constants & rules |
| src/utils/LotteryTypes.js | ✅ ACTIVE | Lottery type definitions |
| src/utils/WeightConfigs.js | ⚠️ UNSURE | Not found in import search. Check before removal. |
| src/utils/LotteryTypes.js.backup | ❌ DEAD | Backup file |

### Config (1)
| File | Status | Notes |
|------|--------|-------|
| src/config/apiConfig.js | ✅ ACTIVE | API URL configuration |

### CSS (3)
| File | Status | Notes |
|------|--------|-------|
| styles.css | ✅ ACTIVE | Main stylesheet |
| professional-design.css | ✅ ACTIVE | Professional theme |
| src/ui/progress.css | ✅ ACTIVE | Progress bar styles |

---

## 3. Dead/Backup Frontend Files

| File | Classification | Reason |
|------|---------------|--------|
| src/core/App.js.backup | ❌ DEAD | Backup copy, not imported |
| src/core/App.js.bak | ❌ DEAD | Backup copy, not imported |
| src/utils/LotteryTypes.js.backup | ❌ DEAD | Backup copy, not imported |

---

## 4. Frontend Routes

This is a Single-Page Application (SPA) with NO client-side routing:
- All navigation is section-based CSS visibility toggling
- No URL changes on page navigation
- State managed entirely in JavaScript objects

---

## 5. CDN Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| lucide | latest | Icon library |
| chart.js | 4.4.0 | Chart rendering |
| @tensorflow/tfjs | 4.9.0 | Client-side ML |

---

## 6. Summary

| Category | Count | Active | Dead/Backup |
|----------|-------|--------|-------------|
| Core JS | 3 | 3 | 0 |
| Handlers | 5 | 5 | 0 |
| Strategies | 21 | 21 | 0 |
| UI | 7 | 6 | 0 (1 uncertain) |
| Services/Data/Config | 3 | 3 | 0 |
| Utils | 4 | 2 | 1 backup, 1 uncertain |
| CSS | 3 | 3 | 0 |
| **Backup/Dead** | **3** | **0** | **3** |
| **TOTAL** | **49** | **43** | **3 dead** |

**Result**: Frontend is largely clean. Only 3 backup files confirmed dead.
