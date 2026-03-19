# Backend Release Audit
**Date**: 2026-03-19
**Auditor**: Claude Code

---

## 1. Entry Point

```
lottery_api/app.py
  └─ Registers 5 Route Modules:
       ├─ admin.py       → GET /, /health, /api/ping, /api/cache/*
       ├─ prediction.py  → POST /api/predict*, /api/wheel/*, /api/performance/*
       ├─ data.py        → GET/POST/DELETE /api/data/*, /api/history, /api/draws/*
       ├─ optimization.py → POST /api/auto-learning/*
       └─ backtest.py    → POST /api/backtest/*
```

---

## 2. Active Route Files

| Route File | Status | Endpoints |
|-----------|--------|-----------|
| lottery_api/routes/admin.py | ✅ REGISTERED | /, /health, /api/ping, /api/cache/* |
| lottery_api/routes/prediction.py | ✅ REGISTERED | 30+ prediction endpoints |
| lottery_api/routes/data.py | ✅ REGISTERED | CRUD for draws and data management |
| lottery_api/routes/optimization.py | ✅ REGISTERED | Auto-learning pipeline |
| lottery_api/routes/backtest.py | ✅ REGISTERED | Rolling backtest endpoints |

## 3. Unregistered Route Files (NOT in app.py)

| Route File | Status | Notes |
|-----------|--------|-------|
| lottery_api/routes/advanced_learning.py | ⚠️ UNREGISTERED | Not in `from routes import ...` in app.py. May be dead. |
| lottery_api/routes/optimized_predict.py | ⚠️ UNREGISTERED | Not in `from routes import ...` in app.py. May be dead. |

---

## 4. Backend API Endpoints (Active)

### admin.py
```
GET  /                          Root info
GET  /health                    Health check
GET  /api/ping                  Alive check
GET  /api/cache/stats           Cache statistics
POST /api/cache/clear           Clear cache
```

### prediction.py (30+ endpoints)
```
POST /api/predict               Universal predict endpoint
POST /api/predict-from-backend  Select backend model
POST /api/predict-from-backend-eval  Evaluation mode
POST /api/predict-with-range    Range-based prediction
POST /api/predict-optimized     Optimized prediction
POST /api/predict/zone-split    Zone split strategy
POST /api/predict/expert-certified  Expert mode
POST /api/predict/core-satellite    Core-satellite
POST /api/predict-entropy-8-bets    Entropy 8-bet
POST /api/predict-enhanced      Enhanced mode
POST /api/predict-enhanced-all  Enhanced all modes
POST /api/predict-smart-multi-bet  Smart multi-bet
POST /api/predict-optimal       Optimal strategy
POST /api/predict-coordinator   RSM coordinator (⭐ Primary)
POST /api/predict-double-bet    2-bet strategy
POST /api/predict-hyper-precision-2bet  2-bet precision
POST /api/predict-dual-bet-539  539 2-bet
POST /api/predict-triple-bet-539  539 3-bet
POST /api/predict-consecutive-539  539 consecutive
POST /api/wheel/generate        Wheel coverage generation
GET  /api/wheel/available-guarantees  Wheel options
GET  /api/performance/regime    Regime performance
POST /api/performance/record-hit  Record hit
GET  /api/models                List available models
GET  /api/enhanced-methods      List enhanced methods
GET  /api/optimal-configs       Optimal configs
```

### data.py
```
GET    /api/history              Full draw history
POST   /api/data/upload          Upload data file
POST   /api/data/validate-csv    Validate CSV format
GET    /api/data/draws           Paginated draws
GET    /api/data/stats           Data statistics
POST   /api/data/clear           Clear data
POST   /api/draws                Create draw record
PUT    /api/draws/{draw_id}      Update draw record
DELETE /api/draws/{draw_id}      Delete draw record
```

### optimization.py
```
POST /api/auto-learning/optimize                  Run optimization
POST /api/auto-learning/schedule/start            Start schedule
POST /api/auto-learning/schedule/stop             Stop schedule
POST /api/auto-learning/schedule/run-now          Run immediately
GET  /api/auto-learning/schedule/status           Get status
GET  /api/auto-learning/best-config               Best config
POST /api/auto-learning/set-target-fitness        Set target
GET  /api/auto-learning/optimization-history      History
POST /api/auto-learning/sync-data                 Sync data
POST /api/auto-learning/evaluate-strategies       Evaluate
GET  /api/auto-learning/best-strategy             Best strategy
POST /api/auto-learning/advanced/multi-stage      Advanced
POST /api/auto-learning/advanced/adaptive-window  Advanced
GET  /api/auto-learning/advanced/status           Advanced status
POST /api/auto-learning/predict-with-best         Predict
```

### backtest.py
```
POST /api/backtest/rolling       Rolling backtest
POST /api/backtest/multi-bet     Multi-bet backtest
GET  /api/backtest/results       Get results
POST /api/backtest/evaluate-config  Evaluate config
```

---

## 5. Active Backend Models (Imported by Routes)

| Model | Imported By | Purpose |
|-------|------------|---------|
| models/optimized_ensemble.py | prediction.py | Ensemble predictor |
| models/unified_predictor.py | prediction.py, backtest.py | Core prediction engine |
| models/enhanced_predictor.py | prediction.py | Enhanced predictions |
| models/smart_multi_bet.py | prediction.py | Smart multi-bet |
| models/daily539_predictor.py | prediction.py | 539-specific predictor |
| models/multi_bet_optimizer.py | prediction.py, backtest.py | Multi-bet optimization |
| models/special_predictor.py | prediction.py | Special number (POWER_LOTTO) |
| models/strategy_adapter.py | prediction.py | Strategy adaptation |
| models/regime_monitor.py | prediction.py | Regime detection |
| models/strategy_evaluator.py | optimization.py | Strategy evaluation |
| models/backtest_framework.py | backtest.py | Rolling backtest |
| models/auto_optimizer.py | backtest.py | Auto optimization |
| models/optimized_predictor.py | backtest.py | Optimized prediction |
| models/wheel_tables.py | prediction.py | Wheel coverage tables |
| models/zone_split.py | prediction.py | Zone split strategy |
| models/anti_consensus_sampler.py | prediction.py | Anti-consensus |
| models/entropy_transformer.py | prediction.py | Entropy calculation |
| models/core_satellite.py | prediction.py | Core-satellite structure |

---

## 6. Active Engine Modules

| Engine Module | Status | Purpose |
|--------------|--------|---------|
| engine/strategy_coordinator.py | ✅ ACTIVE | RSM coordinator (primary) |
| engine/rolling_strategy_monitor.py | ✅ ACTIVE | Rolling strategy monitor |
| engine/perm_test.py | ✅ ACTIVE | Permutation testing |
| engine/prediction_logger.py | ✅ ACTIVE | Prediction JSONL logging |
| engine/drift_detector.py | ✅ ACTIVE | Data drift detection |
| engine/hypothesis_registry.py | ✅ ACTIVE | Hypothesis tracking |
| engine/llm_analyzer.py | ✅ ACTIVE | LLM analysis (mocked/Groq) |
| engine/s2_markov_weibull.py | ✅ ACTIVE | Markov-Weibull gates |
| engine/core_satellite.py | ✅ ACTIVE | Core-satellite engine |
| engine/multi_bet_optimizer.py | ⚠️ DEPRECATED | Marked invalid in CLAUDE.md, but may still be imported |

---

## 7. Active Utility Modules

| Utility | Status | Purpose |
|---------|--------|---------|
| utils/scheduler.py | ✅ ACTIVE | Data scheduling |
| utils/model_cache.py | ✅ ACTIVE | Model caching |
| utils/smart_scheduler.py | ✅ ACTIVE | Smart scheduling |
| utils/benchmark_framework.py | ✅ ACTIVE | Backtest framework |
| utils/backtest_safety.py | ✅ ACTIVE | Safety checks |
| utils/csv_validator.py | ✅ ACTIVE | CSV validation |
| utils/game_dependency.py | ✅ ACTIVE | Game dependencies |

---

## 8. Core Backend Files

| File | Status | Purpose |
|------|--------|---------|
| app.py | ✅ ACTIVE | FastAPI application |
| common.py | ✅ ACTIVE | Shared utilities |
| database.py | ✅ ACTIVE | Database manager |
| config.py | ✅ ACTIVE | Configuration |
| schemas.py | ✅ ACTIVE | Pydantic schemas |
| predictors.py | ✅ ACTIVE | Predictor factory |
| requirements.txt | ✅ ACTIVE | Dependencies |
| CLAUDE.md | ✅ ACTIVE | Strategy documentation |

---

## 9. Unused/Legacy Model Files (Confirmed by CLAUDE.md + import analysis)

### Documented as Deprecated in CLAUDE.md
| Model | Reason | Safe Action |
|-------|--------|------------|
| models/arima_predictor.py | Edge -3.46%/-3.86%, position-ordering flaw | MOVE_TO_TMP |
| models/attention_lstm.py | Baseline error, Edge -0.19% | MOVE_TO_TMP |
| models/negative_selection_biglotto.py | Edge -0.87% | MOVE_TO_TMP |
| models/cooccurrence_graph.py | Edge -3.87% | MOVE_TO_TMP |
| models/perball_lstm.py | Edge +0.11%, weak | MOVE_TO_TMP |
| engine/multi_bet_optimizer.py | Marked deprecated | MOVE_TO_TMP (if not imported) |

### Additional Legacy Models (Not imported by any route, research-only)
~80+ additional model files exist but are not imported by any active route.
See `unused_code_classification.md` for complete list.

---

## 10. Legacy Research Scripts in lottery_api/ Root

There are **122 Python scripts** in the `lottery_api/` root directory that are NOT
part of the active FastAPI application. These include:
- `analyze_*.py` - Analysis scripts
- `backtest_*.py` - Old backtest scripts
- `predict_*.py` - Old prediction scripts
- `benchmark_*.py` - Benchmark scripts
- `compare_*.py` - Comparison scripts
- etc.

These are research artifacts and should be **moved to tmp/backend_archive/**.

---

## 11. Infrastructure Files Referenced

| File | Referenced By | Status |
|------|--------------|--------|
| tools/verify_prediction_api.py | start_all.sh | ✅ ACTIVE |
| tools/contract_test_prediction_api.py | verify_prediction_api.py | ✅ ACTIVE |
| tools/smoke_test_coordinator_api.py | verify_prediction_api.py | ✅ ACTIVE |

---

## 12. Summary

| Category | Total | Active | Unregistered/Unused |
|----------|-------|--------|---------------------|
| Route Files | 7 | 5 | 2 unregistered |
| Engine Modules | 10 | 9 | 1 deprecated |
| Active Models | ~20 | ~20 | 0 |
| Unused Models | ~87 | 0 | 87 (research only) |
| Utility Modules | 7 | 7 | 0 |
| Legacy Root Scripts | 122 | 0 | 122 (research only) |

**Result**: The active system is well-defined with 5 registered routes and ~20 active models.
The 87+ unused models and 122 legacy root scripts are research artifacts to be archived.
