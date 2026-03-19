# Release Dependency Map
**Date**: 2026-03-19
**Auditor**: Claude Code

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  Browser (http://localhost:8081)                    │
│                                                     │
│  index.html                                         │
│  ├─ styles.css + professional-design.css            │
│  └─ <script type="module"> src/main.js              │
│       └─ App.js (orchestrator)                      │
│            ├─ PredictionEngine (21 strategies)      │
│            ├─ UIManager + ChartManager              │
│            ├─ AutoLearningManager                   │
│            ├─ SmartBettingComponent                 │
│            ├─ RecordManager + ProgressManager       │
│            └─ ApiClient ──────────────────────────┐ │
└───────────────────────────────────────────────────┼─┘
                                                    │ HTTP (port 8002)
┌───────────────────────────────────────────────────┼─┐
│  FastAPI Backend (http://localhost:8002)           │ │
│                                                   ▼ │
│  lottery_api/app.py                                  │
│  ├─ admin.py    → /, /health, /api/ping, /api/cache  │
│  ├─ data.py     → /api/data/*, /api/history          │
│  ├─ prediction.py → /api/predict*, /api/wheel/*      │
│  ├─ optimization.py → /api/auto-learning/*           │
│  └─ backtest.py → /api/backtest/*                    │
│                                                      │
│  Engine Layer:                                       │
│  ├─ strategy_coordinator.py (RSM primary)            │
│  ├─ rolling_strategy_monitor.py                      │
│  ├─ perm_test.py                                     │
│  ├─ drift_detector.py                                │
│  ├─ hypothesis_registry.py                           │
│  └─ prediction_logger.py                             │
│                                                      │
│  Model Layer (~20 active):                           │
│  ├─ daily539_predictor.py                            │
│  ├─ unified_predictor.py                             │
│  ├─ special_predictor.py                             │
│  ├─ regime_monitor.py                                │
│  └─ ...17 more                                       │
│                                                      │
│  Database:                                           │
│  └─ data/lottery_v2.db (SQLite)                      │
└──────────────────────────────────────────────────────┘
```

---

## 2. Frontend Module Dependency Graph

```
src/main.js
└── src/core/App.js
    ├── src/core/DataProcessor.js
    │   └── src/utils/LotteryTypes.js
    ├── src/data/StatisticsService.js
    │   └── src/utils/LotteryTypes.js
    ├── src/engine/PredictionEngine.js
    │   ├── src/utils/Constants.js
    │   │   └── src/utils/LotteryTypes.js (re-exports)
    │   └── src/engine/strategies/ [21 strategy files]
    │       ├── FrequencyStrategy.js
    │       ├── TrendStrategy.js
    │       ├── MarkovStrategy.js
    │       ├── MonteCarloStrategy.js
    │       ├── BayesianStrategy.js
    │       ├── DeviationStrategy.js
    │       ├── UnifiedEnsembleStrategy.js
    │       ├── MLStrategy.js
    │       ├── CollaborativeStrategy.js
    │       ├── AutoOptimizeStrategy.js
    │       ├── APIStrategy.js
    │       ├── BackendOptimizedStrategy.js
    │       ├── ZoneSplitStrategy.js
    │       ├── CoreSatelliteStrategy.js
    │       ├── OddEvenBalanceStrategy.js
    │       ├── ZoneBalanceStrategy.js
    │       ├── HotColdMixStrategy.js
    │       ├── SumRangeStrategy.js
    │       ├── WheelingStrategy.js
    │       ├── NumberPairsStrategy.js
    │       └── StatisticalAnalysisStrategy.js
    ├── src/ui/UIManager.js
    │   └── src/utils/LotteryTypes.js (dynamic import)
    ├── src/ui/ChartManager.js
    ├── src/ui/components/SmartBettingComponent.js
    ├── src/engine/QuickPredictionService.js
    │   └── src/utils/LotteryTypes.js
    ├── src/utils/Constants.js
    ├── src/ui/AutoLearningManager.js
    │   └── src/utils/LotteryTypes.js
    ├── src/services/ApiClient.js
    ├── src/ui/ProgressManager.js
    ├── src/ui/RecordManager.js
    ├── src/core/handlers/FileUploadHandler.js
    ├── src/core/handlers/DataHandler.js
    ├── src/core/handlers/UIDisplayHandler.js
    ├── src/core/handlers/SimulationHandler.js
    ├── src/core/handlers/PredictionHandler.js
    └── src/config/apiConfig.js
```

---

## 3. Backend Module Dependency Graph

```
lottery_api/app.py
├── routes/admin.py
│   ├── utils/scheduler.py
│   └── utils/model_cache.py
│
├── routes/data.py
│   ├── database.py
│   ├── utils/scheduler.py
│   ├── utils/model_cache.py
│   ├── utils/csv_validator.py
│   ├── common.py
│   └── schemas.py
│
├── routes/prediction.py
│   ├── predictors.py          ← predictor factory
│   │   ├── models/prophet_model.py
│   │   ├── models/xgboost_model.py
│   │   ├── models/autogluon_model.py
│   │   ├── models/lstm_model.py
│   │   ├── models/transformer_model.py
│   │   ├── models/bayesian_ensemble.py
│   │   └── models/mab_ensemble.py
│   ├── utils/model_cache.py
│   ├── utils/scheduler.py
│   ├── models/optimized_ensemble.py
│   ├── models/unified_predictor.py
│   ├── models/enhanced_predictor.py
│   ├── models/smart_multi_bet.py
│   ├── models/daily539_predictor.py
│   ├── models/multi_bet_optimizer.py
│   ├── models/special_predictor.py
│   ├── models/strategy_adapter.py
│   ├── models/regime_monitor.py
│   ├── models/wheel_tables.py
│   ├── models/zone_split.py
│   ├── models/anti_consensus_sampler.py
│   ├── models/entropy_transformer.py
│   ├── models/core_satellite.py
│   ├── database.py
│   ├── common.py
│   ├── config.py
│   ├── schemas.py
│   └── engine/strategy_coordinator.py
│       ├── engine/rolling_strategy_monitor.py
│       ├── engine/perm_test.py
│       ├── engine/prediction_logger.py
│       ├── engine/drift_detector.py
│       ├── engine/hypothesis_registry.py
│       └── engine/s2_markov_weibull.py
│
├── routes/optimization.py
│   ├── utils/scheduler.py
│   ├── utils/smart_scheduler.py
│   ├── predictors.py
│   ├── database.py
│   ├── common.py
│   └── models/strategy_evaluator.py
│
└── routes/backtest.py
    ├── database.py
    ├── common.py
    ├── models/backtest_framework.py
    ├── models/auto_optimizer.py
    ├── models/multi_bet_optimizer.py
    └── models/optimized_predictor.py
```

---

## 4. Frontend → Backend API Call Map

| Frontend Action | API Called | Route Handler |
|----------------|-----------|---------------|
| Load history | GET /api/history | data.py |
| Upload CSV | POST /api/data/upload | data.py |
| Predict (frontend) | POST /api/predict | prediction.py |
| Predict (backend model) | POST /api/predict-from-backend | prediction.py |
| Optimize | POST /api/auto-learning/optimize | optimization.py |
| Schedule status | GET /api/auto-learning/schedule/status | optimization.py |
| Best config | GET /api/auto-learning/best-config | optimization.py |
| Evaluate strategies | POST /api/auto-learning/evaluate-strategies | optimization.py |
| Health check | GET /health | admin.py |
| Record hit | POST /api/performance/record-hit | prediction.py |
| Get data stats | GET /api/data/stats | data.py |
| Clear data | POST /api/data/clear | data.py |

---

## 5. Data Flow

```
External Data Sources
    │
    ▼ (upload CSV or load DB)
lottery_api/data/lottery_v2.db     ← SQLite (primary store)
lottery_api/data/lottery_history.json  ← JSON snapshot
    │
    ▼ (scheduler loads on startup)
utils/scheduler.py → in-memory history
    │
    ▼ (route handlers pull from scheduler)
routes/prediction.py → strategy_coordinator.py
    │                    → rolling_strategy_monitor.py
    ▼                    → individual model predictors
API response (JSON)
    │
    ▼
Frontend: ApiClient.js → App.js → UIManager.js
```

---

## 6. State Files (Persistent JSON)

| File | Updated By | Read By |
|------|-----------|---------|
| data/lottery_v2.db | database.py | All routes |
| data/lottery_history.json | data sync | scheduler.py |
| data/predictions_*.jsonl | prediction_logger.py | llm_analyzer.py |
| data/strategy_states_*.json | strategy_coordinator.py | RSM |
| data/agent_tracking_*.json | agent_tracking.py | RSM |
| ../data/rolling_monitor_*.json | rolling_strategy_monitor.py | tools/rsm_bootstrap.py |
| data/current_jackpots.json | update_current_jackpots.py | prediction.py |

---

## 7. Tools Referenced by Active System

| Tool | Used By | Status |
|------|---------|--------|
| tools/verify_prediction_api.py | start_all.sh | ✅ CRITICAL |
| tools/contract_test_prediction_api.py | verify_prediction_api.py | ✅ CRITICAL |
| tools/smoke_test_coordinator_api.py | verify_prediction_api.py | ✅ CRITICAL |
| tools/quick_predict.py | CLI / CLAUDE.md | ✅ PRODUCTION |
| tools/rsm_bootstrap.py | RSM init | ✅ PRODUCTION |
| tools/strategy_leaderboard.py | RSM monitoring | ✅ PRODUCTION |
| tools/update_db_latest.py | Data sync | ✅ PRODUCTION |
| tools/power_fourier_rhythm.py | CLAUDE.md | ✅ VALIDATED |

---

## 8. Key Dependencies Summary

### Python Backend
- fastapi, uvicorn - Web framework
- pydantic - Schema validation
- SQLite (built-in) - Database
- numpy, pandas - Data processing
- scikit-learn - ML utilities

### JavaScript Frontend
- Vanilla JS (ES6 modules) - No bundler
- Chart.js 4.4.0 - Charts
- TensorFlow.js 4.9.0 - Client-side ML
- Lucide - Icons

---

**Conclusion**: The dependency graph is well-structured. Frontend imports are clean.
Backend has 5 active routes with clear engine/model layering. The RSM coordinator
is the primary production prediction path.
