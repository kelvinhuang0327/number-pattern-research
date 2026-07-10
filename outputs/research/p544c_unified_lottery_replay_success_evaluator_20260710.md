# P544C R1 — Unified Lottery Replay Success Evaluation

> Retrospective research only. Historical replay is not evidence of future performance or increased winning odds.
> This is not betting advice and does not establish production or go-live readiness.

## Deterministic Provenance

- schema: `p544c_unified_lottery_replay_success_evaluation.v1`
- pinned commit: `0279409fbfeba94c2b1be667c0b99f9a39e45069`
- generated_at_utc: `2026-07-10T09:11:15+00:00`
- frozen spec digest: `0a42970722d58d6e04bacca79d4d324444742882566d363622e5c5523d4b5649`
- canonical payload digest: `ba6962a7faf1fca370498268ec035413ea4e281e5412ccc9415e14dd0e83a51b`

| role | committed artifact | SHA-256 | bytes | portability |
|---|---|---|---:|---|
| `p273a_distinct_ticket_identity` | `outputs/research/p273a_distinct_ticket_identity_20260615.json` | `b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0` | 26,707,364 | `portable_blob_with_absolute_provenance_warning_not_opened` |
| `p273a_primary_window_observed_counts` | `outputs/research/p273a_primary_window_observed_counts_20260615.json` | `14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73` | 116,807 | `portable_blob_with_absolute_provenance_warning_not_opened` |
| `p273a_prize_aware_inference` | `outputs/research/p273a_prize_aware_inferential_validation_20260615.json` | `ab923a06327afcc8595f224e65bcd98fec0cfdeaf31b10aeeb86ac54ed6648fe` | 4,658,516 | `portable_repo_relative_blob` |
| `p281a_cross_lottery_verification` | `outputs/research/p281a_cross_lottery_prize_aware_validation_20260619.json` | `584d4e0de7f02d5b649d10f75a541731b07a221c4d26c83ab1f5ded5c218b68d` | 695,172 | `portable_blob_with_absolute_provenance_warning_not_opened` |
| `p536c_lift_extension` | `outputs/research/p536c_success_matrix_lift_extension_20260708.json` | `e98443bbe549ec23d46187689bd810423bfa07d2626fa2b98d919c96b54ac316` | 1,761,713 | `portable_blob_with_absolute_provenance_warning_not_opened` |
| `p542a_scoreboard` | `outputs/research/p542a_strategy_pick_combination_scoreboard_20260710.json` | `c23a993c570de2f09c757f8ddbcf0e04b444d3312cd370c915222844ee927d5b` | 1,999,750 | `portable_blob_with_absolute_provenance_warning_not_opened` |
| `p543a_stability_packet` | `outputs/research/p543a_scoreboard_stability_packet_20260710.json` | `190fc9f9a8f2d4817a955204b5af1f5d9cf1fb186fa0695713202235f306e0e5` | 987,573 | `portable_repo_relative_blob` |
| `p543c_per_draw_contract` | `outputs/research/p543c_candidate_per_draw_validation_contract_20260710.json` | `71be8549daddbc0e810e17e3e6afbd49eedc02eee402c017e562a834ef1448a5` | 515,478 | `portable_blob_with_absolute_provenance_warning_not_opened` |

## Owner-Approved BIG_LOTTO Special-Hit Amendment

- authoritative fields: `selected_numbers, special_actual`
- rule: `special_actual in selected_numbers`
- source special hits: **0**
- recomputed special hits: **63**
- source/recomputed mismatches: **63**
- M2 + special prize rows: **7**
- resolution: `semantic_drift_explained_recomputed_from_primary_fields`
- P543C source bytes were not modified.

### Affected Rows

