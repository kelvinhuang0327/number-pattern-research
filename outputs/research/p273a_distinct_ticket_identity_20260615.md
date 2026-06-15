# P273A Distinct-Ticket Identity Export

> Read-only identity evidence only. No baseline, expected successes, p-value, correction, stability, EDGE/NULL decision, GO recommendation, or production decision is computed.

## Scope and safety

- Task: `P273A_DISTINCT_TICKET_IDENTITY_READONLY_EXPORT`
- Classification: `P273A_DISTINCT_TICKET_IDENTITY_EXPORT_COMPLETE`
- Frozen groups: **36**
- Primary windows: **[50, 300, 750]**
- Planned family only: **m=108**
- Production write: `false`; services controlled: `false`
- Inference/baseline/p-value/EDGE/GO: `false`

## Provenance

- DB mode: `sqlite3 URI mode=ro + PRAGMA query_only=ON`
- query_only: `1`
- Single connection / single snapshot: `true` / `true`
- Permitted tables: draws, strategy_prediction_replays
- Primary raw SHA-256: `14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73`
- Primary canonical digest: `65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f`
- Reference raw SHA-256: `ee5cc98a4c0b673e1172d4478e72bced50167e7f206acf25fe170eee0ece7bd9`
- Reference canonical digest: `859c3889f2c698a27d16caf4195bbd0fd032cad80d8c44e990958658624b3103`
- Identity artifact digest: `ad85e447dfc7db7afd70e9fdde928bb12a2ae367d6c1f23f14b7e3504701ae51`

## Integrity summary

- Per-draw identity records: **23999**
- Same-bet-index content conflicts: **0**
- Duplicate-content draw records: **0**
- Duplicate ticket contents removed: **0**
- Artifact alignment: **PASS** (108 windows)

## Per-window identity summary

