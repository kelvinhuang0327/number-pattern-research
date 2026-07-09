# P541B — BIG_LOTTO Legacy / Folklore / Statistical Method Classification Audit

> generated_at: 2026-07-09T14:08:49.600925+00:00
> Historical legacy method classification audit only; not a prediction, betting edge, future-winning, or production-readiness claim.

## Recommended next task: P541B_BLOCKED_LEGACY_METHODS_TOO_AMBIGUOUS_NEED_CTO_REVIEW

Classified 580 BIG_LOTTO-referencing legacy scripts/methods across 8 discovery groups (P541A's original 451 tools/analysis scripts plus 5 newly-discovered groups: root-level scripts, `ai_lab/`, `recovered_strategies/biglotto/`, and `lottery_api/models|tools|engine/`). 221 show static signals of implementing their own numbers-selection logic; 142 are classified `include_in_replay_readiness` (clean enough for a small adapter); 167 are too ambiguous for static classification alone and need a human/CTO read; 9 contain a literal strategy_id string matching an already-registered strategy.

## Summary counts

| metric | value |
|---|---|
| total_methods_scripts_scanned | 580 |
| actual_candidate_prediction_methods | 221 |
| replay_covered_methods_via_duplicate_match | 8 |
| code_only_methods_needs_adapter_wrapper | 142 |
| non_strategy_utilities | 46 |
| duplicates | 9 |
| unsafe_or_not_runnable | 96 |
| candidate_methods_for_future_replay_readiness | 142 |
| methods_requiring_cto_review | 167 |
| obsolete_or_deprecated | 2 |

## Discovery groups scanned

| group | count | note |
|---|---|---|
| p541a_tools | 385 | from P541A artifact (tools/*.py, analysis/*.py) |
| p541a_analysis | 66 | from P541A artifact (tools/*.py, analysis/*.py) |
| root_level_scripts | 5 | new discovery, not in P541A's original scan |
| ai_lab | 23 | new discovery, not in P541A's original scan |
| recovered_strategies_biglotto | 28 | new discovery, not in P541A's original scan |
| lottery_api_models | 46 | new discovery, not in P541A's original scan |
| lottery_api_tools | 21 | new discovery, not in P541A's original scan |
| lottery_api_engine | 6 | new discovery, not in P541A's original scan |

## by_runnable_status

| runnable_status | count |
|---|---|
| ambiguous_needs_cto_review | 166 |
| needs_adapter_wrapper | 142 |
| hardcoded_paths_or_dates | 66 |
| needs_db_safety_refactor | 64 |
| needs_refactor_to_pure_function | 59 |
| not_a_strategy | 46 |
| unsafe_side_effects | 26 |
| runnable_with_existing_adapter | 5 |
| imports_db_or_runs_work_at_module_load | 3 |
| obsolete_or_deprecated | 2 |
| broken_or_import_error | 1 |

## by_method_family

| method_family | count |
|---|---|
| utility | 166 |
| report | 103 |
| ML_like | 85 |
| statistical | 46 |
| frequency | 43 |
| zone | 27 |
| data_prep | 24 |
| unknown | 23 |
| hot_cold | 16 |
| deviation | 16 |
| markov | 10 |
| regime | 7 |
| parity | 5 |
| sum_range | 3 |
| overdue | 2 |
| folklore | 2 |
| tail | 1 |
| neighbor | 1 |

## legacy_script_group_summary (item-8 taxonomy)

| category | count |
|---|---|
| unknown | 167 |
| candidate prediction method | 142 |
| strategy experiment | 123 |
| one-off notebook-like script | 95 |
| statistical report | 46 |
| duplicate / variant | 5 |
| obsolete / unsafe | 2 |

## Registered zero-replay strategy review

- **biglotto_ts3_acb_4bet** (REJECTED): Formally registered in lottery_api/models/replay_strategy_registry.py with status REJECTED; REJECTED strategies are excluded from replay-row generation eligibility (in_registry_generation_eligible=false per P541A inventory), so zero replay rows is expected, not a gap.
- **biglotto_ts3_markov_freq_5bet** (REJECTED): Formally registered in lottery_api/models/replay_strategy_registry.py with status REJECTED; REJECTED strategies are excluded from replay-row generation eligibility (in_registry_generation_eligible=false per P541A inventory), so zero replay rows is expected, not a gap.

## Phantom id review

- **p1_dev_sum5bet**: No registry entry and no replay rows; the registry file's own source comment documents this explicitly: it cites memory/lessons.md L90 naming this id among production strategies but states 'No exact callable found in codebase' and that related ids were handled via SAFE_RECONSTRUCTION thin wrappers rather than a real implementation being found.
  - Recommendation: Treat as a historical/naming-drift note only; do not delete from historical memory citations, but do not claim it as a buildable/missing implementation without further explicit code archaeology.
- **p1_deviation_4bet**: No registry entry and no replay rows; the registry file's own source comment documents this explicitly: it cites memory/lessons.md L90 naming this id among production strategies but states 'No exact callable found in codebase' and that related ids were handled via SAFE_RECONSTRUCTION thin wrappers rather than a real implementation being found.
  - Recommendation: Treat as a historical/naming-drift note only; do not delete from historical memory citations, but do not claim it as a buildable/missing implementation without further explicit code archaeology.
- **p1_neighbor_cold_2bet**: No registry entry and no replay rows; the registry file's own source comment documents this explicitly: it cites memory/lessons.md L90 naming this id among production strategies but states 'No exact callable found in codebase' and that related ids were handled via SAFE_RECONSTRUCTION thin wrappers rather than a real implementation being found.
  - Recommendation: Treat as a historical/naming-drift note only; do not delete from historical memory citations, but do not claim it as a buildable/missing implementation without further explicit code archaeology.
- **regime_2bet**: No registry entry and no replay rows; the registry file's own source comment documents this explicitly: it cites memory/lessons.md L90 naming this id among production strategies but states 'No exact callable found in codebase' and that related ids were handled via SAFE_RECONSTRUCTION thin wrappers rather than a real implementation being found.
  - Recommendation: Treat as a historical/naming-drift note, not a claim of a missing implementation to build. If `ts3_regime_3bet` (the confirmed ONLINE strategy referenced alongside it in the same memory citation) is the intended real strategy, map future references to that id instead of the phantom name.

## Runnable candidate set (future replay readiness)

142 method(s) classified `include_in_replay_readiness`:

- `tools/advanced_prediction_engine.py`
- `tools/analyze_biglotto_special.py`
- `tools/analyze_theoretical_vs_actual.py`
- `tools/audit_raw_experts.py`
- `tools/auto_discovery_biglotto.py`
- `tools/auto_optimizer_alpha.py`
- `tools/auto_optimizer_v2.py`
- `tools/backtest/big_lotto_2025_tournament.py`
- `tools/backtest_10bet_biglotto.py`
- `tools/backtest_apriori.py`
- `tools/backtest_big_lotto_3bet.py`
- `tools/backtest_big_lotto_orthogonal_5bet.py`
- `tools/backtest_biglotto_5bet_ts3markov.py`
- `tools/backtest_biglotto_6bet.py`
- `tools/backtest_biglotto_6bet_ewma.py`
- `tools/backtest_biglotto_7bet_optimized.py`
- `tools/backtest_biglotto_coldpool_15.py`
- `tools/backtest_biglotto_enhancements.py`
- `tools/backtest_biglotto_hot_stop_rebound.py`
- `tools/backtest_biglotto_markov_4bet.py`
- `tools/backtest_biglotto_portfolio.py`
- `tools/backtest_biglotto_triple_strike_original.py`
- `tools/backtest_biglotto_triple_strike_v2.py`
- `tools/backtest_graph_method.py`
- `tools/backtest_markov_repeat_exception.py`
- `tools/backtest_ml_comprehensive_2025_biglotto.py`
- `tools/backtest_must_hit.py`
- `tools/backtest_must_not_hit.py`
- `tools/backtest_p1_dynamic.py`
- `tools/backtest_radical_strategy.py`
- `tools/backtest_strategy_1.py`
- `tools/backtest_structural_group.py`
- `tools/backtest_sum_constraint.py`
- `tools/big_lotto_exhaustive_audit.py`
- `tools/biglotto_special_v4.py`
- `tools/compare_random_vs_smart.py`
- `tools/covering_strategy_research.py`
- `tools/dynamic_frequency_predictor.py`
- `tools/edge_splicer_5bet.py`
- `tools/edge_splicer_v2.py`
- `tools/eval_traits_115000021.py`
- `tools/evaluate_combinations.py`
- `tools/evolving_strategy_engine/evolution_engine.py`
- `tools/exhaustive_feature_sweep_v2.py`
- `tools/feasibility_benchmark_biglotto.py`
- `tools/final_draw_v11.py`
- `tools/find_best_test_periods.py`
- `tools/generate_2_3_bets.py`
- `tools/generate_final_predictions.py`
- `tools/generate_v7_predictions.py`
- `tools/historical_audit_rigorous.py`
- `tools/hot_cooccurrence_analyzer.py`
- `tools/negative_selector.py`
- `tools/negative_selector_optimized.py`
- `tools/optimal_2bet_3bet_matrix.py`
- `tools/optimize_biglotto_cluster.py`
- `tools/optimize_deviation_extreme_generic.py`
- `tools/power_fourier_rhythm.py`
- `tools/predict_biglotto_7bets_optimized.py`
- `tools/predict_biglotto_best.py`
- `tools/predict_biglotto_echo_phase2.py`
- `tools/predict_biglotto_quad_strike.py`
- `tools/predict_biglotto_triple_strike.py`
- `tools/predict_consensus_ensemble.py`
- `tools/predict_evolutionary_gum.py`
- `tools/predict_superlotto_best.py`
- `tools/predict_v9_anomaly_cluster.py`
- `tools/predictability_engine.py`
- `tools/quick_ml_predict.py`
- `tools/research_variant_history.py`
- `tools/scientific_baseline_report.py`
- `tools/standard_ts3_5bet.py`
- `tools/strategy_leaderboard.py`
- `tools/test_4bet_dcb.py`
- `tools/test_5bet_optimization.py`
- `tools/test_asm.py`
- `tools/test_cag.py`
- `tools/test_ces.py`
- `tools/test_cluster_cover.py`
- `tools/test_dcb.py`
- `tools/test_dms.py`
- `tools/test_ecp.py`
- `tools/test_greedy_optimizer.py`
- `tools/test_mwsc.py`
- `tools/test_pce.py`
- `tools/test_smh.py`
- `tools/test_tme.py`
- `tools/test_zdp.py`
- `tools/testing/test-all-optimizations.py`
- `tools/testing/test-optimization-b.py`
- `tools/testing/test-optimization-simple.py`
- `tools/verify_biglotto_3bet_comparison.py`
- `tools/verify_cluster_size.py`
- `tools/verify_elite7_claim.py`
- `tools/verify_gemini_2bet_claim.py`
- `tools/verify_gemini_3bet_claim.py`
- `tools/verify_markov_vs_triple_2bet.py`
- `tools/verify_randomness_impact.py`
- `ai_lab/scripts/attention_replay_predictor.py`
- `ai_lab/scripts/benchmark_ai.py`
- `ai_lab/scripts/benchmark_ai_zdp.py`
- `ai_lab/scripts/benchmark_hybrid.py`
- `ai_lab/scripts/benchmark_rl.py`
- `ai_lab/scripts/benchmark_v3.py`
- `ai_lab/scripts/graph_predictor.py`
- `ai_lab/scripts/high_prize_trend_optimizer.py`
- `ai_lab/scripts/train_critic.py`
- `lottery_api/models/advanced_strategies.py`
- `lottery_api/models/anti_consensus_strategy.py`
- `lottery_api/models/autogluon_model.py`
- `lottery_api/models/bayesian_ensemble.py`
- `lottery_api/models/big_lotto_dual_bet_optimizer.py`
- `lottery_api/models/big_lotto_optimizer.py`
- `lottery_api/models/biglotto_2bet_final.py`
- `lottery_api/models/biglotto_2bet_optimizer.py`
- `lottery_api/models/biglotto_2bet_optimizer_v2.py`
- `lottery_api/models/biglotto_3bet_optimizer.py`
- `lottery_api/models/biglotto_tme_optimizer.py`
- `lottery_api/models/concentrated_pool_predictor.py`
- `lottery_api/models/constraint_filter_predictor.py`
- `lottery_api/models/cooccurrence_graph.py`
- `lottery_api/models/core_satellite.py`
- `lottery_api/models/enhanced_dual_bet_predictor.py`
- `lottery_api/models/ensemble_predictor.py`
- `lottery_api/models/hpsb_optimizer.py`
- `lottery_api/models/lstm_attention_predictor.py`
- `lottery_api/models/mcts_portfolio_optimizer.py`
- `lottery_api/models/meta_learning.py`
- `lottery_api/models/negative_selection_biglotto.py`
- `lottery_api/models/optimized_ensemble.py`
- `lottery_api/models/optimized_predictor.py`
- `lottery_api/models/p47_wave4_powerlotto_adapters.py`
- `lottery_api/models/quantum_random_predictor.py`
- `lottery_api/models/selective_ensemble.py`
- `lottery_api/models/social_wisdom_predictor.py`
- `lottery_api/models/ultra_optimized_predictor.py`
- `lottery_api/models/xgboost_model.py`
- `lottery_api/models/zone_split.py`
- `lottery_api/tools/backtest_8_bets_2025.py`
- `lottery_api/tools/backtest_8_bets_2025_v2.py`
- `lottery_api/tools/rolling_backtest_2025.py`
- `lottery_api/engine/core_satellite.py`

## Out-of-scope directories (grouped, not individually classified)

| directory | count | reason |
|---|---|---|
| scripts_dir | 57 | Operational/ingestion/backfill/audit/migration worker scripts (scripts/p*.py task-numbered lineage). Naming and prior artifact evidence (e.g. p356a_all_strategy_inventory.py, p1_replay_truth_executable_inventory.py) indicate these are one-off task-execution or inventory scripts, not standalone candidate prediction methods. Not given individual method_classification_records in this pass; grouped here. |
| tests_dir | 220 | pytest test files (source_type=test). By definition these verify other code rather than implement a prediction method; grouped rather than individually classified. |
| lottery_api_routes | 7 | FastAPI route handlers (source_type=ui_reference/API infra), not methods. |
| lottery_api_utils | 7 | Shared utility modules (scheduler, csv validation, baseline calc), not methods. |
| lottery_api_fetcher_diagnostics | 5 | Data-fetch/diagnostics infra, not prediction methods. |
| frontend_src_js | 21 | Already fully named and classified by P541A's folklore_and_statistical_method_inventory section (17 generic frontend advisory strategy classes in src/engine/strategies/*.js, e.g. FrequencyStrategy, HotColdMixStrategy, MarkovStrategy). They have no strategy_id in the replay system and no replay coverage is possible under the current schema; not re-enumerated here. |

## Provenance and limits

Static AST parsing (ast.parse, no import/exec), regex keyword/content scoring, and git grep file discovery only. No module was imported, no script was executed, no DB connection was opened by this audit script itself.

Not performed by this task:
- DB writes of any kind
- DB reads of any kind (P541A's replay coverage numbers are reused as-is, not re-queried)
- import/execution of any classified script
- replay row generation
- OOS evaluator runs, strategy scoring, or promotion gating
- recomputation or overwrite of P536-P541A artifacts

Known limits:
- Classification is heuristic (filename/docstring/content keyword scoring plus AST structural checks); it cannot substitute for actually importing and testing a script.
- is_actual_prediction_method, method_family, and runnable_status should be treated as a first-pass triage signal, not a final verdict — confidence field reflects this.
- duplicate_of_existing_strategy only catches literal strategy_id string matches; naming-convention-similar-but-not-identical files (e.g. biglotto_2bet_final.py vs biglotto_deviation_2bet) are NOT auto-flagged as duplicates to avoid false positives.

*Historical legacy method classification audit only; not a prediction, betting edge, future-winning, or production-readiness claim.*
