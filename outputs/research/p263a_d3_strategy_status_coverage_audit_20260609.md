# P263A — D3 Strategy Status / Contract Audit Coverage Audit

_Read-only audit. No UI/API/DB/registry/adapter change._

## Summary
- Universe: **41 cells / 40 strategy_ids** (registry 38, DB 36).
- D3 coverage: **8 / 41 cells** (14 D3 rows = 8 mapped + 6 phantom).
- registered-without-rows (5): BIG_LOTTO:biglotto_ts3_acb_4bet, BIG_LOTTO:biglotto_ts3_markov_freq_5bet, DAILY_539:p1_deviation_2bet_539, POWER_LOTTO:h6_gate_mk20_ew85, POWER_LOTTO:power_shlc_midfreq
- unregistered orphans (2): POWER_LOTTO:midfreq_fourier_mk_3bet, POWER_LOTTO:pp3_freqort_4bet
- registry/lottery mismatch (1): POWER_LOTTO:midfreq_fourier_2bet

## D3 missing fields
can_open_detail, distinct_draw_count, missing_reason, registry_status, reject_reason, reject_source_artifact, reject_updated_at, status_reason, status_source, status_updated_at, success_rate_100, success_rate_1500, success_rate_30, success_rate_500

## D3 lifecycle disagreements (D3 vs registry)
- BIG_LOTTO:ts3_regime_3bet — D3=ADOPTED vs registry=ONLINE
- DAILY_539:acb_1bet — D3=ADOPTED vs registry=RETIRED
- DAILY_539:acb_markov_midfreq_3bet — D3=PROVISIONAL vs registry=RETIRED
- DAILY_539:midfreq_acb_2bet — D3=ADOPTED vs registry=RETIRED
- POWER_LOTTO:fourier_rhythm_3bet — D3=ADOPTED vs registry=ONLINE
- POWER_LOTTO:midfreq_fourier_2bet — D3=EXPERIMENTAL vs registry=RETIRED
- POWER_LOTTO:midfreq_fourier_mk_3bet — D3=PROVISIONAL vs registry=UNREGISTERED
- POWER_LOTTO:pp3_freqort_4bet — D3=ADOPTED vs registry=UNREGISTERED

## D3 replay_row_count findings (per-lottery aggregate)
- BIG_LOTTO: D3=24140 vs DB total=24140 (matches=True)
- DAILY_539: D3=36104 vs DB total=34680 (matches=False)
- POWER_LOTTO: D3=34680 vs DB total=36104 (matches=False)

## Success-rate (30/100/500/1500) availability
- raw data exists in strategy_prediction_replays: True
- exposed by D3 / any API: False / False
- contract defined: False
- open contract questions:
  - Is hit_count >= 1 a success, or a per-lottery threshold (539 M2+/M3+, BIG/POWER M3+)?
  - Is special_hit counted toward success or excluded?
  - Multi-bet: any-bet-hit per draw, or per-bet average?
  - Do per-lottery hit_count thresholds differ across 539 / BIG_LOTTO / POWER_LOTTO?
  - Window basis: last-N by target_draw (CAST INTEGER DESC) or by draw_date?
  - Window set: system evidence uses 150/500/1500; task asks 30/100/500/1500 — confirm intended windows (30/100 have no precedent in this repo).

