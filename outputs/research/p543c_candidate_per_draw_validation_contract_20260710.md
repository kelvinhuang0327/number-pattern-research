# P543C — Candidate-linked Per-draw Validation Contract

> 本文件只生成候選與歷史 draw 的資料契約；不執行 walk-forward 或 permutation 驗證。
> 僅供描述性研究，不預測未來，也不構成投注建議。
> 本契約不表示候選可正式使用、可上線或已具備正式環境準備。

## Sources

| artifact | SHA256 | bytes |
|---|---|---:|
| `outputs/research/p543b_scoreboard_validation_feasibility_pilot_20260710.json` | `78e13eb255dac6e283e0d61a88c217019c9a4a9cc6f85f8a2b911c542742767f` | 229734 |
| `outputs/research/p543a_scoreboard_stability_packet_20260710.json` | `190fc9f9a8f2d4817a955204b5af1f5d9cf1fb186fa0695713202235f306e0e5` | 987573 |
| `outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json` | `c23a993c570de2f09c757f8ddbcf0e04b444d3312cd370c915222844ee927d5b` | 1999750 |

## Read-only Access

- DB path: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db`
- DB opened read-only: `True`
- SQL categories: PRAGMA query_only=ON; SELECT sqlite_master table inventory; PRAGMA table_info schema inventory; SELECT candidate linkage aggregates; SELECT capped candidate contract rows

## Schema Evidence

| table | columns used / inspected |
|---|---|
| `agent_locks` | runner, pid, task_id, started_at, heartbeat_at |
| `agent_task_runs` | id, runner, tick_at, outcome, task_id, message, duration_ms |
| `agent_tasks` | id, slot_key, date_folder, title, slug, status, previous_task_id, prompt_file_path, prompt_text, completed_file_path, completed_text, changed_files_json, worker_pid, started_at, completed_at, duration_seconds, error_message, created_at, updated_at |
| `draws` | id, draw, date, lottery_type, numbers, special, created_at, jackpot_amount, sell_amount, total_amount, numbers_positional |
| `prediction_explanations` | id, prediction_run_id, lottery_type, profile, explanation_json, created_at |
| `prediction_items` | id, run_id, bet_index, numbers, special, status, created_at, strategy_name, num_bets, zone_coverage |
| `prediction_results` | id, item_id, actual_draw, actual_date, actual_numbers, actual_special, hit_count, matched_numbers, special_hit, resolved_at, researched, wq_score, split_risk |
| `prediction_review_status` | id, prediction_run_id, review_session_id, review_status, resolved_at, notes |
| `prediction_runs` | id, lottery_type, latest_known_draw, latest_known_date, strategy_name, notes, created_at, snapshot_source, analyzed, analysis_note, review_json |
| `review_actions` | id, session_id, priority, action_title, action_description, expected_gain, cost_level, risk_level, validation_method, stop_condition, status, created_at, updated_at |
| `review_findings` | id, session_id, section_type, title, content, evidence_type, sort_order |
| `review_hypotheses` | id, session_id, hypothesis_type, description, expected_impact, validation_method, kill_condition, status, created_at, updated_at |
| `review_sessions` | id, game, draw, draw_date, session_type, created_at, updated_at, summary, final_decision, confidence_level, raw_report_text, parsed_successfully, status |
| `shadow_experiments` | id, session_id, game, experiment_name, base_strategy, experiment_strategy, experiment_config_json, status, notes, created_at, updated_at |
| `snapshot_schedule` | id, lottery_type, target_draw, target_date, scheduled_at, status, run_id, notes |
| `sqlite_sequence` | name, seq |
| `strategy_prediction_replays` | id, lottery_type, target_draw, target_date, strategy_id, strategy_name, strategy_version, history_cutoff_draw, replay_status, reject_reason, predicted_numbers, predicted_special, actual_numbers, actual_special, hit_numbers, hit_count, special_hit, replay_run_id, generated_at, truth_level, controlled_apply_id, source, provenance_hash, provenance_source, dry_run, prediction_cutoff_date, prediction_generated_at, bet_index |
| `strategy_replay_runs` | id, lottery_type, strategy_scope, started_at, finished_at, status, generator_version, data_hash, notes, created_at |

## Candidate Subset

| candidate | lottery | strategy ID | bet index | windows |
|---|---|---|---:|---|
| bet2_fourier_expansion_biglotto:1 | BIG_LOTTO | bet2_fourier_expansion_biglotto | 1 | 50, 300, 750 |
| biglotto_deviation_2bet:1 | BIG_LOTTO | biglotto_deviation_2bet | 1 | 50, 300, 750 |
| biglotto_echo_aware_3bet:1 | BIG_LOTTO | biglotto_echo_aware_3bet | 1 | 50, 300, 750 |
| biglotto_triple_strike:1 | BIG_LOTTO | biglotto_triple_strike | 1 | 50, 300, 750 |
| biglotto_ts3_markov_4bet_w30:1 | BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 1 | 50, 300, 750 |
| coldpool15_biglotto:1 | BIG_LOTTO | coldpool15_biglotto | 1 | 50, 300, 750 |
| fourier30_markov30_biglotto:1 | BIG_LOTTO | fourier30_markov30_biglotto | 1 | 50, 300 |
| markov_2bet_biglotto:1 | BIG_LOTTO | markov_2bet_biglotto | 1 | 50, 300, 750 |
| markov_single_biglotto:1 | BIG_LOTTO | markov_single_biglotto | 1 | 50, 300, 750 |
| ts3_regime_3bet:1 | BIG_LOTTO | ts3_regime_3bet | 1 | 50, 300, 750 |

## Contract Result

- contract_status: `generated`
- contract rows: 500
- linkage: candidate_id maps to strategy_prediction_replays.strategy_id plus bet_index.
- capped rows: latest 50 complete historical rows per selected candidate, emitted in chronological order per candidate.

## Next Recommended Task

Review the contract provenance and define a separate, authorized validation protocol before any walk-forward or permutation computation.
