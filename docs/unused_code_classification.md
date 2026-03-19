# Unused Code Classification
**Date**: 2026-03-19
**Auditor**: Claude Code

---

## Classification Legend
- **A: SAFE_TO_DELETE** - Confirmed dead, no risk
- **B: MOVE_TO_TMP** - Unused but uncertain; move to tmp/backend_archive/
- **C: KEEP** - Active or required
- **D: UNSURE** - Needs further investigation before action

---

## 1. FRONTEND FILES

### A. SAFE_TO_DELETE (Frontend)

| File | Reason | Risk |
|------|--------|------|
| src/core/App.js.backup | Backup copy, not imported, not in HTML | NONE |
| src/core/App.js.bak | Backup copy, not imported, not in HTML | NONE |
| src/utils/LotteryTypes.js.backup | Backup copy, not imported | NONE |

### C. KEEP (Frontend)

All 35+ active JS files in `src/` are KEEP. See `release_audit_frontend.md`.

### D. UNSURE (Frontend)

| File | Reason | Action |
|------|--------|--------|
| src/ui/components/AssetDoublingPlanComponent.js | Uses `window.AssetDoublingPlanComponent` global registration. Not in App.js import chain or HTML script tags. May be dead OR may be used by inline script in HTML body. | KEEP - do not delete until confirmed unused by full HTML audit |
| src/utils/WeightConfigs.js | Not found in import search. May be used dynamically or be dead code. | KEEP - do not delete until confirmed unused |

---

## 2. BACKEND ROUTE FILES

### B. MOVE_TO_TMP (Unregistered Routes)

| File | Reason | Risk |
|------|--------|------|
| lottery_api/routes/advanced_learning.py | NOT registered in app.py's `from routes import ...`. Not reachable via HTTP. | LOW - API unreachable |
| lottery_api/routes/optimized_predict.py | NOT registered in app.py. Not reachable via HTTP. | LOW - API unreachable |

---

## 3. BACKEND MODEL FILES

### C. KEEP (Active Models - Imported by Routes)

| Model | Imported By |
|-------|------------|
| models/optimized_ensemble.py | prediction.py |
| models/unified_predictor.py | prediction.py, backtest.py |
| models/enhanced_predictor.py | prediction.py |
| models/smart_multi_bet.py | prediction.py |
| models/daily539_predictor.py | prediction.py |
| models/multi_bet_optimizer.py | prediction.py, backtest.py |
| models/special_predictor.py | prediction.py |
| models/strategy_adapter.py | prediction.py |
| models/regime_monitor.py | prediction.py |
| models/strategy_evaluator.py | optimization.py |
| models/backtest_framework.py | backtest.py |
| models/auto_optimizer.py | backtest.py |
| models/optimized_predictor.py | backtest.py |
| models/wheel_tables.py | prediction.py |
| models/zone_split.py | prediction.py |
| models/anti_consensus_sampler.py | prediction.py |
| models/entropy_transformer.py | prediction.py |
| models/core_satellite.py | prediction.py |
| models/prophet_model.py | predictors.py |
| models/xgboost_model.py | predictors.py |
| models/autogluon_model.py | predictors.py |
| models/lstm_model.py | predictors.py |
| models/transformer_model.py | predictors.py |
| models/bayesian_ensemble.py | predictors.py |
| models/mab_ensemble.py | predictors.py |

### A. SAFE_TO_DELETE (Documented Deprecated in CLAUDE.md - Not Imported)

Per CLAUDE.md explicit deprecation notices:

| Model | Deprecation Reason | Risk |
|-------|-------------------|------|
| models/arima_predictor.py | Position-ordering flaw, Edge -3.46%/-3.86% | NONE |
| models/attention_lstm.py | Baseline error caused false positive, Edge -0.19% | NONE |
| models/negative_selection_biglotto.py | Edge -0.87%, documented invalid | NONE |
| models/cooccurrence_graph.py | Edge -3.87%, documented invalid | NONE |
| models/perball_lstm.py | Edge +0.11% only, Gemini, confirmed weak | NONE |
| models/transformer_model.py.backup | Backup file | NONE |

**Note**: Even though these are SAFE_TO_DELETE, per conservative policy we will MOVE_TO_TMP.