## Coverage matrix
| lottery | strategy_id | in_D3 | lifecycle | registry_status | has_rows | can_open_detail | missing_reason |
|---|---|---|---|---|---|---|---|
| BIG_LOTTO | bet2_fourier_expansion_biglotto | NO | REJECTED | registered | Y | Y | - |
| BIG_LOTTO | biglotto_deviation_2bet | NO | ONLINE | registered | Y | Y | - |
| BIG_LOTTO | biglotto_echo_aware_3bet | NO | RETIRED | registered | Y | Y | - |
| BIG_LOTTO | biglotto_triple_strike | NO | ONLINE | registered | Y | Y | - |
| BIG_LOTTO | biglotto_ts3_acb_4bet | NO | REJECTED | registered | N | N | registered_without_rows |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | NO | RETIRED | registered | Y | Y | - |
| BIG_LOTTO | biglotto_ts3_markov_freq_5bet | NO | REJECTED | registered | N | N | registered_without_rows |
| BIG_LOTTO | cold_complement_biglotto | NO | REJECTED | registered | Y | Y | - |
| BIG_LOTTO | coldpool15_biglotto | NO | REJECTED | registered | Y | Y | - |
| BIG_LOTTO | fourier30_markov30_biglotto | NO | REJECTED | registered | Y | Y | - |
| BIG_LOTTO | markov_2bet_biglotto | NO | REJECTED | registered | Y | Y | - |
| BIG_LOTTO | markov_single_biglotto | NO | REJECTED | registered | Y | Y | - |
| BIG_LOTTO | ts3_regime_3bet | YES | ONLINE | registered | Y | Y | - |
| DAILY_539 | 539_3bet_orthogonal | NO | REJECTED | registered | Y | Y | - |
| DAILY_539 | acb_1bet | YES | RETIRED | registered | Y | Y | - |
| DAILY_539 | acb_markov_midfreq | NO | RETIRED | registered | Y | Y | - |
| DAILY_539 | acb_markov_midfreq_3bet | YES | RETIRED | registered | Y | Y | - |
| DAILY_539 | acb_single_539 | NO | REJECTED | registered | Y | Y | - |
| DAILY_539 | daily539_f4cold | NO | ONLINE | registered | Y | Y | - |
| DAILY_539 | daily539_f4cold_3bet | NO | RETIRED | registered | Y | Y | - |
| DAILY_539 | daily539_f4cold_5bet | NO | RETIRED | registered | Y | Y | - |
| DAILY_539 | daily539_markov_cold | NO | ONLINE | registered | Y | Y | - |
| DAILY_539 | markov_1bet_539 | NO | REJECTED | registered | Y | Y | - |
| DAILY_539 | midfreq_acb_2bet | YES | RETIRED | registered | Y | Y | - |
| DAILY_539 | midfreq_fourier_2bet | NO | RETIRED | registered | Y | Y | - |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | NO | REJECTED | registered | Y | Y | - |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | NO | REJECTED | registered | Y | Y | - |
| DAILY_539 | p1_deviation_2bet_539 | NO | REJECTED | registered | N | N | registered_without_rows |
| DAILY_539 | zone_gap_3bet_539 | NO | REJECTED | registered | Y | Y | - |
| POWER_LOTTO | cold_complement_2bet | NO | RETIRED | registered | Y | Y | - |
| POWER_LOTTO | fourier30_markov30_2bet | NO | RETIRED | registered | Y | Y | - |
| POWER_LOTTO | fourier_rhythm_3bet | YES | ONLINE | registered | Y | Y | - |
| POWER_LOTTO | h6_gate_mk20_ew85 | NO | OBSERVATION | registered | N | N | observation_no_data |
| POWER_LOTTO | midfreq_fourier_2bet | YES | RETIRED | registry_lottery_mismatch | Y | Y | - |
| POWER_LOTTO | midfreq_fourier_mk_3bet | YES | UNREGISTERED | unregistered_orphan | Y | Y | - |
| POWER_LOTTO | power_fourier_rhythm_2bet | NO | RETIRED | registered | Y | Y | - |
| POWER_LOTTO | power_orthogonal_5bet | NO | ONLINE | registered | Y | Y | - |
| POWER_LOTTO | power_precision_3bet | NO | ONLINE | registered | Y | Y | - |
| POWER_LOTTO | power_shlc_midfreq | NO | REJECTED | registered | N | N | registered_without_rows |
| POWER_LOTTO | pp3_freqort_4bet | YES | UNREGISTERED | unregistered_orphan | Y | Y | - |
| POWER_LOTTO | zonal_entropy_2bet | NO | RETIRED | registered | Y | Y | - |
