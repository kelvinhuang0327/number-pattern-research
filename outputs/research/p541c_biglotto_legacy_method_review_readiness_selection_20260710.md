# P541C — BIG_LOTTO Legacy Method Review & Replay-Readiness Selection

> generated_at: 2026-07-10T02:12:56.834011+00:00
> task_id: P541C_BIG_LOTTO_LEGACY_METHOD_REVIEW_AND_REPLAY_READINESS_SELECTION

**Disclaimer:** Historical legacy method review and replay-readiness selection only; not a prediction, betting edge, future-winning, or production-readiness claim.

## Summary

| Metric | Count |
|---|---|
| total_reviewed_from_p541b | 580 |
| ready_for_replay_readiness_now | 0 |
| needs_adapter_before_readiness | 173 |
| needs_refactor_before_readiness | 35 |
| needs_cto_review | 290 |
| exclude_from_replay | 82 |
| high_priority_candidates | 140 |
| medium_priority_candidates | 36 |
| low_priority_candidates | 32 |

## Selection Policy

- **method**: Deterministic re-bucketing of P541B's 580 method_classification_records using only fields P541B already computed (recommended_action, runnable_status, is_actual_prediction_method, confidence, evidence flags) plus one limited static re-check per record: does source_path still exist on disk. No file contents were re-read; no new static analysis was performed beyond what P541B already recorded.
- **bucket_A_ready_for_replay_readiness_now**: P541B's own 'runnable_as_is'/'runnable_with_existing_adapter' records (5 total) are all mark_duplicate of an already-replayed strategy id, so bucket A is legitimately empty: P541B did not surface any candidate that needs zero further work.
- **bucket_B_needs_adapter_before_readiness**: P541B recommended_action=include_in_replay_readiness (142, all is_actual_prediction_method=True, all needs_adapter_wrapper/small effort) PLUS the exclude_from_replay/hardcoded_paths_or_dates records with is_actual_prediction_method=True (31): both are confirmed real prediction methods where the only blocker is a wrapper or parameterization, matching bucket B's definition verbatim.
- **bucket_C_needs_refactor_before_readiness**: exclude_from_replay/needs_refactor_to_pure_function and exclude_from_replay/needs_db_safety_refactor records with is_actual_prediction_method=True: confirmed real methods that need pure-function extraction or DB-safety refactor before they can be safely wrapped.
- **bucket_D_needs_cto_review**: P541B's own needs_cto_review bucket (167) is carried through unchanged (P541C found no additional resolving evidence), PLUS any exclude_from_replay record whose is_actual_prediction_method is 'unknown' (identity itself, not just readiness, is unresolved): deferring these to CTO review instead of silently excluding them or silently promoting them without confirmed identity.
- **bucket_E_exclude_from_replay**: mark_not_strategy, mark_duplicate, mark_deprecated (57 total), plus exclude_from_replay/unsafe_side_effects and exclude_from_replay/imports_db_or_runs_work_at_module_load (25, excluded regardless of identity confidence because the blocker is a code-safety fact, not an identity judgment), plus any record whose source_path no longer exists on disk (phantom).
- **risk_level_rule**: high if evidence flag uses_db_anywhere=True; medium if writes_files_anywhere=True or hardcoded_abs_path=True (and not already high); else low.
- **priority_rule**: Bucket B: high if confidence=high and risk=low; medium if confidence in (high, medium) and risk<=medium; low otherwise; risk=high always caps at low. Bucket C: medium if confidence=high and risk!=high, else low. Bucket D/A: unknown/n-a. Bucket E: exclude.
- **shortlist_rule**: Bucket B members with priority=high and risk=low only (guarantees no DB import/write risk and no unsafe side effects by construction), deduplicated by method_id, round-robin diversified across method_family, capped at 20, sorted deterministically by method_id within each family.

## Bucket Sizes

- A. ready_for_replay_readiness_now: 0
- B. needs_adapter_before_readiness: 173
- C. needs_refactor_before_readiness: 35
- D. needs_cto_review: 290
- E. excluded_methods: 82

## High-Priority Candidate Shortlist (max 20, n=20)

