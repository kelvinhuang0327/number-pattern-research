# P543A — Scoreboard Stability Packet

> 本文件僅整理已提交 artifact 的歷史描述資料；不預測未來，也不構成投注建議。
> 選擇偏差注意：來源中的 top rows 是從多個候選中挑出的歷史極值，edge 僅為描述性比較，可能偏樂觀。
> 本 packet 不宣告任何候選可上線、可獲利或會在未來維持相同結果。

## Source

- source artifact: `outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json`
- SHA256: `c23a993c570de2f09c757f8ddbcf0e04b444d3312cd370c915222844ee927d5b`
- bytes: 1999750
- generated_at: `2026-07-10T00:00:00+08:00`

## Schema Summary

- top-level keys: classification, combination_leaderboard, descriptive_rankings, deterministic_output, deterministic_payload_sha256, disclaimer_zh, historical_replay_only, metric_definitions, no_betting_advice, no_prediction_claim, power_lotto_zone2_metrics, safety_flags, schema_version, source, strategy_pick_matrix, summary, task_id, window_policy
- ranking sections: top_strategy_pick_by_lottery_window_pick, best_combination_by_lottery_window_budget
- supported windows: 50, 300, 750
- direct numeric comparison is restricted to matching lottery, section, and selection-count bucket.

## Per-lottery Candidate Summary

| lottery | multi-window stable | single-window spike | prize/zone2 signal | UNKNOWN/incomplete |
|---|---:|---:|---:|---:|
| BIG_LOTTO | 49 | 84 | 0 | 0 |
| DAILY_539 | 47 | 62 | 0 | 0 |
| POWER_LOTTO | 49 | 76 | 35 | 0 |

## Top Historical Candidates by Matching Bucket

