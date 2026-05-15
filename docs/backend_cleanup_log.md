# Backend Cleanup Log
**Date**: 2026-03-19
**Phase**: 4 - Backend Cleanup / Tmp Relocation

---

## Archive Structure Created

```
tmp/
├── frontend_archive/          ← Frontend backup files
│   ├── App.js.backup
│   ├── App.js.bak
│   └── LotteryTypes.js.backup
└── backend_archive/
    ├── routes/                ← Unregistered route files
    ├── models_deprecated/     ← CLAUDE.md-documented deprecated models
    ├── models_research/       ← Unused research/experimental models
    └── lottery_api_legacy/    ← Legacy scripts from lottery_api/ root
```

---

## 1. Unregistered Routes Moved

| File | Destination | Reason |
|------|-------------|--------|
| lottery_api/routes/advanced_learning.py | tmp/backend_archive/routes/ | NOT registered in app.py; unreachable API |
| lottery_api/routes/optimized_predict.py | tmp/backend_archive/routes/ | NOT registered in app.py; unreachable API |

**Total**: 2 files moved

---

## 2. Deprecated Models Moved (per CLAUDE.md)

| File | Destination | CLAUDE.md Reason |
|------|-------------|-----------------|
| models/arima_predictor.py | models_deprecated/ | Position-ordering flaw, Edge -3.46% |
| models/attention_lstm.py | models_deprecated/ | Baseline error, Edge -0.19% |
| models/negative_selection_biglotto.py | models_deprecated/ | Edge -0.87% |
| models/cooccurrence_graph.py | models_deprecated/ | Edge -3.87% |
| models/perball_lstm.py | models_deprecated/ | Weak Edge +0.11% |
| models/transformer_model.py.backup | models_deprecated/ | Backup file |

**Total**: 6 files moved

---

## 3. Research/Experimental Models Moved

76 model files moved to `tmp/backend_archive/models_research/`.
These files are not imported by any active route file.

Notable moves:
- adaptive_window.py, advanced_auto_learning.py, advanced_bayesian_analyzer.py
- anomaly_predictor.py, anomaly_regression.py, anti_consensus_predictor.py
- attention_lstm_torch.py, auto_learning.py, autogluon_model_extensions.py
- best_practice_predictor.py, big_lotto_dual_bet_optimizer.py, big_lotto_optimizer.py
- biglotto_2bet_final.py, biglotto_2bet_optimizer.py, biglotto_2bet_optimizer_v2.py
- biglotto_3bet_optimizer.py, biglotto_graph.py, biglotto_tme_optimizer.py
- cold_hunter_predictor.py, concentrated_pool_predictor.py, constraint_filter_predictor.py
- deep_feature_extractor.py, diffusion_predictor.py, dual_bet_strategy.py
- dynamic_ensemble_predictor.py, dynamic_weight_adjuster.py
- enhanced_dual_bet_predictor.py, ensemble_predictor.py, ensemble_stacking.py
- feature_analyzer.py, feature_importance.py, fourier_rhythm.py
- gap_manager.py, gap_predictor.py, gap_pressure.py, genetic_optimizer.py
- gnn_predictor.py, hpsb_optimizer.py, hyperparameter_optimizer.py
- improved_special_predictor.py, individual_rhythm_predictor.py
- lag_reversion.py, lottery_graph.py, lstm_attention_predictor.py, lstm_predictor.py
- main_optimizer.py, markov_2nd_special_predictor.py
- mcts_portfolio_optimizer.py, meta_learning.py, meta_predictor.py
- meta_stacking_2b.py, meta_stacking_predictor.py, negative_selector.py
- optimized_bayesian_predictor.py, orthogonal_2bet.py
- power_lotto_predictor.py, prediction_optimizer.py, prize_optimizer.py
- quantum_random_predictor.py, regime_detector.py, selective_ensemble.py
- sgp_strategy.py, simplified_bayesian_predictor.py, smart_selector.py
- social_wisdom_predictor.py, sota_predictor.py, stability_profile.py
- transformer_predictor.py, ultra_optimized_predictor.py, unified_ml_predictor.py
- vae_predictor.py, wobble_optimizer.py
- zone_cluster.py, zone_shift_detector.py
- advanced_strategies.py, anti_consensus_strategy.py