### B. MOVE_TO_TMP (Unused Models - Research/Experimental)

Models not imported by any active route file (research artifacts):

| Model | Category |
|-------|----------|
| models/adaptive_window.py | Experimental |
| models/advanced_auto_learning.py | Research |
| models/advanced_bayesian_analyzer.py | Research |
| models/advanced_strategies.py | Research |
| models/anomaly_predictor.py | Research |
| models/anomaly_regression.py | Research |
| models/anti_consensus_predictor.py | Research |
| models/anti_consensus_strategy.py | Research |
| models/attention_lstm_torch.py | Research |
| models/auto_learning.py | Research |
| models/autogluon_model_extensions.py | Research |
| models/best_practice_predictor.py | Research |
| models/big_lotto_dual_bet_optimizer.py | Research |
| models/big_lotto_optimizer.py | Research |
| models/biglotto_2bet_final.py | Research |
| models/biglotto_2bet_optimizer_v2.py | Research |
| models/biglotto_2bet_optimizer.py | Research |
| models/biglotto_3bet_optimizer.py | Research |
| models/biglotto_graph.py | Research |
| models/biglotto_tme_optimizer.py | Research |
| models/cold_hunter_predictor.py | Research |
| models/concentrated_pool_predictor.py | Research |
| models/constraint_filter_predictor.py | Research |
| models/deep_feature_extractor.py | Research |
| models/diffusion_predictor.py | Research |
| models/dual_bet_strategy.py | Research |
| models/dynamic_ensemble_predictor.py | Research |
| models/dynamic_weight_adjuster.py | Research |
| models/enhanced_dual_bet_predictor.py | Research |
| models/ensemble_predictor.py | Research |
| models/ensemble_stacking.py | Research |
| models/feature_analyzer.py | Research |
| models/feature_importance.py | Research |
| models/fourier_rhythm.py | Research |
| models/gap_manager.py | Research |
| models/gap_predictor.py | Research |
| models/gap_pressure.py | Research |
| models/genetic_optimizer.py | Research |
| models/gnn_predictor.py | Research |
| models/hpsb_optimizer.py | Research |
| models/hyperparameter_optimizer.py | Research |
| models/improved_special_predictor.py | Research |
| models/individual_rhythm_predictor.py | Research |
| models/lag_reversion.py | Research |
| models/lottery_graph.py | Research |
| models/lstm_attention_predictor.py | Research |
| models/lstm_predictor.py | Research |
| models/main_optimizer.py | Research |
| models/markov_2nd_special_predictor.py | Research |
| models/mcts_portfolio_optimizer.py | Research |
| models/meta_learning.py | Research |
| models/meta_predictor.py | Research |
| models/meta_stacking_2b.py | Research |
| models/meta_stacking_predictor.py | Research |
| models/negative_selector.py | Research |
| models/optimized_bayesian_predictor.py | Research |
| models/orthogonal_2bet.py | Research |
| models/power_lotto_predictor.py | Research |
| models/prediction_optimizer.py | Research |
| models/prize_optimizer.py | Research |
| models/quantum_random_predictor.py | Research |
| models/regime_detector.py | Research |
| models/selective_ensemble.py | Research |
| models/sgp_strategy.py | Research |
| models/simplified_bayesian_predictor.py | Research |
| models/smart_selector.py | Research |
| models/social_wisdom_predictor.py | Research |
| models/sota_predictor.py | Research |
| models/stability_profile.py | Research |
| models/transformer_predictor.py | Research |
| models/ultra_optimized_predictor.py | Research |
| models/unified_ml_predictor.py | Research |
| models/vae_predictor.py | Research |
| models/wobble_optimizer.py | Research |
| models/zone_cluster.py | Research |
| models/zone_shift_detector.py | Research |

**Total MOVE_TO_TMP models**: ~76 files

---

## 4. LOTTERY_API ROOT LEGACY SCRIPTS

### B. MOVE_TO_TMP (Legacy Research Scripts in lottery_api/)

These 122+ Python files exist in `lottery_api/` root (NOT in subdirectories) and are
NOT part of the active FastAPI application. They are legacy research scripts:

**Pattern: analyze_*.py** (~15 files)
- analyze_114000113.py, analyze_biglotto_115000011.py ... (draw analysis)