| lottery | window | section | bucket/scope | source rank | candidate | descriptive edge (pp) |
|---|---:|---|---|---:|---|---:|
| BIG_LOTTO | 50 | combination | 1 | 1 | ts3_regime_3bet:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 2 | biglotto_ts3_markov_4bet_w30:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 3 | biglotto_triple_strike:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 4 | bet2_fourier_expansion_biglotto:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 5 | markov_single_biglotto:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 6 | markov_2bet_biglotto:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 7 | biglotto_deviation_2bet:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 8 | fourier30_markov30_biglotto:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 9 | biglotto_echo_aware_3bet:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 1 | 10 | coldpool15_biglotto:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 1 | biglotto_ts3_markov_4bet_w30:2 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 2 | ts3_regime_3bet:2 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 3 | biglotto_triple_strike:2 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 4 | biglotto_echo_aware_3bet:2 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 5 | bet2_fourier_expansion_biglotto:2 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 6 | biglotto_deviation_2bet:1 + markov_single_biglotto:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 7 | biglotto_deviation_2bet:1 + markov_2bet_biglotto:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 8 | biglotto_deviation_2bet:2 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 9 | markov_single_biglotto:1 + ts3_regime_3bet:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 2 | 10 | markov_2bet_biglotto:1 + ts3_regime_3bet:1 | 0.0 |
| BIG_LOTTO | 50 | combination | 3 | 1 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:1 | -0.1595744680851064 |
| BIG_LOTTO | 50 | combination | 3 | 2 | bet2_fourier_expansion_biglotto:1 + biglotto_echo_aware_3bet:2 | -0.16337386018237082 |
| BIG_LOTTO | 50 | combination | 3 | 3 | biglotto_echo_aware_3bet:2 + ts3_regime_3bet:1 | -0.16337386018237082 |
| BIG_LOTTO | 50 | combination | 3 | 4 | biglotto_echo_aware_3bet:2 + biglotto_triple_strike:1 | -0.16337386018237082 |
| BIG_LOTTO | 50 | combination | 3 | 5 | biglotto_echo_aware_3bet:2 + markov_single_biglotto:1 | -0.15577507598784196 |
| BIG_LOTTO | 50 | combination | 3 | 6 | biglotto_echo_aware_3bet:2 + markov_2bet_biglotto:1 | -0.15577507598784196 |
| BIG_LOTTO | 50 | combination | 3 | 7 | markov_single_biglotto:1 + ts3_regime_3bet:2 | 1.8404255319148937 |
| BIG_LOTTO | 50 | combination | 3 | 8 | markov_2bet_biglotto:1 + ts3_regime_3bet:2 | 1.8404255319148937 |
| BIG_LOTTO | 50 | combination | 3 | 9 | biglotto_ts3_markov_4bet_w30:2 + markov_single_biglotto:1 | 1.8404255319148937 |
| BIG_LOTTO | 50 | combination | 3 | 10 | biglotto_ts3_markov_4bet_w30:2 + markov_2bet_biglotto:1 | 1.8404255319148937 |
| BIG_LOTTO | 50 | combination | 4 | 1 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 | -0.6062508259548037 |
| BIG_LOTTO | 50 | combination | 4 | 2 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 | -0.6166578564820933 |
| BIG_LOTTO | 50 | combination | 4 | 3 | biglotto_echo_aware_3bet:2 + ts3_regime_3bet:2 | -0.6166578564820933 |
| BIG_LOTTO | 50 | combination | 4 | 4 | biglotto_echo_aware_3bet:2 + biglotto_triple_strike:2 | -0.6166578564820933 |
| BIG_LOTTO | 50 | combination | 4 | 5 | biglotto_deviation_2bet:2 + ts3_regime_3bet:2 | 1.445784326681644 |
| BIG_LOTTO | 50 | combination | 4 | 6 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:2 | 1.445784326681644 |
| BIG_LOTTO | 50 | combination | 4 | 7 | biglotto_deviation_2bet:2 + biglotto_triple_strike:2 | 1.445784326681644 |
| BIG_LOTTO | 50 | combination | 4 | 8 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 | 1.445784326681644 |
| BIG_LOTTO | 50 | combination | 4 | 9 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:1 + markov_single_biglotto:1 | -0.5390181049292982 |
| BIG_LOTTO | 50 | combination | 4 | 10 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:1 + markov_2bet_biglotto:1 | -0.5390181049292982 |
| BIG_LOTTO | 50 | combination | 5 | 1 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 + markov_single_biglotto:1 | 0.7623893220562972 |
| BIG_LOTTO | 50 | combination | 5 | 2 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 + markov_2bet_biglotto:1 | 0.7623893220562972 |
| BIG_LOTTO | 50 | combination | 5 | 3 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 + markov_single_biglotto:1 | 0.7623893220562972 |
| BIG_LOTTO | 50 | combination | 5 | 4 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 + markov_2bet_biglotto:1 | 0.7623893220562972 |
| BIG_LOTTO | 50 | combination | 5 | 5 | biglotto_echo_aware_3bet:2 + markov_single_biglotto:1 + ts3_regime_3bet:2 | 0.7623893220562972 |
| BIG_LOTTO | 50 | combination | 5 | 6 | biglotto_echo_aware_3bet:2 + markov_2bet_biglotto:1 + ts3_regime_3bet:2 | 0.7623893220562972 |
| BIG_LOTTO | 50 | combination | 5 | 7 | biglotto_echo_aware_3bet:2 + biglotto_triple_strike:2 + markov_single_biglotto:1 | 0.7623893220562972 |
| BIG_LOTTO | 50 | combination | 5 | 8 | biglotto_echo_aware_3bet:2 + biglotto_triple_strike:2 + markov_2bet_biglotto:1 | 0.7623893220562972 |
| BIG_LOTTO | 50 | combination | 5 | 9 | biglotto_deviation_2bet:1 + biglotto_echo_aware_3bet:2 + ts3_regime_3bet:2 | -1.0565283467688646 |
| BIG_LOTTO | 50 | combination | 5 | 10 | biglotto_deviation_2bet:1 + biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 | -1.0565283467688646 |
| BIG_LOTTO | 50 | combination | 6 | 1 | biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + ts3_regime_3bet:2 | 0.16742254045676794 |
| BIG_LOTTO | 50 | combination | 6 | 2 | biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 | 0.16742254045676794 |
| BIG_LOTTO | 50 | combination | 6 | 3 | biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + biglotto_triple_strike:2 | 0.16742254045676794 |
| BIG_LOTTO | 50 | combination | 6 | 4 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 | 0.16742254045676794 |
| BIG_LOTTO | 50 | combination | 6 | 5 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 + markov_single_biglotto:2 | -0.30156661100231885 |
| BIG_LOTTO | 50 | combination | 6 | 6 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 + markov_2bet_biglotto:2 | -0.30156661100231885 |
| BIG_LOTTO | 50 | combination | 6 | 7 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 + markov_single_biglotto:2 | -0.30156661100231885 |
| BIG_LOTTO | 50 | combination | 6 | 8 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 + markov_2bet_biglotto:2 | -0.30156661100231885 |
| BIG_LOTTO | 50 | combination | 6 | 9 | biglotto_deviation_2bet:2 + markov_single_biglotto:2 + ts3_regime_3bet:2 | -0.1480681668008219 |
| BIG_LOTTO | 50 | combination | 6 | 10 | biglotto_deviation_2bet:2 + markov_2bet_biglotto:2 + ts3_regime_3bet:2 | -0.1480681668008219 |
| BIG_LOTTO | 50 | strategy_pick | 1 | 1 | ts3_regime_3bet | 0.0 |
| BIG_LOTTO | 50 | strategy_pick | 2 | 1 | biglotto_ts3_markov_4bet_w30 | 0.0 |
| BIG_LOTTO | 50 | strategy_pick | 3 | 1 | biglotto_echo_aware_3bet | -0.1899696048632219 |
| BIG_LOTTO | 50 | strategy_pick | 4 | 1 | ts3_regime_3bet | -0.7103211312276992 |
| BIG_LOTTO | 50 | strategy_pick | 5 | 1 | ts3_regime_3bet | 2.3414827540636978 |
| BIG_LOTTO | 50 | strategy_pick | 6 | 1 | biglotto_deviation_2bet | 0.9048219742021777 |
| BIG_LOTTO | 300 | combination | 1 | 1 | bet2_fourier_expansion_biglotto:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 2 | ts3_regime_3bet:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 3 | biglotto_ts3_markov_4bet_w30:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 4 | biglotto_triple_strike:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 5 | biglotto_deviation_2bet:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 6 | fourier30_markov30_biglotto:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 7 | biglotto_echo_aware_3bet:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 8 | markov_single_biglotto:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 9 | markov_2bet_biglotto:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 1 | 10 | coldpool15_biglotto:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 1 | biglotto_deviation_2bet:2 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 2 | biglotto_echo_aware_3bet:2 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 3 | bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 4 | biglotto_deviation_2bet:1 + ts3_regime_3bet:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 5 | biglotto_deviation_2bet:1 + biglotto_ts3_markov_4bet_w30:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 6 | biglotto_deviation_2bet:1 + biglotto_triple_strike:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 7 | bet2_fourier_expansion_biglotto:1 + coldpool15_biglotto:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 8 | bet2_fourier_expansion_biglotto:1 + cold_complement_biglotto:1 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 9 | biglotto_ts3_markov_4bet_w30:2 | 0.0 |
| BIG_LOTTO | 300 | combination | 2 | 10 | bet2_fourier_expansion_biglotto:2 | 0.0 |
| BIG_LOTTO | 300 | combination | 3 | 1 | bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2 | -0.16590678824721378 |
| BIG_LOTTO | 300 | combination | 3 | 2 | biglotto_deviation_2bet:2 + ts3_regime_3bet:1 | -0.16590678824721378 |
| BIG_LOTTO | 300 | combination | 3 | 3 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:1 | -0.16590678824721378 |
| BIG_LOTTO | 300 | combination | 3 | 4 | biglotto_deviation_2bet:2 + biglotto_triple_strike:1 | -0.16590678824721378 |
| BIG_LOTTO | 300 | combination | 3 | 5 | bet2_fourier_expansion_biglotto:1 + biglotto_echo_aware_3bet:2 | -0.1697061803444782 |
| BIG_LOTTO | 300 | combination | 3 | 6 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:1 | -0.16843971631205673 |
| BIG_LOTTO | 300 | combination | 3 | 7 | biglotto_echo_aware_3bet:2 + ts3_regime_3bet:1 | -0.1697061803444782 |
| BIG_LOTTO | 300 | combination | 3 | 8 | biglotto_echo_aware_3bet:2 + biglotto_triple_strike:1 | -0.1697061803444782 |
| BIG_LOTTO | 300 | combination | 3 | 9 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:1 | -0.1614741641337386 |
| BIG_LOTTO | 300 | combination | 3 | 10 | biglotto_deviation_2bet:1 + ts3_regime_3bet:2 | -0.1614741641337386 |
| BIG_LOTTO | 300 | combination | 4 | 1 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 | -0.2573069468305361 |
| BIG_LOTTO | 300 | combination | 4 | 2 | biglotto_deviation_2bet:2 + ts3_regime_3bet:2 | -0.2590414519184177 |
| BIG_LOTTO | 300 | combination | 4 | 3 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:2 | -0.2590414519184177 |
| BIG_LOTTO | 300 | combination | 4 | 4 | biglotto_deviation_2bet:2 + biglotto_triple_strike:2 | -0.2590414519184177 |
| BIG_LOTTO | 300 | combination | 4 | 5 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 | -0.2844257962204308 |
| BIG_LOTTO | 300 | combination | 4 | 6 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 | -0.28789480639619397 |
| BIG_LOTTO | 300 | combination | 4 | 7 | biglotto_echo_aware_3bet:2 + ts3_regime_3bet:2 | -0.28789480639619397 |
| BIG_LOTTO | 300 | combination | 4 | 8 | biglotto_echo_aware_3bet:2 + biglotto_triple_strike:2 | -0.28789480639619397 |
| BIG_LOTTO | 300 | combination | 4 | 9 | bet2_fourier_expansion_biglotto:2 + coldpool15_biglotto:2 | -0.639206422624554 |
| BIG_LOTTO | 300 | combination | 4 | 10 | bet2_fourier_expansion_biglotto:2 + cold_complement_biglotto:2 | -0.639206422624554 |
| BIG_LOTTO | 300 | combination | 5 | 1 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 + coldpool15_biglotto:1 | -0.5871712699881061 |
| BIG_LOTTO | 300 | combination | 5 | 2 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 + cold_complement_biglotto:1 | -0.5871712699881061 |
| BIG_LOTTO | 300 | combination | 5 | 3 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_single_biglotto:1 | -0.16807629619840536 |
| BIG_LOTTO | 300 | combination | 5 | 4 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_2bet_biglotto:1 | -0.16807629619840536 |
| BIG_LOTTO | 300 | combination | 5 | 5 | biglotto_deviation_2bet:2 + markov_single_biglotto:1 + ts3_regime_3bet:2 | -0.17123694991410063 |
| BIG_LOTTO | 300 | combination | 5 | 6 | biglotto_deviation_2bet:2 + markov_2bet_biglotto:1 + ts3_regime_3bet:2 | -0.17123694991410063 |
| BIG_LOTTO | 300 | combination | 5 | 7 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:2 + markov_single_biglotto:1 | -0.17123694991410063 |
| BIG_LOTTO | 300 | combination | 5 | 8 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:2 + markov_2bet_biglotto:1 | -0.17123694991410063 |
| BIG_LOTTO | 300 | combination | 5 | 9 | biglotto_deviation_2bet:2 + biglotto_triple_strike:2 + markov_single_biglotto:1 | -0.17123694991410063 |
| BIG_LOTTO | 300 | combination | 5 | 10 | biglotto_deviation_2bet:2 + biglotto_triple_strike:2 + markov_2bet_biglotto:1 | -0.17123694991410063 |
| BIG_LOTTO | 300 | combination | 6 | 1 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 + coldpool15_biglotto:2 | -0.8991567585462127 |
| BIG_LOTTO | 300 | combination | 6 | 2 | bet2_fourier_expansion_biglotto:2 + biglotto_echo_aware_3bet:2 + cold_complement_biglotto:2 | -0.8991567585462127 |
| BIG_LOTTO | 300 | combination | 6 | 3 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 | -0.25816543924777025 |
| BIG_LOTTO | 300 | combination | 6 | 4 | biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + ts3_regime_3bet:2 | -0.25653722369726045 |
| BIG_LOTTO | 300 | combination | 6 | 5 | biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 | -0.25653722369726045 |
| BIG_LOTTO | 300 | combination | 6 | 6 | biglotto_deviation_2bet:2 + biglotto_echo_aware_3bet:2 + biglotto_triple_strike:2 | -0.25653722369726045 |
| BIG_LOTTO | 300 | combination | 6 | 7 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 + coldpool15_biglotto:2 | -0.8895790200138023 |
| BIG_LOTTO | 300 | combination | 6 | 8 | biglotto_echo_aware_3bet:2 + biglotto_ts3_markov_4bet_w30:2 + cold_complement_biglotto:2 | -0.8895790200138023 |
| BIG_LOTTO | 300 | combination | 6 | 9 | biglotto_deviation_2bet:2 + markov_single_biglotto:2 + ts3_regime_3bet:2 | -1.0797251622876045 |
| BIG_LOTTO | 300 | combination | 6 | 10 | biglotto_deviation_2bet:2 + markov_2bet_biglotto:2 + ts3_regime_3bet:2 | -1.0797251622876045 |
| BIG_LOTTO | 300 | strategy_pick | 1 | 1 | bet2_fourier_expansion_biglotto | 0.0 |
| BIG_LOTTO | 300 | strategy_pick | 2 | 1 | biglotto_deviation_2bet | 0.0 |
| BIG_LOTTO | 300 | strategy_pick | 3 | 1 | biglotto_deviation_2bet | -0.1899696048632219 |
| BIG_LOTTO | 300 | strategy_pick | 4 | 1 | biglotto_deviation_2bet | -0.3769877978943659 |
| BIG_LOTTO | 300 | strategy_pick | 5 | 1 | biglotto_deviation_2bet | -0.9918505792696354 |
| BIG_LOTTO | 300 | strategy_pick | 6 | 1 | biglotto_deviation_2bet | 0.23815530753551056 |
| BIG_LOTTO | 750 | combination | 1 | 1 | ts3_regime_3bet:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 2 | biglotto_ts3_markov_4bet_w30:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 3 | biglotto_triple_strike:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 4 | biglotto_echo_aware_3bet:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 5 | biglotto_deviation_2bet:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 6 | bet2_fourier_expansion_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 7 | coldpool15_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 8 | cold_complement_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 9 | markov_single_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 1 | 10 | markov_2bet_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 1 | biglotto_deviation_2bet:2 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 2 | coldpool15_biglotto:1 + ts3_regime_3bet:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 3 | cold_complement_biglotto:1 + ts3_regime_3bet:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 4 | biglotto_ts3_markov_4bet_w30:1 + coldpool15_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 5 | biglotto_ts3_markov_4bet_w30:1 + cold_complement_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 6 | biglotto_triple_strike:1 + coldpool15_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 7 | biglotto_triple_strike:1 + cold_complement_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 8 | bet2_fourier_expansion_biglotto:1 + coldpool15_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 9 | bet2_fourier_expansion_biglotto:1 + cold_complement_biglotto:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 2 | 10 | bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:1 | 0.0 |
| BIG_LOTTO | 750 | combination | 3 | 1 | bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2 | -0.16134751773049646 |
| BIG_LOTTO | 750 | combination | 3 | 2 | biglotto_deviation_2bet:2 + ts3_regime_3bet:1 | -0.16286727456940223 |
| BIG_LOTTO | 750 | combination | 3 | 3 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:1 | -0.16286727456940223 |
| BIG_LOTTO | 750 | combination | 3 | 4 | biglotto_deviation_2bet:2 + biglotto_triple_strike:1 | -0.16286727456940223 |
| BIG_LOTTO | 750 | combination | 3 | 5 | coldpool15_biglotto:2 + ts3_regime_3bet:1 | -0.16590678824721378 |
| BIG_LOTTO | 750 | combination | 3 | 6 | cold_complement_biglotto:2 + ts3_regime_3bet:1 | -0.16590678824721378 |
| BIG_LOTTO | 750 | combination | 3 | 7 | biglotto_ts3_markov_4bet_w30:1 + coldpool15_biglotto:2 | -0.16590678824721378 |
| BIG_LOTTO | 750 | combination | 3 | 8 | biglotto_ts3_markov_4bet_w30:1 + cold_complement_biglotto:2 | -0.16590678824721378 |
| BIG_LOTTO | 750 | combination | 3 | 9 | biglotto_triple_strike:1 + coldpool15_biglotto:2 | -0.16590678824721378 |
| BIG_LOTTO | 750 | combination | 3 | 10 | biglotto_triple_strike:1 + cold_complement_biglotto:2 | -0.16590678824721378 |
| BIG_LOTTO | 750 | combination | 4 | 1 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 | -0.31687590855028414 |
| BIG_LOTTO | 750 | combination | 4 | 2 | coldpool15_biglotto:2 + ts3_regime_3bet:2 | -0.6061847495705036 |
| BIG_LOTTO | 750 | combination | 4 | 3 | cold_complement_biglotto:2 + ts3_regime_3bet:2 | -0.6061847495705036 |
| BIG_LOTTO | 750 | combination | 4 | 4 | biglotto_triple_strike:2 + coldpool15_biglotto:2 | -0.6061847495705036 |
| BIG_LOTTO | 750 | combination | 4 | 5 | biglotto_triple_strike:2 + cold_complement_biglotto:2 | -0.6061847495705036 |
| BIG_LOTTO | 750 | combination | 4 | 6 | biglotto_deviation_2bet:2 + ts3_regime_3bet:2 | -0.32103872076120005 |
| BIG_LOTTO | 750 | combination | 4 | 7 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:2 | -0.32103872076120005 |
| BIG_LOTTO | 750 | combination | 4 | 8 | biglotto_deviation_2bet:2 + biglotto_triple_strike:2 | -0.32103872076120005 |
| BIG_LOTTO | 750 | combination | 4 | 9 | bet2_fourier_expansion_biglotto:2 + coldpool15_biglotto:2 | -0.6038500506585613 |
| BIG_LOTTO | 750 | combination | 4 | 10 | bet2_fourier_expansion_biglotto:2 + cold_complement_biglotto:2 | -0.6038500506585613 |
| BIG_LOTTO | 750 | combination | 5 | 1 | bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2 + markov_single_biglotto:2 | -0.08110435663627145 |
| BIG_LOTTO | 750 | combination | 5 | 2 | bet2_fourier_expansion_biglotto:1 + biglotto_deviation_2bet:2 + markov_2bet_biglotto:2 | -0.08110435663627145 |
| BIG_LOTTO | 750 | combination | 5 | 3 | biglotto_deviation_2bet:2 + markov_single_biglotto:2 + ts3_regime_3bet:1 | -0.08679133077837964 |
| BIG_LOTTO | 750 | combination | 5 | 4 | biglotto_deviation_2bet:2 + markov_2bet_biglotto:2 + ts3_regime_3bet:1 | -0.08679133077837964 |
| BIG_LOTTO | 750 | combination | 5 | 5 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:1 + markov_single_biglotto:2 | -0.08679133077837964 |
| BIG_LOTTO | 750 | combination | 5 | 6 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:1 + markov_2bet_biglotto:2 | -0.08679133077837964 |
| BIG_LOTTO | 750 | combination | 5 | 7 | biglotto_deviation_2bet:2 + biglotto_triple_strike:1 + markov_single_biglotto:2 | -0.08679133077837964 |
| BIG_LOTTO | 750 | combination | 5 | 8 | biglotto_deviation_2bet:2 + biglotto_triple_strike:1 + markov_2bet_biglotto:2 | -0.08679133077837964 |
| BIG_LOTTO | 750 | combination | 5 | 9 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_single_biglotto:1 | -0.01541782300339186 |
| BIG_LOTTO | 750 | combination | 5 | 10 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_2bet_biglotto:1 | -0.01541782300339186 |
| BIG_LOTTO | 750 | combination | 6 | 1 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_single_biglotto:2 | -0.4458914505167973 |
| BIG_LOTTO | 750 | combination | 6 | 2 | bet2_fourier_expansion_biglotto:2 + biglotto_deviation_2bet:2 + markov_2bet_biglotto:2 | -0.4458914505167973 |
| BIG_LOTTO | 750 | combination | 6 | 3 | biglotto_deviation_2bet:2 + markov_single_biglotto:2 + ts3_regime_3bet:2 | -0.4543749908227245 |
| BIG_LOTTO | 750 | combination | 6 | 4 | biglotto_deviation_2bet:2 + markov_2bet_biglotto:2 + ts3_regime_3bet:2 | -0.4543749908227245 |
| BIG_LOTTO | 750 | combination | 6 | 5 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:2 + markov_single_biglotto:2 | -0.4543749908227245 |
| BIG_LOTTO | 750 | combination | 6 | 6 | biglotto_deviation_2bet:2 + biglotto_ts3_markov_4bet_w30:2 + markov_2bet_biglotto:2 | -0.4543749908227245 |
| BIG_LOTTO | 750 | combination | 6 | 7 | biglotto_deviation_2bet:2 + biglotto_triple_strike:2 + markov_single_biglotto:2 | -0.4543749908227245 |
| BIG_LOTTO | 750 | combination | 6 | 8 | biglotto_deviation_2bet:2 + biglotto_triple_strike:2 + markov_2bet_biglotto:2 | -0.4543749908227245 |
| BIG_LOTTO | 750 | combination | 6 | 9 | biglotto_echo_aware_3bet:2 + coldpool15_biglotto:2 + ts3_regime_3bet:2 | -0.73336416897934 |
| BIG_LOTTO | 750 | combination | 6 | 10 | biglotto_echo_aware_3bet:2 + cold_complement_biglotto:2 + ts3_regime_3bet:2 | -0.73336416897934 |
| BIG_LOTTO | 750 | strategy_pick | 1 | 1 | ts3_regime_3bet | 0.0 |
| BIG_LOTTO | 750 | strategy_pick | 2 | 1 | biglotto_deviation_2bet | 0.0 |
| BIG_LOTTO | 750 | strategy_pick | 3 | 1 | biglotto_deviation_2bet | 0.0766970618034448 |
| BIG_LOTTO | 750 | strategy_pick | 4 | 1 | biglotto_deviation_2bet | -0.04365446456103253 |
| BIG_LOTTO | 750 | strategy_pick | 5 | 1 | biglotto_deviation_2bet | 0.20814942073036463 |
| BIG_LOTTO | 750 | strategy_pick | 6 | 1 | coldpool15_biglotto | -0.2951780257978223 |
| DAILY_539 | 50 | combination | 1 | 1 | zone_gap_3bet_539:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 2 | p0c_539_3bet_f_cold_x2:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 3 | p0b_539_3bet_f_cold_fmid:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 4 | daily539_f4cold_5bet:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 5 | daily539_f4cold_3bet:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 6 | daily539_f4cold:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 7 | midfreq_fourier_2bet:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 8 | midfreq_acb_2bet:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 9 | acb_markov_midfreq:1 | 0.0 |
| DAILY_539 | 50 | combination | 1 | 10 | markov_1bet_539:1 | 0.0 |
| DAILY_539 | 50 | combination | 2 | 1 | p0c_539_3bet_f_cold_x2:1 + zone_gap_3bet_539:1 | 0.6504723346828609 |
| DAILY_539 | 50 | combination | 2 | 2 | p0b_539_3bet_f_cold_fmid:1 + zone_gap_3bet_539:1 | 0.6504723346828609 |
| DAILY_539 | 50 | combination | 2 | 3 | daily539_f4cold_5bet:1 + zone_gap_3bet_539:1 | 0.6504723346828609 |
| DAILY_539 | 50 | combination | 2 | 4 | daily539_f4cold_3bet:1 + zone_gap_3bet_539:1 | 0.6504723346828609 |
| DAILY_539 | 50 | combination | 2 | 5 | daily539_f4cold:1 + zone_gap_3bet_539:1 | 0.6504723346828609 |
| DAILY_539 | 50 | combination | 2 | 6 | acb_markov_midfreq:1 + p0c_539_3bet_f_cold_x2:1 | 0.7314439946018894 |
| DAILY_539 | 50 | combination | 2 | 7 | acb_markov_midfreq:1 + p0b_539_3bet_f_cold_fmid:1 | 0.7314439946018894 |
| DAILY_539 | 50 | combination | 2 | 8 | acb_markov_midfreq:1 + daily539_f4cold_5bet:1 | 0.7314439946018894 |
| DAILY_539 | 50 | combination | 2 | 9 | acb_markov_midfreq:1 + daily539_f4cold_3bet:1 | 0.7314439946018894 |
| DAILY_539 | 50 | combination | 2 | 10 | acb_markov_midfreq:1 + daily539_f4cold:1 | 0.7314439946018894 |
| DAILY_539 | 50 | combination | 3 | 1 | p0c_539_3bet_f_cold_x2:2 + zone_gap_3bet_539:1 | 0.17025932815406541 |
| DAILY_539 | 50 | combination | 3 | 2 | p0b_539_3bet_f_cold_fmid:2 + zone_gap_3bet_539:1 | 0.17025932815406541 |
| DAILY_539 | 50 | combination | 3 | 3 | daily539_f4cold_5bet:2 + zone_gap_3bet_539:1 | 0.17025932815406541 |
| DAILY_539 | 50 | combination | 3 | 4 | daily539_f4cold_3bet:2 + zone_gap_3bet_539:1 | 0.17025932815406541 |
| DAILY_539 | 50 | combination | 3 | 5 | daily539_f4cold:2 + zone_gap_3bet_539:1 | 0.17025932815406541 |
| DAILY_539 | 50 | combination | 3 | 6 | acb_single_539:2 + p0c_539_3bet_f_cold_x2:1 | 0.21986358828464114 |
| DAILY_539 | 50 | combination | 3 | 7 | acb_single_539:2 + p0b_539_3bet_f_cold_fmid:1 | 0.21986358828464114 |
| DAILY_539 | 50 | combination | 3 | 8 | acb_single_539:2 + daily539_f4cold_5bet:1 | 0.21986358828464114 |
| DAILY_539 | 50 | combination | 3 | 9 | acb_single_539:2 + daily539_f4cold_3bet:1 | 0.21986358828464114 |
| DAILY_539 | 50 | combination | 3 | 10 | acb_single_539:2 + daily539_f4cold:1 | 0.21986358828464114 |
| DAILY_539 | 50 | combination | 4 | 1 | acb_single_539:2 + p0c_539_3bet_f_cold_x2:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 2 | acb_single_539:2 + p0b_539_3bet_f_cold_fmid:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 3 | acb_single_539:2 + daily539_f4cold_5bet:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 4 | acb_single_539:2 + daily539_f4cold_3bet:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 5 | acb_single_539:2 + daily539_f4cold:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 6 | acb_markov_midfreq_3bet:2 + p0c_539_3bet_f_cold_x2:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 7 | acb_markov_midfreq_3bet:2 + p0b_539_3bet_f_cold_fmid:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 8 | acb_markov_midfreq_3bet:2 + daily539_f4cold_5bet:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 9 | acb_markov_midfreq_3bet:2 + daily539_f4cold_3bet:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 4 | 10 | acb_markov_midfreq_3bet:2 + daily539_f4cold:2 | 0.964584017215596 |
| DAILY_539 | 50 | combination | 5 | 1 | acb_single_539:2 + p0c_539_3bet_f_cold_x2:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 2 | acb_single_539:2 + p0b_539_3bet_f_cold_fmid:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 3 | acb_single_539:2 + daily539_f4cold_5bet:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 4 | acb_single_539:2 + daily539_f4cold_3bet:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 5 | acb_single_539:2 + daily539_f4cold:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 6 | acb_markov_midfreq_3bet:2 + p0c_539_3bet_f_cold_x2:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 7 | acb_markov_midfreq_3bet:2 + p0b_539_3bet_f_cold_fmid:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 8 | acb_markov_midfreq_3bet:2 + daily539_f4cold_5bet:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 9 | acb_markov_midfreq_3bet:2 + daily539_f4cold_3bet:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | combination | 5 | 10 | acb_markov_midfreq_3bet:2 + daily539_f4cold:2 + zone_gap_3bet_539:1 | 6.220759799707168 |
| DAILY_539 | 50 | strategy_pick | 1 | 1 | zone_gap_3bet_539 | 0.0 |
| DAILY_539 | 50 | strategy_pick | 2 | 1 | p0c_539_3bet_f_cold_x2 | 0.6504723346828609 |
| DAILY_539 | 50 | strategy_pick | 3 | 1 | acb_single_539 | 0.17025932815406541 |
| DAILY_539 | 50 | strategy_pick | 4 | 1 | zone_gap_3bet_539 | 0.759966444176971 |
| DAILY_539 | 50 | strategy_pick | 5 | 1 | zone_gap_3bet_539 | 4.602657023709655 |
| DAILY_539 | 300 | combination | 1 | 1 | p0c_539_3bet_f_cold_x2:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 2 | p0b_539_3bet_f_cold_fmid:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 3 | daily539_f4cold_5bet:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 4 | daily539_f4cold_3bet:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 5 | daily539_f4cold:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 6 | markov_1bet_539:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 7 | daily539_markov_cold:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 8 | midfreq_fourier_2bet:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 9 | midfreq_acb_2bet:1 | 0.0 |
| DAILY_539 | 300 | combination | 1 | 10 | acb_markov_midfreq:1 | 0.0 |
| DAILY_539 | 300 | combination | 2 | 1 | midfreq_fourier_2bet:2 | -0.016194331983805654 |
| DAILY_539 | 300 | combination | 2 | 2 | midfreq_acb_2bet:2 | -0.016194331983805654 |
| DAILY_539 | 300 | combination | 2 | 3 | daily539_f4cold_5bet:1 + midfreq_fourier_2bet:1 | 0.38461538461538464 |
| DAILY_539 | 300 | combination | 2 | 4 | daily539_f4cold_5bet:1 + midfreq_acb_2bet:1 | 0.38461538461538464 |
| DAILY_539 | 300 | combination | 2 | 5 | daily539_f4cold_3bet:1 + midfreq_fourier_2bet:1 | 0.38461538461538464 |
| DAILY_539 | 300 | combination | 2 | 6 | daily539_f4cold_3bet:1 + midfreq_acb_2bet:1 | 0.38461538461538464 |
| DAILY_539 | 300 | combination | 2 | 7 | daily539_f4cold:1 + midfreq_fourier_2bet:1 | 0.38461538461538464 |
| DAILY_539 | 300 | combination | 2 | 8 | daily539_f4cold:1 + midfreq_acb_2bet:1 | 0.38461538461538464 |
| DAILY_539 | 300 | combination | 2 | 9 | midfreq_fourier_2bet:1 + p0c_539_3bet_f_cold_x2:1 | 0.3801169590643274 |
| DAILY_539 | 300 | combination | 2 | 10 | midfreq_fourier_2bet:1 + p0b_539_3bet_f_cold_fmid:1 | 0.3801169590643274 |
| DAILY_539 | 300 | combination | 3 | 1 | daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2 | 0.7929508455824248 |
| DAILY_539 | 300 | combination | 3 | 2 | daily539_f4cold_5bet:1 + midfreq_acb_2bet:2 | 0.7929508455824248 |
| DAILY_539 | 300 | combination | 3 | 3 | daily539_f4cold_3bet:1 + midfreq_fourier_2bet:2 | 0.7929508455824248 |
| DAILY_539 | 300 | combination | 3 | 4 | daily539_f4cold_3bet:1 + midfreq_acb_2bet:2 | 0.7929508455824248 |
| DAILY_539 | 300 | combination | 3 | 5 | daily539_f4cold:1 + midfreq_fourier_2bet:2 | 0.7929508455824248 |
| DAILY_539 | 300 | combination | 3 | 6 | daily539_f4cold:1 + midfreq_acb_2bet:2 | 0.7929508455824248 |
| DAILY_539 | 300 | combination | 3 | 7 | midfreq_fourier_2bet:2 + p0c_539_3bet_f_cold_x2:1 | 0.7846834688939958 |
| DAILY_539 | 300 | combination | 3 | 8 | midfreq_fourier_2bet:2 + p0b_539_3bet_f_cold_fmid:1 | 0.7846834688939958 |
| DAILY_539 | 300 | combination | 3 | 9 | midfreq_acb_2bet:2 + p0c_539_3bet_f_cold_x2:1 | 0.7846834688939958 |
| DAILY_539 | 300 | combination | 3 | 10 | midfreq_acb_2bet:2 + p0b_539_3bet_f_cold_fmid:1 | 0.7846834688939958 |
| DAILY_539 | 300 | combination | 4 | 1 | markov_1bet_539:2 + midfreq_fourier_2bet:2 | 1.0518534729061044 |
| DAILY_539 | 300 | combination | 4 | 2 | markov_1bet_539:2 + midfreq_acb_2bet:2 | 1.0518534729061044 |
| DAILY_539 | 300 | combination | 4 | 3 | daily539_markov_cold:2 + midfreq_fourier_2bet:2 | 1.0518534729061044 |
| DAILY_539 | 300 | combination | 4 | 4 | daily539_markov_cold:2 + midfreq_acb_2bet:2 | 1.0518534729061044 |
| DAILY_539 | 300 | combination | 4 | 5 | acb_single_539:1 + daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2 | -0.4519945046260826 |
| DAILY_539 | 300 | combination | 4 | 6 | acb_single_539:1 + daily539_f4cold_5bet:1 + midfreq_acb_2bet:2 | -0.4519945046260826 |
| DAILY_539 | 300 | combination | 4 | 7 | acb_single_539:1 + daily539_f4cold_3bet:1 + midfreq_fourier_2bet:2 | -0.4519945046260826 |
| DAILY_539 | 300 | combination | 4 | 8 | acb_single_539:1 + daily539_f4cold_3bet:1 + midfreq_acb_2bet:2 | -0.4519945046260826 |
| DAILY_539 | 300 | combination | 4 | 9 | acb_single_539:1 + daily539_f4cold:1 + midfreq_fourier_2bet:2 | -0.4519945046260826 |
| DAILY_539 | 300 | combination | 4 | 10 | acb_single_539:1 + daily539_f4cold:1 + midfreq_acb_2bet:2 | -0.4519945046260826 |
| DAILY_539 | 300 | combination | 5 | 1 | acb_single_539:2 + daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 2 | acb_single_539:2 + daily539_f4cold_5bet:1 + midfreq_acb_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 3 | acb_single_539:2 + daily539_f4cold_3bet:1 + midfreq_fourier_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 4 | acb_single_539:2 + daily539_f4cold_3bet:1 + midfreq_acb_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 5 | acb_single_539:2 + daily539_f4cold:1 + midfreq_fourier_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 6 | acb_single_539:2 + daily539_f4cold:1 + midfreq_acb_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 7 | acb_markov_midfreq_3bet:2 + daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 8 | acb_markov_midfreq_3bet:2 + daily539_f4cold_5bet:1 + midfreq_acb_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 9 | acb_markov_midfreq_3bet:2 + daily539_f4cold_3bet:1 + midfreq_fourier_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | combination | 5 | 10 | acb_markov_midfreq_3bet:2 + daily539_f4cold_3bet:1 + midfreq_acb_2bet:2 | 1.226253436779752 |
| DAILY_539 | 300 | strategy_pick | 1 | 1 | p0c_539_3bet_f_cold_x2 | 0.0 |
| DAILY_539 | 300 | strategy_pick | 2 | 1 | midfreq_fourier_2bet | -0.016194331983805654 |
| DAILY_539 | 300 | strategy_pick | 3 | 1 | midfreq_fourier_2bet | 2.170259328154065 |
| DAILY_539 | 300 | strategy_pick | 4 | 1 | midfreq_fourier_2bet | 2.0932997775103046 |
| DAILY_539 | 300 | strategy_pick | 5 | 1 | midfreq_fourier_2bet | 4.602657023709657 |
| DAILY_539 | 750 | combination | 1 | 1 | p0c_539_3bet_f_cold_x2:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 2 | p0b_539_3bet_f_cold_fmid:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 3 | daily539_f4cold_5bet:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 4 | daily539_f4cold_3bet:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 5 | daily539_f4cold:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 6 | acb_markov_midfreq:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 7 | midfreq_fourier_2bet:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 8 | midfreq_acb_2bet:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 9 | zone_gap_3bet_539:1 | 0.0 |
| DAILY_539 | 750 | combination | 1 | 10 | markov_1bet_539:1 | 0.0 |
| DAILY_539 | 750 | combination | 2 | 1 | midfreq_fourier_2bet:2 | 0.25047233468286095 |
| DAILY_539 | 750 | combination | 2 | 2 | midfreq_acb_2bet:2 | 0.25047233468286095 |
| DAILY_539 | 750 | combination | 2 | 3 | daily539_f4cold_5bet:1 + midfreq_fourier_2bet:1 | 0.20530814215024734 |
| DAILY_539 | 750 | combination | 2 | 4 | daily539_f4cold_5bet:1 + midfreq_acb_2bet:1 | 0.20530814215024734 |
| DAILY_539 | 750 | combination | 2 | 5 | daily539_f4cold_3bet:1 + midfreq_fourier_2bet:1 | 0.20530814215024734 |
| DAILY_539 | 750 | combination | 2 | 6 | daily539_f4cold_3bet:1 + midfreq_acb_2bet:1 | 0.20530814215024734 |
| DAILY_539 | 750 | combination | 2 | 7 | daily539_f4cold:1 + midfreq_fourier_2bet:1 | 0.20530814215024734 |
| DAILY_539 | 750 | combination | 2 | 8 | daily539_f4cold:1 + midfreq_acb_2bet:1 | 0.20530814215024734 |
| DAILY_539 | 750 | combination | 2 | 9 | midfreq_fourier_2bet:1 + p0c_539_3bet_f_cold_x2:1 | 0.2035087719298244 |
| DAILY_539 | 750 | combination | 2 | 10 | midfreq_fourier_2bet:1 + p0b_539_3bet_f_cold_fmid:1 | 0.2035087719298244 |
| DAILY_539 | 750 | combination | 3 | 1 | daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2 | 0.994604320920111 |
| DAILY_539 | 750 | combination | 3 | 2 | daily539_f4cold_5bet:1 + midfreq_acb_2bet:2 | 0.994604320920111 |
| DAILY_539 | 750 | combination | 3 | 3 | daily539_f4cold_3bet:1 + midfreq_fourier_2bet:2 | 0.994604320920111 |
| DAILY_539 | 750 | combination | 3 | 4 | daily539_f4cold_3bet:1 + midfreq_acb_2bet:2 | 0.994604320920111 |
| DAILY_539 | 750 | combination | 3 | 5 | daily539_f4cold:1 + midfreq_fourier_2bet:2 | 0.994604320920111 |
| DAILY_539 | 750 | combination | 3 | 6 | daily539_f4cold:1 + midfreq_acb_2bet:2 | 0.994604320920111 |
| DAILY_539 | 750 | combination | 3 | 7 | midfreq_fourier_2bet:2 + p0c_539_3bet_f_cold_x2:1 | 0.9912973702447391 |
| DAILY_539 | 750 | combination | 3 | 8 | midfreq_fourier_2bet:2 + p0b_539_3bet_f_cold_fmid:1 | 0.9912973702447391 |
| DAILY_539 | 750 | combination | 3 | 9 | midfreq_acb_2bet:2 + p0c_539_3bet_f_cold_x2:1 | 0.9912973702447391 |
| DAILY_539 | 750 | combination | 3 | 10 | midfreq_acb_2bet:2 + p0b_539_3bet_f_cold_fmid:1 | 0.9912973702447391 |
| DAILY_539 | 750 | combination | 4 | 1 | acb_single_539:2 + midfreq_fourier_2bet:2 | 0.6766507398086347 |
| DAILY_539 | 750 | combination | 4 | 2 | acb_single_539:2 + midfreq_acb_2bet:2 | 0.6766507398086347 |
| DAILY_539 | 750 | combination | 4 | 3 | acb_markov_midfreq_3bet:2 + midfreq_fourier_2bet:2 | 0.6766507398086347 |
| DAILY_539 | 750 | combination | 4 | 4 | acb_markov_midfreq_3bet:2 + midfreq_acb_2bet:2 | 0.6766507398086347 |
| DAILY_539 | 750 | combination | 4 | 5 | acb_1bet:2 + midfreq_fourier_2bet:2 | 0.6766507398086347 |
| DAILY_539 | 750 | combination | 4 | 6 | acb_1bet:2 + midfreq_acb_2bet:2 | 0.6766507398086347 |
| DAILY_539 | 750 | combination | 4 | 7 | 539_3bet_orthogonal:2 + midfreq_fourier_2bet:2 | 0.6766507398086347 |
| DAILY_539 | 750 | combination | 4 | 8 | 539_3bet_orthogonal:2 + midfreq_acb_2bet:2 | 0.6766507398086347 |
| DAILY_539 | 750 | combination | 4 | 9 | acb_single_539:1 + daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2 | 0.20257018151755013 |
| DAILY_539 | 750 | combination | 4 | 10 | acb_single_539:1 + daily539_f4cold_5bet:1 + midfreq_acb_2bet:2 | 0.20257018151755013 |
| DAILY_539 | 750 | combination | 5 | 1 | acb_single_539:2 + daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 2 | acb_single_539:2 + daily539_f4cold_5bet:1 + midfreq_acb_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 3 | acb_single_539:2 + daily539_f4cold_3bet:1 + midfreq_fourier_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 4 | acb_single_539:2 + daily539_f4cold_3bet:1 + midfreq_acb_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 5 | acb_single_539:2 + daily539_f4cold:1 + midfreq_fourier_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 6 | acb_single_539:2 + daily539_f4cold:1 + midfreq_acb_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 7 | acb_markov_midfreq_3bet:2 + daily539_f4cold_5bet:1 + midfreq_fourier_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 8 | acb_markov_midfreq_3bet:2 + daily539_f4cold_5bet:1 + midfreq_acb_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 9 | acb_markov_midfreq_3bet:2 + daily539_f4cold_3bet:1 + midfreq_fourier_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | combination | 5 | 10 | acb_markov_midfreq_3bet:2 + daily539_f4cold_3bet:1 + midfreq_acb_2bet:2 | 0.8990929622508581 |
| DAILY_539 | 750 | strategy_pick | 1 | 1 | p0c_539_3bet_f_cold_x2 | 0.0 |
| DAILY_539 | 750 | strategy_pick | 2 | 1 | midfreq_fourier_2bet | 0.25047233468286095 |
| DAILY_539 | 750 | strategy_pick | 3 | 1 | midfreq_fourier_2bet | 1.2369259948207318 |
| DAILY_539 | 750 | strategy_pick | 4 | 1 | midfreq_fourier_2bet | 0.6266331108436372 |
| DAILY_539 | 750 | strategy_pick | 5 | 1 | midfreq_fourier_2bet | 2.069323690376321 |
| POWER_LOTTO | 50 | combination | 1 | 1 | power_precision_3bet:1 | 0.0 |
| POWER_LOTTO | 50 | combination | 1 | 2 | power_orthogonal_5bet:1 | 0.0 |
| POWER_LOTTO | 50 | combination | 1 | 3 | power_fourier_rhythm_2bet:1 | 0.0 |
| POWER_LOTTO | 50 | combination | 1 | 4 | fourier_rhythm_3bet:1 | 0.0 |
| POWER_LOTTO | 50 | combination | 1 | 5 | midfreq_fourier_mk_3bet:1 | -1.9736842105263164 |
| POWER_LOTTO | 50 | combination | 1 | 6 | pp3_freqort_4bet:1 | 0.026315789473683668 |
| POWER_LOTTO | 50 | combination | 1 | 7 | zonal_entropy_2bet:1 | 0.026315789473683668 |
| POWER_LOTTO | 50 | combination | 1 | 8 | cold_complement_2bet:1 | 0.026315789473683668 |
| POWER_LOTTO | 50 | combination | 1 | 9 | fourier30_markov30_2bet:1 | -1.93421052631579 |
| POWER_LOTTO | 50 | combination | 1 | 10 | midfreq_fourier_2bet:1 | -1.9736842105263164 |
| POWER_LOTTO | 50 | combination | 2 | 1 | midfreq_fourier_mk_3bet:2 | 0.31934566145092536 |
| POWER_LOTTO | 50 | combination | 2 | 2 | pp3_freqort_4bet:2 | 2.319345661450925 |
| POWER_LOTTO | 50 | combination | 2 | 3 | power_precision_3bet:2 | 0.0 |
| POWER_LOTTO | 50 | combination | 2 | 4 | power_orthogonal_5bet:2 | 0.0 |
| POWER_LOTTO | 50 | combination | 2 | 5 | power_fourier_rhythm_2bet:2 | 0.0 |
| POWER_LOTTO | 50 | combination | 2 | 6 | fourier_rhythm_3bet:2 | 0.0 |
| POWER_LOTTO | 50 | combination | 2 | 7 | cold_complement_2bet:1 + power_precision_3bet:1 | 0.42176386913229114 |
| POWER_LOTTO | 50 | combination | 2 | 8 | cold_complement_2bet:1 + power_orthogonal_5bet:1 | 0.42176386913229114 |
| POWER_LOTTO | 50 | combination | 2 | 9 | cold_complement_2bet:1 + power_fourier_rhythm_2bet:1 | 0.42176386913229114 |
| POWER_LOTTO | 50 | combination | 2 | 10 | cold_complement_2bet:1 + fourier_rhythm_3bet:1 | 0.42176386913229114 |
| POWER_LOTTO | 50 | combination | 3 | 1 | cold_complement_2bet:2 + power_precision_3bet:1 | 0.7426505452821246 |
| POWER_LOTTO | 50 | combination | 3 | 2 | cold_complement_2bet:2 + power_orthogonal_5bet:1 | 0.7426505452821246 |
| POWER_LOTTO | 50 | combination | 3 | 3 | cold_complement_2bet:2 + power_fourier_rhythm_2bet:1 | 0.7426505452821246 |
| POWER_LOTTO | 50 | combination | 3 | 4 | cold_complement_2bet:2 + fourier_rhythm_3bet:1 | 0.7426505452821246 |
| POWER_LOTTO | 50 | combination | 3 | 5 | midfreq_fourier_2bet:1 + midfreq_fourier_mk_3bet:2 | -0.8883357041251774 |
| POWER_LOTTO | 50 | combination | 3 | 6 | fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:1 | -1.0878378378378377 |
| POWER_LOTTO | 50 | combination | 3 | 7 | fourier30_markov30_2bet:2 + fourier_rhythm_3bet:1 | -1.0878378378378377 |
| POWER_LOTTO | 50 | combination | 3 | 8 | fourier30_markov30_2bet:2 + power_precision_3bet:1 | -1.1902560455192028 |
| POWER_LOTTO | 50 | combination | 3 | 9 | fourier30_markov30_2bet:2 + power_orthogonal_5bet:1 | -1.1902560455192028 |
| POWER_LOTTO | 50 | combination | 3 | 10 | cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2 | 0.3003793266951174 |
| POWER_LOTTO | 50 | combination | 4 | 1 | fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | -4.221872248188037 |
| POWER_LOTTO | 50 | combination | 4 | 2 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + power_precision_3bet:1 | -1.0052157420578467 |
| POWER_LOTTO | 50 | combination | 4 | 3 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:1 | -1.0052157420578467 |
| POWER_LOTTO | 50 | combination | 4 | 4 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:1 | -1.0052157420578467 |
| POWER_LOTTO | 50 | combination | 4 | 5 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + fourier_rhythm_3bet:1 | -1.0052157420578467 |
| POWER_LOTTO | 50 | combination | 4 | 6 | fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:2 | -2.69511616880038 |
| POWER_LOTTO | 50 | combination | 4 | 7 | fourier30_markov30_2bet:2 + fourier_rhythm_3bet:2 | -2.69511616880038 |
| POWER_LOTTO | 50 | combination | 4 | 8 | fourier30_markov30_2bet:2 + power_precision_3bet:2 | -2.82110682110682 |
| POWER_LOTTO | 50 | combination | 4 | 9 | fourier30_markov30_2bet:2 + power_orthogonal_5bet:2 | -2.82110682110682 |
| POWER_LOTTO | 50 | combination | 4 | 10 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + pp3_freqort_4bet:1 | -3.8375668901984654 |
| POWER_LOTTO | 50 | combination | 5 | 1 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_precision_3bet:1 | 0.14347474409393823 |
| POWER_LOTTO | 50 | combination | 5 | 2 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:1 | 0.14347474409393823 |
| POWER_LOTTO | 50 | combination | 5 | 3 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:1 | 0.14347474409393823 |
| POWER_LOTTO | 50 | combination | 5 | 4 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + fourier_rhythm_3bet:1 | 0.14347474409393823 |
| POWER_LOTTO | 50 | combination | 5 | 5 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + pp3_freqort_4bet:1 | -1.3867737706746959 |
| POWER_LOTTO | 50 | combination | 5 | 6 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | -5.083678990799734 |
| POWER_LOTTO | 50 | combination | 5 | 7 | fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 + power_precision_3bet:1 | -0.5498085436165923 |
| POWER_LOTTO | 50 | combination | 5 | 8 | fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 + power_orthogonal_5bet:1 | -0.5498085436165923 |
| POWER_LOTTO | 50 | combination | 5 | 9 | fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 + power_fourier_rhythm_2bet:1 | -0.5498085436165923 |
| POWER_LOTTO | 50 | combination | 5 | 10 | fourier30_markov30_2bet:2 + fourier_rhythm_3bet:1 + midfreq_fourier_2bet:2 | -0.5498085436165923 |
| POWER_LOTTO | 50 | combination | 6 | 1 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_precision_3bet:2 | -2.1739896786336423 |
| POWER_LOTTO | 50 | combination | 6 | 2 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:2 | -2.1739896786336423 |
| POWER_LOTTO | 50 | combination | 6 | 3 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:2 | -2.1739896786336423 |
| POWER_LOTTO | 50 | combination | 6 | 4 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + fourier_rhythm_3bet:2 | -2.1739896786336423 |
| POWER_LOTTO | 50 | combination | 6 | 5 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + pp3_freqort_4bet:2 | -4.007940794318504 |
| POWER_LOTTO | 50 | combination | 6 | 6 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | -4.504739229197432 |
| POWER_LOTTO | 50 | combination | 6 | 7 | fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 + power_precision_3bet:2 | -2.798423287587373 |
| POWER_LOTTO | 50 | combination | 6 | 8 | fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 + power_orthogonal_5bet:2 | -2.798423287587373 |
| POWER_LOTTO | 50 | combination | 6 | 9 | fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 + power_fourier_rhythm_2bet:2 | -2.798423287587373 |
| POWER_LOTTO | 50 | combination | 6 | 10 | fourier30_markov30_2bet:2 + fourier_rhythm_3bet:2 + midfreq_fourier_2bet:2 | -2.798423287587373 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 1 | pp3_freqort_4bet:2 | 2.319345661450925 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 2 | cold_complement_2bet:2 + fourier_rhythm_3bet:1 | 0.7426505452821246 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 3 | cold_complement_2bet:2 + power_fourier_rhythm_2bet:1 | 0.7426505452821246 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 4 | cold_complement_2bet:2 + power_orthogonal_5bet:1 | 0.7426505452821246 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 5 | cold_complement_2bet:2 + power_precision_3bet:1 | 0.7426505452821246 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 6 | cold_complement_2bet:1 + fourier_rhythm_3bet:1 | 0.42176386913229114 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 7 | cold_complement_2bet:1 + power_fourier_rhythm_2bet:1 | 0.42176386913229114 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 8 | cold_complement_2bet:1 + power_orthogonal_5bet:1 | 0.42176386913229114 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 9 | cold_complement_2bet:1 + power_precision_3bet:1 | 0.42176386913229114 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | combination | 10 | midfreq_fourier_mk_3bet:2 | 0.31934566145092536 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 1 | pp3_freqort_4bet | 2.813113865745445 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 2 | midfreq_fourier_mk_3bet | 2.700917635902156 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 3 | pp3_freqort_4bet | 2.319345661450925 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 4 | midfreq_fourier_mk_3bet | 2.217037752641468 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 5 | fourier_rhythm_3bet | 1.1126464810675336 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 6 | power_fourier_rhythm_2bet | 1.1126464810675336 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 7 | power_orthogonal_5bet | 1.1126464810675336 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 8 | power_precision_3bet | 1.1126464810675336 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 9 | midfreq_fourier_mk_3bet | 0.8131138657454449 |
| POWER_LOTTO | 50 | power_lotto_zone2_metrics | strategy_pick | 10 | pp3_freqort_4bet | 0.7009176359021568 |
| POWER_LOTTO | 50 | strategy_pick | 1 | 1 | power_precision_3bet | 0.0 |
| POWER_LOTTO | 50 | strategy_pick | 2 | 1 | midfreq_fourier_mk_3bet | 0.31934566145092536 |
| POWER_LOTTO | 50 | strategy_pick | 3 | 1 | cold_complement_2bet | 0.6420104314841156 |
| POWER_LOTTO | 50 | strategy_pick | 4 | 1 | midfreq_fourier_2bet | -3.1868861342545554 |
| POWER_LOTTO | 50 | strategy_pick | 5 | 1 | midfreq_fourier_2bet | -3.2990823640978437 |
| POWER_LOTTO | 50 | strategy_pick | 6 | 1 | midfreq_fourier_2bet | -1.7829622473585327 |
| POWER_LOTTO | 300 | combination | 1 | 1 | zonal_entropy_2bet:1 | 1.3596491228070169 |
| POWER_LOTTO | 300 | combination | 1 | 2 | fourier30_markov30_2bet:1 | 0.6995614035087715 |
| POWER_LOTTO | 300 | combination | 1 | 3 | midfreq_fourier_mk_3bet:1 | -0.640350877192983 |
| POWER_LOTTO | 300 | combination | 1 | 4 | midfreq_fourier_2bet:1 | -1.3070175438596496 |
| POWER_LOTTO | 300 | combination | 1 | 5 | cold_complement_2bet:1 | 0.35964912280701705 |
| POWER_LOTTO | 300 | combination | 1 | 6 | power_precision_3bet:1 | 0.0 |
| POWER_LOTTO | 300 | combination | 1 | 7 | power_orthogonal_5bet:1 | 0.0 |
| POWER_LOTTO | 300 | combination | 1 | 8 | power_fourier_rhythm_2bet:1 | 0.0 |
| POWER_LOTTO | 300 | combination | 1 | 9 | fourier_rhythm_3bet:1 | 0.0 |
| POWER_LOTTO | 300 | combination | 1 | 10 | pp3_freqort_4bet:1 | -0.9736842105263164 |
| POWER_LOTTO | 300 | combination | 2 | 1 | midfreq_fourier_mk_3bet:2 | -1.013987671882408 |
| POWER_LOTTO | 300 | combination | 2 | 2 | fourier30_markov30_2bet:2 | 0.6649478425794226 |
| POWER_LOTTO | 300 | combination | 2 | 3 | zonal_entropy_2bet:2 | 0.6526789947842587 |
| POWER_LOTTO | 300 | combination | 2 | 4 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 | 3.3508771929824586 |
| POWER_LOTTO | 300 | combination | 2 | 5 | midfreq_fourier_2bet:1 + zonal_entropy_2bet:1 | -0.1321716453295388 |
| POWER_LOTTO | 300 | combination | 2 | 6 | midfreq_fourier_2bet:2 | -2.013987671882408 |
| POWER_LOTTO | 300 | combination | 2 | 7 | cold_complement_2bet:1 + midfreq_fourier_mk_3bet:1 | 1.3694879089615948 |
| POWER_LOTTO | 300 | combination | 2 | 8 | fourier30_markov30_2bet:1 + midfreq_fourier_2bet:1 | -1.2381460407776177 |
| POWER_LOTTO | 300 | combination | 2 | 9 | cold_complement_2bet:1 + midfreq_fourier_2bet:1 | -0.6987908961593168 |
| POWER_LOTTO | 300 | combination | 2 | 10 | cold_complement_2bet:1 + zonal_entropy_2bet:1 | 1.0542911332385025 |
| POWER_LOTTO | 300 | combination | 3 | 1 | cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2 | 2.516397976924292 |
| POWER_LOTTO | 300 | combination | 3 | 2 | midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:1 | 1.9720048996364787 |
| POWER_LOTTO | 300 | combination | 3 | 3 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 | 3.2293345977556496 |
| POWER_LOTTO | 300 | combination | 3 | 4 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 | 2.562667931088984 |
| POWER_LOTTO | 300 | combination | 3 | 5 | fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 1.4648332543069382 |
| POWER_LOTTO | 300 | combination | 3 | 6 | midfreq_fourier_2bet:2 + zonal_entropy_2bet:1 | 1.0271850798166589 |
| POWER_LOTTO | 300 | combination | 3 | 7 | cold_complement_2bet:1 + midfreq_fourier_2bet:2 | -0.5571360834518729 |
| POWER_LOTTO | 300 | combination | 3 | 8 | cold_complement_2bet:1 + zonal_entropy_2bet:2 | 0.3757705073494544 |
| POWER_LOTTO | 300 | combination | 3 | 9 | cold_complement_2bet:2 + zonal_entropy_2bet:1 | 1.0424371740161218 |
| POWER_LOTTO | 300 | combination | 3 | 10 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 + midfreq_fourier_2bet:1 | 1.4736446973289075 |
| POWER_LOTTO | 300 | combination | 4 | 1 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 | 2.250423355686515 |
| POWER_LOTTO | 300 | combination | 4 | 2 | fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 1.7126233376233397 |
| POWER_LOTTO | 300 | combination | 4 | 3 | cold_complement_2bet:2 + zonal_entropy_2bet:2 | 0.2500846711373031 |
| POWER_LOTTO | 300 | combination | 4 | 4 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 + midfreq_fourier_2bet:2 | 2.075187969924813 |
| POWER_LOTTO | 300 | combination | 4 | 5 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 + midfreq_fourier_2bet:1 | 0.013276434329070885 |
| POWER_LOTTO | 300 | combination | 4 | 6 | cold_complement_2bet:1 + midfreq_fourier_2bet:2 + zonal_entropy_2bet:1 | 0.6715437241753066 |
| POWER_LOTTO | 300 | combination | 4 | 7 | midfreq_fourier_2bet:2 + zonal_entropy_2bet:2 | -0.2944523470839261 |
| POWER_LOTTO | 300 | combination | 4 | 8 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 3.899681636523744 |
| POWER_LOTTO | 300 | combination | 4 | 9 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_2bet:1 | 1.1868183973447133 |
| POWER_LOTTO | 300 | combination | 4 | 10 | cold_complement_2bet:2 + midfreq_fourier_mk_3bet:2 | 1.8022082232608567 |
| POWER_LOTTO | 300 | combination | 5 | 1 | cold_complement_2bet:1 + midfreq_fourier_2bet:2 + zonal_entropy_2bet:2 | -0.709145678185924 |
| POWER_LOTTO | 300 | combination | 5 | 2 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 | 1.6802698319726195 |
| POWER_LOTTO | 300 | combination | 5 | 3 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_2bet:1 | -0.4294161476823988 |
| POWER_LOTTO | 300 | combination | 5 | 4 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 3.0623657713441 |
| POWER_LOTTO | 300 | combination | 5 | 5 | cold_complement_2bet:2 + midfreq_fourier_2bet:1 + zonal_entropy_2bet:2 | -1.7670368289563338 |
| POWER_LOTTO | 300 | combination | 5 | 6 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1 | 2.259695343286677 |
| POWER_LOTTO | 300 | combination | 5 | 7 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 2.3329468344948228 |
| POWER_LOTTO | 300 | combination | 5 | 8 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_precision_3bet:1 | 1.3761231377330456 |
| POWER_LOTTO | 300 | combination | 5 | 9 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:1 | 1.3761231377330456 |
| POWER_LOTTO | 300 | combination | 5 | 10 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:1 | 1.3761231377330456 |
| POWER_LOTTO | 300 | combination | 6 | 1 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 1.9172296014401264 |
| POWER_LOTTO | 300 | combination | 6 | 2 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 | -0.23480631530167495 |
| POWER_LOTTO | 300 | combination | 6 | 3 | cold_complement_2bet:2 + midfreq_fourier_2bet:2 + zonal_entropy_2bet:2 | -1.342255890243507 |
| POWER_LOTTO | 300 | combination | 6 | 4 | cold_complement_2bet:2 + midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:2 | -0.24678850375444983 |
| POWER_LOTTO | 300 | combination | 6 | 5 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + pp3_freqort_4bet:2 | 0.5840642218351205 |
| POWER_LOTTO | 300 | combination | 6 | 6 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_precision_3bet:2 | 1.2044796193402985 |
| POWER_LOTTO | 300 | combination | 6 | 7 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:2 | 1.2044796193402985 |
| POWER_LOTTO | 300 | combination | 6 | 8 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:2 | 1.2044796193402985 |
| POWER_LOTTO | 300 | combination | 6 | 9 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + fourier_rhythm_3bet:2 | 1.2044796193402985 |
| POWER_LOTTO | 300 | combination | 6 | 10 | fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 + midfreq_fourier_mk_3bet:2 | 1.2126901538666246 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 1 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 3.899681636523744 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 2 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 | 3.3508771929824586 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 3 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 | 3.2293345977556496 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 4 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 3.0623657713441 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 5 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 | 2.562667931088984 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 6 | cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2 | 2.516397976924292 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 7 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 2.3329468344948228 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 8 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1 | 2.259695343286677 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 9 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 | 2.250423355686515 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | combination | 10 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 + midfreq_fourier_2bet:2 | 2.075187969924813 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 1 | zonal_entropy_2bet | 1.3596491228070169 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 2 | zonal_entropy_2bet | 1.3086770981507825 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 3 | zonal_entropy_2bet | 0.8131138657454449 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 4 | cold_complement_2bet | 0.7009176359021568 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 5 | fourier30_markov30_2bet | 0.6995614035087715 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 6 | fourier30_markov30_2bet | 0.6649478425794226 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 7 | zonal_entropy_2bet | 0.6526789947842587 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 8 | cold_complement_2bet | 0.4797805324121107 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 9 | cold_complement_2bet | 0.35964912280701705 |
| POWER_LOTTO | 300 | power_lotto_zone2_metrics | strategy_pick | 10 | cold_complement_2bet | 0.3086770981507822 |
| POWER_LOTTO | 300 | strategy_pick | 1 | 1 | zonal_entropy_2bet | 1.3596491228070169 |
| POWER_LOTTO | 300 | strategy_pick | 2 | 1 | midfreq_fourier_mk_3bet | -1.013987671882408 |
| POWER_LOTTO | 300 | strategy_pick | 3 | 1 | fourier30_markov30_2bet | -0.34091986723565615 |
| POWER_LOTTO | 300 | strategy_pick | 4 | 1 | zonal_entropy_2bet | 0.8131138657454449 |
| POWER_LOTTO | 300 | strategy_pick | 5 | 1 | fourier30_markov30_2bet | -1.274995915862788 |
| POWER_LOTTO | 300 | strategy_pick | 6 | 1 | fourier30_markov30_2bet | -0.08991839332396778 |
| POWER_LOTTO | 750 | combination | 1 | 1 | midfreq_fourier_mk_3bet:1 | 0.15964912280701687 |
| POWER_LOTTO | 750 | combination | 1 | 2 | fourier30_markov30_2bet:1 | 0.428947368421052 |
| POWER_LOTTO | 750 | combination | 1 | 3 | pp3_freqort_4bet:1 | -0.24035087719298312 |
| POWER_LOTTO | 750 | combination | 1 | 4 | power_precision_3bet:1 | 0.0 |
| POWER_LOTTO | 750 | combination | 1 | 5 | power_orthogonal_5bet:1 | 0.0 |
| POWER_LOTTO | 750 | combination | 1 | 6 | power_fourier_rhythm_2bet:1 | 0.0 |
| POWER_LOTTO | 750 | combination | 1 | 7 | fourier_rhythm_3bet:1 | 0.0 |
| POWER_LOTTO | 750 | combination | 1 | 8 | cold_complement_2bet:1 | 0.026315789473683668 |
| POWER_LOTTO | 750 | combination | 1 | 9 | zonal_entropy_2bet:1 | 0.29298245614035046 |
| POWER_LOTTO | 750 | combination | 1 | 10 | midfreq_fourier_2bet:1 | -0.7736842105263163 |
| POWER_LOTTO | 750 | combination | 2 | 1 | midfreq_fourier_mk_3bet:2 | 0.31934566145092536 |
| POWER_LOTTO | 750 | combination | 2 | 2 | cold_complement_2bet:1 + midfreq_fourier_mk_3bet:1 | 0.6439307728781429 |
| POWER_LOTTO | 750 | combination | 2 | 3 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 | 1.2231626363205321 |
| POWER_LOTTO | 750 | combination | 2 | 4 | fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:1 | 1.3996206733048855 |
| POWER_LOTTO | 750 | combination | 2 | 5 | fourier30_markov30_2bet:2 | 0.05758653390232418 |
| POWER_LOTTO | 750 | combination | 2 | 6 | pp3_freqort_4bet:2 | 0.31934566145092536 |
| POWER_LOTTO | 750 | combination | 2 | 7 | zonal_entropy_2bet:2 | 0.1860123281175921 |
| POWER_LOTTO | 750 | combination | 2 | 8 | fourier30_markov30_2bet:1 + power_precision_3bet:1 | 1.0097202465623525 |
| POWER_LOTTO | 750 | combination | 2 | 9 | fourier30_markov30_2bet:1 + power_orthogonal_5bet:1 | 1.0097202465623525 |
| POWER_LOTTO | 750 | combination | 2 | 10 | fourier30_markov30_2bet:1 + power_fourier_rhythm_2bet:1 | 1.0146277856804178 |
| POWER_LOTTO | 750 | combination | 3 | 1 | cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2 | 1.1152046783625746 |
| POWER_LOTTO | 750 | combination | 3 | 2 | fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 1.6421289710763411 |
| POWER_LOTTO | 750 | combination | 3 | 3 | midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:1 | 1.0700885095621961 |
| POWER_LOTTO | 750 | combination | 3 | 4 | cold_complement_2bet:2 + midfreq_fourier_mk_3bet:1 | 0.07571518887308504 |
| POWER_LOTTO | 750 | combination | 3 | 5 | fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1 | 1.3936936936936941 |
| POWER_LOTTO | 750 | combination | 3 | 6 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 | 1.199778726094515 |
| POWER_LOTTO | 750 | combination | 3 | 7 | fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:1 | 0.45235498656551254 |
| POWER_LOTTO | 750 | combination | 3 | 8 | fourier30_markov30_2bet:2 + fourier_rhythm_3bet:1 | 0.45235498656551254 |
| POWER_LOTTO | 750 | combination | 3 | 9 | fourier30_markov30_2bet:2 + power_precision_3bet:1 | 0.44552710605342205 |
| POWER_LOTTO | 750 | combination | 3 | 10 | fourier30_markov30_2bet:2 + power_orthogonal_5bet:1 | 0.44552710605342205 |
| POWER_LOTTO | 750 | combination | 4 | 1 | fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 1.6982185192711525 |
| POWER_LOTTO | 750 | combination | 4 | 2 | cold_complement_2bet:2 + midfreq_fourier_mk_3bet:2 | 0.0037390774232884394 |
| POWER_LOTTO | 750 | combination | 4 | 3 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 2.3528359186253955 |
| POWER_LOTTO | 750 | combination | 4 | 4 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1 | 2.2027162500846744 |
| POWER_LOTTO | 750 | combination | 4 | 5 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 | 0.9137167242430411 |
| POWER_LOTTO | 750 | combination | 4 | 6 | midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:2 | 0.5835455756508401 |
| POWER_LOTTO | 750 | combination | 4 | 7 | cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:1 | 0.914687619950777 |
| POWER_LOTTO | 750 | combination | 4 | 8 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:1 | 2.091255164939379 |
| POWER_LOTTO | 750 | combination | 4 | 9 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + power_precision_3bet:1 | 1.0194201720517522 |
| POWER_LOTTO | 750 | combination | 4 | 10 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:1 | 1.0194201720517522 |
| POWER_LOTTO | 750 | combination | 5 | 1 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 1.6829115714564635 |
| POWER_LOTTO | 750 | combination | 5 | 2 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1 | 1.8289125038351062 |
| POWER_LOTTO | 750 | combination | 5 | 3 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 1.0767188240872472 |
| POWER_LOTTO | 750 | combination | 5 | 4 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_2bet:1 | 0.01946997860310662 |
| POWER_LOTTO | 750 | combination | 5 | 5 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_precision_3bet:1 | 0.4470986687704931 |
| POWER_LOTTO | 750 | combination | 5 | 6 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:1 | 0.4470986687704931 |
| POWER_LOTTO | 750 | combination | 5 | 7 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:1 | 0.4470986687704931 |
| POWER_LOTTO | 750 | combination | 5 | 8 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + fourier_rhythm_3bet:1 | 0.4470986687704931 |
| POWER_LOTTO | 750 | combination | 5 | 9 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + pp3_freqort_4bet:1 | -0.07454885225783026 |
| POWER_LOTTO | 750 | combination | 5 | 10 | cold_complement_2bet:1 + midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:2 | 0.6868666100864257 |
| POWER_LOTTO | 750 | combination | 6 | 1 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 0.7500696144659008 |
| POWER_LOTTO | 750 | combination | 6 | 2 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_2bet:2 | -0.9326697772518211 |
| POWER_LOTTO | 750 | combination | 6 | 3 | cold_complement_2bet:2 + midfreq_fourier_mk_3bet:2 + zonal_entropy_2bet:2 | -0.1494013011040879 |
| POWER_LOTTO | 750 | combination | 6 | 4 | cold_complement_2bet:2 + midfreq_fourier_2bet:2 + zonal_entropy_2bet:2 | -0.975070184977303 |
| POWER_LOTTO | 750 | combination | 6 | 5 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + pp3_freqort_4bet:2 | -0.1448439714693578 |
| POWER_LOTTO | 750 | combination | 6 | 6 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_precision_3bet:2 | 0.26121279495892324 |
| POWER_LOTTO | 750 | combination | 6 | 7 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_orthogonal_5bet:2 | 0.26121279495892324 |
| POWER_LOTTO | 750 | combination | 6 | 8 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + power_fourier_rhythm_2bet:2 | 0.26121279495892324 |
| POWER_LOTTO | 750 | combination | 6 | 9 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + fourier_rhythm_3bet:2 | 0.26121279495892324 |
| POWER_LOTTO | 750 | combination | 6 | 10 | cold_complement_2bet:2 + pp3_freqort_4bet:2 + zonal_entropy_2bet:2 | -0.607327056862661 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 1 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 2.3528359186253955 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 2 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1 | 2.2027162500846744 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 3 | cold_complement_2bet:2 + fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:1 | 2.091255164939379 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 4 | cold_complement_2bet:2 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1 | 1.8289125038351062 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 5 | fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 1.6982185192711525 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 6 | cold_complement_2bet:1 + fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:2 | 1.6829115714564635 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 7 | fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:2 | 1.6421289710763411 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 8 | fourier30_markov30_2bet:1 + midfreq_fourier_mk_3bet:1 | 1.3996206733048855 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 9 | fourier30_markov30_2bet:2 + midfreq_fourier_mk_3bet:1 | 1.3936936936936941 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | combination | 10 | cold_complement_2bet:1 + fourier30_markov30_2bet:1 | 1.2231626363205321 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 1 | midfreq_fourier_mk_3bet | 1.6837044193081323 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 2 | midfreq_fourier_mk_3bet | 1.63425096923549 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 3 | pp3_freqort_4bet | 1.500917635902156 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 4 | fourier_rhythm_3bet | 1.2601854397520034 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 5 | power_fourier_rhythm_2bet | 1.2601854397520034 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 6 | power_orthogonal_5bet | 1.2601854397520034 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 7 | power_precision_3bet | 1.2601854397520034 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 8 | fourier_rhythm_3bet | 1.196860629677967 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 9 | power_fourier_rhythm_2bet | 1.196860629677967 |
| POWER_LOTTO | 750 | power_lotto_zone2_metrics | strategy_pick | 10 | power_orthogonal_5bet | 1.196860629677967 |
| POWER_LOTTO | 750 | strategy_pick | 1 | 1 | midfreq_fourier_mk_3bet | 0.15964912280701687 |
| POWER_LOTTO | 750 | strategy_pick | 2 | 1 | midfreq_fourier_mk_3bet | 0.31934566145092536 |
| POWER_LOTTO | 750 | strategy_pick | 3 | 1 | midfreq_fourier_mk_3bet | 0.5086770981507817 |
| POWER_LOTTO | 750 | strategy_pick | 4 | 1 | midfreq_fourier_mk_3bet | 1.0797805324121112 |
| POWER_LOTTO | 750 | strategy_pick | 5 | 1 | midfreq_fourier_mk_3bet | 1.63425096923549 |
| POWER_LOTTO | 750 | strategy_pick | 6 | 1 | midfreq_fourier_mk_3bet | 1.6837044193081323 |