| Lottery | Strategy | Window | Support | Eligible-index dist | Distinct-ticket dist | Duplicate draws | Duplicate tickets | POWER missing-special | Alignment |
|---|---|---:|---:|---|---|---:|---:|---:|---|
| DAILY_539 | 539_3bet_orthogonal | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | 539_3bet_orthogonal | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | 539_3bet_orthogonal | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_1bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_1bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_1bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_markov_midfreq | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_markov_midfreq | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_markov_midfreq | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_markov_midfreq_3bet | 50 | 50 | `{"3": 50}` | `{"3": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_markov_midfreq_3bet | 300 | 300 | `{"3": 300}` | `{"3": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_markov_midfreq_3bet | 750 | 750 | `{"3": 750}` | `{"3": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_single_539 | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_single_539 | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | acb_single_539 | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold_3bet | 50 | 50 | `{"3": 50}` | `{"3": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold_3bet | 300 | 300 | `{"3": 300}` | `{"3": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold_3bet | 750 | 750 | `{"3": 750}` | `{"3": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold_5bet | 50 | 50 | `{"5": 50}` | `{"5": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold_5bet | 300 | 300 | `{"5": 300}` | `{"5": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_f4cold_5bet | 750 | 750 | `{"5": 750}` | `{"5": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_markov_cold | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_markov_cold | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | daily539_markov_cold | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | markov_1bet_539 | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | markov_1bet_539 | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | markov_1bet_539 | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | midfreq_acb_2bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | midfreq_acb_2bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | midfreq_acb_2bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | midfreq_fourier_2bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | midfreq_fourier_2bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | midfreq_fourier_2bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| DAILY_539 | zone_gap_3bet_539 | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| DAILY_539 | zone_gap_3bet_539 | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| DAILY_539 | zone_gap_3bet_539 | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_deviation_2bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_deviation_2bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_deviation_2bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_echo_aware_3bet | 50 | 50 | `{"3": 50}` | `{"3": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_echo_aware_3bet | 300 | 300 | `{"3": 300}` | `{"3": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_echo_aware_3bet | 750 | 750 | `{"3": 750}` | `{"3": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_triple_strike | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_triple_strike | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_triple_strike | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 50 | 50 | `{"4": 50}` | `{"4": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 300 | 300 | `{"4": 300}` | `{"4": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 750 | 750 | `{"4": 750}` | `{"4": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | cold_complement_biglotto | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | cold_complement_biglotto | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | cold_complement_biglotto | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | coldpool15_biglotto | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | coldpool15_biglotto | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | coldpool15_biglotto | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | fourier30_markov30_biglotto | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | fourier30_markov30_biglotto | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | fourier30_markov30_biglotto | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | markov_2bet_biglotto | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | markov_2bet_biglotto | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | markov_2bet_biglotto | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | markov_single_biglotto | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | markov_single_biglotto | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | markov_single_biglotto | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | ts3_regime_3bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | ts3_regime_3bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| BIG_LOTTO | ts3_regime_3bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | cold_complement_2bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | cold_complement_2bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | cold_complement_2bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | fourier30_markov30_2bet | 50 | 49 | `{"1": 49}` | `{"1": 49}` | 0 | 0 | 1 | PASS |
| POWER_LOTTO | fourier30_markov30_2bet | 300 | 299 | `{"1": 299}` | `{"1": 299}` | 0 | 0 | 1 | PASS |
| POWER_LOTTO | fourier30_markov30_2bet | 750 | 749 | `{"1": 749}` | `{"1": 749}` | 0 | 0 | 1 | PASS |
| POWER_LOTTO | fourier_rhythm_3bet | 50 | 0 | `{}` | `{}` | 0 | 0 | 150 | PASS |
| POWER_LOTTO | fourier_rhythm_3bet | 300 | 0 | `{}` | `{}` | 0 | 0 | 900 | PASS |
| POWER_LOTTO | fourier_rhythm_3bet | 750 | 0 | `{}` | `{}` | 0 | 0 | 2250 | PASS |
| POWER_LOTTO | midfreq_fourier_2bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | midfreq_fourier_2bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | midfreq_fourier_2bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 100 | PASS |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 600 | PASS |
| POWER_LOTTO | midfreq_fourier_mk_3bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 1500 | PASS |
| POWER_LOTTO | power_fourier_rhythm_2bet | 50 | 0 | `{}` | `{}` | 0 | 0 | 100 | PASS |
| POWER_LOTTO | power_fourier_rhythm_2bet | 300 | 0 | `{}` | `{}` | 0 | 0 | 600 | PASS |
| POWER_LOTTO | power_fourier_rhythm_2bet | 750 | 0 | `{}` | `{}` | 0 | 0 | 1500 | PASS |
| POWER_LOTTO | power_orthogonal_5bet | 50 | 0 | `{}` | `{}` | 0 | 0 | 250 | PASS |
| POWER_LOTTO | power_orthogonal_5bet | 300 | 0 | `{}` | `{}` | 0 | 0 | 1500 | PASS |
| POWER_LOTTO | power_orthogonal_5bet | 750 | 0 | `{}` | `{}` | 0 | 0 | 3750 | PASS |
| POWER_LOTTO | power_precision_3bet | 50 | 0 | `{}` | `{}` | 0 | 0 | 150 | PASS |
| POWER_LOTTO | power_precision_3bet | 300 | 0 | `{}` | `{}` | 0 | 0 | 900 | PASS |
| POWER_LOTTO | power_precision_3bet | 750 | 0 | `{}` | `{}` | 0 | 0 | 2250 | PASS |
| POWER_LOTTO | pp3_freqort_4bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 150 | PASS |
| POWER_LOTTO | pp3_freqort_4bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 900 | PASS |
| POWER_LOTTO | pp3_freqort_4bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 2250 | PASS |
| POWER_LOTTO | zonal_entropy_2bet | 50 | 50 | `{"1": 50}` | `{"1": 50}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | zonal_entropy_2bet | 300 | 300 | `{"1": 300}` | `{"1": 300}` | 0 | 0 | 0 | PASS |
| POWER_LOTTO | zonal_entropy_2bet | 750 | 750 | `{"1": 750}` | `{"1": 750}` | 0 | 0 | 0 | PASS |