| candidate | order | draw | date | main hits | source | recomputed |
|---|---:|---|---|---:|---:|---|
| `bet2_fourier_expansion_biglotto:1` | 3 | `115000007` | 2026/01/23 | 1 | 0 | true |
| `bet2_fourier_expansion_biglotto:1` | 5 | `115000009` | 2026/01/30 | 1 | 0 | true |
| `bet2_fourier_expansion_biglotto:1` | 14 | `115000018` | 2026/02/17 | 0 | 0 | true |
| `bet2_fourier_expansion_biglotto:1` | 18 | `115000022` | 2026/02/21 | 1 | 0 | true |
| `bet2_fourier_expansion_biglotto:1` | 32 | `115000036` | 2026/03/17 | 0 | 0 | true |
| `bet2_fourier_expansion_biglotto:1` | 45 | `115000049` | 2026/05/01 | 2 | 0 | true |
| `bet2_fourier_expansion_biglotto:1` | 50 | `115000054` | 2026/05/19 | 0 | 0 | true |
| `biglotto_deviation_2bet:1` | 2 | `115000005` | 2026/01/16 | 1 | 0 | true |
| `biglotto_deviation_2bet:1` | 20 | `115000023` | 2026/02/22 | 1 | 0 | true |
| `biglotto_deviation_2bet:1` | 37 | `115000040` | 2026/03/31 | 0 | 0 | true |
| `biglotto_deviation_2bet:1` | 45 | `115000048` | 2026/04/28 | 1 | 0 | true |
| `biglotto_deviation_2bet:1` | 48 | `115000051` | 2026/05/08 | 2 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 6 | `115000011` | 2026/02/06 | 1 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 22 | `115000027` | 2026/02/26 | 3 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 23 | `115000028` | 2026/02/27 | 1 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 33 | `115000038` | 2026/03/24 | 0 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 34 | `115000039` | 2026/03/27 | 0 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 37 | `115000042` | 2026/04/07 | 0 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 43 | `115000048` | 2026/04/28 | 1 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 46 | `115000051` | 2026/05/08 | 1 | 0 | true |
| `biglotto_echo_aware_3bet:1` | 49 | `115000054` | 2026/05/19 | 1 | 0 | true |
| `biglotto_triple_strike:1` | 1 | `115000004` | 2026/01/13 | 1 | 0 | true |
| `biglotto_triple_strike:1` | 4 | `115000007` | 2026/01/23 | 1 | 0 | true |
| `biglotto_triple_strike:1` | 6 | `115000009` | 2026/01/30 | 1 | 0 | true |
| `biglotto_triple_strike:1` | 15 | `115000018` | 2026/02/17 | 0 | 0 | true |
| `biglotto_triple_strike:1` | 19 | `115000022` | 2026/02/21 | 1 | 0 | true |
| `biglotto_triple_strike:1` | 33 | `115000036` | 2026/03/17 | 0 | 0 | true |
| `biglotto_triple_strike:1` | 46 | `115000049` | 2026/05/01 | 2 | 0 | true |
| `biglotto_ts3_markov_4bet_w30:1` | 2 | `115000007` | 2026/01/23 | 1 | 0 | true |
| `biglotto_ts3_markov_4bet_w30:1` | 4 | `115000009` | 2026/01/30 | 1 | 0 | true |
| `biglotto_ts3_markov_4bet_w30:1` | 13 | `115000018` | 2026/02/17 | 0 | 0 | true |
| `biglotto_ts3_markov_4bet_w30:1` | 17 | `115000022` | 2026/02/21 | 1 | 0 | true |
| `biglotto_ts3_markov_4bet_w30:1` | 31 | `115000036` | 2026/03/17 | 0 | 0 | true |
| `biglotto_ts3_markov_4bet_w30:1` | 44 | `115000049` | 2026/05/01 | 2 | 0 | true |
| `biglotto_ts3_markov_4bet_w30:1` | 49 | `115000054` | 2026/05/19 | 0 | 0 | true |
| `coldpool15_biglotto:1` | 1 | `115000005` | 2026/01/16 | 1 | 0 | true |
| `coldpool15_biglotto:1` | 19 | `115000023` | 2026/02/22 | 1 | 0 | true |
| `coldpool15_biglotto:1` | 36 | `115000040` | 2026/03/31 | 1 | 0 | true |
| `fourier30_markov30_biglotto:1` | 12 | `115000016` | 2026/02/15 | 1 | 0 | true |
| `fourier30_markov30_biglotto:1` | 16 | `115000020` | 2026/02/19 | 1 | 0 | true |
| `fourier30_markov30_biglotto:1` | 19 | `115000023` | 2026/02/22 | 1 | 0 | true |
| `fourier30_markov30_biglotto:1` | 24 | `115000028` | 2026/02/27 | 0 | 0 | true |
| `fourier30_markov30_biglotto:1` | 34 | `115000038` | 2026/03/24 | 1 | 0 | true |
| `fourier30_markov30_biglotto:1` | 38 | `115000042` | 2026/04/07 | 0 | 0 | true |
| `markov_2bet_biglotto:1` | 1 | `115000005` | 2026/01/16 | 1 | 0 | true |
| `markov_2bet_biglotto:1` | 6 | `115000010` | 2026/02/03 | 0 | 0 | true |
| `markov_2bet_biglotto:1` | 19 | `115000023` | 2026/02/22 | 0 | 0 | true |
| `markov_2bet_biglotto:1` | 21 | `115000025` | 2026/02/24 | 0 | 0 | true |
| `markov_2bet_biglotto:1` | 31 | `115000035` | 2026/03/13 | 0 | 0 | true |
| `markov_2bet_biglotto:1` | 36 | `115000040` | 2026/03/31 | 2 | 0 | true |
| `markov_single_biglotto:1` | 1 | `115000005` | 2026/01/16 | 1 | 0 | true |
| `markov_single_biglotto:1` | 6 | `115000010` | 2026/02/03 | 0 | 0 | true |
| `markov_single_biglotto:1` | 19 | `115000023` | 2026/02/22 | 0 | 0 | true |
| `markov_single_biglotto:1` | 21 | `115000025` | 2026/02/24 | 0 | 0 | true |
| `markov_single_biglotto:1` | 31 | `115000035` | 2026/03/13 | 0 | 0 | true |
| `markov_single_biglotto:1` | 36 | `115000040` | 2026/03/31 | 2 | 0 | true |
| `ts3_regime_3bet:1` | 1 | `115000004` | 2026/01/13 | 1 | 0 | true |
| `ts3_regime_3bet:1` | 4 | `115000007` | 2026/01/23 | 1 | 0 | true |
| `ts3_regime_3bet:1` | 6 | `115000009` | 2026/01/30 | 1 | 0 | true |
| `ts3_regime_3bet:1` | 15 | `115000018` | 2026/02/17 | 0 | 0 | true |
| `ts3_regime_3bet:1` | 19 | `115000022` | 2026/02/21 | 1 | 0 | true |
| `ts3_regime_3bet:1` | 33 | `115000036` | 2026/03/17 | 0 | 0 | true |
| `ts3_regime_3bet:1` | 46 | `115000049` | 2026/05/01 | 2 | 0 | true |