## UNKNOWN / Missing-data Rows

| section | source key | missing fields |
|---|---|---|
| NONE | No incomplete selected ranking rows | — |

## Excluded / Not-comparable Rows

| lottery | section | differing bucket values | reason |
|---|---|---|---|
| BIG_LOTTO | combination | 1, 2, 3, 4, 5, 6 | Rows with different selection-count buckets are retained separately and are not numerically ranked against each other. |
| BIG_LOTTO | strategy_pick | 1, 2, 3, 4, 5, 6 | Rows with different selection-count buckets are retained separately and are not numerically ranked against each other. |
| DAILY_539 | combination | 1, 2, 3, 4, 5 | Rows with different selection-count buckets are retained separately and are not numerically ranked against each other. |
| DAILY_539 | strategy_pick | 1, 2, 3, 4, 5 | Rows with different selection-count buckets are retained separately and are not numerically ranked against each other. |
| POWER_LOTTO | combination | 1, 2, 3, 4, 5, 6 | Rows with different selection-count buckets are retained separately and are not numerically ranked against each other. |
| POWER_LOTTO | strategy_pick | 1, 2, 3, 4, 5, 6 | Rows with different selection-count buckets are retained separately and are not numerically ranked against each other. |

## Next-step Recommendation

P543B 可先評估 walk-forward / permutation 驗證的可行性，並以本 packet 的 evidence、bucket 與 UNKNOWN 狀態作為輸入；本任務不實作該驗證。