**Pattern: backtest_*.py** (~20 files)
- backtest_2025_double_bet.py, backtest_big_lotto_2025_ensemble.py ... (legacy backtests)

**Pattern: predict_*.py** (~15 files)
- predict_114000114_upgraded.py, predict_biglotto_117.py ... (old prediction scripts)

**Pattern: benchmark_*.py** (~5 files)
- benchmark_all_lotteries.py, benchmark_sota.py ... (benchmarks)

**Pattern: compare_*.py** (~6 files)
- compare_data_windows.py, compare_v10_v11.py ... (comparisons)

**Pattern: verify_*.py** (~8 files)
- verify_4bet_strategy_2025.py, verify_539_prediction.py ... (old verifications)

**Pattern: test_*.py** (~10 files)
- test_backtest.py, test_daily539_match.py ... (old tests)

**Pattern: other research** (~20 files)
- advanced_data_analysis.py, calculate_win_probability.py,
  comprehensive_rolling_backtest.py, rolling_backtest_2025.py, etc.

**Active: Keep in lottery_api/ root**:
- app.py, common.py, database.py, config.py, config_loader.py
- schemas.py, predictors.py, requirements.txt, install.sh, CLAUDE.md

---

## 5. ROOT-LEVEL LEGACY FILES

### A. SAFE_TO_DELETE (Root-level audit/result text files)

| File Pattern | Count | Reason |
|-------------|-------|--------|
| audit_p*.txt | ~30 files | Old strategy audit text files |
| audit_results*.txt | ~10 files | Old audit results |
| audit_report*.txt | ~5 files | Old audit reports |
| audit_stabilized*.txt | ~3 files | Old audit artifacts |
| backtest_2025_detail.log | 1 | Old log |

### B. MOVE_TO_TMP (Root-level backtest/analysis JSON result files)

| File Pattern | Count | Reason |
|-------------|-------|--------|
| backtest_*.json | ~60 files | Research result files |
| backtest_39lotto_comprehensive.json | 1 | Research |
| backtest_ortho_5bet_result.json | 1 | Research |
| 4bet_validation_results_2025.json | 1 | Research |

### C. KEEP (Root-level - Active or Required)

| File/Dir | Reason |
|---------|--------|
| index.html | Frontend entry point |
| styles.css | Active stylesheet |
| professional-design.css | Active stylesheet |
| start_all.sh | Service startup |
| stop_all.sh | Service shutdown |
| src/ | Frontend source |
| lottery_api/ | Backend source |
| tools/ | Tools directory (some active) |
| data/ | RSM state data |
| docs/ | Documentation |
| rejected/ | MUST KEEP (CLAUDE.md: rejected strategies archive) |
| research/ | Research scripts (CLAUDE.md: research never stops) |
| CLAUDE.md | Project instructions |
| MEMORY.md | Auto-memory |
| memory/ | Memory directory |
| tests/ | Test files |

### D. UNSURE (Root-level)

| File/Dir | Reason |
|---------|--------|
| analysis/ | Contains analysis scripts. Keep if research artifacts |
| ai_lab/ | Unknown purpose |
| archive/ | Archive directory - keep |
| design-system/ | May be needed for frontend development |
| rl_logs/ | RL experiment logs |
| claude-code-showcase/ | Unknown - check before deletion |

---

## 6. SUMMARY TABLE

| Category | Frontend | Backend Models | Backend Routes | Root Files | Total |
|----------|----------|----------------|----------------|------------|-------|
| A: SAFE_TO_DELETE | 3 | 6 | 0 | ~48 | ~57 |
| B: MOVE_TO_TMP | 0 | ~76 | 2 | ~60 | ~138 |
| C: KEEP | 35 | 25 | 5 | ~15 dirs | ~80 |
| D: UNSURE | 2 | 0 | 0 | ~5 | ~7 |

**Conservative Policy Applied**:
- SAFE_TO_DELETE items will be moved to tmp/ rather than deleted immediately
- KEEP items are untouched
- UNSURE items are retained with documentation

---

**Note**: The `rejected/` directory at root level and all validated strategy state files
MUST be preserved per CLAUDE.md: "舊策略不得刪除，只能歸檔".