## Track 1 — BIG_LOTTO SHORT-50

| candidate | M0 | M1 | M2 | M3+ | special hits | M2+special | any prize | rate | classification |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `bet2_fourier_expansion_biglotto:1` | 20 | 19 | 8 | 3 | 7 | 1 | 4 | 0.080 | `descriptive_only` |
| `biglotto_deviation_2bet:1` | 18 | 26 | 5 | 1 | 5 | 1 | 2 | 0.040 | `near_baseline` |
| `biglotto_echo_aware_3bet:1` | 20 | 18 | 10 | 2 | 9 | 0 | 2 | 0.040 | `near_baseline` |
| `biglotto_triple_strike:1` | 19 | 20 | 8 | 3 | 7 | 1 | 4 | 0.080 | `descriptive_only` |
| `biglotto_ts3_markov_4bet_w30:1` | 19 | 19 | 9 | 3 | 7 | 1 | 4 | 0.080 | `descriptive_only` |
| `coldpool15_biglotto:1` | 23 | 19 | 6 | 2 | 3 | 0 | 2 | 0.040 | `near_baseline` |
| `fourier30_markov30_biglotto:1` | 20 | 25 | 4 | 1 | 6 | 0 | 1 | 0.020 | `near_baseline` |
| `markov_2bet_biglotto:1` | 23 | 19 | 8 | 0 | 6 | 1 | 1 | 0.020 | `near_baseline` |
| `markov_single_biglotto:1` | 23 | 19 | 8 | 0 | 6 | 1 | 1 | 0.020 | `near_baseline` |
| `ts3_regime_3bet:1` | 19 | 20 | 8 | 3 | 7 | 1 | 4 | 0.080 | `descriptive_only` |

The pairing permutation is an alignment/timing null using P543D's within-lottery re-pairing semantics. It is not an absolute-skill null.
SHORT-only results cannot exceed a diagnostic classification.

## Track 2 — Aggregate and Constant Verification

- P273A windows verified: **108**; mismatches: **0**; family size: **108**.
- P281A analytic checks: **18**; mismatches: **0**.
- P281A legacy 100/500/1500 labels are isolated from the current window policy.

## Track 3 — Normalized Summary Projections

- P542A strategy rows: **603**
- P536C lift rows: **603**
- P536C cross-lottery projections: **195**
- P543A historical evidence rows: **621**
- Raw rates were not pooled across lotteries, and overlapping lineage is not treated as independent evidence.

## Unresolved Data Dependencies

- committed official outcomes registry covering P273A identity sets: full per-draw SHORT/MID/LONG recomputation remains unavailable.
- DAILY_539 and POWER_LOTTO committed per-draw outcome joins: cross-lottery per-draw evaluation remains unavailable.
- committed official prize-amount constants: currency and return calculations are out of scope.

## Limitations and Safety

- P543C remains immutable; P544C corrects interpretation, not historical source bytes.
- P543C's stored special_hit derived field is inconsistent and is disclosed alongside the recomputed primary-field value.
- The P543C rows are complete contract rows and cannot measure registry-level no-prediction coverage.
- Historical fit does not imply a future advantage or increased winning probability.
- SHORT-50 is diagnostic only and cannot establish research, holdout, deployment, or production status.
- Full 750/300/50 per-draw analysis remains blocked by the committed outcomes-registry dependency.
- P542A, P536C, and P543A share lineage and are normalized projections, not independent evidence.
- P281A's legacy 100/500/1500 labels are isolated and do not override the current 50/300/750 policy.
- No database was opened or written.
- No API, UI, service, deployment, upstream artifact, or strategy-combination search was changed or performed.
