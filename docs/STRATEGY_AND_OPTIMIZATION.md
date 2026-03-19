# 🎯 Strategy Matrix + Optimization Plan (2025-11-30)

This consolidated document merges:
- LATEST_PREDICTION_METHODS_2025.md (strategy matrix, mappings, runtime rules)
- PREDICTION_OPTIMIZATION_ANALYSIS.md (confidence analysis, optimization proposals)

Use this as the single source of truth for strategies, backend integration, and ongoing optimization.

---

> Dev Ports Quick Note
- Backend runs on `http://localhost:5001` (`/health`, `/api/*`).
- Frontend static server runs on `http://localhost:8081` via `npm run dev`.
- `http://localhost:8000` is not used and won’t respond to backend health.

## ✅ Current Implementation Overview

- Frontend strategies mapped to backend models with fallbacks
- Backend endpoints: `/api/predict`, `/api/predict-from-backend`, auto-learning, cache, health
- Robustness: backend health backoff, disabled AI options on failure, LSTM → ensemble fallback
- Data caps: backend simulation and auto optimize capped to 500 records

### Strategy Matrix (condensed)
- Statistical: `frequency`, `trend`, `bayesian`, `markov`, `monte_carlo`, `deviation`, `statistical`
- Shape/Distribution: `odd_even`, `zone_balance`, `hot_cold`, `sum_range`, `number_pairs`
- Ensemble: `ensemble`, `ensemble_advanced`
- ML: `random_forest`
- Backend: `backend_optimized`, `auto_optimize`
- AI API: `prophet`, `xgboost`, `autogluon` (LSTM not implemented → fallback)

### Mapping & Fallbacks
- Deprecated → New: boosting/cooccurrence/features → `ensemble_advanced`; collaborative_* → `collaborative_hybrid` (internally uses ensemble); `wheeling` → `statistical`
- Backend down: disable `ai_*`, `auto_optimize`, `backend_optimized`
- `ai_lstm`: auto message + fallback `ensemble`
- Backend optimized requires data sync; otherwise returns error

### Health Backoff
- Exponential retry: 15s → 30s → 60s → 120s; reset on success

---

## 🔬 Confidence & Optimization Summary

- Ensemble variants perform best (0.75–0.95)
- Statistical stable (0.65–0.90)
- Shape strategies weaker (0.55–0.62)

### High-Impact Optimizations (Plan A)
- Bayesian dynamic weights: +6–10%
- Frequency adaptive decay: +5–8%
- Odd/Even position-aware: +8–12%
- Hot/Cold adaptive window: +6–10%

Expected overall uplift: +8–15%

### Advanced (Plan B)
- Markov multi-order transitions: +8–12%
- Zone balance dynamic boundaries (K-means): +10–15%
- New strategies: Pattern Recognition (0.80–0.85), Cycle Analysis (0.75–0.85)

---

## 🛠 Backend Cache Improvements (Implemented)
- Lightweight signature hash: count + last draw/date + rules + extra signature
- `extra_signature` used for `backend_optimized` bestConfig invalidation
- TTL: 24h (configurable)

---

## 🚀 Quick Usage
1. Load CSV to IndexedDB
2. Click Sync to backend
3. Use strategies; backend preferred when available
4. Simulations auto-truncate >500 records
5. Auto optimize with caps, then try `backend_optimized`

---

## 🔗 Related Files
- `lottery_api/app.py`: endpoints, dispatch map, backend_optimized unified
- `lottery_api/utils/model_cache.py`: enhanced caching
- `tools/sync_converted_2024.py`: CSV → backend sync + smoke predictions
- `styles.css`: disabled backend option styling

---

## 📈 Roadmap
- Add dynamic TTL per strategy
- Cache stats counters & diagnostics exposure
- Implement Plan A optimizations in `models/unified_predictor`
- Optional: Strategy evaluation automation pipeline

---

## 🧾 Changelog (2025-11-30)
- Unified `backend_optimized` branch in API and added `_load_backend_history` helper
- Introduced `MODEL_DISPATCH` map to reduce branching
- Health `/health` marks LSTM `not_implemented` for consistency
- Enhanced model cache with lightweight signature and `extra_signature` support
- Added `tools/sync_converted_2024.py` to sync CSV and smoke test predictions
- Consolidated docs to this file and linked from README