| method_id | method_family | source_path | reason |
|---|---|---|---|
| ai_lab/scripts/attention_replay_predictor.py | ML_like | ai_lab/scripts/attention_replay_predictor.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/biglotto_2bet_optimizer.py | deviation | lottery_api/models/biglotto_2bet_optimizer.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/anti_consensus_strategy.py | folklore | lottery_api/models/anti_consensus_strategy.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| ai_lab/scripts/high_prize_trend_optimizer.py | frequency | ai_lab/scripts/high_prize_trend_optimizer.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/engine/core_satellite.py | hot_cold | lottery_api/engine/core_satellite.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/biglotto_2bet_final.py | markov | lottery_api/models/biglotto_2bet_final.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/cooccurrence_graph.py | neighbor | lottery_api/models/cooccurrence_graph.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| tools/predict_evolutionary_gum.py | regime | tools/predict_evolutionary_gum.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| ai_lab/scripts/benchmark_ai.py | report | ai_lab/scripts/benchmark_ai.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| tools/backtest_big_lotto_orthogonal_5bet.py | statistical | tools/backtest_big_lotto_orthogonal_5bet.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/constraint_filter_predictor.py | sum_range | lottery_api/models/constraint_filter_predictor.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/tools/rolling_backtest_2025.py | utility | lottery_api/tools/rolling_backtest_2025.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/enhanced_dual_bet_predictor.py | zone | lottery_api/models/enhanced_dual_bet_predictor.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| ai_lab/scripts/benchmark_rl.py | ML_like | ai_lab/scripts/benchmark_rl.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/biglotto_3bet_optimizer.py | deviation | lottery_api/models/biglotto_3bet_optimizer.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/social_wisdom_predictor.py | folklore | lottery_api/models/social_wisdom_predictor.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/big_lotto_dual_bet_optimizer.py | frequency | lottery_api/models/big_lotto_dual_bet_optimizer.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| lottery_api/models/negative_selection_biglotto.py | hot_cold | lottery_api/models/negative_selection_biglotto.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| tools/analyze_biglotto_special.py | markov | tools/analyze_biglotto_special.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |
| ai_lab/scripts/benchmark_ai_zdp.py | report | ai_lab/scripts/benchmark_ai_zdp.py | P541B: confirmed actual prediction method needing a small adapter wrapper. Appears to implement its own numbers-selection logic in well-scoped functions with no detected module-level side effects; likely only needs a thin adapter to plug into the replay strategy registry. |

## Recommended Next Task

`P541D_BIG_LOTTO_ADAPTER_DESIGN_FOR_SELECTED_METHODS_NO_DB_WRITE`

## Provenance and Limits

- **method**: Static, read-only re-bucketing of the P541B classification artifact. No DB access. No file content re-reads beyond an os.path.isfile() existence check per reviewed record. No replay generation, no OOS evaluation, no scoring/promotion gate.
- **p541b_artifacts_consumed**:
  - outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.json
  - outputs/research/p541b_biglotto_legacy_method_classification_audit_20260709.md
- **p541a_artifacts_consumed**:
  - outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.json
  - outputs/research/p541a_biglotto_strategy_inventory_replay_coverage_audit_20260709.md
- **not_performed_by_this_task**:
  - No DB write, migration, backfill, or replay row generation.
  - No OOS evaluator or strategy scoring/promotion gate.
  - No recomputation of P536-P541B artifacts.
  - No route/API/UI changes.
  - No adapter code was written; only the decision to route a method to needs_adapter_before_readiness / needs_refactor_before_readiness.
- **known_limits**:
  - The 167 needs_cto_review records inherited from P541B were not further resolved: P541B's own static evidence already shows 'no strong static signal either way' for all of them (or a syntax error for the one broken_or_import_error record), so no additional P541C-level static heuristic was applied on top of evidence P541B already weighed and found inconclusive.
  - source_path existence was the only new static check performed; 0 of 580 reviewed source paths were missing at P541C review time.
  - Risk/priority scoring is a deterministic function of P541B's own evidence flags; it is a triage aid for the next task, not a safety guarantee, and does not itself verify runtime behavior.
- **disclaimer**: Historical legacy method review and replay-readiness selection only; not a prediction, betting edge, future-winning, or production-readiness claim.