**Total**: 76 files moved

---

## 4. Legacy Scripts Moved from lottery_api/ Root

115 Python scripts moved from `lottery_api/` root to `tmp/backend_archive/lottery_api_legacy/`.

These are legacy research and analysis scripts that were never part of the active FastAPI application.

Categories:
- analyze_*.py (draw analysis scripts, ~15 files)
- backtest_*.py (legacy backtest scripts, ~20 files)
- predict_*.py (old prediction scripts, ~15 files)
- benchmark_*.py (benchmark scripts, ~5 files)
- compare_*.py (comparison scripts, ~6 files)
- verify_*.py (old verification scripts, ~8 files)
- test_*.py (old test scripts, ~10 files)
- Other research scripts (~36 files)

Also moved research JSON result files:
- backtest_ortho_5bet_result.json
- backtest_report_2025.json
- backtest_report_phase1_20251215_231909.json
- backtest_report_quick_20251215_231154.json
- strategy_evaluation_20251216_150817.json
- quick_evaluation_20251216_151922.json

**Total**: 121 files moved (115 Python + 6 JSON)

---

## 5. Active Backend Files Verified Intact

### Routes (5 active)
```
lottery_api/routes/
├── __init__.py
├── admin.py         ✅
├── prediction.py    ✅
├── data.py          ✅
├── optimization.py  ✅
└── backtest.py      ✅
```

### Models (26 active)
```
lottery_api/models/
├── __init__.py
├── anti_consensus_sampler.py  ✅
├── auto_optimizer.py          ✅
├── autogluon_model.py         ✅
├── backtest_framework.py      ✅
├── bayesian_ensemble.py       ✅
├── core_satellite.py          ✅
├── daily539_predictor.py      ✅
├── enhanced_predictor.py      ✅
├── entropy_transformer.py     ✅
├── lstm_model.py              ✅
├── mab_ensemble.py            ✅
├── multi_bet_optimizer.py     ✅
├── optimized_ensemble.py      ✅
├── optimized_predictor.py     ✅
├── prophet_model.py           ✅
├── regime_monitor.py          ✅
├── smart_multi_bet.py         ✅
├── special_predictor.py       ✅
├── strategy_adapter.py        ✅
├── strategy_evaluator.py      ✅
├── transformer_model.py       ✅
├── unified_predictor.py       ✅
├── wheel_tables.py            ✅
├── xgboost_model.py           ✅
└── zone_split.py              ✅
```

### Core Files (7 active)
```
lottery_api/
├── app.py            ✅ (FastAPI application)
├── common.py         ✅
├── config.py         ✅
├── config_loader.py  ✅
├── database.py       ✅
├── predictors.py     ✅
└── schemas.py        ✅
```

### Engine (10 active)
```
lottery_api/engine/
├── core_satellite.py         ✅
├── drift_detector.py         ✅
├── hypothesis_registry.py    ✅
├── llm_analyzer.py           ✅
├── multi_bet_optimizer.py    ✅
├── perm_test.py              ✅
├── prediction_logger.py      ✅
├── rolling_strategy_monitor.py ✅
├── s2_markov_weibull.py      ✅
└── strategy_coordinator.py   ✅
```

---

## Summary

| Category | Files Moved | Files Kept |
|----------|------------|------------|
| Unregistered routes | 2 | 0 |
| Deprecated models | 6 | 0 |
| Research models | 76 | 26 |
| Legacy lottery_api scripts | 121 | 7 |
| **TOTAL** | **205** | **33** |

**Impact on Active System**: NONE - all active route, model, and engine files intact.
